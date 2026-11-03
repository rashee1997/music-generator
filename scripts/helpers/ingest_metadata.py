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

The standard tags live in `presets/metatdats/metadata.json`; a project may add
`<project>/metadata.json` with an `overrides` map, and the score supplies the
title, genre and a factual comment. `ingest()` writes the merged result beside
the audio as `<name>.json`, which the MP3 compressor and the report read.

Usage:
  python scripts/helpers/ingest_metadata.py out/master.wav --project <project>
  python scripts/helpers/ingest_metadata.py out/master.wav --title "X" --artist "Y"
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
DEFAULTS_PATH = SKILL / 'presets' / 'metatdats' / 'metadata.json'


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
        bits.append(f"{key} {mode}".strip())
    if score.get('bpm'):
        bits.append(f"{float(score['bpm']):g} BPM")
    if score.get('piece_type'):
        bits.append(str(score['piece_type']))
    return ' · '.join(bits)


def build(score=None, project_dir=None, overrides=None):
    """Merged tags for one render: standard < score-derived < explicit overrides."""
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

    for key, value in (overrides or {}).items():
        if value not in (None, ''):
            tags[key] = value
    return {k: v for k, v in tags.items() if v not in (None, '')}


def ingest(audio_path, score=None, project_dir=None, overrides=None, extra=None):
    """Write `<audio>.json` beside the audio and return what was written."""
    audio = Path(audio_path)
    tags = build(score=score, project_dir=project_dir, overrides=overrides)
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
    return {'sidecar': str(sidecar), 'metadata': tags}


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
