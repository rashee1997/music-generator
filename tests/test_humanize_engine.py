# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""The engine split and the features added with it, measured rather than trusted.

The first test class is a parity gate: the five hashes freeze what the engine emits for one score, preset, role and
seed, so a refactor that changes a single float fails here. Re-freeze them only for a deliberate change to how the
engine plays, and say in the commit which change it was:

    .venv/bin/python tests/test_humanize_engine.py --update-parity
"""
import hashlib
import io
import json
import os
import re
import sys
import unittest
from unittest import mock

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import humanize as hz                    # noqa: E402
from humanize_engine import config as engine_config   # noqa: E402
from humanize_engine import timemap as engine_timemap  # noqa: E402

# Hashes of the events with every float rounded to PARITY_DECIMALS. The first freeze hashed the raw floats, and those
# differ in the last bits between platforms (libm and SIMD paths): it never matched on Linux, even at the commit that
# froze it. Re-frozen on 26 November 2026 after checking that the split commit (1e6546a) and the tip give identical
# values for all five cases, so the rounding hides platform noise and not a change of behaviour.
PARITY_DECIMALS = 6
PARITY = {
    'natural-melody': '89dfa7ec6de3fe99a381c6b9fd52e665e21e11d1f8e992b62b09d49121806a7f',
    'natural-chord': 'b5346d5a4d77358d8874d24b545e8d71dc127d1fe3d0145779f42e5f04b26d30',
    'loose-bass': '5f8272b5d6d39144a2fb1190e904deb8d5463e9fb797210189a88e5e8e4b90e2',
    'tight-drums': '502f1e9f3481d27c4520141fa65aaa7817b865f875d5f5f612f92f95626521bf',
    'rubato-pad': '9dc94aba7e4c9e43be8929e0cbfa9a5aa1a8232a13ed244d9467ed1d06f71359',
}


def _parity_combos():
    return [
        ('natural-melody', 'natural', 'melody', dict(bpm=96, seed=7), 3),
        ('natural-chord', 'natural', 'chord', dict(bpm=96, seed=7), 4),
        ('loose-bass', 'loose', 'bass', dict(bpm=72, seed=11, rubato=0.02), 5),
        ('tight-drums', 'tight', 'drum', dict(bpm=128, seed=3), 2),
        ('rubato-pad', dict(dict(hz.PRESETS['rubato']), mood='tender'), 'pad',
         dict(bpm=60, seed=9, elastic=dict(amount=0.03, corr_beats=8)), 3),
    ]


def _parity_hashes():
    out = {}
    for name, cfg, role, sc, seed in _parity_combos():
        tm = hz.tempo_map_for(dict(sc, key='D', tracks=[]), seed=seed)
        notes = _line(24, 0.5)
        if role == 'drum':
            notes = [dict(t=i * 0.25, d=0.2, p=[36, 38, 42, 42][i % 4], v=0.8) for i in range(32)]
        ev = hz.humanize_track(notes, tm, cfg, role=role, seed=seed, key='D')
        out[name] = hashlib.sha256(json.dumps(_canonical(ev), sort_keys=True).encode()).hexdigest()
    return out


def update_parity():
    """Re-freeze the hashes. Only for a deliberate change to how the engine plays: say which one in the commit."""
    got = _parity_hashes()
    src = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    for name, h in got.items():
        src = re.sub(r"(?m)^(    '%s': )'[0-9a-f]{64}'," % re.escape(name), r"\1'%s'," % h, src)
    with io.open(os.path.abspath(__file__), 'w', encoding='utf-8', newline='') as fh:
        fh.write(src)
    print('re-froze', ', '.join(sorted(got)))


def _canonical(obj):
    """The events with every float rounded: a value that differs only below the 6th decimal is the same performance."""
    if isinstance(obj, float):
        return round(obj, PARITY_DECIMALS)
    if isinstance(obj, dict):
        return {k: _canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    return obj

FLAT = dict(timing_ms=4, drum_ms=0, lead_ms=0, drift_ms=0, vel_sigma=0, rubato=0.0, wander=0.0,
            strum_ms=0, ritard=0.0, accent=0.0, note_lag1=0.0, vel_dur=0.0, tune_drift_cents=0.0,
            just_ratio=0.0, subdiv_push_ms=0.0, duration_contrast=0.0, double_duration=0.0,
            faster_uphill_ms=0.0, punctuation_ms=0.0, repetition_gap_ms=0.0, high_sharp_cents=0.0,
            vel_lead_ms=0.0, phrase_tempo_vel=0.0, melodic_charge_vel=0.0, melodic_charge_dur=0.0,
            harmonic_charge_vel=0.0, harmonic_charge_dur=0.0, vel_time_couple=0.0, short_share=1.0)


def _line(n=16, step=1.0):
    return [dict(t=i * step, d=step * 0.9, p=57 + (i * 2) % 13, v=0.7) for i in range(n)]


class ParityTests(unittest.TestCase):
    """The split changed no behaviour: same score, preset, role and seed -> the same events."""

    def test_the_five_frozen_outputs(self):
        for name, got in _parity_hashes().items():
            self.assertEqual(got, PARITY[name], f'{name}: the engine output changed')


class StructureTests(unittest.TestCase):
    def test_the_facade_and_the_engine_share_the_same_objects(self):
        self.assertIs(hz.PRESETS, engine_config.PRESETS)
        self.assertIs(hz.TIMING, engine_config.TIMING)
        self.assertIs(hz.TempoMap, engine_timemap.TempoMap)

    def test_no_engine_module_imports_the_facade(self):
        d = os.path.join(HERE, '..', 'scripts', 'humanize_engine')
        bad = []
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.py'):
                continue
            with open(os.path.join(d, fn), encoding='utf-8') as fh:
                text = fh.read()
            if re.search(r'^\s*(import humanize|from humanize import)\b', text, re.M):
                bad.append(fn)
        self.assertEqual(bad, [], f'engine modules import the facade: {bad}')

    def test_both_cache_keys_cover_the_engine_package(self):
        import render_natural as rn
        import stem_gate
        self.assertIn('humanize_engine', rn._RENDER_PACKAGES)
        stem_gate._GATE_CODE = None
        with mock.patch.object(stem_gate.stem_cache, 'code_hash', return_value='h') as m:
            stem_gate._gate_code()
        stem_gate._GATE_CODE = None
        self.assertIn('humanize_engine', m.call_args[0][2])

    def test_unknown_humanize_key_is_an_error(self):
        with self.assertRaises(ValueError):
            hz.resolve({'timing_mss': 5})
        with self.assertRaises(ValueError):
            hz.resolve({'preset': 'not_a_preset'})
        with self.assertRaises(ValueError):
            hz.resolve('not_a_preset')

    def test_a_nested_preset_key_now_selects_the_base(self):
        c = hz.resolve({'preset': 'tight', 'timing_ms': 9})
        self.assertEqual(c['timing_ms'], 9)            # explicit key wins
        self.assertEqual(c['drum_ms'], 2)              # from `tight`, not from natural's 5
        self.assertEqual(hz.resolve('loose')['timing_ms'], 12)


class TempoRelativeTests(unittest.TestCase):
    def _sd(self, bpm, frac):
        tm = hz.TempoMap(bpm, total_beats=30, rubato=0.0, ritard=0.0, wander=0.0)
        ev = hz.humanize_track(_line(16, 1.0), tm, dict(FLAT, timing_beat_frac=frac), role='melody', seed=5, bpm=bpm)
        dev = np.array([e['t'] for e in ev]) - tm.sec([e['beat'] for e in ev])
        return float(dev.std())

    def test_the_spread_follows_the_beat_when_asked(self):
        slow, fast = self._sd(60, 0.03), self._sd(120, 0.03)
        self.assertGreater(slow / fast, 1.6)           # same relative deviation, twice the absolute ms

    def test_off_by_default(self):
        slow, fast = self._sd(60, 0.0), self._sd(120, 0.0)
        self.assertLess(slow / fast, 1.2)

    def test_the_default_changes_nothing(self):
        tm = hz.TempoMap(96, total_beats=30, rubato=0.0, ritard=0.0)
        a = hz.humanize_track(_line(12), tm, dict(FLAT), role='melody', seed=2)
        b = hz.humanize_track(_line(12), tm, dict(FLAT, timing_beat_frac=0.0), role='melody', seed=2)
        self.assertEqual(a, b)


class PocketTests(unittest.TestCase):
    NOTES = ([dict(t=float(i * 2), d=0.4, p=36, v=0.7) for i in range(4)] +
             [dict(t=float(i * 2 + 1), d=0.4, p=38, v=0.7) for i in range(4)] +
             [dict(t=float(i * 0.5), d=0.2, p=42, v=0.7) for i in range(16)])

    def _run(self, cfg):
        tm = hz.TempoMap(96, total_beats=10, rubato=0.0, ritard=0.0)
        return hz.humanize_track(self.NOTES, tm, cfg, role='drum', seed=4,
                                 bpm=96), tm

    def test_laid_back_snare_is_later_and_louder_than_the_hat(self):
        base_cfg = dict(FLAT, drum_ms=0.0, accent=0.0)
        plain, tm = self._run(base_cfg)
        pk, _ = self._run(dict(base_cfg, pocket='laid_back'))
        def dev(ev, pitch):
            rows = [e for e in ev if e['p'] == pitch]
            return np.array([e['t'] - float(tm.sec(e['beat'])) for e in rows]), np.array([e['v'] for e in rows], float)
        sn_t, sn_v = dev(pk, 38)
        ht_t, _ = dev(pk, 42)
        self.assertGreater(float(sn_t.mean()), 0.002)
        self.assertLess(float(ht_t.mean()), float(sn_t.mean()))
        self.assertGreater(float(sn_v.mean()), 90.0)     # the pocket adds level to a laid-back snare
        self.assertEqual(len(plain), len(pk))

    def test_pushed_hat_is_earlier_than_the_snare(self):
        base_cfg = dict(FLAT, drum_ms=0.0, accent=0.0)
        _, tm = self._run(base_cfg)
        ev, _ = self._run(dict(base_cfg, pocket='pushed'))
        hat = [e['t'] - float(tm.sec(e['beat'])) for e in ev if e['p'] == 42]
        snare = [e['t'] - float(tm.sec(e['beat'])) for e in ev if e['p'] == 38]
        self.assertLess(float(np.mean(hat)), float(np.mean(snare)))

    def test_unknown_pocket_is_an_error(self):
        tm = hz.TempoMap(96, total_beats=4)
        with self.assertRaises(ValueError):
            hz.humanize_track(self.NOTES, tm, dict(FLAT, pocket='nope'), role='drum', seed=1)


class SwingDownbeatTests(unittest.TestCase):
    def test_the_on_beat_delays_by_the_configured_ms(self):
        notes = [dict(t=float(i), d=0.4, p=60, v=0.7) for i in range(4)]
        tm = hz.TempoMap(120, total_beats=6, rubato=0.0, ritard=0.0)
        off = hz.humanize_track(notes, tm, dict(FLAT), role='melody', seed=1, bpm=120)
        on = hz.humanize_track(notes, tm, dict(FLAT, swing_downbeat_ms=10.0), role='melody', seed=1, bpm=120)
        d = np.array([b['t'] - a['t'] for a, b in zip(off, on)])
        self.assertTrue(np.allclose(d, 0.010, atol=1e-6))


class AsynchronyTests(unittest.TestCase):
    SCORE = dict(bpm=96, seed=5, key='D', asynchrony=dict(amount_ms=12),
                 tracks=[dict(name='bass', role='bass', instrument='contrabass'),
                         dict(name='vln', role='melody', instrument='violin'),
                         dict(name='kit', role='drum', instrument='drums')])

    def test_the_field_is_signed_and_stable(self):
        a = hz.tempo_map_for(self.SCORE, seed=5)
        b = hz.tempo_map_for(self.SCORE, seed=5)
        self.assertLess(a.asynchrony['bass'], 0.0)
        self.assertGreater(a.asynchrony['vln'], 0.0)
        self.assertEqual(a.asynchrony, b.asynchrony)
        self.assertIsNotNone(a.asynchrony_sig)

    def test_absent_or_zero_means_no_field(self):
        tm = hz.tempo_map_for(dict(self.SCORE, asynchrony=None), seed=5)
        self.assertEqual(tm.asynchrony, {})
        self.assertIsNone(tm.asynchrony_sig)
        tm0 = hz.tempo_map_for(dict(self.SCORE, asynchrony=dict(amount_ms=0.0)), seed=5)
        self.assertEqual(tm0.asynchrony, {})

    def test_a_named_part_gets_its_offset_and_an_unnamed_line_does_not(self):
        tm = hz.tempo_map_for(self.SCORE, seed=5)
        notes = [dict(n, t=n['t'] + 1.0) for n in _line(8)]     # away from bar 1, where a negative onset is clamped
        named = hz.humanize_track(notes, tm, 'natural', role='melody', seed=1, part='vln')
        plain = hz.humanize_track(notes, tm, 'natural', role='melody', seed=1)
        d = float(np.mean([a['t'] - b['t'] for a, b in zip(named, plain)]))
        self.assertAlmostEqual(d, tm.asynchrony['vln'] / 1000.0, places=6)

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            hz.tempo_map_for(dict(self.SCORE, asynchrony=dict(depth=3)), seed=5)


class ReportTests(unittest.TestCase):
    def test_metrics_move_with_the_humanizer_and_a_grid_is_flat(self):
        tm = hz.TempoMap(96, total_beats=30, rubato=0.0, ritard=0.0)
        played = hz.humanize_track(_line(16), tm, 'natural', role='melody', seed=3)
        m = hz.grid_metrics(played, tm)
        self.assertGreater(m['timing_beat_sd'], 0.0)
        self.assertGreater(m['vel_levels'], 1)
        grid = [dict(t=float(tm.sec(i)), dur=0.4, p=60, v=90, beat=float(i)) for i in range(16)]
        flat = hz.grid_metrics(grid, tm)
        self.assertEqual(flat['timing_beat_sd'], 0.0)
        self.assertIsNone(flat.get('timing_lag1'))
        self.assertIsNone(flat.get('swing_bur'))
        self.assertEqual(flat['vel_levels'], 1)

    def test_ensemble_spread_measures_a_known_offset(self):
        tm = hz.TempoMap(96, total_beats=8, rubato=0.0, ritard=0.0)
        a = [dict(t=float(tm.sec(i)), dur=0.4, p=60, v=90, beat=float(i)) for i in range(4)]
        b = [dict(e, t=e['t'] + 0.010) for e in a]
        m = hz.ensemble_metrics({'a': a, 'b': b}, tm)
        self.assertAlmostEqual(m['asynchrony_mean_abs_ms'], 10.0, places=6)
        self.assertEqual(m['parts'], 2)


if __name__ == '__main__':
    if '--update-parity' in sys.argv:
        update_parity()
    else:
        unittest.main()
