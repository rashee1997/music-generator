# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""decorrelate.py - short all-pass decorrelation for surround and height channels.

Kendall, G. S. (1995). "The decorrelation of audio signals and its impact on spatial imagery." Computer Music
Journal 19(4), 71-87.

Two surround channels carrying the same signal collapse to a point between the speakers and comb-filter against each
other whenever the listener moves. A first-order all-pass (flat magnitude, phase only) with a different coefficient per
channel keeps the timbre while breaking the correlation. The amount and the maximum delay live in the layout preset.
"""
import numpy as np
from scipy.signal import lfilter


def _coefficient(seed, max_delay_ms, sr):
    """A deterministic all-pass coefficient in the range the layout allows, from a channel seed."""
    rng = np.random.default_rng(int(seed))
    # the coefficient sets the group delay; keep it inside the layout's allowed window
    max_a = float(np.clip(1.0 - 1.0 / max(2.0, float(max_delay_ms) * sr / 1000.0), 0.0, 0.95))
    return float(rng.uniform(0.2, max(0.25, max_a)))


def allpass(y, seed, max_delay_ms, sr, amount=1.0):
    """Phase-only decorrelation of one channel. `amount` 0 leaves the signal untouched, 1 is the full all-pass."""
    x = np.asarray(y, dtype=np.float64)
    if amount <= 0.0:
        return x.copy()
    a = _coefficient(seed, max_delay_ms, sr)
    # y[n] = -a*x[n] + x[n-1] + a*y[n-1]
    wet = lfilter([-a, 1.0], [1.0, -a], x)
    return (1.0 - amount) * x + amount * wet


def bus(channels, cfg, sr, names=None):
    """Decorate a dict {speaker name: array} of surround/height channels. `names` limits which ones (default: all but L/R/C)."""
    if not (cfg or {}).get('enabled'):
        return channels
    amount = float(cfg.get('amount', 0.0))
    max_delay = float(cfg.get('max_delay_ms', 0.0))
    keep = set(cfg.get('exempt') or ['L', 'R', 'FL', 'FR', 'FC', 'C'])
    out = {}
    for i, (name, y) in enumerate(sorted(channels.items())):
        if name in keep or name in set(names or []):
            out[name] = y
        else:
            out[name] = allpass(y, seed=1009 + i * 7919, max_delay_ms=max_delay, sr=sr, amount=amount)
    return out
