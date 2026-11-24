# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Regression controls for the measurement-engine defects found on a real cue.

* the per-bar correlation must be the same number the direct correlation gives, at FFT speed;
* a left/right (or front/back) ratio must not depend on how many speakers a side has;
* a placement row must read the preset the mixer actually plays, including `sfx:` presets;
* the masking rows must follow the focus the score declares, not the profile's widest list.
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import channel_qa                                            # noqa: E402
import presets                                               # noqa: E402
import quality_gate as qg                                    # noqa: E402


def direct_corr(a, b, max_lag=64):
    """The direct reduced-lag correlation this row used before the FFT path, for comparison."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    n = min(len(a), len(b))
    a = a[:n] - np.mean(a[:n])
    b = b[:n] - np.mean(b[:n])
    den = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    if den <= 1e-20:
        return 0.0
    c = np.correlate(a, b, mode='full')
    mid = n - 1
    lag = max(1, min(int(max_lag), n - 1))
    lo, hi = mid - lag, mid + lag + 1
    mag = np.abs(c[lo:hi])
    near = np.flatnonzero(mag >= 0.95 * mag.max())
    i = lo + int(near[np.argmin(np.abs(lo + near - mid))])
    return float(c[i] / den)


class CorrelationMaths(unittest.TestCase):
    def test_fft_matches_the_direct_correlation(self):
        rng = np.random.default_rng(7)
        pairs = [
            (rng.standard_normal(4096), rng.standard_normal(4096)),
            (np.sin(np.arange(4096) * 0.1), np.sin(np.arange(4096) * 0.1 + 0.3)),
        ]
        for a, b in pairs:
            self.assertAlmostEqual(channel_qa._corr(a, b, 32), direct_corr(a, b, 32), places=10)

    def test_an_inverted_bar_still_reads_negative(self):
        t = np.arange(8192)
        tone = np.sin(2 * np.pi * 220.0 * t / 8000.0)
        self.assertLess(channel_qa._corr(-tone, tone, 64), -0.99)

    def test_a_full_bar_correlates_fast(self):
        rng = np.random.default_rng(11)
        a, b = rng.standard_normal(150000), rng.standard_normal(150000)
        start = time.perf_counter()
        channel_qa._corr(a, b, 64)
        channel_qa._corr(a, b, 64)
        self.assertLess(time.perf_counter() - start, 2.0)

    def test_group_energy_does_not_depend_on_channel_count(self):
        x = np.full((1000, 5), 0.5)
        three = channel_qa._energy(x, 0, 1000, [0, 1, 2])
        four = channel_qa._energy(x, 0, 1000, [0, 1, 2, 3])
        self.assertAlmostEqual(three, four, places=12)


class BalanceRecord(unittest.TestCase):
    def test_a_group_swing_is_not_labelled_with_the_last_speaker(self):
        rng = np.random.default_rng(5)
        edges = np.array([0, 1000, 2000, 3000, 4000])
        x = rng.standard_normal((4000, 4)) * 0.01
        x[1000:2000, [0, 2]] *= 4.0                 # left speakers lift for one bar only
        positions = [(-30.0, 0.0), (30.0, 0.0), (-90.0, 0.0), (90.0, 0.0)]
        levels = channel_qa._level_matrix(x, edges)
        found = channel_qa._conflicts(x, levels, edges, positions, ['a', 'b', 'c', 'd'],
                                      channel_qa.PARAMS)
        swings = [c for c in found if c['kind'] == 'balance']
        self.assertTrue(swings)
        for c in swings:
            self.assertIsNone(c['channel'])
            self.assertEqual(c['channel_name'], 'group')


class FocusAndPlacement(unittest.TestCase):
    def test_declared_focus_wins_over_the_profile_list(self):
        score = dict(piece_type='cinematic', focus='melody', tracks=[
            dict(name='piano', role='melody', notes=[]),
            dict(name='pedal', role='drone', notes=[]),
        ])
        stems = dict(piano=np.full(2000, 0.10), pedal=np.full(2000, 0.90))
        lead, bed, beds = qg.figure_and_bed(score, stems)
        self.assertEqual(lead, 'piano')
        self.assertIn('pedal', beds)
        self.assertIsNotNone(bed)

    def test_an_sfx_preset_places_the_effect_where_the_mixer_plays_it(self):
        tmp = tempfile.mkdtemp(prefix='sfx_place_')
        sfx = Path(tmp) / 'presets' / 'sfx'
        sfx.mkdir(parents=True)
        (sfx / 'test_sweep.json').write_text(json.dumps({
            'spatial': dict(azimuth=-120.0, elevation=28.0, distance=9.0, kind='spot', binaural=True),
        }), encoding='utf-8')
        presets.reset_projects()
        presets.add_project(tmp)
        try:
            score = dict(tracks=[dict(name='fx', role='fx', instrument='sfx:test_sweep')])
            az, el, sp, role, rendered = qg._place_of(score, score['tracks'][0], None)
            self.assertAlmostEqual(az, -120.0)
            self.assertAlmostEqual(el, 28.0)
            self.assertEqual(role, 'fx')
            self.assertTrue(rendered)
        finally:
            presets.reset_projects()
            for p in sorted(sfx.glob('*')):
                p.unlink()
            sfx.rmdir()
            (Path(tmp) / 'presets').rmdir()
            Path(tmp).rmdir()


if __name__ == '__main__':
    unittest.main()
