# music-generator

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Agent Skill](https://img.shields.io/badge/agent%20skill-SKILL.md-black.svg)](SKILL.md)

An AI agent skill and Python audio pipeline that composes, renders, mixes and validates original music from text briefs, scores or video, and delivers one mix as stereo, mono, 5.1, 7.1.4, an ambisonic sound field and object audio.

**Demo:** **Black Jaguar (Cinematic Chase)** — *D minor · 134 BPM*
▶ **[Listen in Browser](https://rashee1997.github.io/music-generator/docs/listen.html#black-jaguar)** · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/black-jaguar-cinematic-chase.mp3)**
▶ **[Arabian Nights: The Desert Crossing (Immersive 2.0)](https://rashee1997.github.io/music-generator/docs/listen.html#arabian-nights)** — with the desert air, mixed on the ambisonic bus · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/arabian-nights-desert.mp3)**
▶ **[The Unwelcome Crossing (haunted desert cue, object audio)](https://rashee1997.github.io/music-generator/docs/listen.html#haunted-desert)** — 48 kHz game master, with 7.1.2, 7.1 and ADM object renders · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/haunted-desert-crossing.mp3)**

## What it does

Writes with voice-leading rules and spiral-array tension (Chew 2000), performs with humanization, renders from a SoundFont, optional SFZ orchestras, a glottal-source voice and physical sound models, places every part in space, mixes from JSON presets only, and gates every render with about 390 rows. A failing row is a fact: the piece or the preset changes, the threshold does not. It also scores to picture, assembling only certified cues.

## Immersive 3.0

One ambisonic mix, judged once, delivered in every channel count. No format is a degraded copy of another.

| `output_targets` | Channels | How it is made | Judged by |
|---|---|---|---|
| `stereo` | 2 | decoded from the bus: `immersive.stereo_decode` is `"binaural"` (headphones) or `"speakers"` (±30°, ITU-R BS.775-3) | the whole gate |
| `mono` | 1 | **rendered**, not folded: no pan, width or head filter | `fold.mono` |
| `immersive_5_1`, `_5_1_2`, `_5_1_4` | 6 / 8 / 10 | VBAP (Pulkki 1997) onto ITU-R BS.2051-3 layouts, a Linkwitz-Riley low-frequency channel (Linkwitz 1976), all-pass decorrelation of the surrounds (Kendall 1995) | `imm.*`, `fold.timbre` |
| `immersive_7_1`, `_7_1_2`, `_7_1_4` | 8 / 10 / 12 | a 7.1 ring with 0, 2 or 4 overhead loudspeakers (see [Limits](#limits)) | `imm.*`, `fold.timbre` |
| `ambix` | 36 (order 5) | the field itself, ACN order, SN3D (Nachbar et al. 2011) | `delivery.true_peak` |
| `adm_bw64` | one per object | Audio Definition Model in BW64 (ITU-R BS.2076-3, BS.2088-1) with `loudnessMetadata` | `adm.*` |
| `atmos_music` | one per object | the same ADM file against the public music delivery figures: 48 kHz/24-bit, -18 LKFS ceiling, -1 dBTP, 50 ms conform | `delivery.loudness_ceiling`, `delivery.conform` |
| `iamf` | one per object | the ADM file through the external AOMedia iamf-tools encoder; absent encoder is an error, never a fallback | `iamf.container` |

List `stereo` first: the `fold.*` rows compare every other format with it. A format that fails its rows stays in `out/_draft_master_<format>.wav`. Every certified stereo master is kept as `out/master_vNN.wav`.

What 3.1 added: AllRAD2 as the default loudspeaker decoder (plane-wave power spread under 0.6 dB on the six layouts at order 5, against 4.7-7.9 dB for AllRAD), a 1500 Hz MagLS crossover with a capped diffuse-field EQ, opt-in near-field-coded HOA for close static sources, ADM BS.2076-3 with a measured `loudnessMetadata`, and the `atmos_music` / `iamf` deliverables.

What 3.0 added: rendered mono (`MonoBus`); BS.1770 loudness and a linked true-peak limiter for any channel count; the `fold.*` and `imm.loudness` rows; CPU or GPU chosen once (`scripts/compute.py`, `MUSICGEN_DEVICE`); parallel mixing (`render.mix_workers`); and master, room and decode choices as preset keys.

Running a real 38-track cue through all six formats showed that a head-filtered stereo master adds up 4-5 dB low at 450-1500 Hz, so `fold.mono` failed until it was decoded for loudspeakers. It also showed that a green gate does not mean the cue has the pressure its brief asked for; `scripts/helpers/arc_report.py` prints the loudness arc per section for that check.

## What's new

* **An effects engine in JSON.** 27 effects (`scripts/fx_engine/`) cover creative treatments (riser, tape stop, reverse swell, freeze, grain cloud, shimmer, Doppler) and mixing tools (saturator with six modes at 4x oversampling, de-esser, gate, parallel and upward compression, band-dependent width, tilt EQ, frequency shifter, resonator bank, a ducked ping-pong delay). Parameters can move over time with `automate`, ready shapes are recipes (`{"chain": "build_riser", "start_s": a, "end_s": b}`), and 34 chains ship in `references/data/presets/fx/`. A new shape is a JSON file, never a script. Ranges are checked by `mix_schema.fx_problems` and stage 2 (`preflight.fx`). `references/sound-design/fx-engine.md`
* **Mixing as preset data.** A mix preset's `fx` table (`*`, `@role`, or an instrument or `sfx:<preset>` name) and `mastering.fx` carry any effect. A preset lists only what the piece changes; every other key is the shipped default in `references/data/mix_defaults.json`. `references/mixing/mixing-and-mastering.md` section 13
* **Sound-model effects with engine physics.** SFX are parameter sets in `presets/sfx/`, built from an excitation, a resonator and control curves. A vehicle's firing frequency follows rpm and cylinder count, a gear shift multiplies the rpm by the ratio of the new gear to the old, with a power gap on an upshift and a blip on a downshift. Doppler comes from the trajectory, and a shared room preset with scenes per section puts music and effects in one space. Sound effects are excluded from the harmony and drone audits (`roles.is_sound_effect`).
* **Gate rows read the piece's own scenes.** Every threshold is data with its source in `references/data/presets/gate/data/rows.json`; a declared rest or stinger silence is honoured by `dropout`, `stem.dead` and `scene.silence_honoured`; what a failing row asks you to change is data too (`feedback.json`). Genre starting profiles ship: `orchestral`, `rock_band`, `hiphop`, `jazz_ensemble`, `world_percussion`, `game_loop`.
* **Root cause before any tolerance.** `scripts/rca.py` names the time, the stems and a verdict (`fault`, `mismatch`, `unknown`) for a failing row; `scripts/debug_audio.py` reports which lever moves it. Relaxing a row that matters to the piece is the user's decision (AGENTS.md rule 20), and revising a certified piece follows the checklist in rule 21.
* **A lessons-learnt system.** `lessons/` holds what went wrong before as YAML front matter, one file per kind of problem (stem rows, master rows, sound effects, mixing, arrangement, engine notes, process). `python scripts/lessons.py find "<symptom>"` and `suggest --log <pipeline log>` return the matching entries (symptom, cause, what to measure first, fix, what to avoid) before any fix; `add`, `update` and `check` keep it small and free of duplicates. Reading it before research and updating it after every fix is mandatory (AGENTS.md step 3.0, rule 22).
* **Two finished pieces to read.** `projects/quiet_frequency_trailer/` is a 120 s action-trailer cue with a gear-by-gear motorcycle, a V8, radio, a story clock shared by score and sound models, and stereo plus 8-channel 7.1 delivery. `projects/indo_afro_sunrise/` is a stereo piece on the instrument families, with lead and group vocals. Both were certified by the gate; neither was auditioned by the author of this note.

## Installation

Needs **Node.js 22.20+**. Install the skill for your agent, then clone the repository for the DSP engine.

```bash
npx skills add rashee1997/music-generator            # add -g for global; -a claude-code -y for one agent
git clone https://github.com/rashee1997/music-generator.git && cd music-generator
python scripts/setup_project.py          # venv, dependencies, SoundFont, smoke test
python scripts/setup_project.py --ears   # optional (~1 GB): lets listen.py evaluate audio
```

**ffmpeg** is needed only for video; **PyTorch** is optional.

## Quick start

With an agent: *"Compose a 60-second underscore for a slow reveal of a mountain range — cold, patient, no drums."*

```bash
source .venv/bin/activate                                   # Windows: .venv\Scripts\activate
python scripts/setup_project.py --new-project my-project --title "My Track"
python scripts/pipeline.py my-project/scores/my_track_score.json --project my-project
python scripts/helpers/arc_report.py my-project/out/master.wav --score my-project/scores/my_track_score.json
python scripts/helpers/compress_mp3.py my-project/out/master_v01.wav -o my-track.mp3 -b 320k
```

Name the formats in the score: `"output_targets": ["stereo", "mono", "immersive_5_1", "immersive_7_1_4", "ambix", "adm_bw64"]`. With none named, a piece is delivered as stereo plus 8-channel 7.1. To render only some formats, add `--only stereo,immersive_7_1_4` to `pipeline.py`; every format added makes the render longer. `MUSICGEN_SFZ_WORKERS=2` lowers memory use on a long render. Film scoring is in [`AGENTS.md`](AGENTS.md) section 9.

## Pipeline

```text
brief / score → 1 compose → 2 linter → 3 humanize → 4 stems (4b stem gate) → 5 mix & master (5b extra formats) → 6 gates → 7 certified release
```

The agent's rules are in [`AGENTS.md`](AGENTS.md): sound design lives in presets, notes in scores, intent in direction sheets; acoustic values are cited or measured; a failing row is fixed in the piece, never loosened. Every row is in [`references/mixing/quality-gate.md`](references/mixing/quality-gate.md).

## Methods used

Each is named with its source and the file that implements it. Derivations are in [`docs/PSYCHOACOUSTICS.md`](docs/PSYCHOACOUSTICS.md).

* **Loudness:** K-weighted gated loudness, short-term loudness and loudness range, and 4× oversampled true peak (ITU-R BS.1770-5, EBU Tech 3341 and 3342), with channel weights for any layout. `scripts/loudness.py`
* **Linked true-peak limiter:** one gain curve for all channels, the engine's own construction. `scripts/spatial_engine/master.py`
* **Rendered mono and fold bands:** level compensation bounded to the 3 dB that averaging two channels loses, and band-by-band spectral comparison in ERB bands (Glasberg & Moore 1990). `scripts/spatial_gate.py`
* **Ambisonic encoding:** real spherical harmonics in ACN order, SN3D for AmbiX (Zotter & Frank 2019; Nachbar et al. 2011). `scripts/spatial_engine/hoa.py`
* **Decoding:** magnitude least squares for headphones (Schörkhuber et al. 2018; Hold et al. 2023); AllRAD with max-rE weights for loudspeakers (Zotter & Frank 2012).
* **VBAP:** vector base amplitude panning with unit-power gains (Pulkki 1997). `scripts/spatial_engine/pan.py`
* **Propagation:** 1/r spreading, ISO 9613-1 air absorption, Doppler, image-source reflections (Allen & Berkley 1979), Eyring reverberation (1930), room measures (ISO 3382-1). `scripts/airabs.py`, `scripts/spatial_hrtf/`
* **Layouts:** ITU-R BS.2051-3 positions, BS.775-3 two-channel fold-down, Linkwitz-Riley 4th-order crossover (Linkwitz 1976), all-pass decorrelation (Kendall 1995). `scripts/spatial_engine/`
* **Gates:** critical-band roughness (Plomp & Levelt 1965; Daniel & Weber 1997), Terhardt's hearing threshold as a relative weighting, spiral-array tonal tension (Chew 2000), bar syncopation index (Witek et al. 2014). `scripts/quality_gate.py`
* **Performance and voice:** KTH performance rules (Friberg et al. 2006), Liljencrants-Fant glottal model (Fant et al. 1985). `scripts/humanize.py` (facade) + `scripts/humanize_engine/`, `scripts/vocal_engine/`

Citations are as the code and its docs state them; page numbers were not re-checked against the publishers' pages.

## Repository structure

`SKILL.md`, `AGENTS.md` (agent entry point and rules) · `lessons/` (what went wrong before, searched by `scripts/lessons.py`) · `scripts/` (pipeline, mixing, gates; `spatial_engine/`, `spatial_hrtf/`, `vocal_engine/`, `helpers/`) · `references/` (guides and JSON presets) · `knowledgebase/` (sourced facts) · `templates/` · `video-mixer/` · `docs/` · `tests/` (about 1,100, each gate row with a passing and a failing control).

## Limits

* **Metrics are not ears.** A cue rendered for this repository passed every row and was heard as too calm.
* **The GPU path has never run on a GPU**; only the CPU kernel and its fallbacks are tested.
* **One measured head** (FABIAN, Brinkmann et al. 2017); a listener's own `.sofa` or `.mat` set can be supplied.
* **The stereo master is a headphone render or a loudspeaker render**, chosen by `immersive.stereo_decode`; one file is not both.
* **The 7.1 layout files carry the wrong system letters.** In ITU-R BS.2051 the letter H is the 22.2 system; this repository stores its 7.1, 7.1.2 and 7.1.4 rings as `itu_bs2051_system_h`, `_i`, `_j`. Do not claim BS.2051 conformance for the 7.1 family until the files are compared with the standard and renamed. The 5.1 family is not compared either.
* **The default sound bank is General MIDI**; the free SFZ library it installs (Sonatina Symphonic Orchestra) is dry and incomplete on case-sensitive file systems.
* **Random sources are redrawn when a piece's length changes**, so a row can pass on one render and fail on the next; fix the track, not the row.

More in [`references/workflow/troubleshooting-and-limits.md`](references/workflow/troubleshooting-and-limits.md).

## Credits & Attributions

* **Spatial audio:** `scripts/spatial_hrtf/` includes a modified copy of [spaudiopy](https://github.com/chris-hld/spaudiopy) by Chris Hold (MIT License).
* **HRTF data:** the **FABIAN HRTF Database** from TU Berlin ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [DOI: 10.14279/depositonce-5718.5](https://doi.org/10.14279/depositonce-5718.5)), fetched via `setup_project.py`.
* **Synthesis:** [tinysoundfont](https://github.com/schellingb/tinysoundfont) by Bernhard Schelling (MIT License) with the [GeneralUser GS SoundFont](https://schristiancollins.com/generaluser.php) by S. Christian Collins.
* **Optional orchestra:** Sonatina Symphonic Orchestra (Mattias Westlund and Peter Eastman, CC Sampling Plus 1.0) via [sfizz](https://github.com/sfztools/sfizz).

## License

[GNU AGPLv3](LICENSE) — Copyright (C) 2026 rasheedh
