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

"""Unit tests for the video scoring path: the pure functions in `video-mixer/`.

Everything here runs without a project, a render or a video file, except one ffprobe-backed test that is skipped
when ffmpeg is missing. The end-to-end proof (cuts, mux identity, all four gate rows, and negative controls) is
`python scripts/video_score.py --selftest`.
"""
import os
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'video-mixer'))

import presets
import video_direction
import video_gate
import video_mux
import video_probe
import video_program_mix

CFG = presets.get('video', 'default')


def row(rows):
    """(level, name, detail) of the single row a test asked for."""
    assert len(rows) == 1, rows
    return rows[0]


class TestProbe(unittest.TestCase):
    def test_stream_facts_reads_seconds_and_fps(self):
        info = {'format': {'duration': '12.5'},
                'streams': [{'codec_type': 'video', 'avg_frame_rate': '24000/1001', 'width': 1920, 'height': 1080,
                             'codec_name': 'h264', 'nb_frames': '300'},
                            {'codec_type': 'audio', 'codec_name': 'aac'}]}
        f = video_probe.stream_facts(info)
        self.assertAlmostEqual(f['duration_s'], 12.5)
        self.assertAlmostEqual(f['fps'], 24000 / 1001, places=6)
        self.assertEqual((f['width'], f['height']), (1920, 1080))
        self.assertTrue(f['has_audio'])
        self.assertEqual(f['audio_streams'], 1)

    def test_stream_facts_without_video(self):
        f = video_probe.stream_facts({'format': {}, 'streams': [{'codec_type': 'audio'}]})
        self.assertFalse(f['has_video'])
        self.assertEqual(f['fps'], 0.0)

    def test_thin_keeps_the_first_of_each_window(self):
        kept = video_probe._thin([(0.0, 1.0), (0.1, 2.0), (1.0, 3.0)], 0.5)
        self.assertEqual([t for t, _ in kept], [0.0, 1.0])


class TestDirection(unittest.TestCase):
    dm = CFG['direction_map']

    def test_two_second_cut_interval_gives_a_frame_locked_tempo(self):
        tempo = video_direction.tempo_from_cuts([2.0, 4.0], self.dm, 25.0)
        self.assertEqual(tempo['bpm'], 125.0)
        self.assertEqual(tempo['frame_lock'], 12)
        self.assertAlmostEqual(25.0 * 60.0 / tempo['bpm'], 12.0)

    def test_tempo_stays_inside_the_preset_range(self):
        tc = self.dm['tempo_from_cuts']
        for interval in (0.2, 0.7, 1.3, 2.0, 3.1, 9.0):
            bpm = video_direction.tempo_from_cuts([0.0, interval], self.dm, 24.0)['bpm']
            self.assertGreaterEqual(bpm, tc['min_bpm'])
            self.assertLessEqual(bpm, tc['max_bpm'])

    def test_no_cut_falls_back_to_the_preset_preference(self):
        tempo = video_direction.tempo_from_cuts([], self.dm, 25.0)
        self.assertIn('no cut', tempo['method'])
        self.assertIsNone(tempo['frame_lock'])

    def test_luma_picks_the_mode(self):
        self.assertEqual(video_direction.mode_from_luma(0.1, self.dm), 'minor')
        self.assertEqual(video_direction.mode_from_luma(0.9, self.dm), 'major')

    def test_centre_of_motion_maps_to_azimuth(self):
        lo, hi = self.dm['centre_of_motion_to_pan']['range']
        limit = self.dm['centre_of_motion_to_pan']['max_azimuth_deg']
        self.assertAlmostEqual(video_direction.azimuth_from_centre(lo, self.dm), -limit)
        self.assertAlmostEqual(video_direction.azimuth_from_centre(hi, self.dm), limit)
        self.assertAlmostEqual(video_direction.azimuth_from_centre(0.0, self.dm), 0.0)

    def test_hits_keep_their_cut_or_motion_origin(self):
        rep = {'cuts': [{'t': 1.0}], 'motion_hits': [{'t': 4.0}]}
        hits = video_direction.hits_from_probe(rep, CFG, 60.0, 10.0)
        self.assertEqual([h['kind'] for h in hits], ['cut', 'motion'])
        self.assertEqual(hits[0]['sound'], CFG['hits']['cut_sound'])
        self.assertEqual(hits[1]['sound'], CFG['hits']['motion_sound'])

    def test_hits_closer_than_the_minimum_gap_are_thinned(self):
        rep = {'cuts': [{'t': 1.0}], 'motion_hits': [{'t': 1.1}]}
        self.assertEqual(len(video_direction.hits_from_probe(rep, CFG, 60.0, 10.0)), 1)

    def test_a_cut_is_a_hard_sync_and_a_movement_is_soft(self):
        rep = {'cuts': [{'t': 1.0}], 'motion_hits': [{'t': 4.0}]}
        hits = video_direction.hits_from_probe(rep, CFG, 60.0, 10.0)
        self.assertEqual([h['sync'] for h in hits], ['hard', 'soft'])

    def test_sheet_carries_the_director_blocks(self):
        rep = {'path': 'a/b.mp4', 'source': {'duration_s': 12.0, 'fps': 25.0, 'has_audio': True},
               'cuts': [{'t': 2.0}, {'t': 5.0}], 'motion_hits': [{'t': 3.5}],
               'energy': [0.1, 0.4, 0.9, 0.2], 'luma_mean': 0.4, 'warmth_mean': 0.0,
               'centre_mean': 0.0, 'cut_source': 'scdet'}
        sheet = video_direction.direction_sheet(rep, CFG, 'calm documentary')
        self.assertTrue(sheet['video']['enabled'])
        self.assertEqual(sheet['video']['source'], 'a/b.mp4')
        self.assertEqual(sheet['video']['cut_sync']['early_ms'], CFG['gate']['cut_sync']['early_ms'])
        self.assertTrue(sheet['video']['dialogue']['present'])
        self.assertEqual(len(sheet['sections']), len(rep['energy']))
        self.assertAlmostEqual(sheet['sections'][-1]['end_s'], 12.0, places=3)
        self.assertEqual([h['t'] for h in sheet['hits']], sheet['hits_at'])
        self.assertTrue(all(h['why'] for h in sheet['hits']))
        self.assertIn(sheet['ending'], ('hard_out', 'tail_out', 'combination'))
        self.assertTrue(sheet['job'] and sheet['mix_intent']['must_hear'])

    def test_a_picture_without_sound_does_not_claim_dialogue(self):
        rep = {'path': 'a/b.mp4', 'source': {'duration_s': 4.0, 'fps': 25.0, 'has_audio': False},
               'cuts': [], 'motion_hits': [], 'energy': [0.5, 0.6], 'luma_mean': 0.5, 'warmth_mean': 0.0,
               'centre_mean': 0.0, 'cut_source': 'scdet (no cut found)'}
        sheet = video_direction.direction_sheet(rep, CFG, '')
        self.assertFalse(sheet['video']['dialogue']['present'])
        self.assertEqual(sheet['mix_intent']['sits_under'], [])


class TestMuxArgs(unittest.TestCase):
    mux = CFG['mux']

    def test_known_container_gets_codec_and_bitrate(self):
        self.assertEqual(video_mux.audio_args(self.mux, 'mp4'), ['-c:a', 'aac', '-b:a', '320k'])

    def test_pcm_gets_no_bitrate(self):
        self.assertEqual(video_mux.audio_args(self.mux, 'mov'), ['-c:a', 'pcm_s24le', '-ar', '48000'])

    def test_unknown_container_is_an_error_not_a_guess(self):
        with self.assertRaises(KeyError):
            video_mux.audio_args(self.mux, 'flv')


class TestGateRows(unittest.TestCase):
    gate = CFG['gate']

    def probe(self, duration=6.0, cuts=(2.0, 4.0), has_audio=True):
        return {'source': {'duration_s': duration, 'has_audio': has_audio}, 'cuts': [{'t': c} for c in cuts]}

    def test_duration_inside_the_tolerance_passes(self):
        rows = []
        video_gate.duration_row(self.probe(), 6.02, self.gate, rows)
        self.assertEqual(row(rows)[0], 'PASS')

    def test_program_longer_than_the_picture_fails(self):
        rows = []
        video_gate.duration_row(self.probe(), 7.5, self.gate, rows)
        level, name, detail = row(rows)
        self.assertEqual((level, name), ('FAIL', 'video.duration_lock'))
        self.assertIn('+1500', detail)

    def test_cut_hit_on_its_cut_passes(self):
        rows = []
        video_gate.cut_sync_rows(self.probe(), [{'t_s': 2.0, 'kind': 'cut'}], self.gate, rows)
        self.assertEqual(row(rows)[0], 'PASS')

    def test_cut_hit_far_late_fails(self):
        rows = []
        video_gate.cut_sync_rows(self.probe(), [{'t_s': 2.3, 'kind': 'cut'}], self.gate, rows)
        self.assertEqual(row(rows)[0], 'FAIL')

    def test_motion_hits_are_not_judged_against_cuts(self):
        rows = []
        offsets = video_gate.cut_sync_rows(self.probe(), [{'t_s': 3.3, 'kind': 'motion'}], self.gate, rows)
        self.assertEqual(row(rows)[0], 'PASS')
        self.assertEqual(offsets, [])

    def test_early_hit_has_its_own_limit(self):
        rows = []
        video_gate.cut_sync_rows(self.probe(), [{'t_s': 1.9, 'kind': 'cut'}], self.gate, rows)
        self.assertEqual(row(rows)[0], 'FAIL')
        self.assertIn('-100', row(rows)[2])

    def test_dialogue_row_fails_when_the_bed_is_too_loud(self):
        rows = []
        video_gate.dialogue_row({'music_under_voice_db': 4.0}, self.probe(), self.gate, rows)
        self.assertEqual(row(rows)[0], 'FAIL')

    def test_dialogue_row_passes_a_silent_picture(self):
        rows = []
        video_gate.dialogue_row({}, self.probe(has_audio=False), self.gate, rows)
        self.assertEqual(row(rows)[0], 'PASS')


class TestProgramMix(unittest.TestCase):
    def test_master_profile_comes_from_the_named_profile(self):
        prof = video_program_mix.master_profile(CFG)
        self.assertEqual(prof['lufs'], CFG['master_profiles'][CFG['master']['profile']]['lufs'])
        self.assertEqual(prof['sample_rate'], CFG['master']['sample_rate'])

    def test_profile_override(self):
        prof = video_program_mix.master_profile(CFG, 'broadcast')
        self.assertEqual(prof['lufs'], CFG['master_profiles']['broadcast']['lufs'])
        self.assertEqual(prof['loudness_mode'], 'dialogue_gated')

    def test_swell_is_flat_without_hits_and_rises_before_one(self):
        cfg = CFG['mix']['swell']
        flat = video_program_mix.swell_curve(44100, [], cfg)
        self.assertTrue(np.allclose(flat, 1.0))
        raised = video_program_mix.swell_curve(44100 * 4, [2.0], cfg)
        self.assertAlmostEqual(float(raised.max()), 10 ** (cfg['pre_hit_db'] / 20.0), places=5)

    def test_tail_never_runs_past_the_picture(self):
        sr = 44100
        voice = np.zeros((sr * 6, 2), np.float32)
        voice[sr:2 * sr] = 0.3
        music = np.zeros((sr * 6, 2), np.float32) + 0.05
        mix = video_program_mix.build(voice, music, [], CFG['mix'], limit_s=6.0)[0]
        self.assertEqual(len(mix), sr * 6)


class TestFFprobe(unittest.TestCase):
    def test_keyframe_probe_returns_numbers(self):
        import shutil
        import tempfile
        import subprocess
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('ffmpeg not on PATH')
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'kf.mp4')
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=64x64:rate=10:duration=1',
                            '-c:v', 'libx264', '-g', '5', '-pix_fmt', 'yuv420p', p], check=True)
            self.assertTrue(all(isinstance(t, float) for t in video_probe.keyframe_times(p)))


if __name__ == '__main__':
    unittest.main()
