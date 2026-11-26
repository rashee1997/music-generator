# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""preflight_lint.py - problems a render would find, read from the score and the presets before any audio is made.

`pattern_audit.py` judges the notes (collisions, voicing, mud). This module judges the notes against what plays them:
the patch's range, the sound's length, the section lines, the mixer's rules for a figure part, and the places in the room.
Each row is a fact about files that exist before rendering, so it costs seconds instead of a render. Every row here was
found by a render that failed; none of them replaces the audio rows, which stay in the stem gate and the quality gate.

    rows = preflight_lint.checks(score, project_dir)        # [(level, name, detail)]

More rows live beside this file: preflight_levels.py (stem_level, arc, tempo, roughness: from the score alone) and
preset_probe.py (probe.*: each one-shot effect rendered once). `checks()` runs all three. lint_coverage.py says, for every
audio row, what here catches it or why only audio can.

Rows
    preflight.range         FAIL  a note is above or below the sampled range of its SFZ patch (it plays silent or stretched)
    preflight.sfx_length    FAIL  a one-shot's event is cut before its sound has played 75 % of its length (the cut is a click)
    preflight.section_edge  WARN  a sparse sound starts in one section and its tail runs into another that has none of its events
    preflight.unison        WARN  two instruments hold the same pitch above middle C for three beats or more (beating, roughness)
    preflight.figure_level  WARN  a figure-family part (melody, lead, vocal) plays only the quiet sections: the mixer lifts it to full level
    preflight.placement     WARN  two parts that play together sit under 25 degrees apart in azimuth and under 15 in elevation

The limits are starting values taken from the failures above, not measured limits. A row that does not apply says so as INFO.
"""
import os
import re

import numpy as np

SFX_MIN_FRACTION = 0.75          # a one-shot must be allowed this much of its length before the next onset or its own end
UNISON_MIN_BEATS = 3.0           # both notes this long, overlapping this long
UNISON_MIN_PITCH = 60            # below middle C a unison is a doubling, not a beat
QUIET_ENERGY = 0.5               # a section is quiet when its declared energy is under this share of the loudest section's
QUIET_SHARE = 0.7                # a figure part is a quiet-section part when this share of its note time is in quiet sections
AZ_MIN_DEG, EL_MIN_DEG = 25.0, 15.0      # the gate's own z-separation limits (quality gate row spatial.z_separation)
PLACEMENT_MIN_SHARED = 0.3       # share of the shorter part's playing time that the two parts share
SPARSE_MAX_BEATS = 16.0          # an event longer than this is a bed, not a sparse sound


# ------------------------------------------------------------------ helpers
def _clock(score):
    """beats -> seconds, on the tempo map the renderer plays (a flat bpm looked at the wrong place)."""
    import gate_clock
    return gate_clock.seconds_fn(score)


def _tracks(score):
    return [t for t in score.get('tracks') or [] if t.get('notes')]


def _kind_name(track):
    inst = str(track.get('instrument') or '')
    if ':' in inst:
        kind, name = inst.split(':', 1)
        return kind, name
    return 'instrument', inst


def _preset(lookup, kind, name):
    try:
        return lookup(kind, name)
    except Exception:
        return None


def default_lookup(kind, name):
    import presets
    if kind == 'sfx':
        return presets.find_sfx(name)
    if kind == 'env':
        return presets.find_environment(name)
    return presets.find_instrument(name)


_NOTE = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def _key_value(text):
    text = text.strip().lower()
    if re.fullmatch(r'-?\d+', text):
        return int(text)
    m = re.fullmatch(r'([a-g])([#b]?)(-?\d)', text)
    if not m:
        return None
    pc = _NOTE[m.group(1)] + (1 if m.group(2) == '#' else -1 if m.group(2) == 'b' else 0)
    return 12 * (int(m.group(3)) + 1) + pc          # C4 = 60, the SFZ default


_KEY_RE = re.compile(r'(?<![A-Za-z_])(lokey|hikey|key)\s*=\s*([0-9]+|[a-gA-G][#b]?-?[0-9])')


def sfz_range(path, depth=3):
    """(lowest, highest) key that has a sample in this SFZ file and the files it includes, or None."""
    if depth < 0 or not os.path.isfile(path):
        return None
    try:
        text = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return None
    lo, hi = [], []
    for kind, val in _KEY_RE.findall(text):
        k = _key_value(val)
        if k is None:
            continue
        if kind == 'lokey':
            lo.append(k)
        elif kind == 'hikey':
            hi.append(k)
        else:                         # `key=` sets both ends of a one-key region
            lo.append(k)
            hi.append(k)
    for inc in re.findall(r'#include\s+"([^"]+)"', text):
        sub = sfz_range(os.path.join(os.path.dirname(path), inc), depth - 1)
        if sub:
            lo.append(sub[0])
            hi.append(sub[1])
    return (min(lo), max(hi)) if lo and hi else None


def default_patch_range(block, project_dir=None):
    """The sounding key range of an instrument preset's `sfz` block, or None when the library is not installed."""
    try:
        import sfz_libs
        eff = sfz_libs.effective_block(block, project_dir)
        path = sfz_libs.find_patch(eff['library'], eff['patch'], project_dir)
    except Exception:
        return None
    return sfz_range(str(path))


# ------------------------------------------------------------------ rows
def range_rows(score, lookup, patch_range, project_dir):
    out = []
    for t in _tracks(score):
        kind, name = _kind_name(t)
        if kind != 'instrument':
            continue
        preset = _preset(lookup, kind, name)
        block = (preset or {}).get('sfz')
        if not block:
            continue
        rng = patch_range(block, project_dir)
        if not rng:
            out.append(('INFO', 'preflight.range', f'"{t["name"]}": the range of patch "{block.get("patch")}" could not be read (library not installed?); not checked'))
            continue
        lo, hi = rng
        bad = sorted({int(n['p']) for n in t['notes'] if 'p' in n and not lo <= int(n['p']) <= hi})
        if bad:
            out.append(('FAIL', 'preflight.range', f'"{t["name"]}" plays notes {bad[:8]} outside the sampled range {lo}-{hi} of patch '
                        f'"{block.get("patch")}": they play silent or stretched. Move them inside the range or use another patch'))
        else:
            out.append(('PASS', 'preflight.range', f'"{t["name"]}": every note is inside the patch range {lo}-{hi}'))
    return out


def fx_rows(score, lookup):
    """An `fx` chain (on the track or in its preset) with an unknown effect, a key it does not have or a number out of range, found
    before the render that would otherwise raise it at the mix, after every stem was drawn."""
    import fx_engine
    out = []
    for t in score.get('tracks') or []:
        kind, name = _kind_name(t)
        preset = _preset(lookup, kind, name) or {}
        chain = t.get('fx') or preset.get('fx')
        if not chain:
            continue
        found = fx_engine.problems(chain)
        label = t.get('name', name)
        if found:
            out.append(('FAIL', 'preflight.fx', f'"{label}": ' + ' | '.join(found)))
        else:
            out.append(('PASS', 'preflight.fx', f'"{label}": the fx chain is valid ({len(fx_engine.resolve(chain))} effect(s))'))
    return out


def sfx_length_rows(score, lookup):
    sec = _clock(score)
    out = []
    for t in _tracks(score):
        kind, name = _kind_name(t)
        if kind != 'sfx':
            continue
        preset = _preset(lookup, 'sfx', name)
        length = float((preset or {}).get('seconds') or 0.0)
        if length <= 0:
            continue
        notes = sorted(t['notes'], key=lambda n: float(n['t']))
        short = []
        for i, n in enumerate(notes):
            a = sec(float(n['t']))
            end = sec(float(n['t']) + float(n.get('d') or 0.0))
            if i + 1 < len(notes):
                end = min(end, sec(float(notes[i + 1]['t'])))
            if end - a < SFX_MIN_FRACTION * length:
                short.append((round(a, 1), round(end - a, 2)))
        if short:
            out.append(('FAIL', 'preflight.sfx_length', f'"{t["name"]}" ({name}, {length:g} s): {len(short)} event(s) get under '
                        f'{int(SFX_MIN_FRACTION * 100)} % of the sound before the next onset or the event end (at {short[0][0]} s, {short[0][1]} s): '
                        'a one-shot cut mid-ring is a click. Lengthen `d` in beats or space the events'))
        else:
            out.append(('PASS', 'preflight.sfx_length', f'"{t["name"]}": every event plays at least {int(SFX_MIN_FRACTION * 100)} % of its {length:g} s sound'))
    return out


def _sections(score):
    sec = _clock(score)
    bpb = float((score.get('ts') or [4, 4])[0]) * 4.0 / float((score.get('ts') or [4, 4])[1])
    out = []
    for s in (score.get('plan') or {}).get('sections') or []:
        if 'start_bar' in s and 'end_bar' in s:
            a, b = (float(s['start_bar']) - 1) * bpb, float(s['end_bar']) * bpb
            out.append(dict(name=str(s.get('name', '?')), a=a, b=b, sa=sec(a), sb=sec(b), energy=s.get('energy')))
    return out


def section_edge_rows(score):
    secs = _sections(score)
    if len(secs) < 2:
        return [('INFO', 'preflight.section_edge', 'fewer than two sections: not checked')]
    out, bad = [], []
    for t in _tracks(score):
        if str(t.get('role')) not in ('fx', 'environment'):
            continue
        for n in t['notes']:
            a, b = float(n['t']), float(n['t']) + float(n.get('d') or 0.0)
            if b - a > SPARSE_MAX_BEATS:       # a bed that runs through the piece is meant to cross the lines
                continue
            home = [s for s in secs if s['a'] <= a < s['b']]
            if not home:
                continue
            over = [s for s in secs if s is not home[0] and s['a'] < b and s['b'] > a and a < s['a']]
            for s in over:
                has = any(s['a'] <= float(m['t']) < s['b'] for m in t['notes'])
                if not has:
                    bad.append((t['name'], home[0]['name'], s['name'], round(a, 1)))
    if bad:
        first = bad[0]
        out.append(('WARN', 'preflight.section_edge', f'{len(bad)} sparse sound(s) end in a section that has none of their events, e.g. "{first[0]}" '
                    f'from {first[1]} into {first[2]} (beat {first[3]}): the stem gate reads it as a part that drops out there. Shorten `d` or end the event before the line'))
    else:
        out.append(('PASS', 'preflight.section_edge', 'every sparse sound ends in a section where it also has an event'))
    return out


def unison_rows(score):
    pads = []
    for t in _tracks(score):
        if str(t.get('role')) in ('drum', 'percussion', 'fx', 'environment', 'texture') or str(t.get('instrument', '')).startswith(('env:', 'sfx:')):
            continue
        pads.append(t)
    found = []
    for i, a in enumerate(pads):
        for b in pads[i + 1:]:
            if str(a['name']).split('_')[0] == str(b['name']).split('_')[0]:
                continue                  # two parts of one family (violins_tremolo and violins_sustain) double each other on purpose
            for na in a['notes']:
                da = float(na.get('d') or 0.0)
                if da < UNISON_MIN_BEATS or int(na['p']) < UNISON_MIN_PITCH:
                    continue
                for nb in b['notes']:
                    if int(nb['p']) != int(na['p']) or float(nb.get('d') or 0.0) < UNISON_MIN_BEATS:
                        continue
                    ov = min(float(na['t']) + da, float(nb['t']) + float(nb['d'])) - max(float(na['t']), float(nb['t']))
                    if ov >= UNISON_MIN_BEATS:
                        found.append((ov, a['name'], b['name'], int(na['p']), float(max(na['t'], nb['t']))))
    if not found:
        return [('PASS', 'preflight.unison', 'no two instruments hold the same pitch above middle C for three beats or more')]
    found.sort(reverse=True)
    ov, a, b, p, t = found[0]
    return [('WARN', 'preflight.unison', f'{len(found)} sustained unison(s) between different instruments, longest "{a}" and "{b}" on {p} for {ov:g} beats '
             f'(from beat {t:g}): two samples tuned a few cents apart beat against each other and read as roughness. Move one part an octave or a third')]


def figure_level_rows(score):
    from roles import canonical, is_lead
    secs = _sections(score)
    energies = [float(s['energy']) for s in secs if s.get('energy') is not None]
    if len(secs) < 2 or not energies:
        return [('INFO', 'preflight.figure_level', 'no section energies: not checked')]
    top = max(energies)
    quiet = [s for s in secs if s.get('energy') is not None and float(s['energy']) < QUIET_ENERGY * top]
    out = []
    for t in _tracks(score):
        try:
            lead = is_lead(t.get('role', ''))
        except Exception:
            lead = False
        if not lead:
            continue
        total = quiet_t = 0.0
        for n in t['notes']:
            d = float(n.get('d') or 0.0)
            total += d
            mid = float(n['t']) + d / 2.0
            if any(s['a'] <= mid < s['b'] for s in quiet):
                quiet_t += d
        share = quiet_t / total if total > 0 else 0.0
        if share >= QUIET_SHARE and total > 0:
            out.append(('WARN', 'preflight.figure_level', f'"{t["name"]}" has role "{t.get("role")}" but {100 * share:.0f} % of its note time is in sections under '
                        f'{int(QUIET_ENERGY * 100)} % of the peak energy: the mixer lifts every figure-family part to full level, so it will play as loud as the '
                        'loudest part. Give it the role "counter" (or set its target level in the mix preset) to keep it quiet'))
    if not out:
        out.append(('PASS', 'preflight.figure_level', 'no figure-family part plays only the quiet sections'))
    return out


def _spatial(track, lookup):
    sp = track.get('spatial')
    if not sp:
        kind, name = _kind_name(track)
        sp = (_preset(lookup, kind, name) or {}).get('spatial')
    if not sp or sp.get('azimuth') is None:
        return None
    return float(sp.get('azimuth', 0.0)), float(sp.get('elevation', 0.0) or 0.0)


def placement_rows(score, lookup):
    sec = _clock(score)
    items = []
    for t in _tracks(score):
        inst = str(t.get('instrument', ''))
        if inst.startswith('env:') or str(t.get('role')) == 'environment':
            continue
        pos = _spatial(t, lookup)
        if pos is None:
            continue
        spans = sorted((sec(float(n['t'])), sec(float(n['t']) + float(n.get('d') or 0.0))) for n in t['notes'])
        items.append((t['name'], pos, spans, str(t.get('role')) == 'fx'))
    bad = []
    for i, (na, (aza, ela), sa, fa) in enumerate(items):
        for nb, (azb, elb), sb, fb in items[i + 1:]:
            if fa == fb:
                continue                  # the orchestra's own seats are set by the instrument presets; the risk is a sound placed on top of a part
            daz = abs((aza - azb + 180.0) % 360.0 - 180.0)
            if daz >= AZ_MIN_DEG or abs(ela - elb) >= EL_MIN_DEG:
                continue
            shared = _shared_seconds(sa, sb)
            shorter = min(sum(b - a for a, b in sa), sum(b - a for a, b in sb))
            if shorter > 0 and shared / shorter >= PLACEMENT_MIN_SHARED:
                bad.append((daz, abs(ela - elb), na, nb))
    if not bad:
        return [('PASS', 'preflight.placement', 'no two parts that play together sit closer than the z-separation limit')]
    bad.sort()
    daz, de, a, b = bad[0]
    return [('WARN', 'preflight.placement', f'{len(bad)} pair(s) of parts that play together sit under {AZ_MIN_DEG:g} deg apart in azimuth and under {EL_MIN_DEG:g} in elevation (a sound against a part), '
             f'e.g. "{a}" and "{b}" ({daz:.0f} deg, {de:.0f} deg): the gate row spatial.z_separation fails the same pair once their mid bands overlap. '
             'Move one 25 deg or more in azimuth or 15 deg in height')]


def _shared_seconds(sa, sb):
    total, j = 0.0, 0
    for a0, a1 in sa:
        while j < len(sb) and sb[j][1] <= a0:
            j += 1
        k = j
        while k < len(sb) and sb[k][0] < a1:
            total += max(0.0, min(a1, sb[k][1]) - max(a0, sb[k][0]))
            k += 1
    return total


def clock_rows(score):
    """The plan's section times against the tempo map the renderer will play. A plan (and every preset curve and trigger that was
    written from it) built on another clock is wrong by seconds, and the audio rows find it only after a render: one project's plan
    was ten seconds off because its map was sized for the default 64 beats, not for its notes."""
    secs = (score.get('plan') or {}).get('sections') or []
    if not secs or not score.get('tempo_points'):
        return []
    sec = _clock(score)
    ts = score.get('ts') or [4, 4]
    bpb = float(ts[0]) * 4.0 / float(ts[1])
    worst, where = 0.0, None
    for s in secs:
        if 'start_bar' in s and 'start_s' in s:
            d = abs(float(sec((float(s['start_bar']) - 1) * bpb)) - float(s['start_s']))
            if d > worst:
                worst, where = d, s.get('name')
    if worst > 0.25:
        return [('FAIL', 'preflight.clock', f'section "{where}" starts {worst:.2f} s away from where the renderer\'s tempo map puts its bar: the plan, '
                 f'the direction sheet and every time written from it use another clock. Build the plan from hz.tempo_map_for(score) on the full score')]
    return [('PASS', 'preflight.clock', f'every section starts within {worst:.2f} s of the renderer\'s tempo map')]


def full_checks(score, project_dir=None, **kw):
    """The rows the pipeline's stage 2 runs, in one call: the acoustic and cognitive laws, the score-against-presets rows, the focus and
    the intent rows. The pipeline and the command line both use it, so a score cannot pass here and fail the same rows at render time."""
    import pattern_audit
    import quality_gate as qg
    rows = list(pattern_audit.acoustic_checks(score))
    rows += [r for r in checks(score, project_dir, **kw) if r[0] in ('FAIL', 'WARN')]
    extra = []
    qg.focus_rows(score, extra)
    qg.intent_rows(score, extra)
    rows += [r for r in extra if r[0] in ('FAIL', 'WARN')]
    return rows


def checks(score, project_dir=None, lookup=None, patch_range=None, probe=True, render=None):
    """Every preflight row for this score. `lookup(kind, name)`, `patch_range(block, project)` and `render(name, seconds, sr, seed)`
    are injectable for tests; `probe=False` skips the one-shot renders of preset_probe."""
    lookup = lookup or default_lookup
    patch_range = patch_range or default_patch_range
    rows = []
    rows += range_rows(score, lookup, patch_range, project_dir)
    rows += sfx_length_rows(score, lookup)
    rows += fx_rows(score, lookup)
    rows += section_edge_rows(score)
    rows += unison_rows(score)
    rows += figure_level_rows(score)
    rows += placement_rows(score, lookup)
    rows += clock_rows(score)
    import preflight_levels
    rows += preflight_levels.checks(score)
    import roughness_forecast
    rows += roughness_forecast.forecast_rows(score, lambda name_kind, name=None: lookup(*(name_kind if isinstance(name_kind, tuple) else ('instrument', name_kind))) if name is None else lookup(name_kind, name))
    if probe:
        import preset_probe
        rows += preset_probe.probe_rows(score, lambda name: lookup('sfx', name), render)
    return rows


if __name__ == '__main__':
    import json
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    path = sys.argv[1]
    proj = sys.argv[2] if len(sys.argv) > 2 else None
    if proj:
        import presets
        presets.add_project(proj)
    for lvl, name, detail in full_checks(json.load(open(path, encoding='utf-8')), proj):
        if lvl != 'PASS':
            print(f'[{lvl}] {name}: {detail}')
