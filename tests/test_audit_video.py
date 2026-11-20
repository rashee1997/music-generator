# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""One test per defect found by the video mixer audit. Each fails on the code as it was and passes on the fix."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import soundfile as sf

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'video-mixer'))
sys.path.insert(0, str(SK / 'tests'))

import mixer as mx                      # noqa: E402
import presets                          # noqa: E402
import video_probe                      # noqa: E402
import video_direction                  # noqa: E402
import video_program_mix as vpm         # noqa: E402
import context as context_mod           # noqa: E402
import video_gate_pipeline              # noqa: E402
from analysis import speech, shot_scale  # noqa: E402
from deliver import reel                # noqa: E402
from gate import rows as R              # noqa: E402
from gate import pass_ as P             # noqa: E402

SR = 8000
DELIVERY = presets.get('film', 'delivery')
GATE = DELIVERY['gate']


def wav(path, seconds, amp=0.2, sr=SR):
    t = np.arange(int(sr * seconds)) / sr
    y = (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(path), np.repeat(y[:, None], 2, axis=1), sr, subtype='PCM_24')
    return path


# ---------------------------------------------------------------- 1, 2: the reel
class TestReel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.film = Path(self.tmp.name)
        for c in ('A', 'C'):
            (self.film / 'cues' / c / 'reports').mkdir(parents=True)
            wav(self.film / 'cues' / c / 'master.wav', 1.0)

    def tearDown(self):
        self.tmp.cleanup()

    def sheet(self, cues):
        return {'cues': cues}

    def report(self, cue, status, fails=0):
        (self.film / 'cues' / cue / 'reports' / 'ci_report.json').write_text(
            json.dumps({'status': status, 'ci_summary': {'fail': fails}}), encoding='utf-8')

    def test_overlap_is_found_past_an_unplaced_silent_row(self):
        data = self.sheet([
            dict(id='A', in_s=0.0, duration_s=100.0, master='cues/A/master.wav'),
            dict(id='S', in_s=20.0, duration_s=10.0, silence=True),
            dict(id='C', in_s=50.0, duration_s=10.0, master='cues/C/master.wav')])
        _, rep = reel.assemble(data, str(self.film), 120.0, {'sample_rate': SR})
        self.assertEqual([(o['a'], o['b']) for o in rep['overlaps']], [('A', 'C')])

    def test_uncertified_cue_is_not_assembled_and_fails_the_reel(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=1.0, master='cues/A/master.wav'),
                           dict(id='C', in_s=2.0, duration_s=1.0, master='cues/C/master.wav')])
        self.report('A', 'PASSED')
        self.report('C', 'FAILED', fails=2)
        reports = reel.load_cue_reports(data, str(self.film))
        audio, rep = reel.assemble(data, str(self.film), 4.0, {'sample_rate': SR}, cue_reports=reports)
        self.assertEqual(rep['placed'], 1)
        self.assertLess(float(np.abs(audio[int(2.2 * SR):int(2.8 * SR)]).max()), 1e-6)
        rows = reel.reel_rows(rep)
        self.assertEqual({n: l for l, n, _ in rows}['reel.placement'], 'FAIL')
        ver = reel.reel_verdict(list(reports.values()), rows)
        self.assertEqual(ver['status'], 'FAILED')
        self.assertEqual(ver['cue_fails'], 2)
        self.assertEqual(ver['uncertified_cues'], ['C'])

    def test_missing_cue_report_is_uncertified(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=1.0, master='cues/A/master.wav')])
        reports = reel.load_cue_reports(data, str(self.film))
        self.assertIsNone(reports['A'])
        _, rep = reel.assemble(data, str(self.film), 2.0, {'sample_rate': SR}, cue_reports=reports)
        self.assertEqual(rep['placed'], 0)

    def test_certified_cues_make_a_passing_reel(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=1.0, master='cues/A/master.wav')])
        self.report('A', 'PASSED')
        reports = reel.load_cue_reports(data, str(self.film))
        _, rep = reel.assemble(data, str(self.film), 2.0, {'sample_rate': SR}, cue_reports=reports)
        self.assertEqual(reel.reel_verdict(list(reports.values()), reel.reel_rows(rep))['status'], 'PASSED')


# ---------------------------------------------------------------- 3: hits
class TestHits(unittest.TestCase):
    CFG = {'hits': dict(cut_sound='sfx:impact', motion_sound='sfx:whoosh', cut_velocity=0.9, motion_velocity=0.7,
                        min_gap_beats=1.0, max_hits_per_minute=24)}

    def test_a_motion_hit_cannot_block_a_cut(self):
        rep = dict(cuts=[dict(t=10.0)], motion_hits=[dict(t=9.95)])
        kept, dropped = video_direction.plan_hits(rep, self.CFG, 300.0, 60.0)     # min gap 0.2 s
        self.assertEqual([(h['t_s'], h['kind']) for h in kept], [(10.0, 'cut')])
        self.assertEqual(dropped, [])

    def test_a_cut_lost_to_the_budget_is_recorded_and_warned(self):
        cfg = {'hits': dict(self.CFG['hits'], max_hits_per_minute=2)}
        rep = dict(cuts=[dict(t=float(t)) for t in (1, 3, 5, 7)], motion_hits=[dict(t=2.0)])
        kept, dropped = video_direction.plan_hits(rep, cfg, 300.0, 30.0)           # budget 1
        self.assertEqual([h['t_s'] for h in kept], [1.0])
        self.assertEqual([d['reason'] for d in dropped], ['budget'] * 3)
        out = []
        R.cut_sync_row([1, 3, 5, 7], kept, GATE, out, dropped=dropped)
        self.assertEqual(out[0][0], 'WARN')
        self.assertIn('3 cut(s) left without a hit', out[0][2])

    def test_a_close_cut_pair_is_recorded_as_min_gap(self):
        rep = dict(cuts=[dict(t=5.0), dict(t=5.1)], motion_hits=[])
        kept, dropped = video_direction.plan_hits(rep, self.CFG, 300.0, 60.0)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped[0]['reason'], 'min_gap')


# ---------------------------------------------------------------- 4, 5: gating mode
class TestGatingApplied(unittest.TestCase):
    def setUp(self):
        t = np.arange(int(2.0 * 44100)) / 44100
        self.y = np.repeat((0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)[:, None], 2, axis=1)
        self.mask = np.ones(len(self.y), np.float32)
        self.cfg = dict(lufs=-27.0, true_peak_db=-2.0, sample_rate=44100)

    def test_master_reports_the_applied_mode(self):
        res = vpm.master(self.y, self.cfg, 44100, loudness_mode='full_program')
        self.assertEqual(res.applied, 'full_program')
        y, sr = res                                           # still unpackable as a pair
        self.assertEqual(sr, 44100)

    def test_an_unconverged_gate_is_not_reported_as_dialogue(self):
        with mock.patch.object(mx, 'dialogue_gated_lufs', return_value=-10.0):    # never reaches -27
            res = vpm.master(self.y, self.cfg, 44100, loudness_mode='dialogue', speech_mask=self.mask)
        self.assertEqual(res.applied, 'full_program')

    def test_a_converged_gate_is_dialogue(self):
        res = vpm.master(self.y, self.cfg, 44100, loudness_mode='dialogue', speech_mask=self.mask)
        self.assertEqual(res.applied, 'dialogue')

    def _rows(self, applied):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'p.wav'
            wav(p, 2.0, 0.05, 44100)
            prof = dict(loudness_mode='dialogue', lufs=-27.0, true_peak_db=-2.0)
            score = dict(video=dict(enabled=True, duration_s=2.0), master={})
            rows, extras = P.pass_rows(score, program_wav=str(p), gating=dict(GATE), master_profile=prof,
                                       mapping=presets.get('film', 'mapping'), applied_mode=applied)
        return {n: l for l, n, _ in rows}, extras

    def test_gating_row_fails_when_the_master_fell_back(self):
        self.assertEqual(self._rows('full_program')[0]['video.gating_mode'], 'FAIL')

    def test_gating_row_fails_when_nothing_was_reported(self):
        rows, extras = self._rows(None)
        self.assertEqual(rows['video.gating_mode'], 'FAIL')
        self.assertEqual(extras['gating_mode'], 'unreported')

    def test_gating_row_passes_when_dialogue_was_applied(self):
        self.assertEqual(self._rows('dialogue')[0]['video.gating_mode'], 'PASS')


# ---------------------------------------------------------------- 6: duration lock
class TestDurationLock(unittest.TestCase):
    def test_score_length_is_compared_with_the_picture(self):
        score = dict(video=dict(enabled=True, duration_s=30.0, picture_duration_s=30.0,
                                score_duration_s=28.0, gate_cfg=dict(GATE), hits_cfg={}, hits=[], cuts=[]))
        rows = {n: l for l, n, _ in video_gate_pipeline.score_rows(score)}
        self.assertEqual(rows['video.duration_lock'], 'FAIL')

    def test_without_two_lengths_the_row_does_not_pass(self):
        score = dict(video=dict(enabled=True, duration_s=30.0, gate_cfg=dict(GATE), hits_cfg={}, hits=[], cuts=[]))
        rows = {n: l for l, n, _ in video_gate_pipeline.score_rows(score)}
        self.assertEqual(rows['video.duration_lock'], 'INFO')

    def test_score_from_sheet_writes_the_picture_length(self):
        import inspect
        self.assertIn("picture_duration_s", inspect.getsource(video_direction.score_from_sheet))


# ---------------------------------------------------------------- 7: motion sync
class TestMotionSync(unittest.TestCase):
    def test_hits_judged_against_themselves_are_not_a_pass(self):
        out = []
        R.motion_sync_row([{'t': 3.0}], [{'t_s': 3.0, 'kind': 'motion'}], GATE, out, independent=False)
        self.assertEqual(out[0][0], 'INFO')

    def test_independent_beats_can_fail(self):
        out = []
        R.motion_sync_row([{'t': 3.0}], [{'t_s': 3.5, 'kind': 'motion'}], GATE, out, independent=True)
        self.assertEqual(out[0][0], 'FAIL')

    def test_probe_rows_without_peaks_say_not_measured(self):
        score = dict(video=dict(enabled=True, duration_s=60.0, gate_cfg=dict(GATE), hits_cfg={},
                                hits=[dict(t_s=3.0, kind='motion')], motion_beats=[dict(t=3.0)],
                                shot_scale_max_density=None))
        rows = P.probe_rows(score, mapping=presets.get('film', 'mapping'))
        self.assertEqual({n: l for l, n, _ in rows}['video.motion_sync'], 'INFO')

    def test_motion_peaks_are_local_maxima_without_threshold(self):
        peaks = video_probe.motion_peaks(dict(fps=10.0, motion=[0.0, 0.1, 0.0, 0.05, 0.0, 0.2, 0.1]))
        self.assertEqual([round(t, 2) for t, _ in peaks], [0.1, 0.3, 0.5])


# ---------------------------------------------------------------- 8: context, silence, mapping
class TestRowInputs(unittest.TestCase):
    PROBE = dict(source=dict(duration_s=20.0, fps=25.0, has_audio=False), cuts=[dict(t=9.0)], motion_hits=[],
                 luma_mean=0.4, luma_min=0.1, luma_max=0.9, path='x.mp4')

    def test_luma_range_comes_from_the_probe(self):
        ctx = context_mod.build(self.PROBE, presets.get('film', 'analysis'), presets.get('film', 'mapping'))
        self.assertEqual(ctx['reel']['luma_range'], [0.1, 0.9])

    def test_spotting_silence_marks_scenes_and_reaches_the_row(self):
        ctx = context_mod.build(self.PROBE, presets.get('film', 'analysis'), presets.get('film', 'mapping'),
                                silence=[(9.0, 20.0)])
        self.assertEqual([s['music_gap'] for s in ctx['scenes']], [False, True])
        self.assertEqual(ctx['silence_windows'], [(9.0, 20.0)])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'p.wav'
            wav(p, 20.0, 0.3)
            out = []
            R.cue_silence_row(str(p), ctx['silence_windows'], GATE, out)
        self.assertEqual(out[0][0], 'FAIL')

    def test_shot_scale_caps_come_from_the_mapping(self):
        cfg = P._shot_scale_cfg(dict(GATE), presets.get('film', 'mapping'))
        self.assertIn('close', cfg['shot_scale_max_density'])

    def test_a_missing_film_mapping_is_an_error(self):
        with mock.patch.object(presets, 'get', side_effect=KeyError('film/mapping')):
            with self.assertRaises(KeyError):
                P._mapping(None)

    def test_missing_caps_are_an_error_not_info(self):
        with self.assertRaises(ValueError):
            P._shot_scale_cfg(dict(GATE), {'kind': 'film'})


# ---------------------------------------------------------------- 9: protected peak ceiling
class TestPeakCeiling(unittest.TestCase):
    def test_no_hidden_slack_on_the_true_peak(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'p.wav'
            wav(p, 3.0, 0.5, 44100)
            y, sr = sf.read(str(p), always_2d=True)
            tp = float(mx.true_peak_db(y.astype(np.float32), sr))
            prof = dict(loudness_mode='full_program', lufs=float(mx.lufs(y.astype(np.float32), sr)),
                        true_peak_db=tp - 0.05)
            out = []
            R.master_row(str(p), prof, dict(GATE, loudness_tolerance_lu=50.0), out)
        self.assertEqual(out[0][0], 'FAIL')


# ---------------------------------------------------------------- 10, 13: performance, identical output
class TestPerformance(unittest.TestCase):
    def test_moving_average_equals_convolve(self):
        rng = np.random.default_rng(1)
        for n, k in ((1000, 7), (1000, 8), (50, 50), (4000, 1), (20000, 4411)):
            x = rng.random(n)
            np.testing.assert_allclose(vpm.moving_average_same(x, k), np.convolve(x, np.ones(k) / k, 'same'),
                                       atol=1e-9)
        x = rng.random(10)                                   # shorter than the window: same result as np.convolve
        np.testing.assert_allclose(vpm.moving_average_same(x, 30), np.convolve(x, np.ones(30) / 30, 'same'))

    def test_duck_curve_is_fast(self):
        import time
        cfg = presets.get('film', 'dialogue')
        voice = np.zeros((441000, 2), np.float32)
        t0 = time.time()
        vpm.duck_curve(voice, len(voice), np.ones(len(voice), bool), cfg)
        self.assertLess(time.time() - t0, 5.0)               # was 15 s per 10 s of audio

    def test_fit_music_equals_the_copying_loop(self):
        def old(music, n, cfg, sr):
            m = music
            if len(m) < n:
                xf = max(1, int(min(cfg['loop_crossfade_max_s'], len(m) / sr / 4.0) * sr))
                out = m.copy()
                while len(out) < n:
                    w = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
                    out[-xf:] = out[-xf:] * (1 - w[:, None]) + m[:xf] * w[:, None]
                    out = np.concatenate([out, m[xf:]])
                m = out
            return m[:n]
        rng = np.random.default_rng(2)
        music = rng.standard_normal((5000, 2)).astype(np.float32)
        cfg = {'loop_crossfade_max_s': 0.1}
        for n in (3000, 5000, 5001, 23456):
            np.testing.assert_array_equal(vpm.fit_music(music, n, cfg, 8000), old(music, n, cfg, 8000))

    def test_nearest_equals_min(self):
        rng = np.random.default_rng(3)
        vals = sorted(rng.random(200) * 100)
        for t in rng.random(300) * 110 - 5:
            self.assertEqual(R._nearest(vals, t), min(vals, key=lambda c: abs(c - t)))

    def test_voicing_by_fft_equals_correlate(self):
        rng = np.random.default_rng(4)
        frames = rng.standard_normal((6, 1102)).astype(np.float32)
        lo, hi = max(1, int(44100 / 400)), min(int(44100 / 60), 1102 - 2)
        ref = []
        for fr in frames:
            fr = fr - fr.mean()
            ac = np.correlate(fr, fr, mode='full')[len(fr) - 1:]
            ref.append(float(np.max(ac[lo:hi]) / (float(np.dot(fr, fr)) + 1e-12)))
        np.testing.assert_allclose(speech._voicing(frames, 44100), ref, atol=1e-4)

    def test_chunked_speech_activity_equals_whole(self):
        sr = 16000
        t = np.arange(int(3 * sr)) / sr
        y = (0.3 * np.sin(2 * np.pi * 170 * t) * (t > 0.5) * (t < 2.0)).astype(np.float32)
        cfg = presets.get('film', 'analysis')
        a = speech.activity(y, sr, cfg)
        with mock.patch.object(speech, 'CHUNK_FRAMES', 37):
            b = speech.activity(y, sr, cfg)
        np.testing.assert_array_equal(a['mask'], b['mask'])
        self.assertEqual(a['per_second'], b['per_second'])
        self.assertEqual(a['segments'], b['segments'])
        self.assertTrue(a['segments'])


# ---------------------------------------------------------------- 11, 12: ffmpeg hygiene, streaming
class TestFfmpeg(unittest.TestCase):
    def test_run_times_out(self):
        with self.assertRaises(RuntimeError) as cm:
            video_probe._run(['sleep', '5'], timeout=0.2)
        self.assertIn('timed out', str(cm.exception))

    def test_frames_are_streamed_one_at_a_time(self):
        gen = video_probe._read_frames(['head', '-c', '100', '/dev/zero'], 10)
        self.assertEqual(sum(1 for _ in gen), 10)

    def test_a_failing_pipe_raises(self):
        with self.assertRaises(RuntimeError):
            list(video_probe._read_frames(['sh', '-c', 'echo boom >&2; exit 3'], 10))

    def test_a_stalled_pipe_is_killed(self):
        with self.assertRaises(RuntimeError) as cm:
            list(video_probe._read_frames(['sleep', '5'], 10, timeout=0.2))
        self.assertIn('timed out', str(cm.exception))

    def test_extract_dialogue_raises_instead_of_returning_none(self):
        import video_score
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / 'not_a_video.mp4'
            bad.write_text('nope')
            with self.assertRaises(RuntimeError):
                video_score.extract_dialogue(str(bad), str(Path(d) / 'out.wav'))

    def test_streamed_metrics_match_whole_buffer(self):
        import shutil
        if shutil.which('ffmpeg') is None:
            self.skipTest('ffmpeg is not installed')
        with tempfile.TemporaryDirectory() as d:
            v = str(Path(d) / 'f.mp4')
            subprocess.run(['ffmpeg', '-y', '-hide_banner', '-nostdin', '-f', 'lavfi', '-i',
                            'testsrc2=size=160x90:rate=12:duration=2', '-pix_fmt', 'yuv420p', v],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cfg = presets.get('film', 'analysis')['probe']
            got = video_probe.frame_metrics(v, cfg)
            w, h = int(cfg['analysis_width']), int(cfg['analysis_height'])
            raw, _ = video_probe._run(['ffmpeg', '-hide_banner', '-nostats', '-nostdin', '-v', 'error', '-i', v,
                                       '-an', '-vf', f"fps={cfg['analysis_fps']},scale={w}:{h},format=rgb24",
                                       '-f', 'rawvideo', '-'], binary=True)
            n = len(raw) // (w * h * 3)
            self.assertEqual(got['frames'], n)
            lum0 = shot_scale.luma_of(np.frombuffer(raw, np.uint8, count=w * h * 3).reshape(h, w, 3)
                                      .astype(np.float32))
            self.assertAlmostEqual(got['luma'][0], float(lum0.mean()), places=6)
            rep = video_probe.probe(v, dict(presets.get('film', 'analysis'),
                                            direction_map=presets.get('film', 'mapping')))
            self.assertLessEqual(rep['luma_min'], rep['luma_mean'])
            self.assertGreaterEqual(rep['luma_max'], rep['luma_mean'])
            self.assertIn('motion_peaks', rep)


# ---------------------------------------------------------------- 15: sign validation
class TestDuckSign(unittest.TestCase):
    def test_opposite_signs_are_an_error(self):
        cfg = dict(presets.get('film', 'dialogue'), duck_db=-9.0, duck_depth_db=6.0)
        with self.assertRaises(ValueError):
            vpm.spectral_duck(np.zeros((44100, 2), np.float32), np.zeros((44100, 2), np.float32), 44100,
                              np.ones(44100, bool), cfg)


if __name__ == '__main__':
    unittest.main()
