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
    return guard(out, sr, cfg)


def guard(bus, sr, cfg):
    """Nothing above `stopband_hz` leaves the low-frequency channel: a cascade of low-passes at the stopband.

    The stopband is an upper limit, so the guard is a low-pass. A high-pass here would be the opposite of a guard: it
    would strip the low end the channel exists to carry.
    """
    stop = cfg.get('stopband_hz')
    if stop is None:
        return bus
    return lr4(bus, sr, float(stop), 'low')


def stopband_leak_db(bus, sr, cfg, reference=None):
    """Energy above the stopband relative to a reference level, in dB (negative = clean).

    The reference is the programme level (the mean RMS of the delivered channels). Measured against the channel's own
    residual instead, a channel with no energy at all would score 0 dB, which says nothing about audibility.
    """
    stop = float(cfg.get('stopband_hz'))
    ref = np.asarray(bus if reference is None else reference, dtype=np.float64)
    ref_rms = float(np.sqrt(np.mean(np.square(ref)) + 1e-20))
    above = lr4(bus, sr, stop, 'high')
    leak = float(np.sqrt(np.mean(np.square(above)) + 1e-20))
    return float(20.0 * np.log10(leak / ref_rms + 1e-20))
