# Research & plan: Immersive 3.3, universal data-driven acoustic biomes

Status: DESIGN ONLY. No pipeline, preset or test file was changed; this report is the only file added. Date: 2026-11-23.
Goal: any real or fictional place, generated only from JSON, CPU only (`numpy`/`scipy`), under 200 MB of overhead,
coupled to the `hoa_bus`, the score and the `ear.*` rows.

Evidence labels (as in `reports/research_immersive_3_2_virtual_ears.md`): **[repo]** read in this repo, file and line
given; **[measured]** computed or timed in this session (the scripts are in §8); **[lit]** from a search snippet or a
paper title I could not open in full, so verify before it goes into a knowledge-base file; **[start]** a starting value
with no source yet (AGENTS rule 16 needs the label on the same line as the number); **ESTIMATE** a value from general
knowledge that a research note must replace.

## 0. Findings that change the brief

1. **The air model is a closed Earth model, but the formula generalises exactly.** ISO 9613-1 is a classical term plus two
   single-relaxation terms. Rewriting each relaxation as `(2 mu / c) (f^2 / f_r) / (1 + (f/f_r)^2)` (mu = peak absorption
   per wavelength, Np) reproduces `airabs.alpha_db_per_m` to the printed digit at 1 kHz (4.66 dB/km) and 10 kHz
   (158.84 dB/km) [measured, §2.1]. So a `medium` block can carry *relaxations as data*, and Earth air becomes one
   instance (its `f_r` and `mu` computed from T, humidity, pressure) instead of a special case. Mars and Titan need their
   own relaxation numbers, which I could not get from open sources (§2.1); they stay ESTIMATE until a research note
   supplies them.
2. **Six modules hard-code 343 m/s** (list in §1.2) and three modules each own a separate absorption path
   (`environment.py`, `phys_core/propagate.py`, `spatial_engine/hoa.py`). A medium that changes `c` must reach all of them,
   so the medium has to be one object that every module reads. This is the core refactor.
3. **Memory, not CPU, is what breaks the 200 MB budget today.** `render_environment_preset` builds every layer for the whole
   piece at once, and each primitive draws `rng.standard_normal(n)` in float64. For a 10-minute piece that is 212 MB for one
   draw of one layer (26.46 M samples x 8 B) [measured arithmetic]. Streaming in chunks with carried filter state is
   exact (block-wise `sosfilt` with `zi` equals the whole-buffer result with max error 0.0, while stateless blocks leave a
   0.63 seam [measured, §4]), and 16 layers x 5 s stereo float32 is 28 MB.
4. **The ambience is not coupled to the score at all.** `render_environment_preset(name, duration_s, sr, seed)` takes no
   score, spectrum or timeline [repo `environment.py:806`]. The only coupling is a fixed 2.1 kHz notch
   (`vocal_pocket_notch_hz`) and the mixer's after-the-fact ducking. A scheduler that places calls in pockets the score
   leaves open needs a score-derived occupancy map as an input; in a synthetic test, pocket-aware placement cut overlap
   with occupied cells from 0.52 to 0.06 [measured, §2.4].
5. **Shared random generator across layers.** Layers share one `rng` [repo `environment.py:825,844`], so inserting or
   reordering a layer changes the random draws of every layer after it. `scene_layers` already seeds each layer apart
   (`seed + 101 * i`, [repo `env_engine/render.py:108`]). The biome engine must seed per generator from a name, not from
   order.
6. **A naive tract filter fails.** For the animal waveguide I tested the cheap route (lossy ABCD tube response, then LPC
   fit). LPC order 12 and 24 put F1 of a 2-tube tract at 782 Hz and 542 Hz when the true peak is 357 Hz; order 40 is
   right but its pole radius is 0.9997, too close to the unit circle for float32 [measured, §2.3]. The ABCD response
   itself is correct (F1 ratio between media 0.5726 against c ratio 0.5769). The design therefore picks peaks of the ABCD
   response and builds a resonator bank from them, not LPC.
7. **Two "do not" rules in AGENTS.md shape the schema.** "Writing a new Python generator for a new sound name is
   forbidden. Unknown fields = error, no fallback. No normalization erasing physical intensity differences" (rule 16),
   and "Acoustic values are cited or measured". The current engine breaks the third: `NORMALIZED` layers are set to RMS
   0.1 before `gain_db` [repo `environment.py:853-859`], and `synth_rain` peak-normalises to 0.8 [repo `environment.py:451`],
   so a drizzle and a downpour of the same preset differ only by event count. The biome engine keeps physical level
   (§2.2, §3) and treats `gain_db` as a trim.

## 1. Codebase gap analysis

### 1.1 What exists, and how it fits together [repo]

| Piece | Where | Role today |
|---|---|---|
| Layer engine | `scripts/environment.py` (983 lines) | 14 primitives in `PRIMITIVES` (L599), `layers[]` preset, whole-buffer render, stereo output |
| Physical scene engine | `scripts/phys_core/` (materials, geometry, excite, resonate, propagate, scene) | materials, modal objects, interactions, one propagation chain; `env_engine/render.py` dispatches `scene` / `scene_layers` |
| Animal calls | `scripts/env_engine/calls.py` | `animal_call` primitive: elements, sequence, one straight tube, 8 presets in `references/data/presets/calls/` |
| One-shots | `scripts/sfx_engine/oneshot.py` | `scene` / `model` / `generator`; peak-normalised to 0.9 |
| Spatial bus | `scripts/spatial_engine/hoa.py`, `render.py`, `mix_engine/placement.py` | 5th-order HOA, air per tap, image-source reflections, late field, Doppler on trajectories |
| Ear model | `scripts/ear_model/model.py`, `ear_rows.py` | CARFAC-style cascade at 22.4 kHz, `ear.fatigue/masking/mod_roughness/pitch_salience/iacc` (advisory) |
| Gate profiles | `references/data/presets/gate/*.json`, `scripts/gate_profiles.py` | rows carry `mode`, params and a written `reason` |

Dispatch is already two-headed: `environment.render_environment_preset` hands a `scene`/`scene_layers` preset to
`env_engine.render`, and `render_preset` hands a `layers` preset back to `environment.py` [repo `environment.py:821`,
`env_engine/render.py:68-89`]. A third shape, `biome`, slots into the same dispatch without breaking either.

### 1.2 Hard-coded Earth assumptions to remove

| # | File:line | Assumption | Refactor |
|---|---|---|---|
| 1 | `env_engine/calls.py:39` | `C = 343.0` feeds `tube_formants` | read `medium.c_m_s` |
| 2 | `phys_core/propagate.py:91` | `2 d f / 343.0` in `fresnel_number` (barrier diffraction) | take `c` as an argument |
| 3 | `phys_core/resonate.py:82` | `c = 343.0` in the Miki porous-absorber `k` | take `c` (and `rho`) from the medium |
| 4 | `spatial_engine/hoa.py:39` | `C = 343.0` for Doppler lead, reflection delays, late field | read once from the scene's medium |
| 5 | `spatial_engine/nfc.py:27` | `C = 343.0` for near-field compensation | same |
| 6 | `spatial_engine/lfe_qa.py:23` | `C_SOUND = 343.0` | same (Earth-only is acceptable here; it QAs a loudspeaker room, but it must read the same constant source) |
| 7 | `airabs.py:31-62` | ISO 9613-1 only; takes `temp_c, rh, pressure_kpa`, no gas | become `medium.absorption(f)`; ISO stays as `model: "iso9613"` |
| 8 | `environment.py:870-875` | `airabs.apply` is passed only `temp_c`, `rh` (never pressure); else a made-up cutoff `22000 / (1 + 0.35 (d - 2))` | one path through the medium; delete the made-up law |
| 9 | `environment.py:933-955` | `apply_environmental_acoustics`: a third distance law (`10000 - 120 d`) | dead code, see §1.3 |
| 10 | `environment.py:419-451` | `synth_rain`: Marshall-Palmer `4.1 R^-0.21`, `v = 3.778 D^0.67`, Minnaert `3.26 / a`, surface table `water/solid/leaf`, `30 sqrt(R)` drops/s "tuned by ear" | pull `g`, `rho_gas`, `rho_liquid`, `gamma`, `p` from the medium and `world`; surfaces become `materials` |
| 11 | `environment.py:454-479` | `synth_cricket_chorus`: Dolbear `(T_F - 40) / 15` in code | a `stridulation` fauna element with `rate_per_k` as data |
| 12 | `environment.py:324-367` | `synth_water_flow`: bubble band 350-1600 Hz, 22 ms, fixed | `particulate_impacts` with a liquid surface; bubble `f` from Minnaert on the medium |
| 13 | `environment.py:164-271` | `synth_fm_chirp_cluster`: floor 100 Hz, 0.35/h partials, one tracheal peak, calls never start in the last second (`while t_curr < sec - 1.0`), fixed `+0.6 s` gap | replaced by `fauna[]` (§2.3); kept as a migrated alias |
| 14 | `environment.py:370-389` | `synth_formant_babble`: Earth vowel formant triples as defaults | formants become preset data; babble is a `fauna` crowd of a tract |
| 15 | `environment.py:910-920` | vocal notch fixed at 2.1 kHz | replaced by the score-pocket map (§2.4) |
| 16 | `phys_core/propagate.py:62` | canopy loss `0.02 dB/m x density x (f/4 kHz)^0.8`, marked ESTIMATE | a measured table in `medium.boundary.canopy` (§2.1) |
| 17 | `phys_core/propagate.py:75` | ground reflection `7 ms x (1 + d/20)` delay, fixed gain 0.35 | derive from source/listener height and ground impedance |
| 18 | `phys_core/propagate.py:181` | `pan()` carries elevation but renders none | feed the HOA bus with real direction instead of stereo pan |
| 19 | `phys_core/render.py:282` | `mass * 9.81` for footfall force | `world.g_m_s2` |
| 20 | `phys_core/materials.py:33-44` | materials are room-temperature handbook values | add `temperature_k` dependence only if a preset needs it; otherwise leave (ice, regolith are new `PRESETS` rows) |
| 21 | `environment.py:880-897` | `diffuse` pans each sample to a random angle; stereo only; no elevation | emitter and diffuse-field spec to the bus (§3 `spatial_coupling`) |
| 22 | `spatial_engine/hoa.py:689,709` | `temp_c`, `rh` taken per track from `spatial` | read from the scene medium, per-track override only |
| 23 | `spatial_engine/hoa.py` `_source` | an environment stem is collapsed to `y.mean(axis=1)` per source and placed as one point or a pair at `half_width_deg` (`mix_engine/dsp_utils.py:568-576`) | a bed is a diffuse field, fauna are point emitters with their own azimuth, elevation and trajectory |

### 1.3 Dead code and cleanup candidates [repo, grep]

- `environment.apply_environmental_acoustics` is never called; the only mention outside its definition is a table row in
  `references/workflow/custom-scripts.md:142` and the docstring of `propagate.py`. Remove, and drop the doc row.
- `ALIASES` (L607) and `LEGACY_NAMES` (L671) map old recipe names; keep until the migration tool (M9) rewrites presets,
  then delete.
- `synth_formant_babble` and `synth_doppler_sweep` are referenced only by tests, `references/spatial/environments-as-presets.md`
  and aliases. They survive as migrated generators, not as Python functions.
- `NORMALIZED` and `BED_REF_RMS` (L53-55) encode "gain_db is comparable across layers". The replacement is an explicit
  `reference` (§3), not a global RMS.

### 1.4 What already works and must be reused

- `phys_core.excite.gust_series` (Kaimal-type -5/3 gust), `granular`, `stress`, `stick_slip`, `flow` [repo].
- `phys_core.materials` (12-field schema with ranges, 13 presets) and `geometry.SHAPES`: the right place for ice, regolith
  and hull materials.
- `env_engine/calls.py` `element()` (pitch contour, subharmonic, biphonation, pulse, vibrato, `rate_per_c`) and its
  validation (`problems`) pattern.
- `sound_model.py` (voice stacks, work estimate `MAX_WORK`, refusal of runaway models): the work estimator becomes
  the CPU gate (`env.cpu_budget`).
- Row API: `_row(out, level, name, detail)` and `gp.param(row, key)` in `ear_rows.py`.
- `compute.py` (workers, optional GPU) for parallel layers.

## 2. Physics primitives and math verification

All checks below ran on numpy 2.5.5 / scipy 1.18.1 in this container (4 cores). Scripts: §8.

### 2.1 Universal acoustic medium

**Bulk state.** Ideal-gas defaults, overridable by a measured value:

$$ c = \sqrt{\gamma R T / M}, \qquad \rho = \frac{p M}{R T}, \qquad Z = \rho c $$

| Medium (declared state) | c, m/s | rho, kg/m3 | Z, rayl | Check |
|---|---|---|---|---|
| Earth, 293.15 K, 101325 Pa, M 0.02897, gamma 1.40 | 343.2 | 1.204 | 413 | matches the repo's 343 [measured] |
| Mars, CO2, 210 K, 610 Pa, gamma 1.29 | 226.2 | 0.0145 | 3.5 | state is a **[start]** typical-surface value |
| Titan, N2, 94 K, 146.7 kPa, M 0.0279, gamma 1.40 | 198.0 | 5.24 | 1037 | measured surface c is 194.0 m/s [lit: Huygens SSP/API-V, Hagermann et al. 2007; value from an Open University thesis snippet]; 2.1 % high, so the ideal-gas default needs a measured override, and `env.medium_consistency` reports the gap |
| Venus surface, CO2, 735 K, 9.2 MPa | 408.2 | 66.3 | 27045 | **[start]** state |

**Absorption.** One equation for every gas:

$$ \alpha(f)\;[\mathrm{Np/m}] = \alpha_{cl} f^2 + \sum_i \frac{2\mu_i}{c}\,\frac{f^2/f_{r,i}}{1+(f/f_{r,i})^2} $$

- `mu_i` is the peak absorption per wavelength of relaxation process `i` at `f = f_r,i`.
- The classical term from gas properties is `alpha_cl = (2 pi)^2 / (2 rho c^3) * eta * (4/3 + (gamma - 1)/Pr)`
  (bulk viscosity neglected). For Earth air it gives 1.21e-10 dB/m/Hz^2 against ISO's 1.60e-10, ratio 0.76 [measured].
  Use it as the default for gases with no tabulated coefficient and say so; Earth keeps the ISO coefficient.
- Earth, expressed this way, reproduces ISO exactly: `f_r,O2 = 35 414 Hz`, `mu_O2 = 1.05e-3`; `f_r,N2 = 332 Hz`,
  `mu_N2 = 1.98e-4` at 20 C, 50 % RH. 1 kHz: ISO 4.66, generalised 4.66 dB/km. 10 kHz: 158.84 and 158.84 dB/km [measured].
  (The match is by construction; it proves the reparametrisation is lossless, not that Earth air is right.)
- **CO2 and N2/CH4 relaxation numbers were not obtained.** The search found the right primary source (Petculescu and
  Lueptow, *Icarus* 186, 413-419, 2007, "Atmospheric acoustics of Titan, Mars, Venus, and Earth") and the qualitative
  result that relaxation is several orders of magnitude stronger on Venus and Mars than on Earth and Titan, and that Titan
  transmits best [lit, from press and Acoustics Today snippets, full text not read]. No `f_r` or `mu` for CO2 were
  retrievable. Rule for the schema: a relaxation entry without a `sources` line is `ESTIMATE` and the example Titan and
  Mars presets must say so (§3).

**Level in a medium.** Pressure is not comparable across media at equal source power: `I = p^2 / (Z)`, so a source of
radiated power `W` gives `p_rms ~ sqrt(Z W / (4 pi r^2))`. On Mars, Z = 3.5 rayl against 413 on Earth, so the same
radiated power gives about 20.7 dB less pressure. A `level_ref` block in the medium (`basis: "power" | "pressure"`)
makes the choice explicit; `gain_db` becomes a trim on top. This is what stops a Martian dust storm sounding as loud as
an Earth one.

**Interfaces.** Energy transmission between two media is `T = 4 Z1 Z2 / (Z1 + Z2)^2`:

- air to water on Earth: -29.5 dB [measured, Z_water = 998 x 1482];
- Titan air to a liquid-methane sea with `c_sea = 1400 m/s` (**ESTIMATE**), `rho = 450` (**[start]**): -21.8 dB [measured].

A fauna entry in the sea medium heard from the air therefore needs a `media` map and an `interfaces` entry, not a filter.

**Wind and Doppler.** Doppler scale is `v / c` with the medium's `c` (the HOA bus has `dop * (d_s - d_s.min()) / C * sr`
[repo `hoa.py:705`], so only the constant changes). A mean-flow profile (`log` or `power`, reference height) shifts the
effective `c` along a path; first version: scalar only, profile `[start]`.

**Boundary scattering (canopy, ice, rock, metal).** I do not propose a closed-form leaf scatterer. A geometric
extinction estimate for a leaf area density of 0.2 m2/m3 gives about 1.7 dB/m, far above the 0.1-0.3 dB/m the foliage
literature reports at a few kHz [lit: Aylor 1972; not opened], because thin flexible leaves do not behave as rigid
scatterers. So `boundary.canopy` is a **measured table** `excess_db_per_m: [[f_hz, dB/m], ...]` with a `sources` line;
the current formula (`0.02 dB/m x density x (f/4k)^0.8`, ESTIMATE) becomes the fallback of a table-less preset and is
labelled as such. Hard boundaries (ice, rock, hull) use the existing `materials` + `flow_resistivity` (Miki) and
`occluder` (Maekawa, mass law) paths, with `c` and `rho` passed in. Dispersion at a boundary is not modelled in v1 and
the report says so.

### 2.2 Composable weather and micro-physics generators

**`turbulence`: vortex shedding.** Shedding frequency from the Strouhal law, with the regime chosen by Reynolds number:

$$ f = \mathrm{St}(Re)\,\frac{U}{d}, \qquad Re = \frac{\rho U d}{\eta} $$

with `St = 0.212 (1 - 21.2/Re)` for 250 < Re < 2e5 (Roshko 1954 [lit: from memory of the standard form; verify]) and
`St = 0.2663 - 1.019 / sqrt(Re)` for laminar shedding, 49 < Re < ~190 (Williamson 1988 [lit: same caveat]).

| Case | Re | St | f |
|---|---|---|---|
| Earth, 5 mm twig, 8 m/s | 2661 | 0.210 | 336 Hz [measured] |
| Titan, 5 mm spire, 2 m/s (rho 5.4, eta 6.0e-6 **[start]**) | 9000 | 0.212 | 84.6 Hz [measured] |
| Mars, 5 mm, 20 m/s (rho 0.0145, eta 1.1e-5 **[start]**) | 132 | outside the high-Re law | the laminar law gives St about 0.178, about 710 Hz |

The Mars row is the reason the schema selects the law by `Re`, not by medium: the Roshko form returns `nan` there
[measured]. The laminar number is my arithmetic from the Williamson form, not a measurement.

Level: a Curle dipole scales as `W ~ rho U^6 S / c^3` [lit: Curle 1955; the constant is not established here].
`k_dipole` is a preset field marked `[start]`; the medium's `rho` and `c` enter the scaling, which is what makes a
thick-atmosphere storm louder than a thin one at the same wind speed.

Synthesis, cheap: an ensemble of K = 16-32 phase-continuous oscillators whose instantaneous frequency is
`St U(t) / d_k`, `U(t)` from the existing `excite.gust_series`, `d_k` sampled from the obstacle size distribution
(lognormal), amplitude weighted by `U^3` per oscillator plus a broadband residual. K x n multiply-adds, no per-obstacle loop.

**`particulate_impacts`: drops, grains, hail, dust, micrometeoroids.** Arrival process: thinned Poisson in absolute time.
Size spectrum `N(D) = N0 exp(-L D)`, `L = 4.1 R^-0.21 mm^-1` (Marshall-Palmer; the repo already uses it) with `N0` a
preset field. Terminal velocity generalised to any gravity and fluid:

$$ v_t = \sqrt{\frac{8\, g\, D\,(\rho_p - \rho_g)}{3\, C_d\, \rho_g}} $$

| Case | Result |
|---|---|
| Earth, 4 mm water drop, `Cd = 1.1` | 8.87 m/s [measured]; the repo's Atlas-Ulbrich form `3.778 D^0.67` gives 9.56 |
| Titan, 4 mm methane drop, g 1.352, rho_p 450, rho_g 5.24, `Cd = 0.6` | 1.43 m/s [measured] |

`Cd` is a preset field and **[start]**; the Earth `Cd` had to be raised to 1.1 to land near the empirical speed because
real drops deform. The Titan `Cd` has no source here, and the 1.43 m/s figure needs a literature check (Lorenz's work on
Titan raindrops is the likely source [lit, not read]). Impact energy `E = 1/2 m v^2` goes to the existing
`excite.impact_energy`/`contact_time`, so a slow Titan drop is physically quieter, not just rarer. A liquid surface
adds Minnaert bubbles:

$$ f_b = \frac{1}{2\pi R_b}\sqrt{\frac{3\gamma p}{\rho_l}} $$

`f_b R_b` = 3.287 Hz m for an air bubble in water at 1 atm [measured], matching the repo's `3.26 / a` to 0.8 %, and
5.89 Hz m for an N2 bubble in liquid methane on Titan [measured, with `rho_l = 450` **[start]**], so a 1 mm bubble rings
near 5.9 kHz there against about 3.3 kHz on Earth. (The Minnaert form is confirmed by the NASA and PMC pages the search
returned; the compact `3.26 / R` constant was not found in them, so I checked it myself.) Entrainment probability by
drop size is a table `[start]`.

Cost note: events that share a surface share a modal bank. 600 impulses/s into a 12-mode two-pole bank ran at
0.40 s of CPU per 60 s of audio [measured]. Per-event unique resonators (bubbles) are vectorised damped sinusoids
and are cheap because only a fraction of events carry one.

**`modal_field`: resonant mediums.** Excitation (stochastic Poisson impulses, granular avalanche, or score-synced) into a
modal bank whose modes come from a `law` (`bar`, `plate`, `membrane`, existing `geometry.SHAPES`) or an explicit list.
Examples as data:

- *Singing dunes:* grain-vibration frequency `f = k sqrt(g / d)` with `k = 0.4` **[start]** reproduces about 89 Hz for
  0.2 mm grains on Earth [measured]; the scaling with `sqrt(g/d)` is from Andreotti's dune work [lit, not opened]. On
  Mars the same preset drops to 54 Hz [measured, same `k`], which is the point of passing `g` from the world block.
- *Ice and crystal:* a `bar`/`plate` mode set from `materials` (ice and quartz rows to add), low `loss_factor`, so the
  tail comes from the material's `T60`, not a reverb.
- *Hull groans:* `excite.stress` events whose rate follows a thermal-cycle `control` curve.

**Stereo bed becomes a field.** A bed is `n_decorrelated` uncorrelated emitters (§3 `spatial_coupling`), not a stereo
pair, which is also what the 5th-order bus can use (36 channels).

### 2.3 Creature and bio-synth

`animal_call` stays as the element/sequence grammar (it already validates and is data), and `fauna[]` adds a
`source` and a `resonator` to each element. Nothing species-specific goes in Python.

**Excitation modes (`source.kind`):**

| kind | What it is | Parameters (all data) | Builds on |
|---|---|---|---|
| `glottal_chaos` | mammal folds: LF-shaped pulse train with `Rd`, jitter/shimmer as an OU process, period doubling by an alternating-period asymmetry, chaos by a logistic-driven period modulation | `f0_hz` contour, `rd`, `jitter`, `subharmonic`, `chaos`, `rd_contour` | `vocal_engine` LF source (docs/PSYCHOACOUSTICS.md "Liljencrants-Fant"), `calls.element` |
| `dual_syrinx` | two independent labia: contours `f_left`, `f_right`, tanh/cubic saturation, FM and AM depth/rate, summing or cross-modulating | `f_left`, `f_right`, `fm_hz/depth`, `am_hz/depth`, `saturation` | `synth_fm_chirp_cluster` (rewritten as data) |
| `stridulation` | tooth impacts at `f_tooth = v_scrape / tooth_pitch` exciting a resonant plate (wing, harp); chirps grouped into trains | `tooth_hz`, `plate_hz`, `plate_q`, `train: {chirp_ms, period_ms, duty}`, `rate_per_k`, `temp_ref_k` | `excite.stick_slip`, cricket chorus (Dolbear becomes data) |
| `click_train` | sonar/clicks: damped sinusoids at `fc` with a click-interval contour (slow train to buzz) | `fc_hz`, `q`, `ici_ms` contour, `level_db` | `sound_model` impact + modal |
| `swim_bladder` | a gas bladder driven by the medium's pressure | `radius_m`, `gamma`, drive pulses | Minnaert form |

**Swim bladder in a liquid medium** shows why the medium must hold pressure: `f = (1/2 pi R) sqrt(3 gamma p / rho)` for a
5 mm bladder rings at 657 Hz at the surface, 1587 Hz at 50 m and 2963 Hz at 200 m of water [measured]. The call's pitch
follows the depth from `medium.state.pressure_pa`, with no code naming a fish.

**Resonator modes (`resonator.kind`):**

1. `tube`: the existing `(2k - 1) c / (4 L)` closed-open tube, now with `c` from the medium.
2. `tract`: N segments `[length_m, area_cm2]`, optional `branches` (nasal, air sac, laryngeal ventricle) as side tubes,
   wall loss `alpha` and a radiation termination. Computed by chain (ABCD) matrices on a frequency grid.
   Verification: a two-tube tract (0.17 m at 2 cm2, 0.17 m at 8 cm2) has |H| peaks at 357, 654, 1365, 1662 Hz in air; the
   same geometry in Titan gas shifts F1 by 0.5726 against the c ratio 0.5769 [measured, 0.7 % off, grid-limited]. The
   closed-open straight tube from a 24-section Kelly-Lochbaum run landed within 1 Hz of `(2k - 1) c / 4L` in air,
   Mars gas and Titan gas [measured].
3. `formant_bank`: explicit `[f_hz, bw_hz, gain_db]` for crystalline or metallic resonators.

**Filter realisation (a finding).** Do not fit the tract with LPC:

| Fit | F1..F4 of the 2-tube tract, air | Max pole radius |
|---|---|---|
| true peaks of the ABCD response | 357, 654, 1365, 1662 | n/a |
| LPC 12 | 782, 1869, 3551, 4656 | 0.76 |
| LPC 24 | 542, 1472, 2028, 2533 | 0.97 |
| LPC 40 | 355, 653, 920, 1364 | 0.9997 |

[measured]. Specification instead: **peak-pick** the response, build one two-pole resonator per peak (frequency exact,
bandwidth from the -3 dB width), 16 peaks below 8 kHz for this tract. A parallel bank of 16 ran 60 s of audio in 0.33 s
(about 0.03 s at 10 % duty) [measured]. **Open issue:** the parallel sum's log-spectrum correlation with |H| was only
0.725 over 0-6 kHz [measured], so formant *positions* are right but spectral *shape* needs a cascade form or fitted
per-peak gains. M3 must test that before the design claims envelope fidelity.

Interfaces to the rest: `individuals`, `individual_spread` and `scale` (smaller animal, shorter tube, higher formants
by `1/scale`) are already in `calls.py` and carry over. Cold-blooded rate follows `rate_per_k` from the medium's
temperature, generalising `rate_per_c` [repo `calls.py:173`] (Gerhardt and Doherty 1988 for pulse rate vs temperature
[lit: from `docs/PSYCHOACOUSTICS.md`]).

### 2.4 Ecological and score-aware scheduler

**Niche partitioning (Krause).** The search confirms the acoustic niche hypothesis: species adjust calls so they are
isolated in frequency and in time, with support from insects, birds and anurans, but sources disagree on 1987 vs 1993 for
the origin and I did not reach the primary paper [lit; cite Krause and Pijanowski only after checking]. Each fauna entry
declares a `niche`: `band_hz`, `active` (diel window or a `control` curve), `bout` rate. Overlap index (Schoener's D on
band-energy shares `p_v(b)`):

$$ D_{vw} = 1 - \tfrac12 \sum_b |p_v(b) - p_w(b)| $$

computed on 1/3-octave bands, weighted by the share of frames where both are active.

**Call-and-response and predator-prey silence.** An `ecology.rules[]` list of `{on, do}` triggers on a timeline of
events: `on: {fauna: "tiger_roar"}` or `{score: "drop"}` (a section name or `hits_at` time from the direction sheet);
`do: {freeze: ["thrush", "frogs"], for_s: [8, 20], fade_ms: 400, resume: "ramp_s: 6"}` or
`{answer: "thrush_b", after_ms: [300, 900], p: 0.6}`. Triggers are resolved on the schedule, before synthesis, so
silence is absence of events, not a duck applied afterwards.

**Score and ear coupling.** The scheduler takes an **occupancy map** built from the score and sheet before any ambience is
rendered:

- time axis: 0.5 s frames; frequency axis: 24 ERB-spaced bands (the ear model already has 48 ERB channels, `auditory.erb_centres`);
- value: expected figure and bed energy from the notes (register, velocity, duration) plus the previous render's stems when a
  render exists; the lead's band is protected with a margin;
- a call is accepted at a candidate time if its band's occupancy is under a threshold, else retried within a window or
  dropped with probability `1 - p_force`; `foreground: true` calls pick the pockets, `background` ones fill what is left.

In a synthetic test (120 x 24 cells, 35 % occupied plus a busy low end), random placement overlapped occupied cells 0.52 of the
time and pocket-aware placement 0.06 with a 5 % escape rate [measured, §8]. That is a property of the sampler on a toy
grid, not evidence of lower `ear.masking` on real pieces; the gate row in §5 is what measures it.

Beds are handled differently: a bed never sits in the figure's bands (`carve` of the same occupancy map, applied as a
slow band gain in the generator, replacing the fixed 2.1 kHz notch), and `ear.fatigue` is protected by capping
`density_budget` (events/s, summed) and by a slow `control` rest curve.

## 3. Universal biome JSON schema

Convention: the repo's own self-documenting schemas are Python dicts of `(default, low, high, unit, doc)` (see
`phys_core/materials.SCHEMA`) validated by `problems()`; unknown keys are errors. The biome schema follows that, so
`presets.py validate` and `project_gate.py` can reuse the pattern. Preset folder: `references/data/presets/biomes/`
(project copy: `presets/biomes/`). `layers` and `scene` presets keep working; dispatch gains a third head,
`"schema": "biome/1"`.

### 3.1 Top-level keys

| Key | Type | Meaning | Required |
|---|---|---|---|
| `schema` | `"biome/1"` | version | yes |
| `name`, `character` | string | one sentence on the place and why these parts (project gate already asks) | yes |
| `world` | object | `g_m_s2` (default 9.81), `day_length_s`, `listener: {medium, height_m}` | no |
| `media` | map name -> medium | at least one; `"air"` is the default listener medium | yes (or `medium`) |
| `medium` | object | shorthand for `media: {"air": ...}` | one of the two |
| `interfaces[]` | list | `{between: [a, b], transmission: "fresnel"}` | if more than one medium |
| `materials` | map | extra `phys_core.materials` rows (ice, regolith, hull) | no |
| `generators[]` | list | bed and event sources (§3.3) | yes |
| `fauna[]` | list | creatures (§3.4) | no |
| `ecology` | object | niches, rules, density budget, score coupling (§3.5) | no |
| `spatial_coupling` | object | field and emitter hand-over to the bus (§3.6) | no |
| `reference` | object | the physical level reference; replaces global RMS normalisation | yes |
| `controls` | map | named slow curves (`[[s, value], ...]` or OU) other blocks cite | no |
| `sources` | list | every number's origin; `ESTIMATE: ...` allowed but listed | yes |

### 3.2 `medium` (schema table)

| Key | Unit | Range | Default | Meaning |
|---|---|---|---|---|
| `model` | - | `ideal_gas`, `iso9613`, `liquid` | `ideal_gas` | `iso9613` computes Earth-air relaxations from T, RH, p |
| `gas.molar_mass_kg_mol` | kg/mol | 0.002..0.2 | 0.02897 | |
| `gas.gamma` | - | 1.0..1.7 | 1.40 | |
| `gas.viscosity_pa_s`, `gas.prandtl` | | | | for `alpha_cl` and `Re` |
| `state.temperature_k` | K | 1..2000 | 293.15 | |
| `state.pressure_pa` | Pa | 1..1e9 | 101325 | |
| `state.rh_percent` | % | 0..100 | 50 | `iso9613` only |
| `c_m_s`, `rho_kg_m3` | | | `"auto"` | a number overrides the ideal-gas value |
| `c_measured_m_s` | m/s | | null | checked by `env.medium_consistency` |
| `classical` | 1/(m Hz^2) | | `"auto"` | `alpha_cl` |
| `relaxations[]` | | | `[]` | `{f_hz or "auto", mu_max, sources}` |
| `flow` | | | none | `{u_ref_m_s, z_ref_m, profile: log or power, gust_corner_hz}` |
| `boundary.canopy` | | | none | `{excess_db_per_m: [[f_hz, dB/m], ...], sources}` |
| `boundary.ground` | | | none | `{material, height_m}` |
| `level_ref` | | | `{basis: "power", p_ref_pa: 2e-5}` | `basis: "pressure"` keeps pressure fixed |

### 3.3 `generators[]` (kinds `turbulence`, `particulate_impacts`, `modal_field`, plus migrated `noise_bed`)

Common keys: `name`, `kind`, `medium` (default listener medium), `gain_db` (trim), `salience` (`bed` | `foreground`),
`control` (name of a slow curve), `seed_key` (defaults to `name`), `spatial` (azimuth, elevation, distance or
`field: true`), `sources`.

- `turbulence`: `obstacles: {d_m: {dist: "lognormal", median, sigma}, count_density, shape}`, `flow: {u_m_s, gust_corner_hz,
  intensity}`, `k_dipole`, `strouhal: {law: "auto" | "roshko" | "williamson"}`, `broadband: {share, band_hz}`.
- `particulate_impacts`: `population: {kind: "rain" | "hail" | "grain" | "dust", rate_mm_h or rate_per_m2_s, n0, d_mm range,
  rho_particle, cd}`, `surface: {material, area_m2, patches}`, `bubbles: {p_by_size: [[d_mm, p], ...]}` (liquid only).
- `modal_field`: `modes: {law, geometry, material}` or `{list: [[f_hz, t60_s, gain_db], ...]}`, `excitation: {kind: "poisson" | "granular"
  | "stress" | "score_synced", rate_hz, ...}`.

### 3.4 `fauna[]`

`name`, `call` (an existing `calls` preset to start from; keys written beside it win), `elements`, `sequence`, `gap_ms`,
`source` (`kind` + data), `resonator` (`kind` + data), `individuals`, `individual_spread`, `bouts_per_min`, `niche`
(`band_hz`, `active`), `salience`, `medium`, `position` (`azimuth`, `elevation`, `distance`, `trajectory`), `temperature`
(`rate_per_k`, `temp_ref_k`), `sources`.

### 3.5 `ecology`

`density_budget: {events_per_s_max, fatigue_guard: true}`, `niches: {auto: true, min_separation: "D<=0.4"}`,
`rules[]` as in §2.4, `score: {occupancy: "from_score", protect_roles: ["melody","lead","vocal"], margin_db, pocket_threshold}`.

### 3.6 `spatial_coupling`

`field: {kind: "diffuse", emitters: 12, order: 5, height_by_band: [...], correlation_target}`; `emitters[]`
point sources with the usual `spatial` (`azimuth`, `elevation`, `distance`, `trajectory`, `doppler`); `room: {space: "<preset>"}`
that names a `spaces/` preset or `"outdoor_open"`; `decode_hint: ["stereo", "immersive_7_1", "immersive_3_2"]`. Elevation from fauna and
field height is carried to the bus, not folded into a pan (closes gap 18 and 23).

### 3.7 Example 1: `western_ghats_monsoon.json` (realistic)

```json
{
  "schema": "biome/1",
  "name": "western_ghats_monsoon",
  "character": "Shola forest edge at about 1000 m in heavy monsoon rain: a steady leaf-drip and canopy bed, a stream below, a dawn thrush that stops when the tiger calls.",
  "world": {"g_m_s2": 9.81, "listener": {"medium": "air", "height_m": 1.6}},
  "medium": {
    "model": "iso9613",
    "state": {"temperature_k": 292.15, "pressure_pa": 89900, "rh_percent": 96},
    "boundary": {
      "canopy": {"excess_db_per_m": [[500, 0.03], [2000, 0.12], [4000, 0.25], [8000, 0.5]],
                 "sources": ["ESTIMATE: shape and size of the foliage excess-attenuation table after Aylor 1972 [lit, not opened]; replace with the values in the research note"]},
      "ground": {"material": "soil", "height_m": 0.0}
    },
    "level_ref": {"basis": "power", "p_ref_pa": 2e-5},
    "sources": ["pressure 89.9 kPa = standard atmosphere at 1000 m [start]", "T 19 C and RH 96 % monsoon values [start]"]
  },
  "materials": {"leaf_wet": {"family": "membrane", "density": 900, "young_modulus_gpa": 0.05, "loss_factor": 0.14,
                             "thickness_m": 0.0003, "flow_resistivity": 9000, "restitution": 0.2}},
  "controls": {"rain_intensity": {"curve": [[0, 12], [60, 28], [180, 18]], "unit": "mm/h"}},
  "generators": [
    {"name": "canopy_rain", "kind": "particulate_impacts", "salience": "bed",
     "population": {"kind": "rain", "rate_mm_h": {"control": "rain_intensity"}, "n0": 8000, "cd": 1.1},
     "surface": {"material": "leaf_wet", "area_m2": 400, "patches": 8},
     "spatial": {"field": true, "elevation": 35},
     "sources": ["Marshall-Palmer size law [repo environment.py:430]", "cd 1.1 fitted to ~9 m/s for 4 mm [measured]; n0 [start]"]},
    {"name": "stream", "kind": "particulate_impacts", "salience": "bed",
     "population": {"kind": "rain", "rate_per_m2_s": 900, "d_mm": [0.3, 1.2], "rho_particle": 998},
     "surface": {"material": "water", "area_m2": 30, "patches": 4},
     "bubbles": {"p_by_size": [[0.4, 0.6], [1.0, 0.25]]},
     "spatial": {"azimuth": -70, "distance": 18, "elevation": -5},
     "sources": ["ESTIMATE: rates and bubble probabilities; measure a stream recording with ambience_reference.py"]},
    {"name": "canopy_wind", "kind": "turbulence", "salience": "bed",
     "obstacles": {"d_m": {"dist": "lognormal", "median": 0.004, "sigma": 0.5}, "count_density": 40, "shape": "cylinder"},
     "flow": {"u_m_s": 2.5, "gust_corner_hz": 0.08, "intensity": 0.35},
     "k_dipole": 1.0, "strouhal": {"law": "auto"},
     "spatial": {"field": true, "elevation": 40},
     "sources": ["Strouhal St(Re) [lit]; twig and leaf-stalk size and u ESTIMATE; k_dipole [start]"]}
  ],
  "fauna": [
    {"name": "malabar_thrush", "call": "songbird_phrase", "salience": "foreground",
     "source": {"kind": "dual_syrinx", "f_left": [[0, 2400], [1, 3100]], "f_right": [[0, 2300], [1, 2900]], "fm_hz": 18, "fm_depth": 0.04, "saturation": 1.4},
     "resonator": {"kind": "tube", "length_cm": 4.5},
     "bouts_per_min": 3, "individuals": 2,
     "niche": {"band_hz": [1800, 4200], "active": {"control": "dawn_dusk"}},
     "position": {"azimuth": 25, "elevation": 20, "distance": 14},
     "sources": ["ESTIMATE: contour, band and bout rate; the shipped songbird_phrase is itself an ESTIMATE; research note must supply a recording-based contour"]},
    {"name": "tree_frogs", "kind": "chorus", "salience": "bed",
     "source": {"kind": "stridulation", "tooth_hz": 90, "plate_hz": 2800, "plate_q": 12, "rate_per_k": 0.04, "temp_ref_k": 292.15,
                "train": {"chirp_ms": 120, "period_ms": 450, "duty": 0.27}},
     "individuals": 14, "niche": {"band_hz": [2400, 3400]},
     "position": {"azimuth": -40, "elevation": 0, "distance": 9},
     "sources": ["ESTIMATE: the schema reuses stridulation for a pulsed frog call; a vocal-sac preset should replace it once researched"]},
    {"name": "tiger_roar", "call": "big_cat_roar", "salience": "foreground",
     "source": {"kind": "glottal_chaos", "f0_hz": [[0, 120], [0.4, 150], [1, 90]], "rd": 1.8, "subharmonic": 0.4, "chaos": 0.25},
     "resonator": {"kind": "tract", "segments": [[0.11, 4.0], [0.10, 9.0], [0.08, 14.0]], "alpha_np_m": 0.02},
     "bouts_per_min": 0.2, "individuals": 1,
     "niche": {"band_hz": [60, 1200]},
     "position": {"azimuth": 110, "elevation": 0, "distance": 60},
     "sources": ["ESTIMATE: every number; vocal-tract length of a large felid and f0 from a measured roar"]}
  ],
  "ecology": {
    "density_budget": {"events_per_s_max": 140, "fatigue_guard": true},
    "niches": {"auto": true, "min_separation": "D<=0.4"},
    "rules": [
      {"on": {"fauna": "tiger_roar"}, "do": {"freeze": ["malabar_thrush", "tree_frogs"], "for_s": [10, 25], "fade_ms": 400, "ramp_s": 8}},
      {"on": {"score": "drop"}, "do": {"freeze": ["malabar_thrush"], "for_s": [3, 6], "fade_ms": 200}}
    ],
    "score": {"occupancy": "from_score", "protect_roles": ["melody", "lead", "vocal"], "margin_db": 3, "pocket_threshold": 0.35}
  },
  "spatial_coupling": {
    "field": {"kind": "diffuse", "emitters": 12, "order": 5, "correlation_target": 0.15},
    "room": {"space": "forest_canopy"},
    "decode_hint": ["stereo", "immersive_7_1", "immersive_3_2"]
  },
  "reference": {"basis": "physical", "check_lufs_range": [-34, -22]},
  "sources": ["ESTIMATE: see each block. A project copy needs the research note and sources the pipeline blocks on (AGENTS 3.2-3.5)."]
}
```

### 3.8 Example 2: `titan_methane_storm.json` (fictional medium, real numbers where they exist)

```json
{
  "schema": "biome/1",
  "name": "titan_methane_storm",
  "character": "Titan lakeshore under a methane downpour: a thick cold nitrogen air that carries sound far, slow heavy drops on water-ice shore, a shoreline of liquid methane, and a leviathan call that crosses the sea surface 22 dB down.",
  "world": {"g_m_s2": 1.352, "listener": {"medium": "air", "height_m": 1.8}},
  "media": {
    "air": {
      "model": "ideal_gas",
      "gas": {"molar_mass_kg_mol": 0.0279, "gamma": 1.40, "viscosity_pa_s": 6.0e-6, "prandtl": 0.71},
      "state": {"temperature_k": 94, "pressure_pa": 146700},
      "c_m_s": "auto", "c_measured_m_s": 194.0,
      "relaxations": [],
      "flow": {"u_ref_m_s": 0.8, "z_ref_m": 1.8, "profile": "power", "gust_corner_hz": 0.05},
      "level_ref": {"basis": "power", "p_ref_pa": 2e-5},
      "sources": ["c_measured 194.0 m/s: Huygens SSP API-V [lit, thesis snippet]", "ideal-gas c is 198.0 [measured]", "eta and Pr ESTIMATE", "no relaxation terms: Titan relaxation is weak per Petculescu & Lueptow 2007 [lit, qualitative]; numbers still to be taken from the paper"]
    },
    "sea": {
      "model": "liquid", "c_m_s": 1400, "rho_kg_m3": 450,
      "gas": {"gamma": 1.40},
      "state": {"temperature_k": 94, "pressure_pa": 146700},
      "sources": ["ESTIMATE: c in liquid methane/ethane; density 450 [start]"]
    }
  },
  "interfaces": [{"between": ["sea", "air"], "transmission": "fresnel"}],
  "materials": {
    "water_ice": {"family": "brittle", "density": 920, "young_modulus_gpa": 9.0, "loss_factor": 0.004, "toughness_kpa": 1500, "restitution": 0.5},
    "liquid_methane": {"family": "absorbent", "density": 450, "young_modulus_gpa": 0.001, "loss_factor": 0.3}
  },
  "controls": {"storm": {"curve": [[0, 4], [40, 18], [90, 6]], "unit": "mm/h"},
               "gust":  {"ou": {"sigma": 0.25, "tau_s": 6}}},
  "generators": [
    {"name": "methane_rain_ice", "kind": "particulate_impacts", "salience": "bed",
     "population": {"kind": "rain", "rate_mm_h": {"control": "storm"}, "n0": 8000, "rho_particle": 450, "cd": 0.6, "d_mm": [1.0, 6.0]},
     "surface": {"material": "water_ice", "area_m2": 250, "patches": 6},
     "spatial": {"field": true, "elevation": 30},
     "sources": ["terminal speed 1.43 m/s for 4 mm [measured arithmetic]; cd 0.6, n0 and d range ESTIMATE; check against Lorenz (Titan raindrops) [lit, not read]"]},
    {"name": "lake_rain", "kind": "particulate_impacts", "salience": "bed",
     "population": {"kind": "rain", "rate_mm_h": {"control": "storm"}, "n0": 8000, "rho_particle": 450, "cd": 0.6, "d_mm": [1.0, 6.0]},
     "surface": {"material": "liquid_methane", "area_m2": 900, "patches": 4},
     "bubbles": {"p_by_size": [[2.0, 0.3], [4.0, 0.1]]},
     "spatial": {"azimuth": 0, "distance": 25, "elevation": -3},
     "sources": ["Minnaert f.R = 5.89 Hz m for N2 in liquid methane [measured]; bubble probabilities ESTIMATE"]},
    {"name": "spire_wind", "kind": "turbulence", "salience": "bed",
     "obstacles": {"d_m": {"dist": "lognormal", "median": 0.05, "sigma": 0.6}, "count_density": 0.2, "shape": "cylinder"},
     "flow": {"u_m_s": 2.0, "gust_corner_hz": 0.05, "intensity": 0.4},
     "k_dipole": 1.0, "strouhal": {"law": "auto"},
     "spatial": {"field": true, "elevation": 10},
     "sources": ["Re about 9e3 for 5 mm at 2 m/s -> f about 85 Hz [measured]; spire sizes and speeds ESTIMATE"]},
    {"name": "ice_shelf_creak", "kind": "modal_field", "salience": "bed",
     "modes": {"law": "plate", "material": "water_ice", "geometry": {"length_m": 40, "width_m": 12, "thickness_m": 0.6}},
     "excitation": {"kind": "stress", "rate_hz": 0.3, "control": "gust"},
     "spatial": {"azimuth": 150, "distance": 40, "elevation": 0},
     "sources": ["mode set from phys_core geometry; ice moduli [start]"]}
  ],
  "fauna": [
    {"name": "leviathan", "salience": "foreground", "medium": "sea",
     "elements": {"rise":  {"f0_hz": [[0, 38], [1, 62]], "ms": [3500, 5000], "harmonics": 8, "rolloff": 1.1, "noise": 0.12, "subharmonic": 0.3},
                  "fall":  {"f0_hz": [[0, 62], [1, 30]], "ms": [4000, 6000], "harmonics": 8, "rolloff": 1.1, "noise": 0.2}},
     "sequence": ["rise", "fall"],
     "source": {"kind": "glottal_chaos", "f0_hz": [[0, 38], [1, 62]], "rd": 2.2, "subharmonic": 0.3, "chaos": 0.2},
     "resonator": {"kind": "tract", "segments": [[2.5, 300], [2.0, 900]], "alpha_np_m": 0.001},
     "bouts_per_min": 0.15, "individuals": 1,
     "niche": {"band_hz": [25, 140]},
     "position": {"azimuth": -20, "elevation": -10, "distance": 120},
     "sources": ["fictional creature; tract size picked for ~35-60 Hz in a medium of c 1400 m/s [start]; nothing here claims a real animal"]},
    {"name": "sonar_skitterers", "salience": "bed", "medium": "air",
     "source": {"kind": "click_train", "fc_hz": 2200, "q": 3, "ici_ms": [[0, 180], [1, 12]]},
     "individuals": 9, "bouts_per_min": 6,
     "niche": {"band_hz": [1600, 3200]},
     "position": {"azimuth": 70, "elevation": 0, "distance": 20},
     "sources": ["fictional; click shape after the click_train primitive; all ESTIMATE"]}
  ],
  "ecology": {
    "density_budget": {"events_per_s_max": 60, "fatigue_guard": true},
    "niches": {"auto": true, "min_separation": "D<=0.4"},
    "rules": [
      {"on": {"fauna": "leviathan"}, "do": {"freeze": ["sonar_skitterers"], "for_s": [14, 30], "fade_ms": 800, "ramp_s": 10}},
      {"on": {"score": "drop"}, "do": {"freeze": ["sonar_skitterers"], "for_s": [4, 8], "fade_ms": 300}}
    ],
    "score": {"occupancy": "from_score", "protect_roles": ["melody", "lead", "vocal", "drone"], "margin_db": 4, "pocket_threshold": 0.3}
  },
  "spatial_coupling": {
    "field": {"kind": "diffuse", "emitters": 12, "order": 5, "correlation_target": 0.1},
    "room": {"space": "outdoor_open"},
    "decode_hint": ["stereo", "immersive_7_1", "immersive_3_2"]
  },
  "reference": {"basis": "physical"},
  "sources": ["Everything marked ESTIMATE is a placeholder until a research note replaces it. The medium numbers that exist are Titan state (Huygens), measured c, and computed c/rho/Z."]
}
```

What the second preset shows: only the `medium` block changes the physics. The leviathan's call is rendered with the sea's
`c` and `rho`, crosses the `sea -> air` interface at -21.8 dB, then 120 m of Titan air; drop speed, bubble pitch and Strouhal tone
all follow from `g`, `rho`, `eta`, `gamma`, `p` and nothing else.

## 4. CPU and RAM budget (< 200 MB overhead)

**Design.** Every generator is a stateful object: `process(n_samples) -> float32 (n,)` (or `(n, K)` for an emitter), with
filter state `zi`, oscillator phase, gust-series carry and a pending-event tail carried across chunks. The renderer pulls
chunks of 5 s (the ear model's `chunk_s` is also 5 s [repo `references/data/presets/ear/model.json`]), so the chunk size matches the
gate's own. Rules:

- float32 buffers; random draws in float32 where the generator allows (`rng.standard_normal(n, dtype=np.float32)`).
- Events are scheduled by a thinned Poisson process in absolute time, one lookahead window ahead, so a chunk edge never
  cuts an event; each event writes into the current and next chunk's overlap tail.
- Seeding: `np.random.default_rng(np.random.SeedSequence([seed, zlib.crc32(name)]))` per generator (closes finding 5).
- Gust and slow-modulation series are generated by a recursive filter (a two-pole approximation of the -5/3 form) so they
  stream; today `gust_series` is a whole-buffer FFT [repo `excite.py:137`], which is exact but not streamable.
- No loop and no cross-fade: continuous synthesis has no seam; `env.loop_stationarity` checks that claim.
- The ear-model and HOA stages are not part of this budget; they are existing stages with their own cost.

**Exactness check.** 20 s of white noise through a 4th-order band-pass: chunked with carried `zi` equals the whole-buffer
result with max error 0.0; chunked without state differs by up to 0.63 [measured].

**Measured cost** (this container, one core, a 1-minute mini-bed): six band-limited noise beds 0.44 s, a 12-mode modal bank
fed by 600 impulses/s 0.40 s, three harmonic voices at 10 % duty 0.19 s: 1.03 s per 60 s of audio, real-time factor 0.017
[measured]. Fauna tract resonator banks at 10 % duty add about 0.03 s per voice-minute [measured].

**Estimate for the full design, 4 cores:** I did not build the full engine, so these are projections.

| Component | Per minute of audio, one core | Basis |
|---|---|---|
| 8 bed generators (noise, turbulence ensemble of 32 oscillators) | 1.0-2.0 s | bands measured; ensemble is K x n MACs, 32 x 2.6 M = 85 M MACs/min, about 0.1-0.3 s |
| 2-3 particulate generators, shared banks | 0.5-1.0 s | measured bank 0.40 s |
| 6-10 fauna voices | 0.3-0.8 s | measured |
| Scheduler, occupancy map, rules | < 0.1 s | one pass over a 120 x 24 map per minute |
| Diffuse field, 12 decorrelated emitters (allpass cascade as today) | 2-5 s | today's 32-stage cascade on one layer; this is the part I did not measure and it is the one to watch |
| Total, serial | about 4-9 s per minute of audio | real-time factor 0.07-0.15 |
| On 4 workers by layer (`compute.py`) | about 1.5-3 s per minute | assumes near-linear scaling, **not measured** |

**RAM.** Per 5 s stereo float32 chunk: 1.76 MB per layer; 16 layers, 28.2 MB [measured arithmetic]. Plus: ISO FIR 1025
taps, resonator states (a few kB), occupancy map (120 x 24 floats per minute of piece, 11.5 kB/min), event queue. Estimated
overhead 40-60 MB, under the 200 MB limit with room for two chunks in flight. The present engine instead holds whole-piece
arrays: one float64 layer of a 10-minute piece is 212 MB before it is cast.

## 5. New QA gate rows (`env.*` in `ci_report.json`)

All thresholds are **[start]**; every row is advisory (INFO/WARN) until measured on real renders, except two that check
declarations and cannot be tuned away. Each row reads its parameters through `gp.param`, so a profile can relax it only with a
written reason, as with `ear.fatigue` in `ambient.json`. Remediations name the lever in the preset or the score, never a threshold.

| Row | Metric and formula | INFO | WARN | FAIL | Step-7 remediation |
|---|---|---|---|---|---|
| `env.medium_consistency` | (a) `err_c = |c_decl - c_calc| / c_meas`; (b) `err_alpha = max_f |alpha_bus(f) - alpha_medium(f)| / alpha_medium(f)` at 1, 4, 8 kHz for three distances; (c) a rendered tube preset's F1 against `c/4L` from the medium; (d) static scan: no `343` literal in modules that read a medium | all within 3 % | `err_c` 3-15 %, `err_alpha` 2-10 %, F1 off 3-8 % | `err_c` > 15 % (an impossible declaration), `err_alpha` > 10 %, any literal found | set `c_measured_m_s`; give a gas `gamma` and `M` that reproduce it; replace the module constant with the medium read. Titan as drafted reads `err_c` = 2.1 % (WARN-free) |
| `env.niche_collision` | per fauna pair: Schoener `D_vw` on 1/3-octave band shares, times co-activity share `A_vw` (frames both active / frames the rarer is active) | `D < 0.4` or `A < 0.2` | `D >= 0.4` and `A >= 0.25` | `D >= 0.7` and `A >= 0.5` | move `niche.band_hz` apart, change `active` windows, lower `individuals`, add a call-and-response rule; never EQ one of them |
| `env.score_pocket` | share of `foreground` calls whose time-frequency cells are below `pocket_threshold` of score occupancy; plus the existing `ear.masking` share for the lead with and without the environment stem (leave-one-out) | >= 85 % in pockets | 60-85 % | < 60 % with `ear.masking` WARN | raise `pocket_threshold`, widen `protect_roles` margin, lower `foreground` density, shift a section's `control` curve |
| `env.foreground_salience` | per foreground event: `S = 10 log10(E_event / (E_bed + E_score))` in the event's ERB channels from the ear model NAP, over +-1 s; background must stay under the lead | `3 <= S <= 15 dB` | `S < 3` for > 30 % of foreground events (inaudible), or `S > 15` for any event while a figure is active | `S > 15` over a figure's active frames for > 10 s | raise the call's level or `salience` pocket; lower beds under a figure; move the call off the lead's band |
| `env.loop_stationarity` | for generators declared `stationary`: (a) per-ERB-band log-energy in 8 windows, `max |mu_k - mu| / sd_ref` (`sd_ref` from the same generator rendered with two seeds); (b) seam test: render in chunks, `D_seam` = level jump across a chunk edge in dB and the spectral-flux ratio seam/median; (c) repeat score = max normalised autocorrelation of the 1 s envelope at lags 5-60 s | (a) <= 2, (b) jump < 0.5 dB and flux ratio < 1.5, (c) < 0.4 | (a) 2-3.5, (b) jump 0.5-1.5 dB or ratio 1.5-3, (c) 0.4-0.6 | (b) jump > 1.5 dB or a click row (`gate_checks` clicks) at a chunk edge, (c) > 0.8 | carry state across chunks; lengthen the gust corner; raise the `control` OU variance; for a repeat, add a second seed-keyed generator or lengthen a table |
| `env.density_budget` | summed event rate, plus the `ear.fatigue` index of the environment stem alone | rate <= `events_per_s_max` and fatigue <= 0.6 | rate over budget by < 25 %, or fatigue 0.6-0.75 over 5 s | rate over by > 25 % with `ear.fatigue` WARN on the master | lower `rate_*`/`individuals`, add `control` rest curves, thin beds |
| `env.level_physical` | measured stem LUFS against the `reference` predicted from `W`, `Z` and distance; a drizzle and a downpour must differ by their physical gap, not by a normalised level | within 3 LU of prediction | 3-8 LU | > 8 LU, or two presets differing in `rate_mm_h` by 10x within 3 LU | remove any normalisation; fix `k_dipole`, `level_ref`, or the rate curve |
| `env.diffuse_field` | interaural coherence of the bed in 500-880 Hz (the existing IACC band), bed `correlation` target, and cross-decoder consistency between stereo fold and `immersive_*` | within 0.1 of target | 0.1-0.25 | > 0.25, or a mono fold more than 3 dB below the stereo sum | raise `emitters`, change `correlation_target`, narrow a part the row names (as `fold.*` rows already direct) |
| `env.ecology_rules` | for every `rules[]` trigger: did the named fauna fall silent within `fade_ms`, for the declared `for_s`, and resume on the ramp; measured on stems | all rules honoured | one late or short | a rule not honoured | check `on` names against sections and fauna names; the scheduler, not a duck, owns this |
| `env.cpu_budget` | the engine's own work estimate (as `sound_model.MAX_WORK` does) per minute of audio, before render | < 12 s/min | 12-30 s/min | > 30 s/min refuses to render | cut `emitters`, patches, fauna `individuals`, oscillators `K` |
| `env.declaration` | every unit and range in the preset against its schema; every number has a `sources` line or `ESTIMATE`; no unknown key | clean | an `ESTIMATE` remains in a delivered preset (listed) | unknown key, out-of-range value, missing `sources` | the schema's error text names the field |

`env.declaration` and the static part of `env.medium_consistency` follow the same rule as `focus.declared` and
`intent.vocabulary`: a declaration is a fact to fix in the preset. `env.score_pocket` and `env.foreground_salience` are
the two that link to the ear model; neither claims to measure how it sounds, and the existing note applies that the ear
model is calibrated on synthetic fixtures only [repo `ear_rows.py` docstring, `ambient.json` reason].

Profiles: `ambient` and `effects_only` take the rows on with `ear.fatigue` relaxed as today; `cinematic` and `melodic`
take `env.score_pocket` and `env.foreground_salience` as WARN; a piece without an environment track reports none of them.

## 6. Phased implementation roadmap

Each milestone is PR-sized, keeps `layers` and `scene` presets rendering byte-for-byte (the repo has
`phys_core/baseline.py` to freeze and verify renders), and ships its own synthetic tests in `tests/`. Order is dependency order.

| # | Milestone | Scope | Tests (synthetic) |
|---|---|---|---|
| M0 | **Baseline freeze** | freeze renders of the 4 shipped environments and 8 calls with `phys_core/baseline.py`; add `tests/test_biome_baseline.py` | every shipped preset renders to the frozen hash; adds nothing else |
| M1 | **`medium.py`** (new, in `phys_core/`) | `Medium` object: bulk `c`, `rho`, `Z`, `alpha(f)` (classical + relaxations + `iso9613`), interfaces; `airabs.alpha_db_per_m` kept as a thin wrapper; schema + `problems()` | `test_medium.py`: ISO reproduction at 1/10 kHz within 0.1 dB/km; generalised form equals ISO (max rel err < 1e-3 across 100 Hz-20 kHz, 3 states); Earth `c` 343.2; Titan `c` within 3 % of 194; Fresnel -29.5 dB for air-water; unknown key raises |
| M2 | **Medium reaches every module** | replace the six `343` literals and the three absorption paths (`environment.py:870-875`, `propagate.air`, `hoa._source`/`_reflections`) with a medium read; Earth default unchanged | `test_medium_wiring.py`: AST scan finds no `343` in the listed modules; an Earth render equals M0 hash; a medium with `c` x 0.5 halves a tube preset's F1 (within 2 %) and doubles the Doppler lead; `err_alpha` row computes < 2 % |
| M3 | **Generators: `turbulence`, `particulate_impacts`, `modal_field`** | stateful `process()` objects, per-name seeding, physical level (`reference`), `Re`-selected Strouhal, generalised `v_t` and Minnaert, shared modal banks; legacy primitives become aliases | `test_generators.py`: Strouhal tone at 336 Hz +-5 % for the Earth twig and 85 Hz +-5 % for the Titan spire; `v_t` 8.9 and 1.43 m/s +-3 %; Minnaert `f R` 3.29 and 5.89 +-1 %; Mars case selects the laminar law (no `nan`); rain 10x intensity is about +10 dB or more at fixed seed, not normalised; adding a generator leaves every other generator's samples identical |
| M4 | **Fauna: `source` + `resonator`** | `glottal_chaos`, `dual_syrinx`, `stridulation`, `click_train`, `swim_bladder`; `tube`, `tract` (ABCD + peak-picked resonators), `formant_bank`; migration of the 8 `calls` presets and bird/cricket primitives | `test_fauna.py`: straight-tube `tract` peaks within 1 % of `(2k-1)c/4L`; the 2-tube tract peaks 357/654/1365/1662 Hz +-2 %; F1 ratio across media within 1.5 % of c ratio; the LPC-12 fit is *not* used (a test asserts the bank's F1 is within 2 % where LPC-12 is off by >50 %); stridulation rate rises with `rate_per_k`; a smaller `scale` raises formants by `1/scale`; subharmonic energy at `f0/2` for `subharmonic` > 0 |
| M5 | **Streaming engine** | chunked renderer, carried state, thinned-Poisson lookahead, recursive gust series, render by chunk to the stem writer | `test_streaming.py`: chunked equals whole-buffer (max err < 1e-6, filters) and statistically equal (events); no click row at a chunk edge; peak RAM of a 10-min render under 200 MB (tracemalloc), against the old engine's 212 MB for one float64 layer; same seed gives the same samples for 5 s and 1 s chunks |
| M6 | **Ecology + score coupling** | `ecology` rules, niche overlap, occupancy map from score + sheet, pocket-aware scheduler, `foreground`/`background`, density budget; replaces the 2.1 kHz notch | `test_ecology.py`: freeze rule silences the named fauna within `fade_ms` and for `for_s`; two same-band callers get `D` > 0.7 flagged; pocket-aware overlap < 0.15 against random > 0.4 on a seeded occupancy grid (the §2.4 result as a regression test); a `score` trigger by section name fires at that section's start |
| M7 | **`env.*` gate rows** | the rows of §5 in `ear_rows.py`-style module `env_rows.py`; profile entries; docs in `references/mixing/quality-gate.md` | `test_env_rows.py`: each row has a passing and a failing fixture (a row that cannot fail is not a row); `medium_consistency` fails on a planted `343`; `niche_collision` fails on two identical niches; `loop_stationarity` fails on a 4 s tile repeated; `foreground_salience` warns on a call 6 dB under the bed |
| M8 | **Spatial coupling** | diffuse field as `emitters` over the HOA bus, fauna as point emitters with elevation and trajectories, interface handling; `spatial_engine` reads the medium; decode to `3.2` and `7.1` | `test_biome_spatial.py`: bed IACC within 0.1 of target; fauna azimuth/elevation recovered from the decoded `7.1` within 15 deg; stereo fold within 3 dB of the sum; elevation reaches the bus (a fauna at 40 deg is not on the horizontal plane); Doppler scale follows medium `c` |
| M9 | **Migration, pruning, docs** | `env_migrate.py` rewrites `layers` presets to `biome/1`; delete `apply_environmental_acoustics`, `ALIASES`/`LEGACY_NAMES` after migration; KB file `knowledgebase/sound-design/biome-acoustics.md` with the §2 facts and sources (header per `knowledgebase/SCHEMA.md`, `tests/check_kb.py` passes); `references/spatial/environments-as-presets.md` and `AGENTS.md` row for biomes; the two example presets under `references/data/presets/biomes/` | `test_env_migrate.py`: each shipped preset migrates and renders within the `ambience_reference.py` tolerance of the old render; `tests/check_kb.py`; `presets.py validate` on both examples |

Risks to schedule early: the streaming gust series (M5 depends on a recursive form matching the FFT -5/3 slope within
the existing test's tolerance), the tract envelope fidelity (§2.3 open issue), and the cost of the diffuse field (the only
unmeasured large item in §4). M8 is the one that touches shared engine code and needs the immersive owner's review.

## 7. Decisions taken from this research

1. One `Medium` object is the single owner of `c`, `rho`, `Z`, absorption and interfaces; the six `343` literals and the
   three absorption paths go away (M1-M2). Earth stays the default and must render identically.
2. Relaxation absorption is data: `(2 mu / c) (f^2/f_r) / (1 + (f/f_r)^2)` per process, with `iso9613` computing Earth's.
   Mars and Titan relaxation values stay ESTIMATE until read from Petculescu and Lueptow 2007.
3. Level is physical (`reference`, `level_ref`); `NORMALIZED`/`BED_REF_RMS` and peak normalisation are removed from the biome
   path. The legacy path keeps them until M9.
4. Strouhal law is chosen by Reynolds number, never by medium; Roshko alone fails at Re 132.
5. Fall speed, Minnaert pitch and dune pitch take `g`, densities, `gamma` and pressure from the world and medium blocks.
6. The animal tract is an ABCD response turned into a peak-picked resonator bank. LPC is rejected on measured evidence.
7. Calls and fauna are data only; a new creature is a JSON file (AGENTS rule 16). `animal_call` stays as the grammar.
8. Ecology is resolved on the schedule, before synthesis; rules and niches are data; ducking stays a mix decision, not a substitute.
9. The scheduler reads an occupancy map built from the score and sheet; the fixed 2.1 kHz notch is replaced by it.
10. Generators are stateful and chunked; seeding is per generator name; no loop and no cross-fade.
11. `env.*` rows are advisory with `[start]` thresholds, except the declaration checks; every row ships a failing fixture.
12. A bed is a diffuse field and fauna are point emitters with elevation; an environment stem is no longer collapsed to a mono pair.

## 8. What was and was not checked

**Checked in this session** (scripts in the session scratchpad, `verify.py` and `tract.py`, numpy 2.5.5 / scipy 1.18.1):
ISO reproduction by the generalised relaxation form; ideal-gas `c`, `rho`, `Z` for four atmospheres; classical-term ratio 0.76;
generalised Minnaert (Earth 3.287, Titan 5.89 Hz m); Strouhal for three media (and the Mars `nan`); generalised fall speed;
dune and swim-bladder scaling; Fresnel interface loss; closed-open tube formants by a 24-section Kelly-Lochbaum model in three
media; ABCD two-tube response and its c scaling; LPC 12/24/40 failure; peak-picked bank cost; stateful vs stateless block
filtering; the mini-bed cost; the pocket-aware sampler on a toy grid. The repo audit read `environment.py`, `env_engine/`,
`phys_core/{scene,propagate,excite,materials,registry,resonate}.py`, `sfx_engine/oneshot.py`, the relevant parts of
`spatial_engine/hoa.py`, `mix_engine/{placement,chains,bus,dsp_utils}.py`, `render_natural.py`, `ear_model/model.py`,
`ear_rows.py`, `project_gate.py`, and `docs/PSYCHOACOUSTICS.md`.

**Not checked:**

- No audio was rendered or auditioned, and nothing here claims any proposed sound is realistic. Taste and realism are not measured.
- No CO2 or N2/CH4 relaxation coefficients, no Titan drag coefficient, no tiger, thrush, frog or leviathan data, no foliage
  attenuation table, no ice moduli beyond a starting value: all ESTIMATE, all in the example presets' `sources`.
- Literature items marked **[lit]** came from search snippets and titles (Petculescu and Lueptow 2007; Huygens sound speed via an
  Open University thesis; Hagermann et al. 2007; the Krause/Pijanowski niche literature, whose origin date the sources disagree
  on; the Minnaert form on NASA and PMC pages; Roshko, Williamson, Curle, Aylor, Andreotti, Lorenz and Gerhardt and Doherty
  from memory of the standard forms). None was read in full. Verify before they enter a knowledge-base file.
- The 4-core cost is a projection; the diffuse-field cost and the full engine were not built or timed. Memory figures for the new
  engine are arithmetic, not a `tracemalloc` run.
- The tract bank's spectral-envelope fidelity is an open issue (correlation 0.725), as is the streaming gust series.
- The HOA, HRTF and decoder changes of M8 were read, not run; the `hoa` stage was not exercised here.
- Nothing in the existing pipeline, presets, tests or gate was changed; the repo's test suite was not run.

Sources used through search (all as snippets, none read in full):
[Petculescu & Lueptow, ASA pressroom](https://acoustics.org/pressroom/httpdocs/153rd/petculescu.html),
[Acoustics Today, Jan 2007](https://acousticstoday.org/issues/2007AT/Jan2007/files/basic-html/page19.html),
[Science News, "Music to alien ears"](https://www.sciencenews.org/article/music-alien-ears),
[Huygens SSP sound speed, Open University](https://oro.open.ac.uk/26571),
[Huygens measurements of the speed of sound on Titan](https://oro.open.ac.uk/64846),
[Niche differentiation in soundscape ecology (arXiv 1907.12812)](https://arxiv.org/pdf/1907.12812),
[Minnaert resonance](https://wikipedia.com/wiki/Minnaert_resonance),
[NASA, Listening to raindrops](https://science.nasa.gov/earth-science/oceanography/listening-to-raindrops/).

## 9. Implementation status (added after the build)

Everything in §6 (M0 to M9) is built, each as its own commit on this branch, each with synthetic tests. The files:
`scripts/phys_core/medium.py` (M1), `scripts/biome/` (`physics`, `context`, `generators`, `schema`, `sources`, `tract`, `fauna`,
`fauna_schema`, `engine`, `ecology`, `ecology_schema`, `spatial`, `spatial_coupling_schema`), `scripts/env_rows.py` (M7),
`scripts/env_migrate.py` (M9), `references/spatial/biomes.md`, `knowledgebase/sound-design/biome-acoustics.md`, and two shipped
presets, `western_ghats_monsoon` and `titan_methane_storm`. Where the build differs from this design:

| Design said | Built | Why |
|---|---|---|
| Earth `c` from the ideal gas, 343.2 m/s | `iso9613` takes 343.0 x sqrt(T / 293.15), the speed the repo always used | an Earth preset renders byte for byte as before (`tests/biome_baseline.py`) |
| six modules with a 343 literal | eight scene modules read the active medium; four playback modules (head model, loudspeaker room) keep Earth's speed on purpose, declared in `tests/test_medium_wiring.py` | a head model describes where the programme is heard, not where it was recorded |
| three absorption paths each changed | `airabs` dispatches to the active medium; every caller already used it | one choke point instead of three edits |
| a field is a stereo pair, decorrelated | a field is N independent emitters, each from its own named random stream | the allpass decorrelator measured 0.36 (rain) and 0.63 (wind) mean `|correlation|` in `env.diffuse_field`, because phase changes cannot decorrelate tonal content; emitters measure 0.00 and 0.01 |
| `obstacles.count_density`, rate in drops per m2 per second | `frontal_area_m2`; `rate_mm_h` is the volume that lands, the event rate follows from the drop sizes | one physical quantity decides the rate, and a rate that implies more than 250 000 impacts a second is refused with advice |
| an animal's level in dB | `power_w`, the radiated acoustic power, required | pressure then follows the medium's impedance |
| `ecology` resolved on the schedule | a chronological planner decides every bout before render; `Fauna` reads the plan through `scheduler.start_of` | a freeze is an absence of calls plus a fade of a call already sounding |
| `env.foreground_salience` against bed and score | against the rest of the biome in the call's band; the score's figure stays with `ear.masking` and `env.score_pocket` | raw stems are not at mix level before the mixer's gain staging |
| M9 deletes `ALIASES`, `LEGACY_NAMES` | kept; only the dead `apply_environmental_acoustics` and the `pedalboard` import it needed are removed | the layer engine still renders its presets, and `env_migrate.py` is an assistant, not a rewrite: it reports what carries and what does not |
| the immersive hand-over | `biome/spatial.py`: emitters and animals are added to the bus instead of the stereo stem, at the level the mixer's chain gave the stem; the biome is rendered a second time | the bus API takes whole-piece sources |

Defects found by the new tests and fixed on the way, none part of the design:

- the default AllRAD2 speaker decoder was mirrored left to right (it built its harmonics with the azimuth un-negated, so a source
  at -30 degrees came out of FR); AllRAD was right. `tests/test_immersive_31.py` now asserts both put -30/30/-90/90/-135/135 on FL/FR/SL/SR/BL/BR;
- with the measured head data present, the `imm_cues` gate row and the HRTF test read the interaural time difference of a
  broadband probe, which a MagLS decoder leaves free of phase above its 1.5 kHz transition; both now read a 100-700 Hz probe;
- ten gate rows and one preflight rule had no entry in `lint_coverage.py`; `channel_qa._corr` chose arbitrarily between equal peaks of
  opposite sign; the vocal gate read vibrato coupling from the first singer only.

Still not checked: no audio was rendered for listening; the literature items of §8 were not read in full; relaxation terms for CO2
and N2/CH4 are absent; the example presets are full of ESTIMATE on purpose (`env.declaration` says so); the thresholds of the `env.*` rows are
starting values; the CPU row is a projection from a 3 s render and varies with the machine.
