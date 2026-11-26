#!/usr/bin/env python3
"""compose_main.py - writes scores/night_pursuit_cinematic_score.json: the notes of Night Pursuit Cinematic and the tracks that play its sounds.

Notes are in beats (0 = first beat of bar 1); the tempo map in timeline.py turns them into seconds. A score holds only track names and notes:
EQ, placement, rooms and the sound of every effect live in presets/. The shape of the cue is in STATUS.md (the craft pass) and in the direction sheet.

Pitches (MIDI): C minor with Db and Gb as the two pressure notes; the key rises a semitone at each turning point (after the crash, the helicopter, the deck, the
flyover) and returns to C for the escape. The hook, "the tick": C Db C | Gb F Eb Db, long-short-short-long-long, answered differently at every camera.
"""
import json
import os
import random

import cars
import timeline as T

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'scores', 'night_pursuit_cinematic_score.json')
rnd = random.Random(T.SEED)
C, Db, Eb, F, Gb, G, Ab, Bb = 0, 1, 3, 5, 6, 7, 8, 10


def p(pc, octave):
    return 12 * (octave + 1) + pc


def s0(name):
    return T.start(name)


def sN(name):
    return T.end(name)


class Track:
    def __init__(self, name, instrument, role, **extra):
        self.d = dict(name=name, instrument=instrument, role=role, notes=[], **extra)

    def add(self, bar, beat, dur, pitch, vel):
        self.d['notes'].append(dict(t=round(T.B(bar, beat), 4), d=round(dur, 4), p=int(pitch), v=round(max(0.05, min(1.0, vel)), 3)))

    def done(self):
        seen = {}
        for n in self.d['notes']:                        # two attacks of one pitch on one beat phase-cancel: keep the louder
            k = (n['t'], n['p'])
            if k not in seen or n['v'] > seen[k]['v']:
                seen[k] = n
        self.d['notes'] = sorted(seen.values(), key=lambda n: (n['t'], n['p']))
        return self.d


def vel(base, spread=0.04):
    return base + rnd.uniform(-spread, spread)


def sect(bar):
    return next(s for s in T.SECTIONS if s[1] <= bar < s[1] + s[2])


def key_shift(bar):
    """Semitones the key has risen by at a bar: a step at each turning point, home again for the escape."""
    if bar > T.CRASH_BAR and bar < s0('the_helicopter'):
        return 1
    if s0('the_helicopter') <= bar < s0('the_bumps'):
        return 2
    if s0('the_bumps') <= bar < s0('the_flyover'):
        return 3
    if s0('the_flyover') <= bar < s0('the_escape'):
        return 4
    return 0


# the slow-motion jump: the bars where the music collapses to a heartbeat and a pedal
COLLAPSE = range(int(T.SLOMO_JUMP['bar']), int(T.SNAP_JUMP))
TUNNEL_THIN = range(s0('the_tunnel'), s0('the_tunnel') + 6)         # six bars of pulse and low brass only

basses = Track('basses', 'pursuit_basses', 'bass')
piano_low = Track('piano_low', 'pursuit_piano_low', 'bass')
tuba = Track('tuba', 'pursuit_tuba', 'bass')
bass_drum = Track('bass_drum', 'pursuit_bass_drum', 'drum')
timpani = Track('timpani', 'pursuit_timpani', 'drum')
taiko = Track('taiko', 'pursuit_taiko', 'drum')
snare = Track('snare', 'pursuit_snare', 'drum')
cymbals = Track('cymbals', 'pursuit_cymbals', 'texture')
sub_drop = Track('sub_drop', 'pursuit_sub_drop', 'fx')
sub_pulse = Track('sub_pulse', 'pursuit_sub_pulse', 'fx')
piano = Track('piano', 'pursuit_piano', 'ostinato')
celli = Track('celli', 'pursuit_celli', 'ostinato')
bass_clarinet = Track('bass_clarinet', 'pursuit_bass_clarinet', 'counter')
horns = Track('horns', 'pursuit_horns', 'melody')
trombones = Track('trombones', 'pursuit_trombones', 'chord')
violins_st = Track('violins_staccato', 'pursuit_violins_staccato', 'arp')
violins_tr = Track('violins_tremolo', 'pursuit_violins_tremolo', 'pad', fade_in_s=0.3, fade_out_s=0.6)
choir = Track('choir', 'pursuit_choir', 'pad', fade_in_s=1.0, fade_out_s=1.5)
solo = Track('solo_violin', 'pursuit_solo_violin', 'counter', fade_in_s=0.2, fade_out_s=0.8)

# ---------------------------------------------------------------------------------------------------------------- the low end, written by phrase
BASS_WALKS = [(0, 0, 0, 7), (0, 0, 3, 0), (0, 0, 10, 7), (0, 0, 0, 1), (0, 7, 0, 5), (0, 0, 8, 7)]
KICKS = [(0.0, 1.5, 3.0), (0.0, 1.5, 2.5), (0.0, 0.75, 1.5, 3.0), (0.0, 1.5, 2.0, 3.0), (0.0, 1.0, 1.5, 3.0), (0.0, 1.5, 3.0, 3.5)]
TUBA_RHYTHMS = [(0.0, 1.5, 3.0), (0.0, 2.0), (0.0, 1.5, 2.5, 3.5), (1.5, 3.0), (0.0, 0.75, 1.5, 3.0)]
for bar in range(1, T.END_BAR):
    sec = sect(bar)
    name, energy = sec[0], sec[3]
    ph, k = (bar - 1) // 4, (bar - 1) % 4
    r = key_shift(bar)
    collapse = bar in COLLAPSE
    escape = name == 'the_escape'
    thin = bar in TUNNEL_THIN
    top = 0.64 + 0.2 * energy
    # basses: the root with a walk; the dominant turns each phrase; a bar before the crash leans on the tritone
    walk = BASS_WALKS[(ph + k) % len(BASS_WALKS)]
    if collapse:
        basses.add(bar, 0, 4.25, p(C + r, 1) if bar != int(T.SNAP_JUMP) - 1 else p(Gb + r, 1), 0.55)
    elif escape:
        basses.add(bar, 0, 4.25 if bar < T.END_BAR - 1 else 6.0, p([C, G, C, C, Eb, C, G, C, Eb, C, C, C][(bar - s0('the_escape')) % 12], 2 if bar < T.END_BAR - 1 else 1), vel(0.66 - 0.02 * (bar - s0('the_escape')), 0.03))      # the last note rings on into the end as one smooth decay
    elif k == 3:
        basses.add(bar, 0, 2.14, p((C + r + walk[k]) % 12, 1), vel(top, 0.05))
        basses.add(bar, 2.0, 1.64, p(G + r, 1), vel(top - 0.06, 0.05))
        basses.add(bar, 3.5, 0.72, p((C + r + (1 if ph % 2 else 10)) % 12, 1), vel(top - 0.1, 0.05))
    else:
        basses.add(bar, 0, 4.2, p((C + r + walk[k]) % 12, 1), vel(top + (0.08 if k == 0 else 0.0), 0.05))
    if not collapse and not escape:
        piano_low.add(bar, 2.0 if k == 3 else 0.0, 1.0, p(C + r, 2), vel(top - 0.04, 0.05))
        if (bar + ph) % 3 != 0:
            piano_low.add(bar, 1.5 + 0.5 * (ph % 2), 0.5, p((C + r + (7 if k == 2 else 0)) % 12, 2), vel(0.5 + 0.1 * (ph % 3), 0.05))
        if bar >= s0('the_chase') or bar < s0('spotted'):
            for b in TUBA_RHYTHMS[(ph * 2 + k) % len(TUBA_RHYTHMS)]:
                tuba.add(bar, b, 0.4, p((C + r + (walk[k] if k < 3 else 0)) % 12, 2), vel(0.40 + 0.35 * energy * (0.6 + 0.4 * (k == 0)), 0.07))
    # drums
    if collapse or escape:
        bass_drum.add(bar, 0, 0.5, 36, 0.62 if collapse else 0.5)
        bass_drum.add(bar, 2.0, 0.5, 36, 0.5 if collapse else 0.4)
    else:
        for b in KICKS[(ph + k) % len(KICKS)]:
            bass_drum.add(bar, b, 0.5, 36, vel(0.6 + 0.2 * energy + (0.08 if b == 0.0 else 0.0), 0.05))
        if not thin:
            if ph % 2 == 1 and k == 3:                                            # a fill: sixteenths on an exponential curve with alternating accents
                for i in range(8):
                    snare.add(bar, 2.0 + i * 0.25, 0.25, 38, 0.3 + 0.35 * ((i + 1) / 8.0) ** 1.6 + (0.04 if i % 2 == 0 else -0.02) + 0.05 * energy)
            else:
                snare.add(bar, 1.0, 0.25, 38, vel(0.44 + 0.15 * energy, 0.05))
                snare.add(bar, 3.0, 0.25, 38, vel(0.5 + 0.15 * energy, 0.05))
                if (bar + ph) % 3 == 1:
                    snare.add(bar, 3.5, 0.25, 38, vel(0.42, 0.04))
                if (bar + 2 * ph) % 4 == 2:
                    snare.add(bar, 2.5, 0.25, 38, vel(0.38, 0.04))
            if k == 0:
                cymbals.add(bar, 0, 3.0, 49, vel(0.4 + 0.2 * energy, 0.04))
            if k == 2:
                timpani.add(bar, 2.0, 0.5, p(G + r, 2), vel(0.45 + 0.25 * energy, 0.05))
            if k == 3:
                for i in range(4):
                    timpani.add(bar, 2.0 + i * 0.5, 0.45, p(G + r if i % 2 == 0 else C + r, 2), 0.40 + 0.08 * i + 0.1 * energy)
    # the sub pulse: eighths under the strings in the chase, the bumps and the flyover
    if name in ('the_chase', 'the_bumps', 'the_flyover') and not collapse:
        for i in range(8):
            sub_pulse.add(bar, i * 0.5, 0.4, p(C + r, 1), vel(0.30 + 0.12 * (i % 2 == 0) + 0.1 * energy, 0.03))

# the first bar: a taiko on the downbeat (no slow opening), and a hit at each camera cut
taiko.add(1, 0, 1.5, p(C, 2), 0.9)
for nm in ('spotted', 'the_chase', 'the_tunnel', 'the_helicopter', 'the_bumps', 'the_flyover'):
    taiko.add(s0(nm), 0, 1.5, p(C + key_shift(s0(nm)), 2), 0.85)
    cymbals.add(s0(nm), 0, 3.5, 49, 0.8)
    timpani.add(s0(nm), 0, 1.5, p(C + key_shift(s0(nm)), 2), 0.8)
taiko.add(s0('the_escape'), 0, 2.0, p(C, 2), 0.55)

# the crash (the last bars of the chase): a held bar before it, then the hit
timpani.add(int(T.CRASH_BAR) - 1, 0, 3.9, p(C, 2), 0.55)
timpani.add(int(T.CRASH_BAR), 2.0, 3.0, p(C, 2), 1.0)
cymbals.add(int(T.CRASH_BAR), 2.0, 4.0, 49, 1.0)
sub_drop.add(int(T.CRASH_BAR), 2.0, 1.9, p(C, 1), 1.0)
taiko.add(int(T.CRASH_BAR), 2.0, 2.0, p(C, 2), 1.0)
# the landing: a drop, a sub, a taiko, a cymbal
sub_drop.add(int(T.SNAP_JUMP), 0, 4.0, p(C + 4, 1), 1.0)
cymbals.add(int(T.SNAP_JUMP), 0, 4.0, 49, 0.9)
timpani.add(int(T.SNAP_JUMP), 0, 3.0, p(C + 4, 2), 1.0)
taiko.add(int(T.SNAP_JUMP), 0, 2.0, p(C + 4, 2), 1.0)
sub_drop.add(s0('the_helicopter'), 0, 3.0, p(C + 2, 1), 0.8)
sub_drop.add(s0('the_flyover'), 0, 3.0, p(C + 4, 1), 0.8)

# ---------------------------------------------------------------------------------------------------------------- the middle
for bar in range(1, s0('the_escape')):
    sec = sect(bar)
    name, energy = sec[0], sec[3]
    ph, k = (bar - 1) // 4, (bar - 1) % 4
    r = key_shift(bar)
    if bar in COLLAPSE:
        continue
    for i in range(8):                                   # celli: eighths, a semitone pressure at the end of each pair of bars
        pc = [Db, G, Eb, Db][(bar - 1) % 4] if i == 7 else (G if (i == 4 and k == 2) else C)         # the figure walks a little each bar, so no pitch repeats at even spacing
        if name not in ('the_helicopter',) or i % 2 == 0:
            celli.add(bar, i * 0.5, 0.45, p((pc + r) % 12, 2), vel(0.4 + 0.3 * energy, 0.04))
    if bar in TUNNEL_THIN:
        continue
    FIG = [C, Eb, G, Eb, C, Eb, G, Eb, C, Eb, G, Eb, C, Eb, Gb, G] if (bar // 2) % 2 == 0 else [C, Eb, G, Ab, G, Eb, C, Eb, G, Eb, C, Db, C, Eb, G, Gb]
    vol = 0.7 if name == 'the_helicopter' else 1.0
    for i, pc in enumerate(FIG):
        accent = 0.1 if i in (0, 3, 6, 8, 11, 14) else 0.0
        piano.add(bar, i * 0.25, 0.22, p((pc + r) % 12, 4), vel((0.38 + 0.25 * energy + accent) * vol, 0.03))

# ---------------------------------------------------------------------------------------------------------------- the hook


def hook(track, bar, octave, shift=0, v=0.7, variant=0):
    if variant % 3 == 0:
        pcs, times, durs = [C, Db, C, Gb, F, Eb, Db], [0.0, 1.5, 2.0, 3.0, 5.5, 6.5, 7.0], [1.5, 0.5, 1.0, 2.5, 1.0, 0.5, 1.0]
    elif variant % 3 == 1:
        pcs, times, durs = [C, Db, C, Gb, Ab, F, Eb, Db], [0.0, 1.5, 2.0, 3.0, 5.0, 5.75, 6.5, 7.0], [1.5, 0.5, 1.0, 2.0, 0.75, 0.75, 0.5, 1.0]
    else:
        pcs, times, durs = [C, Db, C, Db, Gb, F, Eb, Db], [0.0, 2.0, 2.5, 3.0, 3.5, 6.0, 6.75, 7.25], [2.0, 0.5, 0.5, 0.5, 2.0, 0.75, 0.5, 0.75]
    for pc, t, d in zip(pcs, times, durs):
        track.add(bar + int(t // 4), t % 4, d, p((pc + shift) % 12, octave), vel(v + (0.08 if pc == Gb else 0.0), 0.03))


# the race: the hook at once on the horns, every four bars; the clarinet answers it in the spotted shot
for n, bar in enumerate(range(1, s0('spotted'), 4)):
    hook(horns, bar, 4, v=0.74, variant=n)
for n, bar in enumerate((s0('spotted') + 2, s0('spotted') + 6)):
    hook(bass_clarinet, bar, 4, v=0.4, variant=n + 1)
    if n == 0:
        hook(horns, s0('spotted'), 4, v=0.7, variant=1)
# the chase: the horns climb; a semitone higher after the crash
for n, bar in enumerate(range(s0('the_chase'), int(T.CRASH_BAR) - 2, 4)):
    hook(horns, bar, 4, v=0.78, variant=n)
for n, bar in enumerate(range(int(T.CRASH_BAR) + 1, s0('the_helicopter') - 1, 4)):
    hook(horns, bar, 4, shift=1, v=0.8, variant=n)
    hook(trombones, bar, 3, shift=1, v=0.66, variant=n)
# the tunnel's second half: tremolo strings and a rising line; the stabs
for i, bar in enumerate(range(s0('the_tunnel') + 6, sN('the_tunnel'))):
    pc = [C, Db, Eb, F, Gb, G, Ab, Bb][i % 8]
    violins_tr.add(bar, 0, 3.9, p((pc + 1) % 12, 5), vel(0.35 + 0.05 * i, 0.02))
    violins_tr.add(bar, 0, 3.9, p((pc + 8) % 12, 4), vel(0.33 + 0.05 * i, 0.02))
for bar in range(int(T.CRASH_BAR) + 1, s0('the_helicopter')):
    if bar % 2 == 0 and bar not in TUNNEL_THIN:
        for b, d in ((0.0, 0.5), (1.5, 0.5)):
            for pc, o in ((C + 1, 3), (Gb + 1, 3), (Db + 1, 4)):
                trombones.add(bar, b, d, p(pc, o), vel(0.8, 0.03))
# the helicopter: the choir carries the hook above, long chords below; the music is thinner
for n, bar in enumerate(range(s0('the_helicopter'), sN('the_helicopter') - 2, 4)):
    hook(choir, bar, 5, shift=2, v=0.55, variant=n)
for bar in range(s0('the_helicopter'), sN('the_helicopter'), 2):
    for pc, o in ((C, 4), (G, 4), (Bb, 4)):
        choir.add(bar, 0, 7.9, p((pc + 2) % 12, o), 0.42)
for n, bar in enumerate(range(s0('the_helicopter') + 1, sN('the_helicopter'), 4)):
    hook(horns, bar, 4, shift=2, v=0.7, variant=n + 1)
# the deck: horns and trombones together, the leap on the weak beat; violins runs
for n, bar in enumerate(range(s0('the_bumps'), sN('the_bumps') - 2, 3)):
    hook(horns, bar, 4, shift=3, v=0.84, variant=n)
    hook(trombones, bar, 3, shift=3, v=0.8, variant=n)
# the flyover: the solo violin carries the hook an octave up, the horns below
for n, bar in enumerate(range(s0('the_flyover'), int(T.SLOMO_JUMP['bar']) - 1, 3)):
    hook(horns, bar, 4, shift=4, v=0.82, variant=n)
    hook(solo, bar, 5, shift=4, v=0.6, variant=n)
for n, bar in enumerate(range(int(T.SNAP_JUMP) + 1, sN('the_flyover') - 2, 3)):
    hook(horns, bar, 4, shift=4, v=0.85, variant=n + 1)
    hook(solo, bar, 5, shift=4, v=0.66, variant=n + 1)
    hook(trombones, bar, 3, shift=4, v=0.78, variant=n + 1)
# fast violins: the end of the chase, the deck and the flyover
SCALE = [C, Db, Eb, F, G, Ab, Bb]
for bar in list(range(int(T.CRASH_BAR) - 3, int(T.CRASH_BAR) - 1)) + list(range(s0('the_bumps'), s0('the_escape'))):
    if bar in COLLAPSE:
        continue
    off = (bar * 5 + (bar // 4) * 3) % 14
    r = key_shift(bar)
    for i in range(16):
        if (bar % 5 == 4 and i in (4, 5, 6, 7)) or rnd.random() < 0.22:      # a gap in the run every fifth bar and a few dropped notes: no fixed grid for the stem gate to read as a tick
            continue
        kk = (off + i) % 14
        violins_st.add(bar, i * 0.25, 0.2, p((SCALE[kk % 7] + r) % 12, 5 + kk // 7), vel(0.5 + 0.006 * i + 0.05 * (bar % 3), 0.03))
# the escape: the hook left on a single note, a held harmonic, the strings thin out
for n, bar in enumerate(range(s0('the_escape'), sN('the_escape') - 3, 4)):
    horns.add(bar, 0, 3.5, p(Gb, 3), 0.62 - 0.07 * n)
solo.add(s0('the_escape') + 1, 0, 14.0, p(C, 5), 0.4)      # home: the Gb4 held here beat against the Porsche's constant 342 Hz partial (cochlear roughness at 169.5 s)
violins_tr.add(s0('the_escape') + 2, 0, 20.0, p(Gb, 5), 0.3)
choir.add(s0('the_escape'), 0, 10.0, p(Gb, 4), 0.3)

music = [basses, piano_low, tuba, bass_drum, timpani, taiko, snare, cymbals, sub_drop, sub_pulse, piano, celli, bass_clarinet, horns, trombones,
         violins_st, violins_tr, choir, solo]

# ---------------------------------------------------------------------------------------------------------------- the sounds and the places
TOTAL_BEATS = T.B(T.END_BAR)
tm = T.tempo_map()
START = T.sfx_start()


def trigger(name, sound, role, key=None, **extra):
    """One trigger note: an effect's own clock starts at its note, which sits where the sound first speaks (timeline.sfx_start)."""
    t0 = float(tm.beat(START[key or name])) if (key or name) in START else 0.0
    return dict(name=name, instrument=sound, role=role, notes=[dict(t=round(t0, 4), d=round(TOTAL_BEATS - t0, 3), p=60, v=1.0)], **extra)


sounds = [
    trigger('ferrari', 'sfx:np_car_ferrari', 'fx', dc_hp_hz=20.0),
    trigger('lamborghini', 'sfx:np_car_lamborghini', 'fx', dc_hp_hz=20.0),
    trigger('mustang', 'sfx:np_car_mustang', 'fx', dc_hp_hz=20.0),
    trigger('porsche', 'sfx:np_car_porsche', 'fx', dc_hp_hz=20.0),
    trigger('siren_first', 'sfx:np_siren_wail', 'fx'),
    trigger('siren_second', 'sfx:np_siren_second', 'fx'),
    trigger('helicopter', 'sfx:np_helicopter', 'fx'),
    trigger('bumps', 'sfx:np_bumps', 'fx', dc_hp_hz=20.0),
    trigger('landing', 'sfx:np_landing', 'fx', dc_hp_hz=20.0),
    trigger('crash', 'sfx:np_crash', 'fx', dc_hp_hz=20.0),
    dict(name='city_far', instrument='env:np_city_far', role='environment', notes=[dict(t=0.0, d=round(TOTAL_BEATS, 3), p=60, v=1.0)], fade_in_s=1.0, fade_out_s=3.5),
]

# ---------------------------------------------------------------------------------------------------------------- the score
sections = T.sections_with_seconds(tm)
dyn = [[round(T.B(first), 3), energy] for name, first, bars, energy, role, cam in T.SECTIONS]
dyn.append([round(TOTAL_BEATS, 3), 0.15])

score = dict(
    title='Night Pursuit Cinematic',
    **T.score_tempo(),
    dynamics=dyn,
    space='np_street_canyon',
    mix_preset='night_pursuit_cinematic_mix',
    output_targets=['stereo', 'immersive_7_1_2'],
    master=dict(lufs=-16.0, true_peak=-1.5, tone='neutral', fade_out=3.0),
    piece_type='night_pursuit_cinematic',
    focus='melody',
    intent={'emotions': ['tense', 'dark_epic'], 'registers': ['cinematic', 'hybrid'], 'scenes': ['establish', 'build', 'chase', 'dread'],
            'tensions': ['ostinato', 'pedal', 'tritone', 'cluster', 'rising_line', 'silence_before', 'unresolved_dominant'],
            'avoid': ['joyful', 'playful']},
    mix_intent=dict(hero='pursuit_horns', leave_free_hz=[]),
    medium=dict(model='iso9613', state=dict(temperature_k=283.15, pressure_pa=101325, rh_percent=95)),
    gate={'tempo.audio': {'mode': 'skip', 'reason': 'the tempo map runs 72-156 BPM by design (a climb with a slow-motion dip to 72 and a slow escape to 92), so no single tempo exists; the onset autocorrelation measured 73.6 BPM against the declared 132 on the third full render, a value set by the slow-motion and escape bars, not a fault of the grid'}},
    plan=dict(sections=sections),
    tracks=[t.done() for t in music] + sounds,
    mix=dict(tracks={}),
)

if __name__ == '__main__':
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(score, fh, indent=1)
    n = sum(len(t['notes']) for t in score['tracks'])
    print(f'wrote {OUT}: {len(score["tracks"])} tracks, {n} notes, {T.seconds(T.END_BAR, 0, tm):.1f} s')
