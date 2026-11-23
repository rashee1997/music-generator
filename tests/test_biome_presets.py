"""M9: the shipped example biomes validate, render, behave as their ecology says, and are honest about what is an estimate."""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import env_rows  # noqa: E402
import environment  # noqa: E402
import presets  # noqa: E402
from biome import engine, schema  # noqa: E402

SR = 44100
EXAMPLES = ('western_ghats_monsoon', 'titan_methane_storm')


def cfg(name):
    return presets.find_environment(name)


def score_for(name, notes=()):
    c = cfg(name)
    med = c['media']['air'] if 'media' in c else c['medium']
    tracks = [dict(name='bed', instrument=f'env:{name}', role='environment', notes=[dict(t=0, d=80, p=60, v=80)])]
    if notes:
        tracks.append(dict(name='lead', role='melody', instrument='piano', notes=[dict(zip(('t', 'd', 'p', 'v'), n)) for n in notes]))
    return dict(bpm=120, ts=[4, 4], seed=1, humanize='tight', medium=med, tracks=tracks, plan={})


class Examples(unittest.TestCase):
    def test_they_are_shipped_environments_and_validate(self):
        known = presets.load('environments')
        for n in EXAMPLES:
            self.assertIn(n, known)
            self.assertEqual(schema.problems(cfg(n)), [], n)
            self.assertEqual(environment.preset_problems(cfg(n)), [], n)
            self.assertTrue(environment.preset_is_bed(cfg(n)), n)

    def test_they_render_finite_non_silent_stereo(self):
        for n in EXAMPLES:
            y = environment.render_environment_preset(n, duration_s=6.0, sr=SR, seed=11)
            self.assertEqual(y.shape, (6 * SR, 2))
            self.assertTrue(np.isfinite(y).all())
            self.assertGreater(float(np.abs(y).max()), 0.0, n)

    def test_every_block_names_its_sources_and_the_estimates_are_listed(self):
        for n in EXAMPLES:
            out = []
            env_rows.declaration_row(env_rows.gate_profiles.resolve({}), dict(track='bed', name=n, preset=cfg(n)), out)
            self.assertEqual(out[0][0], 'WARN', out)                                    # a shipped example is full of ESTIMATE, and says so
            self.assertIn('ESTIMATE remains on', out[0][2])

    def test_no_example_asks_for_more_impacts_than_the_engine_allows(self):
        for n in EXAMPLES:
            b = engine.Biome(cfg(n), seed=3)
            for s in b.sources:
                gen = s.gen
                rate = gen.events_per_s(3.0) if hasattr(gen, 'events_per_s') else None
                if rate is not None:
                    self.assertLess(rate, 250000.0, (n, s.name))


class WesternGhats(unittest.TestCase):
    def test_the_tiger_silences_the_thrush_and_the_frogs(self):
        b = engine.Biome(cfg('western_ghats_monsoon'), seed=5)
        b.planner.plan_until(90.0)
        rep = b.planner.report()
        tiger = [s for s, _ in rep['bouts']['tiger_roar/0']]
        self.assertTrue(tiger)
        for n in ('malabar_thrush', 'tree_frogs'):
            self.assertTrue(rep['windows'][n], n)
            for t0, t1, _, _ in rep['windows'][n]:
                self.assertAlmostEqual(t0, min(tiger, key=lambda s: abs(s - t0)), places=6)
                for k, v in rep['bouts'].items():
                    if k.startswith(n):
                        self.assertEqual([s for s, _ in v if t0 <= s < t1], [])

    def test_the_thrush_calls_more_as_the_day_opens(self):
        c = dict(cfg('western_ghats_monsoon'))
        c['ecology'] = dict(c['ecology'], rules=[])                                   # no tiger: only the time of day shapes the calling
        early = late = 0
        for seed in range(6):
            b = engine.Biome(c, seed=seed)
            b.planner.plan_until(100.0)
            calls = [s for k, v in b.planner.report()['bouts'].items() if k.startswith('malabar_thrush') for s, _ in v]
            early += len([s for s in calls if s < 15.0])
            late += len([s for s in calls if 40.0 <= s < 100.0])
        self.assertGreater(late / 60.0, 1.5 * early / 15.0)                           # dawn_dusk: 0.2 at the start (0.4 on average over 15 s), about 0.9 from 40 s

    def test_a_lead_in_the_thrushs_band_makes_it_wait(self):
        notes = [(k * 2, 1.9, 91, 110) for k in range(0, 60)]                          # G6 and its overtones all through
        quiet = engine.Biome(cfg('western_ghats_monsoon'), seed=5, score=score_for('western_ghats_monsoon'))
        busy = engine.Biome(cfg('western_ghats_monsoon'), seed=5, score=score_for('western_ghats_monsoon', notes))
        for b in (quiet, busy):
            b.planner.plan_until(60.0)
        n = lambda b: sum(len(v) for k, v in b.planner.report()['bouts'].items() if k.startswith('malabar_thrush'))      # noqa: E731
        self.assertGreater(n(quiet), 0)
        self.assertLessEqual(n(busy), n(quiet))

    def test_the_rows_find_nothing_to_fail(self):
        out = env_rows.rows(score_for('western_ghats_monsoon'), window_s=15.0)
        self.assertEqual([n for lv, n, _ in out if lv == 'FAIL'], [])
        self.assertEqual([lv for lv, n, _ in out if n == 'env.medium_consistency'], ['INFO'])
        self.assertEqual([lv for lv, n, _ in out if n == 'env.ecology_rules'], ['INFO'])


class Titan(unittest.TestCase):
    def test_the_medium_is_titans_and_its_speed_matches_the_measurement(self):
        b = engine.Biome(cfg('titan_methane_storm'), seed=3)
        self.assertAlmostEqual(b.listener.c, 198.0, delta=1.0)
        self.assertAlmostEqual(b.listener.consistency()['err_c'], 0.0206, delta=0.003)
        self.assertAlmostEqual(b.listener.rho, 5.24, delta=0.05)

    def test_the_leviathan_is_heard_through_the_sea_surface(self):
        rep = {r['name']: r for r in engine.Biome(cfg('titan_methane_storm'), seed=3).report()}
        self.assertAlmostEqual(rep['leviathan']['interface_db'], -21.8, delta=0.3)
        self.assertEqual(rep['leviathan']['medium'], 'sea')
        self.assertEqual(rep['sonar_skitterers']['interface_db'], 0.0)

    def test_the_wind_sings_low_in_thick_cold_air(self):
        b = engine.Biome(cfg('titan_methane_storm'), seed=3)
        gen = b.source('spire_wind').gen
        re = b.listener.reynolds(2.0, 0.05)
        self.assertGreater(re, 1000.0)
        self.assertLess(gen.expected_rms_pa(1.0) * math.sqrt(2.0), 1.0)

    def test_raindrops_fall_slowly_under_titans_gravity(self):
        b = engine.Biome(cfg('titan_methane_storm'), seed=3)
        d, pdf, v, rate = b.source('methane_rain_ice').gen.population(12.0)
        self.assertLess(float(v.max()), 3.0)                                            # metres a second: Earth rain falls at 9 and more
        self.assertGreater(rate, 0.0)

    def test_the_rows_find_nothing_to_fail(self):
        out = env_rows.rows(score_for('titan_methane_storm'), window_s=15.0)
        self.assertEqual([n for lv, n, _ in out if lv == 'FAIL'], [])
        self.assertEqual([lv for lv, n, _ in out if n == 'env.medium_consistency'], ['INFO'])


class Pruned(unittest.TestCase):
    def test_the_dead_distance_filter_is_gone(self):
        self.assertFalse(hasattr(environment, 'apply_environmental_acoustics'))
        self.assertFalse(hasattr(environment, 'pb'))

    def test_the_layer_engine_still_renders_its_shipped_presets(self):
        for n in ('amazon_rainforest', 'savanna_dusk', 'wetland_night', 'woodland_dawn'):
            y = environment.render_environment_preset(n, duration_s=2.0, sr=SR, seed=1)
            self.assertEqual(y.shape, (2 * SR, 2))
            self.assertTrue(np.isfinite(y).all())


if __name__ == '__main__':
    unittest.main()
