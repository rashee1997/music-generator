"""zplace.py - `spatial.z_separation` as the pair rule it is, solved exactly.

The autopsy used to price this row as "one degree of azimuth moves it one degree". That is wrong in the three ways that
make a placement fix come back:

  * It is a rule over pairs, not a number. Moving one part away from the part it fought can put it inside the zone of a
    third part that also holds the midrange, so the row fails again with a different name pair.
  * Height only counts where the mixer renders it. A staged elevation on a part with no binaural route is ignored by
    the gate, so a proposal to "add 20 degrees of elevation" does nothing until the route is on.
  * Anchors do not travel. Bass and drums sit on the floor at their own place in an immersive mix; a proposal that moves
    one of them is a proposal the mixer overrides.

The pair table comes from the gate itself (`quality_gate.z_pairs`, the same function the row reads), the rule is the
gate's (`overlap >= overlap_min and sep < min_sep and delev < min_elev`), and a candidate placement is verified by
re-applying that rule to every pair, so the result is exact for the rule and not a linearisation. What is not exact:
the overlap itself depends on level, and the table holds it fixed.
"""
from __future__ import annotations

import itertools
import math

AZ_STEP = 5.0               # degrees: the finest placement a person writes, and the grid the search walks (starting value)
AZ_SPAN = 60.0              # how far one part may be asked to move in azimuth (starting value, matches the lever span)
EL_STEP = 5.0
EL_RANGE = (-10.0, 45.0)    # heights the mixer's head model is specified for (starting value)
MIN_UNIQUE_DEG = 5.0        # two parts closer than this in angle share a spot, which the workflow forbids
ANCHOR_ROLES = ('bass', 'drum')


def _wrap(d):
    d = abs(float(d)) % 360.0
    return 360.0 - d if d > 180.0 else d


def table(case):
    """The gate's own pair table for this render, or None with the reason in the second slot."""
    if not case.score or not case.stem_names():
        return None, 'no score or no processed stems'
    try:
        import presets
        import quality_gate as qg
        import mixer
    except Exception as exc:
        return None, f'gate not importable ({type(exc).__name__})'
    saved = list(presets.PROJECT_ROOTS)
    state = mixer.STATE.get('processed')
    try:
        presets.reset_projects()
        presets.add_project(case.project)
        mixer.STATE['processed'] = None
        stems = {n: case.stem(n) for n in case.stem_names()}
        got = qg.z_pairs(case.score, stems)
        if got is None:
            return None, 'the profile does not judge spatial.z_separation, or fewer than two parts share the climax'
        got['fights'] = qg.z_fights(got)
        return got, ''
    except Exception as exc:
        return None, f'pair table failed ({type(exc).__name__}: {exc})'
    finally:
        presets.PROJECT_ROOTS[:] = saved
        mixer.STATE['processed'] = state


def _passes(p, az, el, rendered, params):
    """The gate's rule for one pair under a candidate placement."""
    daz = _wrap(az[p['a']] - az[p['b']])
    delev = abs(el[p['a']] - el[p['b']]) if (rendered[p['a']] and rendered[p['b']]) else 0.0
    sep = math.hypot(daz, delev)
    if p['overlap'] < params['overlap_min']:
        return True, sep, daz, delev
    return (sep >= params['min_sep'] or delev >= params['min_elev']), sep, daz, delev


def verify(tab, az, el, rendered=None):
    """Pairs that still fight under a placement (empty list means the row passes), by the gate's own rule."""
    params = tab['params']
    rendered = rendered or {n: v['rendered'] for n, v in tab['parts'].items()}
    return [p for p in tab['pairs'] if not _passes(p, az, el, rendered, params)[0]]


def _unique(az, el, moved, parts):
    """No moved part may land on another part's spot (angular distance under MIN_UNIQUE_DEG in both axes)."""
    for m in moved:
        for n in parts:
            if n == m:
                continue
            if _wrap(az[m] - az[n]) < MIN_UNIQUE_DEG and abs(el[m] - el[n]) < MIN_UNIQUE_DEG:
                return False
    return True


def candidates(name, part, params):
    """(azimuth, elevation) options for one part, nearest first, including 'stay'. Anchors only offer 'stay'."""
    if part['role'] in ANCHOR_ROLES:
        return [(part['az'], part['el'])]
    out = []
    n_az = int(AZ_SPAN // AZ_STEP)
    elevs = [part['el']]
    if part['rendered']:
        e = EL_RANGE[0]
        while e <= EL_RANGE[1] + 1e-9:
            if abs(e - part['el']) > 1e-9:
                elevs.append(e)
            e += EL_STEP
    for da in range(-n_az, n_az + 1):
        for el in elevs:
            out.append((part['az'] + da * AZ_STEP, el))
    out.sort(key=lambda c: abs(c[0] - part['az']) + 1.0 * abs(c[1] - part['el']))
    return out


def solve(tab, max_parts=2):
    """The smallest placement change that clears every pair, or why none exists.

    Tries one part, then two, among the parts that appear in a failing pair. Cost of a move is degrees of azimuth plus
    degrees of elevation. A solution must pass every pair in the table (not only the failing ones) and keep every moved
    part on a spot of its own. Returns dict(status, moves, remaining, parts_tried, anchors_blocked).
    """
    params = tab['params']
    parts = tab['parts']
    fights = tab['fights']
    if not fights:
        return dict(status='passes', moves={}, remaining=[], parts_tried=[], anchors_blocked=[])
    involved = []
    for p in fights:
        for n in (p['a'], p['b']):
            if n not in involved:
                involved.append(n)
    movable = [n for n in involved if parts[n]['role'] not in ANCHOR_ROLES]
    blocked = [n for n in involved if parts[n]['role'] in ANCHOR_ROLES]
    rendered = {n: v['rendered'] for n, v in parts.items()}
    base_az = {n: v['az'] for n, v in parts.items()}
    base_el = {n: v['el'] for n, v in parts.items()}
    cand = {n: candidates(n, parts[n], params) for n in movable}

    best = None
    for k in range(1, max_parts + 1):
        for group in itertools.combinations(movable, k):
            for combo in itertools.product(*[cand[n][:220] for n in group]):
                az, el = dict(base_az), dict(base_el)
                cost = 0.0
                for n, (a, e) in zip(group, combo):
                    az[n], el[n] = a, e
                    cost += abs(a - base_az[n]) + abs(e - base_el[n])
                if best is not None and cost >= best[0]:
                    continue
                if verify(tab, az, el, rendered):
                    continue
                if not _unique(az, el, group, parts):
                    continue
                moves = {n: dict(az=az[n], el=el[n], d_az=az[n] - base_az[n], d_el=el[n] - base_el[n])
                         for n in group if (az[n], el[n]) != (base_az[n], base_el[n])}
                best = (cost, moves)
        if best:
            break
    if best:
        return dict(status='solved', moves=best[1], remaining=[], parts_tried=movable, anchors_blocked=blocked, cost=best[0])
    # nothing passes by moving parts: report what is left under the best effort, and why
    return dict(status='unsolvable', moves={}, remaining=fights, parts_tried=movable, anchors_blocked=blocked)


def unrendered_height(tab):
    """Parts whose staged height the gate ignores because no binaural route renders it."""
    return sorted(n for n, v in tab['parts'].items() if not v['rendered'])


def describe(tab, sol):
    """Report lines for a z row: the failing pairs, the minimal placement, and the blocks."""
    p = tab['params']
    lines = []
    for q in tab['fights'][:4]:
        lines.append(f"pair {q['a']}/{q['b']}: band overlap {q['overlap']:.2f} (limit {p['overlap_min']:.2f}), "
                     f"{q['sep']:.0f} deg apart (az {q['daz']:.0f}, el {q['delev']:.0f}); needs {p['min_sep']:.0f} deg or "
                     f"{p['min_elev']:.0f} deg of height"
                     + ('' if q['heights'] else ' [height not rendered for one of them: set binaural]'))
    near = sorted((q for q in tab['pairs'] if q not in tab['fights'] and q['overlap'] >= p['overlap_min']),
                  key=lambda q: q['sep'])[:3]
    for q in near:
        lines.append(f"near miss {q['a']}/{q['b']}: overlap {q['overlap']:.2f}, {q['sep']:.0f} deg apart "
                     f"(limit {p['min_sep']:.0f}); a move that closes on it fails the row with a new name")
    if sol['status'] == 'solved':
        for n, m in sol['moves'].items():
            lines.append(f"smallest placement that clears every pair: {n} azimuth {m['d_az']:+.0f} deg, elevation "
                         f"{m['d_el']:+.0f} deg (verified against all {len(tab['pairs'])} pairs)")
    elif sol['status'] == 'unsolvable':
        lines.append('no placement of the movable parts clears every pair'
                     + (f"; {', '.join(sol['anchors_blocked'])} are anchors and do not travel" if sol['anchors_blocked'] else '')
                     + ': the overlap itself has to fall (a level, a register or a density change in the score), not the angle')
    return lines
