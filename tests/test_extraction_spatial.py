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
"""test_extraction_spatial.py - pan, width, delay trick, movement and RT60 measured on stems with known placement."""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
from extraction import config, spatial  # noqa: E402

SR = 22050
RNG = np.random.default_rng(11)
CFG = config.load()


def noise(sec):
    b, a = signal.butter(2, [200 / (SR / 2), 4000 / (SR / 2)], 'band')
    return signal.lfilter(b, a, RNG.standard_normal(int(sec * SR)))


def pan_law(x, p):                       # p in -1..1, same law the measurement inverts
    th = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(th), x * np.sin(th)])


class TestSpatial(unittest.TestCase):
    def test_pan_is_recovered_and_the_source_is_narrow(self):
        for p in (-0.8, -0.3, 0.0, 0.5):
            m = spatial.measure_source(pan_law(noise(6), p), SR, CFG)['baseline']
            self.assertAlmostEqual(m['azimuth_deg'], p * 90.0, delta=4.0, msg=f'pan {p}')
            self.assertLess(m['width_0_1'], 0.15)
        self.assertEqual(spatial.measure_source(pan_law(noise(6), 0.0), SR, CFG)['baseline']['technique'], 'mono_centre')
        self.assertEqual(spatial.measure_source(pan_law(noise(6), -0.6), SR, CFG)['baseline']['technique'], 'mono_panned')

    def test_haas_delay_and_decorrelated_double(self):
        x = noise(6)
        d = int(0.015 * SR)
        haas = np.stack([x, np.r_[np.zeros(d), x[:-d]]])
        b = spatial.measure_source(haas, SR, CFG)['baseline']
        self.assertEqual(b['technique'], 'haas_delay')
        self.assertAlmostEqual(abs(b['haas_ms']), 15.0, delta=1.0)
        dbl = np.stack([noise(6), noise(6)])
        self.assertEqual(spatial.measure_source(dbl, SR, CFG)['baseline']['technique'], 'decorrelated_double')
        self.assertGreater(spatial.measure_source(dbl, SR, CFG)['baseline']['width_0_1'], 0.7)

    def test_a_move_is_found_with_its_times(self):
        x = noise(10)
        pan = np.where(np.arange(len(x)) < 4 * SR, -0.7, np.where(np.arange(len(x)) < 7 * SR, 0.7, -0.7))
        th = (pan + 1) * np.pi / 4
        st = np.stack([x * np.cos(th), x * np.sin(th)])
        r = spatial.measure_source(st, SR, CFG)
        self.assertEqual(len(r['moves']), 1, r['moves'])
        self.assertAlmostEqual(r['moves'][0]['start_s'], 4.0, delta=0.6)
        self.assertAlmostEqual(r['moves'][0]['end_s'], 7.0, delta=0.6)

    def test_rt60_from_cutoffs(self):
        rt = 1.2
        parts = []
        for _ in range(4):
            burst = noise(1.0) * np.hanning(int(1.0 * SR)) ** 0.1
            t = np.arange(int(2.5 * SR)) / SR
            tail = noise(2.5) * np.exp(-6.9078 * t / rt) * 0.05           # amplitude decays 60 dB in rt seconds
            parts += [burst, tail]
        mix = np.concatenate(parts)
        t60, n = spatial.rt60(mix, SR, CFG)
        self.assertIsNotNone(t60)
        self.assertAlmostEqual(t60, rt, delta=0.35 * rt)

    def test_room_numbers(self):
        mono = np.stack([noise(4)] * 2)
        r = spatial.room(mono, SR, CFG)
        self.assertLess(r['low_end_side_pct'], 1.0)
        self.assertAlmostEqual(r['mono_sum_change_db'], 0.0, delta=0.1)


if __name__ == '__main__':
    unittest.main()
