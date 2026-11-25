"""catalog.py - the levers a project's presets and score actually declare.

Nothing in this file names a piece. Levers come from `mix.inst_eq` (band gains per stem), each instrument's
`gain_db`, each track's `spatial` and `fade`, the score's note lengths and the mix's mastering block. A project that
declares none of these simply has fewer levers, and a row with no lever is reported as closed rather than as a
failure to fix.
"""
from __future__ import annotations

from . import margins
from .domains import base

EQ_GAIN_SPAN = 12.0        # dB a band may be moved from where it is now
GAIN_SPAN = 6.0            # dB a stem trim may be moved
LEN_SPAN = 0.06            # beats a note length may be moved, about a 32nd at 100 bpm


def _bands(case, stem):
    table = (case.mix or {}).get('inst_eq') or {}
    return table.get(stem) or []


def eq_levers(case, domain='stems', only_stems=None):
    """One lever per declared EQ band, on the stem that declares it."""
    out = []
    stems = only_stems if only_stems is not None else list((case.mix or {}).get('inst_eq') or {})
    for stem in stems:
        for i, b in enumerate(_bands(case, stem)):
            kind = str(b.get('type') or 'peak').lower()
            f0 = float(b.get('f') or b.get('freq') or 1000.0)
            gain = float(b.get('gain') or 0.0)
            q = float(b.get('q') or 1.0)
            out.append(base.Lever(
                f'inst_eq.{stem}.{i}', domain, 'eq', gain, gain - EQ_GAIN_SPAN, min(12.0, gain + EQ_GAIN_SPAN),
                0.5, 'dB', f'{stem} {kind} {f0:.0f} Hz q{q:g}', stem=stem,
                burns=('clicks', 'spectral.equal_loudness') if kind in ('peak', 'highshelf', 'lp') else ()))
    return out


def gain_levers(case, domain='stems', only_stems=None):
    out = []
    for name, inst in (case.instruments or {}).items():
        if only_stems is not None and name not in only_stems:
            continue
        if 'gain_db' not in inst:
            continue
        cur = float(inst['gain_db'])
        out.append(base.Lever(f'gain.{name}', domain, 'gain', cur, cur - GAIN_SPAN, cur + GAIN_SPAN, 0.5, 'dB',
                              f'{name} instrument trim', stem=name, burns=('stems',)))
    return out


def onset_levers(case, domain='stems', only_stems=None):
    """The two sample-domain shapes a sampled or percussive voice exposes."""
    out = []
    for name, inst in (case.instruments or {}).items():
        if only_stems is not None and name not in only_stems:
            continue
        if 'onset_fade_ms' in inst:
            cur = float(inst['onset_fade_ms'])
            out.append(base.Lever(f'onset.{name}.ms', domain, 'onset', cur, 0.0, 3.0, 0.1, 'ms',
                                  f'{name} onset ramp', stem=name, burns=('stem.dropout',)))
        if 'onset_fade_all' in inst:
            out.append(base.Lever(f'onset.{name}.all', domain, 'onset', 1.0 if inst['onset_fade_all'] else 0.0,
                                  0.0, 1.0, 1.0, 'flag', f'{name} ramp every onset', stem=name,
                                  burns=('stem.dropout',)))
    return out


def note_len_levers(case, domain='stems', only_stems=None):
    """One length lever per stem: the dominant written length, not every note."""
    out = []
    for tr in case.score.get('tracks', []):
        name = tr.get('name')
        if only_stems is not None and name not in only_stems:
            continue
        notes = tr.get('notes') or []
        if not notes:
            continue
        ds = [float(n.get('d') or 0.0) for n in notes]
        if not ds or max(ds) <= 0:
            continue
        cur = round(sum(ds) / len(ds), 4)
        out.append(base.Lever(f'note.{name}.d', domain, 'note_len', cur, max(0.01, cur - LEN_SPAN), cur + LEN_SPAN,
                              1.0 / 48, 'beats', f'{name} written note length (mean {cur:g} beats)', stem=name,
                              burns=('stem.dropout',)))
    return out


def stem_levers(case, rows, domain='stems'):
    stems = sorted({r.get('stem') for r in rows if r.get('stem')})
    only = stems or None
    return (gain_levers(case, domain, only) + eq_levers(case, domain, only)
            + onset_levers(case, domain, only) + note_len_levers(case, domain, only))


def spatial_levers(case, domain='spatial'):
    """Azimuth, elevation, distance and reverb send, where the score or a preset declares them."""
    out = []
    for tr in case.score.get('tracks', []):
        sp = tr.get('spatial') or {}
        name = tr.get('name')
        for key, kind, span, step, unit in (('az', 'az', 40.0, 5.0, 'deg'), ('azimuth', 'az', 40.0, 5.0, 'deg'),
                                            ('elev', 'elev', 20.0, 5.0, 'deg'), ('elevation', 'elev', 20.0, 5.0, 'deg'),
                                            ('dist', 'dist', 3.0, 0.5, 'm'), ('distance', 'dist', 3.0, 0.5, 'm')):
            if key in sp:
                cur = float(sp[key])
                out.append(base.Lever(f'spatial.{name}.{kind}', domain, kind, cur, cur - span, cur + span, step,
                                      unit, f'{name} {kind}', stem=name, burns=('spatial.', 'imm.')))
    send = ((case.mix or {}).get('space') or {}).get('send_by_role') or {}
    for role, cur in send.items():
        if not isinstance(cur, (int, float)):
            continue
        out.append(base.Lever(f'send.{role}', domain, 'send', float(cur), 0.0, 0.6, 0.02, 'frac',
                              f'{role} reverb send', burns=('spatial.', 'ambient_glue')))
    return out


def band_share_for(case, lever, row):
    """How much of a row's band one EQ band covers, as a first-order coefficient."""
    if lever.kind != 'eq' or not lever.stem:
        return None
    if row.get('stem') and row['stem'] != lever.stem:
        return None
    band = margins.band_of(row)
    if not band:
        return None
    got = base.psd(case, lever.stem)
    if got is None:
        return None
    f, p = got
    _i = lever.id.rsplit('.', 1)[-1]
    b = _bands(case, lever.stem)[int(_i)]
    kind = str(b.get('type') or 'peak').lower()
    f0 = float(b.get('f') or b.get('freq') or 1000.0)
    edges = base.shelf_band(kind, f0) if kind in ('lp', 'hp', 'highshelf', 'lowshelf') else base.eq_band(kind, f0, b.get('q'))
    return base.energy_share(f, p, band, edges)
