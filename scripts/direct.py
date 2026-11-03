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
"""direct.py - the edits a music director makes to a score, as plain functions.

compose.py gives a first draft from a brief. These functions change it on purpose, the way a
director would ("keep a steady pulse under the whole cue", "a brass fanfare on the reveal", "the
strings should swell into the hit"). Each one edits the score dict in place and returns it.

    import json, direct
    s = json.load(open('score.json', encoding='utf-8'))
    direct.add_pulse(s, start=0, end=None, gain_db=-6, dyn=[[0, .45], [20, .7], [24, 1.0]])
    direct.add_line(s, 'fanfare', 'trumpet', at_beat=66,
                    phrase=[(0, .5, 70), (.5, .5, 74), (1, .5, 77), (2, 1.5, 70)], gain_db=-3)
    json.dump(s, open('score2.json', 'w', encoding='utf-8'))

Then render:  python3 scripts/render_natural.py score2.json --out cue.wav
Then listen:  python3 scripts/listen.py cue.wav --direction direction.json
Times are in beats (score['bpm'] and score['ts'] say how long a beat is).
"""
import copy

KIT_FOR_PULSE = 'orchestral'      # drum kit name (soundbank.resolve)


def beats_per_bar(score):
    ts = score.get('ts') or [4, 4]
    return int(ts[0])


def _track(score, name):
    for t in score['tracks']:
        if t['name'] == name:
            return t
    return None


def add_pulse(score, name='pulse', start=0.0, end=None, gain_db=-6.0, dyn=None, humanize='tight',
              floor_tom_on_beat3=True, accent=0.85, soft=0.6):
    """A steady grid under the cue: a kick on every beat (accented on the bar), optionally a floor tom
    on beat 3. This is what makes a trailer or a march read as driving; without it the pulse check fails."""
    bpb = beats_per_bar(score)
    if end is None:
        end = max(n['t'] + n['d'] for tr in score['tracks'] for n in tr['notes'])
    notes = []
    b = float(start)
    while b < end:
        bar_pos = int(round(b)) % bpb
        notes.append({'t': b, 'd': 0.2, 'p': 'kick', 'v': accent if bar_pos == 0 else soft})
        if floor_tom_on_beat3 and bar_pos == 2 % bpb:
            notes.append({'t': b, 'd': 0.2, 'p': 'tom_floor', 'v': 0.5})
        b += 1.0
    track = dict(name=name, instrument=KIT_FOR_PULSE, role='drum', notes=notes, gain_db=gain_db,
                 humanize=humanize)
    if dyn:
        track['dynamics'] = dyn
    score['tracks'].append(track)
    return score


def add_line(score, name, instrument, at_beat, phrase, gain_db=-3.0, role='melody', dyn=None,
             reverb=0.2, pan=0.0, humanize='natural'):
    """A melodic phrase placed at a beat. phrase = [(rel_beat, dur_beats, midi_pitch), ...] with
    velocity 0.9 unless you edit it afterwards. Use for fanfares, hooks, answers, stingers."""
    notes = [{'t': at_beat + rb, 'd': d, 'p': int(p), 'v': 0.9, 'art': 'legato'} for rb, d, p in phrase]
    track = dict(name=name, instrument=instrument, role=role, notes=notes, gain_db=gain_db,
                 reverb=reverb, pan=pan, humanize=humanize)
    if dyn:
        track['dynamics'] = dyn
    score['tracks'].append(track)
    return score


def add_notes(score, name, notes):
    """Append notes to an existing track (e.g. an extra bar of strings, a held final chord)."""
    tr = _track(score, name)
    if tr is None:
        raise KeyError(f'no track named {name!r}; tracks: {[t["name"] for t in score["tracks"]]}')
    tr['notes'].extend(dict(n) for n in notes)
    return score


def set_gain(score, name, gain_db):
    tr = _track(score, name)
    if tr is None:
        raise KeyError(name)
    tr['gain_db'] = float(gain_db)
    return score


def set_arc(score, name, points):
    """Shape one track's loudness over time: points = [[beat, 0..1], ...]."""
    tr = _track(score, name)
    if tr is None:
        raise KeyError(name)
    tr['dynamics'] = [[float(b), float(v)] for b, v in points]
    return score


def remove_track(score, name):
    score['tracks'] = [t for t in score['tracks'] if t['name'] != name]
    return score


def copy_track(score, name, new_name, transpose=0, shift_beats=0.0, gain_db=None):
    """Duplicate a track (a canon, an octave doubling, a later entry) with optional shift and transpose."""
    tr = _track(score, name)
    if tr is None:
        raise KeyError(name)
    new = copy.deepcopy(tr)
    new['name'] = new_name
    for n in new['notes']:
        n['t'] = float(n['t']) + shift_beats
        if isinstance(n['p'], int):
            n['p'] = n['p'] + transpose
    if gain_db is not None:
        new['gain_db'] = gain_db
    score['tracks'].append(new)
    return score


def tempo(score, bpm):
    """Change the tempo of the whole score (note times stay in beats, so the cue gets shorter or longer)."""
    score['bpm'] = float(bpm)
    return score


if __name__ == '__main__':
    import argparse
    import json
    ap = argparse.ArgumentParser(description='Small director edits on a score JSON (see docstring).')
    ap.add_argument('score')
    ap.add_argument('--out', required=True)
    ap.add_argument('--pulse', action='store_true', help='add a steady kick pulse from the start')
    ap.add_argument('--pulse-gain', type=float, default=-6.0)
    ap.add_argument('--bpm', type=float, help='set the tempo')
    ap.add_argument('--remove', nargs='*', default=[], help='track names to remove')
    a = ap.parse_args()
    import cli_util
    cli_util.require_file(a.score, 'score')
    s = json.load(open(a.score, encoding='utf-8'))
    if a.bpm:
        tempo(s, a.bpm)
    for n in a.remove:
        remove_track(s, n)
    if a.pulse:
        add_pulse(s, gain_db=a.pulse_gain)
    json.dump(s, open(a.out, 'w', encoding='utf-8'))
    print('wrote', a.out)
