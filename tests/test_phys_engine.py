# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""The physical sound engine, behaviourally: a material changes what a sound is, not just its EQ.

Each test names the physical fact it holds the engine to (contact time falls with stiffness, a porous material eats the
top end, brittle fails in more and shorter cracks than fibrous, energy doubling is +3 dB). Numbers that are estimates
in the code are tested for their *direction and scaling*, not for a magic value, because the estimate is the thing
stage 1 research replaces.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import phys_core.calibrate as cal
import phys_core.excite as ex
import phys_core.fracture as fr
import phys_core.gait as gait
import phys_core.geometry as geo
import phys_core.materials as mat
import phys_core.propagate as prop
import phys_core.resonate as res
import phys_core.scene as scene

SR = 44100


def _peaks(y, f, lo, hi):
    band = (f >= lo) & (f < hi)
    return float(np.abs(y[band]).max())


class Materials(unittest.TestCase):
    def test_unknown_and_out_of_range_are_refused(self):
        self.assertTrue(mat.problems({'family': 'fibrous', 'density': 700, 'colour': 'red'}))
        self.assertTrue(mat.problems({'family': 'fibrous', 'density': -1}))
        self.assertTrue(mat.problems({'family': 'nonsense'}))
        self.assertEqual(mat.problems({'family': 'fibrous', 'density': 700}), [])

    def test_defaults_fill_in_and_a_preset_is_usable_by_name(self):
        m = mat.get({'family': 'metal'})
        self.assertEqual(m['density'], mat.DEFAULTS['density'])
        self.assertEqual(mat.get('glass')['family'], 'brittle')

    def test_a_damped_material_dies_faster_than_a_lossless_one(self):
        wood = mat.get({'family': 'fibrous', 'loss_factor': 0.02})
        glass = mat.get({'family': 'brittle', 'loss_factor': 0.0005})
        self.assertLess(mat.t60(440.0, wood), mat.t60(440.0, glass))

    def test_high_modes_die_before_the_first(self):
        t = mat.mode_t60(0.5, [1.0, 2.7, 5.4, 8.9])
        self.assertTrue(np.all(np.diff(t) < 0))


class Geometry(unittest.TestCase):
    def test_a_longer_bar_is_lower_and_a_declared_pitch_wins(self):
        oak = mat.get('oak')
        short = geo.first_mode('bar', oak, {'shape': 'bar', 'length_m': 0.5, 'thickness_m': 0.03})[0]
        long = geo.first_mode('bar', oak, {'shape': 'bar', 'length_m': 1.0, 'thickness_m': 0.03})[0]
        self.assertGreater(short, long)
        declared = geo.first_mode('bar', oak, {'shape': 'bar', 'length_m': 1.0, 'f1_hz': 220.0})
        self.assertEqual(declared, (220.0, 'declared'))

    def test_a_thicker_bar_is_higher(self):
        oak = mat.get('oak')
        thin = geo.first_mode('bar', oak, {'shape': 'bar', 'length_m': 1.0, 'thickness_m': 0.01})[0]
        thick = geo.first_mode('bar', oak, {'shape': 'bar', 'length_m': 1.0, 'thickness_m': 0.04})[0]
        self.assertGreater(thick, thin)

    def test_resolve_returns_a_modal_identity(self):
        f1, ratios, t60, m = geo.resolve({'material': 'oak', 'geometry': {'shape': 'bar', 'length_m': 1.0}}, {})
        self.assertGreater(f1, 0)
        self.assertEqual(len(ratios), 8)
        self.assertGreater(t60, 0)
        self.assertEqual(m['family'], 'fibrous')


class Resonators(unittest.TestCase):
    def test_the_modal_bank_rings_at_its_mode(self):
        x = np.zeros(SR, dtype=float)
        x[10] = 1.0
        y = res.modal(x, 500.0, [1.0, 2.0, 3.0], 1.0, SR)
        f = np.fft.rfftfreq(len(y), 1 / SR)
        Y = np.abs(np.fft.rfft(y))
        self.assertTrue(450 < f[np.argmax(Y)] < 560)

    def test_a_porous_material_eats_the_top_end_first(self):
        rng = np.random.default_rng(1)
        x = rng.standard_normal(SR)
        y = res.porous(x, sigma=30000, thickness_m=0.02, sr=SR)
        X, Y = np.abs(np.fft.rfft(x)), np.abs(np.fft.rfft(y))
        f = np.fft.rfftfreq(len(x), 1 / SR)
        low = Y[(f > 100) & (f < 300)].mean() / X[(f > 100) & (f < 300)].mean()
        high = Y[(f > 6000) & (f < 9000)].mean() / X[(f > 6000) & (f < 9000)].mean()
        self.assertLess(high, low)
        self.assertLess(high, 0.2)

    def test_a_bubble_rings_at_the_minnaert_frequency(self):
        y = res.bubble(1000.0, 0.2, 0.2, SR)
        f = np.fft.rfftfreq(len(y), 1 / SR)
        self.assertTrue(900 < f[np.argmax(np.abs(np.fft.rfft(y)))] < 1100)
        self.assertAlmostEqual(res.bubble_frequency(0.00326), 1000.0, delta=1.0)


class Excitation(unittest.TestCase):
    def test_a_harder_contact_is_shorter_and_a_faster_one_too(self):
        soft = ex.contact_time(1e6, 0.5, 1.0)
        hard = ex.contact_time(1e9, 0.5, 1.0)
        self.assertLess(hard, soft)
        self.assertLess(ex.contact_time(1e9, 0.5, 5.0), ex.contact_time(1e9, 0.5, 1.0))

    def test_energy_scales_with_the_square_of_velocity(self):
        self.assertAlmostEqual(ex.impact_energy(2.0, 3.0) / ex.impact_energy(2.0, 1.5), 4.0, places=6)

    def test_turbulence_has_the_minus_five_thirds_slope(self):
        z = ex.kaimal(SR * 40, SR, np.random.default_rng(3), corner_hz=0.1, intensity=0.4)
        f = np.fft.rfftfreq(len(z), 1 / SR)
        p = np.abs(np.fft.rfft(z - z.mean())) ** 2
        lo = p[(f > 1) & (f < 2)].mean()
        hi = p[(f > 10) & (f < 20)].mean()
        slope = np.log10(hi / lo) / np.log10(15.0 / 1.5)
        self.assertAlmostEqual(slope, -5.0 / 3.0, delta=0.4)

    def test_granular_contacts_arrive_like_a_poisson_process(self):
        times, sizes = ex.granular(10.0, np.random.default_rng(2), rate=100.0)
        gaps = np.diff(times)
        self.assertAlmostEqual(float(gaps.mean()), 0.01, delta=0.002)
        self.assertGreater(float(sizes.std()), 0.05)          # not every grain identical

    def test_stick_slip_runs_at_its_slip_frequency(self):
        x = ex.stick_slip(1.0, SR, np.random.default_rng(4), f_slip=40.0, depth=1.0, jitter=0.0)
        onsets = np.flatnonzero((x[1:] > 0.1) & (x[:-1] <= 0.1))
        self.assertAlmostEqual(len(onsets), 40, delta=6)


class Failure(unittest.TestCase):
    def test_brittle_releases_more_cracks_in_less_time_than_fibrous(self):
        glass, oak = mat.get('glass'), mat.get('oak')
        g = fr.crack_train(glass, 2.0, np.random.default_rng(1))
        w = fr.crack_train(oak, 2.0, np.random.default_rng(1))
        self.assertGreater(len(g), len(w))
        self.assertLess(max(t for t, _, _ in g), max(t for t, _, _ in w))

    def test_a_brittle_object_breaks_into_more_pieces(self):
        self.assertGreater(len(fr.fragments(mat.get('glass'), 2.0, np.random.default_rng(1))),
                           len(fr.fragments(mat.get('oak'), 2.0, np.random.default_rng(1))))

    def test_released_energy_scales_with_the_square_of_velocity(self):
        self.assertAlmostEqual(fr.released_energy(1.0, 4.0) / fr.released_energy(1.0, 2.0), 4.0, places=6)


class Gait(unittest.TestCase):
    def test_feet_alternate_and_a_run_lands_on_the_forefoot(self):
        steps = gait.steps(3.0, 112.0, np.random.default_rng(1))
        self.assertGreater(len(steps), 3)
        self.assertNotEqual(steps[0]['foot'], steps[1]['foot'])
        run = gait.steps(3.0, 170.0, np.random.default_rng(1))
        self.assertTrue(all(s['phase'] == 'forefoot' for s in run))
        self.assertLess(run[0]['contact_s'], steps[0]['contact_s'])

    def test_faster_cadence_means_more_contacts(self):
        self.assertGreater(len(gait.steps(5.0, 170.0, np.random.default_rng(0))),
                           len(gait.steps(5.0, 100.0, np.random.default_rng(0))))


class Calibration(unittest.TestCase):
    def test_four_times_the_energy_is_six_db_louder(self):
        quiet, _ = cal.apply(np.ones(100) * cal.amplitude(1.0) * 0.1)
        loud, _ = cal.apply(np.ones(100) * cal.amplitude(4.0) * 0.1)
        self.assertAlmostEqual(20 * np.log10(loud[0] / quiet[0]), 6.02, delta=0.05)

    def test_energy_mode_keeps_intensity_and_peak_mode_destroys_it(self):
        a, _ = cal.apply(np.linspace(0.01, 0.02, 100), {'normalize': 'energy'})
        b, _ = cal.apply(np.linspace(0.02, 0.04, 100), {'normalize': 'energy'})
        self.assertAlmostEqual(float(np.abs(b).max() / np.abs(a).max()), 2.0, delta=0.02)
        c, rep = cal.apply(np.linspace(0.02, 0.04, 100), {'normalize': 'peak'})
        self.assertAlmostEqual(float(np.abs(c).max()), cal.PEAK_CEILING, places=6)
        self.assertEqual(rep['normalize'], 'peak')


class Propagation(unittest.TestCase):
    def test_spreading_is_inverse_distance(self):
        self.assertAlmostEqual(prop.distance_gain(8.0), 0.125, places=4)

    def test_air_and_canopy_darken_the_far_sound(self):
        rng = np.random.default_rng(3)
        x = rng.standard_normal(SR)
        far = prop.apply(x, SR, {'distance_m': 60.0, 'atmosphere': {'temp_c': 20, 'rh': 50}})
        thick = prop.apply(x, SR, {'distance_m': 60.0, 'atmosphere': {'temp_c': 20, 'rh': 50}, 'canopy_density': 1.0})
        def hf(y):
            Y = np.abs(np.fft.rfft(y))
            f = np.fft.rfftfreq(len(y), 1 / SR)
            return float(Y[(f > 5000) & (f < 9000)].mean())
        self.assertLess(hf(thick), hf(far))


def _scene(material_family, brittle=None):
    m = {'brittle': dict(family='brittle', density=2500, young_modulus_gpa=70, loss_factor=0.001, toughness_kpa=4000),
         'fibrous': dict(family='fibrous', density=700, young_modulus_gpa=11, loss_factor=0.02, toughness_kpa=900)}
    act = {"at": 0.1, "interaction": "fracture", "target": "obj", "mass_kg": 1.0, "velocity_m_s": 2.0}
    if brittle is not None:
        act['brittle'] = brittle
    return {"seconds": 2.0, "materials": {"m": m[material_family]},
            "objects": {"obj": {"material": "m", "geometry": {"shape": "bar", "length_m": 0.8}, "modes": 10}},
            "timeline": [act], "calibration": {"normalize": "energy", "level_db": -6}}


class Scenes(unittest.TestCase):
    def test_a_scene_is_deterministic_and_the_seed_matters(self):
        a, _ = scene.render_scene(_scene('fibrous'), SR, 7)
        b, _ = scene.render_scene(_scene('fibrous'), SR, 7)
        c, _ = scene.render_scene(_scene('fibrous'), SR, 8)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))

    def test_glass_and_wood_are_not_the_same_break(self):
        glass, _ = scene.render_scene(_scene('brittle'), SR, 3)
        wood, _ = scene.render_scene(_scene('fibrous'), SR, 3)
        def hf_share(x):
            X = np.abs(np.fft.rfft(x)) ** 2
            f = np.fft.rfftfreq(len(x), 1 / SR)
            return float(X[f > 3000].sum() / (X.sum() + 1e-12))
        self.assertGreater(hf_share(glass), hf_share(wood))

    def test_a_then_edge_changes_the_result(self):
        base = _scene('fibrous')
        with_child = _scene('fibrous')
        with_child['timeline'][0]['then'] = [{"offset": 0.5, "interaction": "impact", "target": "obj",
                                              "velocity_m_s": 1.0, "mass_kg": 0.5}]
        a, _ = scene.render_scene(base, SR, 3)
        b, _ = scene.render_scene(with_child, SR, 3)
        self.assertFalse(np.array_equal(a, b))

    def test_a_walk_on_gravel_renders(self):
        s = {"seconds": 2.0,
             "materials": {"gravel": dict(family='granular', density=1800, young_modulus_gpa=30, loss_factor=0.08)},
             "objects": {"path": {"material": "gravel", "geometry": {"shape": "plate", "width_m": 0.4}, "modes": 6}},
             "timeline": [{"at": 0.0, "for": 1.8, "interaction": "gait", "target": "path", "cadence_spm": 112.0}]}
        x, _ = scene.render_scene(s, SR, 5)
        self.assertTrue(np.isfinite(x).all())
        self.assertGreater(float(np.abs(x).max()), 1e-3)


class EngineSplit(unittest.TestCase):
    """The new engines must not change what the old entry points produce."""

    def test_sfx_engine_matches_sfx_for_a_legacy_preset(self):
        import sfx
        import sfx_engine.oneshot as one
        a, src_a, _ = one.make('impact', 1.0, SR, 3)
        b, src_b, _ = sfx.make('impact', 1.0, SR, 3)
        self.assertTrue(np.array_equal(a, b))

    def test_env_engine_matches_environment_for_a_shipped_preset(self):
        import environment
        import env_engine.render as er
        a = er.render_preset('amazon_rainforest', duration_s=2.0, sr=SR, seed=11)
        b = environment.render_environment_preset('amazon_rainforest', duration_s=2.0, sr=SR, seed=11)
        self.assertTrue(np.array_equal(a, b))


if __name__ == '__main__':
    unittest.main()
