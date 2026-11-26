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

"""modfx.py - effects that modulate a stem's level, spectrum or filter: the sweep, ring modulation, tremolo and auto-pan, a
rhythmic gate and a transient shaper. Same contract as timefx.py: `fn(x, sr, p, rng) -> y`, same length, input outside the
range returned unchanged."""
import math

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d

from . import core

BLOCK = 128          # samples between two coefficient updates of the sweep: 3 ms at 44.1 kHz, below what a sweep can show
WARMUP = 2048        # samples before the range that prime the filter so it starts from the signal, not from silence


def sweep_window(p, n, sr):
    """The sweep's range; with after == "hold" the filter stays at f_end_hz to the end of the stem."""
    i0, i1 = core.span(p, n, sr)
    return (i0, n) if p.get('after') == 'hold' else (i0, i1)


def _biquad(kind, f, q, sr):
    """RBJ cookbook biquad (b, a), normalised. The cutoff is held under 0.45 sr."""
    f = float(np.clip(f, 20.0, 0.45 * sr))
    w0 = 2.0 * math.pi * f / sr
    cs, alpha = math.cos(w0), math.sin(w0) / (2.0 * q)
    if kind == 'lowpass':
        b = [(1 - cs) / 2, 1 - cs, (1 - cs) / 2]
    elif kind == 'highpass':
        b = [(1 + cs) / 2, -(1 + cs), (1 + cs) / 2]
    else:
        b = [alpha, 0.0, -alpha]
    a = [1 + alpha, -2 * cs, 1 - alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


def filter_sweep(x, sr, p, rng):
    """A filter whose cutoff glides from f_start_hz at start_s to f_end_hz at end_s (even in octaves for "exp")."""
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    j1 = n if p.get('after') == 'hold' else i1
    y = x.copy()
    if j1 - i0 < 2:
        return y
    f0, f1, q, kind = float(p['f_start_hz']), float(p['f_end_hz']), float(p['q']), p['kind']
    total = max(1, i1 - i0)

    def cutoff(i):
        u = min(1.0, max(0.0, (i - i0) / total))
        return f0 * (f1 / f0) ** u if p['curve'] == 'exp' else f0 + (f1 - f0) * u

    zi = np.zeros((2, x.shape[1]))
    b, a = _biquad(kind, cutoff(i0), q, sr)
    lo = max(0, i0 - WARMUP)
    if i0 - lo > 8:
        _, zi = signal.lfilter(b, a, x[lo:i0].astype(np.float64), axis=0, zi=zi)
    for s in range(i0, j1, BLOCK):
        e = min(j1, s + BLOCK)
        b, a = _biquad(kind, cutoff((s + e) / 2.0), q, sr)
        seg, zi = signal.lfilter(b, a, x[s:e].astype(np.float64), axis=0, zi=zi)
        y[s:e] = seg
    return y


def ring_mod(x, sr, p, rng):
    """The stem multiplied by a sine carrier."""
    t = np.arange(len(x), dtype=np.float64) / sr
    return (x * np.sin(2.0 * math.pi * float(p['freq_hz']) * t)[:, None]).astype(np.float32)


def tremolo(x, sr, p, rng):
    """Level dips by `depth` once per cycle (starting at full level); `pan_depth` swings the sound between the channels."""
    t = np.arange(len(x), dtype=np.float64) / sr
    lfo = 0.5 - 0.5 * np.cos(2.0 * math.pi * float(p['rate_hz']) * t)         # 0 at t = 0
    depth, pan = float(p['depth']), float(p['pan_depth'])
    left = (1.0 - depth * lfo) * (1.0 - pan * lfo)
    right = (1.0 - depth * lfo) * (1.0 - pan * (1.0 - lfo))
    return (x * np.stack([left, right], axis=1)).astype(np.float32)


def gate_pulse(x, sr, p, rng):
    """A rhythmic gate: open for `duty` of every pulse, `floor_db` while closed, edges smoothed over `smooth_ms`."""
    t = np.arange(len(x), dtype=np.float64) / sr
    opened = ((t * float(p['rate_hz'])) % 1.0 < float(p['duty'])).astype(np.float64)
    k = max(1, int(round(float(p['smooth_ms']) * sr / 1000.0)))
    smooth = uniform_filter1d(opened, size=k, mode='nearest') if k > 1 else opened
    floor = core.db(p['floor_db'])
    return (x * (floor + (1.0 - floor) * smooth)[:, None]).astype(np.float32)


def transient(x, sr, p, rng):
    """`dsp.transient_shaper`: attack and sustain in dB."""
    import dsp
    return dsp.transient_shaper(x, sr, attack=float(p['attack_db']), sustain=float(p['sustain_db']))
