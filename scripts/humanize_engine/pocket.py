# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Groove pockets: a pushed or laid-back feel is timing AND dynamics, not a single millisecond offset.

A pocket is data (`references/data/presets/humanize/<name>.json`): one signed offset and one velocity
delta per drum limb. The direction is measured (a laid-back snare is later and louder, a pushed hi-hat
earlier and louder); the magnitudes are starting values.
"""
import presets


def get(name):
    """The named pocket, or ValueError listing the known ones."""
    try:
        return presets.get('humanize', name)
    except KeyError as ex:
        raise ValueError(str(ex)) from None


def offsets(pocket, p, limb_of):
    """Signed ms and velocity delta per drum note, from the pocket's per-limb table."""
    import numpy as np
    table = (pocket or {}).get('instruments') or {}
    ms = np.zeros(len(p), dtype=float)
    dv = np.zeros(len(p), dtype=float)
    for i, pitch in enumerate(p):
        spec = table.get(limb_of(pitch)) or {}
        ms[i] = float(spec.get('ms', 0.0))
        dv[i] = float(spec.get('vel', 0.0))
    return ms, dv


def tempo_power(pocket, default=0.4):
    return float((pocket or {}).get('tempo_power', default))
