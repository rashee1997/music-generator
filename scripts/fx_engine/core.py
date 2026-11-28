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

"""core.py - the few helpers every effect shares: shapes, a range mask, a time-varying read and levels."""
import numpy as np


def stereo(x):
    """(n, 2) float32 from a mono vector or an (n, 1) / (n, 2) array."""
    y = np.asarray(x, dtype=np.float32)
    if y.ndim == 1:
        y = y[:, None]
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    return np.ascontiguousarray(y[:, :2])


def span(p, n, sr):
    """(i0, i1) sample range of an effect's start_s / end_s, clipped to the stem. i1 is exclusive; empty gives i0 == i1."""
    i0 = int(round(float(p.get('start_s') or 0.0) * sr))
    end = p.get('end_s')
    i1 = n if end is None else int(round(float(end) * sr))
    i0 = max(0, min(n, i0))
    i1 = max(i0, min(n, i1))
    return i0, i1


def range_mask(n, i0, i1, edge_samples):
    """A float32 mask of length n: 1 inside [i0, i1), 0 outside, with raised-cosine edges of `edge_samples` that sit inside the
    range, so the effect never leaks outside the times the preset gave it."""
    m = np.zeros(n, dtype=np.float32)
    if i1 <= i0:
        return m
    m[i0:i1] = 1.0
    e = int(min(edge_samples, (i1 - i0) // 2))
    if e >= 2:
        ramp = (0.5 - 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, e))).astype(np.float32)
        m[i0:i0 + e] = ramp
        m[i1 - e:i1] = ramp[::-1]
    return m


def read_at(x, pos):
    """x (n, ch) read at fractional sample positions `pos` (m,), linear interpolation, zero outside the signal. Only the part
    of the signal the positions touch is looked at, so reading a short grain from a long stem costs the grain."""
    pos = np.asarray(pos, dtype=np.float64)
    n, ch = x.shape
    out = np.zeros((len(pos), ch), dtype=np.float32)
    if pos.size == 0 or n == 0:
        return out
    lo = max(0, int(np.floor(pos.min())) - 1)
    hi = min(n, int(np.ceil(pos.max())) + 2)
    if hi <= lo:
        return out
    idx = np.arange(lo, hi, dtype=np.float64)
    for c in range(ch):
        out[:, c] = np.interp(pos, idx, x[lo:hi, c].astype(np.float64), left=0.0, right=0.0)
    return out


def rms(x):
    x = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


def match_rms(y, target_rms):
    """y scaled so its RMS is target_rms (unchanged when y is silent)."""
    r = rms(y)
    return y if r < 1e-12 else (y * np.float32(target_rms / r)).astype(np.float32)


def db(x):
    return float(10.0 ** (float(x) / 20.0))
