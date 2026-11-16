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
from scipy.optimize import brentq
from scipy.signal import lfilter, resample_poly

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


LF_RD = (0.3, 2.7)          # the range Fant's regressions cover: 0.3 pressed, about 1 modal, 2.7 breathy
MODELS = ('pulse', 'lf')
_LF = {}


def lf_params(rd):
    """Timing of one LF period (length 1) from the shape parameter Rd (Fant 1995): (tp, te, ta, alpha, epsilon).
    Ra = (-1 + 4.8 Rd)/100, Rk = (22.4 + 11.8 Rd)/100, Rg = Rk (0.5 + 1.2 Rk) / (4 (0.11 Rd - Ra (0.5 + 1.2 Rk))).
    epsilon closes the return phase at the end of the period; alpha makes the flow return to zero."""
    rd = float(np.clip(rd, *LF_RD))
    ra = (-1.0 + 4.8 * rd) / 100.0
    rk = (22.4 + 11.8 * rd) / 100.0
    rg = rk * (0.5 + 1.2 * rk) / (4.0 * (0.11 * rd - ra * (0.5 + 1.2 * rk)))
    tp = 1.0 / (2.0 * rg)
    te = tp * (1.0 + rk)
    ta = ra
    gap = 1.0 - te
    eps = 1.0 / ta
    for _ in range(60):                                   # eps * ta = 1 - exp(-eps * (1 - te))
        eps = (1.0 - np.exp(-eps * gap)) / ta
    wg = np.pi / tp
    ret = -((1.0 - np.exp(-eps * gap)) / eps - gap * np.exp(-eps * gap)) / (eps * ta)   # area of the return phase

    def net(alpha):                                       # open-phase area + return area, with E(te) = -1
        e = np.exp(alpha * te)
        area = (e * (alpha * np.sin(wg * te) - wg * np.cos(wg * te)) + wg) / (alpha * alpha + wg * wg)
        return -area / (e * np.sin(wg * te)) + ret
    return tp, te, ta, float(brentq(net, -60.0, 120.0)), float(eps)


def _lf_table(points=4096, steps=49):
    """(Rd grid, flow-derivative table, flow table): one LF period per Rd, the flow peaking at 1."""
    if not _LF:
        rds = np.linspace(LF_RD[0], LF_RD[1], steps)
        t = np.arange(points) / points
        E, G = np.zeros((steps, points)), np.zeros((steps, points))
        for i, rd in enumerate(rds):
            tp, te, ta, alpha, eps = lf_params(rd)
            wg = np.pi / tp
            e0 = -1.0 / (np.exp(alpha * te) * np.sin(wg * te))
            d = np.where(t <= te, e0 * np.exp(alpha * t) * np.sin(wg * t),
                         -(np.exp(-eps * (t - te)) - np.exp(-eps * (1.0 - te))) / (eps * ta))
            g = np.cumsum(d) / points
            E[i], G[i] = d / g.max(), np.maximum(g, 0.0) / g.max()
        _LF.update(rds=rds, E=E, G=G)
    return _LF['rds'], _LF['E'], _LF['G']


def lf_pulse(phi, rd):
    """(flow derivative per cycle, flow) of the LF model at phase `phi` (0..1) and shape `rd` (scalar or track)."""
    rds, E, G = _lf_table()
    points = E.shape[1]
    r = np.clip((np.broadcast_to(np.asarray(rd, dtype=float), np.shape(phi)) - rds[0]) / (rds[1] - rds[0]),
                0.0, len(rds) - 1.0 - 1e-9)
    i = r.astype(int)
    fr = r - i
    x = np.asarray(phi, dtype=float) * points
    j = x.astype(int) % points
    fx = x - np.floor(x)
    j1 = (j + 1) % points

    def at(T):
        return (1.0 - fr) * ((1.0 - fx) * T[i, j] + fx * T[i, j1]) + fr * ((1.0 - fx) * T[i + 1, j] + fx * T[i + 1, j1])
    return at(E), at(G)


def _radiate(g, f0, sr):
    """Flow derivative, scaled so its level does not depend on f0."""
    d = np.diff(g, prepend=g[:1])
    return d * sr / np.maximum(f0, 20.0)


def _tilt_once(x, tilt_hz, sr):
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


def _tilt(x, tilt_hz, sr, poles=1):
    """Spectral tilt: one pole is -6 dB/oct above the corner, two is -12 dB/oct (the glottal source's
    natural roll-off). `source.tilt_poles` chooses; 1 reproduces the old one-pole sound exactly."""
    y = _tilt_once(x, tilt_hz, sr)
    for _ in range(max(0, int(poles) - 1)):
        y = _tilt_once(y, tilt_hz, sr)
    return y


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
                   jitter_pct=0.0, jitter_shimmer_corr=0.5, sub_extra=0.0, stats=None, amp_mod=None,
                   tilt_poles=1, model='pulse', oversample=1):
    """The source at `oversample` times the rate, low-passed and decimated: the pulse has a corner at every closure,
    and at soprano pitch its harmonics above half the rate fold back between the real ones. 1 = the engine as it was.
    `model`: "pulse" (the Rosenberg-family flow) or "lf" (Liljencrants-Fant, shaped by reg["rd"])."""
    if model not in MODELS:
        raise ValueError(f'source.model "{model}" is not one of {", ".join(MODELS)}')
    k = int(oversample)
    kw = dict(breathiness=breathiness, phase0=phase0, subharmonic=subharmonic, sub_weight=sub_weight,
              stats_gate=stats_gate, stats_notes=stats_notes, whistle_hz=whistle_hz, whistle_weight=whistle_weight,
              aspiration_depth=aspiration_depth, tilt_hz=tilt_hz, jitter_pct=jitter_pct,
              jitter_shimmer_corr=jitter_shimmer_corr, sub_extra=sub_extra, stats=stats, amp_mod=amp_mod,
              tilt_poles=tilt_poles, model=model)
    n = len(f0)
    if k <= 1 or n == 0:
        return _source(f0, sr, rng, reg, **kw)

    def up(v):                                            # a per-sample track is held for k samples
        return np.repeat(v, k) if isinstance(v, np.ndarray) and v.shape == (n,) else v
    for name in ('breathiness', 'stats_gate', 'stats_notes', 'tilt_hz', 'sub_extra', 'amp_mod'):
        kw[name] = up(kw[name])
    d, c, g = _source(np.repeat(np.asarray(f0, dtype=float), k), sr * k, rng, {a: up(b) for a, b in reg.items()}, **kw)
    return resample_poly(d, 1, k), c[k - 1::k], g[::k]


def _source(f0, sr, rng, reg, breathiness=0.03, phase0=0.0, subharmonic=False, sub_weight=0.65, stats_gate=None,
            stats_notes=None,
            whistle_hz=0.0, whistle_weight=0.45, aspiration_depth=0.65, tilt_hz=None,
            jitter_pct=0.0, jitter_shimmer_corr=0.5, sub_extra=0.0, stats=None, amp_mod=None,
            tilt_poles=1, model='pulse'):
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
    lf = model == 'lf'

    def wave(ph, f):                                      # (flow derivative, flow) of the chosen model
        if lf:
            return lf_pulse(ph, reg.get('rd', 1.0))
        flow = pulse(ph, reg['open_quotient'], reg['speed_quotient'], reg['closure'])
        return _radiate(flow, f, sr), flow
    d, g = wave(phi, f0_eff)
    if shimmer > 0 and z is not None:
        d = d * np.maximum(1.0 + shimmer * z[idx], 0.05)
    sub_total = np.asarray(sub_weight * float(subharmonic), dtype=float) + np.asarray(sub_extra, dtype=float)
    sub_total = np.broadcast_to(sub_total, (n,)).astype(float)
    if np.any(sub_total > 0):
        c2 = c / 2.0
        d = d + sub_total * wave(c2 - np.floor(c2), 0.5 * f0_eff)[0]
    # the LF return phase is the source's own roll-off (set by Rd), so only one pole is left for the tilt that
    # follows loudness; a second would darken it twice
    d = _tilt(d, reg['tilt_hz'] if tilt_hz is None else tilt_hz, sr, poles=1 if lf else tilt_poles)
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
