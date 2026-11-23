"""M3: the physics laws and the three stateful generators (turbulence, particulate_impacts, modal_field), the controls,
the per-name seeding and the preset schema. Synthetic only: every number is checked against a hand calculation or a
spectrum of the render itself."""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from biome import context, generators as G, physics, schema  # noqa: E402
from phys_core import geometry, medium  # noqa: E402

SR = 44100
AIR = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.02897, gamma=1.4, viscosity_pa_s=1.81e-5, prandtl=0.71),
       'state': {'temperature_k': 293.15}}
TITAN = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.0279, gamma=1.40, viscosity_pa_s=6.0e-6, prandtl=0.71),
         'state': {'temperature_k': 94, 'pressure_pa': 146700}}
MARS = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.04401, gamma=1.29, viscosity_pa_s=1.1e-5, prandtl=0.75),
        'state': {'temperature_k': 210, 'pressure_pa': 610}}


def ctx(med=AIR, g=9.81, seed=1, controls=None, materials=None, sr=SR):
    return context.Context(sr=sr, medium=medium.Medium(med), g=g, controls=controls, seed=seed, materials=materials)


def rms(y):
    return float(np.sqrt(np.mean(np.asarray(y, dtype=np.float64) ** 2)))


def peak_hz(y, lo=20.0, sr=SR):
    y = np.asarray(y, dtype=np.float64)
    s = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    f = np.fft.rfftfreq(len(y), 1.0 / sr)
    s[f < lo] = 0
    return float(f[int(np.argmax(s))])


def band_share(y, lo, hi, sr=SR):
    s = np.abs(np.fft.rfft(np.asarray(y, dtype=np.float64) * np.hanning(len(y)))) ** 2
    f = np.fft.rfftfreq(len(y), 1.0 / sr)
    return float(s[(f >= lo) & (f <= hi)].sum() / s.sum())


def wind(u, d=0.005, area=10.0, intensity=0.01, bb=0.01, name='w', **kw):
    return dict(name=name, kind='turbulence', obstacles=dict(d_m=dict(dist='fixed', value=d), frontal_area_m2=area, oscillators=1),
                flow=dict(u_m_s=u, intensity=intensity), broadband=dict(share=bb), **kw)


class Physics(unittest.TestCase):
    def test_strouhal_by_reynolds_number(self):
        self.assertAlmostEqual(physics.strouhal(2661.0), 0.2103, places=3)
        self.assertAlmostEqual(physics.strouhal(132.0), 0.178, delta=0.003)       # laminar shedding, where Roshko is undefined
        self.assertAlmostEqual(physics.strouhal(9000.0), 0.2115, places=3)
        self.assertEqual(physics.strouhal(30.0), 0.0)                              # below 49 the wake is steady and silent
        self.assertEqual(physics.strouhal(5e5), 0.2)

    def test_the_two_laws_join_without_a_step(self):
        steps = [abs(physics.strouhal(r + 0.01) - physics.strouhal(r)) for r in (48.9, 189.9, 249.9)]
        self.assertLess(steps[1], 0.001)
        self.assertLess(steps[2], 0.001)
        self.assertGreater(physics.strouhal(190.0), 0.19)

    def test_a_forced_law_outside_its_range_raises(self):
        with self.assertRaises(ValueError):
            physics.strouhal(132.0, 'roshko')
        with self.assertRaises(ValueError):
            physics.strouhal(5000.0, 'williamson')
        with self.assertRaises(ValueError):
            physics.strouhal(1000.0, 'nope')

    def test_shedding_tones(self):
        self.assertAlmostEqual(physics.shedding_hz(8.0, 0.005, 2661.0), 336.5, delta=1.0)
        self.assertAlmostEqual(physics.shedding_hz(2.0, 0.005, 9000.0), 84.6, delta=0.5)

    def test_terminal_velocity_follows_gravity_and_density(self):
        self.assertAlmostEqual(physics.terminal_velocity(9.81, 0.004, 998, 1.204, 1.1), 8.87, delta=0.05)
        self.assertAlmostEqual(physics.terminal_velocity(1.352, 0.004, 450, 5.237, 0.6), 1.43, delta=0.03)
        self.assertEqual(physics.terminal_velocity(9.81, 0.004, 1.0, 1.204, 1.0), 0.0)          # lighter than the gas: it does not fall

    def test_minnaert_in_two_liquids(self):
        self.assertAlmostEqual(physics.minnaert_hz(1e-3, 1.4, 101325, 998) * 1e-3, 3.287, places=2)
        self.assertAlmostEqual(physics.minnaert_hz(1e-3, 1.4, 146700, 450) * 1e-3, 5.89, places=2)
        self.assertAlmostEqual(physics.minnaert_hz(1e-3, 1.4, 101325, 998), 3.26e3, delta=0.03 * 3.26e3)   # the repo's old 3.26 / R

    def test_dune_pitch_scales_with_root_g(self):
        e, m = physics.dune_hz(9.81, 2e-4), physics.dune_hz(3.71, 2e-4)
        self.assertAlmostEqual(e, 88.6, delta=0.5)
        self.assertAlmostEqual(m / e, math.sqrt(3.71 / 9.81), places=9)

    def test_power_and_pressure_laws(self):
        w = physics.dipole_power(1e-3, 1.2, 4.0, 2.0, 343.0)
        self.assertAlmostEqual(w, 1e-3 * 1.2 * 4.0 ** 6 * 2.0 / 343.0 ** 3, places=15)
        self.assertAlmostEqual(physics.pressure_rms_from_power(413.0, 1e-3, 1.0), math.sqrt(413.0 * 1e-3 / (4 * math.pi)), places=12)
        self.assertAlmostEqual(physics.pressure_rms_from_power(413.0, 1e-3, 2.0) * 2.0, physics.pressure_rms_from_power(413.0, 1e-3, 1.0), places=12)

    def test_a_drop_population_conserves_the_volume_flux(self):
        d, pdf, v, rate = physics.drop_population(20.0, [0.5, 6.0], 9.81, 998.0, 1.204, 1.1)
        vol = float((pdf * math.pi / 6.0 * d ** 3).sum())
        self.assertAlmostEqual(rate * vol, 20.0e-3 / 3600.0, places=12)
        self.assertAlmostEqual(float(pdf.sum()), 1.0, places=12)
        self.assertEqual(physics.drop_population(0.0, [0.5, 6.0], 9.81, 998.0, 1.204, 1.1)[3], 0.0)

    def test_heavier_rain_has_bigger_drops(self):
        _, p_light, _, _ = physics.drop_population(1.0, [0.5, 6.0], 9.81, 998.0, 1.204, 1.1)
        d, p_heavy, _, _ = physics.drop_population(50.0, [0.5, 6.0], 9.81, 998.0, 1.204, 1.1)
        self.assertGreater(float((p_heavy * d).sum()), float((p_light * d).sum()))


class Controls(unittest.TestCase):
    def test_a_curve_interpolates_and_a_number_passes_through(self):
        c = context.Controls({'rain': {'curve': [[0, 10], [10, 30]]}})
        self.assertAlmostEqual(float(c.value({'control': 'rain'}, 5.0)), 20.0)
        self.assertEqual(c.value(7.0, 3.0), 7.0)
        self.assertEqual(c.value(7.0, np.zeros(3)).tolist(), [7.0, 7.0, 7.0])

    def test_an_ou_control_is_the_same_series_in_any_query_order(self):
        cfg = {'gust': {'ou': {'mean': 1.0, 'sigma': 0.3, 'tau_s': 5.0}}}
        a, b = context.Controls(cfg, seed=3), context.Controls(cfg, seed=3)
        late = float(b.value({'control': 'gust'}, 50.0))
        early_then_late = (float(a.value({'control': 'gust'}, 2.0)), float(a.value({'control': 'gust'}, 50.0)))
        self.assertAlmostEqual(early_then_late[1], late, places=12)
        self.assertAlmostEqual(float(b.value({'control': 'gust'}, 2.0)), early_then_late[0], places=12)

    def test_an_ou_control_has_the_declared_mean_and_spread(self):
        c = context.Controls({'g': {'ou': {'mean': 2.0, 'sigma': 0.5, 'tau_s': 2.0}}}, seed=1)
        x = c.value({'control': 'g'}, np.arange(0, 4000.0, 1.0))
        self.assertAlmostEqual(float(x.mean()), 2.0, delta=0.1)
        self.assertAlmostEqual(float(x.std()), 0.5, delta=0.1)

    def test_unknown_control_and_bad_blocks_are_errors(self):
        with self.assertRaises(ValueError):
            context.Controls({'a': {'curve': [[0, 1], [10, 2]]}}).value({'control': 'b'}, 1.0)
        self.assertTrue(context.control_problems({'a': {'curve': [[5, 1], [1, 2]]}}))
        self.assertTrue(context.control_problems({'a': {}}))
        self.assertTrue(context.control_problems({'a': {'curve': [[0, 1], [1, 2]], 'ou': {'sigma': 1, 'tau_s': 1}}}))
        self.assertTrue(context.control_problems({'a': {'ou': {'sigma': 1, 'tau_s': -1}}}))


class Seeds(unittest.TestCase):
    def test_a_seed_comes_from_the_name(self):
        self.assertEqual(context.seed_of(5, 'rain'), context.seed_of(5, 'rain'))
        self.assertNotEqual(context.seed_of(5, 'rain'), context.seed_of(5, 'wind'))
        self.assertNotEqual(context.seed_of(5, 'rain'), context.seed_of(6, 'rain'))

    def test_adding_a_generator_leaves_every_other_one_unchanged(self):
        cfg = wind(8.0, intensity=0.2)
        alone = G.build(cfg, ctx()).render(1.0)
        c = ctx()
        G.build(wind(3.0, name='other'), c).render(0.5)                 # another generator lives and runs in the same context
        together = G.build(cfg, c).render(1.0)
        self.assertTrue(np.array_equal(alone, together))
        self.assertFalse(np.array_equal(alone, G.build(dict(cfg, name='w2'), ctx()).render(1.0)))


class GustSpectrum(unittest.TestCase):
    def test_the_gust_series_falls_as_minus_five_thirds(self):
        g = G.GustSeries(0.05, np.random.default_rng(1))
        x = g.next(300000)
        self.assertAlmostEqual(float(x.std()), 1.0, delta=0.15)
        from scipy import signal
        f, p = signal.welch(x, fs=100.0, nperseg=16384)
        sel = (f > 0.4) & (f < 6.0)
        slope = np.polyfit(np.log(f[sel]), np.log(p[sel]), 1)[0]
        self.assertAlmostEqual(slope, -5.0 / 3.0, delta=0.3)


class TurbulenceGen(unittest.TestCase):
    def test_earth_twig_sings_at_the_strouhal_tone(self):
        y = G.build(wind(8.0), ctx(AIR)).render(4.0)
        self.assertAlmostEqual(peak_hz(y), 336.5, delta=0.05 * 336.5)

    def test_titan_spire_sings_lower_because_the_air_is_thick(self):
        y = G.build(wind(2.0, bb=0.0), ctx(TITAN, g=1.352)).render(6.0)
        self.assertAlmostEqual(peak_hz(y, lo=40.0), 84.6, delta=0.05 * 84.6)

    def test_mars_wind_uses_the_laminar_law(self):
        y = G.build(wind(20.0), ctx(MARS, g=3.71)).render(3.0)
        st = physics.strouhal(MARS_RE)
        self.assertLess(st, 0.19)
        self.assertAlmostEqual(peak_hz(y), st * 20.0 / 0.005, delta=0.06 * st * 20.0 / 0.005)

    def test_the_level_follows_u_cubed_and_the_medium(self):
        lo = rms(G.build(wind(4.0, bb=0.0), ctx(AIR)).render(2.0))
        hi = rms(G.build(wind(8.0, bb=0.0), ctx(AIR)).render(2.0))
        self.assertAlmostEqual(20 * math.log10(hi / lo), 18.06, delta=1.0)                # p goes as U^3
        titan = rms(G.build(wind(8.0, bb=0.0), ctx(TITAN)).render(2.0))
        self.assertGreater(20 * math.log10(titan / hi), 10.0)                              # a thick atmosphere radiates more at the same wind

    def test_the_output_is_pressure_in_pascals_from_the_dipole_law(self):
        c = ctx(AIR)
        m = c.medium
        want = physics.pressure_rms_from_power(m.z, physics.dipole_power(1e-3, m.rho, 8.0, 10.0, m.c))
        self.assertAlmostEqual(rms(G.build(wind(8.0, bb=0.0), c).render(4.0)), want, delta=0.03 * want)

    def test_a_medium_without_viscosity_is_refused_with_a_message(self):
        with self.assertRaises(ValueError) as cm:
            G.build(wind(8.0), ctx({'model': 'iso9613'}))
        self.assertIn('viscosity', str(cm.exception))

    def test_a_wake_below_re_49_is_silent_in_tone(self):
        y = G.build(wind(0.05, d=0.0005, bb=0.0), ctx(AIR)).render(1.0)
        self.assertLess(rms(y), 1e-9)

    def test_lognormal_obstacles_spread_the_tones(self):
        cfg = dict(name='w', kind='turbulence', obstacles=dict(d_m=dict(dist='lognormal', median=0.005, sigma=0.5), frontal_area_m2=10.0, oscillators=16),
                   flow=dict(u_m_s=8.0, intensity=0.05), broadband=dict(share=0.01))
        y = G.build(cfg, ctx(AIR)).render(4.0)
        self.assertGreater(band_share(y, 150, 900), 0.8)
        self.assertLess(band_share(y, 300, 370), 0.5)


MARS_RE = 0.0145 * 20.0 * 0.005 / 1.1e-5      # about 132: only used to name the expected law


class ChunkExact(unittest.TestCase):
    CASES = {
        'turbulence': wind(8.0, intensity=0.3, bb=0.3),
        'rain': dict(name='r', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=15.0, cd=1.1),
                     surface=dict(kind='solid', material='oak', area_m2=20.0, patches=2)),
        'lake': dict(name='l', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=15.0, cd=1.1),
                     surface=dict(kind='liquid', area_m2=20.0), bubbles=dict(p_by_size=[[0.5, 0.5], [6.0, 0.2]])),
        'ice': dict(name='i', kind='modal_field', modes=dict(material='oak', geometry=dict(shape='bar', length_m=1.0, thickness_m=0.03)),
                    excitation=dict(kind='poisson', rate_hz=12.0, energy_j=1e-9)),
        'dune': dict(name='d', kind='modal_field', modes=dict(law='grain_vibration', grain_size_m=2e-4),
                     excitation=dict(kind='continuous', level_pa=0.01)),
    }

    def test_any_chunking_gives_the_same_samples(self):
        for name, cfg in self.CASES.items():
            whole = G.build(cfg, ctx()).process(SR)
            g = G.build(cfg, ctx())
            sizes, left = [1, 4409, 4410, 777, 5000, 12345], SR
            pieces = []
            for n in sizes:
                pieces.append(g.process(n))
                left -= n
            pieces.append(g.process(left))
            self.assertTrue(np.array_equal(whole, np.concatenate(pieces)), name)

    def test_an_event_ring_crosses_a_block_edge_without_a_step(self):
        cfg = self.CASES['ice']
        y = G.build(dict(cfg, excitation=dict(kind='poisson', rate_hz=40.0, energy_j=1e-9)), ctx()).render(3.0)
        edges = np.arange(1, 30) * (SR // 10)
        jumps = np.abs(y[edges] - y[edges - 1])
        self.assertLess(float(jumps.max()), 20.0 * float(np.abs(np.diff(y)).mean()) + 1e-12)


class ParticulateGen(unittest.TestCase):
    def rain(self, rate, med=AIR, g=9.81, cd=1.1, rho=998.0, **kw):
        return dict(name='r', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=rate, cd=cd, rho_particle=rho),
                    surface=dict(kind='solid', material='leaf_green', area_m2=50.0, patches=3), **kw)

    def test_ten_times_the_rain_is_at_least_nine_db_louder(self):
        a = rms(G.build(self.rain(2.0), ctx()).render(4.0))
        b = rms(G.build(self.rain(20.0), ctx()).render(4.0))
        self.assertGreater(20 * math.log10(b / a), 9.0)

    def test_no_rain_is_silence(self):
        self.assertEqual(float(np.abs(G.build(self.rain(0.0), ctx()).render(1.0)).max()), 0.0)

    def test_slow_methane_drops_are_much_quieter_than_earth_rain(self):
        e = rms(G.build(self.rain(10.0), ctx(AIR)).render(4.0))
        t = rms(G.build(self.rain(10.0, cd=0.6, rho=450.0), ctx(TITAN, g=1.352)).render(4.0))
        self.assertLess(20 * math.log10(t / e), -8.0)

    def test_the_rate_follows_a_control_curve(self):
        c = ctx(controls={'storm': {'curve': [[0, 1], [4, 1], [4.01, 40], [8, 40]]}})
        y = G.build(self.rain({'control': 'storm'}), c).render(8.0)
        self.assertGreater(rms(y[5 * SR:]) / rms(y[:3 * SR]), 5.0)

    def test_bubbles_ring_at_the_minnaert_frequency(self):
        base = dict(name='l', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=30.0, cd=1.1, d_mm=[4.0, 4.001]),
                    surface=dict(kind='liquid', area_m2=5.0))
        f = physics.minnaert_hz(0.2 * 4e-3 / 2.0, 1.4, 101325.0, 998.0)
        with_b = G.build(dict(base, bubbles=dict(p_by_size=[[1.0, 1.0], [8.0, 1.0]], energy_share=0.9)), ctx()).render(4.0)
        without = G.build(base, ctx()).render(4.0)
        self.assertAlmostEqual(f, 8212.0, delta=40.0)
        self.assertGreater(band_share(with_b, 0.7 * f, 1.35 * f), 3.0 * band_share(without, 0.7 * f, 1.35 * f))

    def test_a_bubble_in_titan_methane_rings_higher_than_in_water(self):
        base = dict(name='l', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=30.0, cd=1.1, d_mm=[4.0, 4.001]),
                    surface=dict(kind='liquid', area_m2=5.0, rho_kg_m3=450.0), bubbles=dict(p_by_size=[[1.0, 1.0], [8.0, 1.0]], energy_share=0.9))
        y = G.build(base, ctx(TITAN, g=1.352)).render(6.0)
        want = physics.minnaert_hz(0.2 * 4e-3 / 2.0, 1.4, 146700.0, 450.0)
        self.assertGreater(want, 10000.0)
        self.assertGreater(band_share(y, 0.7 * want, 1.35 * want), 0.2)

    def test_a_solid_ring_sits_at_the_surface_modes(self):
        cfg = dict(name='p', kind='particulate_impacts', population=dict(kind='hail', rate_mm_h=30.0, cd=0.8, d_mm=[3.0, 6.0], rho_particle=900.0),
                   surface=dict(kind='solid', material='steel', geometry=dict(shape='plate', width_m=0.1, thickness_m=0.002), area_m2=2.0, patches=1))
        f1 = geometry.resolve({'material': 'steel', 'geometry': {'shape': 'plate', 'width_m': 0.1, 'thickness_m': 0.002}, 'modes': 6}, {})[0]
        y = G.build(cfg, ctx()).render(4.0)
        self.assertGreater(band_share(y, 0.7 * f1, 1.6 * f1), 0.3)

    def test_the_materials_of_the_preset_are_used(self):
        mats = {'ice': {'family': 'brittle', 'density': 920, 'young_modulus_gpa': 9.0, 'loss_factor': 0.004}}
        cfg = dict(name='p', kind='particulate_impacts', population=dict(kind='hail', rate_mm_h=30.0, d_mm=[3.0, 6.0]),
                   surface=dict(kind='solid', material='ice', geometry=dict(shape='plate', width_m=0.3, thickness_m=0.05), area_m2=2.0))
        y = G.build(cfg, ctx(materials=mats)).render(2.0)
        self.assertGreater(rms(y), 0.0)

    def test_the_output_is_finite_and_float32(self):
        y = G.build(self.rain(60.0), ctx()).render(2.0)
        self.assertEqual(y.dtype, np.float32)
        self.assertTrue(np.isfinite(y).all())


class ModalFieldGen(unittest.TestCase):
    def dune(self, g):
        cfg = dict(name='d', kind='modal_field', modes=dict(law='grain_vibration', grain_size_m=2e-4), excitation=dict(kind='continuous', level_pa=0.01))
        return G.build(cfg, ctx(g=g)).render(6.0)

    def test_a_dune_sings_at_k_root_g_over_d(self):
        self.assertAlmostEqual(peak_hz(self.dune(9.81)), 88.6, delta=3.0)

    def test_the_same_dune_sings_lower_on_mars(self):
        e, m = peak_hz(self.dune(9.81)), peak_hz(self.dune(3.71))
        self.assertAlmostEqual(m / e, math.sqrt(3.71 / 9.81), delta=0.04)

    def test_a_continuous_source_has_the_declared_level(self):
        self.assertAlmostEqual(rms(self.dune(9.81)), 0.01, delta=0.0015)

    def test_a_plate_rings_at_its_first_mode(self):
        geo = dict(shape='bar', length_m=1.2, thickness_m=0.03)
        f1 = geometry.resolve({'material': 'oak', 'geometry': geo, 'modes': 8}, {})[0]
        cfg = dict(name='p', kind='modal_field', modes=dict(material='oak', geometry=geo), excitation=dict(kind='poisson', rate_hz=6.0, energy_j=1e-8))
        y = G.build(cfg, ctx()).render(8.0)
        self.assertAlmostEqual(peak_hz(y), f1, delta=0.03 * f1)

    def test_an_explicit_mode_list(self):
        cfg = dict(name='m', kind='modal_field', modes={'list': [[500.0, 0.5, 0.0]]}, excitation=dict(kind='poisson', rate_hz=8.0, energy_j=1e-8))
        self.assertAlmostEqual(peak_hz(G.build(cfg, ctx()).render(6.0)), 500.0, delta=8.0)

    def test_stress_events_come_in_bursts(self):
        def spread(kind):
            cfg = dict(name='s', kind='modal_field', modes={'list': [[300.0, 0.2, 0.0]]}, excitation=dict(kind=kind, rate_hz=10.0, energy_j=1e-8, sigma=0.0))
            y = G.build(cfg, ctx(seed=4)).render(60.0)
            blocks = y[:len(y) // 4410 * 4410].reshape(-1, 4410)
            r = np.sqrt((blocks ** 2).mean(axis=1))
            return float(r.std() / r.mean())
        self.assertGreater(spread('stress'), 1.2 * spread('poisson'))

    def test_every_mode_above_nyquist_is_an_error(self):
        cfg = dict(name='m', kind='modal_field', modes={'list': [[30000.0, 0.5, 0.0]]}, excitation=dict(kind='poisson', rate_hz=8.0))
        with self.assertRaises(ValueError):
            G.build(cfg, ctx())

    def test_the_energy_sets_the_pressure(self):
        def level(e):
            cfg = dict(name='m', kind='modal_field', modes={'list': [[500.0, 0.3, 0.0]]}, excitation=dict(kind='poisson', rate_hz=6.0, energy_j=e, sigma=0.0))
            return rms(G.build(cfg, ctx()).render(6.0))
        self.assertAlmostEqual(20 * math.log10(level(1e-6) / level(1e-8)), 20.0, delta=0.5)        # 100x the energy is 10x the pressure: p goes as the square root of E


class Schema(unittest.TestCase):
    def preset(self, **over):
        p = {'schema': 'biome/1', 'name': 't', 'character': 'a test place', 'medium': AIR,
             'generators': [wind(8.0)]}
        p.update(over)
        return p

    def test_a_valid_preset_is_clean(self):
        self.assertEqual(schema.problems(self.preset()), [])

    def test_unknown_keys_everywhere_are_errors(self):
        self.assertTrue(any('unknown top-level' in p for p in schema.problems(self.preset(colour=1))))
        g = wind(8.0)
        g['obstacles']['shiny'] = 1
        self.assertTrue(any('shiny' in p for p in schema.problems(self.preset(generators=[g]))))
        self.assertTrue(any('unknown key "foo"' in p for p in schema.problems(self.preset(generators=[dict(wind(8.0), foo=1)]))))

    def test_there_is_no_silent_earth_default(self):
        p = self.preset()
        del p['medium']
        self.assertTrue(any('medium' in x for x in schema.problems(p)))
        self.assertTrue(any('not both' in x for x in schema.problems(self.preset(media={'air': AIR}))))

    def test_ranges_are_refused_not_clamped(self):
        g = wind(8.0)
        g['flow']['intensity'] = 5.0
        self.assertTrue(schema.problems(self.preset(generators=[g])))
        self.assertTrue(schema.problems(self.preset(world={'g_m_s2': -1})))

    def test_a_control_reference_must_exist(self):
        g = wind({'control': 'gust'})
        self.assertTrue(any('control' in p for p in schema.problems(self.preset(generators=[g]))))
        self.assertEqual(schema.problems(self.preset(generators=[g], controls={'gust': {'curve': [[0, 2], [10, 9]]}})), [])

    def test_duplicate_names_are_refused_because_the_name_is_the_seed(self):
        self.assertTrue(any('twice' in p for p in schema.problems(self.preset(generators=[wind(8.0), wind(3.0)]))))

    def test_a_liquid_has_no_material_and_only_a_liquid_has_bubbles(self):
        liquid = dict(name='l', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=5.0),
                      surface=dict(kind='liquid', area_m2=3.0, material='oak'))
        self.assertTrue(any('liquid surface' in p for p in schema.generator_problems(liquid)))
        solid = dict(name='s', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=5.0), surface=dict(kind='solid', area_m2=3.0),
                     bubbles=dict(p_by_size=[[1.0, 0.5]]))
        self.assertTrue(any('only a liquid' in p for p in schema.generator_problems(solid)))

    def test_only_cylinders_are_modelled(self):
        g = wind(8.0)
        g['obstacles']['shape'] = 'plate'
        self.assertTrue(any('cylinder' in p for p in schema.generator_problems(g)))

    def test_modal_field_needs_exactly_one_way_to_say_its_modes(self):
        cfg = dict(name='m', kind='modal_field', modes={'list': [[100, 1, 0]], 'law': 'grain_vibration'}, excitation=dict(kind='poisson', rate_hz=1))
        self.assertTrue(any('exactly one' in p for p in schema.generator_problems(cfg)))
        self.assertTrue(any('rate_hz' in p for p in schema.generator_problems(dict(cfg, modes={'list': [[100, 1, 0]]}, excitation=dict(kind='poisson')))))

    def test_the_wrong_schema_id_and_a_missing_character(self):
        self.assertTrue(schema.problems(self.preset(schema='biome/9')))
        self.assertTrue(schema.problems(self.preset(character='  ')))
        self.assertTrue(schema.problems('nope'))

    def test_every_number_in_the_schema_table_has_a_unit_and_a_doc(self):
        for k, (default, lo, hi, unit, doc) in schema.NUMBERS.items():
            self.assertLess(lo, hi, k)
            self.assertTrue(unit and doc, k)
            if default is not None:
                self.assertTrue(lo <= default <= hi, k)

    def test_unknown_generator_kind_cannot_be_built(self):
        with self.assertRaises(ValueError):
            G.build(dict(name='x', kind='lightning'), ctx())


if __name__ == '__main__':
    unittest.main()
