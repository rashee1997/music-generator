---
id: virtual-speaker-qa
title: Virtual speaker arrangements and per-bar channel QA
domain: sound-design
status: partly-sourced
sources: [https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.2051-3-202205-I%21%21PDF-E.pdf, https://tech.ebu.ch/docs/tech/tech3304.pdf, https://www.isdcf.com/resources/test-content/audio/, https://www.aes.org/publications/elibrary-page/?id=16554, https://arxiv.org/abs/2210.00378, https://www2.iis.fraunhofer.de/AAC/multichannel.html]
used_by: [scripts/channel_qa.py, scripts/spatial_gate.py, references/spatial/virtual-speaker-qa.md]
updated: 2026-11-22
---

> **Not verified in full.** The standards and the AllRAD paper were read as search-result excerpts in the session
> that wrote this file. The physical facts below are sourced; the dB thresholds are working starting values for
> `scripts/channel_qa.py`, not measurements of a listening room or a calibrated corpus.

# Virtual speaker arrangements and per-bar channel QA

## Why a virtual arrangement

A channel-based master is easy to inspect: every channel has a nominal loudspeaker position. A scene-based master
does not. Fifth-order AmbiX has 36 channels, and no one channel is a speaker; each carries a spherical-harmonic
component of the whole field. To judge it channel by channel, decode it to a known array first, then measure the
array. The decoder is also the only way to ask a spatial question - is the left side 6 dB low for this bar? - of a
format that has no left side until it is decoded.

**AllRAD** (All-Round Ambisonic Decoding) builds that array in two stages: sample the sphere with a dense,
near-uniform set of virtual directions, decode the field at each direction, then pan each virtual source to the
real loudspeakers with VBAP. Max-rE weights reduce side lobes. This handles irregular arrays and keeps power and
direction more stable than a plain projection decoder. The engine's `hoa.allrad_matrix` uses 1200 Fibonacci-sphere
directions and the engine's own VBAP; `ambix_qa_36` is a 36-point observation array for order 5.

| Format | Channel count | Position source |
|---|---|---|
| Stereo (BS.775) | 2 | L/R at ±30° |
| ITU-R BS.2051 system J (7.1.4) | 12 | middle ring plus four overhead |
| ITU-R BS.2051 system H (22.2, 9+10+3) | 24 | three layers plus two LFEs |
| AmbiX order 5 | 36 | decoded to `ambix_qa_36` |
| no declared layout | any | channel index only |

ITU-R BS.2051 defines the labels and the convention: azimuth is positive to the left facing the front, elevation
is positive upward. The 22.2 system is 9 upper + 10 middle + 3 bottom channels plus two LFEs (24 channels), not
22.2 "speakers" in the home-layout sense. The layout presets use the same nominal positions.

## What a per-bar test can catch

A channel fault that is present for one bar only is invisible to a whole-file RMS or spectrum: the file's average
is dominated by the other bars. Splitting at the score's bar lines and comparing an interior bar with both
neighbours isolates it.

| Fault | Observable | Starting value |
|---|---|---|
| send/automation jump | one channel differs from both neighbours in the same direction | 8 dB |
| dropout or muted region | one channel is below both neighbours, neighbours agree | 15 dB |
| balance/pan jump | left/right, front/back or floor/height ratio moves for one bar | 4 dB |
| polarity inversion | best-lag correlation with both neighbours is strongly negative | -0.5 |

The isolation condition matters. A one-bar accent raises (or lowers) every channel in the bar, so no single channel
is isolated; a one-bar mute, a bad automation point or a polarity flip leaves the other channels in place. The
comparison uses the best small lag because a bar line can fall at a different phase of a sustained tone; a truly
inverted bar still correlates negatively at its best lag.

## What the standards actually provide

- ITU-R BS.2051-3 is a loudspeaker-position recommendation. It gives labels and positions, not a per-bar QA
  threshold.
- EBU Tech 3304 is a line-up and identification signal: 1 kHz tone, then a clockwise channel-identification
  sequence including every main channel and the LFE. It establishes presence, position and polarity by listening.
- ISDCF audio test content uses voice slates and SMPTE ST 2095-1 pink noise per channel for the same job in a
  cinema: confirm each channel is reproduced and calibrated.
- AllRAD (Zotter & Frank, JAES 2012) is the decoding method, not a quality threshold. Max-rE and the
  velocity/energy-vector criteria describe what a good decode should preserve: constant energy, correct
  low-frequency direction, concentrated high-frequency energy. They are diagnostics, not a pass/fail limit for a
  music master.

## Limits

- The virtual array is a measurement grid, not a room, a binaural render or a listening test.
- A 36-point Fibonacci sphere has no exact pole point and is not a certified spherical t-design. It is dense
  enough to observe 36 decoded channels; AllRAD's internal 1200-point sampling is what makes the decoder.
- RMS per bar cannot see a timbre-only change or a fault shorter than the bar. It does not judge whether a
  deliberate one-bar effect is musically right.
- The thresholds are starting values. A piece with a measured reason may relax or skip the row; the row is never
  edited to hide a failure.
