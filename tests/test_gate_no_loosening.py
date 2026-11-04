"""No existing gate threshold was loosened.

`tests/fixtures/gate/thresholds.json` is a snapshot of every row's default parameters taken when the bigger gate work
landed. This test fails when a number moves without the fixture being regenerated in a reviewed commit, so a relaxed
threshold cannot slip in as a side effect of another change.

Regenerate deliberately (and say why in the commit message):

    .venv/Scripts/python.exe tests/test_gate_no_loosening.py --update
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import gate_profiles as gp  # noqa: E402

SNAP = os.path.join(HERE, 'fixtures', 'gate', 'thresholds.json')


def current():
    """Every row's default parameters, and the rows that cannot be skipped."""
    return dict(
        rows={rid: {k: v[0] for k, v in (r.get('params') or {}).items()} for rid, r in gp.ROWS.items()},
        protected=sorted(rid for rid, r in gp.ROWS.items() if r.get('protected')),
        no_skip=sorted(rid for rid, r in gp.ROWS.items() if r.get('no_skip')),
    )


class NoThresholdWasLoosened(unittest.TestCase):
    def test_the_snapshot_exists(self):
        self.assertTrue(os.path.isfile(SNAP), f'missing {SNAP}: run tests/test_gate_no_loosening.py --update')

    def test_every_default_matches_the_snapshot(self):
        with open(SNAP, encoding='utf-8') as fh:
            want = json.load(fh)
        got = current()
        self.assertEqual(sorted(got['rows']), sorted(want['rows']), 'a row was added or removed')
        for rid in sorted(want['rows']):
            self.assertEqual(got['rows'][rid], want['rows'][rid], f'row {rid} changed a default')

    def test_a_protected_row_cannot_be_switched_off(self):
        with open(SNAP, encoding='utf-8') as fh:
            want = json.load(fh)
        self.assertEqual(current()['protected'], want['protected'])
        self.assertEqual(current()['no_skip'], want['no_skip'])


def update():
    os.makedirs(os.path.dirname(SNAP), exist_ok=True)
    with open(SNAP, 'w', encoding='utf-8') as fh:
        json.dump(current(), fh, indent=2, sort_keys=True)
        fh.write('\n')
    print('wrote', SNAP)


if __name__ == '__main__':
    if '--update' in sys.argv:
        update()
    else:
        unittest.main()
