# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or redistribute it
# under the terms of the GNU Affero General Public License as published
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

"""The pitch-class measurement behind `harmonic_concordance`.

It has to read the whole stem (the old single 186 ms frame at the midpoint returned zeros for a bed that sounded
early, and the gate printed that as "0.0% dissonance"), hold a real semitone clash apart from a clean chord, and say
when a bed has no tonal content instead of calling noise concordant.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import naturalness_check as nc  # noqa: E402
import quality_gate as qg  # noqa: E402
from scipy import signal  # noqa: E402

SR = 44100
C, CS, E, G, GS = 261.63, 277.18, 329.63, 392.00, 415.30
C_SHARP_AND_B = [1, 11]                      # the pitch classes a piece in C must not hold


def chord(freqs, sec=6.0, detune_cents=0.0, amp=0.3):
    t = np.arange(int(sec * SR)) / SR
    x = sum(amp * np.sin(2 * np.pi * f * 2 ** (detune_cents / 1200.0) * t) for f in freqs)
    return np.stack([x, x], axis=1)


def noise(sec=6.0, band=None, seed=0):
    x = np.random.default_rng(seed).standard_normal(int(sec * SR))
    if band:
        x = signal.sosfilt(signal.butter(2, band, 'band', fs=SR, output='sos'), x)
    x = 0.3 * x / (np.abs(x).max() + 1e-9)
    return np.stack([x, x], axis=1)


def score(key='C'):
    return {'key': key, 'tracks': [{'name': 'amb', 'role': 'environment', 'instrument': 'env:test'}]}


def rows_for(x, key='C'):
    return qg.chroma_concordance_rows(score(key), None, {'amb': x})


class TheWholeStemIsMeasured(unittest.TestCase):
    def test_a_bed_that_only_sounds_early_is_measured_not_read_as_zero(self):
        """The defect this replaced: a 20 s stem whose bed stops before the midpoint produced an all-zero profile,
        and the gate reported it as 0.0 % dissonance - a pass from no measurement at all."""
        x = np.zeros((int(20 * SR), 2))
        head = chord([C, E, G], 3.0)
        x[:len(head)] = head
        a = nc.chroma_analysis(x, SR)
        self.assertGreater(a['sounding_frames'], 10)                 # the early bed is what was measured
        self.assertLess(a['sounding_frames'], 60)                    # ...and the silence was not counted as signal
        self.assertAlmostEqual(float(a['chroma'].sum()), 1.0, places=6)
        self.assertLess(float(a['chroma'][C_SHARP_AND_B].sum()), 0.05)

    def test_the_profile_is_a_distribution(self):
        a = nc.chroma_analysis(chord([C, E, G]), SR)
        self.assertTrue(np.all(a['chroma'] >= 0.0))
        self.assertAlmostEqual(float(a['chroma'].sum()), 1.0, places=6)


class AClashIsAHundredTimesACleanChord(unittest.TestCase):
    def test_a_semitone_inside_the_chord_reads_far_above_a_clean_triad(self):
        clean = float(nc.chroma_analysis(chord([C, E, G]), SR)['chroma'][C_SHARP_AND_B].sum())
        clash = float(nc.chroma_analysis(chord([C, E, G, CS]), SR)['chroma'][C_SHARP_AND_B].sum())
        self.assertLess(clean, 0.05)
        self.assertGreater(clash, 4 * clean)

    def test_the_row_still_fires_on_a_bed_rooted_a_semitone_from_the_key(self):
        rows = rows_for(chord([CS, GS]))
        self.assertEqual(rows[0][0], 'WARN', rows)
        self.assertIn('dissonant semitone', rows[0][2])

    def test_the_row_passes_a_bed_in_the_key(self):
        rows = rows_for(chord([C, G]))
        self.assertEqual(rows[0][0], 'PASS', rows)
        self.assertIn('sounding frames tonal', rows[0][2])


class TuningDoesNotMoveTheNotes(unittest.TestCase):
    def test_a_band_tuned_to_442_still_reads_c_e_g(self):
        a = nc.chroma_analysis(chord([C, E, G], detune_cents=7.85), SR)
        top = set(np.argsort(a['chroma'])[-3:])
        self.assertEqual(top, {0, 4, 7})
        self.assertLess(abs(a['tuning_cents']), 30.0)

    def test_tuning_is_estimated_and_reported(self):
        self.assertAlmostEqual(nc.chroma_analysis(chord([C, E, G]), SR)['tuning_cents'], 0.0, delta=30.0)


class NoTonalContentIsStatedNotPassed(unittest.TestCase):
    def test_white_noise_has_no_tonal_frames(self):
        a = nc.chroma_analysis(noise(seed=1), SR)
        self.assertEqual(a['tonal_frames'], 0)

    def test_band_limited_noise_is_not_called_tonal(self):
        """Rain is noise in a band, and spectral flatness over the whole spectrum calls that tonal because its energy
        sits in one part of it (measured: rain 0.30-0.45, a chord 0.00-0.02). Peak prominence is what separates them."""
        a = nc.chroma_analysis(noise(band=[400, 3000], seed=2), SR)
        self.assertEqual(a['tonal_frames'], 0)

    def test_a_noise_bed_is_reported_as_not_measurable(self):
        rows = rows_for(noise(band=[400, 3000], seed=2))
        self.assertEqual(rows[0][0], 'INFO', rows)
        self.assertIn('broadband', rows[0][2])

    def test_a_silent_stem_is_not_read_as_concordant(self):
        rows = rows_for(np.zeros((4 * SR, 2)))
        self.assertEqual(rows[0][0], 'INFO', rows)
        self.assertIn('no signal', rows[0][2])

    def test_without_librosa_the_row_says_so(self):
        had = sys.modules.get('librosa')
        sys.modules['librosa'] = None                     # `import librosa` now raises, as on a machine without it
        try:
            self.assertIsNone(nc.chroma_analysis(chord([C, E, G]), SR))
            rows = rows_for(chord([C, E, G]))
        finally:
            if had is None:
                sys.modules.pop('librosa', None)
            else:
                sys.modules['librosa'] = had
        self.assertEqual(rows[0][0], 'INFO', rows)
        self.assertIn('librosa is missing', rows[0][2])


if __name__ == '__main__':
    unittest.main()
