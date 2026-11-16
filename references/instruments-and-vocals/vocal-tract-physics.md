---
title: Vocal tract physics (the waveguide model)
summary: How the vocal engine measures formant bandwidth, gain and the nasal anti-formant from a solved tube instead of reading a fixed table.
tags: [vocal, formant, bandwidth, nasal, waveguide, kelly-lochbaum, physics]
load_when:
  - a vocal preset sounds too bright, too dull or too narrow, or a vowel's level changes with the vowel
  - a project asks where the formant bandwidths come from
  - the hum's anti-formant or nasal poles look wrong
---

# Vocal tract physics: what the numbers are measured from

The engine can take each formant's **bandwidth** and **gain** from a physical tube instead of the fixed
`tract.bandwidths` / `tract.gains` lists. This file is the configuration reference; the design definition, the gate
results and the numbers behind every claim are in `docs/VOCAL-TRACT-WAVEGUIDE.md`.

## 1. Choosing the source of the numbers

| `waveguide.mode` | Bandwidth and gain come from | Behaviour |
|---|---|---|
| `physical` (default) | a tube solved to have the requested F1–F3, measured at the lip | per-vowel widths and amplitudes |
| `table` | `tract.bandwidths`, `tract.gains` | the pre-physics engine, exactly |

A preset or a caller that passes `bandwidths=` / `gains=` explicitly always wins in either mode: that is the override
the physical model demotes, not replaces. The **formant positions are never physical** - they are whatever the score
asked for, which is what keeps a score's vowels intact. `scripts/vocal_engine/voice.tract_params` is the single place
that decides, and `performance.py` calibrates level through it, so what is measured and what is rendered cannot drift.

## 2. What the measurement gives

| Quantity | Fixed table | Measured (`physical`) |
|---|---|---|
| F1 bandwidth | 90 Hz for every vowel | 111–192 Hz, per vowel |
| F2 / F3 bandwidth | 110 / 150 Hz | 141–239 / 186–438 Hz |
| Gains | one vector for all vowels | per vowel (6.2 dB mean deviation from that vector) |
| Nasal murmur poles | 270 / 1000 / 2200 Hz | 204 / 1480 / 2148 Hz (bw 110 / 162 / 420) |
| Nasal anti-formant | a 1 kHz constant | 822 Hz, the first null of the 3-way junction |

The gain vector is not pure physics: the parallel bank has no source tilt in it, so each measured amplitude is
tilted by `(F_i/F_1)^-gain_tilt_power` with `gain_tilt_power` (0.582) fitted once, across every vowel, against the
legacy table. That is the one calibration number; it exists so a preset keeps its voicing while every vowel still
gets its own measured amplitude. There is no tuned-by-ear step anywhere in this.

## 3. The knobs

`references/data/vocal-engine-data/defaults.json`, key `waveguide`:

| Key | Meaning |
|---|---|
| `mode` | `physical` or `table` |
| `tract_length_m`, `sections` | the tube the formants are solved in |
| `radiation.ka_max`, `losses.k0_per_m`, `losses.k1_s_per_m` | the loss model the widths are measured through (a starting value, calibrated by measurement: boundary-layer losses alone give 22–131 Hz widths, speech measures 50–300 Hz) |
| `geometry.*` | control points, bounds, curvature, scale pin, trust region, iterations, `tolerance_hz`, `blend_sigma_hz` |
| `gain_tilt_power` | the one gain calibration |
| `nasal.*` | velum fraction, pharynx/oral/nasal areas and lengths: what sets the poles and the zero |

`humming.antiformant_from_junction` (default `true`) switches the derived zero off in favour of
`humming.antiformant_hz`; `humming.antiformant_hz` itself stays as that override, and the gains, brightness and depth
of the hum remain config values because they are preset decisions about the singer, not properties of the tube.

## 4. Cost, and what to do about it

One geometry build per process: 0.7 s for the ten vowels of the table, cached by config signature. After that the
measured table is a dict lookup, and a 5-voice 11 s `render_choir` is +1.0 % (9.13 -> 9.22 s). A project that renders
one vocal phrase pays the 0.7 s; on a long session it is amortised.

## 5. Limits

- The renderer is a parallel bank of resonators, not the Kelly–Lochbaum network: tract zeros are approximated by one
  notch, so a nasal's null has a physical frequency but a simplified shape.
- The eigenproblem is a staircase of the taper, which is why a strongly tapered tube's F1 can sit ~4 % from the network.
- The gains are peak amplitudes with one calibrated tilt, not a full source-filter fit.
- **Nothing has been listened to.** Everything here is measured, and no measurement in this file says the result sounds
  like a person.

## 6. The source model, oversampling and syllables

- **Source model.** `source.model: "lf"` replaces the pulse with the Liljencrants-Fant model, shaped by one number,
  `rd`: 0.3 is pressed, about 1 is modal, 2.7 is breathy. Each register carries its own `rd`, blended across the
  passaggio like the other register values; `source.rd` (a number) overrides them for the whole voice. With `lf` the
  level-following tilt keeps one pole, because the model's return phase already is the source's roll-off. Measured:
  the first harmonic against the second goes from -4 dB at `rd` 0.3 to +19 dB at 2.7.
- **Oversampling.** `source.oversample` 2 or 4 makes the source at that multiple of the rate and decimates. At 1 kHz
  the energy that folds back between the harmonics drops by about 14 dB at 2 and 24 dB at 4. Default 1: the engine as
  it was.
- **Syllable shorthand.** A note may carry `"syl": "la"`: the longest onset in `consonants.inventory`, then one vowel
  or two (a diphthong), written out as the `consonant` and `vowel` keys. `"shai"` is `sh` + `["a", "i"]`. A note's
  own `consonant` or `vowel` wins. It is spelling for syllables, not a dictionary: an unknown syllable is an error.
- The LF source is the textbook model with Fant's regression from `rd` to its timing; the `rd` per register in
  `defaults.json` is a starting value, and neither model is fitted to a recorded singer.
