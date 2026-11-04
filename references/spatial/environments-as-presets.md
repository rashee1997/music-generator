# Ambience and rooms are project presets

Ambience (a forest, rain, a bazaar) and the room the music sits in are **written for each project, from its research**.
The skill ships examples (`references/presets/environments/`, `references/presets/spaces/`); they are fallbacks and starting
points, never the answer. Add ambience to a score only when the user asked for it. `setup_project.py --new-project` makes none
unless you pass `--ambience`.

## Steps

1. **Research the place** (see `research-step.md`, including Step 0.2b for the real sounds): write a short "Preset brief" in `reports/research_<topic>.md`: what is
   audible, what is steady (beds) and what happens at a place (spots), the weather, the room's size and surfaces.
2. **Environment preset:** `python scripts/presets.py scaffold environments <name> --project <dir>` (or `--from <shipped>` to start
   from an example). Then edit `<dir>/presets/environments/<name>.json`:
   - `character`: one sentence on the place and why these layers. The gate blocks the placeholder.
   - `sources`: the slugs of the "Real-world references" sections you wrote in the research note (`research_kb.py ... --sounds rain_roof`):
     each has two real sources, a `Licence:` line, and the measured values or `No measurement found: ESTIMATE <reason>`. The gate blocks a
     project-owned environment without them. Pick the physical primitive for the place: `rain_physical` with the `rate_mm_h` and `surface`
     (water, solid, leaf) you found, not the older `rain` name (the gate warns about it).
   - at least one **bed** (`"kind": "bed"`: steady, wide, nothing recognisable) and, as needed, **spots**
     (`"kind": "spot"`: an event with a place; give it `spatial` or a `trajectory`). In the scene form the gate reads the
     scene instead of the layer list: `scene_layers` counts as a bed, and so does a scene whose timeline uses a continuous
     mechanism (`flow`, `foliage`, `granular`, `rolling`, `gait`, `repeated_impact`). A single impact, creak or fracture
     scene is a spot, so pair it with a bed. `environment.preset_is_bed` is the one owner of that rule.
   - every layer's `primitive` and keys come from `python scripts/environment.py --primitives`. An unknown name or key is an error.
   - `gain_curve: [[seconds, dB], ...]` changes a layer's level over time; `decorrelate` (0-1) widens a bed.
3. **Space preset:** `python scripts/presets.py scaffold spaces <name> --project <dir>` (or `--from hall`). Set `room` (rt60,
   pre-delay, high-frequency decay), `reflections` (ground, side, ceiling, rear), `distance` (falloff, air damping, reverb exponent,
   `pre_delay_law`) and a `character` sentence. Name it in the score: `"space": "<name>"`.
4. **Score:** add `{"instrument": "env:<name>", "role": "environment"}` only if ambience was asked for. Give spots that should sound
   placed `spatial: {kind: "spot", ...}`; beds `kind: "bed"` (never binaural). `spread` (0-1) widens a big or close source.
5. **Run the pipeline.** The project gate checks the environment (project-owned, character, a bed, known primitives and keys, no
   ambience built in `scripts/`), the space (project-owned, character) and prints one `staging` line per track.

## The physical scene form

A place can also be written as a physical scene instead of a list of primitives, and that is the route for a new place:

```json
{"name": "roof_at_night", "character": "a tin roof under steady rain, one street away",
 "scene": {"seconds": 30.0,
           "materials": {"tin": {"family": "metal", "density": 7800, "young_modulus_gpa": 200, "loss_factor": 0.0008}},
           "objects": {"sheet": {"material": "tin", "geometry": {"shape": "plate", "width_m": 1.2, "thickness_m": 0.0004}}},
           "timeline": [{"at": 0.0, "for": 30.0, "interaction": "granular", "target": "sheet",
                         "rate_hz": 700, "velocity_m_s": 4.5}],
           "calibration": {"normalize": "energy", "level_db": -18},
           "propagation": {"distance_m": 6.0, "atmosphere": {"temp_c": 12, "rh": 90}}}}
```

`"scene_layers": [{...}, {...}]` mixes several scenes as one bed; each layer keeps its own `gain_db` and `spatial`, and
each is seeded separately so adding a layer does not change the others. The layer form above (`"layers"` with
primitives) still renders unchanged - a project can move one layer at a time.

Start from a worked scene rather than a blank file, and check it before it enters the preset:

```bash
python scripts/physical.py template --out scene.json    # materials, objects, a timeline with a `then` edge
python scripts/physical.py check scene.json             # every problem, render nothing (exit 1 on a problem)
python scripts/physical.py render scene.json --out x.wav --seconds 8   # listen before wiring it in
```

`check` is the gate for the scene itself: an unknown material, object, key or interaction is an error that lists what
is valid, never a fallback. `physical.py verify` re-renders the 40 frozen fixtures and proves nothing moved, so a
refactor can be separated from a sound change.

Surface matters through the material, not a switch: the same drop pattern on tin, on leaves and on water differs
because stiffness, loss factor and flow resistivity differ. Schema: `references/physical-scene.md`.

## Starting values by place

| Place | Bed | Spots | Space rt60 |
|---|---|---|---|
| Forest / jungle | `noise_bed` 100-2600 Hz, `stridulation_bed` | `fm_chirp_cluster`, `bird_chorus`, `impulse_cluster` drips | 1.5-2.8 s, damped highs |
| Open grass / desert | `noise_bed` 90-2200 Hz or `resonant_gust` | `cricket_chorus`, far `fm_chirp_cluster` | 0.4-0.6 s |
| Water | `water_flow` | `impulse_cluster` | 0.8-1.5 s |
| Town / bazaar | `formant_babble` | `doppler_sweep`, `impulse_cluster` | 1.0-1.5 s |

Rules from the research: avoid layering similar frequency content; vary a bed's level slowly (`mod_depth`, turbulence); beds carry
the reverb and spots carry the foreground; distance changes level, direct-to-reverb ratio and brightness together.
