# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""expression_report and the gate rows built on it, each with a passing and a failing control.

Run: python -m unittest tests.test_expression
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'helpers'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import expression_report as er  # noqa: E402
import quality_gate as qg  # noqa: E402


def _notes(pitches, start=0.0, step=1.0, d=1.0, v=0.7):
    return [dict(t=start + i * step, d=d, p=p, v=v) for i, p in enumerate(pitches)]


def _score(sections, tracks, **kw):
    s = dict(bpm=100, ts=[4, 4], tempo_points=[], plan=dict(sections=sections), tracks=tracks)
    s.update(kw)
    return s


def _building():
    """Three sections whose notes get denser, louder, higher and faster: a real build."""
    secs = [dict(name='a', start_bar=1, end_bar=2, energy=0.2), dict(name='b', start_bar=3, end_bar=4, energy=0.5),
            dict(name='c', start_bar=5, end_bar=6, energy=0.9)]
    ns = _notes([40, 43], 0.0, 2.0, 2.0, 0.3) + _notes([45, 47, 48, 50, 52, 55], 8.0, 1.0, 0.8, 0.6) \
        + _notes(list(range(60, 76)), 16.0, 0.5, 0.25, 0.95)
    return _score(secs, [dict(name='x', role='chord', notes=ns)], tempo_points=[[0, 70], [8, 100], [16, 150]])


def _flat_then_loud():
    """The loudest, densest section is declared the quietest: the written music contradicts the sheet."""
    s = _building()
    for sec, e in zip(s['plan']['sections'], (0.9, 0.5, 0.2)):
        sec['energy'] = e
    return s


class ArousalOrder(unittest.TestCase):
    def test_a_written_build_follows_a_declared_build(self):
        rho, rows, flag = er.arousal_order(_building())
        self.assertGreater(rho, 0.9, rows)
        self.assertEqual(flag, '')

    def test_a_declared_build_that_the_notes_do_not_make_is_flagged(self):
        rho, rows, flag = er.arousal_order(_flat_then_loud())
        self.assertLess(rho, 0.0)
        self.assertIn('rank correlation', flag)

    def test_two_sections_say_nothing(self):
        s = _building()
        s['plan']['sections'] = s['plan']['sections'][:2]
        self.assertEqual(er.arousal_order(s)[0], None)

    def test_spearman_of_a_reversed_series_is_minus_one(self):
        self.assertAlmostEqual(er.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(er.spearman([1, 1, 1], [1, 2, 3]))


class MelodyVariety(unittest.TestCase):
    def _fig(self, pitches, step=1.0):
        return _score([], [dict(name='m', role='melody', notes=_notes(pitches, 0.0, step))])

    def test_a_shaped_line_passes(self):
        line = [62, 64, 65, 69, 67, 65, 64, 62, 60, 62, 65, 67, 72, 71, 69, 67, 65, 64, 62, 57, 60, 62, 64, 65]
        mv = er.melody_variety(self._fig(line))
        self.assertEqual(mv['flags'], [], mv)
        self.assertGreater(mv['interval_entropy_bits'], 1.5)

    def test_one_repeated_cell_is_flagged(self):
        mv = er.melody_variety(self._fig([62, 65, 67, 65] * 8))
        self.assertTrue(any('repeat an earlier bar' in f for f in mv['flags']), mv)

    def test_a_narrow_line_is_flagged_as_having_no_peak(self):
        mv = er.melody_variety(self._fig([62, 63, 62, 64, 62, 63, 64, 63, 62, 64, 63, 62, 63, 64, 62, 63, 64, 62]))
        self.assertTrue(any('no climb' in f for f in mv['flags']), mv)

    def test_a_short_figure_is_not_judged(self):
        mv = er.melody_variety(self._fig([62, 64, 65]))
        self.assertIn('too short', mv['note'])

    def test_no_figure_track_means_no_measure(self):
        self.assertEqual(er.figure_notes(_building()), [])


class SheetBlock(unittest.TestCase):
    def _block(self):
        return dict(sonic_picture='A narrow stair in the dark, the pulse enters first and never leaves.',
                    performer='Celli bow close to the bridge, breathing in the phrase gaps and leaning on beat one.',
                    producer_moves='Filter opens over the last eight bars; a full stop before the final hit.',
                    anti_generic='The generic version is a pad and a drum loop; this one keeps one pulse that changes.',
                    cues=[dict(section='a', arousal='low', articulation='tenuto', timbre='dark')],
                    theme=dict(contour='arch', interval_character='fourths then a step', rhythm_cell='long short short',
                               why_memorable='the leap lands on the weak beat', variation_plan='inverted on return'))

    def test_a_complete_block_has_no_problem(self):
        self.assertEqual(er.expression_block_problems(dict(expression=self._block())), [])

    def test_a_missing_block_is_named(self):
        self.assertIn('no `expression` block', er.expression_block_problems({})[0])

    def test_a_half_written_block_names_what_is_missing(self):
        b = self._block()
        b['performer'] = 'x'
        b['cues'] = [dict(section='a', arousal='low')]
        text = ' '.join(er.expression_block_problems(dict(expression=b)))
        self.assertIn('expression.performer', text)
        self.assertIn('articulation', text)


class GateRows(unittest.TestCase):
    def _rows(self, score, sheet):
        out = []
        qg._expression_rows(score, sheet, out)
        return {r[1]: r for r in out}

    def test_missing_block_warns_incomplete_fails_complete_passes(self):
        score = _building()
        self.assertEqual(self._rows(score, {})['direction.expression'][0], 'WARN')
        self.assertEqual(self._rows(score, dict(expression=dict(sonic_picture='x')))['direction.expression'][0], 'FAIL')
        full = self._rows(score, dict(expression=SheetBlock()._block()))
        self.assertEqual(full['direction.expression'][0], 'PASS')

    def test_arousal_row_warns_on_a_contradicting_score_and_never_fails(self):
        self.assertEqual(self._rows(_building(), {})['expression.arousal_order'][0], 'PASS')
        self.assertEqual(self._rows(_flat_then_loud(), {})['expression.arousal_order'][0], 'WARN')

    def test_melody_row_is_info_without_a_figure_and_warns_on_one_cell(self):
        self.assertEqual(self._rows(_building(), {})['melody.variety'][0], 'INFO')
        one_cell = _score([], [dict(name='m', role='melody', notes=_notes([62, 65, 67, 65] * 8))])
        self.assertEqual(self._rows(one_cell, {})['melody.variety'][0], 'WARN')


if __name__ == '__main__':
    unittest.main()
