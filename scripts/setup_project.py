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
"""setup_project.py - set up the music-generator skill in one command.

    python3 scripts/setup_project.py              # core: .venv, packages, SoundFont, smoke test
    python3 scripts/setup_project.py --ears       # also earshot (listen.py hears the music) and its models (about 1 GB)

What it does, in order:
  1. makes a virtual environment in .venv (with uv when uv is installed, otherwise python -m venv and pip)
  2. installs requirements.txt into it
  3. installs tinysoundfont with --no-deps (see requirements.txt for why)
  4. with --ears: installs torch (CPU build), then requirements-ears.txt, then downloads earshot's models
  5. runs the SoundFont download and a render smoke test inside the environment
  6. downloads the measured head data for "binaural": "hrtf" (scripts/spatial_hrtf, about 150 MB once; failure is not fatal)

Only the standard library is used, so this runs before anything else is installed. Needs Python 3.10 or newer.
Install uv for faster installs: pip install uv   (or see https://docs.astral.sh/uv/)
"""
import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TINYSOUNDFONT = 'tinysoundfont==0.3.7'
TORCH = 'torch==2.14.1'
TORCH_INDEX = 'https://download.pytorch.org/whl/cpu'
EARSHOT_HOME = Path.home() / '.cache' / 'music-generator' / 'earshot'


def run(cmd, **kw):
    cmd = [str(c) for c in cmd]
    print('$ ' + ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        sys.exit(f'stopped: "{cmd[0]}" exited with code {r.returncode}. Fix the error above and run this again.')


def venv_python(venv):
    return venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def make_venv(venv, uv):
    if uv:
        # the pins in requirements.txt (numpy 2.5) need Python 3.12+; uv fetches one when this interpreter is older
        run([uv, 'venv', '--allow-existing', '--python', '3.12' if sys.version_info < (3, 12) else sys.executable, venv])
    else:
        if not venv_python(venv).exists():
            run([sys.executable, '-m', 'venv', venv])
        run([venv_python(venv), '-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'])


def install(venv, uv, *args):
    if uv:
        run([uv, 'pip', 'install', '--python', venv_python(venv), *args])
    else:
        run([venv_python(venv), '-m', 'pip', 'install', *args])


def scaffold_project(proj_path, title="New Composition", ambience=False):
    """ambience=False (default): no environment preset or track. Ambience is added only when the user asked for it."""
    proj_dir = Path(proj_path).resolve()
    direction_dir = proj_dir / 'direction'
    presets_dir = proj_dir / 'presets'
    inst_dir = presets_dir / 'instruments'
    vocal_dir = presets_dir / 'vocals'
    env_dir = presets_dir / 'environments'
    scores_dir = proj_dir / 'scores'
    midi_dir = proj_dir / 'midi'
    stems_dir = proj_dir / 'stems'
    reports_dir = proj_dir / 'reports'
    scripts_dir = proj_dir / 'scripts'
    out_dir = proj_dir / 'out'
    spaces_dir = presets_dir / 'spaces'
    mix_dir = presets_dir / 'mix'
    sfx_dir = presets_dir / 'sfx'            # one-hit effect presets (optional: the shipped defaults work without it)
    video_dir = presets_dir / 'video'        # scoring to picture: probe, direction map, mix, master, mux (scripts/video_score.py)
    gate_dir = presets_dir / 'gate'          # this piece's gate profile (gate_profiles.py new <name> --project <dir>)
    ref_dir = proj_dir / 'reference'         # measured real-sound metrics (reference/<slug>.json), URLs and licences
    slug = ''.join(c if c.isalnum() else '_' for c in title.lower()).strip('_') or 'piece'

    for d in (direction_dir, inst_dir, vocal_dir, spaces_dir, mix_dir, sfx_dir, video_dir, gate_dir, ref_dir, scores_dir, midi_dir, stems_dir, reports_dir, scripts_dir, out_dir) + ((env_dir,) if ambience else ()):
        d.mkdir(parents=True, exist_ok=True)

    # Delivery metadata: the standard tags live in the skill (presets/metadata/metadata.json); this file only
    # overrides them for this piece. scripts/helpers/ingest_metadata.py reads both at certification.
    meta_file = proj_dir / 'metadata.json'
    if not meta_file.exists():
        meta_file.write_text(json.dumps({
            'overrides': {},
            'derive_from_score': {'title': True, 'genre': True, 'comment': True, 'year': True},
        }, indent=2) + '\n', encoding='utf-8')
    
    skill_scripts = (SKILL / 'scripts').resolve()
    skill_scripts_str = str(skill_scripts).replace('\\', '/')
    
    # 1. Generate direction/direction_sheet.json: a director's sheet, not a checklist.
    #    Every block is one a director decides before a note exists (spotting: where the cue starts and stops, the
    #    arc, the motif plan, the hits with a reason, how it ends). The gate rejects a sheet whose sections overlap,
    #    whose hits disagree with hits_at, or whose video block names no picture. Detail: references/workflow/music-direction.md.
    room = f'{slug}_room'
    direction_content = {
        "title": title,
        "project": "TODO: the client, film, album or game this cue belongs to",
        "version": 1,
        "medium": "TODO: film, ad, game, album, social or installation",
        "brief": "TODO: the words the client actually used, verbatim",
        "audience": "TODO: who hears it, where, and what they already know",
        "purpose": "TODO: what this piece must do for the listener or the picture",
        "point_of_view": "TODO: whose ears we are in, and what that forbids (a character walks, a narrator floats)",
        "job": ["TODO: three or four jobs the music must do, in order of importance"],
        "story": "TODO: the cue in one sentence, from its first moment to its last",
        "duration_s": 45.0,
        "in_point_s": 0.0,
        "out_point_s": 45.0,
        "ending": "tail_out",
        "feel": ["TODO: plain feeling words"],
        "avoid_feel": ["synthetic", "robotic", "flat", "harsh"],
        "sections": [
            {"name": "TODO: first section", "start_s": 0.0, "end_s": 10.0, "energy": 0.2,
             "action": "TODO: what happens on screen or in the piece",
             "music": "TODO: what enters and what it does", "role": "place"},
            {"name": "TODO: build", "start_s": 10.0, "end_s": 24.0, "energy": 0.45,
             "action": "TODO", "music": "TODO", "role": "build"},
            {"name": "TODO: peak", "start_s": 24.0, "end_s": 34.0, "energy": 0.8,
             "action": "TODO", "music": "TODO", "role": "peak"},
            {"name": "TODO: ending", "start_s": 34.0, "end_s": 45.0, "energy": 0.25,
             "action": "TODO", "music": "TODO", "role": "button"}
        ],
        "motifs": [{"name": "TODO: motif name", "first_at_s": 4.0, "shape": "TODO: its few notes",
                    "returns": "TODO: where it comes back, and changed how"}],
        "instruments": ["lead_flute", "warm_piano", "acoustic_bass"],
        "avoid_sounds": ["TODO: sounds that must never appear in this piece"],
        "pulse": "steady",
        "tempo_bpm": [78, 92],
        "key": "D",
        "mode": "dorian",
        "energy": 0.5,
        "space": room,
        "hits_at": [16.0, 32.0],
        "hits": [
            {"t": 16.0, "kind": "musical", "sync": "soft", "sound": "TODO: what lands here",
             "why": "TODO: the reason this moment needs an accent"},
            {"t": 32.0, "kind": "musical", "sync": "soft", "sound": "TODO", "why": "TODO"}
        ],
        "mix_intent": {"hero": "lead_flute", "support": ["warm_piano", "acoustic_bass"], "sits_under": [],
                       "must_hear": ["TODO: what has to be audible, and by when"], "leave_free_hz": [250, 3800]},
        "loudness_lufs": -16.0,
        "true_peak_max": -1.5,
        "delivery": {"format": "wav", "sample_rate": 48000, "bit_depth": 24,
                     "stage": "TODO: web, broadcast or cinema"},
        "references": ["TODO: in words, never a copyrighted track (references/workflow/music-direction.md section 2)"],
        "spatial_staging": {
            "lead_flute": {"azimuth": 0.0, "elevation": 4.0, "distance": 1.4, "space": room},
            "warm_piano": {"azimuth": -45.0, "elevation": 0.0, "distance": 2.0, "space": room},
            "acoustic_bass": {"azimuth": 0.0, "elevation": -6.0, "distance": 1.2, "space": room},
            "vocal_hum": {"azimuth": 45.0, "elevation": 8.0, "distance": 2.8, "space": room}
        },
        "piece_type": "melodic",
        "gate_reason": "TODO: one line on why this gate profile fits this piece; the gate runs it",
        "video": {"enabled": False, "source": None, "fps": None, "cuts": [], "cut_source": None,
                  "cut_sync": {"early_ms": 45, "late_ms": 125},
                  "dialogue": {"present": False, "duck_db": -9.0, "snr_min_db": 15.0},
                  "master_profile": None, "deliverable": None, "preset": "default",
                  "notes": "music-only piece: leave enabled false. For a cue against a cut, run scripts/video_score.py and it fills this block."},
        "notes": "TODO: anything in the brief that has no field of its own"
    }
    with open(direction_dir / "direction_sheet.json", "w", encoding="utf-8") as f:
        json.dump(direction_content, f, indent=2)

    # 2. Generate presets/
    flute_preset = {
        "name": "lead_flute",
        "description": "Solo expressive acoustic flute with breath dynamics and 3D spatial staging",
        "instrument": "flute",
        "role": "melody",
        "humanize": {"preset": "natural", "timing_ms": 5.0, "drift_ms": 6.0, "vel_sigma": 4.0},
        "spatial": {"azimuth": 0.0, "elevation": 4.0, "distance": 1.4, "space": "hall", "binaural": True},
        "eq": [
            {"type": "hp", "f": 180.0},
            {"type": "peak", "f": 2200.0, "gain": 1.8, "q": 1.2},
            {"type": "lp", "f": 12000.0}
        ],
        "gain_db": -2.0,
        "reverb": 0.24
    }
    with open(inst_dir / "lead_flute.json", "w", encoding="utf-8") as f:
        json.dump(flute_preset, f, indent=2)

    piano_preset = {
        "name": "warm_piano",
        "description": "Acoustic piano arpeggiations with stereo width and vocal pocket carving",
        "instrument": "piano",
        "role": "chord",
        "spatial": {"azimuth": -40.0, "elevation": 0.0, "distance": 2.0, "space": "hall"},
        "eq": [
            {"type": "hp", "f": 80.0},
            {"type": "peak", "f": 250.0, "gain": 1.5, "q": 1.0},
            {"type": "notch", "f": 2000.0, "gain": -2.0, "q": 1.5}
        ],
        "gain_db": -6.0,
        "reverb": 0.22
    }
    with open(inst_dir / "warm_piano.json", "w", encoding="utf-8") as f:
        json.dump(piano_preset, f, indent=2)

    bass_preset = {
        "name": "acoustic_bass",
        "description": "Grounded acoustic bass foundation",
        "instrument": "cello",
        "role": "bass",
        "spatial": {"azimuth": 0.0, "elevation": -6.0, "distance": 1.2, "space": "hall"},
        "eq": [
            {"type": "hp", "f": 35.0},
            {"type": "peak", "f": 90.0, "gain": 2.0, "q": 1.1},
            {"type": "lp", "f": 1200.0}
        ],
        "gain_db": -4.0,
        "reverb": 0.0
    }
    with open(inst_dir / "acoustic_bass.json", "w", encoding="utf-8") as f:
        json.dump(bass_preset, f, indent=2)

    vocal_preset = {
        "name": "vocal_hum",
        "description": "Warm organic humming formant choir in mid-backstage",
        "synthesis": "formant",
        "vowel": "m",
        "character": "a small close group humming with the mouth closed, warm and a little shy, breathing between phrases",
        "hum": True,
        "expression": "gentle",
        "ensemble": {"voices": 4, "cohesion": 0.4, "pitch_spread_cents": 8.0},
        "vibrato": {"depth_cents": 18.0, "rate_hz": 4.8},
        "articulation": {"attack_ms": 250.0, "release_ms": 400.0},
        "gain_db": -10.0,
        "reverb": 0.38,
        "spatial": {"azimuth": 20.0, "elevation": 6.0, "distance": 2.8, "space": "hall", "binaural": True}
    }
    with open(vocal_dir / "vocal_hum.json", "w", encoding="utf-8") as f:
        json.dump(vocal_preset, f, indent=2)

    if ambience:      # only when the user asked for ambience; the layers are a starting point to rewrite from the research
        env_preset = {
            "name": "forest_canopy_3d",
            "character": "ONE SENTENCE: the place, the time, and why these layers make it",
            "description": "Spatialized gentle canopy breeze and distant birds",
            "layers": [
                {"name": "distant_breeze", "primitive": "noise_bed", "kind": "bed", "color": "pink", "low_hz": 100.0,
                 "high_hz": 1100.0, "gain_db": -22.0, "spatial": {"azimuth": 0.0, "distance": 5.0}},
                {"name": "far_bird", "primitive": "fm_chirp_cluster", "kind": "spot", "event_rate": 0.25, "gain_db": -24.0,
                 "spatial": {"azimuth": -45.0, "distance": 9.0}}
            ]
        }
        with open(env_dir / "forest_canopy_3d.json", "w", encoding="utf-8") as f:
            json.dump(env_preset, f, indent=2)

    # a room and a mix preset of this project: the gate blocks until their "character" sentences are written
    shipped_hall = json.loads((SKILL / 'references' / 'data' / 'presets' / 'spaces' / 'hall.json').read_text(encoding='utf-8'))
    shipped_hall.update(name=f'{slug}_room', character='ONE SENTENCE: the place and why its tail, walls and distance law suit this piece')
    shipped_hall.pop('kind', None)
    with open(spaces_dir / f'{slug}_room.json', 'w', encoding='utf-8') as f:
        json.dump(shipped_hall, f, indent=2)
    import mix_schema              # stdlib-only, like this file: the role chains and spectral profiles are data a project edits
    mix_preset = {"name": f"{slug}_mix", "character": "ONE SENTENCE: what this music is (genre, mood, density) and why the mix below suits it",
                  "carve_db": -4.0, "max_boost_db": 12.0,
                  "note": "only list what differs: everything else comes from references/data/presets/mix/default.json",
                  # the strategies (references/mixing/mixing-and-mastering.md, section 8b); the defaults are the old behaviour
                  "gain_staging": {"strategy": "legacy", "ref_lufs": -24.0, "block_s": 0.4,
                                   "max_cut_db": 24.0, "peak_headroom_db": -1.0},
                  "dynamics": {"engine": "pedalboard", "knee_db": 0.0, "detector": "peak",
                               "stereo_link": True, "lookahead_ms": 0.0, "parallel": 1.0},
                  "spectral": {"max_auto_cut_db": 0.0, "preserve_spectrum_roles": ["environment"],
                               "profiles": copy.deepcopy(mix_schema.SPECTRAL_PROFILES)},   # rain, wind, water, voice, strings, ...
                  "space": {"auto_env_blend": {"enabled": True},
                            "drr": {"enabled": False, "target_db": 0.0}},
                  "sidechain": {"mode": "legacy", "band_hz": [250.0, 3800.0], "residual": 0.3,
                                "env_plateau": True},
                  "automation": {"curve": "linear"},
                  "mastering": {"profile": "default"},
                  "role_chains": copy.deepcopy(mix_schema.ROLE_CHAINS)}    # the EQ + compression each role starts with
    with open(mix_dir / f'{slug}_mix.json', 'w', encoding='utf-8') as f:
        json.dump(mix_preset, f, indent=2)

    # 3. Generate declarative scores/main_score.json
    score_content = {
        "title": title,
        "bpm": 84.0,
        "ts": [4, 4],
        "key": "D",
        "mode": "dorian",
        "space": f"{slug}_room",
        "mix_preset": f"{slug}_mix",
        "dynamics": [[0.0, 0.4], [8.0, 0.5], [16.0, 0.7], [24.0, 0.9], [28.0, 0.75], [32.0, 0.4]],
        "ritard": 0.35,
        "ritard_beats": 6,
        "master": {"lufs": -16.0, "true_peak": -1.5, "tone": "warm"},
        "tracks": [
            {
                "name": "flute_melody",
                "instrument": "lead_flute",
                "role": "melody",
                "notes": [
                    {"t": 0.0, "d": 1.5, "p": 69, "v": 78},
                    {"t": 1.5, "d": 0.5, "p": 71, "v": 74},
                    {"t": 2.0, "d": 2.0, "p": 74, "v": 82},
                    {"t": 4.0, "d": 1.5, "p": 72, "v": 76},
                    {"t": 5.5, "d": 0.5, "p": 71, "v": 72},
                    {"t": 6.0, "d": 2.0, "p": 69, "v": 80}
                ]
            },
            {
                "name": "piano_chords",
                "instrument": "warm_piano",
                "role": "chord",
                "notes": [
                    {"t": 0.0, "d": 3.8, "p": 50, "v": 62},
                    {"t": 0.5, "d": 3.2, "p": 57, "v": 58},
                    {"t": 1.0, "d": 2.8, "p": 62, "v": 60},
                    {"t": 4.0, "d": 3.8, "p": 53, "v": 64},
                    {"t": 4.5, "d": 3.2, "p": 57, "v": 60},
                    {"t": 5.0, "d": 2.8, "p": 65, "v": 62}
                ]
            },
            {
                "name": "bass_foundation",
                "instrument": "acoustic_bass",
                "role": "bass",
                "notes": [
                    {"t": 0.0, "d": 3.9, "p": 26, "v": 72},
                    {"t": 4.0, "d": 3.9, "p": 29, "v": 74}
                ]
            },
            {
                "name": "vocal_pad",
                "instrument": "vocal_hum",
                "role": "pad",
                "gain_db": -7.0,          # a bed sits under the lead; unshaped it read +9 dB against the flute
                "notes": [
                    {"t": 0.0, "d": 7.8, "p": 50, "v": 65},
                    {"t": 0.0, "d": 7.8, "p": 57, "v": 60}
                ]
            }
        ]
    }
    if ambience:
        score_content["tracks"].append({"name": "forest_texture", "instrument": "env:forest_canopy_3d", "role": "environment", "notes": []})
    with open(scores_dir / "main_score.json", "w", encoding="utf-8") as f:
        json.dump(score_content, f, indent=2)

    # 4. Generate scripts/compose_main.py (Custom composing script that authors notes, saves score, & triggers pipeline)
    compose_script_content = f'''#!/usr/bin/env python3
"""compose_main.py - Custom composition script for '{title}'.

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
SKILL_SCRIPTS = os.environ.get("MUSIC_SKILL_SCRIPTS") or "{skill_scripts_str}"

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

score_data = {{
    "title": "{title}",
    "bpm": BPM,
    "ts": [bb, 4],
    "key": "D",
    "mode": "dorian",
    "space": "{slug}_room",
    "mix_preset": "{slug}_mix",
    "dynamics": [[0.0, 0.45], [8.0, 0.60], [16.0, 0.85], [24.0, 0.95], [28.0, 0.70], [total_beats, 0.40]],
    "master": {{"lufs": -16.0, "true_peak": -1.5, "tone": "warm"}},
    "tracks": [
        {{"name": "flute_lead", "instrument": "lead_flute", "role": "melody", "notes": theme}},
        {{"name": "piano_arps", "instrument": "warm_piano", "role": "chord", "notes": piano_notes}},
        {{"name": "acoustic_bass", "instrument": "acoustic_bass", "role": "bass", "notes": bass_notes}},
        {{"name": "vocal_pad", "instrument": "vocal_hum", "role": "pad", "notes": pad_notes}}
    ]
}}
if {ambience!r}:      # ambience only when the user asked for it
    score_data["tracks"].append({{"name": "forest_env", "instrument": "env:forest_canopy_3d", "role": "environment", "notes": []}})

with open(SCORE_JSON, 'w', encoding='utf-8') as f:
    json.dump(score_data, f, indent=2)

print(f"[OK] Wrote declarative score to: {{SCORE_JSON}}")

if __name__ == '__main__':
    pipe = pipeline.MusicPipeline(verbose=True)
    pipe.execute(SCORE_JSON, out_wav=OUT_WAV, out_midi=OUT_MIDI, json_report=REPORT_JSON)
'''
    (scripts_dir / 'compose_main.py').write_text(compose_script_content, encoding='utf-8')

    # 2. Generate scripts/analyze_music21.py from template
    tmpl_src = SKILL / 'templates' / 'analyze_music21_template.py'
    if tmpl_src.exists():
        shutil.copy(tmpl_src, scripts_dir / 'analyze_music21.py')
    
    # 3. Research stub: honest placeholder; the pipeline blocks until research_kb.py + web sources replace it
    research_content = f"""# Research: {title}

TODO. Not researched yet. Run:

    python scripts/research_kb.py {proj_dir.as_posix()} --topic "<topic>" --tags <culture,genre,...>

then add web sources under "Web research" in the generated reports/research_<topic>.md.
The pipeline will not render until a note cites the knowledge base and lists at least one web URL.
"""
    (reports_dir / 'research_brief.md').write_text(research_content, encoding='utf-8')

    # 4. Generate STATUS.md
    status_content = f'''# Project Status: {title}

## Flow (SKILL.md): tick each step, note decisions below
- [x] 1. Project scaffolded (direction/ presets/ scores/ midi/ stems/ reports/ scripts/ out/)
- [ ] 2. Research: `research_kb.py` note citing the knowledge base + web sources (reports/research_<topic>.md);
      for every ambience or effect the score uses: `--sounds a,b` and fill each "Real-world references" section (2 sources, licence)
- [ ] 3. Direction sheet filled (direction/direction_sheet.json)
- [ ] 4. Presets for every non-built-in instrument / vocal (presets/instruments, presets/vocals), each ambience (presets/environments)
      and tuned one-hit effect (presets/sfx), each listing its "sources"
- [ ] 5. Score written (scores/*.json) referencing presets by exact name
- [ ] 6. `pipeline.py scores/<title>_score.json --project .` renders out/master.wav, midi/, stems/, reports/ci_report.json
- [ ] 7. Revise one lever at a time until 0 FAIL (max 5 attempts, then report)
- [ ] 8. listen.py on out/master.wav; deliver

## Rules
1. Never monolithic: sound and space in presets/, notes in scores/, intent in direction/.
2. Sample presets here (lead_flute, warm_piano, ...) are examples: rename or replace them.
3. The mixer applies azimuth (pan), distance (air filter, level, reverb send), width and one shared room.
4. The mix preset owns the strategies: gain_staging (legacy|adaptive), dynamics.engine (pedalboard|dsp),
   spectral profiles, space, sidechain.mode (legacy|explicit|off) and the mastering profile.
   `python scripts/presets.py show mix default` prints every key with its shipped value.
   `spatial.elevation` and `spatial.space` are stored but not applied.

## Decisions / feedback
'''
    (proj_dir / 'STATUS.md').write_text(status_content, encoding='utf-8')

    # 5. Generate project requirements.txt from template
    req_tmpl = SKILL / 'templates' / 'requirements_template.txt'
    if req_tmpl.exists():
        shutil.copy(req_tmpl, proj_dir / 'requirements.txt')
    elif (SKILL / 'requirements.txt').exists():
        shutil.copy(SKILL / 'requirements.txt', proj_dir / 'requirements.txt')

    print(f"\nSuccessfully scaffolded music project at: {proj_dir}")
    print("  Structure created:")
    print("    requirements.txt       (Project dependencies for uv pip install)")
    print("    direction/             (Direction sheets & 3D spatial staging)")
    print("      direction_sheet.json")
    print("    presets/               (Modular sound design & spatial definitions)")
    print("      instruments/         (lead_flute.json, warm_piano.json, acoustic_bass.json)")
    print("      vocals/              (vocal_hum.json)")
    print("      spaces/              (<title>_room.json: write its character sentence)")
    print("      mix/                 (<title>_mix.json: character sentence + the strategies: gain staging, dynamics,")
    print("                            spectral profiles, space, sidechain, mastering profile; role_chains written out)")
    print("      sfx/                 (one-hit effects; empty: the shipped defaults work until you tune one)")
    print("      gate/                (this piece's gate profile: gate_profiles.py new <name> --project <dir>)")
    if ambience:
        print("      environments/        (forest_canopy_3d.json)")
    print("    reference/             (measured real-sound metrics: reference/<slug>.json; empty until the research measures one)")
    print("    scores/                (Declarative score JSONs referencing presets)")
    print("      main_score.json")
    print("    scripts/               (Custom composition & dynamic music21 analysis)")
    print("      compose_main.py")
    print("      analyze_music21.py")
    print("    reports/               (Research preflight & CI/CD quality reports)")
    print("      research_brief.md")
    print("      ci_report.json")
    print("    metadata.json           (standard delivery tags: overrides only; the defaults live in the skill)")
    print("    out/                   (Master WAV and exported MIDI)")
    print("      master.wav           (copy of the newest certified version)")
    print("      master_vNN.wav       (every certified version; earlier ones are never overwritten)")
    print("      versions.json        (each version with the gate failures it cleared)")
    print("    STATUS.md              (Project tracking and decisions)")
    print("\nNext: 2) research_kb.py  3) fill direction/  4) presets  5) score  6) pipeline.py (blocked until 2-4 are done):")
    print(f"  {venv_python(SKILL / '.venv')} {skill_scripts_str}/pipeline.py {scores_dir / 'main_score.json'} --project {proj_dir}")


def main():
    ap = argparse.ArgumentParser(description='Set up the music-generator skill or scaffold a music project.')
    ap.add_argument('--ambience', action='store_true', help='with --new-project: also scaffold an environment preset and track (only when the user asked for ambience)')
    ap.add_argument('--new-project', metavar='DIR', help='scaffold a project: direction/ presets/ scores/ midi/ stems/ reports/ scripts/ out/ STATUS.md')
    ap.add_argument('--title', default='New Composition', help='title of the piece when scaffolding a new project')
    ap.add_argument('--ears', action='store_true', help='also install earshot and download its models (about 1 GB)')
    ap.add_argument('--venv', default=str(SKILL / '.venv'), help='where the virtual environment goes (default: .venv)')
    ap.add_argument('--earshot-home', default=str(EARSHOT_HOME), help='where earshot keeps its models')
    args = ap.parse_args()

    if args.new_project:
        scaffold_project(args.new_project, title=args.title, ambience=args.ambience)
        return

    if sys.version_info < (3, 10):
        sys.exit('Python 3.10 or newer is needed. Found ' + sys.version.split()[0])
    venv = Path(args.venv).resolve()
    uv = shutil.which('uv')
    if uv is None:
        print('uv is not installed, so this uses python -m venv and pip (slower). '
              'For faster installs: pip install uv', flush=True)

    print(f'\n[1/5] virtual environment: {venv}', flush=True)
    make_venv(venv, uv)

    print('\n[2/5] core packages (requirements.txt)', flush=True)
    install(venv, uv, '-r', SKILL / 'requirements.txt')

    print('\n[3/5] tinysoundfont (--no-deps)', flush=True)
    install(venv, uv, '--no-deps', TINYSOUNDFONT)

    if args.ears:
        print('\n[4/5] earshot: torch (CPU), then requirements-ears.txt, then the models', flush=True)
        install(venv, uv, '--index-url', TORCH_INDEX, TORCH)
        install(venv, uv, '-r', SKILL / 'requirements-ears.txt')
        home = Path(args.earshot_home).expanduser().resolve()
        home.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, EARSHOT_HOME=str(home))
        run([venv_python(venv), '-m', 'earshot', 'doctor', '--fetch'], env=env)
    else:
        print('\n[4/5] earshot: skipped (run with --ears to let listen.py hear the music)', flush=True)

    print('\n[5/5] SoundFont and render smoke test', flush=True)
    smoke_code = (
        "import sys, os; sys.path.insert(0, 'scripts'); "
        "import soundbank, render_natural as rn, numpy as np; "
        "print('SoundFont:', soundbank.ensure_soundfont()); "
        "score = dict(bpm=90, tracks=[dict(name='p', instrument='piano', role='melody', "
        "notes=[dict(t=0, d=1, p=60, v=0.7), dict(t=1, d=1, p=64, v=0.7)])]); "
        "stems, _ = rn.build_stems(score, verbose=False); "
        "peak = float(np.abs(stems['p']).max()); "
        "print('Smoke test OK' if peak > 0.001 else 'Smoke test failed: silent output'); "
        "sys.exit(0 if peak > 0.001 else 1)"
    )
    run([venv_python(venv), '-c', smoke_code], cwd=SKILL)

    # measured head data for "binaural": "hrtf" (about 150 MB once, kept in scripts/spatial_hrtf/data). Not fatal: without it the mixer uses spatial.py.
    print('\n[+] head data for binaural rendering (scripts/spatial_hrtf, FABIAN set, CC BY 4.0)', flush=True)
    r = subprocess.run([str(venv_python(venv)), '-m', 'spatial_hrtf.data'], cwd=SKILL / 'scripts')
    if r.returncode != 0:
        print('  head data not downloaded (offline?). Run later:  python -m spatial_hrtf.data   (from scripts/). Until then "hrtf" falls back to spatial.py.')

    activate = (r'.venv\Scripts\activate' if os.name == 'nt' else 'source .venv/bin/activate')
    print('\nSetup finished.')
    print(f'  Activate: {activate}   (or call {venv_python(venv)} directly)')
    print('  Try:      python scripts/compose.py --list')
    if args.ears:
        print(f'  Listen:   python scripts/listen.py cue.wav --direction templates/direction_sheet.json')
        print(f'            (models live in {Path(args.earshot_home).expanduser()}; listen.py finds them there)')
    else:
        print('  Listen:   run again with --ears to enable listen.py')


if __name__ == '__main__':
    main()
