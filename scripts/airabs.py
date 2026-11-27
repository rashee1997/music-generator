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

Two things are kept between calls, because a render asks for the same air hundreds of times:

  alpha_spectrum()  the coefficient on a transform's own rfft grid, per (bins, rate, air state). A room's
                    reflection taps all read the same grid at different distances.
  iso_fir()         the 1025-tap impulse response, per (distance, air state, rate), in a cache bounded by bytes.

The convolution runs through `compute`, so `MUSICGEN_FFT_WORKERS` and a GPU apply here as they do to the rest of
the engine. On the CPU the transform is float64 with SciPy's own next_fast_len, which is the arithmetic this module
always used, so a CPU render does not depend on `compute` for its numbers.
"""
import collections
import threading

import numpy as np
import scipy.signal as signal

SR = 44100
TAPS = 1025  # odd, so the centre tap is an exact integer delay

_ALPHA_CACHE = collections.OrderedDict()     # (bins, sr, state) -> alpha in dB/m on that rfft grid
_ALPHA_MAX = 96                              # a grid is at most half a transform long: a few megabytes in all
_FIR_CACHE = collections.OrderedDict()       # (distance, state, sr, taps) -> the impulse response
_FIR_CACHE_BYTES = 32 * 1024 * 1024          # a 1025-tap response is 8 kB: four thousand distinct paths
_LOCK = threading.Lock()                     # a hoa render places sources on worker threads


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


def _state(temp_c, rh, pressure_kpa):
    """The air state as a cache key: a hundredth of a degree, a hundredth of a percent, a tenth of a pascal."""
    return (round(float(temp_c), 4), round(float(rh), 4), round(float(pressure_kpa), 5))


def alpha_spectrum(bins, sr=SR, temp_c=None, rh=None, pressure_kpa=None):
    """alpha (dB/m) of the active medium on the rfft grid of a `bins`-point transform, kept per (grid, rate, state).

    The spectrum, not an array of arbitrary frequencies: every caller in the engine reads either this grid or a
    fixed octave table, and the room's taps ask for the same grid at a dozen different paths. A `temp_c` / `rh`
    overrides the active medium's own state the way `apply` does.
    """
    m, st = _route(temp_c, rh, pressure_kpa)
    grid = np.fft.rfftfreq(int(bins), 1.0 / float(sr))
    if st is None:                                  # another medium: its own law, keyed on its own description
        key = (int(bins), int(sr), 'medium', m.describe())
    else:
        key = (int(bins), int(sr)) + _state(*st)
    with _LOCK:
        got = _ALPHA_CACHE.get(key)
        if got is not None:
            _ALPHA_CACHE.move_to_end(key)
            return got
    got = iso_alpha_db_per_m(grid, *st) if st else m.alpha_db_per_m(grid)
    with _LOCK:
        _ALPHA_CACHE[key] = got
        while len(_ALPHA_CACHE) > _ALPHA_MAX:
            _ALPHA_CACHE.popitem(last=False)
    return got


def cached_fir(key, build):
    """`build()`'s impulse response, kept under `key` in the shared FIR cache (bounded by bytes, thread-safe).

    The cache is what a medium with its own absorption law uses: designing a 1025-tap response is an inverse
    transform and a window, and a render asks for the same path once per tap and once per air blend level.
    The cached array is read-only; `iso_fir` hands out a copy for callers that want to edit one.
    """
    with _LOCK:
        got = _FIR_CACHE.get(key)
        if got is not None:
            _FIR_CACHE.move_to_end(key)
            return got
    got = np.asarray(build(), dtype=np.float64)
    got.flags.writeable = False
    if got.nbytes <= _FIR_CACHE_BYTES:
        with _LOCK:
            _FIR_CACHE[key] = got
            while sum(v.nbytes for v in _FIR_CACHE.values()) > _FIR_CACHE_BYTES and len(_FIR_CACHE) > 1:
                _FIR_CACHE.popitem(last=False)          # the least recently used path goes first
    return got


def clear_caches():
    """Forget every cached spectrum and response (tests, and a render that changes the air mid-piece)."""
    with _LOCK:
        _ALPHA_CACHE.clear()
        _FIR_CACHE.clear()


def cache_info():
    """(spectra, responses, bytes of the responses): what the two caches hold right now, for a report."""
    with _LOCK:
        return len(_ALPHA_CACHE), len(_FIR_CACHE), int(sum(v.nbytes for v in _FIR_CACHE.values()))


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


def iso_fir(distance_m, temp_c=20.0, rh=50.0, pressure_kpa=101.325, sr=SR):
    """The impulse response (TAPS taps, linear phase, centred) of distance_m of Earth air: the filter iso_apply convolves
    with. A copy of the cached response, for a caller that wants to look at or edit the taps."""
    return _iso_fir_shared(distance_m, temp_c, rh, pressure_kpa, sr).copy()


def _iso_fir_shared(distance_m, temp_c=20.0, rh=50.0, pressure_kpa=101.325, sr=SR):
    """The cached response itself (read-only). iso_apply convolves with this one: no copy per tap."""
    key = ('iso9613', round(float(distance_m), 4)) + _state(temp_c, rh, pressure_kpa) + (int(sr), TAPS)

    def build():
        gain = 10.0 ** (-alpha_spectrum(TAPS - 1, sr, temp_c, rh, pressure_kpa) * float(distance_m) / 20.0)
        n = TAPS - 1
        ir = np.roll(np.fft.irfft(gain, n=n), n // 2)    # zero-phase response, centred
        return np.append(ir, 0.0) * signal.windows.blackman(TAPS)

    return cached_fir(key, build)


def group_delay(taps=TAPS):
    """Samples a centred, linear-phase FIR of `taps` taps delays the signal it is convolved with: (taps - 1) // 2.

    `iso_apply` and `medium.absorb` take the response's centre out (they read out[TAPS // 2 : ...]), so a path
    through this module has no delay of its own. A caller that convolves the taps causally (`lfilter`, or a plain
    `irfft` of their spectrum) gets this many samples of extra distance and must remove them itself: 512 samples
    here, 11.6 ms at 44.1 kHz, which is a metre and a half of path.
    """
    return (int(taps) - 1) // 2


def apply_fir(x, ir, centre=None):
    """`x` ((N,) or (N, C)) full-convolved with `ir` ((M,) or (M, C)) along axis 0 and read out centred, so a
    linear-phase response adds its magnitude and no delay.

    On the CPU this is `scipy.signal.fftconvolve` itself, so the numbers are the ones the engine always made; a GPU
    render takes `compute`'s kernel instead and differs in the last bits. `compute`'s own CPU transform (rfft with
    `workers`) was measured here at 11.2 ms against SciPy's 10.0 ms for the same 220 500-sample path on two cores:
    an extra transform of the response and its temporaries cost more than the two-way split saves, so the air keeps
    SciPy's kernel and only the GPU is a different arithmetic.
    """
    x = np.asarray(x, np.float32)
    n = len(x)
    if n == 0 or len(ir) == 0:
        return x
    h = np.asarray(ir)
    hh = h[:, None] if (x.ndim == 2 and h.ndim == 1) else h
    import compute                    # lazy: this module is imported by the environment code, which does not need it
    if compute.on_gpu():
        out = compute.fftconvolve(x, hh, mode='full')
    else:
        out = signal.fftconvolve(x, hh, mode='full', axes=0)
    g = (len(h) - 1) // 2 if centre is None else int(centre)
    return out[g:g + n].astype(np.float32)


def iso_apply(x, distance_m, temp_c=20.0, rh=50.0, pressure_kpa=101.325, sr=SR):
    """The ISO 9613-1 linear-phase filter for distance_m of Earth air: `x` convolved with `iso_fir` and read out
    centred, so the path adds absorption and no delay."""
    x = np.asarray(x, dtype=np.float32)
    if distance_m <= 0:
        return x
    return apply_fir(x, _iso_fir_shared(distance_m, temp_c, rh, pressure_kpa, sr), centre=TAPS // 2)
