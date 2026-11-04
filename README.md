# music-generator

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Agent Skill](https://img.shields.io/badge/agent%20skill-SKILL.md-black.svg)](SKILL.md)

An AI agent skill and Python audio pipeline that composes, renders, mixes, and validates original music from text briefs, scores, or video files.

 **Demo:** **Black Jaguar (Cinematic Chase)** — *D minor · 134 BPM*
▶ **[Listen in Browser](https://rashee1997.github.io/music-generator/docs/listen.html)** · **[Download MP3 (320 kbps)](assets/samples/black-jaguar-cinematic-chase.mp3)**

---

## The Problem vs. What This Sorts Out

### Why LLM-Generated Music Usually Fails

* **Robotic Grid or Random Chaos:** Naive code locks MIDI notes to a rigid grid with static velocity. When told to "humanize," LLMs scatter notes randomly—creating unrecovered leaps and broken rhythm.
* **Low-End Mud & Voicing Clashes:** Voices clustered below middle C violate low-interval limits, muddying 100–300 Hz. Closed-position chords create grating minor-second clashes.
* **Ear Fatigue (Cochlear Roughness):** Stacked overtones colliding within a critical bandwidth cause harsh acoustic beating.
* **Spectral Masking:** Pads, guitars, and bass swallow lead instruments in the 250–500 Hz range when nothing carves out frequency pockets.
* **Aimless Harmony:** Chord progressions either loop statically or jump between unrelated keys without voice leading or cadence resolution.

### What `music-generator` Sorts Out

* **Voice-Leading & Melodic Rules:** Enforces conjunct motion, leap recovery, chromatic tension resolution, and 3D spiral-array tonal tension.
* **Groove That Breathes:** Evaluates metric-tree syncopation across 4/4, 3/4, 6/8, 5/4, 7/8, and 12/8—rejecting both robotic marches and rhythmic collapse.
* **Measured Humanization:** Separates shared ensemble tempo drift from individual player motor error, scales drum push with tempo, couples velocity to note duration, and adds note-on/note-off mechanism noise.
* **Roughness & Masking Gates:** Runs critical-band analysis (80–6000 Hz) and ERB stereo masking checks so leads stay clear and overtones don't clash.
* **Spatial Staging:** Applies per-stem azimuth, distance filtering, stereo width, shared room acoustics, and optional measured-HRTF binaural rendering.
* **Preset-Driven Mixing:** Keeps sound design, spatial placement, mix bus processing, and loudness targets (LUFS / True Peak) strictly in JSON presets rather than hardcoded scripts.
* **CI/CD Quality Gates:** Audits every render before finalizing. If a mix fails a check, it stays in `out/_draft_master.wav` until the issue is fixed.

---

## Installation

Installing the skill gives your coding agent (`Claude Code`, `Cursor`, `Codex`, etc.) the workflow instructions (`SKILL.md`). Because rendering requires the Python DSP engine and SoundFonts, **clone the repository alongside installing the skill.**

### 1. Install the Agent Skill

Requires **Node.js 22.20+**:

```bash
# Install into current project
npx skills add rashee1997/music-generator

# Install globally for all projects
npx skills add rashee1997/music-generator -g

# Install for a specific agent (e.g., Claude Code)
npx skills add rashee1997/music-generator --skill music-generator -a claude-code -y
```

Manage the skill:

```bash
npx skills list                      # Verify installation
npx skills update music-generator    # Pull latest version
```

### 2. Set Up the Audio Engine

```bash
git clone https://github.com/rashee1997/music-generator.git
cd music-generator

# Core setup: creates .venv, installs dependencies, downloads SoundFont, runs smoke test
python scripts/setup_project.py

# Optional: install earshot (~1 GB) so listen.py can evaluate rendered audio
python scripts/setup_project.py --ears
```

> **Note:** `setup_project.py` uses [uv](https://docs.astral.sh/uv/) if available and falls back to `python -m venv` + `pip`. **ffmpeg** is required only if using `video-mixer/`.

---

## Quick Start

### Using with an AI Agent

Prompt your agent naturally:

> *"Compose a 60-second underscore for a slow reveal of a mountain range — cold, patient, no drums."*

The agent will automatically read `SKILL.md`, research the style, generate a direction sheet and presets, write the score, and iterate through the rendering pipeline until all quality gates pass.

### Using via CLI

Use the virtual environment created during setup (`.venv/bin/python` on macOS/Linux or `.venv\Scripts\python.exe` on Windows):

```bash
# 1. Scaffold a new project
python scripts/setup_project.py --new-project my-project --title "My Track"

# 2. Render score and run quality gates
python scripts/pipeline.py my-project/scores/my_track_score.json --project my-project

# 3. Audit an existing WAV file (no re-rendering)
python scripts/pipeline.py path/to/master.wav --check-only

# 4. Inspect certified version history
python scripts/helpers/version_manager.py list --project my-project

# 5. Export certified master to MP3 with metadata tags
python scripts/helpers/compress_mp3.py out/master_v01.wav -o my-track.mp3 -b 320k
```

---

## Pipeline Architecture

```text
[Brief / Prompt / Score]
   │
   ├─ 1. Composition & Voice Leading    (compose.py · theory.py · world.py)
   ├─ 2. Pre-Flight Theory Linter       (pattern_audit.py)
   ├─ 3. Humanization & Respiration     (humanize.py)
   ├─ 4. Multi-Engine Stem Rendering    (tinysoundfont · vocals.py · environment.py · spatial.py)
   ├─ 5. Mixing & Mastering             (mixer.py)
   ├─ 6. Psychoacoustic Quality Gates   (quality_gate.py · naturalness_check.py · music21)
   └─ 7. Certified Release Packaging    (out/master_vNN.wav · stems/ · midi/ · ci_report.json)
```

### The 8-Step Agent Workflow

| Step  | Action                | Output Artifact                                                      |
|:----- |:--------------------- |:-------------------------------------------------------------------- |
| **1** | Scaffold project      | `direction/`, `presets/`, `scores/`, `out/`, `reports/`, `STATUS.md` |
| **2** | Research idiom        | `reports/research_<topic>.md`                                        |
| **3** | Write direction sheet | `direction/direction_<title>.json`                                   |
| **4** | Configure presets     | Instrument, vocal, space, and mix JSON presets                       |
| **5** | Write score           | `scores/<title>_score.json`                                          |
| **6** | Render & gate         | `out/master_vNN.wav`, `stems/`, `midi/`, `reports/ci_report.json`    |
| **7** | Iterate fixes         | Adjusts one parameter per run until 0 FAIL (max 5 attempts)          |
| **8** | Verify & deliver      | `listen.py` evaluation and final checklist in `STATUS.md`            |

Every certified render is versioned (`master_v01.wav`, `master_v02.wav`) in `out/versions.json` so previous takes are never overwritten, with metadata sidecars written to `out/master.json`.

---

## Repository Structure

```text
music-generator/
├── SKILL.md         # Agent skill entry point and workflow instructions
├── AGENTS.md        # Strict agent rules, preset schemas, and gate profiles
├── scripts/         # Core pipeline, composition, mixing, and gate scripts
├── presets/         # Default instrument, mix, space, vocal, and metadata JSONs
├── knowledgebase/   # Genre, cultural idiom, and DSP reference docs
├── references/      # Detailed guides (mixing, vocals, spatial, SFZ, video, limits)
├── templates/       # Project, direction-sheet, and score templates
├── video-mixer/     # Video cut detection, dialogue ducking, and muxing
├── docs/            # Psychoacoustic math (PSYCHOACOUSTICS.md) & web audio player
└── tests/           # Pipeline, spatial, and audio integrity test suites
```

---

## Known Limitations

* **Metrics Are Not Ears:** Quality gates catch technical and psychoacoustic errors (masking, clipping, bad voice leading), but cannot judge subjective musical taste or emotional fit.
* **General MIDI Default Bank:** Uses GeneralUser GS by default. Concert-grade orchestral realism requires supplying multisampled SFZ libraries per project.
* **Vowel-Only Vocals:** Synthesized vocals generate textures (choirs, *oohs*, hums) without consonants or lyrics.
* **Cultural Idioms Are Approximations:** Non-Western scales and rhythms are approximated unless paired with authentic instrument presets or user recordings.
* **Opt-In Binaural Processing:** Full HRTF elevation and head-shadowing only apply when `spatial.binaural: true` is enabled in the mix preset.
* **Basic Video Sync:** Cut detection misses gradual fades/dissolves and ducks dialogue by level rather than semantic context.

See [references/workflow/troubleshooting-and-limits.md](references/workflow/troubleshooting-and-limits.md) and [docs/PSYCHOACOUSTICS.md](docs/PSYCHOACOUSTICS.md) for full details.

---

## Credits & Attributions

* **Spatial Audio:** `scripts/spatial_hrtf/` includes a modified copy of [spaudiopy](https://github.com/chris-hld/spaudiopy) by Chris Hold (MIT License).
* **HRTF Data:** Uses the **FABIAN HRTF Database** from TU Berlin ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [DOI: 10.14279/depositonce-5718.5](https://doi.org/10.14279/depositonce-5718.5)), fetched via `setup_project.py`.
* **Synthesis:** Powered by [tinysoundfont](https://github.com/schellingb/tinysoundfont) by Bernhard Schelling (MIT License) using the [GeneralUser GS SoundFont](https://schristiancollins.com/generaluser.php) by S. Christian Collins.

## License

[GNU AGPLv3](LICENSE) — Copyright (C) 2026 rasheedh
