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
"""video_probe.py - read the picture: duration, frame rate, streams, cuts, motion, light and colour.

    python3 video-mixer/video_probe.py clips/source.mp4 --preset default --out reports/video_probe.json

Three passes, all numbers from the video preset (`references/data/presets/video/<name>.json`):
  ffprobe    container and stream facts, plus keyframe times
  scdet      scene-change candidates (ffmpeg's luma-change score, 0-100 scale)
  rawvideo   every frame at analysis_fps, downscaled, piped to numpy:
             luma (brightness), motion (frame difference), horizontal centre of motion, warmth

Nothing here knows about music. It measures pixels and hands over numbers.
Fades and dissolves score low on scdet and are missed by design; the cut list is a candidate list.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SCD_RE = re.compile(r'lavfi\.scd\.score:\s*(-?[\d.]+),\s*lavfi\.scd\.time:\s*(-?[\d.]+)')


def _run(cmd, binary=False):
    """Run ffmpeg/ffprobe. Returns (stdout, stderr); raises with the tool's own message on failure."""
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    err = p.stderr.decode('utf-8', 'replace')
    if p.returncode != 0:
        raise RuntimeError(f'{os.path.basename(cmd[0])} failed ({p.returncode}): {err.strip()[-800:]}')
    return (p.stdout if binary else p.stdout.decode('utf-8', 'replace')), err


def ffprobe_json(path):
    out, _ = _run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', path])
    return json.loads(out)


def _fps(stream):
    for key in ('avg_frame_rate', 'r_frame_rate'):
        rate = stream.get(key) or ''
        if '/' in rate:
            num, den = rate.split('/', 1)
            try:
                if float(den) > 0:
                    return float(num) / float(den)
            except ValueError:
                pass
    return 0.0


def stream_facts(info):
    """Container and stream facts, in the units the rest of the pipeline speaks (seconds, fps, pixels)."""
    streams = info.get('streams') or []
    video = [s for s in streams if s.get('codec_type') == 'video']
    audio = [s for s in streams if s.get('codec_type') == 'audio']
    v = video[0] if video else {}
    fmt = info.get('format') or {}
    duration = 0.0
    for cand in (fmt.get('duration'), v.get('duration')):
        try:
            duration = float(cand)
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue
    return dict(duration_s=duration, fps=_fps(v), width=int(v.get('width') or 0), height=int(v.get('height') or 0),
                video_codec=v.get('codec_name'), frames=int(v.get('nb_frames') or 0),
                has_video=bool(video), has_audio=bool(audio),
                audio_streams=len(audio), audio_codec=(audio[0].get('codec_name') if audio else None))


def keyframe_times(path):
    """Keyframe timestamps only. Cheap: ffprobe skips non-key frames instead of decoding them."""
    try:
        out, _ = _run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-skip_frame', 'nokey',
                       '-show_entries', 'frame=pts_time', '-of', 'csv=p=0', path])
    except RuntimeError:
        return []
    times = []
    for line in out.splitlines():
        line = line.strip().rstrip(',')
        try:
            times.append(float(line))
        except ValueError:
            continue
    return times


def cut_candidates(path, cfg, duration_s=0.0):
    """scdet scores -> [(t, score)]. Returns ([], 'unavailable') when the build has no scdet."""
    cut_cfg = cfg['scene_cut']
    try:
        _, err = _run(['ffmpeg', '-hide_banner', '-nostats', '-nostdin', '-i', path, '-an',
                       '-vf', f"scdet=t={cut_cfg['threshold']}", '-f', 'null', os.devnull])
    except RuntimeError as e:
        return [], f'unavailable: {e}'
    cuts = [(float(t), float(s)) for s, t in SCD_RE.findall(err)]
    cuts.sort()
    return _thin(cuts, cut_cfg.get('min_gap_s', 0.0)), 'scdet'


def _thin(items, min_gap_s, t_index=0):
    """Keep the strongest item inside each min_gap_s window, so one cut is not counted twice."""
    if min_gap_s <= 0 or not items:
        return list(items)
    kept = []
    for item in sorted(items, key=lambda x: x[t_index]):
        if not kept or item[t_index] - kept[-1][t_index] >= min_gap_s:
            kept.append(item)
    return kept


def frame_metrics(path, cfg):
    """Per-frame luma, motion, horizontal centre of motion and warmth, read one frame at a time.

    Streams the rawvideo pipe so memory stays flat however long the picture is.
    Scale is fixed (not aspect-preserving): these numbers are relative, and a fixed grid keeps the centroid meaningful.
    """
    fps = float(cfg['analysis_fps'])
    w, h = int(cfg['analysis_width']), int(cfg['analysis_height'])
    out, _ = _run(['ffmpeg', '-hide_banner', '-nostats', '-nostdin', '-v', 'error', '-i', path, '-an',
                   '-vf', f'fps={fps},scale={w}:{h},format=rgb24', '-f', 'rawvideo', '-'], binary=True)
    frame_bytes = w * h * 3
    n = len(out) // frame_bytes
    luma, motion, centre, warmth = [], [], [], []
    prev = None
    xs = np.arange(w, dtype=np.float32)
    for i in range(n):
        rgb = np.frombuffer(out, np.uint8, count=frame_bytes, offset=i * frame_bytes).reshape(h, w, 3).astype(np.float32)
        lum = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]) / 255.0
        luma.append(float(lum.mean()))
        r, b = rgb[:, :, 0].mean(), rgb[:, :, 2].mean()
        warmth.append(float((r - b) / (r + b + 1e-6)))
        if prev is None:
            motion.append(0.0)
            centre.append(0.0)
        else:
            d = np.abs(lum - prev)
            total = float(d.sum())
            motion.append(total / d.size)
            centre.append(float((d.sum(axis=0) * xs).sum() / total / (w - 1) * 2.0 - 1.0) if total > 1e-6 else 0.0)
        prev = lum
    return dict(fps=fps, frames=n, luma=luma, motion=motion, centre=centre, warmth=warmth)


def motion_hits(frames, cfg):
    """Frame-difference peaks: the moments the picture itself hits. (t, strength) pairs."""
    motion = frames['motion']
    if len(motion) < 3:
        return []
    mh = cfg['motion_hit']
    thresh = float(np.percentile(motion, mh['percentile']))
    peaks = [(i / frames['fps'], v) for i, v in enumerate(motion) if v > thresh and v > 0]
    return _thin(peaks, mh.get('min_gap_s', 0.0))


def energy_curve(frames, bins):
    """Motion binned into equal time slices, normalised 0..1: the shape of the picture's energy."""
    motion = np.asarray(frames['motion'], np.float32)
    if not len(motion):
        return []
    edges = np.linspace(0, len(motion), int(bins) + 1).astype(int)
    vals = [float(motion[edges[i]:max(edges[i] + 1, edges[i + 1])].mean()) for i in range(int(bins))]
    peak = max(vals) or 1.0
    return [round(v / peak, 4) for v in vals]


def probe(path, cfg, verbose=False):
    """Everything the direction stage needs, in one dict. `cfg` is the whole video preset. Raises if the file is unreadable."""
    pcfg = cfg['probe']
    if not os.path.isfile(path):
        raise FileNotFoundError(f'no video at {path}')
    info = ffprobe_json(path)
    facts = stream_facts(info)
    if not facts['has_video']:
        raise ValueError(f'{path} has no video stream')
    frames = frame_metrics(path, pcfg)
    cuts, cut_source = cut_candidates(path, pcfg, facts['duration_s'])
    if not cuts and cut_source == 'scdet':                      # a single-shot film has no cut; that is not an error
        cut_source = 'scdet (no cut found)'
    elif cut_source != 'scdet':
        cuts = _thin(motion_hits(frames, pcfg), pcfg['scene_cut'].get('min_gap_s', 0.0))
        cut_source = f'frame-difference fallback ({cut_source})'
    if not facts['duration_s'] and frames['frames']:
        facts['duration_s'] = frames['frames'] / frames['fps']
    out = dict(path=os.path.abspath(path), source=facts, cut_source=cut_source,
               cuts=[dict(t=round(t, 4), score=round(s, 3)) for t, s in cuts],
               motion_hits=[dict(t=round(t, 4), strength=round(float(v), 5)) for t, v in motion_hits(frames, pcfg)],
               energy=energy_curve(frames, cfg['direction_map']['energy_curve_bins']),
               luma_mean=round(float(np.mean(frames['luma'])) if frames['luma'] else 0.0, 4),
               warmth_mean=round(float(np.mean(frames['warmth'])) if frames['warmth'] else 0.0, 4),
               centre_mean=round(float(np.mean(frames['centre'])) if frames['centre'] else 0.0, 4),
               centre_range=[round(float(np.min(frames['centre'])), 4), round(float(np.max(frames['centre'])), 4)] if frames['centre'] else [0.0, 0.0],
               motion_mean=round(float(np.mean(frames['motion'])) if frames['motion'] else 0.0, 5),
               frames_analysed=frames['frames'], analysis_fps=frames['fps'])
    if pcfg.get('keyframe_probe'):
        out['keyframes'] = keyframe_times(path)
    if verbose:
        s = out['source']
        print(f"  probe: {s['duration_s']:.2f}s {s['width']}x{s['height']} @ {s['fps']:.3f} fps, "
              f"{len(out['cuts'])} cuts ({cut_source}), {len(out['motion_hits'])} motion hits, "
              f"audio {'yes' if s['has_audio'] else 'no'}")
    return out


def main():
    import argparse
    sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
    import presets
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--preset', default='default')
    ap.add_argument('--project')
    ap.add_argument('--out', default=None)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    cfg = presets.get('video', a.preset)
    rep = probe(a.video, cfg, verbose=not a.quiet)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as fh:
            json.dump(rep, fh, indent=2)
        print(f'  wrote {a.out}')
    else:
        print(json.dumps(rep, indent=2))


if __name__ == '__main__':
    main()
