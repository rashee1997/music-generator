"""render_natural velocity_timbre: a SoundFont's missing velocity layers, emulated per note from preset numbers."""
import os
import sys
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import render_natural as rn  # noqa: E402

PTS = [[20, 1500], [127, 9000]]


def track(vels, **extra):
    return dict(name='t', instrument='nobody_has_this_preset', role='melody',
                notes=[dict(t=float(i), d=0.5, p=60, v=v) for i, v in enumerate(vels)], **extra)


class Validation(unittest.TestCase):
    def test_off_without_the_block(self):
        self.assertIsNone(rn._velocity_timbre(track([60, 90])))

    def test_unknown_key_is_an_error(self):
        with self.assertRaises(ValueError):
            rn._velocity_timbre(track([60], velocity_timbre=dict(points=PTS, colour='red')))

    def test_points_must_be_ordered_pairs(self):
        for bad in ([[20, 1500]], [[90, 5000], [20, 1500]], [[20, 0], [90, 5000]], [[20], [90, 5000]], 'x'):
            with self.assertRaises(ValueError):
                rn._velocity_timbre(track([60], velocity_timbre=dict(points=bad)))

    def test_not_for_sfz_or_clone_tracks(self):
        for inst in ('sfz:piano', 'clone:x', 'sfx:y', 'env:z'):
            tr = track([60], velocity_timbre=dict(points=PTS))
            tr['instrument'] = inst
            with self.assertRaises(ValueError):
                rn._velocity_timbre(tr)

    def test_bands_must_be_two_or_more(self):
        with self.assertRaises(ValueError):
            rn._velocity_timbre(track([60], velocity_timbre=dict(points=PTS, bands=1)))


class Layers(unittest.TestCase):
    def _render(self, vels, **vt):
        calls = []
        rng = np.random.default_rng(0)

        def fake(tr, *a, **k):
            calls.append([n['v'] for n in tr['notes']])
            return rng.standard_normal((44100, 2)).astype(np.float32) * 0.1

        blk = dict(points=PTS, **vt)
        with mock.patch.object(rn, '_render_track', fake):
            out = rn._render_velocity_layers(track(vels), blk, None, None, None, None, 0, (4, 4), 0.0, None)
        return calls, out

    def test_notes_split_into_bands_by_velocity(self):
        calls, out = self._render([20, 30, 40, 100, 110, 120], bands=2)
        self.assertEqual(len(calls), 2)
        self.assertTrue(max(calls[0]) < min(calls[1]))                       # every soft note in the first band
        self.assertEqual(sorted(sum(calls, [])), [20, 30, 40, 100, 110, 120])  # no note lost or doubled
        self.assertEqual(out.shape, (44100, 2))

    def test_a_soft_band_is_darker_than_a_hard_one(self):
        rn.REPORT.clear()
        self._render([20, 25, 30, 110, 115, 120], bands=2)
        info = rn.REPORT['t']['velocity_layers']
        self.assertLess(info[0]['lowpass_hz'], info[1]['lowpass_hz'])
        self.assertTrue(1500 <= info[0]['lowpass_hz'] <= 9000 and 1500 <= info[1]['lowpass_hz'] <= 9000)

    def test_one_velocity_is_one_band(self):
        calls, _ = self._render([64, 64, 64], bands=4)
        self.assertEqual(len(calls), 1)

    def test_cutoff_follows_the_points(self):
        rn.REPORT.clear()
        self._render([20, 20, 127, 127], bands=2)
        info = rn.REPORT['t']['velocity_layers']
        self.assertEqual([i['lowpass_hz'] for i in info], [1500, 9000])      # the end points are returned exactly


if __name__ == '__main__':
    unittest.main()
