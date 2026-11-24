# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Controls for the per-bar channel row and the two channel-count rows, at a production sample rate.

Each case here was a real false positive measured on a delivered 7.1 file at 44.1 kHz:

* a clean sustained tone scored -0.96 against its own next bar, because the polarity search's fixed 64-sample
  window is 1.45 ms at 44.1 kHz (the half-period of 345 Hz) and could not reach the periodic peak;
* a 7.1 LFE sitting at -60 dBFS was reported for jumps, dropouts and polarity while the programme ran at
  -25 dBFS, because the only guard was an absolute -60 dBFS with no relation to programme level;
* `imm.surround_ratio` compared four surrounds with three fronts by summing channel means, which reads
  +1.25 dB for an identical per-speaker level and made the -9..-2 dB window unreachable;
* `imm.height_arc` summed seven beds against two heights, a +5.44 dB bias against a correctly mixed 7.1.2 bed.

The controls below prove the faults are gone without the detection being weakened: a genuine one-bar inversion
is still found, a field that really is too diffuse still fails, and a genuinely loud bed still fails the height
ceiling.
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

SR = 44100                       # the rate every delivery is judged at; the old control ran at 8 kHz
SCORE = dict(title='false positive control', bpm=120, ts=[4, 4], tracks=[])


def tone(f, seconds=8.0, ch=4, amp=0.2):
    t = np.arange(int(seconds * SR)) / SR
    return np.repeat((amp * np.sin(2 * np.pi * f * t))[:, None], ch, axis=1)


def harmonic_tone(f=220.0, seconds=8.0, ch=4, amp=0.2):
    """A sustained note with harmonics above 500 Hz: the case a polarity test can actually judge, because the
    waveform repeats across bars and an inversion flips every partial at once, while a delay does not."""
    t = np.arange(int(seconds * SR)) / SR
    x = sum((1.0 / k) * np.sin(2 * np.pi * f * k * t) for k in range(1, 10))
    x = x / np.max(np.abs(x)) * amp
    return np.repeat(x[:, None], ch, axis=1)


def analyse(x, target=None):
    return channel_qa.analyse(SCORE, x, SR, target)


def kinds(a, kind):
    return [(c['bar'], c['channel'], c['channel_name']) for c in a['conflicts'] if c['kind'] == kind]


def second_bar(a):
    return a['edges'][1], a['edges'][2]


class Polarity(unittest.TestCase):
    def test_a_clean_sustained_tone_is_not_a_polarity_fault(self):
        for f in (55.0, 73.0, 110.0, 220.0, 880.0):
            with self.subTest(hz=f):
                self.assertEqual(kinds(analyse(tone(f)), 'polarity'), [])

    def test_a_clean_noise_bed_is_not_a_polarity_fault(self):
        rng = np.random.default_rng(3)
        x = rng.standard_normal((int(8.0 * SR), 4)) * 0.05
        self.assertEqual(kinds(analyse(x), 'polarity'), [])

    def test_a_genuine_one_bar_inversion_is_still_found(self):
        x = harmonic_tone(220.0)
        lo, hi = second_bar(analyse(x))
        x[lo:hi, 2] *= -1.0
        found = [(b, ch) for b, ch, _ in kinds(analyse(x), 'polarity')]
        self.assertIn((2, 3), found)

    def test_a_pure_low_tone_inversion_is_not_claimed(self):
        # A 73 Hz sine "inverted" is a half-period delay: the same waveform, one 6.8 ms shift apart. Polarity is
        # only decidable where a bar has a waveform above 500 Hz, so the row says nothing instead of guessing.
        x = tone(73.0)
        lo, hi = second_bar(analyse(x))
        x[lo:hi, 2] *= -1.0
        self.assertEqual(kinds(analyse(x), 'polarity'), [])

    def test_a_genuine_inversion_of_a_harmonic_note_is_found_at_any_pitch(self):
        # 220 Hz and up: a note low enough to leave only a few partials above 500 Hz can be genuinely
        # ambiguous (an inverted copy and a delayed one cannot be told apart), and the row then says nothing
        # rather than guess. That is the documented limit, measured in test_a_pure_low_tone_inversion_is_not_claimed.
        for f in (220.0, 440.0):
            with self.subTest(hz=f):
                x = harmonic_tone(f)
                lo, hi = second_bar(analyse(x))
                x[lo:hi, 2] *= -1.0
                found = [(b, ch) for b, ch, _ in kinds(analyse(x), 'polarity')]
                self.assertIn((2, 3), found)

    def test_one_bar_of_unrelated_noise_is_not_an_inversion(self):
        # Two bars of a noise bed share no waveform, so an inverted copy of one bar is indistinguishable from a
        # fresh noise bar. The row must not call that an inversion.
        rng = np.random.default_rng(7)
        x = rng.standard_normal((int(8.0 * SR), 4)) * 0.05
        lo, hi = second_bar(analyse(x))
        x[lo:hi, 2] *= -1.0
        self.assertEqual(kinds(analyse(x), 'polarity'), [])

    def test_a_bar_on_another_note_is_not_a_polarity_fault(self):
        # A pedal that changes pitch at the bar line is an arrangement, not an inverted channel: the bar and its
        # neighbours share no periodic structure, so their correlation says nothing about polarity.
        x = tone(73.0)
        lo, hi = second_bar(analyse(x))
        t = np.arange(hi - lo) / SR
        x[lo:hi, 2] = 0.2 * np.sin(2 * np.pi * 58.27 * t)
        self.assertEqual(kinds(analyse(x), 'polarity'), [])

    def test_a_low_frequency_channel_is_not_judged_for_polarity(self):
        order = render_targets.get('immersive_7_1')['channel_order']
        x = tone(70.0, ch=len(order))
        lo, hi = second_bar(analyse(x, 'immersive_7_1'))
        x[lo:hi, order.index('LFE')] *= -1.0
        self.assertNotIn('LFE', [n for _, _, n in kinds(analyse(x, 'immersive_7_1'), 'polarity')])


class Levels(unittest.TestCase):
    def test_a_channel_that_is_quiet_throughout_is_not_a_channel_fault(self):
        # What a 7.1 LFE looked like on a delivered file: -60 dBFS in every bar, with 20 dB of wobble between
        # bars. That is an empty channel, not a channel with faults, and it produced 29 of 33 reported faults.
        x = tone(220.0)
        lo, hi = second_bar(analyse(x))
        x[:, 3] *= 3e-3                           # about -50 dB under the programme, in every bar
        x[lo:hi, 3] *= 2.0                        # a per-bar wobble inside the empty channel
        found = {c['kind'] for c in analyse(x)['conflicts'] if c['channel'] == 4}
        self.assertEqual(found, set())

    def test_a_loud_channel_still_reports_a_real_dropout(self):
        x = tone(220.0)
        lo, hi = second_bar(analyse(x))
        x[lo:hi, 3] = 0.0
        found = {(c['bar'], c['channel'], c['kind']) for c in analyse(x)['conflicts']}
        self.assertIn((2, 4, 'dropout'), found)

    def test_a_loud_channel_still_reports_a_real_jump(self):
        x = tone(220.0)
        lo, hi = second_bar(analyse(x))
        x[lo:hi, 3] *= 4.0
        found = {(c['bar'], c['channel'], c['kind']) for c in analyse(x)['conflicts']}
        self.assertIn((2, 4, 'jump'), found)


class ImmersiveRatios(unittest.TestCase):
    def _rows(self, audio, target, filename):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, filename)
        sf.write(path, audio, SR)
        out = []
        spatial_gate.output_rows(dict(title='ratio control', piece_type='cinematic',
                                      output_targets=[target]), path, out)
        return {name: (level, detail) for level, name, detail in out}

    def _layout_noise(self, target, gains):
        order = render_targets.get(target)['channel_order']
        rng = np.random.default_rng(11)
        x = rng.standard_normal((int(3.0 * SR), len(order))) * 0.05
        for name, gain in gains.items():
            x[:, order.index(name)] *= gain
        return x

    @staticmethod
    def _value(detail, after):
        return float(detail.split(after)[1].split('dB')[0])

    def test_surrounds_three_db_down_pass_without_a_channel_count_bias(self):
        x = self._layout_noise('immersive_7_1',
                               {'BL': 0.7079, 'BR': 0.7079, 'SL': 0.7079, 'SR': 0.7079})
        level, detail = self._rows(x, 'immersive_7_1', 'master_7_1.wav')['imm.surround_ratio']
        self.assertEqual(level, 'PASS', detail)
        self.assertAlmostEqual(self._value(detail, 'surround energy'), -3.0, delta=0.6)

    def test_a_field_with_surrounds_at_front_level_is_measured_without_bias(self):
        # 0 dB per speaker is outside the -9..-2 window, and must still be reported as 0 dB, not +1.25 dB.
        x = self._layout_noise('immersive_7_1', {})
        level, detail = self._rows(x, 'immersive_7_1', 'master_7_1.wav')['imm.surround_ratio']
        self.assertEqual(level, 'FAIL', detail)
        self.assertAlmostEqual(self._value(detail, 'surround energy'), 0.0, delta=0.4)

    def test_a_far_too_quiet_surround_field_still_fails(self):
        x = self._layout_noise('immersive_7_1',
                               {'BL': 0.1, 'BR': 0.1, 'SL': 0.1, 'SR': 0.1})
        level, detail = self._rows(x, 'immersive_7_1', 'master_7_1.wav')['imm.surround_ratio']
        self.assertEqual(level, 'FAIL', detail)

    def test_heights_six_db_down_pass_in_7_1_2(self):
        x = self._layout_noise('immersive_7_1_2', {'TFL': 0.5012, 'TFR': 0.5012})
        level, detail = self._rows(x, 'immersive_7_1_2', 'master_7_1_2.wav')['imm.height_arc']
        self.assertEqual(level, 'PASS', detail)
        self.assertAlmostEqual(self._value(detail, 'height channels'), -6.0, delta=0.6)

    def test_heights_at_bed_level_still_fail_the_ceiling(self):
        x = self._layout_noise('immersive_7_1_2', {})
        level, detail = self._rows(x, 'immersive_7_1_2', 'master_7_1_2.wav')['imm.height_arc']
        self.assertEqual(level, 'FAIL', detail)


if __name__ == '__main__':
    unittest.main(verbosity=2)
