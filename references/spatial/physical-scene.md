---
title: Physical scene
summary: Building a sound from materials, geometry and events, and which numbers are measured or estimates.
tags: [physical, scene, material, geometry, event, foley, break, footstep]
load_when:
  - a sound has to be synthesised from a model
  - a scene value needs a source
---

# A new sound is data: the physical scene

Use this when a sound must be built or changed: a break, a footstep on a surface, rain on a material, a knock on an
object, a creak, a scatter. **No Python function is written per sound.** A scene says what is physically happening -
which sources excite which objects, made of which materials, in which order, and how that travels to a listener.

    python scripts/physical.py laws                     # every mechanism a scene may name
    python scripts/physical.py template --out scene.json # a worked scene: a branch loaded, creaking, breaking, falling
    python scripts/physical.py check  scene.json        # every problem, render nothing
    python scripts/physical.py render scene.json --out x.wav [--stereo] [--seed 1]
    python scripts/physical.py bench  scene.json        # wall-clock, and how much faster than real time

Validation is strict on purpose: an unknown key, an unknown interaction, an unknown material or a bad range is an
error that lists what is valid. Nothing falls back to a generic noise bed.

## The two shapes

| Shape | What it is | When |
|---|---|---|
| `"voices"` | the older stack: excitation -> resonator -> events (`sound_model.py`) | existing presets; still renders byte for byte |
| `"timeline"` | materials, objects and interactions (`phys_core/render.py`) | anything new |

A preset (one-hit `presets/sfx/` or an `env:` preset) carries one or the other under `"scene"`. An environment preset
may also carry `"scene_layers"`: a list of scenes mixed into one bed, each with its own `gain_db` and `spatial`.

## Materials (`phys_core/materials.py`)

A material is properties, never a sound. Ranges are plausibility bounds; a value outside them is refused.

| Property | Unit | What it decides |
|---|---|---|
| `family` | brittle, fibrous, granular, membrane, absorbent, metal | how it fails, how it contacts, whether it rings |
| `density` | kg/m3 | with stiffness, the speed of sound in it |
| `young_modulus_gpa` | GPa | how high the modes sit |
| `loss_factor` | - | how fast a mode dies: `t60 = 2.2 / (f * eta)` |
| `thickness_m`, `length_m`, `width_m` | m | which bending dimension dominates |
| `toughness_kpa` | kPa | stress at which it fails |
| `flow_resistivity` | N s/m4 | porosity: how much the top end is absorbed (leaves, fabric, soil) |
| `restitution` | - | how much speed a bounce keeps |
| `roughness_beta` | - | friction noise slope; more negative is smoother |
| `damp_exp` | - | how much faster the high modes die |
| `grain_size_m` | m | one grain's size, hence its mass, contact time and brightness |

Twelve presets ship (`oak`, `pine`, `glass`, `steel`, `aluminium`, `leaf_dry`, `leaf_green`, `gravel`, `sand_dry`,
`soil`, `stone`, `fabric`, `bark`): anchors, not answers.

## Objects and geometry (`phys_core/geometry.py`)

```json
"objects": {"limb": {"material": "oak",
                     "geometry": {"shape": "bar", "length_m": 1.2, "thickness_m": 0.03},
                     "modes": 10, "f1_hz": 0}}
```

Shapes: `bar`, `plate`, `plate_circular`, `tube`, `string`, `membrane`, `leaf`. The first mode is derived from the
material and the geometry (a bar's `sqrt(E/rho) * h / L^2`, a plate's `0.469 * h/a^2 * sqrt(E/(rho(1-nu^2)))`), and
`f1_hz` on the object always overrides it, because a real branch, leaf or drum head is tensioned and irregular.

## Interactions

| Interaction | Physical model | Key parameters |
|---|---|---|
| `impact` | Hertz contact time from stiffness, mass and velocity, then the object's modes | `target`, `velocity_m_s`, `mass_kg`, `stiffness_pa_m` |
| `repeated_impact` | a bounce: gaps and levels follow the restitution | `restitution`, `gap_s`, `count` |
| `friction` | fractal surface read at the contact speed | `speed_m_s`, `beta`, `band_low/high` |
| `stick_slip` | self-excited limit cycle at the slip frequency | `slip_hz`, `depth` |
| `rolling` | rough surface at speed, low-passed | `speed_m_s`, `beta` |
| `flow` | Kaimal turbulence (-5/3 above the corner) driving a surface | `speed_m_s`, `corner_hz`, `intensity` |
| `granular` | Poisson cascade of grain contacts, each from its own mass and contact time | `rate_hz`, `velocity_m_s`, `grain_size_m` |
| `creak` | stress events whose rate follows the strain rate | `strain`, `rate_hz`, `creep` |
| `fracture` | crack impulses then fragment bodies then settling; brittle vs fibrous | `mass_kg`, `velocity_m_s`, `brittle`, `piece_count` |
| `gait` | gait cycle, heel/forefoot, ground-reaction force on a surface material | `cadence_spm`, `mass_kg` |
| `foliage` | leaf contacts per gust, rate ~ v^2, amplitudes following the gust | `speed_m_s`, `leaf_count` |

`then` is a dependency edge: an event that starts after another. That is what makes a ten-stage branch break data.

## Calibration and propagation

```json
"calibration": {"normalize": "energy", "level_db": -10},
"propagation": {"distance_m": 8.0, "atmosphere": {"temp_c": 18, "rh": 70}, "canopy_density": 0.2},
"spatial": {"azimuth": -20}
```

`normalize` is a declared choice, never silent: `energy` (default; the radiated energy decides the level), `none`,
`peak`, `rms`. Intensity relationships survive unless the scene asks otherwise. `level_db` trims; it is not a fix for
a wrong physical parameter. Propagation is one law for every sound: 1/r spreading, ISO 9613-1 air absorption, canopy
loss and one ground reflection.

## Worked example

`python scripts/physical.py template` writes this (abridged):

```json
{"seconds": 5.0,
 "materials": {"oak": {"family": "fibrous", "density": 700, "young_modulus_gpa": 11, "toughness_kpa": 900}},
 "objects": {"limb": {"material": "oak", "geometry": {"shape": "bar", "length_m": 1.1, "thickness_m": 0.03}}},
 "timeline": [
   {"at": 0.0, "for": 2.6, "interaction": "creak", "target": "limb", "strain": 0.009, "rate_hz": 3.0},
   {"at": 2.6, "interaction": "fracture", "target": "limb", "mass_kg": 1.6, "velocity_m_s": 2.2,
    "then": [{"offset": 0.35, "interaction": "impact", "target": "ground", "velocity_m_s": 3.1},
             {"offset": 0.38, "interaction": "foliage", "target": "leaves", "speed_m_s": 2.5}]}]}
```

Changing one thing changes one thing: `"material": "glass"` instead of oak makes the same knock bright and ringing;
`"grain_size_m": 0.0003` instead of 0.008 turns a gravel crunch into a sand hiss.

## What is measured, and what is an estimate

- **Measured / standard:** modal response (van den Doel, Kry, Pai 2001), ISO 9613-1 absorption (`airabs.py`, checked
  against the standard's values), Minnaert `f = 3.26/r`, Delany-Bazley-Miki porous formulas, Marshall-Palmer drop
  sizes, -5/3 turbulence slope.
- **ESTIMATE, marked in the code:** the 2 ms contact-time reference, the 0.35 fracture energy fraction, canopy
  attenuation per metre, the free-free-bar table used for plates, leaf and grain contact bands.
- Nothing here has been auditioned against a recording. `ambience_reference.py measure` and `--modes` exist to replace
  an estimate with a measurement per project; `sound_fit.py` moves declared `free` parameters toward it.

## Limits, stated plainly

- No pre-recorded audio, no samples, no generative model: pure procedural synthesis, deterministic per seed.
- A leaf's flutter and a canopy's scattering are statistical surrogates, not aeroacoustics.
- Radiation is omnidirectional; directivity is not modelled.
- Material presets are handbook-like round numbers. A production sound needs the measurement step.

## Where the distance is applied — once

A scene places its own source: `propagation.distance_m` is rendered into the stem (1/r, ISO 9613-1 air loss, canopy,
ground reflection — `phys_core/propagate.py`). The mixer must not attenuate it a second time, so it recognises a scene
stem from its preset: a `scene` or `scene_layers` block with `propagation.distance_m` sets `scene_distance_m` on the mix
spec, and `scripts/mixer.py` then skips its own air-absorption and 1/r stages for that track. Azimuth, width, pan and
reverb still apply — only the distance law is skipped, because it already happened.

- `spatial.distance` on a scene track is therefore panning information only. Change the audible distance in
  `propagation.distance_m`, not in both; `project_gate.double_distance_warnings` prints a line when both are set.
- A preset with no `scene`/`scene_layers` (every shipped preset today) keeps the mixer's distance stage unchanged, which
  is why the 40 frozen renders stayed byte-identical.
- `scene_layers` nests `propagation` inside each layer's own `scene`; either form is detected.
