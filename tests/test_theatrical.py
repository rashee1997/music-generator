"""The theatrical engine additions, measured: loudness-dependent timbre, section scatter, phrase elasticity.

These assert the structure and the direction of the effect, not a calibrated sound: the numbers are starting
values until a reference cue is measured (knowledgebase/sound-design/theatrical-realism.md).
"""
import os
import sys
import unittest

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import dsp          # noqa: E402
import humanize as hz  # noqa: E402
import mixer        # noqa: E402

SR = 22050


def _mono(x):
    x = np.asarray(x, dtype=np.float64)
    return x.mean(axis=1) if x.ndim == 2 else x


def _stereo(x):
    x = np.asarray(x, dtype=np.float32)
    return np.stack([x, x], axis=1) if x.ndim == 1 else x


def _tone(f, seconds, amp):
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


def _harmonic_db(x, f0=220.0, n=3):
    """Third harmonic over fundamental, dB, from one Welch PSD."""
    y = _mono(x)
    f, p = signal.welch(y, fs=SR, nperseg=min(8192, max(256, len(y))))
    def band(centre):
        m = (f >= centre * 0.94) & (f <= centre * 1.06)
        return float(p[m].sum()) + 1e-20
    return 10.0 * np.log10(band(n * f0) / band(f0))


class LevelTimbreTests(unittest.TestCase):
    def setUp(self):
        n = int(1.5 * SR)
        t = np.arange(n) / SR
        self.x = np.zeros(2 * n, np.float32)
        self.x[:n] = (0.02 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)   # quiet
        self.x[n:] = (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)    # loud, same waveform

    def test_loud_half_gains_more_harmonic_content_than_the_quiet_half(self):
        y = dsp.level_timbre(self.x, sr=SR, drive=0.6, tilt_db=0.0, amount=1.0)
        half = len(self.x) // 2
        before = _harmonic_db(self.x[half:]) - _harmonic_db(self.x[:half])
        after = _harmonic_db(y[half:]) - _harmonic_db(y[:half])
        self.assertGreater(after, before + 3.0)
        self.assertGreater(after, 3.0)

    def test_level_is_compensated(self):
        y = dsp.level_timbre(self.x, sr=SR, drive=0.6, tilt_db=2.0)
        before = float(np.sqrt(np.mean(self.x.astype(np.float64) ** 2)))
        after = float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))
        self.assertAlmostEqual(after / before, 1.0, places=2)

    def test_off_is_a_no_op_and_a_single_dynamic_is_left_alone(self):
        np.testing.assert_allclose(dsp.level_timbre(self.x, sr=SR, drive=0.0, tilt_db=0.0).ravel(), self.x, atol=1e-7)
        n = int(1.0 * SR)
        t = np.arange(n) / SR
        flat = (0.2 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
        np.testing.assert_allclose(dsp.level_timbre(flat, sr=SR).ravel(), flat, atol=1e-7)

    def test_bad_values_are_errors(self):
        for kw in (dict(band_hz=(9000.0, 100.0)), dict(oversample=3), dict(drive=-1.0),
                   dict(quiet_pct=90.0, loud_pct=10.0)):
            with self.assertRaises(ValueError):
                dsp.level_timbre(self.x, sr=SR, **kw)


class EnsembleTests(unittest.TestCase):
    def _notes(self, n=4):
        return [dict(t=float(i), d=0.5, p=60 + i, v=0.8) for i in range(n)]

    def test_every_written_note_becomes_every_player(self):
        out = hz.ensemble_expand(self._notes(3), players=4, spread_cents=6.0, spread_ms=10.0, seed=1)
        self.assertEqual(len(out), 12)
        self.assertEqual(sorted({e['player'] for e in out}), [0, 1, 2, 3])
        for p in range(4):
            self.assertEqual(len([e for e in out if e['player'] == p]), 3)

    def test_players_are_a_few_cents_and_a_few_ms_apart(self):
        out = hz.ensemble_expand(self._notes(6), players=4, spread_cents=6.0, spread_ms=10.0, seed=1)
        first = [e for e in out if e['p'] == 60]
        cents = np.array([e['c'] for e in first])
        times = np.array([e['t'] for e in first])
        self.assertGreaterEqual(float(np.std(cents)), 1.0)
        self.assertLessEqual(float(np.max(np.abs(cents))), 9.0)
        self.assertGreater(float(np.max(times) - np.min(times)), 0.0)
        self.assertLess(float(np.max(np.abs(times))), 0.03)          # beats at 96 bpm: under ~19 ms

    def test_it_is_deterministic_and_keeps_the_line(self):
        a = hz.ensemble_expand(self._notes(), players=3, seed=7)
        b = hz.ensemble_expand(self._notes(), players=3, seed=7)
        self.assertEqual([(round(e['t'], 9), e['p'], round(e['c'], 9)) for e in a],
                         [(round(e['t'], 9), e['p'], round(e['c'], 9)) for e in b])
        self.assertEqual(sorted(e['p'] for e in a), [60, 60, 60, 61, 61, 61, 62, 62, 62, 63, 63, 63])
        self.assertTrue(all(0.7 <= e['v'] <= 0.9 for e in a))

    def test_a_solo_is_refused(self):
        with self.assertRaises(ValueError):
            hz.ensemble_expand(self._notes(), players=1)
        with self.assertRaises(ValueError):
            hz.ensemble_expand(self._notes(), players=17)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tm = hz.TempoMap(96, total_beats=16, rubato=0.0, wander=0.0, ritard=0.0)

    def test_a_section_block_expands_before_the_renderer_sees_it(self):
        import render_natural as rn
        tr = dict(name='Violins', role='chord', instrument='piano',
                  ensemble=dict(players=3, spread_cents=4.0, spread_ms=8.0))
        notes = [dict(t=float(i), d=1.0, p=60, v=0.7) for i in range(4)]
        out = rn._expand_ensemble(tr, notes, self.tm, 'chord', 1)
        self.assertEqual(len(out), 12)
        self.assertTrue(all('player' in e for e in out))

    def test_ensemble_is_refused_on_a_drum_part_and_a_one_player_section(self):
        import render_natural as rn
        with self.assertRaises(ValueError):
            rn._expand_ensemble(dict(name='Kit', role='drum', ensemble=dict(players=3)), [], self.tm, 'drum', 1)
        with self.assertRaises(ValueError):
            rn._expand_ensemble(dict(name='Solo', role='melody', ensemble=dict(players=1)), [], self.tm, 'melody', 1)

    def test_a_timbre_block_is_applied_and_unknown_keys_are_errors(self):
        import render_natural as rn
        x = _stereo(_tone(220, 1.5, 0.25))
        x[:len(x) // 2] *= 0.05
        tr = dict(name='Horns', instrument='piano', timbre_dynamics=dict(drive=0.6, tilt_db=0.0, amount=1.0))
        y = rn._apply_timbre(tr, x)
        self.assertEqual(y.shape, x.shape)
        self.assertGreater(float(np.max(np.abs(y - x))), 1e-5)
        with self.assertRaises(ValueError):
            rn._apply_timbre(dict(name='Horns', instrument='piano', timbre_dynamics=dict(drive=0.5, colour='red')), x)
        with self.assertRaises(ValueError):
            rn._apply_timbre(dict(name='Room', instrument='env:room', timbre_dynamics=dict(drive=0.5)), x)


class TheatricalBusTests(unittest.TestCase):
    def tearDown(self):
        mixer.reset_context()

    def test_the_stage_runs_in_the_mix_and_leans_the_low_mids(self):
        n = int(2.0 * SR)
        t = np.arange(n) / SR
        stems = {'bed': _stereo(0.3 * np.sin(2 * np.pi * 300.0 * t) + 0.05 * np.sin(2 * np.pi * 1200.0 * t))}
        score = dict(bpm=96, space='none', tracks=[dict(name='bed', role='chord', instrument='piano',
                                                        notes=[dict(t=0.0, d=4.0, p=60, v=0.7)])])
        def energy(a, f):
            z = _mono(a)
            fr, p = signal.welch(z, fs=SR, nperseg=4096)
            m = (fr >= f * 0.9) & (fr <= f * 1.1)
            return float(p[m].sum())
        import mix_context
        plain_ctx = mix_context.MixContext({'theatrical': {'enabled': False}}, {}, name='plain')
        leaned_ctx = mix_context.MixContext({'theatrical': {'enabled': True,
                                                            'low_mid': {'enabled': True, 'range_db': 2.0,
                                                                        'ratio': 2.0, 'max_dip_db': 2.0},
                                                            'air': {'enabled': False}}}, {}, name='leaned')
        plain = mixer.mix_stems(score, {k: v.copy() for k, v in stems.items()}, sr=SR, ctx=plain_ctx)
        leaned = mixer.mix_stems(score, {k: v.copy() for k, v in stems.items()}, sr=SR, ctx=leaned_ctx)
        self.assertEqual(plain.shape, leaned.shape)
        self.assertLess(energy(leaned, 300.0), 0.9 * energy(plain, 300.0))
        self.assertAlmostEqual(energy(leaned, 1200.0) / energy(plain, 1200.0), 1.0, places=1)


class TheatricalBusUnitTests(unittest.TestCase):
    def test_the_schema_rejects_an_unknown_theatrical_key(self):
        import mix_schema
        self.assertEqual(mix_schema.validate({'theatrical': {'enabled': True,
                                                             'detail': {'duck_db': 2.0}}}), [])
        bad = mix_schema.validate({'theatrical': {'detail': {'colour': 'red'}}})
        self.assertTrue(any('theatrical.detail.colour' in p for p in bad))


    def test_the_send_ducks_through_an_attack_and_returns(self):
        n = int(1.0 * SR)
        x = np.zeros((n, 2), np.float32)
        x[n // 4:n // 4 + 40] = 1.0                                  # one sharp attack
        x[n // 4 + 40:n // 2] = 0.02                                 # and a quiet body
        g = mixer.theatrical_send_gain(x, SR, {'detail': {'enabled': True, 'duck_db': 4.0}})
        self.assertLess(float(g[n // 4 + 2]), 0.8)                   # the attack is protected
        self.assertGreater(float(g[-1]), 0.99)                       # the tail is not
        off = mixer.theatrical_send_gain(x, SR, {'detail': {'enabled': False}})
        np.testing.assert_allclose(off, 1.0)

    def test_low_mid_stage_dips_only_the_named_band(self):
        t = np.arange(int(2.0 * SR)) / SR
        low = (0.3 * np.sin(2 * np.pi * 300.0 * t)).astype(np.float32)
        high = (0.1 * np.sin(2 * np.pi * 5000.0 * t)).astype(np.float32)
        x = _stereo(low + high)
        cfg = {'low_mid': {'enabled': True, 'max_dip_db': 2.0, 'range_db': 2.0, 'ratio': 2.0},
               'air': {'enabled': False}}
        y = mixer.theatrical_tone(x, SR, cfg)
        def energy(a, f):
            z = _mono(a)
            fr, p = signal.welch(z, fs=SR, nperseg=8192)
            m = (fr >= f * 0.95) & (fr <= f * 1.05)
            return float(p[m].sum())
        self.assertLess(energy(y, 300.0), energy(x, 300.0))
        self.assertAlmostEqual(energy(y, 5000.0) / energy(x, 5000.0), 1.0, places=2)

    def test_disabled_stage_is_a_no_op(self):
        x = _stereo(_tone(220, 1.0, 0.2))
        np.testing.assert_allclose(mixer.theatrical_tone(x, SR, {'low_mid': {'enabled': False},
                                                                 'air': {'enabled': False}}), x, atol=1e-7)


class ElasticTests(unittest.TestCase):
    def _length(self, tm, beat):
        return float(tm.sec(beat))

    def test_elasticity_moves_the_bar_not_the_note(self):
        plain = hz.TempoMap(96, total_beats=64, rubato=0.0, wander=0.0, ritard=0.0, seed=3)
        elastic = hz.TempoMap(96, total_beats=64, rubato=0.0, wander=0.0, ritard=0.0, seed=3,
                              elastic=0.05, elastic_corr_beats=12.0)
        grid = np.arange(0.0, 60.0, 0.25)
        d0 = np.diff(plain.sec(grid))
        d1 = np.diff(elastic.sec(grid))
        dev = d1 / d0 - 1.0
        from scipy.ndimage import uniform_filter1d
        smooth = uniform_filter1d(dev, size=16, mode='nearest')
        self.assertGreater(float(np.std(smooth)), 0.005)            # more than half a percent at bar scale
        self.assertLess(abs(float(np.mean(dev))), 0.01)             # no average tempo change

    def test_a_breath_holds_the_whole_ensemble_after_its_beat(self):
        tm = hz.TempoMap(96, total_beats=32, rubato=0.0, wander=0.0, ritard=0.0, breaths=[16], breath_s=0.12)
        self.assertAlmostEqual(self._length(tm, 16.0) - self._length(tm, 15.0), 0.625, places=2)
        self.assertAlmostEqual(self._length(tm, 17.0) - self._length(tm, 16.0), 0.625 + 0.12, places=2)

    def test_tempo_map_for_reads_the_score_block_and_rejects_unknown_keys(self):
        tm = hz.tempo_map_for(dict(bpm=96, seed=1, elastic=dict(amount=0.04, corr_beats=10.0,
                                                               breaths=[8], breath_s=0.08)))
        self.assertAlmostEqual(float(tm.sec(8.1) - tm.sec(8.0)), 0.0625 + 0.08, places=2)
        with self.assertRaises(ValueError):
            hz.tempo_map_for(dict(bpm=96, elastic=dict(swing=0.2)))

    def test_no_elastic_block_changes_nothing(self):
        a = hz.tempo_map_for(dict(bpm=96, seed=2, rubato=0.02, ritard=0.3))
        b = hz.TempoMap(96, total_beats=a.total_beats, rubato=0.02, wander=0.004, ritard=0.3,
                        ritard_beats=6, phrase_beats=16, seed=2)
        grid = np.arange(0.0, 40.0, 1.0)
        np.testing.assert_allclose(a.sec(grid), b.sec(grid), atol=1e-9)


if __name__ == '__main__':
    unittest.main()
