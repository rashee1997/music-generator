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

from . import breath, consonant, tract, voice
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


def _vowel_name(ev, default='a'):
    """(onset vowel, diphthong target) from a note. A list of *names* is a diphthong; a list of numbers is formants."""
    v = ev.get('vowel', default)
    if isinstance(v, (list, tuple)):
        if v and all(isinstance(x, str) for x in v):
            return v[0], (v[1] if len(v) > 1 else None)
        return None, None
    return str(v), None


def _pharynx(F, scale):
    """Pharynx scaling: shortening raises F1 more than F2 (non-uniform, unlike a uniform tract length)."""
    s = float(scale)
    if abs(s - 1.0) < 1e-9 or len(F) < 2:
        return F
    F = np.array(F, dtype=float, copy=True)
    F[0] *= s
    F[1] *= 1.0 + 0.5 * (s - 1.0)
    return F


def _cover(F, ev, cfg, scale, K):
    """Vowel modification: above the passaggio a vowel is sung closer to its covered neighbour."""
    te = cfg.get('technique') or {}
    c = float(te.get('cover', 0.0))
    if c <= 0.0 or len(F) < 3:
        return F
    pitch = float(ev.get('p', 60.0))
    w = c * float(np.clip((pitch - float(te.get('cover_start_midi', 64.0)))
                          / max(float(te.get('cover_span_semitones', 3.0)), 1e-3), 0.0, 1.0))
    name = _vowel_name(ev)[0]
    tgt = (cfg['tract'].get('cover_map') or {}).get(name) if name else None
    if w <= 0.0 or not tgt or tgt not in cfg['tract']['vowels']:
        return F
    T = _pharynx(np.array(list(cfg['tract']['vowels'][tgt])[:K], dtype=float) * scale,
                 cfg['tract'].get('pharynx_scale', 1.0))
    if len(T) != len(F):
        return F
    return (1.0 - w) * F + w * T


def _formants(ev, cfg, style):
    """Note -> formant targets. Five when the tract offers five (Klatt's cascade uses five); a preset that declares
    three keeps three, because the bank is sliced to the shortest of formants / gains / bandwidths."""
    tr = cfg['tract']
    K = min(len(tr['gains']), len(style.get('bandwidths') or tr['bandwidths']))
    if ev.get('formants'):
        F = list(ev['formants'])
    elif tr.get('formants'):
        F = list(tr['formants'])
    elif style.get('formants'):
        F = list(style['formants'])
    else:
        v = ev.get('vowel', 'a')
        if isinstance(v, (list, tuple)) and v and all(isinstance(x, str) for x in v):
            F = list(tr['vowels'].get(v[0], tr['vowels']['a']))
        elif isinstance(v, (list, tuple)):
            F = list(v)
        else:
            F = list(tr['vowels'].get(v, tr['vowels']['a']))
    m = float(ev.get('formant_scale', 1.0)) * float(tr['formant_scale']) * float(tr.get('length_scale', 1.0))
    F = _pharynx(np.array(F[:K], dtype=float) * m, tr.get('pharynx_scale', 1.0))
    F = tract.ring_cluster(F, float((cfg.get('technique') or {}).get('singer_formant', 0.0)), tr.get('ring'))
    return _cover(F, ev, cfg, m, K)


def _diph_target(ev, cfg, style, onset):
    """The vowel a note glides to (a diphthong), or the onset formants when there is none."""
    name = _vowel_name(ev)[1] or ev.get('vowel_to')
    if not name or name not in cfg['tract']['vowels']:
        return onset
    tr = cfg['tract']
    K = len(onset)
    m = float(ev.get('formant_scale', 1.0)) * float(tr['formant_scale']) * float(tr.get('length_scale', 1.0))
    F = _pharynx(np.array(list(tr['vowels'][name])[:K], dtype=float) * m, tr.get('pharynx_scale', 1.0))
    return tract.ring_cluster(F, float((cfg.get('technique') or {}).get('singer_formant', 0.0)), tr.get('ring'))


def _note_consonants(notes, cn):
    """The onset consonant of each note ('' = none). A note's own key wins; `consonants.auto` fills the rest from
    `onsets` round-robin - deterministic, never random, so the same score always sings the same syllables."""
    if not cn or not cn.get('enabled', True):
        return [''] * len(notes)
    inv = cn.get('inventory') or {}
    onsets = list(cn.get('onsets') or [])
    min_s = float(cn.get('min_note_s', 0.25))
    out, j = [], 0
    for e in notes:
        c = e.get('consonant')
        if isinstance(c, (list, tuple)):
            c = c[-1] if c else ''
        if c:
            out.append(str(c) if str(c) in inv else '')
        elif cn.get('auto') and onsets and float(e.get('dur', 0.0)) >= min_s:
            out.append(str(onsets[j % len(onsets)]))
            j += 1
        else:
            out.append('')
    return out


def _formant_track(n, sr, s, e_, Fn, steady, vsteps, dip_start, dip_n):
    """Formant track with a diphthong glide inside a note. Only used when a note has a diphthong target: the plain
    vowel-change path still goes through step_curve, so a score without diphthongs renders exactly as before."""
    k = len(Fn)
    xs, ys = [0.0], [np.asarray(Fn[0], dtype=float)]
    for i in range(k):
        if not np.allclose(steady[i], Fn[i]):
            t0 = float(max(0, s[i] + dip_start))
            t1 = float(max(t0 + 4, min(s[i] + dip_start + dip_n, s[i] + 0.8 * (e_[i] - s[i]))))
            xs += [t0, t1]
            ys += [np.asarray(Fn[i], dtype=float), np.asarray(steady[i], dtype=float)]
        if i < k - 1:
            c, w, _ = vsteps[i]
            xs += [float(max(0, c - w // 2)), float(max(1, c + w // 2))]
            ys += [np.asarray(steady[i], dtype=float), np.asarray(Fn[i + 1], dtype=float)]
    order = np.argsort(np.asarray(xs), kind='stable')
    X = np.asarray(xs, dtype=float)[order]
    Y = np.stack([np.asarray(y, dtype=float) for y in ys])[order]
    raw = np.stack([np.interp(np.arange(n), X, Y[:, d]) for d in range(Y.shape[1])])
    w = max(8, min(int(0.012 * sr), max(8, n // 8)))
    ker = np.hanning(w + 2)[1:-1]
    ker /= ker.sum()
    pad = w // 2
    return np.stack([np.convolve(np.pad(row, (pad, pad), mode='edge'), ker, mode='valid')[:n] for row in raw])


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


def _tuned_formants(F, f0, cfg):
    """The formants a singer's tract actually has at pitch `f0`: F1 follows f0 when f0 climbs into it (Sundberg's
    formant tuning), F2 follows by `tuning_f2_share`, and F1 stays under F2.

    One implementation for two callers: the per-sample track below and the calibration that sets the timbre's gain.
    Measured on a real phrase, calibrating the untuned F1 (430 Hz) while synthesising the tuned one (766 Hz at
    f0 784 Hz) put a 7 dB pitch-dependent error on `note_rms`, so the level no longer followed velocity.
    """
    F = np.array(F, dtype=float)
    te = cfg.get('technique') or {}
    tune = float(te.get('formant_tuning', 0.0))
    if tune <= 0 or F.size < 2:
        return F
    f0 = np.asarray(f0, dtype=float)
    over = f0 > float(te.get('tuning_threshold', 0.9)) * F[0]
    d = np.where(over, tune * (f0 - F[0]), 0.0)
    F[1] = F[1] + float(te.get('tuning_f2_share', 0.5)) * d
    F[0] = np.minimum(F[0] + d, 0.95 * F[1])
    return F


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
    CN = cfg.get('consonants') or {}
    codes = _note_consonants(notes, CN)
    pad = int(round(max([consonant.length_s(CN, c) for c in codes if c] or [0.0]) * sr))
    s = [pad + int(round((e['t'] - t0) * sr)) for e in notes]
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
    cyc = np.cumsum(rate_t) / sr
    walk = float(V.get('phase_walk', 0.0))
    if walk > 0:                                          # a random-walk phase, not a perfect LFO
        ci = np.floor(cyc).astype(int)
        rw = np.concatenate([[0.0], np.cumsum(rng.standard_normal(int(ci[-1]) + 1))]) * walk
        vib_phase = 2 * np.pi * rng.random() + 2 * np.pi * cyc + 2 * np.pi * rw[ci]
    else:
        vib_phase = 2 * np.pi * rng.random() + 2 * np.pi * cyc
    wave = np.sin(vib_phase)
    asym = amt * float((PH.get('vibrato') or {}).get('asymmetry', 0.0))
    if asym:
        wave = (wave + asym * np.sin(2 * vib_phase + 0.9)) / (1.0 + asym)
    depth_mod = 1 + V['depth_var'] * 0.5 * smooth_noise(rng, n, sr, 0.8)
    if amt > 0:
        depth_mod = depth_mod * (1.0 + amt * float((PH.get('vibrato') or {}).get('swell', 0.0))
                                 * smooth_noise(rng, n, sr, 0.35))
    vib_curve = depth_t * env * depth_mod * wave
    cents += vib_curve
    f0 = 440.0 * 2.0 ** ((cents - 6900.0) / 1200.0)
    # vibrato is not F0-only: subglottal pressure oscillates with the rate, so level and formants move too
    vib_depth = depth_t * env * depth_mod
    vib_max = max(float(np.max(np.abs(vib_depth))), 1e-9)
    vib_norm = vib_curve / vib_max
    am_db = float(V.get('amplitude_db', 0.0))
    vib_am = 10.0 ** (am_db * vib_norm / 20.0) if am_db > 0 else None
    vib_gate = np.abs(vib_depth) >= 0.5 * vib_max if vib_am is not None else None   # where the vibrato is developed
    fmt_pct = float(V.get('formant_pct', 0.0))

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
    K = min([len(f) for f in Fn] + [len(cfg['tract']['gains'])])
    Fn = [f[:K] for f in Fn]
    BW = np.array(style.get('bandwidths') or cfg['tract']['bandwidths'], dtype=float)[:K]
    reg = register or style.get('register')
    comp = float(D['pitch_compensation'])        # singers even out the level between pitches; harmonics near a formant would not
    TE = cfg.get('technique') or {}
    # calibrate on the tract the synthesis will use, not the untuned one: `formant_tuning` moves F1 toward a high f0,
    # so measuring the gain at F1 430 Hz and then singing through F1 766 Hz makes the level depend on pitch
    TFn = [_tuned_formants(F, 440.0 * 2 ** ((b / 100.0 - 69) / 12), cfg) if not hum else np.asarray(F, dtype=float)
           for F, b in zip(Fn, base)]
    c220 = [_calibration(sr, cfg, hum, F, BW, style, reg, nasality) for F in Fn]
    cals = c220 if comp <= 0 else [
        _calibration(sr, cfg, hum, F, BW, style, reg, nasality, hz=440.0 * 2 ** ((b / 100.0 - 69) / 12)) ** comp * c0 ** (1 - comp)
        for F, b, c0 in zip(TFn, base, c220)]
    wv = int(P['vowel_blend_ms'] * 1e-3 * sr)
    FH = PH.get('formants') or {}
    CO = FH.get('coarticulation') or {}
    co_lead = int(float(CO.get('anticipate_ms', 0.0)) * 1e-3 * sr)
    co_settle = int(float(CO.get('settle_ms', 0.0)) * 1e-3 * sr)
    vsteps = []
    for i in range(k - 1):
        if connected[i] and (co_lead or co_settle):
            w = max(4, co_lead + co_settle)               # anticipatory coarticulation: the tract is already
            c = s[i + 1] - ant - co_lead + (co_settle - co_lead) // 2   # moving before the note boundary
        else:
            w, c = (wv, s[i + 1] - ant) if connected[i] else (4, (e_[i] + s[i + 1]) // 2)
        vsteps.append((c, w, Fn[i + 1] - Fn[i]))
    Fn_to = [_diph_target(e, cfg, style, Fn[i]) for i, e in enumerate(notes)]
    if any(not np.allclose(Fn_to[i], Fn[i]) for i in range(k)):
        steady = [Fn_to[i] if not np.allclose(Fn_to[i], Fn[i]) else Fn[i] for i in range(k)]
        F_track = _formant_track(n, sr, s, e_, Fn, steady, vsteps,
                                 int(float(FH.get('diphthong_start_ms', 0.0)) * 1e-3 * sr),
                                 max(4, int(float(FH.get('diphthong_ms', 150.0)) * 1e-3 * sr)))
    else:
        F_track = step_curve(n, Fn[0], vsteps) if not np.allclose(np.diff(np.array(Fn), axis=0), 0) else Fn[0]
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
            nv = list(FH.get('neutral', [500.0, 1500.0, 2500.0]))
            neutral = np.array((nv + list(Fn[i]))[:len(Fn[i])], dtype=float) * scale_i
            ref = Fn[i - 1] if i > 0 else neutral
            ramp = np.exp(-np.arange(m) / (0.35 * m))
            F_track[:, a0:a0 + m] += amt * float(FH['onset_glide']) * (ref - Fn[i])[:, None] * ramp[None, :]
            if dur_s[i] > float(FH.get('drift_ref_s', 1e9)):   # a very long note is not a frozen filter
                ln = min(e_[i] - a0, n - a0)
                drift = np.linspace(0.0, 1.0, ln) ** 2
                F_track[:, a0:a0 + ln] += amt * float(FH.get('long_note_drift', 0.0)) \
                    * (neutral - Fn[i])[:, None] * drift[None, :]
    # ---- formant tuning and formant vibrato (a real singer moves F1 toward f0 and lets the vibrato reach the tract)
    F_track = np.asarray(F_track, dtype=float)
    if F_track.ndim == 1:                              # per-sample track: a frozen vowel is still one formant set
        F_track = np.repeat(F_track[:, None], n, axis=1)   # the technique blocks below move it in time
    tune = float(TE.get('formant_tuning', 0.0))
    if tune > 0 and F_track.size >= 2 and not hum:
        F_track = np.asarray(F_track, dtype=float)
        if np.any(f0 > float(TE.get('tuning_threshold', 0.9)) * F_track[0]):
            if F_track.ndim == 1:                     # a frozen vowel only becomes a track when tuning moves it
                F_track = np.repeat(F_track[:, None], n, axis=1)
            F_track = _tuned_formants(F_track, f0, cfg)
    if fmt_pct > 0 and not hum and np.any(vib_norm) and F_track.size >= 2:
        F_track = F_track.copy()
        F_track[0] *= 1.0 + fmt_pct * vib_norm
        F_track[1] *= 1.0 + 0.5 * fmt_pct * vib_norm
    cal = step_curve(n, cals[0], [(c, w, cals[i + 1] - cals[i]) for i, (c, w, _) in enumerate(vsteps)])
    reg_cfg = voice.register_track(cfg, reg or (cfg['humming']['register'] if hum else None), f0)
    tilt = np.asarray(reg_cfg['tilt_hz'], dtype=float) * 2.0 ** (D['timbre_follow'] * (np.clip(level, 0, 1) - 0.5) * 2.0)
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
    creak = float(TE.get('creak', 0.0))
    creak_env = 0.0
    if creak > 0:                                         # vocal fry: phrase ends and the bottom of the range
        cm = int(float(TE.get('creak_ms', 90.0)) * 1e-3 * sr)
        creak_env = np.zeros(n)
        if cm > 4 and e_[-1] > cm:
            creak_env[e_[-1] - cm:e_[-1]] = _ramp(cm)
        floor_hz = max(float(TE.get('creak_floor_hz', 100.0)), 1.0)
        creak_env = np.maximum(creak_env, np.clip((floor_hz - f0) / (0.25 * floor_hz), 0.0, 1.0))
        creak_env = creak * creak_env
    vstats = {}
    sg = vib_gate                                         # creak is level movement of its own, not vibrato
    if sg is not None and np.ndim(creak_env):
        sg = sg & (np.asarray(creak_env) < 0.1)
    note_id = np.full(n, -1, dtype=int)                   # the vibrato lives inside a note, never across a step
    for _i in range(k):
        note_id[s[_i]:e_[_i]] = _i
    sig, _ = voice.synth(f0, sr, rng, cfg, formants=F_track, bandwidths=BW, hum=hum, nasality=nasality, register=reg,
                         style=style, breathiness=br, tilt_hz=tilt, creak=creak_env, stats=vstats, vib_am=vib_am,
                         stats_gate=sg, stats_notes=note_id)
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
    cons_report = _place_consonants(sig, codes, CN, sr, rng, f0, s, e_, Fn, lv, n, notes)
    tech = _technique_report(sig, sr, f0, F_track, s, e_, k, reg, cfg, vib_am, src_stats=vstats)
    p0 = t0 - pad / sr                                   # the consonant sits before the scored onset
    return dict(signal=sig, t0=p0, t1=p0 + n / sr, f0=f0, gate=gate, level=level, connected=connected, s=s, e=e_,
                voiced_end=p0 + max(e_) / sr, ref_rms=D['ref_rms'] * D['level_scale'],
                note_rms=note_rms, note_v=note_v, dev_cents=dev, n_joins=int(sum(connected)),
                contour=contour, arc_db=arc_db_curve, timing_ms=[float(x) for x in timing_ms],
                accents_db=[float(x) for x in acc_db], formants=F_track,
                technique=tech, consonants=cons_report)


# ---------------------------------------------------------------- technique report and consonant placement

def _longest_note(s, e_):
    i = int(np.argmax([b - a for a, b in zip(s, e_)]))
    return s[i], e_[i]


def _detrend(x, w):
    w = max(3, min(int(w), max(3, len(x) // 2)))
    pad = w // 2
    ker = np.ones(w) / w
    return x - np.convolve(np.pad(x, (pad, pad), mode='edge'), ker, mode='valid')[:len(x)]


def _local_jitter(sig, f0, sr):
    """Local period perturbation measured on the rendered signal (Titze 1994 / Praat: mean |T(i+1)-T(i)| / mean T).
    One glottal closure instant per cycle (the loudest |sample| inside the cycle) gives the period sequence."""
    if len(sig) < 64:
        return None
    cyc = np.cumsum(np.maximum(np.asarray(f0, dtype=float), 20.0)) / sr
    idx = np.floor(cyc).astype(int)
    m = int(idx[-1]) + 1
    if m < 12:
        return None
    bounds = np.append(np.searchsorted(idx, np.arange(m), side='left'), len(idx))
    a = np.abs(sig)
    pos = []
    for j in range(m):
        lo, hi = int(bounds[j]), int(bounds[j + 1])
        if hi - lo < 3:
            continue
        k = lo + int(np.argmax(a[lo:hi]))
        if lo < k < len(a) - 1:                       # sub-sample peak: one sample is ~0.9 % of a period here
            den = a[k - 1] - 2.0 * a[k] + a[k + 1]
            k = k + (0.5 * (a[k - 1] - a[k + 1]) / den if den < 0 else 0.0)
        pos.append(float(k))
    T = np.diff(np.asarray(pos, dtype=float))
    T = T[T > 0]
    if len(T) < 10:
        return None
    return float(np.mean(np.abs(np.diff(T))) / (np.mean(T) + 1e-12) * 100.0)


def _place_consonants(sig, codes, cn, sr, rng, f0, s, e_, Fn, lv, n, notes):
    """Add the consonant segments into the phrase buffer. A consonant is part of the word, not of the breath, so it
    goes into the voice signal (before the voiced onset by its own VOT), never into the breath stem."""
    out = []
    if not codes or not any(codes):
        return out
    gain = 10.0 ** (float(cn.get('gain_db', 0.0)) / 20.0)
    for i, code in enumerate(codes):
        if not code:
            continue
        a, b = s[i], max(s[i] + 8, e_[i])
        f0i = float(np.mean(f0[a:b]))
        lvl = float(lv[min(i, len(lv) - 1)])
        y, meta = consonant.render(code, cn, sr, rng, f0=f0i, vowel=list(Fn[i]))
        if len(y):
            at = a - len(y)
            if at < 0:
                y = y[-at:]
                at = 0
            m = min(len(y), n - at)
            if m > 8:
                sig[at:at + m] += gain * lvl * y[:m]
                meas = consonant.measure(y[:m], sr)
                out.append(dict(code=meta['code'], type=meta.get('type'), band=meta.get('band'),
                                vot_ms=meta.get('vot_ms'), centroid_hz=meas['centroid_hz'], dur_ms=meas['dur_ms']))
        c = notes[i].get('consonant')
        if cn.get('codas') and isinstance(c, (list, tuple)) and len(c) > 1:
            y2, meta2 = consonant.render(c[0], cn, sr, rng, f0=f0i, vowel=list(Fn[i]))
            if len(y2):
                at = max(0, e_[i] - len(y2))
                m = min(len(y2), n - at)
                if m > 8:
                    sig[at:at + m] += gain * lvl * y2[:m]
                    meas = consonant.measure(y2[:m], sr)
                    out.append(dict(code=str(c[0]), type=meta2.get('type'), band=meta2.get('band'), vot_ms=None,
                                    centroid_hz=meas['centroid_hz'], dur_ms=meas['dur_ms']))
    return out


def _technique_report(sig, sr, f0, F_track, s, e_, k, reg, cfg, vib_am, src_stats=None):
    """Objective measurements of what the technique actually produced. The gate reads these, never the config."""
    te = cfg.get('technique') or {}
    out = {}
    F_track = np.asarray(F_track, dtype=float)
    if F_track.ndim == 1:                                  # a frozen vowel: one formant set for the whole phrase
        F_track = np.repeat(F_track[:, None], max(1, len(f0)), axis=1)
    if float(te.get('singer_formant', 0.0)) > 0 and F_track.shape[0] >= 5:
        out['ring_spread_hz'] = float(np.median(F_track[4] - F_track[2]))
        out['ring_amount'] = float(te.get('singer_formant'))
    if float(te.get('formant_tuning', 0.0)) > 0 and F_track.shape[0] >= 2:
        defs, lo_hz = [], float(te.get('tuning_threshold', 0.9))
        for i in range(k):
            a, b = s[i], e_[i]
            m0 = a + (b - a) // 3
            m1 = min(b, m0 + 4096)
            if m1 - m0 < 512:
                continue
            f0i = float(np.mean(f0[m0:m1]))
            f1i = float(np.mean(F_track[0][m0:m1]))
            if f0i <= lo_hz * f1i:
                continue                                  # only a note whose f0 is up at F1 is a tuning case
            spec = np.abs(np.fft.rfft(sig[m0:m1] * np.hanning(m1 - m0)))
            fr = np.fft.rfftfreq(m1 - m0, 1 / sr)

            def _lvl(c, w):
                sel = (fr >= c - w) & (fr <= c + w)
                return 20.0 * np.log10(max(float(spec[sel].max()) if np.any(sel) else 1e-12, 1e-12))

            defs.append(_lvl(f1i, max(25.0, f1i * 0.06)) - _lvl(f0i, max(20.0, f0i * 0.03)))
        out['tuning_deficit_db'] = float(np.mean(defs)) if defs else None
    if F_track.shape[0] >= 2:
        co, found = 0.0, False
        for i in range(k - 1):
            j = s[i + 1]
            start = float(F_track[1][s[i]])
            end = float(F_track[1][j])
            d = abs(end - start)
            if d < 100.0:
                continue                                  # not a vowel change worth calling coarticulation
            found = True
            lo = max(0, j - int(0.3 * sr))
            seg = F_track[1][lo:j]
            moved = np.where(np.abs(seg - start) > 0.05 * d)[0]
            if len(moved):
                co = max(co, (j - (lo + int(moved[0]))) / sr * 1e3)
        out['coart_lead_ms'] = float(co) if found else None
    p = cfg['source'].get('passaggio') or {}
    if p.get('enabled'):
        oq = np.asarray(voice.register_track(cfg, reg, f0)['open_quotient'], dtype=float)
        if oq.ndim and oq.size > 1:
            out['passaggio_step'] = float(np.max(np.abs(np.diff(oq))))
    if float(cfg['source'].get('jitter_period_pct', 0.0)) > 0:
        mis = (src_stats or {}).get('jitter_pct')           # the periods the source really played
        if mis is None:
            a, b = _longest_note(s, e_)
            q0, q1 = a + (b - a) // 4, b - (b - a) // 4
            mis = _local_jitter(sig[q0:q1], f0[q0:q1], sr)
        out['jitter_pct'] = mis
    if vib_am is not None and float(np.ptp(np.asarray(vib_am))) > 1e-3:   # no vibrato: nothing to judge
        out['vib_am_db'] = float((src_stats or {}).get('vib_am_db',
                                                      20.0 * np.log10(max(float(np.max(vib_am)), 1e-9)
                                                                      / max(float(np.min(vib_am)), 1e-9))))
        a, b = _longest_note(s, e_)
        i0, i1 = a + int(0.2 * (b - a)), b - int(0.2 * (b - a))   # skip attack and release: the level swings 60+ dB
        seg = sig[i0:i1]
        w = max(16, int(0.01 * sr))
        if len(seg) > 4 * w:
            p = w // 2
            env = np.sqrt(np.convolve(np.pad(seg ** 2, (p, p), mode='edge'),
                                      np.ones(w) / w, mode='valid')[:len(seg)] + 1e-18)
            e1 = _detrend(np.log(env + 1e-12), int(0.05 * sr))
            f1 = _detrend(f0[i0:i1], int(0.05 * sr))
            if e1.std() > 0 and f1.std() > 0:
                out['vib_am_corr'] = float((src_stats or {}).get('vib_am_corr', np.corrcoef(e1, f1)[0, 1]))
    return out
