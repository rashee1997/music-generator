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
import sys

import numpy as np


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
        if t.get('role') not in ('chord', 'harmony') and 'piano' not in inst and 'guitar' not in inst:
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
        if pct >= 0.5 and (stac >= 0.5 or (t.get('role') == 'chord' and avg < 0.35)):
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
        if t.get('role') != 'drum':
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
        if t.get('role') != 'drum':
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
        if t.get('role') not in ('chord', 'pad', 'arp'):
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
        if 'reverb' in t and float(t['reverb'] or 0) == 0.0 and t.get('role') in ('chord', 'pad', 'arp', 'melody',
                                                                                  'counter', 'harmony'):
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
    for t in score.get('tracks', []):
        if t.get('role') not in ('melody', 'counter', 'lead'):
            continue
        raw_notes = sorted(t.get('notes', []), key=lambda n: n['t'])
        notes = [n for n in raw_notes if isinstance(n.get('p'), (int, float))]
        if len(notes) < 8:
            continue

        pitches = np.array([_pitch_cont(n) for n in notes])
        diffs = np.diff(pitches)
        if len(diffs) == 0:
            continue

        name = t.get('name', 'melody')
        flagged = False

        # thresholds come from the piece's gate profile: an arpeggiated lead, a pentatonic call or a 12-tone line
        # is legitimately leap-heavy, and one global constant failed them as "unmelodic"
        mc = (getattr(_gp(score), 'rows', {}) or {}).get('melodic_contour') or {}
        step_min = float(mc.get('step_frac', 0.45))
        step_fail = float(mc.get('step_frac_fail', 0.25))
        leap_semis = float(mc.get('leap_semis', 4.8))
        flip_max = float(mc.get('flip_frac', 0.85))

        # 1. Stepwise Balance
        step_frac = float(np.mean(np.abs(diffs) <= 3.2))
        if step_frac < step_min and not intent['is_ambient']:
            lvl = 'FAIL' if step_frac < step_fail else 'WARN'
            rows.append((lvl, 'melodic_contour_feel',
                         f"Track '{name}' has only {step_frac:.0%} stepwise intervals (<= 3 semitones; expect >= {step_min:.0%}). "
                         "Human vocal and lead melodies are predominantly conjunct. Shape phrases as smooth arches."))
            flagged = True

        # 2. Meyer's Gap-Fill Law
        large_leaps = []
        for i in range(len(diffs) - 1):
            if abs(diffs[i]) >= leap_semis:
                same_dir_leap = (np.sign(diffs[i]) == np.sign(diffs[i + 1])) and (abs(diffs[i + 1]) >= 3.8)
                large_leaps.append(same_dir_leap)
        if len(large_leaps) >= 2:
            unrecovered_frac = float(np.mean(large_leaps))
            if unrecovered_frac > 0.50:
                rows.append(('FAIL', 'melodic_contour_feel',
                             f"Track '{name}' breaches Meyer's Gap-Fill law: {unrecovered_frac:.0%} of large leaps (>= 5 semitones) "
                             "continue leaping in the same direction without stepwise or reversal recovery. "
                             "Recover large leaps by changing direction with stepwise motion (1-2 semitones)."))
                flagged = True

        # 3. Sawtooth Zig-Zag Penalty
        nonzero = diffs[np.abs(diffs) > 0.05]
        if len(nonzero) >= 4:
            dirs = np.sign(nonzero)
            flips = float(np.mean(dirs[:-1] != dirs[1:]))
            if (flips > flip_max or (flips > 0.75 and step_frac < 0.30)):
                rows.append(('FAIL', 'melodic_contour_feel',
                             f"Track '{name}' exhibits mechanical sawtooth zig-zagging ({flips:.0%} direction reversals). "
                             "Human melodies form sustained contour arches rather than alternating up/down on every note."))
                flagged = True
            elif flips > 0.75 and not intent['is_ambient']:
                rows.append(('WARN', 'melodic_contour_feel',
                             f"Track '{name}' has frequent directional alternation ({flips:.0%} reversals). Shape lines with longer contour arches."))
                flagged = True

        if not flagged:
            rows.append(('PASS', 'melodic_contour_feel',
                         f"Track '{name}' maintains natural melodic arch and stepwise balance ({step_frac:.0%} conjunct)"))
    return rows


def harmonic_resolution_feel(score):
    """Law 2: Harmonic Tension-to-Resolution Gravity.
    Dissonant non-chord tension notes (minor 2nd / major 7th against active harmonic accompaniment)
    must resolve by step (<= 2 semitones) on the subsequent melody note.
    """
    rows = []
    intent = get_intent_profile(score)
    mel_tracks = [t for t in score.get('tracks', []) if t.get('role') in ('melody', 'lead')]
    if not mel_tracks:
        mel_tracks = [t for t in score.get('tracks', []) if t.get('role') == 'counter']
    harm_tracks = [t for t in score.get('tracks', []) if t.get('role') in ('chord', 'arp', 'pad', 'bass')]

    if not mel_tracks or not harm_tracks:
        return rows

    harm_notes = [n for t in harm_tracks for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
    if not harm_notes:
        return rows

    scale_pcs = None
    k_obj = score.get('key')
    if hasattr(k_obj, 'scale') and hasattr(k_obj, 'tpc'):
        scale_pcs = {(k_obj.tpc + deg) % 12 for deg in k_obj.scale}
    elif isinstance(k_obj, str):
        try:
            import theory
            parts = k_obj.split()
            k = theory.Key(parts[0], parts[1] if len(parts) > 1 else 'major')
            scale_pcs = {(k.tpc + deg) % 12 for deg in k.scale}
        except Exception:
            pass

    for t in mel_tracks:
        raw_notes = sorted(t.get('notes', []), key=lambda n: n['t'])
        notes = [n for n in raw_notes if isinstance(n.get('p'), (int, float))]
        if len(notes) < 2:
            continue

        name = t.get('name', 'melody')
        tension_count = 0
        unresolved_count = 0
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
                    resolved = (leap <= 2.2) or (not is_chromatic and next_pc in scale_pcs and leap <= 4.2)
                else:
                    resolved = (leap <= 2.2)

                tension_count += 1
                if not resolved:
                    unresolved_count += 1
                    if first_unresolved_info is None:
                        first_unresolved_info = (t_mel, leap)

        if tension_count >= 3:
            unresolved_ratio = unresolved_count / tension_count
            if unresolved_ratio > 0.40 and not intent['is_tense']:
                beat, leap = first_unresolved_info or (0.0, 0)
                rows.append(('FAIL', 'harmonic_resolution_feel',
                             f"Track '{name}' has unresolved harmonic tension: {unresolved_count} of {tension_count} "
                             f"({unresolved_ratio:.0%}) dissonant tension notes leaped away without stepwise resolution. "
                             f"E.g. note at beat {beat:.1f} leaped by {leap:.1f} semitones. Resolve tensions by step (1-2 semitones)."))
            elif unresolved_count > 0:
                rows.append(('WARN', 'harmonic_resolution_feel',
                             f"Track '{name}' has {unresolved_count} unresolved harmonic tension note(s) leaping away instead of resolving by step."))
            else:
                rows.append(('PASS', 'harmonic_resolution_feel',
                             f"Track '{name}' resolves all {tension_count} harmonic tension notes stepwise into consonant chord tones"))
        elif tension_count > 0 and unresolved_count > 0:
            rows.append(('WARN', 'harmonic_resolution_feel',
                         f"Track '{name}' has {unresolved_count} unresolved harmonic tension note(s) leaping away without stepwise resolution."))
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
    rhythm_tracks = [t for t in score.get('tracks', []) if t.get('role') in ('drum', 'arp', 'bass')]
    if not rhythm_tracks:
        return rows

    all_notes = [n for t in rhythm_tracks for n in t.get('notes', []) if 't' in n]
    if not all_notes:
        return rows

    ts = score.get('ts', [4, 4])
    weights, steps_per_beat, total_bar_steps = build_metric_tree(ts)
    num, den = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)

    total_beats = max(n['t'] + n.get('d', 1.0) for n in all_notes)
    if total_beats < num * 4:
        return [('PASS', 'groove_pocket_lock', 'Rhythmic duration under 4 bars; groove pocket check skipped')]

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
    if pocket_corr < 0.30 and not intent['is_ambient']:
        rows.append(('FAIL', 'groove_pocket_lock',
                     f"Rhythmic autocorrelation is chaotic ({pocket_corr:.2f} < 0.30). "
                     "Off-beat hits are scattered randomly instead of locking into a repeating groove pocket. "
                     "Repeat rhythmic syncopations consistently across bar boundaries."))
    else:
        rows.append(('PASS', 'groove_pocket_lock',
                     f"Rhythmic groove pocket locked (autocorrelation {pocket_corr:.2f} >= 0.30)"))

    return rows


def kinematic_effort_feel(score):
    """Law 4: Kinematic Effort & Phrase Respiration Coupling.
    Ensures that for wind, bowed, and vocal instruments, high melodic pitches do not drop in velocity
    against breath/bow physics.
    """
    rows = []
    for t in score.get('tracks', []):
        if t.get('role') not in ('melody', 'counter', 'lead'):
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

def spiral_tension_arc(score):
    """1.1 Chew's 3D Spiral Array Tonal Tension & Arc Alignment (Chew 2000, Herremans & Chew 2016).
    Evaluates tonal tension trajectory, cloud momentum, and outro resolution in 3D helical space.
    """
    rows = []
    intent = get_intent_profile(score)
    ts = score.get('ts', [4, 4])
    num, _ = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)
    w_len = 2 * num

    all_notes = [n for t in score.get('tracks', []) if t.get('role') not in ('drum', 'environment')
                 for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
    if not all_notes:
        return rows

    total_beats = max(n['t'] + n.get('d', 1.0) for n in all_notes)
    N = max(1, int(np.ceil(total_beats / w_len)))

    # Resolve tonic
    import soul_check
    tonic_pc = soul_check._tonic_pc(score)

    def P_helical(pc_cont):
        rel_pc = (float(pc_cont) - float(tonic_pc)) % 12.0
        k = ((7.0 * rel_pc + 5.0) % 12.0) - 5.0
        return np.array([np.sin(k * np.pi / 2.0), np.cos(k * np.pi / 2.0), k * np.sqrt(2.0 / 15.0)])

    CE_key = P_helical(float(tonic_pc))

    CEs = []
    T_cds = []

    for w in range(N):
        t0 = w * w_len
        t1 = t0 + w_len
        active = [n for n in all_notes if max(t0, n['t']) < min(t1, n['t'] + n.get('d', 1.0))]
        if active:
            vecs = [P_helical(_pitch_cont(n)) for n in active]
            weights = [float(n.get('d', 1.0)) * _vel(n) for n in active]
            tot_w = sum(weights) + 1e-9
            ce = sum(v * w for v, w in zip(vecs, weights)) / tot_w
            dists = [np.linalg.norm(a - b) for a in vecs for b in vecs]
            cd = max(dists) if dists else 0.0
        else:
            ce = CEs[-1] if CEs else CE_key
            cd = 0.0
        CEs.append(ce)
        T_cds.append(cd)

    T_cms = [float(np.linalg.norm(CEs[i] - CEs[i - 1])) for i in range(1, len(CEs))]
    T_tss = [float(np.linalg.norm(ce - CE_key)) for ce in CEs]

    # Gate 1: Harmonic Stagnation vs. Teleportation
    if T_cms:
        mean_cm = float(np.mean(T_cms))
        if mean_cm < 0.05 and N >= 8 and not intent['is_ambient']:
            rows.append(('WARN', 'spiral_tension_arc',
                         f"Static harmony: mean cloud momentum is {mean_cm:.3f} (< 0.05) across {N*2} bars; harmonic movement is stalled."))
        max_cm = float(np.max(T_cms))
        if max_cm > 1.45:
            w_jump = int(np.argmax(T_cms)) + 1
            rows.append(('FAIL', 'spiral_tension_arc',
                         f"Jarring un-led harmonic teleportation at bar {w_jump*2} (momentum {max_cm:.2f} > 1.45); prescribe common-tone voice leading."))

    # Gate 2: Cadential Home Resolution in final 2 bars
    if len(T_tss) >= 2 and not intent['is_tense'] and not intent['is_cliffhanger']:
        last_strain = T_tss[-1]
        p30 = float(np.percentile(T_tss, 30))
        if last_strain > p30 and last_strain > 0.50:
            rows.append(('FAIL', 'spiral_tension_arc',
                         f"Unresolved harmonic tension at outro: final 2 bars tensile strain ({last_strain:.2f}) "
                         f"does not resolve to the bottom 30th percentile ({p30:.2f}) of the piece's tension range."))
        else:
            rows.append(('PASS', 'spiral_tension_arc',
                         f"Cadential home resolution confirmed (final tensile strain {last_strain:.2f} <= {max(p30, 0.50):.2f})"))
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
            if r < -0.35:
                rows.append(('WARN', 'spiral_tension_arc',
                             f"Tension-dynamics discordance (corr {r:.2f} < -0.35): harmony gets more tense while dynamics quiet down, fighting emotional arc."))

    return rows


def witek_groove_curve(score):
    """1.2 Witek-Vuust Inverted-U Groove & Syncopation Pleasure Curve (Witek 2014, Vuust 2018).
    Measures Bar Syncopation Index (BSI) across the metric tree of any time signature.
    """
    rows = []
    intent = get_intent_profile(score)
    ts = score.get('ts', [4, 4])
    weights, steps_per_beat, total_bar_steps = build_metric_tree(ts)
    num, _ = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)

    rhythm_tracks = [t for t in score.get('tracks', []) if t.get('role') in ('drum', 'bass', 'arp')]
    if not rhythm_tracks:
        return rows

    rhythm_notes = [n for t in rhythm_tracks for n in t.get('notes', []) if 't' in n]
    if not rhythm_notes:
        return rows

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

    bsi = float(syncopation / total_bars)

    if intent['is_ambient']:
        rows.append(('PASS', 'witek_groove_curve', f"Ambient/free-pulse mode: BSI {bsi:.2f}/bar conforms to meditative profile"))
    elif bsi < 0.4:
        rows.append(('WARN', 'witek_groove_curve',
                     f"Dead-on-grid rhythmic predictability: Bar Syncopation Index {bsi:.2f} < 0.4/bar. "
                     "Add syncopated pickups before strong beats to trigger human groove prediction."))
    elif bsi > 5.5:
        rows.append(('FAIL', 'witek_groove_curve',
                     f"Metric collapse: excessive syncopation (BSI {bsi:.2f} > 5.5/bar) destroys internal beat prediction model. "
                     "Anchor beats 1 and 3 in bass or kick."))
    else:
        rows.append(('PASS', 'witek_groove_curve', f"Optimal human groove zone (BSI {bsi:.2f}/bar in [0.4, 4.8])"))

    return rows


def melodic_information_entropy(score):
    """1.3 Information-Theoretic Melodic Surprise & IDyOM Entropy (Pearce 2005, Huron 2006).
    Evaluates Shannon conditional entropy H and ungrounded high-surprise leaps across melodic lines.
    """
    rows = []
    intent = get_intent_profile(score)
    mel_tracks = [t for t in score.get('tracks', []) if t.get('role') in ('melody', 'counter', 'lead')]
    if not mel_tracks:
        return rows

    for t in mel_tracks:
        notes = [n for n in sorted(t.get('notes', []), key=lambda n: n['t']) if isinstance(n.get('p'), (int, float))]
        if len(notes) < 8:
            continue
        name = t.get('name', 'melody')
        pitches = np.array([_pitch_cont(n) for n in notes])
        dp = np.clip(np.round(np.diff(pitches)).astype(int), -12, 12)
        obs = sorted(set(dp))
        K = len(obs)
        if K < 2:
            if not intent['is_ambient']:
                rows.append(('FAIL', 'melodic_information_entropy', f"Track '{name}': Melodic entropy is zero; pitch is completely static."))
            continue

        idx = {val: i for i, val in enumerate(obs)}
        counts = np.full((K, K), 0.2)
        for i in range(len(dp) - 1):
            counts[idx[dp[i]], idx[dp[i + 1]]] += 1.0

        P = counts / counts.sum(axis=1, keepdims=True)
        ics = [-np.log2(P[idx[dp[i]], idx[dp[i + 1]]]) for i in range(len(dp) - 1)]
        H = float(np.mean(ics)) if ics else 2.0

        ungrounded = 0
        for i in range(len(ics)):
            if ics[i] > 4.2:
                resolved = (i + 1 < len(ics) and ics[i + 1] <= 2.2)
                if not resolved:
                    ungrounded += 1
        ungrounded_frac = ungrounded / max(1, len(ics))

        if H < 1.15 and not intent['is_ambient']:
            rows.append(('FAIL', 'melodic_information_entropy',
                         f"Track '{name}': Melodic entropy is too low ({H:.2f} bits < 1.15); motif is mechanically predictable."))
        elif H > 3.35 or ungrounded_frac > 0.30:
            rows.append(('FAIL', 'melodic_information_entropy',
                         f"Track '{name}': Melodic surprise is ungrounded (entropy {H:.2f} bits, {ungrounded_frac:.0%} ungrounded leaps > 4.2 bits); "
                         "high-surprise leaps must be followed by predictable stepwise resolution."))
        else:
            rows.append(('PASS', 'melodic_information_entropy',
                         f"Track '{name}' melodic information entropy in optimal human cognition corridor ({H:.2f} bits)"))

    return rows


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
              ('feel.entropy', melodic_information_entropy))
    rows = []
    for rid, fn in checks:
        if gp.on(rid):                      # a skipped row is listed once by the profile notes, with its reason
            rows += fn(score)
    return rows


def cognitive_metrics(score):
    """Computes exact numerical metrics for Stage 7 release packaging."""
    out = dict(witek_bsi=0.0, melodic_entropy_bits=2.0, spiral_strain_end=0.0)
    try:
        ts = score.get('ts', [4, 4])
        weights, steps_per_beat, total_bar_steps = build_metric_tree(ts)
        num, _ = ts if (isinstance(ts, (list, tuple)) and len(ts) >= 2) else (4, 4)
        rhythm_tracks = [t for t in score.get('tracks', []) if t.get('role') in ('drum', 'bass', 'arp')]
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
    except Exception:
        pass

    try:
        mel_tracks = [t for t in score.get('tracks', []) if t.get('role') in ('melody', 'lead', 'counter')]
        for t in mel_tracks:
            notes = [n for n in sorted(t.get('notes', []), key=lambda n: n['t']) if isinstance(n.get('p'), (int, float))]
            if len(notes) >= 8:
                dp = np.clip(np.round(np.diff([_pitch_cont(n) for n in notes])).astype(int), -12, 12)
                obs = sorted(set(dp))
                K = len(obs)
                if K >= 2:
                    idx = {val: i for i, val in enumerate(obs)}
                    counts = np.full((K, K), 0.2)
                    for i in range(len(dp) - 1):
                        counts[idx[dp[i]], idx[dp[i + 1]]] += 1.0
                    P = counts / counts.sum(axis=1, keepdims=True)
                    ics = [-np.log2(P[idx[dp[i]], idx[dp[i + 1]]]) for i in range(len(dp) - 1)]
                    out['melodic_entropy_bits'] = round(float(np.mean(ics)), 2)
                    break
    except Exception:
        pass

    try:
        import soul_check
        tonic_pc = soul_check._tonic_pc(score)

        def P_helical_c(pc_cont):
            rel_pc = (float(pc_cont) - float(tonic_pc)) % 12.0
            k = ((7.0 * rel_pc + 5.0) % 12.0) - 5.0
            return np.array([np.sin(k * np.pi / 2.0), np.cos(k * np.pi / 2.0), k * np.sqrt(2.0 / 15.0)])

        CE_key = P_helical_c(float(tonic_pc))
        num, _ = score.get('ts', [4, 4])
        all_notes = [n for t in score.get('tracks', []) if t.get('role') not in ('drum', 'environment')
                     for n in t.get('notes', []) if isinstance(n.get('p'), (int, float))]
        if all_notes:
            total_beats = max(n['t'] + n.get('d', 1.0) for n in all_notes)
            t0 = max(0.0, total_beats - 2 * num)
            active = [n for n in all_notes if max(t0, n['t']) < min(total_beats, n['t'] + n.get('d', 1.0))]
            if active:
                vecs = [P_helical_c(_pitch_cont(n)) for n in active]
                weights = [float(n.get('d', 1.0)) * _vel(n) for n in active]
                ce = sum(v * w for v, w in zip(vecs, weights)) / (sum(weights) + 1e-9)
                out['spiral_strain_end'] = round(float(np.linalg.norm(ce - CE_key)), 2)
    except Exception:
        pass

    return out


def note_collision(score):
    """One pitch attacked twice on one beat (+ a re-attack while the same pitch still rings). Two identical
    attacks either phase-cancel or spike; one note per pitch per beat is the only safe way to write it. Drums
    count too: a drum key is its pitch."""
    rows = []
    spb = 60.0 / float(score.get('bpm', 120) or 120)
    for t in score.get('tracks', []):
        by_pitch = {}
        for n in t.get('notes', []):
            by_pitch.setdefault(n.get('p'), []).append(n)
        for p, ns in by_pitch.items():
            ns.sort(key=lambda n: n['t'])
            for a, b in zip(ns, ns[1:]):
                if abs(b['t'] - a['t']) < 1e-6:
                    rows.append(('FAIL', 'note_collision',
                                 f"Track '{t.get('name', '?')}': pitch {p} is attacked twice on beat {b['t']:g} "
                                 f"({b['t'] * spb:.2f} s). Two identical attacks phase-cancel or spike: delete one."))
                elif b['t'] < a['t'] + float(a.get('d', 1.0)) - 0.25:
                    rows.append(('WARN', 'note_collision',
                                 f"Track '{t.get('name', '?')}': pitch {p} is re-attacked on beat {b['t']:g} while the "
                                 f"note from beat {a['t']:g} still sounds. Shorten the first note or move the attack."))
    if not rows:
        rows.append(('PASS', 'note_collision', 'no pitch is attacked twice on one beat or re-attacked while ringing'))
    return rows


def acoustic_checks(score):
    """Every rule in one list of (level, name, detail) rows; used by quality_gate.score_checks and the CLI."""
    return (note_collision(score) + chord_voicing_and_strum(score) + choked_resonance(score)
            + machine_gun_percussion(score) + percussion_flam(score) + low_interval_mud(score)
            + spatial_glue(score) + cognitive_feel_checks(score))


def audit(score):
    """(info, flags). Which rules run, and their numbers, come from the piece's gate profile (gate_profiles.py); the
    defaults below are the 'melodic' profile."""
    gp = _gp(score)
    P = gp.param
    bb = score['ts'][0]
    flags, info = [], []
    for t in score['tracks']:
        if t.get('role') == 'environment' or 'notes' not in t or str(t.get('instrument', '')).startswith('env:'):
            continue
        notes = t['notes']
        if len(notes) < 8:
            continue
        name, role = t['name'], t.get('role', '')
        sigs = [s for s in bar_sigs(notes, bb)]
        filled = [s for s in sigs if s]
        n_bars = len(sigs)
        distinct = len(set(filled))
        period = best_period(sigs) if n_bars >= 8 else 0
        vel = np.array([n['v'] for n in notes])
        on_beat = np.mean([abs(n['t'] - round(n['t'])) < 1e-6 for n in notes])
        info.append(f'{name:10s} {role:7s} bars {n_bars:3d}  distinct {distinct:3d}  loop-period {period or "-"}  '
                    f'velocity sd {vel.std():.2f}  on-beat {on_beat:.0%}')
        if t.get('allow_ostinato') or t.get('is_drone') or t.get('is_ostinato') or t.get('role') in ('drone', 'pad'):
            continue
        if gp.on('pattern.drums_few') and role == 'drum' and n_bars >= 8 and distinct <= max(2, n_bars // P('pattern.drums_few', 'distinct_div')):
            flags.append(f'{name}: the drums play {distinct} different bar(s) in {n_bars}. Add fills, dropouts, a different groove in the chorus, ghost notes')
        if (gp.on('pattern.loop_short') and role in ('chord', 'pad', 'arp', 'bass') and n_bars >= P('pattern.loop_short', 'min_bars')
                and period and period <= P('pattern.loop_short', 'max_period_bars') and distinct <= P('pattern.loop_short', 'max_distinct')):
            flags.append(f'{name}: loops every {period} bar(s) for the whole piece. Change the figure between sections, add a pickup, a variation every 4th bar')
        if gp.on('pattern.melody_notes') and role in ('melody', 'counter') and len(notes) >= 12:
            durs = {round(n['d'], 2) for n in notes}
            if len(durs) < P('pattern.melody_notes', 'min_lengths'):
                flags.append(f'{name}: only {len(durs)} note length(s). Mix long and short notes, add a rest, a held note, a pickup')
            if on_beat > P('pattern.melody_notes', 'on_beat_max'):
                flags.append(f'{name}: {on_beat:.0%} of the notes sit exactly on the beat (the march grid). Use off-beat starts, ties across the bar, triplets')
            rep = np.mean([a['p'] == b['p'] for a, b in zip(notes, notes[1:])])
            if rep > P('pattern.melody_notes', 'repeat_max'):
                flags.append(f'{name}: {rep:.0%} of the notes repeat the previous pitch. Give the line contour')
        if gp.on('pattern.bass_pitches') and role == 'bass' and len(notes) >= 16:
            pcs = collections.Counter(n['p'] % 12 for n in notes)
            if len(pcs) <= P('pattern.bass_pitches', 'max_classes') and n_bars >= 12:
                flags.append(f'{name}: the bass uses {len(pcs)} pitch classes in {n_bars} bars. Add passing notes, octave jumps, a walk into chord changes')
        # judged against the track's own level: a quiet pad at 0.3 and a loud lead at 0.6 both need their own
        # contour, and an absolute 0.04 sd flagged every soft mood while letting a loud flat track pass.
        if gp.on('pattern.velocity_flat') and len(notes) >= 16 and vel.std() < P('pattern.velocity_flat', 'sd_frac') * max(float(vel.mean()), 1e-6):
            flags.append(f'{name}: velocity barely moves (sd {vel.std():.2f} on a mean of {vel.mean():.2f}). Accent by phrase, add ghost notes, swell and fade')
    dyn = [d[1] for d in score.get('dynamics', [])]
    if gp.on('pattern.flat_dynamics') and dyn and max(dyn) - min(dyn) < P('pattern.flat_dynamics', 'min_range_frac') * max(float(np.mean(dyn)), 1e-6):
        flags.append(f'dynamics: the whole piece stays between {min(dyn):.2f} and {max(dyn):.2f}. Build and release: a quiet intro, a peak, a breath before it')
    drums = [t for t in score['tracks'] if t.get('role') == 'drum']
    if drums and gp.on('pattern.four_on_floor'):
        kicks = [n for n in drums[0]['notes'] if n['p'] == 'kick']
        on = np.mean([abs(n['t'] - round(n['t'])) < 1e-6 for n in kicks]) if kicks else 0
        if kicks and on == 1.0 and len({round(n['t'] % bb, 2) for n in kicks}) >= bb:
            flags.append('drums: a kick on every beat and nothing else (four-on-the-floor / march). Drop beats out; move one to an off-beat')
    return info, flags


def main():
    ap = argparse.ArgumentParser(description='Flag copy-paste patterns in a score.')
    ap.add_argument('score')
    ap.add_argument('--strict', action='store_true')
    a = ap.parse_args()
    score = json.load(open(a.score, encoding='utf-8'))
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
