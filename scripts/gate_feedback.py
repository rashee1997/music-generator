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
"""gate_feedback.py - what a failing row asks you to do next, in one place.

The gate says WHAT failed; this table says what to change, where, and what that costs (a report note, a re-render, a
re-performance, or a fix in the engine). It is data: `references/data/presets/gate/data/feedback.json`, one entry per row
plus a default per tier and a fallback, so the three readers (rca.py, gate_report.py, debug_audio.py --feedback) cannot
disagree with each other.

    python3 scripts/gate_feedback.py clipping feel.contour     # the action for these rows
    python3 scripts/gate_feedback.py --tier 1                  # every row that has its own entry in a tier

A row with no entry of its own inherits its tier's advice, and the tier's advice is deliberately about the KIND of row -
"this is the piece's own promise" for tier 2, "telemetry, do not chase it" for tier 3 - because inventing a specific fix
for a row nobody has measured yet would be worse than saying what class of problem it is.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PATH = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate', 'data', 'feedback.json')
_TABLE = {}


def table(path=PATH):
    key = os.path.abspath(path)
    if key not in _TABLE:
        with open(path, encoding='utf-8') as f:
            _TABLE[key] = json.load(f)
    return _TABLE[key]


def _tier(rid):
    try:
        import gate_tiers
        return gate_tiers.tier_of(rid)
    except Exception:
        return None


def entry(rid, path=PATH):
    """{do_next, where, cost, tier, from} for one row: its own entry, else its tier's, else the fallback."""
    t = table(path)
    tier = _tier(rid)
    own = (t.get('rows') or {}).get(rid)
    base = dict((t.get('fallback') or {}))
    base.update((t.get('tiers') or {}).get(str(tier)) or {})
    if own:
        base.update(own)
        base['from'] = 'row'
    elif tier is not None and str(tier) in (t.get('tiers') or {}):
        base['from'] = f'tier {tier}'
    else:
        base['from'] = 'fallback'
    base['tier'] = tier
    base.setdefault('where', [])
    base.setdefault('cost', 'render')
    return base


def rows_in(tier=None, path=PATH):
    """Row ids that have their own entry, optionally only those in one tier."""
    ids = sorted((table(path).get('rows') or {}))
    if tier is None:
        return ids
    return [r for r in ids if _tier(r) == int(tier)]


def plan(failures, limit=None, path=PATH):
    """[(level, row, do_next, cost)] for failing rows, most urgent first: tier 1, then 2, then 3, then unknown."""
    order = {1: 0, 2: 1, 3: 2, None: 3}
    items = []
    for f in failures:
        level, rid = f[0], f[1]
        if level != 'FAIL':
            continue
        e = entry(rid, path)
        items.append((order.get(e.get('tier'), 3), rid, e.get('do_next'), e.get('cost')))
    items.sort(key=lambda it: (it[0], it[1]))
    if limit:
        items = items[:limit]
    return [(rid, do, cost) for _o, rid, do, cost in items]


def text(failures, limit=None):
    lines = []
    for rid, do, cost in plan(failures, limit):
        lines.append(f'  {rid} ({cost}): {do}')
    return '\n'.join(lines) if lines else '  nothing to do: no row failed'


def main(argv=None):
    ap = argparse.ArgumentParser(description='What each gate row asks you to change, and what that costs.')
    ap.add_argument('rows', nargs='*', help='row ids (aliases accepted)')
    ap.add_argument('--tier', type=int, default=None, choices=(1, 2, 3), help='list the rows that have their own entry in this tier')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if a.tier is not None and not a.rows:
        ids = rows_in(a.tier)
        print('\n'.join(ids) if ids else f'no row has its own entry in tier {a.tier}')
        return 0
    if not a.rows:
        ap.error('give at least one row, or --tier N')
    out = {}
    for rid in a.rows:
        try:
            import gate_profiles
            rid = gate_profiles.canonical(rid)
        except Exception:
            pass
        out[rid] = entry(rid)
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for rid, e in out.items():
            print(f'{rid}  [tier {e.get("tier")}, {e.get("cost")}, from {e.get("from")}]')
            print(f'  {e.get("do_next")}')
            for w in e.get('where') or []:
                print(f'  where: {w}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
