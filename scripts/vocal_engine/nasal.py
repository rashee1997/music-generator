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

"""Nasal humming model (closed lips, sound leaves through the nose).

Structure, after the /m/ murmur literature: a strong low nasal resonance (~250-300 Hz), weaker wide upper nasal
poles, an oral-side anti-formant (a notch where the closed oral cavity side-branch cancels, ~1 kHz for bilabials),
a weak coupled oral-cavity branch, a lip-closure low-pass that sets how much high frequency survives, and a small
pulse-modulated nasal airflow noise. All values come from the `humming` config section.
"""
import numpy as np
from scipy.signal import lfilter

from .tract import bank, resonate
from .utils import one_pole_lp, rms


def notch(x, f, bw, depth, sr):
    """Anti-formant: zero pair at radius rz, pole pair at rp, unity gain at DC. depth 0 = flat, 1 = full null."""
    th = 2 * np.pi * min(f, 0.45 * sr) / sr
    rp = np.exp(-np.pi * max(bw, 5.0) / sr)
    rz = 1.0 - (1.0 - rp) * (1.0 - float(np.clip(depth, 0.0, 1.0)))
    b = np.array([1.0, -2 * rz * np.cos(th), rz * rz])
    a = np.array([1.0, -2 * rp * np.cos(th), rp * rp])
    b = b * (a.sum() / b.sum())
    return lfilter(b, a, x)


def _brightness_db(brightness, i, k):
    """Upper nasal poles get -/+ up to 12 dB across the range of `brightness` (0..1, 0.5 neutral)."""
    return (float(brightness) - 0.5) * 24.0 * (i / max(1, k - 1))


def hum_branch(src, sr, h, rng, flow=None, block=220):
    """Source -> nasal tract. h: humming config. Returns the signal (not level-normalised)."""
    poles = h['nasal_poles']
    k = len(poles)
    F = [p['hz'] for p in poles]
    BW = [p['bw'] for p in poles]
    G = [p['gain'] * 10 ** (_brightness_db(h['brightness'], i, k) / 20.0) * h['murmur_gain'] for i, p in enumerate(poles)]
    y = bank(src, F, BW, G, sr, block)
    if h['oral_coupling'] > 0:
        y = y + h['oral_coupling'] * bank(src, h['oral_formants'], h['oral_bandwidths'], [1.0, 0.6, 0.3], sr, block)
    y = notch(y, h['antiformant_hz'], h['antiformant_bw'], h['antiformant_depth'], sr)
    lp = float(h['lip_closure_hz']) * 2.0 ** (2.0 * (float(h['brightness']) - 0.5))
    y = one_pole_lp(one_pole_lp(y, lp, sr), lp, sr)
    if h['airflow'] > 0 and len(y):
        air = one_pole_lp(one_pole_lp(rng.standard_normal(len(y)), h['airflow_hz'], sr), h['airflow_hz'], sr)
        if flow is not None:
            air = air * (0.4 + 0.6 * flow)
        y = y + h['airflow'] * rms(y) * air / (rms(air) + 1e-12)
    return y


def nasalize(y, src, sr, amount, h, block=220):
    """Blend nasal colour into an open vowel: low nasal pole added, oral anti-formant notch, a little less top."""
    a = float(np.clip(amount, 0.0, 1.0))
    if a <= 0:
        return y
    p = h['nasal_poles'][0]
    low = resonate(src, p['hz'], p['bw'], sr, block) * p['gain']
    out = (1.0 - 0.35 * a) * y + a * 0.6 * rms(y) * low / (rms(low) + 1e-12)
    return notch(out, h['antiformant_hz'], h['antiformant_bw'], h['antiformant_depth'] * a, sr)
