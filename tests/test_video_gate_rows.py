# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Every picture gate row must pass on good input and FAIL on bad input.

A row that cannot fail is not a row, so each class here has a negative control.
No project, no render: the rows are pure functions of numbers and files.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'video-mixer'))

import gate_profiles                 # noqa: E402
import presets                       # noqa: E402
from gate import pass_ as gate_pass  # noqa: E402
from gate import rows as R           # noqa: E402

DELIVERY = presets.get('film', 'delivery')
GATE = DELIVERY['gate']
HITS = presets.get('film', 'hits')


def single(rows):
    assert len(rows) == 1, rows
    return rows[0]


def tone(path, sr=44100, seconds=2.0, amp=0.1):
    t = np.arange(int(sr * seconds)) / sr
    y = (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, np.repeat(y[:, None], 2, axis=1), sr, subtype='PCM_24')
    return path


class TestPictureTime(unittest.TestCase):
    def test_duration_inside_tolerance_passes(self):
        rows = []
        R.duration_row({'source': {'duration_s': 6.0}}, 6.02, GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_program_longer_than_the_picture_fails(self):
        rows = []
        R.duration_row({'source': {'duration_s': 6.0}}, 7.5, GATE, rows)
        level, name, detail = single(rows)
        self.assertEqual((level, name), ('FAIL', 'video.duration_lock'))
        self.assertIn('+1500', detail)

    def test_cut_hit_on_its_cut_passes(self):
        rows = []
        R.cut_sync_row([2.0], [{'t_s': 2.0, 'kind': 'cut'}], GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_cut_hit_far_late_fails(self):
        rows = []
        R.cut_sync_row([2.0], [{'t_s': 2.3, 'kind': 'cut'}], GATE, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_early_hit_has_its_own_limit(self):
        rows = []
        R.cut_sync_row([2.0], [{'t_s': 1.9, 'kind': 'cut'}], GATE, rows)
        self.assertEqual(single(rows)[0], 'FAIL')
        self.assertIn('-100', single(rows)[2])

    def test_motion_hits_are_not_judged_against_cuts(self):
        rows = []
        offsets = R.cut_sync_row([2.0], [{'t_s': 3.3, 'kind': 'motion'}], GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')
        self.assertEqual(offsets, [])


class TestMotionSync(unittest.TestCase):
    def test_hit_inside_the_window_passes(self):
        rows = []
        R.motion_sync_row([{'t': 3.0}], [{'t_s': 3.1, 'kind': 'motion'}], GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_hit_outside_the_window_fails(self):
        rows = []
        R.motion_sync_row([{'t': 3.0}], [{'t_s': 3.4, 'kind': 'motion'}], GATE, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_no_movement_hit_passes_with_its_reason(self):
        rows = []
        R.motion_sync_row([{'t': 3.0}], [], GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')


class TestHitClass(unittest.TestCase):
    def test_dead_on_hit_on_the_frame_passes(self):
        rows = []
        R.hit_class_row([{'t': 1.0, 'class': 'dead_on', 'offset_s': 0.0}], HITS, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_dead_on_hit_off_the_frame_fails(self):
        rows = []
        R.hit_class_row([{'t': 1.0, 'class': 'dead_on', 'offset_s': 0.4}], HITS, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_reaction_hit_after_the_moment_passes(self):
        rows = []
        R.hit_class_row([{'t': 1.35, 'class': 'reaction', 'offset_s': 0.35}], HITS, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_reaction_hit_on_the_frame_fails(self):
        rows = []
        R.hit_class_row([{'t': 1.0, 'class': 'reaction', 'offset_s': 0.0}], HITS, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_unknown_class_fails(self):
        rows = []
        R.hit_class_row([{'t': 1.0, 'class': 'sorcery', 'offset_s': 0.0}], HITS, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_no_class_is_reported_as_not_run(self):
        rows = []
        R.hit_class_row([{'t': 1.0}], HITS, rows)
        self.assertEqual(single(rows)[0], 'INFO')


class TestGridPhase(unittest.TestCase):
    def test_tight_grid_passes(self):
        rows = []
        R.grid_phase_row({'worst_residual_ms': 10.0, 'tolerance_frames': 0.25}, GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_loose_grid_fails(self):
        rows = []
        R.grid_phase_row({'worst_residual_ms': 200.0, 'tolerance_frames': 5.0}, GATE, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_no_frame_rate_is_reported(self):
        rows = []
        R.grid_phase_row({'worst_residual_ms': 10.0}, GATE, rows)
        self.assertEqual(single(rows)[0], 'INFO')


class TestHitDensity(unittest.TestCase):
    def test_sparse_cue_passes(self):
        rows = []
        R.hit_density_row([{'t_s': 1.0}, {'t_s': 3.0}], [1.0, 3.0, 5.0], 60.0,
                          dict(GATE, density=HITS['density']), rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_over_budget_fails(self):
        many = [{'t_s': float(i)} for i in range(60)]
        rows = []
        R.hit_density_row(many, [float(i) for i in range(60)], 60.0,
                          dict(GATE, density=HITS['density']), rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_mickey_mousing_is_its_own_failure(self):
        # inside the per-minute budget, but every adjacent cut pair is hit
        cuts = [float(i) for i in range(0, 20)]
        hits = [{'t_s': c} for c in cuts]
        rows = []
        R.hit_density_row(hits, cuts, 120.0, dict(GATE, density=HITS['density']), rows)
        self.assertEqual(single(rows)[0], 'FAIL')
        self.assertIn('Mickey', single(rows)[2])


class TestCueSilence(unittest.TestCase):
    def test_real_silence_passes(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'silent.wav')
            sf.write(p, np.zeros((44100, 2), np.float32), 44100, subtype='PCM_24')
            rows = []
            R.cue_silence_row(p, [(0.1, 0.8)], GATE, rows)
            self.assertEqual(single(rows)[0], 'PASS')

    def test_music_in_a_silent_window_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = tone(os.path.join(td, 'loud.wav'), seconds=1.0)
            rows = []
            R.cue_silence_row(p, [(0.1, 0.8)], GATE, rows)
            self.assertEqual(single(rows)[0], 'FAIL')

    def test_no_silent_section_passes(self):
        rows = []
        R.cue_silence_row(None, [], GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')


class TestDialogue(unittest.TestCase):
    def probe(self, audio=True):
        return {'source': {'duration_s': 6.0, 'has_audio': audio}}

    def test_snr_below_the_floor_fails(self):
        rows = []
        R.dialogue_row({'music_under_voice_db': 4.0}, self.probe(), GATE, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_snr_above_the_floor_passes(self):
        rows = []
        R.dialogue_row({'music_under_voice_db': 18.0}, self.probe(), GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_a_silent_picture_passes_with_its_reason(self):
        rows = []
        R.dialogue_row({}, self.probe(audio=False), GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_speech_measured_but_no_figure_fails(self):
        rows = []
        R.dialogue_row({'speech_measured': True}, self.probe(), GATE, rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_band_under_the_voice_passes(self):
        rows = []
        R.dialogue_band_row({'music_under_voice_band_db': 18.0}, self.probe(), GATE, rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_band_over_the_consonants_fails(self):
        rows = []
        R.dialogue_band_row({'music_under_voice_band_db': 2.0}, self.probe(), GATE, rows)
        self.assertEqual(single(rows)[0], 'FAIL')


class TestShotScaleRow(unittest.TestCase):
    mapping = presets.get('film', 'mapping')

    def test_a_close_up_with_a_lead_passes(self):
        rows = []
        R.shot_scale_row([{'name': 's', 'shot_scale': 'close', 'density': 0.3}], [],
                         dict(self.mapping, tolerance=0.15), rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_a_full_band_in_a_close_up_fails(self):
        rows = []
        R.shot_scale_row([{'name': 's', 'shot_scale': 'close', 'density': 0.9}], [],
                         dict(self.mapping, tolerance=0.15), rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_no_scale_is_reported_as_not_run(self):
        rows = []
        R.shot_scale_row([{'name': 's', 'density': 0.5}], [], dict(self.mapping, tolerance=0.15), rows)
        self.assertEqual(single(rows)[0], 'INFO')


class TestGating(unittest.TestCase):
    def test_declared_matches_measured(self):
        rows = []
        R.gating_mode_row({'loudness_mode': 'dialogue'}, 'dialogue', rows)
        self.assertEqual(single(rows)[0], 'PASS')

    def test_a_claimed_gate_that_was_not_applied_fails(self):
        rows = []
        R.gating_mode_row({'loudness_mode': 'dialogue'}, 'full_program', rows)
        self.assertEqual(single(rows)[0], 'FAIL')

    def test_dialogue_target_without_speech_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = tone(os.path.join(td, 'p.wav'))
            rows = []
            R.master_row(p, {'loudness_mode': 'dialogue', 'lufs': -27.0, 'true_peak_db': -2.0},
                         GATE, rows, mask=None)
            self.assertEqual(single(rows)[0], 'FAIL')


class TestRegistration(unittest.TestCase):
    def test_every_row_is_registered(self):
        for rid in ('video.duration_lock', 'video.cut_sync', 'video.motion_sync', 'video.hit_class',
                    'video.grid_phase', 'video.hit_density', 'video.cue_silence', 'video.dialogue_snr',
                    'video.dialogue_band', 'video.shot_scale', 'video.master_compliance', 'video.gating_mode'):
            self.assertIn(rid, gate_profiles.ROWS, rid)

    def test_protected_rows_cannot_be_relaxed(self):
        for rid in ('video.duration_lock', 'video.master_compliance', 'video.gating_mode'):
            self.assertTrue(gate_profiles.ROWS[rid].get('protected'), rid)

    def test_the_film_profiles_resolve(self):
        for name in ('video_basic', 'video_dialogue', 'video_montage', 'video_underscore', 'video_trailer'):
            p = gate_profiles.resolve({'piece_type': name})
            self.assertEqual(p.errors, [], name)
            self.assertTrue(p.on('video.cut_sync'), name)

    def test_a_score_cannot_silence_a_protected_picture_row(self):
        p = gate_profiles.resolve({'piece_type': 'video_basic',
                                   'gate': {'video.duration_lock': {'mode': 'skip', 'reason': 'too long'}}})
        self.assertEqual(p.mode('video.duration_lock'), 'apply')

    def test_gate_presets_are_valid(self):
        self.assertEqual(gate_profiles.problems(), [])


class TestPassRows(unittest.TestCase):
    def test_a_pass_returns_rows_and_extras(self):
        with tempfile.TemporaryDirectory() as td:
            p = tone(os.path.join(td, 'program.wav'), seconds=2.0, amp=0.02)
            score = {'bpm': 120, 'video': {'enabled': True, 'duration_s': 2.0, 'cuts': [0.5, 1.0],
                                           'hits': [{'t_s': 0.5, 'kind': 'cut'}], 'motion_beats': []}}
            rows, extras = gate_pass.pass_rows(score,
                                               probe={'source': {'duration_s': 2.0, 'has_audio': False},
                                                      'cuts': [{'t': 0.5}, {'t': 1.0}]},
                                               program_wav=p, mix_report={},
                                               gating=GATE, master_profile={'loudness_mode': 'full_program',
                                                                            'lufs': -14.0, 'true_peak_db': -1.5})
            names = [r[1] for r in rows]
            self.assertIn('video.duration_lock', names)
            self.assertIn('video.gating_mode', names)
            self.assertEqual(extras['gating_mode'], 'full_program')

    def test_score_rows_need_only_a_score(self):
        import video_gate_pipeline
        score = {'video': {'enabled': True, 'duration_s': 10.0, 'cuts': [2.0, 5.0, 8.0],
                           'hits': [{'t_s': 2.0, 'kind': 'cut', 'class': 'dead_on', 'offset_s': 0.0},
                                    {'t_s': 5.0, 'kind': 'cut', 'class': 'dead_on', 'offset_s': 0.0}],
                           'gate_cfg': GATE, 'hits_cfg': HITS}}
        rows = video_gate_pipeline.score_rows(score)
        names = {r[1] for r in rows}
        self.assertIn('video.cut_sync', names)
        self.assertFalse([r for r in rows if r[0] == 'FAIL'], rows)


if __name__ == '__main__':
    unittest.main()
