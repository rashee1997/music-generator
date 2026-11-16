# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""trajectory.py - where a source is at every moment, read from a preset's `spatial.trajectory`.

Three forms, all data:
  * start_/end_ azimuth, elevation, distance: a straight move over the whole stem (the form the engine always had).
  * keyframes: [{"bar": 9, "azimuth": 40, "elevation": 20, "distance": 1.6}, ...]. A key is placed by "t_s"
    (seconds), "bar" (1-based, through the score's tempo map) or "section" (+ "bar" inside it). Between keys the
    path is a PCHIP curve: it passes through every key and never overshoots one.
  * mode "sway": a slow periodic move around the track's own place; `rate` in cycles per bar (sync "bars") or Hz.

A path is sampled on a control grid, one point every HOP samples. Angles are not wrapped: write 0 -> 360 for a
full turn. `spatial_role: "anchor"` keeps a source within a small span of its place (low instruments have no
cue that survives motion); "mover" is free.
"""
import numpy as np

HOP = 64
MIN_DISTANCE_M = 0.2
AXES = (('azimuth', 0), ('elevation', 1), ('distance', 2))


def _tempo(score):
    import humanize
    return humanize.tempo_map_for(score or {}, seed=(score or {}).get('seed', 1))


def _beats_per_bar(score):
    return float(((score or {}).get('ts') or [4, 4])[0])


def seconds(anchor, score=None, tm=None):
    """A place in the piece -> seconds. anchor: {"t_s"} | {"bar"} | {"section", optional "bar"}; bars are 1-based."""
    if 't_s' in anchor:
        return float(anchor['t_s'])
    tm = tm or _tempo(score)
    bb = _beats_per_bar(score)
    start = 0.0
    if anchor.get('section') is not None:
        plan = ((score or {}).get('plan') or {}).get('sections') or []
        hit = next((s for s in plan if s.get('name') == anchor['section']), None)
        if hit is None:
            raise ValueError(f'no section "{anchor["section"]}" in the score plan; known: '
                             f'{[s.get("name") for s in plan]}')
        if hit.get('start_s') is not None:
            return float(hit['start_s']) + float(tm.sec((float(anchor.get('bar', 1)) - 1.0) * bb))
        start = float(hit.get('start_bar', 0)) * bb
    elif 'bar' not in anchor:
        raise ValueError(f'a key needs "t_s", "bar" or "section", got {sorted(anchor)}')
    return float(tm.sec(start + (float(anchor.get('bar', 1)) - 1.0) * bb))


def path(traj, azimuth, elevation, distance, n, sr, score=None):
    """(m, 3) azimuth / elevation / distance on the control grid, or None for a source that stays put."""
    if not traj:
        return None
    m = n // HOP + 2
    t = np.arange(m) * HOP / float(sr)
    base = np.array([float(azimuth), float(elevation), float(distance)])
    out = np.tile(base, (m, 1))
    keys = traj.get('keyframes')
    mode = str(traj.get('mode') or ('keyframes' if keys else 'line'))
    if mode == 'static':
        return None
    if mode == 'keyframes':
        if not keys:
            raise ValueError('trajectory mode "keyframes" needs a "keyframes" list')
        tm = _tempo(score) if any('t_s' not in k for k in keys) else None
        rows = sorted((seconds(k, score, tm), k) for k in keys)
        times = np.array([r[0] for r in rows])
        if len(times) > 1 and np.min(np.diff(times)) <= 0:
            raise ValueError('two trajectory keyframes fall on the same moment')
        for name, col in AXES:
            vals, last = [], base[col]
            for _, k in rows:                      # an axis a key does not name holds its previous value
                last = float(k.get(name, last))
                vals.append(last)
            if len(times) == 1:
                out[:, col] = vals[0]
            else:
                from scipy.interpolate import PchipInterpolator
                out[:, col] = PchipInterpolator(times, vals)(np.clip(t, times[0], times[-1]))
    elif mode == 'sway':
        rate = float(traj.get('rate', 0.25))
        if str(traj.get('sync', 'bars')) == 'bars':
            phase = _tempo(score).beat(t) / _beats_per_bar(score) * rate
        else:
            phase = t * rate
        w = 2.0 * np.pi * phase
        out[:, 0] += 0.5 * float(traj.get('azimuth_span_deg', 0.0)) * np.sin(w)
        out[:, 1] += 0.5 * float(traj.get('elevation_span_deg', 0.0)) * np.sin(w + 0.5 * np.pi)
        out[:, 2] += 0.5 * float(traj.get('distance_span_m', 0.0)) * np.sin(w)
    elif mode == 'line':
        f = np.clip(t / max(n / float(sr), 1e-9), 0.0, 1.0)
        for name, col in AXES:
            a = float(traj.get('start_' + name, base[col]))
            b = float(traj.get('end_' + name, base[col]))
            out[:, col] = a + f * (b - a)
    else:
        raise ValueError(f'trajectory mode "{mode}" is not one of static, line, keyframes, sway')
    out[:, 1] = np.clip(out[:, 1], -90.0, 90.0)
    out[:, 2] = np.maximum(out[:, 2], MIN_DISTANCE_M)
    return out


def anchor(p, azimuth, elevation, distance, max_span_deg):
    """Hold a path within +-max_span/2 of its place, at its own distance: the "anchor" role."""
    half = 0.5 * float(max_span_deg)
    q = p.copy()
    q[:, 0] = float(azimuth) + np.clip(p[:, 0] - float(azimuth), -half, half)
    q[:, 1] = float(elevation) + np.clip(p[:, 1] - float(elevation), -half, half)
    q[:, 2] = float(distance)
    return q


def is_anchor(traj, role):
    """Bass and drums are anchors whatever the preset says; otherwise the preset's `spatial_role` decides."""
    return role in ('bass', 'drum') or str((traj or {}).get('spatial_role', 'mover')) == 'anchor'


def speed_deg_per_s(p, sr):
    """The fastest angular speed along a path (great-circle angle between neighbouring control points)."""
    if p is None or len(p) < 2:
        return 0.0
    az, el = np.radians(p[:, 0]), np.radians(p[:, 1])
    v = np.stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)], axis=1)
    ang = np.degrees(np.arccos(np.clip(np.sum(v[1:] * v[:-1], axis=1), -1.0, 1.0)))
    return float(np.max(ang) * sr / HOP)


def at_samples(p, col, a, b):
    """One axis of a path at samples a..b-1 (linear between control points)."""
    return np.interp(np.arange(a, b), np.arange(len(p)) * HOP, p[:, col])
