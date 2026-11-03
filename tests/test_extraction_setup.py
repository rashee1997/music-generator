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
"""test_extraction_setup.py - extraction project setup, profile merging, music_db reading and checks."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, SCRIPTS)
from extraction import config, music_db as mdb  # noqa: E402

PIPE = os.path.join(SCRIPTS, 'extract_pipeline.py')


def write(folder, name, obj):
    with open(os.path.join(folder, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f)


def good_folder(tmp):
    write(tmp, 'song.json', {'schema': 'music_db.song/1', 'duration_s': 60.0, 'tempo_bpm': {'value': 120.0}, 'time_signature': '4/4',
                             'key': {'tonic': 'A', 'mode': 'minor'},
                             'sections': [{'name': 'intro', 'start_s': 0, 'end_s': 4}, {'name': 'a', 'start_s': 4, 'end_s': 20},
                                          {'name': 'b', 'start_s': 20, 'end_s': 60}]})
    write(tmp, 'instruments.json', {'schema': 'music_db.instruments/1', 'instruments': [
        {'id': 'trumpet_lead', 'family': 'brass', 'range': {'lowest_note': 'E4', 'highest_note': 'C6'}, 'polyphony': 1,
         'similar_to': ['trumpet_muted_trumpet'], 'timbre': {'harmonics_rel': [1.0] + [0.5] * 11},
         'pitch_behavior': {'tuning_offset_cents': 35}, 'activity': [{'start_s': 4, 'end_s': 30, 'level_0_10': 8}]}]})
    write(tmp, 'drums.json', {'schema': 'music_db.drums/1', 'pieces': [{'id': 'kick', 'kind': 'kick', 'hit_times_s': [4.0, 4.5, 5.0, 5.5, 6.0]}]})
    write(tmp, 'effects.json', {'schema': 'music_db.effects/1', 'events': [{'id': 'fx_01', 'type': 'riser', 'start_s': 10.0, 'end_s': 14.0}]})


class TestSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='test_extraction_')
        self.song = os.path.join(self.tmp, 'song.wav')
        with open(self.song, 'wb') as f:
            f.write(b'RIFF')
        self.proj = os.path.join(self.tmp, 'proj')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def setup_cmd(self, song=None):
        return subprocess.run([sys.executable, PIPE, 'setup', '--new-project', self.proj, '--song', song or self.song, '--no-env'],
                              capture_output=True, text=True)

    def snapshot(self):
        return sorted((os.path.relpath(os.path.join(d, f), self.proj), os.path.getmtime(os.path.join(d, f)))
                      for d, _, fs in os.walk(self.proj) for f in fs)

    def test_tree_and_idempotent_second_run(self):
        r = self.setup_cmd()
        self.assertEqual(r.returncode, 0, r.stderr)
        for d in ('music_db', 'profiles', 'presets', 'prompts', 'out/stems', 'out/midi', 'reports'):
            self.assertTrue(os.path.isdir(os.path.join(self.proj, *d.split('/'))), d)
        for f in ('project.json', 'STATUS.md', 'profiles/project.json', 'prompts/gemini_listener_prompts.md'):
            self.assertTrue(os.path.isfile(os.path.join(self.proj, *f.split('/'))), f)
        before = self.snapshot()
        r2 = self.setup_cmd()
        self.assertIn('nothing (already set up)', r2.stdout)
        self.assertEqual(before, self.snapshot())

    def test_other_song_in_same_folder_is_refused(self):
        self.setup_cmd()
        other = os.path.join(self.tmp, 'other.wav')
        open(other, 'wb').close()
        self.assertNotEqual(self.setup_cmd(other).returncode, 0)


class TestConfig(unittest.TestCase):
    def test_set_overrides_and_unknown_keys_fail(self):
        cfg = config.load(sets=['music_db.span_pad_s=0.9', 'analysis.bands.sub=[20,60]'])
        self.assertEqual(cfg['music_db']['span_pad_s'], 0.9)
        self.assertEqual(cfg['analysis']['bands']['sub'], [20, 60])      # free section accepts new keys
        with self.assertRaises(ValueError):
            config.load(sets=['music_db.span_pad=0.9'])
        with self.assertRaises(ValueError):
            config.load(sets=['nonsense.x=1'])


class TestMusicDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='test_music_db_')
        good_folder(self.tmp)
        self.cfg = config.load()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def errors(self):
        return [m for lv, w, m in mdb.validate(mdb.load(self.tmp, self.cfg), self.cfg) if lv == 'ERROR']

    def test_note_names_and_tuning(self):
        self.assertEqual(mdb.note_to_midi('C4'), 60)
        self.assertEqual(mdb.note_to_midi('D#2'), 39)
        self.assertEqual(mdb.note_to_midi('Bb3'), 58)
        self.assertIsNone(mdb.note_to_midi('H9'))
        self.assertAlmostEqual(mdb.hz(69), 440.0)
        self.assertAlmostEqual(mdb.hz(69, 100.0), 440 * 2 ** (1 / 12), places=3)

    def test_good_folder_priors(self):
        db = mdb.load(self.tmp, self.cfg)
        self.assertEqual(self.errors(), [])
        p = mdb.priors(db, self.cfg)
        self.assertEqual(p['tuning_cents'], 35.0)
        self.assertAlmostEqual(p['grid']['beat_s'], 0.5)
        self.assertEqual(p['grid']['anchor_s'], 4.0)                       # the intro is skipped
        self.assertEqual((p['voices'][0]['midi_lo'], p['voices'][0]['midi_hi']), (64, 84))
        self.assertTrue(mdb.voice_active(p['voices'][0], 10.0, 0.5))
        self.assertFalse(mdb.voice_active(p['voices'][0], 50.0, 0.5))

    def test_bad_range_window_and_hits_are_errors(self):
        write(self.tmp, 'instruments.json', {'schema': 'music_db.instruments/1', 'instruments': [
            {'id': 'x', 'range': {'lowest_note': 'C6', 'highest_note': 'C4'}, 'activity': [{'start_s': 50, 'end_s': 99}]},
            {'id': 'y', 'range': {'lowest_note': 'loud', 'highest_note': 'high'}}]})
        write(self.tmp, 'drums.json', {'schema': 'music_db.drums/1', 'pieces': [{'id': 'kick', 'hit_times_s': [4.0, 4.5, 5.0, 999.0]}]})
        msgs = ' | '.join(self.errors())
        for part in ('above highest_note', 'outside the song', 'not note names'):
            self.assertIn(part, msgs)

    def test_off_grid_hits_warn_and_threshold_is_configurable(self):
        write(self.tmp, 'drums.json', {'schema': 'music_db.drums/1', 'pieces': [{'id': 'kick', 'hit_times_s': [4.07, 4.57, 5.07, 5.57, 6.07]}]})
        db = mdb.load(self.tmp, self.cfg)
        self.assertTrue([m for lv, w, m in mdb.validate(db, self.cfg) if 'grid' in m])
        lax = config.load(sets=['music_db.hit_offset_warn_steps=0.9'])
        self.assertFalse([m for lv, w, m in mdb.validate(db, lax) if 'grid' in m])

    def test_wrong_schema_and_spatial_loading(self):
        write(self.tmp, 'effects.json', {'schema': 'something/9', 'events': []})
        self.assertTrue(any('schema' in m for m in self.errors()))
        write(self.tmp, 'effects.json', {'schema': 'music_db.effects/1', 'events': []})
        write(self.tmp, 'spatial.json', {'schema': 'music_db.spatial/1', 'space': {'rt60_s': 1.2},
                                        'sources': [{'id': 'trumpet_lead', 'baseline': {'azimuth_deg': -20}, 'moves': [{'start_s': 5, 'end_s': 99}]},
                                                    {'id': 'ghost'}]})
        db = mdb.load(self.tmp, self.cfg)
        self.assertEqual(len(db['spatial']['sources']), 2)
        issues = mdb.validate(db, self.cfg)
        self.assertTrue(any('matches no instrument' in m for lv, w, m in issues))
        self.assertTrue(any(lv == 'ERROR' and 'move' in m for lv, w, m in issues))


if __name__ == '__main__':
    unittest.main()
