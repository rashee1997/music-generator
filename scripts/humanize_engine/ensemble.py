# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Sections: expanding one written line into players, and the asynchrony field they share."""
import zlib

import numpy as np


ENSEMBLE_KEYS = ('players', 'spread_cents', 'spread_ms', 'vel_spread')


def ensemble_expand(notes, players=4, spread_cents=5.0, spread_ms=10.0, vel_spread=3.0, bpm=96.0, seed=0):
    """One written line -> `players` independent players of a section, as notes for the renderer.

    A sampled section track is one player multiplied, which is why a large string or brass section can read as a
    single very good player rather than a room of them. Real sections are a few cents apart (measured standard
    deviations of 2-13 cents in small violin sections, ISMA 2019; 14 cents is the tolerated F0 scatter in a choir,
    Ternstrom 1993), their bow/breath onsets are 20-50 ms apart (Rasch; Keller), and no two players have the same
    bow pressure, so each has a fixed intonation, timing and level offset, with per-note jitter on top.

    Each player gets one fixed offset drawn once (so it is the same player for the whole piece) and one small
    per-note deviation. `c` is added to any cents already on the note, so a microtonal line keeps its own tuning.
    `spread_ms` is a peak offset in milliseconds at the score's tempo; it is converted to beats here.

    Use it on a section part, not on a drum kit or a solo: a solo is one player by definition, and the engine's
    other humanisation already covers that. Values are starting values until a piece is measured.
    """
    n_pl = int(players)
    if n_pl < 2:
        raise ValueError('ensemble: players must be at least 2 (a solo is not a section)')
    if n_pl > 8:
        raise ValueError('ensemble: above 8 players, use a real multisampled section')
    if float(spread_cents) < 0.0 or float(spread_ms) < 0.0 or float(vel_spread) < 0.0:
        raise ValueError('ensemble: spread_cents, spread_ms and vel_spread cannot be negative')
    rng = np.random.default_rng(int(seed) + 104729)
    # stratified offsets: every player is somewhere in the section, not four copies drawn from a bell curve
    base = np.linspace(-1.0, 1.0, n_pl)
    base = base + rng.uniform(-0.3, 0.3, n_pl) / max(n_pl - 1, 1)
    cents = base * float(spread_cents)
    delay_ms = base * float(spread_ms) + rng.normal(0.0, max(0.5, float(spread_ms) * 0.2), n_pl)
    level = rng.normal(0.0, float(vel_spread), n_pl)
    length = 1.0 + rng.normal(0.0, 0.02, n_pl)
    beats_per_ms = float(bpm) / 60000.0
    out = []
    for nt in notes:
        for k in range(n_pl):
            e = dict(nt)
            e['t'] = float(nt['t']) + float(delay_ms[k]) * beats_per_ms
            e['c'] = float(nt.get('c', 0.0)) + float(cents[k]) + float(rng.normal(0.0, max(0.2, float(spread_cents) * 0.12)))
            e['d'] = max(0.02, float(nt.get('d', 1.0)) * float(length[k]))
            v = nt.get('v', 0.7)
            if float(v) <= 1.0:
                # a level offset in MIDI units is a fraction of the velocity scale, not of the note's own value
                e['v'] = float(np.clip(float(v) * (1.0 + float(level[k]) / 127.0), 0.01, 1.0))
            else:
                e['v'] = float(np.clip(float(v) + float(level[k]), 1.0, 127.0))
            e['player'] = k
            out.append(e)
    out.sort(key=lambda z: (z['t'], z['p']))
    return out


# ------------------------------------------------------------------------------------------------
# The ensemble asynchrony field: one stable vertical offset per named part, shared by the piece.
# ------------------------------------------------------------------------------------------------
_STRING_WORDS = ('violin', 'viola', 'cello', 'contrabass', 'double bass', 'string', 'fiddle')
_WIND_WORDS = ('flute', 'piccolo', 'clarinet', 'oboe', 'bassoon', 'sax', 'recorder', 'bansuri', 'ney', 'shakuhachi')
_BRASS_WORDS = ('trumpet', 'trombone', 'horn', 'tuba', 'brass', 'cornet', 'flugel')


def family_of(track):
    """The instrument family a part's asynchrony is drawn from (a coarse, stable label)."""
    role = str((track or {}).get('role') or '').lower()
    inst = str((track or {}).get('instrument') or '').lower()
    if role == 'drum':
        return 'drums'
    if role == 'bass' or 'bass' in inst:
        return 'bass'
    if role == 'vocal':
        return 'vocal'
    if any(w in inst for w in _STRING_WORDS):
        return 'strings'
    if any(w in inst for w in _WIND_WORDS):
        return 'winds'
    if any(w in inst for w in _BRASS_WORDS):
        return 'brass'
    if any(w in inst for w in ('piano', 'celesta', 'harpsichord', 'organ', 'keys', 'rhodes')):
        return 'keys'
    if any(w in inst for w in ('guitar', 'lute', 'harp', 'sitar', 'kora', 'banjo', 'mandolin')):
        return 'guitar'
    if role in ('pad', 'texture', 'drone'):
        return 'pad'
    return 'other'


def asynchrony_field(score, seed=1):
    """{part name: signed ms} for every named track, plus a cache signature.

    The block is score data: `"asynchrony": {"amount_ms": 12}`. Zero or absent means no field at all, so a
    score that does not ask for one renders exactly as before. Each part's offset is a function of its own
    name, family and the seed only: it does not depend on which other tracks exist or on their order, which
    is what lets the renderer cache a stem per track and still keep the ensemble consistent.
    """
    blk = (score or {}).get('asynchrony') or {}
    if not isinstance(blk, dict):
        raise ValueError(f"score.asynchrony must be an object, got {type(blk).__name__}")
    unknown = sorted(set(blk) - {'amount_ms'})
    if unknown:
        raise ValueError(f"score.asynchrony: unknown key(s) {', '.join(unknown)}; known: amount_ms")
    amount = float(blk.get('amount_ms', 0.0) or 0.0)
    if amount < 0.0 or amount > 80.0:
        raise ValueError('score.asynchrony.amount_ms: expected 0..80')
    if amount <= 0.0:
        return {}, None
    table = {}
    cap = 35.0
    try:
        import presets
        cfg = presets.get('humanize', 'asynchrony')
        table = cfg.get('families') or {}
        cap = float(cfg.get('cap_ms', cap))
    except (KeyError, ValueError, ImportError):
        table = {}
    out = {}
    for tr in (score or {}).get('tracks', []) or []:
        name = str(tr.get('name') or '')
        if not name:
            continue
        weight = float(table.get(family_of(tr), table.get('other', 0.2)))
        jitter = np.random.default_rng(int(seed) * 1000003 + zlib.crc32(name.encode('utf-8'))).normal(0.0, amount * 0.15)
        out[name] = float(np.clip(amount * weight + jitter, -cap, cap))
    sig = tuple(sorted((k, round(v, 3)) for k, v in out.items())) or None
    return out, sig
