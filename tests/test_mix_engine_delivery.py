"""The mixing engine's measurement layer: standards, meters and the masking proxy.

These tests assert the claims, not the implementation: a declared standard that contradicts its document is
caught, a true peak between samples is found, PLR/PSR are the defined differences, an out-of-phase band shows
up in its own band, and the measured band excess names the masked band.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

import mix_engine.masking as masking       # noqa: E402
import mix_engine.meters as meters         # noqa: E402
import mix_engine.standards as standards   # noqa: E402


def _stereo(sig, sr=44100, seconds=1.0):
    n = int(sr * seconds)
    x = np.asarray(sig[:n], dtype=np.float32)
    return np.stack([x, x], axis=1)


class StandardsTests(unittest.TestCase):

    def test_the_figures_are_the_documents(self):
        self.assertEqual(standards.get('ebu_r128')['lufs'], -23.0)
        self.assertEqual(standards.get('ebu_r128')['true_peak'], -1.0)
        self.assertEqual(standards.get('atsc_a85')['lufs'], -24.0)
        self.assertEqual(standards.get('atsc_a85')['true_peak'], -2.0)
        self.assertEqual(standards.get('aes_td1008')['lufs'], -16.0)
        self.assertEqual(standards.get('spotify')['kind'], 'policy')

    def test_an_unknown_standard_names_the_known_ones(self):
        with self.assertRaises(KeyError) as ctx:
            standards.get('apple_music')
        self.assertIn('ebu_r128', str(ctx.exception))

    def test_a_profile_that_contradicts_its_standard_is_a_problem(self):
        problems = standards.declaration_problems('ebu_r128', -14.0, -1.5)
        self.assertTrue(any('-23' in p for p in problems), problems)
        self.assertFalse(standards.declaration_problems('ebu_r128', -23.0, -1.0))

    def test_a_delivered_file_outside_the_tolerance_warns(self):
        level, msg = standards.file_problems('ebu_r128', -21.0, -1.0)
        self.assertEqual(level, 'WARN')
        self.assertIn('EBU R 128', msg)
        self.assertEqual(standards.file_problems('ebu_r128', -23.1, -1.2)[0], 'PASS')

    def test_a_platform_policy_is_reported_not_failed(self):
        level, msg = standards.file_problems('spotify', -10.0, -0.5)
        self.assertEqual(level, 'INFO')
        self.assertIn('normalises', msg)


class TruePeakTests(unittest.TestCase):

    def test_an_inter_sample_peak_is_found_by_oversampling(self):
        sr = 44100
        n = sr // 4
        t = np.arange(n) / sr
        # fs/4 tone at 45 degrees: every sample sits below the peak of the continuous waveform
        x = _stereo(0.7 * np.sin(2 * np.pi * (sr / 4) * t + np.pi / 4), sr, 0.25)
        rep = meters.true_peak_report(x, sr)
        sample_peak = 20 * np.log10(np.abs(x).max())
        self.assertGreater(rep['true_peak'], sample_peak + 2.0)
        self.assertGreaterEqual(rep['true_peak_8x'], rep['true_peak_4x'] - 1e-9)

    def test_micro_dynamics_are_the_defined_differences(self):
        md = meters.micro_dynamics(-14.0, -1.0, -9.5)
        self.assertAlmostEqual(md['plr'], 13.0)
        self.assertAlmostEqual(md['psr'], 8.5)
        self.assertTrue(np.isnan(meters.micro_dynamics(-14.0, -1.0)['psr']))


class MonoBandTests(unittest.TestCase):

    def test_a_polarity_flipped_band_shows_in_its_own_band(self):
        sr = 44100
        t = np.arange(sr) / sr
        base = 0.4 * np.sin(2 * np.pi * 300 * t)
        x = np.stack([base, -base], axis=1)
        rows = meters.band_correlation(x, sr)
        band = next(r for r in rows if r['band_hz'][0] <= 300 < r['band_hz'][1])
        self.assertLess(band['correlation'], -0.9)
        self.assertLess(band['fold_loss_db'], -20.0)
        self.assertGreaterEqual(band['fold_loss_db'], -60.0)     # clamped for reporting

    def test_correlated_channels_do_not_lose_in_the_fold(self):
        sr = 44100
        t = np.arange(sr) / sr
        base = 0.3 * np.sin(2 * np.pi * 500 * t)
        rows = meters.band_correlation(np.stack([base, base], axis=1), sr)
        band = next(r for r in rows if r['band_hz'][0] <= 500 < r['band_hz'][1])
        self.assertGreater(band['correlation'], 0.95)
        self.assertGreater(band['fold_loss_db'], -0.5)


class MaskingTests(unittest.TestCase):

    def test_the_band_where_the_bed_covers_the_figure_is_named(self):
        sr = 44100
        t = np.arange(sr) / sr
        focus = _stereo(0.2 * np.sin(2 * np.pi * 1200 * t), sr)
        bed = _stereo(0.5 * np.sin(2 * np.pi * 1200 * t), sr)
        rows = masking.band_excess_db(focus, bed, sr)
        named, msg = masking.describe(rows, floor_db=0.0)
        band = min((r for r in rows if r['band_hz'][0] <= 1200 < r['band_hz'][1]),
                   key=lambda r: abs(r['band_hz'][0] - 1200))
        self.assertGreater(band['excess_db'], 5.0)
        self.assertTrue(named)
        self.assertIn('Hz', msg)

    def test_a_quiet_bed_has_no_excess(self):
        sr = 44100
        t = np.arange(sr) / sr
        focus = _stereo(0.5 * np.sin(2 * np.pi * 1200 * t), sr)
        bed = _stereo(0.01 * np.sin(2 * np.pi * 1200 * t), sr)
        named, msg = masking.describe(masking.band_excess_db(focus, bed, sr), floor_db=0.0)
        self.assertFalse(named)
        self.assertIn('within', msg)


if __name__ == '__main__':
    unittest.main()
