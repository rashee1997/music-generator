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


def _detrend_cycles(x):
    """Remove the slow arc of a per-cycle series (a note's swell and decay), leaving what moves faster than it.
    A quadratic, because a moving average wide enough to kill the arc would also flatten the vibrato."""
    x = np.asarray(x, dtype=float)
    if len(x) < 8:
        return x - float(np.mean(x))
    t = np.linspace(-1.0, 1.0, len(x))
    return x - np.polyval(np.polyfit(t, x, 2), t)


def _smooth3(x):
    """Three-cycle smoothing: follows a vibrato (tens of cycles long) but not cycle-to-cycle noise."""
    x = np.asarray(x, dtype=float)
    if len(x) < 5:
        return x
    return np.convolve(x, np.array([0.25, 0.5, 0.25]), mode='same')


def _vib_band(la, lp, dur_s, half_width=1):
    """Take only the band where the pitch actually oscillates. Cycle-to-cycle noise (shimmer, a changing
    pulse shape) is spread over every frequency, so a correlation over the whole series measures the noise;
    the band around the pitch modulation's own peak measures the modulation."""
    n = len(la)
    if n < 24:
        return None
    mag = np.abs(np.fft.rfft(lp))
    kmin = max(3, int(2.0 * float(dur_s)))         # faster than 2 Hz is a vibrato; slower is a drift
    kmax = min(len(mag) - 1, max(kmin + 1, int(12.0 * float(dur_s))))   # and a vibrato is not a flutter
    if kmin >= kmax:
        return None
    band_mag = mag[kmin:kmax + 1]
    k = kmin + int(np.argmax(band_mag))
    if mag[k] <= 3.0 * float(np.median(band_mag)):     # no clear oscillation: do not report noise as a vibrato
        return None
    mag[:] = 0.0
    mag[k] = 1.0
    m = np.zeros(len(mag))
    m[max(1, k - half_width):min(len(mag), k + half_width + 1)] = 1.0
    a = np.fft.irfft(np.fft.rfft(la) * m, n)
    b = np.fft.irfft(np.fft.rfft(lp) * m, n)
    if a.std() <= 0 or b.std() <= 0:
        return None
    return a, b


def glottal_source(f0, sr, rng, reg, breathiness=0.03, phase0=0.0, subharmonic=False, sub_weight=0.65, stats_gate=None,
                   stats_notes=None,
                   whistle_hz=0.0, whistle_weight=0.45, aspiration_depth=0.65, tilt_hz=None,
                   jitter_pct=0.0, jitter_shimmer_corr=0.5, sub_extra=0.0, stats=None, amp_mod=None):
    """f0: Hz per sample. reg: dict(open_quotient, speed_quotient, closure, tilt_hz, shimmer); each value scalar
    or per-sample array. Returns (source, cycles, flow). Voiced part has unit RMS, so dynamics are applied later.

    `jitter_pct` is period-to-period perturbation in percent (Titze 1994: local jitter ~0.5-1 % is normal), drawn once
    per cycle. A smooth 7 Hz noise on the pitch curve is flutter, which is a different phenomenon and stays in
    performance.jitter_cents. `jitter_shimmer_corr` shares one latent draw, so period and amplitude perturbation are
    correlated the way a real voice's are. `sub_extra` adds a period-doubling track (vocal creak)."""
    f0 = np.asarray(f0, dtype=float)
    n = len(f0)
    if n == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    jit = max(float(jitter_pct), 0.0) * 1e-2
    shimmer = float(np.mean(reg.get('shimmer', 0.0)))
    f0_eff, z, idx, m = f0, None, None, 0
    if jit > 0 or shimmer > 0 or amp_mod is not None:
        base = cycles(f0, sr, phase0)                        # cycle index from the unperturbed phase
        idx = (np.floor(base) - np.floor(base[0])).astype(int)
        m = int(idx[-1]) + 1
    if jit > 0 or shimmer > 0:
        z = rng.standard_normal(m)
        w = rng.standard_normal(m)
        corr = float(np.clip(jitter_shimmer_corr, -1.0, 1.0))
        per = corr * z + np.sqrt(max(0.0, 1.0 - corr * corr)) * w
        if jit > 0:
            f0_eff = f0 * np.maximum(1.0 + jit * per[idx], 0.2)
    c = cycles(f0_eff, sr, phase0)
    phi = c - np.floor(c)
    g = pulse(phi, reg['open_quotient'], reg['speed_quotient'], reg['closure'])
    d = _radiate(g, f0_eff, sr)
    if shimmer > 0 and z is not None:
        d = d * np.maximum(1.0 + shimmer * z[idx], 0.05)
    sub_total = np.asarray(sub_weight * float(subharmonic), dtype=float) + np.asarray(sub_extra, dtype=float)
    sub_total = np.broadcast_to(sub_total, (n,)).astype(float)
    if np.any(sub_total > 0):
        c2 = c / 2.0
        d = d + sub_total * _radiate(pulse(c2 - np.floor(c2), reg['open_quotient'], reg['speed_quotient'],
                                           reg['closure']), 0.5 * f0_eff, sr)
    d = _tilt(d, reg['tilt_hz'] if tilt_hz is None else tilt_hz, sr)
    d = d / (rms(d) + 1e-12)
    if whistle_hz and whistle_hz > 0:
        h = max(1, int(round(whistle_hz / float(np.mean(f0)))))
        d = d + whistle_weight * np.sin(2 * np.pi * np.cumsum(f0 * h) / sr)
    if np.any(np.asarray(breathiness) > 0):                       # scalar or per-sample track
        noise = lfilter([1, -1], [1, -0.7], rng.standard_normal(n))
        noise = noise * ((1.0 - aspiration_depth) + aspiration_depth * g)
        d = d + breathiness * noise / (rms(noise) + 1e-12)
    if amp_mod is not None:                                      # level oscillates with the vibrato
        d = d * amp_mod
    if stats is not None and idx is not None and m > 2:          # what this source really played, cycle by cycle
        cnt = np.bincount(idx, minlength=m).astype(float)
        ok = cnt > 0
        per_cycle = np.bincount(idx, weights=1.0 / np.maximum(f0_eff, 1e-6), minlength=m)[ok]
        if jit > 0 and len(per_cycle) >= 3:
            stats['jitter_pct'] = float(100.0 * np.mean(np.abs(np.diff(per_cycle))) / np.mean(per_cycle))
        if amp_mod is not None and len(per_cycle) >= 8:
            amp = np.sqrt(np.bincount(idx, weights=d * d, minlength=m)[ok] / cnt[ok]) + 1e-12
            keep = amp > 0.1 * np.median(amp)                        # rests have no period worth measuring
            if stats_gate is not None:                               # only where the vibrato is developed
                keep &= np.bincount(idx, weights=np.asarray(stats_gate, float), minlength=m)[ok] > 0.5 * cnt[ok]
            keep &= per_cycle < 1.35 * np.median(per_cycle)          # creak's double-length cycles are not vibrato
            cnote = None
            if stats_notes is not None:
                starts = np.searchsorted(idx, np.arange(m))          # first sample of every cycle
                nid = np.asarray(stats_notes, dtype=int)
                cnote = nid[np.clip(starts, 0, len(nid) - 1)][ok][keep]
            amp, per_cycle = amp[keep], per_cycle[keep]
            if len(amp) >= 8:
                # the attack and the release move the level far more than the vibrato does: keep the steady body
                body = np.abs(_smooth3(_smooth3(np.log(amp))) - np.median(np.log(amp))) < 1.15
                if int(body.sum()) >= 8:
                    amp, per_cycle = amp[body], per_cycle[body]
                    if cnote is not None:
                        cnote = cnote[body]
                runs = []
                if cnote is not None and len(np.unique(cnote)) > 1:
                    for u in np.unique(cnote):     # one note at a time: a step between notes is not a vibrato
                        sel = cnote == u
                        if int(sel.sum()) >= 12:
                            runs.append((amp[sel], per_cycle[sel]))
                if not runs:
                    runs = [(amp, per_cycle)]
                cs, ds, ws = [], [], []
                for a_, p_ in runs:
                    # level against pitch: a shorter cycle is a higher note. The note's own swell is removed so
                    # it cannot masquerade as the modulation.
                    la = _detrend_cycles(np.log(a_))
                    lp = _detrend_cycles(-np.log(p_))
                    if la.std() <= 0 or lp.std() <= 0:
                        continue
                    band = _vib_band(la, lp, len(a_) / max(float(np.mean(f0_eff)), 1.0))
                    if band is None:
                        continue
                    a, b = band
                    cs.append(float(len(a_)) * float(np.corrcoef(a, b)[0, 1]))
                    ds.append(float(np.ptp(np.percentile(a, [3, 97]))) * 8.685889638)
                    ws.append(float(len(a_)))
                if ws:
                    stats['vib_am_corr'] = sum(cs) / sum(ws)
                    stats['vib_am_db'] = max(ds)
    return d, c, g
