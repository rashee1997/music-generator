# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""M9: the valence/arousal coordinates, the section measurements, and the two advisory arc rows."""
import os
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import affect  # noqa: E402
import gate_profiles  # noqa: E402
import intent  # noqa: E402
import lint_coverage  # noqa: E402
import presets  # noqa: E402

SR = 22050
MAJOR, MINOR = (0, 4, 7), (0, 3, 7)


def chord_section(seconds, notes_per_s, level_db, triad, octave=0, seed=0):
    """Repeated chord hits (additive tones with a decay), the hit rate and level being the arousal knobs."""
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    out = np.zeros(n)
    step = int(SR / notes_per_s)
    for start in range(0, n - step, step):
        tt = np.arange(step) / SR
        env = np.exp(-4.0 * tt) * np.minimum(1.0, tt * 200.0)
        for semi in triad:
            f = 261.63 * 2 ** ((semi + 12 * octave) / 12.0) * (1 + rng.normal(0, 0.0005))
            out[start:start + step] += env * sum(np.sin(2 * np.pi * f * h * tt) / h ** 1.2 for h in range(1, 7))
    out /= max(float(np.abs(out).max()), 1e-9)
    return out * 10 ** (level_db / 20.0)


def piece(triad, ladder=((1.0, -34.0, 0), (3.0, -24.0, 0), (6.0, -14.0, 1))):
    return np.concatenate([chord_section(6.0, r, db, triad, o, seed=i) for i, (r, db, o) in enumerate(ladder)])


def sheet(energies=(0.2, 0.5, 0.9), emotions=('joyful',)):
    return {'sections': [{'name': n, 'start_s': 6.0 * i, 'end_s': 6.0 * (i + 1), 'energy': e}
                         for i, (n, e) in enumerate(zip('abc', energies))],
            'intent': {'emotions': list(emotions), 'registers': [], 'scenes': [], 'tensions': [], 'avoid': []}}


class Coordinates(unittest.TestCase):
    def test_every_emotion_has_coordinates_in_range(self):
        va = presets.load('intent')['valence_arousal']['emotions']
        self.assertEqual(set(va), set(intent.vocabulary()['emotions']))
        for cid, c in va.items():
            for axis in ('valence', 'arousal'):
                self.assertTrue(-1.0 <= c[axis] <= 1.0, (cid, axis))
        self.assertEqual(intent.problems(), [])

    def test_the_quadrants_are_the_expected_ones(self):
        va = presets.load('intent')['valence_arousal']['emotions']
        self.assertGreater(va['joyful']['valence'], 0.5)
        self.assertGreater(va['joyful']['arousal'], 0.3)
        self.assertLess(va['grief']['valence'], -0.5)
        self.assertLess(va['grief']['arousal'], 0.0)
        self.assertLess(va['calm']['arousal'], -0.5)
        self.assertLess(va['scary']['valence'], -0.5)

    def test_a_missing_coordinate_is_a_problem(self):
        from unittest import mock
        real = presets.load

        def without_calm(kind):
            out = real(kind)
            if kind == 'intent':
                out['valence_arousal']['emotions'].pop('calm')
            return out
        with mock.patch.object(intent.presets, 'load', side_effect=without_calm):
            self.assertTrue(any('valence_arousal.calm' in p for p in intent.problems()))


class Measures(unittest.TestCase):
    def test_mode_score_reads_major_and_minor_profiles(self):
        c = np.zeros(12)
        c[[0, 4, 7]] = [1.0, 0.7, 0.8]
        c[[2, 5, 9, 11]] = 0.1
        self.assertGreater(affect.mode_score(c), 0.2)
        m = np.zeros(12)
        m[[0, 3, 7]] = [1.0, 0.7, 0.8]
        m[[2, 5, 8, 10]] = 0.1
        self.assertLess(affect.mode_score(m), -0.2)
        self.assertEqual(affect.mode_score(np.zeros(12)), 0.0)

    def test_clash_counts_adjacent_pitch_classes(self):
        a, b = np.zeros(12), np.zeros(12)
        a[[0, 7]] = 1.0
        b[[0, 1]] = 1.0
        self.assertGreater(affect.clash(b), affect.clash(a))

    def test_arousal_follows_density_and_level(self):
        a = affect.arc(piece(MAJOR), SR, [('a', 0.0, 6.0), ('b', 6.0, 12.0), ('c', 12.0, 18.0)])
        self.assertEqual(a['names'], ['a', 'b', 'c'])
        self.assertLess(a['arousal'][0], a['arousal'][1])
        self.assertLess(a['arousal'][1], a['arousal'][2])

    def test_valence_has_the_sign_of_the_mode(self):
        spans = [('a', 0.0, 6.0), ('b', 6.0, 12.0), ('c', 12.0, 18.0)]
        major = affect.arc(piece(MAJOR), SR, spans)['valence'].mean()
        minor = affect.arc(piece(MINOR), SR, spans)['valence'].mean()
        self.assertGreater(major, minor + 0.1)

    def test_short_sections_are_skipped(self):
        a = affect.arc(piece(MAJOR), SR, [('tiny', 0.0, 1.0), ('ok', 6.0, 12.0)])
        self.assertEqual(a['names'], ['ok'])


class Rows(unittest.TestCase):
    def levels(self, x, sh):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'm.wav')
            sf.write(path, np.stack([x, x], 1).astype(np.float32), SR, subtype='FLOAT')
            return {r[1]: r for r in affect.rows({}, sh, path)}

    def test_a_piece_that_follows_its_sheet_passes_both_rows(self):
        got = self.levels(piece(MAJOR), sheet())
        self.assertEqual(got['emotion.arc_arousal'][0], 'INFO')
        self.assertEqual(got['emotion.arc_valence'][0], 'INFO')

    def test_a_reversed_energy_order_warns(self):
        got = self.levels(piece(MAJOR), sheet(energies=(0.9, 0.5, 0.2)))
        self.assertEqual(got['emotion.arc_arousal'][0], 'WARN')
        self.assertIn('change its density', got['emotion.arc_arousal'][2])

    def test_a_minor_piece_for_a_joyful_brief_warns_on_valence_only(self):
        got = self.levels(piece(MINOR), sheet())
        self.assertEqual(got['emotion.arc_valence'][0], 'WARN')
        self.assertEqual(got['emotion.arc_arousal'][0], 'INFO')

    def test_a_neutral_brief_never_warns_on_valence(self):
        got = self.levels(piece(MINOR), sheet(emotions=('focused',)))
        self.assertEqual(got['emotion.arc_valence'][0], 'INFO')

    def test_a_sheet_without_sections_or_a_missing_file_is_not_measured(self):
        got = self.levels(piece(MAJOR), {'sections': []})
        self.assertTrue(all(r[0] == 'INFO' and 'not measured' in r[2] for r in got.values()))
        self.assertTrue(all(r[0] == 'INFO' for r in affect.rows({}, sheet(), '/nonexistent.wav')))

    def test_no_row_can_fail_and_both_are_registered(self):
        for rid in ('emotion.arc_arousal', 'emotion.arc_valence'):
            self.assertIn(rid, gate_profiles.ROWS)
            self.assertTrue(gate_profiles.ROWS[rid].get('hint'))
            self.assertIn(rid, lint_coverage.COVERAGE)
        got = self.levels(piece(MINOR), sheet(energies=(0.9, 0.5, 0.2)))
        self.assertTrue(all(r[0] in ('INFO', 'WARN') for r in got.values()))


if __name__ == '__main__':
    unittest.main()
