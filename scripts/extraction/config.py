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

"""Profile loading: template defaults <- profile file <- --set overrides. Unknown keys are rejected, so a typo never passes silently."""
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.dirname(os.path.dirname(HERE))
TEMPLATE = os.path.join(SK, 'templates', 'extraction_profile.json')
PRESET_DIR = os.path.join(SK, 'templates', 'profiles')


def jload(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def jdump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def defaults():
    return jload(TEMPLATE)


def _merge(base, over, path, free, errors):
    for k, v in over.items():
        if k.startswith('_'):
            continue
        here = f'{path}.{k}' if path else k
        if k not in base:
            if any(path == f or path.startswith(f + '.') for f in free):   # free-form section: any key may be added
                base[k] = copy.deepcopy(v)
            else:
                errors.append(here)
            continue
        if isinstance(base[k], dict) and isinstance(v, dict):
            _merge(base[k], v, here, free, errors)
        else:
            base[k] = copy.deepcopy(v)


def parse_set(items):
    """['a.b=3', 'c.d=[1,2]'] -> {'a': {'b': 3}, 'c': {'d': [1, 2]}}; values are JSON, else plain text."""
    out = {}
    for it in items or []:
        if '=' not in it:
            raise ValueError(f'--set needs key=value, got "{it}"')
        key, raw = it.split('=', 1)
        try:
            val = json.loads(raw)
        except ValueError:
            val = raw
        node = out
        parts = key.split('.')
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = val
    return out


def resolve_profile(name, project=None):
    """Profile name or path -> file path. Looks in <project>/profiles, then the skill's templates/profiles."""
    if not name:
        p = os.path.join(project, 'profiles', 'project.json') if project else None
        return p if p and os.path.isfile(p) else None
    if os.path.isfile(name):
        return name
    for d in ([os.path.join(project, 'profiles')] if project else []) + [PRESET_DIR]:
        p = os.path.join(d, name if name.endswith('.json') else name + '.json')
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(f'profile "{name}" not found in {project and os.path.join(project, "profiles")} or {PRESET_DIR}')


def load(profile=None, sets=None, project=None):
    cfg = defaults()
    free = set(cfg.get('_free', []))
    errors = []
    path = resolve_profile(profile, project)
    layers = ([jload(path)] if path else []) + ([parse_set(sets)] if sets else [])
    for layer in layers:
        _merge(cfg, layer, '', free, errors)
    if errors:
        raise ValueError('unknown profile keys: ' + ', '.join(errors))
    cfg['_profile_path'] = path
    return cfg


def with_overrides(cfg, pairs):
    """Copy of cfg with [["a.b", value], ...] applied (keys must exist)."""
    out = copy.deepcopy(cfg)
    for key, val in pairs:
        node = out
        parts = key.split('.')
        for p in parts[:-1]:
            node = node[p]
        if parts[-1] not in node:
            raise KeyError(f'lever "{key}" is not a profile key')
        node[parts[-1]] = val
    return out
