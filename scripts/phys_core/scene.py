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
"""scene.py - the physical sound scene: one schema for ambience and for one-hit effects.

    python scripts/physical.py laws                      # what a scene may name
    python scripts/physical.py check  scene.json         # every problem, render nothing
    python scripts/physical.py render scene.json --out x.wav

A scene says what is physically happening: which sources excite which objects, made of which materials, in which order,
and how that travels to a listener. It never says "play the rain effect". Two shapes are accepted, and the first is the
older one so nothing written before this module stopped working:

    voices     a stack of excitation -> resonator -> events (sound_model.py), byte for byte the old renderer
    timeline   objects, materials and interactions (render.py) - the physical scene

    {
      "seconds": 4.0,
      "calibration": {"normalize": "energy", "level_db": -12},
      "materials": {"oak": {"family": "fibrous", "density": 700, "young_modulus_gpa": 11}},
      "objects": {"limb": {"material": "oak", "geometry": {"shape": "bar", "length_m": 1.2,
                                                           "thickness_m": 0.03}, "modes": 10}},
      "timeline": [{"at": 0.2, "interaction": "impact", "target": "limb", "velocity_m_s": 2.4,
                    "then": [{"offset": 0.3, "interaction": "fracture", "target": "limb"}]}],
      "propagation": {"distance_m": 8.0, "atmosphere": {"temp_c": 18, "rh": 70}},
      "spatial": {"azimuth": -20}
    }

`then` is a dependency edge: an event that starts after another one. That is what makes a ten-stage branch break data
instead of a function. Every stage is optional and every interaction is a mechanism (render.INTERACTIONS), so an unseen
sound is a new JSON file, not a new Python file.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import sound_model

from . import calibrate, geometry, materials, propagate, render

SR = sound_model.SR
SCHEMA_VERSION = 2

LIVE = ('seconds', 'voices', 'note', 'free', 'calibration',
        'materials', 'objects', 'sources', 'timeline', 'propagation', 'spatial')
PROPAGATION_KEYS = ('distance_m', 'atmosphere', 'canopy_density', 'ground_gain', 'ground_delay_ms', 'ground_cutoff_hz',
                    'occluder')
OCCLUDER_KEYS = ('material', 'thickness_m', 'edge_offset_m', 'coverage', 'transmission', 'distance_m')
SPATIAL_KEYS = ('azimuth', 'elevation', 'distance_m')
SOURCE_KEYS = ('mechanism', 'speed_m_s', 'corner_hz', 'intensity', 'band_low', 'band_high')
ACTION_KEYS = ('at', 'after', 'offset', 'for', 'duration_s', 'interaction', 'target', 'object', 'surface', 'source',
               'then', 'gain', 'velocity_m_s', 'mass_kg', 'stiffness_pa_m', 'efficiency', 'restitution', 'gap_s',
               'count', 'speed_m_s', 'beta', 'band_low', 'band_high', 'slip_hz', 'depth', 'energy_j', 'rate_hz',
               'strain', 'creep', 'brittle', 'fragments', 'piece_count', 'settle', 'settle_s', 'settle_rate_hz',
               'cadence_spm', 'leaf_count', 'corner_hz', 'intensity', 'crack_pitch', 'modes', 'material', 'geometry',
               'grain_rate_hz', 'contact_hz', 'note')


def model_of(scene):
    """The part sound_model renders: the legacy voice subset, with the scene-only keys removed."""
    return {k: v for k, v in scene.items() if k in ('seconds', 'voices', 'note', 'free')}


# A mechanism that keeps sounding for as long as the scene lasts, as opposed to one that fires and stops.
# This is what makes a scene a place (a bed) rather than a moment (a spot); it is read off the timeline,
# never guessed from a preset name.
CONTINUOUS = ('repeated_impact', 'flow', 'granular', 'rolling', 'gait', 'foliage')


def is_continuous(scene):
    """True when the timeline keeps sounding: any action (or a `then` child) uses a continuous mechanism.
    A scene of single impacts, creaks or a fracture is a moment, not a bed."""
    def walk(acts):
        for a in acts or []:
            if not isinstance(a, dict):
                continue
            if a.get('interaction', 'impact') in CONTINUOUS:
                return True
            if walk(a.get('then')):
                return True
        return False
    return walk((scene or {}).get('timeline'))


# ------------------------------------------------------------------------------------------------ validation
def _action_problems(act, where):
    out = []
    if not isinstance(act, dict):
        return [f'{where}: a timeline entry is an object (interaction, target, at)']
    for k in act:
        if k not in ACTION_KEYS:
            out.append(f'{where}: unknown key "{k}" (known: {", ".join(sorted(ACTION_KEYS))})')
    kind = act.get('interaction', 'impact')
    if kind not in render.INTERACTIONS:
        out.append(f'{where}.interaction "{kind}": use one of {", ".join(render.INTERACTIONS)}')
    for k in ('at', 'after', 'offset', 'for', 'duration_s', 'gain'):
        if k in act and (isinstance(act[k], bool) or not isinstance(act[k], (int, float))):
            out.append(f'{where}.{k}: needs a number')
    for j, child in enumerate(act.get('then') or []):
        out += _action_problems(child, f'{where}.then[{j}]')
    return out


def problems(scene):
    """Every problem of a scene (empty = good). Unknown keys, bad ranges, unknown materials and interactions."""
    if not isinstance(scene, dict):
        return ['a scene is an object {"seconds": ..., "objects": {...}, "timeline": [...]} (see phys_core/scene.py)']
    out = []
    for k in scene:
        if k not in LIVE:
            out.append(f'scene: unknown key "{k}" (known: {", ".join(sorted(LIVE))})')
    sec = scene.get('seconds', 1.0)
    if isinstance(sec, bool) or not isinstance(sec, (int, float)) or not 0.02 <= sec <= 3600:
        out.append(f'scene.seconds={sec!r}: use a number from 0.02 to 3600')

    mats = scene.get('materials') or {}
    if not isinstance(mats, dict):
        out.append('scene.materials: an object of named materials')
        mats = {}
    for name, m in mats.items():
        out += materials.problems(m, f'materials.{name}')

    objs = scene.get('objects') or {}
    if not isinstance(objs, dict):
        out.append('scene.objects: an object of named objects')
        objs = {}
    for name, obj in objs.items():
        if not isinstance(obj, dict):
            out.append(f'objects.{name}: an object {{"material": ..., "geometry": {{...}}}}')
            continue
        for k in obj:
            if k not in ('material', 'geometry', 'modes', 'strike', 'note'):
                out.append(f'objects.{name}: unknown key "{k}" (known: material, geometry, modes, strike, note)')
        out += geometry.problems(obj.get('geometry') or {}, f'objects.{name}.geometry')
        ref = obj.get('material')
        if isinstance(ref, str) and ref not in mats and ref not in materials.PRESETS:
            out.append(f'objects.{name}.material "{ref}": no such material in the scene or the built-in set '
                       f'({", ".join(sorted(materials.PRESETS))})')
        if 'modes' in obj and (not isinstance(obj['modes'], int) or not 1 <= obj['modes'] <= 48):
            out.append(f'objects.{name}.modes: an integer from 1 to 48')

    srcs = scene.get('sources') or {}
    if not isinstance(srcs, dict):
        out.append('scene.sources: an object of named sources')
    else:
        for name, s in srcs.items():
            if not isinstance(s, dict):
                out.append(f'sources.{name}: an object {{"mechanism": ...}}')
                continue
            for k in s:
                if k not in SOURCE_KEYS:
                    out.append(f'sources.{name}: unknown key "{k}" (known: {", ".join(SOURCE_KEYS)})')

    tl = scene.get('timeline')
    if tl is not None:
        if not isinstance(tl, list) or not tl:
            out.append('scene.timeline: a non-empty list of interactions')
        else:
            for i, act in enumerate(tl):
                out += _action_problems(act, f'timeline[{i}]')

    cal = scene.get('calibration')
    if cal is not None:
        out += calibrate.problems(cal)

    prop = scene.get('propagation')
    if prop is not None:
        if not isinstance(prop, dict):
            out.append('scene.propagation: an object {"distance_m": ..., "atmosphere": {...}}')
        else:
            for k in prop:
                if k not in PROPAGATION_KEYS:
                    out.append(f'propagation: unknown key "{k}" (known: {", ".join(PROPAGATION_KEYS)})')
            if 'distance_m' in prop and (prop['distance_m'] <= 0):
                out.append('propagation.distance_m: must be positive')
            occ = prop.get('occluder')
            if occ is not None:
                if not isinstance(occ, dict):
                    out.append('propagation.occluder: an object {"material": ..., "thickness_m": ..., '
                               '"edge_offset_m": ..., "coverage": 0..1}')
                else:
                    for k in occ:
                        if k not in OCCLUDER_KEYS:
                            out.append(f'propagation.occluder: unknown key "{k}" '
                                       f'(known: {", ".join(OCCLUDER_KEYS)})')
                    for k in ('thickness_m', 'edge_offset_m', 'distance_m'):
                        if k in occ and (not isinstance(occ[k], (int, float)) or occ[k] < 0):
                            out.append(f'propagation.occluder.{k}: needs a number >= 0')
                    cov = occ.get('coverage')
                    if cov is not None and (not isinstance(cov, (int, float)) or not (0.0 <= float(cov) <= 1.0)):
                        out.append('propagation.occluder.coverage: 0 (clear line) .. 1 (fully behind the barrier)')
                    if float(occ.get('thickness_m', 0.02)) <= 0.0 and occ.get('transmission', True):
                        out.append('propagation.occluder.thickness_m: a transmitting barrier needs a thickness')

    sp = scene.get('spatial')
    if sp is not None:
        if not isinstance(sp, dict):
            out.append('scene.spatial: an object {"azimuth": ...}')
        else:
            for k in sp:
                if k not in SPATIAL_KEYS:
                    out.append(f'spatial: unknown key "{k}" (known: {", ".join(SPATIAL_KEYS)})')

    if 'voices' in scene:
        out += sound_model.problems(model_of(scene))
    elif tl is None:
        out.append('scene: needs either "voices" (the voice engine) or "timeline" (the physical scene); '
                   'there is no default sound')
    return out


# ------------------------------------------------------------------------------------------------ rendering
def render_scene(scene, sr=SR, seed=1, seconds=None):
    """(mono array, report). A `voices` scene is the legacy renderer, a `timeline` scene is the physical one."""
    bad = problems(scene)
    if bad:
        raise ValueError('physical scene: ' + '; '.join(bad))
    if 'voices' in scene and 'timeline' not in scene:
        return sound_model.render(model_of(scene), sr, seed, seconds), {'engine': 'voices'}
    x, report = render.render_scene(scene, sr, seed, seconds)
    report = dict(report, engine='timeline')
    sp = scene.get('spatial') or {}
    return x, report


def render_stereo(scene, sr=SR, seed=1, seconds=None):
    """(N, 2) for a scene: mono render placed by spatial.azimuth."""
    x, report = render_scene(scene, sr, seed, seconds)
    sp = scene.get('spatial') or {}
    return propagate.pan(x, sp.get('azimuth', 0.0), sp.get('elevation', 0.0)), report


def describe():
    lines = ['scene schema version %d' % SCHEMA_VERSION, '',
             'two shapes, both valid:', '  voices    excitation -> resonator -> events (sound_model.py); the old renderer',
             '  timeline  materials, objects and interactions (render.py); the physical scene', '',
             'live keys:']
    for k in sorted(LIVE):
        lines.append(f'  {k:12s} ' + {'seconds': 'render length, s',
                                       'voices': 'legacy voice stack',
                                       'note': 'what the sound is, one sentence',
                                       'free': 'parameters sound_fit.py may move',
                                       'calibration': 'normalize (energy|none|peak|rms), level_db',
                                       'materials': 'named materials (materials.py SCHEMA)',
                                       'objects': 'named objects: material + geometry + modes',
                                       'sources': 'named flow sources (flow: speed, corner_hz, intensity)',
                                       'timeline': 'interactions and their `then` edges',
                                       'propagation': 'distance_m, atmosphere, canopy_density, ground',
                                       'spatial': 'azimuth, elevation, distance_m'}[k])
    lines.append('')
    lines.append('interactions: ' + ', '.join(render.INTERACTIONS))
    return '\n'.join(lines)
