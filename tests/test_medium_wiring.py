"""M2: the medium reaches every module that used to hard-code 343 m/s or ISO air. Earth stays byte-identical
(tests/test_biome_baseline.py); a different medium changes tube formants, Doppler, room delays, barrier diffraction,
absorption and near-field gains together."""
import ast
import os
import sys
import unittest

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airabs  # noqa: E402
import biome_baseline as bb  # noqa: E402
from phys_core import medium, propagate  # noqa: E402

SR = 44100
SLOW = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.02897, gamma=1.4), 'c_m_s': 171.5, 'classical': 0.0}   # half of Earth's c
TITAN = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.0279, gamma=1.40, viscosity_pa_s=6.0e-6, prandtl=0.71),
         'state': {'temperature_k': 94, 'pressure_pa': 146700}}

# modules that describe where the sound is RECORDED read the medium; these describe where it is HEARD (a head model, a
# loudspeaker room) and keep the Earth speed on purpose
SCENE_MODULES = ('env_engine/calls.py', 'phys_core/propagate.py', 'phys_core/resonate.py', 'environment.py', 'airabs.py',
                 'spatial_engine/hoa.py', 'spatial_engine/nfc.py', 'spatial_hrtf/room.py')
PLAYBACK_MODULES = ('spatial_engine/lfe_qa.py', 'spatial_hrtf/binaural.py', 'spatial_hrtf/sph.py', 'spatial.py')


def literals(path, values=(343, 343.0)):
    tree = ast.parse(open(os.path.join(ROOT, 'scripts', path), encoding='utf-8').read())
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool) and n.value in values]


class NoHardCodedSpeed(unittest.TestCase):
    def test_scene_modules_have_no_343_literal(self):
        found = {m: literals(m) for m in SCENE_MODULES}
        self.assertEqual({m: v for m, v in found.items() if v}, {})

    def test_the_scan_can_fail(self):
        self.assertTrue(literals('phys_core/medium.py'))              # EARTH_C lives here, and only here

    def test_playback_modules_are_the_declared_exceptions(self):
        for m in PLAYBACK_MODULES:
            self.assertTrue(literals(m), f'{m} no longer holds a 343 literal: move it to SCENE_MODULES')


class Earth(unittest.TestCase):
    def test_every_shipped_preset_is_byte_identical(self):
        self.assertEqual([r for r in bb.verify() if r[0] != 'PASS'], [])


class Tubes(unittest.TestCase):
    def test_formants_follow_c(self):
        from env_engine import calls
        earth = calls.tube_formants(17.0, SR)
        with medium.use(SLOW):
            slow = calls.tube_formants(17.0, SR)
        for a, b in zip(earth, slow):
            self.assertAlmostEqual(b / a, 0.5, places=3)
        self.assertAlmostEqual(earth[0], 343.0 / (4 * 0.17), places=6)

    def test_an_explicit_c_wins(self):
        from env_engine import calls
        self.assertAlmostEqual(calls.tube_formants(17.0, SR, c=200.0)[0], 200.0 / (4 * 0.17), places=6)


class Barriers(unittest.TestCase):
    def test_fresnel_number_doubles_when_c_halves(self):
        n0 = float(propagate.fresnel_number(0.3, 1000.0))
        with medium.use(SLOW):
            n1 = float(propagate.fresnel_number(0.3, 1000.0))
        self.assertAlmostEqual(n1 / n0, 2.0, places=3)

    def test_the_maekawa_loss_grows_in_a_slower_medium(self):
        a = float(propagate.maekawa_il(0.3, 1000.0))
        with medium.use(SLOW):
            b = float(propagate.maekawa_il(0.3, 1000.0))
        self.assertGreater(b, a)


class Absorption(unittest.TestCase):
    def test_the_air_filter_follows_the_active_medium(self):
        x = np.random.default_rng(1).standard_normal(SR).astype(np.float32)
        with medium.use(TITAN) as m:
            y = airabs.apply(x, 100.0, sr=SR)
            self.assertTrue(np.array_equal(y, m.absorb(x, 100.0, SR)))
        self.assertTrue(np.array_equal(airabs.apply(x, 100.0, sr=SR), airabs.iso_apply(x, 100.0, sr=SR)))

    def test_earth_air_settings_on_another_medium_are_an_error(self):
        with medium.use(TITAN):
            with self.assertRaises(ValueError):
                airabs.apply(np.zeros(8, np.float32), 10.0, temp_c=20.0, sr=SR)
            with self.assertRaises(ValueError):
                airabs.alpha_db_per_m(1000.0, rh=50.0)

    def test_iso_medium_state_is_the_default_for_the_air_filter(self):
        hot = {'model': 'iso9613', 'state': {'temperature_k': 308.15, 'rh_percent': 20.0}}
        with medium.use(hot):
            a = airabs.alpha_db_per_m(8000.0)
        self.assertAlmostEqual(float(a), float(airabs.iso_alpha_db_per_m(8000.0, 35.0, 20.0)), places=9)
        self.assertNotAlmostEqual(float(a), float(airabs.iso_alpha_db_per_m(8000.0, 20.0, 50.0)), places=3)

    def test_an_explicit_state_still_overrides_earth_air(self):
        self.assertAlmostEqual(float(airabs.alpha_db_per_m(8000.0, 35.0, 20.0)), float(airabs.iso_alpha_db_per_m(8000.0, 35.0, 20.0)), places=12)

    def test_propagate_air_uses_the_medium(self):
        x = np.random.default_rng(2).standard_normal(SR)
        with medium.use(TITAN) as m:
            y = propagate.air(x, SR, 60.0)
        self.assertTrue(np.allclose(y, m.absorb(x, 59.0, SR), atol=1e-5))


class Rooms(unittest.TestCase):
    BOX = dict(width_m=10.0, depth_m=14.0, height_m=6.0, listener=dict(x=5.0, y=4.0, z=1.5),
               materials=dict(floor='wood', ceiling='plaster', walls='plaster'), material_set='room_materials',
               max_order=2, max_taps=8, min_level_db=-30.0)

    def test_reflection_delays_double_when_c_halves(self):
        from spatial_hrtf import room
        t0 = room.taps(self.BOX, 0.0, 0.0, 3.0)
        with medium.use(SLOW):
            t1 = room.taps(self.BOX, 0.0, 0.0, 3.0)
        d0, d1 = [t['delay_ms'] for t in t0], [t['delay_ms'] for t in t1]
        self.assertTrue(d0)
        for a, b in zip(d0, d1):
            self.assertAlmostEqual(b / a, 2.0, places=3)

    def test_the_late_field_rings_longer_when_c_is_lower(self):
        from spatial_hrtf import room
        _, t_earth = room.eyring_rt60(self.BOX)
        with medium.use(SLOW):
            _, t_slow = room.eyring_rt60(self.BOX)
        self.assertTrue(np.all(t_slow > t_earth))


class Bus(unittest.TestCase):
    def test_the_bus_reads_the_score_medium_and_makes_it_active_for_the_field(self):
        from spatial_engine import hoa

        class Probe(hoa.HoaBus):
            def _field(self):
                return medium.speed_of_sound()
        self.assertEqual(Probe(score={}).field(), 343.0)
        self.assertAlmostEqual(Probe(score={'medium': TITAN}).field(), 198.0, delta=1.0)
        self.assertEqual(medium.speed_of_sound(), 343.0)               # and it is restored

    def test_the_bus_medium_is_earth_without_a_declaration(self):
        from spatial_engine import hoa
        self.assertEqual(hoa.HoaBus(score={}).medium.c, 343.0)


class NearField(unittest.TestCase):
    def test_nfc_gains_depend_on_c(self):
        from spatial_engine import nfc
        f = np.array([100.0, 400.0])
        g0 = nfc.order_gains(f, 3, 0.4, 1.0)
        with medium.use(SLOW):
            g1 = nfc.order_gains(f, 3, 0.4, 1.0)
        self.assertFalse(np.allclose(g0, g1))


if __name__ == '__main__':
    unittest.main()
