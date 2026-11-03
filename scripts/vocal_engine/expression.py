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

"""Expression profiles: JSON bundles that move many synthesis parameters together (attack, release, vibrato,
portamento, phrase arc, register, breath, ...). Never a volume multiplier alone. `intensity` blends numeric
values between the current config (0) and the profile (1); it can exceed 1 to exaggerate."""
import copy
import glob
import json
import os

from . import data

DIR = os.path.join(data.DIR, 'expression')


def _project_dirs():
    """<project>/presets/vocals/expression for every project added with presets.add_project (latest first)."""
    try:
        import presets
    except ImportError:
        return []
    return [os.path.join(r, 'vocals', 'expression') for r in reversed(presets.PROJECT_ROOTS)]


def names(extra_dirs=()):
    out = {}
    for d in (DIR, *reversed(_project_dirs()), *extra_dirs):
        for f in sorted(glob.glob(os.path.join(d, '*.json'))):
            out[os.path.splitext(os.path.basename(f))[0]] = f
    return sorted(out)


def load(name, extra_dirs=()):
    """Profile dict by name (a project folder in extra_dirs wins over the skill's)."""
    for d in (*extra_dirs, *_project_dirs(), DIR):
        f = os.path.join(d, f'{name}.json')
        if os.path.exists(f):
            with open(f, encoding='utf-8') as fh:
                return {k: v for k, v in json.load(fh).items() if not k.startswith('_')}
    raise KeyError(f'unknown expression profile {name!r}; have {names(extra_dirs)}')


def blend(base, over, w):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = blend(out[k], v, w)
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(out.get(k), (int, float)):
            out[k] = out[k] + w * (v - out[k])
        elif w >= 0.5:
            out[k] = copy.deepcopy(v)
    return out


def apply(cfg, profile, intensity=1.0, extra_dirs=()):
    """cfg + profile (name or dict) -> new cfg. Empty/None profile returns cfg unchanged."""
    if not profile:
        return cfg
    prof = load(profile, extra_dirs) if isinstance(profile, str) else profile
    return blend(cfg, prof, float(intensity))
