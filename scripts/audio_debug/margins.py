"""margins.py - every row as one signed number: how much room is left, in its own tolerance.

A gate row is a measured value, a threshold and a direction. Comparing "0.4 dB" with "1 impulse" is meaningless;
what the solver needs is a dimensionless headroom whose sign is the verdict and whose magnitude is comparable
across rows. Each row is therefore divided by a scale: its own tolerance band where the row has one (a hole is
judged over a 20 ms limit, so 10 ms of room is 0.5), otherwise a starting value per unit.

    safety > 0   passes with that much room
    safety = 0   exactly on the limit
    safety < 0   fails by that fraction of the tolerance

The sign convention is fixed once here so the sensitivity matrix and the solver cannot disagree about which way a
row improves: `sense='max'` (a level, a count, a duration) improves as the value falls; `sense='min'` improves as
it rises.
"""
from __future__ import annotations

import re

# Rows whose good direction is "at least this much". Everything else is "at most this much", which is the gate's
# default: a limit on a level, a count or a duration.
MIN_ROWS = (
    'loudness', 'delivery.true_peak', 'crest', 'stem.dead', 'imm.loudness', 'chem.reward_build',
    'chem.reward_arrival', 'chem.affiliation', 'chem.motor_drive',
)

# Per-unit starting scales (the words "starting value" apply): how much room counts as a full unit of safety.
UNIT_SCALE = {'dB': 6.0, 'dBTP': 3.0, 'LU': 3.0, 'LUFS': 3.0, 'ms': 10.0, 'events': 1.0, 'samples': 1.0,
              'FS': 0.01, 'rho': 0.2, 'flatness': 0.05, 'bits': 0.5, '': 1.0}


def sense(row):
    stated = (row.get('raw') or {}).get('sense')
    if stated in ('min', 'max'):        # the row itself said which direction improves (parsed verdict text)
        return stated
    name = row.get('row') or ''
    if name in MIN_ROWS:
        return 'min'
    if name.startswith('spectral.') and ('balance' in name or 'tilt' in name):
        return 'max'
    return 'max'


def scale(row):
    """The row's own tolerance band when it has one, else the unit's starting scale."""
    thr = row.get('threshold')
    unit = row.get('unit') or ''
    base = UNIT_SCALE.get(unit, 1.0)
    try:
        thr = float(thr)
    except (TypeError, ValueError):
        return base
    if unit in ('ms', 'events', 'samples') and thr > 0:
        return max(thr, 1e-9)                 # "a 20 ms limit" already is the band
    return base if base > 0 else max(abs(thr), 1e-9)


def safety(row):
    """(safety, sense, scale) for one row. Rows the profile skipped are INFO and carry safety +inf."""
    val, thr = row.get('value'), row.get('threshold')
    try:
        val, thr = float(val), float(thr)
    except (TypeError, ValueError):
        return float('inf'), sense(row), 1.0
    if row.get('level') == 'INFO':
        return float('inf'), sense(row), 1.0
    s = sense(row)
    ss = scale(row) or 1.0
    room = (thr - val) if s == 'max' else (val - thr)
    return room / ss, s, ss


def describe(s):
    """The safety as the words a report uses."""
    if s == float('inf'):
        return 'not judged'
    if s < 0:
        return f'FAILS by {abs(s):.2f} tolerance units'
    if s < 0.15:
        return f'passes on the edge ({s:.2f})'
    return f'passes with {s:.2f} units of room'


def row_key(row):
    """A stable key for a row on a stem: a row may be judged once per stem."""
    return f"{row.get('row')}::{row.get('stem') or '-'}"


def events(row):
    """The discrete events a row names, as (time_s, magnitude) pairs when it has them."""
    raw = row.get('raw') or {}
    out = []
    for t in raw.get('worst_times_s') or []:
        out.append((float(t), 1.0))
    for h in raw.get('holes') or []:
        try:
            out.append((float(h.get('start_s')), float(h.get('length_ms', 0.0))))
        except (TypeError, ValueError):
            continue
    for t, d in (raw.get('drops') or []) if isinstance(raw.get('drops'), list) else []:
        pass
    return out


def is_event_row(row):
    """True for rows whose verdict is a count/length of discrete events rather than a spectrum or a level."""
    name = row.get('row') or ''
    return name in ('clicks', 'stem.clicks', 'stem.dropout', 'stem.cut', 'stem.flatness', 'stem.clipping',
                    'silence', 'stem.edge') or bool(events(row))


BAND_ROWS = {
    # row -> (band from the profile, or None for "the row's own band")
    'spectral.equal_loudness': ('band_lo_hz', 'band_hi_hz'),
    'mix.band_fold': ('band_hz', None),
    'masking.excess': (None, None),
    'erb_binaural_masking': (None, None),
}


def band_of(row, params=None):
    """(lo, hi) Hz the row measures, or None. `params` is a gate profile's param(row, key) callable."""
    spec = BAND_ROWS.get(row.get('row'))
    if not spec:
        return None
    raw = row.get('raw') or {}
    lo = raw.get('band_lo_hz') or raw.get('band_hz')
    if isinstance(lo, (list, tuple)) and len(lo) == 2:
        return float(lo[0]), float(lo[1])
    if params is not None:
        try:
            a = float(params(row['row'], spec[0])) if spec[0] else None
            b = float(params(row['row'], spec[1])) if spec[1] else None
            if a and b:
                return a, b
        except Exception:
            pass
    try:
        m = re.search(r'(\d+)\s*-\s*(\d+)\s*Hz', row.get('detail') or '')
        if m:
            return float(m.group(1)), float(m.group(2))
    except Exception:
        pass
    return None
