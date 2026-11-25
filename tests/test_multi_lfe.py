# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""M1: the engine finds low-frequency speakers by their `lfe` flag, never by the name "LFE"."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import loudness  # noqa: E402
from spatial_engine import bass, config, master  # noqa: E402

SR = 44100


def _old_lfe_bus(sends, sr, cfg):
    """The single-channel bus exactly as it was before the pair existed (reference for byte identity)."""
    cutoff = float(cfg.get('lowpass_hz'))
    gain = bass.send_gain(cfg.get('send_db', 0.0))
    n = max((len(s) for s in sends), default=0)
    out = np.zeros(n, dtype=np.float64)
    for s in sends:
        out[:len(s)] += bass.lowpass(s, sr, cutoff) * gain
    return bass.release_fade(bass.guard(out, sr, cfg), sr, cfg)


class MultiLfe(unittest.TestCase):
    def test_every_layout_reports_its_flagged_speakers(self):
        for name, lay in config.layouts().items():
            flagged = [sp['name'] for sp in lay.get('speakers') or [] if sp.get('lfe')]
            self.assertEqual(config.lfe_names(name), flagged, name)

    def test_existing_layouts_keep_one_lfe(self):
        for name in ('itu_bs2051_system_b', 'itu_bs2051_system_c', 'itu_bs2051_system_d', 'itu_bs2051_system_h',
                     'itu_bs2051_system_i', 'itu_bs2051_system_j'):
            self.assertEqual(config.lfe_names(name), ['LFE'], name)

    def test_new_layouts_are_valid(self):
        self.assertEqual(config.problems('lrc_lfe1'), [])
        self.assertEqual(config.problems('lrc_lfe2'), [])
        self.assertEqual(config.channel_names('lrc_lfe2'), ['L', 'R', 'C', 'LFE1', 'LFE2'])
        self.assertEqual(config.lfe_names('lrc_lfe2'), ['LFE1', 'LFE2'])
        self.assertEqual([round(sp['azimuth']) for sp in config.speakers('lrc_lfe2')], [-30, 30, 0])

    def test_loudness_weights_exclude_every_lfe(self):
        w = loudness.weights_for('lrc_lfe2')
        self.assertEqual(list(w[3:]), [0.0, 0.0])
        self.assertTrue(np.all(w[:3] > 0))

    def test_dc_block_keeps_both_lfe_bands_and_cleans_mains(self):
        n = SR * 2
        x = np.full((n, 5), 0.2, dtype=np.float32)           # a pure offset on every channel
        y = master._dc_block(x, 'lrc_lfe2', SR, 24.0)
        self.assertLess(abs(float(y[SR:, :3].mean())), 0.02)  # mains: the offset is gone
        self.assertTrue(np.allclose(y[:, 3:], 0.2))           # LFE1 and LFE2 untouched (not matched by name "LFE")

    def test_single_lfe_bus_is_byte_identical_to_the_old_one(self):
        rng = np.random.default_rng(3)
        sends = [rng.standard_normal(SR) * 0.1, rng.standard_normal(SR // 2) * 0.1]
        cfg = config.lfe_cfg('itu_bs2051_system_h', 'immersive_7_1')
        self.assertTrue(np.array_equal(bass.lfe_bus(sends, SR, cfg), _old_lfe_bus(sends, SR, cfg)))
        self.assertTrue(np.array_equal(bass.lfe_channels(sends, [0.0, 0.0], SR, cfg, 1)[0],
                                       _old_lfe_bus(sends, SR, cfg)))


if __name__ == '__main__':
    unittest.main()
