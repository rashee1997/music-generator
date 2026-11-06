# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Unit tests for the video context model: the pure measurements in `video-mixer/analysis` and `context.py`.

No video file, no project, no render. The end-to-end proof is
`python scripts/video_score.py --selftest`.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'video-mixer'))

import presets                      # noqa: E402
import context as context_mod       # noqa: E402
from analysis import shot_scale     # noqa: E402
from analysis import speech         # noqa: E402

ANALYSIS = presets.get('film', 'analysis')
MAPPING = presets.get('film', 'mapping')


def speech_like(sr=44100, bursts=((0.4, 1.1), (3.2, 4.4)), duration=6.0):
    n = int(duration * sr)
    y = np.zeros((n, 1), np.float32)
    for a, b in bursts:
        i, j = int(a * sr), min(int(b * sr), n)
        if j <= i:
            continue
        t = np.arange(j - i) / sr
        env = np.minimum(1.0, np.minimum(t * 30.0, (t[-1] - t) * 30.0))
        f0 = 170.0 + 10.0 * np.sin(2 * np.pi * 4.0 * t)
        sig = sum(0.3 * np.sin(2 * np.pi * k * f0 * t) / k for k in (1, 2, 3, 4, 5))
        y[i:j, 0] = (sig * env).astype(np.float32)
    return y, sr


class TestCutPhase(unittest.TestCase):
    def test_cuts_on_a_grid_give_that_grids_offset(self):
        phase = context_mod.cut_phase([0.5, 1.5, 2.5, 3.5], 60.0, 25.0)
        self.assertAlmostEqual(phase['offset_s'], 0.5, places=3)
        self.assertLess(phase['worst_residual_ms'], 1.0)
        self.assertGreater(phase['confidence'], 0.9)

    def test_jittered_cuts_keep_a_positive_worst_residual(self):
        phase = context_mod.cut_phase([0.5, 1.53, 2.46], 60.0, 25.0)
        self.assertGreater(phase['worst_residual_ms'], 10.0)
        self.assertLess(phase['confidence'], 1.0)

    def test_one_cut_is_not_a_grid(self):
        phase = context_mod.cut_phase([1.0], 60.0, 25.0)
        self.assertEqual(phase['confidence'], 0.0)
        self.assertEqual(phase['cuts'], 1)

    def test_frame_residual_is_reported_in_frames(self):
        phase = context_mod.cut_phase([0.5, 1.5, 2.5], 60.0, 25.0)
        self.assertLess(phase['tolerance_frames'], 0.1)


class TestShotsAndScenes(unittest.TestCase):
    def test_shots_cover_the_whole_picture(self):
        shots = context_mod.shots_from_cuts([2.0, 5.0], 10.0)
        self.assertEqual(shots, [(0.0, 2.0), (2.0, 5.0), (5.0, 10.0)])

    def test_a_long_take_ends_a_scene(self):
        shots = [(0.0, 1.0), (1.0, 12.0), (12.0, 13.0), (13.0, 14.0)]
        scenes = context_mod.group_scenes(shots, [], ANALYSIS)
        self.assertGreaterEqual(len(scenes), 2)
        self.assertAlmostEqual(scenes[0]['end_s'], 12.0, places=2)

    def test_scene_energy_is_normalised(self):
        shots = [(0.0, 2.0), (2.0, 4.0)]
        hits = [{'t': 0.5, 'strength': 0.01}, {'t': 2.5, 'strength': 0.09}]
        scenes = context_mod.group_scenes(shots, hits, ANALYSIS)
        self.assertLessEqual(max(s['energy'] for s in scenes), 1.0)
        self.assertGreaterEqual(min(s['energy'] for s in scenes), 0.0)

    def test_scenes_carry_the_keys_the_rows_need(self):
        scenes = context_mod.group_scenes([(0.0, 3.0)], [], ANALYSIS)
        for k in ('id', 'start_s', 'end_s', 'shot_scale', 'speech_activity', 'energy', 'music_gap', 'motion'):
            self.assertIn(k, scenes[0])


class TestShotScale(unittest.TestCase):
    def test_a_flat_frame_has_no_subject(self):
        self.assertEqual(shot_scale.classify(np.full((90, 160), 0.5, np.float32), ANALYSIS)[0], 'insert')

    def test_a_detailed_full_frame_reads_wider_than_a_small_subject(self):
        rng = np.random.default_rng(3)
        wide = rng.random((90, 160)).astype(np.float32)
        close = np.full((90, 160), 0.5, np.float32)
        close[35:55, 70:90] = rng.random((20, 20)).astype(np.float32)
        w, w_share = shot_scale.classify(wide, ANALYSIS)
        c, c_share = shot_scale.classify(close, ANALYSIS)
        self.assertGreater(w_share, c_share)
        self.assertIn(w, shot_scale.SCALES)
        self.assertIn(c, shot_scale.SCALES)

    def test_scale_can_be_disabled(self):
        cfg = dict(ANALYSIS, shot_scale=dict(ANALYSIS['shot_scale'], enabled=False))
        self.assertEqual(shot_scale.classify(np.zeros((10, 10), np.float32), cfg)[0], 'medium')

    def test_scene_scale_takes_the_majority(self):
        rng = np.random.default_rng(4)
        wide = rng.random((90, 160)).astype(np.float32)
        close = np.full((90, 160), 0.5, np.float32)
        close[38:52, 74:86] = rng.random((14, 12)).astype(np.float32)
        out = shot_scale.scene_scale([wide, wide, close], ANALYSIS)
        self.assertEqual(out['scale'], 'wide')
        self.assertEqual(out['frames'], 3)
        self.assertEqual(out['scale_source'], 'measured')

    def test_no_frame_is_said_so(self):
        out = shot_scale.scene_scale([], ANALYSIS)
        self.assertEqual(out['scale_source'], 'no frame sampled')


class TestSpeech(unittest.TestCase):
    def test_bursts_are_found(self):
        y, sr = speech_like()
        act = speech.activity(y, sr, ANALYSIS)
        self.assertGreaterEqual(len(act['segments']), 2)
        self.assertLessEqual(len(act['segments']), 3)
        self.assertGreater(act['share'], 0.15)
        self.assertLess(act['share'], 0.75)

    def test_silence_has_no_speech(self):
        act = speech.activity(np.zeros((44100 * 3, 1), np.float32), 44100, ANALYSIS)
        self.assertEqual(act['segments'], [])
        self.assertEqual(act['share'], 0.0)

    def test_a_flat_noise_is_not_speech(self):
        rng = np.random.default_rng(11)
        noise = (rng.random((44100 * 3, 1)).astype(np.float32) - 0.5) * 0.4
        act = speech.activity(noise, 44100, ANALYSIS)
        self.assertLess(act['share'], 0.5)

    def test_mask_at_is_per_sample(self):
        y, sr = speech_like(duration=3.0)
        act = speech.activity(y, sr, ANALYSIS)
        m = speech.mask_at(act['mask'], act['times'], len(y), sr)
        self.assertEqual(len(m), len(y))
        self.assertTrue(set(np.unique(m)).issubset({0.0, 1.0}))
        self.assertGreater(m.mean(), 0.1)


class TestBuild(unittest.TestCase):
    def probe(self, duration=12.0, cuts=(2.0, 5.0, 9.0), audio=True):
        return dict(path='a/b.mp4', source=dict(duration_s=duration, fps=25.0, has_audio=audio),
                    cuts=[dict(t=c) for c in cuts],
                    motion_hits=[dict(t=3.0, strength=0.02), dict(t=9.5, strength=0.05)],
                    energy=[0.2, 0.5, 0.9, 0.3], luma_mean=0.4, warmth_mean=0.1,
                    motion_mean=0.04, centre_mean=0.0, cut_source='scdet')

    def test_context_has_three_timescales(self):
        ctx = context_mod.build(self.probe(), ANALYSIS, MAPPING)
        self.assertIn('reel', ctx)
        self.assertTrue(ctx['scenes'])
        self.assertIn('cut_phase', ctx)
        self.assertEqual(ctx['reel']['cuts'], 3)
        self.assertEqual(ctx['reel']['palette']['temperature'], 'warm')

    def test_scene_of_finds_the_window(self):
        ctx = context_mod.build(self.probe(), ANALYSIS, MAPPING)
        scene = context_mod.scene_of(ctx, 3.0)
        self.assertIsNotNone(scene)
        self.assertTrue(scene['start_s'] <= 3.0 < scene['end_s'])
        self.assertIsNone(context_mod.scene_of(ctx, 999.0))

    def test_text_on_screen_is_not_guessed(self):
        ctx = context_mod.build(self.probe(), ANALYSIS, MAPPING)
        self.assertIsNone(ctx['reel']['text_on_screen'])

    def test_speech_fills_scene_activity(self):
        y, sr = speech_like(duration=12.0, bursts=((2.1, 3.9),))
        act = speech.activity(y, sr, ANALYSIS)
        ctx = context_mod.build(self.probe(), ANALYSIS, MAPPING, speech=act)
        self.assertTrue(any(s['speech_activity'] > 0 for s in ctx['scenes']))
        self.assertGreater(ctx['reel']['speech_share'], 0)

    def test_silence_windows_come_from_the_spotting(self):
        ctx = context_mod.build(self.probe(), ANALYSIS, MAPPING)
        ctx['scenes'][0]['music_gap'] = True
        windows = context_mod.silence_windows(ctx)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0][0], ctx['scenes'][0]['start_s'])
        self.assertEqual(context_mod.silence_windows(ctx['scenes']), windows)


if __name__ == '__main__':
    unittest.main()
