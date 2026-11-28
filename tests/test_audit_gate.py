"""One test per defect found by the gate-engine audit. Each fails on the code as it was and passes on the fix."""
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'tests'))

import gate_audio
import gate_checks as gc
import gate_clock
import gate_profiles
import project_gate
import quality_gate as qg
import stem_gate
from gate_audio import Signal

SR = 44100


def old_clipping_flats(audio, full=0.999):
    a = np.abs(audio)
    flats = 0
    for c in range(a.shape[1]):
        run = 0
        for v in a[:, c] >= full:
            run = run + 1 if v else 0
            if run == 3:
                flats += 1
    return int(np.sum(a >= full)), flats


class RefreshKeepsStems(unittest.TestCase):
    def _run(self, refresh, stems):
        seen = {}
        names = ['score_checks', 'render_checks', 'audio_checks', 'master_extra_rows', 'immersive_rows',
                 'immersive2_rows', 'fold_rows', 'ambient_fusion_rows', 'focus_rows', 'intent_rows',
                 'spatial_separation_rows', 'equal_loudness_rows', 'vocal_rows', 'chroma_concordance_rows',
                 'kick_grid_rows', 'soul_rows', 'metadata_rows', 'direction_rows']
        import spatial_gate, ambience_reference, sfx_eval
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'scores'))
            sp = os.path.join(d, 'scores', 's.json')
            patches = [mock.patch.object(qg, n, lambda *a, **k: None) for n in names]
            patches += [mock.patch.object(qg, 'balance_rows', lambda score, st, out=None: seen.setdefault('st', st)),
                        mock.patch.object(qg.rn, 'build_stems', lambda *a, **k: ({'a': np.zeros((10, 2))}, None)),
                        mock.patch.object(qg, 'masking_rows', lambda *a, **k: []),
                        mock.patch.object(qg.nc, 'modulation_flutter_check', lambda *a, **k: []),
                        mock.patch.object(spatial_gate, 'output_rows', lambda *a, **k: None),
                        mock.patch.object(ambience_reference, 'gate_rows', lambda *a, **k: []),
                        mock.patch.object(sfx_eval, 'gate_rows', lambda *a, **k: [])]
            for p in patches:
                p.start()
            try:
                out, _ = qg.run_gate(sp, os.path.join(d, 'x.wav'), refresh=refresh, stems=stems, score={'tracks': []})
            finally:
                mock.patch.stopall()
        return out, seen

    def test_refresh_keeps_the_rebuilt_stems(self):
        out, seen = self._run(True, None)
        self.assertIsNotNone(seen.get('st'))

    def test_no_stems_is_an_info_row_not_silence(self):
        out, seen = self._run(False, None)
        self.assertTrue([r for r in out if r[1] == 'stem_rows' and r[0] == 'INFO'], out)


class ProfileAliasKey(unittest.TestCase):
    def test_alias_key_in_profile_is_canonical(self):
        allp = {'p': {'rows': {'kick_grid': {'mode': 'skip', 'reason': 'r'}}}}
        flags, rows, focus, expr, scene = gate_profiles._merge_profile('p', allp)
        prof = gate_profiles.Profile(['p'], 'declared', '', flags, rows, [], focus, expr, scene)
        self.assertFalse(prof.on('kick.grid'))
        self.assertTrue([r for r in prof.notes() if r[1] == 'gate_skip'])


class PercussiveWholeWords(unittest.TestCase):
    def test_bottom_pad_is_not_percussion(self):
        self.assertFalse(stem_gate._is_percussive({'name': 'Bottom Pad', 'instrument': 'pad', 'role': 'pad'}))
        self.assertFalse(stem_gate._is_percussive({'name': 'chat', 'instrument': 'Whatever', 'role': 'pad'}))
        self.assertTrue(stem_gate._is_percussive({'name': 'Tom 1', 'instrument': 'x', 'role': 'fx'}))
        self.assertTrue(stem_gate._is_percussive({'name': 'hi-hat', 'instrument': 'x', 'role': 'fx'}))
        self.assertTrue(stem_gate._is_percussive({'name': 'toms', 'instrument': 'x', 'role': 'fx'}))
        self.assertTrue(stem_gate._is_percussive({'name': 'a', 'instrument': 'x', 'role': 'drum'}))

    def test_excluded_rows_say_so(self):
        rng = np.random.default_rng(0)
        audio = (rng.standard_normal((SR * 3, 2)) * 0.05).astype(np.float32)
        track = {'name': 'k', 'role': 'drum', 'instrument': 'kick',
                 'notes': [{'t': 0, 'd': 1, 'p': 36}, {'t': 1, 'd': 1, 'p': 36}]}
        score = {'bpm': 120, 'tracks': [track], '_sr': SR}
        gp = gate_profiles.resolve(score)
        secs = gc.section_bounds(score, 3.0)
        rows, _ = stem_gate._stem_rows('k', audio, track, score, secs, 3.0, gp)
        ids = {r[1] for r in rows if r[0] == 'INFO'}
        self.assertIn('stem.cut', ids)
        self.assertIn('stem.edge', ids)


class SharedClock(unittest.TestCase):
    BAD = {'bpm': 100, 'tempo_points': 'garbage'}

    def test_broken_tempo_map_is_reported(self):
        probs = []
        fn = gate_clock.seconds_fn(self.BAD, probs)
        self.assertEqual(len(probs), 1)
        self.assertAlmostEqual(fn(2.0), 1.2)
        with self.assertRaises(ValueError):
            gate_clock.seconds_fn(self.BAD)

    def test_one_default(self):
        self.assertEqual(gate_clock.flat_bpm({}), gate_clock.DEFAULT_BPM)
        self.assertAlmostEqual(stem_gate._secs(stem_gate._clock({}, []), 1.0), 60.0 / gate_clock.DEFAULT_BPM)

    def test_stem_gate_warns(self):
        score = dict(self.BAD, tracks=[{'name': 'a', 'role': 'pad', 'instrument': 'x', 'notes': []}])
        rows, meta = stem_gate.run_stem_gate(score, {'a': np.zeros((SR * 2, 2), np.float32)}, sr=SR, workers=1)
        self.assertTrue([r for r in rows if r[1] == 'stem.tempo' and r[0] == 'WARN'], rows)


class ClippingVectorised(unittest.TestCase):
    def test_equals_the_loop(self):
        rng = np.random.default_rng(3)
        cases = [rng.choice([0.0, 1.0, -1.0, 0.5], size=(500, 3), p=[.4, .3, .2, .1]),
                 np.ones((10, 2)), np.ones((2, 2)), np.zeros((0, 2)), np.ones((3, 1)),
                 np.array([[1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1]], dtype=float).T,
                 np.array([[1, 1, 0, 1, 1]], dtype=float).T]
        for x in cases:
            want = old_clipping_flats(x)
            res = gc.check_clipping(Signal(x, SR)) if len(x) else None
            if res is None:
                continue
            self.assertEqual((res['value'], res['flat_runs']), want)


class FlatnessWindows(unittest.TestCase):
    def test_one_window_per_run(self):
        rng = np.random.default_rng(1)
        x = (rng.standard_normal(SR * 2) * 0.2)[:, None].repeat(2, 1)
        res = gc.check_flatness(Signal(x, SR))
        self.assertGreater(res['windows'], 0)
        self.assertLessEqual(res['windows'], 3, res['detail'])
        self.assertEqual(len(res['times']), len(set(res['times'])))


class RivalBisection(unittest.TestCase):
    def test_matches_brute_force(self):
        rng = np.random.default_rng(5)
        for _ in range(20):
            ks = np.sort(rng.choice(20000, size=40, replace=False))
            events = [(int(k), float(rng.uniform(0.01, 1.0))) for k in ks]
            for iso in (10.0, 3.3):
                want = [any(j != i and abs(k2 - k) <= iso * SR / 1000.0 and a2 >= 0.5 * a
                            for j, (k2, a2) in enumerate(events)) for i, (k, a) in enumerate(events)]
                self.assertEqual(gc._rivals(events, SR, iso, 0.5), want)


class MaskingShortStems(unittest.TestCase):
    def test_short_stems_are_not_a_pass(self):
        score = {'piece_type': 'melodic', 'tracks': [{'name': 'm', 'role': 'melody', 'instrument': 'x'},
                                                    {'name': 'p', 'role': 'pad', 'instrument': 'y'}]}
        stems = {'m': np.random.randn(SR, 2) * 0.1, 'p': np.random.randn(SR, 2) * 0.1}
        rows = qg.masking_rows(stems, score)
        self.assertEqual([r[0] for r in rows if r[1] == 'erb_binaural_masking'], ['INFO'], rows)


class MultichannelNoLayout(unittest.TestCase):
    def test_fail_row(self):
        import soundfile as sf
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'm.wav')
            sf.write(p, np.random.randn(SR, 5) * 0.1, SR, subtype='FLOAT')
            out = []
            qg.audio_checks(p, {'tracks': []}, out)
        self.assertTrue([r for r in out if r[0] == 'FAIL' and r[1] == 'audio' and '5 channels' in r[2]], out)


class StemCacheKey(unittest.TestCase):
    def test_tempo_edit_changes_the_key(self):
        gp = gate_profiles.resolve({})
        secs = [{'name': 's', 'start_s': 0.0, 'end_s': 4.0, 'dyn': 1.0}]
        a = {'bpm': 100, 'tempo_points': [[0, 100], [8, 100]]}
        b = {'bpm': 100, 'tempo_points': [[0, 100], [8, 140]]}
        ka = stem_gate._gate_key('x', 'h', None, a, secs, 4.0, gp)
        kb = stem_gate._gate_key('x', 'h', None, b, secs, 4.0, gp)
        self.assertNotEqual(ka, kb)

    def test_code_hash_covers_humanize(self):
        stem_gate._GATE_CODE = None
        with mock.patch.object(stem_gate.stem_cache, 'code_hash', return_value='h') as m:
            stem_gate._gate_code()
        stem_gate._GATE_CODE = None
        self.assertIn('humanize.py', m.call_args[0][1])
        self.assertIn('humanize_engine', m.call_args[0][2])


class OnePlacement(unittest.TestCase):
    def test_requested_vs_rendered(self):
        imm = {'enabled': True, 'height_by_role': {'bass': 30.0, 'pad': 40.0}}
        for role, req, rend in (('bass', 30.0, 0.0), ('pad', 40.0, 40.0)):
            tr = {'name': 'n', 'role': role, 'instrument': ''}
            r, el, sp, _ = project_gate.requested_place(tr, {}, imm)
            self.assertEqual(el, req)
            self.assertEqual(qg._place_of({}, tr, imm)[1], rend)
        self.assertIs(qg._mix_immersive({}), None)


class DeadCodeGone(unittest.TestCase):
    def test_signal_has_no_unused_meters(self):
        self.assertFalse(hasattr(gate_audio.GateAudio, 'true_peak'))
        self.assertFalse(hasattr(gate_audio.GateAudio, 'lufs'))
        self.assertTrue(hasattr(gate_audio, 'loudness_lufs'))


if __name__ == '__main__':
    unittest.main()
