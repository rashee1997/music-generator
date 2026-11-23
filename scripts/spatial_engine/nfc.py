# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""nfc.py - near-field-coded encoding for sources inside the reference sphere.

Daniel's distance-coding filters (AES 23rd Convention, 2003; Adriaensen 2007) apply one filter per Ambisonic
order so the encoded field keeps the curvature of a spherical wave instead of assuming a plane wave. The
combined source/compensation filter used here is the ratio given by Adamek et al. (DAGA 2010, eq. 1):

    H_m(k) = [ h_m(k r_s) / h_0(k r_s) ] * [ h_0(k R) / h_m(k R) ]

with `h` the spherical Hankel function of the second kind, `r_s` the source distance, `R` the reference
radius and `k = 2*pi*f/c`. For m = 0 the ratio is 1, so only the higher orders carry the near-field cue.

At low frequency the gain grows like (R/r_s)^m, which is why every implementation caps it: Favrot &
Buchholz regularise their filters at 30 dB, and loudspeakers cannot reproduce more than that anyway. The cap
here is a preset value (`immersive.nfc.max_gain_db`), not a constant of the physics.

This module filters the direct sound only. Reflections and the late field are encoded without NFC: a room
tap is a distant image source, and the cue it would carry is below the level where it matters.
"""
import numpy as np

C = 343.0
DEFAULT_CAP_DB = 30.0


def order_gains(freqs, order, distance_m, ref_m=1.0, cap_db=DEFAULT_CAP_DB):
    """(order+1, bins) complex NFC gains for a source at `distance_m`, relative to `ref_m`.

    Frequencies at or below 1 Hz are clamped: the spherical Hankel ratio diverges at DC and no programme
    carries that band.
    """
    from spatial_hrtf import sph
    f = np.maximum(np.asarray(freqs, float), 1.0)
    k = 2.0 * np.pi * f / C
    r = max(float(distance_m), 1e-3)
    ref = max(float(ref_m), 1e-3)
    if abs(r - ref) < 1e-9:
        return np.ones((int(order) + 1, len(f)), dtype=complex)
    h0_s = sph.spherical_hn2(0, k * r)
    h0_r = sph.spherical_hn2(0, k * ref)
    out = np.empty((int(order) + 1, len(f)), dtype=complex)
    for m in range(int(order) + 1):
        hm_s = sph.spherical_hn2(m, k * r)
        hm_r = sph.spherical_hn2(m, k * ref)
        out[m] = (hm_s / h0_s) * (h0_r / hm_r)
    cap = 10.0 ** (float(cap_db) / 20.0)
    return np.minimum(np.abs(out), cap) * np.exp(1j * np.angle(out))


def apply(x, order, distance_m, sr, ref_m=1.0, cap_db=DEFAULT_CAP_DB):
    """(n, order+1) signals: one filtered copy of `x` per Ambisonic order. Zero-phase, offline (FFT)."""
    from scipy.fft import next_fast_len
    x = np.asarray(x, dtype=float).ravel()
    n = len(x)
    if n == 0:
        return np.zeros((0, int(order) + 1))
    nfft = int(next_fast_len(2 * n))
    freqs = np.fft.rfftfreq(nfft, 1.0 / float(sr))
    gains = order_gains(freqs, order, distance_m, ref_m, cap_db)
    spec = np.fft.rfft(x, nfft)
    return np.stack([np.fft.irfft(spec * gains[m], nfft)[:n] for m in range(int(order) + 1)], axis=1)


def boost_db(order, distance_m, ref_m=1.0, cap_db=DEFAULT_CAP_DB):
    """The low-frequency boost (dB) the filters apply to the highest order, for the delivery report."""
    g = order_gains(np.array([20.0]), order, distance_m, ref_m, cap_db)
    return float(20.0 * np.log10(np.abs(g[-1, 0]) + 1e-30))
