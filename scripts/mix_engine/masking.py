"""masking - how far the beds sit above the figure, per critical band.

The existing `masking.vs_melody` row compares eight fixed ERB bands and a broadband margin. This module
adds the measurement the masking literature actually describes: the beds' level in a band against the
figure's level in the *same* band, so the report can name the bands and the moments where one part is
covering another.

It is a band-level proxy, not a full excitation-pattern model: simultaneous masking is approximated by
comparing energies in the same critical band. The asymmetry of masking (a lower masker spreads upward,
Moore 2007) is why the bands are compared one band up as well, but no dB threshold is asserted here.
Numbers from this module are reported; a pass/fail mark would need listening calibration the engine
cannot perform, so the gate keeps this advisory.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

SR = 44100

# critical-band-ish analysis bands (Zwicker & Terhardt: ~100 Hz below 500 Hz, ~20 % above). 15 bands
# cover the range where a bed masks a figure; above 11 kHz masking is not the problem.
BANDS_HZ = ((40, 80), (80, 120), (120, 180), (180, 250), (250, 350), (350, 500), (500, 700),
            (700, 1000), (1000, 1400), (1400, 2000), (2000, 2800), (2800, 4000), (4000, 5600),
            (5600, 8000), (8000, 11000))

SPREAD_BANDS = 1        # a masker's energy spreads into the next band up


def _mono(x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        x = x.mean(axis=1)
    return x


def band_energy_db(x, sr=SR, bands=BANDS_HZ):
    """Mean power of each band over the whole signal, in dB (0 dB = full-scale mean square)."""
    y = _mono(x)
    out = []
    for lo, hi in bands:
        hi = min(hi, sr / 2.0 - 1.0)
        if lo >= hi:
            continue
        sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
        try:
            b = signal.sosfiltfilt(sos, y)
        except ValueError:
            out.append((lo, hi, float('-inf')))
            continue
        out.append((lo, hi, float(10.0 * np.log10(np.mean(b ** 2) + 1e-20))))
    return out


def band_excess_db(focus, beds, sr=SR, bands=BANDS_HZ):
    """Per band: how far the beds sit above the figure, and the same one band up.

    `excess_db` is the simultaneous case (beds minus figure in the same band); `spread_db` is the
    upward-spread case (beds in a band minus the figure one band below). Both are dB, both are reported
    as measurements.
    """
    f = band_energy_db(focus, sr, bands)
    b = band_energy_db(beds, sr, bands)
    out = []
    for i, ((lo, hi, fe), (_lo, _hi, be)) in enumerate(zip(f, b)):
        excess = be - fe
        spread = (be - f[i - SPREAD_BANDS][2]) if i >= SPREAD_BANDS else float('-inf')
        out.append(dict(band_hz=(lo, hi), focus_db=fe, beds_db=be,
                        excess_db=float(excess), spread_db=float(spread)))
    return out


def describe(rows, floor_db=0.0, top=3):
    """(worst bands above `floor_db`, message) for a report or an INFO row."""
    loud = [r for r in rows if np.isfinite(r['excess_db']) and r['excess_db'] > floor_db]
    loud.sort(key=lambda r: r['excess_db'], reverse=True)
    if not loud:
        return [], f'the beds stay within {floor_db:g} dB of the figure in every measured band'
    parts = [f'{r["band_hz"][0]}-{r["band_hz"][1]} Hz +{r["excess_db"]:.1f} dB' for r in loud[:top]]
    return loud, ('the beds sit above the figure in ' + ', '.join(parts)
                  + ' (band-level masking proxy; a report, not a threshold)')
