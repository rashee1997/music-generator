# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

#!/usr/bin/env python3
"""video_score.py - score a picture end to end: probe, direct, render, program-mix, mux, gate.

    python3 scripts/video_score.py --video clips/source.mp4 --project <project> --brief "calm documentary"
    python3 scripts/video_score.py --selftest

This is the only video file in `scripts/`. Everything it calls lives in `video-mixer/`:

  video_probe.py        picture -> reports/video_probe.json
  video_direction.py    probe   -> direction sheet, hit list, score
  video_program_mix.py  music + voice -> out/program.wav
  video_mux.py          picture + program -> out/final.mp4, video stream proven identical
  video_gate.py         four delivery rows appended to reports/ci_report.json

The music itself is rendered by the normal engine (`pipeline.py`), unchanged, so every music rule still applies.
Numbers come from `references/data/presets/video/<name>.json`, deep-merged with `<project>/presets/video/<name>.json`.
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
import video_gate         # noqa: E402


def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_') or 'video'


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
    project, not to the skill. Numbers stay in the video preset; only the file is written here.
    """
    d = os.path.join(project, 'presets', kind)
    path = os.path.join(d, f'{slug(spec["name"])}.json')
    if not os.path.exists(path):
        os.makedirs(d, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(spec, fh, indent=2)
    return spec['name']


def run(video, project, title=None, brief='', preset='default', profile=None, out=None, verbose=True):
    """The whole job. Returns (report dict, exit code)."""
    project = os.path.abspath(project)
    cfg = presets.get('video', preset)
    cfg['name'] = preset
    ensure_preset(project, 'spaces', cfg['staging']['space'])
    ensure_preset(project, 'mix', cfg['mix_preset'])
    presets.add_project(project)
    name = title or os.path.splitext(os.path.basename(video))[0]
    s = slug(name)
    reports = os.path.join(project, 'reports')
    out_dir = os.path.join(project, 'out')
    for d in (reports, out_dir, os.path.join(project, 'scores'), os.path.join(project, 'direction')):
        os.makedirs(d, exist_ok=True)

    if verbose:
        print('=' * 78)
        print(f'  VIDEO SCORE: {name}')
        print('=' * 78)

    probe_rep = video_probe.probe(video, cfg, verbose=verbose)
    probe_path = os.path.join(reports, 'video_probe.json')
    with open(probe_path, 'w', encoding='utf-8') as fh:
        json.dump(probe_rep, fh, indent=2)

    sheet = video_direction.direction_sheet(probe_rep, cfg, brief, title=name)
    video_direction.write_direction(sheet, os.path.join(project, 'direction', 'direction_sheet.json'))
    video_direction.write_direction(sheet, os.path.join(project, 'direction', f'video_{s}.json'))
    score = video_direction.score_from_sheet(sheet, cfg, probe_rep)
    score_path = os.path.join(project, 'scores', f'{s}_score.json')
    with open(score_path, 'w', encoding='utf-8') as fh:
        json.dump(score, fh, indent=2)
    if verbose:
        print(f"  direction: {sheet['tempo_bpm']:.0f} bpm, {sheet['key']} {sheet['mode']}, "
              f"{len(sheet['hits_at'])} hits -> {os.path.relpath(score_path, project)}")

    import pipeline
    master_wav = os.path.join(out_dir, 'master.wav')
    ci_path = os.path.join(reports, 'ci_report.json')
    report = pipeline.MusicPipeline(verbose=verbose).execute(score_path, project=project, out_wav=master_wav,
                                                             json_report=ci_path)

    hits = sheet['hits']
    dialogue = extract_dialogue(video, os.path.join(out_dir, 'dialogue.wav')) if probe_rep['source']['has_audio'] else None
    prof = video_program_mix.master_profile(cfg, profile)
    picture_s = float(probe_rep['source']['duration_s'])
    if dialogue:
        voice = video_program_mix.load(dialogue)
        music = video_program_mix.load(master_wav)
        mix, _, _, _, mix_rep = video_program_mix.build(voice, music, [], cfg['mix'],
                                                        hit_times=sheet['hits_at'], limit_s=picture_s)
    else:
        mix = video_program_mix.load(master_wav)[:int(round(picture_s * video_program_mix.SR))]
        mix_rep = dict(note='no audio in the source: the cue plays alone')
    program, sr = video_program_mix.master(mix, prof)
    import soundfile as sf
    program_wav = os.path.join(out_dir, 'program.wav')
    sf.write(program_wav, program, sr, subtype='PCM_24')
    if verbose:
        print(f'  program: {os.path.relpath(program_wav, project)}  {len(program) / sr:.2f}s @ {sr} Hz')

    container = (out or os.path.join(out_dir, f'final.{cfg["mux"].get("container", "mp4")}'))
    mux_rep = video_mux.mux(video, program_wav, container, cfg['mux'], verbose=verbose)

    offsets = []
    video_block = dict(preset=preset, source=probe_rep['source'], probe=os.path.relpath(probe_path, project),
                       direction=os.path.relpath(os.path.join(project, 'direction', f'video_{s}.json'), project),
                       score=os.path.relpath(score_path, project), hits_at=sheet['hits_at'],
                       tempo_bpm=sheet['tempo_bpm'], tempo_method=sheet['tempo_method'],
                       mix=mix_rep, mux=mux_rep, program=os.path.relpath(program_wav, project),
                       master_profile=prof, cut_source=probe_rep['cut_source'])
    rows_out, offsets = video_gate.rows(probe_rep, program_wav, mix_rep, prof, cfg['gate'], hits=hits)
    video_block['cut_sync'] = [dict(hit_s=round(t, 4), cut_s=round(c, 4), offset_ms=round(o, 1)) for t, c, o in offsets]
    video_block['master'] = dict(lufs=video_block['master_profile']['lufs'],
                                 true_peak_db=video_block['master_profile']['true_peak_db'],
                                 loudness_mode=video_block['master_profile']['loudness_mode'])
    if os.path.exists(ci_path):
        video_gate.attach(ci_path, video_block, rows_out)

    fails = sum(1 for l, _, _ in rows_out if l == 'FAIL')
    music_fails = int((report.get('ci_summary') or {}).get('fail', 0))
    ok = fails == 0 and music_fails == 0 and report.get('status') == 'PASSED'
    verdict = 'CERTIFIED' if ok else f'NOT CERTIFIED (video {fails} FAIL, music {music_fails} FAIL)'
    print('\n  --- VIDEO SCOREBOARD ---')
    for lvl, n, d in rows_out:
        print(f'  [{lvl:4s}] {n:24s} {d}')
    print(f'\n  {container}')
    print(f'  {verdict}')
    return dict(report=report, video=video_block, rows=rows_out, out=container)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--video')
    ap.add_argument('--project')
    ap.add_argument('--title')
    ap.add_argument('--brief', default='')
    ap.add_argument('--preset', default='default')
    ap.add_argument('--profile', default=None, help='streaming | broadcast | cinema (default: the preset)')
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
    fails = sum(1 for l, _, _ in res['rows'] if l == 'FAIL')
    sys.exit(0 if fails == 0 and res['report'].get('status') == 'PASSED' else 1)


if __name__ == '__main__':
    main()
