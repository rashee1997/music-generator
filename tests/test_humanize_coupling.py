# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Cross-track phase coupling: the opt-in block, the curves it produces and the cache signature.

The claim under test is the one the model makes: a first-order correction toward the reference removes
ensemble asynchrony without removing it entirely, stays bounded, and never moves a score that did not ask.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import humanize as hz


def _events(dev_ms, beats=range(1, 9)):
    return [dict(t=b * 0.5 + dev_ms / 1000.0, beat=float(b), p=60, v=90, dur=0.4) for b in beats]


def _tm():
    return hz.tempo_map_for({'bpm': 96, 'ts': [4, 4], 'tracks': []}, seed=5)


BLOCK = dict(mode='phase', gain=0.6, anchor='bass', window_beats=0.0, cap_ms=25.0)


class CouplingBlock(unittest.TestCase):
    def test_absent_is_off(self):
        self.assertEqual(hz.resolve_block({})['mode'], 'off')
        self.assertEqual(hz.resolve_block({'coupling': {}})['mode'], 'off')
        self.assertEqual(hz.resolve_block({'coupling': {'mode': 'off'}})['mode'], 'off')

    def test_unknown_key_is_an_error(self):
        with self.assertRaises(ValueError) as cm:
            hz.resolve_block({'coupling': {'mode': 'phase', 'gaim': 0.4}})
        self.assertIn('gaim', str(cm.exception))

    def test_ranges(self):
        for bad in ({'gain': 2.0}, {'gain': -0.1}, {'cap_ms': 200}, {'window_beats': 40}, {'mode': 'orbit'}):
            with self.assertRaises(ValueError, msg=bad):
                hz.resolve_block({'coupling': dict({'mode': 'phase'}, **bad)})


class PhaseCorrection(unittest.TestCase):
    def test_off_returns_no_curves(self):
        curves, stats = hz.phase_correction({'bass': _events(0), 'lead': _events(10)}, _tm(), dict(mode='off'))
        self.assertEqual(curves, {})
        self.assertIsNone(stats['asynchrony_rms_ms_before'])

    def test_variance_is_reduced_but_not_removed(self):
        curves, stats = hz.phase_correction({'bass': _events(0), 'lead': _events(12)}, _tm(), BLOCK,
                                            roles={'bass': 'bass', 'lead': 'melody'})
        self.assertAlmostEqual(stats['asynchrony_rms_ms_before'], 12.0, places=3)
        self.assertAlmostEqual(stats['asynchrony_rms_ms_after'], 4.8, places=2)     # (1 - 0.6) * 12
        self.assertGreater(stats['asynchrony_rms_ms_after'], 0.0)                    # coordination, not quantization
        self.assertAlmostEqual(stats['mean_abs_ms'], 7.2, places=2)
        self.assertTrue(all(c < 0 for _, c in curves['lead']))                       # a late part is pulled earlier

    def test_gain_one_flattens_and_cap_bounds(self):
        curves, _ = hz.phase_correction({'bass': _events(0), 'lead': _events(300)}, _tm(),
                                        dict(BLOCK, gain=1.0, cap_ms=25.0))
        self.assertAlmostEqual(max(abs(c) for _, c in curves['lead']), 0.025, places=6)

    def test_anchor_auto_prefers_drums_then_bass(self):
        curves, stats = hz.phase_correction({'drums': _events(0), 'bass': _events(8), 'lead': _events(-6)}, _tm(),
                                            dict(BLOCK, anchor='auto'),
                                            roles={'drums': 'drum', 'bass': 'bass', 'lead': 'melody'})
        self.assertEqual(stats['anchor'], 'drums')
        self.assertEqual(curves['drums'], [])
        self.assertTrue(curves['bass'] and curves['lead'])

    def test_one_shared_onset_is_not_a_trend(self):
        curves, _ = hz.phase_correction({'bass': _events(0)[:1], 'lead': _events(20)[:1]}, _tm(), BLOCK)
        self.assertEqual(curves['lead'], [])

    def test_deterministic(self):
        a = hz.phase_correction({'bass': _events(0), 'lead': _events(9)}, _tm(), BLOCK)
        b = hz.phase_correction({'bass': _events(0), 'lead': _events(9)}, _tm(), BLOCK)
        self.assertEqual(a, b)


class TrackPipeline(unittest.TestCase):
    def test_curve_shifts_onsets_exactly(self):
        tm = _tm()
        notes = [dict(t=b * 1.0, d=1.0, p=60, v=90) for b in range(1, 5)]      # not beat 0: an onset is clamped there
        base = hz.humanize_track(notes, tm, 'natural', role='melody', seed=11, part='lead')
        tm.phase_curves = {'lead': [(0.0, 0.012), (4.0, 0.012)]}
        shifted = hz.humanize_track(notes, tm, 'natural', role='melody', seed=11, part='lead')
        self.assertEqual(len(base), len(shifted))
        for a, b in zip(base, shifted):
            self.assertAlmostEqual(b['t'] - a['t'], 0.012, places=9)

    def test_no_curve_is_byte_identical(self):
        tm = _tm()
        notes = [dict(t=b * 1.0, d=1.0, p=60, v=90) for b in range(1, 5)]
        a = hz.humanize_track(notes, tm, 'natural', role='melody', seed=11, part='lead')
        tm.phase_curves = {}
        b = hz.humanize_track(notes, tm, 'natural', role='melody', seed=11, part='lead')
        self.assertEqual(a, b)


class RendererWiring(unittest.TestCase):
    def setUp(self):
        try:
            import render_natural as rn
        except Exception as exc:                      # soundfile etc. missing: the engine tests still run
            self.skipTest(f'renderer unavailable: {exc}')
        self.rn = rn

    def test_cache_key_includes_the_curve(self):
        rn = self.rn
        tr = {'name': 'lead', 'instrument': 'piano', 'role': 'melody', 'notes': [{'t': 0, 'd': 1, 'p': 60, 'v': 90}]}
        tm = _tm()
        tm.phase_curves = {}
        k1 = rn._track_cache_key(tr, 1, (4, 4), 0.5, tm, None, 44100)
        tm.phase_curves = {'lead': [(0.0, 0.012)]}
        k2 = rn._track_cache_key(tr, 1, (4, 4), 0.5, tm, None, 44100)
        k3 = rn._track_cache_key(tr, 1, (4, 4), 0.5, tm, None, 44100)
        self.assertNotEqual(k1, k2)
        self.assertEqual(k2, k3)

    def _score(self, coupling=None):
        tracks = [{'name': 'bass', 'instrument': 'piano', 'role': 'bass',
                   'notes': [dict(t=float(b), d=0.9, p=40, v=90) for b in range(4)]},
                  {'name': 'lead', 'instrument': 'piano', 'role': 'melody',
                   'notes': [dict(t=float(b) + 0.03, d=0.9, p=72, v=90) for b in range(4)]}]
        score = dict(bpm=96, ts=[4, 4], seed=5, tracks=tracks)
        if coupling:
            score['coupling'] = coupling
        return score

    def test_prepass_builds_bounded_curves_and_reports(self):
        rn = self.rn
        score = self._score({'mode': 'phase', 'gain': 0.6, 'anchor': 'bass', 'window_beats': 0, 'cap_ms': 25})
        tm = hz.tempo_map_for(score, seed=5)
        marked = [(i, t['name'], rn._mark_accompanied(t, score['tracks'])) for i, t in enumerate(score['tracks'])]
        rn._reset_stats()
        rn._coupling_prepass(score, tm, marked, 'natural', 5, (4, 4), 0.5)
        self.assertEqual(tm.phase_curves['bass'], [])
        self.assertTrue(tm.phase_curves['lead'])
        self.assertLessEqual(max(abs(c) for _, c in tm.phase_curves['lead']), 0.025)
        self.assertIn('coupling_correction_ms', rn._report_entry('lead'))
        self.assertEqual(tm.phase_stats['anchor'], 'bass')

    def test_unknown_anchor_is_an_error(self):
        score = self._score({'mode': 'phase', 'anchor': 'kazoo'})
        with self.assertRaises(ValueError):
            hz.coupling.resolve_block(score)
        with self.assertRaises(ValueError):
            hz.coupling._pick_anchor({'bass': [1], 'lead': [1]}, {'bass': 'bass', 'lead': 'melody'}, 'kazoo')

    def test_prepass_uses_the_render_swing_grid(self):
        """The pre-pass must humanize with the same swing unit and strum direction the render uses, or the curve is
        estimated from off-beat onsets the render never plays."""
        rn = self.rn
        seen = []
        real = hz.humanize_track

        def spy(notes, tm, cfg, **kw):
            seen.append(kw)
            shift = 0.02 if kw.get('part') == 'lead' else 0.0
            return [dict(t=float(n['t']) + shift, beat=float(n['t']), p=int(n['p']), v=90, dur=0.5) for n in notes]

        import tempfile
        old_dir = rn._track_cache_dir
        with tempfile.TemporaryDirectory() as d:
            rn._track_cache_dir = lambda: os.path.join(d, 'stems')
            hz.humanize_track = spy
            try:
                score = self._score({'mode': 'phase', 'anchor': 'bass', 'window_beats': 0})
                score['swing'] = 0.6
                score['tracks'][1]['notes'] = [dict(t=b + 0.25, d=0.2, p=72, v=90) for b in range(4)]
                tm = hz.tempo_map_for(score, seed=5)
                marked = [(i, t['name'], rn._mark_accompanied(t, score['tracks']))
                          for i, t in enumerate(score['tracks'])]
                rn._reset_stats()
                rn.REPORT.clear()
                rn._coupling_prepass(score, tm, marked, 'natural', 5, (4, 4), 0.6)
            finally:
                hz.humanize_track = real
                rn._track_cache_dir = old_dir
        lead = [k for k in seen if k.get('part') == 'lead'][0]
        self.assertEqual(lead['swing_unit'], 0.25)
        self.assertEqual(lead['strum_dir'], 'alt')

    def test_prepass_cache_replays_the_same_curves(self):
        """A second pre-pass with the same score/seed/presets is served from its cache, with the same curves and report."""
        rn = self.rn
        import tempfile
        old_dir = rn._track_cache_dir
        score = self._score({'mode': 'phase', 'anchor': 'bass', 'window_beats': 0})
        marked = [(i, t['name'], rn._mark_accompanied(t, score['tracks'])) for i, t in enumerate(score['tracks'])]
        with tempfile.TemporaryDirectory() as d:
            rn._track_cache_dir = lambda: os.path.join(d, 'stems')
            try:
                tm1 = hz.tempo_map_for(score, seed=5)
                rn._reset_stats()
                rn.REPORT.clear()
                rn._coupling_prepass(score, tm1, marked, 'natural', 5, (4, 4), 0.5)
                first = (dict(tm1.phase_curves), dict(tm1.phase_stats), dict(rn._report_entry('lead')))
                tm2 = hz.tempo_map_for(score, seed=5)
                rn._reset_stats()
                rn.REPORT.clear()
                rn._coupling_prepass(score, tm2, marked, 'natural', 5, (4, 4), 0.5)
                second = (dict(tm2.phase_curves), dict(tm2.phase_stats), dict(rn._report_entry('lead')))
            finally:
                rn._track_cache_dir = old_dir
        self.assertEqual(first, second)
        self.assertTrue(first[0]['lead'])

    def test_prepass_is_off_when_not_asked(self):
        rn = self.rn
        score = self._score()
        tm = hz.tempo_map_for(score, seed=5)
        marked = [(i, t['name'], t) for i, t in enumerate(score['tracks'])]
        rn._reset_stats()
        rn.REPORT.clear()
        rn._coupling_prepass(score, tm, marked, 'natural', 5, (4, 4), 0.5)
        self.assertEqual(tm.phase_curves, {})
        self.assertNotIn('coupling_correction_ms', rn._report_entry('lead'))


if __name__ == '__main__':
    unittest.main()
