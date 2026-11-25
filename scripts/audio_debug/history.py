"""history.py - what has already been tried on this piece, so it is not tried again.

Every autopsy records the moves it recommends. Every render records what the gate then said. A lever that was tried
against a row and did not clear it is *burned* for that row: the solver zeroes its column and the report lists it,
which is what stops the same failed experiment from being proposed a fourth time.
"""
from __future__ import annotations

import datetime as _dt
import json
import os

FILE = 'debug_history.jsonl'


def path(project):
    return os.path.join(project, 'reports', FILE)


def load(project):
    out = []
    try:
        with open(path(project), encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def record(project, lever, row, delta, outcome, note=''):
    """Append one attempt. `outcome` is 'cleared', 'no change', 'worse' or 'same'."""
    entry = dict(stamp=_dt.datetime.now().isoformat(timespec='seconds'), lever=lever, row=row,
                 delta=delta, outcome=outcome, note=note)
    os.makedirs(os.path.dirname(path(project)), exist_ok=True)
    with open(path(project), 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry) + '\n')
    return entry
