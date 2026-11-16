# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The film project: its own scaffold, its own preset family, its own gate profiles."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'video-mixer'))

import gate_profiles                    # noqa: E402
import presets                          # noqa: E402
import setup_project                    # noqa: E402

FILM_PRESETS = ('analysis', 'mapping', 'hits', 'dialogue', 'delivery')


class TestFilmPresets(unittest.TestCase):
    def test_every_film_preset_loads(self):
        for name in FILM_PRESETS:
            p = presets.get('film', name)
            self.assertEqual(p.get('kind'), 'film', name)
            self.assertTrue(str(p.get('character', '')).strip(), name)

    def test_every_film_preset_cites_a_source(self):
        for name in FILM_PRESETS:
            p = presets.get('film', name)
            self.assertTrue(p.get('sources'), f'{name} has no sources')
            self.assertTrue(p.get('provenance'), f'{name} has no provenance')

    def test_the_split_keeps_the_one_cue_numbers(self):
        one = presets.get('video', 'default')
        analysis = presets.get('film', 'analysis')
        mapping = presets.get('film', 'mapping')
        self.assertEqual(analysis['probe']['analysis_fps'], one['probe']['analysis_fps'])
        self.assertEqual(mapping['tempo_from_cuts'], one['direction_map']['tempo_from_cuts'])
        self.assertEqual(presets.get('film', 'dialogue')['duck_db'], one['mix']['duck_db'])

    def test_gating_modes_are_explicit(self):
        delivery = presets.get('film', 'delivery')
        for name, prof in delivery['master_profiles'].items():
            self.assertIn(prof.get('loudness_mode'), ('dialogue', 'full_program'), name)
            self.assertTrue(prof.get('reference'), name)

    def test_streaming_and_netflix_do_not_share_a_mode(self):
        delivery = presets.get('film', 'delivery')
        self.assertEqual(delivery['master_profiles']['streaming']['loudness_mode'], 'full_program')
        self.assertEqual(delivery['master_profiles']['netflix']['loudness_mode'], 'dialogue')


class TestFilmGateProfiles(unittest.TestCase):
    def test_the_family_resolves(self):
        for name in ('video_basic', 'video_dialogue', 'video_montage', 'video_underscore', 'video_trailer'):
            prof = gate_profiles.resolve({'piece_type': name})
            self.assertEqual(prof.errors, [], name)

    def test_the_legacy_profile_still_resolves(self):
        prof = gate_profiles.resolve({'piece_type': 'video_cinematic'})
        self.assertEqual(prof.errors, [])
        self.assertEqual(prof.mode('video.duration_lock'), 'apply')

    def test_no_profile_may_skip_a_protected_row(self):
        bad = gate_profiles.row_problems({'video.master_compliance': {'mode': 'skip', 'reason': 'x'}}, 'test')
        self.assertTrue(bad)


class TestFilmScaffold(unittest.TestCase):
    def setUp(self):
        presets.reset_projects()
        self.tmp = tempfile.TemporaryDirectory()
        self.film = Path(self.tmp.name) / 'film'
        setup_project.scaffold_film_project(self.film, title='Glaciers', fps=24.0, cues=['M01_open', 'M02_close'])

    def tearDown(self):
        presets.reset_projects()
        self.tmp.cleanup()

    def test_the_tree_is_what_the_plan_says(self):
        for rel in ('spotting', 'analysis', 'deliver', 'cues', 'cues/M01_open', 'cues/M02_close',
                    'cues/M01_open/direction', 'cues/M01_open/presets', 'cues/M01_open/scores',
                    'cues/M01_open/reports', 'cues/M01_open/out'):
            self.assertTrue((self.film / rel).is_dir(), rel)
        for rel in ('film.json', 'metadata.json', 'STATUS.md',
                    'spotting/cutlist.json', 'spotting/cuesheet.json', 'spotting/notes.md'):
            self.assertTrue((self.film / rel).is_file(), rel)

    def test_each_cue_is_a_complete_music_project(self):
        for cid in ('M01_open', 'M02_close'):
            cue = self.film / 'cues' / cid
            self.assertTrue((cue / 'direction' / 'direction_sheet.json').is_file())
            self.assertTrue((cue / 'presets').is_dir())
            self.assertTrue((cue / 'STATUS.md').is_file())

    def test_the_cuesheet_points_at_each_cue_master(self):
        sheet = json.loads((self.film / 'spotting' / 'cuesheet.json').read_text(encoding='utf-8'))
        self.assertEqual([c['id'] for c in sheet['cues']], ['M01_open', 'M02_close'])
        self.assertEqual(sheet['cues'][0]['master'], 'cues/M01_open/out/master.wav')

    def test_film_json_records_the_rate(self):
        film = json.loads((self.film / 'film.json').read_text(encoding='utf-8'))
        self.assertEqual(film['fps'], 24.0)
        self.assertEqual(film['title'], 'Glaciers')

    def test_a_project_film_preset_overrides_the_skill_one(self):
        p = self.film / 'cues' / 'M01_open' / 'presets' / 'film'
        p.mkdir(parents=True, exist_ok=True)
        (p / 'hits.json').write_text(json.dumps({
            'kind': 'film', 'name': 'hits', 'character': 'this film hits sparsely',
            'max_hits_per_minute': 6}), encoding='utf-8')
        presets.add_project(str(self.film / 'cues' / 'M01_open'))
        merged = presets.get('film', 'hits')
        self.assertEqual(merged['max_hits_per_minute'], 6)
        self.assertEqual(merged['cut_sound'], presets.get('film', 'hits')['cut_sound'])


class TestPresetValidation(unittest.TestCase):
    def test_no_film_preset_is_missing_a_required_key(self):
        problems = [p for p in presets.validate() if p.startswith('film/')]
        self.assertEqual(problems, [])


if __name__ == '__main__':
    unittest.main()
