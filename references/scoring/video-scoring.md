---
title: Video scoring
summary: Scoring to picture at three timescales, with its own gate rows, its own presets and a reel assembled from certified cues.
tags: [video, picture, sync, cut, dialogue, fps, hits, spotting, film, reel, gating]
load_when:
  - the brief has a video file or a film reel
  - a video gate row fails
  - a film project needs scaffolding
---

# Scoring to picture

Music written against a film: the picture sets the tempo, the density and the hits; the film's own
speech stays intelligible; and the finished file carries the original video stream untouched.

```bash
python3 scripts/setup_project.py --new-film D:/films/glaciers --title "Glaciers" --fps 25
python3 scripts/video_score.py --video clips/reel1.mp4 --project D:/films/glaciers/cues/M01_open --brief "calm documentary"
python3 scripts/video_score.py --selftest        # the video path proves it works, and that it can fail
python3 video-mixer/deliver/reel.py D:/films/glaciers --reel 1 --mux
```

## Two project shapes

| Shape | For | Scaffold |
|---|---|---|
| music project | one piece, no picture | `setup_project.py --new-project <dir>` |
| **film project** | a reel, several cues, a spotting list | `setup_project.py --new-film <dir> --fps 25` |

A film project is not a music project with extra folders: its unit of work is a **cue**, and each
cue folder is a complete music project, so every rule in `AGENTS.md` applies to it unchanged.

```
my-film/
  film.json                 reel facts: fps, picture, duration, delivery, reels
  spotting/                 cutlist.json, cuesheet.json, notes.md
  analysis/                 reel_<id>_probe.json, reel_<id>_context.json
  cues/<id>/                one complete music project per cue
  deliver/                  reel_<id>_program.wav, reel_<id>_report.json, the muxed file
```

The reel **places and aggregates**; it never re-scores, re-times or rewrites a cue's report.

## What runs, in order

| Stage | File | Does |
|---|---|---|
| probe | `video-mixer/video_probe.py` | ffprobe facts, `scdet` cuts, per-frame luma / motion / centre / warmth |
| context | `video-mixer/context.py` (+ `analysis/shot_scale.py`, `analysis/speech.py`) | the three timescales below, plus the fitted cut-grid phase |
| direction | `video-mixer/video_direction.py` | context → sections with music, hits with a class, score |
| score | `compose.py` (unchanged) | the music, rendered by `pipeline.py` with every normal music rule |
| program | `video-mixer/video_program_mix.py` | voice chain, bed under speech, band duck, swell, master in the declared gating mode |
| **gate** | `video-mixer/gate/pass_.py` | every picture row, **inside** the pipeline's own certification |
| mux | `video-mixer/video_mux.py` | `-c:v copy` + audio, then proves the video stream is identical |
| reel | `video-mixer/deliver/reel.py` | cues placed in reel time, one program, one aggregate verdict |

The music rows and the picture rows run in the same list, at the same moment, and produce one
verdict. There is no `attach()` that rewrites an already-certified report.

### Who owns what

| Path | Owns | Does not |
|---|---|---|
| `video-mixer/video_probe.py` | ffprobe facts, `scdet` cuts, per-frame luma / motion / centre / warmth | choose music |
| `video-mixer/analysis/shot_scale.py` | block contrast → subject box → `wide` / `medium` / `close` / `insert` | set the density (the mapping preset does) |
| `video-mixer/analysis/speech.py` | speech activity (presence) and the per-sample mask | judge intelligibility |
| `video-mixer/context.py` | the three timescales, `cut_phase`, `silence_windows` | write a direction sheet |
| `video-mixer/video_direction.py` | context → sections, hits with a class, a score | invent feel, purpose or motifs |
| `video-mixer/video_program_mix.py` | voice chain, bed under speech, band duck, swell, master in the declared gating mode | touch the music's own mix preset |
| `video-mixer/gate/rows.py` | one function per `video.*` row | decide which rows apply |
| `video-mixer/gate/pass_.py` | loads the five `film/*` presets, runs the rows, returns `(rows, extras)` | re-judge a certified report |
| `video-mixer/deliver/reel.py` | certified cues placed in reel time, one program, one aggregate verdict | re-score or re-time a cue |
| `video-mixer/video_gate.py` | the old import path, as a thin wrapper | hold a second verdict |
| `scripts/video_gate_pipeline.py` | the picture rows a music render can answer alone (no program supplied) | replace the program-side rows |

A change belongs in the module that owns the number. A new threshold goes in a `film/*` preset with its
`provenance`; a new row goes in `gate/rows.py` and `scripts/gate_profiles.py`; a new placement rule goes in
`video_direction.py`; nothing in `video-mixer/` writes into a cue's score.

## The three timescales

The picture is not four scalars. `analysis/reel_<id>_context.json` holds:

| Timescale | Answers | Fields |
|---|---|---|
| **reel** (s–min) | what kind of film is this | shots, scenes, palette temperature, motion profile, speech share, mean/range luma |
| **scene** (2–40 s) | what is this shot | `shot_scale`, motion + direction, luma, speech activity, energy, `music_gap` |
| **motion beat** (frames) | where does the picture pulse | peaks with strength and direction, plus `cut_phase` (bpm, offset, confidence, worst residual) |

`shot_scale` implements the rule the direction guide already states: the further the camera, the
bigger the music may be (`references/workflow/music-direction.md` §2.4). A close-up caps the density;
a wide allows the band. The cap is a preset table, and the gate measures the density that actually
resulted, not the intention.

`text_on_screen` is `null` and says "not measured": nothing in this skill detects text, and a
measurement that is not made must not be invented.

## The presets, split by concern

`references/data/presets/film/` holds five files; a project overrides only the one it needs:

| Preset | Holds |
|---|---|
| `analysis.json` | probe rate, cut detection, shot-scale thresholds, speech thresholds, phase fit, scene grouping |
| `mapping.json` | tempo from cuts, luma/palette → mode, centre and direction → pan, shot scale → density, layers per density |
| `hits.json` | sounds, budget, gap, **hit classes** (`dead_on`, `reaction`) and their windows |
| `dialogue.json` | voice chain, bed, duck, speech band, intelligibility band, audited loudness difference |
| `delivery.json` | master profiles **with an explicit gating mode**, mux target, gate tolerances |

Every new number carries a source or the words "starting value" in that preset's `provenance`.

The one-cue `references/data/presets/video/default.json` still supplies the room (`staging`) and the
mix preset; it remains readable as a merged view for compatibility.

## Hit classes

An accent is not always on the frame:

| Class | For | Placement |
|---|---|---|
| `dead_on` | a cut, an explosion, a slam | on the frame (ITU-R BT.1359: +45 ms early, −125 ms late) |
| `reaction` | a line, a look, a reveal | *after* the audience's reaction time (about 350 ms), because the moment has to be absorbed first |

`video.hit_class` fails an accent that drifts out of its own class window, and `video.cut_sync` and
`video.motion_sync` judge the two sync families separately: a cut is hard, a movement inside a shot is
softer (music-to-motion synchrony is detected inside about 300–450 ms).

## The gate rows

Registered in `scripts/gate_profiles.py`; chosen by a `video_*` profile.

| Row | Measures | Protected |
|---|---|---|
| `video.duration_lock` | program length against the picture, ±`duration_tolerance_ms` | yes |
| `video.cut_sync` | a cut hit against its cut; early and late limits separate | no |
| `video.motion_sync` | a movement hit against its movement beat | no |
| `video.hit_class` | a delayed accent lands after its moment; a dead-on one does not drift | no |
| `video.grid_phase` | the cuts' worst residual against the fitted grid, in frames | no |
| `video.hit_density` | accents per minute, and the share of adjacent cut pairs both hit (Mickey Mousing) | no |
| `video.cue_silence` | music energy where the spotting asked for silence | no |
| `video.dialogue_snr` | music level under speech | no |
| `video.dialogue_band` | music energy in 1–4 kHz under speech | no |
| `video.shot_scale` | realised density against the camera distance | no |
| `video.master_compliance` | delivered loudness **in the declared gating mode**, and true peak | yes |
| `video.gating_mode` | the declared gating mode was the mode actually measured | yes |

Profiles: `video_basic` (no speech), `video_dialogue`, `video_underscore` (sparse, dialogue strict),
`video_montage` (many short shots, budget relaxed with a written reason), `video_trailer`.
`video_cinematic` is kept for the one-cue path.

Sign convention: `video.dialogue_snr` and `video.dialogue_band` both print `voice − music`, so a positive
number means the music sits *under* the voice and a bigger number is a quieter bed. `film/delivery.json`
stores `dialogue_band_min_db: 12.0` in that convention; the row's range in `gate_profiles.py` follows it.

## Gating: the fix this gate row exists for

A delivery that says `loudness_mode: dialogue` is measured on the **speech-active part only**
(ITU-R BS.1770-1 practice, what Netflix grades a print master on), not on the whole program. The
master and the gate use the same speech mask, so they cannot disagree:

- `mixer.dialogue_gated_lufs(y, sr, mask)` measures the speech segments;
- `video_program_mix.master(..., loudness_mode='dialogue', speech_mask=...)` converges on that target;
- `video.gating_mode` fails a delivery whose declared gate was not the measured one;
- `video.master_compliance` fails a dialogue target when no speech was found, instead of grading a
  dialogue target on a full-program number.

Platform targets live in `film/delivery.json` with their source: Netflix −27 LKFS ±2 dialogue-gated,
−2 dBTP; EBU R128 −23 LUFS, −1 dBTP; ATSC A/85 −24 LKFS ±2; Prime −24 full program; YouTube ≈ −14 on
playback.

## The direction sheet

The sheet keeps the shape of `templates/direction_sheet.json`, so a cue to picture and a cue to a
brief are read the same way. What the picture fills:

| Block | Filled from |
|---|---|
| `tempo_bpm`, `tempo_method` | the median cut interval (1/2/4/8 beats), frame-locked when asked |
| `key`, `mode` | the mapping preset; luma decides, palette only breaks a tie |
| `sections` | one per scene: `shot_scale`, `energy`, `density`, `allowed_roles`, `action`, `music` |
| `hits`, `hits_at` | cuts (hard) and movements (soft), each with `kind`, `sync`, `class`, `offset_s` |
| `video.cuts`, `cut_phase`, `scenes`, `silence_windows` | the context artifact |
| `video.dialogue` | whether speech was **measured**, and the duck policy |
| `video.master_profile` | the delivery preset's own profile |

Everything else (`job`, `feel`, `point_of_view`, `motifs`, `mix_intent`) is still a hand decision: the
probe cannot know what the film is about. `sections[].density` is the allowance; the score is thinned
to it by `apply_section_arrangement()`, and the realised density is what the gate measures.

## Honest limits

- Cuts come from `scdet`, which misses fades and dissolves. A deep detector (TransNetV2 class,
  F1 0.962 on BBC Planet Earth) is described in `film/analysis.json` but is **not shipped**: it needs
  TensorFlow and 1.4 GB of weights. `cut_source` in the report says which detector ran.
- Shot scale is a heuristic (block contrast, subject bounding box, `analysis.shot_scale.peak_frac`
  keeping a flat background out of the subject). It is wrong on shallow focus and on text-over-graphics;
  a scene can be pinned by hand in `spotting/cutlist.json` and the context records which source won.
- Speech activity is a measurement of *presence*, not a demix. `video.dialogue_snr` is a loudness
  difference, not an intelligibility score.
- `motion_sync`, `grid_phase`, `shot_scale` and `dialogue_band` thresholds are starting values until
  measured on real reels. They may only be relaxed after measurement, with the reason written down.
- Nothing in the video path has been auditioned. `listen.py` judges the music bed, not the program
  under speech.
- The audio is always re-encoded at mux; only the video stream is copied, and that copy is proven by
  comparing codec, size, pixel format and frame count before and after.
