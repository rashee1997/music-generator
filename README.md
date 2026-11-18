# music-generator

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Agent Skill](https://img.shields.io/badge/agent%20skill-SKILL.md-black.svg)](SKILL.md)

An AI agent skill and Python audio pipeline that composes, renders, mixes and validates original music from text briefs, scores or video, and delivers one mix as stereo, mono, 5.1, 7.1.4, an ambisonic sound field and object audio.

**Demo:** **Black Jaguar (Cinematic Chase)** — *D minor · 134 BPM*
▶ **[Listen in Browser](https://rashee1997.github.io/music-generator/docs/listen.html#black-jaguar)** · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/black-jaguar-cinematic-chase.mp3)**
▶ **[Arabian Nights: The Desert Crossing (Immersive 2.0)](https://rashee1997.github.io/music-generator/docs/listen.html#arabian-nights)** — with the desert air, mixed on the ambisonic bus · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/arabian-nights-desert.mp3)**
▶ **[The Unwelcome Crossing (haunted desert cue, object audio)](https://rashee1997.github.io/music-generator/docs/listen.html#haunted-desert)** — 48 kHz game master, with 7.1.2, 7.1 and ADM object renders · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/haunted-desert-crossing.mp3)**

> Everything here is verified by tests, probes and gate rows. The pipeline's numbers measure faults and levels, not taste:
> see [Limits](#limits).

## What it does

* **Writes** with voice-leading and melodic rules, spiral-array tonal tension [24] and metric-tree syncopation.
* **Performs** with humanization that separates shared tempo drift from individual motor error [26].
* **Sounds** from a General MIDI SoundFont, optional SFZ orchestras played per articulation, a glottal-source voice [27], physical sound models (footsteps, foliage, rain) and animal calls stored as data.
* **Places** every part in space: measured-HRTF binaural, shared room acoustics, and the ambisonic bus below.
* **Mixes** from JSON presets only: gain staging, sidechain, room send per role, master chain, loudness target.
* **Gates** every render with about 390 rows. A failing row is a fact: the piece or the preset changes, the threshold does not.
* **Scores to picture** at three timescales; a reel assembles only certified cues.

## Immersive 3.0

One ambisonic mix, judged once, delivered in every channel count a listener might have. No format is a degraded copy of another.

| `output_targets` | Channels | How it is made | Judged by |
|---|---|---|---|
| `stereo` | 2 | decoded from the bus: `immersive.stereo_decode` is `"binaural"` (headphones) or `"speakers"` (±30°, BS.775 [5]) | the whole gate |
| `mono` | 1 | **rendered**, not folded: no pan, width or head filter | `fold.mono` |
| `immersive_5_1`, `_5_1_2`, `_5_1_4` | 6 / 8 / 10 | VBAP [9] onto BS.2051-3 [4] layouts, a Linkwitz-Riley low-frequency channel [17], all-pass decorrelation of the surrounds [18] | `imm.*`, `fold.timbre` |
| `immersive_7_1`, `_7_1_2`, `_7_1_4` | 8 / 10 / 12 | a 7.1 ring with 0, 2 or 4 overhead loudspeakers (see [Limits](#limits)) | `imm.*`, `fold.timbre` |
| `ambix` | 36 (order 5) | the field itself, ACN order, SN3D [10][11] | `delivery.true_peak` |
| `adm_bw64` | one per object | Audio Definition Model in a BW64 container [6] | `adm.*` |

List `stereo` first: the `fold.*` rows compare every other format with that master. A format that fails its rows stays in
`out/_draft_master_<format>.wav`. Every certified stereo master is kept as `out/master_vNN.wav` (`out/versions.json`).

```text
 tracks ─► per-track decisions (EQ, dynamics, sends, ducking, distance) ──┐
                                                                          ▼
        ┌── unplaced ─► MonoBus ─────────────────────────────────► mono (rendered)
        │                        ┌─► binaural (MagLS) ─┐
 HoaBus ◄── placed sources ◄─────┤                     ├─► stereo ─► master chain, limiter
 (N+1)² channels                 ├─► speakers (AllRAD) ┘
        ▲                        ├─► LayoutBus: VBAP + LFE ─────────► 5.1 … 7.1.4
 reflections, tail, Doppler      ├─► field as-is, ACN/SN3D ─────────► AmbiX
                                 └─► one object per track ──────────► ADM BW64
```

What 3.0 added:

* **Rendered mono** (`MonoBus`): adding two channels would inherit the stereo master's panning and head filter.
* **BS.1770 loudness for any channel count** (`scripts/loudness.py`) with layout weights, and a **linked multichannel true-peak limiter**.
* **Fold rows** (`fold.mono`, `fold.timbre`, `fold.reference`, `imm.loudness`) so no format is the dull, thin or loud one.
* **CPU or GPU, chosen once** (`scripts/compute.py`, `render.compute.device` or `MUSICGEN_DEVICE`): FFT convolution and matrix products use a GPU when present and fall back to the CPU with a note.
* **Parallel stems and sources** (`render.mix_workers`): 14 sources of 20 s went from 34 s to about 10.6 s with identical samples.
* **Master and room numbers as preset keys**, including `mastering.highpass_order` and `immersive.stereo_decode`.

Running a real 38-track orchestral cue through all six formats found three things worth knowing. A head-filtered stereo
master adds up 4-5 dB low at 450-1500 Hz (its ears disagree there by design), so `fold.mono` failed until the master was
decoded for loudspeakers (worst band then +3.1 dB). A loud 80-120 Hz tone reads as `master.dc` drift, and the fix is a
steeper master high-pass, not a looser row. And a green gate does not mean the cue has the pressure its brief asked for:
`scripts/helpers/arc_report.py` prints the loudness arc per section for that check.

## Installation

Install the skill so your agent (`Claude Code`, `Cursor`, `Codex`, ...) gets `SKILL.md`, and clone the repository for the DSP engine. Needs **Node.js 22.20+**.

```bash
npx skills add rashee1997/music-generator            # into the current project; add -g for global
npx skills add rashee1997/music-generator --skill music-generator -a claude-code -y

git clone https://github.com/rashee1997/music-generator.git && cd music-generator
python scripts/setup_project.py          # venv, dependencies, SoundFont, smoke test
python scripts/setup_project.py --ears   # optional (~1 GB): lets listen.py evaluate audio
```

`setup_project.py` uses [uv](https://docs.astral.sh/uv/) if present, else `venv` + `pip`. **ffmpeg** is needed only for video; **PyTorch** is optional.

## Quick start

With an agent, just ask: *"Compose a 60-second underscore for a slow reveal of a mountain range — cold, patient, no drums."*

From the command line:

```bash
source .venv/bin/activate                                   # Windows: .venv\Scripts\activate
python scripts/setup_project.py --new-project my-project --title "My Track"
python scripts/pipeline.py my-project/scores/my_track_score.json --project my-project
python scripts/pipeline.py path/to/master.wav --check-only  # audit a WAV without rendering
python scripts/helpers/arc_report.py my-project/out/master.wav --score my-project/scores/my_track_score.json
python scripts/helpers/compress_mp3.py my-project/out/master_v01.wav -o my-track.mp3 -b 320k
```

Name the formats in the score: `"output_targets": ["stereo", "mono", "immersive_5_1", "immersive_7_1_4", "ambix", "adm_bw64"]`.
`MUSICGEN_SFZ_WORKERS=2` lowers memory use on a long render. Film: `setup_project.py --new-film`, `video_score.py`, `video-mixer/deliver/reel.py` (see [`AGENTS.md`](AGENTS.md) section 9).

## Pipeline

```text
[Brief / score]
  ├─ 1 Composition & voice leading   compose.py · theory.py · world.py
  ├─ 2 Pre-flight linter             pattern_audit.py
  ├─ 3 Humanization                  humanize.py
  ├─ 4 Stem rendering                tinysoundfont · sfz_render · vocal_engine · environment · sfx_engine   (4b stem gate)
  ├─ 5 Mix & master                  mixer.py → HoaBus / LayoutBus / MonoBus → limiter   (5b extra deliverables)
  ├─ 6 Quality gates                 quality_gate.py · naturalness_check.py · music21
  └─ 7 Certified release             out/master_vNN.wav · master_<format>.wav · ci_report.json
```

The agent's rules and phases are in [`AGENTS.md`](AGENTS.md): sound design lives in presets, notes in scores, intent in direction sheets; acoustic values are cited or measured; a failing row is fixed in the piece, never loosened. The full row table is [`references/mixing/quality-gate.md`](references/mixing/quality-gate.md); `loudness`, `true_peak`, `clipping`, `silence`, `clicks` and `channels` are protected from relaxation.

## Equations in use

Each block names the file that implements it. Numbers in brackets are in [References](#references); worked values and the head, near-field and room-measure derivations are in [`docs/PSYCHOACOUSTICS.md`](docs/PSYCHOACOUSTICS.md).

**Loudness and true peak** (`scripts/loudness.py`). After K-weighting, over 400 ms blocks overlapping 75 %, with channel weights $G_c$ (1.0 front, +1.5 dB surround, low-frequency channel excluded) [1]:

$$
z_j = \sum_c G_c \frac{1}{N}\sum_{k\in j} x_{c,k}^2, \qquad L_j = -0.691 + 10\log_{10} z_j\ \text{[LKFS]}
$$

Integrated loudness averages the blocks that pass an absolute gate at −70 LKFS and a relative gate 10 LU lower [1]. Short-term loudness is the same measure over 3 s [2]; loudness range is the 10th-95th percentile spread of short-term values above a gate 20 LU under their power mean [3]; true peak is the maximum of the signal oversampled 4× [1].

**Linked limiter** (`scripts/spatial_engine/master.py`, the engine's own construction). With per-sample oversampled peak $p_n$ over all channels, ceiling $c$ and release constant $k = e^{-1/(\tau f_s)}$, one gain multiplies every channel so the image does not move:

$$
a_n = -\ln\min\left(1, \tfrac{c}{p_n}\right), \qquad \tilde a_n = \max_{j\le n} a_j k^{\,n-j}, \qquad g_n = e^{-\tilde a_n}
$$

**Rendered mono and fold rows** (`scripts/spatial_engine/render.py`, `scripts/spatial_gate.py`). Two unrelated channels average $10\log_{10}2 \approx 3.01$ dB low, so a stereo part is mixed down as $m = \tfrac12(L+R)$ and given back that level, bounded by `compensate_max_db`. The fold rows compare long-term spectra in bands one ERB wide, with ERB-rate $= 21.4\log_{10}(0.00437 f + 1)$ [20]. With reference and candidate band powers $P^{ref}_b$, $P^{cand}_b$, level-matched over the bands $K$ within `fold_floor_db` of the loudest:

$$
\delta_b = 10\log_{10}\frac{P^{cand}_b}{P^{ref}_b} - 10\log_{10}\frac{\sum_{K}P^{cand}_b}{\sum_{K}P^{ref}_b}, \qquad \text{PASS} \iff \max_{b\in K}|\delta_b| \le \delta_{\max}
$$

A layout's two-channel fold is $L' = \sum_c g^L_c x_c$, $R' = \sum_c g^R_c x_c$ with the BS.775 coefficients stored in the layout preset [5].

**Ambisonic bus** (`scripts/spatial_engine/hoa.py`). A source at $(\theta,\phi)$ is written as $b_{nm}(t) = s(t)\,Y_n^m(\theta(t),\phi(t))$ with real spherical harmonics, $0\le n\le N$ [11]: $(N+1)^2$ channels (25 at order 4, 36 at order 5), ACN index $n^2+n+m$, rescaled by $\sqrt{4\pi/(2n+1)}$ to SN3D for AmbiX [10]. A moving source only changes gains, so no filter is switched. Headphone decoding uses magnitude least squares from the measured head [12][13]. Loudspeaker decoding is all-round (AllRAD): $J$ virtual loudspeakers on a near-uniform sphere, each panned onto the real layout by VBAP [9][8]:

$$
D = \frac{4\pi}{J}\,G^{\mathsf T} Y\,\mathrm{diag}(w_n), \qquad w_n = P_n\!\left(\cos\tfrac{137.9^\circ}{N+1.51}\right)
$$

($w_n$: max-$r_E$ weights [8][11]; $D$ is scaled so a plane wave keeps unit power.) VBAP solves $\mathbf g = L^{-1}\mathbf p$ in the enclosing loudspeaker triplet and normalises $\lVert\mathbf g\rVert_2 = 1$, so loudness does not change as a source moves [9].

**Propagation** (`scripts/airabs.py`, `scripts/spatial_hrtf/`). Level falls as $1/r$; air filters highs with the ISO 9613-1 coefficient $\alpha(f)$ [7] as the linear-phase filter $10^{-\alpha(f)d/20}$ (4.7 dB/km at 1 kHz, 159 dB/km at 10 kHz, 20 °C, 50 % RH). Doppler reads the direct sound at $t - \lambda\,(d(t)-d_{\min})/c$ with $c=343$ m/s, and every reflection with its own path. Early reflections are image sources [14] of amplitude $g_i = \frac{1}{r_i}\prod\sqrt{1-a_k(f)}$; the tail follows Eyring [15]:

$$
T_{60}(f) = \frac{24\ln 10}{c}\cdot\frac{V}{-S\ln(1-\bar a(f)) + 4m(f)V}
$$

Room measures (IACC, $C_{80}$) are taken on the impulse response as ISO 3382-1 defines them [16].

**Crossover and decorrelation** (`scripts/spatial_engine/bass.py`, `decorrelate.py`). The low-frequency channel uses a 4th-order Linkwitz-Riley crossover, two cascaded 2nd-order Butterworth sections in phase at the crossover [17]. Surround and height channels carrying one signal are separated by a first-order all-pass per channel, $y[n] = -a\,x[n] + x[n-1] + a\,y[n-1]$ [18].

**Psychoacoustic gates** (`scripts/quality_gate.py`, `scripts/naturalness_check.py`). Critical bands one ERB wide [20]; roughness from pairs of partials inside a critical bandwidth [21][22]; the hearing threshold, used only as a relative weighting [23]: $T(f) = 3.64 f^{-0.8} - 6.5 e^{-0.6(f-3.3)^2} + 10^{-3}f^4$ dB SPL, $f$ in kHz. Tonal tension is the distance of a chord's centre of effect from the key's on the spiral array [24]; groove uses the bar syncopation index [25]; performance rules follow the KTH system [26]; the voice's glottal pulse is the Liljencrants-Fant model [27] driving a Kelly-Lochbaum tube [28].

## Repository structure

```text
SKILL.md · AGENTS.md      agent entry point and rules
scripts/                  pipeline, composition, mixing, gates (spatial_engine/, spatial_hrtf/, vocal_engine/, helpers/)
references/               how the skill works (workflow, mixing, spatial, scoring) and data/presets (JSON)
knowledgebase/            facts about music and sound, each labelled with its source and status
templates/ · video-mixer/ project templates; scoring to picture
docs/                     psychoacoustics, roughness, vocal tract, web player
tests/                    about 1,100 tests, each gate row with a passing and a failing control
```

Immersive reading order: [`references/spatial/immersive-deliverables.md`](references/spatial/immersive-deliverables.md), [`immersive-spatial.md`](references/spatial/immersive-spatial.md), [`quality-gate.md`](references/mixing/quality-gate.md) §5b.

## Limits

* **Metrics are not ears.** A cue rendered for this repository passed every row and was heard as too calm.
* **The GPU path has never run on a GPU**; only the CPU kernel and the fallbacks are tested.
* **One measured head** (FABIAN [19]); a listener's own `.sofa` or `.mat` set can be supplied.
* **The stereo master is a headphone render or a loudspeaker render**, chosen by `immersive.stereo_decode`; one file is not both.
* **The 7.1 layout files carry the wrong system letters.** In BS.2051 the letter H is the 22.2 system; this repository stores its 7.1, 7.1.2 and 7.1.4 rings as `itu_bs2051_system_h`, `_i`, `_j`. Do not claim BS.2051 conformance for the 7.1 family until the files are compared with the standard's table and renamed. The 5.1 family (B, C, D) is not compared either.
* **The default sound bank is General MIDI**; the free SFZ library the skill installs (Sonatina Symphonic Orchestra) is dry and incomplete on case-sensitive file systems.
* **Random sources are redrawn when a piece's length changes**, so a row can pass on one render and fail on the next; fix the track, not the row.
* **Syllables, not words**; cultural idioms are approximations; picture analysis is heuristic.

See [`references/workflow/troubleshooting-and-limits.md`](references/workflow/troubleshooting-and-limits.md).

## References

Bibliographic details come from the comments and documents in this repository and from standard citations; the page numbers were not re-checked against the publishers' pages. Verify a citation before relying on it in a publication.

**Standards.** [1] ITU-R BS.1770-5 (2023). *Algorithms to measure audio programme loudness and true-peak audio level.* [2] EBU Tech 3341 (2020). *Loudness metering: "EBU Mode" metering.* [3] EBU Tech 3342 (2020). *Loudness range.* [4] ITU-R BS.2051-3 (2022). *Advanced sound system for programme production.* [5] ITU-R BS.775-3 (2012). *Multichannel stereophonic sound system with and without accompanying picture.* [6] ITU-R BS.2076-2 (2019) *Audio Definition Model*; BS.2088-1 (2019) *BW64*. [7] ISO 9613-1:1993. *Attenuation of sound during propagation outdoors, part 1.* [16] ISO 3382-1:2009. *Measurement of room acoustic parameters, part 1: performance spaces.*

**Spatial audio.** [8] Zotter, F., & Frank, M. (2012). All-round ambisonic panning and decoding. *J. Audio Eng. Soc.* 60(10), 807-820. [9] Pulkki, V. (1997). Virtual sound source positioning using vector base amplitude panning. *J. Audio Eng. Soc.* 45(6), 456-466. [10] Nachbar, C., Zotter, F., Deleflie, E., & Sontacchi, A. (2011). AmbiX: a suggested ambisonics format. *2nd Int. Symp. on Ambisonics and Spherical Acoustics.* [11] Zotter, F., & Frank, M. (2019). *Ambisonics.* Springer. [12] Schörkhuber, C., Zaunschirm, M., & Höldrich, R. (2018). Binaural rendering of Ambisonic signals via magnitude least squares. *DAGA 2018.* [13] Hold, C., Meyer-Kahlen, N., & Pulkki, V. (2023). Magnitude-least-squares binaural ambisonic rendering with phase continuation. *DAGA 2023.* [14] Allen, J. B., & Berkley, D. A. (1979). Image method for efficiently simulating small-room acoustics. *J. Acoust. Soc. Am.* 65(4), 943-950. [15] Eyring, C. F. (1930). Reverberation time in "dead" rooms. *J. Acoust. Soc. Am.* 1(2A), 217-241. [17] Linkwitz, S. H. (1976). Active crossover networks for noncoincident drivers. *J. Audio Eng. Soc.* 24(1), 2-8. [18] Kendall, G. S. (1995). The decorrelation of audio signals and its impact on spatial imagery. *Computer Music J.* 19(4), 71-87. [19] Brinkmann, F., et al. (2017). A high resolution and full-spherical head-related transfer function database for different head-above-torso orientations. *J. Audio Eng. Soc.* 65(10), 841-848.

**Psychoacoustics, music and voice.** [20] Glasberg, B. R., & Moore, B. C. J. (1990). Derivation of auditory filter shapes from notched-noise data. *Hearing Research* 47, 103-138. [21] Plomp, R., & Levelt, W. J. M. (1965). Tonal consonance and critical bandwidth. *J. Acoust. Soc. Am.* 38, 548-560. [22] Daniel, P., & Weber, R. (1997). Psychoacoustical roughness: implementation of an optimized model. *Acustica* 83, 113-123. [23] Terhardt, E. (1979). Calculating virtual pitch. *Hearing Research* 1, 155-182 (the threshold-in-quiet approximation as commonly quoted). [24] Chew, E. (2000). *Towards a mathematical model of tonality.* PhD thesis, MIT. [25] Witek, M. A. G., et al. (2014). Syncopation, body-movement and pleasure in groove music. *PLoS ONE* 9(4), e94446. [26] Friberg, A., Bresin, R., & Sundberg, J. (2006). Overview of the KTH rule system for musical performance. *Adv. Cogn. Psychol.* 2(2-3), 145-161. [27] Fant, G., Liljencrants, J., & Lin, Q. (1985). A four-parameter model of glottal flow. *STL-QPSR* 26(4), 1-13. [28] Kelly, J. L., & Lochbaum, C. C. (1962). Speech synthesis. *Proc. 4th Int. Congress on Acoustics.*

## Credits & Attributions

* **Spatial audio:** `scripts/spatial_hrtf/` includes a modified copy of [spaudiopy](https://github.com/chris-hld/spaudiopy) by Chris Hold (MIT License).
* **HRTF data:** the **FABIAN HRTF Database** from TU Berlin ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [DOI: 10.14279/depositonce-5718.5](https://doi.org/10.14279/depositonce-5718.5)), fetched via `setup_project.py`.
* **Synthesis:** [tinysoundfont](https://github.com/schellingb/tinysoundfont) by Bernhard Schelling (MIT License) with the [GeneralUser GS SoundFont](https://schristiancollins.com/generaluser.php) by S. Christian Collins.
* **Optional orchestra:** Sonatina Symphonic Orchestra (Mattias Westlund and Peter Eastman, CC Sampling Plus 1.0) via [sfizz](https://github.com/sfztools/sfizz).

## License

[GNU AGPLv3](LICENSE) — Copyright (C) 2026 rasheedh
