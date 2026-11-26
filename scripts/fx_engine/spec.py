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

"""spec.py - what a chain may say, checked before anything renders.

The library of effects (names, parameters, ranges, defaults) is data: `references/data/presets/fx/effects.json`, which a
project may override per value in `<project>/presets/fx/effects.json`. A chain is a list of effects (or the name of a
shipped or project chain preset). Every problem in a chain is reported together, with the effect it belongs to; an
unknown effect, an unknown key and an out-of-range number are errors, never silently corrected.
"""
import math
import os

import presets

COMMON_KEYS = ('mix', 'start_s', 'end_s', 'edge_ms', 'seed')


def library():
    """The effect library, merged with any project override."""
    lib = presets.load('fx').get('effects')
    if not lib or 'effects' not in lib:
        raise ValueError('the effect library references/data/presets/fx/effects.json is missing or has no "effects"')
    return lib


def effect_names():
    return sorted(library()['effects'])


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _check_value(label, meta, value):
    """None when `value` is fine for `meta`, else a sentence."""
    if value is None:
        return None if meta.get('default') is None else f'{label}: none is not allowed (default {meta.get("default")!r})'
    if 'choices' in meta:
        return None if value in meta['choices'] else f'{label}: {value!r} is not one of {meta["choices"]}'
    if meta.get('type') == 'object':
        return None if isinstance(value, dict) else f'{label}: expected an object'
    if meta.get('type') == 'string':
        return None if isinstance(value, str) and value else f'{label}: expected a non-empty string'
    if not _is_number(value):
        return f'{label}: expected a number, got {value!r}'
    lo, hi = meta.get('min'), meta.get('max')
    if lo is not None and float(value) < float(lo):
        return f'{label}: {value} is below the minimum {lo}{meta.get("unit", "") and " " + meta["unit"]}'
    if hi is not None and float(value) > float(hi):
        return f'{label}: {value} is above the maximum {hi}{meta.get("unit", "") and " " + meta["unit"]}'
    if isinstance(meta.get('default'), int) and not isinstance(meta.get('default'), bool) and float(value) != int(value):
        return f'{label}: {value} must be a whole number'
    return None


def _flatten(chain, depth=0):
    """Expand named chains: [effect dict | chain name]. Returns (items, problems). One level of naming only."""
    if isinstance(chain, str):
        chain = [chain]
    if not isinstance(chain, (list, tuple)):
        return [], ['an fx chain is a list of effects or the name of a chain preset']
    items, problems = [], []
    for i, item in enumerate(chain):
        if isinstance(item, str):
            if depth:
                problems.append(f'fx[{i}]: a named chain inside a named chain ("{item}") is not followed: write its effects out')
                continue
            preset = presets.exact('fx', item)
            if not preset or not isinstance(preset.get('chain'), list):
                known = sorted(k for k, v in presets.load('fx').items() if isinstance(v, dict) and 'chain' in v)
                problems.append(f'fx[{i}]: no chain preset "{item}". Known: {known}')
                continue
            sub, sub_problems = _flatten(preset['chain'], depth + 1)
            items += sub
            problems += [f'chain "{item}": {p}' for p in sub_problems]
        elif isinstance(item, dict):
            items.append(item)
        else:
            problems.append(f'fx[{i}]: an effect is an object with a "type", got {item!r}')
    return items, problems


def normalise(chain):
    """([ {'type', 'params': {every parameter with its value}} ], [problems]). A chain with problems still returns what could
    be read, so a caller can show every error at once; `resolve` is the strict form."""
    lib = library()
    items, problems = _flatten(chain)
    out = []
    for i, item in enumerate(items):
        kind = item.get('type')
        label = f'fx[{i}] {kind!r}'
        entry = lib['effects'].get(kind) if isinstance(kind, str) else None
        if entry is None:
            problems.append(f'fx[{i}]: unknown effect {kind!r}. Known: {effect_names()}')
            continue
        metas = dict(lib.get('common') or {})
        metas.update(entry.get('params') or {})
        unknown = sorted(set(item) - set(metas) - {'type'})
        if unknown:
            problems.append(f'{label}: unknown key(s) {unknown}. Known: {sorted(metas)}')
        values = {}
        for key, meta in metas.items():
            v = item.get(key, meta.get('default'))
            msg = _check_value(f'{label} {key}', meta, v)
            if msg:
                problems.append(msg)
            values[key] = v
        s, e = values.get('start_s'), values.get('end_s')
        if _is_number(s) and _is_number(e) and float(e) <= float(s):
            problems.append(f'{label}: end_s ({e}) must be after start_s ({s})')
        if kind == 'pedalboard' and not values.get('plugin'):
            problems.append(f'{label}: "plugin" is required')
        if kind == 'external':
            path = values.get('path')
            if not path:
                problems.append(f'{label}: "path" is required')
            elif not os.path.isfile(str(path)):
                problems.append(f'{label}: the plugin file {path!r} does not exist')
        out.append(dict(type=kind, params=values))
    return out, problems


def problems(chain):
    """Every problem of a chain (empty = good), including a Pedalboard plugin that rejects its arguments."""
    norm, found = normalise(chain)
    if not found:
        from . import host
        for i, e in enumerate(norm):
            if e['type'] == 'pedalboard':
                try:
                    host.build_pedalboard(e['params']['plugin'], e['params']['params'])
                except Exception as exc:
                    found.append(f'fx[{i}] pedalboard {e["params"]["plugin"]}: {type(exc).__name__}: {exc}')
    return found


def resolve(chain):
    """The normalised chain, or ValueError listing every problem."""
    found = problems(chain)
    if found:
        raise ValueError('fx chain: ' + ' | '.join(found))
    return normalise(chain)[0]


def library_problems(registered=()):
    """What is wrong with the effect library itself (empty = good): a default outside its own range or choices, a range with
    min above max, an effect with no character, a common key an effect redefines with a different meaning of "type", and (when
    `registered` is given) an effect with no function or a function with no entry."""
    lib = library()
    out = []
    for key in COMMON_KEYS:
        if key not in (lib.get('common') or {}):
            out.append(f'common: missing "{key}"')
    groups = [('common', lib.get('common') or {})] + [(f'{n}', e.get('params') or {}) for n, e in lib['effects'].items()]
    for label, metas in groups:
        for key, meta in metas.items():
            where = f'{label}.{key}'
            lo, hi = meta.get('min'), meta.get('max')
            if lo is not None and hi is not None and float(lo) > float(hi):
                out.append(f'{where}: min {lo} is above max {hi}')
            if meta.get('default') is not None:
                msg = _check_value(where, meta, meta['default'])
                if msg:
                    out.append(f'{msg} (the default)')
            if 'text' not in meta:
                out.append(f'{where}: no "text" saying what it does')
    for name, entry in lib['effects'].items():
        if not entry.get('character'):
            out.append(f'{name}: no "character"')
    if registered:
        out += [f'{n}: in the library but no function in fx_engine.EFFECTS' for n in sorted(set(lib['effects']) - set(registered))]
        out += [f'{n}: a function in fx_engine.EFFECTS but no entry in the library' for n in sorted(set(registered) - set(lib['effects']))]
    return out
