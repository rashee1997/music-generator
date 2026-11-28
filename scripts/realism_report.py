#!/usr/bin/env python3
"""realism_report.py - measure the twelve qualities that separate a produced cue from a generated one (eight of the mix, four of the parts).

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
    'vibrato': 'a sustained part moves 3-9 Hz by 10 cents or more in 30 % of its stable held windows (starting value)',
    'repetition': 'under 40 % of a part\'s same-pitch attacks are the same sample twice (spectral similarity 0.995, starting value)',
    'velocity_response': 'brightness follows written velocity, correlation 0.30 or more once pitch is removed (starting value; the literature reads 0.62 for loudness)',
    'coherence': 'inter-channel coherence 2-8 kHz at most 0.85 (starting value)',
    'sub_weight': 'the 20-60 Hz share the stems carry reaches the master (loss at most realism.sub_loss_max_db, constants.json), starting value',
    'air': '8-16 kHz share of the master at least -40 dB; parts with no air in their samples are named (starting value)',
    'dynamic_scale': 'loudest section mean at least 10 dB above the quietest (starting value)',
    'impact_attack': 'a struck part rises in 30 ms or less or carries a click above -18 dB (starting value)',
    'foreground': 'a voice the score declares in `foreground` is within 12 dB of the loudest part while it plays (starting value)',
    'harmonic_motion': 'a section over 20 s moves the bass or declares a `pedal` (starting value)',
}

SECTION_WORDS = ('string', 'violin', 'viola', 'cello', 'celli', 'bass', 'brass', 'horn', 'trumpet', 'trombone', 'tuba',
                 'wind', 'flute', 'oboe', 'clarinet', 'bassoon', 'choir', 'voice', 'section', 'ensemble', 'tutti')
BANDS = ((20.0, 80.0, 'sub'), (180.0, 450.0, 'low_mid'), (500.0, 2000.0, 'mid'),
         (2000.0, 8000.0, 'high'), (8000.0, 16000.0, 'air'))
ATTACK_BANDS = (50.0, 150.0, 300.0, 600.0, 1200.0, 2400.0, 4800.0, 9600.0, 16000.0)


def _order(key):
    return int(key.split('_', 1)[0])


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


def _players(track):
    """The players a section part declares: its own `ensemble` block, else its instrument preset's (the renderer reads both)."""
    blk = track.get('ensemble')
    if not blk:
        try:
            import presets
            cfg = presets.find_instrument(str(track.get('instrument', '')))
            blk = (cfg or {}).get('ensemble')
        except Exception:
            blk = None
    return int((blk or {}).get('players', 1) or 1)


def ensemble(score):
    if not score:
        return dict(value=None, verdict='N/A', note='no score given')
    tracks = score.get('tracks', []) or []
    named = [t for t in tracks if any(w in str(t.get('name', '')).lower() for w in SECTION_WORDS)]
    declared = sum(_players(t) for t in named)
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


def distance(project, score=None):
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
    medium = ((score or {}).get('medium') or {})
    modelled = str(medium.get('model', '')).startswith('iso9613') and bool(medium.get('state'))      # the score's own medium is the air model of every source in it
    missing = [] if modelled else [r for r in far if not r['temp'] and r['absorption']]
    # ISO 9613-1 at 20 C / 50 % RH: 4 kHz alpha is 0.02967 dB/m, so this is the predicted high-band loss
    worst = max((0.02967 * max(0.0, r['distance_m'] - 1.0) for r in far), default=0.0)
    return dict(value=len(rows), far=int(len(far)), missing_model=int(len(missing)),
                predicted_4k_loss_db=round(float(worst), 2),
                verdict='PASS' if not missing else 'WARN',
                note=('every far source has an air model' + (' (the score\'s medium, ISO 9613-1)' if modelled else '')) if not missing
                     else f'{len(missing)} far source(s) have no temperature/humidity air model')


# ------------------------------------------------------------------ the four per-stem and stereo dimensions (9-12)
# Starting values, not measured on a reference cue. Direction and reference figures (search-result text only): a typical string vibrato is about
# 6 per second and about 30 cents, varying 10-60 cents (Fletcher and Sanders, cited in the vibrato literature); a detector counts a pitch
# half-cycle as vibrato at 2-10 Hz and more than 0.1 semitone; the spectral centroid correlates 0.62 with dynamic level across five
# nonpercussive instruments (Timbre 2018 study); spaced pickup lowers inter-channel coherence and with it the sense of envelopment.
VIBRATO_MIN_CENTS = 10.0           # the detector's 0.1 semitone
VIBRATO_BAND_HZ = (3.0, 9.0)       # inside the 2-10 Hz window, away from the slow drift of a note and from tremolo
SUSTAIN_MIN_S = 0.9                # a part whose median note is shorter than this is not a sustained part
VIBRATO_SHARE_MIN = 0.30
REPEAT_SIM = 0.995                 # the same value the master-level transient dimension uses
REPEAT_SHARE_MAX = 0.40
VELOCITY_R_MIN = 0.30              # a velocity layer response: brightness follows the written velocity (the literature reads 0.62 for loudness)
COHERENCE_MAX = 0.85


def _stem_dict(stems):
    """Stems as {name: array}. A list (the older call) has no names, so the per-stem dimensions skip it."""
    if isinstance(stems, dict):
        return stems
    return {}


def _track_map(score):
    return {t.get('name'): t for t in ((score or {}).get('tracks') or []) if t.get('name')}


def _tempo(score):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import humanize as hz
    return hz.tempo_map_for(score, seed=score.get('seed', 1))


def _is_sustained(track, tm):
    notes = [n for n in (track.get('notes') or []) if isinstance(n.get('p'), (int, float))]
    if len(notes) < 3:
        return False
    secs = [float(tm.sec(float(n['t']) + float(n.get('d', 0.0)))) - float(tm.sec(float(n['t']))) for n in notes]
    return float(np.median(secs)) >= SUSTAIN_MIN_S


def _peak_track(x, sr, lo=100.0, hi=2000.0):
    """Frequency of the strongest partial per 10 ms frame, from a 58 ms window zero-padded to 4096 points on a signal brought down to 8.8 kHz."""
    from scipy.signal import resample_poly
    q = max(1, int(round(sr / 8820.0)))
    y = resample_poly(np.asarray(x, np.float64), 1, q) if q > 1 else np.asarray(x, np.float64)
    fs = sr / float(q)
    nper, nfft, hop = 512, 4096, int(round(fs * 0.01))
    f, t, Z = signal.stft(y, fs=fs, nperseg=nper, noverlap=nper - hop, nfft=nfft, boundary=None, padded=False)
    mag = np.abs(Z)
    band = (f >= lo) & (f <= hi)
    sub = mag[band]
    k = np.argmax(sub, axis=0)
    peak = sub[k, np.arange(sub.shape[1])]
    med = np.median(sub, axis=0) + 1e-12
    idx = np.where(band)[0][k]
    a = mag[np.clip(idx - 1, 0, len(f) - 1), np.arange(mag.shape[1])]
    c = mag[np.clip(idx + 1, 0, len(f) - 1), np.arange(mag.shape[1])]
    b = mag[idx, np.arange(mag.shape[1])]
    denom = a - 2.0 * b + c
    shift = np.where(np.abs(denom) > 1e-12, 0.5 * (a - c) / denom, 0.0)
    freq = f[idx] + np.clip(shift, -1.0, 1.0) * (f[1] - f[0])
    freq = np.where(peak / med > 12.0, freq, np.nan)
    return freq, 1.0 / (hop / fs)


def vibrato_share(x, sr):
    """Share of stable one-second windows of a sustained part whose pitch moves 3-9 Hz by at least 10 cents; (share, windows)."""
    freq, frame_rate = _peak_track(_mono(x), sr)
    win = int(frame_rate)
    if len(freq) < win * 2:
        return 0.0, 0
    cents = np.full(len(freq), np.nan)
    ok = np.isfinite(freq)
    cents[ok] = 1200.0 * np.log2(freq[ok])
    hits = total = 0
    for a in range(0, len(cents) - win, win // 2):
        w = cents[a:a + win]
        if np.mean(np.isfinite(w)) < 0.9:
            continue
        idx = np.arange(win)
        good = np.isfinite(w)
        w = np.interp(idx, idx[good], w[good])
        trend = np.polyval(np.polyfit(idx, w, 2), idx)           # the note's own slow drift and any slide
        dev = w - trend
        if np.max(np.abs(np.diff(trend))) > 8.0:                 # a slide or a note change inside the window: not a held note
            continue
        spec = np.abs(np.fft.rfft(dev * np.hanning(win))) * 2.0 / (np.sum(np.hanning(win)) + 1e-12)
        fr = np.fft.rfftfreq(win, 1.0 / frame_rate)
        m = (fr >= VIBRATO_BAND_HZ[0]) & (fr <= VIBRATO_BAND_HZ[1])
        total += 1
        if m.any() and float(spec[m].max()) >= VIBRATO_MIN_CENTS:
            hits += 1
    return (hits / total if total else 0.0), total


def vibrato(stems, score=None):
    stems = _stem_dict(stems)
    if not stems or not score:
        return dict(value=None, verdict='N/A', note='needs the dry stems by name and the score')
    tm = _tempo(score)
    tracks = _track_map(score)
    rows = {}
    for name, x in stems.items():
        tr = tracks.get(name)
        if not tr or not _is_sustained(tr, tm) or str(tr.get('role')) in ('drum', 'fx', 'environment', 'texture'):
            continue
        share, n = vibrato_share(x, int(score.get('_sr', SR_DEFAULT)))
        if n >= 4:
            rows[name] = round(share, 2)
    if not rows:
        return dict(value=None, verdict='N/A', note='no sustained part with enough stable held notes to measure')
    flat = sorted(n for n, v in rows.items() if v < VIBRATO_SHARE_MIN)
    med = float(np.median(list(rows.values())))
    return dict(value=round(med, 2), parts=rows, verdict='PASS' if not flat else 'WARN',
                note=('every sustained part moves in pitch' if not flat
                      else f'{len(flat)} sustained part(s) hold a flat pitch (no 3-9 Hz movement of 10 cents or more): {", ".join(flat[:6])}'))


def _attack_vector(x, start, sr, win_s=0.08):
    n = int(win_s * sr)
    seg = np.asarray(x[start:start + n], np.float64)
    if len(seg) < n // 2:
        return None, None
    seg = np.pad(seg, (0, n - len(seg))) * np.hanning(n)
    mag = np.abs(np.fft.rfft(seg, 4096))
    return np.log10(mag + 1e-9), int(np.argmax(mag))


def repetition(stems, score=None):
    """Per stem: of the attacks on the same pitch, the share that are the same sample twice (the machine-gun tell)."""
    stems = _stem_dict(stems)
    if not stems:
        return dict(value=None, verdict='N/A', note='needs the dry stems by name')
    rows = {}
    for name, x in stems.items():
        mono = _mono(x)
        sr = int(SR_DEFAULT)
        on = detect_onsets(mono, sr)
        if len(on) < 8:
            continue
        groups = {}
        for o in on:
            v, peak = _attack_vector(mono, int(o), sr)
            if v is None or float(np.max(v)) < -2.0:
                continue
            groups.setdefault(peak // 3, []).append(v - v.mean())
        pairs = same = 0
        for vs in groups.values():
            for a, b in zip(vs, vs[1:]):
                pairs += 1
                c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
                same += c >= REPEAT_SIM
        if pairs >= 8:
            rows[name] = round(same / pairs, 2)
    if not rows:
        return dict(value=None, verdict='N/A', note='no part repeats a pitch often enough to compare its attacks')
    bad = sorted(n for n, v in rows.items() if v >= REPEAT_SHARE_MAX)
    return dict(value=round(max(rows.values()), 2), parts=rows, verdict='PASS' if not bad else 'WARN',
                note=('repeated attacks differ' if not bad
                      else f'{len(bad)} part(s) repeat a pitch with the same attack: {", ".join(bad[:6])}'))


def velocity_response(stems, score=None):
    """Per monophonic stem: does the brightness of a note's attack (up to 250 ms, never into the next note) follow its written velocity once the pitch is taken out?"""
    stems = _stem_dict(stems)
    if not stems or not score:
        return dict(value=None, verdict='N/A', note='needs the dry stems by name and the score')
    tm = _tempo(score)
    tracks = _track_map(score)
    sr = int(SR_DEFAULT)
    rows, spread = {}, {}
    for name, x in stems.items():
        tr = tracks.get(name)
        if not tr or str(tr.get('role')) in ('drum', 'fx', 'environment'):
            continue
        notes = [n for n in (tr.get('notes') or []) if isinstance(n.get('p'), (int, float)) and isinstance(n.get('v'), (int, float))]
        if len(notes) < 12:
            continue
        starts = np.array([float(tm.sec(float(n['t']))) for n in notes])
        ends = np.array([float(tm.sec(float(n['t']) + float(n.get('d', 0.5)))) for n in notes])
        order = np.argsort(starts)
        if np.mean(starts[order][1:] < ends[order][:-1] - 0.05) > 0.25:        # chords and overlaps: one window holds several notes
            continue
        vel = np.array([float(n['v']) for n in notes])
        if np.ptp(vel) < (0.15 if vel.max() <= 1.0 else 20.0):
            continue
        mono = _mono(x).astype(np.float64)
        cents, pitch, v_used = [], [], []
        nxt = np.append(np.sort(starts)[1:], np.inf)
        gap = dict(zip(np.sort(starts).tolist(), nxt.tolist()))
        for n, t0, v in zip(notes, starts, vel):
            # the window is the note's own attack: 250 ms at most, and never into the next note (an eighth at 140 bpm is 210 ms)
            win = min(0.25, float(gap.get(float(t0), np.inf)) - float(t0) - 0.02)
            if win < 0.06:
                continue
            a = int((t0 + 0.01) * sr)
            seg = mono[a:a + int(win * sr)]
            if len(seg) < int(0.05 * sr) or float(np.sqrt(np.mean(seg ** 2))) < 1e-4:
                continue
            spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 8192)) ** 2
            f = np.fft.rfftfreq(8192, 1.0 / sr)
            cents.append(float(np.log2(np.sum(f * spec) / np.sum(spec) + 1.0)))
            pitch.append(float(n['p']))
            v_used.append(v)
        if len(cents) < 12:
            continue
        c, p, v = np.array(cents), np.array(pitch), np.array(v_used)
        resid = c - np.polyval(np.polyfit(p, c, 1), p) if np.ptp(p) > 0 else c - c.mean()
        if np.std(v) < 1e-9:
            continue
        # a part whose attack centroid barely moves (under 0.02 octave, about 1.4 %) has no brightness response to correlate: the correlation of
        # numerical noise with velocity is not evidence, so it reads as 0
        rows[name] = round(float(np.corrcoef(resid, v)[0, 1]), 2) if np.std(resid) >= 0.02 else 0.0
        spread[name] = round(float(np.std(resid)), 3)
    if not rows:
        return dict(value=None, verdict='N/A', note='no single-line part with a spread of written velocities to compare')
    flat = sorted(n for n, r in rows.items() if r < VELOCITY_R_MIN)
    return dict(value=round(float(np.median(list(rows.values()))), 2), parts=rows, centroid_spread_octaves=spread, verdict='PASS' if not flat else 'WARN',
                note=('brightness follows velocity in every measured part' if not flat
                      else f'{len(flat)} part(s) get louder but not brighter with velocity (a one-sample layer): {", ".join(flat[:6])}'))


def coherence(master, sr):
    """Inter-channel coherence of the master from 2 to 8 kHz: a mix that is near mono at the top has no spaced-pickup envelopment."""
    x = np.asarray(master, np.float64)
    if x.ndim != 2 or x.shape[1] < 2:
        return dict(value=None, verdict='N/A', note='needs a two-channel master')
    f, c = signal.coherence(x[:, 0], x[:, 1], fs=sr, nperseg=4096)
    band = (f >= 2000.0) & (f <= 8000.0)
    mid = (f >= 500.0) & (f < 2000.0)
    v = float(np.mean(c[band]))
    return dict(value=round(v, 2), mid=round(float(np.mean(c[mid])), 2), verdict='PASS' if v <= COHERENCE_MAX else 'WARN',
                note='the top of the mix is decorrelated between the channels' if v <= COHERENCE_MAX else 'the top of the mix is nearly the same in both channels')



def analyse(master, sr, stems=None, score=None, project=None):
    """`stems` is {name: array} (the per-stem dimensions 9-11 need the names) or a list (dimensions 1-8 only)."""
    f = _frame_features(master, sr)
    if isinstance(stems, dict) and score:
        names = {t.get('name') for t in (score.get('tracks') or [])}
        stems = {k: v for k, v in stems.items() if k in names}          # a stems folder keeps the files of earlier versions of the cue: only the score's own parts count
    plain = list(stems.values()) if isinstance(stems, dict) else stems
    out = {
        'source': dict(sr=sr, seconds=round(len(master) / float(sr), 2), stems=len(stems or [])),
        '1_timbre_loudness': timbre_loudness(f),
        '2_ensemble': ensemble(score),
        '3_transient': transient_similarity(master, sr),
        '4_depth': depth(master, plain, sr),
        '6_distance': distance(project, score),
        '7_openness': openness(f),
        '8_phrasing': phrasing(score),
    }
    # the low-mid dimension needs the time-domain band pass, not the frame summary
    out['5_low_mid'] = low_mid_bands(master, sr)
    sc = dict(score or {}, _sr=sr)
    out['9_vibrato'] = vibrato(stems, sc)
    out['10_repetition'] = repetition(stems, sc)
    out['11_velocity_response'] = velocity_response(stems, sc)
    out['12_coherence'] = coherence(master, sr)
    import realism_cinema as rc
    sd = stems if isinstance(stems, dict) else {}
    out['13_sub_weight'] = rc.sub_weight(master, sd, sr)
    out['14_air'] = rc.air(master, sd, sr)
    out['15_dynamic_scale'] = rc.dynamic_scale(master, sr, score)
    out['16_impact_attack'] = rc.impact_attack(sd, sr, score)
    out['17_foreground'] = rc.foreground(sd, sr, score)
    out['18_harmonic_motion'] = rc.harmonic_motion(score)
    return out


DIMENSION = {'1_timbre_loudness': 'timbre', '2_ensemble': 'ensemble', '3_transient': 'transient',
             '4_depth': 'depth', '5_low_mid': 'low_mid', '6_distance': 'distance',
             '7_openness': 'openness', '8_phrasing': 'phrasing', '9_vibrato': 'vibrato', '10_repetition': 'repetition',
             '11_velocity_response': 'velocity_response', '12_coherence': 'coherence',
             '13_sub_weight': 'sub_weight', '14_air': 'air', '15_dynamic_scale': 'dynamic_scale',
             '16_impact_attack': 'impact_attack', '17_foreground': 'foreground', '18_harmonic_motion': 'harmonic_motion'}


def format_report(r):
    lines = [f"Realism report  {r['source']['seconds']} s, {r['source']['sr']} Hz, "
             f"{r['source']['stems']} dry stem(s)"]
    for key in sorted((k for k in r if k[0].isdigit()), key=_order):
        d = r[key]
        name = key.split('_', 1)[1].replace('_', ' ')
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
    for key in sorted((k for k in reports[0] if k[0].isdigit()), key=_order):
        cells = []
        for r in reports:
            d = r[key]
            value = d.get('value')
            cells.append(f"{d['verdict']:<4}" + (f' {value}' if value is not None else ''))
        lines.append(f"{key.split('_', 1)[1].replace('_', ' '):<14} " + '  |  '.join(cells))
    return '\n'.join(lines)


def _align(y, stems_dir, path, sr):
    """A stem file starts where its part first sounds (stems.json `start_s`); pad it back to the cue's clock so a score time is a sample index."""
    try:
        with open(os.path.join(stems_dir, 'stems.json'), encoding='utf-8') as fh:
            man = json.load(fh)
        start = float((man.get(os.path.splitext(os.path.basename(path))[0]) or {}).get('start_s', 0.0))
    except (OSError, ValueError):
        start = 0.0
    n = int(round(start * sr))
    return np.pad(y, ((n, 0), (0, 0))) if n > 0 and y.ndim == 2 else (np.pad(y, (n, 0)) if n > 0 else y)


REALISM_REGISTERS = ('cinematic', 'orchestral', 'hybrid', 'theatrical', 'epic', 'trailer')


def wanted(score):
    """True when the pipeline should run this report after a certified render: a cue briefed as cinematic, orchestral, hybrid or theatrical
    (`intent.registers`, or `intent.emotions` naming one), unless the score says `"realism": false`; `"realism": true` asks for it on any
    piece. It is advisory, so a piece that does not need it is simply not measured."""
    flag = (score or {}).get('realism')
    if flag is not None:
        return bool(flag)
    intent = (score or {}).get('intent') or {}
    words = [str(w).lower() for key in ('registers', 'emotions', 'scenes') for w in (intent.get(key) or [])]
    return any(w in REALISM_REGISTERS for w in words)


def rows_from(report):
    """The report as pipeline rows: [(level, row name, detail)], WARN or PASS, never FAIL (the report measures, it does not judge a render)."""
    out = []
    for key in sorted((k for k in report if k[0].isdigit()), key=_order):
        d = report[key]
        name = 'realism.' + key.split('_', 1)[1]
        value = d.get('value')
        out.append(('WARN' if d.get('verdict') == 'WARN' else 'PASS', name,
                    (f"value {value}: " if value is not None else '') + str(d.get('note', ''))
                    + f" (target: {TARGETS.get(DIMENSION.get(key, ''), '')})"))
    return out


def run_after_certification(project_dir, score, master_wav, stems_dir=None):
    """Measure the certified master and write the result next to the other gate artefacts: presets/gate/data/realism.json and realism.txt
    (never reports/, which holds research, the CI report and the debug autopsy). Returns (rows, path of the json)."""
    master, sr = load_audio(master_wav)
    stems = {}
    if stems_dir and os.path.isdir(stems_dir):
        for p in sorted(glob.glob(os.path.join(stems_dir, '*.wav'))):
            y, _ = load_audio(p)
            stems[os.path.splitext(os.path.basename(p))[0]] = _align(y, stems_dir, p, sr)
    r = analyse(master, sr, stems=stems, score=score, project=project_dir)
    import gate_profiles
    d = gate_profiles.data_dir(project_dir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, 'realism.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(dict(master=os.path.basename(master_wav), report=r), fh, indent=2)
    with open(os.path.join(d, 'realism.txt'), 'w', encoding='utf-8') as fh:
        fh.write(format_report(r) + '\n')
    return rows_from(r), path


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
    stems = {}
    if a.stems:
        for p in sorted(glob.glob(os.path.join(a.stems, '*.wav'))):
            y, _ = load_audio(p)
            stems[os.path.splitext(os.path.basename(p))[0]] = _align(y, a.stems, p, sr)
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
