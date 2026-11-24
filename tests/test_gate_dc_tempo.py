"""The two rows whose measurement, not the music, was wrong.

* `check_dc` read a low programme tone as DC drift: a 1 s block mean is a boxcar decimation, and a 73 Hz note leaves
  about A/(pi f) in every block. The drift is measured on the sub-2 Hz component now, so a clean low note passes and a
  real offset still fails.
* `check_tempo` deferred to librosa's beat tracker, which returns 0.0 BPM on a perfect 152 BPM click track (1.0.1)
  and 99.4 BPM on a 152 BPM orchestral master. The row reads the onset-envelope autocorrelation peak now.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import gate_audio  # noqa: E402
import gate_checks as gc  # noqa: E402

SR = 44100


def clicks(bpm, seconds=20.0, sr=SR):
    y = np.zeros(int(sr * seconds), dtype=np.float64)
    n = int(bpm / 60.0 * seconds)
    for k in range(n):
        i = int(k * 60.0 / bpm * sr)
        y[i:i + 220] = np.hanning(220)
    return gate_audio.Signal(y, sr)


class Tempo(unittest.TestCase):
    def test_click_track_is_measured_at_its_tempo(self):
        for bpm in (152.0, 90.0, 120.0):
            res = gc.check_tempo(clicks(bpm), bpm)
            self.assertFalse(res.get('skipped'), res)
            self.assertAlmostEqual(res['value'], 0.0, delta=2.0, msg=f'{bpm}: {res["detail"]}')
            self.assertFalse(res['fail'], res['detail'])

    def test_a_wrong_tempo_still_fails(self):
        res = gc.check_tempo(clicks(152.0), 96.0)
        self.assertTrue(res['fail'], res['detail'])

    def test_no_pulse_is_skipped_not_passed(self):
        y = np.zeros(SR * 5, dtype=np.float64) + 0.01 * np.sin(2 * np.pi * 40 * np.arange(SR * 5) / SR)
        res = gc.check_tempo(gate_audio.Signal(y, SR), 120.0)
        self.assertTrue(res.get('skipped'), res)
        self.assertIn('no isochronous pulse', res['detail'])


class Dc(unittest.TestCase):
    def _tone(self, hz=73.416, amp=0.5, seconds=6.0, dc=0.0):
        t = np.arange(int(SR * seconds)) / SR
        return gate_audio.Signal(amp * np.sin(2 * np.pi * hz * t) + dc, SR)

    def test_a_low_note_is_not_dc_drift(self):
        # A/(pi f) for a 0.5 FS 73 Hz tone is about 2.2e-3 per 1 s block: the old row failed this clean tone.
        res = gc.check_dc(self._tone())
        self.assertLess(res['value'], 0.001, res['detail'])
        self.assertLess(res['drift'], 0.001, res['detail'])

    def test_a_real_offset_fails(self):
        res = gc.check_dc(self._tone(dc=0.01))
        self.assertGreater(res['value'], 0.001, res['detail'])

    def test_a_drifting_offset_fails(self):
        t = np.arange(int(SR * 6.0)) / SR
        y = 0.01 * (t / 6.0)          # a slow ramp: 0 to 0.01 FS across the file
        res = gc.check_dc(gate_audio.Signal(y, SR))
        self.assertGreater(res['drift'], 0.001, res['detail'])


if __name__ == '__main__':
    unittest.main()
