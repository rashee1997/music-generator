# music-generator

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Agent Skill](https://img.shields.io/badge/agent%20skill-SKILL.md-black.svg)](SKILL.md)

An agent skill that composes, renders, mixes and certifies original music against psychoacoustic law.

Give it a mood, a scene, a duration, or a video file. It researches the idiom, writes a direction sheet,
declares a score, renders it, and refuses to hand over the master until every quality gate passes.

## Listen

**Black Jaguar — cinematic chase** · D minor · 134 BPM · jungle ambience, stalking strings, chromatic pursuit, build and release

▶ **[Listen in the browser](https://rashee1997.github.io/music-generator/docs/listen.html)** · [MP3, 320 kbps](assets/samples/black-jaguar-cinematic-chase.mp3)

GitHub strips `<audio>` tags from Markdown, so the player lives on the project's [Pages site](https://rashee1997.github.io/music-generator/docs/listen.html).

## Install

### As an agent skill

Install with the open skills CLI. Requires **Node.js 22.20 or later**.

```bash
# install into the current project (.agents/skills/, .claude/skills/, …)
npx skills add rashee1997/music-generator

# or make it available to every project
npx skills add rashee1997/music-generator -g

# non-interactive, pick one agent
npx skills add rashee1997/music-generator --skill music-generator -a claude-code -y
```

The repository exposes exactly one skill, `music-generator`, from its root `SKILL.md`.

```bash
npx skills list                      # confirm it is installed
npx skills update music-generator    # pull the latest version from main
```

Installing the skill copies instructions only. The engine, presets and knowledge base are not fetched
by the CLI — clone the repository next to your work and run the setup below.

### As a standalone project

```bash
git clone https://github.com/rashee1997/music-generator.git
cd music-generator
python scripts/setup_project.py          # core: .venv, packages, SoundFont, smoke test
python scripts/setup_project.py --ears   # also earshot, so listen.py can hear the mix (~1 GB)
```

`setup_project.py` uses [uv](https://docs.astral.sh/uv/) when available (`pip install uv`) and falls back
to `python -m venv` + pip. It writes `.venv/`, installs the pinned packages from `requirements.txt`, places the
GeneralUser GS SoundFont in `~/.cache/music-generator`, and runs a smoke test.

Use the environment it created:

```bash
# Windows
.venv/Scripts/python.exe scripts/pipeline.py --help
# macOS / Linux
.venv/bin/python scripts/pipeline.py --help
```

System dependency: **ffmpeg**, required only by `video-mixer/` for probing, muxing and dialogue extraction.

## Quick start

```bash
python scripts/setup_project.py --new-project my-project --title "My Track"
python scripts/pipeline.py my-project/scores/my_track_score.json --project my-project
```

If gates fail, the uncertified mix stays at `out/_draft_master.wav` and `out/master.wav` is untouched.
Change one lever and run again.

To let the skill drive it instead, just ask in your agent:

> Compose a 60-second underscore for a slow reveal of a mountain range — cold, patient, no drums.

It will read `SKILL.md`, open the references it needs, research the idiom, write the direction sheet,
scaffold presets, write the score and iterate the pipeline until the gates are green.

## Auditing existing music

```bash
python scripts/pipeline.py path/to/master.wav --check-only
```

Reports loudness, true peak, balance, masking and grid problems in `reports/ci_report.json` without
re-rendering or altering the audio.

## The problem with code-generated music

When LLMs or scripts generate music, they fail in ways that are predictable and audible, because a text
model cannot hear what it writes:

1. **Mechanical rigidity or random chaos.** Naive code locks notes to the grid with static velocities (a 1990s MIDI file). Told to "humanize", an LLM scatters notes unpredictably — zig-zag lines, unrecovered leaps, incoherent rhythm — passing simple rules while sounding unmusical.
2. **Harmonic mud and voicing violations.** Voices clustered below middle C violate the low-interval limit, muddying 100–300 Hz. Closed-position major sevenths put the root and seventh adjacent in one register, producing a grating minor second.
3. **Cochlear roughness.** Stacked overtones that collide inside a quarter of a critical bandwidth set the basilar membrane beating; the ear tires within seconds.
4. **Spectral masking.** Pads, rhythm guitars and bass swallow the vocal or lead in 250–500 Hz when nothing carves a pocket or uses unmasking.
5. **Static harmony or broken tension.** Progressions either stagnate or teleport between unrelated keys with no voice leading and no cadence resolution.

## What this system does instead

Music generation is treated as a **CI/CD pipeline**: every piece is constrained by perceptual law, humanized
from measurement rather than taste, staged in space, mixed from a preset, and certified by gates before
anything is delivered.

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

## The eight-step workflow

The skill refuses to skip stages. Each step leaves an artifact you can inspect:

| Step | Action | Artifact |
|---|---|---|
| 1 | Create project | `direction/`, `presets/`, `scores/`, `out/`, `reports/`, `STATUS.md` |
| 2 | Research the idiom | `reports/research_<topic>.md` with KB citations and sources |
| 3 | Write the direction sheet | `direction/direction_<title>.json` |
| 4 | Scaffold presets | Instrument, vocal, space and mix presets with unique spatial placement |
| 5 | Write the score | `scores/<title>_score.json`, referencing presets only |
| 6 | Render and gate | `out/master_vNN.wav`, `stems/`, `midi/`, `reports/ci_report.json` |
| 7 | Revise one lever | Re-render until 0 FAIL (max 5 attempts) |
| 8 | Listen and deliver | `listen.py` report, then the self-check in `STATUS.md` |

## Delivery: metadata and versions

A render that passes every gate is certified, not merely written. Certification does three things after the
musical gate passes:

- **Versions the master.** Each certified render becomes `out/master_v01.wav`, `master_v02.wav`, … and `out/master.wav` is refreshed as a copy of the newest. An earlier master is never overwritten, so a previous take can always be recovered.
- **Records the change.** `out/versions.json` lists every version with its timestamp, measurements and the gate failures it cleared (`cleared balance; kick.grid`, or `first certified render`). Inspect it with `python scripts/helpers/version_manager.py list --project <project>`.
- **Tags the deliverable.** Standard tags come from `presets/metatdats/metadata.json` (artist, album, copyright, licence, publisher, ISRC, language), then from the score (title, genre, year, a factual `key · BPM · piece_type` comment), then from the project's own `metadata.json` overrides. They are written to `out/master.json` beside the audio.

MP3 compression is deliberately **manual** and never part of the pipeline:

```bash
python scripts/helpers/compress_mp3.py out/master_v01.wav -o my-track.mp3 -b 320k
```

It carries the sidecar tags into the MP3. The gate rows `meta.tags` and `meta.version` only trace this record —
they warn rather than fail, and report `INFO` on a piece's first render. A new project is scaffolded with
`presets/gate/` for its gate profile and a `metadata.json` for its own tag overrides.

## Structure

```text
music-generator/
├── SKILL.md         the skill entry point: when to use it, the eight-step workflow
├── AGENTS.md        the rule book: read table, research, presets, gate profiles, self-check
├── scripts/         engine: pipeline, composing, mixing, gates, renderers
│   └── helpers/     metadata ingestion, master versioning, manual MP3 encoding
├── presets/         default instrument, mix, space, vocal and metadata-preset files
│   └── metatdats/   the standard delivery tags every render inherits
├── knowledgebase/   genre, culture and DSP research
├── references/      guides and schemas
├── templates/       project, direction-sheet and score templates
├── video-mixer/     cut detection, ducking and muxing
├── assets/samples/  rendered demo audio
├── tests/           integrity, soul, spatial and pipeline tests
└── docs/            theory and documentation
```

## Documentation

| Document | What it covers |
|---|---|
| [SKILL.md](SKILL.md) | What the skill does and the eight-step workflow |
| [AGENTS.md](AGENTS.md) | The rule book: read table, research, presets, gate profiles, self-check |
| [docs/README.md](docs/README.md) | Index of every document, plus the engine's known limitations |
| [docs/PSYCHOACOUSTICS.md](docs/PSYCHOACOUSTICS.md) | The perceptual laws the gate enforces: thresholds, equations and peer-reviewed sources |
| [docs/listen.html](docs/listen.html) | The Pages audio player for the rendered sample |
| [references/](references/) | Brief reading, music direction, mixing and mastering, quality gate, vocals, spatial audio, SFZ, video scoring, troubleshooting |
| [knowledgebase/](knowledgebase/) | Genre, culture and DSP knowledge |
| [templates/](templates/) | Project, direction-sheet and score templates |

## Limitations

Stated plainly, because every delivery should carry them:

- **The engine cannot hear.** Numbers and `listen.py` stand in for ears; the first render is a draft. Without earshot installed, the report is measurement only.
- **Even with earshot it is an opinion.** Taste, whether a raga or maqam is correct, whether an instrument sounds convincing and how the music sits in picture are never measured.
- **The default bank is General MIDI.** Good, not concert-grade. Symphonic work needs a multisampled SFZ library installed per project.
- **No words.** Synthesised voices are texture — choirs, oohs and hums — with no consonants and no language; a hum-to-vowel change starts a new phrase.
- **Traditional idioms are approximations** unless a preset or a user recording supplies the real instrument.
- **Spatial depth is limited by preset.** Head-related delays and elevation apply only to presets with `spatial.binaural: true`; everything else gets pan, distance filtering, width and one shared room.
- **Diagnostics report, they do not fix.** Mix measurements say what is masked or colliding; they cannot say what sounds good.
- **Video audio is not auditioned.** Nothing in the video path listens to the bed under speech, and cut detection misses fades and dissolves.
- **Loudness targets are starting points.** Verify against the current platform specification before publishing.

The full list lives in [references/troubleshooting-and-limits.md](references/troubleshooting-and-limits.md).

## Credits

- `scripts/spatial_hrtf/` contains a vendored copy of [spaudiopy](https://github.com/chris-hld/spaudiopy) by Chris Hold (MIT License, kept in `scripts/spatial_hrtf/LICENSE`) with the small changes listed in `scripts/spatial_hrtf/README.md`.
- Head-Related Transfer Function data is from the **FABIAN HRTF Database**, TU Berlin, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ([DOI: 10.14279/depositonce-5718.5](https://doi.org/10.14279/depositonce-5718.5)), downloaded via `setup_project.py` and not bundled in this repository.
- SoundFont synthesis utilizes [tinysoundfont](https://github.com/schellingb/tinysoundfont) by Bernhard Schelling (MIT License) with the [GeneralUser GS SoundFont](https://schristiancollins.com/generaluser.php) by S. Christian Collins.

## Third-party libraries, attributions and key equations

All dependencies are used in accordance with their respective open-source licenses.

### Core scientific computing

| Library | License | Repository | Purpose and key mathematical operations |
|---|---|---|---|
| [NumPy](https://numpy.org/) | BSD-3-Clause | [GitHub](https://github.com/numpy/numpy) | Vectorized numerical computation, linear algebra, FFT operations for spectral analysis, windowing functions |
| [SciPy](https://scipy.org/) | BSD-3-Clause | [GitHub](https://github.com/scipy/scipy) | Digital signal processing (`scipy.signal`), IIR/FIR filter design, Welch PSD, polyphase decimation (`resample_poly`) |

### Audio I/O and processing

| Library | License | Repository | Purpose and key algorithms |
|---|---|---|---|
| [soundfile](https://python-soundfile.readthedocs.io/) | BSD-3-Clause | [GitHub](https://github.com/bastibe/python-soundfile) | C-level audio I/O via libsndfile; bit-depth preservation (32-bit float streaming) |
| [Pedalboard](https://spotify.github.io/pedalboard/) | GPL-3.0 | [GitHub](https://github.com/spotify/pedalboard) | Spotify DSP engine: true-peak brickwall limiting, dynamic compression, stereo spatialization |
| [pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) | MIT | [GitHub](https://github.com/csteinmetz1/pyloudnorm) | EBU R128 and ITU-R BS.1770-4 loudness measurement with K-weighting pre-filter |

### MIDI and music theory

| Library | License | Repository | Purpose and key algorithms |
|---|---|---|---|
| [pretty_midi](https://craffel.github.io/pretty-midi/) | MIT | [GitHub](https://github.com/craffel/pretty-midi) | MIDI 1.0 container parsing, timing quantization, note array extraction |
| [mido](https://mido.readthedocs.io/) | MIT | [GitHub](https://github.com/mido/mido) | Real-time and file-based MIDI stream serialization |
| [music21](https://web.mit.edu/music21/) | BSD-3-Clause / LGPL | [GitHub](https://github.com/cuthbertLab/music21) | Computational musicology, Roman numeral voice-leading analysis, tonal pitch class matrices |

### Analysis and diagnostics

| Library | License | Repository | Purpose and key algorithms |
|---|---|---|---|
| [librosa](https://librosa.org/) | ISC | [GitHub](https://github.com/librosa/librosa) | Short-Time Fourier Transform, constant-Q transform, 12-bin chroma profiling, onset envelope detection |
| [matplotlib](https://matplotlib.org/) | PSF | [GitHub](https://github.com/matplotlib/matplotlib) | Offline diagnostic plots of spectral masking curves, roughness surfaces and rhythm trees |

### Spatial audio and utilities

| Library | License | Repository | Purpose and key algorithms |
|---|---|---|---|
| [h5py](https://www.h5py.org/) | BSD-3-Clause | [GitHub](https://github.com/h5py/h5py) | HDF5 access for multidimensional SOFA / FABIAN HRTF impulse response grids |
| [requests](https://requests.readthedocs.io/) | Apache-2.0 | [GitHub](https://github.com/psf/requests) | HTTPS asset acquisition for soundbanks and acoustic impulse responses |
| [resampy](https://github.com/bmcfee/resampy) | ISC | [GitHub](https://github.com/bmcfee/resampy) | High-order bandlimited sinc interpolation for sample-rate conversion |

### Psychoacoustic and music theory foundations

The engine implements formal models from peer-reviewed acoustic and cognitive literature:

| Model | Citation | Purpose and defining formulation |
|---|---|---|
| **Low-Interval Limit** | Huron, D. (2001). [Tone and Voice: A Derivation of the Rules of Voice-Leading from Perceptual Principles](https://doi.org/10.1525/mp.2001.19.1.1). *Music Perception*, 19(1), 1–64. | Register-dependent frequency minimums that prevent basilar-membrane critical-band roughness in the low register ($f < 250$ Hz). |
| **Krumhansl-Schmuckler key profiles** | Krumhansl, C. L. (1990). [*Cognitive Foundations of Musical Pitch*](https://global.oup.com/academic/product/cognitive-foundations-of-musical-pitch-9780195148367). Oxford University Press. | Tonal hierarchy correlation of pitch-class distributions against probe-tone ratings: $r = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum (x_i - \bar{x})^2 \sum (y_i - \bar{y})^2}}$. |
| **Chew's spiral array** | Chew, E. (2000). [*Towards a Mathematical Model of Tonality*](https://dspace.mit.edu/handle/1721.1/9139). Doctoral dissertation, MIT. | Pitch classes mapped into a 3D helix where line-of-fifths intervals stay contiguous: $\mathbf{p}(k) = [r \sin(k\pi/2),\, r \cos(k\pi/2),\, k h]^T$; measures Tensile Strain and Cloud Momentum. |
| **Plomp-Levelt sensory consonance** | Plomp, R., & Levelt, W. J. M. (1965). [Tonal Consonance and Critical Bandwidth](https://doi.org/10.1121/1.1909741). *JASA*, 38(4), 548–560. | Dissonance between partials as a function of critical bandwidth: $d(f_1, f_2) = e^{-a s \Delta f} - e^{-b s \Delta f}$, peaking near 25% of the critical band. |
| **Sethares dissonance curves** | Sethares, W. A. (1998/2005). [*Tuning, Timbre, Spectrum, Scale*](https://doi.org/10.1007/978-1-84628-113-6). Springer-Verlag. | Generalizes sensory dissonance to non-harmonic spectra and microtonal temperaments by integrating all pairwise partial clashes. |
| **Witek-Vuust syncopation curve** | Witek, M. A. G. et al. (2014). [Syncopation, Body-Movement and Pleasure in Groove Music](https://doi.org/10.1371/journal.pone.0094446). *PLOS ONE*, 9(4), e94446. | Inverted-U groove index across metric levels using the Bar Syncopation Index ($0.15 \le BSI \le 5.5$). |
| **Moore-Glasberg ERB filters** | Moore, B. C. J., & Glasberg, B. R. (1983). [Suggested formulae for calculating auditory-filter bandwidths and excitation patterns](https://doi.org/10.1121/1.389861). *JASA*, 74(3), 750–753. | Equivalent Rectangular Bandwidth for masking pockets: $\text{ERB}(f) = 24.7\,(4.37 f/1000 + 1)$ Hz. |
| **Meyer's gap-fill principle** | Meyer, L. B. (1956). [*Emotion and Meaning in Music*](https://press.uchicago.edu/ucp/books/book/chicago/E/bo5479468.html). University of Chicago Press. | Wide disjunct leaps ($\ge 5$ semitones) must resolve conjunctly in the opposite direction ($\ge 45\%$ step motion). |
| **IDyOM information dynamics** | Pearce, M. T. (2005). [*The Construction and Evaluation of Statistical Models of Melodic Predictability*](https://qmro.qmul.ac.uk/xmlui/handle/123456789/1376). PhD thesis, City University London. | Variable-order Markov Shannon entropy ($1.2 \le H \le 3.8$ bits) and surprise ($I = -\log_2 P$) balancing predictability with cognitive interest. |
| **ITU-R BS.1770-4 / EBU R128** | International Telecommunication Union (2015). [ITU-R BS.1770-4](https://www.itu.int/rec/R-REC-BS.1770-4-201510-I/en). | Loudness gating: $L_K = -0.691 + 10 \log_{10} \sum_i G_i z_i$ after K-weighting pre-filter. |

## License

[GNU AGPLv3](LICENSE) — Copyright (C) 2026 rasheedh
