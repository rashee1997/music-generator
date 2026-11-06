# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""context.py - the reel read at three timescales.

    python3 video-mixer/context.py reports/video_probe.json --project <film> --out analysis/reel_1_context.json

The picture is not a handful of scalars. It is read at three timescales, each
of which answers a different musical question:

    reel          seconds to minutes   what kind of film is this (palette, speech share, motion profile)
    scene         2-40 s               what is this shot (scale, motion, speech, energy)
    motion beat   per frame window     where does the picture itself pulse

Everything here is a measurement. What the music does with it lives in
`film/mapping.json` and in the direction stage; none of it is decided here.

The beat grid is fitted twice: tempo from the median cut interval (as before)
and a *phase* with the residual, so "on the grid but 40 ms late" is a different
finding from "on no grid at all".
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
for p in (HERE, os.path.join(SKILL, 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

from analysis import shot_scale as shot_scale_mod      # noqa: E402

PHASE_STEPS = 64


def cut_phase(cuts, bpm, fps=0.0, cfg=None):
    """Fit a beat grid to every cut and report how far off the grid they sit.

    Two-stage search: a coarse sweep over one period, then a refinement around
    the best offset. The cost is the mean squared normalised distance to the
    nearest grid line, so a cut 3 % of a beat off costs less than one 40 % off.

    Returns {'bpm', 'offset_s', 'confidence', 'worst_residual_ms', 'mean_residual_ms',
             'residuals_ms', 'cuts', 'period_s'}.
    """
    cuts = sorted(float(c) for c in cuts or [])
    period = 60.0 / float(bpm) if bpm else 0.0
    out = dict(bpm=round(float(bpm), 4) if bpm else 0.0, offset_s=0.0, confidence=0.0,
               worst_residual_ms=0.0, mean_residual_ms=0.0, residuals_ms=[], cuts=len(cuts),
               period_s=round(period, 6), tolerance_frames=None)
    if len(cuts) < 2 or period <= 0:
        out['confidence'] = 0.0
        return out

    def cost_at(offset):
        r = np.array([((c - offset) % period) / period for c in cuts], dtype=np.float64)
        d = np.minimum(r, 1.0 - r)
        return float(np.mean(d * d)), d

    best = None
    for k in range(PHASE_STEPS):
        off = period * k / PHASE_STEPS
        c, d = cost_at(off)
        if best is None or c < best[0]:
            best = (c, off, d)
    step = period / (PHASE_STEPS * 4.0)
    for k in range(-8, 9):
        off = (best[1] + k * step) % period
        c, d = cost_at(off)
        if c < best[0]:
            best = (c, off, d)
    _, offset, d = best
    residuals = d * period
    out.update(offset_s=round(float(offset), 6),
               confidence=round(float(max(0.0, 1.0 - 2.0 * float(np.median(d)))), 4),
               worst_residual_ms=round(float(np.max(residuals)) * 1000.0, 2),
               mean_residual_ms=round(float(np.mean(residuals)) * 1000.0, 2),
               residuals_ms=[round(float(x) * 1000.0, 2) for x in residuals])
    if fps:
        out['tolerance_frames'] = round(float(np.max(residuals)) * float(fps), 3)
    return out


def shots_from_cuts(cuts, duration_s):
    """[(start, end)] for every shot, including the first and last."""
    cuts = [float(c) for c in cuts or [] if 0 < float(c) < float(duration_s)]
    edges = [0.0] + sorted(cuts) + [float(duration_s)]
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] > edges[i]]


def _shot_motion(a, b, motion_hits):
    """How hard this shot moves, 0..1-ish: the mean strength of the movement peaks inside it."""
    inside = [float(h.get('strength', 0.0)) for h in motion_hits or []
              if a <= float(h.get('t', -1.0)) < b]
    if not inside:
        return 0.0
    return float(np.clip(np.mean(inside) * 10.0, 0.0, 1.0))


def _shot_dir(a, b, motion_hits, default='static'):
    votes = {}
    for h in motion_hits or []:
        if a <= float(h.get('t', -1.0)) < b and h.get('dir'):
            votes[h['dir']] = votes.get(h['dir'], 0) + 1
    if not votes:
        return default
    return sorted(votes.items(), key=lambda kv: -kv[1])[0][0]


def group_scenes(shots, motion_hits, cfg):
    """Group shots into scenes.

    A scene ends when its current length reaches `max_scene_s`, or when the
    previous shot was long enough to read as a take of its own (`long_shot_s`),
    or when the motion jumps by `motion_delta` between shots. Every boundary
    rule is a preset key.
    """
    grp = cfg.get('scene_grouping') or {}
    long_shot = float(grp.get('long_shot_s', 8.0))
    delta = float(grp.get('motion_delta', 0.35))
    max_scene = float(grp.get('max_scene_s', 40.0))
    scenes, cur, prev_dur = [], None, 0.0
    for a, b in shots:
        dur = b - a
        motion = _shot_motion(a, b, motion_hits)
        start_new = cur is None
        if cur is not None:
            if prev_dur >= long_shot:
                start_new = True
            elif abs(motion - cur['motion']) >= delta:
                start_new = True
            elif (b - cur['start_s']) >= max_scene:
                start_new = True
        if start_new:
            if cur is not None:
                scenes.append(cur)
            cur = dict(start_s=float(a), end_s=float(b), shots=1, motion=motion,
                       motion_dir=_shot_dir(a, b, motion_hits))
        else:
            cur['end_s'] = float(b)
            cur['shots'] += 1
            cur['motion'] = round((cur['motion'] * (cur['shots'] - 1) + motion) / cur['shots'], 4)
            d = _shot_dir(a, b, motion_hits)
            if cur['motion_dir'] == 'static' and d != 'static':
                cur['motion_dir'] = d
        prev_dur = dur
    if cur is not None:
        scenes.append(cur)
    peak = max((s['motion'] for s in scenes), default=0.0) or 1.0
    for i, s in enumerate(scenes):
        s['id'] = i + 1
        s['shots'] = int(s['shots'])
        s['start_s'] = round(s['start_s'], 3)
        s['end_s'] = round(s['end_s'], 3)
        s['motion'] = round(float(s['motion']), 4)
        s['energy'] = round(float(s['motion']) / peak, 4)
        s['shot_scale'] = 'medium'
        s['scale_source'] = 'not sampled'
        s['speech_activity'] = 0.0
        s['music_gap'] = False
    return scenes


def speech_per_scene(scenes, speech):
    """Fill each scene's `speech_activity` from the measured mask."""
    if not speech or not len(speech.get('times', [])):
        return scenes
    times = np.asarray(speech['times'], np.float64)
    mask = np.asarray(speech['mask'], np.float64)
    for s in scenes:
        sel = (times >= s['start_s']) & (times < s['end_s'])
        s['speech_activity'] = round(float(mask[sel].mean()) if sel.any() else 0.0, 4)
    return scenes


def _motion_profile(motion_mean):
    if motion_mean < 0.02:
        return 'static'
    if motion_mean < 0.06:
        return 'slow'
    if motion_mean < 0.14:
        return 'steady'
    return 'fast'


def build(probe, cfg_analysis, cfg_mapping=None, frames_by_scene=None, speech=None, bpm=None):
    """The whole context for one reel. `probe` is video_probe.probe()'s report."""
    src = probe.get('source') or {}
    duration = float(src.get('duration_s') or 0.0)
    fps = float(src.get('fps') or 0.0)
    cuts = [float(c['t']) for c in probe.get('cuts') or []]
    motion_hits = probe.get('motion_hits') or []
    shots = shots_from_cuts(cuts, duration)
    cfg_analysis = cfg_analysis or {}

    if bpm is None:
        import video_direction                      # local: video_direction imports this module lazily
        tc = (cfg_mapping or {}).get('tempo_from_cuts') or \
            (cfg_analysis.get('direction_map') or {}).get('tempo_from_cuts') or {}
        try:
            bpm = video_direction.tempo_from_cuts(cuts, {'tempo_from_cuts': tc}, fps)['bpm']
        except Exception:
            bpm = 120.0

    scenes = group_scenes(shots, motion_hits, cfg_analysis)
    speech_per_scene(scenes, speech)

    if frames_by_scene:
        for s in scenes:
            frames = frames_by_scene.get(s['id']) or []
            if frames:
                sc = shot_scale_mod.scene_scale(frames, cfg_analysis)
                s.update(shot_scale=sc['scale'], scale_share=sc['share'], scale_source=sc['scale_source'])
            else:
                s['scale_source'] = 'no frame sampled'

    luma = float(probe.get('luma_mean') or 0.0)
    warmth = float(probe.get('warmth_mean') or 0.0)
    reel = dict(
        duration_s=round(duration, 3), fps=round(fps, 4),
        shots=len(shots), scenes=len(scenes), cuts=len(cuts),
        mean_luma=round(luma, 4),
        luma_range=[round(float(probe.get('luma_min', luma)), 4), round(float(probe.get('luma_max', luma)), 4)],
        warmth_mean=round(warmth, 4),
        motion_mean=round(float(probe.get('motion_mean') or 0.0), 5),
        motion_profile=_motion_profile(float(probe.get('motion_mean') or 0.0)),
        palette=dict(temperature='warm' if warmth > 0.02 else ('cool' if warmth < -0.02 else 'neutral'),
                     warmth=round(warmth, 4)),
        text_on_screen=None,
        text_note='not measured: no text detector runs, so nothing claims there is or is not text on screen',
        speech_share=round(float((speech or {}).get('share') or 0.0), 4),
        has_audio=bool(src.get('has_audio')),
        cut_source=probe.get('cut_source'),
    )
    return dict(
        version=1,
        source=os.path.abspath(probe.get('path') or ''),
        reel=reel,
        shots=[dict(start_s=round(a, 3), end_s=round(b, 3)) for a, b in shots],
        scenes=scenes,
        motion_beats=[dict(t=round(float(h.get('t', 0.0)), 4),
                           strength=round(float(h.get('strength', 0.0)), 5),
                           dir=h.get('dir') or 'static', kind='peak')
                      for h in motion_hits],
        cut_phase=cut_phase(cuts, bpm, fps, cfg_analysis),
        silence_windows=silence_windows(scenes),
        speech=dict(share=round(float((speech or {}).get('share') or 0.0), 4),
                    segments=[list(s) for s in (speech or {}).get('segments') or []],
                    per_second=(speech or {}).get('per_second') or [],
                    measured=bool(speech)),
        bpm_hint=round(float(bpm), 4),
        preset_source=cfg_analysis.get('_source'),
    )


def silence_windows(scenes):
    """[(start_s, end_s)] the spotting marked as no music.

    Accepts the scene list or the whole context, so a caller holding either artifact
    does not have to know which shape this takes.
    """
    if isinstance(scenes, dict):
        scenes = scenes.get('scenes') or []
    return [(float(s['start_s']), float(s['end_s'])) for s in scenes or [] if s.get('music_gap')]


def write(context, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(context, fh, indent=2)
    return path


def load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def scene_of(context, t_s):
    """The scene covering `t_s`, or None."""
    for s in (context or {}).get('scenes') or []:
        if float(s['start_s']) <= float(t_s) < float(s['end_s']):
            return s
    return None


def main():
    import argparse
    import presets
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('probe')
    ap.add_argument('--project')
    ap.add_argument('--audio', default=None, help='the picture extracted to wav, for the speech mask')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    cfg_a = presets.get('film', 'analysis')
    cfg_m = presets.get('film', 'mapping')
    with open(a.probe, encoding='utf-8') as fh:
        probe = json.load(fh)
    speech = None
    if a.audio:
        import soundfile as sf
        from analysis import speech as speech_mod
        y, sr = sf.read(a.audio, always_2d=True)
        speech = speech_mod.activity(y, sr, cfg_a)
    ctx = build(probe, cfg_a, cfg_m, speech=speech)
    if a.out:
        write(ctx, a.out)
        print(f'  wrote {a.out}')
    print(json.dumps({k: ctx['reel'][k] for k in ('duration_s', 'shots', 'scenes', 'motion_profile', 'speech_share')}, indent=2))


if __name__ == '__main__':
    main()
