# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""config.py - the data seam of the spatial engine.

A layout is a preset of the kind `layouts`; a deliverable is a preset of the kind `outputs`. Both are loaded through
presets.py, so a project can add its own format (7.1.2, a room-specific ring) by dropping a JSON file in
`<project>/presets/layouts/` or `<project>/presets/outputs/` - no Python changes.

No acoustic number is written here. The only literals are structural (a speaker needs a name, an azimuth, an elevation).
"""
import presets

REQUIRED_SPEAKER = ('name', 'azimuth', 'elevation')


def layout(name):
    """The layout preset called `name`, or raise KeyError with the known names."""
    return presets.get('layouts', name)


def layouts():
    return presets.load('layouts')


def target(name):
    """The deliverable preset called `name` (via render_targets, which resolves aliases), or None."""
    import render_targets
    return render_targets.get(name)


def target_name(name):
    import render_targets
    return render_targets.canonical(name)


def speakers(layout_name):
    """The non-LFE speakers of a layout, in channel order, as dicts with a unit vector added."""
    lay = layout(layout_name)
    from . import pan
    out = []
    for sp in lay.get('speakers') or []:
        if sp.get('lfe'):
            continue
        out.append(dict(sp, vector=pan.vector(float(sp['azimuth']), float(sp['elevation']))))
    return out


def lfe_speaker(layout_name):
    lay = layout(layout_name)
    for sp in lay.get('speakers') or []:
        if sp.get('lfe'):
            return dict(sp)
    return None


def channel_names(layout_name):
    return [sp['name'] for sp in layout(layout_name).get('speakers') or []]


def lfe_cfg(layout_name, target_name=None):
    """The bass-management block: the layout's, with the target's own numbers merged over it.

    A target may set the channel index, the send level and the stopband; the layout supplies the crossover and the
    default send. Either may be absent: the caller gets only the keys that are really defined.
    """
    lay = (layout(layout_name).get('lfe') or {})
    tgt = (target(target_name) or {}).get('lfe') or {} if target_name else {}
    return {**lay, **tgt}


def threshold(layout_name, key):
    """A gate threshold the layout declares (e.g. the surround energy window), in its own units."""
    return (layout(layout_name).get('gate') or {}).get(key)


def problems(layout_name=None):
    """Structural problems: a speaker without a position, channels that disagree, a missing LFE channel."""
    out = []
    items = {layout_name: layout(layout_name)} if layout_name else layouts()
    for name, lay in items.items():
        sps = lay.get('speakers') or []
        if not sps:
            out.append(f'{name}: no "speakers"')
            continue
        if int(lay.get('channels') or 0) != len(sps):
            out.append(f'{name}: channels {lay.get("channels")} does not match {len(sps)} speakers')
        seen = set()
        for sp in sps:
            missing = [k for k in REQUIRED_SPEAKER if k not in sp]
            if missing:
                out.append(f'{name}/{sp.get("name", "?")}: missing {", ".join(missing)}')
            if sp.get('name') in seen:
                out.append(f'{name}: two speakers called "{sp.get("name")}"')
            seen.add(sp.get('name'))
            try:
                if not (-180.0 <= float(sp['azimuth']) <= 180.0):
                    out.append(f'{name}/{sp["name"]}: azimuth {sp["azimuth"]} is outside -180..180 degrees')
                if not (-90.0 <= float(sp['elevation']) <= 90.0):
                    out.append(f'{name}/{sp["name"]}: elevation {sp["elevation"]} is outside -90..90 degrees')
            except (KeyError, TypeError, ValueError):
                pass
        if not any(sp.get('lfe') for sp in sps):
            out.append(f'{name}: no LFE speaker')
        dm = lay.get('downmix') or {}
        for sp in sps:
            if sp['name'] not in dm:
                out.append(f'{name}/{sp["name"]}: no downmix coefficient (a fold-down would drop it silently)')
            elif len(dm[sp['name']]) != 2:
                out.append(f'{name}/{sp["name"]}: downmix must be [left, right]')
    return out
