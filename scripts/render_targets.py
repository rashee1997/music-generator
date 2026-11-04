# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""render_targets.py - which deliverables a score asks for, and only those.

A score is a project file; this module is the engine side of that. It reads the score's `output_targets` and the
formats shipped as presets of the kind `outputs` (references/data/presets/outputs/, each one a
presets.py preset a project can override or extend with its own file):

    "output_targets": "stereo"                       one target
    "output_targets": ["immersive_7_1", "stereo"]    these, in this order (the first is the certified master)
    "output_targets": "all"                          every target in manifest order
    (no "output_targets")                            the default preset's list (presets/outputs/_default.json)

Nothing about a format is hard-coded here. Channel counts, channel order, file names, true-peak ceilings, aliases and
the renderer that builds a format all live in the preset. A target whose `renderer` is null is described but cannot be
built yet: asking for it by name is a blocking problem, never a silent downgrade, and "all" reports it as skipped.

The legacy score key `outputs` is accepted as an alias for `output_targets`.

This module only reads presets and the score. It renders nothing.
"""
import copy

import presets

KIND = 'outputs'
DEFAULT_PRESET = '_default'
SCORE_KEY = 'output_targets'
LEGACY_SCORE_KEY = 'outputs'
ALL = 'all'
# The renderers that exist in the engine today. A preset naming anything else is a data error, not a fallback.
ENGINE_RENDERERS = ('mix_master',)
REQUIRED = ('channels', 'channel_order', 'file', 'renderer', 'true_peak_dbtp')


def _norm(name):
    return str(name).lower().strip().replace(' ', '_').replace('-', '_')


def _all():
    """Every target preset (the `_default` preset is the default rule, not a target)."""
    out = {}
    for name, p in presets.load(KIND).items():
        if name == DEFAULT_PRESET:
            continue
        out[name] = {k: v for k, v in p.items() if k != '_source'}
    return out


def names():
    """Every target the presets define, in manifest order."""
    targets = _all()
    return sorted(targets, key=lambda n: (float(targets[n].get('order', 999)), n))


def get(name):
    """One target's description, or None. A fresh copy: a caller may edit it."""
    t = _all().get(_norm(name))
    return copy.deepcopy(t) if isinstance(t, dict) else None


def canonical(name):
    """The target a name or alias means, or the normalised name when nothing matches."""
    n = _norm(name)
    if n in _all():
        return n
    for target in names():
        if n in [_norm(a) for a in (_all()[target].get('aliases') or [])]:
            return target
    return n


def default():
    """The targets a score that names none is delivered as (a list, in order)."""
    p = presets.load(KIND).get(DEFAULT_PRESET) or {}
    raw = p.get('targets', p.get('target'))
    if isinstance(raw, str):
        return [canonical(raw)]
    return [canonical(x) for x in (raw or []) if isinstance(x, str)]


def buildable(name):
    """True when the engine has the renderer this target names."""
    t = get(name) or {}
    return t.get('renderer') in ENGINE_RENDERERS


def filename(name):
    """The file a target is delivered as, inside out/."""
    return (get(name) or {}).get('file') or (name + '.wav')


def channels(name):
    return int((get(name) or {}).get('channels') or 0)


def true_peak(name):
    """The true-peak ceiling of a target in dBTP (data), or None."""
    v = (get(name) or {}).get('true_peak_dbtp')
    return float(v) if v is not None else None


def requested(score):
    """The raw `output_targets` value of a score (None when it says nothing)."""
    score = score or {}
    return score.get(SCORE_KEY, score.get(LEGACY_SCORE_KEY))


def resolve(score):
    """What this score asks for -> dict(requested, selected, skipped, problems).

    selected  the targets to build, in the promise order, first one first (deduplicated)
    skipped   targets "all" covered that the engine cannot build yet, with their reason
    problems  blocking messages; when it is non-empty nothing should render
    """
    raw = requested(score)
    out = dict(requested=raw, selected=[], skipped=[], problems=[])
    if raw is None:
        wanted = default()
        if not wanted:
            out['problems'].append(f'no default deliverable: the "{DEFAULT_PRESET}" preset of kind "{KIND}" '
                                   f'names no "targets" and the score has no "{SCORE_KEY}"')
            return out
    elif isinstance(raw, str):
        wanted = [raw]
    elif isinstance(raw, list):
        if not raw:
            out['problems'].append(f'score "{SCORE_KEY}" is an empty list: name a target '
                                   f'({", ".join(names())}) or "all"')
            return out
        wanted = raw
    else:
        out['problems'].append(f'score "{SCORE_KEY}" must be a target name, a list of names, or "all"; '
                               f'got {type(raw).__name__}')
        return out
    for w in wanted:
        if not isinstance(w, str):
            out['problems'].append(f'score "{SCORE_KEY}" entry {w!r} is not a string')
            continue
        if _norm(w) == ALL:
            for n in names():
                if buildable(n):
                    _add(out['selected'], n)
                else:
                    out['skipped'].append(dict(target=n, reason=(get(n) or {}).get('unavailable_reason')
                                               or f'the engine has no renderer for "{n}"'))
            continue
        n = canonical(w)
        if n not in names():
            out['problems'].append(f'score "{SCORE_KEY}" names "{w}", which is not a target; '
                                   f'known: {", ".join(names())} (or "all")')
            continue
        if not buildable(n):
            out['problems'].append(f'score "{SCORE_KEY}" asks for "{w}" (target "{n}") but the engine cannot build it yet: '
                                   f'{(get(n) or {}).get("unavailable_reason") or "no renderer"} '
                                   f'Buildable today: {", ".join(x for x in names() if buildable(x)) or "none"}')
            continue
        _add(out['selected'], n)
    if not out['selected'] and not out['problems']:
        out['problems'].append(f'score "{SCORE_KEY}" asks only for targets the engine cannot build '
                               f'({", ".join(s["target"] for s in out["skipped"])})')
    if out['problems']:
        out['selected'] = []        # a malformed request renders nothing, not only the entries that parsed
    return out


def _add(seq, name):
    if name not in seq:
        seq.append(name)


def problems(score):
    """Blocking problems only: what presets.validate / project_gate want."""
    try:
        return resolve(score)['problems']
    except (OSError, ValueError) as exc:          # a preset file that does not parse is a problem, not a crash
        return [f'the "{KIND}" presets could not be read ({exc})']


def manifest_problems():
    """The presets are data, so they are checked like data: required keys, known layout and renderer, unique files."""
    out, seen = [], {}
    try:
        targets = _all()
    except (OSError, ValueError) as exc:
        return [f'the "{KIND}" presets could not be read ({exc})']
    if not targets:
        return [f'no target presets: add references/data/presets/{KIND}/<name>.json']
    try:
        layouts = presets.load('layouts')
    except (OSError, ValueError) as exc:
        return [f'the "layouts" presets could not be read ({exc})']
    for name in names():
        t = targets[name]
        for k in REQUIRED:
            if k not in t:
                out.append(f'{name}: missing "{k}"')
        order = [s.get('name') for s in (layouts.get(t.get('layout')) or {}).get('speakers') or []] \
            if t.get('layout') else []
        if t.get('layout') is not None and t['layout'] not in layouts:
            out.append(f'{name}: layout "{t["layout"]}" is not a layout preset (known: {", ".join(sorted(layouts))})')
        elif order and t.get('channel_order') and order != list(t['channel_order']):
            out.append(f'{name}: channel_order {t.get("channel_order")} does not match layout "{t["layout"]}" '
                       f'speaker order {order}')
        if int(t.get('channels') or 0) != len(t.get('channel_order') or []):
            out.append(f'{name}: channels {t.get("channels")} does not match channel_order '
                       f'({len(t.get("channel_order") or [])} names)')
        if t.get('renderer') is not None and t.get('renderer') not in ENGINE_RENDERERS:
            out.append(f'{name}: renderer "{t.get("renderer")}" is not one of {", ".join(ENGINE_RENDERERS)}')
        if t.get('renderer') is None and not t.get('unavailable_reason'):
            out.append(f'{name}: renderer is null but no "unavailable_reason" says why')
        try:
            float(t.get('true_peak_dbtp'))
        except (TypeError, ValueError):
            out.append(f'{name}: true_peak_dbtp must be a number in dBTP')
        f = t.get('file')
        if f in seen:
            out.append(f'{name}: file "{f}" is also used by "{seen[f]}"')
        seen[f] = name
    for n in default():
        if n not in targets:
            out.append(f'default "{n}" is not a target')
        elif not buildable(n):
            out.append(f'default "{n}" cannot be built by the engine; a default must be deliverable')
    return out


if __name__ == '__main__':
    import json
    import sys
    score = json.loads(open(sys.argv[1], encoding='utf-8').read()) if len(sys.argv) > 1 else {}
    r = resolve(score)
    print(f'requested: {r["requested"]!r}')
    print(f'build:     {", ".join(r["selected"]) or "nothing"}')
    for s in r['skipped']:
        print(f'skipped:   {s["target"]} ({s["reason"]})')
    for p in r['problems'] + manifest_problems():
        print(f'FAIL {p}')
    sys.exit(1 if (r['problems'] or manifest_problems()) else 0)
