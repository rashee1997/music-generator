# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""The per-track pipeline: one written line in, played events out.

Stage order is part of the result (each stage draws from one seeded generator in this order), so it is
documented here and must not be reshuffled without a parity measurement:

    resolve -> swing -> phrases -> microtiming -> strum -> dynamics -> drums/pocket -> KTH rules
    -> tonal charge -> phrase dynamics -> expectation -> velocity lead -> onsets -> durations
    -> intonation -> events -> legato
"""
import sys

import numpy as np

import expectation
import roles as rolelib

from . import pocket as pocketlib
from .articulation import auto_pedal, finalize_durations
from .config import DRUM_PUSH, FIG, JUST, ROLE, VEL_LEAD_WORDS, resolve
from .coupling import curve_at
from .drums import _drum_run
from .dynamics import shape_velocity
from .form import (_circle_distance, _limb_of, _mood_profile, _phrase_ids, _vel127, key_tonic)
from .microtiming import timing_terms
from .noise import _smooth_noise
from .swing import apply_swing


def humanize_track(notes, tm, cfg='natural', role=None, seed=0, ts=(4, 4), swing=0.5, swing_unit=0.5,
                   legato_overlap_ms=35, strum_dir='alt', detune_cents=0.0, instrument=None,
                   drift=None, articulation=None, bpm=None, mood=None, key=None, chord_roots=None,
                   tempo_swing=None, part=None):
    """Humanize one track. Returns events in seconds sorted by time. cfg = preset name or dict.

    drift: (beats, values) from shared_drift(). When None the tempo map's own `shared_drift` is used, so every track of a
    piece that came from tempo_map_for() drifts together.
    articulation: {overlap_ms, gate, release_ms} from the instrument preset; overrides the role's fixed legato numbers.
    bpm: the tempo, for the drum push's tempo scaling (falls back to the tempo map).
    mood: a GERM expression profile (MOODS) layered on the groove preset; falls back to the tempo map's score mood.
    key / chord_roots: the tonic and the sounding roots, for tonal charge; fall back to the tempo map's.
    tempo_swing: alias for `swing` that also accepts 'auto'.
    part: the track's name. A named part reads its stable ensemble asynchrony from the tempo map
    (`tempo_map_for` builds one field for the piece); an unnamed line plays with no ensemble offset.
    detune_cents: accepted for call compatibility; track detune is applied by the renderer when it places the
    notes on channels, not here.
    """
    c = resolve(cfg)
    rng = np.random.default_rng(seed)
    breathed = set()               # beats of the notes that let go before a bar line: legato must not close that gap
    if not role:                    # a role-less track still plays as a chord part, but it is said, not assumed
        print('[WARN] humanize_track: no role given, humanized as a chord part. Set the track role (scripts/roles.py).',
              file=sys.stderr)
    base_role = rolelib.canonical(role) if role else 'chord'
    rd = ROLE.get(base_role, ROLE['chord'])
    if isinstance(articulation, dict):             # an instrument's own articulation, not the role's default
        rd = dict(rd, gate=float(articulation.get('gate', rd['gate'])))
        legato_overlap_ms = float(articulation.get('overlap_ms', legato_overlap_ms))
    if bpm is None:
        try:
            bpm = float(np.atleast_1d(getattr(tm, 'base_bpm', 96.0)).ravel()[0])
        except Exception:
            bpm = 96.0
    if mood is None:
        mood = getattr(tm, 'mood', None)
    if mood:
        c['mood'] = mood
    _mood_profile(c)                               # level, gate, accent, duration contrast and strum, scaled
    if drift is None:
        drift = getattr(tm, 'shared_drift', None)
    if tempo_swing is not None:
        swing = tempo_swing
    # the swing ratio belongs to the tempo and to the role: a soloist swings less than the ride cymbal
    ns = apply_swing([dict(n) for n in notes], swing, swing_unit, bpm=bpm, role=base_role,
                     downbeat_ms=float(c.get('swing_downbeat_ms', 0.0) or 0.0))
    ns.sort(key=lambda n: (n['t'], n['p']))
    if not ns:
        return []
    is_drum = base_role == 'drum'

    # ---- phrase structure and pitch contour -------------------------------------------------
    pid = _phrase_ids(ns)
    phrases = {}
    for i, k in enumerate(pid):
        phrases.setdefault(k, []).append(i)

    # ---- timing noise: two-scale 1/f drift + per-limb anti-correlated motor error -----------
    n = len(ns)
    t_beats = np.array([nt['t'] for nt in ns], dtype=float)
    d_beats = np.array([nt['d'] for nt in ns], dtype=float)
    p = np.array([nt['p'] for nt in ns], dtype=float)
    start_boost = np.zeros(n)
    gaps = np.diff(np.sort(t_beats)) if n > 1 else np.array([])
    gap = float(np.median(gaps)) if len(gaps) else 1.0
    step_beats = max(1e-6, gap)
    beta = float(c.get('fractal_beta', 0.85))
    terms = timing_terms(ns, c, rng, is_drum, drift, beta, step_beats, n, bpm)
    frac, anti, drift_term = terms['frac'], terms['anti'], terms['drift_term']

    # group simultaneous onsets (chords) for strum spreading
    groups = {}
    for i, nt in enumerate(ns):
        groups.setdefault(round(nt['t'] * 96), []).append(i)
    strum_off = np.zeros(n)
    flip = 0
    guitar = 'guitar' in str(instrument or '').lower()
    for key_, idx in groups.items():
        if len(idx) > 1 and base_role in ('chord', 'pad', 'arp', 'counter', 'texture') and c['strum_ms'] > 0:
            idx_sorted = sorted(idx, key=lambda j: ns[j]['p'])
            span_in = max(ns[j]['t'] for j in idx) - min(ns[j]['t'] for j in idx)
            if guitar and span_in < 0.005:             # beats: downstroke; off-beats: upstroke
                order = idx_sorted[::-1] if abs(ns[idx[0]]['t'] % 1) > 1e-6 else idx_sorted
            else:
                if strum_dir == 'alt':
                    flip ^= 1
                order = idx_sorted if (strum_dir == 'up' or (strum_dir == 'alt' and flip)) else idx_sorted[::-1]
            span = c['strum_ms'] / 1000.0 * (0.6 + 0.8 * rng.random())
            for rank, j in enumerate(order):
                strum_off[j] = span * rank / max(len(order) - 1, 1)

    # simultaneous onsets (0.04 beat) - one chord, one cluster
    clusters = []
    for i in range(n):
        if clusters and ns[i]['t'] - ns[clusters[-1][0]]['t'] <= 0.04:
            clusters[-1].append(i)
        else:
            clusters.append([i])

    # a melody leads the accompaniment only when something else sounds with it (render_natural sets note 'acc')
    accomp = np.array([float(nt.get('acc', 1.0)) for nt in ns])
    lead = rd['off'] * c['lead_ms'] / 1000.0 * accomp

    # ---- velocities ---------------------------------------------------------------------------
    v_in = np.array([_vel127(nt.get('v', 0.7)) for nt in ns], dtype=float)
    v, acc = shape_velocity(ns, p, v_in, rd, c, base_role, is_drum, phrases, clusters, ts, rng, frac, n,
                            FIG, step_beats=step_beats)

    # ---- pocket: a pushed or laid-back groove is timing AND dynamics -------------------------
    pk = pocketlib.get(str(c['pocket'])) if c.get('pocket') else None
    pocket_ms, pocket_dv = pocketlib.offsets(pk, p, _limb_of) if pk else (np.zeros(n), np.zeros(n))
    if pk and np.any(pocket_dv):
        v += pocket_dv

    # ---- KTH local rules, durations and onsets (Friberg, Bresin & Sundberg 2006) --------------
    ms2b = float(bpm) / 60000.0                        # beats per millisecond
    if not is_drum:
        # Duration Contrast: short notes a little shorter, long ones a little longer, so the rhythm reads
        dc = float(c.get('duration_contrast', 0.0))
        if dc > 0:
            for idx in phrases.values():
                ii = np.asarray(idx, int)
                med = float(np.median(d_beats[ii]))
                if med <= 1e-9:
                    continue
                r = d_beats[ii] / med
                sh, lo = r < 0.75, r > 1.5
                if sh.any():
                    d_beats[ii[sh]] *= (1.0 - 0.5 * dc)
                if lo.any():
                    d_beats[ii[lo]] *= (1.0 + 0.5 * dc)
        # Double Duration: a written 2:1 pair is played softer than 2:1 - lengthen the short, shorten the long
        dd = float(c.get('double_duration', 0.0))
        if dd > 0:
            for i in range(1, n):
                if ns[i]['t'] - ns[i - 1]['t'] < 1e-9:          # simultaneous: a chord, not a pair
                    continue
                a, b = float(d_beats[i - 1]), float(d_beats[i])
                if a <= 1e-9 or b <= 1e-9:
                    continue
                ratio = a / b
                if 1.8 <= ratio <= 2.2:
                    d_beats[i - 1], d_beats[i] = a * (1.0 - dd), b * (1.0 + dd)
                elif 1.8 <= 1.0 / ratio <= 2.2:
                    d_beats[i - 1], d_beats[i] = a * (1.0 + dd), b * (1.0 - dd)
        for i in range(1, n):
            if base_role in FIG + ('counter',) and abs(ns[i]['p'] - ns[i - 1]['p']) >= 5:
                start_boost[i] += 0.008                # agogic delay on the arrival of a leap
                v[i] += 4.0
                d_beats[i - 1] *= 0.92                 # shorten the note before the leap to articulate it
        for i, nt in enumerate(ns):
            if 'c' in nt or 'gl' in nt:                # microtones / glides / chromatic tension lean in
                v[i] += 3.0
                d_beats[i] *= 1.04
        # Faster Uphill: an ascending line leans forward, a few ms per step
        fu = float(c.get('faster_uphill_ms', 0.0))
        if fu > 0 and base_role in FIG + ('counter',):
            for i in range(1, n):
                rise = float(p[i] - p[i - 1])
                if rise > 0:
                    start_boost[i] -= min(fu, 0.35 * rise) / 1000.0
        # Anticipation: a note that sits just before a strong beat (the next bar line or the middle of the bar) and is not on a beat
        # itself leans into it, a few ms early; and the last note of a bar lets go before the bar line so the bar breathes. Both are
        # opt-in per track (`anticipate_ms`, `bar_breath_ms`) and draw from the generator only when asked, so a track that names
        # neither plays exactly as before. Ensemble studies find push and pull of the beat in every performance (Danielsen et al.).
        an = float(c.get('anticipate_ms', 0.0) or 0.0)
        bb = float(c.get('bar_breath_ms', 0.0) or 0.0)
        if (an > 0 or bb > 0) and base_role in FIG + ('counter', 'arp', 'chord', 'ostinato'):
            bar = float(ts[0]) * 4.0 / float(ts[1])
            half = bar / 2.0 if ts[0] % 2 == 0 else None
            for i in range(n):
                pos = t_beats[i] % bar
                to_bar = bar - pos
                to_half = (half - (pos % half)) if half else None
                near = min(x for x in (to_bar, to_half) if x is not None)
                frac_pos = t_beats[i] - np.floor(t_beats[i] + 1e-9)
                if an > 0 and frac_pos > 1e-6 and 0 < near <= 0.76:
                    start_boost[i] -= an / 1000.0 * (0.6 + 0.8 * rng.random())
                end_off = (t_beats[i] + d_beats[i]) % bar
                if bb > 0 and (end_off < 0.06 or bar - end_off < 0.06):
                    d_beats[i] = max(0.5 * d_beats[i], d_beats[i] - bb * ms2b)
                    breathed.add(float(t_beats[i]))
                    for j in range(i + 1, n):
                        if t_beats[j] >= t_beats[i] + d_beats[i] - 1e-6 and t_beats[j] % bar < 0.06:
                            start_boost[j] += 0.35 * bb / 1000.0
                            break
        # Punctuation: a micro-phrase comma - a fragment that departs at least a whole tone and then turns back -
        # is lengthened on its last note and the next gesture waits for it
        pu = float(c.get('punctuation_ms', 0.0))
        if pu > 0 and base_role in FIG + ('counter',) and n >= 3:
            for i in range(2, n):
                a = float(p[i - 1] - p[i - 2])
                b = float(p[i] - p[i - 1])
                if abs(a) < 2.0 or abs(b) < 2.0 or np.sign(a) == np.sign(b):
                    continue
                if ns[i]['t'] - ns[i - 1]['t'] > 2.0:  # a rest already separates them
                    continue
                d_beats[i - 1] += 0.6 * pu * ms2b
                start_boost[i] += pu * ms2b
        # Repetition Articulation: the same pitch twice in a row needs air before the re-attack
        rg = float(c.get('repetition_gap_ms', 0.0))
        if rg > 0:
            gap_b = rg * ms2b
            for i in range(1, n):
                if ns[i]['p'] != ns[i - 1]['p'] or ns[i]['t'] - ns[i - 1]['t'] < 1e-9:
                    continue
                d_beats[i - 1] = max(0.3 * d_beats[i - 1], d_beats[i - 1] - gap_b)
    else:
        by_p = {}
        for i, nt in enumerate(ns):
            by_p.setdefault(nt['p'], []).append(i)
        for idx in by_p.values():
            run = [idx[0]]
            for a, b in zip(idx, idx[1:]):
                if ns[b]['t'] - ns[a]['t'] <= 0.55 + 1e-9:
                    run.append(b)
                else:
                    _drum_run(run, v, ns, start_boost, rng)
                    run = [b]
            _drum_run(run, v, ns, start_boost, rng)
        for i in range(1, n):                          # layered hits flam instead of phase-locking
            if abs(ns[i]['t'] - ns[i - 1]['t']) < 0.003 and ns[i]['p'] != ns[i - 1]['p']:
                start_boost[i] += 0.003 if i % 2 else -0.003

    # ---- tonal tension: KTH melodic charge and harmonic charge --------------------------------
    tonic = key_tonic(key) if key is not None else getattr(tm, 'key', None)
    roots = chord_roots if chord_roots is not None else getattr(tm, 'chord_roots', None)
    mc_v, mc_d = float(c.get('melodic_charge_vel', 0.0)), float(c.get('melodic_charge_dur', 0.0))
    hc_v, hc_d = float(c.get('harmonic_charge_vel', 0.0)), float(c.get('harmonic_charge_dur', 0.0))
    if tonic is not None:
        if (mc_v or mc_d) and roots is not None and len(roots[0]):
            rb, rp = np.asarray(roots[0], float), np.asarray(roots[1], int)
            if base_role in FIG + ('counter',):
                at = np.clip(np.searchsorted(rb, t_beats + 1e-9, side='right') - 1, 0, len(rb) - 1)
                ch = np.array([_circle_distance(int(p[i]) % 12, int(rp[at[i]])) for i in range(n)])
                v += mc_v * ch
                d_beats *= 1.0 + mc_d * ch
        if (hc_v or hc_d) and base_role in ('chord', 'pad', 'arp', 'texture'):
            for cl in clusters:
                root = int(min(ns[j]['p'] for j in cl)) % 12
                ch = _circle_distance(root, tonic)
                if ch <= 0.0:
                    continue
                v[cl] += hc_v * ch
                d_beats[cl] *= 1.0 + hc_d * ch

    # ---- phrase tempo -> phrase dynamics (Todd 1992) -----------------------------------------
    ptv = float(c.get('phrase_tempo_vel', 0.0))
    if ptv > 0 and base_role in FIG + ('counter',) and hasattr(tm, 'local_tempo'):
        lt = np.asarray(tm.local_tempo(t_beats), float)
        m = float(lt.mean()) if len(lt) else 0.0
        if m > 1e-9:
            v += ptv * np.clip((lt / m - 1.0) / 0.05, -2.0, 2.0)     # a swell where the tempo leans forward

    # ---- expectation -> expression: hesitation before a surprise, a breath before an uncertain note ---------------
    ic_ms, ic_v, h_ms = (float(c.get(k, 0.0)) for k in ('ic_agogic_ms', 'ic_vel', 'h_breath_ms'))
    if (ic_ms or ic_v or h_ms) and base_role in FIG + ('counter',) and tonic is not None:
        z_ic, z_h = expectation.note_z(ns, tonic)
        start_boost += ic_ms / 1000.0 * z_ic + h_ms / 1000.0 * np.maximum(z_h - 0.5, 0.0)
        v += ic_v * z_ic

    # ---- melody lead that follows velocity (Goebl 2001; Goebl et al. 2005) --------------------
    vl = float(c.get('vel_lead_ms', 0.0))
    if vl > 0 and not is_drum:
        fac = 1.0 if any(w in str(instrument or '').lower() for w in VEL_LEAD_WORDS) else 0.25
        for cl in clusters:
            if len(cl) < 2:
                continue
            mv = float(v_in[cl].mean())
            for j in cl:
                # a harder stroke throws its hammer sooner: the loud note of a chord arrives first
                start_boost[j] -= fac * vl / 1000.0 * float(v_in[j] - mv) / 64.0

    # ---- build events -------------------------------------------------------------------------
    t0 = tm.sec(t_beats)
    t1 = tm.sec(t_beats + d_beats)
    grace = np.zeros(n)                                  # grace notes (d <= 0.12 beats) tuck in before the beat, softer
    if not is_drum:
        for i in np.where(d_beats <= 0.12)[0]:
            grace[i] = -0.04
            v[i] *= 0.75
    start = t0 + lead + drift_term + anti + strum_off + grace + start_boost
    if pk:                                               # a pocket carries its own per-limb timing
        tempo_scale = (96.0 / max(40.0, float(bpm))) ** float(pocketlib.tempo_power(pk, c.get('push_tempo_power', 0.4)))
        start = start + pocket_ms * tempo_scale / 1000.0
    if is_drum and not pk:
        # a fixed push per piece is only right at one tempo and one subdivision: scale both
        tempo_scale = (96.0 / max(40.0, float(bpm))) ** float(c.get('push_tempo_power', 0.4))
        uniq = np.unique(np.round(t_beats, 3))
        dense = bool(len(uniq) > 1 and np.min(np.diff(uniq)) < 0.26)
        subdiv = float(c.get('subdiv_push_ms', 0.0)) if dense else 0.0
        push = np.array([DRUM_PUSH.get(int(pp), 0.0) * tempo_scale for pp in p]) / 1000.0
        push = push + (subdiv / 1000.0 if subdiv else 0.0)
        start = start + push
    elif is_drum:
        uniq = np.unique(np.round(t_beats, 3))
        dense = bool(len(uniq) > 1 and np.min(np.diff(uniq)) < 0.26)
        subdiv = float(c.get('subdiv_push_ms', 0.0)) if dense else 0.0
        start = start + subdiv / 1000.0
    # a named part reads the piece's ensemble asynchrony: one field, built by tempo_map_for
    async_ms = float((getattr(tm, 'asynchrony', None) or {}).get(str(part), 0.0)) if part is not None else 0.0
    start = start + async_ms / 1000.0
    # and its own phase-coupling correction, when the score asked for one (build_stems pre-pass)
    if part is not None:
        curve = (getattr(tm, 'phase_curves', None) or {}).get(str(part))
        if curve:
            start = start + curve_at(curve, t_beats)
    dur = finalize_durations(t0, t1, rd, c, v, phrases, base_role, is_drum, rng, n, FIG + ('counter',))
    # A negative offset near bar 1 used to collapse every affected note onto sample 0, phase-locking a chord and
    # leaving the list unsorted. Clamp, then stagger the clamped onsets so the attack order survives.
    start = np.asarray(start, dtype=float)
    clamped = np.maximum(0.0, start)
    neg = start < 0.0
    if neg.any():
        idx = np.where(neg)[0]
        for rank, j in enumerate(idx[np.argsort(start[idx])]):
            clamped[j] = 0.001 * min(rank, 32)
    # intonation: a phrase drifts a few cents together, a chord leans towards just intonation instead of being
    # tuned to 12-TET (a major third about 14 cents flat, a fifth about 2 cents sharp), and a high register sits a
    # touch sharp (High Sharp, ~1.5 cents per octave above C4)
    cents_extra = np.zeros(n)
    td = float(c.get('tune_drift_cents', 0.0))
    if td > 0:
        for idx in phrases.values():
            cents_extra[idx] += _smooth_noise(rng, len(idx), corr=3.0) * td
    jr = float(c.get('just_ratio', 0.0))
    if jr > 0 and base_role in ('chord', 'pad', 'arp', 'texture'):
        for cl in clusters:
            if len(cl) < 2:
                continue
            root = ns[min(cl, key=lambda j: ns[j]['p'])]['p']
            for j in cl:
                cents_extra[j] += jr * JUST.get(int((ns[j]['p'] - root) % 12), 0.0)
    hs = float(c.get('high_sharp_cents', 0.0))
    if hs and base_role in FIG + ('counter',):
        cents_extra += hs * np.clip((p - 60.0) / 12.0, 0.0, 3.0)
    ev = []
    order = np.lexsort((p, clamped))                     # strictly ordered by (onset, pitch)
    for j in order:
        extra = {k: ns[j][k] for k in ('art', 'c', 'gl', 'gs', 'vd', 'vowel', 'style', 'formants', 'voices', 'lyric') if k in ns[j]}
        if cents_extra[j] or 'c' in extra:
            extra['c'] = float(extra.get('c', 0.0)) + float(cents_extra[j])
        ev.append(dict(t=float(clamped[j]), dur=float(max(0.03, dur[j])), p=int(ns[j]['p']),
                       v=int(np.clip(round(v[j]), 1, 127)), role=base_role, beat=float(t_beats[j]), **extra))
    # legato: let a sustained melodic note overlap the next one in the same line by a few tens of ms
    if rd['legato'] and not is_drum:
        mono = sorted(ev, key=lambda e_: e_['t'])
        for a, b in zip(mono[:-1], mono[1:]):
            gap = b['t'] - (a['t'] + a['dur'])
            if a.get('art') == 'staccato' or b['t'] <= a['t'] + 0.05 or a['beat'] in breathed:   # staccato, a chord tone or a bar breath: leave alone
                continue
            if -0.001 < gap < 0.20:
                a['dur'] = (b['t'] - a['t']) + legato_overlap_ms / 1000.0
    return sorted(ev, key=lambda e_: e_['t'])
