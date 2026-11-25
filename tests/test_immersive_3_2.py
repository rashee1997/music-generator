# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""M3: the 3.2 target, the data-driven fold chain (3.2 -> 3.1 -> 2.0) and the ADM DirectSpeakers pack."""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import render_targets  # noqa: E402
from spatial_engine import adm, config, downmix, master, render  # noqa: E402

SR = 44100


def tone(f, seconds=2.0, amp=0.3):
    t = np.arange(int(SR * seconds)) / SR
    return amp * np.sin(2 * np.pi * f * t)


class Target(unittest.TestCase):
    def test_targets_are_valid_and_buildable(self):
        self.assertEqual(render_targets.manifest_problems(), [])
        for name in ('immersive_3_2', 'adm_3_2'):
            t = render_targets.get(name)
            self.assertTrue(render_targets.buildable(name), name)
            self.assertEqual(t['channel_order'], config.channel_names('lrc_lfe2'))
            self.assertEqual(t['channels'], 5)

    def test_default_targets_are_unchanged(self):
        self.assertEqual(render_targets.default(), ['stereo', 'immersive_7_1'])
        self.assertEqual(render_targets.canonical('3.2'), 'immersive_3_2')

    def test_bus_end_to_end_places_left_lead_and_both_subs(self):
        bus = render.LayoutBus('lrc_lfe2', 'immersive_3_2', SR)
        bus.add('lead', tone(440), dict(role='melody', spatial=dict(azimuth=-30.0, elevation=0.0)))
        bus.add('sub', tone(45), dict(role='bass'))
        audio = bus.result()
        self.assertEqual(audio.shape[1], 5)
        rms = [float(np.sqrt(np.mean(audio[SR // 2:, i] ** 2))) for i in range(5)]
        self.assertGreater(rms[0], 10 * rms[1])                 # L, not R
        self.assertGreater(rms[3], 0.01)
        self.assertGreater(rms[4], 0.01)                        # both low-frequency channels carry the bass


class FoldChain(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(5)
        self.x = rng.standard_normal((SR // 2, 5)) * 0.1

    def test_stages_run_in_the_order_the_layout_declares(self):
        stages = downmix.fold_chain(self.x, 'lrc_lfe2')
        self.assertEqual([n for n, _ in stages], ['lrc_lfe2', 'lrc_lfe1', 'stereo_bs775'])
        self.assertEqual([a.shape[1] for _, a in stages], [5, 4, 2])

    def test_the_chain_ends_where_the_direct_fold_ends(self):
        stages = downmix.fold_chain(self.x, 'lrc_lfe2')
        self.assertTrue(np.allclose(stages[-1][1], downmix.fold(self.x, 'lrc_lfe2')))

    def test_a_layout_without_a_chain_folds_in_one_step(self):
        x = np.zeros((100, 6))
        stages = downmix.fold_chain(x, 'itu_bs2051_system_b')
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[-1][1].shape[1], 2)

    def test_lfe_sum_gain_follows_the_coherence(self):
        self.assertAlmostEqual(downmix.lfe_sum_gain(1.0), 0.5, places=6)
        self.assertAlmostEqual(downmix.lfe_sum_gain(0.0), 0.70710678, places=6)
        self.assertEqual(downmix.lfe_sum_gain(-1.0), 1.0)         # opposed: capped, not amplified

    def test_identical_subs_fold_to_unit_level_and_unrelated_ones_keep_power(self):
        y = np.zeros((SR, 5))
        y[:, 3] = y[:, 4] = tone(50, 1.0)
        merged = downmix.fold_chain(y, 'lrc_lfe2')[1][1][:, 3]
        self.assertAlmostEqual(float(np.std(merged) / np.std(y[:, 3])), 1.0, delta=0.01)
        rng = np.random.default_rng(1)
        z = np.zeros((SR * 4, 5))
        z[:, 3], z[:, 4] = rng.standard_normal(SR * 4), rng.standard_normal(SR * 4)
        merged = downmix.fold_chain(z, 'lrc_lfe2')[1][1][:, 3]
        self.assertAlmostEqual(float(np.std(merged) / np.std(z[:, 3])), 1.0, delta=0.05)

    def test_merge_refuses_a_stage_that_is_not_two_lfe_into_one(self):
        with self.assertRaises(ValueError):
            downmix._merge_lfe(np.zeros((10, 4)), 'lrc_lfe1', 'lrc_lfe1')


class AdmSpeakers(unittest.TestCase):
    def test_pack_validates_and_round_trips(self):
        bed = adm.SpeakerBed('lrc_lfe2', SR, {'title': 'bed'})
        audio = np.stack([tone(220 + 10 * i, 1.0, 0.1) for i in range(5)], axis=1).astype(np.float32)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'x.wav')
            adm.write(path, audio, SR, bed.xml(len(audio), SR), bed.chna())
            self.assertEqual(adm.validate_file(path), [])
            parsed = adm.parse(path)
            self.assertEqual(parsed['channels'], 5)
            self.assertEqual(adm.validate_adm(bed.xml(len(audio), SR), bed.chna(), SR, 5), [])

    def test_labels_positions_and_lfe_frequency(self):
        bed = adm.SpeakerBed('lrc_lfe2', SR)
        root = ET.fromstring(bed.xml(SR, SR))
        ns = {'e': 'urn:ebu:metadata-schema:ebuCore_2016'}
        labels = [e.text for e in root.iter('{%s}speakerLabel' % ns['e'])]
        self.assertEqual(labels, ['M+030', 'M-030', 'M+000', 'LFE1', 'LFE2'])
        az = {}
        for ch in root.findall('.//e:audioChannelFormat', ns):
            p = ch.find(".//e:position[@coordinate='azimuth']", ns)
            az[ch.get('audioChannelFormatName')] = float(p.text)
        self.assertEqual((az['L'], az['R'], az['C']), (30.0, -30.0, 0.0))     # ADM azimuth is positive to the left
        freq = root.findall('.//e:frequency', ns)
        self.assertEqual(len(freq), 2)
        self.assertTrue(all(f.get('typeDefinition') == 'lowPass' for f in freq))
        self.assertEqual(len(root.findall('.//e:audioPackFormat', ns)), 1)
        self.assertEqual(root.find('.//e:audioPackFormat', ns).get('typeLabel'), '0001')

    def test_a_broken_chna_is_caught_by_the_validator(self):
        bed = adm.SpeakerBed('lrc_lfe2', SR)
        chna = bed.chna()[:-1]
        self.assertTrue(adm.validate_adm(bed.xml(SR, SR), chna, SR, 4))


if __name__ == '__main__':
    unittest.main()
