#!/usr/bin/env python3
"""make_direction.py - writes direction/direction_the_mayan_palace.json from the score's own times and the presets' own places.
Words are written here; every time and every position is read, so the sheet cannot disagree with the score or the presets."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, '..', '..', 'scripts'))
import humanize as hz

score = json.load(open(os.path.join(ROOT, 'scores', 'the_mayan_palace_score.json')))
TM = hz.tempo_map_for(score, seed=score['seed'])
BB = 4


def sec(bar, beat=0.0):
    return round(float(TM.sec((bar - 1) * BB + beat)), 2)


base = json.load(open(os.path.join(ROOT, '..', 'amazon_deep', 'direction', 'direction_into_the_green_dark.json')))
end_s = round(float(TM.sec(76 * BB)), 1)
secs = {s['name']: s for s in score['plan']['sections']}
sections = [
    dict(name='the_entry', role='place', energy=0.25, action='an explorer walks into a stone palace the forest has swallowed, torch-lit, curious and unafraid',
         music='a D pedal in the basses, a far timpani stroke, a high shimmer in the strings, a piano that asks a six-note question, and a far closed-mouth hum that answers'),
    dict(name='the_relic_chamber', role='establish', energy=0.4, action='the explorer finds a carved relic in a small chamber, studies it, touches it and opens it',
         music='the question comes back up a fourth, a bass clarinet answers it from the stone, a harp touches the relic, a cello pulse grows under, a choir cluster appears, and a stone lid grinds open'),
    dict(name='the_opening', role='build', energy=0.65, action='what was inside is out: the palace wakes, a door shuts behind the explorer',
         music='a braam, a choir cluster that climbs a semitone a bar, the question in the horns as a threat, a death whistle far inside the walls, a chant that starts on the beat, then one full bar of nothing'),
    dict(name='the_corridors', role='peak', energy=0.85, action='the chase through the palace corridors: the explorer runs, a stone guardian follows, the way out collapses',
         music='a piano pulse of sixteenths that does not stop, chop strings, a 3+3+2 drum pattern with a snare, trombone stabs, a heavy low piano octave behind for the pursuer, the chant on the beat, the horns state the threat, and a timpani roll and a cymbal for the exit falling in'),
    dict(name='the_forest', role='peak', energy=0.95, action='out into the night forest, running through leaves and branches, with the pursuer breaking trees behind',
         music='the pulse continues a tone higher with fast violin runs for branches and leaves, a bar with a beat of silence and a rush for the stumble, the violins climb a semitone a bar, and a hit on the first beat after a rest each time the pursuer breaks a tree'),
    dict(name='the_escape', role='peak', energy=1.0, action='cornered, the explorer turns the curse back with a power of their own and escapes by a hair',
         music='the minor key turns to D major, the hero theme in the horns overrules the threat, and one last hit lands'),
    dict(name='the_release', role='transition', energy=0.45, action='the power spent, the explorer is out of reach; the monsters stop and the forest is quiet again',
         music='the last hit, a beat of nothing, then a held low D, strings in D major and the horns\' hero theme at half weight, a conch far away'),
    dict(name='the_aftermath', role='button', energy=0.2, action='the forest at night, calm; the explorer is safe, and the reed holds a low, steady D',
         music='a held D major, the flute\'s question answered and falling home to D, the forest returns, and the bass clarinet holds a low D')]
for s in sections:
    s['start_s'], s['end_s'] = secs[s['name']]['start_s'], secs[s['name']]['end_s']
hits = [(sec(16, 3.0), 'motion', 'soft', 'the relic\'s stone lid grinds open', 'the choice that starts the story'),
        (sec(18), 'musical', 'hard', 'the opening braam', 'the evil is out; weight, not volume'),
        (sec(22, 2.0), 'motion', 'hard', 'a stone door shuts behind the explorer', 'there is no way back'),
        (sec(25), 'musical', 'hard', 'a full bar of nothing', 'the held breath before the chase'),
        (sec(26), 'musical', 'hard', 'the chase begins on a braam and a drum hit', 'the music does not let go from here'),
        (sec(39, 3.0), 'motion', 'hard', 'the palace exit collapses', 'the way back is gone, the forest begins'),
        (sec(62), 'musical', 'hard', 'D minor turns to D major and the hero theme enters', 'the explorer\'s power'),
        (sec(66), 'musical', 'hard', 'the last hit, then a beat of nothing', 'the narrow escape')]
staging = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'presets', 'instruments', 'mayan_*.json'))):
    d = json.load(open(f))
    sp = d['spatial']
    staging[d['name']] = dict(azimuth=sp['azimuth'], elevation=sp['elevation'], distance=sp['distance'], space=score['space'])
for t in score['tracks']:
    sp = t.get('spatial')
    if sp and t['name'] not in staging and t.get('role') in ('fx', 'environment'):
        staging[t['name']] = dict(azimuth=sp['azimuth'], elevation=sp['elevation'], distance=sp['distance'], space=score['space'])
sheet = dict(base)
sheet.update(
    title='The Mayan Palace', project='A haunted Mayan palace in the deep Mesoamerican rainforest (the Petén lowlands of Guatemala): a story cue from curious exploration to a chase and a narrow escape',
    brief='a Hans Zimmer-style, cinema-grade 7.1.2 score of at least 2 minutes 30 seconds: a hero explores a haunted ancient Mayan palace in the deep rainforest of the Petén, opens a relic out of curiosity and frees an evil, is chased through the palace and then the deep forest, and escapes narrowly using his own power. No sound effects: pianos, orchestra, percussion and voices tell the chase; only the ambience of a haunted palace (with bats) and of the forest is heard',
    audience='a listener on an 8-channel (7.1) system or headphones who should feel they are in the chase; they came for the story',
    purpose='a ' + str(round(end_s)) + '-second cue that tells a whole story: wonder, discovery, a mistake, a chase and an escape',
    point_of_view='the explorer: the steps and the forest touching the runner are the nearest sounds; the palace and what it holds are what is closing in',
    job=['let the first half be curiosity with a low pulse under it, so the opening of the relic lands as a mistake the listener saw coming',
         'hold pressure from bar 26 to bar 66 with a pulse that does not stop; the only rest is the bar before it',
         'turn the minor key to major only at the escape, so the power is heard as a change and not as a reward'],
    story='An explorer walks into a stone palace, slow and curious. In a small chamber they find a carved relic, touch it and open it. Something inside is released; a door shuts behind them and for one bar there is nothing. Then they run: through the corridors with a stone guardian behind, through a collapsing exit and into the night forest where branches and leaves tear at them and trees break behind. Cornered, they turn the curse back with a power of their own and escape by a hair. The forest is calm again and the question has an answer.',
    duration_s=end_s, in_point_s=0.0, out_point_s=end_s, ending='tail_out',
    feel=['tense', 'epic', 'ancient', 'relentless', 'cinematic'], avoid_feel=['comic', 'cosy', 'serene', 'meditative', 'cheerful', 'new-age cliche'],
    sections=sections,
    motifs=[dict(name='the relic motif', first_at_s=sec(4), shape='D Eb D A G F: a flat second that returns, a leap of a fifth, then a falling step (it ends on F, not home on D: a question)', returns='in the flute as a question (bar 4), up a fourth (bar 9), in the bass clarinet as the answer (bar 11), in the horns as a threat (bars 18-61), in the flute again as a resolved answer (bar 70), and answered at last, falling home to D'),
            dict(name='the hero theme', first_at_s=sec(62), shape='D A C D E D C A: a rising fifth, a climb to the octave and a step above it, then back down; over D major the C natural keeps a hard-won mixolydian colour (the flat seventh) instead of a plain major lift', returns='once more at bar 66 a fourth higher, and under the aftermath as a held horn D')],
    instruments=['piano', 'low piano', 'celli', 'basses', 'violas', 'violins', 'alto flute', 'bass clarinet', 'harp', 'horns', 'trombones', 'tuba', 'timpani', 'bass drum', 'snare', 'cymbals', 'conga', 'choir', 'chant voices', 'hum', 'death whistle', 'conch', 'bats', 'forest ambience'],
    avoid_sounds=['synth pad', 'electric guitar', 'drum kit', 'pop vocals', 'sirens', 'riser', 'whoosh', 'stinger', 'boom tail', 'stock jungle loop', 'footsteps', 'foley', 'sound effects'],
    pulse='the relentless pulse is a piano figure of sixteenths with staccato celli and violas from bar 26 that never stops until bar 66; before it there is only a warning: one far timpani stroke per bar from bar 5, a sparse cello figure of eighths from bar 13 (the relic hum), and a rolled timpani in the opening; footsteps are the second pulse; a 3+3+2 drum pattern from bar 26',
    tempo_bpm=[56, 172], key='D', mode='minor', energy=0.7, space=score['space'],
    hits_at=[h[0] for h in hits], hits=[dict(t=h[0], kind=h[1], sync=h[2], sound=h[3], why=h[4]) for h in hits],
    loudness_lufs=score['master']['lufs'], true_peak_max=-1.5, spatial_staging=staging,
    references=['in words, not a track: an adventure-horror film score where a quiet exploration turns into a relentless orchestral chase with a recurring motif, ending in release'],
    mix_intent=dict(hero='horns', support=['celli', 'trombones', 'timpani', 'choir'], sits_under=['chant'],
                    must_hear=['the flute\'s question at ' + str(sec(4)) + ' s', 'the stone lid at ' + str(sec(16, 3.0)) + ' s', 'a bar of nothing at ' + str(sec(25)) + ' s',
                               'the exit collapse at ' + str(sec(39, 3.0)) + ' s', 'the D major turn at ' + str(sec(62)) + ' s', 'the answer in the flute at ' + str(sec(70)) + ' s'],
                    leave_free_hz=[700, 2600], executed_by=base['mix_intent']['executed_by']),
    intent=score['intent'], focus=score['focus'], piece_type=score['piece_type'],
    gate_reason='a build-hit-release cue with a long melodic line (the motif), a held bar and a release: the cinematic profile, started strict',
    notes=base['notes'])
sheet['expression'] = dict(
    sonic_picture='The first ten seconds are a low D held on a piano in a large dark room with bats in the vault and far away a whistle, and a high piano that is close and a little hesitant asking a six-note question; the middle is a hard, fast run, a piano pulse of sixteenths with fast violin runs on both sides and a heavy low octave behind; the last note is a low reed holding D under a wide major chord.',
    performer='The flute breathes before the long note and lets the last note fall off; the celli dig into the beat with a little drag on beat one and a push into the next bar; the horns enter late on the threat and play the leaps with a short slide in; the timpani stroke is soft and slightly behind; the pianist plays the pulse with the left hand a hair ahead and trips once, in the bar with a beat of silence.',
    producer_moves='The room gets bigger at the opening and tighter in the corridors and then opens to the forest; one full bar of nothing before the chase; the tempo accelerates in the chase and the forest; a single tutti hit and one beat of nothing before the release; the key turns to major only at the escape.',
    anti_generic='The generic version is a drone, a riser and a drum loop with a monster sound; this one is a story told by a motif that is first a question, then an answer, then a threat, and is finally overruled by a different shape, with a pulse that appears only once the evil is out.',
    cues=[dict(section='the_entry', arousal='low', mode_register='D minor, mid-low with a high shimmer', tempo_trend='steady and slow (72)', dynamics='pp to p', articulation='tenuto, legato', timbre='dark, breathy'),
          dict(section='the_relic_chamber', arousal='low to mid', mode_register='D minor, a low reed against a high flute', tempo_trend='steady (72)', dynamics='p growing to mp', articulation='legato with single plucks', timbre='hollow, dark'),
          dict(section='the_opening', arousal='mid to high', mode_register='D minor with a rising cluster', tempo_trend='accelerating from 72 to 90, then a one-bar hold at 58', dynamics='mf to ff then a bar of nothing', articulation='sustained swells, a rolled timpani', timbre='dark, brassy'),
          dict(section='the_corridors', arousal='high', mode_register='D minor, low and loud', tempo_trend='fast and steady (132 to 146)', dynamics='f to ff', articulation='staccato ostinato and marcato brass', timbre='dark, hard'),
          dict(section='the_forest', arousal='high', mode_register='D minor, a rising line in the violins', tempo_trend='faster (146 to 154)', dynamics='ff', articulation='staccato ostinato, tremolo strings', timbre='dark and rough'),
          dict(section='the_escape', arousal='very high, then release', mode_register='D minor to D major, bright and wide', tempo_trend='158, then a hit and a hold', dynamics='fff then a drop', articulation='broad, full-length brass', timbre='bright, open'),
          dict(section='the_release', arousal='mid, falling', mode_register='D major, wide, the horns at half weight', tempo_trend='158, then a hit, a hold and a slow fall', dynamics='fff then a drop to mp', articulation='broad, then held', timbre='open'),
          dict(section='the_aftermath', arousal='low', mode_register='D major, wide and still', tempo_trend='slow (66 to 62)', dynamics='p to pp', articulation='legato, held', timbre='warm, open')],
    theme=dict(contour='a flat second that returns, a leap up of a fifth and then a falling step: a question that does not resolve',
               interval_character='a minor second, a perfect fifth, two steps down', rhythm_cell='long, short, long, very long, long, long',
               why_memorable='the semitone returns before the leap, so the ear expects the fall to land on D and it lands on F',
               variation_plan='up a fourth and curious in the flute, low and hollow in the bass clarinet, loud in the horns as a threat, overruled by the hero theme in D major, and finally answered in the flute, falling home to D'))
sheet['delivery'] = dict(base['delivery'], output_targets=score['output_targets'])
imm = dict(base['immersive'])
imm.update(why='the story is about what is around the runner: the pursuer is behind, the runs of the violins pass on both sides, the chant is all around, and the rooms change from a stone hall to a forest; a stereo mix can say it, a 7.1.2 bed can place it',
           anchors=['basses', 'celli', 'tuba', 'timpani', 'bass_drum', 'drums_left', 'drums_right'],
           movers=[dict(part='piano_low', why='the heavy low octave is the pursuer, behind the listener', path='behind and to the left at 3 m, fixed; louder on each fourth bar'),
                   dict(part='chant', why='the voices answer the drums from behind and from the side', path='behind to the left at 5 m, fixed')],
           height=dict(horns=18, piano=30, violins_staccato=34, violins_tremolo=22, violins_sustain=40, choir=34, cymbals=14, night=40),
           room_changes=[dict(at_section='the_relic_chamber', why='a small chamber with the relic', transition_s=4.0),
                         dict(at_section='the_opening', why='the vault opens above: a taller, longer tail', transition_s=4.0),
                         dict(at_section='the_corridors', why='a narrow stone passage: a close tail', transition_s=3.0),
                         dict(at_section='the_forest', why='out of the stone into an open green space', transition_s=4.0),
                         dict(at_section='the_aftermath', why='the forest, quiet', transition_s=4.0)],
           must_hear=['the heavy octave behind in the corridors', 'the violin runs on the left in the forest', 'the room opening at the exit'],
           deliverables=score['output_targets'])
sheet['immersive'] = imm
os.makedirs(os.path.join(ROOT, 'direction'), exist_ok=True)
out = os.path.join(ROOT, 'direction', 'direction_the_mayan_palace.json')
json.dump(sheet, open(out, 'w'), indent=2)
print('wrote', os.path.relpath(out, os.getcwd()))
