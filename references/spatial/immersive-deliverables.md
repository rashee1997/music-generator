---
title: Immersive 3.0 deliverables
summary: One mix delivered at every channel count: rendered mono, the 5.1 and 7.1 families, loudness and limiting of a layout file, the fold-down rows, and CPU or GPU rendering.
tags: [immersive, mono, surround, deliverables, loudness, limiter, gpu, fold-down]
load_when:
  - the piece must exist in mono, 5.1 or any loudspeaker layout
  - a fold.* or imm.loudness gate row fails
  - the render should use a GPU, or more than one core
---

# Immersive 3.0: every channel count from one mix

One mix, one set of per-track decisions, and a summing bus per deliverable. `output_targets` names the formats,
a loudspeaker stereo master first; each extra format is rendered after the first is certified and judged by its own rows.

| Target | Layout preset | Channels, in file order |
|---|---|---|
| `mono` | none | `M` |
| `stereo` | none | `L R` |
| `immersive_5_1` | `itu_bs2051_system_b` | `FL FR FC LFE SL SR` |
| `immersive_5_1_2` | `itu_bs2051_system_c` | the 5.1 ring, then `TFL TFR` |
| `immersive_5_1_4` | `itu_bs2051_system_d` | the 5.1 ring, then `TFL TFR TBL TBR` |
| `immersive_7_1`, `immersive_7_1_2`, `immersive_7_1_4` | `itu_bs2051_system_h`, `_i`, `_j` | the 7.1 ring, then the overhead pairs |

Another layout is a JSON file in `<project>/presets/layouts/` and a target in `<project>/presets/outputs/`: speakers
with azimuth and elevation, a `downmix` pair per speaker, the `lfe`, `reverb`, `decorrelation` and `gate` blocks. No
Python changes.

**Mono is rendered, never folded.** Adding the two channels of a stereo or headphone master inherits everything that
master did to place its sources: a hard-panned part comes out 3 dB down, a widened part loses what was added out of
phase, a head-filtered source is notched where its two ears disagree. The `mono` target takes every track from the
mixer before pan, width and head filter, applies only the distance laws, and sums. A track that is stereo in itself and
the shared reverb return are averaged, and the level that averaging costs is given back with one gain bounded by the
target's `mono.compensate_max_db`; a part whose channels cancel is not boosted to rescue it. The `fold.mono` row then
says what a listener hears when a device sums the stereo file instead.

**A track with a `pan` and no `spatial` block** sits on a layout's front stage at that pan: full left is the front-left
loudspeaker (`reverb.front_azimuth_max` is the half-width of the front stage). A piece with no 3-D staging therefore
keeps its stereo picture on a layout, and `imm.surround_ratio` reports that nothing is behind the listener.

**Loudness and peaks of a layout file.** A target with `"loudness": {"method": "bs1770_layout"}` is levelled on the
delivered channels with the layout's own `loudness_weight_db`, the low-frequency channel excluded; `"stereo_fold"`
levels it on the two-channel fold instead. `"limiter": {"enabled": true, "lookahead_ms", "release_ms", "oversample",
"max_reduction_db", ...}` puts one linked gain curve on every channel, so the picture does not move when a peak is
caught. When reaching the target would take more than `max_reduction_db`, the programme keeps its dynamics, comes out
under the target and `imm.loudness` says so: lower the target or accept it. With no `limiter` block the file is only
trimmed under its ceiling.

**Where the arithmetic runs.** `render.compute.device` in the mix preset is `auto`, `cpu`, `cuda` or `mps`; the
`MUSICGEN_DEVICE` variable overrides it for one run. `auto` takes a GPU when torch is installed and reports one, and the
CPU otherwise; a device that is asked for and absent falls back to the CPU with a line in `mixer.STATE['compute']`.
The convolutions (head filters, air absorption, the late field) are the work that moves; recursive filters, the
limiter and the sample players stay on the CPU. A CPU render is bit-for-bit independent of this setting. A GPU render
differs from it in the last bits of float32, so the gate certifies the render that was made. `render.mix_workers`
(`auto` or a count) processes that many stems at once; the samples are the same as one after another.

## Limits (state them in the reply)

- The layout positions are the nominal ones of ITU-R BS.2051; the gate windows, the fold coefficients for overhead
  speakers, the limiter times and the fold-down band limits are starting values. None was tuned on a room.
- The `fold.*` rows compare long-term spectra after level matching. They are not a listening test.
- A binaural master summed to one channel is notched by the delay between the ears. That is the head, not a fault, and
  it is why `mono` is its own target.
- The GPU kernels run only on a machine that has one. A piece certified on the CPU says nothing about the GPU render
  of it until that render is gated too.

## Stereo master: speakers or headphones (`immersive.stereo_decode`)

On the ambisonic engine the two-channel master is decoded from the field once, and the mix preset says how:

| `stereo_decode` | Decoder | Use |
|---|---|---|
| `binaural` (default) | head-filtered (MagLS), ears disagree on purpose | a master meant for headphones |
| `speakers` | AllRAD to the pair in `immersive.stereo_layout` (default `stereo_bs775`, +-30 deg), no head filter | a master meant for loudspeakers, and the one `fold.mono` assumes |

A head-filtered master loses 3-5 dB when its two channels are added, in the 450-1500 Hz band where a lateral source
reaches the ears out of phase. Moving parts toward the centre cut only part of that (measured on one piece: -5.2 to
-4.7 dB); decoding for loudspeakers brought the same piece to +3.1 dB against the 3.5 dB limit. The stereo pair is a
layout preset with `"decode_only": true`: it needs no low-frequency channel and no room return.

`mastering.highpass_order` (default 1) cascades the master high-pass: Pedalboard's filter is first order, so 55-70 Hz at
order 3 is what removes a loud sub from a loudspeaker stereo master. The sub is then carried by the layouts' low-frequency
channel. `master.dc` measures 1 s block means, and a loud 80-120 Hz tone that does not complete its cycles in each block
reads as drift, which is why the high-pass, and not a looser row, is the fix.

## Choosing what to render

Each format is its own mixing pass, run one after another after the stereo master is certified, so a render with six formats takes about six times as long. With no format named the default is `stereo` plus `immersive_7_1` (8 channels). `pipeline.py --only <comma list>` renders only those and overrides the score; name `stereo` first because the `fold.*` rows compare every other format with it. A 7.1 file as the only format failed three rows on a 117 s cue (clipping and a true peak 1.6 dBTP over the ceiling once folded to two channels, and `master.dc` on the low-frequency channel); until the multichannel master limits against its own fold, keep `stereo` in the list.
