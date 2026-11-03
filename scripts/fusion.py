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
"""fusion.py - plan a blend of ANY cultures: one scale, one tempo, one meter, instruments by role, rhythm patterns.

    brief = {"fusion": ["indian", "west_african"], "duration_s": 60, "emotion": "joyful"}
    compose.py --brief brief.json          # compose() calls plan() and apply() when "fusion" is set

How it chooses (the rules the skill follows, see references/cultures-fusion.md):
  1. SCALE: a scale every selected culture uses (same pitch classes). If none, the scale that most cultures share.
     Any scale a selected culture avoids is rejected. A heptatonic scale with an augmented second (3 semitones
     between adjacent degrees, e.g. Hijaz, Bhairav) is rejected unless "arabic" is one of the cultures.
  2. TEMPO: the overlap of the cultures' tempo ranges; if they do not overlap, the nearest point to all of them.
  3. METER: compound (6 beats per bar, 12/8 or 6/8) if any culture is compound, so the bell and dadra share one grid.
     A 4/4 culture contributes instruments and melody; its own rhythm is not forced onto the 12/8 grid.
  4. INSTRUMENTS: each culture's core sounds by role (lead, pluck, bass, pad, drone, lift), minus anything another
     selected culture avoids. Western orchestra is never added here.
  5. RHYTHM: each compound culture's pattern (dadra, 12/8 bell, jig) becomes a drum track.

Every number and name here is a data entry: add a culture by adding one CULTURES item.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theory  # noqa: E402  (its MODES include the world scales)
import soul    # noqa: E402  (what each culture needs to feel alive; see references/cultural-soul.md)

# Sources for the rhythm and scale facts are listed in references/cultures-fusion.md.
import presets  # noqa: E402  (every tunable value comes from the presets: references/presets, and each project's presets/)


def _cultures_from_presets():
    out = {}
    for name, c in presets.load('cultures').items():
        c = dict(c)
        c['bpm'] = tuple(c['bpm'])
        out[name] = c
    return out


CULTURES = _cultures_from_presets()


# A style is an overlay on the planned roles: the same cultures, a different production voice. Each style is a JSON file
# in references/styles/ (name, note, roles_add, sources). Adding a style is adding a file, not changing code.
SKILL_REFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references')
PRESET_ROOTS = []                       # project preset folders (<project>/presets); the latest one added wins


def use_project(project_dir):
    """Use a project's own presets: <project>/presets/styles, /cultures and /soul. They add to the skill's presets and
    override them by name. Call it once, before composing. Cultures in the project are added to CULTURES here."""
    presets.add_project(project_dir)
    CULTURES.clear()
    CULTURES.update(_cultures_from_presets())


def load_styles():
    """Every style, keyed by name: the skill's references/styles, then the project's presets/styles."""
    return presets.load('styles')


def _pcs_mod12(scale):
    return frozenset(s % 12 for s in theory.MODES[scale])


def _has_aug_second(scale):
    steps = [(b - a) % 12 for a, b in zip(theory.MODES[scale], theory.MODES[scale][1:])]
    return len(theory.MODES[scale]) == 7 and 3 in steps


def plan(cultures, key='D', style=None, pocket=False):
    """Return the fusion plan dict. Raises ValueError for an unknown culture name."""
    cultures = [c.lower().strip().replace(' ', '_') for c in cultures]
    for c in cultures:
        if c not in CULTURES:
            raise ValueError(f'unknown culture "{c}". Known: {sorted(CULTURES)}')
    if len(set(cultures)) < 2:
        raise ValueError('a fusion needs at least two different cultures')
    warnings = []
    arabic_ok = 'arabic' in cultures

    # 1 scale
    candidates = []
    for c in cultures:
        for s in CULTURES[c]['scales']:
            if s not in candidates:
                candidates.append(s)
    # a foreign scale is avoided only when no culture in the mix owns it: an Arabic mix keeps its own maqamat
    own = {_pcs_mod12(s) for c in cultures for s in CULTURES[c]['scales']}
    avoid = {s for c in cultures for s in CULTURES[c]['avoid_scales'] if _pcs_mod12(s) not in own}
    scored = []
    for s in candidates:
        if any(_pcs_mod12(s) == _pcs_mod12(a) for a in avoid):
            continue
        if not arabic_ok and _has_aug_second(s):
            continue
        cover = sum(any(_pcs_mod12(t) == _pcs_mod12(s) for t in CULTURES[c]['scales']) for c in cultures)
        scored.append((cover, -candidates.index(s), s))
    if not scored:
        raise ValueError(f'no scale survives the avoid rules for {cultures}')
    best = max(scored)
    scale = best[2]
    if best[0] < len(cultures):
        warnings.append(f'no scale is shared by every culture; using {scale}, shared by {best[0]} of {len(cultures)}')

    # 2 tempo
    lo = max(CULTURES[c]['bpm'][0] for c in cultures)
    hi = min(CULTURES[c]['bpm'][1] for c in cultures)
    if lo <= hi:
        bpm = int(round((lo + hi) / 2))
    else:
        mids = [sum(CULTURES[c]['bpm']) / 2 for c in cultures]
        bpm = int(round(float(np.median(mids))))
        warnings.append(f'tempo ranges do not overlap; using {bpm} bpm, between the cultures')

    # 3 meter
    compound = [c for c in cultures if CULTURES[c]['meter'] == 6]
    meter = 6 if compound else 4
    # Groove pocket rule: when pocket=True, compound/polyrhythmic fusions breathe in 96-104 bpm
    if pocket and compound and bpm > 106:
        bpm = min(bpm, 104)
    if compound and len(compound) < len(cultures):
        warnings.append('4/4 cultures are placed on the compound grid: their instruments and melody are used, their rhythm is not')

    # 4 instruments by role (order = the cultures' order)
    roles = {}
    owned = {n for c in cultures for names in CULTURES[c]['roles'].values() for n in names}
    avoid_inst = {n for o in cultures for n in CULTURES[o]['avoid_instruments'] if n not in owned}
    for c in cultures:
        for role, names in CULTURES[c]['roles'].items():
            for n in names:
                if n in avoid_inst:
                    continue
                lst = roles.setdefault(role, [])
                if n not in lst:
                    lst.append(n)

    # the style overlay: its instruments go first in each role, so the style leads and the cultures support
    if style:
        styles = load_styles()
        if style not in styles:
            raise ValueError(f'unknown style "{style}". Known: {sorted(styles)} (add references/styles/{style}.json)')
        for role, names in styles[style]['roles_add'].items():
            roles[role] = list(dict.fromkeys(names + roles.get(role, [])))

    # 5 rhythm patterns (compound cultures only), at most two tracks
    patterns = []
    for c in cultures:
        p = CULTURES[c]['pattern']
        if p and CULTURES[c]['meter'] == meter and p not in patterns:
            patterns.append(p)
    return dict(cultures=cultures, mode=scale, tonic=key, bpm=bpm, meter=meter, roles=roles, soul=soul.merged(cultures),
                style=style,
                patterns=patterns[:2], warnings=warnings,
                notes={c: CULTURES[c]['note'] for c in cultures})


def apply(brief, fp):
    """Fill the brief from the plan. Anything the brief already sets wins. The mood is NOT invented here (a
    fusion used to default to 'joyful', 108-130 BPM and driving, which is why every fusion came out upbeat), and
    the planned tempo is a hint, not an order: the mood and any "slow" / "uptempo" word still move it."""
    out = dict(brief)
    out.setdefault('mode', fp['mode'])
    out.setdefault('key', fp['tonic'])
    out.setdefault('bpm_hint', fp['bpm'])
    out.setdefault('beats_per_bar', fp['meter'])
    return out


def group_G(fp, G):
    """A genre-like layer set built from the plan's roles. Drums come from the pattern tracks, not a kit layer."""
    layers = []
    roles = fp['roles']
    soul_req = fp.get('soul')
    pluck = roles.get('pluck', [])
    bass = roles.get('bass', [])
    lead = roles.get('lead', [])
    pad = roles.get('pad', []) + roles.get('drone', [])
    lift = roles.get('lift', [])
    used = set()

    def take(lst):
        for n in lst:
            if n not in used:
                used.add(n)
                return n
        return None

    anchor = take(pluck)
    if anchor:
        layers.append(dict(name='anchor', instrument=anchor, kind='chords', tex_low='sparse', tex_mid='arp8', tex_hi='arp16',
                           lo=48, hi=72, min=0.0, role='chord'))
    b = take(bass)
    if b:
        layers.append(dict(name='bass', instrument=b, kind='bass', bass='half', lo=33, hi=48, min=0.0, role='bass', gain_db=-1))
    ld = take(lead)
    req = soul_req or {}
    if ld:
        # ornament the soul needs: slides into some notes (meend, kan, portamento)
        glide = 0.3 if req.get('ornament') else 0.0
        layers.append(dict(name='lead', instrument=ld, kind='melody', oct=0, min=0.2, role='melody', gain_db=-2,
                           glide=glide))
    pd = take(pad)
    if pd:
        layers.append(dict(name='pad', instrument=pd, kind='pad', lo=45, hi=72, min=0.15, role='pad', gain_db=-3))
    lf = take(lift) or take(lead)
    if lf:
        layers.append(dict(name='lift', instrument=lf, kind='harmony', min=0.8, role='counter', oct=0, gain_db=-3))
    chorus = roles.get('chorus', [])
    if chorus:                                          # chorus and hums: the community voice, entering with the build
        layers.append(dict(name='chorus', instrument=chorus[0], kind='pad', lo=52, hi=72, min=0.5, role='pad', gain_db=-6))
    # Anti-clutter: keep at most 1 subtle textural extra rather than stacking every unused instrument
    for i, n in enumerate([x for x in pluck + bass + lead + pad + lift if x not in used][:1]):
        layers.append(dict(name=f'extra{i}', instrument=n, kind='pad', lo=48, hi=72, min=0.7, role='pad', gain_db=-10))
    return dict(G, layers=layers, groove=None)


# ------------------------------------------------------------------------------------------------
# rhythm patterns. One bar each; t is in beats; bb = beats per bar (6 for a 12/8 or 6/8 bar).
# ------------------------------------------------------------------------------------------------
def _pattern_bar(name, bb, vel, rng):
    out = []
    if name == 'dadra':                               # 6 matras, two halves of 3 beats; one matra = half a beat
        bols = [('tabla_ge', 0.0, 1.0), ('tabla_na', 0.5, 0.8), ('tabla_ti', 1.0, 0.7),
                ('tabla_ge', 1.5, 0.9), ('tabla_tin', 2.0, 0.8), ('tabla_na', 2.5, 0.75)]
        for cycle in range(0, int(bb), 3):
            for bol, beat, w in bols:
                if cycle + beat < bb:
                    out.append(dict(t=cycle + beat, d=0.2, p=bol, v=vel * w))
    elif name == 'bell12':                            # standard 7-stroke bell over 12 pulses (pulse = half a beat)
        for k in [0, 2, 3, 5, 7, 8, 10]:
            if k * 0.5 < bb:
                out.append(dict(t=k * 0.5, d=0.2, p='agogo_high', v=vel * (1.0 if k in (0, 5) else 0.8)))
    elif name == 'jig':                               # 6/8 jig: a kick on each dotted half, closed hat on every beat
        for t in (0.0, 3.0):
            if t < bb:
                out.append(dict(t=t, d=0.2, p='kick', v=vel))
        for t in np.arange(0, bb, 0.5):
            out.append(dict(t=float(t), d=0.1, p='hat_closed', v=vel * (0.5 if t % 1 == 0 else 0.3)))
    elif name in theory.GROOVES:                      # a named groove from the 16-step library (adi, tamil_film, maqsum...)
        out = theory.groove_bar(name, bb, vel, rng)
    else:
        raise ValueError(f'unknown pattern {name}')
    for n in out:
        n['v'] = float(np.clip(n['v'] * rng.uniform(0.94, 1.0), 0.05, 1.0))
    return out


def pattern_tracks(fp, n_bars, bb, inten, seed=52):
    """One drum track per pattern. Velocity follows the piece's intensity curve."""
    rng = np.random.default_rng(seed)
    tracks = []
    for name in fp['patterns']:
        notes = []
        for bar in range(n_bars):
            vel = float(np.clip(0.5 + 0.35 * float(inten[bar]), 0.2, 0.95))
            bar_notes = _pattern_bar(name, bb, vel, rng)
            # the groove moves from bar to bar (ghosts, dropped hits, pickups): a static loop reads as a machine
            from compose import vary_bar          # imported here: compose imports this module at its top
            bar_notes = vary_bar(bar_notes, 'drums', bar, bb, 0.6, rng)
            notes += [dict(n, t=n['t'] + bar * bb) for n in bar_notes]
        tracks.append(dict(name=f'pattern_{name}', instrument='standard', role='drum', gain_db=-3, notes=notes))
    return tracks


def shape_for_soul(tracks, fp, bb):
    """Make the parts the soul asks for. Call and response: the melody is split by 4-bar phrases into a call and an
    answer, on two voices. Breath: every 4-bar phrase ends with a rest of soul.breath_beats before the next one."""
    req = fp.get('soul') or {}
    mel = [t for t in tracks if t.get('role') == 'melody' and len(t.get('notes', [])) >= 4]
    if not mel:
        return tracks
    lead = mel[0]
    if req.get('call_response'):
        phrase = 4 * bb
        call = [n for n in lead['notes'] if int(n['t'] // phrase) % 2 == 0]
        answer = [dict(n, v=n['v'] * 0.92) for n in lead['notes'] if int(n['t'] // phrase) % 2 == 1]
        lead['notes'] = call
        names = fp['roles'].get('lead', [])
        inst = names[1] if len(names) > 1 else lead['instrument']
        tracks.append(dict(name='answer', instrument=inst, role='counter', notes=answer, gain_db=-3))
        # 3-Tier Hierarchy: Midground chords and arps back off during solo dialogue so lead voices stay clear
        for t in tracks:
            if t.get('role') in ('chord', 'arp'):
                for n in t.get('notes', []):
                    n['v'] = float(np.clip(n['v'] * 0.82, 0.05, 1.0))
    breath = float(req.get('breath_beats', 0.0))
    melodic = [t for t in tracks if t.get('role') in ('melody', 'counter') and t.get('notes')]
    if breath > 0:
        phrase = 2 * bb                          # a rest every 2 bars: every 4-bar window holds one
        for t in melodic:
            for b in np.arange(phrase, t['notes'][-1]['t'] + phrase, phrase):
                for n in t['notes']:
                    if b - breath <= n['t'] < b:          # starts inside the rest: it begins on the phrase's downbeat
                        n['t'] = float(b)
                    elif n['t'] < b - breath < n['t'] + n['d']:   # crosses the rest: cut so the rest is silent
                        n['d'] = max(0.1, (b - breath) - n['t'])
            t['notes'].sort(key=lambda n: n['t'])
    # phrase shape: every line swells and lets go over each 4-bar phrase (no flat velocity)
    for t in melodic:
        for n in t['notes']:
            pos = (n['t'] % (4 * bb)) / (4 * bb)
            n['v'] = float(np.clip(n['v'] * (0.82 + 0.3 * np.sin(np.pi * pos)), 0.05, 1.0))
    return tracks


if __name__ == '__main__':
    import json
    print(json.dumps(plan(sys.argv[1:] or ['indian', 'west_african']), indent=2))
