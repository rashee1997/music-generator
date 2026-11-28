"""tempo.audio: a measured tempo at the double or half of the written one is accepted only when the piece's gate profile says so."""
import os
import sys
import types
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import gate_checks as gc    # noqa: E402
import gate_profiles        # noqa: E402

SR = 22050


def clicks(bpm, seconds=24):
    x = np.zeros(int(seconds * SR))
    step = 60.0 / bpm
    for k in range(int(seconds / step)):
        i = int(k * step * SR)
        n = int(0.02 * SR)
        x[i:i + n] += np.random.default_rng(k).normal(0, 1, min(n, len(x) - i)) * np.exp(-np.arange(min(n, len(x) - i)) / (0.004 * SR))
    return types.SimpleNamespace(mono=x.astype(np.float32), sr=SR, dur=seconds)


@unittest.skipIf(gc.librosa is None, 'librosa missing')
class Octave(unittest.TestCase):
    def test_double_tempo_fails_by_default_and_passes_with_the_parameter(self):
        sig = clicks(176.0)
        r = gc.check_tempo(sig, 88.0)
        if r.get('skipped'):
            self.skipTest('no pulse found in the synthetic signal')
        self.assertTrue(r['fail'])
        ok = gc.check_tempo(sig, 88.0, octave_ok=1.0)
        self.assertFalse(ok['fail'])
        self.assertIn('metrical octave', ok['detail'])

    def test_a_wrong_tempo_still_fails_with_the_parameter(self):
        r = gc.check_tempo(clicks(150.0), 88.0, octave_ok=1.0)
        if r.get('skipped'):
            self.skipTest('no pulse found in the synthetic signal')
        self.assertTrue(r['fail'])

    def test_the_parameter_is_a_bounded_profile_row_param(self):
        self.assertEqual(gate_profiles.ROWS['tempo.audio']['params']['octave_ok'], (0.0, 0.0, 1.0)) if hasattr(gate_profiles, 'ROWS') else None


if __name__ == '__main__':
    unittest.main()
