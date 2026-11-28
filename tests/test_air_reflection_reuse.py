# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The air filter and the room's surface filter, on synthetic signals only.

Three properties the renderers depend on:

  * a cached spectrum, impulse response or surface filter is the same numbers as the one built from scratch;
  * the caches stay inside their byte budgets and are emptied by `clear_caches`;
  * a path through the air or a wall adds absorption and no delay of its own (the surface filter is linear phase:
    convolved causally it is 64 samples, 1.45 ms, of extra distance on every reflection).
"""
import sys
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import airabs
from spatial_hrtf import room

SR = 44100


class AirCache(unittest.TestCase):
    def setUp(self):
        airabs.clear_caches()

    def tearDown(self):
        airabs.clear_caches()

    def test_a_repeated_path_is_the_same_response(self):
        a = airabs.iso_fir(12.5, 20.0, 50.0, 101.325, SR)
        b = airabs.iso_fir(12.5, 20.0, 50.0, 101.325, SR)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(airabs_cache()[1], 1)               # the second call was a hit

    def test_a_copy_is_what_the_caller_gets(self):
        a = airabs.iso_fir(4.0)
        a[0] = 1e9                                          # a caller may edit its own response
        b = airabs.iso_fir(4.0)
        self.assertNotEqual(float(b[0]), 1e9)

    def test_another_air_state_is_another_response(self):
        dry = airabs.iso_fir(30.0, 20.0, 20.0, 101.325, SR)
        humid = airabs.iso_fir(30.0, 20.0, 80.0, 101.325, SR)
        self.assertGreater(float(np.max(np.abs(dry - humid))), 1e-4)

    def test_the_alpha_spectrum_is_the_standard_on_the_transform_grid(self):
        got = airabs.alpha_spectrum(1024, SR, 20.0, 50.0, 101.325)
        want = airabs.iso_alpha_db_per_m(np.fft.rfftfreq(1024, 1.0 / SR), 20.0, 50.0, 101.325)
        np.testing.assert_array_equal(got, want)
        self.assertIs(got, airabs.alpha_spectrum(1024, SR, 20.0, 50.0, 101.325))

    def test_the_fir_cache_never_holds_more_than_its_byte_budget(self):
        old = airabs._FIR_CACHE_BYTES
        airabs._FIR_CACHE_BYTES = 40000                      # about five 1025-tap float64 responses
        try:
            for d in range(100):                             # a hundred distinct paths
                airabs.iso_fir(1.0 + d, 20.0, 50.0, 101.325, SR)
                self.assertLessEqual(airabs_cache()[2], 40000)
            self.assertGreater(len(airabs_cache_hits()), 0)
        finally:
            airabs._FIR_CACHE_BYTES = old
            airabs.clear_caches()

    def test_applying_a_distance_keeps_the_samples_where_they_were(self):
        """The response is applied centred, exactly as it always was: it absorbs and does not delay."""
        x = np.zeros(SR)
        x[1000] = 1.0
        for distance in (2.0, 50.0, 200.0):
            y = airabs.apply(x, distance, 20.0, 50.0, sr=SR)
            self.assertEqual(int(np.argmax(np.abs(y))), 1000)
            self.assertLess(float(np.abs(y).max()), 1.0)     # 50 m and 200 m are quieter than the impulse

    def test_the_distance_is_reported_as_a_group_delay(self):
        self.assertEqual(airabs.group_delay(), airabs.TAPS // 2)

    def test_the_cpu_convolution_is_the_old_scipy_arithmetic(self):
        """`compute` supplies the worker count; the numbers must still be the ones scipy.signal.fftconvolve made."""
        from scipy import signal
        x = (0.3 * np.random.default_rng(0).standard_normal(20000)).astype(np.float32)
        ir = airabs.iso_fir(25.0, 20.0, 50.0, 101.325, SR)
        g = airabs.TAPS // 2
        want = signal.fftconvolve(x, ir, mode='full')[g:g + len(x)].astype(np.float32)
        np.testing.assert_array_equal(airabs.iso_apply(x, 25.0, 20.0, 50.0, sr=SR), want)
        stereo = np.stack([x, 0.5 * x], axis=1)
        want2 = signal.fftconvolve(stereo, ir[:, None], mode='full', axes=0)[g:g + len(x)].astype(np.float32)
        np.testing.assert_array_equal(airabs.iso_apply(stereo, 25.0, 20.0, 50.0, sr=SR), want2)


class SurfaceFilter(unittest.TestCase):
    def setUp(self):
        self.coeffs = room.coefficients(room.material_table('room_materials'), 'plaster')
        room._FIR_CACHE.clear()

    def test_a_repeated_surface_is_the_same_filter(self):
        a = room.absorption_fir(self.coeffs, sr=SR)
        b = room.absorption_fir(self.coeffs, sr=SR)
        self.assertIs(a, b)
        self.assertFalse(a.flags.writeable)                  # read-only: a room's filter is shared by its taps

    def test_the_linear_phase_filter_is_centred(self):
        fir = room.absorption_fir(self.coeffs, sr=SR)
        self.assertEqual(int(np.argmax(np.abs(fir))), room.group_delay(len(fir)))
        self.assertEqual(room.group_delay(len(fir)), 64)     # 1.45 ms at 44.1 kHz

    def test_applying_a_wall_absorbs_and_does_not_delay(self):
        x = np.zeros(8192)
        x[2000] = 1.0
        y = room.apply_absorption(x, self.coeffs, sr=SR)
        self.assertEqual(int(np.argmax(np.abs(y))), 2000)
        self.assertGreater(float(np.abs(y[2000])), 0.5)

    def test_the_material_library_is_read_once_per_signature(self):
        import presets
        first = room.material_table('room_materials')
        sig = presets.signature('materials')
        self.assertIn(sig, room._TABLE_CACHE)
        self.assertIs(first, room.material_table('room_materials'))
        with self.assertRaises(KeyError):
            room.material_table('no_such_library')


def airabs_cache():
    return airabs.cache_info()


def airabs_cache_hits():
    return airabs._FIR_CACHE


if __name__ == '__main__':
    unittest.main()
