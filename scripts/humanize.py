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

#!/usr/bin/env python3
"""humanize.py - turn a robotic, grid-perfect note list into something a person could have played.

Why this exists: a MIDI score where every note lands exactly on the grid with the same velocity
sounds like a machine no matter how good the samples are. Real players differ from the grid in
structured ways (research summary in references/humanization.md):

  * the melody leads the accompaniment by ~15-30 ms and is played louder (Goebl 2001)
  * timing error is NOT white noise: it drifts slowly (1/f-like) and neighbouring errors are
    anti-correlated (a late note is followed by an early one) - so we use drift + (e[i]-0.5*e[i-1])
  * phrases breathe: tiny accelerando into the middle, slowing at the end, big ritardando at the close
  * dynamics follow the beat (downbeat > offbeat), the phrase (arch), and the pitch contour
  * chords are never struck at the same instant: strums / rolls spread 5-30 ms
  * notes overlap or detach according to articulation; durations vary a few percent
  * drums: kick tight, snare a hair late, hats loose, ghost notes quiet, accents patterned

Everything is seeded, so the same score + seed always renders identically.

Input note (dict): {"t": beat, "d": beats, "p": midi, "v": 0..1 or 1..127, "role": optional}
roles: melody | counter | chord | pad | bass | arp | drum | fx (default: chord)
Output event (dict, SECONDS): {"t","dur","p","v"(1-127),"role","beat"}

    from humanize import humanize_track, TempoMap, PRESETS
"""
import numpy as np

import pattern_audit as pa                          # one definition of "machine gun", shared with the gate

PRESETS = {
    # timing_ms = per-note gaussian sigma; lead_ms = how early the melody sits; drift_ms = slow ensemble wander
    'tight':   dict(timing_ms=3,  drum_ms=2,  lead_ms=8,  drift_ms=3,  vel_sigma=3, rubato=0.00, wander=0.000, strum_ms=4,  ritard=0.20, accent=0.6),
    'natural': dict(timing_ms=7,  drum_ms=5,  lead_ms=20, drift_ms=9,  vel_sigma=5, rubato=0.025, wander=0.006, strum_ms=10, ritard=0.35, accent=1.0),
    'loose':   dict(timing_ms=12, drum_ms=9,  lead_ms=25, drift_ms=15, vel_sigma=7, rubato=0.04, wander=0.010, strum_ms=16, ritard=0.40, accent=1.2),
    'rubato':  dict(timing_ms=9,  drum_ms=6,  lead_ms=28, drift_ms=12, vel_sigma=6, rubato=0.07, wander=0.015, strum_ms=22, ritard=0.50, accent=0.8),
    'punchy':  dict(timing_ms=4,  drum_ms=2,  lead_ms=10, drift_ms=4,  vel_sigma=4, rubato=0.01, wander=0.002, strum_ms=6,  ritard=0.20, accent=1.3, upbeat=True),
    'bouncy':  dict(timing_ms=5,  drum_ms=3,  lead_ms=12, drift_ms=5,  vel_sigma=5, rubato=0.01, wander=0.003, strum_ms=8,  ritard=0.20, accent=1.4, upbeat=True),
}

# The timing model's own defaults, merged under a preset. They are values, not choices: a preset or a score overrides
# any of them. `note_lag1` is the pull-back of a note on the one before (the negative lag-1 correlation of a player);
# `drift_corr_beats` is how slowly the shared wander moves; `vel_dur` couples a louder note to a slightly longer one;
# `tune_drift_cents` lets a phrase drift in intonation together; `just_ratio` bends chord tones towards just intonation
# (0 = equal temperament, 1 = full just intonation); the drum keys scale the fixed push with tempo and subdivision.
TIMING = dict(note_lag1=0.5, drift_corr_beats=6.0, vel_dur=0.018, tune_drift_cents=1.2, just_ratio=0.45,
              push_tempo_power=0.4, subdiv_push_ms=1.2)

# deviation of just intonation from 12-TET, in cents, by interval above the chord's lowest sounding note
JUST = {1: 11.7, 2: 3.9, 3: 15.6, 4: -13.7, 5: -2.0, 6: -9.8, 7: 2.0, 8: 13.7, 9: -15.6, 10: 17.6, 11: -11.7}

# per-role defaults: (timing offset ms relative to the beat, velocity offset, legato gate)
ROLE = {
    'melody':  dict(off=-1.0, vel=+8,  gate=1.00, legato=True),    # offset multiplier of lead_ms (negative = early)
    'counter': dict(off=-0.4, vel=+2,  gate=1.00, legato=True),
    'chord':   dict(off=+0.2, vel=-6,  gate=0.95, legato=False),
    'pad':     dict(off=+0.3, vel=-10, gate=1.02, legato=True),
    'bass':    dict(off=0.0,  vel=-1,  gate=0.90, legato=False),
    'arp':     dict(off=+0.1, vel=-4,  gate=0.85, legato=False),
    'drum':    dict(off=0.0,  vel=0,   gate=1.00, legato=False),
    'fx':      dict(off=0.0,  vel=0,   gate=1.00, legato=False),
}

# drum piece offsets in ms (kick tight/early, snare lays back, hats loose)
DRUM_PUSH = {36: -3.0, 35: -3.0, 38: +5.0, 40: +5.0, 37: +3.0, 39: +4.0, 42: +1.0, 44: +1.0, 46: +2.0,
             51: +2.0, 59: +2.0, 49: 0.0, 57: 0.0}


def _vel127(v):
    v = float(v)
    return v * 127.0 if v <= 1.0 else v


def _smooth_noise(rng, n, corr):
    """Slowly varying zero-mean noise with unit std; `corr` = correlation length in samples."""
    if n <= 0:
        return np.zeros(0)
    w = rng.standard_normal(n + int(corr) * 6)
    k = np.exp(-0.5 * (np.arange(-3 * int(corr) - 1, 3 * int(corr) + 2) / max(corr, 1)) ** 2)
    y = np.convolve(w, k / k.sum(), mode='same')[int(corr) * 3:int(corr) * 3 + n]
    s = y.std()
    return (y - y.mean()) / (s if s > 1e-9 else 1.0)


def shared_drift(seed, total_beats, preset='natural', points=512):
    """One slow wander for the whole piece, as (beats, values), so every track drifts together.

    Measured before this: each track built its own drift, so two players of the same section wandered apart by tens of
    milliseconds. A section shares its tempo drift and differs only in the small motor error of each note, which is
    what `note_lag1` produces.
    """
    c = dict(PRESETS['natural'])
    c.update(TIMING)
    if isinstance(preset, str):
        c.update(PRESETS.get(preset, {}))
    elif isinstance(preset, dict):
        c.update(preset)
    rng = np.random.default_rng(int(seed) + 7919)
    g = np.linspace(0.0, max(1.0, float(total_beats)), int(points))
    span = float(c.get('drift_corr_beats', 6.0)) * 8.0
    vals = _smooth_noise(rng, int(points), corr=max(2.0, span))
    return g, vals * 0.5          # 0.5: the curve is multiplied by drift_ms at use, matching the old amplitude


class TempoMap:
    """beats -> seconds, with tempo points, phrase-arch rubato, slow wander and a final ritardando.

    TempoMap(100) is a plain constant tempo. TempoMap(100, points=[[0,100],[32,84]]) ramps linearly.
    rubato: amplitude of the phrase arch (0.03 = +-3 % tempo). ritard: fraction slowed at the very end.
    """

    def __init__(self, bpm, total_beats=64, points=None, rubato=0.0, phrase_beats=16, wander=0.0,
                 ritard=0.0, ritard_beats=6, fermata=None, seed=1):
        rng = np.random.default_rng(seed)
        step = 1.0 / 48.0
        T = total_beats + 16
        g = np.arange(0, T, step)
        if points:
            pts = sorted(points)
            base = np.interp(g, [p[0] for p in pts], [p[1] for p in pts])
        else:
            base = np.full_like(g, float(bpm))
        f = np.ones_like(g)
        if rubato:
            x = (g % phrase_beats) / phrase_beats
            f *= 1 + rubato * (np.sin(np.pi * x) - 2 / np.pi)
        if wander:
            f *= 1 + wander * _smooth_noise(rng, len(g), corr=8 / step)
        if ritard:
            a = total_beats - ritard_beats
            x = np.clip((g - a) / ritard_beats, 0, 1)
            f *= 1 - ritard * x ** 2
        spb = 60.0 / (base * f)
        secs = np.concatenate([[0], np.cumsum(spb[:-1] * step)])
        if fermata:                               # [(beat, extra_seconds), ...] - hold a note/chord longer
            for b, extra in fermata:
                secs += np.where(g > b, extra, 0.0)
        self.g, self.secs, self.base_bpm, self.total_beats = g, secs, base, total_beats

    def sec(self, beats):
        b = np.asarray(beats, dtype=float)
        out = np.interp(b, self.g, self.secs)
        # np.interp clamps past the end of the map. A note beyond it then landed on the same second as every other
        # note out there, collapsing the end of a piece onto one instant (measured: 49 events at 20.60 s). Continue
        # at the last mapped tempo instead.
        if np.any(b > self.g[-1]) and len(self.g) > 2:
            slope = (self.secs[-1] - self.secs[-2]) / (self.g[-1] - self.g[-2])
            out = np.where(b > self.g[-1], self.secs[-1] + (b - self.g[-1]) * slope, out)
        return out

    def beat(self, seconds):
        return np.interp(np.asarray(seconds, dtype=float), self.secs, self.g)

    @property
    def length(self):
        return float(self.sec(self.total_beats))


def tempo_map_for(score, seed=None, pad_beats=1):
    """The one TempoMap of a score. The renderer and the pipeline both call this, so the reported duration,
    the ritardando position and the rendered audio cannot disagree (they were built independently with
    different rubato, ritard and total length)."""
    tracks = score.get('tracks', []) or []
    total = max([float(n['t']) + float(n.get('d', 0.0)) for t in tracks for n in t.get('notes', [])] or [16.0])
    cfg = score.get('humanize', 'natural')
    preset = PRESETS.get(cfg if isinstance(cfg, str) else 'natural', PRESETS['natural'])
    rub = score.get('rubato', preset.get('rubato', 0.02))
    wander = score.get('wander', 0.0 if cfg == 'tight' else 0.004)
    tm = TempoMap(score.get('bpm', 90), total_beats=total + pad_beats, points=score.get('tempo_points'),
                  rubato=rub, wander=wander, ritard=score.get('ritard', 0.3),
                  ritard_beats=score.get('ritard_beats', 6), phrase_beats=score.get('phrase_beats', 16),
                  fermata=score.get('fermata'), seed=seed)
    # one shared wander for the whole piece: every track of a section drifts together instead of apart
    tm.shared_drift = shared_drift(seed if seed is not None else score.get('seed', 1), tm.total_beats, cfg)
    return tm


def apply_swing(notes, swing=0.5, unit=0.5):
    """Shift off-beat subdivisions late. swing 0.5 = straight, 0.58 light, 0.66 = triplet feel.

    The shift is capped at 45 % of the gap to the next onset, so a dense swung passage can never reorder or
    overlap notes (at 16th density a 0.66 swing used to hand a note to its successor).
    """
    if abs(swing - 0.5) < 1e-3:
        return notes
    shift = (swing - 0.5) * 2 * unit
    times = sorted({round(float(n['t']), 9) for n in notes})
    nxt = {a: b for a, b in zip(times, times[1:])}
    out = []
    for n in notes:
        m = n['t'] / unit
        r = round(m)
        t_new = n['t']
        if r % 2 == 1 and abs(m - r) < 0.2:
            room = nxt.get(round(float(n['t']), 9))
            cap = 0.45 * (room - n['t']) if room is not None else shift
            t_new = n['t'] + min(shift, max(0.0, cap))
        out.append(dict(n, t=t_new) if t_new != n['t'] else n)
    return out


def _beat_accent(t, ts=(4, 4), upbeat=False):
    """Metric weight 0..1 for a position in beats (strong on bar start, medium on mid-bar, weak off-beat)."""
    bar = ts[0]
    pos = t % bar
    if upbeat:
        if abs(pos * 2 - round(pos * 2)) < 0.04 and abs(pos - round(pos)) > 0.04:
            return 1.0   # primary upbeat (e.g. 0.5, 1.5, 2.5, 3.5)
        if abs(pos * 4 - round(pos * 4)) < 0.04 and abs(pos * 2 - round(pos * 2)) > 0.04:
            return 0.85  # 16th syncopation (e.g. 0.25, 0.75, 1.25)
        if abs(pos) < 0.02:
            return 0.75  # downbeat foundation
        return 0.4
    if abs(pos) < 0.02:
        return 1.0
    if ts[0] == 4 and abs(pos - 2) < 0.02:
        return 0.65
    if abs(pos - round(pos)) < 0.02:
        return 0.4
    if abs(pos * 2 - round(pos * 2)) < 0.04:
        return 0.15
    return 0.0


def _phrase_ids(notes_sorted, gap_beats=1.0, max_beats=16.0):
    """Split a line into phrases at rests >= gap_beats or after max_beats."""
    ids, cur, start, last_end = [], 0, None, None
    for n in notes_sorted:
        if start is None:
            start = n['t']
        elif (last_end is not None and n['t'] - last_end >= gap_beats) or n['t'] - start >= max_beats:
            cur += 1
            start = n['t']
        ids.append(cur)
        last_end = max(last_end or 0, n['t'] + n['d'])
    return ids


def humanize_track(notes, tm, cfg='natural', role=None, seed=0, ts=(4, 4), swing=0.5, swing_unit=0.5,
                   legato_overlap_ms=35, strum_dir='alt', detune_cents=0.0, instrument=None,
                   drift=None, articulation=None, bpm=None):
    """Humanize one track. Returns events in seconds sorted by time. cfg = preset name or dict.

    drift: (beats, values) from shared_drift(). When None the tempo map's own `shared_drift` is used, so every track of a
    piece that came from tempo_map_for() drifts together.
    articulation: {overlap_ms, gate, release_ms} from the instrument preset; overrides the role's fixed legato numbers.
    bpm: the tempo, for the drum push's tempo scaling (falls back to the tempo map).
    """
    c = dict(PRESETS['natural'])
    c.update(TIMING)
    c.update(PRESETS[cfg] if isinstance(cfg, str) else (cfg or {}))
    rng = np.random.default_rng(seed)
    base_role = role or 'chord'
    rd = ROLE.get(base_role, ROLE['chord'])
    if isinstance(articulation, dict):             # an instrument's own articulation, not the role's default
        rd = dict(rd, gate=float(articulation.get('gate', rd['gate'])))
        legato_overlap_ms = float(articulation.get('overlap_ms', legato_overlap_ms))
    if bpm is None:
        try:
            bpm = float(np.atleast_1d(getattr(tm, 'base_bpm', 96.0)).ravel()[0])
        except Exception:
            bpm = 96.0
    if drift is None:
        drift = getattr(tm, 'shared_drift', None)
    ns = apply_swing([dict(n) for n in notes], swing, swing_unit)
    ns.sort(key=lambda n: (n['t'], n['p']))
    if not ns:
        return []
    is_drum = base_role == 'drum'

    # ---- phrase structure and pitch contour -------------------------------------------------
    pid = _phrase_ids(ns)
    phrases = {}
    for i, k in enumerate(pid):
        phrases.setdefault(k, []).append(i)

    # ---- timing noise: slow drift + anti-correlated per-note error --------------------------
    n = len(ns)
    sig = (c['drum_ms'] if is_drum else c['timing_ms']) / 1000.0
    e = rng.standard_normal(n + 1) * sig
    # motor error: each note is pulled back by a fraction of the previous one, which is where the negative lag-1
    # correlation of a real player comes from
    anti = e[1:] - float(c.get('note_lag1', 0.5)) * e[:-1]
    # slow wander: shared by every track of the piece when the tempo map carries one (tempo_map_for builds it)
    if isinstance(drift, (tuple, list)) and len(drift) == 2:
        grid, vals = np.asarray(drift[0], float), np.asarray(drift[1], float)
        drift_term = np.interp(np.array([nt['t'] for nt in ns], float), grid, vals) * (c['drift_ms'] / 1000.0)
    elif drift is not None and len(drift):
        d = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(drift)), np.asarray(drift, float))
        drift_term = d * (c['drift_ms'] / 1000.0)
    else:
        drift_term = _smooth_noise(rng, n, corr=float(c.get('drift_corr_beats', 6.0))) * (c['drift_ms'] / 1000.0) * 0.5

    # group simultaneous onsets (chords) for strum spreading
    groups = {}
    for i, nt in enumerate(ns):
        groups.setdefault(round(nt['t'] * 96), []).append(i)
    strum_off = np.zeros(n)
    flip = 0
    guitar = 'guitar' in str(instrument or '').lower()
    for key, idx in groups.items():
        if len(idx) > 1 and base_role in ('chord', 'pad', 'arp', 'counter') and c['strum_ms'] > 0:
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

    # a melody leads the accompaniment only when something else sounds with it (render_natural sets note 'acc')
    accomp = np.array([float(nt.get('acc', 1.0)) for nt in ns])
    lead = rd['off'] * c['lead_ms'] / 1000.0 * accomp

    # ---- velocities ---------------------------------------------------------------------------
    v = np.array([_vel127(nt.get('v', 0.7)) for nt in ns], dtype=float)
    v_in = v.copy()                                    # what the score wrote, before any human shaping
    p = np.array([nt['p'] for nt in ns], dtype=float)
    upbeat = bool(c.get('upbeat', False) or c.get('upbeats', False))
    acc = np.array([_beat_accent(nt['t'], ts, upbeat=upbeat) for nt in ns])
    v += rd['vel']
    v += c['accent'] * (acc - 0.35) * 9.0                          # downbeats stronger
    for k, idx in phrases.items():                                # phrase arch + pitch-contour loudness
        m = len(idx)
        x = np.linspace(0, 1, m) if m > 1 else np.array([0.5])
        arch = np.sin(np.pi * x) - 0.5
        # a melody swells to its middle; a counter-line answers softer in the middle; beds and drums get no arch
        if base_role == 'melody':
            v[idx] += 7.0 * arch
        elif base_role == 'counter':
            v[idx] -= 3.0 * arch
        if m > 2:
            pz = (p[idx] - p[idx].mean()) / (p[idx].std() + 1e-6)
            v[idx] += 2.0 * np.clip(pz, -1.5, 1.5)             # higher notes a little louder
        if base_role == 'melody':
            v[idx[-1]] -= 6.0                                  # last note of a phrase relaxes
    # fast runs (taans, scale runs, 16th arpeggios): a run of 4+ short notes, each within half a beat of the last,
    # is shaped as a run. Every group of four starts stronger (the taan's sam-like accent); the run swells to its
    # middle and lets go. Without this a run is one flat level, because off-beat 16ths have metric weight 0.
    if not is_drum:
        runs, cur = [], []
        for i in range(n):
            if ns[i]['d'] > 0.5:
                continue
            gap = ns[i]['t'] - ns[cur[-1]]['t'] if cur else 0.0
            if cur and 0.01 < gap <= 0.5 + 1e-6:
                cur.append(i)
            else:
                if len(cur) >= 4:
                    runs.append(cur)
                cur = [i]
        if len(cur) >= 4:
            runs.append(cur)
        for run in runs:
            for pos, i in enumerate(run):
                v[i] += 5.0 if pos % 4 == 0 else (1.0 if pos % 4 == 2 else -2.0)
            v[run] += 4.0 * (np.sin(np.pi * np.linspace(0, 1, len(run))) - 0.5)
            # directional swell: an ascending run crescendos, a descending run decrescendos; the peak note leans forward
            pr = p[run]
            sgn = 1.0 if pr[-1] >= pr[0] else -1.0
            v[run] += 5.0 * sgn * np.linspace(-0.5, 0.5, len(run))
            v[run[int(np.argmax(pr))]] += 3.0
    vs = c['vel_sigma']
    v += _smooth_noise(rng, n, corr=3) * vs * 0.6 + rng.standard_normal(n) * vs * 0.6

    # automatic chord voicing (Goebl 2001): a score that wrote one velocity for every chord tone gets the top voice
    # lifted, the inner voices tucked back and the bass anchored. Uses the input velocities, so shaped scores are left alone.
    clusters = []
    for i in range(n):
        if clusters and ns[i]['t'] - ns[clusters[-1][0]]['t'] <= 0.04:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    if base_role in ('chord', 'pad', 'arp'):
        for cl in clusters:
            if len(cl) < 3 or v_in[cl].std() >= 1.5:
                continue
            order = sorted(cl, key=lambda j: ns[j]['p'])
            v[order[0]] += 2.0
            for j in order[1:-1]:
                v[j] -= 3.0
            v[order[-1]] += 5.0

    # ---- build events -------------------------------------------------------------------------
    t_beats = np.array([nt['t'] for nt in ns])
    d_beats = np.array([nt['d'] for nt in ns])
    start_boost = np.zeros(n)

    def _drum_run(run):
        """A run of rapid same-pitch hits with no dynamic contour is a machine gun: accent alternately."""
        if not pa._machine_run(v[run]):
            return
        m = len(run)
        for pos, i in enumerate(run):
            v[i] += 5.0 if pos % 2 == 0 else -5.0
            if v[run[-1]] > v[run[0]]:                 # an ascending build gets an exponential arch
                v[i] += 4.0 * ((pos / max(m - 1, 1)) ** 1.6 - 0.5)
            start_boost[i] += rng.uniform(-0.003, 0.003)

    if not is_drum:
        for i in range(1, n):
            if base_role in ('melody', 'counter') and abs(ns[i]['p'] - ns[i - 1]['p']) >= 5:
                start_boost[i] += 0.008                # agogic delay on the arrival of a leap
                v[i] += 4.0
                d_beats[i - 1] *= 0.92                 # shorten the note before the leap to articulate it
        for i, nt in enumerate(ns):
            if 'c' in nt or 'gl' in nt:                # microtones / glides / chromatic tension lean in
                v[i] += 3.0
                d_beats[i] *= 1.04
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
                    _drum_run(run)
                    run = [b]
            _drum_run(run)
        for i in range(1, n):                          # layered hits flam instead of phase-locking
            if abs(ns[i]['t'] - ns[i - 1]['t']) < 0.003 and ns[i]['p'] != ns[i - 1]['p']:
                start_boost[i] += 0.003 if i % 2 else -0.003

    t0 = tm.sec(t_beats)
    t1 = tm.sec(t_beats + d_beats)
    grace = np.zeros(n)                                  # grace notes (d <= 0.12 beats) tuck in before the beat, softer
    if not is_drum:
        for i in np.where(d_beats <= 0.12)[0]:
            grace[i] = -0.04
            v[i] *= 0.75
    start = t0 + lead + drift_term + anti[:n] + strum_off + grace + start_boost
    if is_drum:
        # a fixed push per piece is only right at one tempo and one subdivision: scale both
        tempo_scale = (96.0 / max(40.0, float(bpm))) ** float(c.get('push_tempo_power', 0.4))
        uniq = np.unique(np.round(t_beats, 3))
        dense = bool(len(uniq) > 1 and np.min(np.diff(uniq)) < 0.26)
        subdiv = float(c.get('subdiv_push_ms', 0.0)) if dense else 0.0
        push = np.array([DRUM_PUSH.get(int(pp), 0.0) * tempo_scale for pp in p]) / 1000.0
        push = push + (subdiv / 1000.0 if subdiv else 0.0)
        start = start + push
    dur = (t1 - t0) * rd['gate'] * (1 + rng.normal(0, 0.04, n))
    if not is_drum:
        # an accent is also a little longer; a soft note a little shorter (velocity-duration coupling)
        dur = dur * (1.0 + float(c.get('vel_dur', 0.0)) * (np.clip(v, 1, 127) - 90.0) / 64.0)
    if base_role in ('melody', 'counter'):                        # a phrase's last note breathes: held a little longer
        for idx in phrases.values():
            dur[idx[-1]] *= 1.08
    # A negative offset near bar 1 used to collapse every affected note onto sample 0, phase-locking a chord and
    # leaving the list unsorted. Clamp, then stagger the clamped onsets so the attack order survives.
    start = np.asarray(start, dtype=float)
    clamped = np.maximum(0.0, start)
    neg = start < 0.0
    if neg.any():
        idx = np.where(neg)[0]
        for rank, j in enumerate(idx[np.argsort(start[idx])]):
            clamped[j] = 0.001 * min(rank, 32)
    # intonation: a phrase drifts a few cents together, and a chord leans towards just intonation instead of being
    # tuned to 12-TET (a major third about 14 cents flat, a fifth about 2 cents sharp)
    cents_extra = np.zeros(n)
    td = float(c.get('tune_drift_cents', 0.0))
    if td > 0:
        for idx in phrases.values():
            cents_extra[idx] += _smooth_noise(rng, len(idx), corr=3.0) * td
    jr = float(c.get('just_ratio', 0.0))
    if jr > 0 and base_role in ('chord', 'pad', 'arp'):
        for cl in clusters:
            if len(cl) < 2:
                continue
            root = ns[min(cl, key=lambda j: ns[j]['p'])]['p']
            for j in cl:
                cents_extra[j] += jr * JUST.get(int((ns[j]['p'] - root) % 12), 0.0)
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
            if a.get('art') == 'staccato' or b['t'] <= a['t'] + 0.05:   # staccato or a chord tone: leave alone
                continue
            if -0.001 < gap < 0.20:
                a['dur'] = (b['t'] - a['t']) + legato_overlap_ms / 1000.0
    return sorted(ev, key=lambda e_: e_['t'])


def auto_pedal(events, tm, change_beats, lift_ms=40, re_press_ms=60):
    """Sustain-pedal events [(t_sec, 0|127)] for a piano line: pressed through each harmony, lifted
    just before every harmony change and pressed again right after (legato pedaling)."""
    out = [(0.0, 127)]
    for b in sorted(change_beats):
        t = float(tm.sec(b))
        out.append((max(0.0, t - lift_ms / 1000.0), 0))
        out.append((t + re_press_ms / 1000.0, 127))
    end = max((e['t'] + e['dur'] for e in events), default=0)
    out.append((end + 0.3, 0))
    return out


def event_stats(events, tm):
    """How far the humanized events moved from the nominal beat grid (what a human-ness check should see)."""
    if not events:
        return {}
    nom = tm.sec([e['beat'] for e in events])
    dev = (np.array([e['t'] for e in events]) - nom) * 1000.0
    v = np.array([e['v'] for e in events])
    return dict(notes=len(events), timing_ms_mean=round(float(dev.mean()), 1), timing_ms_std=round(float(dev.std()), 1),
                vel_mean=round(float(v.mean()), 1), vel_std=round(float(v.std()), 1), vel_levels=int(len(set(v.tolist()))))


def humanize_report(events):
    """Quick numbers a reviewer can read: velocity spread, timing deviation from a 16th grid."""
    if not events:
        return {}
    v = np.array([e['v'] for e in events])
    return dict(n=len(events), vel_mean=float(v.mean()), vel_std=float(v.std()),
                vel_unique=int(len(set(v.tolist()))))


if __name__ == '__main__':
    tm = TempoMap(100, total_beats=16, rubato=0.03, ritard=0.35)
    notes = [dict(t=i * 0.5, d=0.45, p=60 + (i % 5) * 2, v=0.7, role='melody') for i in range(32)]
    ev = humanize_track(notes, tm, 'natural', role='melody', seed=1)
    print(humanize_report(ev))
    print([round(e['t'], 3) for e in ev[:8]])
