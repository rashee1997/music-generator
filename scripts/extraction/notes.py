# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Multi-pitch note finding by iterative cancellation: pick the strongest fundamental, remove its harmonics, repeat.

Works on the semitone spectrum from spectrum.py, so a note an octave or a fifth above a louder one is still found
(its energy is not credited to the lower note's harmonics)."""
import numpy as np
from scipy import ndimage

from .music_db import voice_active
from .spectrum import harmonic_offsets


def salience(R, offs, weights):
    """Row m collects the energy at its harmonics: sum_h w_h * R[m + off_h]."""
    out = np.zeros_like(R)
    n = R.shape[0]
    for off, w in zip(offs, weights):
        if off < n:
            out[:n - off] += w * R[off:]
    return out


def allowed_mask(spec, priors, cfg):
    """(semitones, frames) bool: pitch m may sound at frame t if some voice active at t covers it. All True when no voice has a range."""
    n, T = spec['S'].shape
    pad = cfg['notes']['range_pad_semitones']
    span_pad = cfg['music_db']['span_pad_s']
    voices = [v for v in priors['voices'] if v['midi_lo'] is not None]
    if not voices or not cfg['notes']['declared_only']:
        return np.ones((n, T), bool)
    m = np.zeros((n, T), bool)
    rows = np.arange(n) + spec['midi_lo']
    for v in voices:
        on = np.array([voice_active(v, t, span_pad) for t in spec['times']])
        band = (rows >= v['midi_lo'] - pad) & (rows <= v['midi_hi'] + pad)
        m |= band[:, None] & on[None, :]
    return m


def pick_pitches(spec, priors, cfg):
    """Per iteration k: pitch row and strength for every frame. Returns (rows[k, T], strength[k, T])."""
    nc = cfg['notes']
    S = spec['S']
    n, T = S.shape
    offs = harmonic_offsets(cfg['spectrum']['harmonics'])
    w = np.array([cfg['spectrum']['harmonic_decay'] ** h for h in range(len(offs))])
    lo = spec['midi_lo']
    cand = np.arange(max(nc['midi_min'] - lo, 0), min(nc['midi_max'] - lo, n - 1) + 1)
    allowed = allowed_mask(spec, priors, cfg)[cand]
    R = S.copy()
    t_idx = np.arange(T)
    rows, strength = [], []
    nc = {**nc, 'frame_floor_db_lin': 10 ** (nc['frame_floor_db'] / 20.0)}
    for _ in range(nc['max_poly']):
        sal = salience(R, offs, w)[cand]
        sal = np.where(allowed, sal, 0.0)
        best = sal.argmax(axis=0)
        st = sal[best, t_idx]
        p = cand[best]
        if rows:
            st = np.where(st >= nc['frame_floor_db_lin'] * strength[0], st, 0.0)       # later picks must stand out of the frame's loudest
        st = np.where(R[p, t_idx] >= nc['fund_min_rel'] * st / w.sum(), st, 0.0)       # the fundamental itself must be there
        rows.append(p)
        strength.append(st)
        idx = np.minimum(p[None, :] + np.array(offs)[:, None], n - 1)            # (H, T) rows of the note's harmonics
        A = R[idx, t_idx[None, :]]
        sm = A.copy()                                                            # smoothness: a harmonic cannot be far above its neighbours
        sm[1:-1] = np.minimum(A[1:-1], 0.5 * (A[:-2] + A[2:]))
        sm[-1] = np.minimum(A[-1], A[-2])
        env = nc['harmonic_cap'] * A.max(axis=0)[None, :] * (cfg['spectrum']['harmonic_decay'] ** np.arange(len(offs)))[:, None]
        R[idx, t_idx[None, :]] -= nc['cancel_frac'] * np.minimum(sm, env)
    return np.array(rows), np.array(strength)


def roll_from_picks(rows, strength, n, floor):
    """Piano roll (semitones, frames) of pick strengths at or above `floor`."""
    roll = np.zeros((n, rows.shape[1]), 'float32')
    t = np.arange(rows.shape[1])
    for r, s in zip(rows, strength):
        ok = s >= floor
        roll[r[ok], t[ok]] = np.maximum(roll[r[ok], t[ok]], s[ok])
    return roll


def notes_from_roll(roll, spec, priors, cfg):
    nc = cfg['notes']
    hop = spec['hop_s']
    gap = max(int(round(nc['gap_ms'] / 1000 / hop)), 1)
    min_len = max(int(round(nc['min_note_ms'] / 1000 / hop)), 1)
    notes = []
    for i in range(roll.shape[0]):
        on = roll[i] > 0
        if not on.any():
            continue
        on = ndimage.binary_closing(on, structure=np.ones(gap + 1)) if gap > 0 else on
        lab, cnt = ndimage.label(on)
        for k in range(1, cnt + 1):
            idx = np.where(lab == k)[0]
            if len(idx) < min_len:
                continue
            seg = roll[i, idx[0]:idx[-1] + 1]
            notes.append({'midi': int(i + spec['midi_lo']), 'start_s': float(idx[0] * hop), 'end_s': float((idx[-1] + 1) * hop),
                          'strength': float(seg.max()), 'mean': float(seg[seg > 0].mean())})
    notes = bridge_gaps(sorted(notes, key=lambda n: (n['midi'], n['start_s'])), spec, cfg)
    mid = lambda n: 0.5 * (n['start_s'] + n['end_s'])
    pad = nc['range_pad_semitones']
    for n in notes:
        n['voices'] = [v['id'] for v in priors['voices'] if v['midi_lo'] is not None and v['midi_lo'] - pad <= n['midi'] <= v['midi_hi'] + pad
                       and voice_active(v, mid(n), cfg['music_db']['span_pad_s'])]
    return suppress_leakage(sorted(notes, key=lambda n: (n['start_s'], n['midi'])), cfg)


def bridge_gaps(notes, spec, cfg):
    """Join two notes of one pitch when the spectrum still holds that pitch in between (a sustained note that was masked for a while).
    Overlapping harmonics of other voices may be what keeps it up; the level solver in separate.py decides how much really belongs to it."""
    nc = cfg['notes']
    hop, lo, S = spec['hop_s'], spec['midi_lo'], spec['S']
    out = []
    for n in notes:
        prev = out[-1] if out else None
        if prev and prev['midi'] == n['midi'] and 0 < n['start_s'] - prev['end_s'] <= nc['bridge_s']:
            row = n['midi'] - lo
            gap = S[row, int(prev['end_s'] / hop):int(n['start_s'] / hop)]
            held = np.r_[S[row, int(prev['start_s'] / hop):int(prev['end_s'] / hop)], S[row, int(n['start_s'] / hop):int(n['end_s'] / hop)]]
            if len(gap) and len(held) and np.median(gap) >= nc['bridge_frac'] * np.median(held):
                prev['end_s'] = n['end_s']
                prev['strength'] = max(prev['strength'], n['strength'])
                continue
        out.append(dict(n))
    return out


def suppress_leakage(notes, cfg):
    """Drop a short note beside a much stronger one (a semitone or two away, touching in time): it is spectral leakage or an attack transient."""
    nc = cfg['notes']
    keep = []
    for n in notes:
        dur = n['end_s'] - n['start_s']
        ghost = any(o is not n and 0 < abs(o['midi'] - n['midi']) <= nc['leak_semitones']
                    and ((dur < nc['leak_max_s'] and o['strength'] >= nc['leak_ratio'] * n['strength']
                          and o['start_s'] - nc['leak_touch_s'] <= n['end_s'] and o['end_s'] + nc['leak_touch_s'] >= n['start_s'])
                         or (abs(o['midi'] - n['midi']) <= 1 and o['strength'] >= nc['leak_strong_ratio'] * n['strength']
                             and min(o['end_s'], n['end_s']) - max(o['start_s'], n['start_s']) >= 0.6 * dur)) for o in notes)
        if not ghost:
            keep.append(n)
    return keep


def find_notes(spec, priors, cfg):
    """Notes [{midi, start_s, end_s, strength, mean, voices}] plus the roll. `voices` lists the declared voices that could play it ([] = undeclared)."""
    rows, st = pick_pitches(spec, priors, cfg)
    floor = float(np.percentile(st[0][st[0] > 0], cfg['notes']['reference_percentile']) if (st[0] > 0).any() else 0.0)
    floor *= 10 ** (cfg['notes']['salience_floor_db'] / 20.0)
    roll = roll_from_picks(rows, st, spec['S'].shape[0], floor)
    return notes_from_roll(roll, spec, priors, cfg), roll
