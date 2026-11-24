# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Microtiming: the errors a player makes, in two scales, plus the one drift a section shares.

The stage returns terms to add to an onset, never a finished event list: the caller owns the melody
lead, the strum and the articulation. `timing_beat_frac` makes the short-scale sigma follow the beat
instead of a fixed millisecond value; measured microtiming is 2.6-6.8 % of a beat, so a 60 BPM ballad
and a 128 BPM dance should not receive the same absolute spread.
"""
import numpy as np

from .form import _motor_streams
from .noise import _fractal_noise


def timing_terms(ns, c, rng, is_drum, drift, beta, step_beats, n, bpm):
    """Timing deviation terms for one line: {sig, frac, anti, drift_term}.

    `anti` already includes the short-scale 1/f part; `frac` is returned because the percussion
    velocity coupling reads the same curve (Rasanen et al. 2015: amplitudes share the intervals'
    long-range correlation). Draw order is fixed: fractal short band, then one motor draw per stream.
    """
    t_beats = np.array([nt['t'] for nt in ns], dtype=float)
    # a drum's own motor jitter stays conservative (<10 ms): beyond that the groove degrades (Fruhauf 2013)
    sig = (min(float(c['drum_ms']), 8.0) if is_drum else float(c['timing_ms'])) / 1000.0
    frac_beats = float(c.get('timing_beat_frac', 0.0) or 0.0)
    if frac_beats > 0.0 and bpm:
        beat_s = 60.0 / max(20.0, float(bpm))
        cap = float(c.get('timing_cap_ms', 40.0) or 40.0) / 1000.0
        if is_drum:
            cap = min(cap, 0.010)
        sig = max(sig, min(cap, frac_beats * beat_s))
    share = float(np.clip(c.get('short_share', 0.0), 0.0, 1.0))
    frac = _fractal_noise(rng, n, beta=beta,
                          fc=step_beats / max(1e-6, float(c.get('short_scale_beats', 8.0))), highpass=True)
    frac_term = frac * sig * np.sqrt(share)      # the short-scale (<8 beats) 1/f process, per player
    motor_sig = sig * np.sqrt(max(0.0, 1.0 - share))
    # motor error: each note is pulled back by a fraction of the previous one of the SAME limb/finger, which is where
    # the negative lag-1 correlation of a real player comes from. Never across limbs or across a chord's fingers.
    anti = np.zeros(n)
    lag1 = float(c.get('note_lag1', 0.5))
    for stream in _motor_streams(ns, is_drum):
        m = len(stream)
        e = rng.standard_normal(m) * motor_sig
        a = e.copy()
        if m > 1:
            a[1:] = e[1:] - lag1 * e[:-1]
        anti[np.asarray(stream)] = a
    anti = anti + frac_term
    # slow wander: shared by every track of the piece when the tempo map carries one (tempo_map_for builds it)
    if isinstance(drift, (tuple, list)) and len(drift) == 2:
        grid, vals = np.asarray(drift[0], float), np.asarray(drift[1], float)
        drift_term = np.interp(t_beats, grid, vals) * (c['drift_ms'] / 1000.0)
    elif drift is not None and len(drift):
        d = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(drift)), np.asarray(drift, float))
        drift_term = d * (c['drift_ms'] / 1000.0)
    else:
        drift_term = (_fractal_noise(rng, n, beta=beta, fc=step_beats / max(1.0, float(c.get('drift_corr_beats', 6.0))))
                      * (c['drift_ms'] / 1000.0) * 0.5)
    return dict(sig=sig, frac=frac, anti=anti, drift_term=drift_term)
