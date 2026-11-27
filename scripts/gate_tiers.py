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
"""gate_tiers.py - what each gate row is for: an invariant, an expressive judgement or telemetry.

    python3 scripts/gate_tiers.py list                 # the three tiers and what each one blocks
    python3 scripts/gate_tiers.py row feel.witek        # which tier a row is in, and why
    python3 scripts/gate_tiers.py check                 # every row classified exactly once

The map is data (`references/data/presets/gate/tiers.json`), keyed exactly like `scripts/lint_coverage.py::COVERAGE`:
one entry per `gate_profiles.ROWS` id, plus a `reported` block for ids a module emits without a profile row
(`delivery.true_peak`, `expression.preset`, the `audio` and `vocal` umbrella rows, `mix:*`, `music21_*`).

Why the split exists: the gate prints one scoreboard, and a broken file (a click, a folded sub, a truncated delivery)
sat in the same list as a judgement about the music (a contour, a groove, a chem guess). The tier says which is which,
so a report can be read - and so a change to one cannot quietly retune the other. It changes no verdict: the
certification rule stays "no FAIL anywhere", and `gate_profiles` still decides which rows apply.

Tier 1 - invariant. A fault regardless of genre, scene or brief: a broken file, a broken delivery, a broken decode.
Tier 2 - expressive. A judgement that depends on what the piece is; a profile may relax or skip it with a measurement
         and a reason, and `rca.py` can return `mismatch` for it.
Tier 3 - advisory. Telemetry: it informs a mixing or mastering decision and its numbers are starting values. It prints
         INFO or WARN and never FAILs.

`warn_only` under tier 1 names the physical rows whose measurement is right and whose verdict is not yet promoted; they
stay WARN until a project measures one, and the list is the record of that decision rather than a silent cap.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

TIERS_PATH = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate', 'tiers.json')
TIER_NAMES = ('1', '2', '3')
REQUIRED = ('name', 'blocks', 'why', 'ids')


def load(path=TIERS_PATH):
    """The tier file as a dict; raises when it is missing or not JSON."""
    with open(path, encoding='utf-8') as f:
        return json.load(f)


_CACHE = {}


def _index(path=TIERS_PATH):
    """{row id: tier} for every id the file names, reported ids included."""
    key = os.path.abspath(path)
    if key not in _CACHE:
        doc = load(path)
        idx = {}
        for tier, block in (doc.get('tiers') or {}).items():
            for rid in block.get('ids') or []:
                idx[rid] = str(tier)
        for rid, tier in (doc.get('reported') or {}).items():
            idx[rid] = str(tier)
        _CACHE[key] = (doc, idx)
    return _CACHE[key]


def tier_of(rid, path=TIERS_PATH):
    """The tier of a row id, alias-aware, or None for an id this file does not name.

    A reported id may be a family: `mix:diagnostics`, `music21_harmony` and `stem_rows` find the `mix:*`,
    `music21_*` and `stem_rows` entries. Nothing falls back to a default tier - an unclassified row is a bug.
    """
    import gate_profiles as gp
    doc, idx = _index(path)
    rid = str(rid)
    cand = [rid, gp.canonical(rid)]
    for pref in ('mix:', 'music21_'):
        if rid.startswith(pref):
            cand.append(pref + '*')
    if rid in ('stem_rows',):
        cand.append('stem_rows')
    for c in cand:
        if c in idx:
            return idx[c]
    return None


def name(tier, path=TIERS_PATH):
    doc, _ = _index(path)
    return ((doc.get('tiers') or {}).get(str(tier)) or {}).get('name', '')


def ids(tier, path=TIERS_PATH):
    doc, _ = _index(path)
    return list(((doc.get('tiers') or {}).get(str(tier)) or {}).get('ids') or [])


def warn_only(path=TIERS_PATH):
    doc, _ = _index(path)
    return list(((doc.get('tiers') or {}).get('1') or {}).get('warn_only') or [])


def summary(rows, path=TIERS_PATH):
    """{tier: {name, rows, pass, warn, fail, info, unclassified}} for a finished row list, for the scoreboard and
    `reports/ci_report.json`. Rows keep their order inside a tier."""
    out = {}
    for tier in TIER_NAMES:
        out[tier] = dict(name=name(tier, path), blocks=((_index(path)[0]['tiers'].get(tier) or {}).get('blocks', '')),
                         rows=0, **{k: 0 for k in ('pass', 'warn', 'fail', 'info')})
    unknown = []
    for lvl, rid, _detail in rows:
        tier = tier_of(rid, path)
        if tier is None:
            unknown.append(rid)
            continue
        b = out[tier]
        b['rows'] += 1
        key = str(lvl).lower()
        if key in b:
            b[key] += 1
    out['unclassified'] = sorted(set(unknown))
    return out


def problems(path=TIERS_PATH):
    """Problems in the tier file: [] when every row is classified exactly once. `lint_coverage.py` calls this, so a
    new row without a tier - or a row listed in two tiers - fails the same check that already guards the coverage."""
    import gate_profiles as gp
    try:
        doc = load(path)
    except (OSError, ValueError) as exc:
        return [f'tiers.json cannot be read: {exc}']
    out = []
    tiers = doc.get('tiers') or {}
    for tier in TIER_NAMES:
        block = tiers.get(tier)
        if not isinstance(block, dict):
            out.append(f'tier {tier} is missing')
            continue
        for key in REQUIRED:
            if key not in block or (key != 'ids' and not str(block[key]).strip()):
                out.append(f'tier {tier}: missing "{key}"')
        if not isinstance(block.get('ids'), list):
            out.append(f'tier {tier}: "ids" must be a list')
    seen = {}
    for tier, block in tiers.items():
        for rid in (block or {}).get('ids') or []:
            if rid in gp.ROWS:
                rid = gp.canonical(rid)
            seen.setdefault(rid, []).append(str(tier))
    for rid, where in sorted(seen.items()):
        if rid not in gp.ROWS:
            out.append(f'{rid!r} is not a gate row (listed under tier {", ".join(where)})')
        if len(where) > 1:
            out.append(f'{rid!r} is in tier {" and ".join(where)}: a row has exactly one job')
    missing = sorted(set(gp.ROWS) - set(seen))
    if missing:
        out.append(f'{len(missing)} row(s) have no tier: {", ".join(missing)}')
    for rid in warn_only(path):
        if rid not in (tiers.get('1') or {}).get('ids', []):
            out.append(f'{rid!r} is in tier 1 warn_only but not in tier 1')
    for tier in ('2', '3'):
        for rid in (tiers.get(tier) or {}).get('ids') or []:
            if (gp.ROWS.get(rid) or {}).get('protected'):
                out.append(f'{rid!r} is a protected row: it belongs to tier 1, not tier {tier}')
    reported = doc.get('reported') or {}
    for rid, tier in reported.items():
        if str(tier) not in TIER_NAMES:
            out.append(f'reported {rid!r}: tier {tier!r} is not one of {TIER_NAMES}')
        if rid in gp.ROWS:
            out.append(f'reported {rid!r} is also a profile row: move it into tier {tier}')
    for tier in ('2', '3'):
        blk = tiers.get(tier) or {}
        if blk.get('blocks') not in ('certification', 'nothing'):
            out.append(f'tier {tier}: "blocks" must be "certification" or "nothing", not {blk.get("blocks")!r}')
    return out


def cmd_list():
    doc = load()
    for tier in TIER_NAMES:
        b = doc['tiers'][tier]
        print(f'{tier} {b["name"]} ({len(b["ids"])} rows, blocks: {b["blocks"]})')
        print(f'  {b["why"]}')
        if b.get('warn_only'):
            print(f'  warn only (physical, verdict not promoted): {", ".join(b["warn_only"])}')
    print(f'reported without a profile row: {", ".join(sorted(doc.get("reported") or {}))}')


def cmd_row(rid):
    tier = tier_of(rid)
    if tier is None:
        print(f'{rid}: no tier. Known rows: gate_tiers.py list, or scripts/gate_profiles.py rows')
        return 2
    doc, _ = _index()
    print(f'{rid}: tier {tier} ({doc["tiers"][tier]["name"]}), blocks: {doc["tiers"][tier]["blocks"]}')
    print(f'  {doc["tiers"][tier]["why"]}')
    return 0


def main():
    ap = argparse.ArgumentParser(description='What each gate row is for.')
    sub = ap.add_subparsers(dest='cmd')
    sub.add_parser('list', help='the three tiers')
    p = sub.add_parser('row', help='one row id')
    p.add_argument('id')
    sub.add_parser('check', help='every row classified exactly once')
    a = ap.parse_args()
    if a.cmd == 'list' or a.cmd is None:
        cmd_list()
        return 0
    if a.cmd == 'row':
        return cmd_row(a.id)
    bad = problems()
    for p_ in bad:
        print(f'[FAIL] {p_}')
    if not bad:
        print('every gate row has exactly one tier')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
