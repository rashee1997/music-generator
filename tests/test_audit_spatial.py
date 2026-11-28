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

"""One test per defect found by the spatial / HRTF audit. Each fails on the code as it was and passes on the fix."""
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'tests'))
warnings.filterwarnings('ignore')

from spatial_engine import adm, decorrelate, hoa, master, trajectory
from spatial_hrtf import binaural, io as hio, process, room
import spatial

SR = 44100


def _bus():
    return adm.AdmBus(SR, dict(enabled=True, height_by_role={'melody': 20.0}, max_elevation=60.0,
                               pair=dict(width_deg_stereo=12.0, width_deg_bed=40.0)), dict(title='t'))


def _roundtrip(bus):
    fd, path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    audio = bus.result()
    adm.write(path, audio, SR, bus.xml(len(audio), SR), bus.chna())
    try:
        return adm.fold_to_stereo(adm.parse(path)), audio
    finally:
        os.remove(path)


class AdmFold(unittest.TestCase):
    def test_bed_side_comes_from_its_track_not_the_global_index(self):
        for n_obj in (1, 2, 3):                                   # odd and even object counts
            bus = _bus()
            for i in range(n_obj):
                bus.objects.append((f'o{i}', np.zeros(3000, np.float32), 0.0, 0.0, 1.5, None, 'melody'))
            bed = np.zeros((3000, 2), np.float32)
            bed[:, 0] = 0.1                                       # hard-left bed
            bus.add_reverb(bed)
            fold, _ = _roundtrip(bus)
            self.assertGreater(float(np.abs(fold[:, 0]).mean()), 0.09, f'{n_obj} objects: left bed lost')
            self.assertLess(float(np.abs(fold[:, 1]).max()), 1e-6, f'{n_obj} objects: left bed folded to the right')

    def _sweep_bus(self):
        bus = _bus()
        n = 4410
        path = np.zeros((n // trajectory.HOP + 2, 3))
        path[:, 0] = np.linspace(-60.0, 60.0, len(path))
        path[:, 2] = 1.5
        bus.objects.append(('sweep', np.full(n, 0.1, np.float32), -60.0, 0.0, 1.5, path, 'melody'))
        return bus

    def test_sweep_is_levelled_and_gated_on_the_same_position(self):
        bus = self._sweep_bus()
        fold, audio = _roundtrip(bus)
        ref = bus.stereo_fold(audio)
        # a left-to-right sweep sits in the middle on both folds, not hard left on the file fold
        for f in (fold, ref):
            lr = float(np.mean(f[:, 0] ** 2)) / float(np.mean(f[:, 1] ** 2))
            self.assertAlmostEqual(lr, 1.0, delta=0.15)       # hard left would be ~1e3
        np.testing.assert_allclose(fold, ref, atol=2e-2)


class Hrtf(unittest.TestCase):
    def test_stft_place_is_a_linear_convolution(self):
        from scipy.signal import fftconvolve
        rng = np.random.default_rng(3)
        n = 6000
        x = rng.standard_normal(n)
        az, el = 40.0, 15.0
        dec = binaural.magls(binaural.ORDER)
        g = binaural.gains(binaural.ORDER, az, el)[0]
        got = binaural._stft_place(x, np.full(n, az), np.full(n, el))
        worst = -300.0
        for e in (0, 1):
            ref = fftconvolve(x, g @ dec[e])[:n]
            err = got[:, e] - ref
            worst = max(worst, 20 * np.log10(np.sqrt(np.mean(err ** 2)) / np.sqrt(np.mean(ref ** 2))))
        print(f'\n_stft_place error vs direct convolution: {worst:.1f} dB (was about -49 dB)')
        self.assertLess(worst, -100.0)

    def test_stft_place_moving_source_is_finite_and_follows_the_direction(self):
        n = 8000
        x = np.random.default_rng(1).standard_normal(n)
        out = binaural._stft_place(x, np.linspace(-80, 80, n), np.zeros(n))
        self.assertTrue(np.isfinite(out).all())
        a, b = out[:1500], out[-1500:]
        self.assertGreater(np.std(a[:, 0]), np.std(a[:, 1]))        # starts on the left
        self.assertGreater(np.std(b[:, 1]), np.std(b[:, 0]))        # ends on the right

    def test_air_follows_the_distance_at_each_instant(self):
        import airabs
        from scipy import signal
        x = np.random.default_rng(2).standard_normal((SR, 2))
        d = np.linspace(1.0, 201.0, len(x))
        y = binaural._air_moving(x, d, 20.0, 50.0, SR)
        hp = signal.butter(4, 8000.0, 'high', fs=SR, output='sos')
        h = lambda v: float(np.sqrt(np.mean(signal.sosfilt(hp, v, axis=0) ** 2)))
        near, far = h(y[:SR // 10]) / h(x[:SR // 10]), h(y[-SR // 10:]) / h(x[-SR // 10:])
        self.assertGreater(near, 0.5)
        self.assertLess(far, 0.3 * near)
        const = binaural._air_moving(x, np.full(len(x), 30.0), 20.0, 50.0, SR)
        np.testing.assert_allclose(const, airabs.apply(x, 29.0, sr=SR).astype(float), atol=1e-6)

    def test_magls_cache_tag_follows_the_file_bytes_and_version(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'set.mat')
            open(p, 'wb').write(b'a' * 100)
            t1 = binaural._magls_tag(p, 5)
            open(p, 'wb').write(b'b' * 100)                       # replaced in place, same path and size
            t2 = binaural._magls_tag(p, 5)
            self.assertNotEqual(t1, t2)
            old = binaural.MAGLS_VERSION
            try:
                binaural.MAGLS_VERSION = old + 1
                self.assertNotEqual(binaural._magls_tag(p, 5), t2)
            finally:
                binaural.MAGLS_VERSION = old

    def _mat(self, d, fs, azi_scale=1.0):
        from scipy.io import savemat
        azi = np.linspace(0.0, 2 * np.pi, 12, endpoint=False) * azi_scale
        zen = np.full(12, np.pi / 2)
        p = os.path.join(d, 'own.mat')
        savemat(p, dict(hrir_l=np.random.rand(12, 64), hrir_r=np.random.rand(12, 64), azi=azi, zen=zen, fs=fs))
        return p

    def test_48k_mat_loads_at_its_native_rate(self):
        with tempfile.TemporaryDirectory() as d:
            h = hio.load_hrirs(44100, self._mat(d, 48000))
            self.assertEqual(int(h.fs), 48000)                    # AssertionError before; binaural resamples it

    def test_mat_in_degrees_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                hio.load_hrirs(44100, self._mat(d, 44100, azi_scale=180.0 / np.pi))

    def test_resample_with_no_jobs_is_serial_not_silent(self):
        h = np.random.default_rng(0).standard_normal((3, 64))
        for jobs in (0, -2, 1):
            l, r, fs = process.resample_hrirs(h, h, 44100, 48000, jobs_count=jobs)
            self.assertEqual(fs, 48000)
            self.assertGreater(float(np.abs(l).max()), 0.1, f'jobs_count={jobs} returned silence')

    def test_reflection_air_uses_the_clamped_direct_path(self):
        import airabs
        geom = dict(width_m=4.0, depth_m=4.0, height_m=3.0, max_order=1, max_taps=4, min_level_db=-60.0)
        taps = room.taps(geom, 0.0, 0.0, 20.0)                    # the source is far outside the 4 m room
        self.assertTrue(taps and all(t['direct_m'] < 20.0 for t in taps))
        calls = []
        real = airabs.apply
        airabs.apply = lambda y, dist, **kw: (calls.append(dist), real(y, dist, **kw))[1]
        try:
            binaural.reflections(np.random.default_rng(0).standard_normal(4000), 0.0, 20.0,
                                 dict(geometry=geom), sr=SR)
        finally:
            airabs.apply = real
        self.assertTrue(calls and all(c > 0 for c in calls))      # the unclamped 20 m made every extra 0 (no air)


class Engine(unittest.TestCase):
    def test_decorrelate_honours_max_delay(self):
        for ms in (0.2, 0.4, 0.5):
            n = ms * SR / 1000.0
            for seed in range(60):
                a = decorrelate._coefficient(seed, ms, SR)
                self.assertLessEqual((1 + a) / (1 - a), n + 1e-9, f'{ms} ms seed {seed}: DC delay over the limit')

    def test_keyframe_inside_a_section_is_measured_from_its_start(self):
        class TM:                                                 # 0.5 s/beat for 16 beats, then 1 s/beat
            def sec(self, b):
                b = np.asarray(b, float)
                return np.where(b <= 16, 0.5 * b, 8.0 + (b - 16.0))
        tm = TM()
        score = dict(ts=[4, 4], plan=dict(sections=[dict(name='B', start_bar=4, start_s=8.0)]))
        t = trajectory.seconds(dict(section='B', bar=3), score, tm)
        self.assertAlmostEqual(t, 16.0, places=6)                 # 8 s start + two 4-beat bars at 1 s/beat

    def test_master_profile_typo_is_an_error_and_highpass_is_resolved(self):
        with self.assertRaises(ValueError):
            master.resolved(dict(master=dict(profile='definitely_not_a_profile')))
        r = master.resolved({})
        self.assertGreater(r['highpass_hz'], 0.0)
        import mix_schema
        self.assertEqual(r['lufs'], mix_schema.master_targets()['default']['lufs'])      # data, not a compiled -14
        y = np.ones((SR, 2)) * 0.2                                # a DC offset: the block removes it at the given cutoff
        a = master._dc_block(y, 'stereo', SR, 24.0)
        b = master._dc_block(y, 'stereo', SR, 0.0)
        self.assertLess(abs(a[-1000:, 0].mean()), 0.01)
        np.testing.assert_allclose(b, y)

    def test_zero_ground_delay_does_not_raise(self):
        x = np.random.default_rng(0).standard_normal(4000).astype(np.float32)
        cfg = dict(spatial.ACOUSTIC_SPACES['outdoor_open'], ground_delay_ms=0.0, lateral_delay_ms=0.0,
                   ceiling_delay_ms=0.0, rear_delay_ms=0.0)
        l, r = spatial.synthesize_early_reflections(x, 30.0, 2.0, cfg, sr=SR)
        self.assertTrue(np.isfinite(l).all() and np.isfinite(r).all())

    def test_bformat_matches_the_engines_ambix(self):
        for az, el in ((90, 0), (30, 20), (-60, 10), (180, 0), (-135, -20)):
            ref = hoa.ambix(binaural.gains(1, az, el))[0]
            got = spatial.encode_ambisonic_bformat(np.ones(1), az, el)[0]
            np.testing.assert_allclose(got, ref, atol=1e-6, err_msg=f'az {az} el {el}')

    def test_bformat_roundtrip_keeps_the_side(self):
        x = np.random.default_rng(5).standard_normal(6000).astype(np.float32)
        out = spatial.decode_ambisonic_to_binaural(spatial.encode_ambisonic_bformat(x, 60.0, 0.0), sr=SR)
        self.assertGreater(float(np.std(out[:, 1])), float(np.std(out[:, 0])))      # +60 is to the right


if __name__ == '__main__':
    unittest.main()
