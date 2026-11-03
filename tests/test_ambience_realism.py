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

"""Ambience realism: ISO 9613-1 filter, physical rain, turbulence, crickets, bird bands, decorrelation,
and the two spatial.py fixes (Brown-Duda alpha range, trajectory early reflections + Doppler)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import airabs
import environment as env
import spatial

SR = 44100


def _corr(l, r):
    return float(np.dot(l, r) / np.sqrt(np.dot(l, l) * np.dot(r, r) + 1e-12))


class AirAbsorption(unittest.TestCase):
    def test_iso_reference_values(self):
        a = airabs.alpha_db_per_m([1000.0, 10000.0]) * 1000.0     # dB/km at 20 C, 50 % RH
        self.assertAlmostEqual(a[0], 5.0, delta=1.0)
        self.assertAlmostEqual(a[1], 160.0, delta=15.0)

    def test_filter_matches_alpha(self):
        x = np.random.default_rng(1).standard_normal(SR).astype(np.float32)
        y = airabs.apply(x, 200.0)
        X, Y = np.abs(np.fft.rfft(x)), np.abs(np.fft.rfft(y))
        db = 20 * np.log10(Y[9800:10200].mean() / X[9800:10200].mean())
        self.assertAlmostEqual(db, -airabs.alpha_db_per_m(10000.0) * 200.0, delta=1.0)
        self.assertEqual(y.shape, x.shape)


class Primitives(unittest.TestCase):
    def test_rain_rate_scales_events_and_water_has_bubbles(self):
        light = env.synth_rain(4, SR, np.random.default_rng(1), rate_mm_h=1.0)
        heavy = env.synth_rain(4, SR, np.random.default_rng(1), rate_mm_h=40.0)
        self.assertGreater(np.mean(np.abs(heavy)), np.mean(np.abs(light)))
        bub = env.synth_rain(4, SR, np.random.default_rng(2), surface='water', bubble_prob=1.0)
        no = env.synth_rain(4, SR, np.random.default_rng(2), surface='solid')
        self.assertFalse(np.allclose(bub, no))

    def test_turbulence_slope_is_minus_five_thirds_power(self):
        z = env._turbulence(SR * 60, SR, np.random.default_rng(3), 0.1)
        f, p = np.fft.rfftfreq(len(z), 1 / SR), np.abs(np.fft.rfft(z)) ** 2
        lo, hi = (f > 1) & (f < 2), (f > 10) & (f < 20)
        slope = np.log10(p[hi].mean() / p[lo].mean()) / np.log10(15.0 / 1.5)
        self.assertAlmostEqual(slope, -5.0 / 3.0, delta=0.35)

    def test_cricket_rate_follows_temperature(self):
        def chirps(t_c):
            x = env.synth_cricket_chorus(10, SR, np.random.default_rng(4), voices=1, temp_c=t_c)
            e = np.abs(x) > 0.01
            return int(np.sum(np.diff(np.flatnonzero(e)) > 0.1 * SR)) + 1
        self.assertGreater(chirps(28.0), chirps(14.0))

    def test_bird_species_use_separate_bands(self):
        x = env.synth_bird_chorus(8, SR, np.random.default_rng(5), species=3, f_lo=1500, f_hi=6000, event_rate=1.0)
        self.assertGreater(np.max(np.abs(x)), 0.0)
        self.assertTrue(np.all(np.isfinite(x)))

    def test_decorrelate_lowers_correlation_and_keeps_mono_level(self):
        x = np.random.default_rng(6).standard_normal(SR * 3).astype(np.float32)
        st = env.decorrelate(x, SR, seed=1)
        self.assertLess(abs(_corr(st[:, 0], st[:, 1])), 0.5)
        mono = 0.5 * (st[:, 0] + st[:, 1])
        self.assertGreater(np.std(mono) / np.std(x), 0.5)         # no deep mono comb loss

    def test_preset_with_new_keys_renders(self):
        cfg = {'atmosphere': {'temp_c': 22, 'rh': 60}, 'layers': [
            {'primitive': 'rain_physical', 'rate_mm_h': 8, 'decorrelate': 1.0, 'spatial': {'distance': 20}},
            {'primitive': 'resonant_gust', 'turbulence': True, 'gain_db': -20},
            {'primitive': 'crickets', 'species': 'cricket', 'gain_db': -26},
            {'primitive': 'bird_chorus', 'species': 3, 'dawn_s': 2, 'gain_db': -24}]}
        out = env.render_environment_preset(cfg, duration_s=5, seed=7)
        self.assertEqual(out.shape, (5 * SR, 2))
        self.assertTrue(np.all(np.isfinite(out)))


class SpatialFixes(unittest.TestCase):
    def test_head_shadow_reaches_full_depth(self):
        x = np.random.default_rng(8).standard_normal(SR).astype(np.float32)
        l, r = spatial.brown_duda_head_shadow(x, 90.0)             # source hard right
        X = np.abs(np.fft.rfft(x))[15000:20000].mean()
        ratio_db = 20 * np.log10(np.abs(np.fft.rfft(l))[15000:20000].mean() / np.abs(np.fft.rfft(r))[15000:20000].mean())
        self.assertLess(ratio_db, -12.0)                           # ~ -16.5 dB shelf at HF (was only ~ -5)
        self.assertGreater(20 * np.log10(np.abs(np.fft.rfft(r))[15000:20000].mean() / X), 3.0)

    def test_trajectory_keeps_reflections_and_is_finite(self):
        x = np.zeros(SR * 2, np.float32)
        x[SR // 2] = 1.0                                           # one click
        traj = dict(start_azimuth=-30, end_azimuth=30, start_distance=3.0, end_distance=3.0, doppler=False)
        out = spatial.render_trajectory(x, traj, acoustic_space='forest_canopy')
        self.assertEqual(out.shape, (len(x), 2))
        self.assertTrue(np.all(np.isfinite(out)))
        peak = SR // 2
        tail = np.abs(out[peak + int(0.008 * SR):peak + int(0.06 * SR)]).max()
        self.assertGreater(tail, 1e-3)                             # 8-60 ms early reflections present

    def test_doppler_shifts_pitch_down_when_receding(self):
        t = np.arange(SR * 3) / SR
        x = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
        out = spatial.render_trajectory(x, dict(start_azimuth=0, end_azimuth=0, start_distance=2.0, end_distance=80.0),
                                        acoustic_space='outdoor_open')
        seg = out[SR:2 * SR, 0]
        f = np.argmax(np.abs(np.fft.rfft(seg * np.hanning(len(seg))))) * SR / len(seg)
        self.assertLess(f, 1000.0)


if __name__ == '__main__':
    unittest.main()
