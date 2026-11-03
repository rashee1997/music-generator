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

"""The physical sound core: the scene schema, the legacy passthrough, the mechanism registry, the frozen-render
baseline, and the CLI. Physics behaviour is in tests/test_phys_engine.py."""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import phys_core.baseline as baseline
import phys_core.registry as registry
import phys_core.scene as scene
import physical
import sound_model as sm

SR = 44100
BALL = HERE.parent / 'references' / 'sound-models' / 'bouncing_ball.json'


def _ball_model():
    return json.load(open(BALL, encoding='utf-8'))['model']


def _branch_scene():
    """A small physical scene: a wooden object struck, once."""
    return {
        "seconds": 1.5,
        "materials": {"oak": {"family": "fibrous", "density": 700, "young_modulus_gpa": 11, "loss_factor": 0.015}},
        "objects": {"limb": {"material": "oak", "geometry": {"shape": "bar", "length_m": 1.0, "thickness_m": 0.03},
                             "modes": 8}},
        "timeline": [{"at": 0.1, "interaction": "impact", "target": "limb", "velocity_m_s": 2.0, "mass_kg": 0.8}],
        "propagation": {"distance_m": 4.0},
    }


class SceneSchema(unittest.TestCase):
    def test_a_voice_scene_is_the_old_model_and_renders_byte_identically(self):
        model = _ball_model()
        self.assertEqual(scene.problems(model), [])
        x, report = scene.render_scene(model, SR, 5)
        self.assertEqual(report['engine'], 'voices')
        self.assertTrue(np.array_equal(x, sm.render(model, SR, 5)))

    def test_a_physical_scene_validates_and_renders(self):
        s = _branch_scene()
        self.assertEqual(scene.problems(s), [])
        x, report = scene.render_scene(s, SR, 3)
        self.assertEqual(report['engine'], 'timeline')
        self.assertEqual(len(x), int(1.5 * SR))
        self.assertTrue(np.isfinite(x).all())
        self.assertGreater(float(np.abs(x).max()), 1e-3)

    def test_unknown_key_is_refused_and_names_what_is_known(self):
        bad = scene.problems(dict(_branch_scene(), reverb=0.3))
        self.assertTrue(any('unknown key "reverb"' in p and 'materials' in p for p in bad), bad)

    def test_unknown_interaction_is_refused_and_lists_the_mechanisms(self):
        s = _branch_scene()
        s['timeline'][0]['interaction'] = 'rain'
        bad = scene.problems(s)
        self.assertTrue(any('unknown' in p.lower() or 'use one of' in p for p in bad), bad)
        self.assertTrue(any('impact' in p for p in bad), bad)

    def test_unknown_material_and_bad_geometry_are_refused(self):
        s = _branch_scene()
        s['objects']['limb']['material'] = 'unobtainium'
        s['objects']['limb']['geometry']['shape'] = 'blob'
        bad = scene.problems(s)
        self.assertTrue(any('unobtainium' in p for p in bad), bad)
        self.assertTrue(any('blob' in p for p in bad), bad)

    def test_a_scene_without_voices_or_timeline_is_refused(self):
        bad = scene.problems({"seconds": 1.0})
        self.assertTrue(any('no default sound' in p for p in bad), bad)

    def test_calibration_modes_are_validated(self):
        self.assertEqual(scene.problems(dict(_branch_scene(), calibration={"normalize": "energy"})), [])
        self.assertTrue(scene.problems(dict(_branch_scene(), calibration={"normalize": "loud"})))
        self.assertTrue(scene.problems(dict(_branch_scene(), calibration={"gain": 3})))


class Registry(unittest.TestCase):
    def test_the_registry_is_internally_consistent(self):
        self.assertEqual(registry.problems(), [])

    def test_every_interaction_is_registered(self):
        live = registry.implemented()
        self.assertEqual(live['interaction'], sorted(__import__('phys_core.render', fromlist=['x']).INTERACTIONS))

    def test_no_planned_mechanism_is_already_an_interaction(self):
        planned = {n for n, _, _, _ in registry.planned()}
        self.assertEqual(planned & set(registry.implemented()['interaction']), set())


class Baseline(unittest.TestCase):
    ONLY = ['sfx:impact', 'model:bouncing_ball']

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = str(Path(self.td.name) / 'b')
        baseline.freeze(self.dir, only=self.ONLY, quiet=True)

    def tearDown(self):
        self.td.cleanup()

    def test_freeze_then_verify_is_identical(self):
        rows = baseline.verify(self.dir, only=self.ONLY, quiet=True)
        self.assertTrue(rows)
        self.assertEqual({s for s, _, _ in rows}, {'PASS'}, rows)

    def test_verify_reports_a_changed_hash_and_an_uncovered_item(self):
        path = Path(self.dir) / 'manifest.json'
        man = json.loads(path.read_text(encoding='utf-8'))
        names = sorted(man['items'])
        man['items'][names[0]]['sha256'] = '0' * 64
        del man['items'][names[1]]
        path.write_text(json.dumps(man), encoding='utf-8')
        rows = {s for s, _, _ in baseline.verify(self.dir, only=self.ONLY, quiet=True)}
        self.assertEqual(rows, {'CHANGED', 'NEW'})

    def test_verify_reports_missing_only_when_the_target_is_gone(self):
        orig = baseline.targets
        baseline.targets = lambda: [t for t in orig() if t['name'] != 'sfx:impact']
        try:
            rows = {s: n for s, n, _ in baseline.verify(self.dir, only=self.ONLY, quiet=True)}
        finally:
            baseline.targets = orig
        self.assertEqual(rows.get('MISSING'), 'sfx:impact')

    def test_only_narrows_the_comparison(self):
        rows = baseline.verify(self.dir, only=['model:bouncing_ball'], quiet=True)
        self.assertEqual({n for _, n, _ in rows}, {'model:bouncing_ball'})

    def test_verify_without_a_manifest_says_how_to_make_one(self):
        with self.assertRaises(FileNotFoundError) as cm:
            baseline.verify(str(Path(self.td.name) / 'nope'), quiet=True)
        self.assertIn('baseline', str(cm.exception))


class Cli(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.good = Path(self.td.name) / 'good.json'
        self.good.write_text(json.dumps(_branch_scene()), encoding='utf-8')
        self.bad = Path(self.td.name) / 'bad.json'
        self.bad.write_text(json.dumps(dict(_branch_scene(), timeline=[{"interaction": "nope"}])), encoding='utf-8')

    def tearDown(self):
        self.td.cleanup()

    def test_check_exit_codes(self):
        self.assertEqual(physical.cmd_check(argparse.Namespace(file=str(self.good))), 0)
        self.assertEqual(physical.cmd_check(argparse.Namespace(file=str(self.bad))), 1)

    def test_render_writes_a_wav_of_the_scene_length(self):
        import soundfile as sf
        out = Path(self.td.name) / 'x.wav'
        a = argparse.Namespace(file=str(self.good), out=str(out), sr=SR, seed=2, seconds=1.0, stereo=True)
        self.assertEqual(physical.cmd_render(a), 0)
        x, sr = sf.read(str(out))
        self.assertEqual(sr, SR)
        self.assertEqual(x.ndim, 2)
        self.assertLessEqual(abs(len(x) / sr - 1.0), 0.02)

    def test_render_refuses_a_bad_scene_without_writing(self):
        out = Path(self.td.name) / 'no.wav'
        a = argparse.Namespace(file=str(self.bad), out=str(out), sr=SR, seed=1, seconds=None, stereo=False)
        self.assertEqual(physical.cmd_render(a), 1)
        self.assertFalse(out.exists())

    def test_template_writes_a_valid_scene(self):
        out = Path(self.td.name) / 't.json'
        self.assertEqual(physical.cmd_template(argparse.Namespace(out=str(out), force=False)), 0)
        self.assertEqual(scene.problems(json.loads(out.read_text(encoding='utf-8'))), [])


if __name__ == '__main__':
    unittest.main()
