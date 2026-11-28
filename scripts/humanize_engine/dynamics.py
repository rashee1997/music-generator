# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Dynamics: every velocity decision of one line, in one place.

Metric accent, the phrase arch, the pitch contour, fast runs, automatic chord voicing, KTH tonal
charge and the 1/f velocity wander. The stage reads the score's velocities (`v_in`) and returns the
played ones; it never changes an onset.
"""
import numpy as np

from .form import _beat_accent, _vel127
from .noise import _fractal_noise


def shape_velocity(ns, p, v_in, rd, c, base_role, is_drum, phrases, clusters, ts, rng, frac, n, fig_roles,
                   step_beats=1.0):
    """The velocity of every note, before KTH charges and the expectation coupling."""
    v = v_in.copy()
    upbeat = bool(c.get('upbeat', False) or c.get('upbeats', False))
    acc = np.array([_beat_accent(nt['t'], ts, upbeat=upbeat) for nt in ns])
    v += rd['vel'] + float(c.get('vel_bias', 0.0))
    v += c['accent'] * (acc - 0.35) * 9.0                          # downbeats stronger
    arch_amp = float(c.get('vel_arch', 7.0))
    for k, idx in phrases.items():                                # phrase arch + pitch-contour loudness
        m = len(idx)
        x = np.linspace(0, 1, m) if m > 1 else np.array([0.5])
        shape = np.sin(np.pi * x) - 0.5
        # The figure swells to its middle; a counter-line answers softer in the middle; beds and drums get no arch.
        # How far it swells follows the level the score wrote for that phrase. One fixed +-7 units on every phrase
        # of every piece is a mannerism rather than a performance: it made a written pp and a written ff arch by the
        # same amount, and left the rendered dynamic range below every measured corpus value.
        if base_role in fig_roles or base_role == 'counter':
            lvl = float(np.clip(float(v_in[idx].mean()) / 90.0, 0.45, 1.35))
        if base_role in fig_roles:
            v[idx] += arch_amp * lvl * shape
        elif base_role == 'counter':
            v[idx] -= 0.43 * arch_amp * lvl * shape        # 3/7 of the figure's arch, at the same level scale
        if m > 2:
            pz = (p[idx] - p[idx].mean()) / (p[idx].std() + 1e-6)
            v[idx] += 2.0 * np.clip(pz, -1.5, 1.5)             # higher notes a little louder
        if base_role in fig_roles:
            v[idx[-1]] -= 6.0                                  # last note of a phrase relaxes
    # fast runs (taans, scale runs, 16th arpeggios): a run of 4+ short notes, each within half a beat of the last,
    # is shaped as a run. Every group of four starts stronger (the taan's sam-like accent); the run swells to its
    # middle and lets go. Without this a run is one flat level, because off-beat 16ths have metric weight 0.
    if not is_drum:
        runs, cur = [], []
        for i in range(n):
            if ns[i]['d'] > 0.5:
                # flush first: a long note between two short runs used to leave `cur` open, merging runs that a rest
                # or a held note separates
                if len(cur) >= 4:
                    runs.append(cur)
                cur = []
                continue
            gap_i = ns[i]['t'] - ns[cur[-1]]['t'] if cur else 0.0
            if cur and 0.01 < gap_i <= 0.5 + 1e-6:
                cur.append(i)
            else:
                if len(cur) >= 4:
                    runs.append(cur)
                cur = [i]
        if len(cur) >= 4:
            runs.append(cur)
        # The run's shape scales with the arch around it, level included: a group-start accent held at 5.0 while the
        # arch grows is a detail the arch cancels, and the group start stops reading as the loudest note of its group.
        k = (arch_amp / 7.0) * float(np.clip(float(v_in.mean()) / 90.0, 0.45, 1.35))
        for run in runs:
            for pos, i in enumerate(run):
                v[i] += k * (5.0 if pos % 4 == 0 else (1.0 if pos % 4 == 2 else -2.0))
            v[run] += k * 4.0 * (np.sin(np.pi * np.linspace(0, 1, len(run))) - 0.5)
            # directional swell: an ascending run crescendos, a descending run decrescendos; the peak note leans forward
            pr = p[run]
            sgn = 1.0 if pr[-1] >= pr[0] else -1.0
            v[run] += k * 5.0 * sgn * np.linspace(-0.5, 0.5, len(run))
            v[run[int(np.argmax(pr))]] += k * 3.0
    vs = c['vel_sigma']
    v += _fractal_noise(rng, n, beta=float(c.get('fractal_beta', 0.85)), fc=step_beats / 3.0) * vs * 0.6 \
        + rng.standard_normal(n) * vs * 0.6
    vtc = float(c.get('vel_time_couple', 0.0))
    if vtc > 0 and is_drum and vs:
        # on percussion the amplitude and the microtiming share their long-range correlation (Rasanen et al. 2015)
        v += vtc * vs * np.clip(frac, -2.0, 2.0)

    # automatic chord voicing (Goebl 2001): a score that wrote one velocity for every chord tone gets the top voice
    # lifted, the inner voices tucked back and the bass anchored. Uses the input velocities, so shaped scores are left alone.
    if base_role in ('chord', 'pad', 'arp', 'texture'):
        for cl in clusters:
            if len(cl) < 3 or v_in[cl].std() >= 1.5:
                continue
            order = sorted(cl, key=lambda j: ns[j]['p'])
            v[order[0]] += 2.0
            for j in order[1:-1]:
                v[j] -= 3.0
            v[order[-1]] += 5.0
    return v, acc
