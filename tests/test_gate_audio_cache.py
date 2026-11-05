"""The gate's shared analysis: one load, one STFT, one decimation, computed lazily and safely across threads."""
import os
import sys
import tempfile
import threading
import unittest

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

from gate_audio import Signal, GateAudio, DECIM_SR  # noqa: E402


def tone(sr=44100, seconds=1.0, freq=220.0):
    t = np.arange(int(sr * seconds)) / sr
    return 0.3 * np.sin(2 * np.pi * freq * t)


class OneComputation(unittest.TestCase):
    def setUp(self):
        self.sig = Signal(tone(), 44100)

    def test_decimation_is_computed_once(self):
        self.assertIs(self.sig.decim, self.sig.decim)
        self.assertAlmostEqual(self.sig.decim.size, len(self.sig.mono) * DECIM_SR / 44100.0, delta=2)

    def test_stft_and_onset_are_computed_once(self):
        self.assertIs(self.sig.stft, self.sig.stft)
        self.assertIs(self.sig.onset_env, self.sig.onset_env)

    def test_the_default_frame_levels_are_cached(self):
        a = self.sig.frame_db()
        b = self.sig.frame_db()
        self.assertIs(a, b)
        self.assertIsNot(a, self.sig.frame_db(hop_ms=10.0))

    def test_invalidate_drops_every_cached_item(self):
        before = self.sig.decim
        self.sig.invalidate()
        self.assertEqual(self.sig._cache, {})
        self.assertIsNot(before, self.sig.decim)

    def test_threads_share_one_result(self):
        sig = Signal(tone(), 44100)
        seen = []

        def work():
            seen.append(id(sig.decim))

        threads = [threading.Thread(target=work) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(set(seen)), 1, 'two threads computed the same analysis twice')


class TheFileIsReadOnce(unittest.TestCase):
    def test_stereo_and_mono_agree_with_one_read(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'a.wav')
            x = tone(seconds=0.5)
            sf.write(path, np.stack([x, x], axis=1), 44100, subtype='PCM_16')
            sig = GateAudio(path)
            self.assertEqual(sig.stereo.shape[1], 2)
            self.assertEqual(sig.channels, 2)
            self.assertAlmostEqual(sig.dur, 0.5, places=2)
            np.testing.assert_allclose(sig.mono, sig.stereo.mean(axis=1))

    def test_a_mono_file_is_analysed_as_one_channel(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'm.wav')
            x = tone(seconds=0.3)
            sf.write(path, x, 44100, subtype='PCM_16')
            sig = GateAudio(path)
            self.assertEqual(sig.stereo.shape[1], 1)
            np.testing.assert_allclose(sig.mono, sig.stereo[:, 0], atol=1e-4)

    def test_nan_audio_is_refused(self):
        with self.assertRaises(ValueError):
            Signal(np.array([0.0, np.nan, 0.1]), 44100)


if __name__ == '__main__':
    unittest.main()
