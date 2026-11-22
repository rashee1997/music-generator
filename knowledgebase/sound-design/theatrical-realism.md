---
# Not verified in full: the sources were read as search-result excerpts. See the note under the header.
id: theatrical-realism
title: The eight acoustic qualities that separate a theatrical mix from a clean synthetic one
domain: sound-design
status: partly-sourced
sources: [https://www.phys.unsw.edu.au/music/people/publications/Fletcheretal1999.pdf, https://conforg.fr/isma2014/cdrom/data/articles/000088.pdf, https://doi.org/10.1121/1.5053113, https://www.speech.kth.se/publications/pdfs/schoonderwaldt_e.pdf, https://webspace.eecs.qmul.ac.uk/s.e.dixon/phd/MagdalenaChudy-PhD-Thesis.pdf, http://pub.dega-akustik.de/ISMA2019/data/articles/000093.pdf, https://kth.diva-portal.org/smash/get/diva2:1416134/FULLTEXT01.pdf, https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2014.00645/full, http://viennatalk2015.mdw.ac.at/proceedings/ViennaTalk2015_submission_55.pdf, https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2014.01115/full, https://pmc.ncbi.nlm.nih.gov/articles/PMC2677334, https://link.springer.com/article/10.3758/s13414-015-1015-1, https://www.cmu.edu/dietrich/psychology/shinn/publications/pdfs/2000/2000ieee_shinn.pdf, https://docs.jmrp.io/phonometry/environment/propagation/outdoor-propagation, https://www.audiolabs-erlangen.de/content/05_fau/professor/00_mueller/03_publications/2016_DriedgerMueller_TSMOverview_AppliedSciences_ePrint.pdf, http://recherche.ircam.fr/anasyn/schwarz/da/specenv/3_3Spectral_Envelopes.html, https://repositori.upf.edu/server/api/core/bitstreams/1405726f-b26a-46a0-b7b2-00d2ea320af5/content]
used_by: [references/mixing/theatrical-realism.md, scripts/realism_report.py]
updated: 2026-11-22
---

> **Not verified in full.** The sources were read as search-result excerpts in the session that wrote this file, not
> as complete papers. A figure marked `per source` is what the source's excerpt states; `starting value` is a
> working threshold for `scripts/realism_report.py`, not a measurement of any room or instrument. Cite the primary
> paper before presenting a number as established.

# The eight acoustic qualities of a theatrical mix

A clean synthetic mix can pass every balance, loudness and masking row and still read as generated, because it is
missing the couplings a real room and a room full of players impose. These are the eight, with the measured
evidence and the working threshold each one is currently checked against. The rules that use them are in
`references/mixing/theatrical-realism.md`; the measurements are `scripts/realism_report.py`.

## 1. Timbre changes with loudness

| Fact | Basis |
|---|---|
| A brass note's spectral centroid rises as the dynamic rises; a trumpet's high-frequency slope is about -30 dB/octave at a low level and -10 dB/octave at a high one, and the upper transition (2-3 kHz) moves up with level | per source: Fletcher et al. 1999, trumpet C4 |
| The enrichment during a crescendo is dominated by nonlinear propagation inside the bore; conical instruments such as the tuba enrich more slowly and may never reach the brassy timbre | per source: ISMA 2014 |
| A bowed string's spectral centroid rises with bow force and from pp to f; on the low strings bow force is the strongest control of centroid | per source: Schoonderwaldt 2009; Chudy 2016 |
| At a high dynamic the partials stand further above the wind/bow noise floor, so spectral flatness falls; listeners use that and attack slope to judge dynamic strength | per source: JASA 2018 |

A sampled instrument with one velocity layer maps velocity to gain only, so this coupling is absent. Working
figure: loud frames at least 0.8 dB brighter in centroid and 0.5 dB richer in 2-8 kHz than quiet frames
(`starting value`).

## 2. Ensemble imperfection

| Fact | Basis |
|---|---|
| Small violin sections are a few cents apart: 2 violins had per-note standard deviations of 0-12.8 cents, 3 violins 0.6-7.4 cents, 4 violins about 5 cents | per source: ISMA 2019 |
| A choir section is tolerated at a fundamental-frequency standard deviation of 14 cents, though listeners preferred zero scatter | per source: Ternstrom 1993, summarised in the KTH choir-acoustics overview |
| Between-player asynchrony in professional ensembles is typically 20-50 ms, with standard deviations of 24-73 ms; a string trio measured 49 ms SD at 79 bpm, a wind ensemble 32 ms at 88 bpm | per source: Rasch, summarised in Frontiers 2014 |
| A string quartet's mean absolute asynchrony ranged from 20 to 114 ms depending on the exercise; melody lead is about 10-20 ms | per source: ISPS string-quartet study; Frontiers 2014 |
| Ensemble members are not locked to one grid: mean pair asynchrony can be under 15 ms while its SD is around 20 ms | per source: Frontiers 2014 |

Working figure: a section part declares 2-8 players, each with a fixed offset of about +/-5 cents, +/-10 ms and
+/-3 MIDI velocity, plus per-note jitter (`starting value`). A solo declares none.

## 3. Register and transient consistency

| Fact | Basis |
|---|---|
| Transposing a sample by resampling scales the spectral envelope along with the partials, so formants move; the result is heard as an unnatural, thinned or "glass" register | per source: Driedger & Muller 2016; IRCAM spectral-envelope notes |
| Shifting the formants by a fifth is enough to make the change clearly perceptible; formant-preserving transposition is a known correction | per source: MDPI 2016 singing-voice study |
| Repeated percussion hits are not identical and should not be: hi-hat strokes sat 2-26 ms ahead of the pulse, and listeners preferred natural asynchronies under 19 ms over a fully quantised version | per source: jazz-trio synchronisation study, PMC 2017 |

Working figure: consecutive attacks at a comparable level should not share one 60 ms spectral shape; similarity
at or below 0.995 (`starting value`). High-register sampled notes need a register correction rather than a
global tilt; that correction is planned, not shipped.

## 4. Close detail against hall depth

| Fact | Basis |
|---|---|
| Direct sound falls about 6 dB per doubling of distance; in a small auditorium the reverberant level fell only about 1 dB per doubling, which is why the direct-to-reverberant ratio falls with distance | per source: auditory-distance review, Springer 2015 |
| The direct-to-reverberant ratio is a distance cue in its own right; discrimination thresholds are 5-6 dB over 0-20 dB, and about 2.4 dB near 0 dB | per source: JASA 2006 |
| For lateral sources within a metre, the near-ear direct-to-reverberant ratio changes at about -25 dB per log10 unit of distance | per source: Shinn-Cunningham 2000 |

Working figure: a master's direct-to-reverberant ratio, measured as the dry-stem sum against the master minus
that sum, should sit between -6 and +18 dB: detail in front of a room, not inside it (`starting value`). A send
that dips 2-3 dB only during an attack keeps the tail while letting the front through (`starting value`).

## 5. Low-mid clarity against sub authority

| Fact | Basis |
|---|---|
| Mixing practice puts "mud" at 200-500 Hz, worst around 250-400 Hz, and attributes it to many sources sharing the region rather than to one source | practice, not a measurement: mix-engineering sources |
| A subwoofer band (roughly 20-80 Hz) carries physical weight with little pitch information; the ear localises weight in the low-mids, where masking is strongest | reasoned from masking behaviour, `starting value` |

Working figure: the 180-450 Hz band should stay below the 500-2000 Hz band and should not grow faster than the
20-80 Hz band into a peak (`starting value`). The measurement is in `realism_report` dimension 5.

## 6. Radial distance realism

| Fact | Basis |
|---|---|
| ISO 9613-1 at 20 C and 50 % relative humidity gives about 9.89 dB/km at 2 kHz, 29.67 dB/km at 4 kHz and 105.29 dB/km at 8 kHz | per source: ISO 9613-1 tabulation |
| Over 10 m that is about 0.30 dB at 4 kHz and 1.05 dB at 8 kHz; over 30 m, 0.89 dB and 3.16 dB | calculated from the coefficients above |
| Within a metre the direct pressure no longer follows inverse square, and the two ears hear different distances (near-field divergence) | per source: Shinn-Cunningham 2000 |

Working figure: a source beyond 4 m uses the ISO model (temperature and humidity, or an explicit decision not
to); the predicted 4 kHz loss is `0.02967 x (distance - 1)` dB (`per source`, ISO).

## 7. Openness during peak density

No direct measurement was found for "air at the peak" in a music mix. The behaviour is consistent with two known
mechanisms: upward spread of masking (a loud low-mid masker raises the threshold of higher bands) and a reverb
return that is low-passed or limited at the loudest moment. Working figure: the 8-16 kHz share of the programme
should not fall by more than 1 dB at the loudest 10 % of frames (`starting value`, reasoned).

## 8. Macro phrase breathing

| Fact | Basis |
|---|---|
| Ensemble tempo excursion was 7.14 % in a mechanical condition, 8.45 % normal and 9.59 % exaggerated; loudness excursion was 15.3-23.4 dB | per source: ISPS collective-performance study |
| Phrase-final lengthening is a stable expressive device, but its size varies between performances of the same piece | per source: Frontiers 2016 |
| Conductor-to-ensemble offset is large and variable (mean around -31 ms in wind bands, -51 ms in orchestras, SD near 95 ms), so a fixed offset is not a model of conducted timing | per source: conductor-gesture study, PMC 2020 |

Working figure: bar-scale tempo deviation of 1-8 % over the body, excluding the written final ritardando, and a
60-120 ms collective breath before a harmonic turn (`starting value`).

## What is not claimed

These are couplings and thresholds, not a recipe for a good cue. The report says a mix has the structure; it
cannot say the theme is memorable, the orchestration is idiomatic or the room is the right room.
