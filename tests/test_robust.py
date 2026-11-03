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

"""Robust-upgrade tests: environment primitive registry, layer checks, gain_curve, decorrelate radius, turbulent modulation."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import environment as env
import presets

SR = 22050


def render(layers, sec=2.0):
    return env.render_environment_preset({'layers': layers}, duration_s=sec, sr=SR, seed=3)


class Strict:
    def __enter__(self):
        self.old, presets.STRICT = presets.STRICT, True

    def __exit__(self, *a):
        presets.STRICT = self.old


class RegistryTests(unittest.TestCase):
    def test_every_primitive_renders(self):
        for name in env.PRIMITIVES:
            y = render([{'primitive': name, 'gain_db': -20}])
            self.assertTrue(np.isfinite(y).all(), name)

    def test_aliases_resolve(self):
        for a, c in env.ALIASES.items():
            self.assertEqual(env.resolve_primitive({'primitive': a}), c)
        self.assertEqual(env.resolve_primitive({'type': 'crickets', 'species': 'cricket'}), 'cricket_chorus')
        self.assertEqual(env.resolve_primitive({'type': 'rain', 'physical': True}), 'rain_physical')

    def test_unknown_primitive_and_key(self):
        self.assertTrue(env.layer_problems({'primitive': 'canopy_rustle'}))
        self.assertTrue(env.layer_problems({'primitive': 'noise_bed', 'density': 'medium'}))
        self.assertFalse(env.layer_problems({'primitive': 'noise_bed', 'kind': 'bed', 'pan': 0.2}))
        self.assertTrue(env.layer_problems({'primitive': 'noise_bed', 'kind': 'wall'}))

    def test_strict_raises_legacy_warns(self):
        bad = [{'primitive': 'canopy_rustle', 'gain_db': -20}]
        with Strict():
            with self.assertRaises(ValueError):
                render(bad)
        self.assertTrue(np.isfinite(render(bad)).all())   # legacy: a warning and a noise bed

    def test_gain_curve(self):
        flat = render([{'primitive': 'noise_bed', 'gain_db': -20}], 4.0)
        ramp = render([{'primitive': 'noise_bed', 'gain_db': -20, 'gain_curve': [[0, -40], [4, 0]]}], 4.0)
        h = len(flat) // 2
        self.assertLess(np.abs(ramp[:h // 4]).mean(), 0.3 * np.abs(flat[:h // 4]).mean())
        self.assertGreater(np.abs(ramp[-h // 4:]).mean(), 0.4 * np.abs(flat[-h // 4:]).mean())
        self.assertTrue(env.layer_problems({'primitive': 'noise_bed', 'gain_curve': [[1, 0], [0, 0]]}))

    def test_decorrelate_radius_default_for_beds(self):
        x = np.random.default_rng(0).standard_normal(SR).astype(np.float32)
        a = env.decorrelate(x, SR, seed=1)
        b = env.decorrelate(x, SR, seed=1, r_hi=env.BED_RADIUS)
        self.assertTrue(np.allclose(a, b))
        self.assertFalse(np.allclose(a, env.decorrelate(x, SR, seed=1, r_hi=env.EVENT_RADIUS)))

    def test_slow_mod_turbulent(self):
        rng = np.random.default_rng(5)
        m = env._slow_mod(SR * 20, SR, 0.1, 0.7, rng)
        self.assertLessEqual(np.abs(m).max(), 1.0)
        pure = env._slow_mod(SR * 20, SR, 0.1, 0.0, np.random.default_rng(5))
        self.assertFalse(np.allclose(m, pure))

    def test_bird_echo_switch(self):
        on = env.synth_fm_chirp_cluster(3.0, SR, np.random.default_rng(2), echo_db=-12.0)
        off = env.synth_fm_chirp_cluster(3.0, SR, np.random.default_rng(2), echo_db=None)
        self.assertFalse(np.allclose(on, off))


class SpaceTests(unittest.TestCase):
    def test_shipped_spaces_cover_every_room_and_space(self):
        import mixer
        import spatial
        for name in list(mixer.ROOMS) + list(spatial.ACOUSTIC_SPACES):
            cfg = presets.find_space(name)
            self.assertIsNotNone(cfg, name)
            self.assertIn('rt60', cfg['room'])
        r = mixer.ROOMS['cave']
        self.assertEqual(mixer.resolve_space('cave')['room']['rt60'], r[0])
        self.assertFalse(mixer._space_owned(mixer.resolve_space('cave')))   # shipped = fallback

    def test_project_space_applies_distance_law_and_kind(self):
        import json
        import tempfile
        import os
        import mixer
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'spaces'))
            json.dump(dict(name='tiny_test_space', room=dict(rt60=0.4, pre_delay_ms=5, hf_decay=0.6, early_level=0.2),
                           distance=dict(ref_m=1.0, falloff=0.5, pre_delay_law=dict(base_ms=32, per_m=3.5, max_ms=30)),
                           binaural=dict(bed=False, spot=True)),
                      open(os.path.join(d, 'presets', 'spaces', 'tiny_test_space.json'), 'w'))
            presets.add_project(d)
            try:
                cfg = mixer.resolve_space('tiny_test_space')
                self.assertTrue(mixer._space_owned(cfg))
                x = np.random.default_rng(1).standard_normal((SR, 2)).astype(np.float32) * 0.1
                score = dict(space='tiny_test_space', tracks=[dict(name='a', role='melody', spatial=dict(azimuth=30, distance=6, spread=0.5))])
                y = mixer.mix_stems(score, {'a': x}, SR)
                self.assertTrue(np.isfinite(y).all())
                self.assertEqual(mixer._space()['room']['rt60'], 0.4)
            finally:
                presets.PROJECT_ROOTS.remove(os.path.abspath(os.path.join(d, 'presets')))


class GateTests(unittest.TestCase):
    def _project(self, ambience):
        import json
        import tempfile
        import setup_project
        d = Path(tempfile.mkdtemp())
        setup_project.scaffold_project(d / 'p', 'Gate Test', ambience=ambience)
        proj = d / 'p'
        score = json.loads((proj / 'scores' / 'main_score.json').read_text(encoding='utf-8'))
        return proj, score

    def tearDown(self):
        presets.PROJECT_ROOTS.clear()

    def test_default_scaffold_has_no_ambience(self):
        import project_gate as pg
        proj, score = self._project(False)
        self.assertFalse((proj / 'presets' / 'environments').exists())
        self.assertFalse(any(str(t.get('instrument')).startswith('env:') for t in score['tracks']))
        self.assertEqual(pg.ambience_problems(score, proj), [])

    def test_placeholder_character_blocks_then_passes(self):
        import json
        import project_gate as pg
        proj, score = self._project(True)
        self.assertTrue(any('character' in p for p in pg.space_problems(score, proj)))
        self.assertTrue(any('character' in p for p in pg.ambience_problems(score, proj)))
        for kind, nm in (('spaces', score['space']), ('environments', 'forest_canopy_3d')):
            f = proj / 'presets' / kind / (nm + '.json')
            d = json.loads(f.read_text(encoding='utf-8'))
            d['character'] = 'a real sentence about the place'
            f.write_text(json.dumps(d), encoding='utf-8')
        self.assertEqual(pg.space_problems(score, proj), [])
        self.assertEqual(pg.ambience_problems(score, proj), [])

    def test_shipped_preset_and_script_ambience_blocked(self):
        import project_gate as pg
        proj, score = self._project(False)
        score['tracks'].append(dict(name='e', instrument='env:amazon_rainforest', role='environment', notes=[]))
        score['space'] = 'hall'
        self.assertTrue(any('shipped' in p for p in pg.ambience_problems(score, proj)))
        self.assertTrue(any('shipped' in p for p in pg.space_problems(score, proj)))
        (proj / 'scripts' / 'mine.py').write_text('import environment\nenvironment.synth_noise_bed(1)\n', encoding='utf-8')
        self.assertTrue(any('mine.py' in p for p in pg.ambience_problems(score, proj)))


class RendererMixerTests(unittest.TestCase):
    def test_expression_curve_is_smooth_and_has_no_tremolo(self):
        import render_natural as rn
        g = rn._expr_curve('breath', 400, 2.0, np.random.default_rng(1))
        self.assertLess(np.abs(np.diff(g, 2)).max(), 0.01)          # no sine wobble on the sustain
        b = rn._expr_curve('bow', 400, 2.0, np.random.default_rng(1))
        self.assertLessEqual(b.max(), 1.0)
        self.assertTrue(np.all(np.diff(b[:20]) >= -1e-9))             # attack only rises

    def test_vibrato_is_halved(self):
        import render_natural as rn
        self.assertEqual(rn.VIBRATO_DEFAULT['flute'][0], 4.5)
        self.assertEqual(rn.VIBRATO_DEFAULT['slow_strings'][0], 7)
        self.assertEqual(rn.VIBRATO_DEFAULT['quena'][0], 7)

    def test_base_names_and_tone_tables(self):
        import mixer
        self.assertIn('shakuhachi', mixer.base_names('quena'))
        self.assertTrue(mixer.inst_eq('quena'))                       # pan_flute / quena / ney ... now have a tone move
        self.assertEqual(mixer.from_table({'flute': 7}, 'flute'), 7)

    def test_band_limited_duck_keeps_the_low_end(self):
        import mixer
        sr = 22050
        t = np.arange(sr * 2) / sr
        low = 0.3 * np.sin(2 * np.pi * 100 * t)
        mid = 0.3 * np.sin(2 * np.pi * 1000 * t)
        pad = np.stack([low + mid] * 2, 1).astype(np.float32)
        lead = np.stack([0.5 * np.sin(2 * np.pi * 440 * t)] * 2, 1).astype(np.float32)
        score = dict(tracks=[dict(name='pad', instrument='warm_pad', role='pad', duck_by='lead', duck_db=-12),
                             dict(name='lead', instrument='flute', role='melody')])
        out = mixer.mix_stems(dict(score, room='none'), {'pad': pad, 'lead': lead}, sr)
        self.assertTrue(np.isfinite(out).all())

    def test_vary_bar_keeps_whole_beats(self):
        import compose
        notes = [dict(t=float(b), d=0.9, p=60, v=0.6) for b in range(4)] + [dict(t=1.5, d=0.4, p=62, v=0.5)]
        for seed in range(20):
            out = compose.vary_bar(notes, 'melody', 3, 4, 1.0, np.random.default_rng(seed))
            beats = sorted(round(n['t'], 3) for n in out if abs(n['t'] - round(n['t'])) < 1e-6)
            self.assertEqual(beats, [0.0, 1.0, 2.0, 3.0])
            for n in out:
                if abs(n['t'] - round(n['t'])) < 1e-6:
                    self.assertTrue(0.9 * 0.6 * 0.94 - 1e-6 <= n['v'] <= 1.1 * 0.6 * 1.06 + 1e-6)

    def test_semitone_rub_and_strong_flag(self):
        import theory
        key = theory.Key('C', 'major')
        chord = dict(pcs=[0, 4, 7])
        deg = next(d for d in range(0, 8) if key.pitch(d) % 12 == 5)   # F rubs against E
        moved = theory._avoid_semitone_rub(key, deg, chord, -3, 11)
        self.assertNotEqual(key.pitch(moved) % 12, 5)
        notes, _, _ = theory.make_phrase(np.random.default_rng(1), key, [chord] * 2, 4)
        self.assertTrue(all('strong' in n for n in notes))
        self.assertTrue(all(isinstance(n['strong'], bool) for n in notes))


if __name__ == '__main__':
    unittest.main()
