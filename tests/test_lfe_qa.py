# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""M4: the low-frequency pair and front-stage rows: measurements on synthetic channels with a known answer."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import gate_profiles  # noqa: E402
import lint_coverage  # noqa: E402
import spatial_gate  # noqa: E402
from spatial_engine import bass, config, lfe_qa, render  # noqa: E402

SR = 44100
CFG = config.lfe_cfg('lrc_lfe2', 'immersive_3_2')


def tone(f, seconds=3.0, amp=0.3):
    t = np.arange(int(SR * seconds)) / SR
    return amp * np.sin(2 * np.pi * f * t)


def programme(flip=False, same=False):
    """A five-channel 3.2 programme from the real bus: a lead on the left and a bass line on both subs."""
    bus = render.LayoutBus('lrc_lfe2', 'immersive_3_2', SR)
    bus.add('lead', tone(440, 3.0, 0.2), dict(role='melody', spatial=dict(azimuth=-30.0, elevation=0.0)))
    bus.add('sub', tone(35, 3.0, 0.5) + tone(70, 3.0, 0.3), dict(role='bass'))
    y = bus.result()
    if flip:
        y[:, 4] *= -1.0
    if same:
        y[:, 4] = y[:, 3]
    return y


class Measurements(unittest.TestCase):
    def test_polarity_reads_identical_and_inverted(self):
        x = tone(50)
        self.assertGreater(lfe_qa.polarity(x, x, SR)[0], 0.99)
        rho0, best, _ = lfe_qa.polarity(x, -x, SR)
        self.assertLess(rho0, -0.99)
        self.assertGreater(best, 0.99)

    def test_coherence_is_high_under_the_corner_for_the_engine_pair(self):
        a, b = bass.lfe_bus_pair([tone(30) + tone(60)], [0.0], SR, CFG)
        self.assertGreater(lfe_qa.coherence(a, b, SR, 20.0, 40.0), 0.95)
        self.assertLess(lfe_qa.coherence(a, b, SR, 55.0, 80.0), 0.8)        # and it falls above the corner

    def test_fold_loss_is_zero_for_identical_channels_and_large_for_opposed_ones(self):
        x = tone(50) + tone(30)
        bands, k = lfe_qa.fold_loss_db(x, x, SR)
        self.assertAlmostEqual(k, 0.5, places=2)
        self.assertLess(max(abs(v) for c, v in bands if 25 <= c <= 63), 0.5)
        bands, _ = lfe_qa.fold_loss_db(x, -x, SR)
        self.assertGreater(max(v for _, v in bands), 20.0)

    def test_engine_pair_folds_within_the_limit(self):
        a, b = bass.lfe_bus_pair([tone(30) + tone(45) + tone(70)], [0.0], SR, CFG)
        bands, _ = lfe_qa.fold_loss_db(a, b, SR)
        limit = float(gate_profiles.defaults('lfe.fold_loss')['max_db'])
        self.assertLess(max(abs(v) for c, v in bands if 25 <= c <= 80), limit)

    def test_two_subs_in_opposite_corners_flatten_a_box_room_and_two_at_one_spot_do_not(self):
        room = dict(config.layout('lrc_lfe2')['qa']['listening_room'])
        far = lfe_qa.modal_spread(room)
        self.assertGreater(far['improvement_db'], 1.0)
        room['subs_m'] = [room['subs_m'][0], room['subs_m'][0]]
        same = lfe_qa.modal_spread(room)
        self.assertLess(abs(same['improvement_db']), 0.2)

    def test_modal_model_finds_the_first_axial_mode(self):
        modes = lfe_qa._modes([5.0, 4.0, 2.5], 60.0)
        axial = min(m[3] for m in modes)
        self.assertAlmostEqual(axial, 343.0 / (2 * 5.0), delta=0.1)

    def test_phantom_fold_has_small_cue_errors_through_the_measured_head(self):
        from spatial_hrtf import binaural
        if not binaural.available():
            self.skipTest('head data not installed')
        m = lfe_qa.phantom_fold_error('lrc_lfe2', SR)
        self.assertLess(m['itd_error_us'], 300.0)
        self.assertLess(m['ild_error_db'], 6.0)
        self.assertAlmostEqual(m['itd_phantom_us'], 0.0, delta=25.0)       # a symmetric pair has no time difference


class Rows(unittest.TestCase):
    def levels(self, y):
        out = []
        spatial_gate.lfe_rows({}, y, SR, 'immersive_3_2', out)
        return {r[1]: r[0] for r in out}

    def test_a_clean_programme_has_no_failure(self):
        got = self.levels(programme())
        self.assertNotIn('FAIL', got.values())
        for row in ('lfe.polarity', 'lfe.sum_coherence', 'lfe.fold_loss', 'lfe.modal_spread'):
            self.assertIn(row, got)

    def test_an_inverted_sub_fails_polarity(self):
        got = self.levels(programme(flip=True))
        self.assertEqual(got['lfe.polarity'], 'FAIL')
        self.assertEqual(got['lfe.sum_coherence'], 'WARN')

    def test_identical_subs_pass_coherence(self):
        self.assertEqual(self.levels(programme(same=True))['lfe.sum_coherence'], 'PASS')

    def test_one_lfe_layouts_get_no_pair_rows(self):
        out = []
        spatial_gate.lfe_rows({}, np.zeros((SR, 6)), SR, 'immersive_5_1', out)
        self.assertEqual([r for r in out if r[1].startswith('lfe.')], [])

    def test_every_new_row_is_registered_with_a_range_and_a_coverage_entry(self):
        for rid in ('lfe.sum_coherence', 'lfe.polarity', 'lfe.fold_loss', 'lfe.modal_spread', 'front.fold_phantom'):
            row = gate_profiles.ROWS[rid]
            self.assertTrue(row.get('hint'), rid)
            for name, (default, lo, hi) in (row.get('params') or {}).items():
                self.assertLessEqual(lo, default, (rid, name))
                self.assertLessEqual(default, hi, (rid, name))
            self.assertIn(rid, lint_coverage.COVERAGE)
            self.assertFalse(row.get('protected'))

    def test_layout_declares_its_own_decoder_bounds(self):
        lim = config.threshold('lrc_lfe2', 'decode_uniformity_max_db')
        self.assertGreater(lim['allrad2'], 0.34)          # measured 0.34 dB, declared with margin
        self.assertGreater(lim['allrad'], 3.26)           # measured 3.26 dB


if __name__ == '__main__':
    unittest.main()
