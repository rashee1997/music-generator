# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The animal_call primitive: a call is data (elements, a sequence, a tube), measured here on what it must do.

No test names a species' numbers: the shipped call presets are only checked for being renderable.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import signal

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import environment as env
import presets
from env_engine import calls

SR = 44100


def peak_hz(x, lo=20.0, hi=20000.0):
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    mag = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    sel = (f >= lo) & (f <= hi)
    return float(f[sel][np.argmax(mag[sel])])


def level_at(x, hz, width=0.03):
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    mag = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return 20 * np.log10(mag[(f > hz * (1 - width)) & (f < hz * (1 + width))].max() + 1e-12)


def one(spec, seed=1, **kw):
    return calls.element(dict(dict(ms=600.0, harmonics=1, attack=0.02, release=0.02), **spec), SR,
                         np.random.default_rng(seed), **kw)


class Source(unittest.TestCase):
    def test_tube_resonances(self):
        np.testing.assert_allclose(calls.tube_formants(17.15, SR, 3), [500.0, 1500.0, 2500.0], rtol=1e-3)
        self.assertEqual(calls.tube_formants(0.0), [])
        self.assertTrue(all(f < 0.45 * SR for f in calls.tube_formants(1.0, SR, 5)))

    def test_pitch_follows_its_contour(self):
        y = one(dict(f0_hz=[[0.0, 1000.0], [1.0, 2000.0]]))
        n = len(y)
        self.assertAlmostEqual(peak_hz(y[:n // 10]), 1030.0, delta=60.0)
        self.assertAlmostEqual(peak_hz(y[-n // 10:]), 1950.0, delta=90.0)
        self.assertAlmostEqual(peak_hz(one(dict(f0_hz=440.0))), 440.0, delta=3.0)

    def test_a_bigger_animal_is_lower(self):
        self.assertAlmostEqual(peak_hz(one(dict(f0_hz=440.0), scale=0.5)), 220.0, delta=3.0)

    def test_subharmonic_puts_energy_between_the_harmonics(self):
        plain, rough = one(dict(f0_hz=600.0, harmonics=4)), one(dict(f0_hz=600.0, harmonics=4, subharmonic=0.6))
        self.assertGreater(level_at(rough, 300.0), level_at(plain, 300.0) + 30.0)
        self.assertGreater(level_at(rough, 900.0), level_at(plain, 900.0) + 30.0)
        self.assertAlmostEqual(level_at(rough, 600.0), level_at(plain, 600.0), delta=1.0)

    def test_biphonation_adds_an_unrelated_pitch(self):
        plain, two = one(dict(f0_hz=600.0)), one(dict(f0_hz=600.0, biphonation=1.37))
        self.assertGreater(level_at(two, 822.0), level_at(plain, 822.0) + 30.0)

    def test_noise_fills_the_gaps_and_a_jump_steps(self):
        clean, rough = one(dict(f0_hz=500.0, harmonics=6)), one(dict(f0_hz=500.0, harmonics=6, noise=0.5))
        self.assertGreater(level_at(rough, 760.0), level_at(clean, 760.0) + 20.0)
        y = one(dict(f0_hz=400.0, jump=[0.5, 1.5]))
        self.assertAlmostEqual(peak_hz(y[:len(y) // 3]), 400.0, delta=8.0)
        self.assertAlmostEqual(peak_hz(y[-len(y) // 3:]), 600.0, delta=8.0)

    def pulse_rate(self, y):
        envl = np.abs(signal.hilbert(y))
        envl = envl - envl.mean()
        f = np.fft.rfftfreq(len(envl), 1.0 / SR)
        mag = np.abs(np.fft.rfft(envl * np.hanning(len(envl))))
        sel = (f > 4.0) & (f < 200.0)
        return float(f[sel][np.argmax(mag[sel])])

    def test_pulses_and_their_temperature(self):
        spec = dict(f0_hz=1500.0, ms=1500.0, pulse_hz=24.0)
        self.assertAlmostEqual(self.pulse_rate(one(spec)), 24.0, delta=1.0)
        self.assertAlmostEqual(self.pulse_rate(one(spec, rate=1.5)), 36.0, delta=1.5)
        kw = dict(elements=dict(t=spec), bouts_per_min=30.0, first_s=0.1, rate_per_c=0.05)
        warm = calls.synth_animal_call(4.0, SR, np.random.default_rng(1), temp_c=30.0, **kw)
        cool = calls.synth_animal_call(4.0, SR, np.random.default_rng(1), temp_c=20.0, **kw)
        first = lambda y: y[int(0.15 * SR):int(1.4 * SR)]
        self.assertAlmostEqual(self.pulse_rate(first(warm)) / self.pulse_rate(first(cool)), 1.5, delta=0.1)

    def test_the_tube_colours_the_source(self):
        el = dict(buzz=dict(f0_hz=90.0, ms=900.0, harmonics=60, rolloff=0.5))
        kw = dict(elements=el, bouts_per_min=40.0, first_s=0.05)
        dry = calls.synth_animal_call(1.2, SR, np.random.default_rng(2), **kw)
        wet = calls.synth_animal_call(1.2, SR, np.random.default_rng(2), tract_cm=17.15, formant_mix=1.0, **kw)

        def tilt(y):                                      # the first resonance against the valley above it
            f, p = signal.welch(y, SR, nperseg=8192)
            return 10 * np.log10(p[(f > 430) & (f < 570)].mean() / p[(f > 900) & (f < 1100)].mean())
        self.assertGreater(tilt(wet), tilt(dry) + 6.0)


class Call(unittest.TestCase):
    EL = dict(a=dict(f0_hz=800.0, ms=100.0), b=dict(f0_hz=1600.0, ms=100.0))

    def bursts(self, y):
        envl = signal.sosfiltfilt(signal.butter(2, 60.0, fs=SR, output='sos'), np.abs(y))
        on = envl > 0.2 * envl.max()
        return int(np.sum(on[1:] & ~on[:-1]) + on[0])

    def test_sequence_and_repeats(self):
        y = calls.one_call(self.EL, ['a', ['b', 3, 3]], [80.0, 80.0], SR, np.random.default_rng(1))
        self.assertEqual(self.bursts(y), 4)
        self.assertAlmostEqual(len(y) / SR, 4 * 0.1 + 3 * 0.08, delta=0.01)
        self.assertAlmostEqual(peak_hz(y[:int(0.1 * SR)]), 800.0, delta=30.0)
        self.assertAlmostEqual(peak_hz(y[-int(0.1 * SR):]), 1600.0, delta=30.0)
        self.assertAlmostEqual(float(np.abs(y).max()), 1.0, places=6)

    def test_seeded_and_bounded(self):
        kw = dict(elements=self.EL, bouts_per_min=20.0, individuals=3)
        a = calls.synth_animal_call(6.0, SR, np.random.default_rng(5), **kw)
        b = calls.synth_animal_call(6.0, SR, np.random.default_rng(5), **kw)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(len(a), 6 * SR)
        self.assertAlmostEqual(float(np.abs(a).max()), 0.5, places=5)
        self.assertFalse(np.array_equal(a, calls.synth_animal_call(6.0, SR, np.random.default_rng(6), **kw)))

    def test_problems_are_named(self):
        self.assertEqual(calls.problems(dict(elements=self.EL, sequence=['a', ['b', 1, 2]])), [])
        self.assertTrue(any('pitch' in p or 'never read' in p
                            for p in calls.problems(dict(elements=dict(a=dict(f0_hz=500.0, pich=3))))))
        self.assertTrue(any('f0_hz' in p for p in calls.problems(dict(elements=dict(a=dict(ms=100.0))))))
        self.assertTrue(any('not an element' in p for p in calls.problems(dict(elements=self.EL, sequence=['c']))))
        self.assertTrue(any('not a calls preset' in p for p in calls.problems(dict(call='no_such_animal'))))
        with self.assertRaises(ValueError):
            calls.synth_animal_call(1.0, SR, elements=dict(a=dict(f0_hz=500.0, pich=3)))
        bad = env.layer_problems(dict(primitive='animal_call', elements=self.EL, sequence=['zz']))
        self.assertTrue(any('not an element' in p for p in bad))
        self.assertTrue(env.layer_problems(dict(primitive='animal_call', elemnts=self.EL)))

    def test_a_layer_can_change_a_preset(self):
        base = dict(layers=[dict(primitive='animal_call', call='frog_trill', gain_db=-12.0, first_s=0.2)])
        one_frog = dict(layers=[dict(base['layers'][0], individuals=1)])
        a = env.render_environment_preset(base, duration_s=6.0, seed=3)
        b = env.render_environment_preset(one_frog, duration_s=6.0, seed=3)
        self.assertEqual(a.shape, (6 * SR, 2))
        self.assertFalse(np.allclose(a, b))


class Shipped(unittest.TestCase):
    def test_every_call_preset_renders(self):
        known = presets.load('calls')
        self.assertTrue(known)
        for name, body in known.items():
            self.assertEqual(calls.problems(dict(call=name)), [], name)
            self.assertTrue(body.get('sources'), name)
            y = calls.synth_animal_call(8.0, SR, np.random.default_rng(1), call=name, first_s=0.2)
            self.assertTrue(np.isfinite(y).all(), name)
            self.assertGreater(float(np.abs(y).max()), 0.1, name)

    def test_example_places_are_valid_beds(self):
        for name in ('woodland_dawn', 'wetland_night'):
            cfg = presets.find_environment(name)
            self.assertEqual(env.preset_problems(cfg), [], name)
            self.assertTrue(env.preset_is_bed(cfg), name)
            y = env.render_environment_preset(name, duration_s=8.0, seed=2)
            self.assertTrue(np.isfinite(y).all())
            self.assertGreater(float(np.sqrt(np.mean(y ** 2))), 1e-4)


if __name__ == '__main__':
    unittest.main()
