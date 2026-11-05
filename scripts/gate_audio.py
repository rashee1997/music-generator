# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""gate_audio.py - one lazy view of a signal, shared by every gate row.

    from gate_audio import Signal, load
    a = load('out/master.wav')      # GateAudio
    a.mono, a.decim, a.stft, a.onset_env, a.lufs, a.true_peak

Every derived array is computed once, on first use, under a lock. Rows must not read the WAV or run a second STFT:
`tests/test_gate_checks.py` asserts the cache is used. Full-rate data (`stereo`, `mono`, true peak, click residual) is
never decimated; envelopes, section levels and cut/dropout use the 8 kHz copy, which is enough for a 20 ms frame and
5.5x smaller.

This module measures only. It has no synthesis, EQ, mixing or preset values.
"""
import threading

import numpy as np
import soundfile as sf

try:
    import librosa
except Exception:                                     # a gate must still explain itself without librosa
    librosa = None

DECIM_SR = 8000
FRAME_MS = 20.0
HOP_MS = 5.0
N_FFT = 2048
HOP = 512


class Signal:
    """A read-only, lazy analysis of one signal: mono, stereo, or a multichannel deliverable.

    `audio` holds every channel as delivered; `stereo` is the first two channels (what the two-channel rows read) and
    `mono` is the mean of all channels. A multichannel file is a legitimate deliverable now, so rejecting it here would
    make the gate unable to describe it at all.
    """

    def __init__(self, y, sr):
        y = np.asarray(y)
        if y.ndim == 1:
            y = np.stack([y, y], axis=1)
        if y.ndim != 2 or y.shape[1] < 1:
            raise ValueError(f'expected a mono, stereo or multichannel signal, got shape {y.shape}')
        if not np.isfinite(y).all():
            raise ValueError('audio contains NaN or Inf')
        self.audio = y.astype(np.float64, copy=False)
        self.stereo = self.audio[:, :2] if self.audio.shape[1] >= 2 else self.audio
        self.sr = int(sr)
        self.mono = self.audio.mean(axis=1)
        self._cache = {}
        self._lock = threading.RLock()

    def _get(self, key, fn):
        with self._lock:
            if key not in self._cache:
                self._cache[key] = fn()
            return self._cache[key]

    def invalidate(self):
        with self._lock:
            self._cache.clear()

    @property
    def dur(self):
        return len(self.mono) / float(self.sr)

    @property
    def decim(self):
        def make():
            from scipy.signal import resample_poly
            g = np.gcd(int(self.sr), DECIM_SR)
            return resample_poly(self.mono, DECIM_SR // g, self.sr // g).astype(np.float64)
        return self._get('decim', make)

    @property
    def decim_sr(self):
        return DECIM_SR

    @property
    def stft(self):
        def make():
            if librosa is None:
                raise RuntimeError('librosa is required for the spectral rows')
            return np.abs(librosa.stft(self.mono, n_fft=N_FFT, hop_length=HOP)).astype(np.float32)
        return self._get('stft', make)

    @property
    def onset_env(self):
        def make():
            if librosa is None:
                raise RuntimeError('librosa is required for the onset rows')
            return librosa.onset.onset_strength(y=self.mono, sr=self.sr, hop_length=HOP).astype(np.float64)
        return self._get('onset_env', make)

    @property
    def lufs(self):
        def make():
            try:
                import pyloudnorm as pyln
                return float(pyln.Meter(self.sr).integrated_loudness(self.mono))
            except Exception:
                return float('nan')
        return self._get('lufs', make)

    @property
    def true_peak(self):
        def make():
            from scipy.signal import resample_poly
            up = resample_poly(self.audio, 4, 1, axis=0)
            return float(20.0 * np.log10(np.max(np.abs(up)) + 1e-12))
        return self._get('true_peak', make)

    @property
    def true_peak_by_channel(self):
        """True peak per channel, in dBTP: a multichannel deliverable is checked channel by channel."""
        def make():
            from scipy.signal import resample_poly
            up = resample_poly(self.audio, 4, 1, axis=0)
            return 20.0 * np.log10(np.max(np.abs(up), axis=0) + 1e-12)
        return self._get('true_peak_by_channel', make)

    def frame_db(self, frame_ms=FRAME_MS, hop_ms=HOP_MS, decimated=True):
        """(dBFS per frame, frame start times). Default 20 ms / 5 ms on the decimated copy."""
        key = f'frame_db:{frame_ms}:{hop_ms}:{decimated}'
        def make():
            sr = self.decim_sr if decimated else self.sr
            x = self.decim if decimated else self.mono
            n = max(1, int(round(frame_ms * sr / 1000.0)))
            h = max(1, int(round(hop_ms * sr / 1000.0)))
            if len(x) < n:
                return np.array([20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)]), np.array([0.0])
            if librosa is not None:
                fr = librosa.util.frame(x, frame_length=n, hop_length=h).astype(np.float64)
            else:
                fr = np.lib.stride_tricks.sliding_window_view(x, n)[::h].T.astype(np.float64)
            rms = np.sqrt(np.mean(fr ** 2, axis=0))
            db = 20.0 * np.log10(rms + 1e-12)
            times = np.arange(db.size) * h / float(sr)
            return db, times
        return self._get(key, make)


class GateAudio(Signal):
    """A signal loaded from a WAV, plus its container facts."""

    def __init__(self, path, y=None, sr=None):
        self.path = str(path)
        self.info = None
        if y is None:
            y, sr = sf.read(self.path, always_2d=True)
            self.info = sf.info(self.path)
        super().__init__(y, sr)

    @property
    def subtype(self):
        return getattr(self.info, 'subtype', None)

    @property
    def channels(self):
        return int(self.audio.shape[1])


def load(path):
    return GateAudio(path)
