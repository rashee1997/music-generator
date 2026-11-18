#!/usr/bin/env python3
"""compose_main.py - writes scores/the_temple_wakes_score.json for "The Temple Wakes".

Only notes and choices live here: which pitch, which beat, which preset. Every sound, level, room and placement is in
presets/ (instruments, environments, sfx, calls, spaces, mix); the intent is in direction/.

Time: beats of a 4/4 bar, 1-based bars; 52 bars on a tempo map that never slows until the cut (84 -> 138 BPM).
Mode: D with a flat second (Eb) and a minor third. The unease is the semitone D / Eb, held in the pedal, flickering in the
ostinato, stacked in the clusters. Pressure carriers (knowledgebase/genre-and-feel/cinematic-hybrid-scoring.md, section 1):
a pulse that does not stop from bar 5, low brass and sub weight at the turning points, percussion that is constant from
bar 9, and a rising device (the violin line climbs a semitone a bar in the awakening). The last section ends on a cut.

    bars  1- 8  the_approach    night jungle, a D pedal, a heartbeat, the first wrong sound
    bars  9-20  the_stairs      the temple appears: a conch, steps on stone, the chirped echo, the pulse doubles
    bars 21-32  the_descent     a stone door grinds open, drips, braam, the passage narrows, a held breath
    bars 33-44  the_awakening   the temple wakes: tutti, drums, the horns' theme, a whistle, the violins climb
    bars 45-52  the_run         everything at once, then the door slams and the music is cut
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'scores', 'the_temple_wakes_score.json')
rng = np.random.default_rng(1519)

BB = 4
TOTAL_BARS = 52


def B(bar, beat=0.0):
    """Absolute beat of a 1-based bar and a beat inside it."""
    return (bar - 1) * BB + beat


# ---------------------------------------------------------------- harmony: one chord per bar (root pitch class, quality)
D, Eb, F, Gb, G, Ab, A, Bb, C, Db = 2, 3, 5, 6, 7, 8, 9, 10, 0, 1
CH = {}
for b in range(1, 9):
    CH[b] = (D, 'm')
for b, c in zip(range(9, 21), [(D, 'm'), (Eb, 'M'), (D, 'm'), (C, 'M')] * 3):
    CH[b] = c
for b, c in zip(range(21, 33), [(Bb, 'M'), (Eb, 'M'), (A, 'm'), (D, 'm')] * 3):
    CH[b] = c
for b, c in zip(range(33, 45), [(D, 'm'), (Eb, 'M'), (Bb, 'M'), (C, 'M')] * 3):
    CH[b] = c
for b, c in zip(range(45, 53), [(D, 'm'), (Eb, 'M')] * 4):
    CH[b] = c
for b in (50, 51, 52):
    CH[b] = (D, 'm')                        # the last bars close on D: the door shuts home, and the cut follows


def near(pc, lo, hi):
    for p in range(lo, hi + 1):
        if p % 12 == pc:
            return p
    raise ValueError((pc, lo, hi))


VEL_FLOOR = 0.42        # a sampled pp sits far under its ff; a played velocity never goes below this


def N(t, d, p, v, **kw):
    v = VEL_FLOOR + (1.0 - VEL_FLOOR) * min(1.0, max(0.0, v))
    return dict(t=round(float(t), 4), d=round(float(d), 4), p=int(p), v=round(float(v), 3), **kw)


# ---------------------------------------------------------------- ostinato cells: the rhythm is kept, the pitches follow the chord; 1 is the flat second
CELLS8 = [[0, 0, 1, 0, 7, 0, 1, 0], [0, 7, 0, 1, 0, 7, 10, 7], [0, 0, 0, 1, 0, 0, 7, 12], [0, 1, 0, 0, 7, 0, 12, 7]]
CELLS16 = [[0, 0, 1, 0, 0, 0, 7, 0, 0, 1, 0, 0, 12, 0, 7, 0],
           [0, 1, 0, 0, 0, 7, 0, 1, 0, 0, 7, 0, 0, 12, 10, 7],
           [0, 0, 0, 1, 0, 0, 7, 0, 0, 10, 0, 0, 1, 0, 12, 7],
           [0, 0, 1, 0, 0, 7, 0, 0, 10, 0, 0, 1, 0, 12, 0, 7]]
ACCENT16 = {0: 0.14, 3: 0.08, 6: 0.08, 8: 0.06, 10: 0.06, 12: 0.06}      # a 3+3+2 grouping inside the bar


def ostinato(bars, grid, vel_a, vel_b, lo, hi, drop=0.0, stop_at=None):
    """grid 8 or 16: notes per bar. Velocity ramps vel_a -> vel_b across `bars`."""
    out, n = [], len(bars)
    for i, bar in enumerate(bars):
        root, q = CH[bar]
        base = near(root, lo, hi)
        cell = (CELLS8 if grid == 8 else CELLS16)[int(rng.integers(0, 4))]
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


tracks = []


def track(name, instrument, role, notes, **extra):
    tracks.append(dict(name=name, instrument=instrument, role=role, notes=notes, **extra))


STAIRS = B(9)
DESCENT = B(21)          # braam 1 and the stone door
BRAAM2 = B(29)           # the slab drops
HELD = B(32, 2.0)        # everything stops for two beats
AWAKE = B(33)            # braam 3: the temple wakes
RUN = B(45)              # braam 4
SLAM = B(51)             # the door shuts: the music is cut
CUT = B(51, 2.0)

# ================================================================ strings
bs = [N(B(1) + 8.0 * k - (0.4 if k else 0.0), 8.4, 26, 0.62 + 0.03 * k) for k in range(4)]          # the D pedal, re-struck every 8 beats
for bar in range(9, 21):
    bs.append(N(B(bar), 4.06, near(CH[bar][0], 26, 37), 0.72 + 0.02 * (bar - 9)))
for bar in range(21, 32):
    bs.append(N(B(bar), 4.06, near(CH[bar][0], 26, 37), min(1.0, 0.88 + 0.012 * (bar - 21))))
bs.append(N(B(32), 2.0, 26, 0.95))
for bar in range(33, 51):
    bs.append(N(B(bar), 4.06, near(CH[bar][0], 26, 37), 0.95))
bs.append(N(B(51), 2.0, 26, 1.0))
track('basses', 'maya_basses', 'bass', bs)

ce = ostinato(range(5, 9), 8, 0.58, 0.68, 38, 49, drop=0.25)
ce += ostinato(range(9, 17), 8, 0.66, 0.78, 38, 49)
ce += ostinato(range(17, 21), 16, 0.62, 0.8, 38, 49)
ce += ostinato(range(21, 32), 16, 0.78, 0.95, 38, 49)
ce += ostinato([32], 16, 0.95, 1.0, 38, 49, stop_at=HELD)
ce += ostinato(range(33, 51), 16, 0.95, 1.0, 38, 49)
ce += ostinato([51], 16, 1.0, 1.0, 38, 49, stop_at=CUT)
ce = [dict(n, p=n['p'] - 1) if (n['t'] >= B(50) and n['p'] % 12 == Eb) else n for n in ce]          # no flat second in the last two bars
track('celli', 'maya_celli_ostinato', 'ostinato', ce)

va = []
for bar in list(range(17, 32)) + list(range(33, 51)):
    root, q = CH[bar]
    base = near(root, 50, 62)
    pos = [2, 6, 7, 10, 14, 15] if bar >= 33 else [2, 6, 10, 14]
    for k in pos:
        va.append(N(B(bar, k * 0.25), 0.2, base + (7 if k in (7, 15) else 12 if k in (6, 14) else 1 if k == 2 else 0),
                    (0.7 if bar >= 33 else 0.45) + rng.normal(0, 0.03)))
va = [dict(n, p=n['p'] - 1) if (n['t'] >= B(50) and n['p'] % 12 == Eb) else n for n in va]
track('violas', 'maya_violas_ostinato', 'arp', va)

vt = []
for bar in range(3, 9):
    vt.append(N(B(bar), 3.95, 86 if bar % 2 else 87, 0.5 + 0.03 * (bar - 3)))
for bar in range(9, 21):
    step = (bar - 9) // 4
    vt += [N(B(bar), 3.95, 86 + step, 0.58 + 0.015 * (bar - 9)), N(B(bar), 3.95, 87 + step, 0.55 + 0.015 * (bar - 9))]
for bar in range(21, 32):
    vt += [N(B(bar), 3.95, 85 + (bar % 3), 0.55 + 0.02 * (bar - 21)), N(B(bar), 3.95, 86 + (bar % 3), 0.5 + 0.02 * (bar - 21))]
for bar in range(33, 50):
    vt += [N(B(bar), 3.95, 86, 0.8), N(B(bar), 3.95, 87, 0.78)]
vt += [N(B(50), 3.95, 86, 0.9), N(B(50), 3.95, 81, 0.88)]
track('violins_tremolo', 'maya_violins_tremolo', 'pad', vt)

vs = [N(B(bar), 3.95, 74 + (bar - 33), 0.55 + 0.035 * (bar - 33)) for bar in range(33, 45)]               # the rising device
vs += [N(B(bar), 3.95, 86 - (bar % 2), 0.95) for bar in range(45, 51)]
track('violins_sustain', 'maya_violins_sustain', 'pad', vs)

# ================================================================ brass
hn = []
for bar in range(9, 21, 2):                                                    # long pedal swells: D then the flat second
    hn.append(N(B(bar), 7.9, near(D, 53, 67), 0.5 + 0.03 * (bar - 9)))
theme = {33: [(62, 1.5), (63, 0.5), (62, 2.0)], 34: [(63, 1.5), (65, 0.5), (63, 2.0)], 35: [(62, 1.0), (70, 1.0), (69, 2.0)], 36: [(67, 1.5), (63, 0.5), (62, 2.0)]}
for k, bar in enumerate(range(33, 45)):
    seq = theme[33 + (k % 4)]
    t0 = B(bar)
    for p, d in seq:
        hn.append(N(t0, d * 0.98, p + (12 if bar >= 41 else 0), 0.78 + 0.01 * k))
        t0 += d
for bar in range(45, 51):
    for b in range(4):
        hn.append(N(B(bar, b), 0.9, near(CH[bar][0], 55, 66), 0.92))
track('horns', 'maya_horns', 'melody', hn)

tb_sus = []
for beat, dur in ((DESCENT, 7.0), (BRAAM2, 7.0), (AWAKE, 7.0), (RUN, 7.0)):
    tb_sus += [N(beat, dur, p, 1.0) for p in (50, 57, 62, 63)]
tb_sus += [N(SLAM, 2.0, p, 1.0) for p in (50, 57, 62)]
track('trombones_sus', 'maya_trombones_sus', 'pad', tb_sus)

tb = []
STABS = {16: ((0, 1.9), (2.5, 0.9)), 19: ((0, 1.4), (3.0, 0.9)), 24: ((0, 1.9), (2.0, 0.9)), 27: ((0, 1.4), (3.0, 0.9)), 31: ((0, 1.4), (3.0, 0.9))}
for bar in list(range(34, 45)) + list(range(46, 51)):
    STABS[bar] = ((0, 1.4), (2.5, 0.9))
for bar, pat in STABS.items():
    r = near(CH[bar][0], 48, 59)
    for off, d in pat:
        vv = 1.0 if off == 0 else 0.55 + 0.25 * float(rng.random())
        tb += [N(B(bar, off), d, r, vv), N(B(bar, off), d, r + 7, vv - 0.05)]
track('trombones', 'maya_trombones', 'chord', tb)

tu = [N(beat, 7.0, 38, 1.0) for beat in (DESCENT, BRAAM2, AWAKE, RUN)] + [N(SLAM, 2.0, 38, 1.0)]
tu += [N(B(bar), 3.9, near(CH[bar][0], 30, 43), 0.85) for bar in (13, 17, 25, 37, 41, 47, 49)]
track('tuba', 'maya_tuba', 'bass', tu)

# ================================================================ percussion
def tp(bar, beat, d, v, root=None):
    return N(B(bar, beat), d, near(CH[bar][0] if root is None else root, 36, 47), v)


ti = []
for bar in range(3, 9):                                                         # the heartbeat
    ti += [tp(bar, 0, 0.4, 0.4 + 0.02 * bar), tp(bar, 0.75, 0.4, 0.28 + 0.02 * bar)]
for bar in range(9, 21):
    ti += [tp(bar, 0, 0.4, 0.6 + 0.02 * (bar - 9)), tp(bar, 0.75, 0.4, 0.42), tp(bar, 2, 0.4, 0.5), tp(bar, 2.75, 0.4, 0.36)]
ROLLS = (20, 28)                                                                # rolls into the braams replace the pattern in their last two beats
ti = [n for n in ti if not any(B(r, 2.0) <= n['t'] < B(r + 1) for r in ROLLS)]
for r in ROLLS:
    ti += [tp(r, 2.0 + 0.25 * k, 0.2, 0.45 + 0.5 * (k / 7.0) ** 1.6 + (0.04 if k % 2 == 0 else -0.04)) for k in range(8)]
for bar in range(21, 32):
    for off, v in ((0, 0.95), (1.5, 0.7), (3, 0.8)):
        if bar in (28,) and off >= 2:
            continue
        ti.append(tp(bar, off, 0.4, v))
ti += [tp(32, 0, 0.4, 0.9), tp(32, 1.0, 0.4, 0.7)]
for bar in range(33, 51):                                                       # 3+3+2 in eighths: the temple's pulse
    for k, v in ((0, 1.0), (3, 0.85), (6, 0.9)):
        ti.append(tp(bar, k * 0.5, 0.4, v))
    if bar % 2 == 0:
        ti += [tp(bar, 3.25 + 0.25 * k, 0.2, 0.62 + 0.07 * k) for k in range(3)]
ti += [tp(51, 0, 0.6, 1.0)]
track('timpani', 'maya_timpani', 'drum', ti)

bd = [N(beat, 1.0, 48, 1.0) for beat in (DESCENT, BRAAM2, AWAKE, RUN, SLAM)]
BRAAMS = {DESCENT, BRAAM2, AWAKE, RUN, SLAM}
for bar in range(23, 32):
    bd += [N(B(bar, o), 1.0, 48, v) for o, v in ((0, 0.6 + 0.03 * (bar - 23)), (2.0, 0.45)) if B(bar, o) not in BRAAMS]
for bar in range(34, 51):
    bd += [N(B(bar, o), 1.0, 48, v) for o, v in ((0, 0.9), (1.5, 0.7), (3.0, 0.8)) if B(bar, o) not in BRAAMS]
track('bass_drum', 'maya_bass_drum', 'drum', bd)

cy = [N(beat - 4.0, 4.0, 50, 0.7) for beat in (DESCENT, BRAAM2, AWAKE, RUN)] + [N(beat, 5.0, 59, 0.6) for beat in (DESCENT, AWAKE, RUN)]
cy += [N(SLAM, 4.0, 60, 0.8)]
track('cymbals', 'maya_cymbals', 'texture', cy)

dl, dr = [], []
POOL_L = [(0, 1.5, 3.0), (0, 1.5, 2.5), (0.5, 2.0, 3.0), (0, 3.0), (1.0, 2.5, 3.5), (0, 0.75, 2.0, 3.0)]
POOL_R = [(0.5, 2.0, 3.5), (1.0, 2.5), (0.5, 1.25, 2.0, 2.75, 3.5), (0, 1.5, 3.5), (0.75, 2.25), (0.5, 1.5, 2.25, 3.25)]


def conga(pool, bar, vel, notes):
    pat = pool[int(rng.integers(0, len(pool)))]
    for i, o in enumerate(pat):
        key = (48, 50, 53)[int(rng.choice([0, 1, 2], p=[0.5, 0.35, 0.15]))]
        notes.append(N(B(bar, o), 0.4, key, vel * (1.0 if i == 0 else 0.62 + 0.3 * float(rng.random()))))


for bar in (13, 15, 17, 19):
    conga(POOL_L if bar % 4 == 1 else POOL_R, bar, 0.34, dl if bar % 4 == 1 else dr)
for bar in range(23, 32, 2):
    conga(POOL_L, bar, 0.4, dl)
for bar in range(34, 51):
    conga(POOL_L if bar % 2 == 0 else POOL_R, bar, min(0.9, 0.4 + 0.03 * (bar - 34)), dl if bar % 2 == 0 else dr)
track('drums_left', 'maya_drums_left', 'drum', dl)
track('drums_right', 'maya_drums_right', 'drum', dr)

# ================================================================ choir: a cluster, never a chord
ch = []
for bar in range(25, 32):
    ch += [N(B(bar), 3.95, p, 0.55 + 0.04 * (bar - 25)) for p in (62, 63, 69)]
for bar in range(33, 45):
    ch += [N(B(bar), 3.95, p, 0.7 + 0.01 * (bar - 33)) for p in (62, 63, 66, 69)]
for bar in range(45, 50):
    ch += [N(B(bar), 3.95, p, 0.95) for p in (63, 66, 69, 74)]
ch += [N(B(50), 3.95, p, 0.95) for p in (62, 69, 74)]
track('choir', 'maya_choir', 'pad', ch)


# ================================================================ places, calls and single sounds
def env(name, preset, t0, d, role='environment', **extra):
    track(name, f'env:{preset}', role, [dict(t=float(t0), d=float(d), p=60, v=1.0)], **extra)


env('night', 'maya_night', 0.0, B(21, 2.0), fade_out_s=8.0)
env('temple_air', 'maya_temple_air', B(19), 208.0 - B(19) - 2.0, fade_in_s=6.0, fade_out_s=1.0)


def call(name, preset, t0, d, az, el, dist, **kw):
    sp = dict(azimuth=az, elevation=el, distance=dist, kind='spot', binaural=True)
    track(name, f'env:{preset}', 'environment', [dict(t=float(t0), d=float(d), p=60, v=1.0)], spatial=sp, fade_in_s=0.04, fade_out_s=0.04, **kw)


call('whistle_1', 'maya_whistle', B(7, 2.0), 4.0, -110, 5, 18.0)
call('whistle_2', 'maya_whistle', B(26, 1.0), 4.0, 130, 5, 12.0)
call('whistle_3', 'maya_whistle', B(37, 0.0), 4.0, -90, 8, 6.0)
call('whistle_4', 'maya_whistle', B(47, 1.0), 4.0, 100, 5, 3.0)
call('conch_1', 'maya_conch', B(9, 0.0), 7.0, 150, 0, 22.0)
call('conch_2', 'maya_conch', B(21, 0.5), 7.0, -150, 0, 16.0)
call('conch_3', 'maya_conch', B(33, 0.0), 7.0, 0, 0, 10.0)
call('chirp_1', 'maya_chirp', B(11, 0.0), 3.0, 0, 10, 9.0)
call('chirp_2', 'maya_chirp', B(17, 1.0), 3.0, 20, 10, 7.0)
call('chirp_3', 'maya_chirp', B(23, 2.0), 3.0, -20, 10, 7.0)
call('chirp_4', 'maya_chirp', B(39, 2.0), 3.0, 0, 12, 6.0)
call('jaguar_far', 'maya_jaguar', B(5, 2.5), 5.4, 150, 0, 16.0)
call('jaguar_near', 'maya_jaguar', B(15, 2.0), 7.9, -120, 0, 6.0)


def steps(name, times, az, dist, vel=0.7, jitter=0.03):
    notes = [dict(t=round(float(t + rng.normal(0, jitter)), 4), d=0.8, p=60, v=round(float(np.clip(vel + rng.normal(0, 0.06), 0.3, 1.0)), 3))
             for t in times]
    track(name, 'sfx:maya_step_stone', 'fx', notes, spatial=dict(azimuth=az, elevation=-15, distance=dist, kind='spot', binaural=True))


climb = [B(11) + k * 1.0 for k in range(0, 36)]                                       # up the stairs, one a beat
slow = [B(22) + k * 2.0 for k in range(0, 20)]                                          # down the passage, afraid
run = [B(45) + k * 0.5 for k in range(0, 24)]                                            # running
steps('steps_left', sorted(climb[0::2] + slow[0::2] + run[0::2]), -8, 2.6, 0.72)
steps('steps_right', sorted(climb[1::2] + slow[1::2] + run[1::2]), 8, 2.6, 0.72)
for t in tracks:
    if t['name'] in ('steps_left', 'steps_right'):
        t['notes'] = [n for n in t['notes'] if not (B(20, 0) <= n['t'] < B(22, 0)) and not (HELD - 1.0 <= n['t'] < B(33, 2.0))]

track('twig_snap', 'sfx:maya_twig_snap', 'fx', [dict(t=B(8, 3.0), d=2.6, p=60, v=1.0)], spatial=dict(azimuth=-22, elevation=0, distance=2.2, kind='spot', binaural=True))
track('stone_door', 'sfx:maya_stone_door', 'fx', [dict(t=B(21, 1.0), d=12.0, p=60, v=0.9)], spatial=dict(azimuth=0, elevation=0, distance=6.0, kind='spot', binaural=True))
track('stone_slam', 'sfx:maya_stone_slam', 'fx', [dict(t=BRAAM2, d=10.0, p=60, v=1.0), dict(t=AWAKE, d=10.0, p=60, v=0.8), dict(t=SLAM, d=10.0, p=60, v=1.0)],
      spatial=dict(azimuth=0, elevation=0, distance=5.0, kind='spot', binaural=True))
track('rattle', 'sfx:maya_rattle', 'fx', [dict(t=t, d=3.0, p=60, v=0.7) for t in (B(35, 1), B(38, 2), B(41, 0), B(43, 0.5))],
      spatial=dict(azimuth=70, elevation=0, distance=4.0, kind='spot', binaural=True))
env('drips', 'maya_drips', B(22), B(31, 2.0) - B(22), fade_in_s=2.0, fade_out_s=2.0)
track('heartbeat', 'sfx:heartbeat', 'fx', [dict(t=B(2) + k * 1.4, d=1.2, p=60, v=0.32 + 0.012 * k) for k in range(18)],
      spatial=dict(azimuth=0, elevation=-5, distance=0.8, kind='spot', binaural=True))
track('risers', 'sfx:riser', 'fx', [dict(t=beat - 4.0, d=4.0, p=60, v=0.7) for beat in (DESCENT, BRAAM2, AWAKE, RUN)],
      spatial=dict(azimuth=0, elevation=20, distance=8.0, kind='bed'))
track('booms', 'sfx:boom', 'fx', [dict(t=beat, d=2.0, p=60, v=0.9) for beat in (DESCENT, BRAAM2, AWAKE, RUN, SLAM)],
      spatial=dict(azimuth=0, elevation=0, distance=3.0, kind='bed'))
for _t in tracks:
    if _t['name'] in ('heartbeat', 'booms', 'risers', 'stone_slam', 'stone_door'):
        _t['dc_hp_hz'] = 45.0                          # sub-bass effects carry energy below 25 Hz that shows as stem drift

# ================================================================ the score
dynamics = [[0, 0.3], [32, 0.45], [64, 0.6], [80, 0.75], [100, 0.85], [124, 0.95], [126, 0.2], [128, 1.0], [160, 1.0], [176, 1.0], [199, 1.0], [202, 1.0]]
sections = [dict(name='the_approach', start_bar=1, end_bar=8, energy=0.35), dict(name='the_stairs', start_bar=9, end_bar=20, energy=0.6),
            dict(name='the_descent', start_bar=21, end_bar=32, energy=0.8), dict(name='the_awakening', start_bar=33, end_bar=44, energy=1.0),
            dict(name='the_run', start_bar=45, end_bar=52, energy=1.0)]
score = dict(
    title='The Temple Wakes', bpm=90, ts=[4, 4], seed=1519, humanize='natural', key='D', mode='minor',
    tempo_points=[[0, 84], [32, 88], [64, 96], [80, 104], [124, 108], [128, 120], [160, 128], [176, 132], [200, 138]],
    dynamics=dynamics, space='maya_temple_room', mix_preset='the_temple_wakes_mix',
    output_targets=['stereo', 'mono', 'immersive_5_1', 'immersive_7_1_4', 'ambix', 'adm_bw64'],
    master=dict(lufs=-13.0, true_peak=-1.6, tone='neutral', fade_out=0.6),
    piece_type='cinematic', focus='melody',
    intent=dict(emotions=['adventure', 'tense', 'wonder'], registers=['cinematic', 'natural'], scenes=['dread', 'chase', 'reveal'],
                tensions=['ostinato', 'pedal', 'silence_before', 'unresolved_dominant'], avoid=['joyful', 'playful']),
    mix_intent=dict(hero='horns', leave_free_hz=[700, 2600]),
    plan=dict(sections=sections, ending=dict(fade_out=0.6)),
    tracks=tracks,
    mix=dict(tracks={}),
)
import sys
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'scripts'))
import humanize as hz
TM = hz.tempo_map_for(score, seed=score['seed'])
for sec in sections:
    sec['start_s'] = round(float(TM.sec((sec['start_bar'] - 1) * BB)), 3)
    sec['end_s'] = round(float(TM.sec(sec['end_bar'] * BB)), 3)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(score, f, indent=1)
print(f'wrote {os.path.relpath(OUT, os.getcwd())}: {len(tracks)} tracks, {sum(len(t["notes"]) for t in tracks)} notes')

if __name__ == '__main__':
    for name, beat in (('stairs', STAIRS), ('descent', DESCENT), ('braam 2', BRAAM2), ('held breath', HELD), ('awakening', AWAKE),
                       ('run', RUN), ('slam', SLAM), ('cut', CUT)):
        print(f'  {name:12s} beat {beat:6.1f}  {float(TM.sec(beat)):6.2f} s')
    for s in sections:
        print(f'  section {s["name"]:14s} {s["start_s"]:6.2f} - {s["end_s"]:6.2f} s')
