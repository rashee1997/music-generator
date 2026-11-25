---
title: Acoustic biomes
summary: Writing a real or invented place as a `biome/1` environment preset - the medium, generators, animals, ecology, spatial coupling, the env.* gate rows and the tools around them.
tags: [biome, environment, medium, ecology, fauna, weather, ambience, niche, immersive, alien]
load_when:
  - an environment must be a real or invented place whose physics differ from Earth air
  - animals must call in the pockets a score leaves open, or fall silent at a drop
  - an env.* gate row failed
  - a legacy layers preset is to be moved to a biome
---

# Acoustic biomes

A biome is an `environments` preset with `"schema": "biome/1"`. A score uses it as `env:<name>` like any other ambience (add
ambience only when the user asked). The engine is `scripts/biome/`; the medium is `scripts/phys_core/medium.py`. The facts and
their sources are in `knowledgebase/sound-design/biome-acoustics.md`; read it before writing numbers. Shipped examples:
`western_ghats_monsoon` (real) and `titan_methane_storm` (invented medium). Copy one into the project, then replace every
`ESTIMATE` from the research note. `python scripts/environment.py <name> --seconds 20` renders one.

## Steps

1. Research the place and the animals (`research-step.md`): medium state, what blows, what falls, what lives there, when.
2. Write `medium` (or `media` and `interfaces` when an animal lives in another medium). A number from the preset overrides
   the ideal-gas value; give `c_measured_m_s` when a measurement exists, and `env.medium_consistency` compares them.
3. Write `generators[]` for weather and mechanisms, `fauna[]` for animals, `ecology` for who may call when.
4. Declare the same medium on the score (`score.medium`) so the bus's air and Doppler agree with the biome's.
5. Validate: `python scripts/presets.py validate`. Render a draft. Fix an `env.*` row in the preset, never by a threshold.

## The preset

| Block | Says |
|---|---|
| `medium` / `media` | `model` (`iso9613` for Earth air, `ideal_gas`, `liquid`), `gas`, `state`, `relaxations`, `flow`, `boundary.canopy` (a measured table), `level_ref` |
| `world` | `g_m_s2` (drop speed, dune pitch) and the listener's medium |
| `materials` | extra materials over `phys_core/materials.py` (ice, regolith) |
| `controls` | named slow curves or OU series other blocks cite as `{"control": name}` |
| `generators[]` | `turbulence`, `particulate_impacts`, `modal_field`; `stationary: true` asks `env.loop_stationarity` to hold it to a steady bed |
| `fauna[]` | an animal: `source`, `elements`, `sequence`, `resonator`, `power_w`, `niche`, `position`, `individuals` |
| `ecology` | `density_budget`, `niches` (auto), `rules` (freeze, answer), `score` (pockets) |
| `spatial_coupling` | emitters of a field, the room, the formats checked |
| `reference` | `full_scale_pa`: the pressure the output scale calls full |

Every block carries `sources`; a number without a measurement says `ESTIMATE:` there. Unknown keys and out-of-range numbers are
errors; the tables of defaults and ranges are in `scripts/biome/schema.py`, `scripts/biome/ecology_schema.py`,
`scripts/biome/spatial_coupling_schema.py` and `scripts/phys_core/medium.py`.

### Generators

- `turbulence`: obstacles shed vortices in a gusting flow. `obstacles.d_m` (`fixed` or `lognormal`), `frontal_area_m2`,
  `flow.u_m_s`, `k_dipole`. The Strouhal law is chosen by Reynolds number, so the medium's viscosity is required.
- `particulate_impacts`: drops, hail, grains or dust on a surface. `population.rate_mm_h` is the volume that lands, `surface`
  is solid (`material`, `geometry`, `patches`) or liquid (`rho_kg_m3`, with `bubbles.p_by_size`). The engine refuses a
  rate and area that imply more than a quarter of a million impacts a second: that is one wash, not events.
- `modal_field`: ice, a dune, a hull. `modes` from a `material` and `geometry`, a `list`, or `law: grain_vibration`;
  `excitation` is `poisson`, `granular`, `stress` (bursty) or `continuous`.

### Animals

`source.kind`: `glottal_chaos` (folds: `rd`, `subharmonic`, `chaos`), `dual_syrinx` (two oscillators, FM, AM),
`stridulation` (teeth and a plate; `rate_per_k` follows temperature), `click_train`, `swim_bladder` (pitch from the depth and
medium), or `additive` through `call: <calls preset>`. `resonator.kind`: `tube`, `tract` (segments and closed branches), or
`formant_bank`. `power_w` is the acoustic power while calling; there is no default level. An animal in another medium
(`medium: sea`) arrives reduced by the interface loss.

### Ecology

A planner decides every bout before it is rendered, so a freeze is an absence of calls plus a short fade of a call already
sounding. A bout is refused when its animal is frozen, when its activity curve (`niche.active`) says it is not the time, when an
animal in an overlapping band is calling, when the score occupies its band (a `foreground` animal looks for a pocket, a `bed`
animal is only kept out of dense passages), or when the density budget is full. A rule's trigger is an animal
(`{"fauna": name}`) or a section or hit of the score (`{"score": name}`); the score is read through the render, so
the section names of the score's plan and the direction sheet resolve.

## Rows

All come from `scripts/env_rows.py` and run in the gate after the ear rows; `python scripts/gate_profiles.py rows` lists
their numbers. Only the declaration rows are FAIL by nature; the measured rows are INFO or WARN until a threshold has been
checked against recordings.

| Row | Looks at | Lever |
|---|---|---|
| `env.declaration` | valid preset, a `sources` line on every block, ESTIMATE listed | the field the message names |
| `env.medium_consistency` | c against `c_measured_m_s`, the biome's air against the score's, a tube's F1, no 343 literal in the scene modules | `score.medium`, the gas properties |
| `env.niche_collision` | Schoener overlap of two animals' bands times the share of time both call | `niche.band_hz`, `ecology.niches.auto` |
| `env.score_pocket` | the share of foreground calls where the score leaves the band open | `pocket_threshold`, `margin_db`, `bouts_per_min` |
| `env.foreground_salience` | a call against the rest of the biome in its band | `power_w`, the beds |
| `env.loop_stationarity` | level drift between windows, a seam at a chunk edge, a repeat of the level envelope | gust corner, control curve |
| `env.density_budget` | calls begun per second against the budget | `bouts_per_min`, `individuals` |
| `env.level_physical` | rendered pressure against what the generator's own physics predicts | `k_dipole`, `efficiency`, `area_m2` |
| `env.diffuse_field` | mean interchannel correlation of a field source | `spatial.emitters` |
| `env.ecology_rules` | every freeze honoured and every rule fired | rule names against sections and animals |
| `env.cpu_budget` | render seconds per minute of audio, projected from a short render | oscillators, patches, individuals |

`env.foreground_salience` does not look at the score's figure: `ear.masking` does.

## Immersive output

For stereo the biome is folded to two channels: a field is two independent emitters (`spatial.emitters`), a point source is
panned. For an ambisonic, loudspeaker or object bus the mixer receives the biome's separate emitters instead of the fold: a
field is a ring of `spatial_coupling.field.emitters` (12 unless said) at the `spatial.elevations`, a point source and an animal
keep their azimuth, elevation, distance and `trajectory`. The track keeps the level the mixer's chain gave its stem. The
biome is rendered a second time for this, so an immersive render of a long biome costs roughly twice.

## Moving a layers preset

`python scripts/env_migrate.py <preset> --out bed.json` writes a skeleton for the layers that have a physical equivalent and lists
the rest with what to write instead. The result does not sound like the old preset: levels are physical now, and every
migrated block carries an `ESTIMATE` naming its layer. The layer engine stays; old presets keep rendering.

## Limits

No part of this has been compared with a recording. The tract bank has the right formant positions and an approximate
spectral shape. Relaxation terms for CO2 and N2/CH4 are not in the skill; a preset that needs them says ESTIMATE. Boundary
scattering is a measured table or nothing. Only a circular cylinder sheds vortices. The ear model's rows are advisory.
