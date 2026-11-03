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

"""Tests for the soul profiles, the soul gate (scripts/soul_check.py), the parametric sound builder and the new cultures.
Run from the skill folder:  python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import compose     # noqa: E402
import fusion     # noqa: E402
import sfx        # noqa: E402
import soul       # noqa: E402
import soul_check  # noqa: E402


class Profiles(unittest.TestCase):
    def test_every_named_culture_has_a_profile(self):
        for c in ('indian', 'carnatic', 'tamil', 'west_african', 'afro_cuban', 'western', 'chinese', 'japanese', 'arabic', 'celtic'):
            self.assertTrue(soul.profile(c)['feel'], c)

    def test_unknown_culture_says_how_to_add_one(self):
        with self.assertRaises(KeyError):
            soul.profile('martian')

    def test_mix_keeps_an_instrument_the_mix_owns(self):
        req = soul.merged(['carnatic', 'tamil', 'arabic'])
        self.assertNotIn('ney', req['avoid_instruments'])
        self.assertNotIn('oud', req['avoid_instruments'])

    def test_breath_and_call_response_are_the_strongest_need(self):
        req = soul.merged(['chinese', 'west_african'])
        self.assertEqual(req['breath_beats'], 2.0)
        self.assertTrue(req['call_response'])


class SoulGate(unittest.TestCase):
    def test_flat_piece_fails_for_missing_ornament(self):
        notes = [dict(t=float(i), d=1.0, p=62 + (i % 5), v=0.6) for i in range(16)]
        score = dict(bpm=100, key='D', tracks=[dict(name='lead', instrument='flute', role='melody', notes=notes)])
        rows = soul_check.check(score, soul.merged(['indian']))
        self.assertTrue(any(r[0] == 'FAIL' and r[1] == 'ornament' for r in rows))

    def test_a_culture_with_no_cadence_fails_western_resolution(self):
        notes = [dict(t=float(i), d=1.0, p=p, v=0.6) for i, p in enumerate([62, 64, 66, 67, 65, 63, 61, 60])]
        score = dict(bpm=100, key='D', tracks=[dict(name='lead', instrument='violin', role='melody', notes=notes)])
        rows = soul_check.check(score, soul.merged(['western']))
        self.assertTrue(any(r[0] == 'FAIL' and r[1] == 'cadence' for r in rows))

    def test_fusion_piece_passes_the_soul_gate(self):
        s = compose.compose({'fusion': ['carnatic', 'tamil', 'arabic'], 'duration_s': 40, 'seed': 11})
        rows = soul_check.check(s, soul.merged(['carnatic', 'tamil', 'arabic']))
        self.assertEqual([r for r in rows if r[0] == 'FAIL'], [])


class Planner(unittest.TestCase):
    def test_carnatic_tamil_arabic_share_a_major_scale(self):
        fp = fusion.plan(['carnatic', 'tamil', 'arabic'])
        self.assertEqual(fp['mode'], 'raga_shankarabharanam')
        self.assertEqual(fp['meter'], 4)
        self.assertIn('hum_formant', fp['roles']['chorus'] + ['hum_formant'])

    def test_chorus_layer_is_added_for_a_singing_culture(self):
        s = compose.compose({'fusion': ['carnatic', 'tamil'], 'duration_s': 30, 'seed': 4})
        self.assertIn('chorus', {t['name'] for t in s['tracks']})


class DynamicSfx(unittest.TestCase):
    def test_spec_builds_a_deterministic_sound(self):
        spec = {'seconds': 1.0, 'layers': [{'kind': 'noise', 'band': [500, 3000], 'env': {'attack': 0.2, 'decay': 0.8}},
                                           {'kind': 'glide', 'f0': 150, 'f1': 900, 'env': {'attack': 0.4, 'decay': 0.6}}]}
        a = sfx.synth(spec, 44100, seed=2)
        b = sfx.synth(spec, 44100, seed=2)
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(np.isfinite(a).all())
        self.assertAlmostEqual(float(np.abs(a).max()), 0.9, places=2)

    def test_unknown_layer_kind_is_an_error(self):
        with self.assertRaises(ValueError):
            sfx.synth({'seconds': 0.5, 'layers': [{'kind': 'laser-beam'}]})


if __name__ == '__main__':
    unittest.main()
