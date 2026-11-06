# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""shot_scale.py - how wide is this shot.

The music's size has to follow the camera: a wide of a mountain can hold an
orchestra, a close-up of a hand cannot (references/workflow/music-direction.md
section 2.4). This module measures the frame and returns a label; the mapping
preset decides what density that label allows.

Method: the analysis frame is cut into a grid of cells, each cell's local
contrast (variance of the discrete Laplacian) is measured, and the bounding box
of the highest-contrast cells is taken as the subject. The bounding box's share
of the frame decides the scale: detail spread across the whole frame reads as a
wide shot, detail confined to one corner as an insert. Every threshold is a
preset key; the defaults are starting values and say so in the preset's
`provenance`.
"""
import os
import subprocess

import numpy as np

SCALES = ('wide', 'medium', 'close', 'insert')


def block_contrast(luma, grid=(16, 9)):
    """Local contrast per grid cell: variance of the discrete Laplacian."""
    luma = np.asarray(luma, dtype=np.float32)
    if luma.ndim != 2 or luma.size == 0:
        return np.zeros((int(grid[1]), int(grid[0])), np.float32)
    gh, gw = int(grid[1]), int(grid[0])
    h, w = luma.shape
    ys = np.linspace(0, h, gh + 1).astype(int)
    xs = np.linspace(0, w, gw + 1).astype(int)
    out = np.zeros((gh, gw), np.float32)
    for i in range(gh):
        for j in range(gw):
            cell = luma[ys[i]:max(ys[i] + 1, ys[i + 1]), xs[j]:max(xs[j] + 1, xs[j + 1])]
            if cell.size < 9:
                continue
            lap = (np.roll(cell, 1, 0) + np.roll(cell, -1, 0) +
                   np.roll(cell, 1, 1) + np.roll(cell, -1, 1) - 4.0 * cell)
            out[i, j] = float(lap.var())
    return out


def subject_box(contrast, mass_frac=0.25, focus_floor=0.05, peak_frac=0.5):
    """Bounding box (y0, y1, x0, x1) of the subject cells, and its area share of the frame.

    mass_frac: at least the top quartile of cells is offered to the threshold.
    peak_frac: and no cell below this fraction of the peak contrast can be subject, so a
               flat background behind a detailed subject does not enter through the
               quantile (with a quarter of the cells at zero, the quantile is zero).
    focus_floor: below this peak contrast the frame has no readable subject at all.

    The share is the bounding box area over the whole grid, not the cell count: scattered
    detail covers the frame, a single detailed patch does not.
    """
    c = np.asarray(contrast, dtype=np.float64)
    if c.size == 0 or float(c.max()) < float(focus_floor):
        return None, 0.0
    thresh = max(float(np.quantile(c, max(0.0, min(1.0, 1.0 - float(mass_frac))))),
                 float(c.max()) * max(0.0, min(1.0, float(peak_frac))))
    mask = c >= thresh
    if not mask.any():
        return None, 0.0
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    share = float((y1 - y0) * (x1 - x0)) / float(c.size)
    return (y0, y1, x0, x1), share


def classify(luma, cfg):
    """(scale, share) for one luma frame. Thresholds come from the analysis preset."""
    sc = cfg['shot_scale'] if 'shot_scale' in cfg else cfg
    if not sc.get('enabled', True):
        return 'medium', 0.0
    contrast = block_contrast(luma, tuple(sc.get('grid') or (16, 9)))
    box, share = subject_box(contrast, sc.get('mass_frac', 0.25), sc.get('focus_floor', 0.05),
                             sc.get('peak_frac', 0.5))
    if box is None:
        return 'insert', 0.0
    if share >= float(sc.get('wide_min', 0.60)):
        return 'wide', share
    if share >= float(sc.get('medium_min', 0.30)):
        return 'medium', share
    if share >= float(sc.get('close_min', 0.12)):
        return 'close', share
    return 'insert', share


def scene_scale(frames, cfg):
    """The scale of a scene from several sampled frames: the majority label wins.

    Returns {'scale': str, 'share': float, 'frames': int, 'votes': {scale: n}}.
    """
    votes, shares = {}, []
    for luma in frames or []:
        label, share = classify(luma, cfg)
        votes[label] = votes.get(label, 0) + 1
        shares.append(share)
    if not votes:
        return dict(scale='medium', share=0.0, frames=0, votes={}, scale_source='no frame sampled')
    order = {s: i for i, s in enumerate(SCALES)}
    label = sorted(votes.items(), key=lambda kv: (-kv[1], order.get(kv[0], 9)))[0][0]
    return dict(scale=label, share=round(float(np.median(shares)), 4), frames=len(frames),
                votes=votes, scale_source='measured')


def frame_at(path, t_s, width, height, timeout=20):
    """One luma frame at `t_s`, as a (height, width) float array. None when ffmpeg cannot read it."""
    cmd = ['ffmpeg', '-hide_banner', '-nostats', '-nostdin', '-v', 'error',
           '-ss', f'{max(0.0, float(t_s)):.3f}', '-i', path, '-frames:v', '1',
           '-vf', f'scale={int(width)}:{int(height)},format=rgb24', '-f', 'rawvideo', '-']
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    need = int(width) * int(height) * 3
    if p.returncode != 0 or len(p.stdout) < need:
        return None
    rgb = np.frombuffer(p.stdout, np.uint8, count=need).reshape(int(height), int(width), 3).astype(np.float32)
    return (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]) / 255.0


def sample_scene_frames(path, scenes, cfg, samples_per_scene=None):
    """{scene_id: [luma, ...]} sampled inside each scene window. Empty when the file is unreadable."""
    sc = cfg['shot_scale'] if 'shot_scale' in cfg else cfg
    probe_cfg = cfg.get('probe') or {}
    w, h = int(probe_cfg.get('analysis_width', 320)), int(probe_cfg.get('analysis_height', 180))
    n = int(samples_per_scene if samples_per_scene is not None else sc.get('samples_per_scene', 3))
    out = {}
    for scene in scenes or []:
        a, b = float(scene['start_s']), float(scene['end_s'])
        if b <= a:
            continue
        frames = []
        for k in range(max(1, n)):
            t = a + (b - a) * (k + 0.5) / max(1, n)
            img = frame_at(path, t, w, h)
            if img is not None:
                frames.append(img)
        out[scene['id']] = frames
    return out


def available():
    """Is there an ffmpeg on PATH (the only external tool this module needs)?"""
    from shutil import which
    return which('ffmpeg') is not None


__all__ = ['SCALES', 'block_contrast', 'subject_box', 'classify', 'scene_scale',
           'frame_at', 'sample_scene_frames', 'available', 'os']
