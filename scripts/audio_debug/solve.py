"""solve.py - the whole set of rows as one problem, and the pairs that cannot both be won.

Every binding row is a constraint on the safety `s_r` and every lever is a bounded variable. A first-order model
gives d s_r / d lever; the programme maximises the worst safety across all rows at once:

    maximise t
    subject to   s_r + sum_l A[r, l] * d_l >= t        for every judged row r
                 lo_l - x_l <= d_l <= hi_l - x_l        for every lever l

That single programme is the answer to whack-a-mole: if a solution exists it improves every row it touches and
degrades none past its limit, so the next render cannot trade one failure for another. When no solution exists, the
interesting object is not the attempt but the reason, so the solver also computes, for every lever, the interval of
moves that would satisfy each of its rows one at a time; an empty intersection names the rows that cannot both be
satisfied by that lever, with the interval that has no solution.

The coefficients are linearisations of the gate's own measurements (band energy shares, first-order placement
effects), not new renders. The report says so, and the pseudo-inverse re-solve after snapping keeps the plan honest
about rounding: a snapped move is re-evaluated, never assumed.
"""
from __future__ import annotations

import numpy as np

from . import margins


class Plan:
    def __init__(self, deltas=None, predicted=None, conflicts=(), closed=(), burned=(), notes=(), t=None,
                 status='ok'):
        self.deltas = deltas or {}          # lever id -> recommended move in the lever's unit
        self.predicted = predicted or {}    # row key -> (safety now, safety after)
        self.conflicts = list(conflicts)
        self.closed = list(closed)
        self.burned = list(burned)
        self.notes = list(notes)
        self.t = t
        self.status = status

    def as_dict(self):
        return dict(status=self.status, worst_safety=self.t, deltas=self.deltas,
                    predicted={k: list(v) for k, v in self.predicted.items()},
                    conflicts=self.conflicts, closed=self.closed, burned=self.burned, notes=self.notes)


def _burned(lever, key, history):
    """True when this exact lever was already tried for this row and did not clear it."""
    for h in history or ():
        if h.get('lever') == lever.id and h.get('row') and key.startswith(h['row']):
            if h.get('outcome') in ('no change', 'worse', 'same'):
                return True
    return False


def build(analysis, history=()):
    """Rows, levers, the sensitivity matrix and the current safety, in a stable order."""
    seen, row_keys = {}, []
    for r in analysis.rows:
        key = margins.row_key(r)
        if key in seen:
            continue
        s, sense, ss = margins.safety(r)
        if s == float('inf'):
            continue
        seen[key] = dict(row=r['row'], key=key, level=r.get('level'), safety=s, sense=sense, scale=ss,
                         stem=r.get('stem'))
        row_keys.append(key)
    levers = []
    for lv in analysis.levers:
        if lv.id not in [x.id for x in levers]:
            levers.append(lv)
    # A domain reports d value / d lever; the solver needs d safety / d lever, so each coefficient is signed by the
    # row's good direction and divided by the row's own tolerance. One conversion, in one place, so no module can
    # disagree about which way a row improves.
    A = np.zeros((len(row_keys), len(levers)))
    idx = {lv.id: j for j, lv in enumerate(levers)}
    sign = {k: (-1.0 if seen[k]['sense'] == 'max' else 1.0) for k in row_keys}
    for (key, lid), c in analysis.coefficients.items():
        if key in seen and lid in idx:
            i = row_keys.index(key)
            A[i, idx[lid]] = sign[key] * float(c) / (seen[key]['scale'] or 1.0)
    s = np.array([seen[k]['safety'] for k in row_keys], dtype=float)
    return seen, row_keys, levers, A, s


def plan(analysis, history=(), max_rows=None):
    seen, row_keys, levers, A, s = build(analysis, history)
    binding = [k for k in row_keys if seen[k]['level'] in ('FAIL', 'WARN')]

    # Burned levers: already spent on this row in an earlier attempt, with no gain. They stay in the system as
    # zeroed columns so the plan does not recommend a repeat, and so the report can name them.
    burned = []
    for j, lv in enumerate(levers):
        hits = [k for k in row_keys if _burned(lv, k, history)]
        if hits:
            A[:, j] = 0.0
            burned.append(dict(lever=lv.id, text=lv.text, rows=sorted({seen[k]['row'] for k in hits})))

    live = [j for j in range(len(levers)) if np.any(A[:, j] != 0.0)]
    dead = [j for j in range(len(levers)) if j not in live]
    closed = [seen[k]['row'] for k in row_keys if k in binding and not np.any(A[row_keys.index(k), :] != 0.0)]

    if not live or not binding:
        return Plan(predicted={k: (seen[k]['safety'], seen[k]['safety']) for k in row_keys}, closed=closed,
                    burned=burned, status='nothing to move' if binding else 'no binding row')

    # ---- the programme: maximise the worst safety over the judged rows ------------------------------------
    n, m = len(levers), len(row_keys)
    c = np.zeros(n + 1)
    c[-1] = -1.0
    c[:n] = 1e-4                                  # tie-break: the smallest total move
    A_ub = np.hstack([-A, np.ones((m, 1))])
    # A lever that moves no judged row is pinned: otherwise the tie-break walks it for no reason and the plan
    # recommends a change with no predicted effect.
    bounds = [((0.0, 0.0) if j in dead else (levers[j].lo - levers[j].current, levers[j].hi - levers[j].current))
              for j in range(n)] + [(None, None)]
    deltas = np.zeros(n)
    t = float(np.min(s)) if s.size else 0.0
    status = 'linear'
    try:
        from scipy.optimize import linprog
        res = linprog(c, A_ub=A_ub, b_ub=s, bounds=bounds, method='highs')
        if res.status == 0 and res.x is not None:
            deltas = np.asarray(res.x[:n], dtype=float)
            t = float(res.x[-1])
        else:
            status = 'greedy'                     # infeasible under the box: fall back to the best single moves
    except Exception:
        status = 'greedy'

    if status == 'greedy':
        deltas = _greedy(A, s, binding, row_keys, levers)

    moves = {levers[j].id: levers[j].snap(deltas[j]) for j in range(n) if abs(deltas[j]) > 1e-9}
    moves = {k: v for k, v in moves.items() if abs(v) > 1e-9}
    dvec = np.zeros(n)
    for j, lv in enumerate(levers):
        if lv.id in moves:
            dvec[j] = moves[lv.id]
    after = s + A @ dvec

    predicted = {k: (float(s[i]), float(after[i])) for i, k in enumerate(row_keys)}
    conflicts = _conflicts(seen, row_keys, levers, A, s, binding)
    notes = []
    # A solved programme can still end below zero when the rows it must not break have no lever of their own: the
    # honest verdict then is "this is the best admissible set, and it does not clear the row", not "solved".
    worst_after = min((after[row_keys.index(k)] for k in binding if k in row_keys), default=0.0)
    if moves and worst_after < 0:
        short = [seen[k]['row'] for k in binding if k in row_keys and after[row_keys.index(k)] < 0]
        status = 'partial'
        notes.append('no admissible combination clears ' + ', '.join(sorted(set(short)))
                     + f'; the best set leaves it at safety {worst_after:+.2f}. The rows that limit it have no lever '
                     'here - fix those first, or change the piece rather than the knob')
    if status == 'greedy':
        notes.append('the box-constrained programme is infeasible; the plan is the best single-move set, see conflicts')
    if not moves:
        notes.append('no admissible move improves the binding rows: every lever is burned, closed or already optimal')
    return Plan(deltas=moves, predicted=predicted, conflicts=conflicts, closed=closed, burned=burned,
                notes=notes, t=t, status=status)


def _greedy(A, s, binding, row_keys, levers):
    """One move at a time: take the lever with the best worst-case gain, then stop when nothing improves."""
    d = np.zeros(len(levers))
    for _ in range(4):
        best, best_j, best_d = 0.0, None, 0.0
        for j in range(len(levers)):
            if not np.any(A[:, j]):
                continue
            span = max(levers[j].hi - levers[j].current, levers[j].current - levers[j].lo)
            step = min(span, max(levers[j].step, span / 4))
            for sign in (1.0, -1.0):
                dd = sign * step
                cand = s + A[:, j] * (d[j] + dd)
                worst = min(cand[row_keys.index(k)] for k in binding)
                gain = worst - min(s[row_keys.index(k)] for k in binding)
                if gain > best + 1e-6:
                    best, best_j, best_d = gain, j, dd
        if best_j is None:
            break
        d[best_j] += best_d
    return d


def _conflicts(seen, row_keys, levers, A, s, binding):
    """Levers whose one-row intervals do not intersect: the arithmetic behind a whack-a-mole cycle."""
    out = []
    for j, lv in enumerate(levers):
        if not np.any(A[:, j]):
            continue
        lo, hi = -np.inf, np.inf
        rows = []
        for k in row_keys:
            i = row_keys.index(k)
            a = A[i, j]
            if a == 0:
                continue
            # interval of moves that makes this row pass on its own
            edge = -s[i] / a
            if a > 0:
                lo = max(lo, edge)
            else:
                hi = min(hi, edge)
            rows.append((seen[k]['row'], round(float(edge), 3), round(float(s[i]), 3)))
        box = (lv.lo - lv.current, lv.hi - lv.current)
        lo = max(lo, box[0])
        hi = min(hi, box[1])
        if rows and lo > hi + 1e-9:
            tight = sorted(rows, key=lambda t: abs(t[2]))[:3]
            out.append(dict(
                lever=lv.id, text=lv.text, unit=lv.unit,
                feasible=[round(float(lo), 3), round(float(hi), 3)], bounds=[round(box[0], 3), round(box[1], 3)],
                rows=[dict(row=r[0], needs=r[1], safety=r[2]) for r in tight],
                why=(f'{lv.text} cannot satisfy ' + ' and '.join(sorted({r[0] for r in rows}))
                     + ' at once: the moves that pass one row fail the other, and the bounds leave no value between')))
    return out


def apply_margins(analysis, moves):
    """What the snapped moves predict, recomputed from the same model (no second optimiser pass)."""
    seen, row_keys, levers, A, s = build(analysis)
    d = np.zeros(len(levers))
    for j, lv in enumerate(levers):
        d[j] = float(moves.get(lv.id, 0.0))
    after = s + A @ d
    return {k: (float(s[i]), float(after[i])) for i, k in enumerate(row_keys)}
