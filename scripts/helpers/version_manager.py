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

"""Versioning for certified masters.

A certified render never destroys the one before it. `publish()`:

  1. gives the new master the next version number (`master_v03.wav`),
  2. keeps every earlier version on disk, each recorded with the change that
     produced it ("largest change") in `out/versions.json`,
  3. refreshes `out/master.wav` as a copy of the newest version, so callers
     that expect a single master keep working.

The change recorded for a version is the failure it resolved, read from the
gate attempts history: the previous attempt's failing rows, or "first certified
render" when the piece passed on its first run.

Usage:
  python scripts/helpers/version_manager.py list --project <project>
  python scripts/helpers/version_manager.py publish <draft.wav> --project <project>
"""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

INDEX_NAME = 'versions.json'


def index_path(directory):
    return Path(directory) / INDEX_NAME


def load(directory):
    """Version index for a project's out/ folder."""
    path = index_path(directory)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            data.setdefault('versions', [])
            data.setdefault('latest', 0)
            return data
        except (OSError, json.JSONDecodeError):
            pass
    return {'versions': [], 'latest': 0}


def save(directory, data):
    index_path(directory).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n',
                                     encoding='utf-8')


def largest_change(attempts):
    """The change that earned this version, from the gate attempts history."""
    attempts = attempts or []
    failed = [a for a in attempts if a.get('fails')]
    if not failed:
        return 'first certified render'
    rows = failed[-1].get('failing') or []
    if not rows:
        return f"cleared {failed[-1].get('fails')} gate failure(s)"
    shown = '; '.join(str(r).split(':')[0] for r in rows[:4])
    more = '' if len(rows) <= 4 else f' +{len(rows) - 4}'
    return f'cleared {shown}{more}'


def publish(draft_wav, master_wav, score=None, attempts=None, measurements=None,
            directory=None):
    """Version a certified draft, keep the old masters, refresh the plain master."""
    draft, master = Path(draft_wav), Path(master_wav)
    out_dir = Path(directory) if directory else master.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    data = load(out_dir)
    version = int(data.get('latest', 0)) + 1
    versioned = out_dir / f'master_v{version:02d}.wav'

    if versioned.exists():                       # never clobber an existing version
        version += 1
        versioned = out_dir / f'master_v{version:02d}.wav'

    os.replace(str(draft), str(versioned))
    shutil.copyfile(str(versioned), str(master))

    entry = {
        'version': version,
        'file': versioned.name,
        'master': master.name,
        'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'change': largest_change(attempts),
        'attempts': len(attempts or []),
        'title': (score or {}).get('title'),
        'piece_type': (score or {}).get('piece_type'),
    }
    for key in ('integrated_lufs', 'true_peak_dbtp', 'crest_factor_db', 'duration_s'):
        if measurements and measurements.get(key) is not None:
            entry[key] = measurements[key]

    data['versions'].append(entry)
    data['latest'] = version
    save(out_dir, data)
    return entry


def update_entry(directory, version, measurements=None, **fields):
    """Attach late measurements (loudness, true peak, crest) to a recorded version."""
    data = load(directory)
    for entry in data.get('versions', []):
        if entry.get('version') == version:
            for key in ('integrated_lufs', 'true_peak_dbtp', 'crest_factor_db', 'duration_s'):
                if measurements and measurements.get(key) is not None:
                    entry[key] = measurements[key]
            entry.update({k: v for k, v in fields.items() if v is not None})
            save(directory, data)
            return entry
    return None


def listing(directory):
    """Recorded versions, oldest first."""
    return load(directory).get('versions', [])


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Inspect or publish certified master versions')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_list = sub.add_parser('list', help='print the version history')
    p_list.add_argument('--project', required=True)

    p_pub = sub.add_parser('publish', help='version a certified draft')
    p_pub.add_argument('draft')
    p_pub.add_argument('--project', required=True)
    p_pub.add_argument('--master', default=None, help='path of the plain master (default: out/master.wav)')
    p_pub.add_argument('--change', default=None, help='description overriding the derived change')
    args = ap.parse_args()

    if args.cmd == 'list':
        out_dir = Path(args.project) / 'out'
        rows = listing(out_dir)
        if not rows:
            print(f'no versions recorded in {out_dir}')
        for row in rows:
            print(f"v{row['version']:02d}  {row.get('timestamp', '')}  {row.get('change', '')}  [{row.get('file')}]")
        return

    out_dir = Path(args.project) / 'out'
    master = Path(args.master) if args.master else out_dir / 'master.wav'
    entry = publish(args.draft, master, attempts=None)
    if args.change:
        data = load(out_dir)
        data['versions'][-1]['change'] = args.change
        save(out_dir, data)
        entry['change'] = args.change
    print(f"v{entry['version']:02d} -> {entry['file']} ({entry['change']})")


if __name__ == '__main__':
    main()
