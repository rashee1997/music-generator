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

"""tract.py - the body that colours a call: a tube, a branched vocal tract, or a bank of formants.

    tube          closed at the source, open at the mouth: resonances (2k - 1) c / (4 L), c of the animal's medium
    tract         N segments [length_m, area_cm2] from the source to the mouth, optional closed side branches (nasal
                  passage, air sac, laryngeal ventricle), wall loss alpha (Np/m). Its transfer function is computed with
                  chain (ABCD) matrices: U_mouth / U_source = 1 / D, D the lower-right element of the product
    formant_bank  explicit [f_hz, bandwidth_hz, gain_db]

A tract is turned into resonators by PEAK PICKING: one two-pole resonator at each peak of |H| (frequency exact, bandwidth
from the -3 dB width). A linear-prediction fit was tried and rejected on evidence: for a two-tube tract (0.17 m at 2 cm2,
0.17 m at 8 cm2, true F1 357 Hz) LPC order 12 put F1 at 782 Hz and order 24 at 542 Hz, and order 40 needed poles at radius
0.9997, too close to the unit circle for float32 (tests/test_biome_fauna.py asserts the bank is right where LPC-12 is not).
Known limit: the parallel bank has the right formant positions but only an approximate spectral shape; it is a timbre
model, not a measurement of an animal.
"""
import numpy as np
from scipy import signal

from env_engine import calls

RES_KINDS = ('tube', 'tract', 'formant_bank')
RES_KEYS = {
    'tube': ('kind', 'length_cm', 'count', 'q', 'mix'),
    'tract': ('kind', 'segments', 'branches', 'alpha_np_m', 'mix', 'max_formants'),
    'formant_bank': ('kind', 'formants', 'mix'),
}
BRANCH_KEYS = ('after_segment', 'length_m', 'area_cm2')


def problems(res, where='resonator'):
    if res is None:
        return []
    if not isinstance(res, dict):
        return [f'{where}: an object with a "kind"']
    kind = res.get('kind')
    if kind not in RES_KINDS:
        return [f'{where}.kind "{kind}": use one of {", ".join(RES_KINDS)}']
    out = [f'{where}: unknown key "{k}" for {kind} (known: {", ".join(RES_KEYS[kind])})' for k in res if k not in RES_KEYS[kind]]
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)    # noqa: E731
    if 'mix' in res and not (num(res['mix']) and 0.0 <= res['mix'] <= 1.0):
        out.append(f'{where}.mix: a number from 0 to 1')
    if kind == 'tube':
        if not (num(res.get('length_cm')) and 0.05 <= res['length_cm'] <= 5000):
            out.append(f'{where}.length_cm: a number from 0.05 to 5000')
        if 'q' in res and not (num(res['q']) and 0.5 <= res['q'] <= 200):
            out.append(f'{where}.q: a number from 0.5 to 200 (starting value 6)')
    elif kind == 'tract':
        seg = res.get('segments')
        if not (isinstance(seg, list) and seg and all(isinstance(s, list) and len(s) == 2 and all(num(x) and x > 0 for x in s) for s in seg)):
            out.append(f'{where}.segments: [[length_m, area_cm2], ...], all positive')
        n = len(seg) if isinstance(seg, list) else 0
        for i, b in enumerate(res.get('branches') or []):
            if not isinstance(b, dict) or any(k not in BRANCH_KEYS for k in b) or any(k not in b for k in BRANCH_KEYS):
                out.append(f'{where}.branches[{i}]: {{"after_segment", "length_m", "area_cm2"}}')
            elif not (isinstance(b['after_segment'], int) and 0 <= b['after_segment'] < n - 1):
                out.append(f'{where}.branches[{i}].after_segment: a junction between two segments, 0 to {max(n - 2, 0)}')
        if 'alpha_np_m' in res and not (num(res['alpha_np_m']) and 0.0 <= res['alpha_np_m'] <= 5.0):
            out.append(f'{where}.alpha_np_m: a number from 0 to 5')
    else:
        f = res.get('formants')
        if not (isinstance(f, list) and f and all(isinstance(r, list) and len(r) == 3 and all(num(x) for x in r) and r[0] > 0 and r[1] > 0 for r in f)):
            out.append(f'{where}.formants: [[f_hz, bandwidth_hz, gain_db], ...]')
    return out


def abcd_response(freqs, segments, c, rho, alpha_np_m=0.0, branches=()):
    """Volume-velocity transfer function (mouth over source) of a tract on a frequency grid, complex.

    Source end closed (a velocity source), mouth open (zero pressure). Each segment is [[cos kL, j Z sin kL],
    [j sin kL / Z, cos kL]] with Z = rho c / A and a complex wavenumber k = w / c - j alpha; a closed side branch of
    length L_b and area A_b is a shunt admittance j (A_b / rho c) tan(k L_b) at its junction."""
    f = np.asarray(freqs, dtype=float)
    k = 2.0 * np.pi * f / float(c) - 1j * float(alpha_np_m)
    K = np.broadcast_to(np.eye(2, dtype=complex), (len(f), 2, 2)).copy()
    by_junction = {}
    for b in branches:
        by_junction.setdefault(int(b['after_segment']), []).append(b)
    for i, (length, area_cm2) in enumerate(segments):
        z = float(rho) * float(c) / (float(area_cm2) * 1e-4)
        cs, sn = np.cos(k * float(length)), np.sin(k * float(length))
        M = np.empty((len(f), 2, 2), dtype=complex)
        M[:, 0, 0], M[:, 0, 1], M[:, 1, 0], M[:, 1, 1] = cs, 1j * z * sn, 1j * sn / z, cs
        K = K @ M
        for b in by_junction.get(i, []):
            y = 1j * (float(b['area_cm2']) * 1e-4 / (float(rho) * float(c))) * np.tan(k * float(b['length_m']))
            S = np.empty((len(f), 2, 2), dtype=complex)
            S[:, 0, 0], S[:, 0, 1], S[:, 1, 0], S[:, 1, 1] = 1.0, 0.0, y, 1.0
            K = K @ S
    return 1.0 / K[:, 1, 1]


def pick_formants(freqs, H, max_formants=24, rel_prominence=0.02):
    """[(f_hz, bandwidth_hz, gain 0..1)] at the peaks of |H|, strongest first dropped last (lowest frequencies kept)."""
    mag = np.abs(H)
    pk, _ = signal.find_peaks(mag, prominence=rel_prominence * float(mag.max()))
    df = float(freqs[1] - freqs[0])
    out = []
    for p in pk:
        half = mag[p] / np.sqrt(2.0)
        lo = p
        while lo > 0 and mag[lo] > half:
            lo -= 1
        hi = p
        while hi < len(mag) - 1 and mag[hi] > half:
            hi += 1
        out.append((float(freqs[p]), max(float(freqs[hi] - freqs[lo]), 2.0 * df), float(mag[p] / mag.max())))
    return out[:int(max_formants)]


def design(res, medium, sr, scale=1.0):
    """The formant list [(f_hz, bw_hz, gain)] of a resonator preset in the animal's medium. `scale` is the animal's own size
    factor (pitch scale of calls.py): a smaller animal has a shorter tube, so formants rise by `scale`."""
    kind = res['kind']
    if kind == 'tube':
        q = float(res.get('q', 6.0))
        fs = calls.tube_formants(res['length_cm'], sr, int(res.get('count', 5)), c=medium.c)
        return [(f * scale, f * scale / q, 1.0 / (i + 1)) for i, f in enumerate(fs) if f * scale < 0.45 * sr]
    if kind == 'formant_bank':
        return [(f * scale, bw, 10.0 ** (g / 20.0)) for f, bw, g in res['formants'] if f * scale < 0.45 * sr]
    grid = np.linspace(20.0, 0.45 * sr / scale, 4096)
    H = abcd_response(grid, [(L / scale, A) for L, A in res['segments']], medium.c, medium.rho, res.get('alpha_np_m', 0.0),
                      [dict(b, length_m=b['length_m'] / scale) for b in res.get('branches') or []])
    return [(f, bw, g) for f, bw, g in pick_formants(grid, H, res.get('max_formants', 24))]


def apply(x, formants, sr, mix=0.7):
    """Colour x with a parallel bank of two-pole resonators; the wet signal takes x's rms so `mix` changes timbre, not level."""
    x = np.asarray(x, dtype=np.float64)
    if not len(x) or not formants:
        return x
    wet = np.zeros(len(x))
    for f, bw, g in formants:
        r = np.exp(-np.pi * max(bw, 1.0) / sr)
        th = 2.0 * np.pi * f / sr
        a = [1.0, -2.0 * r * np.cos(th), r * r]
        b = [(1.0 - r) * np.sin(th)]
        wet += g * signal.lfilter(b, a, x)
    rw, rx = float(np.sqrt(np.mean(wet ** 2))), float(np.sqrt(np.mean(x ** 2)))
    if rw > 0 and rx > 0:
        wet *= rx / rw
    return (1.0 - float(mix)) * x + float(mix) * wet
