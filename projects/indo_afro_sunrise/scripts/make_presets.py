#!/usr/bin/env python3
"""make_presets.py - writes the data this piece's presets carry: each instrument's `family` and sources, the characters of the presets that were
scaffolded, and the two happy-vocal presets. Placement moved out of the score into the presets (a score holds names and notes).

Nothing here makes a sound; it fills JSON the engine reads.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
INST = os.path.join(PROJ, 'presets', 'instruments')
VOC = os.path.join(PROJ, 'presets', 'vocals')

FAMILY = {'finger_bass': 'plucked', 'highlife_guitar': 'plucked', 'sitar': 'plucked', 'tambura': 'plucked', 'marimba': 'struck_pitched',
          'brass_section': 'blown_brass', 'bansuri': 'blown_reed', 'djembe': 'struck_membrane', 'tabla': 'struck_membrane',
          'kit': 'struck_membrane', 'shekere': 'struck_membrane'}
CHARACTER = {
    'finger_bass': 'A round fingerstyle bass that owns the low end: roots and fifths on the one, a walking turnaround on every fourth bar, centre-left.',
    'marimba': 'A wooden marimba doubling the groove in short bright figures between the guitar and the flute, a little right of centre.',
    'sitar': 'A sitar that crosses behind the listener in the second half: a buzzing counter-line in the bansuri\'s gaps, never over it.',
    'brass_section': 'A small brass section that punches the turn of a section: short stabs on the chorus, a bar of rest before them.',
}
SOURCES = ['indian-film-fusion', 'african']
NEW_NOTE = ('Scaffolded for the latest implementation (2026-11-28): the preset declares its sound family so the family laws (velocity brightness, attack) '
            'apply, and carries its own placement. Levels and EQ are starting values for this piece.')


def load(p):
    return json.load(open(p, encoding='utf-8'))


def save(p, d):
    json.dump(d, open(p, 'w', encoding='utf-8'), indent=2)


def instruments():
    score = load(os.path.join(PROJ, 'scores', 'indo_afro_sunrise_score.json')) if os.path.exists(
        os.path.join(PROJ, 'scores', 'indo_afro_sunrise_score.json')) else {'tracks': []}
    inline = {t['instrument']: t.get('spatial') for t in score['tracks'] if t.get('spatial')}
    for name, fam in FAMILY.items():
        p = os.path.join(INST, name + '.json')
        d = load(p)
        d['family'] = fam
        if name in CHARACTER:
            d['character'] = CHARACTER[name]
            d['sources'] = SOURCES + [NEW_NOTE]
        if 'character' not in d:
            d['character'] = d.get('description', name)
        sp = inline.get(name)
        if sp:                                           # the placement the score used to carry
            d.setdefault('spatial', {}).update({k: sp[k] for k in ('azimuth', 'elevation', 'distance') if k in sp})
            d['spatial'].setdefault('space', 'indo_afro_sunrise_room')
        save(p, d)
        print('instrument', name, fam, d.get('spatial'))


def vocals():
    base = {
        'synthesis': 'formant', 'hum': False, 'expression_intensity': 1.0,
        'source': {'register': 'modal', 'breathiness': 0.05},
        'performance': {'portamento_ms': 40.0, 'pitch_stability': 1.0},
        'breathing': {'capacity_s': 6.0, 'inhale_gain': 0.5},
    }
    lead = dict(base, name='indo_afro_happy_lead',
                character='A bright wordless lead voice calling in short syllables (la, na, ha, ho) over the groove, forward and a little right of centre, '
                          'answering the bansuri and answered by the group.',
                description='a happy call: open vowels, quick onsets, a light vibrato, one singer doubled by a second',
                vowel='a', expression='hopeful', formants=[850, 1250, 2850], bandwidths=[85.0, 95.0, 130.0],
                vibrato={'depth_cents': 22.0, 'rate_hz': 5.6, 'delay_s': 0.18},
                articulation={'mode': 'legato', 'attack_ms': 45.0, 'release_ms': 140.0},
                ensemble={'voices': 2, 'cohesion': 0.6, 'pitch_spread_cents': 8.0, 'timing_spread_ms': 14.0, 'pan_width': 0.3, 'diversity': 1.0},
                spatial={'azimuth': 38.0, 'elevation': 0.0, 'distance': 2.0, 'space': 'indo_afro_sunrise_room'},
                gain_db=-6.0, reverb=0.22,
                sources=['indian-film-fusion', 'african',
                         'https://books.openedition.org/ifra/522 (Afrobeat: chants and call and response are its vocal core)',
                         'https://flypaper.soundfly.com/write/afrobeat-songs-are-long-and-repetitive-how-are-they-so-irresistibly-compelling/ (call and response runs through the backing vocals and the band)',
                         'ESTIMATE: formants, vibrato and levels are starting values for a bright female voice; no recording was analysed and nothing was listened to'])
    group = dict(base, name='indo_afro_happy_group',
                 character='A group of six answering the call: short chanted hei and ha on the beat, then long open oohs in the last section, wide and a little behind the lead.',
                 description='a happy crowd: more voices, looser timing, a wide spread, shorter notes in the chant',
                 vowel='a', expression='powerful', formants=[780, 1180, 2750], bandwidths=[90.0, 100.0, 140.0],
                 vibrato={'depth_cents': 16.0, 'rate_hz': 5.2, 'delay_s': 0.3},
                 articulation={'mode': 'staccato', 'attack_ms': 25.0, 'release_ms': 110.0},
                 ensemble={'voices': 6, 'cohesion': 0.35, 'pitch_spread_cents': 14.0, 'timing_spread_ms': 28.0, 'pan_width': 0.8, 'diversity': 1.0},
                 spatial={'azimuth': -62.0, 'elevation': 0.0, 'distance': 2.9, 'space': 'indo_afro_sunrise_room'},
                 gain_db=-8.0, reverb=0.28,
                 sources=['indian-film-fusion', 'african',
                          'https://books.openedition.org/ifra/522 (Afrobeat: a chorus sung by a group answers the lead)',
                          'ESTIMATE: voice count, spread and levels are starting values; nothing was listened to'])
    for d in (lead, group):
        save(os.path.join(VOC, d['name'] + '.json'), d)
        print('vocal', d['name'])


if __name__ == '__main__':
    instruments()
    vocals()
