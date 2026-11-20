# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""gate_clock.py - the one place a gate turns beats into seconds.

The renderer plays the score's tempo map when it has `tempo_points`. A gate that counts beats at the flat `bpm` looks at
the wrong place by seconds on a piece that speeds up (a bed judged from 88 s that began at 104 s; a kick grid that
drifts off the real beat). Every gate module asks this module for the conversion; `tests/test_gate_clock.py` fails when a
gate module reads `score['bpm']` without saying why a flat tempo is right there.
"""
import numpy as np


# The tempo the renderer plays when a score names none: humanize.tempo_map_for reads score.get('bpm', 90). Every gate
# module takes its fallback from here, so two gates never count the same score at two different flat tempos.
DEFAULT_BPM = 90.0          # starting value, equal to the renderer's own default in humanize.tempo_map_for


def flat_bpm(score):
    """The flat tempo of a score, DEFAULT_BPM when it names none."""
    return float(score.get('bpm') or DEFAULT_BPM)


def tempo_map(score, problems=None):
    """The renderer's TempoMap when the score declares `tempo_points`, else None (a flat tempo applies).

    A tempo map that cannot be built never degrades to a flat tempo silently: the reason is appended to `problems`
    (the caller turns it into a WARN row) and the flat tempo is used; with no `problems` list it is raised."""
    if not score.get('tempo_points'):
        return None
    try:
        import humanize as hz
        return hz.tempo_map_for(score, seed=score.get('seed', 7))
    except Exception as exc:
        msg = (f'the tempo map could not be built ({type(exc).__name__}: {exc}); beats were counted at the flat '
               f'{flat_bpm(score):g} BPM, which is not the tempo the renderer plays')
        if problems is None:
            raise ValueError(msg) from exc
        problems.append(msg)
        return None


def seconds_fn(score, problems=None):
    """beats -> seconds, on the tempo map when the score has one, else at the flat bpm. Accepts a number or an array.
    See tempo_map() for `problems`."""
    tm = tempo_map(score, problems)
    if tm is not None:
        return lambda b: np.vectorize(lambda x: float(tm.sec(float(x))), otypes=[float])(b) if np.ndim(b) else float(tm.sec(float(b)))
    bd = 60.0 / flat_bpm(score)
    return lambda b: np.asarray(b, dtype=float) * bd if np.ndim(b) else float(b) * bd


def beat_grid_seconds(score, total_s):
    """Seconds of every whole beat from 0 to total_s, on the tempo map."""
    sec = seconds_fn(score)
    out, b = [], 0
    while True:
        t = float(sec(b))
        if t > total_s + 1.0 or b > 100000:
            break
        out.append(t)
        b += 1
    return np.asarray(out, dtype=float)


def bar_beats(score):
    ts = score.get('ts') or [4, 4]
    return float(ts[0]) * 4.0 / float(ts[1])
