# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""fx_engine: every effect does what its name says (a measured positive control) and leaves alone what it must (a negative one).

Run: python -m unittest tests.test_fx_engine
"""
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import fx_engine  # noqa: E402
import presets  # noqa: E402
from fx_engine import spec  # noqa: E402

SR = 22050


def sine(freq, secs, amp=0.4):
    t = np.arange(int(secs * SR)) / SR
    return np.repeat((amp * np.sin(2 * np.pi * freq * t))[:, None], 2, axis=1).astype(np.float32)


def noise(secs, amp=0.2, seed=0):
    return (amp * np.random.default_rng(seed).standard_normal((int(secs * SR), 2))).astype(np.float32)


def run(x, *chain, seed=1):
    return fx_engine.apply(x, SR, list(chain), seed=seed)


def freq(seg):
    """Frequency of a sine segment from its upward zero crossings."""
    s = seg[:, 0] if seg.ndim == 2 else seg
    up = np.flatnonzero((s[:-1] < 0) & (s[1:] >= 0))
    return 0.0 if len(up) < 2 else (len(up) - 1) * SR / float(up[-1] - up[0])


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))


def at(x, a, b):
    return x[int(a * SR):int(b * SR)]


def added_root(project_dir):
    """Register a project's presets and return the root, so a test can take out exactly what it put in: `reset_projects()` would
    also drop roots other tests registered and rely on."""
    return presets.add_project(project_dir)


def drop_root(root):
    if root in presets.PROJECT_ROOTS:
        presets.PROJECT_ROOTS.remove(root)


class Library(unittest.TestCase):
    def test_the_library_is_consistent_and_every_effect_has_a_function(self):
        self.assertEqual(fx_engine.library_problems(), [])
        self.assertEqual(sorted(fx_engine.EFFECTS), fx_engine.effect_names())

    def test_a_broken_library_is_reported(self):
        lib = copy.deepcopy(spec.library())
        lib['effects']['tape_stop']['params']['dur_s']['default'] = 99.0              # above its own maximum
        lib['effects']['ring_mod']['params']['freq_hz'].pop('text')
        lib['effects']['ghost'] = {'character': 'x', 'params': {}}
        lib['effects']['tremolo']['params']['depth']['min'] = 5.0
        with mock.patch.object(spec, 'library', return_value=lib):
            found = ' | '.join(spec.library_problems(fx_engine.EFFECTS))
        for needle in ('tape_stop.dur_s', 'ring_mod.freq_hz', 'ghost', 'tremolo.depth'):
            self.assertIn(needle, found)

    def test_presets_validate_covers_the_library_and_every_chain(self):
        self.assertEqual([p for p in presets.validate() if p.startswith('fx')], [])

    def test_describe_lists_every_effect(self):
        text = fx_engine.describe()
        for name in fx_engine.effect_names():
            self.assertIn(name, text)


class Chains(unittest.TestCase):
    def test_every_shipped_chain_is_valid_and_runs(self):
        names = sorted(k for k, v in presets.load('fx').items() if 'chain' in v)
        self.assertGreaterEqual(len(names), 8)
        x = noise(3.0)
        for name in names:
            self.assertEqual(fx_engine.problems(name), [], name)
            y = fx_engine.apply(x, SR, name, seed=3)
            self.assertEqual(y.shape, x.shape, name)
            self.assertTrue(np.isfinite(y).all(), name)

    def test_a_named_chain_is_the_same_as_writing_it_out(self):
        written = presets.exact('fx', 'tape_stop_out')['chain']
        x = sine(300, 3.0)
        self.assertTrue(np.array_equal(fx_engine.apply(x, SR, 'tape_stop_out', seed=2), fx_engine.apply(x, SR, written, seed=2)))

    def test_every_problem_is_reported_together(self):
        found = fx_engine.problems([{'type': 'nope'}, {'type': 'tape_stop', 'dur_s': 999, 'bogus': 1},
                                    {'type': 'tremolo', 'depth': 'deep'}, {'type': 'filter_sweep', 'kind': 'notch'},
                                    {'type': 'freeze', 'fft': 1000.5}, {'type': 'ring_mod', 'start_s': 5, 'end_s': 2}, 'no_such_chain'])
        text = ' | '.join(found)
        for needle in ("unknown effect 'nope'", 'above the maximum', "unknown key(s) ['bogus']", 'expected a number',
                       "not one of ['lowpass'", 'must be a whole number', 'must be after start_s', 'no chain preset "no_such_chain"'):
            self.assertIn(needle, text)

    def test_resolve_raises_with_the_problems(self):
        with self.assertRaises(ValueError) as cm:
            fx_engine.resolve([{'type': 'tape_stop', 'dur_s': 0}])
        self.assertIn('below the minimum', str(cm.exception))

    def test_a_chain_inside_a_named_chain_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'fx'))
            with open(os.path.join(d, 'presets', 'fx', 'outer.json'), 'w', encoding='utf-8') as fh:
                json.dump({'name': 'outer', 'character': 'x', 'chain': ['tape_stop_out']}, fh)
            root = added_root(d)
            try:
                self.assertTrue(any('not followed' in p for p in fx_engine.problems('outer')))
                self.assertTrue(any('fx/outer' in p for p in presets.validate()))
            finally:
                drop_root(root)

    def test_a_project_can_override_one_default_and_keep_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'fx'))
            with open(os.path.join(d, 'presets', 'fx', 'effects.json'), 'w', encoding='utf-8') as fh:
                json.dump({'name': 'effects', 'effects': {'tape_stop': {'params': {'dur_s': {'default': 2.5}}}}}, fh)
            root = added_root(d)
            try:
                got = fx_engine.resolve([{'type': 'tape_stop'}])[0]['params']
                self.assertEqual(got['dur_s'], 2.5)
                self.assertEqual(got['curve'], 1.5)
                self.assertEqual(fx_engine.library_problems(), [])
            finally:
                drop_root(root)

    def test_an_empty_chain_and_an_empty_stem(self):
        x = sine(200, 0.5)
        self.assertTrue(np.array_equal(fx_engine.apply(x, SR, []), x))
        self.assertTrue(np.array_equal(fx_engine.apply(x, SR, None), x))
        self.assertEqual(fx_engine.apply(np.zeros((0, 2), np.float32), SR, [{'type': 'ring_mod'}]).shape, (0, 2))


class Defaults(unittest.TestCase):
    def test_every_effect_runs_on_its_defaults_and_keeps_shape_and_type(self):
        x = noise(3.0)
        for kind in fx_engine.effect_names():
            if kind in ('external',):
                continue
            item = {'type': kind}
            if kind == 'pedalboard':
                item['plugin'] = 'Gain'
                item['params'] = {'gain_db': 3.0}
            y = run(x, item)
            self.assertEqual((y.shape, y.dtype), (x.shape, np.float32), kind)
            self.assertTrue(np.isfinite(y).all(), kind)

    def test_effects_that_use_chance_are_repeatable_and_a_seed_changes_them(self):
        x = noise(3.0)
        for kind in ('grain_cloud', 'freeze', 'reverse_swell', 'tape_wobble'):
            a, b, c = (run(x, {'type': kind, 'start_s': 0.2}, seed=s) for s in (5, 5, 6))
            self.assertTrue(np.array_equal(a, b), kind)
            self.assertFalse(np.array_equal(a, c), kind)
        d = run(x, {'type': 'grain_cloud', 'seed': 11}, seed=5)
        e = run(x, {'type': 'grain_cloud', 'seed': 11}, seed=99)
        self.assertFalse(np.array_equal(d, e))                       # the effect's own seed adds to the stem's, it does not replace it


class RangeAndMix(unittest.TestCase):
    def test_an_effect_does_not_leak_outside_its_range(self):
        x = sine(440, 4.0)
        y = run(x, {'type': 'ring_mod', 'freq_hz': 100.0, 'start_s': 1.0, 'end_s': 3.0, 'edge_ms': 50})
        self.assertTrue(np.array_equal(at(y, 0, 1.0), at(x, 0, 1.0)))
        self.assertTrue(np.array_equal(at(y, 3.0, 4.0), at(x, 3.0, 4.0)))
        self.assertFalse(np.allclose(at(y, 1.2, 2.8), at(x, 1.2, 2.8), atol=0.05))

    def test_the_edges_are_a_crossfade_not_a_step(self):
        x = sine(440, 3.0)
        y = run(x, {'type': 'ring_mod', 'freq_hz': 100.0, 'start_s': 1.0, 'end_s': 2.0, 'edge_ms': 100})
        step = float(np.max(np.abs(np.diff(y[:, 0]))))
        self.assertLess(step, 0.1)                                     # the carrier alone moves a 440 Hz sine by ~0.05 a sample

    def test_mix_zero_is_the_input_and_mix_half_is_halfway(self):
        x = sine(440, 2.0)
        full = run(x, {'type': 'ring_mod', 'freq_hz': 100.0})
        self.assertTrue(np.array_equal(run(x, {'type': 'ring_mod', 'mix': 0.0}), x))
        half = run(x, {'type': 'ring_mod', 'freq_hz': 100.0, 'mix': 0.5})
        np.testing.assert_allclose(half, x + 0.5 * (full - x), atol=1e-6)

    def test_a_nonfinite_result_names_its_effect(self):
        nan_fn = lambda x, sr, p, rng: np.full_like(x, np.nan)                     # noqa: E731
        with mock.patch.dict(fx_engine.EFFECTS, {'ring_mod': (nan_fn, 'ranged', None)}):
            with self.assertRaises(ValueError) as cm:
                run(sine(440, 1.0), {'type': 'ring_mod'})
        self.assertIn('ring_mod', str(cm.exception))
        self.assertIn('non-finite', str(cm.exception))

    def test_a_mono_vector_is_accepted(self):
        y = fx_engine.apply(sine(440, 1.0)[:, 0], SR, [{'type': 'ring_mod'}])
        self.assertEqual(y.shape, (SR, 2))


class TimeEffects(unittest.TestCase):
    def test_tape_stop_slows_the_pitch_drops_the_level_and_ends_in_silence(self):
        x = sine(440, 4.0)
        y = run(x, {'type': 'tape_stop', 'start_s': 1.0, 'dur_s': 1.0, 'curve': 1.0})
        self.assertTrue(np.array_equal(at(y, 0, 1.0), at(x, 0, 1.0)))
        early, late = freq(at(y, 1.0, 1.1)), freq(at(y, 1.6, 1.75))
        self.assertAlmostEqual(early, 440 * 0.95, delta=25)
        self.assertLess(late, 0.55 * early)
        self.assertLess(rms(at(y, 1.8, 1.9)), 0.7 * rms(at(y, 1.0, 1.1)))
        self.assertEqual(float(np.max(np.abs(at(y, 2.01, 4.0)))), 0.0)

    def test_a_tape_stop_after_the_stem_ends_changes_nothing(self):
        x = sine(440, 2.0)
        self.assertTrue(np.array_equal(run(x, {'type': 'tape_stop', 'start_s': 5.0}), x))

    def test_pitch_glide_reaches_the_interval_and_leaves_the_rest_alone(self):
        x = sine(440, 4.0)
        y = run(x, {'type': 'pitch_glide', 'start_s': 1.0, 'end_s': 3.0, 'semitones': 12.0, 'curve': 1.0})
        self.assertAlmostEqual(freq(at(y, 2.9, 2.97)), 440 * 2 ** (12 * 0.97 / 12), delta=45)
        self.assertAlmostEqual(freq(at(y, 1.0, 1.1)), 440 * 2 ** (12 * 0.03 / 12), delta=20)
        self.assertTrue(np.array_equal(at(y, 0, 1.0), at(x, 0, 1.0)))
        self.assertTrue(np.array_equal(at(y, 3.1, 4.0), at(x, 3.1, 4.0)))

    def test_pitch_glide_dives_when_the_interval_is_negative(self):
        x = sine(440, 4.0)
        y = run(x, {'type': 'pitch_glide', 'start_s': 1.0, 'end_s': 3.0, 'semitones': -12.0})
        self.assertLess(freq(at(y, 2.9, 2.97)), 300)

    def test_doppler_pitch_follows_the_path_and_the_level_peaks_at_the_pass(self):
        x = sine(1000, 6.0)
        y = run(x, {'type': 'doppler', 'start_s': 0.0, 'end_s': 6.0, 'closest_m': 5.0, 'speed_m_s': 60.0, 'c_m_s': 343.0, 'edge_ms': 0})
        approach, recede = freq(at(y, 0.5, 0.6)), freq(at(y, 5.4, 5.5))
        self.assertAlmostEqual(approach, 1000 / (1 - 60.0 / 343.0), delta=70)
        self.assertAlmostEqual(recede, 1000 / (1 + 60.0 / 343.0), delta=50)
        self.assertGreater(approach, 1000)
        self.assertLess(recede, 1000)
        self.assertGreater(20 * np.log10(rms(at(y, 2.9, 3.1)) / rms(at(y, 0.5, 0.6))), 15.0)

    def test_doppler_reads_the_speed_of_sound_from_the_medium_unless_told(self):
        x = sine(1000, 4.0)
        a = run(x, {'type': 'doppler', 'start_s': 0, 'end_s': 4, 'edge_ms': 0})
        b = run(x, {'type': 'doppler', 'start_s': 0, 'end_s': 4, 'edge_ms': 0, 'c_m_s': 343.0})
        np.testing.assert_allclose(a, b, atol=1e-6)                              # the active medium is air at 343 m/s
        c = run(x, {'type': 'doppler', 'start_s': 0, 'end_s': 4, 'edge_ms': 0, 'c_m_s': 1500.0})
        self.assertFalse(np.allclose(a, c, atol=1e-3))

    def test_wow_and_flutter_deviate_by_the_cents_asked(self):
        from scipy.signal import hilbert
        x = sine(1000, 8.0)

        def deviation_cents(cents):
            y = run(x, {'type': 'tape_wobble', 'wow_hz': 0.5, 'wow_cents': cents, 'flutter_cents': 0.0})
            phase = np.unwrap(np.angle(hilbert(y[:, 0].astype(np.float64))))
            inst = np.diff(phase) * SR / (2 * np.pi)
            body = inst[SR:-SR]
            return float(np.max(np.abs(1200 * np.log2(body / 1000.0))))
        self.assertAlmostEqual(deviation_cents(20.0), 20.0, delta=6.0)
        self.assertGreater(deviation_cents(20.0), 2.5 * deviation_cents(5.0))

    def test_no_wobble_is_no_change(self):
        x = sine(1000, 2.0)
        y = run(x, {'type': 'tape_wobble', 'wow_cents': 0.0, 'flutter_cents': 0.0})
        np.testing.assert_allclose(y, x, atol=1e-6)

    def test_stutter_repeats_the_first_slice_a_little_quieter(self):
        x = noise(3.0, seed=4)
        y = run(x, {'type': 'stutter', 'start_s': 0.5, 'end_s': 1.5, 'slice_ms': 100.0, 'decay_db': -3.0, 'edge_ms': 0})
        i0, ln = SR // 2, int(0.1 * SR)
        first, second = y[i0:i0 + ln], y[i0 + ln:i0 + 2 * ln]
        np.testing.assert_allclose(second, first * 10 ** (-3.0 / 20), atol=1e-5)
        self.assertTrue(np.array_equal(at(y, 0, 0.5), at(x, 0, 0.5)))
        self.assertTrue(np.array_equal(at(y, 1.5, 3.0), at(x, 1.5, 3.0)))

    def test_a_slice_longer_than_the_range_changes_nothing(self):
        x = noise(2.0)
        self.assertTrue(np.array_equal(run(x, {'type': 'stutter', 'start_s': 0.5, 'end_s': 0.6, 'slice_ms': 500.0}), x))

    def test_freeze_holds_a_steady_wash_at_the_level_it_was_taken(self):
        t = np.arange(6 * SR) / SR
        x = np.repeat((0.5 * np.sin(2 * np.pi * 440 * t) * np.exp(-3 * t))[:, None], 2, axis=1).astype(np.float32)
        y = run(x, {'type': 'freeze', 'start_s': 0.5, 'hold_s': 3.0, 'fft': 2048})
        held = [rms(at(y, a, a + 0.25)) for a in np.arange(1.0, 3.2, 0.25)]
        decay = [rms(at(x, a, a + 0.25)) for a in np.arange(1.0, 3.2, 0.25)]
        self.assertLess(np.std(held) / np.mean(held), 0.08)            # steady
        self.assertGreater(np.std(decay) / np.mean(decay), 0.5)        # the dry stem is not
        ref = rms(x[max(0, int(0.5 * SR) - 2048):int(0.5 * SR) + 2048])
        self.assertAlmostEqual(np.mean(held) / ref, 1.0, delta=0.25)
        seg = at(y, 2.0, 2.5)[:, 0]
        peak = np.fft.rfftfreq(len(seg), 1 / SR)[np.argmax(np.abs(np.fft.rfft(seg * np.hanning(len(seg)))))]
        self.assertAlmostEqual(peak, 440, delta=25)
        self.assertTrue(np.array_equal(at(y, 0, 0.5), at(x, 0, 0.5)))
        self.assertTrue(np.array_equal(at(y, 3.7, 6.0), at(x, 3.7, 6.0)))

    def test_a_freeze_shorter_than_one_frame_changes_nothing(self):
        x = sine(440, 2.0)
        self.assertTrue(np.array_equal(run(x, {'type': 'freeze', 'start_s': 0.5, 'hold_s': 0.1, 'fft': 8192}), x))

    def test_grain_cloud_is_levelled_against_the_stem_and_stays_in_its_range(self):
        x = sine(330, 5.0) + noise(5.0, 0.05, 2)
        y = run(x, {'type': 'grain_cloud', 'start_s': 1.0, 'end_s': 4.0, 'level_db': -6.0, 'edge_ms': 0})
        self.assertAlmostEqual(rms(at(y, 1.0, 4.0)) / rms(at(x, 1.0, 4.0)), 10 ** (-6.0 / 20), delta=0.05)
        self.assertTrue(np.array_equal(at(y, 0, 1.0), at(x, 0, 1.0)))
        self.assertTrue(np.array_equal(at(y, 4.0, 5.0), at(x, 4.0, 5.0)))
        self.assertFalse(np.allclose(at(y, 1.5, 3.5), at(x, 1.5, 3.5), atol=0.05))

    def test_a_cloud_too_thin_to_start_a_grain_changes_nothing(self):
        x = noise(2.0)
        self.assertTrue(np.array_equal(run(x, {'type': 'grain_cloud', 'start_s': 0.5, 'end_s': 1.0, 'density_hz': 1.0}), x))


class FilterAndModulation(unittest.TestCase):
    def gain(self, y, x, a, b):
        return rms(at(y, a, b)) / rms(at(x, a, b))

    def test_a_lowpass_sweep_opens_over_the_range(self):
        x = sine(5000, 6.0)
        y = run(x, {'type': 'filter_sweep', 'kind': 'lowpass', 'f_start_hz': 200, 'f_end_hz': 8000, 'q': 0.7, 'start_s': 1.0, 'end_s': 5.0})
        self.assertLess(self.gain(y, x, 1.1, 1.3), 0.1)
        self.assertGreater(self.gain(y, x, 4.8, 4.95), 0.8)
        self.assertTrue(np.array_equal(at(y, 0, 1.0), at(x, 0, 1.0)))

    def test_after_bypass_returns_the_dry_stem_and_after_hold_keeps_the_filter(self):
        x = sine(5000, 6.0)
        base = {'type': 'filter_sweep', 'kind': 'lowpass', 'f_start_hz': 1000, 'f_end_hz': 1000, 'q': 0.7, 'start_s': 1.0, 'end_s': 3.0}
        bypass, hold = run(x, dict(base, after='bypass')), run(x, dict(base, after='hold'))
        self.assertTrue(np.array_equal(at(bypass, 3.1, 6.0), at(x, 3.1, 6.0)))
        self.assertLess(self.gain(hold, x, 3.5, 5.5), 0.1)

    def test_a_highpass_removes_what_is_below_and_a_bandpass_keeps_its_centre(self):
        low = sine(100, 4.0)
        hp = run(low, {'type': 'filter_sweep', 'kind': 'highpass', 'f_start_hz': 2000, 'f_end_hz': 2000, 'start_s': 0.5, 'end_s': 3.5})
        self.assertLess(self.gain(hp, low, 1.0, 3.0), 0.05)
        bp = {'type': 'filter_sweep', 'kind': 'bandpass', 'f_start_hz': 1000, 'f_end_hz': 1000, 'q': 4.0, 'start_s': 0.5, 'end_s': 3.5}
        self.assertGreater(self.gain(run(sine(1000, 4.0), bp), sine(1000, 4.0), 1.0, 3.0), 0.8)
        self.assertLess(self.gain(run(low, bp), low, 1.0, 3.0), 0.2)

    def test_ring_mod_moves_the_energy_to_the_sidebands(self):
        y = run(sine(440, 4.0), {'type': 'ring_mod', 'freq_hz': 100.0})
        spec_ = np.abs(np.fft.rfft(y[:, 0] * np.hanning(len(y))))
        f = np.fft.rfftfreq(len(y), 1 / SR)
        peak = lambda c: spec_[(f > c - 3) & (f < c + 3)].max()          # noqa: E731
        self.assertGreater(peak(340), 20 * peak(440))
        self.assertGreater(peak(540), 20 * peak(440))

    def test_tremolo_dips_by_its_depth_and_zero_depth_is_the_input(self):
        x = sine(440, 4.0)
        y = run(x, {'type': 'tremolo', 'rate_hz': 2.0, 'depth': 0.6})
        env = np.array([rms(at(y, a, a + 0.02)) for a in np.arange(0.1, 3.8, 0.02)])
        self.assertAlmostEqual(env.min() / env.max(), 0.4, delta=0.06)
        np.testing.assert_allclose(run(x, {'type': 'tremolo', 'depth': 0.0}), x, atol=1e-6)

    def test_auto_pan_swings_between_the_channels_and_none_keeps_them_equal(self):
        x = sine(440, 4.0)
        y = run(x, {'type': 'tremolo', 'rate_hz': 1.0, 'depth': 0.0, 'pan_depth': 1.0})
        env = lambda c: np.array([rms(at(y, a, a + 0.02)[:, c]) for a in np.arange(0.1, 3.8, 0.02)])      # noqa: E731
        self.assertLess(np.corrcoef(env(0), env(1))[0, 1], -0.8)
        flat = run(x, {'type': 'tremolo', 'rate_hz': 1.0, 'depth': 0.0, 'pan_depth': 0.0})
        self.assertTrue(np.allclose(flat[:, 0], flat[:, 1]))

    def test_gate_pulse_closes_to_the_floor_and_opens_at_the_rate(self):
        x = sine(440, 4.0)
        y = run(x, {'type': 'gate_pulse', 'rate_hz': 2.0, 'duty': 0.5, 'floor_db': -40.0, 'smooth_ms': 5.0})
        self.assertAlmostEqual(rms(at(y, 0.05, 0.2)) / rms(at(x, 0.05, 0.2)), 1.0, delta=0.05)
        self.assertLess(rms(at(y, 0.3, 0.45)) / rms(at(x, 0.3, 0.45)), 0.03)
        env = np.array([rms(at(y, a, a + 0.02)) for a in np.arange(0.0, 3.98, 0.02)])
        opened = env > 0.5 * env.max()
        self.assertEqual(int(np.sum(opened[1:] & ~opened[:-1])), 7)             # 2 Hz over 4 s: eight pulses, the first has no rising edge

    def test_transient_shaper_sharpens_softens_and_zero_is_the_input(self):
        n = int(3 * SR)
        t = np.arange(n) / SR
        x = np.zeros((n, 2), np.float32)
        hit = np.random.default_rng(1).standard_normal(int(0.4 * SR)) * np.exp(-np.arange(int(0.4 * SR)) / (0.08 * SR))
        x[SR:SR + len(hit)] = (0.5 * hit)[:, None]
        sharp = run(x, {'type': 'transient', 'attack_db': 8.0, 'sustain_db': 0.0})
        soft = run(x, {'type': 'transient', 'attack_db': -8.0, 'sustain_db': 0.0})
        self.assertGreater(np.abs(sharp).max(), 1.15 * np.abs(x).max())
        self.assertLess(np.abs(soft).max(), 0.85 * np.abs(x).max())
        np.testing.assert_allclose(run(x, {'type': 'transient', 'attack_db': 0.0, 'sustain_db': 0.0}), x, atol=1e-6)
        del t


class TailEffects(unittest.TestCase):
    def click(self, at_s=3.0, secs=6.0):
        x = np.zeros((int(secs * SR), 2), np.float32)
        i = int(at_s * SR)
        x[i:i + 110] = (0.8 * np.hanning(110) * np.random.default_rng(3).standard_normal(110))[:, None]
        return x

    def test_the_reverse_swell_builds_before_the_note_and_a_short_one_barely_does(self):
        x = self.click()
        y = run(x, {'type': 'reverse_swell', 'decay_s': 1.5, 'wet_db': 0.0})
        self.assertEqual(rms(at(x, 2.0, 2.95)), 0.0)
        self.assertGreater(rms(at(y, 2.7, 2.95)), 1e-3)                        # the swell exists before the click
        self.assertGreater(rms(at(y, 2.7, 2.95)), 3 * rms(at(y, 2.0, 2.25)))   # and rises toward it
        short = run(x, {'type': 'reverse_swell', 'decay_s': 0.1, 'wet_db': 0.0})
        self.assertLess(rms(at(short, 2.0, 2.25)), 1e-4)
        self.assertTrue(np.array_equal(at(y, 0, 1.0), at(x, 0, 1.0)) or rms(at(y, 0, 1.0)) < 1e-9)

    def test_the_swell_level_follows_wet_db(self):
        x = self.click()
        loud = run(x, {'type': 'reverse_swell', 'wet_db': 0.0})
        quiet = run(x, {'type': 'reverse_swell', 'wet_db': -12.0})
        ratio = rms(at(loud, 2.5, 2.95)) / rms(at(quiet, 2.5, 2.95))
        self.assertAlmostEqual(20 * np.log10(ratio), 12.0, delta=1.0)

    def test_the_shimmer_tail_has_the_octave_and_without_feedback_it_does_not(self):
        t = np.arange(4 * SR) / SR
        x = np.zeros((4 * SR, 2), np.float32)
        x[:SR // 2] = (0.4 * np.sin(2 * np.pi * 440 * t[:SR // 2]))[:, None]

        def octave_share(feedback):
            y = run(x, {'type': 'shimmer', 'start_s': 0.0, 'end_s': 4.0, 'iterations': 3, 'feedback': feedback, 'wet_db': -3.0})
            seg = y[SR:3 * SR, 0]
            power = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
            f = np.fft.rfftfreq(len(seg), 1 / SR)
            return power[(f >= 860) & (f <= 900)].sum() / (power[(f >= 425) & (f <= 455)].sum() + 1e-30)
        self.assertLess(octave_share(0.0), 0.01)
        self.assertGreater(octave_share(0.6), 1.0)


class Host(unittest.TestCase):
    def test_a_builtin_pedalboard_plugin_runs_in_the_chain(self):
        x = sine(440, 1.0)
        y = run(x, {'type': 'pedalboard', 'plugin': 'Gain', 'params': {'gain_db': 6.0}})
        np.testing.assert_allclose(at(y, 0.1, 0.9), at(x, 0.1, 0.9) * 10 ** (6.0 / 20), atol=1e-5)      # past the 20 ms edge crossfade

    def test_a_plugin_off_the_allow_list_or_with_a_bad_argument_is_refused_before_a_render(self):
        self.assertTrue(any('not one of' in p for p in fx_engine.problems([{'type': 'pedalboard', 'plugin': 'Evil'}])))
        self.assertTrue(any('TypeError' in p or 'Error' in p for p in
                            fx_engine.problems([{'type': 'pedalboard', 'plugin': 'Gain', 'params': {'nonsense': 1}}])))
        self.assertTrue(any('"plugin" is required' in p for p in fx_engine.problems([{'type': 'pedalboard'}])))

    def test_an_external_plugin_needs_its_file(self):
        self.assertTrue(any('does not exist' in p for p in fx_engine.problems([{'type': 'external', 'path': '/no/such/plugin.vst3'}])))
        self.assertTrue(any('"path" is required' in p for p in fx_engine.problems([{'type': 'external'}])))

    def test_an_external_plugin_is_loaded_its_parameters_set_by_name_and_it_processes(self):
        class Fake:
            parameters = {'drive': object()}
            drive = 0.0

            def __call__(self, audio, sr):
                return audio * np.float32(0.5 + self.drive)
        fake = Fake()
        with tempfile.NamedTemporaryFile(suffix='.vst3') as fh, mock.patch('pedalboard.load_plugin', return_value=fake) as load:
            x = sine(440, 1.0)
            y = run(x, {'type': 'external', 'path': fh.name, 'params': {'drive': 0.25}})
            load.assert_called_once_with(fh.name)
            self.assertEqual(fake.drive, 0.25)
            np.testing.assert_allclose(at(y, 0.1, 0.9), at(x, 0.1, 0.9) * 0.75, atol=1e-6)
            with self.assertRaises(ValueError) as cm:
                run(x, {'type': 'external', 'path': fh.name, 'params': {'volume': 1.0}})
            self.assertIn("no parameter 'volume'", str(cm.exception))

    def test_board_has_the_pedalboard_call_shape(self):
        x = sine(440, 1.0)
        chain = [{'type': 'ring_mod', 'freq_hz': 100.0}]
        board = fx_engine.Board(chain, seed=3)
        out = board(np.ascontiguousarray(x.T), SR)
        self.assertEqual(out.shape, (2, len(x)))
        np.testing.assert_allclose(out.T, fx_engine.apply(x, SR, chain, seed=3), atol=1e-7)
        mono = board(x[:, 0], SR)
        self.assertEqual(mono.shape, (len(x),))
        with self.assertRaises(ValueError):
            fx_engine.Board([{'type': 'nope'}])


class InTheMix(unittest.TestCase):
    def test_a_track_spec_carries_the_chain_written_out(self):
        import mixer
        spec_ = mixer.default_spec(dict(name='pad', instrument='warm_pad', role='pad', fx='tape_stop_out'))
        self.assertEqual([e['type'] for e in spec_['fx']], ['tape_stop'])
        self.assertEqual(spec_['fx'][0]['dur_s'], 1.2)                              # every parameter, defaults included

    def test_a_named_chain_that_changes_changes_the_spec_and_so_the_cache_key(self):
        import mixer
        from mix_engine import chains
        x = sine(300, 1.0)
        mx = mixer._mix()
        a = mixer.default_spec(dict(name='p', instrument='warm_pad', role='pad', fx=[{'type': 'tape_stop', 'dur_s': 1.0}]))
        b = mixer.default_spec(dict(name='p', instrument='warm_pad', role='pad', fx=[{'type': 'tape_stop', 'dur_s': 2.0}]))
        self.assertNotEqual(chains._chain_key('p', x, a, mx, SR, len(x)), chains._chain_key('p', x, b, mx, SR, len(x)))

    def test_an_invalid_chain_stops_the_mix_with_its_problems(self):
        import mixer
        with self.assertRaises(ValueError) as cm:
            mixer.default_spec(dict(name='pad', instrument='warm_pad', role='pad', fx=[{'type': 'tape_stop', 'dur_s': 0}]))
        self.assertIn('below the minimum', str(cm.exception))

    def test_process_chain_applies_the_chain_and_a_stem_without_one_is_untouched(self):
        import mixer
        x = sine(300, 4.0, 0.2)
        plain = mixer.process_chain('pad', x, mixer.default_spec(dict(name='pad', instrument='warm_pad', role='pad')), sr=SR)
        cut = mixer.process_chain('pad', x, mixer.default_spec(dict(name='pad', instrument='warm_pad', role='pad',
                                                                    fx=[{'type': 'tape_stop', 'start_s': 1.0, 'dur_s': 0.5}])), sr=SR)
        self.assertEqual(float(np.max(np.abs(at(cut, 1.6, 4.0)))), 0.0)
        self.assertGreater(float(np.max(np.abs(at(plain, 1.6, 4.0)))), 1e-3)
        np.testing.assert_allclose(at(cut, 0, 0.95), at(plain, 0, 0.95), atol=1e-6)

    def test_the_engine_is_in_the_processed_stem_code_identity(self):
        import inspect
        from mix_engine import chains
        self.assertIn("'fx_engine'", inspect.getsource(chains._code_tag))

    def test_fx_is_a_mix_key_so_a_chain_edit_does_not_redraw_the_dry_stems(self):
        import stem_cache
        self.assertIn('fx', stem_cache.MIX_KEYS)
        self.assertNotIn('fx', stem_cache.dry_track({'name': 'a', 'fx': 'x', 'notes': []}))
        self.assertIn('notes', stem_cache.dry_track({'name': 'a', 'fx': 'x', 'notes': []}))


class Separation(unittest.TestCase):
    """Sound design lives in the preset: the score may not carry a chain, and a preset's chain wins over a stale one."""

    def setUp(self):
        self._roots = list(presets.PROJECT_ROOTS)         # project_gate registers the project it is given and never removes it

    def tearDown(self):
        presets.PROJECT_ROOTS[:] = self._roots

    def test_the_project_gate_blocks_an_fx_chain_written_in_the_score(self):
        import project_gate
        with tempfile.TemporaryDirectory() as d:
            score = {'tracks': [{'name': 'pad', 'instrument': 'warm_pad', 'role': 'pad', 'notes': [], 'fx': 'tape_stop_out'}]}
            found = project_gate.track_problems(score, d)
            self.assertTrue(any('effects chain' in p and 'not in the score' in p for p in found), found)
            clean = project_gate.track_problems({'tracks': [{'name': 'pad', 'instrument': 'warm_pad', 'role': 'pad', 'notes': []}]}, d)
            self.assertFalse(any('effects chain' in p for p in clean))

    def test_a_preset_chain_replaces_the_one_a_track_already_carries(self):
        import pipeline
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'instruments'))
            with open(os.path.join(d, 'instruments', 'warm_pad.json'), 'w', encoding='utf-8') as fh:
                json.dump({'name': 'warm_pad', 'fx': 'riser_sweep'}, fh)
            track = {'name': 'pad', 'instrument': 'warm_pad', 'fx': 'tape_stop_out', 'notes': []}
            out = pipeline.MusicPipeline(verbose=False).adopt_presets({'tracks': [track]}, presets_dir=d, project_dir=d)
            self.assertEqual(out['tracks'][0]['fx'], 'riser_sweep')


class Preflight(unittest.TestCase):
    def rows(self, score, lookup=lambda k, n: None):
        import preflight_lint
        return [r for r in preflight_lint.fx_rows(score, lookup)]

    def test_a_valid_chain_passes_and_an_invalid_one_fails_with_every_problem(self):
        ok = {'tracks': [{'name': 'pad', 'instrument': 'warm_pad', 'role': 'pad', 'notes': [], 'fx': 'riser_sweep'}]}
        self.assertEqual([r[0] for r in self.rows(ok)], ['PASS'])
        bad = {'tracks': [{'name': 'pad', 'instrument': 'warm_pad', 'role': 'pad', 'notes': [],
                           'fx': [{'type': 'tape_stop', 'dur_s': 0}, {'type': 'nope'}]}]}
        rows = self.rows(bad)
        self.assertEqual([r[0] for r in rows], ['FAIL'])
        self.assertIn('below the minimum', rows[0][2])
        self.assertIn("unknown effect 'nope'", rows[0][2])

    def test_the_chain_in_the_preset_is_read_too_and_a_track_without_fx_has_no_row(self):
        score = {'tracks': [{'name': 'pad', 'instrument': 'warm_pad', 'role': 'pad', 'notes': []}]}
        self.assertEqual(self.rows(score), [])
        rows = self.rows(score, lookup=lambda kind, name: {'fx': [{'type': 'tape_stop', 'dur_s': 0}]})
        self.assertEqual([r[0] for r in rows], ['FAIL'])

    def test_the_rule_is_in_the_preflight_table(self):
        import lint_coverage
        self.assertIn('preflight.fx', lint_coverage.PREFLIGHT_ROWS)


if __name__ == '__main__':
    unittest.main()
