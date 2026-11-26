# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""`pattern_audit._spiral_series` was an all-pairs Python loop (~2.8 s on a 4-minute orchestral score) and is array maths now.
The reference below is the loop it replaced, kept here only to prove the numbers did not move.

Run: python -m unittest tests.test_spiral_series
"""
import os
import sys
import time
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import pattern_audit as pa  # noqa: E402
import soul_check  # noqa: E402


def reference(score):
    """The implementation before the change, verbatim."""
    num = pa._beats_per_bar(score)
    w_len = 2 * num
    all_notes = [n for t in score.get('tracks', []) if pa._role(t) not in ('drum', 'environment')
                 for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
    if not all_notes:
        return None
    N = max(1, int(np.ceil(max(n['t'] + n.get('d', 1.0) for n in all_notes) / w_len)))
    tonic_pc = soul_check._tonic_pc(score)
    CE_key = pa._helix_point(float(tonic_pc), tonic_pc)
    CEs, T_cds = [], []
    for w in range(N):
        t0 = w * w_len
        t1 = t0 + w_len
        active = [n for n in all_notes if max(t0, n['t']) < min(t1, n['t'] + n.get('d', 1.0))]
        if active:
            vecs = [pa._helix_point(pa._pitch_cont(n), tonic_pc) for n in active]
            weights = [float(n.get('d', 1.0)) * pa._vel(n) for n in active]
            ce = sum(v * w for v, w in zip(vecs, weights)) / (sum(weights) + 1e-9)
            cd = max(np.linalg.norm(a - b) for a in vecs for b in vecs)
        else:
            ce = CEs[-1] if CEs else CE_key
            cd = 0.0
        CEs.append(ce)
        T_cds.append(cd)
    return CEs, T_cds, CE_key, N, w_len


def random_score(seed, n_notes=300, bars=40, key='D minor'):
    rng = np.random.default_rng(seed)
    notes = [dict(t=float(rng.uniform(0, bars * 4 - 2)), d=float(rng.choice([0.25, 0.5, 1.0, 2.0, 6.0])),
                  p=int(rng.integers(36, 90)), v=float(rng.uniform(0.2, 1.0)),
                  **({'c': float(rng.choice([-50, 0, 25]))} if rng.random() < 0.2 else {})) for _ in range(n_notes)]
    return dict(ts=[4, 4], bpm=100, key=key, tracks=[
        dict(name='a', role='melody', instrument='violin', notes=notes),
        dict(name='d', role='drum', instrument='drums', notes=[dict(t=float(i), d=0.5, p='kick', v=0.8) for i in range(bars * 4)]),
        dict(name='e', role='environment', instrument='env:x', notes=[dict(t=0.0, d=bars * 4.0, p=60, v=0.5)]),
    ])


class Equivalence(unittest.TestCase):
    def check(self, score):
        want, got = reference(score), pa._spiral_series(score)
        if want is None:
            self.assertIsNone(got)
            return
        self.assertEqual((got[3], got[4]), (want[3], want[4]))
        np.testing.assert_allclose(got[2], want[2], atol=1e-12)
        self.assertEqual(len(got[0]), len(want[0]))
        np.testing.assert_allclose(np.array(got[0]), np.array(want[0]), rtol=0, atol=1e-9)
        np.testing.assert_allclose(np.array(got[1], dtype=float), np.array(want[1], dtype=float), rtol=0, atol=1e-9)

    def test_random_scores_match_the_loop_they_replaced(self):
        for seed in range(12):
            self.check(random_score(seed, n_notes=40 + 30 * seed, key=('C major', 'D minor', 'F# minor')[seed % 3]))

    def test_silent_windows_repeat_the_last_centre_and_have_zero_diameter(self):
        sc = dict(ts=[4, 4], key='C major', tracks=[dict(name='a', role='melody', instrument='flute', notes=[
            dict(t=0.0, d=1.0, p=60, v=0.7), dict(t=40.0, d=1.0, p=67, v=0.7)])])
        got = pa._spiral_series(sc)
        self.check(sc)
        self.assertEqual(got[1][2], 0.0)
        np.testing.assert_array_equal(got[0][2], got[0][1])

    def test_one_note_has_no_diameter_and_a_unison_cloud_is_a_point(self):
        sc = dict(ts=[4, 4], key='C major', tracks=[dict(name='a', role='melody', instrument='flute', notes=[
            dict(t=0.0, d=4.0, p=60, v=0.7), dict(t=1.0, d=2.0, p=60, v=0.5)])])
        self.check(sc)
        self.assertEqual(pa._spiral_series(sc)[1][0], 0.0)

    def test_no_pitched_notes_is_none(self):
        sc = dict(ts=[4, 4], tracks=[dict(name='d', role='drum', instrument='drums', notes=[dict(t=0, d=1, p='kick', v=0.8)])])
        self.assertIsNone(pa._spiral_series(sc))
        self.assertIsNone(reference(sc))

    def test_the_row_built_on_it_is_unchanged(self):
        for seed in (0, 3, 7):
            sc = random_score(seed, n_notes=200)
            self.assertEqual(pa.spiral_tension_arc(sc), pa.spiral_tension_arc(sc))

    def test_vector_helix_points_are_the_scalar_ones(self):
        pcs = [60.0, 61.25, 66.5, 71.0, 48.0, 90.75]
        want = np.array([pa._helix_point(p, 2) for p in pcs])
        np.testing.assert_allclose(pa._helix_points(pcs, 2), want, atol=1e-12)


class Speed(unittest.TestCase):
    def test_a_long_dense_score_takes_well_under_a_second(self):
        sc = random_score(1, n_notes=12000, bars=120)
        t0 = time.perf_counter()
        pa._spiral_series(sc)
        took = time.perf_counter() - t0
        self.assertLess(took, 1.5, f'{took:.2f} s')

    def test_it_agrees_with_the_loop_on_a_long_score_too(self):
        sc = random_score(2, n_notes=1500, bars=100)
        want, got = reference(sc), pa._spiral_series(sc)
        np.testing.assert_allclose(np.array(got[1], dtype=float), np.array(want[1], dtype=float), atol=1e-9)
        np.testing.assert_allclose(np.array(got[0]), np.array(want[0]), atol=1e-9)


if __name__ == '__main__':
    unittest.main()
