# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""M2: two low-frequency channels: routing modes, coherence, polarity, delay, crossover flatness, bus integration."""
import os
import sys
import unittest

import numpy as np
from scipy.signal import butter, sosfreqz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

from spatial_engine import bass, config, render  # noqa: E402

SR = 44100
CFG = config.lfe_cfg('lrc_lfe2', None)


def tone(f, seconds=3.0, amp=0.3):
    t = np.arange(int(SR * seconds)) / SR
    return amp * np.sin(2 * np.pi * f * t)


def steady(x):
    return x[SR:2 * SR]


def corr(a, b):
    return float(np.corrcoef(steady(a), steady(b))[0, 1])


class Crossover(unittest.TestCase):
    def test_lr4_low_plus_high_is_flat_within_a_tenth_of_a_db(self):
        for fc in (40.0, 80.0, 120.0):
            sos = butter(2, fc, btype='low', fs=SR, output='sos')
            hos = butter(2, fc, btype='high', fs=SR, output='sos')
            w, hl = sosfreqz(sos, worN=np.geomspace(20, 20000, 400), fs=SR)
            _, hh = sosfreqz(hos, worN=w, fs=SR)
            h = (hl ** 2) + (hh ** 2)                     # two cascaded sections each
            db = 20 * np.log10(np.abs(h))
            self.assertLess(float(np.max(np.abs(db))), 0.1, fc)


class Pair(unittest.TestCase):
    def test_dual_mono_outputs_equal_the_single_bus(self):
        x = tone(60)
        cfg = dict(CFG, mode='dual_mono')
        a, b = bass.lfe_bus_pair([x], [0.0], SR, cfg)
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(np.array_equal(a, bass.lfe_bus([x], SR, cfg)))

    def test_stereo_bass_is_coherent_below_the_corner_and_never_antiphase_inside_the_band(self):
        rho = {}
        for f in (25, 30, 40, 60, 80):
            a, b = bass.lfe_bus_pair([tone(f)], [0.0], SR, CFG)
            rho[f] = corr(a, b)
        self.assertGreater(rho[25], 0.98)
        self.assertGreater(rho[30], 0.97)
        self.assertGreater(min(rho.values()), 0.0)              # decorrelated above the corner, but never opposed
        self.assertLess(rho[80], rho[40])                       # and the decorrelation grows with frequency

    def test_stereo_bass_keeps_equal_levels_and_power(self):
        a, b = bass.lfe_bus_pair([tone(60)], [0.0], SR, CFG)
        ra, rb = np.std(steady(a)), np.std(steady(b))
        self.assertAlmostEqual(20 * np.log10(ra / rb), 0.0, delta=1.0)
        single = bass.lfe_bus([tone(60)], SR, CFG)
        self.assertAlmostEqual(float(np.sqrt(ra ** 2 + rb ** 2) / np.std(steady(single))), 1.0, delta=0.1)

    def test_lfe_pan_sends_a_track_to_one_side(self):
        left, right = bass.lfe_bus_pair([tone(50)], [-1.0], SR, CFG)
        self.assertGreater(np.std(steady(left)), 0.01)
        self.assertLess(np.std(steady(right)), 1e-6)
        left, right = bass.lfe_bus_pair([tone(50)], [1.0], SR, CFG)
        self.assertLess(np.std(steady(left)), 1e-6)

    def test_polarity_and_delay_apply_per_channel(self):
        cfg = dict(CFG, mode='modal_split', polarity=[1, -1], delay_ms=[0.0, 2.0])
        a, b = bass.lfe_bus_pair([tone(30)], [0.0], SR, cfg)
        self.assertLess(corr(a, b), 0.0)                        # a 2 ms delay at 30 Hz is 22 deg; inverted it is opposed
        plain = dict(CFG, mode='modal_split')
        a0, b0 = bass.lfe_bus_pair([tone(30)], [0.0], SR, plain)
        self.assertGreater(corr(a0, b0), 0.99)                  # modal_split alone does not decorrelate

    def test_stopband_guard_holds_on_both_channels(self):
        x = tone(60) + tone(2000, amp=0.3)
        for ch in bass.lfe_bus_pair([x], [0.0], SR, CFG):
            self.assertLess(bass.stopband_leak_db(ch, SR, CFG, reference=x), -30.0)

    def test_unknown_mode_and_negative_delay_are_errors(self):
        with self.assertRaises(ValueError):
            bass.lfe_bus_pair([tone(50)], [0.0], SR, dict(CFG, mode='nope'))
        with self.assertRaises(ValueError):
            bass.lfe_bus_pair([tone(50)], [0.0], SR, dict(CFG, delay_ms=[-1.0, 0.0]))
        with self.assertRaises(ValueError):
            bass.lfe_channels([tone(50)], [0.0], SR, CFG, 3)


class Bus(unittest.TestCase):
    def test_layout_bus_fills_both_lfe_channels_and_leaves_mains_without_bass(self):
        bus = render.LayoutBus('lrc_lfe2', None, SR)
        bus.lfe = dict(bus.lfe, roles=['bass'])
        bus.roles = {'bass'}
        bus.add('bass', tone(50, 2.0), {'role': 'bass'})
        out = bus.result()
        self.assertEqual(out.shape[1], 5)
        self.assertGreater(float(np.std(out[:, 3])), 0.001)
        self.assertGreater(float(np.std(out[:, 4])), 0.001)
        self.assertLess(float(np.std(out[SR // 2:, :3])), 0.02)        # the 50 Hz was taken off the mains by the high-pass

    def test_render_stems_places_stems_on_three_fronts(self):
        stems = {'bass': tone(50, 2.0), 'lead': tone(440, 2.0)}
        specs = {'bass': {'role': 'bass'}, 'lead': {'role': 'lead', 'azimuth': -30.0}}
        out = render.render_stems(stems, 'lrc_lfe2', None, specs=specs, sr=SR)
        self.assertEqual(out.shape[1], 5)
        self.assertGreater(float(np.std(out[:, 0])), float(np.std(out[:, 1])))   # the lead sits left


if __name__ == '__main__':
    unittest.main()
