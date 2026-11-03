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
"""video_mux.py - put the finished program audio back on the picture, without touching the picture.

    python3 video-mixer/video_mux.py --video source.mp4 --audio out/program.wav --out out/final.mp4

The video stream is copied (`-c:v copy`), never re-encoded: the output carries the original packets.
Audio is always encoded, because the program mix is new audio. Codec, bitrate, faststart and length
flags come from the video preset's "mux" block, keyed by output extension.

After muxing the video stream is compared with the source (codec, size, pixel format, frame count).
That comparison is the lossless proof; `video_copy` alone is only a claim.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _ffprobe_streams(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(f'ffprobe failed on {path}: {p.stderr.decode("utf-8", "replace").strip()[-500:]}')
    info = json.loads(p.stdout.decode('utf-8', 'replace'))
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    return info, v


def _video_identity(path):
    info, v = _ffprobe_streams(path)
    dur = 0.0
    try:
        dur = float((info.get('format') or {}).get('duration') or 0.0)
    except ValueError:
        pass
    return dict(codec=v.get('codec_name'), width=v.get('width'), height=v.get('height'),
                pix_fmt=v.get('pix_fmt'), frames=int(v.get('nb_frames') or 0), duration_s=round(dur, 4))


def audio_args(cfg, ext):
    """Codec and its flags for this container, from the preset. Unknown extension is an error, not a guess."""
    codecs = cfg['audio_codec']
    codec = codecs.get(ext)
    if not codec:
        raise KeyError(f'no audio codec for ".{ext}" in the video preset (known: {sorted(codecs)}). '
                       f'Add it to the preset rather than guessing one.')
    args = ['-c:a', codec]
    if codec in ('aac', 'libopus', 'libmp3lame'):
        args += ['-b:a', str(cfg.get('audio_bitrate', '320k'))]
    if codec == 'pcm_s24le':
        args += ['-ar', '48000']
    return args


def mux(video, audio, out, cfg, verbose=False):
    """Mux and verify. Returns a report dict; raises if the video stream did not survive intact."""
    ext = os.path.splitext(out)[1].lstrip('.').lower()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cmd = ['ffmpeg', '-y', '-hide_banner', '-nostdin', '-i', video, '-i', audio,
           '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy' if cfg.get('video_copy', True) else 'libx264']
    cmd += audio_args(cfg, ext)
    if cfg.get('faststart') and ext in ('mp4', 'mov', 'm4a'):
        cmd += ['-movflags', '+faststart']
    if cfg.get('shortest'):
        cmd += ['-shortest']
    cmd += [out]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(f'mux failed ({p.returncode}): {p.stderr.decode("utf-8", "replace").strip()[-900:]}')
    src, dst = _video_identity(video), _video_identity(out)
    same = all(src[k] == dst[k] for k in ('codec', 'width', 'height', 'pix_fmt'))
    if src['frames'] and dst['frames']:
        same = same and src['frames'] == dst['frames']
    report = dict(out=os.path.abspath(out), video_copy=bool(cfg.get('video_copy', True)),
                  source_video=src, out_video=dst, video_identical=bool(same),
                  audio_codec=audio_args(cfg, ext)[1], audio_streams=None)
    info, _ = _ffprobe_streams(out)
    report['audio_streams'] = sum(1 for s in info.get('streams', []) if s.get('codec_type') == 'audio')
    if verbose:
        print(f"  mux: {out}  video {src['codec']} {src['width']}x{src['height']} "
              f"{'copied, identical' if same else 'CHANGED'}; audio {report['audio_codec']}")
    if not same:
        raise RuntimeError(f'video stream changed during mux: {src} -> {dst}')
    return report


def main():
    import argparse
    sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
    import presets
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--video', required=True)
    ap.add_argument('--audio', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--preset', default='default')
    ap.add_argument('--project')
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    cfg = presets.get('video', a.preset)
    print(json.dumps(mux(a.video, a.audio, a.out, cfg['mux'], verbose=True), indent=2))


if __name__ == '__main__':
    main()
