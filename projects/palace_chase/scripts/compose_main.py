#!/usr/bin/env python3
"""compose_main.py - writes scores/the_mayan_palace_score.json for "The Mayan Palace".

Only notes and choices live here: which pitch, which beat, which preset. Every sound, level, room and placement is in
presets/ (instruments, environments, sfx, calls, spaces, mix); the intent is in direction/.

A story in seven sections (4/4, bars 1-75, 1-based):

    bars  1- 8  the_entry          an explorer walks into a stone palace; wonder under a low pedal; a flute asks a question
    bars  9-17  the_relic_chamber  the relic is found; the question is answered by a bass clarinet; a harp touches it; the lid is opened
    bars 18-25  the_opening        the evil wakes: choir cluster, braam, the motif in the horns, a door shuts, a held breath
    bars 26-41  the_corridors      the chase through the palace: a pulse that never stops, a heavy pursuer behind, the exit collapses
    bars 42-57  the_forest         the chase through the forest: leaves, branches, a stumble, the pursuer breaks the trees
    bars 58-69  the_escape         the hero turns the curse back: D minor becomes D major, the hero theme, a hit, a release
    bars 70-75  the_aftermath      the forest at night, calm; the flute's question is answered and falls home to D

Themes: the relic motif is D Eb D A G F (a flat second that returns, a leap of a fifth, then a falling step): it is
innocent in the flute, hollow in the bass clarinet, a threat in the horns, and in the escape it is overruled by the hero
theme (D A Bb C D: a rising fifth and a climb), which is its own shape. Pressure carriers: a pulse that does not stop
from bar 26 to bar 69, low brass and sub weight at the turning points, constant percussion, a rising line in the forest.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'scores', 'the_mayan_palace_score.json')
rng = np.random.default_rng(1511)

BB = 4
D, Eb, F, Fs, G, Ab, A, Bb, B_, C = 2, 3, 5, 6, 7, 8, 9, 10, 11, 0


def B(bar, beat=0.0):
    """Absolute beat of a 1-based bar and a beat inside it."""
    return (bar - 1) * BB + beat


S_ENTRY, S_CHAMBER, S_OPEN, S_CORR, S_FOREST, S_ESCAPE, S_AFTER, S_END = 1, 9, 18, 26, 42, 58, 70, 76

CH = {}
for b in range(1, 9):
    CH[b] = (D, 'm')
for b, c in zip(range(9, 18), [(D, 'm'), (Bb, 'M'), (D, 'm'), (C, 'M'), (D, 'm'), (Eb, 'M'), (D, 'm'), (Bb, 'M'), (D, 'm')]):
    CH[b] = c
for b, c in zip(range(18, 26), [(D, 'm'), (Eb, 'M'), (D, 'm'), (Eb, 'M'), (Bb, 'M'), (Eb, 'M'), (D, 'm'), (D, 'm')]):
    CH[b] = c
for b, c in zip(range(26, 42), [(D, 'm'), (Eb, 'M'), (C, 'M'), (D, 'm')] * 4):
    CH[b] = c
for b, c in zip(range(42, 58), [(Bb, 'M'), (C, 'M'), (D, 'm'), (Eb, 'M')] * 4):
    CH[b] = c
for b, c in zip(range(58, 62), [(D, 'm'), (Eb, 'M'), (D, 'm'), (C, 'M')]):
    CH[b] = c
for b, c in zip(range(62, 70), [(D, 'M'), (G, 'M'), (A, 'M'), (D, 'M')] * 2):
    CH[b] = c
for b in range(70, 76):
    CH[b] = (D, 'M')


def near(pc, lo, hi):
    for p in range(lo, hi + 1):
        if p % 12 == pc:
            return p
    raise ValueError((pc, lo, hi))


VEL_FLOOR = 0.42        # a sampled pp sits far under its ff; a played velocity never goes below this


def N(t, d, p, v, **kw):
    v = VEL_FLOOR + (1.0 - VEL_FLOOR) * min(1.0, max(0.0, v))
    return dict(t=round(float(t), 4), d=round(float(d), 4), p=int(p), v=round(float(v), 3), **kw)


tracks = []


def track(name, instrument, role, notes, **extra):
    tracks.append(dict(name=name, instrument=instrument, role=role, notes=notes, **extra))


# ---------------------------------------------------------------- the relic motif and the hero theme
MOTIF = [(0, 1.5), (1, 0.5), (0, 1.0), (7, 2.0), (5, 1.0), (3, 2.0)]        # D Eb D A G F: 8 beats
HERO = [(0, 1.5), (7, 0.5), (10, 1.0), (12, 1.5), (14, 0.5), (12, 1.0), (10, 1.0), (7, 1.0)]       # D A Bb C D... 8 beats, a rising fifth and a climb


def phrase(shape, t0, base, vel, scale=1.0, art=0.96, vstep=0.0, upto=None):
    out, t = [], t0
    for k, (iv, d) in enumerate(shape):
        if upto is not None and k >= upto:
            break
        out.append(N(t, d * scale * art, base + iv, vel + vstep * k))
        t += d * scale
    return out


# ---------------------------------------------------------------- ostinato cells (offset 1 is the flat second; 4 the major third)
CELLS_MIN = [[0, 0, 1, 0, 0, 0, 7, 0, 0, 1, 0, 0, 12, 0, 7, 0],
             [0, 1, 0, 0, 0, 7, 0, 1, 0, 0, 7, 0, 0, 12, 10, 7],
             [0, 0, 0, 1, 0, 0, 7, 0, 0, 10, 0, 0, 1, 0, 12, 7],
             [0, 0, 1, 0, 0, 7, 0, 0, 10, 0, 0, 1, 0, 12, 0, 7]]
CELLS_MAJ = [[0, 0, 4, 0, 0, 0, 7, 0, 0, 4, 0, 0, 12, 0, 7, 0],
             [0, 4, 0, 0, 0, 7, 0, 4, 0, 0, 7, 0, 0, 12, 9, 7]]
CELLS8 = [[0, 0, 1, 0, 7, 0, 1, 0], [0, 7, 0, 1, 0, 7, 10, 7], [0, 0, 0, 1, 0, 0, 7, 12], [0, 1, 0, 0, 7, 0, 12, 7]]
ACCENT16 = {0: 0.14, 3: 0.08, 6: 0.08, 8: 0.06, 10: 0.06, 12: 0.06}


def ostinato(bars, grid, vel_a, vel_b, lo, hi, drop=0.0, stop_at=None, cells=None):
    out, n = [], len(bars)
    for i, bar in enumerate(bars):
        root, q = CH[bar]
        base = near(root, lo, hi)
        pool = cells or (CELLS8 if grid == 8 else CELLS_MIN)
        cell = pool[int(rng.integers(0, len(pool)))]
        step = BB / grid
        for k, off in enumerate(cell):
            t = B(bar, k * step)
            if stop_at is not None and t >= stop_at:
                continue
            if rng.random() < drop and k not in (0, 4):
                continue
            v = vel_a + (vel_b - vel_a) * ((i + k / len(cell)) / max(1, n))
            v += ACCENT16.get(k, 0.0) if grid == 16 else (0.08 if k in (0, 3, 6) else 0.0)
            v += rng.normal(0, 0.025)
            out.append(N(t, step * 0.82, base + off, v))
    return out


HELD = B(25, 0.0)                    # everything stops for a bar
BRAAM1 = B(S_OPEN)                   # the evil wakes
SHUT = B(22, 2.0)                    # a door shuts behind the hero
CORR_HIT = B(S_CORR)                 # the chase starts
COLLAPSE = B(40, 2.0)                # the exit falls in
FOREST_HIT = B(S_FOREST)
POWER = B(62)                        # the hero turns the curse: D minor -> D major
CUT = B(66, 0.0)                     # the last hit lands; a beat of nothing
LAST = B(S_END)

# ================================================================ strings
bs = [N(B(1), 15.9, 26, 0.7), N(B(5), 15.9, 26, 0.72)]                                   # the D pedal, re-struck every 16 beats
bs += [N(B(9), 15.9, 26, 0.75), N(B(13), 15.9, 26, 0.78), N(B(17), 4.0, 26, 0.8)]
bs += [N(B(bar), 4.0, near(CH[bar][0], 26, 37), 0.85 + 0.015 * (bar - 18)) for bar in range(18, 25)]
bs += [N(B(bar), 4.06, near(CH[bar][0], 26, 37), 0.88) for bar in range(26, 62)]
bs += [N(B(bar), 4.06, near(CH[bar][0], 26, 37), 0.95) for bar in range(62, 66)]
bs += [N(B(66), 15.9, 26, 0.8), N(B(70), 15.9, 26, 0.7), N(B(74), 8.0, 26, 0.65)]          # release: one long D
track('basses', 'mayan_basses', 'bass', bs)

ce = ostinato(range(13, 17), 8, 0.68, 0.78, 38, 49, drop=0.3)
ce += ostinato(range(18, 25), 8, 0.78, 0.9, 38, 49)
ce += ostinato(range(26, 42), 16, 0.82, 0.92, 38, 49)
ce += ostinato(range(42, 58), 16, 0.95, 1.0, 38, 49)
ce += ostinato(range(58, 62), 16, 0.95, 1.0, 38, 49)
ce += ostinato(range(62, 65), 16, 0.95, 1.0, 38, 49, cells=CELLS_MAJ)
ce += ostinato([65], 16, 1.0, 1.0, 38, 49, cells=CELLS_MAJ, stop_at=CUT)
track('celli', 'mayan_celli_ostinato', 'ostinato', ce)

va = []
for bar in list(range(30, 42)) + list(range(42, 62)):
    root, q = CH[bar]
    base = near(root, 50, 62)
    pos = [2, 6, 7, 10, 14, 15] if bar >= 42 else [2, 6, 10, 14]
    for k in pos:
        va.append(N(B(bar, k * 0.25), 0.2, base + (7 if k in (7, 15) else 12 if k in (6, 14) else 1 if k == 2 else 0),
                    (0.72 if bar >= 42 else 0.55) + rng.normal(0, 0.03)))
track('violas', 'mayan_violas_ostinato', 'arp', va)

vt = []
for bar in range(3, 9):                                                     # a high flat second, a shimmer in the stone
    vt.append(N(B(bar), 4.05, 86 if bar % 2 else 87, 0.65 + 0.02 * (bar - 3)))
for bar in range(13, 18):
    vt += [N(B(bar), 4.05, 86, 0.7 + 0.03 * (bar - 13)), N(B(bar), 4.05, 87, 0.68 + 0.03 * (bar - 13))]
for bar in range(18, 25):                                                   # a semitone a bar: the evil climbs
    vt += [N(B(bar), 4.05, 78 + (bar - 18), 0.78 + 0.02 * (bar - 18)), N(B(bar), 4.05, 79 + (bar - 18), 0.76 + 0.02 * (bar - 18))]
for bar in range(26, 42):
    vt += [N(B(bar), 4.05, 86, 0.85), N(B(bar), 4.05, 87, 0.83)]
for bar in range(42, 58):
    vt += [N(B(bar), 4.05, 85 + (bar % 3), 0.88), N(B(bar), 4.05, 86 + (bar % 3), 0.86)]
for bar in range(58, 62):
    vt += [N(B(bar), 4.05, 86, 0.92), N(B(bar), 4.05, 87, 0.9)]
track('violins_tremolo', 'mayan_violins_tremolo', 'pad', vt)

vs = [N(B(bar), 4.05, 74 + (bar - 42), 0.7 + 0.015 * (bar - 42)) for bar in range(42, 58)]          # the rising device in the forest
vs += [N(B(bar), 4.05, 78 + 2 * (bar - 62), 0.95) for bar in range(62, 66)]
vs += [N(B(66), 15.9, 81, 0.85), N(B(70), 15.9, 81, 0.7), N(B(74), 8.0, 81, 0.62)]               # F#5, D major add9 above: the light
track('violins_sustain', 'mayan_violins_sustain', 'pad', vs)

# ================================================================ woodwinds and harp: the human voice, and the relic's
Q = [(0, 1.5), (1, 0.5), (0, 1.0), (7, 2.0), (5, 1.0), (3, 2.0)]               # the question: the motif as it is
CURIOUS = [(0, 1.0), (2, 1.0), (3, 0.5), (7, 1.5), (5, 1.0), (7, 3.0)]          # up a fourth, stepping: D E F A G A
HOLLOW_A = [(0, 1.5), (1, 0.5), (-2, 1.0), (5, 2.0), (3, 1.0), (0, 2.0)]        # the relic answers, a step lower
HOLLOW_B = [(0, 1.0), (1, 1.0), (0, 0.5), (3, 1.5), (5, 1.0), (10, 3.0)]        # and rising, a threat in the making
ANSWER = [(0, 1.5), (2, 1.5), (5, 1.0), (7, 2.0), (5, 1.0), (2, 2.0), (0, 4.0)]   # the question, answered: it falls home to D
fl = phrase(Q, B(4), 74, 0.5, vstep=0.01)                                                              # the question, innocent
fl += phrase(Q, B(7), 74, 0.48, upto=3)
fl += phrase(CURIOUS, B(9), 79, 0.5)                                                                   # up a fourth: curious
fl += phrase(Q, B(13), 79, 0.46, scale=1.2, upto=4)
fl += phrase(ANSWER, B(70), 74, 0.5, scale=1.4) + [N(B(73, 3.0), 6.0, 81, 0.35)]                       # the answer: it ends on a held D
track('alto_flute', 'mayan_alto_flute', 'melody', fl)

bc = phrase(HOLLOW_A, B(11), 50, 0.55) + phrase(HOLLOW_B, B(15), 50, 0.6)                              # the relic answers, hollow
bc += [N(B(74), 8.0, 38, 0.35)]                                                                        # a last low D: held, not flat
track('bass_clarinet', 'mayan_bass_clarinet', 'counter', bc)

hp = [N(B(10) + 1.0 * k, 0.9, p, 0.6 + 0.03 * k) for k, p in enumerate((62, 69, 74, 77))]
hp += [N(B(14, 2.0), 1.4, 62, 0.7), N(B(15, 2.0), 1.4, 63, 0.72), N(B(16, 2.0), 1.4, 69, 0.78)]        # touching the relic
hp += [N(B(bar, 0), 1.4, near(CH[bar][0], 62, 74), 0.6) for bar in range(70, 74)]
track('harp', 'mayan_harp', 'arp', hp)

# ================================================================ brass
hn = []
for bar in range(18, 25, 2):                                                                          # the motif, muted then open: the threat
    hn += phrase(MOTIF, B(bar), 55, 0.75 + 0.03 * (bar - 18), scale=1.0, art=1.1)
for bar in range(30, 42, 4):
    hn += phrase(MOTIF, B(bar), 55, 0.85, scale=1.0, art=1.1)
    hn += phrase(MOTIF, B(bar + 2), 62, 0.9, scale=1.0, art=1.1)
for bar in range(46, 58, 4):
    hn += phrase(MOTIF, B(bar), 59, 0.92, scale=1.0, art=1.1)
    hn += phrase(MOTIF, B(bar + 2), 66, 0.95, scale=1.0, art=1.1)
for bar in (58, 60):
    hn += phrase(MOTIF, B(bar), 62, 0.95, scale=1.0, upto=3, art=1.1)
for k, bar in enumerate((62, 66)):                                                                    # the hero theme overrules it, in D major
    hn += phrase(HERO, B(bar), 55, 0.92, scale=1.0, art=1.1)                                           # the horns' top note is F5 (77): the lift stays inside it
    hn += phrase(HERO, B(bar + 2), 62, 0.95, scale=1.0, art=1.1)
track('horns', 'mayan_horns', 'melody', hn)

tb_sus = []
for beat, dur in ((BRAAM1, 7.0), (CORR_HIT, 7.0), (FOREST_HIT, 7.0), (B(58), 7.0)):
    tb_sus += [N(beat, dur, p, 1.0) for p in (50, 57, 62, 63)]
tb_sus += [N(POWER, 7.0, p, 1.0) for p in (50, 57, 62, 66)]                                           # D major: F# in the chord
track('trombones_sus', 'mayan_trombones_sus', 'pad', tb_sus)

tb = []
STABS = {28: ((0, 1.9), (2.5, 0.9)), 31: ((0, 1.4), (3.0, 0.9)), 34: ((0, 1.9), (2.0, 0.9)), 37: ((0, 1.4), (3.0, 0.9)), 40: ((0, 1.4), (3.0, 0.9))}
for bar in list(range(43, 58, 2)) + [59, 61]:
    STABS[bar] = ((0, 1.4), (2.5, 0.9))
for bar, pat in STABS.items():
    r = near(CH[bar][0], 48, 59)
    for off, d in pat:
        vv = 1.0 if off == 0 else 0.55 + 0.25 * float(rng.random())
        tb += [N(B(bar, off), d, r, vv), N(B(bar, off), d, r + 7, vv - 0.05)]
track('trombones', 'mayan_trombones', 'chord', tb)

tu = [N(beat, 7.0, 38, 1.0) for beat in (BRAAM1, CORR_HIT, FOREST_HIT, B(58), POWER)]
tu += [N(B(bar), 3.9, near(CH[bar][0], 30, 43), 0.85) for bar in (30, 34, 38, 46, 50, 54, 60)]
track('tuba', 'mayan_tuba', 'bass', tu)

# ================================================================ percussion
def tp(bar, beat, d, v, root=None):
    return N(B(bar, beat), d, near(CH[bar][0] if root is None else root, 36, 47), v)


ti = []
for bar in range(5, 9):                                                                              # the palace's pulse, far away
    ti.append(tp(bar, 0, 0.6, 0.3 + 0.02 * bar))
for bar in range(13, 18):
    ti += [tp(bar, 0, 0.5, 0.4 + 0.03 * (bar - 13)), tp(bar, 2, 0.5, 0.3 + 0.03 * (bar - 13))]
for bar in range(18, 25):
    ti += [tp(bar, 0, 0.4, 0.6 + 0.03 * (bar - 18)), tp(bar, 1.5, 0.4, 0.45), tp(bar, 2.5, 0.4, 0.5)]
ti += [tp(24, 2.0 + 0.25 * k, 0.2, 0.45 + 0.5 * (k / 7.0) ** 1.6 + (0.04 if k % 2 == 0 else -0.04)) for k in range(8)]
ti = [n for n in ti if not (B(24, 2.0) <= n['t'] < B(25) and n['d'] > 0.3)]
for bar in range(26, 62):                                                                            # 3+3+2 in eighths
    for k, v in ((0, 1.0), (3, 0.85), (6, 0.9)):
        ti.append(tp(bar, k * 0.5, 0.4, v))
    if bar % 2 == 0:
        ti += [tp(bar, 3.25 + 0.25 * k, 0.2, 0.62 + 0.07 * k) for k in range(3)]
for bar in range(62, 66):
    ti += [tp(bar, k * 0.5, 0.4, 1.0 if k % 2 == 0 else 0.75) for k in range(8)]
ti += [tp(66, 0, 0.6, 1.0)]
ti += [tp(70, 0, 0.8, 0.28), tp(72, 0, 0.8, 0.22)]
track('timpani', 'mayan_timpani', 'drum', ti)

bd = [N(beat, 1.0, 48, 1.0) for beat in (BRAAM1, CORR_HIT, FOREST_HIT, B(58), POWER, CUT)]
BRAAMS = {BRAAM1, CORR_HIT, FOREST_HIT, B(58), POWER, CUT}
for bar in range(20, 25):
    bd += [N(B(bar, o), 1.0, 48, v) for o, v in ((0, 0.55 + 0.04 * (bar - 20)), (2.0, 0.4)) if B(bar, o) not in BRAAMS]
for bar in range(27, 66):
    bd += [N(B(bar, o), 1.0, 48, v) for o, v in ((0, 0.9), (1.5, 0.7), (3.0, 0.8)) if B(bar, o) not in BRAAMS]
track('bass_drum', 'mayan_bass_drum', 'drum', bd)

cy = [N(beat - 4.0, 4.0, 50, 0.7) for beat in (BRAAM1, CORR_HIT, FOREST_HIT, POWER)] + [N(beat, 5.0, 59, 0.6) for beat in (BRAAM1, FOREST_HIT, POWER)]
cy += [N(CUT, 4.0, 60, 0.9)]
track('cymbals', 'mayan_cymbals', 'texture', cy)

dl, dr = [], []
POOL_L = [(0, 1.5, 3.0), (0, 1.5, 2.5), (0.5, 2.0, 3.0), (0, 3.0), (1.0, 2.5, 3.5), (0, 0.75, 2.0, 3.0)]
POOL_R = [(0.5, 2.0, 3.5), (1.0, 2.5), (0.5, 1.25, 2.0, 2.75, 3.5), (0, 1.5, 3.5), (0.75, 2.25), (0.5, 1.5, 2.25, 3.25)]


def conga(pool, bar, vel, notes):
    pat = pool[int(rng.integers(0, len(pool)))]
    for i, o in enumerate(pat):
        key = (48, 50, 53)[int(rng.choice([0, 1, 2], p=[0.5, 0.35, 0.15]))]
        notes.append(N(B(bar, o), 0.4, key, vel * (1.0 if i == 0 else 0.62 + 0.3 * float(rng.random()))))


for bar in range(28, 42):
    conga(POOL_L if bar % 2 == 0 else POOL_R, bar, min(0.9, 0.4 + 0.03 * (bar - 28)), dl if bar % 2 == 0 else dr)
for bar in range(42, 66):
    conga(POOL_L if bar % 2 == 0 else POOL_R, bar, 0.9, dl if bar % 2 == 0 else dr)
track('drums_left', 'mayan_drums_left', 'drum', dl)
track('drums_right', 'mayan_drums_right', 'drum', dr)

# ================================================================ choir: a cluster, never a chord, until the hero turns it
ch = []
for bar in range(15, 18):
    ch += [N(B(bar), 4.05, p, 0.6 + 0.05 * (bar - 15)) for p in (62, 63, 69)]
for bar in range(18, 25):
    ch += [N(B(bar), 4.05, p, 0.72 + 0.03 * (bar - 18)) for p in (62, 63, 66, 69)]
for bar in range(26, 42):
    ch += [N(B(bar), 4.05, p, 0.78 + 0.01 * (bar - 26)) for p in (62, 63, 69)]
for bar in range(42, 58):
    ch += [N(B(bar), 4.05, p, 0.86) for p in (63, 66, 69, 74)]
for bar in range(58, 62):
    ch += [N(B(bar), 4.05, p, 0.92) for p in (62, 63, 69, 74)]
for bar in range(62, 66):
    ch += [N(B(bar), 4.05, p, 1.0) for p in (62, 66, 69, 74)]                 # D major: the cluster is gone, F# in the chord
ch += [N(B(66), 15.9, p, 0.8) for p in (62, 69, 74)]
ch += [N(B(70), 23.9, p, 0.7) for p in (62, 69)]                  # an open fifth: no third, so the ending is calm in either mode
track('choir', 'mayan_choir', 'pad', ch)

# ================================================================ places, calls and single sounds
def env(name, preset, t0, d, role='environment', **extra):
    track(name, f'env:{preset}', role, [dict(t=float(t0), d=float(d), p=60, v=1.0)], **extra)


env('hall_air', 'mayan_hall_air', 0.0, B(S_FOREST, 0.0), fade_out_s=6.0)
env('night', 'mayan_night', B(40, 0.0), B(S_END) - B(40, 0.0) + 4.0, fade_in_s=8.0, fade_out_s=6.0)


def call(name, preset, t0, d, az, el, dist, **kw):
    sp = dict(azimuth=az, elevation=el, distance=dist, kind='spot', binaural=True)
    track(name, f'env:{preset}', 'environment', [dict(t=float(t0), d=float(d), p=60, v=1.0)], spatial=sp, fade_in_s=0.04, fade_out_s=0.04, **kw)


call('conch_1', 'mayan_conch', B(S_OPEN, 0.0), 8.0, 150, 0, 20.0)
call('whistle_1', 'mayan_whistle', B(21, 0.0), 6.0, -110, 5, 16.0)
call('whistle_2', 'mayan_whistle', B(30, 1.0), 6.0, 130, 5, 8.0)
call('whistle_3', 'mayan_whistle', B(52, 0.0), 6.0, 160, 5, 4.0)
call('conch_2', 'mayan_conch', B(S_ESCAPE, 0.0), 8.0, -150, 0, 12.0)


def footfalls(name, preset, times, az, dist, vel=0.72, jitter=0.03, el=-15, dur=1.9):
    """`dur` is in beats and must be at least as long as the sound, or the next onset cuts the ring and the cut is a click."""
    notes = [dict(t=round(float(t + rng.normal(0, jitter)), 4), d=dur, p=60, v=round(float(np.clip(vel + rng.normal(0, 0.06), 0.3, 1.0)), 3))
             for t in times]
    track(name, f'sfx:{preset}', 'fx', notes, spatial=dict(azimuth=az, elevation=el, distance=dist, kind='spot', binaural=True))


def alternate(start, stop, every, skip=()):
    ts = [B(1) + start + every * k for k in range(int((stop - start) / every) + 1) if start + every * k < stop]
    return [t for t in ts if not any(a <= t < b for a, b in skip)]


# the hero walks, stops to look, walks again; goes still at the relic; steps back; then runs
walk = alternate(B(2), B(12), 1.02, skip=[(B(6, 1.5), B(7, 3.0))])
walk += [B(14, 1.0)]
walk += [B(22, 2.5), B(22, 3.4), B(23, 0.2)]                                                         # a step back, two quick: the door shut
footfalls('walk_left', 'mayan_step_stone', walk[0::2], -20, 2.2, 0.55)
footfalls('walk_right', 'mayan_step_stone', walk[1::2], 20, 2.2, 0.55)
run_stone = alternate(B(26), B(41, 2.0), 1.0)
footfalls('run_left', 'mayan_step_run_stone', run_stone[0::2], -50, 1.6, 0.78)
footfalls('run_right', 'mayan_step_run_stone', run_stone[1::2], 50, 1.6, 0.78)
run_leaf = alternate(B(41, 2.0), B(66), 1.0, skip=[(B(53, 1.0), B(53, 3.0))])
run_leaf += [B(53, 2.0), B(53, 2.5)]                                                                 # the stumble: a missed step, then two close ones
run_leaf = sorted(t for t in run_leaf if t < CUT)
footfalls('leaf_left', 'mayan_step_run_leaf', run_leaf[0::2], -55, 1.5, 0.8, el=-12)
footfalls('leaf_right', 'mayan_step_run_leaf', run_leaf[1::2], 55, 1.5, 0.8, el=-12)

# the pursuer: a stone figure behind, heavy, every two beats; nearer in the forest it breaks trees instead
g_far = alternate(B(28), B(34), 2.0)
g_near = alternate(B(34), B(41, 2.0), 2.0)
footfalls('guardian_far_a', 'mayan_guardian_step', g_far[0::2], 175, 8.0, 0.85, jitter=0.02, el=-10, dur=3.9)
footfalls('guardian_far_b', 'mayan_guardian_step', g_far[1::2], -175, 8.0, 0.85, jitter=0.02, el=-10, dur=3.9)
footfalls('guardian_near_a', 'mayan_guardian_step', g_near[0::2], 160, 4.5, 1.0, jitter=0.02, el=-10, dur=3.9)
footfalls('guardian_near_b', 'mayan_guardian_step', g_near[1::2], -160, 4.5, 1.0, jitter=0.02, el=-10, dur=3.9)

# the forest touches the runner: brushes, branches and a trunk grabbed at a turn, from alternating sides, close
def touches(name, preset, times, az, dist, vel=0.8, el=0, dur=3.0):
    notes = [dict(t=float(t), d=dur, p=60, v=round(float(np.clip(vel + rng.normal(0, 0.08), 0.4, 1.0)), 3)) for t in times]
    track(name, f'sfx:{preset}', 'fx', notes, spatial=dict(azimuth=az, elevation=el, distance=dist, kind='spot', binaural=True))


touches('brush_left', 'mayan_leaf_brush', [B(43, 1.5), B(46, 0.0), B(49, 2.5), B(52, 1.0), B(55, 3.0), B(58, 0.5), B(60, 2.0)], -70, 1.0, 0.7)
touches('brush_right', 'mayan_leaf_brush', [B(44, 2.5), B(47, 1.5), B(50, 3.5), B(54, 0.0), B(56, 2.0), B(59, 1.5), B(61, 0.5)], 70, 1.0, 0.7)
touches('branch_left', 'mayan_branch_whip', [B(45, 1.0), B(48, 3.0), B(51, 2.0), B(55, 0.5), B(59, 3.5)], -85, 0.9, 0.85)
touches('branch_right', 'mayan_branch_whip', [B(42, 3.0), B(47, 0.0), B(50, 0.5), B(53, 0.5), B(56, 2.5), B(57, 3.0)], 85, 0.9, 0.85)
touches('bark_scratch', 'mayan_bark_scratch', [B(49, 0.0), B(56, 1.0)], -80, 0.9, 0.9)
touches('twig_snap', 'mayan_twig_snap', [B(51, 3.5)], 40, 1.2, 0.85)
touches('tree_crack', 'mayan_tree_crack', [B(46, 2.0), B(50, 2.0), B(54, 1.0), B(60, 2.0), B(63, 0.0)], 170, 7.0, 1.0, dur=6.0)

track('stone_door', 'sfx:mayan_stone_door', 'fx', [dict(t=B(16, 3.0), d=12.0, p=60, v=0.8)], spatial=dict(azimuth=0, elevation=10, distance=2.0, kind='spot', binaural=True))
track('door_shut', 'sfx:mayan_stone_slam', 'fx', [dict(t=SHUT, d=10.0, p=60, v=0.8)], spatial=dict(azimuth=180, elevation=0, distance=6.0, kind='spot', binaural=True))
track('collapse', 'sfx:mayan_rubble', 'fx', [dict(t=COLLAPSE, d=6.0, p=60, v=1.0)], spatial=dict(azimuth=180, elevation=20, distance=5.0, kind='spot', binaural=True))
track('final_slam', 'sfx:mayan_stone_slam', 'fx', [dict(t=CUT, d=10.0, p=60, v=1.0)], spatial=dict(azimuth=170, elevation=0, distance=4.0, kind='spot', binaural=True))
for _t in tracks:
    if _t['name'] in ('stone_door', 'door_shut', 'final_slam'):
        _t['dc_hp_hz'] = 90.0
    if _t['name'] in ('run_left', 'run_right', 'guardian_far_a', 'guardian_far_b', 'guardian_near_a', 'guardian_near_b', 'collapse'):
        _t['dc_hp_hz'] = 60.0
    if _t['name'] in ('branch_left', 'branch_right'):
        _t['dc_hp_hz'] = 60.0
    if _t['name'] == 'tree_crack':
        _t['dc_hp_hz'] = 90.0                           # sub-bass effects carry energy below 25 Hz that shows as stem drift

# ================================================================ the score
dynamics = [[0, 0.45], [16, 0.45], [32, 0.5], [52, 0.55], [64, 0.6], [68, 0.65], [92, 0.85], [95, 0.85], [96, 0.5], [100, 1.0],
            [160, 1.0], [164, 1.0], [228, 1.0], [244, 1.0], [264, 0.9], [268, 0.6], [276, 0.55], [296, 0.5], [300, 0.4]]
sections = [dict(name='the_entry', start_bar=S_ENTRY, end_bar=8, energy=0.25), dict(name='the_relic_chamber', start_bar=S_CHAMBER, end_bar=17, energy=0.4),
            dict(name='the_opening', start_bar=S_OPEN, end_bar=25, energy=0.65), dict(name='the_corridors', start_bar=S_CORR, end_bar=41, energy=0.85),
            dict(name='the_forest', start_bar=S_FOREST, end_bar=57, energy=0.95), dict(name='the_escape', start_bar=S_ESCAPE, end_bar=69, energy=1.0),
            dict(name='the_aftermath', start_bar=S_AFTER, end_bar=75, energy=0.2)]
score = dict(
    title='The Mayan Palace', bpm=150, ts=[4, 4], seed=1511, humanize='natural', key='D', mode='minor',
    tempo_points=[[0, 72], [68, 72], [96, 90], [99.9, 58], [100, 132], [160, 144], [164, 146], [228, 152], [232, 154], [276, 158], [276.01, 66], [300, 62]],
    dynamics=dynamics, space='palace_room', mix_preset='the_palace_hunts_mix',
    output_targets=['stereo', 'immersive_7_1'],
    master=dict(lufs=-14.5, true_peak=-2.0, tone='neutral', fade_out=3.0),
    piece_type='cinematic', focus='melody',
    intent=dict(emotions=['tense', 'dark_epic', 'adventure'], registers=['cinematic', 'natural'], scenes=['arrival', 'build', 'battle'],
                tensions=['ostinato', 'pedal', 'cluster', 'rising_line', 'silence_before'], avoid=['joyful', 'playful']),
    mix_intent=dict(hero='horns', leave_free_hz=[700, 2600]),
    plan=dict(sections=sections, ending=dict(fade_out=3.0)),
    tracks=tracks,
    mix=dict(tracks={}),
)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'scripts'))
import humanize as hz
TM = hz.tempo_map_for(score, seed=score['seed'])
for sec in sections:
    sec['start_s'] = float(TM.sec((sec['start_bar'] - 1) * BB))     # not rounded: a note that starts on a section line must not overlap the section before it
    sec['end_s'] = float(TM.sec(sec['end_bar'] * BB))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(score, f, indent=1)
print(f'wrote {os.path.relpath(OUT, os.getcwd())}: {len(tracks)} tracks, {sum(len(t["notes"]) for t in tracks)} notes')

if __name__ == '__main__':
    for name, beat in (('relic opened', B(16, 3.0)), ('opening', BRAAM1), ('held breath', HELD), ('chase', CORR_HIT), ('collapse', COLLAPSE),
                       ('forest', FOREST_HIT), ('power', POWER), ('cut', CUT), ('aftermath', LAST - 24)):
        print(f'  {name:12s} beat {beat:6.1f}  {float(TM.sec(beat)):6.2f} s')
    for s in sections:
        print(f'  section {s["name"]:18s} {s["start_s"]:6.2f} - {s["end_s"]:6.2f} s')
    print(f'  total {float(TM.sec(B(S_END))):.1f} s')
