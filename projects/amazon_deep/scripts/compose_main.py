#!/usr/bin/env python3
"""compose_main.py - writes scores/into_the_green_dark_score.json for "Into the Green Dark".

Only notes and choices live here: which pitch, which beat, which preset. Every sound, level, room and placement is in
presets/ (instruments, environments, sfx, calls, spaces, mix); the intent is in direction/.

Time: beats of a 4/4 bar, 1-based bars. 40 bars, 100 BPM base with a tempo map (a slow start, a push in the chase, a
broad slowing into the clearing). Key: D minor, using the Amazonian pentatonic (D F G A C) as the melodic material
(knowledgebase/cultures/brazil-turkic-mongolian.md, id brazil-turkic-mongolian, section 6.3).

    bars  1- 8  canopy        a flute call over a D pedal; a walker's first steps; the forest is alive
    bars  9-16  closing_in    ostinato and heartbeat; the snap (bar 13 beat 3) and the silence after it; the jaguar
    bars 17-24  the_watcher   the ostinato doubles in speed; monkeys, thunder, the walker starts to run
    bars 25-32  the_chase     tutti; the key moves up a minor third at bar 29; everything stops on bar 32 beat 4
    bars 33-36  the_clearing  the canopy opens: the relative major, chorus, harp, a river
    bars 37-40  not_alone     distant drums answer from all around; a second set of footsteps; D with no third
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'scores', 'into_the_green_dark_score.json')
rng = np.random.default_rng(2026)

BB = 4
TOTAL_BARS = 40


def B(bar, beat=0.0):
    """Absolute beat of a 1-based bar and a beat inside it."""
    return (bar - 1) * BB + beat


# ---------------------------------------------------------------- harmony: one chord per bar (root pitch class, quality)
D, Eb, F, Gb, G, Ab, A, Bb, C, Db = 2, 3, 5, 6, 7, 8, 9, 10, 0, 1
CH = {}
for b in range(1, 13):
    CH[b] = (D, 'm')
CH[11] = (Bb, 'M')
CH[13] = CH[14] = (D, 'm')
CH[15], CH[16] = (G, 'm'), (A, 'M')
for b, c in zip(range(17, 25), [(D, 'm'), (Bb, 'M'), (F, 'M'), (C, 'M'), (G, 'm'), (Bb, 'M'), (A, 'M'), (A, 'M')]):
    CH[b] = c
for b, c in zip(range(25, 29), [(D, 'm'), (Bb, 'M'), (F, 'M'), (C, 'M')]):
    CH[b] = c
for b, c in zip(range(29, 33), [(F, 'm'), (Db, 'M'), (Ab, 'M'), (C, 'M')]):      # the twist: up a minor third
    CH[b] = c
for b, c in zip(range(33, 37), [(F, 'M'), (Db, 'M'), (Bb, 'M'), (C, 'M')]):      # the clearing: the relative major, borrowed bVI
    CH[b] = c
for b in range(37, 41):
    CH[b] = (D, 'm')


def near(pc, lo, hi):
    """The pitch of pitch class pc inside [lo, hi] (the lowest one)."""
    for p in range(lo, hi + 1):
        if p % 12 == pc:
            return p
    raise ValueError((pc, lo, hi))


def tones(bar, lo, hi):
    """Chord tones of the bar's chord inside [lo, hi], low to high."""
    root, q = CH[bar]
    third = 3 if q == 'm' else 4
    return [p for p in range(lo, hi + 1) if (p - root) % 12 in (0, third, 7)]


VEL_FLOOR = 0.42        # a played velocity never goes below this: a sampled pp sits 40 dB under its ff, which is wider than the arc declared


def N(t, d, p, v, **kw):
    v = VEL_FLOOR + (1.0 - VEL_FLOOR) * min(1.0, max(0.0, v))
    return dict(t=round(float(t), 4), d=round(float(d), 4), p=int(p), v=round(float(v), 3), **kw)


# ---------------------------------------------------------------- ostinato cells: the rhythm is kept, the pitches follow the chord
CELLS8 = [[0, 0, 7, 0, 10, 0, 7, 0], [0, 7, 0, 7, 12, 7, 10, 7], [0, 0, 0, 7, 0, 0, 10, 12], [0, 7, 0, 0, 10, 0, 12, 7]]
CELLS16 = [[0, 0, 7, 0, 0, 0, 10, 0, 0, 7, 0, 0, 12, 0, 7, 0],
           [0, 7, 0, 0, 0, 10, 0, 7, 0, 0, 7, 0, 0, 12, 10, 7],
           [0, 0, 0, 7, 0, 0, 7, 0, 0, 10, 0, 0, 7, 0, 12, 10],
           [0, 0, 7, 0, 0, 7, 0, 0, 10, 0, 0, 7, 0, 12, 0, 7]]
ACCENT16 = {0: 0.12, 3: 0.08, 6: 0.08, 8: 0.05, 10: 0.06, 12: 0.06}      # a 3+3+2 grouping inside the bar


def cell_pitch(off, q):
    if q == 'M' and off == 10:
        return 12
    return off


def ostinato(bars, grid, vel_a, vel_b, lo, hi, skip=None, drop=0.0, stop_at=None):
    """grid 8 or 16: notes per bar. Velocity ramps vel_a -> vel_b across `bars`. `skip` is a set of absolute beats left out."""
    out = []
    n = len(bars)
    for i, bar in enumerate(bars):
        root, q = CH[bar]
        base = near(root, lo, hi)
        cell = (CELLS8 if grid == 8 else CELLS16)[int(rng.integers(0, 4))]
        step = BB / grid
        for k, off in enumerate(cell):
            t = B(bar, k * step)
            if stop_at is not None and t >= stop_at:
                continue
            if skip and t in skip:
                continue
            if rng.random() < drop and k not in (0, 4):
                continue
            v = vel_a + (vel_b - vel_a) * ((i + k / len(cell)) / max(1, n))
            v += ACCENT16.get(k, 0.0) if grid == 16 else (0.08 if k in (0, 3, 6) else 0.0)
            v += rng.normal(0, 0.025)
            out.append(N(t, step * 0.82, base + cell_pitch(off, q), v))
    return out


tracks = []


def track(name, instrument, role, notes, **extra):
    tracks.append(dict(name=name, instrument=instrument, role=role, notes=notes, **extra))


SNAP = B(13, 2.0)          # beat 50: the twig
ENTRY = B(17)              # beat 64: the watcher
CHASE = B(25)              # beat 96
TWIST = B(29)              # beat 112
HUSH = B(32, 2.0)          # beat 126: the held breath before the clearing (two beats of silence)
REVEAL = B(33)             # beat 128
FINAL = B(39)              # beat 152

# ================================================================ strings
# basses: the floor
bs = [N(B(1) + 8.0 * k - (0.4 if k else 0.0), 8.4, 26, 0.34 + 0.02 * k) for k in range(4)]     # a non-looped pedal is re-struck every 8 beats
for bar in range(9, 13):
    bs.append(N(B(bar), 4.06, near(CH[bar][0], 26, 37), 0.42 + 0.03 * (bar - 9)))
bs.append(N(B(13), 2.0, 26, 0.46))
bs += [N(B(15), 3.95, near(G, 26, 37), 0.36), N(B(16), 3.95, near(A, 26, 37), 0.48)]
for bar in range(17, 32):
    v = 0.58 + 0.025 * (bar - 17)
    bs.append(N(B(bar), 4.06, near(CH[bar][0], 38 if 21 <= bar <= 31 else 26, 49 if 21 <= bar <= 31 else 37), min(0.95, v)))
bs.append(N(B(32), 2.0, near(C, 26, 37), 0.92))
bs += [N(B(33), 7.9, near(F, 26, 37), 0.5), N(B(35), 3.9, near(Bb, 26, 37), 0.52), N(B(36), 3.9, near(C, 26, 37), 0.55)]
bs += [N(B(37), 7.4, 26, 0.5), N(B(37) + 7.0, 6.4, 26, 0.5)]
track('basses', 'green_basses', 'bass', bs)

# celli: the ostinato engine
ce = ostinato(range(9, 13), 8, 0.7, 0.74, 38, 49)
ce += [N(B(13, k * 0.5), 0.42, 38 + (7 if k in (2, 3) else 0), 0.5 - 0.04 * k) for k in range(4)]      # stops dead at the snap
ce += [N(B(15, k * 0.5), 0.42, near(G, 38, 49), 0.3 + 0.01 * k) for k in range(8)]
ce += ostinato([16], 8, 0.4, 0.6, 38, 49)
ce += ostinato(range(17, 21), 8, 0.55, 0.72, 38, 49)
ce += ostinato(range(21, 25), 16, 0.62, 0.86, 38, 49)
ce += ostinato(range(25, 29), 16, 0.8, 0.95, 38, 49)
ce += ostinato(range(29, 32), 16, 0.88, 1.0, 38, 49)
ce += ostinato([32], 16, 0.95, 1.0, 38, 49, drop=0.0, stop_at=B(32, 2.0))
track('celli', 'green_celli_ostinato', 'ostinato', ce)

# violas: the offbeat layer of the chase
va = []
for bar in list(range(21, 25)) + list(range(25, 32)):
    root, q = CH[bar]
    base = near(root, 50, 62)
    pos = [2, 6, 7, 10, 14, 15] if bar >= 25 else [2, 6, 10, 14]
    for k in pos:
        va.append(N(B(bar, k * 0.25), 0.2, base + (7 if k in (7, 15) else 12 if k in (6, 14) else 0), (0.62 if bar >= 25 else 0.4) + rng.normal(0, 0.03)))
track('violas', 'green_violas_ostinato', 'arp', va)

# violins in tremolo: the shiver
vt = []
for bar, p in zip(range(9, 13), [81, 81, 86, 86]):
    vt.append(N(B(bar), 3.95, p, 0.24 + 0.03 * (bar - 9)))
vt[-1] = N(B(12), 3.95, 86, 0.34)
vt.append(N(B(13), 2.0, 86, 0.34))
vt += [N(B(15), 3.95, 82, 0.3), N(B(16), 3.95, 85, 0.45)]
for bar in range(17, 32):
    t3 = tones(bar, 74, 90)
    pick = [t3[1], t3[-1]] if len(t3) > 2 else t3
    for p in pick:
        vt.append(N(B(bar), 3.95, p, min(0.9, 0.5 + 0.02 * (bar - 17))))
vt = [n for n in vt if not (B(32) <= n['t'])] + [N(B(32), 1.9, p, 0.9) for p in tones(32, 74, 90)[1:]]
track('violins_tremolo', 'green_violins_tremolo', 'pad', vt)

# violins on a bowed sustain: the canopy at the start, the light at the end
vs = [N(0, 15.9, 81, 0.5), N(B(5), 15.9, 84, 0.52)]
for bar, ps in ((33, (69, 72)), (34, (68, 73)), (35, (74, 77)), (36, (76, 79))):
    for p in ps:
        vs.append(N(B(bar), 3.95, p, 0.5 + 0.1 * (bar - 33)))
vs += [N(B(37), 14.4, 74, 0.4), N(B(37), 14.4, 69, 0.38)]
track('violins_sustain', 'green_violins_sustain', 'pad', vs)

# ================================================================ winds
motif = [(62, 1.4), (65, 0.9), (67, 0.9), (69, 1.4), (72, 3.5)]            # D F G A C: the icaro pentatonic
FL_UP, FL_DOWN = [0.3, 0.45, 0.6, 0.78, 0.95], [0.9, 0.72, 0.55, 0.42, 0.3]
fl = []
for i, (p, d) in enumerate(motif):
    fl.append(N(B(3) + [0, 1.5, 2.5, 3.5, 5.0][i], d, p, FL_UP[i], art='legato'))
inv = [(72, 1.4), (69, 0.9), (67, 0.9), (65, 1.4), (62, 3.5)]
for i, (p, d) in enumerate(inv):
    fl.append(N(B(7) + [0, 1.5, 2.5, 3.5, 5.0][i], d, p, FL_DOWN[i], art='legato'))
fl += [N(B(10), 2.5, 69, 0.5, art='legato'), N(B(12), 3.2, 72, 0.85, art='legato')]
fl += [N(B(14), 6.0, 62, 0.25, art='legato')]                                 # one breath in the silence
for k, (p, v) in enumerate(((69, 0.55), (72, 0.8), (69, 0.5))):
    fl.append(N(B(19) + k * 0.5, 0.4, p, v, art='legato'))
for k, (p, v) in enumerate(((74, 0.5), (77, 0.75), (74, 0.6), (72, 0.9))):
    fl.append(N(B(22, 2) + k * 0.5, 0.4, p, v, art='legato'))
fl += [N(B(34), 3.5, 77, 0.7, art='legato'), N(B(35), 3.5, 81, 0.55, art='legato')]
for i, (p, d, v) in enumerate([(62, 2.0, 0.3), (65, 2.0, 0.55), (67, 2.0, 0.4), (69, 2.0, 0.7)]):
    fl.append(N(B(37) + i * 2.0 + (0.1 if i else 0), d, p, v, art='legato'))
fl.append(N(B(39), 6.8, 72, 0.35, art='legato'))                              # ends on C, the flat seventh: no resolution
track('flute', 'green_alto_flute', 'melody', fl)

bc = [N(B(15) + o, 0.6, p, 0.34 + 0.1 * i % 0.4) for i, (o, p) in enumerate(zip((0.0, 0.75, 1.5, 2.5, 3.25), (50, 51, 50, 49, 50)))]
bc += [N(B(19) + o, 0.6, p, 0.5 + 0.08 * i) for i, (o, p) in enumerate(zip((0.5, 1.25, 2.0, 3.0), (50, 51, 53, 51)))]
bc += [N(B(23) + o, 0.6, p, 0.45 + 0.1 * (i % 3)) for i, (o, p) in enumerate(zip((0.0, 0.75, 1.5, 2.25, 3.25), (45, 46, 45, 44, 45)))]
bc += [N(B(38, 0.5), 1.8, 50, 0.3), N(B(38, 2.5), 1.8, 51, 0.5), N(B(39, 0.5), 2.8, 50, 0.35)]
track('bass_clarinet', 'green_bass_clarinet', 'counter', bc)

# ================================================================ brass
hn = []
for bar in range(17, 25):
    late = 0.5 if bar % 2 == 0 else 0.0
    hn.append(N(B(bar) + late, 3.4 - late * 0.0, near((CH[bar][0] + 7) % 12, 53, 67), 0.4 + 0.07 * ((bar - 17) % 4) + 0.02 * (bar - 17)))
theme = {25: [(62, 1.5), (69, 2.5)], 26: [(74, 1.5), (72, 0.5), (70, 2.0)], 27: [(69, 1.5), (72, 2.5)], 28: [(67, 1.5), (64, 2.4)],
         29: [(65, 1.5), (72, 2.5)], 30: [(77, 1.5), (75, 0.5), (73, 2.0)], 31: [(72, 1.5), (75, 2.5)], 32: [(67, 1.9)],
         33: [(65, 1.5), (72, 2.5)], 34: [(68, 1.5), (73, 2.5)], 35: [(74, 1.5), (77, 2.5)], 36: [(76, 3.9)],
         37: [(69, 3.9)], 38: [(65, 3.9)], 39: [(62, 3.9)]}
for bar, seq in theme.items():
    t0 = B(bar)
    for p, d in seq:
        v = 0.7 + 0.012 * (bar - 25) if bar < 33 else (0.6 + 0.07 * (bar - 33) if bar < 37 else 0.4 - 0.05 * (bar - 37))
        hn.append(N(t0, d * 0.98, p, v))
        t0 += d
track('horns', 'green_horns', 'melody', hn)

PATTERNS_TU = [((0, 2.4), (2.5, 1.4)), ((0, 1.4), (1.5, 2.3)), ((0.5, 1.9), (2.5, 1.4)), ((0, 3.4),), ((1.0, 2.8),)]
tb_sus = [N(ENTRY, 6.0, p, 0.9) for p in (50, 57, 62)] + [N(CHASE, 8.0, p, 1.0) for p in (50, 57, 62, 65)]
tb_sus += [N(TWIST, 6.0, p, 1.0) for p in (53, 56, 60, 65)] + [N(FINAL, 6.8, p, 0.5) for p in (50, 57, 62)]    # Dm9 without the third
tb = [N(B(21, 0), 1.5, p, 0.72) for p in (55, 62)]
PATTERNS = [((0, 1.4), (1.5, 1.4), (3.0, 0.9)), ((0, 1.9), (2.0, 0.9), (3.5, 0.45)), ((0, 1.4), (1.5, 0.9), (2.5, 1.4)),
            ((0, 0.9), (1.0, 0.9), (2.0, 1.9)), ((0, 1.4), (3.0, 0.9)), ((0, 2.9), (3.0, 0.9))]
STAB_BARS = {26: ((0, 1.9), (2.0, 0.9)), 31: ((0, 1.4), (3.0, 0.9))}      # few stabs: each one is an event, not a pulse
for bar, pat in STAB_BARS.items():
    root, q = CH[bar]
    r = near(root, 48, 59)
    for off, d in pat:
        if bar == 32 and off > 0:
            continue
        if bar in (25, 29) and off == 0:
            continue                                              # the braam on the downbeat belongs to the sustain track
        vv = 1.0 if off == 0 else 0.5 + 0.25 * float(rng.random())
        tb += [N(B(bar, off), d, r, vv), N(B(bar, off), d, r + 7, vv - 0.05)]
track('trombones', 'green_trombones', 'chord', tb)
track('trombones_sus', 'green_trombones_sus', 'pad', tb_sus)

tu = [N(ENTRY, 6.0, 38, 0.8), N(CHASE, 8.0, 38, 0.95), N(TWIST, 6.0, 41, 0.95), N(FINAL, 4.6, 38, 0.5)]
tu.append(N(B(27), 3.4, near(CH[27][0], 30, 43), 0.8))                      # one more blow in the chase; the tuba owns only the structural moments
track('tuba', 'green_tuba', 'bass', tu)

# ================================================================ percussion
def tp(bar, beat, d, v, root=None):
    return N(B(bar, beat), d, near(CH[bar][0] if root is None else root, 36, 47), v)       # the pitched range of the patch


ti = []
for bar in (9, 11):
    ti += [tp(bar, 0, 0.4, 0.42), tp(bar, 0.75, 0.4, 0.28)]
ti += [tp(13, 0, 0.4, 0.46), tp(13, 0.75, 0.4, 0.32)]                          # the last heartbeat before the snap
ti += [N(B(14, 2), 0.5, 38, 0.3)]
ti += [tp(15, 0, 0.4, 0.4), tp(15, 0.75, 0.4, 0.28), tp(15, 2, 0.4, 0.4), tp(15, 2.75, 0.4, 0.28)]
ti += [tp(16, b, 0.4, 0.4 + 0.1 * b) for b in range(3)] + [N(B(16, 3), 1.0, 86, 0.5)]      # a crescendo roll into the entry
for bar in range(17, 21):
    ti += [tp(bar, b, 0.4, v) for b, v in zip(range(4), (0.78, 0.6, 0.72, 0.58))]
for bar in range(21, 25):
    ramp = 0.5 + 0.06 * (bar - 21)
    ti += [tp(bar, k * 0.5, 0.3, ramp + 0.3 * ((k / 8.0) ** 1.6) + (0.14 if k in (0, 3, 6) else -0.03) + float(rng.normal(0, 0.03)))
           for k in range(8)]
ti += [N(B(24, 3), 1.0, 92, 0.7)]
for bar in range(25, 32):
    for off, v in ((0, 1.0), (1.5, 0.82), (3, 0.9)):
        ti.append(tp(bar, off, 0.4, v))
    if bar % 2 == 0:
        ti += [tp(bar, 3.25 + 0.25 * k, 0.2, 0.62 + 0.06 * k) for k in range(3)]
ti += [tp(31, 3.5, 0.4, 0.95)]                                                    # the last blow before the held breath
ti += [N(B(33), 4.06, 65, 0.4), N(B(34), 4.06, 62, 0.42), N(B(35), 4.06, 65, 0.44), N(B(36), 4.06, 68, 0.46)]    # rolls through the clearing
ti += [tp(37, 0, 0.4, 0.3), tp(37, 0.75, 0.4, 0.2), tp(39, 0, 0.6, 0.95), tp(40, 0.5, 0.6, 0.45)]
track('timpani', 'green_timpani', 'drum', ti)

bd = [N(b, 1.0, 48, v) for b, v in ((ENTRY, 1.0), (CHASE, 1.0), (TWIST, 1.0), (FINAL, 0.8))]
BD_BARS = {22: ((0, 0.6), (2.5, 0.45)), 24: ((0, 0.7), (1.5, 0.5), (3.0, 0.55)), 26: ((1.5, 0.8), (3.0, 0.6)), 27: ((0, 0.85), (2.5, 0.6)),
           28: ((0, 0.8), (2.0, 0.5), (3.5, 0.7)), 30: ((1.5, 0.75), (3.0, 0.8)), 31: ((0, 0.9), (1.5, 0.55), (2.5, 0.7), (3.5, 0.85))}
for bar, hits in BD_BARS.items():
    bd += [N(B(bar, o), 1.0, 48, v) for o, v in hits]
track('bass_drum', 'green_bass_drum', 'drum', bd)

cy = [N(B(16, 2), 4.0, 50, 0.7), N(B(24, 2), 4.0, 50, 0.6), N(B(31, 0), 4.0, 50, 0.75), N(TWIST, 3.0, 57, 0.8), N(REVEAL, 5.0, 59, 0.45)]
cy += [N(CHASE, 3.0, 55, 0.7), N(FINAL, 6.0, 60, 0.5)]
track('cymbals', 'green_cymbals', 'texture', cy)

# distant drums: 3+3+2 call and answer, from two sides, nearer and louder at the end
dl, dr = [], []
POOL_L = [(0, 1.5, 3.0), (0, 1.5, 2.5), (0.5, 2.0, 3.0), (0, 3.0), (1.0, 2.5, 3.5), (0, 0.75, 2.0, 3.0)]
POOL_R = [(0.5, 2.0, 3.5), (1.0, 2.5), (0.5, 1.25, 2.0, 2.75, 3.5), (0, 1.5, 3.5), (0.75, 2.25), (0.5, 1.5, 2.25, 3.25)]


def conga(pool, bar, vel, notes):
    pat = pool[int(rng.integers(0, len(pool)))]
    for i, o in enumerate(pat):
        key = (48, 50, 53)[int(rng.choice([0, 1, 2], p=[0.5, 0.35, 0.15]))]
        notes.append(N(B(bar, o), 0.4, key, vel * (1.0 if i == 0 else 0.62 + 0.3 * float(rng.random()))))


for bar, v in ((22, 0.3), (24, 0.34)):
    conga(POOL_L, bar, v, dl)
for bar in (33, 35):
    conga(POOL_L, bar, 0.36, dl)
for bar in (34, 36):
    conga(POOL_R, bar, 0.33, dr)
for bar in range(37, 41):
    k = bar - 36
    conga(POOL_L, bar, min(0.9, 0.36 + 0.1 * k), dl)
    conga(POOL_R, bar, min(0.9, 0.3 + 0.1 * k), dr)
track('drums_left', 'green_drums_left', 'drum', dl)
track('drums_right', 'green_drums_right', 'drum', dr)

# ================================================================ chorus and harp
ch = []
for bar in range(25, 33):
    t3 = tones(bar, 55, 76)
    for p in (t3[0], t3[2], t3[-1]):
        if bar == 32:
            ch.append(N(B(bar), 1.9, p, 0.7))
        else:
            ch.append(N(B(bar), 3.95, p, 0.55 + 0.02 * (bar - 25)))
for bar, ps, v in ((33, (65, 69, 72, 77), 0.5), (34, (68, 73, 77), 0.58), (35, (70, 74, 77), 0.68), (36, (67, 72, 76), 0.78)):
    ch += [N(B(bar), 3.95, p, v) for p in ps]
ch += [N(B(37), 14.4, p, 0.4) for p in (57, 62, 69)]                         # D and A, no third
track('choir', 'green_choir', 'pad', ch)

hp = []
pent = [74, 77, 79, 81, 84]
for beat in (14.0, 21.5, 29.5, 34.0, 38.5, 43.5, 46.5):
    hp.append(N(beat, 1.2, int(rng.choice(pent)), 0.32 + rng.normal(0, 0.03)))
hp += [N(B(14, 3), 1.2, 79, 0.34)]
def run(start, pitches, first_gap, last_gap, d, v0, dv):
    """A harp run that speeds up (or slows) from first_gap to last_gap beats between notes, with a little unevenness: a
    hand does not tick like a clock."""
    out, t = [], start
    for k, p in enumerate(pitches):
        out.append(N(t, d, p, v0 + dv * k))
        gap = first_gap + (last_gap - first_gap) * k / max(1, len(pitches) - 1)
        t += gap * float(1.0 + rng.normal(0, 0.06))
    return out


hp += run(B(23), [57, 60, 63, 66, 69, 72, 75, 78], 0.62, 0.34, 0.45, 0.4, 0.04)
hp += run(B(24), [69, 72, 75, 78, 81, 84, 87, 90], 0.55, 0.28, 0.45, 0.55, 0.04)
hp += run(B(33), [53, 60, 65, 69, 72, 77, 81, 84], 0.42, 0.64, 0.9, 0.5, 0.02)
hp += run(B(35), [58, 65, 70, 74, 77, 82, 86, 89], 0.44, 0.7, 0.9, 0.52, 0.02)
hp += [N(B(39, 1), 0.8, 79, 0.8), N(B(40, 1), 0.6, 81, 0.8)]
track('harp', 'green_harp', 'arp', hp)

# ================================================================ the forest: places and animals
def env(name, preset, t0, d, role='environment', **extra):
    track(name, f'env:{preset}', role, [dict(t=float(t0), d=float(d), p=60, v=1.0)], **extra)


env('canopy', 'green_canopy_alive', 0.0, SNAP)
env('hush', 'green_hush', SNAP, 16.0, fade_in_s=0.05, fade_out_s=3.0)
env('rain_heavy', 'green_rain_heavy', ENTRY - 2.0, REVEAL - ENTRY + 2.0, fade_in_s=4.0, fade_out_s=1.5)
env('rain_clearing', 'green_rain_clearing', REVEAL - 0.5, 166.0 - (REVEAL - 0.5), fade_in_s=2.5, fade_out_s=4.0)
env('river', 'green_river_far', B(21), B(36) - B(21), fade_in_s=8.0, fade_out_s=5.0)
env('monkeys', 'green_monkeys', B(19), 18.0, fade_in_s=1.0, fade_out_s=2.0)


def jag(name, t0, d, az, el, dist, keys=None, **kw):
    sp = dict(azimuth=az, elevation=el, distance=dist, kind='spot', binaural=True)
    if keys:
        sp['trajectory'] = dict(spatial_role='mover', doppler_strength=1.0, keyframes=keys)
    track(name, 'env:green_jaguar', 'environment', [dict(t=float(t0), d=float(d), p=60, v=1.0)], spatial=sp, fade_in_s=0.04, fade_out_s=0.15, **kw)


jag('jaguar_far', B(15, 2.5), 5.4, 150, 0, 16.0)
jag('jaguar_near', B(22, 2), 8.0, -140, 0, 6.0,
    keys=[dict(bar=22.5, azimuth=-140, distance=6.0), dict(bar=24.5, azimuth=-75, distance=3.6), dict(bar=24.9, azimuth=-60, distance=3.0)])
jag('jaguar_chase', B(27, 1), 14.0, -90, 0, 5.0,
    keys=[dict(bar=27.2, azimuth=-90, distance=5.0), dict(bar=29.0, azimuth=0, distance=2.6), dict(bar=31.0, azimuth=95, distance=5.5)])
jag('jaguar_eyes', B(39, 2), 6.0, 4, 0, 2.6)

# ================================================================ the walker: one note per step
def steps(name, preset, times, az, dist, vel=0.7, jitter=0.03, **extra):
    notes = [dict(t=round(float(t + rng.normal(0, jitter)), 4), d=0.6, p=60, v=round(float(np.clip(vel + rng.normal(0, 0.06), 0.3, 1.0)), 3))
             for t in times]
    track(name, f'sfx:{preset}', 'fx', notes, spatial=dict(azimuth=az, elevation=-15, distance=dist, kind='spot', binaural=True), **extra)


walk = [b for b in range(16, 50) if b not in (27, 31, 35, 39)]        # he stops four times to listen
l_steps = [b for i, b in enumerate(walk) if i % 2 == 0]
r_steps = [b for i, b in enumerate(walk) if i % 2 == 1]
cautious = [58, 60, 62, 63]
pursued = list(range(64, 80))
quick = [80 + k * 0.75 for k in range(11)]
run = [88.0 + k * (2.0 / 3.0) for k in range(int((126.0 - 88.0) / (2.0 / 3.0)) + 1)]
calm = [132.0, 134.5, 137.0, 139.5, 142.0, 144.5, 147.0]
walk_all = {'left': [], 'right': []}
for i, b in enumerate(l_steps + [58, 62] + pursued[0::2] + quick[0::2]):
    walk_all['left'].append(b)
for i, b in enumerate(r_steps + [60, 63] + pursued[1::2] + quick[1::2]):
    walk_all['right'].append(b)
steps('steps_left', 'green_step_leaf', sorted(walk_all['left'] + calm[0::2]), -8, 2.6, 0.7)
steps('steps_right', 'green_step_leaf', sorted(walk_all['right'] + calm[1::2]), 8, 2.6, 0.7)
steps('run_left', 'green_step_mud', run[0::2], -14, 2.4, 0.85)
steps('run_right', 'green_step_mud', run[1::2], 14, 2.4, 0.85)
other = [146.0, 148.0, 150.0, 152.0, 153.5, 155.0]                   # after he has stopped, somebody behind him has not
steps('steps_other', 'green_step_leaf', other, 160, 9.0, 0.5, spatial_trajectory=True)
for t in tracks:
    if t['name'] == 'steps_other':
        t['spatial']['trajectory'] = dict(spatial_role='mover', doppler_strength=0.5,
                                          keyframes=[dict(bar=37.5, azimuth=160, distance=9.0), dict(bar=40.0, azimuth=140, distance=4.5)])
        del t['spatial_trajectory']

# ================================================================ single sounds: the snap, the blade, the sky, the heart
track('twig_snap', 'sfx:green_twig_snap', 'fx', [dict(t=SNAP, d=2.6, p=60, v=1.0)],
      spatial=dict(azimuth=-22, elevation=0, distance=2.2, kind='spot', binaural=True))
track('vine_chop', 'sfx:green_vine_chop', 'fx', [dict(t=27.0, d=2.0, p=60, v=0.6), dict(t=39.0, d=2.0, p=60, v=0.65),
                                                  dict(t=108.5, d=2.0, p=60, v=0.7)],
      spatial=dict(azimuth=18, elevation=0, distance=2.0, kind='spot', binaural=True))
track('thunder', 'sfx:green_thunder', 'fx', [dict(t=B(21, 3), d=11.0, p=60, v=0.32), dict(t=TWIST - 0.8, d=11.0, p=60, v=0.4)],
      spatial=dict(azimuth=-30, elevation=35, distance=24.0, kind='bed'))
track('heartbeat', 'sfx:heartbeat', 'fx', [dict(t=B(14) + k * 1.4, d=1.2, p=60, v=0.3 + 0.012 * k) for k in range(8)]
      + [dict(t=B(37) + k * 2.8, d=1.2, p=60, v=0.27 - 0.03 * k) for k in range(5)],
      spatial=dict(azimuth=0, elevation=-5, distance=0.8, kind='spot', binaural=True))
track('risers', 'sfx:riser', 'fx', [dict(t=ENTRY - 4.0, d=4.0, p=60, v=0.5), dict(t=CHASE - 4.0, d=4.0, p=60, v=0.65),
                                    dict(t=TWIST - 3.0, d=3.0, p=60, v=0.7)],
      spatial=dict(azimuth=0, elevation=20, distance=8.0, kind='bed'))

# sub-bass effects carry energy below 25 Hz that shows as a slow drift in the stem gate: remove it at the track (measured, stem.dc)
for _t in tracks:
    if _t['name'] in ('heartbeat', 'thunder', 'vine_chop'):
        _t['dc_hp_hz'] = 25.0

# ================================================================ the score
dynamics = [[0, 0.45], [16, 0.5], [32, 0.55], [48, 0.58], [49.5, 0.6], [50, 0.4], [56, 0.45], [62, 0.6], [64, 0.7], [80, 0.76],
            [92, 0.85], [96, 0.95], [112, 1.0], [126, 0.96], [127, 0.4], [128, 0.65], [140, 0.85], [144, 0.6], [152, 0.5], [160, 0.4]]
sections = [dict(name='canopy', start_bar=1, end_bar=8, energy=0.5), dict(name='closing_in', start_bar=9, end_bar=16, energy=0.55),
            dict(name='the_watcher', start_bar=17, end_bar=24, energy=0.75), dict(name='the_chase', start_bar=25, end_bar=32, energy=1.0),
            dict(name='the_clearing', start_bar=33, end_bar=36, energy=0.8), dict(name='not_alone', start_bar=37, end_bar=40, energy=0.55)]
score = dict(
    title='Into the Green Dark', bpm=100, ts=[4, 4], seed=2026, humanize='natural', key='D', mode='minor',
    tempo_points=[[0, 96], [56, 100], [88, 102], [96, 106], [120, 108], [128, 108], [132, 90], [152, 88], [160, 78]],
    dynamics=dynamics, ritard=0.12, ritard_beats=8, space='green_dark_room', mix_preset='into_the_green_dark_mix',
    output_targets=['stereo', 'mono', 'immersive_5_1', 'immersive_7_1_4', 'ambix', 'adm_bw64'],
    master=dict(lufs=-16.0, true_peak=-1.6, tone='neutral', fade_out=2.5),
    piece_type='cinematic', focus='melody',
    intent=dict(emotions=['adventure', 'tense', 'wonder'], registers=['cinematic', 'natural'], scenes=['dread', 'chase', 'reveal'],
                tensions=['ostinato', 'pedal', 'silence_before', 'unresolved_dominant'], avoid=['joyful', 'playful']),
    mix_intent=dict(hero='horns', leave_free_hz=[700, 2600]),
    plan=dict(sections=sections, ending=dict(fade_out=2.5)),
    tracks=tracks,
    mix=dict(tracks={}),
)
import sys
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'scripts'))
import humanize as hz
TM = hz.tempo_map_for(score, seed=score['seed'])          # the map the renderer will play, rubato and ritardando included
for sec in sections:
    sec['start_s'] = round(float(TM.sec((sec['start_bar'] - 1) * BB)), 3)
    sec['end_s'] = round(float(TM.sec(sec['end_bar'] * BB)), 3)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(score, f, indent=1)
print(f'wrote {os.path.relpath(OUT, os.getcwd())}: {len(tracks)} tracks, {sum(len(t["notes"]) for t in tracks)} notes')

if __name__ == '__main__':
    tm = TM
    for name, beat in (('snap', SNAP), ('watcher', ENTRY), ('chase', CHASE), ('twist', TWIST), ('held breath', HUSH), ('reveal', REVEAL),
                       ('final', FINAL), ('end', 160)):
        print(f'  {name:12s} beat {beat:6.1f}  {float(tm.sec(beat)):6.2f} s')
    for s in sections:
        print(f'  section {s["name"]:14s} {float(tm.sec((s["start_bar"] - 1) * 4)):6.2f} - {float(tm.sec(s["end_bar"] * 4)):6.2f} s')
