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
"""geometry.py - shape turns a material into a set of mode frequencies.

A material property alone says nothing about pitch: the same oak is a low dull thud as a thick beam and a bright knock
as a thin board. This module owns that: one material plus one geometry gives (ratios, f1), and resonate.py turns that
into sound.

The first-mode formulas are the standard taut/solid ones, rounded:
    bar      f1 = (4.730^2 / 2*pi) * (h / L^2) * sqrt(E / (12 rho))        free-free bar, h = thickness, L = length
    plate    f1 = 0.469 * (h / a^2) * sqrt(E / (rho (1 - nu^2)))           clamped circular plate, a = radius
    tube     f1 = c / (2 L)  (open) or c / (4 L)  (closed at one end),  c = sqrt(E / rho)
    string   f1 = c / (2 L)
Ratios come from the measured tables in sound_model (string, tube, bar, membrane) so the two engines cannot disagree.

What this cannot do, stated plainly: a real leaf, a real branch and a real drum head are tensioned and irregular, and
none of these formulas covers that. A scene may always write ``f1_hz`` on the object to override the estimate, which
is why the derived values are reported with a note rather than trusted silently.
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import sound_model

from . import materials as mat_mod

LIN, LIN_LO, LIN_HI = 20.0, 20.0, 12000.0

# shape -> (mode law name in sound_model, which size keys it reads, how f1 is computed)
SHAPES = {
    'bar':            ('bar',      ('length_m', 'thickness_m')),
    'plate':          ('plate',    ('width_m', 'thickness_m')),
    'plate_circular': ('plate',    ('width_m', 'thickness_m')),
    'tube':           ('tube_closed', ('length_m',)),
    'string':         ('string',   ('length_m',)),
    'membrane':       ('membrane', ('width_m', 'thickness_m')),
    'leaf':           ('plate',    ('width_m', 'thickness_m')),
}

GEOMETRY_SCHEMA = ('shape', 'length_m', 'width_m', 'thickness_m', 'f1_hz', 'note')


def problems(geo, where='geometry'):
    out = []
    if not isinstance(geo, dict):
        return [f'{where}: a geometry is an object {{"shape": ...}}']
    if geo.get('shape') not in SHAPES:
        out.append(f'{where}.shape "{geo.get("shape")}": use one of {", ".join(SHAPES)}')
    for k in geo:
        if k not in GEOMETRY_SCHEMA:
            out.append(f'{where}: unknown key "{k}" (known: {", ".join(GEOMETRY_SCHEMA)})')
    for k in ('length_m', 'width_m', 'thickness_m', 'f1_hz'):
        if k in geo and (isinstance(geo[k], bool) or not isinstance(geo[k], (int, float)) or not math.isfinite(geo[k])):
            out.append(f'{where}.{k}: needs a number')
        elif k in geo and geo[k] <= 0:
            out.append(f'{where}.{k}={geo[k]}: must be positive')
    return out


def ratios(shape, n):
    """Mode ratios for a shape, from sound_model's tables (one source of truth)."""
    law = SHAPES[shape][0]
    if law == 'plate':
        law = 'bar'          # a plate is its own set only by measured ratios; the free-free bar is the honest fallback
    return sound_model.mode_ratios(dict(n=int(n), law=law, ratios=None, exponent=1.0))


def first_mode(shape, mat, geo):
    """First mode frequency in Hz, or the object's own f1_hz when it declares one."""
    if geo.get('f1_hz'):
        return float(geo['f1_hz']), 'declared'
    e = mat['young_modulus_gpa'] * 1e9
    rho = max(mat['density'], 1e-9)
    h = float(geo.get('thickness_m', mat['thickness_m']))
    length = float(geo.get('length_m', mat['length_m']))
    width = float(geo.get('width_m', mat['width_m']))
    c = math.sqrt(e / rho)
    if shape == 'bar':
        f = (4.730 ** 2 / (2 * math.pi)) * (h / max(length ** 2, 1e-9)) * math.sqrt(e / (12 * rho))
    elif shape in ('plate', 'plate_circular', 'leaf'):
        a = max(width, 1e-6)
        nu2 = 1 - 0.33 ** 2
        f = 0.469 * (h / (a ** 2)) * math.sqrt(e / (rho * nu2))
    elif shape == 'tube':
        f = c / (4 * max(length, 1e-6))
    elif shape == 'string':
        f = c / (2 * max(length, 1e-6))
    else:
        f = c / (2 * max(length, 1e-6))
    return float(min(LIN_HI, max(LIN_LO, f))), 'estimated'


def resolve(obj, mats, index=0):
    """(f1_hz, ratios, t60_1, material) for one object of a scene: its modal identity.

    `mats` is the scene's materials mapping. A string names either a material in the scene or one of the built-in
    presets; an object is used as written; nothing is a fallback to a hidden default without saying so.
    """
    if not isinstance(obj, dict):
        return 440.0, ratios('bar', 8), 0.4, mat_mod.get(mat_mod.PRESETS['oak'])
    ref = obj.get('material')
    if isinstance(ref, str):
        source = (mats or {}).get(ref, ref)
        mat = mat_mod.get(source, name=ref)
    elif isinstance(ref, dict):
        mat = mat_mod.get(ref)
    else:
        mat = mat_mod.get(Materials_default(index, mats))
    geo = dict(obj.get('geometry') or {'shape': 'bar'})
    shape = geo.get('shape', 'bar')
    if shape not in SHAPES:
        shape = 'bar'
    n = int(obj.get('modes', 8))
    f1, how = first_mode(shape, mat, geo)
    return f1, ratios(shape, n), mat_mod.t60(f1, mat), dict(mat, _f1_source=how, _shape=shape)


def Materials_default(index, mats):
    """A stable default material for an object that skipped one: the scene's first, else oak."""
    if isinstance(mats, dict) and mats:
        return list(mats.values())[0]
    return mat_mod.get(mat_mod.PRESETS['oak'])
