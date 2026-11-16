# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Dialogue gating: the master and the gate must measure the same thing.

Before this, `loudness_mode: dialogue_gated` was a label: both the master and the
gate measured the full program, so a Netflix -27 target was graded on a number
Netflix does not use.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'video-mixer'))

import mixer as mx                          # noqa: E402
import video_program_mix as vpm             # noqa: E402
from analysis import speech                 # noqa: E402
import presets                              # noqa: E402

ANALYSIS = presets.get('film', 'analysis')
SR = 44100


def program_with_loud_gap(duration=8.0):
    """Speech at 1-3 s and 5-7 s, and a loud non-speech passage at 3.2-4.8 s.

    The loud passage is what makes full-program and dialogue-gated loudness
    disagree; without it the two measurements are the same number and the test
    would prove nothing.
    """
    n = int(duration * SR)
    y = np.zeros((n, 1), np.float32)
    for a, b in ((1.0, 3.0), (5.0, 7.0)):
        i, j = int(a * SR), int(b * SR)
        t = np.arange(j - i) / SR
        env = np.minimum(1.0, np.minimum(t * 20.0, (t[-1] - t) * 20.0))
        f0 = 165.0 + 8.0 * np.sin(2 * np.pi * 3.5 * t)
        sig = sum(0.12 * np.sin(2 * np.pi * k * f0 * t) / k for k in (1, 2, 3, 4, 5))
        y[i:j, 0] = (sig * env).astype(np.float32)
    i, j = int(3.2 * SR), int(4.8 * SR)
    rng = np.random.default_rng(5)
    y[i:j, 0] = (0.5 * (rng.random(j - i) - 0.5)).astype(np.float32)
    return np.repeat(y, 2, axis=1)


class TestDialogueGatedLufs(unittest.TestCase):
    def setUp(self):
        self.y = program_with_loud_gap()
        act = speech.activity(self.y, SR, ANALYSIS)
        self.mask = speech.mask_at(act['mask'], act['times'], len(self.y), SR)

    def test_speech_is_actually_masked(self):
        self.assertGreater(float(self.mask.mean()), 0.2)
        self.assertLess(float(self.mask.mean()), 0.9)

    def test_gated_differs_from_full_program(self):
        full = mx.lufs(self.y, SR)
        gated = mx.dialogue_gated_lufs(self.y, SR, self.mask)
        self.assertIsNotNone(gated)
        self.assertLess(gated, full - 1.0)

    def test_no_mask_is_none_not_a_guess(self):
        self.assertIsNone(mx.dialogue_gated_lufs(self.y, SR, None))
        self.assertIsNone(mx.dialogue_gated_lufs(self.y, SR, np.zeros(len(self.y), np.float32)))

    def test_short_blips_are_ignored(self):
        blip = np.zeros(len(self.y), np.float32)
        blip[100:150] = 1.0
        self.assertIsNone(mx.dialogue_gated_lufs(self.y, SR, blip, min_seg_s=0.2))


class TestProgramMaster(unittest.TestCase):
    def setUp(self):
        self.y = program_with_loud_gap()
        act = speech.activity(self.y, SR, ANALYSIS)
        self.mask = speech.mask_at(act['mask'], act['times'], len(self.y), SR)
        self.cfg = {'lufs': -20.0, 'true_peak_db': -2.0}

    def test_dialogue_mode_reaches_the_dialogue_target(self):
        y, sr = vpm.master(self.y, self.cfg, SR, loudness_mode='dialogue', speech_mask=self.mask)
        gated = mx.dialogue_gated_lufs(y, sr, self.mask)
        self.assertIsNotNone(gated)
        self.assertLess(abs(gated - self.cfg['lufs']), 2.0)

    def test_full_program_mode_reaches_the_full_program_target(self):
        y, sr = vpm.master(self.y, self.cfg, SR, loudness_mode='full_program')
        self.assertLess(abs(mx.lufs(y, sr) - self.cfg['lufs']), 1.5)

    def test_the_two_modes_do_not_deliver_the_same_file(self):
        a, sr = vpm.master(self.y, self.cfg, SR, loudness_mode='full_program')
        b, _ = vpm.master(self.y, self.cfg, SR, loudness_mode='dialogue', speech_mask=self.mask)
        self.assertGreater(float(np.abs(a - b).max()), 1e-3)

    def test_dialogue_mode_without_speech_is_labelled_honestly(self):
        y, sr = vpm.master(self.y, self.cfg, SR, loudness_mode='dialogue', speech_mask=None)
        self.assertEqual(mx.STATE['master']['gating'], 'full_program')
        self.assertEqual(mx.STATE['master']['declared_gating'], 'dialogue')

    def test_unknown_mode_is_an_error(self):
        with self.assertRaises(ValueError):
            vpm.master(self.y, self.cfg, SR, loudness_mode='loudness_war')


class TestMixReport(unittest.TestCase):
    def test_the_band_figure_and_the_mask_segments_are_reported(self):
        y = program_with_loud_gap()
        voice = np.repeat(np.zeros((len(y), 1), np.float32), 2, axis=1)
        voice[int(1.0 * SR):int(2.0 * SR)] = 0.2
        cfg = presets.get('film', 'dialogue')
        mix, _, _, mask, rep = vpm.build(voice, y, [], cfg, limit_s=len(y) / SR)
        self.assertIn('music_under_voice_band_db', rep)
        self.assertIn('speech_segments', rep)
        self.assertTrue(rep['speech_segments'])
        first = rep['speech_segments'][0]
        self.assertLess(first[0], first[1])


if __name__ == '__main__':
    unittest.main()
