# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""gate_checks.py - pure measurements used by the stem gate and the mix gate.

Every function takes a `gate_audio.Signal` (so the load, the decimated copy and the STFT are shared) and returns a dict
with `value`, `threshold`, `margin`, `times` and a human `detail`. The maths for every row is in
`references/mixing/gate-maths.md`; thresholds marked uncalibrated there are starting values, not measurements.

No synthesis, EQ, mixing or preset values: this module only reads samples.
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt, lfilter, find_peaks

import cut_windows as _cut_windows

try:
    import librosa
except Exception:                                     # the gate must run and say what it could not measure
    librosa = None

EPS = 1e-12
HP_HZ = 6000.0
CLICK_ORDER = 4
LPC_ORDER = 16
LPC_FRAME = 1024
LPC_HOP = 512


def robust_z(x):
    """Modified z-score: 0.6745 * (x - median) / MAD."""
    x = np.asarray(x, dtype=np.float64)
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med))) + EPS
    return 0.6745 * (x - med) / mad


def _result(value, threshold, unit, times, detail, **extra):
    d = dict(value=float(value), threshold=float(threshold), unit=unit,
             margin=float(value) - float(threshold), times=[float(t) for t in times], detail=detail)
    d.update(extra)
    return d


def frame_db(sig, frame_ms=20.0, hop_ms=5.0, decimated=True):
    return sig.frame_db(frame_ms=frame_ms, hop_ms=hop_ms, decimated=decimated)


ATTACK_STEPS = 2            # two same-sign sample steps inside 8 samples is a steep attack, not a digital click


def _is_attack(mono, k, steps=ATTACK_STEPS, ratio=0.3, reach=8):
    """True when the largest step at the event is part of a short monotone ramp: an acoustic attack, not a click.

    A digital discontinuity is one sample that jumps and returns; an instrument attack moves the same way for several
    samples. Measured on a real project render, three master "clicks" at 1.078 / 1.443 / 2.899 s were monotone ramps of
    two and three samples inside a note attack (peak 0.15-0.37 FS, step 0.068-0.078), while an injected one-sample click
    is a single step. The stems were clean; the ramp steepened through the spatial/mix chain.
    """
    a = max(0, k - reach)
    b = min(len(mono) - 1, k + reach)
    d = np.diff(mono[a:b + 1])
    if d.size < 2:
        return False
    i = int(np.argmax(np.abs(d)))
    peak = float(np.abs(d[i]))
    if peak <= 0:
        return False
    sign = np.sign(d[i])
    runs = 1
    for j in range(i - 1, max(-1, i - steps - 2), -1):
        if np.sign(d[j]) == sign and abs(d[j]) >= ratio * peak:
            runs += 1
        else:
            break
    for j in range(i + 1, min(d.size, i + steps + 2)):
        if np.sign(d[j]) == sign and abs(d[j]) >= ratio * peak:
            runs += 1
        else:
            break
    return runs >= steps


def _rivals(events, sr, isolate_ms, second_ratio):
    """[bool] per (sample, amplitude) event: another event within `isolate_ms` is at least `second_ratio` as large.

    Sorted by sample index, the neighbours of an event are a slice found by bisection, not a scan of every event."""
    n = len(events)
    if not n:
        return []
    ks = np.array([k for k, _ in events], dtype=np.int64)
    amps = np.array([a for _, a in events], dtype=np.float64)
    order = np.argsort(ks, kind='stable')
    ks_s, amps_s = ks[order], amps[order]
    pos = np.empty(n, dtype=np.int64)
    pos[order] = np.arange(n)
    reach = int(np.floor(isolate_ms * sr / 1000.0))        # sample distances are integers: |d| <= reach
    out = []
    for i in range(n):
        k, a = events[i]
        lo = int(np.searchsorted(ks_s, k - reach, side='left'))
        hi = int(np.searchsorted(ks_s, k + reach, side='right'))
        count = int(np.count_nonzero(amps_s[lo:hi] >= second_ratio * a))
        if amps_s[pos[i]] >= second_ratio * a:
            count -= 1                                       # the event itself
        out.append(count > 0)
    return out


def check_clicks(sig, mad_z=8.0, floor_fs=0.02, cluster_gap_ms=1.5, isolate_ms=10.0,
                 second_ratio=0.5, quiet_ms=5.0, run_lpc=True):
    """High-pass MAD residual, clustered into impulse events, plus a Burg LPC residual count.

    The cluster step exists because a 4th-order zero-phase high-pass rings around a large impulse: measured at 44.1 kHz,
    a 0.5 FS click made 4 candidates inside 0.091 ms and a 0.2 FS click made 2 inside 0.068 ms. Rejecting any candidate
    with a neighbour within 5 ms would therefore lose the loud clicks. Candidates within `cluster_gap_ms` are one event;
    only a second distinct event of comparable amplitude within `isolate_ms` marks a cymbal/shaker burst. An event that
    sits on a short monotone ramp is an instrument attack (`_is_attack`), not a discontinuity.
    """
    mono = sig.mono
    sos = butter(CLICK_ORDER, HP_HZ, 'high', fs=sig.sr, output='sos')
    h = sosfiltfilt(sos, mono)
    r = np.diff(h)
    rz = robust_z(r)
    cand = np.flatnonzero((rz > mad_z) & (np.abs(r) > floor_fs))

    events, rejected, spans = [], 0, []
    if cand.size:
        groups, cur = [], [int(cand[0])]
        for c in cand[1:]:
            if (int(c) - cur[-1]) / sig.sr * 1000.0 <= cluster_gap_ms:
                cur.append(int(c))
            else:
                groups.append(cur)
                cur = [int(c)]
        groups.append(cur)
        for g in groups:
            span = (g[-1] - g[0]) / sig.sr * 1000.0
            if span > cluster_gap_ms:
                rejected += 1                     # a dense burst (noise, cymbal), not a single impulse
                continue
            k = int(g[int(np.argmax(np.abs(r[g])))])
            events.append((k, float(abs(r[k]))))
            spans.append(span)
        kept, attacks = [], 0
        rivals = _rivals(events, sig.sr, isolate_ms, second_ratio)
        for i, (k, a) in enumerate(events):
            rival = rivals[i]
            if rival:
                rejected += 1
            elif _is_attack(mono, k):
                attacks += 1
            else:
                kept.append((k, a))
    else:
        kept, attacks = [], 0

    lpc_count, lpc_times = (0, [])
    if run_lpc and librosa is not None and kept:
        # LPC is a second opinion on the frames the high-pass kept as a single impulse, not a full-file scan: a full
        # scan is slow and flags every frame of a clean tone at the frame edges. A dense noise burst is already rejected.
        frames = sorted({max(0, (int(k) // LPC_HOP) * LPC_HOP - LPC_HOP) for k, _ in kept})
        lpc_count, lpc_times = _lpc_clicks(sig, mad_z=mad_z, starts=frames)

    times = [k / sig.sr for k, _ in kept]
    value = max(len(kept), lpc_count)
    detail = (f'{len(kept)} clustered impulse event(s) (MAD), {lpc_count} LPC frame(s); '
              f'{rejected} event(s) rejected as a dense burst, {attacks} as a steep attack; '
              f'max cluster span {max(spans) if spans else 0:.3f} ms')
    return _result(value, 0.0, 'events', times, detail,
                   mad_count=len(kept), lpc_count=lpc_count, rejected=rejected, attacks_ignored=attacks,
                   max_cluster_span_ms=float(max(spans) if spans else 0.0))


def _lpc_clicks(sig, mad_z=8.0, starts=None):
    """Burg LPC residual on the frames that the high-pass flagged: count, frame start times."""
    mono = sig.mono
    n = LPC_FRAME
    if len(mono) < n * 2:
        return 0, []
    count, times = 0, []
    for start in (starts or []):
        if start < 0 or start + n > len(mono):
            continue
        fr = mono[start:start + n]
        rms = float(np.sqrt(np.mean(fr ** 2)))
        if rms < 1e-4:
            continue
        fr = fr / (rms + EPS)
        try:
            a = librosa.lpc(fr, order=LPC_ORDER)
            e = lfilter(a, [1.0], fr)
        except Exception:
            continue
        # a click is a spike far above the prediction error of the frame, not merely a high z of a tiny error
        err = float(np.max(np.abs(e)))
        if err > 0.2 and float(np.max(np.abs(robust_z(e)))) > mad_z:
            count += 1
            times.append(start / sig.sr)
    return count, times


def check_dropout(sig, min_ms=20.0, max_ms=1000.0, floor_below_db=45.0, edge_ms=250.0,
                  frame_ms=20.0, hop_ms=5.0, sounding=None, note_margin_s=0.03):
    """A run of frames 45 dB below the file's median and below -60 dBFS, away from both edges.

    sounding: the track's own note intervals. When given, only a hole whose middle falls inside a sounding note is a
    dropout: silence between phrases is the score's rest, not a fault. Measured on a real project, a hummed vocal stem
    read seven 20-40 ms "holes" that were all the gaps between phrases; without the score the row cannot tell a cut
    from a rest.
    """
    db, times = frame_db(sig, frame_ms, hop_ms)
    if db.size == 0:
        return _result(0.0, 0.0, 'ms', [], 'no frames')
    floor = float(np.median(db)) - floor_below_db
    quiet = (db < floor) & (db < -60.0)
    runs, i = [], 0
    while i < quiet.size:
        if not quiet[i]:
            i += 1
            continue
        j = i
        while j + 1 < quiet.size and quiet[j + 1]:
            j += 1
        a, b = times[i], times[j] + hop_ms / 1000.0
        if a >= edge_ms / 1000.0 and b <= sig.dur - edge_ms / 1000.0:
            runs.append((a, b - a))
        i = j + 1
    holes = [(a, d * 1000.0) for a, d in runs if min_ms <= d * 1000.0 <= max_ms]
    if sounding:
        spans = [(float(x), float(y)) for x, y in sounding]
        holes = [(a, d) for a, d in holes
                 if any(x - note_margin_s <= a + d / 2000.0 <= y + note_margin_s for x, y in spans)]
    longest = max((d for _, d in holes), default=0.0)
    detail = (f'longest hole {longest:.0f} ms (limit {min_ms:.0f}-{max_ms:.0f} ms), '
              f'floor {floor:.1f} dBFS; {len(holes)} hole(s)')
    return _result(longest, min_ms, 'ms', [a for a, _ in holes], detail,
                   holes=[dict(start_s=round(a, 3), length_ms=round(d, 1)) for a, d in holes])


def check_cut(sig, boundaries_s, drop_db=12.0, window_ms=20.0, hop_ms=5.0,
              recovery_db=3.0, location_ms=75.0, end_ms=200.0, silence_below_db=25.0,
              intentional_cut_windows=()):
    """A one/two-frame RMS collapse with no release, near a section boundary or at the end.

    A 15.7 dB drop at a section boundary on a clean render is an arrangement change, not a cut: the remaining layers are
    still audible. Only a step that lands near silence (below the file median by `silence_below_db`) is a hard edit.

    `intentional_cut_windows` is a list of (start_s, end_s) the direction sheet declared as hard cuts (`cut_windows.py`):
    a drop that lands inside one is the cut the piece asked for and is not counted. It exempts this one measure only; the
    detail says how many drops it skipped, so an exemption is never silent. Nothing outside a window changes.
    """
    db, times = frame_db(sig, window_ms, hop_ms)
    if db.size < 24:
        return _result(0.0, drop_db, 'dB', [], 'too short to judge')
    d = db[:-2] - db[2:]
    floor_ref = float(np.median(db))
    best, hits, exempt = 0.0, [], []
    windows = _cut_windows.windows_of(list(intentional_cut_windows or ()))
    for i in np.flatnonzero(d > drop_db):
        low = db[i + 2]
        if low > floor_ref - silence_below_db:
            continue                                    # still audible after the step: a section drop, not a cut
        nxt = db[i + 2:i + 22]
        if nxt.size and float(nxt.max() - low) >= recovery_db:
            continue                                    # it recovers: a transient, not a cut
        t = float(times[i])
        if t >= sig.dur - end_ms / 1000.0:
            continue                                    # the ending is its own row (`end.abrupt`), not a cut
        near = any(abs(t - b) <= location_ms / 1000.0 for b in boundaries_s)
        if not near:
            continue
        if any(a <= t <= z for a, z in windows):
            exempt.append(t)                            # the sheet asked for this cut: not a defect
            continue
        if float(d[i]) > best:
            best = float(d[i])
        hits.append(t)
    detail = (f'largest un-recovered step {best:.1f} dB over ~10 ms (limit {drop_db:g} dB), '
              f'{len(hits)} location(s) near a boundary/end')
    if exempt:
        detail += f'; {len(exempt)} drop(s) skipped inside {len(windows)} intentional cut window(s) (first at {exempt[0]:.3f} s)'
    return _result(best, drop_db, 'dB', hits, detail, drops=[round(float(x), 1) for x in d[np.flatnonzero(d > drop_db)][:8]],
                   exempted=[round(float(x), 4) for x in exempt[:8]])


def check_abrupt_end(sig, floor_db=-45.0, min_decay_db=12.0, tail_ms=50.0, body_ms=(300.0, 800.0),
                     expected_dur=None):
    """The last 50 ms is still loud and the final 300 ms lost less than `min_decay_db`.

    expected_dur: when given (a stem), an un-truncated stem is skipped: the mixer applies the master fade, so a stem that
    reaches the end at full level is normal. Only a stem shorter than the score duration is judged.
    """
    if expected_dur is not None and sig.dur >= float(expected_dur) - 0.05:
        return _result(0.0, min_decay_db, 'dB', [], 'not truncated: the master fade belongs to the mixer',
                       skipped=True)
    mono = sig.mono
    sr = sig.sr
    tail_n = max(1, int(tail_ms * sr / 1000.0))
    body_a = max(0, len(mono) - int(body_ms[1] * sr / 1000.0))
    body_b = max(0, len(mono) - int(body_ms[0] * sr / 1000.0))
    if len(mono) < tail_n + 10 or body_b <= body_a:
        return _result(0.0, min_decay_db, 'dB', [], 'too short to judge')
    tail = 20 * np.log10(np.sqrt(np.mean(mono[-tail_n:] ** 2)) + EPS)
    body = 20 * np.log10(np.sqrt(np.mean(mono[body_a:body_b] ** 2)) + EPS)
    decay = float(body - tail)
    fail = tail > floor_db and decay < min_decay_db
    detail = (f'end level {tail:.1f} dBFS (limit {floor_db:g}), decay over final 300 ms {decay:.1f} dB '
              f'(limit {min_decay_db:g}); ' + ('abrupt' if fail else 'natural release'))
    return _result(decay, min_decay_db, 'dB', [sig.dur] if fail else [], detail,
                   end_level_db=tail, fail=bool(fail))


def check_edge(sig, first_note_s, last_note_s, max_silence_ms=25.0, floor_below_db=60.0,
               frame_ms=20.0, hop_ms=5.0):
    """A stem's audible span against the score's own note span.

    Trim-equivalent of `librosa.effects.trim(top_db=60)` on the shared 20 ms / 5 ms frame levels: the first and last
    frame within 60 dB of the stem's loudest frame are the audible span. A stem that only starts 300 ms after its first
    written note, or stops 300 ms before its last one, was padded, offset or truncated: that is a render fault, and the
    mixer cannot repair it.
    """
    db, times = frame_db(sig, frame_ms, hop_ms)
    if db.size == 0 or not np.isfinite(db).any():
        return _result(0.0, max_silence_ms, 'ms', [], 'no frames')
    peak = float(np.max(db[np.isfinite(db)]))
    audible = np.isfinite(db) & (db >= peak - floor_below_db)
    if not audible.any():
        return _result(0.0, max_silence_ms, 'ms', [], 'no audible frame')
    first = float(times[int(np.argmax(audible))])
    last = float(times[db.size - 1 - int(np.argmax(audible[::-1]))]) + hop_ms / 1000.0
    head_ms = (first - float(first_note_s)) * 1000.0
    tail_ms = (float(last_note_s) - last) * 1000.0
    worst = max(head_ms, tail_ms, 0.0)
    fail = worst > max_silence_ms
    times_out = []
    if fail:
        times_out = [first if head_ms >= tail_ms else last]
    detail = (f'audible span {first:.3f}-{last:.3f} s against score notes {float(first_note_s):.3f}-'
              f'{float(last_note_s):.3f} s: leading silence {head_ms:.0f} ms, trailing silence {tail_ms:.0f} ms '
              f'(limit {max_silence_ms:g} ms)')
    return _result(worst, max_silence_ms, 'ms', times_out, detail,
                   head_ms=round(head_ms, 1), tail_ms=round(tail_ms, 1), fail=bool(fail))


def _peak_rise_db(sig, onset_times, win_ms=20.0):
    """How far the peak envelope jumps at each onset, in dB: the median over the onsets and how many were usable.

    The footprint of a tick is a short transient, so the statistic has to be a local *peak*: a 20 ms peak window is
    long enough to hold a cycle of a low bed (so a steady tone reads flat) and short enough to see a 5 ms burst. A
    sinusoidal projection of the frame level cannot see one at all (a 20 ms spike every 250 ms has almost no
    fundamental), which is why a loud 5 ms tick read 0.1-0.4 dB there. Measured with this peak window: a clean pad
    0.0 dB, a 5.5 Hz 10% tremolo 0.6 dB, a flat-level 92.9 ms timbre loop 0.2-0.8 dB, and a 5 ms tick at programme
    level 4-6 dB. The windows do not straddle the transient: the local background is the same envelope 60-300 ms
    before and 60-150 ms after the onset, so a section gain step is not mistaken for a tick.
    """
    try:
        from scipy.ndimage import maximum_filter1d
        x = np.abs(np.asarray(sig.mono, dtype=np.float64))
    except Exception:
        return 0.0, 0
    times_in = np.asarray(onset_times, dtype=np.float64)
    if x.size == 0 or times_in.size == 0:
        return 0.0, 0
    sr = float(sig.sr)
    env = maximum_filter1d(x, size=max(3, int(round(win_ms * sr / 1000.0))))
    rises = []
    for s in times_in:
        post = env[int(max(0, (s - 0.02) * sr)):int(min(env.size, (s + 0.03) * sr + 1))]
        before = env[int(max(0, (s - 0.30) * sr)):int(max(0, (s - 0.06) * sr))]
        after = env[int(min(env.size, (s + 0.06) * sr)):int(min(env.size, (s + 0.15) * sr))]
        bg = np.concatenate([before, after])
        if post.size < 3 or bg.size < max(8, int(0.02 * sr)):
            continue
        floor = float(np.median(bg))
        if floor <= 1e-9:
            continue
        rises.append(20.0 * np.log10(float(np.max(post)) / floor))
    if not rises:
        return 0.0, 0
    return float(np.median(rises)), len(rises)


def check_tick(sig, rho_min=0.35, min_events=6, cv_max=0.05, lag_s=(0.1, 1.0), hop=512,
               min_rise_db=3.0):
    """Onset-strength autocorrelation in the 0.1-1 s lag range, corroborated by tempogram, PLP and peak rise."""
    if librosa is None:
        return _result(0.0, rho_min, 'rho', [], 'librosa missing: tick row not measured', skipped=True)
    onset = sig.onset_env
    if onset.size < 32 or float(np.max(onset)) <= 1e-9:
        return _result(0.0, rho_min, 'rho', [], 'no onset activity')
    o = onset - onset.mean()
    ac = librosa.autocorrelate(o, max_size=None)
    ac = ac / (ac[0] + EPS)
    lo = max(1, int(lag_s[0] * sig.sr / hop))
    hi = min(ac.size - 1, int(lag_s[1] * sig.sr / hop))
    if hi <= lo:
        return _result(0.0, rho_min, 'rho', [], 'not enough frames for the lag range')
    seg = ac[lo:hi + 1]
    rho = float(np.max(seg))
    # The best lag is often a multiple of the true period: a train at 250 ms correlates just as well at 500 ms, and
    # scoring the grid at 500 ms then counts half the ticks as off-grid. Take the shortest lag that is within 5% of
    # the best, so the period describes one tick.
    near = np.flatnonzero(seg >= 0.95 * rho)
    period_s = (lo + int(near[0] if near.size else np.argmax(seg))) * hop / float(sig.sr)
    peaks, _ = find_peaks(onset, prominence=max(1e-6, 0.5 * float(np.median(onset[onset > 0])) if np.any(onset > 0) else 1e-6))
    # A pad has many weak flux peaks from its own envelope; a tick train has a few strong ones. Score the strong peaks
    # only, or the coefficient of variation measures the pad, not the tick (measured: 205 onsets, CV 0.26 for a clean
    # 4 Hz train that was clearly visible in the autocorrelation at 244 ms).
    strong = peaks[onset[peaks] >= 0.25 * float(np.max(onset))] if peaks.size else peaks
    ioi = np.diff(strong) * hop / float(sig.sr)
    cv = float(np.std(ioi) / (np.mean(ioi) + EPS)) if ioi.size > 1 else 1.0
    win = min(384, max(32, onset.size // 2))
    try:
        tg = librosa.feature.tempogram(onset_envelope=onset, sr=sig.sr, hop_length=hop, win_length=win)
        tg_ratio = _peak_ratio(tg)
    except Exception:
        tg_ratio = float('nan')
    try:
        pulse = librosa.beat.plp(onset_envelope=onset, sr=sig.sr, hop_length=hop, win_length=win)
        plp_ratio = _peak_ratio(pulse)
    except Exception:
        plp_ratio = float('nan')
    # CV breaks when a few extra strong onsets follow the train (measured: 24 strong peaks, CV 0.48, while the first 8
    # sat exactly on a 244/255 ms grid). Score how many strong peaks land on the autocorrelation period instead.
    st = strong * hop / float(sig.sr)
    matched = _grid_matches(st, period_s, tol_s=0.02) if st.size else 0
    # A tick train is a repeated transient, not only a periodic spectrum. Onset strength (spectral flux) rises whenever
    # the spectrum moves, so a sampled orchestral sustain reads as periodic while it has no transient at all: measured
    # 0.0-0.8 dB of local peak rise on a pad, a tremolo and a flat-level 92.9 ms timbre loop, against 4-6 dB for a
    # 5 ms tick at programme level. A defect has to be an impulse, so require that before calling it one.
    rise_db, rise_n = _peak_rise_db(sig, st)
    periodic = (rho >= rho_min and strong.size >= min_events and matched >= min_events
                and matched >= 0.3 * strong.size and rise_n > 0 and rise_db >= min_rise_db)
    times = [float(st[0])] if st.size else []
    detail = (f'onset autocorrelation {rho:.2f} at a {period_s * 1000:.0f} ms grid (limit {rho_min:g}; '
              f'onset frames are {hop / float(sig.sr) * 1000:.1f} ms apart, so the reported grid can be a multiple of '
              f'the tick spacing), '
              f'{strong.size} strong onset(s) of {peaks.size}, {matched} on the grid, IOI CV {cv:.3f}; '
              f'peak rise {rise_db:.2f} dB at those onsets over {rise_n} onset(s) (min {min_rise_db:g}); '
              f'tempogram peak ratio {tg_ratio:.2f}, PLP peak ratio {plp_ratio:.2f}')
    return _result(rho, rho_min, 'rho', times, detail,
                   periodic=bool(periodic), period_ms=period_s * 1000.0, events=int(strong.size),
                   cv=cv, grid_matched=int(matched), tempogram_ratio=tg_ratio, plp_ratio=plp_ratio,
                   rise_db=round(rise_db, 3), rise_onsets=int(rise_n))


def _grid_matches(times, period_s, tol_s=0.02):
    """How many times land on a grid of `period_s` for the best phase. Robust to a few extra onsets."""
    times = np.asarray(times, dtype=np.float64)
    if times.size == 0 or period_s <= 0:
        return 0
    best = 0
    for phase in times[:min(times.size, 64)]:
        k = np.round((times - phase) / period_s)
        err = np.abs(times - (phase + k * period_s))
        best = max(best, int(np.sum(err <= tol_s)))
    return best


def _peak_ratio(a):
    """A bounded 0..1 prominence of the 99th percentile over the median, not an unbounded ratio."""
    a = np.asarray(a, dtype=np.float64)
    if a.size == 0:
        return float('nan')
    hi = float(np.percentile(a, 99))
    med = float(np.median(a))
    return float((hi - med) / (hi + med + EPS))


def _slow_component(x, sr, cutoff_hz=2.0):
    """(slow component, its sample rate): the part of a channel below `cutoff_hz`, which is what a DC drift is.

    A 1 s block mean is a boxcar decimation, and a boxcar is a poor anti-alias filter: a 73 Hz programme tone (a low
    pedal, a timp) still leaves about A / (pi f) in every block mean, so the row read a loud low note as "DC drift"
    (measured on a master whose 40 Hz high-pass leaves no offset at all). Low-passing the waveform first, steeply,
    means only sub-2 Hz content can reach the block means.
    """
    from scipy.signal import butter, decimate, sosfiltfilt
    if cutoff_hz <= 0.0 or cutoff_hz >= 0.5 * float(sr) or len(x) < 64:
        return np.asarray(x, dtype=np.float64), float(sr)
    y, sr2 = np.asarray(x, dtype=np.float64), float(sr)
    # An 8th-order filter at 2 Hz on a 44.1 kHz signal has a normalised corner of 9e-5 and is numerically fragile, so
    # the signal is decimated first (zero-phase FIR anti-alias at a few hundred Hz, where the corner is still low but
    # the filter is well conditioned), then low-passed at the decimated rate.
    # One decimation only, to a few hundred Hz: a second stage at 8 Hz aliased a 73 Hz note down to about 1 Hz
    # (73 - 9*8), which is exactly the drift it was supposed to exclude.
    q = int(sr2 // 400.0)
    if q >= 2 and len(y) > 4 * q:
        y = decimate(y, q, ftype='fir', zero_phase=True)
        sr2 /= q
    if sr2 <= 4.0 * cutoff_hz:
        return y, sr2
    sos = butter(4, cutoff_hz / (0.5 * sr2), btype='low', output='sos')
    return sosfiltfilt(sos, y), sr2


def check_dc(sig, dc_max=0.001, drift_max=0.001):
    """Per-channel DC mean, and the drift of the sub-2 Hz component between 1 s blocks."""
    channels = sig.audio.shape[1]
    means = [float(np.mean(sig.audio[:, c])) for c in range(channels)]
    drift = 0.0
    for c in range(channels):
        x, sr2 = _slow_component(sig.audio[:, c], sig.sr)
        block = max(1, int(round(sr2)))            # one second at the slow component's own rate
        # The decimating filter starts on a step of its own (measured: 0.24 FS in the first samples, which read as
        # 8e-3 of "drift" on a tone with no offset). One second is dropped at each end; nothing is lost from a
        # multi-second file and a file too short to have an interior is not judged on its edges.
        if len(x) > 4 * block:
            x = x[block:len(x) - block]
        elif len(x) > 16:
            # A delivery shorter than four seconds has no room for a one-second guard at each end, and the filter's
            # own start-up was 8e-3 of "drift" on a clean 2 s control. Drop an eighth at each edge instead; a file
            # left with one block is judged on its mean, which is the row's other half.
            edge = max(1, len(x) // 8)
            x = x[edge:len(x) - edge]
        n = len(x) // block
        if n >= 2:
            bm = x[:n * block].reshape(n, block).mean(axis=1)
            drift = max(drift, float(np.max(bm) - np.min(bm)))
    value = max(max(abs(m) for m in means), drift)
    detail = f'channel mean(s) {", ".join(f"{m:.5f}" for m in means)} FS, 1 s drift {drift:.5f} (limit {dc_max:g})'
    return _result(value, dc_max, 'FS', [], detail, channel_means=means, drift=drift)


def check_clipping(sig, full=0.999):
    """Samples at or above `full`, plus flat-top runs of 3+ samples."""
    a = np.abs(sig.audio)
    clipped = a >= full
    count = int(np.count_nonzero(clipped))
    # One flat-top run = a run of 3+ consecutive clipped samples in one channel: count the samples where the third
    # consecutive clipped sample arrives (a rising edge of "this and the two before it are all clipped").
    flats = 0
    if clipped.shape[0] >= 3:
        three = clipped[2:] & clipped[1:-1] & clipped[:-2]      # this sample and the two before it are all clipped
        starts = three.copy()
        starts[1:] &= ~three[:-1]                               # keep only the first sample of each such stretch
        flats = int(np.count_nonzero(starts))
    detail = f'{count} sample(s) at/above {full:g} FS, {flats} flat-top run(s)'
    return _result(count, 0.0, 'samples', [], detail, flat_runs=flats)


def check_flatness(sig, threshold=0.10, level_floor_db=-50.0, min_ms=50.0, hop=512):
    """Sustained broadband frames: spectral flatness above `threshold` while the frame is audible."""
    if librosa is None:
        return _result(0.0, threshold, 'flatness', [], 'librosa missing: flatness row not measured', skipped=True)
    S = sig.stft
    fl = librosa.feature.spectral_flatness(S=S)[0]
    rms = librosa.feature.rms(S=S)[0]
    level = 20 * np.log10(rms + EPS)
    mask = (fl > threshold) & (level > level_floor_db)
    run_need = max(1, int(round(min_ms / 1000.0 * sig.sr / hop)))
    best, hits, run = 0.0, [], 0
    for i, v in enumerate(mask):
        run = run + 1 if v else 0
        if run >= run_need:
            t = (i - run + 1) * hop / float(sig.sr)
            if run == run_need:                  # one window per sustained run, not one per frame of the run
                hits.append(t)
            best = max(best, float(np.max(fl[i - run + 1:i + 1])))
    detail = (f'max sustained flatness {best:.2f} (limit {threshold:g}) over {len(hits)} window(s) '
              f'>= {min_ms:.0f} ms')
    return _result(best, threshold, 'flatness', hits, detail, windows=len(hits))


def tempo_from_onsets(y, sr, hop=512, lo_bpm=50.0, hi_bpm=220.0):
    """(BPM, peak strength) from the autocorrelation of the onset envelope, or (None, strength).

    A beat tracker reports a *beat* tempo from a dynamic-programming pass and, measured here, it does not do this
    reliably on every signal: librosa 1.0.1's `beat_track` returned 0.0 BPM on a perfect 152 BPM click track, and
    99.4 BPM on a 152 BPM orchestral master whose onset envelope autocorrelates at exactly 152.0 (2:3 of 152 is
    101.3, which is what it locked to). The autocorrelation peak in a musical tempo window is the measured
    periodicity of the onsets, which is what this row asks about; the beat tracker's answer is kept as a cross-check
    in the detail string instead of deciding the row.
    """
    oenv = librosa.onset.onset_strength(y=np.asarray(y, dtype=np.float32), sr=sr, hop_length=hop)
    if oenv.size < 16 or not np.any(oenv > 0):
        return None, 0.0
    # A signal without onsets (a held tone, a bed) autocorrelates smoothly and has a spurious peak at any lag:
    # require the envelope to actually contain attacks before it is allowed to name a tempo.
    med = float(np.median(oenv))
    sd = float(np.std(oenv)) + 1e-12
    prom = (float(np.max(oenv)) - med) / sd
    if prom < 3.0:
        return None, 0.0
    # Count the attacks with the adaptive detector, not with a threshold set against the file's own peak: on a cue
    # that runs from a quiet opening to a loud climax, only the climax attacks clear `median + 25 % of peak`
    # (measured: 37 frames in 127 s on a cue with a quarter-note timpani pulse throughout, so the row declined to
    # judge the tempo of a piece that plainly has one).
    try:
        detected = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, hop_length=hop, units='time')
    except Exception:
        detected = np.array([])
    n_onsets = int(len(detected))
    rate = n_onsets / (len(oenv) / (float(sr) / float(hop)))
    if n_onsets < 8 or rate < 0.4:
        return None, 0.0
    # mean-removed, unit-variance envelope: the raw one carries the programme's loudness contour, which lifts every
    # lag in the window and hides the periodicity (measured: the 152.0 lag peaked at only 1.05x the window median
    # before this; after it, 152.0 stands 5.7 % clear of the next candidate).
    ac = librosa.autocorrelate((oenv - med) / sd, max_size=len(oenv))
    if not np.isfinite(ac).all() or ac[0] <= 0:
        return None, 0.0
    fps = float(sr) / float(hop)
    lags = np.arange(2, len(ac))
    bpms = 60.0 * fps / lags
    sel = (bpms >= lo_bpm) & (bpms <= hi_bpm)
    if not np.any(sel):
        return None, 0.0
    cand = np.asarray(ac[lags[sel]], dtype=np.float64)
    i = int(np.argmax(cand))
    peak = float(cand[i])
    strength = peak / (float(np.std(cand)) + 1e-12)
    lag = float(lags[sel][i])
    # parabolic refinement of the lag peak, so a tempo that is not an integer number of frames is not rounded
    if 0 < i < len(cand) - 1:
        a, b, c = cand[i - 1], cand[i], cand[i + 1]
        den = a - 2.0 * b + c
        if abs(den) > 1e-12:
            lag += 0.5 * (a - c) / den
    bpm = 60.0 * fps / lag
    # The autocorrelation peak can sit on a metrical level below the beat: a part that attacks every two beats
    # makes the envelope periodic at half the tempo (measured: the gate's own 120 BPM control fixture read 60.0, a
    # peak 7x the median). The spacing between consecutive attacks says which level they are on, so a peak whose
    # period is a whole multiple of that spacing is lifted to it -- never above hi_bpm, so a piece with eighth-note
    # material keeps its quarter-note beat instead of being read at double tempo.
    onsets = detected
    if len(onsets) > 3:
        gaps = np.diff(np.asarray(onsets, dtype=np.float64))
        gaps = gaps[gaps > 1e-3]
        if gaps.size >= 3:
            spacing = float(np.median(gaps))
            if spacing > 0:
                ratio = (60.0 / bpm) / spacing
                k = int(round(ratio))
                if k >= 2 and abs(ratio - k) <= 0.2 * k and bpm * k <= hi_bpm:
                    bpm *= k
    return bpm, strength


def check_tempo(sig, bpm_ref, tol_bpm=2.0, tol_pct=2.0, drift_bpm=2.0):
    """Tempo from the onset periodicity against the score/sheet, plus drift over four quarters."""
    if librosa is None or not bpm_ref:
        return _result(0.0, tol_bpm, 'BPM', [], 'librosa missing or no reference tempo', skipped=True)
    try:
        bpm, strength = tempo_from_onsets(sig.mono, sig.sr)
    except Exception as exc:
        return _result(0.0, tol_bpm, 'BPM', [], f'onset tempo estimate failed: {exc}', skipped=True)
    if bpm is None or strength < 1.0:
        return _result(0.0, tol_bpm, 'BPM', [],
                       f'no isochronous pulse in the onsets (peak strength {strength:.1f}): tempo not judged '
                       '(a bed or rubato piece may have none)', skipped=True)
    try:                                        # the beat tracker, reported but not decisive (see tempo_from_onsets)
        est, _ = librosa.beat.beat_track(y=sig.mono, sr=sig.sr, units='time')
        beat_bpm = float(np.asarray(est).reshape(-1)[0])
    except Exception:
        beat_bpm = float('nan')
    quarter = sig.dur / 4.0
    vals = []
    for i in range(4):
        seg = sig.mono[int(i * quarter * sig.sr):int(min(sig.dur, (i + 1) * quarter) * sig.sr)]
        if len(seg) < sig.sr:
            continue
        try:
            v, s = tempo_from_onsets(seg, sig.sr)
        except Exception:
            v = None
        if v is not None and s >= 1.0:
            # A quarter can lock onto a subdivision or a multiple of the beat (measured: quarters of a metronomic
            # 152 BPM cue read 76.0, i.e. half, and the spread was reported as 75.8 BPM of "drift" on a render that
            # does not drift at all). Snap each quarter to the nearest metrical relative of the whole-piece estimate
            # before the spread, so the number means tempo drift and not a metrical-level disagreement.
            for mult in (0.25, 1.0 / 3.0, 0.5, 2.0 / 3.0, 0.75, 1.0, 4.0 / 3.0, 1.5, 2.0, 3.0, 4.0):
                if abs(v * mult - bpm) <= max(2.0, 0.04 * bpm):
                    v = v * mult
                    break
            vals.append(v)
    drift = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
    tol = max(float(tol_bpm), float(bpm_ref) * float(tol_pct) / 100.0)
    # Drift is reported, not decisive: quarter-length estimates are noisy even on a metronomic render.
    fail = abs(bpm - float(bpm_ref)) > tol
    detail = (f'measured {bpm:.1f} BPM vs {float(bpm_ref):.1f} (tolerance {tol:.1f}) from the onset-envelope '
              f'autocorrelation (peak {strength:.1f}x the median); beat tracker said {beat_bpm:.1f}; '
              f'four-quarter drift {drift:.1f} BPM reported, not decisive')
    return _result(abs(bpm - float(bpm_ref)), tol, 'BPM', [], detail,
                   measured_bpm=bpm, beat_tracker_bpm=beat_bpm, drift_bpm=drift, fail=bool(fail))


def section_bounds(score, dur, sheet=None, problems=None):
    """[{name, start_s, end_s, dyn}] from the score plan or the direction sheet, else four equal parts.
    A tempo map that cannot be built raises, unless `problems` (a list) is given to receive the reason."""
    import gate_clock
    _sec = gate_clock.seconds_fn(score, problems)
    bpb = gate_clock.bar_beats(score)
    bar_s = float(_sec(bpb))
    out = []
    plan = (score.get('plan') or {}).get('sections') or []
    if plan:
        for i, s in enumerate(plan):
            if s.get('start_s') is not None:
                a = float(s['start_s'])
                b = float(s.get('end_s', a + bar_s))
            else:
                a = float(_sec(float(s.get('start_bar', 0)) * bpb))
                b = float(_sec(float(s.get('end_bar', s.get('start_bar', 0) + 1)) * bpb))
            out.append(dict(name=s.get('name', f'section {i + 1}'), start_s=a, end_s=min(b, dur),
                            dyn=float(s.get('dyn', s.get('energy', 0.5)))))
    elif sheet and sheet.get('sections'):
        for i, s in enumerate(sheet['sections']):
            a = float(s.get('start_s', 0))
            b = float(s.get('end_s', dur))
            out.append(dict(name=s.get('name', f'section {i + 1}'), start_s=a, end_s=min(b, dur),
                            dyn=float(s.get('energy', 0.5))))
    if not out and dur > 0:
        n = 4
        step = dur / n
        out = [dict(name=f'section {i + 1}', start_s=i * step, end_s=(i + 1) * step, dyn=0.5) for i in range(n)]
    return [s for s in out if s['end_s'] > s['start_s']]


def section_energy(sig, score, sheet=None, fail_rho=0.5, warn_rho=0.7):
    """Spearman rank correlation between measured section level and the promised energy/dynamics."""
    secs = section_bounds(score, sig.dur, sheet)
    if len(secs) < 4:
        return _result(1.0, fail_rho, 'rho', [], 'fewer than 4 sections: not judged', skipped=True, level='INFO')
    db, times = frame_db(sig, 20.0, 5.0)
    rows = []
    for s in secs:
        a, b = s['start_s'], s['end_s']
        pad = 0.1 * (b - a)
        m = (times >= a + pad) & (times <= b - pad)
        level = float(np.mean(db[m])) if np.any(m) else float('nan')
        rows.append(dict(name=s['name'], start_s=a, end_s=b, energy=s['dyn'], level_db=level))
    vals = [r['level_db'] for r in rows]
    energies = [r['energy'] for r in rows]
    if not np.all(np.isfinite(vals)) or len(set(round(e, 6) for e in energies)) < 2:
        return _result(1.0, fail_rho, 'rho', [], 'section levels or promised energies are constant: not judged',
                       skipped=True, table=rows, level='INFO')
    from scipy.stats import spearmanr
    rho = float(spearmanr(energies, vals).correlation)
    level = 'FAIL' if rho < fail_rho else ('WARN' if rho < warn_rho else 'PASS')
    detail = (f'Spearman rho {rho:.2f} between promised energy and measured section level '
              f'(FAIL < {fail_rho:g}, WARN < {warn_rho:g})')
    out = _result(rho, fail_rho, 'rho', [], detail, level=level, table=rows)
    return out
