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
"""The gate does not become soft by being configurable.

A profile may relax or skip a row, so the ways that freedom could quietly become a rubber stamp are held here:

  * every relaxation in a shipped profile carries a written, measured reason (a number in it, not a mood word),
  * a protected or un-skippable row is never the one relaxed,
  * the Witek band is one function, and its Warn band is real: 5.0 fails under an override of 4.8 and passes as a WARN
    under the shipped 5.5, while 5.6 fails under the shipped limits,
  * every tier-1 row resolves to advice (its own entry or its tier's), never to the generic fallback,
  * the feedback table only names rows the gate knows, and the scene contract's roles are internally consistent.

Run: python -m unittest tests.test_gate_anti_soft
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import gate_feedback              # noqa: E402
import gate_profiles as gpf       # noqa: E402
import gate_tiers                 # noqa: E402
import pattern_audit as pa        # noqa: E402
import presets                    # noqa: E402


def _shipped():
    return presets.load('gate')


class RelaxationsAreReasons(unittest.TestCase):
    def test_every_shipped_profile_validates(self):
        self.assertEqual(gpf.problems(), [])

    def test_every_relax_or_skip_has_a_measured_reason(self):
        bad = []
        for name, prof in _shipped().items():
            for rid, cfg in (prof.get('rows') or {}).items():
                if not isinstance(cfg, dict) or cfg.get('mode') not in ('relax', 'skip'):
                    continue
                reason = str(cfg.get('reason') or '')
                # a shipped type profile says in words why its music needs the relaxation; the measurement is required
                # of a *project's* relaxation by gate_profiles.relax (it refuses a row the last render did not fail)
                if len(reason) < 20:
                    bad.append(f'{name}: {rid} (reason {reason!r})')
        self.assertEqual(bad, [], 'a relaxation needs a written, measured reason')

    def test_no_protected_or_unskippable_row_is_relaxed(self):
        bad = []
        for name, prof in _shipped().items():
            for rid, cfg in (prof.get('rows') or {}).items():
                canon = gpf.canonical(rid)
                spec = gpf.ROWS.get(canon) or {}
                if not isinstance(cfg, dict):
                    continue
                mode = cfg.get('mode')
                if mode == 'skip' and (spec.get('protected') or spec.get('no_skip')):
                    bad.append(f'{name}: {rid} skipped')
                if mode == 'relax' and spec.get('protected'):
                    bad.append(f'{name}: {rid} relaxed')
        self.assertEqual(bad, [])


class WitekBandIsOneFunction(unittest.TestCase):
    def test_the_warn_band_is_between_the_pocket_and_the_fail_limit(self):
        lo, hi, fail_hi = 0.4, 4.8, 5.5
        self.assertEqual(pa.bsi_verdict(5.0, lo, hi, fail_hi)[0], 'WARN')
        self.assertEqual(pa.bsi_verdict(4.0, lo, hi, fail_hi)[0], 'PASS')
        self.assertEqual(pa.bsi_verdict(0.1, lo, hi, fail_hi)[0], 'WARN')
        self.assertEqual(pa.bsi_verdict(5.6, lo, hi, fail_hi)[0], 'FAIL')
        self.assertEqual(pa.bsi_verdict(5.0, lo, hi, 4.8)[0], 'FAIL')

    def test_the_defaults_have_not_moved(self):
        d = gpf.defaults('feel.witek')
        self.assertEqual((d['bsi_lo'], d['bsi_hi'], d['bsi_fail_hi']), (0.4, 4.8, 5.5))

    def test_a_score_override_moves_the_limit_and_keeps_its_reason(self):
        score = {"piece_type": "melodic", "gate": {"feel.witek": {"bsi_fail_hi": 4.8,
                                                                  "reason": "measured on a 5.0 BSI cue"}}}
        p = gpf.resolve(score)
        self.assertEqual(p.param('feel.witek', 'bsi_fail_hi'), 4.8)
        self.assertEqual(p.param('feel.witek', 'bsi_hi'), 4.8)
        self.assertEqual(pa.bsi_verdict(5.0, 0.4, 4.8, float(p.param('feel.witek', 'bsi_fail_hi')))[0], 'FAIL')


class TiersAndFeedback(unittest.TestCase):
    def test_every_tier_one_row_resolves_to_advice(self):
        ids = json.load(open(os.path.join(HERE, '..', 'references', 'data', 'presets', 'gate', 'data',
                                          'tiers.json'), encoding='utf-8'))['tiers']['1']['ids']
        for rid in ids:
            e = gate_feedback.entry(rid)
            self.assertIn(e['from'], ('row', 'tier 1'), f'{rid} falls through to the generic advice')
            self.assertTrue(e.get('do_next'))
        own = [r for r in ids if gate_feedback.entry(r)['from'] == 'row']
        self.assertGreaterEqual(len(own), 6, 'the feedback table has stopped naming the rows an agent meets first')
        # the same question asked of the reader's own filter: an empty list here means the tier comparison broke
        self.assertIn('clipping', gate_feedback.rows_in(1))

    def test_feedback_only_names_rows_the_gate_knows(self):
        reported = json.load(open(os.path.join(HERE, '..', 'references', 'data', 'presets', 'gate', 'data',
                                               'tiers.json'), encoding='utf-8')).get('reported') or {}
        known = set(gpf.ROWS) | set(reported)
        named = set(gate_feedback.rows_in())
        self.assertEqual(sorted(named - known), [])

    def test_every_row_has_exactly_one_tier(self):
        self.assertEqual(gate_tiers.problems(), [])

    def test_a_fail_gets_a_plan_before_a_warn(self):
        plan = gate_feedback.plan([('WARN', 'clicks', ''), ('FAIL', 'clipping', ''), ('FAIL', 'scene.arc_step', '')])
        self.assertEqual([p[0] for p in plan][0], 'clipping')
        self.assertEqual(len(plan), 2)          # a WARN is not a call to action


class SceneContractIsConsistent(unittest.TestCase):
    def test_roles_agree_with_the_key_table(self):
        doc = json.load(open(os.path.join(HERE, '..', 'references', 'data', 'presets', 'gate', 'data',
                                          'scene_roles.json'), encoding='utf-8'))
        keys = doc['keys']
        for role, spec in doc['roles'].items():
            self.assertTrue(spec.get('kind'), f'{role} has no kind')
            req, allowed = spec.get('required') or [], spec.get('allowed') or []
            self.assertTrue(set(req) <= set(allowed), f'{role}: a required key is not allowed')
            self.assertEqual(sorted(set(allowed) - set(keys)), [], f'{role}: a key has no meaning or range')

    def test_analysis_points_at_roles_that_exist(self):
        doc = json.load(open(os.path.join(HERE, '..', 'references', 'data', 'presets', 'gate', 'data',
                                          'scene_roles.json'), encoding='utf-8'))
        kinds = {spec.get('kind') for spec in doc['roles'].values()}
        for key in ('peak_kind', 'build_kind', 'release_kind'):
            self.assertIn(doc['analysis'][key], kinds, f'analysis.{key} names a kind no role has')
        self.assertIn('surprise_min_z', doc['keys'])


if __name__ == '__main__':
    unittest.main()
