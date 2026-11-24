# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""What the humanizer did, measured: spread, coupling, and the numbers a reviewer reads."""
import numpy as np

import expectation

from .config import FIG


def _resolved(cfg):
    from .config import resolve
    return resolve(cfg)


def coupling_report(events, tm, tonic=None):
    """How closely a line's timing and loudness follow its melodic surprise, as Spearman rank correlations over its notes:
    {'ic_timing_rho': IC against the onset's offset from the tempo map (ms), 'ic_vel_rho': IC against velocity,
    'notes': n}. None where the line has too few notes (under 8) or no spread in surprise. Rubato, drift and the other
    rules move the timing too, so the timing rho is smaller than the share the coupling alone would give."""
    from scipy.stats import spearmanr
    tonic = tonic if tonic is not None else getattr(tm, 'key', None)
    if tonic is None or len(events) < 8:
        return dict(ic_timing_rho=None, ic_vel_rho=None, notes=len(events))
    notes = [dict(t=e['beat'], p=e['p']) for e in sorted(events, key=lambda e_: (e_['beat'], e_['p']))]
    evs = sorted(events, key=lambda e_: (e_['beat'], e_['p']))
    z_ic, _ = expectation.note_z(notes, tonic)
    if float(np.std(z_ic)) < 1e-6:
        return dict(ic_timing_rho=None, ic_vel_rho=None, notes=len(events))
    dev = np.array([e['t'] for e in evs]) - np.asarray(tm.sec([e['beat'] for e in evs]), float)
    vel = np.array([e['v'] for e in evs], float)
    rho_t = spearmanr(z_ic, dev)[0] if float(np.std(dev)) > 1e-9 else None
    rho_v = spearmanr(z_ic, vel)[0] if float(np.std(vel)) > 1e-9 else None
    return dict(ic_timing_rho=None if rho_t is None else round(float(rho_t), 3),
                ic_vel_rho=None if rho_v is None else round(float(rho_v), 3), notes=len(events))


def event_stats(events, tm, cfg=None):
    """How far the humanized events moved from the nominal beat grid (what a human-ness check should see). With `cfg`
    (the groove preset the track used) and an active expectation coupling (ic_agogic_ms, ic_vel or h_breath_ms above 0)
    on a line, the correlations of `coupling_report` and the keys used are added: the gate's `expr.agogic_coupling` reads them."""
    if not events:
        return {}
    nom = tm.sec([e['beat'] for e in events])
    dev = (np.array([e['t'] for e in events]) - nom) * 1000.0
    v = np.array([e['v'] for e in events])
    out = dict(notes=len(events), timing_ms_mean=round(float(dev.mean()), 1), timing_ms_std=round(float(dev.std()), 1),
               vel_mean=round(float(v.mean()), 1), vel_std=round(float(v.std()), 1), vel_levels=int(len(set(v.tolist()))))
    if cfg is not None and events[0].get('role') in FIG + ('counter',):
        c = _resolved(cfg)
        used = {k: float(c.get(k, 0.0)) for k in ('ic_agogic_ms', 'ic_vel', 'h_breath_ms')}
        if any(used.values()):
            out.update(coupling=dict(used, **coupling_report(events, tm)))
    return out


def humanize_report(events):
    """Quick numbers a reviewer can read: velocity spread, timing deviation from a 16th grid."""
    if not events:
        return {}
    v = np.array([e['v'] for e in events])
    return dict(n=len(events), vel_mean=float(v.mean()), vel_std=float(v.std()),
                vel_unique=int(len(set(v.tolist()))))


# ------------------------------------------------------------------------------------------------
# The humanize report: the numbers a reviewer reads before claiming a performance is more human.
# ------------------------------------------------------------------------------------------------
def _beat_seconds(tm):
    try:
        bpm = float(np.atleast_1d(getattr(tm, 'base_bpm', 96.0)).ravel()[0])
    except Exception:
        bpm = 96.0
    return 60.0 / max(20.0, bpm)


def grid_metrics(events, tm):
    """How far a line sits from the grid, and how its loudness and length move with its timing.

    `timing_beat_sd` is the tempo-adjusted deviation (sDelta, in beats) used to compare performances at
    different tempi; `dnvr`/`dnodr` are the velocity and onset-deviation ratios GigaMIDI uses to separate
    expressive from mechanical MIDI; `swing_bur` is the mean beat-upbeat ratio of the shortest pairs.
    """
    if not events:
        return {'notes': 0}
    ev = sorted(events, key=lambda e_: (e_['t'], e_['p']))
    beat_s = _beat_seconds(tm)
    nom = np.asarray(tm.sec([e['beat'] for e in ev]), float)
    t = np.array([e['t'] for e in ev], float)
    dev = t - nom
    v = np.array([e['v'] for e in ev], float)
    d = np.array([e['dur'] for e in ev], float)
    out = dict(notes=len(ev), timing_ms_sd=round(float(dev.std() * 1000.0), 2),
               timing_beat_sd=round(float(dev.std() / beat_s), 4),
               vel_mean=round(float(v.mean()), 2), vel_sd=round(float(v.std()), 2),
               vel_levels=int(len(set(v.tolist()))))
    if len(dev) > 3 and float(dev.std()) > 1e-9:
        out['timing_lag1'] = round(float(np.corrcoef(dev[:-1], dev[1:])[0, 1]), 3)
    if len(v) > 3 and float(v.std()) > 1e-9 and float(d.std()) > 1e-9:
        out['vel_dur_r'] = round(float(np.corrcoef(v, d)[0, 1]), 3)
    # DNVR: how different the velocities of simultaneous notes are (a machine writes one level)
    groups = {}
    for e in ev:
        groups.setdefault(round(float(e['beat']) * 4), []).append(e)
    ratios = [float(np.ptp([x['v'] for x in g])) / max(1.0, float(np.mean([x['v'] for x in g])))
              for g in groups.values() if len(g) > 1]
    out['dnvr'] = round(float(np.mean(ratios)), 4) if ratios else None
    # DNODR: the onset spread of those same groups, relative to the line's own median interval
    gaps = np.diff(np.unique(np.round([e['t'] for e in ev], 6)))
    ioi = float(np.median(gaps)) if len(gaps) else 0.0
    spreads = []
    for g in groups.values():                    # the groups already hold their events: no rescan of the line per group
        if len(g) < 2 or ioi <= 1e-9:
            continue
        spreads.append(float(np.ptp([x['t'] for x in g])) / ioi)
    out['dnodr'] = round(float(np.mean(spreads)), 4) if spreads else None
    # swing: pairs whose onsets are a half-beat apart; BUR = long side / short side
    times = np.unique(np.round(t, 6))
    burs = []
    for i in range(len(times) - 1):
        on, off = float(times[i]), float(times[i + 1])
        if off <= on or on % 1.0 > 0.05:
            continue
        if abs((off % 1.0) - 0.5) > 0.12:
            continue
        short = off - on
        nxt = float(times[i + 2]) if i + 2 < len(times) else None
        if nxt is None or short <= 1e-9:
            continue
        burs.append(max(0.0, nxt - off) / short)
    out['swing_bur'] = round(float(np.mean(burs)), 3) if burs else None
    return out


def ensemble_metrics(events_by_part, tm):
    """Vertical spread: how far apart the parts play the same written beat (the ensemble asynchrony)."""
    beats = {}
    for name, events in (events_by_part or {}).items():
        for e in events or []:
            beats.setdefault(round(float(e['beat']) * 24), []).append((name, float(e['t'])))
    spreads = []
    for group in beats.values():
        parts = {n for n, _ in group}
        if len(parts) < 2:
            continue
        spreads.append(float(np.ptp([t for _, t in group])) * 1000.0)
    if not spreads:
        return {'parts': len(events_by_part or {}), 'asynchrony_sd_ms': None, 'asynchrony_mean_abs_ms': None}
    arr = np.asarray(spreads, float)
    return {'parts': len(events_by_part or {}), 'asynchrony_sd_ms': round(float(arr.std()), 2),
            'asynchrony_mean_abs_ms': round(float(arr.mean()), 2),
            'asynchrony_p95_ms': round(float(np.percentile(arr, 95)), 2)}


def humanize_metrics(events_by_part, tm):
    """Per-part grid metrics plus the ensemble spread, in one dict (what `humanize_report.py` prints)."""
    parts = {}
    for name, events in (events_by_part or {}).items():
        parts[name] = grid_metrics(events, tm)
    out = dict(parts=parts, ensemble=ensemble_metrics(events_by_part, tm))
    vals = [m['timing_beat_sd'] for m in parts.values() if m.get('timing_beat_sd') is not None]
    out['timing_beat_sd_mean'] = round(float(np.mean(vals)), 4) if vals else None
    return out
