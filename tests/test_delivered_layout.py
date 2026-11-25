# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The gate on the channels that were delivered, not on an assumed stereo master.

Every row here is a positive and a negative control: the same 7.1.2 file, clean once and broken in one place
at a time. `docs/agent_prompt_mix_speed_and_channels.md` Part A item 6 asks for exactly this, because a row
that cannot fail is not a row, and a row that fails a clean delivery is a measurement on the wrong basis.

No threshold is relaxed anywhere: the controls assert which row answers, not that the answer got softer.
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

import gate_audio                                            # noqa: E402
import quality_gate as qg                                     # noqa: E402
import render_targets                                        # noqa: E402
import spatial_gate                                          # noqa: E402

SR = 44100
TARGET = 'immersive_7_1_2'
ORDER = render_targets.get(TARGET)['channel_order']           # FL FR FC LFE BL BR SL SR TFL TFR


def score():
    """A score that asks for 7.1.2 only: the delivered file is the master, there is no stereo beside it."""
    return dict(title='layout control', bpm=120, key='D', ts=[4, 4], tracks=[],
                output_targets=[TARGET],
                master=dict(lufs=-14.0, true_peak=-1.5, lufs_tolerance=2.5))


def stereo_policy_score():
    """The same piece delivered as a two-channel master: the rows must behave exactly as they always did."""
    return dict(title='stereo control', bpm=120, key='D', ts=[4, 4], tracks=[],
                output_targets=['stereo'], master=dict(lufs=-14.0, true_peak=-1.5))


def programme(seconds=2.0, level=0.25, dc=None):
    """A 7.1.2 file: a tone on the front pair, nothing anywhere else unless a control asks for it."""
    t = np.arange(int(seconds * SR)) / SR
    x = np.zeros((len(t), len(ORDER)))
    tone = level * np.sin(2 * np.pi * 220.0 * t)
    x[:, ORDER.index('FL')] = tone
    x[:, ORDER.index('FR')] = tone
    if dc:
        for name, value in dc.items():
            x[:, ORDER.index(name)] += value
    return x


def write(audio, tmp, name='master_7_1_2.wav'):
    path = os.path.join(tmp, name)
    sf.write(path, audio.astype(np.float32), SR, subtype='PCM_24')
    return path


def rows(path, sc=None):
    out = []
    qg.master_extra_rows(sc or score(), path, out)
    return out


def level_of(out, name):
    got = [lvl for lvl, n, _ in out if n == name]
    return got[0] if got else None


def audio_rows(path, sc=None):
    out = []
    qg.audio_checks(path, sc or score(), out)
    return out


class DeliveredLayout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='delivered_layout_')

    def test_a_clean_7_1_2_delivery_passes_clipping_and_dc(self):
        out = rows(write(programme(), self.tmp))
        self.assertEqual(level_of(out, 'clipping'), 'PASS')
        self.assertEqual(level_of(out, 'master.dc'), 'PASS')

    def test_a_clipped_surround_channel_fails_clipping(self):
        x = programme()
        x[:, ORDER.index('SR')] = 1.0                              # pinned on one surround channel only
        out = rows(write(x, self.tmp))
        self.assertEqual(level_of(out, 'clipping'), 'FAIL')
        detail = [d for lvl, n, d in out if n == 'clipping'][0]
        self.assertIn('sample(s) at/above', detail)

    def test_dc_on_a_height_channel_fails_master_dc(self):
        out = rows(write(programme(dc={'TFL': 0.05}), self.tmp))
        self.assertEqual(level_of(out, 'master.dc'), 'FAIL')

    def test_dc_on_the_low_frequency_channel_is_not_a_programme_fault(self):
        # the sub channel carries content below the DC blocker's corner by design; it is not a programme channel
        out = rows(write(programme(dc={'LFE': 0.05}), self.tmp))
        self.assertEqual(level_of(out, 'master.dc'), 'PASS')
        detail = [d for lvl, n, d in out if n == 'master.dc'][0]
        self.assertIn('low-frequency channel', detail)

    def test_the_fold_peak_is_reported_not_failed_on_a_delivered_layout(self):
        # each channel is under the format's own -3.0 dBTP ceiling, but the two-channel fold sums them over the
        # two-channel -1.5 policy: a sum of channels is not a delivery limit
        x = np.zeros((int(2.0 * SR), len(ORDER)))
        t = np.arange(len(x)) / SR
        x[:, ORDER.index('FL')] = 0.68 * np.sin(2 * np.pi * 100.0 * t)
        x[:, ORDER.index('BL')] = 0.32 * np.sin(2 * np.pi * 100.0 * t)
        peaks = [float(np.max(np.abs(x[:, c]))) for c in range(x.shape[1])]
        self.assertLess(max(peaks), 10 ** (-3.0 / 20.0))           # every channel inside the format's ceiling
        out = audio_rows(write(x, self.tmp))
        self.assertNotIn('FAIL', [lvl for lvl, n, _ in out if n == 'true peak'])
        self.assertEqual(level_of(out, 'true peak'), 'INFO')
        detail = [d for lvl, n, d in out if n == 'true peak'][0]
        self.assertIn('delivery.true_peak', detail)

    def test_a_stereo_delivery_still_judges_its_own_peak(self):
        # the same over-peak programme as a two-channel master: nothing about the layout rule may silence this row
        path = os.path.join(self.tmp, 'master.wav')
        t = np.arange(int(2.0 * SR)) / SR
        sf.write(path, (0.98 * np.sin(2 * np.pi * 100.0 * t))[:, None].repeat(2, axis=1).astype(np.float32),
                 SR, subtype='PCM_24')
        out = audio_rows(path, stereo_policy_score())
        self.assertEqual(level_of(out, 'true peak'), 'FAIL')

    def test_the_loudness_row_reads_the_basis_the_master_was_levelled_on(self):
        # a target that asks for bs1770_layout is trimmed on the delivered channels' LKFS: the row must read that,
        # and say so, instead of reading the fold and reporting a correct master as off target
        out = audio_rows(write(programme(level=0.05), self.tmp))
        detail = [d for lvl, n, d in out if n == 'loudness']
        self.assertTrue(detail, msg='the loudness row did not run')
        self.assertIn('BS.1770', detail[0])


class OneTruthAndOneDecode(unittest.TestCase):
    """What the run delivered, and how many times the gate reads it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='delivered_layout_')

    def test_delivered_names_the_target_the_format_and_the_ceiling(self):
        d = render_targets.delivered(score())
        self.assertEqual([x['name'] for x in d], [TARGET])
        self.assertEqual(d[0]['channels'], 10)
        self.assertEqual(d[0]['layout'], 'itu_bs2051_system_i')
        self.assertEqual(d[0]['renderer'], 'spatial')
        self.assertEqual(d[0]['file'], 'master_7_1_2.wav')
        self.assertAlmostEqual(d[0]['true_peak_dbtp'], -3.0)

    def test_the_gate_decodes_the_delivered_file_once(self):
        path = write(programme(), self.tmp)
        gate_audio.clear()
        import soundfile
        calls = {'n': 0}
        real = soundfile.read

        def counting(*a, **k):
            calls['n'] += 1
            return real(*a, **k)

        soundfile.read = counting
        try:
            qg.audio_checks(path, score(), [])
            qg.master_extra_rows(score(), path, [])
            qg.spatial_check(path, score(), [])
        finally:
            soundfile.read = real
        self.assertEqual(calls['n'], 1, msg=f'the delivered file was decoded {calls["n"]} time(s)')

    def test_fold_rows_compare_a_sole_layout_with_its_own_fold(self):
        path = write(programme(), self.tmp)
        out = []
        spatial_gate.fold_rows(score(), None, path, TARGET, out)
        names = [n for _l, n, _d in out]
        self.assertNotIn('fold.reference', names, msg='a delivered layout must not need a stereo master')
        self.assertEqual(level_of(out, 'fold.timbre'), 'PASS')
        detail = [d for _l, n, d in out if n == 'fold.timbre'][0]
        self.assertIn('own two-channel fold', detail)


if __name__ == '__main__':
    unittest.main()
