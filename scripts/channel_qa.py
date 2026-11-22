# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""channel_qa.py - measure a delivered multichannel file channel by channel and bar by bar.

The same measurements run on every channel count:

* a declared loudspeaker layout uses its real speaker positions (ITU-R BS.2051 system J, stereo, 22.2, ...);
* a fifth-order AmbiX file (36 ACN/SN3D channels) is decoded through AllRAD/max-rE to the 36-point
  `ambix_qa_36` virtual sphere, so it can be judged like a real array;
* a file with no declared layout is still checked per channel (jump, dropout, polarity), just without
  spatial balance.

The per-bar test asks a deliberately narrow question. A channel that changes level for one bar only -
because of a missing send, a bad automation point, a dropped region or an inverted polarity - is isolated
against both neighbours, and the overall bar level must stay put. That last condition is what keeps a
deliberate one-bar accent (which also lifts the whole bar) from being read as a channel fault.

This module measures only. Thresholds come from the gate profile (`gate_profiles.ROWS`).
"""
import numpy as np

# Starting values, not calibrated against a corpus. They are registered as gate-profile parameters so a
# piece type can relax or skip a row with a reason rather than the engine hiding the measurement.
PARAMS = {
    'jump_db': 8.0,              # a one-bar channel move that neither neighbour shares
    'dropout_db': 15.0,          # a one-bar channel hole
    'balance_db': 4.0,           # a one-bar left/right, front/back or floor/height swing
    'stable_db': 3.0,            # how still the whole bar must be for an isolated channel fault
    'polarity_corr': -0.5,       # a bar correlated this negatively with both neighbours is inverted
    'polarity_neighbor': 0.2,    # ...while both neighbours must agree in polarity
}

_REPORT_LIMIT = 6


class ChannelLayoutError(ValueError):
    """The file and its declared target cannot be put on the layout the target promises."""


def _bar_edges(score, sr, duration):
    """Sample indices of bar starts plus the end, using the score's own tempo map (rubato included)."""
    n = int(round(float(duration) * float(sr)))
    if n <= 0:
        return np.array([0], dtype=int)
    ts = (score or {}).get('ts', [4, 4])
    if isinstance(ts, str) and '/' in ts:
        num, den = (float(x) for x in ts.split('/', 1))
    else:
        try:
            num, den = float(ts[0]), float(ts[1] if len(ts) > 1 else 4)
        except (TypeError, IndexError, ValueError):
            num, den = 4.0, 4.0
    beats_per_bar = num * 4.0 / den if den else 4.0
    if not np.isfinite(beats_per_bar) or beats_per_bar <= 0:
        return np.array([0, n], dtype=int)
    starts = [0.0]
    try:
        import humanize
        tm = humanize.tempo_map_for(score or {}, seed=(score or {}).get('seed', 1))
        beats = beats_per_bar
        while len(starts) < 4096:
            at = float(tm.sec(beats))
            if not np.isfinite(at) or at >= duration:
                break
            starts.append(max(0.0, at))
            beats += beats_per_bar
    except Exception:
        # A malformed tempo block must not hide a channel fault: fall back to the nominal tempo. The
        # caller reports the exception-free result; score validation is a different gate.
        bpm = float((score or {}).get('bpm', 90.0) or 90.0)
        bar_s = beats_per_bar * 60.0 / bpm if bpm > 0 else float(duration)
        if bar_s > 0:
            starts = list(np.arange(0.0, float(duration), bar_s))
    idx = np.unique(np.rint(np.asarray(starts, dtype=float) * sr).astype(int))
    idx = idx[(idx >= 0) & (idx < n)]
    if not len(idx) or idx[0] != 0:
        idx = np.r_[0, idx]
    if idx[-1] != n:
        idx = np.r_[idx, n]
    return idx


def _db(x):
    x = np.asarray(x, dtype=np.float64)
    return float(20.0 * np.log10(np.sqrt(np.mean(np.square(x)) + 1e-20)))


def _corr(a, b, max_lag=64):
    """Signed normalized cross-correlation at the best small lag.

    Zero-lag correlation of two bars of a sustained tone can be negative just because the bar boundary lands at
    a different phase. The best lag removes that boundary phase; an inverted bar still has a negative peak.
    """
    a = np.asarray(a, dtype=np.float64) - np.mean(a)
    b = np.asarray(b, dtype=np.float64) - np.mean(b)
    den = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    if den <= 1e-20:
        return 0.0
    c = np.correlate(a, b, mode='full')
    mid = len(b) - 1
    lo, hi = max(0, mid - int(max_lag)), min(len(c), mid + int(max_lag) + 1)
    i = lo + int(np.argmax(np.abs(c[lo:hi])))
    return float(c[i] / den)


def _level_matrix(signals, edges):
    signals = np.asarray(signals, dtype=np.float64)
    out = np.full((len(edges) - 1, signals.shape[1]), -120.0)
    for b in range(len(edges) - 1):
        seg = signals[edges[b]:edges[b + 1]]
        if len(seg):
            for c in range(signals.shape[1]):
                out[b, c] = _db(seg[:, c])
    return out


def _groups(positions):
    """Spatial groups that can be compared without inventing a layout: left/right, front/back, floor/height."""
    have = [(i, p) for i, p in enumerate(positions or []) if p is not None]
    out = []
    tests = (
        ('left/right', lambda p: p[0] < -1e-6, lambda p: p[0] > 1e-6),
        ('front/back', lambda p: abs(p[0]) <= 90.0, lambda p: abs(p[0]) > 90.0),
        ('floor/height', lambda p: p[1] <= 15.0, lambda p: p[1] > 15.0),
    )
    for label, a, b in tests:
        ia = [i for i, p in have if a(p)]
        ib = [i for i, p in have if b(p)]
        if len(ia) >= 2 and len(ib) >= 2:
            out.append((label, ia, ib))
    return out


def _energy(signals, a, b, idx):
    if a >= b or not idx:
        return 0.0
    seg = np.asarray(signals[a:b], dtype=np.float64)[:, idx]
    return float(np.sum(np.mean(np.square(seg), axis=0)))


def _conflicts(signals, levels, edges, positions, names, params):
    """Isolated per-bar channel faults and spatial balance swings."""
    signals = np.asarray(signals, dtype=np.float64)
    jump, drop, bal, pol = (float(params[k]) for k in
                            ('jump_db', 'dropout_db', 'balance_db', 'polarity_corr'))
    stable = float(params['stable_db'])
    neigh = float(params['polarity_neighbor'])
    groups = _groups(positions)
    found = []
    seen = set()

    def add(bar, ch, kind, delta, **extra):
        key = (bar, ch, kind)
        if key in seen:
            return
        seen.add(key)
        item = dict(bar=bar + 1, channel=ch + 1, channel_name=names[ch] if ch < len(names) else f'CH{ch + 1}',
                    kind=kind, delta_db=float(delta))
        item.update(extra)
        found.append(item)

    for b in range(1, max(1, len(edges) - 2)):
        prev, cur, nxt = levels[b - 1], levels[b], levels[b + 1]
        dprev, dnext = cur - prev, cur - nxt

        def isolated(ch):
            """The other channels stay put in this bar, so the move is one channel, not a whole-bar accent."""
            others = [i for i in range(len(cur)) if i != ch]
            if not others:
                return True
            still = (np.abs(cur[others] - prev[others]) <= stable) & \
                    (np.abs(cur[others] - nxt[others]) <= stable)
            return float(np.mean(still)) >= 0.5

        # A one-bar hole: both neighbours sit above it and agree with each other. The bar as a whole may
        # move (one channel of four is a real level change); the test is that the other channels did not.
        holes = np.where((cur < prev - drop) & (cur < nxt - drop) &
                         (np.abs(prev - nxt) <= stable))[0]
        holes = [int(ch) for ch in holes if isolated(int(ch))]
        for ch in holes:
            add(b, ch, 'dropout', float(prev[ch] - cur[ch]),
                neighbour_db=float(0.5 * (prev[ch] + nxt[ch])))
        # A one-bar lift or dip, away from both neighbours in the same direction. A mute is reported as a
        # dropout above, not twice.
        move = (dprev * dnext > 0.0) & (np.minimum(np.abs(dprev), np.abs(dnext)) > jump)
        if holes:
            move[holes] = False
        for ch in np.where(move)[0]:
            if isolated(int(ch)):
                add(b, int(ch), 'jump', float(0.5 * (dprev[ch] + dnext[ch])),
                    neighbour_db=float(0.5 * (prev[ch] + nxt[ch])))
        # One-bar channel polarity inversion: both neighbours correlate positively, the bar does not.
        if len(edges) > 3:
            a0, a1 = edges[b], edges[b + 1]
            for ch in range(signals.shape[1]):
                if levels[b, ch] <= -60.0:
                    continue
                x = signals[a0:a1, ch]
                p = signals[edges[b - 1]:edges[b], ch]
                n = signals[edges[b + 1]:edges[b + 2], ch]
                m = min(len(x), len(p), len(n))
                cp, cn = _corr(x[:m], p[:m]), _corr(x[:m], n[:m])
                if max(cp, cn) < pol and min(abs(cp), abs(cn)) > neigh:
                    add(b, ch, 'polarity', 0.0, corr_prev=cp, corr_next=cn)
        # One-bar spatial swing: the whole grouping moves while both neighbours agree.
        for label, ia, ib in groups:
            ep, ec, en = (_energy(signals, edges[b - 1], edges[b], ia),
                          _energy(signals, edges[b], edges[b + 1], ia),
                          _energy(signals, edges[b + 1], edges[b + 2], ia))
            fp, fc, fn = (_energy(signals, edges[b - 1], edges[b], ib),
                          _energy(signals, edges[b], edges[b + 1], ib),
                          _energy(signals, edges[b + 1], edges[b + 2], ib))
            if min(ep, en, fp, fn) <= 1e-20:
                continue
            rp, rc, rn = 10.0 * np.log10((ep + 1e-20) / (fp + 1e-20)), \
                10.0 * np.log10((ec + 1e-20) / (fc + 1e-20)), \
                10.0 * np.log10((en + 1e-20) / (fn + 1e-20))
            if abs(rc - rp) > bal and abs(rc - rn) > bal and abs(rp - rn) <= stable:
                add(b, -1, 'balance', rc - 0.5 * (rp + rn), group=label,
                    ratio_db=float(rc), neighbour_db=float(0.5 * (rp + rn)))
    return found


def prepare(score, audio, sr, target=None):
    """Put a delivered file on the positions it claims, or leave it per-channel when it claims none.

    Returns a dict with the signals to judge (`signals`), their positions (`positions`, None for an LFE or
    an undeclared channel), channel names, and how the mapping was made (`kind`).
    """
    import render_targets
    from spatial_engine import config, hoa

    x = np.asarray(audio, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    n = x.shape[1]
    if isinstance(target, str):
        tgt = render_targets.get(target) or {}
        tname = target
    elif isinstance(target, dict):
        tgt = target
        tname = target.get('name') or target.get('label') or 'target'
    else:
        tgt, tname = {}, ''
    if tgt.get('renderer') == 'hoa':
        order = int(tgt.get('ambisonic_order') or 0)
        expected = (order + 1) ** 2
        if n != expected:
            raise ChannelLayoutError(
                f'{n} channel(s) but AmbiX order {order} needs {expected} ({order + 1} squared)')
        gate = tgt.get('gate') or {}
        lay_name = gate.get('virtual_layout') or 'ambix_qa_36'
        spk = config.speakers(lay_name)
        need = int(gate.get('min_virtual_channels') or expected)
        if len(spk) < need:
            raise ChannelLayoutError(
                f'virtual layout {lay_name} has {len(spk)} speaker(s), below the {need} this target requires')
        d = hoa.allrad_matrix(spk, order)
        scale = np.concatenate([[np.sqrt(4.0 * np.pi / (2 * k + 1))] * (2 * k + 1)
                                for k in range(order + 1)])
        # AllRAD decodes the engine's orthonormal field; AmbiX is SN3D, so undo that per-order scale.
        decoded = x @ (d / scale[:, None]).T
        names = [s['name'] for s in spk]
        positions = [(float(s['azimuth']), float(s['elevation'])) for s in spk]
        note = (f'{n} ACN/SN3D channel(s), order {order}, decoded with AllRAD/max-rE to '
                f'{len(spk)} virtual speaker(s) ({lay_name})')
        return dict(signals=decoded, positions=positions, names=names, kind='ambix', layout=lay_name,
                    order=order, channels=n, virtual=len(spk), note=note, target=tname,
                    raw=x, raw_names=[f'ACN{i}' for i in range(n)])
    lay = tgt.get('layout')
    if lay:
        speakers = config.layout(lay).get('speakers') or []
        if n != len(speakers):
            raise ChannelLayoutError(f'{n} channel(s) but layout "{lay}" has {len(speakers)} speaker(s)')
        by_name = {s['name']: s for s in speakers}
        order = list(tgt.get('channel_order') or [])
        if len(order) != n:
            order = [s['name'] for s in speakers]
        positions, names = [], []
        for name in order:
            s = by_name.get(name)
            names.append(name)
            positions.append(None if (s is None or s.get('lfe')) else
                             (float(s['azimuth']), float(s['elevation'])))
        note = f'{n} channel(s) mapped to layout "{lay}" ({sum(p is not None for p in positions)} positioned)'
        return dict(signals=x, positions=positions, names=names, kind='layout', layout=lay, channels=n,
                    virtual=None, note=note, target=tname)
    names = [f'CH{i + 1}' for i in range(n)]
    note = f'{n} channel(s); no declared layout, so the checks are per channel (no spatial balance)'
    return dict(signals=x, positions=None, names=names, kind='channels', layout=None, channels=n,
                virtual=None, note=note, target=tname)


def analyse(score, audio, sr, target=None, params=None):
    """Channel mapping plus per-bar levels and conflicts. Raises ChannelLayoutError if the mapping is wrong."""
    p = dict(PARAMS)
    p.update({k: v for k, v in (params or {}).items() if k in p})
    prepared = prepare(score, audio, sr, target)
    edges = _bar_edges(score, sr, len(prepared['signals']) / float(sr))
    levels = _level_matrix(prepared['signals'], edges)
    conflicts = _conflicts(prepared['signals'], levels, edges, prepared['positions'],
                           prepared['names'], p)
    # An AmbiX channel fault is spread across every decoded speaker by the decoder, so it can fail the
    # isolation test in the virtual domain. The raw ACN channels are checked too: a lost or inverted ACN
    # channel is exactly the sort of one-bar fault this row exists to find.
    if prepared.get('raw') is not None:
        raw_levels = _level_matrix(prepared['raw'], edges)
        conflicts += _conflicts(prepared['raw'], raw_levels, edges, None, prepared['raw_names'], p)
        conflicts.sort(key=lambda c: (c['bar'], c['channel'], c['kind']))
    prepared.update(edges=edges, levels=levels, bars=len(edges) - 1, conflicts=conflicts, params=p)
    return prepared
