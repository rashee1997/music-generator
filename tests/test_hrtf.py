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

"""Measured-HRTF binaural route (scripts/spatial_hrtf). Skipped when the head data is not downloaded (python -m spatial_hrtf.data)."""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from spatial_hrtf import binaural  # noqa: E402

SR = 44100


def _noise():
    x = np.random.default_rng(1).standard_normal(SR)
    return signal.sosfilt(signal.butter(4, [300, 6000], 'band', fs=SR, output='sos'), x)


def _cues(y):
    """(right minus left level in dB, ms the right ear lags the left)"""
    L, R = y[:, 0], y[:, 1]
    ild = 20 * np.log10(np.sqrt((R ** 2).mean()) / np.sqrt((L ** 2).mean()))
    return ild, (np.argmax(signal.correlate(R, L, 'full')) - (len(L) - 1)) / SR * 1000


@unittest.skipUnless(binaural.available(), 'head data not downloaded')
class TestHrtf(unittest.TestCase):
    def test_sides_are_mirrored_and_far_ear_is_late(self):
        x = _noise()
        ild_r, itd_r = _cues(binaural.spatialize(x, 60, 0, 1.0))       # source on the right: right ear louder and first
        ild_l, itd_l = _cues(binaural.spatialize(x, -60, 0, 1.0))
        self.assertGreater(ild_r, 8)
        self.assertLess(ild_l, -8)
        self.assertLess(itd_r, -0.3)
        self.assertGreater(itd_l, 0.3)

    def test_height_changes_the_colour(self):
        x = _noise()

        def tilt(y):
            f, p = signal.welch(y.mean(axis=1), SR, nperseg=2048)
            return 10 * np.log10(p[(f > 6000) & (f < 12000)].mean() / p[(f > 500) & (f < 1500)].mean())
        self.assertGreater(tilt(binaural.spatialize(x, 0, 60, 1.0)) - tilt(binaural.spatialize(x, 0, 0, 1.0)), 3)

    def test_trajectory_sweeps_left_to_right(self):
        y = binaural.spatialize(_noise(), 0, 0, 2.0, trajectory={'start_azimuth': -70, 'end_azimuth': 70})
        self.assertEqual(y.shape, (SR, 2))
        self.assertLess(_cues(y[:SR // 5])[0], -6)
        self.assertGreater(_cues(y[-SR // 5:])[0], 6)

    def test_mixer_route_and_fallback(self):
        import mixer
        x = _noise().astype(np.float32)
        spec = {'role': 'fx', 'gain_db': 0.0, 'inst': 'x', 'spatial': {'azimuth': 60.0, 'distance': 2.0, 'binaural': 'hrtf'}}
        y = mixer.process_stem('t', x, spec, sr=SR)
        self.assertGreater(_cues(y)[0], 6)                              # right ear louder: the measured route ran
        real = binaural.available
        binaural.available = lambda: False                             # data missing: still renders, through spatial.py
        try:
            spec = {'role': 'fx', 'gain_db': 0.0, 'inst': 'x', 'spatial': {'azimuth': 60.0, 'distance': 2.0, 'binaural': 'hrtf'}}
            y2 = mixer.process_stem('t', x, spec, sr=SR)
        finally:
            binaural.available = real
        self.assertEqual(y2.shape[1], 2)
        self.assertGreater(_cues(y2)[0], 3)

    def test_distance_lowers_level(self):
        x = _noise()
        near, far = (np.abs(binaural.spatialize(x, 30, 0, d)).max() for d in (1.0, 4.0))
        self.assertLess(far, near / 2)


if __name__ == '__main__':
    unittest.main()
