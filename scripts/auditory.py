# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""auditory.py - the one home of the auditory scales: ERB rate and bandwidth, Bark, and the absolute threshold.

Every module that needs a critical-band scale or the threshold of hearing imports it from here, so the gate, the mixer
and the ear model cannot drift apart. Pure numpy.

  ERB rate           Glasberg & Moore (1990): 21.4 log10(0.00437 f + 1)
  ERB bandwidth      24.7 (4.37 f / 1000 + 1) Hz
  Bark               Traunmuller (1990): 26.81 f / (1960 + f) - 0.53
  absolute threshold Terhardt's approximation (dB SPL); a relative weighting, never an absolute SPL calibration
"""
import numpy as np


def erb_rate(f):
    return 21.4 * np.log10(4.37e-3 * np.asarray(f, dtype=np.float64) + 1.0)


def erb_to_hz(e):
    return (10.0 ** (np.asarray(e, dtype=np.float64) / 21.4) - 1.0) / 4.37e-3


def erb_bandwidth(f):
    """Equivalent rectangular bandwidth in Hz at centre frequency `f`."""
    return 24.7 * (4.37 * np.asarray(f, dtype=np.float64) / 1000.0 + 1.0)


def erb_edges(lo=100.0, hi=5000.0):
    """Band edges one ERB apart from `lo` to `hi` Hz."""
    k = np.arange(np.ceil(erb_rate(lo)), np.floor(erb_rate(hi)) + 1.0)
    return erb_to_hz(k)


def erb_centres(lo, hi, count):
    """`count` centre frequencies evenly spaced on the ERB-rate scale from `lo` to `hi` Hz, ascending."""
    return erb_to_hz(np.linspace(erb_rate(lo), erb_rate(hi), int(count)))


def bark(f):
    """Critical-band rate in Bark (Traunmuller)."""
    f = np.asarray(f, dtype=np.float64)
    return 26.81 * f / (1960.0 + f) - 0.53


def ath_db(f):
    """Terhardt's absolute threshold of hearing (dB SPL) for f in Hz: the sensitivity dip near 3.3 kHz that ISO 226's
    threshold region encodes. Used as a relative weighting, never as an absolute SPL calibration."""
    k = np.maximum(np.asarray(f, dtype=np.float64), 20.0) / 1000.0
    return 3.64 * k ** -0.8 - 6.5 * np.exp(-0.6 * (k - 3.3) ** 2) + 1e-3 * k ** 4
