# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""A hard cut in the direction sheet: the renderer ramps the sustained voices over 15 ms, and the gate skips only the
sudden-drop check inside the +-150 ms window around it.

Both halves have a negative control: a cut outside a window is still reported, and a click inside a window still fails.

Run: python -m unittest tests.test_hard_cut
"""
import os
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, HERE)

import cut_windows  # noqa: E402
import dsp  # noqa: E402
import gate_audio  # noqa: E402
import gate_checks as gc  # noqa: E402
import gate_fixture as fx  # noqa: E402
import render_natural as rn  # noqa: E402
import stem_gate  # noqa: E402

SR = 44100


def tone(seconds=3.0, f=220.0, amp=0.5):
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


def stereo(x):
    return np.stack([x, x], axis=1)


class FakeMap:
    """A tempo map at 120 bpm: one beat is half a second."""
    def sec(self, beats):
        return beats * 0.5


class Windows(unittest.TestCase):
    SHEET = {'hits': [
        {'t': 10.0, 'kind': 'motion', 'sync': 'soft'},
        {'t': 38.0, 'kind': 'cut', 'sync': 'hard'},
        {'t': 52.0, 'kind': 'musical', 'sync': 'hard'},
        {'t': 'x', 'kind': 'cut', 'sync': 'hard'},
        {'kind': 'cut', 'sync': 'hard'},
        'not a hit',
    ]}

    def test_a_hard_hit_opens_a_150_ms_window_and_a_soft_one_does_not(self):
        found = cut_windows.from_sheet(self.SHEET)
        self.assertEqual(found['windows'], [[37.85, 38.15], [51.85, 52.15]])

    def test_only_a_cut_asks_the_renderer_to_stop_the_voices(self):
        self.assertEqual(cut_windows.from_sheet(self.SHEET)['cuts'], [38.0])

    def test_a_sheet_with_no_hard_hit_gives_nothing(self):
        self.assertEqual(cut_windows.from_sheet({'hits': [{'t': 1.0, 'sync': 'soft'}]}), {'windows': [], 'cuts': []})
        self.assertEqual(cut_windows.from_sheet({}), {'windows': [], 'cuts': []})
        self.assertEqual(cut_windows.from_sheet(None), {'windows': [], 'cuts': []})

    def test_a_hit_near_zero_does_not_open_a_negative_window(self):
        self.assertEqual(cut_windows.from_sheet({'hits': [{'t': 0.05, 'kind': 'cut', 'sync': 'hard'}]})['windows'], [[0.0, 0.2]])

    def test_attach_returns_a_new_score_and_keeps_what_the_score_already_has(self):
        score = {'tracks': []}
        out = cut_windows.attach(score, self.SHEET)
        self.assertIsNot(out, score)
        self.assertNotIn('intentional_cut_windows', score)
        self.assertEqual(out['hard_cuts'], [38.0])
        own = {'intentional_cut_windows': [[1.0, 1.2]], 'hard_cuts': [1.1]}
        kept = cut_windows.attach(own, self.SHEET)
        self.assertEqual(kept['intentional_cut_windows'], [[1.0, 1.2]])
        self.assertEqual(kept['hard_cuts'], [1.1])

    def test_a_bad_window_can_only_exempt_less(self):
        raw = [[1.0, 1.3], [2.0, 1.0], ['a', 3.0], [5.0], [0.0, 30.0], [-1.0, 0.5], 'x', [4.0, 4.0]]
        self.assertEqual(cut_windows.windows_of(raw), [(1.0, 1.3)])
        self.assertEqual(cut_windows.windows_of({'intentional_cut_windows': raw}), [(1.0, 1.3)])
        self.assertEqual(cut_windows.windows_of(None), [])
        self.assertTrue(cut_windows.problems({'intentional_cut_windows': raw}))
        self.assertEqual(cut_windows.problems({'intentional_cut_windows': [[1.0, 1.3]]}), [])
        self.assertEqual(cut_windows.problems({}), [])

    def test_inside(self):
        w = [(1.0, 1.3)]
        self.assertTrue(cut_windows.inside(1.15, w))
        self.assertFalse(cut_windows.inside(1.31, w))


class MicroRamp(unittest.TestCase):
    def setUp(self):
        self.x = tone(3.0)
        # a quarter period after 1.0 s the 220 Hz tone is at its crest: a plain cut there is the worst case, a full-size step
        # (at exactly 1.0 s the phase is zero and a plain cut would be invisible)
        self.cut = 1.0 + 1.0 / (4 * 220.0)

    def naive(self):
        y = self.x.copy()
        y[int(self.cut * SR):] = 0.0
        return y

    def test_a_plain_cut_has_a_step_and_the_ramp_has_none(self):
        step_naive = float(np.max(np.abs(np.diff(self.naive()))))
        out = dsp.hard_cut(self.x, SR, cuts=[self.cut])[:, 0]
        step_ramp = float(np.max(np.abs(np.diff(out))))
        self.assertGreater(step_naive, 0.2)            # the control: a plain cut jumps
        self.assertLess(step_ramp, 0.03)               # the ramp stays inside the tone's own sample-to-sample slope
        self.assertLessEqual(step_ramp, float(np.max(np.abs(np.diff(self.x)))) * 1.001)

    def test_the_click_detector_hears_the_plain_cut_and_not_the_ramp(self):
        plain = gate_audio.Signal(stereo(self.naive()), SR)
        ramped = gate_audio.Signal(dsp.hard_cut(self.x, SR, cuts=[self.cut]), SR)
        self.assertGreater(len(gc.check_clicks(plain).get('times', [])) + gc.check_clicks(plain).get('mad_count', 0)
                           + gc.check_clicks(plain).get('lpc_count', 0), 0)
        c = gc.check_clicks(ramped)
        self.assertEqual((c.get('mad_count', 0), c.get('lpc_count', 0)), (0, 0), c)

    def test_the_ramp_is_fifteen_milliseconds_ending_on_the_cut(self):
        out = dsp.hard_cut(self.x, SR, cuts=[self.cut], ramp_ms=15.0)[:, 0]
        i1, n = int(self.cut * SR), int(round(0.015 * SR))
        self.assertTrue(np.array_equal(out[:i1 - n], self.x[:i1 - n]))      # nothing before the ramp moves
        self.assertEqual(float(out[i1]), 0.0)                              # silent from the cut
        self.assertLess(abs(float(out[i1 - 1])), 0.01)                     # and arrives there at zero
        env = np.abs(out[i1 - n:i1])
        self.assertGreater(float(env[:n // 4].max()), 0.45)                # still full at the start of the ramp
        self.assertLess(float(env[-n // 8:].max()), 0.06)                  # near zero at its end

    def test_silent_to_the_end_when_nothing_follows(self):
        out = dsp.hard_cut(self.x, SR, cuts=[self.cut])
        self.assertEqual(float(np.max(np.abs(out[int(self.cut * SR):]))), 0.0)

    def test_the_voice_comes_back_at_its_next_note(self):
        out = dsp.hard_cut(self.x, SR, cuts=[self.cut], resume=[2.0])[:, 0]
        self.assertEqual(float(np.max(np.abs(out[int(self.cut * SR):int(1.98 * SR)]))), 0.0)     # silent until the fade-in
        self.assertTrue(np.array_equal(out[int(2.0 * SR):], self.x[int(2.0 * SR):]))             # the note itself is untouched
        self.assertLess(float(np.max(np.abs(np.diff(out)))), 0.03)                               # and nothing steps on the way back
        fade = out[int(1.985 * SR):int(2.0 * SR)]                                                # the last 15 ms before the note
        self.assertGreater(float(np.max(np.abs(fade))), 0.0)                                     # it fades in, it does not jump in

    def test_a_note_that_starts_on_the_cut_is_not_silenced(self):
        out = dsp.hard_cut(self.x, SR, cuts=[self.cut], resume=[self.cut])[:, 0]
        i1 = int(self.cut * SR)
        self.assertTrue(np.array_equal(out[i1:], self.x[i1:]))
        self.assertLess(abs(float(out[i1 - 1])), 0.01)

    def test_a_cut_outside_the_stem_and_no_cut_change_nothing(self):
        self.assertTrue(np.array_equal(dsp.hard_cut(self.x, SR, cuts=[0.0, 99.0])[:, 0], self.x))
        self.assertTrue(np.array_equal(dsp.hard_cut(self.x, SR, cuts=[])[:, 0], self.x))
        self.assertEqual(dsp.hard_cut(np.zeros(0, np.float32), SR, cuts=[1.0]).shape[0], 0)

    def test_two_cuts_each_get_their_own_ramp(self):
        out = dsp.hard_cut(self.x, SR, cuts=[1.0, 2.0], resume=[1.5])[:, 0]
        self.assertEqual(float(np.max(np.abs(out[int(1.0 * SR):int(1.48 * SR)]))), 0.0)
        self.assertEqual(float(np.max(np.abs(out[int(2.0 * SR):]))), 0.0)
        self.assertLess(float(np.max(np.abs(np.diff(out)))), 0.03)


class RendererSelectsSustainedVoices(unittest.TestCase):
    def setUp(self):
        self.stem = stereo(tone(3.0))
        self.notes = [dict(t=0, d=6, p=60, v=0.7), dict(t=4, d=2, p=62, v=0.7)]       # 120 bpm: beats 0-3 s and 2-3 s
        self.tm = FakeMap()

    def run_cut(self, **track):
        tr = dict(name='x', notes=self.notes, **track)
        return rn._apply_hard_cuts('x', self.stem, tr, self.tm, [1.0])

    def test_a_pad_is_cut_with_a_ramp_and_returns_at_its_next_written_note(self):
        out = self.run_cut(instrument='warm_pad', role='pad')
        self.assertEqual(float(np.max(np.abs(out[int(1.0 * SR):int(1.95 * SR)]))), 0.0)     # silent; the 15 ms fade-in ends 30 ms early
        self.assertGreater(float(np.max(np.abs(out[int(2.0 * SR):]))), 0.4)
        self.assertLess(float(np.max(np.abs(np.diff(out[:, 0])))), 0.03)

    def test_strings_and_brass_count_as_sustained_by_instrument(self):
        for inst in ('strings', 'violin', 'horn', 'trombone', 'flute', 'choir'):
            out = self.run_cut(instrument=inst, role='melody')
            self.assertEqual(float(out[int(1.2 * SR), 0]), 0.0, inst)

    def test_a_struck_or_plucked_voice_and_a_one_shot_are_not_cut(self):
        for inst, role in (('piano', 'chord'), ('harp', 'arp'), ('kit', 'drum'), ('sfx:impact', 'fx'), ('timpani', 'drum')):
            out = self.run_cut(instrument=inst, role=role)
            self.assertTrue(np.array_equal(out, self.stem), inst)

    def test_no_cut_is_no_change_and_returns_the_same_array(self):
        tr = dict(name='x', notes=self.notes, instrument='strings', role='pad')
        self.assertIs(rn._apply_hard_cuts('x', self.stem, tr, self.tm, []), self.stem)

    def test_the_cut_is_in_the_render_report(self):
        self.run_cut(instrument='strings', role='pad')
        entry = rn._report_entry('x')
        self.assertEqual(entry.get('hard_cuts'), [1.0])
        self.assertEqual(entry.get('hard_cut_ramp_ms'), 15.0)


class GateSkipsOnlyTheDropInsideTheWindow(unittest.TestCase):
    """The control signal: a tone with a silence at 1.0-1.3 s and another at 2.0-2.3 s, so there are two real drops."""

    def setUp(self):
        x = tone(3.5)
        for a in (1.0, 2.0):
            x[int(a * SR):int((a + 0.3) * SR)] = 0.0
        self.sig = gate_audio.Signal(stereo(x), SR)
        self.bounds = [1.0, 2.0]

    def test_both_drops_are_reported_without_a_window(self):
        res = gc.check_cut(self.sig, self.bounds)
        self.assertGreater(res['value'], res['threshold'])
        near = lambda t: min(abs(t - 1.0), abs(t - 2.0)) < 0.1             # noqa: E731
        self.assertTrue(any(abs(t - 1.0) < 0.1 for t in res['times']), res['times'])
        self.assertTrue(any(abs(t - 2.0) < 0.1 for t in res['times']), res['times'])
        self.assertTrue(all(near(t) for t in res['times']))

    def test_a_window_skips_its_own_drop_and_leaves_the_other_one_reported(self):
        res = gc.check_cut(self.sig, self.bounds, intentional_cut_windows=[(0.85, 1.15)])
        self.assertFalse(any(abs(t - 1.0) < 0.1 for t in res['times']), res['times'])
        self.assertTrue(any(abs(t - 2.0) < 0.1 for t in res['times']), res['times'])
        self.assertGreater(res['value'], res['threshold'])                  # the unwindowed cut still fails the row
        self.assertTrue(res['exempted'])
        self.assertIn('intentional cut window', res['detail'])

    def test_a_window_on_every_drop_clears_the_row_and_says_what_it_skipped(self):
        res = gc.check_cut(self.sig, self.bounds, intentional_cut_windows=[(0.85, 1.15), (1.85, 2.15)])
        self.assertLessEqual(res['value'], res['threshold'])
        self.assertEqual(res['times'], [])
        self.assertIn('skipped', res['detail'])

    def test_a_window_that_misses_the_drop_exempts_nothing(self):
        res = gc.check_cut(self.sig, self.bounds, intentional_cut_windows=[(0.2, 0.5)])
        self.assertGreater(res['value'], res['threshold'])
        self.assertEqual(res['exempted'], [])

    def test_a_window_wider_than_a_cut_is_ignored(self):
        res = gc.check_cut(self.sig, self.bounds, intentional_cut_windows=[(0.0, 3.4)])
        self.assertGreater(res['value'], res['threshold'])

    def test_a_ramped_cut_is_one_the_gate_skips_and_a_plain_cut_in_the_window_is_too(self):
        x = tone(3.5)
        out = dsp.hard_cut(x, SR, cuts=[1.0], resume=[1.3])
        sig = gate_audio.Signal(out, SR)
        res = gc.check_cut(sig, [1.0], intentional_cut_windows=[(0.85, 1.15)])
        self.assertLessEqual(res['value'], res['threshold'])


class StemGateIntegration(unittest.TestCase):
    def rows(self, mutate, windows=None, name='pad'):
        stems = fx.build_stems()
        stems[name] = mutate(stems[name])
        score = fx.score()
        if windows is not None:
            score['intentional_cut_windows'] = windows
        rows, meta = stem_gate.run_stem_gate(score, stems, sr=fx.SR, workers=1)
        return rows

    @staticmethod
    def fails(rows):
        return {n for lvl, n, _ in rows if lvl == 'FAIL'}

    def test_a_cut_with_no_window_fails_stem_cut(self):
        self.assertIn('stem.cut', self.fails(self.rows(lambda x: fx.add_cut(x, at=4.0, ms=500))))

    def test_the_same_cut_inside_a_declared_window_does_not(self):
        rows = self.rows(lambda x: fx.add_cut(x, at=4.0, ms=500), windows=[[3.85, 4.15]])
        self.assertNotIn('stem.cut', self.fails(rows))
        self.assertTrue(any(n == 'stem.cut' and 'intentional cut window' in d for _, n, d in rows))

    def test_a_window_elsewhere_does_not_hide_the_cut(self):
        rows = self.rows(lambda x: fx.add_cut(x, at=4.0, ms=500), windows=[[5.85, 6.15]])
        self.assertIn('stem.cut', self.fails(rows))

    def test_every_other_row_still_judges_inside_the_window(self):
        window = [[2.85, 3.15]]
        self.assertIn('stem.clicks', self.fails(self.rows(lambda x: fx.add_click(x, at=3.0, amp=0.5), windows=window)))
        self.assertIn('stem.dropout', self.fails(self.rows(lambda x: fx.add_dropout(x, at=3.0, ms=80), windows=window)))

    def test_the_window_is_part_of_the_cache_identity(self):
        score = fx.score()
        secs = [dict(name='a', start_s=0.0, end_s=2.0, dyn=0.5)]
        k0 = stem_gate._gate_key('pad', 'h', None, score, secs, 8.0, stem_gate.gate_profiles.resolve(score))
        score['intentional_cut_windows'] = [[3.85, 4.15]]
        k1 = stem_gate._gate_key('pad', 'h', None, score, secs, 8.0, stem_gate.gate_profiles.resolve(score))
        self.assertNotEqual(k0, k1)


class MixGateIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import quality_gate as qg
        cls.qg = qg
        cls.tmp = tempfile.mkdtemp(prefix='hard_cut_')

    def cut_hard(self, score=None, project=None):
        mix = fx.add_cut(fx.build_mix(fx.build_stems()), at=4.0, ms=500)
        wav = os.path.join(self.tmp, 'mix.wav')
        sf.write(wav, mix, fx.SR)
        out = []
        self.qg.master_extra_rows(score or fx.score(), wav, out, project_dir=project)
        return next((lvl, d) for lvl, n, d in out if n == 'cut.hard')

    def test_the_mix_cut_fails_and_a_window_in_the_score_clears_it(self):
        self.assertEqual(self.cut_hard()[0], 'FAIL')
        score = fx.score()
        score['intentional_cut_windows'] = [[3.85, 4.15]]
        level, detail = self.cut_hard(score)
        self.assertEqual(level, 'PASS')
        self.assertIn('intentional cut window', detail)

    def test_the_direction_sheet_is_read_when_the_score_carries_nothing(self):
        import json
        with tempfile.TemporaryDirectory() as proj:
            os.makedirs(os.path.join(proj, 'direction'))
            with open(os.path.join(proj, 'direction', 'direction_x.json'), 'w', encoding='utf-8') as fh:
                json.dump({'hits': [{'t': 4.0, 'kind': 'cut', 'sync': 'hard'}]}, fh)
            self.assertEqual(self.cut_hard(project=proj)[0], 'PASS')
            with open(os.path.join(proj, 'direction', 'direction_x.json'), 'w', encoding='utf-8') as fh:
                json.dump({'hits': [{'t': 4.0, 'kind': 'cut', 'sync': 'soft'}]}, fh)
            self.assertEqual(self.cut_hard(project=proj)[0], 'FAIL')


class PipelineAttach(unittest.TestCase):
    def test_the_pipeline_puts_the_sheets_cuts_on_the_score_and_leaves_a_sheetless_project_alone(self):
        import json
        import pipeline
        pl = pipeline.MusicPipeline(verbose=False)
        with tempfile.TemporaryDirectory() as proj:
            self.assertEqual(pl.with_cut_windows({'tracks': []}, proj), {'tracks': []})
            self.assertEqual(pl.with_cut_windows({'tracks': []}, None), {'tracks': []})
            os.makedirs(os.path.join(proj, 'direction'))
            with open(os.path.join(proj, 'direction', 'direction_x.json'), 'w', encoding='utf-8') as fh:
                json.dump({'hits': [{'t': 4.0, 'kind': 'cut', 'sync': 'hard'}]}, fh)
            out = pl.with_cut_windows({'tracks': []}, proj)
            self.assertEqual(out['intentional_cut_windows'], [[3.85, 4.15]])
            self.assertEqual(out['hard_cuts'], [4.0])


if __name__ == '__main__':
    unittest.main()
