# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""speech.py - where speech is in a picture's own audio.

"Dialogue present" used to mean "the container has an audio stream", which is a
guess. This module measures a speech mask and reports it as per-second truth.

Three cues must agree before a frame counts as speech:

  band energy    the frame is loud enough inside 300-3400 Hz
  flatness       the spectrum is peaky (a voice), not flat (noise, a cymbal)
  voicing        a normalised autocorrelation peak exists in the 60-400 Hz lag
                 range, which is where a speaking f0 lives

Segments shorter than `min_seg_s` are dropped, gaps shorter than `merge_gap_s`
are closed, and each segment's end is held by `hold_s` so the duck does not
release between words.

Every threshold is a key in the analysis preset's `speech` block; the shipped
numbers are starting values and the preset's `provenance` says so.
"""
import numpy as np
from scipy import signal

BAND_DEFAULT = (300.0, 3400.0)
F0_RANGE_HZ = (60.0, 400.0)


def frame_signal(y, sr, frame_ms, hop_ms):
    """Frames of the signal, (n_frames, frame_len), plus the times of their centres."""
    y = np.asarray(y, dtype=np.float32)
    if y.ndim > 1:
        y = y.mean(axis=1)
    n = int(round(float(frame_ms) * sr / 1000.0))
    hop = max(1, int(round(float(hop_ms) * sr / 1000.0)))
    n = max(8, min(n, len(y)) if len(y) else 8)
    if len(y) < n:
        y = np.pad(y, (0, n - len(y)))
    count = 1 + max(0, (len(y) - n) // hop)
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    return y[idx], (np.arange(count) * hop + n / 2.0) / float(sr)


def _band_rms_db(frames, sr, band):
    lo, hi = float(band[0]), float(band[1])
    sos = signal.butter(4, [lo, min(hi, sr / 2.0 * 0.98)], btype='band', fs=sr, output='sos')
    try:
        filtered = signal.sosfilt(sos, frames, axis=1)
    except ValueError:
        return np.full(len(frames), -120.0)
    rms = np.sqrt(np.mean(np.square(filtered), axis=1) + 1e-12)
    return 20.0 * np.log10(rms + 1e-12)


def _flatness(frames):
    """Spectral flatness per frame: geometric mean / arithmetic mean of the power spectrum."""
    if not len(frames):
        return np.zeros(0)
    spec = np.abs(np.fft.rfft(frames * np.hanning(frames.shape[1]), axis=1)) ** 2 + 1e-12
    g = np.exp(np.mean(np.log(spec), axis=1))
    a = np.mean(spec, axis=1)
    return g / (a + 1e-12)


def _voicing(frames, sr):
    """Normalised autocorrelation peak inside the speaking-f0 lag range."""
    if not len(frames):
        return np.zeros(0)
    lo = max(1, int(sr / F0_RANGE_HZ[1]))
    hi = max(lo + 1, int(sr / F0_RANGE_HZ[0]))
    hi = min(hi, frames.shape[1] - 2)
    out = np.zeros(len(frames))
    for i, fr in enumerate(frames):
        fr = fr - fr.mean()
        denom = float(np.dot(fr, fr)) + 1e-12
        ac = np.correlate(fr, fr, mode='full')[len(fr) - 1:]
        if hi <= lo or hi >= len(ac):
            continue
        out[i] = float(np.max(ac[lo:hi]) / denom)
    return out


def activity(y, sr, cfg):
    """Speech mask for one audio track.

    Returns {'mask': float array at hop rate, 'times': seconds, 'share': fraction,
             'segments': [(start_s, end_s)], 'per_second': [fraction, ...]}
    """
    sp = cfg.get('speech', cfg)
    frames, times = frame_signal(y, sr, sp.get('frame_ms', 25.0), sp.get('hop_ms', 10.0))
    band_db = _band_rms_db(frames, sr, sp.get('band_hz', BAND_DEFAULT))
    flat = _flatness(frames)
    voice = _voicing(frames, sr)
    active = (band_db > float(sp.get('threshold_db', -42.0))) & \
             (flat < float(sp.get('max_flatness', 0.45))) & \
             (voice > float(sp.get('min_voicing', 0.30)))
    segs = _segments(times, active)
    segs = _merge(segs, float(sp.get('merge_gap_s', 0.30)))
    segs = [(a, b) for a, b in segs if b - a >= float(sp.get('min_seg_s', 0.15))]
    hold = float(sp.get('hold_s', 0.25))
    segs = [(a, min(b + hold, float(times[-1]) + 1e-6)) for a, b in segs]
    mask = np.zeros(len(times), np.float32)
    for a, b in segs:
        mask[(times >= a) & (times < b)] = 1.0
    total = float(times[-1]) if len(times) else 0.0
    per_second = []
    for s in range(int(np.ceil(total)) if total > 0 else 0):
        sel = (times >= s) & (times < s + 1)
        per_second.append(round(float(mask[sel].mean()) if sel.any() else 0.0, 3))
    return dict(mask=mask, times=times, share=round(float(mask.mean()) if len(mask) else 0.0, 4),
                segments=[(round(a, 3), round(b, 3)) for a, b in segs], per_second=per_second,
                frames=len(frames))


def _segments(times, active):
    segs, start = [], None
    for i, on in enumerate(active):
        if on and start is None:
            start = times[i]
        elif not on and start is not None:
            segs.append((start, times[i]))
            start = None
    if start is not None and len(times):
        segs.append((start, float(times[-1]) + float(times[1] - times[0]) if len(times) > 1 else 0.0))
    return segs


def _merge(segs, gap_s):
    if gap_s <= 0 or len(segs) < 2:
        return list(segs)
    out = [list(segs[0])]
    for a, b in segs[1:]:
        if a - out[-1][1] <= gap_s:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def mask_at(mask, times, n, sr):
    """A per-sample 0/1 mask of length n from a hop-rate mask, so filters and meters can use it."""
    mask = np.asarray(mask, dtype=np.float32)
    times = np.asarray(times, dtype=np.float32)
    if not len(mask):
        return np.zeros(int(n), np.float32)
    t = np.arange(int(n)) / float(sr)
    return (np.interp(t, times, mask) >= 0.5).astype(np.float32)


__all__ = ['activity', 'frame_signal', 'mask_at', 'BAND_DEFAULT']
