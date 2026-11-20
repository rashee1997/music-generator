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

"""One test per defect found by the engine audit. Each fails on the code as it was and passes on the fix."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'tests'))

import compose
import dsp
import gate_checks as gc
import mixer
import sfx
import sound_model
import theory
import vocals


class Theory(unittest.TestCase):
    def test_diminished_seventh_has_no_added_dominant_seventh(self):
        tones = theory.Key('C', 'major').chord('viidim7')['tones']
        self.assertEqual(tones, [0, 3, 6, 9])

    def test_five_note_modes_can_voice_a_seventh_degree_chord(self):
        for mode in ('ethiopian_bati', 'ethiopian_tizita_maj'):
            tones = theory.Key('C', mode).chord('VII')['tones']
            self.assertTrue(tones, mode)

    def test_a_mode_too_short_for_the_degree_says_which_mode(self):
        theory.MODES['_four_notes'] = [0, 3, 6, 9]
        try:
            with self.assertRaises(ValueError) as cm:
                theory.Key('C', '_four_notes').chord('VII')
            self.assertIn('_four_notes', str(cm.exception))
        finally:
            del theory.MODES['_four_notes']


class KeyParsing(unittest.TestCase):
    def test_minor_suffix_on_flat_and_sharp_tonics(self):
        self.assertEqual(compose.split_minor_suffix('Bbm'), ('Bb', 'aeolian'))
        self.assertEqual(compose.split_minor_suffix('C#m'), ('C#', 'aeolian'))
        self.assertEqual(compose.split_minor_suffix('Am'), ('A', 'aeolian'))
        self.assertEqual(compose.split_minor_suffix('F#minor'), ('F#', 'aeolian'))

    def test_a_major_tonic_is_left_alone(self):
        for t in ('C', 'Bb', 'F#', 'D'):
            self.assertEqual(compose.split_minor_suffix(t), (t, None))


class SoundModels(unittest.TestCase):
    def test_free_bar_overtones_follow_the_stated_law(self):
        r = sound_model.mode_ratios(dict(n=8, law='bar'))
        want = [1.0, 2.757, 5.404, 8.933, 13.34] + [((2 * n + 1) / 3.0) ** 2 for n in (6, 7, 8)]
        np.testing.assert_allclose(r, want, rtol=1e-9)
        self.assertTrue(np.all(np.diff(r) > 0))

    def test_sweeps_are_integrated_phase_not_frequency_times_time(self):
        sr = 22050
        rng = np.random.default_rng(3)
        got = sfx.impact(0.8, sr, rng)
        rng = np.random.default_rng(3)
        t = sfx._t(0.8, sr)
        f = 48 - 14 * np.minimum(t, 0.4) / 0.4
        sub = np.sin(np.cumsum(2 * np.pi * f / sr)) * sfx._decay(t, 0.9)
        crack = sfx._lp(sfx._noise(rng, len(t)), 3500, sr) * sfx._decay(t, 0.05)
        np.testing.assert_allclose(got, sub + 0.6 * crack, atol=1e-9)

    def test_a_brittle_material_fails_with_brittle_timing(self):
        from phys_core import fracture, vegetation
        seen = []
        real = fracture.crack_train

        def spy(material, energy_j, rng, brittle=False):
            seen.append(brittle)
            return real(material, energy_j, rng, brittle=brittle)
        fracture.crack_train = spy
        try:
            vegetation.failure_stages(dict(family='brittle'), 1.0)
        finally:
            fracture.crack_train = real
        self.assertEqual(seen, [True])


class Vocals(unittest.TestCase):
    def test_voiced_consonant_in_a_named_register_style_renders(self):
        ev = [dict(t=0.0, dur=0.6, p=57, v=90, style='tuvan_kargyraa', consonant='m', vowel='a')]
        out = vocals.render_choir(ev, voices=1)
        sig = out[0] if isinstance(out, tuple) else out
        self.assertTrue(np.isfinite(np.asarray(sig)).all())


class Mixer(unittest.TestCase):
    def test_dither_lands_on_the_target_bit_grid(self):
        x = np.random.default_rng(1).uniform(-0.5, 0.5, (4000, 2))
        y = mixer.apply_dither(x, bits=16).astype(np.float64)
        steps = y * 32768.0
        np.testing.assert_allclose(steps, np.round(steps), atol=1e-6)

    def test_finalized_16_bit_master_is_dithered_last(self):
        sr = 44100
        x = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr))[:, None].repeat(2, 1)
        out, subtype = mixer.finalize_pcm(x, sr, {'dither': {'bits': 16, 'shape': 'tpdf'}})
        self.assertEqual(subtype, 'PCM_16')
        steps = out.astype(np.float64) * 32768.0
        np.testing.assert_allclose(steps, np.round(steps), atol=1e-6)

    def test_wrap_loop_crossfade_is_continuous_at_both_ends(self):
        sr = 8000
        n, tail = 4 * sr, sr // 2
        x = np.zeros((n + tail, 2), np.float32)
        x[n:] = 1.0                                   # a constant tail on a silent body
        out = mixer.wrap_loop(x, 4.0, sr)
        xf = int(0.035 * sr)
        k = tail
        self.assertAlmostEqual(float(out[k - xf - 1, 0]), 1.0, places=5)
        self.assertAlmostEqual(float(out[k, 0]), 0.0, places=5)
        self.assertLess(float(np.max(np.abs(np.diff(out[:k + 5, 0])))), 2.5 / xf)

    def test_duck_gain_is_finite_for_a_zero_threshold(self):
        src = np.zeros((2000, 2), np.float32)
        src[500:1000] = 0.5
        g = mixer.duck_gain(src, 2000, depth_db=-12, thresh=0.0, sr=8000)
        self.assertTrue(np.isfinite(g).all())
        self.assertLess(float(g.min()), 0.5)

    def test_pedalboard_engine_runs_the_compressor_once(self):
        calls = []
        real = dsp.compressor

        def spy(x, *a, **k):
            calls.append(1)
            return real(x, *a, **k)
        dsp.compressor = spy
        try:
            x = (0.4 * np.random.default_rng(2).standard_normal((4000, 2))).astype(np.float32)
            dyn = {'engine': 'pedalboard', 'comp': {'thr': -20, 'ratio': 3.0}, 'parallel': 0.5}
            mixer._dsp_dynamics(x, dyn, 8000, comp_done=True)
        finally:
            dsp.compressor = real
        self.assertEqual(calls, [])


class Gate(unittest.TestCase):
    def test_a_skipped_section_check_is_info_not_pass(self):
        class Sig:
            dur = 10.0
        score = {'bpm': 120, 'ts': [4, 4], 'plan': {'sections': [
            {'name': 'a', 'start_s': 0.0, 'end_s': 5.0}, {'name': 'b', 'start_s': 5.0, 'end_s': 10.0}]}}
        res = gc.section_energy(Sig(), score, None)
        self.assertTrue(res.get('skipped'))
        self.assertEqual(res.get('level'), 'INFO')

    def test_flag_limit_can_tighten_but_never_loosen_the_profile(self):
        import quality_gate as qg

        class GP:
            @staticmethod
            def param(row, key):
                return 8
        self.assertEqual(qg.flags_limit({}, GP), 8)
        self.assertEqual(qg.flags_limit({'pattern_flags_max': 1}, GP), 1)
        self.assertEqual(qg.flags_limit({'pattern_flags_max': 1000}, GP), 8)
        self.assertEqual(qg.flags_limit({'quality': {'pattern_flags_max': 99}}, GP), 8)

    def test_correlation_of_a_silent_channel_is_not_a_pass(self):
        import spatial_gate as sg
        a = np.random.default_rng(0).standard_normal(1000)
        self.assertFalse(np.isfinite(sg.channel_correlation(a, np.zeros(1000))))
        level, _ = sg.correlation_verdict(float('nan'), 0.0)
        self.assertEqual(level, 'FAIL')
        self.assertEqual(sg.correlation_verdict(0.5, 0.0)[0], 'PASS')
        self.assertEqual(sg.correlation_verdict(-0.2, 0.0)[0], 'FAIL')


class Spatial(unittest.TestCase):
    def test_scene_weights_sum_to_one_when_transitions_overlap(self):
        from spatial_engine import hoa
        t = np.arange(1000)
        r1 = np.sin(0.5 * np.pi * np.clip((t - 200) / 400.0, 0, 1)) ** 2
        r2 = np.sin(0.5 * np.pi * np.clip((t - 300) / 400.0, 0, 1)) ** 2
        w = hoa.scene_weights([np.ones(1000), r1, r2])
        np.testing.assert_allclose(np.sum(w, axis=0), 1.0, atol=1e-12)
        self.assertTrue(np.all(np.asarray(w) >= 0.0))

    def test_a_scene_without_a_transition_is_rejected(self):
        from spatial_engine import hoa
        with self.assertRaises(ValueError):
            hoa.scene_fade_samples({'anchor': {'section': 'B'}}, 2.0, 48000)
        self.assertEqual(hoa.scene_fade_samples({'transition_s': 0.5}, 2.0, 1000), 500)
        self.assertEqual(hoa.scene_fade_samples({'transition_bars': 2}, 2.0, 1000), 4000)

    def test_adm_validate_file_honours_the_expected_sample_rate(self):
        from spatial_engine import adm
        sr = 44100
        bus = adm.AdmBus(sr, dict(enabled=True, height_by_role={'melody': 20.0}, max_elevation=60.0,
                                  pair=dict(width_deg_stereo=12.0, width_deg_bed=40.0)), dict(title='t'))
        bus.objects.append(('a', np.ones(4410, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        audio = bus.result()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.wav')
            adm.write(p, audio, sr, bus.xml(len(audio), sr), bus.chna())
            self.assertEqual(adm.validate_file(p, expect_sr=sr), [])
            probs = adm.validate_file(p, expect_sr=48000)
        self.assertTrue(any('sample rate' in q for q in probs), probs)


class Render(unittest.TestCase):
    def test_exported_stems_keep_samples_above_full_scale(self):
        import pipeline
        stems = {'a': np.full((4000, 2), 1.5, np.float32)}
        with tempfile.TemporaryDirectory() as d:
            pipeline.write_stems(stems, d, full=True, sr=8000)
            import soundfile as sf
            y, _ = sf.read(os.path.join(d, 'a.wav'))
        self.assertGreater(float(np.abs(y).max()), 1.4)

    def test_stem_cache_key_follows_the_oversample_setting(self):
        import render_natural as rn

        class TM:
            secs = np.zeros(4)
        tr = dict(name='t', instrument='piano', notes=[])
        real = rn._oversample
        try:
            rn._oversample = lambda: 1
            a = rn._track_cache_key(tr, 1, [4, 4], 0.5, TM(), None, 44100, None)
            rn._oversample = lambda: 2
            b = rn._track_cache_key(tr, 1, [4, 4], 0.5, TM(), None, 44100, None)
        finally:
            rn._oversample = real
        self.assertNotEqual(a, b)


if __name__ == '__main__':
    unittest.main()
