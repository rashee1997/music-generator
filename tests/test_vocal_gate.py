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

"""Quality-gate rows for vocal tracks, config migration, and the shipped vocal presets end to end."""
import glob
import json
import os
import sys
import tempfile
import unittest
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path[:0] = [os.path.join(ROOT, 'scripts')]
import gate_profiles  # noqa: E402
import quality_gate as qg  # noqa: E402
import vocals  # noqa: E402
from vocal_engine import config  # noqa: E402

SR = 44100
SCORE = {'tracks': [{'name': 'hum', 'instrument': 'hum_formant', 'role': 'pad'}]}


def good(**over):
    r = dict(voices=5, phrases=3, joins=6, longest_phrase_s=4.0, capacity_s=7.0, over_capacity=0, inhales=2, no_room_phrases=1,
             mean_abs_dev_cents=9.0, max_abs_dev_cents=25.0, dyn_corr=0.9, max_corr=0.2, hum_hf_frac=1e-4, finite=True,
             dc=1e-6, peak_pre_limit=0.4, peak=0.4)
    r.update(over)
    return r


def rows(v, stems=None, score=SCORE):
    return qg.vocal_rows(score, stems if stems is not None else {'hum': np.zeros((SR, 2), np.float32)},
                         report={'hum': {'vocal': v}})


def levels(rs):
    return [r[0] for r in rs]


class VocalGate(unittest.TestCase):
    def test_clean_report_has_no_fail_or_warn(self):
        rs = rows(good())
        self.assertNotIn('FAIL', levels(rs))
        self.assertNotIn('WARN', levels(rs))
        self.assertGreaterEqual(len(rs), 6)

    def test_no_vocal_track_no_rows(self):
        self.assertEqual(qg.vocal_rows({'tracks': [{'name': 'x'}]}, {}, report={'x': {}}), [])

    def test_negative_controls_each_row_can_fail(self):
        cases = {
            'nan': (good(finite=False), 'FAIL', 'NaN'),
            'dc': (good(dc=0.05), 'FAIL', 'DC'),
            'limiter': (good(peak_pre_limit=1.4), 'WARN', 'limiter'),
            'breath': (good(longest_phrase_s=14.0), 'WARN', 'breath'),
            'copy': (good(max_corr=0.97), 'FAIL', 'one singer copied'),
            'pitch': (good(mean_abs_dev_cents=120.0), 'FAIL', 'pitch error'),
            'pitch_one': (good(max_abs_dev_cents=400.0), 'WARN', 'written pitch'),
            'flat': (good(dyn_corr=0.05), 'FAIL', 'normalised'),
            'bright': (good(hum_hf_frac=0.4), 'WARN', 'too bright'),
        }
        for name, (rep, level, word) in cases.items():
            rs = rows(rep)
            self.assertTrue(any(l == level and word in d for l, _, d in rs), (name, rs))

    def test_click_row_detects_a_step_in_the_stem(self):
        clean = (0.2 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
        bad = clean.copy()
        bad[20000:] += 0.9                                     # a one-sample jump with quiet either side
        self.assertNotIn('FAIL', levels(rows(good(), stems={'hum': np.stack([clean, clean], 1)})))
        self.assertIn('FAIL', levels(rows(good(), stems={'hum': np.stack([bad, bad], 1)})))

    def test_ensemble_and_dynamics_skip_when_not_applicable(self):
        rs = rows(good(voices=1, max_corr=None, dyn_corr=None))
        self.assertFalse(any('correlation' in d and 'voice-to-voice' in d for _, _, d in rs))
        self.assertTrue(any('too uniform' in d for _, _, d in rs))

    def test_profile_relax_needs_a_reason_and_integrity_is_protected(self):
        ok = dict(SCORE, gate={'vocal.ensemble': {'mode': 'relax', 'reason': 'unison chant, voices should match', 'max_corr': 0.9}})
        rs = qg.vocal_rows(ok, {'hum': np.zeros((SR, 2), np.float32)}, report={'hum': {'vocal': good(max_corr=0.8)}})
        self.assertNotIn('FAIL', levels(rs))
        self.assertTrue(gate_profiles.row_problems({'vocal.ensemble': {'mode': 'relax', 'max_corr': 0.9}}, 'x'))      # no reason
        self.assertTrue(gate_profiles.row_problems({'vocal.integrity': {'mode': 'skip', 'reason': 'no'}}, 'x'))        # protected
        self.assertEqual(gate_profiles.problems(), [])

    def test_real_engine_report_passes_the_gate(self):
        ev = [dict(t=0.0, dur=1.2, p=62, v=60), dict(t=1.2, dur=1.2, p=65, v=100), dict(t=2.4, dur=1.2, p=64, v=75),
              dict(t=3.6, dur=1.6, p=62, v=110), dict(t=6.0, dur=1.5, p=60, v=70)]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            y, _info = vocals.render_choir(ev, sr=SR, voices=4, seed=3, hum=True, return_stems=True)
        rep = dict(_info['report'])
        self.assertTrue(rep['finite'])
        self.assertGreater(rep['dyn_corr'], 0.7)               # level follows velocity: nothing normalised per note
        self.assertLess(rep['max_corr'], 0.6)
        self.assertLess(rep['hum_hf_frac'], 0.02)
        rs = qg.vocal_rows(SCORE, {'hum': y}, report={'hum': {'vocal': rep}})
        self.assertNotIn('FAIL', levels(rs), rs)


class ConfigLayer(unittest.TestCase):
    def test_legacy_flat_keys_migrate(self):
        c, w = config.resolve(dict(voices=3, attack=0.5, release=0.7, breath=0.04, vib_cents=10, vib_hz=5, vib_delay=0.2,
                                   spread_cents=15, pan_width=0.3, formants=[500, 1500, 2500]))
        self.assertEqual(c['ensemble']['voices'], 3)
        self.assertEqual((c['articulation']['attack_ms'], c['articulation']['release_ms']), (500.0, 700.0))
        self.assertEqual((c['source']['breathiness'], c['vibrato']['depth_cents']), (0.04, 10.0))
        self.assertEqual(c['ensemble']['pitch_spread_cents'], 15.0)
        self.assertEqual(c['tract']['formants'], [500.0, 1500.0, 2500.0])
        self.assertEqual(w, [])

    def test_old_nested_preset_keys_migrate(self):
        c, _ = config.resolve({'formant_profile': {'vowel': 'm', 'F1_hz': 260, 'F2_hz': 960, 'F3_hz': 2100},
                               'articulation': {'attack_ms': 220, 'decay_ms': 150, 'sustain_level': 0.85, 'release_ms': 400,
                                                'vib_cents': 12.0, 'vib_hz': 4.8}})
        self.assertEqual(c['tract']['formants'], [260.0, 960.0, 2100.0])
        self.assertEqual((c['articulation']['attack_ms'], c['vibrato']['depth_cents'], c['vibrato']['rate_hz']), (220, 12.0, 4.8))

    def test_clamp_unknowns_and_none(self):
        c, w = config.resolve({'vib_cents': 900, 'style': 'nope', 'expression': 'nope', 'wat': 1, 'breath': None,
                               'source': {'register': 'nope'}, 'vowel': 'z'})
        self.assertEqual(c['vibrato']['depth_cents'], 100)
        text = ' | '.join(w)
        for word in ('outside', 'unknown style', 'unknown expression', 'unknown vocal key "wat"', 'register', 'unknown vowel'):
            self.assertIn(word, text)
        self.assertEqual(c['source']['breathiness'], 0.03)      # None = unset

    def test_expression_sits_under_explicit_values(self):
        c, _ = config.resolve({'expression': 'powerful', 'attack': 0.5, 'vib_cents': 5})
        self.assertEqual(c['articulation']['attack_ms'], 500.0)
        self.assertEqual(c['vibrato']['depth_cents'], 5.0)
        self.assertEqual(c['vibrato']['rate_hz'], 5.8)           # not set by the preset: the profile's value
        c0, _ = config.resolve({'expression': 'powerful', 'expression_intensity': 0.0})
        self.assertEqual(c0['vibrato']['rate_hz'], 5.3)

    def test_project_expression_profile_is_found_and_wins(self):
        import presets
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'vocals', 'expression'))
            with open(os.path.join(d, 'presets', 'vocals', 'expression', 'my_mood.json'), 'w') as f:
                json.dump({'vibrato': {'rate_hz': 7.5}}, f)
            with open(os.path.join(d, 'presets', 'vocals', 'expression', 'gentle.json'), 'w') as f:
                json.dump({'vibrato': {'rate_hz': 3.0}}, f)
            n = len(presets.PROJECT_ROOTS)
            presets.add_project(d)
            try:
                c, w = config.resolve({'expression': 'my_mood'})
                self.assertEqual((c['vibrato']['rate_hz'], w), (7.5, []))
                self.assertEqual(config.resolve({'expression': 'gentle'})[0]['vibrato']['rate_hz'], 3.0)   # project beats skill
            finally:
                del presets.PROJECT_ROOTS[n:]
        self.assertTrue(any('unknown expression' in x for x in config.resolve({'expression': 'my_mood'})[1]))

    def test_hum_defaults_can_be_overridden(self):
        c, _ = config.resolve({}, hum=True)
        self.assertEqual((c['vibrato']['depth_cents'], c['source']['breathiness']), (18.0, 0.01))
        c, _ = config.resolve({'vib_cents': 30, 'hum': True})
        self.assertEqual(c['vibrato']['depth_cents'], 30.0)

    def test_custom_style_and_inline_expression_render(self):
        cfg = {'style': 'my_tradition', 'styles': {'my_tradition': {'formants': [500, 1400, 2600], 'register': 'falsetto',
                                                                    'subharmonic': True, 'vib_cents': 4}},
               'expression': {'vibrato': {'rate_hz': 6.5}}}
        with warnings.catch_warnings():
            warnings.simplefilter('error')                     # a valid custom style must not warn
            y = vocals.render_choir([dict(t=0, dur=1.0, p=55, v=90)], sr=SR, voices=2, config=cfg)
        self.assertTrue(np.isfinite(y).all() and np.abs(y).max() > 0.02)

    def test_every_shipped_vocal_preset_renders(self):
        files = sorted(glob.glob(os.path.join(ROOT, 'references', 'data', 'presets', 'vocals', '*.json')))
        self.assertGreaterEqual(len(files), 3)
        for f in files:
            cfg = json.load(open(f, encoding='utf-8'))
            self.assertEqual(config.validate(cfg), [], f)
            with warnings.catch_warnings():
                warnings.simplefilter('error')
                y = vocals.render_choir([dict(t=0, dur=0.8, p=62, v=90), dict(t=0.8, dur=0.8, p=65, v=90)], sr=SR, config=cfg)
            self.assertTrue(np.isfinite(y).all() and np.abs(y).max() > 0.01, f)

    def test_sing_keeps_its_legacy_contract(self):
        x = vocals.sing(57, 0.8, SR, np.random.default_rng(1), vowel='a', gain=0.5)
        self.assertAlmostEqual(float(np.abs(x).max()), 0.5, places=3)
        self.assertEqual(len(x), int(round(0.8 * SR)))

    def test_dsp_helpers_are_safe_and_configurable(self):
        x = np.random.default_rng(0).standard_normal((SR, 2)).astype(np.float32) * 0.3
        a = vocals.apply_vocal_dsp(x, SR)
        b = vocals.apply_vocal_dsp(x, SR, dsp={'intensity': 0.0})
        self.assertTrue(np.isfinite(a).all() and np.abs(a).max() <= 1.0 and np.abs(a.mean(0)).max() < 1e-3)
        self.assertFalse(np.allclose(a, b))
        self.assertEqual(vocals.apply_vocal_dsp(x[:, 0], SR).shape, (SR, 2))
        self.assertEqual(vocals.apply_vocal_dsp(x[:, 0], SR, keep_shape=True).shape, (SR,))
        d1 = vocals.apply_vocal_dsp(x, SR, style='qawwali_devotional')              # the real key now saturates
        d2 = vocals.apply_vocal_dsp(x, SR, style='classical_choir')
        self.assertFalse(np.allclose(d1, d2))


class ProjectGateVocals(unittest.TestCase):
    def test_bad_vocal_block_and_placeholder_character_are_reported(self):
        import project_gate as pg
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'vocals'))
            json.dump({'name': 'choir_x', 'character': 'ONE SENTENCE: who sings', 'style': 'nope', 'vib_cents': 900},
                      open(os.path.join(d, 'presets', 'vocals', 'choir_x.json'), 'w'))
            score = {'tracks': [{'name': 'v', 'instrument': 'choir_x', 'notes': []},
                                {'name': 'w', 'instrument': 'choir_formant', 'vocal': {'expression': 'zzz'}, 'notes': []}]}
            text = '\n'.join(pg.track_problems(score, d))
            for word in ('unknown style', 'outside', 'character', 'unknown expression'):
                self.assertIn(word, text)



class EndToEnd(unittest.TestCase):
    """A real score: render_natural -> mixer -> vocal gate rows. No mixer change was needed for vocals."""
    NOTES = [{'t': 0, 'd': 1.5, 'p': 62, 'v': 70}, {'t': 1.5, 'd': 1.5, 'p': 65, 'v': 95},
             {'t': 3, 'd': 1, 'p': 64, 'v': 80}, {'t': 4.5, 'd': 2, 'p': 62, 'v': 100}]

    def _run(self, extra):
        import render_natural as rn
        import mixer
        import soundfile as sf
        rn.REPORT.clear()
        score = {'title': 't', 'bpm': 100, 'meter': [4, 4], 'tracks': [
            {'name': 'hum', 'instrument': 'hum_formant', 'role': 'pad', 'notes': self.NOTES,
             'vocal': {'expression': 'gentle', 'ensemble': {'voices': 4}}, **extra},
            {'name': 'pn', 'instrument': 'piano', 'role': 'chord', 'notes': [{'t': 0, 'd': 4, 'p': 50, 'v': 50}]}]}
        stems, _ = rn.build_stems(score, verbose=False)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'm.wav')
            mixer.mix_and_master(score, stems, out, master=False, report=False)
            y, _ = sf.read(out)
        self.assertIn('vocal', rn.REPORT['hum'])
        rs = qg.vocal_rows(score, stems)
        return stems['hum'], y, rs

    def test_vocal_track_renders_mixes_and_passes_every_vocal_row(self):
        stem, mix, rs = self._run({})
        self.assertTrue(np.isfinite(stem).all() and np.isfinite(mix).all())
        self.assertGreater(np.abs(mix).max(), 0.01)
        self.assertNotIn('FAIL', levels(rs), rs)
        self.assertNotIn('WARN', levels(rs), rs)
        self.assertGreaterEqual(len(rs), 7)

    def test_vocal_track_with_a_spatial_block_still_mixes(self):
        for binaural in (True, 'hrtf'):
            _, mix, rs = self._run({'spatial': {'azimuth': 20, 'elevation': 0, 'distance': 2.5, 'space': 'hall', 'binaural': binaural}})
            self.assertTrue(np.isfinite(mix).all() and np.abs(mix).max() > 0.01)
            self.assertNotIn('FAIL', levels(rs), rs)


if __name__ == '__main__':
    unittest.main()
