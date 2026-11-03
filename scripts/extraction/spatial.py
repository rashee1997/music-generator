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

"""Stage `spatial`: where each source sits, how wide it is, whether it moves, and the room it was mixed in.

Measured on the stereo stems (they kept the mix's channel balance), never read from a table:
* azimuth from the level difference between left and right (pan-law inverse; -90 = hard left, +90 = hard right),
* inter-channel time difference and correlation (IACC) within +-1 ms, and a delay search out to 40 ms for the Haas
  trick or a doubled take,
* width = 1 - IACC (a hard-panned mono source is narrow, an uncorrelated pair is wide),
* moves: stretches where the windowed azimuth leaves its baseline,
* room: RT60 from the energy decay after abrupt cut-offs in the mix, low-end side energy, mono-sum loss.
A listening model's spatial claims (spatial*.json) are compared, never trusted."""
import os

import numpy as np
from scipy import signal

from .config import jdump


def lowpass(x, sr, hz, order=4):
    b, a = signal.butter(order, hz / (sr / 2), 'low')
    return signal.lfilter(b, a, x, axis=-1)


def xcorr(l, r, max_lag):
    """Normalised cross-correlation for lags -max_lag..+max_lag samples; positive lag = the right channel is later."""
    c = signal.correlate(r, l, mode='full', method='fft')
    mid = len(l) - 1
    seg = c[mid - max_lag: mid + max_lag + 1]
    return np.arange(-max_lag, max_lag + 1), seg / (np.sqrt(np.sum(l ** 2) * np.sum(r ** 2)) + 1e-12)


def azimuth_deg(el, er):
    theta = np.degrees(np.arctan2(np.sqrt(er), np.sqrt(el)))
    return float((theta - 45.0) * 2.0)


def measure_window(w, sr, cfg):
    """One window of a stereo stem -> azimuth, iacc, itd_ms, haas_ms, haas_corr, side_ratio."""
    s = cfg['spatial']
    l, r = w
    el, er = float(np.sum(l ** 2)), float(np.sum(r ** 2))
    near = int(s['itd_max_ms'] * sr / 1000)
    far = int(s['haas_max_ms'] * sr / 1000)
    lo = lowpass(w, sr, s['itd_lowpass_hz'])
    lags, c = xcorr(lo[0], lo[1], far)
    inner = np.abs(lags) <= near
    k = np.argmax(np.abs(c[inner]))
    iacc = float(np.abs(c[inner])[k])
    itd = float(lags[inner][k] * 1000.0 / sr)
    outer = np.abs(lags) >= int(s['haas_min_ms'] * sr / 1000)
    ko = np.argmax(np.abs(c[outer])) if outer.any() else 0
    haas_ms, haas_corr = (float(lags[outer][ko] * 1000.0 / sr), float(np.abs(c[outer])[ko])) if outer.any() else (0.0, 0.0)
    m, sd = (l + r) / 2, (l - r) / 2
    return {'azimuth_deg': azimuth_deg(el, er), 'iacc': iacc, 'itd_ms': itd, 'haas_ms': haas_ms, 'haas_corr': haas_corr,
            'side_ratio': float(np.sum(sd ** 2) / (np.sum(m ** 2) + np.sum(sd ** 2) + 1e-12)), 'energy': el + er}


def windows(stem, sr, cfg, t0=0.0):
    """Per-window measurements over the active parts of a stereo stem."""
    s = cfg['spatial']
    n = int(s['window_s'] * sr)
    rows = []
    starts = list(range(0, stem.shape[1] - n + 1, n))
    peak = max([float(np.sum(stem[:, i:i + n] ** 2)) for i in starts] or [0.0]) + 1e-12
    gate = peak * 10 ** (s['active_gate_db'] / 10)
    for i in range(0, stem.shape[1] - n + 1, n):
        seg = stem[:, i:i + n]
        if np.sum(seg ** 2) < gate:
            continue
        row = measure_window(seg, sr, cfg)
        row['t'] = t0 + i / sr
        rows.append(row)
    return rows


def technique(base, cfg):
    """Name the stereo technique from the baseline numbers."""
    s = cfg['spatial']
    if base['haas_corr'] >= s['haas_corr'] and base['haas_corr'] > base['iacc'] + 0.1:
        return 'haas_delay'
    if base['iacc'] < s['decorrelated_iacc'] and base['side_ratio'] > s['wide_side_ratio']:
        return 'decorrelated_double'
    if base['iacc'] >= s['mono_iacc'] and abs(base['azimuth_deg']) < s['centre_deg']:
        return 'mono_centre'
    if base['iacc'] >= s['mono_iacc']:
        return 'mono_panned'
    return 'stereo'


def find_moves(rows, base_az, cfg):
    """Stretches where the azimuth sits more than `move_deg` away from the baseline for at least `move_min_s`."""
    s = cfg['spatial']
    if len(rows) < 3:
        return []
    t = np.array([r['t'] for r in rows])
    az = signal.medfilt(np.array([r['azimuth_deg'] for r in rows]), 3)
    off = np.abs(az - base_az) > s['move_deg']
    out, i = [], 0
    while i < len(off):
        if off[i]:
            j = i
            while j + 1 < len(off) and off[j + 1] and t[j + 1] - t[j] <= 2 * s['window_s']:
                j += 1
            if t[j] - t[i] + s['window_s'] >= s['move_min_s']:
                out.append({'start_s': float(t[i]), 'end_s': float(t[j] + s['window_s']), 'from_deg': float(az[max(i - 1, 0)] if i else base_az),
                            'to_deg': float(az[j])})
            i = j + 1
        else:
            i += 1
    return out


def reverb_tail_db(stem, sr, cfg):
    """How loud the 60-250 ms after each note/hit ends is, relative to the last 100 ms before it ends (median; null if no clean ends)."""
    s = cfg['spatial']
    hop = int(0.01 * sr)
    mono = np.abs(stem).mean(axis=0)
    env = np.sqrt(np.convolve(mono ** 2, np.ones(hop) / hop, mode='same'))[::hop]
    db = 20 * np.log10(env + 1e-9)
    ref = db.max()
    vals = []
    for i in range(10, len(db) - 26):
        if db[i - 1] > ref - 30 and db[i - 1] - db[i + 2] > s['cut_drop_db']:
            before = db[i - 10:i].mean()
            after = db[i + 6:i + 25].mean()
            if before > ref - 30:
                vals.append(after - before)
    return float(np.median(vals)) if len(vals) >= s['min_cut_events'] else None


def rt60(mix_mono, sr, cfg):
    """RT60 from Schroeder backward integration of the decay after abrupt cut-offs in the mix; median of good fits."""
    s = cfg['spatial']
    hop = int(0.01 * sr)
    env = np.sqrt(np.convolve(mix_mono ** 2, np.ones(hop) / hop, mode='same'))[::hop]
    db = 20 * np.log10(env + 1e-9)
    fits, i = [], 5
    while i < len(db) - 10:
        if db[i - 3] - db[i + 3] > s['cut_drop_db'] and db[i - 3] > db.max() - 40:
            a = (i + 2) * hop
            b = min(a + int(s['rt60_max_s'] * sr), len(mix_mono))
            seg = mix_mono[a:b]
            if len(seg) > int(0.3 * sr):
                edc = np.cumsum((seg ** 2)[::-1])[::-1]
                edc_db = 10 * np.log10(edc / edc[0] + 1e-12)
                lo, hi = np.argmax(edc_db <= -5), np.argmax(edc_db <= -s['rt60_fit_db'])
                if hi > lo + 10:
                    t = np.arange(lo, hi) / sr
                    p = np.polyfit(t, edc_db[lo:hi], 1)
                    resid = edc_db[lo:hi] - np.polyval(p, t)
                    r2 = 1 - np.sum(resid ** 2) / (np.sum((edc_db[lo:hi] - edc_db[lo:hi].mean()) ** 2) + 1e-12)
                    if p[0] < 0 and r2 >= s['rt60_min_r2']:
                        fits.append(-60.0 / p[0])
            i += int(0.5 * sr / hop)
        else:
            i += 1
    return (float(np.median(fits)), len(fits)) if fits else (None, 0)


def room(mix, sr, cfg):
    s = cfg['spatial']
    l, r = mix
    low = lowpass(mix, sr, s['low_end_hz'])
    m, sd = (low[0] + low[1]) / 2, (low[0] - low[1]) / 2
    t60, n = rt60(mix.mean(axis=0), sr, cfg)
    return {'rt60_s': t60, 'rt60_cutoffs_used': n,
            'low_end_side_pct': float(100 * np.sum(sd ** 2) / (np.sum(m ** 2) + np.sum(sd ** 2) + 1e-12)),
            'mono_sum_change_db': float(10 * np.log10(np.sum((l + r) ** 2) / (2 * (np.sum(l ** 2) + np.sum(r ** 2))) + 1e-12))}


def measure_source(stem, sr, cfg, t0=0.0):
    rows = windows(stem, sr, cfg, t0)
    if not rows:
        return None
    w = np.array([r['energy'] for r in rows])
    med = lambda k: float(np.average([r[k] for r in rows], weights=w))
    base = {k: med(k) for k in ('azimuth_deg', 'iacc', 'itd_ms', 'haas_ms', 'haas_corr', 'side_ratio')}
    base['azimuth_deg'] = float(np.median([r['azimuth_deg'] for r in rows]))
    base['width_0_1'] = float(np.clip(1.0 - base['iacc'], 0.0, 1.0))
    base['technique'] = technique(base, cfg)
    base['reverb_tail_db'] = reverb_tail_db(stem, sr, cfg)
    return {'baseline': base, 'moves': find_moves(rows, base['azimuth_deg'], cfg),
            'windows': {'t': [round(r['t'], 2) for r in rows], 'azimuth_deg': [round(r['azimuth_deg'], 1) for r in rows],
                        'width_0_1': [round(1 - r['iacc'], 2) for r in rows]}}


def compare(measured, claimed, cfg):
    """Rows (id, claimed azimuth, measured azimuth, agree) for sources the listening model made a claim about."""
    out = []
    for c in claimed.get('sources', []):
        m = measured.get(c['id'])
        a = (c.get('baseline') or {}).get('azimuth_deg')
        if m and a is not None:
            d = m['baseline']['azimuth_deg'] - a
            out.append({'id': c['id'], 'claimed_deg': a, 'measured_deg': round(m['baseline']['azimuth_deg'], 1),
                        'agree': abs(d) <= cfg['spatial']['disagree_deg']})
    return out


def run(ctx):
    cfg, d = ctx['cfg'], ctx['data']
    if 'effects' not in d:
        from . import effects
        effects.run(ctx)
    sr = cfg['analysis']['sr']
    src = {}
    for i, a in d['sep']['voices'].items():
        src[i] = measure_source(a, sr, cfg)
    for i, p in d['drums']['pieces'].items():
        src[i] = measure_source(p['stem'], sr, cfg)
    for k, ev in enumerate(d['effects']['events'], 1):
        src[f'fx_{k:02d}_{ev["features"]["kind"]}'] = measure_source(ev['audio'], sr, cfg, ev['audio_start_s'])
    src['ambient_bed'] = measure_source(d['effects']['bed'], sr, cfg)
    src = {k: v for k, v in src.items() if v}
    space = room(d['mix'], sr, cfg)
    claimed = ctx['priors']['spatial']
    cmp_rows = compare(src, claimed, cfg)
    d['spatial'] = {'sources': src, 'space': space, 'claimed_vs_measured': cmp_rows}
    jdump({'convention': 'azimuth_deg: -90 hard left, 0 centre, +90 hard right; width_0_1 = 1 - IACC', 'space': space,
           'claimed_vs_measured': cmp_rows, 'sources': src}, os.path.join(ctx['root'], 'reports', 'spatial.json'))
    for k, v in src.items():
        b = v['baseline']
        print(f'  {k:<30} az {b["azimuth_deg"]:>6.1f}  width {b["width_0_1"]:.2f}  {b["technique"]:<18} moves {len(v["moves"])}')
    print(f'  room: RT60 {space["rt60_s"]}, low-end side {space["low_end_side_pct"]:.1f}%, mono-sum {space["mono_sum_change_db"]:+.1f} dB')
