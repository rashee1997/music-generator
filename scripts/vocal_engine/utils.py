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

"""Small shared DSP helpers (vectorised, O(n))."""
import numpy as np
from scipy.signal import lfilter


def smooth_noise(rng, n, sr, rate_hz=6.0):
    """Unit-std slow random curve: random knots at ~rate_hz, linear interpolation, one-pole smoothing. O(n)."""
    n = int(n)
    if n <= 0:
        return np.zeros(0)
    m = max(4, int(n / sr * rate_hz) + 4)
    knots = rng.standard_normal(m)
    x = np.interp(np.linspace(0, m - 1, n), np.arange(m), knots)
    a = np.exp(-2 * np.pi * rate_hz * 0.5 / sr)
    x = lfilter([1 - a], [1, -a], x)
    return x / (x.std() + 1e-9)


def one_pole_lp(x, fc, sr):
    a = float(np.exp(-2 * np.pi * min(fc, 0.45 * sr) / sr))
    return lfilter([1 - a], [1, -a], x)


def drift_walk(rng, n, sr, rate_hz=0.35):
    """Mean-reverting random walk (Ornstein-Uhlenbeck), unit std, corner at `rate_hz`. O(n).

    A singer's intonation is not a fixed offset: it wanders slowly and comes back. The one-pole on white
    noise gives that: 1/f^2 below nothing, `rate_hz` as the corner, and it cannot run away from centre.
    """
    n = int(n)
    if n <= 0:
        return np.zeros(0)
    a = float(np.exp(-2 * np.pi * max(float(rate_hz), 1e-3) / sr))
    x = lfilter([1.0 - a], [1.0, -a], rng.standard_normal(n))
    return x / (x.std() + 1e-9)


def dc_block(x, r=0.9995):
    return lfilter([1, -1], [1, -r], x)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
