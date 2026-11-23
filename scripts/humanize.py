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
structured ways (research summary in references/mixing/humanization.md):

  * the melody leads the accompaniment by ~15-30 ms and is played louder (Goebl 2001); part of that lead is a
    hammer-velocity artifact, so a louder note inside a chord also starts earlier (Goebl et al. 2005)
  * timing error is NOT white noise: it is long-range correlated (1/f^beta) and neighbouring errors are
    anti-correlated along one limb/finger (a late note is followed by an early one) - so we use a two-scale
    fractal drift plus an anti-correlated motor error per limb, never across limbs
  * phrases breathe: tiny accelerando into the middle, slowing at the end, big ritardando at the close; the close
    follows the kinematics of a stopping runner (v(x) with q = 3), not a parabola (Friberg & Sundberg 1999)
  * dynamics follow the beat (downbeat > offbeat), the phrase (arch), the pitch contour, and the tonal charge of the
    moment (KTH melodic/harmonic charge)
  * chords are never struck at the same instant: strums / rolls spread 5-30 ms
  * notes overlap or detach according to articulation; durations vary a few percent, and the KTH Duration Contrast /
    Double Duration / Faster Uphill / Punctuation / Repetition rules keep a rhythm from reading as a table
  * drums: kick tight, snare a hair late, hats loose, ghost notes quiet, accents patterned; the swing ratio itself
    shrinks as the tempo rises, because the short side of a swung pair has a physical floor (Friberg & Sundstrom 2002)

Everything is seeded, so the same score + seed always renders identically.

Input note (dict): {"t": beat, "d": beats, "p": midi, "v": 0..1 or 1..127, "role": optional}
roles: the canonical vocabulary in scripts/roles.py - melody | lead | vocal | counter | chord | pad |
bass | drum | arp | ostinato | drone | texture | fx | environment (default: chord). A synonym in that
module's alias table (`harmony`, `vox`, `percussion`, `sfx`) is resolved before the profile is chosen.
Output event (dict, SECONDS): {"t","dur","p","v"(1-127),"role","beat"}

    from humanize import humanize_track, TempoMap, PRESETS
"""
import re
import sys

import numpy as np

import pattern_audit as pa                          # one definition of "machine gun", shared with the gate
import roles as rolelib                             # one role vocabulary, shared with the gate and the mixer

PRESETS = {
    # timing_ms = short-scale (<8 beats) per-note jitter sigma; lead_ms = how early the melody sits;
    # drift_ms = long-scale (>=8 beats) shared ensemble wander; short_share = how much of the short-scale timing
    # variance is 1/f rather than white motor error. Sogorski, Geisel & Priesemann (2018) measured two power-law
    # regimes in >100 jazz and rock/pop recordings: a short process below ~8 beats that is much larger in jazz, and a
    # long process above ~8 beats (the shared tempo drift) that is similar across genres. So `timing_ms` is the
    # short, genre-dependent part and `drift_ms` the long, shared one - they are not interchangeable.
    'tight':   dict(timing_ms=3,  drum_ms=2,  lead_ms=8,  drift_ms=3,  vel_sigma=3, rubato=0.00, wander=0.000, strum_ms=4,  ritard=0.20, accent=0.6, short_share=0.15),
    'natural': dict(timing_ms=7,  drum_ms=5,  lead_ms=20, drift_ms=9,  vel_sigma=5, rubato=0.025, wander=0.006, strum_ms=10, ritard=0.35, accent=1.0, short_share=0.22),
    'loose':   dict(timing_ms=12, drum_ms=9,  lead_ms=25, drift_ms=15, vel_sigma=7, rubato=0.04, wander=0.010, strum_ms=16, ritard=0.40, accent=1.2, short_share=0.30),
    'rubato':  dict(timing_ms=9,  drum_ms=6,  lead_ms=28, drift_ms=12, vel_sigma=6, rubato=0.07, wander=0.015, strum_ms=22, ritard=0.50, accent=0.8, short_share=0.30),
    'punchy':  dict(timing_ms=4,  drum_ms=2,  lead_ms=10, drift_ms=4,  vel_sigma=4, rubato=0.01, wander=0.002, strum_ms=6,  ritard=0.20, accent=1.3, upbeat=True, short_share=0.15),
    'bouncy':  dict(timing_ms=5,  drum_ms=3,  lead_ms=12, drift_ms=5,  vel_sigma=5, rubato=0.01, wander=0.003, strum_ms=8,  ritard=0.20, accent=1.4, upbeat=True, short_share=0.18),
}

# The timing model's own defaults, merged under a preset. They are values, not choices: a preset or a score overrides
# any of them. `note_lag1` is the pull-back of a note on the one before (the negative lag-1 correlation of a player);
# `drift_corr_beats` is how slowly the shared wander moves; `vel_dur` couples a louder note to a slightly longer one;
# `tune_drift_cents` lets a phrase drift in intonation together; `just_ratio` bends chord tones towards just intonation
# (0 = equal temperament, 1 = full just intonation); the drum keys scale the fixed push with tempo and subdivision.
#
# fractal_beta / short_scale_beats / short_share: timing and loudness are scale-free (1/f^beta), not one Gaussian
# cutoff. beta ~0.85 is inside the 0.5-1.0 band measured for both inter-beat intervals and hit amplitudes.
# vel_time_couple: on percussion, loudness itself follows the microtiming (Rasanen et al. 2015: Porcaro's hi-hat has
# 1/f long-range correlation in BOTH intervals and amplitudes, plus short-range anti-correlation).
# The KTH local rules (Friberg, Bresin & Sundberg 2006): duration_contrast, double_duration (the 2:1 softening),
# faster_uphill_ms, punctuation_ms, repetition_gap_ms, high_sharp_cents.
# vel_lead_ms: the hammer-velocity part of melody lead (Goebl 2001; Goebl et al. 2005), only on hammered/plucked
# instruments; phrase_tempo_vel couples phrase rubato to phrase dynamics (Todd 1992);
# melodic_charge_* / harmonic_charge_*: KTH tonal tension (Sundberg et al. 1991) from circle-of-fifths distance.
TIMING = dict(note_lag1=0.5, drift_corr_beats=6.0, vel_dur=0.018, tune_drift_cents=1.2, just_ratio=0.45,
              push_tempo_power=0.4, subdiv_push_ms=1.2,
              fractal_beta=0.85, short_scale_beats=8.0, short_share=0.22, vel_time_couple=0.35,
              duration_contrast=0.06, double_duration=0.10, faster_uphill_ms=2.0, punctuation_ms=12.0,
              repetition_gap_ms=14.0, high_sharp_cents=1.5, vel_lead_ms=6.0, phrase_tempo_vel=2.0,
              melodic_charge_vel=2.0, melodic_charge_dur=0.015, harmonic_charge_vel=1.5, harmonic_charge_dur=0.010)

# A score's `elastic` block: long-range tempo breathing, and a collective breath hold at named beats.
ELASTIC_KEYS = ('amount', 'corr_beats', 'breaths', 'breath_s')

# deviation of just intonation from 12-TET, in cents, by interval above the chord's lowest sounding note
JUST = {1: 11.7, 2: 3.9, 3: 15.6, 4: -13.7, 5: -2.0, 6: -9.8, 7: 2.0, 8: 13.7, 9: -15.6, 10: 17.6, 11: -11.7}

# per-role defaults: (timing offset ms relative to the beat, velocity offset, legato gate)
ROLE = {
    'melody':  dict(off=-1.0, vel=+8,  gate=1.00, legato=True),    # offset multiplier of lead_ms (negative = early)
    'lead':    dict(off=-1.0, vel=+8,  gate=1.00, legato=True),    # the same figure under its prominence name
    'vocal':   dict(off=-0.9, vel=+7,  gate=1.03, legato=True),    # a sung line sits slightly ahead and holds longer
    'counter': dict(off=-0.4, vel=+2,  gate=1.00, legato=True),
    'chord':   dict(off=+0.2, vel=-6,  gate=0.95, legato=False),
    'pad':     dict(off=+0.3, vel=-10, gate=1.02, legato=True),
    'texture': dict(off=+0.3, vel=-10, gate=1.03, legato=True),    # a grain bed is shaped like a pad, not like an effect
    'drone':   dict(off=+0.3, vel=-10, gate=1.05, legato=True),    # holds through, never re-attacks on the grid
    'bass':    dict(off=0.0,  vel=-1,  gate=0.90, legato=False),
    'arp':     dict(off=+0.1, vel=-4,  gate=0.85, legato=False),
    'ostinato': dict(off=+0.1, vel=-3, gate=0.94, legato=False),   # repeated cell, but each repeat is played
    'drum':    dict(off=0.0,  vel=0,   gate=1.00, legato=False),
    'fx':      dict(off=0.0,  vel=0,   gate=1.00, legato=False),
    'environment': dict(off=0.0, vel=0, gate=1.00, legato=False),
}

# The figure family: the line the ear follows. A role missing from ROLE used to fall through to the chord
# profile, which is how a drone ended up shaped like a comp. Unknown roles now raise in roles.canonical().
FIG = rolelib.LEAD

# GERM expression profiles (Juslin, Friberg & Bresin 2001; Bresin & Friberg 2011): a mood is a bundle of the same
# variables - level, articulation, accent, rubato, strum - not a different humanizer. They scale on top of a groove
# preset, so `tight` + `tender` and `loose` + `tender` are both possible. Values are starting values.
MOODS = {
    'tender': dict(vel=-6.0, gate=+0.04, accent=0.85, duration_contrast=0.70, strum=1.35, rubato=1.25),
    'bright': dict(vel=+5.0, gate=-0.02, accent=1.15, duration_contrast=1.30, strum=0.75, rubato=0.85),
    'solemn': dict(vel=-3.0, gate=+0.02, accent=1.05, duration_contrast=0.85, strum=1.15, rubato=0.70),
    'urgent': dict(vel=+4.0, gate=-0.06, accent=1.25, duration_contrast=1.50, strum=0.50, rubato=0.35),
}

# drum piece offsets in ms (kick tight/early, snare lays back, hats loose)
DRUM_PUSH = {36: -3.0, 35: -3.0, 38: +5.0, 40: +5.0, 37: +3.0, 39: +4.0, 42: +1.0, 44: +1.0, 46: +2.0,
             51: +2.0, 59: +2.0, 49: 0.0, 57: 0.0}

# A limb is one motor program. The lag-1 correction belongs to it and to nothing else: a simultaneous kick and hi-hat
# are two limbs, and two notes of one chord are two fingers. (Frühauf et al. 2013; Senn et al. 2016 on groove loss.)
DRUM_LIMB = {35: 'kick', 36: 'kick', 37: 'stick', 38: 'snare', 39: 'clap', 40: 'snare', 41: 'tom_low',
             43: 'tom_low', 45: 'tom_mid', 47: 'tom_mid', 48: 'tom_high', 50: 'tom_high',
             42: 'hat', 44: 'hat', 46: 'hat', 51: 'ride', 53: 'ride', 59: 'ride', 49: 'crash', 52: 'crash',
             55: 'crash', 57: 'crash'}

# instruments whose onset is a hammer or a pluck, where a harder stroke really does arrive sooner (Goebl 2001)
VEL_LEAD_WORDS = ('piano', 'celesta', 'harpsichord', 'clav', 'marimba', 'vibra', 'xylophone', 'glocken', 'kalimba',
                  'guitar', 'lute', 'harp', 'sitar', 'santoor', 'kora', 'banjo', 'mandolin', 'dulcimer', 'cimbalom')

# Circle-of-fifths position of each pitch class (C=0, G=1, D=2, ...). Tonal distance is the short way round it.
CIRCLE = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: 7, 8: 8, 3: 9, 10: 10, 5: 11}
NOTE_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

# swing: BUR (beat-upbeat ratio) falls nearly linearly with tempo and reaches 1:1 at ~280 BPM, and the short side of a
# pair has a physical floor around 95 ms (Friberg & Sundstrom 2002). Starting values.
SWING_BUR_SLOW, SWING_BUR_FAST = 3.5, 1.0
SWING_BPM_SLOW, SWING_BPM_FAST = 60.0, 280.0
SWING_FLOOR_S = 0.095
SWING_FIG_DEPTH = 0.6        # a soloist swings less than the ride cymbal behind them

CHORD_ROLES = ('chord', 'pad', 'bass', 'arp', 'texture')


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


def _fractal_noise(rng, n, beta=0.85, fc=None, highpass=False):
    """1/f^beta noise with unit std, shaped in the frequency domain.

    Human timing and loudness are long-range correlated rather than smoothed white noise: every frequency bin of a
    white draw is scaled by f**(-beta/2), so the series carries a scale-free cascade instead of a single Gaussian
    cutoff (Rasanen et al. 2015 on intervals AND amplitudes; Sogorski, Geisel & Priesemann 2018 on the two regimes).
    `fc` (cycles per sample) is a soft band edge: with `highpass` the slow trend is removed (the short-scale process,
    inside `short_scale_beats`), without it the fast detail is removed (the long-scale process, the shared wander).
    """
    n = int(n)
    if n <= 0:
        return np.zeros(0)
    if n < 3:
        return np.zeros(n)
    w = rng.standard_normal(n)
    spec = np.fft.rfft(w)
    f = np.fft.rfftfreq(n)
    f = np.where(f <= 0.0, 1.0 / n, f)
    amp = f ** (-0.5 * float(beta))
    if fc and float(fc) > 0.0:
        lp = 1.0 / (1.0 + (f / float(fc)) ** 4)
        amp = amp * ((1.0 - lp) if highpass else lp)
    y = np.fft.irfft(spec * amp, n)
    y = y - y.mean()
    s = float(y.std())
    return y / s if s > 1e-12 else np.zeros(n)


def _limb_of(pitch):
    """The motor stream a drum pitch belongs to (a kit is several limbs, not one hand)."""
    return DRUM_LIMB.get(int(pitch), f'other{int(pitch)}')


def _circle_distance(pc, root_pc):
    """Tonal charge of a pitch class against a root: 0 at the root, 1 at the tritone (circle-of-fifths distance)."""
    d = abs(CIRCLE[int(pc) % 12] - CIRCLE[int(root_pc) % 12]) % 12
    return min(d, 12 - d) / 6.0


def key_tonic(key):
    """'D minor' / 'Bb' / 'F#' / 2 -> tonic pitch class (None when the score names no key)."""
    if key is None:
        return None
    if isinstance(key, (int, float, np.integer, np.floating)):
        return int(key) % 12
    m = re.match(r'\s*([A-Ga-g])([#b]?)', str(key))
    if not m:
        return None
    pc = NOTE_PC[m.group(1).upper()] + {'#': 1, 'b': -1}.get(m.group(2), 0)
    return pc % 12


def _figure_track(tracks):
    """The track that carries the line (melody | lead | vocal), which is the one whose phrases the piece breathes on."""
    for tr in tracks or []:
        try:
            role = rolelib.canonical(tr.get('role'))
        except Exception:
            continue
        if role in FIG and tr.get('notes'):
            return tr
    return None


def score_phrase_spans(tracks):
    """Real phrase boundaries of the figure, as [(start_beat, end_beat), ...]; None when the piece has no figure.

    The tempo arches and the velocity arches must be the same phrases. A fixed `phrase_beats=16` rubato over a line
    whose phrases are 5 or 21 beats long is uncoordinated by construction: it swells where the melody does not.
    """
    tr = _figure_track(tracks)
    if not tr:
        return None
    ns = sorted([dict(n, d=float(n.get('d', 1.0))) for n in tr['notes']], key=lambda n: (float(n['t']), n.get('p', 0)))
    ids = _phrase_ids(ns)
    if not ids:
        return None
    starts, ends = [], []
    for k in sorted(set(ids)):
        idx = [i for i, q in enumerate(ids) if q == k]
        starts.append(float(ns[idx[0]]['t']))
        ends.append(float(ns[idx[-1]]['t']) + max(float(ns[idx[-1]]['d']), 0.25))
    spans = []
    for i, (s0, _e) in enumerate(zip(starts, ends)):
        s1 = starts[i + 1] if i + 1 < len(starts) else ends[i]
        if s1 > s0:
            spans.append((s0, s1))
    return spans or None


def score_chord_roots(tracks):
    """(beats, pitch classes) of the sounding harmony: the lowest note of every chord/pad/bass cluster.

    A melody note's tonal charge is measured against the root actually sounding under it. Without this the humanizer
    can only hear its own track, and a chromatic passing tone and a chord tone are indistinguishable.
    """
    notes = []
    for tr in tracks or []:
        try:
            role = rolelib.canonical(tr.get('role'))
        except Exception:
            continue
        if role not in CHORD_ROLES:
            continue
        for n in tr.get('notes', []) or []:
            try:
                notes.append((float(n['t']), float(n['p'])))
            except (KeyError, TypeError, ValueError):
                continue
    if not notes:
        return None
    notes.sort()
    beats, roots = [], []
    for t, pitch in notes:
        if beats and abs(t - beats[-1]) <= 1e-6:
            roots[-1] = min(roots[-1], pitch)
        else:
            beats.append(t)
            roots.append(pitch)
    return np.array(beats, float), np.array([int(round(r)) % 12 for r in roots], int)


def shared_drift(seed, total_beats, preset='natural', points=512):
    """One slow wander for the whole piece, as (beats, values), so every track drifts together.

    Measured before this: each track built its own drift, so two players of the same section wandered apart by tens of
    milliseconds. A section shares its tempo drift and differs only in the small motor error of each note, which is
    what `note_lag1` produces. Its shape is 1/f^beta below the drift correlation length, not one Gaussian cutoff.
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
    beats_per_point = max(float(total_beats), 1.0) / max(int(points), 1)
    vals = _fractal_noise(rng, int(points), beta=float(c.get('fractal_beta', 0.85)),
                          fc=beats_per_point / max(span, 1.0))
    return g, vals * 0.5          # 0.5: the curve is multiplied by drift_ms at use, matching the old amplitude


class TempoMap:
    """beats -> seconds, with tempo points, phrase-arch rubato, slow wander and a final ritardando.

    TempoMap(100) is a plain constant tempo. TempoMap(100, points=[[0,100],[32,84]]) ramps linearly.
    rubato: amplitude of the phrase arch (0.03 = +-3 % tempo). ritard: fraction slowed at the very end.
    ritard_q: the deceleration law of the close. q=3 (constant braking power) is the curve that fits measured final
    ritardandi and the highest-rated decelerations in listening tests (Friberg & Sundberg 1999); q=2 is the constant
    braking force. The old 1-ritard*x**2 was a parabola with no measurable support.
    phrase_spans: [(start_beat, end_beat)] - the figure's real phrases. When given, the rubato arch is placed on those
    and a rest carries no swell, instead of assuming a 16-beat period.
    elastic: long-range tempo deviation (0.04 = +-4 % over `elastic_corr_beats`), zero-mean so the average tempo
    is unchanged. breaths: beats where the whole ensemble takes a short collective breath (`breath_s` seconds).
    """

    def __init__(self, bpm, total_beats=64, points=None, rubato=0.0, phrase_beats=16, wander=0.0,
                 ritard=0.0, ritard_beats=6, fermata=None, seed=1, elastic=0.0,
                 elastic_corr_beats=12.0, breaths=None, breath_s=0.06, ritard_q=3.0, phrase_spans=None,
                 fractal_beta=None):
        rng = np.random.default_rng(seed)
        step = 1.0 / 48.0
        T = total_beats + 16
        g = np.arange(0, T, step)
        beta = float(TIMING['fractal_beta'] if fractal_beta is None else fractal_beta)
        if points:
            pts = sorted(points)
            base = np.interp(g, [p[0] for p in pts], [p[1] for p in pts])
        else:
            base = np.full_like(g, float(bpm))
        f = np.ones_like(g)
        if rubato:
            if phrase_spans:
                arch = np.ones_like(g)
                for s0, s1 in phrase_spans:
                    m = (g >= s0) & (g < s1)
                    if not m.any() or s1 <= s0:
                        continue
                    x = (g[m] - s0) / (s1 - s0)
                    arch[m] = 1 + rubato * (np.sin(np.pi * x) - 2 / np.pi)
                f *= arch
            else:
                x = (g % phrase_beats) / phrase_beats
                f *= 1 + rubato * (np.sin(np.pi * x) - 2 / np.pi)
        if wander:
            f *= 1 + wander * _fractal_noise(rng, len(g), beta=beta, fc=step / 8.0)
        if elastic:
            # phrase-scale elasticity, not a per-note wobble: a correlation length of several bars, and an
            # exactly zero-mean curve so the piece does not get slower or faster on average, only more or less urgent
            e = _fractal_noise(rng, len(g), beta=beta, fc=step / max(2.0, float(elastic_corr_beats)))
            body = g <= float(total_beats)             # centre on the piece, not on the padded map
            f *= 1 + float(elastic) * (e - float(e[body].mean() if body.any() else e.mean()))
        if ritard:
            a = total_beats - ritard_beats
            x = np.clip((g - a) / ritard_beats, 0, 1)
            q = float(ritard_q) if ritard_q and float(ritard_q) > 0.0 else 3.0
            w = max(0.05, 1.0 - float(ritard))
            f *= (1.0 + (w ** q - 1.0) * x) ** (1.0 / q)
        self.factor = f.copy()                    # the tempo multiplier alone, for local_tempo()/phrase coupling
        spb = 60.0 / (base * f)
        secs = np.concatenate([[0], np.cumsum(spb[:-1] * step)])
        if fermata:                               # [(beat, extra_seconds), ...] - hold a note/chord longer
            for b, extra in fermata:
                secs += np.where(g > b, extra, 0.0)
        if breaths:                               # a held breath before a harmonic turn, shared by every player
            for b in breaths:
                secs += np.where(g > float(b), float(breath_s), 0.0)
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

    def local_tempo(self, beats):
        """The tempo multiplier at a beat (1.0 = the written tempo): rubato, wander, elasticity and the final ritard."""
        return np.interp(np.asarray(beats, dtype=float), self.g, self.factor, left=1.0, right=1.0)

    @property
    def length(self):
        return float(self.sec(self.total_beats))


def tempo_map_for(score, seed=None, pad_beats=1):
    """The one TempoMap of a score. The renderer and the pipeline both call this, so the reported duration,
    the ritardando position and the rendered audio cannot disagree (they were built independently with
    different rubato, ritard and total length).

    It also carries the piece's phrase spans, tonic and sounding chord roots, so a track's humanization can place its
    arches on the real phrases and hear the harmony under its own line.
    """
    tracks = score.get('tracks', []) or []
    total = max([float(n['t']) + float(n.get('d', 0.0)) for t in tracks for n in t.get('notes', [])] or [16.0])
    cfg = score.get('humanize', 'natural')
    preset = PRESETS.get(cfg if isinstance(cfg, str) else 'natural', PRESETS['natural'])
    rub = score.get('rubato', preset.get('rubato', 0.02))
    wander = score.get('wander', 0.0 if cfg == 'tight' else 0.004)
    elastic = score.get('elastic') or {}
    if not isinstance(elastic, dict):
        raise ValueError(f"score.elastic must be an object {{{', '.join(ELASTIC_KEYS)}}}, got {type(elastic).__name__}")
    unknown = sorted(set(elastic) - set(ELASTIC_KEYS))
    if unknown:
        raise ValueError(f"score.elastic: unknown key(s) {', '.join(unknown)}; known: {', '.join(ELASTIC_KEYS)}")
    el_amount = float(elastic.get('amount', 0.0))
    el_corr = float(elastic.get('corr_beats', 12.0))
    el_breaths = [float(b) for b in (elastic.get('breaths') or [])]
    el_breath_s = float(elastic.get('breath_s', 0.06))
    if el_amount < 0.0 or el_amount > 0.25:
        raise ValueError('score.elastic.amount: expected 0..0.25 (a quarter of the tempo is not elasticity)')
    if el_breath_s < 0.0 or el_breath_s > 2.0:
        raise ValueError('score.elastic.breath_s: expected 0..2 seconds')
    mood = score.get('mood')
    mood = str(mood).lower() if mood is not None else None
    if mood in MOODS:                       # an expression profile scales the rubato (GERM: urgency is less rubato)
        rub = float(rub) * float(MOODS[mood].get('rubato', 1.0))
    elif mood is not None:
        mood = None                         # a score word that is not one of the profiles shapes nothing here
    seed = seed if seed is not None else score.get('seed', 1)
    tm = TempoMap(score.get('bpm', 90), total_beats=total + pad_beats, points=score.get('tempo_points'),
                  rubato=rub, wander=wander, ritard=score.get('ritard', 0.3),
                  elastic=el_amount, elastic_corr_beats=el_corr, breaths=el_breaths, breath_s=el_breath_s,
                  ritard_beats=score.get('ritard_beats', 6), phrase_beats=score.get('phrase_beats', 16),
                  ritard_q=score.get('ritard_q', 3.0), phrase_spans=score_phrase_spans(tracks),
                  fermata=score.get('fermata'), seed=seed)
    # one shared wander for the whole piece: every track of a section drifts together instead of apart
    tm.shared_drift = shared_drift(seed if seed is not None else score.get('seed', 1), tm.total_beats, cfg)
    tm.key = key_tonic(score.get('key'))
    tm.chord_roots = score_chord_roots(tracks)
    tm.mood = mood
    return tm


def auto_swing(bpm):
    """The swing ratio a player actually uses at a tempo, as a swing value (0.5 straight): BUR falls with tempo."""
    t = np.clip((SWING_BPM_FAST - float(bpm)) / (SWING_BPM_FAST - SWING_BPM_SLOW), 0.0, 1.0)
    bur = SWING_BUR_FAST + (SWING_BUR_SLOW - SWING_BUR_FAST) * float(t)
    return bur / (1.0 + bur)


def apply_swing(notes, swing=0.5, unit=0.5, bpm=None, role=None):
    """Shift off-beat subdivisions late. swing 0.5 = straight, 0.58 light, 0.66 = triplet feel.

    swing='auto' takes the ratio from the tempo (auto_swing): ~3.5:1 when slow, 2:1 at medium-fast, straight when
    fast. A figure role swings less than the accompaniment (SWING_FIG_DEPTH), which is what a soloist does over a
    ride cymbal. The short side of a pair never drops below SWING_FLOOR_S, so a fast passage straightens itself
    instead of asking for a 40 ms note.

    The shift is capped at 45 % of the gap to the next onset, so a dense swung passage can never reorder or
    overlap notes (at 16th density a 0.66 swing used to hand a note to its successor).
    """
    if isinstance(swing, str):
        if swing.lower() != 'auto':
            raise ValueError(f"swing: expected a number or 'auto', got {swing!r}")
        swing = auto_swing(120.0 if bpm is None else bpm)
    eff = float(swing)
    if role is not None:
        try:
            if rolelib.canonical(role) in FIG:
                eff = 0.5 + SWING_FIG_DEPTH * (eff - 0.5)
        except Exception:
            pass
    if abs(eff - 0.5) < 1e-3:
        return notes
    shift = (eff - 0.5) * 2 * unit
    if bpm:
        room = unit - float(bpm) * SWING_FLOOR_S / 60.0      # the short side, in beats, at the floor
        shift = min(shift, max(0.0, room))
        if shift <= 1e-9:
            return notes
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


ENSEMBLE_KEYS = ('players', 'spread_cents', 'spread_ms', 'vel_spread')


def ensemble_expand(notes, players=4, spread_cents=5.0, spread_ms=10.0, vel_spread=3.0, bpm=96.0, seed=0):
    """One written line -> `players` independent players of a section, as notes for the renderer.

    A sampled section track is one player multiplied, which is why a large string or brass section can read as a
    single very good player rather than a room of them. Real sections are a few cents apart (measured standard
    deviations of 2-13 cents in small violin sections, ISMA 2019; 14 cents is the tolerated F0 scatter in a choir,
    Ternstrom 1993), their bow/breath onsets are 20-50 ms apart (Rasch; Keller), and no two players have the same
    bow pressure, so each has a fixed intonation, timing and level offset, with per-note jitter on top.

    Each player gets one fixed offset drawn once (so it is the same player for the whole piece) and one small
    per-note deviation. `c` is added to any cents already on the note, so a microtonal line keeps its own tuning.
    `spread_ms` is a peak offset in milliseconds at the score's tempo; it is converted to beats here.

    Use it on a section part, not on a drum kit or a solo: a solo is one player by definition, and the engine's
    other humanisation already covers that. Values are starting values until a piece is measured.
    """
    n_pl = int(players)
    if n_pl < 2:
        raise ValueError('ensemble: players must be at least 2 (a solo is not a section)')
    if n_pl > 8:
        raise ValueError('ensemble: above 8 players, use a real multisampled section')
    if float(spread_cents) < 0.0 or float(spread_ms) < 0.0 or float(vel_spread) < 0.0:
        raise ValueError('ensemble: spread_cents, spread_ms and vel_spread cannot be negative')
    rng = np.random.default_rng(int(seed) + 104729)
    # stratified offsets: every player is somewhere in the section, not four copies drawn from a bell curve
    base = np.linspace(-1.0, 1.0, n_pl)
    base = base + rng.uniform(-0.3, 0.3, n_pl) / max(n_pl - 1, 1)
    cents = base * float(spread_cents)
    delay_ms = base * float(spread_ms) + rng.normal(0.0, max(0.5, float(spread_ms) * 0.2), n_pl)
    level = rng.normal(0.0, float(vel_spread), n_pl)
    length = 1.0 + rng.normal(0.0, 0.02, n_pl)
    beats_per_ms = float(bpm) / 60000.0
    out = []
    for nt in notes:
        for k in range(n_pl):
            e = dict(nt)
            e['t'] = float(nt['t']) + float(delay_ms[k]) * beats_per_ms
            e['c'] = float(nt.get('c', 0.0)) + float(cents[k]) + float(rng.normal(0.0, max(0.2, float(spread_cents) * 0.12)))
            e['d'] = max(0.02, float(nt.get('d', 1.0)) * float(length[k]))
            v = nt.get('v', 0.7)
            if float(v) <= 1.0:
                # a level offset in MIDI units is a fraction of the velocity scale, not of the note's own value
                e['v'] = float(np.clip(float(v) * (1.0 + float(level[k]) / 127.0), 0.01, 1.0))
            else:
                e['v'] = float(np.clip(float(v) + float(level[k]), 1.0, 127.0))
            e['player'] = k
            out.append(e)
    out.sort(key=lambda z: (z['t'], z['p']))
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
        last_end = max(last_end or 0, n['t'] + n.get('d', 0.0))
    return ids


def _motor_streams(ns, is_drum):
    """The streams whose successive onsets one motor program controls: one limb on a kit, one key/finger on a keyboard.

    The lag-1 correction belongs to that stream. Applied across the flat sorted list it correlated a hi-hat's error
    with a kick struck at the same instant (two limbs), and note 2 of a chord with note 1 of the same chord (two
    fingers, one keystroke), distorting the strum offset.
    """
    streams = {}
    for i, nt in enumerate(ns):
        k = _limb_of(nt['p']) if is_drum else int(nt['p'])
        streams.setdefault(k, []).append(i)
    return [streams[k] for k in sorted(streams, key=str)]


def _mood_profile(c):
    """Apply the GERM expression profile named in `c['mood']` (already merged from the score/preset), if any."""
    name = c.get('mood')
    if not name:
        return
    prof = MOODS.get(str(name).lower())
    if prof is None:
        raise ValueError(f"mood: unknown expression {name!r}; known: {', '.join(sorted(MOODS))}")
    c['vel_bias'] = c.get('vel_bias', 0.0) + float(prof.get('vel', 0.0))
    c['gate_bias'] = c.get('gate_bias', 0.0) + float(prof.get('gate', 0.0))
    c['accent'] = float(c.get('accent', 1.0)) * float(prof.get('accent', 1.0))
    c['duration_contrast'] = float(c.get('duration_contrast', 0.0)) * float(prof.get('duration_contrast', 1.0))
    c['strum_ms'] = float(c.get('strum_ms', 0.0)) * float(prof.get('strum', 1.0))


def humanize_track(notes, tm, cfg='natural', role=None, seed=0, ts=(4, 4), swing=0.5, swing_unit=0.5,
                   legato_overlap_ms=35, strum_dir='alt', detune_cents=0.0, instrument=None,
                   drift=None, articulation=None, bpm=None, mood=None, key=None, chord_roots=None,
                   tempo_swing=None):
    """Humanize one track. Returns events in seconds sorted by time. cfg = preset name or dict.

    drift: (beats, values) from shared_drift(). When None the tempo map's own `shared_drift` is used, so every track of a
    piece that came from tempo_map_for() drifts together.
    articulation: {overlap_ms, gate, release_ms} from the instrument preset; overrides the role's fixed legato numbers.
    bpm: the tempo, for the drum push's tempo scaling (falls back to the tempo map).
    mood: a GERM expression profile (MOODS) layered on the groove preset; falls back to the tempo map's score mood.
    key / chord_roots: the tonic and the sounding roots, for tonal charge; fall back to the tempo map's.
    tempo_swing: alias for `swing` that also accepts 'auto'.
    """
    c = dict(PRESETS['natural'])
    c.update(TIMING)
    c.update(PRESETS[cfg] if isinstance(cfg, str) else (cfg or {}))
    rng = np.random.default_rng(seed)
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
    ns = apply_swing([dict(n) for n in notes], swing, swing_unit, bpm=bpm, role=base_role)
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
    # a drum's own motor jitter stays conservative (<10 ms): beyond that the groove degrades (Fruhauf 2013)
    sig = (min(float(c['drum_ms']), 8.0) if is_drum else float(c['timing_ms'])) / 1000.0
    gaps = np.diff(np.sort(t_beats)) if n > 1 else np.array([])
    gap = float(np.median(gaps)) if len(gaps) else 1.0
    step_beats = max(1e-6, gap)
    beta = float(c.get('fractal_beta', 0.85))
    share = float(np.clip(c.get('short_share', 0.0), 0.0, 1.0))
    frac = _fractal_noise(rng, n, beta=beta,
                          fc=step_beats / max(1e-6, float(c.get('short_scale_beats', 8.0))), highpass=True)
    frac_term = frac * sig * np.sqrt(share)      # the short-scale (<8 beats) 1/f process, per player
    motor_sig = sig * np.sqrt(max(0.0, 1.0 - share))
    # motor error: each note is pulled back by a fraction of the previous one of the SAME limb/finger, which is where
    # the negative lag-1 correlation of a real player comes from. Never across limbs or across a chord's fingers.
    anti = np.zeros(n)
    lag1 = float(c.get('note_lag1', 0.5))
    for stream in _motor_streams(ns, is_drum):
        m = len(stream)
        e = rng.standard_normal(m) * motor_sig
        a = e.copy()
        if m > 1:
            a[1:] = e[1:] - lag1 * e[:-1]
        anti[np.asarray(stream)] = a
    anti = anti + frac_term
    # slow wander: shared by every track of the piece when the tempo map carries one (tempo_map_for builds it)
    if isinstance(drift, (tuple, list)) and len(drift) == 2:
        grid, vals = np.asarray(drift[0], float), np.asarray(drift[1], float)
        drift_term = np.interp(t_beats, grid, vals) * (c['drift_ms'] / 1000.0)
    elif drift is not None and len(drift):
        d = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(drift)), np.asarray(drift, float))
        drift_term = d * (c['drift_ms'] / 1000.0)
    else:
        drift_term = (_fractal_noise(rng, n, beta=beta, fc=step_beats / max(1.0, float(c.get('drift_corr_beats', 6.0))))
                      * (c['drift_ms'] / 1000.0) * 0.5)

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
    v = np.array([_vel127(nt.get('v', 0.7)) for nt in ns], dtype=float)
    v_in = v.copy()                                    # what the score wrote, before any human shaping
    upbeat = bool(c.get('upbeat', False) or c.get('upbeats', False))
    acc = np.array([_beat_accent(nt['t'], ts, upbeat=upbeat) for nt in ns])
    v += rd['vel'] + float(c.get('vel_bias', 0.0))
    v += c['accent'] * (acc - 0.35) * 9.0                          # downbeats stronger
    for k, idx in phrases.items():                                # phrase arch + pitch-contour loudness
        m = len(idx)
        x = np.linspace(0, 1, m) if m > 1 else np.array([0.5])
        arch = np.sin(np.pi * x) - 0.5
        # the figure swells to its middle; a counter-line answers softer in the middle; beds and drums get no arch
        if base_role in FIG:
            v[idx] += 7.0 * arch
        elif base_role == 'counter':
            v[idx] -= 3.0 * arch
        if m > 2:
            pz = (p[idx] - p[idx].mean()) / (p[idx].std() + 1e-6)
            v[idx] += 2.0 * np.clip(pz, -1.5, 1.5)             # higher notes a little louder
        if base_role in FIG:
            v[idx[-1]] -= 6.0                                  # last note of a phrase relaxes
    # fast runs (taans, scale runs, 16th arpeggios): a run of 4+ short notes, each within half a beat of the last,
    # is shaped as a run. Every group of four starts stronger (the taan's sam-like accent); the run swells to its
    # middle and lets go. Without this a run is one flat level, because off-beat 16ths have metric weight 0.
    if not is_drum:
        runs, cur = [], []
        for i in range(n):
            if ns[i]['d'] > 0.5:
                # flush first: a long note between two short runs used to leave `cur` open, merging runs that a rest
                # or a held note separates
                if len(cur) >= 4:
                    runs.append(cur)
                cur = []
                continue
            gap_i = ns[i]['t'] - ns[cur[-1]]['t'] if cur else 0.0
            if cur and 0.01 < gap_i <= 0.5 + 1e-6:
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
    v += _fractal_noise(rng, n, beta=beta, fc=step_beats / 3.0) * vs * 0.6 + rng.standard_normal(n) * vs * 0.6
    vtc = float(c.get('vel_time_couple', 0.0))
    if vtc > 0 and is_drum and vs:
        # on percussion the amplitude and the microtiming share their long-range correlation (Rasanen et al. 2015)
        v += vtc * vs * np.clip(frac, -2.0, 2.0)

    # automatic chord voicing (Goebl 2001): a score that wrote one velocity for every chord tone gets the top voice
    # lifted, the inner voices tucked back and the bass anchored. Uses the input velocities, so shaped scores are left alone.
    if base_role in ('chord', 'pad', 'arp', 'texture'):
        for cl in clusters:
            if len(cl) < 3 or v_in[cl].std() >= 1.5:
                continue
            order = sorted(cl, key=lambda j: ns[j]['p'])
            v[order[0]] += 2.0
            for j in order[1:-1]:
                v[j] -= 3.0
            v[order[-1]] += 5.0

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
    if is_drum:
        # a fixed push per piece is only right at one tempo and one subdivision: scale both
        tempo_scale = (96.0 / max(40.0, float(bpm))) ** float(c.get('push_tempo_power', 0.4))
        uniq = np.unique(np.round(t_beats, 3))
        dense = bool(len(uniq) > 1 and np.min(np.diff(uniq)) < 0.26)
        subdiv = float(c.get('subdiv_push_ms', 0.0)) if dense else 0.0
        push = np.array([DRUM_PUSH.get(int(pp), 0.0) * tempo_scale for pp in p]) / 1000.0
        push = push + (subdiv / 1000.0 if subdiv else 0.0)
        start = start + push
    dur = (t1 - t0) * (rd['gate'] + float(c.get('gate_bias', 0.0))) * (1 + rng.normal(0, 0.04, n))
    if not is_drum:
        # an accent is also a little longer; a soft note a little shorter (velocity-duration coupling)
        dur = dur * (1.0 + float(c.get('vel_dur', 0.0)) * (np.clip(v, 1, 127) - 90.0) / 64.0)
    if base_role in FIG + ('counter',):                           # a phrase's last note breathes: held a little longer
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
            if a.get('art') == 'staccato' or b['t'] <= a['t'] + 0.05:   # staccato or a chord tone: leave alone
                continue
            if -0.001 < gap < 0.20:
                a['dur'] = (b['t'] - a['t']) + legato_overlap_ms / 1000.0
    return sorted(ev, key=lambda e_: e_['t'])


def _drum_run(run, v, ns, start_boost, rng):
    """A run of rapid same-pitch hits with no dynamic contour is a machine gun: accent alternately."""
    if not pa._machine_run(v[run]):
        return
    m = len(run)
    for pos, i in enumerate(run):
        v[i] += 5.0 if pos % 2 == 0 else -5.0
        if v[run[-1]] > v[run[0]]:                 # an ascending build gets an exponential arch
            v[i] += 4.0 * ((pos / max(m - 1, 1)) ** 1.6 - 0.5)
        start_boost[i] += rng.uniform(-0.003, 0.003)


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
