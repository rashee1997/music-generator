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
"""compose.py - emotion/scene brief  ->  natural score (JSON)  ->  (optionally) rendered WAV + MIDI.

This is the "situational music" engine. You describe the situation, it builds real music whose
musical parameters follow the research on how listeners hear emotion (Juslin / Eerola: mode, tempo,
register, loudness, articulation, harmony, density, timbre), in a recognisable form (phrases that
repeat, vary and cadence), arranged in layers that enter and leave with the emotional arc.

    python3 compose.py --emotion sad --genre piano --duration 60 --out sad.json --render sad.wav
    python3 compose.py --brief brief.json --render out.wav --midi out.mid
    python3 compose.py --list                       # emotions, genres, arcs

brief.json (all keys optional except emotion or scene):
{
  "emotion": "melancholy",              # see --list; free words are mapped by EMOTION_ALIASES
  "scene": "rainy window, quiet evening",   # extra keywords nudge emotion/genre if emotion missing
  "genre": "piano",                     # ambient piano cinematic acoustic lofi orchestral folk jazz pop dark electronic
  "duration_s": 60, "bpm": null, "key": "D", "mode": null,
  "energy": null,                       # 0..1 how hard it pushes. Default: the mood's own band (calm 0.40, epic 0.68)
  "space": null,                        # dry | studio | hall | large_hall | cathedral: how much room it sits in
  "tempo_scale": 1.0,                   # multiplies the tempo (0.86 = a "slow" version of the same mood)
  "plan": false,                        # true: build the section plan (open, develop, build, climax, hush, reveal)
  "arc": "rise_fall",                   # steady build rise_fall wave tension_release fall sparse
  "intensity": 0.5,                     # 0..1 overall energy (scales loudness, density, layers)
  "tension": null,                      # 0..1 override of dissonance/ostinato/sparse-stinger amount
  "lead": null,                         # override melody instrument, e.g. "flute"
  "voiceover": false,                   # true: sparse mid-range underscore that leaves room for speech
  "loop": false,                        # true: seamless loop (no ritardando, tail wrapped)
  "hit_points": [{"t": 12.0, "type": "impact"}, {"t": 30, "type": "rise"}, {"t": 41, "type": "silence"}],
  "seed": 7, "humanize": "natural"
}
Output is a natural score for render_natural.py. EDIT IT: change instruments, swap bars, retune - or write
your own score from scratch (see references/workflow/custom-scripts.md); compose.py is a starting point, not a cage.
"""
import argparse
import copy
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from theory import (Key, TEXTURES, bass_line, bass_note, clamp_register, drum_bar, harmony_line, make_phrase,
                    note_name, parse_progression, vary_phrase, voice_lead, MODES)
import presets
import world

# ------------------------------------------------------------------------------------------------
# emotion table.  Based on listener-perception research (see references/scoring/emotion-and-scoring.md):
#   mode strongest cue (major=happy, minor=sad) > tempo > register > dynamics > articulation > timbre
# ------------------------------------------------------------------------------------------------
EMOTIONS = {
    'calm': dict(modes=['major', 'lydian', 'pentatonic_major'], bpm=(56, 74), center=6, dyn=(0.25, 0.55), style='slow',
                 rest=0.25, tension=0.0, hr=2, genres=['ambient', 'piano', 'acoustic'], arc='steady',
                 keys=['C', 'F', 'G', 'D', 'Bb'], art=0.97, drums='none',
                 prog={'major': ['I-V-vi-IV', 'I-iii-IV-I', 'Imaj7-IVmaj7-Imaj7-V'], 'lydian': ['Imaj7-II-Imaj7-vi'],
                       'pentatonic_major': ['I-IV-I-V']}),
    'tender': dict(modes=['major', 'lydian'], bpm=(58, 78), center=7, dyn=(0.28, 0.6), style='slow', rest=0.2,
                   tension=0.05, hr=1, genres=['piano', 'acoustic', 'orchestral'], arc='rise_fall',
                   keys=['F', 'Eb', 'G', 'D', 'Ab'], art=0.97, drums='none',
                   prog={'major': ['I-iii-IV-V', 'I-vi-IV-V', 'I-V-vi-iii-IV-I-IV-V', 'Imaj7-iii7-IVmaj7-V'],
                         'lydian': ['I-II-vi-V']}),
    'sad': dict(modes=['aeolian', 'dorian'], bpm=(54, 70), center=5, dyn=(0.22, 0.6), style='slow', rest=0.25,
                tension=0.1, hr=1, genres=['piano', 'cinematic', 'orchestral'], arc='rise_fall',
                keys=['D', 'A', 'E', 'C', 'G'], art=0.98, drums='none',
                prog={'aeolian': ['i-VI-III-VII', 'i-iv-VII-III', 'i-VII-VI-V', 'i-iv-i-V', 'i-VI-iv-V'],
                      'dorian': ['i-IV-i-VII', 'i-VII-IV-i']}),
    'melancholy': dict(modes=['dorian', 'aeolian'], bpm=(62, 80), center=6, dyn=(0.25, 0.62), style='slow', rest=0.2,
                       tension=0.1, hr=1, genres=['piano', 'acoustic', 'lofi'], arc='wave',
                       keys=['D', 'E', 'A', 'G'], art=0.95, drums='soft_pulse',
                       prog={'dorian': ['i-IV-i-VII', 'i7-IV7-i7-v7', 'i-VII-IV-i'],
                             'aeolian': ['i-VI-III-VII', 'i-iv-VI-V']}),
    'grief': dict(modes=['aeolian'], bpm=(48, 60), center=3, dyn=(0.2, 0.5), style='slow', rest=0.35, tension=0.15,
                  hr=2, genres=['piano', 'orchestral', 'ambient'], arc='fall', keys=['D', 'C', 'F#'], art=1.0,
                  drums='none', prog={'aeolian': ['i-iv-i-V', 'i-VI-iv-i', 'i-VII-VI-V']}),
    'nostalgic': dict(modes=['major', 'mixolydian'], bpm=(66, 86), center=6, dyn=(0.3, 0.62), style='medium',
                      rest=0.15, tension=0.05, hr=1, genres=['acoustic', 'piano', 'lofi'], arc='wave',
                      keys=['G', 'C', 'D', 'A'], art=0.9, drums='soft_pulse',
                      prog={'major': ['I-vi-ii-V', 'I-iii-IV-iv', 'I-IV-I-iv', 'I-vi-IV-V'], 'mixolydian': ['I-bVII-IV-I']}),
    'hopeful': dict(modes=['major', 'lydian'], bpm=(76, 98), center=7, dyn=(0.3, 0.8), style='medium', rest=0.1,
                    tension=0.05, hr=1, genres=['cinematic', 'acoustic', 'piano'], arc='build',
                    keys=['D', 'G', 'C', 'A'], art=0.92, drums='half',
                    prog={'major': ['vi-IV-I-V', 'I-V-vi-IV', 'IV-I-V-vi', 'I-iii-IV-V'], 'lydian': ['I-II-I-V']}),
    'joyful': dict(modes=['major', 'mixolydian'], bpm=(108, 130), center=8, dyn=(0.45, 0.85), style='driving',
                   rest=0.08, tension=0.0, hr=1, genres=['pop', 'folk', 'acoustic'], arc='wave',
                   keys=['G', 'C', 'D', 'A', 'E'], art=0.8, drums='pop',
                   prog={'major': ['I-V-vi-IV', 'I-IV-V-I', 'I-vi-IV-V', 'I-IV-I-V'], 'mixolydian': ['I-bVII-IV-I']}),
    'playful': dict(modes=['major', 'mixolydian'], bpm=(100, 124), center=8, dyn=(0.35, 0.7), style='medium',
                    rest=0.2, tension=0.0, hr=1, genres=['acoustic', 'folk', 'jazz'], arc='wave',
                    keys=['C', 'F', 'G'], art=0.55, drums='shaker',
                    prog={'major': ['I-IV-V-I', 'I-vi-ii-V', 'I-V-I-IV'], 'mixolydian': ['I-bVII-IV-I']}),
    'triumphant': dict(modes=['major', 'mixolydian'], bpm=(84, 108), center=7, dyn=(0.4, 1.0), style='medium',
                       rest=0.05, tension=0.1, hr=1, genres=['cinematic', 'orchestral'], arc='build',
                       keys=['D', 'Bb', 'C', 'Eb'], art=0.95, drums='taiko',
                       prog={'major': ['I-V-vi-IV', 'I-IV-V-I', 'vi-IV-I-V'], 'mixolydian': ['I-bVII-IV-I']}),
    'epic': dict(modes=['major', 'mixolydian'], bpm=(88, 112), center=7, dyn=(0.35, 1.0), style='medium', rest=0.05,
                 tension=0.2, hr=1, genres=['cinematic', 'orchestral'], arc='build', keys=['D', 'C', 'Bb', 'Eb'],
                 art=0.95, drums='taiko',
                 prog={'major': ['I-V-vi-IV', 'I-IV-V-I', 'vi-IV-I-V', 'I-vi-IV-V', 'I-bVI-bVII-I'], 'mixolydian': ['I-bVII-IV-I']}),
    'determined': dict(modes=['aeolian', 'dorian'], bpm=(92, 112), center=5, dyn=(0.4, 0.85), style='driving',
                       rest=0.1, tension=0.25, hr=1, genres=['cinematic', 'pop'], arc='build', keys=['E', 'A', 'D'],
                       art=0.8, drums='march', prog={'aeolian': ['i-VII-VI-VII', 'i-VI-III-VII'], 'dorian': ['i-IV-i-VII']}),
    'tense': dict(modes=['aeolian', 'phrygian'], bpm=(72, 100), center=3, dyn=(0.25, 0.85), style='medium',
                  rest=0.3, tension=0.7, hr=1, genres=['dark', 'cinematic'], arc='tension_release',
                  keys=['C', 'D', 'E', 'F#'], art=0.7, drums='heartbeat',
                  prog={'aeolian': ['i-i-bVI-bII', 'i-iv-i-V7', 'i-bVI-bII-V'], 'phrygian': ['i-II-i-II', 'i-II-vii-i']}),
    'scary': dict(modes=['phrygian', 'locrian'], bpm=(48, 68), center=1, dyn=(0.2, 1.0), style='slow', rest=0.45,
                  tension=1.0, hr=2, genres=['dark'], arc='tension_release', keys=['C', 'E', 'F#', 'Bb'], art=0.8,
                  drums='heartbeat', prog={'phrygian': ['i-II-i-II', 'i-II-vii-II'], 'locrian': ['i-II-i-vii']}),
    'angry': dict(modes=['phrygian', 'aeolian'], bpm=(120, 150), center=4, dyn=(0.6, 1.0), style='driving',
                  rest=0.05, tension=0.7, hr=1, genres=['dark', 'cinematic', 'pop'], arc='build', keys=['E', 'D', 'C'],
                  art=0.6, drums='pop', prog={'phrygian': ['i-II-i-VII', 'i-II-iii-II'], 'aeolian': ['i-VII-VI-VII', 'i-bII-i-V']}),
    'mysterious': dict(modes=['lydian', 'dorian', 'whole_tone'], bpm=(58, 82), center=7, dyn=(0.2, 0.6), style='slow',
                       rest=0.35, tension=0.4, hr=2, genres=['ambient', 'dark', 'cinematic'], arc='wave',
                       keys=['D', 'E', 'Bb', 'F#'], art=0.95, drums='none',
                       prog={'lydian': ['Imaj7-II-Imaj7-vi', 'I-II-I-bVII'], 'dorian': ['i-IV-i-bVII'],
                             'whole_tone': ['I-II-I-II']}),
    'wonder': dict(modes=['lydian', 'major'], bpm=(66, 90), center=9, dyn=(0.25, 0.8), style='slow', rest=0.2,
                   tension=0.1, hr=1, genres=['cinematic', 'ambient', 'orchestral'], arc='build',
                   keys=['D', 'F', 'A', 'E'], art=0.95, drums='none',
                   prog={'lydian': ['I-II-I-V', 'Imaj7-II-vi-V', 'I-II-iii-II'], 'major': ['I-V-vi-IV', 'IV-I-V-vi']}),
    'dreamy': dict(modes=['lydian', 'major', 'dorian'], bpm=(58, 76), center=7, dyn=(0.2, 0.5), style='slow', rest=0.3,
                   tension=0.05, hr=2, genres=['ambient', 'lofi', 'piano'], arc='wave', keys=['F', 'Bb', 'C', 'A'],
                   art=1.0, drums='none', prog={'lydian': ['Imaj7-II-Imaj7-vi'], 'major': ['Imaj7-iii7-IVmaj7-V'],
                                                'dorian': ['i7-IV7']}),
    'focused': dict(modes=['major', 'pentatonic_major', 'dorian'], bpm=(84, 104), center=6, dyn=(0.3, 0.5),
                    style='medium', rest=0.3, tension=0.0, hr=2, genres=['lofi', 'piano', 'acoustic'], arc='steady',
                    keys=['C', 'G', 'D', 'F'], art=0.9, drums='lofi',
                    prog={'major': ['I-V-vi-IV', 'I-iii-IV-V', 'I-IV-vi-V'], 'pentatonic_major': ['I-IV-I-V'],
                          'dorian': ['i-IV-i-IV']}),
    'energetic': dict(modes=['major', 'mixolydian'], bpm=(118, 140), center=8, dyn=(0.55, 0.95), style='driving',
                      rest=0.05, tension=0.1, hr=1, genres=['pop', 'electronic', 'folk'], arc='build',
                      keys=['E', 'A', 'D', 'G'], art=0.75, drums='four_floor',
                      prog={'major': ['I-V-vi-IV', 'vi-IV-I-V', 'I-IV-V-V'], 'mixolydian': ['I-bVII-IV-I']}),
    'majestic': dict(modes=['major', 'lydian'], bpm=(60, 78), center=7, dyn=(0.4, 1.0), style='slow', rest=0.05,
                     tension=0.1, hr=1, genres=['orchestral', 'cinematic'], arc='build', keys=['D', 'Bb', 'Eb'],
                     art=1.0, drums='taiko', prog={'major': ['I-IV-I-V', 'I-V-vi-IV', 'I-iii-IV-V'], 'lydian': ['I-II-I-V']}),
    'dark_epic': dict(modes=['aeolian', 'phrygian'], bpm=(76, 100), center=5, dyn=(0.4, 1.0), style='medium', rest=0.08,
                      tension=0.5, hr=1, genres=['cinematic', 'dark'], arc='build', keys=['D', 'C', 'E', 'G'],
                      art=0.95, drums='taiko',
                      prog={'aeolian': ['i-VI-III-VII', 'i-VII-VI-VII', 'i-bVI-VII-i'], 'phrygian': ['i-II-i-VII']}),
    'passionate': dict(modes=['harmonic_minor', 'aeolian'], bpm=(96, 120), center=7, dyn=(0.4, 0.9), style='driving',
                       rest=0.08, tension=0.45, hr=1, genres=['orchestral', 'cinematic'], arc='build', keys=['D', 'A', 'E'],
                       art=0.85, drums='half',
                       prog={'harmonic_minor': ['i-iv-V-i', 'i-VI-iv-V'], 'aeolian': ['i-iv-VII-i']}),
    # wide-eyed rather than victorious: a journey, not a battle. It is NOT the epic preset, so it does not inherit
    # taiko, the trailer build or a 107 BPM drive unless the brief asks for them.
    'adventure': dict(modes=['major', 'lydian', 'dorian'], bpm=(84, 104), center=7, dyn=(0.3, 0.8), style='medium',
                      rest=0.15, tension=0.15, hr=1, genres=['orchestral', 'cinematic', 'world'], arc='build',
                      keys=['D', 'G', 'A', 'C'], art=0.9, drums='half',
                      prog={'major': ['I-V-vi-IV', 'I-IV-V-I', 'vi-IV-I-V'], 'lydian': ['I-II-I-V', 'I-II-vi-V'],
                            'dorian': ['i-IV-i-VII']}),
}
EMOTION_ALIASES = {
    'peaceful': 'calm', 'serene': 'calm', 'relaxed': 'calm', 'soothing': 'calm', 'meditative': 'calm', 'sleepy': 'calm',
    'love': 'tender', 'romantic': 'tender', 'warm': 'tender', 'intimate': 'tender', 'gentle': 'tender',
    'sorrow': 'sad', 'sorrowful': 'sad', 'lonely': 'sad', 'loss': 'grief', 'mourning': 'grief', 'funeral': 'grief',
    'bittersweet': 'melancholy', 'wistful': 'melancholy', 'reflective': 'melancholy', 'rain': 'melancholy',
    'memory': 'nostalgic', 'memories': 'nostalgic', 'vintage': 'nostalgic', 'homesick': 'nostalgic',
    'optimistic': 'hopeful', 'uplifting': 'hopeful', 'inspiring': 'hopeful', 'sunrise': 'hopeful', 'dawn': 'hopeful',
    'happy': 'joyful', 'cheerful': 'joyful', 'celebration': 'joyful', 'party': 'joyful', 'fun': 'playful',
    'quirky': 'playful', 'comedy': 'playful', 'whimsical': 'playful', 'cute': 'playful',
    'victory': 'triumphant', 'heroic': 'epic', 'hero': 'epic', 'battle': 'dark_epic', 'powerful': 'epic',
    'adventure': 'adventure', 'adventurous': 'adventure', 'quest': 'adventure', 'journey': 'adventure',
    'expedition': 'adventure', 'explore': 'adventure', 'exploration': 'adventure', 'frontier': 'adventure',
    'motivational': 'hopeful', 'motivate': 'hopeful', 'motivation': 'hopeful', 'motivating': 'hopeful',
    'purposeful': 'hopeful', 'uplift': 'hopeful', 'encouraging': 'hopeful',
    'resolve': 'determined', 'training': 'determined', 'chase': 'tense', 'suspense': 'tense', 'anxious': 'tense',
    'nervous': 'tense', 'thriller': 'tense', 'dread': 'scary', 'horror': 'scary', 'creepy': 'scary', 'fear': 'scary',
    'aggressive': 'angry', 'rage': 'angry', 'intense': 'angry', 'mystery': 'mysterious', 'curious': 'mysterious',
    'magic': 'wonder', 'magical': 'wonder', 'awe': 'wonder', 'discovery': 'wonder', 'space': 'wonder',
    'dream': 'dreamy', 'floating': 'dreamy', 'hazy': 'dreamy', 'study': 'focused', 'work': 'focused', 'neutral': 'focused',
    'explainer': 'focused', 'tutorial': 'focused', 'corporate': 'focused', 'productive': 'focused', 'upbeat': 'energetic',
    'workout': 'energetic', 'sport': 'energetic', 'hype': 'energetic', 'regal': 'majestic', 'grand': 'majestic',
    'noble': 'majestic', 'ceremony': 'majestic',
    # GEMS factors (Zentner et al.) and basic emotions, mapped to the nearest preset; see references/scoring/genres-and-moods.md
    'power': 'epic', 'transcendence': 'wonder', 'transcendent': 'wonder', 'sensual': 'tender',
    'passion': 'passionate', 'depressed': 'sad', 'depression': 'sad', 'sadness': 'sad',
    'joy': 'joyful', 'happiness': 'joyful', 'anger': 'angry', 'tenderness': 'tender',
    'peacefulness': 'calm', 'nostalgia': 'nostalgic', 'joyful_activation': 'energetic',
}

EMOTION_ALIASES.update({   # mood words from Pixabay playlists (relax, energise, focus, party, peace, spooky...)
    'relax': 'calm', 'peace': 'calm', 'calming': 'calm', 'mellow': 'calm', 'laid_back': 'calm', 'zen': 'calm',
    'focus': 'focused', 'energise': 'energetic', 'energize': 'energetic', 'stimulating': 'energetic',
    'running': 'energetic', 'spooky': 'scary', 'haunting': 'scary', 'funny': 'playful', 'bloopers': 'playful',
    'kids': 'playful', 'children': 'playful', 'dramatic': 'tense',
})

# ------------------------------------------------------------------------------------------------
# mood words that are not emotions. "motivational" is a mood; "slow", "reverb" and "sparse" are arrangement
# decisions. They are read from the same text and applied to tempo, density and the room, so a phrase like
# "slow reverb mix" produces a slow piece in a large hall instead of another upbeat one.
# ------------------------------------------------------------------------------------------------
MOOD_MODS = {   # word: (energy delta, tempo factor). The neutral point is the mood's own band, not 0.5.
    'slow': (-0.15, 0.86), 'slower': (-0.2, 0.80), 'slowly': (-0.15, 0.86), 'downtempo': (-0.15, 0.86),
    'ballad': (-0.12, 0.85), 'chill': (-0.12, 0.90), 'lazy': (-0.15, 0.86), 'hushed': (-0.12, 0.95),
    'understated': (-0.12, 0.95), 'subtle': (-0.10, 1.00), 'restrained': (-0.12, 0.95),
    'fast': (0.12, 1.14), 'faster': (0.15, 1.20), 'uptempo': (0.12, 1.14), 'driving': (0.10, 1.08),
    'punchy': (0.10, 1.05), 'frantic': (0.18, 1.20),
}
WET_WORDS = {'reverb', 'reverbed', 'wet', 'spacious', 'cavernous', 'cathedral', 'wash', 'washed', 'vast', 'huge',
             'distant', 'tail', 'trail', 'echo'}
DRY_WORDS = {'dry', 'close', 'dead', 'tight', 'intimate'}
DENSE_WORDS = {'sparse': -1, 'minimal': -1, 'bare': -1, 'simple': -1, 'stripped': -1,
               'dense': 1, 'full': 1, 'lush': 1, 'busy': 1}


def mood_from_mods(mods):
    """No emotion word, but the user did say how it should sound: pick the mood their modifiers imply."""
    slow, wet, fast = mods['bpm'] < 0.95, mods['room'] in ('large_hall', 'cathedral', 'cave'), mods['bpm'] > 1.05
    if slow and wet:
        return 'dreamy'
    if fast:
        return 'energetic'
    if slow or mods['density'] < 0:
        return 'calm'
    return 'dreamy' if wet else 'focused'


ARCS = {   # intensity per 4-bar phrase, resampled to the piece length (0..1)
    'steady':  [0.45, 0.5, 0.5, 0.5, 0.5, 0.45],
    'build':   [0.2, 0.35, 0.5, 0.65, 0.85, 1.0, 0.7],
    'rise_fall': [0.2, 0.4, 0.65, 0.9, 0.7, 0.4, 0.2],
    'wave':    [0.3, 0.55, 0.4, 0.7, 0.45, 0.8, 0.35],
    'tension_release': [0.2, 0.35, 0.55, 0.8, 1.0, 0.3, 0.2],
    'fall':    [0.6, 0.5, 0.4, 0.3, 0.2, 0.12],
    'sparse':  [0.2, 0.25, 0.3, 0.25, 0.3, 0.2],
}

# ------------------------------------------------------------------------------------------------
# genre = instrumentation + feel. layers enter when intensity >= min.
# kind: chords | bass | melody | harmony | pad | sparkle | drums | ostinato
# ------------------------------------------------------------------------------------------------
GENRES = {
    'piano': dict(room='hall', swing=0.5, humanize='rubato', tone='neutral', lufs=-16, layers=[
        dict(name='piano', instrument='piano', kind='chords', tex_low='sparse', tex_mid='arp8', tex_hi='arp8', lo=48, hi=70, min=0.0, role='chord'),
        dict(name='lead', instrument='piano', kind='melody', oct=0, min=0.15, role='melody', gain_db=-2),
        dict(name='strings', instrument='slow_strings', kind='pad', lo=45, hi=69, min=0.45, role='pad', gain_db=-3),
        dict(name='cello', instrument='cello', kind='bass', bass='whole', lo=36, hi=52, min=0.5, role='bass', gain_db=-1),
        dict(name='counter', instrument='violin', kind='harmony', min=0.75, role='counter', oct=0)]),
    'cinematic': dict(room='large_hall', swing=0.5, humanize='natural', tone='warm', lufs=-16, layers=[
        dict(name='strings', instrument='slow_strings', kind='pad', lo=45, hi=72, min=0.0, role='pad'),
        dict(name='piano', instrument='piano', kind='chords', tex_low='sparse', tex_mid='arp8', tex_hi='arp16', lo=50, hi=72, min=0.12, role='chord'),
        dict(name='lead', instrument='cello', kind='melody', oct=0, min=0.2, role='melody', gain_db=-1),
        dict(name='bass', instrument='double_bass', kind='bass', bass='whole', lo=31, hi=48, min=0.35, role='bass'),
        dict(name='violins', instrument='violin', kind='melody', oct=1, min=0.8, role='counter', gain_db=-2),
        dict(name='horn', instrument='horn', kind='harmony', min=0.7, role='counter', oct=-1, gain_db=-2),
        dict(name='harp', instrument='harp', kind='sparkle', lo=72, hi=96, min=0.3, role='arp', gain_db=-4),
        dict(name='drums', instrument='orchestral', kind='drums', min=0.6, role='drum', gain_db=-3),
        dict(name='timpani', instrument='timpani', kind='bass', bass='half', lo=38, hi=52, min=0.85, role='bass', gain_db=-6)]),
    'ambient': dict(room='cathedral', swing=0.5, humanize='rubato', tone='warm', lufs=-18, layers=[
        dict(name='pad', instrument='warm_pad', kind='pad', lo=48, hi=72, min=0.0, role='pad', gain_db=-1),
        dict(name='strings', instrument='slow_strings', kind='pad', lo=40, hi=67, min=0.35, role='pad', gain_db=-3),
        dict(name='lead', instrument='celesta', kind='melody', oct=1, min=0.2, role='melody', gain_db=-2),
        dict(name='piano', instrument='piano', kind='chords', tex_low='sparse', tex_mid='sparse', tex_hi='arp8', lo=55, hi=76, min=0.25, role='chord'),
        dict(name='sparkle', instrument='glockenspiel', kind='sparkle', lo=79, hi=100, min=0.3, role='arp', gain_db=-6)]),
    'acoustic': dict(room='chamber', swing=0.5, humanize='natural', tone='warm', lufs=-15, layers=[
        dict(name='guitar', instrument='nylon_guitar', kind='chords', tex_low='fingerpick', tex_mid='fingerpick', tex_hi='strum', lo=45, hi=69, min=0.0, role='chord'),
        dict(name='lead', instrument='flute', kind='melody', oct=1, min=0.2, role='melody', gain_db=-1),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='half', lo=33, hi=48, min=0.3, role='bass'),
        dict(name='strings', instrument='slow_strings', kind='pad', lo=45, hi=69, min=0.6, role='pad', gain_db=-4),
        dict(name='drums', instrument='brush', kind='drums', min=0.45, role='drum', gain_db=-5)]),
    'lofi': dict(room='room_warm', swing=0.58, humanize='loose', tone='warm', lufs=-14, groove='boom_bap', bpm=(68, 88), layers=[
        dict(name='rhodes', instrument='epiano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=50, hi=72, min=0.0, role='chord', color='seventh'),
        dict(name='lead', instrument='vibraphone', kind='melody', oct=0, min=0.25, role='melody', gain_db=-2),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='sync', lo=33, hi=48, min=0.2, role='bass'),
        dict(name='drums', instrument='808', kind='drums', min=0.15, role='drum', gain_db=-4)]),
    'orchestral': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-16, layers=[
        dict(name='strings', instrument='string_ensemble', kind='pad', lo=45, hi=72, min=0.0, role='pad'),
        dict(name='lead', instrument='violin', kind='melody', oct=0, min=0.15, role='melody', gain_db=-1),
        dict(name='woodwind', instrument='oboe', kind='harmony', min=0.4, role='counter', oct=0, gain_db=-3),
        dict(name='bass', instrument='double_bass', kind='bass', bass='half', lo=31, hi=48, min=0.25, role='bass'),
        dict(name='harp', instrument='harp', kind='chords', tex_low='sparse', tex_mid='arp8', tex_hi='arp16', lo=50, hi=84, min=0.2, role='arp', gain_db=-3),
        dict(name='horns', instrument='french_horn', kind='pad', lo=43, hi=65, min=0.65, role='pad', gain_db=-3),
        dict(name='drums', instrument='orchestral', kind='drums', min=0.6, role='drum', gain_db=-4),
        dict(name='timpani', instrument='timpani', kind='bass', bass='half', lo=38, hi=52, min=0.8, role='bass', gain_db=-6)]),
    'folk': dict(room='room_warm', swing=0.5, humanize='loose', tone='warm', lufs=-15, layers=[
        dict(name='guitar', instrument='acoustic_guitar', kind='chords', tex_low='fingerpick', tex_mid='strum', tex_hi='strum', lo=45, hi=69, min=0.0, role='chord'),
        dict(name='lead', instrument='fiddle', kind='melody', oct=0, min=0.2, role='melody', gain_db=-1),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='half', lo=33, hi=48, min=0.3, role='bass'),
        dict(name='whistle', instrument='flute', kind='harmony', min=0.65, role='counter', oct=1, gain_db=-4),
        dict(name='drums', instrument='brush', kind='drums', min=0.4, role='drum', gain_db=-5)]),
    'jazz': dict(room='room_warm', swing=0.62, humanize='loose', tone='warm', lufs=-15, layers=[
        dict(name='piano', instrument='piano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=48, hi=70, min=0.0, role='chord', color='seventh'),
        dict(name='lead', instrument='muted_trumpet', kind='melody', oct=0, min=0.2, role='melody', gain_db=-1),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='walk', lo=31, hi=48, min=0.0, role='bass'),
        dict(name='drums', instrument='brush', kind='drums', min=0.1, role='drum', gain_db=-5)]),
    'pop': dict(room='studio', swing=0.5, humanize='natural', tone='neutral', lufs=-14, groove='synthpop', bpm=(100, 124), layers=[
        dict(name='synth', instrument='polysynth', kind='chords', tex_low='arp8', tex_mid='pulse', tex_hi='pulse', lo=50, hi=74, min=0.0, role='chord', gain_db=-3),
        dict(name='piano', instrument='piano', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=48, hi=70, min=0.2, role='chord', gain_db=-3),
        dict(name='lead', instrument='saw_lead', kind='melody', oct=0, min=0.2, role='melody', gain_db=-4),
        dict(name='bass', instrument='synth_bass', kind='bass', bass='sync', lo=31, hi=46, min=0.1, role='bass'),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'dark': dict(room='cave', swing=0.5, humanize='rubato', tone='warm', lufs=-18, layers=[
        dict(name='drone', instrument='tremolo_strings', kind='pad', lo=36, hi=60, min=0.0, role='pad', gain_db=-2),
        dict(name='pulse', instrument='piano', kind='ostinato', lo=36, hi=55, min=0.25, role='chord', gain_db=-4),
        dict(name='bass', instrument='contrabass', kind='bass', bass='pedal', lo=28, hi=43, min=0.2, role='bass'),
        dict(name='lead', instrument='celesta', kind='melody', oct=1, min=0.35, role='melody', gain_db=-4),
        dict(name='sparkle', instrument='music_box', kind='sparkle', lo=72, hi=96, min=0.2, role='arp', gain_db=-5),
        dict(name='choir', instrument='voice_oohs', kind='pad', lo=48, hi=72, min=0.75, role='pad', gain_db=-4),
        dict(name='drums', instrument='orchestral', kind='drums', min=0.55, role='drum', gain_db=-3)]),
    'electronic': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-14, layers=[
        dict(name='pad', instrument='warm_pad', kind='pad', lo=48, hi=72, min=0.0, role='pad'),
        dict(name='arp', instrument='piano', kind='chords', tex_low='arp16', tex_mid='arp16', tex_hi='arp16', lo=55, hi=79, min=0.15, role='arp'),
        dict(name='lead', instrument='saw_lead', kind='melody', oct=0, min=0.3, role='melody', gain_db=-4),
        dict(name='bass', instrument='synth_bass', kind='bass', bass='pulse8', lo=31, hi=46, min=0.2, role='bass'),
        dict(name='drums', instrument='electronic', kind='drums', min=0.2, role='drum', gain_db=-3)]),
    'hiphop': dict(room='room_warm', swing=0.55, humanize='natural', tone='warm', lufs=-14, groove='boom_bap', bpm=(84, 100), layers=[
        dict(name='keys', instrument='epiano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=50, hi=72, min=0.0, role='chord', color='seventh'),
        dict(name='lead', instrument='vibraphone', kind='melody', oct=0, min=0.2, role='melody', gain_db=-3),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='sync', lo=33, hi=48, min=0.0, role='bass'),
        dict(name='strings', instrument='string_ensemble', kind='pad', lo=48, hi=72, min=0.5, role='pad', gain_db=-6),
        dict(name='drums', instrument='808', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'trap': dict(room='room', swing=0.5, humanize='tight', tone='bright', lufs=-14, groove='trap', bpm=(66, 80), layers=[
        dict(name='pad', instrument='warm_pad', kind='pad', lo=48, hi=72, min=0.0, role='pad', gain_db=-4),
        dict(name='bell', instrument='glockenspiel', kind='melody', oct=1, min=0.2, role='melody', gain_db=-4),
        dict(name='sub', instrument='synth_bass_2', kind='bass', bass='pedal', lo=24, hi=40, min=0.0, role='bass'),
        dict(name='sparkle', instrument='music_box', kind='sparkle', lo=76, hi=96, min=0.4, role='arp', gain_db=-8),
        dict(name='drums', instrument='808', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'dubstep': dict(room='hall', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='halftime', bpm=(138, 144), layers=[
        dict(name='pad', instrument='sweep_pad', kind='pad', lo=48, hi=72, min=0.0, role='pad', gain_db=-6),
        dict(name='wobble', instrument='synth_bass', kind='bass', bass='pulse8', lo=28, hi=45, min=0.0, role='bass', gain_db=-1),
        dict(name='lead', instrument='saw_lead', kind='melody', oct=0, min=0.45, role='melody', gain_db=-5),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'dnb': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='breakbeat', bpm=(166, 176), layers=[
        dict(name='pad', instrument='choir_aahs', kind='pad', lo=48, hi=72, min=0.0, role='pad', gain_db=-6),
        dict(name='keys', instrument='epiano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=52, hi=76, min=0.2, role='chord', gain_db=-3),
        dict(name='reese', instrument='synth_bass_2', kind='bass', bass='pulse8', lo=26, hi=42, min=0.0, role='bass'),
        dict(name='lead', instrument='voice_oohs', kind='melody', oct=0, min=0.35, role='melody', gain_db=-3),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-2)]),
    'reggae': dict(room='room_warm', swing=0.5, humanize='loose', tone='warm', lufs=-15, groove='one_drop', bpm=(66, 84), layers=[
        dict(name='skank', instrument='clean_guitar', kind='chords', tex_low='skank', tex_mid='skank', tex_hi='skank', lo=48, hi=69, min=0.0, role='chord', gain_db=-1),
        dict(name='organ', instrument='organ', kind='chords', tex_low='skank', tex_mid='skank', tex_hi='skank', lo=55, hi=76, min=0.3, role='chord', gain_db=-6),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='half', lo=31, hi=48, min=0.0, role='bass', gain_db=-1),
        dict(name='lead', instrument='harmonica', kind='melody', oct=0, min=0.25, role='melody', gain_db=-3),
        dict(name='drums', instrument='room', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'funk': dict(room='studio', swing=0.52, humanize='tight', tone='bright', lufs=-14, groove='funk', bpm=(96, 112), layers=[
        dict(name='clav', instrument='clavinet', kind='chords', tex_low='chop', tex_mid='chop', tex_hi='chop', lo=52, hi=76, min=0.0, role='chord', gain_db=-1),
        dict(name='gtr', instrument='muted_guitar', kind='chords', tex_low='chop', tex_mid='chop', tex_hi='chop', lo=45, hi=67, min=0.2, role='chord', gain_db=-3),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='sync', lo=30, hi=48, min=0.0, role='bass', gain_db=-1),
        dict(name='horns', instrument='brass_section', kind='harmony', min=0.4, role='counter', oct=0, gain_db=-5),
        dict(name='drums', instrument='standard', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'rock': dict(room='studio', swing=0.5, humanize='natural', tone='neutral', lufs=-13, groove='rock', bpm=(110, 140), layers=[
        dict(name='guitar', instrument='distortion_guitar', kind='chords', tex_low='strum', tex_mid='strum', tex_hi='strum', lo=40, hi=64, min=0.0, role='chord', gain_db=-3),
        dict(name='lead', instrument='overdrive_guitar', kind='melody', oct=0, min=0.3, role='melody', gain_db=-2),
        dict(name='bass', instrument='pick_bass', kind='bass', bass='pulse8', lo=28, hi=48, min=0.1, role='bass'),
        dict(name='organ', instrument='rock_organ', kind='pad', lo=52, hi=72, min=0.6, role='pad', gain_db=-8),
        dict(name='drums', instrument='power', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'metal': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='metal', bpm=(160, 180), layers=[
        dict(name='gtr', instrument='distortion_guitar', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=36, hi=58, min=0.0, role='chord', gain_db=-2),
        dict(name='gtr2', instrument='distortion_guitar', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=48, hi=70, min=0.2, role='chord', gain_db=-5),
        dict(name='bass', instrument='pick_bass', kind='bass', bass='pulse8', lo=24, hi=40, min=0.0, role='bass', gain_db=-1),
        dict(name='lead', instrument='distortion_guitar', kind='melody', oct=1, min=0.4, role='melody', gain_db=-3),
        dict(name='drums', instrument='power', kind='drums', min=0.0, role='drum', gain_db=-2)]),
    'rnb': dict(room='room_warm', swing=0.56, humanize='loose', tone='warm', lufs=-14, groove='rnb', bpm=(66, 92), layers=[
        dict(name='keys', instrument='epiano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=50, hi=72, min=0.0, role='chord', color='seventh'),
        dict(name='pad', instrument='slow_strings', kind='pad', lo=48, hi=72, min=0.5, role='pad', gain_db=-6),
        dict(name='lead', instrument='alto_sax', kind='melody', oct=0, min=0.25, role='melody', gain_db=-2),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='sync', lo=33, hi=48, min=0.1, role='bass'),
        dict(name='drums', instrument='808', kind='drums', min=0.0, role='drum', gain_db=-4)]),
    'bossa': dict(room='chamber', swing=0.5, humanize='natural', tone='warm', lufs=-15, groove='bossa', bpm=(112, 132), layers=[
        dict(name='guitar', instrument='nylon_guitar', kind='chords', tex_low='fingerpick', tex_mid='fingerpick', tex_hi='fingerpick', lo=45, hi=69, min=0.0, role='chord', color='seventh'),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='half', lo=33, hi=48, min=0.0, role='bass'),
        dict(name='lead', instrument='flute', kind='melody', oct=1, min=0.2, role='melody', gain_db=-2),
        dict(name='drums', instrument='brush', kind='drums', min=0.0, role='drum', gain_db=-6)]),
    'samba': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-14, groove='samba', bpm=(96, 116), layers=[
        dict(name='guitar', instrument='nylon_guitar', kind='chords', tex_low='strum', tex_mid='strum', tex_hi='strum', lo=45, hi=69, min=0.0, role='chord'),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='half', lo=33, hi=48, min=0.0, role='bass'),
        dict(name='lead', instrument='trumpet', kind='melody', oct=0, min=0.3, role='melody', gain_db=-3),
        dict(name='drums', instrument='standard', kind='drums', min=0.0, role='drum', gain_db=-4)]),
    'house': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-14, groove='four_floor', bpm=(118, 128), layers=[
        dict(name='pad', instrument='warm_pad', kind='pad', lo=48, hi=72, min=0.2, role='pad', gain_db=-6),
        dict(name='stabs', instrument='epiano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=52, hi=76, min=0.0, role='chord', gain_db=-2),
        dict(name='bass', instrument='synth_bass', kind='bass', bass='pulse8', lo=31, hi=46, min=0.0, role='bass'),
        dict(name='lead', instrument='saw_lead', kind='melody', oct=0, min=0.5, role='melody', gain_db=-7),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'techno': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-14, groove='four_floor', bpm=(124, 134), layers=[
        dict(name='pad', instrument='polysynth', kind='pad', lo=48, hi=72, min=0.3, role='pad', gain_db=-7),
        dict(name='stab', instrument='synth_bass', kind='ostinato', lo=36, hi=55, min=0.0, role='chord', gain_db=-3),
        dict(name='bass', instrument='synth_bass', kind='bass', bass='pulse8', lo=28, hi=40, min=0.2, role='bass'),
        dict(name='lead', instrument='square_lead', kind='melody', oct=0, min=0.5, role='melody', gain_db=-8),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'corporate': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='pop', bpm=(112, 126), layers=[
        dict(name='piano', instrument='piano', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=48, hi=72, min=0.0, role='chord'),
        dict(name='guitar', instrument='clean_guitar', kind='chords', tex_low='strum', tex_mid='strum', tex_hi='strum', lo=45, hi=67, min=0.3, role='chord', gain_db=-3),
        dict(name='lead', instrument='vibraphone', kind='melody', oct=0, min=0.2, role='melody', gain_db=-2),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='sync', lo=33, hi=48, min=0.15, role='bass'),
        dict(name='strings', instrument='string_ensemble', kind='pad', lo=48, hi=72, min=0.6, role='pad', gain_db=-6),
        dict(name='drums', instrument='standard', kind='drums', min=0.2, role='drum', gain_db=-4)]),
    'indie': dict(room='studio', swing=0.5, humanize='natural', tone='neutral', lufs=-14, groove='rock', bpm=(100, 140), layers=[
        dict(name='guitar', instrument='clean_guitar', kind='chords', tex_low='fingerpick', tex_mid='strum', tex_hi='strum', lo=45, hi=69, min=0.0, role='chord'),
        dict(name='lead', instrument='overdrive_guitar', kind='melody', oct=0, min=0.3, role='melody', gain_db=-3),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='pulse8', lo=31, hi=48, min=0.1, role='bass'),
        dict(name='keys', instrument='piano', kind='chords', tex_low='sparse', tex_mid='pulse', tex_hi='pulse', lo=52, hi=72, min=0.5, role='chord', gain_db=-6),
        dict(name='drums', instrument='room', kind='drums', min=0.1, role='drum', gain_db=-4)]),
    'futurebass': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='halftime', bpm=(140, 160), layers=[
        dict(name='chords', instrument='synth_strings', kind='chords', tex_low='block', tex_mid='half', tex_hi='half', lo=52, hi=76, min=0.0, role='chord', gain_db=-3),
        dict(name='pad', instrument='warm_pad', kind='pad', lo=48, hi=72, min=0.2, role='pad', gain_db=-6),
        dict(name='sub', instrument='synth_bass_2', kind='bass', bass='half', lo=26, hi=40, min=0.0, role='bass'),
        dict(name='vox', instrument='choir_aahs', kind='melody', oct=1, min=0.3, role='melody', gain_db=-3),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'halloween': dict(room='cave', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='heartbeat', bpm=(80, 110), layers=[
        dict(name='strings', instrument='tremolo_strings', kind='pad', lo=40, hi=64, min=0.0, role='pad', gain_db=-3),
        dict(name='box', instrument='music_box', kind='melody', oct=1, min=0.1, role='melody', gain_db=-1),
        dict(name='celesta', instrument='celesta', kind='sparkle', lo=72, hi=96, min=0.2, role='arp', gain_db=-5),
        dict(name='bass', instrument='contrabass', kind='bass', bass='pedal', lo=28, hi=43, min=0.2, role='bass'),
        dict(name='choir', instrument='voice_oohs', kind='pad', lo=48, hi=72, min=0.7, role='pad', gain_db=-5),
        dict(name='drums', instrument='orchestral', kind='drums', min=0.5, role='drum', gain_db=-4)]),
    'trance': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='four_floor', bpm=(134, 142), layers=[
        dict(name='pad', instrument='warm_pad', kind='pad', lo=48, hi=72, min=0.0, role='pad', gain_db=-5),
        dict(name='pluck', instrument='polysynth', kind='chords', tex_low='arp16', tex_mid='arp16', tex_hi='arp16', lo=55, hi=79, min=0.1, role='arp', gain_db=-3),
        dict(name='bass', instrument='synth_bass', kind='bass', bass='pulse8', lo=28, hi=43, min=0.2, role='bass'),
        dict(name='lead', instrument='saw_lead', kind='melody', oct=1, min=0.4, role='melody', gain_db=-5),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'hardstyle': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='four_floor', bpm=(150, 165), layers=[
        dict(name='stab', instrument='synth_brass', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=48, hi=72, min=0.0, role='chord', gain_db=-3),
        dict(name='gtr', instrument='distortion_guitar', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=40, hi=60, min=0.2, role='chord', gain_db=-5),
        dict(name='bass', instrument='synth_bass', kind='bass', bass='pulse8', lo=26, hi=40, min=0.0, role='bass', gain_db=-1),
        dict(name='lead', instrument='sweep_pad', kind='melody', oct=1, min=0.4, role='melody', gain_db=-5),
        dict(name='drums', instrument='power', kind='drums', min=0.0, role='drum', gain_db=-2)]),
    'synthpop': dict(room='plate', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='synthpop', bpm=(100, 125), layers=[
        dict(name='pad', instrument='polysynth', kind='pad', lo=48, hi=72, min=0.0, role='pad', gain_db=-5),
        dict(name='arp', instrument='epiano', kind='chords', tex_low='arp8', tex_mid='arp16', tex_hi='arp16', lo=52, hi=76, min=0.2, role='arp', gain_db=-3),
        dict(name='bass', instrument='synth_bass', kind='bass', bass='pulse8', lo=31, hi=46, min=0.1, role='bass'),
        dict(name='lead', instrument='saw_lead', kind='melody', oct=0, min=0.3, role='melody', gain_db=-4),
        dict(name='drums', instrument='electronic', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'deep_house': dict(room='room_warm', swing=0.52, humanize='natural', tone='warm', lufs=-15, groove='four_floor', bpm=(118, 124), layers=[
        dict(name='pad', instrument='warm_pad', kind='pad', lo=48, hi=72, min=0.0, role='pad', gain_db=-5),
        dict(name='chords', instrument='epiano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=50, hi=74, min=0.0, role='chord', color='seventh', gain_db=-2),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='sync', lo=31, hi=46, min=0.1, role='bass'),
        dict(name='lead', instrument='vibraphone', kind='melody', oct=0, min=0.45, role='melody', gain_db=-6),
        dict(name='drums', instrument='room', kind='drums', min=0.0, role='drum', gain_db=-4)]),
    'darksynth': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-14, groove='halftime', bpm=(100, 125), layers=[
        dict(name='pad', instrument='sweep_pad', kind='pad', lo=40, hi=64, min=0.0, role='pad', gain_db=-5),
        dict(name='arp', instrument='saw_lead', kind='ostinato', lo=40, hi=60, min=0.2, role='chord', gain_db=-5),
        dict(name='bass', instrument='synth_bass_2', kind='bass', bass='pulse8', lo=26, hi=42, min=0.0, role='bass'),
        dict(name='lead', instrument='synth_brass', kind='melody', oct=0, min=0.4, role='melody', gain_db=-4),
        dict(name='drums', instrument='electronic', kind='drums', min=0.1, role='drum', gain_db=-3)]),
    'motown': dict(room='room_warm', swing=0.52, humanize='natural', tone='warm', lufs=-14, groove='motown', bpm=(108, 128), layers=[
        dict(name='piano', instrument='piano', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=48, hi=70, min=0.0, role='chord'),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='pulse8', lo=31, hi=48, min=0.0, role='bass'),
        dict(name='lead', instrument='trumpet', kind='melody', oct=0, min=0.25, role='melody', gain_db=-3),
        dict(name='strings', instrument='string_ensemble', kind='pad', lo=48, hi=72, min=0.5, role='pad', gain_db=-5),
        dict(name='drums', instrument='standard', kind='drums', min=0.0, role='drum', gain_db=-3)]),
    'reggaeton': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-14, groove='dembow', bpm=(90, 98), layers=[
        dict(name='pluck', instrument='muted_guitar', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=48, hi=72, min=0.0, role='chord', gain_db=-1),
        dict(name='bass', instrument='synth_bass_2', kind='bass', bass='sync', lo=24, hi=40, min=0.0, role='bass', gain_db=0),
        dict(name='lead', instrument='synth_voice', kind='melody', oct=0, min=0.3, role='melody', gain_db=-3),
        dict(name='bell', instrument='glockenspiel', kind='sparkle', lo=79, hi=100, min=0.4, role='arp', gain_db=-7),
        dict(name='drums', instrument='808', kind='drums', min=0.0, role='drum', gain_db=0)]),
    'cumbia': dict(room='studio', swing=0.5, humanize='loose', tone='warm', lufs=-14, groove='cumbia', bpm=(84, 100), layers=[
        dict(name='accordion', instrument='accordion', kind='melody', oct=0, min=0.1, role='melody', gain_db=-2),
        dict(name='guitar', instrument='nylon_guitar', kind='chords', tex_low='strum', tex_mid='strum', tex_hi='strum', lo=45, hi=69, min=0.0, role='chord', gain_db=-2),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='half', lo=31, hi=48, min=0.0, role='bass'),
        dict(name='drums', instrument='standard', kind='drums', min=0.0, role='drum', gain_db=-5)]),
    'salsa': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='salsa', bpm=(170, 200), layers=[
        dict(name='piano', instrument='piano', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=48, hi=72, min=0.0, role='chord', gain_db=-1),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='sync', lo=31, hi=48, min=0.0, role='bass'),
        dict(name='brass', instrument='trumpet', kind='melody', oct=0, min=0.2, role='melody', gain_db=-2),
        dict(name='horns', instrument='trombone', kind='harmony', min=0.5, role='counter', oct=-1, gain_db=-4),
        dict(name='drums', instrument='standard', kind='drums', min=0.0, role='drum', gain_db=-5)]),
    'forro': dict(room='studio', swing=0.5, humanize='loose', tone='warm', lufs=-14, groove='forro', bpm=(108, 130), layers=[
        dict(name='accordion', instrument='accordion', kind='melody', oct=0, min=0.1, role='melody', gain_db=-2),
        dict(name='guitar', instrument='acoustic_guitar', kind='chords', tex_low='strum', tex_mid='strum', tex_hi='strum', lo=45, hi=69, min=0.0, role='chord', gain_db=-3),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='half', lo=31, hi=48, min=0.0, role='bass'),
        dict(name='drums', instrument='standard', kind='drums', min=0.0, role='drum', gain_db=-5)]),
    'afrobeat': dict(room='studio', swing=0.54, humanize='loose', tone='warm', lufs=-14, groove='afrobeat', bpm=(98, 112), layers=[
        dict(name='guitar', instrument='clean_guitar', kind='chords', tex_low='comp', tex_mid='comp', tex_hi='comp', lo=48, hi=72, min=0.0, role='chord'),
        dict(name='bass', instrument='finger_bass', kind='bass', bass='sync', lo=31, hi=48, min=0.0, role='bass'),
        dict(name='lead', instrument='marimba', kind='melody', oct=0, min=0.2, role='melody', gain_db=-2),
        dict(name='horns', instrument='brass_section', kind='harmony', min=0.5, role='counter', oct=0, gain_db=-5),
        dict(name='drums', instrument='standard', kind='drums', min=0.0, role='drum', gain_db=-4)]),
    'percussion': dict(room='large_hall', swing=0.5, humanize='tight', tone='warm', lufs=-14, groove='percussion_drive', bpm=(92, 120), layers=[
        dict(name='drums', instrument='orchestral', kind='drums', min=0.0, role='drum', gain_db=-1),
        dict(name='timpani', instrument='timpani', kind='bass', bass='half', lo=38, hi=52, min=0.0, role='bass', gain_db=-3),
        dict(name='strings', instrument='tremolo_strings', kind='pad', lo=40, hi=64, min=0.3, role='pad', gain_db=-5),
        dict(name='brass', instrument='brass_section', kind='pad', lo=43, hi=65, min=0.5, role='pad', gain_db=-5),
        dict(name='lead', instrument='trumpet', kind='melody', oct=0, min=0.6, role='melody', gain_db=-4)]),
    'comedy': dict(room='room_warm', swing=0.5, humanize='loose', tone='neutral', lufs=-15, groove='march', bpm=(110, 130), layers=[
        dict(name='pizz', instrument='pizzicato_strings', kind='chords', tex_low='pulse', tex_mid='pulse', tex_hi='pulse', lo=48, hi=72, min=0.0, role='chord'),
        dict(name='lead', instrument='bassoon', kind='melody', oct=0, min=0.1, role='melody', gain_db=-2),
        dict(name='tuba', instrument='tuba', kind='bass', bass='half', lo=28, hi=46, min=0.0, role='bass'),
        dict(name='xylo', instrument='xylophone', kind='sparkle', lo=72, hi=96, min=0.3, role='arp', gain_db=-6),
        dict(name='drums', instrument='standard', kind='drums', min=0.2, role='drum', gain_db=-6)]),
    'kids': dict(room='room_warm', swing=0.5, humanize='natural', tone='bright', lufs=-15, groove='shaker', bpm=(100, 118), layers=[
        dict(name='uke', instrument='nylon_guitar', kind='chords', tex_low='strum', tex_mid='strum', tex_hi='strum', lo=55, hi=76, min=0.0, role='chord', gain_db=-1),
        dict(name='lead', instrument='xylophone', kind='melody', oct=1, min=0.1, role='melody', gain_db=-2),
        dict(name='bass', instrument='acoustic_bass', kind='bass', bass='half', lo=33, hi=48, min=0.1, role='bass'),
        dict(name='glock', instrument='glockenspiel', kind='sparkle', lo=79, hi=100, min=0.3, role='arp', gain_db=-6),
        dict(name='drums', instrument='brush', kind='drums', min=0.3, role='drum', gain_db=-6)]),
}
GENRE_ALIASES = {'solo_piano': 'piano', 'film': 'cinematic', 'score': 'cinematic', 'orchestra': 'orchestral',
                 'guitar': 'acoustic', 'chill': 'lofi', 'lo-fi': 'lofi', 'jazzy': 'jazz', 'horror': 'dark',
                 'ethereal': 'ambient', 'edm': 'electronic', 'synth': 'electronic', 'country': 'folk',
                 'hip-hop': 'hiphop', 'hip_hop': 'hiphop', 'rap': 'hiphop', 'boom_bap': 'hiphop', 'hip': 'hiphop',
                 'halftime': 'dubstep', 'brostep': 'dubstep', 'drum_and_bass': 'dnb', 'drum_n_bass': 'dnb',
                 'd&b': 'dnb', 'jungle': 'dnb', 'ska': 'reggae', 'dub': 'reggae', 'soul': 'rnb', 'r&b': 'rnb',
                 'neo_soul': 'rnb', 'bossa_nova': 'bossa', 'bossanova': 'bossa', 'heavy_metal': 'metal',
                 'punk': 'rock', 'hard_rock': 'rock', 'disco': 'funk', 'deep_house': 'house', 'tech_house': 'house'}
# labels from Pixabay's genre pages and playlists (and common names) -> the genre implemented here
GENRE_ALIASES.update({
    'upbeat': 'pop', 'beats': 'hiphop', 'alternative_hip_hop': 'hiphop', 'lo_fi': 'lofi', 'chill_beats': 'lofi',
    'lofi_hip_hop': 'lofi', 'lofi_chillout': 'lofi', 'lofi_study': 'lofi', 'future_bass': 'futurebass',
    'scary_childrens_tunes': 'halloween', 'spooky': 'halloween', 'childrens': 'kids', 'children': 'kids',
    'childrens_music': 'kids', 'kids_music': 'kids', 'techno_&_trance': 'techno', 'techno_and_trance': 'techno',
    'psytrance': 'trance', 'psystyle': 'trance', 'gabber': 'hardstyle', 'jumpstyle': 'hardstyle',
    'rawstyle': 'hardstyle', 'hard_dance': 'hardstyle', 'synth_pop': 'synthpop', 'synthwave': 'synthpop',
    'new_wave': 'synthpop', 'retrowave': 'synthpop', 'soft_house': 'deep_house', 'chill_house': 'deep_house',
    'tropical_house': 'deep_house', 'cyberpunk': 'darksynth', 'dark_synth': 'darksynth', 'electro': 'electronic',
    'glitch_hop': 'electronic', 'dance': 'house', 'dance_party': 'house', 'motown_&_old_school_rnb': 'motown',
    'old_school_rnb': 'motown', 'urban_latin': 'reggaeton', 'latin': 'reggaeton', 'dembow': 'reggaeton',
    'brazilian': 'samba', 'brazil': 'samba', 'carnival': 'samba', 'afrobeats': 'afrobeat', 'african': 'afrobeat',
    'africa': 'afrobeat', 'world': 'folk', 'powerful_percussion': 'percussion', 'taiko': 'percussion',
    'bloopers': 'comedy', 'funny': 'comedy', 'quirky': 'comedy', 'cartoon': 'comedy', 'silent_movie': 'comedy',
    'alternative': 'indie', 'indie_rock': 'indie', 'emo': 'indie', 'uplifting_indie_rock': 'indie',
    'commercial': 'corporate', 'advertising': 'corporate', 'vlog': 'corporate', 'tutorial': 'corporate',
    'tutorials': 'corporate', 'background': 'corporate', 'business': 'corporate', 'presentation': 'corporate',
    'sport': 'rock', 'thrash': 'metal', 'thrash_metal': 'metal', 'doom': 'metal', 'doom_metal': 'metal',
    'power_metal': 'metal', 'nu_metal': 'metal', 'modern_classical': 'piano', 'classical': 'orchestral',
    'epic_classical': 'cinematic', 'adventure': 'orchestral', 'main_title': 'cinematic', 'trailer': 'cinematic',
    'mystery': 'dark', 'build_up_scenes': 'cinematic', 'build_up': 'cinematic', 'zen': 'ambient',
    'meditation': 'ambient', 'yoga': 'ambient', 'sleep': 'ambient', 'nature': 'ambient', 'cosmos': 'ambient',
})
GENRES.update(world.GENRES)                       # India, Arabic, Turkish, Persian, East Asia, Rio and Brazil, Latin, Africa, Europe, Americas
GENRE_ALIASES.update(world.GENRE_ALIASES)
SCENE_WORDS = {  # free-text scene -> emotion hints (used only when brief has no emotion)
    'rain': 'melancholy', 'window': 'melancholy', 'night': 'dreamy', 'sunrise': 'hopeful', 'morning': 'hopeful',
    'forest': 'wonder', 'ocean': 'calm', 'sea': 'calm', 'beach': 'calm', 'city': 'focused', 'chase': 'tense',
    'dark': 'scary', 'battle': 'dark_epic', 'wedding': 'tender', 'funeral': 'grief', 'graduation': 'triumphant',
    'child': 'playful', 'kids': 'playful', 'cafe': 'lofi', 'coffee': 'nostalgic', 'memories': 'nostalgic',
    'victory': 'triumphant', 'space': 'wonder', 'robot': 'focused', 'tech': 'focused', 'startup': 'energetic',
}


# ------------------------------------------------------------------------------------------------
# epic: a DYNAMIC mix, not a fixed stack. The brief's "instruments" (or, with a genre, that genre's own
# sounds) fill the roles: a pluck/keys anchor, a bass, a lead, a pad, a lift for the climax, and extras.
# A culture (a world genre) keeps Western orchestral sounds out unless the brief says orchestral /
# cinematic / hollywood. With no instruments and no genre, the default is a full Western epic mix.
# ------------------------------------------------------------------------------------------------
EPIC_EMOTIONS = ('epic', 'dark_epic')
WESTERN_ORCH = {'french_horn', 'horn', 'trumpet', 'fast_strings', 'timpani', 'orchestral', 'brass_section'}
EPIC_DEFAULT = ['piano', 'contrabass', 'violin', 'french_horn', 'choir_aahs', 'trumpet']
PLUCK_ANCHOR = {'piano', 'epiano', 'harp', 'kora', 'sitar', 'nylon_guitar', 'acoustic_guitar', 'koto', 'guzheng', 'balafon',
                'marimba', 'kalimba', 'vibraphone', 'clean_guitar', 'steel_guitar', 'bouzouki', 'saz', 'oud', 'santoor', 'dulcimer'}
BASS_NAMES = {'contrabass', 'double_bass', 'cello', 'acoustic_bass', 'finger_bass', 'tuba', 'synth_bass', 'pick_bass',
              'guitarron', 'guembri'}


def epic_recipe(brief, G, g_name):
    text = json.dumps(brief).lower()
    culture = g_name if g_name in world.GENRES else None
    if brief.get('instruments'):
        names = [str(x).lower().strip().replace(' ', '_') for x in brief['instruments']]
    elif brief.get('genre') and g_name not in ('cinematic', 'orchestral'):
        names = [l['instrument'] for l in G['layers'] if l['kind'] != 'drums']
    else:
        names = list(EPIC_DEFAULT)
    if culture and not re.search(r'orchestra|cinematic|hollywood', text):      # the culture guardrail
        names = [n for n in names if n not in WESTERN_ORCH]
    used = set()

    def take(pred):
        for n in names:
            if n not in used and pred(n):
                used.add(n)
                return n
        return None

    anchor = take(lambda n: n in PLUCK_ANCHOR)
    bass = take(lambda n: n in BASS_NAMES)
    lead, pad, lift = take(lambda n: True), take(lambda n: True), take(lambda n: True)
    extra = [n for n in names if n not in used]
    layers = []
    if anchor:
        layers.append(dict(name='anchor', instrument=anchor, kind='chords', tex_low='sparse', tex_mid='arp8', tex_hi='arp16',
                           lo=48, hi=72, min=0.0, role='chord'))
    if bass:
        layers.append(dict(name='bass', instrument=bass, kind='bass', bass='half' if culture else 'pedal', lo=28, hi=48,
                           min=0.0, role='bass', gain_db=-1))
    if lead:
        layers.append(dict(name='lead', instrument=lead, kind='melody', oct=0, min=0.2, role='melody', gain_db=-2))
    if pad:
        layers.append(dict(name='pad', instrument=pad, kind='pad', lo=45, hi=72, min=0.15, role='pad', gain_db=-3))
    if lift:
        layers.append(dict(name='lift', instrument=lift, kind='harmony', min=0.8, role='counter', oct=0, gain_db=-3))
    for i, n in enumerate(extra):
        layers.append(dict(name=f'extra{i}', instrument=n, kind='pad', lo=48, hi=72, min=0.6, role='pad', gain_db=-6))
    kit = [l for l in G['layers'] if l['kind'] == 'drums']
    if culture:
        layers += kit[:1]                                    # the culture's own percussion
    else:
        layers += [dict(name='drums', instrument='orchestral', kind='drums', min=0.0, role='drum', gain_db=-3),
                   dict(name='timpani', instrument='timpani', kind='bass', bass='half', lo=38, hi=52, min=0.85, role='bass', gain_db=-6)]
    return dict(G, layers=layers, groove=G.get('groove') if culture else 'taiko')


def resolve_emotion(brief, rng=None):
    """The user's own words -> one emotion. Reads emotion, scene, style and notes, takes the first word it knows,
    and states in meta['mood_notes'] when it had to fall back (no silent defaults)."""
    e = str(brief.get('emotion', '')).lower().strip().replace(' ', '_')
    if e in EMOTIONS:
        return e, True, []
    if e in EMOTION_ALIASES:
        return EMOTION_ALIASES[e], True, []
    for w in re.findall(r'[a-z]+', (e + ' ' + str(brief.get('scene', ''))).lower()):
        if w in EMOTIONS:
            return w, True, []
        if w in EMOTION_ALIASES:
            return EMOTION_ALIASES[w], True, []
        if w in SCENE_WORDS:
            return SCENE_WORDS[w], True, []
    return 'focused', False, []


def read_mods(brief):
    """The words that are not emotions but do change the arrangement: speed, room, density. 'slow reverb mix'
    is not a mood, it is calm + 0.86 tempo + a large hall; this turns it into those settings."""
    text = ' '.join(str(brief.get(k, '')) for k in ('emotion', 'scene', 'style', 'notes', 'note')).lower()
    words = re.findall(r'[a-z]+', text)
    energy, bpm, room, wet, dens, notes = 0.0, 1.0, None, 1.0, 0, []
    for w in words:
        if w in MOOD_MODS:
            de, tb = MOOD_MODS[w]
            energy, bpm = energy + de, bpm * tb
            notes.append(f"'{w}': tempo x{tb:g}, energy {de:+.2f}")
        elif w in WET_WORDS and room is None:
            room, wet = 'large_hall', 1.5
            notes.append(f"'{w}': large hall, reverb return 1.5")
        elif w in DRY_WORDS and room is None:
            room, wet = 'dry', 0.6
            notes.append(f"'{w}': dry room")
        elif w in DENSE_WORDS:
            dens = DENSE_WORDS[w]
            notes.append(f"'{w}': {'fewer' if dens < 0 else 'more'} layers")
    if brief.get('energy') is not None:                 # an explicit number always wins over a word
        energy = float(brief['energy']) - 0.5
        notes.append(f"energy={float(brief['energy']):g}")
    if brief.get('space'):
        room = str(brief['space'])
        wet = 1.5 if room in ('large_hall', 'cathedral', 'cave') else (0.6 if room == 'dry' else 1.0)
        notes.append(f"space={room}")
    speed = float(brief.get('tempo_scale', 1.0))
    return dict(energy=energy, bpm=bpm * speed, room=room, wet=wet, density=dens, notes=notes)


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------

def seventh(sym):
    """triad symbol -> seventh chord symbol (jazz/lofi colour)"""
    if re.search(r'[0-9]|sus|dim|aug', sym):
        return sym
    m = re.match(r'^([b#]?)([ivIV]+)$', sym)
    if not m:
        return sym
    num = m.group(2)
    if num.islower():
        return sym + '7'
    return sym + ('7' if num in ('V',) or sym == 'bVII' else 'maj7')


def spice(sym, tension, rng):
    """add dissonance to a chord symbol as tension rises (b9 / dim / sus / #11)"""
    if tension < 0.5 or re.search(r'[0-9]', sym):
        return sym
    r = rng.random()
    if r < (tension - 0.4) * 0.5:
        return sym + ('b9' if sym.islower() or sym[0] in 'iv' else '')
    return sym


def fit_tempo_and_bars(duration, bpm_range, bb, bpm=None, mid=None):
    mid = mid or sum(bpm_range) / 2
    if bpm:
        bars = max(2, int(round(duration * bpm / 60.0 / bb / 2.0)) * 2)
        if bars >= 8:
            bars = max(8, int(round(bars / 4.0)) * 4)
        return int(bpm), bars
    best = None
    short = duration < 14
    for b in range(int(bpm_range[0]), int(bpm_range[1]) + 1):
        for bars in range(2 if short else 8, 161, 2 if short else 4):
            err = abs(bars * bb * 60.0 / b - duration) + abs(b - mid) * 0.03
            if best is None or err < best[0]:
                best = (err, b, bars)
    return best[1], best[2]


HIGH_LEADS = {'flute', 'violin', 'oboe', 'fiddle', 'celesta', 'vibraphone', 'saw_lead', 'muted_trumpet', 'piccolo', 'pan_flute',
              'recorder', 'ocarina', 'whistle', 'bansuri', 'dizi', 'quena', 'shakuhachi', 'ney'}     # leads that sing high; the ambient genre skips the clamp


def _base_names(inst):
    """The instrument's own name plus the General MIDI sound or world name it is built on (preset `gm` / `instrument`)."""
    name = str(inst).lower().replace(' ', '_')
    out = [name]
    cfg = presets.find_instrument(name) or {}
    for k in ('gm', 'instrument'):
        if isinstance(cfg.get(k), str):
            out.append(cfg[k].lower().replace(' ', '_'))
    out += [world.INSTRUMENTS[n] for n in list(out) if isinstance(world.INSTRUMENTS.get(n), str)]
    return out


def vary_bar(notes, kind, bar, bb, amt, rng):
    """Break the one-bar template so the bars are not clones: the later bars of a 4-bar phrase change more.
    The downbeat stays; other hits can drop, shift a 16th, swing in velocity or gain a ghost / pickup note.
    amt 0 = the old behaviour (every bar identical)."""
    if amt <= 0 or not notes:
        return notes
    pos = bar % 4
    heat = amt * (0.35 + 0.22 * pos)
    swell = 1.0 + amt * (-0.06 + 0.04 * pos)              # each phrase breathes: 0.94 -> 1.06
    decided, out = {}, []
    for n in notes:
        k = (round(n['t'], 3), n['p'] if kind == 'drums' else None)
        if k not in decided:
            shift = 0.0
            main_beat = abs(n['t'] - round(n['t'])) < 1e-6      # a whole beat anchors the groove: never moved or dropped
            if n['t'] > 1e-6:
                u = rng.random()                                # drawn for every note, so the sequence does not depend on the beat
                if main_beat:
                    pass
                elif u < heat * 0.35:
                    shift = None                          # drop this hit
                elif u < heat * 0.35 + heat * 0.4:
                    shift = float(rng.choice([-0.25, 0.25]))
            w = float(rng.random())
            vm = 0.9 + 0.2 * w if main_beat else (1 - 0.28 * amt) + w * 0.40 * amt     # main beats: velocity within +-10%
            decided[k] = (shift, vm)
        shift, vm = decided[k]
        if shift is None:
            continue
        t = n['t'] + shift
        if 0 <= t < bb:
            out.append(dict(n, t=t, v=float(np.clip(n['v'] * vm * swell, 0.04, 1.0))))
    if not out:
        return notes
    if kind == 'drums' and rng.random() < heat * 0.7:          # ghost note on a free 16th
        used = {round(n['t'], 2) for n in out}
        free = [t for t in np.arange(0.25, bb, 0.5) if round(float(t), 2) not in used]
        if free:
            name = 'snare' if any(n['p'] == 'snare' for n in out) else out[-1]['p']
            out.append(dict(t=float(rng.choice(free)), d=0.08, p=name, v=0.2 + 0.08 * float(rng.random())))
    elif kind == 'bass' and rng.random() < heat * 0.45:        # pickup into the next bar
        last = max(out, key=lambda n: n['t'])
        if last['t'] < bb - 0.75:
            out.append(dict(last, t=bb - 0.5, d=0.4, v=last['v'] * 0.7))
    return sorted(out, key=lambda n: n['t'])


def resample(points, n):
    xs = np.linspace(0, 1, len(points))
    return np.interp(np.linspace(0, 1, n), xs, points)


def intensity_per_bar(arc, n_bars, base, hit_shifts, bpm, bb):
    n_ph = max(1, int(np.ceil(n_bars / 4)))
    curve = ARCS.get(arc, ARCS['steady'])
    ph = resample(curve, n_ph)
    per_bar = np.repeat(ph, 4)[:n_bars]
    if n_bars % 4:
        per_bar = np.concatenate([per_bar, np.full(n_bars - len(per_bar), ph[-1])])
    # smooth between phrases
    k = np.ones(3) / 3
    per_bar = np.convolve(np.pad(per_bar, (1, 1), mode='edge'), k, mode='valid')
    per_bar = np.clip(per_bar * (0.55 + 0.9 * base), 0.02, 1.0)
    for h in hit_shifts:
        b = int(round(h['t'] * bpm / 60.0 / bb))
        if h['type'] == 'shift':
            per_bar[b:] = np.clip(per_bar[b:] + 0.25, 0, 1)
        elif h['type'] == 'drop':
            per_bar[b:] = np.clip(per_bar[b:] - 0.3, 0.02, 1)
    return per_bar


# ------------------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------------------

def compose(brief):
    fp = None
    if brief.get('fusion'):                            # any mix of cultures: scripts/fusion.py picks scale, tempo, instruments
        import fusion
        fp = fusion.plan(brief['fusion'], key=brief.get('key') or 'D', style=brief.get('style'))
        brief = fusion.apply(brief, fp)
    seed = int(brief.get('seed', 7))
    rng = np.random.default_rng(seed)
    mods = read_mods(brief)
    emo, mood_known, _ = resolve_emotion(brief)
    if not mood_known:
        emo = mood_from_mods(mods) if mods['notes'] else 'focused'
    mood_notes = list(mods['notes'])
    if not mood_known and not mods['notes']:
        mood_notes.append("no mood word recognised: used 'focused' (neutral, mid-tempo). Name the feel to change it")
    if fp:
        mood_notes += fp['warnings']   # the cultures' own scale/tempo conflicts, not just the mood-vs-genre one below
    E = EMOTIONS[emo]
    g_name = str(brief.get('genre') or E['genres'][0]).lower().replace(' ', '_')
    g_name = g_name if g_name in GENRES else GENRE_ALIASES.get(g_name, g_name)     # a real genre name beats an alias
    G = copy.deepcopy(GENRES[g_name if g_name in GENRES else E['genres'][0]])
    if emo in EPIC_EMOTIONS:
        G = epic_recipe(brief, G, g_name)
    if fp:
        import fusion
        G = fusion.group_G(fp, G)                       # a fusion's instruments override the genre's layers
    voiceover = bool(brief.get('voiceover'))
    loop = bool(brief.get('loop'))
    # the mood's own dynamic band is the neutral energy. calm starts at 0.40, epic at 0.68; 0.5 is a compromise
    # that made every mood play as hard as the next one.
    intensity = float(brief.get('intensity', (E['dyn'][0] + E['dyn'][1]) / 2 + mods['energy']))
    if voiceover:
        intensity = min(intensity, 0.45)
    tension = float(brief['tension']) if brief.get('tension') is not None else E['tension']

    # key + mode
    mode = brief.get('mode') or G.get('mode') or E['modes'][int(rng.integers(len(E['modes'])))]
    if mode not in MODES:
        mode = E['modes'][0]
    tonic = brief.get('key') or E['keys'][int(rng.integers(len(E['keys'])))]
    tonic = tonic.replace('♭', 'b').replace('♯', '#')
    if len(tonic) > 1 and tonic[1:] in ('m', 'min', 'minor'):
        tonic, mode = tonic[0], 'aeolian'
    key = Key(tonic, mode, octave=4)
    bb = int(brief.get('beats_per_bar', G.get('bb', 3 if brief.get('ts') == 3 else 4)))
    bpm_lo, bpm_hi = E['bpm']
    if G.get('bpm') and brief.get('bpm') is None:      # genre tempo range, kept inside the mood's range when they overlap
        glo, ghi = G['bpm']
        lo2, hi2 = max(bpm_lo, glo), min(bpm_hi, ghi)
        if lo2 <= hi2:
            bpm_lo, bpm_hi = lo2, hi2
        elif mood_known:
            # They do not overlap ("calm house", "motivational corporate"). Tempo is the second-strongest mood cue,
            # so the mood wins 2:1 over the genre instead of the genre taking the whole range (that is how every
            # request came out at 120+ BPM).
            mid = (2 * (bpm_lo + bpm_hi) / 2 + (glo + ghi) / 2) / 3
            bpm_lo, bpm_hi = mid - 5, mid + 5
            mood_notes.append(f"mood tempo {E['bpm']} and genre tempo {(glo, ghi)} do not overlap; using {mid:.0f} BPM")
        else:
            bpm_lo, bpm_hi = glo, ghi                     # genre-driven request: the genre owns the tempo
    elif brief.get('bpm') is None and brief.get('bpm_hint'):
        # a fusion plans a tempo from the cultures' overlap; that is a window, so the mood can still pull it
        h = float(brief['bpm_hint'])
        lo2, hi2 = max(bpm_lo, h - 7), min(bpm_hi, h + 7)
        if lo2 <= hi2:
            bpm_lo, bpm_hi = lo2, hi2
        else:
            mid = (2 * (bpm_lo + bpm_hi) / 2 + h) / 3
            bpm_lo, bpm_hi = mid - 5, mid + 5
            mood_notes.append(f"mood tempo {E['bpm']} and fusion tempo ~{h:.0f} do not overlap; using {mid:.0f} BPM")
    if brief.get('bpm') is None and mods['bpm'] != 1.0:
        bpm_lo, bpm_hi = np.clip([bpm_lo * mods['bpm'], bpm_hi * mods['bpm']], 40, 200)
    bpm, n_bars = fit_tempo_and_bars(float(brief.get('duration_s', 45)), (bpm_lo, bpm_hi), bb, brief.get('bpm'))
    if voiceover:
        bpm = min(bpm, 100)

    # progression: choose per mode (fallback to nearest parent)
    plist = E['prog'].get(mode) or E['prog'].get('major' if key.scale[2] == 4 else 'aeolian') or list(E['prog'].values())[0]
    prog_text = brief.get('progression') or G.get('prog') or plist[int(rng.integers(len(plist)))]
    syms = re.split(r'[-\s,]+', prog_text.strip())
    if any(L.get('color') == 'seventh' for L in G['layers']):
        syms = [seventh(s) for s in syms]
    syms = [spice(s, tension, rng) for s in syms]
    hr = E['hr']
    chords_by_bar = []
    ci = 0
    while len(chords_by_bar) < n_bars:
        ch = key.chord(syms[ci % len(syms)])
        for _ in range(int(hr)):
            chords_by_bar.append(ch)
        ci += 1
    chords_by_bar = chords_by_bar[:n_bars]
    # cadence: dominant before each 8-bar group end, tonic on the last bar
    if n_bars >= 8 and not loop:
        for b in range(7, n_bars - 1, 8):
            chords_by_bar[b] = key.chord('V' if mode in ('major', 'ionian', 'mixolydian', 'lydian') else 'V')
        chords_by_bar[-1] = key.chord('I' if key.scale[2] == 4 else 'i')
        if n_bars >= 4:
            chords_by_bar[-2] = key.chord('IV' if key.scale[2] == 4 else 'iv') if rng.random() < .5 else chords_by_bar[-2]

    # arc / intensity
    hits = list(brief.get('hit_points', []))
    arc = brief.get('arc') or E['arc']
    inten = intensity_per_bar(arc, n_bars, intensity, [h for h in hits if h['type'] in ('shift', 'drop')], bpm, bb)
    if float(brief.get('variation', 0.45)) > 0 and n_bars >= 8:     # widen the swing so a 'steady' arc still breathes
        v_amt = float(brief.get('variation', 0.45))
        inten = inten.mean() + (inten - inten.mean()) * (1 + 2.0 * v_amt)
        if not loop:
            inten[:4] *= 0.8                                          # an intro that builds
            inten = inten + 0.5 * v_amt * np.sin(np.linspace(0, np.pi, n_bars)) ** 1.5 - 0.12 * v_amt   # one long arch: build, peak, release
            for b in range(7, n_bars - 1, 8):
                inten[b] -= 0.12 * v_amt                              # a breath before each 8-bar group
        inten = np.clip(inten, 0.02, 1.0)

    # plan (scripts/plan.py): loudness, density, lead and register become separate curves, not one intensity.
    # Without "plan": true the old single curve is used, unchanged.
    gate = inten                                                    # what decides whether a layer enters
    p_lead, p_reg = np.ones(n_bars, bool), np.zeros(n_bars)
    plan = None
    if brief.get('plan'):
        import plan as planmod
        plan = planmod.build_plan(n_bars, bb, bpm, hits)
        inten, gate, p_lead, p_reg = planmod.per_bar(plan)
    if mods['density'] < 0:                          # "sparse" / "minimal": layers enter later, so there are fewer
        gate = np.clip(gate * 0.85, 0, 1)
    elif mods['density'] > 0:                        # "full" / "lush"
        gate = np.clip(gate + 0.08, 0, 1)

    # ---- melody material (phrases of 4 bars; form AABA / ABAB) -------------------------------
    L = len(key.scale)
    tonic_deg = int(round(E['center'] / L)) * L if L else 0
    center_deg = E['center'] + (L if g_name in ('ambient', 'dark') else 0)
    phrase_bars = 4 if n_bars >= 8 else max(2, n_bars)
    n_ph = int(np.ceil(n_bars / phrase_bars))
    form = list(brief.get('form') or ('AABA' if n_ph >= 4 else 'AB'))
    bars_chords = [chords_by_bar[i:i + phrase_bars] for i in range(0, n_bars, phrase_bars)]
    material, melody = {}, []
    span = (center_deg - 6, center_deg + 9)
    for pi in range(n_ph):
        letter = form[pi % len(form)]
        ch = bars_chords[pi]
        ch = ch + [ch[-1]] * (phrase_bars - len(ch))
        last_ph = pi == n_ph - 1
        end_deg = tonic_deg if (last_ph or pi % 2 == 1) else tonic_deg + (4 if L == 7 else 2)   # half cadence on odd phrases
        if letter not in material:
            c = center_deg + (3 if letter == 'B' else 0)
            ph_notes, _, _ = make_phrase(rng, key, ch, bb, E['style'], center_deg=c, span=span,
                                         rest_p=E['rest'], contour='arch' if letter != 'B' else 'rise',
                                         end_deg=end_deg, vel=0.62)
            material[letter] = ph_notes
            notes = ph_notes
        else:
            notes = vary_phrase(rng, key, material[letter], ch, bb, shift=int(rng.choice([0, 0, 1, -1])) if not last_ph else 0,
                                cadence_deg=end_deg)
        for n in notes:
            melody.append(dict(n, t=n['t'] + pi * phrase_bars * bb))
    # last note rings out
    if melody and not loop:
        melody[-1]['d'] = bb * 1.5
    melody.sort(key=lambda n: n['t'])

    # ---- layers ----------------------------------------------------------------------------------
    lead_override = brief.get('lead')
    dyn_lo, dyn_hi = E['dyn']
    tracks = []
    variation = float(brief.get('variation', 0.45))        # 0 = every bar a copy of the template; 1 = most change
    drums_kind = brief.get('drums', E['drums'])
    if g_name == 'jazz':
        drums_kind = 'brush'
    if G.get('groove') and 'drums' not in brief:      # a genre names its own groove unless the brief sets drums
        drums_kind = G['groove']
    for layer in G['layers']:
        kind = layer['kind']
        inst = layer['instrument']
        if lead_override and layer['name'] == 'lead':
            inst = lead_override
        notes = []
        prev_v, prev_b = None, None
        for bar in range(n_bars):
            lv = float(inten[bar])
            thr = layer['min']
            if kind == 'drums' and drums_kind in ('taiko', 'march', 'heartbeat', 'half'):
                thr = min(thr, 0.35)              # the mood's own percussion (epic's taiko, passion's half-time) enters early enough to be heard
            if float(gate[bar]) < thr:
                prev_v = prev_v
                continue
            ch = chords_by_bar[bar]
            nxt = chords_by_bar[bar + 1] if bar + 1 < n_bars else None
            t0 = bar * bb
            vel = dyn_lo + (dyn_hi - dyn_lo) * lv
            if kind == 'chords':
                tex = layer['tex_low'] if lv < 0.4 else (layer['tex_mid'] if lv < 0.7 else layer['tex_hi'])
                if tension > 0.6 and layer['name'] == 'pulse':
                    tex = 'ostinato'
                prev_v = voice_lead(ch, prev_v, layer['lo'], layer['hi'])
                if g_name in ('folk', 'acoustic') and bb == 3:
                    tex = 'waltz'
                for n in vary_bar(TEXTURES[tex](prev_v, bb, vel=vel * 0.9, rng=rng), 'chords', bar, bb, variation, rng):
                    notes.append(dict(n, t=n['t'] + t0))
            elif kind == 'pad':
                prev_v = voice_lead(ch, prev_v, layer['lo'], layer['hi'], open_=False)
                same = bar > 0 and chords_by_bar[bar - 1] is ch and (bar % phrase_bars) != 0
                if same and notes and notes[-1]['t'] + notes[-1]['d'] >= t0 - 0.01:
                    for n in notes[-len(prev_v):]:
                        n['d'] += bb          # tie across bars with the same chord
                else:
                    for p in prev_v:
                        notes.append(dict(t=t0, d=bb * 0.995, p=p, v=vel * 0.8))
            elif kind == 'ostinato':
                prev_v = voice_lead(ch, prev_v, layer['lo'], layer['hi'], n=3)
                for n in TEXTURES['ostinato'](prev_v, bb, vel=vel * 0.8, rng=rng):
                    notes.append(dict(n, t=n['t'] + t0))
            elif kind == 'bass':
                bl, prev_b = bass_line(layer['bass'], ch, nxt, prev_b, bb, vel * 0.95, rng, layer['lo'], layer['hi'])
                for n in vary_bar(bl, 'bass', bar, bb, variation, rng):
                    notes.append(dict(n, t=n['t'] + t0))
            elif kind == 'drums':
                fill = (bar % 8 == 7 and bar < n_bars - 1 and lv > 0.3)
                crash = (bar % 8 == 0 and bar > 0 and lv > 0.4)
                bar_kind = drums_kind if drums_kind != 'none' else ('soft_pulse' if lv > 0.5 else 'none')
                bar_dr = drum_bar(bar_kind, bb, vel * 0.95, rng, fill=fill, crash=crash)
                for n in vary_bar(bar_dr, 'drums', bar, bb, variation * (0.4 if fill else 1.0), rng):
                    notes.append(dict(n, t=n['t'] + t0))
            elif kind == 'sparkle':
                nsp = 1 + int(lv * 2.5)
                tones = [m for m in range(layer['lo'], layer['hi'] + 1) if m % 12 in ch['pcs']]
                if tension > 0.5:        # dissonant plinks: add the minor 2nd above the root
                    tones += [m for m in range(layer['lo'], layer['hi'] + 1) if m % 12 == (ch['root_pc'] + 1) % 12]
                for ti in sorted(rng.choice(np.arange(0.5, bb, 0.5), size=min(nsp, int(bb * 2) - 1), replace=False)):
                    if rng.random() < 0.7:
                        notes.append(dict(t=t0 + float(ti), d=1.2, p=int(rng.choice(tones)), v=vel * 0.7))
        if kind in ('melody', 'harmony'):
            src = melody
            if kind == 'harmony':
                src = harmony_line(key, melody, -2, chords_by_bar, bb)
            octs = layer.get('oct', 0)
            for n in src:
                bar = min(int(n['t'] // bb), n_bars - 1)
                lv = float(inten[bar])
                if float(gate[bar]) < layer['min']:
                    continue
                is_lead = layer['name'] == 'lead'
                if is_lead and not p_lead[bar]:          # the plan's hush or rest: the lead is silent
                    continue
                vel = dyn_lo + (dyn_hi - dyn_lo) * lv
                shift = int(p_reg[bar]) if is_lead else 0
                notes.append(dict(t=n['t'], d=n['d'], p=n['p'] + 12 * octs + shift, v=min(1.0, n['v'] * (0.65 + 0.5 * vel)),
                                  **({'art': 'legato'} if E['art'] >= 0.9 else {'art': 'staccato'})))
            if layer['name'] == 'lead':
                pass
            if notes and g_name != 'ambient':
                # keep the lead inside a playable, singing register
                lo_r, hi_r = (62, 88) if any(n in HIGH_LEADS for n in _base_names(inst)) else (52, 82)
                notes = clamp_register(notes, lo_r, hi_r)
        if not notes:
            continue
        cents = world.MICRO.get(mode)                 # the scale's real tuning, as a pitch bend per note
        if cents and kind != 'drums' and layer.get('micro', True):
            for n in notes:
                n['c'] = cents.get(key.degree_of(n['p']) % L, 0.0) if n['p'] % 12 in key.pcs() else 0.0
        if layer.get('glide') and kind in ('melody', 'harmony'):     # slide up into some notes (meend, kan, portamento)
            for n in notes:
                if n['d'] >= 0.5 and rng.random() < layer['glide']:
                    n['gl'] = float(rng.choice([-100, -200]))
        tr = dict(name=layer['name'], instrument=inst, role=layer['role'], notes=notes)
        for k in ('gain_db', 'vibrato', 'expression'):
            if k in layer:
                tr[k] = layer[k]
        if kind == 'drums' and g_name in ('cinematic', 'orchestral', 'dark'):
            pass
        tracks.append(tr)

    if fp:
        tracks = fusion.shape_for_soul(tracks, fp, bb)                        # call and answer, rests between phrases
        tracks += fusion.pattern_tracks(fp, n_bars, bb, inten, seed=seed)     # dadra, 12/8 bell, jig: the rhythm of each culture

    # ---- dynamics curve (the emotional shape the listener feels) ----------------------------------
    dyn_pts = [[0, float(0.35 + 0.5 * inten[0])]]
    for b in range(n_bars):
        dyn_pts.append([b * bb + bb / 2, float(0.3 + 0.65 * inten[b])])
    dyn_pts.append([n_bars * bb, float(0.3 + 0.65 * inten[-1])])

    room = mods['room'] or G['room']
    score = dict(title=brief.get('title', f'{emo} {g_name}'), bpm=bpm, ts=[bb, 4], key=f'{tonic} {mode}', seed=seed,
                 humanize=brief.get('humanize', G['humanize']), swing=G['swing'], room=room,
                 dynamics=dyn_pts, tracks=tracks,
                 master=dict(lufs=brief.get('lufs', -18 if voiceover else G['lufs']), true_peak=-1.5, tone=G['tone']),
                 meta=dict(emotion=emo, genre=g_name, mode=mode, tonic=tonic, bars=n_bars, progression=prog_text,
                           form=''.join(form), arc=arc, intensity_per_bar=[round(float(x), 2) for x in inten],
                           energy=round(float(intensity), 2), room=room, mood_notes=mood_notes,
                           duration_s_nominal=round(n_bars * bb * 60.0 / bpm, 1)))
    if mods['wet'] != 1.0:
        score['mix'] = dict(reverb_return=round(float(mods['wet']), 2))
    if brief.get('piece_type'):               # the type of piece for the quality gate (gate_profiles.py list); else the gate infers it
        score['piece_type'] = brief['piece_type']
    if fp:
        score['fusion'] = fp
    if plan:
        score['plan'] = plan
        score['master']['fade_out'] = plan['ending']['fade_out']
    if loop:
        score.update(rubato=0.0, ritard=0.0, wander=0.0, loop_seconds=n_bars * bb * 60.0 / bpm)
    elif emo in ('grief', 'sad', 'tender', 'calm', 'melancholy', 'dreamy'):
        score.update(ritard=0.4)
    if voiceover:
        for tr in score['tracks']:        # leave the speech band (2-4 kHz) clear; keep everything modest
            tr.setdefault('eq', [])
            tr['eq'].append(dict(type='peak', f=3000, gain=-3.0, q=0.9))
        score['master']['lufs'] = brief.get('lufs', -20)
    add_hit_points(score, hits, bpm, bb, key, rng)
    return score


def add_hit_points(score, hits, bpm, bb, key, rng):
    """impact / rise / silence / stinger at specific seconds (scene cuts, reveals, logo hits)"""
    dyn = score['dynamics']
    for h in hits:
        typ = h['type']
        beat = round(h['t'] * bpm / 60.0 * 2) / 2.0
        if typ == 'impact':
            root = key.tonic_midi % 12 + 36
            score['tracks'].append(dict(name=f'impact_{int(beat)}', instrument='orchestral', role='drum', gain_db=-1,
                                        notes=[dict(t=beat, d=0.5, p='tom_floor', v=1.0), dict(t=beat, d=2, p='crash', v=0.9),
                                               dict(t=beat + 0.01, d=0.5, p='kick', v=1.0)]))
            score['tracks'].append(dict(name=f'boom_{int(beat)}', instrument='timpani', role='bass', gain_db=-1,
                                        notes=[dict(t=beat, d=4, p=int(root + 12), v=1.0)]))
            dyn += [[beat - 0.05, 0.5], [beat, 1.0], [beat + 4, 0.65]]
        elif typ == 'rise':
            start = max(0.0, beat - 4)
            score['tracks'].append(dict(name=f'riser_{int(beat)}', instrument='reverse_cymbal', role='fx', gain_db=-4,
                                        notes=[dict(t=start, d=beat - start, p=60, v=0.8)]))
            roll = []
            t = start
            step = 0.5
            while t < beat - 0.05:
                roll.append(dict(t=t, d=0.1, p='snare', v=0.3 + 0.6 * (t - start) / max(beat - start, 1)))
                step = max(0.125, step * 0.9)
                t += step
            score['tracks'].append(dict(name=f'roll_{int(beat)}', instrument='standard', role='drum', gain_db=-6, notes=roll))
            dyn += [[start, 0.4], [beat - 0.05, 1.0]]
        elif typ == 'silence':
            end = beat + float(h.get('beats', 1.5))
            for tr in score['tracks']:
                tr['notes'] = [n for n in tr['notes'] if not (beat <= n['t'] < end)]
                for n in tr['notes']:
                    if n['t'] < beat < n['t'] + n['d']:
                        n['d'] = max(0.1, beat - n['t'])
            dyn += [[beat - 0.1, 0.5], [beat, 0.05], [end - 0.1, 0.05], [end + 0.5, 0.5]]
    score['dynamics'] = sorted([list(map(float, p)) for p in dyn])


def export_midi(score, path):
    """Standard MIDI of the pitched and drum tracks. Environment/effect tracks (no pitch) are skipped. Preset names resolve through
    the preset's GM sound; a score with tempo_points is exported on its own tempo map (rubato off), so the beats land where they sound."""
    import pretty_midi
    import soundbank as sb
    import presets as _presets
    pm = pretty_midi.PrettyMIDI(initial_tempo=score['bpm'])
    spb = 60.0 / score['bpm']
    sec = lambda beat: beat * spb
    if score.get('tempo_points'):
        import humanize as _hz
        end = max((n['t'] + n.get('d', 0) for t in score['tracks'] for n in t.get('notes', [])), default=1.0) + 1
        tm = _hz.TempoMap(score['bpm'], total_beats=end, points=score['tempo_points'], rubato=0.0, wander=0.0, ritard=0.0)
        sec = lambda beat: float(tm.sec(beat))
    for tr in score['tracks']:
        name = str(tr.get('instrument', ''))
        if tr.get('role') == 'environment' or name.startswith(('env:', 'sfx:')):
            continue
        cfg = None
        try:
            cfg = _presets.find_instrument(name) or _presets.find_vocal(name)
        except Exception:
            cfg = None
        gm = (cfg or {}).get('gm') or (cfg or {}).get('instrument') or name
        try:
            bank, prog, drum = sb.resolve(gm)
        except KeyError:                       # formant voices (hum, choir, voice) have no GM patch: a choir patch stands in
            bank, prog, drum = sb.resolve('choir_aahs')
        if tr.get('role') == 'drum' and any(isinstance(n.get('p'), str) for n in tr.get('notes', [])):
            drum = True
        inst = pretty_midi.Instrument(program=0 if drum else prog, is_drum=drum, name=tr.get('name', ''))
        for n in tr['notes']:
            if 'p' not in n:
                continue
            p = sb.DRUM_KEYS[n['p']] if isinstance(n['p'], str) else int(n['p'])
            v = n.get('v', 0.7)
            v = int(np.clip(v * 127 if v <= 1 else v, 1, 127))
            inst.notes.append(pretty_midi.Note(velocity=v, pitch=p, start=sec(n['t']), end=sec(n['t'] + max(n['d'], 0.05))))
        pm.instruments.append(inst)
    pm.write(path)


def describe(score):
    m = score['meta']
    print(f"{score['title']}: {score['key']}, {score['bpm']} bpm, {m['bars']} bars (~{m['duration_s_nominal']}s), "
          f"form {m['form']}, progression {m['progression']}, arc {m['arc']}")
    print(f"  mood {m['emotion']} at energy {m.get('energy', '?')} in a '{m.get('room', '?')}' room")
    for note in m.get('mood_notes', []):
        print('  note:', note)
    for tr in score['tracks']:
        ns = tr['notes']
        print(f"  {tr['name']:10s} {tr['instrument']:16s} {tr['role']:7s} {len(ns):4d} notes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--brief')
    ap.add_argument('--emotion')
    ap.add_argument('--scene')
    ap.add_argument('--genre')
    ap.add_argument('--duration', type=float)
    ap.add_argument('--bpm', type=float)
    ap.add_argument('--key')
    ap.add_argument('--mode')
    ap.add_argument('--arc')
    ap.add_argument('--intensity', type=float)
    ap.add_argument('--energy', type=float, help='0..1 how hard it pushes (default: the mood\'s own band)')
    ap.add_argument('--space', help='dry | studio | hall | large_hall | cathedral')
    ap.add_argument('--seed', type=int)
    ap.add_argument('--voiceover', action='store_true')
    ap.add_argument('--loop', action='store_true')
    ap.add_argument('--out', default='score.json')
    ap.add_argument('--render')
    ap.add_argument('--midi')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        print('EMOTIONS:', ', '.join(sorted(EMOTIONS)))
        print('ALIASES :', ', '.join(sorted(EMOTION_ALIASES)))
        print('GENRES  :', ', '.join(sorted(GENRES)))
        print('GENRE ALIASES (Pixabay and common names):', ', '.join(sorted(GENRE_ALIASES)))
        print('ARCS    :', ', '.join(sorted(ARCS)))
        print('MODES   :', ', '.join(sorted(MODES)))
        return
    if a.brief:
        brief = json.load(open(a.brief, encoding='utf-8'))
        import presets
        presets.add_project(os.path.dirname(os.path.abspath(a.brief)))
    else:
        brief = {}
    for k, v in dict(emotion=a.emotion, scene=a.scene, genre=a.genre, duration_s=a.duration, bpm=a.bpm, key=a.key,
                     mode=a.mode, arc=a.arc, intensity=a.intensity, seed=a.seed, energy=a.energy,
                     space=a.space).items():
        if v is not None:
            brief[k] = v
    if a.voiceover:
        brief['voiceover'] = True
    if a.loop:
        brief['loop'] = True
    score = compose(brief)
    json.dump(score, open(a.out, 'w', encoding='utf-8'))
    describe(score)
    print('score ->', a.out)
    if a.midi:
        export_midi(score, a.midi)
        print('midi  ->', a.midi)
    if a.render:
        import render_natural as rn
        import mixer
        stems, tm = rn.build_stems(score)
        mixer.mix_and_master(score, stems, a.render)


if __name__ == '__main__':
    main()
