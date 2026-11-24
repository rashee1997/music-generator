# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Seeded noise: smooth, 1/f^beta fractal, and the one drift curve a whole piece shares."""
import numpy as np

from .config import PRESETS, TIMING


def _smooth_noise(rng, n, corr):
    """Slowly varying zero-mean noise with unit std; `corr` = correlation length in samples."""
    if n <= 0:
        return np.zeros(0)
    w = rng.standard_normal(n + int(corr) * 6)
    k = np.exp(-0.5 * (np.arange(-3 * int(corr) - 1, 3 * int(corr) + 2) / max(corr, 1)) ** 2)
    y = np.convolve(w, k / k.sum(), mode='same')[int(corr) * 3:int(corr) * 3 + n]
    s = y.std()
    return (y - y.mean()) / (s if s > 1e-9 else 1.0)


def _fractal_noise(rng, n, beta=0.85, fc=None, highpass=False):
    """1/f^beta noise with unit std, shaped in the frequency domain.

    Human timing and loudness are long-range correlated rather than smoothed white noise: every frequency bin of a
    white draw is scaled by f**(-beta/2), so the series carries a scale-free cascade instead of a single Gaussian
    cutoff (Rasanen et al. 2015 on intervals AND amplitudes; Sogorski, Geisel & Priesemann 2018 on the two regimes).
    `fc` (cycles per sample) is a soft band edge: with `highpass` the slow trend is removed (the short-scale process,
    inside `short_scale_beats`), without it the fast detail is removed (the long-scale process, the shared wander).
    """
    n = int(n)
    if n <= 0:
        return np.zeros(0)
    if n < 3:
        return np.zeros(n)
    w = rng.standard_normal(n)
    spec = np.fft.rfft(w)
    f = np.fft.rfftfreq(n)
    f = np.where(f <= 0.0, 1.0 / n, f)
    amp = f ** (-0.5 * float(beta))
    if fc and float(fc) > 0.0:
        lp = 1.0 / (1.0 + (f / float(fc)) ** 4)
        amp = amp * ((1.0 - lp) if highpass else lp)
    y = np.fft.irfft(spec * amp, n)
    y = y - y.mean()
    s = float(y.std())
    return y / s if s > 1e-12 else np.zeros(n)


def shared_drift(seed, total_beats, preset='natural', points=512):
    """One slow wander for the whole piece, as (beats, values), so every track drifts together.

    Measured before this: each track built its own drift, so two players of the same section wandered apart by tens of
    milliseconds. A section shares its tempo drift and differs only in the small motor error of each note, which is
    what `note_lag1` produces. Its shape is 1/f^beta below the drift correlation length, not one Gaussian cutoff.
    """
    c = dict(PRESETS['natural'])
    c.update(TIMING)
    if isinstance(preset, str):
        c.update(PRESETS.get(preset, {}))
    elif isinstance(preset, dict):
        c.update(preset)
    rng = np.random.default_rng(int(seed) + 7919)
    g = np.linspace(0.0, max(1.0, float(total_beats)), int(points))
    span = float(c.get('drift_corr_beats', 6.0)) * 8.0
    beats_per_point = max(float(total_beats), 1.0) / max(int(points), 1)
    vals = _fractal_noise(rng, int(points), beta=float(c.get('fractal_beta', 0.85)),
                          fc=beats_per_point / max(span, 1.0))
    return g, vals * 0.5
