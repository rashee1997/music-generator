# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
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
"""The scene timeline and the rows that read it.

A profile's `scene` block points at the project's own direction sheet; these tests hold the four things that make that
useful rather than decorative:

  * the timeline reads roles, declared rests and dialogue windows from the sheet (no new file format),
  * a declared rest is silent or the row fails - a hole is not excused by being outside a window, and a rest is not a hole,
  * a role's `waive_ceiling` really removes its own window from a whole-piece ceiling (the Catch-22 the scene block exists
    to remove), and
  * a one-section sheet is not asked for contrast unless the profile forces it.

Run: python -m unittest tests.test_scene_timeline_gate
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import gate_profiles as gpf      # noqa: E402
import pattern_audit as pa       # noqa: E402
import presets                   # noqa: E402
import scene_gate                # noqa: E402
import scene_timeline            # noqa: E402


def _sheet(sections, hits=None, dialogue=None):
    d = {"sections": [{"name": n, "role": r, "start_s": a, "end_s": b} for n, r, a, b in sections],
         "hits": hits or []}
    if dialogue:
        d["video"] = {"dialogue": {"windows": dialogue}}
    return d


def _score(tracks=None, piece_type='cinematic_suspense', gate=None, bpm=120):
    sc = {"bpm": bpm, "key": "C", "tracks": tracks or [], "piece_type": piece_type}
    if gate:
        sc["gate"] = gate
    return sc


def _melody(notes, name='flute', role='melody'):
    return {"name": name, "role": role, "instrument": "flute",
            "notes": [{"t": t, "d": d, "p": p, "v": 0.8} for t, d, p in notes]}


class SceneCase(unittest.TestCase):
    def setUp(self):
        presets.reset_projects()
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, 'direction'), exist_ok=True)

    def tearDown(self):
        presets.reset_projects()
        shutil.rmtree(self.dir, ignore_errors=True)

    def write_sheet(self, sheet, name='sheet.json'):
        path = os.path.join(self.dir, 'direction', name)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(sheet, fh)
        return path

    def rows(self, sc, path=None):
        return scene_gate.rows(sc, path=path, project_dir=self.dir)


class TimelineReadsTheSheet(SceneCase):
    def test_roles_rests_and_dialogue_windows(self):
        path = self.write_sheet(_sheet(
            [('open', 'establish', 0.0, 4.0), ('climb', 'build', 4.0, 8.0), ('top', 'peak', 8.0, 12.0)],
            hits=[{"t": 8.0, "kind": "cut", "sync": "hard", "silence_after_s": 1.5}],
            dialogue=[(5.0, 6.0)]))
        tl = scene_timeline.Timeline({'timeline': {}}, sheet=json.load(open(path, encoding='utf-8')))
        tl.dialogue_windows = [(5.0, 6.0)]
        self.assertEqual(tl.roles(), ['establish', 'build', 'peak'])
        self.assertEqual(tl.windows('peak'), [(8.0, 12.0)])
        self.assertEqual(tl.role_at(9.0), 'peak')
        self.assertTrue(tl.is_rest(8.5) and tl.is_rest(9.4))
        self.assertFalse(tl.is_rest(7.0))
        self.assertTrue(tl.in_windows(5.5, tl.dialogue_windows))

    def test_seconds_and_beats_round_trip(self):
        tl = scene_timeline.Timeline({'_score_bpm': 120.0}, sheet=_sheet([('a', 'place', 0.0, 4.0)]))
        self.assertAlmostEqual(tl.beat_to_s(8.0), 4.0, places=6)
        self.assertAlmostEqual(tl.s_to_beat(4.0), 8.0, places=6)

    def test_no_scene_block_emits_nothing(self):
        self.write_sheet(_sheet([('a', 'place', 0.0, 4.0)]))
        self.assertEqual(self.rows(_score(piece_type='melodic')), [])

    def test_a_missing_sheet_is_not_a_pass(self):
        sc = _score()
        rows = self.rows(sc)                       # direction/ is empty
        self.assertEqual(rows[0][1], 'scene.preset')
        self.assertIn('no direction sheet', rows[0][2])
        # every row the scene block would judge says it did not run: a missing sheet is never a pass
        self.assertTrue(all(r[0] == 'INFO' for r in rows))
        self.assertEqual(len(rows), 7)


class DeclaredRestIsSilent(SceneCase):
    def _wav(self, bursts, dur=6.0, sr=44100, bed=0.002):
        x = np.full((int(dur * sr), 2), bed, dtype=np.float64)
        for a, b in bursts:
            x[int(a * sr):int(b * sr)] = 0.5
        import soundfile as sf
        path = os.path.join(self.dir, 'mix.wav')
        sf.write(path, x, sr)
        return path

    def test_a_tone_inside_a_declared_rest_fails_the_row(self):
        self.write_sheet(_sheet([('top', 'peak', 0.0, 6.0)],
                                hits=[{"t": 2.0, "kind": "cut", "sync": "hard", "silence_after_s": 1.5}]))
        path = self._wav([(2.0, 3.5)])
        row = next(r for r in self.rows(_score(tracks=[_melody([(0, 1, 60)])]), path) if r[1] == 'scene.silence_honoured')
        self.assertEqual(row[0], 'FAIL')
        self.assertIn('declares silence', row[2])

    def test_silence_where_the_sheet_says_so_passes(self):
        self.write_sheet(_sheet([('top', 'peak', 0.0, 6.0)],
                                hits=[{"t": 4.6, "kind": "cut", "sync": "hard", "silence_after_s": 1.0}]))
        path = self._wav([(1.0, 2.0)])             # loud earlier, silent in the declared rest
        row = next(r for r in self.rows(_score(tracks=[_melody([(0, 1, 60)])]), path) if r[1] == 'scene.silence_honoured')
        self.assertEqual(row[0], 'PASS')


class WaivedCeilingIsNotJudged(SceneCase):
    def _leapy(self):
        # ten notes a fifth apart: 0 % stepwise, every interval inside the peak window (bpm 120 -> 0.5 s/beat)
        notes = [(4 + i, 1, 60 + (7 if i % 2 else 0)) for i in range(10)]
        return _score(tracks=[_melody(notes)])

    def test_without_a_waiver_the_line_fails(self):
        self.write_sheet(_sheet([('top', 'peak', 0.0, 8.0)]))
        rows = pa.cognitive_feel_checks(self._leapy())
        self.assertIn('FAIL', [lvl for lvl, name, _ in rows if name == 'melodic_contour_feel'])

    def test_a_peak_that_waives_the_row_is_not_judged(self):
        self.write_sheet(_sheet([('top', 'peak', 0.0, 8.0)]))
        sc = self._leapy()
        sc['gate'] = {"feel.contour": {"mode": "apply"}}
        rows = pa.cognitive_feel_checks(sc)
        self.assertIn('FAIL', [lvl for lvl, name, _ in rows if name == 'melodic_contour_feel'])
        # the shipped suspense profile waives feel.contour inside its peak; the same line then produces no FAIL
        base = json.load(open(os.path.join(HERE, '..', 'references', 'data', 'presets', 'gate',
                                           'cinematic_suspense.json'), encoding='utf-8'))
        prof_path = os.path.join(self.dir, 'presets', 'gate', 'cinematic_suspense.json')
        os.makedirs(os.path.dirname(prof_path), exist_ok=True)
        with open(prof_path, 'w', encoding='utf-8') as fh:
            json.dump(base, fh)
        presets.add_project(self.dir)
        rows = pa.cognitive_feel_checks(sc)
        self.assertNotIn('FAIL', [lvl for lvl, name, _ in rows if name == 'melodic_contour_feel'])


class OneSectionIsNotAskedForContrast(SceneCase):
    def test_single_role_is_skipped_unless_forced(self):
        self.write_sheet(_sheet([('only', 'peak', 0.0, 8.0)]))
        # sixteen notes across four bars: enough windows for the strain series to have a variance at all
        notes = [(i, 1, 60 + (i * 3) % 12) for i in range(16)]
        sc = _score(tracks=[_melody(notes)])
        row = next(r for r in self.rows(sc) if r[1] == 'scene.macro_contrast')
        self.assertEqual(row[0], 'INFO')
        self.assertIn('1 section', row[2])
        sc['gate'] = {"scene.macro_contrast": {"force": True}}
        row = next(r for r in self.rows(sc) if r[1] == 'scene.macro_contrast')
        self.assertIn('tension variance', row[2])

    def test_every_row_is_reported_for_a_declared_scene(self):
        self.write_sheet(_sheet([('open', 'establish', 0.0, 4.0), ('top', 'peak', 4.0, 8.0)],
                                hits=[{"t": 4.0, "kind": "cut", "sync": "hard"}]))
        names = [r[1] for r in self.rows(_score(tracks=[_melody([(0, 1, 60), (2, 1, 67), (4, 1, 64), (6, 1, 69)])]))]
        for want in ('scene.preset', 'scene.arc_step', 'scene.hit_surprise', 'scene.release_delta',
                     'scene.macro_contrast', 'scene.silence_honoured', 'scene.bed_stability'):
            self.assertIn(want, names)


if __name__ == '__main__':
    unittest.main()
