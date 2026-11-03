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
"""test_extraction_separate.py - voices + harmonic masks on a synthetic stereo mix with known stems: measured SDR per stem."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
from extraction import config, notes, separate, spectrum, voices  # noqa: E402
from extraction.music_db import hz  # noqa: E402

SR = 22050
CENTS = 35.0
TOTAL = 6.0


def tone(midi, start, dur, harm, amp):
    t = np.arange(int(dur * SR)) / SR
    f = hz(midi, CENTS)
    y = sum(a * np.sin(2 * np.pi * f * (h + 1) * t) for h, a in enumerate(harm)) * amp
    y *= np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.03)
    out = np.zeros(int(TOTAL * SR))
    i = int(start * SR)
    out[i:i + len(y)] = y[:len(out) - i]
    return out


def pan(x, p):
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)])


SRC = {  # id: (notes, harmonics, amp, pan)
    'bass': ([(40, 0, 1.5), (43, 1.5, 1.5), (45, 3, 1.5), (40, 4.5, 1.5)], (1, .5, .3, .15, .08), .4, 0.0),
    'lead': ([(72, 0.5, 1.0), (76, 2.0, 1.0), (79, 3.5, 1.0), (76, 5.0, 0.9)], (1, .7, .5, .35, .25, .15, .1), .3, -0.4),
    'pad': ([(52, 0, 6.0), (55, 0, 6.0), (59, 0, 6.0)], (1, .3, .1), .25, 0.5),
}
RANGES = {'bass': (38, 47), 'lead': (70, 81), 'pad': (50, 61)}


def build():
    stems = {k: pan(sum(tone(m, s, d, h, a) for m, s, d in nts), p) for k, (nts, h, a, p) in SRC.items()}
    return stems, sum(stems.values())


def sdr(ref, est):
    ref, est = ref.sum(0), est.sum(0)
    return 10 * np.log10(np.sum(ref ** 2) / (np.sum((ref - est) ** 2) + 1e-12))


def run_pipeline(cfg):
    stems, mix = build()
    pri = {'voices': [{'id': k, 'midi_lo': lo, 'midi_hi': hi, 'spans': [], 'timbre': None} for k, (lo, hi) in RANGES.items()]}
    spec = spectrum.semitone_spectrum(mix.mean(0), SR, CENTS, cfg)
    found, roll = notes.find_notes(spec, pri, cfg)
    vs, left = voices.assign(found, spec, pri, cfg)
    res = separate.separate(mix, SR, vs, spec, CENTS, cfg)
    return stems, mix, vs, left, res


class TestSeparate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load()
        cls.stems, cls.mix, cls.vs, cls.left, cls.res = run_pipeline(cls.cfg)

    def test_every_note_goes_to_its_declared_voice(self):
        for k, (nts, _, _, _) in SRC.items():
            got = {n['midi'] for n in self.vs[k]['notes']}
            self.assertTrue({m for m, _, _ in nts} <= got, f'{k}: {sorted(got)}')

    def test_stems_sum_to_the_mix(self):
        total = sum(self.res['voices'].values()) + self.res['perc'] + self.res['residual']
        self.assertLess(np.max(np.abs(total - self.mix)), 1e-4)

    def test_separation_beats_leaving_the_mix_alone(self):
        for k in SRC:
            s = sdr(self.stems[k], self.res['voices'][k])
            base = sdr(self.stems[k], self.mix)
            print(f'  {k}: SDR {s:.1f} dB (the unseparated mix scores {base:.1f})')
            self.assertGreater(s, base + 6.0, k)

    def test_stereo_image_is_kept(self):
        v = self.res['voices']['lead']
        ratio = np.sum(v[1] ** 2) / np.sum(v[0] ** 2)                     # lead panned left: right channel quieter
        true = np.sum(self.stems['lead'][1] ** 2) / np.sum(self.stems['lead'][0] ** 2)
        self.assertAlmostEqual(10 * np.log10(ratio), 10 * np.log10(true), delta=1.5)


if __name__ == '__main__':
    unittest.main()
