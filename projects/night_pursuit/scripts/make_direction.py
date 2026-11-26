#!/usr/bin/env python3
"""make_direction.py - writes direction/direction_night_pursuit.json: the cue as decisions that can be checked.

Every time in the sheet comes from timeline.py (the bars and the tempo map), so a section that moves in the score moves here.
Only intent lives in the sheet; the numbers that carry it (azimuths, keyframes, room geometry, sweeps) are in presets/.
"""
import json
import os

import timeline as T
from staging import STAGE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'direction', 'direction_night_pursuit.json')
tm = T.tempo_map()
secs = T.sections_with_seconds(tm)
by = {s['name']: s for s in secs}


def at(bar, beat=0.0):
    return round(T.seconds(bar, beat, tm), 2)


T_SPOT = at(T.start('spotted') + 1, 2)                       # the cruiser's lights come on
T_LAUNCH = at(T.start('the_avenue'))
T_DRIFT = at(T.SLOMO_DRIFT['bar'])                           # the tyres let go: time starts to slow
T_SNAP = at(T.SNAP_DRIFT)                                    # the tyres bite: time snaps back
T_UNDER = at(T.start('under_the_bridge'))
T_SPIN = at(T.SLOMO_SPIN['bar'])
T_CRASH = at(T.CRASH_BAR)
T_CUT = at(T.CUT_BAR)
DUR = round(T.seconds(T.END_BAR, 0, tm), 1)

HITS = [
    dict(t=T_SPOT, kind='motion', sync='soft', sound='a cruiser crosses the junction ahead; its lights come on and a siren starts far to the left',
         why='the moment the courier is seen; a soft sync, so a beat either way does not matter'),
    dict(t=T_LAUNCH, kind='musical', sync='soft', sound='the engine wakes: wheelspin on the wet road, first gear, the pulse begins',
         why='the chase starts; the pulse that never stops enters here'),
    dict(t=T_DRIFT, kind='motion', sync='soft', sound='the rear steps out: the drift begins and time starts to slow',
         why='the slow-motion drift needs its lead-in: the tempo falls and the engine and tyres go down in pitch'),
    dict(t=T_SNAP, kind='musical', sync='hard', sound='the tyres bite: a cinematic drop, a sub drop and one impact, and the tempo snaps back',
         why='the release of the slow-motion drift; the strings keep sounding, so it is a hard accent and not a cut'),
    dict(t=T_UNDER, kind='motion', sync='soft', sound='the car enters the underpass: the room closes and the sirens echo',
         why='the place changes; the field, not the music, says it'),
    dict(t=T_SPIN, kind='motion', sync='soft', sound='a cruiser loses the road at the roadblock: a second slow-motion passage',
         why='the pursuer is seen to fail, in slow motion'),
    dict(t=T_CRASH, kind='musical', sync='hard', sound='the cruiser hits the barrier: one impact, metal, glass, and the tempo snaps back',
         why='the turning point of the chase; weight and one real hit, with the quietest bar before it'),
    dict(t=T_CUT, kind='cut', sync='hard', sound='everything sustained stops on the frame; then rain, a ticking engine and one far siren',
         why='the cliff: a hard cut into near silence, so the listener is left on the edge and not given relief'),
]

SECTION_TEXT = {
    'the_stakeout': ('The courier idles at a red light on a wet avenue at two in the morning; rain on the roof, a far siren.',
                     'one low C every bar and a heartbeat on the bass drum; a bass clarinet whispers the semitone; nothing else'),
    'spotted': ('A patrol car crosses ahead and its lights come on; the siren starts to the left; the courier does not move.',
                'the celli begin a quiet figure of eighths; the siren answers the clarinet; the heartbeat quickens'),
    'the_avenue': ('The light changes. Launch on the wet avenue: wheelspin, four shifts, the cruisers behind.',
                   'the pulse enters and does not stop: piano sixteenths, staccato celli, a 3+3+2 drum figure; the horns state the motif'),
    'the_turn': ('A drift into a side street; at its crest time slows, and snaps back.',
                 'the music thins to the heartbeat and a low pedal as the tempo falls; a sub drop and one impact snap it back; the pulse returns a semitone up'),
    'under_the_bridge': ('An underpass: the sirens echo, a second car joins, the engine is loud in the concrete.',
                         'the pulse thins to pulse and low brass, then breaks open into tremolo strings and a rising line, a semitone up again'),
    'the_roadblock': ('Lights across the road; a handbrake turn through the gap; a cruiser spins out.',
                      'the loudest music: trombone stabs, tritone clusters, the snare roll; a second slow passage and the crash hit; a semitone up again'),
    'the_bridge': ('Out onto the bridge, the whole city below; the road ahead is empty and that is worse.',
                   'the pulse at its fastest, violins in staccato runs, the horns state the motif larger; it climbs and does not resolve'),
    'the_cliff': ('A hard cut. Rain, an engine ticking as it cools, a siren far away that does not come closer.',
                  'nothing is sustained at the first beat; a heartbeat returns, a high string harmonic, one unresolved tritone'),
}

ROLE_CUES = {
    'the_stakeout': dict(arousal='low', mode_register='C minor, low and dark', tempo_trend='steady, 128 BPM', dynamics='pp, a heartbeat at mp',
                         articulation='held, then single struck notes', timbre='dark, close, little air'),
    'spotted': dict(arousal='mid', mode_register='C minor with a Db neighbour, mid-low', tempo_trend='steady, a little faster', dynamics='pp rising to mp',
                    articulation='staccato eighths in the celli', timbre='dark, a clarinet reed edge'),
    'the_avenue': dict(arousal='high', mode_register='C minor, a pedal on C and the figure around it', tempo_trend='accelerating 132 BPM and up',
                       dynamics='mf to f, accents on the 3+3+2 cell', articulation='sixteenths, staccato, marcato accents',
                       timbre='brighter as it gets louder: the piano hammers and the brass bite'),
    'the_turn': dict(arousal='high', mode_register='C minor, then a semitone up after the snap', tempo_trend='142 to 146, then a fall to 60 and a snap to 150',
                     dynamics='ff, a collapse to pp in the slow motion, then a drop', articulation='the pulse thins to single notes, then returns',
                     timbre='muffled and low in the slow motion, open and bright at the snap'),
    'under_the_bridge': dict(arousal='high', mode_register='Db minor, tritones against the bass', tempo_trend='steady 150', dynamics='f, thinning then breaking open',
                             articulation='tremolo strings, long low brass', timbre='dense, a tail from the room'),
    'the_roadblock': dict(arousal='high', mode_register='D minor, clusters', tempo_trend='150 to 152, a slow-motion dip and a snap', dynamics='ff, the loudest bar at the crash',
                          articulation='stabs, snare roll, full tutti hit', timbre='the brightest: brass, snare, cymbal, glass'),
    'the_bridge': dict(arousal='high', mode_register='Eb minor, rising line', tempo_trend='152 to 156, still accelerating', dynamics='ff held, no relief',
                       articulation='fast staccato runs and the horn motif', timbre='open and hard, the air up'),
    'the_cliff': dict(arousal='mid', mode_register='C with a Gb above it, unresolved', tempo_trend='a cut to 96, then 84', dynamics='ppp, one swell',
                      articulation='a single harmonic and a heartbeat', timbre='thin, cold, rain-wet'),
}

sheet = dict(
    title='Night Pursuit',
    project='A cinematic car-chase cue through a rainy New York night, written as a listening piece for an 8-channel system',
    version=1,
    medium='film',
    brief='A realistic car chase scene with real car sounds, shifts and drifts in a rainy New York night, police sirens and a full story; '
          'tense, the listener should sit on the edge; instruments, music and the place by physics (rainy roads, street objects that '
          'absorb and reflect), cinematic drops and slow-motion drifts; full immersive, 8 channel; two minutes, three if two is not enough',
    audience='a listener on an 8-channel (7.1) system or headphones, inside the courier\'s car, who came for the chase',
    purpose=f'a {DUR:.0f}-second cue that tells a whole chase: a stakeout, a spotting, a launch, a slow-motion drift, an underpass, a roadblock, a bridge and a cut into silence',
    point_of_view='the courier, in the driver\'s seat: the engine, the rain on the roof and the tyres are the nearest sounds; the sirens and the city are outside and they pass by',
    job=['keep the listener on the edge from the first bar to the last: pressure, never relief',
         'tell the chase in sound: where the cars are, what the road is doing and who is gaining',
         'make the street physical: wet road, façades, parked trucks, an underpass and a bridge change what is heard',
         'give two moments of slow motion and two real hits, and end on a hard cut'],
    story='A courier with a drive of evidence is seen at a red light at two in the morning; the light changes and the chase begins; '
          'a drift into a side street goes into slow motion and snaps back; an underpass, a roadblock and a handbrake turn through the gap; '
          'a cruiser spins out; the bridge; and a hard cut into rain, a ticking engine and one far siren.',
    duration_s=DUR,
    in_point_s=0.0,
    out_point_s=DUR,
    ending='hard_out',
    feel=['tense', 'relentless', 'cold'],
    avoid_feel=['hopeful', 'playful', 'calm', 'triumphant'],
    sections=[dict(name=s['name'], start_s=s['start_s'], end_s=s['end_s'], energy=s['energy'], role=s['role'],
                   action=SECTION_TEXT[s['name']][0], music=SECTION_TEXT[s['name']][1]) for s in secs],
    motifs=[dict(name='the_tick', first_at_s=at(T.start('spotted') + 2), shape='C, Db, C, then a leap up a tritone to Gb and a step down to F: long, short, short, long, long',
                 returns='bass clarinet whispers it; the horns state it at the launch; after the drift snap it climbs a semitone and the horns play it in octaves; '
                         'on the bridge it is played by horns and trombones together with the leap on the weak beat; at the cliff only the Gb is left'),
            dict(name='the_siren_figure', first_at_s=at(T.start('the_stakeout') + 4), shape='a rising and falling sweep between 600 and 1400 Hz, a minor ninth from the key',
                 returns='the second cruiser has a different, faster sweep so the two never share a pitch; both fall away at the cut')],
    instruments=['pursuit_piano', 'pursuit_celli', 'pursuit_basses', 'pursuit_horns', 'pursuit_trombones', 'pursuit_violins_staccato',
                 'pursuit_violins_tremolo', 'pursuit_bass_clarinet', 'pursuit_tuba', 'pursuit_timpani', 'pursuit_bass_drum', 'pursuit_snare',
                 'pursuit_cymbals', 'pursuit_piano_low', 'pursuit_sub_drop'],
    avoid_sounds=['choir', 'bell', 'harp', 'flute', 'guitar', 'synth pad'],
    pulse='steady',
    tempo_bpm=[60, 156],
    key='C',
    mode='minor',
    energy=0.9,
    space='np_street_canyon',
    hits_at=[h['t'] for h in HITS],
    hits=HITS,
    mix_intent=dict(hero='pursuit_horns', support=['pursuit_celli', 'pursuit_trombones', 'pursuit_timpani', 'pursuit_piano'],
                    sits_under=['np_rain_street', 'np_city_far'],
                    must_hear=[f'the engine and the rain in the first 3 s', f'a siren in the left by {T_SPOT:.1f} s',
                               f'the first shift at {at(T.start("the_avenue"), 8):.1f} s', f'the drop at {T_SNAP:.1f} s',
                               f'the room closing at {T_UNDER:.1f} s', f'the crash at {T_CRASH:.1f} s', f'the cut at {T_CUT:.1f} s'],
                    leave_free_hz=[]),
    loudness_lufs=-16.0,
    true_peak_max=-1.5,
    delivery=dict(format='wav', sample_rate=48000, bit_depth=24, stage='cinema', output_targets=['stereo', 'immersive_7_1'],
                  played_on='an 8-channel 7.1 theatre or home system (the fifth-order field decoded to eight speakers), and headphones through the stereo master'),
    references=['a relentless low-string and piano pulse over a wet, close, loud street, with low brass at the turning points and a hard cut into silence',
                'the car as the listener\'s room: the engine in front and below, the road behind, the sirens passing outside'],
    spatial_staging={n: dict(azimuth=a, elevation=e, distance=r, space='np_street_canyon') for n, (a, e, r) in STAGE.items() if n.startswith('pursuit_')},

    immersive=dict(
        enabled=True,
        why='the listener sits inside the courier\'s car: the engine is in front, the road and the spray are behind and at the sides, and the sirens '
            'are outside and pass; the street between the buildings, the underpass and the bridge change the room around the car',
        engine='hoa_bus',
        anchors=['pursuit_piano_low', 'pursuit_basses', 'pursuit_tuba', 'pursuit_bass_drum', 'pursuit_timpani', 'np_engine'],
        movers=[dict(part='np_siren_wail', why='the first cruiser is behind and to the left, then draws alongside and falls back',
                     path='starts far to the front left, comes round to the left at the turn, passes behind in the underpass and falls away behind at the bridge'),
                dict(part='np_siren_yelp', why='the second cruiser joins from the right and tries to cut in',
                     path='enters far to the front right, crosses in front at the roadblock, ends close at the right rear'),
                dict(part='np_drift_squeal', why='the tyres are at the back of the car: the drift swings the rear out',
                     path='left rear to right rear through the turn, and again at the roadblock'),
                dict(part='np_crash', why='the cruiser spins out ahead and to the right',
                     path='fixed ahead and to the right at 12 m; the barrier is the occluder')],
        height={},
        room_changes=[dict(at_section='the_stakeout', why='the street canyon: two façades, a wet road, open sky', transition_s=0.5),
                      dict(at_section='under_the_bridge', why='the underpass: concrete above and on both sides, a long close tail', transition_s=3.0),
                      dict(at_section='the_bridge', why='the bridge: open sky again, steel girders, a flutter between rails', transition_s=3.0),
                      dict(at_section='the_cliff', why='the street again, empty, cold and wet', transition_s=2.0)],
        must_hear=[f'the siren moving from the front left to the left between {T_SPOT:.0f} s and {T_DRIFT:.0f} s',
                   f'the tyres swinging round behind at {T_DRIFT:.0f} s', f'the room closing at {T_UNDER:.0f} s',
                   f'the second siren crossing in front at {at(T.start("the_roadblock") + 4):.0f} s'],
        deliverables=['stereo', 'immersive_7_1'],
        notes='the sheet records intent; the presets execute it. The bus is fifth order (36 channels) and is decoded once to the eight speakers of 7.1, which has no '
              'height speakers, so every part is on the horizontal plane. Keyframes, room geometry and materials are in presets/spaces and presets/sfx.'),
    expression=dict(
        sonic_picture='The first ten seconds: a big engine idling low and a little rough in front and below, rain on the roof all round and a '
                      'far siren that never gets closer; the middle: the engine screaming through its gears with the road hissing behind, a siren moving past on the left, '
                      'a piano pulse of sixteenths and low brass; the last note: nothing sustained, an engine ticking as it cools, rain, one far siren and a single high '
                      'harmonic with a tritone under it.',
        performer='The piano plays the pulse hard and a little ahead of the beat; the celli dig into the first beat of every bar with a short drag and push into the next; '
                  'the horns enter late on each statement and lean on the leap; the timpani heartbeat is soft and slightly behind; the snare roll tightens into the crash; '
                  'the drummer of the 3+3+2 plays the cell with accents that move a little each bar; the strings are sections of six and the brass sections of four.',
        producer_moves='The tempo climbs from 128 to 156 BPM and dips twice into slow motion that snaps back; a bar of near silence before the drop and before the crash; '
                       'the sub drop and one impact at each snap; the room closes in the underpass and opens on the bridge; the rain is thinned, not pitched, in slow motion; '
                       'the final hard cut leaves the rain and one siren.',
        anti_generic='The generic version is a drone, a riser, a drum loop and a car sound laid on top; this one is a pulse that goes up a semitone at each turning point, '
                     'engine, tyres and sirens that obey the road and the geometry, and a cut that leaves the question open.',
        cues=[dict(section=s, **ROLE_CUES[s]) for s in [x['name'] for x in secs]],
        theme=dict(contour='a semitone step and back, then a leap up a tritone and a step down',
                   interval_character='mostly a minor second, with one leap of a tritone',
                   rhythm_cell='long, short, short, long, long',
                   why_memorable='the leap of a tritone lands on the weak beat every time and never resolves',
                   variation_plan='whispered in the bass clarinet, stated by the horns, raised a semitone and doubled in octaves after the snap, played by horns and '
                                  'trombones together on the bridge, and at the cliff only the Gb is left')),
    focus='melody',
    intent=dict(emotions=['tense', 'dark_epic'], registers=['cinematic', 'hybrid'], scenes=['establish', 'build', 'chase', 'dread'],
                tensions=['ostinato', 'pedal', 'tritone', 'cluster', 'rising_line', 'silence_before', 'unresolved_dominant'],
                avoid=['joyful', 'playful', 'hopeful']),
    piece_type='night_pursuit',
    gate_reason='a build-hit-release cue with a short motif, a pulse that never stops and two slow-motion passages: the cinematic profile, started strict, with a '
                'project profile of its own',
    video=dict(enabled=False, source=None, fps=None, cuts=[], cut_source=None, cut_sync=dict(early_ms=45, late_ms=125),
               dialogue=dict(present=False, duck_db=-9.0, snr_min_db=15.0), master_profile=None, deliverable=None, preset='default',
               notes='music-only piece: leave enabled false.'),
    notes='Sound effects and ambience were asked for in the brief: the car, the tyres, the sirens, the crash and the rain are presets from physical models. '
          'They are synthesised, not recordings; the research note says which numbers are sourced and which are starting values.',
)

if __name__ == '__main__':
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(sheet, fh, indent=2)
    print(f'wrote {os.path.relpath(OUT)}: {len(sheet["sections"])} sections, {len(HITS)} hits, {DUR} s')
    for h in HITS:
        print(f'  {h["t"]:7.2f} s  {h["kind"]:7s} {h["sync"]:4s}  {h["sound"][:70]}')
