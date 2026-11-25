# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_model.features - the elicitors, read from machinery the pipeline already has.

Everything here is a re-reading, not a new signal chain:

    build        the positive slope of an arousal proxy over the preset's 4-12 s window
    proximity    how close the next declared arrival is (`hits_at` in the direction sheet)
    tension      Chew's helical strain per two bars (pattern_audit._spiral_series)
    uncertainty  melodic entropy H per bar           (scripts/expectation.py, PPM-C)
    surprise     melodic information content IC per bar, less the ungrounded share
    density      onsets per second (score, or the measured onsets when audio is there)
    low_end      velocity-weighted share of notes below the preset's MIDI bound
    vocal        share of the grid sounding with a `vocal` role
    legato       share of the sounding figure with `art: legato` or a long gate
    consonance   1 - adjacent-pitch-class clash of the sounding harmony
    silence      the share of a window with nothing sounding
    arrival      the composite change at a declared hit (level, centroid, onset rate, density)
    recovery     the measured fall after the piece's loudest point
    slow_tempo   a scalar from the score's BPM against the preset's reference
    pulse        measured onset periodicity, halved outside the Witek BSI window
    roughness    the ear model's 30-150 Hz modulation index
    fatigue      the ear model's adaptation depth

A missing input is a zero array plus `measured[name] = False`, never a silent default that looks like a measurement:
chem_rows names what was not measured, and the pool that wanted it simply loses that term.

Normalisation is per piece except `proximity`, `silence`, `arrival` and `slow_tempo`, which are absolute. That is
what keeps the layer from rewarding loudness, and it is also why the report can order events inside a piece and
cannot compare two pieces.
"""
import numpy as np

import pattern_audit


def clip01(v):
    return float(min(1.0, max(0.0, v)))


def _z(v):
    a = np.asarray(v, dtype=float)
    s = float(np.std(a))
    return (a - a.mean()) / s if s > 1e-9 else np.zeros_like(a)


def _smooth(v, k):
    a = np.asarray(v, dtype=float)
    k = max(1, int(k))
    if k <= 1 or len(a) <= 1:
        return a
    kernel = np.ones(k) / k
    return np.convolve(a, kernel, mode='same')


def _rolling_min(v, k):
    """The smallest value in the last k samples (a running floor: what the piece has climbed from)."""
    a = np.asarray(v, dtype=float)
    k = max(1, int(k))
    return np.array([a[max(0, i - k + 1):i + 1].min() for i in range(len(a))])


def _norm01(v, low=5.0, high=95.0):
    a = np.asarray(v, dtype=float)
    lo, hi = np.percentile(a, low), np.percentile(a, high)
    if hi - lo < 1e-9:
        return np.zeros_like(a)
    return np.clip((a - lo) / (hi - lo), 0.0, 1.0)


def bpm_of(score):
    meta = score.get('meta') or {}
    try:
        b = float(score.get('bpm') or meta.get('bpm') or 100.0)
    except (TypeError, ValueError):
        b = 100.0
    return b if 20.0 <= b <= 300.0 else 100.0


def beats_per_bar(score):
    return pattern_audit._beats_per_bar(score)


def piece_end_s(score, bpm, sheet=None):
    """The last note's end in seconds (the sheet's duration when it is longer)."""
    end = 0.0
    for tr in score.get('tracks', []):
        for n in tr.get('notes', []):
            try:
                end = max(end, (float(n['t']) + float(n.get('d', 1.0))) * 60.0 / bpm)
            except (KeyError, TypeError, ValueError):
                continue
    for key in ('duration_s', 'duration_seconds'):
        try:
            if sheet and sheet.get(key):
                end = max(end, float(sheet[key]))
        except (TypeError, ValueError):
            continue
    return max(end, 1.0)


def _declared_arrivals(sheet):
    out = []
    for h in (sheet or {}).get('hits_at') or []:
        try:
            out.append(float(h))
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def _score_notes(score):
    notes = []
    for tr in score.get('tracks', []):
        role = pattern_audit._role(tr)
        for n in tr.get('notes', []):
            if 't' not in n:
                continue
            try:
                notes.append(dict(t=float(n['t']), d=max(float(n.get('d', 1.0)), 1e-3),
                                  v=pattern_audit._vel(n), p=n.get('p'), role=role, art=n.get('art'),
                                  track=tr.get('name', '')))
            except (TypeError, ValueError):
                continue
    return notes


def _score_series(score, times, step_s, cfg):
    """The score-side elicitors on the grid, in 0..1 (or raw seconds, where a row needs them)."""
    n = len(times)
    bpm = bpm_of(score)
    spb = 60.0 / bpm
    notes = _score_notes(score)
    counts = np.zeros(n)
    cover = np.zeros(n)
    wvel = np.zeros(n)
    wreg = np.zeros(n)
    wlow = np.zeros(n)
    vox = np.zeros(n)
    leg = np.zeros(n)
    fig_cover = np.zeros(n)
    chroma = np.zeros((n, 12))
    for nt in notes:
        t0, d = nt['t'] * spb, nt['d'] * spb
        i0, i1 = int(t0 / step_s), int(np.ceil((t0 + d) / step_s))
        if 0 <= i0 < n:
            counts[i0] += 1.0
        for i in range(max(i0, 0), min(i1, n)):
            ov = max(0.0, min(times[i] + step_s, t0 + d) - max(times[i], t0))
            if ov <= 0.0:
                continue
            cover[i] += ov
            w = ov * max(nt['v'], 0.01)
            wvel[i] += w
            p = nt['p']
            if isinstance(p, (int, float)):
                wreg[i] += w * float(p)
                if float(p) < cfg['elicitors']['low_end']['midi_below']:
                    wlow[i] += w
                chroma[i, int(round(float(p))) % 12] += w
            if nt['role'] == 'vocal':
                vox[i] += ov
            if nt['role'] in ('melody', 'lead', 'vocal'):
                fig_cover[i] += ov
                if nt['art'] == 'legato' or nt['d'] >= 0.75:
                    leg[i] += ov
    sounding = np.clip(cover / step_s, 0.0, 1.0)
    rate = counts / step_s
    dens_win = float(cfg['elicitors']['density']['window_s'])
    sil_win = float(cfg['elicitors']['silence']['window_s'])
    prof = chroma / np.maximum(chroma.sum(axis=1, keepdims=True), 1e-12)
    clash = np.sum(prof * np.roll(prof, -1, axis=1), axis=1) if n else np.zeros(0)
    return dict(
        rate=rate,
        density=np.clip(_smooth(rate, dens_win / step_s) / max(float(cfg['elicitors']['density']['ref_per_s']), 1e-6), 0.0, 1.0),
        silence=np.clip(1.0 - _smooth(sounding, sil_win / step_s), 0.0, 1.0),
        vel=np.clip(wvel / np.maximum(cover, 1e-9), 0.0, 1.5),
        register=wreg / np.maximum(wvel, 1e-9),
        low_end=np.clip(wlow / np.maximum(wvel, 1e-9), 0.0, 1.0),
        vocal=np.clip(_smooth(vox / step_s, sil_win / step_s), 0.0, 1.0),
        legato=np.clip(leg / np.maximum(fig_cover, 1e-9), 0.0, 1.0),
        consonance=np.clip(1.0 - clash / max(float(cfg['elicitors']['consonance']['clash_ref']), 1e-6), 0.0, 1.0),
        bpm=bpm, spb=spb, notes=notes, has_figure=any(nt['role'] in ('melody', 'lead', 'vocal') for nt in notes),
    )


def _tension_series(score, times, spb):
    series = pattern_audit._spiral_series(score)
    if series is None:
        return None
    CEs, _cloud, key, N, w_len = series
    strain = np.array([float(np.linalg.norm(np.asarray(ce) - np.asarray(key))) for ce in CEs])
    centres = (np.arange(N) + 0.5) * w_len * spb
    return np.interp(times, centres, strain)


def _nan_row_mean(rows):
    """Column mean of a ragged list of per-bar arrays, ignoring NaN; a column with no value stays NaN."""
    out = []
    for col in zip(*rows):
        vals = [float(v) for v in col if not np.isnan(v)]
        out.append(float(np.mean(vals)) if vals else np.nan)
    return np.array(out)


def _expectation_series(score, times, spb, cfg):
    """(H, IC) per bar, interpolated to the grid; None when no line is long enough to model."""
    lines = pattern_audit._melody_lines(score)
    if not lines:
        return None
    bpb = beats_per_bar(score)
    hs, ics, ungrounded = [], [], []
    for _name, a in lines:
        v = a['h']
        h = ~np.isnan(v)
        if h.sum() >= 4:
            import expectation
            hs.append(expectation.by_bar(a['onsets'], v, bpb))
            ics.append(expectation.by_bar(a['onsets'], a['ic'], bpb))
            ungrounded.append(expectation.ungrounded_share(a['ic'], cfg['elicitors']['surprise']['high_bits']))
    if not ics:
        return None
    width = max(len(x) for x in ics)
    ic = _nan_row_mean([np.pad(x, (0, width - len(x)), constant_values=np.nan) for x in ics])
    h = _nan_row_mean([np.pad(x, (0, width - len(x)), constant_values=np.nan) for x in hs])
    centres = (np.arange(len(ic)) + 0.5) * bpb * spb
    return (np.interp(times, centres[~np.isnan(h)], h[~np.isnan(h)]) if (~np.isnan(h)).sum() >= 1
            else np.zeros(len(times)),
            np.interp(times, centres[~np.isnan(ic)], ic[~np.isnan(ic)]) if (~np.isnan(ic)).sum() >= 1
            else np.zeros(len(times)),
            float(np.mean(ungrounded)) if ungrounded else 0.0)


def _audio_series(path, times, step_s):
    """Level, spectral centroid, measured onset rate and pulse clarity of the rendered master, on the grid."""
    import naturalness_check as nc                     # lazy: the score-only path must not need soundfile
    try:
        x, sr = nc.load(path)
    except Exception:
        return None
    mono = x.mean(axis=1) if x.ndim == 2 else np.asarray(x, dtype=float)
    if len(mono) < sr * 0.5:
        return None
    hop = max(1, int(round(step_s * sr)))
    n = len(times)
    loud = np.full(n, -70.0)
    cent = np.zeros(n)
    for i in range(n):
        seg = mono[i * hop:(i + 1) * hop]
        if len(seg) < 32:
            continue
        loud[i] = 20.0 * np.log10(float(np.sqrt(np.mean(seg ** 2))) + 1e-12)
        mag = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1.0 / sr)
        cent[i] = float((mag * f).sum() / (mag.sum() + 1e-12))
    on = nc.onsets(x[:n * hop], sr) if n else np.array([])      # nc.onsets takes the (n, channels) signal
    idx = np.clip((np.asarray(on) / step_s).astype(int), 0, max(n - 1, 0)) if len(on) else np.array([], dtype=int)
    rate = np.bincount(idx, minlength=n)[:n] / step_s if n else np.zeros(0)
    return dict(loud_db=loud, centroid=np.log2(np.maximum(cent, 20.0)), onset_rate=rate,
                pulse=_pulse_clarity(on, n * step_s), duration_s=len(mono) / float(sr))


def _pulse_clarity(on, duration_s):
    """Peak of the onset train's normalised autocorrelation between 0.3 and 1.2 s: how periodic the pulse is."""
    res = 0.02
    m = max(int(duration_s / res), 8)
    tr = np.zeros(m)
    for t in np.asarray(on, dtype=float):
        k = int(t / res)
        if 0 <= k < m:
            tr[k] += 1.0
    if tr.sum() < 4:
        return 0.0
    tr = tr - tr.mean()
    spec = np.fft.rfft(tr, 2 * m)
    ac = np.fft.irfft(spec * np.conj(spec))[:m]
    ac = ac / (ac[0] + 1e-12)
    lo, hi = int(0.3 / res), int(1.2 / res)
    return clip01(float(ac[lo:hi].max()))


def _window_mean(v, times, a, b):
    m = (times >= a) & (times < b)
    return float(np.mean(v[m])) if m.any() else float('nan')


def _arrivals(score, sheet, times, proxy, audio, score_feats, step_s, cfg):
    """Every declared hit, with the composite change measured at it. With no `hits_at`, the piece's own peak."""
    win = float(cfg['measures']['arrival']['window_s'])
    e = cfg['elicitors']['arrival']
    hits = [(t, True) for t in _declared_arrivals(sheet)]
    if not hits:
        # no declaration: the strongest measured *change* stands in for a hit (the peak of the proxy is a plateau, not
        # an event, so its own change is near zero and every piece would read as having no arrival)
        d = np.diff(_smooth(proxy, max(1, int(1.0 / step_s))))
        stop = max(1, int(len(d) * 0.9))          # an ending fade is not an arrival
        rise = np.maximum(0.0, d[:stop])
        pick = rise if rise.max() > 0.0 else np.abs(d[:stop])
        hits = [(float(times[int(np.argmax(pick)) + 1]) if len(pick) else 0.0, False)]
    out = []
    for ta, declared in hits:
        parts, contrast = [], None
        if audio is not None:
            dl = _window_mean(audio['loud_db'], times, ta, ta + win) - _window_mean(audio['loud_db'], times, ta - win, ta)
            dc = _window_mean(audio['centroid'], times, ta, ta + win) - _window_mean(audio['centroid'], times, ta - win, ta)
            do = _window_mean(audio['onset_rate'], times, ta, ta + win) - _window_mean(audio['onset_rate'], times, ta - win, ta)
            if np.isfinite(dl):
                parts.append(max(0.0, dl) / float(e['loud_ref_db']))
                contrast = float(dl)
            if np.isfinite(dc):
                parts.append(max(0.0, dc) / float(e['centroid_ref_oct']))
            if np.isfinite(do):
                parts.append(max(0.0, do) / float(e['density_ref_per_s']))
        for key, ref in (('rate', float(e['density_ref_per_s'])), ('low_end', 0.3), ('vel', 0.3)):
            d = (_window_mean(score_feats[key], times, ta, ta + win)
                 - _window_mean(score_feats[key], times, ta - win, ta))
            if np.isfinite(d):
                parts.append(max(0.0, d) / ref)
        first = {}
        for nt in score_feats['notes']:
            at = nt['t'] * score_feats['spb']
            first[nt['track']] = min(first.get(nt['track'], at), at)
        entering = sum(1 for at in first.values() if abs(at - ta) <= 1.0)
        if entering:
            parts.append(min(1.0, entering / 3.0))
        out.append(dict(at_s=ta, declared=declared, contrast_db=contrast,
                        strength=clip01(float(np.mean(parts))) if parts else 0.0,
                        entering=entering))
    out.sort(key=lambda a: a['at_s'])
    return out


def build(score, path, sheet, summary, cfg, step_s=None):
    """The whole feature bus for one piece: {u: {elicitor: array}, measured: {name: bool}, ...}."""
    step = float(step_s if step_s is not None else cfg['step_s'])
    bpm = bpm_of(score)
    dur = piece_end_s(score, bpm, sheet)
    n = max(2, int(np.ceil(dur / step)))
    times = np.arange(n) * step
    sf = _score_series(score, times, step, cfg)
    audio = _audio_series(path, times, step) if path else None

    # one arousal proxy: the measured level/onset/centroid when audio is there, the written density/velocity/register otherwise
    if audio is not None:
        proxy = (_z(audio['loud_db']) + _z(audio['onset_rate']) + _z(audio['centroid'])) / 3.0
    else:
        proxy = (_z(sf['density']) + _z(sf['vel']) + _z(sf['register'])) / 3.0

    arrivals = _arrivals(score, sheet, times, proxy, audio, sf, step, cfg)
    b = cfg['elicitors']['build']
    fast = _smooth(proxy, max(1, int(float(b['window_s'][0]) / step)))
    # the climb out of the last 12 s floor, not the instantaneous slope: a slope dies at the hit (the slow window catches
    # up with the fast one), which would make anticipation decay exactly where it should be highest.
    climb = fast - _rolling_min(fast, int(float(b['window_s'][1]) / step))
    lo, hi = np.percentile(climb, float(b['low_pct'])), np.percentile(climb, float(b['high_pct']))
    build_u = np.clip((climb - lo) / (hi - lo), 0.0, 1.0) if hi - lo > 1e-9 else np.zeros(n)

    prox = np.zeros(n)
    lead = float(cfg['elicitors']['proximity']['max_lead_s'])
    for i, t in enumerate(times):
        future = [a['at_s'] - t for a in arrivals if a['at_s'] >= t]
        if future:
            prox[i] = clip01(1.0 - min(future) / lead)

    arr = np.zeros(n)
    for a in arrivals:
        dt = times - a['at_s']
        m = dt >= 0
        arr[m] = np.maximum(arr[m], a['strength'] * np.exp(-dt[m] / max(float(cfg['measures']['arrival']['window_s']), 1e-6)))

    peak_i = int(np.argmax(proxy))
    span = float(proxy.max() - proxy.min())
    rec = np.zeros(n)
    if span > 1e-9 and peak_i < n - 1:
        rec[peak_i:] = np.clip((proxy[peak_i] - proxy[peak_i:]) / span, 0.0, 1.0)
    tail = float(cfg['measures']['recovery']['tail_frac'])
    rec[int(n * (1.0 - tail)):] = np.maximum(rec[int(n * (1.0 - tail)):], 0.5)

    u, measured = {}, {}
    u['build'] = build_u
    u['proximity'] = prox
    u['arrival'] = arr
    u['recovery'] = rec
    u['silence'] = sf['silence']
    u['density'] = sf['density']
    u['low_end'] = sf['low_end']
    u['vocal'] = sf['vocal']
    u['legato'] = sf['legato']
    u['consonance'] = sf['consonance']
    for key, label in (('silence', 'silence'), ('density', 'density'), ('low_end', 'low_end'),
                       ('vocal', 'vocal'), ('legato', 'legato'), ('consonance', 'consonance')):
        measured[label] = True
    u['slow_tempo'] = np.full(n, clip01((float(cfg['elicitors']['slow_tempo']['bpm_ref']) - bpm)
                                       / float(cfg['elicitors']['slow_tempo']['bpm_ref'])))
    measured['slow_tempo'] = True

    tension = _tension_series(score, times, sf['spb'])
    if tension is not None:
        u['tension'] = _norm01(tension)
        measured['tension'] = True
    else:
        u['tension'] = np.zeros(n)
        measured['tension'] = False

    model = _expectation_series(score, times, sf['spb'], cfg)
    if model is not None:
        h, ic, ung = model
        u['uncertainty'] = _norm01(h)
        u['surprise'] = np.clip(_norm01(ic) * (1.0 - ung), 0.0, 1.0)
        u['ungrounded'] = np.full(n, clip01(ung))
        measured['uncertainty'] = measured['surprise'] = measured['ungrounded'] = True
    else:
        for k in ('uncertainty', 'surprise', 'ungrounded'):
            u[k] = np.zeros(n)
            measured[k] = False

    bsi = pattern_audit.bar_syncopation(score)
    pulse_val = float(audio['pulse']) if audio is not None else 0.0
    lo_b, hi_b = cfg['elicitors']['pulse']['bsi_window']
    if bsi is not None and not (float(lo_b) <= bsi <= float(hi_b)):
        pulse_val *= 0.5
    u['pulse'] = np.full(n, clip01(pulse_val))
    measured['pulse'] = audio is not None

    frame_s = None
    for key, field in (('roughness', 'roughness'), ('fatigue', 'fatigue')):
        if summary is not None and summary.get(field) is not None and len(summary.get(field)):
            v = np.asarray(summary[field], dtype=float)
            frame_s = float(summary.get('frame_s') or frame_s or 0.05)
            src = np.arange(len(v)) * frame_s
            u[key] = np.clip(np.interp(times, src, v), 0.0, 1.0)
            measured[key] = True
        else:
            u[key] = np.zeros(n)
            measured[key] = False
    measured['build'] = True
    measured['proximity'] = bool(arrivals and arrivals[0]['declared'])
    measured['arrival'] = True
    measured['recovery'] = True

    return dict(times=times, step_s=step, u=u, measured=measured, arrivals=arrivals, proxy=proxy,
                audio=audio, score=sf, bsi=bsi, bpm=bpm, duration_s=n * step)
