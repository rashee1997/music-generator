"""Choir layers: one vocal part played by several sections, each with its own register, vowel, timbre and the dynamics at which it sings.

A single `render` call makes N singers of one kind that all sing the same notes the same way; a choir that never changes make-up
is what a listener hears as "the same choir every time". `ensemble.layers` is a list of sections. Each section

    name         label in the report and the stem names
    voices       singers in the section
    select       which notes it sings of a chord: "all" (default), "highest", "lowest", "middle"
    shift        semitones added to every pitch (12 = octave up, -12 = octave down)
    vowel        optional vowel for the section
    vel          [lo, hi] MIDI velocity band (1-127) it sings in: a section that enters at forte is silent below it
    level_db     gain of the section in the sum
    overrides    any vocal config block, merged over the base for this section (tract, source, vibrato, technique, dynamics...)
    pan_width, distance_m, cohesion   optional placement and tightness of this section

Notes below a section's band are not sung by it, so a crescendo written as velocities adds sections, as a real choir does.
No name of a piece or a part appears here; the sections are data in the preset (references/data/vocal-engine-data/choirs/).
"""
import copy

import numpy as np

from . import data

SELECTS = ('all', 'highest', 'lowest', 'middle')
GROUP_S = 0.03            # starting value: notes starting within 30 ms are one chord


def specs(cfg):
    """Validated layer specs, or [] when the config has none. Unknown keys and values are errors, never silently ignored."""
    raw = (cfg.get('ensemble') or {}).get('layers') or []
    out = []
    names = set()
    for i, L in enumerate(raw):
        unknown = set(L) - {'name', 'voices', 'select', 'shift', 'vowel', 'vel', 'level_db', 'overrides', 'pan_width',
                            'distance_m', 'cohesion', '_about'}
        if unknown:
            raise ValueError(f'ensemble.layers[{i}] has unknown key(s) {sorted(unknown)}')
        sel = L.get('select', 'all')
        if sel not in SELECTS:
            raise ValueError(f'ensemble.layers[{i}].select must be one of {SELECTS}, got {sel!r}')
        vel = L.get('vel', [1, 127])
        if len(vel) != 2 or not (1 <= vel[0] <= vel[1] <= 127):
            raise ValueError(f'ensemble.layers[{i}].vel must be [lo, hi] inside 1-127, got {vel!r}')
        name = str(L.get('name') or f'layer{i}')
        if name in names:
            raise ValueError(f'ensemble.layers has two sections called "{name}"')
        names.add(name)
        out.append(dict(name=name, voices=int(L.get('voices', 4)), select=sel, shift=float(L.get('shift', 0.0)),
                        vowel=L.get('vowel'), vel=(float(vel[0]), float(vel[1])), level_db=float(L.get('level_db', 0.0)),
                        overrides=copy.deepcopy(L.get('overrides') or {}), pan_width=L.get('pan_width'),
                        distance_m=L.get('distance_m'), cohesion=L.get('cohesion')))
    return out


def select_events(events, spec):
    """The notes a section sings: the chord member it takes, inside its velocity band, shifted. Never mutates the input."""
    ev = sorted(events, key=lambda e: (e['t'], e['p']))
    groups, cur = [], []
    for e in ev:
        if cur and e['t'] - cur[0]['t'] > GROUP_S:
            groups.append(cur)
            cur = []
        cur.append(e)
    if cur:
        groups.append(cur)
    lo, hi = spec['vel']
    out = []
    for g in groups:
        g = sorted(g, key=lambda e: e['p'])
        pick = {'all': g, 'highest': g[-1:], 'lowest': g[:1], 'middle': g[len(g) // 2:len(g) // 2 + 1] if len(g) > 2 else []}[spec['select']]
        for e in pick:
            if lo <= float(e.get('v', 80)) <= hi:
                d = dict(e)
                d['p'] = float(e['p']) + spec['shift']
                if spec['vowel'] and not e.get('vowel'):
                    d['vowel'] = spec['vowel']
                out.append(d)
    return out


def layer_config(cfg, spec):
    """The config one section renders with: the base minus its layers, then the section's own voices, placement and overrides."""
    c = copy.deepcopy(cfg)
    c['ensemble']['layers'] = []
    c['ensemble']['voices'] = spec['voices']
    for k in ('pan_width', 'distance_m', 'cohesion'):
        if spec[k] is not None:
            c['ensemble'][k] = float(spec[k])
    if spec['overrides']:
        c = data.deep_merge(c, spec['overrides'])
        c['ensemble']['layers'] = []
    return c


def render(events, sr, cfg, seed, hum, default_vowel, render_one):
    """Render every section with `render_one(events, sr, cfg, seed, hum, default_vowel)` -> (mix, info) and sum them.
    Returns (mix, info). info['layers'] lists each section's voices, notes and level; its report is the busiest section's, with
    the voice count of the whole choir."""
    sp = specs(cfg)
    parts = []
    for i, s in enumerate(sp):
        ev = select_events(events, s)
        if not ev:
            parts.append((s, None, None))
            continue
        mix, info = render_one(ev, sr, layer_config(cfg, s), int(seed) + 1009 * (i + 1), hum, default_vowel)
        parts.append((s, mix * float(10 ** (s['level_db'] / 20.0)), info))
    live = [p for p in parts if p[1] is not None]
    if not live:
        raise ValueError('no choir section sings any note: the velocity bands and selections of ensemble.layers cover none of the events')
    n = max(len(m) for _, m, _ in live)
    total = np.zeros((n, 2))
    stems, breaths, voices = [], [], []
    for s, m, info in live:
        total[:len(m)] += m
        stems += [np.pad(x, (0, n - len(x))) for x in info.get('stems', [])]
        breaths += [np.pad(x, (0, n - len(x))) for x in info.get('breath_stems', [])]
        for v in info['voices']:
            voices.append(dict(v, group=s['name']))
    lead = max(live, key=lambda p: p[2]['report']['phrases'] * 1000 + p[2]['report']['voices'])[2]
    rep = dict(lead['report'])
    rep['voices'] = sum(p[2]['report']['voices'] for p in live)
    info = dict(lead, voices=voices, stems=stems, breath_stems=breaths, report=rep,
                layers=[dict(name=s['name'], voices=s['voices'], notes=(None if info is None else int(sum(1 for _ in info['voices']))),
                             level_db=s['level_db'], sings=(m is not None)) for s, m, info in parts])
    return total.astype(np.float32), info
