"""M9: the migration assistant carries what means the same thing, lists the rest with a reason, and never claims the sound is kept."""
import json
import os
import subprocess
import sys
import unittest

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import env_migrate  # noqa: E402
import environment  # noqa: E402
import presets  # noqa: E402
from biome import engine, schema  # noqa: E402

LEGACY = ('amazon_rainforest', 'savanna_dusk', 'wetland_night', 'woodland_dawn')


def lyr(**kw):
    d = dict(name='x', kind='bed')
    d.update(kw)
    return d


class Shipped(unittest.TestCase):
    def test_every_shipped_layers_preset_migrates_to_a_valid_skeleton_that_renders(self):
        for n in LEGACY:
            res = env_migrate.plan(presets.find_environment(n))
            self.assertEqual(schema.problems(res['biome']), [], n)
            self.assertTrue(res['mapped'], n)
            y = engine.Biome(res['biome'], seed=3).render(3.0)
            self.assertTrue(np.isfinite(y).all() and float(np.abs(y).max()) > 0.0, n)

    def test_what_has_no_equivalent_is_listed_with_a_reason(self):
        res = env_migrate.plan(presets.find_environment('amazon_rainforest'))
        names = dict(res['unmapped'])
        self.assertIn('drips (impulse_cluster)', names)
        self.assertIn('particulate_impacts', names['drips (impulse_cluster)'])
        wet = dict(env_migrate.plan(presets.find_environment('wetland_night'))['unmapped'])
        self.assertIn('water (water_flow)', wet)

    def test_the_blending_and_the_gain_are_reported_not_carried(self):
        res = env_migrate.plan(presets.find_environment('amazon_rainforest'))
        text = ' '.join(res['notes'])
        self.assertIn('blending', text)
        self.assertIn('gain_db is not carried', text)

    def test_every_migrated_block_is_an_estimate_naming_its_layer(self):
        res = env_migrate.plan(presets.find_environment('amazon_rainforest'))
        for blk in res['biome']['generators'] + res['biome']['fauna']:
            self.assertTrue(blk['sources'][0].startswith('ESTIMATE: migrated from layer'), blk['name'])

    def test_the_layer_engine_is_left_alone(self):
        before = environment.render_environment_preset('amazon_rainforest', duration_s=2.0, sr=44100, seed=1)
        env_migrate.plan(presets.find_environment('amazon_rainforest'))
        self.assertTrue(np.array_equal(before, environment.render_environment_preset('amazon_rainforest', duration_s=2.0, sr=44100, seed=1)))


class Mapping(unittest.TestCase):
    def one(self, layer, **top):
        return env_migrate.plan(dict(top, name='t', character='c', layers=[layer]))['biome']

    def test_physical_rain_keeps_its_rate_and_surface(self):
        b = self.one(lyr(primitive='rain_physical', rate_mm_h=22.0, surface='water', bubble_prob=0.4))
        g = b['generators'][0]
        self.assertEqual((g['kind'], g['population']['rate_mm_h'], g['surface']['kind']), ('particulate_impacts', 22.0, 'liquid'))
        self.assertEqual(g['bubbles']['p_by_size'], [[0.5, 0.4], [6.0, 0.4]])
        leaf = self.one(lyr(primitive='rain_physical', rate_mm_h=5.0, surface='leaf'))['generators'][0]
        self.assertEqual((leaf['surface']['kind'], leaf['surface']['material']), ('solid', 'leaf_green'))

    def test_crickets_carry_the_syllable_timing_and_dolbears_law(self):
        a = self.one(lyr(primitive='cricket_chorus', voices=7, carrier_hz=2500.0, syllables=6, syl_ms=15.0, gap_ms=5.0, temp_c=20.0))['fauna'][0]
        self.assertEqual(a['source']['kind'], 'stridulation')
        self.assertEqual(a['individuals'], 7)
        self.assertAlmostEqual(a['source']['tooth_hz'], 50.0, places=6)               # a syllable and its gap: 20 ms
        self.assertEqual(a['source']['plate_hz'], 2500.0)
        self.assertAlmostEqual(a['rate_per_k'], 1.8 / (68.0 - 40.0), places=3)         # d ln(rate) / dT from (T_F - 40) / 15
        self.assertAlmostEqual(a['temp_ref_k'], 293.15, places=6)
        self.assertEqual(a['source']['train']['chirp_ms'], 120.0)

    def test_birds_keep_their_band_as_a_niche(self):
        a = self.one(lyr(primitive='bird_chorus', species=4, f_lo=1500.0, f_hi=7500.0, event_rate=0.5))['fauna'][0]
        self.assertEqual(a['niche']['band_hz'], [1500.0, 7500.0])
        self.assertEqual(a['source']['kind'], 'dual_syrinx')
        self.assertAlmostEqual(a['bouts_per_min'], 0.5 * 4 * 60.0)

    def test_a_calls_preset_stays_a_calls_preset(self):
        a = self.one(lyr(primitive='animal_call', call='owl_hoot', bouts_per_min=2.5, individuals=2))['fauna'][0]
        self.assertEqual((a['call'], a['bouts_per_min'], a['individuals']), ('owl_hoot', 2.5, 2))
        with self.assertRaises(ValueError):
            self.one(lyr(primitive='animal_call'))

    def test_wind_keeps_its_band(self):
        g = self.one(lyr(primitive='noise_bed', low_hz=200.0, high_hz=3000.0))['generators'][0]
        self.assertEqual((g['kind'], g['broadband']['band_hz']), ('turbulence', [200.0, 3000.0]))

    def test_a_point_layer_stays_a_point_and_a_wide_one_becomes_a_field(self):
        point = self.one(lyr(primitive='noise_bed', spatial={'azimuth': -40, 'distance': 8}))['generators'][0]
        self.assertEqual(point['spatial'], {'azimuth': -40.0, 'distance': 8.0})
        wide = self.one(lyr(primitive='noise_bed'))['generators'][0]
        self.assertTrue(wide['spatial']['field'])
        panned = self.one(lyr(primitive='noise_bed', pan=1.0))['generators'][0]
        self.assertEqual(panned['spatial']['azimuth'], 90.0)

    def test_the_atmosphere_becomes_the_medium(self):
        b = self.one(lyr(primitive='noise_bed'), atmosphere={'temp_c': 30.0, 'rh': 80.0})
        self.assertAlmostEqual(b['medium']['state']['temperature_k'], 303.15)
        self.assertEqual(b['medium']['state']['rh_percent'], 80.0)

    def test_nothing_migratable_is_an_error_with_the_reasons(self):
        with self.assertRaises(ValueError) as cm:
            self.one(lyr(primitive='impulse_cluster'))
        self.assertIn('particulate_impacts', str(cm.exception))

    def test_a_scene_or_a_biome_is_not_migrated(self):
        for bad in ({'scene': {'seconds': 1}}, {'schema': 'biome/1'}, 'x', {'layers': 'no'}):
            with self.assertRaises(ValueError):
                env_migrate.plan(bad)

    def test_an_unknown_primitive_is_listed(self):
        res = env_migrate.plan({'layers': [lyr(primitive='rain_physical', rate_mm_h=5.0, surface='water'), lyr(name='odd', primitive='nonsense')]})
        self.assertEqual([n for n, _ in res['unmapped']], ['odd (None)'])


class Command(unittest.TestCase):
    def test_the_command_prints_the_report_and_writes_a_valid_skeleton(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'bed.json')
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'env_migrate.py'), 'savanna_dusk', '--out', out], capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('migrated: 3 layer(s)', r.stdout)
            self.assertEqual(schema.problems(json.load(open(out))), [])
            bad = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'env_migrate.py'), 'no_such_place'], capture_output=True, text=True, timeout=120)
            self.assertNotEqual(bad.returncode, 0)


if __name__ == '__main__':
    unittest.main()
