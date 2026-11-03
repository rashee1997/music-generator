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
"""resonate.py - the object answers: modal bank, porous absorption, bubbles.

A resonator is what the material does to whatever hit it. Three kinds are enough for contact, foliage, water and
enclosed spaces:

  modal   a bank of damped resonators at the object's mode frequencies (van den Doel, Kry, Pai, SIGGRAPH 2001, eq. 1)
  porous  a frequency-dependent attenuation from the material's flow resistivity, so a leaf or a fabric swallows the
          top end instead of needing an EQ (Delany-Bazley-Miki, formulas read from the APMR reference)
  bubble  a Minnaert resonator, f = 3.26 / r for radius r in metres

The modal bank carries filter state per mode and is driven by a sampled excitation, so it can be used on a whole
voice at once (no per-event Python loop) and it does not click at block edges.
"""
import math

import numpy as np
from scipy.signal import butter, lfilter, sosfilt

MAX_MODES = 48


def modal(x, f1, ratios, t60_1, sr=44100, damp_exp=0.6, pitch=1.0, gains=None, strike_spread=0.0, rng=None):
    """Drive a damped resonator bank with x. An impulse in gives sum a_n exp(-d_n t) sin(2 pi f_n t)."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return x
    r = np.asarray(ratios, dtype=float)[:MAX_MODES]
    f = f1 * pitch * r
    keep = f < sr / 2 - 200
    r, f = r[keep], f[keep]
    if f.size == 0:
        return np.zeros_like(x)
    t60 = np.clip(float(t60_1) * np.maximum(r, 1e-9) ** (-float(damp_exp)), 0.002, 8.0)
    d = 6.907755 / t60
    a = (r ** -1.0) if gains is None else np.asarray(gains, float)[keep]
    if strike_spread > 0 and rng is not None:
        a = a * np.exp(rng.standard_normal(a.size) * strike_spread)
    a = a / (np.abs(a).max() + 1e-12)
    y = np.zeros_like(x)
    for fn, dn, an in zip(f, d, a):
        rad = math.exp(-dn / sr)
        th = 2 * math.pi * min(fn, sr / 2 - 100) / sr
        y += an * lfilter([0.0, rad * math.sin(th)], [1.0, -2 * rad * math.cos(th), rad * rad], x)
    return y


def bandpass(x, lo, hi, sr=44100, order=2):
    lo, hi = max(20.0, float(lo)), min(sr / 2 - 100, float(hi))
    if hi <= lo:
        return np.asarray(x, dtype=float)
    return sosfilt(butter(order, [lo, hi], btype='band', fs=sr, output='sos'), x)


def porous_absorption(freq_hz, sigma, thickness_m=0.001):
    """Attenuation of the Delany-Bazley-Miki model over `thickness_m`, as a linear gain per frequency.

    The Miki revision of Delany-Bazley (formulas: APMR / Matelys, cited in STATUS):
        X    = f / sigma
        k    = (w/c) * ( 11.41 X^-0.618 + i (1 + 7.81 X^-0.618) )
    The imaginary part of k is the attenuation along the propagation direction, so the gain after a thickness h is
    exp(-|Im k| h). Physical range: X between about 0.01 and 1 (the models' stated validity), sigma in N s/m4.
    """
    f = np.maximum(np.asarray(freq_hz, dtype=float), 1e-6)
    sigma = max(float(sigma), 1.0)
    x = f / sigma
    c = 343.0
    im_k = (2 * np.pi * f / c) * (1.0 + 7.81 * np.power(x, -0.618))
    return np.exp(-im_k * max(float(thickness_m), 1e-9))


def porous(x, sigma, thickness_m=0.001, sr=44100):
    """Apply porous absorption to a signal in the frequency domain (zero phase, no filter transient)."""
    x = np.asarray(x, dtype=float)
    if x.size < 8 or sigma <= 0 or thickness_m <= 0:
        return x
    n = x.size
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    spec *= porous_absorption(f, sigma, thickness_m)
    return np.fft.irfft(spec, n)


def bubble(f_hz, t60_s=0.03, dur_s=0.06, sr=44100, rise=0.1, pitch=1.0):
    """Minnaert bubble: a decaying sine whose pitch rises slightly as the bubble shrinks."""
    f0 = min(float(f_hz) * pitch, sr / 2 - 300)
    n = max(2, int(round(dur_s * sr)))
    t = np.arange(n) / sr
    d = 6.907755 / max(t60_s, 1e-4)
    return np.exp(-d * t) * np.sin(2 * np.pi * f0 * (t + 0.5 * rise * d * t * t))


def bubble_radius(f_hz):
    """Minnaert radius in metres for a resonance frequency: r = 3.26 / f."""
    return 3.26 / max(float(f_hz), 1.0)


def bubble_frequency(radius_m):
    """Minnaert frequency for a radius in metres: f = 3.26 / r."""
    return 3.26 / max(float(radius_m), 1e-6)
