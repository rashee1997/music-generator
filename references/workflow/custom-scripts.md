---
title: Custom scores
summary: The score schema and the helper calls that build one: tracks, notes, hits, arcs and tempo changes.
tags: [score, json, track, notes, direct, schema, custom]
load_when:
  - writing a score by hand or with helpers
  - a score fails schema validation
---

# Writing custom music scripts (for any kind of work)

`compose.py` covers common moods. For everything else (a named theme, a chord sheet the user gave you, music that
must hit exact timecodes, a unique line-up, game layers, a jingle, a reworked arrangement) write a custom Python
composition script.

## Project layout

A custom script is optional. It may only generate the score JSON; sound and space live in `presets/`, intent in
`direction/` (enforced by `scripts/project_gate.py`). Every project follows this layout (`setup_project.py --new-project` makes it):

```
<project>/
├── scripts/
│   ├── compose_main.py          # ALL custom composing scripts MUST live here (NEVER in reports/ or root)
│   └── analyze_music21.py       # Flexible project-specific music21 quality gate script
├── reports/
│   ├── research_<topic>.md      # Ethnomusicological, acoustic, and DSP research notes (NO CODE)
│   └── ci_report.json           # Automated CI/CD quality gate scoreboard output
├── out/master.wav               # Final rendered master audio file
├── midi/<score>.mid             # Exported MIDI score
├── stems/<track>.wav            # One stem per track, trimmed to where it sounds; stems/stems.json holds each start
└── STATUS.md                    # Project milestones, decisions, and progress tracking
```

### Critical Rules for AI Agents:
1. **Composing Scripts in `scripts/` ONLY:**
   - If you need a composing script (`compose_main.py`, `compose_theme.py`, ...), keep it in `<project>/scripts/`, never in `reports/` or the project root.
2. **`reports/` is for Research Notes & CI Reports ONLY:**
   - Put ethnomusicological, psychoacoustic, and DSP research in `reports/research_<topic>.md`.
   - The automated CI/CD quality gate writes `reports/ci_report.json`.
   - Absolutely no Python code belongs in `reports/`.
3. **`out/` is for Final Deliverables ONLY:**
   - `out/master.wav`; the MIDI goes to `midi/` and the stems to `stems/`.
4. **Flexible `music21` Quality Gate in `scripts/`:**
   - Place dynamic music theory checks in `<project>/scripts/analyze_music21.py`.
   - `pipeline.py` automatically detects and executes this script during Stage 6, merging custom musical analysis rows into the final Quality Scoreboard.

### Scaffolding in One Command:
```bash
python scripts/setup_project.py --new-project <project_path> --title "My Piece"
```

The loop is the same as in `music-direction.md`: decide, write, direct, render, listen, revise.

## 1. The steps

1. **Decide** from the direction sheet: feel, arc, key and mode, tempo, form, instruments, loop, voice-over, hit points.
   Read the brief's words first: the mood sets mode and tempo, and the modifiers (`slow`, `reverb`, `sparse`,
   `driving`) set energy, room and density. If you call `compose.compose(brief)`, it reads `emotion`, `scene`,
   `style`, `notes`, `energy`, `space` and `tempo_scale` for you and reports the reading in `meta.mood_notes`
   (`emotion-and-scoring.md` section 1a).
2. **Write notes**: dicts `{"t": beat, "d": beats, "p": MIDI int, "v": 0..1}`, plus optional `"art": "staccato"` or
   `"legato"`. Drum notes use names: `kick snare hat_closed hat_open ride crash tom_floor shaker clap rim` (see
   `soundbank.DRUM_KEYS`). Beats are quarter notes unless the time signature says otherwise.
3. **Assemble** a score dict (below).
4. **Direct** with `scripts/direct.py`: `add_pulse`, `add_line`, `add_notes`, `set_gain`, `set_arc`, `copy_track`,
   `remove_track`, `tempo`.
5. **Render**: `python3 scripts/render_natural.py score.json --out cue.wav` (masters to the score's `master` target).
6. **Listen**: `python3 scripts/listen.py cue.wav --direction sheet.json`, then revise one lever and repeat.

## 2. Score format

```python
score = dict(
  title="...", bpm=72, ts=[4, 4], seed=7,
  humanize="natural",                     # tight | natural | loose | rubato | {dict}
  swing=0.5, rubato=0.03, ritard=0.35, ritard_beats=6,
  tempo_points=[[0, 72], [32, 60]],       # optional tempo map (beat, bpm)
  fermata=[(48, 1.5)],                    # hold beat 48 for 1.5 s extra
  dynamics=[[0, .4], [16, .9], [32, .3]], # global loudness arc 0..1 by beat (the emotion)
  room="hall",                            # reverb room (mixer.ROOMS) or "none"
  mix=dict(reverb_return=1.0),            # 1.5 for a "reverb mix"; 0.6 for dry and close
  meta=dict(mood_notes=["read: dreamy, slow, large_hall"]),   # what you read from the brief; printed by describe()
  master=dict(lufs=-16, true_peak=-1.5, tone="warm"),   # tone: neutral | warm | bright
  loop_seconds=None,                      # set for gapless loops (and rubato=0, ritard=0)
  tracks=[dict(name="cello", instrument="cello", role="melody", notes=[...],
               gain_db=-3, pan=0.2, reverb=0.2, widen=0.0,
               eq=[dict(type="peak", f=3000, gain=-3, q=1)], comp=dict(thr=-22, ratio=2.5),
               vibrato=dict(depth_cents=22, rate_hz=5.4, delay_ms=260), expression="bow",
               pedal="auto", detune_cents=0, humanize="loose", strum="alt",
               dynamics=[[0, 1], [16, .6]])],
)
```
Instrument strings: GM names (`python3 scripts/soundbank.py --list`) or `"clone:path"` for a cloned instrument.
Roles: `melody counter chord pad bass arp drum fx` (they set the humanizing and the mix defaults).

### Deliverable formats (`output_targets`)

The score says which files to build; the engine builds only those. Add one key:

```python
score["output_targets"] = "stereo"                       # one target
score["output_targets"] = ["immersive_7_1", "stereo"]    # these, in this order; the first is the certified master
score["output_targets"] = "all"                          # every target the engine can build
# absent: the default preset's list (references/data/presets/outputs/_default.json)
```

Targets ship as presets of the kind `outputs` (`references/data/presets/outputs/`): `stereo`, `binaural`,
`immersive_7_1` (8 channels, ITU-R BS.2051 System H), `immersive_7_1_4` (12 channels, System J) and
`immersive_7_1_2` (10 channels, System I). Each preset carries
its channel count, channel order, file name, true-peak ceiling and the renderer that builds it; the loudspeaker
positions are presets of the kind `layouts`. A project adds a format (7.1.2, a room-specific ring) by writing
`<project>/presets/outputs/<name>.json` and `<project>/presets/layouts/<name>.json` - no Python change.

- A target whose `renderer` is null is defined but cannot be built yet. Naming it in the score is a **blocking**
  problem (the render never starts); `"all"` lists it as skipped. There is never a silent downgrade to stereo.
- The shipped renderers are `mix_master` (the stereo bus), `spatial` (the discrete bus in `spatial_engine/render.py`,
  which reuses `mixer.mix_stems` for every track decision and only changes the summing target) and `binaural` (the same
  mix with the head-related route on). A project target may name any of the three.
- The legacy score key `"outputs"` and the aliases `7.1` / `7.1.4` still resolve.
- The CLI overrides the score for one run: `--targets stereo` or `--targets all` (comma separated).
- The certified master is `out/<file of the first selected target>`, e.g. `out/master.wav` for stereo.
- The gate only checks formats that were requested: `scripts/spatial_gate.py` runs the target's ceiling and the
  layout's low-frequency stopband, surround-energy window and height ceiling on the file that was delivered.

## 3. Helpers (import from `scripts/`)

| Module | Useful calls |
|---|---|
| `pipeline` | `MusicPipeline().execute(spec, out_wav, ...)`: unified master orchestrator running composition, linting, rendering, mastering and CI quality checking |
| `direct` | `add_pulse(score, start, end, gain_db, dyn)`, `add_line(score, name, instrument, at_beat, phrase, ...)`, `add_notes`, `set_gain`, `set_arc`, `remove_track`, `copy_track(score, name, new, transpose, shift_beats)`, `tempo(score, bpm)` |
| `theory` | `Key("D","dorian")`, `key.pitch(degree)`, `parse_progression(key, "i-VI-III-VII")`, `voice_lead(chord, prev, lo, hi)`, `bass_note`, `TEXTURES[name](voicing, bar_beats, vel, rng)` (block, half, arp8, arp16, alberti, fingerpick, pulse, comp, strum, waltz, ostinato, sparse), `bass_line(kind, ...)`, `drum_bar(kind, bb, vel, rng, fill, crash)`, `make_phrase`, `vary_phrase`, `harmony_line`, `clamp_register`, `note_name` |
| `compose` | `compose(brief)` (a score from a preset; edit it), `add_hit_points(score, hits, bpm, bb, key, rng)`, `export_midi(score, path)`, `fit_tempo_and_bars` |
| `humanize` | `TempoMap`, `humanize_track`, `event_stats`, `PRESETS` |
| `render_natural` | `build_stems(score)`, `render_track`, `REPORT` |
| `mixer` | `mix_and_master(score, stems, out)`, `mix_stems`, `master_chain` (`BrickwallLimiter`), `reverb_bus` (`NoiseGate`), `make_ir`, `duck_gain` |
| `vocals` | `render_choir`, `sing`, `add_vocal_harmonies` (`PitchShift`), `add_vocal_chorus` (`Chorus`), `apply_vocal_dsp` |
| `sfx` | `make`, `timeline`, `synth`, `apply_lofi` (`Bitcrush`/`GSM`/`MP3`), `apply_ladder_filter` (`LadderFilter`), `apply_delay` (`Delay`) |
| `environment` | `render_environment_preset`, `apply_environmental_acoustics` (`Convolution`, `HighShelfFilter`, `LowpassFilter`) |
| `spatial` | `spatialize_stem(audio, azimuth, elevation, distance, space, ...)`, `brown_duda_head_shadow`, `kuhn_itd`, `apply_near_field_divergence`, `render_trajectory`, `encode_ambisonic_bformat`, `decode_ambisonic_to_binaural` |
| `clone_instrument` | `load_instrument(path)`, `render_events(inst, events)` (for custom rendering) |
| `video_program_mix` | `build(voice, music, sfx, cfg['mix'])` (music under narration) |
| `listen` | `python3 scripts/listen.py cue.wav --direction sheet.json` (measurements and earshot) |

## 3b. Pedalboard DSP Architecture in Custom Scripts

For real-time and offline audio manipulation in custom scripts, use **Spotify's Pedalboard** (`import pedalboard as pb`).

### 1. Audio Shape Contract
Pedalboard requires NumPy float32 arrays formatted as `(channels, samples)` (`[2, N]` or `[1, N]`). When interfacing with `soundfile` or `scipy.signal` (`[N, 2]`):
```python
import pedalboard as pb
import soundfile as sf

audio, sr = sf.read("stem.wav")  # shape: (N, 2)
board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=80.0),
    pb.Compressor(threshold_db=-20.0, ratio=2.5),
    pb.BrickwallLimiter(ceiling_db=-1.5, true_peak=True)
])
# Transpose to (2, N) for pedalboard, then back to (N, 2) for soundfile
processed = board(audio.T.copy(), sr).T
sf.write("processed.wav", processed, sr)
```

### 2. Loading VST3 plugins
Any commercial or open-source VST3 instrument or effect plugin can be loaded and automated:
```python
vst = pb.load_plugin("C:/Program Files/Common Files/VST3/Surge XT.vst3")
# Inspect parameters
print(vst.parameters.keys())
vst.cutoff = 1200.0
board = pb.Pedalboard([vst])
out = board(audio.T.copy(), sr).T
```

## 3a. The six acoustic laws (a hand-written score must follow them too)

`pattern_audit.py --strict score.json` checks these, and `quality_gate.py` prints them as rows. The renderer applies
them to composed scores; when you write notes by hand, do the same:

1. **Voice and roll chords** (`chord_voicing_and_strum`). `theory.voice_lead` / `theory.TEXTURES['block']` already
   lead the top note and roll the chord; if you write a block by hand, give the top note the most velocity and start
   the notes about 8 ms apart.
2. **Do not choke plucked notes** (`choked_resonance`). Guitar, harp, kora, oud, guzheng: 0.6-1.0 beat notes with
   `"art": "legato"`; keep staccato under half the part.
3. **No machine-gun runs** (`machine_gun_percussion`). A repeated same-pitch run needs at least 10 % velocity spread
   around its own mean, alternating accents, and `(step/N) ** 1.6` on an ascending fill.
4. **No phase-locked flams** (`percussion_flam`). Put a clap or tambourine 0.02-0.028 beats after a snare or rim.
5. **No low mud** (`low_interval_mud`). Below F3 (MIDI 53), keep 5+ semitones between voices (root-5th-10th).
6. **One shared room** (`spatial_glue`). Do not leave one acoustic track at `reverb: 0` in a wet score.

Dynamics are relative: a track's velocity sd should be at least 5 % of its mean, and the whole-piece `dynamics`
curve should move by 25 % of its mean. A quiet mood is not a flat one.

## 4. Recipes

**A. Start from a preset, then direct it.** The fastest good base:
```python
import json, sys; sys.path.insert(0, 'scripts')
import compose, direct
score = compose.compose(dict(emotion='nostalgic', genre='acoustic', duration_s=75, key='G', seed=3))
direct.remove_track(score, 'drums')
direct.set_gain(score, 'lead', -1)
json.dump(score, open('score.json', 'w'))
```
Then `render_natural.py score.json --out cue.wav`.

**B. A chord sheet from the user** ("Am F C G, verse x2, then chorus"):
```python
key = Key('A', 'aeolian'); chords = parse_progression(key, 'i VI III VII')
```
Give each section its own texture (`sparse` verse, `arp8` pre-chorus, `strum` or `pulse` chorus) and its own
dynamics. Write the notes for each section, then concatenate with the right `t` offsets.

**C. Music to exact timecodes (video).** `beat = seconds x bpm / 60`. Choose a bpm so that a bar lasts a round
number of seconds (`compose.fit_tempo_and_bars`). Put bar lines on the cuts. Use `add_hit_points` for `impact`,
`rise` and `silence`, and check the hits with `listen.py --direction` (`hits_at` in the sheet).

**D. Theme and variations (leitmotif).** Write `theme` once, then derive:
```python
theme_minor = [dict(n, p=n['p'] - 1) for n in theme]                 # sad: lower the 3rd
theme_fast  = [dict(n, t=n['t'] / 2, d=n['d'] / 2) for n in theme]   # tense: twice as fast
theme_low   = [dict(n, p=n['p'] - 12) for n in theme]                # darker: an octave down
```
A canon: `direct.copy_track(score, 'theme', 'theme2', shift_beats=4)` on another instrument. See the template.

**E. Game layers that crossfade.** Render the same key, tempo and seed three times with `intensity` 0.3, 0.6 and 0.95
and `loop=True`. Export each as WAV; they line up bar for bar. Full steps: `scene-recipes.md` section 6.

**F. Jingle or sting (3-10 s).** A short memorable figure, a strong final chord with a long `d`, no ritard, and the
hit at the end. For a logo, `rise` then `impact`. `scene-recipes.md` section 7.

**G. Arrangement of a known tune.** Only for public-domain tunes or a melody the user wrote or gave you. Write the
notes by hand. Do not reproduce a copyrighted melody from memory.

**H. Mix someone else's stems.**
```bash
python3 scripts/mixer.py stems/ --mix mix.json --out final.wav
```
with `mix.json` like `{"tracks": [{"name": "gtr", "role": "chord", "gain_db": -6, "pan": -0.3, "reverb": 0.15}],
"room": "hall", "master": {"lufs": -14}}`. Stem file names without `.wav` are the track names.

**I. A custom pulse or grid.** `direct.add_pulse(score, start=0, end=beat_end, gain_db=-6, dyn=[...])` puts a kick on
every beat (accented on the bar). It is the change that moved a trailer from "no pulse" to a clear grid in this
session (clarity 0.04 to 0.49). Use `humanize="tight"` for a driving groove and `"natural"` for a soft one.

**J. Custom humanize rule.** After `humanize.humanize_track` you can post-process the event list (times in seconds):
shorten notes before leaps, add a rubato at a cadence, delay a note for a sigh. Then render with your own loop; see
`render_track` in `render_natural.py` for a complete example.

**K. Listen to a state or a version.** Render each version to a WAV and run `listen.py` on each with the same sheet.
Compare the forced-choice numbers. The version that moves the target is the one to keep.

## 5. Debugging

- Silent stem: wrong instrument name (`soundbank.resolve` raises `unknown instrument`), notes past the end, dynamics at 0.
- Track too loud or quiet: change `gain_db` (it is relative after normalisation), not the note velocities.
- Thin or odd notes: outside the instrument's range (`natural-instruments.md`); transpose by octaves.
- Muddy or boomy: the fix table in `mixing-and-mastering.md`.
- Sounds like MIDI: `pattern_audit.py --strict score.json` names the rule. The usual causes are block chords on one
  sample, short plucked notes, flat repeated runs and a dry track in a wet score (section 3a).
- Too slow to render: shorter duration, fewer tracks. A 60 s piece renders in under 10 s.
- Same seed = same performance. A different seed = a different take of the same score.
- `listen.py` says "no steady beat" for a piece that should have one: add a grid with `direct.add_pulse` first.

## 6. Quality checklist before delivering

- [ ] Every target in the direction sheet is PASS, or the remaining CHECKs are named in the reply.
- [ ] `python3 scripts/pattern_audit.py score.json --strict` and `scripts/quality_gate.py score.json cue.wav` pass,
      including the six acoustic laws.
- [ ] The mood line printed by `compose.describe()` matches the brief (`meta.emotion`, `energy`, `room`, `mood_notes`);
      nothing silently fell back to `focused` or to an upbeat default.
- [ ] The mode and the tempo agree with the feel; the arc has a shape; there is an ending (ritardando, ring-out, or a clean loop point).
- [ ] The melody is the loudest layer, stays in range, breathes at phrase ends.
- [ ] The bass is low and centred; pads are high-passed; nothing stacks at the same pitch and rhythm.
- [ ] `naturalness_check` (via listen) shows no clipping and no FAIL on loudness or true peak.
- [ ] Delivered: WAV, MIDI, the sheet, the listen report in plain words, and one line on what was not checked.
