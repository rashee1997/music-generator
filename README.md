# music-generator

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

A research-backed, measurement-driven procedural music generation system that composes, renders, mixes and validates original music against psychoacoustic principles.

## Listen

**Black Jaguar — cinematic chase** · D minor · 134 BPM · jungle ambience, stalking strings, chromatic pursuit, build and release

<audio controls preload="none" src="https://cdn.jsdelivr.net/gh/rashee1997/music-generator@master/assets/samples/black-jaguar-cinematic-chase.mp3">
</audio>

▶ [Play the sample (MP3, 320 kbps)](assets/samples/black-jaguar-cinematic-chase.mp3)

## The problem with code-generated music

When LLMs or scripts generate music, they fail in ways that are predictable and audible, because a text model cannot hear what it writes:

1. **Mechanical rigidity or random chaos.** Naive code locks notes to the grid with static velocities (a 1990s MIDI file). Told to "humanize", an LLM scatters notes unpredictably — zig-zag lines, unrecovered leaps, incoherent rhythm — passing simple rules while sounding unmusical.
2. **Harmonic mud and voicing violations.** Voices clustered below middle C violate the low-interval limit, muddying 100–300 Hz. Closed-position major sevenths put the root and seventh adjacent in one register, producing a grating minor second.
3. **Cochlear roughness.** Stacked overtones that collide inside a quarter of a critical bandwidth set the basilar membrane beating; the ear tires within seconds.
4. **Spectral masking.** Pads, rhythm guitars and bass swallow the vocal or lead in 250–500 Hz when nothing carves a pocket or uses unmasking.
5. **Static harmony or broken tension.** Progressions either stagnate or teleport between unrelated keys with no voice leading and no cadence resolution.

## What this system does instead

Music generation is treated as a **CI/CD pipeline**: every piece is constrained by perceptual law, humanized from measurement rather than taste, staged in space, mixed from a preset, and certified by gates before anything is delivered.

```text
[Brief / Prompt / Score]
        │
   Stage 1  Composition, voice leading, culture fusion   compose.py · theory.py · world.py
        │
   Stage 2  Cognitive & acoustic pre-flight linter        pattern_audit.py
        │
   Stage 3  Humanization and phrase respiration           humanize.py
        │
   Stage 4  Multi-engine stem rendering                   tinysoundfont · vocals.py · environment.py · spatial.py
        │
   Stage 5  Precision mixing and mastering                mixer.py
        │
   Stage 6  Automated quality suite                       quality_gate.py · naturalness_check.py · music21
        │
   Stage 7  Certified release packaging                   WAV · MIDI · stems/ · ci_report.json
```

## What it enforces

- **Melodic and harmonic law** — conjunct-motion ratio and leap recovery (Meyer/Narmour), resolution gravity for chromatic tension notes, and 3D spiral-array tonal tension (Chew) measuring chord spread, voice-leading speed and distance from the tonic.
- **Rhythm that breathes** — metric-tree syncopation across 4/4, 3/4, 6/8, 5/4, 7/8 and 12/8, rejecting both robotic marches and metric collapse.
- **Information interest** — Shannon entropy and Markov surprise kept inside the band where listeners stay engaged rather than bored or lost.
- **No cochlear roughness** — Hann-windowed critical-band analysis across 80–6000 Hz catches overtone clashes and unanswered cadence tension.
- **Unmasking in stereo** — equivalent-rectangular-bandwidth masking analysis with a binaural unmasking bonus for panned sources.
- **Stable ambience** — dropout-free beds and a pumping limit, so a soundscape never gulps.
- **Human performance by measurement** — shared tempo drift separated from each player's own motor error, drum push scaled with tempo, velocity coupled to duration; the renderer oversamples the sampler and adds the mechanism noise a real instrument makes at note-on and note-off.
- **Spatial staging** — per-stem azimuth, distance filtering, level, width and a shared room; measured-HRTF binaural and immersive height are opt-in per mix preset.
- **Presets, never hardcoded** — sound, space, mix strategy, gate profile and every spatial number live in JSON; scripts only write notes.

## Quick start

```bash
python scripts/setup_project.py                                     # first time: venv + packages + soundfont
python scripts/setup_project.py --new-project my-project --title "My Track"
.venv/Scripts/python.exe scripts/pipeline.py my-project/scores/my_track_score.json --project my-project
```

If gates fail, the uncertified mix stays at `out/_draft_master.wav` and `out/master.wav` is untouched. Change one lever and run again.

## Auditing existing music

```bash
python scripts/pipeline.py path/to/master.wav --check-only
```

Reports loudness, true peak, balance, masking and grid problems in `reports/ci_report.json` without re-rendering or altering the audio.

## Structure

```text
music-generator/
├── scripts/         engine: pipeline, composing, mixing, gates, renderers
├── presets/         default instrument, mix, space and vocal presets
├── knowledgebase/   genre, culture and DSP research
├── references/      guides and schemas
├── templates/       project, direction-sheet and score templates
├── video-mixer/     cut detection, ducking and muxing
├── assets/samples/  rendered demo audio
└── docs/            theory and documentation
```

## License

[GNU AGPLv3](LICENSE) — Copyright (C) 2026 rasheedh

## Documentation

**[docs/](docs/)** — the workflow, the rules, the psychoacoustic foundations and every reference file.
