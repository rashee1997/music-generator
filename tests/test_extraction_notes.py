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

#!/usr/bin/env python3
"""test_extraction_notes.py - tuning, semitone spectrum and multi-pitch note finding on a synthetic mix with known notes."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
from extraction import config, notes, spectrum, tuning  # noqa: E402
from extraction.music_db import hz  # noqa: E402

SR = 22050
CENTS = 35.0


def tone(midi, start, dur, total, amp=0.3, harm=(1, .6, .45, .3, .2, .12), cents=CENTS):
    t = np.arange(int(dur * SR)) / SR
    f = hz(midi, cents)
    y = sum(a * np.sin(2 * np.pi * f * (h + 1) * t) for h, a in enumerate(harm))
    y = y * np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.03) * amp
    out = np.zeros(int(total * SR))
    i = int(start * SR)
    out[i:i + len(y)] = y[:len(out) - i]
    return out


# known notes: (midi, start_s, dur_s)
BASS = [(40, 0.0, 1.0), (43, 1.0, 1.0), (45, 2.0, 1.0), (40, 3.0, 1.0)]
LEAD = [(72, 0.5, 0.8), (76, 1.5, 0.8), (79, 2.5, 0.8)]
CHORD = [(52, 0.0, 4.0), (55, 0.0, 4.0), (59, 0.0, 4.0)]


def mix(total=4.0):
    y = np.zeros(int(total * SR))
    for m, s, d in BASS + LEAD + CHORD:
        y += tone(m, s, d, total, amp=0.2 if (m, s, d) in CHORD else 0.3)
    return y


def covered(found, m, s, d):
    """Fraction of the true note's time that notes of the same pitch cover."""
    return sum(max(0.0, min(n['end_s'], s + d) - max(n['start_s'], s)) for n in found if n['midi'] == m) / d


def score(found, truth, need=0.6):
    return sum(covered(found, m, s, d) >= need for m, s, d in truth)


class TestNotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load(sets=['notes.max_poly=6'])
        cls.y = mix()
        cls.pri = {'voices': []}

    def test_tuning_is_found_and_judged_against_the_claim(self):
        c = tuning.estimate_cents(self.y, SR, self.cfg)
        self.assertAlmostEqual(c, CENTS, delta=8)
        self.assertTrue(tuning.resolve(c, 35.0, self.cfg)['agree'])
        self.assertFalse(tuning.resolve(c, -30.0, self.cfg)['agree'])
        r = tuning.resolve(49.0, -49.0, self.cfg)                   # +49 and -49 cents are 2 cents apart on the circle
        self.assertTrue(r['agree'])

    def test_all_known_notes_are_found_with_few_extras(self):
        spec = spectrum.semitone_spectrum(self.y, SR, CENTS, self.cfg)
        found, _ = notes.find_notes(spec, self.pri, self.cfg)
        truth = BASS + LEAD + CHORD
        hit = score(found, truth)
        self.assertGreaterEqual(hit, len(truth) - 1, f'found {hit}/{len(truth)}: {[(n["midi"], round(n["start_s"], 2)) for n in found]}')
        extra = [n for n in found if not any(n['midi'] == m and n['start_s'] < s + d and n['end_s'] > s for m, s, d in truth)]
        self.assertLessEqual(len(extra), 3, f'extra notes: {[(n["midi"], round(n["start_s"], 2)) for n in extra]}')

    def test_wrong_tuning_names_the_wrong_notes(self):
        spec = spectrum.semitone_spectrum(self.y, SR, -50.0, self.cfg)  # a half-semitone off: notes land between rows
        found, _ = notes.find_notes(spec, self.pri, self.cfg)
        self.assertLess(score(found, BASS + LEAD + CHORD), len(BASS + LEAD + CHORD))


if __name__ == '__main__':
    unittest.main()
