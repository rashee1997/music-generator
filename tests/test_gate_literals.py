"""A new gate threshold is a rows.json parameter, not a Python constant.

The fixture lists the module-level numeric constants the gate modules had when the thresholds became data. A constant that
is not on it fails here: move the number to references/data/presets/gate/data/rows.json (a default, a range, a source),
read it with gp.param(), or - for a physical or unit constant that really is not a threshold - regenerate the fixture with
`python scripts/threshold_audit.py --update` and say why in the commit.
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import threshold_audit as ta  # noqa: E402


class NoNewLiteralThresholds(unittest.TestCase):
    def test_no_gate_module_gained_a_numeric_constant(self):
        with open(ta.FIXTURE, encoding='utf-8') as f:
            allowed = json.load(f)
        added = {m: sorted(set(v) - set(allowed.get(m, []))) for m, v in ta.names().items()}
        added = {m: v for m, v in added.items() if v}
        self.assertEqual(added, {}, 'new literal constants in the gate: put the number in rows.json')


if __name__ == '__main__':
    unittest.main()
