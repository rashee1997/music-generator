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

"""Metadata engine.

The standard tags live in `presets/metadata/metadata.json`; a project may add
`<project>/metadata.json` with an `overrides` map, and the score supplies the
title, genre and a factual comment. `ingest()` writes the merged result beside
the audio as `<name>.json`, which the MP3 compressor and the report read.

Usage:
  python scripts/helpers/ingest_metadata.py out/master.wav --project <project>
  python scripts/helpers/ingest_metadata.py out/master.wav --title "X" --artist "Y"
"""
import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

# The WAV blocks a tag is written to (RIFF INFO chunk ids). `description` has no standard INFO id, so it uses
# IDES; every reader that understands RIFF INFO shows it, and the JSON sidecar carries the same value.
INFO_TAGS = {
    'title': 'INAM',
    'artist': 'IART',
    'album': 'IPRD',
    'date': 'ICRD',
    'comment': 'ICMT',
    'copyright': 'ICOP',
    'license': 'ILIC',
    'genre': 'IGNR',
    'tracknumber': 'ITRK',
    'description': 'IDES',
}
_ID_TO_KEY = {v: k for k, v in INFO_TAGS.items()}

SKILL = Path(__file__).resolve().parents[2]
DEFAULTS_PATH = SKILL / 'presets' / 'metadata' / 'metadata.json'


def load_standard(project_dir=None):
    """Standard tags from the skill preset, plus a project's own overrides."""
    meta = {}
    if DEFAULTS_PATH.is_file():
        try:
            meta = json.loads(DEFAULTS_PATH.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            meta = {}
    standard = dict(meta.get('standard') or {})
    derive = dict(meta.get('derive_from_score') or {})
    overrides = dict(meta.get('project_overrides') or {})

    if project_dir:
        project = Path(project_dir)
        if project.name in overrides:
            standard.update(overrides[project.name] or {})
        own = project / 'metadata.json'
        if own.is_file():
            try:
                local = json.loads(own.read_text(encoding='utf-8'))
                standard.update(local.get('overrides') or {})
                if isinstance(local.get('derive_from_score'), dict):
                    derive.update(local['derive_from_score'])
            except (OSError, json.JSONDecodeError):
                pass
    return standard, derive


def score_comment(score):
    """A factual one-line description of the piece, never a claim about how it sounds."""
    bits = []
    key = score.get('key')
    mode = score.get('mode')
    if key:
        bits.append(' '.join(str(x) for x in (key, mode) if x))
    if score.get('bpm'):
        bits.append(f"{float(score['bpm']):g} BPM")
    if score.get('piece_type'):
        bits.append(str(score['piece_type']))
    return ' · '.join(bits)


def find_direction(project_dir):
    """The project's direction sheet (the first parseable direction/*.json), or {}."""
    if not project_dir:
        return {}
    folder = Path(project_dir) / 'direction'
    if not folder.is_dir():
        return {}
    for name in sorted(folder.glob('*.json')):
        try:
            data = json.loads(name.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def description_from_sheet(sheet, limit=600):
    """The purpose, then the story, in one plain sentence. Empty when the sheet has neither."""
    if not isinstance(sheet, dict):
        return ''
    purpose = ' '.join(str(sheet.get('purpose') or '').split())
    story = ' '.join(str(sheet.get('story') or '').split())
    if purpose and story and not purpose.endswith(('.', '!', '?')):
        purpose += '.'
    text = ' '.join(x for x in (purpose, story) if x)
    return text[:limit].strip()


def build(score=None, project_dir=None, overrides=None, direction=None):
    """Merged tags for one render: standard < score-derived < sheet description < explicit overrides."""
    score = score or {}
    standard, derive = load_standard(project_dir)
    tags = dict(standard)

    if derive.get('title', True) and score.get('title'):
        tags['title'] = score['title']
    if derive.get('genre', True) and score.get('piece_type'):
        tags['genre'] = str(score['piece_type']).replace('_', ' ').title()
    if derive.get('year', True) and not tags.get('year'):
        tags['year'] = str(datetime.now(timezone.utc).year)
    if derive.get('comment', True):
        fact = score_comment(score)
        base = (tags.get('comment') or '').strip()
        tags['comment'] = f'{base} — {fact}' if base and fact else (base or fact)

    sheet = find_direction(project_dir) if direction is None else direction
    desc = description_from_sheet(sheet)
    if desc:
        tags['description'] = desc

    for key, value in (overrides or {}).items():
        if value not in (None, ''):
            tags[key] = value
    return {k: v for k, v in tags.items() if v not in (None, '')}


def read_wav_tags(audio_path):
    """{tag: value} written in the RIFF INFO chunk of a WAV, or {} when there is none."""
    raw = Path(audio_path).read_bytes()
    if raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
        raise ValueError(f'{Path(audio_path).name} is not a RIFF/WAVE file')
    tags = {}
    pos = 12
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        body = raw[pos + 8:pos + 8 + size]
        if cid == b'LIST' and body[:4] == b'INFO':
            q = 4
            while q + 8 <= len(body):
                sid = body[q:q + 4]
                ssize = struct.unpack('<I', body[q + 4:q + 8])[0]
                value = body[q + 8:q + 8 + ssize].split(b'\x00', 1)[0].decode('utf-8', 'replace')
                key = _ID_TO_KEY.get(sid.decode('ascii', 'replace'))
                if key:
                    tags[key] = value
                q += 8 + ssize + (ssize % 2)
        pos += 8 + size + (size % 2)
    return tags


def write_wav_tags(audio_path, tags):
    """Write the supported tags into the WAV's RIFF INFO chunk. The audio chunks are copied byte for byte.

    Returns the list of tag names written. Raises on anything that is not a RIFF/WAVE file: the caller must
    report that, never swallow it.
    """
    audio = Path(audio_path)
    raw = audio.read_bytes()
    if raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
        raise ValueError(f'{audio.name} is not a RIFF/WAVE file')
    payload = []
    for key, value in tags.items():
        sid = INFO_TAGS.get(key)
        if not sid or value in (None, ''):
            continue
        data = str(value).encode('utf-8') + b'\x00'
        if len(data) % 2:
            data += b'\x00'
        payload.append(sid.encode('ascii') + struct.pack('<I', len(data)) + data)
    if not payload:
        return []
    info = b'INFO' + b''.join(payload)

    kept, pos = [], 12
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        end = pos + 8 + size + (size % 2)
        chunk = raw[pos:min(end, len(raw))]
        if not (cid == b'LIST' and chunk[8:12] == b'INFO'):
            kept.append(chunk if len(chunk) % 2 == 0 else chunk + b'\x00')
        pos = end
    body = b'WAVE' + b''.join(kept) + b'LIST' + struct.pack('<I', len(info)) + info
    audio.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)
    return [k for k in tags if INFO_TAGS.get(k) and tags.get(k) not in (None, '')]


def ingest(audio_path, score=None, project_dir=None, overrides=None, extra=None, direction=None,
           tag_audio=True):
    """Write the tags into the WAV (RIFF INFO), write `<audio>.json` beside it, and report both.

    `direction` is the project's direction sheet (read from <project>/direction/ when omitted): its purpose
    and story become the `description` field. A tagging failure is returned in `tag_error`, never raised,
    so the caller can print it and record it in ci_report.json.
    """
    audio = Path(audio_path)
    tags = build(score=score, project_dir=project_dir, overrides=overrides, direction=direction)
    payload = {
        'schema': 1,
        'audio': audio.name,
        'written_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'metadata': tags,
    }
    if extra:
        payload.update({k: v for k, v in extra.items() if v is not None})
    sidecar = audio.with_suffix('.json')
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    written, error = [], None
    if tag_audio:
        try:
            written = write_wav_tags(audio, tags)
        except Exception as exc:            # reported by the caller: a delivered file without tags is a defect
            error = str(exc)
    return {'sidecar': str(sidecar), 'metadata': tags, 'tagged': written, 'tag_error': error}


def read_sidecar(audio_path):
    """Tags already written beside an audio file, or an empty dict."""
    sidecar = Path(audio_path).with_suffix('.json')
    if not sidecar.is_file():
        return {}
    try:
        return json.loads(sidecar.read_text(encoding='utf-8')).get('metadata') or {}
    except (OSError, json.JSONDecodeError):
        return {}


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Write standard metadata beside an audio file')
    ap.add_argument('audio', nargs='+', help='audio file(s) to tag')
    ap.add_argument('--project', help='project folder (reads <project>/metadata.json overrides)')
    ap.add_argument('--score', help='score JSON to derive title, genre and comment from')
    for field in ('title', 'artist', 'album', 'album_artist', 'genre', 'year',
                  'composer', 'copyright', 'comment', 'publisher', 'isrc'):
        ap.add_argument('--' + field.replace('_', '-'), dest=field)
    args = ap.parse_args()

    score = {}
    if args.score:
        score = json.loads(Path(args.score).read_text(encoding='utf-8'))
    overrides = {k: getattr(args, k) for k in
                 ('title', 'artist', 'album', 'album_artist', 'genre', 'year',
                  'composer', 'copyright', 'comment', 'publisher', 'isrc')
                 if getattr(args, k)}

    for audio in args.audio:
        result = ingest(audio, score=score, project_dir=args.project, overrides=overrides)
        tags = result['metadata']
        print(f"{audio}: {tags.get('title') or '(untitled)'} — {result['sidecar']}")


if __name__ == '__main__':
    main()
