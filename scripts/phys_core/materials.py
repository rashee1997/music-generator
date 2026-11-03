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
"""materials.py - what a thing is made of, and what that does to its sound.

A material is data. It is never a sound. Its numbers decide mode frequencies (with geometry.py), how fast each mode
decays (resonate.py), how much high frequency it swallows (porous), how it fails (fracture.py) and how it behaves in
contact (excite.py). A wooden object is not metal with an EQ: it has a different stiffness, a different loss factor,
a different fracture mode and different contact behaviour, and every one of those is a number here.

Units are in the field name where it is not obvious. Every range is a physical plausibility bound, not a taste
judgement: a value outside it is refused, never silently clamped.
"""
import math

FAMILIES = ('brittle', 'fibrous', 'granular', 'membrane', 'absorbent', 'metal')

# field -> (default, low, high, unit, what it does)
SCHEMA = {
    'density':            (700.0,  20.0,    22000.0, 'kg/m3',   'mass per volume; with stiffness it sets the speed of sound'),
    'young_modulus_gpa':  (11.0,   0.0005,  400.0,   'GPa',     'elastic stiffness; sets how high the modes sit'),
    'loss_factor':        (0.02,   0.0003,  0.6,     'eta',     'internal friction; sets how fast a mode dies'),
    'thickness_m':        (0.02,   1e-5,    2.0,     'm',       'the dimension that bends; a thin sheet rings higher'),
    'length_m':           (1.0,    0.001,   50.0,    'm',       'the span that sets the first mode'),
    'width_m':            (0.1,    0.001,   10.0,    'm',       'the other dimension of a plate'),
    'toughness_kpa':      (600.0,  0.1,     60000.0, 'kPa',     'stress at which it fails; brittle fails sooner'),
    'flow_resistivity':   (0.0,    0.0,     500000.0, 'N s/m4', 'porosity: how much air movement it resists (leaves, fabric, soil)'),
    'restitution':        (0.5,    0.02,    0.99,    '-',       'how much speed a bounce keeps'),
    'roughness_beta':     (-1.5,   -3.0,    0.0,     '-',       'friction noise slope: higher magnitude = smoother surface'),
    'damp_exp':           (0.6,    -0.5,    3.0,     '-',       'how much faster the high modes die than the first'),
    'grain_size_m':       (0.005,  1e-5,    0.05,    'm',       'grain or fibre scale; sets the contact time of one grain and its mass'),
}

DEFAULTS = {k: v[0] for k, v in SCHEMA.items()}

# A few real families, as starting points. Room-temperature handbook values, rounded: not answers, anchors.
PRESETS = {
    'oak':      dict(family='fibrous',  density=700,  young_modulus_gpa=11.0,  loss_factor=0.015, toughness_kpa=900,
                     restitution=0.45, roughness_beta=-1.3, damp_exp=0.6),
    'pine':     dict(family='fibrous',  density=500,  young_modulus_gpa=9.0,   loss_factor=0.02,  toughness_kpa=600,
                     restitution=0.4, roughness_beta=-1.3, damp_exp=0.7),
    'glass':    dict(family='brittle',  density=2500, young_modulus_gpa=70.0,  loss_factor=0.001, toughness_kpa=4000,
                     restitution=0.65, roughness_beta=-0.6, damp_exp=0.35),
    'steel':    dict(family='metal',    density=7800, young_modulus_gpa=200.0, loss_factor=0.0005, toughness_kpa=250000,
                     restitution=0.85, roughness_beta=-0.8, damp_exp=0.3),
    'aluminium': dict(family='metal',   density=2700, young_modulus_gpa=69.0,  loss_factor=0.0008, toughness_kpa=150000,
                      restitution=0.8, roughness_beta=-0.8, damp_exp=0.3),
    'leaf_dry': dict(family='membrane', density=400,  young_modulus_gpa=0.02,  loss_factor=0.09, toughness_kpa=40,
                     thickness_m=0.0002, flow_resistivity=12000, restitution=0.2, roughness_beta=-1.0, damp_exp=0.5),
    'leaf_green': dict(family='membrane', density=800, young_modulus_gpa=0.05, loss_factor=0.12, toughness_kpa=120,
                       thickness_m=0.0003, flow_resistivity=9000, restitution=0.2, roughness_beta=-1.1, damp_exp=0.5),
    'gravel':   dict(family='granular', density=1800, young_modulus_gpa=30.0,  loss_factor=0.08, toughness_kpa=200,
                     restitution=0.35, roughness_beta=-0.9, damp_exp=0.9, grain_size_m=0.008),
    'sand_dry': dict(family='granular', density=1600, young_modulus_gpa=0.05,  loss_factor=0.15, toughness_kpa=20,
                     restitution=0.2, roughness_beta=-1.0, damp_exp=1.0, grain_size_m=0.0003),
    'soil':     dict(family='absorbent', density=1300, young_modulus_gpa=0.03, loss_factor=0.2, toughness_kpa=30,
                     flow_resistivity=90000, restitution=0.15, roughness_beta=-0.7, damp_exp=1.0, grain_size_m=0.0005),
    'stone':    dict(family='brittle',  density=2600, young_modulus_gpa=50.0,  loss_factor=0.006, toughness_kpa=8000,
                     restitution=0.55, roughness_beta=-0.7, damp_exp=0.4, grain_size_m=0.002),
    'fabric':   dict(family='absorbent', density=300, young_modulus_gpa=0.01,  loss_factor=0.3, toughness_kpa=50,
                     thickness_m=0.002, flow_resistivity=25000, restitution=0.1, roughness_beta=-1.2, damp_exp=0.8),
    'bark':     dict(family='fibrous',  density=900,  young_modulus_gpa=5.0,   loss_factor=0.05, toughness_kpa=1200,
                     restitution=0.3, roughness_beta=-0.8, damp_exp=0.6),
}


def problems(m, where='material'):
    """Every problem of one material (empty = good). Takes a name, a family, or both."""
    out = []
    if not isinstance(m, dict):
        return [f'{where}: a material is an object of properties (see materials.SCHEMA)']
    if m.get('family') not in FAMILIES:
        out.append(f'{where}.family "{m.get("family")}": use one of {", ".join(FAMILIES)}')
    for k, v in m.items():
        if k in ('family', 'note', 'name'):
            continue
        spec = SCHEMA.get(k)
        if spec is None:
            out.append(f'{where}: unknown property "{k}" (known: {", ".join(sorted(SCHEMA))}, family)')
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            out.append(f'{where}.{k}: needs a number ({spec[3]}), got {v!r}')
        elif not spec[1] <= v <= spec[2]:
            out.append(f'{where}.{k}={v}: outside {spec[1]} to {spec[2]} {spec[3]}')
    return out


def get(m, name=None):
    """A complete material: every field, always. A preset or a scene overrides the defaults, never replaces them."""
    base = dict(DEFAULTS)
    base['family'] = 'fibrous'
    if isinstance(m, str):
        base.update(PRESETS.get(m, {}))
        name = name or m
    elif isinstance(m, dict):
        base.update({k: v for k, v in m.items() if k in SCHEMA})
        if m.get('family'):
            base['family'] = m['family']
    if name:
        base['name'] = name
    return base


def speed_of_sound(m):
    """Longitudinal speed in the material, m/s: sqrt(E / rho)."""
    return math.sqrt(m['young_modulus_gpa'] * 1e9 / max(m['density'], 1e-9))


def t60(f1_hz, m, damp_exp=None):
    """-60 dB time of the first mode from the loss factor: T60 = 2.2 / (f * eta).

    eta is the structural loss factor (2.2 is the usual 6.91/(pi*f) recombination for a lightly damped resonator).
    Clamped to a range a listener would accept as an object rather than a drone or a click.
    """
    eta = max(m['loss_factor'], 1e-5)
    t = 2.2 / (max(f1_hz, 1.0) * eta)
    return min(8.0, max(0.005, t))


def mode_t60(t60_1, ratios, damp_exp=None):
    """Per-mode decay: high modes die faster as a power of the ratio (damp_exp), capped at the render limit."""
    import numpy as np
    keep = np.maximum(np.asarray(ratios, float), 1e-9) ** (-float(0.6 if damp_exp is None else damp_exp))
    return np.clip(float(t60_1) * keep, 0.002, 8.0)


def porous(m):
    """Flow resistivity (N s/m4) if the family absorbs, else 0."""
    return max(0.0, float(m.get('flow_resistivity', 0.0)))


def is_brittle(m):
    return m['family'] in ('brittle', 'metal')


def is_fibrous(m):
    return m['family'] == 'fibrous'


def is_granular(m):
    return m['family'] == 'granular'
