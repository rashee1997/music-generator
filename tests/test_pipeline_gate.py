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

"""Project gate, exact presets, default deliverables, reverb tail.  Run: python -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import mixer
import numpy as np
import presets
import project_gate
import setup_project

KB_ID = sorted(project_gate.kb_document_ids())[0]


def project_presets(proj):
    """The room and mix presets a project must own (the gate wants a `character` sentence in each)."""
    hall = json.loads((Path(presets.SKILL_PRESETS) / 'spaces' / 'hall.json').read_text(encoding='utf-8'))
    hall.update(name='t_room', character='a test room')
    hall.pop('kind', None)
    (proj / 'presets' / 'spaces').mkdir(parents=True, exist_ok=True)
    (proj / 'presets' / 'mix').mkdir(parents=True, exist_ok=True)
    (proj / 'presets' / 'spaces' / 't_room.json').write_text(json.dumps(hall), encoding='utf-8')
    (proj / 'presets' / 'mix' / 't_mix.json').write_text(json.dumps(dict(name='t_mix', character='a test mix', carve_db=-4.0, max_boost_db=12.0)), encoding='utf-8')


def make_project(td, research=True, direction=True, preset=True, ambience=False):
    proj = Path(td) / 'p'
    setup_project.scaffold_project(str(proj), title='T', ambience=ambience)
    for f in list((proj / 'reports').glob('research_*.md')) + list((proj / 'presets').rglob('*.json')):
        f.unlink()
    project_presets(proj)
    if research:
        (proj / 'reports' / 'research_t.md').write_text(f'## Knowledge base\n- id: {KB_ID}\n## Web research\nhttps://example.org\n', encoding='utf-8')
    if direction:
        sheet = proj / 'direction' / 'direction_sheet.json'
        sheet.write_text(sheet.read_text(encoding='utf-8').replace('TODO', 'x'), encoding='utf-8')
    if preset:
        (proj / 'presets' / 'instruments' / 'oud.json').write_text(json.dumps(dict(name='oud', instrument='acoustic_guitar', spatial=dict(azimuth=-30.0, distance=2.0))), encoding='utf-8')
    return proj


def score_with(*instruments):
    return dict(title='t', bpm=90, space='t_room', tracks=[dict(name=f't{i}', instrument=n, notes=[]) for i, n in enumerate(instruments)])


class ProjectGate(unittest.TestCase):
    def test_complete_project_passes(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            self.assertEqual(project_gate.problems(score_with('oud', 'cello', 'standard'), proj), [])

    def test_each_missing_piece_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(any('research' in p for p in project_gate.problems(score_with('oud'), make_project(td, research=False))))
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(any('TODO' in p for p in project_gate.problems(score_with('oud'), make_project(td, direction=False))))
        with tempfile.TemporaryDirectory() as td:
            probs = project_gate.problems(score_with('oud'), make_project(td, preset=False))
            self.assertTrue(any('"oud"' in p for p in probs), probs)

    def test_research_needs_url_and_citation(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            note = proj / 'reports' / 'research_t.md'
            note.write_text(f'## Knowledge base\n- id: {KB_ID}\n## Web research\nTODO\n', encoding='utf-8')
            self.assertTrue(any('URL' in p for p in project_gate.problems(None, proj)))
            note.write_text('## Web research\nhttps://example.org\n', encoding='utf-8')
            self.assertTrue(any('knowledge-base' in p for p in project_gate.problems(None, proj)))

    def test_near_miss_name_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            self.assertTrue(project_gate.problems(score_with('ou'), proj))
            self.assertTrue(project_gate.problems(score_with('oud_lute'), proj))

    def test_stage_needs_spatial_and_no_shared_spot(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            d = proj / 'presets' / 'instruments'
            (d / 'nay.json').write_text(json.dumps(dict(name='nay', instrument='flute')), encoding='utf-8')
            self.assertTrue(any('no spatial' in p for p in project_gate.problems(score_with('oud', 'nay'), proj)))
            (d / 'nay.json').write_text(json.dumps(dict(name='nay', instrument='flute', spatial=dict(azimuth=-30.0, distance=2.0))), encoding='utf-8')
            self.assertTrue(any('flat stage' in p for p in project_gate.problems(score_with('oud', 'nay'), proj)))
            (d / 'nay.json').write_text(json.dumps(dict(name='nay', instrument='flute', spatial=dict(azimuth=40.0, distance=3.0))), encoding='utf-8')
            self.assertEqual(project_gate.problems(score_with('oud', 'nay'), proj), [])

    def test_broken_preset_json_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            (proj / 'presets' / 'instruments' / 'bad.json').write_text('{nope', encoding='utf-8')
            self.assertTrue(any('bad.json' in p for p in project_gate.problems(None, proj)))


class ExactPresets(unittest.TestCase):
    def tearDown(self):
        presets.STRICT = False
        presets.PROJECT_ROOTS.clear()

    def test_strict_lookup_is_exact(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            presets.add_project(str(proj))
            presets.STRICT = False
            self.assertIsNotNone(presets.find_instrument('oud_lute'))      # fuzzy still works outside projects
            presets.STRICT = True
            self.assertIsNone(presets.find_instrument('oud_lute'))
            self.assertIsNotNone(presets.find_instrument('Oud'))

    def test_scaffold_every_kind(self):
        with tempfile.TemporaryDirectory() as td:
            for kind in ('instruments', 'vocals', 'environments'):
                path = presets.scaffold(kind, 'x_' + kind, td)
                self.assertEqual(json.loads(Path(path).read_text(encoding='utf-8'))['name'], 'x_' + kind)


class Mixer(unittest.TestCase):
    def test_reverb_tail_is_kept(self):
        x = np.zeros((44100, 2), np.float32)
        x[-1] = 1.0                                                         # an impulse on the last sample
        y = mixer.reverb_bus(x, 'hall')
        self.assertGreater(len(y), len(x))
        self.assertGreater(float(np.abs(y[len(x):]).max()), 1e-4)


class DirectionSheet(unittest.TestCase):
    """The director's sheet is a promise: its sections must not overlap, its hits must be the same moments as
    hits_at, and a video block that claims a picture must name it."""

    def sheet(self):
        return json.loads((SK / 'templates' / 'direction_sheet.json').read_text(encoding='utf-8'))

    def test_template_is_valid_json_and_shaped_right(self):
        d = self.sheet()
        self.assertEqual(project_gate.sheet_shape_problems(d), [])
        self.assertEqual([h['t'] for h in d['hits']], d['hits_at'])
        self.assertFalse(d['video']['enabled'], 'the template is a music-only piece')

    def test_overlapping_sections_block(self):
        d = self.sheet()
        d['sections'][2]['start_s'] = d['sections'][1]['start_s'] + 1.0
        self.assertTrue(any('inside the section above' in p for p in project_gate.sheet_shape_problems(d)))

    def test_section_past_the_duration_blocks(self):
        d = self.sheet()
        d['sections'][-1]['end_s'] = d['duration_s'] + 10.0
        self.assertTrue(any('past duration_s' in p for p in project_gate.sheet_shape_problems(d)))

    def test_hits_must_match_hits_at(self):
        d = self.sheet()
        d['hits'].pop()
        self.assertTrue(any('hits_at' in p for p in project_gate.sheet_shape_problems(d)))

    def test_hit_without_a_known_kind_blocks(self):
        d = self.sheet()
        d['hits'][0]['kind'] = 'stab'
        self.assertTrue(any('kind' in p for p in project_gate.sheet_shape_problems(d)))

    def test_video_block_must_name_its_picture(self):
        d = self.sheet()
        d['video'] = dict(d['video'], enabled=True)
        problems = project_gate.sheet_shape_problems(d)
        self.assertTrue(any('video.source' in p for p in problems))
        self.assertTrue(any('video.fps' in p for p in problems))

    def test_a_filled_video_block_passes(self):
        d = self.sheet()
        d['video'].update(enabled=True, source='clips/a.mp4', fps=25.0, cuts=[2.0], master_profile='streaming')
        self.assertEqual(project_gate.sheet_shape_problems(d), [])


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-I', str(SK / 'scripts' / 'pipeline.py'), *args],
                              capture_output=True, text=True, timeout=300)

    def test_bare_brief_needs_test_flag(self):
        r = self.run_cli('trailer in D minor, 4s')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('--test', r.stdout + r.stderr)

    def test_project_run_writes_default_deliverables(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td, preset=False, ambience=True)
            placed = []
            for kind, name in (('instruments', 'lead_flute'), ('instruments', 'warm_piano'), ('instruments', 'acoustic_bass'),
                               ('vocals', 'vocal_hum'), ('environments', 'forest_canopy_3d')):
                p = presets.scaffold(kind, name, str(proj))
                if kind == 'environments':          # the gate wants a character sentence in every project preset
                    cfg = json.loads(Path(p).read_text(encoding='utf-8'))
                    cfg['character'] = 'a test forest'
                    cfg['sources'] = ['forest_air']           # a project-owned ambience must cite the real sound it rests on
                    with open(proj / 'reports' / 'research_t.md', 'a', encoding='utf-8') as fh:
                        fh.write('## Real-world references: forest_air\n- https://example.org/a\n- https://example.org/b\nLicence: analysed only\n')
                    Path(p).write_text(json.dumps(cfg), encoding='utf-8')
                if kind == 'vocals':                # the gate also wants a character sentence in a project vocal preset
                    cfg = json.loads(Path(p).read_text(encoding='utf-8'))
                    cfg['character'] = 'a test hum, closed mouth, close and warm'
                    Path(p).write_text(json.dumps(cfg), encoding='utf-8')
                if kind != 'environments':          # the scaffold's shared default spot is a flat stage; place each one
                    cfg = json.loads(Path(p).read_text(encoding='utf-8'))
                    staged = project_gate.staging_of(proj).get(name)       # a preset named in the direction sheet must agree with it
                    # 30 deg apart, not 20: `spatial.z_separation` asks a climax pair in the same midrange band to be at
                    # least 25 deg apart, and a fixture that places them 20 apart fails the gate it is meant to pass
                    cfg['spatial'] = dict(staged) if staged else dict(azimuth=-40.0 + 30.0 * len(placed), distance=1.5)
                    placed.append(name)
                    Path(p).write_text(json.dumps(cfg), encoding='utf-8')
            mixpath = proj / 'presets' / 'mix' / 't_mix.json'      # the gate wants this piece's mix to differ from the
            if mixpath.exists():                                   # schema default, exactly as a real project does
                cfg = json.loads(mixpath.read_text(encoding='utf-8'))
                cfg.setdefault('mastering', {})['crest_floor_db'] = 9.0
                mixpath.write_text(json.dumps(cfg), encoding='utf-8')
            r = self.run_cli(str(proj / 'scores' / 'main_score.json'), '--project', str(proj))
            self.assertIn(r.returncode, (0, 1), r.stdout[-800:] + r.stderr[-800:])
            self.assertTrue((proj / 'out' / 'master.wav').is_file(), r.stdout[-800:])
            self.assertTrue((proj / 'midi' / 'main_score.mid').is_file())
            self.assertGreaterEqual(len(list((proj / 'stems').glob('*.wav'))), 5)
            rep = json.loads((proj / 'reports' / 'ci_report.json').read_text(encoding='utf-8'))
            self.assertEqual(rep['mode'], 'project')
            self.assertEqual(rep['attempts'][-1]['fails'] == 0, r.returncode == 0)     # the exit code tells the truth


if __name__ == '__main__':
    unittest.main()
