# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Immersive 2.0, phases 2 to 5: expression, the LF voice source, the new gate rows, the new deliverables.

Synthetic signals only. Every gate row has a signal it passes and a signal it fails.
"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import numpy as np
import soundfile as sf
from scipy import signal

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import dsp
import gate_profiles
import mix_context
import mix_schema
import mixer
import quality_gate
import render_natural
import render_targets
import spatial_gate
from spatial_engine import adm, hoa, render
from vocal_engine import config as vconfig, data as vdata, performance, source

SR = 44100
IMM = dict(mix_schema.DEFAULTS['immersive'], enabled=True, engine='hoa_bus')


def noise(seconds=2.0, seed=1, amp=0.1):
    return (amp * np.random.default_rng(seed).standard_normal(int(seconds * SR))).astype(np.float32)


def rms_db(x):
    return 10.0 * np.log10(float(np.mean(np.asarray(x, float) ** 2)) + 1e-20)


def rows_of(out, name):
    return [r for r in out if r[1] == name]


def mix(stems, tracks, mix_over=None, bus=None):
    m = mix_schema.with_defaults(dict({'immersive': IMM}, **(mix_over or {})))
    ctx = mix_context.MixContext(m, {}, name='test', space_name='none', space_owned=False)
    try:
        return mixer.mix_stems(dict(bpm=120, space='none', tracks=tracks), stems, SR, ctx, bus=bus)
    finally:
        mixer.reset_context()


def track(name, notes=None, **spatial):
    return dict(name=name, role='melody', instrument='test', notes=notes or [dict(t=0, d=1, p=60)], chain='none',
                spatial=dict(spatial, widen=0.0) if spatial else None)


class Expression(unittest.TestCase):
    def test_ou_track_has_the_asked_spread_and_is_seeded(self):
        a = render_natural._ou(np.random.default_rng(3), 200000, 0.006, 0.35, 0.06)
        b = render_natural._ou(np.random.default_rng(3), 200000, 0.006, 0.35, 0.06)
        np.testing.assert_array_equal(a, b)
        self.assertAlmostEqual(float(a[5000:].std()), 0.06, delta=0.006)
        self.assertEqual(a[0] * 0.0, 0.0)
        lag = int(0.35 / 0.006)                               # one correlation time later: correlation 1/e
        r = float(np.corrcoef(a[:-lag], a[lag:])[0, 1])
        self.assertAlmostEqual(r, np.exp(-1.0), delta=0.08)

    def test_dynamic_tilt_darkens_the_quiet_part_and_keeps_the_level(self):
        x = noise(2.0)
        x[SR:] *= 0.05                                        # second half is 26 dB quieter
        y = dsp.dynamic_tilt(x, SR, velocity=64)[:, 0]

        def bright(v):
            f, p = signal.welch(v, SR, nperseg=2048)
            return 10 * np.log10(p[f > 6000].sum() / p[f < 1000].sum())
        self.assertLess(bright(y[SR + 4000:]), bright(y[:SR]) - 3.0)
        self.assertAlmostEqual(rms_db(y), rms_db(x), delta=0.05)

    def test_dynamic_tilt_block_rejects_an_unknown_key(self):
        self.assertEqual(render_natural._tilt_block({'dynamic_tilt': {'floor': 0.4}}, None, 't'), {'floor': 0.4})
        self.assertIsNone(render_natural._tilt_block({}, {}, 't'))
        with self.assertRaises(ValueError):
            render_natural._tilt_block({'dynamic_tilt': {'flor': 0.4}}, None, 't')

    def test_resonator_rings_at_its_note_after_the_source_stops(self):
        x = np.zeros(2 * SR)
        x[:SR] = noise(1.0)
        y = dsp.resonator_bank(x, SR, [220.0], 300.0)
        tail = y[SR + 2000:SR + 2000 + 16384]
        f = np.fft.rfftfreq(len(tail), 1.0 / SR)
        self.assertAlmostEqual(float(f[np.argmax(np.abs(np.fft.rfft(tail)))]), 220.0, delta=3.0)
        self.assertGreater(rms_db(tail), rms_db(y[:SR]) - 20.0)           # q / (pi f) = 0.43 s: still ringing
        self.assertLess(rms_db(y[-2000:]), rms_db(y[:SR]) - 15.0)         # and it dies away

    def test_sympathetic_bed_is_off_by_default_and_sits_at_its_level(self):
        stems = {'a': np.repeat(noise()[:, None], 2, axis=1)}
        specs = {'a': dict(role='melody')}
        score = dict(tracks=[dict(name='a', notes=[dict(t=0, d=4, p=57), dict(t=4, d=1, p=64)])])
        self.assertIsNone(mixer.sympathetic_bed(score, stems, specs, mix_schema.with_defaults({}), SR))
        mx = mix_schema.with_defaults({'sympathetic_resonance': dict(enabled=True, level_db=-20.0, strings=1, partials=1)})
        bed = mixer.sympathetic_bed(score, stems, specs, mx, SR)
        self.assertEqual(bed.shape, (len(stems['a']), 2))
        self.assertAlmostEqual(rms_db(bed.mean(axis=1)), rms_db(stems['a'][:, 0]) - 20.0, delta=1.5)
        f, p = signal.welch(bed.mean(axis=1), SR, nperseg=16384)
        self.assertAlmostEqual(float(f[np.argmax(p)]), 110.0, delta=3.0)   # the most-used pitch class (A), from low_hz up

    def test_sympathetic_bed_skips_drums_and_reaches_the_mix(self):
        stems = {'a': noise(), 'd': noise(seed=2)}
        tracks = [track('a'), dict(track('d'), role='drum')]
        on = dict(sympathetic_resonance=dict(enabled=True, level_db=-12.0, tuning=[330.0], partials=1))
        dry = mix(stems, tracks)
        wet = mix(stems, tracks, on)
        self.assertGreater(rms_db(wet - dry), rms_db(dry) - 30.0)
        with self.assertRaises(ValueError):
            mix(stems, tracks, dict(sympathetic_resonance=dict(enabled=True, tuning='just')))
        self.assertEqual(mix_schema.validate({'sympathetic_resonance': {'enabled': True, 'q': 120.0}}), [])
        self.assertTrue(mix_schema.validate({'sympathetic_resonance': {'kew': 1}}))


class Voice(unittest.TestCase):
    REG = dict(open_quotient=0.6, speed_quotient=2.0, closure=0.25, tilt_hz=3000.0, shimmer=0.0)

    def spectrum(self, model, rd=1.0, f0=220.0, oversample=1):
        d, c, g = source.glottal_source(np.full(SR, f0), SR, np.random.default_rng(1), dict(self.REG, rd=rd),
                                        breathiness=0.0, model=model, oversample=oversample, tilt_poles=2)
        self.assertEqual(len(d), SR)
        self.assertEqual(len(g), SR)
        self.assertTrue(np.isfinite(d).all())
        return np.abs(np.fft.rfft(d * np.hanning(len(d)))), c

    def test_lf_pulse_closes_and_has_no_net_flow(self):
        for rd in (0.3, 1.0, 2.7):
            tp, te, ta, alpha, eps = source.lf_params(rd)
            self.assertTrue(0.0 < tp < te < 1.0)
            d, g = source.lf_pulse(np.arange(4096) / 4096.0, rd)
            self.assertAlmostEqual(float(d.mean()), 0.0, delta=2e-3 * float(np.abs(d).max()))
            self.assertAlmostEqual(float(g.max()), 1.0, places=3)
            self.assertLess(float(g[-1]), 0.01)

    def test_h1_h2_rises_with_rd(self):
        got = []
        for rd in (0.3, 0.8, 1.0, 1.6, 2.7):
            X, _ = self.spectrum('lf', rd)
            got.append(20 * np.log10(X[218:223].max() / X[438:443].max()))
        self.assertTrue(all(b > a + 1.0 for a, b in zip(got, got[1:])), got)
        self.assertLess(got[0], 0.0)                          # pressed: the second harmonic leads
        self.assertGreater(got[-1], 15.0)                     # breathy: the fundamental dominates

    def test_oversampling_lowers_what_folds_back(self):
        def alias_db(model, k):
            X, _ = self.spectrum(model, 1.0, 1000.0, k)
            harm = np.zeros(len(X), bool)
            for m in range(1, 23):
                harm[m * 1000 - 4:m * 1000 + 5] = True
            return 10 * np.log10(np.sum(X[~harm] ** 2) / np.sum(X[harm] ** 2))
        for model in source.MODELS:
            self.assertLess(alias_db(model, 2), alias_db(model, 1) - 8.0, model)
            self.assertLess(alias_db(model, 4), alias_db(model, 2) - 5.0, model)

    def test_phase_carries_on_whatever_the_rate(self):
        _, c1 = self.spectrum('lf', 1.0, 220.0, 1)
        _, c2 = self.spectrum('lf', 1.0, 220.0, 2)
        self.assertAlmostEqual(float(c1[-1]), float(c2[-1]), places=6)

    def test_unknown_model_and_config_values_are_errors(self):
        with self.assertRaises(ValueError):
            source.glottal_source(np.full(100, 220.0), SR, np.random.default_rng(1), self.REG, model='klatt')
        self.assertTrue(any('source.model' in w for w in vconfig.validate({'source': {'model': 'klatt'}})))
        self.assertTrue(any('oversample' in w for w in vconfig.validate({'source': {'oversample': 3}})))
        self.assertTrue(any('source.rd' in w for w in vconfig.validate({'source': {'rd': 9.0}})))   # clamped, and said
        self.assertFalse([w for w in vconfig.validate({'source': {'model': 'lf', 'rd': 1.4, 'oversample': 2}})
                          if 'source' in w])

    def test_syllable_shorthand(self):
        cfg = vdata.defaults()
        self.assertEqual(performance.expand_syllable(dict(syl='la'), cfg), dict(syl='la', consonant='l', vowel='a'))
        got = performance.expand_syllable(dict(syl='shai'), cfg)
        self.assertEqual((got['consonant'], got['vowel']), ('sh', ['a', 'i']))
        self.assertEqual(performance.expand_syllable(dict(syl='o'), cfg)['vowel'], 'o')
        self.assertNotIn('consonant', performance.expand_syllable(dict(syl='o'), cfg))
        self.assertEqual(performance.expand_syllable(dict(syl='la', vowel='u'), cfg)['vowel'], 'u')   # own key wins
        self.assertEqual(performance.expand_syllable(dict(p=60), cfg), dict(p=60))
        with self.assertRaises(ValueError):
            performance.expand_syllable(dict(syl='xq'), cfg)

    def test_a_voice_sings_with_the_lf_source(self):
        import vocals
        ev = [dict(t=0.0, dur=0.8, p=62, v=90, syl='la'), dict(t=0.8, dur=0.8, p=64, v=90, syl='nai')]
        a = vocals.render_choir(ev, sr=SR, voices=1, seed=4, config={'source': {'model': 'lf', 'oversample': 2}})
        b = vocals.render_choir(ev, sr=SR, voices=1, seed=4, config={'source': {'model': 'pulse'}})
        self.assertTrue(np.isfinite(a).all())
        self.assertGreater(rms_db(a), -60.0)
        self.assertFalse(np.allclose(a[:len(b)], b[:len(a)]))


class GateRows(unittest.TestCase):
    def brir(self, kind):
        n = int(3.0 * SR)
        h = np.zeros((n, 2))
        if kind == 'dry':                                     # one arrival, the same in both ears
            h[100] = 1.0
        else:                                                 # a weak direct sound under a long unrelated tail
            rng = np.random.default_rng(5)
            h[100] = 0.02
            h[100:] += rng.standard_normal((n - 100, 2)) * np.exp(-np.arange(n - 100) / (1.0 * SR))[:, None] * 0.1
        return h

    def run_room(self, kind, **score):
        out = []
        with mock.patch.object(mixer, 'immersive_cfg', return_value=IMM):
            quality_gate.immersive2_rows(dict(dict(bpm=120, tracks=[]), **score), None, out, brir=self.brir(kind))
        return out

    def test_room_measures(self):
        iacc, c80 = quality_gate.room_measures(self.brir('dry'), SR)
        self.assertGreater(iacc, 0.98)
        self.assertGreater(c80, 30.0)
        iacc, c80 = quality_gate.room_measures(self.brir('wash'), SR)
        self.assertLess(iacc, 0.5)
        self.assertLess(c80, -3.0)

    def test_iacc_and_clarity_rows_pass_and_warn(self):
        dry, wash = self.run_room('dry'), self.run_room('wash')
        self.assertEqual(rows_of(dry, 'imm_iacc_early')[0][0], 'WARN')     # every early arrival from the front
        self.assertEqual(rows_of(dry, 'imm_clarity')[0][0], 'PASS')
        self.assertEqual(rows_of(wash, 'imm_iacc_early')[0][0], 'PASS')
        self.assertEqual(rows_of(wash, 'imm_clarity')[0][0], 'WARN')

    def test_room_rows_measure_a_real_room_through_the_bus(self):
        from spatial_hrtf import binaural
        if not binaural.available():
            self.skipTest('head data not on disk')
        geom = dict(width_m=10.0, depth_m=14.0, height_m=6.0, listener=dict(x=5.0, y=4.0, z=1.5),
                    materials=dict(floor='wood', ceiling='plaster', walls='plaster'), material_set='room_materials',
                    max_order=2, max_taps=8, min_level_db=-30.0)
        space = dict(_source='test', reflections=dict(geometry=geom, late=dict(enabled=True, rt60_s='auto',
                                                                                 pre_delay_ms='auto', level_db=-14.0)))
        h = hoa.probe_brir(IMM, space, SR, distance=4.0)
        iacc, c80 = quality_gate.room_measures(h, SR)
        self.assertTrue(0.05 < iacc < 1.0, iacc)
        self.assertTrue(-15.0 < c80 < 40.0, c80)
        dead = dict(space, reflections=dict(geometry=geom, late=dict(enabled=False)))
        self.assertGreater(quality_gate.room_measures(hoa.probe_brir(IMM, dead, SR, distance=4.0), SR)[1], c80 + 3.0)

    def test_kinematics_row(self):
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        try:
            sf.write(path, np.zeros((4 * SR, 2), np.float32), SR)

            def run(seconds):
                keys = [dict(t_s=0.0, azimuth=-170.0), dict(t_s=seconds, azimuth=170.0)]
                tr = dict(name='fly', role='melody', spatial=dict(azimuth=0.0, distance=2.0, trajectory=dict(keyframes=keys)))
                out = []
                with mock.patch.object(mixer, 'immersive_cfg', return_value=dict(IMM, engine='per_stem')):
                    quality_gate.immersive2_rows(dict(bpm=120, tracks=[tr]), path, out)
                return rows_of(out, 'imm_kinematics')[0]
            self.assertEqual(run(4.0)[0], 'PASS')              # 340 degrees in 4 s is 85 deg/s; in half a second it is 680
            self.assertEqual(run(0.5)[0], 'FAIL')
            self.assertIn('fly', run(0.5)[2])
        finally:
            os.remove(path)

    def fold(self, x, immersive=False):
        out = []
        with mock.patch.object(mixer, 'immersive_cfg', return_value=IMM if immersive else None):
            quality_gate.fold_rows(dict(bpm=120, tracks=[]), None, out, audio=x, sr=SR)
        return out

    def test_band_fold_row(self):
        m = noise(3.0)
        self.assertEqual(rows_of(self.fold(np.stack([m, m], axis=1)), 'mix.band_fold')[0][0], 'PASS')
        wide = np.stack([m, noise(3.0, seed=9)], axis=1)                   # unrelated channels: 3 dB, allowed
        self.assertEqual(rows_of(self.fold(wide), 'mix.band_fold')[0][0], 'PASS')
        band = signal.sosfiltfilt(signal.butter(4, [900, 1300], 'band', fs=SR, output='sos'), m)
        bad = np.stack([m - 1.9 * band, m], axis=1)                        # one band out of phase between the ears
        row = rows_of(self.fold(bad), 'mix.band_fold')[0]
        self.assertEqual(row[0], 'FAIL')
        self.assertRegex(row[2], r'worst (9|1[0-2])\d\d?-')

    def test_low_fold_row(self):
        m = noise(3.0)
        low = signal.sosfiltfilt(signal.butter(4, 200, 'low', fs=SR, output='sos'), m)
        good, bad = np.stack([m, m], axis=1), np.stack([m, m - 1.8 * low], axis=1)
        self.assertEqual(rows_of(self.fold(good, True), 'imm_low_fold')[0][0], 'PASS')
        self.assertEqual(rows_of(self.fold(bad, True), 'imm_low_fold')[0][0], 'FAIL')
        self.assertEqual(rows_of(self.fold(bad, False), 'imm_low_fold'), [])          # only an immersive piece has the row
        self.assertEqual(rows_of(self.fold(bad, True), 'mix.band_fold'), [])           # and a headphone master not the other

    def test_finite_row(self):
        x = np.zeros((100, 3))
        out = []
        spatial_gate.finite_row(x, out)
        self.assertEqual(out[0][0], 'PASS')
        x[5, 1] = np.nan
        x[9, 2] = np.inf
        out = []
        spatial_gate.finite_row(x, out)
        self.assertEqual(out[0][0], 'FAIL')
        self.assertIn('2, 3', out[0][2])

    def test_rows_are_registered(self):
        for rid in ('imm.iacc_early', 'imm.clarity', 'imm.low_fold', 'mix.band_fold', 'imm.kinematics', 'render.finite'):
            self.assertIn(rid, gate_profiles.ROWS)
        self.assertTrue(gate_profiles.ROWS['render.finite'].get('protected'))
        self.assertEqual(gate_profiles.canonical('imm_low_fold'), 'imm.low_fold')
        self.assertEqual(gate_profiles.problems(), [])


class Deliverables(unittest.TestCase):
    def test_target_presets_are_valid(self):
        self.assertEqual(render_targets.manifest_problems(), [])
        for name, renderer in (('ambix', 'hoa'), ('adm_bw64', 'adm'), ('stereo_48k', 'mix_master')):
            self.assertEqual(render_targets.get(name)['renderer'], renderer)
            self.assertTrue(render_targets.buildable(name))
        self.assertEqual(render_targets.canonical('adm'), 'adm_bw64')

    def test_resampling_keeps_the_length_the_tone_and_the_ceiling(self):
        t = np.arange(SR) / SR
        x = np.stack([0.9 * np.sin(2 * np.pi * 997.0 * t)] * 2, axis=1).astype(np.float32)
        y = render.to_rate(x, SR, 48000, ceiling=-3.0)
        self.assertEqual(y.shape, (48000, 2))
        f = np.fft.rfftfreq(48000, 1 / 48000.0)
        self.assertAlmostEqual(float(f[np.argmax(np.abs(np.fft.rfft(y[:, 0])))]), 997.0, delta=1.0)
        self.assertLessEqual(mixer.true_peak_db(y, 48000), -3.0)
        self.assertIs(render.to_rate(x, SR, SR).dtype, x.dtype)

    def test_ambix_field_from_the_mixer(self):
        x = noise(1.0)
        bus = hoa.HoaBus(SR, 3, 'ambix', IMM, {}, {})
        out = mix({'a': x}, [track('a', azimuth=90.0, elevation=0.0, distance=1.0)], bus=bus)
        self.assertEqual(out.shape[1], 16)
        w, y_ch, z = out[:len(x), 0], out[:len(x), 1], out[:len(x), 2]
        self.assertGreater(float(np.corrcoef(w, x)[0, 1]), 0.9)            # W is the pressure
        self.assertGreater(rms_db(y_ch), rms_db(z) + 10.0)                 # a source at the side lives on the Y axis
        self.assertAlmostEqual(rms_db(y_ch), rms_db(w), delta=1.5)         # SN3D: first order peaks at W's level

    def test_adm_file(self):
        keys = [dict(t_s=0.0, azimuth=-40.0), dict(t_s=1.0, azimuth=60.0)]
        tracks = [track('still', azimuth=30.0, elevation=10.0, distance=2.0),
                  track('mover', azimuth=0.0, distance=2.0, trajectory=dict(keyframes=keys)),
                  dict(track('flat'), spatial=None)]
        stems = {'still': noise(1.0), 'mover': noise(1.0, 2), 'flat': np.stack([noise(1.0, 3), noise(1.0, 4)], axis=1)}
        bus = adm.AdmBus(SR, IMM, dict(title='t'))
        audio = mix(stems, tracks, bus=bus)
        self.assertEqual(audio.shape[1], 4 + 2)                            # still, mover, flat L, flat R, then the bed
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        try:
            adm.write(path, audio, SR, bus.xml(len(audio), SR), bus.chna())
            back, sr = sf.read(path, always_2d=True)
            self.assertEqual((sr, back.shape), (SR, audio.shape))
            np.testing.assert_allclose(back, np.clip(audio, -1, 1), atol=2.0 / (1 << 23))
            chunks = adm.read_chunks(path)
            self.assertEqual(set(chunks), {'fmt ', 'chna', 'axml', 'data'})
            self.assertEqual(len(chunks['chna']), 4 + 40 * 6)
            self.assertEqual(os.path.getsize(path) % 2, 0)
            ns = {'e': 'urn:ebu:metadata-schema:ebuCore_2016'}
            root = ET.fromstring(chunks['axml'])
            objs = root.findall('.//e:audioObject', ns)
            self.assertEqual([o.get('audioObjectName') for o in objs], ['still', 'mover', 'flat L', 'flat R', 'room return'])
            uids = [u.get('UID') for u in root.findall('.//e:audioTrackUID', ns)]
            self.assertEqual(len(uids), 6)
            self.assertEqual(sorted(uids), sorted(r.text for o in objs for r in o.findall('e:audioTrackUIDRef', ns)))
            chans = root.findall('.//e:audioChannelFormat', ns)

            def az(block):
                return float(block.find("e:position[@coordinate='azimuth']", ns).text)
            still = chans[0].findall('e:audioBlockFormat', ns)
            self.assertEqual(len(still), 1)
            self.assertAlmostEqual(az(still[0]), -30.0)                    # ADM counts azimuth to the left
            moving = chans[1].findall('e:audioBlockFormat', ns)
            self.assertGreater(len(moving), 5)
            self.assertGreater(az(moving[0]), 20.0)
            self.assertAlmostEqual(az(moving[-1]), -60.0, delta=1.0)
            self.assertEqual(moving[0].get('rtime'), '00:00:00.00000')
        finally:
            os.remove(path)

    def test_a_file_named_for_a_variable_channel_target_gets_its_rows(self):
        fd, path = tempfile.mkstemp(suffix='_master_adm.wav')
        os.close(fd)
        try:
            sf.write(path, np.zeros((SR, 5), np.float32), SR, subtype='PCM_24')
            out = []
            spatial_gate.output_rows(dict(output_targets=['stereo', 'adm_bw64'], tracks=[]), path, out)
            self.assertEqual([r[0] for r in rows_of(out, 'render.finite')], ['PASS'])
            self.assertEqual(rows_of(out, 'delivery.format'), [])
            self.assertEqual(len(rows_of(out, 'delivery.true_peak')), 1)
        finally:
            os.remove(path)


if __name__ == '__main__':
    unittest.main()
