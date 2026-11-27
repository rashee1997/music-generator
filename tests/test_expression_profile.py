# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The expression rows' figures belong to the piece: they come from its own gate profile.

`expression.arousal_order` and `melody.variety` are measured, not guessed, but the anchors they are measured against
describe a piece - a drone cue has no build to rank, a through-composed cue no repeating figure. Those anchors live in
the profile's `"expression"` block, so a project states the piece it wrote; the shipped starting values are what a
profile that says nothing inherits. This also holds the two limits that keep it honest: an unknown key or a number
outside its range is an error (never a silent default), and no value can switch a row off.
Run: python -m unittest tests.test_expression_profile
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import gate_profiles as gpf  # noqa: E402
import presets  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'helpers'))
import expression_report as er  # noqa: E402


class ExpressionProfileTest(unittest.TestCase):
    def setUp(self):
        presets.reset_projects()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        presets.reset_projects()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _project(self, expression, name='probe'):
        """A temp project with its own gate profile, added to the presets' project layer."""
        d = os.path.join(self.tmp, name, 'presets', 'gate')
        os.makedirs(d)
        prof = {'name': name, 'character': 'a probe profile for the expression figures', 'extends': 'melodic',
                'rows': {}}
        if expression is not None:
            prof['expression'] = expression
        with open(os.path.join(d, name + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(prof, fh)
        presets.add_project(os.path.join(self.tmp, name))
        return name

    def test_a_profile_that_says_nothing_keeps_the_shipped_figures(self):
        # every profile written before the block existed must be judged exactly as it was
        cfg = gpf.resolve({'piece_type': 'melodic'}).expression_cfg()
        self.assertEqual(cfg['melody_variety'], gpf.EXPRESSION_DEFAULTS['melody_variety'])
        self.assertEqual(cfg['arousal_order'], gpf.EXPRESSION_DEFAULTS['arousal_order'])

    def test_the_project_profile_states_the_figure(self):
        name = self._project({'melody_variety': {'max_identical_bar_share': 0.2}})
        cfg = gpf.resolve({'piece_type': name}).expression_cfg()
        self.assertAlmostEqual(cfg['melody_variety']['max_identical_bar_share'], 0.2)
        # the keys the block did not name keep their value instead of disappearing
        self.assertEqual(cfg['melody_variety']['min_notes'], gpf.EXPRESSION_DEFAULTS['melody_variety']['min_notes'])

    def test_an_unknown_key_is_an_error_not_a_default(self):
        name = self._project({'melody_variety': {'max_identical_bars': 0.2}})
        with self.assertRaises(ValueError):
            gpf.resolve({'piece_type': name}).expression_cfg()

    def test_a_number_outside_its_range_is_an_error(self):
        # a min_rho of -1 would pass every piece: the range is what stops a profile from switching the row off
        name = self._project({'arousal_order': {'min_rho': -1.0}})
        with self.assertRaises(ValueError):
            gpf.resolve({'piece_type': name}).expression_cfg()

    def test_the_profile_check_reports_a_bad_role(self):
        name = self._project({'figure_roles': ['melody', 'not_a_role']})
        allp = presets.load('gate')
        probs = gpf.profile_problems(name, allp[name], allp)
        self.assertTrue(any('not_a_role' in p for p in probs), probs)

    def test_the_figures_reach_the_measurement(self):
        # four distinct cells, each played twice: half the bars repeat an earlier bar exactly
        cells = [[60, 62, 64, 67], [62, 64, 67, 69], [64, 67, 69, 72], [65, 67, 69, 72]]
        notes = []
        for bar in range(8):
            for i, p in enumerate(cells[bar // 2]):
                notes.append({'t': bar * 4 + i, 'p': p, 'd': 0.9, 'v': 0.7})
        score = {'bpm': 96, 'ts': [4, 4], 'tracks': [{'name': 'fig', 'role': 'melody', 'notes': notes}]}
        shipped = er.defaults()
        tight = dict(shipped, melody_variety=dict(shipped['melody_variety'], max_identical_bar_share=0.05))
        self.assertFalse(er.melody_variety(score, shipped)['flags'], er.melody_variety(score, shipped)['flags'])
        self.assertTrue(er.melody_variety(score, tight)['flags'])


if __name__ == '__main__':
    unittest.main()
