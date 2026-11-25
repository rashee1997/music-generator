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
import json

import numpy as np
from scipy.signal import lfilter

from . import waveguide as wg
from .tract import bank, resonate
from .utils import one_pole_lp, rms

_JUNCTION = {}


def junction(h, wv):
    """Poles, bandwidths and the oral-side zero measured from the 3-way pharynx junction.

    Nothing here is dialled in. The mouth is closed, so the oral branch is a short-circuited side branch whose input
    impedance falls to zero at c/(4 l_oral) - that is the /m/ antiformant, and it needs no constant. The murmur poles
    are the resonances of the same branched network. The 1 kHz figure in `humming.antiformant_hz` survives only as an
    override (`antiformant_from_junction: false`) for a preset that was voiced against it.

    Measured for the configured geometry: first nasal pole ~204 Hz, first null ~822 Hz against c/(4*0.099) = 870 Hz.
    """
    key = json.dumps([wv['nasal'], float(wv['tract_length_m']), int(wv['sections']), wv['losses'], wv['radiation'],
                      h['nasal_poles'], h.get('antiformant_hz')], sort_keys=True, default=str)
    hit = _JUNCTION.get(key)
    if hit is not None:
        return hit
    n = wv['nasal']
    L = float(wv['tract_length_m'])
    l_ph = L * float(n['velum_fraction'])
    l_or = L * (1.0 - float(n['velum_fraction']))
    a_ph = np.full(max(4, int(wv['sections']) // 3), float(n['pharynx_area_cm2']) * 1e-4)
    a_or = np.full(max(4, int(wv['sections']) // 2), float(n['oral_area_cm2']) * 1e-4)
    a_na = np.full(int(n['nasal_sections']), float(n['nasal_area_cm2']) * 1e-4)
    f = np.linspace(80.0, 4000.0, 981)
    mag = np.abs(wg.nasal_response(f, a_ph, l_ph, a_or, l_or, a_na, float(n['nasal_length_m']), wv))
    pk = np.nonzero((mag[1:-1] > mag[:-2]) & (mag[1:-1] > mag[2:]))[0] + 1
    lo = np.nonzero((mag[1:-1] < mag[:-2]) & (mag[1:-1] < mag[2:]))[0] + 1
    band = (f[lo] > 400.0) & (f[lo] < 3000.0)
    zero = float(f[lo][band][int(np.argmin(mag[lo][band]))]) if band.any() else float(h['antiformant_hz'])
    k = len(h['nasal_poles'])
    F = np.array([p['hz'] for p in h['nasal_poles']], dtype=float)
    BW = np.array([p['bw'] for p in h['nasal_poles']], dtype=float)
    if len(pk) >= k:
        F = f[pk][:k]
        BW = wg.bandwidths(f, mag, F)
    else:                                            # fewer junction poles than the config names: keep the rest
        F[:len(pk)] = f[pk]
    out = (F, BW, zero)
    _JUNCTION[key] = out
    return out


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


def hum_branch(src, sr, h, rng, flow=None, block=220, wv=None):
    """Source -> nasal tract. h: humming config, wv: the waveguide config (None keeps the table).

    Returns the signal (not level-normalised). In `physical` mode the poles and the zero come from the junction; the
    per-pole gains and the brightness tilt stay in the config, because brightness is a preset decision about the
    singer, not a property of the tube.
    """
    poles = h['nasal_poles']
    sc = float(h.get('nasal_scale', 1.0))            # singer's nasal cavity size, not the piece's
    k = len(poles)
    physical = wv is not None and wv.get('mode', 'physical') == 'physical'
    if physical:
        Fj, BWj, zero = junction(h, wv)
        F = [float(x) * sc for x in Fj]
        BW = [float(x) for x in BWj]
    else:
        F = [p['hz'] * sc for p in poles]
        BW = [p['bw'] for p in poles]
        zero = float(h['antiformant_hz']) * sc
    G = [p['gain'] * 10 ** (_brightness_db(h['brightness'], i, k) / 20.0) * h['murmur_gain'] for i, p in enumerate(poles)]
    y = bank(src, F, BW, G, sr, block)
    if h['oral_coupling'] > 0:
        oral = [f * sc for f in h['oral_formants']]
        y = y + h['oral_coupling'] * bank(src, oral, h['oral_bandwidths'], [1.0, 0.6, 0.3], sr, block)
    if not physical or not h.get('antiformant_from_junction', True):
        zero = float(h['antiformant_hz']) * sc
    y = notch(y, zero, h['antiformant_bw'], h['antiformant_depth'], sr)
    lp = float(h['lip_closure_hz']) * 2.0 ** (2.0 * (float(h['brightness']) - 0.5))
    y = one_pole_lp(one_pole_lp(y, lp, sr), lp, sr)
    if h['airflow'] > 0 and len(y):
        air = one_pole_lp(one_pole_lp(rng.standard_normal(len(y)), h['airflow_hz'], sr), h['airflow_hz'], sr)
        if flow is not None:
            air = air * (0.4 + 0.6 * flow)
        y = y + h['airflow'] * rms(y) * air / (rms(air) + 1e-12)
    return y


def nasalize(y, src, sr, amount, h, block=220, wv=None):
    """Blend nasal colour into an open vowel: low nasal pole added, oral anti-formant notch, a little less top.

    The pole and the zero are the junction's when `wv` is passed in physical mode - partial nasalisation has the same
    antiresonance as a full hum, it is only weaker.
    """
    a = float(np.clip(amount, 0.0, 1.0))
    if a <= 0:
        return y
    sc = float(h.get('nasal_scale', 1.0))
    physical = wv is not None and wv.get('mode', 'physical') == 'physical'
    p = h['nasal_poles'][0]
    hz, bw, zero = p['hz'], p['bw'], float(h['antiformant_hz'])
    if physical:
        Fj, BWj, zj = junction(h, wv)
        hz, bw = float(Fj[0]), float(BWj[0])
        if h.get('antiformant_from_junction', True):
            zero = zj
    low = resonate(src, hz * sc, bw, sr, block) * p['gain']
    out = (1.0 - 0.35 * a) * y + a * 0.6 * rms(y) * low / (rms(low) + 1e-12)
    return notch(out, zero * sc, h['antiformant_bw'], h['antiformant_depth'] * a, sr)
