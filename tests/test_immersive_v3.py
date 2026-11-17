# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Immersive 3.0: every channel count from one mix, and the rows that compare them.

Each gate row here is run with a control that must pass and a control that must fail: a row that cannot fail is not
a row. Nothing in this file listens; the assertions are on levels, spectra, channel counts and file structure.

Run: python -m unittest tests.test_immersive_v3
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import compute                 # noqa: E402
import loudness                # noqa: E402
import mix_schema              # noqa: E402
import mixer                   # noqa: E402
import render_targets          # noqa: E402
import spatial_gate            # noqa: E402
from spatial_engine import config, master, pan  # noqa: E402
from spatial_engine import render as srender    # noqa: E402

SR = 44100


def _tone(hz, seconds=6.0, amp=0.2, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def _noise(seconds=6.0, amp=0.1, seed=0, sr=SR):
    return (amp * np.random.default_rng(seed).standard_normal(int(seconds * sr))).astype(np.float32)


def _score(tracks, targets=('stereo',), **kw):
    s = {'bpm': 90, 'room': 'none', 'space': 'none', 'output_targets': list(targets), 'master': {},
         'tracks': [dict(notes=[{'t': 0, 'd': 8, 'p': 60}], **t) for t in tracks]}
    s.update(kw)
    return s


class Loudness(unittest.TestCase):
    def test_same_as_the_stereo_meter(self):
        x = np.stack([_tone(440, 8.0), _noise(8.0)], 1)
        self.assertAlmostEqual(loudness.integrated(x, SR), mixer.lufs(x, SR), places=3)

    def test_full_scale_sine_reads_minus_three(self):
        self.assertAlmostEqual(loudness.integrated(_tone(997, 5.0, 1.0), SR), -3.01, delta=0.06)

    def test_low_frequency_channel_is_left_out_and_surrounds_weigh_more(self):
        lay = 'itu_bs2051_system_b'
        names = config.channel_names(lay)
        w = loudness.weights_for(lay)
        self.assertEqual(w[names.index('LFE')], 0.0)
        self.assertAlmostEqual(10 * np.log10(w[names.index('SL')] / w[names.index('FL')]), 1.5, places=6)
        n = SR * 5
        front, surround, sub = (np.zeros((n, len(names)), np.float32) for _ in range(3))
        front[:, names.index('FL')] = _tone(1000, 5.0)
        surround[:, names.index('SL')] = _tone(1000, 5.0)
        sub[:, names.index('LFE')] = _tone(60, 5.0, 0.9)
        self.assertAlmostEqual(loudness.layout_lufs(surround, lay, SR) - loudness.layout_lufs(front, lay, SR), 1.5, delta=0.01)
        self.assertEqual(loudness.layout_lufs(sub, lay, SR), loudness.SILENCE)

    def test_one_pass_series_matches_filtering_each_window(self):
        x = np.stack([_tone(300, 12.0) * np.linspace(0.1, 1.0, SR * 12, dtype=np.float32), _noise(12.0)], 1)
        new = loudness.Blocks(x, SR).gated_series(3.0, 0.5)
        n, hop = 3 * SR, SR // 2
        old = [mixer.lufs(x[i:i + n], SR) for i in range(0, len(x) - n + 1, hop)]
        self.assertEqual(len(new), len(old))
        self.assertLess(float(np.max(np.abs(np.array(new) - np.array(old)))), 0.1)


class Limiter(unittest.TestCase):
    CFG = dict(lookahead_ms=5.0, release_ms=120.0, oversample=4)

    def _programme(self):
        rng = np.random.default_rng(3)
        x = np.zeros((SR * 6, 6), np.float32)
        for c in range(6):
            x[:, c] = _tone(100 + 70 * c, 6.0, 0.05)
            for k in rng.integers(0, len(x) - 2000, 20):
                x[k:k + 800, c] += (0.9 * np.exp(-np.arange(800) / 120.0) * np.sin(np.arange(800) * 0.9)).astype(np.float32)
        return x

    def test_every_channel_ends_under_the_ceiling(self):
        x = self._programme()
        self.assertGreater(max(master.channel_peaks(x, SR)), -3.0)
        y, depth = master.limit(x, SR, -3.0, self.CFG)
        self.assertLessEqual(max(master.channel_peaks(y, SR)), -3.0 + 0.05)
        self.assertGreater(depth, 0.5)

    def test_one_gain_for_all_channels(self):
        x = self._programme()
        y, _ = master.limit(x, SR, -3.0, self.CFG)
        m = (np.abs(x[:, 0]) > 1e-3) & (np.abs(x[:, 4]) > 1e-3)
        self.assertLess(float(np.max(np.abs(y[m, 0] / x[m, 0] - y[m, 4] / x[m, 4]))), 1e-4)

    def test_a_quiet_programme_is_not_touched(self):
        x = 0.01 * self._programme()
        y, depth = master.limit(x, SR, -3.0, self.CFG)
        self.assertEqual(depth, 0.0)
        np.testing.assert_array_equal(x, y)

    def test_the_reduction_bound_keeps_dynamics_and_says_so(self):
        x = self._programme() * 0.05                      # far below the target: reaching it needs heavy limiting
        target = dict(config.target('immersive_5_1'))
        target['limiter'] = dict(target['limiter'], max_reduction_db=1.0)
        master.master(x, {'master': {'lufs': -10.0}}, target, SR)
        self.assertLessEqual(master.REPORT['limiter_depth_db'], 1.0 + 0.3)
        self.assertLess(master.REPORT['reached_lufs'], -10.0 - 1.0)   # under the target, reported, not flattened

    def test_no_limiter_block_is_the_old_scalar_trim(self):
        x = self._programme()
        target = {k: v for k, v in config.target('immersive_5_1').items() if k not in ('limiter', 'loudness')}
        y = master.master(x, {'master': {'lufs': -14.0}}, target, SR)
        self.assertEqual(master.REPORT['method'], 'stereo_fold')
        self.assertFalse(master.REPORT['limiter'])
        self.assertLessEqual(max(master.channel_peaks(y, SR)), -3.0 + 0.05)


class Layouts(unittest.TestCase):
    NEW = {'immersive_5_1': 6, 'immersive_5_1_2': 8, 'immersive_5_1_4': 10}

    def test_presets_are_sound(self):
        self.assertEqual(render_targets.manifest_problems(), [])
        self.assertEqual(config.problems(), [])
        for name, ch in self.NEW.items():
            self.assertEqual(render_targets.channels(name), ch)
            self.assertTrue(render_targets.buildable(name))

    def test_panning_keeps_unit_power_everywhere(self):
        for name in self.NEW:
            spk = config.speakers(config.target(name)['layout'])
            for az in range(-180, 180, 15):
                for el in (0, 30, 60, 90):
                    g = pan.gains(az, el, spk)
                    self.assertAlmostEqual(sum(v * v for v in g.values()), 1.0, places=6, msg=f'{name} {az} {el}')
                    self.assertGreaterEqual(min(g.values()), -1e-9)

    def test_same_channel_count_is_told_apart_by_file_name(self):
        score = _score([dict(name='a', role='melody', instrument='flute')],
                       targets=('stereo', 'immersive_7_1', 'immersive_5_1_2'))
        self.assertEqual(sorted(spatial_gate.targets_for(score, 8)), ['immersive_5_1_2', 'immersive_7_1'])
        self.assertEqual(spatial_gate.targets_for(score, 8, '/x/out/_draft_master_5_1_2.wav'), ['immersive_5_1_2'])
        self.assertEqual(spatial_gate.targets_for(score, 8, '/x/out/master_7_1.wav'), ['immersive_7_1'])

    def test_ambix_has_the_channels_it_promises(self):
        tgt = config.target('ambix')
        self.assertEqual((int(tgt['ambisonic_order']) + 1) ** 2, tgt['channels'])
        score = _score([dict(name='a', role='melody', instrument='flute',
                             spatial=dict(azimuth=30.0, elevation=10.0, distance=2.0))])
        field = srender.hoa_mix(score, {'a': np.stack([_tone(440, 3.0)] * 2, 1)}, tgt, SR)
        self.assertEqual(field.shape[1], tgt['channels'])

    def test_a_panned_track_reaches_its_side_of_a_layout(self):
        stems = {'a': np.stack([_tone(440, 3.0)] * 2, 1)}
        order = config.target('immersive_5_1')['channel_order']
        for pan_value, loud, quiet in ((-1.0, 'FL', 'FR'), (1.0, 'FR', 'FL')):
            score = _score([dict(name='a', role='melody', instrument='flute', pan=pan_value)])
            y = srender.spatial_mix(score, stems, 'immersive_5_1', SR)
            lv = {n: 10 * np.log10(np.mean(y[:, i] ** 2) + 1e-20) for i, n in enumerate(order)}
            self.assertGreater(lv[loud], lv['FC'] + 20.0)
            self.assertGreater(lv[loud], lv[quiet] + 20.0)


class Mono(unittest.TestCase):
    def _levels(self, pan_value):
        """(rendered mono level, level of the stereo mix summed to one channel) for one track at a pan, in dB."""
        stems = {'a': np.stack([_tone(440, 3.0)] * 2, 1)}
        score = _score([dict(name='a', role='melody', instrument='flute', pan=pan_value, chain='none')])
        bus = srender.MonoBus(SR, {'compensate_max_db': 3.0})
        mono = mixer.mix_stems(score, stems, SR, bus=bus)[:, 0]
        st = mixer.mix_stems(score, stems, SR)
        db = lambda v: 10 * np.log10(np.mean(np.square(v)) + 1e-20)     # noqa: E731
        return db(mono), db(0.5 * (st[:, 0] + st[:, 1]))

    def test_rendered_mono_does_not_depend_on_pan_but_the_fold_does(self):
        centre_r, centre_f = self._levels(0.0)
        side_r, side_f = self._levels(-1.0)
        self.assertAlmostEqual(side_r, centre_r, delta=0.05)          # rendered: the same level wherever it sat
        self.assertAlmostEqual(centre_f, centre_r, delta=0.05)        # a centred part folds without loss
        self.assertAlmostEqual(side_f, centre_f - 3.01, delta=0.1)    # a hard-panned part folds 3 dB down

    def test_unrelated_channels_get_their_three_db_back_and_no_more(self):
        bus = srender.MonoBus(SR, {'compensate_max_db': 3.0})
        l, r = _noise(4.0, seed=1), _noise(4.0, seed=2)
        got = bus._one('bed', np.stack([l, r], 1))
        self.assertAlmostEqual(10 * np.log10(np.mean(got ** 2) / np.mean(l ** 2)), 0.0, delta=0.2)
        cancelling = bus._one('wide', np.stack([l, -0.98 * l], 1))     # nearly out of phase: not rescued
        self.assertLessEqual(bus.compensation['wide'], 3.0)
        self.assertLess(10 * np.log10(np.mean(cancelling ** 2) / np.mean(l ** 2)), -25.0)

    def test_identical_channels_are_not_changed(self):
        bus = srender.MonoBus(SR, {'compensate_max_db': 3.0})
        x = _tone(300, 2.0)
        np.testing.assert_allclose(bus._one('a', np.stack([x, x], 1)), x, atol=1e-6)

    def test_deliverable_is_one_channel_under_its_ceiling(self):
        stems = {'a': np.stack([_tone(440, 4.0)] * 2, 1), 'b': np.stack([_noise(4.0, seed=1), _noise(4.0, seed=2)], 1)}
        score = _score([dict(name='a', role='melody', instrument='flute', pan=-0.8),
                        dict(name='b', role='pad', instrument='strings', pan=0.6)], targets=('stereo', 'mono'))
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            path = os.path.join(d, render_targets.filename('mono'))
            srender.render_deliverable(score, stems, 'mono', path)
            rows = []
            spatial_gate.output_rows(score, path, rows)
        self.assertNotIn('FAIL', [r[0] for r in rows], rows)
        self.assertIn('delivery.true_peak', [r[1] for r in rows])


class FoldRows(unittest.TestCase):
    """fold.mono and fold.timbre, each with a control that passes and one that fails."""

    def _write(self, d, name, audio):
        import soundfile as sf
        path = os.path.join(d, name)
        sf.write(path, audio, SR, subtype='PCM_24')
        return path

    def _rows(self, score, primary, extra, target):
        rows = []
        spatial_gate.fold_rows(score, primary, extra, target, rows)
        return {name: level for level, name, _ in rows}

    def test_fold_mono_passes_and_fails(self):
        score = _score([dict(name='a', role='melody', instrument='flute')], targets=('stereo', 'mono'))
        low, high = _noise(6.0, 0.1, 1), _noise(6.0, 0.1, 2)
        from scipy import signal
        lo = signal.sosfilt(signal.butter(4, 800, 'low', fs=SR, output='sos'), low).astype(np.float32)
        hi = signal.sosfilt(signal.butter(4, 800, 'high', fs=SR, output='sos'), high).astype(np.float32)
        mono = lo + hi
        with tempfile.TemporaryDirectory() as d:
            m = self._write(d, 'master_mono.wav', mono[:, None])
            good = self._write(d, 'master.wav', np.stack([mono, mono], 1))
            self.assertEqual(self._rows(score, good, m, 'mono'), {'fold.mono': 'PASS'})
            # the high band is out of phase between the two channels: it vanishes when they are added
            bad = self._write(d, 'bad.wav', np.stack([lo + hi, lo - hi], 1))
            self.assertEqual(self._rows(score, bad, m, 'mono'), {'fold.mono': 'FAIL'})

    def test_fold_timbre_passes_and_fails(self):
        score = _score([dict(name='a', role='melody', instrument='flute')], targets=('stereo', 'immersive_5_1'))
        order = config.target('immersive_5_1')['channel_order']
        x = _noise(6.0, 0.1, 5)
        from scipy import signal
        dull = signal.sosfilt(signal.butter(4, 600, 'low', fs=SR, output='sos'), x).astype(np.float32)
        with tempfile.TemporaryDirectory() as d:
            st = self._write(d, 'master.wav', np.stack([x, x], 1))
            same, lost = (np.zeros((len(x), len(order)), np.float32) for _ in range(2))
            same[:, order.index('FL')] = x
            same[:, order.index('FR')] = x
            lost[:, order.index('FL')] = dull
            lost[:, order.index('FR')] = dull
            self.assertEqual(self._rows(score, st, self._write(d, 'master_5_1.wav', same), 'immersive_5_1'),
                             {'fold.timbre': 'PASS'})
            self.assertEqual(self._rows(score, st, self._write(d, 'dull.wav', lost), 'immersive_5_1'),
                             {'fold.timbre': 'FAIL'})

    def test_no_stereo_master_first_is_said_not_assumed(self):
        score = _score([dict(name='a', role='melody', instrument='flute')], targets=('binaural', 'mono'))
        rows = []
        spatial_gate.fold_rows(score, 'missing.wav', 'missing.wav', 'mono', rows)
        self.assertEqual([(r[0], r[1]) for r in rows], [('WARN', 'fold.reference')])


class MixPresetData(unittest.TestCase):
    """Numbers that used to be literals in mixer.py and are read from the mix preset now."""

    def tearDown(self):
        mixer.reset_context()

    def test_defaults_validate(self):
        self.assertEqual(mix_schema.validate(mix_schema.with_defaults({})), [])

    def test_a_project_can_define_its_own_master_tone(self):
        x = np.stack([_noise(5.0, 0.05, 1), _noise(5.0, 0.05, 2)], 1)
        base = mixer.master_chain(x, {'tone': 'neutral', 'glue': False}, SR)
        mx = mix_schema.with_defaults({'mastering': {'tones': {'airless': [{'type': 'lp', 'f': 1500}]}}})
        mixer._install(mx)
        dark = mixer.master_chain(x, {'tone': 'airless', 'glue': False}, SR)
        import dsp
        self.assertLess(dsp.band_db(dark, SR, 6000, 12000) - dsp.band_db(dark, SR, 200, 800),
                        dsp.band_db(base, SR, 6000, 12000) - dsp.band_db(base, SR, 200, 800) - 12.0)

    def test_an_unlisted_tone_masters_neutral_and_says_so(self):
        x = np.stack([_noise(4.0, 0.05, 1), _noise(4.0, 0.05, 2)], 1)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            odd = mixer.master_chain(x, {'tone': 'no_such_tone'}, SR)
        np.testing.assert_array_equal(odd, mixer.master_chain(x, {'tone': 'neutral'}, SR))
        self.assertIn('no_such_tone', err.getvalue())

    def test_send_by_role_reaches_the_role(self):
        tr = dict(role='bass', instrument='no_such_instrument_xyz')
        self.assertEqual(mixer.default_spec(tr)['reverb'], 0.18)
        mixer._install(mix_schema.with_defaults({'space': {'send_by_role': {'bass': 0.0}}}))
        self.assertEqual(mixer.default_spec(tr)['reverb'], 0.0)
        self.assertEqual(mixer.default_spec(dict(tr, reverb=0.4))['reverb'], 0.4)      # the track still wins


class MixBehaviour(unittest.TestCase):
    def tearDown(self):
        mixer.reset_context()

    def _piece(self):
        stems = {'lead': np.stack([_tone(1000, 4.0, 0.3)] * 2, 1),
                 'bed': np.stack([_noise(4.0, 0.2, 1), _noise(4.0, 0.2, 2)], 1)}
        score = _score([dict(name='lead', role='melody', instrument='flute', chain='none'),
                        dict(name='bed', role='pad', instrument='strings', chain='none')])
        return score, stems

    def _ctx(self, mix):
        import mix_context
        return mix_context.MixContext(mix_schema.with_defaults(mix), {}, name='test')

    def test_stems_in_threads_give_the_same_samples(self):
        score, stems = self._piece()
        one = mixer.mix_stems(score, stems, SR, ctx=self._ctx({'render': {'mix_workers': 1}}))
        many = mixer.mix_stems(score, stems, SR, ctx=self._ctx({'render': {'mix_workers': 4}}))
        np.testing.assert_array_equal(one, many)

    def test_mix_intent_drives_the_carve_only_when_asked(self):
        import dsp
        score, stems = self._piece()
        score['mix_intent'] = {'hero': 'lead', 'leave_free_hz': [700, 1400]}
        carve = dict(enabled=True, ratio=8.0, threshold_db=-50.0, roles=['pad'])
        mixer.mix_stems(score, stems, SR, ctx=self._ctx({'lead_carve': carve}))
        self.assertEqual(mixer.STATE['mix_intent_used'], {})
        ignored = dsp.band_db(mixer.STATE['processed']['bed'], SR, 800, 1300)
        mixer.mix_stems(score, stems, SR, ctx=self._ctx({'lead_carve': dict(carve, from_intent=True)}))
        self.assertEqual(mixer.STATE['mix_intent_used'], {'hero': 'lead', 'leave_free_hz': [700.0, 1400.0]})
        used = dsp.band_db(mixer.STATE['processed']['bed'], SR, 800, 1300)
        self.assertLess(used, ignored - 1.0)          # the bed gives way in the band the sheet asked to keep free


class Compute(unittest.TestCase):
    def tearDown(self):
        os.environ.pop(compute.ENV, None)
        compute.configure(None)

    def test_convolution_matches_scipy(self):
        from scipy import signal
        rng = np.random.default_rng(0)
        x, h = rng.standard_normal((5000, 2)), rng.standard_normal((300, 2))
        want = np.stack([signal.fftconvolve(x[:, c], h[:, c]) for c in range(2)], 1)
        np.testing.assert_allclose(compute.fftconvolve(x, h), want, atol=1e-9)
        np.testing.assert_allclose(compute.fftconvolve(x[:, 0], h[:, 0], 'same'), want[:5000, 0], atol=1e-9)
        np.testing.assert_allclose(compute.fftconvolve(x, h[:, 0]), np.stack(
            [signal.fftconvolve(x[:, c], h[:, 0]) for c in range(2)], 1), atol=1e-9)

    def test_the_gpu_kernel_agrees_with_the_cpu_one(self):
        """The kernel a GPU runs, on torch's CPU device: the same arithmetic in float32. Skipped without torch."""
        try:
            import torch  # noqa: F401
        except ImportError:
            self.skipTest('torch is not installed')
        from scipy import signal
        rng = np.random.default_rng(1)
        x, h = rng.standard_normal((20000, 2)), rng.standard_normal((2000, 2))
        want = np.stack([signal.fftconvolve(x[:, c], h[:, c]) for c in range(2)], 1)
        got = compute._torch_conv(x, h, len(want), 'cpu')
        err = 20 * np.log10(np.max(np.abs(got - want)) / np.max(np.abs(want)))
        self.assertLess(err, -90.0)                     # float32 against float64: far below a 24-bit file's floor

    def test_asking_for_a_device_that_is_not_there_falls_back_and_says_so(self):
        try:
            import torch
            if torch.cuda.is_available():
                self.skipTest('this machine has a CUDA device')
        except ImportError:
            pass
        info = compute.configure('cuda')
        self.assertEqual((info['backend'], info['device']), ('numpy', 'cpu'))
        self.assertTrue(info['fallback'])
        self.assertEqual(compute.cache_tag(), 'cpu')

    def test_auto_on_a_cpu_machine_is_silent(self):
        try:
            import torch
            if torch.cuda.is_available() or torch.backends.mps.is_available():
                self.skipTest('this machine has a GPU')
        except ImportError:
            pass
        info = compute.configure('auto')
        self.assertEqual(info['device'], 'cpu')
        self.assertIsNone(info['fallback'])

    def test_environment_variable_wins_and_an_unknown_name_is_reported(self):
        os.environ[compute.ENV] = 'quantum'
        info = compute.configure('auto')
        self.assertEqual(info['device'], 'cpu')
        self.assertIn('quantum', info['fallback'])

    def test_render_compute_is_a_valid_mix_preset_section(self):
        self.assertEqual(mix_schema.validate({'render': {'compute': {'device': 'auto'}}}), [])
        self.assertTrue(mix_schema.validate({'render': {'compute': {'device': 'abacus'}}}))


class StereoDecodeAndMemory(unittest.TestCase):
    """The stereo master can be decoded for loudspeakers, the master high-pass can be steeper, and a many-channel file
    is measured one channel at a time."""

    def test_stereo_decode_is_a_preset_choice_with_two_values(self):
        self.assertEqual(mix_schema.validate({'immersive': {'stereo_decode': 'speakers'}}), [])
        self.assertEqual(mix_schema.validate({'immersive': {'stereo_decode': 'binaural'}}), [])
        self.assertTrue(mix_schema.validate({'immersive': {'stereo_decode': 'surround'}}))

    def test_the_stereo_pair_layout_is_a_decode_only_layout(self):
        from spatial_engine import config
        self.assertEqual(config.problems('stereo_bs775'), [])
        self.assertEqual([s['name'] for s in config.speakers('stereo_bs775')], ['L', 'R'])

    def test_highpass_order_is_bounded_and_defaults_to_one(self):
        self.assertEqual(mix_schema.with_defaults({})['mastering']['highpass_order'], 1)
        self.assertEqual(mix_schema.validate({'mastering': {'highpass_order': 3}}), [])
        self.assertTrue(mix_schema.validate({'mastering': {'highpass_order': 9}}))

    def test_true_peak_by_channel_matches_the_whole_file_upsample(self):
        from scipy.signal import resample_poly
        from gate_audio import Signal
        rng = np.random.default_rng(5)
        a = (0.3 * rng.standard_normal((44100, 4))).astype(np.float32)
        want = 20.0 * np.log10(np.max(np.abs(resample_poly(a, 4, 1, axis=0)), axis=0) + 1e-12)
        np.testing.assert_allclose(Signal(a, 44100).true_peak_by_channel, want, atol=1e-4)


if __name__ == '__main__':
    unittest.main()
