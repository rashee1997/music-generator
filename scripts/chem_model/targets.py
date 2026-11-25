# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_model.targets - what the piece's own mood and genre ask of its chemistry.

Both are JSON, so a new mood or a new genre is a preset edit and not a code change:

  * a mood resolves through the intent vocabulary (scripts/intent.py, references/data/presets/intent/), and its target
    is built from its own valence/arousal coordinates by the axis shifts in chem/moods.json, with a per-mood override
    only where two axes plainly fail (grief wants affiliation a low-arousal/negative-valence point does not reach);
  * a genre maps to a family in chem/genres.json, and the family holds the constraints that family is defined by.

Neither is a measurement. They say what a piece of that kind should contain - the layer still cannot say a listener
will feel anything (5-10 % of listeners are music-anhedonic, Mas-Herrero 2014).
"""
import numpy as np

import chem_model.config as config
import intent
import presets


def _coords():
    return (presets.load('intent').get('valence_arousal') or {}).get('emotions') or {}


def mood_target(sheet, score):
    """{'words': [...], 'valence', 'arousal', 'target': {dim: 0..1}, 'known': bool, 'why': str}."""
    cfg = config.moods()
    words = []
    for w in ((sheet or {}).get('intent') or {}).get('emotions') or []:
        words.append(str(w))
    meta = score.get('meta') or {}
    if meta.get('emotion'):
        words.append(str(meta['emotion']))
    if not words and score.get('emotion'):
        words.append(str(score['emotion']))
    ids, coords = [], _coords()
    for w in words:
        try:
            for kind, cid in intent.resolve_word(w):
                if kind == 'emotions' and cid in coords and cid not in ids:
                    ids.append(cid)
        except Exception:
            continue
    if not ids:
        return dict(words=words, ids=[], valence=None, arousal=None, target={}, known=False,
                    why='no mood word in the sheet or the score resolves to an intent emotion')
    ids = ids[:int(cfg['max_words'])]
    v = float(np.mean([float(coords[i]['valence']) for i in ids]))
    a = float(np.mean([float(coords[i]['arousal']) for i in ids]))
    t = {d: float(cfg['base']) for d in config.DIMENSIONS}
    for axis, coord in (('valence', v), ('arousal', a)):
        for dim, shift in cfg['axes'][axis]['shift'].items():
            t[dim] += coord * float(shift)
    applied = []
    for cid in ids:
        for dim, val in (cfg['overrides'].get(cid) or {}).items():
            if dim == 'why':
                continue
            t[dim] = float(val)
            applied.append(f'{cid}.{dim}')
    t = {d: float(min(1.0, max(0.0, x))) for d, x in t.items()}
    return dict(words=words, ids=ids, valence=v, arousal=a, target=t, known=True, applied=applied,
                excess_weight=float(cfg['excess_weight']),
                why=f'valence {v:+.2f} / arousal {a:+.2f} from the intent coordinates'
                     + (f', overridden by {", ".join(applied)}' if applied else ''))


def genre_of(score):
    meta = score.get('meta') or {}
    g = meta.get('genre') or score.get('genre') or ''
    if isinstance(g, (list, tuple)):
        g = g[0] if g else ''
    return str(g).strip().lower().replace(' ', '_').replace('-', '_')


def genre_target(score):
    """{'genre', 'family', 'constraints': {dim: {'min'|'max': float}}, 'known': bool, 'why'}."""
    cfg = config.genres()
    g = genre_of(score)
    fam = cfg['genres'].get(g) or cfg['aliases'].get(g) or 'default'
    fam_cfg = cfg['families'][fam]
    cons = {d: {k: float(x) for k, x in lim.items()} for d, lim in fam_cfg.items() if d != 'why'}
    return dict(genre=g, family=fam, constraints=cons, known=fam != 'default',
                why=str(fam_cfg.get('why') or 'no family constraint'), tolerance=float(cfg['tolerance']))


def distance(measured, target, excess_weight=0.5):
    """(mean distance, [(dim, got, want, weighted delta)]): a shortfall counts fully, an excess `excess_weight`."""
    if not target:
        return None, []
    diffs = []
    for d in config.DIMENSIONS:
        if d not in target:
            continue
        got, want = float(measured.get(d, 0.0)), float(target[d])
        delta = got - want
        diffs.append((d, got, want, delta if delta < 0 else delta * float(excess_weight)))
    if not diffs:
        return None, []
    return float(np.mean([abs(x[3]) for x in diffs])), diffs


def breaches(measured, target):
    """[(dim, got, kind, limit)] where a family constraint is missed by more than the preset's tolerance."""
    if not target:
        return []
    tol = float(target.get('tolerance') or 0.0)
    out = []
    for dim, lim in (target.get('constraints') or {}).items():
        got = float(measured.get(dim, 0.0))
        if 'min' in lim and got < lim['min'] - tol:
            out.append((dim, got, 'min', lim['min']))
        if 'max' in lim and got > lim['max'] + tol:
            out.append((dim, got, 'max', lim['max']))
    return out
