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

"""Vocal tract: parallel 2-pole resonators with exact unity gain at the centre frequency (the old _resonator's
normalisation used a polynomial evaluated at the wrong point). Formant tracks may move: coefficients change every
`block` samples and the filter state is carried, so there is no restart.
"""
import numpy as np
from scipy.signal import lfilter


def coefs(f, bw, sr):
    """Klatt resonator y = A x + B y1 + C y2 with |H(e^{j theta})| = 1 at theta = 2 pi f / sr. Vectorised over f, bw."""
    f = np.clip(np.asarray(f, dtype=float), 20.0, 0.45 * sr)
    bw = np.maximum(np.asarray(bw, dtype=float), 5.0)
    r = np.exp(-np.pi * bw / sr)
    th = 2 * np.pi * f / sr
    B, C = 2 * r * np.cos(th), -r * r
    z1 = np.exp(-1j * th)
    A = np.abs(1 - B * z1 - C * z1 * z1)
    return A, B, C


def block_track(v, n, block):
    """Per-sample or scalar track -> one value per block (value at the block centre). Scalar stays length 1."""
    v = np.asarray(v, dtype=float)
    if v.ndim == 0 or len(v) == 1:
        return v.reshape(1)
    nb = int(np.ceil(n / block))
    centres = np.minimum((np.arange(nb) * block + block // 2), len(v) - 1)
    return v[centres]


def resonate(x, f, bw, sr, block=220):
    """One resonator with scalar or per-sample f, bw. Unity gain at f."""
    n = len(x)
    f, bw = block_track(f, n, block), block_track(bw, n, block)
    if len(f) == 1 and len(bw) == 1:
        A, B, C = coefs(f[0], bw[0], sr)
        return lfilter([A], [1, -B, -C], x)
    m = max(len(f), len(bw))
    f, bw = np.broadcast_to(f, (m,)), np.broadcast_to(bw, (m,))
    A, B, C = coefs(f, bw, sr)
    y = np.empty(n)
    y_p1, y_p2 = 0.0, 0.0
    for j in range(m):
        s, e = j * block, min(n, (j + 1) * block)
        if s >= n:
            break
        zi = np.array([B[j] * y_p1 + C[j] * y_p2, C[j] * y_p1], dtype=float)
        seg, _ = lfilter([A[j]], [1.0, -B[j], -C[j]], x[s:e], zi=zi)
        y[s:e] = seg
        if len(seg) >= 2:
            y_p1, y_p2 = float(seg[-1]), float(seg[-2])
        elif len(seg) == 1:
            y_p2, y_p1 = y_p1, float(seg[-1])
    return y


def lock_to_harmonics(F, f0, amount):
    """Pull formant centres toward the nearest harmonic of f0 (amount 0..1). F, f0 broadcastable arrays."""
    F, f0 = np.asarray(F, dtype=float), np.maximum(np.asarray(f0, dtype=float), 20.0)
    nearest = np.maximum(np.round(F / f0), 1.0) * f0
    return F + amount * (nearest - F)


def bank(x, F, BW, G, sr, block=220):
    """Parallel resonator bank. F, BW: lists of scalars or per-sample arrays; G: gain per resonator."""
    out = np.zeros(len(x))
    for f, bw, g in zip(F, BW, G):
        out += g * resonate(x, f, bw, sr, block)
    return out
