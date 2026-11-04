---
title: Bundled files
summary: What ships in this skill, what each file is for, and which ones a piece never touches.
tags: [files, layout, scripts, presets, knowledgebase, index]
load_when:
  - finding where something lives
  - a file's purpose is unclear
---

# Bundled files, pipeline stages and Pedalboard


## Bundled files

| File | Use |
|---|---|
| `scripts/pipeline.py` | **Unified Music CI/CD Pipeline**: Stage 0 project gate, then stages 1-7. Project mode (default, `--project`) writes `out/master.wav`, `midi/`, `stems/`, `reports/ci_report.json` and exits 1 on any FAIL; `--test` is a smoke test; `--check-only` audits a master. Stage 6 is a single `quality_gate.run_gate(..., score=...)` call plus the mixing diagnostics as `mix:` rows, so the pipeline and `quality_gate.py <score>` print the same rows |
| `scripts/project_gate.py` | Stage 0: scaffold folders, research note (KB citation + web URL), direction sheet without TODOs, exact presets for non-built-in instruments/vocals. `python scripts/project_gate.py <project> [score.json]` |
| `scripts/research_kb.py` | pulls the matching `knowledgebase/*.md` sections into `reports/research_<topic>.md` with `document_id` citations and an empty Web research section |
| `scripts/fusion.py` | plans a multi-culture mix: shared scale, tempo overlap, meter, instruments by role (`"fusion": [...]` in a brief) |
| `scripts/soul.py` / `scripts/soul_check.py` | culture soul profiles (breath, groove, call-and-response, ornament, cadence) and the release check that FAILs a flat piece |
| `scripts/presets.py` | preset layers (skill, then project): `list`, `show`, `validate`, `scaffold instruments\|vocals\|environments <name> --project <dir>`, `ingest`; `exact()` and `STRICT` for no-guess lookups |
| `scripts/world.py` | world-instrument names (oud, kora, ney ...) mapped to GM stand-ins, scales and idioms; stand-in names need a preset in a project |
| `templates/analyze_music21_template.py` | default Stage 6 music21 analysis; copy to `<project>/scripts/analyze_music21.py` to customise |
| `templates/requirements_template.txt` | dependency list copied into new projects |
| `scripts/setup_project.py` | one command: uv venv, packages, earshot and its models with `--ears`, SoundFont, smoke test |
| `requirements.txt` | core packages, pinned to the tested versions |
| `requirements-ears.txt` | earshot (pinned commit) and its extras; torch comes from the CPU index |
| `scripts/cli_util.py` | `require_file/require_dir` (one-line errors for bad paths), note names to MIDI (`D3` -> 50), used by pipeline and the CLIs |
| `scripts/envcheck.py` | compares installed packages with the `==` pins in `requirements.txt`; pipeline prints mismatches as WARN |
| `scripts/airabs.py` | ISO 9613-1 absorption (dB/m) and a linear-phase FIR air filter; used by environment.py, mixer.py (when `temp_c`/`rh` are set) and spatial.py |
| `scripts/spatial.py` | 3D physical spatial audio, used by the mixer only for presets with `spatial.binaural: true` (and by tests): Brown-Duda analytical head shadow, Kuhn ITD, near-field ILD surge, ISO 9613-1 air absorption, 6-surface ISM early reflections, and 1st-Order Ambisonics |
| `scripts/environment.py` | public entry point for ambience (facade over `env_engine/`): JSON layer presets or a physical `scene`/`scene_layers`, with ISO 9613-1 distance absorption |
| `scripts/vocals.py` | public facade of the vocal engine: `render_choir` (phrase-based, independent singers, true nasal hum, breath, expression, stems and a gate report), `sing`, Pedalboard harmonies / chorus / polish with numbers from config |
| `scripts/vocal_engine/` | the engine: `config` (defaults, old-key migration, validation), `source` (glottal pulse), `tract` (resonators), `nasal` (hum), `voice`, `performance` (phrases), `breath`, `expression`, `singer`, `ensemble` |
| `references/data/vocal-engine-data/` | all engine data: `defaults.json` (+ `ranges`, sources), `styles.json` (8 styles), `expression/*.json` (10 profiles), `vocal.schema.json` |
| `references/instruments-and-vocals/vocal-engine.md` | the vocal engine reference: signal path, hum model, breath, expression, ensemble, stems for the spatial engine, gate rows, limits, benchmark |
| `tests/test_vocals_engine.py`, `tests/test_vocal_gate.py` | 73 vocal tests; `tests/legacy_vocals.py` (old engine kept for A/B), `tests/render_vocal_artifacts.py`, `tests/compare_vocals.py`, `tests/bench_vocals.py`, `tests/artifacts/vocals/` (old and new WAVs, `REPORT.md`) |
| `scripts/sfx.py` | public entry point for one-hit effects (facade over `sfx_engine/`); a preset may be a physical `scene`, a `model`, a `spec` or a legacy `generator`. (score route: instrument `sfx:<name>`, one note = one hit) 21 one-hit effects, each with a shipped default preset in `references/data/presets/sfx/` (project `presets/sfx/` overrides it), 7 older ambience recipes kept for old scores (ambience is an `env:` preset) + Pedalboard analog sweeps (`LadderFilter`), lo-fi (`Bitcrush`/`GSM`/`MP3`), and stereo delays |
| `scripts/sound_model.py` | any sound effect or ambience as data: voices of excitation, resonator and event process (`laws`, `check`, `render`); used by `sfx:` model presets and the `model_layer` environment primitive |
| `scripts/physical.py` | orchestrator for the physical sound engine: `laws`, `check`, `render`, `baseline`, `verify`. A scene is data - sources, objects, materials, events, propagation - and an unknown or not-yet-wired field is an error that names its stage |
| `scripts/phys_core/` | the shared physical layer that both `env:` and `sfx:` use, so neither presentation owns the physics: materials (`materials.py`), geometry to modes (`geometry.py`), excitation (`excite.py`), resonators and porous absorption (`resonate.py`), fracture (`fracture.py`), gait (`gait.py`), vegetation (`vegetation.py`), one propagation law (`propagate.py`), energy calibration (`calibrate.py`), scene schema + validator (`scene.py`), renderer (`render.py`), mechanism registry (`registry.py`), frozen-render check (`baseline.py`) |
| `scripts/env_engine/` | ambience presentation: a preset's layers or physical scenes, several scenes mixed as one bed, per-layer gain and place |
| `scripts/sfx_engine/` | one-hit presentation: `make()`/`timeline()` over a scene, a model, or a legacy adapter |
| `scripts/sound_fit.py` | move a model's `free` parameters toward measured real recordings (bounded, seeded search; writes `<name>_fit.json`) |
| `scripts/ambience_reference.py` | `measure` a real recording into `<project>/reference/<slug>.json` (numbers only), `compare` a render with it; the gate row `ambience_reference` is a WARN, never a FAIL |
| `scripts/listen.py` | hear a file (earshot) and judge it against a direction sheet; measurements always |
| `scripts/direct.py` | director's edits on a score: pulse, lines, arcs, gains, copies, tempo, remove |
| `scripts/compose.py` | brief to score (mood words, energy, space, emotions, genres, arcs, hit points, loops, voice-over); `--list`, `--render`, `--midi`, `--energy`, `--space` |
| `scripts/render_natural.py` | score to stems and master: sampled instruments, per-note expression, clones |
| `scripts/mixer.py` | the mix and master engine: gain staging, EQ, dynamics, sidechain, space, stereo, loudness |
| `scripts/mix_schema.py` | the default value and the checking rule of every mix setting; role chains and spectral profiles |
| `scripts/mix_context.py` | one resolved configuration per piece (mix preset + space), so no mix depends on the last one |
| `scripts/dsp.py` | the kernels Pedalboard does not provide: soft-knee compressor, RMS detector, filtered sidechain, multiband, dynamic EQ, transient shaper, M/S EQ, measurements |
| `scripts/mix_diagnostics.py` | the mixing diagnostics table (masking, phase, mud, crest, headroom); reports, never changes the mix |
| `scripts/mix_bench.py` | mix timing and a legacy-versus-adaptive comparison, measured |
| `scripts/video_score.py` | score a real video end to end: probe → direction → render → program mix → mux → gate; `--selftest` |
| `video-mixer/video_program_mix.py` | voice-over, music and effects to a platform loudness, with the music-under-speech report |
| `video-mixer/video_probe.py`, `video_direction.py`, `video_mux.py`, `video_gate.py`, `video_selftest.py` | picture telemetry, probe→direction, lossless mux, the four `video.*` gate rows, the 17-check selftest |
| `references/data/presets/video/default.json`, `references/scoring/video-scoring.md` | every number the video path uses, and how the path works |
| `scripts/extract_pipeline.py` | orchestrator for pure-DSP song extraction: `setup`, `check-db`, `run`, `status`, `kb`; code in `scripts/extraction/` |
| `templates/extraction_profile.json`, `templates/gemini_listener_prompts.md` | every extraction setting; the prompts that make a listening model write the `music_db` |
| `references/workflow/extraction.md` | how a song becomes MIDI and stems rebuilt from it, what each stage does, the gate, the limits |
| `scripts/extraction/midi_clean.py`, `resynth.py`, `gate.py` | MIDI repair, stem rebuild (sampler / additive / drums / ambience / room), the extraction gate (borrows `naturalness_check.py` and `quality_gate.py`) |
| `scripts/clone_instrument.py` | clone an instrument from a recording (spectral-flux onset attack slicing, 8192-pt FFT harmonic partials, export SFZ) |
| `knowledgebase/data/instruments_registry.json` | dynamic updatable database of instrument auditioning thresholds, presence criteria, role mappings, and sequential studio mastering biquad chains |
| `scripts/naturalness_check.py` | the measurements used by listen.py (loudness, peaks, dynamics, balance, stereo, mobile phone mono fold-down, chroma) |
| `scripts/soundbank.py` | SoundFont discovery and download, instrument names to GM programs, drum keys |
| `scripts/plan.py` | the section plan (open, develop, build, climax, hush, reveal, release): separate loudness, density, lead and register per bar; `check_plan` validation |
| `scripts/section_report.py` | per-section loudness, active tracks and lead from a render, for comparing two versions on the same numbers |
| `tests/test_composition.py` | unit tests for the plan, the mood reading, the acoustic laws, the lead and arch rules, compose determinism, and widening stability: `python3 -m unittest discover -s tests` from the skill folder |
| `scripts/humanize.py` | timing, velocity, articulation, strum and tempo-map humanizer (melody arch only, lead only when accompanied, phrase-end breath) |
| `scripts/theory.py` | keys and modes, chords, voice leading, textures, bass lines, drum bars, phrases; the voicing, strum, fill and grid-accent laws |
| `scripts/pattern_audit.py` | the six acoustic laws plus copy-paste/flatness flags: `pattern_audit.py score.json [--strict]` |
| `scripts/sfz_libs.py`, `scripts/sfz_render.py` | optional SFZ sample libraries kept in the project (`libs/sfz/`): downloader with flags, checks, lock + licence files; a track plays through `sfizz_render` when its instrument is `sfz:<lib>/<patch>` or its preset has an `sfz` block (`references/instruments-and-vocals/sfz-libraries.md`) |
| `scripts/gate_profiles.py` | the quality gate by type of piece: row registry, `gate` presets (`references/data/presets/gate/`: melodic, tense, ambient, dance, cinematic, effects_only), `piece_type` in the score, `list / rows / explain / new / check` |
| `scripts/quality_gate.py` | the gate rows: score (including the acoustic laws), speech corridor masking, harmonic concordance, mobile mono, render and audio checks. `run_gate(score_path, ..., score=<dict>)` is the one list of rows; the pipeline calls it with its in-memory score |
| `templates/direction_sheet.json` | the director's sheet: targets for listen.py, plus the arc, motifs, hits with reasons, delivery and the `video` block |
| `templates/custom_score_template.py` | a runnable template for hand-written music |
| `references/workflow/music-direction.md` | the director's workflow, the research on cues and mechanisms, the revision levers, earshot's limits |
| `references/workflow/scene-recipes.md` | recipes by situation: trailer (tested), voice-over, calm, tense, end card, game loop, jingle, sleep, playful, traditional |
| `references/scoring/genres-and-moods.md` | epic (heroic and dark), mood models, the genres with tempo and groove, the Pixabay label map, how to add a genre |
| `references/scoring/emotion-and-scoring.md` | emotion table, arcs, tension toolkit, layers, motifs |
| `references/workflow/custom-scripts.md` | the score format, helpers, recipes and debugging for custom scripts |
| `references/instruments-and-vocals/natural-instruments.md` | which source for which sound, GM strengths, ranges, arrangement rules |
| `references/mixing/humanization.md` | why music sounds robotic and the numbers that fix it |
| `references/instruments-and-vocals/instrument-cloning.md` | recording guide, methods, limits, neural options, rights |
| `references/mixing/mixing-and-mastering.md` | mix order, EQ chart, loudness targets, voice-over rules, rooms, fix table |
| `references/workflow/music21-analysis.md` | dynamic, non-rigid musical computing with `music21`: tonality, chordification, melodic contour, voice leading, polyrhythmic analysis |
| `references/spatial/immersive-spatial.md` | headphone immersion inside the existing system: mix-preset `immersive` block, height rules, what the mixer changes, Stage 0 and Stage 6 `imm_*` rows, research, limits |
| `references/spatial/spatial-presets-and-scoring.md` | the 5-stage modular architecture (`direction/`, `presets/`, `scores/`), 3D spatial staging schemas, ISO 9613-1 air absorption, and DRR physical realism |

## The Music CI/CD Pipeline (pipeline.py)

[`scripts/pipeline.py`](../../scripts/pipeline.py) unifies the entire composition, pre-flight linting, humanization, rendering, Pedalboard mastering, and quality verification into a single executable command:
- **Stage 1 (Composition & Ingestion):** Ingests plain-language briefs (`"motivational trailer in D minor, 45s"`), brief JSONs, or score JSONs.
- **Stage 2 (Acoustic Pre-Flight Linter):** Enforces the 6 Acoustic Laws (chord voicing, choked resonance, machine-gun percussion, flams, low mud, spatial glue) prior to rendering.
- **Stage 3 (Humanization & Respiration):** Applies phrase respiration breath gaps, phrase velocity arches, swing, and rubato tempo maps.
- **Stage 4 (Multi-Engine Stem Rendering):** High-fidelity rendering across SoundFonts, vocal formant choirs ([`vocals.py`](../../scripts/vocals.py)), procedural nature soundscapes ([`environment.py`](../../scripts/environment.py)), and cloned instruments.
- **Stage 5 (High-Precision Mixing & Mastering):** Subtractive slot EQ, 2–4 kHz vocal pocket carving, shared room convolution reverb, and ITU-R BS.1770 broadcast limiting via `pb.BrickwallLimiter`.
- **Stage 6 (Automated CI Quality Gate):** Objective verification across loudness tolerance, true peak, silence dropouts, click detection, 250–3,800 Hz speech masking corridor, 12-TET harmonic chroma concordance, 1–5 kHz mobile phone mono-phase check, and kick-drum beat-grid lock.
- **Stage 7 (Release Packaging):** Delivers master WAV, MIDI, optional stems (`--stems`), and `ci_report.json` with a color-coded terminal scoreboard.

## Pedalboard DSP Engine & VST3 Architecture

The pipeline uses Spotify's **Pedalboard** DSP library across mixing, vocal polishing, environments and effects:
- **Mastering & Dynamic Limiting:** [`scripts/mixer.py`](../../scripts/mixer.py) uses `pb.BrickwallLimiter(ceiling_db=..., true_peak=True)` with 4× oversampling and lookahead for strict ITU-R BS.1770 true-peak broadcast compliance, plus `pb.NoiseGate` for 80s gated reverb tails and `pb.Mix` for parallel compression.
- **Vocal Harmonies & Chorus:** [`scripts/vocals.py`](../../scripts/vocals.py) uses `pb.PitchShift` for instant multi-part backing harmonies (sub-octave, 5th, upper octave) and `pb.Chorus` for wide stereo vocal ensemble diffusion without phase cancellation.
- **Procedural Sound Effects:** [`scripts/sfx.py`](../../scripts/sfx.py) uses `pb.LadderFilter` for warm Moog 24 dB/oct resonant sweeps, `pb.Bitcrush` for vintage 8-bit / 12-bit sampler grit, `pb.GSMFullRateCompressor` / `pb.MP3Compressor` for codec degradation, and `pb.Delay` for tempo-synced stereo echoes.
- **Environmental Acoustics:** [`scripts/environment.py`](../../scripts/environment.py) uses `pb.Convolution` and distance air absorption filters (`LowpassFilter`, `HighShelfFilter`).
- **Array Layout Rule:** Pedalboard requires `(channels, samples)` arrays (`[2, N]`). Scripts automatically manage transposition between Scipy/Soundfile format (`[N, 2]`) and Pedalboard.
- **VST3 plugins:** an external VST3 instrument or effect can be loaded via `pb.load_plugin(path)` and automated in Python.
