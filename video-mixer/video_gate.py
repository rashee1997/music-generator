# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

#!/usr/bin/env python3
"""video_gate.py - compatibility surface for the picture rows.

The rows themselves live in `video-mixer/gate/`, and they run **inside**
certification: `pipeline.stage6_ci_quality_suite` calls `gate.pass_rows()` with
the program, in the same list as every music row. This module keeps the older
per-row entry points working (tests, tools, one-off checks) and nothing more.

There is deliberately no `attach()`: rewriting a report that has already been
certified is what made the video gate an appendage instead of a gate.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
for p in (HERE, os.path.join(SKILL, 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

from gate import rows as _rows                                   # noqa: E402
from gate.rows import (cut_sync_row, cue_silence_row, dialogue_band_row, dialogue_row,  # noqa: E402,F401
                       duration_row, gating_mode_row, grid_phase_row, hit_class_row,
                       hit_density_row, master_row, motion_sync_row, shot_scale_row)


def cut_sync_rows(probe, hits, cfg, out):
    """Legacy name and signature: a probe report plus hits. Returns the offsets."""
    return _rows.cut_sync_row(probe.get('cuts') or [], hits, cfg, out)


def rows(probe, program_wav, mix_report, profile, cfg, hits=None, out=None):
    """All picture rows for one program. `cfg` is the delivery preset's `gate` block.

    Returns (rows, offsets). Kept for tools that call the gate directly; the
    pipeline path uses `gate.pass_rows()` so the row list is never hand-copied.
    """
    out = [] if out is None else out
    import soundfile as sf
    y, sr = sf.read(program_wav, always_2d=True)
    duration_row(probe, len(y) / float(sr), cfg, out)
    offsets = cut_sync_rows(probe, hits or [], cfg, out)
    dialogue_row(mix_report or {}, probe, cfg, out)
    dialogue_band_row(mix_report or {}, probe, cfg, out)
    master_row(program_wav, profile, cfg, out, sr=sr)
    return out, offsets


def main():
    import argparse
    import json
    import presets
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--probe', required=True)
    ap.add_argument('--program', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--preset', default='default')
    ap.add_argument('--project')
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    cfg = presets.get('video', a.preset)
    with open(a.probe, encoding='utf-8') as fh:
        probe = json.load(fh)
    with open(a.report, encoding='utf-8') as fh:
        rep = json.load(fh)
    block = rep.get('video', {})
    hits = ([dict(t_s=float(h['t']), kind=h.get('kind', 'cut')) for h in block['hits']]
            if block.get('hits') else [dict(t_s=float(t)) for t in block.get('hits_at', [])])
    rows_out, _ = rows(probe, a.program, block.get('mix', {}),
                       cfg['master_profiles'][cfg['master']['profile']], cfg['gate'], hits=hits)
    for lvl, name, detail in rows_out:
        print(f'[{lvl:4s}] {name:24s} {detail}')


if __name__ == '__main__':
    main()
