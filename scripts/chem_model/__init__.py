# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_model - the inferred-neurochemical layer the chem.* gate rows read.

One call runs the whole layer:

    import chem_model
    rep = chem_model.evaluate(score, path, sheet, summary, gp)
    rep['observables'], rep['dims'], rep['mood'], rep['genre']

`path` may be None: the score-side elicitors (expectation, tension, density, legato, consonant harmony) then carry the
model alone and every audio input is reported unmeasured. `summary` is the virtual ear's mono summary
(`ear_rows.summary_for`), which is where roughness and fatigue come from.

This is not a measurement of a molecule. It integrates elicitors the pipeline already has into seven inferred pools
(chem/model.json), compares their arc with what the piece's own mood and genre ask for (chem/moods.json,
chem/genres.json), and reports it as advisory rows. docs/NEUROCHEMICAL-AFFECT-PLAN.md has the evidence, the model and
the promotion rule; the shorter statement is that a chem.* row may warn and may never fail.
"""
from . import config, features, measures, pools, targets

ROW_IDS = ('chem.model', 'chem.reward_build', 'chem.reward_arrival', 'chem.stress_load', 'chem.affiliation',
           'chem.motor_drive', 'chem.recovery', 'chem.arc_variety', 'chem.mood_connection', 'chem.genre_connection')


def evaluate(score, path=None, sheet=None, summary=None, gp=None, step_s=None):
    """The whole layer for one piece: features, traced pools, observables, the 0..1 signature and the two targets."""
    cfg = config.model()
    if gp is None:
        import gate_profiles
        gp = gate_profiles.resolve(score)
    feats = features.build(score, path, sheet, summary, cfg, step_s)
    traced = pools.simulate(feats['u'], feats['step_s'], cfg)
    obs = measures.observables(feats, traced, score, cfg, gp)
    return dict(step_s=feats['step_s'], times=feats['times'], features=feats, pools=traced, observables=obs,
                dims=obs['dims'], mood=targets.mood_target(sheet, score), genre=targets.genre_target(score),
                model=cfg)


def signature_lines(rep):
    """Human-readable lines for a report: every pool's start/peak/end, then the signature against the two targets."""
    times = rep['times']
    out = []
    for pool in config.POOLS:
        v = rep['pools']['P'][pool]
        if not len(v):
            continue
        i = int(v.argmax()) if hasattr(v, 'argmax') else 0
        out.append(f'{pool:7s} tier {rep["model"]["pools"][pool]["tier"]}  start {v[0]:.2f}  peak {v[i]:.2f} '
                   f'at {times[i]:.1f} s  end {v[-1]:.2f}')
    for d in config.DIMENSIONS:
        out.append(f'{d:15s} {rep["dims"][d]:.2f}')
    return out
