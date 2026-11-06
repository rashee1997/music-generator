# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

#!/usr/bin/env python3
"""video_score.py - score a picture end to end: probe, context, direct, render, program, certify, mux.

    python3 scripts/video_score.py --video clips/source.mp4 --project <project> --brief "calm documentary"
    python3 scripts/video_score.py --selftest

The picture is read at three timescales (`video-mixer/context.py`), the direction comes from
the film presets, and the music is rendered by the normal engine unchanged. The picture rows
run **inside** the certification (`pipeline.stage6`), so a cue has one verdict and one author:

  video_probe.py        picture -> reports/video_probe.json
  context.py            probe + speech -> analysis/reel_<id>_context.json
  video_direction.py    context -> direction sheet, hit list, score
  video_program_mix.py  music + voice -> out/program.wav, mastered in the declared gating mode
  gate/pass_.py         every picture row, in the pipeline's own row list
  video_mux.py          picture + program -> out/final.mp4, video stream proven identical

Numbers come from `references/data/presets/film/*.json` (deep-merged with the project's own
copies) plus the one-cue `video` preset that still supplies the room and the mix preset.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
VIDEO = os.path.join(SKILL, 'video-mixer')
for p in (HERE, VIDEO):
    if p not in sys.path:
        sys.path.insert(0, p)

import presets            # noqa: E402
import video_probe        # noqa: E402
import video_direction    # noqa: E402
import video_program_mix  # noqa: E402
import video_mux          # noqa: E402
import context as context_mod        # noqa: E402
from analysis import speech as speech_mod   # noqa: E402
from gate import pass_rows as gate_pass_rows   # noqa: E402

FILM_PRESETS = ('analysis', 'mapping', 'hits', 'dialogue', 'delivery')


def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_') or 'video'


def film_config(project=None):
    """The five film presets, merged with the project layer. Missing ones are an error, not a default."""
    if project:
        presets.add_project(project)
    return {name: presets.get('film', name) for name in FILM_PRESETS}


def extract_dialogue(video, out_wav):
    """The picture's own audio, as a working track. Returns None when the container has no audio stream."""
    os.makedirs(os.path.dirname(os.path.abspath(out_wav)), exist_ok=True)
    p = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-nostdin', '-i', video, '-vn', '-ac', '2', '-ar', '44100', out_wav],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    if p.returncode != 0 or not os.path.exists(out_wav):
        return None
    return out_wav


def ensure_preset(project, kind, spec):
    """Write one of the video preset's own project presets (space, mix) if the project does not have it yet.

    The project gate refuses a shipped fallback, and the room and the balance a cue is heard through belong to the
    project, not to the skill. Numbers stay in the presets; only the file is written here.
    """
    d = os.path.join(project, 'presets', kind)
    path = os.path.join(d, f'{slug(spec["name"])}.json')
    if not os.path.exists(path):
        os.makedirs(d, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(spec, fh, indent=2)
    return spec['name']


def cue_config(preset='default', project=None):
    """The film presets plus the one-cue staging preset that still owns the room and the mix."""
    film = film_config(project)
    one = presets.get('video', preset)
    one['name'] = preset
    film['staging'] = one['staging']
    film['mix_preset'] = one['mix_preset']
    film['_one_cue'] = one
    return film


def run(video, project, title=None, brief='', preset='default', profile=None, out=None, verbose=True):
    """The whole job. Returns (report dict, exit code)."""
    project = os.path.abspath(project)
    cfg = cue_config(preset, project)
    analysis, mapping, hits_cfg = cfg['analysis'], cfg['mapping'], cfg['hits']
    dialogue_cfg, delivery = cfg['dialogue'], cfg['delivery']
    one = cfg['_one_cue']

    ensure_preset(project, 'spaces', one['staging']['space'])
    ensure_preset(project, 'mix', one['mix_preset'])
    presets.add_project(project)
    name = title or os.path.splitext(os.path.basename(video))[0]
    s = slug(name)
    reports = os.path.join(project, 'reports')
    out_dir = os.path.join(project, 'out')
    analysis_dir = os.path.join(project, 'analysis')
    for d in (reports, out_dir, os.path.join(project, 'scores'), os.path.join(project, 'direction'), analysis_dir):
        os.makedirs(d, exist_ok=True)

    if verbose:
        print('=' * 78)
        print(f'  VIDEO SCORE: {name}')
        print('=' * 78)

    probe_rep = video_probe.probe(video, analysis, verbose=verbose)
    probe_path = os.path.join(reports, 'video_probe.json')
    with open(probe_path, 'w', encoding='utf-8') as fh:
        json.dump(probe_rep, fh, indent=2)

    reel_id = 1
    dialogue_wav = (extract_dialogue(video, os.path.join(out_dir, 'dialogue.wav'))
                    if probe_rep['source']['has_audio'] else None)

    speech = None
    if dialogue_wav:
        import soundfile as sf
        vy, vsr = sf.read(dialogue_wav, always_2d=True)
        speech = speech_mod.activity(vy, vsr, analysis)
        if verbose:
            print(f"  speech: {speech['share'] * 100:.1f} % of the picture, {len(speech['segments'])} segments")

    ctx = context_mod.build(probe_rep, analysis, mapping, speech=speech)
    scenes = ctx['scenes']
    frames = {}
    if scenes and analysis.get('shot_scale', {}).get('enabled', True):
        frames = __import__('analysis.shot_scale', fromlist=['shot_scale']).sample_scene_frames(
            video, scenes, analysis)
        ctx = context_mod.build(probe_rep, analysis, mapping, frames_by_scene=frames, speech=speech)
        if verbose:
            scales = [sc['shot_scale'] for sc in ctx['scenes']]
            print(f'  context: {len(ctx["shots"])} shots in {len(scenes)} scenes, scales {scales}')
    with open(os.path.join(analysis_dir, f'reel_{reel_id}_context.json'), 'w', encoding='utf-8') as fh:
        json.dump(ctx, fh, indent=2)

    sheet = video_direction.direction_sheet(probe_rep, one, brief, title=name, context=ctx, film=cfg)
    sheet_path = os.path.join(project, 'direction', 'direction_sheet.json')
    video_direction.write_direction(sheet, sheet_path)
    score = video_direction.score_from_sheet(sheet, one, probe_rep, context=ctx, mapping=mapping)
    score['piece_type'] = score.get('piece_type') or 'video_dialogue'
    score_path = os.path.join(project, 'scores', f'{s}_score.json')
    with open(score_path, 'w', encoding='utf-8') as fh:
        json.dump(score, fh, indent=2)
    if verbose:
        print(f"  direction: {sheet['tempo_bpm']:.0f} bpm, {sheet['key']} {sheet['mode']}, "
              f"{len(sheet['hits_at'])} hits, {len(sheet.get('sections') or [])} sections -> "
              f"{os.path.relpath(score_path, project)}")

    prof = video_program_mix.master_profile(delivery, profile)
    picture_s = float(probe_rep['source']['duration_s'])
    program_wav = os.path.join(out_dir, 'program.wav')
    container = out or os.path.join(out_dir, f'final.{one["mux"].get("container", "mp4")}')
    programme = {}

    def programme_rows(score_now, master_wav, ci_rows):
        """Runs inside pipeline stage 6: build the program, then return the picture rows."""
        mix_rep, mask_lengths = {}, {}
        if dialogue_wav:
            voice = video_program_mix.load(dialogue_wav)
            if verbose:
                print(f"  voice: {'chain applied' if not dialogue_cfg.get('no_voice_chain') else 'raw'}")
            voice = video_program_mix.voice_chain(voice, dialogue_cfg)
            music = video_program_mix.load(master_wav)
            mask = speech_mod.mask_at(speech['mask'], speech['times'], len(voice), video_program_mix.SR) \
                if speech else None
            mix, _, _, d_mask, mix_rep = video_program_mix.build(
                voice, music, [], dialogue_cfg, hit_times=sheet['hits_at'], limit_s=picture_s)
            mask_for_master, mask_lengths = d_mask, dict(mask=len(d_mask))
        else:
            mix = video_program_mix.load(master_wav)[:int(round(picture_s * video_program_mix.SR))]
            mask_for_master = None
            mix_rep = dict(note='no audio in the source: the cue plays alone', speech_measured=False)
        program, sr = video_program_mix.master(mix, prof, loudness_mode=prof.get('loudness_mode'),
                                               speech_mask=mask_for_master)
        import soundfile as sf
        sf.write(program_wav, program, sr, subtype='PCM_24')
        if verbose:
            print(f'  program: {os.path.relpath(program_wav, project)}  {len(program) / sr:.2f}s @ {sr} Hz '
                  f'({prof.get("loudness_mode")})')
        mux_rep = video_mux.mux(video, program_wav, container, one['mux'], verbose=verbose)
        rows, extras = gate_pass_rows(score_now, context=ctx, probe=probe_rep, program_wav=program_wav,
                                      mix_report=mix_rep, gating=dict(delivery['gate'], **hits_cfg),
                                      master_profile=prof, hits=sheet['hits'])
        programme.update(dict(program=program_wav, mux=mux_rep, mix=mix_rep, extras=extras))
        block = dict(preset=preset, source=probe_rep['source'], reel=reel_id,
                     probe=os.path.relpath(probe_path, project),
                     context=os.path.relpath(os.path.join(analysis_dir, f'reel_{reel_id}_context.json'), project),
                     direction=os.path.relpath(sheet_path, project),
                     score=os.path.relpath(score_path, project),
                     hits_at=sheet['hits_at'], hits=sheet['hits'],
                     tempo_bpm=sheet['tempo_bpm'], tempo_method=sheet['tempo_method'],
                     cut_phase=ctx['cut_phase'], scenes=ctx['scenes'], reel_context=ctx['reel'],
                     mix=mix_rep, mux=mux_rep, program=os.path.relpath(program_wav, project),
                     master_profile=prof, cut_source=probe_rep['cut_source'],
                     cut_sync=[dict(hit_s=round(t, 4), cut_s=round(c, 4), offset_ms=round(o, 1))
                               for t, c, o in extras.get('cut_sync') or []],
                     motion_sync=[dict(hit_s=round(t, 4), beat_s=round(b, 4), offset_ms=round(o, 1))
                                  for t, b, o in extras.get('motion_sync') or []],
                     gating=dict(declared=prof.get('loudness_mode'), measured=extras.get('gating_mode'),
                                 full_program_lufs=extras.get('lufs'),
                                 dialogue_gated_lufs=extras.get('dialogue_lufs')),
                     master=dict(lufs=prof['lufs'], true_peak_db=prof['true_peak_db'],
                                 loudness_mode=prof['loudness_mode']))
        return rows, block

    import pipeline
    master_wav = os.path.join(out_dir, 'master.wav')
    ci_path = os.path.join(reports, 'ci_report.json')
    report = pipeline.MusicPipeline(verbose=verbose).execute(score_path, project=project, out_wav=master_wav,
                                                             json_report=ci_path, video_rows=programme_rows)

    rows_out = [(c['level'], c['check'], c['detail']) for c in report.get('ci_checks') or []
                if str(c['check']).startswith(('video.', 'reel.'))]
    fails = int((report.get('ci_summary') or {}).get('fail', 0))
    verdict = 'CERTIFIED' if fails == 0 and report.get('status') == 'PASSED' else f'NOT CERTIFIED ({fails} FAIL)'
    print('\n  --- VIDEO SCOREBOARD ---')
    for lvl, n, d in rows_out:
        print(f'  [{lvl:4s}] {n:24s} {d}')
    print(f'\n  {container}')
    print(f'  {verdict}')
    with open(os.path.join(reports, 'video_rows.json'), 'w', encoding='utf-8') as fh:
        json.dump(dict(rows=[dict(level=l, check=n, detail=d) for l, n, d in rows_out],
                       video=report.get('video'), programme={k: v for k, v in programme.items() if k != 'mix'}),
                  fh, indent=2)
    return dict(report=report, video=report.get('video') or {}, rows=rows_out, out=container)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--video')
    ap.add_argument('--project')
    ap.add_argument('--title')
    ap.add_argument('--brief', default='')
    ap.add_argument('--preset', default='default')
    ap.add_argument('--profile', default=None, help='streaming | broadcast | cinema | netflix | prime | youtube')
    ap.add_argument('--out', default=None)
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        import video_selftest
        sys.exit(0 if video_selftest.run() else 1)
    if not a.video or not a.project:
        ap.error('--video and --project are required (or use --selftest)')
    import cli_util
    cli_util.require_file(a.video, 'video file')
    cli_util.require_dir(a.project, 'project folder')
    res = run(a.video, a.project, a.title, a.brief, a.preset, a.profile, a.out, verbose=not a.quiet)
    sys.exit(0 if res['report'].get('status') == 'PASSED' else 1)


if __name__ == '__main__':
    main()
