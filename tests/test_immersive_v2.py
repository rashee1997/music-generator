# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Immersive 2.0, measured on synthetic signals only: the ambisonic bus, the room's physics, motion.

No test here knows a piece, a genre or an instrument. The head-data tests skip when the FABIAN set is not on disk.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import airabs
import gate_checks
import gate_audio
import mix_schema
import mixer
import mix_context
from spatial_engine import config, hoa, trajectory
from spatial_hrtf import binaural, room

SR = 44100
HEAD = binaural.available()
BOX = dict(width_m=10.0, depth_m=14.0, height_m=6.0, listener=dict(x=5.0, y=4.0, z=1.5),
           materials=dict(floor='wood', ceiling='plaster', walls='plaster'), material_set='room_materials',
           max_order=2, max_taps=8, min_level_db=-30.0)


def noise(seconds=1.5, seed=1):
    return (0.1 * np.random.default_rng(seed).standard_normal(int(seconds * SR))).astype(np.float32)


def rms_db(x):
    return 10.0 * np.log10(float(np.mean(np.asarray(x, float) ** 2)) + 1e-20)


def mix(stems, tracks, immersive, space=None, bus=None):
    """One mix through mixer.mix_stems with an explicit immersive block and space (no project on disk)."""
    m = mix_schema.with_defaults({'immersive': dict(immersive, enabled=True)})
    ctx = mix_context.MixContext(m, space or {}, name='test', space_name='none', space_owned=bool(space))
    score = dict(bpm=120, space='none', tracks=tracks)
    try:
        return mixer.mix_stems(score, stems, SR, ctx, bus=bus)
    finally:
        mixer.reset_context()


def track(name, **spatial):
    # widen 0: the old engine widens the finished binaural signal by role, the bus does not (a width in a 3-D field
    # is a pair angle), so the two are compared without it
    return dict(name=name, role='melody', instrument='test', notes=[dict(t=0, d=1, p=60)], chain='none',
                spatial=dict(spatial, widen=0.0))


class Trajectory(unittest.TestCase):
    def test_keyframes_pass_through_their_keys_and_never_overshoot(self):
        keys = [dict(t_s=0.0, azimuth=-30, elevation=0, distance=3), dict(t_s=1.0, azimuth=40, elevation=20, distance=2),
                dict(t_s=2.0, azimuth=40, elevation=20, distance=2)]
        p = trajectory.path(dict(keyframes=keys), 0.0, 0.0, 1.5, 2 * SR, SR)
        at = lambda s: p[int(s * SR / trajectory.HOP)]
        np.testing.assert_allclose(at(0.0), [-30, 0, 3], atol=1e-6)
        np.testing.assert_allclose(at(1.0), [40, 20, 2], atol=0.05)
        self.assertLessEqual(p[:, 0].max(), 40.0 + 1e-9)
        self.assertGreaterEqual(p[:, 2].min(), 2.0 - 1e-9)

    def test_bar_keys_use_the_tempo(self):
        score = dict(bpm=120, humanize='tight', rubato=0.0, ritard=0.0, tracks=[dict(notes=[dict(t=0, d=64, p=60)])])
        self.assertAlmostEqual(trajectory.seconds(dict(bar=3), score), 4.0, places=2)     # two bars of 4 at 120

    def test_old_form_is_a_straight_line(self):
        p = trajectory.path(dict(start_azimuth=-60, end_azimuth=60), 0.0, 5.0, 2.0, SR, SR)
        self.assertAlmostEqual(p[0, 0], -60.0)
        self.assertAlmostEqual(p[len(p) // 2, 0], 0.0, delta=0.5)
        self.assertTrue(np.all(p[:, 1] == 5.0))

    def test_anchor_stays_near_its_place(self):
        p = trajectory.path(dict(start_azimuth=-90, end_azimuth=90), 10.0, 0.0, 2.0, SR, SR)
        q = trajectory.anchor(p, 10.0, 0.0, 2.0, 6.0)
        self.assertLessEqual(np.ptp(q[:, 0]), 6.0 + 1e-9)
        self.assertTrue(trajectory.is_anchor({}, 'bass'))
        self.assertFalse(trajectory.is_anchor({}, 'melody'))

    def test_speed_is_degrees_per_second(self):
        p = trajectory.path(dict(start_azimuth=0, end_azimuth=90), 0.0, 0.0, 2.0, SR, SR)
        self.assertAlmostEqual(trajectory.speed_deg_per_s(p, SR), 90.0, delta=1.0)

    def test_unknown_mode_and_section_are_errors(self):
        with self.assertRaises(ValueError):
            trajectory.path(dict(mode='spiral'), 0, 0, 2, SR, SR)
        with self.assertRaises(ValueError):
            trajectory.seconds(dict(section='nowhere'), dict(bpm=100, tracks=[]))


class RoomPhysics(unittest.TestCase):
    def test_air_absorption_matches_the_standard(self):
        a = airabs.alpha_db_per_m([1000.0, 10000.0]) * 1000.0            # dB per km at 20 C, 50 %, one atmosphere
        self.assertAlmostEqual(a[0], 4.7, delta=0.5)
        self.assertAlmostEqual(a[1], 159.0, delta=8.0)

    def test_eyring_matches_a_hand_calculation(self):
        geom = dict(BOX, materials=dict(floor='carpet', ceiling='carpet', walls='carpet'))
        bands, t60 = room.eyring_rt60(geom)
        i = bands.index(1000.0)
        vol, surf = 10.0 * 14.0 * 6.0, 2 * (10 * 14 + 6 * (10 + 14))
        m = airabs.alpha_db_per_m(1000.0) / 4.3429
        want = 24 * np.log(10) / 343.0 * vol / (-surf * np.log(1 - 0.69) + 4 * m * vol)
        self.assertAlmostEqual(t60[i], want, places=6)
        self.assertLess(t60[i], room.eyring_rt60(BOX)[1][i])               # carpet is deader than plaster

    def test_an_open_ceiling_sends_nothing_back(self):
        geom = dict(BOX, materials=dict(floor='earth', ceiling='open', walls='foliage'), max_taps=40, min_level_db=-80)
        up = [t for t in room.taps(geom, 20.0, 0.0, 3.0) if t['image'][2] > 0]
        self.assertTrue(all(float(np.max(t['coeffs'])) == 0.0 for t in up))

    def test_auto_tail_comes_from_the_geometry(self):
        refl = dict(geometry=BOX, late=dict(enabled=True, rt60_s='auto', pre_delay_ms='auto', level_db=-18))
        cfg = room.late_cfg(refl)
        self.assertEqual(len(cfg['rt60_bands_s']), 7)
        self.assertAlmostEqual(cfg['pre_delay_ms'], room.mixing_time_ms(BOX))
        ir = room.late_ir(cfg, SR)
        self.assertTrue(np.all(ir[:int(cfg['pre_delay_ms'] / 1000 * SR)] == 0.0))
        with self.assertRaises(ValueError):
            room.late_cfg(dict(late=dict(enabled=True, rt60_s='auto')))
        same = dict(late=dict(enabled=True, rt60_s=1.2))
        self.assertIs(room.late_cfg(same), same['late'])

    def test_a_source_outside_the_walls_is_clamped_inside(self):
        direct, images = room.image_tracks(BOX, np.array([90.0]), np.array([0.0]), np.array([50.0]))
        self.assertLessEqual(float(direct[0]), 5.0)
        self.assertTrue(all(float(im['path_m'][0]) > float(direct[0]) for im in images))

    def test_image_tracks_agree_with_taps_for_a_still_source(self):
        taps = room.taps(BOX, 30.0, 5.0, 3.0)
        direct, images = room.image_tracks(BOX, np.array([30.0]), np.array([5.0]), np.array([3.0]))
        for t, im in zip(taps, images):
            self.assertAlmostEqual(t['distance_m'], float(im['path_m'][0]), places=9)
            self.assertAlmostEqual(t['azimuth'], float(im['azimuth'][0]), places=9)


class ReflectionTaps(unittest.TestCase):
    """The tap renderer against the per-tap loop it replaced (`docs/mix_profile_palace.md`).

    The old loop built a delayed copy of the source, ran the room's absorption FIR over it and then the air
    absorption, once per tap; the new one takes one transform of the source and applies each tap as a response.
    Both must give the same delay, the same level and the same spectrum, or the room has changed.
    """

    def setUp(self):
        self.raw = noise(0.5, seed=5).astype(np.float64)
        self.taps = room.taps(BOX, 35.0, 5.0, 2.0)
        self.temp, self.rh = 20.0, 50.0

    def per_tap(self, tap, raw=None):
        """One tap written out by hand: a delayed copy, the surface's response read out centred (its own group delay
        removed: the tap's delay is its path length), then the air that path crosses."""
        from scipy import signal
        raw = self.raw if raw is None else raw
        n = len(raw)
        d = int(round(tap['delay_ms'] / 1000.0 * SR))
        s = np.zeros(n)
        s[d:] = raw[:n - d] * (1.0 / tap['distance_m'])
        fir = room.absorption_fir(tap['coeffs'], sr=SR)
        g = room.group_delay(len(fir))
        s = signal.fftconvolve(s, fir)[g:g + n]
        return airabs.apply(s, tap['distance_m'] - 1.0, self.temp, self.rh, sr=SR)

    def test_a_tap_arrives_at_its_path_length(self):
        """The 129-tap surface filter is linear phase: convolved causally it used to add its 64 samples (1.45 ms) to
        every early reflection of the room while the direct sound stayed put."""
        signals, kept = list(hoa.tap_signals(self.raw, self.taps, SR, self.temp, self.rh))[0]
        for j, tap in enumerate(kept):
            d = int(round(tap['delay_ms'] / 1000.0 * SR))
            plain = np.zeros(len(self.raw))
            plain[d:] = self.raw[:len(self.raw) - d]
            self.assertEqual(self.lag(plain, signals[:, j].astype(np.float64)), 0,
                             msg=f'tap {tap["image"]} does not arrive at its path length')

    @staticmethod
    def lag(a, b):
        """How far b is delayed against a, in samples: the peak of their circular cross-correlation."""
        size = 1 << int(np.ceil(np.log2(2 * max(len(a), len(b)))))
        c = np.fft.irfft(np.fft.rfft(b, size) * np.conj(np.fft.rfft(a, size)), size)
        i = int(np.argmax(c))
        return i - size if i > size // 2 else i

    def test_one_transform_per_tap_is_the_same_delay_level_and_spectrum(self):
        groups = list(hoa.tap_signals(self.raw, self.taps, SR, self.temp, self.rh))
        self.assertEqual(len(groups), 1)
        signals, kept = groups[0]
        self.assertEqual(len(kept), len(self.taps))
        for j, tap in enumerate(kept):
            want = self.per_tap(tap).astype(np.float64)
            got = signals[:, j].astype(np.float64)
            msg = f'tap {tap["image"]} at {tap["distance_m"]:.1f} m'
            self.assertAlmostEqual(rms_db(got), rms_db(want), delta=0.05, msg=msg)
            self.assertEqual(self.lag(got, want), 0, msg=f'{msg}: the tap arrives at a different time')
            # the air filter used to be a 1025-tap approximation: its error may not be a spectral tilt
            f = np.fft.rfftfreq(len(want), 1.0 / SR)
            for lo, hi in ((100.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)):
                band = (f >= lo) & (f < hi)
                dev = (10 * np.log10(np.sum(np.abs(np.fft.rfft(got)[band]) ** 2) + 1e-30)
                       - 10 * np.log10(np.sum(np.abs(np.fft.rfft(want)[band]) ** 2) + 1e-30))
                self.assertLess(abs(dev), 0.3, msg=f'{msg}: {dev:+.2f} dB at {lo:.0f}-{hi:.0f} Hz')

    def test_the_grouping_changes_nothing_about_the_taps(self):
        (one, a), = list(hoa.tap_signals(self.raw, self.taps, SR, self.temp, self.rh))
        parts = list(hoa.tap_signals(self.raw, self.taps, SR, self.temp, self.rh,
                                     budget=len(self.raw) * 4))       # one tap per group
        self.assertGreater(len(parts), 1)
        for k, (sig, taps) in enumerate(parts):
            j = k * len(taps)
            np.testing.assert_array_equal(sig, one[:, j:j + len(taps)])

    def test_physics_off_leaves_the_level_out(self):
        (with_air, taps), = list(hoa.tap_signals(self.raw, self.taps, SR, self.temp, self.rh))
        (no_air, _), = list(hoa.tap_signals(self.raw, self.taps, SR, self.temp, self.rh, physics=False))
        for j, tap in enumerate(taps):
            want = 20.0 * np.log10(tap['distance_m'])
            got = rms_db(no_air[:, j]) - rms_db(with_air[:, j])
            self.assertGreater(got, want - 1.0, msg=f'tap {tap["image"]}: 1/distance is the level')

    def test_encoding_together_is_the_sum_of_encoding_one_at_a_time(self):
        rng = np.random.default_rng(4)
        signals = rng.standard_normal((2000, 5)).astype(np.float32)
        gains = rng.standard_normal((5, 9)).astype(np.float32)
        together = np.zeros((2000, 9), np.float32)
        hoa.encode_many(together, signals, gains)
        one_at_a_time = np.zeros((2000, 9), np.float32)
        for j in range(5):
            hoa.encode(one_at_a_time, signals[:, j], gains[j])
        np.testing.assert_allclose(together, one_at_a_time, atol=1e-6)


class NearField(unittest.TestCase):
    CFG = dict(model='dvf', max_m=1.0, head_radius_m=0.0875)

    def test_sphere_limits(self):
        far = binaural._sphere_mag(np.array([0.05, 30.0]), 200.0, np.array([1.0]))[0]
        self.assertAlmostEqual(far[0], 1.0, delta=0.03)          # a long wave does not see the head
        self.assertAlmostEqual(far[1], 2.0, delta=0.05)          # a short one doubles on the facing side

    def test_no_change_at_the_reference_distance(self):
        np.testing.assert_allclose(binaural.dvf_gains(70.0, 0.0, 1.0, self.CFG), 1.0, atol=1e-9)

    def test_near_ear_rises_and_far_ear_falls_as_the_source_closes(self):
        f = np.fft.rfftfreq(binaural.DVF_BLOCK, 1.0 / SR)
        low = int(np.argmin(np.abs(f - 300.0)))
        last = 0.0
        for d in (0.7, 0.4, 0.25):
            left, right = 20 * np.log10(binaural.dvf_gains(90.0, 0.0, d, self.CFG)[:, low])
            self.assertGreater(right - left, last)
            self.assertGreater(right, 0.0)
            self.assertLess(left, 0.0)
            last = right - left
        self.assertGreater(last, 6.0)                            # a strong low-frequency level difference at 25 cm

    def test_time_varying_filter_is_transparent_at_unity(self):
        x = noise(0.5).astype(float)
        np.testing.assert_allclose(binaural.stft_gain(x, lambda k: np.ones(binaural.DVF_BLOCK // 2 + 1)), x, atol=1e-9)


class Decoders(unittest.TestCase):
    def test_allrad_keeps_power_over_the_upper_sphere(self):
        for layout in ('itu_bs2051_system_h', 'itu_bs2051_system_i', 'itu_bs2051_system_j'):
            spk = config.speakers(layout)
            d = hoa.allrad_matrix(spk, 5)
            rng = np.random.default_rng(4)
            az, el = rng.uniform(-180, 180, 300), (rng.uniform(0, 25, 300) if layout != 'itu_bs2051_system_h' else np.zeros(300))
            power = 10 * np.log10(np.sum((d @ binaural.gains(5, az, el).T) ** 2, axis=0))
            # a matrix decoder on ten loudspeakers cannot hold power exactly: this is the measured spread, kept honest
            self.assertLess(float(np.ptp(power)), 4.0, msg=f'{layout}: {power.min():.2f}..{power.max():.2f} dB')
            self.assertAlmostEqual(float(np.mean(power)), 0.0, delta=1.5, msg=layout)

    def test_allrad_points_at_the_right_loudspeaker(self):
        spk = config.speakers('itu_bs2051_system_j')
        d = hoa.allrad_matrix(spk, 5)
        names = [s['name'] for s in spk]
        for want in ('FL', 'SR', 'TBL'):
            s = spk[names.index(want)]
            g = d @ binaural.gains(5, s['azimuth'], s['elevation'])[0]
            self.assertEqual(names[int(np.argmax(np.abs(g)))], want)

    def test_an_ear_height_source_uses_its_two_neighbours(self):
        # found while building the decoder: with height loudspeakers present, a source at +80 deg played from the
        # front LEFT and back right loudspeakers, a pair 165 deg apart that happens to hold the direction
        from spatial_engine import pan
        for layout in ('itu_bs2051_system_i', 'itu_bs2051_system_j'):
            spk = config.speakers(layout)
            used = {n for n, g in pan.gains(80.0, 0.0, spk).items() if g > 1e-6}
            self.assertEqual(used, {'FR', 'SR'}, msg=layout)
            used = {n for n, g in pan.gains(-110.0, 0.0, spk).items() if g > 1e-6}
            self.assertEqual(used, {'SL', 'BL'}, msg=layout)

    def test_ambix_is_acn_sn3d(self):
        left = hoa.ambix(binaural.gains(1, -90.0, 0.0))[0]       # a source on the listener's left
        np.testing.assert_allclose(left, [1.0, 1.0, 0.0, 0.0], atol=1e-6)      # W, Y (left +), Z, X
        np.testing.assert_allclose(hoa.ambix(binaural.gains(1, 0.0, 90.0))[0], [1.0, 0.0, 1.0, 0.0], atol=1e-6)

    def test_fractional_read_is_exact_on_whole_samples_and_smooth_between(self):
        t = np.arange(4000) / SR
        x = np.sin(2 * np.pi * 440.0 * t)
        np.testing.assert_allclose(hoa.read(x, np.arange(100, 200)), x[100:200], atol=1e-12)
        got = hoa.read(x, np.arange(100, 200) + 0.37)
        np.testing.assert_allclose(got, np.sin(2 * np.pi * 440.0 * (np.arange(100, 200) + 0.37) / SR), atol=1e-5)


@unittest.skipUnless(HEAD, 'the measured head data is not on disk (python -m spatial_hrtf.data)')
class Bus(unittest.TestCase):
    SPACE = dict(reflections=dict(path_physics=True, geometry=BOX), _source='test')

    def both(self, tracks, stems, space=None):
        return (mix(stems, tracks, dict(engine='per_stem'), space), mix(stems, tracks, dict(engine='hoa_bus'), space))

    def test_default_engine_is_the_old_one(self):
        self.assertEqual(mix_schema.DEFAULTS['immersive']['engine'], 'per_stem')
        self.assertEqual(mix_schema.validate({'immersive': {'engine': 'hoa_bus', 'order': 5}}), [])
        self.assertTrue(mix_schema.validate({'immersive': {'engine': 'object'}}))

    def test_a_still_source_is_the_same_on_both_engines(self):
        for az, el, d in ((-50.0, 10.0, 2.0), (120.0, 30.0, 4.0)):
            a, b = self.both([track('a', azimuth=az, elevation=el, distance=d)], {'a': noise()})
            n = min(len(a), len(b))
            diff = rms_db(a[:n] - b[:n]) - rms_db(a[:n])
            self.assertLess(diff, -60.0, msg=f'az {az}: bus differs from per-stem by {diff:.1f} dB')

    def test_reflections_arrive_on_both_engines_at_the_same_level(self):
        tr = [track('a', azimuth=35.0, elevation=0.0, distance=2.0)]
        a, b = self.both(tr, {'a': noise()}, self.SPACE)
        dry = mix({'a': noise()}, tr, dict(engine='hoa_bus'))
        self.assertGreater(rms_db(b[:len(dry)] - dry), rms_db(dry) - 30.0)         # the room is really there
        for e in (0, 1):
            self.assertAlmostEqual(rms_db(a[:, e]), rms_db(b[:, e]), delta=0.1)

    def test_a_stereo_bed_becomes_a_pair(self):
        st = np.stack([noise(seed=1), noise(seed=2)], axis=1)
        a, b = self.both([track('a', azimuth=0.0, distance=2.0, kind='bed')], {'a': st})
        # not sample-identical by design: the old engine reflects a pair as one source at its centre, the bus
        # reflects each side from its own side. The level and the width must still agree.
        for e in (0, 1):
            self.assertAlmostEqual(rms_db(a[:, e]), rms_db(b[:, e]), delta=1.0)
        corr = lambda y: float(np.corrcoef(y[:, 0], y[:, 1])[0, 1])
        self.assertAlmostEqual(corr(a), corr(b), delta=0.1)
        self.assertLess(corr(b), 0.6)

    def test_late_field_is_one_room_at_the_preset_level(self):
        space = dict(reflections=dict(late=dict(enabled=True, rt60_s=0.8, hf_decay=0.6, level_db=-12.0, count=6,
                                                spread_deg=70.0, seed=3)), _source='test')
        tr = [track('a', azimuth=20.0, distance=2.0)]
        x = {'a': noise(3.0)}
        a, b = self.both(tr, x, space)
        dry = mix(x, tr, dict(engine='hoa_bus'))
        tail_a, tail_b = a[:len(dry)] - dry, b[:len(dry)] - dry
        self.assertAlmostEqual(rms_db(tail_a), rms_db(tail_b), delta=3.0)
        c = float(np.corrcoef(tail_b[SR:, 0], tail_b[SR:, 1])[0, 1])
        self.assertLess(abs(c), 0.4, msg=f'the late field is not spread: L/R correlation {c:.2f}')

    def test_an_orbit_has_no_clicks_and_moves(self):
        t = np.arange(3 * SR) / SR
        tone = (0.2 * np.sin(2 * np.pi * 330.0 * t) * np.minimum(1.0, np.minimum(t, 3.0 - t) * 20)).astype(np.float32)
        keys = [dict(t_s=0.0, azimuth=0.0), dict(t_s=3.0, azimuth=360.0)]
        out = mix({'a': tone}, [track('a', azimuth=0.0, distance=2.0, trajectory=dict(keyframes=keys))],
                  dict(engine='hoa_bus'), self.SPACE)
        self.assertTrue(np.isfinite(out).all())
        hit = gate_checks.check_clicks(gate_audio.Signal(out, SR)) if hasattr(gate_audio, 'Signal') else None
        if hit is not None:
            self.assertEqual(int(hit['value']), 0, msg=hit.get('detail'))
        out = mix({'a': noise(3.0)}, [track('a', azimuth=0.0, distance=2.0, trajectory=dict(keyframes=keys))],
                  dict(engine='hoa_bus'))                               # level difference needs a broadband source
        q = len(out) // 4
        ild = lambda seg: rms_db(seg[:, 1]) - rms_db(seg[:, 0])
        self.assertGreater(ild(out[q - 4000:q + 4000]), 3.0)             # on the right a quarter of the way round
        self.assertLess(ild(out[3 * q - 4000:3 * q + 4000]), -3.0)       # on the left three quarters round

    def test_a_moving_source_keeps_its_room(self):
        tr = [track('a', azimuth=0.0, distance=3.0, trajectory=dict(start_azimuth=-60, end_azimuth=60))]
        x = {'a': noise(2.0)}
        with_room = mix(x, tr, dict(engine='hoa_bus'), self.SPACE)
        without = mix(x, tr, dict(engine='hoa_bus'))
        self.assertGreater(rms_db(with_room[:len(without)] - without), rms_db(without) - 30.0)

    def test_approach_raises_the_pitch(self):
        t = np.arange(2 * SR) / SR
        tone = (0.2 * np.sin(2 * np.pi * 1000.0 * t)).astype(np.float32)
        tr = lambda s: [track('a', azimuth=0.0, distance=40.0,
                              trajectory=dict(start_distance=40.0, end_distance=6.0, doppler_strength=s))]
        peak = lambda y: float(np.argmax(np.abs(np.fft.rfft(y[SR // 2:3 * SR // 2, 0] * np.hanning(SR)))))
        still = peak(mix({'a': tone}, tr(0.0), dict(engine='hoa_bus')))
        moving = peak(mix({'a': tone}, tr(1.0), dict(engine='hoa_bus')))
        self.assertAlmostEqual(still, 1000.0, delta=1.0)
        self.assertAlmostEqual(moving, 1000.0 * (1 + 17.0 / 343.0), delta=3.0)     # 34 m in 2 s towards the listener

    def test_a_long_field_on_disk_decodes_the_same(self):
        tr = [track('a', azimuth=-40.0, elevation=10.0, distance=2.0)]
        want = mix({'a': noise()}, tr, dict(engine='hoa_bus'))
        keep, hoa.IN_RAM_BYTES = hoa.IN_RAM_BYTES, 1024
        try:
            got = mix({'a': noise()}, tr, dict(engine='hoa_bus'))
        finally:
            hoa.IN_RAM_BYTES = keep
        np.testing.assert_array_equal(got, want)

    def test_keyframes_need_the_bus(self):
        tr = [track('a', azimuth=0.0, distance=2.0, trajectory=dict(keyframes=[dict(t_s=0, azimuth=10)]))]
        with self.assertRaises(ValueError):
            mix({'a': noise()}, tr, dict(engine='per_stem'))

    def test_scenes_change_the_room_and_identical_scenes_change_nothing(self):
        tr = [track('a', azimuth=25.0, distance=2.0)]
        x = {'a': noise(3.0)}
        base = mix(x, tr, dict(engine='hoa_bus'), self.SPACE)
        same = dict(self.SPACE, scenes=[dict(anchor=dict(t_s=1.0), transition_s=0.5, space_overrides={})])
        np.testing.assert_allclose(mix(x, tr, dict(engine='hoa_bus'), same), base, atol=2e-6)
        small = dict(self.SPACE, scenes=[dict(anchor=dict(t_s=1.0), transition_s=0.5,
                                              space_overrides=dict(geometry=dict(width_m=4.0, depth_m=5.0, height_m=2.6,
                                                                                 listener=dict(x=2.0, y=1.5, z=1.5))))])
        changed = mix(x, tr, dict(engine='hoa_bus'), small)
        np.testing.assert_allclose(changed[:SR // 2], base[:SR // 2], atol=2e-6)         # before the scene: the old room
        self.assertGreater(rms_db(changed[2 * SR:] - base[2 * SR:len(changed)]), rms_db(base[2 * SR:]) - 30.0)

    def test_a_loudspeaker_layout_gets_the_room_around_the_direct_sound(self):
        from spatial_engine import render
        layout = 'itu_bs2051_system_j'
        names = config.channel_names(layout)
        tr = [track('a', azimuth=0.0, elevation=0.0, distance=2.0)]
        out = mix({'a': noise(2.0)}, tr, dict(engine='hoa_bus'), self.SPACE, bus=render.LayoutBus(layout, None, SR))
        self.assertEqual(out.shape[1], len(names))
        self.assertTrue(np.isfinite(out).all())
        level = {n: rms_db(out[:, i]) for i, n in enumerate(names)}
        self.assertEqual(max((n for n in names if n != 'LFE'), key=level.get), 'FC')      # the source itself: VBAP
        for n in ('BL', 'BR', 'TBL', 'TBR'):                                               # the room: behind and above
            self.assertGreater(level[n], level['FC'] - 45.0, msg=f'{n} is silent: {level[n]:.1f} dB')
            self.assertLess(level[n], level['FC'] - 3.0)

    def test_near_field_cue_survives_on_the_bus(self):
        near = dict(enabled=True, model='dvf', max_m=1.0, head_radius_m=0.0875)
        space = dict(distance=dict(near_field=near), _source='test')
        ild = lambda y: rms_db(y[:, 1]) - rms_db(y[:, 0])
        far = mix({'a': noise()}, [track('a', azimuth=90.0, distance=1.0)], dict(engine='hoa_bus'), space)
        close = mix({'a': noise()}, [track('a', azimuth=90.0, distance=0.5)], dict(engine='hoa_bus'), space)
        self.assertGreater(ild(close), ild(far) + 1.0)


if __name__ == '__main__':
    unittest.main()
