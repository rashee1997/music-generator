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

"""The behaviours added on top of the engine: a dynamic lead carve, a physical barrier, a measured bed
loudness, and a cache key that covers the packages. Each test states the property, not the implementation."""

import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)

import dsp
import environment
import mixer
import render_natural
from phys_core import propagate, scene as pscene

SR = 22050


def band_energy(x, lo, hi, sr=SR):
    from scipy import signal
    y = np.asarray(x, dtype=float)
    if y.ndim == 2:
        y = y.mean(axis=1)
    sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
    return float(np.sum(signal.sosfiltfilt(sos, y) ** 2))


class TestLeadCarve(unittest.TestCase):
    """The bed yields in the lead's band only while the lead is sounding there."""

    def setUp(self):
        n = int(1.5 * SR)
        t = np.arange(n) / SR
        self.n = n
        lead = np.zeros((n, 2), np.float32)
        lead[n // 2:] = (0.5 * np.sin(2 * np.pi * 1000.0 * t[n // 2:]))[:, None]
        bed = (0.4 * np.sin(2 * np.pi * 1000.0 * t))[:, None].repeat(2, axis=1).astype(np.float32)
        self.processed = {'lead': lead, 'pad': bed}
        self.specs = {'lead': {'role': 'melody'}, 'pad': {'role': 'pad'}}
        self.mx = {'lead_carve': {'enabled': True, 'bands_hz': [[700.0, 1400.0]],
                                  'ratio': 4.0, 'threshold_db': -20.0, 'attack_ms': 5.0,
                                  'release_ms': 60.0, 'roles': ['pad']}}

    def test_bed_is_carved_under_the_lead_and_kept_when_it_rests(self):
        out = mixer.apply_lead_carve(dict(self.processed), self.specs, self.mx, SR)
        before, after = self.processed['pad'][:, 0], out['pad'][:, 0]
        quiet = slice(int(0.2 * SR), int(0.6 * SR))          # lead silent
        loud = slice(int(1.0 * SR), int(1.4 * SR))           # lead sounding in the same band
        self.assertGreater(band_energy(after[quiet], 700, 1400), 0.9 * band_energy(before[quiet], 700, 1400))
        self.assertLess(band_energy(after[loud], 700, 1400), 0.75 * band_energy(before[loud], 700, 1400))

    def test_disabled_preset_is_a_no_op(self):
        out = mixer.apply_lead_carve(dict(self.processed), self.specs, {'lead_carve': {'enabled': False}}, SR)
        np.testing.assert_allclose(out['pad'], self.processed['pad'], atol=1e-7)

    def test_band_edges_round_trip(self):
        f, q = mixer._band_center_q(250.0, 4500.0)
        self.assertAlmostEqual(f / (1.0 + 1.0 / (2.0 * q)), 250.0, places=3)
        self.assertAlmostEqual(f * (1.0 + 1.0 / (2.0 * q)), 4500.0, places=3)

    def test_schema_accepts_the_section_and_its_ranges(self):
        self.assertEqual([p for p in mixer.mix_schema.validate({'lead_carve': {'enabled': True}})], [])
        bad = mixer.mix_schema.validate({'lead_carve': {'ratio': 40.0}})
        self.assertTrue(any('lead_carve.ratio' in p for p in bad))


class TestOcclusion(unittest.TestCase):
    """A barrier between source and listener: more loss at height in frequency, and no loss when absent."""

    def setUp(self):
        self.x = np.random.RandomState(0).randn(SR).astype(np.float32)
        self.mats = {'brick': {'density': 1800.0}}

    def test_transmission_is_frequency_dependent(self):
        cfg = {'material': 'brick', 'thickness_m': 0.15, 'edge_offset_m': 0.0, 'coverage': 1.0,
               'distance_m': 4.0}
        y = propagate.occlusion(self.x, SR, cfg, self.mats)
        low = band_energy(y, 100, 300) / band_energy(self.x, 100, 300)
        high = band_energy(y, 4000, 8000) / band_energy(self.x, 4000, 8000)
        self.assertLess(high, low)
        self.assertLess(10 * np.log10(max(high, 1e-12)), 10 * np.log10(max(low, 1e-12)) - 6.0)

    def test_diffraction_alone_still_attenuates_highs_more(self):
        cfg = {'edge_offset_m': 0.4, 'coverage': 1.0, 'transmission': False, 'distance_m': 4.0}
        y = propagate.occlusion(self.x, SR, cfg, {})
        low = band_energy(y, 100, 300) / band_energy(self.x, 100, 300)
        high = band_energy(y, 4000, 8000) / band_energy(self.x, 4000, 8000)
        self.assertLess(high, low)

    def test_a_clear_line_is_untouched(self):
        cfg = {'edge_offset_m': 0.0, 'coverage': 0.0, 'transmission': False, 'distance_m': 4.0}
        y = propagate.occlusion(self.x, SR, cfg, {})
        np.testing.assert_allclose(y, self.x, atol=1e-5)

    def test_scene_validates_the_block(self):
        base = {'seconds': 1.0, 'propagation': {'distance_m': 4.0, 'occluder': {'coverage': 2.0}}}
        probs = pscene.problems(base)
        self.assertTrue(any('occluder.coverage' in p for p in probs))
        ok = {'seconds': 1.0, 'propagation': {'distance_m': 4.0,
                                              'occluder': {'material': 'brick', 'thickness_m': 0.1,
                                                           'coverage': 0.8}}}
        self.assertEqual([p for p in pscene.problems(ok) if 'occluder' in p], [])
        unknown = {'seconds': 1.0, 'propagation': {'distance_m': 4.0, 'occluder': {'foo': 1}}}
        self.assertTrue(any('unknown key "foo"' in p for p in pscene.problems(unknown)))


class TestBedLoudness(unittest.TestCase):
    def test_target_lufs_is_measured_not_guessed(self):
        try:
            meter = dsp.meter(SR)
        except Exception:
            self.skipTest('loudness meter unavailable')
        x = (0.12 * np.random.RandomState(2).randn(2 * SR)).astype(np.float32)
        y = environment._match_lufs(x, -30.0, SR)
        got = meter.integrated_loudness(y.astype(np.float64))
        self.assertLess(abs(got + 30.0), 0.5)


class TestStemCacheKey(unittest.TestCase):
    def test_key_covers_the_render_packages(self):
        for pkg in ('vocal_engine', 'phys_core', 'env_engine', 'sfx_engine'):
            self.assertIn(pkg, render_natural._RENDER_PACKAGES)
        self.assertIn('sound_model.py', render_natural._RENDER_CODE)
        self.assertEqual(render_natural._code_hash(), render_natural._code_hash())


if __name__ == '__main__':
    unittest.main()
