"""realism_report's eight measurements: each one has a positive and a negative control.

A measurement that cannot fail is not a measurement. These are synthetic signals with a known answer, not a
claim about any rendered piece.
"""
import os
import sys
import unittest

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import realism_report as rr  # noqa: E402

SR = 22050


def _stereo(x):
    x = np.asarray(x, dtype=np.float32)
    return np.stack([x, x], axis=1) if x.ndim == 1 else x


def _tone(f, seconds, amp):
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


class TimbreTests(unittest.TestCase):
    def test_a_loud_half_with_more_partials_passes(self):
        quiet = _tone(220, 3.0, 0.02) + _tone(660, 3.0, 0.00005) + _tone(3300, 3.0, 0.00002)
        loud = _tone(220, 3.0, 0.4) + _tone(660, 3.0, 0.12) + _tone(3300, 3.0, 0.03)
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        r = rr.timbre_loudness(f)
        self.assertGreater(r['value'], 0.8)
        self.assertEqual(r['verdict'], 'PASS')

    def test_the_same_waveform_at_two_levels_fails(self):
        quiet = _tone(220, 3.0, 0.02)
        loud = _tone(220, 3.0, 0.4)
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        r = rr.timbre_loudness(f)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertLess(abs(r['value']), 0.5)


class LowMidTests(unittest.TestCase):
    def test_a_thick_300_hz_layer_is_flagged(self):
        x = _tone(60, 4.0, 0.03) + _tone(300, 4.0, 0.3) + _tone(1200, 4.0, 0.05)
        r = rr.low_mid_bands(_stereo(x), SR)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertGreater(r['value'], 0.0)

    def test_sub_authority_with_lean_low_mids_passes(self):
        x = _tone(55, 4.0, 0.5) + _tone(300, 4.0, 0.01) + _tone(1200, 4.0, 0.1)
        r = rr.low_mid_bands(_stereo(x), SR)
        self.assertEqual(r['verdict'], 'PASS')
        self.assertLess(r['value'], 0.0)


class OpennessTests(unittest.TestCase):
    def test_a_loud_section_that_loses_its_air_is_flagged(self):
        rng = np.random.default_rng(2)
        quiet = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.02
        loud = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.3
        sos = signal.butter(6, 5000.0, btype='low', fs=SR, output='sos')
        loud = signal.sosfilt(sos, loud).astype(np.float32)
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        r = rr.openness(f)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertLess(r['value'], -1.0)

    def test_air_kept_at_the_peak_passes(self):
        rng = np.random.default_rng(3)
        quiet = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.02
        loud = rng.standard_normal(int(3 * SR)).astype(np.float32) * 0.3
        f = rr._frame_features(_stereo(np.concatenate([quiet, loud])), SR)
        self.assertEqual(rr.openness(f)['verdict'], 'PASS')


class DepthTests(unittest.TestCase):
    def test_dry_detail_in_front_of_a_room_passes_and_a_wash_fails(self):
        rng = np.random.default_rng(4)
        dry = _stereo(rng.standard_normal(int(4 * SR)).astype(np.float32) * 0.1)
        room = np.zeros_like(dry)
        k = int(0.06 * SR)
        room[k:] = dry[:-k] * 0.25
        good = rr.depth(_stereo(dry + room), [dry], SR)
        self.assertEqual(good['verdict'], 'PASS')
        wash = rr.depth(_stereo(dry + room * 12.0), [dry], SR)
        self.assertEqual(wash['verdict'], 'WARN')

    def test_no_stems_says_so(self):
        self.assertEqual(rr.depth(_stereo(_tone(220, 1.0, 0.2)), [], SR)['verdict'], 'N/A')


class TransientTests(unittest.TestCase):
    def test_identical_hits_share_a_shape(self):
        n = int(6.0 * SR)
        x = np.zeros(n, np.float32)
        rng = np.random.default_rng(5)
        hit = rng.standard_normal(int(0.06 * SR)).astype(np.float32) * 0.3
        for i in range(12):
            k = int((0.2 + i * 0.4) * SR)
            x[k:k + len(hit)] += hit
        r = rr.transient_similarity(_stereo(x), SR)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertGreater(r['value'], 0.99)

    def test_varied_hits_do_not(self):
        n = int(6.0 * SR)
        x = np.zeros(n, np.float32)
        rng = np.random.default_rng(6)
        for i in range(12):
            f = 300.0 + 250.0 * i
            t = np.arange(int(0.06 * SR)) / SR
            hit = (np.sin(2 * np.pi * f * t) * np.exp(-t * 60.0) * 0.3).astype(np.float32)
            k = int((0.2 + i * 0.4) * SR)
            x[k:k + len(hit)] += hit
        r = rr.transient_similarity(_stereo(x), SR)
        self.assertLess(r['value'], 0.995)
        self.assertEqual(r['verdict'], 'PASS')


class ScoreTests(unittest.TestCase):
    def _score(self, **extra):
        s = dict(bpm=96, seed=1, tracks=[dict(name='Violins', role='melody',
                                             notes=[dict(t=float(i), d=1.0, p=60 + i % 5, v=0.7) for i in range(24)])],
                 plan=dict(sections=[dict(name='A', start=0, end=12)]))
        s.update(extra)
        return s

    def test_a_section_of_one_player_is_flagged_and_declared_players_pass(self):
        self.assertEqual(rr.ensemble(self._score())['verdict'], 'WARN')
        s = self._score()
        s['tracks'][0]['ensemble'] = dict(players=6)
        self.assertEqual(rr.ensemble(s)['verdict'], 'PASS')

    def test_phrasing_reads_the_elastic_block(self):
        plain = rr.phrasing(self._score())
        self.assertTrue(plain['elastic'] is False)
        el = rr.phrasing(self._score(elastic=dict(amount=0.05, corr_beats=12.0, breaths=[12], breath_s=0.08)))
        self.assertTrue(el['elastic'] is True)
        self.assertGreater(el['value'], 0.0)

    def test_no_score_is_not_measured(self):
        self.assertEqual(rr.ensemble(None)['verdict'], 'N/A')
        self.assertEqual(rr.phrasing(None)['verdict'], 'N/A')


if __name__ == '__main__':
    unittest.main()


class PipelineHook(unittest.TestCase):
    """The realism report runs after a certified render of a cinematic or orchestral cue, as advisory rows."""

    def test_wanted_follows_the_intent_and_the_override(self):
        import realism_report as rr
        self.assertTrue(rr.wanted(dict(intent=dict(registers=['cinematic']))))
        self.assertTrue(rr.wanted(dict(intent=dict(emotions=['tense'], registers=['Orchestral']))))
        self.assertFalse(rr.wanted(dict(intent=dict(registers=['lofi']))))
        self.assertFalse(rr.wanted(dict(intent=dict(registers=['cinematic']), realism=False)))
        self.assertTrue(rr.wanted(dict(realism=True)))
        self.assertFalse(rr.wanted({}))

    def test_rows_are_warn_or_pass_never_fail(self):
        import realism_report as rr
        rows = rr.rows_from({'1_timbre_loudness': dict(value=1.4, verdict='WARN', note='loud and quiet differ mainly in volume'),
                             '4_depth': dict(value=0.0, verdict='PASS', note='detail sits in front of the room'),
                             'source': dict(sr=44100)})
        self.assertEqual([r[0] for r in rows], ['WARN', 'PASS'])
        self.assertEqual(rows[0][1], 'realism.timbre_loudness')
        self.assertIn('differ mainly in volume', rows[0][2])


class PresetAwareChecks(unittest.TestCase):
    """The report reads what the renderer reads: a section's players from its instrument preset, and the score's own air model."""

    def test_players_come_from_the_instrument_preset_too(self):
        from unittest import mock
        score = dict(tracks=[dict(name='celli', instrument='p_celli', notes=[]), dict(name='violas', instrument='p_violas', notes=[])])
        cfgs = {'p_celli': dict(ensemble=dict(players=4)), 'p_violas': dict(ensemble=dict(players=3))}
        with mock.patch('presets.find_instrument', side_effect=lambda n: cfgs.get(n)):
            r = rr.ensemble(score)
        self.assertEqual((r['value'], r['verdict']), (7, 'PASS'))

    def test_a_score_medium_is_the_air_model(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'presets', 'instruments'))
            json.dump(dict(spatial=dict(distance=30.0)), open(os.path.join(td, 'presets', 'instruments', 'far.json'), 'w'))
            self.assertEqual(rr.distance(td)['verdict'], 'WARN')
            r = rr.distance(td, dict(medium=dict(model='iso9613', state=dict(temperature_k=283.15, rh_percent=95))))
            self.assertEqual(r['verdict'], 'PASS')
            self.assertIn('ISO 9613-1', r['note'])


class PartDimensions(unittest.TestCase):
    """Dimensions 9-12 each have a signal that must pass and a signal that must fail: a row that cannot fail is not a row."""
    SR = 44100

    def tone(self, seconds, f0=440.0, cents=0.0, rate=6.0, harmonics=1):
        t = np.arange(int(seconds * self.SR)) / self.SR
        inst = f0 * 2.0 ** ((cents * np.sin(2 * np.pi * rate * t)) / 1200.0)
        phase = 2 * np.pi * np.cumsum(inst) / self.SR
        return sum(np.sin(h * phase) / h for h in range(1, harmonics + 1)) * 0.3

    def test_vibrato_is_found_in_a_moving_tone_and_not_in_a_flat_one(self):
        moving, n1 = rr.vibrato_share(self.tone(6.0, cents=30.0), self.SR)
        flat, n2 = rr.vibrato_share(self.tone(6.0, cents=0.0), self.SR)
        self.assertGreaterEqual(n1, 4)
        self.assertGreaterEqual(moving, 0.8)
        self.assertLessEqual(flat, 0.1)

    def burst(self, seconds, f0, seed=None):
        n = int(seconds * self.SR)
        t = np.arange(n) / self.SR
        rng = np.random.default_rng(seed)
        x = np.sin(2 * np.pi * f0 * t) * np.exp(-t * 18.0)
        if seed is not None:
            x = x + rng.standard_normal(n) * np.exp(-t * 60.0) * 0.4 * rng.random()
        return x

    def stem_of(self, bursts, gap=0.5):
        out = np.zeros(int((len(bursts) + 1) * gap * self.SR))
        for i, b in enumerate(bursts):
            a = int(i * gap * self.SR)
            out[a:a + len(b)] += b[:len(out) - a]
        return np.stack([out, out], axis=1).astype(np.float32)

    def test_identical_attacks_are_flagged_and_varied_ones_are_not(self):
        same = {'violins': self.stem_of([self.burst(0.4, 440.0)] * 12)}
        varied = {'violins': self.stem_of([self.burst(0.4, 440.0, seed=s) for s in range(12)])}
        self.assertEqual(rr.repetition(same)['verdict'], 'WARN')
        self.assertEqual(rr.repetition(varied)['verdict'], 'PASS')

    def line(self, bright):
        """Sixteen notes of one pitch, one second apart (60 bpm: a beat is a second), velocity rising; brightness follows velocity or not."""
        rng = np.random.default_rng(3)
        vels = rng.permutation(np.linspace(0.25, 1.0, 16))
        notes = [dict(t=float(i), d=0.9, p=60, v=float(v)) for i, v in enumerate(vels)]
        out = np.zeros(int(18 * self.SR))
        t = np.arange(int(0.9 * self.SR)) / self.SR
        for i, v in enumerate(vels):
            h = int(1 + 14 * v) if bright else 6
            x = sum(np.sin(2 * np.pi * 261.6 * k * t) / k for k in range(1, h + 1)) * (0.2 if bright else 0.4 * v)
            a = int(i * self.SR)
            out[a:a + len(x)] += x
        score = dict(bpm=60, ts=[4, 4], tracks=[dict(name='violins', role='melody', notes=notes)], _sr=self.SR)
        return {'violins': np.stack([out, out], axis=1).astype(np.float32)}, score

    def test_brightness_that_follows_velocity_passes_and_level_only_fails(self):
        stems, score = self.line(bright=True)
        self.assertEqual(rr.velocity_response(stems, score)['verdict'], 'PASS')
        stems, score = self.line(bright=False)
        r = rr.velocity_response(stems, score)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertIn('violins', r['note'])

    def test_coherence_separates_a_mono_top_from_a_decorrelated_one(self):
        rng = np.random.default_rng(1)
        n = self.SR * 4
        a = rng.standard_normal(n)
        self.assertEqual(rr.coherence(np.stack([a, a], axis=1), self.SR)['verdict'], 'WARN')
        self.assertEqual(rr.coherence(np.stack([a, rng.standard_normal(n)], axis=1), self.SR)['verdict'], 'PASS')

    def test_report_order_and_names_cover_two_digit_keys(self):
        rows = rr.rows_from({'9_vibrato': dict(value=0.1, verdict='WARN', note='x'), '10_repetition': dict(value=0.0, verdict='PASS', note='y'),
                             '2_ensemble': dict(value=3, verdict='PASS', note='z')})
        self.assertEqual([r[1] for r in rows], ['realism.ensemble', 'realism.vibrato', 'realism.repetition'])
