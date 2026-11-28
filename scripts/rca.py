#!/usr/bin/env python3
"""rca.py - the root cause of every failing row, from the audio and the score, before anything is edited.

The debug engine (scripts/debug_audio.py) prices a lever against a row: it answers "which knob moves this number". It reads rows the
gate wrote and says nothing about a row that the gate only printed (a stem failure that blocked the mix, a delivery-format row), and it
cannot say that a failure is a fault in the material rather than a rule that does not fit the brief. This script answers the question
before the knob: what in the signal or the score made this row fail, where is the evidence, and is a tolerance change even the right kind
of answer.

    python scripts/rca.py projects/<piece>                    # every FAIL the last render's gate data holds
    python scripts/rca.py projects/<piece> --log run.log      # also every FAIL line of a pipeline log (stem rows that blocked the mix, format rows)
    python scripts/rca.py projects/<piece> --formats          # re-measure each uncertified delivery format (out/_draft_<name>_<format>.wav)
    python scripts/rca.py projects/<piece> --row dropout      # only rows whose name contains this

Each finding says: the row, the cause class (what the measurement shows), the evidence (numbers and times), where the fix lives (the notes, the
presets, the placement), and a verdict:

    fault      the material or the placement is wrong for a reason the measurement names: fix it there. A tolerance change would hide it.
    mismatch   the signal is as written and the row's rule does not fit this piece: a bounded profile relaxation with the measurement
               (`gate_profiles.py relax`) is the legitimate route, and only after this verdict.
    unknown    the measurement did not settle it: say so, and measure more before editing.

The script reads and measures; it never edits a file of the project except its own report (presets/gate/data/rca.json and rca.txt). The numbers
are starting values where they say so. Nothing here is auditioned.
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAULT, MISMATCH, UNKNOWN = 'fault', 'mismatch', 'unknown'
SR = 44100


# ------------------------------------------------------------------------------------------------ pure helpers (tested)
def parse_log(text):
    """[(row, stem or None, detail)] for every FAIL line of a pipeline log. A stem row reads `stem "name": ...` in its detail."""
    out, seen = [], set()
    for line in text.splitlines():
        m = re.match(r'\s*\[FAIL\]\s+([A-Za-z0-9_.]+):?\s+(.*)$', line)
        if not m:
            continue
        row, detail = m.group(1), m.group(2).strip()
        sm = re.search(r'stem "([^"]+)"', detail)
        key = (row, sm.group(1) if sm else None, detail[:60])
        if key not in seen:
            seen.add(key)
            out.append((row, sm.group(1) if sm else None, detail))
    return out


def parse_seconds(detail):
    """The first time a detail names: `at 169.5s`, `at 10.0s`, `192.595s` (None when there is none)."""
    m = re.search(r'(?:at|from|around)\s+(\d+(?:\.\d+)?)\s*s\b', detail or '')
    return float(m.group(1)) if m else None


def parse_bar(detail):
    m = re.search(r'\bbar\s+(\d+)', detail or '')
    return int(m.group(1)) if m else None


def db(x, floor=1e-12):
    return 10.0 * np.log10(float(x) + floor)


def window_db(x, sr, t0, t1):
    """RMS in dB of x[t0:t1] seconds (mono or stereo)."""
    a, b = max(0, int(t0 * sr)), max(0, int(t1 * sr))
    seg = np.asarray(x[a:b], np.float64)
    if seg.size == 0:
        return -200.0
    return db(np.mean(seg ** 2))


def classify_hole(t, dur, top_stem_roles, floor_db, level_db, same_pitch_gap_ms=None):
    """What kind of hole is this? (cause class, one-line reason). The classes are the ones this project's failures fell into.

    t, dur: where the hole starts and the file length (s). top_stem_roles: roles of the stems that carry the level at t, loudest first.
    level_db: the level around the hole; floor_db: the dropout floor the gate used. same_pitch_gap_ms: the gap between a note's end and the
    next onset of the same pitch around t (None when there is none)."""
    if dur - t < 2.0:
        return 'tail', f'{dur - t:.2f} s before the end of the file: the decay of the last sounds crosses the floor and wobbles around it'
    if same_pitch_gap_ms is not None and same_pitch_gap_ms > 0.0:
        return 'retrigger gap', f'a note ends {same_pitch_gap_ms:.0f} ms before the same pitch is struck again: the overlap that bridges the two is missing'
    if top_stem_roles and top_stem_roles[0] == 'environment' and level_db < floor_db + 8.0:
        return 'bed at the floor', f'the bed carries the level there, {level_db - floor_db:.1f} dB above the floor: a wobble of the bed alone opens the hole'
    return 'rest', 'no stem in the score sounds there: a gap between phrases the row reads as a hole'


def band_table(a, b, sr, edges=(500, 1000, 2000, 3000, 4000, 4426, 4955, 5600, 7000, 10000), match=(200, 2000)):
    """Level of `a` against `b` per band, after matching their level in `match`: [(lo, hi, dB)]."""
    from scipy.signal import welch
    fa, pa = welch(np.asarray(a, np.float64).mean(axis=1) if np.ndim(a) == 2 else np.asarray(a, np.float64), sr, nperseg=8192)
    fb, pb = welch(np.asarray(b, np.float64).mean(axis=1) if np.ndim(b) == 2 else np.asarray(b, np.float64), sr, nperseg=8192)

    def band(f, p, lo, hi):
        k = (f >= lo) & (f < hi)
        return db(p[k].sum(), 1e-20)
    g = band(fa, pa, *match) - band(fb, pb, *match)
    return [(lo, hi, band(fa, pa, lo, hi) - band(fb, pb, lo, hi) - g) for lo, hi in zip(edges[:-1], edges[1:])]


def tilt_fit(table):
    """(slope in dB per octave of the straight fit, the largest departure of any band from a smooth quadratic curve of the band table).
    A loudspeaker decode against a binaural master gives a smooth, usually curved tilt; one part or a notch makes a band stand out of any smooth curve."""
    centres = np.array([np.sqrt(lo * hi) for lo, hi, _ in table], np.float64)
    vals = np.array([v for _, _, v in table], np.float64)
    x = np.log2(centres)
    slope = float(np.polyfit(x, vals, 1)[0])
    resid = vals - np.polyval(np.polyfit(x, vals, 2), x)
    return slope, float(np.max(np.abs(resid)))


def classify_fold(table, limit_db):
    """(cause class, reason) of a fold.timbre failure from its band table."""
    slope, dev = tilt_fit(table)
    worst = min(table, key=lambda r: r[2])
    if dev <= 2.0 and slope < -0.4:       # the 8-channel fold of this cue (measured) departs from a smooth curve by 1.0 dB; a notch departs by many
        return 'structural tilt', (f'the fold is {-slope:.1f} dB per octave darker than the stereo master across the spectrum (no band departs from a smooth curve by more than {dev:.1f} dB): '
                                   f'a loudspeaker decode against a binaural master, not one part')
    return 'one band', f'{worst[2]:+.1f} dB at {worst[0]}-{worst[1]} Hz stands out of a smooth curve by {dev:.1f} dB: look at the parts that carry that band'


def bar_table(x, sr, bar_seconds, bars, front, back):
    """Per bar: front-to-back energy in dB, from channel indices. bar_seconds(bar) -> start second."""
    rows = []
    for bar in bars:
        a, b = int(bar_seconds(bar) * sr), int(bar_seconds(bar + 1) * sr)
        e = (np.asarray(x[a:b], np.float64) ** 2).mean(axis=0) if b > a else np.zeros(x.shape[1])
        rows.append((bar, db(e[front].sum()) - db(e[back].sum()), {i: db(e[i]) for i in range(len(e))}))
    return rows


def free_slots(occupied, mid_band_overlaps, step=5, min_sep=25.0):
    """Azimuths (deg) at least `min_sep` from every part in `occupied` that overlaps in the midrange: where a part could be put."""
    out = []
    for az in range(-180, 180, step):
        if all(min(abs(az - o) % 360, 360 - abs(az - o) % 360) >= min_sep for o in occupied):
            out.append(az)
    return out


def tolerance_note(row):
    """The row's parameter ranges, so the report says whether a bounded relaxation exists at all."""
    try:
        import gate_profiles as gp
        r = gp.canonical(row)
        spec = gp.ROWS.get(r)
    except Exception:
        return None
    if spec is None:
        return 'this row is not a gate-profile row: its limit lives in a target preset or in code'
    if spec.get('protected'):
        return 'protected: no profile or score can change it, so the audio is the only fix'
    params = spec.get('params') or {}
    if not params:
        return 'a profile can only skip or apply this row (no parameter): skipping is not a fix'
    def one(k, v):
        return f'{k} {v[0]} (range {v[1]}..{v[2]})' if len(v) >= 3 else f'{k} {v[0]} (choices {list(v)})'
    return 'bounded relaxation exists: ' + ', '.join(one(k, v) for k, v in params.items())


# ------------------------------------------------------------------------------------------------ context
class Ctx:
    def __init__(self, project):
        import audio_debug
        import render_targets
        self.project = os.path.abspath(project)
        self.case = audio_debug.Case.load(self.project)
        self.score = self.case.score or {}
        self.slug = render_targets.project_slug(self.project)
        self.out = os.path.join(self.project, 'out')
        self._master = None
        self._tm = None

    def master(self):
        if self._master is None:
            import soundfile as sf
            path = self.case.master if self.case.master and os.path.isfile(self.case.master) else None
            if path is None:
                import render_targets
                path = render_targets.certified_master(self.project)
                draft = os.path.join(self.out, '_draft_' + self.slug + '.wav')
                if os.path.isfile(draft) and (not os.path.isfile(path) or os.path.getmtime(draft) > os.path.getmtime(path)):
                    path = draft
            x, sr = sf.read(path, dtype='float32', always_2d=True)
            self._master = (x, sr, path)
        return self._master

    def tempo(self):
        if self._tm is None:
            import humanize as hz
            self._tm = hz.tempo_map_for(self.score, seed=self.score.get('seed', 1))
        return self._tm

    def sec(self, beat):
        return float(self.tempo().sec(float(beat)))

    def processed(self):
        return {n: self.case.stem(n) for n in self.case.stem_names()}

    def role(self, name):
        return self.case.role(name)

    def draft_formats(self):
        """{format: path} for every uncertified delivery draft in out/."""
        found = {}
        for p in glob.glob(os.path.join(self.out, '_draft_' + self.slug + '_*.wav')):
            found[os.path.basename(p)[len('_draft_' + self.slug + '_'):-4]] = p
        return found

    def bar_start(self, bar):
        ts = (self.score.get('ts') or [4, 4])
        beats = float(ts[0]) * 4.0 / float(ts[1])
        return self.sec((bar - 1) * beats)


def finding(row, stem, verdict, cause, evidence, where, extra=None):
    f = dict(row=row, stem=stem, verdict=verdict, cause=cause, evidence=list(evidence), where=list(where), tolerance=tolerance_note(row))
    # what the row asks for, from the one table every reader shares (scripts/gate_feedback.py)
    try:
        import gate_feedback
        e = gate_feedback.entry(row)
        f['do_next'] = e.get('do_next')
        f['cost'] = e.get('cost')
    except Exception:
        pass
    f.update(extra or {})
    return f


# ------------------------------------------------------------------------------------------------ analyzers
def a_dropout(ctx, row, stem, detail):
    """A hole in the master or in one stem: where it is, what carries the level there, and which of four causes it is."""
    import gate_checks as gc
    name = stem
    sig_stem = ctx.case.stem(stem) if stem else None
    x, sr, path = ctx.master()
    audio = (sig_stem if sig_stem is not None else x)
    mono = audio.mean(axis=1)

    class Sig:
        pass
    sig = Sig()
    sig.sr, sig.dur, sig.x = SR if sig_stem is not None else sr, len(mono) / float(SR if sig_stem is not None else sr), mono
    try:
        import gate_audio
        sig = gate_audio.load(path) if sig_stem is None else gate_audio.GateAudio(mono.astype(np.float32), SR) if hasattr(gate_audio, 'GateAudio') else sig
    except Exception:
        pass
    try:
        res = gc.check_dropout(sig)
    except Exception as exc:                                    # the checker's own signature may differ: say so rather than guess
        return finding(row, name, UNKNOWN, 'could not re-measure the hole', [f'check_dropout failed: {exc}'], ['re-run the gate'])
    holes = res.get('holes') or []
    if not holes:
        return finding(row, name, UNKNOWN, 'no hole on re-measure', [detail], ['the audio changed since the verdict: re-render'])
    procs = ctx.processed()
    evidence, causes = [], []
    dur = len(mono) / float(sr if sig_stem is None else SR)
    for h in holes[:3]:
        t, ms = float(h['start_s']), float(h['length_ms'])
        lv = sorted(((window_db(a, SR, t - 0.3, t + 0.3), n) for n, a in procs.items() if a is not None), reverse=True)[:4]
        top_roles = [ctx.role(n) or '' for _, n in lv]
        master_db = window_db(x, sr, t - 0.3, t + 0.3)
        floor = float(re.search(r'floor (-?\d+(?:\.\d+)?)', res.get('detail', '') or '').group(1)) if re.search(r'floor (-?\d+(?:\.\d+)?)', res.get('detail', '') or '') else -65.0
        gap = _same_pitch_gap_ms(ctx, name or (lv[0][1] if lv else None), t)
        cause, why = classify_hole(t, dur, top_roles, floor, master_db, gap)
        causes.append(cause)
        evidence.append(f'{ms:.0f} ms at {t:.3f} s ({dur - t:.2f} s before the end); master {master_db:.1f} dB there, floor {floor:.1f} dB; carried by '
                        + ', '.join(f'{n} {l:.0f} dB' for l, n in lv))
        evidence.append(f'  -> {cause}: {why}')
    cause = max(set(causes), key=causes.count)
    where = {'tail': ['the ending: let the last sounds end on a smooth decay above the floor (a longer final note, the bed level), not the master fade'],
             'retrigger gap': ['the score: overlap same-pitch notes by a quarter beat or more (durations), or use another pitch'],
             'bed at the floor': ['the mix preset: level_by_role for the bed, or the bed preset gain'],
             'rest': ['the score: a rest the row reads as a hole; fill it or make it a declared silence']}[cause]
    return finding(row, name, FAULT, cause, evidence, where, dict(holes=holes[:3]))


def _same_pitch_gap_ms(ctx, stem, t):
    tr = ctx.case.track(stem) if stem else None
    if not tr:
        return None
    best = None
    notes = sorted((n for n in tr.get('notes', []) if isinstance(n.get('p'), (int, float))), key=lambda n: n['t'])
    for i, n in enumerate(notes):
        end = ctx.sec(float(n['t']) + float(n.get('d', 0.0)))
        if abs(end - t) > 0.15:
            continue
        for m in notes[i + 1:i + 8]:
            if m['p'] == n['p']:
                gap = (ctx.sec(float(m['t'])) - end) * 1000.0
                if -50.0 <= gap <= 400.0 and (best is None or gap < best):
                    best = gap
                break
    return best


def a_stem_level(ctx, row, stem, detail):
    """stem.dead / stem.edge: per-section level of the stem, and how many of its notes lie under the mastering high-pass."""
    a = ctx.case.stem(stem) if stem else None
    if a is None:
        return finding(row, stem, UNKNOWN, 'no processed stem to measure', [detail], ['re-render'])
    mono = a.mean(axis=1)
    secs = (ctx.score.get('plan') or {}).get('sections') or []
    table = []
    for s in secs:
        table.append((s['name'], window_db(mono, SR, float(s['start_s']), float(s['end_s']))))
    evidence = [detail]
    if table:
        med = float(np.median([v for _, v in table if v > -150]))
        evidence.append('per section (dB, shortfall from the median): ' + ', '.join(f'{n} {v:.0f} ({med - v:+.0f})' for n, v in table))
    tr = ctx.case.track(stem)
    hp = float(((ctx.case.mix or {}).get('mastering') or {}).get('highpass_hz') or 0.0)
    cause, where = 'a quiet section', ['the score: the velocities and the dynamics curve in that section, or the part\'s own level']
    if tr and hp:
        pitches = [float(n['p']) for n in tr.get('notes', []) if isinstance(n.get('p'), (int, float))]
        if pitches:
            hz = 440.0 * 2.0 ** ((np.array(pitches) - 69.0) / 12.0)
            under = float(np.mean(hz < hp))
            evidence.append(f'{100 * under:.0f} % of its notes have a fundamental under the master high-pass ({hp:.0f} Hz)')
            if under > 0.3:
                cause, where = 'notes under the high-pass', ['the score: write the part an octave up, where the master keeps it (a sub-100 Hz fundamental is gone after a 105 Hz high-pass)']
    if 'edge' in row and tr:
        ends = [ctx.sec(float(n['t']) + float(n.get('d', 0))) for n in tr.get('notes', [])]
        if ends:
            evidence.append(f'last scored note ends at {max(ends):.2f} s; the stem is {len(mono) / SR:.2f} s long')
        cause, where = 'the audible tail ends before the note does', ['the score: velocity/level of the last note (the audibility floor is relative to the stem\'s median), or end the note where the sound ends']
    return finding(row, stem, FAULT, cause, evidence, where)


def a_zsep(ctx, row, stem, detail):
    try:
        from audio_debug import zplace
        tab, why = zplace.table(ctx.case)
        if tab is None:
            return finding(row, stem, UNKNOWN, 'no pair table', [why], ['re-render'])
        sol = zplace.solve(tab)
        text = zplace.describe(tab, sol)
    except Exception as exc:
        return finding(row, stem, UNKNOWN, 'could not build the pair table', [str(exc)], [])
    return finding(row, stem, FAULT, 'two parts hold the same midrange at the same place',
                   [detail] + (text if isinstance(text, list) else [str(text)]),
                   ['presets: the parts\' azimuth/elevation (scripts/staging.py in a project); anchors (bass, drums) move in azimuth only'])


def a_fold(ctx, row, stem, detail):
    fmts = ctx.draft_formats()
    if not fmts:
        return finding(row, stem, UNKNOWN, 'no delivery draft in out/', [detail], ['run the pipeline, or rca.py --formats after a render'])
    name, path = sorted(fmts.items())[0]
    import soundfile as sf
    from spatial_engine import downmix
    import render_targets
    a, sr = sf.read(path, dtype='float32', always_2d=True)
    layout = (render_targets.get(name) or {}).get('layout')
    m, msr, _ = ctx.master()
    f = downmix.fold(a, layout)
    n = min(len(f), len(m))
    table = band_table(f[:n], m[:n], sr)
    cause, why = classify_fold(table, 6.0)
    ev = [detail, f'{name}: fold against the stereo master, level matched on 200-2000 Hz:'] + [f'  {lo}-{hi} Hz  {v:+.1f} dB' for lo, hi, v in table] + [why]
    if cause == 'structural tilt':
        return finding(row, stem, MISMATCH, cause, ev, ['a measured, bounded override of the target preset\'s fold limit (presets/outputs/<format>.json, gate.fold_band_max_db) with this table as the reason'])
    procs = ctx.processed()
    lo, hi = min(table, key=lambda r: r[2])[:2]
    from scipy.signal import welch
    share = []
    for nme, arr in procs.items():
        if arr is None:
            continue
        fr, p = welch(arr.mean(axis=1).astype(np.float64), SR, nperseg=4096)
        k = (fr >= lo) & (fr < hi)
        share.append((float(p[k].sum()), nme))
    tot = sum(s for s, _ in share) or 1.0
    ev.append('parts carrying that band: ' + ', '.join(f'{n} {100 * s / tot:.0f}%' for s, n in sorted(share, reverse=True)[:4]))
    return finding(row, stem, FAULT, cause, ev, ['the placement or level of the parts named: re-seat the part that carries the band (rear and height positions fold lower)'])


def a_channels(ctx, row, stem, detail):
    """imm.surround_ratio / imm.height_arc / channel.*: per-channel energy and the parts that put it there."""
    fmts = ctx.draft_formats()
    if not fmts:
        return finding(row, stem, UNKNOWN, 'no delivery draft in out/', [detail], [])
    name, path = sorted(fmts.items())[0]
    import soundfile as sf
    import render_targets
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    order = list((render_targets.get(name) or {}).get('channel_order') or [])
    e = (x.astype(np.float64) ** 2).mean(axis=0)
    ev = [detail, 'channel energy (dB): ' + ', '.join(f'{c} {db(v):.1f}' for c, v in zip(order, e))]
    if 'channel.bars' in row:
        bar = parse_bar(detail)
        if bar:
            front = [i for i, c in enumerate(order) if c in ('FL', 'FR', 'FC')]
            back = [i for i, c in enumerate(order) if c in ('BL', 'BR')]
            rows = bar_table(x, sr, ctx.bar_start, range(max(1, bar - 3), bar + 4), front, back)
            ev.append('front-to-back by bar: ' + ', '.join(f'{b}: {v:+.1f}' for b, v, _ in rows))
            vals = [v for _, v, _ in rows]
            swing = float(np.ptp(vals))
            ev.append(f'the swing across these bars is {swing:.1f} dB')
            hits = [h for h in (ctx.score.get('plan') or {}).get('hits', [])]
            return finding(row, stem, MISMATCH if swing > 5.0 else FAULT, 'a one-bar swing in a piece that breathes by the bar', ev,
                           ['if the swing follows the writing (a hit at the bar before, a dip after it): a bounded channel.bars balance_db with this table as the reason; if not, the part that jumps'])
    parts = ctx.case and zpos(ctx)
    if parts:
        procs = ctx.processed()
        en = {n: float(np.mean(a.astype(np.float64) ** 2)) for n, a in procs.items() if a is not None}
        tot = sum(en.values()) or 1.0
        rear = sorted(((en[n] / tot, n, p['az'], p['el']) for n, p in parts.items() if n in en and abs(p['az']) >= 70), reverse=True)[:5]
        high = sorted(((en[n] / tot * min(1.0, max(0.0, p['el']) / 45.0) ** 2, n, p['az'], p['el']) for n, p in parts.items() if n in en), reverse=True)[:5]
        ev.append('largest energy at the sides and the back: ' + ', '.join(f'{n} {100 * s:.1f}% ({az:.0f} deg)' for s, n, az, el in rear))
        ev.append('largest modelled height share: ' + ', '.join(f'{n} {100 * s:.2f}% ({el:.0f} deg up)' for s, n, az, el in high))
    return finding(row, stem, FAULT, 'where the parts are placed', ev, ['the parts named: azimuth toward the front for the surround ratio; elevation down for the height arc (check z-separation after)'])


def zpos(ctx):
    try:
        from audio_debug import zplace
        tab, _ = zplace.table(ctx.case)
        return (tab or {}).get('parts')
    except Exception:
        return None


def a_roughness(ctx, row, stem, detail):
    """cochlear_roughness: the stems sounding in the window and their strongest partials, and which partials of different parts sit within a quarter of a critical band."""
    t = parse_seconds(detail)
    m = re.search(r'final\s+(\d+(?:\.\d+)?)\s*s', detail or '')
    x, sr, _ = ctx.master()
    dur = len(x) / float(sr)
    t0, t1 = (dur - float(m.group(1)), dur) if m else ((t - 1.0, t + 1.0) if t is not None else (0.0, dur))
    procs = ctx.processed()
    rows = []
    for n, a in procs.items():
        if a is None:
            continue
        lv = window_db(a, SR, t0, t1)
        if lv > -80:
            seg = a[int(t0 * SR):int(t1 * SR)].mean(axis=1).astype(np.float64)
            spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
            fr = np.fft.rfftfreq(len(seg), 1.0 / SR)
            k = (fr > 40) & (fr < 4000)
            idx = np.argsort(spec[k])[-3:][::-1]
            rows.append((lv, n, [round(float(fr[k][i])) for i in idx]))
    rows.sort(reverse=True)
    ev = [detail, f'window {t0:.1f}-{t1:.1f} s; sounding parts: ' + ', '.join(f'{n} {lv:.0f} dB {p}' for lv, n, p in rows[:8])]
    close = []
    for i, (la, na, pa) in enumerate(rows[:8]):
        for lb, nb, pb in rows[i + 1:8]:
            for fa in pa:
                for fb in pb:
                    if fa != fb and abs(fa - fb) < max(15.0, 0.25 * 0.108 * (fa + fb) / 2.0):
                        close.append(f'{na} {fa} Hz vs {nb} {fb} Hz ({abs(fa - fb)} Hz apart)')
    if close:
        ev.append('partials of different parts within about a quarter critical band: ' + '; '.join(close[:6]))
    return finding(row, stem, FAULT, 'partials of sounding parts beat' if close else 'roughness with no single beating pair found', ev,
                   ['the notes or the placement of the parts named: move one off the other\'s partial by a minor third or an octave, or drop one from the window'])


def a_section_energy(ctx, row, stem, detail):
    path = os.path.join(ctx.project, 'presets', 'gate', 'data', 'section_energy.json')
    try:
        t = json.load(open(path, encoding='utf-8')).get('table') or []
    except (OSError, ValueError):
        return finding(row, stem, UNKNOWN, 'no section table', [detail], [])
    order_p = np.argsort(np.argsort([r['energy'] for r in t]))
    order_m = np.argsort(np.argsort([r['level_db'] for r in t]))
    ev = [detail] + [f"{r['name']}: promised {r['energy']}, measured {r['level_db']:.1f} dB, rank {int(a)} vs {int(b)}" for r, a, b in zip(t, order_p, order_m)]
    off = [r['name'] for r, a, b in zip(t, order_p, order_m) if abs(int(a) - int(b)) >= 3]
    return finding(row, stem, FAULT, 'the written level does not follow the declared energy', ev,
                   [f'either the sections named ({", ".join(off)}) are written louder or quieter than declared, or the declared energy is not what the brief means there: fix the one that is wrong'])


def a_ambient(ctx, row, stem, detail):
    a = ctx.case.stem(stem) if stem else None
    procs = ctx.processed()
    if a is None:
        return finding(row, stem, UNKNOWN, 'no processed bed', [detail], [])
    mix = np.sum([p.mean(axis=1)[:min(len(p) for p in procs.values() if p is not None)] for p in procs.values() if p is not None], axis=0)
    body = mix[int(8 * SR):-int(8 * SR)] if len(mix) > 16 * SR else mix
    floor = min(-58.0, db(np.mean(body ** 2)) - 38.0)
    lv = window_db(a.mean(axis=1), SR, 8.0, len(a) / SR - 8.0)
    return finding(row, stem, FAULT, 'the bed sits at the silence floor of the mix',
                   [detail, f'bed level {lv:.1f} dB (median over its body); the gate\'s floor is {floor:.1f} dB (the mix level minus 38 dB, never above -58)'],
                   ['the mix preset: level_by_role.environment, or the bed preset gain (a 3-6 dB lift clears a bed within 3 dB of the floor)'])


def a_generic(ctx, row, stem, detail):
    t = parse_seconds(detail)
    ev = [detail]
    if t is not None:
        procs = ctx.processed()
        lv = sorted(((window_db(a, SR, t - 0.5, t + 0.5), n) for n, a in procs.items() if a is not None), reverse=True)[:5]
        ev.append(f'around {t:.1f} s: ' + ', '.join(f'{n} {l:.0f} dB' for l, n in lv))
    return finding(row, stem, UNKNOWN, 'no analyzer for this row yet', ev, ['measure the row\'s own inputs before editing; add an analyzer to scripts/rca.py when you learn the cause'])


ANALYZERS = [('dropout', a_dropout), ('stem.dead', a_stem_level), ('stem.edge', a_stem_level), ('spatial.z_separation', a_zsep),
             ('fold.timbre', a_fold), ('imm.surround_ratio', a_channels), ('imm.height_arc', a_channels), ('channel.', a_channels),
             ('cochlear_roughness', a_roughness), ('section.energy', a_section_energy), ('ambient_bed', a_ambient)]


def analyse(ctx, failures, only=None):
    out = []
    for row, stem, detail in failures:
        if only and only not in row:
            continue
        fn = next((f for key, f in ANALYZERS if row.startswith(key) or key in row), a_generic)
        try:
            out.append(fn(ctx, row, stem, detail))
        except Exception as exc:                                  # one analyzer must never hide the others
            out.append(finding(row, stem, UNKNOWN, 'the analyzer failed', [detail, f'{type(exc).__name__}: {exc}'], []))
    return out


def collect(ctx, log=None, formats=False):
    """Every failing row: the gate's data, a pipeline log, and (with `formats`) the delivery drafts re-measured by the gate's own format rows."""
    fails, seen = [], set()

    def add(row, stem, detail):
        key = (row, stem)
        if key not in seen:
            seen.add(key)
            fails.append((row, stem, detail))
    for r in ctx.case.failing():
        add(r['row'], r.get('stem'), str(r.get('detail') or ''))
    if log and os.path.isfile(log):
        for row, stem, detail in parse_log(open(log, encoding='utf-8', errors='replace').read()):
            add(row, stem, detail)
    if formats:
        import spatial_gate
        m, msr, mpath = ctx.master()
        for name, path in ctx.draft_formats().items():
            rows = []
            spatial_gate.output_rows(ctx.score, path, rows)
            spatial_gate.fold_rows(ctx.score, mpath, path, name, rows)
            for lvl, n, d in rows:
                if lvl == 'FAIL':
                    add(n, None, f'{name}: {d}')
    return fails


def format_text(findings):
    lines = []
    for f in findings:
        lines.append(f"[{f['verdict'].upper()}] {f['row']}" + (f" on {f['stem']}" if f.get('stem') else '') + f"  -  {f['cause']}")
        lines += ['    ' + e for e in f['evidence']]
        lines += ['    fix here: ' + w for w in f['where']]
        if f.get('tolerance'):
            lines.append('    tolerance: ' + f['tolerance'])
        if f.get('do_next'):
            lines.append(f"    do next ({f.get('cost') or 'render'}): {f['do_next']}")
        lines.append('')
    return '\n'.join(lines) if lines else 'no failing row to analyse'


def main(argv=None):
    ap = argparse.ArgumentParser(description='Root cause of every failing row of the last render.')
    ap.add_argument('project')
    ap.add_argument('--log', default=None, help='a pipeline log: its FAIL lines are analysed too')
    ap.add_argument('--formats', action='store_true', help='re-measure the uncertified delivery drafts with the format rows')
    ap.add_argument('--row', default=None, help='only rows whose name contains this')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    ctx = Ctx(a.project)
    findings = analyse(ctx, collect(ctx, a.log, a.formats), a.row)
    d = os.path.join(ctx.project, 'presets', 'gate', 'data')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'rca.json'), 'w', encoding='utf-8') as fh:
        json.dump(dict(name='rca', findings=findings), fh, indent=1, default=str)      # an object, like every other file under presets/: the pipeline reads that folder
    with open(os.path.join(d, 'rca.txt'), 'w', encoding='utf-8') as fh:
        fh.write(format_text(findings) + '\n')
    print(json.dumps(findings, indent=1, default=str) if a.json else format_text(findings))
    return 1 if any(f['verdict'] == FAULT for f in findings) else 0


if __name__ == '__main__':
    sys.exit(main())
