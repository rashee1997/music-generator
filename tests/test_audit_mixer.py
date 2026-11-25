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

"""One test per defect found by the engine audit. Each fails on the code as it was and passes on the fix."""

"""One test per mixer / DSP audit defect. Each fails on the code as it was and passes on the fix."""
import copy
import io
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'tests'))

import deep_merge
import dsp
import loudness
import mix_context
import mix_schema
import mixer
import presets

SR = 44100


def tone(f, secs=1.0, amp=0.3, sr=SR):
    t = np.arange(int(secs * sr)) / sr
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


def stereo(m):
    return np.stack([m, m], 1).astype(np.float32)


class EqAlias(unittest.TestCase):
    def test_slope_filter_accepts_freq_alias(self):
        spec = dict(role='pad', chain='none', eq=[{'type': 'hp', 'freq': 80, 'order': 4}])
        x = stereo(np.random.default_rng(1).standard_normal(SR) * 0.1)
        y = mixer.process_chain('a', x, spec, SR)         # KeyError 'f' before
        self.assertTrue(np.isfinite(y).all())


class Rooms(unittest.TestCase):
    def test_unknown_room_is_an_error(self):
        with self.assertRaises(ValueError) as cm:
            mixer.make_ir('no_such_room_anywhere')
        self.assertIn('hall', str(cm.exception))

    def test_known_names_still_work(self):
        self.assertGreater(len(mixer.make_ir('studio')), 1000)
        self.assertGreater(len(mixer.make_ir('forest_canopy')), 1000)
        cfg = mixer.resolve_space('hall')
        self.assertGreater(len(mixer.make_ir(cfg)), 1000)
        self.assertGreater(len(mixer.make_ir((0.5, 5, 0.6, 0.2))), 1000)


class Lufs(unittest.TestCase):
    def test_meter_error_propagates(self):
        real = dsp.meter

        class Boom:
            def integrated_loudness(self, x):
                raise RuntimeError('meter broke')
        dsp.meter = lambda sr=44100: Boom()
        try:
            with self.assertRaises(RuntimeError):
                mixer.lufs(stereo(tone(440)))
        finally:
            dsp.meter = real

    def test_silence_still_reads_floor(self):
        self.assertEqual(mixer.lufs(np.zeros((SR, 2), np.float32)), -70.0)

    def test_master_of_silence_gets_no_gain(self):
        err = io.StringIO()
        with redirect_stderr(err):
            y = mixer.master_chain(np.zeros((SR * 2, 2), np.float32), dict(lufs=-14.0, true_peak=-1.5), SR)
        self.assertLess(float(np.abs(y).max()), 1e-6)
        self.assertIn('silent', err.getvalue())

    def test_zero_iterations_is_an_error(self):
        mx = copy.deepcopy(mix_context.mix_for('default'))      # a copy: mix_for hands out the shared default
        mx['mastering']['converge']['max_iterations'] = 0
        ctx = mix_context.MixContext(mx, {}, name='t')
        prev = mix_context.current()                  # master_chain installs ctx for this thread: put the old one back
        try:
            with self.assertRaises(ValueError):
                mixer.master_chain(stereo(tone(440, 2)), dict(lufs=-14.0), SR, ctx=ctx)
        finally:
            mix_context.make_current(prev)


class Lra(unittest.TestCase):
    def test_relative_gate_uses_the_power_mean(self):
        # EBU Tech 3342: the gate is 20 LU under the POWER mean. [-20 x4, -44]: power mean -21.0 -> gate -41.0, so
        # -44 is dropped; the old arithmetic mean of dB (-24.8 -> -44.8) kept it and inflated the range.
        # (The audit's [-20, -20, -40] does not separate the two rules: -40 sits above both gates.)
        st = np.array([-20.0, -20.0, -20.0, -20.0, -44.0])
        self.assertEqual(list(loudness.Blocks.lra_gate(st)), [-20.0] * 4)
        old = st[st > float(np.mean(st)) - 20.0]
        self.assertEqual(len(old), 5)

    def test_master_measures_lra_is_blocks_lra(self):
        rng = np.random.default_rng(0)
        x = np.concatenate([stereo(tone(300, 4, 0.02)), stereo(tone(300, 6, 0.4))])
        x = x + (rng.standard_normal(x.shape) * 1e-3).astype(np.float32)
        m = mixer.master_measures(x, SR)
        self.assertAlmostEqual(m['lra'], loudness.Blocks(x, SR).lra(), places=9)


class Multiband(unittest.TestCase):
    def test_uncovered_band_passes_through(self):
        x = stereo(tone(5000) + tone(300))
        y = dsp.multiband_compressor(x, SR, [dict(lo=200, hi=400, threshold_db=-60, ratio=8)])
        spec_in = np.abs(np.fft.rfft(x[:, 0]))
        spec_out = np.abs(np.fft.rfft(y[:, 0]))
        k = int(5000 * len(x) / SR)
        self.assertAlmostEqual(spec_out[k] / spec_in[k], 1.0, delta=0.02)   # 5 kHz was discarded before

    def test_transparent_when_nothing_compresses(self):
        x = stereo(tone(1000) + tone(7000))
        y = dsp.multiband_compressor(x, SR, [dict(lo=100, hi=3000, threshold_db=0, ratio=1)])
        self.assertTrue(np.allclose(x, y, atol=1e-4))


class Transient(unittest.TestCase):
    def test_attack_is_in_db(self):
        env = np.zeros(SR)
        env[SR // 2:SR // 2 + 400] = 1.0
        x = stereo((env * np.sin(2 * np.pi * 1000 * np.arange(SR) / SR) * 0.5).astype(np.float32))
        y = dsp.transient_shaper(x, SR, attack=3.0, sustain=0.0)
        gain_db = 20 * np.log10((np.abs(y).max() + 1e-12) / (np.abs(x).max() + 1e-12))
        self.assertLessEqual(gain_db, 3.05)      # decades x 3 reached 6 dB on a sharp front
        self.assertGreater(gain_db, 2.0)

    def test_zero_is_identity(self):
        x = stereo(tone(300))
        self.assertTrue(np.array_equal(dsp.transient_shaper(x, SR), x))


class RepairClicksWarn(unittest.TestCase):
    def test_broken_import_is_reported(self):
        import builtins
        real = builtins.__import__

        def fake(name, *a, **k):
            if name == 'gate_checks':
                raise ImportError('boom')
            return real(name, *a, **k)
        x = stereo(tone(200, 0.5, 0.2))
        x[10000:, :] += 0.4                                   # a step, so a candidate exists
        err = io.StringIO()
        builtins.__import__ = fake
        try:
            with redirect_stderr(err):
                dsp.repair_clicks(x, SR)
        finally:
            builtins.__import__ = real
        self.assertIn('WARN', err.getvalue())


class Makeup(unittest.TestCase):
    def test_makeup_does_not_lift_the_dry_path(self):
        x = stereo(tone(200, 1.0, 0.5))
        kw = dict(threshold_db=-40, ratio=4, mix=0.5)
        a = dsp.compressor(x, SR, makeup_db=0.0, **kw)
        b = dsp.compressor(x, SR, makeup_db=6.0, **kw)
        wet = dsp.compressor(x, SR, makeup_db=0.0, threshold_db=-40, ratio=4, mix=1.0)
        gain = 10 ** (6 / 20)
        sl = slice(SR // 2, SR)
        # dry fraction unchanged: b = 0.5 x + 0.5 wet gain  ->  b - a = 0.5 wet (gain - 1)
        self.assertTrue(np.allclose((b - a)[sl], 0.5 * wet[sl] * (gain - 1), atol=1e-4))
        self.assertTrue(np.allclose(dsp.compressor(x, SR, makeup_db=6.0, mix=1.0, threshold_db=-40, ratio=4)[sl],
                                    wet[sl] * gain, atol=1e-4))


class SchemaDynamics(unittest.TestCase):
    def test_dynamic_eq_keys_checked(self):
        mx = {'dynamics': {'dynamic_eq': [{'freq': 3000, 'threshold_db': -20}, {'f': 500, 'thresh': -3}, {'q': 1}]}}
        p = mix_schema.validate(mx)
        self.assertTrue(any('thresh' in s and 'unknown key' in s for s in p), p)
        self.assertTrue(any('missing "f"' in s for s in p), p)
        self.assertFalse(any('[0]' in s for s in p), p)          # `freq` is the accepted alias

    def test_mixer_reads_freq_alias(self):
        x = stereo(tone(3000, 1.0, 0.5))
        a = mixer._dsp_dynamics(x, {'dynamic_eq': [{'freq': 3000, 'threshold_db': -40, 'ratio': 8}]}, SR)
        b = mixer._dsp_dynamics(x, {'dynamic_eq': [{'f': 3000, 'threshold_db': -40, 'ratio': 8}]}, SR)
        self.assertTrue(np.array_equal(a, b))

    def test_comp_is_in_the_schema(self):
        self.assertIn('comp', mix_schema.DEFAULTS['dynamics'])
        self.assertEqual(mix_schema.validate({'dynamics': {'comp': {'thr': -20, 'ratio': 3}}}), [])
        p = mix_schema.validate({'dynamics': {'comp': {'thr': -20, 'knee': 3}}})
        self.assertTrue(any('knee' in s for s in p), p)
        self.assertEqual(mix_schema.comp_params({'thr': -10})['ratio'], 2.5)

    def test_plateau_fade_frac_has_a_range(self):
        self.assertTrue(mix_schema.validate({'sidechain': {'plateau_fade_frac': 0.9}}))
        self.assertEqual(mix_schema.validate({'sidechain': {'plateau_fade_frac': 0.25}}), [])

    def test_with_defaults_equals_deep_merge(self):
        over = {'dynamics': {'engine': 'dsp', 'comp': {'thr': -9}}, 'name': 'x', 'role_chains': {'a': {'eq': []}},
                'sidechain': {'band_roles': ['pad']}}
        self.assertEqual(mix_schema.with_defaults(over), deep_merge.merge(mix_schema.DEFAULTS, over))
        self.assertEqual(mix_schema.with_defaults(None), mix_schema.DEFAULTS)


class CacheKey(unittest.TestCase):
    def test_change_between_sampled_frames_changes_the_key(self):
        mx = mix_context.mix_for('default')
        x = stereo(tone(300, 1.0))
        y = x.copy()
        y[5, :] += 0.01                                     # frame 5 is not on the old stride-4 grid
        spec = dict(role='pad')
        self.assertNotEqual(mixer._chain_key('a', x, spec, mx, SR, len(x)),
                            mixer._chain_key('a', y, spec, mx, SR, len(y)))


class Duplication(unittest.TestCase):
    def test_envelope_matches_the_old_recurrence(self):
        rng = np.random.default_rng(2)
        x = (rng.standard_normal((SR, 2)) * np.linspace(0, 1, SR)[:, None] ** 2).astype(np.float32)
        for hold in (False, True):
            got = dsp.envelope(x, SR, 8.0, 150.0, hold_tail=hold)
            mono = np.abs(x).max(1)
            blk = max(1, int(SR // dsp.CONTROL_RATE))
            n = len(mono) // blk + 1
            m = np.pad(mono, (0, n * blk - len(mono))).reshape(n, blk).max(1)
            a = np.exp(-1.0 / (8.0 / 1000.0 * dsp.CONTROL_RATE))
            r = np.exp(-1.0 / (150.0 / 1000.0 * dsp.CONTROL_RATE))
            e = np.zeros(n)
            for i in range(1, n):
                c = a if m[i] > e[i - 1] else r
                e[i] = c * e[i - 1] + (1 - c) * m[i]
            if hold and n > 1:
                e[-1] = e[-2]
            want = np.interp(np.arange(len(mono)), np.arange(n) * blk + blk / 2, e)
            self.assertTrue(np.array_equal(got, want))

    def test_rms_db_is_dsps(self):
        x = np.random.default_rng(3).standard_normal((1000, 2)).astype(np.float32) * 0.1
        self.assertAlmostEqual(mixer.rms_db(x), float(20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12)), places=4)
        self.assertIs(mixer.rms_db, dsp.rms_db)

    def test_one_distance_helper(self):
        x = stereo(tone(4000, 0.5, 0.3))
        sp = dict(distance=8.0)
        y = mixer._distance(x.copy(), {}, sp, 8.0, 1.5, 0.4, 3200.0, 0.18, SR)
        self.assertLess(float(np.abs(y).max()), float(np.abs(x).max()) * mixer._direct_gain(8.0, 0.18) * 1.01)
        self.assertEqual(mixer._direct_gain(0.5, 0.18), 1.0)

    def test_dead_code_is_gone(self):
        for name in ('declick', '_apply_bands', '_peak'):
            self.assertFalse(hasattr(dsp, name), name)
        self.assertFalse(hasattr(mixer, 'pan_stereo'))
        self.assertFalse(hasattr(mixer, '_peak'))


class Loudness(unittest.TestCase):
    def test_einsum_power_equals_matmul(self):
        rng = np.random.default_rng(4)
        k = rng.standard_normal((5000, 8))
        w = rng.uniform(0, 2, 8)
        self.assertTrue(np.allclose(np.einsum('ij,ij,j->i', k, k, w), (k * k) @ w, rtol=1e-12, atol=1e-12))

    def test_blocks_unchanged_by_einsum(self):
        x = np.random.default_rng(5).standard_normal((SR * 2, 6)) * 0.1
        w = np.array([1, 1, 1, 0, 1.4, 1.4])
        z = loudness.Blocks(x, SR, w).z
        k = loudness.k_weight(x, SR)
        power = (k * k) @ w
        c = np.concatenate([[0.0], np.cumsum(power)])
        nb = int(round(loudness.BLOCK_S * SR))
        starts = np.arange(0, len(power) - nb + 1, int(round(loudness.BLOCK_S * 0.25 * SR)))
        self.assertTrue(np.allclose(z, (c[starts + nb] - c[starts]) / nb, rtol=1e-12, atol=1e-15))


class SpaceOwned(unittest.TestCase):
    def test_sibling_directory_is_not_the_shipped_dir(self):
        shipped = presets.SKILL_PRESETS
        self.assertFalse(mix_context.space_owned({'_source': os.path.join(shipped, 'spaces', 'hall.json')}))
        self.assertTrue(mix_context.space_owned({'_source': shipped + '_mine/spaces/x.json'}))   # startswith matched
        self.assertTrue(mix_context.space_owned({'_source': '/tmp/proj/presets/spaces/x.json'}))
        self.assertFalse(mix_context.space_owned({}))


if __name__ == '__main__':
    unittest.main()
