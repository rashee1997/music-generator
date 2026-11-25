"""Tests for the debug engine: the arithmetic that has to hold no matter which piece it runs on."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

import audio_debug
from audio_debug import margins, solve
from audio_debug.domains import base


def row(name, value, threshold, unit='dB', level='FAIL', stem=None, **raw):
    return dict(row=name, value=value, threshold=threshold, unit=unit, level=level, stem=stem, detail='',
                raw=dict(raw), source='test')


def case(rows, project='/tmp/audio_debug_case', score=None, mix=None, instruments=None):
    return audio_debug.Case(project, score or {}, rows, mix or {}, instruments or {}, {}, None, {})


class Margins(unittest.TestCase):
    def test_max_row_is_signed_by_its_tolerance(self):
        s, sense, _ = margins.safety(row('clicks', 1, 0, unit='events'))
        self.assertEqual(sense, 'max')
        self.assertAlmostEqual(s, -1.0)                 # one event over a limit of zero fails by one whole unit

    def test_a_duration_is_judged_against_its_own_limit(self):
        s, _, scale = margins.safety(row('stem.dropout', 12.0, 20.0, unit='ms'))
        self.assertAlmostEqual(scale, 20.0)
        self.assertAlmostEqual(s, 0.4)                  # 8 ms of room in a 20 ms limit

    def test_a_minimum_row_improves_as_it_rises(self):
        s, sense, _ = margins.safety(row('loudness', -14.0, -16.0, unit='LUFS'))
        self.assertEqual(sense, 'min')
        self.assertGreater(s, 0)

    def test_an_info_row_is_not_judged(self):
        s, _, _ = margins.safety(row('chem.valence', 0.3, 0.0, unit='index', level='INFO'))
        self.assertEqual(s, float('inf'))


class VerdictText(unittest.TestCase):
    """Older renders have no rows.json; the numbers in the verdict text are still usable."""

    def test_a_limit_is_read_with_its_unit(self):
        got = audio_debug.artifacts._parse_detail('15-22 kHz holds -45.0 dB of the 200 Hz-16 kHz band (limit -45)')
        self.assertAlmostEqual(got['value'], -45.0)
        self.assertAlmostEqual(got['threshold'], -45.0)
        self.assertEqual(got['unit'], 'dB')

    def test_a_want_is_a_minimum(self):
        got = audio_debug.artifacts._parse_detail(
            'keeps its pitch in 6% of its pitched frames (want 50%)')
        self.assertEqual(got['unit'], '%')
        self.assertAlmostEqual(got['threshold'], 50.0)


class Solver(unittest.TestCase):
    def _analysis(self, bound=(-6.0, 6.0)):
        levers = [base.Lever('gain.x', 'stems', 'gain', 0.0, bound[0], bound[1], 0.5, 'dB', 'x', stem='x')]
        # dB rows: a coefficient of +6 means the value rises 6 dB per unit, so safety falls 1 per unit.
        rows = [row('spectral.equal_loudness', 6.0, 0.0), row('spectral.band_fold', -12.0, 0.0, level='PASS')]
        coef = {(margins.row_key(rows[0]), 'gain.x'): 6.0, (margins.row_key(rows[1]), 'gain.x'): -6.0}
        return base.Analysis(rows=rows, levers=levers, coefficients=coef)

    def test_it_equalises_margins_instead_of_maximising_one_row(self):
        plan = solve.plan(self._analysis())
        self.assertLess(plan.deltas.get('gain.x', 0.0), 0.0)      # raising this stem's level would cost the other row
        a = plan.predicted[margins.row_key(self._analysis().rows[0])]
        b = plan.predicted[margins.row_key(self._analysis().rows[1])]
        self.assertAlmostEqual(a[1], b[1], places=2)     # the worst safety of both rows is the same after the move
        self.assertGreater(a[1], a[0])

    def test_a_move_that_no_value_can_make_is_reported_as_a_conflict(self):
        plan = solve.plan(self._analysis(bound=(0.0, 2.0)))
        self.assertTrue(plan.conflicts)
        c = plan.conflicts[0]
        self.assertEqual(c['lever'], 'gain.x')
        self.assertGreater(c['feasible'][0], c['feasible'][1])
        self.assertIn('cannot satisfy', c['why'])

    def test_a_burned_lever_is_not_proposed_again(self):
        hist = [dict(lever='gain.x', row='spectral.equal_loudness', outcome='no change')]
        plan = solve.plan(self._analysis(), history=hist)
        self.assertNotIn('gain.x', plan.deltas)
        self.assertTrue(plan.burned)

    def test_a_row_with_no_lever_is_closed_not_failed(self):
        rows = [row('hrtf.cue_error', 9.0, 3.0)]
        plan = solve.plan(base.Analysis(rows=rows))
        self.assertIn('hrtf.cue_error', plan.closed)
        self.assertEqual(plan.deltas, {})


class LazyDomains(unittest.TestCase):
    def test_only_the_failing_domain_runs(self):
        rows = [row('clicks', 1, 0, unit='events'),
                row('stem.dropout', 4.0, 20.0, unit='ms', level='PASS', stem='kit'),
                row('chem.valence', 0.2, 0.0, unit='index', level='INFO')]
        tmp = tempfile.mkdtemp()
        try:
            rep = audio_debug.autopsy(case(rows, project=tmp))
            self.assertEqual(rep.run_domains, ['master'])
            self.assertEqual([r['row'] for r in rep.binding], ['clicks'])
            self.assertTrue(os.path.isfile(os.path.join(tmp, 'reports', 'debug_audio.md')))
            with open(os.path.join(tmp, 'reports', 'debug_audio.md'), encoding='utf-8') as fh:
                text = fh.read()
            self.assertIn('Debug autopsy', text)
            self.assertIn('not run', text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_an_advisory_row_never_binds(self):
        rows = [row('chem.tension', 0.9, 0.3, unit='index', level='WARN')]
        rep = audio_debug.autopsy(case(rows, project=tempfile.mkdtemp()), write=False)
        self.assertEqual(rep.binding, [])
        self.assertEqual(rep.run_domains, [])


if __name__ == '__main__':
    unittest.main()
