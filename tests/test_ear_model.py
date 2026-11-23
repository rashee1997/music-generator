# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""M5: the streaming ear model: tuning, compression, adaptation, chunk equality, memory, and the summary quantities."""
import os
import sys
import tracemalloc
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import auditory  # noqa: E402
from ear_model import BinauralSummariser, EarModel, Summariser, iacc  # noqa: E402

SR = 44100


def tone(f, seconds=2.0, amp=0.1):
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


def am(carrier, rate, seconds=3.0, amp=0.1):
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * carrier * t) * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t))).astype(np.float32)


def steady(summary, key):
    return float(np.mean(summary[key][1:]))


class Cochlea(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ear = EarModel(SR)

    def test_a_tone_drives_the_channel_at_its_frequency(self):
        peaks = []
        for f in (250, 1000, 3000):
            nap, _ = self.ear.run(tone(f))
            prof = nap[:, nap.shape[1] // 2:].mean(axis=1)
            k = int(np.argmax(prof))
            self.assertTrue(0.8 < self.ear.fc[k] / f < 1.05, (f, self.ear.fc[k]))
            peaks.append(k)
        self.assertEqual(peaks, sorted(peaks, reverse=True))          # channels run base (high) to apex (low)

    def test_the_cochlea_is_compressive(self):
        levels = {}
        for db in (-70, -50, -30):
            nap, _ = self.ear.run(tone(1000, 1.5, 10 ** (db / 20)))
            levels[db] = float(nap[:, nap.shape[1] // 2:].mean(axis=1).max())
        self.assertGreater(levels[-30], levels[-50])
        self.assertGreater(levels[-50], levels[-70])
        self.assertLess(levels[-30] / levels[-50], 10.0)               # 20 dB more input, far less than 20 dB more output

    def test_a_sustained_tone_adapts(self):
        nap, depth = self.ear.run(tone(1000, 2.0, 0.1))
        rate = self.ear.nap_rate
        k = int(np.argmax(nap[:, nap.shape[1] // 2:].mean(axis=1)))
        onset = float(nap[k, int(0.005 * rate):int(0.03 * rate)].max())
        late = float(nap[k, int(1.5 * rate):].mean())
        self.assertGreater(onset, 1.5 * late)
        self.assertGreater(float(depth[k, int(1.5 * rate):].mean()), float(depth[k, :int(0.01 * rate)].mean()))

    def test_silence_stays_silent(self):
        nap, depth = self.ear.run(np.zeros(SR, dtype=np.float32))
        self.assertLess(float(np.abs(nap).max()), 1e-6)
        self.assertLess(float(depth.max()), 1e-6)

    def test_a_run_is_repeatable(self):
        x = tone(440, 1.0) + tone(660, 1.0)
        a, _ = self.ear.run(x)
        b, _ = self.ear.run(x)
        self.assertTrue(np.array_equal(a, b))


class Streaming(unittest.TestCase):
    def test_chunked_equals_unchunked(self):
        rng = np.random.default_rng(4)
        x = (0.05 * rng.standard_normal(SR * 12) + tone(330, 12.0, 0.05)).astype(np.float32)
        ear = EarModel(SR)
        a, da = ear.run(x, chunk_s=3.0)
        b, db = ear.run(x, chunk_s=60.0)
        self.assertEqual(a.shape, b.shape)
        scale = max(1.0, float(np.abs(b).max()))
        self.assertLess(float(np.abs(a - b).max()) / scale, 1e-5)
        self.assertLess(float(np.abs(da - db).max()), 1e-5)

    def test_output_is_float32_and_decimated(self):
        ear = EarModel(SR)
        nap, depth = ear.run(tone(500, 2.0))
        self.assertEqual(nap.dtype, np.float32)
        self.assertEqual(depth.dtype, np.float32)
        self.assertAlmostEqual(ear.nap_rate, 2240.0)
        self.assertEqual(nap.shape[0], ear.n)

    def test_peak_python_memory_is_bounded_by_the_chunk_not_the_track(self):
        ear = EarModel(SR)
        x = (0.05 * np.random.default_rng(1).standard_normal(SR * 40)).astype(np.float32)
        tracemalloc.start()
        for _ in ear.stream(x, 5.0):
            pass
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLess(peak / 1e6, 200.0)

    def test_other_sample_rates_resample_to_the_model_rate(self):
        ear = EarModel(48000)
        t = np.arange(48000 * 2) / 48000
        nap, _ = ear.run((0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32))
        k = int(np.argmax(nap[:, nap.shape[1] // 2:].mean(axis=1)))
        self.assertTrue(0.8 < ear.fc[k] / 1000.0 < 1.05)


class Summary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ear = EarModel(SR)
        cls.sm = Summariser(cls.ear)

    def test_pitch_of_a_complex_tone(self):
        t = np.arange(SR * 4) / SR
        x = sum(0.05 * np.sin(2 * np.pi * 220 * h * t) / h for h in range(1, 6)).astype(np.float32)
        r = self.sm.run(x)
        self.assertAlmostEqual(steady(r, 'f0_hz') / 220.0, 1.0, delta=0.04)
        self.assertGreater(steady(r, 'salience'), 0.6)
        self.assertGreater(steady(r, 'resolved'), 0.5)

    def test_noise_has_less_pitch_salience_than_a_tone(self):
        noise = (0.05 * np.random.default_rng(2).standard_normal(SR * 4)).astype(np.float32)
        t = np.arange(SR * 4) / SR
        harm = sum(0.05 * np.sin(2 * np.pi * 220 * h * t) / h for h in range(1, 6)).astype(np.float32)
        self.assertLess(steady(self.sm.run(noise), 'salience'), steady(self.sm.run(harm), 'salience') - 0.2)

    def test_roughness_peaks_for_modulation_near_70_hz(self):
        r = {rate: steady(self.sm.run(am(1000, rate)), 'roughness') for rate in (4, 70, 400)}
        pure = steady(self.sm.run(tone(1000, 3.0)), 'roughness')
        self.assertGreater(r[70], 2.0 * r[4])
        self.assertGreater(r[70], 2.0 * r[400])
        self.assertGreater(r[70], 2.0 * pure)

    def test_a_dense_steady_pad_is_more_fatiguing_than_sparse_bursts_of_equal_energy(self):
        rng = np.random.default_rng(7)
        t = np.arange(SR * 8) / SR
        pad = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in rng.uniform(150, 3000, 16))
        pad = (0.2 * pad / np.abs(pad).max()).astype(np.float32)
        gate = ((t % 1.0) < 0.1).astype(np.float32)
        burst = pad * gate
        burst *= float(np.sqrt(np.mean(pad ** 2) / np.mean(burst ** 2)))
        dense, sparse = self.sm.run(pad), self.sm.run(burst.astype(np.float32))
        self.assertAlmostEqual(float(np.sqrt(np.mean(pad ** 2))), float(np.sqrt(np.mean(burst ** 2))), delta=1e-3)
        self.assertGreater(steady(dense, 'fatigue'), steady(sparse, 'fatigue'))

    def test_frame_count_and_times(self):
        r = self.sm.run(tone(440, 5.0))
        self.assertEqual(len(r['fatigue']), 5)
        self.assertAlmostEqual(float(r['times_s'][0]), 0.5, places=3)

    def test_iacc_identical_ears_and_independent_noise(self):
        ear_l, ear_r = EarModel(SR), EarModel(SR)
        x = (0.05 * np.random.default_rng(3).standard_normal(SR * 3)).astype(np.float32)
        y = (0.05 * np.random.default_rng(9).standard_normal(SR * 3)).astype(np.float32)
        same = BinauralSummariser(ear_l, ear_r).run(x, x)
        diff = BinauralSummariser(ear_l, ear_r).run(x, y)
        self.assertGreater(float(same.mean()), 0.99)
        self.assertLess(float(diff.mean()), 0.5)
        shifted = np.roll(x, 12)                                     # 0.27 ms: inside the +-1 ms search
        self.assertGreater(float(BinauralSummariser(ear_l, ear_r).run(x, shifted).mean()), 0.8)

    def test_iacc_function_bounds(self):
        a = np.random.default_rng(0).standard_normal((4, 500))
        self.assertTrue(np.allclose(iacc(a, a, 2), 1.0, atol=1e-6))
        self.assertTrue(np.all(iacc(a, -a, 2) < 0.5))


class Scales(unittest.TestCase):
    def test_one_home_for_the_auditory_scales(self):
        self.assertAlmostEqual(float(auditory.erb_rate(1000.0)), 15.6, delta=0.2)
        self.assertAlmostEqual(float(auditory.erb_to_hz(auditory.erb_rate(440.0))), 440.0, places=6)
        self.assertAlmostEqual(float(auditory.erb_bandwidth(1000.0)), 132.6, delta=0.5)
        self.assertAlmostEqual(float(auditory.bark(1000.0)), 8.5, delta=0.1)
        self.assertLess(float(auditory.ath_db(3300.0)), float(auditory.ath_db(100.0)))


if __name__ == '__main__':
    unittest.main()
