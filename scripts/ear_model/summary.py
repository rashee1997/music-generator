# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""summary.py - per-frame quantities read from the neural activity pattern, computed while it streams.

Per frame of `summary.frame_s` seconds (1 s):

  excitation   mean NAP per channel (how strongly each ERB channel is driven)
  depth        mean adaptation depth per channel (how much of the slow store is in use)
  fatigue      depth averaged over channels, weighted by excitation: a proxy for sustained drive that a loudness
               meter cannot see (a dense saturated pad and a sparse texture can share a LUFS value)
  roughness    envelope modulation between `mod_band_hz` (30-150 Hz) as a depth (median of four quarter-frames, at most 1), squared, averaged over the active
               channels above `rough_min_hz`, weighted by excitation: independent of the partial-pair model in naturalness_check
  salience     height of the highest peak of the summary autocorrelation of the NAP (Meddis & Hewitt) inside
               `pitch_hz`, normalised by lag zero, 0..1; f0 is its lag. The NAP is sampled at 2240 Hz, so the pitch
               range stops near 700 Hz: above it the row is unmeasured, not low
  resolved     share of the excitation in channels whose centre is below `resolved_harmonics` times f0 (harmonics a
               single cochlear filter can separate)

Nothing is stored per sample: only a (frames, channels) matrix per quantity.
"""
import numpy as np
from scipy.signal import butter, sosfilt


class Summariser:
    def __init__(self, ear):
        self.ear = ear
        s = ear.p['summary']
        self.frame = int(round(float(s['frame_s']) * ear.nap_rate))
        self.band = [float(v) for v in s['mod_band_hz']]
        self.pitch = [float(v) for v in s['pitch_hz']]
        self.k_res = float(s['resolved_harmonics'])
        self.rough_min = float(s['rough_min_hz'])
        self.floor = float(s['active_floor'])
        self.bp = butter(2, self.band, btype='band', fs=ear.nap_rate, output='sos')

    def run(self, x, chunk_s=None):
        ear = self.ear
        frames = {k: [] for k in ('excitation', 'depth', 'fatigue', 'roughness', 'salience', 'f0_hz', 'resolved')}
        zi = None
        buf_n = buf_d = None
        for nap, dep in ear.stream(x, chunk_s):
            buf_n = nap if buf_n is None else np.concatenate([buf_n, nap], axis=1)
            buf_d = dep if buf_d is None else np.concatenate([buf_d, dep], axis=1)
            while buf_n.shape[1] >= self.frame:
                fn, fd = buf_n[:, :self.frame], buf_d[:, :self.frame]
                buf_n, buf_d = buf_n[:, self.frame:], buf_d[:, self.frame:]
                if zi is None:
                    zi = np.zeros((self.bp.shape[0], fn.shape[0], 2))
                one, zi = self._frame(fn, fd, zi)
                for k, v in one.items():
                    frames[k].append(v)
        out = {k: np.asarray(v, dtype=np.float32) for k, v in frames.items()}
        out['times_s'] = (np.arange(len(out['fatigue'])) + 0.5) * self.frame / ear.nap_rate
        out['fc_hz'] = ear.fc.copy()
        out['frame_s'] = self.frame / ear.nap_rate
        return out

    def _frame(self, nap, depth, zi):
        exc = nap.mean(axis=1)
        dep = depth.mean(axis=1)
        w = exc / (exc.sum() + 1e-12)
        bp, zi = sosfilt(self.bp, nap.astype(np.float64), axis=1, zi=zi)
        # depth per quarter of the frame, then the median: a single note onset or gate edge is a transient in one
        # quarter, sustained modulation is in all four, and only the second is roughness
        q = self.frame // 4
        seg = bp[:, :4 * q].reshape(bp.shape[0], 4, q)
        base = nap[:, :4 * q].reshape(nap.shape[0], 4, q).mean(axis=2)
        ref = np.maximum(base, self.floor * max(float(exc.max()), 1e-9))          # a silent quarter must not divide by ~0
        mod_depth = np.minimum(np.median(np.sqrt(np.mean(seg ** 2, axis=2)) / ref, axis=1), 1.0)
        active = exc.sum() > 1e-6
        rough = 0.0
        if active:
            use = (exc > self.floor * exc.max()) & (self.ear.fc >= self.rough_min)
            if use.any():
                wu = exc[use] / exc[use].sum()
                rough = float((wu * mod_depth[use] ** 2).sum())
        sal, f0 = self._pitch(nap) if active else (0.0, 0.0)
        res = float(w[self.ear.fc < self.k_res * f0].sum()) if f0 > 0 else 0.0
        return dict(excitation=exc, depth=dep, fatigue=float((w * dep).sum()) if active else 0.0,
                    roughness=rough,
                    salience=sal, f0_hz=f0, resolved=res), zi

    def _pitch(self, nap):
        x = nap.astype(np.float64)
        x = x - x.mean(axis=1, keepdims=True)
        n = x.shape[1]
        spec = np.fft.rfft(x, 2 * n, axis=1)
        ac = np.fft.irfft(spec * np.conj(spec), axis=1)[:, :n].sum(axis=0)
        if ac[0] <= 1e-12:
            return 0.0, 0.0
        ac = ac / ac[0]
        rate = self.ear.nap_rate
        lo, hi = int(np.ceil(rate / self.pitch[1])), int(np.floor(rate / self.pitch[0]))
        k = lo + int(np.argmax(ac[lo:hi + 1]))
        peak = float(ac[k])
        if 0 < k < len(ac) - 1:                          # parabolic refinement of the lag
            a, b, c = ac[k - 1], ac[k], ac[k + 1]
            den = a - 2 * b + c
            shift = 0.5 * (a - c) / den if abs(den) > 1e-12 else 0.0
            return float(np.clip(peak, 0.0, 1.0)), float(rate / (k + shift))
        return float(np.clip(peak, 0.0, 1.0)), float(rate / k)


def iacc(nap_l, nap_r, max_lag):
    """Interaural cross-correlation per channel: the largest normalised correlation of the two NAPs within +-max_lag
    samples (mean removed), the peak refined by a parabola through its neighbours because the NAP is sampled at 2240 Hz
    (0.45 ms) and a true delay rarely falls on a sample. (channels, frames) in, (channels,) out, 0..1."""
    l = nap_l.astype(np.float64) - nap_l.mean(axis=1, keepdims=True)
    r = nap_r.astype(np.float64) - nap_r.mean(axis=1, keepdims=True)
    den = np.sqrt((l * l).sum(axis=1) * (r * r).sum(axis=1)) + 1e-12
    n = l.shape[1]
    lags = list(range(-int(max_lag) - 1, int(max_lag) + 2))
    cc = np.stack([(l[:, max(0, k):n + min(0, k)] * r[:, max(0, -k):n - max(0, k)]).sum(axis=1) / den for k in lags], axis=1)
    inner = cc[:, 1:-1]
    i = np.argmax(inner, axis=1)
    rows = np.arange(cc.shape[0])
    y0, y1, y2 = cc[rows, i], cc[rows, i + 1], cc[rows, i + 2]
    den2 = y0 - 2.0 * y1 + y2
    shift = np.where(np.abs(den2) > 1e-12, 0.5 * (y0 - y2) / den2, 0.0)
    peak = y1 - 0.25 * (y0 - y2) * np.clip(shift, -1.0, 1.0)
    return np.clip(np.maximum(peak, y1), 0.0, 1.0)


class BinauralSummariser:
    """IACC per frame from two ears run in lockstep: mean over the channels inside `iacc_band_hz`."""

    def __init__(self, ear_l, ear_r):
        self.l, self.r = ear_l, ear_r
        s = ear_l.p['summary']
        self.band = [float(v) for v in s['iacc_band_hz']]
        self.lag = int(round(float(s['iacc_max_lag_ms']) * 1e-3 * ear_l.nap_rate))
        self.frame = int(round(float(s['frame_s']) * ear_l.nap_rate))

    def run(self, left, right, chunk_s=None):
        sel = (self.l.fc >= self.band[0]) & (self.l.fc <= self.band[1])
        out = []
        buf_l = buf_r = None
        for (nl, _), (nr, _) in zip(self.l.stream(left, chunk_s), self.r.stream(right, chunk_s)):
            buf_l = nl[sel] if buf_l is None else np.concatenate([buf_l, nl[sel]], axis=1)
            buf_r = nr[sel] if buf_r is None else np.concatenate([buf_r, nr[sel]], axis=1)
            while buf_l.shape[1] >= self.frame:
                out.append(float(np.mean(iacc(buf_l[:, :self.frame], buf_r[:, :self.frame], self.lag))))
                buf_l, buf_r = buf_l[:, self.frame:], buf_r[:, self.frame:]
        return np.asarray(out, dtype=np.float32)
