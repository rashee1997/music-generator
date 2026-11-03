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

import os
import sys
import unittest
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)

import environment


class TestEnvironmentEngine(unittest.TestCase):
    def setUp(self):
        self.sr = 44100
        self.dur = 2.0
        self.rng = np.random.default_rng(42)

    def test_noise_bed_primitive(self):
        pink = environment.synth_noise_bed(self.dur, self.sr, self.rng, color='pink')
        brown = environment.synth_noise_bed(self.dur, self.sr, self.rng, color='brown')
        self.assertEqual(len(pink), int(self.dur * self.sr))
        self.assertTrue(np.isfinite(pink).all())
        self.assertTrue(np.max(np.abs(pink)) > 0.01)
        self.assertTrue(np.isfinite(brown).all())

    def test_resonant_gust_primitive(self):
        gust = environment.synth_resonant_gust(self.dur, self.sr, self.rng, center_hz=450.0, q=6.0)
        self.assertEqual(len(gust), int(self.dur * self.sr))
        self.assertTrue(np.isfinite(gust).all())
        self.assertTrue(np.max(np.abs(gust)) > 0.01)

    def test_formant_babble_primitive(self):
        babble = environment.synth_formant_babble(self.dur, self.sr, self.rng, voices=4)
        self.assertEqual(len(babble), int(self.dur * self.sr))
        self.assertTrue(np.isfinite(babble).all())
        self.assertTrue(np.max(np.abs(babble)) > 0.01)

    def test_doppler_sweep_primitive(self):
        sweep = environment.synth_doppler_sweep(self.dur, self.sr, self.rng, f_start=400.0, f_end=150.0)
        self.assertEqual(len(sweep), int(self.dur * self.sr))
        self.assertTrue(np.isfinite(sweep).all())
        self.assertTrue(np.max(np.abs(sweep)) > 0.01)

    def test_impulse_cluster_primitive(self):
        cluster = environment.synth_impulse_cluster(self.dur, self.sr, self.rng, event_rate=8.0)
        self.assertEqual(len(cluster), int(self.dur * self.sr))
        self.assertTrue(np.isfinite(cluster).all())

    def test_water_surf_primitive(self):
        surf = environment.synth_water_flow(self.dur, self.sr, self.rng, swell_period_s=1.0)
        self.assertEqual(len(surf), int(self.dur * self.sr))
        self.assertTrue(np.isfinite(surf).all())
        self.assertTrue(np.max(np.abs(surf)) > 0.01)

    def test_render_environment_preset_dictionary(self):
        custom_preset = {
            'name': 'test_bazaar_env',
            'acoustic_space': 'bazaar_alley',
            'layers': [
                {'primitive': 'noise_bed', 'color': 'pink', 'gain_db': -18.0, 'spatial': {'azimuth': 0, 'distance': 8.0}},
                {'primitive': 'formant_babble', 'voices': 3, 'gain_db': -16.0, 'spatial': {'azimuth': -40, 'distance': 3.0}},
                {'primitive': 'impulse_cluster', 'event_rate': 4.0, 'gain_db': -20.0, 'spatial': {'azimuth': 45, 'distance': 2.5}}
            ],
            'blending': {
                'overall_gain_db': -20.0,
                'high_pass_hz': 90.0,
                'vocal_pocket_notch_hz': 2100.0,
                'vocal_pocket_notch_db': -3.5
            }
        }
        audio = environment.render_environment_preset(custom_preset, duration_s=1.5, sr=self.sr)
        self.assertEqual(audio.shape, (int(1.5 * self.sr), 2))
        self.assertTrue(np.isfinite(audio).all())
        self.assertTrue(np.max(np.abs(audio)) > 1e-4)

    @staticmethod
    def _centroid(x, sr):
        s = np.abs(np.fft.rfft(x)) ** 2
        return float((np.fft.rfftfreq(len(x), 1.0 / sr) * s).sum() / s.sum())

    LOW_VOICE = dict(bouts_per_min=5.0, first_s=1.0, bout_s=(3.0, 4.0), f0_hz=95.0, f0_contour=(1.1, 0.8),
                     formants_hz=(480.0, 1050.0, 2100.0), formant_weights=(1.0, 0.7, 0.3), breath=0.35, chop_hz=4.0, chop_depth=0.35)

    def test_voice_bouts_is_low_sparse_and_deterministic(self):
        a = environment.synth_voice_bouts(12.0, self.sr, np.random.default_rng(3), **self.LOW_VOICE)
        b = environment.synth_voice_bouts(12.0, self.sr, np.random.default_rng(3), **self.LOW_VOICE)
        c = environment.synth_voice_bouts(12.0, self.sr, np.random.default_rng(4), **self.LOW_VOICE)
        self.assertEqual(len(a), 12 * self.sr)
        self.assertTrue(np.isfinite(a).all())
        self.assertAlmostEqual(float(np.abs(a).max()), 0.5, places=3)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))
        self.assertLess(self._centroid(a, self.sr), 900.0)                      # the preset's low formants decide the colour
        self.assertLess(float(np.abs(a[:self.sr // 2]).max()), 1e-6)            # silent before first_s

    def test_voice_bouts_pitch_follows_the_preset(self):
        lo = environment.synth_voice_bouts(6.0, self.sr, np.random.default_rng(1), bouts_per_min=10.0, first_s=0.5, f0_hz=100.0)
        hi = environment.synth_voice_bouts(6.0, self.sr, np.random.default_rng(1), bouts_per_min=10.0, first_s=0.5, f0_hz=400.0)
        self.assertGreater(self._centroid(hi, self.sr), 1.5 * self._centroid(lo, self.sr))

    def test_syllable_bouts_are_high_and_in_bouts(self):
        a = environment.synth_syllable_bouts(10.0, self.sr, np.random.default_rng(5), bouts_per_min=12.0, first_s=0.5)
        self.assertEqual(len(a), 10 * self.sr)
        self.assertTrue(np.isfinite(a).all())
        self.assertAlmostEqual(float(np.abs(a).max()), 0.5, places=3)
        self.assertGreater(self._centroid(a, self.sr), 1500.0)
        quiet = (np.abs(a.reshape(-1, self.sr // 10)).max(axis=1) < 1e-4).mean()
        self.assertGreater(quiet, 0.3)                                          # gaps between bouts, not a continuous texture

    def test_generic_primitives_take_every_key_from_the_layer(self):
        cfg = {'layers': [dict(self.LOW_VOICE, primitive='voice_bouts', bout_s=[1.0, 1.5], first_s=0.2, gain_db=-10),
                          {'primitive': 'syllable_bouts', 'first_s': 0.2, 'f_start_hz': 5000, 'f_end_hz': 4000, 'gain_db': -10}]}
        audio = environment.render_environment_preset(cfg, duration_s=3.0, sr=self.sr)
        self.assertEqual(audio.shape, (3 * self.sr, 2))
        self.assertGreater(float(np.abs(audio).max()), 0.01)
        only_hi = environment.render_environment_preset({'layers': [cfg['layers'][1]]}, duration_s=3.0, sr=self.sr)
        self.assertGreater(self._centroid(only_hi.mean(axis=1), self.sr), 3500.0)   # f_start_hz / f_end_hz from the preset arrived


if __name__ == '__main__':
    unittest.main()
