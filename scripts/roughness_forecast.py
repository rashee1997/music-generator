"""Roughness before the render: forecast it from the score, diagnose it from a master, learn partials from stems.

The audio row `cochlear_roughness` (`naturalness_check.cochlear_roughness_check`) looks at the ten strongest partials of
each 1 s frame and sums the Plomp-Levelt beating of the three worst pairs. It sees overtones, not written notes, so two
consonant notes can still fail it: a D2's sixth harmonic is an A4, a D3's third is the same A4, and a horn's Bb4 sits 25 Hz
from that. This module runs the SAME pair model on the score (before a render costs minutes) and on a finished master
(to name the pair and the stems that own it), so a clash is found once, by number, instead of by trial.

    python scripts/roughness_forecast.py forecast  <score.json> [--project DIR]
    python scripts/roughness_forecast.py diagnose  <master.wav> [--stems DIR] [--score score.json]
    python scripts/roughness_forecast.py calibrate <score.json> <master.wav> [--project DIR]
    python scripts/roughness_forecast.py partials  <stem.wav> <score.json> <track> [--project DIR]

`forecast`   per 1 s frame (0.5 s hop, as the gate) the modelled roughness, the frames that stand out against the piece's
             own median (the gate's relative rule) and, for each, the two partials that beat, with the track each came from.
`diagnose`   the gate's own row on the master, then for every frame over the limit the pairs of real spectral peaks inside
             a quarter critical band, and which stems hold a peak at each frequency.
`calibrate`  how well the forecast follows the measured frames (correlation, and the ratio of medians): the honest check
             of how far to trust it.
`partials`   the harmonic profile of one track, measured from its dry stem; paste it into the instrument preset as
             `"partials": [...]` (declared, measured) and the forecast uses it.

Numbers: the pair weight and the frame rule are the gate's (`naturalness_check`); the default partial profiles are in
`references/data/roughness_forecast.json`, each a starting value until measured. The forecast is a model of the score,
not of the SoundFont: use `partials` to make it measure the instrument.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import naturalness_check as nc  # noqa: E402

DATA_PATH = os.path.join(HERE, '..', 'references', 'data', 'roughness_forecast.json')
MERGE_HZ = 2.0            # two partials closer than this are one spectral peak at the gate's 1 Hz resolution
SKIP_ROLES = ('drum', 'environment', 'fx')


def load_data(path=None):
    with open(path or DATA_PATH, encoding='utf-8') as fh:
        return json.load(fh)


def pair_weight(f1, f2):
    """The gate's Plomp-Levelt pair weight (Sethares form), symmetric in its arguments."""
    lo, hi = (f1, f2) if f1 <= f2 else (f2, f1)
    s = 0.24 / (0.0207 * lo + 18.96)
    df = hi - lo
    return float(max(0.0, np.exp(-3.51 * s * df) - np.exp(-5.75 * s * df)))


def frame_value(freqs, amps, top=10):
    """The gate's frame value from partials: the ten strongest inside the band and within the audible range of the
    loudest, amplitudes normalised to it, the mean of the three strongest pair contributions. Returns (value, pairs)
    where each pair is (contribution, index_a, index_b) into the arrays given."""
    freqs, amps = np.asarray(freqs, float), np.asarray(amps, float)
    if len(freqs) < 2:
        return float('nan'), []
    lo, hi = nc.ROUGHNESS_BAND_HZ
    keep = np.flatnonzero((freqs >= lo) & (freqs <= hi))
    if len(keep) < 2:
        return float('nan'), []
    mx = float(np.max(amps[keep]))
    if mx <= 1e-12:
        return float('nan'), []
    keep = keep[amps[keep] >= mx * 10 ** (nc.ROUGHNESS_AUDIBLE_DB / 20.0)]
    keep = keep[np.argsort(amps[keep])[-top:]]
    if len(keep) < 2:
        return float('nan'), []
    keep = keep[np.argsort(freqs[keep])]
    contrib = []
    for a in range(len(keep)):
        for b in range(a + 1, len(keep)):
            ia, ib = keep[a], keep[b]
            w = pair_weight(freqs[ia], freqs[ib])
            if w > 0.0:
                contrib.append((float(min(amps[ia], amps[ib]) / mx * w), int(ia), int(ib)))
    contrib.sort(reverse=True)
    top3 = [c[0] for c in contrib[:3]]
    return (float(np.mean(top3)) if top3 else 0.0), contrib[:3]


def mtof(p):
    return 440.0 * 2.0 ** ((float(p) - 69.0) / 12.0)


def _filter_gain(f, eq):
    """Magnitude of the preset's hp/lp stages at f (second order unless the stage says otherwise)."""
    g = 1.0
    for st in eq or []:
        kind, fc = str(st.get('type', '')), float(st.get('f', 0) or 0)
        order = float(st.get('order', 2))
        if fc <= 0:
            continue
        if kind in ('hp', 'highpass'):
            g *= 1.0 / np.sqrt(1.0 + (fc / f) ** (2 * order))
        elif kind in ('lp', 'lowpass'):
            g *= 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order))
    return g


def profile_for(preset, data):
    """The partial amplitudes for a track: the preset's own `partials` (measured), else the family of its gm name."""
    if preset and preset.get('partials'):
        return [float(a) for a in preset['partials']], 'preset'
    gm = str((preset or {}).get('gm') or (preset or {}).get('instrument') or '')
    fam = data.get('by_gm', {}).get(gm)
    return [float(a) for a in (fam or data['default_partials'])], ('family ' + gm if fam else 'default')


def forecast(score, lookup=None, data=None, win=1.0, hop=0.5):
    """Frames of modelled roughness for a score. Returns dict(times, values, parts) where parts[i] is the list of
    (freq, amp, track) behind frame i, so a flagged frame can name its pair."""
    data = data or load_data()
    import gate_clock
    clock = gate_clock.seconds_fn(score)
    dyn = score.get('dynamics') or []
    bpm = float(score.get('bpm', 120))
    dyn_t = [float(d[0]) * 60.0 / bpm for d in dyn]
    dyn_v = [float(d[1]) for d in dyn]

    def level(t):
        return float(np.interp(t, dyn_t, dyn_v)) if len(dyn_t) >= 2 else 0.6

    tracks = []
    for tr in score.get('tracks') or []:
        role = str(tr.get('role') or '')
        if role in SKIP_ROLES or not tr.get('notes'):
            continue
        name = str(tr.get('instrument') or tr.get('name'))
        preset = None
        if lookup:
            try:
                preset = lookup('instrument', name)
            except Exception:
                preset = None
        prof, _src = profile_for(preset, data)
        gain = 10 ** (float((preset or {}).get('gain_db', 0.0)) / 20.0)
        rel = float(data.get('release_s', {}).get(str((preset or {}).get('gm') or ''), data['default_release_s']))
        notes = []
        for n in tr['notes']:
            if not isinstance(n.get('p'), (int, float)):
                continue
            s0 = float(clock(float(n['t'])))
            s1 = float(clock(float(n['t']) + float(n.get('d', 1.0)))) + rel
            notes.append((s0, s1, float(n['p']), float(n.get('v', 80)) / 127.0))
        if notes:
            tracks.append((tr.get('name', name), prof, (preset or {}).get('eq'), gain, notes))
    if not tracks:
        return dict(times=[], values=[], parts=[])
    end = max(n[1] for t in tracks for n in t[4])
    count = max(1, int((end - win) // hop) + 1)
    times, values, parts_all = [], [], []
    for i in range(count):
        a, b = i * hop, i * hop + win
        parts = []
        for name, prof, eq, gain, notes in tracks:
            for s0, s1, p, v in notes:
                ov = min(b, s1) - max(a, s0)
                if ov <= 0:
                    continue
                amp0 = gain * v * level(0.5 * (max(a, s0) + min(b, s1))) * (ov / win)
                f0 = mtof(p)
                for k, ak in enumerate(prof, start=1):
                    f = f0 * k
                    if f > nc.ROUGHNESS_BAND_HZ[1]:
                        break
                    parts.append((f, amp0 * ak * _filter_gain(f, eq), name))
        parts.sort()
        merged = []
        for f, am, nm in parts:
            if merged and f - merged[-1][0] < MERGE_HZ:
                pf, pa, pn = merged[-1]
                merged[-1] = (pf, float(np.sqrt(pa * pa + am * am)), pn | {nm})
            else:
                merged.append((f, am, {nm}))
        times.append(a + win / 2.0)
        fr = np.array([m[0] for m in merged]) if merged else np.array([])
        am = np.array([m[1] for m in merged]) if merged else np.array([])
        val, pairs = frame_value(fr, am)
        values.append(val)
        parts_all.append((merged, pairs))
    return dict(times=times, values=values, parts=parts_all)


def flag_frames(fc, ratio=None, min_frames=2):
    """Frames that stand out against the forecast's own median (the gate's relative rule), with the worst pair."""
    ratio = float(ratio if ratio is not None else nc.ROUGHNESS_RELATIVE)
    vals = np.array([v for v in fc['values'] if not np.isnan(v)])
    if len(vals) < 4:
        return [], float('nan')
    med = float(np.median(vals))
    hot = float(np.percentile(vals, 90))                        # only the hottest tenth of the frames, and
    flagged = []
    for t, v, (merged, pairs) in zip(fc['times'], fc['values'], fc['parts']):
        if np.isnan(v) or v <= ratio * med or v < hot or not pairs:   # ... the gate's relative rule on top
            continue
        c, ia, ib = pairs[0]
        fa, fb = merged[ia], merged[ib]
        flagged.append(dict(t=float(t), value=float(v), f_a=float(fa[0]), f_b=float(fb[0]), tracks_a=sorted(fa[2]),
                            tracks_b=sorted(fb[2])))
    return (flagged if len(flagged) >= min_frames else []), med


def forecast_rows(score, lookup=None, top=3):
    """The preflight row: the hottest frames of the forecast, with the pair that beats in each. A WARN, never a FAIL: it is a
    model of the score (default partial profiles unless the presets carry measured `partials`), measured to rank the
    worst frames of one piece only modestly, so it points at where to look and `diagnose` on a draft master confirms."""
    try:
        fc = forecast(score, lookup)
    except Exception as ex:                      # a missing dependency or an odd score must not block a render
        return [('INFO', 'preflight.roughness_partials', f'not forecast: {ex}')]
    flagged, med = flag_frames(fc)
    if not flagged:
        return [('PASS', 'preflight.roughness_partials', 'no frame stands out in the partial-level roughness forecast')]
    flagged.sort(key=lambda d: -d['value'])
    seen, picked = set(), []
    for fl in flagged:                           # one line per distinct pair, not one per frame it lasts
        key = (round(fl['f_a'] / 10.0), round(fl['f_b'] / 10.0))
        if key not in seen:
            seen.add(key)
            picked.append(fl)
    lines = []
    for fl in picked[:top]:
        lines.append(f'{fl["t"]:.0f} s: {fl["f_a"]:.0f} Hz ({", ".join(fl["tracks_a"][:3])}) against {fl["f_b"]:.0f} Hz '
                     f'({", ".join(fl["tracks_b"][:3])}), {abs(fl["f_b"] - fl["f_a"]):.0f} Hz apart')
    return [('WARN', 'preflight.roughness_partials',
             f'{len(flagged)} frame(s) stand out in the partial-level forecast (overtones, not only written notes); the worst: '
             + '; '.join(lines) + '. Move one of the parts, keep a bass note off the pitch whose harmonic lands there, or '
             'measure the instruments with `roughness_forecast.py partials` and re-run; `roughness_forecast.py diagnose` names '
             'the pair on a finished master')]


# ------------------------------------------------------------------------------------------------ audio side
def _peaks(mono, sr, t0, win=1.0):
    """The gate's peak picking on one window: (freqs, mags) of the spectral peaks in the roughness band."""
    n = int(sr * win)
    i0 = int(t0 * sr)
    seg = mono[i0:i0 + n]
    if len(seg) < n:
        return np.array([]), np.array([])
    mag = np.abs(np.fft.rfft(seg * np.hanning(n)))
    fr = np.fft.rfftfreq(n, 1.0 / sr)
    lo, hi = nc.ROUGHNESS_BAND_HZ
    m = (fr >= lo) & (fr <= hi)
    mg, ff = mag[m], fr[m]
    if len(mg) < 3:
        return np.array([]), np.array([])
    pk = np.where((mg[1:-1] > mg[:-2]) & (mg[1:-1] > mg[2:]))[0] + 1
    return ff[pk], mg[pk]


def diagnose(wav, stems_dir=None, score=None, top=3):
    """The gate's row on a master, then the clashing partial pairs at each frame over the limit and the stems that hold
    a peak at each of the two frequencies."""
    import soundfile as sf
    x, sr = sf.read(wav, dtype='float32', always_2d=True)
    rows, metrics = nc.cochlear_roughness_check(x, sr=sr, score=score)
    frames = metrics.get('frames') or []
    vals = np.array([np.nan if v is None else v for v in frames], float)
    ok = vals[~np.isnan(vals)]
    out = dict(rows=[(r[0], r[1], r[2]) for r in rows], flagged=[])
    if len(ok) < 4:
        return out
    med = float(np.median(ok))
    # the gate's two rules: a chronically high median (above the absolute limit) fails on its own, else a frame must
    # also stand ROUGHNESS_RELATIVE above the piece's median
    thr = nc.ROUGHNESS_MEDIAN if med > nc.ROUGHNESS_MEDIAN else max(nc.ROUGHNESS_MEDIAN, nc.ROUGHNESS_RELATIVE * med)
    win, hop = int(sr), int(sr // 2)
    mono = x.mean(axis=1)
    stems = {}
    if stems_dir and os.path.isfile(os.path.join(stems_dir, 'stems.json')):
        meta = json.load(open(os.path.join(stems_dir, 'stems.json'), encoding='utf-8'))
        for name, m in meta.items():
            path = os.path.join(stems_dir, name + '.wav')
            if os.path.isfile(path):
                y, ssr = sf.read(path, dtype='float32', always_2d=True)
                stems[name] = (y.mean(axis=1), ssr, float(m.get('start_s', 0.0)))
    for i in np.argsort(-np.nan_to_num(vals, nan=-1.0))[:top * 4]:
        if np.isnan(vals[i]) or vals[i] <= thr:
            continue
        t0 = i * hop / sr
        ff, mg = _peaks(mono, sr, t0)
        if len(ff) < 2:
            continue
        mx = float(mg.max())
        sel = np.argsort(mg)[-10:]
        sel = sel[mg[sel] >= mx * 10 ** (nc.ROUGHNESS_AUDIBLE_DB / 20.0)]
        pairs = []
        for a in range(len(sel)):
            for b in range(a + 1, len(sel)):
                fa, fb = float(ff[sel[a]]), float(ff[sel[b]])
                w = pair_weight(fa, fb)
                if w > 0:
                    pairs.append((float(min(mg[sel[a]], mg[sel[b]]) / mx * w), fa, fb))
        pairs.sort(reverse=True)
        if not pairs:
            continue

        def owners(f):
            res = []
            for name, (y, ssr, st) in stems.items():
                s0 = int((t0 - st) * ssr)
                if s0 < 0 or s0 + ssr > len(y):
                    continue
                sf_, sm = _peaks(y, ssr, t0 - st)
                if len(sf_) == 0:
                    continue
                j = int(np.argmin(np.abs(sf_ - f)))
                if abs(sf_[j] - f) <= 3.0 and sm[j] >= 0.1 * float(sm.max()):
                    res.append(name)
            return res
        out['flagged'].append(dict(t=float(t0 + 0.5), value=float(vals[i]), limit=float(thr),
                                   pairs=[dict(weight=p[0], f_a=p[1], f_b=p[2], delta_hz=p[2] - p[1],
                                               stems_a=owners(p[1]), stems_b=owners(p[2])) for p in pairs[:top]]))
    return out


def calibrate(fc, wav, score=None):
    """How well the forecast follows the measured frames. Both are 1 s frames on a 0.5 s hop, aligned by index."""
    import soundfile as sf
    x, sr = sf.read(wav, dtype='float32', always_2d=True)
    _rows, metrics = nc.cochlear_roughness_check(x, sr=sr, score=score)
    meas = np.array([np.nan if v is None else v for v in metrics.get('frames') or []], float)
    pred = np.array(fc['values'], float)
    n = min(len(meas), len(pred))
    m, p = meas[:n], pred[:n]
    ok = ~np.isnan(m) & ~np.isnan(p)
    if ok.sum() < 4:
        return dict(frames=int(ok.sum()), correlation=float('nan'), median_ratio=float('nan'))
    corr = float(np.corrcoef(m[ok], p[ok])[0, 1])
    return dict(frames=int(ok.sum()), correlation=corr, median_ratio=float(np.median(m[ok]) / max(np.median(p[ok]), 1e-12)))


def measure_partials(stem_audio, sr, notes, clock, count=12, min_len_s=0.4):
    """The harmonic profile of a track from its dry stem: for each note held long enough, the magnitude at k*f0 (nearest
    peak within 1.5 %), normalised to the strongest harmonic of that note; the median over the notes. `notes` are the
    score's (t, d, p) and `clock` maps beats to seconds."""
    prof = []
    for n in notes:
        if not isinstance(n.get('p'), (int, float)):
            continue
        s0 = float(clock(float(n['t'])))
        s1 = float(clock(float(n['t']) + float(n.get('d', 1.0))))
        if s1 - s0 < min_len_s:
            continue
        a, b = int((s0 + 0.15) * sr), int(min(s1, s0 + 1.2) * sr)
        seg = stem_audio[a:b]
        if len(seg) < int(0.25 * sr):
            continue
        mag = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n=1 << 16))
        fr = np.fft.rfftfreq(1 << 16, 1.0 / sr)
        f0, row = mtof(n['p']), []
        for k in range(1, count + 1):
            sel = (fr > f0 * k * 0.985) & (fr < f0 * k * 1.015)
            row.append(float(mag[sel].max()) if sel.any() else 0.0)
        mx = max(row)
        if mx > 1e-9:
            prof.append([r / mx for r in row])
    if not prof:
        return []
    return [round(float(v), 3) for v in np.median(np.array(prof), axis=0)]


# ------------------------------------------------------------------------------------------------ CLI
def _lookup(project):
    import presets
    if project:
        presets.add_project(project)
    return lambda kind, name: presets.find_instrument(name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('forecast')
    f.add_argument('score')
    f.add_argument('--project')
    d = sub.add_parser('diagnose')
    d.add_argument('wav')
    d.add_argument('--stems')
    d.add_argument('--score')
    c = sub.add_parser('calibrate')
    c.add_argument('score')
    c.add_argument('wav')
    c.add_argument('--project')
    p = sub.add_parser('partials')
    p.add_argument('stem')
    p.add_argument('score')
    p.add_argument('track')
    p.add_argument('--project')
    a = ap.parse_args(argv)
    if a.cmd == 'forecast':
        score = json.load(open(a.score, encoding='utf-8'))
        fc = forecast(score, _lookup(a.project))
        flagged, med = flag_frames(fc)
        print(f'{len(fc["times"])} frames, forecast median {med:.3f}; {len(flagged)} frame(s) stand out (> {nc.ROUGHNESS_RELATIVE} x median)')
        for fl in flagged:
            print(f'  {fl["t"]:6.1f} s  value {fl["value"]:.3f}: {fl["f_a"]:.0f} Hz ({", ".join(fl["tracks_a"])}) against '
                  f'{fl["f_b"]:.0f} Hz ({", ".join(fl["tracks_b"])}), {abs(fl["f_b"] - fl["f_a"]):.0f} Hz apart')
        return 1 if flagged else 0
    if a.cmd == 'diagnose':
        score = json.load(open(a.score, encoding='utf-8')) if a.score else None
        res = diagnose(a.wav, a.stems, score)
        for lvl, name, detail in res['rows']:
            print(f'[{lvl}] {name}: {detail}')
        for fl in res['flagged']:
            print(f'  {fl["t"]:6.1f} s  value {fl["value"]:.3f} (limit {fl["limit"]:.3f})')
            for pr in fl['pairs']:
                print(f'      {pr["f_a"]:.1f} Hz [{", ".join(pr["stems_a"]) or "?"}] against {pr["f_b"]:.1f} Hz '
                      f'[{", ".join(pr["stems_b"]) or "?"}]: {pr["delta_hz"]:.1f} Hz apart, weight {pr["weight"]:.3f}')
        return 0
    if a.cmd == 'calibrate':
        score = json.load(open(a.score, encoding='utf-8'))
        fc = forecast(score, _lookup(a.project))
        cal = calibrate(fc, a.wav, score)
        print(f'{cal["frames"]} frames: correlation {cal["correlation"]:.2f}, measured median / forecast median {cal["median_ratio"]:.2f}')
        return 0
    if a.cmd == 'partials':
        import soundfile as sf
        import gate_clock
        score = json.load(open(a.score, encoding='utf-8'))
        tr = next(t for t in score['tracks'] if t.get('name') == a.track)
        y, sr = sf.read(a.stem, dtype='float32', always_2d=True)
        meta_path = os.path.join(os.path.dirname(os.path.abspath(a.stem)), 'stems.json')
        start = 0.0
        if os.path.isfile(meta_path):
            start = float(json.load(open(meta_path, encoding='utf-8')).get(a.track, {}).get('start_s', 0.0))
        clock = gate_clock.seconds_fn(score)
        shifted = lambda b: clock(b) - start  # noqa: E731
        prof = measure_partials(y.mean(axis=1), sr, tr['notes'], shifted)
        print(json.dumps(prof))
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
