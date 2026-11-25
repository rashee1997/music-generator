# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""model.py - the streaming peripheral model: audio in, neural activity pattern (NAP) out.

Stages, per chunk of a few seconds, all state carried between chunks (`zi` / `zf`) so a chunked run equals an unchunked
one to float32 rounding:

  middle ear   linear-phase FIR whose gain is the inverse of the absolute threshold (auditory.ath_db), clipped
  cochlea      serial cascade of asymmetric resonators at ERB spacing (a pole pair with a zero pair above it); channel
               k is the input of stage k minus its output, so it is shaped by every stage basal to it (Lyon) and has no
               low-frequency tail: a unit-gain cascade tap alone drives every basal channel with a low tone
  compression  a gain per channel and per block of `block` samples (about 3 ms), from the block's level smoothed in
               time and spread over neighbouring channels (suppression); feed-forward, vectorised over all channels.
               CARFAC proper feeds the level back into each stage's damping; that needs a coefficient update every
               block inside the cascade, which costs about 20 s per minute of audio in numpy, so it is not done here
  hair cell    half-wave rectification, saturation, low-pass (phase locking falls off)
  adaptation   divisive gain with a fast and a slow time constant; the slow store's fill is `depth`, the fatigue proxy
  decimation   anti-alias low-pass and every `decimate`-th sample: 22400 Hz -> 2240 Hz

Memory: one chunk of (channels, samples) float32 (21 MB for 48 channels and 5 s) plus one-channel float64 rows.
Rows are processed one at a time, so no (channels, samples) float64 array is ever built. Parameters: the `ear` preset
`model`; every number is a starting value (see its `sources`).
"""
import math

import numpy as np
from scipy.signal import butter, firwin2, lfilter, lfilter_zi, resample_poly, sosfilt, sosfilt_zi

import auditory
import presets


def params(name='model'):
    p = dict(presets.get('ear', name))
    p.pop('_source', None)
    return p


def _unit_dc(b, a):
    return np.asarray(b, dtype=np.float64) * (np.sum(a) / np.sum(b))


class EarModel:
    def __init__(self, sr=44100, p=None):
        self.p = p or params()
        self.sr_in = int(sr)
        self.rate = int(self.p['rate_hz'])
        self.block = int(self.p['block'])
        self.decimate = int(self.p['decimate'])
        self.nap_rate = self.rate / float(self.decimate)
        self.n = int(self.p['channels'])
        # centres, basal (high) first: the cascade runs from the base to the apex
        self.fc = auditory.erb_centres(self.p['f_lo_hz'], min(self.p['f_hi_hz'], 0.45 * self.rate), self.n)[::-1].copy()
        self._design()
        self.reset()

    # ---- design -------------------------------------------------------------------------------------------
    def _design(self):
        p, rate = self.p, float(self.rate)
        taps = int(p['middle_ear']['taps']) | 1
        f = np.linspace(0.0, rate / 2.0, 257)
        g_db = np.clip(float(auditory.ath_db(1000.0)) - auditory.ath_db(np.maximum(f, 20.0)),
                       p['middle_ear']['min_db'], p['middle_ear']['max_db'])
        self.me_taps = firwin2(taps, f / (rate / 2.0), 10.0 ** (g_db / 20.0))
        c = p['car']
        self.car = []
        for fc in self.fc:
            th = 2.0 * np.pi * fc / rate
            r = 1.0 - float(c['zeta']) * th
            thz = min(th * float(c['zero_ratio']), 0.98 * np.pi)
            rz = 1.0 - float(c['zeta']) * float(c['zero_zeta_ratio']) * thz
            b = [1.0, -2.0 * rz * math.cos(thz), rz * rz]
            a = [1.0, -2.0 * r * math.cos(th), r * r]
            self.car.append((_unit_dc(b, a), np.asarray(a, dtype=np.float64)))
        g = p['agc']
        self.agc_a = math.exp(-1.0 / (float(g['tau_ms']) * 1e-3 * rate / self.block))        # per block
        self.agc_up = math.exp(-1.0 / self.block)                                             # gain upsampling, per sample
        self.knee = 10.0 ** (float(g['knee_dbfs']) / 20.0)
        self.slope = float(g['slope'])
        self.min_gain = 10.0 ** (float(g['min_gain_db']) / 20.0)
        self.spread = np.asarray(g['spread'], dtype=np.float64)
        h = p['ihc']
        self.ihc_sos = butter(int(h['order']), float(h['lowpass_hz']), fs=rate, output='sos')
        a_ = p['adapt']
        self.ad_fast = math.exp(-1.0 / (float(a_['tau_fast_ms']) * 1e-3 * rate))
        self.ad_slow = math.exp(-1.0 / (float(a_['tau_slow_ms']) * 1e-3 * rate))
        n = p['nap']
        self.aa_sos = butter(int(n['antialias_order']), float(n['antialias_hz']), fs=rate, output='sos')

    def reset(self):
        n = self.n
        self.z_me = np.zeros(len(self.me_taps) - 1)
        self.z_car = [lfilter_zi(b, a) * 0.0 for b, a in self.car]
        self.z_agc = np.zeros((n, 1))
        self.last_gain = np.ones(n)
        self.z_ihc = [sosfilt_zi(self.ihc_sos) * 0.0 for _ in range(n)]
        self.z_fast = np.zeros(n)
        self.z_slow = np.zeros(n)
        self.z_aa = [sosfilt_zi(self.aa_sos) * 0.0 for _ in range(n)]

    # ---- input --------------------------------------------------------------------------------------------
    def prepare(self, x):
        """Mono at the input rate -> float32 at the model rate, zero-padded to a whole number of blocks and decimation steps."""
        x = np.asarray(x, dtype=np.float32)
        if x.ndim == 2:
            x = x.mean(axis=1)
        if self.sr_in != self.rate:
            g = math.gcd(self.sr_in, self.rate)
            x = resample_poly(x, self.rate // g, self.sr_in // g).astype(np.float32)
        unit = self.block * self.decimate // math.gcd(self.block, self.decimate)
        pad = (-len(x)) % unit
        return np.pad(x, (0, pad)) if pad else x

    def chunk_samples(self, chunk_s=None):
        unit = self.block * self.decimate // math.gcd(self.block, self.decimate)
        return max(unit, int(round(float(chunk_s or self.p['chunk_s']) * self.rate / unit)) * unit)

    # ---- one chunk ----------------------------------------------------------------------------------------
    def _chunk(self, x):
        T, n, B = len(x), self.n, self.block
        y, self.z_me = lfilter(self.me_taps, [1.0], x.astype(np.float64), zi=self.z_me)
        tap = np.empty((n, T), dtype=np.float32)
        for k, (b, a) in enumerate(self.car):
            prev = y
            y, self.z_car[k] = lfilter(b, a, prev, zi=self.z_car[k])
            tap[k] = prev - y          # the stage's input minus its output: a band-pass at the stage, no low-frequency tail
        del y, prev
        # block-rate level, smoothed in time, spread over neighbouring channels
        nb = T // B
        blocks = tap.reshape(n, nb, B)
        power = np.einsum('cnb,cnb->cn', blocks, blocks, dtype=np.float32) / np.float32(B)
        env = np.sqrt(power.astype(np.float64))
        a = self.agc_a
        env, self.z_agc = lfilter([1.0 - a], [1.0, -a], env, axis=1, zi=self.z_agc)
        pad = np.pad(env, ((1, 1), (0, 0)), mode='edge')
        s = self.spread
        env = s[0] * pad[:-2] + s[1] * pad[1:-1] + s[2] * pad[2:]
        gain = np.minimum(1.0, (np.maximum(env, self.knee) / self.knee) ** (self.slope - 1.0))
        gain = np.maximum(gain, self.min_gain)
        nap = np.empty((n, T // self.decimate), dtype=np.float32)
        depth = np.empty_like(nap)
        sat = float(self.p['ihc']['sat'])
        thr = float(self.p['ihc'].get('threshold', 0.0))
        c0 = float(self.p['adapt']['c'])
        D = self.decimate
        for c in range(n):
            g = np.repeat(gain[c], B)
            g, _ = lfilter([1.0 - self.agc_up], [1.0, -self.agc_up], g, zi=[self.last_gain[c] * self.agc_up])
            self.last_gain[c] = g[-1]
            v = tap[c].astype(np.float64) * g
            v -= thr
            np.maximum(v, 0.0, out=v)
            v = v / (v + sat)
            v, self.z_ihc[c] = sosfilt(self.ihc_sos, v, zi=self.z_ihc[c])
            m, self.z_fast[c] = self._ema(v, self.ad_fast, self.z_fast[c])
            v = v / (c0 + m)
            m, self.z_slow[c] = self._ema(v, self.ad_slow, self.z_slow[c])
            d = m / (c0 + m)
            v = v / (c0 + m)
            v, self.z_aa[c] = sosfilt(self.aa_sos, v, zi=self.z_aa[c])
            nap[c] = v[D - 1::D]
            depth[c] = d[D - 1::D]
        return nap, depth

    @staticmethod
    def _ema(v, a, z):
        out, zf = lfilter([1.0 - a], [1.0, -a], v, zi=[a * z])
        return out, out[-1]

    # ---- public -------------------------------------------------------------------------------------------
    def stream(self, x, chunk_s=None):
        """Yield (nap, depth) float32 chunks of shape (channels, frames at nap_rate). `x` is mono at the input rate.
        State is reset first, so a call analyses one signal."""
        self.reset()
        x = self.prepare(x)
        step = self.chunk_samples(chunk_s)
        for i in range(0, len(x), step):
            yield self._chunk(x[i:i + step])

    def run(self, x, chunk_s=None):
        """The whole NAP and depth as (channels, frames) arrays: for short signals and tests only; a track should stream."""
        parts = list(self.stream(x, chunk_s))
        return np.concatenate([p[0] for p in parts], axis=1), np.concatenate([p[1] for p in parts], axis=1)
