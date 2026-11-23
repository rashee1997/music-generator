"""meters - what a finished file measures.

The K-weighting, gating and true-peak definitions come from `loudness.py` and `dsp.py`, so there is one
implementation of each number in the skill. This module only combines them into the figures the delivery
report and the gate need, and adds the two measurements that were missing:

  * true peak at 4x and 8x oversampling. ITU-R BS.1770-5 Annex 2 defines the 4x reference method; EBU
    Tech 3343 notes it can under-read by about 0.5 dB at 48 kHz, so the larger of the two is reported
    and judged.
  * PLR (EBU Tech 3401) and PSR (AES EBU 373): peak against integrated and short-term loudness.
  * per-band L/R correlation and mono-fold loss. A broadband correlation hides a narrow band that
    cancels when folded; these are measurements, and no validated pass mark exists for them.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

import dsp
import loudness

SR = 44100

# octave bands for the mono check: low enough to catch a polarity-flipped bass double, high enough to
# catch a phasey pad or a widened top
MONO_BANDS_HZ = ((63, 125), (125, 250), (250, 500), (500, 1000),
                 (1000, 2000), (2000, 4000), (4000, 8000))


def true_peak_db(x, sr=SR, over=4):
    return float(dsp.true_peak_db(x, sr, over))


def true_peak_report(x, sr=SR):
    """The two estimates and the larger one, with the difference the standards warn about."""
    tp4 = true_peak_db(x, sr, 4)
    tp8 = true_peak_db(x, sr, 8)
    return dict(true_peak_4x=tp4, true_peak_8x=tp8, true_peak=max(tp4, tp8), under_read_db=tp8 - tp4)


def integrated_lufs(x, sr=SR):
    """Integrated loudness with the engine's own meter (a meter error reads as silence, never a guess)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    if len(x) < int(0.5 * sr):
        x = np.pad(x, ((0, int(0.5 * sr) - len(x)), (0, 0)))
    v = dsp.meter(sr).integrated_loudness(x)
    return -70.0 if not np.isfinite(v) else float(v)


def micro_dynamics(integrated_lufs, true_peak, short_term_peak=None):
    """PLR and PSR in LU. PSR is NaN when no short-term peak was measured, never a silent zero."""
    plr = float(true_peak) - float(integrated_lufs)
    if short_term_peak is None or not np.isfinite(short_term_peak):
        psr = float('nan')
    else:
        psr = float(true_peak) - float(short_term_peak)
    return dict(plr=plr, psr=psr)


def _bands(shape, sr):
    return [(lo, min(hi, sr / 2.0 - 1.0)) for lo, hi in MONO_BANDS_HZ if lo < sr / 2.0 - 1.0]


def band_correlation(x, sr=SR, bands=None):
    """Per-octave L/R correlation and the mono-fold energy loss of that band, in dB.

    Returns a list of dicts: `band_hz`, `correlation`, `fold_loss_db`, `energy_db`. A band whose fold
    loss is large (or whose correlation is negative) is where a mono delivery loses that part; the
    numbers are reported, and the acceptance threshold stays with the piece, not with this meter.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    left, right = x[:, 0], x[:, 1]
    out = []
    for lo, hi in (bands or _bands(x.shape, sr)):
        try:
            sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
            l = signal.sosfiltfilt(sos, left)
            r = signal.sosfiltfilt(sos, right)
        except ValueError:
            continue                       # shorter than the filter's padding: no band measurement
        el = float(np.mean(l ** 2))
        er = float(np.mean(r ** 2))
        if el <= 1e-20 and er <= 1e-20:
            continue
        corr = float(np.corrcoef(l, r)[0, 1]) if el > 1e-20 and er > 1e-20 else 0.0
        if not np.isfinite(corr):
            corr = 0.0
        mono = 0.5 * (l + r)
        em = float(np.mean(mono ** 2))
        ref = 0.5 * (el + er)
        loss = float(np.clip(10.0 * np.log10((em + 1e-20) / (ref + 1e-20)), -60.0, 12.0))
        out.append(dict(band_hz=(lo, hi), correlation=corr, fold_loss_db=float(loss),
                        energy_db=float(10.0 * np.log10(ref + 1e-20))))
    return out


def master_measures(x, sr=SR):
    """Everything the delivery report needs from one pass over the master.

    One K-weighting pass feeds every loudness figure. True peak is measured at 4x and 8x because EBU Tech
    3343 documents the 4x under-read; PLR and PSR are reported, not judged.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    blocks = loudness.Blocks(x, sr)
    st_raw = np.array(blocks.gated_series(3.0, 0.5), dtype=float)
    st_all = st_raw[np.isfinite(st_raw)]
    st = loudness.Blocks.lra_gate(st_all)
    tp = true_peak_report(x, sr)
    integrated = integrated_lufs(x, sr)
    md = micro_dynamics(integrated, tp['true_peak'], st_all.max() if len(st_all) else None)
    return {
        'lufs': integrated,
        'short_term_max': float(st.max()) if len(st) else float('nan'),
        'short_term_min': float(st.min()) if len(st) else float('nan'),
        'short_term_peak': float(st_all.max()) if len(st_all) else float('nan'),
        'lra': blocks.lra(),                                  # EBU Tech 3342, from the standard's own series
        'true_peak': tp['true_peak'],
        'true_peak_4x': tp['true_peak_4x'],
        'true_peak_8x': tp['true_peak_8x'],
        'true_peak_under_read_db': tp['under_read_db'],
        'plr': md['plr'],
        'psr': md['psr'],
        'sample_peak': float(20 * np.log10(np.abs(x).max() + 1e-12)),
        'crest': dsp.crest_db(x),
        'mono_fold': dsp.mono_fold_db(x),
        'correlation': dsp.correlation(x),
        'mono_bands': band_correlation(x, sr),
    }


def worst_mono_band(rows, floor_db=-6.0):
    """The band that loses the most in mono, when it loses more than `floor_db`; else None."""
    if not rows:
        return None
    worst = min(rows, key=lambda r: r['fold_loss_db'])
    return worst if worst['fold_loss_db'] < floor_db else None
