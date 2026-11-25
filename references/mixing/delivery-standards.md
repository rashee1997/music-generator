---
title: Delivery standards
summary: The loudness, true-peak and micro-dynamics figures a master is judged against, and the documents they come from.
tags: [loudness, true peak, lra, plr, psr, delivery, gate]
load_when:
  - choosing a loudness target or a true-peak ceiling
  - a delivery or streaming target is named
  - the gate reports delivery.standard, master.micro_dynamics or master.mono_bands
---

# Delivery standards: the figures and the documents behind them

A loudness target is a fact about a document, not a taste. This page lists the documents the engine can
declare, the figures they define, and what the gate does with them. `mix_engine/standards.py` holds the same
data in code; `mastering.standard` in a mix preset names one of them.

## 1. The standards as data

| `mastering.standard` | Kind | Target | Ceiling | Tolerance | Document |
|---|---|---|---|---|---|
| `ebu_r128` | standard | -23.0 LUFS | -1.0 dBTP | +-0.2 LU (±1.0 where normalisation is impractical), ±0.3 dB TP | EBU R 128 v5 (2023) |
| `atsc_a85` | standard | -24.0 LKFS | -2.0 dBTP | +-2 dB (meter ~±0.5 dB) | ATSC A/85:2026-07 |
| `aes_td1008` | standard | -16.0 LUFS (track) | -1.0 dBTP | +-0.2 LU | AES TD1008 (2021) / AES77-2023 |
| `spotify` | platform policy | -14.0 LUFS | -1.0 dBTP (-2.0 when hotter than -14) | none: the platform normalises at playback | Spotify loudness documentation |

Sources: EBU R 128 v5 (2023) and EBU Tech 3342 v4 (2023); ATSC A/85:2026-07; AES TD1008
(AESTD1008.1.21-9, 2021) and AES77-2023; Spotify's loudness-normalisation documentation. The exact figure,
version and link for each entry are in `mix_engine/standards.py`, which is the data the gate reads; this page
is the reading, not a second copy of the numbers.

Apple Music and YouTube publish no music loudness target. A figure quoted for them is a third-party
measurement, so the engine does not offer one as a standard.

## 2. What the gate checks

- **`delivery.standard`** (master stage). Two different jobs:
  - If the preset's declared target or ceiling contradicts the document it names (more than 0.1 LU / 0.1 dB),
    that is a configuration fault and a **FAIL**: the report would otherwise cite a standard the profile does
    not implement. Fix the preset, not the gate.
  - If the delivered file misses the document's own tolerance, that is a **WARN** naming how far. A `policy`
    entry is **INFO**, because a platform's figure describes what it does to the file, not a rule the file must
    meet. A standard entry is never silently satisfied.
- **`master.micro_dynamics`** reports PLR, PSR, LRA and the 4x/8x true-peak readings. It is **INFO** by design:
  no document defines a pass mark for micro-dynamics, and De Man & Reiss (AES 138, 2015) found only a weak
  association between LDR and listener preference (ρ = +0.26). Writing a threshold here would invent a rule.
- **`master.mono_bands`** reports the octave band that loses the most when folded to mono, when it loses more
  than 3 dB. It is **WARN** at most: a broadband correlation hides a narrow cancellation, but no validated
  pass mark exists. MixCheck (AES 10186, 2024) found mono issues in 16.9% of submitted mixes, which is why the
  measurement is worth reporting at all.

## 3. True peak is measured twice

ITU-R BS.1770-5 Annex 2 defines the 4x oversampled reference method. EBU Tech 3343 notes that a 4x meter at
48 kHz can under-read by about 0.5 dB, which is why the EBU leaves 1 dB of headroom. `master_measures`
reports both estimates and judges the larger; a ceiling checked only on the optimistic estimate is not a
ceiling.

## 4. Known limits

The figures are quoted from the documents above. Where a platform publishes nothing, the engine asserts
nothing; where a document defines no pass mark (micro-dynamics, mono bands, masking), the gate reports the
measurement and leaves the judgement to the piece and to listening.

- The standards above define **integrated loudness**, not a musical result. A piece can hit -23 LUFS and still
  be the wrong shape for its brief (measure the arc, section 9.4b of `AGENTS.md`).
- LRA has no maximum in EBU R 128; a wide range is not a fault by itself, and LRA below one minute of audio is
  not meaningful (EBU Tech 3342).
- PSR is defined on 3 s short-term loudness. The engine reports it; it does not judge it.
- Apple Music's Sound Check raises or lowers playback volume with no published target, so no figure is claimed.
