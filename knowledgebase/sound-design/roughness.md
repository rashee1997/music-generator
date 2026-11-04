---
id: roughness
title: Auditory roughness - what the sources measure
domain: sound-design
status: partly-sourced
sources: [https://www.mpi.nl/world/materials/publications/levelt/Plomp_Levelt_Tonal_1965.pdf, https://acousticslab.org/learnmoresra/moremodel.html, https://acousticslab.org/learnmoresra/moreroughness.html, https://zhenilo.narod.ru/main/students/Zwicker_Fastl.pdf, https://iem.kug.ac.at/fileadmin/03_Microsites/01_Kuenstlerisch_wissenschaftliche_Einheiten/01_Institute/Institut_17_Elektronische_Musik_und_Akustik/Projekte/Projekte_bis_2008/Publikationen/pub_avlpaper.pdf, https://www.iso.org/standard/34222.html, https://eclass.uoa.gr/modules/document/file.php/MUSIC101/Masking_Frequency_selectivity_and_the_Critical_Band.pdf]
used_by: [scripts/naturalness_check.py, docs/roughness_model.md]
updated: 2026-11-04
---

> **Not verified** in one place: every number below is labelled. `read in source` means the sentence or
> figure was read in the cited text; `standard result` means a textbook statement; `starting value` means a
> modelling choice this skill made and has not measured.

# Auditory roughness - what the sources measure

Roughness is the buzzing quality of partials close enough to beat inside one critical band. It is not
dissonance: dissonance adds cultural and harmonic expectation, roughness is the sensory part only.
Plomp and Levelt call the sensory part *tonal consonance*; their 1965 experiment is the origin of the
quarter-critical-band rule below.

## What roughness needs

| Property | Value | Source |
|---|---|---|
| Modulation rate that produces roughness | 15-300 Hz | read in source (Zwicker & Fastl, Ch. 11, p. 257) |
| Rate of maximum roughness, carrier >= 1 kHz | about 70 Hz | read in source (Zwicker & Fastl, Ch. 11, p. 259) |
| Rate of maximum roughness, carrier < 1 kHz | falls with carrier frequency, limited by critical bandwidth | read in source (Zwicker & Fastl, p. 259) |
| Reference sensation, 1 asper | 60 dB SPL, 1 kHz, 100% AM at 70 Hz | read in source (Zwicker & Fastl, p. 257) |
| Interval of maximum roughness | 25% of the critical bandwidth | read in source (Plomp & Levelt 1965, Fig. 9) |
| Interval of maximum roughness vs frequency | grows with frequency; a constant 30-40 Hz fits only 500-1000 Hz | read in source (Plomp & Levelt 1965) |
| Modulation above which roughness vanishes | about 300 Hz | read in source (Zwicker & Fastl; Vassilakis 2005) |

## Level

| Property | Value | Source |
|---|---|---|
| Roughness vs sound pressure level | a 40 dB level increase multiplies roughness by about 3 (about 1.2 dB of roughness per 10 dB of level) | read in source (Zwicker & Fastl, Fig. 11.4, p. 260) |
| Roughness vs degree of modulation | power law, exponent near 1.6; 25% modulation gives about 0.1 asper | read in source (Zwicker & Fastl, p. 258) |
| Audibility threshold | excitation below the absolute threshold contributes nothing | read in source (Daniel & Weber 1997, as described in Hoeldrich & Pfluger) |
| Equal loudness | a pair-sum model does not correct for it; the ear's sensitivity curve decides which partials can beat | read in source (Vassilakis model page: "The model does not adjust for equal loudness") |

The level effect is weak, not absent: a clash at `pp` is quieter-rough, not "not rough". Two sources
disagree on how weak: the Vassilakis intensity term `(Amin*Amax)^0.1` changes about 2% per 10 dB, while
Zwicker and Fastl measure about 12% per 10 dB. Vassilakis argues earlier models overestimate level; the
book measures it directly.

## Masking

| Property | Value | Source |
|---|---|---|
| Which partials mask | only components inside the same critical band contribute | standard result (critical-band masking; Lopez-Poveda, "Masking, the critical band and frequency selectivity") |
| Lower masking slope | -27 dB/Bark below the masker | read in source (Daniel & Weber 1997 model, `S_l = -27 dB/Bark`) |
| Upper masking slope | about -10.5 dB/Bark above the masker at 450-480 Hz, 64-70 dB | read in source (Daniel & Weber 1997 worked example: slopes -11.7, -10.5, -11.7 dB/Bark) |
| Upper slope vs level | grows with masker level (nonlinear) | read in source (Zwicker & Fastl, Sect. 4.2.1) |
| Masking bandwidth used by the model | 1 Bark filters, 47 overlapping bands | read in source (Daniel & Weber 1997) |

There is no published "X dB under the masker and it is inaudible". The masking curve is a slope in
dB/Bark, and it is asymmetric: masking spreads much further upwards than downwards.

## The pair model (the formula this skill uses)

Vassilakis (2001, 2005), as published on the SRA pages:

    R(pair) = X^0.1 * 0.5 * Y^3.11 * Z
    X = Amin * Amax
    Y = 2*Amin / (Amin + Amax)
    Z = exp(-3.5*s*df) - exp(-5.75*s*df)
    s = 0.24 / (0.0207*fmin + 18.96)

- `Z` is the Sethares (1998) kernel: it carries the register behaviour through `fmin` (read in source).
- `Y` is the degree of amplitude fluctuation: two partials at equal level are roughest (read in source).
- `X^0.1` is the weak intensity term described under Level (read in source).
- Only one of the three terms is a rational number that could be tuned: `0.5` normalises the pair weight.
- The published model sums over all pairs. This skill averages the three strongest pairs instead, because a
  sum grows with the number of parts and failed every 6+ part chord in the gate's own calibration
  (starting value: density control, not a published result).

## What the sources do not give

- No mood, genre or section-role effect on roughness. All cited experiments vary the stimulus only.
- No persistence threshold: roughness exists while the modulation exists. An analysis window of 1 s
  resolves 15-300 Hz modulation; the gate's separate three-frame persistence rule is
  this skill's rule, not a perceptual constant (starting value).
- ISO 226 gives equal-loudness contours for pure tones, not for a partial inside a complex tone; it is
  used here only as the reason to weight each partial against the hearing threshold. The exact ISO 226
  arithmetic is not implemented (standard is paywalled; only definitions were read).
