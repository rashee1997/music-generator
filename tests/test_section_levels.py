"""mastering.section_levels: contrast between sections from the plan's energies, loudness target kept."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import mixer         # noqa: E402
import mix_schema    # noqa: E402
from mix_engine import mastering   # noqa: E402

SR = 44100


def music(seconds=24):
    t = np.arange(seconds * SR) / SR
    x = 0.12 * np.sin(2 * np.pi * 220 * t) + 0.05 * np.sin(2 * np.pi * 880 * t) + 0.02 * np.random.default_rng(1).normal(0, 1, len(t))
    return np.stack([x, x], 1).astype(np.float32)


SECTIONS = [dict(name='a', start_s=0.0, end_s=8.0, energy=0.15), dict(name='b', start_s=8.0, end_s=16.0, energy=0.5),
            dict(name='c', start_s=16.0, end_s=24.0, energy=1.0)]


def section_db(y, a, b):
    seg = y[int(a * SR):int(b * SR)]
    return 10 * np.log10(np.mean(seg ** 2) + 1e-12)


class Gain(unittest.TestCase):
    def test_curve_follows_energy_and_is_centred(self):
        g = mastering.section_gain(24 * SR, SR, SECTIONS, 12.0, 1.0)
        db = 20 * np.log10(g)
        self.assertGreater(db[int(20 * SR)], db[int(12 * SR)])
        self.assertGreater(db[int(12 * SR)], db[int(4 * SR)])
        self.assertAlmostEqual(db[int(20 * SR)] - db[int(4 * SR)], 12.0 * (1.0 - 0.15), delta=0.5)
        self.assertTrue(np.all(np.diff(db) < 0.01))                    # no jumps: the steps are ramped

    def test_nothing_to_contrast_is_none(self):
        self.assertIsNone(mastering.section_gain(SR, SR, [SECTIONS[0]], 10.0, 1.0))
        self.assertIsNone(mastering.section_gain(SR, SR, [dict(start_s=0, end_s=1), dict(start_s=1, end_s=2)], 10.0, 1.0))


class Chain(unittest.TestCase):
    def tearDown(self):
        mixer.reset_context()

    def run_chain(self, section_levels):
        mx = mix_schema.with_defaults({'mastering': {'section_levels': section_levels}} if section_levels else {})
        mixer._install(mx)
        return mixer.master_chain(music(), {'lufs': -16.0, 'true_peak': -1.5, '_sections': SECTIONS}, SR)

    def test_contrast_widens_and_the_target_still_lands(self):
        flat, wide = self.run_chain(None), self.run_chain({'range_db': 12.0, 'ramp_s': 1.0})
        spread = lambda y: section_db(y, 17, 23) - section_db(y, 1, 7)
        self.assertGreater(spread(wide), spread(flat) + 4.0)
        self.assertAlmostEqual(mixer.master_measures(wide, SR)['lufs'], -16.0, delta=0.6)

    def test_off_by_default(self):
        self.assertIsNone(mix_schema.with_defaults({})['mastering']['section_levels'])
        self.assertEqual(mix_schema.validate(mix_schema.with_defaults({})), [])


if __name__ == '__main__':
    unittest.main()
