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
"""fracture.py - structural failure, brittle and fibrous, as data.

A break is not one noise burst. It is a sequence: stress builds, cracks initiate, energy releases as a train of
impulses, the object comes apart into fragments that then fall, hit things and settle. Zheng and James (SIGGRAPH 2010)
model exactly this and are the reference for the shape of the event graph: a stress solver resolves near-audio-rate
fracture events, an energy-based pattern decides where it cracks, and the crack events become impulses. There is no
audio recording behind this module and no sound bank: the impulses drive resonators like every other contact.

Brittle (glass, stone, some metals) and fibrous (wood, bark, stems) differ in four measurable ways, and each is a
parameter, not an EQ:
    impulse count     brittle: many, nearly simultaneous; fibrous: fewer, spread over a longer time
    impulse shape     brittle: very short; fibrous: longer and tension-modulated (fibres pulling)
    decay             brittle: high, ringing fragments; fibrous: shorter and duller
    fragment spread   brittle: many small, high-pitched; fibrous: few, larger, lower

Every number here is an ESTIMATE from those qualitative differences plus the material's own toughness and loss factor.
They have not been fitted to a recording; `ambience_reference.py --modes` exists to do that per project.
"""
import numpy as np


def crack_train(material, energy_j=1.0, rng=None, brittle=None):
    """[(time_offset_s, relative_amp, tau_s)] for the crack impulses of one failure.

    Toughness sets how much energy a crack needs, so a tougher material makes fewer, bigger cracks for the same
    released energy. A brittle material releases it in a burst; a fibrous one drags it out.
    """
    rng = rng or np.random.default_rng(0)
    if brittle is None:
        brittle = material.get('family') in ('brittle', 'metal')
    toughness = max(float(material.get('toughness_kpa', 600.0)), 1.0)
    e = max(float(energy_j), 1e-6)
    if brittle:
        count = int(np.clip(8 + 40 * np.log10(1 + e), 8, 90))
        spread = 0.004 + 0.02 * np.log10(1 + e)         # a brittle release is fast
        tau = np.clip(0.0004 + 0.002 / np.sqrt(toughness / 4000.0), 3e-4, 0.004)
    else:
        count = int(np.clip(4 + 14 * np.log10(1 + e), 4, 30))
        spread = 0.05 + 0.12 * np.log10(1 + e)          # fibres separate over a longer time
        tau = np.clip(0.004 + 0.02 / np.sqrt(toughness / 1000.0), 0.002, 0.03)
    times = np.sort(np.abs(rng.standard_normal(count)) * spread)
    amps = np.exp(-2.2 * times / max(spread, 1e-6)) * (1.0 + 0.35 * rng.standard_normal(count))
    amps = np.clip(amps, 0.05, 1.0)
    return list(zip(times.tolist(), amps.tolist(), [float(tau * (1.0 + 0.4 * rng.standard_normal())) for _ in times]))


def fragments(material, energy_j=1.0, rng=None, count=None, brittle=None):
    """[(size_relative, delay_s)] for the pieces that come off.

    Size distribution is lognormal about the mean, clipped; delay grows with the fragment number (the small ones fly
    first). A cohesive (fibrous) material gives fewer, bigger pieces.
    """
    rng = rng or np.random.default_rng(0)
    if brittle is None:
        brittle = material.get('family') in ('brittle', 'metal')
    if count is None:
        count = int(np.clip((10 if brittle else 4) + 6 * np.log10(1 + max(energy_j, 1e-6)), 2, 24))
    sigma = 0.45 if brittle else 0.3
    sizes = np.exp(sigma * rng.standard_normal(count))
    sizes = np.clip(sizes, 0.15, 3.0)
    order = np.sort(sizes)[::-1]
    delays = np.cumsum(np.abs(rng.standard_normal(count)) * (0.012 if brittle else 0.03))
    return list(zip(order.tolist(), delays.tolist()))


def released_energy(mass_kg, velocity_m_s, fraction=0.35):
    """Energy a failure can radiate: the kinetic energy brought in, times the fraction that becomes sound.

    The 0.35 is an ESTIMATE (a large part of a break is heat and permanent deformation). It is one constant for every
    material, so it cannot hide a per-material fudge.
    """
    return 0.5 * float(mass_kg) * float(velocity_m_s) ** 2 * float(fraction)
