# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

#!/usr/bin/env python3
"""The tier map: every gate row has exactly one job, and an advisory row never fails.

The map is `references/data/presets/gate/tiers.json`, read by `scripts/gate_tiers.py`. These tests are what keeps it
honest: a new row cannot ship without a tier (`lint_coverage.tier_problems`), a protected row cannot be filed as a
taste judgement, and a row the file calls advisory cannot appear as a FAIL in a certified report.
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / '..' / 'scripts'))

import gate_profiles            # noqa: E402
import gate_tiers               # noqa: E402
import lint_coverage            # noqa: E402

PROJECTS = HERE / '..' / 'projects'


class TierMap(unittest.TestCase):
    def test_every_row_is_classified_exactly_once(self):
        self.assertEqual(gate_tiers.problems(), [])
        self.assertEqual(lint_coverage.tier_problems(), [])          # the same check, from the coverage side

    def test_the_three_tiers_partition_the_rows(self):
        ids = [rid for tier in ('1', '2', '3') for rid in gate_tiers.ids(tier)]
        self.assertEqual(len(ids), len(set(ids)), 'a row is listed twice')
        self.assertEqual(set(ids), set(gate_profiles.ROWS))
        self.assertEqual(sum(1 for _ in ids), len(gate_profiles.ROWS))

    def test_every_reported_alias_resolves_to_a_tier(self):
        for reported in gate_profiles.ALIASES:
            self.assertIsNotNone(gate_tiers.tier_of(reported), f'{reported} has no tier')
        for rid in ('delivery.true_peak', 'expression.preset', 'scene.preset', 'audio', 'vocal', 'stem_rows'):
            self.assertIsNotNone(gate_tiers.tier_of(rid), f'{rid} has no tier')
        self.assertEqual(gate_tiers.tier_of('mix:something'), '3')      # a family, matched by prefix
        self.assertEqual(gate_tiers.tier_of('music21_harmony'), '3')
        self.assertIsNone(gate_tiers.tier_of('no.such.row'))

    def test_a_protected_row_is_an_invariant(self):
        for tier in ('2', '3'):
            for rid in gate_tiers.ids(tier):
                self.assertFalse(gate_profiles.ROWS[rid].get('protected'),
                                 f'{rid} is protected and cannot be a tier-{tier} judgement')

    def test_warn_only_rows_are_invariants(self):
        self.assertTrue(gate_tiers.warn_only())
        for rid in gate_tiers.warn_only():
            self.assertIn(rid, gate_tiers.ids('1'))
            self.assertIn(rid, gate_profiles.ROWS)

    def test_summary_keeps_an_unclassified_row_visible(self):
        s = gate_tiers.summary([('PASS', 'loudness', ''), ('FAIL', 'feel.witek', ''), ('INFO', 'ear.fatigue', ''),
                                ('WARN', 'mix:diagnostics', ''), ('FAIL', 'nobody.knows', '')])
        self.assertEqual(s['1']['pass'], 1)
        self.assertEqual(s['2']['fail'], 1)
        self.assertEqual(s['3']['info'], 1)
        self.assertEqual(s['3']['warn'], 1)              # mix:* is a family
        self.assertEqual(s['unclassified'], ['nobody.knows'])


class AdvisoryNeverBlocks(unittest.TestCase):
    """A tier-3 row prints INFO or WARN and never FAILs - checked against the reports this repo has already produced,
    which is the only place the claim can be observed on real numbers rather than in the code that makes it."""

    def reports(self):
        for path in sorted(PROJECTS.glob('*/reports/ci_report.json')):
            try:
                yield path, json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue

    def test_no_advisory_row_is_a_fail_in_any_certified_report(self):
        checked, seen = 0, set()
        for path, rep in self.reports():
            for row in rep.get('ci_checks') or []:
                tier = gate_tiers.tier_of(row.get('check'))
                if tier != '3':
                    continue
                checked += 1
                seen.add(row.get('check'))
                self.assertNotEqual(row.get('level'), 'FAIL',
                                    f'{path.parent.parent.name}: {row.get("check")} is advisory and failed')
        self.assertGreater(checked, 0, 'no advisory row was found in any report: the check proved nothing')
        self.assertIn('ear.fatigue', seen)


if __name__ == '__main__':
    unittest.main()
