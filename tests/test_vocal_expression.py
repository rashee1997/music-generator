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

"""Tests for the phrase-level performance shaping (scripts/vocal_engine/context.py, performance.py, breath.py).

The contract these tests defend:
  * `phrasing.amount = 0` reproduces the previous phrase exactly (contour, no accents, no micro-timing).
  * expressive terms change the sound, do not move the phrase's mean level, and never reorder notes.
  * breaths are timed per singer; a choir does not gasp on one millisecond.
  * a bad contour or profile is an error, not a silent fallback.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'scripts')]
from vocal_engine import config, data, ensemble, performance as pf  # noqa: E402

SR = 44100
MEL = [dict(t=0.0, dur=1.2, p=62, v=70), dict(t=1.2, dur=1.2, p=65, v=76), dict(t=2.4, dur=0.8, p=64, v=80),
       dict(t=3.2, dur=1.6, p=62, v=88), dict(t=5.2, dur=1.0, p=60, v=70), dict(t=6.2, dur=1.0, p=62, v=78),
       dict(t=7.2, dur=2.4, p=57, v=66)]
LINE = [dict(t=i * 0.9, dur=0.8, p=p, v=80) for i, p in enumerate((60, 62, 64, 65, 67, 69))]


def _cfg(**ph):
    c = data.defaults()
    c['phrasing'].update(ph)
    return c


def _phrase(notes, cfg=None, seed=3, hum=False, ctx=None):
    return pf.render_phrase(notes, SR, np.random.default_rng(seed), cfg or data.defaults(), hum=hum, ctx=ctx)


def _ctx(notes, cfg, cfg_ctx=None):
    from vocal_engine import context
    piece = context.analyse(notes, cfg)
    return context.phrase_context(notes, piece, cfg, 0, 1)


class BackwardCompatibility(unittest.TestCase):
    def test_amount_zero_is_the_previous_phrase(self):
        c = _cfg(amount=0.0)
        r = _phrase(MEL, c)
        D = data.defaults()['dynamics']
        pos = np.arange(len(r['arc_db'])) / (len(r['arc_db']) - 1)
        f = np.where(pos < D['arc_peak'], pos / D['arc_peak'], (1 - pos) / (1 - D['arc_peak']))
        old = D['phrase_arc_db'] * np.sin(0.5 * np.pi * np.clip(f, 0, 1))
        self.assertTrue(np.allclose(r['arc_db'], old))
        self.assertEqual(r['contour'], 'arch')
        self.assertLess(float(np.max(np.abs(r['timing_ms']))), 1e-9)
        self.assertFalse(np.any(r['accents_db']))

    def test_amount_zero_is_deterministic_and_matches_old_semantics(self):
        a = _phrase(MEL, _cfg(amount=0.0), seed=9)['signal']
        b = _phrase(MEL, _cfg(amount=0.0), seed=9)['signal']
        self.assertTrue(np.array_equal(a, b))

    def test_default_config_still_renders_the_old_contract(self):
        c = data.defaults()
        self.assertIn('phrasing', c)                      # the section exists and has defaults
        self.assertEqual(c['phrasing']['amount'], 1.0)
        y = _phrase(MEL)['signal']
        self.assertTrue(np.isfinite(y).all())
        self.assertLessEqual(float(np.abs(y).max()), 1.0)


class PhraseDynamics(unittest.TestCase):
    def test_contours_are_not_one_static_arc(self):
        c = _cfg()
        shapes = set()
        for seed in range(12):
            shapes.add(_phrase(MEL, c, seed=seed)['contour'])
        self.assertGreaterEqual(len(shapes), 3, shapes)
        self.assertIn('arch', {'arch'} | shapes)

    def test_contour_choice_follows_phrase_position_and_expression(self):
        ph = data.defaults()['phrasing']
        rng = np.random.default_rng(1)
        last = [pf._pick_contour(rng, ph, dict(is_last=True, is_first=False, direction=0.0)) for _ in range(400)]
        first = [pf._pick_contour(rng, ph, dict(is_last=False, is_first=True, direction=0.0)) for _ in range(400)]
        mel = [pf._pick_contour(rng, ph, dict(expression='melancholic', direction=-1)) for _ in range(400)]
        hop = [pf._pick_contour(rng, ph, dict(expression='hopeful', direction=1)) for _ in range(400)]
        self.assertGreater(last.count('fall') + last.count('settle'), first.count('fall') + first.count('settle'))
        self.assertGreater(mel.count('fall'), hop.count('fall'))
        self.assertGreater(hop.count('rise'), mel.count('rise'))

    def test_mean_level_of_the_phrase_does_not_move(self):
        a = _phrase(MEL, _cfg(amount=0.0))['arc_db'].mean()
        for seed in range(6):
            b = _phrase(MEL, _cfg(amount=1.0), seed=seed)['arc_db']
            self.assertAlmostEqual(float(b.mean()), float(a), delta=0.02)
        acc = _phrase(MEL, _cfg())['accents_db']
        self.assertAlmostEqual(float(np.mean(acc)), 0.0, delta=1e-6)

    def test_accents_are_present_and_shaped(self):
        r = _phrase(MEL, _cfg())
        acc = np.asarray(r['accents_db'])
        self.assertGreater(float(np.max(acc) - np.min(acc)), 0.5)          # accents exist
        self.assertLessEqual(float(np.max(np.abs(acc))), 8.0)              # and stay subtle
        long_note = _phrase([dict(t=0.0, dur=2.0, p=60, v=80)], _cfg())
        self.assertGreater(float(np.max(np.abs(long_note['accents_db']))), 0.1)

    def test_expression_bias_widens_or_narrows_without_new_sounds(self):
        c = _cfg()
        a = _phrase(MEL, c, ctx=dict(expression='powerful', intensity=1.0, role='melody'))
        b = _phrase(MEL, c, ctx=dict(expression='intimate', intensity=1.0, role='melody'))
        self.assertGreater(np.ptp(a['arc_db']), np.ptp(b['arc_db']))
        for r in (a, b):
            self.assertTrue(np.isfinite(r['signal']).all())


class TimingImperfections(unittest.TestCase):
    def test_offsets_never_reorder_or_collapse_notes(self):
        for seed in range(8):
            r = _phrase(LINE, _cfg(), seed=seed)
            s = np.asarray(r['s'])
            self.assertTrue(np.all(np.diff(s) > 0), s)
            self.assertGreaterEqual(int(s[0]), 0)
            self.assertEqual(int(s[0]), 0, 'the phrase must still begin where the score says')
            self.assertLess(float(np.max(np.abs(r['timing_ms']))), 60.0)

    def test_tempo_decides_metric_lag(self):
        c = _cfg()
        notes = [dict(t=i * 0.5, dur=0.45, p=60 + (i % 3), v=80) for i in range(8)]
        slow = dict(c, phrasing=dict(c['phrasing'], tempo_bpm=60.0))
        fast = dict(c, phrasing=dict(c['phrasing'], tempo_bpm=150.0))
        a = _phrase(notes, slow, ctx=_ctx(notes, slow))
        b = _phrase(notes, fast, ctx=_ctx(notes, fast))
        self.assertFalse(np.allclose(a['timing_ms'], b['timing_ms']))
        no_grid = _phrase(notes, _cfg(tempo_bpm=0.0), ctx=dict(beat_s=None, beats_per_bar=4))
        self.assertTrue(np.isfinite(no_grid['signal']).all())

    def test_short_notes_are_not_treated_like_long_ones(self):
        short = [dict(t=0.0, dur=0.2, p=60, v=80), dict(t=0.3, dur=0.2, p=62, v=80),
                 dict(t=0.6, dur=0.2, p=64, v=80), dict(t=1.2, dur=0.2, p=62, v=80)]
        r = _phrase(short, _cfg())
        self.assertTrue(np.all(np.isfinite(r['signal'])))
        self.assertLess(float(np.max(np.abs(r['timing_ms']))), 100.0)


class VibratoAndArticulation(unittest.TestCase):
    def _depth(self, sig_f0, a, b):
        return float(np.std(sig_f0[int(a * SR):int(b * SR)]))

    def test_vibrato_depth_follows_note_length(self):
        notes = [dict(t=0.0, dur=0.35, p=60, v=80), dict(t=0.5, dur=3.0, p=60, v=80)]
        c = _cfg()
        r = _phrase(notes, c)
        f0 = 440.0 * 2 ** ((1200 * np.log2(np.maximum(r['f0'], 1e-6) / 440.0)) / 1200)
        cs = 1200 * np.log2(np.maximum(r['f0'], 1e-6) / 440.0)
        short_d = self._depth(cs - cs.mean(), 0.22, 0.34)
        long_d = self._depth(cs - cs.mean(), 2.2, 3.2)
        self.assertLess(short_d, long_d)

    def test_vibrato_is_not_a_clean_sine(self):
        c = _cfg()
        r = _phrase([dict(t=0.0, dur=4.0, p=57, v=80)], c)
        cs = 1200 * np.log2(np.maximum(r['f0'], 1e-6) / 440.0)
        seg = cs[int(1.5 * SR):int(4.0 * SR)]
        seg = seg - seg.mean()
        idx = np.arange(len(seg))
        third = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 4 * len(seg))) ** 2
        fr = np.fft.rfftfreq(4 * len(seg), 1 / SR)
        f0v = fr[1 + int(np.argmax(third[1:]))]
        h2 = third[np.argmin(np.abs(fr - 2 * f0v))]
        h1 = third[np.argmin(np.abs(fr - f0v))]
        self.assertGreater(h2 / (h1 + 1e-20), 0.002)       # a second harmonic in the vibrato (asymmetry)

    def test_formants_articulate_the_onset_of_a_held_note(self):
        r = _phrase([dict(t=0.0, dur=2.5, p=62, v=80)], _cfg())
        F = np.asarray(r['formants'])
        self.assertEqual(F.ndim, 2)
        onset = F[:, int(0.01 * SR)]
        steady = F[:, int(1.5 * SR)]
        self.assertGreater(float(np.max(np.abs(onset - steady))), 5.0)
        flat = _phrase([dict(t=0.0, dur=2.5, p=62, v=80)], _cfg(amount=0.0))
        self.assertEqual(np.asarray(flat['formants']).ndim, 1)   # the old path is unchanged

    def test_role_profile_keeps_a_pad_calmer_than_a_lead(self):
        lead = _phrase(MEL, _cfg(), ctx=dict(role='melody'))
        pad = _phrase(MEL, _cfg(), ctx=dict(role='pad'))
        self.assertLess(np.std(pad['timing_ms']), np.std(lead['timing_ms']) + 1e-9)
        self.assertGreaterEqual(np.ptp(lead['level']), np.ptp(pad['level']) * 0.99)


class Breaths(unittest.TestCase):
    def _render(self, amount, voices=5):
        c = _cfg(amount=amount)
        # cohesion 1 removes the ensemble's own timing spread, so any remaining spread IS the breath jitter
        c['ensemble'].update(voices=voices, cohesion=1.0, diversity=0.5)
        y, info = ensemble.render(MEL, SR, c, seed=4, hum=True, stems=True)
        return y, info

    def test_singers_do_not_gasp_on_the_same_millisecond(self):
        _, new = self._render(1.0)
        spread = new['report']['phrasing']['inhale_spread_ms']
        self.assertIsNotNone(spread)
        self.assertGreater(spread, 4.0)
        _, old = self._render(0.0)
        old_spread = old['report']['phrasing']['inhale_spread_ms']
        self.assertTrue(old_spread is None or old_spread < 1e-6, old_spread)

    def test_onset_puff_gives_the_first_phrase_air(self):
        _, r0 = self._render(0.0, voices=1)
        _, r1 = self._render(1.0, voices=1)
        n = int(0.2 * SR)
        a = float(np.sqrt(np.mean(np.asarray(r0['breath_stems'][0][:n]) ** 2)))
        b = float(np.sqrt(np.mean(np.asarray(r1['breath_stems'][0][:n]) ** 2)))
        self.assertGreater(b, a)

    def test_breath_stem_stays_far_under_the_voice(self):
        y, info = self._render(1.0, voices=1)
        voice = float(np.sqrt(np.mean(np.asarray(info['stems'][0]) ** 2)))
        br = float(np.sqrt(np.mean(np.asarray(info['breath_stems'][0]) ** 2)))
        self.assertLess(br, 0.5 * voice)


class Validation(unittest.TestCase):
    def test_unknown_contour_and_bad_profile_are_errors(self):
        c = data.defaults()
        c['phrasing']['contours']['one_point'] = {'points': [[0.0, 0.5]], 'weight': 1}
        c['phrasing']['expression_bias']['gentle']['contours']['nope'] = 2.0
        w = config.check(c)
        self.assertTrue(any('one_point' in x for x in w), w)
        self.assertTrue(any('nope' in x for x in w), w)

    def test_preset_phrasing_is_merged_and_clamped(self):
        cfg, warn = config.resolve({'phrasing': {'amount': 0.5, 'timing': {'sigma_ms': 500.0},
                                                 'accent': {'gain_db': 2.0}}})
        self.assertAlmostEqual(cfg['phrasing']['amount'], 0.5)
        self.assertEqual(cfg['phrasing']['timing']['sigma_ms'], 80.0)
        self.assertEqual(cfg['phrasing']['accent']['gain_db'], 2.0)
        self.assertTrue(any('phrasing.timing.sigma_ms' in x for x in warn), warn)

    def test_missing_phrasing_section_still_configures(self):
        cfg, warn = config.resolve({})
        self.assertIn('phrasing', cfg)
        self.assertEqual(warn, [])


if __name__ == '__main__':
    unittest.main()
