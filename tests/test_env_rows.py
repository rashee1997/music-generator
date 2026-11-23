"""M7: the env.* gate rows. Every row has a fixture that passes and a fixture that fails (a row that cannot fail is not a row),
the three stationarity measures are checked against planted artefacts, and the entry point is checked on a real score."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import env_rows  # noqa: E402
import gate_profiles  # noqa: E402
import lint_coverage  # noqa: E402
import presets  # noqa: E402
from biome import engine  # noqa: E402

SR = 44100
AIR = {'model': 'iso9613', 'gas': dict(molar_mass_kg_mol=0.02897, gamma=1.4, viscosity_pa_s=1.81e-5, prandtl=0.71), 'state': {'temperature_k': 293.15},
       'sources': ['ISO 9613-1; viscosity and Prandtl number of air at 20 C, handbook values']}
TITAN = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.0279, gamma=1.40, viscosity_pa_s=6.0e-6, prandtl=0.71),
         'state': {'temperature_k': 94, 'pressure_pa': 146700}, 'sources': ['test']}


def gp():
    return gate_profiles.resolve({})


def bird(name='bird', band=(1500, 3000), power=1e-5, rate=20.0, **over):
    lo, hi = band
    d = dict(name=name, power_w=power, bouts_per_min=rate, first_s=1.0, salience='foreground', niche={'band_hz': [lo, hi]},
             source=dict(kind='dual_syrinx', saturation=0.0, harmonics=1), elements=dict(c={'f_left': (lo * hi) ** 0.5, 'ms': [400, 500]}), sources=['test'])
    d.update(over)
    return d


def rain(name='rain', **over):
    d = dict(name=name, kind='particulate_impacts', stationary=True, population=dict(kind='rain', rate_mm_h=15.0, cd=1.1),
             surface=dict(kind='solid', material='oak', area_m2=20.0, patches=2), spatial=dict(field=True, distance=2.0), sources=['test'])
    d.update(over)
    return d


def wind(name='wind', **over):
    d = dict(name=name, kind='turbulence', obstacles=dict(d_m=dict(dist='fixed', value=0.005), frontal_area_m2=10.0, oscillators=1),
             flow=dict(u_m_s=8.0, intensity=0.0), broadband=dict(share=1.0, band_hz=[150, 12000]), spatial=dict(field=True), sources=['test'])
    d.update(over)
    return d


def preset(generators=None, fauna=None, ecology=None, medium=None, **over):
    p = {'schema': 'biome/1', 'name': 'bed1', 'character': 'a test place for the rows', 'medium': medium or AIR,
         'generators': [rain(), wind()] if generators is None else generators, 'fauna': [bird()] if fauna is None else fauna}
    if ecology is not None:
        p['ecology'] = ecology
    p.update(over)
    return p


def score(notes=(), bpm=120.0, medium=None, span=200):
    tracks = [dict(name='clock', role='fx', instrument='sfx:tick', notes=[dict(t=span - 1, d=1, p=60, v=1)])]
    if notes:
        tracks.append(dict(name='lead', role='melody', instrument='piano', notes=[dict(zip(('t', 'd', 'p', 'v'), n)) for n in notes]))
    sc = dict(bpm=bpm, ts=[4, 4], seed=1, humanize='tight', tracks=tracks, plan={})
    if medium:
        sc['medium'] = medium
    return sc


def rec(p, span=40.0, t0=0.0):
    return dict(track='bed', name='bed1', preset=p, t0=t0, span=span)


def biome_and_plan(p, sc=None, span=40.0):
    b = engine.Biome(p, seed=7, score=sc)
    return b, env_rows.bouts(b, span)


def one(fn, *a, **k):
    out = []
    fn(*a, out, **k)
    assert len(out) == 1, out
    return out[0]


class Declaration(unittest.TestCase):
    def test_a_clean_preset_is_info(self):
        lv, name, msg = one(env_rows.declaration_row, gp(), rec(preset()))
        self.assertEqual((lv, name), ('INFO', 'env.declaration'), msg)

    def test_an_estimate_is_a_warn_and_is_named(self):
        p = preset(fauna=[bird(sources=['ESTIMATE: band from general knowledge'])])
        lv, _, msg = one(env_rows.declaration_row, gp(), rec(p))
        self.assertEqual(lv, 'WARN')
        self.assertIn('animal bird', msg)

    def test_a_block_with_no_sources_fails(self):
        p = preset(fauna=[bird(sources=[])])
        lv, _, msg = one(env_rows.declaration_row, gp(), rec(p))
        self.assertEqual(lv, 'FAIL')
        self.assertIn('animal bird', msg)

    def test_an_invalid_preset_fails_with_its_problem(self):
        lv, _, msg = one(env_rows.declaration_row, gp(), rec(dict(preset(), colour=1)))
        self.assertEqual(lv, 'FAIL')
        self.assertIn('colour', msg)


class Consistency(unittest.TestCase):
    def run_row(self, p, sc=None):
        return one(env_rows.consistency_row, gp(), rec(p), sc or score())

    def test_earth_in_earth_is_info_and_the_scan_is_clean(self):
        self.assertEqual(self.run_row(preset())[0], 'INFO')
        self.assertEqual({m: env_rows.literals(m) for m in env_rows.SCENE_MODULES if env_rows.literals(m)}, {})

    def test_a_speed_far_from_its_measurement_fails_and_a_near_one_warns(self):
        far = dict(TITAN, c_measured_m_s=100.0)
        near = dict(TITAN, c_measured_m_s=198.0 / 1.06)
        self.assertEqual(self.run_row(preset(medium=far), score(medium=TITAN))[0], 'FAIL')
        self.assertEqual(self.run_row(preset(medium=near), score(medium=TITAN))[0], 'WARN')
        self.assertEqual(self.run_row(preset(medium=dict(TITAN, c_measured_m_s=194.0)), score(medium=TITAN))[0], 'INFO')      # Huygens: 2.1 %

    def test_a_biome_in_another_medium_than_the_score_fails(self):
        lv, _, msg = self.run_row(preset(medium=TITAN), score())
        self.assertEqual(lv, 'FAIL')
        self.assertIn('score.medium', msg)

    def test_a_planted_literal_fails(self):
        real = env_rows.literals
        env_rows.literals = lambda path, values=(343, 343.0): [12] if path == 'environment.py' else []
        try:
            lv, _, msg = self.run_row(preset())
        finally:
            env_rows.literals = real
        self.assertEqual(lv, 'FAIL')
        self.assertIn('environment.py:12', msg)

    def test_a_tube_follows_c(self):
        p = preset(fauna=[bird(resonator={'kind': 'tube', 'length_cm': 17.0})])
        lv, _, msg = self.run_row(p)
        self.assertEqual(lv, 'INFO')
        self.assertIn('tube F1', msg)


class Plan(unittest.TestCase):
    def test_niche_rows(self):
        far = preset(fauna=[bird('a', (300, 600)), bird('b', (3000, 6000))])
        b, plan = biome_and_plan(far)
        self.assertEqual(one(env_rows.niche_row, gp(), rec(far), b, plan)[0], 'INFO')
        same = preset(fauna=[bird('a', (1500, 3000), rate=100.0), bird('b', (1500, 3000), rate=100.0, first_s=1.1)])
        b, plan = biome_and_plan(same)
        self.assertIn(one(env_rows.niche_row, gp(), rec(same), b, plan)[0], ('WARN', 'FAIL'))
        kept_apart = preset(fauna=same['fauna'], ecology={'niches': {'auto': True}})
        b, plan = biome_and_plan(kept_apart)
        self.assertEqual(one(env_rows.niche_row, gp(), rec(kept_apart), b, plan)[0], 'INFO')
        solo = preset(fauna=[bird('a')])
        b, plan = biome_and_plan(solo)
        self.assertIn('nothing to compare', one(env_rows.niche_row, gp(), rec(solo), b, plan)[2])

    def test_pocket_rows(self):
        sc = score([(k * 2, 1.9, 84, 110) for k in range(0, 40)])                 # C6 and its overtones all through the span
        busy_band = preset(fauna=[bird('a', (900, 1300), rate=30.0)])
        b, plan = biome_and_plan(busy_band, sc)
        lv, _, msg = one(env_rows.pocket_row, gp(), rec(busy_band), b, plan, sc)
        self.assertEqual(lv, 'FAIL', msg)                                           # no ecology: it calls over the lead
        waiting = preset(fauna=[bird('a', (900, 1300), rate=30.0)], ecology={'score': {'p_force': 1.0, 'max_tries': 0}})
        quiet_sc = score()
        b, plan = biome_and_plan(waiting, quiet_sc)
        self.assertEqual(one(env_rows.pocket_row, gp(), rec(waiting), b, plan, quiet_sc)[0], 'INFO')
        nofg = preset(fauna=[bird('a', salience='bed')])
        b, plan = biome_and_plan(nofg, sc)
        self.assertIn('not measured', one(env_rows.pocket_row, gp(), rec(nofg), b, plan, sc)[2])

    def test_density_rows(self):
        none = preset()
        b, plan = biome_and_plan(none)
        self.assertEqual(one(env_rows.density_row, gp(), rec(none), b, plan)[0], 'INFO')
        ok = preset(fauna=[bird(rate=6.0)], ecology={'density_budget': {'events_per_s_max': 1.0}})
        b, plan = biome_and_plan(ok)
        self.assertEqual(one(env_rows.density_row, gp(), rec(ok), b, plan)[0], 'INFO')
        asks_too_much = preset(fauna=[bird(rate=300.0)], ecology={'density_budget': {'events_per_s_max': 0.2}})
        b, plan = biome_and_plan(asks_too_much)
        lv, _, msg = one(env_rows.density_row, gp(), rec(asks_too_much), b, plan)
        self.assertEqual(lv, 'WARN')
        self.assertIn('thins', msg)
        dense = {'bird': [(float(t) * 0.1, 0.05) for t in range(300)]}                  # a plan that breaks its own budget
        self.assertEqual(one(env_rows.density_row, gp(), rec(asks_too_much), b, dense)[0], 'FAIL')

    def test_rules_rows(self):
        eco = {'rules': [{'on': {'fauna': 'tiger'}, 'do': {'freeze': ['bird'], 'for_s': [6, 6], 'fade_ms': 200}}]}
        tiger = bird('tiger', (80, 400), power=1e-4, rate=6.0, first_s=3.0)
        p = preset(fauna=[tiger, bird('bird', (1500, 3000), rate=30.0)], ecology=eco)
        b, plan = biome_and_plan(p)
        lv, _, msg = one(env_rows.rules_row, gp(), rec(p), b, plan)
        self.assertEqual(lv, 'INFO', msg)
        self.assertIn('every freeze honoured', msg)
        idle = preset(fauna=[bird('tiger', (80, 400), rate=0.05, first_s=500.0), bird('bird', (1500, 3000), rate=30.0)], ecology=eco)
        b, plan = biome_and_plan(idle)
        self.assertEqual(one(env_rows.rules_row, gp(), rec(idle), b, plan)[0], 'WARN')
        b, plan = biome_and_plan(p)
        start = b.planner.report()['windows']['bird'][0]
        broken = dict(plan, bird=plan['bird'] + [(start[0] + 1.0, 0.5)])               # a call inside its own freeze
        self.assertEqual(one(env_rows.rules_row, gp(), rec(p), b, broken)[0], 'FAIL')
        self.assertEqual(one(env_rows.rules_row, gp(), rec(preset()), *biome_and_plan(preset()))[0], 'INFO')


class Measured(unittest.TestCase):
    def test_the_level_follows_the_physics_and_a_normalised_generator_fails(self):
        lv, _, msg = one(env_rows.level_row, gp(), rec(preset()), window_s=10.0)
        self.assertEqual(lv, 'INFO', msg)
        from biome import generators
        real = generators.Particulate.expected_rms_pa
        generators.Particulate.expected_rms_pa = lambda self, t=0.0: real(self, t) * 10.0
        try:
            lv, _, msg = one(env_rows.level_row, gp(), rec(preset()), window_s=10.0)
        finally:
            generators.Particulate.expected_rms_pa = real
        self.assertEqual(lv, 'FAIL', msg)

    def test_a_rate_that_follows_a_curve_is_not_judged_against_one_number(self):
        p = preset(generators=[rain(population=dict(kind='rain', rate_mm_h={'control': 'r'}, cd=1.1))], controls={'r': {'curve': [[0, 5], [60, 50]]}})
        self.assertIn('not measured', one(env_rows.level_row, gp(), rec(p), window_s=5.0)[2])

    def test_a_steady_bed_is_stationary_and_a_ramping_one_is_not(self):
        lv, _, msg = one(env_rows.stationarity_row, gp(), rec(preset(), span=30.0), window_s=24.0)
        self.assertEqual(lv, 'INFO', msg)
        ramp = preset(generators=[rain(population=dict(kind='rain', rate_mm_h={'control': 'r'}, cd=1.1))], controls={'r': {'curve': [[0, 1], [24, 100]]}})
        lv, _, msg = one(env_rows.stationarity_row, gp(), rec(ramp, span=30.0), window_s=24.0)
        self.assertIn(lv, ('WARN', 'FAIL'), msg)
        none = preset(generators=[rain(stationary=False)])
        self.assertIn('not measured', one(env_rows.stationarity_row, gp(), rec(none), window_s=5.0)[2])

    def test_a_field_is_decorrelated_and_a_single_emitter_is_not(self):
        lv, _, msg = one(env_rows.diffuse_row, gp(), rec(preset()), window_s=10.0)
        self.assertEqual(lv, 'INFO', msg)
        one_emitter = preset(generators=[rain(spatial=dict(field=True, emitters=1, distance=2.0))])
        lv, _, msg = one(env_rows.diffuse_row, gp(), rec(one_emitter), window_s=10.0)
        self.assertEqual(lv, 'FAIL', msg)
        point = preset(generators=[rain(spatial=dict(azimuth=30, distance=5.0))])
        self.assertIn('not measured', one(env_rows.diffuse_row, gp(), rec(point), window_s=5.0)[2])

    def test_salience_rows(self):
        beds = [wind(broadband=dict(share=1.0, band_hz=[1000, 4000]), flow=dict(u_m_s=3.0, intensity=0.0))]
        sal = lambda power, sc=None, **kw: self._salience(preset(generators=beds, fauna=[bird(power=power, **kw)]), sc)      # noqa: E731
        lv, _, msg = sal(3e-7)
        self.assertEqual(lv, 'INFO', msg)
        lv, _, msg = sal(1e-12)
        self.assertEqual(lv, 'WARN', msg)                                                   # drowned in its own band
        lv, _, msg = sal(1e6)
        self.assertEqual(lv, 'WARN', msg)                                                   # far louder than anything around it
        sc = score([(k * 2, 1.9, 84, 110) for k in range(0, 60)])
        lv, _, msg = sal(1e6, sc, rate=60.0)
        self.assertEqual(lv, 'FAIL', msg)                                                   # and over the lead's own band for more than 10 s

    def _salience(self, p, sc):
        b, plan = biome_and_plan(p, sc, span=30.0)
        env_rows._SCORES['bed'] = sc
        try:
            return one(env_rows.salience_row, gp(), rec(p, span=30.0), b, plan, window_s=30.0)
        finally:
            env_rows._SCORES.pop('bed', None)

    def test_the_cpu_row_with_a_clock(self):
        def clock(per_probe):
            ticks = iter([0.0, per_probe])
            return lambda: next(ticks)
        self.assertEqual(one(env_rows.cpu_row, gp(), rec(preset()), timer=clock(0.5), probe_s=3.0)[0], 'INFO')        # 10 s a minute
        self.assertEqual(one(env_rows.cpu_row, gp(), rec(preset()), timer=clock(1.0), probe_s=3.0)[0], 'WARN')        # 20
        self.assertEqual(one(env_rows.cpu_row, gp(), rec(preset()), timer=clock(2.0), probe_s=3.0)[0], 'FAIL')        # 40


class Measures(unittest.TestCase):
    def test_window_deviation(self):
        rng = np.random.default_rng(1)
        steady = rng.standard_normal(SR * 16)
        self.assertLess(env_rows.window_deviation(steady), 2.0)                               # the INFO limit of the row: sampling noise only
        ramp = steady * np.linspace(0.2, 2.0, len(steady))
        self.assertGreater(env_rows.window_deviation(ramp), 5.0)

    def test_chunk_seam(self):
        rng = np.random.default_rng(2)
        y = rng.standard_normal(SR * 20)
        self.assertLess(env_rows.chunk_seam_db(y, 1.0), 0.5)
        stepped = y.copy()
        for k in range(1, 20):
            stepped[k * SR:] *= 1.5 if k % 2 else 1.0 / 1.5
        self.assertGreater(env_rows.chunk_seam_db(stepped, 1.0), 1.5)

    def test_repeat_score(self):
        rng = np.random.default_rng(3)
        tile = rng.standard_normal(SR * 6) * np.repeat(rng.uniform(0.2, 2.0, 6), SR)             # a 6 s tile with its own level shape
        self.assertGreater(env_rows.repeat_score(np.tile(tile, 8)), 0.8)
        self.assertLess(env_rows.repeat_score(rng.standard_normal(SR * 48)), 0.4)

    def test_mean_abs_correlation(self):
        rng = np.random.default_rng(4)
        x = rng.standard_normal(SR * 6)
        self.assertGreater(env_rows.mean_abs_correlation(np.stack([x, x], 1)), 0.95)
        self.assertGreater(env_rows.mean_abs_correlation(np.stack([x, -x], 1)), 0.95)                 # anti-phase is not wide either
        self.assertLess(env_rows.mean_abs_correlation(np.stack([x, rng.standard_normal(len(x))], 1)), 0.1)


class Entry(unittest.TestCase):
    ROWS = ['env.declaration', 'env.medium_consistency', 'env.niche_collision', 'env.score_pocket', 'env.density_budget', 'env.ecology_rules',
            'env.level_physical', 'env.loop_stationarity', 'env.diffuse_field', 'env.foreground_salience', 'env.cpu_budget']

    def project(self, p):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'presets', 'environments'))
        json.dump(dict(p, name='bed1'), open(os.path.join(d, 'presets', 'environments', 'bed1.json'), 'w'))
        presets.reset_projects()
        presets.add_project(d)

    def tearDown(self):
        presets.reset_projects()

    def piece(self, **kw):
        sc = score(**kw)
        sc['tracks'] = [t for t in sc['tracks'] if t['name'] != 'clock'] + [dict(name='bed', instrument='env:bed1', role='environment', notes=[dict(t=0, d=40, p=60, v=80)])]
        return sc

    def test_every_row_is_reported_for_a_biome_track(self):
        self.project(preset())
        out = env_rows.rows(self.piece(), window_s=20.0)
        self.assertEqual([n for _, n, _ in out], self.ROWS)
        self.assertTrue(all(lv in ('INFO', 'WARN', 'FAIL') for lv, _, _ in out))
        self.assertTrue(all('"bed"' in d for _, _, d in out))
        self.assertNotIn('FAIL', [lv for lv, n, _ in out if n != 'env.cpu_budget'])

    def test_a_score_without_a_biome_has_no_env_rows(self):
        self.assertEqual(env_rows.rows(score()), [])
        presets.reset_projects()
        sc = score()
        sc['tracks'].append(dict(name='bed', instrument='env:amazon_rainforest', role='environment', notes=[dict(t=0, d=8, p=60, v=80)]))
        self.assertEqual(env_rows.rows(sc), [])                                      # a layer preset is not a biome

    def test_a_profile_can_skip_a_row_with_a_reason(self):
        self.project(preset())
        sc = self.piece()
        sc['gate'] = {'env.cpu_budget': {'mode': 'skip', 'reason': 'this bed is measured elsewhere'}}
        names = [n for _, n, _ in env_rows.rows(sc, window_s=10.0)]
        self.assertNotIn('env.cpu_budget', names)
        self.assertIn('env.declaration', names)

    def test_a_broken_preset_reports_instead_of_raising(self):
        self.project(dict(preset(), colour=1))
        out = env_rows.rows(self.piece(), window_s=5.0)
        self.assertEqual([lv for lv, n, _ in out if n == 'env.declaration'], ['FAIL'])
        self.assertTrue(any('not measured' in d for _, n, d in out if n != 'env.declaration'))

    def test_the_gate_calls_it(self):
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'quality_gate.py'), encoding='utf-8').read()
        self.assertIn('env_rows.rows(score, rendered, stems', src)

    def test_the_rows_are_registered_and_covered(self):
        env = [r for r in gate_profiles.ROWS if r.startswith('env.')]
        self.assertEqual(sorted(env), sorted(self.ROWS))
        self.assertEqual(lint_coverage.missing(env), [])
        for r in env:
            self.assertTrue(gate_profiles.ROWS[r]['meaning'] and gate_profiles.ROWS[r].get('hint'), r)
            for k, (default, lo, hi) in (gate_profiles.ROWS[r].get('params') or {}).items():
                self.assertTrue(lo <= default <= hi, (r, k))

    def test_a_threshold_outside_its_range_is_refused(self):
        sc = score()
        sc['gate'] = {'env.score_pocket': {'mode': 'relax', 'min_in_pocket': 0.1, 'reason': 'test'}}
        self.assertTrue([r for r in gate_profiles.resolve(sc).errors] or gate_profiles.resolve(sc).param('env.score_pocket', 'min_in_pocket') != 0.1)


if __name__ == '__main__':
    unittest.main()
