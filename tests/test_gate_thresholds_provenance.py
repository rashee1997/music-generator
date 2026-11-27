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
"""Every gate threshold is data, and every number says where it came from.

`references/data/presets/gate/data/rows.json` is the only copy of the row table: `gate_profiles.ROWS` is built from it.
This test holds the two things that keep it honest:

  * no number is duplicated in Python (a change in the JSON moves ROWS, and a default cannot drift), and
  * every parameter carries a `source`: either the citation it came from, or the words "starting value" when no
    published measurement exists. A threshold with no provenance is the failure this file exists for - not because a
    starting value is wrong, but because an unlabelled number claims an authority it does not have.

Run: python -m unittest tests.test_gate_thresholds_provenance
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import gate_profiles as gp      # noqa: E402
import gate_tiers               # noqa: E402

DATA = os.path.join(HERE, '..', 'references', 'data', 'presets', 'gate', 'data')
CITE = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:ITU-R|ISO|AES|EBU|ANSI|Witek|Vuust|Huron|Meyer|Pearce|Zwicker|Fastl|"
                  r"Moore|Glasberg|Daniel|Weber|Sethares|Plomp|Vassilakis|Chew|Terhardt|ASAP|corpus)\b")


def rows_doc():
    with open(os.path.join(DATA, 'rows.json'), encoding='utf-8') as f:
        return json.load(f)


class ThresholdsAreData(unittest.TestCase):
    def test_python_holds_no_second_copy(self):
        doc = rows_doc()['rows']
        self.assertEqual(sorted(doc), sorted(gp.ROWS), 'a row exists in one place only')
        for rid, spec in doc.items():
            live = gp.ROWS[rid]
            self.assertEqual(spec.get('meaning', ''), live['meaning'], f'{rid}: meaning drifted')
            for flag in ('protected', 'no_skip'):
                self.assertEqual(bool(spec.get(flag)), bool(live.get(flag)), f'{rid}: {flag} drifted')
            want = {}
            for name, p in (spec.get('params') or {}).items():
                if isinstance(p['default'], bool):
                    want[name] = (p['default'],)
                elif 'choices' in p:
                    want[name] = tuple([p['default']] + [c for c in p['choices'] if c != p['default']])
                else:
                    t = (p['default'], p['low'], p['high'])
                    want[name] = t + (str(p['unit']),) if p.get('unit') else t
            self.assertEqual(want, live.get('params') or {}, f'{rid}: parameters drifted from the JSON')

    def test_every_row_has_a_meaning(self):
        for rid, spec in rows_doc()['rows'].items():
            self.assertTrue(str(spec.get('meaning') or '').strip(), f'{rid} has no meaning')

    def test_every_parameter_has_a_provenance(self):
        missing, weak = [], []
        for rid, spec in rows_doc()['rows'].items():
            for name, p in (spec.get('params') or {}).items():
                src = str(p.get('source') or '').strip()
                if not src:
                    missing.append(f'{rid}.{name}')
                elif 'starting value' not in src.lower() and not CITE.search(src):
                    weak.append(f'{rid}.{name}: {src!r}')
        self.assertEqual(missing, [], 'a threshold has no source and does not say it is a starting value')
        self.assertEqual(weak, [], 'a source names neither a citation nor the words "starting value"')

    def test_ranges_still_bound_every_number(self):
        for rid, spec in rows_doc()['rows'].items():
            for name, p in (spec.get('params') or {}).items():
                if 'low' in p:
                    self.assertLessEqual(p['low'], p['default'], f'{rid}.{name}: default under its own floor')
                    self.assertLessEqual(p['default'], p['high'], f'{rid}.{name}: default over its own ceiling')
                elif 'choices' in p:
                    self.assertIn(p['default'], p['choices'], f'{rid}.{name}: default is not one of the choices')

    def test_enough_rows_are_actually_cited(self):
        # a source may cite a study and still call its number a starting value (that is the honest case); what must not
        # happen is the table losing its citations altogether
        cited = {rid for rid, spec in rows_doc()['rows'].items()
                 for p in (spec.get('params') or {}).values() if CITE.search(str(p.get('source', '')))}
        self.assertGreaterEqual(len(cited), 6,
                                'the table has stopped citing its research; a regression to nothing but starting values '
                                'is the hallucination this file guards against')

    def test_every_row_has_exactly_one_tier(self):
        self.assertEqual(gate_tiers.problems(), [])

    def test_tiers_and_rows_describe_the_same_gate(self):
        with open(os.path.join(DATA, 'tiers.json'), encoding='utf-8') as f:
            tiers = json.load(f)
        tier_ids = {rid for t in tiers['tiers'].values() for rid in t['ids']}
        self.assertEqual(sorted(set(gp.ROWS) - tier_ids), [], 'a row has no tier')
        # an id in a tier that is not a row must be a reported id the tier map declares, so a renamed row cannot leave
        # its old tier behind unnoticed
        unknown = sorted(tier_ids - set(gp.ROWS) - set(tiers.get('reported') or {}))
        self.assertEqual(unknown, [], 'a tier names a row the gate does not have')


if __name__ == '__main__':
    unittest.main()
