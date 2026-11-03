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
"""vegetation.py - leaves and branches as structures moved by air.

Foliage is not a filtered-noise swell with a sine on it. It is a large number of light, stiff, damped plates being
pushed by turbulence until adjacent leaves touch. The sound is those contacts: short, high, dense, and *statistically*
following the gust rather than being modulated by an LFO.

    leaf_events(seconds, flow_speed, leaf_count) -> [(time, amplitude, size)]
    branch_motion(seconds, flow_speed)           -> (displacement, contact_rate)

What is not modelled and is said plainly: the aerodynamics of an individual leaf (flutter instability, vortex
shedding at the tip) and the acoustics of a canopy (scattering, absorption over many leaves) are beyond this module.
A canopy's *propagation* is handled in propagate.py as absorption, which is defensible; the leaf-level flutter is a
statistical surrogate, and it is labelled as one.
"""
import numpy as np


def gust_envelope(seconds, sr, rng, corner_hz=0.15, intensity=0.35):
    """The turbulence that drives everything here: -5/3 above the corner, clipped positive."""
    from . import excite as _ex
    n = max(1, int(seconds * sr))
    return _ex.kaimal(n, sr, rng, corner_hz=corner_hz, intensity=intensity)


def leaf_events(seconds, flow_speed=3.0, leaf_count=4000.0, rng=None, gust=None):
    """Leaf-to-leaf contacts: arrival times, amplitudes and relative leaf sizes.

    The contact rate rises roughly with the square of the flow speed (aerodynamic pressure ~ v^2) and with the number
    of leaves; amplitudes follow the local gust, so a lull really is quiet and a gust really is dense. Sizes are drawn
    per event, because a bush has small leaves and big leaves and they sound different.
    """
    rng = rng or np.random.default_rng(0)
    v = max(float(flow_speed), 0.05)
    rate = 0.02 * leaf_count * (v / 3.0) ** 2           # contacts per second
    n_est = max(1, int(seconds * rate * 1.4) + 8)
    gaps = rng.exponential(1.0 / max(rate, 0.01), n_est)
    times = np.cumsum(gaps)
    times = times[times < seconds]
    if times.size == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    amps = 0.35 + 0.65 * np.abs(rng.standard_normal(times.size))
    if gust is not None and len(gust):
        idx = np.clip((times * (len(gust) / max(seconds, 1e-9))).astype(int), 0, len(gust) - 1)
        amps = amps * np.clip(gust[idx], 0.05, 2.5)
    sizes = np.exp(0.4 * rng.standard_normal(times.size))
    return times, np.clip(amps, 0.05, 2.0), np.clip(sizes, 0.2, 3.0)


def branch_motion(seconds, sr, flow_speed=4.0, stiffness=1.0, rng=None):
    """Bending displacement of a branch and the rate at which its leaves and twigs make contact.

    Displacement is the filtered gust (a branch is a low-pass on turbulence); the contact rate follows |velocity| of
    the branch, which is the derivative of that displacement, so contacts concentrate where the branch moves fastest.
    """
    rng = rng or np.random.default_rng(0)
    n = max(1, int(seconds * sr))
    g = gust_envelope(seconds, sr, rng)
    k = max(2, int(0.12 * sr / max(stiffness, 0.05)))
    disp = np.convolve(g, np.ones(k) / k, 'same')
    disp = (disp - disp.mean()) * (flow_speed / 4.0)
    vel = np.abs(np.diff(disp, prepend=disp[0])) * sr
    return disp, np.clip(vel / (vel.max() + 1e-9), 0.0, 1.0)


def failure_stages(material, energy_j=1.0, rng=None):
    """The ordered stages of a branch failing, as named events a scene can switch on or off.

    Returned as data, not rendered here: (stage, offset_s, note). A scene decides which stages it wants; nothing is
    mandatory, which is what lets the same code make a twig snap and a whole limb come down.
    """
    rng = rng or np.random.default_rng(0)
    from . import fracture as _fr
    brittle = material.get('family') in ('brittle', 'metal')
    cracks = _fr.crack_train(material, energy_j, rng, brittle=False)
    frags = _fr.fragments(material, energy_j, rng, brittle=False)
    out = [('stress', 0.0, 'strain builds; creak events, not sound yet')]
    if cracks:
        first = cracks[0][0]
        out.append(('initiation', float(first), 'first fibres fail'))
        out.append(('failure', float(max(c[0] for c in cracks)), 'main structural break'))
    out.append(('fragments', float(frags[0][1]) if frags else 0.05, 'pieces separate and fall'))
    out.append(('settle', float(frags[-1][1]) + 0.4 if frags else 0.5, 'debris lands and stops'))
    return out
