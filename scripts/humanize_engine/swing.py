# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Swing: the ratio a player uses at a tempo, and where the off-beat lands."""
import numpy as np

import roles as rolelib

from .config import FIG, SWING_BPM_FAST, SWING_BPM_SLOW, SWING_BUR_FAST, SWING_BUR_SLOW, SWING_FIG_DEPTH, SWING_FLOOR_S


def auto_swing(bpm):
    """The swing ratio a player actually uses at a tempo, as a swing value (0.5 straight): BUR falls with tempo."""
    t = np.clip((SWING_BPM_FAST - float(bpm)) / (SWING_BPM_FAST - SWING_BPM_SLOW), 0.0, 1.0)
    bur = SWING_BUR_FAST + (SWING_BUR_SLOW - SWING_BUR_FAST) * float(t)
    return bur / (1.0 + bur)


def apply_swing(notes, swing=0.5, unit=0.5, bpm=None, role=None, downbeat_ms=0.0):
    """Shift off-beat subdivisions late. swing 0.5 = straight, 0.58 light, 0.66 = triplet feel.

    swing='auto' takes the ratio from the tempo (auto_swing): ~3.5:1 when slow, 2:1 at medium-fast, straight when
    fast. A figure role swings less than the accompaniment (SWING_FIG_DEPTH), which is what a soloist does over a
    ride cymbal. The short side of a pair never drops below SWING_FLOOR_S, so a fast passage straightens itself
    instead of asking for a 40 ms note.

    The shift is capped at 45 % of the gap to the next onset, so a dense swung passage can never reorder or
    overlap notes (at 16th density a 0.66 swing used to hand a note to its successor). `downbeat_ms` delays the
    notes that land on a beat: measured swing is a long-short pair where the downbeat is late too, not only an
    off-beat pushed later (Communications Physics 2022).
    """
    if isinstance(swing, str):
        if swing.lower() != 'auto':
            raise ValueError(f"swing: expected a number or 'auto', got {swing!r}")
        swing = auto_swing(120.0 if bpm is None else bpm)
    eff = float(swing)
    if role is not None:
        try:
            if rolelib.canonical(role) in FIG:
                eff = 0.5 + SWING_FIG_DEPTH * (eff - 0.5)
        except Exception:
            pass
    if abs(eff - 0.5) < 1e-3:
        return _downbeat(notes, downbeat_ms, bpm)
    shift = (eff - 0.5) * 2 * unit
    if bpm:
        room = unit - float(bpm) * SWING_FLOOR_S / 60.0      # the short side, in beats, at the floor
        shift = min(shift, max(0.0, room))
        if shift <= 1e-9:
            return _downbeat(notes, downbeat_ms, bpm)
    times = sorted({round(float(n['t']), 9) for n in notes})
    nxt = {a: b for a, b in zip(times, times[1:])}
    out = []
    for n in notes:
        m = n['t'] / unit
        r = round(m)
        t_new = n['t']
        if r % 2 == 1 and abs(m - r) < 0.2:
            room = nxt.get(round(float(n['t']), 9))
            cap = 0.45 * (room - n['t']) if room is not None else shift
            t_new = n['t'] + min(shift, max(0.0, cap))
        out.append(dict(n, t=t_new) if t_new != n['t'] else n)
    return _downbeat(out, downbeat_ms, bpm)


def _downbeat(notes, downbeat_ms=0.0, bpm=None):
    """Delay the notes that sit on a beat, in seconds converted to beats (0 = untouched, byte-identical)."""
    if not downbeat_ms:
        return notes
    ms = float(np.clip(float(downbeat_ms), -20.0, 20.0))
    d = ms / 1000.0 * (float(bpm) / 60.0 if bpm else 1.0)
    return [dict(n, t=n['t'] + d) if abs(float(n['t']) - round(float(n['t']))) < 1e-6 else n for n in notes]
