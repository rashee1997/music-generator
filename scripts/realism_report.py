#!/usr/bin/env python3
"""realism_report.py - measure the eight qualities that separate a produced cue from a generated one.

The gate says a render is not faulty. It does not say the timbre changes with loudness, that a section is a room
of players rather than one player multiplied, that the attack is in front of the hall, that the low-mids stay lean
while the sub carries the weight, or that the phrases breathe at the bar rather than the note. This file measures
those, from the master, the dry stems, the score and the project presets. It is a report, not a gate: nothing here
changes a render, and a PASS is not a claim that the cue is good.

Thresholds are starting values (the knowledge base records what is measured and what is practice). Calibrate them
on a reference cue before treating any of them as a rule.

    python scripts/realism_report.py out/master.wav --score scores/x.json --stems out/stems --project .
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d

SR_DEFAULT = 44100

# (dimension, figure, starting value, why). Values without a measured source are marked in the knowledge base.
TARGETS = {
    'timbre': 'loud passages at least 0.8 dB brighter (centroid) and 0.5 dB more 2-8 kHz energy than quiet ones',
    'ensemble': 'a section part declares 2+ players; a solo declares none',
    'transient': 'repeated attacks are not sample-identical: 60 ms spectral similarity <= 0.995',
    'depth': 'direct-to-reverberant ratio -6..+18 dB: detail in front of a hall, not inside it',
    'low_mid': '180-450 Hz stays below the 500-2000 Hz band and does not grow faster than the sub at a peak',
    'distance': 'a source beyond 4 m uses the ISO 9613-1 air model or says why not',
    'openness': 'the 8-16 kHz share does not fall by more than 1 dB at the loudest 10 % of the piece',
    'phrasing': 'bar-scale tempo deviation 1-8 % over the body, excluding the final ritardando',
}

SECTION_WORDS = ('string', 'violin', 'viola', 'cello', 'bass', 'brass', 'horn', 'trumpet', 'trombone', 'tuba',
                 'wind', 'flute', 'oboe', 'clarinet', 'bassoon', 'choir', 'voice', 'section', 'ensemble', 'tutti')
BANDS = ((20.0, 80.0, 'sub'), (180.0, 450.0, 'low_mid'), (500.0, 2000.0, 'mid'),
         (2000.0, 8000.0, 'high'), (8000.0, 16000.0, 'air'))
ATTACK_BANDS = (50.0, 150.0, 300.0, 600.0, 1200.0, 2400.0, 4800.0, 9600.0, 16000.0)


def _db(power):
    return 10.0 * np.log10(float(power) + 1e-24)


def _mono(x):
    x = np.asarray(x, dtype=np.float32)
    return x.mean(axis=1) if x.ndim == 2 else x


def load_audio(path):
    import soundfile as sf
    x, sr = sf.read(path, always_2d=True)
    return np.asarray(x, dtype=np.float32), int(sr)


def _frame_features(x, sr, win_s=0.5, hop_s=0.25):
    """Level and spectral features per frame: the raw material for four of the eight dimensions."""
    mono = _mono(x).astype(np.float64)
    win = max(256, int(win_s * sr))
    hop = max(64, int(hop_s * sr))
    if len(mono) < win:
        mono = np.pad(mono, (0, win - len(mono)))
    n = 1 + (len(mono) - win) // hop
    window = signal.windows.hann(win, sym=False)
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    feats = {k: [] for k in ('level_db', 'centroid', 'hf_ratio', 'air_ratio')}
    for i in range(n):
        seg = mono[i * hop:i * hop + win]
        level = 20.0 * np.log10(float(np.sqrt(np.mean(seg ** 2)) + 1e-12))
        spec = np.abs(np.fft.rfft(seg * window)) ** 2
        total = float(spec.sum()) + 1e-24
        feats['level_db'].append(level)
        feats['centroid'].append(float((freqs * spec).sum() / total))
        bands = {}
        for lo, hi, tag in BANDS:
            m = (freqs >= lo) & (freqs < hi)
            bands[tag] = float(spec[m].sum()) + 1e-24
        speech = bands['low_mid'] + bands['mid'] + bands['high']
        feats['hf_ratio'].append(bands['high'] / max(bands['sub'] + bands['low_mid'] + bands['mid'], 1e-24))
        feats['air_ratio'].append(bands['air'] / max(speech, 1e-24))
    out = {k: np.asarray(v) for k, v in feats.items()}
    out['active'] = out['level_db'] > float(out['level_db'].max()) - 50.0
    return out


def _levels(f):
    """(quiet mask, loud mask) over the sounding frames."""
    lv, act = f['level_db'], f['active']
    if int(act.sum()) < 8:
        return None, None
    sounding = lv[act]
    q = float(np.percentile(sounding, 30.0))
    l = float(np.percentile(sounding, 90.0))
    if l - q < 2.0:
        return None, None
    return act & (lv <= q), act & (lv >= l)


def _ratio_db(a, b):
    """One band against another in dB, bounded: a band that is absent in one side is not a 200 dB effect."""
    return float(np.clip(10.0 * np.log10((float(a) + 1e-24) / (float(b) + 1e-24)), -30.0, 30.0))


def timbre_loudness(f):
    q, l = _levels(f)
    if q is None:
        return dict(value=None, verdict='N/A', note='no dynamic range to follow (quiet and loud frames are the same)')
    cq = float(np.median(f['centroid'][q]))
    cl = float(np.median(f['centroid'][l]))
    hf = _ratio_db(float(np.mean(f['hf_ratio'][l])), float(np.mean(f['hf_ratio'][q])))
    shift = float(20.0 * np.log10((cl + 1e-9) / (cq + 1e-9)))
    ok = shift >= 0.8 and hf >= 0.5
    return dict(value=round(shift, 2), hf_shift_db=round(hf, 2), centroid_quiet_hz=round(cq, 1),
                centroid_loud_hz=round(cl, 1), verdict='PASS' if ok else 'WARN',
                note='timbre follows loudness' if ok else 'loud and quiet differ mainly in volume')


def ensemble(score):
    if not score:
        return dict(value=None, verdict='N/A', note='no score given')
    tracks = score.get('tracks', []) or []
    named = [t for t in tracks if any(w in str(t.get('name', '')).lower() for w in SECTION_WORDS)]
    declared = sum(int((t.get('ensemble') or {}).get('players', 1) or 1) for t in named)
    if not named:
        return dict(value=0, verdict='INFO', note='no section-named parts in the score')
    ok = declared > len(named)
    return dict(value=declared, tracks=len(named), verdict='PASS' if ok else 'WARN',
                note=f'{declared} player(s) across {len(named)} section part(s)'
                     + ('' if ok else '; each section is one player multiplied'))


def detect_onsets(x, sr, hop=256, min_gap_s=0.04):
    mono = _mono(x).astype(np.float64)
    win = 1024
    if len(mono) < win * 2:
        return np.zeros(0, dtype=int)
    window = signal.windows.hann(win, sym=False)
    frames = 1 + (len(mono) - win) // hop
    mags = np.empty((frames, win // 2 + 1), np.float32)
    for i in range(frames):
        mags[i] = np.abs(np.fft.rfft(mono[i * hop:i * hop + win] * window))
    flux = np.maximum(0.0, np.diff(mags, axis=0)).sum(axis=1)
    if flux.size < 4:
        return np.zeros(0, dtype=int)
    thr = float(np.median(flux) + 3.0 * np.std(flux))
    cand = np.flatnonzero(flux > thr) + 1
    out, last = [], -10 ** 9
    for c in cand:
        t = c * hop
        if t - last >= int(min_gap_s * sr):
            out.append(t)
            last = t
    return np.asarray(out, dtype=int)


def transient_similarity(x, sr):
    ix = detect_onsets(x, sr)
    if len(ix) < 6:
        return dict(value=None, onsets=int(len(ix)), verdict='N/A', note='fewer than 6 isolated onsets')
    mono = _mono(x).astype(np.float64)
    n = int(0.06 * sr)
    win = signal.windows.hann(n, sym=False)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    vecs, levels = [], []
    for i in ix:
        seg = mono[i:i + n]
        if len(seg) < n:
            continue
        levels.append(20.0 * np.log10(float(np.sqrt(np.mean(seg ** 2))) + 1e-12))
        spec = np.abs(np.fft.rfft(seg * win)) ** 2
        band = []
        for lo, hi in zip(ATTACK_BANDS[:-1], ATTACK_BANDS[1:]):
            m = (freqs >= lo) & (freqs < hi)
            band.append(float(spec[m].sum()) + 1e-24)
        v = np.log10(np.asarray(band))
        vecs.append((v - v.mean()) / (v.std() + 1e-9))
    if len(vecs) < 4:
        return dict(value=None, onsets=int(len(ix)), verdict='N/A', note='no usable attack windows')
    sims = []
    for i in range(1, len(vecs)):
        if abs(levels[i] - levels[i - 1]) <= 6.0:
            sims.append(float(np.dot(vecs[i - 1], vecs[i]) / len(vecs[i])))
    if not sims:
        return dict(value=None, onsets=int(len(ix)), verdict='N/A', note='no attacks at a comparable level')
    mean = float(np.mean(sims))
    return dict(value=round(mean, 4), onsets=len(sims), verdict='PASS' if mean <= 0.995 else 'WARN',
                note='attacks vary' if mean <= 0.995 else 'consecutive attacks share one spectral shape')


def depth(master, stems, sr):
    if not stems:
        return dict(value=None, verdict='N/A', note='no dry stems: a direct-to-reverberant ratio cannot be separated')
    dry = np.zeros((len(master), 2), np.float32)
    for y in stems:
        k = min(len(dry), len(y))
        dry[:k] += y[:k]
    k = min(len(dry), len(master))
    wet = master[:k] - dry[:k]
    rd = float(np.sqrt(np.mean(dry[:k].astype(np.float64) ** 2)) + 1e-12)
    rw = float(np.sqrt(np.mean(wet.astype(np.float64) ** 2)) + 1e-12)
    drr = float(20.0 * np.log10(rd / rw))
    if not np.isfinite(drr) or rw < 1e-9 * max(rd, 1e-12):
        return dict(value=None, verdict='N/A', note='the master is the dry stems: no room to measure')
    ok = -6.0 <= drr <= 18.0
    return dict(value=round(drr, 2), wet_share=round(float(rw ** 2 / (rd ** 2 + rw ** 2)), 4),
                verdict='PASS' if ok else 'WARN',
                note='detail sits in front of the room' if ok else 'either a wash or no room at all')


def low_mid_bands(x, sr):
    mono = _mono(x).astype(np.float64)
    band = {tag: signal.sosfilt(signal.butter(3, [lo, min(hi, sr * 0.45)], btype='band', fs=sr, output='sos'),
                                mono) for lo, hi, tag in BANDS if hi > lo}
    power = {tag: float(np.mean(y ** 2)) + 1e-24 for tag, y in band.items()}
    lv = 20.0 * np.log10(np.abs(mono) + 1e-12)
    active = lv > lv.max() - 50.0
    quiet = active & (lv <= np.percentile(lv[active], 30.0))
    loud = active & (lv >= np.percentile(lv[active], 90.0))

    def band_level(mask, tag):
        return 10.0 * np.log10(float(np.mean(band[tag][mask] ** 2)) + 1e-24)

    thick = 10.0 * np.log10(power['low_mid'] / power['mid'])
    over_sub = 10.0 * np.log10(power['low_mid'] / power['sub'])
    growth_lm = band_level(loud, 'low_mid') - band_level(quiet, 'low_mid')
    growth_sub = band_level(loud, 'sub') - band_level(quiet, 'sub')
    ok = thick <= 0.0 and (growth_lm - growth_sub) <= 1.5
    return dict(value=round(thick, 2), low_mid_over_sub_db=round(over_sub, 2),
                low_mid_growth_db=round(growth_lm, 2), sub_growth_db=round(growth_sub, 2),
                verdict='PASS' if ok else 'WARN',
                note='lean low-mids, sub carries the weight' if ok else 'low-mids thicken or grow into the peak')


def openness(f):
    q, l = _levels(f)
    if q is None:
        return dict(value=None, verdict='N/A', note='no dynamic range to compare')
    aq = float(np.median(f['air_ratio'][q]))
    al = float(np.median(f['air_ratio'][l]))
    drop = _ratio_db(al, aq)
    verdict = 'PASS' if drop >= -1.0 else ('WARN' if drop <= -2.0 else 'INFO')
    return dict(value=round(drop, 2), verdict=verdict,
                note='air survives the peak' if drop >= -1.0 else 'the top closes in at density')


def phrasing(score):
    if not score:
        return dict(value=None, verdict='N/A', note='no score given')
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import humanize as hz
    tm = hz.tempo_map_for(score, seed=score.get('seed', 1))
    total = float(tm.total_beats)
    body = max(8.0, total - 8.0)                     # exclude the written final ritardando
    grid = np.arange(0.0, body, 0.25)
    if len(grid) < 16:
        return dict(value=None, verdict='N/A', note='shorter than four bars: no bar-scale phrasing to measure')
    secs = np.asarray(tm.sec(grid), dtype=float)
    step = np.diff(secs)                              # seconds per quarter beat
    if not np.all(np.isfinite(step)) or float(np.median(step)) <= 0.0:
        return dict(value=None, verdict='N/A', note='tempo map is not usable')
    dev = step / float(np.median(step)) - 1.0
    smooth = uniform_filter1d(dev, size=16, mode='nearest')     # over four beats
    cv = 100.0 * float(np.std(smooth))
    peak = 100.0 * float(np.max(np.abs(smooth)))
    elastic = bool(score.get('elastic'))
    ok = 1.0 <= cv <= 8.0
    return dict(value=round(cv, 2), peak_pct=round(peak, 2), elastic=elastic,
                verdict='PASS' if ok else 'WARN',
                note='bar-scale breathing' if ok else ('metronomic at the bar' if cv < 1.0 else 'unstable at the bar'))


def distance(project):
    if not project:
        return dict(value=None, verdict='N/A', note='no project given')
    rows = []
    for path in glob.glob(os.path.join(project, 'presets', '**', '*.json'), recursive=True):
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                sp = node.get('spatial')
                dist = None
                if isinstance(sp, dict):
                    dist = sp.get('distance')
                prop = node.get('propagation') or ((node.get('scene') or {}).get('propagation')
                                                   if isinstance(node.get('scene'), dict) else None)
                if dist is None and isinstance(prop, dict):
                    dist = prop.get('distance_m')
                if isinstance(dist, (int, float)):
                    rows.append(dict(file=os.path.basename(path), distance_m=float(dist),
                                     temp=isinstance(sp, dict) and ('temp_c' in sp or 'rh' in sp),
                                     absorption=not (isinstance(sp, dict) and sp.get('air_absorption') is False),
                                     scene=isinstance(prop, dict) and prop.get('distance_m') is not None))
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(node)
    if not rows:
        return dict(value=None, verdict='N/A', note='no spatial distances in the project presets')
    far = [r for r in rows if r['distance_m'] > 4.0 and not r['scene']]
    missing = [r for r in far if not r['temp'] and r['absorption']]
    # ISO 9613-1 at 20 C / 50 % RH: 4 kHz alpha is 0.02967 dB/m, so this is the predicted high-band loss
    worst = max((0.02967 * max(0.0, r['distance_m'] - 1.0) for r in far), default=0.0)
    return dict(value=len(rows), far=int(len(far)), missing_model=int(len(missing)),
                predicted_4k_loss_db=round(float(worst), 2),
                verdict='PASS' if not missing else 'WARN',
                note='every far source has an air model' if not missing
                     else f'{len(missing)} far source(s) have no temperature/humidity air model')


def analyse(master, sr, stems=None, score=None, project=None):
    f = _frame_features(master, sr)
    out = {
        'source': dict(sr=sr, seconds=round(len(master) / float(sr), 2), stems=len(stems or [])),
        '1_timbre_loudness': timbre_loudness(f),
        '2_ensemble': ensemble(score),
        '3_transient': transient_similarity(master, sr),
        '4_depth': depth(master, stems, sr),
        '6_distance': distance(project),
        '7_openness': openness(f),
        '8_phrasing': phrasing(score),
    }
    # the low-mid dimension needs the time-domain band pass, not the frame summary
    out['5_low_mid'] = low_mid_bands(master, sr)
    return out


DIMENSION = {'1_timbre_loudness': 'timbre', '2_ensemble': 'ensemble', '3_transient': 'transient',
             '4_depth': 'depth', '5_low_mid': 'low_mid', '6_distance': 'distance',
             '7_openness': 'openness', '8_phrasing': 'phrasing'}


def format_report(r):
    lines = [f"Realism report  {r['source']['seconds']} s, {r['source']['sr']} Hz, "
             f"{r['source']['stems']} dry stem(s)"]
    for key in sorted(k for k in r if k[0].isdigit()):
        d = r[key]
        name = key[2:].replace('_', ' ')
        value = d.get('value')
        head = f"[{d['verdict']:<4}] {name:<14}"
        detail = f"value {value}" if value is not None else 'not measured'
        extra = ', '.join(f'{k}={v}' for k, v in d.items()
                          if k not in ('value', 'verdict', 'note') and not isinstance(v, bool))
        lines.append(f"{head} {detail}" + (f"  ({extra})" if extra else ''))
        lines.append(f"         {d.get('note', '')}")
        lines.append(f"         target: {TARGETS.get(DIMENSION.get(key, ''), '')}")
    return '\n'.join(lines)


def compare_report(reports):
    """Side-by-side verdicts for the calibration renders (off / couplings / all stages)."""
    names = [r['source']['name'] for r in reports]
    lines = ['Realism calibration  ' + '  |  '.join(names)]
    for key in sorted(k for k in reports[0] if k[0].isdigit()):
        cells = []
        for r in reports:
            d = r[key]
            value = d.get('value')
            cells.append(f"{d['verdict']:<4}" + (f' {value}' if value is not None else ''))
        lines.append(f"{key[2:].replace('_', ' '):<14} " + '  |  '.join(cells))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Measure the eight qualities of a theatrical mix.')
    ap.add_argument('master', nargs='?', help='a master wav')
    ap.add_argument('--compare', nargs='+', metavar='WAV',
                    help='calibration: two or more masters, printed side by side')
    ap.add_argument('--score')
    ap.add_argument('--stems', help='directory of dry stem wav files')
    ap.add_argument('--project', help='project directory, for the spatial presets')
    ap.add_argument('--json', help='write the measurements here instead of printing them')
    a = ap.parse_args(argv)
    if a.compare:
        reports = []
        for p in a.compare:
            y, rate = load_audio(p)
            r = analyse(y, rate)
            r['source']['name'] = os.path.basename(p)
            reports.append(r)
        print(compare_report(reports))
        return 0
    if not a.master:
        ap.error('give a master wav, or --compare with two or more')
    master, sr = load_audio(a.master)
    stems = []
    if a.stems:
        for p in sorted(glob.glob(os.path.join(a.stems, '*.wav'))):
            y, _ = load_audio(p)
            stems.append(y)
    score = None
    if a.score:
        with open(a.score, encoding='utf-8') as fh:
            score = json.load(fh)
    r = analyse(master, sr, stems=stems, score=score, project=a.project)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as fh:
            json.dump(r, fh, indent=2)
        print(f'wrote {a.json}')
    else:
        print(format_report(r))
    return 0 if all(d['verdict'] != 'WARN' for d in r.values() if isinstance(d, dict) and 'verdict' in d) else 1


if __name__ == '__main__':
    sys.exit(main())
