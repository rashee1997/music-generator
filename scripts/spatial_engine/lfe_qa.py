# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""lfe_qa.py - measurements for a layout with two low-frequency channels, and for its front stage.

Everything here reads a delivered programme (or a layout preset) and reports numbers; the gate rows that judge them
are in spatial_gate.py and their limits in gate_profiles.ROWS. Nothing here changes a signal.

  coherence / polarity / fold_loss   the pair of low-frequency channels against each other, from the file alone
  modal_spread                       a model of what two subs do to the spatial variance of a box room: a model, not a
                                     measurement of the listener's room (positions and size come from the layout preset)
  phantom_fold_error                 the stereo fold of the centre channel against the real centre, through the
                                     measured head set: interaural time and level differences and colour
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt

from . import downmix

C_SOUND = 343.0                      # m/s, 20 C
BAND_HZ = (20.0, 80.0)               # the low-frequency band the checks read; the layout's lowpass_hz replaces the top


def _band(x, sr, lo, hi):
    sos = butter(2, [max(lo, 1.0), min(hi, 0.45 * sr)], btype='band', fs=sr, output='sos')
    return sosfiltfilt(sos, np.asarray(x, dtype=np.float64))


def third_octaves(lo, hi):
    """Centres of 1/3-octave bands from `lo` to `hi` Hz."""
    n = int(np.floor(3.0 * np.log2(hi / lo))) + 1
    return lo * 2.0 ** (np.arange(n) / 3.0)


def coherence(a, b, sr, lo=BAND_HZ[0], hi=BAND_HZ[1]):
    """Zero-lag correlation of two channels inside one band (1 = identical, 0 = unrelated, -1 = opposed)."""
    return downmix.lfe_correlation(_band(a, sr, lo, hi), _band(b, sr, lo, hi))


def coherence_by_band(a, b, sr, lo=BAND_HZ[0], hi=BAND_HZ[1]):
    """[(centre Hz, correlation)] per 1/3 octave from `lo` to `hi`."""
    out = []
    for c in third_octaves(lo, hi):
        f1, f2 = c * 2 ** (-1 / 6.0), min(c * 2 ** (1 / 6.0), hi * 1.0)
        if f2 <= f1:
            continue
        out.append((float(c), coherence(a, b, sr, f1, f2)))
    return out


def polarity(a, b, sr, hi=BAND_HZ[1], max_lag_ms=1.0):
    """(rho at zero lag, best |rho| within +-max_lag_ms, lag of that best in ms) of the two low-passed channels."""
    x, y = _band(a, sr, BAND_HZ[0], hi), _band(b, sr, BAND_HZ[0], hi)
    den = float(np.sqrt(np.sum(x * x) * np.sum(y * y)))
    if den <= 0.0:
        return 1.0, 1.0, 0.0
    m = int(max_lag_ms * sr / 1000.0)
    best, best_lag = 0.0, 0
    n = len(x)
    for lag in range(-m, m + 1):
        s = float(np.sum(x[max(0, lag):n + min(0, lag)] * y[max(0, -lag):n - max(0, lag)])) / den
        if abs(s) > abs(best):
            best, best_lag = s, lag
    return float(np.sum(x * y) / den), float(abs(best)), float(best_lag * 1000.0 / sr)


def fold_loss_db(a, b, sr, lo=BAND_HZ[0], hi=BAND_HZ[1]):
    """What summing two low-frequency channels into one costs, per 1/3 octave, in dB.

    The sum is scaled by `downmix.lfe_sum_gain` of the broadband coherence (the gain the fold chain uses), so a
    pair of identical or unrelated channels folds with no loss on average. A band where the pair is partly opposed
    loses level, a band where the broadband gain is too small for a still-coherent band gains it. Returns
    ([(centre Hz, dB)], the gain used). dB is 10 log10(mean power of the pair / power of the scaled sum): 0 = no loss,
    positive = the fold loses that much.
    """
    k = downmix.lfe_sum_gain(coherence(a, b, sr, lo, hi))
    out = []
    for c in third_octaves(lo, hi):
        f1, f2 = c * 2 ** (-1 / 6.0), min(c * 2 ** (1 / 6.0), hi * 1.0)
        if f2 <= f1:
            continue
        x, y = _band(a, sr, f1, f2), _band(b, sr, f1, f2)
        pair = 0.5 * (np.mean(x * x) + np.mean(y * y))
        folded = np.mean((k * (x + y)) ** 2)
        out.append((float(c), float(10.0 * np.log10((pair + 1e-20) / (folded + 1e-20)))))
    return out, k


def _modes(size, fmax):
    lx, ly, lz = size
    nmax = [int(np.floor(2.0 * fmax * d / C_SOUND)) + 1 for d in size]
    out = []
    for nx in range(nmax[0] + 1):
        for ny in range(nmax[1] + 1):
            for nz in range(nmax[2] + 1):
                f = 0.5 * C_SOUND * np.sqrt((nx / lx) ** 2 + (ny / ly) ** 2 + (nz / lz) ** 2)
                if 0.0 < f <= fmax:
                    out.append((nx, ny, nz, f))
    return out


def _shape(modes, size, pos):
    p = np.asarray(pos, dtype=np.float64)
    nx, ny, nz = (np.array([m[i] for m in modes]) for i in range(3))
    return (np.cos(nx * np.pi * p[0] / size[0]) * np.cos(ny * np.pi * p[1] / size[1])
            * np.cos(nz * np.pi * p[2] / size[2]))


def modal_spread(room, freqs=None, coherent_below_hz=40.0):
    """Spatial spread of a box room's low-frequency response with one sub and with two. Returns a dict of dB values.

    `room` (a layout's `qa.listening_room`): size_m [Lx, Ly, Lz], rt60_s, subs_m [[x, y, z], [x, y, z]],
    listeners_frac [[...]] positions as fractions of the room (default a 3 x 3 grid at 1.2 m seat height).
    Pressure at listener r from a source at s is the modal sum  sum_n e_n psi_n(s) psi_n(r) / (w_n^2 - w^2 + 2j d w_n w),
    e_n = product of 2 for each non-zero index, d = 3 ln 10 / RT60 (Kuttruff). Two subs add in amplitude (each at
    0.7071) below `coherent_below_hz`, where the pair is identical, and in power above it, where LFE2 is decorrelated.
    The spread is the standard deviation over listeners of the level in dB, averaged over frequency: one number each
    for one sub and for two. A model of a rectangular room only: reflections, furniture and openings are not in it.
    """
    size = [float(v) for v in room['size_m']]
    subs = [list(map(float, s)) for s in room['subs_m']]
    delta = 3.0 * np.log(10.0) / float(room['rt60_s'])
    fmax = float((freqs[-1] if freqs is not None else 120.0)) * 1.5
    modes = _modes(size, fmax)
    if not modes:
        raise ValueError('no room modes below the band: the room is too small for the band asked')
    wn = 2.0 * np.pi * np.array([m[3] for m in modes])
    eps = np.array([np.prod([2.0 if m[i] else 1.0 for i in range(3)]) for m in modes])
    freqs = np.geomspace(25.0, 120.0, 48) if freqs is None else np.asarray(freqs, dtype=np.float64)
    if room.get('listeners_m'):
        listeners = [list(map(float, p)) for p in room['listeners_m']]
    else:
        fr = [0.35, 0.5, 0.65]
        listeners = [[fx * size[0], fy * size[1], min(1.2, 0.9 * size[2])] for fx in fr for fy in fr]
    psi_s = [_shape(modes, size, s) for s in subs]
    psi_l = np.stack([_shape(modes, size, p) for p in listeners])             # (listeners, modes)
    spread = {'one': [], 'two': []}
    for f in freqs:
        w = 2.0 * np.pi * f
        den = wn ** 2 - w ** 2 + 2j * delta * wn * w
        g = [(psi_l * (eps * ps / den)).sum(axis=1) for ps in psi_s]          # (listeners,) per sub
        one = np.abs(g[0])
        if f < coherent_below_hz:
            two = np.abs((g[0] + g[1]) * np.sqrt(0.5))
        else:
            two = np.sqrt(0.5 * (np.abs(g[0]) ** 2 + np.abs(g[1]) ** 2))
        spread['one'].append(float(np.std(20.0 * np.log10(one + 1e-30))))
        spread['two'].append(float(np.std(20.0 * np.log10(two + 1e-30))))
    one, two = float(np.mean(spread['one'])), float(np.mean(spread['two']))
    return dict(one_sub_db=one, two_subs_db=two, improvement_db=one - two, modes=len(modes))


def _noise(n, seed=2):
    return np.random.default_rng(seed).standard_normal(n) * 0.1


def _itd_ild(ear, sr):
    """(ITD in microseconds, positive when the right ear leads; ILD in dB, right minus left) of a binaural pair."""
    left, right = ear[:, 0].astype(np.float64), ear[:, 1].astype(np.float64)
    lo_l, lo_r = _band(left, sr, 200.0, 1500.0), _band(right, sr, 200.0, 1500.0)
    m = int(0.001 * sr)
    n = len(lo_l)
    best, lag = -2.0, 0
    for k in range(-m, m + 1):
        s = float(np.sum(lo_l[max(0, k):n + min(0, k)] * lo_r[max(0, -k):n - max(0, k)]))
        if s > best:
            best, lag = s, k
    hi_l, hi_r = _band(left, sr, 1500.0, 8000.0), _band(right, sr, 1500.0, 8000.0)
    ild = 10.0 * np.log10((np.mean(hi_r ** 2) + 1e-20) / (np.mean(hi_l ** 2) + 1e-20))
    return float(-lag * 1e6 / sr), float(ild)


def phantom_fold_error(layout_name='lrc_lfe2', sr=44100, seconds=1.0):
    """The centre channel folded into L and R (the layout's own downmix coefficients) against a real centre, through
    the measured head set. Returns dict(itd_error_us, ild_error_db, colour_rms_db, itd_c_us, itd_phantom_us).

    Needs the head data (`spatial_hrtf.binaural.available()`); raises RuntimeError without it.
    """
    from spatial_hrtf import binaural
    from . import config
    if not binaural.available():
        raise RuntimeError('head data missing: run `python -m spatial_hrtf.data` from scripts/')
    names = config.channel_names(layout_name)
    dm = config.layout(layout_name)['downmix']
    spk = {s['name']: s for s in config.speakers(layout_name)}
    x = _noise(int(sr * seconds))
    real = binaural.spatialize(x, spk['C']['azimuth'], spk['C']['elevation'], 1.0, sr)
    phantom = np.zeros_like(real, dtype=np.float64)
    for side, name in ((0, 'L'), (1, 'R')):
        g = float(dm['C'][side])
        phantom += g * binaural.spatialize(x, spk[name]['azimuth'], spk[name]['elevation'], 1.0, sr)
    itd_c, ild_c = _itd_ild(real, sr)
    itd_p, ild_p = _itd_ild(phantom, sr)
    from scipy.signal import welch
    f, p_real = welch(real.mean(axis=1), fs=sr, nperseg=4096)
    _, p_ph = welch(phantom.mean(axis=1), fs=sr, nperseg=4096)
    sel = (f >= 1000.0) & (f <= 8000.0)
    diff = 10.0 * np.log10((p_ph[sel] + 1e-20) / (p_real[sel] + 1e-20))
    return dict(itd_error_us=abs(itd_p - itd_c), ild_error_db=abs(ild_p - ild_c),
                colour_rms_db=float(np.sqrt(np.mean((diff - diff.mean()) ** 2))),
                itd_c_us=itd_c, itd_phantom_us=itd_p, names=names)
