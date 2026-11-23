"""M5: the streaming engine. Chunk-size independence, bounded memory, placement (distance, absorption, interfaces, pan,
diffuse field), the hand-over to environment.render_environment_preset and name-seeded independence of the sources."""
import copy
import math
import os
import sys
import tracemalloc
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import environment  # noqa: E402
from biome import engine, physics  # noqa: E402
from phys_core import medium  # noqa: E402

SR = 44100
AIR = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.02897, gamma=1.4, viscosity_pa_s=1.81e-5, prandtl=0.71),
       'state': {'temperature_k': 293.15, 'pressure_pa': 89900}}
WATER = {'model': 'liquid', 'c_m_s': 1482.0, 'rho_kg_m3': 998.0, 'gas': {'gamma': 1.4}, 'state': {'pressure_pa': 101325.0}}


def wind(name='wind', **spatial):
    return dict(name=name, kind='turbulence', obstacles=dict(d_m=dict(dist='fixed', value=0.005), frontal_area_m2=10.0, oscillators=1),
                flow=dict(u_m_s=8.0, intensity=0.02), broadband=dict(share=0.02), spatial=spatial)


def preset(**over):
    p = {'schema': 'biome/1', 'name': 'test_place', 'character': 'a test place for the engine', 'media': {'air': AIR, 'sea': WATER},
         'controls': {'rain': {'curve': [[0, 12], [20, 28]]}},
         'materials': {'leaf_wet': {'family': 'membrane', 'density': 900, 'young_modulus_gpa': 0.05, 'loss_factor': 0.14,
                                    'thickness_m': 0.0003, 'flow_resistivity': 9000}},
         'generators': [
             dict(name='rain', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h={'control': 'rain'}, cd=1.1),
                  surface=dict(kind='solid', material='leaf_wet', area_m2=30.0, patches=3), spatial=dict(field=True, distance=3.0)),
             dict(name='pond', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=15.0, cd=1.1),
                  surface=dict(kind='liquid', area_m2=20.0), bubbles=dict(p_by_size=[[0.5, 0.4], [6.0, 0.1]]), spatial=dict(azimuth=-70, distance=18)),
             dict(name='wind', kind='turbulence', obstacles=dict(d_m=dict(dist='lognormal', median=0.004, sigma=0.5), frontal_area_m2=40.0),
                  flow=dict(u_m_s=2.5, intensity=0.35), spatial=dict(field=True, distance=2.0))],
         'fauna': [dict(name='tiger', power_w=0.01, bouts_per_min=6.0, first_s=1.0, source=dict(kind='glottal_chaos', rd=1.8, subharmonic=0.4, chaos=0.25),
                        elements=dict(roar={'f0_hz': [[0, 120], [0.4, 150], [1, 90]], 'ms': [800, 1000]}), position=dict(azimuth=110, distance=60)),
                   dict(name='leviathan', medium='sea', power_w=0.5, bouts_per_min=4.0, first_s=0.5, source=dict(kind='glottal_chaos', rd=2.0),
                        elements=dict(c={'f0_hz': [[0, 40], [1, 60]], 'ms': [1500, 2000]}), position=dict(azimuth=-20, distance=120))]}
    p.update(over)
    return p


def only(*gens, fauna=()):
    return preset(generators=list(gens), fauna=list(fauna), controls={})


def rms(y):
    return float(np.sqrt(np.mean(np.asarray(y, dtype=np.float64) ** 2)))


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])


class Chunks(unittest.TestCase):
    def test_the_render_does_not_depend_on_the_chunk_size(self):
        a = engine.Biome(preset(), seed=3).render(6.0, chunk_s=5.0)
        b = engine.Biome(preset(), seed=3).render(6.0, chunk_s=0.7)
        self.assertEqual(a.shape, b.shape)
        scale = float(np.abs(a).max())
        self.assertLess(float(np.abs(a - b).max()), 1e-5 * scale + 1e-12)

    def test_process_in_odd_pieces_equals_the_stream(self):
        whole = engine.Biome(preset(), seed=3).render(4.0)
        b = engine.Biome(preset(), seed=3)
        parts = [b.process(n) for n in (5, 4409, 30000, 4410)]
        parts.append(b.process(4 * SR - sum(len(p) for p in parts)))
        got = np.concatenate(parts)
        self.assertLess(float(np.abs(whole - got).max()), 1e-5 * float(np.abs(whole).max()) + 1e-12)

    def test_the_same_seed_gives_the_same_samples_and_another_seed_does_not(self):
        a = engine.Biome(preset(), seed=3).render(3.0)
        self.assertTrue(np.array_equal(a, engine.Biome(preset(), seed=3).render(3.0)))
        self.assertFalse(np.array_equal(a, engine.Biome(preset(), seed=4).render(3.0)))

    def test_shape_dtype_and_finiteness(self):
        y = engine.Biome(preset(), seed=1).render(2.5)
        self.assertEqual(y.shape, (int(2.5 * SR), 2))
        self.assertEqual(y.dtype, np.float32)
        self.assertTrue(np.isfinite(y).all())

    def test_there_is_no_step_at_a_chunk_edge(self):
        y = engine.Biome(preset(), seed=1).render(20.0, chunk_s=5.0)
        m = y[:, 0].astype(np.float64)
        edges = np.arange(1, 4) * 5 * SR
        d = np.abs(np.diff(m))
        for e in edges:
            self.assertLess(float(d[e - 1]), 8.0 * float(np.percentile(d, 99.9)))


class Memory(unittest.TestCase):
    def test_a_long_render_needs_the_memory_of_a_chunk_not_of_the_piece(self):
        def peak(seconds):
            b = engine.Biome(preset(), seed=2)
            tracemalloc.start()
            try:
                for _ in b.stream(seconds, chunk_s=5.0):
                    pass
                return tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
        short, long = peak(10.0), peak(40.0)
        self.assertLess(long, 200e6)
        self.assertLess(long, 1.5 * short + 5e6)                      # four times the piece, no more memory
        self.assertGreater(600 * SR * 8, 200e6)                       # one float64 draw of one layer of ten minutes: what the layer engine needed


class Placement(unittest.TestCase):
    def one(self, cfg, seconds=3.0, **kw):
        return engine.Biome(only(cfg, **kw), seed=1).render(seconds)

    def test_doubling_the_distance_halves_the_pressure(self):
        a = rms(self.one(wind(distance=10.0, azimuth=0)))
        b = rms(self.one(wind(distance=20.0, azimuth=0)))
        self.assertAlmostEqual(20 * math.log10(a / b), 6.02, delta=0.5)

    def test_a_far_source_loses_its_high_frequencies_to_the_air(self):
        def band(y, lo, hi):
            s = np.abs(np.fft.rfft(y[:, 0].astype(np.float64))) ** 2
            f = np.fft.rfftfreq(len(y), 1.0 / SR)
            return float(s[(f >= lo) & (f <= hi)].sum())
        cfg = lambda d: dict(name='hiss', kind='turbulence', obstacles=dict(d_m=dict(dist='fixed', value=0.005), frontal_area_m2=10.0, oscillators=1),   # noqa: E731
                             flow=dict(u_m_s=8.0, intensity=0.02), broadband=dict(share=1.0, band_hz=[200, 18000]), spatial=dict(distance=d, azimuth=0))
        near, far = self.one(cfg(2.0)), self.one(cfg(400.0))
        hi = band(far, 8000, 16000) / band(near, 8000, 16000)
        lo = band(far, 200, 800) / band(near, 200, 800)
        m = medium.Medium(AIR)
        self.assertLess(hi, 0.25 * lo)
        self.assertAlmostEqual(10 * math.log10(hi / lo), -float(m.alpha_db_per_m(11000.0)) * 398.0, delta=8.0)

    def test_azimuth_pans_a_point_source(self):
        right = self.one(wind(azimuth=90, distance=5.0))
        left = self.one(wind(azimuth=-90, distance=5.0))
        centre = self.one(wind(azimuth=0, distance=5.0))
        self.assertGreater(20 * math.log10(rms(right[:, 1]) / max(rms(right[:, 0]), 1e-12)), 20.0)
        self.assertGreater(20 * math.log10(rms(left[:, 0]) / max(rms(left[:, 1]), 1e-12)), 20.0)
        self.assertAlmostEqual(rms(centre[:, 0]), rms(centre[:, 1]), delta=0.02 * rms(centre[:, 0]))
        self.assertAlmostEqual(rms(centre[:, 0]) ** 2 + rms(centre[:, 1]) ** 2, rms(right[:, 1]) ** 2 + rms(right[:, 0]) ** 2, delta=0.03 * rms(centre[:, 0]) ** 2 * 2)

    def test_a_field_is_wide_and_a_point_is_not(self):
        broad = lambda **sp: dict(wind(**sp), broadband=dict(share=1.0, band_hz=[150, 12000]))      # noqa: E731  a tone only changes phase
        point = self.one(broad(azimuth=0, distance=3.0))
        field = self.one(broad(field=True, distance=3.0))
        self.assertGreater(corr(point[:, 0], point[:, 1]), 0.99)
        self.assertLess(corr(field[:, 0], field[:, 1]), 0.6)
        self.assertAlmostEqual(rms(field), rms(point), delta=0.25 * rms(point))          # decorrelating keeps the level

    def test_a_source_in_the_sea_is_heard_through_the_interface(self):
        loud = dict(name='whale', power_w=0.5, bouts_per_min=30.0, first_s=0.2, source=dict(kind='glottal_chaos', rd=2.0),
                    elements=dict(c={'f0_hz': 60.0, 'ms': [800, 900]}), position=dict(azimuth=0, distance=1.0))
        in_sea = engine.Biome(only(fauna=[dict(loud, medium='sea')]), seed=1)
        in_air = engine.Biome(only(fauna=[loud]), seed=1)
        a, b = in_sea.render(4.0), in_air.render(4.0)
        sea, air = medium.Medium(WATER), medium.Medium(AIR)
        expect = (10 * math.log10(sea.z / air.z) + sea.transmission_db(air)) / 1.0          # pressure at 1 m in the sea, then through the surface
        self.assertAlmostEqual(20 * math.log10(rms(a) / rms(b)), expect, delta=1.5)
        self.assertAlmostEqual(in_sea.report()[0]['interface_db'], sea.transmission_db(air), places=9)
        self.assertEqual(in_air.report()[0]['interface_db'], 0.0)

    def test_the_report_lists_every_source(self):
        r = engine.Biome(preset(), seed=1).report()
        self.assertEqual([x['name'] for x in r], ['rain', 'pond', 'wind', 'tiger', 'leviathan'])
        self.assertEqual([x['field'] for x in r], [True, False, True, False, False])
        self.assertEqual(r[4]['medium'], 'sea')

    def test_gain_db_is_a_trim_on_top_of_the_physical_level(self):
        a = rms(self.one(wind(azimuth=0, distance=5.0)))
        b = rms(self.one(dict(wind(azimuth=0, distance=5.0), gain_db=-12.0)))
        self.assertAlmostEqual(20 * math.log10(a / b), 12.0, delta=0.1)

    def test_the_level_is_pressure_over_the_full_scale(self):
        m = medium.Medium(AIR)
        want = physics.pressure_rms_from_power(m.z, physics.dipole_power(1e-3, m.rho, 8.0, 10.0, m.c)) / 2.0
        cfg = dict(wind(azimuth=0, distance=1.0), broadband=dict(share=0.0), flow=dict(u_m_s=8.0, intensity=0.0))     # a steady wind: no gust realisation in the mean
        y = self.one(cfg, seconds=4.0)
        self.assertAlmostEqual(rms(y[:, 0]) ** 2 + rms(y[:, 1]) ** 2, want ** 2, delta=0.06 * want ** 2)


class Independence(unittest.TestCase):
    def test_adding_a_source_adds_its_own_signal_and_changes_nothing_else(self):
        a = engine.Biome(only(wind('a', azimuth=-30, distance=4.0)), seed=5).render(2.0).astype(np.float64)
        b = engine.Biome(only(wind('b', azimuth=40, distance=9.0)), seed=5).render(2.0).astype(np.float64)
        both = engine.Biome(only(wind('a', azimuth=-30, distance=4.0), wind('b', azimuth=40, distance=9.0)), seed=5).render(2.0).astype(np.float64)
        self.assertLess(float(np.abs(both - a - b).max()), 1e-5 * float(np.abs(both).max()))


class HandOver(unittest.TestCase):
    def test_environment_renders_a_biome_preset(self):
        y = environment.render_environment_preset(preset(), duration_s=3.0, sr=SR, seed=3)
        self.assertEqual(y.shape, (3 * SR, 2))
        self.assertEqual(y.dtype, np.float32)
        self.assertTrue(np.array_equal(y, engine.Biome(preset(), seed=3).render(3.0)))

    def test_the_layer_engine_is_untouched(self):
        cfg = {'layers': [dict(name='air', primitive='noise_bed', kind='bed', gain_db=-22.0, low_hz=120, high_hz=2600)]}
        self.assertEqual(environment.render_environment_preset(cfg, duration_s=1.0, sr=SR, seed=1).shape, (SR, 2))

    def test_the_preset_validator_and_the_bed_rule_know_a_biome(self):
        self.assertEqual(environment.preset_problems(preset()), [])
        self.assertTrue(environment.preset_problems(dict(preset(), colour=1)))
        self.assertTrue(environment.preset_is_bed(preset()))
        only_foreground = preset(generators=[dict(wind(), salience='foreground')], fauna=[])
        self.assertFalse(environment.preset_is_bed(only_foreground))
        self.assertTrue(engine.is_biome(preset()))
        self.assertFalse(engine.is_biome({'layers': []}))

    def test_a_bad_preset_is_refused_with_its_name(self):
        with self.assertRaises(ValueError) as cm:
            engine.Biome(dict(preset(), colour=1))
        self.assertIn('test_place', str(cm.exception))

    def test_a_listener_medium_that_does_not_exist_is_refused(self):
        p = copy.deepcopy(preset())
        p['world'] = {'listener': {'medium': 'lava'}}
        with self.assertRaises(ValueError):
            engine.Biome(p)


class Pieces(unittest.TestCase):
    def test_the_fir_carries_its_tail(self):
        ir = np.random.default_rng(0).standard_normal(257)
        x = np.random.default_rng(1).standard_normal(5000)
        f = engine.StreamFIR(ir)
        got = np.concatenate([f.process(x[:1234]), f.process(x[1234:])])
        from scipy import signal
        self.assertLess(float(np.abs(got - signal.fftconvolve(x, ir)[:len(x)]).max()), 1e-9)

    def test_the_decorrelator_is_stateful_and_keeps_the_magnitude(self):
        x = np.random.default_rng(2).standard_normal(20000)
        d = engine.StreamDecorrelator(np.random.default_rng(3), SR)
        y = np.concatenate([d.process(x[:7000]), d.process(x[7000:])])
        e = engine.StreamDecorrelator(np.random.default_rng(3), SR)
        self.assertLess(float(np.abs(y - e.process(x)).max()), 1e-9)
        self.assertAlmostEqual(rms(y[2000:, 0]), rms(x[2000:]), delta=0.1 * rms(x))

    def test_pan_gains_are_constant_power(self):
        for az in (-90, -30, 0, 45, 90):
            l, r = engine.pan_gains(az)
            self.assertAlmostEqual(l * l + r * r, 1.0, places=9)
        self.assertGreater(engine.pan_gains(90)[1], engine.pan_gains(90)[0])


if __name__ == '__main__':
    unittest.main()
