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

"""cli_util.py - small shared helpers so the command-line tools fail with one clear line, not a traceback."""
import os
import re
import sys

_NOTE = re.compile(r'^([A-Ga-g])([#b]?)(-?\d)$')
_SEMI = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def require_file(path, what='file'):
    """Exit with a plain message when a required input path does not exist."""
    if path and not os.path.isfile(path):
        sys.exit(f'error: {what} not found: {path}')
    return path


def require_dir(path, what='folder'):
    if path and not os.path.isdir(path):
        sys.exit(f'error: {what} not found: {path}')
    return path


def pitch_to_midi(p):
    """60, '60', 60.0 and note names ('D3', 'F#4', 'Bb2', C4 = 60) -> int MIDI. Other strings (drum names) pass through."""
    if isinstance(p, (int, float)):
        return int(p)
    s = str(p).strip()
    if re.fullmatch(r'-?\d+(\.\d+)?', s):
        return int(float(s))
    m = _NOTE.match(s)
    if not m:
        return p
    n = _SEMI[m.group(1).upper()] + (1 if m.group(2) == '#' else -1 if m.group(2) == 'b' else 0)
    return 12 * (int(m.group(3)) + 1) + n


def normalize_pitches(score):
    """Convert note-name pitches to MIDI numbers in place, so every later stage sees numbers."""
    for tr in score.get('tracks', []):
        for n in tr.get('notes', []):
            if 'p' in n:
                n['p'] = pitch_to_midi(n['p'])
    return score


def midi_int(p, where=''):
    """Pitch as an int MIDI number, or a ValueError that says what to write instead."""
    v = pitch_to_midi(p)
    if isinstance(v, str):
        raise ValueError(f'{where}pitch {p!r} is not a MIDI number (0-127) or a note name such as "D3"')
    return int(v)
