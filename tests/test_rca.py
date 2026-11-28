"""rca.py: the root-cause analyser's pure parts. Each classifier has a case that must land in each class: a classifier that cannot say no is not one."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import rca  # noqa: E402


class LogParsing(unittest.TestCase):
    LOG = """
  [PASS] stem.clicks   stem "a": 0 clicks
  [FAIL] stem.dead                  stem "horns": own median -22.3 dBFS, worst section shortfall 13.1 dB (limit 12 dB)
[FAIL] dropout                    longest hole 105 ms (limit 20-1000 ms), floor -65.3 dBFS; 2 hole(s)
  [FAIL] ambient_bed                ambient stem "city_far" drops out to silence at 10.0s
[FAIL] stem.dead: stem "horns": own median -22.3 dBFS, worst section shortfall 13.1 dB (limit 12 dB)
"""

    def test_fail_lines_become_rows_with_their_stem(self):
        rows = rca.parse_log(self.LOG)
        self.assertEqual([(r, s) for r, s, _ in rows], [('stem.dead', 'horns'), ('dropout', None), ('ambient_bed', 'city_far')])

    def test_times_and_bars_are_read_from_a_detail(self):
        self.assertEqual(rca.parse_seconds('drops out to silence at 10.0s'), 10.0)
        self.assertEqual(rca.parse_seconds('roughness at 169.5s (0.101 > 0.072)'), 169.5)
        self.assertIsNone(rca.parse_seconds('no time here'))
        self.assertEqual(rca.parse_bar('bar 24 front/back balance'), 24)


class HoleClasses(unittest.TestCase):
    def test_the_four_causes_are_each_reachable(self):
        self.assertEqual(rca.classify_hole(192.4, 193.3, ['basses'], -65.0, -64.0)[0], 'tail')
        self.assertEqual(rca.classify_hole(120.0, 193.3, ['basses'], -65.0, -40.0, same_pitch_gap_ms=40.0)[0], 'retrigger gap')
        self.assertEqual(rca.classify_hole(10.0, 193.3, ['environment'], -65.0, -60.0)[0], 'bed at the floor')
        self.assertEqual(rca.classify_hole(10.0, 193.3, ['bass'], -65.0, -90.0)[0], 'rest')

    def test_a_loud_bed_is_not_a_bed_at_the_floor(self):
        self.assertEqual(rca.classify_hole(10.0, 193.3, ['environment'], -65.0, -30.0)[0], 'rest')


class FoldClasses(unittest.TestCase):
    SR = 44100

    def noise(self, seconds=6, seed=0):
        return np.random.default_rng(seed).standard_normal(self.SR * seconds)

    def test_a_smooth_tilt_is_structural_and_a_notch_is_one_band(self):
        a = self.noise()
        from scipy.signal import butter, sosfilt
        dark = sosfilt(butter(2, 3500.0, 'lp', fs=self.SR, output='sos'), a)
        cause, _ = rca.classify_fold(rca.band_table(dark, a, self.SR), 6.0)
        self.assertEqual(cause, 'structural tilt')
        notch = sosfilt(butter(4, [4300.0, 5100.0], 'bs', fs=self.SR, output='sos'), a)
        cause, _ = rca.classify_fold(rca.band_table(notch, a, self.SR), 6.0)
        self.assertEqual(cause, 'one band')

    def test_the_tilt_fit_reads_the_slope(self):
        table = [(500, 1000, 0.0), (1000, 2000, -1.0), (2000, 4000, -2.0), (4000, 8000, -3.0)]
        slope, dev = rca.tilt_fit(table)
        self.assertAlmostEqual(slope, -1.0, places=2)
        self.assertLess(dev, 0.01)


class Bars(unittest.TestCase):
    def test_front_to_back_by_bar(self):
        sr = 1000
        x = np.zeros((4 * sr, 3))
        x[:, 0] = 1.0                       # front
        x[:, 2] = 0.5                       # back
        x[2 * sr:3 * sr, 2] = 0.1           # bar 3: the back drops
        rows = rca.bar_table(x, sr, lambda b: float(b - 1), range(1, 5), [0, 1], [2])
        vals = [v for _, v, _ in rows]
        self.assertGreater(vals[2], vals[1] + 10.0)


class Tolerance(unittest.TestCase):
    def test_a_protected_row_has_no_tolerance_answer(self):
        self.assertIn('protected', rca.tolerance_note('clicks'))

    def test_a_row_with_parameters_names_its_range(self):
        self.assertIn('range', rca.tolerance_note('dropout'))

    def test_free_slots_keep_the_distance(self):
        slots = rca.free_slots([0.0, 90.0], [], step=5, min_sep=25.0)
        self.assertNotIn(10, slots)
        self.assertIn(50, slots)


class Findings(unittest.TestCase):
    def test_a_finding_carries_a_verdict_and_the_tolerance_note(self):
        f = rca.finding('dropout', None, rca.FAULT, 'tail', ['x'], ['y'])
        self.assertEqual(f['verdict'], 'fault')
        self.assertTrue(f['tolerance'])

    def test_a_row_with_no_analyzer_says_unknown_instead_of_guessing(self):
        class Ctx:
            def processed(self):
                return {}
        f = rca.analyse(Ctx(), [('some.new.row', None, 'a detail')])[0]
        self.assertEqual(f['verdict'], 'unknown')


if __name__ == '__main__':
    unittest.main()
