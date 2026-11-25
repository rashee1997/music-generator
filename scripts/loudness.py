# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""loudness.py - ITU-R BS.1770 loudness for any channel count, measured once and reused.

Two things the stereo meter (pyloudnorm, through mixer.lufs) could not do:

  * weight the channels of a loudspeaker layout. BS.1770 sums the K-weighted mean squares of the channels with a
    weight per channel (surrounds count more than fronts, the low-frequency channel is left out). The weights are
    data: each layout preset carries `loudness_weight_db` per speaker and marks its `lfe` speaker.
  * answer several questions from one pass. The K-weighting filters are the expensive part; integrated loudness,
    the short-term series and the loudness range all come from the same 400 ms block energies, so they are filtered
    once (`Blocks`) instead of once per 3 s window.

The K-weighting coefficients are pyloudnorm's own (dsp.meter), so a stereo programme measures the same here as it
does through mixer.lufs. The gates (-70 LKFS absolute, -10 LU relative), the 400 ms block and its 75 % overlap are
the standard's, not this project's: they are named constants below, with the clause that defines each.
"""
import numpy as np
from scipy import signal

BLOCK_S = 0.4            # BS.1770-5 Annex 1: gating block
OVERLAP = 0.75           # ... overlapping by 75 %
ABS_GATE = -70.0         # ... absolute threshold, LKFS
REL_GATE = -10.0         # ... relative threshold, LU below the absolute-gated loudness
OFFSET = -0.691          # ... the constant that makes a 997 Hz full-scale sine read -3.01 LKFS
SHORT_S = 3.0            # EBU Tech 3341: short-term window
LRA_GATE = -20.0         # EBU Tech 3342: relative gate of the loudness range
LRA_PCT = (10.0, 95.0)   # ... and its percentiles
SILENCE = -70.0


def k_weight(x, sr):
    """x (N, C) through the two K-weighting stages, every channel at once."""
    import dsp
    y = np.asarray(x, dtype=np.float64)
    if y.ndim == 1:
        y = y[:, None]
    for stage in dsp.meter(sr)._filters.values():
        y = stage.passband_gain * signal.lfilter(stage.b, stage.a, y, axis=0)
    return y


def weights_for(layout_name):
    """(C,) linear power weights in the layout's channel order: 10^(dB/10) per speaker, 0 for the LFE."""
    from spatial_engine import config
    out = []
    for sp in config.layout(layout_name).get('speakers') or []:
        out.append(0.0 if sp.get('lfe') else 10.0 ** (float(sp.get('loudness_weight_db', 0.0)) / 10.0))
    return np.asarray(out, dtype=np.float64)


class Blocks:
    """The 400 ms block energies of a programme: z[j] = sum over channels of weight * mean square, K-weighted."""

    def __init__(self, x, sr, weights=None):
        y = np.asarray(x)
        if y.ndim == 1:
            y = y[:, None]
        self.sr = int(sr)
        n_block = int(round(BLOCK_S * self.sr))
        self.hop = int(round(BLOCK_S * (1.0 - OVERLAP) * self.sr))
        if len(y) < n_block:                        # shorter than one block: pad, as the stereo meter always has
            y = np.pad(y, ((0, n_block - len(y)), (0, 0)))
        w = np.ones(y.shape[1]) if weights is None else np.asarray(weights, dtype=np.float64)
        if len(w) != y.shape[1]:
            raise ValueError(f'{len(w)} loudness weights for {y.shape[1]} channels')
        k = k_weight(y, self.sr)
        power = np.einsum('ij,ij,j->i', k, k, w)    # weighted instantaneous power, no N x C temporaries
        c = np.concatenate([[0.0], np.cumsum(power)])
        starts = np.arange(0, len(power) - n_block + 1, self.hop)
        self.z = (c[starts + n_block] - c[starts]) / float(n_block)
        self.per_s = self.sr / float(self.hop)      # blocks per second

    @staticmethod
    def _db(z):
        return OFFSET + 10.0 * np.log10(np.maximum(z, 1e-30))

    @classmethod
    def _gated(cls, z):
        if not len(z):
            return SILENCE
        l = cls._db(z)
        keep = l >= ABS_GATE
        if not keep.any():
            return SILENCE
        rel = cls._db(np.mean(z[keep])) + REL_GATE
        keep &= l > rel
        if not keep.any():
            return SILENCE
        return float(cls._db(np.mean(z[keep])))

    def integrated(self):
        """Gated programme loudness, LKFS."""
        return self._gated(self.z)

    def short_term(self, hop_s=0.5):
        """The ungated 3 s loudness every `hop_s` seconds (EBU Tech 3341), LKFS."""
        n = int(round((SHORT_S - BLOCK_S) * self.per_s)) + 1        # blocks that tile one 3 s window
        step = max(1, int(round(hop_s * self.per_s)))
        if len(self.z) < n:
            return np.array([float(self._db(np.mean(self.z)))]) if len(self.z) else np.array([SILENCE])
        # non-overlapping quarters of each 400 ms block tile the window exactly: mean of every 4th block
        idx = np.arange(0, len(self.z) - n + 1, step)
        pick = np.arange(0, n, int(round(1.0 / (1.0 - OVERLAP))))
        return self._db(np.mean(self.z[idx[:, None] + pick[None, :]], axis=1))

    def gated_series(self, win_s=SHORT_S, hop_s=0.5):
        """The gated loudness of each `win_s` window (every 400 ms block inside it, both gates applied within the
        window). This is the series mixer.master_measures has always reported; it is kept so a master measures the
        same as before, at one filtering pass instead of one per window."""
        n = int(round((win_s - BLOCK_S) * self.per_s)) + 1
        step = max(1, int(round(hop_s * self.per_s)))
        if len(self.z) < n:
            return np.array([self._gated(self.z)])
        return np.array([self._gated(self.z[i:i + n]) for i in range(0, len(self.z) - n + 1, step)])

    @classmethod
    def lra_gate(cls, st):
        """The short-term values that count for a loudness range: above the absolute gate, then above the
        POWER mean of those minus 20 LU (EBU Tech 3342; an arithmetic mean of dB values would sit too low)."""
        st = np.asarray(st, dtype=np.float64)
        st = st[st > ABS_GATE]
        if not len(st):
            return st
        power = 10.0 ** ((st - OFFSET) / 10.0)
        return st[st > float(cls._db(np.mean(power))) + LRA_GATE]

    def lra(self, hop_s=0.5):
        """Loudness range, LU (EBU Tech 3342): the spread of the short-term loudness between its gated percentiles."""
        st = self.lra_gate(self.short_term(hop_s))
        if len(st) < 5:
            return 0.0
        lo, hi = np.percentile(st, LRA_PCT)
        return float(hi - lo)


def integrated(x, sr, weights=None):
    return Blocks(x, sr, weights).integrated()


def layout_lufs(audio, layout_name, sr):
    """Programme loudness of a multichannel file in a layout's channel order, with that layout's own weights."""
    return integrated(audio, sr, weights_for(layout_name))
