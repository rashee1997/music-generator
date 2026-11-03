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

"""Preset-driven sound effects and real-sound references: one-hit effects from presets, ambience through environments,
the per-sound research citation gate (project mode only), the reference tool, and older projects staying valid."""
import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
import ambience_reference as ar
import environment as env
import presets
import project_gate
import research_kb
import setup_project
import sfx

SR = 44100
SR_ = SR


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding='utf-8')


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.proj = Path(self.td.name) / 'p'
        setup_project.scaffold_project(str(self.proj), title='T')
        for f in list((self.proj / 'reports').glob('research_*.md')) + list((self.proj / 'presets').rglob('*.json')):
            f.unlink()
        presets.PROJECT_ROOTS.clear()

    def tearDown(self):
        presets.PROJECT_ROOTS.clear()
        self.td.cleanup()


class OneHitPresets(Base):
    def test_every_one_hit_has_a_shipped_default_and_ambience_has_none(self):
        for name in sfx.GENERATORS:
            cfg = presets.find_sfx(name)
            if name in sfx.AMBIENCE:
                self.assertIsNone(cfg, name)
            else:
                self.assertIsNotNone(cfg, name)
                self.assertEqual(sfx.preset_problems(cfg), [], name)

    def test_default_equals_the_recipe(self):
        a, _, _ = sfx.make('impact', 1.0, SR, 3)
        b = sfx._norm(np.asarray(sfx.GENERATORS['impact'](1.0, SR, np.random.default_rng(3)), dtype=float))
        self.assertTrue(np.array_equal(a, b))

    def test_project_preset_overrides_the_default_and_is_deterministic(self):
        _write(self.proj / 'presets' / 'sfx' / 'impact.json',
               dict(name='impact', character='x', spec=dict(seconds=1, layers=[dict(kind='tone', f=200, env=dict(tau=0.2))])))
        presets.add_project(str(self.proj))
        a, src, _ = sfx.make('impact', 1.0, SR, 3)
        b, _, _ = sfx.make('impact', 1.0, SR, 3)
        self.assertEqual(src, 'preset')
        self.assertTrue(np.array_equal(a, b))
        shipped = sfx._norm(np.asarray(sfx.GENERATORS['impact'](1.0, SR, np.random.default_rng(3)), dtype=float))
        self.assertFalse(np.array_equal(a, shipped))

    def test_unknown_key_is_an_error(self):
        _write(self.proj / 'presets' / 'sfx' / 'coin.json', dict(name='coin', character='x', generator='coin', colour='red'))
        presets.add_project(str(self.proj))
        with self.assertRaises(ValueError) as cm:
            sfx.make('coin', 0.5, SR, 1)
        self.assertIn('colour', str(cm.exception))

    def test_unknown_param_is_an_error_and_known_param_works(self):
        self.assertTrue(sfx.preset_problems(dict(generator='footstep', params=dict(speed=3))))
        self.assertEqual(sfx.preset_problems(dict(generator='footstep', params=dict(surface='gravel'))), [])
        x, _, _ = sfx.make('footstep', 0.3, SR, 2, surface='gravel')
        self.assertTrue(np.isfinite(x).all())

    def test_ambience_name_still_renders_with_a_pointer(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            x, _, _ = sfx.make('rain', 1.0, SR, 1)
        self.assertTrue(any('environments preset' in str(i.message) for i in w))
        self.assertGreater(np.abs(x).max(), 0.1)

    def test_scaffold_sfx_writes_a_valid_template(self):
        p = presets.scaffold('sfx', 'zap', str(self.proj))
        cfg = json.loads(Path(p).read_text(encoding='utf-8'))
        self.assertEqual(sfx.preset_problems(cfg), [])
        self.assertEqual(presets.validate(), [])


class MixerReadsPresets(Base):
    def test_sfx_and_env_presets_carry_their_mix_settings(self):
        import mixer
        _write(self.proj / 'presets' / 'sfx' / 'coin.json', dict(name='coin', character='x', generator='coin', gain_db=-3.0, reverb=0.4,
                                                                  spatial=dict(azimuth=30.0, distance=4.0)))
        _write(self.proj / 'presets' / 'environments' / 'roof.json', dict(name='roof', character='x', gain_db=-20.0, reverb=0.05,
                                                                          layers=[dict(primitive='noise_bed', kind='bed')]))
        presets.add_project(str(self.proj))
        s = mixer.default_spec(dict(instrument='sfx:coin', role='fx'))
        self.assertEqual((s['gain_db'], s['reverb'], s['spatial']['azimuth']), (-3.0, 0.4, 30.0))
        self.assertEqual(mixer.default_spec(dict(instrument='sfx:coin', role='fx', gain_db=-10.0))['gain_db'], -10.0)      # the score still wins
        e = mixer.default_spec(dict(instrument='env:roof', role='environment'))
        self.assertEqual((e['gain_db'], e['reverb']), (-20.0, 0.05))
        self.assertEqual(sfx.preset_problems(dict(generator='coin', gain_db=-3.0, spatial=dict(azimuth=0.0))), [])

    def test_mix_and_master_applies_the_preset_level_to_the_stem(self):
        """The same path the pipeline's stage 5 takes: the stem's level in the mix follows the sfx preset's gain_db."""
        import mixer
        x = (np.random.default_rng(1).standard_normal((SR_ * 4, 2)) * 0.2).astype(np.float32)
        score = {'bpm': 120, 'meter': [4, 4], 'tracks': [{'name': 'hit', 'instrument': 'sfx:coin', 'role': 'fx', 'notes': []}]}
        levels = []
        for db in (-3.0, -20.0):
            _write(self.proj / 'presets' / 'sfx' / 'coin.json', dict(name='coin', character='x', generator='coin', gain_db=db, reverb=0.0))
            presets.PROJECT_ROOTS.clear()
            presets.add_project(str(self.proj))
            mixer.mix_and_master(score, {'hit': x.copy()}, str(Path(self.td.name) / 'm.wav'), master=False, report=False)
            y = mixer.STATE['processed']['hit']
            levels.append(20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12))
        self.assertAlmostEqual(levels[0] - levels[1], 17.0, delta=2.0)

    def test_shipped_default_with_no_mix_keys_keeps_the_role_defaults(self):
        import mixer
        presets.add_project(str(self.proj))
        s = mixer.default_spec(dict(instrument='sfx:coin', role='fx'))
        self.assertEqual(s['gain_db'], mixer._level_by_role().get('fx', -8))


class GateRules(Base):
    def _score(self, instrument):
        return {'tracks': [{'name': 't', 'instrument': instrument, 'notes': []}]}

    def test_ambience_sfx_track_blocks_and_points_to_env(self):
        probs = project_gate.track_problems(self._score('sfx:rain'), self.proj)
        self.assertTrue(any('env:' in p and 'ambience' in p for p in probs), probs)

    def test_one_hit_with_shipped_default_passes_without_sources(self):
        score = self._score('sfx:coin')
        self.assertEqual(project_gate.track_problems(score, self.proj), [])
        self.assertEqual(project_gate.reference_problems(score, self.proj), [])

    def test_unknown_effect_still_blocks(self):
        self.assertTrue(any('unknown effect' in p for p in project_gate.track_problems(self._score('sfx:nope'), self.proj)))

    def _rain_preset(self, sources):
        _write(self.proj / 'presets' / 'environments' / 'roof.json',
               dict(name='roof', character='A tin roof in heavy rain.', sources=sources,
                    layers=[dict(primitive='rain_physical', rate_mm_h=20, surface='solid', kind='bed')]))

    def test_own_ambience_needs_sources_then_a_section_then_two_urls(self):
        score = self._score('env:roof')
        self._rain_preset([])
        self.assertTrue(any('no "sources"' in p for p in project_gate.reference_problems(score, self.proj)))
        self._rain_preset(['rain_roof'])
        self.assertTrue(any('has no "## Real-world references: rain_roof"' in p for p in project_gate.reference_problems(score, self.proj)))
        note = self.proj / 'reports' / 'research_rain.md'
        _write(note, '## Real-world references: rain_roof\n- https://a.example/paper\nLicence: analysed only\n')
        self.assertTrue(any('1 URL' in p for p in project_gate.reference_problems(score, self.proj)))
        _write(note, '## Real-world references: rain_roof\n- https://a.example/paper\n- https://b.example/rec\nLicence: analysed only\n')
        self.assertEqual(project_gate.reference_problems(score, self.proj), [])

    def test_estimate_with_reason_is_accepted_and_missing_licence_is_not(self):
        score = self._score('env:roof')
        self._rain_preset(['rain_roof'])
        note = self.proj / 'reports' / 'research_rain.md'
        _write(note, '## Real-world references: rain_roof\nNo measurement found: ESTIMATE no tin-roof recording is published\nLicence: n/a\n')
        self.assertEqual(project_gate.reference_problems(score, self.proj), [])
        _write(note, '## Real-world references: rain_roof\n- https://a.example/1\n- https://b.example/2\n')
        self.assertTrue(any('Licence' in p for p in project_gate.reference_problems(score, self.proj)))

    def test_todo_stub_from_research_kb_does_not_pass(self):
        text, _ = research_kb.build('rain ambience', ['sfx'], 1, ['rain_roof'])
        _write(self.proj / 'reports' / 'research_rain.md', text)
        self._rain_preset(['rain_roof'])
        self.assertTrue(project_gate.reference_problems(self._score('env:roof'), self.proj))

    def test_score_without_env_or_sfx_tracks_is_untouched(self):
        self.assertEqual(project_gate.reference_problems(self._score('piano'), self.proj), [])

    def test_new_folders_are_scaffolded_but_not_required(self):
        self.assertTrue((self.proj / 'presets' / 'sfx').is_dir() and (self.proj / 'reference').is_dir())
        self.assertNotIn('reference', project_gate.SCAFFOLD)
        (self.proj / 'reference').rmdir()
        (self.proj / 'presets' / 'sfx').rmdir()
        self.assertFalse([p for p in project_gate.problems(None, self.proj) if 'missing folder' in p])

    def test_legacy_alias_warns_but_does_not_block(self):
        _write(self.proj / 'presets' / 'environments' / 'old.json',
               dict(name='old', character='x', layers=[dict(primitive='rain', kind='bed', gain_db=-20)]))
        presets.add_project(str(self.proj))
        self.assertEqual(env.preset_problems(presets.exact('environments', 'old')), [])
        self.assertTrue(any('older name' in w and 'impulse_cluster' in w for w in project_gate.warnings(self.proj)))


class ReferenceTool(Base):
    def _noise_wav(self, path, lo_hz, hi_hz, seed=0, sec=3.0):
        from scipy.signal import butter, sosfilt
        x = np.random.default_rng(seed).standard_normal(int(SR * sec))
        x = sosfilt(butter(4, [lo_hz, hi_hz], btype='band', fs=SR, output='sos'), x)
        sf.write(str(path), (x / np.abs(x).max() * 0.5).astype(np.float32), SR)

    def test_band_shares_of_a_known_signal(self):
        from scipy.signal import butter, sosfilt
        x = sosfilt(butter(6, [4000, 6000], btype='band', fs=SR, output='sos'), np.random.default_rng(1).standard_normal(SR * 3))
        m = ar.measure_array(x, SR)
        self.assertGreater(m['bands']['3k_7k'], 0.9)
        self.assertLess(m['bands']['lt300'], 0.01)
        self.assertTrue(3500 < m['centroid_hz'] < 6500)

    def test_level_does_not_change_the_measurement(self):
        x = np.random.default_rng(2).standard_normal(SR * 2)
        a, b = ar.measure_array(x, SR), ar.measure_array(x * 0.01, SR)
        self.assertAlmostEqual(a['centroid_hz'], b['centroid_hz'], places=3)

    def test_silence_is_rejected(self):
        with self.assertRaises(ValueError):
            ar.measure_array(np.zeros(SR), SR)

    def test_measure_stores_numbers_not_audio_and_compare_flags_a_far_render(self):
        real = Path(self.td.name) / 'real.wav'
        self._noise_wav(real, 3000, 7000)
        path, rec, n = ar.measure_file(str(real), 'rain_roof', str(self.proj), 'https://x.example', 'analysed only')
        self.assertEqual(n, 1)
        self.assertEqual(sorted(p.suffix for p in (self.proj / 'reference').iterdir()), ['.json'])
        near = ar.measure_array(np.random.default_rng(9).standard_normal(SR * 3) * 0 + sf.read(str(real))[0], SR)
        self.assertEqual(ar.compare_rows(near, str(self.proj), ['rain_roof'])[0][0], 'PASS')
        dark = Path(self.td.name) / 'dark.wav'
        self._noise_wav(dark, 80, 400)
        far = ar.measure_array(sf.read(str(dark))[0], SR)
        row = ar.compare_rows(far, str(self.proj), ['rain_roof'])[0]
        self.assertEqual(row[0], 'WARN')                                  # a warning, never a FAIL
        self.assertEqual(ar.compare_rows(far, str(self.proj), ['no_such_slug']), [])

    def test_gate_rows_use_the_preset_sources(self):
        real = Path(self.td.name) / 'real.wav'
        self._noise_wav(real, 3000, 7000)
        ar.measure_file(str(real), 'rain_roof', str(self.proj))
        _write(self.proj / 'presets' / 'environments' / 'roof.json',
               dict(name='roof', character='x', sources=['rain_roof'], layers=[dict(primitive='rain_physical', kind='bed')]))
        presets.add_project(str(self.proj))
        score = {'tracks': [{'name': 'rain', 'instrument': 'env:roof', 'notes': []}]}
        stems = {'rain': sf.read(str(real))[0]}
        rows = ar.gate_rows(score, stems, [str(self.proj)])
        self.assertEqual([r[1] for r in rows], ['ambience_reference'])
        self.assertEqual(ar.gate_rows(score, None, [str(self.proj)]), [])


if __name__ == '__main__':
    unittest.main()
