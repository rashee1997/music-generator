#!/usr/bin/env python3
"""make_direction.py - writes direction/direction_night_pursuit_cinematic.json: the cue as decisions that can be checked.

Every time in the sheet comes from timeline.py (the bars and the tempo map), so a section that moves in the score moves here.
Only intent lives in the sheet; the numbers that carry it (azimuths, keyframes, room geometry, sweeps, speeds) are in presets/ and cars.py.
"""
import json
import os

import cars
import timeline as T
from staging import STAGE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'direction', 'direction_night_pursuit_cinematic.json')
SPACE = 'np_street_canyon'
tm = T.tempo_map()
secs = T.sections_with_seconds(tm)
EV = T.events(tm)
DUR = round(EV['end'], 1)
S = lambda name, b=0.0: round(T.seconds(T.start(name), b, tm), 2)       # noqa: E731


def at(bar, beat=0.0):
    return round(T.seconds(bar, beat, tm), 2)


HITS = [
    dict(t=EV['spot'], kind='motion', sync='soft', sound='a cruiser at the kerb sees the speeding: its lights come on and its siren starts',
         why='the moment the race becomes a chase; a soft sync, so a beat either way does not matter'),
    dict(t=S('the_chase'), kind='musical', sync='soft', sound='the chase proper: the second cruiser joins and the camera swings in behind the cars',
         why='a camera cut and a taiko hit; the hook changes its answer'),
    dict(t=round(EV['crash'], 2), kind='musical', sync='hard', sound='the Mustang hits the barrier at the tunnel mouth: one impact, metal and glass',
         why='the first car is out; weight and one real hit; the strings keep sounding, so it is a hard accent and not a cut'),
    dict(t=S('the_tunnel'), kind='motion', sync='soft', sound='the cars enter the tunnel: the room closes and the engines and sirens echo',
         why='the place changes; the field, not the music, says it'),
    dict(t=S('the_helicopter'), kind='musical', sync='soft', sound='the helicopter arrives overhead: the choir opens and the music goes distant',
         why='a camera cut to the air; the height pair carries it'),
    dict(t=S('the_bumps'), kind='motion', sync='soft', sound='the flyover deck: a thump at every expansion joint at speed',
         why='a camera cut inside the car; the joints are a rhythm of their own'),
    dict(t=round(EV['jump'], 2), kind='motion', sync='soft', sound='the Ferrari leaves the edge of the flyover: time slows',
         why='the one slow-motion moment; the tempo falls and the engine and tyres go down in pitch'),
    dict(t=round(EV['land'], 2), kind='musical', sync='hard', sound='the landing: a deep thump, a metal knock, a sub drop and the tempo snaps back',
         why='the release of the slow motion; the strings keep sounding, so it is a hard accent and not a cut'),
    dict(t=round(EV['lost'], 2), kind='motion', sync='soft', sound='the Lamborghini loses the road after the landing and spins off',
         why='the second car is out'),
    dict(t=round(EV['evade'], 2), kind='musical', sync='soft', sound='the cruisers stop: the Ferrari is clear and the sirens fall behind',
         why='the chase is over: the cue releases and does not resolve fully'),
]

SECTION_TEXT = {
    'the_race': ('Inside the Ferrari at speed on a wet avenue at night: a street race, four cars, the Porsche holding one steady speed at the side.',
                 'it starts at once: the pulse and the horns state the hook over a low pulse, the taiko on the first beat; no slow opening'),
    'spotted': ('The camera on the kerb: the cars pass at different speeds with the Doppler swing; a cruiser sees the speeding and its siren starts.',
                'the pulse rolls on; the hook is answered by the clarinet; the music widens and brightens for the outside camera'),
    'the_chase': ('Beside and behind the pack: corners, squeals, shifts and pops on the lift; the cruisers close in; the Mustang runs out of road at the tunnel mouth.',
                  'full strings and brass, the snare backbeat and a fill each phrase, the sub pulse; the hook climbs a semitone; the crash is a hit on the last bar'),
    'the_tunnel': ('A tunnel: the engines and the sirens echo in concrete; the Mustang is gone.',
                   'the pulse and the low brass only for six bars, then tremolo strings and a rising line; the room does the rest'),
    'the_helicopter': ('A police helicopter joins from above; the cars are small and far below.',
                       'the choir opens, the music goes distant and filtered with a pulse; the height speakers carry the choir and the rotor'),
    'the_bumps': ('Inside the Ferrari on a flyover deck: a thump at every joint at 150 km per hour.',
                  'the pulse locks to the joints; the horns and trombones play the hook together'),
    'the_flyover': ('The edge: the Ferrari jumps in slow motion and lands; the Lamborghini loses the road.',
                    'a collapse to a heartbeat and a pedal in the slow motion; a drop on the landing; the solo violin carries the hook an octave up'),
    'the_escape': ('Evaded: the cruisers stop, the Ferrari runs on into the dark and the engine falls away; drips from the fronts.',
                   'the pulse thins and slows, the hook is left on a single note and the cue ends open'),
}

ROLE_CUES = {
    'the_race': dict(arousal='high', mode_register='C minor, the pulse low and the horns mid', tempo_trend='steady, 132 BPM', dynamics='f from the first bar',
                     articulation='staccato sixteens in the piano, marcato horns', timbre='close and dry, the cabin'),
    'spotted': dict(arousal='high', mode_register='C minor with a Db neighbour', tempo_trend='136 BPM', dynamics='f, widening',
                    articulation='staccato eighths, the clarinet answers', timbre='wider and brighter, the street'),
    'the_chase': dict(arousal='high', mode_register='C minor, then Db minor after the crash', tempo_trend='142 BPM, accelerating', dynamics='ff, accents on the 3+3+2 cell',
                      articulation='sixteenths, staccato, marcato, fills each phrase', timbre='brighter as it gets louder'),
    'the_tunnel': dict(arousal='high', mode_register='Db minor, tritones against the bass', tempo_trend='146 BPM', dynamics='f, thinning then breaking open',
                       articulation='tremolo strings, long low brass', timbre='dense, a long tail from the room'),
    'the_helicopter': dict(arousal='high', mode_register='D minor, a choir above', tempo_trend='148 BPM', dynamics='ff, distant and filtered',
                           articulation='a pulse and long choir notes', timbre='open air, the top rolled off by distance'),
    'the_bumps': dict(arousal='high', mode_register='Eb minor, rising line', tempo_trend='150 BPM', dynamics='ff held',
                      articulation='the hook in horns and trombones together', timbre='open and hard, the air up'),
    'the_flyover': dict(arousal='high', mode_register='E minor, solo violin high', tempo_trend='152 BPM, a fall to 72 and a snap to 156', dynamics='ff, a collapse to pp in the slow motion, then a drop',
                        articulation='the pulse thins to single notes, then returns', timbre='muffled in the slow motion, bright at the landing'),
    'the_escape': dict(arousal='mid', mode_register='C with a Gb above it, unresolved', tempo_trend='124 BPM falling to 92', dynamics='mp falling to pp',
                       articulation='a heartbeat and a held harmonic', timbre='thin, cold, wet'),
}

CAR_LINE = ', '.join(f'{cars.CARS[c]["label"]}' for c in cars.CARS)

sheet = dict(
    title='Night Pursuit Cinematic',
    project='A cinematic street race and car chase through a wet New York night after the rain: four cars, the police, a tunnel, a flyover and an escape, written as a listening piece for a ten-channel 7.1.2 system',
    version=1,
    medium='film',
    brief='A street race that the police see; four cars (a Mustang, a Ferrari, a Lamborghini and a Porsche) at different speeds up to 150 km/h, one of them at one speed all the way; '
          'streets, a tunnel, cuts, bumps and a flyover edge; evaded at the end. The road is wet after the rain, nothing is falling, no wipers. The camera changes: inside the car, '
          'at the kerb, beside the cars and from a helicopter. Music in front, effects and fx behind it; a film mix; ten channels.',
    audience='a listener on a 7.1.2 system or headphones who came for the chase',
    purpose=f'a {DUR:.0f}-second cue that tells a whole chase: a street race, a spotting, a chase, a tunnel, a helicopter, a flyover, a jump and an escape',
    point_of_view='the camera: inside the Ferrari in the race and on the deck, on the kerb at the pass, behind the pack in the chase, in the air over the city for the helicopter',
    job=['start in motion with no slow opening and keep the listener in the car from the first bar',
         'tell the chase in sound: where each car is, who is faster, who drops out and who gets away',
         'change the camera and let the room, the music and the sound level change with it',
         'keep the music in front and the effects a supporting layer that comes forward only at a hit'],
    story=f'Four cars race on a wet avenue ({CAR_LINE}); a cruiser at the kerb sees the speeding and the chase begins. The Mustang runs out of road at the tunnel mouth. '
          'A helicopter joins. On the flyover the Ferrari jumps the edge in slow motion and lands; the Lamborghini loses the road. The cruisers stop and the Ferrari is evaded.',
    duration_s=DUR,
    in_point_s=0.0,
    out_point_s=DUR,
    ending='tail_out',
    feel=['tense', 'relentless', 'cold'],
    avoid_feel=['playful', 'calm', 'triumphant'],
    sections=[dict(name=s['name'], start_s=s['start_s'], end_s=s['end_s'], energy=s['energy'], role=s['role'],
                   action=SECTION_TEXT[s['name']][0], music=SECTION_TEXT[s['name']][1]) for s in secs],
    motifs=[dict(name='the_tick', first_at_s=at(1), shape='C, Db, C, then a leap up a tritone to Gb and a step down to F, Eb, Db: long, short, short, long, long',
                 returns='stated at once by the horns; whispered by the clarinet at the kerb; a semitone up and doubled after the crash; played by the choir above the helicopter; '
                         'by horns and trombones together on the deck; an octave up on the solo violin over the flyover; left on a single note at the end'),
            dict(name='the_siren_figure', first_at_s=round(EV['spot'], 2), shape='a rising and falling sweep between 600 and 1400 Hz, a minor ninth from the key',
                 returns='the second cruiser has a different, faster sweep so the two never share a pitch; both stop when the chase is lost')],
    instruments=sorted(STAGE) if False else [n for n in STAGE],
    avoid_sounds=['bell', 'harp', 'flute', 'guitar', 'rain', 'wipers'],
    pulse='steady',
    tempo_bpm=[72, 156],
    key='C',
    mode='minor',
    energy=0.9,
    space=SPACE,
    hits_at=[h['t'] for h in HITS],
    hits=HITS,
    mix_intent=dict(hero='pursuit_horns', support=['pursuit_celli', 'pursuit_trombones', 'pursuit_timpani', 'pursuit_piano', 'pursuit_choir'],
                    sits_under=['np_car_ferrari', 'np_car_lamborghini', 'np_car_mustang', 'np_car_porsche', 'np_siren_wail', 'np_siren_second', 'np_helicopter', 'np_city_far'],
                    must_hear=[f'the hook on the horns in the first 3 s', f'a pass at the kerb at {S("spotted", 8):.0f} s',
                               f'a siren by {EV["spot"]:.0f} s', f'the crash at {EV["crash"]:.0f} s', f'the helicopter at {S("the_helicopter"):.0f} s',
                               f'the landing at {EV["land"]:.0f} s'],
                    leave_free_hz=[]),
    loudness_lufs=-16.0,
    true_peak_max=-1.5,
    delivery=dict(format='wav', sample_rate=48000, bit_depth=24, stage='cinema', output_targets=['stereo', 'immersive_7_1_2'],
                  played_on='a 7.1.2 system of ten speakers (the fifth-order field decoded once), and headphones through the stereo master'),
    references=['a relentless low-string and piano pulse with taiko at the camera cuts, the engines and sirens a layer under it, and a hard-edged flyover at the end',
                'the camera as the listener: the room changes at every cut, the music stays in front'],
    spatial_staging={n: dict(azimuth=a, elevation=e, distance=r, space=SPACE) for n, (a, e, r) in STAGE.items()},
    immersive=dict(
        enabled=True,
        why='the camera changes: the field carries where the listener is. Inside the Ferrari the engine is behind and the road below; at the kerb the cars pass left to right; '
            'in the tunnel the room closes; the helicopter, the choir and the high strings are on the height pair',
        engine='hoa_bus',
        anchors=['pursuit_piano_low', 'pursuit_basses', 'pursuit_tuba', 'pursuit_bass_drum', 'pursuit_timpani', 'pursuit_taiko', 'np_bumps'],
        movers=[dict(part='np_car_ferrari', why='the hero car: inside, then passing the kerb, then ahead', path='behind the listener inside, a pass at the kerb, ahead in the chase, far in the air shot'),
                dict(part='np_car_lamborghini', why='the second car pulls ahead and to the left', path='left of the Ferrari in the race and the chase, spins off after the landing'),
                dict(part='np_car_mustang', why='the third car runs on the right and is the first to go', path='right of the pack, ends at the tunnel mouth with the crash'),
                dict(part='np_car_porsche', why='the car at one speed: it is left behind as the others pull away', path='behind the listener, falling further behind through the cue'),
                dict(part='np_siren_wail', why='the first cruiser closes in behind', path='far at the kerb, behind the pack from the chase, stops at the escape'),
                dict(part='np_siren_second', why='the second cruiser joins on the right', path='enters in the chase and crosses behind in the tunnel'),
                dict(part='np_helicopter', why='the helicopter is overhead and crosses the room', path='far and high, over the listener in the air shot, still above on the flyover')],
        height={'np_helicopter': 55, 'pursuit_choir': 60, 'pursuit_solo_violin': 45, 'pursuit_violins_tremolo': 30, 'pursuit_bass_clarinet': 30},
        room_changes=[dict(at_section='the_race', why='inside the car: a very small, dry cabin', transition_s=0.5),
                      dict(at_section='spotted', why='the kerb: the street canyon between two façades, wet asphalt, open sky', transition_s=1.0),
                      dict(at_section='the_tunnel', why='a tunnel: concrete above and on both sides, a long close tail', transition_s=6.0),
                      dict(at_section='the_helicopter', why='open air high over the city: a very large room, little reflection, air absorption', transition_s=4.0),
                      dict(at_section='the_bumps', why='back inside the car on the deck', transition_s=3.0),
                      dict(at_section='the_flyover', why='the steel deck outside, open sky', transition_s=3.0),
                      dict(at_section='the_escape', why='the street again, empty and wet', transition_s=4.0)],
        must_hear=[f'the pass at the kerb near {S("spotted", 8):.0f} s', f'the helicopter on the height pair from {S("the_helicopter"):.0f} s',
                   f'the room closing at {S("the_tunnel"):.0f} s', f'the landing at {EV["land"]:.0f} s'],
        deliverables=['stereo', 'immersive_7_1_2'],
        notes='the sheet records intent; the presets execute it. The bus is fifth order (36 channels) decoded once to the ten speakers of 7.1.2. Keyframes, room geometry and '
              'materials are in presets/spaces and presets/sfx; bass and drums are on the horizontal plane (no pinna cue at low frequency).'),
    expression=dict(
        sonic_picture='The first ten seconds: the hook on the horns over a driving low pulse, a big V8 engine behind and the road hissing under the car, a Mustang alongside on the right; '
                      'the middle: cars passing the kerb with the Doppler swing, a helicopter overhead with the choir above it; the last note: a single high harmonic over a Gb, the engine falling away, drips.',
        performer='The piano plays the pulse hard and a little ahead of the beat; the celli dig into the first beat of every bar; the horns enter late on each statement and lean on the leap; '
                  'the taiko is struck on the camera cuts; the snare fill tightens at each phrase end; the strings are sections of six and the brass sections of four; the solo violin is a little exposed.',
        producer_moves='The tempo climbs from 132 to 156 BPM with one slow-motion jump that snaps back; a drop and a sub hit on the landing; the room changes at every cut; '
                       'the effects sit a layer under the music and come forward on the crash and the landing; a risers-free cut at each camera.',
        anti_generic='The generic version is a drone, a riser and a drum loop with a car sound laid on top; this one has four cars with their own engines and speeds, a camera that changes the room, '
                     'and a hook that answers differently at every cut.',
        cues=[dict(section=s['name'], **ROLE_CUES[s['name']]) for s in secs],
        theme=dict(contour='a semitone step and back, then a leap up a tritone and a step down by steps',
                   interval_character='mostly a minor second, with one leap of a tritone',
                   rhythm_cell='long, short, short, long, long',
                   why_memorable='the leap of a tritone lands on the weak beat every time and is answered by a different tail',
                   variation_plan='stated by the horns, whispered by the clarinet, a semitone up and doubled after the crash, on the choir over the helicopter, horns and trombones together on the deck, '
                                  'an octave up on the solo violin over the flyover, a single note at the end')),
    focus='melody',
    intent=dict(emotions=['tense', 'dark_epic'], registers=['cinematic', 'hybrid'], scenes=['establish', 'build', 'chase', 'dread'],
                tensions=['ostinato', 'pedal', 'tritone', 'cluster', 'rising_line', 'silence_before', 'unresolved_dominant'],
                avoid=['joyful', 'playful']),
    piece_type='night_pursuit_cinematic',
    gate_reason='a build-hit-release cue with a short motif, a pulse that never stops and one slow-motion jump: the cinematic profile, started strict, with a project profile of its own',
    video=dict(enabled=False, source=None, fps=None, cuts=[], cut_source=None, cut_sync=dict(early_ms=45, late_ms=125),
               dialogue=dict(present=False, duck_db=-9.0, snr_min_db=15.0), master_profile=None, deliverable=None, preset='default',
               notes='music-only piece: leave enabled false.'),
    notes='Sound effects and ambience were asked for in the brief: four cars, two sirens, a helicopter, expansion joints, a landing, a crash, the city and drips are presets from physical models. '
          'They are synthesised, not recordings; the research note says which numbers are sourced and which are starting values.',
)

if __name__ == '__main__':
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(sheet, fh, indent=2)
    print(f'wrote {os.path.relpath(OUT)}: {len(sheet["sections"])} sections, {len(HITS)} hits, {DUR} s')
    for h in HITS:
        print(f'  {h["t"]:7.2f} s  {h["kind"]:7s} {h["sync"]:4s}  {h["sound"][:70]}')
