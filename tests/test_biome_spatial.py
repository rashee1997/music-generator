"""M8: a biome on a bus that places sources itself. Emitters and their places, power, interface loss, independence, the registry
that render_natural fills, the level hand-over of the mixer, and decoding to an ambisonic field and a loudspeaker layout."""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import mix_context  # noqa: E402
import mix_schema  # noqa: E402
import mixer  # noqa: E402
import presets  # noqa: E402
from biome import engine, schema, spatial_coupling_schema as scs  # noqa: E402
from biome import spatial as bspatial  # noqa: E402
from phys_core import medium  # noqa: E402
from spatial_engine import config, hoa, pan  # noqa: E402

SR = 44100
AIR = {'model': 'iso9613', 'gas': dict(molar_mass_kg_mol=0.02897, gamma=1.4, viscosity_pa_s=1.81e-5, prandtl=0.71), 'state': {'temperature_k': 293.15},
       'sources': ['test']}
WATER = {'model': 'liquid', 'c_m_s': 1482.0, 'rho_kg_m3': 998.0, 'gas': {'gamma': 1.4}, 'state': {'pressure_pa': 101325.0}, 'sources': ['test']}
IMM = dict(mix_schema.DEFAULTS['immersive'], enabled=True, engine='hoa_bus')


def rain(**sp):
    return dict(name='rain', kind='particulate_impacts', population=dict(kind='rain', rate_mm_h=15.0, cd=1.1), sources=['test'],
                surface=dict(kind='solid', material='oak', area_m2=20.0, patches=2), spatial=dict(dict(field=True, distance=3.0), **sp))


def wind(name='wind', **sp):
    return dict(name=name, kind='turbulence', obstacles=dict(d_m=dict(dist='fixed', value=0.005), frontal_area_m2=10.0, oscillators=1), sources=['test'],
                flow=dict(u_m_s=8.0, intensity=0.0), broadband=dict(share=1.0, band_hz=[150, 12000]), spatial=dict(sp))


def animal(name='tiger', **pos):
    return dict(name=name, power_w=1e-3, bouts_per_min=60.0, first_s=0.1, sources=['test'], source=dict(kind='dual_syrinx', saturation=0.0, harmonics=1),
                elements=dict(c={'f_left': 600.0, 'ms': [700, 800]}), position=dict(dict(azimuth=0.0, distance=10.0), **pos))


def preset(generators, fauna=(), coupling=None, media=None):
    p = {'schema': 'biome/1', 'name': 'bed1', 'character': 'a test place for the spatial hand-over', 'generators': list(generators), 'fauna': list(fauna)}
    if media:
        p['media'] = media
    else:
        p['medium'] = AIR
    if coupling is not None:
        p['spatial_coupling'] = coupling
    return p


def rms(y):
    return float(np.sqrt(np.mean(np.asarray(y, dtype=np.float64) ** 2)))


def decode(emitters, layout='itu_bs2051_system_j', order=5):
    """Place mono emitters on an ambisonic bus and decode to a loudspeaker layout: ({channel: power}, speaker list)."""
    spk = config.speakers(layout)
    bus = hoa.HoaBus(SR, order, 'speakers', dict(decoder='allrad2'), {}, speakers=spk)
    for name, mono, place in emitters:
        bus.add(name, mono, dict(role='melody', spatial=dict(place, widen=0.0)))
    out, _, _ = bus.field()
    return np.mean(np.asarray(out, dtype=np.float64) ** 2, axis=0), spk


def direction(power, spk):
    v = sum(p * np.asarray(s['vector'], dtype=float) for p, s in zip(power, spk))
    return v / max(float(power.sum()), 1e-30)


def angle_deg(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return math.degrees(math.acos(float(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30), -1, 1))))


class Emitters(unittest.TestCase):
    def test_a_field_is_a_ring_of_independent_emitters(self):
        b = engine.Biome(preset([rain(elevation=30.0)], coupling={'field': {'emitters': 12}}), seed=3, hoa=True)
        pl = b.emitter_specs()
        self.assertEqual(list(pl), [f'rain/e{i}' for i in range(12)])
        az = [pl[f'rain/e{i}']['azimuth'] for i in range(12)]
        steps = [(b_ - a_) % 360.0 for a_, b_ in zip(az, az[1:] + az[:1])]
        self.assertTrue(all(abs(s - 30.0) < 1e-6 for s in steps))
        self.assertTrue(all(p['elevation'] == 30.0 and p['distance'] == 3.0 for p in pl.values()))

    def test_elevations_cycle_round_the_ring(self):
        b = engine.Biome(preset([rain(elevations=[0.0, 40.0])], coupling={'field': {'emitters': 4}}), seed=3, hoa=True)
        self.assertEqual([p['elevation'] for p in b.emitter_specs().values()], [0.0, 40.0, 0.0, 40.0])

    def test_the_stereo_hand_over_keeps_its_two_emitters(self):
        self.assertEqual(engine.Biome(preset([rain()], coupling={'field': {'emitters': 12}}), seed=3).report()[0]['emitters'], 2)
        self.assertEqual(engine.Biome(preset([rain(emitters=5)]), seed=3).report()[0]['emitters'], 5)
        self.assertEqual(engine.Biome(preset([rain()]), seed=3, hoa=True).report()[0]['emitters'], 12)

    def test_a_point_source_and_an_animal_keep_their_places_and_trajectories(self):
        keys = {'keyframes': [dict(t_s=0.0, azimuth=-40.0), dict(t_s=1.0, azimuth=60.0)]}
        b = engine.Biome(preset([wind(azimuth=-70.0, elevation=5.0, distance=18.0)], [animal(azimuth=110.0, elevation=12.0, trajectory=keys)]), seed=3, hoa=True)
        pl = b.emitter_specs()
        self.assertEqual(pl['wind']['azimuth'], -70.0)
        self.assertEqual((pl['wind']['elevation'], pl['wind']['distance']), (5.0, 18.0))
        self.assertEqual(pl['tiger']['azimuth'], 110.0)
        self.assertEqual(pl['tiger']['trajectory'], keys)

    def test_the_emitters_carry_the_power_of_the_stereo_hand_over(self):
        p = preset([rain(distance=1.0)])
        st = engine.Biome(p, seed=3).render(6.0).astype(np.float64)
        parts = engine.Biome(p, seed=3, hoa=True).render_emitters(6.0)
        total = sum(rms(v) ** 2 for v in parts.values())
        self.assertAlmostEqual(total, rms(st) ** 2 * 2.0, delta=0.15 * total)        # rms of a stereo array is per channel: two channels

    def test_the_emitters_are_uncorrelated(self):
        parts = engine.Biome(preset([wind(field=True, distance=3.0)]), seed=3, hoa=True).render_emitters(4.0)
        names = list(parts)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                self.assertLess(abs(float(np.corrcoef(parts[names[i]], parts[names[j]])[0, 1])), 0.1, (names[i], names[j]))

    def test_an_animal_in_the_sea_arrives_reduced_by_the_interface(self):
        loud = animal('whale', azimuth=0.0, distance=1.0)
        a = engine.Biome(preset([wind()], [loud], media={'air': AIR, 'sea': WATER}), seed=3, hoa=True).render_emitters(3.0)['whale']
        b = engine.Biome(preset([wind()], [dict(loud, medium='sea')], media={'air': AIR, 'sea': WATER}), seed=3, hoa=True).render_emitters(3.0)['whale']
        sea, air = medium.Medium(WATER), medium.Medium(AIR)
        want = 10 * math.log10(sea.z / air.z) + sea.transmission_db(air)
        self.assertAlmostEqual(20 * math.log10(rms(b) / rms(a)), want, delta=1.5)

    def test_spreading_is_applied_here_and_absorption_is_the_buss(self):
        near = engine.Biome(preset([wind(azimuth=0.0, distance=2.0)]), seed=3, hoa=True).render_emitters(2.0)['wind']
        far = engine.Biome(preset([wind(azimuth=0.0, distance=8.0)]), seed=3, hoa=True).render_emitters(2.0)['wind']
        self.assertAlmostEqual(20 * math.log10(rms(near) / rms(far)), 12.04, delta=0.2)            # 1/r, and nothing else

    def test_the_planner_still_decides_the_animal_calls_on_the_emitter_path(self):
        p = preset([wind()], [animal()])
        p['ecology'] = {'rules': []}
        b = engine.Biome(p, seed=3, hoa=True)
        b.render_emitters(5.0)
        self.assertTrue(b.ecology_report()['bouts']['tiger/0'])


class Schema(unittest.TestCase):
    def test_a_valid_coupling_is_clean(self):
        self.assertEqual(schema.problems(preset([rain()], coupling={'field': {'kind': 'diffuse', 'emitters': 12, 'order': 5, 'correlation_target': 0.15},
                                                                     'room': {'space': 'forest_canopy'}, 'decode_hint': ['stereo', 'immersive_7_1']})), [])

    def test_bad_values_and_names_are_errors(self):
        for bad in ({'colour': 1}, {'field': {'emitters': 1}}, {'field': {'emitters': 99}}, {'field': {'emitters': 2.5}}, {'field': {'kind': 'point'}},
                    {'field': {'order': 6}}, {'field': {'correlation_target': 2}}, {'room': {'space': 'nope'}}, {'room': {'size': 1}}, {'decode_hint': [3]},
                    {'field': 'wide'}):
            self.assertTrue(schema.problems(preset([rain()], coupling=bad)), bad)

    def test_a_spatial_block_is_validated(self):
        for bad in (dict(colour=1), dict(elevations=[]), dict(elevations=[95]), dict(trajectory='left')):
            self.assertTrue(schema.problems(preset([rain(**bad)])), bad)

    def test_every_number_has_a_unit_and_a_doc(self):
        for k, (d, lo, hi, unit, doc) in scs.NUMBERS.items():
            self.assertTrue(lo <= d <= hi and unit and doc, k)


class Decoded(unittest.TestCase):
    def test_an_animal_is_heard_from_its_azimuth_and_elevation(self):
        for az, el in ((60.0, 0.0), (-120.0, 0.0), (30.0, 40.0)):
            b = engine.Biome(preset([wind(azimuth=0.0, distance=2.0)], [animal(azimuth=az, elevation=el, distance=2.0)]), seed=3, hoa=True)
            pl, parts = b.emitter_specs(), b.render_emitters(3.0)
            power, spk = decode([('tiger', parts['tiger'], pl['tiger'])])
            self.assertLess(angle_deg(direction(power, spk), pan.vector(az, el)), 20.0, (az, el))

    def test_a_field_is_all_round_and_an_animal_is_not(self):
        b = engine.Biome(preset([wind(field=True, distance=3.0, elevation=0.0)], [animal(azimuth=60.0, distance=3.0)]), seed=3, hoa=True)
        parts, pl = b.render_emitters(3.0), b.emitter_specs()
        field = [(k, v, pl[k]) for k, v in parts.items() if k.startswith('wind')]
        power, spk = decode(field)
        self.assertLess(np.linalg.norm(direction(power, spk)), 0.35)
        power, spk = decode([('tiger', parts['tiger'], pl['tiger'])])
        self.assertGreater(np.linalg.norm(direction(power, spk)), 0.6)

    def test_overhead_rain_has_its_energy_in_the_height_speakers(self):
        b = engine.Biome(preset([rain(elevation=50.0)], coupling={'field': {'emitters': 8}}), seed=3, hoa=True)
        parts, pl = b.render_emitters(3.0), b.emitter_specs()
        power, spk = decode([(k, v, pl[k]) for k, v in parts.items()])
        high = sum(p for p, s in zip(power, spk) if s['elevation'] > 20.0)
        low = sum(p for p, s in zip(power, spk) if s['elevation'] <= 20.0)
        self.assertGreater(high, low)

    def test_a_trajectory_moves_the_animal_across_the_layout(self):
        keys = {'keyframes': [dict(t_s=0.0, azimuth=-50.0), dict(t_s=3.0, azimuth=60.0)]}
        b = engine.Biome(preset([wind(azimuth=0.0, distance=2.0)], [animal(azimuth=0.0, distance=2.0, trajectory=keys)]), seed=3, hoa=True)
        mono, place = b.render_emitters(3.0)['tiger'], b.emitter_specs()['tiger']
        spk = config.speakers('itu_bs2051_system_j')
        bus = hoa.HoaBus(SR, 5, 'speakers', dict(decoder='allrad2'), {}, speakers=spk)
        bus.add('tiger', mono, dict(role='melody', spatial=dict(place, widen=0.0)))
        out, _, _ = bus.field()
        right = pan.vector(90.0, 0.0)
        side = lambda seg: float(direction(np.mean(np.asarray(seg, dtype=np.float64) ** 2, axis=0), spk) @ right)      # noqa: E731
        n = len(out)
        self.assertLess(side(out[:n // 4]), side(out[3 * n // 4:]))
        self.assertLess(side(out[:n // 4]), 0.0)
        self.assertGreater(side(out[3 * n // 4:]), 0.0)


class Mixer(unittest.TestCase):
    def setUp(self):
        bspatial.clear()

    def tearDown(self):
        bspatial.clear()
        presets.reset_projects()

    def test_the_level_of_the_stereo_stem_is_kept(self):
        p = preset([rain(distance=1.0)], [animal(distance=1.0)])
        bspatial.register('bed', p, 3, SR, 0.0, 4.0, {'tracks': []})
        stem = engine.Biome(p, seed=3).render(4.0)
        placed = (stem * 0.5).astype(np.float32)
        out = bspatial.bus_sources('bed', placed, stem, {'role': 'environment', 'spatial': {'distance': 1.0}})
        self.assertEqual(len(out), 13)                                                       # 12 emitters and the animal
        total = sum(rms(m) ** 2 for _, m, _ in out)
        self.assertAlmostEqual(total, (rms(placed) ** 2) * 2.0, delta=0.2 * total)
        self.assertTrue(all(len(m) == len(placed) for _, m, _ in out))
        self.assertTrue(all(name.startswith('bed/') for name, _, _ in out))

    def test_the_tracks_own_distance_is_taken_back_out(self):
        p = preset([rain(distance=1.0)])
        bspatial.register('bed', p, 3, SR, 0.0, 3.0, {'tracks': []})
        stem = engine.Biome(p, seed=3).render(3.0)
        at1 = bspatial.bus_sources('bed', stem, stem, {'role': 'environment', 'spatial': {'distance': 1.0}})
        at4 = bspatial.bus_sources('bed', stem / 4.0, stem, {'role': 'environment', 'spatial': {'distance': 4.0}})       # the mixer divided by 4
        self.assertAlmostEqual(sum(rms(m) ** 2 for _, m, _ in at1), sum(rms(m) ** 2 for _, m, _ in at4), delta=0.02 * sum(rms(m) ** 2 for _, m, _ in at1))

    def test_a_part_time_bed_is_placed_at_its_start_and_ramped(self):
        p = preset([wind(field=True, distance=1.0)])
        bspatial.register('bed', p, 3, SR, 2.0, 3.0, {'tracks': []})
        stem = np.zeros((SR * 8, 2), np.float32)
        stem[2 * SR:5 * SR] = engine.Biome(p, seed=3).render(3.0)
        out = bspatial.bus_sources('bed', stem, stem, {'role': 'environment', 'spatial': {'distance': 1.0}})
        m = out[0][1]
        self.assertEqual(float(np.abs(m[:2 * SR]).max()), 0.0)
        self.assertEqual(float(np.abs(m[5 * SR:]).max()), 0.0)
        self.assertGreater(float(np.abs(m[2 * SR + SR:4 * SR]).max()), 0.0)
        self.assertLess(abs(float(m[2 * SR])), 0.05 * float(np.abs(m).max()))

    def test_an_unregistered_or_silent_track_is_left_alone(self):
        self.assertIsNone(bspatial.bus_sources('other', np.ones((10, 2), np.float32), np.ones((10, 2), np.float32), {}))
        bspatial.register('bed', preset([rain()]), 3, SR, 0.0, 1.0, {'tracks': []})
        z = np.zeros((SR, 2), np.float32)
        self.assertIsNone(bspatial.bus_sources('bed', z, z, {}))

    def test_render_natural_registers_a_biome_track_and_the_mixer_hands_its_emitters_to_the_bus(self):
        import json
        import tempfile
        import render_natural as rn
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'environments'))
            p = preset([rain(elevation=40.0), wind('breeze', azimuth=-70.0, distance=12.0)], [animal(azimuth=100.0, distance=20.0)],
                       coupling={'field': {'emitters': 6}})
            json.dump(dict(p, name='bed1'), open(os.path.join(d, 'presets', 'environments', 'bed1.json'), 'w'))
            presets.reset_projects()
            presets.add_project(d)
            sc = dict(bpm=120, space='none', seed=1, humanize='tight',
                      tracks=[dict(name='bed', role='environment', instrument='env:bed1', chain='none', spatial=dict(distance=1.0, widen=0.0),
                                   notes=[dict(t=0, d=8, p=60, v=80)])])
            stems, _ = rn.build_stems(sc, verbose=False)
            self.assertTrue(bspatial.is_registered('bed'))
            ctx = mix_context.MixContext(mix_schema.with_defaults(dict(immersive=IMM)), {}, name='test', space_name='none', space_owned=False)
            bus = hoa.HoaBus(SR, 3, 'ambix', IMM, {}, {})
            try:
                out = mixer.mix_stems(sc, stems, SR, ctx, bus=bus)
            finally:
                mixer.reset_context()
            names = [n for n, _, _ in bus.sources]
            self.assertEqual(names, [f'bed/rain/e{i}' for i in range(6)] + ['bed/breeze', 'bed/tiger'])
            places = {n: s['spatial'] for n, _, s in bus.sources}
            self.assertEqual(places['bed/breeze']['azimuth'], -70.0)
            self.assertEqual(places['bed/tiger']['azimuth'], 100.0)
            self.assertEqual(out.shape[1], 16)
            self.assertGreater(float(np.abs(out).max()), 0.0)
            self.assertTrue(np.isfinite(out).all())


class Reset(unittest.TestCase):
    def test_build_stems_forgets_the_last_piece(self):
        bspatial.register('old', preset([rain()]), 1, SR, 0.0, 1.0, {})
        import render_natural as rn
        rn.build_stems(dict(bpm=120, seed=1, tracks=[dict(name='p', role='melody', instrument='piano', notes=[dict(t=0, d=1, p=60, v=80)])]), verbose=False)
        self.assertFalse(bspatial.is_registered('old'))


if __name__ == '__main__':
    unittest.main()
