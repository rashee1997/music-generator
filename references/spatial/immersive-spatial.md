---
title: Immersive and height
summary: Height, elevation and the immersive rows: what may be lifted, what must stay on the floor, and why.
tags: [immersive, height, elevation, atmos, surround, binaural, 3d]
load_when:
  - the brief asks for immersive or height
  - an imm gate row fails
---

# Immersive spatial audio: headphone and speaker renders

"Immersive" covers two distinct output paths: stereo headphone spatialization through `mixer.py`, `spatial_hrtf` and the `spaces`/`mix` presets; and discrete channel-based speaker renders through `spatial_engine`. The speaker renderer supports 7.1 (System H), 7.1.2 (System I) and 7.1.4 (System J) WAV deliverables. These are fixed channel layouts, not object-based Dolby Atmos, ADM or a binaural headphone master. Each path is selected as an output target; headphone height processing remains off unless enabled in the project's mix preset.

## 1. Switch and rules (mix preset, kind `mix`)

```json
"immersive": {
  "enabled": true,
  "height_by_role": {"melody": 6, "pad": 15, "environment": 40, "chord": 0, "bass": 0, "drum": 0},
  "max_elevation": 60,
  "min_height_tracks": 1,
  "pair": {"width_deg_bed": 40, "width_deg_stereo": 12},
  "hrtf": {"dataset": ""},
  "gate": {"max_late_iacc": 0.4}
}
```
`hrtf.dataset` is `""` for the bundled FABIAN set, or a listener's own set: put `<name>.sofa` or `<name>.mat` in
`<project>/presets/hrtf/` and write it here. A listener's own set is the largest single step towards an externalised
image, because the cues that do it are individual.
`presets.py scaffold mix <name> --project <dir>` writes this block with `enabled: false`.

**Height rules** (all in presets, never in code by track name):
1. Elevation comes from the track's `spatial`, else its instrument/vocal preset `spatial`, else `height_by_role[role]`.
2. Bass and drums stay at 0 deg (the mixer forces it): height is carried by high-frequency pinna cues, which low sounds do not have.
3. Nothing above `max_elevation` (default 60): near-vertical positions are the least reliable with a dummy head.
4. At least `min_height_tracks` tracks are lifted, otherwise the piece is flat in name only.
5. Elevation in the instrument preset must agree with the direction sheet's `spatial_staging` (within 10 deg) when the sheet gives one.
6. A lifted stem needs energy above 4 kHz to sound high (WARN `imm_band` when it has almost none).
7. The piece's `space` preset needs ground, ceiling, lateral and rear reflections (the gate needs at least 3).

## 2. What the mixer does when `enabled` is true

| Without immersive | With immersive |
|---|---|
| `elevation` and `space` ignored unless the track opted in with `binaural` | every track with a `spatial` block uses the measured-head route (`binaural: "hrtf"`); `binaural: false` is the only opt-out |
| stereo stems folded to mono | stereo stems become two sources at azimuth -/+ half-width (the mix preset's `immersive.pair` sets `width_deg_bed` and `width_deg_stereo`; `spatial.half_width_deg` overrides per track) |
| `kind: "bed"` never binaural | beds are binaural pairs |
| head-data route had no room | early reflections from the space preset, each from its own direction: floor below (-25 deg), ceiling above (+60 deg), far wall (+-90 deg), rear wall |
| `spatial.py` reflections identical in both ears | `spatial.py` now places floor, ceiling and rear reflections with head shadow, ITD and pinna colour (also the fallback when the head data is missing) |
| reflection taps kept full level while the direct sound fell (DRR inverted: +4 dB measured at 6 m) | each tap obeys its own path, 1/r about `reflections.ref_m` plus the air the longer path crosses; the space preset's `reflections.path_physics` (default true) switches it off for an older project |

Distance, air loss and the shared reverb are unchanged.

## 2b. The four physical layers (all space-preset keys)

| Key (space preset) | What it does |
|---|---|
| `distance.near_field` | below `max_m` (1 m) the ears are different distances from a point source, so the near ear gains level and low end. `strength` 0-1 blends the geometric difference, `lf_boost`/`lf_hz` set the bass emphasis. Before this, 0.2 / 0.5 / 1.0 m rendered byte-identical. |
| `reflections.geometry` | a shoebox room instead of four fixed taps: `width_m`/`depth_m`/`height_m`, a `listener`, six surface `materials` from the `materials` preset library, `max_order`, `max_taps`, `min_level_db`. Delays become real path lengths and each surface filters its tap with its own octave absorption (`scripts/spatial_hrtf/room.py`). |
| `reflections.late` | the directional late field: `count` decorrelated tails from spread directions, sharing `rt60_s`, `hf_decay`, `rise_s`. `level_db` is relative to the dry signal. One tail in both ears is the in-head sound; this is what `imm_envelopment` measures. |
| mix `immersive.hrtf.dataset` | the head data in use: bundled or the listener's own set (section 1). |

A moving source now updates its filter in the STFT domain every 256 samples (`spatial_hrtf/binaural.py::_stft_place`) instead of
interpolating harmonic gains 20 times a second, and `doppler` (default true) resamples the path length, so a crossing source
gets its time-varying cue and its pitch shift together. `references/data/presets/spaces/concert_hall_3d.json` is the worked
example: copy it into a project and change the box.

## 2c. Immersive 2.0: the ambisonic bus (`immersive.engine: "hoa_bus"`)

```json
"immersive": {"enabled": true, "engine": "hoa_bus", "order": 5,
              "anchor_max_span_deg": 6.0, "max_deg_per_sec": {"anchor": 10.0, "mover": 120.0}}
```

`engine` is `"per_stem"` in the shipped defaults, so an older piece mixes exactly as before. `presets.py scaffold mix`
writes `"hoa_bus"` for a new project. Code: `scripts/spatial_engine/hoa.py`, `trajectory.py`.

On the bus every source, reflection and late tail is written into one ambisonic sound field (order 5, 36 channels)
and the field is decoded once: to headphones through the same MagLS head filters, to loudspeakers through an
all-round decoder built on the engine's VBAP. On a loudspeaker target the direct sound stays VBAP; the bus adds the
room behind and above it.

| | `per_stem` | `hoa_bus` |
|---|---|---|
| a still source | one head filter per stem | the same samples (measured: under -60 dB difference) |
| a moving source | filter updated every 256 samples, no reflections, air loss for the farthest point only | a gain curve on the harmonics, every image source followed along the path with its own delay and Doppler, air loss per frame |
| trajectory | `start_*` / `end_*` only | also `keyframes` and `mode: "sway"` |
| late field | one render per stem, level set per stem | one render per room; `level_db` is tail power against the dry power of a steady broadband source |
| a stereo bed | reflected as one source at its centre | each side reflected from its own side |
| `widen` / `width` on a placed track | applied to the binaural signal | not applied: width is the pair angle (`half_width_deg`) |
| the room over time | fixed | `scenes` on the space preset |

**Trajectory** (a track's or a preset's `spatial.trajectory`):

```json
"trajectory": {"spatial_role": "mover", "doppler_strength": 1.0,
               "keyframes": [{"bar": 1, "azimuth": -35, "elevation": 5, "distance": 3.2},
                             {"bar": 9, "azimuth": 40, "elevation": 20, "distance": 1.6}]}
```

- A key is placed by `t_s` (seconds), `bar` (1-based, through the score's tempo map) or `section` (a name in the
  score's `plan.sections`, plus an optional `bar` inside it). An axis a key leaves out keeps its last value.
- The curve between keys passes through every key and never overshoots one. Angles are not wrapped: write
  `0` to `360` for a full turn.
- `mode: "sway"` moves around the track's own place: `rate` in cycles per bar (`sync: "bars"`) or Hz
  (`sync: "seconds"`), with `azimuth_span_deg`, `elevation_span_deg`, `distance_span_m`.
- `spatial_role: "anchor"` holds a source within `anchor_max_span_deg` of its place at a fixed distance. Bass and
  drums are anchors whatever the preset says. `"mover"` is free.
- `doppler_strength` sets the pitch shift of the direct sound, from none (0) to the physical one (1); `doppler: false` is 0.
- Keyframes or a mode on the `per_stem` engine is an error that names the switch.

**The room, worked out instead of typed in** (space preset):

| Key | Value | What it does |
|---|---|---|
| `reflections.late.rt60_s` | `"auto"` | Eyring's reverberation time per octave band from the box, its materials and the air (`room.eyring_rt60`). The tail and the reflections then describe one room |
| `reflections.late.pre_delay_ms` | `"auto"` | the tail starts at the room's mixing time, `20 V/S + 12` ms (Lindau, Kosanke & Weinzierl 2012) |
| `geometry.materials` | `"open"` | a surface that is not there (open sky, a missing wall): nothing comes back from it |
| `distance.near_field.model` | `"dvf"` | the rigid-sphere distance variation function (Duda & Martens 1998; Kan, Jin & van Schaik 2009): the level difference between the ears grows towards low frequencies as the source closes. `"geometric"` is the older rule |
| `scenes` | list | the room changes during the piece, below |

```json
"scenes": [{"anchor": {"section": "B"}, "transition_bars": 4,
            "space_overrides": {"geometry": {"width_m": 22, "depth_m": 26, "height_m": 11},
                                "late": {"level_db": -14}}}]
```

A scene starts at its `anchor` (the same forms as a trajectory key) and fades in over `transition_bars` or
`transition_s`. `space_overrides` is merged into the `reflections` block of the state before it. What is faded is
each room's input, with weights that always sum to one: the old room rings out while the new one builds, and two
identical rooms crossfade to exactly the same room.

Measured in `tests/test_immersive_v2.py`: a source at 25 cm and 90 deg gains over 6 dB of level difference at 300 Hz
from the `dvf` model; an approach at 17 m/s raises a 1 kHz tone by the physical 5 %; a full orbit of a tone passes
the click check; the all-round decoder holds plane-wave power within 4 dB peak to peak on 7.1, 7.1.2 and 7.1.4.

## 2d. Deliverables that carry the scene, not a speaker feed

| Target | File | What it is |
|---|---|---|
| `ambix` | `master_ambix.wav` | the bus itself as AmbiX (ACN order, SN3D), fifth order. Any ambisonic decoder can put it on any loudspeakers or headphones later, and it can still be rotated (head tracking, 360 video) |
| `adm_bw64` | `master_adm.wav` | one channel per placed track with its position over time as ADM metadata, plus the reverb return as a stereo bed. The playback renderer does the panning |
| any target with `"rate_hz": 48000` (shipped: `stereo_48k`) | as its preset says | the finished programme resampled last; the true peak is measured again at the new rate and the whole file is turned down if it now passes the ceiling |

Both scene formats switch the immersive block on for themselves, as `binaural` does, so the score's stereo mix preset
is not changed. Loudness: a scene has none until something renders it, so `ambix` is levelled on its first channel
(the plain pressure) and `adm_bw64` on a plain two-speaker fold of its objects; one gain for the whole file. The fold
is this engine's internal levelling reference, not a standard-required loudness (an object file has no loudness until
a renderer folds it); the method is recorded in the delivery report and asserted in the gate's `adm.loudness` row.

ADM routing and metadata (what the file actually contains):

| Track | Audio in the file | ADM metadata |
|---|---|---|
| placed mono (`spatial` present, not `binaural: false`) | one mono object channel, per-track processing only (no pan, no air absorption, no distance law -- `mixer._place` hands it over unplaced and adm undoes the `1/max(dist,1)` scalar it applies so the renderer does not apply it twice) | azimuth/elevation/distance at BS.2076 conventions (azimuth negated: engine +right becomes ADM +left; elevation passes through; engine distance in metres written as the normalised ADM distance, 1.0 = 1 m default sphere radius) |
| placed stereo | two mono object channels (left at azimuth minus the pair half-width, right at azimuth plus it; the width is `pair_half_width` -- `spatial.half_width_deg`, else the `immersive.pair` width, else 0 for dual-mono, one object then, since the content is one) | each channel its own object with its own position blocks; no mid fold, no dropped channel |
| `binaural: false` (explicitly out of the field) | the stereo outcome split as a mono per channel | two flat objects at +-30 deg, elevation 0 |
| no `spatial` block | the mixer's stereo placement outcome (width/widen/pan seating) split per channel, or one centred object when mono | two flat objects at +-30 deg, or one centred object; elevation follows the role (`place_of`), so bass/drums stay on the floor |
| reverb return, when the mix produced one | two extra channels | a `room return` stereo bed on the 0+2+0 common definition (AP_00010002, referenced, not redefined) |
| no reverb return | no bed channels | no bed object |

A moving object (trajectory `line`/`keyframes`/`sway`, anchored the same way `hoa` anchors it) gets `audioBlockFormat`
blocks whose stride adapts to the trajectory's fastest angular speed: at least every 0.1 s, at most 200 blocks per
second, and no step above about 2 deg (the largest step is reported in the delivery report). Blocks are positioned
at their end and tile the file exactly (first at 0 to the last sample, 1e-5 s grid), so a renderer that interpolates
between them reproduces the authored path.

The container is strict BW64 (BS.2088-2): `BW64` + 0xFFFFFFFF + `WAVE`, then `ds64` (64-bit file and data sizes),
`fmt `, `chna`, `axml`, `data`, always -- even below 4 GiB -- so the format is recognisable by structure, and audio is
streamed in bounded blocks so the data chunk may pass 4 GiB. `scripts/spatial_engine/adm.py` (with `validate_file`)
writes and checks it without the EBU libraries, whose releases pin numpy below 2. Sampling is 24-bit PCM with no
clipping ever: a non-finite sample or a sample over full scale is an error, never a hard-clipped file. The delivery
gate (`spatial_gate.adm_rows`, behind `adm.container` / `adm.channels` / `adm.loudness` plus the shared
`delivery.true_peak` / `render.finite`) fails the file for a plain RIFF container, a broken ds64, a chna that does not
map 1:1 to ADM tracks, unresolved IDs, non-contiguous blocks, out-of-range positions or a true-peak overshoot.
Players that only understand RIFF/RF64 cannot open the BW64 magic, and libsndfile/soundfile cannot read BW64 at all,
so the project reads its own files back with `adm.parse`. The writer's structural check is the gate
(`tests/test_adm_bw64.py` covers it byte for byte), and the files were additionally checked outside the project
against the EBU implementations: libbw64 0.10.0 (BS.2088) opened them as `BW64`, reported `ds64` sizes matching the
file on disk, the `chna` rows and `axml` chunk, and read every frame; the EBU ADM Renderer 2.1.0 (BS.2076 parser /
BS.2127) opened them, reconciled `chna` against the AXML, validated the model, and rendered them with
`ear-render --strict -c` to BS.2051 `0+5+0` and `4+7+0` without warnings or overload. libadm itself was not built
(its CMake requires Boost, which this environment lacks), so no libadm-specific schema validation result exists. It
is an open-standard ADM file, not a Dolby Atmos master and not a certified deliverable.

## 2e. Immersive 3.0: every channel count from one mix

Mono, the 5.1 family, loudness and limiting of a layout file, and where the arithmetic runs (CPU or GPU) are in
`references/spatial/immersive-deliverables.md`.

## 3. Stage 0 (project gate) and the Stage 6 immersion rows

Stage 0 blocks when immersive is on and: the mix preset lacks `height_by_role`/`max_elevation` or a real `character`; the head data is not downloaded
(`python -m spatial_hrtf.data`); a bass/drum is lifted; an elevation exceeds `max_elevation` or disagrees with the direction sheet; fewer than `min_height_tracks` are lifted.

| Row | Meaning | Level |
|---|---|---|
| `imm_cues` | probe at +-60 deg: level difference above 8 dB, right source reaches the right ear first by over 0.3 ms (numbers from `tests/test_hrtf.py`) | FAIL |
| `imm_elevation` | the 6-12 kHz tilt grows by over 3 dB at +60 deg | FAIL |
| `imm_frontback` | 30 deg vs 150 deg tilt differ by over 2 dB | WARN |
| `imm_height_rules` | rules 1-4 hold on the final score | FAIL |
| `imm_band` | lifted stems hold at least 0.3% of their energy above 4 kHz | WARN |
| `imm_externalization` | reflections from at least 3 directions; their level is -30 to -3 dB re direct | FAIL / WARN |
| `imm_envelopment` | late-tail interaural correlation under `gate.max_late_iacc` | WARN |
| `imm_width` | master L/R correlation under 0.95 | WARN |
| `imm_foldown` | mono fold-down no more than 3 LU below the stereo master | FAIL |
| `imm_coloration` | front-facing 1/3-octave deviation from the dry signal, 500-5000 Hz, under 3.5 dB rms | WARN |
| `imm_route_parity` | the measured-head and analytic routes agree within 3 dB and 0.2 ms at +-60 deg | WARN |

All nine rows are gate-profile rows (`imm.*` in `gate_profiles.py`, reported under their `imm_*` ids), so a type of piece can skip or relax one with a measured reason, and every threshold the function compares against is read from that profile — none is a constant in `quality_gate.py`.

Rows of the ambisonic engine (`quality_gate.immersive2_rows`, `fold_rows`):

| Row | What is measured | Level | Fix |
|---|---|---|---|
| `imm_kinematics` | the fastest angular speed along each track's `trajectory`, against `immersive.max_deg_per_sec` for its role (`anchor` / `mover`) | FAIL | spread the keyframes further apart, or make the part a mover |
| `imm_low_fold` | below `hz` (250), the power of the two channels against the power of their mono sum | FAIL above 2.5 dB | keep bass and kick centred and unplaced in height; narrow a wide bed below the corner |
| `mix.band_fold` | the same loss in each auditory band (one ERB wide) from 100 to 5000 Hz, for a two-channel master that is not immersive; bands more than `floor_db` under the loudest are not judged | FAIL above 3.5 dB | the row names the band and the stem most out of phase there: lower that stem's `widen`, or its pair width |
| `imm_iacc_early` | the room's own impulse response (`hoa.probe_brir`): interaural correlation of the first 80 ms, mean of the 500, 1000 and 2000 Hz octaves | WARN above 0.97 | bring a side wall in or make it harder: lateral reflections are what widen a source |
| `imm_clarity` | the same response: C80, early against late energy, mean of the 500 to 4000 Hz octaves. Only the low side can trip | WARN below -5 dB | lower `late.level_db`, shorten `rt60_s`, or move the sources closer |

Two unrelated channels lose 3 dB in mono, so the fold rows only fail when a band actually cancels. A headphone
master is not given `mix.band_fold`: the delay between the ears of a source at the side notches the mono sum near
700 Hz by itself. `imm_iacc_early` has little range here, because the probe's direct sound dominates its first 80 ms:
a room with no reflections reads 1.00 and the scaffolded hall at 2.5 m reads 0.96, so the row only flags an early
field that is nearly empty. The two room rows
exist only on `"engine": "hoa_bus"` with a space the project owns, because that is the only route where one room
holds every source; the probe sits in front at the median distance of the piece's tracks. `imm_clarity` is skipped by
the `ambient` profile: a bed is meant to sit inside its tail. Concert halls measure about -5 to +5 dB and a dry studio
far above that, which is not a fault, so there is no upper limit.

Thresholds other than the `test_hrtf.py` numbers are provisional: calibrate on a real piece, then freeze them; never loosen one to get green.
Loudness, true peak, clicks and silence are the existing rows.

## 4. Why these cues

- Reverberation and spectral detail in the direct sound are the two essential cues for externalising headphone sources, even with non-individual data (Li, Schlieper, Peissig 2019, Applied Sciences 9(3):460). Hence directional reflections.
- Envelopment needs surrounding sound events arriving densely from spread directions, and sound from above is its own attribute (arXiv 2301.10210). Hence beds as pairs and a ceiling reflection; a multi-direction late tail is not built yet.
- IACC alone does not predict envelopment, so `imm_envelopment` is a WARN. Spectral manipulation helps elevation with non-individual HRTFs.
- Methods already vendored: MagLS binaural decoding in `spatial_hrtf`, FABIAN head data.

## 5. Limits (state them in the reply)

- Height with the FABIAN dummy head is weak and differs by listener; front/back can flip.
- The late field is a statistical tail (`room.late_ir`), not a geometric ray-traced one: it has the room's RT60, damping and direction spread, not its actual wall pattern beyond `max_order`.
- Surface diffusion is not modelled (a specular image cannot scatter); `geometry` keeps the strongest `max_taps` images and stops at `min_level_db`. Below the Schroeder frequency of a small room the modal behaviour is not modelled either.
- A listener's own set must be a `.mat` with `hrir_l`/`hrir_r`/`azi`/`zen` or a SOFA file; a set at another rate is resampled, but nothing checks it was measured at the same distance convention as FABIAN.
- Everything is measured by probes and proxies. Nothing replaces listening on headphones (`listen.py`, then a person).
- On the ambisonic bus: a reflection of a moving source takes one air filter for its mean path (the direct sound
  gets the exact one per frame); a near-field source is decoded on its own, because no sound field holds two ears at
  different distances, and on loudspeakers it has no near-field cue at all; a matrix decoder on ten or twelve
  loudspeakers cannot hold power exactly (measured spread up to 3.4 dB on 7.1.2).
- `"auto"` reverberation time is Eyring's diffuse-field estimate. It is wrong for a room that is not diffuse: a long
  corridor, a room with one very dead surface, anything coupled to another space.
- `adm_bw64` is an open-standard ADM file. It is not a Dolby Atmos master file, carries no vendor certification, and
  its container is strict BW64, so a data chunk may pass 4 GiB (the 32-bit fields then saturate and the true sizes live
  in `ds64`; audio is streamed, so RAM does not grow with the file). An object carries the track after the mixer's chain
  but without the room: early reflections and the late field are not in the file, only the shared reverb return is, and
  it is a stereo bed rather than per-object room metadata. The distance is written in metres as the normalised ADM
  distance (1.0 = 1 m), so a renderer that scales it by `absoluteDistance` will place the objects in that room.
- What the outside check covered, and what it did not: libbw64 and the EBU ADM Renderer parsed and rendered these files
  (see the container paragraph above), which is the strongest reading available here, but neither replaces an ADM
  profile validator: libadm was not built (Boost missing), nothing checked a delivery profile such as BS.2088/BS.2076
  conformance of every optional element, and no file past 4 GiB was written end to end (the `ds64` saturation path is
  exercised on a small file by overriding `adm.SATURATE_AT`). Both tools were installed in a scratch environment, not
  in the project; the check is recorded here rather than run by the test suite.
- 24-bit PCM only. The writer refuses a non-finite sample or a sample over full scale instead of clipping, so a mix
  that cannot meet its ceiling fails the gate rather than being forced into compliance.
- `ambix` holds the whole field in memory while it is scaled and written; a long piece at order 5 needs several GB.
  If it is the only target of a score, the stereo rows of the gate read its first two channels, which are not left
  and right: list a two-channel target first.
- The channel-based 7.1, 7.1.2 and 7.1.4 WAV renders are not object-based Atmos/ADM, and speaker-layout gate checks do not replace listening on a correctly configured playback system.
