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

"""MIDI clean-up: turn a voice's found notes into a playable part before anything is synthesised from it.

A voice that plays one note at a time cannot have two notes sounding at once, and an instrument cannot play outside its
range. Notes the finder produced against those rules are leakage from a neighbour or an octave ghost: the weaker one is
trimmed or dropped. What was changed is counted, so the gate can say how much of a voice had to be repaired."""


def clean_voice(notes, polyphony, rng_range, cfg):
    """(kept notes sorted by start, stats). `rng_range` = (lo, hi) midi or None for an undeclared voice."""
    c = cfg['midi']
    stats = {'found': len(notes), 'short': 0, 'out_of_range': 0, 'dropped_poly': 0, 'trimmed': 0}
    out = []
    for n in sorted(notes, key=lambda n: (n['start_s'], n['midi'])):
        if n['end_s'] - n['start_s'] < c['min_note_s']:
            stats['short'] += 1
            continue
        if rng_range and rng_range[0] is not None and not rng_range[0] - c['range_pad_semitones'] <= n['midi'] <= rng_range[1] + c['range_pad_semitones']:
            stats['out_of_range'] += 1
            continue
        out.append(dict(n))
    poly = max(int(polyphony or c['default_polyphony']), 1)
    kept, active = [], []
    for n in out:
        active = [a for a in active if a['end_s'] > n['start_s']]
        if len(active) >= poly:
            weakest = min(active + [n], key=lambda a: a['strength'])
            if weakest is n:
                stats['dropped_poly'] += 1
                continue
            weakest['end_s'] = n['start_s']                      # the stronger newcomer cuts the weaker held note short
            active.remove(weakest)
            stats['trimmed'] += 1
            if weakest['end_s'] - weakest['start_s'] < c['min_note_s']:
                kept.remove(weakest)
                stats['dropped_poly'] += 1
        active.append(n)
        kept.append(n)
    kept.sort(key=lambda n: (n['start_s'], n['midi']))
    stats['kept'] = len(kept)
    stats['repaired_pct'] = round(100.0 * (len(notes) - len(kept) + stats['trimmed']) / max(len(notes), 1), 1)
    short = [n for n in kept if n['end_s'] - n['start_s'] < c['short_note_s']]
    stats['short_pct'] = round(100.0 * len(short) / max(len(kept), 1), 1)
    return kept, stats


def overlap_violations(notes, polyphony):
    """Number of instants (note starts) at which more notes sound than the voice's polyphony allows. 0 after clean_voice."""
    import numpy as np
    s = np.array([n['start_s'] for n in notes])
    e = np.array([n['end_s'] for n in notes])
    return int(sum(np.sum((s <= t) & (e > t)) > polyphony for t in s)) if len(s) else 0


def key_fit_pct(notes_by_voice, key, modes):
    """Share of note-time (percent) whose pitch class lies in the song's key. None when the key is unknown."""
    from .music_db import PC
    if not key or not key.get('tonic') or key.get('mode') not in modes:
        return None
    letter = str(key['tonic'])[:1].upper()
    tonic = PC.get(letter)
    if tonic is None:
        return None
    tonic = (tonic + (1 if '#' in str(key['tonic']) else -1 if str(key['tonic'])[1:2] == 'b' else 0)) % 12
    scale = {(tonic + i) % 12 for i in modes[key['mode']]}
    tot = inside = 0.0
    for notes in notes_by_voice.values():
        for n in notes:
            d = n['end_s'] - n['start_s']
            tot += d
            inside += d * (n['midi'] % 12 in scale)
    return None if tot == 0 else 100.0 * inside / tot
