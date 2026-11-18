#!/usr/bin/env python3
"""compose_main.py - writes scores/the_mayan_palace_score.json for "The Mayan Palace" (second version: music, no effects).

Only notes and choices live here: which pitch, which beat, which preset. Every sound, level, room and placement is in
presets/ (instruments, vocals, environments, calls, spaces, mix); the intent is in direction/.

There are no sound effects. The picture is told by the music: the pulse is a piano figure, the steps are percussion and a
low piano octave, the branches and leaves are fast violin runs, the collapse is a timpani roll and a brass cluster, the
pursuer is a hit on the first beat after a rest, the ritual is a five-voice chant. Ambience stays: the palace (low air,
a far whistle and conch, bats) and then the night forest.

A story in eight sections (4/4, bars 1-75, 1-based):

    bars  1- 8  the_entry          a piano asks a six-note question in a stone palace; a hum answers from far away
    bars  9-17  the_relic_chamber  the relic is found; a bass clarinet answers; a piano figure starts to pulse; the lid opens
    bars 18-25  the_opening        the evil wakes: braam, chant, the motif in the horns, a held bar of nothing
    bars 26-41  the_corridors      the chase through the palace: piano sixteenths, chop strings, 3+3+2 drums, chant; D then E-flat
    bars 42-57  the_forest         the chase through the forest: E, fast violin runs, a stumble, trees broken behind
    bars 58-65  the_escape         D minor, then D major from bar 62: the hero theme, the pulse in major
    bars 66-69  the_release        the last hit, a beat of nothing, then a fall to D major
    bars 70-75  the_aftermath      the forest at night; the question is answered and falls home to D
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


S_ENTRY, S_CHAMBER, S_OPEN, S_CORR, S_FOREST, S_ESCAPE, S_RELEASE, S_AFTER, S_END = 1, 9, 18, 26, 42, 58, 66, 70, 76
VEL_FLOOR = 0.42        # a sampled pp sits far under its ff; a played velocity never goes below this


def N(t, d, p, v, **kw):
    v = VEL_FLOOR + (1.0 - VEL_FLOOR) * min(1.0, max(0.0, v))
    return dict(t=round(float(t), 4), d=round(float(d), 4), p=int(p), v=round(float(v), 3), **kw)


tracks = []


def track(name, instrument, role, notes, **extra):
    tracks.append(dict(name=name, instrument=instrument, role=role, notes=notes, **extra))


def near(pc, lo, hi):
    for p in range(lo, hi + 1):
        if p % 12 == pc % 12:
            return p
    raise ValueError((pc, lo, hi))


# ---------------------------------------------------------------- the key and the chord of every beat
def key_of(bar):
    """Semitones above D: the chase climbs a semitone at bar 34 and another at bar 42, and comes home to D at bar 58."""
    if bar < 34 or bar >= 58:
        return 0
    return 1 if bar < 42 else 2


MAJOR_ESCAPE = range(62, 70)
LOOP = ((0, 'm'), (0, 'm'), (8, 'M'), (8, 'M')), ((3, 'M'), (3, 'M'), (10, 'M'), (10, 'M'))         # Dm Dm Bb Bb | F F C C


def chord_at(bar, beat):
    """(root pitch class, 'm' or 'M') of this beat. Quiet sections hold one chord a bar; the chase changes every two beats."""
    k = key_of(bar)
    if bar < S_CORR or bar >= S_AFTER or bar >= S_RELEASE:
        if bar in MAJOR_ESCAPE or bar >= S_RELEASE:
            return (D, 'M')
        quiet = {9: (0, 'm'), 10: (8, 'M'), 11: (0, 'm'), 12: (10, 'M'), 13: (0, 'm'), 14: (3, 'M'), 15: (0, 'm'), 16: (8, 'M'), 17: (0, 'm'),
                 18: (0, 'm'), 19: (3, 'M'), 20: (0, 'm'), 21: (3, 'M'), 22: (8, 'M'), 23: (3, 'M'), 24: (0, 'm'), 25: (0, 'm')}
        pc, q = quiet.get(bar, (0, 'm'))
        return ((D + pc) % 12, q)
    if bar in MAJOR_ESCAPE:
        seq = ((0, 'M'), (0, 'M'), (5, 'M'), (7, 'M')) if (bar - 62) % 2 == 0 else ((7, 'M'), (7, 'M'), (0, 'M'), (0, 'M'))
        pc, q = seq[int(beat) % 4]
        return ((D + pc) % 12, q)
    pc, q = LOOP[(bar - S_CORR) % 2][int(beat) % 4]
    return ((D + k + pc) % 12, q)


def triad(root_pc, q, base):
    """root, third, fifth, octave at or above `base`."""
    r = near(root_pc, base, base + 11)
    return [r, r + (3 if q == 'm' else 4), r + 7, r + 12]


# ---------------------------------------------------------------- the relic motif and the hero theme
MOTIF = [(0, 1.5), (1, 0.5), (0, 1.0), (7, 2.0), (5, 1.0), (3, 2.0)]        # D Eb D A G F: 8 beats
HERO = [(0, 1.5), (7, 0.5), (10, 1.0), (12, 1.5), (14, 0.5), (12, 1.0), (10, 1.0), (7, 1.0)]       # D A C D E D C A: a rising fifth and a climb


def phrase(shape, t0, base, vel, scale=1.0, art=0.96, vstep=0.0, upto=None):
    out, t = [], t0
    for k, (iv, d) in enumerate(shape):
        if upto is not None and k >= upto:
            break
        out.append(N(t, d * scale * art, base + iv, vel + vstep * k))
        t += d * scale
    return out


Q = [(0, 1.5), (1, 0.5), (0, 1.0), (7, 2.0), (5, 1.0), (3, 2.0)]
CURIOUS = [(0, 1.0), (2, 1.0), (3, 0.5), (7, 1.5), (5, 1.0), (7, 3.0)]
HOLLOW_A = [(0, 1.5), (1, 0.5), (-2, 1.0), (5, 2.0), (3, 1.0), (0, 2.0)]
HOLLOW_B = [(0, 1.0), (1, 1.0), (0, 0.5), (3, 1.5), (5, 1.0), (10, 3.0)]
ANSWER = [(0, 1.5), (2, 1.5), (5, 1.0), (7, 2.0), (5, 1.0), (2, 2.0), (0, 4.0)]

BRAAM1 = B(S_OPEN)
HELD = B(25)
CORR_HIT = B(S_CORR)
FOREST_HIT = B(S_FOREST)
POWER = B(62)
CUT = B(S_RELEASE)

# ================================================================ pianos: the pulse, the question, the pursuer
pl = [N(B(bar), 3.9, 33, 0.42 + 0.008 * bar + (0.06 if bar % 4 == 1 else 0.0)) for bar in range(1, 18)]        # a low D struck once a bar in the quiet: a piano note does not hold for sixteen beats
pl += [N(B(bar), 4.0, near(chord_at(bar, 0)[0], 26, 37) + 12, 0.66 + 0.02 * (bar - 18)) for bar in range(18, 25)]
for bar in range(S_CORR, S_ESCAPE + 4):                                                                  # the pursuer: heavy two-hand octaves on 3+3+2
    for off, v, d in ((0, 1.0, 0.5), (1.5, 0.78, 0.35), (3.0, 0.88, 0.35)):
        if bar % 4 == 1 and off == 3.0:
            continue                                                                                      # the fill bar leaves the last beat to the drums
        r = near(chord_at(bar, off)[0], 31, 42)
        pl += [N(B(bar, off), d, r, v), N(B(bar, off), d, r + 12, v - 0.06)]
pl += [N(B(66), 4.0, 38, 1.0), N(B(66), 4.0, 50, 0.95)]
pl += [N(B(bar), 3.9 if bar < 75 else 2.0, 33, 0.7 - 0.015 * (bar - 70)) for bar in range(70, 74)]
track('piano_low', 'mayan_piano_low', 'bass', pl)

CELLS = [[0, 2, 3, 2], [0, 3, 2, 3], [0, 2, 0, 3], [2, 3, 2, 0], [0, 1, 2, 3], [3, 2, 1, 2]]       # indices into [root, third, fifth, octave]
pn = []
pn += phrase(Q, B(4), 74, 0.5, vstep=0.01) + phrase(Q, B(7), 74, 0.48, upto=3)                          # the question, alone, high and soft
pn += phrase(CURIOUS, B(9), 79, 0.52)
for bar in range(10, 18):                                                                              # an eighth-note figure starts to pulse under the discovery
    for k in range(8):
        r, q = chord_at(bar, 0)
        t = triad(r, q, 57)
        pn.append(N(B(bar, k * 0.5), 0.48, t[[0, 2, 1, 2][k % 4]] + (12 if k % 4 == 3 else 0), 0.34 + 0.025 * (bar - 10) + (0.08 if k % 4 == 0 else 0.0)))
for bar in range(18, 25):                                                                              # the same figure, louder and in octaves: the opening
    for k in range(8):
        r, q = chord_at(bar, 0)
        t = triad(r, q, 57)
        n = t[[0, 2, 3, 2][k % 4]]
        v = 0.62 + 0.04 * (bar - 18) + (0.1 if k % 4 == 0 else 0.0)
        pn += [N(B(bar, k * 0.5), 0.46, n, v), N(B(bar, k * 0.5), 0.46, n + 12, v - 0.08)]
for bar in range(S_CORR, S_ESCAPE + 4):                                                                # the chase: sixteenths, the pitches follow the chord every two beats
    cell = CELLS[int(rng.integers(0, len(CELLS)))]
    for beat in range(4):
        r, q = chord_at(bar, beat)
        t = triad(r, q, 60)
        for k in range(4):
            tt = B(bar, beat + k * 0.25)
            if bar == 53 and beat == 2:
                continue                                                                              # the stumble: a beat of nothing, then a rush
            v = 0.7 + (0.2 if k == 0 else 0.0) + (0.06 if beat in (0, 2) else 0.0) + 0.0015 * (bar - S_CORR) + rng.normal(0, 0.03)
            pn += [N(tt, 0.22, t[cell[k]], v), N(tt, 0.22, t[cell[k]] + 12, v - 0.14)]
pn += phrase(ANSWER, B(70), 74, 0.5, scale=1.4)
pn[-1]['d'] -= 0.9                                                                                      # the last note rings out: the score stops where the sound does
track('piano', 'mayan_piano', 'ostinato', pn)

# ================================================================ strings
bs = [N(B(1), 16.3, 26, 0.7), N(B(5), 16.3, 26, 0.72), N(B(9), 16.3, 26, 0.75), N(B(13), 16.3, 26, 0.78), N(B(17), 4.0, 26, 0.8)]
bs += [N(B(bar), 4.0, near(chord_at(bar, 0)[0], 26, 37), 0.85 + 0.015 * (bar - 18)) for bar in range(18, 25)]
bs += [N(B(bar), 4.06, near(chord_at(bar, 0)[0], 26, 37), 0.9) for bar in range(S_CORR, 62)]
bs += [N(B(bar), 4.06, near(chord_at(bar, 0)[0], 26, 37), 0.95) for bar in range(62, 66)]
bs += [N(B(66), 16.3, 26, 0.8), N(B(70), 16.3, 26, 0.7), N(B(74), 8.0, 26, 0.65)]
track('basses', 'mayan_basses', 'bass', bs)

ce = []
for bar in range(13, 17):
    ce += [N(B(bar, k * 0.5), 0.4, near(chord_at(bar, 0)[0], 38, 49) + (7 if k % 4 == 2 else 0), 0.68 + 0.02 * bar + (0.06 if k % 4 == 0 else 0)) for k in range(8) if rng.random() > 0.3]
for bar in range(18, 25):
    ce += [N(B(bar, k * 0.5), 0.4, near(chord_at(bar, 0)[0], 38, 49) + (7 if k % 4 == 2 else 0), 0.78 + 0.015 * (bar - 18) + (0.07 if k % 4 == 0 else 0)) for k in range(8)]
for bar in range(S_CORR, S_ESCAPE + 4):                                                                # eighths on the root and the fifth, an accent on the 3+3+2 beats
    for k in range(8):
        r, q = chord_at(bar, k // 2)
        n = near(r, 38, 49) + (7 if k % 4 == 2 else 0)
        if bar == 53 and k // 2 == 2:
            continue
        ce.append(N(B(bar, k * 0.5), 0.4, n, 0.82 + 0.1 * (k in (0, 3, 6)) + 0.002 * (bar - S_CORR) + rng.normal(0, 0.025)))
track('celli', 'mayan_celli_ostinato', 'ostinato', ce)

va = []
for bar in range(S_CORR + 2, S_ESCAPE + 4):                                                            # chops on the off-beats
    for off in ((0.5, 1.5, 2.5, 3.5) if bar % 2 == 0 else (0.5, 1.0, 2.5, 3.0)):
        r, q = chord_at(bar, int(off))
        t = triad(r, q, 55)
        for n in (t[1], t[2]):
            va.append(N(B(bar, off), 0.22, n, 0.74 + 0.1 * (off in (0.5, 2.5)) + rng.normal(0, 0.03)))
track('violas', 'mayan_violas_ostinato', 'arp', va)

vs_ = []                                                                                               # violin staccato: breath, branches and leaves as quick runs
for bar in range(S_CORR + 4, S_ESCAPE + 4):
    r, q = chord_at(bar, 3)
    top = near(r, 79, 90)
    if bar % 2 == 0:                                                                                   # a run down on the last beat
        notes = [top - iv for iv in (0, 2, 3, 5)]
        for k, p in enumerate(notes):
            vs_.append(N(B(bar, 3.0 + k * 0.25), 0.2, p, 0.8 + 0.03 * k))
    else:                                                                                              # a run up on the second beat
        base = near(chord_at(bar, 1)[0], 67, 78)
        for k, iv in enumerate((0, 3, 5, 7)):
            vs_.append(N(B(bar, 1.0 + k * 0.25), 0.2, base + iv, 0.76 + 0.03 * k))
    if bar >= S_FOREST and bar % 4 == 3:                                                               # a flurry of repeated notes: leaves
        for k in range(8):
            vs_.append(N(B(bar, 2.0 + k * 0.125), 0.1, top - 7, 0.6 + 0.04 * k))
track('violins_staccato', 'mayan_violins_staccato', 'arp', vs_)

vt = []
for bar in range(3, 9):
    vt.append(N(B(bar), 4.05, 86 if bar % 2 else 87, 0.65 + 0.02 * (bar - 3)))
for bar in range(13, 18):
    vt += [N(B(bar), 4.05, 86, 0.7 + 0.03 * (bar - 13)), N(B(bar), 4.05, 87, 0.68 + 0.03 * (bar - 13))]
for bar in range(18, 25):
    vt += [N(B(bar), 4.05, 78 + (bar - 18), 0.78 + 0.02 * (bar - 18)), N(B(bar), 4.05, 79 + (bar - 18), 0.76 + 0.02 * (bar - 18))]
for bar in (S_CORR, S_CORR + 1, 34, 35, 42, 43, 58, 59, 60, 61):                                      # a held shimmer at each turn of the chase
    vt += [N(B(bar), 4.05, 86 + key_of(bar), 0.85), N(B(bar), 4.05, 87 + key_of(bar), 0.83)]
track('violins_tremolo', 'mayan_violins_tremolo', 'pad', vt)

vsu = [N(B(bar), 4.05, 74 + (bar - 50) + key_of(bar), 0.72 + 0.015 * (bar - 50)) for bar in range(50, 58)]      # the rising device: a semitone a bar before the escape
vsu += [N(B(bar), 4.05, 78 + 2 * (bar - 62), 0.95) for bar in range(62, 66)]
vsu += [N(B(66), 8.1, 81, 0.85), N(B(68), 8.1, 81, 0.8)]
track('violins_sustain', 'mayan_violins_sustain', 'pad', vsu)

# ================================================================ woodwinds and harp
fl = phrase(CURIOUS, B(13), 79, 0.46, scale=1.2, upto=4)
fl_end = phrase(ANSWER, B(70), 79, 0.46, scale=1.4)
fl_end[-1]['d'] = 2.2                                                                                    # the last phrase note ends before the held A begins: a whole step apart they beat
fl += fl_end + [N(B(73, 3.0), 6.0, 81, 0.35)]
track('alto_flute', 'mayan_alto_flute', 'counter', fl)
bc = phrase(HOLLOW_A, B(11), 50, 0.55) + phrase(HOLLOW_B, B(15), 50, 0.6) + [N(B(74), 8.0, 45, 0.35)]
track('bass_clarinet', 'mayan_bass_clarinet', 'counter', bc)
hp = [N(B(10) + 1.0 * k, 0.9, p, 0.6 + 0.03 * k) for k, p in enumerate((62, 69, 74, 77))]
hp += [N(B(14, 2.0), 1.4, 62, 0.7), N(B(15, 2.0), 1.4, 63, 0.72), N(B(16, 2.0), 1.4, 69, 0.78)]
track('harp', 'mayan_harp', 'arp', hp)

# ================================================================ brass
hn = []
for bar in range(18, 25, 2):
    hn += phrase(MOTIF, B(bar), 55, 0.75 + 0.03 * (bar - 18), art=1.1)
for bar in (30, 38):                                                                                   # the motif as a threat, over the chase
    hn += phrase(MOTIF, B(bar), 55 + key_of(bar), 0.88, art=1.1) + phrase(MOTIF, B(bar + 2), 62 + key_of(bar), 0.92, art=1.1)
for bar in (46, 54):
    hn += phrase(MOTIF, B(bar), 59 + key_of(bar), 0.92, art=1.1) + phrase(MOTIF, B(bar + 2), 66 + key_of(bar), 0.95, art=1.1)
for bar in (58, 60):
    hn += phrase(MOTIF, B(bar), 62, 0.95, upto=3, art=1.1)
for bar in (62, 66):
    hn += phrase(HERO, B(bar), 55, 0.92, art=1.1) + phrase(HERO, B(bar + 2), 62, 0.95, art=1.1)
track('horns', 'mayan_horns', 'melody', hn)

tbs = []
for beat in (BRAAM1, CORR_HIT, FOREST_HIT, B(58)):
    tbs += [N(beat, 6.0, p, 1.0) for p in (50, 57, 62, 63)]
tbs += [N(POWER, 6.0, p, 1.0) for p in (50, 57, 62, 66)]
track('trombones_sus', 'mayan_trombones_sus', 'pad', tbs)

tb = []
for bar in range(S_CORR + 2, S_ESCAPE + 4):                                                            # stabs on 3+3+2, a rest in the fill bar
    r = near(chord_at(bar, 0)[0], 48, 59)
    for off, d in ((0, 0.4), (1.5, 0.4), (3.0, 0.4)):
        if bar % 4 == 1 and off == 3.0:
            continue
        vv = 1.0 if off == 0 else 0.7 + 0.2 * float(rng.random())
        rr = near(chord_at(bar, off)[0], 48, 59)
        tb += [N(B(bar, off), d, rr, vv), N(B(bar, off), d, rr + 7, vv - 0.05)]
track('trombones', 'mayan_trombones', 'chord', tb)

tu = [N(beat, 6.0, 38, 1.0) for beat in (BRAAM1, CORR_HIT, FOREST_HIT, B(58), POWER)]
tu += [N(B(bar), 0.9, near(chord_at(bar, 0)[0], 30, 43), 0.9) for bar in range(S_CORR + 1, S_ESCAPE + 4) if bar % 2 == 1]
track('tuba', 'mayan_tuba', 'bass', tu)

# ================================================================ percussion: the steps, the heart, the collapse
def tp(bar, beat, d, v, root=None):
    return N(B(bar, beat), d, near(chord_at(bar, int(beat))[0] if root is None else root, 36, 47), v)


ti = [tp(bar, 0, 0.6, 0.3 + 0.02 * bar) for bar in range(5, 9)]
for bar in range(13, 18):
    ti += [tp(bar, 0, 0.5, 0.4 + 0.03 * (bar - 13)), tp(bar, 2, 0.5, 0.3 + 0.03 * (bar - 13))]
for bar in range(18, 25):
    ti += [tp(bar, 0, 0.4, 0.6 + 0.03 * (bar - 18)), tp(bar, 1.5, 0.4, 0.45), tp(bar, 2.5, 0.4, 0.5)]
ti += [tp(24, 2.0 + 0.25 * k, 0.2, 0.45 + 0.5 * (k / 7.0) ** 1.6 + (0.04 if k % 2 == 0 else -0.04)) for k in range(8)]
ti = [n for n in ti if not (B(24, 2.0) <= n['t'] < B(25) and n['d'] > 0.3)]
for bar in range(S_CORR, S_ESCAPE + 4):
    if bar % 4 == 1:                                                                                   # a fill every fourth bar: sixteenths rising into the next bar
        ti += [tp(bar, 0, 0.4, 1.0), tp(bar, 1.5, 0.4, 0.85)] + [tp(bar, 2.5 + 0.25 * k, 0.2, 0.5 + 0.45 * (k / 5.0) ** 1.6 + (0.04 if k % 2 == 0 else -0.04)) for k in range(6)]
    else:
        ti += [tp(bar, 0, 0.4, 1.0), tp(bar, 1.5, 0.4, 0.85), tp(bar, 3.0, 0.4, 0.9)]
        if bar % 2 == 0:
            ti += [tp(bar, 3.5, 0.2, 0.6), tp(bar, 3.75, 0.2, 0.7)]
ti += [tp(66, 0, 0.6, 1.0), tp(70, 0, 0.8, 0.28), tp(72, 0, 0.8, 0.22)]
ti = [n for n in ti if not (B(53, 2.0) <= n['t'] < B(53, 3.0))]              # the stumble
track('timpani', 'mayan_timpani', 'drum', ti)

bd = [N(beat, 1.0, 48, 1.0) for beat in (BRAAM1, CORR_HIT, FOREST_HIT, B(58), POWER, CUT)]
BR = {BRAAM1, CORR_HIT, FOREST_HIT, B(58), POWER, CUT}
for bar in range(20, 25):
    bd += [N(B(bar, o), 1.0, 48, v) for o, v in ((0, 0.55 + 0.04 * (bar - 20)), (2.0, 0.4)) if B(bar, o) not in BR]
for bar in range(S_CORR + 1, S_ESCAPE + 4):
    for o, v in ((0, 0.9), (1.5, 0.72), (2.0, 0.6), (3.0, 0.8)):
        if B(bar, o) in BR or (bar == 53 and o == 2.0) or (bar % 4 == 1 and o == 3.0):
            continue
        bd.append(N(B(bar, o), 0.9, 48, v + rng.normal(0, 0.03)))
    extra = (None, 0.75, 3.5, 2.5)[bar % 4]                                                            # a different pickup each bar of the cycle
    if extra is not None and not (bar == 53 and extra >= 2.0) and B(bar, extra) not in BR:
        bd.append(N(B(bar, extra), 0.4, 48, 0.5 + rng.normal(0, 0.03)))
track('bass_drum', 'mayan_bass_drum', 'drum', bd)

sn = []
for bar in range(S_CORR + 2, S_ESCAPE + 4):                                                            # a backbeat snare and a ghost note, a roll into the fill bar
    if bar == 53:
        continue
    back = 3.0 if bar % 4 != 2 else 3.5                                                               # the second backbeat moves in alternate bars: no stack of attacks on the 3+3+2 beat
    ghost = (2.75, 1.75, 3.25, 2.25)[bar % 4]
    sn += [N(B(bar, 1.0), 0.3, 49, 0.9 + rng.normal(0, 0.03)), N(B(bar, back), 0.3, 49, 0.92 + rng.normal(0, 0.03)), N(B(bar, ghost), 0.15, 49, 0.45)]
    if bar % 4 == 0:
        sn += [N(B(bar, 3.0 + 0.125 * k), 0.1, 49, 0.45 + 0.45 * (k / 7.0) ** 1.6 + (0.04 if k % 2 == 0 else -0.04)) for k in range(1, 8)]
track('snare', 'mayan_snare', 'drum', sn)

cy = [N(beat - 3.0, 3.0, 50, 0.7) for beat in (CORR_HIT, FOREST_HIT, POWER)] + [N(beat, 4.0, 59, 0.6) for beat in (BRAAM1, CORR_HIT, FOREST_HIT, B(58), POWER)]        # every swell lands in a section that also holds a hit
cy += [N(BRAAM1, 4.0, 60, 1.0), N(B(21), 4.0, 50, 0.9), N(B(23), 4.0, 59, 0.95), N(B(34), 4.0, 59, 0.9), N(B(38), 4.0, 59, 0.85)]        # the opening and the corridors keep up with the sections around them
cy += [N(CUT, 4.0, 60, 0.9), N(B(46, 0.0), 3.0, 59, 0.6), N(B(50, 0.0), 3.0, 59, 0.6), N(B(54, 0.0), 3.0, 59, 0.6)]
track('cymbals', 'mayan_cymbals', 'texture', cy)

dl, dr = [], []
POOL_L = [(0, 1.5, 3.0), (0, 1.5, 2.5), (0.5, 2.0, 3.0), (0, 3.0), (1.0, 2.5, 3.5), (0, 0.75, 2.0, 3.0)]
POOL_R = [(0.5, 2.0, 3.5), (1.0, 2.5), (0.5, 1.25, 2.0, 2.75, 3.5), (0, 1.5, 3.5), (0.75, 2.25), (0.5, 1.5, 2.25, 3.25)]


def conga(pool, bar, vel, notes):
    pat = pool[int(rng.integers(0, len(pool)))]
    for i, o in enumerate(pat):
        key = (48, 50, 52)[int(rng.choice([0, 1, 2], p=[0.5, 0.35, 0.15]))]
        notes.append(N(B(bar, o), 0.4, key, vel * (1.0 if i == 0 else 0.62 + 0.3 * float(rng.random()))))


for bar in range(S_CORR + 2, S_ESCAPE + 4):
    if bar != 53:
        conga(POOL_L if bar % 2 == 0 else POOL_R, bar, min(0.9, 0.5 + 0.02 * (bar - S_CORR)), dl if bar % 2 == 0 else dr)
track('drums_left', 'mayan_drums_left', 'drum', dl)
track('drums_right', 'mayan_drums_right', 'drum', dr)

# ================================================================ voices
ch = []
ch += [N(B(15), 12.05, p, 0.6) for p in (62, 63, 69)]                                                  # the voices change at uneven distances, never on a bar grid
for bar, nb in ((18, 8), (20, 8), (22, 12)):
    ch += [N(B(bar), nb + 0.05, p, 0.72 + 0.03 * (bar - 18)) for p in (66, 69, 74, 75)]               # above the trombone chord, never on its pitches
for bar, nb in ((58, 12), (61, 4)):
    ch += [N(B(bar), nb + 0.05, p, 0.92) for p in (69, 74, 75, 81)]
for bar, nb in ((62, 8), (64, 4), (65, 4)):
    ch += [N(B(bar), nb + 0.05, p, 1.0) for p in (69, 74)]
ch += [N(B(66), 15.9, p, 0.8) for p in (62, 69, 74)]
ch += [N(B(74, 2.0), 5.9, p, 0.7) for p in (50, 62)]
track('choir', 'mayan_choir', 'pad', ch)

cn = []
for bar in range(S_OPEN + 2, 25):                                                                      # the chant wakes under the opening, on the beat
    cn += [N(B(bar, o), 0.4, 50 + (0 if o == 0 else 3), 0.7 + 0.04 * (bar - S_OPEN)) for o in (0.0, 2.0)]
for bar in range(S_CORR, S_ESCAPE + 4):                                                                # and answers the drums through the chase on 3+3+2
    if bar == 53:
        continue
    for o in (0.0, 1.5, 3.0):
        if bar % 4 == 1 and o == 3.0:
            continue
        cn.append(N(B(bar, o), 0.3, 50 + key_of(bar) + (0 if o == 0 else 3 if o == 1.5 else 5), (0.9 if o == 0 else 0.72 if o == 1.5 else 0.6) + rng.normal(0, 0.04)))
track('chant', 'mayan_chant', 'chord', cn, vowel='a')

wh = phrase(Q, B(5), 62, 0.4, scale=1.3, upto=4) + phrase(HOLLOW_A, B(15), 62, 0.42, scale=1.0, upto=3)           # far away, closed mouth: what is in the relic
track('whisper', 'mayan_whisper', 'pad', wh, hum=True, vowel='m')

# ================================================================ ambience: the palace, then the forest
def env(name, preset, t0, d, role='environment', **extra):
    track(name, f'env:{preset}', role, [dict(t=float(t0), d=float(d), p=60, v=1.0)], **extra)


env('hall_air', 'mayan_hall_air', 0.0, B(S_FOREST, 0.0), fade_out_s=6.0)
env('night', 'mayan_night', B(40, 0.0), B(S_END) - B(40, 0.0) + 4.0, fade_in_s=2.0, fade_out_s=6.0)
env('bats', 'mayan_bats', B(2, 0.0), B(S_CORR, 0.0) - B(2, 0.0), fade_in_s=2.0, fade_out_s=2.0)


def call(name, preset, t0, d, az, el, dist, **kw):
    sp = dict(azimuth=az, elevation=el, distance=dist, kind='spot', binaural=True)
    track(name, f'env:{preset}', 'environment', [dict(t=float(t0), d=float(d), p=60, v=1.0)], spatial=sp, fade_in_s=0.04, fade_out_s=0.04, **kw)


call('conch_1', 'mayan_conch', B(S_OPEN, 0.0), 8.0, 150, 0, 20.0)
call('whistle_1', 'mayan_whistle', B(7, 0.0), 6.0, -110, 5, 18.0)
call('whistle_2', 'mayan_whistle', B(21, 0.0), 6.0, -110, 5, 16.0)
call('whistle_3', 'mayan_whistle', B(52, 0.0), 6.0, 160, 5, 4.0)

# ================================================================ the score
dynamics = [[0, 0.45], [16, 0.45], [32, 0.5], [52, 0.55], [64, 0.6], [68, 0.65], [92, 0.85], [95, 0.85], [96, 0.5], [100, 1.0],
            [160, 1.0], [164, 1.0], [228, 1.0], [244, 1.0], [260, 0.9], [264, 0.7], [276, 0.55], [296, 0.5], [300, 0.4]]
sections = [dict(name='the_entry', start_bar=S_ENTRY, end_bar=8, energy=0.25), dict(name='the_relic_chamber', start_bar=S_CHAMBER, end_bar=17, energy=0.4),
            dict(name='the_opening', start_bar=S_OPEN, end_bar=25, energy=0.55), dict(name='the_corridors', start_bar=S_CORR, end_bar=41, energy=0.85),
            dict(name='the_forest', start_bar=S_FOREST, end_bar=57, energy=0.95), dict(name='the_escape', start_bar=S_ESCAPE, end_bar=65, energy=1.0),
            dict(name='the_release', start_bar=S_RELEASE, end_bar=69, energy=0.45), dict(name='the_aftermath', start_bar=S_AFTER, end_bar=75, energy=0.2)]
def no_retrigger(name, gap=0.004):
    """A key struck again while its last strike still sounds restarts the voice and clicks: end each note before the next one of the same pitch."""
    for tr in tracks:
        if tr['name'] == name:
            last = {}
            for n in sorted(tr['notes'], key=lambda q: (q['p'], q['t'])):
                if n['p'] in last and last[n['p']]['t'] + last[n['p']]['d'] > n['t'] - gap:
                    last[n['p']]['d'] = max(0.05, n['t'] - gap - last[n['p']]['t'])
                last[n['p']] = n


for _name in ('bass_drum', 'snare', 'timpani', 'drums_left', 'drums_right'):
    no_retrigger(_name)
no_retrigger('piano', 0.03)
for _name in ('piano_low', 'celli', 'violas', 'violins_staccato', 'trombones', 'tuba', 'horns', 'harp'):
    no_retrigger(_name, 0.06)                                                                            # the humanizer moves a note by a few ms: a pitched key needs room to release first


def swell(name, lo=0.76):
    """A part that plays the whole chase at one weight reads as a loop: its velocity climbs from `lo` at the corridors to full at the escape."""
    t0, t1 = B(S_CORR), B(S_ESCAPE)
    for tr in tracks:
        if tr['name'] == name:
            for n in tr['notes']:
                if t0 <= n['t'] < t1:
                    n['v'] = float(min(1.0, n['v'] * (lo + (1.0 - lo) * (n['t'] - t0) / (t1 - t0))))


for _name in ('basses', 'celli', 'violas', 'violins_staccato', 'horns', 'tuba', 'chant'):
    swell(_name)
score = dict(
    gate={'tempo.audio': dict(mode='skip', reason='the tempo map runs 56-172 BPM by design (a slow entry, the chase at 148-172, a fall back to 62), so no single tempo exists; the beat tracker measured 83.4 BPM against the declared 150 on this render, a subdivision of the chase, and the declared range is judged by tempo.bpm')},
    title='The Mayan Palace', bpm=150, ts=[4, 4], seed=1511, humanize='natural', key='D', mode='minor',
    tempo_points=[[0, 66], [68, 66], [96, 84], [99.9, 56], [100, 148], [164, 158], [228, 168], [260, 172], [262, 120], [270, 84], [276, 66], [300, 62]],
    dynamics=dynamics, space='palace_room', mix_preset='the_palace_hunts_mix',
    output_targets=['stereo', 'immersive_7_1_2'],
    master=dict(lufs=-15.0, true_peak=-2.0, tone='neutral', fade_out=3.0),
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
    sec['start_s'] = float(TM.sec((sec['start_bar'] - 1) * BB))
    sec['end_s'] = float(TM.sec(sec['end_bar'] * BB))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(score, f, indent=1)
print(f'wrote {os.path.relpath(OUT, os.getcwd())}: {len(tracks)} tracks, {sum(len(t["notes"]) for t in tracks)} notes')

if __name__ == '__main__':
    for s in sections:
        print(f'  section {s["name"]:18s} {s["start_s"]:6.2f} - {s["end_s"]:6.2f} s')
    print(f'  total {float(TM.sec(B(S_END))):.1f} s')
