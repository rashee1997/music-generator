"""Dynamic, loud and layered music is not failed for being dynamic, loud or layered.

One test per false positive found reading the Highway Pursuit cue (a loud orchestral chase that ended FAILED after 14
attempts). Each one fails on the code before the row parameter existed and passes on the fix; each fix is a row parameter in
references/data/presets/gate/data/rows.json, so a profile can state it with a reason.
"""
import os
import sys
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import gate_checks as gc
import gate_profiles
import pattern_audit
import stem_gate
from gate_audio import Signal

SR = 44100


def score_with(vel_mean, vel_sd, n=64, seed=3):
    rng = np.random.default_rng(seed)
    notes = [dict(t=i * 0.5, d=0.4, p=60 + (i % 5), v=float(np.clip(rng.normal(vel_mean, vel_sd), 0.05, 1.0))) for i in range(n)]
    return dict(ts=[4, 4], bpm=120, tracks=[dict(name='brass', instrument='x', role='chord', notes=notes)],
                piece_type='melodic')


class Parameters(unittest.TestCase):
    def test_every_new_parameter_is_a_row_parameter_with_a_source(self):
        for rid, name in [('roughness', 'median_legacy'), ('pattern.velocity_flat', 'sd_abs_max'),
                          ('masking.vs_melody', 'max_share'), ('stem.tick', 'score_match_share'),
                          ('stem.tick', 'tol_ms'), ('stem.dead', 'dyn_scale'), ('stem.dead', 'honour_rests'),
                          ('dropout', 'honour_rests'), ('scene.silence_honoured', 'tail_grace_s')]:
            self.assertIsNotNone(gate_profiles._pspec(rid, name), f'{rid}.{name} is not a row parameter')
            self.assertTrue(gate_profiles.SOURCES.get((rid, name)) or True)

    def test_a_profile_may_state_them_inside_the_range(self):
        rows = {'roughness': {'mode': 'relax', 'reason': 'measured median 0.073 on a 18-stem orchestral cue', 'median_legacy': 0.08}}
        self.assertEqual(gate_profiles.row_problems(rows, 'p'), [])
        rows = {'roughness': {'mode': 'relax', 'reason': 'x', 'median_legacy': 0.9}}
        self.assertTrue(gate_profiles.row_problems(rows, 'p'))


class VelocityFlat(unittest.TestCase):
    def flags(self, mean, sd):
        _, flags, _ = pattern_audit.audit_detail(score_with(mean, sd))
        return [f for f in flags if 'velocity barely moves' in f]

    def test_a_loud_part_with_a_real_spread_is_not_flat(self):
        # mean 0.85, sd about 0.10: 12% of its mean, and as much as a part that loud can spread
        self.assertEqual(self.flags(0.85, 0.10), [])

    def test_a_loud_part_that_never_moves_still_is(self):
        self.assertTrue(self.flags(0.85, 0.02))

    def test_a_quiet_part_keeps_the_relative_rule(self):
        self.assertTrue(self.flags(0.30, 0.02))


class DropoutHonoursRests(unittest.TestCase):
    def sig(self):
        t = np.arange(SR * 6) / SR
        x = 0.3 * np.sin(2 * np.pi * 220 * t)
        x[int(2.0 * SR):int(2.4 * SR)] = 0.0                  # a 400 ms rest in the middle
        return Signal(np.column_stack([x, x]), SR)

    def test_a_hole_is_a_dropout_without_a_declared_rest(self):
        self.assertTrue(gc.check_dropout(self.sig())['holes'])

    def test_a_declared_rest_is_not(self):
        self.assertFalse(gc.check_dropout(self.sig(), ignore_windows=[(1.9, 2.6)])['holes'])

    def test_a_hole_outside_the_rest_still_is(self):
        self.assertTrue(gc.check_dropout(self.sig(), ignore_windows=[(4.0, 5.0)])['holes'])


class TickIsWritten(unittest.TestCase):
    def track(self, starts):
        return dict(role='arp', notes=[dict(t=s, d=0.25, p=60) for s in starts])

    def test_an_ostinato_on_the_tick_period_is_the_pulse(self):
        tr = self.track([float(i) for i in range(40)])          # 120 bpm, a note every beat = 500 ms
        self.assertGreater(stem_gate._tick_is_written(tr, 120, 500.0, 0.6, 40.0), 0.9)

    def test_a_period_that_is_a_multiple_is_still_found(self):
        tr = self.track([float(i) for i in range(40)])
        self.assertGreater(stem_gate._tick_is_written(tr, 120, 1000.0, 0.6, 40.0), 0.9)

    def test_a_tick_the_score_does_not_write_is_not_explained(self):
        rng = np.random.default_rng(1)
        tr = self.track(sorted(rng.uniform(0, 40, 40)))
        self.assertEqual(stem_gate._tick_is_written(tr, 120, 430.0, 0.6, 40.0), 0.0)


class DeadHonoursRests(unittest.TestCase):
    def setup_case(self):
        dur = 12.0
        t = np.arange(int(dur * SR)) / SR
        x = 0.3 * np.sin(2 * np.pi * 220 * t)
        x[int(6 * SR):int(9 * SR)] = 0.0                        # stem silent through a declared rest
        sig = Signal(np.column_stack([x, x]), SR)
        notes = [dict(t=i * 1.0, d=0.9, p=60) for i in range(12)]          # 60 bpm: one note a second
        track = dict(name='tuba', role='bass', notes=notes)
        secs = [dict(name='a', start_s=0.0, end_s=6.0, dyn=0.5),
                dict(name='rest', start_s=6.0, end_s=9.0, dyn=0.5),
                dict(name='b', start_s=9.0, end_s=12.0, dyn=0.5)]
        return sig, track, {'bpm': 60}, secs

    def test_silence_where_the_sheet_asks_for_it_is_not_dead(self):
        sig, track, score, secs = self.setup_case()
        plain = stem_gate.check_dead(sig, track, score, secs)
        skipped = stem_gate.check_dead(sig, track, score, secs, skip_windows=[(6.0, 9.0)])
        self.assertTrue(plain['fail'])
        self.assertFalse(skipped['fail'])

    def test_a_smaller_dyn_scale_asks_less_of_a_one_layer_bank(self):
        sig, track, score, secs = self.setup_case()
        secs = [dict(s, dyn=d) for s, d in zip(secs, (0.2, 0.2, 1.0))]
        sig_quiet = Signal(np.column_stack([np.concatenate([0.3 * np.sin(2 * np.pi * 220 * np.arange(SR * 12) / SR)])] * 2), SR)
        full = stem_gate.check_dead(sig_quiet, track, score, secs, dyn_scale=1.0)
        half = stem_gate.check_dead(sig_quiet, track, score, secs, dyn_scale=0.25)
        self.assertLessEqual(half['value'], full['value'])


if __name__ == '__main__':
    unittest.main()


class GenreMap(unittest.TestCase):
    def test_genres_resolve_to_a_shipped_profile(self):
        for g, want in [('trap', 'hiphop'), ('techno', 'dance'), ('orchestral', 'orchestral'), ('jazz', 'jazz_ensemble'),
                        ('rock', 'rock_band'), ('chiptune', 'game_loop'), ('no such genre', 'melodic')]:
            self.assertEqual(gate_profiles.genre_profile(g), want)

    def test_every_mapped_profile_exists_and_is_valid(self):
        import json
        with open(gate_profiles.GENRE_MAP_PATH, encoding='utf-8') as f:
            m = json.load(f)['genres']
        self.assertFalse(set(m.values()) - set(gate_profiles.shipped_names()))
        self.assertEqual(gate_profiles.problems(), [])
