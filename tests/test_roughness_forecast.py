"""scripts/roughness_forecast.py: the score-side forecast, the master-side diagnosis and the measured partials."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import roughness_forecast as rf  # noqa: E402

SR = 44100


def score(notes_a, notes_b, bpm=60.0):
    return dict(bpm=bpm, ts=[4, 4], dynamics=[[0, 0.8], [64, 0.8]],
                tracks=[dict(name='a', instrument='a', role='pad', notes=notes_a),
                        dict(name='b', instrument='b', role='lead', notes=notes_b)])


def held(p, beats=24):
    return [dict(t=0.0, d=float(beats), p=p, v=100)]


class PairModel(unittest.TestCase):
    def test_symmetric_and_octave_is_quiet(self):
        self.assertAlmostEqual(rf.pair_weight(440.0, 466.0), rf.pair_weight(466.0, 440.0))
        self.assertGreater(rf.pair_weight(440.0, 466.0), 0.1)
        self.assertLess(rf.pair_weight(440.0, 880.0), 0.001)

    def test_frame_value_close_pair_beats_an_octave(self):
        close, _ = rf.frame_value([440.0, 466.0], [1.0, 1.0])
        octave, _ = rf.frame_value([440.0, 880.0], [1.0, 1.0])
        self.assertGreater(close, 10 * octave)

    def test_frame_value_needs_two_partials(self):
        self.assertTrue(np.isnan(rf.frame_value([440.0], [1.0])[0]))


class Forecast(unittest.TestCase):
    DATA = dict(default_partials=[1.0, 0.5, 0.3], default_release_s=0.2, by_gm={}, release_s={})

    PURE = dict(DATA, default_partials=[1.0])                                 # one partial per note: the clash is exact

    def test_a_clashing_pair_is_hotter_than_a_consonant_one(self):
        clash = rf.forecast(score(held(69), held(70)), data=self.PURE)       # A4 against Bb4, sustained
        calm = rf.forecast(score(held(69), held(81)), data=self.PURE)        # A4 against A5
        self.assertGreater(np.nanmedian(clash['values']), 5 * np.nanmedian(calm['values']))

    def test_the_hot_frames_name_the_pair_and_its_tracks(self):
        # 20 beats at 60 BPM: b plays A5 (consonant with A4) for 16 s, then Bb4 (a clash) for the last 4 s
        notes_b = [dict(t=0.0, d=16.0, p=81, v=100), dict(t=16.0, d=4.0, p=70, v=100)]
        fc = rf.forecast(score(held(69, 20), notes_b), data=self.PURE)
        flagged, _med = rf.flag_frames(fc)
        self.assertTrue(flagged)
        self.assertTrue(all(fl['t'] > 15.0 for fl in flagged))               # only the clashing end
        self.assertEqual({tr for fl in flagged for tr in fl['tracks_a'] + fl['tracks_b']}, {'a', 'b'})

    def test_a_preset_partials_list_wins(self):
        prof, src = rf.profile_for(dict(partials=[1.0, 0.0, 0.9], gm='piano'), self.DATA)
        self.assertEqual((prof, src), ([1.0, 0.0, 0.9], 'preset'))
        prof, src = rf.profile_for(dict(gm='nothing'), self.DATA)
        self.assertEqual(src, 'default')

    def test_the_presets_low_pass_removes_the_overtone_that_clashes(self):
        # A2 (110 Hz) has its 4th harmonic at 440 Hz; against Bb4 that clashes unless a low-pass removes it
        only4th = dict(partials=[0.0, 0.0, 0.0, 1.0])                         # A2's partial at 440 Hz and nothing else
        only1st = dict(partials=[1.0])                                        # the other part: its Bb4 fundamental
        open_ = rf.forecast(score(held(45), held(70)), lambda k, n: dict(only4th) if n == 'a' else dict(only1st), data=self.DATA)
        filt = rf.forecast(score(held(45), held(70)),
                           lambda k, n: dict(only4th, eq=[dict(type='lp', f=150)]) if n == 'a' else dict(only1st), data=self.DATA)
        self.assertGreater(np.nanmedian(open_['values']), 2 * np.nanmedian(filt['values']))

    def test_drums_are_ignored(self):
        sc = score(held(69), held(70))
        sc['tracks'][1]['role'] = 'drum'
        fc = rf.forecast(sc, data=self.PURE)                                  # one pitched part with one partial: nothing to beat
        self.assertTrue(all(np.isnan(v) or v == 0.0 for v in fc['values']))

    def test_the_preflight_row_is_a_warn_not_a_fail(self):
        rows = rf.forecast_rows(score(held(69, 20), [dict(t=0.0, d=10.0, p=81, v=100), dict(t=10.0, d=10.0, p=70, v=100)]),
                                lambda k, n: None)
        self.assertEqual(rows[0][1], 'preflight.roughness_partials')
        self.assertIn(rows[0][0], ('WARN', 'PASS'))


class Audio(unittest.TestCase):
    def _tone(self, freqs, seconds=4.0, amps=None):
        t = np.arange(int(SR * seconds)) / SR
        amps = amps or [1.0] * len(freqs)
        return sum(a * np.sin(2 * np.pi * f * t) for f, a in zip(freqs, amps)).astype(np.float32) * 0.2

    def test_diagnose_names_the_pair_and_the_stems(self):
        with tempfile.TemporaryDirectory() as d:
            lo, hi = self._tone([440.0, 880.0]), self._tone([466.0, 932.0])
            sf.write(os.path.join(d, 'lowpart.wav'), lo, SR)
            sf.write(os.path.join(d, 'highpart.wav'), hi, SR)
            json.dump({'lowpart': dict(start_s=0.0), 'highpart': dict(start_s=0.0)}, open(os.path.join(d, 'stems.json'), 'w'))
            sf.write(os.path.join(d, 'master.wav'), np.column_stack([lo + hi, lo + hi]), SR)
            res = rf.diagnose(os.path.join(d, 'master.wav'), d, None)
        self.assertTrue(res['flagged'])
        pr = res['flagged'][0]['pairs'][0]
        self.assertAlmostEqual(abs(pr['delta_hz']), 26.0, delta=3.0)
        self.assertEqual({tuple(pr['stems_a']), tuple(pr['stems_b'])}, {('lowpart',), ('highpart',)})

    def test_measure_partials_recovers_a_harmonic_series(self):
        f0, amps = 220.0, [1.0, 0.5, 0.25, 0.0, 0.125]
        y = self._tone([f0 * (k + 1) for k in range(5)], seconds=3.0, amps=amps)
        notes = [dict(t=0.0, d=2.5, p=57)]                              # A3 = 220 Hz
        prof = rf.measure_partials(y, SR, notes, lambda b: float(b), count=5)
        for got, want in zip(prof, amps):
            self.assertAlmostEqual(got, want, delta=0.05)


if __name__ == '__main__':
    unittest.main()
