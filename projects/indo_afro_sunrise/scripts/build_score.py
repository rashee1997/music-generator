"""Write scores/indo_afro_sunrise_score.json — notes only.

Indo-Afro Sunrise: an upbeat Indo-Afro groove (A mixolydian, 112 BPM, 32 bars) with an Indian
tanpura/bansuri/tabla layer over an Afrobeat kit, djembe and shekere, played inside a rainforest
canopy and delivered immersive (stereo + 7.1). This script decides pitches, times and the velocity a
player would use; every level, space, stereo position and room number lives in the presets.

The revised pass (2026-11-27) answers the pattern audit: a part that played one written bar for
thirty-two bars was the reason the piece read as a loop, and a velocity that never moved was the reason
a chorus did not lift. Every part now has bar-phase variants, a fill or turnaround where a player
would put one, a rest where the arrangement needs air, and a level that follows its section.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT, '..', '..', 'scripts'))
from soundbank import DRUM_KEYS  # noqa: E402  (GM percussion keys; world drums are named stand-ins)

BPM = 112
# A natural score counts time in BEATS (render_natural.py line 44: the dynamics arc is "0..1 (beats)"),
# so one beat is the unit here and 32 bars of 4/4 are 128 beats = 68.57 s at 112 BPM.
BEAT = 1.0
BAR = 4.0
BARS = 32
TOTAL = BARS * BAR          # 128 beats


def sec(beats):
    """Beats -> seconds, for the fields (plan sections, master fade) that are written in seconds."""
    return beats * 60.0 / BPM

CHORDS = {'A': [57, 61, 64, 69], 'G': [55, 59, 62, 67], 'D': [50, 54, 57, 62], 'E': [52, 56, 59, 64]}
ROOTS = {'A': 33, 'G': 31, 'D': 38, 'E': 40}
PROG = ['A', 'G', 'D', 'A'] * 4            # 16 two-bar chords = 32 bars
SCALE = [69, 71, 73, 76, 78, 81, 83]       # A mixolydian from A4

SECTIONS = [
    ('dawn', 1, 8, 0.32),
    ('grove', 9, 16, 0.7),
    ('high_sun', 17, 24, 0.95),
    ('golden_hour', 25, 32, 0.6),
]


def note(t, d, p, v):
    return {'t': round(t, 4), 'd': round(max(d, 0.05), 4), 'p': int(p), 'v': round(min(max(v, 0.05), 0.98), 3)}


def bar_time(bar):
    return (bar - 1) * BAR


def chord_at(bar):
    return PROG[min(len(PROG) - 1, (bar - 1) // 2)]


def energy_at(bar):
    for _name, b0, b1, e in SECTIONS:
        if b0 <= bar <= b1:
            return e
    return 0.5


def gain(bar):
    """The section's level as a multiplier: dawn 0.79, grove 0.99, high_sun 1.14, golden_hour 0.95.

    A written velocity that stays at one number all piece is the fault the `pattern.velocity_flat` and
    `shape.contrast` rows name, and it is the arranger's job to fix it, not the mixer's."""
    return 0.62 + 0.55 * energy_at(bar)


def v(bar, base, accent=1.0):
    return base * gain(bar) * accent


def tracks():
    out = []

    # 1. tanpura: the drone the whole piece sits on, retriggered every four bars so it breathes.
    # A drone is the one part that does hold, so its variation is in the register the phrase sits in and
    # in how hard the player plucks, never in a new figure.
    tan = []
    drone_roots = {1: 45, 5: 43, 9: 38, 13: 45, 17: 43, 21: 45, 25: 38, 29: 45}
    for b in range(1, BARS + 1, 4):
        t = bar_time(b)
        dur = min(4 * BAR + 1.0, TOTAL - t)
        root = drone_roots.get(b, 45)
        lift = 1.0 if b in (17, 21) else 0.92        # the sun's peak is plucked a little harder
        tan.append(note(t, dur, root, v(b, 0.42 * lift)))
        tan.append(note(t, dur, root + 7, v(b, 0.30 * lift + (0.04 if b in (25, 29) else 0.0))))
        tan.append(note(t + 0.5 * BEAT, dur * 0.9, root + 12, v(b, 0.26 * lift)))
    out.append({'name': 'tanpura', 'instrument': 'tambura', 'role': 'drone', 'notes': tan,
                'spatial': {'azimuth': 0.0, 'elevation': 0.0, 'distance': 4.0},
                'fade_in_s': 2.0, 'fade_out_s': 3.0})

    # 2. bass: one owner of the low end. Three written bars - a statement, a pushed statement, and a
    # turnaround that walks into the next chord on the fourth - so the line has an engine and a seam.
    bass = []
    fig_a = [(0.0, 0.75, 'r', 1.0), (0.75, 0.75, 'r', 0.7), (1.5, 1.0, '5', 0.88),
             (2.5, 0.5, '8', 0.82), (3.0, 0.5, '5', 0.95), (3.5, 0.5, '8', 0.7)]
    fig_b = [(0.0, 0.5, 'r', 1.0), (0.5, 0.5, 'r', 0.62), (1.0, 0.75, '5', 0.86),
             (1.75, 0.25, 'r', 0.58), (2.0, 1.0, '8', 0.9), (3.0, 0.5, '5', 0.92), (3.5, 0.5, '8', 0.74)]
    fig_c = [(0.0, 0.75, 'r', 0.98), (0.75, 0.75, '5', 0.8), (1.5, 0.5, '8', 0.86),
             (2.0, 0.5, 'b7', 0.72), (2.5, 0.5, 'r', 0.9), (3.0, 0.5, '5', 0.86), (3.5, 0.5, '9', 0.78)]
    for b in range(5, BARS + 1):
        t, chord = bar_time(b), chord_at(b)
        root = ROOTS[chord] if b != 32 else ROOTS['A']
        beat_in_group = (b - 1) % 4
        if b in (8, 16, 24):                       # the breath before a new section: the bass drops out
            continue
        # a bass note is held to the next onset: the humanizer plays 90 % of the written length, so a two-beat
        # note written as 2.0 beats leaves a 107 ms hole and the dropout row calls it a fault
        if b <= 8:                                 # dawn: two long notes, no engine yet
            bass.append(note(t, 2.24 * BEAT, root, v(b, 0.72)))
            bass.append(note(t + 2.0 * BEAT, 2.24 * BEAT, root + 7, v(b, 0.62)))
            continue
        fig = fig_c if beat_in_group == 3 else (fig_b if beat_in_group == 1 else fig_a)
        for beat, dur, which, acc in fig:
            p = {'r': root, '5': root + 7, '8': root + 12, 'b7': root + 10,
                 '9': root + 14}[which]
            # the register pops: the last phrase of each section answers an octave up
            if b >= 29 and which in ('5', '8'):
                p += 12
            bass.append(note(t + beat * BEAT, min(dur * 1.12, 4.0 - beat) * BEAT, p, v(b, 0.72, acc)))
    out.append({'name': 'bass', 'instrument': 'finger_bass', 'role': 'bass', 'notes': bass,
                'spatial': {'azimuth': -25.0, 'elevation': 0.0, 'distance': 3.0}})

    # 3. guitar: highlife skank, the Afro half of the rhythm guitar. Four strum shapes rotate with the
    # four-bar phrase, and the driving one only arrives with the full band.
    gtr = []
    strums = {
        'skank': (0.5, 1.5, 2.5, 3.5),
        'push': (0.75, 1.75, 2.75, 3.75),
        'half': (0.5, 2.5),
        'drive': (0.0, 1.0, 2.0, 3.0, 3.5),
    }
    for b in range(3, BARS + 1):
        t, chord = bar_time(b), chord_at(b)
        if b in (8, 24):                           # both section seams leave the guitar out for a bar
            continue
        if b in (28, 29):                          # golden_hour: the band thins to let the flute speak
            continue
        beat_in_group = (b - 1) % 4
        shape = 'drive' if b >= 17 and beat_in_group in (0, 1) else \
            ('half' if b <= 8 else ('push' if beat_in_group == 2 else 'skank'))
        voicing = [CHORDS[chord][1] + 12, CHORDS[chord][2] + 12, CHORDS[chord][3] + 12]
        for i, beat in enumerate(strums[shape]):
            for j, p in enumerate(voicing):
                # a strummed chord is staggered, never a block, and the top note is the loudest
                # a skank is a chop: the backbeat chords are hit hard, the upstroke between them is a ghost,
                # and every second bar leans in (the phrase breathes instead of ticking)
                lean = 1.12 if b % 2 else 0.92
                acc = (1.15 if beat in (0.5, 2.5) else 0.62) + 0.08 * j + 0.05 * (i % 2)
                gtr.append(note(t + beat * BEAT + j * 0.02 * BEAT, 0.22 * BEAT, p, v(b, 0.5, acc * lean)))
    out.append({'name': 'guitar', 'instrument': 'highlife_guitar', 'role': 'chord', 'notes': gtr,
                'spatial': {'azimuth': -25.0, 'elevation': 4.0, 'distance': 3.0}})

    # 4. marimba: the arpeggio that keeps the groove moving, moving through the field. Four shapes, and
    # the last section drops to every second sixteenth so the field has room.
    mar = []
    for b in range(9, 25):
        t, chord = bar_time(b), chord_at(b)
        tones = [CHORDS[chord][0] + 12, CHORDS[chord][1] + 12, CHORDS[chord][2] + 12, CHORDS[chord][3] + 12]
        shape = (b // 2) % 4
        for step in range(8):
            if b >= 21 and step % 2 == 1:
                continue                                    # golden_hour thins out
            if shape == 0:
                idx = (step * 3) % 4                        # rising skip
            elif shape == 1:
                idx = (3 - step * 3) % 4                    # the same figure falling
            elif shape == 2:
                idx = 0 if step % 2 == 0 else (2 if step % 4 == 1 else 3)     # pedal, then the third
            else:
                idx = (step * 4) % 4 + (1 if step >= 4 else 0)                # broken chord over an octave
            p = tones[idx % 4] + (12 if (shape == 3 and step >= 4) else 0)
            # the mallet hits the first of each group, the rest are the run it leaves behind
            acc = (1.22 if step in (0, 4) else 0.7) + (0.06 if step % 3 == 2 else 0.0)
            mar.append(note(t + step * 0.5 * BEAT, 0.3 * BEAT, p, v(b, 0.44, acc)))
    out.append({'name': 'marimba', 'instrument': 'marimba', 'role': 'arp', 'notes': mar,
                'spatial': {'azimuth': -45.0, 'elevation': 10.0, 'distance': 3.5,
                            'trajectory': {'spatial_role': 'mover', 'doppler_strength': 0.6,
                                           'keyframes': [{'bar': 9, 'azimuth': -45, 'distance': 3.5},
                                                         {'bar': 16, 'azimuth': -80, 'distance': 3.2},
                                                         {'bar': 24, 'azimuth': -100, 'distance': 3.8}]}}})

    # 5. bansuri: the melody. Motif A rises, motif B answers, the chorus lifts it an octave.
    # A flute line is mostly conjunct: the intervals here are 2-3 semitones stepping through the raga,
    # and every phrase ends by step on the tonic rather than leaping away from a tension note.
    flu = []
    motif_a = [(0.0, 0.75, 1), (0.75, 0.25, 2), (1.0, 1.0, 3), (2.0, 0.5, 2), (2.5, 1.0, 1)]
    motif_b = [(0.0, 0.5, 3), (0.5, 0.5, 2), (1.0, 0.75, 1), (1.75, 0.25, 0), (2.25, 1.25, 0)]

    def phrase(bar, motif, octave=0, start_beat=0.0, level=0.62, ornament=False):
        t = bar_time(bar) + start_beat * BEAT
        if ornament:
            # a grace pair before the phrase: the flute's own attack, and two extra note lengths in the bar
            flu.append(note(t - 0.25 * BEAT, 0.2 * BEAT, SCALE[motif[0][2]] + 12 * octave - 2, v(bar, level * 0.7)))
            flu.append(note(t - 0.12 * BEAT, 0.1 * BEAT, SCALE[motif[0][2]] + 12 * octave - 1, v(bar, level * 0.8)))
        # the phrase swells into its middle and eases on the last note (Todd 1992), on top of the section level
        for k, (beat, dur, idx) in enumerate(motif):
            arch = 1.0 + (0.1 if 0 < k < len(motif) - 1 else 0.0) - (0.12 if k == len(motif) - 1 else 0.0)
            flu.append(note(t + beat * BEAT, dur * BEAT, SCALE[idx] + 12 * octave, v(bar, level, arch)))

    for b in (1, 5):
        phrase(b, motif_a, 0, 2.0, 0.55)
    for b in (9, 13):
        phrase(b, motif_a, 0, 0.0, 0.66, ornament=True)
    for b in (11, 15):
        phrase(b, motif_b, 0, 0.0, 0.64, ornament=True)
        phrase(b, motif_a, 0, 2.0, 0.6)
    for b in range(17, 25, 2):
        phrase(b, motif_b, 1, 0.0, 0.74, ornament=True)
        phrase(b + 1, motif_a, 1, 1.0, 0.7)
    for b in (25, 27):
        phrase(b, motif_a, 0, 0.0, 0.55)
    phrase(29, motif_b, 0, 0.0, 0.6)
    flu.append(note(bar_time(30), 2 * BAR, SCALE[0], v(30, 0.5)))   # A4 held to the end
    out.append({'name': 'bansuri', 'instrument': 'bansuri', 'role': 'melody', 'notes': flu,
                'spatial': {'azimuth': 8.0, 'elevation': 12.0, 'distance': 2.2,
                            'trajectory': {'spatial_role': 'mover', 'doppler_strength': 0.4,
                                           'keyframes': [{'bar': 1, 'azimuth': 8, 'distance': 2.4},
                                                         {'bar': 17, 'azimuth': -10, 'distance': 2.0},
                                                         {'bar': 24, 'azimuth': 14, 'distance': 2.3}]}}})

    # 6. sitar: the Indian answer. Sixteenths through the chorus, then a wide arc - and each four-bar
    # phrase closes on a held note, so the part has two lengths instead of one machine-gun value.
    sit = []
    for b in list(range(17, 25)) + list(range(29, 33)):
        t, chord = bar_time(b), chord_at(b)
        tones = [CHORDS[chord][0], CHORDS[chord][1], CHORDS[chord][2], CHORDS[chord][3]]
        # a sitar taan is not a metronome: the order changes every bar and the register jumps, so the line is not
        # predictable from the previous bar (the entropy row reads exactly that)
        orders = [(0, 1, 2, 3), (0, 2, 1, 3), (3, 1, 2, 0), (1, 3, 2, 0)]
        order = orders[b % len(orders)]
        if b == 20:                                  # a breath bar: one long note instead of the run
            sit.append(note(t, 3.5 * BEAT, tones[0], v(b, 0.42)))
            continue
        steps = 12 if (b % 4 == 0) else 16
        for step in range(steps):
            idx = order[step % 4]
            p = tones[idx] + (12 if (step // 4) % 2 else 0)
            if step % 7 == 6:
                p = tones[(idx + 2) % 4] + 12
            # a taan starts under the beat and climbs: the last group is the loudest, the sam the loudest of all
            climb = 0.72 + 0.55 * (step / max(steps - 1, 1))
            acc = climb * (1.15 if step % 4 == 0 else 1.0) * (1.2 if step in (0, steps - 1) else 1.0)
            sit.append(note(t + step * 0.25 * BEAT, 0.22 * BEAT, p, v(b, 0.34, acc)))
        if b % 4 == 0:                               # the phrase closes held: the arc the line was building
            sit.append(note(t + 3.0 * BEAT, 1.5 * BEAT, tones[0] + 12, v(b, 0.44)))
    out.append({'name': 'sitar', 'instrument': 'sitar', 'role': 'counter', 'notes': sit,
                'spatial': {'azimuth': 95.0, 'elevation': 0.0, 'distance': 3.0,
                            'trajectory': {'spatial_role': 'mover', 'doppler_strength': 0.8,
                                           'keyframes': [{'bar': 17, 'azimuth': 95, 'distance': 3.0},
                                                         {'bar': 21, 'azimuth': 108, 'distance': 2.6},
                                                         {'bar': 24, 'azimuth': 120, 'distance': 3.2}]}}})

    # 7. horns: the Afro brass stab that makes the chorus lift. A stab, a held answer and one long swell
    # closing the section - a brass section phrases, it does not fire one fixed length.
    hor = []
    for b in (17, 19, 21, 23):
        t, chord = bar_time(b), chord_at(b)
        cue = [(0.0, 0.35), (2.5, 0.75 if b in (19, 23) else 0.35)]
        if b == 23:                                  # the section closes on a two-beat swell
            cue = [(0.0, 0.5), (1.0, 2.0)]
        for k, (beat, dur) in enumerate(cue):
            for j, p in enumerate((CHORDS[chord][0], CHORDS[chord][1], CHORDS[chord][2])):
                # a brass section is voiced: the top trumpet leads, the bottom is softer, and the players are not a block
                # a stab is a hit and a held note is a build: 0.68 at the bottom of the section, 1.25 at the swell
                swell = 0.78 + 0.35 * (b - 17) / 6.0 + (0.12 if dur >= 0.75 else 0.0)
                acc = swell * (0.86 + 0.1 * j) + (0.1 if (beat, dur) == (0.0, 0.35) else 0.0)
                hor.append(note(t + beat * BEAT + j * 0.015 * BEAT, dur * BEAT, p + 12, v(b, 0.6, acc)))
    out.append({'name': 'horns', 'instrument': 'brass_section', 'role': 'counter', 'notes': hor,
                'spatial': {'azimuth': 55.0, 'elevation': 22.0, 'distance': 4.0}})

    # 8. kit: afrobeat kick (1, 2&, 3, 4), snare on 2 and 4, shaker-driven hats. The last bar of each
    # four is a fill, and the hats change shape between sections.
    kit = []
    for b in range(5, BARS + 1):
        t = bar_time(b)
        if b in (24,):                                # the drop into golden_hour: one bar of air
            continue
        kicks = (0, 6, 8, 10, 12) if b >= 25 else ((0, 6, 8, 12) if b % 4 else (0, 6, 8, 11, 12))
        if b % 4 == 0 and b < 24:                     # the fill bar: three extra kicks pulling into the next phrase
            kicks = (0, 3, 6, 8, 10, 11, 14)
        for step in kicks:
            kit.append(note(t + step * 0.25 * BEAT, 0.45 * BEAT, DRUM_KEYS['kick'],
                            v(b, 0.86, 1.0 - 0.06 * (step == 11))))
        snares = (4, 12) if b % 4 else (4, 12, 14)
        for step in snares:
            kit.append(note(t + step * 0.25 * BEAT, 0.45 * BEAT, DRUM_KEYS['snare'], v(b, 0.6)))
        # the shaker-hand of the kit: 16ths on a tambourine. A closed hat decays to silence before the next 16th and
        # the gate read that gap inside a sounding note as a dropout (20-25 ms, stem.dropout); the tambourine's ring
        # carries across the step, which is also the afrobeat hand this groove wants.
        hat = 'tambourine'
        for step in range(16):
            if b <= 8 and step % 2 == 1:
                continue                              # dawn: eighths only
            shape = 0.12 * (step / 16.0) ** 1.2 if b < 17 else 0.16 * ((step % 4) / 4.0) ** 0.8
            acc = 0.7 + 0.85 * shape + (0.08 if step % 4 == 0 else 0.0) + (0.05 if b % 4 == 3 and step >= 12 else 0.0)
            # a flam: the tambourine lands 12 ms after the snare instead of on it (percussion_flam reads the lock)
            off = 0.022 if step in snares else 0.0
            kit.append(note(t + (step * 0.25 + off) * BEAT, 0.25 * BEAT, DRUM_KEYS[hat], v(b, 0.86, acc)))
        # the open hat rings under the fill: at 0.4 it sat 0.41 below the kick on the same beat, which the
        # intent row reads as a sudden jump inside no time at all
        kit.append(note(t + 14 * 0.25 * BEAT, 0.7 * BEAT, DRUM_KEYS['hat_open'], v(b, 0.62)))
        if b in (9, 17, 25):
            kit.append(note(t, 0.5 * BEAT, DRUM_KEYS['crash'], v(b, 0.72)))
    out.append({'name': 'kit', 'instrument': 'kit', 'role': 'drum', 'notes': kit,
                'spatial': {'azimuth': 0.0, 'elevation': 0.0, 'distance': 5.0}})

    # 9. djembe: the West African hand layer. Eight stroke rotations, a fill every fourth bar and a
    # ghost-stroke pair, so no two bars of the hand layer are the same bar.
    dje = []
    kinds = ['conga_mute', 'conga_open', 'tom_mid', 'conga_open',
             'conga_mute', 'tom_high', 'conga_open', 'conga_mute']
    for b in range(5, BARS + 1):
        t = bar_time(b)
        if b == 24:
            continue
        for step in range(16):
            if b % 4 == 3 and step in (9, 10) :
                continue                              # the ghost pair leaves two holes before the fill
            key = kinds[(step * 3 + b * 5) % len(kinds)]
            acc = 0.5 + 0.2 * ((step / 16.0) ** 1.6) + (0.05 if step % 4 == 0 else -0.03)
            if b % 4 == 0 and step >= 12:             # the fill: every stroke louder as it climbs
                key = 'conga_open' if step % 2 == 0 else 'tom_high'
                acc = 0.55 + 0.09 * (step - 12)
            elif step in (7, 15):
                acc = 0.34                             # a quiet ghost stroke, not an accent
            dje.append(note(t + step * 0.25 * BEAT, 0.5 * BEAT, DRUM_KEYS[key], v(b, 0.5, acc)))
    out.append({'name': 'djembe', 'instrument': 'djembe', 'role': 'percussion', 'notes': dje,
                'spatial': {'azimuth': -110.0, 'elevation': 0.0, 'distance': 4.5}})

    # 10. tabla: the Indian hand layer, named world-drum keys (GM stand-ins, not a sampled tabla).
    # Eight theka variants and a tihai every eighth bar, with three stroke lengths (ge held, na, ti short).
    tab = []
    theka = [(0, 2, 6, 8, 10, 14), (0, 3, 6, 8, 11, 14), (0, 2, 7, 8, 10, 13), (0, 2, 6, 9, 10, 14),
             (0, 2, 5, 8, 10, 12), (0, 3, 7, 8, 11, 13), (0, 2, 6, 8, 9, 14), (0, 4, 6, 8, 10, 15)]
    for b in range(9, BARS + 1):
        t = bar_time(b)
        if b == 24:
            continue
        for step in theka[b % len(theka)]:
            if step in (0, 8):
                key, dur = 'tabla_na', 0.5
            elif step in (2, 10):
                key, dur = 'tabla_ge', 1.0          # the resonant stroke is held
            else:
                key, dur = 'tabla_ti', 0.25
            acc = 0.95 if step in (0, 8) else 0.72
            if b % 8 == 0 and step >= 12:            # tihai: three strokes and a rest, repeated into the cadence
                key, dur, acc = 'tabla_ti', 0.25, 0.86
            tab.append(note(t + step * 0.25 * BEAT, dur * BEAT, DRUM_KEYS[key], v(b, 0.46, acc)))
    out.append({'name': 'tabla', 'instrument': 'tabla', 'role': 'percussion', 'notes': tab,
                'spatial': {'azimuth': 60.0, 'elevation': 0.0, 'distance': 4.5}})

    # 11. shekere: the shaker that never stops once the groove starts - but it has four hands, and the
    # hand changes with the bar, so the 16ths are not one written bar thirty-two times.
    shek = []
    # each hand is a different set of played steps, not the same 16ths accented differently: the bar the
    # listener hears has to change, or the shaker is one written bar repeated thirty-two times
    hands = {
        'straight': tuple(range(16)),
        'triplet': (0, 3, 4, 7, 8, 11, 12, 15),
        'offbeat': (4, 12, 0, 8),
        'clave': (0, 3, 6, 10, 12),
    }
    for b in range(1, BARS + 1):
        t = bar_time(b)
        if b == 24:
            continue                              # the drop into golden_hour
        if b <= 8:
            for step in range(0, 16, 2):          # dawn: the shaker alone, in eighths
                shek.append(note(t + step * 0.25 * BEAT, 0.5 * BEAT, DRUM_KEYS['shaker'],
                                 v(b, 0.36, 1.25 if step % 8 == 0 else 0.72)))
            continue
        hand = list(hands.values())[(b - 1) % 4]
        for step in hand:
            acc = (1.25 if step in (0, 4, 8, 12) else 0.66) + (0.08 if step % 8 == 4 else 0.0)
            if b % 4 == 0 and step in (7, 15):
                acc += 0.1                        # phrase-end accent
            if (b - 1) % 8 in (3, 7) and step in (5, 13):
                acc -= 0.08                       # a ghost hand in the second half of each eight
            shek.append(note(t + step * 0.25 * BEAT, 0.5 * BEAT, DRUM_KEYS['shaker'], v(b, 0.34, acc)))
    out.append({'name': 'shekere', 'instrument': 'shekere', 'role': 'percussion', 'notes': shek,
                'spatial': {'azimuth': 90.0, 'elevation': 4.0, 'distance': 4.0}})

    # 12. canopy: the rainforest bed, one long event, faded at both ends
    canopy = [note(0.0, 70.0, 60, 0.5)]
    out.append({'name': 'canopy', 'instrument': 'env:amazon_rainforest', 'role': 'environment',
                'notes': canopy,
                'spatial': {'azimuth': -40.0, 'elevation': 40.0, 'kind': 'spot'},
                'fade_in_s': 4.0, 'fade_out_s': 5.0})
    return out


def score():
    sections = []
    for name, b0, b1, energy in SECTIONS:
        sections.append({'name': name, 'start_bar': b0, 'end_bar': b1, 'energy': energy,
                         'start_s': round(sec(bar_time(b0)), 4), 'end_s': round(sec(bar_time(b1) + BAR), 4)})
    # one continuous level curve in beats (0..1), peaking on the chorus and easing for golden_hour
    dynamics = [[0.0, 0.3], [round(bar_time(9), 3), 0.5], [round(bar_time(17), 3), 0.78],
                [round(bar_time(24) + BAR, 3), 0.95], [round(bar_time(30), 3), 0.62],
                [round(TOTAL - 0.1, 3), 0.5]]
    return {
        'title': 'Indo-Afro Sunrise',
        'bpm': BPM,
        'ts': [4, 4],
        'seed': 20261125,
        'humanize': 'natural',
        'key': 'A',
        'mode': 'mixolydian',
        'dynamics': dynamics,
        'space': 'indo_afro_sunrise_room',
        'mix_preset': 'indo_afro_sunrise_mix',
        'output_targets': ['stereo', 'immersive_7_1'],
        'master': {'lufs': -14.0, 'true_peak': -1.5, 'tone': 'warm', 'fade_out': 2.5},
        'piece_type': 'indo_afro_sunrise',
        'focus': 'melody',
        'intent': {'emotions': ['joyful', 'energetic'], 'registers': ['natural'],
                   'scenes': ['arrival', 'establish'], 'tensions': [],
                   'avoid': []},
        'mix_intent': {'hero': 'bansuri', 'support': ['marimba', 'sitar', 'guitar', 'horns'],
                       'sits_under': ['canopy'],
                       'must_hear': ['the tanpura alone in the first four bars',
                                     'the shekere before the kit enters at 17.1 s',
                                     'the brass stab at 34.3 s',
                                     'the sitar crossing behind at 42 s'],
                       'leave_free_hz': [700, 2600],
                       'executed_by': 'carried on the score; the mix preset reads it with lead_carve.from_intent'},
        'plan': {'sections': sections, 'ending': {'fade_out': 2.5}},
        'tracks': tracks(),
        'mix': {'tracks': {}},
    }


def main():
    path = os.path.join(PROJECT, 'scores', 'indo_afro_sunrise_score.json')
    data = score()
    with open(path, 'w') as fh:
        json.dump(data, fh, indent=1)
    total = sum(len(t['notes']) for t in data['tracks'])
    print(f'wrote {path}: {len(data["tracks"])} tracks, {total} notes, {TOTAL:.0f} beats = {sec(TOTAL):.2f} s, '
          f'{len(data["plan"]["sections"])} sections')


if __name__ == '__main__':
    main()
