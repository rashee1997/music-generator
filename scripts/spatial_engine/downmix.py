# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""downmix.py - the two-channel fold-down of a multichannel deliverable (ITU-R BS.775).

The coefficients are data: every layout preset carries a `downmix` map of speaker -> [left, right]. A speaker with no
coefficient is a data problem (config.problems reports it) rather than being dropped silently.

    L' = sum(g_L[spk] * channel[spk])      R' = sum(g_R[spk] * channel[spk])

The low-frequency channel has no coefficient: it is not part of the two-channel fold.
"""
import numpy as np

from . import config


def fold(audio, layout_name):
    """(N, channels) in the layout's order -> (N, 2), using the layout's own coefficients."""
    y = np.asarray(audio, dtype=np.float64)
    lay = config.layout(layout_name)
    names = config.channel_names(layout_name)
    if y.ndim != 2 or y.shape[1] != len(names):
        raise ValueError(f'expected {len(names)} channels for layout "{layout_name}", got shape {y.shape}')
    coeffs = lay.get('downmix') or {}
    out = np.zeros((y.shape[0], 2), dtype=np.float64)
    for i, name in enumerate(names):
        c = coeffs.get(name)
        if not c:
            continue
        out[:, 0] += float(c[0]) * y[:, i]
        out[:, 1] += float(c[1]) * y[:, i]
    return out


def rms_db(y):
    y = np.asarray(y, dtype=np.float64)
    return float(20.0 * np.log10(np.sqrt(np.mean(np.square(y)) + 1e-20)))
