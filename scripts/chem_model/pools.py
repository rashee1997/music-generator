# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_model.pools - the reaction kinetics: release, saturation, first-order clearance and depletion.

For every pool i at time t (docs/NEUROCHEMICAL-AFFECT-PLAN.md section 3.2):

    dP_i/dt = R_i(t) * A_i(t) - Vmax_i * P_i / (Km_i + P_i) - k_i * P_i
    dA_i/dt = (1 - A_i) / tau_rec_i - k_des_i * P_i * A_i
    R_i(t)  = sum_j w_ij * u_j(t)

`u_j` are elicitors in 0..1 that the pipeline already measures (a build, the approach to a declared arrival, Chew
tension, melodic information content, the ear model's roughness). The Michaelis-Menten term is the saturation that
stops a louder passage from earning unbounded reward; `k_des` is the adaptation that makes a second identical arrival
release less. That is the whole anti-cliche mechanism: the layer is never a reward function for "more impact".

Explicit Euler at the preset's `step_s` (0.25 s), which is small against every pool's time constant; `substeps`
halves the step so a test can check convergence against 8 Hz. Nothing here is measured neurochemistry - the pools are
inferred states, and their confidence tier is in the preset per pool.
"""
import numpy as np

import chem_model.config as config


def _array(u, name, n):
    """One elicitor as a float array of length n (zeros when the caller did not measure it)."""
    v = u.get(name)
    if v is None:
        return np.zeros(n)
    a = np.asarray(v, dtype=float)
    if a.ndim == 0:
        return np.full(n, float(a))
    if len(a) != n:
        raise ValueError(f'elicitor "{name}" has {len(a)} values, the grid has {n}')
    return np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)


def simulate(u, step_s, cfg, substeps=1):
    """Run every pool over the elicitor grid.

    Returns {'P': {pool: array}, 'A': {pool: array}, 'step_s': dt, 'substeps': n}. P is the released pool (0 at
    silence), A the availability that depletion spends (1 = rested). No pool is ever negative and A stays in 0..1.
    """
    names = list(config.POOLS)
    n = len(np.asarray(u.get('build', [0.0] * 1))) if u else 1
    for v in u.values():
        n = max(n, len(np.atleast_1d(np.asarray(v, dtype=float))))
    n = int(n)
    dt = float(step_s) / int(substeps)
    series = {name: _array(u, name, n) for name in config.ELICITORS}
    release = {}
    for pool in names:
        R = np.zeros(n)
        for f, w in cfg['weights'][pool].items():
            R += float(w) * series[f]
        release[pool] = R
    P = {pool: np.zeros(n) for pool in names}
    A = {pool: np.ones(n) for pool in names}
    for pool in names:
        c = cfg['pools'][pool]
        vmax, km, k, tau, k_des = (float(c['vmax']), float(c['km']), float(c['k']),
                                  float(c['tau_rec_s']), float(c['k_des']))
        p, a = 0.0, 1.0
        p_out, a_out = P[pool], A[pool]
        R = release[pool]
        for i in range(n):
            for _ in range(int(substeps)):
                p = p + dt * (R[i] * a - vmax * p / (km + max(p, 0.0)) - k * p)
                a = a + dt * ((1.0 - a) / tau - k_des * max(p, 0.0) * a)
                p = min(max(p, 0.0), vmax)     # the pool is reported on its own 0..vmax scale, which is 0..1 here
                a = min(max(a, 0.0), 1.0)
            p_out[i], a_out[i] = p, a
    return dict(P=P, A=A, step_s=dt, substeps=int(substeps))


def convergence(step_s, cfg, u, substeps=2):
    """Largest absolute difference between the preset's step and a step `substeps` times finer, per pool."""
    a = simulate(u, step_s, cfg)
    b = simulate(u, step_s, cfg, substeps=substeps)
    return {pool: float(np.max(np.abs(a['P'][pool] - b['P'][pool]))) for pool in config.POOLS}
