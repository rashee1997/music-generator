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
"""pattern_audit.py - find the 'copy-paste' in a score before anyone has to hear it.

    python3 scripts/pattern_audit.py score.json            # a score from compose.py or a custom script
    python3 scripts/pattern_audit.py score.json --strict   # exit 1 when something is flagged

It reads notes only (no audio), so it is instant. It flags the habits that make music sound like a march, a loop or
a template: bars that are exact copies, a drum part that never changes, every note on the beat, a flat dynamic
curve, one velocity everywhere, a melody with two note lengths, a bass that only ever plays the root.
A flag is a question for the composer, not a verdict: a drone or a minimalist ostinato is repetitive on purpose.
"""
import argparse
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roles  # noqa: E402  (the one role vocabulary: a figure is melody, lead or vocal)


def bar_sigs(notes, bb):
    bars = collections.defaultdict(list)
    for n in notes:
        bars[int(n['t'] // bb)].append((round(n['t'] % bb, 2), n['p'] if isinstance(n['p'], str) else n['p'] % 12))
    return [tuple(sorted(bars[b])) for b in range(max(bars) + 1)] if bars else []


def best_period(sigs):
    """smallest loop length (bars) that explains >= 90% of the bars, else 0"""
    for p in range(1, len(sigs) // 2 + 1):
        same = sum(sigs[i] == sigs[i + p] for i in range(len(sigs) - p))
        if same >= 0.9 * (len(sigs) - p):
            return p
    return 0


# ------------------------------------------------------------------------------------------------
# acoustic & music-theory rules. These are the rules that make a score sound like an instrument rather
# than a MIDI file; quality_gate.score_checks() prints them as its own rows and the CLI lists them.
# ------------------------------------------------------------------------------------------------
PLUCKED = {'acoustic_guitar', 'nylon_guitar', 'harp', 'kora', 'oud', 'guzheng'}
BRIGHT = {39: 'clap', 38: 'snare', 40: 'snare', 37: 'rim', 54: 'tambourine'}
BRIGHT_NAMES = set(BRIGHT.values())


def _role(t):
    """The canonical role of a track ('' when it has none or an unknown one; roles.problems() reports those)."""
    try:
        return roles.canonical(t.get('role'), default='')
    except roles.UnknownRole:
        return ''


def _is_figure(t):
    """The figure family: melody, lead or vocal."""
    return roles.is_lead(t.get('role'))


def _is_melodic(t):
    """A line the ear follows: the figure family or a counter-line."""
    return _is_figure(t) or _role(t) == 'counter'


def _vel(n):
    v = float(n.get('v', 0.7))
    return v / 127.0 if v > 1.5 else v


def _clusters(notes, gap=0.05):
    """group note onsets that start within `gap` beats of the first note of the cluster"""
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


def _runs(hits, gap):
    out, cur = [], []
    for n in hits:
        if cur and n['t'] - cur[-1]['t'] <= gap + 1e-9:
            cur.append(n)
        else:
            if cur:
                out.append(cur)
            cur = [n]
    if cur:
        out.append(cur)
    return out


def chord_voicing_and_strum(score):
    rows = []
    for t in score['tracks']:
        inst = str(t.get('instrument', '')).lower()
        if _role(t) not in ('chord', 'counter') and 'piano' not in inst and 'guitar' not in inst:
            continue
        chords = [c for c in _clusters(t.get('notes', [])) if len(c) >= 3]
        if not chords:
            continue
        flat = sum(1 for c in chords if np.std([_vel(n) for n in c]) < 0.005) / len(chords)
        if flat >= 0.4:
            detail = (f"Track '{t['name']}' has {flat:.0%} flat-velocity block chords. Voice chords naturally by "
                      'boosting the top note (e.g. vel * (0.88 + 0.05 * idx)).')
            rows.append(('FAIL' if flat >= 0.6 else 'WARN', 'chord_voicing_and_strum', detail))
        if 'guitar' in inst and 'muted_guitar' not in inst:
            block = sum(1 for c in chords if max(n['t'] for n in c) - min(n['t'] for n in c) < 0.005) / len(chords)
            if block >= 0.5:
                rows.append(('FAIL', 'chord_voicing_and_strum',
                             f"Guitar track '{t['name']}' has {block:.0%} un-strummed simultaneous block chords. "
                             'Stagger chord tones by idx * 0.015 to 0.025 beats and alternate down/upstrokes.'))
    return rows


def choked_resonance(score):
    rows = []
    for t in score['tracks']:
        if str(t.get('instrument', '')).lower() not in PLUCKED:
            continue
        ns = t.get('notes', [])
        if not ns:
            continue
        short = [n for n in ns if n.get('d', 0) <= 0.42]
        pct = len(short) / len(ns)
        stac = sum(1 for n in short if str(n.get('art', '')).lower() == 'staccato') / max(len(short), 1)
        avg = float(np.mean([n.get('d', 0) for n in ns]))
        if pct >= 0.5 and (stac >= 0.5 or (_role(t) == 'chord' and avg < 0.35)):
            rows.append(('FAIL', 'choked_resonance',
                         f"Track '{t['name']}' has {pct:.0%} short staccato notes (d <= 0.42), choking SoundFont body "
                         "resonance. Increase strum durations to 0.6-1.0 beats and use 'legato' articulation."))
    return rows


def _machine_run(vv):
    """True when a run of repeated hits has no dynamic contour: the peak-to-trough is under 10% of the mean level
    (a stamped machine gun), or the contour is a single straight ramp with no accent inside it. Judging the spread
    against the run's own mean keeps a quiet 16th-note shaker (velocity 0.06) to the same standard as a loud one."""
    if len(vv) < 4:
        return False
    vv = np.asarray(vv, dtype=float)
    spread = float(vv.max() - vv.min())
    if spread < 0.10 * max(float(vv.mean()), 1e-6):
        return True
    x = np.arange(len(vv))
    slope, icpt = np.polyfit(x, vv, 1)
    resid = float(np.max(np.abs(vv - (slope * x + icpt))))
    return resid < 0.06 * spread and abs(slope) * (len(vv) - 1) > 0.5 * spread


def machine_gun_percussion(score):
    rows = []
    for t in score['tracks']:
        if _role(t) != 'drum':
            continue
        by_p = collections.defaultdict(list)
        for n in sorted(t.get('notes', []), key=lambda n: n['t']):
            by_p[n['p']].append(n)
        for p, hits in by_p.items():
            for run in _runs(hits, 0.5):
                if len(run) < 6:
                    continue
                if _machine_run([_vel(n) for n in run]):
                    rows.append(('FAIL', 'machine_gun_percussion',
                                 f"Drum pitch {p} has a robotic 'machine-gun' run at beat {run[0]['t']:.1f} "
                                 f'({len(run)} hits with flat or linear velocity). Use an exponential curve '
                                 '((step/N)**1.6) plus alternating downbeat/upbeat accents (+0.04 on even steps, '
                                 '-0.04 on odd steps).'))
                    break
    return rows


def percussion_flam(score):
    rows = []
    for t in score['tracks']:
        if _role(t) != 'drum':
            continue
        hits = []
        for n in t.get('notes', []):
            p = n['p']
            label = BRIGHT.get(p) if isinstance(p, (int, float)) else p
            if label in BRIGHT_NAMES:
                hits.append((n['t'], label))
        hits.sort()
        count, pairs = 0, collections.Counter()
        for i, (t1, p1) in enumerate(hits):
            for t2, p2 in hits[i + 1:]:
                if t2 - t1 >= 0.003:
                    break
                if p1 != p2:
                    count += 1
                    pairs[(p1, p2)] += 1
        if count > 4:
            p1, p2 = pairs.most_common(1)[0][0]
            rows.append(('FAIL', 'percussion_flam',
                         f'Drum track has {count} phase-locked simultaneous hits between {p1} and {p2}. Offset secondary '
                         'layered percussion (e.g. tambourine/clap) by +0.02 to +0.03 beats (~10-15ms) for a natural '
                         'human flam.'))
    return rows


def low_interval_mud(score):
    rows = []
    for t in score['tracks']:
        if _role(t) not in ('chord', 'pad', 'arp'):
            continue
        chords = [c for c in _clusters(t.get('notes', [])) if len(c) >= 3]
        if not chords:
            continue
        bad = 0
        for c in chords:
            ps = sorted(int(n['p']) for n in c)
            if any(1 <= b - a <= 4 and b < 53 for a, b in zip(ps, ps[1:])):
                bad += 1
        pct = bad / len(chords)
        if pct > 0.2:
            rows.append(('FAIL' if pct > 0.5 else 'WARN', 'low_interval_mud',
                         f"Track '{t['name']}' has close intervals (< 5 semitones) below F3 (MIDI 53) in {pct:.0%} of "
                         'chords, causing low-mid mud. Spread lower voicings (root-5th-10th) or raise chord register lo >= 52.'))
    return rows


def spatial_glue(score):
    room = score.get('space') or score.get('room') or 'hall'
    if room == 'none':
        return []
    tracks = score['tracks']
    if not any(float(t.get('reverb', 0) or 0) > 0.1 for t in tracks):
        return []
    rows = []
    for t in tracks:
        if 'reverb' in t and float(t['reverb'] or 0) == 0.0 and (_role(t) in ('chord', 'pad', 'arp', 'counter')
                                                                                  or _is_figure(t)):
            rows.append(('WARN', 'spatial_glue',
                         f"Track '{t['name']}' has reverb=0 in a '{room}' score, creating a dry stock-MIDI mismatch. "
                         "Set 'reverb': 0.15-0.22 so all acoustic instruments share the room."))
    return rows


ACOUSTIC_PHYSICAL_INSTS = {
    'flute', 'pan_flute', 'shakuhachi', 'recorder', 'tin_whistle', 'oboe', 'clarinet', 'bassoon',
    'duduk', 'ney', 'bamboo_flute', 'quena', 'siku', 'violin', 'viola', 'cello', 'contrabass',
    'strings', 'slow_strings', 'sarangi', 'erhu', 'kemenche', 'morin_khuur', 'choir', 'vocal',
    'soprano', 'tenor', 'lead_vocal', 'trumpet', 'trombone', 'french_horn', 'tuba', 'brass'
}


def _pitch_cont(n):
    p = n.get('p', 60)
    if isinstance(p, (int, float)):
        return float(p) + float(n.get('c', 0.0)) / 100.0
    return 60.0


def get_intent_profile(score):
    """Derives an automatic intent profile from score metadata (emotion, feel, genre, pulse, tracks)."""
    # the type of piece comes from the gate profile presets (scripts/gate_profiles.py): declared piece_type, else inferred
    import gate_profiles
    flags = gate_profiles.resolve(score).flags
    dyn = score.get('dynamics', [])
    ending_dyn = dyn[-1][1] if dyn and len(dyn[-1]) > 1 else 0.5
    is_cliffhanger = ending_dyn >= 0.85
    return dict(is_ambient='ambient' in flags, is_tense='tense' in flags, is_dance='dance' in flags, is_cliffhanger=is_cliffhanger)


def _gp(score):
    import gate_profiles
    return gate_profiles.resolve(score)


def _timeline(score, gp=None):
    """The piece's scene windows, or None when its profile declares no scene block. A timeline that cannot be read is
    None as well: a broken sheet must not stop the acoustic rows, it must make the scene rows say they did not run."""
    try:
        import scene_timeline
        return scene_timeline.load(score, gp or _gp(score))
    except Exception:
        return None


def _judged_diffs(notes, diffs, tl, waived):
    """(diffs kept for judging, count excluded): an interval whose first note sits in a window that waives this row is
    not judged by it. A climax is allowed to be the leapiest, roughest part of the piece; it is not allowed to make the
    whole-piece ceiling a lie."""
    if tl is None or not waived or not len(diffs):
        return diffs, 0
    keep = np.ones(len(diffs), dtype=bool)
    for i in range(len(diffs)):
        if tl.in_windows(tl.beat_to_s(notes[i]['t']), waived):
            keep[i] = False
    return diffs[keep], int((~keep).sum())


def build_metric_tree(ts):
    """16th-note metric weight hierarchy M(pos) for any time signature ts=[num, den].

    0 downbeat, -1 primary division (half bar, or the first compound beat of a 6/8, 9/8, 12/8 bar), -2 beat,
    -3 subdivision of the beat, -4 off-16th. Compound meters are measured in dotted-quarter beats (3 eighths),
    not per eighth: labelling every eighth in 6/8 as a beat mis-scored every compound groove.
    """
    num, den = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)
    num, den = max(1, int(num)), max(1, int(den))
    steps_per_unit = max(1, int(round(16.0 / den)))          # 16th-note steps per notated denominator unit
    total_steps = num * steps_per_unit
    weights = np.full(total_steps, -4, dtype=int)           # off-16th by default
    compound = den >= 8 and num % 3 == 0 and num > 3        # 6/8, 9/8, 12/8 (not 3/8)
    beat_steps = 3 * steps_per_unit if compound else steps_per_unit
    n_beats = total_steps // beat_steps

    for b in range(n_beats):                                 # beats: -2
        weights[b * beat_steps] = -2
    # Primary division: the second half of a 6/8 bar, the mid-bar of a 4-beat bar. 3/4 and 9/8 have no secondary
    # accent (marking beat 2 as strong over-weighted a waltz), so they only get their beats.
    if (compound and n_beats == 2) or (not compound and n_beats >= 4):
        weights[beat_steps] = -1
        if n_beats == 4:
            weights[2 * beat_steps] = -1
    if num == 5 and den == 4:                                # 5/4 as 3+2
        weights[2 * steps_per_unit] = -1
    if num == 7 and den == 4:
        weights[3 * steps_per_unit] = -1

    # subdivisions one level below the beat: -3 (eighths in simple meters, eighths in compound)
    sub = max(1, steps_per_unit if compound else steps_per_unit // 2)
    for s in range(0, total_steps, sub):
        if weights[s] == -4:
            weights[s] = -3

    weights[0] = 0                                           # downbeat is always 0
    return weights, steps_per_unit, total_steps


def melodic_contour_feel(score):
    """Law 1: Melodic Arch & Meyer's Gap-Fill Law.
    For every track with role in ('melody', 'counter', 'lead') and >= 8 pitched notes:
    1. Stepwise balance: fraction of intervals <= 3 semitones (expect >= 45%).
    2. Meyer's Gap-Fill Law: large leaps (>= 5 semitones) must not consecutively leap in the same direction.
    3. Sawtooth Zig-Zag Penalty: non-zero intervals must not alternate direction > 75% of the time.
    """
    rows = []
    intent = get_intent_profile(score)
    gp = _gp(score)          # every figure below is the piece's (defaults = the constants this function used to hold)
    min_notes = int(gp.param('feel.contour', 'min_notes'))
    step_max = float(gp.param('feel.contour', 'step_max_semitones'))
    step_min = float(gp.param('feel.contour', 'step_frac'))
    step_fail = float(gp.param('feel.contour', 'step_frac_fail'))
    leap_semis = float(gp.param('feel.contour', 'leap_semis'))
    gap_recover = float(gp.param('feel.contour', 'gap_recover_semis'))
    gap_fill_max = float(gp.param('feel.contour', 'gap_fill_max'))
    flip_max = float(gp.param('feel.contour', 'flip_frac'))
    zigzag_max = float(gp.param('feel.contour', 'zigzag_max'))
    zigzag_step = float(gp.param('feel.contour', 'zigzag_step_frac'))
    tl = _timeline(score, gp)
    waived = tl.waived('feel.contour') if tl is not None else []
    for t in score.get('tracks', []):
        if not _is_melodic(t):
            continue
        raw_notes = sorted(t.get('notes', []), key=lambda n: n['t'])
        notes = [n for n in raw_notes if isinstance(n.get('p'), (int, float))]
        if len(notes) < min_notes:
            continue

        name = t.get('name', 'melody')
        pitches = np.array([_pitch_cont(n) for n in notes])
        all_diffs = np.diff(pitches)
        if len(all_diffs) == 0:
            continue
        diffs, excluded = _judged_diffs(notes, all_diffs, tl, waived)
        if len(diffs) == 0:
            rows.append(('INFO', 'melodic_contour_feel',
                         f"Track '{name}': every interval sits in a scene window that waives this ceiling, so none was judged"))
            continue
        flagged = False
        clause = f' ({excluded} interval(s) in a waiving scene window not judged)' if excluded else ''

        # 1. Stepwise Balance
        step_frac = float(np.mean(np.abs(diffs) <= step_max))
        if step_frac < step_min and not intent['is_ambient']:
            lvl = 'FAIL' if step_frac < step_fail else 'WARN'
            rows.append((lvl, 'melodic_contour_feel',
                         f"Track '{name}' has only {step_frac:.0%} stepwise intervals (<= {step_max:g} semitones; expect >= {step_min:.0%}){clause}. "
                         "Human vocal and lead melodies are predominantly conjunct. Shape phrases as smooth arches."))
            flagged = True

        # 2. Meyer's Gap-Fill Law (a pair is judged only when both intervals are)
        large_leaps = []
        for i in range(len(all_diffs) - 1):
            if tl is not None and waived and (tl.in_windows(tl.beat_to_s(notes[i]['t']), waived)
                                              or tl.in_windows(tl.beat_to_s(notes[i + 1]['t']), waived)):
                continue
            if abs(all_diffs[i]) >= leap_semis:
                same_dir_leap = (np.sign(all_diffs[i]) == np.sign(all_diffs[i + 1])) and (abs(all_diffs[i + 1]) >= gap_recover)
                large_leaps.append(same_dir_leap)
        if len(large_leaps) >= 2:
            unrecovered_frac = float(np.mean(large_leaps))
            if unrecovered_frac > gap_fill_max:
                rows.append(('FAIL', 'melodic_contour_feel',
                             f"Track '{name}' breaches Meyer's Gap-Fill law: {unrecovered_frac:.0%} of large leaps (>= {leap_semis:g} semitones) "
                             f"continue leaping in the same direction without stepwise or reversal recovery (limit {gap_fill_max:.0%}). "
                             "Recover large leaps by changing direction with stepwise motion (1-2 semitones)."))
                flagged = True

        # 3. Sawtooth Zig-Zag Penalty
        nonzero = diffs[np.abs(diffs) > 0.05]
        if len(nonzero) >= 4:
            dirs = np.sign(nonzero)
            flips = float(np.mean(dirs[:-1] != dirs[1:]))
            if (flips > flip_max or (flips > zigzag_max and step_frac < zigzag_step)):
                rows.append(('FAIL', 'melodic_contour_feel',
                             f"Track '{name}' exhibits mechanical sawtooth zig-zagging ({flips:.0%} direction reversals). "
                             "Human melodies form sustained contour arches rather than alternating up/down on every note."))
                flagged = True
            elif flips > zigzag_max and not intent['is_ambient']:
                rows.append(('WARN', 'melodic_contour_feel',
                             f"Track '{name}' has frequent directional alternation ({flips:.0%} reversals). Shape lines with longer contour arches."))
                flagged = True

        if not flagged:
            rows.append(('PASS', 'melodic_contour_feel',
                         f"Track '{name}' maintains natural melodic arch and stepwise balance ({step_frac:.0%} conjunct){clause}"))
    return rows


def harmonic_resolution_feel(score):
    """Law 2: Harmonic Tension-to-Resolution Gravity.
    Dissonant non-chord tension notes (minor 2nd / major 7th against active harmonic accompaniment)
    must resolve by step (<= 2 semitones) on the subsequent melody note.
    """
    rows = []
    intent = get_intent_profile(score)
    gp = _gp(score)
    min_tension = int(gp.param('feel.resolution', 'min_tension_notes'))
    max_unresolved = float(gp.param('feel.resolution', 'max_unresolved_share'))
    resolve_step = float(gp.param('feel.resolution', 'resolve_step_semitones'))
    resolve_leap = float(gp.param('feel.resolution', 'resolve_leap_semitones'))
    tl = _timeline(score, gp)
    mel_tracks = [t for t in score.get('tracks', []) if _is_figure(t)]
    if not mel_tracks:
        mel_tracks = [t for t in score.get('tracks', []) if _role(t) == 'counter']
    harm_tracks = [t for t in score.get('tracks', []) if _role(t) in ('chord', 'arp', 'pad', 'bass')]

    if not mel_tracks or not harm_tracks:
        return rows

    harm_notes = [n for t in harm_tracks for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
    if not harm_notes:
        return rows

    scale_pcs = None
    k_obj = score.get('key')
    if hasattr(k_obj, 'scale') and hasattr(k_obj, 'tpc'):
        scale_pcs = k_obj.pcs()
    elif isinstance(k_obj, str):
        try:
            import theory
            parts = k_obj.split()
            scale_pcs = theory.Key(parts[0], parts[1] if len(parts) > 1 else 'major').pcs()
        except (ValueError, KeyError, IndexError):      # a key the theory module cannot parse: the scale test is skipped
            pass

    for t in mel_tracks:
        raw_notes = sorted(t.get('notes', []), key=lambda n: n['t'])
        notes = [n for n in raw_notes if isinstance(n.get('p'), (int, float))]
        if len(notes) < 2:
            continue

        name = t.get('name', 'melody')
        tension_count = 0
        unresolved_count = 0
        premature_count = 0
        relaxed_count = 0
        first_unresolved_info = None

        for i in range(len(notes) - 1):
            mn = notes[i]
            next_mn = notes[i + 1]
            if abs(mn.get('c', 0.0)) >= 15 or abs(mn.get('gl', 0.0)) >= 20:
                continue
            t_mel = mn['t']
            mel_pc = int(round(_pitch_cont(mn))) % 12

            active_h = [int(round(_pitch_cont(hn))) % 12 for hn in harm_notes if hn['t'] <= t_mel < hn['t'] + hn.get('d', 1.0) + 0.25]
            if not active_h:
                continue
            harm_pcs = set(active_h)

            is_dissonant = (mel_pc not in harm_pcs) and any(min((mel_pc - hp) % 12, (hp - mel_pc) % 12) == 1 for hp in harm_pcs)
            if is_dissonant:
                leap = abs(_pitch_cont(next_mn) - _pitch_cont(mn))
                next_pc = int(round(_pitch_cont(next_mn))) % 12
                if scale_pcs:
                    is_chromatic = (mel_pc not in scale_pcs)
                    resolved = (leap <= resolve_step) or (not is_chromatic and next_pc in scale_pcs and leap <= resolve_leap)
                else:
                    resolved = (leap <= resolve_step)

                # A scene role decides what a tension may do here: a build may FORBID the homecoming, a release may
                # ENFORCE it, a stillness RELAX it. No role, no gate block: the counters are the ones this row had.
                role = tl.role_at(tl.beat_to_s(t_mel)) if (tl is not None and tl.active) else None
                gravity = (tl.role_cfg(role).get('huron_resolution_gravity') if role else None)
                tension_count += 1
                if gravity == 'FORBID':
                    if resolved:
                        premature_count += 1
                elif not resolved:
                    if gravity == 'RELAX':
                        relaxed_count += 1
                    else:
                        unresolved_count += 1
                        if first_unresolved_info is None:
                            first_unresolved_info = (t_mel, leap)

        violations = unresolved_count + premature_count
        if tension_count >= min_tension:
            bad_ratio = violations / tension_count
            extra = (f'; {premature_count} resolved home inside a scene window that forbids it' if premature_count else '') \
                + (f'; {relaxed_count} left open inside a role that allows it' if relaxed_count else '')
            if bad_ratio > max_unresolved and not intent['is_tense']:
                beat, leap = first_unresolved_info or (0.0, 0)
                rows.append(('FAIL', 'harmonic_resolution_feel',
                             f"Track '{name}' breaks the resolution rule this piece declared: {violations} of {tension_count} "
                             f"({bad_ratio:.0%}, limit {max_unresolved:.0%}) dissonant tension notes neither resolve by step nor "
                             f"belong to a window that allows them{extra}. "
                             f"E.g. note at beat {beat:.1f} leaped by {leap:.1f} semitones. Resolve tensions by step (1-2 semitones)."))
            elif violations > 0:
                rows.append(('WARN', 'harmonic_resolution_feel',
                             f"Track '{name}' has {violations} tension note(s) against this piece's resolution rule{extra}."))
            else:
                rows.append(('PASS', 'harmonic_resolution_feel',
                             f"Track '{name}' resolves its {tension_count} tension notes the way the piece's scenes ask{extra}"))
        elif tension_count > 0 and violations > 0:
            rows.append(('WARN', 'harmonic_resolution_feel',
                         f"Track '{name}' has {violations} unresolved harmonic tension note(s) leaping away without stepwise resolution{extra}."))
        else:
            rows.append(('PASS', 'harmonic_resolution_feel',
                         f"Track '{name}' adheres to harmonic resolution gravity"))

    return rows


def groove_pocket_lock(score):
    """Law 3: Groove Pocket Autocorrelation.
    Measures 1-bar and 2-bar Pearson autocorrelation of rhythmic onsets on a 16th-note energy grid.
    Fails if pocket_corr < 0.30 over >= 4 bars.
    """
    rows = []
    gp = _gp(score)
    min_bars = int(gp.param('feel.groove', 'min_bars'))
    min_corr = float(gp.param('feel.groove', 'min_pocket_corr'))
    rhythm_tracks = [t for t in score.get('tracks', []) if _role(t) in ('drum', 'arp', 'bass')]
    if not rhythm_tracks:
        return rows

    all_notes = [n for t in rhythm_tracks for n in t.get('notes', []) if 't' in n]
    if not all_notes:
        return rows

    ts = score.get('ts', [4, 4])
    weights, steps_per_beat, total_bar_steps = build_metric_tree(ts)
    num, den = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)

    total_beats = max(n['t'] + n.get('d', 1.0) for n in all_notes)
    if total_beats < num * min_bars:
        return [('INFO', 'groove_pocket_lock',
                 f'Rhythmic duration under {min_bars} bars: not measured, not passed')]

    grid_len = int(np.ceil(total_beats * steps_per_beat)) + total_bar_steps * 2 + 16
    grid = np.zeros(grid_len, dtype=float)
    for n in all_notes:
        idx = int(round(n['t'] * steps_per_beat))
        if 0 <= idx < grid_len:
            grid[idx] += _vel(n)

    lag1 = total_bar_steps
    lag2 = total_bar_steps * 2

    corrs = []
    for lag in (lag1, lag2):
        if len(grid) > lag + 16:
            x = grid[:-lag]
            y = grid[lag:]
            if np.std(x) > 1e-4 and np.std(y) > 1e-4:
                c = float(np.corrcoef(x, y)[0, 1])
                if np.isfinite(c):
                    corrs.append(c)

    pocket_corr = max(corrs) if corrs else 0.0
    intent = get_intent_profile(score)
    if pocket_corr < min_corr and not intent['is_ambient']:
        rows.append(('FAIL', 'groove_pocket_lock',
                     f"Rhythmic autocorrelation is chaotic ({pocket_corr:.2f} < {min_corr:g}). "
                     "Off-beat hits are scattered randomly instead of locking into a repeating groove pocket. "
                     "Repeat rhythmic syncopations consistently across bar boundaries."))
    else:
        rows.append(('PASS', 'groove_pocket_lock',
                     f"Rhythmic groove pocket locked (autocorrelation {pocket_corr:.2f} >= {min_corr:g})"))

    return rows


def kinematic_effort_feel(score):
    """Law 4: Kinematic Effort & Phrase Respiration Coupling.
    Ensures that for wind, bowed, and vocal instruments, high melodic pitches do not drop in velocity
    against breath/bow physics.
    """
    rows = []
    for t in score.get('tracks', []):
        if not _is_melodic(t):
            continue
        inst = str(t.get('instrument', '')).lower()
        is_physical = (inst in ACOUSTIC_PHYSICAL_INSTS or any(k in inst for k in ('flute', 'whistle', 'string', 'violin', 'cello', 'bow', 'voice', 'choir', 'brass', 'horn', 'sax', 'reed', 'pipe')))
        if not is_physical:
            continue

        raw_notes = sorted(t.get('notes', []), key=lambda n: n['t'])
        notes = [n for n in raw_notes if isinstance(n.get('p'), (int, float))]
        if len(notes) < 8:
            continue

        name = t.get('name', 'melody')

        phrases = []
        cur_phrase = []
        for n in notes:
            if cur_phrase and (n['t'] - (cur_phrase[-1]['t'] + cur_phrase[-1].get('d', 1.0))) >= 0.20:
                phrases.append(cur_phrase)
                cur_phrase = [n]
            else:
                cur_phrase.append(n)
        if cur_phrase:
            phrases.append(cur_phrase)

        corrs = []
        for phrase in phrases:
            if len(phrase) >= 4:
                ps = np.array([_pitch_cont(n) for n in phrase])
                vs = np.array([_vel(n) for n in phrase])
                if (ps.max() - ps.min()) >= 5 and np.std(ps) > 1e-4 and np.std(vs) > 1e-4:
                    c = float(np.corrcoef(ps, vs)[0, 1])
                    if np.isfinite(c):
                        corrs.append(c)

        all_vels = np.array([_vel(n) for n in notes])
        if corrs:
            avg_corr = float(np.mean(corrs))
            if avg_corr < -0.35 and np.std(all_vels) > 0.04:
                rows.append(('WARN', 'kinematic_effort_feel',
                             f"Track '{name}': High notes drop in velocity (corr {avg_corr:.2f}), sounding limp against human breath/bow physics. "
                             "Boost velocity on melodic peaks."))
            else:
                rows.append(('PASS', 'kinematic_effort_feel',
                             f"Track '{name}' demonstrates natural kinematic effort coupling (pitch-velocity corr {avg_corr:.2f})"))
        else:
            rows.append(('PASS', 'kinematic_effort_feel',
                         f"Track '{name}' kinematic effort check passed"))

    return rows


# ================================================================================================
# Module 1: Symbolic Neuro-Cognitive Gates
# ================================================================================================

def _helix_point(pc_cont, tonic_pc):
    """A pitch (continuous pitch class) on Chew's spiral array, relative to the tonic: the line of fifths wound on a helix."""
    rel_pc = (float(pc_cont) - float(tonic_pc)) % 12.0
    k = ((7.0 * rel_pc + 5.0) % 12.0) - 5.0
    return np.array([np.sin(k * np.pi / 2.0), np.cos(k * np.pi / 2.0), k * np.sqrt(2.0 / 15.0)])


def _helix_points(pc_cont, tonic_pc):
    """`_helix_point` for an array of pitches at once: an (n, 3) array, row for row the same numbers."""
    rel_pc = (np.asarray(pc_cont, dtype=float) - float(tonic_pc)) % 12.0
    k = ((7.0 * rel_pc + 5.0) % 12.0) - 5.0
    return np.stack([np.sin(k * np.pi / 2.0), np.cos(k * np.pi / 2.0), k * np.sqrt(2.0 / 15.0)], axis=1)


def _spiral_series(score):
    """Chew's cloud per window of two bars: (centres of effect, cloud diameters, key centre, windows, window beats), or None
    for a score with no pitched notes. The one place the windowed tension is computed (the arc row and `expr.tension_ic`).

    Array maths, not a loop over notes: the note arrays are built once, a window is a mask over them, and the diameter of
    a cloud is taken over its distinct pitches (two notes of one pitch are the same point, so they cannot change the
    largest distance). The all-pairs Python loop it replaced was ~2.8 s on a 4-minute orchestral score."""
    import soul_check
    from scipy.spatial.distance import pdist
    num = _beats_per_bar(score)
    w_len = 2 * num
    all_notes = [n for t in score.get('tracks', []) if _role(t) not in ('drum', 'environment')
                 for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
    if not all_notes:
        return None
    starts = np.array([n['t'] for n in all_notes], dtype=float)
    ends = starts + np.array([n.get('d', 1.0) for n in all_notes], dtype=float)
    N = max(1, int(np.ceil(float(ends.max()) / w_len)))
    tonic_pc = soul_check._tonic_pc(score)
    CE_key = _helix_point(float(tonic_pc), tonic_pc)
    pcs = np.array([_pitch_cont(n) for n in all_notes], dtype=float)
    pts = _helix_points(pcs, tonic_pc)
    wts = np.array([float(n.get('d', 1.0)) * _vel(n) for n in all_notes], dtype=float)
    CEs, T_cds = [], []
    for w in range(N):
        t0 = w * w_len
        t1 = t0 + w_len
        idx = np.flatnonzero(np.maximum(t0, starts) < np.minimum(t1, ends))
        if idx.size:
            ce = (pts[idx] * wts[idx, None]).sum(axis=0) / (float(wts[idx].sum()) + 1e-9)
            distinct = np.unique(pcs[idx])
            cd = float(pdist(_helix_points(distinct, tonic_pc)).max()) if distinct.size > 1 else 0.0
        else:
            ce = CEs[-1] if CEs else CE_key
            cd = 0.0
        CEs.append(ce)
        T_cds.append(cd)
    return CEs, T_cds, CE_key, N, w_len


def spiral_tension_arc(score):
    """1.1 Chew's 3D Spiral Array Tonal Tension & Arc Alignment (Chew 2000, Herremans & Chew 2016).
    Evaluates tonal tension trajectory, cloud momentum, and outro resolution in 3D helical space.
    """
    rows = []
    intent = get_intent_profile(score)
    gp = _gp(score)
    static_mom = float(gp.param('feel.spiral', 'static_momentum'))
    teleport_mom = float(gp.param('feel.spiral', 'teleport_momentum'))
    outro_max = float(gp.param('feel.spiral', 'outro_strain_max'))
    outro_pct = float(gp.param('feel.spiral', 'outro_percentile'))
    concordance = float(gp.param('feel.spiral', 'concordance_min_rho'))
    tl = _timeline(score, gp)
    last_role = tl.spans[-1]['role'] if (tl is not None and tl.active) else None
    last_gravity = tl.role_cfg(last_role).get('huron_resolution_gravity') if last_role else None
    series = _spiral_series(score)
    if series is None:
        return rows
    CEs, T_cds, CE_key, N, w_len = series

    T_cms = [float(np.linalg.norm(CEs[i] - CEs[i - 1])) for i in range(1, len(CEs))]
    T_tss = [float(np.linalg.norm(ce - CE_key)) for ce in CEs]

    # Gate 1: Harmonic Stagnation vs. Teleportation
    if T_cms:
        mean_cm = float(np.mean(T_cms))
        if mean_cm < static_mom and N >= 8 and not intent['is_ambient']:
            rows.append(('WARN', 'spiral_tension_arc',
                         f"Static harmony: mean cloud momentum is {mean_cm:.3f} (< 0.05) across {N*2} bars; harmonic movement is stalled."))
        max_cm = float(np.max(T_cms))
        if max_cm > teleport_mom:
            w_jump = int(np.argmax(T_cms)) + 1
            rows.append(('FAIL', 'spiral_tension_arc',
                         f"Jarring un-led harmonic teleportation at bar {w_jump*2} (momentum {max_cm:.2f} > {teleport_mom:g}); "
                         f"prescribe common-tone voice leading."))

    # Gate 2: Cadential Home Resolution in final 2 bars
    # A scene role decides whether the end must come home: ENFORCE asks even of a tense or cliffhanger piece,
    # RELAX/FORBID excuse it, and with no role the type flags decide exactly as they did.
    outro_required = (last_gravity == 'ENFORCE') or (
        last_gravity not in ('RELAX', 'FORBID') and not intent['is_tense'] and not intent['is_cliffhanger'])
    if len(T_tss) >= 2 and outro_required:
        last_strain = T_tss[-1]
        p30 = float(np.percentile(T_tss, outro_pct))
        if last_strain > p30 and last_strain > outro_max:
            rows.append(('FAIL', 'spiral_tension_arc',
                         f"Unresolved harmonic tension at outro: final 2 bars tensile strain ({last_strain:.2f}) "
                         f"does not resolve to the bottom {outro_pct:g}th percentile ({p30:.2f}) of the piece's tension range."))
        else:
            rows.append(('PASS', 'spiral_tension_arc',
                         f"Cadential home resolution confirmed (final tensile strain {last_strain:.2f} <= {max(p30, outro_max):.2f})"))
    else:
        rows.append(('PASS', 'spiral_tension_arc', f"Harmonic tension arc tracked across {N*2} bars"))

    # Gate 3: Tension-Dynamics Concordance
    dyn = score.get('dynamics', [])
    if dyn and N >= 4 and len(dyn) >= 2:
        dyn_times = [d[0] for d in dyn]
        dyn_vals = [d[1] for d in dyn]
        w_centers = [(w + 0.5) * w_len for w in range(N)]
        interp_dyn = np.interp(w_centers, dyn_times, dyn_vals)
        comb_tension = np.array(T_tss) + np.array(T_cds)
        if np.std(interp_dyn) > 0.04 and np.std(comb_tension) > 0.04:
            r = float(np.corrcoef(interp_dyn, comb_tension)[0, 1])
            if r < concordance:
                rows.append(('WARN', 'spiral_tension_arc',
                             f"Tension-dynamics discordance (corr {r:.2f} < {concordance:g}): harmony gets more tense while "
                             f"dynamics quiet down, fighting emotional arc."))

    return rows


def bar_syncopation(score, t0=None, t1=None):
    """Witek's Bar Syncopation Index of the drum/bass/arp cell, or None when the piece has no rhythm part to score.

    The one place the index is computed: the `feel.witek` row and the chem model's motor pool both read it, so a
    change to the metric tree moves both. Weighted by the 16th-note metric hierarchy of the score's own time signature.
    `t0`/`t1` (beats) judge one scene window instead of the whole piece; the metric tree is still the score's own.
    """
    ts = score.get('ts', [4, 4])
    weights, steps_per_beat, total_bar_steps = build_metric_tree(ts)
    num, _ = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)
    rhythm_tracks = [t for t in score.get('tracks', []) if _role(t) in ('drum', 'bass', 'arp')]
    if not rhythm_tracks:
        return None
    rhythm_notes = [n for t in rhythm_tracks for n in t.get('notes', []) if 't' in n]
    if t0 is not None or t1 is not None:
        a = -1e9 if t0 is None else float(t0)
        b = 1e9 if t1 is None else float(t1)
        rhythm_notes = [n for n in rhythm_notes if a <= float(n['t']) < b]
    if not rhythm_notes:
        return None
    vels = [_vel(n) for n in rhythm_notes]
    med_v = float(np.median(vels)) if vels else 0.5
    step_hits = set()
    for n in rhythm_notes:
        if _vel(n) >= med_v * 0.85:
            step_hits.add(int(round(n['t'] * steps_per_beat)))
    total_beats = max(n['t'] + n.get('d', 1.0) for n in rhythm_notes)
    total_bars = max(1.0, total_beats / num)
    total_steps_piece = int(np.ceil(total_beats * steps_per_beat))
    syncopation = 0.0
    for s in range(total_steps_piece - 1):
        if s in step_hits:
            pos_w = s % total_bar_steps
            pos_s = (s + 1) % total_bar_steps
            w_w = weights[pos_w]
            w_s = weights[pos_s]
            if w_s > w_w and (s + 1) not in step_hits:
                syncopation += (w_s - w_w)
    return float(syncopation / total_bars)


def bsi_verdict(bsi, lo, hi, fail_hi, mode='pocket', still_max=0.0, rupture_min=0.0):
    """(level, note) for one Bar Syncopation Index against the piece's own band.

    The band is the piece's `feel.witek` parameters; this function is the one place its three zones (dead-on, pocket,
    the WARN band `hi..fail_hi`, and the collapse limit) are decided, so a caller, a scene window and a test cannot read
    the same number differently. `mode` is a scene role's `bsi_mode`.
    """
    b = float(bsi)
    head = f'{b:.2f}/bar'
    if mode == 'stillness':
        return ('PASS', f'{head} is at or below the stillness limit {still_max:g}') if b <= still_max else \
               ('WARN', f'{head} is over the stillness limit {still_max:g}: this window is busier than the role declared')
    if mode == 'rupture':
        if b < rupture_min:
            return ('WARN', f'{head} is under the rupture floor {rupture_min:g}: the break is not written as one')
        return ('PASS', f'{head}, and a rupture may exceed the collapse limit {fail_hi:g} without failing the pocket rule')
    if b < lo:
        return ('WARN', f'{head} is under the pocket {lo:g}')
    if b > fail_hi:
        return ('FAIL', f'{head} is over the collapse limit {fail_hi:g}')
    if b > hi:
        return ('WARN', f'{head} is over the pocket {hi:g} and under the collapse limit {fail_hi:g}')
    return ('PASS', f'{head} is inside the pocket [{lo:g}, {hi:g}]')


def witek_groove_curve(score):
    """1.2 Witek-Vuust Inverted-U Groove & Syncopation Pleasure Curve (Witek 2014, Vuust 2018).

    Measures the Bar Syncopation Index (BSI) across the metric tree of any time signature. The window and the collapse
    limit are the piece's (`feel.witek`); the band between them used to print a PASS while the text said the index was
    outside it, so it now warns. A scene role may state `bsi_mode`: `stillness` accepts a low index, `rupture` accepts
    one above the collapse limit, and only `pocket` (the default) enforces the inverted U.
    """
    rows = []
    intent = get_intent_profile(score)
    gp = _gp(score)
    lo = float(gp.param('feel.witek', 'bsi_lo'))
    hi = float(gp.param('feel.witek', 'bsi_hi'))
    fail_hi = float(gp.param('feel.witek', 'bsi_fail_hi'))
    still_max = float(gp.param('feel.witek', 'bsi_still_max'))
    rupture_min = float(gp.param('feel.witek', 'bsi_rupture_min'))
    bsi = bar_syncopation(score)
    if bsi is None:
        return rows

    tl = _timeline(score, gp)
    scoped = []
    if tl is not None and tl.active:
        for s in tl.spans:
            mode = tl.role_cfg(s['role']).get('bsi_mode')
            if not mode:
                continue
            b = bar_syncopation(score, tl.s_to_beat(s['start_s']), tl.s_to_beat(s['end_s']))
            if b is not None:
                scoped.append((s['role'], mode, b))
    if scoped:
        for role, mode, b in scoped:
            lvl, note = bsi_verdict(b, lo, hi, fail_hi, mode=mode, still_max=still_max, rupture_min=rupture_min)
            rows.append((lvl, 'witek_groove_curve', f"Scene role '{role}' is {mode}: BSI {note}."))
        return rows

    if intent['is_ambient']:
        rows.append(('PASS', 'witek_groove_curve', f"Ambient/free-pulse mode: BSI {bsi:.2f}/bar conforms to meditative profile"))
    else:
        lvl, note = bsi_verdict(bsi, lo, hi, fail_hi)
        rows.append((lvl, 'witek_groove_curve', f"Bar Syncopation Index {note}."
                     + (' Anchor beats 1 and 3 in bass or kick.' if lvl == 'FAIL' else '')
                     + (' Add syncopated pickups before strong beats.' if lvl == 'WARN' and bsi < lo else '')))

    return rows


def _melody_lines(score):
    """[(track name, expectation analysis)] for every melodic track with at least 8 pitched notes (scripts/expectation.py:
    prediction by partial matching, each note predicted before it is learned)."""
    import expectation
    import soul_check
    model = expectation.Expectation()
    tonic = soul_check._tonic_pc(score)
    out = []
    for t in score.get('tracks', []):
        if not _is_melodic(t):
            continue
        notes = [n for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
        if len(notes) >= 8:
            out.append((t.get('name', 'melody'), model.analyse(notes, tonic)))
    return out


def _distinct_intervals(line):
    iv = line['viewpoints']['cpint']['ic']
    return len({int(round(b - a)) for a, b in zip(line['pitches'], line['pitches'][1:])}) if len(iv) > 1 else 0


def melodic_information_entropy(score):
    """1.3 Information-theoretic melodic surprise (Pearce & Wiggins 2004, Huron 2006): the mean information content of a
    line, from the PPM model in scripts/expectation.py. Too low is a mechanical loop; too high is indistinguishable
    from a random walk. (The grounding of high-surprise notes is the `expr.surprise_grounded` row.)

    The estimator predicts each note before learning it. The first-order Markov estimate this row used before counted the
    note it was predicting, so it read 1.0-2.9 bits lower on the same melodies (24 generated melodies: 1.22-2.49 then,
    3.12-4.27 now), and the upper limit moved with it: see the `feel.entropy` parameters in gate_profiles.ROWS."""
    rows = []
    intent = get_intent_profile(score)
    gp = _gp(score)
    lo, hi = float(gp.param('feel.entropy', 'min_bits')), float(gp.param('feel.entropy', 'max_bits'))
    for name, line in _melody_lines(score):
        if _distinct_intervals(line) < 2:
            if not intent['is_ambient']:
                rows.append(('FAIL', 'melodic_information_entropy', f"Track '{name}': Melodic entropy is zero; pitch is completely static."))
            continue
        ic = line['ic'][~np.isnan(line['ic'])]
        H = float(np.mean(ic)) if len(ic) else 2.0
        if H < lo and not intent['is_ambient']:
            rows.append(('FAIL', 'melodic_information_entropy',
                         f"Track '{name}': Melodic entropy is too low ({H:.2f} bits < {lo:g}); motif is mechanically predictable."))
        elif H > hi:
            rows.append(('WARN', 'melodic_information_entropy',
                         f"Track '{name}': Melodic information content {H:.2f} bits > {hi:g}: as unpredictable as a random walk; "
                         "repeat or vary a motif so the listener can learn it."))
        else:
            rows.append(('PASS', 'melodic_information_entropy',
                         f"Track '{name}' melodic information entropy in optimal human cognition corridor ({H:.2f} bits)"))
    return rows


def expectation_checks(score):
    """expr.ic_profile and expr.surprise_grounded: what the PPM model says about each melodic line (INFO / WARN only)."""
    import expectation
    rows = []
    gp = _gp(score)
    num = _beats_per_bar(score)
    limit = float(gp.param('expr.surprise_grounded', 'max_share'))
    if gp.on('expr.tension_ic'):
        rows += tension_ic_row(score)
    for name, line in _melody_lines(score):
        ic, h = line['ic'], line['h']
        if gp.on('expr.ic_profile'):
            per_bar = expectation.by_bar(line['onsets'], ic, num)
            ok = per_bar[~np.isnan(per_bar)]
            rows.append(('INFO', 'expr.ic_profile',
                         f"Track '{name}': information content mean {np.nanmean(ic):.2f} bits, uncertainty mean {np.nanmean(h):.2f} bits; "
                         f"per bar {ok.min():.1f}-{ok.max():.1f} bits over {len(ok)} bars; rhythm {np.nanmean(line['ic_rhythm']):.2f} bits"
                         if len(ok) else f"Track '{name}': too few notes for a per-bar profile"))
        if gp.on('expr.surprise_grounded'):
            share = expectation.ungrounded_share(ic)
            rows.append(('WARN' if share > limit else 'PASS', 'expr.surprise_grounded',
                         f"Track '{name}': {share:.0%} of notes are surprising (> 4.2 bits) and not followed by a predictable one "
                         f"(<= 2.2 bits); limit {limit:.0%}" + ("; resolve high-surprise leaps stepwise or repeat the figure after them" if share > limit else '')))
    return rows


def tension_ic_row(score):
    """expr.tension_ic (INFO): how closely the harmonic tension of each two-bar window follows the surprise of the melody in it."""
    import expectation
    series = _spiral_series(score)
    lines = _melody_lines(score)
    if series is None or not lines:
        return []
    CEs, T_cds, CE_key, N, w_len = series
    T = np.array([float(np.linalg.norm(ce - CE_key)) + cd for ce, cd in zip(CEs, T_cds)])
    name, line = lines[0]
    ic = expectation.by_bar(line['onsets'], line['ic'], w_len)
    m = min(len(ic), len(T))
    ok = ~np.isnan(ic[:m])
    if ok.sum() < 4 or np.std(T[:m][ok]) < 1e-6 or np.std(ic[:m][ok]) < 1e-6:
        return [('INFO', 'expr.tension_ic', f"Track '{name}': too few windows, or no change in tension or surprise, to correlate them")]
    r = float(np.corrcoef(T[:m][ok], ic[:m][ok])[0, 1])
    return [('INFO', 'expr.tension_ic',
             f"Track '{name}': harmonic tension (Chew) and melodic information content per two bars correlate {r:+.2f} over {int(ok.sum())} windows")]


def _beats_per_bar(score):
    ts = score.get('ts', [4, 4])
    return float(ts[0]) if isinstance(ts, (list, tuple)) and len(ts) >= 2 else 4.0


def cognitive_feel_checks(score):
    """Executes the complete suite of Dynamic Cognitive & Psychoacoustic Symbolic Laws:
    1. Melodic Arch & Meyer's Gap-Fill Law (melodic_contour_feel)
    2. Harmonic Tension-to-Resolution Gravity (harmonic_resolution_feel)
    3. Groove Pocket Autocorrelation (groove_pocket_lock)
    4. Kinematic Effort & Phrase Respiration Coupling (kinematic_effort_feel)
    5. Chew's 3D Spiral Array Tonal Tension (spiral_tension_arc)
    6. Witek-Vuust Inverted-U Groove Pleasure Curve (witek_groove_curve)
    7. Melodic Information Surprise & IDyOM Entropy (melodic_information_entropy)
    """
    gp = _gp(score)
    checks = (('feel.contour', melodic_contour_feel), ('feel.resolution', harmonic_resolution_feel), ('feel.groove', groove_pocket_lock),
              ('feel.effort', kinematic_effort_feel), ('feel.spiral', spiral_tension_arc), ('feel.witek', witek_groove_curve),
              ('feel.entropy', melodic_information_entropy), (None, expectation_checks))
    rows = []
    for rid, fn in checks:
        if rid is None or gp.on(rid):       # a skipped row is listed once by the profile notes, with its reason; None gates itself
            rows += fn(score)
    return rows


def cognitive_metrics(score):
    """Computes exact numerical metrics for Stage 7 release packaging."""
    out = dict(witek_bsi=0.0, melodic_entropy_bits=2.0, spiral_strain_end=0.0)
    errors = {}                 # a metric that could not be computed keeps its default value AND is named here
    try:
        ts = score.get('ts', [4, 4])
        weights, steps_per_beat, total_bar_steps = build_metric_tree(ts)
        num, _ = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)
        rhythm_tracks = [t for t in score.get('tracks', []) if _role(t) in ('drum', 'bass', 'arp')]
        rhythm_notes = [n for t in rhythm_tracks for n in t.get('notes', []) if 't' in n]
        if rhythm_notes:
            vels = [_vel(n) for n in rhythm_notes]
            med_v = float(np.median(vels)) if vels else 0.5
            step_hits = {int(round(n['t'] * steps_per_beat)) for n in rhythm_notes if _vel(n) >= med_v * 0.85}
            total_beats = max(n['t'] + n.get('d', 1.0) for n in rhythm_notes)
            total_bars = max(1.0, total_beats / num)
            total_steps_piece = int(np.ceil(total_beats * steps_per_beat))
            sync = sum((weights[(s + 1) % total_bar_steps] - weights[s % total_bar_steps])
                       for s in range(total_steps_piece - 1)
                       if s in step_hits and weights[(s + 1) % total_bar_steps] > weights[s % total_bar_steps] and (s + 1) not in step_hits)
            out['witek_bsi'] = round(float(sync / total_bars), 2)
    except Exception as e:
        errors['witek_bsi'] = repr(e)

    try:
        for _name, line in _melody_lines(score):
            if _distinct_intervals(line) >= 2:
                out['melodic_entropy_bits'] = round(float(np.nanmean(line['ic'])), 2)
                break
    except Exception as e:
        errors['melodic_entropy_bits'] = repr(e)

    try:
        import soul_check
        tonic_pc = soul_check._tonic_pc(score)

        CE_key = _helix_point(float(tonic_pc), tonic_pc)
        num, _ = score.get('ts', [4, 4])
        all_notes = [n for t in score.get('tracks', []) if _role(t) not in ('drum', 'environment')
                     for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
        if all_notes:
            total_beats = max(n['t'] + n.get('d', 1.0) for n in all_notes)
            t0 = max(0.0, total_beats - 2 * num)
            active = [n for n in all_notes if max(t0, n['t']) < min(total_beats, n['t'] + n.get('d', 1.0))]
            if active:
                vecs = _helix_points([_pitch_cont(n) for n in active], tonic_pc)
                weights = np.array([float(n.get('d', 1.0)) * _vel(n) for n in active], dtype=float)
                ce = (vecs * weights[:, None]).sum(axis=0) / (float(weights.sum()) + 1e-9)
                out['spiral_strain_end'] = round(float(np.linalg.norm(ce - CE_key)), 2)
    except Exception as e:
        errors['spiral_strain_end'] = repr(e)

    if errors:
        out['_errors'] = errors
    return out


def note_collision(score):
    """One pitch attacked twice on one beat (+ a re-attack while the same pitch still rings). Two identical
    attacks either phase-cancel or spike; one note per pitch per beat is the only safe way to write it. Drums
    count too: a drum key is its pitch."""
    rows = []
    import gate_clock
    _sec = gate_clock.seconds_fn(score)
    for t in score.get('tracks', []):
        if str(t.get('instrument', '')).startswith(('sfx:', 'env:')):
            continue                 # a one-shot or a place has no pitch to re-attack; its event length is judged by preflight.sfx_length
        by_pitch = {}
        for n in t.get('notes', []):
            by_pitch.setdefault(n.get('p'), []).append(n)
        for p, ns in by_pitch.items():
            ns.sort(key=lambda n: n['t'])
            for a, b in zip(ns, ns[1:]):
                if abs(b['t'] - a['t']) < 1e-6:
                    rows.append(('FAIL', 'note_collision',
                                 f"Track '{t.get('name', '?')}': pitch {p} is attacked twice on beat {b['t']:g} "
                                 f"({float(_sec(b['t'])):.2f} s). Two identical attacks phase-cancel or spike: delete one."))
                elif b['t'] < a['t'] + float(a.get('d', 1.0)) - 0.25:
                    rows.append(('WARN', 'note_collision',
                                 f"Track '{t.get('name', '?')}': pitch {p} is re-attacked on beat {b['t']:g} while the "
                                 f"note from beat {a['t']:g} still sounds. Shorten the first note or move the attack."))
    if not rows:
        rows.append(('PASS', 'note_collision', 'no pitch is attacked twice on one beat or re-attacked while ringing'))
    return rows


def acoustic_checks(score):
    """Every rule in one list of (level, name, detail) rows; used by quality_gate.score_checks and the CLI."""
    import orch_rows                    # imported here: orch_rows needs gate_profiles, which needs presets
    return (note_collision(score) + chord_voicing_and_strum(score) + choked_resonance(score)
            + machine_gun_percussion(score) + percussion_flam(score) + low_interval_mud(score)
            + spatial_glue(score) + cognitive_feel_checks(score) + orch_rows.checks(score))


LOOP_ROLES = ('chord', 'pad', 'arp', 'bass', 'ostinato', 'texture')


def audit(score):
    """(info, flags). Which rules run, and their numbers, come from the piece's gate profile (gate_profiles.py); the
    defaults below are the 'melodic' profile."""
    info, flags, _ = audit_detail(score)
    return info, flags


def audit_detail(score):
    """(info, flags, per_track). `per_track` counts the flags by the part that earned them, so the gate can tell one
    part that loops for the whole piece (a fault) from eight parts with one flag each (a piece with work to do)."""
    gp = _gp(score)
    P = gp.param
    bb = score['ts'][0]
    flags, info, per_track = [], [], {}

    def flag(part, msg):
        flags.append(msg)
        per_track.setdefault(part, []).append(msg)

    for t in score['tracks']:
        if _role(t) == 'environment' or 'notes' not in t or str(t.get('instrument', '')).startswith('env:'):
            continue
        notes = t['notes']
        if len(notes) < 8:
            continue
        name, role = t['name'], _role(t)
        sigs = [s for s in bar_sigs(notes, bb)]
        filled = [s for s in sigs if s]
        n_bars = len(sigs)
        distinct = len(set(filled))
        period = best_period(sigs) if n_bars >= 8 else 0
        vel = np.array([n['v'] for n in notes])
        on_beat = np.mean([abs(n['t'] - round(n['t'])) < 1e-6 for n in notes])
        info.append(f'{name:10s} {role:7s} bars {n_bars:3d}  distinct {distinct:3d}  loop-period {period or "-"}  '
                    f'velocity sd {vel.std():.2f}  on-beat {on_beat:.0%}')
        # Which checks apply is decided per role below, not by one blanket exemption. A pad, a drone and a declared
        # ostinato were skipped before any rule ran, so the parts that repeat the most were the only ones the
        # auditor never looked at. A part that is meant to repeat is relaxed by the profile's own numbers instead.
        if role == 'fx':
            continue
        held = role == 'drone' or bool(t.get('is_drone'))      # a held drone is the part, not a performance of it
        if gp.on('pattern.drums_few') and role == 'drum' and n_bars >= 8 and distinct <= max(2, n_bars // P('pattern.drums_few', 'distinct_div')):
            flag(name, f'{name}: the drums play {distinct} different bar(s) in {n_bars}. Add fills, dropouts, a different groove in the chorus, ghost notes')
        # A part is heard as a loop when it has too few different bars to carry the piece, not when its period is
        # merely holdable in memory: the old rule needed a non-zero period AND a short one, so a part repeating one
        # bar 22 times through a 96-bar piece was invisible whenever its `best_period` was 0 or long.
        if gp.on('pattern.loop_short') and role in LOOP_ROLES and not held and n_bars >= P('pattern.loop_short', 'min_bars'):
            frac = distinct / max(n_bars, 1)
            short = bool(period) and period <= P('pattern.loop_short', 'max_period_bars')
            if frac < P('pattern.loop_short', 'min_distinct_frac') or (short and distinct <= P('pattern.loop_short', 'max_distinct')):
                if short:
                    flag(name, f'{name}: loops every {period} bar(s) for the whole piece ({distinct} different bar(s) in {n_bars}, '
                               f'{frac:.0%} of them). Change the figure between sections, add a pickup, a variation every 4th bar')
                else:
                    flag(name, f'{name}: {distinct} different bar(s) in {n_bars} ({frac:.0%} of them). '
                               f'Change the figure between sections, add a pickup, a variation every 4th bar')
        if gp.on('pattern.melody_notes') and _is_melodic(t) and len(notes) >= 12:
            durs = {round(n['d'], 2) for n in notes}
            if len(durs) < P('pattern.melody_notes', 'min_lengths'):
                flag(name, f'{name}: only {len(durs)} note length(s). Mix long and short notes, add a rest, a held note, a pickup')
            if on_beat > P('pattern.melody_notes', 'on_beat_max'):
                flag(name, f'{name}: {on_beat:.0%} of the notes sit exactly on the beat (the march grid). Use off-beat starts, ties across the bar, triplets')
            rep = np.mean([a['p'] == b['p'] for a, b in zip(notes, notes[1:])])
            if rep > P('pattern.melody_notes', 'repeat_max'):
                flag(name, f'{name}: {rep:.0%} of the notes repeat the previous pitch. Give the line contour')
        if gp.on('pattern.bass_pitches') and role == 'bass' and len(notes) >= 16:
            pcs = collections.Counter(n['p'] % 12 for n in notes)
            if len(pcs) <= P('pattern.bass_pitches', 'max_classes') and n_bars >= 12:
                flag(name, f'{name}: the bass uses {len(pcs)} pitch classes in {n_bars} bars. Add passing notes, octave jumps, a walk into chord changes')
        # judged against the track's own level: a quiet pad at 0.3 and a loud lead at 0.6 both need their own
        # contour, and an absolute 0.04 sd flagged every soft mood while letting a loud flat track pass.
        if gp.on('pattern.velocity_flat') and len(notes) >= 16 and vel.std() < P('pattern.velocity_flat', 'sd_frac') * max(float(vel.mean()), 1e-6):
            flag(name, f'{name}: velocity barely moves (sd {vel.std():.2f} on a mean of {vel.mean():.2f}, {vel.std() / max(float(vel.mean()), 1e-6):.0%} of it). '
                       f'Accent by phrase, add ghost notes, swell and fade')
    dyn = [d[1] for d in score.get('dynamics', [])]
    if gp.on('pattern.flat_dynamics') and dyn and max(dyn) - min(dyn) < P('pattern.flat_dynamics', 'min_range_frac') * max(float(np.mean(dyn)), 1e-6):
        flags.append(f'dynamics: the whole piece stays between {min(dyn):.2f} and {max(dyn):.2f}. Build and release: a quiet intro, a peak, a breath before it')
    drums = [t for t in score['tracks'] if _role(t) == 'drum']
    if drums and gp.on('pattern.four_on_floor'):
        kicks = [n for n in drums[0]['notes'] if n['p'] == 'kick']
        on = np.mean([abs(n['t'] - round(n['t'])) < 1e-6 for n in kicks]) if kicks else 0
        if kicks and on == 1.0 and len({round(n['t'] % bb, 2) for n in kicks}) >= bb:
            flags.append('drums: a kick on every beat and nothing else (four-on-the-floor / march). Drop beats out; move one to an off-beat')
    return info, flags, per_track


def _midi_vel(n):
    """A score writes velocity on 0..1 or on 1..127; the contrast row compares MIDI units."""
    v = float(n.get('v', 0.7))
    return v * 127.0 if v <= 1.0 else v


def section_stats(score):
    """[{name, velocity, density}] one row per plan section that has notes. Velocity is the section mean in MIDI
    units, density the notes per beat: the two things a listener hears change between sections."""
    bb = float(score['ts'][0]) if score.get('ts') else 4.0
    rows = []
    for s in ((score.get('plan') or {}).get('sections') or []):
        try:
            a = (float(s['start_bar']) - 1) * bb
            b = float(s['end_bar']) * bb
        except (KeyError, TypeError, ValueError):
            continue
        sel = []
        for t in score.get('tracks') or []:
            for n in t.get('notes') or []:
                if 't' in n and a <= float(n['t']) < b:
                    sel.append(n)
        if len(sel) < 4:
            continue
        beats = max(b - a, 1e-6)
        rows.append(dict(name=str(s.get('name', '?')),
                         velocity=sum(_midi_vel(n) for n in sel) / len(sel),
                         density=len(sel) / beats))
    return rows


def shape_contrast(score):
    """shape.contrast: does the piece go anywhere? A piece can pass every repetition row with eight perfectly
    varied parts that all play at one level - that is the soulless case the pattern row cannot see, because it
    counts faults per part and never compares section with section. Fails only when BOTH the level and the
    density are flat between sections: a quiet section that is busier, or a loud one that is sparser, is contrast."""
    gp = _gp(score)
    if not gp.on('shape.contrast'):
        return [('INFO', 'shape.contrast', 'the profile does not judge section contrast')]
    secs = section_stats(score)
    if len(secs) < 2:
        return [('INFO', 'shape.contrast', 'fewer than two plan sections with notes: no contrast to measure')]
    lo = min(secs, key=lambda s: s['velocity'])
    hi = max(secs, key=lambda s: s['velocity'])
    spread = hi['velocity'] - lo['velocity']
    dens = max(s['density'] for s in secs) / max(min(s['density'] for s in secs), 1e-6)
    need_v = float(gp.param('shape.contrast', 'min_vel_spread'))
    need_d = float(gp.param('shape.contrast', 'min_density_ratio'))
    detail = (f"quietest section '{lo['name']}' at {lo['velocity']:.0f} against loudest '{hi['name']}' at "
              f"{hi['velocity']:.0f} (spread {spread:.0f} of {need_v:.0f} MIDI units), density {dens:.1f}x "
              f'(needs {need_d:.1f}x)')
    if spread < need_v and dens < need_d:
        return [('FAIL', 'shape.contrast', detail + ': nothing carries the listener from one section to the next. '
                 'Build one section above the others and let another sit under them')]
    if spread < need_v or dens < need_d:
        return [('WARN', 'shape.contrast', detail + ': one of the two arcs is flat')]
    return [('PASS', 'shape.contrast', detail)]


def main():
    ap = argparse.ArgumentParser(description='Flag copy-paste patterns in a score.')
    ap.add_argument('score')
    ap.add_argument('--strict', action='store_true')
    a = ap.parse_args()
    with open(a.score, encoding='utf-8') as fh:
        score = json.load(fh)
    info, flags = audit(score)
    acoustic = acoustic_checks(score)
    print('\n'.join(info))
    print()
    print('FLAGS:' if flags else 'No repetition flags.')
    for f in flags:
        print(' -', f)
    if acoustic:
        print()
        print('ACOUSTIC / THEORY:')
        for level, name, detail in acoustic:
            print(f' - [{level}] {name}: {detail}')
    if a.strict and (flags or [r for r in acoustic if r[0] == 'FAIL']):
        sys.exit(1)


if __name__ == '__main__':
    main()
