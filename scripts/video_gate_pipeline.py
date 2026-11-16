# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""video_gate_pipeline.py - the picture rows a music render can answer on its own.

`pipeline.stage6_ci_quality_suite` uses this when a score carries an enabled
`video` block but no program was supplied. It is the score-side half of the
video gate (`video.cut_sync`, `video.motion_sync`, `video.hit_density`,
`video.grid_phase`, `video.hit_class`, `video.shot_scale` and `video.duration_lock`
against the picture length). The program-side half (dialogue, loudness, mux)
needs the program and runs through `video-mixer/gate/pass_.py`.

Keeping this here, and not in `pipeline.py`, is the separation rule: the music
engine knows nothing about a picture beyond the block a score happens to carry.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
VIDEO = os.path.join(SKILL, 'video-mixer')
for p in (VIDEO, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)


def score_rows(score):
    """Picture rows that need only the score. Never raises: a failure becomes a WARN row."""
    try:
        from gate import rows as R
    except Exception as exc:                       # video-mixer missing: say so, do not pass
        return [('WARN', 'video.gate', f'video-mixer is not importable: {exc}')]
    video = score.get('video') or {}
    gate_cfg = dict(video.get('gate_cfg') or {})
    hits_cfg = dict(video.get('hits_cfg') or {})
    hits = [dict(h) for h in (video.get('hits') or [])]
    if not hits and video.get('hits_at'):
        hits = [dict(t_s=float(t), kind='cut') for t in video['hits_at']]
    out = []
    duration = float(video.get('duration_s') or 0.0)
    if duration > 0:
        picture = float(video.get('picture_duration_s') or duration)
        R.duration_row({'source': {'duration_s': picture}}, duration, gate_cfg, out)
    R.cut_sync_row(video.get('cuts') or [], hits, gate_cfg, out)
    R.motion_sync_row(video.get('motion_beats') or [], hits,
                      dict(gate_cfg, motion_sync=gate_cfg.get('motion_sync') or {'window_ms': 150.0}), out)
    R.hit_class_row(hits, dict(hits_cfg, classes=hits_cfg.get('classes') or {}), out)
    R.hit_density_row(hits, video.get('cuts') or [], duration,
                      dict(hits_cfg, density=hits_cfg.get('density') or {}), out)
    R.grid_phase_row(video.get('cut_phase') or {}, gate_cfg, out)
    R.shot_scale_row(score.get('sections') or video.get('sections') or [],
                     video.get('scenes') or [], gate_cfg, out)
    return out
