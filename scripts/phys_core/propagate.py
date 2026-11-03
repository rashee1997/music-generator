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


def pan(mono, azimuth_deg=0.0, elevation_deg=0.0):
    """Constant-power stereo placement from an azimuth (elevation is carried, not yet rendered as height)."""
    a = np.radians(np.clip(float(azimuth_deg), -180.0, 180.0))
    p = np.clip(np.sin(a), -1.0, 1.0)
    ang = (p + 1.0) * (np.pi / 4.0)
    m = np.asarray(mono, dtype=float)
    return np.stack([m * np.cos(ang), m * np.sin(ang)], axis=1)


def apply(mono, sr, cfg=None):
    """The whole chain for one layer: spreading, air, canopy and ground. cfg is the scene's `propagation` block."""
    cfg = cfg or {}
    x = np.asarray(mono, dtype=float)
    d = float(cfg.get('distance_m', REF_DISTANCE_M))
    x = x * distance_gain(d)
    atm = cfg.get('atmosphere') or {}
    x = air(x, sr, d, atm.get('temp_c', 20.0), atm.get('rh', 50.0))
    x = canopy(x, sr, d, float(cfg.get('canopy_density', 0.0)))
    x = ground(x, sr, d, float(cfg.get('ground_gain', 0.35)), float(cfg.get('ground_delay_ms', 7.0)),
               float(cfg.get('ground_cutoff_hz', 3500.0)))
    return x
