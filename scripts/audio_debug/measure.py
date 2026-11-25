"""measure.py - re-run the gate's own checker for a row whose verdict text lost its numbers.

A row's structured result (value, threshold, unit, the times of its events) is now written to
`presets/gate/data/rows.json`, but a render made before that file existed only has prose. For the discrete rows whose
events must be located anyway - an impulse, a clipped sample, a DC offset - the cheapest honest answer is to call the
same function the gate called, on the same master, and use its numbers. It costs a couple of seconds on one file, not
a render, and it is the gate's own arithmetic, not a second opinion.
"""
from __future__ import annotations

from . import margins

# row -> the gate_checks function that produces it
CHECKERS = {
    'clicks': 'check_clicks',
    'audio.clicks': 'check_clicks',
    'clipping': 'check_clipping',
    'clipped_samples': 'check_clipping',
    'master.dc': 'check_dc',
    'dc': 'check_dc',
}


def enrich(case, rows):
    """Fill value/threshold/times on event rows that have none. Returns the rows that were measured."""
    if getattr(case, 'stale', False):
        # The file on disk is a different render than the verdict: its impulses are real but they are not this row's.
        return []
    need = [r for r in rows if r['row'] in CHECKERS and (r.get('value') is None or not margins.events(r))]
    if not need or not case.master:
        return []
    try:
        import gate_audio
        import gate_checks
    except Exception:
        return []
    try:
        sig = gate_audio.load(case.master)
    except Exception:
        return []
    done, cache = [], {}
    for r in need:
        fn = CHECKERS[r['row']]
        if fn not in cache:
            cache[fn] = getattr(gate_checks, fn)(sig)
        res = cache[fn]
        r['value'] = float(res.get('value', 0.0))
        r['threshold'] = float(res.get('threshold', 0.0))
        r['unit'] = res.get('unit') or r.get('unit') or ''
        r.setdefault('raw', {})['worst_times_s'] = [round(float(t), 4) for t in (res.get('times') or [])][:8]
        r['raw']['remeasured'] = True
        r['detail'] = (r.get('detail') or '') + f' [re-measured: {res.get("detail", "")[:120]}]'
        done.append(r['row'])
    return done
