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
"""render.py - a place becomes a stereo bed.

Two shapes of environment preset, and the older one keeps working:

    {"layers": [...]}    the existing environment preset (primitives, gain_db, gain_curve, spatial, decorrelate);
                         rendered by environment.py exactly as before, so nothing already written changes
    {"scene": {...}}     a physical scene (phys_core/scene.py): materials, objects, interactions, propagation

An environment preset may also carry `scene_layers`: a list of physical scenes, each with its own gain, pan and
distance, mixed into one bed. That is the bridge that lets a project move a layer at a time instead of all at once.

The place is not the physics: a leaf-light rain and a tin-roof downpour are two scenes with the same mechanisms and
different materials, not two presets of one recipe.
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import phys_core.scene as scene_mod
from phys_core import propagate

SR = 44100


def has_scene(cfg):
    return isinstance(cfg, dict) and isinstance(cfg.get('scene'), dict)


def has_scene_layers(cfg):
    return isinstance(cfg, dict) and isinstance(cfg.get('scene_layers'), list) and cfg['scene_layers']


def is_bed(cfg):
    """True when this preset is a place that keeps sounding: several scenes mixed as one bed (`scene_layers`),
    or one scene whose timeline uses a continuous mechanism (phys_core.scene.CONTINUOUS).

    The project gate asks this instead of assuming a bed is a `layers` entry, so a physical scene ambience is
    judged by what it is, not by which schema wrote it."""
    if has_scene_layers(cfg):
        return True
    if has_scene(cfg):
        return scene_mod.is_continuous(cfg['scene'])
    return False


def render_preset(name_or_dict, duration_s=30.0, sr=SR, seed=42):
    """Stereo float32 for an environment preset (a name, or the dict itself).

    Delegates the layer form to environment.py so every existing preset renders identically, and renders the scene
    forms here.
    """
    import presets
    if isinstance(name_or_dict, dict):
        cfg, name = name_or_dict, name_or_dict.get('name', '<inline>')
    else:
        cfg = presets.find_environment(name_or_dict)
        if not cfg:
            raise ValueError(f'unknown environment "{name_or_dict}" (it would render as silence). '
                             f'Known: {", ".join(sorted(presets.load("environments")))}')
        name = name_or_dict

    if has_scene(cfg):
        return render_scene_layer(cfg['scene'], duration_s, sr, seed, cfg)
    if has_scene_layers(cfg):
        return mix_scene_layers(cfg, duration_s, sr, seed)

    import environment                             # the layer form: the existing engine, unchanged
    return environment.render_environment_preset(cfg, duration_s=duration_s, sr=sr, seed=seed)


def render_scene_layer(scene, duration_s, sr=SR, seed=42, outer=None):
    """One physical scene as a stereo layer: its own calibration, then the preset's gain and place on top."""
    outer = outer or {}
    x, report = scene_mod.render_scene(dict(scene, seconds=float(duration_s)), sr, seed)
    gain_db = float(outer.get('gain_db', 0.0))
    sp = outer.get('spatial') or {}
    st = propagate.pan(x, sp.get('azimuth', 0.0), sp.get('elevation', 0.0))
    return (st * 10.0 ** (gain_db / 20.0)).astype(np.float32)


def mix_scene_layers(cfg, duration_s, sr=SR, seed=42):
    """Several physical scenes as one bed. Each layer is seeded separately, so adding one does not change the others."""
    n = int(round(float(duration_s) * sr))
    out = np.zeros((n, 2), np.float32)
    for i, layer in enumerate(cfg['scene_layers']):
        sc = layer.get('scene') or {}
        st = render_scene_layer(sc, duration_s, sr, seed + 101 * i, layer)
        if len(st) < n:
            st = np.pad(st, ((0, n - len(st)), (0, 0)))
        out += st[:n]
    return out


def render_environment_preset(name_or_dict, duration_s=30.0, sr=SR, seed=42):
    """Compatibility name, same signature as environment.render_environment_preset."""
    return render_preset(name_or_dict, duration_s, sr, seed)
