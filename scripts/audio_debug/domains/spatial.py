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
    return base.Analysis(rows=rows, levers=levers, coefficients=coef, notes=notes,
                         measured=[r['row'] for r in rows])
