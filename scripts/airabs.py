# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

#!/usr/bin/env python3
"""airabs.py - ISO 9613-1 atmospheric absorption as a linear-phase FIR filter.

alpha(f) in dB/m comes from the standard's O2/N2 relaxation formulas (temperature, humidity, pressure).
The filter has gain 10^(-alpha(f) * r / 20), built by frequency sampling, a Blackman window and a centred
delay, so it adds no phase colouring. Check values (20 C, 50 % RH, 101.325 kPa): about 5 dB/km at 1 kHz,
about 160 dB/km at 10 kHz. Spherical 1/r spreading is NOT included; apply it separately.
"""
import numpy as np
import scipy.signal as signal

SR = 44100
TAPS = 1025  # odd, so the centre tap is an exact integer delay


def iso_alpha_db_per_m(f, temp_c=20.0, rh=50.0, pressure_kpa=101.325):
    """ISO 9613-1 pure-tone absorption coefficient (dB/m) at frequencies f (Hz): Earth air, whatever the active medium."""
    f = np.asarray(f, dtype=np.float64)
    T = temp_c + 273.15
    T0, T01, pr = 293.15, 273.16, 101.325
    pp = pressure_kpa / pr
    C = -6.8346 * (T01 / T) ** 1.261 + 4.6151
    h = rh * 10.0 ** C / pp                      # molar concentration of water vapour, percent
    fr_o = pp * (24.0 + 4.04e4 * h * (0.02 + h) / (0.391 + h))
    fr_n = pp * (T / T0) ** -0.5 * (9.0 + 280.0 * h * np.exp(-4.170 * ((T / T0) ** (-1.0 / 3.0) - 1.0)))
    f2 = f * f
    return 8.686 * f2 * (
        1.84e-11 / pp * (T / T0) ** 0.5
        + (T / T0) ** -2.5 * (0.01275 * np.exp(-2239.1 / T) / (fr_o + f2 / fr_o)
                              + 0.1068 * np.exp(-3352.0 / T) / (fr_n + f2 / fr_n)))


def _route(temp_c, rh, pressure_kpa):
    """(medium, (temp_c, rh, pressure_kpa) or None). Earth air takes its own state unless the caller overrides it; any
    other active medium is asked, and an Earth-air setting given for it is an error, never silently ignored."""
    from phys_core import medium
    m = medium.active()
    if m.model != 'iso9613':
        if temp_c is not None or rh is not None or pressure_kpa is not None:
            raise ValueError(f'temp_c / rh / pressure are Earth-air settings, but the active medium is "{m.name}" '
                             f'({m.model}); put its state in the medium block instead')
        return m, None
    return m, (m.temp_c if temp_c is None else float(temp_c), m.rh if rh is None else float(rh),
               m.pressure_pa / 1000.0 if pressure_kpa is None else float(pressure_kpa))


def alpha_db_per_m(f, temp_c=None, rh=None, pressure_kpa=None):
    """Absorption (dB/m) of the ACTIVE medium at f (Hz). Earth air is ISO 9613-1 at the medium's state (20 C, 50 % RH,
    101.325 kPa unless the medium or the caller says otherwise); another medium answers with its own law."""
    m, st = _route(temp_c, rh, pressure_kpa)
    return iso_alpha_db_per_m(f, *st) if st else m.alpha_db_per_m(f)


def apply(x, distance_m, temp_c=None, rh=None, pressure_kpa=None, sr=SR):
    """Filter x ((N,) or (N, C)) for distance_m of the active medium. Returns float32, same shape."""
    m, st = _route(temp_c, rh, pressure_kpa)
    if st is None:
        return m.absorb(x, distance_m, sr)
    return iso_apply(x, distance_m, *st, sr=sr)


def iso_apply(x, distance_m, temp_c=20.0, rh=50.0, pressure_kpa=101.325, sr=SR):
    """The ISO 9613-1 linear-phase filter for distance_m of Earth air."""
    x = np.asarray(x, dtype=np.float32)
    if distance_m <= 0:
        return x
    freqs = np.linspace(0.0, sr / 2.0, TAPS // 2 + 1)
    gain = 10.0 ** (-iso_alpha_db_per_m(freqs, temp_c, rh, pressure_kpa) * float(distance_m) / 20.0)
    n = TAPS - 1
    ir = np.roll(np.fft.irfft(gain, n=n), n // 2)    # zero-phase response, centred
    ir = np.append(ir, 0.0) * signal.windows.blackman(TAPS)
    import compute
    out = (compute.fftconvolve(x, ir.astype(np.float32)) if compute.on_gpu()
           else signal.fftconvolve(x, ir if x.ndim == 1 else ir[:, None], mode='full', axes=0))
    start = TAPS // 2
    return out[start:start + len(x)].astype(np.float32)
