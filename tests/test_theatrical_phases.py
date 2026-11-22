"""Tests for the later theatrical phases: distance, register, onset variety, multichannel.

Run: .venv/bin/python -m unittest tests.test_theatrical_phases
"""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import dsp
import humanize
import mix_schema
import mixer
import spatial
import spatial_engine.master as master


SR = 22050


def tone(freqs, seconds=1.0, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    x = sum(np.sin(2 * np.pi * f * t) / (i + 1) for i, f in enumerate(freqs))
    return (x / max(1e-9, np.abs(x).max()) * 0.3).astype(np.float32)


def band_db(x, lo, hi, sr=SR):
    sos = signal.butter(4, [lo, hi], btype='band', fs=sr, output='sos')
    y = signal.sosfilt(sos, x, axis=0)
    return float(10 * np.log10(np.mean(y.astype(np.float64) ** 2) + 1e-18))


class DistanceTests(unittest.TestCase):
    def test_proximity_boosts_low_more_than_high_and_stops_at_the_reference(self):
        x = tone([80, 1200])
        close = spatial.proximity_gain(x, 0.4, ref_m=1.5, max_db=3.0, hz=200, sr=SR)
        far = spatial.proximity_gain(x, 2.0, ref_m=1.5, max_db=3.0, hz=200, sr=SR)
        self.assertGreater(band_db(close, 50, 150) - band_db(x, 50, 150), 1.0)
        self.assertLess(abs(band_db(close, 900, 1600) - band_db(x, 900, 1600)), 0.6)
        self.assertLess(abs(band_db(far, 50, 150) - band_db(x, 50, 150)), 0.01)

    def test_proximity_is_off_at_zero_and_rejects_negative(self):
        x = tone([80])
        np.testing.assert_allclose(spatial.proximity_gain(x, 0.4, max_db=0.0), x)
        with self.assertRaises(ValueError):
            spatial.proximity_gain(x, 0.4, max_db=-1.0)

    def test_the_mixer_reads_the_space_distance_block(self):
        owned = mixer._space_owned
        mixer._space_owned = lambda space: True
        try:
            cfg = mixer._spatial_cfg({'spatial': {}}, {'distance': {'proximity_db': 4.0, 'proximity_hz': 180,
                                                                   'er_distance_exponent': 1.4}})
        finally:
            mixer._space_owned = owned
        self.assertEqual(cfg['proximity_db'], 4.0)
        self.assertEqual(cfg['proximity_hz'], 180)
        self.assertEqual(cfg['er_distance_exponent'], 1.4)

    def test_early_reflection_exponent_changes_the_early_level_only(self):
        space = {'path_physics': True, 'ref_m': 1.5, 'ground_delay_ms': 4.0, 'ground_gain': 0.5,
                 'ground_cutoff_hz': 4000, 'lateral_gain': 0.0, 'ceiling_gain': 0.0, 'rear_gain': 0.0}
        x = tone([300], seconds=0.5)
        near_1, far_1 = spatial.synthesize_early_reflections(x, 0, 0.8, space, sr=SR)
        near_2, far_2 = spatial.synthesize_early_reflections(x, 0, 6.0,
                                                             dict(space, er_distance_exponent=1.6), sr=SR)
        near_3, far_3 = spatial.synthesize_early_reflections(x, 0, 6.0, space, sr=SR)
        self.assertLess(np.sqrt(np.mean(far_2 ** 2)), np.sqrt(np.mean(far_3 ** 2)))
        self.assertGreater(np.sqrt(np.mean(near_2 ** 2)), 0.0)
        self.assertGreater(np.sqrt(np.mean(near_1 ** 2)), 0.0)


class RegisterTests(unittest.TestCase):
    def test_a_transposed_high_note_loses_more_top_than_it_loses_body(self):
        x = tone([220, 660, 2640, 5280])
        out = dsp.register_tone(x, SR, semitones=12, pivot_hz=1200, db_per_oct=2.0, max_db=6.0)
        low = band_db(out, 180, 300) - band_db(x, 180, 300)
        high = band_db(out, 2000, 6000) - band_db(x, 2000, 6000)
        self.assertLess(high, low - 1.0)
        self.assertLess(abs(dsp.rms_db(out) - dsp.rms_db(x)), 0.1)

    def test_zero_semitones_is_a_no_op_and_bad_values_raise(self):
        x = tone([440])
        np.testing.assert_allclose(dsp.register_tone(x, SR, semitones=0.0)[:, 0], x)
        with self.assertRaises(ValueError):
            dsp.register_tone(x, SR, semitones=12, db_per_oct=-1.0)

    def test_the_renderer_validates_the_register_block(self):
        import render_natural as rn
        self.assertIsNone(rn._register_block({'notes': []}))
        with self.assertRaises(ValueError):
            rn._register_block({'name': 'v', 'register': {'split': 72}})
        with self.assertRaises(ValueError):
            rn._register_block({'name': 'v', 'register': {'split_pitch': 200}})
        self.assertEqual(rn._register_block({'name': 'v', 'register': {'split_pitch': 72}})['split_pitch'], 72)
        blk, lo, hi = rn._register_split({'name': 'v', 'instrument': 'violin', 'role': 'melody',
                                         'register': {'split_pitch': 72},
                                         'notes': [{'t': 0, 'p': 60}, {'t': 1, 'p': 84}]})
        self.assertEqual((len(lo), len(hi)), (1, 1))
        self.assertIsNone(rn._register_split({'name': 'v', 'role': 'drum', 'instrument': 'timpani',
                                              'register': {'split_pitch': 72},
                                              'notes': [{'t': 0, 'p': 84}]}))


class OnsetVarietyTests(unittest.TestCase):
    def _hits(self):
        t = np.arange(int(2.0 * SR)) / SR
        x = np.zeros_like(t, dtype=np.float32)
        for k in (0.2, 0.8, 1.4):
            x += 0.4 * np.exp(-40 * (t - k)) * (t >= k) * np.sin(2 * np.pi * 1800 * (t - k))
        return x.astype(np.float32)

    def test_repeated_onsets_are_no_longer_identical_and_the_result_is_deterministic(self):
        x = self._hits()
        a = dsp.transient_variety(x, SR, times=[0.2, 0.8, 1.4], gain_db=2.0, tilt_db=3.0, width_ms=20, seed=4)
        b = dsp.transient_variety(x, SR, times=[0.2, 0.8, 1.4], gain_db=2.0, tilt_db=3.0, width_ms=20, seed=4)
        np.testing.assert_allclose(a, b)
        i = int(0.2 * SR)
        j = int(0.8 * SR)
        w = int(0.015 * SR)
        self.assertGreater(np.max(np.abs(a[i:i + w] - x[i:i + w])), 1e-4)
        self.assertGreater(np.max(np.abs(a[i:i + w] - x[i:i + w] - (a[j:j + w] - x[j:j + w]))), 1e-5)

    def test_zero_is_a_no_op_and_an_environment_is_rejected(self):
        x = self._hits()
        np.testing.assert_allclose(dsp.transient_variety(x, SR, times=[0.2], gain_db=0.0, tilt_db=0.0)[:, 0], x)
        import render_natural as rn
        tm = humanize.TempoMap(120, total_beats=8)
        with self.assertRaises(ValueError):
            rn._apply_variety({'name': 'rain', 'instrument': 'env:rain',
                               'transient_variety': {'gain_db': 1.0}, 'notes': [{'t': 0, 'p': 60}]}, x, tm, 1)


class MultichannelTheatricalTests(unittest.TestCase):
    def test_low_mids_lean_on_the_main_channels_and_the_lfe_is_not_touched(self):
        n = int(2.0 * SR)
        t = np.arange(n) / SR
        main = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
        lfe = (0.3 * np.sin(2 * np.pi * 60 * t)).astype(np.float32)
        y = np.stack([main, main, lfe], axis=1)
        cfg = mix_schema.section(mix_schema.with_defaults(
            {'theatrical': {'enabled': True, 'low_mid': {'enabled': True, 'range_db': 2.0, 'ratio': 2.0,
                                                         'max_dip_db': 2.0}, 'air': {'enabled': False}}}), 'theatrical')
        out = mixer.theatrical_multichannel(y, SR, cfg, skip={2})
        np.testing.assert_allclose(out[:, 2], y[:, 2])
        self.assertLess(float(np.sqrt(np.mean(out[:, 0].astype(np.float64) ** 2))),
                        float(np.sqrt(np.mean(y[:, 0].astype(np.float64) ** 2))))


class CompareTests(unittest.TestCase):
    def test_the_calibration_table_names_every_render_and_dimension(self):
        import realism_report as rr
        a = rr.analyse(tone([220, 660], 2.0), SR)
        b = rr.analyse(tone([220, 2640], 2.0), SR)
        a['source']['name'] = 'off.wav'
        b['source']['name'] = 'all.wav'
        text = rr.compare_report([a, b])
        self.assertIn('off.wav', text)
        self.assertIn('all.wav', text)
        self.assertIn('timbre loudness', text)


if __name__ == '__main__':
    unittest.main()
