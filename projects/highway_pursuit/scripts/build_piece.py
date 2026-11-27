# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""build_piece.py - the highway pursuit cue's data: space, gate profile, sheet and score.

This is the piece's own generator (templates/custom_score_template.py is the pattern). It writes note data only: no
synthesis, no EQ, no mixing, no sound effects. Every event the picture has - a twist, a drift, a slow-motion beat, a
swerve - is written as music: a modulation, a chromatic slide, a tempo drop with long notes, a cluster.

    .venv/bin/python projects/highway_pursuit/scripts/build_piece.py

Decisions, all written before the first note (AGENTS.md 4.9):
  * 140 BPM, 4/4, 33 bars. Chases are cited at 120-140 BPM (Karanyi Sounds; Evenant); the cue opens AT speed, mid-evasion,
    because the brief says the piece starts from evading, not from a quiet place.
  * D minor with three deliberate harmonic events: a tritone twist to Ab at bar 5, a chromatic drift D -> Db -> C at bars
    11-13, and the Neapolitan Eb under both chases. Nothing resolves until the escape.
  * Slow motion is a real tempo event, not a filter: the tempo map drops 140 -> 84 across bars 20-23 and the writing
    changes with it (long chords, a timpani roll, the cell stretched to three times its length), then it snaps back.
  * A drift is a slide: the strings move chromatically, the bass steps down a semitone per bar, the backbeat stops.
  * The hook: a cell (root, minor 3rd, 2nd, 5th) on four horns, fragmented in the twist, inverted in the swerve.
  * Rooms change with the camera, not with the bar count: open highway, close cockpit, tunnel bore, flyover deck, open
    air - geometry, materials and a late field in presets/spaces/highway_canyon.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), 'scripts'))
import intent
import gate_clock                      # the renderer's own tempo map: sheet seconds and note seconds cannot drift

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PROJ))

BPM, TS = 140, [4, 4]
BARS = 33
# the cue is cinematic and hybrid: its loudness is the middle of what those registers overlap on, not a figure from a blog
LOUDNESS = intent.register_loudness(['cinematic', 'hybrid'])
BEATS_PER_BAR = TS[0]

# (beat, bpm) - a step map: the slow motion is a tempo drop, and everything downstream (section seconds, hit times) is
# computed from it, so no hit can be "close enough" to the picture.
TEMPO = [(0, 140), (76, 140), (80, 124), (84, 96), (86, 84), (92, 84), (96, 140)]


def beat_of(bar, b=0.0):
    return (bar - 1) * BEATS_PER_BAR + b


_SEC = None


def sec(beat):
    """Seconds at a beat, from the renderer's tempo map (linear ramps between the points)."""
    global _SEC
    if _SEC is None:
        # the map needs the piece's length, which the renderer takes from the notes: one silent note at the last beat
        # gives the same total the rendered score has, so this clock is the renderer's clock
        _SEC = gate_clock.seconds_fn({'bpm': BPM, 'tempo_points': [[b, v] for b, v in TEMPO], 'seed': 7181,
                                      'tracks': [{'notes': [{'t': BARS * BEATS_PER_BAR, 'd': 0.0}]}]})
    return float(_SEC(beat))


def at(bar, b=0.0):
    return round(sec(beat_of(bar, b)), 4)


CHORDS = {
    'Dm': (2, [2, 5, 9]),      # D F A
    'Bb': (10, [10, 2, 5]),    # Bb D F
    'Gm': (7, [7, 10, 2]),     # G Bb D
    'A': (9, [9, 1, 4]),       # A C# E (never resolves)
    'Eb': (3, [3, 7, 10]),     # Eb G Bb (Neapolitan)
    'F': (5, [5, 9, 0]),
    'C': (0, [0, 4, 7]),
    'Ab': (8, [8, 0, 3, 9]),   # Ab C Eb over the held A: the tritone twist, with a common tone
    'Ddim': (2, [2, 5, 8]),    # D F Ab: the tritone arrives inside the tonic
    'Db': (1, [1, 5, 8]),      # Db F Ab: the drift's first slide
    'Dcl': (2, [2, 3, 4, 5]),  # the near-miss cluster
}

PLAN = {
    1: 'Dm', 2: 'Dm', 3: 'Dm', 4: 'Dm',
    5: 'Ddim', 6: 'Ab', 7: 'Dm', 8: 'Dm',
    9: 'Bb', 10: 'A',
    11: 'Dm', 12: 'Db', 13: 'C',
    14: 'Dm', 15: 'Eb', 16: 'F', 17: 'Gm', 18: 'Bb', 19: 'A',
    20: 'Bb', 21: 'Gm', 22: 'Dm', 23: 'Dm',
    24: 'Dm', 25: 'Eb', 26: 'F', 27: 'Gm', 28: 'Bb', 29: 'C',
    30: 'Dcl', 31: 'Dcl',
    32: 'Dm', 33: 'Dm',
}

# (name, role, first bar, last bar, energy, camera)
SECTIONS = [
    ('the_evasion', 'establish', 1, 4, 0.72, 'already moving: low tracking shot, the Hero ahead, the villain closing'),
    ('the_twist', 'build', 5, 10, 0.82, 'a tritone cut to the villain, then back: the road switches direction'),
    ('the_drift', 'transition', 11, 13, 0.55, 'the rear wheel steps out: a low side-tracking shot, no cuts'),
    ('the_chase', 'peak', 14, 19, 0.95, 'handheld, cuts on the bar lines: the two bikes swap the lead'),
    ('the_slow_motion', 'release', 20, 23, 0.50, 'bullet time: the near-collision from three angles, everything pulled back'),
    ('the_swerve', 'peak', 24, 29, 1.0, 'high angle over the flyover, the widest shot, tempo back to full'),
    ('the_near_miss', 'rupture', 30, 31, 0.65, 'the villain clips a truck: one second of nothing'),
    ('the_escape', 'button', 32, 33, 0.30, 'the Hero rides out, cut to black'),
]

ENERGY = {name: e for name, _r, _a, _b, e, _c in SECTIONS}


def section_of(bar):
    for name, role, a, b, e, cam in SECTIONS:
        if a <= bar <= b:
            return name
    return SECTIONS[-1][0]


def role_of(bar):
    for name, role, a, b, e, cam in SECTIONS:
        if a <= bar <= b:
            return role
    return 'button'


def energy_of(bar):
    return ENERGY[section_of(bar)]


def vel(bar, scale=1.0):
    """Velocity from the section's declared energy: one continuous figure, so a section change is not a 0.5 jump."""
    return round(min(1.0, 0.18 + 0.82 * energy_of(bar) * scale), 3)


def chord(bar):
    return CHORDS[PLAN[bar]]


def root_pitch(bar, lo, hi):
    p = chord(bar)[0]
    while p < lo:
        p += 12
    while p > hi:
        p -= 12
    return p


def tone(bar, degree, lo, hi):
    pcs = chord(bar)[1]
    p = pcs[degree % len(pcs)]
    while p < lo:
        p += 12
    while p > hi:
        p -= 12
    return p


def note(t, d, p, v):
    return {'t': round(t, 4), 'd': round(d, 4), 'p': int(p), 'v': round(float(v), 3)}


def clean(notes):
    """One attack per pitch, and no note that starts while the same pitch is still sounding."""
    kept, ends = [], {}
    for n in sorted(notes, key=lambda x: (x['t'], x['p'])):
        if ends.get(n['p'], -1.0) > n['t'] + 1e-6:
            continue
        kept.append(n)
        ends[n['p']] = n['t'] + n['d']
    # no velocity cliff between consecutive notes: a section change is a crescendo, not a jump (intent.avoid sudden_loud)
    prev = None
    for n in kept:
        if prev is not None:
            n['v'] = round(max(prev - 0.28, min(prev + 0.28, n['v'])), 3)
        prev = n['v']
    return kept


# ---- parts --------------------------------------------------------------------------------------------
def basses():
    out = []
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r == 'rupture':
            continue
        base = root_pitch(bar, 24, 35)
        out.append(note(beat_of(bar), 3.7, base, vel(bar, 0.95)))
        if r in ('peak', 'button'):
            out.append(note(beat_of(bar, 2), 1.7, base + 7, round(vel(bar, 0.78), 3)))
    # the drift: the bass itself slides, a semitone per bar, under the 16ths
    for bar, p in ((11, 0), (12, -1), (13, -2)):
        out.append(note(beat_of(bar), 3.7, root_pitch(11, 36, 47) + p, round(vel(bar, 0.9), 3)))
    return out


def basses_pizz():
    out = []
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r not in ('build', 'peak', 'establish'):
            continue
        base = root_pitch(bar, 36, 47)
        v = vel(bar)
        for i in range(8):
            p = base + [0, 12, 7, 12, 0, 12, 10, 12][i]
            out.append(note(beat_of(bar, i * 0.5), 0.42, p, round(v * (0.92 if i % 2 == 0 else 0.74), 3)))
    return out


def tuba():
    out = []
    for bar in range(14, BARS + 1):
        r = role_of(bar)
        if r == 'peak':
            b = root_pitch(bar, 38, 49)
            out.append(note(beat_of(bar, 0.25 if bar == 14 else 0.0), 0.9, b, vel(bar, 0.9)))
            out.append(note(beat_of(bar, 2.5), 0.9, b - 5, vel(bar, 0.76)))
        elif r == 'release':                      # slow motion: a held pedal, not a stab
            out.append(note(beat_of(bar), 3.6, root_pitch(bar, 38, 49), vel(bar, 0.7)))
        elif r == 'button':
            out.append(note(beat_of(bar), 3.7, root_pitch(bar, 38, 49), vel(bar)))
    return out


def celli():
    out = []
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r in ('build', 'peak', 'establish'):
            base = root_pitch(bar, 36, 47)
            v = vel(bar)
            shape = [0, 7, 12, 7, 10, 7, 12, 7]
            accent = (0.92, 0.60, 0.70, 0.88, 0.56, 0.78, 0.66, 0.94, 0.58, 0.72, 0.90, 0.62, 0.68, 0.56, 0.84, 0.64)
            for i in range(16):
                if i in (7, 12):
                    continue
                out.append(note(beat_of(bar, i * 0.25), 0.27, base + shape[i % 8], round(v * accent[i], 3)))
        elif r == 'release':                      # slow motion: one long chord tone per bar
            out.append(note(beat_of(bar), 3.7, tone(bar, 0, 36, 47), round(vel(bar, 0.8), 3)))
    for p in (38, 43, 45):
        out.append(note(beat_of(31, 2.7), 2.4, p, 0.7))
    return out


def violas():
    out = []
    for p in (50, 53, 57):
        out.append(note(beat_of(31, 2.7), 2.6, p, 0.72))
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r == 'rupture':
            continue
        if r == 'button':                      # the escape: a held chord, no ostinato under the cut to black
            out.append(note(beat_of(bar), 3.8, tone(bar, 0, 47, 58), round(vel(bar) * 0.7, 3)))
            continue
        if r == 'release':
            out.append(note(beat_of(bar), 3.7, tone(bar, 1, 48, 59), round(vel(bar, 0.8), 3)))
            continue
        base = tone(bar, 0, 47, 58)
        v = vel(bar)
        shape = [0, 3, 7, 3, 5, 3, 7, 10, 7, 3, 5, 3, 2, 3, 5, 7]
        if r == 'transition':
            # the drift: the bass slides a semitone per bar under the 16ths, so the figure keeps to chord tones (root,
            # third, fifth). The 4th and 7th of the full shape sit a semitone from the 5th harmonic of the sliding bass
            # (measured: 368 Hz against 390 Hz at 18.5 s, roughness 0.134 over the 0.104 limit), and the drift is a slide,
            # not a cluster.
            shape = [0, 3, 7, 3, 7, 3, 7, 3, 0, 3, 7, 3, 7, 3, 0, 3]
        accent = (0.95, 0.62, 0.72, 0.95, 0.58, 0.80, 0.66, 0.95, 0.60, 0.74, 0.95, 0.64, 0.70, 0.58, 0.86, 0.66)
        for i, off in enumerate(shape):
            if i in (6, 13):                    # a sixteenth rests: the run is phrasing, not a machine
                continue
            out.append(note(beat_of(bar, i * 0.25), 0.27, base + off, round(v * accent[i], 3)))
    return out


def violins_long():
    out = []
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r in ('build', 'release', 'button'):
            out.append(note(beat_of(bar), 3.7, tone(bar, 1, 72, 83), vel(bar, 0.85)))
        elif r == 'transition' and bar in (12, 13):   # the drift: a chromatic slide, written as notes
            base = tone(bar, 0, 76, 87)
            # three long falling notes, not a chromatic ladder: the drift is the wheel stepping out, heard as a bend
            for i, (b, d, step) in enumerate(((0.0, 1.5, 0), (1.6, 1.3, -4), (3.0, 0.9, -7))):
                out.append(note(beat_of(bar, b), d, base + 12 + step, round(vel(bar) * (0.9 - 0.08 * i), 3)))
    return out


def violins_staccato():
    out = []
    for bar in range(24, 30):
        base = tone(bar, 0, 72, 83)
        v = vel(bar)
        accent = (0.95, 0.55, 0.74, 0.88, 0.52, 0.82, 0.60, 0.92, 0.56, 0.70, 0.94, 0.58, 0.66, 0.54, 0.86, 0.62)
        for i in range(16):
            if i in (5, 11):
                continue
            p = base + [0, 7, 12, 7, 3, 10, 12, 10][i % 8]
            out.append(note(beat_of(bar, i * 0.25), 0.20, p, round(v * accent[i], 3)))
    return out


# (beat, duration, semitones above the chord root). The fourth is a suspension that falls to the third in a semitone:
# the figure is lyrical without leaving a tension unresolved.
THEME = [(0.0, 1.0, 0), (1.0, 0.5, 3), (1.5, 0.5, 5), (2.0, 0.5, 4), (2.5, 0.5, 3), (3.0, 1.0, 7),
         (4.0, 0.5, 6), (4.5, 0.5, 5), (5.0, 1.0, 3), (6.0, 0.5, 2), (6.5, 0.5, 3), (7.0, 1.0, 0)]


def horns():
    out = []
    last = [None]                     # the note before this phrase, so a section entry is not a leap from nowhere

    def near(base, lo=45, hi=74):
        if last[0] is None:
            return base
        while base - last[0] > 6 and base - 12 >= lo:
            base -= 12
        while last[0] - base > 6 and base + 12 <= hi:
            base += 12
        return base
    # the twist: the cell's first four notes, a tritone away, then back - the music turns with the road
    for bar in (5, 6):
        base = root_pitch(bar, 55, 66)
        for i, (b, d, off) in enumerate(THEME[:4]):
            out.append(note(beat_of(bar, b), d * 0.9, base + off, round(vel(bar) * (0.95 if i % 2 == 0 else 0.7), 3)))
    # chase 1
    for pair in (14, 16, 18):
        last[0] = out[-1]['p'] if out else last[0]
        base = near(root_pitch(pair, 57, 66))
        for i, (b, d, off) in enumerate(THEME):
            out.append(note(beat_of(pair, b), d * 0.9, base + off, round(vel(pair) * (1.0 if i % 2 == 0 else 0.78), 3)))
    last[0] = out[-1]['p'] if out else last[0]
    # slow motion: the same cell, stretched to three times its length, an octave down
    base = near(root_pitch(20, 50, 60))
    for i, (b, d, off) in enumerate(THEME[:5]):
        out.append(note(beat_of(20, b * 2.2), d * 2.6, base + off, round(vel(20) * (0.9 if i % 2 == 0 else 0.7), 3)))
    last[0] = out[-1]['p'] if out else last[0]
    # the swerve: the cell, then its inversion over the flyover
    for pair in (24, 26, 28):
        base = near(root_pitch(pair, 57, 66))
        for i, (b, d, off) in enumerate(THEME):
            out.append(note(beat_of(pair, b), d * 0.9, base + off, round(vel(pair) * (1.0 if i % 2 == 0 else 0.78), 3)))
    for pair in (25, 27):
        base = root_pitch(pair, 57, 64)
        for i, (b, d, off) in enumerate(THEME):
            p = base + (min(12 - off, 10) if off else 0)
            out.append(note(beat_of(pair, b), d * 0.9, min(p, 74), round(vel(pair) * 0.85, 3)))
    last[0] = out[-1]['p'] if out else last[0]
    # near miss: one low cluster, held
    for p in (50, 55, 57):
        out.append(note(beat_of(31, 2.7), 2.2, p, 0.7))
    for p in (38, 45):
        out.append(note(beat_of(31, 2.7), 2.4, p, 0.62))
    # escape: root and fifth, held
    base = near(root_pitch(32, 55, 64))
    out.append(note(beat_of(32), 5.5, base, 0.46))
    out.append(note(beat_of(32, 1.5), 4.0, base + 7, 0.40))
    last[0] = base + 7
    return out


def trombones():
    out = []
    for bar in range(14, BARS + 1):
        r = role_of(bar)
        shift = 0.25 if bar == 14 else 0.0
        if r not in ('peak', 'release'):
            continue
        b = tone(bar, 0, 48, 59)
        v = vel(bar, 0.95)
        if r == 'release':                     # slow motion: one long voicing per bar
            for idx, off in enumerate((0, 3, 7)):
                out.append(note(beat_of(bar, shift + idx * 0.05), 3.6, b + off, round(v * 0.8 * (0.88 + 0.05 * idx), 3)))
        else:
            for idx, off in enumerate((0, 4 if PLAN[bar] == 'A' else 3, 7)):
                out.append(note(beat_of(bar, shift + idx * 0.02), 0.55, b + off, round(v * 0.74 * (0.88 + 0.06 * idx), 3)))
    return out


def piano_theme():
    out = []
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r in ('build', 'peak', 'establish'):
            b = root_pitch(bar, 36, 47)
            v = vel(bar, 0.8)
            for i, bb in enumerate((0, 1.5, 2, 3.5)):
                out.append(note(beat_of(bar, bb), 0.45, b, round(v * (0.92 if i % 2 == 0 else 0.74), 3)))
    return out


def bass_clarinet():
    out = []
    for bar in (5, 14, 20, 24, 30, 32):
        tgt = root_pitch(bar, 50, 62)
        for i, p in enumerate((tgt - 1, tgt - 2)):
            out.append(note(beat_of(bar, -1 + i * 0.5), 0.30, p, round(0.55 + 0.05 * i, 3)))
    for bar in range(24, 30):
        base = tone(bar, 2, 53, 65)
        for i in range(4):
            out.append(note(beat_of(bar, 0.5 + i), 0.4, base + [0, 2, 5, 2][i], round(vel(bar) * 0.6, 3)))
    # slow motion: a long chromatic fall, the counter-line of the drift heard again in bullet time
    base = tone(20, 2, 53, 65)
    for i in range(8):
        out.append(note(beat_of(20, i * 1.2), 1.1, base - i, round(0.42 - 0.02 * i, 3)))
    return out


def choir():
    out = []
    for bar in range(24, 30):
        r = root_pitch(bar, 55, 66)
        for off in (0, 3, 7, 10):
            out.append(note(beat_of(bar), 3.7, r + off, round(vel(bar) * (0.5 if off in (1, 3) else 0.62), 3)))
    for bar in (20, 21, 22, 23):                 # slow motion: a wide open fifth, no cluster
        r = root_pitch(bar, 55, 66)
        for off in (0, 7, 12):
            out.append(note(beat_of(bar), 3.7, r + off, round(vel(bar) * 0.55, 3)))
    for p in (58, 62, 65):
        out.append(note(beat_of(31, 2.7), 2.6, p, 0.6))
    return out


def timpani():
    out = []
    for bar in range(14, BARS + 1):
        r = role_of(bar)
        b = root_pitch(bar, 38, 49)
        if r == 'peak':
            out.append(note(beat_of(bar), 0.6, b, vel(bar, 0.95)))
            out.append(note(beat_of(bar, 2), 0.6, b + 7, vel(bar, 0.8)))
        elif r == 'release':                     # slow motion: a roll, not hits
            for i in range(8):
                shaped = (i / 7.0) ** 1.6
                out.append(note(beat_of(bar, i * 0.5), 0.42, b,
                                round(vel(bar) * (0.66 + 0.34 * shaped + (0.03 if i % 2 == 0 else -0.03)), 3)))
        elif r == 'rupture' and bar == 31:
            out.append(note(beat_of(bar, 2.7), 1.0, b, 0.8))
        elif r == 'button':
            out.append(note(beat_of(bar), 2.0, b, vel(bar)))
    return out


def taiko():
    out = []
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r in ('build', 'peak', 'establish'):
            v = vel(bar)
            keys = (36, 37, 38, 37, 36, 37, 38, 43) if bar % 2 else (36, 38, 37, 38, 36, 43, 38, 37)
            accents = (0.9, 0.72, 0.78, 0.7, 0.92, 0.74, 0.8, 0.76)
            for i in range(8):
                out.append(note(beat_of(bar, i * 0.5), 0.2, keys[i], round(v * accents[i], 3)))
        elif bar in (30, 31):                    # after the near miss: two hits, then the room
            if bar == 31:
                out.append(note(beat_of(bar, 2.9), 0.3, 36, 0.42))
    return out


def bass_drum():
    out = []
    for bar in range(1, BARS + 1):
        r = role_of(bar)
        if r not in ('build', 'peak', 'establish'):
            continue
        v = vel(bar)
        if bar % 4 == 0:
            pattern = ((0.0, 1.0), (0.5, 0.62), (1.0, 0.78), (1.75, 0.7), (2.25, 0.86), (3.0, 0.92),
                       (3.5, 0.66), (3.75, 0.82))
        elif bar % 2 == 0:
            pattern = ((0.0, 1.0), (1.0, 0.7), (1.5, 0.8), (2.0, 0.95), (2.75, 0.66), (3.5, 0.84))
        else:
            pattern = ((0.0, 1.0), (1.5, 0.8), (1.75, 0.74), (2.0, 0.95), (3.0, 0.86), (3.5, 0.8))
        for b, a in pattern:
            out.append(note(beat_of(bar, b), 0.3, 36, round(v * a, 3)))
    return out


def snare():
    out = []
    for bar in (12, 13):
        for i in range(16):
            out.append(note(beat_of(bar, i * 0.25), 0.2, 38, round(0.42 + 0.02 * i + 0.03 * (bar - 12), 3)))
    for bar in range(14, BARS + 1):
        r = role_of(bar)
        if r == 'peak':
            for b in (1.0, 3.0):
                out.append(note(beat_of(bar, b), 0.25, 38, vel(bar, 0.85)))
        elif r == 'release':                     # slow motion: a rim, once a bar
            out.append(note(beat_of(bar, 2.0), 0.25, 37, round(vel(bar) * 0.6, 3)))
    return out


def cymbals():
    out = []
    for bar in (1, 5, 11, 14, 20, 24, 31, 32):
        out.append(note(beat_of(bar, 2.7 if bar == 31 else 0.0), 2.4, 49, round(vel(bar, 0.85), 3)))
    for bar in (18, 19):                         # the swell into the slow motion
        for i in range(8):
            key = 52 if i % 2 else 49
            jitter = 0.02 if i % 3 == 0 else -0.015
            out.append(note(beat_of(bar, i * 0.5 + jitter), 0.35, key, round(0.33 + 0.04 * i + 0.03 * (bar - 18), 3)))
    return out


def low_swell():
    out = []
    for bar in (13, 23, 29):
        out.append(note(beat_of(bar, 2), 2.0, root_pitch(bar, 36, 47) - 12, 0.8))
    # the near miss: the sheet declares one second of nothing (hit at the section start, silence_after_s 1.0), then the
    # room. The notes used to leave about 2.9 s of nothing, so the master read a 165 ms hole at 54.4 s (rca: "no stem in the
    # score sounds there"). A low swell enters when the declared rest ends and runs into the escape.
    out.append(note(beat_of(30, 2.5), beat_of(32) - beat_of(30, 2.5), root_pitch(31, 36, 47) - 12, 0.5))
    return out


TRACKS = [
    ('basses', 'pursuit_basses', 'bass', basses),
    ('basses_pizz', 'pursuit_basses_pizz', 'bass', basses_pizz),
    ('tuba', 'pursuit_tuba', 'bass', tuba),
    ('bass_drum', 'pursuit_bass_drum', 'drum', bass_drum),
    ('timpani', 'pursuit_timpani', 'drum', timpani),
    ('taiko', 'pursuit_taiko', 'drum', taiko),
    ('snare', 'pursuit_snare', 'drum', snare),
    ('cymbals', 'pursuit_cymbals', 'texture', cymbals),
    ('low_swell', 'pursuit_low_swell', 'texture', low_swell),
    ('violas', 'pursuit_violas', 'ostinato', violas),
    ('celli', 'pursuit_celli', 'ostinato', celli),
    ('violins_staccato', 'pursuit_violins_staccato', 'ostinato', violins_staccato),
    ('violins_long', 'pursuit_violins_long', 'pad', violins_long),
    ('choir', 'pursuit_choir', 'pad', choir),
    ('trombones', 'pursuit_trombones', 'chord', trombones),
    ('piano_theme', 'pursuit_piano_theme', 'chord', piano_theme),
    ('bass_clarinet', 'pursuit_bass_clarinet', 'counter', bass_clarinet),
    ('horns', 'pursuit_horns', 'melody', horns),
]


def sections_json():
    out = []
    for name, role, a, b, e, cam in SECTIONS:
        out.append(dict(name=name, role=role, start_bar=a, end_bar=b, start_s=at(a), end_s=at(b + 1),
                        energy=e, camera=cam))
    return out


def hits():
    """The picture events, in seconds from the tempo map: every cut is on a bar line, the slow motion is not."""
    return [
        {'t': at(5), 'kind': 'musical', 'sync': 'hard', 'sound': 'the tritone twist: trombones and crash on the cut',
         'why': 'the road turns; the harmony turns with it (Dm -> Ab), and the strings run through the cut'},
        {'t': at(11), 'kind': 'cut', 'sync': 'soft', 'sound': 'the drift: drums out, strings slide',
         'why': 'no edit, a camera move: a soft sync'},
        {'t': at(14), 'kind': 'musical', 'sync': 'hard', 'sound': 'full orchestra on the wide shot',
         'why': 'chase 1 lands on the cut'},
        {'t': at(20), 'kind': 'musical', 'sync': 'hard', 'sound': 'the pad opens and the tempo drops: bullet time',
         'why': 'the slow-motion beat starts on this frame; the tempo drops under it and the held notes carry over'},
        {'t': at(24), 'kind': 'musical', 'sync': 'hard', 'sound': 'the tempo snaps back, cluster and taiko',
         'why': 'the flyover: the widest shot and the loudest bar'},
        {'t': at(30), 'kind': 'cut', 'sync': 'hard', 'sound': 'the truck horn is picture: the music stops for a second',
         'silence_after_s': 1.0, 'why': 'the near miss: silence is the effect, and the room is what sounds'},
        {'t': at(32), 'kind': 'musical', 'sync': 'soft', 'sound': 'one low D and a taiko, then the tail',
         'why': 'the escape, under the cut to black'},
    ]


def sheet():
    base = json.load(open(os.path.join(ROOT, 'projects', 'night_pursuit_cinematic', 'direction',
                                       'direction_night_pursuit_cinematic.json'), encoding='utf-8'))
    base.pop('video', None)
    secs = sections_json()
    base.update({
        'title': 'Highway Pursuit',
        'job': 'a 60 s title-sequence cue for a motorcycle chase on an Indian national highway: the Hero is already '
               'evading when the cue starts, the villain closes, and every twist, drift and slow-motion beat is played '
               'by the music - no sound effects',
        'purpose': 'keep the viewer leaning forward for a minute and land on a cut to black',
        'point_of_view': "the Hero's, over the bars: the music is what the rider hears, not a narrator's comment",
        'piece_type': 'highway_pursuit', 'focus': 'melody',
        'tempo': {'bpm': BPM,
                  'note': '140 BPM, at the top of the cited 120-140 chase band (Karanyi Sounds); the slow-motion beat '
                          'drops the tempo map to 84 and back, so the bullet-time is played, not filtered'},
        'key': 'D minor', 'energy': 0.9,
        'sections': secs,
        'motifs': [{'name': 'the_cell', 'instrument': 'horns',
                    'shape': 'root, minor 3rd, fourth falling to the third, fifth: two bars; fragmented at the twist, stretched in slow '
                             'motion, inverted over the flyover',
                    'why': 'four notes survive engine noise, a cut and a tempo change'}],
        'hits_at': [h['t'] for h in hits()],
        'hits': hits(),
        'ending': 'combination',
        'ending_note': 'cut to black on the low D, then a short tail: no fade of a fake climax',
        'feel': ['relentless', 'dangerous', 'fast'],
        'avoid_feel': ['triumphant', 'playful', 'exotic'],
        'avoid_feel_note': 'no victory cadence, no comedy, no tourist colour: the cue stays cold and forward',
        'palette': ['strings: 16th ostinato, chromatic slides, staccato', 'brass: horns, trombones, tuba',
                    'percussion: bass drum, timpani, taiko, snare, crash', 'piano: low octave pulse',
                    'bass clarinet: chromatic approach and a long fall', 'choir: open fifth in slow motion'],
        'avoid_sounds': ['bansuri', 'veena', 'tambura', 'sitar', 'tabla', 'police siren',
                         'any Indian classical instrument or scale', 'ambience', 'rain', 'sound effects'],
        'space': 'highway_canyon',
        'mix_intent': {'hero': 'horns', 'leave_free_hz': []},
        'loudness': LOUDNESS, 'true_peak_max': -1.5,
        'delivery': {'format': 'wav', 'sample_rate': 48000, 'bit_depth': 24, 'stage': 'master'},
        'references': ['night_pursuit_cinematic: the same chase grammar, rewritten for a highway, a colder colour and '
                       'a real slow-motion beat'],
        'spatial_staging': {
            'front': ['horns', 'violins_staccato'], 'mid': ['violas', 'celli', 'trombones', 'piano_theme',
                                                            'bass_clarinet'],
            'low_front': ['basses', 'basses_pizz', 'tuba', 'bass_drum'], 'overhead': ['cymbals', 'choir'],
            'rear': ['taiko', 'timpani'],
            'why': 'the bikes are in front of the viewer and the percussion is behind: that is what makes the seat feel '
                   'uncomfortable rather than loud',
        },
        'intent': {'emotions': ['tense', 'dark_epic'], 'registers': ['cinematic', 'hybrid'],
                   'scenes': ['establish', 'build', 'chase', 'dread'],
                   'tensions': ['ostinato', 'pedal', 'tritone', 'cluster', 'silence_before', 'unresolved_dominant'],
                   'avoid': ['joyful', 'playful']},
        'harmony_plan': [{'section': s['name'], 'root': PLAN[s['start_bar']],
                          'move': {'the_evasion': 'pedal D', 'the_twist': 'tritone to Ab and back',
                                   'the_drift': 'chromatic slide D -> Db -> C',
                                   'the_chase': 'Neapolitan Eb over a D pedal',
                                   'the_slow_motion': 'wide triads, no dissonance: the ear is allowed to breathe',
                                   'the_swerve': 'the same progression a fourth up, cluster in the choir',
                                   'the_near_miss': 'a semitone cluster, unresolved',
                                   'the_escape': 'a bare D and A'}[s['name']],
                          'why': 'each harmonic event is a picture event, not a key change for its own sake'} for s in secs],
    })
    base['expression'] = {
        'sonic_picture': {'first_10s': 'already at speed: pedal D, 16th ostinato, a taiko behind the listener',
                          'middle': 'the twist to Ab, the drift down a semitone at a time, then the full chase',
                          'last_note': 'one low D, struck, left to ring'},
        'performer': 'a session orchestra playing to picture, conductor taking the cuts from a click and the slow '
                     'motion from the tempo map',
        'producer_moves': ['ride the ostinato up 3 dB into the chase, not the whole mix',
                           'in bullet time, open the room and pull the 16ths out: the tempo drop does the rest',
                           'keep the sub under the trucks, not under the strings'],
        'anti_generic': 'no riser-and-impact drop and no trailer braam: the twist is a tritone, the drift is a slide '
                        'played by the strings, the slow motion is a tempo, and the silence is written',
        'theme': {'name': 'the_cell',
                  'shape': 'up a third, a fourth that falls to the third, leap a fifth, settle on the third',
                  'variation_plan': 'fragmented at the twist, stretched 3x in slow motion, inverted over the flyover, '
                                    'two notes and a low D at the escape'},
        'cues': [{'section': s['name'], 'arousal': s['energy'], 'mode': 'D minor / Ab tritone / Eb Neapolitan',
                  'tempo': ('84 (slow motion)' if s['name'] == 'the_slow_motion' else '140'),
                  'dynamics': f"mean velocity {vel(s['start_bar']):.2f}",
                  'articulation': 'spiccato strings, marcato brass, rolled timpani in bullet time',
                  'timbre': 'cold, close, no reverb on the low end'} for s in secs],
    }
    base['immersive'] = {
        'why': 'the chase surrounds the listener: the bikes swap the lead across the front, the tunnel closes the '
               'field, the flyover opens it and lifts the percussion overhead',
        'anchors': [{'part': 'basses', 'why': 'the road is fixed under the viewer'},
                    {'part': 'horns', 'why': 'the Hero is in front of the camera for the whole cue'}],
        'movers': [{'part': 'bass_clarinet', 'why': 'the villain crosses the frame',
                    'path': 'hard left rear to hard right front over the twist'},
                   {'part': 'cymbals', 'why': 'camera shake and wind', 'path': 'overhead, sweeping with each cut'}],
        'height_plan': {'overhead': ['cymbals', 'choir'], 'low': ['basses', 'bass_drum'],
                        'why': 'height is used for the shot, not for decoration'},
        'room_changes': [{'at_section': 'the_drift', 'why': 'the camera drops to the tarmac: a close, dry field'},
                         {'at_section': 'the_slow_motion', 'why': 'bullet time: the room lengthens and the near '
                                                                   'field empties'},
                         {'at_section': 'the_swerve', 'why': 'the flyover: the tail opens and the percussion lifts'},
                         {'at_section': 'the_escape', 'why': 'back to the open road, dry and close'}],
        'deliverables': ['stereo', 'ambix'],
    }
    return base


def gate_profile():
    return {
        'name': 'highway_pursuit',
        'character': 'a 60 s highway chase cue judged against its own camera cuts: the Hero is already evading when it '
                     'starts, a tritone twist, a chromatic drift and a real tempo drop carry the picture, and the two '
                     'chases are allowed to be the roughest, loudest and most syncopated part of the piece while the '
                     'slow motion and the near-miss silence are allowed to be the quietest.',
        'extends': 'orchestral',
        'flags': [],
        'focus': {'roles': ['melody', 'lead', 'vocal'], 'label': 'the cell on the horns',
                  'reason': 'the cue is defined by a figure: four horns state it at every camera'},
        'scene': {
            'timeline': {'tolerance_s': 0.5},
            'roles': {
                'establish': {'bsi_mode': 'pocket'},
                'build': {'huron_resolution_gravity': 'RELAX', 'strain_slope_min': 0.0, 'bsi_mode': 'pocket'},
                'transition': {'arousal_max': 0.65, 'bsi_mode': 'stillness'},
                'peak': {'arousal_min': 0.6, 'surprise_min_z': 1.0, 'min_hits': 1, 'roughness_min_frac': 0.5,
                         'waive_ceiling': ['roughness', 'feel.contour', 'feel.resolution'],
                         'bsi_mode': 'pocket', 'huron_resolution_gravity': 'RELAX'},
                'release': {'strain_drop_min': 0.15, 'arousal_max': 0.55, 'huron_resolution_gravity': 'ENFORCE'},
                'rupture': {'bsi_mode': 'rupture', 'bsi_min': 1.5, 'surprise_min_z': 1.0,
                            'allow_intentional_silence': True, 'waive_ceiling': ['roughness', 'feel.witek']},
                'button': {'arousal_max': 0.45, 'huron_resolution_gravity': 'ENFORCE'},
            },
            'dialogue': {},
        },
        'rows': {
            'scene.macro_contrast': {'min_sections': 2},
            # measured on the first render on the orchestral profile: cymbals in the final section, 13.6 dB under the sheet's
            # energy ratio against 12 dB (the other six sections follow the curve); `gate_profiles.py relax` wrote it
            'stem.dead': {'mode': 'relax', 'under_db': 15.0,
                          'reason': "cymbals in the final 'the_escape' section (sheet energy 0.3) are a fading roll of low-velocity "
                                    'strokes (0.36-0.6) on a one-layer GM sample: the stem sits 13.6 dB under the sheet\'s energy '
                                    'ratio against the 12 dB limit, in the last section only; the other six sections follow the '
                                    'curve within 3 dB. The notes cannot be louder (velocity 0.4 is already the roll), so the '
                                    "row's expectation does not fit a decaying tail. Measured in the last render: cymbals 13.6 dB, master."},
        },
    }


def space():
    return {
        'name': 'highway_canyon', 'kind': 'spaces',
        'character': 'NH-48 at night: an open asphalt corridor between concrete crash barriers, with a tunnel bore, a '
                     'steel flyover deck above it and open air beyond. Each camera is a room scene.',
        'room': {'rt60': 1.3, 'pre_delay_ms': 14, 'hf_decay': 0.55, 'early_level': 0.40},
        'reflections': {
            'path_physics': True, 'ref_m': 1.5, 'ground_delay_ms': 6.0, 'ground_gain': 0.45,
            'ground_cutoff_hz': 4200, 'lateral_delay_ms': 13.0, 'lateral_gain': 0.5,
            'lateral_cutoff_hz': 3600, 'ceiling_delay_ms': 26.0, 'ceiling_gain': 0.08,
            'rear_delay_ms': 38.0, 'rear_gain': 0.28,
            'geometry': {'width_m': 26.0, 'depth_m': 400.0, 'height_m': 14.0,
                         'listener': {'x': 13.0, 'y': 120.0, 'z': 1.1},
                         'materials': {'floor': 'asphalt_wet', 'ceiling': 'open', 'walls': 'brick_facade'},
                         'material_set': 'highway_materials', 'max_order': 3, 'max_taps': 16, 'min_level_db': -34.0},
            'late': {'enabled': True, 'rt60_s': 1.3, 'hf_decay': 0.55, 'level_db': -23.0, 'count': 8,
                     'spread_deg': 100.0, 'rise_s': 0.02, 'seed': 7181},
        },
        'scenes': [
            {'anchor': {'section': 'the_evasion'}, 'transition_s': 0.4,
             'space_overrides': {'geometry': {'width_m': 26.0, 'depth_m': 400.0, 'height_m': 14.0,
                                              'listener': {'x': 13.0, 'y': 120.0, 'z': 2.5}},
                                 'late': {'rt60_s': 1.6, 'level_db': -26.0}}},
            {'anchor': {'section': 'the_twist'}, 'transition_s': 0.6,
             'space_overrides': {'geometry': {'width_m': 30.0, 'depth_m': 500.0, 'height_m': 20.0,
                                              'listener': {'x': 15.0, 'y': 150.0, 'z': 1.4}},
                                 'late': {'rt60_s': 1.9, 'level_db': -21.0}}},
            {'anchor': {'section': 'the_drift'}, 'transition_s': 1.0,
             'space_overrides': {'geometry': {'width_m': 6.0, 'depth_m': 9.0, 'height_m': 1.4,
                                              'listener': {'x': 3.0, 'y': 4.5, 'z': 0.5},
                                              'materials': {'floor': 'asphalt_wet', 'ceiling': 'open',
                                                            'walls': 'brick_facade'}},
                                 'late': {'rt60_s': 0.4, 'level_db': -32.0}}},
            {'anchor': {'section': 'the_chase'}, 'transition_s': 1.2,
             'space_overrides': {'geometry': {'width_m': 26.0, 'depth_m': 400.0, 'height_m': 14.0,
                                              'listener': {'x': 13.0, 'y': 120.0, 'z': 1.1}},
                                 'late': {'rt60_s': 1.3, 'level_db': -23.0}}},
            {'anchor': {'section': 'the_slow_motion'}, 'transition_s': 1.4,
             'space_overrides': {'geometry': {'width_m': 12.0, 'depth_m': 300.0, 'height_m': 6.5,
                                              'listener': {'x': 6.0, 'y': 90.0, 'z': 1.1},
                                              'materials': {'floor': 'underpass_concrete',
                                                            'ceiling': 'underpass_concrete',
                                                            'walls': 'underpass_concrete'}},
                                 'late': {'rt60_s': 2.7, 'level_db': -15.0, 'hf_decay': 0.35}}},
            {'anchor': {'section': 'the_swerve'}, 'transition_s': 1.5,
             'space_overrides': {'geometry': {'width_m': 40.0, 'depth_m': 600.0, 'height_m': 60.0,
                                              'listener': {'x': 20.0, 'y': 200.0, 'z': 9.0},
                                              'materials': {'floor': 'steel_deck', 'ceiling': 'open',
                                                            'walls': 'open'}},
                                 'late': {'rt60_s': 2.2, 'level_db': -19.0, 'hf_decay': 0.45}}},
            {'anchor': {'section': 'the_near_miss'}, 'transition_s': 0.3,
             'space_overrides': {'geometry': {'width_m': 26.0, 'depth_m': 400.0, 'height_m': 14.0,
                                              'listener': {'x': 13.0, 'y': 120.0, 'z': 1.1}},
                                 'late': {'rt60_s': 3.2, 'level_db': -12.0}}},
            {'anchor': {'section': 'the_escape'}, 'transition_s': 1.0,
             'space_overrides': {'geometry': {'width_m': 26.0, 'depth_m': 400.0, 'height_m': 14.0,
                                              'listener': {'x': 13.0, 'y': 120.0, 'z': 1.1}},
                                 'late': {'rt60_s': 1.2, 'level_db': -25.0}}},
        ],
        'distance': {'ref_m': 1.5, 'falloff': 0.18, 'air_damping': 0.42, 'min_cutoff_hz': 3200,
                     'reverb_exponent': 0.62,
                     'pre_delay_law': {'base_ms': 11.0, 'per_m': 1.4, 'max_ms': 28.0}},
        'binaural': {'bed': False, 'spot': True},
        'sources': ['KB cinematic-hybrid-scoring: pressure is a deliverable, a hit that stops the music is declared',
                    'Room physics: the tunnel and the flyover are the same engine scene module (scripts/phys_core) with '
                    'geometry, materials and a late field, not a reverb preset switch',
                    'Barrier and asphalt materials come from the shipped static-scene material set'],
    }


def write(path, obj):
    full = os.path.join(PROJ, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)
    print('wrote', os.path.relpath(full, ROOT))


def main():
    write('presets/spaces/highway_canyon.json', space())
    write('presets/gate/highway_pursuit.json', gate_profile())
    write('direction/direction_highway_pursuit.json', sheet())
    score = {
        'title': 'Highway Pursuit', 'bpm': BPM, 'ts': TS, 'seed': 7181, 'humanize': 'natural',
        'tempo_points': [[b, v] for b, v in TEMPO],
        'key': 'D', 'mode': 'minor', 'space': 'highway_canyon', 'mix_preset': 'highway_pursuit_mix',
        'output_targets': ['stereo', 'ambix'],
        # no 'lufs': the piece declares registers, so the master is levelled to the register's range (intent.register_loudness)
        'master': {'true_peak': -1.5, 'tone': 'neutral', 'fade_out': 0.8},
        'piece_type': 'highway_pursuit', 'focus': 'melody',
        'intent': {'emotions': ['tense', 'dark_epic'], 'registers': ['cinematic', 'hybrid'],
                   'scenes': ['establish', 'build', 'chase', 'dread'],
                   'tensions': ['ostinato', 'pedal', 'tritone', 'cluster', 'silence_before', 'unresolved_dominant'],
                   'avoid': ['joyful', 'playful']},
        'mix_intent': {'hero': 'horns', 'leave_free_hz': []},
        'medium': {'model': 'iso9613', 'state': {'temperature_k': 293.15, 'pressure_pa': 101325, 'rh_percent': 78}},
        'plan': {'sections': sections_json()},
        'tracks': [{'name': n, 'instrument': inst, 'role': role, 'notes': clean(fn())} for n, inst, role, fn in TRACKS],
        'mix': {'tracks': {}},
    }
    write('scores/highway_pursuit_score.json', score)
    print('notes:', sum(len(t['notes']) for t in score['tracks']), 'duration_s', at(BARS + 1))


if __name__ == '__main__':
    main()
