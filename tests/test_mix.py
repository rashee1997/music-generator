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

"""Tests for the mix-congestion rules: mixer.carve_for_lead and quality_gate.masking_rows.
Run from the skill folder:  python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import mixer          # noqa: E402
import quality_gate  # noqa: E402

SR = 44100


def _tone(f, sec=12.0, amp=0.2):
    t = np.arange(int(sec * SR)) / SR
    x = amp * np.sin(2 * np.pi * f * t)
    return np.stack([x, x], 1).astype(np.float32)


class CarveRule(unittest.TestCase):
    def test_beds_get_a_2k_dip_when_a_lead_is_present(self):
        specs = {'lead': dict(role='melody', eq=[]), 'pad': dict(role='pad', eq=[]), 'bass': dict(role='bass', eq=[])}
        mixer.carve_for_lead(specs)
        self.assertTrue(any(d['f'] == 2000 and d['gain'] < 0 for d in specs['pad']['eq']))
        self.assertEqual(specs['bass']['eq'], [])                 # the bass is not a bed in the lead's band

    def test_no_lead_means_no_carve(self):
        specs = {'pad': dict(role='pad', eq=[])}
        mixer.carve_for_lead(specs)
        self.assertEqual(specs['pad']['eq'], [])

    def test_a_user_dip_is_not_doubled(self):
        specs = {'lead': dict(role='melody', eq=[]),
                 'pad': dict(role='pad', eq=[dict(type='peak', f=2000, gain=-4.0, q=1.0)])}
        mixer.carve_for_lead(specs)
        self.assertEqual(len(specs['pad']['eq']), 1)


class MaskingCheck(unittest.TestCase):
    def _score(self):
        return dict(tracks=[dict(name='lead', role='melody'), dict(name='pad', role='pad')])

    def test_pad_on_top_of_the_lead_band_is_flagged(self):
        stems = {'lead': _tone(2000, amp=0.2), 'pad': _tone(2000, amp=0.2)}   # the same 2 kHz energy
        rows = quality_gate.masking_rows(stems, self._score(), SR)
        self.assertTrue(rows and rows[0][0] in ('WARN', 'FAIL'))

    def test_pad_out_of_the_lead_band_passes(self):
        stems = {'lead': _tone(2000, amp=0.2), 'pad': _tone(120, amp=0.2)}   # the pad sits low, far from the lead
        rows = quality_gate.masking_rows(stems, self._score(), SR)
        self.assertEqual(rows[0][0], 'PASS')


if __name__ == '__main__':
    unittest.main()
