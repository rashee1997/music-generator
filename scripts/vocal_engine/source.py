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

"""Glottal source: parametric flow pulse (Rosenberg/LF family) driven by a continuous phase.

Flow g(phi): raised-cosine opening to the peak (fraction Tp of the period), then a closing phase that ends at the
open quotient. `closure` blends an abrupt cosine close (0, strong high harmonics, pressed/chest) with a smooth
raised-cosine close (1, weak high harmonics, falsetto/breathy). The radiated source is the flow derivative.
`phase` is a cumulative cycle count, so a phrase rendered in one call has no restart at note joins.
"""
import numpy as np
from scipy.signal import lfilter

from .utils import one_pole_lp, rms


def cycles(f0, sr, phase0=0.0):
    """Cumulative cycles at every sample (continuous phase). Returns array; the last value + frac is the next phase0."""
    return phase0 + np.cumsum(np.maximum(f0, 20.0)) / sr


def pulse(phi, oq, sq, closure):
    oq = np.clip(oq, 0.05, 0.98)
    sq = np.clip(sq, 0.3, 6.0)
    closure = np.clip(closure, 0.0, 1.0)
    tp = oq * sq / (1.0 + sq)
    tn = np.maximum(oq - tp, 1e-3)
    rise = 0.5 * (1.0 - np.cos(np.pi * np.clip(phi / tp, 0, 1)))
    x = np.clip((phi - tp) / tn, 0.0, 1.0)
    fall = (1.0 - closure) * np.cos(0.5 * np.pi * x) + closure * 0.5 * (1.0 + np.cos(np.pi * x))
    g = np.where(phi < tp, rise, np.where(phi < oq, fall, 0.0))
    return g


def _radiate(g, f0, sr):
    """Flow derivative, scaled so its level does not depend on f0."""
    d = np.diff(g, prepend=g[:1])
    return d * sr / np.maximum(f0, 20.0)


def _tilt(x, tilt_hz, sr):
    t = np.asarray(tilt_hz, dtype=float)
    t = np.maximum(t, 20.0)
    if t.ndim == 0 or t.min() == t.max():
        return one_pole_lp(x, float(np.maximum(t.reshape(-1)[0], 20.0)), sr)
    lo, hi = float(np.maximum(t.min(), 20.0)), float(np.maximum(t.max(), 20.0))
    if hi <= lo:
        hi = lo * 1.001
    t_clamped = np.maximum(t, 20.0)
    w = (np.log(t_clamped) - np.log(lo)) / (np.log(hi) - np.log(lo))
    return (1.0 - w) * one_pole_lp(x, lo, sr) + w * one_pole_lp(x, hi, sr)


def glottal_source(f0, sr, rng, reg, breathiness=0.03, phase0=0.0, subharmonic=False, sub_weight=0.65,
                   whistle_hz=0.0, whistle_weight=0.45, aspiration_depth=0.65, tilt_hz=None):
    """f0: Hz per sample. reg: dict(open_quotient, speed_quotient, closure, tilt_hz, shimmer); each value scalar
    or per-sample array. Returns (source, cycles, flow). Voiced part has unit RMS, so dynamics are applied later."""
    f0 = np.asarray(f0, dtype=float)
    n = len(f0)
    if n == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    c = cycles(f0, sr, phase0)
    phi = c - np.floor(c)
    g = pulse(phi, reg['open_quotient'], reg['speed_quotient'], reg['closure'])
    d = _radiate(g, f0, sr)
    shimmer = float(np.mean(reg.get('shimmer', 0.0)))
    if shimmer > 0:
        idx = (np.floor(c) - np.floor(c[0])).astype(int)
        shimmer_env = (1.0 + shimmer * rng.standard_normal(idx[-1] + 1)[idx])
        shimmer_env = one_pole_lp(shimmer_env, 80.0, sr)
        d = d * shimmer_env
    if subharmonic:
        c2 = c / 2.0
        d = d + sub_weight * _radiate(pulse(c2 - np.floor(c2), reg['open_quotient'], reg['speed_quotient'],
                                            reg['closure']), 0.5 * f0, sr)
    d = _tilt(d, reg['tilt_hz'] if tilt_hz is None else tilt_hz, sr)
    d = d / (rms(d) + 1e-12)
    if whistle_hz and whistle_hz > 0:
        h = max(1, int(round(whistle_hz / float(np.mean(f0)))))
        d = d + whistle_weight * np.sin(2 * np.pi * np.cumsum(f0 * h) / sr)
    if np.any(np.asarray(breathiness) > 0):                       # scalar or per-sample track
        noise = lfilter([1, -1], [1, -0.7], rng.standard_normal(n))
        noise = noise * ((1.0 - aspiration_depth) + aspiration_depth * g)
        d = d + breathiness * noise / (rms(noise) + 1e-12)
    return d, c, g
