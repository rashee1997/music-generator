# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Articulation: how long a note is held, how it releases, and the piano pedal that follows harmony."""
import numpy as np

def finalize_durations(t0, t1, rd, c, v, phrases, base_role, is_drum, rng, n, fig_roles):
    """Written beats -> played seconds: gate, velocity-duration coupling, phrase-end breath."""
    dur = (t1 - t0) * (rd['gate'] + float(c.get('gate_bias', 0.0))) * (1 + rng.normal(0, 0.04, n))
    if not is_drum:
        dur = dur * (1.0 + float(c.get('vel_dur', 0.0)) * (np.clip(v, 1, 127) - 90.0) / 64.0)
    if base_role in fig_roles:
        for idx in phrases.values():
            dur[idx[-1]] *= 1.08
    return dur


def auto_pedal(events, tm, change_beats, lift_ms=40, re_press_ms=60):
    """Sustain-pedal events [(t_sec, 0|127)] for a piano line: pressed through each harmony, lifted
    just before every harmony change and pressed again right after (legato pedaling)."""
    out = [(0.0, 127)]
    for b in sorted(change_beats):
        t = float(tm.sec(b))
        out.append((max(0.0, t - lift_ms / 1000.0), 0))
        out.append((t + re_press_ms / 1000.0, 127))
    end = max((e['t'] + e['dur'] for e in events), default=0)
    out.append((end + 0.3, 0))
    return out
