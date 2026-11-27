"""The shipped cinematic presets: the impact layers, the air effect, the vocal sections."""
import json
import os
import sys
import unittest

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import fx_engine     # noqa: E402
import sfx           # noqa: E402

SR = 44100


class Impact(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(HERE, '..', 'references', 'data', 'presets', 'sfx', 'impact_cinematic.json'), encoding='utf-8') as fh:
            self.cfg = json.load(fh)

    def test_validates(self):
        self.assertEqual(sfx.preset_problems(self.cfg), [])

    def test_has_sub_click_and_a_fast_front(self):
        x = sfx.synth(self.cfg['spec'], SR, seed=1)
        sp = np.abs(np.fft.rfft(x)) ** 2
        f = np.fft.rfftfreq(len(x), 1 / SR)
        sub = sp[(f >= 20) & (f < 60)].sum() / sp.sum()
        self.assertGreater(sub, 0.2)                                                  # real weight below 60 Hz
        hf = signal.sosfilt(signal.butter(4, [2000 / (SR / 2), 8000 / (SR / 2)], 'band', output='sos'), x)
        self.assertGreater(float(np.sqrt(np.mean(hf[:int(0.012 * SR)] ** 2))), 5 * float(np.sqrt(np.mean(hf[int(0.2 * SR):int(0.4 * SR)] ** 2))))   # a click at the front
        env = np.abs(x)
        pk = int(np.argmax(env))
        self.assertLess(pk / SR, 0.03)                                                # peaks within 30 ms

    def test_deterministic(self):
        a, b = sfx.synth(self.cfg['spec'], SR, seed=2), sfx.synth(self.cfg['spec'], SR, seed=2)
        self.assertTrue(np.array_equal(a, b))


class Air(unittest.TestCase):
    def band(self, y):
        sp = np.abs(np.fft.rfft(y[:, 0])) ** 2
        f = np.fft.rfftfreq(len(y), 1 / SR)
        return 10 * np.log10(sp[(f > 8000) & (f < 16000)].sum() / sp.sum() + 1e-20)

    def test_air_creates_content_a_shelf_cannot(self):
        x = np.random.default_rng(1).normal(0, 0.1, (SR * 2, 2)).astype(np.float32)
        x = signal.sosfilt(signal.butter(10, 5000 / (SR / 2), 'low', output='sos'), x, axis=0).astype(np.float32)
        y = fx_engine.apply(x, SR, [{'type': 'air', 'corner_hz': 4000, 'drive': 4, 'amount_db': -20}], seed=1)
        self.assertGreater(self.band(y), self.band(x) + 10)

    def test_silence_stays_silent_and_library_is_valid(self):
        z = np.zeros((SR, 2), np.float32)
        self.assertLess(float(np.abs(fx_engine.apply(z, SR, [{'type': 'air'}], seed=1)).max()), 1e-6)
        self.assertEqual(fx_engine.library_problems(), [])


if __name__ == '__main__':
    unittest.main()
