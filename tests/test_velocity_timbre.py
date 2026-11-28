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


class SfzLikeZones(unittest.TestCase):
    """Fixed velocity zones, a velocity-to-attack ramp and the 0-1 velocity scale: the SFZ lovel/hivel, ampeg_vel2attack idea on a SoundFont."""

    def _render(self, vels, **vt):
        calls, ramps = [], []
        rng = np.random.default_rng(0)

        def fake(tr, *a, **k):
            calls.append([n['v'] for n in tr['notes']])
            ramps.append(tr.get('onset_fade_ms'))
            return rng.standard_normal((44100, 2)).astype(np.float32) * 0.1

        with mock.patch.object(rn, '_render_track', fake):
            rn._render_velocity_layers(track(vels), dict(points=PTS, **vt), None, None, None, None, 0, (4, 4), 0.0, None)
        return calls, ramps

    def test_a_note_lands_in_a_zone_by_its_own_velocity(self):
        calls_a, _ = self._render([20, 50, 80, 120], zones=4)
        calls_b, _ = self._render([20, 50, 80, 120, 21, 22, 23], zones=4)
        zone_of = lambda calls, v: next(i for i, c in enumerate(sorted(calls, key=min)) if v in c)         # noqa: E731
        self.assertEqual(len(calls_a), 4)
        self.assertEqual(zone_of(calls_a, 80), 2)
        self.assertTrue(any(80 in c and 120 not in c and 20 not in c for c in calls_b))     # extra soft notes never move the loud ones into other zones

    def test_zones_must_be_in_range(self):
        for bad in (1, 17):
            with self.assertRaises(ValueError):
                rn._velocity_timbre(track([60], velocity_timbre=dict(points=PTS, zones=bad)))

    def test_a_soft_zone_begins_more_slowly(self):
        _, ramps = self._render([20, 20, 120, 120], zones=4, attack_ms=[[20, 40], [120, 4]])
        soft, hard = ramps[0], ramps[-1]
        self.assertGreater(soft, hard)
        self.assertTrue(4 <= hard <= soft <= 40)

    def test_attack_ramp_validation(self):
        for bad in ([[20, 40]], [[120, 4], [20, 40]], [[20, 400], [120, 4]]):
            with self.assertRaises(ValueError):
                rn._velocity_timbre(track([60], velocity_timbre=dict(points=PTS, attack_ms=bad)))

    def test_a_zero_to_one_velocity_scale_reads_as_the_loud_end(self):
        rn.REPORT.clear()
        self._render([0.2, 0.25, 0.95, 1.0], zones=4)
        info = rn.REPORT['t']['velocity_layers']
        self.assertGreater(info[-1]['lowpass_hz'], 5000)          # velocity 0.95-1.0 is 120-127, not 1
        self.assertLess(info[0]['lowpass_hz'], info[-1]['lowpass_hz'])


if __name__ == '__main__':
    unittest.main()
