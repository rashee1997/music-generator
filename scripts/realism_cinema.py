"""realism_cinema.py - six realism dimensions for cinematic pieces (advisory, never a gate FAIL).

13 sub_weight        does the master keep the sub that the stems carry (20-60 Hz)?
14 air               8-16 kHz share of the master, and the parts whose own samples hold nothing there
15 dynamic_scale     how far the loud passages sit above the quiet ones (section means and 3 s windows)
16 impact_attack     rise time and click-to-body ratio of the struck parts' onsets
17 foreground        voices the score declares must be heard are not buried in the stems
18 harmonic_motion   the bass moves under a long section, or the key changes, or a pedal is declared

Nothing here reads a part name: struck parts are the tracks whose role is `drum` or whose family is struck_*; foreground
voices come from the score's own `foreground` list; harmonic_motion reads the notes. Every threshold is a STARTING VALUE
until measured on an audited render; none says a piece sounds good.
"""
import numpy as np
import gate_constants
from scipy import signal

SUB_BAND = (20.0, 60.0)
AIR_BAND = (8000.0, 16000.0)
AIR_MIN_DB = -40.0              # starting value
BAND_LIMITED_DB = -60.0         # starting value: a stem whose own 8-16 kHz share is below this has no air to raise
SCALE_MIN_DB = 10.0             # starting value: loudest minus quietest section mean (3 s windows when there are no sections)
RISE_MAX_MS = 30.0              # starting value: 10 to 90 % rise of a struck onset
CLICK_MIN_DB = -18.0            # starting value: 2-8 kHz in the first 12 ms against the body (12-160 ms)
FOREGROUND_GAP_DB = 12.0        # starting value: a declared voice more than this below the loudest part while it plays is buried
LONG_SECTION_S = 20.0           # starting value: a section longer than this needs the bass to move
STRUCK_ROLES = ('drum',)


def _mono(x):
    x = np.asarray(x, np.float64)
    return x.mean(axis=1) if x.ndim == 2 else x


def band_share_db(x, sr, band, total=(20.0, 20000.0)):
    """Share of the power in `band` over `total`, in dB, from one Welch spectrum of the whole signal."""
    y = _mono(x)
    if len(y) < 4096 or not np.any(y):
        return -200.0
    f, p = signal.welch(y, fs=sr, nperseg=8192)
    tot = p[(f >= total[0]) & (f < total[1])].sum() + 1e-30
    return float(10 * np.log10(p[(f >= band[0]) & (f < band[1])].sum() / tot + 1e-30))


def sub_weight(master, stems, sr):
    carriers = {k: band_share_db(v, sr, SUB_BAND) for k, v in (stems or {}).items()}
    carriers = {k: round(v, 1) for k, v in carriers.items() if v >= gate_constants.get('realism.sub_carrier_db')}
    m = band_share_db(master, sr, SUB_BAND)
    if not carriers:
        return dict(value=round(m, 1), verdict='PASS', carriers=0, note='no stem carries a sub, so none can be lost')
    summed = None
    for k in carriers:
        y = _mono(stems[k])
        summed = y if summed is None else summed[:min(len(summed), len(y))] + y[:min(len(summed), len(y))]
    # loss: how much lower the master's sub share is than the share of the carriers together
    loss = band_share_db(summed, sr, SUB_BAND) - m
    # The loss alone is the fault. It used to need the master to be "thin" (under -34 dB) as well, and a master at -32 dB that had lost
    # 31 dB of what its stems carried (a 105 Hz fourth-order master high-pass) read as a pass.
    bad = loss > gate_constants.get('realism.sub_loss_max_db')
    return dict(value=round(m, 1), loss_db=round(loss, 1), carriers=len(carriers), verdict='WARN' if bad else 'PASS',
                note=(f'{len(carriers)} stem(s) carry the sub ({", ".join(sorted(carriers))}) but the master keeps {loss:.1f} dB less of it '
                      'than they hold: look at the mix high-pass, ducking and the loudness stage (rca / band trace)') if bad
                else 'the sub the stems carry reaches the master')


def air(master, stems, sr):
    m = band_share_db(master, sr, AIR_BAND)
    limited = sorted(k for k, v in (stems or {}).items() if np.any(_mono(v)) and band_share_db(v, sr, AIR_BAND) < BAND_LIMITED_DB)
    bad = m < AIR_MIN_DB
    note = ('8-16 kHz is thin' + (f'; {len(limited)} part(s) hold nothing there in their own samples ({", ".join(limited[:6])}): '
                                  'EQ cannot add a band the samples lack, so use a preset `air` treatment or a bank that has it' if limited else '')
            ) if bad else 'the top octave is present'
    return dict(value=round(m, 1), band_limited=len(limited), verdict='WARN' if bad else 'PASS', note=note)


def _section_means(master, sr, sections):
    y = _mono(master)
    out = []
    for s in sections or []:
        a, b = float(s.get('start_s', 0)), float(s.get('end_s', 0))
        seg = y[int(a * sr):int(b * sr)]
        if len(seg) > sr:
            out.append((s.get('name'), 10 * np.log10(np.mean(seg ** 2) + 1e-12)))
    return out


def dynamic_scale(master, sr, score=None):
    y = _mono(master)
    sections = ((score or {}).get('plan') or {}).get('sections') or []
    secs = _section_means(master, sr, sections)
    win = int(3 * sr)
    levels = [10 * np.log10(np.mean(y[i:i + win] ** 2) + 1e-12) for i in range(0, max(1, len(y) - win), win // 2) if len(y[i:i + win]) == win]
    if len(secs) >= 3:
        vals = [v for _, v in secs]
        value = max(vals) - min(vals)
        basis = 'section means'
    elif len(levels) >= 4:
        value = float(np.percentile(levels, 95) - np.percentile(levels, 5))
        basis = '3 s windows (p95 - p5)'
    else:
        return dict(value=None, verdict='N/A', note='too short to measure')
    bad = value < SCALE_MIN_DB
    return dict(value=round(float(value), 1), basis=basis, verdict='WARN' if bad else 'PASS',
                note='the loud and the quiet passages are close in level: fortissimo reads polite' if bad else 'a wide gap between the quiet and the loud passages')


def struck_tracks(score):
    out = []
    for t in (score or {}).get('tracks') or []:
        fam = t.get('family')
        if t.get('role') in STRUCK_ROLES or (fam or '').startswith('struck'):
            out.append(t.get('name'))
    return out


def onset_metrics(x, sr, onsets):
    """(median 10-90 % rise ms, median click dB) over the onsets of a mono signal."""
    rises, clicks = [], []
    sos = signal.butter(4, [2000.0 / (sr / 2), min(8000.0, sr / 2 * 0.95) / (sr / 2)], 'band', output='sos')
    hf = signal.sosfilt(sos, x)
    for o in onsets:
        seg = np.abs(x[o:o + int(0.12 * sr)])
        if len(seg) < int(0.05 * sr):
            continue
        env = np.convolve(seg, np.ones(max(1, int(0.001 * sr))) / max(1, int(0.001 * sr)), 'same')
        pk_i = int(np.argmax(env[:int(0.1 * sr)]))
        pk = env[pk_i]
        if pk <= 1e-6:
            continue
        lo = np.flatnonzero(env[:pk_i + 1] >= 0.1 * pk)
        hi = np.flatnonzero(env[:pk_i + 1] >= 0.9 * pk)
        if len(lo) and len(hi):
            rises.append(1000.0 * (hi[0] - lo[0]) / sr)
        a = float(np.mean(hf[o:o + int(0.012 * sr)] ** 2)) + 1e-14
        b = float(np.mean(x[o + int(0.012 * sr):o + int(0.16 * sr)] ** 2)) + 1e-14
        clicks.append(10 * np.log10(a / b))
    if not rises:
        return None, None
    return float(np.median(rises)), float(np.median(clicks))


def impact_attack(stems, sr, score=None):
    names = struck_tracks(score)
    rows = {}
    import realism_report as rr
    for n in names:
        if n not in (stems or {}):
            continue
        x = _mono(stems[n])
        on = rr.detect_onsets(x, sr)
        r, c = onset_metrics(x, sr, on)
        if r is not None:
            rows[n] = (r, c)
    if not rows:
        return dict(value=None, verdict='N/A', note='no struck part (role drum, or a struck_* family) with measurable onsets')
    soft = sorted(n for n, (r, c) in rows.items() if r > RISE_MAX_MS and c < CLICK_MIN_DB)
    med = float(np.median([r for r, _ in rows.values()]))
    return dict(value=round(med, 1), parts=len(rows), soft_attack=len(soft), verdict='WARN' if soft else 'PASS',
                note=(f'{len(soft)} struck part(s) rise slowly and carry no click ({", ".join(soft[:6])}): add a beater click layer or a transient shaper in the preset')
                if soft else 'struck onsets rise fast or carry a click')


def foreground(stems, sr, score=None):
    voices = [v for v in ((score or {}).get('foreground') or []) if v in (stems or {})]
    if not (score or {}).get('foreground'):
        return dict(value=None, verdict='N/A', note='the score declares no `foreground` voices')
    win = int(0.5 * sr)
    rms = {}
    for k, v in (stems or {}).items():
        y = _mono(v)
        n = len(y) // win
        rms[k] = np.sqrt(np.mean(y[:n * win].reshape(n, win) ** 2, axis=1)) if n else np.zeros(0)
    n = min((len(r) for r in rms.values()), default=0)
    buried = {}
    for v in voices:
        own = rms[v][:n]
        others = np.max([rms[k][:n] for k in rms if k != v], axis=0) if len(rms) > 1 else np.zeros(n)
        act = own > 10 ** (-50 / 20)
        if not np.any(act):
            continue
        gap = float(np.median(20 * np.log10((others[act] + 1e-9) / (own[act] + 1e-9))))
        if gap > FOREGROUND_GAP_DB:
            buried[v] = round(gap, 1)
    return dict(value=len(buried), declared=len(voices), verdict='WARN' if buried else 'PASS',
                note=(f'declared voice(s) sit well below the loudest part while they play: {buried}') if buried
                else 'every declared voice is within reach of the loudest part')


def _beats_per_bar(score):
    """Beats per bar from the score's `ts`, written either as [4, 4] (what scores use) or as "4/4"."""
    ts = score.get('ts', [4, 4])
    if isinstance(ts, str):
        ts = [int(x) for x in ts.split('/')]
    return float(ts[0]) * 4.0 / float(ts[1])


def _bars(score, a, b):
    bpb = _beats_per_bar(score)
    return (a - 1) * bpb, b * bpb


def harmonic_motion(score):
    sections = ((score or {}).get('plan') or {}).get('sections') or []
    if not sections:
        return dict(value=None, verdict='N/A', note='the score has no plan.sections')
    bass_roles = ('bass', 'drone')
    rows, flat = [], []
    prev_hist = None
    changes = 0
    for s in sections:
        lo, hi = _bars(score, int(s.get('start_bar', 1)), int(s.get('end_bar', 1)))
        pcs, hist = set(), np.zeros(12)
        for t in score.get('tracks') or []:
            if t.get('role') in ('drum', 'environment', 'fx'):          # drum keys are names, not pitches; ambience and effects carry no harmony
                continue
            for n in t.get('notes') or []:
                if isinstance(n.get('p'), (int, float)) and lo <= float(n.get('t', 0)) < hi:
                    hist[int(n['p']) % 12] += float(n.get('d', 1))
                    if t.get('role') in bass_roles:
                        pcs.add(int(n['p']) % 12)
        if prev_hist is not None and prev_hist.any() and hist.any():
            c = float(np.corrcoef(prev_hist, hist)[0, 1])
            if c < 0.8:
                changes += 1
        prev_hist = hist
        length = float(s.get('end_s', 0)) - float(s.get('start_s', 0))
        rows.append((s.get('name'), len(pcs), length))
        if length >= LONG_SECTION_S and len(pcs) <= 1 and not s.get('pedal'):
            flat.append(s.get('name'))
    moving = sum(1 for _, n, _ in rows if n >= 2)
    return dict(value=changes, sections=len(rows), moving_bass_sections=moving, verdict='WARN' if flat else 'PASS',
                note=(f'section(s) longer than {LONG_SECTION_S:g} s sit on one bass note with no declared pedal: {", ".join(flat)}; '
                      'turn the harmony (a root move, a key change, a counter-hook) or declare `pedal` on the section') if flat
                else f'{changes} pitch-class change(s) between sections; {moving} section(s) move the bass')
