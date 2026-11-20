"""Writes scores/confluence_score.json: the notes of the one-minute ringtone and nothing else.

Sound, EQ, placement and room live in presets/; intent lives in direction/. A track here names a preset and a role and
carries notes. Run:  python projects/ringtone_confluence/scripts/compose_ringtone.py

The piece is in D major pentatonic [D E F# A B]: the same five notes are Mohanam / Bhupali (Indian), Gong (Chinese) and
the African pentatonic, and the scale has no half-step, so no two notes of the piece can rub. Every chord is built from
those five notes. 120 BPM in 4/4: a bar is 2 s and thirty bars are 60 s. The piece ends with a natural ring-out on the tonic.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'scores', 'confluence_score.json')
BAR = 4.0
rng = random.Random(7)                     # fixed: the same score every run

SCALE_PC = (2, 4, 6, 9, 11)                # D E F# A B


def up(p, steps=1):
    """The pentatonic note `steps` scale steps above MIDI note p (p is a scale note)."""
    for _ in range(steps):
        p += 1
        while p % 12 not in SCALE_PC:
            p += 1
    return p


def bt(bar, off=0.0):
    return (bar - 1) * BAR + off


def N(t, d, p, v, **kw):
    n = dict(t=round(float(t), 4), d=round(float(d), 4), p=p, v=int(max(1, min(127, round(v)))))
    n.update(kw)
    return n


# ---------------------------------------------------------------------------------------------------- the harmony
CHORDS = {1: 'Dadd9', 2: 'Bm7', 3: 'Asus2', 4: 'D6',
          5: 'Dadd9', 6: 'Bm7', 7: 'Esus4', 8: 'Asus2',
          9: 'Bm7', 10: 'Asus2', 11: 'D6', 12: 'Esus4', 13: 'Bm7', 14: 'Asus2', 15: 'Dadd9', 16: 'Esus4',
          17: 'D6', 18: 'Esus4', 19: 'Bm7', 20: 'Asus2', 21: 'D6', 22: 'Esus4',
          23: 'Dadd9', 24: 'Dadd9',
          25: 'Dadd9', 26: 'Bm7', 27: 'Asus2', 28: 'D6',
          29: 'D6', 30: 'Dadd9'}
# Open voicings: fifths, fourths and thirds, never a whole tone between neighbours in the low register (A3 against B3 beats
# against itself: the roughness row measured it). The pitches come from the five-note scale, so nothing here can rub.
PAD = {'Dadd9': [50, 57, 66, 76], 'Bm7': [59, 66, 69, 74], 'Asus2': [57, 64, 71, 76], 'D6': [57, 62, 66, 71],
       'Esus4': [59, 64, 69, 76]}
BASS = {'Dadd9': (50, 57), 'Bm7': (47, 54), 'Asus2': (45, 52), 'D6': (50, 57), 'Esus4': (52, 59)}   # root, fifth: octave 2-3
OUD = {'Dadd9': (50, 57, 62), 'Bm7': (59, 62, 66), 'Asus2': (57, 64, 69), 'D6': (50, 57, 66), 'Esus4': (52, 59, 64)}

# ---------------------------------------------------------------------------------------------------- the hook
# (beat, length, pitch, velocity) over four bars: a question (bars 1-2) and an answer (bars 3-4). Long notes sit on chord
# tones of Dadd9 | Bm7 | Asus2 | D6; everything else is short and passing.
HOOK = [(0.0, 0.5, 69, 76), (0.5, 0.5, 74, 78), (1.0, 0.5, 76, 80), (1.5, 1.5, 78, 86), (3.0, 0.5, 76, 72), (3.5, 0.5, 74, 70),
        (4.0, 1.5, 71, 80), (5.5, 0.5, 74, 74), (6.0, 1.0, 78, 84), (7.0, 0.5, 76, 72), (7.5, 0.5, 69, 70),
        (8.0, 0.5, 69, 76), (8.5, 0.5, 74, 78), (9.0, 0.5, 76, 80), (9.5, 1.5, 81, 90), (11.0, 0.5, 78, 74), (11.5, 0.5, 76, 70),
        (12.0, 2.0, 74, 84), (14.0, 1.0, 71, 74), (15.0, 0.5, 69, 70)]


def phrase(bar, line, octave=0, vel=1.0, shift=0.0, scoop=False, trill=False, rel_from=0.0, rel_to=16.0, push=0.0):
    """Place `line` (relative beats) at `bar`. scoop: a short slide in from below on a leap or after a rest (the bansuri
    meend). trill: a quick upper-neighbour decoration on every long note (the oud). rel_from/rel_to cut the line."""
    out, prev = [], None
    for (t, d, p, v) in line:
        if not (rel_from <= t < rel_to):
            continue
        a = bt(bar, t - rel_from + shift)
        kw = {}
        if scoop and (prev is None or p - prev >= 4 or t - prev_end >= 0.4):
            kw = dict(gl=-110, gs=0.09)
        if trill and d >= 1.0:
            hi = up(p)
            out += [N(a, 0.125, p + octave, v * vel), N(a + 0.125, 0.125, hi + octave, v * vel * 0.85),
                    N(a + 0.25, d - 0.25, p + octave, v * vel * 0.95)]
        else:
            out.append(N(a, d, p + octave, v * vel, **kw))
        prev, prev_end = p, t + d
    return out


def shift(p, k):
    """The pentatonic note k scale steps from p (k may be negative)."""
    step = 1 if k >= 0 else -1
    for _ in range(abs(k)):
        p += step
        while p % 12 not in SCALE_PC:
            p += step
    return p


SHAPES = {'up': [1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1], 'arch': [1, 2, 1, 2, 1, -1, -2, -1, -1, -2, 1, -1, -1],
          'cascade': [-1, -1, -2, -1, -2, -1, -1, -2, -1, -1, -2, -1, -1], 'wide': [2, 1, 2, 2, 1, 1, 2, 1, 2, 1, 1, 2, 1]}


def sweep(start, n=10, step=0.05, v0=56, v1=84, tail=1.0, first=74, shape='up'):
    """A run through the pentatonic scale in one of four shapes, then a held last note (the guzheng glissando)."""
    out, p = [], first
    for i in range(n):
        last = i == n - 1
        out.append(N(start + i * step, tail if last else step * 1.6, p, v0 + (v1 - v0) * i / max(1, n - 1)))
        p = shift(p, SHAPES[shape][i % len(SHAPES[shape])])
        while p > 90:                                   # F#6 is the top of the zither's comfortable range: a stretched pluck clicks
            p -= 12
    return out


FLOWER = {'Dadd9': (78, 81, 83), 'Bm7': (83, 81, 78), 'Asus2': (81, 83, 88), 'D6': (86, 83, 81), 'Esus4': (83, 88, 81)}


def flower(bar, vel):
    """Three quick plucks on the weak part of the bar: the zither "adding flowers" around a skeleton tune."""
    a, b_, c = FLOWER[CHORDS[bar]]
    return [N(bt(bar, 2.5), 0.2, a, vel), N(bt(bar, 2.75), 0.2, b_, vel + 6), N(bt(bar, 3.0), 0.5, c if bar % 2 else a, vel + 2)]


def pad_bar(bar, vel):
    # 3.4 beats, not the whole bar: the old chord must have released before the new one starts, or a whole tone between the
    # two chords' low notes beats for half a second (the roughness row measured it at every chord change)
    return [N(bt(bar) + 0.02 * i, 3.4, p, vel - 3 * i + rng.randint(-2, 2)) for i, p in enumerate(PAD[CHORDS[bar]])]


def marimba_bar(bar, scale):
    ct = PAD[CHORDS[bar]]
    pat = [0, 2, 1, 3, 2, 1] if bar % 2 else [0, 2, 3, 1, 2, 3]
    eighths = [0, 1, 3, 4, 6, 7]
    out = []
    for e, i in zip(eighths, pat):
        acc = 1.0 if e in (0, 3, 6) else 0.72                                   # accents on the three-three-two
        out.append(N(bt(bar, e * 0.5), 0.45, ct[i], (62 * acc) * scale + rng.randint(-3, 3)))
    return out


def bass_bar(bar, scale, sustain=False):
    root, fifth = BASS[CHORDS[bar]]
    if sustain:
        return [N(bt(bar), 3.6, root, 92 * scale)]        # a held note that is thin, not absent: the stem gate reads a quiet one as dropped out
    if bar % 2:
        return [N(bt(bar), 1.5, root, 86 * scale), N(bt(bar, 2.0), 1.0, fifth, 74 * scale), N(bt(bar, 3.5), 0.5, root, 66 * scale)]
    return [N(bt(bar), 1.0, root, 86 * scale), N(bt(bar, 1.5), 0.5, root, 64 * scale), N(bt(bar, 2.0), 1.5, fifth, 76 * scale),
            N(bt(bar, 3.5), 0.5, root, 62 * scale)]


def oud_strum(bar, scale):
    lo, mid, hi = OUD[CHORDS[bar]]
    out = [N(bt(bar), 1.0, lo, 74 * scale), N(bt(bar, 1.5), 1.0, mid, 66 * scale), N(bt(bar, 3.0), 0.9, hi, 70 * scale)]
    if bar % 2 == 0:
        out.append(N(bt(bar, 3.5), 0.4, mid, 56 * scale))
    return out


def darbuka_bar(bar, scale, light=False):
    """The maqsum: dum tak . tak dum . tak . ; ghost strokes vary the bars."""
    s = scale * (0.6 if light else 1.0)
    out = [N(bt(bar), 0.4, 'dum', 80 * s), N(bt(bar, 0.5), 0.3, 'tak', 68 * s), N(bt(bar, 1.5), 0.3, 'tak', 66 * s),
           N(bt(bar, 2.0), 0.4, 'dum', 76 * s), N(bt(bar, 3.0), 0.3, 'tak', 70 * s)]
    if not light:
        out.append(N(bt(bar, 3.5), 0.25, 'tek' if bar % 2 else 'ka', 42 * s))
        if bar % 4 == 2:
            out.append(N(bt(bar, 2.75), 0.25, 'tek', 38 * s))
    return out


def fill(bar, start=3.0, big=False):
    syl = ['tabla_na', 'tabla_tin', 'tabla_ti', 'tabla_ge'] * (3 if big else 1)
    step = 0.25 if not big else 0.125
    return [N(bt(bar, start + i * step), 0.2, s, 56 + 26 * i / max(1, len(syl) - 1)) for i, s in enumerate(syl)]


def shaker_bar(bar, scale, drop=False, backbeat=False):
    """The pulse: Indian hand cymbals (manjira) on every eighth. They ring into the next, so the stem has no silent hole. (A scraped-gourd
    ghost stroke between them was tried: its hard start made 43 click events in the stem, so it is gone.)"""
    out = []
    for e in range(8):
        if drop and e >= 7:
            continue                                                        # a gap on the last eighth of every fourth bar
        acc = 62 if e % 2 == 0 else 48
        if e in (0, 4):
            acc += 8
        if backbeat and e in (2, 6):
            acc = 76 + (4 if e == 6 else 0)                                 # the backbeat is a louder stroke, not a second one
        out.append(N(bt(bar, e * 0.5), 0.3, 'manjira', acc * scale * (1.0 if backbeat and e in (2, 6) else 0.8) + rng.randint(-2, 2)))
    return out


def bell_bar(bar, scale):
    """The three-three-two bell in four variants that cycle by bar, so the pattern is never the same bar twice in a row."""
    hi, lo = 'agogo_hi', 'agogo_lo'
    v = bar % 4
    if v == 1:
        return [N(bt(bar), 0.3, hi, 70 * scale), N(bt(bar, 1.5), 0.3, lo, 62 * scale), N(bt(bar, 3.0), 0.3, hi, 66 * scale)]
    if v == 2:
        return [N(bt(bar), 0.3, hi, 70 * scale), N(bt(bar, 1.5), 0.3, lo, 62 * scale), N(bt(bar, 3.0), 0.3, hi, 66 * scale),
                N(bt(bar, 3.5), 0.25, lo, 48 * scale)]
    if v == 3:
        return [N(bt(bar), 0.3, hi, 70 * scale), N(bt(bar, 1.5), 0.3, hi, 58 * scale), N(bt(bar, 3.0), 0.3, lo, 68 * scale)]
    return [N(bt(bar), 0.3, hi, 70 * scale), N(bt(bar, 1.5), 0.3, lo, 60 * scale)]


# ---------------------------------------------------------------------------------------------------- the tracks
kal, ban, oud, koto, mar, pad, bas, dar, sha, bel = ([] for _ in range(10))

# 1-4 Hook: the kalimba alone with the rattle, the maqsum, a soft pad and one bass note a bar
kal += phrase(1, HOOK, vel=0.95)
koto += sweep(bt(4, 3.5), n=8, step=0.102, v0=53, v1=71, first=76, shape='up')

# 5-8 Hook joined: the bansuri sings it; the marimba and bell and bass join; the kalimba rests
ban += phrase(5, HOOK, scoop=True)
koto += sweep(bt(8, 3.5), n=9, step=0.093, v0=53, v1=73, first=74, shape='arch')

# 9-16 Passing: the oud carries it with trills, the bansuri sustains over it; then the bansuri leads the answer first
oud += phrase(9, HOOK, octave=0, vel=0.95, shift=0.04, trill=True)
# (a sustained bansuri obbligato over the oud was tried here: its A5 and B5 sit a quarter of a critical band from the high
# agogo's own pitch and the roughness row measured the clash, so the bansuri rests until it takes the answer at bar 13)
koto += sweep(bt(12, 3.5), n=9, step=0.093, v0=53, v1=73, first=78, shape='cascade')
ban += phrase(13, HOOK, scoop=True, rel_from=8.0, rel_to=16.0)                    # the answer first ...
ban += phrase(15, HOOK, scoop=True, rel_from=0.0, rel_to=7.5)                     # ... then the question
koto += sweep(bt(16, 3.5), n=10, step=0.085, v0=54, v1=75, first=74, shape='wide')

# 17-22 Lift: the bansuri and the kalimba an octave apart, then a two-bar rising tag
ban += phrase(17, HOOK, scoop=True, vel=1.05)
kal += phrase(17, HOOK, octave=12, vel=0.92)
koto += sweep(bt(20, 3.5), n=10, step=0.085, v0=56, v1=76, first=76, shape='arch')
TAG = [(0.0, 0.5, 69, 78), (0.5, 0.5, 74, 80), (1.0, 0.5, 76, 82), (1.5, 1.5, 78, 88), (3.0, 0.5, 76, 74), (3.5, 0.5, 78, 78),
       (4.0, 0.5, 74, 80), (4.5, 0.5, 76, 84), (5.0, 0.5, 78, 88), (5.5, 2.0, 81, 96)]
ban += phrase(21, TAG, scoop=True, vel=1.05)
kal += phrase(21, TAG, octave=12, vel=0.92)
koto += sweep(bt(22, 3.0), n=14, step=0.119, v0=56, v1=82, first=69, shape='up')

# 23-24 Breath: the question alone, then one ringing koto note
kal += phrase(23, HOOK, vel=0.7, rel_from=0.0, rel_to=2.5)       # the question's first four notes: the rest of the bar is the breath
koto.append(N(bt(24), 4.5, 90, 84))
koto.append(N(bt(25), 2.0, 81, 54))                      # the zither answers the return, and the ring above never runs dry before it                   # rings a quarter second into the return: a ring decays under the downbeat

# 25-30 Return and turnaround
RET = [n for n in HOOK if n[0] < 12.0] + [(12.0, 1.0, 74, 86), (13.0, 0.5, 76, 84), (13.5, 0.5, 78, 86), (14.0, 0.5, 81, 90),
                                          (14.5, 0.5, 83, 92), (15.0, 0.5, 86, 94)]
kal += phrase(25, RET, vel=1.0)
ban += phrase(25, RET, scoop=True, vel=1.05)
oud += phrase(25, RET, octave=-12, vel=0.9, shift=0.05, trill=True)
koto += sweep(bt(28, 3.5), n=12, step=0.068, v0=58, v1=83, first=74, shape='wide')
kal += [N(bt(29), 1.0, 83, 82), N(bt(29, 1.0), 1.0, 81, 78), N(bt(29, 2.0), 1.0, 78, 74), N(bt(29, 3.0), 1.0, 74, 70),
        N(bt(30), 1.0, 76, 72), N(bt(30, 1.0), 3.0, 74, 76)]
ban.append(N(bt(29), 4.0, 81, 58, gl=-60, gs=0.12))

for bar in list(range(5, 8)) + list(range(9, 12)) + list(range(13, 16)) + list(range(17, 20)) + [21] + list(range(25, 28)):
    koto += flower(bar, 56 if bar < 17 else 62)

koto += sweep(bt(29, 2.0), n=5, step=0.30, v0=50, v1=58, first=86, shape='cascade', tail=1.5)       # the zither steps down with the tune
koto += [N(bt(30), 3.5, 81, 70), N(bt(30, 2.0), 0.5, 83, 60)]

# accompaniment by bar
SECT = [(1, 4, 'hook'), (5, 8, 'joined'), (9, 16, 'passing'), (17, 22, 'lift'), (23, 23, 'breath'), (24, 24, 'drop'),
        (25, 28, 'return'), (29, 30, 'turn')]
LEVEL = {'hook': 0.78, 'joined': 0.9, 'passing': 0.95, 'lift': 1.08, 'breath': 0.7, 'drop': 0.0, 'return': 1.08, 'turn': 0.8}
SHAKE = {'hook': 0.7, 'joined': 0.85, 'passing': 1.0, 'lift': 1.15, 'breath': 0.5, 'drop': 0.0, 'return': 1.15, 'turn': 0.75}
PADV = {'hook': 40, 'joined': 46, 'passing': 48, 'lift': 56, 'breath': 52, 'drop': 48, 'return': 56, 'turn': 44}
for a, z, name in SECT:
    for bar in range(a, z + 1):
        lv, sh = LEVEL[name], SHAKE[name]
        pad += pad_bar(bar, PADV[name])
        if name == 'drop':
            continue                                                         # one bar of near-silence before the return
        if name == 'hook':
            bas += bass_bar(bar, lv, sustain=True)
            dar += darbuka_bar(bar, lv, light=(bar < 3))
            sha += shaker_bar(bar, sh)
        elif name == 'breath':
            bas += bass_bar(bar, lv, sustain=True)
            dar += [N(bt(bar), 0.4, 'dum', 54), N(bt(bar, 2.0), 0.4, 'dum', 48)]
            sha += shaker_bar(bar, sh, drop=True)
        else:
            bas += bass_bar(bar, lv)
            dar += darbuka_bar(bar, lv)
            sha += shaker_bar(bar, sh, drop=(bar % 4 == 0), backbeat=name in ('lift', 'return'))
            if name in ('joined', 'passing', 'lift', 'return', 'turn') and bar != 30:
                bel += bell_bar(bar, lv)
            if name in ('joined', 'passing', 'lift', 'return') or bar == 29:
                mar += marimba_bar(bar, lv)
            if name == 'passing' and bar >= 13 or name == 'lift':
                oud += oud_strum(bar, lv)
mar += marimba_bar(30, 0.8)[:4]
dar += fill(8) + fill(16) + fill(22, 2.5, big=True) + fill(30, 2.0, big=True)
for bar in (8, 16, 22, 30):                                                  # the bar's own groove stops where its fill starts
    dar[:] = [n for n in dar if not (bt(bar, 3.0) <= n['t'] < bt(bar + 1) and n['p'] in ('tak', 'tek', 'ka') and bar != 30)]

# Who plays slightly ahead of or behind the beat, in beats at 120 BPM (0.02 beat = 10 ms). It is the sheet's `performer` block
# written into the notes: the lute sits a hair behind, the flute breathes in late, the hand drum anchors the grid. It also
# keeps six instruments from landing within a millisecond of each other, which sums their sharp starts into one click.
LEAN = {'kalimba_hook': 0.0, 'bansuri_lead': 0.05, 'oud_lead': 0.08, 'koto_flourish': 0.03, 'marimba_ostinato': 0.03,
        'open_pad': 0.0, 'bass_pulse': -0.02, 'darbuka_groove': 0.0, 'shaker_pulse': -0.03, 'bell_tresillo': -0.05}


def lean(name, notes):
    return [dict(n, t=round(n['t'] + LEAN[name], 4)) if n['t'] + LEAN[name] >= 0 else n for n in notes]


TRACKS = [('kalimba_hook', 'melody', kal), ('bansuri_lead', 'lead', ban), ('oud_lead', 'lead', oud),
          ('koto_flourish', 'counter', koto), ('marimba_ostinato', 'ostinato', mar), ('open_pad', 'pad', pad),
          ('bass_pulse', 'bass', bas), ('darbuka_groove', 'drum', dar), ('shaker_pulse', 'drum', sha),
          ('bell_tresillo', 'drum', bel)]

score = dict(
    title='Confluence', bpm=120.0, ts=[4, 4], key='D', mode='pentatonic_major', space='confluence_room', mix_preset='confluence_mix',
    piece_type='melodic', focus='melody',
    intent=dict(emotions=['joyful', 'playful'], registers=['natural'], scenes=['arrival'], tensions=['silence_before', 'ostinato'],
                avoid=['four_on_floor', 'pedal_drone_throughout']),
    mix_intent=dict(hero='bansuri_lead', support=['kalimba_hook', 'oud_lead', 'koto_flourish', 'bass_pulse'],
                    sits_under=['marimba_ostinato', 'open_pad', 'darbuka_groove', 'shaker_pulse', 'bell_tresillo']),
    rubato=0.0, ritard=0.0, wander=0.0,
    master=dict(profile='ringtone'), output_targets=['stereo'],
    dynamics=[[0.0, 0.5], [16.0, 0.6], [32.0, 0.65], [64.0, 0.8], [88.0, 0.4], [96.0, 0.75], [112.0, 0.45], [120.0, 0.45]],
    plan=dict(sections=[dict(name=n, start_bar=a, end_bar=z, start_s=(a - 1) * 2.0, end_s=z * 2.0, energy=e, dyn=e)
                        for n, a, z, e in (('Hook', 1, 4, 0.5), ('Hook joined', 5, 8, 0.6), ('Passing', 9, 16, 0.65),
                                           ('Lift', 17, 22, 0.8), ('Breath', 23, 24, 0.4), ('Return', 25, 28, 0.75),
                                           ('Turnaround', 29, 30, 0.45))]),
    tracks=[dict(name=n, instrument=n, role=r, notes=sorted(lean(n, ns), key=lambda e: (e['t'], str(e['p'])))) for n, r, ns in TRACKS if ns])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(score, fh, indent=1)
print(OUT)
for t in score['tracks']:
    print('  %-18s %-9s %4d notes' % (t['name'], t['role'], len(t['notes'])))
