---
id: layout-3-2
title: Three-front loudspeaker layout with two low-frequency channels
domain: sound-design
status: partly-sourced
sources: [https://www.itu.int/rec/R-REC-BS.775, https://www.itu.int/rec/R-REC-BS.2051, https://www.aes.org/e-lib/browse.cfm?elib=13988]
used_by: [knowledgebase/sound-design/virtual-speaker-qa.md]
updated: 2026-11-23
---

> **Not verified** in one place: `read in source` means read at the cited page; `from memory` was not re-read;
> `starting value` is this skill's modelling choice.

# L / C / R with two low-frequency channels ("3.2")

## What is and is not a standard

| Claim | Status |
|---|---|
| Front loudspeakers at -30, 0, +30 degrees are the front of the five-channel reference arrangement (BS.775) | from memory |
| BS.775 two-channel downmix: centre goes into both channels at -3 dB (0.7071) | from memory; the repo's `stereo_bs775` layout carries the coefficients |
| BS.2051 has no three-front layout; its only two-LFE system is the 22.2 family (LFE1, LFE2) | from memory; confirm against the recommendation before any delivery note says otherwise |
| IAMF loudspeaker layouts have no three-front layout with two LFE | from memory |

Consequence: this layout is project-defined. A delivery note must call it a project layout and not claim
conformance to a broadcast format.

## Bass management

| Fact | Value | Status |
|---|---|---|
| Linkwitz-Riley 4th order: low-pass and high-pass are in phase and each -6 dB at the crossover; their sum is flat | LR4 | standard result (Linkwitz 1976); the repo's `bass.py` uses it |
| Crossover | 80 Hz | the repo's shipped 5.1 value, starting value |
| Below about 80 Hz interaural cues are small, so bass is poorly localised | | from memory |
| Several subwoofers reduce the spatial variance of the low-frequency response in a room | | from memory (Welti & Devantier, JAES 2006); size of the gain depends on the room |
| Axial and oblique mode frequencies of a rectangular room: `f = (c/2) sqrt((nx/Lx)^2 + (ny/Ly)^2 + (nz/Lz)^2)` | | standard result (Kuttruff) |

A file cannot know the room. Sub delay and polarity against the mains are measured on site; the layout carries
them as inputs and the report lists them as not verified for the room.
