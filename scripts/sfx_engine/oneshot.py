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
"""oneshot.py - a one-hit effect becomes samples.

A preset may say what the sound is in three ways, and the newest wins:

    "scene"      a physical scene (phys_core/scene.py): materials, objects, interactions, propagation
    "model"      a voice stack (sound_model.py): the shape that existed before the scene schema
    "generator"  one of the 28 built-in recipes in sfx.py: a compatibility adapter, kept so old scores render

`make()` keeps the contract the rest of the skill depends on: a mono float array, the same bytes for the same seed, and
a peak of 0.9 unless the caller asks otherwise or the preset declares its own calibration. That peak is a presentation
contract at the boundary, not the physics: inside a scene the amplitude comes from the radiated energy, so a heavy
impact and a light one stay different.
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import phys_core.scene as scene_mod

SR = 44100
PEAK = 0.9


def _norm(x, peak=PEAK):
    x = np.asarray(x, dtype=float)
    m = float(np.abs(x).max()) if x.size else 0.0
    return x * (peak / m) if m > 1e-12 else x


def make(name, seconds=2.0, sr=SR, seed=1, normalize=True, **kw):
    """(mono array, 'scene'|'model'|'preset'|'code', note). Same seed, same sound."""
    kw.pop('backend', None)
    import presets
    import sfx
    cfg = presets.find_sfx(name)
    if cfg is not None:
        bad = sfx.preset_problems(cfg)
        if bad:
            raise ValueError(f'sfx preset "{name}" ({cfg.get("_source")}): ' + '; '.join(bad))
    elif name not in sfx.GENERATORS:
        raise KeyError(f'unknown sound effect: {name}. Known: {", ".join(sfx.GENERATORS)}')

    if cfg is not None and isinstance(cfg.get('scene'), dict):
        sc = dict(cfg['scene'], seconds=float(seconds))
        x, report = scene_mod.render_scene(sc, sr, seed)
        declared = 'calibration' in cfg['scene']
        if normalize and not declared:
            x = _norm(x)
        return np.asarray(x, dtype=float), 'scene', f'scene from {cfg.get("_source")}'
    if cfg is not None and cfg.get('model') is not None:
        import sound_model
        x = sound_model.render(cfg['model'], sr, seed, seconds)
        return (_norm(x) if normalize else x), 'model', f'model from {cfg.get("_source")}'
    if cfg is not None and cfg.get('spec') is not None:
        import sfx as _sfx
        x = _sfx.synth(dict(cfg['spec'], seconds=seconds), sr, seed)
        return (_norm(x) if normalize else x), 'preset', f'spec from {cfg.get("_source")}'

    gen = (cfg or {}).get('generator') or name
    if gen in sfx.AMBIENCE:
        import warnings
        warnings.warn(f'sfx "{gen}" is ambience: use an environments preset (env:<name>); this fixed recipe is kept '
                      f'only for older scores', stacklevel=2)
    x = sfx.GENERATORS[gen](seconds, sr, np.random.default_rng(seed), **{**(cfg or {}).get('params', {}), **kw})
    x = np.asarray(x, dtype=float)
    return (_norm(x) if normalize else x), ('preset' if cfg else 'code'), (f'preset {cfg.get("_source")}' if cfg else 'procedural dsp')


def timeline(items, total_sec, sr=SR, seed=1, **kw):
    """Lay effects on a stereo bed. items: dicts with name, at (s), seconds, gain_db, pan (-1..1), optional kw."""
    n = int(round(float(total_sec) * sr))
    out = np.zeros((n, 2))
    for i, it in enumerate(items):
        x, _, _ = make(it['name'], it.get('seconds', 2.0), sr, seed + i, **dict(it.get('kw', {})))
        x = x * 10 ** (it.get('gain_db', 0.0) / 20)
        pan = float(np.clip(it.get('pan', 0.0), -1, 1))
        left, right = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
        start = int(it['at'] * sr)
        seg = x[:max(0, n - start)]
        out[start:start + len(seg), 0] += seg * left
        out[start:start + len(seg), 1] += seg * right
    return out.astype(np.float32)
