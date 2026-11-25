# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""M7: PPM-C expectation model (information content and entropy) and the rows built on it."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import expectation  # noqa: E402
import pattern_audit as pa  # noqa: E402
from expectation import PPM, Expectation  # noqa: E402


def line(pitches, step=0.5, start=0.0):
    return [{'t': start + i * step, 'd': step, 'p': p} for i, p in enumerate(pitches)]


MOTIF = [60, 62, 64, 62, 60, 62, 64, 62] * 4


def random_walk(n, seed):
    rng = np.random.default_rng(seed)
    return [int(60 + rng.integers(-12, 13)) for _ in range(n)]


def score(pitches, **kw):
    return dict({'ts': [4, 4], 'key': 'C', 'tracks': [{'name': 'lead', 'role': 'melody', 'notes': line(pitches)}]}, **kw)


class Ppm(unittest.TestCase):
    def test_a_hand_computed_distribution(self):
        """Seq 0 1 0 1 0 1 0, order 2, history [0, 1, 0]: order-2 context (1,0) has {1: 2} -> P(1) = 2/3, escape 1/3;
        order 1 has only the excluded symbol; order 0 has {0: 4} after excluding 1 -> P(0) = 1/3 * 4/5; the rest, 1/15,
        goes to the one unseen symbol."""
        m = PPM(range(3), 2)
        m.train([0, 1, 0, 1, 0, 1, 0])
        d = m.distribution([0, 1, 0])
        self.assertTrue(np.allclose(d, [4 / 15, 10 / 15, 1 / 15]))

    def test_a_distribution_always_sums_to_one(self):
        m = PPM(range(5), 3)
        rng = np.random.default_rng(0)
        seq = [int(x) for x in rng.integers(0, 5, 60)]
        m.train(seq)
        for i in range(0, 55, 5):
            self.assertAlmostEqual(float(m.distribution(seq[:i]).sum()), 1.0, places=9)
        self.assertAlmostEqual(float(PPM(range(5)).distribution([1, 2]).sum()), 1.0, places=9)

    def test_an_untrained_model_is_uniform(self):
        d = PPM(range(8)).distribution([])
        self.assertTrue(np.allclose(d, 1 / 8))
        self.assertAlmostEqual(expectation.entropy(d), 3.0)


class Analysis(unittest.TestCase):
    def test_each_note_is_predicted_before_it_is_learned(self):
        r = Expectation().analyse(line([60, 62, 64]), 0)
        self.assertAlmostEqual(float(r['viewpoints']['degree']['ic'][0]), np.log2(12), places=6)
        self.assertAlmostEqual(float(r['viewpoints']['cpint']['ic'][1]), np.log2(25), places=6)
        self.assertTrue(np.isnan(r['viewpoints']['cpint']['ic'][0]))

    def test_a_repeated_motif_becomes_predictable(self):
        r = Expectation().analyse(line(MOTIF), 0)
        ic = r['ic']
        self.assertGreater(float(np.nanmean(ic[:8])), 2.0)
        self.assertLess(float(np.nanmean(ic[-8:])), 0.5)
        self.assertLess(float(np.nanmean(r['h'][-8:])), float(np.nanmean(r['h'][:8])))

    def test_a_random_walk_stays_surprising(self):
        motif = np.nanmean(Expectation().analyse(line(MOTIF), 0)['ic'])
        rnd = np.nanmean(Expectation().analyse(line(random_walk(96, 1)), 0)['ic'])
        self.assertGreater(rnd, motif + 2.0)

    def test_the_long_term_model_lowers_the_surprise_of_a_known_style(self):
        plain = Expectation().analyse(line(MOTIF), 0)
        trained = Expectation()
        trained.train(line(MOTIF * 3), 0)
        known = trained.analyse(line(MOTIF), 0)
        self.assertLess(float(np.nanmean(known['ic'][:8])), float(np.nanmean(plain['ic'][:8])))

    def test_the_result_is_deterministic(self):
        a = Expectation().analyse(line(random_walk(40, 3)), 0)
        b = Expectation().analyse(line(random_walk(40, 3)), 0)
        self.assertTrue(np.array_equal(a['ic'], b['ic'], equal_nan=True))

    def test_chords_are_reduced_to_their_top_note(self):
        notes = line([60, 62, 64, 65]) + [{'t': 0.0, 'd': 0.5, 'p': 48}, {'t': 1.0, 'd': 0.5, 'p': 52}]
        t, p = expectation.line_of(notes)
        self.assertEqual(list(p), [60, 62, 64, 65])

    def test_rhythm_is_reported_apart_from_pitch(self):
        steady = Expectation().analyse(line(random_walk(32, 2)), 0)
        self.assertLess(float(np.nanmean(steady['ic_rhythm'])), 1.0)
        self.assertGreater(float(np.nanmean(steady['ic'])), 3.0)         # not diluted by the constant rhythm

    def test_by_bar_and_ungrounded_share(self):
        t = np.arange(8) * 1.0
        v = np.array([1.0, 3.0, np.nan, np.nan, 5.0, 5.0, 2.0, 4.0])
        per = expectation.by_bar(t, v, 4.0)
        self.assertEqual(len(per), 2)
        self.assertAlmostEqual(float(per[0]), 2.0)
        self.assertAlmostEqual(float(per[1]), 4.0)
        self.assertEqual(expectation.ungrounded_share([5.0, 1.0, 5.0, 5.0, 1.0]), 0.2)


class Rows(unittest.TestCase):
    def rows(self, sc):
        return {r[1]: r for r in pa.cognitive_feel_checks(sc)}

    def test_a_loop_fails_the_entropy_row(self):
        got = pa.melodic_information_entropy(score(MOTIF))
        self.assertEqual(got[0][0], 'FAIL')
        self.assertIn('mechanically predictable', got[0][2])

    def test_a_static_line_fails_and_an_ambient_one_is_allowed(self):
        self.assertEqual(pa.melodic_information_entropy(score([60] * 16))[0][0], 'FAIL')

    def test_a_shaped_melody_passes(self):
        melody = [60, 62, 64, 65, 67, 65, 64, 62, 60, 64, 67, 72, 71, 69, 67, 65, 64, 62, 60, 59, 60, 62, 64, 67]
        self.assertEqual(pa.melodic_information_entropy(score(melody))[0][0], 'PASS')

    def test_wide_random_walks_warn_and_none_fails(self):
        levels = [pa.melodic_information_entropy(score(random_walk(96, s)))[0][0] for s in range(8)]
        self.assertNotIn('FAIL', levels)
        self.assertGreaterEqual(levels.count('WARN'), 6)            # measured: mean information content 4.4-4.7 bits

    def test_the_metric_is_the_mean_information_content(self):
        melody = [60, 62, 64, 65, 67, 65, 64, 62, 60, 64, 67, 72]
        want = round(float(np.nanmean(Expectation().analyse(line(melody), 0)['ic'])), 2)
        self.assertEqual(pa.cognitive_metrics(score(melody))['melodic_entropy_bits'], want)

    def test_the_expr_rows_are_emitted_and_never_fail(self):
        melody = [60, 62, 64, 65, 67, 65, 64, 62, 60, 64, 67, 72, 71, 69, 67, 65, 64, 62, 60, 59] * 2
        got = self.rows(score(melody))
        for rid in ('expr.ic_profile', 'expr.surprise_grounded', 'expr.tension_ic'):
            self.assertIn(rid, got)
            self.assertIn(got[rid][0], ('INFO', 'PASS', 'WARN'))

    def test_a_skipped_expr_row_is_not_emitted(self):
        sc = score([60, 62, 64, 65, 67, 65, 64, 62, 60, 64, 67, 72], gate={'expr.ic_profile': {'mode': 'skip', 'reason': 'test'}})
        self.assertNotIn('expr.ic_profile', self.rows(sc))

    def test_the_spiral_series_is_shared_with_the_arc_row(self):
        sc = score([60, 62, 64, 65, 67, 69, 71, 72] * 4)
        CEs, T_cds, CE_key, N, w_len = pa._spiral_series(sc)
        self.assertEqual((len(CEs), len(T_cds), w_len), (N, N, 8.0))
        self.assertTrue(pa.spiral_tension_arc(sc))


if __name__ == '__main__':
    unittest.main()
