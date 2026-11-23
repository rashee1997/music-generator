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

A layout may also declare a `fold_chain` (a list of layout names ending at the stereo pair): 3.2 folds to 3.1 (the two
low-frequency channels are summed, scaled by their coherence) and 3.1 folds to 2.0. `fold_chain` runs those stages and
returns every intermediate programme, so a gate can measure what each stage costs.
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


def lfe_sum_gain(rho):
    """Gain for summing two low-frequency channels into one, from their correlation `rho` (-1..1).

    Identical channels (rho 1) add to twice the amplitude, so each is weighted 0.5; unrelated channels (rho 0) add in
    power, so each is weighted 0.7071. General form: 1 / sqrt(2 (1 + rho)), which keeps the power of the sum equal to
    the power of one channel. Opposed channels (rho -1) cancel: the gain is capped at 1 so a flipped sub is reported,
    not amplified.
    """
    return float(min(1.0, 1.0 / np.sqrt(max(2.0 * (1.0 + float(rho)), 1e-9))))


def lfe_correlation(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    den = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    return float(np.sum(a * b) / den) if den > 0.0 else 1.0


def _merge_lfe(audio, src, dst):
    """One fold stage between two layouts that share their main channel names: mains copy across, the source's
    low-frequency channels are summed into the destination's single one with `lfe_sum_gain`."""
    y = np.asarray(audio, dtype=np.float64)
    src_names, dst_names = config.channel_names(src), config.channel_names(dst)
    src_lfe, dst_lfe = config.lfe_names(src), config.lfe_names(dst)
    if len(dst_lfe) != 1 or len(src_lfe) < 2:
        raise ValueError(f'fold stage {src} -> {dst}: expects two low-frequency channels folding into one')
    out = np.zeros((y.shape[0], len(dst_names)), dtype=np.float64)
    for j, name in enumerate(dst_names):
        if name in src_names and name not in src_lfe:
            out[:, j] = y[:, src_names.index(name)]
    cols = [y[:, src_names.index(n)] for n in src_lfe]
    k = lfe_sum_gain(lfe_correlation(cols[0], cols[1])) if len(cols) == 2 else 1.0 / len(cols)
    out[:, dst_names.index(dst_lfe[0])] = k * np.sum(cols, axis=0)
    return out


def fold_chain(audio, layout_name):
    """Run the layout's `fold_chain`: [(layout name, programme)] from the source layout to the stereo pair, inclusive.

    A stage into a layout with fewer low-frequency channels merges them (`_merge_lfe`); the last stage is the ordinary
    coefficient fold (`fold`). A layout with no chain is folded in one step.
    """
    lay = config.layout(layout_name)
    stages = [(layout_name, np.asarray(audio, dtype=np.float64))]
    current, y = layout_name, stages[0][1]
    for nxt in (lay.get('fold_chain') or []):
        if len(config.layout(nxt).get('speakers') or []) > 2:
            y = _merge_lfe(y, current, nxt)
        else:
            y = fold(y, current)
        current = nxt
        stages.append((current, y))
    if len(stages) == 1:
        stages.append(('stereo_bs775', fold(y, layout_name)))
    return stages
