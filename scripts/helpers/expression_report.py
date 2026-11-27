# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""expression_report.py - does the written music carry the expression its direction sheet declared?

No neural model and no audio: the numbers come from the score's notes, tempo and key, with published cue directions.
Emotion in music is carried mostly by a few cues - mode, tempo, register, dynamics, articulation (Gabrielsson and
Lindstrom 2010; Eerola, Friberg and Bresin 2013) - and those cues act mostly additively (Eerola et al. 2013), so a
plain mean of normalised cues is a defensible, explainable index. It is an index of arousal (how hard the music
pushes), not of valence: valence from features is weak even in the research, so this module does not claim it.

    python scripts/helpers/expression_report.py scores/<title>_score.json [--direction direction/<sheet>.json]

Two reports
    arousal order   per section of `plan.sections`, an index from tempo, note density, velocity, register and
                    staccato share; its rank order is compared with the sheet's declared section `energy`
                    (Spearman). A cue declared to build whose written notes do not build is flagged.
    melody variety  for the figure track (role melody, lead or vocal): interval entropy, step and leap shares, contour
                    variety, bars that repeat an earlier bar exactly. A theme that is one cell repeated is flagged.

The anchors and limits are the piece's own: they come from its gate profile (`"expression": {...}` in
`<project>/presets/gate/<piece_type>.json`, read by `gate_profiles.Profile.expression_cfg`), because they describe the
piece - a drone cue has no build to rank, a through-composed cue no repeating figure, a sting no phrase. The constants
below are what every profile inherited before that block existed, and what this module uses when nothing passes a cfg.
Every one of them is a STARTING VALUE, not a measured limit; none has been calibrated on a corpus. The module reports
and warns; the gate turns a flag into a WARN, never a FAIL.
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

# starting values: the range each cue is scaled over before the mean
ANCHORS = dict(tempo_bpm=(60.0, 180.0), notes_per_beat=(0.0, 8.0), velocity=(0.2, 1.0), pitch=(36.0, 84.0))
FIGURE_ROLES = ('melody', 'lead', 'vocal')
ARRANGEMENT_SKIP = ('environment', 'fx', 'texture')   # sound design is not what the notes' expression is made of

MIN_SECTIONS = 3              # a rank order of two sections says nothing
MIN_RHO = 0.5                 # starting value: below this the written build does not follow the declared one
MIN_NOTES = 16                # a figure shorter than this has no variety to measure
MAX_IDENTICAL_BAR_SHARE = 0.6
MIN_INTERVAL_ENTROPY_BITS = 1.0
MIN_RANGE_SEMITONES = 7
MIN_INTERVALS_FOR_LEAP = 20   # a line this long with no leap at all has no peak


def defaults():
    """The figures used when no gate profile supplied any: the starting values this module has always shipped with."""
    return dict(anchors={k: tuple(v) for k, v in ANCHORS.items()},
                arousal_order=dict(min_sections=MIN_SECTIONS, min_rho=MIN_RHO),
                melody_variety=dict(min_notes=MIN_NOTES, max_identical_bar_share=MAX_IDENTICAL_BAR_SHARE,
                                    min_interval_entropy_bits=MIN_INTERVAL_ENTROPY_BITS,
                                    min_range_semitones=MIN_RANGE_SEMITONES,
                                    intervals_for_leap_check=MIN_INTERVALS_FOR_LEAP),
                figure_roles=tuple(FIGURE_ROLES), skip_roles=tuple(ARRANGEMENT_SKIP), source='module defaults')


def _tempo_at(score, beat):
    pts = sorted((float(a), float(b)) for a, b in (score.get('tempo_points') or []))
    bpm = float(score.get('bpm', 100))
    for b0, v in pts:
        if b0 <= beat:
            bpm = v
    return bpm


def _scale(x, lo, hi):
    return min(1.0, max(0.0, (x - lo) / (hi - lo)))


def _beats_per_bar(score):
    ts = score.get('ts') or [4, 4]
    return float(ts[0]) * 4.0 / float(ts[1])


def _notes(score, skip=None):
    skip = ARRANGEMENT_SKIP if skip is None else skip
    for tr in score.get('tracks') or []:
        if tr.get('role') in skip:
            continue
        for n in tr.get('notes') or []:
            if 'p' in n and 't' in n:
                yield tr, n


def _unit_velocity(n):
    """A note's velocity on 0..1. Scores carry MIDI velocity (1-127) or a unit value; the anchors are on the unit scale, so
    a MIDI velocity read raw saturated every section at 1.0 and the arousal order could not tell sections apart."""
    v = float(n.get('v', 0.7))
    return v / 127.0 if v > 1.0 else v


def arousal_by_section(score, cfg=None):
    """[{name, energy, index, parts}] one row per plan section that has notes. `parts` holds the five cue values."""
    cfg = cfg or defaults()
    anchors = cfg['anchors']
    bpb = _beats_per_bar(score)
    rows = []
    for s in (score.get('plan') or {}).get('sections') or []:
        a, b = (float(s['start_bar']) - 1) * bpb, float(s['end_bar']) * bpb
        sel = [n for _, n in _notes(score, cfg.get('skip_roles')) if a <= float(n['t']) < b]
        if not sel:
            continue
        beats = max(b - a, 1e-6)
        dens = len(sel) / beats
        vel = sum(_unit_velocity(n) for n in sel) / len(sel)
        # register is the pitched notes' average: a percussion stroke is a name ('dum'), not a pitch
        pitched = [float(n['p']) for n in sel if isinstance(n['p'], (int, float)) and not isinstance(n['p'], bool)]
        pitch = sum(pitched) / len(pitched) if pitched else sum(anchors['pitch']) / 2.0
        stac = sum(1 for n in sel if float(n.get('d', 1.0)) < 0.5) / len(sel)
        tempo = _tempo_at(score, (a + b) / 2.0)
        parts = dict(tempo=_scale(tempo, *anchors['tempo_bpm']), density=_scale(dens, *anchors['notes_per_beat']),
                     velocity=_scale(vel, *anchors['velocity']), register=_scale(pitch, *anchors['pitch']),
                     staccato=stac)
        rows.append(dict(name=str(s.get('name', '?')), energy=s.get('energy'), index=sum(parts.values()) / len(parts),
                         parts=parts))
    return rows


def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def spearman(a, b):
    """Rank correlation with ties averaged; None when either series is constant."""
    if len(a) != len(b) or len(a) < 2:
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return None if den == 0 else num / den


def arousal_order(score, cfg=None):
    """(rho, rows, flag): flag is a sentence when the written build does not follow the declared energy, else ''."""
    cfg = cfg or defaults()
    lim = cfg['arousal_order']
    rows = [r for r in arousal_by_section(score, cfg) if r['energy'] is not None]
    if len(rows) < lim['min_sections']:
        return None, rows, ''
    rho = spearman([float(r['energy']) for r in rows], [r['index'] for r in rows])
    if rho is None:
        return None, rows, ''
    flag = ''
    if rho < lim['min_rho']:
        flag = (f'the written notes follow the declared section energy with rank correlation {rho:+.2f} '
                f'(< {float(lim["min_rho"]):g}): '
                'the sections that are declared to push hardest are not the ones with the fastest, densest, loudest, '
                'highest or most detached notes')
    return rho, rows, flag


def figure_notes(score, cfg=None):
    """The top voice of the figure track, in time order, as [(t, pitch, dur)]. Empty when the piece has none."""
    for role in (cfg or defaults())['figure_roles']:
        for tr in score.get('tracks') or []:
            if tr.get('role') == role and tr.get('notes'):
                ns = sorted(((float(n['t']), int(n['p']), float(n.get('d', 1.0))) for n in tr['notes'] if 'p' in n),
                            key=lambda x: (x[0], -x[1]))
                top, last = [], None
                for t, p, d in ns:
                    if last is None or t - last > 1e-6:
                        top.append((t, p, d))
                        last = t
                return top
    return []


def _entropy(counts):
    n = float(sum(counts.values()))
    return -sum((c / n) * math.log2(c / n) for c in counts.values()) if n else 0.0


def melody_variety(score, cfg=None):
    """dict of measures for the figure track, with `flags`: sentences, empty when the line has variety."""
    cfg = cfg or defaults()
    lim = cfg['melody_variety']
    seq = figure_notes(score, cfg)
    out = dict(notes=len(seq), flags=[])
    if len(seq) < lim['min_notes']:
        out['note'] = f'figure track has {len(seq)} notes (< {lim["min_notes"]:g}): too short to measure'
        return out
    ivs = [seq[i + 1][1] - seq[i][1] for i in range(len(seq) - 1)]
    cl = [max(-12, min(12, i)) for i in ivs]
    out['interval_entropy_bits'] = _entropy(Counter(cl))
    out['step_share'] = sum(1 for i in ivs if 1 <= abs(i) <= 2) / len(ivs)
    out['leap_share'] = sum(1 for i in ivs if abs(i) >= 5) / len(ivs)
    out['repeat_share'] = sum(1 for i in ivs if i == 0) / len(ivs)
    out['range_semitones'] = max(p for _, p, _ in seq) - min(p for _, p, _ in seq)
    signs = [(i > 0) - (i < 0) for i in ivs]
    tri = Counter(tuple(signs[k:k + 3]) for k in range(len(signs) - 2))
    out['contour_trigrams'] = len(tri)
    bpb = _beats_per_bar(score)
    bars = {}
    t0 = seq[0][0]
    for t, p, d in seq:
        k = int((t - t0) // bpb)
        bars.setdefault(k, []).append((round((t - t0) % bpb * 4) / 4.0, p))
    keys = sorted(bars)
    seen, same = [], 0
    for k in keys:
        cell = tuple(bars[k])
        if cell in seen:
            same += 1
        seen.append(cell)
    out['bars'] = len(keys)
    out['identical_bar_share'] = same / len(keys) if keys else 0.0
    f = out['flags']
    if len(keys) >= 4 and out['identical_bar_share'] > lim['max_identical_bar_share']:
        f.append(f'{100 * out["identical_bar_share"]:.0f} % of the figure\'s bars repeat an earlier bar exactly '
                 f'(> {100 * float(lim["max_identical_bar_share"]):.0f} %): one cell, not a theme that develops')
    if out['interval_entropy_bits'] < lim['min_interval_entropy_bits']:
        f.append(f'interval entropy {out["interval_entropy_bits"]:.2f} bits '
                 f'(< {float(lim["min_interval_entropy_bits"]):g}): the line '
                 'moves by almost one interval, which a listener hears as a pattern, not a melody')
    if out['range_semitones'] < lim['min_range_semitones']:
        f.append(f'the line spans {out["range_semitones"]} semitones (< {float(lim["min_range_semitones"]):g}): '
                 'no climb, so no peak')
    if len(ivs) >= lim['intervals_for_leap_check'] and out['leap_share'] == 0:
        f.append('no leap of a fourth or more in the whole line: it has no moment of reach')
    return out


def expression_block_problems(sheet):
    """Sentences for what the direction sheet's `expression` block is missing; [] when it is complete."""
    ex = (sheet or {}).get('expression')
    if not isinstance(ex, dict):
        return ['no `expression` block: the sheet does not say how the music is played and heard']
    out = []
    for key in ('sonic_picture', 'performer', 'producer_moves', 'anti_generic'):
        v = ex.get(key)
        if not (isinstance(v, str) and len(v.split()) >= 6) and not (isinstance(v, list) and v):
            out.append(f'expression.{key} is missing or too short to decide anything')
    cues = ex.get('cues')
    if not (isinstance(cues, list) and cues):
        out.append('expression.cues is empty: no section says its arousal, register, articulation or timbre')
    else:
        need = ('section', 'arousal', 'articulation', 'timbre')
        for c in cues:
            miss = [k for k in need if not (isinstance(c, dict) and c.get(k))]
            if miss:
                out.append(f'expression.cues entry {c.get("section", "?") if isinstance(c, dict) else "?"} lacks ' + ', '.join(miss))
    th = ex.get('theme')
    if isinstance(th, dict) and th:
        for k in ('contour', 'interval_character', 'rhythm_cell', 'why_memorable', 'variation_plan'):
            if not th.get(k):
                out.append(f'expression.theme.{k} is missing')
    elif sheet.get('focus') in FIGURE_ROLES + ('melody',):
        out.append('expression.theme is missing for a piece whose focus is a melody')
    return out


def profile_cfg(score_path, project_dir):
    """The figures the gate would judge this score with: the project's own gate profile's `expression` block."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import gate_profiles
    import presets
    presets.add_project(project_dir)
    score = json.load(open(score_path, encoding='utf-8'))
    return gate_profiles.resolve(score).expression_cfg()


def report(score_path, sheet_path=None, cfg=None):
    cfg = cfg or defaults()
    score = json.load(open(score_path, encoding='utf-8'))
    rho, rows, flag = arousal_order(score, cfg)
    print(f'arousal index by section (tempo, density, velocity, register, staccato) - figures from {cfg.get("source")}')
    print(f'{"section":<18}{"energy":>8}{"index":>8}   cues')
    for r in rows:
        print(f'{r["name"]:<18}{r["energy"]!s:>8}{r["index"]:>8.2f}   ' + ' '.join(f'{k}={v:.2f}' for k, v in r['parts'].items()))
    print('rank correlation with declared energy: ' + ('n/a' if rho is None else f'{rho:+.2f}'))
    if flag:
        print('FLAG: ' + flag)
    mv = melody_variety(score, cfg)
    print(f'figure track: {mv["notes"]} notes' + (f' - {mv["note"]}' if mv.get('note') else ''))
    for k in ('interval_entropy_bits', 'step_share', 'leap_share', 'repeat_share', 'range_semitones', 'contour_trigrams',
              'bars', 'identical_bar_share'):
        if k in mv:
            print(f'  {k}: {mv[k]:.2f}' if isinstance(mv[k], float) else f'  {k}: {mv[k]}')
    for f in mv['flags']:
        print('FLAG: ' + f)
    if sheet_path:
        sheet = json.load(open(sheet_path, encoding='utf-8'))
        for p in expression_block_problems(sheet):
            print('SHEET: ' + p)
    return dict(rho=rho, rows=rows, arousal_flag=flag, melody=mv)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('score')
    ap.add_argument('--direction', default=None, help='the direction sheet JSON, to check its `expression` block')
    ap.add_argument('--project', default=None,
                    help="the project folder: judge with the figures in its gate profile (the gate's own numbers)")
    a = ap.parse_args(argv)
    cfg = profile_cfg(a.score, a.project) if a.project else None
    report(a.score, a.direction, cfg)
    return 0


if __name__ == '__main__':
    sys.exit(main())
