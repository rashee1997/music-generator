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
"""sound_fit.py - move a sound model toward what was measured in real recordings, with a bounded, seeded search.

    python3 scripts/sound_fit.py fit presets/sfx/tin_roof.json tin_roof_rain --project <dir> [--sweeps 3] [--seed 1] [--no-texture]
    python3 scripts/sound_fit.py fit presets/environments/roof.json rain_roof --project <dir> --layer 0

The preset (or a bare model JSON) names the parameters that may move in "free": {"voices.0.resonator.f1": [400, 2000], ...}
(each must be written in the model, with a [min, max]). References are read from <project>/reference/<slug>.json, made by
`ambience_reference.py measure`. The search is coordinate descent: every sweep tries each free parameter a step up and a step down,
keeps the change that lowers the distance, and halves the step. The seed, the render length and the number of sweeps are fixed, so
a run always gives the same answer. The original file is never edited: the result is written next to it as <name>_fit.json with the
distance before and after.

What this can and cannot do: it moves numbers to match measured spectrum, bands and texture statistics of the nearest real recording.
It cannot add structure the model does not have, and one recording is a weak anchor (the result says so).
"""
import argparse
import copy
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ambience_reference as ar
import sound_model as sm

SR = 44100


def _model_of(doc, layer):
    """(model dict, how to put it back) from a sfx preset, an environments preset layer, or a bare model."""
    if 'model' in doc:
        return doc['model'], lambda m: dict(doc, model=m)
    if 'layers' in doc:
        lyr = doc['layers'][layer]
        if lyr.get('primitive') != 'model_layer':
            raise ValueError(f'layer {layer} is "{lyr.get("primitive")}", not a model_layer; only model layers can be fitted')
        m = dict(seconds=float(lyr.get('seconds', 6.0)), voices=lyr['voices'], free=lyr.get('free', {}))

        def back(new):
            d = copy.deepcopy(doc)
            d['layers'][layer]['voices'] = new['voices']
            return d
        return m, back
    return doc, lambda m: m


def _score(model, refs, seed, seconds, texture):
    x = sm.render(model, SR, seed, seconds)
    if not np.isfinite(x).all() or np.abs(x).max() < 1e-9:
        return 1e9
    m = ar.measure_array(x, SR, texture=texture)
    return min(ar.metric_distance(m, r) for r in refs)


def fit(model, refs, free, seed=1, sweeps=3, seconds=4.0, texture=True, step0=0.25):
    """Coordinate descent over the free parameters. Returns (new_model, report)."""
    cur = copy.deepcopy(model)
    names = list(free)
    tex = texture and all(r.get('texture') for r in refs)
    best = _score(cur, refs, seed, seconds, tex)
    first, evals, step = best, 1, step0
    history = [round(best, 4)]
    for _ in range(sweeps):
        for path in names:
            lo, hi = free[path]
            for sgn in (+1, -1):
                moved = False
                while True:                                    # keep stepping the same way while it keeps improving
                    v0 = sm.get_path(cur, path)
                    v = v0 * math.exp(sgn * step) if lo > 0 else v0 + sgn * step * (hi - lo)
                    v = min(max(v, lo), hi)
                    if isinstance(v0, int) and not isinstance(v0, bool):
                        v = int(round(v))
                    if v == v0:
                        break
                    trial = copy.deepcopy(cur)
                    sm.set_path(trial, path, v)
                    if sm.problems(trial):
                        break
                    sc = _score(trial, refs, seed, seconds, tex)
                    evals += 1
                    if sc < best - 1e-9:
                        best, cur, moved = sc, trial, True
                    else:
                        break
                if moved:
                    break                                      # the other direction cannot also be better
        history.append(round(best, 4))
        step /= 2
    weak = len(refs) < 2
    return cur, dict(distance_before=round(first, 4), distance_after=round(best, 4), improved=bool(best < first - 1e-9), evaluations=evals,
                     sweeps=sweeps, seed=seed, render_seconds=seconds, texture_used=tex, history=history,
                     references=len(refs), weak_anchor=weak,
                     note='one recording is a weak anchor; measure at least two' if weak else 'fitted to the nearest of the references')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['fit'])
    ap.add_argument('file')
    ap.add_argument('slug')
    ap.add_argument('--project', required=True)
    ap.add_argument('--layer', type=int, default=0, help='environments preset: which layer (a model_layer)')
    ap.add_argument('--sweeps', type=int, default=3)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--seconds', type=float, default=4.0)
    ap.add_argument('--no-texture', action='store_true', help='fit on spectrum and bands only (about 5 times faster)')
    a = ap.parse_args()
    doc = json.load(open(a.file, encoding='utf-8'))
    model, back = _model_of(doc, a.layer)
    if doc.get('layers') and doc['layers'][a.layer].get('free') is not None:
        model['free'] = doc['layers'][a.layer]['free']
    bad = sm.problems(model)
    if bad:
        sys.exit('model problems:\n' + '\n'.join(bad))
    free = model.get('free') or {}
    if not free:
        sys.exit('nothing to fit: add "free": {"voices.0.resonator.f1": [min, max], ...} to the model')
    refs = ar.load_refs(a.project, a.slug)
    if not refs:
        sys.exit(f'no reference for "{a.slug}" in {a.project}/reference/ (run ambience_reference.py measure)')
    new, rep = fit(model, refs, free, a.seed, a.sweeps, a.seconds, not a.no_texture)
    out_doc = back(new)
    out_doc['fit'] = dict(rep, slug=a.slug, fitted_values={p: sm.get_path(new, p) for p in free})
    out = os.path.splitext(a.file)[0] + '_fit.json'
    json.dump(out_doc, open(out, 'w', encoding='utf-8'), indent=2)
    print(f'wrote {out}')
    print(f'distance {rep["distance_before"]} -> {rep["distance_after"]} in {rep["evaluations"]} renders ({"improved" if rep["improved"] else "NOT improved"}); {rep["note"]}')
    for p in free:
        print(f'  {p}: {sm.get_path(model, p)} -> {sm.get_path(new, p)}')


if __name__ == '__main__':
    main()
