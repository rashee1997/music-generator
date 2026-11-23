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

"""fauna_schema.py - the validator of a biome preset's `fauna` list (called by biome.schema.problems)."""
import math

from biome import context, fauna as fauna_mod, sources, tract


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def entry_problems(f, preset=None, where='fauna'):
    if not isinstance(f, dict):
        return [f'{where}: an object']
    name = f.get('name')
    where = f'{where} "{name}"' if name else where
    out = []
    if not name or not isinstance(name, str):
        out.append(f'{where}: needs a "name" (it seeds the animal, so it must be stable)')
    out += [f'{where}: unknown key "{k}" (known: {", ".join(fauna_mod.KEYS)})' for k in f if k not in fauna_mod.KEYS]
    if f.get('salience', 'bed') not in ('bed', 'foreground'):
        out.append(f'{where}.salience: one of bed, foreground')
    if not _num(f.get('power_w')) or not 1e-12 <= f['power_w'] <= 1e6:
        out.append(f'{where}.power_w: radiated acoustic power while calling, W (1e-12 to 1e6); there is no default level')
    for k, lo, hi in (('individuals', 1, 200), ('bouts_per_min', 0.0, 600.0), ('individual_spread', 0.0, 0.5),
                      ('rate_per_k', -0.2, 0.2), ('first_s', 0.0, 3600.0)):
        if k in f and not (_num(f[k]) and lo <= f[k] <= hi):
            out.append(f'{where}.{k}: a number from {lo:g} to {hi:g}')
    if f.get('call'):
        try:
            from env_engine import calls
            out += [f'{where}: {p}' for p in calls.problems({'call': f['call']})]
        except Exception as exc:                                        # an unreadable preset is reported, never raised
            out.append(f'{where}.call: {exc}')
    src = f.get('source') or ({'kind': 'additive'} if f.get('call') else None)
    if src is None:
        out.append(f'{where}: needs a "source" (or a "call" preset to start from)')
    elif not isinstance(src, dict) or 'kind' not in src:
        out.append(f'{where}.source: {{"kind": one of {", ".join(sources.KINDS)}, ...}}')
    else:
        try:
            merged = fauna_mod.from_call_preset(f) if f.get('call') else f
        except KeyError:                                                  # an unknown calls preset is reported above
            return out
        els = merged.get('elements') or {'call': {}}
        defaults = {k: v for k, v in src.items() if k != 'kind'}
        for n, e in els.items():
            if not isinstance(e, dict):
                out.append(f'{where}.elements.{n}: an object')
                continue
            out += sources.problems(src['kind'], {**defaults, **e}, f'{where}.elements.{n}')
        seq = merged.get('sequence') or list(els)
        for item in seq:
            n = item if isinstance(item, str) else (item[0] if item else None)
            if n not in els:
                out.append(f'{where}.sequence names "{n}", which is not an element')
    out += [f'{where}.{p}' for p in tract.problems(f.get('resonator'), 'resonator')]
    ni = f.get('niche')
    if ni is not None:
        if not isinstance(ni, dict) or any(k not in fauna_mod.NICHE_KEYS for k in ni):
            out.append(f'{where}.niche: {{"band_hz": [low, high], "active": {{"control": name}}}}')
        else:
            b = ni.get('band_hz')
            if b is not None and not (isinstance(b, list) and len(b) == 2 and all(_num(x) and x > 0 for x in b) and b[0] < b[1]):
                out.append(f'{where}.niche.band_hz: [low_hz, high_hz]')
            a = ni.get('active')
            if a is not None and preset is not None and not (isinstance(a, dict) and set(a) == {'control'} and a['control'] in (preset.get('controls') or {})):
                out.append(f'{where}.niche.active: {{"control": name}} naming one of {sorted(preset.get("controls") or {}) or "none"}')
    po = f.get('position')
    if po is not None:
        if not isinstance(po, dict) or any(k not in fauna_mod.POSITION_KEYS for k in po):
            out.append(f'{where}.position: {{"azimuth", "elevation", "distance", "trajectory"}}')
        else:
            for k, lo, hi in (('azimuth', -360, 360), ('elevation', -90, 90), ('distance', 0.1, 10000)):
                if k in po and not (_num(po[k]) and lo <= po[k] <= hi):
                    out.append(f'{where}.position.{k}: a number from {lo} to {hi}')
    if f.get('medium') is not None and preset is not None:
        media = preset.get('media') or {'air': preset.get('medium')}
        if f['medium'] not in media:
            out.append(f'{where}.medium "{f["medium"]}" is not one of the media ({", ".join(sorted(media))})')
    return out


def problems(fauna, preset=None):
    if not isinstance(fauna, list):
        return ['fauna: a list of animals']
    out, names = [], set()
    for f in fauna:
        out += entry_problems(f, preset)
        n = f.get('name') if isinstance(f, dict) else None
        if n in names:
            out.append(f'fauna "{n}": the name is used twice (it seeds the animal)')
        names.add(n)
    gens = {g.get('name') for g in (preset or {}).get('generators', []) if isinstance(g, dict)}
    out += [f'fauna "{n}": the name is also a generator name' for n in names & gens]
    return out
