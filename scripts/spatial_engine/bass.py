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
from scipy.signal import butter, sosfilt


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


def lfe_bus(sends, sr, cfg):
    """Sum the low-passed sends, apply the send gain, then enforce the stopband guard.

    `sends` is a list of mono arrays. `cfg` is config.lfe_cfg(): lowpass_hz, stopband_hz, stopband_db, send_db.
    """
    cutoff = float(cfg.get('lowpass_hz'))
    gain = send_gain(cfg.get('send_db', 0.0))
    n = max((len(s) for s in sends), default=0)
    out = np.zeros(n, dtype=np.float64)
    for s in sends:
        out[:len(s)] += lowpass(s, sr, cutoff) * gain
    return release_fade(guard(out, sr, cfg), sr, cfg)


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
