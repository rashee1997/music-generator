# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Channel QA is not an AmbiX-only row: every channel count gets the same positive and negative controls.

The controls use one file per case: clean, one bar of one channel lifted, muted, inverted, and a whole-bar
accent. The last one must not be flagged, because it is an arrangement choice, not a channel fault.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import channel_qa                                            # noqa: E402
import render_targets                                        # noqa: E402
import spatial_gate                                          # noqa: E402

SR = 8000
SCORE = dict(title='channel qa control', bpm=120, ts=[4, 4], tracks=[])


def tone(seconds=8.0, channels=4):
    t = np.arange(int(seconds * SR)) / SR
    x = np.repeat((0.2 * np.sin(2 * np.pi * 220.0 * t))[:, None], channels, axis=1)
    return x


def analyse(x, target=None):
    return channel_qa.analyse(SCORE, x, SR, target)


def middle_bar(a):
    return a['edges'][1], a['edges'][2]


class AnyChannel(unittest.TestCase):
    def test_clean_audio_passes_for_an_undeclared_channel_count(self):
        a = analyse(tone(channels=5))
        self.assertEqual(a['kind'], 'channels')
        self.assertIsNone(a['positions'])
        self.assertEqual(a['channels'], 5)
        self.assertEqual(a['conflicts'], [])

    def test_a_one_bar_channel_lift_is_found(self):
        x = tone()
        a0 = analyse(x)
        lo, hi = middle_bar(a0)
        x[lo:hi, 2] *= 4.0
        kinds = [(c['bar'], c['channel'], c['kind']) for c in analyse(x)['conflicts']]
        self.assertIn((2, 3, 'jump'), kinds)

    def test_a_one_bar_channel_dropout_is_found(self):
        x = tone()
        lo, hi = middle_bar(analyse(x))
        x[lo:hi, 2] = 0.0
        kinds = [(c['bar'], c['channel'], c['kind']) for c in analyse(x)['conflicts']]
        self.assertIn((2, 3, 'dropout'), kinds)

    def test_a_one_bar_channel_polarity_flip_is_found(self):
        x = tone()
        lo, hi = middle_bar(analyse(x))
        x[lo:hi, 2] *= -1.0
        kinds = [(c['bar'], c['channel'], c['kind']) for c in analyse(x)['conflicts']]
        self.assertIn((2, 3, 'polarity'), kinds)

    def test_a_whole_bar_accent_is_not_a_channel_fault(self):
        x = tone()
        lo, hi = middle_bar(analyse(x))
        x[lo:hi, :] *= 2.0
        self.assertEqual(analyse(x)['conflicts'], [])

    def test_a_declared_layout_uses_its_speaker_positions(self):
        order = render_targets.get('immersive_5_1')['channel_order']
        a = analyse(tone(channels=len(order)), 'immersive_5_1')
        self.assertEqual(a['kind'], 'layout')
        self.assertEqual(a['channels'], len(order))
        self.assertEqual(len(a['positions']), len(order))
        self.assertIsNone(a['positions'][order.index('LFE')])       # no direction for a low-frequency channel
        self.assertIsNotNone(a['positions'][order.index('FL')])

    def test_order_five_ambix_decodes_to_36_virtual_speakers(self):
        x = np.zeros((int(2.0 * SR), 36))
        x[:, 0] = 0.1 * np.sin(2 * np.pi * 220.0 * np.arange(len(x)) / SR)
        a = analyse(x, 'ambix')
        self.assertEqual(a['kind'], 'ambix')
        self.assertEqual(a['channels'], 36)
        self.assertEqual(a['virtual'], 36)
        self.assertEqual(len(a['positions']), 36)
        self.assertTrue(np.isfinite(a['signals']).all())
        self.assertEqual(a['conflicts'], [])

    def test_one_bar_fault_in_an_acn_channel_is_found(self):
        x = np.zeros((int(8.0 * SR), 36))
        x[:, 0] = 0.1 * np.sin(2 * np.pi * 220.0 * np.arange(len(x)) / SR)
        lo, hi = middle_bar(analyse(x, 'ambix'))
        x[lo:hi, 0] = 0.0
        kinds = [(c['bar'], c['channel_name'], c['kind']) for c in analyse(x, 'ambix')['conflicts']]
        self.assertIn((2, 'ACN0', 'dropout'), kinds)

    def test_ambix_with_the_wrong_channel_count_is_an_error(self):
        with self.assertRaises(channel_qa.ChannelLayoutError):
            channel_qa.prepare(SCORE, np.zeros((100, 35)), SR, 'ambix')


class DeliveredRows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='channel_qa_')

    def tearDown(self):
        for name in os.listdir(self.tmp):
            os.unlink(os.path.join(self.tmp, name))
        os.rmdir(self.tmp)

    def write(self, x, name='master_5_1.wav'):
        path = os.path.join(self.tmp, name)
        sf.write(path, x.astype(np.float32), SR, subtype='PCM_24')
        return path

    def rows(self, path):
        out = []
        spatial_gate.output_rows(dict(SCORE, output_targets=['immersive_5_1']), path, out)
        return {name: (level, detail) for level, name, detail in out}

    def test_clean_5_1_delivery_gets_both_channel_rows(self):
        order = render_targets.get('immersive_5_1')['channel_order']
        rows = self.rows(self.write(tone(channels=len(order))))
        self.assertEqual(rows['channel.virtual'][0], 'PASS')
        self.assertEqual(rows['channel.bars'][0], 'PASS')

    def test_an_isolated_bar_fault_fails_channel_bars(self):
        order = render_targets.get('immersive_5_1')['channel_order']
        x = tone(channels=len(order))
        lo, hi = middle_bar(analyse(x, 'immersive_5_1'))
        x[lo:hi, order.index('FC')] = 0.0
        rows = self.rows(self.write(x))
        self.assertEqual(rows['channel.bars'][0], 'FAIL')
        self.assertIn('FC', rows['channel.bars'][1])


if __name__ == '__main__':
    unittest.main()
