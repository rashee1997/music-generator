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
    """Picture rows that need only the score. Never raises: a failure becomes a WARN row.

    The rows themselves are `gate.pass_.probe_rows` (one definition, not a copy here); this adds the one row that
    needs two lengths: the score's own, against the picture's as probed. Without both, the row says so instead
    of comparing a number with itself.
    """
    try:
        from gate import rows as R
        from gate import pass_ as P
    except Exception as exc:                       # video-mixer missing: say so, do not pass
        return [('WARN', 'video.gate', f'video-mixer is not importable: {exc}')]
    video = score.get('video') or {}
    out = []
    try:
        picture, own = video.get('picture_duration_s'), video.get('score_duration_s')
        gate_cfg = dict(video.get('gate_cfg') or {})
        if picture is None or own is None:
            out.append(('INFO', 'video.duration_lock',
                        'not measured: the score carries no independent picture length and score length '
                        f'(picture_duration_s={picture}, score_duration_s={own})'))
        else:
            R.duration_row({'source': {'duration_s': float(picture)}}, float(own), gate_cfg, out)
        P.probe_rows(score, out)
    except Exception as exc:
        out.append(('WARN', 'video.gate', f'picture rows did not run: {type(exc).__name__}: {exc}'))
    return out
