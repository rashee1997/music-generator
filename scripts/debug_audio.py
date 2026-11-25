"""debug_audio.py - run the autopsy on a project's last render.

    python scripts/debug_audio.py projects/<piece>                 # only the failing domains
    python scripts/debug_audio.py projects/<piece> --level WARN    # when nothing fails
    python scripts/debug_audio.py projects/<piece> --json          # machine form on stdout
    python scripts/debug_audio.py projects/<piece> --record clicks=render.oversample=4 --outcome "no change"

The report is written to `<project>/reports/debug_audio.{md,json}` either way; nothing is rendered and nothing is
changed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audio_debug  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description='Diagnose the last render; propose the smallest change set that clears '
                                            'every failing row without creating another.')
    ap.add_argument('project')
    ap.add_argument('--score', default=None)
    ap.add_argument('--level', default=None, choices=(None, 'FAIL', 'WARN'))
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--record', action='append', default=[], metavar='ROW=LEVER=DELTA',
                    help='record an attempt in reports/debug_history.jsonl')
    ap.add_argument('--outcome', default='no change', choices=('cleared', 'no change', 'worse', 'same'))
    args = ap.parse_args(argv)

    case = audio_debug.Case.load(args.project, args.score)
    history = audio_debug.history.load(case.project)
    for spec in args.record:
        try:
            row, lever, delta = spec.split('=')
        except ValueError:
            ap.error(f'--record wants ROW=LEVER=DELTA, got {spec!r}')
        audio_debug.history.record(case.project, lever, row, float(delta), args.outcome)
        history = audio_debug.history.load(case.project)
    rep = audio_debug.autopsy(case, level=args.level, history=history)
    if args.json:
        print(json.dumps(rep.as_dict(), indent=1))
    elif not args.quiet:
        print(rep.text)
    else:
        print(f'{rep.plan.status}: {len(rep.plan.deltas)} move(s), {len(rep.plan.conflicts)} conflict(s)'
              f' -> {os.path.join(case.project, "reports", "debug_audio.md")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
