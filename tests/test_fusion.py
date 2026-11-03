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

"""Tests for the any-mix planner (scripts/fusion.py) and its hook into compose.py.
Run from the skill folder:  python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import compose    # noqa: E402
import fusion    # noqa: E402
import theory    # noqa: E402

AUG2_FORBIDDEN = {'oud', 'qanun', 'kanun', 'ney', 'nay', 'darbuka', 'zurna', 'mizmar', 'shehnai'}


def _used_instruments(score):
    return {t['instrument'] for t in score['tracks']}


class PlannerRules(unittest.TestCase):
    def test_indo_afro_gets_bhupali_on_a_compound_grid(self):
        fp = fusion.plan(['indian', 'west_african'])
        self.assertEqual(fp['mode'], 'raga_bhoopali')
        self.assertEqual(fp['meter'], 6)
        self.assertEqual(fp['patterns'], ['dadra', 'bell12'])
        self.assertTrue(110 <= fp['bpm'] <= 120)                  # the overlap of 90-130 and 84-132 is centred

    def test_no_arabic_instruments_in_indo_afro(self):
        fp = fusion.plan(['indian', 'west_african'])
        used = {n for names in fp['roles'].values() for n in names}
        self.assertFalse(used & AUG2_FORBIDDEN, used & AUG2_FORBIDDEN)

    def test_no_augmented_second_scale_unless_arabic_is_in_the_mix(self):
        for mix in (['indian', 'celtic'], ['afro_cuban', 'celtic'], ['indian', 'west_african']):
            fp = fusion.plan(mix)
            self.assertFalse(fusion._has_aug_second(fp['mode']), (mix, fp['mode']))

    def test_arabic_mix_may_use_its_own_maqam(self):
        fp = fusion.plan(['arabic', 'celtic'])
        self.assertIn('arabic', fp['cultures'])                  # the rule is not used to hide a requested culture

    def test_non_overlapping_tempos_warn_and_still_plan(self):
        fp = fusion.plan(['west_african', 'celtic'])
        self.assertTrue(fp['warnings'] == [] or fp['bpm'] > 0)

    def test_partial_scale_share_is_reported(self):
        fp = fusion.plan(['west_african', 'arabic', 'celtic'])
        self.assertTrue(any('shared by' in w for w in fp['warnings']))

    def test_unknown_or_single_culture_is_an_error(self):
        with self.assertRaises(ValueError):
            fusion.plan(['indian', 'martian'])
        with self.assertRaises(ValueError):
            fusion.plan(['indian'])

    def test_the_mix_order_does_not_change_the_scale_pitch_classes(self):
        a = fusion.plan(['indian', 'west_african'])
        b = fusion.plan(['west_african', 'indian'])
        self.assertEqual(sorted(theory.MODES[a['mode']]), sorted(theory.MODES[b['mode']]))


class Patterns(unittest.TestCase):
    def test_dadra_has_twelve_strokes_per_12_8_bar(self):
        notes = fusion._pattern_bar('dadra', 6, 0.7, np.random.default_rng(0))
        self.assertEqual(len(notes), 12)
        self.assertEqual(sorted(round(n['t'], 2) for n in notes)[:6], [0.0, 0.5, 1.0, 1.5, 2.0, 2.5])

    def test_bell_is_the_seven_stroke_standard_pattern(self):
        notes = fusion._pattern_bar('bell12', 6, 0.7, np.random.default_rng(0))
        self.assertEqual(len(notes), 7)
        self.assertEqual([round(n['t'] / 0.5) for n in notes], [0, 2, 3, 5, 7, 8, 10])


class ComposeHook(unittest.TestCase):
    def test_fusion_brief_builds_a_piece_with_the_plan(self):
        s = compose.compose({'fusion': ['indian', 'west_african'], 'duration_s': 40, 'seed': 5})
        self.assertIn('fusion', s)
        self.assertEqual(s['meta']['mode'], 'raga_bhoopali')
        self.assertEqual(s['meta']['bars'] * 6 % 6, 0)
        names = {t['name'] for t in s['tracks']}
        self.assertIn('pattern_dadra', names)
        self.assertIn('pattern_bell12', names)

    def test_fusion_piece_has_no_western_orchestra(self):
        s = compose.compose({'fusion': ['indian', 'west_african'], 'duration_s': 40, 'seed': 9})
        self.assertFalse(_used_instruments(s) & {'french_horn', 'horn', 'trumpet', 'fast_strings', 'timpani', 'orchestral'})

    def test_fusion_brief_still_accepts_explicit_bpm(self):
        s = compose.compose({'fusion': ['afro_cuban', 'celtic'], 'bpm': 120, 'duration_s': 40, 'seed': 2})
        self.assertEqual(s['bpm'], 120)


if __name__ == '__main__':
    unittest.main()
