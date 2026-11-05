# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""pan.py - vector base amplitude panning over the loudspeakers a layout names.

Pulkki, V. (1997). "Virtual sound source positioning using vector base amplitude panning." JAES 45(6), 456-466.

A direction is panned to the two or three loudspeakers whose unit vectors enclose it. The gains solve
L g = p for the enclosing triangle, then they are power-normalised so that sum(g_i^2) = 1: the perceived loudness of a
source does not change as it moves. A layout whose speakers are all at ear level is panned pairwise (equal power)
because three coplanar vectors are linearly dependent.

The layouts come from data. There is no speaker table here, and a new layout needs no code.
"""
import itertools
from functools import lru_cache

import numpy as np

EPS = 1e-9


def vector(azimuth_deg, elevation_deg):
    """Unit vector for a position: x right, y front, z up. Azimuth is clockwise from front centre."""
    a = np.radians(float(azimuth_deg))
    e = np.radians(float(elevation_deg))
    return np.array([np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)], dtype=np.float64)


def _horizontal(spk):
    return all(abs(float(s['elevation'])) < EPS for s in spk)


def _pair_gains(p, spk):
    """Two-speaker equal-power pan by azimuth, for a direction on the ring the speakers share."""
    az = np.degrees(np.arctan2(p[0], p[1]))
    ring = sorted((float(s['azimuth']), s['name']) for s in spk)
    names = [n for _, n in ring]
    azs = [a for a, _ in ring]
    # find the two adjacent speakers that enclose `az`; wrap at 180
    ext = azs + [azs[0] + 360.0]
    ext_names = names + [names[0]]
    for i in range(len(azs)):
        lo, hi = ext[i], ext[i + 1]
        target = az if az >= azs[0] else az + 360.0
        if lo - EPS <= target <= hi + EPS:
            frac = 0.0 if hi == lo else (target - lo) / (hi - lo)
            theta = frac * (np.pi / 2.0)
            g = {ext_names[i]: float(np.cos(theta)), ext_names[i + 1]: float(np.sin(theta))}
            # power normalisation: cos^2 + sin^2 is already 1, but keep the invariant explicit
            norm = np.sqrt(sum(v * v for v in g.values())) or 1.0
            return {k: v / norm for k, v in g.items()}
    return {names[0]: 1.0}


@lru_cache(maxsize=None)
def _triplets(vectors):
    """Every non-degenerate loudspeaker triplet and its inverse matrix, as tuples (i, j, k, inv)."""
    out = []
    for i, j, k in itertools.combinations(range(len(vectors)), 3):
        m = np.array([vectors[i], vectors[j], vectors[k]])
        if abs(np.linalg.det(m)) < 1e-4:
            continue
        # p = sum(g_i * v_i), so the system is V^T g = p: the vectors are the columns of V^T, not its rows
        out.append((i, j, k, m, np.linalg.inv(m.T)))
    return out


def gains(azimuth_deg, elevation_deg, spk):
    """{speaker name: gain} for a direction. sum(gain^2) == 1; LFE speakers must not be passed in."""
    if not spk:
        raise ValueError('a pan needs at least one non-LFE speaker')
    p = vector(azimuth_deg, elevation_deg)
    # a direction exactly on a loudspeaker is that loudspeaker, not a blend of a triangle that happens to contain it
    for s in spk:
        if float(np.dot(p, s['vector'])) > 1.0 - 1e-6:
            return {s['name']: 1.0}
    if _horizontal(spk):
        return _pair_gains(p, spk)
    vectors = [tuple(s['vector']) for s in spk]
    best = None
    for i, j, k, m, inv in _triplets(tuple(vectors)):
        g = inv @ p
        if float(np.min(g)) < -1e-6:
            continue
        # a near-coplanar triplet inverts to huge gains that can look positive: accept only a real solution
        if float(np.linalg.norm(m.T @ g - p)) > 1e-9:
            continue
        score = float(np.min(g))
        if best is None or score > best[0]:
            best = (score, {spk[i]['name']: float(g[0]), spk[j]['name']: float(g[1]),
                            spk[k]['name']: float(g[2])})
    if best is None:                       # a direction outside the hull: fall back to the nearest speaker
        idx = int(np.argmax([float(np.dot(p, s['vector'])) for s in spk]))
        return {spk[idx]['name']: 1.0}
    g = best[1]
    norm = float(np.sqrt(sum(v * v for v in g.values()))) or 1.0
    return {k: v / norm for k, v in g.items()}


def pan(signal, azimuth_deg, elevation_deg, spk):
    """Spread a mono signal onto the speakers: {name: array}."""
    x = np.asarray(signal, dtype=np.float64)
    return {name: x * gain for name, gain in gains(azimuth_deg, elevation_deg, spk).items()}
