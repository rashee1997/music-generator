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
"""excite.py - how energy gets into an object.

Each mechanism is distinguishable: a hard contact is a short pulse and a bright mode set, a soft one is long and dull; a
sliding contact is a fractal surface read at the contact speed; stick-slip is a self-excited limit cycle, not a saw
wave; a gust is a -5/3 turbulence series, not a sine; a granular medium is a cascade of many small contacts with a size
distribution, not one crunch. They are not one noise source with different filters.

Formulas and where they come from (full table: knowledgebase/PHYSICS.md when Stage 1 lands; the two that matter here):
  impact      force F(t) = 1 - cos(2 pi t / tau), tau = contact time     (van den Doel, Kry, Pai, SIGGRAPH 2001, 4.1)
  friction    surface profile with power spectrum ~ omega^beta, read at the contact speed (same paper, scraping)
  turbulence  PSD ~ (1 + (f/fc)^2)^(-5/6), the von Karman/Kaimal form (already used by environment._turbulence)

Everything takes an explicit rng and returns arrays, so a scene is reproducible for a seed.
"""
import math

import numpy as np


# ------------------------------------------------------------------ contact
def impact_energy(mass_kg, velocity_m_s):
    """Kinetic energy of the contact, J. This is the physical intensity an effect should not be normalized away."""
    return 0.5 * float(mass_kg) * float(velocity_m_s) ** 2


def contact_time(stiffness_pa_m, mass_kg, velocity_m_s, ref_tau=0.002):
    """Contact duration of a Hertzian impact, s.

    The Hertz contact law gives tau ~ 2.94 (5 m / (4 n))^(2/5) v^(-1/5) for a sphere against a plane with local
    stiffness n = (4/3) E* sqrt(R). E* and R are folded into `stiffness_pa_m`, so the two exponents are kept and the
    scale is referenced to a 2 ms contact (a hard, small object). This is an ESTIMATE with the right scaling: the 2 s
    reference is a design choice, the v^(-1/5) and m^(2/5) exponents are the physics.
    """
    n = max(float(stiffness_pa_m), 1.0)
    m = max(float(mass_kg), 1e-6)
    v = max(float(velocity_m_s), 0.01)
    # scaled from a 1 kg, 1 m/s contact against a 1e7 Pa/m reference: tau ~ m^0.4 n^-0.4 v^-0.2
    return float(np.clip(ref_tau * (m ** 0.4) * ((1e7 / n) ** 0.4) * (v ** -0.2), 1e-5, 0.2))


def impact_pulse(tau, sr=44100, n=None):
    """F(t) = 1 - cos(2 pi t / tau) for 0 <= t <= tau, else 0, unit area."""
    m = max(2, int(round(float(tau) * sr)))
    if n is not None:
        m = min(m, int(n))
    t = np.arange(m) / float(m)
    pulse = 1.0 - np.cos(2 * np.pi * t)
    out = np.zeros(int(n) if n is not None else m)
    out[:m] = pulse / max(pulse.sum(), 1e-12)
    return out


def burst(tau, sr=44100, rng=None, color='white', n=None):
    """Short broadband excitation with an exponential decay (a blast, a crack, a snap)."""
    rng = rng or np.random.default_rng(0)
    m = max(2, int(round(3.0 * float(tau) * sr)))
    if n is not None:
        m = min(m, int(n))
    x = noise(m, rng, color=color) * np.exp(-np.arange(m) / max(tau * sr, 1.0))
    out = np.zeros(int(n) if n is not None else m)
    out[:m] = x / (np.abs(x).max() + 1e-12)
    return out


# ------------------------------------------------------------------ noise and surface profile
def noise(n, rng, color='white', beta=None):
    """Coloured noise; `beta` sets the slope directly (power ~ f^beta, -1.5 is a natural rough surface)."""
    x = rng.standard_normal(int(n))
    if beta is None:
        beta = {'white': 0.0, 'pink': -1.0, 'brown': -2.0}.get(color, 0.0)
    if beta == 0.0 or n < 32:
        return x
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x))
    f[0] = f[1] if len(f) > 1 else 1.0
    spec *= np.abs(f) ** (beta / 2.0)
    y = np.fft.irfft(spec, len(x))
    return y / (np.std(y) + 1e-12)


def fractal_profile(n, rng, beta=-1.5, oversample=2):
    """Surface height profile whose power spectrum is ~ omega^beta, longer than n so it can be read at speed."""
    L = max(int(n * oversample), 1024)
    return noise(L, rng, beta=beta)


def scratch(seconds, sr, rng, speed=1.0, beta=-1.5, amp_exp=1.0):
    """A sliding contact: the surface profile sampled at the contact speed. Faster = brighter and louder."""
    n = max(1, int(round(seconds * sr)))
    prof = fractal_profile(n + 2 * sr, rng, beta)
    v = np.clip(np.full(n, float(speed)), 0.0, 8.0)
    pos = np.cumsum(v)
    x = np.interp(pos % (len(prof) - 1), np.arange(len(prof)), prof)
    return x * (np.maximum(v, 0) ** amp_exp)


def stick_slip(seconds, sr, rng, f_slip=38.0, depth=0.8, jitter=0.06, tau_s=0.004):
    """Self-excited stick-slip: a pulse train whose rate is the slip frequency, each slip a short contact pulse.

    The slip frequency of a mass on a spring with a velocity-weakening friction law is ~ (1/2pi) sqrt(k/m), which is
    why it rises when the contact gets stiffer. It is not an LFO: the pulses are individual slips, with jitter.
    """
    n = max(1, int(round(seconds * sr)))
    out = np.zeros(n)
    period = max(1.0 / max(f_slip, 1.0), 1e-4)
    t = 0.0
    pulse_n = max(2, int(tau_s * sr))
    shape = 1.0 - np.cos(2 * np.pi * np.arange(pulse_n) / pulse_n)
    while t < seconds:
        i = int(t * sr)
        if i >= n:
            break
        amp = depth * (1.0 + jitter * rng.standard_normal())
        seg = shape[: max(1, min(pulse_n, n - i))] * max(amp, 0.05)
        out[i:i + len(seg)] += seg
        t += period * (1.0 + jitter * rng.standard_normal())
    if depth < 1.0:
        out = out + (1.0 - depth) * noise(n, rng, beta=-1.0) * 0.25
    return out


def rolling(seconds, sr, rng, roughness=-1.2, speed=1.0):
    """Rolling contact: a rough surface read at speed, low-passed, with a slow amplitude wander."""
    x = scratch(seconds, sr, rng, speed=speed, beta=roughness)
    k = max(2, int(0.004 * sr))
    smooth = np.convolve(x, np.ones(k) / k, 'same')
    n = len(smooth)
    t = np.arange(n) / sr
    return smooth * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * t + rng.uniform(0, 6)))


# ------------------------------------------------------------------ flow
def kaimal(n, sr, rng, corner_hz=0.12, intensity=0.2):
    """Turbulence series with the -5/3 slope above the corner frequency, unit variance, slowly varying in time."""
    spec = np.fft.rfft(rng.standard_normal(int(n)))
    f = np.fft.rfftfreq(int(n), 1.0 / sr)
    spec *= (1.0 + (f / max(corner_hz, 1e-3)) ** 2) ** (-5.0 / 12.0)
    spec[0] = 0.0
    z = np.fft.irfft(spec, int(n))
    z = z / (z.std() + 1e-12)
    return np.clip(1.0 + float(intensity) * z, 0.05, 3.0)


def flow(seconds, sr, rng, speed_m_s=4.0, corner_hz=0.12, intensity=0.2, band=(120.0, 4000.0), roughness=-1.0):
    """Air moving over something: turbulence-modulated noise, brightness and level both follow the wind speed."""
    n = max(1, int(round(seconds * sr)))
    base = noise(n, rng, beta=roughness)
    gust = kaimal(n, sr, rng, corner_hz, intensity)
    from . import resonate as _res
    out = _res.bandpass(base, band[0], band[1], sr)
    out = out * gust
    return out * float(speed_m_s) ** 1.5 / 4.0      # level rises faster than linearly with speed


# ------------------------------------------------------------------ granular
def granular(seconds, rng, rate=60.0, sigma=0.5, restitution=0.3, size_min=0.2, size_max=3.0):
    """A cascade of particle contacts: sorted arrival times and relative sizes (mean 1).

    Gaps are exponential (independent collisions), not uniform: a granular medium at a given shear rate has a Poisson
    event stream, and the sizes are lognormal because the grains are. One 'crunch' per second is a drum, not gravel.
    """
    n_est = max(1, int(seconds * rate * 1.5) + 8)
    gaps = rng.exponential(1.0 / max(rate, 0.01), n_est)
    times = np.cumsum(gaps)
    times = times[times < seconds]
    sizes = np.exp(sigma * rng.standard_normal(times.size))
    sizes = np.clip(sizes, size_min, size_max)
    return times, sizes / max(sizes.mean() if sizes.size else 1.0, 1e-9)


# ------------------------------------------------------------------ structural stress
def stress(seconds, sr, rng, strain=0.004, rate_per_s=2.0, creep=False):
    """Mechanical stress: creak events whose rate follows the strain rate, amplitudes with the strain.

    A loaded wooden structure does not hum: it makes many small stick-slip events that speed up as the strain rises,
    then a single large failure. `creep=True` keeps a low continuous groan under the events (fibres slipping).
    """
    n = max(1, int(round(seconds * sr)))
    out = np.zeros(n)
    t = 0.0
    count = 0
    while t < seconds:
        i = int(t * sr)
        if i >= n:
            break
        f = 12.0 + 60.0 * float(strain) * 100.0 + rng.uniform(0, 30)
        seg = stick_slip(1.0 / max(rate_per_s, 0.05) * 0.3, sr, rng, f_slip=f, depth=0.5)
        seg = seg[: max(1, min(len(seg), n - i))] * min(1.0, 0.2 + 200 * float(strain))
        out[i:i + len(seg)] += seg
        t += (1.0 / max(rate_per_s, 0.05)) * rng.uniform(0.6, 1.4)
        count += 1
    if creep:
        out += 0.15 * stick_slip(seconds, sr, rng, f_slip=18.0, depth=0.25)
    return out
