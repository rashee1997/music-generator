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

"""Slurred legato in sfz_render and the unpitched environment track in the tension check."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import sfz_render as R
import pattern_audit as pa

BLK = dict(library='sso', patch='x', cc='none')


def _notes(arts, patch):
    ev = [dict(t=1.0 + 0.5 * i, p=62 + i, v=90, art=a) for i, a in enumerate(arts)]
    offs = [e['t'] + 0.49 for e in ev]
    pm = R.midi_for(ev, offs, BLK, lambda t: .8, patch)
    return pm, pm.instruments[0]


class SlurAndEnvironment(unittest.TestCase):
    """unittest collectable (pytest collects the class too), so one runner covers the whole suite."""

    def test_slur_overlap_glide_and_soft_attack(self):
        pm, ins = _notes(['legato', 'legato', 'legato'], '1st Violins Legato.sfz')
        n = ins.notes
        assert abs(n[0].end - (n[1].start + 0.025)) < 1e-6          # 25 ms overlap into the next attack
        assert n[0].velocity == 90 and n[1].velocity < 90           # first note keeps its bite
        assert pm._slur_onsets == [1.5, 2.0] and ins.pitch_bends[0].pitch < 0

    def test_no_slur_on_staccato_patch_or_non_legato_art(self):
        pm, ins = _notes(['legato', 'legato'], 'Horns Marcato.sfz')
        assert pm._slur_onsets == [] and not ins.pitch_bends
        pm, ins = _notes(['legato', 'staccato'], '1st Violins Legato.sfz')
        assert pm._slur_onsets == []

    def test_environment_note_is_not_harmony(self):
        notes = lambda p: [dict(t=i * 4.0, d=3.5, p=p, v=90) for i in range(8)]
        sc = dict(ts=[4, 4], key='D', mode='phrygian', tracks=[
            dict(name='a', role='melody', notes=notes(62)),
            dict(name='env', role='environment', notes=[dict(t=0.0, d=60.0, p=60, v=80)])])
        rows = pa.spiral_tension_arc(sc)
        assert not any(r[0] == 'FAIL' for r in rows)
