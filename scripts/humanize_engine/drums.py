# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Drum-kit behaviour: runs, flams and the pocket that replaces the fixed per-piece push."""
import numpy as np

import pattern_audit as pa


def _drum_run(run, v, ns, start_boost, rng):
    """A run of rapid same-pitch hits with no dynamic contour is a machine gun: accent alternately."""
    if not pa._machine_run(v[run]):
        return
    m = len(run)
    for pos, i in enumerate(run):
        v[i] += 5.0 if pos % 2 == 0 else -5.0
        if v[run[-1]] > v[run[0]]:                 # an ascending build gets an exponential arch
            v[i] += 4.0 * ((pos / max(m - 1, 1)) ** 1.6 - 0.5)
        start_boost[i] += rng.uniform(-0.003, 0.003)

