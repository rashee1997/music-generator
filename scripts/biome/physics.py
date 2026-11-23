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

"""physics.py - the closed-form laws a generator needs, with their sources and their limits.

Every function is pure (numbers in, numbers out) so a test can check it against a hand calculation. Status labels:
[lit] from a paper whose coefficients are quoted from memory of the standard form (verify before citing),
[start] a starting value with no source yet, [derived] follows from the formula above it.

Strouhal number of a circular cylinder, by Reynolds number Re = rho U d / eta:
    Re < 49            no shedding: the wake is steady and silent
    49 <= Re < 190     laminar shedding   St = 0.2684 - 1.0356 / sqrt(Re)           [lit: Fey, Koenig & Eckelmann 1998]
    190 <= Re < 250    blend of the two laws, linear in Re
    250 <= Re <= 2e5   subcritical        St = 0.212 (1 - 21.2 / Re)               [lit: Roshko 1954]
    Re > 2e5           supercritical      St = 0.2, wide band                       [start]
Terminal velocity of a drop of diameter D, density rho_p in a gas of density rho_g under gravity g, drag coefficient Cd:
    v = sqrt(8 g D (rho_p - rho_g) / (3 Cd rho_g))                                  [derived: weight = drag]
Minnaert resonance of a gas bubble of radius R in a liquid of density rho_l at pressure p:
    f = sqrt(3 gamma p / rho_l) / (2 pi R)                                          [lit: Minnaert 1933]
Grain-driven dune pitch:   f = k sqrt(g / d)   (d = grain diameter), k = 0.4        [lit: Andreotti 2012 scaling; k is a start]
Aeroacoustic dipole (Curle) power of a body of frontal area A in a flow U:  W = k rho U^6 A / c^3   [lit: Curle 1955; k is a start]
Radiated pressure of a point source of power W at distance r:  p_rms = sqrt(Z W / (4 pi r^2)),  Z = rho c
Pressure of a transient of radiated energy E at r, with a unit-energy waveform w (integral of w^2 dt = 1):
    p(t) = sqrt(Z E / (4 pi r^2)) w(t)                                              [derived]
"""
import math

import numpy as np

G_EARTH = 9.81                      # m/s2, the default `world.g_m_s2`
RE_LAMINAR_LO, RE_LAMINAR_HI, RE_SUBCRIT_LO, RE_SUBCRIT_HI = 49.0, 190.0, 250.0, 2.0e5
STROUHAL_LAWS = ('auto', 'roshko', 'williamson')


def _st_laminar(re):
    return 0.2684 - 1.0356 / math.sqrt(re)


def _st_subcritical(re):
    return 0.212 * (1.0 - 21.2 / re)


def strouhal(re, law='auto'):
    """Strouhal number of a circular cylinder at Reynolds number `re`; 0.0 where no regular shedding exists.

    `auto` picks the law from the Reynolds number (never from the medium). `roshko` and `williamson` force one law, and
    raise outside the range it is quoted for: a number outside its law is a wrong number, not a fallback."""
    re = float(re)
    if law not in STROUHAL_LAWS:
        raise ValueError(f'strouhal law "{law}": use one of {", ".join(STROUHAL_LAWS)}')
    if law == 'roshko':
        if not RE_SUBCRIT_LO <= re <= RE_SUBCRIT_HI:
            raise ValueError(f'the Roshko law holds for Re {RE_SUBCRIT_LO:g}..{RE_SUBCRIT_HI:g}, not {re:g}; use law "auto"')
        return _st_subcritical(re)
    if law == 'williamson':
        if not RE_LAMINAR_LO <= re <= RE_LAMINAR_HI:
            raise ValueError(f'the laminar law holds for Re {RE_LAMINAR_LO:g}..{RE_LAMINAR_HI:g}, not {re:g}; use law "auto"')
        return _st_laminar(re)
    if re < RE_LAMINAR_LO:
        return 0.0
    if re < RE_LAMINAR_HI:
        return _st_laminar(re)
    if re < RE_SUBCRIT_LO:
        w = (re - RE_LAMINAR_HI) / (RE_SUBCRIT_LO - RE_LAMINAR_HI)
        return (1.0 - w) * _st_laminar(RE_LAMINAR_HI) + w * _st_subcritical(RE_SUBCRIT_LO)
    if re <= RE_SUBCRIT_HI:
        return _st_subcritical(re)
    return 0.2


def strouhal_array(re):
    """`strouhal(re, "auto")` over an array."""
    return np.array([strouhal(r) for r in np.asarray(re, dtype=float).ravel()]).reshape(np.shape(re))


def shedding_hz(u_m_s, d_m, re):
    """Vortex-shedding (Aeolian) tone, Hz: St(Re) U / d."""
    return strouhal(re) * float(u_m_s) / float(d_m)


def terminal_velocity(g, d_m, rho_particle, rho_gas, cd):
    """Terminal fall speed, m/s (weight balances drag)."""
    if rho_particle <= rho_gas:
        return 0.0                  # a particle lighter than its gas does not fall
    return math.sqrt(8.0 * g * d_m * (rho_particle - rho_gas) / (3.0 * cd * rho_gas))


def minnaert_hz(radius_m, gamma, pressure_pa, rho_liquid):
    """Resonance of a gas bubble in a liquid, Hz."""
    return math.sqrt(3.0 * gamma * pressure_pa / rho_liquid) / (2.0 * math.pi * float(radius_m))


def dune_hz(g, grain_m, k=0.4):
    """Pitch of a singing dune, Hz: k sqrt(g / d)."""
    return float(k) * math.sqrt(float(g) / float(grain_m))


def dipole_power(k, rho, u, area_m2, c):
    """Radiated acoustic power of an aeroacoustic dipole, W: k rho U^6 A / c^3."""
    return float(k) * float(rho) * float(u) ** 6 * float(area_m2) / float(c) ** 3


def pressure_rms_from_power(z, power_w, r_m=1.0):
    """RMS pressure at r metres of a source radiating `power_w` (spherical spreading), Pa."""
    return math.sqrt(max(0.0, float(z) * float(power_w)) / (4.0 * math.pi * float(r_m) ** 2))


def pressure_scale_from_energy(z, energy_j, r_m=1.0):
    """Amplitude of a unit-energy transient radiating `energy_j` joules, Pa (see the module docstring)."""
    return math.sqrt(max(0.0, float(z) * float(energy_j)) / (4.0 * math.pi * float(r_m) ** 2))


def marshall_palmer_lambda(rate_mm_h):
    """Slope of the exponential drop-size distribution, 1/mm: 4.1 R^-0.21 (R in mm/h)  [lit: Marshall & Palmer 1948]."""
    return 4.1 * max(0.05, float(rate_mm_h)) ** -0.21


def drop_population(rate_mm_h, d_mm, g, rho_particle, rho_gas, cd, lam_per_mm=None, bins=48):
    """The drops that ARRIVE at a surface, as arrays over a diameter grid.

    Sizes follow N(D) ~ exp(-lambda D); a drop of diameter D arrives with weight N(D) v(D) (bigger ones fall faster, so they
    are over-represented among the arrivals). The overall rate is then fixed by the volume flux: `rate_mm_h` of liquid
    depth per hour (1 mm/h = 1 litre per m2 per hour) is the sum over arrivals of their volume. Returns
    (d_m, pdf, v_m_s, drops_per_m2_s) where pdf is the probability of an arrival at each bin (sums to 1).
    """
    lo, hi = float(d_mm[0]), float(d_mm[1])
    lam = float(lam_per_mm) if lam_per_mm else marshall_palmer_lambda(rate_mm_h)
    d = np.linspace(lo, hi, int(bins)) * 1e-3                                  # m
    v = np.array([terminal_velocity(g, x, rho_particle, rho_gas, cd) for x in d])
    w = np.exp(-lam * d * 1e3) * v
    pdf = w / max(w.sum(), 1e-300)
    vol = (math.pi / 6.0) * d ** 3                                              # m3 per drop
    mean_vol = float((pdf * vol).sum())
    flux_m_s = float(rate_mm_h) * 1e-3 / 3600.0                                 # m3 of liquid per m2 per second
    rate = flux_m_s / max(mean_vol, 1e-30) if rate_mm_h > 0 else 0.0
    return d, pdf, v, rate
