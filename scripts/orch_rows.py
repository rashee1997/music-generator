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
"""orch_rows.py - is the orchestral writing something a player, or a sampled orchestra, could honour?

    python scripts/orch_rows.py score.json [--project DIR]

Judged from the score alone (no audio, so it runs in stage 2 before any render):

    orch.range           a note outside the playing range of its instrument (FAIL only far outside it)
    orch.voice_leading   parallel perfect fifths between two lines (octaves only with `include_octaves`, and never a doubling)
    orch.playable        more simultaneous notes than the player or section has, a repeated-note run faster than the
                         tongue or bow, or a wind/brass phrase with no room to breathe
    orch.legato          two notes marked legato with a gap between them: a sampler plays that as two detached notes

The numbers are in `references/data/presets/orchestra/ranges.json` (a project may override it in
`<project>/presets/orchestra/ranges.json`) and every one is a starting value there. The rows are WARN unless a note is
more than `fail_over_semitones` beyond the range: nothing here says a line sounds good, only that it is hard to play.
An instrument that cannot be identified from its preset, name or track name is skipped, never guessed.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import deep_merge  # noqa: E402
import gate_clock  # noqa: E402
import gate_profiles  # noqa: E402
import presets  # noqa: E402
import roles  # noqa: E402

SKIP_ROLES = ('drum', 'environment', 'fx')
MODIFIERS = {'alto', 'bass', 'tenor', 'baritone', 'contra', 'sub', 'soprano'}      # `low` and `high` name a register, not an instrument
DOUBLING_SHARE = 0.6        # starting value: this share of two lines' moves in parallel octaves is a doubling by design
MAX_MONO_SHARE = 0.9        # a line is monophonic when this share of its onsets carry one note
OVERLAP_BEATS = 0.1         # two notes sound together only when they overlap by this much
BREATH_S = 0.15             # a gap this long is a breath or a bow change
RUN_MIN_NOTES = 6           # a repeated-note run shorter than this is an ornament, not a texture
MAX_PAIR_TRACKS = 40


# ------------------------------------------------------------------ data
def table(project_roots=None):
    """The ranges table: the shipped file, then every project's override merged on top."""
    path = os.path.join(presets.SKILL_PRESETS, 'orchestra', 'ranges.json')
    with open(path, encoding='utf-8') as fh:
        out = json.load(fh)
    for root in (presets.PROJECT_ROOTS if project_roots is None else project_roots):
        over = os.path.join(root, 'orchestra', 'ranges.json')
        if os.path.isfile(over):
            with open(over, encoding='utf-8') as fh:
                out = deep_merge.merge(out, json.load(fh))
    return out


def problems(tab):
    """Everything wrong with a ranges table (empty = good). Tests and `presets.py validate` callers use it."""
    out = []
    ins = tab.get('instruments')
    if not isinstance(ins, dict) or not ins:
        return ['"instruments" must be a non-empty object']
    for name, e in ins.items():
        if not isinstance(e, dict):
            out.append(f'{name}: expected an object')
            continue
        lo, hi = e.get('lo'), e.get('hi')
        if not (isinstance(lo, int) and isinstance(hi, int) and 0 <= lo < hi <= 127):
            out.append(f'{name}: "lo" and "hi" must be integers with 0 <= lo < hi <= 127')
        if not (isinstance(e.get('voices'), int) and e['voices'] >= 1):
            out.append(f'{name}: "voices" must be an integer >= 1')
        if not (isinstance(e.get('max_rate_hz'), (int, float)) and e['max_rate_hz'] > 0):
            out.append(f'{name}: "max_rate_hz" must be a positive number')
        ph = e.get('max_phrase_s')
        if ph is not None and not (isinstance(ph, (int, float)) and ph > 0):
            out.append(f'{name}: "max_phrase_s" must be null or a positive number')
    for alias, target in (tab.get('aliases') or {}).items():
        if target not in ins:
            out.append(f'alias "{alias}" points at "{target}", which is not an instrument')
    return out


# ------------------------------------------------------------------ identification
def _norm(name):
    return re.sub(r'[^a-z0-9]+', '_', str(name).lower()).strip('_')


def _resolve(word, tab):
    ins, al = tab['instruments'], tab.get('aliases') or {}
    for w in (word, word[:-1] if word.endswith('s') else None):
        if w and w in ins:
            return w
        if w and w in al:
            return al[w]
    return None


def instrument_key(name, tab):
    """The table key a name stands for, or None. The whole name first; then its words, unless a word such as `bass` or
    `alto` says it is a different instrument from the one the other word names (bass_clarinet is not a clarinet)."""
    n = _norm(name)
    if not n:
        return None
    hit = _resolve(n, tab)
    if hit:
        return hit
    words = [w for w in n.split('_') if w]
    found = [h for h in (_resolve(w, tab) for w in words) if h]
    if not found:
        return None
    if any(w in MODIFIERS for w in words) and len(words) > 1:
        return None
    return found[0] if len(set(found)) == 1 else None


def identify(track, tab, exact=None):
    """The table key for a track: the instrument preset's `gm` or `instrument`, then the instrument name, then the
    track name. A prefixed instrument (sfx:, env:, sfz:, clone:, vocal) is not identified."""
    exact = exact or presets.exact
    inst = str(track.get('instrument', ''))
    if ':' in inst:
        return None
    cfg = exact('instruments', inst) if inst else None
    cands = []
    if isinstance(cfg, dict):
        cands += [cfg.get('gm'), cfg.get('instrument')]
    cands += [inst, track.get('name')]
    for c in cands:
        if isinstance(c, str):
            hit = instrument_key(c, tab)
            if hit:
                return hit
    return None


def _role(track):
    try:
        return roles.canonical(track.get('role'), default='')
    except roles.UnknownRole:
        return ''


def _is_section(track, entry, tab):
    if entry.get('section') or track.get('section'):
        return True
    ens = track.get('ensemble')
    if isinstance(ens, dict) and int(ens.get('players', 1) or 1) >= 2:
        return True
    if int(track.get('players', 1) or 1) >= 2:
        return True
    words = set(_norm(track.get('name', '')).split('_')) | set(_norm(track.get('instrument', '')).split('_'))
    return bool(words & set(tab.get('section_words') or []))


def _pitched(track):
    return [n for n in track.get('notes') or [] if isinstance(n.get('p'), (int, float)) and not isinstance(n.get('p'), bool)]


def _instrument_lookup():
    """presets.exact reads every instrument file on each call; one read serves every track of the score."""
    loaded = presets.load('instruments')
    return lambda kind, name: loaded.get(presets._norm(name)) if kind == 'instruments' else None


def _candidates(score, tab, exact=None):
    """[(track, key, entry)] for every pitched track the table knows."""
    exact = exact or _instrument_lookup()
    out = []
    for t in score.get('tracks') or []:
        if _role(t) in SKIP_ROLES or not _pitched(t):
            continue
        key = identify(t, tab, exact)
        if key:
            out.append((t, key, tab['instruments'][key]))
    return out


def _name(t):
    return t.get('name', '?')


# ------------------------------------------------------------------ rows
def range_rows(score, gp, tab, cands):
    out = []
    fail_over = int(gp.param('orch.range', 'fail_over_semitones'))
    for t, key, e in cands:
        if t.get('extended_range'):
            continue
        ps = [int(n['p']) for n in _pitched(t)]
        low = [p for p in ps if p < e['lo']]
        high = [p for p in ps if p > e['hi']]
        if not (low or high):
            out.append(('PASS', 'orch.range', f'"{_name(t)}" ({key}): all {len(ps)} note(s) inside {e["lo"]}-{e["hi"]}'))
            continue
        over = max((e['lo'] - min(low)) if low else 0, (max(high) - e['hi']) if high else 0)
        level = 'FAIL' if over >= fail_over else 'WARN'
        parts = []
        if low:
            parts.append(f'{len(low)} note(s) down to {min(low)}, {e["lo"] - min(low)} semitone(s) under the lowest ({e["lo"]})')
        if high:
            parts.append(f'{len(high)} note(s) up to {max(high)}, {max(high) - e["hi"]} semitone(s) over the highest ({e["hi"]})')
        out.append((level, 'orch.range',
                    f'"{_name(t)}" ({key}): ' + '; '.join(parts) + '. Move them in, give the line to an instrument that has them, '
                    'or set "extended_range": true on the track if the extreme register is the point'))
    return out


def _line(track):
    """{onset beat: pitch} when the track is a single line, else None."""
    by = {}
    for n in _pitched(track):
        by.setdefault(round(float(n['t']), 3), []).append(int(n['p']))
    if len(by) < 4:
        return None
    mono = sum(1 for v in by.values() if len(v) == 1) / len(by)
    if mono < MAX_MONO_SHARE:
        return None
    return {t: v[0] for t, v in by.items() if len(v) == 1}


def voice_leading_rows(score, gp, tab, cands):
    out = []
    share_max = float(gp.param('orch.voice_leading', 'max_parallel_share'))
    min_events = int(gp.param('orch.voice_leading', 'min_events'))
    octaves = bool(gp.param('orch.voice_leading', 'include_octaves'))     # off: an octave doubling is orchestration, not a fault
    lines = []
    for t in score.get('tracks') or []:
        if _role(t) in SKIP_ROLES or str(t.get('instrument', '')).startswith(('sfx:', 'env:')):
            continue
        ln = _line(t)
        if ln:
            lines.append((t, ln))
    lines = lines[:MAX_PAIR_TRACKS]
    checked = flagged = 0
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            (ta, a), (tb, b) = lines[i], lines[j]
            shared = sorted(set(a) & set(b))
            if len(shared) < min_events + 1:
                continue
            moves = p5 = p8 = 0
            for s0, s1 in zip(shared, shared[1:]):
                da, db = a[s1] - a[s0], b[s1] - b[s0]
                if da == 0 or db == 0:
                    continue
                moves += 1
                if (da > 0) != (db > 0):
                    continue
                i0, i1 = abs(a[s0] - b[s0]), abs(a[s1] - b[s1])
                if i0 % 12 == 7 and i1 % 12 == 7:
                    p5 += 1
                elif i0 > 0 and i1 > 0 and i0 % 12 == 0 and i1 % 12 == 0:
                    p8 += 1
            if moves < min_events:
                continue
            checked += 1
            doubling = p8 / moves >= DOUBLING_SHARE
            count8 = p8 if octaves and not doubling else 0
            bad = p5 + count8
            if bad >= min_events and bad / moves >= share_max:
                flagged += 1
                kinds = []
                if p5:
                    kinds.append(f'{p5} parallel fifth(s)')
                if count8:
                    kinds.append(f'{p8} parallel octave(s)')
                out.append(('WARN', 'orch.voice_leading',
                            f'"{_name(ta)}" and "{_name(tb)}": {" and ".join(kinds)} in {moves} shared moves '
                            f'({bad / moves:.0%}). Move one line by a step, invert the interval, or hold one note while the other moves'))
    if not flagged and checked:
        out.append(('PASS', 'orch.voice_leading', f'{checked} pair(s) of lines: no parallel fifths or undoubled octaves above the limit'))
    return out


def _clusters(notes, gap=0.05):
    out, cur = [], []
    for n in sorted(notes, key=lambda n: n['t']):
        if cur and n['t'] - cur[0]['t'] <= gap:
            cur.append(n)
        else:
            if cur:
                out.append(cur)
            cur = [n]
    if cur:
        out.append(cur)
    return out


def _max_voices(notes):
    """The most notes sounding together at any onset, counting a note only if it still has more than OVERLAP_BEATS left.
    One pass over the onsets with a heap of the ends: O(n log n), where a pairwise count was O(n^2) on a long score."""
    import heapq
    best, i, ends = 0, 0, []
    ordered = sorted(notes, key=lambda n: float(n['t']))
    for n in ordered:
        t = float(n['t'])
        while i < len(ordered) and float(ordered[i]['t']) <= t + 1e-9:
            heapq.heappush(ends, float(ordered[i]['t']) + float(ordered[i].get('d', 1.0)))
            i += 1
        while ends and ends[0] - t <= OVERLAP_BEATS:          # ended, or about to: onsets only move forward, so it never counts again
            heapq.heappop(ends)
        best = max(best, len(ends))
    return best


def playable_rows(score, gp, tab, cands):
    out = []
    sec = gate_clock.seconds_fn(score)
    rate_scale = float(gp.param('orch.playable', 'rate_scale'))
    phrase_scale = float(gp.param('orch.playable', 'phrase_scale'))
    for t, key, e in cands:
        notes = _pitched(t)
        section = _is_section(t, e, tab)
        problems_found = 0
        allowed = e['voices'] * (int(tab.get('section_voices', 4)) if section and not e.get('section') else 1)
        ens = t.get('ensemble')
        if isinstance(ens, dict):
            allowed *= max(1, int(ens.get('players', 1) or 1))
        have = _max_voices(notes)
        if have > allowed:
            problems_found += 1
            out.append(('WARN', 'orch.playable',
                        f'"{_name(t)}" ({key}): {have} notes sound together, one {"section" if section else "player"} has {allowed}. '
                        'Split the part into two tracks, or write a smaller chord'))
        bowed = [n for n in notes if 'trem' not in str(n.get('art', '')).lower()]     # a tremolo is a bow technique, not a note rate
        starts = [float(sec(c[0]['t'])) for c in _clusters(bowed)]
        limit = e['max_rate_hz'] * rate_scale
        run = best = 1
        run_start = best_start = starts[0] if starts else 0.0
        for a, b in zip(starts, starts[1:]):
            if b - a <= 1.0 / limit + 1e-9:
                run += 1
            else:
                run, run_start = 1, b
            if run > best:
                best, best_start = run, run_start
        if best >= RUN_MIN_NOTES:
            problems_found += 1
            out.append(('WARN', 'orch.playable',
                        f'"{_name(t)}" ({key}): a run of {best} notes from {best_start:.1f} s faster than {limit:.1f} notes/s. '
                        'Slow it, or move it to an instrument that can (a harp, a keyboard)'))
        if e.get('max_phrase_s') and not section:
            span_limit = float(e['max_phrase_s']) * phrase_scale
            ordered = sorted(notes, key=lambda n: n['t'])
            start = float(sec(ordered[0]['t']))
            end = float(sec(ordered[0]['t'] + ordered[0].get('d', 1.0)))
            longest, at = 0.0, start
            for n in ordered[1:]:
                n0 = float(sec(n['t']))
                if n0 - end >= BREATH_S:
                    if end - start > longest:
                        longest, at = end - start, start
                    start = n0
                end = max(end, float(sec(n['t'] + n.get('d', 1.0))))
            if end - start > longest:
                longest, at = end - start, start
            if longest > span_limit:
                problems_found += 1
                out.append(('WARN', 'orch.playable',
                            f'"{_name(t)}" ({key}): {longest:.1f} s without a breath from {at:.1f} s (limit {span_limit:.1f} s). '
                            f'Leave a gap of {BREATH_S:g} s or more, or share the line between two parts'))
        if not problems_found:
            out.append(('PASS', 'orch.playable', f'"{_name(t)}" ({key}): within the voices, speed and breath of {"a section" if section else "one player"}'))
    return out


def legato_rows(score, gp):
    out = []
    max_gap = float(gp.param('orch.legato', 'max_gap_beats'))
    for t in score.get('tracks') or []:
        if _role(t) in SKIP_ROLES or str(t.get('instrument', '')).startswith(('sfx:', 'env:')):
            continue
        leg = sorted((n for n in _pitched(t) if str(n.get('art', '')).lower() in ('legato', 'slur', 'slurred')), key=lambda n: n['t'])
        if len(leg) < 2:
            continue
        gaps = []
        for a, b in zip(leg, leg[1:]):
            gap = float(b['t']) - (float(a['t']) + float(a.get('d', 1.0)))
            if 0 < gap <= 2.0 and gap > max_gap:         # a bigger gap is a rest between phrases, not a slur
                gaps.append((gap, float(b['t'])))
        if gaps:
            worst = max(gaps)
            out.append(('WARN', 'orch.legato',
                        f'"{_name(t)}": {len(gaps)} legato note(s) start after a gap of more than {max_gap:g} beat (worst {worst[0]:.2f} beat before beat '
                        f'{worst[1]:g}). A legato patch needs the next note to start before the last one ends: lengthen the note or drop the marking'))
        else:
            out.append(('PASS', 'orch.legato', f'"{_name(t)}": every legato note joins the next'))
    return out


def checks(score, exact=None, tab=None):
    """Every orch.* row for a score, as (level, name, detail). A row the piece's gate profile skips is not run."""
    gp = gate_profiles.resolve(score)
    tab = tab or table()
    cands = _candidates(score, tab, exact)
    rows = []
    if gp.on('orch.range'):
        rows += range_rows(score, gp, tab, cands)
    if gp.on('orch.voice_leading'):
        rows += voice_leading_rows(score, gp, tab, cands)
    if gp.on('orch.playable'):
        rows += playable_rows(score, gp, tab, cands)
    if gp.on('orch.legato'):
        rows += legato_rows(score, gp)
    return rows


def main():
    ap = argparse.ArgumentParser(description='Orchestral-writing rows for a score (no audio).')
    ap.add_argument('score')
    ap.add_argument('--project', default=None)
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    with open(a.score, encoding='utf-8') as fh:
        score = json.load(fh)
    bad = problems(table())
    if bad:
        print('\n'.join(f'ranges table: {b}' for b in bad))
        sys.exit(2)
    worst = 'PASS'
    for level, name, detail in checks(score):
        print(f'[{level}] {name}: {detail}')
        if level == 'FAIL':
            worst = 'FAIL'
    sys.exit(1 if worst == 'FAIL' else 0)


if __name__ == '__main__':
    main()
