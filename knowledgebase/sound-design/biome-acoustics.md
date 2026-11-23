---
id: biome-acoustics
title: Acoustic biomes - the medium, weather micro-physics, creature sources and niche partitioning
domain: sound-design
status: partly-sourced
sources: [https://acoustics.org/pressroom/httpdocs/153rd/petculescu.html, https://acousticstoday.org/issues/2007AT/Jan2007/files/basic-html/page19.html, https://oro.open.ac.uk/26571, https://oro.open.ac.uk/64846, https://wikipedia.com/wiki/Minnaert_resonance, https://science.nasa.gov/earth-science/oceanography/listening-to-raindrops/, https://arxiv.org/pdf/1907.12812]
used_by: [scripts/phys_core/medium.py, scripts/biome/physics.py, scripts/biome/generators.py, scripts/biome/sources.py, scripts/biome/tract.py, scripts/biome/ecology.py, scripts/env_rows.py, docs/PSYCHOACOUSTICS.md]
updated: 2026-11-23
---

> **Not verified** in one place: `computed` was checked numerically in this skill's tests; `read in source` means the
> text was read at the cited URL on 2026-11-23, search snippets included; `from memory` is the standard form of a result
> that was not re-read; `starting value` is a modelling choice of this skill, not yet measured.

# Acoustic biomes

A place is described by a medium, mechanisms that make sound in it, animals, and the rules by which animals share time and
the score's open pockets. Nothing below names a place or a species.

## The medium

Bulk state of an ideal gas: `c = sqrt(gamma R T / M)`, `rho = p M / (R T)`, impedance `Z = rho c`.

| Medium and state | c, m/s | rho, kg/m3 | Z, rayl | Status |
|---|---|---|---|---|
| Earth air, 293.15 K, 101325 Pa | 343.2 | 1.204 | 413 | computed |
| Mars, CO2, 210 K, 610 Pa | 226.2 | 0.0145 | 3.5 | computed; the state is a starting value |
| Titan, N2, 94 K, 146.7 kPa | 198.0 | 5.24 | 1037 | computed; measured surface c is 194.0 m/s, 2.1 % lower (read in source: Huygens sound-speed pages) |
| Venus surface, CO2, 735 K, 9.2 MPa | 408.2 | 66.3 | 27045 | computed; the state is a starting value |

Absorption of any gas, Np/m: `alpha(f) = a_cl f^2 + sum_i (2 mu_i / c) (f^2 / f_r,i) / (1 + (f / f_r,i)^2)`, with `mu_i` the
peak absorption per wavelength of relaxation process `i`. ISO 9613-1 is this law with two processes (O2 and N2); written this
way it reproduces the standard's 4.66 dB/km at 1 kHz and 158.84 dB/km at 10 kHz (computed). The classical term of a gas is
`(2 pi)^2 / (2 rho c^3) * eta * (4/3 + (gamma - 1) / Pr)`; for air it is 24 % under the standard's coefficient (computed).

Relaxation matters far more on Venus and Mars than on Earth and Titan, and Titan carries sound best (read in source:
Petculescu and Lueptow, Icarus 186, 2007, through press and Acoustics Today summaries). No relaxation frequency or strength
for CO2 or N2/CH4 was read; a preset that needs them says ESTIMATE.

Energy transmission between two media: `T = 4 Z1 Z2 / (Z1 + Z2)^2`. Air to water is -29.5 dB; Titan air to a liquid sea at
`c = 1400 m/s`, `rho = 450 kg/m3` (starting values) is -21.8 dB (computed).

Level of a source of radiated power `W` at `r`: `p_rms = sqrt(Z W / (4 pi r^2))`. The same power gives 20.7 dB less
pressure in Mars air than in Earth air (computed).

## Mechanisms

**Vortex shedding.** Tone `f = St(Re) U / d`, `Re = rho U d / eta`. Laminar shedding for `49 < Re < 190`:
`St = 0.2684 - 1.0356 / sqrt(Re)` (from memory, Fey, Koenig and Eckelmann 1998). Subcritical for `250 < Re < 2e5`:
`St = 0.212 (1 - 21.2 / Re)` (from memory, Roshko 1954). Between 190 and 250 the two are joined linearly; above `2e5` the
Strouhal number is taken as 0.2 (starting value); below 49 there is no regular shedding. A 5 mm twig at 8 m/s in Earth air
sings at 336 Hz; a 5 mm spire at 2 m/s in Titan air at 85 Hz; a 5 mm cylinder at 20 m/s in Mars air has `Re = 132` and
falls in the laminar law (all computed, density and viscosity of the non-Earth gases are starting values).

**Dipole power.** `W = k rho U^6 A / c^3` for a body of frontal area `A` in a flow `U` (from memory, Curle 1955); the pressure
follows `U^3`, and a thicker atmosphere radiates more at the same wind. `k` is a starting value.

**Fall speed.** `v = sqrt(8 g D (rho_p - rho_g) / (3 Cd rho_g))`. A 4 mm water drop with `Cd = 1.1` falls at 8.9 m/s on Earth;
a 4 mm methane drop with `Cd = 0.6` falls at 1.43 m/s at Titan's gravity of 1.352 m/s2 (computed; the drag coefficients are
starting values, because real drops deform).

**Drop sizes.** Exponential, slope `4.1 R^-0.21` per mm for a rate `R` in mm/h (from memory, Marshall and Palmer 1948). The drops
that arrive are weighted by their fall speed, and the rate is fixed by the volume that lands.

**Bubbles.** A gas bubble of radius `R` in a liquid rings at `f = sqrt(3 gamma p / rho_l) / (2 pi R)` (read in source: the
Minnaert form). `f R` is 3.29 Hz m for air in water at 1 atm and 5.89 Hz m for nitrogen in liquid methane at Titan's
pressure (computed). The same law gives the pitch of a swim bladder, which rises with depth: 657 Hz at the surface, 1587 Hz at 50 m
and 2963 Hz at 200 m for a 5 mm radius (computed).

**Singing dunes.** Pitch `f = k sqrt(g / d)` for grains of diameter `d` (from memory, Andreotti's dune work); `k = 0.4` is a
starting value that gives 89 Hz for 0.2 mm grains on Earth and 54 Hz on Mars (computed).

## Creatures

A call is a source and a filter. Sources: a pulse train of the Liljencrants-Fant model with jitter, a period-doubled
subharmonic and chaos from a logistic map (mammal folds); two independent syringeal oscillators with their own contours, FM and
AM (birds); teeth struck at a rate that follows temperature, ringing a plate (stridulation; Dolbear's law is `rate_per_k`);
damped clicks at a changing interval; a bladder driven by pulses.

A tract is segments `[length, area]` and closed side branches. Its transfer function is the chain-matrix product with
`U_mouth / U_source = 1 / D`, `D` the lower-right element; a closed side branch is a shunt admittance
`j (A_b / rho c) tan(k L_b)`. The resonances of a two-tube tract (0.17 m at 2 cm2 then 0.17 m at 8 cm2) are 357, 654, 1365 and
1662 Hz in air and fall by the ratio of the speeds of sound in another medium (computed, within 0.7 %).

Fitting that response with linear prediction fails: order 12 puts the first resonance at 782 Hz and order 24 at 542 Hz where
it is 357 Hz, and order 40 needs poles at radius 0.9997 (computed). The skill takes the peaks of the response and builds one
two-pole resonator at each. The formant positions are exact; the spectral shape of the parallel bank is only approximate (a
log-spectrum correlation of 0.73 over 0-6 kHz, computed).

## Sharing time and the score

Niche overlap of two animals on third-octave band shares `p_v(b)`: `D = 1 - 1/2 sum_b |p_v(b) - p_w(b)|` (Schoener; 1 for the
same band, 0 for disjoint ones). The acoustic niche hypothesis says species adjust their calls so they are isolated in frequency
and in time (read in source: search summaries of the soundscape-ecology literature; the origin year differs between sources,
1987 or 1993).

A score occupies time-band cells through its notes, their harmonics up to 5 kHz, and drums across every band; a figure role is
protected with a margin of one band at 3 dB and two at 6 dB (starting values). A call that needs a pocket looks for a cell the
score occupies under 0.35 and gives up after 8 tries except with probability 0.05 (starting values). In a synthetic test,
pocket-aware placement cut overlap with occupied cells from 0.52 to 0.06 (computed on a toy grid, not evidence about real
pieces).

## Decorrelation

Two copies of one signal through different phase responses cannot be decorrelated where the signal is tonal: rain on a plate
rings at its modes. Independent emitters, each from its own random stream, are uncorrelated by construction. Measured mean
interchannel `|correlation|` over 250 Hz-8 kHz: rain 0.36 and wind 0.63 through an allpass cascade, 0.00 and 0.01 through
independent emitters (computed).
