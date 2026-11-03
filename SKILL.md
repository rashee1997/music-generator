---
name: music-generator
description: Generate procedural music for scenes, videos, games, and custom pieces. Use when asked for soundtracks, underscore, jingles, loops, music under voice-over, themes, instrument cloning, mixing/mastering, or when music sounds robotic/flat/off-mood. Creates projects with research, direction sheets, custom presets, declarative scores, renders via pipeline.py with quality gates until passing.
license: AGPL-3.0-or-later. See LICENSE.
metadata:
  author: rasheedh
  version: "1.0"
allowed-tools: Read Write Edit Glob Grep Bash
---

# Music Generator

A procedural music generation system that creates original music through a strict, measurable pipeline. All decisions are made by the agent; scripts execute them. The pipeline uses objective measurements and quality gates rather than subjective guessing.

## When to Use

Use this skill when:
- Creating original music for video, games, ads, podcasts, or voice-overs
- Generating soundtracks from mood descriptions (e.g., "tense cinematic build-up", "calm lo-fi")
- Cloning instruments from recordings
- Mixing or mastering existing stems
- Scoring to video with cuts/dialogue
- Fixing robotic, flat, or unbalanced music
- Working with specific cultural styles (Carnatic, Arabic, African, East Asian, etc.)

## Quick Start

Run from the skill directory with its virtual environment:
- Windows: `.venv/Scripts/python.exe`
- Unix: `.venv/bin/python`

First-time setup: see [`references/setup.md`](references/setup.md).

## Workflow

Follow these steps in order. Never skip steps.

| Step | Action | Output | Check |
|---|---|---|---|
| 1 | **Create project** | `python scripts/setup_project.py --new-project <dir> --title "<Title>"` (add `--ambience` only if requested) | Project structure with direction/, presets/, scores/, out/, reports/, STATUS.md |
| 2 | **Research** | `python scripts/research_kb.py <dir> --topic "<topic>" --tags <tags>`. Add web sources via TinyFish. For ambience/effects, use `--sounds` and document real references with licenses/measurements. | `reports/research_<topic>.md` with KB citations and sources |
| 3 | **Direction sheet** | Copy `templates/direction_sheet.json` to `<dir>/direction/direction_<title>.json`. Fill all fields per [`references/music-direction.md`](references/music-direction.md). For video, run `scripts/video_score.py` first. | Complete sheet with job, feel, sections, motifs, hits, mix_intent, spatial_staging |
| 4 | **Create presets** | `python scripts/presets.py scaffold instruments/vocals/environments/sfx <name> --project <dir>`. Each needs unique spatial placement. | Presets in project with character, spatial.azimuth/distance |
| 5 | **Write score** | Create `<dir>/scores/<title>_score.json` (declarative, references presets). Use [`templates/custom_score_template.py`](templates/custom_score_template.py) for exact control. | Valid JSON with tracks referencing presets |
| 6 | **Render & gate** | `python scripts/pipeline.py <dir>/scores/<title>_score.json --project <dir>` | `out/master.wav`, `stems/`, `midi/`, `reports/ci_report.json` with 0 FAIL |
| 7 | **Revise** | Change ONE lever at a time ([`references/music-direction.md`](references/music-direction.md) §6). Re-run step 6 until green (max 5 attempts). | All gates pass |
| 8 | **Listen & deliver** | `python scripts/listen.py out/master.wav --direction direction/<sheet>.json` | Verify and report results |

## Key Principles

- **Modular**: Sound/space in `presets/`, notes in `scores/`, intent in `direction/`. No monolithic scripts.
- **Research-driven**: Every custom instrument/vocal/culture needs KB research citations.
- **Data over code**: New sounds use scene data (`"scene"`/`"scene_layers"`), not Python generators.
- **One change at a time**: When fixing gate failures, change exactly one parameter and re-measure.
- **Measure, don't guess**: Use pipeline metrics and diagnostics. Taste is not measured.
- **Every piece gets a mix preset**: Controls gain staging, dynamics, sidechain, mastering.

## Routes by Task

| Task | Key References |
|---|---|
| Video scoring/cuts | [`references/video-scoring.md`](references/video-scoring.md), `scripts/video_score.py` |
| Vocals/choirs/hums | [`references/vocals-and-choirs.md`](references/vocals-and-choirs.md), [`references/vocal-engine.md`](references/vocal-engine.md) |
| Cultural styles/fusion | [`knowledgebase/README.md`](knowledgebase/README.md), [`references/cultural-soul.md`](references/cultural-soul.md), [`references/genre-fusion.md`](references/genre-fusion.md) |
| SFX/ambience/foley | [`references/sound-effects.md`](references/sound-effects.md), [`references/physical-scene.md`](references/physical-scene.md), [`references/environments-as-presets.md`](references/environments-as-presets.md) |
| SFZ orchestra | [`references/sfz-libraries.md`](references/sfz-libraries.md), `scripts/sfz_libs.py` |
| Instrument cloning/extraction | [`references/instrument-cloning.md`](references/instrument-cloning.md), [`references/extraction.md`](references/extraction.md) |
| Mixing/mastering | [`references/mixing-and-mastering.md`](references/mixing-and-mastering.md), `scripts/mixer.py`, `scripts/mix_diagnostics.py` |
| Gate failures | [`references/quality-gate.md`](references/quality-gate.md), `scripts/gate_profiles.py` |

## Output Template

```
Done: out/master.wav (Xs, -X.X LUFS, -X.X dBTP), midi/<title>_score.mid, stems/ (N), reports/ci_report.json.
What it is: <feel, key, BPM, instruments, presets>.
Gates: <N pass, 0 fail after K attempts>; listen: <readings>.
Not checked: taste, real-instrument realism, fit in final video.
Next: <one suggested change>.
```

## Notes & Limits

- GM SoundFont used by default; SFZ libraries optional. No sung words in standard synthesis (choirs/hums are textures).
- `listen.py` requires earshot model (`python scripts/setup_project.py --ears` to install).
- Headphone spatialization only for presets with `spatial.binaural: true`.
- Mix diagnostics report but don't block gates (blocking gates are in quality gate).
- See [`AGENTS.md`](AGENTS.md) for complete rules and [`references/troubleshooting-and-limits.md`](references/troubleshooting-and-limits.md) for full limits.
