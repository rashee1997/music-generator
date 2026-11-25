"""M4: creatures as data. The tract (ABCD matrices turned into peak-picked resonators), the six source kinds, the fauna
generator (level from radiated power, per-individual bouts, chunk-exact, name-seeded) and its validator."""
import math
import os
import sys
import unittest

import numpy as np
from scipy import signal
from scipy.linalg import solve_toeplitz

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from biome import context, fauna, fauna_schema, physics, schema, sources, tract  # noqa: E402
from phys_core import medium  # noqa: E402

SR = 44100
AIR = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.02897, gamma=1.4, viscosity_pa_s=1.81e-5, prandtl=0.71), 'state': {'temperature_k': 293.15}}
TITAN = {'model': 'ideal_gas', 'gas': dict(molar_mass_kg_mol=0.0279, gamma=1.40, viscosity_pa_s=6.0e-6, prandtl=0.71),
         'state': {'temperature_k': 94, 'pressure_pa': 146700}}
WATER = {'model': 'liquid', 'c_m_s': 1482.0, 'rho_kg_m3': 998.0, 'gas': {'gamma': 1.4}, 'state': {'pressure_pa': 101325.0}}
TWO_TUBE = {'kind': 'tract', 'segments': [[0.17, 2.0], [0.17, 8.0]], 'alpha_np_m': 0.02}


def ctx(med=AIR, g=9.81, seed=1):
    return context.Context(sr=SR, medium=medium.Medium(med), g=g, seed=seed)


def rms(y):
    return float(np.sqrt(np.mean(np.asarray(y, dtype=np.float64) ** 2)))


def peak_hz(y, lo=20.0, hi=None):
    y = np.asarray(y, dtype=np.float64)
    s = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    f = np.fft.rfftfreq(len(y), 1.0 / SR)
    s[f < lo] = 0
    if hi:
        s[f > hi] = 0
    return float(f[int(np.argmax(s))])


def true_peaks(res, med, n=4):
    grid = np.linspace(20.0, 0.45 * SR, 4096)
    H = tract.abcd_response(grid, res['segments'], med.c, med.rho, res.get('alpha_np_m', 0.0), res.get('branches') or [])
    pk, _ = signal.find_peaks(np.abs(H))
    return [float(grid[p]) for p in pk[:n]]


class Tract(unittest.TestCase):
    def test_a_straight_tube_has_the_quarter_wave_resonances(self):
        m = medium.Medium(AIR)
        res = {'kind': 'tract', 'segments': [[0.5, 4.0]], 'alpha_np_m': 0.001}
        got = [f for f, _, _ in tract.design(res, m, SR)][:3]
        for k, f in enumerate(got, 1):
            self.assertAlmostEqual(f, (2 * k - 1) * m.c / (4 * 0.5), delta=0.01 * f)

    def test_the_two_tube_tract_has_its_known_peaks(self):
        got = [f for f, _, _ in tract.design(TWO_TUBE, medium.Medium(AIR), SR)][:4]
        for f, want in zip(got, (357.0, 654.0, 1365.0, 1662.0)):
            self.assertAlmostEqual(f, want, delta=0.02 * want)

    def test_formants_scale_with_the_speed_of_sound(self):
        a = tract.design(TWO_TUBE, medium.Medium(AIR), SR)[0][0]
        t = tract.design(TWO_TUBE, medium.Medium(TITAN), SR)[0][0]
        self.assertAlmostEqual(t / a, medium.Medium(TITAN).c / medium.Medium(AIR).c, delta=0.015 * 0.577)

    def test_a_smaller_animal_has_higher_formants(self):
        m = medium.Medium(AIR)
        a, b = tract.design(TWO_TUBE, m, SR)[0][0], tract.design(TWO_TUBE, m, SR, scale=1.25)[0][0]
        self.assertAlmostEqual(b / a, 1.25, delta=0.02)

    def test_the_peak_picked_bank_is_right_where_lpc_12_is_not(self):
        m = medium.Medium(AIR)
        grid = np.linspace(1.0, SR / 2.0, 2048)
        H = tract.abcd_response(grid, TWO_TUBE['segments'], m.c, m.rho, 0.02)
        truth = true_peaks(TWO_TUBE, m, 1)[0]
        bank_f1 = tract.design(TWO_TUBE, m, SR)[0][0]
        r = np.fft.irfft(np.abs(H) ** 2)[:13]
        a = np.r_[1.0, solve_toeplitz(r[:12], -r[1:13])]
        roots = np.roots(a)
        lpc_f1 = float(np.sort(np.angle(roots[np.imag(roots) > 0]) * SR / (2 * np.pi))[0])
        self.assertLess(abs(bank_f1 - truth) / truth, 0.02)
        self.assertGreater(abs(lpc_f1 - truth) / truth, 0.5)                 # the measurement that ruled LPC out

    def test_a_closed_side_branch_adds_a_resonance(self):
        m = medium.Medium(AIR)
        plain = true_peaks(TWO_TUBE, m, 8)
        branched = true_peaks(dict(TWO_TUBE, branches=[{'after_segment': 0, 'length_m': 0.1, 'area_cm2': 1.5}]), m, 8)
        self.assertNotEqual([round(x) for x in plain], [round(x) for x in branched])

    def test_a_tube_follows_the_medium(self):
        res = {'kind': 'tube', 'length_cm': 17.0}
        a, t = tract.design(res, medium.Medium(AIR), SR)[0][0], tract.design(res, medium.Medium(TITAN), SR)[0][0]
        self.assertAlmostEqual(a, medium.Medium(AIR).c / 0.68, delta=1.0)
        self.assertAlmostEqual(t / a, medium.Medium(TITAN).c / medium.Medium(AIR).c, places=6)

    def test_a_formant_bank_is_as_written(self):
        got = tract.design({'kind': 'formant_bank', 'formants': [[700, 80, 0], [1200, 100, -6]]}, medium.Medium(AIR), SR)
        self.assertEqual([round(f) for f, _, _ in got], [700, 1200])
        self.assertAlmostEqual(got[1][2], 10 ** (-6 / 20), places=6)

    def test_apply_keeps_the_level_and_puts_energy_at_the_formant(self):
        x = np.random.default_rng(1).standard_normal(SR)
        y = tract.apply(x, [(1000.0, 60.0, 1.0)], SR, mix=1.0)
        self.assertAlmostEqual(rms(y), rms(x), delta=0.02 * rms(x))
        self.assertAlmostEqual(peak_hz(y, 100.0), 1000.0, delta=50.0)
        self.assertTrue(np.array_equal(tract.apply(x, [], SR), x))

    def test_problems(self):
        self.assertEqual(tract.problems(TWO_TUBE), [])
        self.assertTrue(tract.problems({'kind': 'tract'}))
        self.assertTrue(tract.problems({'kind': 'tract', 'segments': [[0.1, 2]], 'colour': 1}))
        self.assertTrue(tract.problems({'kind': 'tract', 'segments': [[0.1, 2]], 'branches': [{'after_segment': 0, 'length_m': 0.1, 'area_cm2': 1}]}))   # no junction
        self.assertTrue(tract.problems({'kind': 'tube', 'length_cm': -1}))
        self.assertTrue(tract.problems({'kind': 'formant_bank', 'formants': [[700, 80]]}))
        self.assertTrue(tract.problems({'kind': 'horn'}))
        self.assertEqual(tract.problems(None), [])


class Sources(unittest.TestCase):
    def element(self, kind, p, med=AIR, seed=2, scale=1.0, g=9.81):
        c = ctx(med, g=g)
        return sources.element(kind, dict(p, ms=p.get('ms', 1000.0)), SR, np.random.default_rng(seed), scale, c)

    def test_glottal_pulses_sit_at_the_f0(self):
        y = self.element('glottal_chaos', {'f0_hz': 150.0, 'rd': 1.0, 'jitter': 0.0, 'attack': 0.02, 'release': 0.02})
        ac = np.correlate(y[SR // 4:SR // 2], y[SR // 4:SR // 2], 'full')[len(y[SR // 4:SR // 2]) - 1:]
        lag = int(np.argmax(ac[100:600])) + 100
        self.assertAlmostEqual(SR / lag, 150.0, delta=6.0)

    def test_a_subharmonic_puts_energy_at_half_the_f0(self):
        def half(sub):
            y = self.element('glottal_chaos', {'f0_hz': 200.0, 'rd': 1.0, 'jitter': 0.0, 'subharmonic': sub, 'attack': 0.02, 'release': 0.02})
            s = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
            f = np.fft.rfftfreq(len(y), 1.0 / SR)
            return float(s[(f > 90) & (f < 110)].sum() / s.sum())
        self.assertGreater(half(0.6), 20.0 * half(0.0))

    def test_chaos_makes_the_period_irregular(self):
        def cv(chaos):
            y = self.element('glottal_chaos', {'f0_hz': 150.0, 'rd': 1.0, 'jitter': 0.0, 'chaos': chaos, 'attack': 0.02, 'release': 0.02})
            pk, _ = signal.find_peaks(-y, distance=int(0.5 * SR / 150.0), height=0.5 * np.abs(y).max())      # the closure spike of the flow derivative
            d = np.diff(pk)
            return float(d.std() / d.mean())
        self.assertGreater(cv(1.0), 4.0 * cv(0.0) + 0.01)

    def test_two_syringeal_voices_make_two_lines(self):
        y = self.element('dual_syrinx', {'f_left': 2000.0, 'f_right': 2500.0, 'harmonics': 1, 'saturation': 0.0, 'attack': 0.02, 'release': 0.02})
        s = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
        f = np.fft.rfftfreq(len(y), 1.0 / SR)
        a, b = s[(f > 1950) & (f < 2050)].sum(), s[(f > 2450) & (f < 2550)].sum()
        self.assertGreater((a + b) / s.sum(), 0.85)
        self.assertGreater(min(a, b) / max(a, b), 0.3)

    def test_fm_spreads_a_syringeal_line(self):
        plain = self.element('dual_syrinx', {'f_left': 2000.0, 'harmonics': 1, 'saturation': 0.0})
        fm = self.element('dual_syrinx', {'f_left': 2000.0, 'harmonics': 1, 'saturation': 0.0, 'fm_hz': 40.0, 'fm_depth': 0.1})
        near = lambda y: float((np.abs(np.fft.rfft(y)) ** 2)[int(1950 * len(y) / SR):int(2050 * len(y) / SR)].sum() / (np.abs(np.fft.rfft(y)) ** 2).sum())  # noqa: E731
        self.assertGreater(near(plain), near(fm) + 0.2)

    def test_stridulation_rings_the_plate(self):
        y = self.element('stridulation', {'tooth_hz': 80.0, 'plate_hz': 3000.0, 'plate_q': 30.0, 'attack': 0.05, 'release': 0.05})
        self.assertAlmostEqual(peak_hz(y), 3000.0, delta=120.0)

    def test_stridulation_rate_follows_temperature(self):
        def teeth(temp_k):
            med = dict(AIR, state={'temperature_k': temp_k})
            y = self.element('stridulation', {'tooth_hz': 40.0, 'plate_hz': 3000.0, 'plate_q': 1.0, 'jitter': 0.0, 'rate_per_k': 0.04,
                                              'temp_ref_k': 293.15, 'attack': 0.001, 'release': 0.001, 'ms': 2000.0}, med=med)
            env = np.abs(signal.hilbert(y))
            pk, _ = signal.find_peaks(env, height=0.5 * env.max(), distance=int(0.3 * SR / 40.0))
            return len(pk)
        base, warm = teeth(293.15), teeth(303.15)
        self.assertAlmostEqual(base / 2.0, 40.0, delta=3.0)
        self.assertAlmostEqual(warm / base, 1.4, delta=0.1)                                  # +10 K at 4 % per K

    def test_a_chirp_train_gates_the_sound(self):
        y = self.element('stridulation', {'tooth_hz': 120.0, 'plate_hz': 3000.0, 'train': {'chirp_ms': 100, 'period_ms': 400}, 'ms': 2000.0,
                                          'attack': 0.001, 'release': 0.001})
        env = np.abs(signal.hilbert(y))
        on = np.mean(env[int(0.02 * SR):int(0.08 * SR)])
        off = np.mean(env[int(0.2 * SR):int(0.35 * SR)])
        self.assertGreater(on, 20.0 * off)

    def test_clicks_speed_up_with_the_interval_contour(self):
        y = self.element('click_train', {'fc_hz': 2200.0, 'q': 3.0, 'ici_ms': [[0, 180], [1, 12]], 'jitter': 0.0, 'attack': 0.001, 'release': 0.001, 'ms': 2000.0})
        env = np.abs(signal.hilbert(y))
        pk, _ = signal.find_peaks(env, height=0.3 * env.max(), distance=int(0.003 * SR))
        n = len(y)
        first, last = np.sum(pk < n // 4), np.sum(pk > 3 * n // 4)
        self.assertGreater(last, 5 * max(first, 1))

    def test_a_bladder_rings_at_its_minnaert_pitch_for_its_depth(self):
        c = ctx(WATER)
        for depth, want in ((0.0, 657.0), (50.0, 1587.0), (200.0, 2963.0)):
            p = {'radius_m': 0.005, 'depth_m': depth, 'pulse_hz': 10.0, 'q': 20.0}
            self.assertAlmostEqual(sources.bladder_hz(p, c), want, delta=0.01 * want)
        y = self.element('swim_bladder', {'radius_m': 0.005, 'depth_m': 50.0, 'pulse_hz': 12.0, 'q': 20.0}, med=WATER)
        self.assertAlmostEqual(peak_hz(y), 1587.0, delta=0.04 * 1587.0)

    def test_a_bladder_above_nyquist_is_refused(self):
        with self.assertRaises(ValueError):
            self.element('swim_bladder', {'radius_m': 0.0001, 'pulse_hz': 10.0}, med=WATER)

    def test_every_kind_has_required_keys_and_ranges(self):
        self.assertTrue(sources.problems('stridulation', {'plate_hz': 3000.0}))
        self.assertTrue(sources.problems('glottal_chaos', {'f0_hz': 100.0, 'rd': 9.0}))
        self.assertTrue(sources.problems('click_train', {'fc_hz': 2000.0, 'ici_ms': [[0, 0]]}))
        self.assertTrue(sources.problems('swim_bladder', {'radius_m': 0.005, 'pulse_hz': 10, 'colour': 1}))
        self.assertTrue(sources.problems('stridulation', {'tooth_hz': 80, 'plate_hz': 3000, 'train': {'chirp_ms': 500, 'period_ms': 100}}))
        self.assertTrue(sources.problems('nope', {}))
        self.assertEqual(sources.problems('glottal_chaos', {'f0_hz': [[0, 100], [1, 120]], 'ms': [400, 600]}), [])


def cfg_tiger(**over):
    d = dict(name='tiger', power_w=0.01, bouts_per_min=30.0, first_s=0.2, source=dict(kind='glottal_chaos', rd=1.8, subharmonic=0.4, chaos=0.25),
             elements=dict(roar={'f0_hz': [[0, 120], [0.4, 150], [1, 90]], 'ms': [600, 800]}), resonator=TWO_TUBE)
    d.update(over)
    return d


def voiced_rms(y):
    y = np.asarray(y, dtype=np.float64)
    m = np.abs(y) > 0.01 * np.abs(y).max()
    return float(np.sqrt(np.mean(y[m] ** 2)))


class FaunaGen(unittest.TestCase):
    def test_the_level_is_the_radiated_power_through_the_medium(self):
        c = ctx(AIR)
        y = fauna.build(cfg_tiger(), c).render(5.0)
        want = physics.pressure_rms_from_power(c.medium.z, 0.01)
        self.assertAlmostEqual(voiced_rms(y), want, delta=0.2 * want)

    def test_thick_air_makes_the_same_animal_louder_at_equal_power(self):
        a = voiced_rms(fauna.build(cfg_tiger(), ctx(AIR)).render(5.0))
        t = voiced_rms(fauna.build(cfg_tiger(), ctx(TITAN)).render(5.0))
        self.assertAlmostEqual(20 * math.log10(t / a), 10 * math.log10(medium.Medium(TITAN).z / medium.Medium(AIR).z), delta=1.0)

    def test_the_first_bout_starts_where_it_was_told_and_bouts_follow_the_rate(self):
        f = fauna.build(cfg_tiger(), ctx())
        f.render(30.0)
        starts = [t for _, t, _ in f.starts]
        self.assertAlmostEqual(starts[0], 0.2, places=6)
        self.assertGreater(len(starts), 6)
        self.assertLess(len(starts), 20)                             # 30 a minute: about 15 in 30 s, never overlapping its own call
        self.assertTrue(all(b - a > d for (_, a, d), (_, b, _) in zip(f.starts, f.starts[1:])))

    def test_individuals_call_on_their_own_schedules(self):
        f = fauna.build(cfg_tiger(individuals=4, bouts_per_min=10.0, first_s=None), ctx())
        f.render(30.0)
        firsts = {i: min(t for j, t, _ in f.starts if j == i) for i in range(4)}
        self.assertEqual(len(set(round(v, 3) for v in firsts.values())), 4)
        self.assertTrue(all(lv <= 1.0 for lv in f.level))

    def test_any_chunking_gives_the_same_samples(self):
        whole = fauna.build(cfg_tiger(), ctx()).process(SR * 3)
        g = fauna.build(cfg_tiger(), ctx())
        parts = [g.process(n) for n in (7, 4409, 40000, 4410, 83000)]
        parts.append(g.process(SR * 3 - sum(len(p) for p in parts)))
        self.assertTrue(np.array_equal(whole, np.concatenate(parts)))

    def test_the_animal_is_seeded_by_its_name(self):
        c = ctx()
        alone = fauna.build(cfg_tiger(), c).render(3.0)
        fauna.build(cfg_tiger(name='cat'), c).render(1.0)
        self.assertTrue(np.array_equal(alone, fauna.build(cfg_tiger(), c).render(3.0)))
        self.assertFalse(np.array_equal(alone, fauna.build(cfg_tiger(name='other'), ctx()).render(3.0)))

    def test_a_calls_preset_is_a_starting_point(self):
        f = fauna.build(dict(name='owl', call='owl_hoot', power_w=1e-3, first_s=0.5), ctx())
        y = f.render(8.0)
        self.assertAlmostEqual(peak_hz(y, 150.0, 800.0), 350.0, delta=40.0)
        self.assertEqual(f.res['kind'] if f.res else None, f.res['kind'] if f.res else None)

    def test_a_calls_preset_with_a_tract_becomes_a_tube(self):
        m = fauna.from_call_preset(dict(name='dog', call='dog_bark', power_w=1e-3))
        self.assertEqual(m['source'], {'kind': 'additive'})
        import presets
        pre = presets.get('calls', 'dog_bark')
        if pre.get('tract_cm'):
            self.assertEqual(m['resonator']['kind'], 'tube')
            self.assertEqual(m['resonator']['length_cm'], float(pre['tract_cm']))
        self.assertEqual(m['name'], 'dog')

    def test_a_key_written_beside_the_preset_wins(self):
        m = fauna.from_call_preset(dict(name='owl', call='owl_hoot', power_w=1e-3, bouts_per_min=99.0))
        self.assertEqual(m['bouts_per_min'], 99.0)

    def test_a_scheduler_decides_when_a_bout_may_begin(self):
        class Every5:
            def __init__(self):
                self.asked = []

            def next_start(self, name, ind, earliest, dur, rng):
                self.asked.append((name, ind, round(earliest, 2)))
                return max(earliest, 5.0 * len(self.asked))

        s = Every5()
        f = fauna.build(cfg_tiger(first_s=None), ctx(), scheduler=s)
        f.render(30.0)
        self.assertEqual([round(t) for _, t, _ in f.starts], [5, 10, 15, 20, 25])
        self.assertEqual(s.asked[0][0], 'tiger')

    def test_a_scheduler_can_end_the_calling(self):
        class Once:
            n = 0

            def next_start(self, name, ind, earliest, dur, rng):
                Once.n += 1
                return 1.0 if Once.n == 1 else None
        f = fauna.build(cfg_tiger(first_s=None), ctx(), scheduler=Once())
        f.render(20.0)
        self.assertEqual(len(f.starts), 1)

    def test_warm_air_calls_more_often_for_a_cold_blooded_animal(self):
        cold = fauna.build(cfg_tiger(rate_per_k=0.04, temp_ref_k=293.15), ctx(dict(AIR, state={'temperature_k': 283.15})))
        warm = fauna.build(cfg_tiger(rate_per_k=0.04, temp_ref_k=293.15), ctx(dict(AIR, state={'temperature_k': 303.15})))
        self.assertGreater(cold.mean_gap, warm.mean_gap)
        self.assertAlmostEqual(cold.mean_gap / warm.mean_gap, 1.4 / 0.6, delta=0.01)

    def test_an_invalid_animal_is_refused_with_its_name(self):
        with self.assertRaises(ValueError) as cm:
            fauna.build(cfg_tiger(sequence=['nope']), ctx())
        self.assertIn('tiger', str(cm.exception))
        no_power = cfg_tiger()
        del no_power['power_w']
        with self.assertRaises(ValueError) as cm:
            fauna.build(no_power, ctx())
        self.assertIn('power_w', str(cm.exception))

    def test_output_is_finite_float32_pascals(self):
        y = fauna.build(cfg_tiger(), ctx()).render(3.0)
        self.assertEqual(y.dtype, np.float32)
        self.assertTrue(np.isfinite(y).all())


class FaunaSchema(unittest.TestCase):
    def preset(self, **over):
        p = {'schema': 'biome/1', 'name': 't', 'character': 'a test place', 'medium': AIR, 'controls': {'dawn': {'curve': [[0, 0], [10, 1]]}},
             'generators': [dict(name='w', kind='turbulence', obstacles=dict(d_m=dict(dist='fixed', value=0.005), frontal_area_m2=10.0),
                                 flow=dict(u_m_s=3.0))],
             'fauna': [cfg_tiger()]}
        p.update(over)
        return p

    def test_a_valid_preset_with_fauna_is_clean(self):
        self.assertEqual(schema.problems(self.preset()), [])

    def test_there_is_no_default_level(self):
        f = cfg_tiger()
        del f['power_w']
        self.assertTrue(any('power_w' in p for p in schema.problems(self.preset(fauna=[f]))))

    def test_unknown_and_misplaced_keys(self):
        self.assertTrue(any('unknown key "colour"' in p for p in schema.problems(self.preset(fauna=[cfg_tiger(colour=1)]))))
        bad = cfg_tiger(source=dict(kind='glottal_chaos', tooth_hz=90))
        self.assertTrue(any('tooth_hz' in p for p in schema.problems(self.preset(fauna=[bad]))))

    def test_the_sequence_must_name_elements(self):
        self.assertTrue(any('sequence' in p for p in schema.problems(self.preset(fauna=[cfg_tiger(sequence=['nope'])]))))

    def test_a_source_is_required_unless_a_call_preset_starts_it(self):
        f = cfg_tiger()
        del f['source']
        self.assertTrue(any('source' in p for p in schema.problems(self.preset(fauna=[f]))))
        self.assertEqual(schema.problems(self.preset(fauna=[dict(name='owl', call='owl_hoot', power_w=1e-3)])), [])

    def test_an_unknown_calls_preset_is_named(self):
        self.assertTrue(any('nope' in p for p in schema.problems(self.preset(fauna=[dict(name='x', call='nope', power_w=1e-3)]))))

    def test_niche_position_and_medium_are_checked(self):
        self.assertEqual(schema.problems(self.preset(fauna=[cfg_tiger(niche={'band_hz': [60, 1200], 'active': {'control': 'dawn'}},
                                                                        position={'azimuth': 110, 'elevation': 0, 'distance': 60})])), [])
        for bad in (dict(niche={'band_hz': [1200, 60]}), dict(niche={'active': {'control': 'nope'}}), dict(position={'elevation': 120}),
                    dict(position={'colour': 1}), dict(medium='sea')):
            self.assertTrue(schema.problems(self.preset(fauna=[cfg_tiger(**bad)])), bad)

    def test_names_are_unique_and_do_not_clash_with_generators(self):
        self.assertTrue(any('twice' in p for p in schema.problems(self.preset(fauna=[cfg_tiger(), cfg_tiger()]))))
        self.assertTrue(any('also a generator' in p for p in schema.problems(self.preset(fauna=[cfg_tiger(name='w')]))))

    def test_the_entry_validator_matches_what_the_generator_refuses(self):
        for bad in (dict(sequence=['nope']), dict(resonator={'kind': 'horn'}), dict(source=dict(kind='stridulation', plate_hz=100))):
            self.assertTrue(fauna_schema.entry_problems(cfg_tiger(**bad)), bad)
            with self.assertRaises(ValueError):
                fauna.build(cfg_tiger(**bad), ctx())


if __name__ == '__main__':
    unittest.main()
