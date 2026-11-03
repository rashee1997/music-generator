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
"""gait.py - locomotion as a gait cycle, not a footstep function.

A footstep is not a thump with a surface switch. It is an alternating contact whose force follows a ground reaction
force (GRF) curve, from the heel or the forefoot, carrying body weight, at a cadence, on a surface whose material
decides the rest. Turchet, Serafin, Dimitrov and Nordahl (DAFx-10) build footsteps exactly this way: simulate the
ground reaction force, then the contact of the sole and the ground; the paper is the reference for the shape.

So there is no `footstep(surface)` here. There is a gait, and a surface material, and the sound of gravel, sand, wood
and wet grass all fall out of the material model plus the granular/contact excitation.

    steps(seconds, cadence_spm)      -> [ {t, foot, phase, velocity, weight, heel} ]
    grf(n, sr, peak, style)          -> the force envelope of one contact

Cadence 100-120 steps/min is a walk, 150-180 a run. Stride length follows speed, so a faster gait lands harder: that
coupling is in `velocity`, and everything downstream sees it.
"""
import numpy as np

WALK_RUN = 150.0        # steps per minute above which the gait is a run (heel strike gives way to forefoot)


def is_running(cadence_spm):
    return float(cadence_spm) >= WALK_RUN


def steps(seconds, cadence_spm=112.0, rng=None, start_foot='left', jitter=0.02):
    """Contact events of a walk or run: time, which foot, heel or forefoot, foot speed, and share of body weight.

    Left and right alternate strictly; the cadence jitters by `jitter` (a metronome is not a person). A run has a
    flight phase, so its contacts are shorter and land with more foot speed.
    """
    rng = rng or np.random.default_rng(0)
    period = 60.0 / max(float(cadence_spm), 1.0)
    run = is_running(cadence_spm)
    out = []
    t = 0.0
    foot = start_foot
    while t < seconds:
        speed = (2.6 if run else 1.4) * (1.0 + 0.12 * rng.standard_normal())
        out.append(dict(t=float(t), foot=foot,
                        phase='forefoot' if (run or rng.random() < 0.35) else 'heel',
                        velocity=float(np.clip(abs(speed), 0.3, 6.0)),
                        weight=float(np.clip(1.0 + 0.08 * rng.standard_normal(), 0.8, 1.2)),
                        contact_s=float(0.16 if run else 0.28)))
        t += period * (1.0 + jitter * rng.standard_normal())
        foot = 'right' if foot == 'left' else 'left'
    return out


def grf(n, sr=44100, peak=800.0, style='walk', heel=False):
    """Ground reaction force of one contact, N, as an N-long envelope.

    Walk: a heel-strike spike, a dip, then the push-off peak (two humps). Run: one broad peak, no spike. The shape
    matters because it decides how the sole and the ground are loaded, which is what a listener recognises.
    """
    n = max(2, int(n))
    t = np.arange(n) / sr
    dur = n / sr
    x = t / max(dur, 1e-9)
    if style == 'run':
        env = np.sin(np.pi * np.clip(x, 0, 1)) ** 1.4
    else:
        strike = np.exp(-((x - 0.06) / 0.05) ** 2) * (0.65 if heel else 0.35)
        push = np.exp(-((x - 0.55) / 0.16) ** 2)
        env = strike + push
        env[:2] = 0.0
    return peak * np.clip(env, 0.0, None)


def body_sway(seconds, sr=44100, cadence_spm=112.0, depth=0.06):
    """Slow vertical body movement at twice the step rate: a walk is not a static head."""
    n = max(1, int(seconds * sr))
    t = np.arange(n) / sr
    return 1.0 + depth * np.sin(2 * np.pi * (2.0 * cadence_spm / 60.0) * t)
