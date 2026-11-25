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

"""Tests for the vocal and extraction audit fixes. Each fails on the code as it was and passes on the fix."""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'tests'))

import vocals  # noqa: E402
from vocal_engine import breath, consonant, data, nasal, performance as pf, utils as vu, voice, waveguide  # noqa: E402

SR = 44100


def _cfg():
    return data.defaults()


class VocalCaches(unittest.TestCase):
    def test_calibration_key_follows_tract_gains_and_waveguide(self):
        c = _cfg()
        c['waveguide']['mode'] = 'table'
        F = list(c['tract']['vowels']['a'])[:3]
        bw = list(c['tract']['bandwidths'])[:3]
        c['tract']['gains'] = list(c['tract']['gains'])[:3]
        a = pf._calibration(SR, c, False, F, bw, {}, None, 0.0, bw_arg=bw)
        c2 = copy.deepcopy(c)
        c2['tract']['gains'] = [g * 0.1 for g in c['tract']['gains']]
        b = pf._calibration(SR, c2, False, F, bw, {}, None, 0.0, bw_arg=bw)
        self.assertGreater(b / a, 5.0)             # 0.1x the gains needs ~10x the calibration gain, not the cached one
        c3 = copy.deepcopy(c)
        c3['waveguide']['gain_tilt_power'] = float(c['waveguide'].get('gain_tilt_power', 1.0)) + 0.37
        self.assertEqual(len(set(pf._CAL)), len(pf._CAL))
        n0 = len(pf._CAL)
        pf._calibration(SR, c3, False, F, bw, {}, None, 0.0, bw_arg=bw)
        self.assertEqual(len(pf._CAL), n0 + 1)

    def test_junction_key_follows_losses(self):
        c = _cfg()
        wv, h = c['waveguide'], c['humming']
        a = nasal.junction(h, wv)
        wv2 = copy.deepcopy(wv)
        wv2['losses']['k0_per_m'] = float(wv['losses']['k0_per_m']) * 20.0
        b = nasal.junction(h, wv2)
        self.assertFalse(np.allclose(a[1], b[1]))

    def test_peaks_windows_are_disjoint_when_modes_are_close(self):
        F = np.array([2800.0, 2825.0, 2850.0, 2900.0, 3000.0])      # two gaps of 25 Hz, under the 40 Hz minimum
        lo, hi = waveguide._peak_windows(F, 0.12)
        self.assertTrue(np.all(hi[:-1] <= lo[1:] + 1e-9), (lo, hi))
        self.assertTrue(np.all(hi > lo))
        out = waveguide.peaks(F, np.full(20, 4e-4), 0.17, _cfg()['waveguide'])
        self.assertEqual(out.shape, F.shape)


class VocalSmall(unittest.TestCase):
    def test_sing_rejects_zero_duration(self):
        with self.assertRaises(ValueError):
            vocals.sing(57, 0.0, SR, np.random.default_rng(0))

    def test_consonant_buzz_follows_source_model(self):
        cn = _cfg()['consonants']
        a, _ = consonant.render('m', cn, SR, np.random.default_rng(0), f0=150.0, model='pulse')
        b, _ = consonant.render('m', cn, SR, np.random.default_rng(0), f0=150.0, model='lf')
        self.assertFalse(np.allclose(a, b))

    def test_shared_bandpass_survives_inverted_band_and_matches_old_design(self):
        from scipy.signal import butter, sosfilt
        x = np.random.default_rng(0).standard_normal(4000)
        y = vu.bandpass(x, SR, 3000.0, 1000.0)           # lo >= hi used to raise in breath
        self.assertTrue(np.isfinite(y).all())
        sos = butter(2, [500.0, 2000.0], btype='band', fs=SR, output='sos')
        self.assertTrue(np.array_equal(vu.bandpass(x, SR, 500.0, 2000.0), sosfilt(sos, x)))
        sos = butter(2, 800.0, btype='low', fs=SR, output='sos')
        self.assertTrue(np.array_equal(vu.lowpass(x, SR, 800.0), sosfilt(sos, x)))
        self.assertIs(vu._sos('band', 2, 500.0, 2000.0, float(SR)), vu._sos('band', 2, 500.0, 2000.0, float(SR)))

    def test_pitch_helpers(self):
        self.assertAlmostEqual(float(vu.cents_to_hz(6900.0)), 440.0)
        self.assertAlmostEqual(float(vu.hz_to_midi(880.0)), 81.0)

    def test_neutral_formants_follow_length_scale_and_pharynx(self):
        c = _cfg()
        FH = c['formant_hold'] if 'formant_hold' in c else {}
        onset = np.array([700.0, 1100.0, 2500.0])
        n1 = pf._neutral_formants({}, c, FH, onset)
        c2 = copy.deepcopy(c)
        c2['tract']['length_scale'] = 1.2
        n2 = pf._neutral_formants({}, c2, FH, onset)
        self.assertAlmostEqual(float(n2[0] / n1[0]), 1.2, places=6)
        c3 = copy.deepcopy(c)
        c3['tract']['pharynx_scale'] = 1.1
        n3 = pf._neutral_formants({}, c3, FH, onset)
        self.assertAlmostEqual(float(n3[0] / n1[0]), 1.1, places=6)


# ------------------------------------------------------------------------------------------------ extraction
import clone_instrument as ci  # noqa: E402
from extraction import audio_io, config as xcfg, enhance, gate, notes, spatial, voices as xvoices  # noqa: E402


class CloneInstrument(unittest.TestCase):
    def test_first_partial_survives_a_sub_bass_fundamental(self):
        sr = 44100
        fr = np.fft.rfftfreq(8192, 1 / sr)
        f0 = 40.0
        spec = np.zeros(len(fr))
        for k in (1, 2, 3):
            spec[int(np.argmin(np.abs(fr - k * f0)))] = 1.0 / k
        pk_f, pk_a = ci._partial_peaks(spec, fr, f0, 5)
        self.assertGreaterEqual(len(pk_f), 3)
        self.assertGreater(pk_a.max(), 0.0)

    def test_segment_notes_on_empty_input_is_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, 'too short'):
            ci.segment_notes(np.zeros(100), 44100)

    def test_yin_matches_the_loop_it_replaced(self):
        sr = 22050
        t = np.arange(int(0.6 * sr)) / sr
        rng = np.random.default_rng(0)
        x = 0.4 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t) + 0.01 * rng.standard_normal(len(t))
        f0, conf, rdb = ci.yin(x, sr)
        # reference: the per-tau loop
        tmax, tmin = int(sr / 55.0), max(2, int(sr / 2200.0))
        n = (len(x) - 2048 - tmax) // 512
        ref = np.zeros(n)
        for i in range(n):
            seg = x[i * 512: i * 512 + 2048 + tmax]
            a = seg[:2048]
            if 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9) < -60:
                continue
            nfft = 1 << int(np.ceil(np.log2(len(seg) + 2048)))
            r = np.fft.irfft(np.fft.rfft(seg, nfft) * np.conj(np.fft.rfft(a, nfft)), nfft)[:tmax]
            cs = np.concatenate([[0], np.cumsum(seg ** 2)])
            d = cs[2048] + (cs[2048:2048 + tmax] - cs[:tmax]) - 2 * r
            d[0] = 0
            cm = np.ones_like(d)
            cm[1:] = d[1:] * np.arange(1, tmax) / (np.cumsum(d[1:]) + 1e-12)
            tt = None
            for tau in range(tmin, tmax - 1):
                if cm[tau] < 0.15:
                    while tau + 1 < tmax - 1 and cm[tau + 1] < cm[tau]:
                        tau += 1
                    tt = tau
                    break
            if tt is None:
                continue
            a_, b_, c_ = cm[tt - 1], cm[tt], cm[tt + 1]
            den = a_ - 2 * b_ + c_
            ref[i] = sr / (tt + (0.5 * (a_ - c_) / den if abs(den) > 1e-12 else 0.0))
        self.assertTrue(np.array_equal(f0, ref))
        self.assertGreater((f0 > 0).sum(), 3)

    def test_moving_mean_equals_convolve_same(self):
        x = np.random.default_rng(1).standard_normal(5000) ** 2
        for h in (41, 441, 40):
            self.assertTrue(np.allclose(ci._moving_mean(x, h), np.convolve(x, np.ones(h) / h, mode='same'), atol=1e-12))


class ExtractionFixes(unittest.TestCase):
    def test_cancel_skips_harmonics_past_the_top_row(self):
        R = np.zeros((3, 1))
        notes._cancel(R, np.array([2]), np.array([0, 1, 2, 3]), np.array([[1.0], [10.0], [100.0], [1000.0]]))
        self.assertEqual(R[2, 0], -1.0)           # the one harmonic that has a row; the old clamp applied the last (1000)
        R = np.zeros((10, 2))
        notes._cancel(R, np.array([1, 3]), np.array([0, 2, 4]), np.ones((3, 2)))
        self.assertEqual(float(R.sum()), -6.0)    # nothing clamped: every harmonic subtracted once

    def test_span_gain_has_no_edge_dip(self):
        g = enhance.span_gain(20000, 1000, [(0.0, 20.0)], 0.0, -40.0, 0.5)
        self.assertTrue(np.allclose(g, 1.0, atol=1e-6), (g.min(), g.max()))

    def test_downmix_keeps_the_centre_channel(self):
        y = np.zeros((6, 100), 'float32')
        y[2] = 1.0                                  # a centre-only voice
        st = audio_io.to_stereo(y)
        self.assertEqual(st.shape, (2, 100))
        self.assertAlmostEqual(float(st[0, 0]), 10 ** (-3 / 20), places=5)
        lfe = np.zeros((6, 10), 'float32')
        lfe[3] = 1.0
        self.assertEqual(float(np.abs(audio_io.to_stereo(lfe)).max()), 0.0)
        self.assertEqual(audio_io.to_stereo(np.ones((2, 5), 'float32')).shape, (2, 5))
        with self.assertRaises(ValueError):
            audio_io.to_stereo(np.ones((4, 5), 'float32'))

    def test_kb_seed_without_a_directory_is_a_clear_exit(self):
        import argparse
        import extract_pipeline as ep
        with self.assertRaises(SystemExit) as cm:
            ep.cmd_kb(argparse.Namespace(action='seed', dir=None))
        self.assertIn('needs a project', str(cm.exception))

    def test_a_crashed_check_is_a_fail_row(self):
        def boom(ctx, rows):
            raise RuntimeError('x')
        old = gate.CHECKS
        gate.CHECKS = (boom,)
        try:
            rows, score = gate.evaluate({'data': {'resynth': {}}})
        finally:
            gate.CHECKS = old
        self.assertEqual(rows[0]['level'], 'FAIL')
        self.assertEqual(score, gate.LEVEL_WEIGHT['FAIL'])

    def test_nearest_gap_equals_min_abs(self):
        rng = np.random.default_rng(2)
        known = np.sort(rng.uniform(0, 30, 200))
        t = rng.uniform(-1, 31, 500)
        ref = np.array([np.min(np.abs(known - x)) for x in t])
        self.assertTrue(np.array_equal(gate.nearest_gap(known, t), ref))

    def test_suppress_leakage_matches_the_all_pairs_version(self):
        cfg = xcfg.defaults()
        nc = cfg['notes']
        rng = np.random.default_rng(3)
        ns = [dict(midi=int(rng.integers(40, 50)), start_s=float(s), end_s=float(s + rng.uniform(0.05, 1.0)),
                   strength=float(rng.uniform(0.1, 3))) for s in rng.uniform(0, 5, 150)]
        ns.sort(key=lambda n: (n['start_s'], n['midi']))
        keep = []
        for n in ns:
            dur = n['end_s'] - n['start_s']
            ghost = any(o is not n and 0 < abs(o['midi'] - n['midi']) <= nc['leak_semitones']
                        and ((dur < nc['leak_max_s'] and o['strength'] >= nc['leak_ratio'] * n['strength']
                              and o['start_s'] - nc['leak_touch_s'] <= n['end_s'] and o['end_s'] + nc['leak_touch_s'] >= n['start_s'])
                             or (abs(o['midi'] - n['midi']) <= 1 and o['strength'] >= nc['leak_strong_ratio'] * n['strength']
                                 and min(o['end_s'], n['end_s']) - max(o['start_s'], n['start_s']) >= 0.6 * dur)) for o in ns)
            if not ghost:
                keep.append(n)
        got = notes.suppress_leakage(ns, cfg)
        self.assertEqual([id(n) for n in got], [id(n) for n in keep])
        self.assertLess(len(keep), len(ns))

    def test_cluster_vectors_matches_the_rescanning_version(self):
        rng = np.random.default_rng(4)
        vecs = [rng.random(8) + (i % 3) for i in range(60)]
        label, centres = xvoices.cluster_vectors(vecs, 0.5)
        lab2, cen2 = [], []
        for v in vecs:
            d = [xvoices.distance(v, c) for c in cen2]
            if d and min(d) <= 0.5:
                k = int(np.argmin(d))
            else:
                cen2.append(v.copy())
                k = len(cen2) - 1
            lab2.append(k)
            cen2[k] = np.mean([vecs[i] for i, l in enumerate(lab2) if l == k], axis=0)
        self.assertEqual(label, lab2)
        self.assertTrue(np.allclose(centres, cen2))

    def test_rms_env_equals_convolve(self):
        x = np.random.default_rng(5).standard_normal(20000).astype('float32')
        hop = 441
        ref = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode='same'))[::hop]
        self.assertTrue(np.allclose(spatial._rms_env(x, hop), ref, rtol=1e-6, atol=1e-8))

    def test_fit_room_linearity_matches_per_gain_stft(self):
        rng = np.random.default_rng(6)
        dry, wet = rng.standard_normal(8000).astype('float32'), rng.standard_normal(8000).astype('float32')
        D, W = gate.stft_complex(dry), gate.stft_complex(wet)
        for g in (0.0, 0.3, 1.1):
            self.assertTrue(np.allclose(np.abs(D + g * W), gate.stft_mag(dry + g * wet), atol=1e-4))

    def test_separate_analysis_is_cached_per_mix(self):
        from extraction import separate
        cfg = xcfg.defaults()
        y = np.random.default_rng(7).standard_normal((2, 6000)).astype('float32')
        a = separate._mix_analysis(y, cfg)
        b = separate._mix_analysis(y.copy(), cfg)
        self.assertIs(a[0], b[0])
        c = separate._mix_analysis(y * 0.5, cfg)
        self.assertIsNot(a[0], c[0])


if __name__ == '__main__':
    unittest.main()
