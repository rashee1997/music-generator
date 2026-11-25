---
title: Immersive 3.1 details
summary: Decoder uniformity, the MagLS crossover, diffuse-field EQ and octave-band NFC-HOA, with their measurements.
tags: [immersive, decoder, allrad2, magls, nfc, hoa]
load_when:
  - changing the immersive decoder or headphone filters
  - an imm.decode_uniformity row fails
---

# Immersive 3.1: decoder uniformity, MagLS crossover, NFC-HOA

Four changes, each measured in `tests/test_immersive_31.py`; the numbers below are starting values, not calibrated
pass marks.

**AllRAD2 is the default speaker decoder** (`immersive.decoder`: `allrad2` | `allrad`). It replaces the per-speaker
AllRAD matrix with a plane-wave-uniform one: the decoder is built from an equal-area (Fibonacci) sample sphere with the
AllRAD panning gains, then normalised so the decoded power of a plane wave is the same in every direction. On six
layouts at order 5, 400 probe directions, the power spread falls from 4.66 / 7.10 / 7.11 / 5.91 / 7.93 / 7.66 dB
(5.1, 5.1.2, 5.1.4, 7.1, 7.1.2, 7.1.4) with AllRAD to 0.45 / 0.40 / 0.43 / 0.51 / 0.49 / 0.55 dB. Both matrices are
built from the engine's own Fibonacci kernel; no spaudiopy grid file is needed. `imm.decode_uniformity` (WARN, default
limit 2.0 dB) measures the configured matrix on every multichannel delivery.

**MagLS crossover and diffuse-field EQ.** `decoder.magls_bin` now takes `f_trans`, and `binaural.magls` reads
`immersive.hrtf.f_trans_hz` (default 1500 Hz; the order-dependent fallback is `min(N*600, 1500)`, so 1500 Hz at order 5).
The 2022-2025 MagLS literature places the perceptual crossover near 1.5 kHz, not the 3 kHz the old `N*600` produced.
`immersive.hrtf.diffuse_eq` (default true) applies a smoothed, per-ear diffuse-field correction computed from the loaded
head set, capped at +-6 dB; on the synthetic head set it lowers the >2 kHz RMS deviation from 0.67 to 0.28 dB. The disk
cache tag now includes the crossover and the EQ flag, so changing either never reuses stale filters.

**NFC-HOA (opt-in, direct sound only).** `immersive.nfc.enabled`, with `max_m` (1.0), `ref_m` (1.0) and `max_gain_db`
(30, the regularisation Favrot & Buchholz use). A static source closer than `max_m` is encoded per order with Daniel's
near-field filters (the Hankel-function ratio between source and reference radius, Adamek's formulation), so a nearby
source keeps a spherical wavefront instead of collapsing to a plane wave. At 20 Hz and 0.5 m the first order gains
5.62 dB; higher orders grow faster and stop at the cap (order 5 reaches 30 dB). The filters are applied to the direct
sound only: reflections, the late field and moving sources keep the ordinary encoding, because the per-order distance
filters assume a fixed source position. Measured boosts and the cap are reported, not hidden.

All three settings are checked by `mix_schema.validate`: an unknown `immersive.nfc` key, a crossover outside
200-12000 Hz or a cap outside 0-40 dB is reported with its path.
