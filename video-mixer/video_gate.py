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
"""video_gate.py - the four video rows: does the finished file keep the picture's time and the platform's level.

    python3 video-mixer/video_gate.py --probe reports/video_probe.json --program out/program.wav \
        --report reports/ci_report.json --preset default

Rows (limits from the video preset's "gate" block, registered in scripts/gate_profiles.py):

  video.duration_lock       program length against the picture                       (protected)
  video.cut_sync            every hit against its cut, early and late measured separately
  video.dialogue_snr        music level under speech while the voice is active
  video.master_compliance   delivered loudness and true peak against the master profile (protected)

Row shape is the gate's own: (level, name, detail). Nothing here decides whether a limit is right for the music;
that is the gate profile's job, with a written reason.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
for p in (HERE, os.path.join(SKILL, 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)


from quality_gate import _row   # one row shape for video and music rows


def duration_row(probe, program_s, cfg, out):
    tol = float(cfg['duration_tolerance_ms'])
    picture = float(probe['source']['duration_s'])
    delta_ms = (program_s - picture) * 1000.0
    level = 'PASS' if abs(delta_ms) <= tol else 'FAIL'
    _row(out, level, 'video.duration_lock',
         f'picture {picture:.3f}s, program {program_s:.3f}s -> {delta_ms:+.0f} ms (limit +/-{tol:.0f})')


def cut_sync_rows(probe, hits, cfg, out):
    """Offsets are signed as heard: negative = the hit arrives before the cut, positive = after it.

    Only hits derived from a cut are judged: a motion hit accents a movement inside a shot and has no edit to be
    late for, so judging it against the nearest cut would be measuring the wrong thing.
    """
    cs = cfg['cut_sync']
    cuts = [c['t'] for c in probe['cuts']]
    cut_hits = [h for h in hits if h.get('kind', 'cut') == 'cut']
    if not cut_hits:
        _row(out, 'PASS', 'video.cut_sync', f'no cut-derived hit ({len(hits)} motion hits only): nothing to sync')
        return []
    if not cuts:
        _row(out, 'PASS', 'video.cut_sync', 'no cut detected: hits are not tied to picture edits')
        return []
    offsets = []
    for h in cut_hits:
        t = float(h['t_s'] if 't_s' in h else h['t'])     # the sheet writes `t`, the gate report writes `t_s`
        nearest = min(cuts, key=lambda c: abs(c - t))
        offsets.append((t, nearest, (t - nearest) * 1000.0))
    worst = max(offsets, key=lambda o: abs(o[2]))
    bad = [o for o in offsets if o[2] < -float(cs['early_ms']) or o[2] > float(cs['late_ms'])]
    level = 'FAIL' if bad else ('WARN' if abs(worst[2]) > float(cs['aim_ms']) else 'PASS')
    detail = (f'{len(cut_hits)} cut hits on {len(cuts)} cuts: worst {worst[2]:+.0f} ms at {worst[0]:.3f}s '
              f'(early limit -{cs["early_ms"]:.0f}, late limit +{cs["late_ms"]:.0f}, aim +/-{cs["aim_ms"]:.0f})')
    if bad:
        detail += f'; {len(bad)} outside the limit'
    _row(out, level, 'video.cut_sync', detail)
    return offsets


def dialogue_row(mix_report, probe, cfg, out):
    if not probe['source'].get('has_audio'):
        _row(out, 'PASS', 'video.dialogue_snr', 'source has no audio: the cue plays alone, nothing to duck under')
        return
    value = mix_report.get('music_under_voice_db')
    if value is None:
        _row(out, 'WARN', 'video.dialogue_snr', 'no speech detected in the program: ducking was not exercised')
        return
    need = float(cfg['dialogue_snr_min_db'])
    level = 'PASS' if value >= need else 'FAIL'
    _row(out, level, 'video.dialogue_snr',
         f'music {value:.1f} dB under speech (need {need:.1f}) while the voice is active')


def master_row(program_wav, profile, cfg, out):
    import mixer as mx
    y, sr = sf.read(program_wav, always_2d=True)
    y = y.astype(np.float32)
    lufs, tp = float(mx.lufs(y, sr)), float(mx.true_peak_db(y, sr))
    tol = float(cfg['loudness_tolerance_lu'])
    dl = abs(lufs - float(profile['lufs']))
    peak_ok = tp <= float(profile['true_peak_db']) + 0.1
    level = 'PASS' if (dl <= tol and peak_ok) else 'FAIL'
    _row(out, level, 'video.master_compliance',
         f'{lufs:.1f} LUFS ({profile["loudness_mode"]}) vs {profile["lufs"]:.1f} +/-{tol:.1f}, '
         f'true peak {tp:.2f} dBTP vs {profile["true_peak_db"]:.2f}')


def rows(probe, program_wav, mix_report, profile, cfg, hits=None, out=None):
    """All four rows. `cfg` is the video preset's "gate" block; `profile` is the chosen master profile."""
    out = [] if out is None else out
    y, sr = sf.read(program_wav, always_2d=True)
    duration_row(probe, len(y) / float(sr), cfg, out)
    offsets = cut_sync_rows(probe, hits or [], cfg, out)
    dialogue_row(mix_report or {}, probe, cfg, out)
    master_row(program_wav, profile, cfg, out)
    return out, offsets


def attach(report_path, video_block, rows_out):
    """Append the video rows to the music CI report and rewrite it. Music rows are left exactly as they were."""
    with open(report_path, encoding='utf-8') as fh:
        rep = json.load(fh)
    existing = [c for c in rep.get('ci_checks', []) if not str(c.get('check', '')).startswith('video.')]
    existing += [{'level': l, 'check': n, 'detail': d} for l, n, d in rows_out]
    rep['ci_checks'] = existing
    rep['ci_summary'] = {'pass': sum(1 for c in existing if c['level'] == 'PASS'),
                         'warn': sum(1 for c in existing if c['level'] == 'WARN'),
                         'fail': sum(1 for c in existing if c['level'] == 'FAIL')}
    rep['status'] = 'PASSED' if rep['ci_summary']['fail'] == 0 else 'FAILED'
    rep['video'] = video_block
    with open(report_path, 'w', encoding='utf-8') as fh:
        json.dump(rep, fh, indent=2)
    return rep


def main():
    import argparse
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
    hits = ([dict(t_s=float(h['t']), kind=h.get('kind', 'cut')) for h in block['hits']] if block.get('hits')
            else [dict(t_s=float(t)) for t in block.get('hits_at', [])])
    rows_out, _ = rows(probe, a.program, rep.get('video', {}).get('mix', {}),
                       cfg['master_profiles'][cfg['master']['profile']], cfg['gate'], hits=hits)
    for lvl, name, detail in rows_out:
        print(f'[{lvl:4s}] {name:24s} {detail}')


if __name__ == '__main__':
    main()
