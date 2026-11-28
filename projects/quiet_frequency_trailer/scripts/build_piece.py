"""build_piece.py - Quiet Frequency's data: staging, space, gate profile, direction sheet and score.

The piece's own generator (templates/custom_score_template.py is the pattern). It writes note data and declarations only: no synthesis,
no EQ, no mixing. The sounds are presets (scripts/make_sfx.py writes the sound models; presets/instruments the orchestra).

    python projects/quiet_frequency_trailer/scripts/build_piece.py

Decisions, written before the first note (AGENTS.md 4.9):
  * 120 BPM, 4/4, 60 bars = 120 s (a bar is 2 s). F minor, nothing resolves: the last sound is a dominant C with a b9 and a device that never stops.
  * The hook: a four-note cell (root, minor 3rd, 4th falling to the 3rd, 5th) on horns, fragmented in the alert, stated in full in the chase,
    inverted in the escalation, and left as two notes on the end.
  * Act 1 (0-24 s) is sound design: an alarm, a radio, a pulse, one low pedal. Act 2 (24-104 s) is the chase: a 16th ostinato that does not
    stop, the villain closing, a declared second of nothing at 62 s, a second peak that is louder than the first. Act 3 (104-120 s): the music
    leaves, two engines idle, the bike stops, a case opens, the device pulses, one hit, a ring.
  * The engines are part of the arrangement, not a layer on it: the bike sits in the mid-low band under the horn, the car under the basses; the
    music is carved where they live (mix preset) and they share the room (space preset) and its scenes.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PROJ))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import intent                      # noqa: E402
import timeline as TL              # noqa: E402
from timeline import BPM, BARS, SECTIONS, at, beat_of  # noqa: E402

TS = [4, 4]
LOUDNESS = -16.0                   # the user's decision for this cue: -16 LUFS integrated, -1.5 dBTP

CHORDS = {
    'Fm': (5, [5, 8, 0]),          # F Ab C
    'Db': (1, [1, 5, 8]),          # Db F Ab
    'Ab': (8, [8, 0, 3]),          # Ab C Eb
    'Eb': (3, [3, 7, 10]),         # Eb G Bb
    'Bbm': (10, [10, 1, 5]),       # Bb Db F
    'C': (0, [0, 4, 7]),           # C E G (the dominant, never answered)
    'Gb': (6, [6, 10, 1]),         # Gb Bb Db (Neapolitan)
    'Cb9': (0, [0, 4, 7, 1]),      # C E G Db: the b9 over the dominant
    'Cl': (0, [0, 1, 4, 7]),       # a semitone cluster for the truck
}

PLAN = {}
for b in range(1, 7):
    PLAN[b] = 'Fm' if b < 5 else 'Db'
for b, c in zip(range(7, 13), ('Fm', 'Fm', 'Db', 'Ab', 'Eb', 'C')):
    PLAN[b] = c
for b, c in zip(range(13, 19), ('Fm', 'Fm', 'Db', 'Db', 'Bbm', 'C')):
    PLAN[b] = c
for b, c in zip(range(19, 27), ('Fm', 'Db', 'Ab', 'Eb', 'Fm', 'Db', 'Bbm', 'C')):
    PLAN[b] = c
for b, c in zip(range(27, 33), ('Fm', 'Gb', 'Fm', 'Gb', 'Cl', 'Cl')):
    PLAN[b] = c
for b, c in zip(range(33, 45), ('Fm', 'Db', 'Ab', 'Eb', 'Fm', 'Db', 'Bbm', 'C', 'Fm', 'Gb', 'C', 'C')):
    PLAN[b] = c
for b, c in zip(range(45, 53), ('Fm', 'Db', 'Ab', 'Eb', 'Fm', 'Gb', 'Bbm', 'C')):
    PLAN[b] = c
for b in (53, 54, 55):
    PLAN[b] = 'Fm'
for b, c in zip(range(56, 61), ('Fm', 'Fm', 'Db', 'Bbm', 'Bbm')):
    PLAN[b] = c

ENERGY = {n: e for n, _r, _a, _b, e, _c in SECTIONS}


def section_of(bar):
    for n, _r, a, b, _e, _c in SECTIONS:
        if a <= bar <= b:
            return n
    return SECTIONS[-1][0]


def role_of(bar):
    for _n, r, a, b, _e, _c in SECTIONS:
        if a <= bar <= b:
            return r
    return 'button'


def vel(bar, scale=1.0):
    return round(min(1.0, 0.18 + 0.82 * ENERGY[section_of(bar)] * scale), 3)


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
    kept, ends = [], {}
    for n in sorted(notes, key=lambda x: (x['t'], x['p'])):
        if ends.get(n['p'], -1.0) > n['t'] + 1e-6:
            continue
        kept.append(n)
        ends[n['p']] = n['t'] + n['d']
    prev = None
    for n in kept:
        if prev is not None:
            n['v'] = round(max(prev - 0.28, min(prev + 0.28, n['v'])), 3)
        prev = n['v']
    return kept


def b(bar, beat=0.0):
    """Seconds -> beats, the unit of the score's note times (a note's `t` is in beats)."""
    return beat_of(bar, beat)


# ---- where the music is silent: bar 32 starts the declared second (62-63 s); the bass returns on its beat 2 --------------------------------
SILENT_BARS = (32,)


def active(bar):
    return bar not in SILENT_BARS


# ---- parts -----------------------------------------------------------------------------------------------------------------------------
def basses():
    out = []
    for bar in range(1, 61):
        r = role_of(bar)
        if not active(bar) or r == 'button' and bar >= 58:
            continue
        base = root_pitch(bar, 24, 35)
        v = vel(bar, 0.95 if bar >= 7 else 0.8)
        if bar == 31:
            out.append(note(b(bar), 1.9, base, v))      # stops at the cut (62 s)
            continue
        out.append(note(b(bar), 3.7, base, v))
        if r == 'peak':
            out.append(note(b(bar, 2), 1.7, base + 7, round(v * 0.8, 3)))
    out.append(note(b(32, 2), 3.7, root_pitch(32, 24, 35), 0.5))
    return out


def basses_pizz():
    out = []
    for bar in range(13, 53):
        r = role_of(bar)
        if r not in ('build', 'peak') or not active(bar):
            continue
        base = root_pitch(bar, 36, 47)
        v = vel(bar)
        for i in range(8):
            p = base + [0, 12, 7, 12, 0, 12, 10, 12][i]
            out.append(note(b(bar, i * 0.5), 0.42, p, round(v * (0.92 if i % 2 == 0 else 0.74), 3)))
    return out


def tuba():
    out = []
    for bar in range(19, 53):
        if role_of(bar) != 'peak':
            continue
        x = root_pitch(bar, 38, 49)
        out.append(note(b(bar), 0.9, x, vel(bar, 0.9)))
        out.append(note(b(bar, 2.5), 0.9, x - 5, vel(bar, 0.76)))
    return out


def celli():
    out = []
    shape = [0, 7, 12, 7, 10, 7, 12, 7]
    accent = (0.92, 0.60, 0.70, 0.88, 0.56, 0.78, 0.66, 0.94, 0.58, 0.72, 0.90, 0.62, 0.68, 0.56, 0.84, 0.64)
    for bar in list(range(13, 31)) + list(range(33, 53)):
        if role_of(bar) not in ('build', 'peak'):
            continue
        base = root_pitch(bar, 36, 47)
        v = vel(bar)
        for i in range(16):
            if i in (7, 12):
                continue
            out.append(note(b(bar, i * 0.25), 0.27, base + shape[i % 8], round(v * accent[i], 3)))
    for p in (41, 48, 53):
        out.append(note(b(31, 2.7), 2.4, p, 0.62))
    return out


def violas():
    out = []
    accent = (0.95, 0.62, 0.72, 0.95, 0.58, 0.80, 0.66, 0.95, 0.60, 0.74, 0.95, 0.64, 0.70, 0.58, 0.86, 0.66)
    shape = [0, 3, 7, 3, 5, 3, 7, 10, 7, 3, 5, 3, 2, 3, 5, 7]
    for bar in list(range(19, 31)) + list(range(33, 53)):
        base = tone(bar, 0, 47, 58)
        v = vel(bar)
        sh = [0, 3, 7, 3, 7, 3, 7, 3, 0, 3, 7, 3, 7, 3, 0, 3] if PLAN[bar] in ('Gb', 'C') else shape
        # a chord whose third is major (the dominant) takes a major third, not the minor 3 of the shape
        if PLAN[bar] == 'C':
            sh = [0, 4, 7, 4, 7, 4, 7, 4, 0, 4, 7, 4, 7, 4, 0, 4]
        for i, off in enumerate(sh):
            if i in (6, 13):
                continue
            out.append(note(b(bar, i * 0.25), 0.27, base + off, round(v * accent[i], 3)))
    for p in (53, 57, 60):
        out.append(note(b(31, 2.7), 2.6, p, 0.66))
    return out


def violins_staccato():
    out = []
    accent = (0.95, 0.55, 0.74, 0.88, 0.52, 0.82, 0.60, 0.92, 0.56, 0.70, 0.94, 0.58, 0.66, 0.54, 0.86, 0.62)
    for bar in range(33, 53):
        if PLAN[bar] == 'C':
            third = 4
        else:
            third = 3
        base = tone(bar, 0, 72, 83)
        for i in range(16):
            if i in (5, 11):
                continue
            p = base + [0, 7, 12, 7, third, 10, 12, 10][i % 8]
            out.append(note(b(bar, i * 0.25), 0.20, p, round(vel(bar) * accent[i], 3)))
    return out


def violins_long():
    out = []
    for bar in range(1, 61):
        r = role_of(bar)
        if bar in (1, 2) or not active(bar):
            continue
        if r in ('establish', 'transition', 'release', 'button') or (r == 'build' and bar < 19):
            sc = 0.7 if r == 'establish' else 0.85
            out.append(note(b(bar), 3.7, tone(bar, 1, 72, 83), vel(bar, sc)))
    return out


def choir():
    out = []
    for bar in list(range(9, 13)) + list(range(45, 53)):
        r_ = root_pitch(bar, 55, 66)
        for off in (0, 7, 12):
            out.append(note(b(bar), 3.7, r_ + off, round(vel(bar) * 0.55, 3)))
    for bar in (57, 58, 59):                       # the end: an open fifth over the dominant, no third
        r_ = root_pitch(bar, 55, 66)
        for off in (0, 7):
            out.append(note(b(bar), 3.8, r_ + off, 0.4))
    return out


THEME = [(0.0, 1.0, 0), (1.0, 0.5, 3), (1.5, 0.5, 5), (2.0, 0.5, 4), (2.5, 0.5, 3), (3.0, 1.0, 7),
         (4.0, 0.5, 6), (4.5, 0.5, 5), (5.0, 1.0, 3), (6.0, 0.5, 2), (6.5, 0.5, 3), (7.0, 1.0, 0)]


def horns():
    out = []
    last = [None]

    def near(base, lo=45, hi=74):
        if last[0] is None:
            return base
        while base - last[0] > 6 and base - 12 >= lo:
            base -= 12
        while last[0] - base > 6 and base + 12 <= hi:
            base += 12
        return base

    def phrase(bar, cells, scale=1.0, invert=False):
        base = near(root_pitch(bar, 57, 66))
        for i, (bt, d, off) in enumerate(cells):
            o = (min(12 - off, 10) if off else 0) if invert else off
            out.append(note(b(bar, bt), d * 0.9, min(base + o, 74), round(vel(bar) * scale * (1.0 if i % 2 == 0 else 0.78), 3)))
        last[0] = out[-1]['p']

    for bar in (15, 17):                           # the alert: the first four notes only, fragmented
        phrase(bar, THEME[:4], 0.9)
    for bar in (19, 21, 23, 25):                   # the chase: the whole cell
        phrase(bar, THEME)
    for bar in (33, 35, 37, 39, 41, 43):           # the escalation: the cell, then its inversion
        phrase(bar, THEME, invert=bar in (35, 39, 43))
    for bar in (45, 47, 49, 51):                   # the wall: the cell in full
        phrase(bar, THEME, 1.0)
    for p in (53, 58, 60):
        out.append(note(b(31, 2.7), 2.2, p, 0.66))
    base = near(root_pitch(57, 55, 64))            # the end: the first two notes of the cell, then silence
    out.append(note(b(57), 3.6, base, 0.42))
    out.append(note(b(58, 1.0), 3.2, base + 3, 0.38))
    return out


def trombones():
    out = []
    for bar in list(range(19, 31)) + list(range(33, 53)):
        r = role_of(bar)
        if r != 'peak':
            continue
        x = tone(bar, 0, 52, 63)
        third = 4 if PLAN[bar] == 'C' else 3
        for idx, off in enumerate((0, third, 7)):
            out.append(note(b(bar, idx * 0.02), 0.55, x + off, round(vel(bar, 0.95) * 0.74 * (0.88 + 0.06 * idx), 3)))
    return out


def piano_theme():
    out = []
    for bar in range(1, 61):
        r = role_of(bar)
        if not active(bar):
            continue
        x = root_pitch(bar, 36, 47)
        if r == 'establish':                       # the lab: one low note a bar, then two
            out.append(note(b(bar), 1.0, x, round(0.3 + 0.03 * bar, 3)))
            if bar >= 4:
                out.append(note(b(bar, 2.0), 1.0, x, round(0.3 + 0.03 * bar, 3)))
        elif r in ('build', 'peak'):
            for i, bb in enumerate((0, 1.5, 2, 3.5)):
                out.append(note(b(bar, bb), 0.45, x, round(vel(bar, 0.8) * (0.92 if i % 2 == 0 else 0.74), 3)))
        elif r == 'button' and bar >= 56:
            out.append(note(b(bar), 1.0, x, 0.36))
    return out


def low_swell():
    out = []
    for bar in (6, 12, 18, 26, 30, 44, 52):
        out.append(note(b(bar, 2), 2.0, root_pitch(bar, 36, 47) - 12, 0.8))
    out.append(note(b(32, 2.0), b(33) - b(32, 2.0), root_pitch(33, 36, 47) - 12, 0.5))
    out.append(note(b(53), 8.0, 29, 0.42))
    return out


def timpani():
    out = []
    for bar in (7, 13, 19, 27, 33, 45, 49, 53):
        out.append(note(b(bar), 1.2, root_pitch(bar, 38, 49), vel(bar, 0.95)))
    for bar in (18, 26, 44, 52):                   # a roll into the next section
        for i in range(8):
            out.append(note(b(bar, 2.0 + i * 0.25), 0.22, root_pitch(bar, 38, 49), round(vel(bar) * (0.66 + 0.34 * (i / 7.0) ** 1.6), 3)))
    for bar in (30, 31):
        out.append(note(b(bar, 0.0), 0.6, 41 if bar == 30 else 36, 0.6))
    out.append(note(b(59, 2.0), 3.0, 29, 1.0))     # the last hit
    return out


def taiko():
    out = []
    for bar in range(19, 53):
        if role_of(bar) != 'peak':
            continue
        keys = (36, 37, 38, 37, 36, 37, 38, 43) if bar % 2 else (36, 38, 37, 38, 36, 43, 38, 37)
        accents = (0.9, 0.72, 0.78, 0.7, 0.92, 0.74, 0.8, 0.76)
        for i in range(8):
            out.append(note(b(bar, i * 0.5), 0.2, keys[i], round(vel(bar) * accents[i], 3)))
    out.append(note(b(59, 2.0), 0.4, 36, 1.0))
    return out


def bass_drum():
    out = []
    for bar in range(13, 53):
        if role_of(bar) not in ('build', 'peak') or not active(bar):
            continue
        v = vel(bar)
        if bar % 4 == 0:
            pattern = ((0.0, 1.0), (0.5, 0.62), (1.0, 0.78), (1.75, 0.7), (2.25, 0.86), (3.0, 0.92), (3.5, 0.66), (3.75, 0.82))
        elif bar % 2 == 0:
            pattern = ((0.0, 1.0), (1.0, 0.7), (1.5, 0.8), (2.0, 0.95), (2.75, 0.66), (3.5, 0.84))
        else:
            pattern = ((0.0, 1.0), (1.5, 0.8), (1.75, 0.74), (2.0, 0.95), (3.0, 0.86), (3.5, 0.8))
        for bb, a in pattern:
            out.append(note(b(bar, bb), 0.3, 36, round(v * a, 3)))
    for bar in range(7, 13):                       # the take: a slow pulse like a heart, one a bar then two
        out.append(note(b(bar), 0.3, 36, round(0.4 + 0.04 * (bar - 7), 3)))
        if bar >= 10:
            out.append(note(b(bar, 2.0), 0.3, 36, round(0.4 + 0.04 * (bar - 7), 3)))
    out.append(note(b(59, 2.0), 0.4, 36, 1.0))
    return out


def snare():
    out = []
    for bar in (17, 43):                            # the roll into the alert and into the wall
        for i in range(16):                          # an exponential crescendo with alternating accents, not a straight ramp
            out.append(note(b(bar, i * 0.25), 0.2, 38, round(0.40 + 0.5 * (i / 15.0) ** 1.6 + (0.04 if i % 2 == 0 else -0.04), 3)))
    for bar in range(19, 53):
        if role_of(bar) == 'peak':
            for bb in (1.0, 3.0):
                out.append(note(b(bar, bb), 0.25, 38, vel(bar, 0.85)))
    return out


def snare_b():
    out = []
    for bar in (18, 44):
        for i in range(16):
            out.append(note(b(bar, i * 0.25 + 0.125), 0.2, 38, round(0.46 + 0.44 * (i / 15.0) ** 1.6 + (0.04 if i % 2 == 0 else -0.04), 3)))
    return out


def cymbals():
    out = []
    for bar in (7, 13, 19, 27, 33, 45, 49):
        out.append(note(b(bar, 0.0), 2.4, 49, round(vel(bar, 0.85), 3)))
    for bar in (19, 33, 45):                         # a second crash 25 ms behind, brighter
        out.append(note(b(bar, 0.0) + 0.05, 3.0, 57, 0.85))
    out.append(note(b(53, 0.0), b(56) - b(53), 49, 0.4))     # a bloom into the empty room
    out.append(note(b(59, 2.0), 3.0, 52, 0.6))
    return out


TRACKS = [
    ('basses', 'qf_basses', 'bass', basses), ('basses_pizz', 'qf_basses_pizz', 'bass', basses_pizz), ('tuba', 'qf_tuba', 'bass', tuba),
    ('bass_drum', 'qf_bass_drum', 'drum', bass_drum), ('timpani', 'qf_timpani', 'drum', timpani), ('taiko', 'qf_taiko', 'drum', taiko),
    ('snare', 'qf_snare', 'drum', snare), ('snare_b', 'qf_snare_b', 'drum', snare_b), ('cymbals', 'qf_cymbals', 'texture', cymbals),
    ('low_swell', 'qf_low_swell', 'texture', low_swell),
    ('violas', 'qf_violas', 'ostinato', violas), ('celli', 'qf_celli', 'ostinato', celli),
    ('violins_staccato', 'qf_violins_staccato', 'ostinato', violins_staccato),
    ('violins_long', 'qf_violins_long', 'pad', violins_long), ('choir', 'qf_choir', 'pad', choir),
    ('trombones', 'qf_trombones', 'chord', trombones), ('piano_theme', 'qf_piano_theme', 'chord', piano_theme),
    ('horns', 'qf_horns', 'melody', horns),
]

# ---- the sounds: one track per sound-model preset, one trigger note each; the preset's own clock starts at its trigger ------------------
SFX = [  # (track, preset, start_s, length_s)
    ('sfx_alarm', 'qf_alarm', 0.0, 12.0), ('sfx_heartbeat', 'qf_heartbeat', 3.0, 115.8), ('sfx_walkie', 'qf_walkie', 6.0, 106.0),
    ('sfx_device', 'qf_device', 8.0, 111.9), ('sfx_bike', 'qf_bike', 13.8, 104.2), ('sfx_tyres_bike', 'qf_tyres_bike', 21.2, 77.3),
    ('sfx_road', 'qf_road', 21.5, 97.5), ('sfx_v8', 'qf_v8', 24.0, 94.0), ('sfx_tyres_v8', 'qf_tyres_v8', 54.9, 42.4),
    ('sfx_truck', 'qf_truck', 58.5, 3.5),
]
HIT_TIMES = [TL.T['take'], TL.T['chase'], TL.T['back'], TL.T['wall'], TL.T['mid_wall'], TL.T['last']]
# the music's own clock is beats: seconds / 0.5 at 120 BPM
SPB = 60.0 / BPM


def sfx_tracks():
    out = []
    for name, preset, t0, ln in SFX:
        out.append({'name': name, 'instrument': 'sfx:' + preset, 'role': 'fx', 'dc_hp_hz': 20.0,
                    'notes': [{'t': round(t0 / SPB, 4), 'd': round(ln / SPB, 4), 'p': 60, 'v': 1.0}]})
    out.append({'name': 'sfx_impacts', 'instrument': 'sfx:qf_impact', 'role': 'fx', 'dc_hp_hz': 20.0,
                'notes': [{'t': round(t / SPB, 4), 'd': 3.0 / SPB, 'p': 60, 'v': 1.0} for t in HIT_TIMES]})
    return out


# ---- staging: one table read by the presets, the sheet and the space ------------------------------------------------------------------------
STAGE = {
    'qf_basses': (0.0, 0.0, 1.5), 'qf_basses_pizz': (30.0, 0.0, 1.4), 'qf_tuba': (150.0, 0.0, 1.8), 'qf_bass_drum': (-25.0, 0.0, 2.2),
    'qf_timpani': (80.0, 0.0, 3.0), 'qf_taiko': (-130.0, 0.0, 3.2), 'qf_snare': (-80.0, 0.0, 2.6), 'qf_snare_b': (-105.0, 0.0, 2.9),
    'qf_cymbals': (-160.0, 30.0, 3.6), 'qf_low_swell': (0.0, 45.0, 1.0), 'qf_violas': (-55.0, 0.0, 2.0), 'qf_celli': (-62.0, 26.0, 2.6),
    'qf_violins_staccato': (-130.0, 30.0, 3.0), 'qf_violins_long': (180.0, 45.0, 4.0), 'qf_choir': (0.0, 60.0, 5.0),
    'qf_trombones': (-108.0, 15.0, 2.8), 'qf_piano_theme': (-30.0, 15.0, 1.8), 'qf_horns': (0.0, 15.0, 2.6),
}


def apply_staging():
    for name, (az, el, dist) in STAGE.items():
        p = os.path.join(PROJ, 'presets', 'instruments', name + '.json')
        d = json.load(open(p, encoding='utf-8'))
        d['spatial'].update(azimuth=az, elevation=el, distance=dist, space='quiet_frequency_room')
        json.dump(d, open(p, 'w', encoding='utf-8'), indent=2)


def sections_json():
    return [dict(name=n, role=r, start_bar=a, end_bar=bb, start_s=at(a), end_s=at(bb + 1), energy=e, camera=cam)
            for n, r, a, bb, e, cam in SECTIONS]


def hits():
    """The picture events, in seconds: every cut is on a bar line."""
    return [
        {'t': TL.T['take'], 'kind': 'musical', 'sync': 'hard', 'sound': 'the Hero takes the device: the pulse starts, a low timpani and a crash',
         'why': 'the story turns on this frame; the bike is a floor away'},
        {'t': TL.T['start_v8'], 'kind': 'musical', 'sync': 'soft', 'sound': 'the V8 wakes: timpani and the first ostinato bar',
         'why': 'the Villain finds the empty case; the pursuit has not started yet'},
        {'t': TL.T['chase'], 'kind': 'musical', 'sync': 'hard', 'sound': 'full orchestra, a crash and the cinematic impact on the wide shot',
         'why': 'the chase begins on the tunnel cut'},
        {'t': TL.T['flyover'], 'kind': 'musical', 'sync': 'soft', 'sound': 'the high angle: the room opens, a crash',
         'why': 'the camera climbs over the flyover'},
        {'t': TL.T['stop'], 'kind': 'cut', 'sync': 'hard', 'sound': 'the truck: the music, the engines and the room stop for a second',
         'silence_after_s': 1.0, 'why': 'the near miss: silence is the effect and the room is what sounds'},
        {'t': TL.T['back'], 'kind': 'musical', 'sync': 'hard', 'sound': 'everything returns on one downbeat: crash, impact, ostinato',
         'why': 'the cut after the truck'},
        {'t': TL.T['wall'], 'kind': 'musical', 'sync': 'hard', 'sound': 'the loudest bar of the cue: the barrier and the tunnel again',
         'why': 'the widest shot and the second peak, louder than the first'},
        {'t': TL.T['mid_wall'], 'kind': 'musical', 'sync': 'soft', 'sound': 'the car rams: timpani, crash and a lunge',
         'why': 'the Villain closes to a metre'},
        {'t': TL.T['dropout'], 'kind': 'cut', 'sync': 'hard', 'sound': 'the music leaves: two engines idle, the radio, a breath',
         'why': 'the pursuit stops without a winner'},
        {'t': TL.T['signal'], 'kind': 'musical', 'sync': 'soft', 'sound': 'the bike has stopped; the case opens; the device pulses',
         'why': 'the question the trailer ends on'},
        {'t': TL.T['last'], 'kind': 'musical', 'sync': 'hard', 'sound': 'one low hit, a bark of timpani and taiko on the front, then the ring',
         'why': 'the cut to black: nothing after the hit but the room and the device'},
    ]


def sheet():
    base = json.load(open(os.path.join(PROJ, 'direction', 'direction_sheet.json'), encoding='utf-8')) if os.path.exists(
        os.path.join(PROJ, 'direction', 'direction_sheet.json')) else {}
    base.pop('video', None)
    secs = sections_json()
    base.update({
        'title': 'Quiet Frequency',
        'job': 'a 120 s theatrical trailer for a 30-minute action short: the Hero steals a device that can control people, the Villain finds the '
               'case empty and hunts him down a highway, there are near misses and no rescue, and the last image is a case being opened',
        'purpose': 'make the viewer want to know what the device does and who else is listening, with no resolution',
        'point_of_view': "the Hero's, and the Villain's closing in from behind: the viewer is on the bike, hearing the car in the mirror",
        'piece_type': 'quiet_frequency', 'focus': 'melody',
        'tempo': {'bpm': BPM, 'note': '120 BPM: a bar is two seconds, so every hit lands on a whole second and the clock needs no tempo map'},
        'key': 'F minor', 'energy': 0.9,
        'sections': secs,
        'motifs': [{'name': 'the_cell', 'instrument': 'horns',
                    'shape': 'root, minor 3rd, fourth falling to the third, fifth: two bars; fragmented at the alert, whole in the chase, inverted in the '
                             'escalation, two notes at the end',
                    'why': 'four notes survive engine noise, a radio and a cut'}],
        'hits_at': [h['t'] for h in hits()], 'hits': hits(),
        'ending': 'combination',
        'ending_note': 'a low hit, a bark of timpani, a dominant C with a b9 that never resolves, and the device still pulsing: no fade, a cut to black',
        'feel': ['relentless', 'dangerous', 'curious'],
        'avoid_feel': ['triumphant', 'playful', 'comic'],
        'avoid_feel_note': 'no victory, no joke, no stunt: heavy, cold and plain, the way a large studio trailer plays a chase',
        'palette': ['strings: 16th ostinato in cellos and violas, staccato violins in the peaks', 'brass: horns on the cell, trombone stabs, tuba pedal',
                    'percussion: bass drum, timpani, taiko, snare, crashes', 'piano: a low pulse', 'choir: open fifths',
                    'sound design: a single-cylinder bike and a V8 car, tyres, a truck horn, a radio, a lab alarm, a heartbeat, a device'],
        'avoid_sounds': ['police siren', 'dialogue', 'stunt whooshes', 'comic effects'],
        'space': 'quiet_frequency_room',
        'mix_intent': {'hero': 'horns', 'leave_free_hz': []},
        'loudness_lufs': LOUDNESS, 'true_peak_max': -1.5,
        'delivery': {'format': 'wav', 'sample_rate': 48000, 'bit_depth': 24, 'stage': 'master'},
        'references': ['the Highway Pursuit cue: the same chase grammar, rewritten as a trailer with sound design in the arrangement'],
        'spatial_staging': {
            'front': ['horns', 'violins_staccato'], 'mid': ['violas', 'celli', 'trombones', 'piano_theme'],
            'low_front': ['basses', 'basses_pizz', 'tuba', 'bass_drum'], 'overhead': ['cymbals', 'choir'], 'rear': ['taiko', 'timpani'],
            'sound': ['the bike ahead of the camera, the V8 behind and beside it, the radio at the left ear'],
            'why': 'the bike is in front of the viewer and the car is in the mirror: that is what makes the seat uncomfortable rather than loud'},
        'intent': {'emotions': ['tense', 'dark_epic'], 'registers': ['cinematic', 'hybrid'], 'scenes': ['establish', 'build', 'chase', 'dread'],
                   'tensions': ['ostinato', 'pedal', 'cluster', 'silence_before', 'unresolved_dominant'], 'avoid': ['joyful', 'playful']},
        'harmony_plan': [{'section': s['name'], 'root': PLAN[s['start_bar']],
                          'move': {'the_lab': 'pedal F, a hint of Db at the end of the bar 6', 'the_take': 'Fm Db Ab Eb then the dominant C',
                                   'the_alert': 'Neapolitan Gb over F, then C', 'the_chase': 'Fm Db Ab Eb / Fm Db Bbm C',
                                   'the_flyover': 'F and Gb alternate, a cluster at the end', 'the_truck': 'a semitone cluster, then nothing',
                                   'the_escalation': 'the chase progression again, a fourth tighter', 'the_wall': 'Neapolitan Gb before the dominant',
                                   'the_dropout': 'a bare F pedal', 'the_signal': 'Fm Db Bbm C with a b9: unresolved'}[s['name']],
                          'why': 'each harmonic event is a picture event'} for s in secs],
    })
    base['expression'] = {
        'sonic_picture': {'first_10s': 'a lab at night: an alarm, a radio squelch, a pulse that speeds up, one low F',
                          'middle': 'the chase: a 16th ostinato that never stops, a V8 behind and a bike ahead, a second of nothing, a second peak louder than the first',
                          'last_note': 'one low hit and a ring, the device still pulsing on a dominant with a b9'},
        'performer': 'a session orchestra playing to picture and a sound-design team riding the engines: the music is conducted from a click, the engines from the rpm',
        'producer_moves': ['carve the music where the engines live and the engines where the horn lives, so both are heard',
                           'the engines duck 2-4 dB smoothly under the drums and come back over a second',
                           'leave a real second of nothing before the second peak'],
        'anti_generic': 'no riser-impact formula and no stunt gags: the opening is sound design, the middle is a chase, the silence is written, and the end is a question',
        'theme': {'name': 'the_cell', 'shape': 'up a third, a fourth that falls to the third, leap a fifth, settle on the third',
                  'variation_plan': 'fragmented in the alert, whole in the chase, inverted in the escalation, two notes at the end'},
        'cues': [{'section': s['name'], 'arousal': s['energy'], 'mode': 'F minor with Gb and a dominant C',
                  'tempo': '120', 'dynamics': f"mean velocity {vel(s['start_bar']):.2f}",
                  'articulation': 'spiccato strings, marcato brass, rolled timpani before a cut', 'timbre': 'cold, close, a dry low end'} for s in secs],
    }
    base['immersive'] = {
        'why': 'the chase surrounds the listener: the car comes up from behind and alongside, the truck passes through the field, the tunnel closes it, the flyover opens it',
        'anchors': [{'part': 'basses', 'why': 'the road is fixed under the viewer'}, {'part': 'horns', 'why': 'the Hero is ahead of the camera for the whole cue'}],
        'movers': [{'part': 'sfx_v8', 'why': 'the Villain closes from behind and alongside', 'path': 'behind and far, to behind and near, to the right side, to a metre at the ram'},
                   {'part': 'sfx_truck', 'why': 'the near miss', 'path': 'from far behind, past the right ear, to far in front'}],
        'height_plan': {'overhead': ['cymbals', 'choir'], 'low': ['basses', 'bass_drum'], 'why': 'height is for the shot, not for decoration'},
        'room_changes': [{'at_section': 'the_lab', 'why': 'a small hard room: the alarm and the radio are close and bright'},
                         {'at_section': 'the_take', 'why': 'the yard and the gate: the room opens'},
                         {'at_section': 'the_chase', 'why': 'a tunnel bore: loud, long, dark'},
                         {'at_section': 'the_flyover', 'why': 'the deck: the tail opens and the percussion lifts'},
                         {'at_section': 'the_truck', 'why': 'open road, a long dry tail for the one second of nothing'},
                         {'at_section': 'the_wall', 'why': 'the tunnel again, longer'},
                         {'at_section': 'the_dropout', 'why': 'open air: nothing near, the engines idle'},
                         {'at_section': 'the_signal', 'why': 'back to a small room: the case is open'}],
        'deliverables': ['stereo', 'immersive_7_1'],
    }
    return base


def gate_profile():
    return {
        'name': 'quiet_frequency',
        'character': 'a 120 s action trailer judged on its own acts: a sound-design opening that is allowed to be the quietest and sparsest part of the cue, a chase '
                     'that is allowed to be dense, loud and syncopated, one declared second of silence, a second peak louder than the first, and a last act that '
                     'drops the music and ends unresolved; the engines, the radio and the device are written into the arrangement and judged with it.',
        'extends': 'cinematic',
        'flags': [],
        'focus': {'roles': ['melody', 'lead', 'vocal'], 'label': 'the cell on the horns', 'reason': 'the cue is defined by a figure: four horns state it at each camera'},
        'scene': {'timeline': {'tolerance_s': 0.5}, 'roles': {
            'establish': {'bsi_mode': 'pocket'},
            'transition': {'arousal_max': 0.65, 'bsi_mode': 'pocket'},
            'build': {'huron_resolution_gravity': 'RELAX', 'strain_slope_min': 0.0, 'bsi_mode': 'pocket'},
            'peak': {'arousal_min': 0.6, 'surprise_min_z': 1.0, 'min_hits': 1, 'roughness_min_frac': 0.5, 'bsi_mode': 'pocket',
                     'huron_resolution_gravity': 'RELAX'},
            'rupture': {'bsi_mode': 'rupture', 'bsi_min': 1.5, 'surprise_min_z': 1.0, 'allow_intentional_silence': True},
            'release': {'strain_drop_min': 0.15, 'arousal_max': 0.55, 'huron_resolution_gravity': 'ENFORCE'},
            'button': {'arousal_max': 0.45, 'huron_resolution_gravity': 'ENFORCE'}}, 'dialogue': {}},
        'rows': {},
    }


def space():
    def geo(w, d, h, lx, ly, lz, mats=None):
        g = {'width_m': w, 'depth_m': d, 'height_m': h, 'listener': {'x': lx, 'y': ly, 'z': lz}}
        if mats:
            g['materials'] = mats
        return g
    tunnel = {'floor': 'underpass_concrete', 'ceiling': 'underpass_concrete', 'walls': 'underpass_concrete'}
    deck = {'floor': 'steel_deck', 'ceiling': 'open', 'walls': 'open'}
    lab = {'floor': 'underpass_concrete', 'ceiling': 'underpass_concrete', 'walls': 'brick_facade'}
    return {
        'name': 'quiet_frequency_room', 'kind': 'spaces',
        'character': 'A night highway and the lab it leaves: an open asphalt corridor between concrete barriers with a tunnel bore, a steel flyover deck and a small hard lab; the '
                     'orchestra and every engine and radio sit in the same room scene, so a camera move changes both.',
        'room': {'rt60': 1.3, 'pre_delay_ms': 14, 'hf_decay': 0.55, 'early_level': 0.40},
        'reflections': {
            'path_physics': True, 'ref_m': 1.5, 'ground_delay_ms': 6.0, 'ground_gain': 0.45, 'ground_cutoff_hz': 4200, 'lateral_delay_ms': 13.0,
            'lateral_gain': 0.5, 'lateral_cutoff_hz': 3600, 'ceiling_delay_ms': 26.0, 'ceiling_gain': 0.08, 'rear_delay_ms': 38.0, 'rear_gain': 0.28,
            'geometry': {'width_m': 26.0, 'depth_m': 400.0, 'height_m': 14.0, 'listener': {'x': 13.0, 'y': 120.0, 'z': 1.1},
                         'materials': {'floor': 'asphalt_wet', 'ceiling': 'open', 'walls': 'brick_facade'}, 'material_set': 'highway_materials',
                         'max_order': 3, 'max_taps': 16, 'min_level_db': -34.0},
            'late': {'enabled': True, 'rt60_s': 1.3, 'hf_decay': 0.55, 'level_db': -23.0, 'count': 8, 'spread_deg': 100.0, 'rise_s': 0.02, 'seed': 6061},
        },
        'scenes': [
            {'anchor': {'section': 'the_lab'}, 'transition_s': 0.4,
             'space_overrides': {'geometry': geo(8.0, 11.0, 3.4, 4.0, 5.0, 1.6, lab), 'late': {'rt60_s': 0.9, 'level_db': -22.0}}},
            {'anchor': {'section': 'the_take'}, 'transition_s': 0.8,
             'space_overrides': {'geometry': geo(30.0, 60.0, 8.0, 15.0, 20.0, 1.4), 'late': {'rt60_s': 1.5, 'level_db': -23.0}}},
            {'anchor': {'section': 'the_alert'}, 'transition_s': 0.8,
             'space_overrides': {'geometry': geo(26.0, 400.0, 14.0, 13.0, 120.0, 1.1), 'late': {'rt60_s': 1.3, 'level_db': -23.0}}},
            {'anchor': {'section': 'the_chase'}, 'transition_s': 1.2,
             'space_overrides': {'geometry': geo(12.0, 300.0, 6.5, 6.0, 90.0, 1.1, tunnel), 'late': {'rt60_s': 2.7, 'level_db': -15.0, 'hf_decay': 0.35}}},
            {'anchor': {'section': 'the_flyover'}, 'transition_s': 1.5,
             'space_overrides': {'geometry': geo(40.0, 600.0, 60.0, 20.0, 200.0, 9.0, deck), 'late': {'rt60_s': 2.2, 'level_db': -19.0, 'hf_decay': 0.45}}},
            {'anchor': {'section': 'the_truck'}, 'transition_s': 0.3,
             'space_overrides': {'geometry': geo(26.0, 400.0, 14.0, 13.0, 120.0, 1.1), 'late': {'rt60_s': 3.2, 'level_db': -12.0}}},
            {'anchor': {'section': 'the_escalation'}, 'transition_s': 0.6,
             'space_overrides': {'geometry': geo(26.0, 400.0, 14.0, 13.0, 120.0, 1.1), 'late': {'rt60_s': 1.3, 'level_db': -23.0}}},
            {'anchor': {'section': 'the_wall'}, 'transition_s': 1.0,
             'space_overrides': {'geometry': geo(12.0, 300.0, 6.5, 6.0, 90.0, 1.1, tunnel), 'late': {'rt60_s': 3.0, 'level_db': -14.0, 'hf_decay': 0.33}}},
            {'anchor': {'section': 'the_dropout'}, 'transition_s': 1.2,
             'space_overrides': {'geometry': geo(60.0, 600.0, 30.0, 30.0, 100.0, 1.2), 'late': {'rt60_s': 0.9, 'level_db': -28.0}}},
            {'anchor': {'section': 'the_signal'}, 'transition_s': 1.5,
             'space_overrides': {'geometry': geo(8.0, 11.0, 3.4, 4.0, 5.0, 1.6, lab), 'late': {'rt60_s': 1.4, 'level_db': -17.0}}},
        ],
        'distance': {'ref_m': 1.5, 'falloff': 0.18, 'air_damping': 0.42, 'min_cutoff_hz': 3200, 'reverb_exponent': 0.62,
                     'pre_delay_law': {'base_ms': 11.0, 'per_m': 1.4, 'max_ms': 28.0}},
        'binaural': {'bed': False, 'spot': True},
        'sources': ['KB cinematic-hybrid-scoring: pressure is a deliverable, a hit that stops the music is declared',
                    'KB sfx-ambience: sound effects and music share one room and one reverb send and are carved in each other\'s bands',
                    'Room physics: the tunnel, the deck and the lab are the same engine scene module (scripts/phys_core) with geometry, materials and a late field',
                    'Barrier and asphalt materials come from the shipped static-scene material set'],
    }


def write(path, obj):
    full = os.path.join(PROJ, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)
    print('wrote', os.path.relpath(full, ROOT))


def main():
    apply_staging()
    write('presets/spaces/quiet_frequency_room.json', space())
    write('presets/gate/quiet_frequency.json', gate_profile())
    write('direction/direction_quiet_frequency.json', sheet())
    tracks = [{'name': n, 'instrument': inst, 'role': role, 'notes': clean(fn())} for n, inst, role, fn in TRACKS] + sfx_tracks()
    score = {
        'title': 'Quiet Frequency', 'bpm': BPM, 'ts': TS, 'seed': 6061, 'humanize': 'natural', 'key': 'F', 'mode': 'minor',
        'space': 'quiet_frequency_room', 'mix_preset': 'quiet_frequency_mix', 'output_targets': ['stereo', 'immersive_7_1'],
        'master': {'lufs': LOUDNESS, 'true_peak': -1.5, 'tone': 'theatrical', 'fade_out': 0.6},
        'piece_type': 'quiet_frequency', 'focus': 'melody',
        'intent': {'emotions': ['tense', 'dark_epic'], 'registers': ['cinematic', 'hybrid'], 'scenes': ['establish', 'build', 'chase', 'dread'],
                   'tensions': ['ostinato', 'pedal', 'cluster', 'silence_before', 'unresolved_dominant'], 'avoid': ['joyful', 'playful']},
        'mix_intent': {'hero': 'horns', 'leave_free_hz': []},
        'medium': {'model': 'iso9613', 'state': {'temperature_k': 291.15, 'pressure_pa': 101325, 'rh_percent': 70}},
        'plan': {'sections': sections_json()},
        'tracks': tracks, 'mix': {'tracks': {}},
    }
    write('scores/quiet_frequency_score.json', score)
    print('notes:', sum(len(t['notes']) for t in score['tracks']), 'duration_s', at(BARS + 1))


if __name__ == '__main__':
    main()
