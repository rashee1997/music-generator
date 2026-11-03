---
name: "music-generator"
description: Direct and make music for a scene, a video, a game or a custom piece. Use whenever the user asks for a soundtrack, background or underscore, trailer or reveal music, a jingle or sting, a loop for a game, music under a voice-over, a custom theme, a cloned instrument from their recording, or mixing and mastering help. Real music is always made inside a project (research from the knowledge base, a direction sheet, custom presets for every non-built-in instrument or vocal, a declarative score), rendered by pipeline.py, and revised one lever at a time until every quality gate passes. Use it also when the brief is a feeling phrase ("motivational", "adventure", "slow reverb mix", "calm but corporate") or when the user says the music sounds robotic, flat, sad when it should be epic, or has no beat.
allowed-tools: Write, Read, Edit, Glob, Grep, Bash
---

# Music Generator: one project, one flow, gates until green

**Read `AGENTS.md` first** (the rule book: which references and knowledge-base files to open for which request, in what order).

You are a music director. The scripts carry out decisions; they do not make them. You cannot hear, so the
pipeline's measurements and `listen.py` (earshot) are your ears. The first render is a draft.

## The flow (do these in order, never skip one)

Run from the skill folder with its venv: `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python`.
First time on this machine: `references/setup.md`.

| # | Step | Command / file | Done when |
|---|---|---|---|
| 1 | **Create the project** | `python scripts/setup_project.py --new-project <dir> --title "<Title>"` | `<dir>` has `direction/ presets/{instruments,vocals,spaces,mix,sfx,video}/ reference/ scores/ midi/ stems/ reports/ scripts/ out/ STATUS.md` (no ambience unless the user asked: add `--ambience`) |
| 2 | **Research: knowledge base first, then web** | `python scripts/research_kb.py <dir> --topic "<topic>" --tags <culture,genre,...>`; then add web sources (TinyFish search/fetch) under "Web research". For every ambience or effect the score uses, add `--sounds a,b` and fill each "Real-world references" section (two real sources, licence, measured values) | `reports/research_<topic>.md` cites KB `document_id`s and has web sources. Detail: `references/research-step.md` |
| 3 | **Direction notes** | copy `templates/direction_sheet.json` to `<dir>/direction/direction_<title>.json` and fill it | purpose, job, duration, tempo, key/mode, feel, avoid_feel, loudness, true_peak_max, hits_at (may be `[]`), `sections` (the arc in seconds), motifs, `hits` with a reason, `mix_intent`, `delivery` and `spatial_staging` (`{name: {azimuth, distance}}`) all set; `video` block filled for a cue to picture (leave `enabled: false` otherwise). Method: `references/music-direction.md` section 2 |
| 4 | **Custom presets** | `python scripts/presets.py scaffold instruments <name> --project <dir>` (also `vocals`, `environments`, `sfx`) | every instrument or vocal that is not built in has a preset in `<dir>/presets/...` with the exact name the score uses. Each preset needs its own `spatial.azimuth` and `spatial.distance` taken from the direction sheet's staging (the gate blocks missing or shared spots). Schema: `references/spatial-presets-and-scoring.md` |
| 5 | **Score** | write `<dir>/scores/<title>_score.json` (declarative; tracks name presets, never inline EQ or spatial values). `compose.py --brief` may draft it; `templates/custom_score_template.py` for exact themes | notes, tempo, tracks present. Format: `references/custom-scripts.md` |
| 6 | **Render + CI gate** | `python scripts/pipeline.py <dir>/scores/<title>_score.json --project <dir>` | writes `out/master.wav`, `midi/<title>_score.mid`, `stems/*.wav` (each holds only where that stem sounds; `stems/stems.json` has its start; `--stems-full` for aligned full-length), `reports/ci_report.json`; exit code 0 only if Stage 6 has 0 FAIL |
| 7 | **Revise until green** | change ONE lever (`references/music-direction.md` section 6), re-run step 6 | `ci_report.json` shows 0 FAIL. Stop after 5 attempts and report what still fails |
| 8 | **Listen, then deliver** | `python scripts/listen.py out/master.wav --direction direction/<sheet>.json` | opening, climax, last 8 s checked; reply with the template below. If it prints `earshot is not installed ... SKIP`, say the ears were not run (`setup_project.py --ears` installs them) |

An `env:` track's notes say when it is audible (first note to last note, faded in and out); no notes means the whole piece, or set `"full_length": true`.

Update `<dir>/STATUS.md` after each step.

**What the pipeline enforces** (it stops with a list of every problem): scaffold folders exist; a research note
citing the knowledge base exists; the direction sheet is complete; every non-built-in instrument or vocal track has
an exact-name preset in the project, each with its own `spatial` spot that agrees with the direction sheet's `spatial_staging`; Stage 6 passes. A misspelled preset name is an error, not a generic sound.

Stage 6 is one `quality_gate.run_gate` call, not a hand-copied subset, so every gate row (score and render checks,
ambience against its measured reference, the physics behaviour of each `sfx:`/`env:` stem, balance, vocals, chroma,
kick grid, masking) and the mixing diagnostics (`mix:` rows) land in `reports/ci_report.json`.

**Built-in names** (need no preset): General MIDI names in `scripts/soundbank.py --list`, drum kits, `env:`
soundscapes, `sfx:<name>` one-hit effects (one note = one hit; the skill ships a neutral default for each, a project preset in `presets/sfx/` overrides it), `clone:<file>` instruments, and the formant voices in `vocals.INSTRUMENTS`. Any other sound is data: `scripts/sound_model.py` (voices of excitation, resonator and events; `references/sound-effects.md` section 2c). Ambience (rain, water, wind, fire, birds, insects) is never `sfx:`: it is an `env:` preset. Any preset you own (`env:` or `sfx:`) lists its real-sound `sources`. Anything else (oud,
quena, a named vocal style) is custom and needs a preset.

**Sample libraries (optional)**: a track can be played by a free multisampled SFZ orchestra kept in the project instead of the GM SoundFont: `scripts/sfz_libs.py get sso --project <dir>`, then an instrument preset with an `sfz` block (`references/sfz-libraries.md`). Nothing downloads unless you run it; GM stays the default.

**Type of piece** (tense, ambient, dance, cinematic, effects only, `video_cinematic`, or your own): set `"piece_type"` in the score and the quality gate applies, relaxes or skips its rows by a `gate` preset, with every reason printed (`scripts/gate_profiles.py list`, `references/quality-gate.md` section 3c).

**Test mode** (smoke tests only, never a deliverable): `python scripts/pipeline.py "trailer in D minor, 8s" --test --out x.wav`.
It skips the project gate and uses generic General MIDI instruments.

## Rules that hold in every project

- **Modular, not monolithic.** Sound and space live in `presets/`, notes in `scores/`, intent in `direction/`.
  Never hardcode synthesis, EQ, notes and mixing in one Python file. A custom `<project>/scripts/compose_main.py` is allowed
  only to generate the score JSON.
- **Research before presets.** No instrument, vocal or culture preset without a research note first. Never guess
  acoustic values.
- **A new sound is data, not a function.** A break, a footstep on gravel or rain on a roof is a `"scene"` in the preset:
  materials, geometry, interactions and calibration (`references/physical-scene.md`). `physical.py check` validates it,
  `physical.py render` previews it, `physical.py verify` proves an existing sound did not move. An unknown field is an
  error, never a fallback noise bed. A place takes the same scene (`"scene"`) or several mixed as one bed
  (`"scene_layers"`), and the gate's bed rule reads the scene instead of a layer list: `scene_layers` counts, and so
  does a continuous mechanism (`flow`, `foliage`, `granular`, `rolling`, `gait`, `repeated_impact`); a single impact or
  fracture scene is a spot.
- **One hero at a time**, beds below the lead, breath between phrases, no identical 2- or 4-bar repeats:
  `references/acoustic-laws.md`, `references/mix-rules.md`, `references/director-roles-and-soul.md`.
- **Rooms and ambience are project presets** (`presets/spaces/`, `presets/environments/`), written from the research, never taken
  from the skill as shipped, and never built in a script. Add ambience only when the user asked for it. Steps:
  `references/environments-as-presets.md`.
- **Every piece gets its own mix preset** (`"mix_preset"` in the score, kind `mix`), written for that music's character. The gate fails a
  score without one. Steps: `references/blending-and-balance.md`, section "Mix preset".
- **The mix preset owns the processing, not the code.** `scaffold mix` writes every strategy with the value this engine
  shipped with: `gain_staging.strategy` (`legacy`|`adaptive`), `dynamics.engine` (`pedalboard`|`dsp`), `spectral`
  profiles, `sidechain.mode` (`legacy`|`explicit`|`off`), `space`, `mastering.profile`. Change one strategy in the
  piece's own preset, re-measure, and say which you changed. `presets.py validate` rejects an unknown key or a bad range;
  `presets.py show mix default` prints every key with its value.
- **Measure the mix, then say what you measured.** `python scripts/mixer.py <stems>/ --mix mix.json --out out.wav --diagnose`
  prints the diagnostics table (masking, low-end congestion, phase, mud, harshness, crest, headroom). It reports and never
  edits: a WARN is a question about the mix, not a verdict, and a FAIL is a technical error to fix in the score or the preset.
- **Immersive means the mix preset's `immersive` block, nothing else.** If the user asks for immersive, 3D or height, set `immersive.enabled` in the piece's own mix preset and write heights from the research and staging; Stage 0 and the `imm_*` rows enforce it. There is no separate engine.
- **A failing gate row is a fact to explain, not a number to loosen.** Find out whether the score or the gate is wrong by
  measuring (stem levels, spectrum), then fix that one. A `balance` FAIL means lower that track's `gain_db`.
- **Say what was not checked.** Taste, real-instrument realism and how it sits in the video are not measured.

## Routes (when the request is more specific)

| The request | Read |
|---|---|
| Mood phrase, scene, film cue, background | `references/brief-reading.md`, `references/scene-recipes.md` |
| A genre (42 built in; Pixabay labels work) | `references/genres-and-moods.md`; `compose.py --list` |
| Culture, fusion, soul (Carnatic, Tamil, Arabic, Afro, Celtic ...) | `knowledgebase/README.md` index, `references/director-roles-and-soul.md`, `references/cultural-soul.md`, `references/world-music.md`, `references/genre-fusion.md`, `references/style-rahman.md` |
| Vocals, choirs, hums | `references/vocals-and-choirs.md`, `references/vocal-engine.md` + a `presets/vocals/` preset |
| Sound effects, ambience, weather | `references/sound-effects.md`, `references/physical-scene.md`, `references/environments-as-presets.md`, `knowledgebase/PROCEDURAL_SFX_AMBIENCE.md` |
| A new physical sound from JSON (a break, footsteps on gravel, rain on a material) | `references/physical-scene.md`, `scripts/physical.py laws` |
| Corporate, ad, voice-over, podcast | `knowledgebase/COMMERCIAL_CORPORATE_PROMO.md`, `compose.py --voiceover`, `video-mixer/video_program_mix.py` |
| Game music or SFX | `knowledgebase/GAME_MUSIC_ADAPTIVE_DSP.md`, `knowledgebase/GAME_SFX_INTERACTIVE_SYSTEMS.md` |
| Motion graphics / video scoring | `knowledgebase/MOTION_GRAPHICS_VIDEO_SCORING.md` |
| Score a real video file (cuts, dialogue, delivery) | `references/video-scoring.md`, `scripts/video_score.py` |
| Immersive, 3D, height, headphone surround (mix preset `immersive.enabled`) | `references/immersive-spatial.md`, `references/spatial-presets-and-scoring.md` |
| Specific theme, chord sheet, exact timecodes | `templates/custom_score_template.py`, `references/custom-scripts.md`, `references/creative-composition.md` |
| "Use my instrument" / clone a recording | `references/instrument-cloning.md`, `scripts/clone_instrument.py` |
| Take a song apart into MIDI and stems rebuilt from it (instruments, drums, ambience, space; no sung vocals) | `references/extraction.md`, `scripts/extract_pipeline.py` |
| Mix or master stems the user already has, or a mix that reads muddy, harsh, narrow or squashed | `references/mixing-and-mastering.md`, `scripts/mixer.py`, `scripts/mix_diagnostics.py`, `scripts/mix_bench.py` |
| Judge any audio file ("does this sound epic?") | `scripts/listen.py`; `scripts/pipeline.py <master.wav> --check-only` |
| Layers not blending, a bass or pad too loud, beds start or stop abruptly, any genre | `references/blending-and-balance.md` |
| What a gate row means | `references/quality-gate.md` |
| Music21 analysis for Stage 6 | `references/music21-analysis.md`, `templates/analyze_music21_template.py` |
| Humanization / robotic sound | `references/humanization.md`, `references/natural-instruments.md`, `references/emotion-and-scoring.md` |
| Direction-sheet example, `direct.py` edits, `listen.py` reading | `references/workflow-snippets.md` |
| Troubleshooting, limits | `references/troubleshooting-and-limits.md` |
| Every script and what it does | `references/bundled-files.md` |
| Evidence behind the rules, theory background | `references/research-sources.md`, `references/expressive-research.md`, `references/global-theory-kb.md` |
| Old loop (archive, do not follow) | `references/legacy-workflow.md` |

## Reply template (plain, short)

```
Done: out/master.wav (45 s, -16.0 LUFS, -1.9 dBTP), midi/<title>_score.mid, stems/ (N), reports/ci_report.json.
What it is: <feel, key, BPM, instruments and the presets used>.
Gates: <N pass, 0 fail after K attempts>; listen report: <the readings>.
Not checked: taste, real-instrument realism, fit in the final video.
Next, if you want it: <one change>.
```
Add "Sources:" only when web research was used.

## Limits (say these in the reply)

- The sampled bank is good, not concert-grade; no sung words (choir, "oohs" and hums are texture). The vocal engine is synthesised, objectively checked, and not listened to.
- earshot is a model's opinion, not taste; it cannot judge whether a raga or maqam is correct.
- Traditional idioms are approximations with GM instruments unless a preset or a user recording supplies the sound.
- The mixer places by pan, distance filtering, width and one shared room. Head-related delays, elevation and `space` apply only to presets with `spatial.binaural: true` (headphone-oriented, point sources).
- The mix diagnostics measure energy, correlation and crest per band; they cannot hear. No threshold in them is a taste.
  Every render runs them; in the report a diagnostic `FAIL` is printed as a `mix:` WARN, because the gate's own rows
  (true peak, clipping, silence) own the blocking verdicts.
- Full list: `references/troubleshooting-and-limits.md`.
