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
"""test_extraction_effects.py - ambient bed, clicks and effect events measured on a synthetic residual with known content."""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
from extraction import config, effects, knowledge  # noqa: E402

SR = 22050
TOTAL = 14.0
RNG = np.random.default_rng(5)
N = int(TOTAL * SR)
HISS = 0.01


def build():
    b, a = signal.butter(1, 6000 / (SR / 2), 'low')
    hiss = np.stack([signal.lfilter(b, a, RNG.standard_normal(N)) * HISS for _ in range(2)])
    clicks = np.zeros(N)
    pos = RNG.choice(N - 10, int(TOTAL * 5), replace=False)
    for p in pos:
        clicks[p:p + 3] = RNG.choice([-1, 1]) * 0.25
    t = np.arange(int(2.0 * SR)) / SR
    riser = 0.3 * np.sin(2 * np.pi * 300 * (10 ** (1.0 * t / 2.0 * 1.0) - 1) / (np.log(10) / 2.0) * 1.0)    # exponential chirp 300 -> 3000 Hz
    ts = np.arange(int(2.5 * SR)) / SR
    scratch = 0.3 * np.sin(2 * np.pi * (800 * ts + 300 * np.sin(2 * np.pi * 4 * ts))) * (np.sin(2 * np.pi * 8 * ts) > 0)
    fx = np.zeros(N)
    fx[3 * SR:3 * SR + len(riser)] += riser
    fx[9 * SR:9 * SR + len(scratch)] += scratch
    return hiss + clicks[None] + fx[None], hiss, pos


class TestEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load()
        cls.mix, cls.hiss, cls.pos = build()
        cls.res = effects.analyse(cls.mix, SR, [{'id': 'fx_a', 'type': 'riser', 'start_s': 2.5, 'end_s': 5.5},
                                                {'id': 'fx_b', 'type': 'vinyl_scratch', 'start_s': 8.5, 'end_s': 12.0}], cls.cfg)

    def test_bed_level_is_close_to_the_hiss(self):
        true_db = 20 * np.log10(np.sqrt(np.mean(self.hiss ** 2)))
        self.assertAlmostEqual(self.res['bed_info']['level_dbfs'], true_db, delta=4.0)

    def test_click_rate(self):
        self.assertAlmostEqual(self.res['clicks_per_s'], 5.0, delta=1.5)

    def test_two_events_found_at_the_right_times_and_tagged(self):
        ev = self.res['events']
        big = [e for e in ev if e['end_s'] - e['start_s'] > 0.8]
        self.assertEqual(len(big), 2, [(round(e['start_s'], 1), round(e['end_s'], 1)) for e in ev])
        self.assertAlmostEqual(big[0]['start_s'], 3.0, delta=0.35)
        self.assertAlmostEqual(big[1]['start_s'], 9.0, delta=0.35)
        self.assertEqual([e['db_id'] for e in big], ['fx_a', 'fx_b'])

    def test_events_are_named_by_the_rules_file(self):
        big = [e for e in self.res['events'] if e['end_s'] - e['start_s'] > 0.8]
        self.assertEqual(big[0]['features']['kind'], 'riser')
        self.assertEqual(big[1]['features']['kind'], 'vinyl_scratch')

    def test_rule_matching(self):
        rules = knowledge.effect_rules()['rules']
        self.assertEqual(knowledge.classify({'dur_s': 1.0, 'centroid_slope_oct_s': -1.0}, rules), 'tape_stop')
        self.assertEqual(knowledge.classify({}, rules), 'other')


if __name__ == '__main__':
    unittest.main()
