# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
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
"""soul_check.py - the gate a piece must pass for its soul before it is released.

    python3 scripts/soul_check.py score.json                       # cultures from the score's fusion block
    python3 scripts/soul_check.py score.json --culture indian --culture west_african
    python3 scripts/soul_check.py score.json --culture western --strict   # WARNs also exit 1

It reads the score's notes only. Each check comes from a culture's soul profile (scripts/soul.py, references/soul/*.json),
so the same gate works for any mix. FAIL means a core element of a named culture is missing (no breath where the
culture needs silence, no off-beat groove where it is required, a phrase that does not come home, an instrument
that reads as another culture). WARN is a soft expectation. The gate cannot judge taste or whether the performance
is moving: a person must still listen.
Exit code 1 on any FAIL.
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import soul  # noqa: E402
from theory import NOTE_PC  # noqa: E402

MELODIC = ('melody', 'counter', 'lead')


def _tonic_pc(score):
    fp = score.get('fusion') or {}
    raw = fp.get('tonic') or (score.get('meta') or {}).get('tonic') or score.get('key', 'D')
    raw_root = str(raw).split()[0].replace('m', '').replace('minor', '').replace('major', '').capitalize()
    ENHARMONIC = {'DB': 'C#', 'EB': 'D#', 'FB': 'E', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#', 'CB': 'B'}
    root_name = ENHARMONIC.get(raw_root.upper(), raw_root)
    return NOTE_PC.get(root_name, 2)


def _melodic_tracks(score):
    return [t for t in score['tracks'] if t.get('role') in MELODIC and len(t.get('notes', [])) >= 4]


def _gaps(notes):
    ns = sorted(notes, key=lambda n: n['t'])
    return [b['t'] - (a['t'] + a['d']) for a, b in zip(ns, ns[1:])]


def check(score, req):
    rows = []

    def row(level, name, msg):
        rows.append((level, name, msg))

    # tempo
    lo, hi = req['tempo']
    bpm = score.get('bpm', 0)
    if lo > hi:
        row('WARN', 'tempo', f'the cultures\' tempo ranges do not overlap ({lo}-{hi}); the piece sits between them')
    elif not lo <= bpm <= hi:
        row('WARN', 'tempo', f'{bpm} bpm is outside the cultures\' range {lo}-{hi}')
    else:
        row('PASS', 'tempo', f'{bpm} bpm inside the cultures\' range {lo}-{hi}')

    # breath (ma, qi, the rest between phrases)
    need = req['breath_beats']
    if need > 0:
        best = 0.0
        for t in _melodic_tracks(score):
            g = _gaps(t['notes'])
            if g:
                best = max(best, max(g))
        if best >= need:
            row('PASS', 'breath', f'a rest of {best:.2f} beats sits between phrases (asked {need})')
        else:
            row('FAIL' if need >= 1.0 else 'WARN', 'breath',
                f'no rest of {need} beat(s) between phrases (longest {best:.2f}); the culture\'s silence is missing')

    # groove: off-beat accents for groove cultures
    if req['groove'] == 'offbeat':
        drums = [n for t in score['tracks'] if t.get('role') == 'drum' for n in t.get('notes', [])]
        if not drums:
            row('FAIL', 'groove', 'no percussion, but the culture is built on an off-beat groove')
        else:
            off = np.mean([abs(n['t'] - round(n['t'])) > 1e-3 for n in drums])
            if off >= 0.25:
                row('PASS', 'groove', f'{off:.0%} of percussion hits are off the beat')
            else:
                row('FAIL', 'groove', f'only {off:.0%} of percussion is off the beat; the groove sits on the grid')
    elif req['groove'] == 'cycle':
        drums = [t for t in score['tracks'] if t.get('role') == 'drum']
        row('PASS' if drums else 'WARN', 'groove', 'a repeating cycle is present' if drums else 'no cycle (tala/iqa) drum part')

    # call and response: two melodic voices that take turns
    if req['call_response']:
        mel = _melodic_tracks(score)
        by_name = {t['name']: t for t in mel}
        pair = [by_name[k] for k in ('lead', 'answer') if k in by_name]     # the call and its answer, when the score names them
        if len(pair) < 2:
            pair = mel[:2]
        if len(pair) < 2:
            row('FAIL', 'call_response', 'the culture answers a leader, but there are fewer than two melodic voices')
        else:
            mel = pair
            a, b = mel[0]['notes'], mel[1]['notes']
            span = lambda ns: [(n['t'], n['t'] + n['d']) for n in ns]        # noqa: E731
            sa, sb = span(a), span(b)
            dur_a = sum(e - s for s, e in sa)
            dur_b = sum(f - g for g, f in sb)
            clash = sum(min(e, f) - max(s, g) for s, e in sa for g, f in sb if min(e, f) > max(s, g))
            tot = max(dur_a + dur_b - clash, 1e-6)  # Union interval (Jaccard denominator)
            overlap_ratio = clash / tot
            if overlap_ratio < 0.35:
                row('PASS', 'call_response', f'{mel[0]["name"]} and {mel[1]["name"]} take turns ({overlap_ratio:.0%} overlap)')
            else:
                row('WARN', 'call_response', f'{mel[0]["name"]} and {mel[1]["name"]} overlap {overlap_ratio:.0%}: they play together, not in answer')

    # ornament: the notes between the notes (slides, short grace, microtone)
    if req['ornament']:
        mel = _melodic_tracks(score)
        allnotes = [n for t in mel for n in t['notes']]
        if not allnotes:
            row('FAIL', 'ornament', 'no melodic line to ornament')
        else:
            orn = np.mean([(n.get('gl', 0) != 0) or (n.get('c', 0) != 0) or n['d'] <= 0.25 for n in allnotes])
            if orn >= 0.05:
                row('PASS', 'ornament', f'{orn:.0%} of melodic notes are ornamented (slides, short grace, microtone)')
            else:
                row('FAIL', 'ornament', f'{orn:.0%} ornamented; the culture needs slides, grace or microtones')

    # cadence: phrases come home
    if req['cadence']:
        tonic = _tonic_pc(score)
        mel = _melodic_tracks(score)
        if mel:
            last = max(mel[0]['notes'], key=lambda n: n['t'] + n['d'])
            if last['p'] % 12 == tonic:
                row('PASS', 'cadence', 'the melody closes on the tonic')
            else:
                row('FAIL', 'cadence', f'the melody ends on pitch class {last["p"] % 12}, not the tonic {tonic}: no resolution')

    # instruments that read as another culture
    bad = sorted({t['instrument'] for t in score['tracks']} & set(req['avoid_instruments']))
    if bad:
        row('FAIL', 'instruments', f'{", ".join(bad)} read as another culture in this mix')
    else:
        row('PASS', 'instruments', 'no instrument from another culture\'s sound')
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('score')
    ap.add_argument('--culture', action='append', default=None, help='a culture name; repeat for a mix')
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--soul', default=None, help='a JSON file with a soul block that overrides the profiles')
    a = ap.parse_args()
    import cli_util
    cli_util.require_file(a.score, 'score')
    cli_util.require_file(a.soul, 'soul file')
    import presets
    presets.add_project(os.path.dirname(os.path.abspath(a.score)))
    score = json.load(open(a.score, encoding='utf-8'))
    cultures = a.culture or (score.get('fusion') or {}).get('cultures') or score.get('soul_cultures')
    if not cultures:
        print('soul_check: no culture named (use --culture, or a fusion score)')
        sys.exit(0)
    override = json.load(open(a.soul, encoding='utf-8')) if a.soul else None
    req = soul.merged(cultures, override)
    rows = check(score, req)
    print(f'soul check: {" + ".join(cultures)}  ({"; ".join(req["feel"][:4])})')
    for level, name, msg in rows:
        print(f'  [{level:4s}] {name:14s} {msg}')
    fails = sum(1 for r in rows if r[0] == 'FAIL')
    warns = sum(1 for r in rows if r[0] == 'WARN')
    print(f'result: {fails} FAIL, {warns} WARN')
    print('not checked by code: whether the performance moves a listener. Listen before release.')
    sys.exit(1 if fails or (a.strict and warns) else 0)


if __name__ == '__main__':
    main()
