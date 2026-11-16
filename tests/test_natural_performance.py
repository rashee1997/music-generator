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

"""The per-note dynamics arch of the SFZ path: a monophonic line carries `sfz_render.note_dyn` on top of the written arc.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import sfz_render

class SfzNoteDynamics(unittest.TestCase):
    def _cc(self, ev, ends, blk, patch='Violin Sustain.sfz'):
        pm = sfz_render.midi_for(ev, ends, blk, lambda t: 1.0, patch)
        return [c for c in pm.instruments[0].control_changes if c.number == 11]

    @staticmethod
    def _val(changes, t):
        return min(changes, key=lambda c: abs(c.time - t)).value

    def test_a_monophonic_line_falls_across_each_note(self):
        ev = [dict(t=0.0, p=60, v=90), dict(t=1.0, p=62, v=90)]
        ch = self._cc(ev, [1.0, 2.0], {'library': 'x', 'patch': 'p', 'cc': 'expression'})
        start, mid, late = self._val(ch, 0.05), self._val(ch, 0.5), self._val(ch, 0.95)
        self.assertGreaterEqual(start, 126)                  # the written level at the note's start
        self.assertLess(mid, start)                          # support eases off while it is held
        self.assertLessEqual(late, mid)                      # and a legato join is not ducked before the next note
        self.assertGreater(late, 78)

    def test_only_a_phrase_end_is_tapered(self):
        # same line, but a rest after the first note: that note lets go over its last 120 ms
        ev = [dict(t=0.0, p=60, v=90), dict(t=1.5, p=62, v=90)]
        ch = self._cc(ev, [1.0, 2.5], {'library': 'x', 'patch': 'p', 'cc': 'expression'})
        self.assertLess(self._val(ch, 0.95), self._val(ch, 0.5) - 1.5)
        self.assertLess(self._val(ch, 0.95), self._val(ch, 0.8) - 0.5)

    def test_a_polyphonic_track_gets_no_arch_and_false_switches_it_off(self):
        ev = [dict(t=0.0, p=60, v=90), dict(t=0.5, p=64, v=90)]
        ch = self._cc(ev, [2.0, 2.5], {'library': 'x', 'patch': 'p', 'cc': 'expression'})
        self.assertTrue(all(c.value == 127 for c in ch))
        ch = self._cc([dict(t=0.0, p=60, v=90)], [2.0],
                      {'library': 'x', 'patch': 'p', 'cc': 'expression', 'note_dyn': False})
        self.assertTrue(all(c.value == 127 for c in ch))

    def test_note_dyn_keys_are_checked(self):
        self.assertTrue(sfz_render.note_dyn({})['enabled'])
        self.assertIsNone(sfz_render.note_dyn({'note_dyn': False}))
        self.assertEqual(sfz_render.note_dyn({'note_dyn': {'release_db': 4.0}})['release_db'], 4.0)
        with self.assertRaises(ValueError):
            sfz_render.note_dyn({'note_dyn': {'hold_db': 1.0}})
        with self.assertRaises(ValueError):
            sfz_render.note_dyn({'note_dyn': 'on'})


if __name__ == '__main__':
    unittest.main()
