---
id: sfx-formulas
title: Formulas behind sound_model.py: excitation, resonator, event process, texture statistics
domain: sound-design
status: unverified
sources: []
used_by: [AGENTS.md, references/sound-design/sound-effects.md, scripts/sound_model.py]
updated: 2026-11-04
---

> **Not verified.** These values are a starting point from practice, not a measurement.
> Cite a source before presenting one as established, and say "starting value" when a piece uses one.

# Formulas behind `sound_model.py`: excitation, resonator, event process, texture statistics

Every sound effect and ambience in the skill is a stack of voices: excitation -> resonator -> time process -> space. This note holds the
formulas each part uses and says where each comes from. **Read-status is stated per row**: "paper text read" means the formula was read in the
paper's full text during this work; "standard" means a textbook result written from knowledge and not re-checked against a source here,
which the research step of a project should confirm before relying on it for a published piece.

## 1. Resonator: modal bank

Response of an object to an impulse at location k (paper text read; van den Doel, Kry, Pai, *FoleyAutomatic*, SIGGRAPH 2001, eq. 1):

    y_k(t) = sum_n  a_nk * exp(-d_n * t) * sin(2 pi f_n t),     t >= 0

`f_n` are mode frequencies, `d_n` decay rates (1/s), `a_nk` gains that depend on where the object is struck. Frequencies and dampings come
from geometry and material; the gains from the mode shapes. Only the gains change with strike position.
Decay time to -60 dB: `T60_n = 6.91 / d_n`. A material usually damps high modes faster: `d_n = d_0 + d_1 * f_n` (standard).

Mode-frequency ratios (standard; check in a project's research for the exact object):

| Object | Ratios f_n / f_1 |
|---|---|
| Ideal string, tube open at both ends | 1, 2, 3, 4, ... |
| Tube closed at one end | 1, 3, 5, 7, ... |
| Free-free bar (xylophone bar, rod, metal strip) | 1, 2.757, 5.404, 8.933, 13.34 |
| Circular membrane (drum head) | 1, 1.594, 2.136, 2.296, 2.653, 2.918 |
| Glass, bell, plate | inharmonic: take the ratios from a measured recording (`ambience_reference.py measure`), not from a law |

## 2. Excitation

| Excitation | Formula | Status |
|---|---|---|
| Impact pulse | force `F(t) = 1 - cos(2 pi t / tau)` for `0 <= t <= tau`, else 0. `tau` is the contact time: a hard contact has a short `tau`, a soft one a long `tau`. The magnitude is the energy transferred. The resonator is driven by this force. | paper text read (FoleyAutomatic section 4.1). The paper names Hertz contact as the more detailed model; it is not used here |
| Scraping and sliding | Surface profile = fractal noise with power spectrum proportional to `omega^beta`, passed through a reson (resonant) filter whose centre frequency scales with contact velocity. Roughness `beta` relates to fractal dimension `D = beta / 2 + 2`. A narrow reson sounds pitched; a wide one sounds random. | paper text read (FoleyAutomatic, scraping). The sign convention of `beta` follows the paper (1/f^beta noise is the common reading; a project checks it by measuring the spectrum slope) |
| Rolling | A gammatone filter (order 2) driven by noise has the same spectrum as a reson driven by noise with envelope `S(omega) = 1 / sqrt((omega - rho)^2 + d^2)`, where `rho`, `d` are the mode frequency and damping. Better than a pure modal bank for rolling. | paper text read (FoleyAutomatic, rolling, citing an earlier observation) |
| Source-filter view of scraping and rolling | Excitation (roughness, speed) and resonator (object) are separate parts, so any excitation can drive any resonator. | Agarwal et al., DAFx 2021, abstract and the overlapping text read |
| Noise with a spectral slope | white, pink (-3 dB/oct), brown (-6 dB/oct), or band-limited | standard |
| Turbulence | noise multiplied by a slow flow envelope | standard |
| Periodic pulse train | saw or pulse at `f0` with jitter and a pitch glide | standard |
| Burst | short broadband pulse with a fast exponential decay (blast, gunshot) | standard |

Warning from the same paper: one model for too wide a category (from contact sounds to animal cries) gave poor sounds. This is why the engine
is a set of small parts chosen per sound, and why speech, singing and named animal calls stay with their own primitives.

## 3. Time process (when events happen)

| Process | Rule | Status |
|---|---|---|
| Single | one event at `t0` | - |
| Periodic with jitter | gap `T * (1 + sigma * N(0,1))` | standard |
| Poisson | gaps `-ln(U) / rate` (exponential); events independent | standard |
| Renewal with gamma gaps | shape `k`, mean `1/rate`; `k > 1` is more regular than Poisson, `k < 1` is clumpier | standard |
| Clustered (Neyman-Scott) | cluster centres by Poisson; each centre has `m` events spread by `sigma_t` | standard |
| Bouncing | gaps `t_{n+1} - t_n = e * (t_n - t_{n-1})`, level `e^n`; `e` is the restitution | standard (constant restitution, free flight) |
| Sequence | explicit list of times and levels | - |

## 4. Parameter laws

| Law | Formula | Status |
|---|---|---|
| Size to pitch | frequency scales as `1 / size` for geometrically similar objects | standard |
| Minnaert bubble | `f = 3.26 / r` Hz, `r` in metres (resonance of an air bubble in water) | standard; the NASA page quotes 13 to 25 kHz for small rain bubbles, which agrees for radii of about 0.13 to 0.25 mm |
| Raindrop sizes | Marshall-Palmer: `N(D) = N0 * exp(-Lambda * D)`, `N0 = 8000 m^-3 mm^-1`, `Lambda = 4.1 * R^-0.21 mm^-1` (`R` in mm/h) | standard |
| Drop impact on a smooth surface | spectral peak near 300 Hz reported | search snippet of Beacham 2020, not read in full |
| Rain noise on roofs | building-acoustics models cover 100 to 5000 Hz | search snippet of Griffin 2012, not read in full |
| Speed to level and brightness | level in dB rises with speed, and the filter cutoff rises with speed | standard |

## 5. Slow control

Envelopes (attack, hold, decay), LFOs, and a bounded random walk for gusts and swells: the Ornstein-Uhlenbeck process
`x_{k+1} = x_k + theta * (mu - x_k) * dt + sigma * sqrt(dt) * N(0,1)`, mapped to a gain or a cutoff (standard).

## 6. Texture statistics (the target for any ambience)

McDermott and Simoncelli, *Neuron* 71, 2011 (paper text read). The model:
1. a bank of band-pass ("cochlear") filters, 32 channels on a log-frequency axis, gives sub-band signals;
2. the envelope of each, with a compressive nonlinearity, gives `s_k(t)`;
3. statistics of the envelopes: the first four normalized moments: mean `M1`, variance divided by squared mean `M2`, skew `M3`, kurtosis `M4`;
   variance, skew and kurtosis measure **sparsity** (infrequent events that make bursts);
4. cross-band envelope correlations `C1` (broadband events such as crackles and claps raise them);
5. the envelopes are filtered by a bank of modulation filters (log-spaced); the power in each modulation band `M` is a statistic;
6. correlations across modulation bands `C2` (for example, onsets that are common to several bands).

Per-band statistics alone failed to give convincing textures; the cross-band correlations were needed. The engine measures a reduced version
(about 12 bands, moments, C1, a few modulation bands) so that it runs on a CPU laptop, and says plainly that it is a subset of the paper's set.

## 7. Where each part is used

| Part | Used for |
|---|---|
| Modal bank + impact pulse | knocks, glass, bells, metal, wood, bounces, ticks, drips |
| Fractal noise + reson | scrapes, creaks, sliding, engines (with a periodic pulse excitation) |
| Noise + flow envelope | wind, steam, surf |
| Poisson events on a modal bank | rain on surfaces, crackle, hail, boiling |
| Clusters | rain in gusts, applause, bubbling |
| Texture statistics | a target to match for any bed that has no clean physics |

## 8. Material to mode frequency (phys_core/geometry.py)

The same oak is a dull thud as a thick beam and a bright knock as a thin board, so frequency comes from the material
*and* the geometry, not from a material table.

| Shape | First mode | Status |
|---|---|---|
| Free-free bar | `f1 = (4.730^2 / 2*pi) * (h / L^2) * sqrt(E / (12 rho))` | standard (Euler-Bernoulli bending, first free-free root 4.730) |
| Clamped plate | `f1 = 0.469 * (h / a^2) * sqrt(E / (rho (1 - nu^2)))` | standard form, coefficient rounded |
| Tube, open / closed at one end | `c / (2 L)` / `c / (4 L)`, `c = sqrt(E / rho)` | standard |
| String | `c / (2 L)` | standard |

Decay of a mode from the material's loss factor: `T60 = 2.2 / (f * eta)` (standard for a lightly damped resonator).
High modes decay faster as `T60_n = T60_1 * ratio_n^(-damp_exp)` (standard; `damp_exp` is the fit).
A scene always overrides with `f1_hz`, because a real branch, leaf or drum head is tensioned and irregular.

## 9. Porous and fibrous absorption (phys_core/resonate.py)

Delany-Bazley-Miki, formulas read from the APMR reference (https://apmr.matelys.com/PropagationModels/MotionlessSkeleton/DelanyBazleyMikiModel.html):

    X   = f / sigma                                            (sigma: flow resistivity, N s/m4)
    k   = (w/c) * ( 11.41 X^-0.618 + i (1 + 7.81 X^-0.618) )
    gain over thickness h  =  exp(-|Im k| h)

Status: paper formulas read; validity range stated there as X between about 0.01 and 1, and it is applied as a
zero-phase frequency-domain gain. It gives leaves, fabric, soil and foam a real top-end absorption instead of an EQ.

## 10. Contact time, fracture and gait (phys_core/excite.py, fracture.py, gait.py)

| Model | Rule | Status |
|---|---|---|
| Hertz contact time | `tau ~ 2.94 (5 m / (4 n))^(2/5) v^(-1/5)`, implemented as `tau = 2 ms * m^0.4 * (1e7/n)^0.4 * v^-0.2` | exponents are physics; the 2 ms reference is an ESTIMATE |
| Impact energy | `E = 0.5 m v^2`; a break radiates `0.35 E` | energy is standard; the 0.35 sink fraction is an ESTIMATE |
| Brittle fracture | many near-simultaneous crack impulses (8-90), very short, high modes, many small fragments | event-graph shape after Zheng & James, SIGGRAPH 2010 (project page read); counts and times ESTIMATE |
| Fibrous fracture | fewer impulses (4-30) spread over a longer time, longer contact time, few larger fragments | same source for the shape; split is ESTIMATE |
| Gait | alternating contacts whose force follows a ground reaction curve; walk has a heel spike and a push-off, a run is one broad peak | Turchet, Serafin, Dimitrov, Nordahl, DAFx-10 (abstract and figures); curve shape ESTIMATE |
| Granular | Poisson contact stream, lognormal grain sizes, each grain's own mass and contact time | Marko, ACM SPY 2013 (abstract); statistics standard |

## 11. Calibration

Sound pressure is proportional to the square root of radiated energy: `amplitude = sqrt(E / E_ref)`. One constant
(`REFERENCE_J`) for the whole engine, so a scene that releases 4x the energy is 6 dB louder and nothing hides a
per-sound fudge. `normalize` (`energy` default, `none`, `peak`, `rms`) is a declared choice; `peak` and `rms` destroy
intensity relationships and are never the default.