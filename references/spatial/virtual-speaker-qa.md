---
id: virtual-speaker-qa
title: Virtual speaker arrangements and per-bar channel QA for any channel count
domain: sound-design
status: partly-sourced
summary: Virtual speaker arrangements and the per-bar channel QA rows for any channel count.
tags: [immersive, speakers, channel, qa, layout]
load_when:
  - a channel.bars or delivered-layout row fails
  - choosing a speaker layout for a delivery
sources: [ITU-R BS.2051-3, EBU Tech 3304, ISDCF test content, AES e-library paper 16554, arXiv 2210.00378, Fraunhofer multichannel reference]
used_by: [scripts/channel_qa.py, scripts/spatial_gate.py, references/spatial/virtual-speaker-qa.md, knowledgebase/sound-design/virtual-speaker-qa.md]
updated: 2026-11-22
---

# Virtual speaker arrangements and per-bar channel QA

> **Partly sourced.** The ITU, EBU and ISDCF documents were read as search-result excerpts and their published
> structure, not as complete conformance runs. The AllRAD and energy-vector sources are cited for the decoder
> design, not for a calibrated threshold. The numbers in `channel.bars` are starting values; they are not yet
> tuned on a listening corpus.

A multichannel master can pass peak, loudness and format rows and still have one channel wrong for one bar: a
send that was automated late, a dropped region, a polarity point, a pan that jumped. The same failure exists in a
36-channel AmbiX file, but an AmbiX file has no loudspeakers to measure. This layer measures the delivered channels
on the positions they claim, and decodes AmbiX to a virtual array first.

## 1. Where the channels are measured

| Delivered target | Positions used | What the row can see |
|---|---|---|
| a loudspeaker layout (stereo, 5.1, 7.1.4, 22.2, a project layout) | the layout's own `speakers` block, in channel order; an LFE channel has no position and is checked for level, dropout and polarity only | per-channel faults and left/right, front/back, floor/height balance |
| order-5 AmbiX (36 ACN/SN3D channels) | decoded with `hoa.allrad_matrix` (AllRAD with max-rE) to the 36 points of `ambix_qa_36` | per-virtual-speaker faults and the same spatial balance |
| a file with no declared layout | channel index only | per-channel jump, dropout and polarity; no spatial balance |

The channel count is a fact, not a preference. A declared layout whose speaker count differs from the file is a
FAIL in `channel.virtual`; so is an AmbiX file whose channel count is not `(order + 1)^2` (36 at order 5).

`render_targets` supplies the target and `spatial_engine.config` supplies the layout. An unknown or project layout
works if it has a `speakers` block; no Python change is needed.

## 2. Why a virtual array for AmbiX

An order-5 sound field is 36 channels, and every one of them carries the whole scene in a different spherical
harmonic. A single broken ACN channel changes the decoded field everywhere, not one speaker. Decoding to a virtual
array turns that into a measurable per-position signal, and gives the per-bar test something to compare: a
speaker that is 12 dB low for one bar is the same fault as a real surround send that is 12 dB low for one bar.

`hoa.allrad_matrix` already builds the decoder this engine uses: 1200 near-uniform virtual directions are panned
to the target speakers with VBAP, with max-rE weights per order, so an irregular array keeps power and direction
better than a plain projection decoder. `ambix_qa_36` is the target for QA: 36 points from a Fibonacci sphere,
names `V01`-`V36`, azimuth/elevation in the layout convention (positive azimuth to the left, positive elevation
up). It is a decode target, not a room; it has no LFE and no reflections.

The AmbiX conversion is ACN/SN3D (Nachbar et al. 2011). The engine's decoder is for its internal orthonormal field,
so the per-order AmbiX scale `sqrt(4*pi/(2n+1))` is divided out before the matrix product; the test
`test_order_five_ambix_decodes_to_36_virtual_speakers` checks the shape, finiteness and a clean one-bar control.

36 is the minimum useful count for order 5, not a claim that 36 is a spherical design. AllRAD's own sampling is the
dense 1200-point sphere inside `allrad_matrix`; the 36 points are where its output is observed.

## 3. The per-bar question

`channel.bars` splits the file at the score's bar lines (the tempo map, rubato included) and measures RMS per
channel per bar. For each interior bar it asks one narrow question: is this bar different from **both** neighbours
for **one** channel, while the other channels stay still?

| Finding | Test | Default |
|---|---|---|
| `jump` | the same channel is above or below both neighbours by more than `jump_db` | 8 dB |
| `dropout` | the channel is below both neighbours by more than `dropout_db` and the neighbours agree | 15 dB |
| `balance` | left/right, front/back or floor/height energy ratio moves by more than `balance_db`, with both neighbours agreeing | 4 dB |
| `polarity` | the channel's best-lag correlation with both neighbours is below `polarity_corr`; both must be strongly negative | -0.5 |

The "other channels stay still" condition is what separates a channel fault from a deliberate accent. A one-bar
accent moves every channel in the bar, so none of them is isolated; a single send that is muted or boosted for one
bar leaves the rest of the bar's channels in place. The correlation uses the best lag in a small window, because a
bar boundary can land at a different phase of a sustained tone; an inverted bar still has a negative peak.

The thresholds are gate-profile parameters (`gate_profiles.ROWS['channel.bars']`). A profile may relax or skip the
row with a measured reason; a score may override it in its `gate` block. A whole-bar accent is not a reason to
loosen the row, and the row is never edited to make a failing file pass.

## 4. What the rows report

`channel.virtual` names the mapping (layout and positioned channels, or the virtual sphere) and fails on a wrong
channel count, too few virtual speakers, or a non-finite decoded channel. `channel.bars` names the bar, channel
and kind of each finding; fewer than three bars is an INFO, because an interior bar has nothing to compare against.

A FAIL is a fact about the file, not a taste judgment. Fix the channel's automation, send, pan or polarity in that
bar; if the one-bar move is intentional, record the measurement and relax the row for that piece.

## 5. Sources and limits

- ITU-R BS.2051-3 defines the speaker labels and the azimuth/elevation convention used by the layout presets.
- EBU Tech 3304 defines multichannel line-up and channel-identification signals: presence and position of every
  main channel, the LFE, and polarity. It is the reason channel presence and polarity are separate checks from a
  long-term spectral row.
- ISDCF audio test content uses per-channel voice slates and SMPTE ST 2095-1 pink noise to check that each channel
  is reproduced and calibrated; it is a listening/room procedure, not a substitute for this measurement.
- Zotter & Frank, "All-Round Ambisonic Panning and Decoding", JAES 60(10), 2012: the AllRAD/virtual-sphere method.
- The energy-vector/max-rE criteria used to judge a decode are summarised in the mixed-order decoder literature
  (arXiv:2210.00378): constant energy, velocity vector at low frequency, energy vector at high frequency.
- Fraunhofer's multichannel AAC page is a practical channel-identification example (spoken slates, EBU Tech 3304).

Limits: this is not a listening test, the virtual array is not a room, and the per-bar RMS test cannot hear a
timbre change that leaves the level alone. A 36-point sphere has no point exactly at the poles and is not a
certified spherical design; it is a QA observation grid. Low-frequency direction is not meaningful in a
first-order sense and the LFE channel is deliberately given no position.
