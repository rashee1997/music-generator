"""The low end of a master: a master high-pass that removes the written bass is caught before a render, the sub row sees the loss,
and the virtual bass puts harmonics where a small speaker can reproduce them.

Highway Pursuit rendered with `mastering.highpass_hz` 105, order 4 (copied from project to project since Night Pursuit): the
stems carried 20-80 Hz and the master kept 22 dB less of it, and realism.sub_weight passed because the master was not "thin".
"""
import os
import sys
import unittest

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import preflight_lint  # noqa: E402
import realism_cinema as rc  # noqa: E402
from mix_engine import mastering  # noqa: E402

SR = 44100


def band_db(x, a, b):
    f, p = signal.welch(x if x.ndim == 1 else x.mean(axis=1), SR, nperseg=16384)
    return 10 * np.log10(p[(f >= a) & (f < b)].sum() + 1e-30)


class VirtualBass(unittest.TestCase):
    def tone(self):
        t = np.arange(SR * 3) / SR
        x = 0.3 * np.sin(2 * np.pi * 45 * t)
        return np.stack([x, x], 1).astype(np.float32)

    def test_it_adds_harmonics_above_the_sub_and_leaves_the_sub_alone(self):
        x = self.tone()
        y = mastering.virtual_bass(x, SR, (30, 90), (80, 240), 4.0, -6.0)
        self.assertGreater(band_db(y, 80, 240), band_db(x, 80, 240) + 25.0)     # a pure 45 Hz tone has nothing there
        self.assertAlmostEqual(band_db(y, 30, 70), band_db(x, 30, 70), delta=0.5)

    def test_the_harmonics_follow_the_bass_level(self):
        x = self.tone()
        x[SR:2 * SR] *= 0.05                                                       # a quiet second in the middle
        y = mastering.virtual_bass(x, SR, (30, 90), (80, 240), 4.0, -6.0)
        mid = band_db(y[SR + 4000:2 * SR - 4000], 80, 240)
        loud = band_db(y[4000:SR - 4000], 80, 240)
        self.assertLess(mid, loud - 15.0)                                         # no level of their own when the bass is quiet

    def test_silence_stays_silence(self):
        self.assertFalse(np.any(mastering.virtual_bass(np.zeros((SR, 2), np.float32), SR)))


class SubWeight(unittest.TestCase):
    def test_a_master_that_lost_the_sub_the_stems_carry_is_warned(self):
        t = np.arange(SR * 4) / SR
        sub = (0.4 * np.sin(2 * np.pi * 40 * t)).astype(np.float32)
        mid = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        stems = {'bass': np.stack([sub, sub], 1)}
        master_ok = np.stack([sub + mid, sub + mid], 1)
        sos = signal.butter(4, 105 / (SR / 2), 'high', output='sos')
        gone = signal.sosfilt(sos, master_ok, axis=0).astype(np.float32)
        self.assertEqual(rc.sub_weight(master_ok, stems, SR)['verdict'], 'PASS')
        self.assertEqual(rc.sub_weight(gone, stems, SR)['verdict'], 'WARN')


class MasterHighpassRow(unittest.TestCase):
    def score(self, hp, order):
        import presets
        presets._CACHE = getattr(presets, '_CACHE', None)
        return {'mix_preset': 'x', 'tracks': [dict(name='basses', role='bass', notes=[dict(t=i, d=1, p=36 + (i % 4), v=0.8) for i in range(8)])]}, hp, order

    def run_row(self, hp, order):
        from unittest import mock
        score, hp, order = self.score(hp, order)
        mix = {'x': {'mastering': {'highpass_hz': hp, 'highpass_order': order}}}
        with mock.patch('presets.load', return_value=mix):
            return preflight_lint.master_highpass_rows(score)

    def test_a_105_hz_fourth_order_master_removes_a_bass_written_at_65_hz(self):
        rows = self.run_row(105.0, 4)
        self.assertEqual(rows[0][0], 'FAIL')
        self.assertIn('do not move the part up an octave', rows[0][2])

    def test_the_default_24_hz_first_order_passes(self):
        self.assertEqual(self.run_row(24.0, 1)[0][0], 'PASS')

    def test_a_moderate_cut_above_the_limit_warns_without_failing(self):
        self.assertEqual(self.run_row(50.0, 1)[0][0], 'WARN')       # lowest note 65 Hz: only 2.7 dB down, so not lost


if __name__ == '__main__':
    unittest.main()


class RestDip(unittest.TestCase):
    def test_the_gain_dips_inside_a_rest_and_nowhere_else(self):
        g = mastering.rest_gain(SR * 10, SR, [(4.0, 5.0)], -30.0, 15.0, 120.0)
        self.assertAlmostEqual(float(g[int(3.9 * SR)]), 1.0, places=6)
        self.assertAlmostEqual(20 * np.log10(g[int(4.5 * SR)]), -30.0, places=3)
        self.assertAlmostEqual(float(g[int(5.2 * SR)]), 1.0, places=6)
        self.assertLess(float(np.max(np.abs(np.diff(g)))), 0.01)           # raised-cosine ramps, no step

    def test_no_rest_means_no_curve(self):
        self.assertIsNone(mastering.rest_gain(SR, SR, []))

    def test_a_hit_with_silence_after_s_becomes_a_declared_rest(self):
        import cut_windows
        sheet = {'hits': [dict(t=52.9717, kind='cut', sync='hard', silence_after_s=1.0), dict(t=56.0, kind='musical', sync='soft')]}
        score = cut_windows.attach({}, sheet)
        self.assertEqual(cut_windows.rests_of(score), [(52.9717, 53.9717)])
        self.assertEqual(cut_windows.rests_of({'declared_rests': [[3, 1], 'x', [0, 99]]}), [])          # reversed, malformed and over-long are dropped
