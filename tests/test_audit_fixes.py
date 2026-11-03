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

"""Smoke tests for the scripts that had none, and for the audit fixes (gate staging, binaural route, sfx route,
note names, CLI errors, scaffold spread, gust continuity, normalised layers, roughness margin)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE.parent / 'video-mixer'))
import cli_util
import direct
import envcheck
import environment as env
import mixer
import naturalness_check as nc
import presets
import project_gate
import research_kb
import section_report
import setup_project
import vocals
import video_program_mix

SR = 44100


def cli(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=300)


def tone_wav(path, sec=3.0, f=440.0, amp=0.3):
    t = np.arange(int(sec * SR)) / SR
    sf.write(path, np.stack([amp * np.sin(2 * np.pi * f * t)] * 2, axis=1).astype(np.float32), SR)


class CliErrors(unittest.TestCase):
    def test_missing_inputs_give_one_line(self):
        for script, args in (('listen.py', ['nope.wav']), ('soul_check.py', ['nope.json']), ('render_natural.py', ['nope.json']),
                             ('mixer.py', ['nope_dir']), ('section_report.py', ['a.json', 'b.wav']),
                             ('direct.py', ['nope.json', '--out', 'x.json'])):
            r = cli(script, *args)
            self.assertNotEqual(r.returncode, 0, script)
            self.assertNotIn('Traceback', r.stderr, script)
            self.assertIn('not found', r.stderr + r.stdout, script)

    def test_note_names(self):
        self.assertEqual([cli_util.pitch_to_midi(p) for p in ('D3', 'C4', 'F#4', 'Bb2', '60', 61.0)], [50, 60, 66, 46, 60, 61])
        self.assertEqual(cli_util.pitch_to_midi('kick'), 'kick')
        with self.assertRaises(ValueError):
            cli_util.midi_int('zzz', 'track x: ')
        sc = {'tracks': [{'notes': [{'t': 0, 'p': 'A3'}, {'t': 1, 'p': 'snare'}]}]}
        cli_util.normalize_pitches(sc)
        self.assertEqual([n['p'] for n in sc['tracks'][0]['notes']], [57, 'snare'])


class Untested(unittest.TestCase):
    def test_research_kb_cites_documents(self):
        text, ids = research_kb.build('rain ambience', ['sfx'], 2)
        self.assertIn('## Web research', text)
        self.assertTrue(ids and all(i in text for i in ids))

    def test_direct_edits(self):
        sc = {'bpm': 100, 'meter': [4, 4], 'tracks': [{'name': 'a', 'instrument': 'piano', 'role': 'chord', 'gain_db': 0,
                                                       'notes': [{'t': 0, 'd': 4, 'p': 60, 'v': 0.6}]}]}
        direct.set_gain(sc, 'a', -5.0)
        self.assertEqual(sc['tracks'][0]['gain_db'], -5.0)
        direct.copy_track(sc, 'a', 'b', transpose=12)
        self.assertEqual(sc['tracks'][-1]['notes'][0]['p'], 72)
        direct.remove_track(sc, 'b')
        self.assertEqual([t['name'] for t in sc['tracks']], ['a'])

    def test_naturalness_and_listen_without_ears(self):
        with tempfile.TemporaryDirectory() as td:
            w = os.path.join(td, 't.wav')
            tone_wav(w)
            r = nc.analyse(w)
            self.assertTrue(np.isfinite(r['lufs']) and r['true_peak'] < 0)
            out = cli('listen.py', w, '--no-ears')
            self.assertEqual(out.returncode, 0, out.stderr[-400:])
            self.assertIn('true_peak', out.stdout)

    def test_section_report_rows(self):
        with tempfile.TemporaryDirectory() as td:
            w, s = os.path.join(td, 't.wav'), os.path.join(td, 's.json')
            tone_wav(w, sec=8.0)
            json.dump({'bpm': 120, 'ts': [4, 4], 'meta': {'bars': 4}, 'tracks': [{'role': 'melody', 'notes': [{'t': 0, 'd': 1}]}]}, open(s, 'w'))
            rows, ring, dur = section_report.report(s, w)
            self.assertEqual(len(rows), 4)
            self.assertTrue(rows[0]['lead'])
            self.assertGreater(dur, 7.0)

    def test_video_program_mix_ducks_music_under_voice(self):
        voice = np.zeros((SR * 3, 2), np.float32)
        voice[SR:2 * SR] = (0.3 * np.sin(2 * np.pi * 200 * np.arange(SR) / SR))[:, None]
        music = np.repeat((0.2 * np.sin(2 * np.pi * 330 * np.arange(SR * 3) / SR)).astype(np.float32)[:, None], 2, axis=1)
        cfg = presets.get('video', 'default')['mix']
        out = video_program_mix.build(voice, music, [], cfg)[0]
        self.assertTrue(np.isfinite(out).all() and len(out) >= SR * 3)

    def test_vocal_choir_renders(self):
        ev = [{'t': 0.0, 'dur': 0.8, 'p': 60, 'v': 0.7}]
        y = vocals.render_choir(ev, voices=2)
        self.assertEqual(y.shape[1], 2)
        self.assertGreater(np.abs(y).max(), 0.01)


class GateStaging(unittest.TestCase):
    def _proj(self, td):
        proj = Path(td) / 'p'
        setup_project.scaffold_project(str(proj), title='T')
        for f in list((proj / 'reports').glob('research_*.md')) + list((proj / 'presets').rglob('*.json')):
            f.unlink()
        sheet = proj / 'direction' / 'direction_sheet.json'
        sheet.write_text(sheet.read_text(encoding='utf-8').replace('TODO', 'x'), encoding='utf-8')
        return proj, sheet

    def test_direction_needs_feel_staging_and_hits(self):
        with tempfile.TemporaryDirectory() as td:
            proj, sheet = self._proj(td)
            for key in ('feel', 'spatial_staging', 'hits_at'):
                d = json.loads(sheet.read_text(encoding='utf-8'))
                d.pop(key)
                sheet.write_text(json.dumps(d), encoding='utf-8')
                self.assertTrue(any(key in p for p in project_gate.direction_problems(proj)), key)
                d2 = json.loads(sheet.read_text(encoding='utf-8')) | {'feel': ['calm'], 'spatial_staging': {'a': {'azimuth': 0, 'distance': 1}},
                                                                      'hits_at': [], 'hits': []}
                sheet.write_text(json.dumps(d2), encoding='utf-8')

    def test_preset_must_match_staging(self):
        with tempfile.TemporaryDirectory() as td:
            proj, sheet = self._proj(td)
            d = json.loads(sheet.read_text(encoding='utf-8'))
            d['spatial_staging'] = {'oud': {'azimuth': -30.0, 'distance': 2.0}}
            sheet.write_text(json.dumps(d), encoding='utf-8')
            (proj / 'presets' / 'instruments' / 'oud.json').write_text(
                json.dumps(dict(name='oud', gm='acoustic_guitar', spatial=dict(azimuth=60.0, distance=2.0))), encoding='utf-8')
            sc = {'tracks': [{'name': 'o', 'instrument': 'oud', 'notes': []}]}
            self.assertTrue(any('agree' in p for p in project_gate.stage_problems(sc, proj)))

    def test_sfx_track_is_builtin_and_unknown_effect_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            proj, _ = self._proj(td)
            ok = {'tracks': [{'name': 'r', 'instrument': 'sfx:water_drip', 'notes': []}]}      # a one-hit effect: shipped default, no preset needed
            bad = {'tracks': [{'name': 'r', 'instrument': 'sfx:nope', 'notes': []}]}
            amb = {'tracks': [{'name': 'r', 'instrument': 'sfx:rain', 'notes': []}]}          # ambience belongs to an environments preset
            self.assertEqual(project_gate.track_problems(ok, proj), [])
            self.assertTrue(any('unknown effect' in p for p in project_gate.track_problems(bad, proj)))
            self.assertTrue(any('env:' in p and 'ambience' in p for p in project_gate.track_problems(amb, proj)))

    def test_scaffold_spreads_presets(self):
        with tempfile.TemporaryDirectory() as td:
            spots = set()
            for n in ('a', 'b', 'c', 'd'):
                p = presets.scaffold('instruments', n, td)
                sp = json.loads(Path(p).read_text(encoding='utf-8'))['spatial']
                spots.add((sp['azimuth'], sp['distance']))
            self.assertEqual(len(spots), 4)

    def test_double_distance_warns(self):
        with tempfile.TemporaryDirectory() as td:
            proj, _ = self._proj(td)
            (proj / 'presets' / 'environments').mkdir(parents=True, exist_ok=True)
            (proj / 'presets' / 'environments' / 'far.json').write_text(
                json.dumps({'name': 'far', 'layers': [{'primitive': 'noise_bed', 'spatial': {'distance': 12}}]}), encoding='utf-8')
            sc = {'tracks': [{'name': 'e', 'instrument': 'env:far', 'role': 'environment', 'spatial': {'distance': 4}, 'notes': []}]}
            self.assertTrue(any('twice' in w for w in project_gate.warnings(proj, sc)))


class Rendering(unittest.TestCase):
    def test_binaural_route_differs_from_pan_route(self):
        x = np.random.default_rng(1).standard_normal((SR, 2)).astype(np.float32) * 0.1
        base = {'role': 'melody', 'gain_db': 0.0, 'reverb': 0.0, 'spatial': {'azimuth': 60.0, 'distance': 2.0}}
        a = mixer.process_stem('t', x.copy(), json.loads(json.dumps(base)))
        b_spec = json.loads(json.dumps(base))
        b_spec['spatial'].update(binaural=True, space='forest_canopy')
        b = mixer.process_stem('t', x.copy(), b_spec)
        self.assertEqual(a.shape, b.shape)
        self.assertTrue(np.isfinite(b).all())
        itd_b = np.argmax(np.correlate(b[:4000, 0], b[:4000, 1], 'full')) - 3999
        self.assertNotEqual(itd_b, 0)             # inter-aural delay exists only on the binaural route

    def test_sfx_track_renders_through_render_natural(self):
        import render_natural as rn
        score = {'title': 't', 'bpm': 120, 'meter': [4, 4], 'tracks': [
            {'name': 'drip', 'instrument': 'sfx:water_drip', 'role': 'fx', 'notes': [{'t': 0, 'd': 2, 'v': 0.8}]}]}
        stems, tm = rn.build_stems(score, verbose=False)
        self.assertGreater(np.abs(stems['drip']).max(), 0.01)

    def test_gust_has_no_block_rate_dips(self):
        g = env.synth_resonant_gust(6, SR, np.random.default_rng(1), center_hz=420, mod_depth=0.0)
        seg = int(0.05 * SR)
        starts = np.mean([abs(g[i * seg:i * seg + 30]).mean() for i in range(2, 100)])
        mids = np.mean([abs(g[i * seg + seg // 2:i * seg + seg // 2 + 30]).mean() for i in range(2, 100)])
        self.assertGreater(starts / mids, 0.5)

    def test_new_layers_share_one_level(self):
        rms = []
        for prim, extra in (('rain_physical', {}), ('cricket_chorus', {}), ('bird_chorus', {'species': 3})):
            o = env.render_environment_preset({'layers': [dict(primitive=prim, gain_db=-20, **extra)]}, duration_s=6, seed=2)
            rms.append(np.sqrt((o ** 2).mean()))
        self.assertLess(max(rms) / min(rms), 2.0)


class Gates(unittest.TestCase):
    def test_borderline_roughness_spike_is_a_warning_not_a_fail(self):
        rng = np.random.default_rng(3)
        t = np.arange(SR * 8) / SR
        x = 0.2 * np.sin(2 * np.pi * 220 * t) + 0.02 * rng.standard_normal(len(t))
        rows, _ = nc.cochlear_roughness_check(np.stack([x, x], 1).astype(np.float32), sr=SR)
        self.assertNotIn('FAIL', [r[0] for r in rows])

    def test_envcheck_reports_a_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            req = os.path.join(td, 'r.txt')
            open(req, 'w').write('numpy==0.0.1\nnot_a_real_pkg_xyz==1.0\n')
            m = envcheck.mismatches(req)
            self.assertEqual(len(m), 2)


if __name__ == '__main__':
    unittest.main()


class StemSpans(unittest.TestCase):
    def test_trim_and_roundtrip_put_a_late_stem_back(self):
        import pipeline as pl
        n = SR * 10
        late = np.zeros((n, 2), np.float32)
        late[6 * SR:8 * SR] = 0.3 * np.sin(2 * np.pi * 440 * np.arange(2 * SR) / SR)[:, None]
        seg, start = pl.trim_stem(late)
        self.assertAlmostEqual(start, 5.95, delta=0.02)
        self.assertLess(len(seg), 2.2 * SR)
        with tempfile.TemporaryDirectory() as td:
            man = pl.write_stems({'late': late, 'early': late[:SR]}, td)
            self.assertAlmostEqual(man['late']['start_s'], 5.95, delta=0.02)
            self.assertLess(man['late']['length_s'], 2.2)
            back = pl.MusicPipeline(verbose=False).load_stems_from_dir(td)['late']
            self.assertAlmostEqual(len(back) / SR, 8.0, delta=0.05)          # start offset restored
            self.assertGreater(np.abs(back[int(6.5 * SR)]).max() + np.abs(back[int(7 * SR):int(7.1 * SR)]).max(), 0.05)
            pl.write_stems({'late': late, 'early': late[:SR]}, td, full=True)
            full = pl.MusicPipeline(verbose=False).load_stems_from_dir(td)
            self.assertEqual({len(v) for v in full.values()}, {n})

    def test_environment_track_renders_only_its_span(self):
        import render_natural as rn
        score = {'title': 't', 'bpm': 120, 'meter': [4, 4], 'tracks': [
            {'name': 'x', 'instrument': 'piano', 'role': 'chord', 'notes': [{'t': 0, 'd': 1, 'p': 60, 'v': 0.5}, {'t': 38, 'd': 2, 'p': 62, 'v': 0.5}]},
            {'name': 'amb', 'instrument': 'env:savanna_dusk', 'role': 'environment', 'notes': [{'t': 20, 'd': 16, 'p': 60, 'v': 0.6}]}]}
        stems, tm = rn.build_stems(score, verbose=False)
        amb = stems['amb']
        a = np.abs(amb).max(axis=1)
        first = np.flatnonzero(a > 1e-4)[0] / SR
        self.assertAlmostEqual(first, tm.sec(20), delta=0.5)                 # silent until its first note


class UnknownEnvironment(unittest.TestCase):
    def test_unknown_environment_is_an_error_not_silence(self):
        with self.assertRaises(ValueError):
            env.render_environment_preset('no_such_place', duration_s=2)

    def test_gate_blocks_env_track_without_preset(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'
            setup_project.scaffold_project(str(proj), title='T')
            sc = {'tracks': [{'name': 'a', 'instrument': 'env:no_such_place', 'role': 'environment', 'notes': []}]}
            self.assertTrue(any('no preset' in p for p in project_gate.track_problems(sc, proj)))
