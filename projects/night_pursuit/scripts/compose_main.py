#!/usr/bin/env python3
"""compose_main.py - writes scores/night_pursuit_score.json: the notes of Night Pursuit and the tracks that play its sounds.

Notes are in beats (0 = first beat of bar 1); the tempo map in timeline.py turns them into seconds. A score holds only track names and notes:
EQ, placement, rooms and the sound of every effect live in presets/. The shape of the cue is in STATUS.md (the craft pass) and in the
direction sheet; this file executes it.

Pitches (MIDI): C minor with Db and Gb as the two pressure notes. The hook, "the tick": C Db C | Gb F, long-short-short-long-long.
"""
import json
import os
import random

import timeline as T

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'scores', 'night_pursuit_score.json')
rnd = random.Random(T.SEED)

C, Db, Eb, F, Gb, G, Ab, Bb = 0, 1, 3, 5, 6, 7, 8, 10                 # pitch classes


def p(pc, octave):
    return 12 * (octave + 1) + pc                                      # C4 = 60


def s0(name):
    return T.start(name)


def sN(name):
    sec = next(s for s in T.SECTIONS if s[0] == name)
    return sec[1] + sec[2]


class Track:
    def __init__(self, name, instrument, role, **extra):
        self.d = dict(name=name, instrument=instrument, role=role, notes=[], **extra)

    def add(self, bar, beat, dur, pitch, vel):
        t = T.B(bar, beat)
        self.d['notes'].append(dict(t=round(t, 4), d=round(dur, 4), p=int(pitch), v=round(max(0.05, min(1.0, vel)), 3)))

    def done(self):
        seen = {}
        for n in self.d['notes']:                        # two attacks of one pitch on one beat phase-cancel: keep the louder
            k = (n['t'], n['p'])
            if k not in seen or n['v'] > seen[k]['v']:
                seen[k] = n
        self.d['notes'] = list(seen.values())
        self.d['notes'].sort(key=lambda n: (n['t'], n['p']))
        return self.d


def vel(base, spread=0.04):
    return base + rnd.uniform(-spread, spread)


tracks = []

# ---------------------------------------------------------------------------------------------------------------- the low end
basses = Track('basses', 'pursuit_basses', 'bass')
piano_low = Track('piano_low', 'pursuit_piano_low', 'bass')
tuba = Track('tuba', 'pursuit_tuba', 'bass')
bass_drum = Track('bass_drum', 'pursuit_bass_drum', 'drum')
timpani = Track('timpani', 'pursuit_timpani', 'drum')
snare = Track('snare', 'pursuit_snare', 'drum')
cymbals = Track('cymbals', 'pursuit_cymbals', 'texture')
sub_drop = Track('sub_drop', 'pursuit_sub_drop', 'fx')

# The pulse never stops once it starts. Its root rises a semitone at each turning point: C (stakeout .. turn), Db after the drift snap
# (the underpass and the first half of the roadblock), C again for the second half and the bridge ends on C so the cut lands on the tonic.
def root_at(bar):
    if bar < T.SNAP_DRIFT:
        return C
    if bar < T.SNAP_SPIN:
        return Db if bar < s0('the_roadblock') + 9 else C
    return C


def bar_chord_root(bar):
    return root_at(bar)


# the stakeout: a heartbeat of bass drum, one low C every bar
for bar in range(s0('the_stakeout'), sN('the_stakeout')):
    basses.add(bar, 0, 4.02, p(C, 1), vel(0.74, 0.02))
    piano_low.add(bar, 0, 3.8, p(C, 1), vel(0.45, 0.02)) if bar >= s0('the_stakeout') + 2 else None
    bass_drum.add(bar, 0, 0.5, 36, vel(0.50, 0.03))
    bass_drum.add(bar, 1.0, 0.5, 36, vel(0.38, 0.03))
    if bar % 2 == 0:
        bass_drum.add(bar, 3.0, 0.5, 36, vel(0.30, 0.03))

# spotted: the cruiser; the pedal breathes, the heart quickens
for bar in range(s0('spotted'), sN('spotted')):
    basses.add(bar, 0, 4.02, p(C, 1), vel(0.74, 0.02))
    piano_low.add(bar, 0, 3.8, p(C, 1), vel(0.5, 0.02))
    for b in (0, 1.5, 3.0):
        bass_drum.add(bar, b, 0.5, 36, vel(0.5, 0.03))
    if bar == sN('spotted') - 1:
        timpani.add(bar, 2.0, 1.0, p(C, 2), 0.6)              # a swell into the launch
        timpani.add(bar, 3.0, 1.0, p(C, 2), 0.75)

# the avenue and on: a 3+3+2 drum pulse, basses on the root, tuba doubling, snare on the backbeat
THREE_THREE_TWO = (0.0, 1.5, 3.0)
for bar in range(s0('the_avenue'), sN('the_bridge')):
    r = bar_chord_root(bar)
    sect = next(s for s in T.SECTIONS if s[1] <= bar < s[1] + s[2])
    energy = sect[3]
    quiet = (sect[0] == 'the_turn' and bar in (T.SLOMO_DRIFT['bar'], T.SLOMO_DRIFT['bar'] + 1, T.SLOMO_DRIFT['bar'] + 2)) or \
            (sect[0] == 'the_roadblock' and bar in (T.SLOMO_SPIN['bar'], T.SLOMO_SPIN['bar'] + 1))
    under = sect[0] == 'under_the_bridge' and bar < s0('under_the_bridge') + 6          # six bars of pulse and low brass only
    if quiet:
        basses.add(bar, 0, 4.02, p(C, 1), 0.55)
        bass_drum.add(bar, 0, 0.5, 36, 0.62)
        bass_drum.add(bar, 2.0, 0.5, 36, 0.5)
        continue
    if bar % 4 == 3:
        basses.add(bar, 0, 2.0, p(G, 1), vel(0.58 + 0.2 * energy, 0.03))          # the dominant, never resolved
        basses.add(bar, 2.0, 2.02, p(r, 1), vel(0.6 + 0.2 * energy, 0.03))
    else:
        basses.add(bar, 0, 4.02, p(r, 1), vel(0.6 + 0.2 * energy, 0.03))
    piano_low.add(bar, 0, 1.0, p(r, 2), vel(0.6 + 0.15 * energy, 0.03))
    piano_low.add(bar, 1.5, 0.5, p(r, 2), vel(0.5, 0.03))
    for b in THREE_THREE_TWO:
        tuba.add(bar, b, 1.0, p(r, 2), vel(0.5 + 0.2 * energy, 0.03)) if bar >= s0('the_avenue') + 2 else None
    for b in (0.0, 1.5, 3.0):
        bass_drum.add(bar, b, 0.5, 36, vel(0.62 + 0.2 * energy, 0.03))
    if not under:
        bass_drum.add(bar, 2.25, 0.25, 36, vel(0.58, 0.03)) if bar % 2 else None
        snare.add(bar, 1.0, 0.25, 38, vel(0.46 + 0.15 * energy, 0.03))
        snare.add(bar, 3.0, 0.25, 38, vel(0.5 + 0.15 * energy, 0.03))
        if bar % 4 == 3:
            snare.add(bar, 3.5, 0.25, 38, vel(0.42, 0.03))                       # a ghost note so no two four-bar blocks are the same
            snare.add(bar, 3.75, 0.25, 38, vel(0.38, 0.03))
    if bar % 4 == 0 and not under:
        cymbals.add(bar, 0, 3.0, 49, vel(0.4 + 0.2 * energy, 0.03))             # an accent at each phrase start
    if bar in (s0('the_avenue'), s0('the_turn'), s0('under_the_bridge') + 6, s0('the_roadblock'), s0('the_bridge')):
        cymbals.add(bar, 0, 3.5, 49, 0.8)
        timpani.add(bar, 0, 1.5, p(r, 2), 0.85)
    if bar % 2 == 0 and not under:
        timpani.add(bar, 3.0, 0.5, p(G, 2), vel(0.5 + 0.2 * energy, 0.04))      # the dominant under the pulse, never resolved

# the bar before the crash is hollow: no snare roll, only a timpani swell
# the held bar before the crash: only a timpani swell, then the hit
timpani.add(int(T.CRASH_BAR) - 1, 0, 3.9, p(C, 2), 0.55)
timpani.add(int(T.CRASH_BAR), 0, 3.0, p(C, 2), 1.0)
cymbals.add(int(T.CRASH_BAR), 0, 4.0, 49, 1.0)
sub_drop.add(int(T.SNAP_DRIFT), 0, 4.0, p(C, 1), 1.0)
sub_drop.add(int(T.CRASH_BAR), 0, 4.0, p(C, 1), 1.0)
sub_drop.add(s0('the_bridge'), 0, 3.0, p(C, 1), 0.9)
cymbals.add(int(T.SNAP_DRIFT), 0, 4.0, 49, 0.9)
timpani.add(int(T.SNAP_DRIFT), 0, 3.0, p(Db, 2), 1.0)

# ---------------------------------------------------------------------------------------------------------------- the middle
piano = Track('piano', 'pursuit_piano', 'ostinato')
celli = Track('celli', 'pursuit_celli', 'ostinato')
bass_clarinet = Track('bass_clarinet', 'pursuit_bass_clarinet', 'counter')
horns = Track('horns', 'pursuit_horns', 'melody')
trombones = Track('trombones', 'pursuit_trombones', 'chord')
violins_st = Track('violins_staccato', 'pursuit_violins_staccato', 'arp')
violins_tr = Track('violins_tremolo', 'pursuit_violins_tremolo', 'pad', fade_in_s=0.3, fade_out_s=0.6)

# celli: eighths from the spotting, a semitone pressure on the second half of each pair of bars
for bar in range(s0('spotted'), sN('the_bridge')):
    quiet = (T.SLOMO_DRIFT['bar'] <= bar < T.SNAP_DRIFT) or (T.SLOMO_SPIN['bar'] <= bar < T.SNAP_SPIN)
    under = s0('under_the_bridge') <= bar < s0('under_the_bridge') + 6
    if quiet:
        continue
    r = bar_chord_root(bar)
    sect = next(s for s in T.SECTIONS if s[1] <= bar < s[1] + s[2])
    for i in range(8):
        pc = r if (i % 4 != 3) else (Db if r == C else C) if (bar % 2 == 1 and i == 7) else r
        celli.add(bar, i * 0.5, 0.45, p(pc, 2), vel(0.4 + 0.3 * sect[3], 0.04))

# piano sixteenths: the one constant in the middle, from the avenue. C Eb G Eb figures that lean on Db / Gb at bar ends.
FIG_A = [C, Eb, G, Eb, C, Eb, G, Eb, C, Eb, G, Eb, C, Eb, Gb, G]
FIG_B = [C, Eb, G, Ab, G, Eb, C, Eb, G, Eb, C, Db, C, Eb, G, Gb]
for bar in range(s0('the_avenue'), sN('the_bridge')):
    quiet = (T.SLOMO_DRIFT['bar'] <= bar < T.SNAP_DRIFT) or (T.SLOMO_SPIN['bar'] <= bar < T.SNAP_SPIN)
    under = s0('under_the_bridge') <= bar < s0('under_the_bridge') + 6
    if quiet or under:
        continue
    shift = (Db - C) if root_at(bar) == Db else 0
    fig = FIG_A if (bar // 2) % 2 == 0 else FIG_B
    sect = next(s for s in T.SECTIONS if s[1] <= bar < s[1] + s[2])
    for i, pc in enumerate(fig):
        accent = 0.1 if i in (0, 3, 6, 8, 11, 14) else 0.0               # the 3+3+2 accent inside the sixteenths
        piano.add(bar, i * 0.25, 0.22, p((pc + shift) % 12, 4), vel(0.38 + 0.25 * sect[3] + accent, 0.03))

# the hook. Rhythm (beats from the bar start): C 1.5, Db 0.5, C 1.0, | Gb on the weak beat (beat 3.5 of the second bar... leap), F long.
def hook(track, bar, octave, shift=0, v=0.7, width=1.0, variant=0):
    if variant % 3 == 0:
        pcs, times, durs = [C, Db, C, Gb, F, Eb, Db], [0.0, 1.5, 2.0, 3.0, 5.5, 6.5, 7.0], [1.5, 0.5, 1.0, 2.5, 1.0, 0.5, 1.0]
    elif variant % 3 == 1:                                   # the tail climbs once before it falls: the leap is the same, the answer is not
        pcs, times, durs = [C, Db, C, Gb, Ab, F, Eb, Db], [0.0, 1.5, 2.0, 3.0, 5.0, 5.75, 6.5, 7.0], [1.5, 0.5, 1.0, 2.0, 0.75, 0.75, 0.5, 1.0]
    else:                                                    # a long first note, so the leap lands later
        pcs, times, durs = [C, Db, C, Db, Gb, F, Eb, Db], [0.0, 2.0, 2.5, 3.0, 3.5, 6.0, 6.75, 7.25], [2.0, 0.5, 0.5, 0.5, 2.0, 0.75, 0.5, 0.75]
    for pc, t, d in zip(pcs, times, durs):
        track.add(bar + int(t // 4), t % 4, d * width, p((pc + shift) % 12, octave), vel(v + (0.08 if pc == Gb else 0.0), 0.03))


# bass clarinet whispers it in the spotting (every other pair of bars after the cruiser appears)
for bar in (s0('spotted') + 2, s0('spotted') + 4):
    hook(bass_clarinet, bar, 3, v=0.38)
# horns state it at the launch (every 4 bars, answered by the cello pedal), then climb a semitone and double in octaves after the drift snap
for bar in range(s0('the_avenue') + 2, int(T.SLOMO_DRIFT['bar']), 4):
    hook(horns, bar, 4, v=0.72, variant=bar // 4)
for bar in range(int(T.SNAP_DRIFT) + 1, int(sN('the_roadblock')) - 2, 4):
    if T.SLOMO_SPIN['bar'] - 1 <= bar <= T.SNAP_SPIN:
        continue
    hook(horns, bar, 4, shift=1, v=0.78, variant=bar // 4)
    hook(trombones, bar, 3, shift=1, v=0.66)
# on the bridge: horns and trombones together, the leap on the weak beat, then the fast violins join
for bar in range(s0('the_bridge'), sN('the_bridge') - 2, 3):
    hook(horns, bar, 4, v=0.85, variant=bar // 4)
    hook(trombones, bar, 3, v=0.80)

# trombone stabs (roadblock): a tritone cluster on the first and third beat every other bar
for bar in range(s0('the_roadblock'), sN('the_roadblock')):
    if T.SLOMO_SPIN['bar'] <= bar < T.SNAP_SPIN:
        continue
    if bar % 2 == 0:
        for b, d in ((0.0, 0.5), (1.5, 0.5)):
            for pc, o in ((C, 3), (Gb, 3), (Db, 4)):
                trombones.add(bar, b, d, p(pc, o), vel(0.8, 0.03))
# the held bar before the crash: a bare fifth-less cluster, whispered, so the crash has somewhere to land
for pc, o in ((C, 3), (Gb, 3), (Db, 4)):
    trombones.add(int(T.SLOMO_SPIN['bar']) + 2, 0, 3.9, p(pc, o), 0.5)

# the underpass: tremolo strings and a rising line over the second half
rising = [C, Db, Eb, F, Gb, G, Ab, Bb]
for i, bar in enumerate(range(s0('under_the_bridge') + 6, sN('under_the_bridge'))):
    pc = rising[i % len(rising)]
    violins_tr.add(bar, 0, 3.9, p(pc, 5), vel(0.35 + 0.05 * i, 0.02))
    violins_tr.add(bar, 0, 3.9, p((pc + 7) % 12, 4), vel(0.33 + 0.05 * i, 0.02))
# tremolo pad in the roadblock's second half
for bar in range(int(T.SNAP_SPIN) + 1, sN('the_roadblock'), 2):
    violins_tr.add(bar, 0, 7.9, p(Gb, 5), 0.6)
    violins_tr.add(bar, 0, 7.9, p(C, 5), 0.58)

# fast violins (staccato runs of sixteenths up the C minor scale), the roadblock's last bars and the whole bridge
SCALE = [C, Db, Eb, F, G, Ab, Bb]
for bar in list(range(int(T.SNAP_SPIN), sN('the_roadblock'))) + list(range(s0('the_bridge'), sN('the_bridge'))):
    off = (bar % 3) * 2
    for i in range(16):
        k = (off + i) % 14
        octv = 5 + k // 7
        pc = SCALE[k % 7]
        if bar == sN('the_bridge') - 1 and i >= 8:
            break
        violins_st.add(bar, i * 0.25, 0.2, p(pc, octv), vel(0.45 + 0.01 * i, 0.04))

# the cliff: the cut, then one long Gb and its high harmonic
violins_tr.add(s0('the_cliff') + 1, 0, 24.0, p(Gb, 4), 0.4)
violins_tr.add(s0('the_cliff') + 2, 0, 20.0, p(Gb, 6), 0.3)
horns.add(s0('the_cliff') + 1, 1.0, 2.0, p(Gb, 3), 0.4)

music = [basses, piano_low, tuba, bass_drum, timpani, snare, cymbals, sub_drop, piano, celli, bass_clarinet, horns, trombones, violins_st, violins_tr]

# ---------------------------------------------------------------------------------------------------------------- sounds and places
TOTAL_BEATS = T.B(T.END_BAR)
tm = T.tempo_map()


START = T.sfx_start()


def whole(name, sound, role, **extra):
    """One trigger note: an effect's own clock starts at its note, which sits where the sound first speaks (timeline.sfx_start)."""
    t0 = float(tm.beat(START[name])) if name in START else 0.0
    d = dict(name=name, instrument=sound, role=role, notes=[dict(t=round(t0, 4), d=round(TOTAL_BEATS - t0, 3), p=60, v=1.0)], **extra)
    return d


sounds = [
    whole('engine', 'sfx:np_engine', 'fx', dc_hp_hz=20.0),
    whole('tyres', 'sfx:np_drift_squeal', 'fx'),
    whole('wipers', 'sfx:np_wipers', 'fx'),
    whole('siren_first', 'sfx:np_siren_wail', 'fx'),
    whole('siren_second', 'sfx:np_siren_second', 'fx'),
    whole('crash', 'sfx:np_crash', 'fx'),
    whole('rain_street', 'env:np_rain_street', 'environment', fade_in_s=2.5, fade_out_s=4.0),
    whole('rain_awnings', 'env:np_rain_awnings', 'environment', fade_in_s=2.5, fade_out_s=4.0),
    whole('city_far', 'env:np_city_far', 'environment', fade_in_s=3.0, fade_out_s=4.0),
]

# ---------------------------------------------------------------------------------------------------------------- the score
sections = T.sections_with_seconds(tm)
dyn = []
for name, first, bars, energy, role in T.SECTIONS:
    dyn.append([round(T.B(first), 3), energy])
dyn.append([round(TOTAL_BEATS, 3), 0.15])

score = dict(
    title='Night Pursuit',
    **T.score_tempo(),
    dynamics=dyn,
    space='np_street_canyon',
    mix_preset='night_pursuit_mix',
    output_targets=['stereo', 'immersive_7_1'],
    master=dict(lufs=-16.0, true_peak=-1.5, tone='neutral', fade_out=2.5),
    piece_type='night_pursuit',
    focus='melody',
    intent={'emotions': ['tense', 'dark_epic'], 'registers': ['cinematic', 'hybrid'], 'scenes': ['establish', 'build', 'chase', 'dread'],
            'tensions': ['ostinato', 'pedal', 'tritone', 'cluster', 'rising_line', 'silence_before', 'unresolved_dominant'],
            'avoid': ['joyful', 'playful', 'hopeful']},
    mix_intent=dict(hero='pursuit_horns', leave_free_hz=[]),
    medium=dict(model='iso9613', state=dict(temperature_k=283.15, pressure_pa=101325, rh_percent=95)),
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
