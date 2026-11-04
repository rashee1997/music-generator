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
"""custom_score_template.py - copy this file, rename it, and write YOUR OWN music with code.

Use this when compose.py's emotion presets are not specific enough: a named theme, a leitmotif that
returns in a different mood, a fixed chord sheet from the user, exact timing to a video, a unique
instrument line-up, or any piece where you (Claude) want full control.

    cp templates/custom_score_template.py my_piece.py     # edit the CONFIG + the "WRITE THE MUSIC" section
    python3 my_piece.py                                   # -> my_piece.wav, my_piece.mid, my_piece.json

The workflow is always the same five steps:
  1. decide      emotion, tempo, key/mode, form, instruments, what changes over time (see references/scoring/emotion-and-scoring.md)
  2. write       notes as dicts {"t": beat, "d": beats, "p": MIDI, "v": 0..1}   (helpers below make this easy)
  3. assemble    a score dict: tracks (instrument + role + notes), dynamics curve, room, master target
  4. execute     pipeline.MusicPipeline().execute (humanize, render, mix, master, and run full CI quality gate)
  5. deliver     master WAV, MIDI, and ci_report.json

Everything not specific to the piece is handled for you; you only write notes and choices.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')                 # when you copy this file elsewhere, set SCRIPTS to the skill's scripts/ folder
sys.path.insert(0, SCRIPTS)

from theory import NOTE_PC, Key, parse_progression, voice_lead, bass_note, TEXTURES, make_phrase, vary_phrase, harmony_line, note_name  # noqa: E402
import render_natural as rn                                   # noqa: E402
import mixer                                                  # noqa: E402
import compose                                                # noqa: E402  (export_midi + add_hit_points)

# ============================ CONFIG ======================================================
OUT = os.path.splitext(os.path.abspath(__file__))[0]          # writes OUT.wav / OUT.mid / OUT.json
TITLE = 'Harbour at dawn'
BPM = 72
BEATS_PER_BAR = 4
KEY = Key('D', 'dorian')                                      # Key(tonic, mode). modes: see theory.MODES
SEED = 11                                                     # same seed = same performance
HUMANIZE = 'natural'                                          # tight | natural | loose | rubato  (or a dict)
ROOM = 'hall'                                                 # studio room_warm chamber plate hall large_hall cathedral cave
LUFS = -16                                                    # -14 streaming / video, -16 film/ambient, -18 underscore
PROGRESSION = 'i-IV-i-VII   i-IV-VII-i'                       # roman numerals, one chord per bar. 8 bars here
# ===========================================================================================

rng = np.random.default_rng(SEED)
bb = BEATS_PER_BAR
chords = parse_progression(KEY, PROGRESSION)
n_bars = len(chords)
total_beats = n_bars * bb


# ------------------------------ WRITE THE MUSIC ----------------------------------------------
# helper: shorthand to write a melody by hand. (beat, duration, "note name" or MIDI)
def line(*items, vel=0.6):
    """line((beat, duration, "A4" | 69), ...) -> note dicts. Names: C C# Db D Eb E F F# Gb G Ab A Bb B + octave (C4 = 60)."""
    out = []
    for t, d, p in items:
        if isinstance(p, str):
            p = 12 * (int(p[-1]) + 1) + NOTE_PC[p[:-1]]
        out.append(dict(t=float(t), d=float(d), p=int(p), v=vel))
    return out


# 1) THE THEME - a motif you invent (rhythm + contour) and then DEVELOP: repeat, sequence, invert, augment.
theme = line((0, 1.5, 'A4'), (1.5, .5, 'B4'), (2, 2, 'D5'),            # bar 1: rising, question
             (4, 1.5, 'C5'), (5.5, .5, 'B4'), (6, 2, 'A4'),            # bar 2: answer, falls back
             (8, 1.5, 'A4'), (9.5, .5, 'B4'), (10, 1, 'D5'), (11, 1, 'E5'),   # bar 3: varied, reaches higher
             (12, 3.5, 'D5'))                                          # bar 4: long note = breath / cadence
# a later, higher, fuller restatement (octave up + a third above) of the same theme
theme_hi = [dict(n, t=n['t'] + 16, p=n['p'] + 12, v=0.7) for n in theme]

# 2) ACCOMPANIMENT from the chords: voice-lead pads/piano, bass roots, any texture from theory.TEXTURES
pad, piano, bass = [], [], []
prev = None
pprev = None
pbass = None
for bar, ch in enumerate(chords):
    t0 = bar * bb
    prev = voice_lead(ch, prev, 48, 69)
    for p in prev:
        pad.append(dict(t=t0, d=bb * .99, p=p, v=0.45))
    pprev = voice_lead(ch, pprev, 55, 76)
    for n in TEXTURES['arp8' if bar >= 4 else 'sparse'](pprev, bb, vel=0.5, rng=rng):
        piano.append(dict(n, t=n['t'] + t0))
    pbass = bass_note(ch, pbass, 33, 48)
    bass.append(dict(t=t0, d=bb * .95, p=pbass, v=0.55))

# 3) THE ARC - how loud/dense the piece feels over time (global dynamics 0..1 by beat). This is the emotion.
dynamics = [[0, .35], [8, .45], [16, .6], [24, .9], [28, .75], [total_beats, .4]]

# ------------------------------ ASSEMBLE -----------------------------------------------------
score = dict(
    title=TITLE, bpm=BPM, ts=[bb, 4], seed=SEED, humanize=HUMANIZE, room=ROOM, dynamics=dynamics,
    ritard=0.4, ritard_beats=6,                                   # slow down at the very end
    master=dict(lufs=LUFS, true_peak=-1.5, tone='warm'),
    tracks=[
        dict(name='pad',   instrument='slow_strings', role='pad',    notes=pad),
        dict(name='piano', instrument='piano',        role='chord',  notes=piano),
        dict(name='bass',  instrument='cello',        role='bass',   notes=bass, gain_db=-5),
        dict(name='theme', instrument='flute',        role='melody', notes=theme[:] + [n for n in theme_hi if n['t'] < total_beats]),
        # --- other things you can drop in -------------------------------------------------
        # dict(name='clone', instrument='clone:clones/my_sitar', role='melody', notes=[...])   # a cloned instrument
        # dict(name='kal',   instrument='marimba',              role='arp',    notes=[...])    # a GM mallet (see natural-instruments.md)
        # dict(name='kit',   instrument='brush', role='drum', notes=[dict(t=0,d=.1,p='kick',v=.7), ...])   # or direct.add_pulse(score)
    ],
    # per-track overrides if the checker complains, e.g.:
    #   "mix": {"tracks": {"piano": {"gain_db": -10, "eq": [{"type": "peak", "f": 300, "gain": -3}], "reverb": 0.3}}}
)
# situational hits at exact seconds (optional): impact / rise / silence
# compose.add_hit_points(score, [dict(t=20.0, type='impact')], BPM, bb, KEY, rng)

# ------------------------------ RENDER + CI/CD CHECK -----------------------------------------
if __name__ == '__main__':
    import pipeline
    pipe = pipeline.MusicPipeline(verbose=True)
    pipe.execute(score, out_wav=OUT + '.wav', out_midi=OUT + '.mid', json_report=OUT + '_report.json')
