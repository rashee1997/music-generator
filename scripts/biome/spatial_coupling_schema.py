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

"""spatial_coupling_schema.py - the validator of a biome preset's `spatial_coupling` block (called by biome.schema.problems).

    "spatial_coupling": {
        "field": {"kind": "diffuse", "emitters": 12, "order": 5, "correlation_target": 0.15},
        "room": {"space": "forest_canopy"},
        "decode_hint": ["stereo", "immersive_7_1", "immersive_3_2"]
    }

`field.emitters` is how many independent emitters a bus that places sources itself (the ambisonic bus, a loudspeaker layout, ADM
objects) gets for each `spatial.field` generator; the stereo hand-over uses `spatial.emitters` (default 2). `room.space` names a
`spaces` preset the emitters are placed in. `decode_hint` lists the formats the author checked, for the report.
"""
import math

KEYS = ('field', 'room', 'decode_hint', 'note')
FIELD_KEYS = ('kind', 'emitters', 'order', 'correlation_target')
# path -> (default, low, high, unit, doc)
NUMBERS = {
    'field.emitters': (12, 2, 64, '-', 'independent emitters per field source on a bus that places sources itself'),
    'field.order': (5, 1, 5, '-', 'ambisonic order the field is meant for (5 is the engine\'s)'),
    'field.correlation_target': (0.2, 0.0, 1.0, '-', 'mean |interchannel correlation| env.diffuse_field compares against (starting value)'),
}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def problems(sc, preset=None):
    if not isinstance(sc, dict):
        return ['spatial_coupling: an object']
    out = [f'spatial_coupling: unknown key "{k}" (known: {", ".join(KEYS)})' for k in sc if k not in KEYS]
    f = sc.get('field')
    if f is not None:
        if not isinstance(f, dict):
            out.append('spatial_coupling.field: an object')
        else:
            out += [f'spatial_coupling.field: unknown key "{k}" (known: {", ".join(FIELD_KEYS)})' for k in f if k not in FIELD_KEYS]
            if f.get('kind', 'diffuse') != 'diffuse':
                out.append('spatial_coupling.field.kind: only "diffuse"')
            for k in ('emitters', 'order', 'correlation_target'):
                if k in f:
                    d, lo, hi, unit, _ = NUMBERS[f'field.{k}']
                    if not _num(f[k]) or not lo <= f[k] <= hi or (k != 'correlation_target' and f[k] != int(f[k])):
                        out.append(f'spatial_coupling.field.{k}={f[k]!r}: a number from {lo} to {hi}')
    r = sc.get('room')
    if r is not None:
        if not isinstance(r, dict) or set(r) - {'space'}:
            out.append('spatial_coupling.room: {"space": "<spaces preset>"}')
        elif 'space' in r:
            import presets
            known = presets.load('spaces')
            if r['space'] not in known:
                out.append(f'spatial_coupling.room.space "{r["space"]}" is not a spaces preset (known: {", ".join(sorted(known))})')
    h = sc.get('decode_hint')
    if h is not None and not (isinstance(h, list) and all(isinstance(x, str) and x for x in h)):
        out.append('spatial_coupling.decode_hint: a list of format names')
    return out
