# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""bass.py - Linkwitz-Riley 4th-order crossover and the low-frequency channel.

Linkwitz, S. H. (1976). "Active crossover networks for noncoincident drivers." JAES 24(1), 2-8.

LR4 is two cascaded 2nd-order Butterworth sections. The low-pass and high-pass outputs are in phase at the crossover and
each is -6 dB there, so their sum is flat. A dedicated low-frequency deliverable channel is fed by an explicit SEND:
the mains get the high-passed signal, the LFE gets the low-passed one (plus anything a mix preset sends to it), and a
hard stopband above the layout's `stopband_hz` keeps the channel from leaking into the main band.

The crossover, the send level and the stopband come from the layout/target presets, never from this file.
"""
import numpy as np
from scipy.signal import butter, lfilter, sosfilt


def lr4(y, sr, cutoff_hz, kind='low'):
    """Linkwitz-Riley 4th order. `kind` is 'low' or 'high'."""
    if kind not in ('low', 'high'):
        raise ValueError("kind must be 'low' or 'high'")
    sos = butter(2, float(cutoff_hz), btype=kind, fs=float(sr), output='sos')
    return sosfilt(sos, sosfilt(sos, np.asarray(y, dtype=np.float64), axis=0), axis=0)


def lowpass(y, sr, cutoff_hz):
    return lr4(y, sr, cutoff_hz, 'low')


def highpass(y, sr, cutoff_hz):
    return lr4(y, sr, cutoff_hz, 'high')


def send_gain(send_db):
    """Linear gain for a send expressed in dB (the LFE is authored low and played back high, so its send is data)."""
    return float(10.0 ** (float(send_db) / 20.0))


def lfe_bus(sends, sr, cfg, weights=None):
    """Sum the low-passed sends, apply the send gain, then enforce the stopband guard.

    `sends` is a list of mono arrays. `cfg` is config.lfe_cfg(): lowpass_hz, stopband_hz, stopband_db, send_db.
    `weights` (one linear gain per send) is the per-track share of this channel; without it every send counts fully.
    """
    out = _low_sum(sends, sr, cfg, weights)
    return release_fade(guard(out, sr, cfg), sr, cfg)


def _low_sum(sends, sr, cfg, weights=None):
    cutoff = float(cfg.get('lowpass_hz'))
    gain = send_gain(cfg.get('send_db', 0.0))
    n = max((len(s) for s in sends), default=0)
    out = np.zeros(n, dtype=np.float64)
    for i, s in enumerate(sends):
        w = 1.0 if weights is None else float(weights[i])
        if w:
            out[:len(s)] += lowpass(s, sr, cutoff) * (gain * w)
    return out


def pan_weights(pans):
    """Equal-power shares (LFE1, LFE2) for per-track `lfe_pan` values in [-1, 1]: -1 is LFE1 only, +1 is LFE2 only."""
    theta = (np.clip(np.asarray(pans, dtype=np.float64), -1.0, 1.0) + 1.0) * (np.pi / 4.0)
    return np.cos(theta), np.sin(theta)


def allpass_cascade(y, sr, stages, max_group_delay_ms):
    """Phase-only decorrelation with a bounded total group delay.

    A first-order all-pass y[n] = -a x[n] + x[n-1] + a y[n-1] delays low frequencies by (1 + a) / (1 - a) samples, so
    `stages` sections of N/stages samples each add N = max_group_delay_ms in total. The coefficients differ per stage
    (spread of 0.5x..1.5x the mean delay) so the cascade is not one repeated delay. Magnitude is flat.
    """
    stages = max(1, int(stages))
    n_total = max(2.0, float(max_group_delay_ms) * sr / 1000.0)
    shares = np.linspace(0.5, 1.5, stages) if stages > 1 else np.ones(1)
    shares = shares / shares.sum() * n_total
    out = np.asarray(y, dtype=np.float64)
    for n in shares:
        a = float(np.clip((n - 1.0) / (n + 1.0), 0.0, 0.999))
        out = lfilter([-a, 1.0], [1.0, -a], out)
    return out


def delay_samples(y, n):
    """Delay by a whole number of samples (zero fill, same length). A negative `n` is an error: a file cannot advance."""
    n = int(n)
    if n < 0:
        raise ValueError('an LFE delay cannot be negative')
    if n == 0:
        return y
    out = np.zeros_like(y)
    out[n:] = y[:len(y) - n] if n < len(y) else 0.0
    return out


def lfe_bus_pair(sends, pans, sr, cfg):
    """Two low-frequency channels (LFE1, LFE2) from the same sends. Returns (lfe1, lfe2), equal length.

    cfg.mode:
      stereo_bass (default)  equal-power split by each track's `lfe_pan`; LFE2 is made incoherent with LFE1 above
                             `decorrelate_above_hz` by a bounded all-pass cascade, and identical below it, so the two
                             add coherently under the corner and excite different room modes above it.
      dual_mono              both channels carry the single-channel bus unchanged (a 5.1 bus on two outputs).
      modal_split            the split of stereo_bass without decorrelation; for a room whose delay and polarity are
                             known and written in `delay_ms` / `polarity`.
    cfg.delay_ms [d1, d2] and cfg.polarity [p1, p2] apply to every mode, in the order LFE1, LFE2.
    """
    mode = str(cfg.get('mode', 'stereo_bass'))
    if mode not in ('stereo_bass', 'dual_mono', 'modal_split'):
        raise ValueError(f'lfe mode "{mode}" is not one of stereo_bass, dual_mono, modal_split')
    if mode == 'dual_mono':
        w1 = w2 = None
    else:
        w1, w2 = pan_weights(pans)
    b1 = _low_sum(sends, sr, cfg, w1)
    b2 = _low_sum(sends, sr, cfg, w2)
    if mode == 'stereo_bass':
        d = cfg.get('decorrelation') or {}
        fd = float(cfg.get('decorrelate_above_hz', 40.0))
        # Both channels go through the same LR4 split and re-sum (that sum is itself an all-pass, so it must be common to
        # both or it would put the channels in antiphase at the corner); only LFE2's upper band gets the cascade.
        b1 = lowpass(b1, sr, fd) + highpass(b1, sr, fd)
        b2 = lowpass(b2, sr, fd) + allpass_cascade(highpass(b2, sr, fd), sr, d.get('stages', 4),
                                                   d.get('max_group_delay_ms', 3.0))
    out = []
    delays, pols = list(cfg.get('delay_ms') or [0.0, 0.0]), list(cfg.get('polarity') or [1, 1])
    for b, ms, pol in zip((b1, b2), delays, pols):
        b = delay_samples(b, round(float(ms) * sr / 1000.0)) * (-1.0 if float(pol) < 0 else 1.0)
        out.append(release_fade(guard(b, sr, cfg), sr, cfg))
    return out[0], out[1]


def lfe_channels(sends, pans, sr, cfg, count):
    """The low-frequency channels for a layout with `count` of them (1 or 2), as a list of arrays."""
    if count == 1:
        return [lfe_bus(sends, sr, cfg)]
    if count == 2:
        return list(lfe_bus_pair(sends, pans, sr, cfg))
    raise ValueError(f'{count} low-frequency channels: the engine routes one or two')


def release_fade(bus, sr, cfg):
    """Close the low channel smoothly: a send that ends at full amplitude is a step, and a step is a click.

    The length is data (`lfe.release_ms`), because how long a fade must be is a project decision, not a constant here.
    """
    ms = float(cfg.get('release_ms') or 0.0)
    n = min(len(bus), int(ms * sr / 1000.0))
    if n <= 1:
        return bus
    out = np.array(bus, dtype=np.float64, copy=True)
    out[-n:] *= np.linspace(1.0, 0.0, n) ** 2      # squared: no slope discontinuity at the join
    return out


def guard(bus, sr, cfg):
    """Nothing above `stopband_hz` leaves the low-frequency channel: a cascade of low-passes at the stopband.

    The stopband is an upper limit, so the guard is a low-pass. A high-pass here would be the opposite of a guard: it
    would strip the low end the channel exists to carry.
    """
    stop = cfg.get('stopband_hz')
    if stop is None:
        return bus
    out = bus
    for _ in range(max(1, int(cfg.get('guard_order', 1)))):   # the layout says how steep the guard must be
        out = lr4(out, sr, float(stop), 'low')
    return out


def stopband_leak_db(bus, sr, cfg, reference=None):
    """Energy above the stopband relative to a reference level, in dB (negative = clean).

    The reference is the programme level (the mean power of the delivered channels). Measured against the channel's
    own residual instead, a channel with no energy at all would score 0 dB, which says nothing about audibility.

    The band is measured with Welch's method, not with a filter: a 4th-order high-pass at 120 Hz still passes a
    55 Hz tone at only about -27 dB, so a filter-based "leak" would report the filter's own skirt as a fault. Welch
    with a Hann window resolves the band and stays amplitude-correct (PSD integrated over the band).
    """
    from scipy.signal import welch
    stop = float(cfg.get('stopband_hz'))
    x = np.asarray(bus, dtype=np.float64).ravel()
    ref = np.asarray(bus if reference is None else reference, dtype=np.float64).ravel()
    if len(x) < 32 or len(ref) < 32:
        return -120.0
    freqs, psd = welch(x, fs=float(sr), window='hann', nperseg=min(len(x), 8192))
    band_power = float(np.sum(psd[freqs > stop]) * (freqs[1] - freqs[0]))
    ref_power = float(np.mean(np.square(ref)) + 1e-20)
    return float(10.0 * np.log10(band_power / ref_power + 1e-30))
