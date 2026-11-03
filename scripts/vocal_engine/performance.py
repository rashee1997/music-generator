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

"""Phrase renderer: a monophonic line of notes becomes ONE continuous performance.

- One pitch curve per phrase (cents): note targets joined by portamento, with anticipation, overshoot/settle,
  slow intonation drift, micro instability, a lean that follows the phrase's melodic direction, stress on
  accented notes and a terminal fall on the last phrase of the line. Vibrato phase never restarts and is
  shaped per note (short notes get a shallower, earlier vibrato; long notes develop more).
- One source phase per phrase (voice.synth carries cumulative cycles), so notes join without waveform breaks.
- Dynamics (velocity levels, a context-chosen phrase contour, per-note accents, small note-to-note level
  variation, flutter) and articulation (attack, release, legato/non-legato dips, detached gaps) are separate
  curves; neither re-normalises a note. Loudness calibration is one constant per timbre, not per note, and
  the contour is normalised so its mean is unchanged: the stem's level in the mix does not move.
- Timing is humanised inside the phrase: a gentle phrase bend, metric lag when the tempo is known, a touch
  early on short notes, and per-note jitter. Offsets are clamped to a fraction of the gap and the phrase
  start is anchored, so notes never reorder and the phrase still begins where the score says.
- Formants articulate: they start a little toward the previous vowel (toward neutral for the first note) and
  settle, and very long notes drift slightly, so a held note is not a frozen filter.
- Performance context (vocal_engine/context.py) supplies tempo, phrase position, direction, register,
  energy, expression and the track's role. `phrasing.amount` blends every new term in; 0 reproduces the
  previous phrase exactly.
All times in seconds at the API, samples inside. Everything numeric comes from cfg (vocal_engine/data.py).
"""
import json

import numpy as np

from . import breath, voice
from .utils import smooth_noise

_CAL = {}


# ---------------------------------------------------------------- curve helpers
def _ramp(n):
    return 0.5 * (1.0 - np.cos(np.pi * (np.arange(n) + 1) / n))


def step_curve(n, start, steps):
    """start: scalar or (k,). steps: [(center, width, delta)] in samples; delta scalar or (k,).
    Smooth (raised-cosine) transitions of `width` samples centred at `center`. Returns (n,) or (k, n)."""
    start = np.atleast_1d(np.asarray(start, dtype=float))
    out = np.repeat(start[:, None], n, axis=1)
    imp = np.zeros((len(start), n + 1))
    for c, w, d in steps:
        d = np.broadcast_to(np.asarray(d, dtype=float), start.shape)
        w = max(int(w), 2)
        a = int(c) - w // 2
        lo, hi = max(a, 0), min(a + w, n)
        if hi > lo:
            out[:, lo:hi] += d[:, None] * _ramp(w)[None, lo - a:hi - a]
        if a + w < n:
            imp[:, max(a + w, 0)] += d
    out += np.cumsum(imp, axis=1)[:, :n]
    return out[0] if len(start) == 1 else out


def _bump(n, start, length, peak):
    """Zero before `start`, rises to `peak`*1 at ~length/5 and decays to 0 (overshoot/settle shape)."""
    out = np.zeros(n)
    s = max(start, 0)
    e = min(start + int(length), n)
    if e > s:
        x = (np.arange(s, e) - start) / max(length / 5.0, 1.0)
        out[s:e] = peak * x * np.exp(1.0 - x)
    return out


# ---------------------------------------------------------------- note preparation
def split_lines(events):
    """Chords/overlaps -> monophonic lines. Each event goes to the free line with the nearest last pitch."""
    lines = []
    for e in sorted(events, key=lambda e: (e['t'], e['p'])):
        best, bd = None, None
        for ln in lines:
            last = ln[-1]
            if last['t'] + last['dur'] <= e['t'] + 0.05:
                d = abs(last['p'] - e['p'])
                if bd is None or d < bd:
                    best, bd = ln, d
        if best is None:
            best = []
            lines.append(best)
        best.append(e)
    return lines


def _is_hum(ev, default_hum):
    return str(ev.get('vowel', 'm' if default_hum else 'a')) == 'm'


def split_phrases(notes, cfg, default_hum=False):
    """Break a line at long gaps and at hum<->vowel changes."""
    gap = cfg['performance']['phrase_gap_s']
    out, cur = [], []
    for e in notes:
        if cur:
            prev = cur[-1]
            if (e['t'] - (prev['t'] + prev['dur']) > gap or _is_hum(e, default_hum) != _is_hum(prev, default_hum)
                    or e.get('style') != prev.get('style')):
                out.append(cur)
                cur = []
        cur.append(e)
    if cur:
        out.append(cur)
    return out


def _formants(ev, cfg, style):
    k = 3
    if ev.get('formants'):
        F = list(ev['formants'])
    elif cfg['tract'].get('formants'):
        F = list(cfg['tract']['formants'])
    elif style.get('formants'):
        F = list(style['formants'])
    else:
        v = ev.get('vowel', 'a')
        F = list(v) if isinstance(v, (list, tuple)) else list(cfg['tract']['vowels'].get(v, cfg['tract']['vowels']['a']))
    return np.array(F[:k], dtype=float) * float(ev.get('formant_scale', 1.0)) * float(cfg['tract']['formant_scale'])


def _calibration(sr, cfg, hum, F, BW, style, register, nasality, hz=220.0):
    """Gain that makes this timbre's steady tone at `hz` hit dynamics.ref_rms (one constant per timbre and pitch, never
    per performed note: velocity, phrase arc and dynamics are applied on top)."""
    key = json.dumps([sr, hum, round(float(hz), 1), [round(float(f), 1) for f in F], [float(b) for b in BW], sorted(style.items()), register,
                      round(float(nasality), 3), cfg['humming'], cfg['source'], cfg['dynamics']['ref_rms']],
                     sort_keys=True, default=str)
    if key not in _CAL:
        n = int(0.5 * sr)
        y, _ = voice.synth(np.full(n, float(hz)), sr, np.random.default_rng(0), cfg, formants=F, bandwidths=BW, hum=hum,
                           nasality=nasality, register=register, style=style, breathiness=0.0)
        r = float(np.sqrt(np.mean(y[n // 4:] ** 2))) + 1e-12
        _CAL[key] = cfg['dynamics']['ref_rms'] / r
    return _CAL[key]


# ---------------------------------------------------------------- performance helpers
def _smoothed(x, n_smooth):
    """Gentle moving-average so a piecewise-linear contour has no corners."""
    if n_smooth < 3 or len(x) < 3 * n_smooth:
        return x
    k = np.hanning(n_smooth)
    k /= k.sum()
    return np.convolve(np.pad(x, (n_smooth // 2,), mode='edge'), k, mode='valid')[:len(x)]


def bias_for(ph_cfg, ctx):
    """How strongly this phrase's expression and role scale the new performance terms. 1 = no change."""
    out = dict(amount=1.0, depth=1.0, timing=1.0, vibrato=1.0)
    esc = (ph_cfg.get('expression_bias') or {}).get(ctx.get('expression') or '', {}) or {}
    for k in list(out):
        if isinstance(esc.get(k), (int, float)):
            out[k] = float(esc[k])
    inten = float(ctx.get('intensity', 1.0))
    for k in list(out):                                  # intensity 0 = the profile does not move this term
        out[k] = 1.0 + inten * (out[k] - 1.0)
    role = (ph_cfg.get('role_profiles') or {}).get(ctx.get('role') or '', {}) or {}
    for k in list(out):
        if isinstance(role.get(k), (int, float)):
            out[k] *= float(role[k])
    return out


def _pick_contour(rng, ph_cfg, ctx):
    """Weighted choice of a phrase contour, biased by expression, role, melodic direction and phrase position."""
    table = {k: v for k, v in (ph_cfg.get('contours') or {}).items() if float(v.get('weight', 0.0)) > 0}
    if not table:
        return 'arch'
    esc = ((ph_cfg.get('expression_bias') or {}).get(ctx.get('expression') or '', {}) or {}).get('contours') or {}
    names = sorted(table)
    weights = []
    for n in names:
        w = float(table[n]['weight']) * float(esc.get(n, 1.0))
        if ctx.get('is_last') and n in ('fall', 'settle'):
            w *= 1.8
        if ctx.get('is_first') and n in ('rise', 'swell'):
            w *= 1.4
        d = float(ctx.get('direction', 0.0))
        if d > 0 and n == 'rise':
            w *= 1.6
        elif d < 0 and n == 'fall':
            w *= 1.6
        weights.append(max(w, 1e-6))
    u = rng.random() * sum(weights)
    for n, w in zip(names, weights):
        u -= w
        if u <= 0:
            return n
    return names[-1]


def _metric_weight(t, beat_s, beats_per_bar):
    """1 on a bar line, 0.5 on another beat, 0 off the grid; None when the tempo is unknown."""
    if not beat_s or beat_s <= 0:
        return None
    b = float(t) / beat_s
    if abs(b - round(b)) > 0.12:
        return 0.0
    bar = max(int(beats_per_bar), 1)
    return 1.0 if abs(b % bar) < 0.12 or bar - (b % bar) < 0.12 else 0.5


# ---------------------------------------------------------------- the phrase
def render_phrase(notes, sr, rng, cfg, hum=False, style=None, register=None, nasality=0.0, breath_track=None, ctx=None):
    """notes: monophonic, time-sorted event dicts (t, dur, p, v, optional c, gl, vowel, formants, art, attack,
    release, vib_cents, vib_hz, vib_delay, formant_scale). `ctx` is a context.phrase_context dict (or None).
    Returns dict(signal, t0, f0, gate, level, contour, arc_db, timing_ms, formants, accents_db, ...)."""
    style = style or {}
    P, V, A, D = cfg['performance'], cfg['vibrato'], cfg['articulation'], cfg['dynamics']
    PH = cfg.get('phrasing') or {}
    ctx = ctx or {}
    bias = bias_for(PH, ctx)
    amt = float(np.clip(float(PH.get('amount', 0.0)), 0.0, 1.0)) * bias['amount']
    amt = float(np.clip(amt, 0.0, 1.0))
    beat_s, bpb = ctx.get('beat_s'), int(ctx.get('beats_per_bar', 4))
    stab = float(P['pitch_stability'])
    t0 = min(e['t'] for e in notes)
    tail = A['phrase_end_tail_ms'] * 1e-3
    s = [int(round((e['t'] - t0) * sr)) for e in notes]
    e_ = [si + max(int(round(e['dur'] * sr)), 8) for si, e in zip(s, notes)]
    for i in range(len(notes) - 1):                         # overlap -> next note takes over
        e_[i] = min(e_[i], s[i + 1] + int(0.02 * sr)) if e_[i] > s[i + 1] else e_[i]
    k = len(notes)
    grid = list(s)
    dur_s = np.array([(e_[i] - s[i]) / sr for i in range(k)], dtype=float)
    arts = [str(e.get('art') or A['mode']) for e in notes]
    arts = ['detached' if a in ('detached', 'staccato') else 'non_legato' if a in ('non_legato', 'marcato') else 'legato'
            for a in arts]

    connected = []
    for i in range(k - 1):
        gap = s[i + 1] - e_[i]
        connected.append(arts[i + 1] != 'detached' and gap <= P['connect_gap_s'] * sr)

    groups, cur = [], [0]                                   # legato groups: the phrasing unit inside the phrase
    for i in range(k - 1):
        if connected[i]:
            cur.append(i + 1)
        else:
            groups.append(cur)
            cur = [i + 1]
    groups.append(cur)

    # ---- micro-timing: expressive offsets inside the phrase, anchored so the phrase still starts on the beat
    if amt > 0 and PH.get('timing'):
        TM = PH['timing']
        u = np.linspace(0.0, 1.0, k)
        off = float(TM['phrase_bend_ms']) * 1e-3 * np.cos(np.pi * u)
        off = off + float(TM['sigma_ms']) * 1e-3 * rng.standard_normal(k)
        mw = np.array([_metric_weight(e['t'], beat_s, bpb) for e in notes], dtype=float)
        if beat_s:
            off = off + float(TM['metric_lag_ms']) * 1e-3 * (np.nan_to_num(mw, nan=0.0) - 0.5)
        off = off - float(TM['short_note_rush_ms']) * 1e-3 * (dur_s < float(TM['short_note_s']))
        off = off * (amt * bias['timing'])
        off = off - off[0]                                  # never slide the phrase start off the score's beat
        t_abs = np.array([e['t'] for e in notes], dtype=float)
        gaps = np.diff(t_abs) if k > 1 else np.array([0.5])
        lim = np.full(k, gaps.max())
        lim[0] = gaps[0]
        lim[-1] = gaps[-1]
        if k > 2:
            lim[1:-1] = np.minimum(gaps[:-1], gaps[1:])
        off = np.clip(off, -float(TM['clamp_frac']) * np.maximum(lim, 1e-3), float(TM['clamp_frac']) * np.maximum(lim, 1e-3))
        shift = np.round(off * sr).astype(int)
        shift -= shift[0]
        s = list(np.asarray(s) + shift)
        for i in range(1, k):                               # never reorder, never collapse a gap
            s[i] = max(s[i], s[i - 1] + max(8, int(0.006 * sr)))
        s[0] = max(s[0], 0)
        e_ = [s[i] + max(int(round(dur_s[i] * sr)), 8) for i in range(k)]
        for i in range(k - 1):
            if e_[i] > s[i + 1]:
                e_[i] = min(e_[i], s[i + 1] + int(0.02 * sr))
        timing_ms = (np.asarray(s) - np.asarray(grid)) / sr * 1e3
    else:
        timing_ms = np.zeros(k)
    n = max(e_) + int(tail * sr) + 1
    T = n / sr
    pos = np.arange(n) / max(n - 1, 1)

    # ---- pitch (cents)
    base = np.array([e['p'] * 100.0 + float(e.get('c', 0.0)) + P['tuning_cents'] for e in notes])
    ant = int(P['anticipation_ms'] * 1e-3 * sr)
    steps, bumps = [], np.zeros(n)
    for i in range(k - 1):
        d = base[i + 1] - base[i]
        if connected[i]:
            ms = P['portamento_ms'] if arts[i + 1] == 'legato' else P['non_legato_ms']
            w = int(min(ms * 1e-3 * sr, 0.8 * (e_[i] - s[i])))
            c = (s[i + 1] - ant) if e_[i] >= s[i + 1] else ((e_[i] + s[i + 1]) // 2 - ant)
            steps.append((c, w, d))
            osh = np.sign(d) * min(abs(d) * P['overshoot_frac'], P['overshoot_cents'])
            bumps += _bump(n, c + w // 2, int(5 * P['settle_ms'] * 1e-3 * sr), osh)
        else:
            steps.append(((e_[i] + s[i + 1]) // 2, int(0.02 * sr), d))
    cents = step_curve(n, base[0], steps) + bumps
    for i, e in enumerate(notes):                           # legacy per-note glide + articulation scoop
        gl = float(e.get('gl', 0.0))
        scoop = A['onset_scoop_cents'] if (i == 0 or not connected[i - 1]) else 0.0
        if gl or scoop:
            tau = 0.08 if gl else A['onset_scoop_ms'] * 1e-3
            seg = np.arange(e_[i] - s[i]) / sr
            cents[s[i]:e_[i]] += (gl if gl else -abs(scoop)) * np.exp(-seg / tau)
    cents += stab * P['drift_cents'] * smooth_noise(rng, n, sr, max(P['drift_hz'], 0.05))
    cents += stab * P['jitter_cents'] * smooth_noise(rng, n, sr, P['jitter_hz'])
    arch_old = P['arch_cents'] * np.sin(np.pi * pos)
    cents += arch_old
    if P['end_sag_cents']:
        sag = np.clip((np.arange(n) / sr - (T - tail - P['end_sag_s'])) / max(P['end_sag_s'], 1e-3), 0, 1)
        cents -= P['end_sag_cents'] * sag ** 2
    if amt > 0 and PH.get('pitch'):
        PI = PH['pitch']
        lean = float(PI.get('direction_lean_cents', 0.0)) * float(np.clip(ctx.get('direction', 0.0), -1, 1)) \
            * np.clip(2 * pos - 1, -1, 1)
        arch_new = P['arch_cents'] * float(PI.get('arch_scale', 1.0)) * np.sin(np.pi * pos)
        cents += amt * (lean + arch_new - arch_old)
        if ctx.get('is_last') and float(PI.get('terminal_fall_cents', 0.0)):
            fs = max(float(PI.get('terminal_fall_s', 0.4)), 1e-3)
            w_fall = np.clip((T - np.arange(n) / sr) / fs, 0, 1)
            cents -= amt * float(PI['terminal_fall_cents']) * (1 - w_fall) ** 1.5

    cents_nov = cents.copy()                                # intonation without the intended vibrato
    # ---- vibrato (one continuous phase; depth and rate shaped per note, never restarted)
    env = np.zeros(n)
    prev_end = 0.0
    for i, e in enumerate(notes):
        hi = s[i + 1] if i + 1 < k else n
        delay = float(e.get('vib_delay', style.get('vib_delay', V['delay_s'])))
        if amt > 0:
            delay = min(delay, float(PH.get('vibrato', {}).get('delay_frac', 0.35)) * dur_s[i])
        onset = max(V['onset_s'], 1e-3)
        if amt > 0:
            onset = min(onset, max(0.5 * dur_s[i], 0.02))
        t = (np.arange(s[i], hi) - s[i]) / sr
        ramp = np.clip((t - delay) / onset, 0, 1)
        floor = V['carry_floor'] * prev_end if (i > 0 and connected[i - 1]) else 0.0
        seg = floor + (1 - floor) * ramp
        env[s[i]:hi] = seg
        prev_end = float(seg[-1]) if len(seg) else 0.0

    rate_i = np.array([float(e.get('vib_hz', style.get('vib_hz', V['rate_hz']))) for e in notes])
    depth_i = np.array([float(e.get('vib_cents', style.get('vib_cents', V['depth_cents']))) for e in notes])
    if amt > 0:
        VH = PH.get('vibrato') or {}
        ref_len = max(float(VH.get('length_ref_s', 1.0)), 1e-3)
        short, long = float(VH.get('short_scale', 1.0)), float(VH.get('long_scale', 1.0))
        scale = np.clip(short + (long - short) * (dur_s / ref_len), min(short, long) * 0.9, max(short, long) * 1.2)
        depth_i = depth_i * (1.0 + amt * (bias['vibrato'] - 1.0) + amt * (scale - 1.0))
        if beat_s:
            bpm = 60.0 / beat_s
            rate_i = rate_i * (1.0 + float(VH.get('rate_tempo_scale', 0.0))
                               * np.log2(max(bpm, 1.0) / max(float(PH.get('tempo_reference_bpm', 96.0)), 1.0)))

    def _per_note(curve):
        return step_curve(n, curve[0], [(s[i + 1], max(4, int(0.06 * sr)), curve[i + 1] - curve[i]) for i in range(k - 1)])

    depth_t = _per_note(depth_i)
    rate_t = _per_note(rate_i) * (1 + V['rate_var'] * 0.5 * smooth_noise(rng, n, sr, 0.6))
    vib_phase = 2 * np.pi * rng.random() + np.cumsum(2 * np.pi * rate_t / sr)
    wave = np.sin(vib_phase)
    asym = amt * float((PH.get('vibrato') or {}).get('asymmetry', 0.0))
    if asym:
        wave = (wave + asym * np.sin(2 * vib_phase + 0.9)) / (1.0 + asym)
    depth_mod = 1 + V['depth_var'] * 0.5 * smooth_noise(rng, n, sr, 0.8)
    if amt > 0:
        depth_mod = depth_mod * (1.0 + amt * float((PH.get('vibrato') or {}).get('swell', 0.0))
                                 * smooth_noise(rng, n, sr, 0.35))
    cents += depth_t * env * depth_mod * wave
    f0 = 440.0 * 2.0 ** ((cents - 6900.0) / 1200.0)

    # ---- level (dynamics), phrase contour and accents
    vexp = D['velocity_exponent']
    lv = np.array([max(np.clip(float(e.get('v', 80)), 1, 127) / 127.0, D['velocity_floor']) for e in notes]) ** vexp * D['level_scale']
    AC = PH.get('accent') or {}
    if amt > 0 and AC.get('note_var_db'):
        d = rng.standard_normal(k) * float(AC['note_var_db'])
        d = np.clip(d, -2.5 * float(AC['note_var_db']), 2.5 * float(AC['note_var_db']))
        d -= d.mean()                                       # mean level of the phrase is unchanged
        lv = lv * 10 ** (amt * d / 20.0)
    lsteps = []
    for i in range(k - 1):
        w = int(P['portamento_ms'] * 1e-3 * sr) if connected[i] else int(0.02 * sr)
        c = (s[i + 1]) if connected[i] else (e_[i] + s[i + 1]) // 2
        lsteps.append((c, w, lv[i + 1] - lv[i]))
    level = step_curve(n, lv[0], lsteps)
    arc_db = D['phrase_arc_db']
    pk = D['arc_peak']
    f = np.where(pos < pk, pos / pk, (1 - pos) / (1 - pk))
    shape_old = np.sin(0.5 * np.pi * np.clip(f, 0, 1))
    mean_old = 2.0 / np.pi                                # mean of the old arch: the new contours keep it
    contour = 'arch'
    shape = shape_old
    if amt > 0 and PH.get('contours'):
        contour = _pick_contour(rng, PH, ctx)
        pts = np.asarray(PH['contours'][contour]['points'], dtype=float)
        grid = np.linspace(0.0, 1.0, 257)                  # build and smooth the shape small, then interpolate
        shape_small = _smoothed(np.interp(grid, pts[:, 0], pts[:, 1]), 9)
        shape_new = np.interp(pos, grid, shape_small)
        shape_new = shape_new - shape_new.mean() + mean_old
        shape = (1.0 - amt) * shape_old + amt * shape_new
    depth_bias = 1.0 + (float(bias['depth']) - 1.0) * amt
    shape = mean_old + depth_bias * (shape - mean_old)     # depth moves the shape, never the mean level
    arc_db_curve = arc_db * shape
    arc = 10 ** (arc_db_curve / 20.0)
    flutter_hz = min(float(D['flutter_hz']), 4.5)
    flutter = 1 + D['flutter'] * smooth_noise(rng, n, sr, flutter_hz)
    acc_db = np.zeros(n)
    if amt > 0 and AC:
        for gi, grp in enumerate(groups):
            i0 = grp[0]
            mw = _metric_weight(float(notes[i0].get('t', 0.0)), beat_s, bpb)
            w = mw if mw is not None else (1.0 if gi == 0 else float(AC.get('internal_weight', 0.35)))
            g = float(AC.get('gain_db', 0.0)) * w
            if dur_s[i0] >= float(AC.get('long_note_s', 1.0)):
                g += float(AC.get('long_note_db', 0.0))
            m = max(2, min(int(float(AC.get('decay_ms', 240.0)) * 1e-3 * sr), n - s[i0]))
            if m > 2 and g:
                acc_db[s[i0]:s[i0] + m] = g * np.exp(-np.arange(m) / (0.35 * m))
        acc_db = acc_db * amt
        acc_db -= acc_db.mean()                            # accents shape the phrase, they do not raise it
    gate = np.zeros(n)
    onsets = []
    for gi, grp in enumerate(groups):
        a, b = s[grp[0]], e_[grp[-1]]
        onsets.append(a)
        if arts[grp[0]] == 'detached':
            b = max(a + 8, b - int(A['detach_ms'] * 1e-3 * sr))
        att = int(max(2, min(float(notes[grp[0]].get('attack', A['attack_ms'] * 1e-3)) * sr, 0.45 * (b - a))))
        rel = int(max(2, min(float(notes[grp[-1]].get('release', A['release_ms'] * 1e-3)) * sr, 0.45 * (b - a))))
        last = gi == len(groups) - 1
        b_end = b + (int(tail * sr) if last else 0)
        seg = np.ones(b_end - a)
        seg[:att] = _ramp(att)
        seg[-rel:] = np.minimum(seg[-rel:], _ramp(rel)[::-1])
        gate[a:b_end] = seg[:n - a]
        for j, idx in enumerate(grp[1:], 1):               # dips on connected joins
            nl = arts[idx] == 'non_legato'
            depth_d = A['non_legato_dip'] if nl else A['legato_dip']
            wd = int((A['non_legato_dip_ms'] if nl else A['legato_dip_ms']) * 1e-3 * sr)
            c = s[idx] - ant
            a0 = c - wd // 2
            lo, hi = max(a0, 0), min(a0 + wd, n)
            if hi > lo:
                gate[lo:hi] *= 1 - depth_d * np.hanning(wd + 2)[1 + lo - a0:1 + hi - a0]

    # ---- timbre tracks
    Fn = [_formants(e, cfg, style) for e in notes]
    BW = np.array(style.get('bandwidths') or cfg['tract']['bandwidths'][:3], dtype=float)
    reg = register or style.get('register')
    comp = float(D['pitch_compensation'])        # singers even out the level between pitches; harmonics near a formant would not
    c220 = [_calibration(sr, cfg, hum, F, BW, style, reg, nasality) for F in Fn]
    cals = c220 if comp <= 0 else [
        _calibration(sr, cfg, hum, F, BW, style, reg, nasality, hz=440.0 * 2 ** ((b / 100.0 - 69) / 12)) ** comp * c0 ** (1 - comp)
        for F, b, c0 in zip(Fn, base, c220)]
    wv = int(P['vowel_blend_ms'] * 1e-3 * sr)
    vsteps = [((s[i + 1] - ant) if connected[i] else (e_[i] + s[i + 1]) // 2, wv if connected[i] else 4, Fn[i + 1] - Fn[i])
              for i in range(k - 1)]
    F_track = step_curve(n, Fn[0], vsteps) if not np.allclose(np.diff(np.array(Fn), axis=0), 0) else Fn[0]
    FH = PH.get('formants') or {}
    if amt > 0 and float(FH.get('onset_glide', 0.0)) > 0:
        F_track = np.asarray(F_track, dtype=float)
        if F_track.ndim == 1:                              # a frozen vowel still articulates its onset
            F_track = np.repeat(F_track[:, None], n, axis=1)
        settle = max(int(float(FH.get('settle_ms', 130.0)) * 1e-3 * sr), 8)
        for i in range(k):
            a0 = s[i]
            m = min(settle, n - a0)
            if m <= 4:
                continue
            scale_i = float(notes[i].get('formant_scale', 1.0)) * float(cfg['tract']['formant_scale'])
            neutral = np.array(FH.get('neutral', [500.0, 1500.0, 2500.0]), dtype=float) * scale_i
            ref = Fn[i - 1] if i > 0 else neutral
            ramp = np.exp(-np.arange(m) / (0.35 * m))
            F_track[:, a0:a0 + m] += amt * float(FH['onset_glide']) * (ref - Fn[i])[:, None] * ramp[None, :]
            if dur_s[i] > float(FH.get('drift_ref_s', 1e9)):   # a very long note is not a frozen filter
                ln = min(e_[i] - a0, n - a0)
                drift = np.linspace(0.0, 1.0, ln) ** 2
                F_track[:, a0:a0 + ln] += amt * float(FH.get('long_note_drift', 0.0)) \
                    * (neutral - Fn[i])[:, None] * drift[None, :]
    cal = step_curve(n, cals[0], [(c, w, cals[i + 1] - cals[i]) for i, (c, w, _) in enumerate(vsteps)])
    reg_cfg = voice.resolve_register(cfg, reg or (cfg['humming']['register'] if hum else None))
    tilt = reg_cfg['tilt_hz'] * 2.0 ** (D['timbre_follow'] * (np.clip(level, 0, 1) - 0.5) * 2.0)
    B = cfg['breathing']
    if breath_track is not None:
        br = breath_track
    else:
        base_br = float(notes[0].get('breath', style.get('breath', cfg['source']['breathiness'])))
        weights = None
        if amt > 0 and acc_db.any() and onsets:
            peak = max(float(np.abs(acc_db).max()), 1e-9)
            weights = [1.0 + 0.6 * float(acc_db[o]) / peak for o in onsets]
        br = breath.aspiration_track(n, sr, base_br, B, onsets, weights=weights)
    # stress is an intended pitch accent: it goes in after the intonation snapshot, like the vibrato
    acc_norm = np.zeros(n)
    if amt > 0 and acc_db.any():
        acc_norm = np.clip(acc_db - acc_db.min(), 0, None)
        acc_norm /= (acc_norm.max() + 1e-9)
        cents = cents + amt * float((PH.get('pitch') or {}).get('stress_cents', 0.0)) * acc_norm
        f0 = 440.0 * 2.0 ** ((cents - 6900.0) / 1200.0)
    sig, _ = voice.synth(f0, sr, rng, cfg, formants=F_track, bandwidths=BW, hum=hum, nasality=nasality, register=reg,
                         style=style, breathiness=br, tilt_hz=tilt)
    press = breath.pressure_curve(n, sr, B)
    pre_contour = sig * cal * level * flutter * (10 ** (acc_db / 20.0)) * gate
    note_rms, note_v, dev = [], [], []
    for i, e in enumerate(notes):                          # measurements the quality gate reads
        a, b = s[i] + int(0.4 * (e_[i] - s[i])), s[i] + int(0.9 * (e_[i] - s[i]))
        if b > a + 64:
            meas = pre_contour[a:b]
            denom = (arc[a:b] * press[a:b] + 1e-18)
            meas_corr = meas / denom
            note_rms.append(float(np.sqrt(np.mean(meas_corr ** 2))))
            note_v.append(float(e.get('v', 80)))
            dev.append(float(np.mean(cents_nov[a:b]) - base[i]))
    sig = sig * cal * level * arc * flutter * (10 ** (acc_db / 20.0)) * gate * press
    return dict(signal=sig, t0=t0, t1=t0 + n / sr, f0=f0, gate=gate, level=level, connected=connected, s=s, e=e_,
                voiced_end=t0 + max(e_) / sr, ref_rms=D['ref_rms'] * D['level_scale'],
                note_rms=note_rms, note_v=note_v, dev_cents=dev, n_joins=int(sum(connected)),
                contour=contour, arc_db=arc_db_curve, timing_ms=[float(x) for x in timing_ms],
                accents_db=[float(x) for x in acc_db], formants=F_track)
