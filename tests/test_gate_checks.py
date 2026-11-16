"""Each gate check must fire on a known defect and stay quiet on clean material.

The fixture is synthetic and deliberately simple, so a failure here means the measurement is wrong, not the music.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, HERE)

import gate_checks as gc
import gate_fixture as fx
import quality_gate as qg
from gate_audio import Signal


class GateCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stems = fx.build_stems()
        cls.score = fx.score()

    def pad(self):
        return Signal(self.stems['pad'], fx.SR)

    def test_clicks_clean_pad_has_none(self):
        res = gc.check_clicks(self.pad())
        self.assertEqual(res['mad_count'], 0, res['detail'])
        self.assertEqual(res['value'], 0.0)

    def test_clicks_fire_on_a_single_impulse(self):
        res = gc.check_clicks(Signal(fx.add_click(self.stems['pad'], at=3.0, amp=0.5), fx.SR))
        self.assertGreaterEqual(res['mad_count'], 1, res['detail'])
        self.assertEqual(res['threshold'], 0.0)

    def test_dropout_fires_on_a_hole(self):
        res = gc.check_dropout(Signal(fx.add_dropout(self.stems['pad'], at=3.0, ms=80), fx.SR))
        self.assertTrue(res['holes'], res['detail'])
        self.assertGreaterEqual(res['value'], 20.0)

    def test_cut_fires_at_a_section_boundary(self):
        sig = Signal(fx.add_cut(self.stems['pad'], at=4.0, ms=500), fx.SR)
        secs = gc.section_bounds(self.score, sig.dur)
        res = gc.check_cut(sig, [s['start_s'] for s in secs if s['start_s'] > 0.05])
        self.assertGreater(res['value'], res['threshold'], res['detail'])

    def test_cut_ignores_a_section_drop_that_stays_audible(self):
        x = np.asarray(self.stems['pad'], dtype=np.float64).copy()
        i = int(4.0 * fx.SR)
        k = int(0.01 * fx.SR)
        x[i:i + k] *= np.linspace(1.0, 0.2, k)
        x[i + k:] *= 0.2
        sig = Signal(x, fx.SR)
        secs = gc.section_bounds(self.score, sig.dur)
        res = gc.check_cut(sig, [s['start_s'] for s in secs if s['start_s'] > 0.05])
        self.assertEqual(res['value'], 0.0, res['detail'])

    def test_abrupt_end_fires_on_a_truncated_file(self):
        res = gc.check_abrupt_end(Signal(fx.truncate_end(self.stems['pad']), fx.SR))
        self.assertTrue(res['fail'], res['detail'])

    def test_abrupt_end_skips_a_stem_that_reaches_the_score_end(self):
        res = gc.check_abrupt_end(self.pad(), expected_dur=fx.DUR)
        self.assertTrue(res.get('skipped'), res['detail'])

    def test_dc_fires_on_an_offset(self):
        res = gc.check_dc(Signal(fx.add_dc(self.stems['bass'], offset=0.02), fx.SR))
        self.assertGreater(res['value'], res['threshold'], res['detail'])

    def test_dc_checks_all_multichannel_outputs(self):
        channels = np.zeros((fx.SR * 2, 4), dtype=np.float64)
        channels[:, 3] = 0.02
        res = gc.check_dc(Signal(channels, fx.SR))
        self.assertGreater(res['value'], res['threshold'], res['detail'])
        self.assertEqual(len(res['channel_means']), 4)

    def test_clipping_fires_on_hard_clip(self):
        res = gc.check_clipping(Signal(fx.clip_hard(self.stems['lead']), fx.SR))
        self.assertGreater(res['value'], 0.0, res['detail'])

    def test_clipping_checks_all_multichannel_outputs(self):
        channels = np.zeros((fx.SR, 4), dtype=np.float64)
        channels[-1, 3] = 1.0
        res = gc.check_clipping(Signal(channels, fx.SR))
        self.assertGreater(res['value'], 0.0, res['detail'])

    def test_flatness_quiet_on_a_tone_and_loud_on_noise(self):
        quiet = gc.check_flatness(self.pad())
        noisy = gc.check_flatness(Signal(fx.add_noise_burst(self.stems['pad']), fx.SR))
        self.assertEqual(quiet['windows'], 0, quiet['detail'])
        self.assertGreater(noisy['windows'], 0, noisy['detail'])

    def test_clicks_in_a_multichannel_master_are_checked_per_channel(self):
        """A click that only one channel carries must not disappear into the fold-down.

        The fixture puts a full-scale impulse on one channel and its mirror on another, which is exactly what a
        channel mean or a weight-summed fold cancels: the folded signal then has no event at all.
        """
        n = fx.SR * 3
        tone = 0.05 * np.sin(2 * np.pi * 220 * np.arange(n) / fx.SR)
        x = np.stack([tone] * 6, axis=1)
        x[int(1.5 * fx.SR), 2] += 0.6
        x[int(1.5 * fx.SR), 3] -= 0.6
        self.assertEqual(gc.check_clicks(Signal(x.mean(axis=1), fx.SR))['mad_count'], 0,
                         'the fold hides the impulse: this test is only meaningful if it does')
        per_channel = qg.per_channel_clicks(x, fx.SR)
        self.assertEqual(len(per_channel), 6)
        self.assertGreater(max(c['mad_count'] for c in per_channel), 0)
        self.assertEqual(qg.per_channel_clicks(tone, fx.SR), [], 'a mono signal has no per-channel pass')

    def test_tick_is_not_periodic_on_clean_material(self):
        res = gc.check_tick(self.pad())
        self.assertFalse(res['periodic'], res['detail'])

    def test_tick_fires_on_a_regular_train(self):
        res = gc.check_tick(Signal(fx.add_tick(self.stems['pad']), fx.SR))
        self.assertTrue(res['periodic'], res['detail'])
        self.assertGreaterEqual(res['rise_db'], 3.0, res['detail'])

    def test_a_level_swing_is_not_a_tick(self):
        """A tremolo is periodic in both spectrum and level, but it is not a transient, so it is not a tick train.

        The periodic evidence alone does flag it (rho and the grid match), so the peak-rise measurement is what
        separates the two. A 4 Hz swing of this depth is a musical gesture, not the machine-gun defect the row names.
        """
        pad = self.stems['pad']
        t = np.arange(pad.size) / fx.SR
        res = gc.check_tick(Signal(pad * (1.0 + 0.40 * np.sin(2 * np.pi * 4.0 * t)), fx.SR))
        self.assertGreaterEqual(res['value'], 0.35, res['detail'])        # periodic in the spectrum
        self.assertGreaterEqual(res['grid_matched'], 6, res['detail'])    # and on a grid
        self.assertFalse(res['periodic'], res['detail'])
        self.assertLess(res['rise_db'], 3.0, res['detail'])

    def test_section_energy_follows_the_score_dynamics(self):
        res = gc.section_energy(Signal(fx.build_mix(self.stems), fx.SR), self.score)
        self.assertFalse(res.get('skipped'), res['detail'])
        self.assertEqual(len(res['table']), 4)
        self.assertGreaterEqual(res['value'], res['threshold'], res['detail'])

    def test_shared_cache_is_used(self):
        sig = self.pad()
        _ = sig.frame_db()
        key = next(k for k in sig._cache if k.startswith('frame_db:'))
        first = sig._cache[key]
        _ = sig.frame_db()
        self.assertIs(first, sig._cache[key])

    def test_tempo_reports_a_number_or_says_why(self):
        res = gc.check_tempo(Signal(fx.build_mix(self.stems), fx.SR), 120.0)
        self.assertTrue(res.get('skipped') or res['measured_bpm'] > 0.0, res['detail'])


if __name__ == '__main__':
    unittest.main()
