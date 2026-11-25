"""channels.py - the speaker-facing rows: per-channel peak, downmix folds, layouts, objects and the ADM bed.

A 7.1 render is judged channel by channel, so a row here is a per-speaker quantity. The levers are the ones that
act on every channel at once (master trim, ceiling) and the send that decides how much of a stem reaches the
surrounds; a channel that fails alone is reported with its own name so the score's placement, not the master, is
what gets looked at.
"""
from __future__ import annotations

from .. import catalog, margins
from . import base

_GAIN_ROWS = ('true peak', 'delivery.true_peak', 'clipping', 'loudness', 'imm.loudness', 'fold.', 'channel.')
_SEND_ROWS = ('fold.mono', 'fold.timbre', 'layout.', 'objects.', 'adm.', 'imm.wide')


def _channel_of(row):
    raw = row.get('raw') or {}
    for key in ('channel', 'speaker', 'label'):
        if raw.get(key):
            return str(raw[key])
    detail = row.get('detail') or ''
    for name in ('L', 'R', 'C', 'LFE', 'Ls', 'Rs', 'Lrs', 'Rrs', 'Lss', 'Rss', 'Lb', 'Rb', 'Tfl', 'Tfr'):
        if f'[{name}]' in detail or f' {name} ' in detail:
            return name
    return None


def analyse(case, rows, history=()):
    from . import master                      # the trim and ceiling are the levers that move a channel peak
    levers = master.levers(case) + catalog.spatial_levers(case, 'channels')
    coef, notes = {}, []
    for r in rows:
        key = margins.row_key(r)
        name = (r['row'] or '').lower()
        ch = _channel_of(r)
        if ch:
            notes.append(f"{r['row']}: channel {ch}" + (f" ({r.get('detail')})" if r.get('detail') else ''))
        for lv in levers:
            if lv.kind in ('gain', 'ceiling', 'lufs') and name.startswith(_GAIN_ROWS):
                coef[(key, lv.id)] = 1.0
            elif lv.kind == 'send' and name.startswith(_SEND_ROWS):
                coef[(key, lv.id)] = 1.0
    return base.Analysis(rows=rows, levers=levers, coefficients=coef, notes=notes,
                         measured=[r['row'] for r in rows])
