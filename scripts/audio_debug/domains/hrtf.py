"""hrtf.py - the binaural rows: interaural cues, externalisation, mono fold on headphones.

An HRTF is a fixed dataset, so most cue errors are closed: the only first-order lever a score has over them is where
a source sits (elevation for the pinna cues, distance for externalisation). The module says which rows are closed and
why, so a cue mismatch is never "fixed" by nudging an unrelated knob.
"""
from __future__ import annotations

from .. import catalog, margins
from . import base


def analyse(case, rows, history=()):
    levers = catalog.spatial_levers(case, 'hrtf')
    coef, notes = {}, []
    hrtf_cfg = (case.mix or {}).get('immersive') or {}
    dataset = hrtf_cfg.get('hrtf') or hrtf_cfg.get('dataset') or 'the project HRTF'
    for r in rows:
        key = margins.row_key(r)
        name = (r['row'] or '').lower()
        for lv in levers:
            if lv.kind == 'elev' and ('cue' in name or 'elevation' in name or 'external' in name):
                coef[(key, lv.id)] = 1.0
            elif lv.kind == 'dist' and ('external' in name or 'distance' in name):
                coef[(key, lv.id)] = 1.0
        if not any(k == key for k, _l in coef):
            notes.append(f"{r['row']} is closed: {dataset} sets this cue and no preset lever changes the filter "
                         f"itself, only where a source sits")
    return base.Analysis(rows=rows, levers=levers, coefficients=coef, notes=notes,
                         measured=[r['row'] for r in rows])
