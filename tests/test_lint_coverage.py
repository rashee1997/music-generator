# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Every gate row has an answer to "what catches this before a render?", and every answer names a rule that exists.

Run: python -m unittest tests.test_lint_coverage
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'helpers'))
import gate_profiles  # noqa: E402
import lint_coverage  # noqa: E402
import preflight_levels  # noqa: E402
import preflight_lint  # noqa: E402
import preset_probe  # noqa: E402


class Coverage(unittest.TestCase):
    def test_every_gate_row_has_an_entry(self):
        self.assertEqual(lint_coverage.missing(gate_profiles.ROWS), [], 'a gate row has no pre-render rule and no reason: add it to scripts/lint_coverage.py')

    def test_no_entry_names_a_row_the_gate_does_not_have(self):
        self.assertEqual([r for r in lint_coverage.COVERAGE if r not in gate_profiles.ROWS], [])

    def test_every_audio_entry_gives_a_reason(self):
        for row, (kind, detail) in lint_coverage.COVERAGE.items():
            if kind == 'audio':
                self.assertTrue(isinstance(detail, str) and len(detail.split()) >= 3, row)

    def test_every_preflight_entry_names_rules_that_exist(self):
        self.assertEqual(lint_coverage.unknown_rules(), [])

    def test_the_rules_the_modules_emit_are_the_rules_the_table_lists(self):
        score = {'bpm': 120, 'ts': [4, 4], 'tracks': [], 'plan': {'sections': []}}
        emitted = {r[1] for r in preflight_lint.checks(score, None, lookup=lambda k, n: None, patch_range=lambda b, p: None, probe=False)}
        self.assertTrue(emitted <= set(lint_coverage.PREFLIGHT_ROWS), sorted(emitted - set(lint_coverage.PREFLIGHT_ROWS)))

    def test_the_audit_can_fail(self):
        self.assertEqual(lint_coverage.missing(['a.row.that.does.not.exist']), ['a.row.that.does.not.exist'])


class Wiring(unittest.TestCase):
    def test_checks_runs_all_three_modules(self):
        score = {'bpm': 120, 'ts': [4, 4], 'tempo_points': [[0, 60], [10, 120]], 'plan': {'sections': []},
                 'tracks': [dict(name='hb', instrument='sfx:heartbeat', role='fx', notes=[dict(t=0, d=2, p=60, v=0.8)])]}
        rows = preflight_lint.checks(score, None, lookup=lambda k, n: {'seconds': 2.0} if k == 'sfx' else None, patch_range=lambda b, p: None)
        names = {r[1] for r in rows}
        self.assertIn('preflight.tempo', names)
        self.assertTrue(any(n.startswith('probe.') for n in names))
        self.assertIn('preflight.sfx_length', names)


if __name__ == '__main__':
    unittest.main()
