#!/usr/bin/env python3
"""make_direction.py - writes direction/direction_the_temple_wakes.json from the score's own times and the presets' own places.
Words are written here; every time and every position is read, so the sheet cannot disagree with the score or the presets."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, '..', '..', 'scripts'))
import humanize as hz

score = json.load(open(os.path.join(ROOT, 'scores', 'the_temple_wakes_score.json')))
TM = hz.tempo_map_for(score, seed=score['seed'])
BB = 4


def sec(bar, beat=0.0):
    return round(float(TM.sec((bar - 1) * BB + beat)), 2)


base = json.load(open(os.path.join(ROOT, '..', 'amazon_deep', 'direction', 'direction_into_the_green_dark.json')))
end_s = round(float(TM.sec(52 * BB)), 1)
secs = {s['name']: s for s in score['plan']['sections']}
sections = [
    dict(name='the_approach', role='place', energy=0.35, action='the walker comes to the foot of an overgrown temple at night',
         music='a D pedal in the basses, a heartbeat in the timpani, a semitone D/Eb in the high strings; the cello pulse starts quietly at bar 5; a far whistle; a twig breaks at bar 8'),
    dict(name='the_stairs', role='establish', energy=0.6, action='the steps up the pyramid, and something that answers them',
         music='a conch blast, steps on stone one a beat, the chirped echo, the pulse doubles to sixteenths at bar 17, the drums begin far away'),
    dict(name='the_descent', role='build', energy=0.8, action='a stone door grinds open and the passage goes down',
         music='braam on the door, drips, the pulse never stops, a cluster in the choir, the slab drops at bar 29, then two beats of nothing at bar 32'),
    dict(name='the_awakening', role='peak', energy=1.0, action='the temple wakes: the walls answer',
         music='a braam, the full orchestra on a 3+3+2 drum pattern, the horns state the theme, the violins climb a semitone a bar, a whistle from every side'),
    dict(name='the_run', role='peak', energy=1.0, action='the run for the way out, and the door shuts',
         music='everything at once on every beat, a braam at bar 45, the stone slab slams and the music is cut dead')]
for s in sections:
    s['start_s'], s['end_s'] = secs[s['name']]['start_s'], secs[s['name']]['end_s']
hits = [(sec(8, 3.0), 'motion', 'hard', 'a twig breaks under the walker\'s foot', 'the first wrong sound; the night insects hold their breath'),
        (sec(21), 'musical', 'soft', 'a braam on the stone door: the temple is open', 'weight, not volume'),
        (sec(29), 'musical', 'hard', 'the slab drops into place', 'the point of no return'),
        (sec(32, 2.0), 'musical', 'hard', 'everything stops for two beats', 'the held breath before the temple wakes'),
        (sec(33), 'musical', 'hard', 'the awakening braam with a drum and slab hit', 'the turn: the place is alive'),
        (sec(45), 'musical', 'soft', 'the run begins on a braam', 'the music does not let go from here'),
        (sec(51), 'motion', 'hard', 'the door slams and the music is cut', 'a cliff, not a fade')]
staging = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'presets', 'instruments', 'maya_*.json'))):
    d = json.load(open(f))
    sp = d['spatial']
    staging[d['name']] = dict(azimuth=sp['azimuth'], elevation=sp['elevation'], distance=sp['distance'], space=score['space'])
sheet = dict(base)
sheet.update(
    title='The Temple Wakes', project='A haunted, unknown Maya temple in the deep forest: a hybrid-orchestral cue of pressure that does not let go',
    brief='a high-tension, Hans Zimmer-style hybrid orchestral cue for an unwelcoming adventure through the deep forest into a haunted ancient Maya temple: a pulse that never stops, braams, drums, ritual whistles and a stone door, ending on a cut',
    audience='a listener on headphones, a living-room 5.1 and a 7.1.4 room, and on a phone speaker; they came for the pressure',
    purpose='a ' + str(round(end_s)) + '-second cue in which the walker is drawn up, into and through a temple that wakes, and the door shuts behind them',
    point_of_view='the walker: the steps are the nearest sound; the orchestra and the temple are what is closing in',
    job=['hold pressure from bar 5 to the cut: no section is a rest, except the two beats that are the held breath',
         'turn the story three times with a braam each: the door (bar 21), the awakening (bar 33), the run (bar 45)',
         'let the ritual sounds be the unknown: a whistle that is not a bird, a conch that is not a horn, an echo that is not a voice'],
    story='A walker comes to the foot of a temple the forest has swallowed. A twig breaks; the night insects stop. The steps up are answered by a chirp that runs away down the stairs. A stone door opens by itself. In the passage the pulse never stops; a slab drops behind them; for two beats there is nothing. Then the temple wakes, drums on every side, a whistle that sounds like a scream, and the run begins. The door shuts and the music is cut.',
    duration_s=end_s, in_point_s=0.0, out_point_s=end_s, ending='cut',
    feel=['tense', 'oppressive', 'ancient', 'relentless', 'vast', 'ritual'], avoid_feel=['comic', 'cosy', 'serene', 'meditative', 'cheerful', 'new-age cliche'],
    sections=sections,
    motifs=[dict(name='the semitone', first_at_s=0.0, shape='D against Eb: a minor second held, flickered and stacked', returns='in the ostinato cells, the high strings, the choir cluster and the horns\' theme; the last chord keeps it'),
            dict(name='the horns\' theme', first_at_s=sec(33), shape='D, Eb, D, A: a fall to the flat second and a leap to the fifth', returns='lifted an octave from bar 41; on every beat in the run')],
    instruments=['celli', 'basses', 'violas', 'violins', 'horns', 'trombones', 'tuba', 'timpani', 'bass drum', 'cymbals', 'choir', 'conga', 'whistle', 'conch', 'stone', 'environment'],
    avoid_sounds=['synth pad', 'electric guitar', 'drum kit', 'pop vocals', 'sirens', 'stock jungle loop', 'harp', 'flute'],
    pulse='eighths in the celli from bar 5 that become sixteenths at bar 17 and never stop; footsteps on stone are the second pulse; a 3+3+2 drum pattern from bar 33',
    tempo_bpm=[84, 138], key='D', mode='minor', energy=0.85, space=score['space'],
    hits_at=[h[0] for h in hits], hits=[dict(t=h[0], kind=h[1], sync=h[2], sound=h[3], why=h[4]) for h in hits],
    loudness_lufs=score['master']['lufs'], true_peak_max=-1.5, spatial_staging=staging,
    references=['in words, not a track: a hybrid orchestral thriller cue where a low-string pulse, brass braams and a drum ensemble never let go, with the colour of ritual instruments and a stone place'],
    mix_intent=dict(hero='horns', support=['celli', 'trombones', 'timpani', 'choir'], sits_under=['steps'],
                    must_hear=['the twig snap at ' + str(sec(8, 3.0)) + ' s with the night stopping', 'the door braam at ' + str(sec(21)) + ' s',
                               'two beats of silence at ' + str(sec(32, 2.0)) + ' s', 'the whistle at ' + str(sec(37)) + ' s', 'the cut at ' + str(sec(51)) + ' s'],
                    leave_free_hz=[700, 2600], executed_by=base['mix_intent']['executed_by']),
    intent=score['intent'], focus=score['focus'], piece_type=score['piece_type'],
    gate_reason='a build-hit-release cue with a long line (the horn theme), a held breath and a cut: the cinematic profile, started strict',
    notes=base['notes'])
sheet['delivery'] = dict(base['delivery'], output_targets=score['output_targets'])
imm = dict(base['immersive'])
imm.update(why='the story is about what is around the walker: the stone, the ritual sounds and the drums come from every side; a stereo mix can say it, a field can place it',
           anchors=['basses', 'celli', 'tuba', 'timpani', 'bass_drum', 'drums_left', 'drums_right'],
           movers=[dict(part='jaguar_near', why='it closes from behind on the left on the stairs', path='behind left at 6 m, passing to the left of the listener at 3 m'),
                   dict(part='whistle_4', why='the scream is the nearest sound in the run', path='from the right at 12 m to 3 m by bar 47')],
           height=dict(horns=8, violins_tremolo=22, violins_sustain=26, choir=34, cymbals=14, night=40),
           room_changes=[dict(at_section='the_stairs', why='the forest falls away and the stone begins', transition_s=4.0),
                         dict(at_section='the_descent', why='a narrow stone passage: a close, bright tail', transition_s=4.0),
                         dict(at_section='the_awakening', why='the vault opens above: a taller, longer tail', transition_s=4.0)],
           must_hear=['the chirp running away down the steps', 'the drums on both sides in the awakening', 'the slam and then the cut'],
           deliverables=score['output_targets'])
sheet['immersive'] = imm
os.makedirs(os.path.join(ROOT, 'direction'), exist_ok=True)
out = os.path.join(ROOT, 'direction', 'direction_the_temple_wakes.json')
json.dump(sheet, open(out, 'w'), indent=2)
print('wrote', os.path.relpath(out, os.getcwd()))
