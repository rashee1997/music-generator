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

#!/usr/bin/env python3
"""A physical scene ambience counts as the bed the project gate asks for; a one-shot scene does not.

The gate used to read only `layers`, so every scene preset was refused with "no environment preset in the score has a
bed layer" and the new ambience path could never render. The rule now lives in environment.preset_is_bed.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / '..' / 'scripts'))

import environment                    # noqa: E402
import env_engine.render as er         # noqa: E402
import phys_core.scene as scene_mod    # noqa: E402
import project_gate                    # noqa: E402

MODEL = json.load(open(HERE / '..' / 'references' / 'data' / 'sound-models' / 'leaf_rain.json', encoding='utf-8'))['model']
SCENE = dict(seconds=1.0, voices=MODEL['voices'])          # a valid scene that sounds once (no timeline)


class SceneAsBed(unittest.TestCase):
    def test_continuous_mechanisms_are_beds_and_impacts_are_not(self):
        self.assertTrue(scene_mod.is_continuous({'timeline': [{'interaction': 'flow'}]}))
        self.assertTrue(scene_mod.is_continuous({'timeline': [{'interaction': 'impact',
                                                              'then': [{'interaction': 'foliage'}]}]}))
        self.assertFalse(scene_mod.is_continuous({'timeline': [{'interaction': 'impact'}]}))
        self.assertFalse(scene_mod.is_continuous({'voices': MODEL['voices']}))
        self.assertEqual(scene_mod.problems(SCENE), [])

    def test_scene_layers_is_a_bed_and_a_one_shot_scene_is_not(self):
        self.assertTrue(er.is_bed({'scene_layers': [{'scene': SCENE}]}))
        self.assertFalse(er.is_bed({'scene': SCENE}))

    def test_gate_accepts_a_scene_bed_and_still_refuses_a_spot_only_place(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'
            envs = proj / 'presets' / 'environments'
            envs.mkdir(parents=True)
            bed = dict(name='bed_scene', character='Two physical scenes mixed as one bed.',
                       scene_layers=[dict(scene=SCENE, gain_db=-6.0, spatial=dict(azimuth=-30.0)),
                                     dict(scene=SCENE, gain_db=-9.0, spatial=dict(azimuth=40.0))])
            (envs / 'bed_scene.json').write_text(json.dumps(bed), encoding='utf-8')
            (envs / 'spot_scene.json').write_text(
                json.dumps(dict(name='spot_scene', character='One knock, once.', scene=SCENE)), encoding='utf-8')
            score = dict(title='t', bpm=90, tracks=[
                dict(name='air', instrument='env:bed_scene', role='environment', notes=[])])
            self.assertEqual(project_gate.ambience_problems(score, proj), [])
            score['tracks'][0]['instrument'] = 'env:spot_scene'
            self.assertTrue(any('bed' in x for x in project_gate.ambience_problems(score, proj)))

    def test_a_scene_bed_renders_audible_stereo(self):
        cfg = dict(name='bed', character='x',
                   scene_layers=[dict(scene=SCENE, gain_db=-6.0, spatial=dict(azimuth=-30.0))])
        x = environment.render_environment_preset(cfg, duration_s=1.0, seed=2)
        self.assertEqual(x.shape, (44100, 2))
        self.assertGreater(float(np.abs(x).max()), 1e-4)
