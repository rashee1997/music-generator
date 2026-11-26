#!/usr/bin/env python3
"""compose_main.py - Custom composition script for 'Night Pursuit Cinematic'.

Project Architecture:
  1. Direction : direction/direction_sheet.json
  2. Presets   : presets/instruments/, presets/vocals/, presets/spaces/, presets/mix/, presets/sfx/, presets/video/ (+ environments/ if ambience was asked)
  3. Score     : scores/main_score.json
  4. Execution : pipeline.py scores/main_score.json
"""
import os
import sys
import json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(HERE)
SKILL_SCRIPTS = os.environ.get("MUSIC_SKILL_SCRIPTS") or "/home/user/music-generator/scripts"

if SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS)

from theory import Key, parse_progression, voice_lead, bass_note, TEXTURES, NOTE_PC  # noqa: E402
import pipeline                                                                         # noqa: E402

SCORE_JSON = os.path.join(PROJECT_DIR, 'scores', 'main_score.json')
OUT_WAV = os.path.join(PROJECT_DIR, 'out', 'master.wav')
OUT_MIDI = os.path.join(PROJECT_DIR, 'out', 'song.mid')
REPORT_JSON = os.path.join(PROJECT_DIR, 'reports', 'ci_report.json')

BPM = 84.0
bb = 4
KEY = Key('D', 'dorian')
SEED = 42

rng = np.random.default_rng(SEED)
chords = parse_progression(KEY, 'i-IV-i-VII   i-IV-VII-i')
total_beats = len(chords) * bb

def line(*items, vel=0.65):
    out = []
    for t, d, p in items:
        if isinstance(p, str):
            p = 12 * (int(p[-1]) + 1) + NOTE_PC[p[:-1]]
        out.append(dict(t=float(t), d=float(d), p=int(p), v=int(vel * 127)))
    return out

# 1. Melodic Theme (references presets/instruments/lead_flute.json)
theme = line((0, 1.5, 'A4'), (1.5, .5, 'B4'), (2, 2, 'D5'),
             (4, 1.5, 'C5'), (5.5, .5, 'B4'), (6, 2, 'A4'),
             (8, 1.5, 'A4'), (9.5, .5, 'B4'), (10, 1, 'D5'), (11, 1, 'E5'),
             (12, 3.5, 'D5'), vel=0.68)

# 2. Harmonic Voicings (references presets/instruments/warm_piano.json)
piano_notes, bass_notes, pad_notes = [], [], []
prev, pprev, pbass = None, None, None
for bar, ch in enumerate(chords):
    t0 = bar * bb
    prev = voice_lead(ch, prev, 48, 69)
    for p in prev:
        pad_notes.append(dict(t=t0, d=bb * 0.98, p=int(p), v=60))
    pprev = voice_lead(ch, pprev, 55, 76)
    for n in TEXTURES['arp8' if bar >= 4 else 'sparse'](pprev, bb, vel=0.52, rng=rng):
        piano_notes.append(dict(t=float(n['t'] + t0), d=float(n['d']), p=int(n['p']), v=int(n['v'] * 127)))
    pbass = bass_note(ch, pbass, 26, 42)
    bass_notes.append(dict(t=t0, d=bb * 0.95, p=int(pbass), v=72))

score_data = {
    "title": "Night Pursuit Cinematic",
    "bpm": BPM,
    "ts": [bb, 4],
    "key": "D",
    "mode": "dorian",
    "space": "night_pursuit_cinematic_room",
    "mix_preset": "night_pursuit_cinematic_mix",
    "dynamics": [[0.0, 0.45], [8.0, 0.60], [16.0, 0.85], [24.0, 0.95], [28.0, 0.70], [total_beats, 0.40]],
    "master": {"lufs": -16.0, "true_peak": -1.5, "tone": "warm"},
    "tracks": [
        {"name": "flute_lead", "instrument": "lead_flute", "role": "melody", "notes": theme},
        {"name": "piano_arps", "instrument": "warm_piano", "role": "chord", "notes": piano_notes},
        {"name": "acoustic_bass", "instrument": "acoustic_bass", "role": "bass", "notes": bass_notes},
        {"name": "vocal_pad", "instrument": "vocal_hum", "role": "pad", "notes": pad_notes}
    ]
}
if False:      # ambience only when the user asked for it
    score_data["tracks"].append({"name": "forest_env", "instrument": "env:forest_canopy_3d", "role": "environment", "notes": []})

with open(SCORE_JSON, 'w', encoding='utf-8') as f:
    json.dump(score_data, f, indent=2)

print(f"[OK] Wrote declarative score to: {SCORE_JSON}")

if __name__ == '__main__':
    pipe = pipeline.MusicPipeline(verbose=True)
    pipe.execute(SCORE_JSON, out_wav=OUT_WAV, out_midi=OUT_MIDI, json_report=REPORT_JSON)
