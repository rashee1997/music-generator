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
"""calibrate.py - one place where energy becomes a level, and normalization is a declared choice.

The audit found normalization doing the wrong job in five places: every rain render was peak-normalized, a light impact
and a heavy one came out at the same peak, model event voices were forced to peak 1, continuous voices to RMS 0.25, and
the environment renderer then re-normalized the layers to RMS 0.1 before applying gain_db. A physical model cannot own
its intensity while that happens, so here it is one function, once, at the end:

    normalize "energy"  the physical amplitude decides the level (default). level_db trims, and that is all.
    normalize "none"    the same thing, kept as a name for scenes that want to say it explicitly.
    normalize "peak"    scale to peak_ceiling. Explicitly requested only; it destroys intensity relationships.
    normalize "rms"     scale to level_db dBFS RMS. Same caveat.

Amplitude from energy: sound pressure is proportional to the square root of the radiated energy, so a break that
releases 4x the energy is 6 dB louder, not "normalized to 0.9". `reference_j` is the energy that maps to 0 dB before
level_db, and it is one constant for the whole engine so it cannot hide a per-sound fudge.
"""
import numpy as np

REFERENCE_J = 1.0
PEAK_CEILING = 0.99
NORMALIZE = ('energy', 'none', 'peak', 'rms')


def amplitude(energy_j, reference_j=REFERENCE_J):
    """Linear amplitude for a radiated energy: sqrt(E / E_ref)."""
    return float(np.sqrt(max(float(energy_j), 0.0) / max(float(reference_j), 1e-12)))


def problems(cal):
    out = []
    if not isinstance(cal, dict):
        return ['calibration: must be an object {"normalize": ..., "level_db": ...}']
    for k in cal:
        if k not in ('normalize', 'level_db', 'reference_j', 'peak_ceiling'):
            out.append(f'calibration: unknown key "{k}" (known: normalize, level_db, reference_j, peak_ceiling)')
    n = cal.get('normalize', 'energy')
    if n not in NORMALIZE:
        out.append(f'calibration.normalize "{n}": use one of {", ".join(NORMALIZE)}')
    for k in ('level_db', 'reference_j', 'peak_ceiling'):
        if k in cal and (isinstance(cal[k], bool) or not isinstance(cal[k], (int, float))):
            out.append(f'calibration.{k}: needs a number')
    return out


def apply(x, cal=None, sr=None):
    """Return (audio, report). The report says what was done, so a render can never silently be normalized."""
    cal = cal or {}
    x = np.asarray(x, dtype=float)
    if not np.isfinite(x).all():               # a solver blow-up must be named here, not discovered in the mixer
        bad = int(np.sum(~np.isfinite(x)))
        raise ValueError(f'calibration input has {bad} non-finite sample(s): the sound model produced NaN/Inf, '
                         f'check the scene values (materials, gain, reference_j)')
    hp_hz = float(cal.get('highpass_hz', 18.0))    # <= 0 keeps sub-bass fundamental weight (a 25 Hz impact)
    if sr and x.size > 64:                     # no DC and no sub-audible offset in a delivered sound
        from scipy.signal import butter, sosfilt
        if hp_hz > 0:
            x = sosfilt(butter(2, hp_hz, btype='highpass', fs=sr, output='sos'), x)
            hp_hz = round(hp_hz, 2)
        x = x - float(np.mean(x))
    mode = cal.get('normalize', 'energy')
    level_db = float(cal.get('level_db', 0.0))
    ceiling = float(cal.get('peak_ceiling', PEAK_CEILING))
    report = dict(normalize=mode, level_db=level_db, highpass_hz=hp_hz)
    if x.size == 0:
        return x, report
    peak = float(np.abs(x).max())
    if mode == 'peak' and peak > 0:
        # scale to the ceiling FIRST, then apply level_db: doing it the other way round divided the declared
        # level straight back out, so a scene asking for -6 dBFS landed at full scale
        x = x / peak * min(ceiling, 1.0)
        x = x * 10.0 ** (level_db / 20.0)
        report['scaled_to_peak'] = round(peak, 4)
        report['level_applied'] = True
    elif mode == 'rms':
        x = x * 10.0 ** (level_db / 20.0)
        rms = float(np.sqrt(np.mean(x ** 2)))
        if rms > 1e-12:
            target = 10.0 ** (level_db / 20.0)
            x = x / rms * target
            report['scaled_to_rms'] = round(rms, 6)
    else:
        x = x * 10.0 ** (level_db / 20.0)
    # a hard ceiling is a safety net, not normalization: it only touches a render that would clip, and says so
    peak = float(np.abs(x).max())
    if peak > ceiling and peak > 0:
        x = x * (ceiling / peak)
        report['ceiling_applied'] = round(peak, 4)
    report['peak'] = round(float(np.abs(x).max()), 6)
    report['rms_db'] = round(20 * float(np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)), 3)
    return x, report
