"""M6: the ecology. The score's occupancy, niche overlap (Schoener), freeze and answer rules, pocket-aware and budgeted
scheduling, and the hand-over of the score to an environment track. Synthetic scores and synthetic animals only."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import environment  # noqa: E402
import presets  # noqa: E402
from biome import context, ecology, ecology_schema, engine, fauna, schema  # noqa: E402
from phys_core import medium  # noqa: E402

SR = 44100
AIR = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.02897, gamma=1.4, viscosity_pa_s=1.81e-5, prandtl=0.71), 'state': {'temperature_k': 293.15}}


def ctx(seed=1, controls=None):
    return context.Context(sr=SR, medium=medium.Medium(AIR), seed=seed, controls=controls)


def animal(name, band, rate=12.0, ms=(400, 500), salience='bed', **over):
    lo, hi = band
    f0 = (lo * hi) ** 0.5
    d = dict(name=name, power_w=1e-4, bouts_per_min=rate, first_s=0.3, salience=salience, niche={'band_hz': [lo, hi]},
             source=dict(kind='dual_syrinx', saturation=0.0, harmonics=1), elements=dict(c={'f_left': f0, 'ms': list(ms)}))
    d.update(over)
    return d


def preset(fauna_list, ecology=None, controls=None):
    p = {'schema': 'biome/1', 'name': 'eco_test', 'character': 'a test place for the ecology', 'medium': AIR, 'fauna': fauna_list,
         'generators': [dict(name='wind', kind='turbulence', obstacles=dict(d_m=dict(dist='fixed', value=0.005), frontal_area_m2=2.0, oscillators=1),
                             flow=dict(u_m_s=2.0, intensity=0.1), spatial=dict(field=True))]}
    if ecology is not None:
        p['ecology'] = ecology
    if controls is not None:
        p['controls'] = controls
    return p


def score(notes_by_track=None, bpm=120.0, sections=None, hits=None, span_beats=200):
    # `humanize: tight` and a note that spans the piece: the tempo map is exact where the sections are, not extrapolated
    tracks = [dict(name='clock', role='fx', instrument='sfx:tick', notes=[dict(t=span_beats - 1, d=1, p=60, v=1)])]
    for name, role, notes in (notes_by_track or []):
        tracks.append(dict(name=name, role=role, instrument='piano', notes=[dict(zip(('t', 'd', 'p', 'v'), n)) for n in notes]))
    plan = {}
    if sections:
        plan['sections'] = sections
    if hits:
        plan['hits'] = hits
    return dict(bpm=bpm, ts=[4, 4], tracks=tracks, plan=plan, seed=1, humanize='tight')


def make(fauna_cfgs, eco=None, sc=None, controls=None, seed=3, t0=0.0):
    return engine.Biome(preset(fauna_cfgs, eco, controls), seed=seed, score=sc, t0_s=t0)


class Occupancy(unittest.TestCase):
    def test_a_lead_note_occupies_its_band_and_harmonics_while_it_sounds(self):
        sc = score([('lead', 'melody', [(0, 4, 69, 100)])])               # A4 = 440 Hz for 2 s at 120 bpm
        occ = ecology.Occupancy.from_score(sc)
        self.assertGreater(occ.level(0.2, 1.8, 400, 480), 0.4)
        self.assertGreater(occ.level(0.2, 1.8, 850, 920), 0.1)            # the second harmonic
        self.assertEqual(occ.level(2.6, 4.0, 400, 480), 0.0)              # after the note
        self.assertLess(occ.level(0.2, 1.8, 100, 140), 0.01)
        self.assertGreater(occ.level(0.2, 1.8, 400, 480, protected_only=True), 0.4)

    def test_only_a_figure_role_is_protected(self):
        sc = score([('pad', 'pad', [(0, 4, 69, 100)])])
        occ = ecology.Occupancy.from_score(sc)
        self.assertGreater(occ.level(0.2, 1.8, 400, 480), 0.2)
        self.assertEqual(occ.level(0.2, 1.8, 400, 480, protected_only=True), 0.0)

    def test_velocity_scales_the_weight(self):
        loud = ecology.Occupancy.from_score(score([('l', 'melody', [(0, 4, 69, 120)])])).level(0.2, 1.8, 400, 480)
        soft = ecology.Occupancy.from_score(score([('l', 'melody', [(0, 4, 69, 20)])])).level(0.2, 1.8, 400, 480)
        self.assertGreater(loud, soft)

    def test_drums_fill_every_band_briefly_and_environment_tracks_are_ignored(self):
        sc = score([('kit', 'drum', [(0, 0.25, 36, 100)]), ('bed', 'environment', [(0, 8, 60, 100)])])
        occ = ecology.Occupancy.from_score(sc)
        self.assertGreater(occ.level(0.0, 0.3, 80, 8000), 0.2)
        self.assertEqual(occ.level(1.0, 3.0, 80, 8000), 0.0)

    def test_the_margin_widens_the_protected_band(self):
        sc = score([('l', 'melody', [(0, 4, 69, 100)])])
        near = lambda occ: occ.level(0.2, 1.8, 560, 640)                      # noqa: E731  two bands above A4
        self.assertGreater(near(ecology.Occupancy.from_score(sc, margin_db=6.0)), near(ecology.Occupancy.from_score(sc, margin_db=0.0)))

    def test_an_unknown_role_is_an_error_not_a_guess(self):
        with self.assertRaises(Exception):
            ecology.Occupancy.from_score(score([('x', 'wizard', [(0, 1, 60, 80)])]))

    def test_velocities_in_0_1_work_too(self):
        occ = ecology.Occupancy.from_score(score([('l', 'melody', [(0, 4, 69, 0.8)])]))
        self.assertGreater(occ.level(0.2, 1.8, 400, 480), 0.4)


class Sections(unittest.TestCase):
    def test_bars_become_seconds_through_the_tempo(self):
        sc = score(sections=[dict(name='intro', start_bar=0, end_bar=4), dict(name='drop', start_bar=8, end_bar=16)], bpm=120.0)
        secs, _ = ecology.section_times(sc)
        self.assertAlmostEqual(secs['drop'][0][0], 16.0, delta=0.5)         # 8 bars of 2 s (rubato-free to within a moment)
        self.assertAlmostEqual(secs['intro'][0][1], 8.0, delta=0.3)

    def test_a_direction_sheet_adds_sections_and_hits(self):
        secs, hits = ecology.section_times(score(), {'sections': [dict(name='crest', start_s=32.0, end_s=50.0)], 'hits': [{'t': 24.0}, {'t': 38.0}]})
        self.assertEqual(secs['crest'], [(32.0, 50.0)])
        self.assertEqual(hits, [24.0, 38.0])


class Niches(unittest.TestCase):
    def test_shares_sum_to_one_and_overlap_follows_the_band(self):
        a, b = ecology.band_shares(1000, 2000), ecology.band_shares(1000, 2000)
        self.assertAlmostEqual(float(a.sum()), 1.0, places=9)
        self.assertAlmostEqual(ecology.schoener(a, b), 1.0, places=9)
        self.assertAlmostEqual(ecology.schoener(a, ecology.band_shares(5000, 9000)), 0.0, places=9)
        mid = ecology.schoener(a, ecology.band_shares(1400, 2800))
        self.assertTrue(0.2 < mid < 0.9)

    def test_the_declared_band_matches_the_measured_spectrum(self):
        x = np.random.default_rng(1).standard_normal(SR * 4)
        from scipy import signal
        y = signal.sosfiltfilt(signal.butter(6, [1000, 2000], 'band', fs=SR, output='sos'), x)
        self.assertGreater(ecology.schoener(ecology.spectrum_shares(y, SR), ecology.band_shares(1000, 2000)), 0.8)

    def test_collisions_weigh_the_overlap_by_the_time_of_day(self):
        ctl = context.Controls({'dawn': {'curve': [[0, 1], [100, 1], [101, 0], [600, 0]]}, 'dusk': {'curve': [[0, 0], [300, 0], [301, 1], [600, 1]]}})
        a = animal('a', (1000, 2000), niche={'band_hz': [1000, 2000], 'active': {'control': 'dawn'}})
        b = animal('b', (1000, 2000), niche={'band_hz': [1000, 2000], 'active': {'control': 'dusk'}})
        c = animal('c', (1000, 2000))
        rows = {(x, y): (d, co) for x, y, d, co in ecology.collisions([a, b, c], ctl, 600.0)}
        self.assertAlmostEqual(rows[('a', 'b')][0], 1.0, places=9)
        self.assertLess(rows[('a', 'b')][1], 0.1)                          # same band, but never at the same time
        self.assertGreater(rows[('a', 'c')][1], 0.9)

    def test_an_animal_without_a_niche_has_no_collisions(self):
        self.assertEqual(ecology.collisions([dict(name='a'), dict(name='b')]), [])


class Rules(unittest.TestCase):
    ECO = {'rules': [{'on': {'fauna': 'tiger'}, 'do': {'freeze': ['thrush'], 'for_s': [8, 8], 'fade_ms': 300, 'ramp_s': 2}}]}

    def cfgs(self):
        return [animal('tiger', (80, 400), rate=3.0, ms=(900, 1000), first_s=5.0, salience='foreground'),
                animal('thrush', (2000, 4000), rate=40.0, first_s=0.3)]

    def test_no_bout_of_a_frozen_animal_begins_in_its_window(self):
        b = make(self.cfgs(), self.ECO)
        b.render(60.0)
        rep = b.ecology_report()
        self.assertTrue(rep['windows']['thrush'])
        for t0, t1, _, _ in rep['windows']['thrush']:
            starts = [s for s, _ in rep['bouts']['thrush/0'] if t0 <= s < t1]
            self.assertEqual(starts, [], (t0, t1))
        self.assertGreater(len(rep['bouts']['thrush/0']), 10)               # it does call when it is not frozen

    def test_the_freeze_begins_when_the_trigger_calls(self):
        b = make(self.cfgs(), self.ECO)
        b.render(40.0)
        rep = b.ecology_report()
        trig = [s for s, _ in rep['bouts']['tiger/0']]
        self.assertAlmostEqual(trig[0], 5.0, places=6)
        starts = sorted(w[0] for w in rep['windows']['thrush'])
        for s, w in zip(trig, starts):
            self.assertAlmostEqual(s, w, places=6)

    def test_a_call_already_sounding_fades_out_and_comes_back(self):
        cfg = animal('thrush', (2000, 4000), rate=600.0, ms=(8000, 8000))
        plain = fauna.build(cfg, ctx()).render(7.0).astype(np.float64)
        f = fauna.build(cfg, ctx())
        f.add_silence(2.0, 4.0, 0.3, 1.0)
        y = f.render(7.0).astype(np.float64)
        r = lambda x, a, b: float(np.sqrt(np.mean(x[int(a * SR):int(b * SR)] ** 2)))             # noqa: E731
        self.assertTrue(np.array_equal(y[:int(2.0 * SR)], plain[:int(2.0 * SR)]))                # untouched before the window
        self.assertGreater(r(plain, 2.4, 3.9), 0.0)
        self.assertLess(r(y, 2.4, 3.9), 1e-9 * r(plain, 2.4, 3.9))                               # silent inside it
        self.assertAlmostEqual(r(y, 5.5, 6.9) / r(plain, 5.5, 6.9), 1.0, delta=0.02)             # and back at full level after the ramp
        fade = r(y, 2.0, 2.3) / r(plain, 2.0, 2.3)
        self.assertTrue(0.1 < fade < 0.8, fade)                                                  # a fade, not a cut
        self.assertLess(float(np.abs(np.diff(y)).max()), 1.5 * float(np.abs(np.diff(plain)).max()))   # and not a click

    def test_an_answer_follows_its_trigger(self):
        eco = {'rules': [{'on': {'fauna': 'tiger'}, 'do': {'answer': 'echo', 'after_ms': [500, 500], 'p': 1.0}}]}
        cfgs = [animal('tiger', (80, 400), rate=3.0, ms=(900, 1000), first_s=5.0), animal('echo', (2000, 4000), rate=0.05, first_s=500.0)]
        b = make(cfgs, eco)
        b.render(30.0)
        rep = b.ecology_report()
        trig = rep['bouts']['tiger/0']
        ans = rep['bouts']['echo/0']
        self.assertGreaterEqual(len(ans), 1)
        self.assertAlmostEqual(ans[0][0], trig[0][0] + trig[0][1] + 0.5, places=6)

    def test_a_score_section_can_trigger_a_freeze(self):
        sc = score(sections=[dict(name='intro', start_bar=0, end_bar=4), dict(name='drop', start_bar=8, end_bar=16)], bpm=120.0)
        eco = {'rules': [{'on': {'score': 'drop'}, 'do': {'freeze': ['thrush'], 'for_s': [6, 6], 'fade_ms': 200}}]}
        b = make([animal('thrush', (2000, 4000), rate=40.0)], eco, sc)
        b.render(40.0)
        (t0, t1, _, _), = b.ecology_report()['windows']['thrush']
        self.assertAlmostEqual(t0, 16.0, delta=0.5)
        self.assertAlmostEqual(t1 - t0, 6.0, places=6)
        self.assertEqual([s for s, _ in b.ecology_report()['bouts']['thrush/0'] if t0 <= s < t1], [])

    def test_a_score_trigger_is_shifted_by_where_the_bed_starts_in_the_piece(self):
        sc = score(sections=[dict(name='drop', start_bar=8, end_bar=16)], bpm=120.0)
        eco = {'rules': [{'on': {'score': 'drop'}, 'do': {'freeze': ['thrush'], 'for_s': [4, 4]}}]}
        b = make([animal('thrush', (2000, 4000))], eco, sc, t0=10.0)
        b.render(20.0)
        self.assertAlmostEqual(b.ecology_report()['windows']['thrush'][0][0], 6.0, delta=0.5)        # 16 s in the piece, 10 s in

    def test_an_unknown_section_names_the_ones_there_are(self):
        sc = score(sections=[dict(name='intro', start_bar=0, end_bar=4)])
        with self.assertRaises(ValueError) as cm:
            make([animal('thrush', (2000, 4000))], {'rules': [{'on': {'score': 'drop'}, 'do': {'freeze': ['thrush']}}]}, sc)
        self.assertIn('intro', str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            make([animal('thrush', (2000, 4000))], {'rules': [{'on': {'score': 'drop'}, 'do': {'freeze': ['thrush']}}]})
        self.assertIn('score', str(cm.exception))

    def test_a_hit_triggers_too(self):
        sc = score(hits=[{'t': 12.0}, {'t': 30.0}])
        b = make([animal('thrush', (2000, 4000))], {'rules': [{'on': {'score': 'hit'}, 'do': {'freeze': ['thrush'], 'for_s': [3, 3]}}]}, sc)
        b.render(40.0)
        self.assertEqual([round(w[0]) for w in b.ecology_report()['windows']['thrush']], [12, 30])


class Scheduling(unittest.TestCase):
    def test_animals_in_the_same_band_do_not_call_over_each_other(self):
        a, c = animal('a', (1000, 2000), rate=40.0), animal('b', (1000, 2000), rate=40.0, first_s=0.35)
        b = make([a, c], {'niches': {'auto': True, 'min_separation': 'D<=0.4'}})
        b.render(60.0)
        rep = b.ecology_report()
        self.assertEqual(rep['conflicts'], [['a', 'b']])
        ev = sorted([(s, s + d, 'a') for s, d in rep['bouts']['a/0']] + [(s, s + d, 'b') for s, d in rep['bouts']['b/0']])
        overlaps = [(x, y) for x, y in zip(ev, ev[1:]) if y[0] < x[1] and x[2] != y[2]]
        self.assertEqual(overlaps, [])

    def test_without_the_niche_rule_they_do_overlap(self):
        a, c = animal('a', (1000, 2000), rate=40.0), animal('b', (1000, 2000), rate=40.0, first_s=0.35)
        b = make([a, c], {})
        b.render(60.0)
        rep = b.ecology_report()
        ev = sorted([(s, s + d, 'a') for s, d in rep['bouts']['a/0']] + [(s, s + d, 'b') for s, d in rep['bouts']['b/0']])
        self.assertTrue([1 for x, y in zip(ev, ev[1:]) if y[0] < x[1] and x[2] != y[2]])

    def test_a_foreground_call_waits_for_a_pocket(self):
        sc = score([('lead', 'melody', [(k * 2, 1.9, 69, 110) for k in range(0, 30)])])          # A4 held from 0 to 30 s
        cfg = animal('bird', (400, 480), rate=20.0, salience='foreground', first_s=1.0)
        eco = {'score': {'pocket_threshold': 0.35, 'p_force': 0.0}}
        with_score = make([cfg], eco, sc)
        with_score.render(60.0)
        starts = [s for s, _ in with_score.ecology_report()['bouts']['bird/0']]
        self.assertEqual([s for s in starts if s < 29.0], [])
        self.assertTrue([s for s in starts if s > 31.0])
        free = make([cfg], eco)
        free.render(60.0)
        self.assertTrue([s for s, _ in free.ecology_report()['bouts']['bird/0'] if s < 29.0])

    def test_a_call_that_finds_no_pocket_is_dropped_and_recorded(self):
        sc = score([('lead', 'melody', [(k * 2, 1.9, 69, 110) for k in range(0, 60)])])
        b = make([animal('bird', (400, 480), rate=20.0, salience='foreground')], {'score': {'p_force': 0.0, 'max_tries': 2}}, sc)
        b.render(30.0)
        self.assertTrue(b.ecology_report()['dropped'])
        self.assertEqual(b.ecology_report()['bouts']['bird/0'], [])

    def test_a_bed_animal_is_only_kept_out_of_dense_passages(self):
        sc = score([('lead', 'melody', [(k * 2, 1.9, 69, 110) for k in range(0, 30)])])
        b = make([animal('frogs', (400, 480), rate=20.0, salience='bed')], {'score': {'bed_threshold': 0.99}}, sc)
        b.render(20.0)
        self.assertTrue([s for s, _ in b.ecology_report()['bouts']['frogs/0'] if s < 20.0])

    def test_the_density_budget_caps_the_calls_per_second(self):
        b = make([animal('a', (500, 900), rate=300.0, ms=(50, 60)), animal('b', (3000, 5000), rate=300.0, ms=(50, 60))],
                 {'density_budget': {'events_per_s_max': 0.3}})
        b.render(60.0)
        rep = b.ecology_report()
        starts = sorted(s for k, v in rep['bouts'].items() for s, _ in v)
        for i, s in enumerate(starts):
            window = [x for x in starts if s - 10.0 < x <= s]
            self.assertLessEqual(len(window) / 10.0, 0.3 + 1e-9)
        self.assertGreater(len(starts), 10)

    def test_the_time_of_day_gates_the_calling(self):
        ctl = {'dawn': {'curve': [[0, 0], [29.9, 0], [30.0, 1], [100, 1]]}}
        cfg = animal('lark', (2000, 4000), rate=20.0, niche={'band_hz': [2000, 4000], 'active': {'control': 'dawn'}})
        b = make([cfg], {}, controls=ctl)
        b.render(60.0)
        starts = [s for s, _ in b.ecology_report()['bouts']['lark/0']]
        self.assertEqual([s for s in starts if s < 29.0], [])
        self.assertGreater(len([s for s in starts if s > 30.0]), 3)

    def test_the_plan_does_not_depend_on_how_far_ahead_it_was_made(self):
        cfgs = [animal('a', (1000, 2000), rate=20.0), animal('b', (1000, 2000), rate=20.0, first_s=0.35)]
        one = make(cfgs, {'niches': {'auto': True}}).planner
        one.plan_until(60.0)
        two = make(cfgs, {'niches': {'auto': True}}).planner
        for t in (7.0, 19.0, 33.3, 60.0):
            two.plan_until(t)
        self.assertEqual(one.plan, two.plan)

    def test_the_plan_is_in_time_order_and_an_animal_never_overlaps_itself(self):
        b = make([animal('a', (1000, 2000), rate=60.0)], {})
        b.render(60.0)
        starts = b.ecology_report()['bouts']['a/0']
        self.assertEqual(starts, sorted(starts))
        self.assertTrue(all(y[0] >= x[0] + x[1] for x, y in zip(starts, starts[1:])))

    def test_the_animals_read_the_plan(self):
        b = make([animal('a', (1000, 2000), rate=30.0)], {})
        b.render(30.0)
        plan = b.planner.plan[('a', 0)]
        started = [(round(t, 6), round(d, 6)) for _, t, d in b.fauna[0].starts]
        self.assertEqual(started, [(round(t, 6), round(d, 6)) for t, d in plan[:len(started)]])
        self.assertGreater(len(started), 5)


class Integration(unittest.TestCase):
    def test_a_preset_without_an_ecology_is_scheduled_as_before(self):
        b = make([animal('a', (1000, 2000), rate=30.0)], None)
        self.assertIsNone(b.planner)
        self.assertEqual(b.ecology_report(), {})
        b.render(10.0)
        self.assertTrue(b.fauna[0].starts)

    def test_the_render_with_an_ecology_does_not_depend_on_the_chunk_size(self):
        sc = score([('lead', 'melody', [(k * 2, 1.9, 69, 110) for k in range(0, 10)])])
        eco = {'niches': {'auto': True}, 'rules': [{'on': {'fauna': 'a'}, 'do': {'freeze': ['b'], 'for_s': [2, 2], 'fade_ms': 100}}]}
        cfgs = [animal('a', (1000, 2000), rate=30.0), animal('b', (1000, 2000), rate=30.0, first_s=0.35)]
        x = make(cfgs, eco, sc).render(12.0, chunk_s=5.0)
        y = make(cfgs, eco, sc).render(12.0, chunk_s=0.9)
        self.assertLess(float(np.abs(x - y).max()), 1e-5 * float(np.abs(x).max()))

    def test_a_scheduler_and_an_ecology_together_are_refused(self):
        class S:
            def next_start(self, *a):
                return None
        with self.assertRaises(ValueError):
            engine.Biome(preset([animal('a', (1000, 2000))], {}), scheduler=S())

    def test_environment_passes_the_score_and_the_offset_through(self):
        sc = score([('lead', 'melody', [(k * 2, 1.9, 69, 110) for k in range(0, 30)])])
        p = preset([animal('bird', (400, 480), rate=20.0, salience='foreground', first_s=1.0)], {'score': {'p_force': 0.0}})
        busy = environment.render_environment_preset(p, duration_s=20.0, sr=SR, seed=3, context={'score': sc, 't0_s': 0.0})
        free = environment.render_environment_preset(p, duration_s=20.0, sr=SR, seed=3)
        late = environment.render_environment_preset(p, duration_s=20.0, sr=SR, seed=3, context={'score': sc, 't0_s': 40.0})
        self.assertLess(float(np.abs(busy).max()), float(np.abs(free).max()))                     # the bird had to wait
        self.assertTrue(np.array_equal(late, free))                                               # 40 s into the piece the score is silent

    def test_the_layer_engine_ignores_the_context(self):
        cfg = {'layers': [dict(name='air', primitive='noise_bed', kind='bed', gain_db=-22.0, low_hz=120, high_hz=2600)]}
        a = environment.render_environment_preset(cfg, duration_s=1.0, sr=SR, seed=1)
        b = environment.render_environment_preset(cfg, duration_s=1.0, sr=SR, seed=1, context={'score': {}, 't0_s': 3.0})
        self.assertTrue(np.array_equal(a, b))

    def test_an_environment_track_of_a_score_gets_the_piece_it_sits_in(self):
        import render_natural as rn
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'environments'))
            p = preset([animal('bird', (400, 480), rate=20.0, salience='foreground', first_s=1.0)], {'score': {'p_force': 0.0}})
            p['generators'] = []                                            # only the bird, so the stem shows when it calls
            json.dump(dict(p, name='eco_bed', character='a bird that waits for the lead'), open(os.path.join(d, 'presets', 'environments', 'eco_bed.json'), 'w'))
            presets.reset_projects()
            presets.add_project(d)
            try:
                sc = score([('lead', 'melody', [(k * 2, 1.9, 69, 110) for k in range(0, 8)])], bpm=120.0)
                sc['tracks'] = [t for t in sc['tracks'] if t['name'] != 'clock']                      # the helper's tempo-map anchor is not a renderable sound
                sc['tracks'].append(dict(name='bed', instrument='env:eco_bed', role='environment', notes=[dict(t=0, d=40, p=60, v=80)]))
                stems, _ = rn.build_stems(sc, verbose=False)
                self.assertIs(rn._PIECE['score'], sc)
                bed = stems['bed']
                quiet = float(np.abs(bed[:int(7.5 * SR)]).max())           # the lead holds A4 for 8 s (16 beats at 120 bpm): the bird waits
                later = float(np.abs(bed[int(10 * SR):]).max())
                self.assertGreater(later, 0.0)
                self.assertGreater(later, quiet)
            finally:
                presets.reset_projects()


class Schema(unittest.TestCase):
    def base(self, eco):
        return preset([animal('tiger', (80, 400)), animal('thrush', (2000, 4000))], eco, controls={'dawn': {'curve': [[0, 0], [10, 1]]}})

    def test_a_valid_ecology_is_clean(self):
        eco = {'density_budget': {'events_per_s_max': 2.0, 'fatigue_guard': True}, 'niches': {'auto': True, 'min_separation': 'D<=0.4'},
               'rules': [{'on': {'fauna': 'tiger'}, 'do': {'freeze': ['thrush'], 'for_s': [10, 25], 'fade_ms': 400, 'ramp_s': 8}},
                         {'on': {'score': 'drop'}, 'do': {'answer': 'thrush', 'after_ms': [300, 900], 'p': 0.5}}],
               'score': {'occupancy': 'from_score', 'protect_roles': ['melody', 'lead', 'vocal'], 'margin_db': 3, 'pocket_threshold': 0.35}}
        self.assertEqual(schema.problems(self.base(eco)), [])

    def test_unknown_names_and_keys_are_errors(self):
        bad = [{'colour': 1}, {'rules': [{'on': {'fauna': 'nope'}, 'do': {'freeze': ['thrush']}}]},
               {'rules': [{'on': {'fauna': 'tiger'}, 'do': {'freeze': ['nope']}}]}, {'rules': [{'on': {'fauna': 'tiger'}, 'do': {'freeze': ['tiger']}}]},
               {'rules': [{'on': {'fauna': 'tiger', 'score': 'drop'}, 'do': {'freeze': ['thrush']}}]}, {'rules': [{'on': {'fauna': 'tiger'}, 'do': {}}]},
               {'rules': [{'on': {'fauna': 'tiger'}, 'do': {'freeze': ['thrush'], 'speed': 3}}]}, {'niches': {'auto': 'yes'}},
               {'niches': {'min_separation': 'D>0.4'}}, {'density_budget': {'events_per_s_max': -1}}, {'score': {'pocket_threshold': 3}},
               {'score': {'protect_roles': ['wizard']}}, {'score': {'occupancy': 'from_stems'}}, {'rules': 'freeze'},
               {'rules': [{'on': {'fauna': 'tiger'}, 'do': {'freeze': ['thrush'], 'for_s': [9, 2]}}]}]
        for eco in bad:
            self.assertTrue(schema.problems(self.base(eco)), eco)

    def test_the_validator_is_the_one_the_engine_uses(self):
        with self.assertRaises(ValueError):
            engine.Biome(self.base({'colour': 1}))
        self.assertTrue(ecology_schema.problems('nope'))

    def test_every_number_has_a_unit_and_a_doc(self):
        for k, (d, lo, hi, unit, doc) in ecology_schema.NUMBERS.items():
            self.assertLess(lo, hi, k)
            self.assertTrue(unit and doc, k)
            if d is not None:
                self.assertTrue(lo <= d <= hi, k)


if __name__ == '__main__':
    unittest.main()
