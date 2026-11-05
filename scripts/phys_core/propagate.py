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
"""propagate.py - how the sound gets from the object to the listener.

One law, shared by ambience and one-hit effects. Before this module the skill had three: ISO 9613-1 when a preset set
`atmosphere`, a 22 kHz/(1+0.35(d-2)) cutoff otherwise, and a 10 kHz - 120d cutoff in apply_environmental_acoustics. The
same physical phenomenon cannot be three formulas, so it is one:

    level      1/r spreading from a reference distance (inverse distance, not inverse square: a pressure wave)
    air        ISO 9613-1 absorption by temperature and humidity (airabs.py, already measured against the standard)
    canopy     extra high-frequency absorption over a distance through vegetation (a density parameter, not a filter)
    ground     one reflection from the ground with a delay and a loss (the first early reflection a listener hears)

The canopy and ground terms are ESTIMATES: real values need a measurement for the place (ambience_reference.py).
"""
import numpy as np

from . import resonate

REF_DISTANCE_M = 1.0


def distance_gain(distance_m, ref_m=REF_DISTANCE_M):
    """Pressure falls with 1/r from the reference distance. Clamped so a scene at 0 m is not infinite."""
    return float(ref_m) / max(float(distance_m), float(ref_m) * 0.5)


def air(x, sr, distance_m, temp_c=20.0, rh=50.0):
    """ISO 9613-1 atmospheric absorption over the distance beyond 1 m."""
    d = max(0.0, float(distance_m) - REF_DISTANCE_M)
    if d <= 1e-6:
        return x
    import airabs
    return airabs.apply(x, d, temp_c=float(temp_c), rh=float(rh), sr=sr)


def canopy(x, sr, distance_m, density=0.0):
    """Vegetation between source and listener: an extra high-frequency loss that grows with distance and density.

    density 0 is open air, 1 is a thick canopy. Implemented as a frequency-domain attenuation (zero phase), which is
    what scattering over many leaves approximates; it is not a reverb and cannot make a forest sound like a hall.
    """
    x = np.asarray(x, dtype=float)
    d = max(0.0, float(distance_m) - REF_DISTANCE_M)
    if d <= 1e-6 or density <= 0 or x.size < 16:
        return x
    n = x.size
    f = np.fft.rfftfreq(n, 1.0 / sr)
    # ~0.02 dB/m of extra loss at 4 kHz per unit density, rising with frequency; ESTIMATE for a woodland
    atten_db = 0.02 * float(density) * d * (f / 4000.0) ** 0.8
    spec = np.fft.rfft(x) * 10.0 ** (-atten_db / 20.0)
    return np.fft.irfft(spec, n)


def ground(x, sr, distance_m, gain=0.35, delay_ms=7.0, cutoff_hz=3500.0):
    """One ground reflection: a delayed, low-passed, quieter copy. The first cue that a source stands on something."""
    x = np.asarray(x, dtype=float)
    d = max(0.0, float(distance_m))
    if gain <= 0 or d <= 1e-6:
        return x
    delay = int(round(delay_ms * 1e-3 * sr * (1.0 + d / 20.0)))
    refl = resonate.bandpass(x, 40.0, cutoff_hz, sr, order=1) * float(gain)
    out = x.copy()
    if delay < len(out):
        out[delay:] += refl[: len(out) - delay]
    return out


def fresnel_number(path_diff_m, freq_hz):
    """Fresnel-Kirchhoff diffraction parameter N = 2 * delta / lambda (Maekawa 1968).

    delta is the extra path length around the barrier edge over the direct line, so a sound barely
    blocked (delta near 0) sits near N = 0 and a sound well screened has a large N.
    """
    d = max(0.0, float(path_diff_m))
    f = np.maximum(np.asarray(freq_hz, dtype=float), 1.0)
    return 2.0 * d * f / 343.0


def maekawa_il(path_diff_m, freq_hz):
    """Insertion loss of a thin barrier, dB, from the Maekawa/Kurze-Anderson curve.

        IL(N) = 5 + 20 log10( sqrt(2 pi N) / tanh( sqrt(2 pi N) ) )      for N > 0
        IL(N) = 0                                                        for N <= 0

    The 5 dB term is the edge's own floor, and the shape is the standard barrier result quoted by
    ISO 9613-2 for a thin screen. Capped at 40 dB: beyond that the model, not the world, is talking.
    """
    n = np.asarray(fresnel_number(path_diff_m, freq_hz), dtype=float)
    arg = np.sqrt(2.0 * np.pi * np.maximum(n, 0.0))
    with np.errstate(divide='ignore', invalid='ignore'):
        il = 5.0 + 20.0 * np.log10(arg / np.tanh(np.maximum(arg, 1e-9)))
    return np.where(n > 0.0, np.clip(il, 0.0, 40.0), 0.0)


def path_difference_m(total_m, edge_offset_m):
    """Extra path around a barrier edge, m, for a source and listener `total_m` apart and an edge
    `edge_offset_m` out of the straight line (assumed halfway: the worst case a scene can state).

    sqrt(a^2 + h^2) + sqrt(b^2 + h^2) - (a + b) with a = b = total / 2.
    """
    d = max(0.0, float(total_m))
    h = max(0.0, float(edge_offset_m))
    half = d / 2.0
    return float(2.0 * np.sqrt(half * half + h * h) - d)


def mass_law_tl(density_kg_m3, thickness_m, freq_hz):
    """Transmission loss through a partition, dB, from the field-incidence mass law.

        TL = 20 log10(m'' f) - 47        m'' = density * thickness  (kg/m^2)

    The standard field-incidence form (Sharp 1978); a real wall's coincidence dip is not modelled, so
    this over-estimates loss near the critical frequency. Negative values are clamped to 0: a thin
    membrane does not amplify.
    """
    m_s = max(float(density_kg_m3) * float(thickness_m), 1e-3)
    f = np.maximum(np.asarray(freq_hz, dtype=float), 1.0)
    return np.clip(20.0 * np.log10(m_s * f) - 47.0, 0.0, None)


def occlusion(x, sr, cfg, materials):
    """A barrier between the source and the listener: transmission through it plus diffraction round its edge.

    cfg is a scene's `propagation.occluder` block:

        {"material": "oak", "thickness_m": 0.03, "edge_offset_m": 0.15,
         "coverage": 1.0, "transmission": true}

    `coverage` is the share of the barrier that blocks the direct line (1 = fully behind it); the
    transmitted and diffracted energies add, which is what makes a door between two rooms sound like
    *some* of the sound and not like a low-pass filter with an arbitrary cutoff. Both are applied per
    frequency, zero phase: two paths, not a tone control.
    """
    cfg = cfg or {}
    x = np.asarray(x, dtype=float)
    if x.size < 16:
        return x
    total = float(cfg.get('distance_m', 1.0))
    edge = float(cfg.get('edge_offset_m', 0.0))
    coverage = float(np.clip(float(cfg.get('coverage', 1.0)), 0.0, 1.0))
    if edge <= 0.0 and coverage <= 0.0:
        return x
    n = x.size
    f = np.fft.rfftfreq(n, 1.0 / sr)
    f[0] = max(f[1] if len(f) > 1 else 1.0, 1.0)
    delta = path_difference_m(total, edge)
    diff = maekawa_il(delta, f) if delta > 0.0 else np.zeros_like(f)
    # The line is blocked by `coverage`; sound still arrives two ways, and their energies add:
    #   the unblocked remainder, and the part that goes through or round the barrier. A barrier with no edge
    #   to go round (edge_offset 0) offers only its transmission path: a wall, not a screen.
    energy = 1.0 - coverage
    if edge > 0.0:
        energy = energy + coverage * 10.0 ** (-diff / 10.0)
    if cfg.get('transmission', True):
        mat = materials.get(str(cfg.get('material') or ''), {}) if isinstance(materials, dict) else {}
        density = float(mat.get('density', 600.0))
        thick = float(cfg.get('thickness_m', 0.02))
        tl = mass_law_tl(density, thick, f)
        energy = energy + coverage * 10.0 ** (-tl / 10.0)
    # energy is a ratio, so the floor is a numerical one, not a tonal choice: a thick wall really does stop
    # 60+ dB at 8 kHz, and a -24 dB cap would make every barrier sound like the same thin curtain.
    atten = np.clip(10.0 * np.log10(np.maximum(energy, 1e-9)), -90.0, 0.0)
    return np.fft.irfft(np.fft.rfft(x) * 10.0 ** (atten / 20.0), n)


def pan(mono, azimuth_deg=0.0, elevation_deg=0.0):
    """Constant-power stereo placement from an azimuth (elevation is carried, not yet rendered as height)."""
    a = np.radians(np.clip(float(azimuth_deg), -180.0, 180.0))
    p = np.clip(np.sin(a), -1.0, 1.0)
    ang = (p + 1.0) * (np.pi / 4.0)
    m = np.asarray(mono, dtype=float)
    return np.stack([m * np.cos(ang), m * np.sin(ang)], axis=1)


def apply(mono, sr, cfg=None, materials=None):
    """The whole chain for one layer: spreading, air, canopy, barrier and ground.

    cfg is the scene's `propagation` block; `materials` is the scene's material table, needed only when a
    barrier is declared (a barrier's transmission loss comes from its material, not from a number here).
    """
    cfg = cfg or {}
    materials = materials or {}
    x = np.asarray(mono, dtype=float)
    d = float(cfg.get('distance_m', REF_DISTANCE_M))
    x = x * distance_gain(d)
    atm = cfg.get('atmosphere') or {}
    x = air(x, sr, d, atm.get('temp_c', 20.0), atm.get('rh', 50.0))
    x = canopy(x, sr, d, float(cfg.get('canopy_density', 0.0)))
    occ = cfg.get('occluder')
    if isinstance(occ, dict) and occ:
        x = occlusion(x, sr, dict(occ, distance_m=occ.get('distance_m', d)), materials)
    x = ground(x, sr, d, float(cfg.get('ground_gain', 0.35)), float(cfg.get('ground_delay_ms', 7.0)),
               float(cfg.get('ground_cutoff_hz', 3500.0)))
    return x
