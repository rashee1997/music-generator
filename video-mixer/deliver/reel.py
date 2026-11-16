# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

#!/usr/bin/env python3
"""reel.py - place certified cues on a reel, then deliver the reel once.

    python3 video-mixer/deliver/reel.py <film> --reel 1
    python3 video-mixer/deliver/reel.py <film> --reel 1 --mux

What it does, in order:

  plan      read spotting/cuesheet.json: which cue, where it starts, how long
  place     load each cue's certified master, resample to the delivery rate, trim or
            pad it to the cue's own length, fade its edges, and add it at its start
  report    cue starts, lengths, gaps and overlaps; an overlap is a fact, not a fix
  verdict   the reel's status is the aggregate of its cues' verdicts and its own rows
  mux       optional: put the reel program on the picture, video stream copied

It never re-scores, never re-times and never rewrites a cue's report.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.abspath(os.path.join(HERE, '..'))
SKILL = os.path.abspath(os.path.join(VIDEO, '..'))
for p in (VIDEO, os.path.join(SKILL, 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULTS = dict(sample_rate=48000, fade_in_s=0.02, fade_out_s=0.05, cue_gain_db=0.0)


def load_cuesheet(film_dir):
    path = os.path.join(film_dir, 'spotting', 'cuesheet.json')
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    cues = data.get('cues') or []
    if not cues:
        raise ValueError(f'{path}: no cues listed')
    return data


def planned_placements(cuesheet, reel=None):
    """[{id, start_s, end_s, length_s, wav, purpose}] for one reel, or every cue when reel is None."""
    out = []
    for c in cuesheet.get('cues') or []:
        if reel is not None and c.get('reel') not in (None, reel):
            continue
        start = float(c.get('in_s') or 0.0)
        end = c.get('out_s')
        length = c.get('duration_s')
        if length is None and end is not None:
            length = float(end) - start
        if length is None:
            raise ValueError(f'cue {c.get("id")}: needs duration_s or out_s')
        out.append(dict(id=str(c.get('id')), start_s=start, end_s=start + float(length),
                        length_s=float(length), wav=c.get('master') or c.get('wav'),
                        title=c.get('title'), purpose=c.get('purpose'),
                        silence=bool(c.get('silence')), reel=c.get('reel')))
    out.sort(key=lambda p: p['start_s'])
    return out


def _load(path, sr):
    import soundfile as sf
    from scipy import signal
    y, s = sf.read(path, always_2d=True)
    y = y.astype(np.float32)
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    elif y.shape[1] > 2:
        y = y[:, :2]
    if int(s) != int(sr):
        y = signal.resample_poly(y, int(sr), int(s), axis=0).astype(np.float32)
    return y


def _fit(y, n):
    if len(y) >= n:
        return y[:n]
    return np.pad(y, ((0, n - len(y)), (0, 0)))


def assemble(cuesheet, film_dir, duration_s, cfg=None, reel=None):
    """(audio, report). A silent cue is a gap, not a mistake: silence is a cue."""
    cfg = dict(DEFAULTS, **(cfg or {}))
    sr = int(cfg['sample_rate'])
    n = int(round(float(duration_s) * sr))
    if n <= 0:
        raise ValueError(f'duration_s must be positive, got {duration_s}')
    audio = np.zeros((n, 2), np.float32)
    rows = []
    for p in planned_placements(cuesheet, reel):
        row = dict(id=p['id'], start_s=round(p['start_s'], 3), end_s=round(p['end_s'], 3),
                   length_s=round(p['length_s'], 3), silence=p['silence'])
        if p['silence']:
            row.update(placed=False, note='spotting marked this cue silent: the reel keeps the gap')
            rows.append(row)
            continue
        wav = p['wav']
        if not wav:
            row.update(placed=False, note='no master named for this cue')
            rows.append(row)
            continue
        path = wav if os.path.isabs(wav) else os.path.join(film_dir, wav)
        if not os.path.exists(path):
            row.update(placed=False, note=f'master not found: {path}')
            rows.append(row)
            continue
        cue_n = int(round(p['length_s'] * sr))
        y = _fit(_load(path, sr), cue_n)
        fi, fo = int(float(cfg['fade_in_s']) * sr), int(float(cfg['fade_out_s']) * sr)
        if fi > 0:
            y[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)[:, None]
        if fo > 0:
            y[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)[:, None]
        y = y * 10 ** (float(cfg['cue_gain_db']) / 20.0)
        i = int(round(p['start_s'] * sr))
        j = min(n, i + len(y))
        if i >= n:
            row.update(placed=False, note='cue starts past the end of the reel')
            rows.append(row)
            continue
        audio[i:j] += y[:j - i]
        row.update(placed=True, samples=j - i, source=os.path.relpath(path, film_dir).replace('\\', '/'))
        rows.append(row)
    overlaps = []
    for a, b in zip(rows, rows[1:]):
        if a.get('placed') and b.get('placed') and float(b['start_s']) < float(a['end_s']) - 1e-6:
            overlaps.append((a['id'], b['id'], round(float(a['end_s']) - float(b['start_s']), 3)))
    report = dict(duration_s=round(float(duration_s), 3), sample_rate=sr, cues=rows,
                  overlaps=[dict(a=a, b=b, overlap_s=s) for a, b, s in overlaps],
                  placed=sum(1 for r in report_rows_placed(rows) if r),
                  note='a cue is placed at its own start and trimmed to its own length; the reel never re-times one')
    return audio, report


def report_rows_placed(rows):
    return [r.get('placed') for r in rows]


def reel_rows(report, cfg=None):
    """The reel's own gate rows: length, placement, overlap. Shape matches the gate's (level, name, detail)."""
    out = []
    cues = report.get('cues') or []
    missing = [c for c in cues if not c.get('placed') and not c.get('silence')]
    level = 'FAIL' if missing else 'PASS'
    out.append((level, 'reel.placement',
                f'{len(cues) - len(missing)} of {len(cues)} cues placed'
                + (f'; {len(missing)} missing: {", ".join(c["id"] for c in missing[:4])}' if missing else '')))
    ov = report.get('overlaps') or []
    out.append(('FAIL' if ov else 'PASS', 'reel.overlap',
                f'{len(ov)} overlapping cue pairs' + (f'; first {ov[0]}' if ov else '')))
    past = [c for c in cues if float(c.get('end_s') or 0.0) > float(report.get('duration_s') or 0.0) + 1e-6]
    out.append(('FAIL' if past else 'PASS', 'reel.length',
                f'{len(past)} cues run past the reel end (reel {report.get("duration_s")}s)'))
    silent = sum(1 for c in cues if c.get('silence'))
    out.append(('INFO', 'reel.silence', f'{silent} cues are deliberate silence'))
    return out


def reel_verdict(cue_reports, rows):
    """Aggregate. A reel is certified only when every cue was and its own rows pass."""
    cue_fails = sum(int((r.get('ci_summary') or {}).get('fail', 0)) for r in cue_reports or [])
    cue_uncertified = [r.get('title') or r.get('cue') for r in cue_reports or []
                       if str(r.get('status')) != 'PASSED']
    own_fails = sum(1 for lvl, _, _ in rows if lvl == 'FAIL')
    fails = cue_fails + own_fails
    return dict(status='PASSED' if fails == 0 else 'FAILED', cue_fails=cue_fails,
                reel_fails=own_fails, uncertified_cues=cue_uncertified,
                cues=len(cue_reports or []),
                summary={'pass': sum(1 for lvl, _, _ in rows if lvl == 'PASS'),
                         'warn': sum(1 for lvl, _, _ in rows if lvl == 'WARN'),
                         'fail': own_fails})


def write_reel(film_dir, reel_id, program, report, verdict, out_wav=None):
    import soundfile as sf
    out_dir = os.path.join(film_dir, 'deliver')
    os.makedirs(out_dir, exist_ok=True)
    wav = out_wav or os.path.join(out_dir, f'reel_{reel_id}_program.wav')
    sf.write(wav, program, int(report['sample_rate']), subtype='PCM_24')
    rep = dict(reel=reel_id, program=os.path.relpath(wav, film_dir).replace('\\', '/'),
               placement=report, verdict=verdict)
    with open(os.path.join(out_dir, f'reel_{reel_id}_report.json'), 'w', encoding='utf-8') as fh:
        json.dump(rep, fh, indent=2)
    return wav, rep


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('film')
    ap.add_argument('--reel', default='1')
    ap.add_argument('--duration', type=float, default=None, help='reel length in seconds (default: film.json or the last cue)')
    ap.add_argument('--mux', action='store_true', help='also mux the reel onto the picture')
    ap.add_argument('--video', default=None)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    film_dir = os.path.abspath(a.film)
    with open(os.path.join(film_dir, 'film.json'), encoding='utf-8') as fh:
        film = json.load(fh)
    duration = a.duration or film.get('duration_s')
    sheet = load_cuesheet(film_dir)
    if duration is None:
        duration = max(p['end_s'] for p in planned_placements(sheet, a.reel))
    audio, report = assemble(sheet, film_dir, duration, film.get('delivery') or {}, reel=a.reel)
    rows = reel_rows(report)
    verdict = reel_verdict([], rows)
    wav, rep = write_reel(film_dir, a.reel, audio, report, verdict, a.out)
    for lvl, name, detail in rows:
        print(f'[{lvl:4s}] {name:20s} {detail}')
    print(f'  {wav}')
    print(f'  reel {a.reel}: {verdict["status"]}')
    if a.mux:
        import presets
        import video_mux
        presets.add_project(film_dir)
        delivery = presets.get('film', 'delivery')['mux']
        out = os.path.join(film_dir, 'deliver', f'reel_{a.reel}_final.{delivery.get("container", "mp4")}')
        video = a.video or film.get('video')
        if not video:
            print('  no picture named: pass --video or set video in film.json')
            return 2
        video_mux.mux(video, wav, out, delivery, verbose=True)
        print(f'  {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
