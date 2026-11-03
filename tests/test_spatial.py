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

import spatial


class TestSpatialAudio(unittest.TestCase):
    def setUp(self):
        self.sr = 44100
        self.duration = 1.0
        t = np.arange(int(self.sr * self.duration)) / self.sr
        # 1-second 440 Hz test tone
        self.test_tone = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

    def test_woodworth_itd(self):
        # Center should have 0 delay
        itd_0, samp_0 = spatial.woodworth_itd(0.0, sr=self.sr)
        self.assertEqual(itd_0, 0.0)
        self.assertEqual(samp_0, 0.0)

        # Right 90 deg: ~0.65 ms delay
        itd_90, samp_90 = spatial.woodworth_itd(90.0, sr=self.sr)
        self.assertTrue(0.0005 < itd_90 < 0.0008, f"Unexpected ITD at 90 deg: {itd_90}")
        self.assertTrue(samp_90 > 20, f"Expected > 20 samples delay, got {samp_90}")

        # Left 90 deg: negative ITD of same magnitude
        itd_neg90, samp_neg90 = spatial.woodworth_itd(-90.0, sr=self.sr)
        self.assertAlmostEqual(itd_90, -itd_neg90, places=6)
        self.assertAlmostEqual(samp_90, -samp_neg90, places=4)

    def test_kuhn_itd(self):
        # Kuhn (1977) frequency-dependent ITD: low frequency ITD should be ~16% larger than high frequency ITD
        tau_0, tau_inf, s_0, s_inf = spatial.kuhn_itd(90.0, sr=self.sr)
        self.assertTrue(tau_0 > tau_inf, f"Low-frequency ITD ({tau_0}s) must exceed high-frequency ITD ({tau_inf}s)")
        ratio = tau_0 / tau_inf
        self.assertTrue(1.10 < ratio < 1.25, f"Expected Kuhn ratio ~1.16, got {ratio:.3f}")

    def test_brown_duda_head_shadow(self):
        # Brown & Duda analytical head shadow filter operates on frequencies > 1.5 kHz (Duplex theory)
        # Test with 4000 Hz tone: Source at +90 deg (pure right) gives right ear boost and left ear shadow
        t = np.arange(int(self.sr * self.duration)) / self.sr
        tone_4k = (0.5 * np.sin(2 * np.pi * 4000.0 * t)).astype(np.float32)
        l_out, r_out = spatial.brown_duda_head_shadow(tone_4k, azimuth_deg=90.0, sr=self.sr)
        self.assertEqual(len(l_out), len(tone_4k))
        self.assertEqual(len(r_out), len(tone_4k))
        self.assertTrue(np.isfinite(l_out).all() and np.isfinite(r_out).all())
        
        # At 4 kHz, right ear should be significantly louder than shadowed left ear (ratio > 2.0, ILD > 6 dB)
        rms_r = np.sqrt(np.mean(r_out ** 2))
        rms_l = np.sqrt(np.mean(l_out ** 2))
        self.assertTrue(rms_r > rms_l * 2.0, f"Right ear ({rms_r}) must be > 2x louder than left ear ({rms_l}) at 4 kHz, azimuth +90")

    def test_near_field_divergence(self):
        # Proximal sound (< 1m, e.g. 0.2m at 90 deg) creates dramatic low-frequency ILD
        l_prox, r_prox = spatial.apply_near_field_divergence(self.test_tone, self.test_tone,
                                                            azimuth_deg=90.0, distance_m=0.2, sr=self.sr)
        rms_r = np.sqrt(np.mean(r_prox ** 2))
        rms_l = np.sqrt(np.mean(l_prox ** 2))
        ild_db = 20.0 * np.log10(rms_r / max(1e-6, rms_l))
        self.assertTrue(ild_db > 4.0, f"Near-field source at 0.2m must have > 4 dB ILD. Got {ild_db:.2f} dB")

    def test_iso9613_air_absorption(self):
        # Air absorption over 50 meters should significantly attenuate high frequencies compared to 1 meter
        noise = np.random.randn(self.sr).astype(np.float32)
        near = spatial.iso9613_air_absorption(noise, distance_m=1.0, sr=self.sr)
        far = spatial.iso9613_air_absorption(noise, distance_m=50.0, sr=self.sr)
        # Check high-frequency energy ratio (> 4 kHz)
        import scipy.signal as signal
        sos_hp = signal.butter(2, 4000.0, btype='highpass', fs=self.sr, output='sos')
        hp_near = signal.sosfilt(sos_hp, near)
        hp_far = signal.sosfilt(sos_hp, far)
        rms_near = np.sqrt(np.mean(hp_near ** 2))
        rms_far = np.sqrt(np.mean(hp_far ** 2))
        self.assertTrue(rms_near > 2.0 * rms_far, f"Air absorption must roll off high frequencies over 50m. Got {rms_near} vs {rms_far}")

    def test_ambisonic_encoding_and_binaural_decoding(self):
        # Encode mono tone to 1st-Order Ambisonics (B-format)
        bformat = spatial.encode_ambisonic_bformat(self.test_tone, azimuth_deg=45.0, elevation_deg=10.0)
        self.assertEqual(bformat.shape, (len(self.test_tone), 4))
        self.assertTrue(np.isfinite(bformat).all())
        
        # Decode B-format to binaural stereo
        binaural = spatial.decode_ambisonic_to_binaural(bformat, sr=self.sr)
        self.assertEqual(binaural.shape, (len(self.test_tone), 2))
        self.assertTrue(np.isfinite(binaural).all())
        self.assertTrue(np.max(np.abs(binaural)) > 0.01)

    def test_distance_attenuation(self):
        # one declared reference distance (1.5 m, the mixer's ref_distance): unity inside it, 1/r beyond it
        d1 = spatial.distance_attenuation(self.test_tone, distance_m=1.0, sr=self.sr)
        d4 = spatial.distance_attenuation(self.test_tone, distance_m=4.0, sr=self.sr)
        d6 = spatial.distance_attenuation(self.test_tone, distance_m=6.0, sr=self.sr)
        rms1 = np.sqrt(np.mean(d1 ** 2))
        rms4 = np.sqrt(np.mean(d4 ** 2))
        rms6 = np.sqrt(np.mean(d6 ** 2))
        self.assertAlmostEqual(rms4 / rms1, 1.5 / 4.0, delta=0.02)
        self.assertAlmostEqual(rms6 / rms1, 1.5 / 6.0, delta=0.02)
        self.assertTrue(rms1 > 3.0 * rms6, f"Distance 6m should be much quieter than 1m. Got rms1={rms1}, rms6={rms6}")

    def test_spatialize_stem_externalization(self):
        # Spatialized with natural externalization (anechoic vs externalized)
        anechoic = spatial.spatialize_stem(self.test_tone, azimuth_deg=45.0, distance_m=2.0, 
                                           externalize=False, sr=self.sr)
        external = spatial.spatialize_stem(self.test_tone, azimuth_deg=45.0, distance_m=2.0, 
                                           externalize=True, sr=self.sr)
        
        self.assertEqual(external.shape, (len(self.test_tone), 2))
        self.assertTrue(np.isfinite(external).all())
        
        # Externalized sound should have early reflection energy present
        diff_energy = np.sum((external - anechoic) ** 2)
        self.assertTrue(diff_energy > 1e-4, "Externalization should contribute reflection energy")

    def test_drr_decreases_with_distance(self):
        # Close source (1m) should have higher Direct-to-Reverberant Ratio than far source (6m)
        close = spatial.spatialize_stem(self.test_tone, azimuth_deg=0.0, distance_m=1.0, externalize=True, sr=self.sr)
        far = spatial.spatialize_stem(self.test_tone, azimuth_deg=0.0, distance_m=6.0, externalize=True, sr=self.sr)
        
        close_rms = np.sqrt(np.mean(close ** 2))
        far_rms = np.sqrt(np.mean(far ** 2))
        self.assertTrue(close_rms > far_rms, f"Close sound must have higher energy than far sound. Got {close_rms} vs {far_rms}")

    def test_far_ear_is_delayed_for_either_side(self):
        """A source on the left must reach the left ear first, as one on the right reaches the right ear first."""
        from scipy.signal import correlate
        rng = np.random.default_rng(1)
        noise = (0.2 * rng.standard_normal(self.sr)).astype(np.float32)

        def lead_ms(az):
            y = spatial.spatialize_stem(noise, azimuth_deg=az, distance_m=2.0, externalize=False, sr=self.sr)
            cc = correlate(y[:, 0], y[:, 1], 'full', method='fft')
            mid = len(cc) // 2
            return (np.argmax(cc[mid - 40:mid + 41]) - 40) / self.sr * 1000.0   # > 0: left ear is later
        self.assertGreater(lead_ms(60.0), 0.2)
        self.assertLess(lead_ms(-60.0), -0.2)

    def test_mixer_trajectory_moves_the_source(self):
        import mixer
        tone = (0.5 * np.sin(2 * np.pi * 4000.0 * np.arange(self.sr * 2) / self.sr)).astype(np.float32)
        sp = {'trajectory': {'start_azimuth': -70.0, 'end_azimuth': 70.0, 'start_distance': 3.0, 'end_distance': 3.0, 'doppler': False},
              'space': 'forest_canopy'}
        y = mixer.process_stem('t', tone, {'role': 'fx', 'gain_db': 0.0, 'spatial': sp, 'inst': 'x'}, sr=self.sr)
        q = len(y) // 4
        left_start = np.sqrt(np.mean(y[:q, 0] ** 2)) / np.sqrt(np.mean(y[:q, 1] ** 2))
        left_end = np.sqrt(np.mean(y[-q:, 0] ** 2)) / np.sqrt(np.mean(y[-q:, 1] ** 2))
        self.assertGreater(left_start, 1.5)
        self.assertLess(left_end, 0.7)

    def test_trajectory_rendering(self):
        traj = {
            'start_azimuth': -60.0,
            'end_azimuth': 60.0,
            'start_distance': 4.0,
            'end_distance': 1.5,
            'start_elevation': 0.0,
            'end_elevation': 0.0,
        }
        # head shadow is small at 440 Hz and early reflections now exist, so pan with a 4 kHz tone
        tone = (0.5 * np.sin(2 * np.pi * 4000.0 * np.arange(len(self.test_tone)) / self.sr)).astype(np.float32)
        rendered = spatial.render_trajectory(tone, traj, sr=self.sr)
        self.assertEqual(rendered.shape, (len(self.test_tone), 2))
        self.assertTrue(np.isfinite(rendered).all())
        # Check that energy pans from left ear to right ear
        first_quarter = rendered[:int(self.sr * 0.25)]
        last_quarter = rendered[-int(self.sr * 0.25):]
        self.assertTrue(np.mean(first_quarter[:, 0] ** 2) > np.mean(first_quarter[:, 1] ** 2), "Start should be left-heavy")
        self.assertTrue(np.mean(last_quarter[:, 1] ** 2) > np.mean(last_quarter[:, 0] ** 2), "End should be right-heavy")


if __name__ == '__main__':
    unittest.main()
