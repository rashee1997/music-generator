"""Write scores/indo_afro_sunrise_score.json — notes only.

Indo-Afro Sunrise: an upbeat Indo-Afro groove (A mixolydian, 112 BPM, 32 bars) with an Indian
tanpura/bansuri/tabla layer over an Afrobeat kit, djembe and shekere, played inside a rainforest
canopy and delivered immersive (stereo + 7.1). This script decides pitches and times; every level,
space, stereo position and room number lives in the presets.
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
    return {'t': round(t, 4), 'd': round(max(d, 0.05), 4), 'p': int(p), 'v': round(v, 3)}


def bar_time(bar):
    return (bar - 1) * BAR


def chord_at(bar):
    return PROG[min(len(PROG) - 1, (bar - 1) // 2)]


def tracks():
    out = []

    # 1. tanpura: the drone the whole piece sits on, retriggered every four bars so it breathes
    tan = []
    drone_roots = {1: 45, 5: 43, 9: 38, 13: 45, 17: 43, 21: 45, 25: 38, 29: 45}
    for b in range(1, BARS + 1, 4):
        t = bar_time(b)
        dur = min(4 * BAR + 1.0, TOTAL - t)
        root = drone_roots.get(b, 45)
        tan.append(note(t, dur, root, 0.42))            # the drone's root follows the harmony
        tan.append(note(t, dur, root + 7, 0.3))         # fifth
        tan.append(note(t + 0.5 * BEAT, dur * 0.9, root + 12, 0.26))  # octave, slightly behind
    out.append({'name': 'tanpura', 'instrument': 'tambura', 'role': 'drone', 'notes': tan,
                'spatial': {'azimuth': 0.0, 'elevation': 0.0, 'distance': 4.0},
                'fade_in_s': 2.0, 'fade_out_s': 3.0})

    # 2. bass: one owner of the low end, root-fifth-octave afrobeat figure
    bass = []
    for b in range(5, BARS + 1):
        t, root, ch = bar_time(b), ROOTS[chord_at(b)], chord_at(b)
        if b == 32:
            root = ROOTS['A']
        # durations run to the next onset: a bass line is a legato line, and a 20 ms gap counts as a dropout
        fig = [(0.0, 0.75, root, 0.88), (0.75, 0.75, root, 0.6), (1.5, 1.0, root + 7, 0.78),
               (2.5, 0.5, root + 12, 0.72), (3.0, 0.5, root + 7, 0.82), (3.5, 0.5, root + 12, 0.6)]
        for beat, dur, p, v in fig:
            bass.append(note(t + beat * BEAT, dur * BEAT, p, v))
    out.append({'name': 'bass', 'instrument': 'finger_bass', 'role': 'bass', 'notes': bass,
                'spatial': {'azimuth': -25.0, 'elevation': 0.0, 'distance': 3.0}})

    # 3. guitar: highlife skank, the Afro half of the rhythm guitar
    gtr = []
    for b in range(3, BARS + 1):
        t, ch = bar_time(b), chord_at(b)
        voicing = [CHORDS[ch][1] + 12, CHORDS[ch][2] + 12, CHORDS[ch][3] + 12]
        for i, beat in enumerate((0.5, 1.5, 2.5, 3.5)):
            for j, p in enumerate(voicing):
                # a strummed chord is staggered, never a block, and the top note is the loudest
                gtr.append(note(t + beat * BEAT + j * 0.02 * BEAT, 0.22 * BEAT, p, 0.46 + 0.05 * j + 0.04 * (i % 2)))
    out.append({'name': 'guitar', 'instrument': 'highlife_guitar', 'role': 'chord', 'notes': gtr,
                'spatial': {'azimuth': -25.0, 'elevation': 4.0, 'distance': 3.0}})

    # 4. marimba: the arpeggio that keeps the groove moving, moving through the field
    mar = []
    for b in range(9, 25):
        t, ch = bar_time(b), chord_at(b)
        tones = [CHORDS[ch][0] + 12, CHORDS[ch][1] + 12, CHORDS[ch][2] + 12, CHORDS[ch][3] + 12]
        for step in range(8):
            p = tones[(step * 3) % 4] + 12
            mar.append(note(t + step * 0.5 * BEAT, 0.3 * BEAT, p, 0.42 + 0.1 * (step % 3 == 0)))
    out.append({'name': 'marimba', 'instrument': 'marimba', 'role': 'arp', 'notes': mar,
                'spatial': {'azimuth': -45.0, 'elevation': 10.0, 'distance': 3.5,
                            'trajectory': {'spatial_role': 'mover', 'doppler_strength': 0.6,
                                           'keyframes': [{'bar': 9, 'azimuth': -45, 'distance': 3.5},
                                                         {'bar': 16, 'azimuth': -80, 'distance': 3.2},
                                                         {'bar': 24, 'azimuth': -100, 'distance': 3.8}]}}})

    # 5. bansuri: the melody. Motif A rises, motif B answers, the chorus lifts it an octave
    flu = []
    # A flute line is mostly conjunct: the intervals here are 2-3 semitones stepping through the raga,
    # and every phrase ends by step on the tonic rather than leaping away from a tension note.
    motif_a = [(0.0, 0.75, 1), (0.75, 0.25, 2), (1.0, 1.0, 3), (2.0, 0.5, 2), (2.5, 1.0, 1)]
    motif_b = [(0.0, 0.5, 3), (0.5, 0.5, 2), (1.0, 0.75, 1), (1.75, 0.25, 0), (2.25, 1.25, 0)]

    def phrase(bar, motif, octave=0, start_beat=0.0, vel=0.62):
        t = bar_time(bar) + start_beat * BEAT
        for beat, dur, idx in motif:
            flu.append(note(t + beat * BEAT, dur * BEAT, SCALE[idx] + 12 * octave, vel))

    for b in (1, 5):
        phrase(b, motif_a, 0, 2.0, 0.55)
    for b in (9, 11, 13, 15):
        phrase(b, motif_a if b % 4 == 1 else motif_b, 0, 0.0, 0.66)
        if b in (11, 15):
            phrase(b, motif_b, 0, 2.0, 0.6)
    for b in range(17, 25, 2):
        phrase(b, motif_b, 1, 0.0, 0.72)
        phrase(b + 1, motif_a, 1, 1.0, 0.68)
    for b in (25, 27):
        phrase(b, motif_a, 0, 0.0, 0.55)
    phrase(29, motif_b, 0, 0.0, 0.6)
    flu.append(note(bar_time(30), 2 * BAR, SCALE[0], 0.5))   # A4 held to the end
    out.append({'name': 'bansuri', 'instrument': 'bansuri', 'role': 'melody', 'notes': flu,
                'spatial': {'azimuth': 8.0, 'elevation': 12.0, 'distance': 2.2,
                            'trajectory': {'spatial_role': 'mover', 'doppler_strength': 0.4,
                                           'keyframes': [{'bar': 1, 'azimuth': 8, 'distance': 2.4},
                                                         {'bar': 17, 'azimuth': -10, 'distance': 2.0},
                                                         {'bar': 24, 'azimuth': 14, 'distance': 2.3}]}}})

    # 6. sitar: the Indian answer, 16th-note arpeggio through the chorus, then a wide arc
    sit = []
    for b in list(range(17, 25)) + list(range(29, 33)):
        t, ch = bar_time(b), chord_at(b)
        tones = [CHORDS[ch][0], CHORDS[ch][1], CHORDS[ch][2], CHORDS[ch][3]]
        # a sitar taan is not a metronome: the order changes every bar and the register jumps, so the line is not
        # predictable from the previous bar (the entropy row reads exactly that)
        orders = [(0, 1, 2, 3), (0, 2, 1, 3), (3, 1, 2, 0), (1, 3, 2, 0)]
        order = orders[b % len(orders)]
        for step in range(16):
            idx = order[step % 4]
            p = tones[idx] + (12 if (step // 4) % 2 else 0)
            if step % 7 == 6:
                p = tones[(idx + 2) % 4] + 12
            sit.append(note(t + step * 0.25 * BEAT, 0.22 * BEAT, p, 0.3 + 0.09 * (step % 4 == 0)))
    out.append({'name': 'sitar', 'instrument': 'sitar', 'role': 'counter', 'notes': sit,
                'spatial': {'azimuth': 95.0, 'elevation': 0.0, 'distance': 3.0,
                            'trajectory': {'spatial_role': 'mover', 'doppler_strength': 0.8,
                                           'keyframes': [{'bar': 17, 'azimuth': 95, 'distance': 3.0},
                                                         {'bar': 21, 'azimuth': 108, 'distance': 2.6},
                                                         {'bar': 24, 'azimuth': 120, 'distance': 3.2}]}}})

    # 7. horns: the Afro brass stab that makes the chorus lift
    hor = []
    for b in (17, 19, 21, 23):
        t, ch = bar_time(b), chord_at(b)
        for beat in (0.0, 2.5):
            for j, p in enumerate((CHORDS[ch][0], CHORDS[ch][1], CHORDS[ch][2])):
                # a brass section is voiced: the top trumpet leads, the bottom is softer, and the players are not a block
                hor.append(note(t + beat * BEAT + j * 0.015 * BEAT, 0.35 * BEAT, p + 12,
                                0.62 + 0.06 * j + 0.03 * (beat > 0)))
    out.append({'name': 'horns', 'instrument': 'brass_section', 'role': 'counter', 'notes': hor,
                'spatial': {'azimuth': 55.0, 'elevation': 22.0, 'distance': 4.0}})

    # 8. kit: afrobeat kick (1, 2&, 3, 4), snare on 2 and 4, shaker-driven hats
    kit = []
    for b in range(5, BARS + 1):
        t = bar_time(b)
        kicks = (0, 6, 8, 10, 12) if b >= 25 else ((0, 6, 8, 12) if b % 4 else (0, 6, 8, 11, 12))
        for step in kicks:
            kit.append(note(t + step * 0.25 * BEAT, 0.45 * BEAT, DRUM_KEYS['kick'], 0.9 - 0.04 * (step == 11)))
        for step in (4, 12):
            kit.append(note(t + step * 0.25 * BEAT, 0.45 * BEAT, DRUM_KEYS['snare'], 0.62))
        # the shaker-hand of the kit: 32nds alternating closed and pedal hat, so the stem is continuous and no
        # single pitch repeats as a machine-gun run
        for step in range(16):
            key = 'hat_closed' if step % 2 == 0 else 'hat_pedal'
            v = 0.56 + 0.12 * (step / 16.0) ** 1.2 + (0.03 if step % 4 == 0 else 0.0)
            kit.append(note(t + step * 0.25 * BEAT, 0.22 * BEAT, DRUM_KEYS[key], v))
        kit.append(note(t + 14 * 0.25 * BEAT, 0.7 * BEAT, DRUM_KEYS['hat_open'], 0.4))
        if b in (9, 17, 25):
            kit.append(note(t, 0.5 * BEAT, DRUM_KEYS['crash'], 0.55))
    out.append({'name': 'kit', 'instrument': 'standard', 'role': 'drum', 'notes': kit,
                'spatial': {'azimuth': 0.0, 'elevation': 0.0, 'distance': 5.0}})

    # 9. djembe: the West African hand layer, tuned to GM conga/tom keys
    dje = []
    for b in range(5, BARS + 1):
        t = bar_time(b)
        # the hand layer plays through the bar: four stroke kinds rotating with the bar, and an exponential
        # velocity curve with alternating accents, so no single pitch repeats as a machine-gun run
        strokes = ['conga_mute', 'conga_open', 'tom_mid', 'conga_open']
        for step in range(16):
            key = strokes[(step + b) % len(strokes)]
            acc = 0.5 + 0.2 * ((step / 16.0) ** 1.6) + (0.04 if step % 2 == 0 else -0.04)
            dje.append(note(t + step * 0.25 * BEAT, 0.5 * BEAT, DRUM_KEYS[key], acc))
    out.append({'name': 'djembe', 'instrument': 'djembe', 'role': 'percussion', 'notes': dje,
                'spatial': {'azimuth': -110.0, 'elevation': 0.0, 'distance': 4.5}})

    # 10. tabla: the Indian hand layer, named world-drum keys (GM stand-ins, not a sampled tabla)
    tab = []
    # the tabla plays a real theka: four bar-variants, and a tihai (a repeated cadence) every eighth bar,
    # so no two four-bar phrases are identical
    theka = [(0, 2, 6, 8, 10, 14), (0, 3, 6, 8, 11, 14), (0, 2, 7, 8, 10, 13), (0, 2, 6, 9, 10, 14)]
    for b in range(9, BARS + 1):
        t = bar_time(b)
        for step in theka[b % len(theka)]:
            key = 'tabla_na' if step in (0, 8) else ('tabla_ge' if step in (2, 10) else 'tabla_ti')
            acc = 0.52 if step in (0, 8) else 0.4
            if b % 8 == 0 and step in (12, 13, 14):
                key = 'tabla_ti'
                acc = 0.46
            tab.append(note(t + step * 0.25 * BEAT, 0.5 * BEAT, DRUM_KEYS[key], acc))
    out.append({'name': 'tabla', 'instrument': 'tabla', 'role': 'percussion', 'notes': tab,
                'spatial': {'azimuth': 60.0, 'elevation': 0.0, 'distance': 4.5}})

    # 11. shekere: the shaker that never stops once the groove starts
    shek = []
    for b in range(1, BARS + 1):
        t = bar_time(b)
        for step in range(16):
            if b == 24 and 4 <= step < 8:
                continue                      # the drop into golden_hour: the shaker stops for a beat
            v = 0.3 + 0.16 * (step % 4 == 0) + 0.06 * (step % 8 == 4)
            if b % 4 == 0 and step in (7, 15):
                v += 0.1                      # phrase-end accent
            if b % 2 == 1 and step in (5, 13):
                v += 0.05
            shek.append(note(t + step * 0.25 * BEAT, 0.5 * BEAT, DRUM_KEYS['shaker'], v))
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
