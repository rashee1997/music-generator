"""The level-aware roughness model: published shape, level, masking, and legacy equivalence.

Fixtures are synthetic (additive synthesis, harmonic series 1/k^1.1) - no downloaded material.
The published shape being asserted: roughness is ~0 at unison, peaks near a quarter of the critical
bandwidth, has fallen far below the peak by one critical bandwidth, rises with level inside one file, and
is reduced when a partial sits under a louder partial in the same critical band. Sources and the argument
for each number: knowledgebase/sound-design/roughness.md.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import naturalness_check as nc  # noqa: E402
import gate_profiles as gpf  # noqa: E402

SR = 44100


def tone(f, level_db=0.0, secs=4.0, partials=10):
    t = np.arange(int(SR * secs)) / SR
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.1 for k in range(1, partials + 1))
    x = x / np.max(np.abs(x))
    return x * 10 ** (level_db / 20.0)


def stereo(x):
    return np.stack([x, x], 1).astype(np.float32)


def cb_hz(f):
    """Critical bandwidth (Zwicker): 25 + 75*(1 + 1.4*(f/1000)**2)**0.69."""
    return 25.0 + 75.0 * (1.0 + 1.4 * (f / 1000.0) ** 2) ** 0.69


def score(audio, model, score=None):
    return nc.cochlear_roughness_check(audio, sr=SR, model=model, score=score)


def mean(audio, model):
    return score(audio, model)[1]['mean_roughness']


class LegacyIsUnchanged(unittest.TestCase):
    """model="legacy" must reproduce the original computation exactly, not approximately."""

    def test_default_equals_explicit_legacy_to_four_decimals(self):
        x = stereo(tone(262.0, -18.0) + tone(277.0, -18.0) + tone(392.0, -24.0))
        _, a = nc.cochlear_roughness_check(x, sr=SR)
        _, b = nc.cochlear_roughness_check(x, sr=SR, model='legacy')
        self.assertEqual(a['mean_roughness'], b['mean_roughness'])
        self.assertEqual(a['max_roughness'], b['max_roughness'])
        self.assertGreater(a['mean_roughness'], 0.0)

    def test_a_semitone_still_fails_under_the_legacy_model(self):
        rows, _ = score(stereo(tone(262.0) + tone(277.0)), 'legacy')
        self.assertIn('FAIL', [r[0] for r in rows])

    def test_a_consonant_triad_still_passes_under_the_legacy_model(self):
        rows, _ = score(stereo(tone(261.6) + tone(329.6) + tone(392.0)), 'legacy')
        self.assertNotIn('FAIL', [r[0] for r in rows])


class PublishedShape(unittest.TestCase):
    def peak_df(self, root):
        scan = [(df, mean(stereo(tone(root, -24.0) + tone(root + df, -24.0)), 'level_aware'))
                for df in np.arange(2.0, cb_hz(root) * 1.5, max(1.0, cb_hz(root) / 40))]
        return max(scan, key=lambda p: p[1])

    def test_unison_has_nothing_to_beat(self):
        self.assertLess(mean(stereo(tone(440.0, -24.0)), 'level_aware'), 0.01)

    def test_peak_near_a_quarter_critical_bandwidth(self):
        df, _ = self.peak_df(1000.0)
        self.assertGreater(df / cb_hz(1000.0), 0.08, f'peak at {df:.0f} Hz = {df / cb_hz(1000.0):.2f} CB')
        self.assertLess(df / cb_hz(1000.0), 0.45, f'peak at {df:.0f} Hz = {df / cb_hz(1000.0):.2f} CB')

    def test_roughness_falls_away_by_one_critical_bandwidth(self):
        peak = self.peak_df(1000.0)[1]
        at_cb = mean(stereo(tone(1000.0, -24.0) + tone(1000.0 + cb_hz(1000.0), -24.0)), 'level_aware')
        self.assertLess(at_cb, 0.25 * peak, f'{at_cb:.4f} vs peak {peak:.4f}')

    def test_the_peak_separation_grows_with_register(self):
        low, high = self.peak_df(220.0)[0], self.peak_df(2093.0)[0]
        self.assertGreater(high, low, f'low register peak {low:.1f} Hz, high register {high:.1f} Hz')


class LevelMattersInsideOneFile(unittest.TestCase):
    """A pp file and an ff file played at matched loudness are equal by design (the model calibrates against the
    file's own loudness). Inside one file the loud half must score higher."""

    def frames(self):
        q = np.arange(int(SR * 8.0)) / SR
        env = np.where(q < 4.0, 10 ** (-36 / 20.0), 10 ** (-12 / 20.0))
        mother = (tone(262.0, 0.0, secs=8.0) + tone(277.0, 0.0, secs=8.0)) * env / 2.0
        m = score(stereo(mother), 'level_aware')[1]
        return [v for v in m['frames'][:3] if v], [v for v in m['frames'][-3:] if v], m

    def test_the_loud_half_scores_higher(self):
        quiet, loud, _ = self.frames()
        self.assertGreater(np.mean(loud), 1.3 * np.mean(quiet))

    def test_the_legacy_model_cannot_see_the_difference(self):
        _, _, m = self.frames()
        leg = [v for v in m['frames_legacy'][:3] if v], [v for v in m['frames_legacy'][-3:] if v]
        self.assertAlmostEqual(np.mean(leg[1]) / np.mean(leg[0]), 1.0, places=2)

    def test_the_legacy_number_is_still_reported(self):
        rows, m = self.frames()[2], None
        x = score(stereo(tone(262.0, -24.0) + tone(277.0, -24.0)), 'level_aware')[0]
        self.assertTrue(any(r[1] == 'cochlear_roughness_legacy' and r[0] == 'INFO' for r in x))
        self.assertIn('mean_roughness_legacy', score(stereo(tone(262.0, -24.0) + tone(277.0, -24.0)), 'level_aware')[1])


class MaskingCounts(unittest.TestCase):
    def test_a_partial_under_a_louder_neighbour_in_the_same_band_is_attenuated(self):
        plain = stereo(tone(262.0, -24.0) + tone(277.0, -24.0))
        masked = stereo(tone(262.0, -24.0) + tone(277.0, -24.0) + tone(311.0, -12.0))
        self.assertLess(mean(masked, 'level_aware'), 0.6 * mean(plain, 'level_aware'))

    def test_the_attenuation_grows_with_the_masker(self):
        """The legacy model has no masking curve at all; this is the behaviour that is new."""
        pair = lambda mask_db: stereo(tone(262.0, -24.0) + tone(277.0, -24.0) + tone(311.0, mask_db))
        self.assertLess(mean(pair(-6.0), 'level_aware'), mean(pair(-24.0), 'level_aware'))


class ProfileOwnsTheModel(unittest.TestCase):
    def test_default_is_legacy(self):
        self.assertEqual(gpf.defaults('roughness')['model'], 'legacy')
        p = gpf.resolve(dict(piece_type='melodic', tracks=[]))
        self.assertEqual(p.param('roughness', 'model'), 'legacy')

    def test_the_old_knobs_still_work(self):
        p = gpf.resolve(dict(piece_type='tense', tracks=[], gate={'roughness': {'scale': 1.5}}))
        self.assertEqual(p.param('cochlear_roughness', 'scale'), 1.5)

    def test_a_bad_model_name_is_rejected(self):
        self.assertTrue(gpf.row_problems({'roughness': {'model': 'sethares_2000'}}, 'w'))

    def test_a_piece_can_ask_for_the_new_model(self):
        p = gpf.resolve(dict(piece_type='melodic', tracks=[], gate={'roughness': {'model': 'level_aware'}}))
        self.assertEqual(p.param('roughness', 'model'), 'level_aware')
        x = stereo(tone(262.0, -24.0) + tone(277.0, -24.0))
        rows, m = score(x, None, score=dict(piece_type='melodic', tracks=[],
                                            gate={'roughness': {'model': 'level_aware'}}))
        self.assertIn('mean_roughness_legacy', m)
        self.assertTrue(rows)


if __name__ == '__main__':
    unittest.main()
