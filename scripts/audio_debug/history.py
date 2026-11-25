"""history.py - what has already been tried on this piece, so it is not tried again.

Every autopsy records the moves it recommends. Every render records what the gate then said. A lever that was tried
against a row and did not clear it is *burned* for that row: the solver zeroes its column and the report lists it,
which is what stops the same failed experiment from being proposed a fourth time.
"""
from __future__ import annotations

import datetime as _dt
import json
import os

FILE = 'debug_history.jsonl'


def path(project):
    return os.path.join(project, 'reports', FILE)


def load(project):
    out = []
    try:
        with open(path(project), encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def record(project, lever, row, delta, outcome, note='', **extra):
    """Append one attempt. `outcome` is 'cleared', 'better', 'no change', 'worse' or 'same'."""
    entry = dict(stamp=_dt.datetime.now().isoformat(timespec='seconds'), lever=lever, row=row,
                 delta=delta, outcome=outcome, note=note, **extra)
    os.makedirs(os.path.dirname(path(project)), exist_ok=True)
    with open(path(project), 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry) + '\n')
    return entry


# -- automatic bookkeeping ---------------------------------------------------------------------------------
# Recording an outcome by hand (`debug_audio.py --record`) was the only way a spent lever became "burned", so a
# proposal that was applied and did nothing was proposed again on the next failure. The engine now writes every move it
# recommends as a `proposed` entry with the lever's setting and the failing rows' safety at that moment; the next
# autopsy compares the lever's setting and the rows against it, and settles it as cleared / no change / worse.

def pending(entries):
    """Proposals that no later entry has settled, oldest first."""
    settled = {e.get('ref') for e in entries if e.get('ref')}
    return [e for e in entries if e.get('outcome') == 'proposed' and e.get('stamp') not in settled]


def propose(project, plan, levers, binding, case=None):
    """Append one `proposed` entry per recommended move. Returns the entries written."""
    from . import margins
    moves = dict(plan.clearing or plan.deltas or {})
    if not moves:
        return []
    by_id = {lv.id: lv for lv in levers}
    rows = {margins.row_key(r): round(margins.safety(r)[0], 4) for r in binding}
    out = []
    for lid, delta in moves.items():
        lv = by_id.get(lid)
        if lv is None:
            continue
        exp = next((e for e in getattr(plan, 'experiments', []) if lid in e['moves']
                    and abs(e['moves'][lid] - float(delta)) < 1e-9 and len(e['moves']) == len(moves)), None)
        entry = dict(stamp=_dt.datetime.now().isoformat(timespec='microseconds'), lever=lid, row=','.join(sorted(rows)),
                     delta=round(float(delta), 4), outcome='proposed', baseline=lv.current, rows=rows,
                     predicted=(exp or {}).get('value'), baseline_value=(exp or {}).get('baseline'),
                     stem=lv.stem, stem_hash=fingerprint(case, lv.stem) if (case is not None and lv.stem) else None,
                     note=f'proposed by the autopsy ({plan.status})')
        os.makedirs(os.path.dirname(path(project)), exist_ok=True)
        with open(path(project), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry) + '\n')
        out.append(entry)
    return out


def fingerprint(case, stem):
    """A hash of the newest processed copy of a stem, or None. Taken when a move is proposed and again when it is settled:
    a stem whose bytes did not change across an applied move was never reached by it."""
    import hashlib
    import numpy as np
    paths = case.stem_paths(stem)
    if not paths:
        return None
    try:
        a = np.load(paths[-1])
    except (OSError, ValueError):
        return None
    return hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


def _unchanged(case, stem, before):
    """True when the stem now holds exactly the bytes it held when the move was proposed."""
    if not before:
        return False
    now = fingerprint(case, stem)
    return now is not None and now == before


def settle(project, case, levers, binding):
    """Settle every pending proposal whose lever has since been moved; returns the outcomes recorded.

    A proposal counts as applied when the lever's setting moved by at least half of what was asked. Its outcome is read
    from the rows it was proposed for: `cleared` when none of them is failing now, `worse` when any is further from its
    limit, else `no change`. A proposal whose lever did not move stays pending, so a render that changed something else
    cannot burn it.
    """
    from . import margins
    if getattr(case, 'drift', None) or getattr(case, 'stale', False):
        return []      # the lever has been edited but the rows still describe the previous render: nothing to settle against
    entries = load(project)
    now = {margins.row_key(r): margins.safety(r)[0] for r in case.rows}
    by_id = {lv.id: lv for lv in levers}
    done = []
    for p in pending(entries):
        lv = by_id.get(p['lever'])
        if lv is None:
            continue
        moved = lv.current - float(p.get('baseline', lv.current))
        want = float(p.get('delta') or 0.0)
        if want == 0.0 or abs(moved) < 0.5 * abs(want) or moved * want < 0:
            continue
        keys = list((p.get('rows') or {}).keys())
        if not keys:
            continue
        if lv.stem and _unchanged(case, lv.stem, p.get('stem_hash')):
            # The lever was applied and the stem it addresses came out identical: nothing read the setting. That is not
            # "no change" (the move failed) but a lever that does not reach the signal, and it must not be proposed again.
            target = round(float(p.get('baseline', lv.current)) + want, 4)
            rec = record(project, p['lever'], p['row'], want, 'unreachable', target=target,
                         note=f'the processed stem "{lv.stem}" is identical before and after: the mixer never read this '
                              f'setting (check the inst_eq key against the track\'s instrument name)')
            with open(path(project), 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(dict(stamp=rec['stamp'], lever=p['lever'], row=p['row'], outcome='settled',
                                         ref=p['stamp'], target=target)) + '\n')
            done.append(rec)
            continue
        failing = [k for k in keys if now.get(k, float('inf')) < 0]
        worse = [k for k in keys if k in now and now[k] < float(p['rows'][k]) - 1e-9]
        better = [k for k in keys if k in now and now[k] > float(p['rows'][k]) + 1e-9]
        outcome = ('cleared' if not failing else 'worse' if worse else 'better' if better else 'no change')
        said = '' if p.get('predicted') is None else f"; the replay had predicted {p['predicted']} event(s)"
        target = round(float(p.get('baseline', lv.current)) + want, 4)
        rec = record(project, p['lever'], p['row'], want, outcome,
                     note='settled automatically against the next render' + said, target=target)
        rec['target'] = target
        with open(path(project), 'a', encoding='utf-8') as fh:       # the ref marks the proposal as settled
            fh.write(json.dumps(dict(stamp=rec['stamp'], lever=p['lever'], row=p['row'], outcome='settled',
                                     ref=p['stamp'], target=rec['target'])) + '\n')
        done.append(rec)
    return done


def calibration(project):
    """How often the engine's own predictions held: [(lever, predicted, outcome)] from settled proposals.

    A proposal records the value its replay predicted; settling records what the render said. The ratio of hits to
    misses is the false-proof rate of this piece's model, and the report prints it so a candidate is never presented
    with more confidence than its record earns.
    """
    entries = load(project)
    pred = {e['stamp']: e for e in entries if e.get('outcome') == 'proposed' and e.get('predicted') is not None}
    out = []
    for e in entries:
        if e.get('outcome') == 'settled' and e.get('ref') in pred:
            p = pred[e['ref']]
            res = next((x for x in entries if x.get('lever') == p['lever'] and x.get('stamp') == e['stamp']
                        and x.get('outcome') != 'settled'), None)
            out.append((p['lever'], p.get('predicted'), (res or {}).get('outcome', '?')))
    return out
