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

"""The mix engine's configuration, strategies, kernels and diagnostics.
Run: python -m unittest tests.test_mix_engine
"""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import dsp                    # noqa: E402
import mix_context            # noqa: E402
import mix_diagnostics        # noqa: E402
import mix_schema             # noqa: E402
import mixer                  # noqa: E402
import presets                # noqa: E402

SR = 44100


def tone(db, secs=2.0, f=440.0):
    t = np.arange(int(SR * secs)) / SR
    x = (np.sin(2 * np.pi * f * t) * np.sqrt(2) * 10 ** (db / 20)).astype(np.float32)
    return np.stack([x, x], 1)


def gs(**kw):
    return dict(mix_schema.section(mix_schema.with_defaults({}), 'gain_staging'), **kw)


class Schema(unittest.TestCase):
    def test_unknown_key_is_reported(self):
        probs = mix_schema.validate({'gain_staging': {'ref_lufss': -24.0}})
        self.assertTrue(any('ref_lufss' in p and 'unknown key' in p for p in probs), probs)

    def test_range_and_enum_are_reported(self):
        self.assertTrue(any('outside' in p for p in mix_schema.validate({'gain_staging': {'ref_lufs': 5.0}})))
        self.assertTrue(any('not one of' in p for p in mix_schema.validate({'dynamics': {'engine': 'analog'}})))

    def test_bad_eq_band_is_reported(self):
        probs = mix_schema.validate({'role_chains': {'pad': {'eq': [{'type': 'comb', 'f': 300}]}}})
        self.assertTrue(any('type' in p for p in probs), probs)

    def test_defaults_carry_the_old_values(self):
        mix = mix_schema.with_defaults({})
        self.assertEqual(mix['gain_staging']['ref_lufs'], -24.0)
        self.assertEqual(mix['gain_staging']['max_boost_db'], 12.0)
        self.assertEqual(mix['gain_staging']['strategy'], 'legacy')
        self.assertEqual(mix['dynamics']['engine'], 'pedalboard')

    def test_a_preset_value_wins_over_the_default(self):
        mix = mix_schema.with_defaults({'gain_staging': {'strategy': 'adaptive'}})
        self.assertEqual(mix['gain_staging']['strategy'], 'adaptive')
        self.assertEqual(mix['gain_staging']['ref_lufs'], -24.0)

    def test_shipped_presets_validate(self):
        self.assertEqual([p for p in presets.validate() if p.startswith('mix/')], [])


class NoLeak(unittest.TestCase):
    """Two pieces, one process: the second must not change the first."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        root = os.path.join(self.td.name, 'presets', 'mix')
        os.makedirs(root)
        with open(os.path.join(root, 'alt.json'), 'w', encoding='utf-8') as fh:
            json.dump({'name': 'alt', 'character': 'a loud-pad alternative', 'carve_db': -8.0,
                       'max_boost_db': 12.0, 'level_by_role': {'pad': -3.0}}, fh)
        presets.PROJECT_ROOTS.clear()
        presets.add_project(self.td.name)

    def tearDown(self):
        presets.PROJECT_ROOTS.clear()
        mixer.use_mix(None)
        self.td.cleanup()

    def test_mixing_a_then_b_then_a_gives_the_same_a(self):
        stems = {'p': tone(-20)}
        a = {'mix_preset': 'default', 'room': 'none', 'tracks': [{'name': 'p', 'role': 'pad'}]}
        b = dict(a, mix_preset='alt')
        first = mixer.mix_stems(a, stems, SR)
        mixer.mix_stems(b, stems, SR)
        third = mixer.mix_stems(a, stems, SR)
        np.testing.assert_allclose(first, third, atol=1e-6)
        louder = mixer.mix_stems(b, stems, SR)
        self.assertGreater(float(np.abs(louder).mean()), float(np.abs(first).mean()))

    def test_the_context_reports_its_preset(self):
        ctx = mix_context.resolve({'mix_preset': 'alt', 'room': 'none'}, space_resolver=mixer.resolve_space)
        self.assertEqual(ctx.name, 'alt')
        self.assertEqual(ctx.mix['level_by_role']['pad'], -3.0)
        self.assertEqual(ctx.space_name, 'none')


class SpecsAreNotMutated(unittest.TestCase):
    def test_process_stem_leaves_the_spec_alone(self):
        spec = mixer.default_spec({'name': 'e', 'role': 'environment', 'instrument': 'env:unknown_place',
                                   'spatial': {'distance': 6.0}})
        before = json.dumps(spec, sort_keys=True, default=str)
        mixer.process_stem('e', tone(-30, 1.0), spec, SR)
        self.assertEqual(json.dumps(spec, sort_keys=True, default=str), before)

    def test_the_send_is_stable_and_far_sources_get_more(self):
        spec = mixer.default_spec({'name': 'e', 'role': 'environment', 'instrument': 'env:unknown_place',
                                   'spatial': {'distance': 6.0}})
        a = mixer.reverb_send_level(spec)
        b = mixer.reverb_send_level(spec)
        self.assertEqual(a, b)
        self.assertGreater(a, float(spec['reverb']))


class GainStaging(unittest.TestCase):
    def test_legacy_is_the_old_formula(self):
        x = tone(-34)
        l = mixer.active_lufs(x, SR)
        self.assertAlmostEqual(mixer.gain_stage(x, l, 'pad', {}, gs(strategy='legacy'), SR),
                               min(-24.0 - l, 12.0), places=6)

    def test_adaptive_stops_a_boost_at_the_peak_headroom(self):
        x = tone(-40, 3.0)
        x[:200] *= 40.0                              # one transient, so the peak sits near -5 dB
        l = mixer.active_lufs(x, SR)
        legacy = mixer.gain_stage(x, l, 'pad', {}, gs(strategy='legacy'), SR)
        self.assertAlmostEqual(legacy, min(-24.0 - l, 12.0), places=6)
        adapt = mixer.gain_stage(x, l, 'pad', {}, gs(strategy='adaptive', peak_headroom_db=-1.0), SR)
        self.assertLess(adapt, legacy)
        self.assertLessEqual(dsp.peak_db(x) + adapt, -0.9)      # the boost stops at the peak headroom

    def test_adaptive_applies_a_cut_limit(self):
        x = tone(-1)
        l = mixer.active_lufs(x, SR)
        self.assertGreaterEqual(mixer.gain_stage(x, l, 'melody', {}, gs(strategy='adaptive', max_cut_db=3.0), SR), -3.0)

    def test_per_role_reference_is_honoured(self):
        x = tone(-40)
        l = mixer.active_lufs(x, SR)
        a = mixer.gain_stage(x, l, 'pad', {}, gs(strategy='adaptive', ref_by_role={'pad': -30.0}), SR)
        b = mixer.gain_stage(x, l, 'pad', {}, gs(strategy='adaptive', ref_by_role={'pad': -20.0}), SR)
        self.assertGreater(b, a)


class Chains(unittest.TestCase):
    def test_role_chain_comes_from_the_preset(self):
        mx = mix_schema.with_defaults({'role_chains': {'melody': {'eq': [{'type': 'hp', 'f': 200}], 'comp': None}}})
        self.assertEqual(len(mixer.role_board('melody', 'synth_pad', mx)), 1)
        self.assertGreater(len(mixer.role_board('melody', 'synth_pad')), 1)

    def test_rain_does_not_share_the_generic_environment_chain(self):
        mx = mix_schema.with_defaults({})
        rain, src = mixer.spectral_chain('environment', {'spectral_profile': 'rain'}, mx)
        self.assertEqual(src, 'profile:rain')
        bed, _ = mixer.spectral_chain('environment', {}, mx)
        self.assertNotEqual(rain['eq'][0]['f'], bed['eq'][0]['f'])
        self.assertIsNone(rain.get('comp'))

    def test_unknown_profile_is_an_error(self):
        with self.assertRaises(ValueError):
            mixer.spectral_chain('environment', {'spectral_profile': 'lava'}, mix_schema.with_defaults({}))

    def test_preserve_spectrum_bypasses_the_automatic_chain(self):
        self.assertEqual(mixer.spectral_chain('environment', {'preserve_spectrum': True})[1], 'bypassed')

    def test_environment_level_is_the_preset_value_not_a_hardcode(self):
        mixer.use_mix(None)
        self.assertEqual(mixer._level_by_role()['environment'], -14.0)
        self.assertEqual(presets.mix()['level_by_role']['environment'], -14.0)


class Ducking(unittest.TestCase):
    def test_lookahead_does_not_release_the_end_instantly(self):
        src = tone(-6, 2.0)
        g = mixer.duck_gain(src, len(src), depth_db=-6)
        self.assertLess(float(g[-1]), 0.9)          # a zeroed tail would have released to 1.0

    def test_duck_holds_during_the_source(self):
        src = tone(-6, 2.0)
        g = mixer.duck_gain(src, len(src), depth_db=-6)
        self.assertAlmostEqual(float(np.median(g[len(g) // 2:])), 0.5, delta=0.05)


class Kernels(unittest.TestCase):
    def test_static_curve_is_exact_outside_the_knee(self):
        self.assertAlmostEqual(float(dsp.static_gain_reduction_db(-30, -20, 4.0)), 0.0)
        self.assertAlmostEqual(float(dsp.static_gain_reduction_db(-10, -20, 4.0)), 7.5)
        at = -20 + 3.0                               # exactly at the knee edge
        self.assertAlmostEqual(float(dsp.static_gain_reduction_db(at, -20, 4.0, 6.0)),
                               float(dsp.static_gain_reduction_db(at, -20, 4.0, 0.0)), places=6)

    def test_knee_starts_before_the_threshold_and_stays_small(self):
        # the knee opens at thr - knee/2, so a signal exactly at threshold is already being bent a little
        self.assertEqual(float(dsp.static_gain_reduction_db(-23.1, -20, 4.0, 6.0)), 0.0)
        at_thr = float(dsp.static_gain_reduction_db(-20, -20, 4.0, 6.0))
        self.assertGreater(at_thr, 0.0)
        self.assertLess(at_thr, 1.0)
        hard_above = float(dsp.static_gain_reduction_db(-20 + 3.0, -20, 4.0, 0.0))   # 2.25 dB, the hard-knee value at the top edge
        self.assertLess(at_thr, hard_above / 2.0)

    def test_compressor_turns_a_loud_tone_down(self):
        x = tone(-6, 1.5)
        y = dsp.compressor(x, SR, threshold_db=-20, ratio=4.0, attack_ms=5, release_ms=50, knee_db=6)
        self.assertLess(dsp.rms_db(y), dsp.rms_db(x) - 3.0)

    def test_parallel_mix_is_louder_than_serial(self):
        x = tone(-6, 1.5)
        kw = dict(threshold_db=-20, ratio=4.0, attack_ms=5, release_ms=50)
        serial = dsp.compressor(x, SR, **kw)
        parallel = dsp.compressor(x, SR, mix=0.5, **kw)
        self.assertGreater(dsp.rms_db(parallel), dsp.rms_db(serial))

    def test_a_filtered_sidechain_does_not_trigger_on_a_low_source(self):
        x = tone(-6, 1.5, f=3000.0)
        kick = tone(-6, 1.5, f=50.0)
        hp = dsp.compressor(x, SR, threshold_db=-24, ratio=4.0, sidechain=kick, sidechain_hp_hz=800.0)
        full = dsp.compressor(x, SR, threshold_db=-24, ratio=4.0, sidechain=kick)
        self.assertGreater(dsp.rms_db(hp), dsp.rms_db(full))

    def test_mono_fold_and_correlation(self):
        mono = tone(-20)
        self.assertAlmostEqual(dsp.mono_fold_db(mono), 0.0, places=6)
        anti = np.stack([mono[:, 0], -mono[:, 0]], 1)
        self.assertLess(dsp.correlation(anti), -0.9)
        self.assertLess(dsp.mono_fold_db(anti), -20)


class Guards(unittest.TestCase):
    def test_empty_stems_is_a_clear_error(self):
        with self.assertRaises(ValueError):
            mixer.mix_stems({'tracks': []}, {}, SR)

    def test_more_than_two_channels_is_rejected(self):
        with self.assertRaises(ValueError):
            mixer.to_stereo(np.zeros((100, 3), np.float32))


class Mastering(unittest.TestCase):
    def tearDown(self):
        mixer.use_mix(None)

    def test_a_profile_sets_the_target(self):
        mixer.master_chain(tone(-12, 2.0), {'profile': 'broadcast'}, SR)
        self.assertEqual(mixer.STATE['master']['target'], -23.0)

    def test_the_score_still_wins_over_the_profile(self):
        mixer.master_chain(tone(-12, 2.0), {'profile': 'broadcast', 'lufs': -16.0}, SR)
        self.assertEqual(mixer.STATE['master']['target'], -16.0)

    def test_measures_are_reported(self):
        mixer.master_chain(tone(-12, 2.0), {}, SR)
        m = mixer.STATE['master']
        for k in ('lufs', 'lra', 'crest', 'true_peak', 'mono_fold', 'correlation'):
            self.assertIn(k, m)
        self.assertTrue(np.isfinite(m['lufs']))

    def test_a_target_that_would_crush_the_crest_is_refused(self):
        feasible, why = mixer.suggest_master_target(tone(-30, 2.0), SR, lufs_target=-6.0)
        self.assertFalse(feasible)
        self.assertIn('crest', why)


class Export(unittest.TestCase):
    def test_the_written_master_passes_its_own_check(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'm.wav')
            score = {'bpm': 120, 'meter': [4, 4], 'room': 'studio',
                     'tracks': [{'name': 'p', 'role': 'pad', 'instrument': 'warm_pad'}]}
            mixer.mix_and_master(score, {'p': tone(-20, 3.0)}, out, report=False)
            rep = mixer.STATE['export']
            self.assertEqual(rep['problems'], [], rep)
            self.assertEqual(rep['channels'], 2)
            self.assertEqual(rep['sr'], SR)


class Diagnostics(unittest.TestCase):
    def test_rows_are_well_formed_and_the_mix_is_untouched(self):
        stems = {'lead': tone(-18), 'pad': tone(-18, f=300.0)}
        before = {k: v.copy() for k, v in stems.items()}
        rows = mix_diagnostics.analyse({'tracks': [{'name': 'lead', 'role': 'melody'},
                                                   {'name': 'pad', 'role': 'pad'}]}, stems)
        self.assertTrue(rows)
        self.assertTrue(all(isinstance(r, tuple) and len(r) == 3 for r in rows), rows)
        self.assertTrue(all(r[0] in ('PASS', 'INFO', 'WARN', 'FAIL') for r in rows), rows)
        for k in stems:
            np.testing.assert_array_equal(stems[k], before[k])

    def test_an_anticorrelated_stem_fails_the_phase_row(self):
        x = tone(-20)
        rows = mix_diagnostics.analyse({'tracks': [{'name': 'a', 'role': 'pad'}]},
                                       {'a': np.stack([x[:, 0], -x[:, 0]], 1)})
        self.assertEqual([r[0] for r in rows if r[1] == 'phase'], ['FAIL'])

    def test_a_silent_stem_is_reported(self):
        rows = mix_diagnostics.analyse({'tracks': [{'name': 'a', 'role': 'pad'}]},
                                       {'a': np.zeros((SR, 2), np.float32)})
        self.assertIn('silent stems', [r[1] for r in rows])


if __name__ == '__main__':
    unittest.main()
