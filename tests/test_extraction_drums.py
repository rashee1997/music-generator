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
"""test_extraction_drums.py - hit discovery, clustering, naming from music_db and per-piece stems on a synthetic kit."""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
from extraction import config, drums  # noqa: E402

SR = 22050
TOTAL = 8.0
RNG = np.random.default_rng(3)


def place(sound, t, n):
    out = np.zeros(n)
    i = int(t * SR)
    out[i:i + len(sound)] = sound[:n - i]
    return out


def kick():
    t = np.arange(int(0.3 * SR)) / SR
    return 0.9 * np.sin(2 * np.pi * (50 * t + 70 * (1 - np.exp(-30 * t)) / 30)) * np.exp(-t / 0.08)


def snare():
    t = np.arange(int(0.25 * SR)) / SR
    b, a = signal.butter(2, [1200 / (SR / 2), 7000 / (SR / 2)], 'band')
    return 0.6 * signal.lfilter(b, a, RNG.standard_normal(len(t))) * np.exp(-t / 0.07) + 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)


def hat():
    t = np.arange(int(0.08 * SR)) / SR
    b, a = signal.butter(2, 7000 / (SR / 2), 'high')
    return 0.25 * signal.lfilter(b, a, RNG.standard_normal(len(t))) * np.exp(-t / 0.015)


# 100 BPM: beat 0.6 s. kick on beats 1,3; snare on 2,4; hat every half beat; kick and hat coincide on the downbeat
KICK_T = [0.0, 1.2, 2.4, 3.6, 4.8, 6.0, 7.2]
SNARE_T = [0.6, 1.8, 3.0, 4.2, 5.4, 6.6]
HAT_T = [round(0.3 * i, 3) for i in range(1, 26)]


def build():
    n = int(TOTAL * SR)
    parts = {'kick': sum(place(kick(), t, n) for t in KICK_T), 'snare': sum(place(snare(), t, n) for t in SNARE_T),
             'hat': sum(place(hat(), t, n) for t in HAT_T)}
    return parts


def sdr(ref, est):
    return 10 * np.log10(np.sum(ref ** 2) / (np.sum((ref - est) ** 2) + 1e-12))


class TestDrums(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load()
        cls.parts = build()
        mono = sum(cls.parts.values())
        cls.perc = np.stack([mono, mono])
        db = [{'id': 'kick_main', 'kind': 'kick', 'centroid_hz': 140}, {'id': 'snare_main', 'kind': 'snare', 'centroid_hz': 1850},
              {'id': 'hat_closed', 'kind': 'hat_closed', 'centroid_hz': 6800}]
        cls.res = drums.extract(cls.perc, SR, db, cls.cfg)

    def test_three_pieces_found_and_named_from_the_database(self):
        self.assertEqual(sorted(self.res['pieces']), ['hat_closed', 'kick_main', 'snare_main'])
        self.assertTrue(all(p['source'] == 'music_db' for p in self.res['pieces'].values()))

    def test_hit_counts_are_close(self):
        got = {k: v['hits'] for k, v in self.res['pieces'].items()}
        for key, truth in (('kick_main', KICK_T), ('snare_main', SNARE_T), ('hat_closed', HAT_T)):
            self.assertAlmostEqual(got[key], len(truth), delta=max(2, len(truth) * 0.25), msg=f'{key}: {got}')

    def test_without_a_database_pieces_get_measured_names(self):
        res = drums.extract(self.perc, SR, [], self.cfg)
        self.assertTrue(all(k.startswith('perc_') for k in res['pieces']))
        self.assertEqual(len(res['pieces']), 3)

    def test_each_stem_resembles_its_drum(self):
        for key, part in (('kick_main', 'kick'), ('snare_main', 'snare'), ('hat_closed', 'hat')):
            s = sdr(self.parts[part], self.res['pieces'][key]['stem'][0])
            base = sdr(self.parts[part], self.perc[0])
            print(f'  {key}: SDR {s:.1f} dB (mix alone {base:.1f})')
            self.assertGreater(s, base + 3.0, key)

    def test_nothing_is_lost(self):
        total = sum(p['stem'] for p in self.res['pieces'].values()) + self.res['unexplained']
        self.assertLess(np.max(np.abs(total - self.perc)), 1e-4)


if __name__ == '__main__':
    unittest.main()
