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

"""Manual MP3 compression. Never called by the pipeline.

Takes a rendered WAV (or a folder of them), reads the metadata sidecar written
by `ingest_metadata.py`, and encodes with ffmpeg at a chosen bitrate.

Usage:
  python scripts/helpers/compress_mp3.py out/master.wav
  python scripts/helpers/compress_mp3.py out/ -o assets/samples -b 192k
  python scripts/helpers/compress_mp3.py out/master.wav --title "X" --artist "Y"
"""
import shutil
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import ingest_metadata

SKILL = Path(__file__).resolve().parents[2]

# sidecar field -> ffmpeg metadata key
FFMPEG_KEYS = {
    'title': 'title',
    'artist': 'artist',
    'album': 'album',
    'album_artist': 'album_artist',
    'genre': 'genre',
    'year': 'date',
    'track_number': 'track',
    'composer': 'composer',
    'copyright': 'copyright',
    'comment': 'comment',
    'publisher': 'publisher',
    'isrc': 'ISRC',
    'language': 'language',
}


def ffmpeg_available():
    return shutil.which('ffmpeg') is not None


def compress(source, output=None, bitrate='320k', tags=None, project_dir=None,
             score=None, overwrite=False):
    """Encode one WAV to MP3 with the sidecar's tags. Returns the output path."""
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(f'no such file: {src}')
    if not ffmpeg_available():
        raise RuntimeError('ffmpeg is not on PATH, so MP3 encoding is unavailable')

    dst = Path(output) if output else SKILL / 'assets' / 'compressed' / f'{src.stem}.mp3'
    if dst.is_dir() or dst.suffix == '':
        dst = dst / f'{src.stem}.mp3'
    if dst.exists() and not overwrite:
        raise FileExistsError(f'{dst} exists (pass --overwrite)')
    dst.parent.mkdir(parents=True, exist_ok=True)

    merged = dict(ingest_metadata.read_sidecar(src))
    merged.update(ingest_metadata.build(score=score, project_dir=project_dir, overrides=tags))

    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(src),
           '-codec:a', 'libmp3lame', '-b:a', bitrate]
    for key, value in merged.items():
        ffkey = FFMPEG_KEYS.get(key)
        if ffkey and value not in (None, ''):
            cmd += ['-metadata', f'{ffkey}={value}']
    cmd.append(str(dst))

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f'ffmpeg failed: {proc.stderr.strip()[:400]}')
    return dst


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Compress rendered WAVs to MP3 (manual, not part of the pipeline)')
    ap.add_argument('source', help='a WAV file or a folder of WAVs')
    ap.add_argument('-o', '--output', help='output MP3 or folder (default: assets/compressed/)')
    ap.add_argument('-b', '--bitrate', default='320k', help='MP3 bitrate (default: 320k)')
    ap.add_argument('--project', help='project folder for metadata overrides')
    ap.add_argument('--score', help='score JSON to derive tags from')
    ap.add_argument('--overwrite', action='store_true', help='replace an existing MP3')
    for field in ('title', 'artist', 'album', 'genre', 'comment'):
        ap.add_argument('--' + field, dest=field)
    args = ap.parse_args()

    src = Path(args.source)
    tags = {k: getattr(args, k) for k in ('title', 'artist', 'album', 'genre', 'comment') if getattr(args, k)}
    import json
    score = json.loads(Path(args.score).read_text(encoding='utf-8')) if args.score else None

    if src.is_dir():
        files = sorted(p for p in src.glob('*.wav') if not p.name.startswith('_'))
        if not files:
            raise SystemExit(f'no WAV files in {src}')
        out_dir = Path(args.output) if args.output else SKILL / 'assets' / 'compressed'
        targets = [(f, out_dir) for f in files]
    else:
        targets = [(src, args.output)]

    try:
        for file_path, out in targets:
            dst = compress(file_path, out, args.bitrate, tags, args.project, score, args.overwrite)
            size = dst.stat().st_size / 1024 / 1024
            print(f'{file_path.name} -> {dst} ({size:.1f} MB, {args.bitrate})')
    except (FileNotFoundError, FileExistsError, RuntimeError) as exc:
        raise SystemExit(str(exc))


if __name__ == '__main__':
    main()
