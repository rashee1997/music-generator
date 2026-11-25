"""stems.py - the per-stem rows: loudness, peak, dropouts, cuts, flatness, DC.

A stem row is owned by its stem, so the levers are that stem's: its trim, its high-pass, its note lengths and its
onset ramp. The discrete rows (a dropout is a stretch that should have sounded and did not) are attributed to the
gaps between that stem's notes, which is what makes the length/spacing conflict visible instead of guessed at.
"""
from __future__ import annotations

from .. import catalog, margins
from . import base


def _note_gaps(case, stem):
    """(gap_s, spacing_s) for the stem's notes, from the score: what a dropout row is really measuring."""
    tr = case.track(stem)
    if not tr:
        return []
    notes = sorted((n for n in (tr.get('notes') or []) if isinstance(n, dict) and 't' in n), key=lambda n: n['t'])
    bpm = float(case.score.get('tempo') or case.score.get('bpm') or 100.0)
    spb = 60.0 / bpm                       # seconds per beat: a note's `d` is written in beats
    out = []
    for a, b in zip(notes, notes[1:]):
        gap = (b['t'] - a['t']) * spb - float(a.get('d') or 0.0) * spb
        out.append((max(0.0, gap), (b['t'] - a['t']) * spb, spb))
    return out


def analyse(case, rows, history=()):
    levers = catalog.stem_levers(case, rows)
    coef = {}
    notes = []
    for r in rows:
        key = margins.row_key(r)
        stem = r.get('stem')
        for lv in levers:
            if lv.stem and stem and lv.stem != stem:
                continue
            if r['row'] in ('stem.loudness', 'stem.rms') and lv.kind == 'gain':
                coef[(key, lv.id)] = 1.0        # a trim moves a measured level one dB per dB
            elif r['row'] == 'stem.dead':
                # A dead stem is silence: no trim makes it audible, and pricing one here let the programme "cure" a
                # silent part by pulling four unrelated trims down 6 dB.
                coef[(key, lv.id)] = 0.0
            elif r['row'] == 'stem.dropout' and lv.kind == 'onset':
                coef[(key, lv.id)] = 1.0        # a millisecond of ramp is a millisecond of silence before the hit
            elif r['row'] == 'stem.dropout' and lv.kind == 'note_len':
                beat_ms = 60000.0 / float(case.score.get('bpm') or case.score.get('tempo') or 100.0)
                coef[(key, lv.id)] = -beat_ms   # a beat of note length is that many ms of gap closed
            elif r['row'] in ('stem.cut', 'stem.edge') and lv.kind == 'fade':
                coef[(key, lv.id)] = 1.0
            elif r['row'] in ('stem.clicks', 'stem.clipping') and lv.kind in ('eq', 'onset'):
                share = catalog.band_share_for(case, lv, r)
                if share:
                    coef[(key, lv.id)] = share
        gaps = _note_gaps(case, stem) if r['row'] == 'stem.dropout' else []
        gaps = [g for g in gaps if g[0] > 0]        # a simultaneous hit is not a gap to be opened
        if gaps:
            tight = min(gaps, key=lambda g: g[0])
            notes.append(f'{stem}: the tightest gap in the score is {tight[0] * 1000:.0f} ms at beat spacing '
                         f'{tight[2]:.3f} s ({60 / tight[2]:.0f} bpm sixteenths); the note lengths and the ramp '
                         f'share this number, so they cannot be moved independently')
    return base.Analysis(rows=rows, levers=levers, coefficients=coef, notes=notes)
