# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Musical form: phrases, motor streams, metric weight, tonal charge, key parsing.

These helpers read a score or a line and answer a question the stages ask; they hold no values of their own.
"""
import re

import numpy as np

import roles as rolelib

from .config import CHORD_ROLES, CIRCLE, DRUM_LIMB, FIG, MOODS, NOTE_PC


def _vel127(v):
    v = float(v)
    return v * 127.0 if v <= 1.0 else v


def _limb_of(pitch):
    """The motor stream a drum pitch belongs to (a kit is several limbs, not one hand)."""
    return DRUM_LIMB.get(int(pitch), f'other{int(pitch)}')


def _circle_distance(pc, root_pc):
    """Tonal charge of a pitch class against a root: 0 at the root, 1 at the tritone (circle-of-fifths distance)."""
    d = abs(CIRCLE[int(pc) % 12] - CIRCLE[int(root_pc) % 12]) % 12
    return min(d, 12 - d) / 6.0


def key_tonic(key):
    """'D minor' / 'Bb' / 'F#' / 2 -> tonic pitch class (None when the score names no key)."""
    if key is None:
        return None
    if isinstance(key, (int, float, np.integer, np.floating)):
        return int(key) % 12
    m = re.match(r'\s*([A-Ga-g])([#b]?)', str(key))
    if not m:
        return None
    pc = NOTE_PC[m.group(1).upper()] + {'#': 1, 'b': -1}.get(m.group(2), 0)
    return pc % 12


def _figure_track(tracks):
    """The track that carries the line (melody | lead | vocal), which is the one whose phrases the piece breathes on."""
    for tr in tracks or []:
        try:
            role = rolelib.canonical(tr.get('role'))
        except Exception:
            continue
        if role in FIG and tr.get('notes'):
            return tr
    return None


def score_phrase_spans(tracks):
    """Real phrase boundaries of the figure, as [(start_beat, end_beat), ...]; None when the piece has no figure.

    The tempo arches and the velocity arches must be the same phrases. A fixed `phrase_beats=16` rubato over a line
    whose phrases are 5 or 21 beats long is uncoordinated by construction: it swells where the melody does not.
    """
    tr = _figure_track(tracks)
    if not tr:
        return None
    ns = sorted([dict(n, d=float(n.get('d', 1.0))) for n in tr['notes']], key=lambda n: (float(n['t']), n.get('p', 0)))
    ids = _phrase_ids(ns)
    if not ids:
        return None
    starts, ends = [], []
    for k in sorted(set(ids)):
        idx = [i for i, q in enumerate(ids) if q == k]
        starts.append(float(ns[idx[0]]['t']))
        ends.append(float(ns[idx[-1]]['t']) + max(float(ns[idx[-1]]['d']), 0.25))
    spans = []
    for i, (s0, _e) in enumerate(zip(starts, ends)):
        s1 = starts[i + 1] if i + 1 < len(starts) else ends[i]
        if s1 > s0:
            spans.append((s0, s1))
    return spans or None


def score_chord_roots(tracks):
    """(beats, pitch classes) of the sounding harmony: the lowest note of every chord/pad/bass cluster.

    A melody note's tonal charge is measured against the root actually sounding under it. Without this the humanizer
    can only hear its own track, and a chromatic passing tone and a chord tone are indistinguishable.
    """
    notes = []
    for tr in tracks or []:
        try:
            role = rolelib.canonical(tr.get('role'))
        except Exception:
            continue
        if role not in CHORD_ROLES:
            continue
        for n in tr.get('notes', []) or []:
            try:
                notes.append((float(n['t']), float(n['p'])))
            except (KeyError, TypeError, ValueError):
                continue
    if not notes:
        return None
    notes.sort()
    beats, roots = [], []
    for t, pitch in notes:
        if beats and abs(t - beats[-1]) <= 1e-6:
            roots[-1] = min(roots[-1], pitch)
        else:
            beats.append(t)
            roots.append(pitch)
    return np.array(beats, float), np.array([int(round(r)) % 12 for r in roots], int)


def _beat_accent(t, ts=(4, 4), upbeat=False):
    """Metric weight 0..1 for a position in beats (strong on bar start, medium on mid-bar, weak off-beat)."""
    bar = ts[0]
    pos = t % bar
    if upbeat:
        if abs(pos * 2 - round(pos * 2)) < 0.04 and abs(pos - round(pos)) > 0.04:
            return 1.0   # primary upbeat (e.g. 0.5, 1.5, 2.5, 3.5)
        if abs(pos * 4 - round(pos * 4)) < 0.04 and abs(pos * 2 - round(pos * 2)) > 0.04:
            return 0.85  # 16th syncopation (e.g. 0.25, 0.75, 1.25)
        if abs(pos) < 0.02:
            return 0.75  # downbeat foundation
        return 0.4
    if abs(pos) < 0.02:
        return 1.0
    if ts[0] == 4 and abs(pos - 2) < 0.02:
        return 0.65
    if abs(pos - round(pos)) < 0.02:
        return 0.4
    if abs(pos * 2 - round(pos * 2)) < 0.04:
        return 0.15
    return 0.0


def _phrase_ids(notes_sorted, gap_beats=1.0, max_beats=16.0):
    """Split a line into phrases at rests >= gap_beats or after max_beats."""
    ids, cur, start, last_end = [], 0, None, None
    for n in notes_sorted:
        if start is None:
            start = n['t']
        elif (last_end is not None and n['t'] - last_end >= gap_beats) or n['t'] - start >= max_beats:
            cur += 1
            start = n['t']
        ids.append(cur)
        last_end = max(last_end or 0, n['t'] + n.get('d', 0.0))
    return ids


def _motor_streams(ns, is_drum):
    """The streams whose successive onsets one motor program controls: one limb on a kit, one key/finger on a keyboard.

    The lag-1 correction belongs to that stream. Applied across the flat sorted list it correlated a hi-hat's error
    with a kick struck at the same instant (two limbs), and note 2 of a chord with note 1 of the same chord (two
    fingers, one keystroke), distorting the strum offset.
    """
    streams = {}
    for i, nt in enumerate(ns):
        k = _limb_of(nt['p']) if is_drum else int(nt['p'])
        streams.setdefault(k, []).append(i)
    return [streams[k] for k in sorted(streams, key=str)]


def _mood_profile(c):
    """Apply the GERM expression profile named in `c['mood']` (already merged from the score/preset), if any."""
    name = c.get('mood')
    if not name:
        return
    prof = MOODS.get(str(name).lower())
    if prof is None:
        raise ValueError(f"mood: unknown expression {name!r}; known: {', '.join(sorted(MOODS))}")
    c['vel_bias'] = c.get('vel_bias', 0.0) + float(prof.get('vel', 0.0))
    c['gate_bias'] = c.get('gate_bias', 0.0) + float(prof.get('gate', 0.0))
    c['accent'] = float(c.get('accent', 1.0)) * float(prof.get('accent', 1.0))
    c['duration_contrast'] = float(c.get('duration_contrast', 0.0)) * float(prof.get('duration_contrast', 1.0))
    c['strum_ms'] = float(c.get('strum_ms', 0.0)) * float(prof.get('strum', 1.0))
