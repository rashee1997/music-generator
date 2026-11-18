# music-generator

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Agent Skill](https://img.shields.io/badge/agent%20skill-SKILL.md-black.svg)](SKILL.md)

An AI agent skill and Python audio pipeline that composes, renders, mixes and validates original music from text briefs, scores or video files, and delivers it as stereo, mono, 5.1, 7.1.4, an ambisonic sound field and object audio from one mix.

**Demo:** **Black Jaguar (Cinematic Chase)** — *D minor · 134 BPM*
▶ **[Listen in Browser](https://rashee1997.github.io/music-generator/docs/listen.html#black-jaguar)** · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/black-jaguar-cinematic-chase.mp3)**
▶ **[Arabian Nights: The Desert Crossing (Immersive 2.0)](https://rashee1997.github.io/music-generator/docs/listen.html#arabian-nights)** — with the desert air, mixed on the ambisonic bus · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/arabian-nights-desert.mp3)**
▶ **[The Unwelcome Crossing (haunted desert cue, object audio)](https://rashee1997.github.io/music-generator/docs/listen.html#haunted-desert)** — 7.1.2, 7.1, 48 kHz and ADM objects · **[Download MP3 (320 kbps)](https://rashee1997.github.io/music-generator/assets/samples/haunted-desert-crossing.mp3)**

> **What was and was not checked.** Everything below is verified by tests, probes and gate rows. Nothing in this
> repository has been auditioned by its author's ears except where a listing says so; the pipeline's numbers measure
> faults and levels, not taste. [Honest limits](#honest-limits) lists what the numbers cannot see.

## Contents

1. [What it does](#what-it-does)
2. [Immersive 3.0](#immersive-30)
3. [Installation](#installation)
4. [Quick start](#quick-start)
5. [Pipeline architecture](#pipeline-architecture)
6. [Quality gates](#quality-gates)
7. [Mathematical foundations and citations](#mathematical-foundations-and-citations)
8. [Repository structure](#repository-structure)
9. [Honest limits](#honest-limits)
10. [References](#references)
11. [Credits and licence](#credits--attributions)

---

## What it does

### Why LLM-generated music usually fails

* **Robotic grid or random chaos:** naive code locks MIDI notes to a rigid grid with static velocity; "humanize" then scatters notes at random and unrelated to the music.
* **Low-end mud and voicing clashes:** voices clustered below middle C muddy 100-300 Hz; closed chords produce grating minor seconds.
* **Ear fatigue (cochlear roughness):** overtones colliding inside one critical bandwidth beat harshly.
* **Spectral masking:** pads, guitars and bass swallow the lead in 250-500 Hz when nothing carves a pocket.
* **Aimless harmony:** progressions loop or jump between unrelated keys with no voice leading or cadence.
* **A green report that sounds wrong:** a render can pass every check and still lack the pressure its brief asked for, because each gate fix tends to remove energy. The skill measures the loudness arc against the brief for that reason (`scripts/helpers/arc_report.py`).

### What it provides

| Area | What it does |
|---|---|
| **Writing** | Voice-leading and melodic rules, 3-D spiral-array tonal tension [34], metric-tree syncopation across 4/4, 3/4, 6/8, 5/4, 7/8, 12/8 [39] |
| **Performance** | Humanization that separates shared ensemble drift from individual motor error, couples velocity to note length, adds note-on and note-off noise [40] |
| **Sound** | General MIDI SoundFont by default; optional SFZ orchestras played per articulation with slurred legato and a written dynamics arc; glottal-source voice [41]; physical sound models for footsteps, foliage, fracture, rain; animal calls stored as data |
| **Space** | Per-stem placement, measured-HRTF binaural rendering, shared room acoustics, and the ambisonic bus described in [Immersive 3.0](#immersive-30) |
| **Mix** | Every number in a JSON mix preset: gain staging, sidechain, spectral carve, room send per role, master chain, loudness target |
| **Gates** | About 390 rows judged one 38-track orchestral cue (faults, psychoacoustic limits, spatial rules, delivery formats). A failing row is a fact; the piece or the preset changes, the threshold does not |
| **Film** | Scoring to picture at three timescales; twelve `video.*` rows inside the same gate; a reel assembles only certified cues |

---

## Immersive 3.0

Immersive 2.0 put every source, reflection and tail on one ambisonic bus. **3.0 makes that bus a delivery system**:
one mix, judged once, comes out as every channel count a listener might have, and no format is a degraded copy of
another.

### One mix, six deliverables

| `output_targets` name | Channels | How it is made | Judged by |
|---|---|---|---|
| `stereo` | 2 | decoded from the bus: `immersive.stereo_decode` is `"binaural"` (headphones) or `"speakers"` (a ±30° pair, BS.775 [5]) | the whole gate; certifies the master |
| `mono` | 1 | **rendered**, not folded: every track at the level the mix gave it, with no pan, width or head filter | `fold.mono` |
| `immersive_5_1`, `_5_1_2`, `_5_1_4` | 6 / 8 / 10 | VBAP onto BS.2051-3 [4] layouts B, C, D; a Linkwitz-Riley low-frequency channel [24]; short all-pass decorrelation of the surrounds [25] | `imm.*`, `fold.timbre` |
| `immersive_7_1`, `_7_1_2`, `_7_1_4` | 8 / 10 / 12 | the same, on a 7.1 ring with 0, 2 or 4 overhead loudspeakers (files `itu_bs2051_system_h`, `_i`, `_j`; see the labelling note under [Honest limits](#honest-limits)) | `imm.*`, `fold.timbre` |
| `ambix` | 36 (order 5) | the field itself, ACN order, SN3D [11][12] | `delivery.true_peak` |
| `adm_bw64` | one per object | an Audio Definition Model file in a BW64 container [6] | `adm.container`, `adm.channels`, `adm.loudness` |

`stereo_48k` (or `"rate_hz": 48000` on a project's own target) adds a 48 kHz copy. List `stereo` first: the `fold.*`
rows compare every other format with that master and only warn without it. A format that fails its own rows stays in
`out/_draft_master_<format>.wav`; it is never delivered under its final name. Every certified stereo master is kept as
`out/master_vNN.wav` with its change recorded in `out/versions.json`.

### Signal flow

```text
 tracks ─► per-track decisions (mixer.mix_stems: EQ, dynamics, sends, ducking, distance) ──────────┐
                                                                                                   ▼
        ┌── unplaced ──► MonoBus ───────────────────────────────────────────► mono (rendered)     │
        │                                                                                         │
        │                         ┌─► binaural (MagLS, measured head) ─┐                          │
 HoaBus ◄── placed sources ◄──────┤                                     ├─► stereo ──► master     │
 (order N,                        ├─► speakers (AllRAD)  ───────────────┘     chain, limiter,     │
  (N+1)² channels)                │                                           loudness, fades    │
        ▲                         ├─► LayoutBus: VBAP + LFE + decorrelation ─► 5.1 … 7.1.4        │
 reflections, late tail,          ├─► field as-is, ACN/SN3D ───────────────► AmbiX                │
 Doppler per image source         └─► one object per track ────────────────► ADM BW64            │
```

### What 3.0 changed in the engine

| Change | Where | Why |
|---|---|---|
| Rendered mono (`MonoBus`) | `scripts/spatial_engine/render.py` | a mono file made by adding two channels inherits the stereo master's panning and head filter; a hard-panned part comes out 3 dB down and a head-filtered one is notched |
| BS.1770 loudness for any channel count, one filtering pass | `scripts/loudness.py` | every deliverable is measured by the same standard, with the layout's channel weights, and the low-frequency channel excluded [1] |
| Linked multichannel true-peak limiter | `scripts/spatial_engine/master.py` | one gain curve for all channels, so the image does not move when the limiter works |
| `fold.mono`, `fold.timbre`, `fold.reference`, `imm.loudness` rows | `scripts/spatial_gate.py` | no format may be the dull, thin or loud one |
| Stereo decode for loudspeakers | `immersive.stereo_decode`, `layouts/stereo_bs775.json` | a head-filtered master adds up 3-5 dB low in 450-1500 Hz; see below |
| Master and room parameters as data | `scripts/mix_schema.py` | the master tone curves, glue compressor, room send per role, duck timing and a steeper master high-pass (`mastering.highpass_order`) are preset keys, never constants in `mixer.py` |
| CPU or GPU, chosen once | `scripts/compute.py` | `render.compute.device` or `MUSICGEN_DEVICE`: `auto`, `cpu`, `cuda`, `mps`; FFT convolution and matrix products move to the GPU when one is present, everything else stays on the CPU, and a failure falls back to the CPU with a note |
| Stems and sources placed in parallel | `render.mix_workers`, `HoaBus._place_all` | measured here: 14 sources of 20 s went from 34 s to about 10.6 s with identical samples (−132 dB re peak) |
| Many-channel files measured one channel at a time | `scripts/gate_audio.py`, `master.limit` | a 36-channel true-peak check held 4× the file in float64 (about 14 GB) and was killed for memory |
| Intent drives the mix | `lead_carve.from_intent` | the direction sheet's `mix_intent` carves the beds in the band the lead lives in |

### A finding from running a real piece through all six formats

A 38-track, 97 s orchestral cue (`projects/amazon_deep`, free SFZ library, rain-forest ambience) was taken through
`pipeline.py` to a certified master plus mono, 5.1, 7.1.4, AmbiX and ADM. Three things the unit tests had not shown:

1. **A head-filtered stereo master fails the mono check by design.** With binaural decoding the two ears disagree in
   450-1500 Hz, so adding them lost 4-5 dB there (limit 3.5 dB) and moving parts toward the centre recovered only half a dB.
   Decoding the stereo master for loudspeakers (`stereo_decode: "speakers"`) brought the worst band to +3.1 dB. Headphone
   masters keep `"binaural"`.
2. **A loud 80-120 Hz tone reads as DC drift.** `master.dc` measures 1 s block means; a bass tone that does not complete its
   cycles in each block shows up as drift. The fix is a steeper master high-pass in the mix preset (`highpass_order`), not a
   looser row; the sub is carried by the layouts' low-frequency channel.
3. **A gate can be green and the piece still miss its brief.** The finished cue measured −16 LUFS, a loudest 3 s of
   −11.5 LUFS and quiet stretches over 12 LU under the mean. A listener called it meditative where the brief said
   hostile. `scripts/helpers/arc_report.py` now prints that table; `references/scoring/cinematic-commercial-grade.md`
   is the procedure it feeds.

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

> `setup_project.py` uses [uv](https://docs.astral.sh/uv/) if available and falls back to `python -m venv` + `pip`.
> **ffmpeg** is required only for the video path. **PyTorch** is optional: without it everything runs on the CPU.

---

## Quick start

### With an AI agent

> *"Compose a 60-second underscore for a slow reveal of a mountain range — cold, patient, no drums."*

The agent reads `SKILL.md` and `AGENTS.md`, researches the style, writes a direction sheet and presets, writes the score and iterates through the pipeline until the gate has no FAIL.

### From the command line

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 1. Scaffold a project
python scripts/setup_project.py --new-project my-project --title "My Track"

# 2. Render, gate and certify (add the formats to the score's "output_targets")
python scripts/pipeline.py my-project/scores/my_track_score.json --project my-project

# 3. Audit an existing WAV without rendering
python scripts/pipeline.py path/to/master.wav --check-only

# 4. Measure the loudness arc against the brief
python scripts/helpers/arc_report.py my-project/out/master.wav --score my-project/scores/my_track_score.json

# 5. Version history, MP3 export
python scripts/helpers/version_manager.py list --project my-project
python scripts/helpers/compress_mp3.py my-project/out/master_v01.wav -o my-track.mp3 -b 320k

# 6. Scoring to picture
python scripts/setup_project.py --new-film films/glaciers --title "Glaciers" --fps 25
python scripts/video_score.py --video clips/reel1.mp4 --project films/glaciers/cues/M01_open --brief "calm documentary"
python video-mixer/deliver/reel.py films/glaciers --reel 1 --mux
```

Useful switches for a long render: `MUSICGEN_DEVICE=cpu|cuda|mps|auto`, `MUSICGEN_SFZ_WORKERS=2` (fewer parallel sample
renderers, less memory), `MUSICGEN_FFT_WORKERS`. Deliverables are named in the score, never produced by a script:

```json
"output_targets": ["stereo", "mono", "immersive_5_1", "immersive_7_1_4", "ambix", "adm_bw64"]
```

---

## Pipeline architecture

```text
[Brief / prompt / score]
   │
   ├─ 1. Composition & voice leading     compose.py · theory.py · world.py
   ├─ 2. Pre-flight theory linter        pattern_audit.py
   ├─ 3. Humanization & respiration      humanize.py
   ├─ 4. Multi-engine stem rendering     tinysoundfont · sfz_render · vocal_engine · environment · sfx_engine
   │      └─ 4b. Stem gate               stem_gate.py   (dead, edge, dropout, tick, dc, cut, clicks)
   ├─ 5. Mixing & mastering              mixer.py → HoaBus / LayoutBus / MonoBus → master chain and limiter
   │      └─ 5b. Additional deliverables spatial_gate.py (fold, layout, object rows), after the master is certified
   ├─ 6. Psychoacoustic quality gates    quality_gate.py · naturalness_check.py · music21
   └─ 7. Certified release               out/master_vNN.wav · master_<format>.wav · ci_report.json · versions.json
```

Scoring to picture adds one path that feeds the same gate, not a second verdict:

```text
[Film reel / cue] ─ probe (ffprobe, scdet) ─ context (reel / scene / motion beat) ─ direction ─ music (Phases 1-8 unchanged)
                  ─ program mix (voice chain, duck, gating mode) ─ video.* rows inside stage 6 ─ reel (certified cues only)
```

### The agent workflow

| Step | Action | Output |
|:--|:--|:--|
| 1 | Scaffold the project | `direction/`, `presets/`, `scores/`, `out/`, `reports/`, `STATUS.md` |
| 2 | Research the idiom | `reports/research_<topic>.md` with citations |
| 3 | Write the direction sheet | `direction/direction_<title>.json` (what the piece is, what carries it, where it peaks) |
| 4 | Configure presets | instrument, vocal, space, calls and mix JSON |
| 5 | Write the score | `scores/<title>_score.json` (tracks and notes only) |
| 6 | Render and gate | `out/master_vNN.wav`, deliverables, `reports/ci_report.json` |
| 7 | Iterate | one change per run, until 0 FAIL |
| 8 | Verify and deliver | `arc_report.py`, `listen.py`, the self-check in `STATUS.md` |

Rules the agent cannot bend are in [`AGENTS.md`](AGENTS.md): sound design lives in presets, notes in scores, intent
in direction sheets; acoustic values are cited or measured; a failing row is fixed in the piece, never loosened.

---

## Quality gates

`python scripts/gate_profiles.py list` shows the profiles; the full row table is
[`references/mixing/quality-gate.md`](references/mixing/quality-gate.md).

| Family | Rows (examples) | What they catch |
|---|---|---|
| Stem | `stem.dead`, `stem.edge`, `stem.dropout`, `stem.tick`, `stem.dc`, `stem.clicks` | a part that is missing, late, clipped or ticking before it is mixed |
| Master | `loudness`, `true_peak`, `clipping`, `clicks`, `dropout`, `master.dc`, `silence` | a faulty file |
| Musical | `cochlear_roughness`, `harmonic_resolution_feel`, `pattern.flags_max`, `spatial.z_separation` | clashing partials, loops, parts sharing one place |
| Declaration | `focus.declared`, `intent.vocabulary`, `intent.avoid` | a piece that is not what its sheet said |
| Immersive | `imm_kinematics`, `imm_iacc_early`, `imm_clarity`, `imm_low_fold`, `imm_height_rules`, `imm.height_arc` | motion, room and height that do not hold up |
| Delivery | `delivery.format`, `delivery.true_peak`, `render.finite`, `imm.loudness`, `imm.lfe_stopband`, `imm.surround_ratio`, `imm.fold_coherence` | a file that is not the format it claims |
| Fold | `fold.mono`, `fold.timbre`, `fold.reference`, `mix.band_fold` | a format that sounds like a different mix |
| Object | `adm.container`, `adm.parse`, `adm.channels`, `adm.loudness` | a BW64/ADM file a renderer cannot read |
| Picture | `video.duration_lock`, `video.cut_sync`, `video.dialogue_snr`, `video.master_compliance`, ... | a cue that misses its picture |

`loudness`, `true_peak`, `clipping`, `silence`, `clicks`, `channels` are protected: no profile may relax them. A
profile or a score may relax another row only with a measurement and a written reason.

---

## Mathematical foundations and citations

Each block names the file that implements it and the sources it comes from. Numbers in brackets are in
[References](#references). Derivations with worked values are in [`docs/PSYCHOACOUSTICS.md`](docs/PSYCHOACOUSTICS.md).

### 1. Loudness, range and true peak: `scripts/loudness.py`, `scripts/spatial_engine/master.py`

Audio is K-weighted (a high-shelf stage then a high-pass stage) [1]. For 400 ms blocks overlapping by 75 %, the block
energy over channels $c$ with channel weights $G_c$ (1.0 front, +1.5 dB surround, low-frequency channel excluded) is

$$
z_j = \sum_c G_c \, \frac{1}{N} \sum_{k \in \text{block } j} x_{c,k}^{2}, \qquad
L_j = -0.691 + 10 \log_{10} z_j \ \ [\text{LKFS}]
$$

Integrated loudness averages the blocks that pass two gates, an absolute one at −70 LKFS and a relative one 10 LU below
the mean of the blocks that passed the first [1]:

$$
L_I = -0.691 + 10 \log_{10} \overline{z}_{\Gamma}
$$

Short-term loudness is the same measure over a sliding 3 s window [2]. Loudness range is the spread between the 10th and
95th percentile of the short-term values that sit above a gate 20 LU under their power mean [3]. True peak is the
maximum of the signal oversampled 4× [1]. `scripts/helpers/arc_report.py` prints these per section.

The master limiter is linked across channels, so the image does not move. With oversampled per-sample peak $p_n$
(maximum over channels), ceiling $c$, release time constant $\tau$ and $k = e^{-1/(\tau f_s)}$:

$$
a_n = -\ln\min\!\left(1, \frac{c}{p_n}\right), \qquad
\tilde a_n = \max_{j \le n} a_j \, k^{\,n-j}, \qquad g_n = e^{-\tilde a_n}
$$

The running maximum is evaluated in the log domain, a sliding minimum plus a moving average of the look-ahead length
gives the curve its lead time and removes its corners, and the same $g_n$ multiplies every channel. This limiter is the
engine's own construction; the ceiling it enforces and the oversampling it measures with are [1].

### 2. Rendered mono and the fold rows: `scripts/spatial_engine/render.py`, `scripts/spatial_gate.py`

Two channels with nothing in common average $10\log_{10}2 \approx 3.01$ dB below either. A stereo part that is mixed to
mono as $m = \tfrac12 (L + R)$ is given back the level it lost, never more than the target's `compensate_max_db`:

$$
g = \operatorname{clip}\!\left(10 \log_{10} \frac{\tfrac12\,\overline{L^2 + R^2}}{\overline{m^2}},\; 0,\; g_{\max}\right)\ \text{dB}
$$

so a part whose channels cancel is not rescued by boosting. The fold rows compare long-term spectra in bands one ERB
wide, with the auditory rate [27][28]

$$
\mathrm{ERB\text{-}rate}(f) = 21.4 \log_{10}(0.00437\, f + 1)
$$

For a reference (the stereo master) and a candidate (the mono render, or a layout folded by its BS.775 coefficients [5])
with band powers $P^{ref}_b$ and $P^{cand}_b$, after matching their overall levels over the bands $K$ that lie within
`fold_floor_db` of the loudest:

$$
\delta_b = 10 \log_{10}\frac{P^{cand}_b}{P^{ref}_b} \;-\; 10 \log_{10}\frac{\sum_{b \in K} P^{cand}_b}{\sum_{b \in K} P^{ref}_b},
\qquad \text{PASS} \iff \max_{b \in K} |\delta_b| \le \delta_{\max}
$$

The two-channel fold of a layout is $L' = \sum_c g^{L}_c x_c$, $R' = \sum_c g^{R}_c x_c$ with the coefficients stored in
the layout preset (the low-frequency channel has none) [5].

### 3. Ambisonic bus, encoding and decoders: `scripts/spatial_engine/hoa.py`, `scripts/spatial_hrtf/`

A source $s(t)$ at direction $(\theta, \phi)$ is written into the field with real spherical harmonics
$Y_n^m$ [11][15]:

$$
b_{nm}(t) = s(t)\, Y_n^m\big(\theta(t), \phi(t)\big), \qquad 0 \le n \le N,\ |m| \le n
$$

The field has $(N+1)^2$ channels (25 at order 4, 36 at order 5), ordered by ACN index $n^2 + n + m$. A moving source only
changes the gains, so no filter is switched. AmbiX export rescales each order by $\sqrt{4\pi/(2n+1)}$ to SN3D [12].

**Headphones (MagLS).** The decoding filters fit the measured head filters in the least-squares sense below a
transition frequency and by magnitude only above it, with the phase continued from the bin below [13][14]. The ear
signal is $\sum_{nm} b_{nm} * h_{nm}^{L,R}$.

**Loudspeakers (AllRAD).** $J$ virtual loudspeakers on a near-uniform sphere sample the field and each is panned onto
the real layout by VBAP [9][10]:

$$
D = \frac{4\pi}{J}\, G^{\mathsf T}\, Y\, \mathrm{diag}(w_n)
$$

$G$ holds the VBAP gains of the virtual loudspeakers, $Y$ their harmonics, and $w_n$ are max-$r_E$ order weights, the
Legendre polynomials $P_n(\cos\vartheta_E)$ with $\vartheta_E = 137.9^\circ / (N + 1.51)$ [10][11]. $D$ is scaled so a plane
wave keeps unit power on average.

**VBAP.** A direction with unit vector $\mathbf p$ inside the loudspeaker triplet with vector matrix $L$ is panned with

$$
\mathbf g = L^{-1}\mathbf p, \qquad \mathbf g \leftarrow \mathbf g / \lVert \mathbf g \rVert_2
$$

so $\sum_i g_i^2 = 1$ and loudness does not change as the source moves [9]. Of the triplets that hold a direction with
non-negative gains, the one with the smallest gain sum is the face the direction passes through. Layouts whose speakers all
sit at ear height are panned pairwise with equal power.

### 4. Propagation: `scripts/airabs.py`, `scripts/spatial_hrtf/binaural.py`, `scripts/spatial_hrtf/room.py`

**Spreading and air.** Level falls as $1/r$ (pressure). Air absorbs high frequencies by the ISO 9613-1 pure-tone
coefficient [7]

$$
\alpha(f) = 8.686\, f^2 \left[ 1.84\times10^{-11} \tfrac{p_r}{p}\sqrt{\tfrac{T}{T_0}} + \left(\tfrac{T}{T_0}\right)^{-5/2}
\left( \tfrac{0.01275\, e^{-2239.1/T}}{f_{rO} + f^2/f_{rO}} + \tfrac{0.1068\, e^{-3352/T}}{f_{rN} + f^2/f_{rN}} \right) \right]\ \text{dB/m}
$$

applied as a linear-phase filter $10^{-\alpha(f)\,d/20}$; $f_{rO}$, $f_{rN}$ are the oxygen and nitrogen relaxation
frequencies. Check values at 20 °C, 50 % relative humidity: 4.7 dB/km at 1 kHz, 159 dB/km at 10 kHz.

**Doppler.** The direct sound is read at $t - \lambda\,(d(t) - d_{\min})/c$ with $c = 343$ m/s and $\lambda$ the preset's
`doppler_strength`; each image-source reflection is read later by its own extra path $(r_i(t) - r_0(t))/c$, so every
reflection has its own Doppler shift.

**Early reflections.** In a box, wall reflections are mirror images of the source [21]; an image at path length $r_i$ arrives
$(r_i - r_0)/c$ after the direct sound from its own direction at amplitude

$$
g_i(f) = \frac{1}{r_i} \prod_{\text{bounces}} \sqrt{1 - a_k(f)}
$$

with $a_k$ the energy absorption of each surface hit.

**Late field.** Reverberation time follows Eyring with an air term, and the late tail starts at the mixing time [22][23]

$$
T_{60}(f) = \frac{24 \ln 10}{c}\cdot\frac{V}{-S\ln(1-\bar a(f)) + 4\,m(f)\,V}, \qquad t_{mix} \approx 20\,\frac{V}{S} + 12\ \text{ms}
$$

($V$ volume, $S$ surface, $\bar a$ the area-weighted mean absorption, $m = \alpha/4.343$ the air's power attenuation per metre).
Sabine's formula $T_{60} = 0.161\,V/A$ is the low-absorption limit [22].

**Head and near field.** The interaural delay of a source combines the low-frequency spherical-head result of Kuhn
and the high-frequency ray limit [19][20]; the head shadow is a one-pole one-zero filter [18]; below one metre each ear is a
different distance from the source and the far-field head filter is multiplied by the ratio of two rigid-sphere responses
(the distance variation function) [16][17]

$$
H(\rho,\mu,\theta) = -\frac{\rho}{\mu}\, e^{-i\mu\rho} \sum_{m=0}^{\infty} (2m+1)\, P_m(\cos\theta)\,\frac{h_m(\mu\rho)}{h_m'(\mu)},
\qquad \mathrm{DVF} = \frac{|H(\rho_{near})|}{|H(\rho_{ref})|}
$$

($\mu = ka$ the normalised frequency, $\rho = r/a$ the distance in head radii, $h_m$ spherical Hankel functions).

**Room measures on the impulse response** (ISO 3382-1 [8]), with $h_L, h_R$ the two ear responses filtered to one octave:

$$
\mathrm{IACC}_E = \max_{|\tau|\le 1\,\mathrm{ms}} \frac{\left|\int_0^{80\,\mathrm{ms}} h_L(t)\,h_R(t+\tau)\,dt\right|}
{\sqrt{\int_0^{80\,\mathrm{ms}} h_L^2\,dt\int_0^{80\,\mathrm{ms}} h_R^2\,dt}}, \qquad
C_{80} = 10\log_{10}\frac{\int_0^{80\,\mathrm{ms}} h^2\,dt}{\int_{80\,\mathrm{ms}}^{\infty} h^2\,dt}\ \text{dB}
$$

### 5. Layouts, crossover, decorrelation, objects: `scripts/spatial_engine/{bass,decorrelate,adm}.py`

Loudspeaker positions come from ITU-R BS.2051-3 [4]. The low-frequency channel and the bass management use a
Linkwitz-Riley 4th-order crossover, two cascaded 2nd-order Butterworth sections whose low-pass and high-pass outputs are in
phase at the crossover [24]. Surround and height channels carrying the same signal collapse to a point and comb-filter, so
each is passed through a first-order all-pass with its own coefficient $a$ (magnitude flat, phase only) [25]:

$$
y[n] = -a\,x[n] + x[n-1] + a\,y[n-1]
$$

Object audio is an Audio Definition Model description (BS.2076-2) in a BW64 container (BS.2088-1) [6]; the file is read
back and every track, channel mapping and block time is checked by `adm.parse`.

### 6. Compute: `scripts/compute.py`

Reverb returns, air absorption and head filters are FFT convolutions, $y = \mathcal{F}^{-1}\{\mathcal{F}\{x\}\cdot\mathcal{F}\{h\}\}$
on zero-padded signals of length $\ge N + M - 1$ [47][48]. The CPU path calls SciPy exactly as the engine always did; the GPU
path computes the same arithmetic in float32 and the tests bound the difference between the two.

### 7. Psychoacoustic gates: `scripts/quality_gate.py`, `scripts/naturalness_check.py`

* **Critical bands.** Band edges one ERB apart [27][28]; Bark-rate bands for the roughness model [29].
* **Roughness.** Pairs of partials inside a critical bandwidth beat; the dissonance of a pair peaks at about a quarter of the
  critical bandwidth and falls away on either side [30][31]. The cochlear roughness row follows the Daniel and Weber
  structure, with masking slopes from their worked example (listed as a limit in [`docs/roughness_model.md`](docs/roughness_model.md)) [32].
* **Absolute threshold of hearing**, used as a relative weighting and not as a calibration of level [33]:
  $T(f) = 3.64\,f^{-0.8} - 6.5\,e^{-0.6\,(f-3.3)^2} + 10^{-3} f^{4}$ dB SPL, $f$ in kHz.
* **Tonal tension.** Chew's spiral array places pitch classes on a helix; tension is the distance of the chord's centre of
  effect from the key's [34][35]. Voice-leading limits follow [36].
* **Information content and surprise** of a melody: Shannon entropy $H = -\sum_i p_i \log_2 p_i$ [37], with the
  variable-order context model of [38].
* **Groove.** The bar syncopation index follows the metrical-weight scheme tested against listeners' groove and pleasure
  ratings in [39].

### 8. Voice and sources: `scripts/vocal_engine/`, `scripts/environment.py`, `docs/VOCAL-TRACT-WAVEGUIDE.md`

The glottal pulse is the four-parameter Liljencrants-Fant model, with one control from pressed to breathy [41][42]; the
tract is a Kelly-Lochbaum tube network [43]; vibrato is an Ornstein-Uhlenbeck process, so it wanders and returns [44]. An
animal call is a source and a filter [45][46].

### 9. Performance model: `scripts/humanize.py`

Timing and velocity deviations are separated into shared drift and individual motor error and coupled to phrase
position and note length; the expressive rules follow the KTH performance rule system [40].

---

## Repository structure

```text
music-generator/
├── SKILL.md              # agent skill entry point
├── AGENTS.md             # rules, workflow phases, read table, gate profiles
├── scripts/              # pipeline, composition, mixing, gates (about 70 modules)
│   ├── spatial_engine/   # HoaBus, LayoutBus, MonoBus, VBAP, crossover, decorrelation, ADM, master limiter
│   ├── spatial_hrtf/     # measured-HRTF binaural, MagLS decoder, image-source room (vendored spaudiopy)
│   ├── vocal_engine/ · sfx_engine/ · env_engine/ · phys_core/
│   ├── loudness.py       # BS.1770 / EBU 3341 / 3342 for any channel count
│   ├── compute.py        # CPU or GPU selection and FFT kernels
│   └── helpers/          # version record, metadata, MP3, arc_report
├── references/           # how the skill works: workflow, mixing, spatial, scoring, plus data/presets
│   └── data/presets/     # instrument, mix, space, layout, output, calls and film presets (JSON)
├── knowledgebase/        # facts about music and sound, each labelled with its source and status
├── templates/            # project, direction-sheet and score templates
├── video-mixer/          # scoring to picture: probe, context, direction, program mix, video gate, reel
├── docs/                 # psychoacoustics, roughness, vocal tract, the Immersive 3.0 audit and plan, web player
├── projects/             # example projects (libraries, stems and renders are not committed)
├── assets/samples/       # demo MP3s
└── tests/                # about 1,100 tests in 68 files, including a positive and a negative control per gate row
```

Immersive 3.0 reading order: [`references/spatial/immersive-deliverables.md`](references/spatial/immersive-deliverables.md),
[`references/spatial/immersive-spatial.md`](references/spatial/immersive-spatial.md),
[`references/mixing/quality-gate.md`](references/mixing/quality-gate.md) (section 5b),
[`docs/ENGINE-AUDIT-AND-IMMERSIVE-3-PLAN.md`](docs/ENGINE-AUDIT-AND-IMMERSIVE-3-PLAN.md).

---

## Honest limits

* **Metrics are not ears.** The gate catches faults and psychoacoustic limits; it cannot judge taste, realism or whether a
  cue has the pressure its brief wanted. A cue rendered for this repository passed every row and was heard as too calm.
* **The GPU path has not run on a GPU.** `compute.py` is tested on the CPU kernel and its fallbacks; PyTorch was never
  available where it was developed. CPU renders do not depend on it.
* **The 7.1 layout files carry the wrong system letters.** In ITU-R BS.2051 the letter H is the 22.2 system (9+10+3); this repository stores its 7.1, 7.1.2 and 7.1.4 rings as `itu_bs2051_system_h`, `_i` and `_j`. The speaker positions are the engine's own 7.1 ring plus overheads, not a checked copy of those BS.2051 systems, so do not claim conformance for the 7.1 family until the files are compared with the standard's table and renamed. The 5.1 family (B, C, D) has not been compared against the table either.
* **Head data is one measured head** (FABIAN [26]); individual HRTFs can be supplied as `.sofa` or `.mat`.
* **The stereo master is either a headphone render or a loudspeaker render.** `immersive.stereo_decode` chooses; one file
  is not both. The loudspeaker pair also drops the sub below the master high-pass, which the 5.1 and 7.1 low-frequency channel carries.
* **The default sound bank is General MIDI.** Concert-grade orchestral realism needs a multisampled SFZ library; the free
  library the skill installs (Sonatina Symphonic Orchestra, CC Sampling Plus 1.0) is dry, mid-2000s and incomplete on
  case-sensitive file systems (120 of 535 patches reference missing samples).
* **Random sound sources are not reproducible across a change of piece length.** Bouts of calls, bed fluctuations and
  onsets are drawn per render, so a row can pass on one render and fail on the next; the fix is at the track, not the row.
* **Syllables, not words.** The voice engine sings vowels, hums and simple syllables.
* **Cultural idioms are approximations** unless paired with authentic presets or recordings.
* **Picture analysis is heuristic.** Cuts come from `scdet` (fades and dissolves are missed), shot scale is block contrast,
  speech activity is presence, and several thresholds are starting values.
* **Still open from the 3.0 plan:** a sample-rate setting (44.1 kHz is a constant in many places), a scene cache shared by
  all targets, a 9.1.6 layout, IAMF, binaural equalisation, a feedback-delay-network late field, field rotation,
  and the vocal, SFX and ambience engine rewrites. See section 11 of the plan.

See [`references/workflow/troubleshooting-and-limits.md`](references/workflow/troubleshooting-and-limits.md) and
[`docs/PSYCHOACOUSTICS.md`](docs/PSYCHOACOUSTICS.md) for more.

---

## References

Numbers match the citations in the text. Standards first, then spatial audio, psychoacoustics and music, voice, signal processing.

**Standards**

1. ITU-R BS.1770-5 (2023). *Algorithms to measure audio programme loudness and true-peak audio level.* International Telecommunication Union.
2. EBU Tech 3341 (2020). *Loudness metering: "EBU Mode" metering to supplement EBU R 128 loudness normalisation.* European Broadcasting Union.
3. EBU Tech 3342 (2020). *Loudness range: a measure to supplement EBU R 128 loudness normalisation.* European Broadcasting Union.
4. ITU-R BS.2051-3 (2022). *Advanced sound system for programme production.*
5. ITU-R BS.775-3 (2012). *Multichannel stereophonic sound system with and without accompanying picture.*
6. ITU-R BS.2076-2 (2019). *Audio Definition Model.* ITU-R BS.2088-1 (2019). *Long-form file format for the international exchange of audio programme materials with metadata (BW64).* ITU-R BS.2127-1 (2023). *Audio Definition Model renderer.*
7. ISO 9613-1:1993. *Acoustics: attenuation of sound during propagation outdoors, part 1: calculation of the absorption of sound by the atmosphere.*
8. ISO 3382-1:2009. *Acoustics: measurement of room acoustic parameters, part 1: performance spaces.*

**Spatial audio**

9. Pulkki, V. (1997). Virtual sound source positioning using vector base amplitude panning. *J. Audio Eng. Soc.* 45(6), 456-466.
10. Zotter, F., & Frank, M. (2012). All-round ambisonic panning and decoding. *J. Audio Eng. Soc.* 60(10), 807-820.
11. Zotter, F., & Frank, M. (2019). *Ambisonics: A Practical 3D Audio Theory for Recording, Studio Production, Sound Reinforcement, and Virtual Reality.* Springer Topics in Signal Processing.
12. Nachbar, C., Zotter, F., Deleflie, E., & Sontacchi, A. (2011). AmbiX: a suggested ambisonics format. *2nd International Symposium on Ambisonics and Spherical Acoustics*, Lexington.
13. Schörkhuber, C., Zaunschirm, M., & Höldrich, R. (2018). Binaural rendering of Ambisonic signals via magnitude least squares. *DAGA 2018*, Munich.
14. Hold, C., Meyer-Kahlen, N., & Pulkki, V. (2023). Magnitude-least-squares binaural ambisonic rendering with phase continuation. *DAGA 2023*, Hamburg.
15. Rafaely, B. (2015). *Fundamentals of Spherical Array Processing.* Springer.
16. Duda, R. O., & Martens, W. L. (1998). Range dependence of the response of a spherical head model. *J. Acoust. Soc. Am.* 104(5), 3048-3058.
17. Kan, A., Jin, C., & van Schaik, A. (2009). A psychophysical evaluation of near-field head-related transfer functions synthesized using a distance variation function. *J. Acoust. Soc. Am.* 125(4), 2233-2242.
18. Brown, C. P., & Duda, R. O. (1998). A structural model for binaural sound synthesis. *IEEE Trans. Speech Audio Process.* 6(5), 476-488.
19. Kuhn, G. F. (1977). Model for the interaural time differences in the azimuthal plane. *J. Acoust. Soc. Am.* 62(1), 157-167.
20. Woodworth, R. S., & Schlosberg, H. (1954). *Experimental Psychology.* Holt, Rinehart and Winston.
21. Allen, J. B., & Berkley, D. A. (1979). Image method for efficiently simulating small-room acoustics. *J. Acoust. Soc. Am.* 65(4), 943-950.
22. Eyring, C. F. (1930). Reverberation time in "dead" rooms. *J. Acoust. Soc. Am.* 1(2A), 217-241. Sabine, W. C. (1922). *Collected Papers on Acoustics.* Harvard University Press.
23. Lindau, A., Kosanke, L., & Weinzierl, S. (2012). Perceptual evaluation of model- and signal-based predictors of the mixing time in binaural room impulse responses. *J. Audio Eng. Soc.* 60(11), 887-898.
24. Linkwitz, S. H. (1976). Active crossover networks for noncoincident drivers. *J. Audio Eng. Soc.* 24(1), 2-8.
25. Kendall, G. S. (1995). The decorrelation of audio signals and its impact on spatial imagery. *Computer Music J.* 19(4), 71-87.
26. Brinkmann, F., et al. (2017). A high resolution and full-spherical head-related transfer function database for different head-above-torso orientations. *J. Audio Eng. Soc.* 65(10), 841-848. Data: DOI 10.14279/depositonce-5718.5.

**Psychoacoustics and music**

27. Glasberg, B. R., & Moore, B. C. J. (1990). Derivation of auditory filter shapes from notched-noise data. *Hearing Research* 47, 103-138.
28. Moore, B. C. J., & Glasberg, B. R. (1983). Suggested formulae for calculating auditory-filter bandwidths and excitation patterns. *J. Acoust. Soc. Am.* 74, 750-753.
29. Zwicker, E., & Fastl, H. (2007). *Psychoacoustics: Facts and Models* (3rd ed.). Springer.
30. Plomp, R., & Levelt, W. J. M. (1965). Tonal consonance and critical bandwidth. *J. Acoust. Soc. Am.* 38, 548-560.
31. Sethares, W. A. (1993). Local consonance and the relationship between timbre and scale. *J. Acoust. Soc. Am.* 94, 1218-1228.
32. Daniel, P., & Weber, R. (1997). Psychoacoustical roughness: implementation of an optimized model. *Acustica* 83, 113-123.
33. Terhardt, E. (1979). Calculating virtual pitch. *Hearing Research* 1, 155-182. (The threshold-in-quiet approximation as commonly quoted from this work.)
34. Chew, E. (2000). *Towards a mathematical model of tonality.* PhD thesis, Massachusetts Institute of Technology.
35. Herremans, D., & Chew, E. (2016). Tension ribbons: quantifying and visualising tonal tension. *Proc. TENOR 2016*.
36. Huron, D. (2001). Tone and voice: a derivation of the rules of voice-leading from perceptual principles. *Music Perception* 19(1), 1-64.
37. Shannon, C. E. (1948). A mathematical theory of communication. *Bell System Technical J.* 27, 379-423, 623-656.
38. Pearce, M. T., & Wiggins, G. A. (2006). Expectation in melody: the influence of context and learning. *Music Perception* 23, 377-405.
39. Witek, M. A. G., Clarke, E. F., Wallentin, M., Kringelbach, M. L., & Vuust, P. (2014). Syncopation, body-movement and pleasure in groove music. *PLoS ONE* 9(4), e94446.
40. Friberg, A., Bresin, R., & Sundberg, J. (2006). Overview of the KTH rule system for musical performance. *Advances in Cognitive Psychology* 2(2-3), 145-161.

**Voice and sources**

41. Fant, G., Liljencrants, J., & Lin, Q. (1985). A four-parameter model of glottal flow. *STL-QPSR* 26(4), 1-13.
42. Fant, G. (1995). The LF-model revisited. Transformations and frequency domain analysis. *STL-QPSR* 36(2-3), 119-156.
43. Kelly, J. L., & Lochbaum, C. C. (1962). Speech synthesis. *Proc. 4th International Congress on Acoustics*, Copenhagen.
44. Uhlenbeck, G. E., & Ornstein, L. S. (1930). On the theory of the Brownian motion. *Physical Review* 36, 823-841.
45. Fant, G. (1960). *Acoustic Theory of Speech Production.* Mouton.
46. Taylor, A. M., & Reby, D. (2010). The contribution of source-filter theory to mammal vocal communication research. *J. Zoology* 280, 221-236.

**Signal processing**

47. Cooley, J. W., & Tukey, J. W. (1965). An algorithm for the machine calculation of complex Fourier series. *Mathematics of Computation* 19, 297-301.
48. Oppenheim, A. V., & Schafer, R. W. (2010). *Discrete-Time Signal Processing* (3rd ed.). Pearson.

> The bibliographic details come from the comments and documents already in this repository and from standard
> citations. The session that wrote this section could not open the publishers' pages, so page numbers, editions and
> years were not re-checked against them. Verify a citation before relying on it in a publication.

---

## Credits & Attributions

* **Spatial audio:** `scripts/spatial_hrtf/` includes a modified copy of [spaudiopy](https://github.com/chris-hld/spaudiopy) by Chris Hold (MIT License).
* **HRTF data:** the **FABIAN HRTF Database** from TU Berlin ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [DOI: 10.14279/depositonce-5718.5](https://doi.org/10.14279/depositonce-5718.5)), fetched via `setup_project.py`.
* **Synthesis:** [tinysoundfont](https://github.com/schellingb/tinysoundfont) by Bernhard Schelling (MIT License) using the [GeneralUser GS SoundFont](https://schristiancollins.com/generaluser.php) by S. Christian Collins.
* **Optional orchestra:** the Sonatina Symphonic Orchestra (Mattias Westlund and Peter Eastman, CC Sampling Plus 1.0) played through [sfizz](https://github.com/sfztools/sfizz).

## License

[GNU AGPLv3](LICENSE) — Copyright (C) 2026 rasheedh
