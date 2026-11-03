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
"""test_extraction_pipeline.py - the whole orchestrator on a short synthetic song with a known music_db: every stage runs,
every output lands in the project, the presets load through clone_instrument."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', 'scripts')))
import test_extraction_drums as D  # noqa: E402
import test_extraction_separate as S  # noqa: E402

PIPE = os.path.abspath(os.path.join(HERE, '..', 'scripts', 'extract_pipeline.py'))
SR = 22050


def write(folder, name, obj):
    with open(os.path.join(folder, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f)


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='test_extract_pipe_')
        stems, mix = S.build()
        drums = D.build()
        n = int(8 * SR)
        song = np.zeros((2, n))
        song[:, :mix.shape[1]] += mix
        for v in drums.values():
            song += np.stack([v[:n], v[:n]])
        song_path = os.path.join(cls.tmp, 'song.wav')
        sf.write(song_path, song.T.astype('float32'), SR)
        cls.proj = os.path.join(cls.tmp, 'proj')
        cls.run_cmd('setup', '--new-project', cls.proj, '--song', song_path, '--no-env')
        db = os.path.join(cls.proj, 'music_db')
        write(db, 'song.json', {'schema': 'music_db.song/1', 'duration_s': 8.0, 'tempo_bpm': {'value': 100.0}, 'time_signature': '4/4',
                                'sections': [{'name': 'a', 'start_s': 0, 'end_s': 8}]})
        ranges = S.RANGES
        write(db, 'instruments.json', {'schema': 'music_db.instruments/1', 'instruments': [
            {'id': k, 'family': 'synth', 'range': {'lowest_note': f'{["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"][lo % 12]}{lo // 12 - 1}',
                                                   'highest_note': f'{["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"][hi % 12]}{hi // 12 - 1}'},
             'pitch_behavior': {'tuning_offset_cents': 35}} for k, (lo, hi) in ranges.items()]})
        write(db, 'drums.json', {'schema': 'music_db.drums/1', 'pieces': [
            {'id': 'kick_main', 'kind': 'kick', 'centroid_hz': 140}, {'id': 'snare_main', 'kind': 'snare', 'centroid_hz': 1850},
            {'id': 'hat_closed', 'kind': 'hat_closed', 'centroid_hz': 6800}]})
        write(db, 'effects.json', {'schema': 'music_db.effects/1', 'events': []})
        cls.run_cmd('run', cls.proj, '--set', 'analysis.sr=22050', '--max-attempts', '1')

    @classmethod
    def run_cmd(cls, *args):
        r = subprocess.run([sys.executable, '-W', 'error::ResourceWarning', PIPE, *args], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'{args}: {r.stdout[-1500:]}\n{r.stderr[-1500:]}')
        return r.stdout

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def p(self, *a):
        return os.path.join(self.proj, *a)

    def test_outputs_exist(self):
        for f in ('out/stems/bass.wav', 'out/stems/lead.wav', 'out/stems/drums.wav', 'out/stems/ambient.wav', 'out/stems/effects.wav',
                  'out/stems/unmodelled.wav', 'out/mix_resynth.wav', 'out/midi/song.mid', 'out/midi/drums.mid', 'reports/extraction_report.json',
                  'reports/gate.json', 'reports/spatial.json', 'reports/voices.json', 'reports/drums.json', 'reports/resynth.json',
                  'presets/instruments/bass.json'):
            self.assertTrue(os.path.isfile(self.p(*f.split('/'))), f)

    def test_no_pile_of_files(self):
        stems = [f for f in os.listdir(self.p('out', 'stems')) if f.endswith('.wav')]
        self.assertLessEqual(len(stems), 12, stems)                      # voices + drums, ambient, effects, unmodelled
        self.assertFalse(os.path.exists(self.p('out', 'raw')))           # the mask-cut stems are written only with export.keep_raw
        self.assertFalse(os.path.exists(self.p('out', 'enhanced')))
        self.assertFalse([f for f in stems if f.startswith(('fx_', 'drum_', 'percussive', 'residual', 'ambient_'))], stems)

    def test_report_has_gate_rows_and_voices(self):
        with open(self.p('reports', 'extraction_report.json'), encoding='utf-8') as f:
            rep = json.load(f)
        self.assertIn('bass', rep['voices'])
        self.assertTrue(rep['gate']['rows'])
        checks = {r['check'] for r in rep['gate']['rows']}
        for want in ('magnitude_match', 'drum_fidelity', 'ambient_match', 'midi_short_notes', 'natural:summary', 'tonal_balance', 'roughness', 'clicks'):
            self.assertIn(want, checks)
        self.assertTrue(any(c.startswith('voice_fidelity:') for c in checks))
        self.assertFalse([r for r in rep['gate']['rows'] if 'check crashed' in r['detail']], 'a gate check crashed')
        self.assertNotIn('explained_energy', checks)                    # the circular row is gone

    def test_presets_load_through_the_clone_route_and_play(self):
        import clone_instrument as ci
        inst = ci.load_instrument(self.p('presets', 'clones', 'lead'))
        y = ci.render_events(inst, [{'t': 0.0, 'dur': 0.5, 'p': 72, 'v': 90}])
        self.assertGreater(float(np.abs(y).max()), 0.05)
        with open(self.p('presets', 'instruments', 'lead.json'), encoding='utf-8') as f:
            pre = json.load(f)
        self.assertLess(pre['spatial']['azimuth'], 0)                      # the lead was panned left
        self.assertTrue(pre['clone'])

    def test_status_is_updated_and_status_command_works(self):
        out = self.run_cmd('status', self.proj)
        self.assertIn('done in', out)
        with open(self.p('STATUS.md'), encoding='utf-8') as f:
            self.assertIn('ran', f.read())


if __name__ == '__main__':
    unittest.main()
