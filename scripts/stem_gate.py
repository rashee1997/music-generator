# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""stem_gate.py - the gate that runs on each stem before mixing.

    rows, meta = run_stem_gate(score, stems, sr=44100)
    if meta['fails']:
        ... stop before mixer.mix_and_master ...

A stem FAIL stops the run: a click on one stem, a cut at a section boundary, a dead part or a tick train must be fixed
before the mixer can average it away. The mix gate (quality_gate.run_gate) still certifies; this gate only decides whether
mixing is allowed.

Every row is a gate-profile row: the piece's type (score "piece_type", else inferred, else melodic) decides whether the
row applies, its parameters, and whether it is relaxed or skipped with a written reason. The profile is the same object
`gate_profiles.resolve` returns for the mix gate, so a piece cannot be strict on the master and lax on the stems.

Measurements only: no synthesis, EQ, mixing or preset values.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import gate_checks as gc
import gate_profiles
from gate_audio import Signal, DECIM_SR

PERCUSSIVE = {'drum', 'drums', 'percussion', 'kit', 'brush', 'shaker', 'cymbal', 'kick', 'snare', 'hat', 'tom'}
TONAL_ROLES = {'melody', 'pad', 'chord', 'arp', 'counter', 'bass', 'drone', 'harmony', 'lead'}
VOCAL_HINTS = ('vocal', 'voice', 'choir', 'hum', 'singer', 'soprano', 'alto', 'tenor', 'bass_voice')


def _track(score, name):
    return next((t for t in score.get('tracks', []) if t.get('name') == name), None)


def _is_percussive(track):
    if not track:
        return False
    role = str(track.get('role') or '').lower()
    inst = str(track.get('instrument') or '').lower()
    name = str(track.get('name') or '').lower()
    return role == 'drum' or any(h in inst or h in name for h in PERCUSSIVE)


def _is_vocal(track):
    if not track:
        return False
    blob = ' '.join(str(track.get(k) or '') for k in ('name', 'instrument', 'role', 'preset')).lower()
    return any(h in blob for h in VOCAL_HINTS)


def _note_intervals(track, bpm):
    out = []
    for n in track.get('notes', []) if track else []:
        try:
            a = float(n['t']) * 60.0 / bpm
            d = float(n.get('d', 0)) * 60.0 / bpm
        except (KeyError, TypeError, ValueError):
            continue
        if d > 0:
            out.append((a, a + d))
    return out


MELODIC_ROLES = {'melody', 'lead', 'counter', 'vocal'}


def _beatless(track, bpm):
    """True when this stem should have no pulse: not percussive, and not a part the score gives a rhythm.

    A melodic part is excluded on purpose. `stem.tick` asks whether a stem that should hold still is ticking; a
    played melody legitimately has repeated bow changes and a vibrato (a 6 Hz violin vibrato is a 163 ms period),
    and reading that as a tick faults the playing, not a defect.
    """
    if _is_percussive(track):
        return False
    if str((track or {}).get('role') or '').lower() in MELODIC_ROLES:
        return False
    starts = sorted(a for a, _ in _note_intervals(track, bpm))
    if len(starts) < 3:
        return True
    ioi = np.diff(starts)
    cv = float(np.std(ioi) / (np.mean(ioi) + 1e-12))
    return cv > 0.05


def _ends_at_end(track, bpm, dur, tol=0.25):
    iv = _note_intervals(track, bpm)
    return bool(iv) and max(b for _, b in iv) >= dur - tol


def _level_in(sig, a, b):
    """Energy-mean level over the window: averaging dB values counts silence as a huge negative and under-reads a drum."""
    db, times = sig.frame_db()
    m = (times >= a) & (times <= b)
    if not np.any(m):
        return float('nan')
    return float(10.0 * np.log10(np.mean(10.0 ** (db[m] / 10.0)) + 1e-12))


def _note_window_level(sig, a, b):
    """Level over the note, capped at 0.5 s so a long pad note does not average across sections."""
    return _level_in(sig, a, min(b, a + 0.5))


def check_dead(sig, track, score, secs, under_db=12.0, floor_db=-70.0):
    bpm = float(score.get('bpm') or 120.0)
    iv = _note_intervals(track, bpm)
    if not iv:
        return None
    active = []
    for s in secs:
        levels = []
        for a, b in iv:
            aa, bb = max(a, s['start_s']), min(b, s['end_s'])
            if bb <= aa:
                continue
            lvl = _note_window_level(sig, aa, bb)
            if np.isfinite(lvl):
                levels.append(lvl)
        if levels:
            # median over the notes in the section, not the section mean: a drum part is mostly silence between hits
            active.append((s, float(np.median(levels))))
    if not active:
        return None
    own = float(np.median([lvl for _, lvl in active]))
    dyns = [s['dyn'] for s, _ in active]
    med_dyn = float(np.median(dyns)) if dyns else 0.5
    worst, worst_s, table = 0.0, None, []
    for s, lvl in active:
        exp = own + (20.0 * np.log10(s['dyn'] / med_dyn) if med_dyn > 0 and s['dyn'] > 0 else 0.0)
        table.append(dict(section=s['name'], start_s=s['start_s'], measured_db=round(lvl, 2),
                          expected_db=round(exp, 2), dyn=s['dyn']))
        if lvl < floor_db and max(l for _, l in active) < floor_db:
            short = floor_db - lvl
            if short > worst:
                worst, worst_s = short, s['start_s']
            continue
        if s['dyn'] >= 0.25:
            short = exp - lvl
            if short > under_db and short > worst:
                worst, worst_s = short, s['start_s']
    dead = max(lvl for _, lvl in active) < floor_db
    dropped = worst > under_db
    value = worst if dropped else max(0.0, floor_db - own if dead else 0.0)
    times = [worst_s] if worst_s is not None else []
    detail = (f'own median {own:.1f} dBFS, worst section shortfall {worst:.1f} dB '
              f'(limit {under_db:g} dB), active sections {len(active)}; '
              + ('all sections silent' if dead else ('dropped in a section' if dropped else 'follows the curve')))
    return dict(value=float(value), threshold=float(under_db), unit='dB',
                margin=float(value - under_db), times=[float(t) for t in times],
                detail=detail, fail=bool(dead or dropped), table=table, dead=bool(dead))


def _res_row(level, name, res, stem=None):
    detail = (f'stem "{stem}": ' if stem else '') + res.get('detail', '')
    d = dict(row=name, stage='stem', stem=stem, level=level,
             value=float(res.get('value', 0.0)), unit=res.get('unit', ''),
             threshold=float(res.get('threshold', 0.0)), margin=float(res.get('margin', 0.0)),
             worst_times_s=[round(float(t), 4) for t in res.get('times', [])][:8],
             calibrated=False, detail=detail)
    for k, v in res.items():
        if k in ('value', 'threshold', 'unit', 'margin', 'times', 'detail'):
            continue
        d[k] = v
    return (level, name, detail), d


def _emit(rows, metrics, rid, level, res, name):
    r, m = _res_row(level, rid, res, name)
    rows.append(r)
    metrics.append(m)


def _skip(rows, metrics, rid, name, gp):
    """A profile skipped this row: say so, with the profile's reason. Never silently disappear."""
    cfg = gp.rows.get(gate_profiles.canonical(rid)) or {}
    detail = f'stem "{name}": SKIPPED by profile {gp.label}: {cfg.get("reason") or "no reason given"}'
    rows.append(('INFO', rid, detail))
    metrics.append(dict(row=rid, stage='stem', stem=name, level='INFO', value=0.0, unit='', threshold=0.0,
                        margin=0.0, worst_times_s=[], calibrated=False, skipped=True, detail=detail))


def _stem_rows(name, audio, track, score, secs, dur, gp):
    rows, metrics = [], []
    try:
        sig = Signal(audio, score.get('_sr', 44100))
    except Exception as exc:
        rows.append(('FAIL', 'stem.integrity', f'stem "{name}": not measurable ({exc})'))
        metrics.append(dict(row='stem.integrity', stage='stem', stem=name, level='FAIL', value=0.0,
                            unit='', threshold=0.0, margin=0.0, worst_times_s=[], calibrated=False,
                            detail=str(exc)))
        return rows, metrics
    bpm = float(score.get('bpm') or 120.0)

    if gp.on('stem.dc'):
        res = gc.check_dc(sig, dc_max=gp.param('stem.dc', 'dc_max'))
        _emit(rows, metrics, 'stem.dc', 'FAIL' if res['value'] > res['threshold'] else 'PASS', res, name)
    else:
        _skip(rows, metrics, 'stem.dc', name, gp)

    if gp.on('stem.clipping'):
        res = gc.check_clipping(sig)
        _emit(rows, metrics, 'stem.clipping', 'FAIL' if res['value'] > 0 else 'PASS', res, name)
    else:
        _skip(rows, metrics, 'stem.clipping', name, gp)

    if gp.on('stem.clicks'):
        res = gc.check_clicks(sig, mad_z=gp.param('stem.clicks', 'mad_z'),
                              floor_fs=gp.param('stem.clicks', 'floor_fs'),
                              cluster_gap_ms=gp.param('stem.clicks', 'cluster_gap_ms'),
                              isolate_ms=gp.param('stem.clicks', 'isolate_ms'))
        level = 'FAIL' if (res.get('mad_count', 0) > 0 or res.get('lpc_count', 0) > 0) else 'PASS'
        _emit(rows, metrics, 'stem.clicks', level, res, name)
    else:
        _skip(rows, metrics, 'stem.clicks', name, gp)

    if gp.on('stem.dropout'):
        # only a hole inside a sounding note is a dropout; a gap between phrases is the score's rest (see gate_checks)
        sounding = _note_intervals(track, bpm) if track is not None else None
        res = gc.check_dropout(sig, min_ms=gp.param('stem.dropout', 'min_ms'),
                               max_ms=gp.param('stem.dropout', 'max_ms'),
                               floor_below_db=gp.param('stem.dropout', 'floor_below_db'), sounding=sounding)
        _emit(rows, metrics, 'stem.dropout', 'FAIL' if res.get('holes') else 'PASS', res, name)
    else:
        _skip(rows, metrics, 'stem.dropout', name, gp)

    if not _is_percussive(track):
        if gp.on('stem.cut'):
            boundaries = [s['start_s'] for s in secs if s['start_s'] > 0.05]
            res = gc.check_cut(sig, boundaries, drop_db=gp.param('stem.cut', 'drop_db'),
                               location_ms=gp.param('stem.cut', 'location_ms'))
            _emit(rows, metrics, 'stem.cut', 'FAIL' if res['value'] > res['threshold'] else 'PASS', res, name)
        else:
            _skip(rows, metrics, 'stem.cut', name, gp)

    if _ends_at_end(track, bpm, dur):
        if gp.on('stem.end'):
            res = gc.check_abrupt_end(sig, expected_dur=dur, floor_db=gp.param('stem.end', 'floor_db'),
                                      min_decay_db=gp.param('stem.end', 'min_decay_db'))
            if not res.get('skipped'):
                _emit(rows, metrics, 'stem.end', 'FAIL' if res.get('fail') else 'PASS', res, name)
        else:
            _skip(rows, metrics, 'stem.end', name, gp)

    iv = _note_intervals(track, bpm) if track is not None else []
    # Percussive stems are excluded: a drum note's written length is a grid cell, not a sound length, so the space
    # between the last hit and the bar line is not silence to trim. An `sfx` track is the same case: its written
    # length is a trigger for a one-shot sound, and the sound's own attack and decay are the instrument, not an edit.
    if iv and not _is_percussive(track) and str((track or {}).get('role') or '').lower() != 'sfx':
        if gp.on('stem.edge'):
            res = gc.check_edge(sig, min(a for a, _ in iv), max(b for _, b in iv),
                                max_silence_ms=gp.param('stem.edge', 'max_silence_ms'))
            _emit(rows, metrics, 'stem.edge', 'FAIL' if res.get('fail') else 'PASS', res, name)
        else:
            _skip(rows, metrics, 'stem.edge', name, gp)

    if track is not None and _beatless(track, bpm):
        if gp.on('stem.tick'):
            res = gc.check_tick(sig, rho_min=gp.param('stem.tick', 'rho'),
                                min_events=int(gp.param('stem.tick', 'min_events')),
                                cv_max=gp.param('stem.tick', 'cv_max'),
                                min_ripple_db=gp.param('stem.tick', 'ripple_db'))
            _emit(rows, metrics, 'stem.tick', 'FAIL' if res.get('periodic') else 'PASS', res, name)
        else:
            _skip(rows, metrics, 'stem.tick', name, gp)

    if track is not None:
        res = check_dead(sig, track, score, secs, under_db=gp.param('stem.dead', 'under_db'),
                         floor_db=gp.param('stem.dead', 'floor_db'))
        if res is not None:
            if gp.on('stem.dead'):
                _emit(rows, metrics, 'stem.dead', 'FAIL' if res.get('fail') else 'PASS', res, name)
            else:
                _skip(rows, metrics, 'stem.dead', name, gp)

    if track is not None and not _is_percussive(track) and str(track.get('role', '')).lower() in TONAL_ROLES:
        if gp.on('stem.flatness'):
            res = gc.check_flatness(sig, threshold=gp.param('stem.flatness', 'threshold'),
                                    min_ms=gp.param('stem.flatness', 'min_ms'))
            _emit(rows, metrics, 'stem.flatness', 'FAIL' if res.get('windows', 0) > 0 else 'PASS', res, name)
        else:
            _skip(rows, metrics, 'stem.flatness', name, gp)

    if _is_vocal(track):
        if gp.on('stem.vocal'):
            dc = gc.check_dc(sig, dc_max=gp.param('stem.dc', 'dc_max') if gp.on('stem.dc') else 0.001)
            clicks = gc.check_clicks(sig, run_lpc=False)
            bad = dc['value'] > dc['threshold'] or clicks.get('mad_count', 0) > 0
            detail = f'vocal stem: DC {dc["value"]:.5f}, {clicks.get("mad_count", 0)} click event(s)'
            rows.append(('FAIL' if bad else 'PASS', 'stem.vocal', detail))
            metrics.append(dict(row='stem.vocal', stage='stem', stem=name, level='FAIL' if bad else 'PASS',
                                value=float(clicks.get('mad_count', 0)), unit='events', threshold=0.0,
                                margin=float(clicks.get('mad_count', 0)), worst_times_s=[], calibrated=False,
                                detail=detail))
        else:
            _skip(rows, metrics, 'stem.vocal', name, gp)
    return rows, metrics


def run_stem_gate(score, stems, sr=44100, workers=2, report_dir=None, mode='full'):
    """Run every stem row through the piece's gate profile. Returns (rows, meta)."""
    t0 = time.perf_counter()
    score = dict(score)
    score['_sr'] = int(sr)
    gp = gate_profiles.resolve(score)
    dur = max((len(x) / float(sr) for x in stems.values()), default=0.0)
    secs = gc.section_bounds(score, dur)
    items = sorted(stems.items())
    workers = max(1, min(int(workers), len(items) or 1))
    timings, results = {}, []

    def work(item):
        name, audio = item
        a = time.perf_counter()
        rows, metrics = _stem_rows(name, audio, _track(score, name), score, secs, dur, gp)
        return name, rows, metrics, (time.perf_counter() - a) * 1000.0

    if workers > 1 and len(items) > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for name, rows, metrics, ms in ex.map(work, items):
                timings[name] = ms
                results.append((name, rows, metrics))
    else:
        for item in items:
            name, rows, metrics, ms = work(item)
            timings[name] = ms
            results.append((name, rows, metrics))

    rows, metrics = [], []
    for name, r, m in results:
        rows.extend(r)
        metrics.extend(m)

    # present: every score track with notes has a stem; extra stems are a WARN
    names = {n for n, _ in items}
    if gp.on('stem.present'):
        for tr in score.get('tracks', []):
            if tr.get('role') == 'environment' or str(tr.get('instrument', '')).startswith('env:'):
                continue
            if tr.get('notes') and tr.get('name') not in names:
                detail = f'score track "{tr.get("name")}" has notes but no stem'
                rows.append(('FAIL', 'stem.present', detail))
                metrics.append(dict(row='stem.present', stage='stem', stem=tr.get('name'), level='FAIL',
                                    value=1.0, unit='count', threshold=0.0, margin=1.0,
                                    worst_times_s=[], calibrated=True, detail=detail))
        for name in sorted(names - {t.get('name') for t in score.get('tracks', [])}):
            detail = f'stem "{name}" has no track in the score'
            rows.append(('WARN', 'stem.present', detail))
            metrics.append(dict(row='stem.present', stage='stem', stem=name, level='WARN', value=1.0,
                                unit='count', threshold=0.0, margin=1.0, worst_times_s=[],
                                calibrated=True, detail=detail))

    # duplicate stems: a copy routed twice is a dead part's mirror image
    if len(items) >= 2:
        max_corr = gp.param('stem.duplicate', 'max_corr') if gp.on('stem.duplicate') else None
        monos = {}
        if max_corr is not None:
            for name, x in items:
                try:
                    monos[name] = Signal(x, sr).decim
                except Exception:
                    continue
        for i, (a, xa) in enumerate(sorted(monos.items())):
            for b, xb in sorted(monos.items())[i + 1:]:
                n = min(len(xa), len(xb))
                if n < DECIM_SR:
                    continue
                xa_, xb_ = xa[:n], xb[:n]
                if np.std(xa_) < 1e-6 or np.std(xb_) < 1e-6:
                    continue
                c = float(np.corrcoef(xa_, xb_)[0, 1])
                if c > max_corr:
                    detail = f'stems "{a}" and "{b}" are the same signal (correlation {c:.4f}): one is routed twice'
                    rows.append(('WARN', 'stem.duplicate', detail))
                    metrics.append(dict(row='stem.duplicate', stage='stem', stem=f'{a}/{b}', level='WARN',
                                        value=c, unit='correlation', threshold=max_corr, margin=c - max_corr,
                                        worst_times_s=[], calibrated=True, detail=detail))

    # the profile's own notes: chosen type, every relaxed or skipped row with its reason, an unknown type as FAIL
    rows.extend(gp.notes())
    fails = sum(1 for l, _, _ in rows if l == 'FAIL')
    warns = sum(1 for l, _, _ in rows if l == 'WARN')
    total_ms = (time.perf_counter() - t0) * 1000.0
    meta = dict(stage='stem', mode=mode, fails=fails, warns=warns, rows=len(rows), profile=gp.label,
                total_ms=total_ms, timings=timings, workers=workers, metrics=metrics,
                sections=secs, duration_s=dur)
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
        with open(os.path.join(report_dir, 'stem_gate.json'), 'w', encoding='utf-8') as fh:
            json.dump(dict(meta=meta, rows=[dict(level=l, row=n, detail=d) for l, n, d in rows]), fh, indent=2)
        with open(os.path.join(report_dir, 'stem_gate.txt'), 'w', encoding='utf-8') as fh:
            fh.write(f'stem gate: {fails} FAIL, {warns} WARN, {len(rows)} rows, profile {gp.label}, {total_ms:.0f} ms\n')
            for l, n, d in rows:
                fh.write(f'[{l}] {n}: {d}\n')
    return rows, meta
