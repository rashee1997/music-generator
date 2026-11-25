"""realism_report's eight measurements: each one has a positive and a negative control.

A measurement that cannot fail is not a measurement. These are synthetic signals with a known answer, not a
claim about any rendered piece.
"""
import os
import sys
import unittest

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import realism_report as rr  # noqa: E402

SR = 22050


def _stereo(x):
    x = np.asarray(x, dtype=np.float32)
    return np.stack([x, x], axis=1) if x.ndim == 1 else x


def _tone(f, seconds, amp):
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


class TimbreTests(unittest.TestCase):
    def test_a_loud_half_with_more_partials_passes(self):
        quiet = _tone(220, 3.0, 0.02) + _tone(660, 3.0, 0.00005) + _tone(3300, 3.0, 0.00002)
        loud = _tone(220, 3.0, 0.4) + _tone(660, 3.0, 0.12) + _tone(3300, 3.0, 0.03)
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        r = rr.timbre_loudness(f)
        self.assertGreater(r['value'], 0.8)
        self.assertEqual(r['verdict'], 'PASS')

    def test_the_same_waveform_at_two_levels_fails(self):
        quiet = _tone(220, 3.0, 0.02)
        loud = _tone(220, 3.0, 0.4)
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        r = rr.timbre_loudness(f)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertLess(abs(r['value']), 0.5)


class LowMidTests(unittest.TestCase):
    def test_a_thick_300_hz_layer_is_flagged(self):
        x = _tone(60, 4.0, 0.03) + _tone(300, 4.0, 0.3) + _tone(1200, 4.0, 0.05)
        r = rr.low_mid_bands(_stereo(x), SR)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertGreater(r['value'], 0.0)

    def test_sub_authority_with_lean_low_mids_passes(self):
        x = _tone(55, 4.0, 0.5) + _tone(300, 4.0, 0.01) + _tone(1200, 4.0, 0.1)
        r = rr.low_mid_bands(_stereo(x), SR)
        self.assertEqual(r['verdict'], 'PASS')
        self.assertLess(r['value'], 0.0)


class OpennessTests(unittest.TestCase):
    def test_a_loud_section_that_loses_its_air_is_flagged(self):
        rng = np.random.default_rng(2)
        quiet = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.02
        loud = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.3
        sos = signal.butter(6, 5000.0, btype='low', fs=SR, output='sos')
        loud = signal.sosfilt(sos, loud).astype(np.float32)
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        r = rr.openness(f)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertLess(r['value'], -1.0)

    def test_air_kept_at_the_peak_passes(self):
        rng = np.random.default_rng(3)
        quiet = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.02
        loud = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.3
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        self.assertEqual(rr.openness(f)['verdict'], 'PASS')


class DepthTests(unittest.TestCase):
    def test_dry_detail_in_front_of_a_room_passes_and_a_wash_fails(self):
        rng = np.random.default_rng(4)
        dry = _stereo(rng.standard_normal(int(4 * SR)).astype(np.float32) * 0.1)
        room = np.zeros_like(dry)
        k = int(0.06 * SR)
        room[k:] = dry[:-k] * 0.25
        good = rr.depth(_stereo(dry + room), [dry], SR)
        self.assertEqual(good['verdict'], 'PASS')
        wash = rr.depth(_stereo(dry + room * 12.0), [dry], SR)
        self.assertEqual(wash['verdict'], 'WARN')

    def test_no_stems_says_so(self):
        self.assertEqual(rr.depth(_stereo(_tone(220, 1.0, 0.2)), [], SR)['verdict'], 'N/A')


class TransientTests(unittest.TestCase):
    def test_identical_hits_share_a_shape(self):
        n = int(6.0 * SR)
        x = np.zeros(n, np.float32)
        rng = np.random.default_rng(5)
        hit = rng.standard_normal(int(0.06 * SR)).astype(np.float32) * 0.3
        for i in range(12):
            k = int((0.2 + i * 0.4) * SR)
            x[k:k + len(hit)] += hit
        r = rr.transient_similarity(_stereo(x), SR)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertGreater(r['value'], 0.99)

    def test_varied_hits_do_not(self):
        n = int(6.0 * SR)
        x = np.zeros(n, np.float32)
        rng = np.random.default_rng(6)
        for i in range(12):
            f = 300.0 + 250.0 * i
            t = np.arange(int(0.06 * SR)) / SR
            hit = (np.sin(2 * np.pi * f * t) * np.exp(-t * 60.0) * 0.3).astype(np.float32)
            k = int((0.2 + i * 0.4) * SR)
            x[k:k + len(hit)] += hit
        r = rr.transient_similarity(_stereo(x), SR)
        self.assertLess(r['value'], 0.995)
        self.assertEqual(r['verdict'], 'PASS')


class ScoreTests(unittest.TestCase):
    def _score(self, **extra):
        s = dict(bpm=96, seed=1, tracks=[dict(name='Violins', role='melody',
                                             notes=[dict(t=float(i), d=1.0, p=60 + i % 5, v=0.7) for i in range(24)])],
                 plan=dict(sections=[dict(name='A', start=0, end=12)]))
        s.update(extra)
        return s

    def test_a_section_of_one_player_is_flagged_and_declared_players_pass(self):
        self.assertEqual(rr.ensemble(self._score())['verdict'], 'WARN')
        s = self._score()
        s['tracks'][0]['ensemble'] = dict(players=6)
        self.assertEqual(rr.ensemble(s)['verdict'], 'PASS')

    def test_phrasing_reads_the_elastic_block(self):
        plain = rr.phrasing(self._score())
        self.assertTrue(plain['elastic'] is False)
        el = rr.phrasing(self._score(elastic=dict(amount=0.05, corr_beats=12.0, breaths=[12], breath_s=0.08)))
        self.assertTrue(el['elastic'] is True)
        self.assertGreater(el['value'], 0.0)

    def test_no_score_is_not_measured(self):
        self.assertEqual(rr.ensemble(None)['verdict'], 'N/A')
        self.assertEqual(rr.phrasing(None)['verdict'], 'N/A')


if __name__ == '__main__':
    unittest.main()
