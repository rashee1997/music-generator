"""spatial.py - distance, direction, immersion and width rows.

Angular separation, depth and the ratio of direct to reverberant energy are first-order in the placement the score
declares: a degree of azimuth moves a separation row by a degree, a metre of distance moves a depth row toward the
room. Those are the coefficients here, and the report labels them as linearisations rather than measurements.
"""
from __future__ import annotations

from .. import catalog, margins
from . import base

_DIRECT = ('spatial.az', 'spatial.elev', 'spatial.dist')


def analyse(case, rows, history=()):
    levers = catalog.spatial_levers(case, 'spatial')
    coef, notes = {}, []
    for r in rows:
        key = margins.row_key(r)
        name = (r['row'] or '').lower()
        for lv in levers:
            if lv.kind == 'az' and any(k in name for k in ('separation', 'azimuth', 'width', 'imm_kinematics')):
                coef[(key, lv.id)] = 1.0
            elif lv.kind == 'elev' and ('elevation' in name or 'z_separation' in name or 'height' in name):
                coef[(key, lv.id)] = 1.0
            elif lv.kind == 'dist' and any(k in name for k in ('depth', 'distance', 'z_separation', 'imm_clarity',
                                                               'low_fold', 'bass')):
                coef[(key, lv.id)] = 1.0
            elif lv.kind == 'send' and any(k in name for k in ('ambient', 'glue', 'clarity', 'low_fold', 'width',
                                                               'diffuse')):
                coef[(key, lv.id)] = 1.0
        if not any(k == key for k, _l in coef):
            notes.append(f"{r['row']}: no placement lever is first-order on this row, so it is closed "
                         f"(the row is a property of the room or the HRTF, not of a knob)")
    experiments = []
    for r in rows:
        if (r['row'] or '') == 'spatial.z_separation' and r.get('level') in ('FAIL', 'WARN'):
            _z_rows(case, r, levers, coef, notes, experiments)
    return base.Analysis(rows=rows, levers=levers, coefficients=coef, notes=notes,
                         measured=[r['row'] for r in rows], experiments=experiments)


def _z_rows(case, r, levers, coef, notes, experiments):
    """Solve the pair rule exactly instead of pricing it as one degree per degree."""
    from .. import zplace
    key = margins.row_key(r)
    tab, why = zplace.table(case)
    if tab is None:
        notes.append(f"spatial.z_separation: pair table unavailable ({why}); the linear placement model is used")
        return
    sol = zplace.solve(tab)
    for line in zplace.describe(tab, sol):
        notes.append('spatial.z_separation: ' + line)
    r['raw']['z_pairs'] = [dict(a=q['a'], b=q['b'], overlap=round(q['overlap'], 3), sep=round(q['sep'], 1))
                           for q in tab['fights']]
    hidden = zplace.unrendered_height(tab)
    if hidden and any(q['heights'] is False for q in tab['fights']):
        notes.append('spatial.z_separation: height is not rendered for ' + ', '.join(hidden) + '; a staged elevation does '
                     'nothing for them until the part has a binaural route')
    # The linear model said 1 degree per degree for every part; once the pair rule is solved it is only misleading.
    for lv in levers:
        coef[(key, lv.id)] = 0.0
    if sol['status'] == 'solved' and sol['moves']:
        moves = {}
        for n, m in sol['moves'].items():
            if abs(m['d_az']) > 1e-9:
                moves[f'spatial.{n}.az'] = m['d_az']
            if abs(m['d_el']) > 1e-9:
                moves[f'spatial.{n}.elev'] = m['d_el']
        have = {lv.id for lv in levers}
        for lid, d in moves.items():
            if lid not in have:                 # a part with no declared spot still has one in its preset: offer the lever
                kind = 'az' if lid.endswith('.az') else 'elev'
                stem = lid.split('.')[1]
                part = tab['parts'][stem]
                cur = part['az'] if kind == 'az' else part['el']
                levers.append(base.Lever(lid, 'spatial', kind, cur, cur - 60.0, cur + 60.0, 5.0, 'deg',
                                         f'{stem} {kind}', stem=stem, burns=('spatial.', 'imm.')))
        experiments.append(dict(row=r['row'], key=key, kind='placement', value=0, baseline=len(tab['fights']),
                                moves=moves, times=[], verdict='clears'))
