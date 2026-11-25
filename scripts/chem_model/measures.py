# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_model.measures - the numbers the chem.* rows print, and the 0..1 signature the connection rows compare.

Every observable is a quantity of the traced pool or of the grid, not a verdict: the rows compare it with their own
parameters, the profile may relax those with a measured reason, and nothing here can fail a piece. The signature is
each dimension divided by its preset anchor, so a mood target written as 0.7 means "about 70 % of the level the row's
own starting bar calls high" - not a physiological quantity, and not comparable between pieces.
"""
import numpy as np
from scipy.stats import spearmanr

import chem_model.config as config


def _clip01(v):
    return float(min(1.0, max(0.0, v)))


def _runs(flags):
    out, start = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - start))
            start = None
    return out


def stress(cort, times, cfg):
    m = cfg['measures']['stress']
    high = float(m['high_frac']) * float(cort.max())
    dt = float(times[1] - times[0]) if len(times) > 1 else 1.0
    settle_n = max(1, int(float(m['settle_s']) / dt))
    runs = _runs(cort > high) if high > 1e-9 else []
    unresolved, resolved = 0.0, 0
    for start, length in runs:
        peak = float(cort[start:start + length].max())
        after = cort[start + length:start + length + settle_n]
        settled = bool(after.size) and float(after.min()) <= float(m['settle_frac']) * peak
        if settled:
            resolved += 1
        else:
            unresolved += length * dt
    mean_load = float(np.trapezoid(cort, times) / max(times[-1] - times[0], 1e-6)) if len(times) > 1 else 0.0
    return dict(mean_load=mean_load,
                unresolved_s=unresolved,
                resolve_frac=(resolved / len(runs)) if runs else 1.0,
                mean=float(cort.mean()), peak=float(cort.max()))


def build(feats, pools, cfg, gp):
    da = pools['P']['DA_ant']
    times, step = feats['times'], feats['step_s']
    arrivals = feats['arrivals']
    if not arrivals:
        return dict(lead_s=0.0, rho=0.0, peak=float(da.max()) if len(da) else 0.0, at_s=None, declared=False,
                    event=False)
    hit = max(arrivals, key=lambda a: a['strength'])
    ta = float(hit['at_s'])
    lead_max = float(gp.param('chem.reward_build', 'min_lead_s')) * 5.0
    m = (times >= ta - lead_max) & (times <= ta)
    if m.sum() < 3:                       # an arrival at the very start: the whole piece is the lead-up
        m = np.ones(len(times), dtype=bool)
    seg = da[m] if m.any() else da[:1]
    peak = float(seg.max()) if len(seg) else 0.0
    floor = float(cfg['measures']['build']['min_event_strength']) if cfg else 0.0
    if float(hit['strength']) < floor:            # nothing measurable at the hit: no build to earn
        return dict(lead_s=0.0, rho=0.0, peak=peak, at_s=ta, declared=bool(hit['declared']), event=False)
    half = np.where(seg >= 0.5 * peak)[0] if peak > 1e-9 else np.zeros(0, dtype=int)
    lead = max(0.0, float(ta - float(times[m][half[0]]))) if len(half) else 0.0
    if len(seg) >= 3 and np.std(seg) > 1e-9:
        # does the anticipation rise *through* the lead-up, or appear at the hit?
        rho = float(spearmanr(np.arange(len(seg)), seg)[0])
    else:
        rho = 0.0
    return dict(lead_s=lead, rho=rho, peak=peak, at_s=ta, declared=bool(hit['declared']))


def arrival(feats, pools):
    con = pools['P']['DA_con']
    times = feats['times']
    i = int(np.argmax(con)) if len(con) else 0
    at = float(times[i]) if len(times) else 0.0
    nearest = min(feats['arrivals'], key=lambda a: abs(a['at_s'] - at)) if feats['arrivals'] else None
    declared = bool(nearest and nearest['declared'])
    return dict(peak=float(con[i]) if len(con) else 0.0, at_s=at,
                offset_s=(abs(nearest['at_s'] - at) if declared else None),
                contrast_db=(nearest.get('contrast_db') if nearest else None),
                declared=declared)


def recovery(feats, pools, cfg):
    """How far the piece comes down from its own peak: 0 when it has no peak to come down from."""
    tail = float(cfg['measures']['recovery']['tail_frac'])
    proxy = np.asarray(feats['proxy'], dtype=float)
    n = max(1, int(len(proxy) * tail))
    cort = pools['P']['CORT']
    drop, peak_i = 0.0, 0
    if len(proxy) > 2 and float(proxy.max() - proxy.min()) > 0.5:
        lo, hi = float(proxy.min()), float(proxy.max())
        pn = (proxy - lo) / (hi - lo)
        peak_i = int(np.argmax(pn))
        if peak_i < len(pn) - n:                     # a peak that is already in the tail is no come-down
            drop = _clip01(float(pn[peak_i]) - float(pn[-n:].mean()))
    return dict(drop_frac=drop, final_cort=float(cort[-n:].mean()) if len(cort) else 0.0,
                peak_at_s=float(feats['times'][peak_i]) if len(feats['times']) else 0.0,
                final_ne=float(pools['P']['NE'][-n:].mean()) if len(pools['P']['NE']) else 0.0)


def variety(feats, pools, cfg):
    v = cfg['measures']['variety']
    names = list(config.POOLS)
    traced = np.vstack([pools['P'][k] for k in names])
    warm = min(int(float(v['warmup_s']) / max(feats['step_s'], 1e-9)), max(traced.shape[1] - 2, 0))
    states = 0
    for row in traced:
        row = row[warm:] if warm else row
        if len(row) < 3 or float(row.max()) < float(v['min_level']):
            continue
        # a pool is a *state* only if it rises and comes back down; a monotone ramp out of its own zero is the model
        # warming up, and counting it would report every static pad as six states.
        rise = float(row.max() - row[0])
        fall = float(row.max() - row[-1])
        span = float(row.max() - row.min())
        if span >= float(v['range_frac']) * float(row.max()) and min(rise, fall) >= 0.5 * span:
            states += 1
    step_move = np.abs(np.diff(traced, axis=1)).sum(axis=0) if traced.shape[1] > 1 else np.zeros(1)
    flat = float(np.mean(step_move < float(v['flat_frac']) * float(step_move.mean()))) if step_move.mean() > 1e-12 else 1.0
    minutes = max(feats['duration_s'], float(v['min_window_s'])) / 60.0
    return dict(states=states, of=len(names), flat_share=flat,
                arrivals_per_min=len(feats['arrivals']) / minutes)


def observables(feats, pools, score, cfg, gp):
    out = dict(
        build=build(feats, pools, cfg, gp),
        arrival=arrival(feats, pools),
        stress=stress(pools['P']['CORT'], feats['times'], cfg),
        recovery=recovery(feats, pools, cfg),
        variety=variety(feats, pools, cfg),
        affiliation=dict(mean=float(pools['P']['OXT'].mean()), legato=float(np.mean(feats['u']['legato'])),
                         vocal=float(np.mean(feats['u']['vocal'])), figure=bool(feats['score']['has_figure'])),
        motor=dict(mean=float(pools['P']['END'].mean()), bsi=feats['bsi'],
                   pulse=float(np.mean(feats['u']['pulse'])) if len(feats['u']['pulse']) else 0.0),
        measured=dict(feats['measured']),
        arrivals=feats['arrivals'],
    )
    out['dims'] = dimensions(out, cfg, gp)
    return out


def dimensions(obs, cfg, gp=None):
    """The 0..1 signature the mood and genre rows compare: each dimension against its own preset anchor.

    The row thresholds are the gate profile's own parameters (`gp.param`), never a second copy of them, so relaxing a
    row in a profile also moves what its connection dimension counts as full marks.
    """
    if gp is None:
        import gate_profiles
        gp = gate_profiles.resolve({})
    a = cfg['anchors']
    bs, ar = obs['build'], obs['arrival']
    lead_ref = float(gp.param('chem.reward_build', 'min_lead_s'))
    peak_ref = float(gp.param('chem.reward_build', 'min_peak'))
    arr_ref = float(gp.param('chem.reward_arrival', 'min_peak'))
    off_ref = float(gp.param('chem.reward_arrival', 'max_offset_s'))
    con_ref = float(gp.param('chem.reward_arrival', 'min_contrast_db'))
    build_val = (0.5 * _clip01(max(bs['lead_s'], 0.0) / max(lead_ref, 1e-6))
                 + 0.25 * _clip01((bs['rho'] + 1.0) / 2.0)
                 + 0.25 * _clip01(bs['peak'] / max(peak_ref, 1e-6)))
    arr = [_clip01(ar['peak'] / max(arr_ref, 1e-6))]
    if ar['declared'] and ar['offset_s'] is not None:
        arr.append(_clip01(1.0 - float(ar['offset_s']) / max(off_ref, 1e-6)))
    if ar['contrast_db'] is not None:
        arr.append(_clip01(float(ar['contrast_db']) / max(con_ref, 1e-6)))
    return {
        'reward_build': _clip01(build_val / float(a['reward_build'])),
        'reward_arrival': _clip01(float(np.mean(arr)) / float(a['reward_arrival'])),
        'stress_load': _clip01(obs['stress']['mean'] / float(a['stress_load'])),
        'affiliation': _clip01(obs['affiliation']['mean'] / float(a['affiliation'])),
        'motor_drive': _clip01(obs['motor']['mean'] / float(a['motor_drive'])),
        'recovery': _clip01(obs['recovery']['drop_frac'] / float(a['recovery'])),
        'arc_variety': _clip01((obs['variety']['states'] / max(obs['variety']['of'], 1)) / float(a['arc_variety'])),
    }
