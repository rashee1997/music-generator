# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The multichannel core, measured: panning energy, the low-frequency stopband, channel order and fold-down."""
import sys
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import render_targets
from spatial_engine import bass, config, downmix, pan, render

SR = 44100
LAYOUTS = ['itu_bs2051_system_h', 'itu_bs2051_system_j']


class LayoutData(unittest.TestCase):
    def test_shipped_layouts_are_valid(self):
        self.assertEqual(config.problems(), [])
        for name in LAYOUTS:
            self.assertTrue(config.channel_names(name))

    def test_target_channel_order_matches_its_layout(self):
        for name in target_names():
            t = render_targets.get(name)
            if t.get('layout'):
                self.assertEqual(list(t['channel_order']), config.channel_names(t['layout']),
                                 msg=f'{name} channel order vs its layout')


def target_names():
    return [n for n in render_targets.names() if render_targets.get(n).get('layout')]


class Panning(unittest.TestCase):
    def test_gains_are_power_normalised(self):
        rng = np.random.default_rng(3)
        for layout in LAYOUTS:
            spk = config.speakers(layout)
            for _ in range(40):
                az = float(rng.uniform(-180.0, 180.0))
                el = float(rng.uniform(0.0, 30.0))
                g = pan.gains(az, el, spk)
                self.assertAlmostEqual(sum(v * v for v in g.values()), 1.0, places=6,
                                       msg=f'{layout} az {az:.1f} el {el:.1f}')
                self.assertTrue(all(v >= -1e-9 for v in g.values()), msg=f'{layout} negative gain')

    def test_front_centre_is_the_centre_speaker(self):
        spk = config.speakers('itu_bs2051_system_h')
        g = pan.gains(0.0, 0.0, spk)
        self.assertGreater(g.get('FC', 0.0), 0.99)

    def test_elevated_direction_uses_height_speakers(self):
        spk = config.speakers('itu_bs2051_system_j')
        g = pan.gains(-30.0, 30.0, spk)
        self.assertGreater(g.get('TFL', 0.0), 0.9)


class Bass(unittest.TestCase):
    def test_lfe_stopband(self):
        cfg = config.lfe_cfg('itu_bs2051_system_j', 'immersive_7_1_4')
        t = np.arange(SR) / SR
        tone = 0.5 * np.sin(2 * np.pi * 1000.0 * t)          # a main-band signal must not reach the LFE
        bus = bass.lfe_bus([tone], SR, cfg)
        self.assertLess(bass.stopband_leak_db(bus, SR, cfg, reference=tone), -45.0)

    def test_crossover_passes_its_own_band(self):
        cfg = config.lfe_cfg('itu_bs2051_system_h', 'immersive_7_1')
        t = np.arange(SR) / SR
        low = bass.lowpass(0.5 * np.sin(2 * np.pi * 40.0 * t), SR, cfg['lowpass_hz'])
        self.assertGreater(np.sqrt(np.mean(low ** 2)), 0.2)


class Rendering(unittest.TestCase):
    def test_channel_count_and_order(self):
        n = SR // 2
        stems = {'cello': np.random.default_rng(1).standard_normal(n) * 0.1}
        specs = {'cello': dict(role='melody', azimuth=-30.0, elevation=30.0)}
        audio = render.render_stems(stems, 'itu_bs2051_system_j', specs=specs, sr=SR)
        self.assertEqual(audio.shape, (n, 12))
        self.assertTrue(np.isfinite(audio).all())

    def test_height_only_source_lands_in_the_overhead_channels(self):
        n = SR // 2
        stems = {'flute': np.random.default_rng(2).standard_normal(n) * 0.1}
        specs = {'flute': dict(role='melody', azimuth=-30.0, elevation=30.0)}
        audio = render.render_stems(stems, 'itu_bs2051_system_j', specs=specs, sr=SR)
        names = config.channel_names('itu_bs2051_system_j')
        energy = {name: float(np.sqrt(np.mean(audio[:, i] ** 2))) for i, name in enumerate(names)}
        self.assertGreater(energy['TFL'], energy['FL'] * 3.0)

    def test_low_role_is_sent_to_the_lfe_and_the_mains_are_high_passed(self):
        n = SR
        t = np.arange(n) / SR
        stems = {'sub': 0.5 * np.sin(2 * np.pi * 40.0 * t)}
        audio = render.render_stems(stems, 'itu_bs2051_system_h', target_name='immersive_7_1',
                                    specs={'sub': dict(role='bass', azimuth=0.0, elevation=0.0)}, sr=SR)
        names = config.channel_names('itu_bs2051_system_h')
        lfe = audio[:, names.index('LFE')]
        fc = audio[:, names.index('FC')]
        dry = float(np.sqrt(np.mean(stems['sub'] ** 2)))      # 0.5 / sqrt(2)
        self.assertGreater(np.sqrt(np.mean(lfe ** 2)), 0.05)
        self.assertLess(np.sqrt(np.mean(fc ** 2)), dry * 0.1)   # the mains are high-passed, not full range


class FoldDown(unittest.TestCase):
    def test_front_left_folds_left_and_lfe_is_left_out(self):
        names = config.channel_names('itu_bs2051_system_h')
        audio = np.zeros((100, len(names)))
        audio[:, names.index('FL')] = 1.0
        audio[:, names.index('LFE')] = 1.0
        fold = downmix.fold(audio, 'itu_bs2051_system_h')
        self.assertAlmostEqual(float(fold[:, 0].mean()), 1.0, places=6)
        self.assertAlmostEqual(float(fold[:, 1].mean()), 0.0, places=6)

    def test_centre_folds_to_both_sides(self):
        names = config.channel_names('itu_bs2051_system_h')
        audio = np.zeros((100, len(names)))
        audio[:, names.index('FC')] = 1.0
        fold = downmix.fold(audio, 'itu_bs2051_system_h')
        self.assertAlmostEqual(float(fold[:, 0].mean()), float(fold[:, 1].mean()), places=6)
        self.assertAlmostEqual(float(fold[:, 0].mean()), 0.7071, places=4)


if __name__ == '__main__':
    unittest.main()
