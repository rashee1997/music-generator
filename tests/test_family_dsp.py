"""Instrument families: declared behaviour only, same stem when nothing is declared."""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import families      # noqa: E402
import family_dsp    # noqa: E402

SR = 22050


def tone(f, s, a):
    t = np.arange(int(s * SR)) / SR
    return (a * np.sin(2 * np.pi * f * t)).astype(np.float32)[:, None].repeat(2, 1)


def hf_share(y):
    sp = np.abs(np.fft.rfft(y[:, 0] * np.hanning(len(y)))) ** 2
    f = np.fft.rfftfreq(len(y), 1 / SR)
    return float(sp[f > 1500].sum() / sp.sum())


class Effective(unittest.TestCase):
    def test_nothing_declared_nothing_applied(self):
        stem = tone(220, 1, 0.3)
        self.assertIs(family_dsp.apply(stem, {'instrument': 'cello'}, {}, SR), stem)          # a legacy name is not a declaration
        self.assertEqual(families.effective({'instrument': 'cello'}, {}), {})

    def test_declared_family_brings_its_blocks_and_a_preset_block_overrides(self):
        e = families.effective({'family': 'bowed'}, {})
        self.assertEqual(e['bloom']['start_depth'], 0.0)
        self.assertEqual(e['noise']['kind'], 'bow')
        e = families.effective({'family': 'bowed', 'bloom': {'ramp_s': 0.9}}, {})
        self.assertEqual((e['bloom']['ramp_s'], e['bloom']['start_depth']), (0.9, 0.0))
        self.assertNotIn('noise', families.effective({'family': 'bowed', 'noise': None}, {}))

    def test_a_block_without_a_family_still_applies(self):
        self.assertEqual(families.effective({}, {'snap': {'attack': 2.0, 'sustain': 0.0}})['snap']['attack'], 2.0)


class Treatments(unittest.TestCase):
    def test_noise_follows_the_stem_and_silence_stays_silent(self):
        y = np.concatenate([tone(220, 1, 0.3), np.zeros((SR, 2), np.float32)])
        out = family_dsp.noise_layer(y, SR, 'bow', -30.0, seed=1)
        self.assertGreater(float(np.abs(out[:SR] - y[:SR]).max()), 1e-4)
        self.assertLess(float(np.abs(out[int(1.2 * SR):] - y[int(1.2 * SR):]).max()), 1e-3)
        with self.assertRaises(ValueError):
            family_dsp.noise_layer(y, SR, 'mist', -30.0)

    def test_flare_opens_a_loud_note_and_leaves_a_quiet_one(self):
        rng = np.random.default_rng(1)
        base = rng.normal(0, 1, 2 * SR).astype(np.float32)[:, None].repeat(2, 1)
        sos = signal.butter(2, 800 / (SR / 2), 'low', output='sos')
        base = signal.sosfilt(sos, base, axis=0).astype(np.float32)
        loud, soft = base * 0.5 / np.abs(base).max(), base * 0.02 / np.abs(base).max()
        shape = np.concatenate([soft[:SR], loud[SR:]])                              # the peak is the loud half
        out = family_dsp.brass_flare(shape, SR, 0.62, 10.0, 2200.0)
        self.assertGreater(hf_share(out[SR:]), hf_share(shape[SR:]) * 1.3)
        self.assertAlmostEqual(hf_share(out[:SR]) / hf_share(shape[:SR]), 1.0, delta=0.05)

    def test_snap_sharpens_the_front(self):
        y = np.zeros((SR, 2), np.float32)
        n = int(0.3 * SR)
        t = np.arange(n) / SR
        for k in (0.1, 0.5):
            i = int(k * SR)
            y[i:i + n] += (0.5 * np.sin(2 * np.pi * 60 * t) * np.exp(-t * 10) * np.minimum(1, t / 0.01))[:, None]
        out = family_dsp.apply(y, {}, {'snap': {'attack': 6.0, 'sustain': -2.0}}, SR)
        i = int(0.1 * SR)
        self.assertGreater(np.abs(out[i:i + 300]).max() / np.abs(out[i + 3000:i + 3300]).max(),
                           np.abs(y[i:i + 300]).max() / np.abs(y[i + 3000:i + 3300]).max())


if __name__ == '__main__':
    unittest.main()


class BloomInRender(unittest.TestCase):
    """The bloom changes how a held note's vibrato grows, and only for a declared bloom."""
    def stem(self, extra):
        import pretty_midi
        import render_natural as rn
        tim = os.path.join(os.path.dirname(pretty_midi.__file__), 'TimGM6mb.sf2')
        score = {'bpm': 60, 'ts': [4, 4], 'tracks': [dict(name='c', instrument='cello', role='melody', vibrato={'depth_cents': 40, 'rate_hz': 5.5, 'delay_ms': 100},
                                                         notes=[dict(t=0, d=6, p=48, v=0.8)], humanize={'preset': 'tight'}, **extra)]}
        stems, _tm = rn.build_stems(score, tim, seed=3, verbose=False)
        return stems['c']

    @staticmethod
    def depth_cents(x, sr, a, b):
        """Std of the instantaneous pitch (cents) of the fundamental inside [a, b] seconds."""
        y = x.mean(axis=1)
        sos = signal.butter(4, [105 / (sr / 2), 160 / (sr / 2)], 'band', output='sos')
        ph = np.unwrap(np.angle(signal.hilbert(signal.sosfiltfilt(sos, y))))
        f = np.diff(ph) * sr / (2 * np.pi)
        seg = f[int(a * sr):int(b * sr)]
        return float(np.std(1200 * np.log2(np.clip(seg, 50, None) / np.median(seg))))

    def test_bloom_starts_pure_and_warms_up(self):
        plain = self.stem({})
        bloom = self.stem({'bloom': {'start_depth': 0.0, 'ramp_s': 2.5}})
        sr = 44100
        self.assertLess(self.depth_cents(bloom, sr, 0.3, 1.0), 0.6 * self.depth_cents(plain, sr, 0.3, 1.0))
        self.assertGreater(self.depth_cents(bloom, sr, 4.0, 5.5), 0.6 * self.depth_cents(plain, sr, 4.0, 5.5))
