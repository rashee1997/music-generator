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
"""registry.py - what a scene may name.

The registry describes physical *mechanisms*, never finished sounds. There is no `rain`, `footstep` or `glass_break`
entry and there never will be: those are compositions of mechanisms, written in JSON.

    implemented()  derived live from the renderer and sound_model, so the list cannot drift from what runs
    PLANNED        named and staged, but not wired: a scene that names one is refused with its stage

Adding a mechanism means adding it to its module, then moving the name from PLANNED to live. Deleting a name from
PLANNED without implementing it is the one change this file must never take.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import sound_model

from . import render as _render

# still to come (Stages 5-7 of the upgrade); each is refused with its stage until then
PLANNED = (
    ('canopy_scattering', 'propagation', 7, 'measured scattering through a real canopy, not the density estimate'),
    ('ground_impedance', 'propagation', 7, 'porous ground impedance from a measured flow resistivity, not one shelf'),
    ('radiation_directivity', 'resonator', 7, 'an object that radiates unevenly, so orientation changes the tone'),
)

_STAGES = (2, 3, 4, 5, 6, 7)


def implemented():
    """{family: sorted names} from the modules that actually run."""
    return {
        'interaction': sorted(_render.INTERACTIONS),
        'material_family': ['brittle', 'fibrous', 'granular', 'membrane', 'absorbent', 'metal'],
        'geometry': ['bar', 'leaf', 'membrane', 'plate', 'plate_circular', 'string', 'tube'],
        'excite': sorted({'impact', 'burst', 'noise', 'scratch', 'stick_slip', 'rolling', 'flow', 'granular',
                          'stress', 'pulse_train', 'friction_surface', 'turbulence'}),
        'resonator': ['modal', 'porous', 'bubble', 'bandpass', 'none'],
        'events': ['single', 'periodic', 'poisson', 'gamma', 'cluster', 'bounce', 'sequence', 'continuous',
                   'dependency'],
        'voice_law': sorted(sound_model.EXCITE) + sorted(sound_model.RESONATOR),
    }


def planned():
    return list(PLANNED)


def planned_of(family):
    return {name: stage for name, fam, stage, _ in PLANNED if fam == family}


def describe():
    live = implemented()
    lines = ['mechanisms that render today:']
    for fam in ('interaction', 'material_family', 'geometry', 'excite', 'resonator', 'events'):
        lines.append(f'  {fam:15s} ' + ', '.join(live[fam]))
    lines.append('')
    lines.append('legacy voice laws (still accepted in a scene as "voices"):')
    lines.append('  excite    ' + ', '.join(sorted(sound_model.EXCITE)))
    lines.append('  resonator ' + ', '.join(sorted(sound_model.RESONATOR)))
    lines.append('')
    lines.append('staged (a scene naming one is refused with its stage):')
    for stage in _STAGES:
        names = [f'{n} ({fam})' for n, fam, s, _ in PLANNED if s == stage]
        if names:
            lines.append(f'  stage {stage}: ' + ', '.join(names))
    for name, fam, stage, note in PLANNED:
        lines.append(f'    {name:22s} {fam:12s} stage {stage}  {note}')
    return '\n'.join(lines)


def problems():
    out = []
    seen = set()
    for name, fam, stage, note in PLANNED:
        if name in seen:
            out.append(f'planned "{name}" is listed twice')
        seen.add(name)
        if stage not in _STAGES:
            out.append(f'planned "{name}": stage {stage} is not one of {_STAGES}')
        if not note:
            out.append(f'planned "{name}": needs a one-line note')
    for name in seen:
        if name in _render.INTERACTIONS:
            out.append(f'planned "{name}" is already an interaction')
    return out


if __name__ == '__main__':
    bad = problems()
    print('\n'.join(bad) if bad else describe())
    sys.exit(1 if bad else 0)
