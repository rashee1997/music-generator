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
"""cut_windows.py - the moments a direction sheet asks the music to stop dead, read once for the renderer and the gate.

A cinematic cue sometimes ends a section on a hard cut: everything that was sustaining stops on the frame. Two parts of
the engine have to agree about it:

    renderer   ramps the sustained voices to zero over RAMP_MS before the cut, so the waveform itself has no step
               (`dsp.hard_cut`, called from `render_natural.build_stems`)
    gate       does not call the level drop at that moment a defect: `stem.cut` and `cut.hard` skip a drop whose time
               lies inside an intentional cut window (`gate_checks.check_cut`). Every other row is untouched there:
               clicks, dropout, clipping, DC and the abrupt end are judged inside the window like anywhere else.

The sheet is the one source. A hit in `hits` with `"sync": "hard"` opens a window of +-HALF_S around its `t` (seconds). Only a
hit with `"kind": "cut"` also asks the renderer to cut the sustained voices (an accent that lands on top of held strings
is hard-synced but must not silence them). `attach` writes both lists onto the score in memory; a score that already
carries them keeps its own.

    score["intentional_cut_windows"]  [[start_s, end_s], ...]   what the gate skips
    score["hard_cuts"]                [t_s, ...]                what the renderer ramps
"""
import json
import math
import os

HALF_S = 0.150           # the window either side of a hard hit: the gate's drop measure is ~20 ms frames, a cut is on the frame
RAMP_MS = 15.0            # the renderer's micro-ramp: slower than a click, faster than any audible decay
MAX_HALF_S = 0.5          # a window wider than this is not a cut, it would exempt a whole passage from the drop check
MAX_WINDOWS = 64


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def read_sheet(project_dir):
    """The project's direction sheet (the first parseable `direction/*.json` holding an object), or {}."""
    if not project_dir:
        return {}
    folder = os.path.join(project_dir, 'direction')
    if not os.path.isdir(folder):
        return {}
    for name in sorted(os.listdir(folder)):
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(folder, name), encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def from_sheet(sheet, half_s=HALF_S):
    """{'windows': [[a, b], ...], 'cuts': [t, ...]} for the hard hits of a direction sheet, sorted, no duplicates.
    A hit without a numeric time, or with a negative one, is ignored (the sheet's own gate reports it)."""
    windows, cuts = [], []
    for hit in (sheet or {}).get('hits') or []:
        if not isinstance(hit, dict) or str(hit.get('sync', '')).lower() != 'hard' or not _num(hit.get('t')):
            continue
        t = float(hit['t'])
        if t < 0:
            continue
        w = [round(max(0.0, t - half_s), 4), round(t + half_s, 4)]
        if w not in windows:
            windows.append(w)
        if str(hit.get('kind', '')).lower() == 'cut' and round(t, 4) not in cuts:
            cuts.append(round(t, 4))
    return {'windows': sorted(windows), 'cuts': sorted(cuts)}


def attach(score, sheet, half_s=HALF_S):
    """The score with the sheet's windows and cuts on it. Returns a new dict; a key the score already has is kept."""
    out = dict(score)
    found = from_sheet(sheet, half_s)
    if found['windows'] and 'intentional_cut_windows' not in out:
        out['intentional_cut_windows'] = found['windows']
    if found['cuts'] and 'hard_cuts' not in out:
        out['hard_cuts'] = found['cuts']
    return out


def windows_of(score_or_list):
    """Valid [start_s, end_s] windows as a list of (a, b) tuples. A malformed entry, a reversed one or one wider than
    2 * MAX_HALF_S is dropped: a bad list can only exempt less, never more."""
    raw = score_or_list.get('intentional_cut_windows') if isinstance(score_or_list, dict) else score_or_list
    out = []
    for w in raw or []:
        if isinstance(w, (list, tuple)) and len(w) == 2 and _num(w[0]) and _num(w[1]):
            a, b = float(w[0]), float(w[1])
            if 0.0 <= a < b and (b - a) <= 2.0 * MAX_HALF_S:
                out.append((a, b))
    return sorted(out)[:MAX_WINDOWS]


def cuts_of(score):
    """The hard-cut times in seconds, as floats, sorted; malformed entries are dropped."""
    return sorted(float(t) for t in (score or {}).get('hard_cuts') or [] if _num(t) and float(t) >= 0.0)


def inside(t, windows):
    """True when time `t` (seconds) lies in any of the (a, b) windows."""
    t = float(t)
    return any(a <= t <= b for a, b in windows)


def problems(score):
    """What is wrong with the lists a score carries (empty = good). Used by the tests and the project gate."""
    out = []
    raw = (score or {}).get('intentional_cut_windows')
    if raw is not None:
        if not isinstance(raw, list):
            out.append('intentional_cut_windows must be a list of [start_s, end_s]')
        else:
            bad = len(raw) - len(windows_of(raw))
            if bad:
                out.append(f'{bad} intentional_cut_windows entr{"y is" if bad == 1 else "ies are"} malformed, reversed or wider than '
                           f'{2 * MAX_HALF_S:g} s and will be ignored')
    return out
