"""M1: the Medium object. One law for absorption (ISO 9613-1 is an instance of it), bulk state from gas properties,
interfaces, and a schema that refuses what it does not know."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import airabs  # noqa: E402
from phys_core import medium  # noqa: E402

SR = 44100
AIR = dict(molar_mass_kg_mol=0.02897, gamma=1.40, viscosity_pa_s=1.81e-5, prandtl=0.71)
TITAN = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.0279, gamma=1.40, viscosity_pa_s=6.0e-6, prandtl=0.71),
         'state': {'temperature_k': 94, 'pressure_pa': 146700}, 'c_measured_m_s': 194.0}
MARS = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.04401, gamma=1.29, viscosity_pa_s=1.1e-5, prandtl=0.75),
        'state': {'temperature_k': 210, 'pressure_pa': 610}}


class Bulk(unittest.TestCase):
    def test_earth_default_keeps_the_repo_speed_of_sound(self):
        m = medium.Medium()
        self.assertEqual(m.c, 343.0)
        self.assertEqual(medium.active().c, 343.0)
        self.assertAlmostEqual(m.rho, 1.204, delta=0.01)
        self.assertAlmostEqual(m.z, 413.0, delta=2.0)

    def test_ideal_gas_earth_is_343(self):
        m = medium.Medium({'model': 'ideal_gas', 'gas': AIR, 'state': {'temperature_k': 293.15}})
        self.assertAlmostEqual(m.c, 343.2, delta=0.5)

    def test_titan_and_mars_follow_from_the_gas(self):
        t, ma = medium.Medium(TITAN), medium.Medium(MARS)
        self.assertAlmostEqual(t.c, 198.0, delta=1.0)
        self.assertAlmostEqual(t.rho, 5.24, delta=0.05)
        self.assertAlmostEqual(ma.c, 226.2, delta=1.0)
        self.assertLess(ma.z, 5.0)                                   # a thin atmosphere has almost no impedance

    def test_a_measured_speed_is_checked_against_the_declared_state(self):
        err = medium.Medium(TITAN).consistency()['err_c']
        self.assertAlmostEqual(err, 0.0206, delta=0.003)             # 198.0 against the Huygens 194.0
        self.assertIsNone(medium.Medium().consistency()['err_c'])

    def test_temperature_changes_the_speed_in_iso_air(self):
        cold = medium.Medium({'model': 'iso9613', 'state': {'temperature_k': 273.15}})
        self.assertAlmostEqual(cold.c, 343.0 * (273.15 / 293.15) ** 0.5, places=6)

    def test_reynolds_number_of_a_twig(self):
        m = medium.Medium({'model': 'ideal_gas', 'gas': AIR})
        self.assertAlmostEqual(m.reynolds(8.0, 0.005), 2661.0, delta=30.0)
        with self.assertRaises(ValueError):
            medium.Medium({'model': 'iso9613'}).reynolds(1, 1)


class Absorption(unittest.TestCase):
    def test_the_general_law_reproduces_iso_9613_in_three_states(self):
        f = np.geomspace(100.0, 20000.0, 60)
        for t_k, rh in ((293.15, 50.0), (278.15, 80.0), (308.15, 20.0)):
            cl, rel = medium.iso_terms(t_k, rh, 101.325, c=343.0)
            m = medium.Medium({'model': 'ideal_gas', 'gas': AIR, 'state': {'temperature_k': t_k}, 'c_m_s': 343.0,
                               'classical': cl, 'relaxations': [{'f_hz': fr, 'mu_max': mu} for fr, mu in rel]})
            iso = airabs.alpha_db_per_m(f, t_k - 273.15, rh)
            self.assertLess(float(np.max(np.abs(m.alpha_db_per_m(f) - iso) / iso)), 1e-3, (t_k, rh))

    def test_iso_check_values(self):
        m = medium.Medium()
        a = m.alpha_db_per_m([1000.0, 10000.0]) * 1000.0
        self.assertAlmostEqual(a[0], 5.0, delta=1.0)
        self.assertAlmostEqual(a[1], 160.0, delta=15.0)

    def test_the_classical_term_from_gas_properties_is_close_to_the_standards(self):
        m = medium.Medium({'model': 'ideal_gas', 'gas': AIR, 'state': {'temperature_k': 293.15}})
        self.assertGreater(m.classical / 1.84e-11, 0.6)
        self.assertLess(m.classical / 1.84e-11, 1.0)

    def test_a_thin_atmosphere_absorbs_more_in_its_classical_term(self):
        earth = medium.Medium({'model': 'ideal_gas', 'gas': AIR})
        mars = medium.Medium(MARS)
        self.assertGreater(mars.alpha_db_per_m(1000.0), 2.0 * earth.alpha_db_per_m(1000.0))

    def test_a_relaxation_peaks_at_its_frequency_with_mu_per_wavelength(self):
        m = medium.Medium({'model': 'ideal_gas', 'gas': AIR, 'classical': 0.0, 'c_m_s': 340.0,
                           'relaxations': [{'f_hz': 1000.0, 'mu_max': 0.01}]})
        # absorption per wavelength: alpha * lambda = mu at f_r
        self.assertAlmostEqual(float(m.alpha_np_per_m(1000.0)) * 340.0 / 1000.0, 0.01, places=9)

    def test_absorb_matches_alpha_for_a_non_iso_medium(self):
        cl, rel = medium.iso_terms(293.15, 50.0, 101.325, c=343.0)
        m = medium.Medium({'model': 'ideal_gas', 'gas': AIR, 'c_m_s': 343.0, 'classical': cl,
                           'relaxations': [{'f_hz': fr, 'mu_max': mu} for fr, mu in rel]})
        x = np.random.default_rng(1).standard_normal(SR).astype(np.float32)
        y = m.absorb(x, 200.0, SR)
        X, Y = np.abs(np.fft.rfft(x)), np.abs(np.fft.rfft(y))
        db = 20 * np.log10(Y[9800:10200].mean() / X[9800:10200].mean())
        self.assertAlmostEqual(db, -float(m.alpha_db_per_m(10000.0)) * 200.0, delta=1.0)
        self.assertEqual(y.shape, x.shape)

    def test_iso_absorb_is_bit_identical_to_airabs(self):
        x = np.random.default_rng(2).standard_normal(SR).astype(np.float32)
        self.assertTrue(np.array_equal(medium.Medium().absorb(x, 50.0, SR), airabs.apply(x, 50.0, sr=SR)))

    def test_zero_distance_is_a_no_op(self):
        x = np.ones(100, np.float32)
        self.assertTrue(np.array_equal(medium.Medium(MARS).absorb(x, 0.0, SR), x))


class Interfaces(unittest.TestCase):
    def test_air_to_water_loses_about_30_db(self):
        water = medium.Medium({'model': 'liquid', 'c_m_s': 1482.0, 'rho_kg_m3': 998.0})
        self.assertAlmostEqual(medium.Medium().transmission_db(water), -29.5, delta=0.2)
        self.assertAlmostEqual(water.transmission_db(medium.Medium()), medium.Medium().transmission_db(water), places=9)

    def test_titan_air_to_a_methane_sea(self):
        sea = medium.Medium({'model': 'liquid', 'c_m_s': 1400.0, 'rho_kg_m3': 450.0})
        self.assertAlmostEqual(medium.Medium(TITAN).transmission_db(sea), -21.8, delta=0.3)

    def test_equal_media_transmit_everything(self):
        self.assertAlmostEqual(medium.Medium().transmission_db(medium.Medium()), 0.0, places=9)


class Boundaries(unittest.TestCase):
    def test_canopy_excess_comes_from_the_measured_table(self):
        m = medium.Medium({'model': 'iso9613', 'boundary': {'canopy': {'excess_db_per_m': [[500, 0.03], [8000, 0.5]]}}})
        self.assertAlmostEqual(float(m.canopy_excess_db(500.0, 10.0)), 0.3, places=9)
        self.assertGreater(float(m.canopy_excess_db(4000.0, 10.0)), float(m.canopy_excess_db(1000.0, 10.0)))
        self.assertEqual(float(medium.Medium().canopy_excess_db(4000.0, 10.0)), 0.0)

    def test_wind_profile_rises_with_height(self):
        m = medium.Medium({'model': 'iso9613', 'flow': {'u_ref_m_s': 4.0, 'z_ref_m': 10.0, 'profile': 'log'}})
        self.assertAlmostEqual(m.wind_speed(10.0), 4.0, places=6)
        self.assertLess(m.wind_speed(2.0), m.wind_speed(10.0))
        self.assertEqual(medium.Medium().wind_speed(5.0), 0.0)

    def test_doppler_scales_with_c(self):
        self.assertAlmostEqual(medium.Medium().doppler_scale(34.3), 0.1, places=6)
        self.assertGreater(medium.Medium(TITAN).doppler_scale(10.0), medium.Medium().doppler_scale(10.0))


class Schema(unittest.TestCase):
    def bad(self, cfg):
        return medium.problems(cfg)

    def test_unknown_keys_are_errors(self):
        self.assertTrue(any('unknown key "colour"' in p for p in self.bad({'model': 'iso9613', 'colour': 1})))
        self.assertTrue(any('unknown key' in p for p in self.bad({'model': 'iso9613', 'state': {'temp': 1}})))

    def test_out_of_range_is_refused_not_clamped(self):
        self.assertTrue(self.bad({'model': 'iso9613', 'state': {'temperature_k': -5}}))
        self.assertTrue(self.bad({'model': 'ideal_gas', 'gas': {'gamma': 3.0, 'viscosity_pa_s': 1e-5, 'prandtl': 0.7}}))
        with self.assertRaises(ValueError):
            medium.Medium({'model': 'iso9613', 'state': {'rh_percent': 150}})

    def test_a_liquid_needs_c_and_rho(self):
        self.assertEqual(len(self.bad({'model': 'liquid'})), 2)

    def test_auto_classical_needs_viscosity_and_prandtl(self):
        self.assertTrue(any('classical' in p for p in self.bad({'model': 'ideal_gas'})))
        self.assertEqual(self.bad({'model': 'ideal_gas', 'classical': 0.0}), [])

    def test_iso_computes_its_own_relaxations(self):
        self.assertTrue(self.bad({'model': 'iso9613', 'relaxations': [{'f_hz': 1000, 'mu_max': 0.1}]}))

    def test_a_relaxation_needs_both_numbers(self):
        self.assertTrue(self.bad({'model': 'ideal_gas', 'classical': 0, 'relaxations': [{'f_hz': 1000}]}))
        self.assertTrue(self.bad({'model': 'ideal_gas', 'classical': 0, 'relaxations': [{'f_hz': 1000, 'mu_max': 5}]}))

    def test_bad_model_and_non_dict(self):
        self.assertTrue(self.bad({'model': 'plasma'}))
        self.assertTrue(self.bad('air'))

    def test_a_canopy_table_must_rise_in_frequency(self):
        cfg = {'model': 'iso9613', 'boundary': {'canopy': {'excess_db_per_m': [[2000, 0.1], [500, 0.2]]}}}
        self.assertTrue(self.bad(cfg))

    def test_numbers_must_be_numbers(self):
        self.assertTrue(self.bad({'model': 'iso9613', 'state': {'temperature_k': True}}))
        self.assertTrue(self.bad({'model': 'iso9613', 'state': {'temperature_k': 'warm'}}))


class Active(unittest.TestCase):
    def test_use_scopes_the_active_medium(self):
        with medium.use(TITAN) as m:
            self.assertIs(medium.active(), m)
            self.assertAlmostEqual(medium.speed_of_sound(), 198.0, delta=1.0)
        self.assertEqual(medium.speed_of_sound(), 343.0)

    def test_use_restores_after_an_error(self):
        with self.assertRaises(RuntimeError):
            with medium.use(TITAN):
                raise RuntimeError('boom')
        self.assertEqual(medium.speed_of_sound(), 343.0)

    def test_from_score(self):
        self.assertEqual(medium.from_score({}).c, 343.0)
        self.assertAlmostEqual(medium.from_score({'medium': TITAN}).c, 198.0, delta=1.0)


if __name__ == '__main__':
    unittest.main()
