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

"""One test per defect found by the environment / sfx / physics audit. Each fails on the code as it was."""
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from scipy.signal import butter, sosfilt

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import environment
import mechanics
import sfx
import sound_model
from phys_core import calibrate, excite, fracture, materials, registry, resonate, baseline
from sfx_engine import oneshot

SR = 44100
VOICE = [{'name': 'a', 'excite': {'kind': 'noise'}, 'resonator': {'kind': 'none'}, 'events': {'kind': 'continuous'}}]


class EnvironmentLayers(unittest.TestCase):
    def test_off_by_one_primitive_length_with_trajectory_and_diffuse(self):
        for extra in ({'trajectory': {'start_azimuth': -30.0}}, {'diffuse': True}):
            cfg = {'layers': [dict(primitive='model_layer', gain_db=-20, voices=VOICE, **extra)]}
            y = environment.render_environment_preset(cfg, duration_s=30.00002)
            self.assertEqual(y.shape, (int(30.00002 * SR), 2))

    def test_malformed_scene_layers_does_not_recurse(self):
        y = environment.render_environment_preset({'scene_layers': 'abc', 'layers': []}, duration_s=0.5)
        self.assertEqual(y.shape[1], 2)

    def test_turbulence_matches_the_shared_series(self):
        rng = np.random.default_rng(3)
        spec = np.fft.rfft(rng.standard_normal(5000))
        f = np.fft.rfftfreq(5000, 1.0 / SR)
        spec *= (1.0 + (f / 0.2) ** 2) ** (-5.0 / 12.0)
        spec[0] = 0.0
        z = np.fft.irfft(spec, 5000)
        old = (z / max(1e-9, z.std())).astype(np.float32)
        new = environment._turbulence(5000, SR, np.random.default_rng(3), 0.2)
        np.testing.assert_array_equal(old, new)

    def test_rise_ramp_helper(self):
        att, rise = environment._impact_rise(SR)
        self.assertEqual(att, int(0.0025 * SR))
        self.assertEqual(rise.dtype, np.float32)
        self.assertAlmostEqual(float(rise[0]), 0.0)


class PhysCore(unittest.TestCase):
    def test_calibration_highpass_key_is_reachable(self):
        self.assertEqual(calibrate.problems({'highpass_hz': 25}), [])
        self.assertTrue(calibrate.problems({'highpass_hz': 'x'}))
        self.assertTrue(calibrate.problems({'nope': 1}))

    def test_registry_lists_come_from_the_modules(self):
        live = registry.implemented()
        for phantom in ('pulse_train', 'friction_surface', 'turbulence', 'burst'):
            self.assertNotIn(phantom, live['excite'])
        for name in live['excite']:
            self.assertTrue(callable(getattr(excite, name)))
        for name in live['resonator']:
            self.assertTrue(callable(getattr(resonate, name)))
        self.assertEqual(live['events'], sorted(sound_model.EVENTS))
        self.assertNotIn('dependency', live['events'])

    def test_small_fragments_leave_first(self):
        for seed in range(5):
            fr = fracture.fragments(materials.get('glass'), 2.0, np.random.default_rng(seed))
            sizes = [s for s, _ in fr]
            delays = [d for _, d in fr]
            self.assertEqual(sizes, sorted(sizes))
            self.assertEqual(delays, sorted(delays))

    def test_dead_code_is_gone(self):
        for mod, names in ((excite, ['burst']), (materials, ['speed_of_sound', 'is_brittle', 'is_fibrous']),
                           (resonate, ['bubble_radius'])):
            for n in names:
                self.assertFalse(hasattr(mod, n), n)

    def test_baseline_metrics_surfaces_non_measurement_errors(self):
        import ambience_reference as ar
        with mock.patch.object(ar, 'measure_array', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                baseline._metrics(np.random.default_rng(0).standard_normal(20000))
        with mock.patch.object(ar, 'measure_array', side_effect=ValueError('short')):
            self.assertIn('peak', baseline._metrics(np.zeros(10)))


class Mechanics(unittest.TestCase):
    CFG = {'enabled': True, 'default_class': 'keys', 'classes': {'keys': {
        'onset': {'gain_db': -30, 'lo_hz': 300, 'hi_hz': 4000, 'ms': 8},
        'offset': {'gain_db': -96, 'ms': 0}}}}

    def _old_add(self, x, events, sr, seed):
        """The previous add(): probes the spec with a full burst drawn from the RNG."""
        rng = np.random.default_rng(int(seed) + 104729)
        out = np.array(x, dtype=np.float32, copy=True)[:, None]
        spec_k = self.CFG['classes']['keys']['onset']

        def burst(level):
            n = max(2, int(spec_k['ms'] / 1000.0 * sr))
            sos = butter(2, [300, 4000], 'band', fs=sr, output='sos')
            noise = sosfilt(sos, rng.standard_normal(n))
            return (noise * np.hanning(n) * 10 ** (spec_k['gain_db'] / 20.0) * level).astype(np.float32)
        for e in events:
            i0 = int(e['t'] * sr)
            burst(0.0)
            seg = burst(10 ** 0 * (0.35 + 0.65 * e['v'] / 127.0))[:max(0, len(out) - i0)]
            out[i0:i0 + len(seg), 0] += seg
        return out

    def test_add_keeps_the_random_stream_of_earlier_renders(self):
        x = np.zeros(SR, np.float32)
        ev = [dict(t=0.1, v=100, dur=0.2), dict(t=0.5, v=60, dur=0.1)]
        with mock.patch.object(mechanics, '_table', return_value=self.CFG):
            new = mechanics.add(x, {}, ev, sr=SR, seed=5)
        np.testing.assert_array_equal(new, self._old_add(x, ev, SR, 5))

    def test_broken_mix_preset_is_not_replaced_by_defaults(self):
        import presets
        with mock.patch.object(presets, 'mix', side_effect=ValueError('bad json')):
            with self.assertRaises(ValueError):
                mechanics._table()
        with mock.patch.object(presets, 'mix', side_effect=KeyError('none')):
            self.assertIsInstance(mechanics._table(), dict)


class Duplication(unittest.TestCase):
    def test_band_helper_matches_old_formulations(self):
        x = np.random.default_rng(1).standard_normal(8000)
        lo, hi = 10.0, 30000.0
        old = sosfilt(butter(2, [max(lo, 20.0), min(hi, SR / 2 - 100)], btype='band', fs=SR, output='sos'), x)
        np.testing.assert_array_equal(sound_model._band(x, (lo, hi), SR), old)
        np.testing.assert_array_equal(sfx._bp(x, lo, hi, SR), old)

    def test_impact_excitation_matches_old(self):
        n, tau = 3000, 0.004
        m = min(max(2, int(round(tau * SR))), n)
        t = np.arange(m) / m
        pulse = 1 - np.cos(2 * np.pi * t)
        old = np.zeros(n)
        old[:m] = pulse / max(pulse.sum(), 1e-12)
        got = sound_model.excitation({'kind': 'impact', 'tau': tau}, n / SR, SR, np.random.default_rng(0))
        np.testing.assert_array_equal(got, old)

    def test_bubble_event_matches_old(self):
        rs = dict(radius_mm=2.0, f_hz=None, t60=0.03, rise=0.1)
        f0 = min(3.26 / (2.0 * 1e-3) * 1.2, SR / 2 - 300)
        n = int(round(0.06 * SR))
        t = np.arange(n) / SR
        d = 6.907755 / 0.03
        old = np.exp(-d * t) * np.sin(2 * np.pi * f0 * (t + 0.5 * 0.1 * d * t * t))
        np.testing.assert_array_equal(sound_model.bubble_event(rs, 0.06, SR, 1.2), old)

    def test_kaimal_unchanged(self):
        rng = np.random.default_rng(9)
        spec = np.fft.rfft(rng.standard_normal(4000))
        f = np.fft.rfftfreq(4000, 1.0 / SR)
        spec *= (1.0 + (f / 0.12) ** 2) ** (-5.0 / 12.0)
        spec[0] = 0.0
        z = np.fft.irfft(spec, 4000)
        z = z / (z.std() + 1e-12)
        old = np.clip(1.0 + 0.2 * z, 0.05, 3.0)
        np.testing.assert_array_equal(excite.kaimal(4000, SR, np.random.default_rng(9)), old)

    def test_sfx_timeline_is_the_engine_timeline(self):
        items = [dict(name='whoosh', at=0.1, seconds=0.5, gain_db=-6, pan=0.4),
                 dict(name='clock_tick', at=0.8, seconds=0.2, pan=-1.0)]
        np.testing.assert_array_equal(sfx.timeline(items, 1.5, SR, seed=3), oneshot.timeline(items, 1.5, SR, seed=3))
        pan = 0.4
        x, _, _ = sfx.make('whoosh', 0.5, SR, 3)
        ref = np.zeros((int(round(1.5 * SR)), 2))
        s = int(0.1 * SR)
        x = x * 10 ** (-6 / 20)
        ref[s:s + len(x), 0] += x * np.sqrt(0.5 * (1 - pan))
        ref[s:s + len(x), 1] += x * np.sqrt(0.5 * (1 + pan))
        got = sfx.timeline(items[:1], 1.5, SR, seed=3)
        np.testing.assert_allclose(got, ref.astype(np.float32), atol=1e-7)

    def test_in_place_place_matches_allocating_place(self):
        def old_place(x, pos, sr, total):
            out = np.zeros(total)
            i = int(pos * sr)
            seg = x[:max(0, total - i)]
            out[i:i + len(seg)] += seg
            return out
        rng = np.random.default_rng(0)
        a = np.zeros(5000)
        b = np.zeros(5000)
        for pos in (0.0, 0.03, 0.1, 0.2):
            x = rng.standard_normal(800)
            a = a + old_place(x, pos, 8000, len(a))
            sfx._place(b, x, pos, 8000)
        np.testing.assert_array_equal(a, b)


if __name__ == '__main__':
    unittest.main()
