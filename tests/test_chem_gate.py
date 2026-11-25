# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The chem.* gate layer: the kinetics, the feature bus, the presets, the mood/genre targets and the ten rows.

A row that cannot fail is not a row, so every row here is driven with a positive and a negative control (the same
rule as `video_score.py --selftest`). No row may ever return FAIL, and every detail names a measured input.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import chem_model  # noqa: E402
import chem_model.config as config  # noqa: E402
import chem_model.features as features  # noqa: E402
import chem_model.measures as measures  # noqa: E402
import chem_model.pools as pools  # noqa: E402
import chem_model.targets as targets  # noqa: E402
import chem_rows  # noqa: E402
import gate_profiles  # noqa: E402
import intent  # noqa: E402
import lint_coverage  # noqa: E402
import presets  # noqa: E402

BPM = 100.0
SPB = 60.0 / BPM
BARS = 16
HIT_BEAT = 32.0          # bar 9
HIT_S = HIT_BEAT * SPB


def _chord(t, d, pitches, v):
    return [dict(t=float(t), d=float(d), p=int(p), v=float(v)) for p in pitches]


def score_for(kind):
    """A 16-bar piece at 100 BPM whose only differences are the things a chem row judges."""
    tracks = [
        dict(name='pad', role='pad', preset='pad', notes=[]),
        dict(name='lead', role='melody', preset='lead', notes=[]),
        dict(name='bass', role='bass', preset='bass', notes=[]),
        dict(name='kit', role='drum', preset='kit', notes=[]),
    ]
    pad, lead, bass, kit = tracks
    for b in range(BARS):
        v = 0.35 if kind != 'flat' else 0.5
        pad['notes'] += _chord(b * 4, 4.0, (48, 55, 60, 64), v)
    if kind == 'flat':
        return dict(title='flat', bpm=BPM, ts=[4, 4], key='C', mode='major', piece_type='melodic',
                    meta=dict(genre='ambient', emotion='calm'), tracks=[pad])
    # a crescendo: the line gets denser and louder into the hit, which is what a build is
    for b in range(8):
        ramp = b / 7.0
        for k in range(2 if b < 4 else 4):
            t = b * 4 + k * (2.0 if b < 4 else 1.0)
            lead['notes'] += _chord(t, 0.5, (60 + (b + k) % 7,), 0.2 + 0.7 * ramp)
    hit_beats = [HIT_BEAT] if kind != 'double' else [HIT_BEAT, HIT_BEAT + 12.0]
    for hb in hit_beats:
        lead['notes'] += _chord(hb, 3.0, (72, 76), 1.0)
        lead['notes'] += _chord(hb, 3.0, (67,), 0.9)
        bass['notes'] += _chord(hb, 4.0, (36,), 0.95)
        for k in range(8):
            kit['notes'].append(dict(t=hb + k * 0.5, d=0.25, p=36 if k % 2 == 0 else 38, v=0.9))
    if kind == 'resolved':
        for b in range(12, BARS):
            lead['notes'] += _chord(b * 4, 4.0, (48, 55, 60), 0.3)
        bass['notes'] += _chord(48.0, 16.0, (36,), 0.4)
    elif kind == 'cliff':
        for b in range(12, BARS):
            lead['notes'] += _chord(b * 4, 4.0, (60, 61, 66), 0.9)
            for k in range(8):
                kit['notes'].append(dict(t=b * 4 + k * 0.5, d=0.25, p=38, v=0.95))
    return dict(title=kind, bpm=BPM, ts=[4, 4], key='C', mode='major', piece_type='melodic',
                meta=dict(genre='cinematic', emotion='wonder'), tracks=tracks)


def sheet_for(kind, hit=HIT_S):
    sections = [
        dict(name='build', start_s=0.0, end_s=hit, energy=0.4),
        dict(name='hit', start_s=hit, end_s=hit + 10.0, energy=0.9),
        dict(name='tail', start_s=hit + 10.0, end_s=BARS * 4 * SPB, energy=0.5),
    ]
    hits = [] if kind == 'flat' else ([hit, hit + 12.0 * SPB] if kind == 'double' else [hit])
    return dict(duration_s=BARS * 4 * SPB, tempo_bpm=[BPM, BPM], sections=sections, hits_at=hits,
                intent=dict(emotions=['wonder'], registers=[], scenes=[], tensions=[], avoid=[]),
                ending='tail_out')


def evaluate(kind):
    score = score_for(kind)
    gp = gate_profiles.resolve(score)
    return chem_model.evaluate(score, None, sheet_for(kind), None, gp)


class Presets(unittest.TestCase):
    def test_the_three_presets_validate_and_are_registered(self):
        self.assertEqual(config.problems(), [])
        self.assertIn('chem', presets.KINDS)
        self.assertTrue(all(not p.startswith('chem:') for p in presets.validate()))

    def test_an_unknown_key_is_an_error_not_a_default(self):
        import copy
        from unittest import mock
        real = presets.get

        def broken(kind, name):
            p = copy.deepcopy(real(kind, name))
            if kind == 'chem' and name == 'model':
                p['pools']['DA_ant']['tau_rec'] = 8.0          # a misspelling, not a rename
            return p
        with mock.patch.object(config.presets, 'get', side_effect=broken):
            self.assertTrue(any('unknown key' in p for p in config.problems()))

    def test_a_number_without_provenance_is_a_problem(self):
        import copy
        from unittest import mock
        real = presets.get

        def broken(kind, name):
            p = copy.deepcopy(real(kind, name))
            if kind == 'chem' and name == 'model':
                p['pools']['CORT']['why'] = ''
            return p
        with mock.patch.object(config.presets, 'get', side_effect=broken):
            self.assertTrue(any('why' in p for p in config.problems()))

    def test_every_intent_emotion_has_a_target(self):
        for word in intent.vocabulary()['emotions']:
            m = targets.mood_target({'intent': {'emotions': [word]}}, {})
            self.assertTrue(m['known'], word)
            self.assertEqual(set(m['target']), set(config.DIMENSIONS), word)
            for v in m['target'].values():
                self.assertTrue(0.0 <= v <= 1.0, (word, v))

    def test_every_shipped_genre_maps_to_a_family(self):
        import compose
        for genre in compose.GENRES:
            t = targets.genre_target({'meta': {'genre': genre}})
            self.assertNotEqual(t['family'], 'default', genre)

    def test_overrides_beat_the_axes_where_the_axes_are_wrong(self):
        grief = targets.mood_target({'intent': {'emotions': ['grief']}}, {})
        scary = targets.mood_target({'intent': {'emotions': ['scary']}}, {})
        self.assertGreater(grief['target']['affiliation'], 0.6)
        self.assertLess(grief['target']['motor_drive'], 0.3)
        self.assertLess(scary['target']['affiliation'], 0.3)
        self.assertGreater(scary['target']['stress_load'], 0.7)


class Kinetics(unittest.TestCase):
    def setUp(self):
        self.cfg = config.model()
        self.n = 240                        # 60 s at the preset step
        self.step = float(self.cfg['step_s'])

    def test_zero_input_decays_to_zero_and_no_pool_goes_negative(self):
        u = {k: np.zeros(self.n) for k in config.ELICITORS}
        u['build'] = np.ones(self.n) * 0.8        # a build, then silence
        u['build'][60:] = 0.0
        out = pools.simulate(u, self.step, self.cfg)
        for pool in config.POOLS:
            self.assertGreaterEqual(float(out['P'][pool].min()), 0.0, pool)
            self.assertTrue(0.0 <= float(out['A'][pool].min()) and float(out['A'][pool].max()) <= 1.0, pool)
            self.assertLess(float(out['P'][pool][-1]), float(out['P'][pool].max()) + 1e-9, pool)
        self.assertLess(float(out['P']['DA_ant'][-1]), 0.05)

    def test_a_step_peaks_then_decays(self):
        u = {k: np.zeros(self.n) for k in config.ELICITORS}
        u['surprise'] = np.ones(self.n)
        u['surprise'][:20] = 0.0
        p = pools.simulate(u, self.step, self.cfg)['P']['NE']
        i = int(np.argmax(p))
        self.assertGreater(i, 0)
        self.assertLess(i, self.n - 1)
        self.assertGreater(float(p[i]), float(p[-1]))

    def test_a_second_arrival_releases_less(self):
        u = {k: np.zeros(self.n) for k in config.ELICITORS}
        u['arrival'] = np.zeros(self.n)
        for t in (40, 40 + int(40 / self.step)):        # 40 s apart: the availability pool has recovered
            u['arrival'][t:t + int(3.0 / self.step)] = 1.0
        p = pools.simulate(u, self.step, self.cfg)['P']['DA_con']
        first = float(p[40:160].max())
        u2 = {k: np.zeros(self.n) for k in config.ELICITORS}
        u2['arrival'] = np.zeros(self.n)
        for t in (40, 40 + int(6.0 / self.step)):       # 6 s apart: inside the recovery constant
            u2['arrival'][t:t + int(3.0 / self.step)] = 1.0
        p2 = pools.simulate(u2, self.step, self.cfg)['P']['DA_con']
        second = float(p2[40 + int(6.0 / self.step):].max())
        self.assertGreater(first, 0.2)
        self.assertLess(second, first)

    def test_the_step_converges_against_a_finer_one(self):
        u = {k: np.zeros(self.n) for k in config.ELICITORS}
        u['build'] = np.linspace(0.0, 1.0, self.n)
        u['tension'] = np.linspace(1.0, 0.0, self.n)
        diff = pools.convergence(self.step, self.cfg, u, substeps=2)
        for pool, d in diff.items():
            self.assertLess(d, 0.05, pool)


class FeatureBus(unittest.TestCase):
    def test_a_score_alone_measures_the_written_elicitors(self):
        rep = chem_model.evaluate(score_for('build'), None, sheet_for('build'), None,
                                  gate_profiles.resolve(score_for('build')))
        m = rep['features']['measured']
        for key in ('tension', 'uncertainty', 'surprise', 'density', 'consonance', 'legato', 'build', 'proximity'):
            self.assertTrue(m[key], key)
        self.assertFalse(m['pulse'])                 # no audio: the row must say so
        self.assertFalse(m['roughness'])

    def test_the_build_rises_into_the_declared_hit(self):
        rep = chem_model.evaluate(score_for('build'), None, sheet_for('build'), None,
                                  gate_profiles.resolve(score_for('build')))
        prox = rep['features']['u']['proximity']
        hit = int(HIT_S / rep['step_s'])
        self.assertGreater(float(prox[hit - 1]), 0.5)
        self.assertLess(float(prox[0]), 0.2)
        self.assertGreater(float(rep['features']['u']['build'][hit - 2]), 0.3)

    def test_a_missing_sheet_hit_and_a_missing_mood_are_said_not_guessed(self):
        score = score_for('build')
        score['meta'].pop('emotion')
        rep = chem_model.evaluate(score, None, {'sections': []}, None, gate_profiles.resolve(score))
        self.assertFalse(rep['features']['measured']['proximity'])
        self.assertFalse(rep['mood']['known'])
        self.assertIn('no mood word', rep['mood']['why'])


class Ordering(unittest.TestCase):
    """The controls: a build beats a flat piece, a resolved ending beats a cliff, a repeat releases less."""

    def test_a_build_outranks_a_flat_piece(self):
        good, flat = evaluate('build'), evaluate('flat')
        self.assertGreater(good['dims']['reward_build'], flat['dims']['reward_build'] + 0.1)
        self.assertGreater(good['dims']['reward_arrival'], flat['dims']['reward_arrival'] + 0.1)

    def test_a_resolved_ending_outranks_a_cliff(self):
        resolved, cliff = evaluate('resolved'), evaluate('cliff')
        self.assertGreater(resolved['dims']['recovery'], cliff['dims']['recovery'])

    def test_a_flat_piece_is_one_state(self):
        flat, good = evaluate('flat'), evaluate('build')
        self.assertLess(flat['observables']['variety']['states'], good['observables']['variety']['states'])

    def test_a_repeated_arrival_is_spent(self):
        twice = evaluate('double')
        arrivals = [a['at_s'] for a in twice['observables']['arrivals']]
        self.assertEqual(len(arrivals), 2)
        con = twice['pools']['P']['DA_con']
        step = twice['step_s']
        first = float(con[int(arrivals[0] / step):int(arrivals[1] / step)].max())
        second = float(con[int(arrivals[1] / step):].max())
        self.assertLess(second, first)


class Rows(unittest.TestCase):
    def rows(self, kind):
        rep = evaluate(kind)
        gp = gate_profiles.resolve(score_for(kind))
        return {r[1]: r for r in chem_rows.report_rows(rep, gp, config.problems())}

    def test_every_row_is_registered_covered_and_never_fails(self):
        for rid in chem_rows.ROW_IDS:
            self.assertIn(rid, gate_profiles.ROWS, rid)
            self.assertIn(rid, lint_coverage.COVERAGE, rid)
            self.assertFalse(gate_profiles.ROWS[rid].get('protected'), rid)
        for kind in ('build', 'flat', 'resolved', 'cliff', 'double'):
            got = self.rows(kind)
            self.assertTrue(got, kind)
            self.assertTrue(all(r[0] in ('INFO', 'WARN') for r in got.values()), kind)

    def test_the_flat_piece_warns_on_the_build_and_the_built_one_does_not(self):
        flat, built = self.rows('flat'), self.rows('build')
        self.assertEqual(flat['chem.reward_build'][0], 'WARN')
        self.assertEqual(built['chem.reward_build'][0], 'INFO')
        self.assertIn('Lever', flat['chem.reward_build'][2])

    def test_the_cliff_warns_on_recovery_and_the_resolved_piece_does_not(self):
        self.assertEqual(self.rows('cliff')['chem.recovery'][0], 'WARN')
        self.assertEqual(self.rows('resolved')['chem.recovery'][0], 'INFO')

    def test_the_double_drop_warns_on_arrival_density(self):
        got = self.rows('double')
        self.assertEqual(got['chem.arc_variety'][0], 'WARN')
        self.assertIn('arrivals per minute', got['chem.arc_variety'][2])

    def test_every_detail_names_its_tier_and_the_inputs_it_measured(self):
        got = self.rows('build')
        for rid in ('chem.reward_build', 'chem.reward_arrival', 'chem.stress_load', 'chem.affiliation',
                    'chem.motor_drive', 'chem.recovery'):
            self.assertIn('Tier', got[rid][2], rid)
            self.assertIn('inputs:', got[rid][2], rid)
        self.assertIn('not measured', got['chem.motor_drive'][2])

    def test_a_mood_and_a_genre_resolve_into_the_connection_rows(self):
        got = self.rows('build')
        self.assertIn('wonder', got['chem.mood_connection'][2])
        self.assertIn('cinematic', got['chem.genre_connection'][2])

    def test_the_mood_row_warns_when_the_signature_is_far_and_says_which_dimension(self):
        rep = evaluate('build')
        rep['dims'] = {d: 0.05 for d in config.DIMENSIONS}
        got = {r[1]: r for r in chem_rows.report_rows(rep, gate_profiles.resolve(score_for('build')),
                                                      config.problems())}
        self.assertEqual(got['chem.mood_connection'][0], 'WARN')
        self.assertIn('Furthest:', got['chem.mood_connection'][2])
        self.assertIn('Lever:', got['chem.mood_connection'][2])

    def test_the_genre_row_warns_when_a_family_constraint_is_missed(self):
        score = score_for('flat')
        score['meta']['genre'] = 'house'                     # a dance genre needs a body-locking pulse
        score['tracks'][0]['notes'] = [n for b in range(BARS)
                                       for n in _chord(b * 4, 4.0, (72, 76, 79), 0.35)]   # no low end, no kick
        gp = gate_profiles.resolve(score)
        rep = chem_model.evaluate(score, None, sheet_for('flat'), None, gp)
        got = {r[1]: r for r in chem_rows.report_rows(rep, gp, config.problems())}
        self.assertEqual(got['chem.genre_connection'][0], 'WARN')
        self.assertIn('motor_drive', got['chem.genre_connection'][2])

    def test_a_broken_preset_reports_instead_of_crashing(self):
        rep = evaluate('build')
        got = {r[1]: r for r in chem_rows.report_rows(rep, gate_profiles.resolve(score_for('build')),
                                                      ['chem/model.pools.DA_ant has unknown key'])}
        self.assertEqual(got['chem.model'][0], 'WARN')
        self.assertTrue(all('not measured' in got[r][2] for r in chem_rows.ROW_IDS if r != 'chem.model'))


class Stress(unittest.TestCase):
    def test_a_carried_load_is_unresolved_and_a_released_one_is_not(self):
        cfg = config.model()
        times = np.arange(60) * 1.0
        held = np.ones(60) * 0.6
        released = np.concatenate([np.ones(20) * 0.8, np.zeros(40)])
        bad = measures.stress(held, times, cfg)
        good = measures.stress(released, times, cfg)
        self.assertGreater(bad['unresolved_s'], good['unresolved_s'])
        self.assertLess(bad['resolve_frac'], good['resolve_frac'])
        self.assertGreater(good['resolve_frac'], 0.5)


if __name__ == '__main__':
    unittest.main()
