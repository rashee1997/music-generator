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

import os
import sys
import unittest
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)

import compose
import soundbank as sb
import theory
import world


class TestWorldIntegrity(unittest.TestCase):
    def test_genres_modes_and_grooves(self):
        for g, G in world.GENRES.items():
            self.assertIn(G.get('mode', 'major'), theory.MODES, f"Genre {g} has unknown mode")
            self.assertTrue(G.get('groove') in (None, 'brush', 'soft_pulse') or G['groove'] in theory.GROOVES,
                            f"Genre {g} has unknown groove")
            sc = compose.compose(dict(genre=g, duration_s=24, seed=3))
            for t in sc['tracks']:
                _, _, is_drum = sb.resolve(t['instrument'])
                for n in t['notes']:
                    if is_drum:
                        self.assertIn(n['p'], sb.DRUM_KEYS)
            if world.MICRO.get(sc['meta']['mode']):
                has_micro = any('c' in n for t in sc['tracks'] for n in t['notes'])
                self.assertTrue(has_micro, f"Genre {g} expected microtones")

    def test_rhythm_cycles(self):
        for name, c in world.CYCLES.items():
            for p, d, _ in c['hits']:
                self.assertTrue(0 <= p < c['beats'], f"Cycle {name} hit out of bounds")
                self.assertIn(d, sb.DRUM_KEYS, f"Cycle {name} drum key unknown")

    def test_genre_aliases(self):
        for a, g in world.GENRE_ALIASES.items():
            self.assertIn(g, compose.GENRES, f"Alias {a} points to unknown genre {g}")

    def test_theory_shapes_and_gamaka(self):
        for s in ('ethiopian_tizita_maj', 'ethiopian_bati', 'western_octatonic'):
            self.assertIn(s, world.MODES)
        self.assertEqual(theory.pentatonic_spine([0, 1, 4, 5, 7, 8, 10]), [0, 1, 5, 7, 8])
        gm = theory.apply_gamaka([dict(t=0, d=1, p=62, v=.5), dict(t=1, d=1, p=64, v=.5), dict(t=2, d=1, p=69, v=.5)],
                                 tonic_pc=2, rng=np.random.default_rng(1))
        self.assertNotIn('gl', gm[0])
        self.assertEqual(gm[1].get('gl'), -170)
        self.assertNotIn('gl', gm[2])
        sw = theory.guzheng_sweep(0, 4, 62, world.MODES['chinese_gong'], direction='down')
        self.assertEqual(len(sw), 10)
        self.assertTrue(all(a['t'] < b['t'] for a, b in zip(sw, sw[1:])))
        self.assertEqual(sw[0]['p'], 62 + 12 + 9)


if __name__ == '__main__':
    unittest.main()
