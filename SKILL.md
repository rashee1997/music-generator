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

First-time setup: see [`references/workflow/setup.md`](references/workflow/setup.md).

## Workflow

Follow these steps in order. Never skip steps.

| Step | Action | Output | Check |
|---|---|---|---|
| 1 | **Create project** | `python scripts/setup_project.py --new-project <dir> --title "<Title>"` (add `--ambience` only if requested) | Project structure with direction/, presets/, scores/, out/, reports/, STATUS.md |
| 2 | **Research** | `python scripts/research_kb.py <dir> --topic "<topic>" --tags <tags>`. Add web sources via TinyFish (see the `use-tinyfish` skill). For ambience/effects, use `--sounds` and document real references with licenses/measurements. | `reports/research_<topic>.md` with KB citations and sources |
| 2b | **Load references** | `python scripts/find_references.py "<the brief in plain words>" --top 5`. Then open only the files it returns, and inside them only the sections it names. | The list of files you will actually open, and why |
| 3 | **Direction sheet** | Copy `templates/direction_sheet.json` to `<dir>/direction/direction_<title>.json`. Fill all fields per [`references/workflow/music-direction.md`](references/workflow/music-direction.md). For video, run `scripts/video_score.py` first. | Complete sheet with job, feel, sections, motifs, hits, mix_intent, spatial_staging |
| 4 | **Create presets** | `python scripts/presets.py scaffold instruments/vocals/environments/sfx <name> --project <dir>`. Each needs unique spatial placement. | Presets in project with character, spatial.azimuth/distance |
| 5 | **Write score** | Create `<dir>/scores/<title>_score.json` (declarative, references presets). Use [`templates/custom_score_template.py`](templates/custom_score_template.py) for exact control. | Valid JSON with tracks referencing presets |
| 6 | **Render & gate** | `python scripts/pipeline.py <dir>/scores/<title>_score.json --project <dir>` | `out/master.wav` (a copy of the newest version), `out/master_vNN.wav`, `out/versions.json`, `<master>.json` tags, `stems/`, `midi/`, `reports/ci_report.json` with 0 FAIL |
| 7 | **Revise** | Change ONE lever at a time ([`references/workflow/music-direction.md`](references/workflow/music-direction.md) §6). Re-run step 6 until green (max 5 attempts). | All gates pass |
| 8 | **Listen & deliver** | `python scripts/listen.py out/master.wav --direction direction/<sheet>.json` | Verify and report results |

## Scripts you run

One line each; every path is under `scripts/` unless it says otherwise.

| Script | What it does |
|---|---|
| `setup_project.py` | create a project: uv venv, packages, SoundFont, `--ears` for earshot |
| `pipeline.py` | render and certify: stages 1-7, the gate, version files, tags |
| `compose.py` | brief to score; `--list`, `--render`, `--midi`, `--energy`, `--space`, `--voiceover` |
| `render_natural.py` | score to stems and master, per-note expression |
| `mixer.py` | the mix and master engine |
| `mix_diagnostics.py` | the mixing diagnostics table; reports, never edits the mix |
| `quality_gate.py` | the gate rows for a score and a rendered master |
| `gate_profiles.py` | gate profiles: `list`, `rows`, `explain`, `new`, `check` |
| `presets.py` | `list`, `show`, `validate`, `scaffold`, `ingest` |
| `direct.py` | director edits on a score: pulse, lines, arcs, gains, tempo |
| `listen.py` | earshot readings and measurements against a direction sheet |
| `research_kb.py` | knowledge-base sections into `reports/research_<topic>.md` |
| `find_references.py` | the reference finder: `--tags`, `--list`, `--check` |
| `soundbank.py` | SoundFont discovery, instrument names and drum keys (`--list`) |
| `world.py` | prints every scale, cycle and genre |
| `sfx.py` | one-hit effects from presets (`list`, `make`) |
| `environment.py` | ambience from presets and physical scenes |
| `physical.py` | the physical scene engine: `laws`, `check`, `render`, `verify` |
| `video_score.py` | score a video end to end (`--selftest`) |
| `clone_instrument.py` | clone an instrument from a recording, export an SFZ |
| `extract_pipeline.py` | song to MIDI and stems: `setup`, `run`, `status`, `kb` |
| `sfz_libs.py`, `sfz_render.py` | optional SFZ libraries and the renderer that plays them |
| `helpers/version_manager.py` | the delivery record (`list --project <dir>`) |
| `helpers/ingest_metadata.py` | rewrite the tags beside a master |
| `helpers/compress_mp3.py` | manual MP3 encode of a certified version |

## Delivery metadata and versions

Certification writes three things automatically, after the musical gate passes:

- **`out/master_vNN.wav`** — every certified render gets its own version file. Earlier versions are kept; a re-render never overwrites one.
- **`out/master.wav`** — a copy of the newest version, for tools that expect a single master.
- **`out/versions.json`** — each version with its timestamp, measurements and the **change** that earned it (the gate failures it cleared, or `first certified render`).
- **`out/master.json`** — the standard tags written beside the master.

Where the tags come from: defaults in `presets/metadata/metadata.json` (artist, album, copyright, licence, publisher, ISRC, language), then values derived from the score (title, genre from `piece_type`, year, a factual `key · BPM · piece_type` comment), then the project's own `metadata.json` overrides. Write real values into `<project>/metadata.json` rather than into scripts.

Rules for an agent:

- Never delete or overwrite a `master_vNN.wav` or a `versions.json` record. If a delivery needs a clean take, it becomes a new version.
- Check the record after a render: `python scripts/helpers/version_manager.py list --project <dir>`.
- MP3 compression is **manual**, never part of the pipeline: `python scripts/helpers/compress_mp3.py out/master_vNN.wav -o <file>.mp3 -b 320k`. It carries the sidecar tags into the MP3.
- The gate rows `meta.tags` and `meta.version` only trace this record. They warn, never fail, and are `INFO` on a piece's first render.

## Deliverable formats

A score names what it wants built; the engine builds only that, never every format at once.

```
"output_targets": "stereo"                     one target
"output_targets": ["immersive_7_1_4", "stereo"]  these, in order; the first is the certified master
"output_targets": "all"                       every target the engine can build
(absent)                                      the default (presets/outputs/_default.json)
```

| Target | Channels | Layout | Ceiling |
|---|---|---|---|
| `stereo` | 2 | direct L/R | -1.5 dBTP |
| `binaural` | 2 | headphone render (not buildable yet) | -1.5 dBTP |
| `immersive_7_1` | 8 | ITU-R BS.2051 System H | -3.0 dBTP |
| `immersive_7_1_4` | 12 | ITU-R BS.2051 System J | -3.0 dBTP |

Every number lives in `references/data/presets/outputs/` (format) and `references/data/presets/layouts/` (speaker
positions, crossover, fold-down), loaded through `presets.py`, so a project can add its own format with two JSON files.
A target with `"renderer": null` is described but cannot be built: naming it blocks the render (no silent downgrade),
and `"all"` reports it as skipped. The CLI can override the score: `--targets stereo` or `--targets all`.

`scripts/spatial_engine/` holds the model behind the multichannel targets: vector base amplitude panning over the
layout's own speakers (Pulkki 1997), a 4th-order Linkwitz-Riley crossover and low-frequency send (Linkwitz 1976),
all-pass decorrelation for the surround and height channels (Kendall 1995), and the ITU-R BS.775 two-channel fold.
The gate rows in `scripts/spatial_gate.py` run only for the formats that were requested.

## References on demand

`references/` is bigger than any one piece needs. Do not open it file by file: ask the finder, which indexes
`references/**/*.md` at run time by keyword (no list of files is stored anywhere), and read only what comes back.

```
python scripts/find_references.py "carnatic violin over a lo-fi bed"
python scripts/find_references.py --tags immersive
python scripts/find_references.py --list      # every file, its summary and its tags
python scripts/find_references.py --check     # front-matter audit; CI runs this
```

Every reference file carries YAML front matter (`title`, `summary`, `tags`, `load_when`). The finder scores the
body, then the title and the tags, and prints the best section of each file with its line number: go to that line
instead of reading the whole page. A query that returns nothing means the words were too vague; use the words of
the brief, a culture, an instrument or a gate row.

Do not read a reference file that the finder did not return, and do not paste its text into an answer: the file
exists so the agent can decide values, not so it can be quoted.

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
| Video scoring/cuts | [`references/scoring/video-scoring.md`](references/scoring/video-scoring.md), `scripts/video_score.py` |
| Vocals/choirs/hums | [`references/instruments-and-vocals/vocals-and-choirs.md`](references/instruments-and-vocals/vocals-and-choirs.md), [`references/instruments-and-vocals/vocal-engine.md`](references/instruments-and-vocals/vocal-engine.md) |
| Cultural styles/fusion | [`knowledgebase/README.md`](knowledgebase/README.md), [`references/scoring/cultural-soul.md`](references/scoring/cultural-soul.md), [`references/scoring/genre-fusion.md`](references/scoring/genre-fusion.md) |
| SFX/ambience/foley | [`references/sound-design/sound-effects.md`](references/sound-design/sound-effects.md), [`references/spatial/physical-scene.md`](references/spatial/physical-scene.md), [`references/spatial/environments-as-presets.md`](references/spatial/environments-as-presets.md) |
| SFZ orchestra | [`references/instruments-and-vocals/sfz-libraries.md`](references/instruments-and-vocals/sfz-libraries.md), `scripts/sfz_libs.py` |
| Instrument cloning/extraction | [`references/instruments-and-vocals/instrument-cloning.md`](references/instruments-and-vocals/instrument-cloning.md), [`references/workflow/extraction.md`](references/workflow/extraction.md) |
| Mixing/mastering | [`references/mixing/mixing-and-mastering.md`](references/mixing/mixing-and-mastering.md), `scripts/mixer.py`, `scripts/mix_diagnostics.py` |
| Gate failures | [`references/mixing/quality-gate.md`](references/mixing/quality-gate.md), `scripts/gate_profiles.py` |

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
- See [`AGENTS.md`](AGENTS.md) for complete rules and [`references/workflow/troubleshooting-and-limits.md`](references/workflow/troubleshooting-and-limits.md) for full limits.
