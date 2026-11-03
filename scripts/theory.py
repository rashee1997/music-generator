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
"""theory.py - the music-theory toolbox behind compose.py (and handy for hand-written custom scripts).

Everything returns plain dict notes {"t": beat, "d": beats, "p": midi, "v": 0..1} so the output can go
straight into a natural score (see render_natural.py). Import what you need:

    from theory import *
    key = Key('D', 'aeolian')
    chords = [key.chord(s) for s in 'i VI III VII'.split()]
    v = voice_lead(chords[0], None, lo=50, hi=72)         # close voicing, then keep passing prev=v
    notes = TEXTURES['arp8'](v, bar_beats=4, vel=0.5, rng=rng)
    melody = make_melody(rng, key, chords_per_bar, ...)

Music-theory conventions used here
  * roman numerals are read against the key's scale: "VI" in aeolian = major chord on the 6th degree (b6)
  * suffixes: 7 maj7 m7 9 maj9 add9 sus2 sus4 dim dim7 aug 5 6   (e.g. "IVmaj7", "v7", "V7", "iisus4")
  * all pitch work happens in SCALE-DEGREE space, then maps to MIDI, so melodies stay in key
"""
import re
import numpy as np

NOTE_PC = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7,
           'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']

MODES = {
    'major': [0, 2, 4, 5, 7, 9, 11], 'ionian': [0, 2, 4, 5, 7, 9, 11], 'dorian': [0, 2, 3, 5, 7, 9, 10],
    'phrygian': [0, 1, 3, 5, 7, 8, 10], 'lydian': [0, 2, 4, 6, 7, 9, 11], 'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'minor': [0, 2, 3, 5, 7, 8, 10], 'aeolian': [0, 2, 3, 5, 7, 8, 10], 'locrian': [0, 1, 3, 5, 6, 8, 10],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11], 'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
    'hijaz': [0, 1, 4, 5, 7, 8, 10], 'double_harmonic': [0, 1, 4, 5, 7, 8, 11],
    'pentatonic_major': [0, 2, 4, 7, 9], 'pentatonic_minor': [0, 3, 5, 7, 10], 'blues': [0, 3, 5, 6, 7, 10],
    'whole_tone': [0, 2, 4, 6, 8, 10],
}
# 7-note parent used for roman-numeral chord roots when the melodic scale is smaller/odd
PARENT = {'pentatonic_major': 'major', 'pentatonic_minor': 'minor', 'blues': 'minor', 'whole_tone': 'lydian',
          'hijaz': 'phrygian', 'double_harmonic': 'phrygian'}

import world as _world      # scales (with cents in world.MICRO) and grooves for the world genres
MODES.update(_world.MODES)
PARENT.update(_world.PARENT)

CHORD_TONES = {'': None}
ROMAN = {'I': 0, 'II': 1, 'III': 2, 'IV': 3, 'V': 4, 'VI': 5, 'VII': 6}


def note_name(m):
    return f'{NAMES[m % 12]}{m // 12 - 1}'


class Key:
    def __init__(self, tonic='C', mode='major', octave=4):
        self.tonic_name = tonic
        self.mode = mode
        self.tpc = NOTE_PC[tonic]
        self.scale = MODES[mode]
        self.parent = MODES[PARENT.get(mode, mode)]
        self.tonic_midi = 12 * (octave + 1) + self.tpc

    def pitch(self, degree):
        """scale degree index (0 = tonic of the key's base octave, may be negative) -> MIDI"""
        L = len(self.scale)
        return self.tonic_midi + 12 * (degree // L) + self.scale[degree % L]

    def degree_of(self, midi):
        """nearest scale degree index to a MIDI pitch"""
        best, bd = 0, 999
        base = int((midi - self.tonic_midi) // 12)
        for oc in (base - 1, base, base + 1):
            for i, s in enumerate(self.scale):
                d = oc * len(self.scale) + i
                dist = abs(self.pitch(d) - midi)
                if dist < bd:
                    best, bd = d, dist
        return best

    def pcs(self):
        return {(self.tpc + s) % 12 for s in self.scale}

    def chord(self, sym):
        """roman numeral -> dict(root_pc, tones(list of intervals from root), name, pcs(set))"""
        m = re.match(r'^([b#]?)(VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)(.*)$', sym.strip())
        if not m:
            raise ValueError(f'bad chord symbol {sym}')
        acc, num, suf = m.groups()
        deg = ROMAN[num.upper()]
        root = self.parent[deg] + (-1 if acc == 'b' else 1 if acc == '#' else 0)
        upper = num.isupper()
        tones = [0, 4, 7] if upper else [0, 3, 7]
        s = suf
        if 'dim' in s:
            tones = [0, 3, 6, 9] if '7' in s else [0, 3, 6]
        elif 'aug' in s:
            tones = [0, 4, 8]
        elif 'sus2' in s:
            tones = [0, 2, 7]
        elif 'sus4' in s:
            tones = [0, 5, 7]
        elif s == '5':
            tones = [0, 7]
        if 'maj7' in s or 'maj9' in s:
            tones = tones + [11]
        elif '7' in s or re.search(r'(?<!add)9', s):
            tones = tones + [10]
        if '6' in s and 'maj' not in s:
            tones = tones + [9]
        if 'add9' in s or '9' in s:
            tones = tones + [14]
        if 'b9' in s:
            tones = [t for t in tones if t != 14] + [13]
        if '#11' in s:
            tones = tones + [18]
        rp = (self.tpc + root) % 12
        return dict(sym=sym, root_pc=rp, root_off=root, tones=sorted(set(tones)), pcs={(rp + t) % 12 for t in tones})


def parse_progression(key, text):
    """'i-VI-III-VII' or 'i VI III VII' -> [chord,...]"""
    toks = [t for t in re.split(r'[-\s,]+', text.strip()) if t]
    return [key.chord(t) for t in toks]


# ------------------------------------------------------------------------------------------------
# voicing
# ------------------------------------------------------------------------------------------------

def chord_midis(ch, low, high):
    """all MIDI notes in [low, high] belonging to the chord, sorted"""
    return [m for m in range(low, high + 1) if m % 12 in ch['pcs']]


def _lil(c):
    """Low-interval limit penalty (Huron 2001): close 3rds/4ths below G3 and anything closer than a 5th below C3
    beat against each other in the same critical band. Semitone/minor 2nd collisions below C5 produce severe roughness."""
    pen = 0.0
    for a, b in zip(c, c[1:]):
        gap = b - a
        if gap <= 2 and b < 72:
            pen += 15.0
        if b < 55 and gap < 5:
            pen += 6.0
        if b < 48 and gap < 7:
            pen += 12.0
    return pen


def _parallel_perfects(c, prev, root_pc):
    """+4 for parallel perfect 5ths/octaves between the outer voices, when the root changes (hollow, 'organ' motion)."""
    if not prev or len(prev) < 2 or len(c) < 2:
        return 0.0
    p0, p1 = min(prev), max(prev)
    c0, c1 = min(c), max(c)
    if (c0 - p0) * (c1 - p1) <= 0 or p0 % 12 == root_pc:
        return 0.0
    old, new = (p1 - p0) % 12, (c1 - c0) % 12
    return 4.0 if old == new and old in (0, 7) else 0.0


def _tension_resolution(c, prev, pcs):
    """-1.5 when a dissonant note of the previous voicing (leading tone, chordal 7th, chromatic tension) resolves
    into the new chord by a semitone or whole tone."""
    if not prev:
        return 0.0
    bonus = 0.0
    for x in prev:
        if x % 12 in pcs:
            continue
        if min(abs(y - x) for y in c) in (1, 2):
            bonus -= 1.5
    return bonus


def voice_lead(ch, prev, lo=52, hi=76, n=None, open_=False, add_root=False):
    """Pick the voicing of `ch` that moves least from `prev` (list of MIDI) inside [lo, hi].
    n = number of voices (default: all chord tones, max 4). open_=True spreads the voicing (root-5-3 style).
    Candidates include octave-spread variants so a low, narrow layer (e.g. lo=36 hi=58) can still obey the
    low-interval limits instead of stacking a muddy third under C3."""
    tones = ch['tones'][: (n or min(len(ch['tones']), 4))]
    pcs = [(ch['root_pc'] + t) % 12 for t in tones]
    cands = []
    rng_ = range(lo, hi + 1)
    # enumerate: choose a lowest note among chord pcs, then stack the remaining pcs upward (close + open variants)
    for start in rng_:
        if start % 12 not in pcs:
            continue
        stack = [start]
        remaining = [p for p in pcs if p != start % 12]
        cur = start
        order = sorted(remaining, key=lambda p: (p - start) % 12)
        for p in order:
            nx = cur + ((p - cur) % 12 or 12)
            stack.append(nx)
            cur = nx
        variants = [list(stack)]
        upper = list(range(1, len(stack)))
        for mask in range(1, 1 << len(upper)):
            vv = list(stack)
            for bit, i in enumerate(upper):
                if mask >> bit & 1:
                    vv[i] += 12
            if vv[-1] <= hi:
                variants.append(sorted(vv))
        if open_ and len(stack) >= 3:
            stack = [stack[0], stack[2] if len(stack) > 2 else stack[1]] + [s + 12 if i == 1 else s for i, s in enumerate(stack[1:], 1) if i != 2]
            variants.append(sorted(set(stack)))
        cands.extend(v for v in variants if v[-1] <= hi)
    if not cands:
        base = lo + ((ch['root_pc'] - lo) % 12)
        return [base + t for t in ch['tones'][:4]]
    if prev:
        def cost(c):
            a, b = sorted(c), sorted(prev)
            k = min(len(a), len(b))
            return (sum(abs(x - y) for x, y in zip(a[:k], b[:k])) + 2 * abs(len(a) - len(b))
                    + 0.1 * abs(np.mean(a) - np.mean(b)) + _lil(a)
                    + _parallel_perfects(a, b, ch['root_pc']) + _tension_resolution(a, b, ch['pcs']))
        return min(cands, key=cost)
    mid = (lo + hi) / 2
    return min(cands, key=lambda c: _lil(c) + 0.1 * abs(np.mean(c) - mid))


def bass_note(ch, prev=None, lo=36, hi=50):
    cands = [m for m in range(lo, hi + 1) if m % 12 == ch['root_pc']]
    if prev is None:
        return cands[0] if cands else lo
    return min(cands, key=lambda m: abs(m - prev)) if cands else lo


# ------------------------------------------------------------------------------------------------
# accompaniment textures. Each returns notes for ONE bar (t relative to bar start, in beats)
# ------------------------------------------------------------------------------------------------

def _n(t, d, p, v):
    return dict(t=float(t), d=float(d), p=int(p), v=float(np.clip(v, 0.05, 1.0)))


def _voiced(v, t, d, vel, roll=0.008):
    """Block chord without the digital brick wall (Goebl 2001): the top voice leads (+8 %), inner voices sit back,
    and the notes roll a few milliseconds instead of landing on one sample."""
    return [_n(t + idx * roll, d, p, vel * (0.92 + 0.05 * idx)) for idx, p in enumerate(v)]


def tex_block(v, bb, vel=0.5, rng=None, **k):
    return _voiced(v, 0, bb * 0.98, vel)


def tex_half(v, bb, vel=0.5, rng=None, **k):
    h = bb / 2
    return _voiced(v, 0, h * 0.95, vel) + _voiced(v, h, h * 0.95, vel * 0.85)


def _pattern(v, bb, idx, step, vel, dur_mul=1.6, accent=(1.0, 0.7, 0.8, 0.7)):
    out = []
    t = 0.0
    i = 0
    while t < bb - 1e-6:
        p = v[idx[i % len(idx)] % len(v)]
        out.append(_n(t, step * dur_mul, p, vel * accent[i % len(accent)]))
        t += step
        i += 1
    return out


def tex_arp8(v, bb, vel=0.5, rng=None, **k):
    return _pattern(v, bb, [0, 1, 2, 3, 2, 1], 0.5, vel)


def tex_arp16(v, bb, vel=0.45, rng=None, **k):
    return _pattern(v, bb, [0, 1, 2, 3, 2, 1, 3, 2], 0.25, vel, 1.8, accent=(1, 0.6, 0.7, 0.6))


def tex_alberti(v, bb, vel=0.5, rng=None, **k):
    return _pattern(v, bb, [0, 2, 1, 2], 0.5, vel, 1.2)


def tex_fingerpick(v, bb, vel=0.5, rng=None, **k):
    return _pattern(v, bb, [0, 2, 1, 3, 2, 1, 3, 1], 0.5, vel, 3.0, accent=(1.0, 0.65, 0.7, 0.65))


def tex_pulse(v, bb, vel=0.4, rng=None, **k):
    out = []
    t = 0.0
    while t < bb - 1e-6:
        out += _voiced(v, t, 0.45, vel * (1.0 if t % 1 == 0 else 0.7))
        t += 0.5
    return out


def tex_comp(v, bb, vel=0.5, rng=None, **k):
    """syncopated off-beat comping (pop / lo-fi / jazz)"""
    hits = [(0, 0.9, 1.0), (1.5, 0.45, 0.75), (2.5, 0.45, 0.85), (3.5, 0.4, 0.7)] if bb == 4 else [(0, .9, 1), (1.5, .45, .8)]
    return [n for t, d, a in hits for n in _voiced(v, t, d, vel * a)]


def tex_strum(v, bb, vel=0.55, rng=None, **k):
    """Acoustic strum: downstrokes low-to-high on the beat, upstrokes high-to-low off the beat, each string a few
    milliseconds after the last, left ringing (legato) so the body is never choked."""
    r = rng or np.random.default_rng(0)
    hits = [(0, 1.0, 1.0), (1, 0.5, 0.7), (1.5, 0.5, 0.8), (2.5, 0.5, 0.75), (3, 0.5, 0.8), (3.5, 0.5, 0.65)] if bb == 4 \
        else [(0, 1, 1), (1, .9, .7), (2, .9, .7)][: int(bb)]
    out = []
    for t, d, a in hits:
        up = abs(t % 1) > 1e-6
        order = sorted(range(len(v)), key=lambda j: v[j], reverse=up)
        if up and len(order) > 1 and r.random() < 0.5:
            order = order[:-1]                       # upstrokes are lighter: drop the lowest bass note half the time
        for i, j in enumerate(order):
            n = _n(t + i * 0.018, max(d * 1.6, 0.6), v[j], vel * a * (0.92 + 0.05 * j))
            n['art'] = 'legato'
            out.append(n)
    return out


def tex_waltz(v, bb, vel=0.5, rng=None, **k):
    out = [_n(0, 0.9, v[0], vel)]
    for b in (1, 2):
        out += _voiced(v[1:], b, 0.9, vel * 0.7)
    return out


def tex_ostinato(v, bb, vel=0.5, rng=None, **k):
    """tension: relentless repeated 16ths on the root-fifth, accents drifting"""
    out = []
    t = 0.0
    i = 0
    pat = [0, 0, 1, 0, 0, 1, 0, 2]
    while t < bb - 1e-6:
        out.append(_n(t, 0.22, v[pat[i % 8] % len(v)], vel * (1.0 if i % 4 == 0 else 0.62)))
        t += 0.25
        i += 1
    return out


def tex_sparse(v, bb, vel=0.45, rng=None, **k):
    """few notes, lots of air: chord tones sprinkled, good for sadness / wonder"""
    r = rng or np.random.default_rng(0)
    out = [_n(0, bb * 0.9, v[0], vel)]
    for t in sorted(r.choice([1.0, 1.5, 2.0, 2.5, 3.0], size=2, replace=False)):
        if t < bb:
            out.append(_n(t, 1.5, v[int(r.integers(1, len(v)))], vel * 0.75))
    return out


def tex_skank(v, bb, vel=0.5, rng=None, **k):
    """reggae / ska: short chord stabs on every offbeat (the 'and' of each beat), nothing on the beat"""
    out = []
    t = 0.5
    while t < bb - 1e-6:
        out += _voiced(v, t, 0.28, vel * (1.0 if int(t) % 2 else 0.85))
        t += 1.0
    return out


def tex_chop(v, bb, vel=0.5, rng=None, **k):
    """funk: tight muted 16th-note chops with rests, the one hit hardest"""
    hits = [(0, .2, 1.0), (.75, .15, .6), (1.5, .2, .8), (2, .2, .85), (2.75, .15, .6), (3.25, .15, .55), (3.5, .2, .8)] \
        if bb == 4 else [(0, .2, 1.0), (1.5, .2, .8)]
    return [n for t, d, a in hits for n in _voiced(v, t, d, vel * a)]


TEXTURES = {'skank': tex_skank, 'chop': tex_chop, 'block': tex_block, 'half': tex_half, 'arp8': tex_arp8, 'arp16': tex_arp16, 'alberti': tex_alberti,
            'fingerpick': tex_fingerpick, 'pulse': tex_pulse, 'comp': tex_comp, 'strum': tex_strum,
            'waltz': tex_waltz, 'ostinato': tex_ostinato, 'sparse': tex_sparse}


# ------------------------------------------------------------------------------------------------
# bass lines (one bar)
# ------------------------------------------------------------------------------------------------

def bass_line(kind, ch, nxt, prev, bb, vel, rng, lo=36, hi=52):
    r = bass_note(ch, prev, lo, hi)
    fifth = r + 7 if r + 7 <= hi + 3 else r - 5
    if kind == 'whole':
        return [_n(0, bb * 0.97, r, vel)], r
    if kind == 'half':
        return [_n(0, bb / 2 * 0.95, r, vel), _n(bb / 2, bb / 2 * 0.95, fifth, vel * 0.85)], r
    if kind == 'pulse8':
        return [_n(t, 0.45, r, vel * (1 if t % 2 == 0 else 0.75)) for t in np.arange(0, bb, 0.5)], r
    if kind == 'sync':
        pts = [(0, 1.0, 1.0), (1.5, 0.75, 0.8), (2.5, 0.5, 0.75), (3.0, 0.9, 0.85)] if bb == 4 else [(0, 1, 1)]
        return [_n(t, d, r if i != 2 else fifth, vel * a) for i, (t, d, a) in enumerate(pts)], r
    if kind == 'walk':
        nr = bass_note(nxt, r, lo, hi) if nxt else r
        third = r + (3 if (ch['tones'][1] == 3) else 4)
        steps = [r, third, fifth, nr - 1 if nr > r else nr + 1]
        return [_n(i, 0.95, p, vel * (1 if i == 0 else 0.8)) for i, p in enumerate(steps[: int(bb)])], r
    if kind == 'pedal':
        return [_n(0, bb * 0.99, r, vel)], r
    return [], r


# ------------------------------------------------------------------------------------------------
# drums (one bar). names map via soundbank.DRUM_KEYS
# ------------------------------------------------------------------------------------------------

# ------------------------------------------------------------------------------------------------
# grooves: one bar on a 16-step grid (step 0 = beat 1; each step is a sixteenth). A genre names one.
# 'sourced' = taken from a source read for this skill; 'practice' = common practice, not from a source.
# Keys 'name@tag' are the same drum with a different weight (e.g. a ghost snare). Weights scale velocity.
# Grids are 4/4: in a 3/4 bar, hits past beat 3 are dropped.
# ------------------------------------------------------------------------------------------------
GROOVES = {
    'boom_bap': ('sourced', {'kick': [0, 8, 10], 'snare': [4, 12], 'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14]},
                 {'kick': .95, 'snare': .9, 'hat_closed': .5}),
    'trap': ('practice', {'kick': [0, 10], 'snare': [8], 'hat_closed': list(range(16))},
             {'kick': .95, 'snare': .9, 'hat_closed': .3}),
    'halftime': ('practice', {'kick': [0, 10], 'snare': [8], 'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14]},
                 {'kick': .95, 'snare': .95, 'hat_closed': .4}),
    'breakbeat': ('practice', {'kick': [0, 10], 'snare': [4, 12], 'snare@ghost': [7, 11],
                               'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14]},
                  {'kick': .95, 'snare': .95, 'snare@ghost': .3, 'hat_closed': .4}),
    'one_drop': ('practice', {'kick': [8], 'rim': [8], 'hat_closed': [2, 6, 10, 14]},
                 {'kick': .95, 'rim': .8, 'hat_closed': .45}),
    'rock': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14]},
             {'kick': .95, 'snare': .95, 'hat_closed': .5}),
    'funk': ('practice', {'kick': [0, 6, 10], 'snare': [4, 12], 'snare@ghost': [3, 7, 11, 15],
                          'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14]},
             {'kick': .95, 'snare': .95, 'snare@ghost': .25, 'hat_closed': .4}),
    'metal': ('practice', {'kick': [0, 2, 4, 6, 8, 10, 12, 14], 'snare': [4, 12]},
              {'kick': .75, 'snare': 1.0}),
    'rnb': ('practice', {'kick': [0, 9], 'snare': [4, 12], 'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14]},
            {'kick': .9, 'snare': .85, 'hat_closed': .35}),
    'bossa': ('practice', {'rim': [0, 3, 6, 10, 12], 'kick': [0, 8], 'ride': [0, 2, 4, 6, 8, 10, 12, 14]},
              {'rim': .6, 'kick': .35, 'ride': .3}),
    'samba': ('practice', {'tom_floor': [0, 8], 'tom_low': [4, 12], 'shaker': [0, 2, 4, 6, 8, 10, 12, 14],
                           'rim': [3, 7, 11, 15]},
              {'tom_floor': .8, 'tom_low': .6, 'shaker': .4, 'rim': .35}),
    'dembow': ('practice', {'kick': [0, 4, 8, 12], 'snare': [3, 6, 11, 14]}, {'kick': .9, 'snare': .8}),
    'cumbia': ('practice', {'kick': [0, 8], 'conga_open': [4, 12], 'guiro': [0, 2, 4, 6, 8, 10, 12, 14]},
               {'kick': .7, 'conga_open': .6, 'guiro': .35}),
    'salsa': ('practice', {'claves': [0, 3, 6, 10, 12], 'cowbell': [0, 2, 4, 6, 8, 10, 12, 14],
                           'conga_open': [6, 12], 'conga_mute': [4, 10, 14]},
              {'claves': .6, 'cowbell': .4, 'conga_open': .6, 'conga_mute': .4}),
    'afrobeat': ('practice', {'kick': [0, 6, 10], 'rim': [4, 12], 'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14],
                              'bongo_high': [2, 5, 9, 13]},
                 {'kick': .85, 'rim': .7, 'hat_closed': .35, 'bongo_high': .35}),
    'motown': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'tambourine': [0, 2, 4, 6, 8, 10, 12, 14]},
               {'kick': .85, 'snare': .95, 'tambourine': .5}),
    'synthpop': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'clap': [4, 12],
                              'hat_closed': [0, 2, 4, 6, 8, 10, 12, 14]},
                 {'kick': .9, 'snare': .8, 'clap': .5, 'hat_closed': .4}),
    'forro': ('practice', {'kick': [0, 8], 'tom_low': [4, 12], 'triangle': [0, 2, 4, 6, 8, 10, 12, 14]},
              {'kick': .8, 'tom_low': .55, 'triangle': .4}),
    'percussion_drive': ('practice', {'tom_floor': [0, 8], 'tom_low': [4, 12], 'tom_mid': [2, 6, 10, 14]},
                         {'tom_floor': .95, 'tom_low': .8, 'tom_mid': .5}),
}


GROOVES.update(_world.GROOVES)

# Arabic iqa'at (dum = bass, tek/tak = edge). The positions are the spec's: maqsum and baladi as the world grooves
# have them, plus the maqsum ghost on 3.75 (tak@ghost, step 15) and malfuf as a 3+3+2 feel in 4/4.
GROOVES['maqsum'] = ('practice', {'dum': [0, 8], 'tak': [2, 6, 12], 'tak@ghost': [15], 'riq': list(range(0, 16, 2))},
                     {'dum': .9, 'tak': .6, 'tak@ghost': .3, 'riq': .25})
GROOVES['malfuf'] = ('practice', {'dum': [0], 'tak': [3, 6]}, {'dum': .9, 'tak': .6})
ARABIC_IQAAT = {'maqsum', 'baladi', 'saidi', 'malfuf'}


def iqaat_bar(name, bb, vel, rng):
    """One bar of an Arabic iqa'a. Only dum/tek strokes: no Latin off-beat skank, no conga tumbao."""
    if name not in ARABIC_IQAAT:
        raise ValueError(f'{name} is not an iqa: use one of {sorted(ARABIC_IQAAT)}')
    return groove_bar(name, bb, vel, rng)


def _flam_layered(D):
    """Offset clap/tambourine a few milliseconds off a snare/rim (or off each other), so two bright samples never
    fire on the same sample: a human flam, not a phase-locked double."""
    t0 = [h['t'] for h in D]
    for i, h in enumerate(D):
        if h['p'] not in ('clap', 'tambourine'):
            continue
        if any(j != i and abs(t0[j] - t0[i]) < 0.003 and D[j]['p'] in ('snare', 'rim', 'clap', 'tambourine')
               for j in range(len(D))):
            h['t'] += 0.022 if h['p'] == 'clap' else 0.028


GRID_ACCENT = (1.18, 0.82, 1.02, 0.76, 1.10, 0.86, 0.96, 0.72)   # step % 8: downbeat loudest, each 16th distinct


def _grid_accent(step):
    """Metric accent on the 16-step grid: a repeated percussion run is never one flat level, and no two 16ths
    share a level (odd-step patterns like a garba shaker would otherwise all get the same accent)."""
    return GRID_ACCENT[step % len(GRID_ACCENT)]


def groove_bar(kind, bb, vel, rng):
    """one bar of a named groove; every hit gets a small random velocity so it does not sound stamped"""
    _, grid, w = GROOVES[kind]
    D = []
    for key, steps in grid.items():
        name = key.split('@')[0]
        for s in steps:
            t = s / 4.0
            if t >= bb:
                continue
            v = vel * w.get(key, 0.6) * _grid_accent(s) * rng.uniform(0.93, 1.0)
            D.append(dict(t=float(t), d=0.1, p=name, v=float(np.clip(v, 0.05, 1.0))))
    _flam_layered(D)
    return D


def drum_bar(kind, bb, vel, rng, fill=False, crash=False):
    D = []

    def hit(t, name, v, d=0.1):
        D.append(dict(t=float(t), d=d, p=name, v=float(np.clip(v, 0.05, 1.0))))
    if kind == 'none':
        return D
    if kind == 'soft_pulse':                      # ballad: kick 1, rim/soft snare 3, quiet hat
        hit(0, 'kick', vel * .8); hit(2, 'rim', vel * .5)
        for i, t in enumerate(np.arange(0, bb, 1.0)):
            hit(t + 0.5, 'hat_closed', vel * .35 * (1.16 if i % 2 == 0 else 0.82))
    elif kind == 'brush':                          # swirling brushes: hat/ride 8ths + soft snare
        for t in np.arange(0, bb, 0.5):
            hit(t, 'ride' if t % 1 == 0 else 'hat_closed', vel * (.4 if t % 1 == 0 else .28))
        hit(1, 'snare', vel * .35); hit(3, 'snare', vel * .4); hit(0, 'kick', vel * .5)
    elif kind == 'pop':
        for b in range(int(bb)):
            hit(b, 'kick' if b % 2 == 0 else 'snare', vel * (.9 if b % 2 == 0 else .85))
        for t in np.arange(0, bb, 0.5):
            hit(t, 'hat_closed', vel * (.55 if t % 1 == 0 else .38))
        if rng.random() < .5: hit(2.5, 'kick', vel * .6)
        if rng.random() < .4: hit(3.75, 'snare', vel * .25)     # ghost
    elif kind == 'half':
        hit(0, 'kick', vel); hit(bb / 2, 'snare', vel * .9)
        for t in np.arange(0, bb, 0.5):
            hit(t, 'hat_closed', vel * (.5 if t % 1 == 0 else .3))
    elif kind == 'four_floor':
        for b in range(int(bb)):
            hit(b, 'kick', vel * .9); hit(b + .5, 'hat_open', vel * .45)
            if b % 2 == 1: hit(b, 'clap', vel * .7)
        for i, t in enumerate(np.arange(0.25, bb, 0.5)): hit(t, 'hat_closed', vel * .25 * (1.2 if i % 2 == 0 else 0.78))
    elif kind == 'lofi':                           # boom-bap, lazy
        hit(0, 'kick', vel * .95); hit(1.5, 'kick', vel * .7); hit(2.5, 'kick', vel * .6)
        hit(1, 'snare', vel * .85); hit(3, 'snare', vel * .9)
        for t in np.arange(0, bb, 0.5):
            hit(t, 'hat_closed', vel * (.45 if t % 1 == 0 else .3))
        if rng.random() < .5: hit(3.75, 'snare', vel * .22)
    elif kind == 'taiko':                          # cinematic: a hit on every beat (a steady grid), accents on 1 and 3
        for t, nm, w in [(0, 'tom_floor', 1.0), (1, 'tom_low', .6), (2, 'tom_floor', .9), (3, 'tom_low', .6), (3.5, 'tom_low', .5)]:
            if t < bb:
                hit(t, nm, vel * w)
    elif kind == 'march':
        for b in range(int(bb)):
            hit(b, 'snare', vel * (.8 if b % 2 == 0 else .6)); hit(b + .75, 'snare', vel * .3, 0.05)
        hit(0, 'kick', vel); hit(2, 'kick', vel * .85)
    elif kind == 'heartbeat':
        hit(0, 'kick', vel * .9); hit(0.4, 'kick', vel * .55)
        if bb > 2: hit(2, 'kick', vel * .85); hit(2.4, 'kick', vel * .5)
    elif kind == 'shaker':
        for t in np.arange(0, bb, 0.5):
            hit(t, 'shaker', vel * (.45 if t % 1 == 0 else .28))
        hit(0, 'kick', vel * .5)
    elif kind in GROOVES:                          # data-driven grooves (see GROOVES above)
        D = groove_bar(kind, bb, vel, rng)
    if fill:                                       # 16th tom roll across the last beat
        D = [h for h in D if h['t'] < bb - 1]
        roll = ['snare', 'snare', 'tom_high', 'tom_mid', 'tom_low', 'tom_floor']
        n = len(roll)
        for i, nm in enumerate(roll):
            arch = (i / max(n - 1, 1)) ** 1.6          # exponential crescendo, not a linear ramp
            accent = 0.05 if i % 2 == 0 else -0.04     # alternating metric accent
            hit(bb - 1 + i * (1 / 6) * 1.0, nm, vel * (0.42 + 0.50 * arch + accent))
    if crash:
        hit(0, 'crash', vel * .9, 1.5)
    _flam_layered(D)
    return D


# ------------------------------------------------------------------------------------------------
# melody generation
# ------------------------------------------------------------------------------------------------
RHYTHMS = {   # bar-length (4/4) cells; each cell sums to 4 beats. lists of durations
    'slow':   [[4], [2, 2], [3, 1], [1.5, 1.5, 1], [2, 1, 1], [1, 1, 2], [2, 1.5, .5], [1, 3]],
    'medium': [[1, .5, .5, 1, 1], [1.5, .5, 1, 1], [1, 1, .5, .5, 1], [.5, .5, 1, 2], [2, 1, .5, .5], [1, 1, 1, 1],
               [1.5, 1.5, 1], [.5, .5, .5, .5, 2]],
    'driving': [[.5, .5, .5, .5, 1, .5, .5], [.75, .25, .5, .5, 1, 1], [.5, .5, 1, .5, .5, 1], [1, .5, .5, .5, .5, 1],
                [.5, .5, .5, .5, .5, .5, .5, .5], [.75, .75, .5, 1, 1]],
}
CADENCE = {'slow': [[2, 2], [4], [1, 1, 2], [3, 1]], 'medium': [[1, 1, 2], [2, 2], [1, .5, .5, 2]],
           'driving': [[1, .5, .5, 2], [.5, .5, 1, 2], [1, 1, 2]]}


def _cell(rng, style, bb, cadence=False):
    pool = CADENCE[style] if cadence else RHYTHMS[style]
    c = list(pool[int(rng.integers(len(pool)))])
    if bb != 4:                                   # scale a 4/4 cell to another bar length (3/4, 6/8 ...)
        scale = bb / 4.0
        c = [x * scale for x in c]
    return c


def _snap(key, deg, chord, maxd=2):
    """move a scale degree to the nearest chord tone (within maxd degrees) - used on strong beats"""
    best, bd = deg, 99
    for d in range(deg - maxd, deg + maxd + 1):
        if key.pitch(d) % 12 in chord['pcs'] and abs(d - deg) < bd:
            best, bd = d, abs(d - deg)
    return best


def _avoid_semitone_rub(key, deg, chord, lo, hi):
    """A held non-chord note a semitone from a chord tone grates (a minor 2nd / major 7th against the harmony).
    Move it to the nearest scale degree that is a chord tone or clear of every chord tone by at least a whole tone."""
    def rubs(x):
        pc = key.pitch(x) % 12
        return pc not in chord['pcs'] and any((pc - c) % 12 in (1, 11) for c in chord['pcs'])
    if not rubs(deg):
        return deg
    for step in (1, -1, 2, -2):
        x = deg + step
        if lo <= x <= hi and not rubs(x):
            return x
    return deg


def make_phrase(rng, key, chords, bb, style='medium', center_deg=4, span=(-3, 11), rest_p=0.1, leap_p=0.06,
                start_deg=None, end_deg=None, contour='arch', bars=None, vel=0.6, strict_beats=False):
    """One phrase over `chords` (one chord per bar). Returns (notes, degrees_list, rhythm_cells).
    Strong beats land on chord tones; leaps are followed by a step back; the last note is the cadence.
    strict_beats (off by default): every note on a whole beat, or at least 0.75 beat long, is also a chord tone.
    Held notes (a beat or more) never sit a semitone from a chord tone."""
    n_bars = len(chords)
    notes, deg_seq, cells = [], [], []
    cur = start_deg if start_deg is not None else _snap(key, center_deg, chords[0])
    lo, hi = span
    for bi, ch in enumerate(chords):
        last = bi == n_bars - 1
        # bars 0 and 2 share a rhythm cell (the "motif"), bar 1 varies it, the last bar cadences
        if last:
            cell = _cell(rng, style, bb, cadence=True)
        elif bi >= 2 and bi - 2 < len(cells):
            cell = cells[bi - 2]
        else:
            cell = _cell(rng, style, bb)
        cells.append(cell)
        t = 0.0
        prev_dir = 0
        for ni, d in enumerate(cell):
            is_last_note = last and ni == len(cell) - 1
            # target by contour
            frac = (bi + t / bb) / n_bars
            tgt = center_deg + {'arch': 3 * np.sin(np.pi * frac) - 1, 'rise': 4 * frac - 1, 'fall': 3 - 4 * frac,
                                'wave': 2 * np.sin(2 * np.pi * frac), 'flat': 0}.get(contour, 0)
            if is_last_note and end_deg is not None:
                nd = end_deg
            elif ni == 0 and bi == 0 and start_deg is not None:
                nd = start_deg
            else:
                r = rng.random()
                if r < leap_p and ni > 0:
                    step = int(rng.choice([-4, -3, 3, 4, 5]))
                    # prefer the leap toward the target
                    step = abs(step) * (1 if tgt > cur else -1)
                else:
                    pull = np.clip((tgt - cur) / 3.0, -1, 1) * 0.5
                    step = int(rng.choice([-2, -1, 0, 1, 2], p=_step_probs(pull, prev_dir)))
                nd = cur + step
            nd = int(np.clip(nd, lo + 0, hi))
            # strong beat / long note -> chord tone
            strong = (abs(t % bb) < 1e-6) or (d >= 1.5) or (bb == 4 and abs(t - 2) < 1e-6)
            if strict_beats and (abs(t - round(t)) < 1e-6 or d >= 0.75):
                strong = True
            if strong or is_last_note:
                nd = _snap(key, nd, ch, 2)
            if d >= 1.0:
                nd = _avoid_semitone_rub(key, nd, ch, lo, hi)
            # repeated notes are boring: usually move to a neighbouring (chord) tone instead
            if deg_seq and nd == deg_seq[-1] and not is_last_note and rng.random() < 0.8:
                alts = [x for x in (nd - 3, nd - 2, nd - 1, nd + 1, nd + 2, nd + 3)
                        if lo <= x <= hi and (not strong or key.pitch(x) % 12 in ch['pcs'])]
                if alts:
                    nd = alts[int(np.argmin([abs(x - tgt) + rng.random() * 1.5 for x in alts]))]
            if rng.random() < rest_p and ni > 0 and not is_last_note and d <= 1.0:
                t += d
                continue
            vv = vel * (1.0 if abs(t % 1) < 1e-6 else 0.85)
            notes.append(dict(t=bi * bb + t, d=d * (0.97 if d >= 1 else 0.9), p=key.pitch(nd), v=vv, deg=nd, strong=bool(strong)))
            prev_dir = np.sign(nd - cur) if nd != cur else prev_dir
            cur = nd
            deg_seq.append(nd)
            t += d
    return notes, deg_seq, cells


def _step_probs(pull, prev_dir):
    """probabilities for steps [-2,-1,0,+1,+2]: mostly stepwise, gentle pull toward the contour target,
    gap-fill (after moving one way, slightly prefer coming back)."""
    base = np.array([0.10, 0.32, 0.14, 0.32, 0.10])
    base[0] *= (1 - pull); base[1] *= (1 - pull); base[3] *= (1 + pull); base[4] *= (1 + pull)
    if prev_dir > 0:
        base[:2] *= 1.15
    elif prev_dir < 0:
        base[3:] *= 1.15
    base = np.clip(base, 0.01, None)
    return base / base.sum()


def vary_phrase(rng, key, phrase_notes, new_chords, bb, shift=0, cadence_deg=None, bars_per_phrase=None):
    """Re-use a phrase over different chords (the 'A' returns): same degrees & rhythm, strong beats re-snapped
    to the new chords, optional transposition by `shift` scale degrees, new cadence note."""
    out = []
    for n in phrase_notes:
        bi = int(n['t'] // bb)
        ch = new_chords[min(bi, len(new_chords) - 1)]
        d = n['deg'] + shift
        t_in = n['t'] - bi * bb
        # the stored length is d*0.97, so a 1.5-beat note is 1.455: use the flag make_phrase stored when there is one
        strong = n['strong'] if 'strong' in n else (abs(t_in) < 1e-6 or n['d'] >= 1.4 or (bb == 4 and abs(t_in - 2) < 1e-6))
        if strong:
            d = _snap(key, d, ch, 2)
        if n['d'] >= 0.97:
            d = _avoid_semitone_rub(key, d, ch, d - 3, d + 3)
        out.append(dict(n, p=key.pitch(d), deg=d))
    if cadence_deg is not None and out:
        out[-1] = dict(out[-1], p=key.pitch(cadence_deg), deg=cadence_deg)
    return out


def harmony_line(key, melody, below=-2, chords_by_bar=None, bb=4):
    """A diatonic line a third (default) below the melody - parallel harmony, snapped to chord tones on long notes."""
    out = []
    for n in melody:
        d = n['deg'] + below
        if chords_by_bar and (n['d'] >= 1.5 or abs((n['t'] % bb)) < 1e-6):
            ch = chords_by_bar[min(int(n['t'] // bb), len(chords_by_bar) - 1)]
            d = _snap(key, d, ch, 1)
        out.append(dict(n, p=key.pitch(d), deg=d, v=n['v'] * 0.8))
    return out


def clamp_register(notes, lo, hi):
    out = []
    for n in notes:
        p = n['p']
        while p < lo:
            p += 12
        while p > hi:
            p -= 12
        out.append(dict(n, p=p))
    return out


# ---- expression helpers from global_music_theory_algorithmic_synthesis_guide.md (sections 1D, 4C, 5B, 7 Law 1) ----
def pentatonic_spine(scale):
    """The 5-note subset of a scale (semitones) that an accompaniment track can share with any lead. KB Law 1."""
    s = set(scale)
    spines = [[0, 2, 4, 7, 9], [0, 3, 5, 7, 10], [0, 2, 5, 7, 10], [0, 1, 5, 7, 8]]
    best = max(spines, key=lambda c: len(s & set(c)))
    return [d for d in best if d in s] or [0, 7]


def apply_gamaka(notes, tonic_pc=2, rng=None, min_d=0.25):
    """Indian gamaka: Sa and Pa stay pure; a step of 1-3 semitones on a long enough note gets a slide from below.
    shortcut: the KB's first-note random slide is kept as written (only when a note has no predecessor)."""
    rng = rng or np.random.default_rng(42)
    out, prev = [], None
    for n in notes:
        n2 = dict(n)
        if (n2['p'] - tonic_pc) % 12 not in (0, 7) and 'gl' not in n2:
            if prev is not None:
                diff = n2['p'] - prev
                if 1 <= abs(diff) <= 3 and n2['d'] >= min_d:
                    n2['gl'] = int(-diff * 85)
            elif rng.random() < 0.45 and n2['d'] >= 0.5:
                n2['gl'] = -150
        prev = n2['p']
        out.append(n2)
    return out


def apply_meri(notes, breath=0.12):
    """Shakuhachi-style head-tilt scoop on long notes (alternating up and down), and a breath gap at the end of each."""
    out = []
    for i, n in enumerate(notes):
        n2 = dict(n)
        if n2['d'] >= 1.0:
            n2['gl'] = -110 if i % 2 == 0 else 75
            n2['d'] = max(0.25, n2['d'] - breath)
        out.append(n2)
    return out


def guzheng_sweep(t0, dur, tonic_midi, scale, direction='up', vel=0.72, octaves=2):
    """A guzheng-style run (guazou) through `scale` (semitones) over `octaves`, filling dur beats from t0."""
    pitches = [tonic_midi + 12 * o + d for o in range(octaves) for d in scale]
    if direction == 'down':
        pitches.reverse()
    step = dur / len(pitches)
    return [dict(t=round(t0 + i * step, 4), d=round(step * 2.2, 4), p=p, v=round(vel * (0.75 + 0.25 * i / len(pitches)), 3))
            for i, p in enumerate(pitches)]


# ------------------------------------------------------------------------------------------------
# cultural idioms. A culture recipe uses its own scale, its own ornament and its own timeline; a neighbour's
# scale (say Arabic Hijaz in an Indian brief) is not a substitute.
# ------------------------------------------------------------------------------------------------
CULTURE_SCALES = {   # the Cultural Scale & Idiom Compatibility table (see references/genres-and-moods.md)
    'indo_afro': ['raga_khamaj', 'raga_bhoopali', 'raga_kafi'],   # NOT charukeshi / hijaz: those read Arabic in fast runs
    'indian': ['raga_bhoopali', 'raga_khamaj', 'raga_kafi', 'raga_bilawal', 'raga_yaman'],
    'arabic': ['maqam_rast', 'maqam_bayati', 'maqam_hijaz', 'maqam_saba'],
}
IDIOM_INSTRUMENTS = {'sitar', 'sarod', 'bansuri', 'shehnai', 'veena', 'santoor', 'sarangi', 'esraj'}
GANKOGUI_STANDARD = [0, 2, 3, 5, 7, 8, 10]    # the 7-stroke standard bell pattern in 12/8 (12 eighth pulses)


def idiom_notes(inst, notes, tonic_pc=2, rng=None):
    """Every phrase of a sitar/sarod/bansuri/shehnai goes through the gamaka (taans and tihai too), then
    meend (a 150-300 ms glide into held notes) and nyasa (vadi/samvadi held longer, vibrato delayed)."""
    if str(inst).lower() not in IDIOM_INSTRUMENTS:
        return notes
    out = []
    for n in apply_gamaka(notes, tonic_pc, rng, min_d=0.1):
        n2 = dict(n)
        if 'gl' in n2:
            n2['gs'] = 0.22                                       # meend: a slow slide into the note
        if n2['d'] >= 1.0 and (n2['p'] - tonic_pc) % 12 in (0, 7):
            n2['d'] = n2['d'] * 1.15                              # nyasa: hold the Sa/Pa
            n2['vd'] = 0.5                                        # vibrato waits half a second
        out.append(n2)
    return out


def kora_bar(root_pc, bb, scale_pcs, vel=0.6):
    """West African kora, one bar. The thumb plays the kumbengo bass ostinato in MIDI 48-60 (root on the beat, fifth
    between); the index fingers play the birimintingo interlock in MIDI 64-79 (16ths alternating across the scale)."""
    low = next(m for m in range(48, 61) if m % 12 == root_pc)
    notes = [_n(t, 1.6, low, vel) for t in np.arange(0, bb, 2.0)]
    notes.append(_n(1.5, 0.5, low + 7, vel * 0.8))
    hi = [m for m in range(64, 80) if m % 12 in scale_pcs] or [64]
    order = [0, 2, 1, 3, 2, 4, 3, 5]                              # interlocking pairs, not a plain up-down arpeggio
    for i, t in enumerate(np.arange(0, bb, 0.25)):
        notes.append(_n(t, 0.2, hi[order[i % 8] % len(hi)], vel * (0.8 if i % 2 else 1.0)))
    return notes


def bell_bar(bar_beats=6.0, vel=0.5, name='agogo_high'):
    """Standard 7-stroke bell (gankogui) on a 12/8 bar: strokes at eighth-note pulses GANKOGUI_STANDARD.
    A 12/8 bar lasts 6 quarter-note beats, so pulse k lands at k * 0.5 beats."""
    out = []
    for k in GANKOGUI_STANDARD:
        if k * 0.5 < bar_beats:
            out.append(dict(t=k * 0.5, d=0.2, p=name, v=vel * (1.0 if k in (0, 5) else 0.8)))
    return out


def pickup_fill(kind, at_beat, beats=1.0, vel=0.7):
    """A 1-2 beat lead-in before a section's downbeat, so a quiet intro never jumps into a full band.
    kind: 'tabla' (mukhra), 'djembe' (roll), 'timpani' (a floor-tom swell), 'cymbal_swell' (crash at the downbeat)."""
    start = at_beat - beats
    if kind == 'cymbal_swell':
        return [dict(t=at_beat, d=1.0, p='crash', v=vel)]
    names = {'tabla': ['tabla_ti', 'tabla_na', 'tabla_tin', 'tabla_ge'], 'djembe': ['djembe_tone', 'djembe_tone', 'djembe_slap', 'djembe_bass'],
             'timpani': ['tom_floor'] * 4}[kind]
    n = len(names) * 2
    out = []
    for i in range(n):
        t = start + i * beats / n
        out.append(dict(t=float(t), d=0.1, p=names[i % len(names)], v=float(vel * (0.45 + 0.55 * i / n))))
    return out


if __name__ == '__main__':
    k = Key('D', 'aeolian')
    ch = parse_progression(k, 'i VI III VII')
    print([c['sym'] + ':' + ','.join(note_name(60 + (c['root_pc'] - 0) % 12 + t) for t in c['tones']) for c in ch])
    rng = np.random.default_rng(3)
    nts, degs, cells = make_phrase(rng, k, ch, 4, 'slow', center_deg=7)
    print(' '.join(note_name(n['p']) + f"({n['d']:g})" for n in nts))
    v = voice_lead(ch[0], None)
    print('voicing', [note_name(x) for x in v], [note_name(x) for x in voice_lead(ch[1], v)])
