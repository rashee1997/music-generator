---
id: virtual-ears
title: Virtual ears - cochlear, hair-cell and adaptation model for QA
domain: sound-design
status: partly-sourced
sources: [https://arxiv.org/html/2404.17490v1, https://raw.githubusercontent.com/google/carfac/master/LICENSE, https://github.com/tomstoll/PyZBC2014, https://github.com/mrkrd/cochlea]
used_by: [scripts/auditory.py, scripts/ear_rows.py, knowledgebase/sound-design/roughness.md, docs/PSYCHOACOUSTICS.md]
updated: 2026-11-23
---

> **Not verified** in one place: `read in source` means the text was read at the cited URL on 2026-11-23;
> `starting value` is a modelling choice of this skill, not yet measured; `from memory` was not re-read.

# Virtual ears

A peripheral auditory model turns a waveform into a neural activity pattern (NAP) per frequency channel. The
gate uses it where a static STFT cannot see: level-dependent compression, neural adaptation (fatigue), and the
envelope modulation that produces roughness.

## Stages and what each one adds

| Stage | Model | Adds over an STFT gate | Status |
|---|---|---|---|
| Middle ear | band-emphasis filter, the inverse of the absolute threshold curve | level reaching the cochlea is not flat in frequency | starting value |
| Cochlear filtering | cascade of asymmetric resonators, channels at ERB spacing | each channel passes the signal through all channels above it | read in source (CARFAC v2 paper, arXiv 2404.17490) |
| Fast-acting compression | a level-dependent damping per channel (automatic gain control) | a loud partial lowers the gain of its neighbours; the cochlea is compressive | read in source (same paper) |
| Hair cell | half-wave rectification, saturation, low-pass | phase locking falls away above about 1-3 kHz | from memory (Lyon) |
| Adaptation | divisive gain with two time constants, about 10 ms and 60 ms | a sustained sound is perceived less strongly than its onset; the depleted fraction is a fatigue proxy | starting value |

ERB rate: `21.4 * log10(0.00437 f + 1)` (Glasberg & Moore 1990), the same formula `scripts/spatial_gate.py` uses.

## Quantities derived from the NAP

| Quantity | Definition | Status |
|---|---|---|
| Modulation roughness | power of the NAP envelope between 30 and 150 Hz, per channel | band from `roughness.md` (15-300 Hz range, maximum near 70 Hz: read in source, Zwicker & Fastl) |
| Pitch salience | height of the highest peak of the summary autocorrelation of the NAP | from memory (Meddis & Hewitt 1991); threshold is a starting value |
| Resolvability | share of harmonic energy at harmonic numbers below about 8-10 | from memory (Plack, Bernstein & Oxenham); starting value |
| Interaural correlation | normalised cross-correlation of left and right NAP, lags within 1 ms | standard result |
| Fatigue | mean depleted fraction of the adaptation store over a 2-5 s window | starting value, no published pass mark for music |

## Reference models, and why they are not run on a whole piece

| Model | Licence as stated on its package page | Use here |
|---|---|---|
| CARFAC v2 | Apache-2.0, LICENSE file read at github.com/google/carfac on 2026-11-23. The paper lists NumPy and JAX ports; the NumPy path was not found at the repository's default branch on that date | structure followed; code written from the paper, nothing vendored |
| Zilany-Bruce-Carney 2014 | wrapper PyZBC2014 states AGPL-3.0, wrapper `cochlea` states GPL-3+ (package pages) | calibration reference for short probes only; not benchmarked here |
| Verhulst 2018 | not confirmed | not used |

Not verified: runtime of the reference models, and every threshold above marked starting value.
