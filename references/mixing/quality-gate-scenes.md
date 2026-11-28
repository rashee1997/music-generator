# The scene gate: judging a piece against its own direction sheet

A whole-piece median cannot tell a climax from a mistake. The gate used to judge roughness, contour, resolution and
silence once, against one ceiling, for the whole piece - so a cue whose sheet asked for a rough, leapy, unresolved peak
had to be quieter than its own climax, and a declared rest read as a dropout. The scene block fixes that without a new
file format and without a second verdict: a profile points at the project's direction sheet, and the rows that were
whole-piece read it.

Nothing here is mandatory. A profile with no `scene` block emits no scene row and its other rows behave exactly as
before, so a piece judged before this existed is judged the same.

## 1. Where it lives

| What | Where |
|---|---|
| the scene block | `<project>/presets/gate/<piece_type>.json` → `"scene": {...}` (a shipped profile may carry one too) |
| the windows | the project's own `direction/direction_<title>.json`: `sections[].role`, `sections[].start_s/end_s`, `hits[]`, `video.dialogue.windows` |
| the role contract | `references/data/presets/gate/data/scene_roles.json` (roles, allowed/required keys, ranges, dialogue defaults, analysis mechanics) |
| every threshold | `references/data/presets/gate/data/rows.json` (the `scene.*` rows and all others) |
| what to change when one fails | `references/data/presets/gate/data/feedback.json` |

`scripts/scene_timeline.py` reads the sheet; it is the only reader. If the block declares a scene and no sheet is found,
every scene row is `INFO` ("not run"), never a pass.

```json
"scene": {
  "timeline": {"tolerance_s": 0.5},
  "roles": {
    "build":   {"huron_resolution_gravity": "RELAX", "bsi_mode": "pocket"},
    "peak":    {"arousal_min": 0.6, "surprise_min_z": 1.0, "roughness_min_frac": 0.5,
                "waive_ceiling": ["roughness", "feel.contour", "feel.resolution"],
                "bsi_mode": "rupture", "huron_resolution_gravity": "RELAX"},
    "release": {"strain_drop_min": 0.15, "huron_resolution_gravity": "ENFORCE"}
  },
  "dialogue": {"margin_db_tight": 5.0}
}
```

An unknown role, an unknown key, a number outside its range, a required key missing, or a role that names nothing is
`scene.preset` FAIL with the message naming the role and the key. A typo never becomes a default.

## 2. Roles and their kinds

The engine never matches a role by its name: it matches the `kind` the contract gives it, and every row that asks a
question about "the peak" asks it of the sections whose kind is `peak`.

| Role | Kind | Must state | May state (short list) |
|---|---|---|---|
| `place` | setup | `arousal_max` | `waive_ceiling`, `bsi_mode`, `huron_resolution_gravity` |
| `establish` | setup | - | `arousal_min`, `arousal_max`, `bsi_mode`, `waive_ceiling` |
| `build` | approach | `huron_resolution_gravity` | `strain_slope_min`, `max_resolution_share`, `roughness_min_frac`, `bsi_mode` |
| `transition` | setup | - | `arousal_max`, `waive_ceiling` |
| `peak` | peak | `arousal_min`, `surprise_min_z` | `arousal_step_min`, `min_hits`, `hit_window_ms`, `roughness_min_frac`, `waive_ceiling`, `bsi_mode`, `huron_resolution_gravity` |
| `release` / `resolve` | release | `strain_drop_min`, `huron_resolution_gravity` | `arousal_max`, `bsi_mode`, `waive_ceiling` |
| `rupture` | rupture | `bsi_mode` | `bsi_min`, `arousal_min`, `surprise_min_z`, `allow_intentional_silence`, `waive_ceiling` |
| `button` | setup | `arousal_max` | `waive_ceiling`, `bsi_mode`, `huron_resolution_gravity` |

`resolve` is the spelling several existing sheets already use; it carries the `release` contract. The full key table
with every range is `scene_roles.json` → `keys`.

## 3. What a scene changes in the existing rows

| Row | With a scene block |
|---|---|
| `feel.witek` | a role's `bsi_mode` decides the band: `pocket` (the inverted U, default), `stillness` (`bsi_still_max`), `rupture` (`bsi_rupture_min`, and a rupture may exceed the collapse limit). The `hi..fail_hi` band is a WARN, never a silent pass. |
| `feel.contour` | intervals inside a role whose `waive_ceiling` names `feel.contour` are not judged; the row says how many it left out. |
| `feel.resolution` | per-window gravity: `ENFORCE` (a tension must resolve), `RELAX` (unresolved allowed), `FORBID` (resolving home here is the fault). |
| `roughness` | frames inside a waiving role are dropped from the median/spike judgement and counted in the row's text. |
| `silence` | a gap inside a declared rest is a rest, not a hole; the thresholds are the row's (`min_gap_s`, `floor_dbfs`, `inner_margin_s`). |
| `ambient_bed` | dropouts and pumps inside a declared rest are not judged; `slope_allowance` says how much of the score's own arc a bed may follow. |
| `masking.vs_melody` | inside a declared dialogue window the margin tightens by `margin_db_tight`; `max_collisions` is the FAIL limit (8 was the constant). |

Exemptions are one-directional: a scene can excuse its own window from a whole-piece ceiling, and it can make a
declared rest stricter (it must actually be silent), but no block can switch a row off or move a default.

## 4. The scene rows

| Row | Question | Figures (all in `rows.json`) | Needs |
|---|---|---|---|
| `scene.preset` | does the block validate, and which sheet did it read? | - | the sheet |
| `scene.arc_step` | does a peak stand above the build before it? | `arousal_step_min`, `strain_step_min` | score (Chew strain); a level step is reported when audio exists |
| `scene.hit_surprise` | does a hard hit land on something new? | `surprise_min_z`, `min_hits`, `hit_window_ms`, `delta_min_db` | score (IDyOM IC of the figure lines); a level delta needs audio |
| `scene.release_delta` | does the tension come down into the release? | `strain_drop_min`, `arousal_drop_min` | score |
| `scene.macro_contrast` | does the piece have a range, a tension variance and a roughness contrast? | `min_dynamic_range_lu`, `min_tension_variance`, `min_roughness_contrast_db`, `min_sections`, `force` | tension variance is score-side; the other two need the rendered mix |
| `scene.silence_honoured` | is a declared rest silent in the master? | `max_dbfs`, `min_s` | audio |
| `scene.bed_stability` | do the environment stems rest where the sheet says silence? | `max_dbfs`, `min_s` | audio and an `environment` stem |
| `scene.dialogue_mask` | does the figure keep its ERB margin while a voice speaks? | `margin_db_tight`, `max_fail_share` | stems; emitted by `quality_gate.masking_rows`, where that measurement lives |

A one-section sheet is not asked for contrast: below `min_sections` the row is `INFO` and says so, unless the profile
sets `force: true`. That is the adjustment that keeps a 20-second sting from failing a row written for a three-minute cue.

## 5. Shipped profiles

- `cinematic_suspense` (extends `video_cinematic`): the peak waives roughness, contour and resolution, the build may
  leave tensions open, the release must resolve, a rupture is judged by its own floor.
- `expressive_acoustic` (extends `melodic`): contour and resolution are relaxed to warnings on measured evidence
  (`western_ghats_sunrise` 86-89 % stepwise; `indo_afro_sunrise` resolves 24 of 24 tension notes), with the scene block
  keeping the peak out of the whole-piece ceiling.

Neither carries `detect`, so no existing project changes profile by being rendered. `python scripts/gate_profiles.py
list` shows both; a project declares one with `piece_type`.

## 6. Reading a failure

The gate prints `level row detail`; the detail names the window, the figure and the floor. Before changing anything:

```bash
python scripts/rca.py projects/<piece> --row scene          # what the signal or the score made the row fail
python scripts/gate_feedback.py scene.arc_step              # what to change, and what it costs
python scripts/debug_audio.py projects/<piece> --feedback   # the same table, beside the autopsy
```

A scene row that fails is a fact about the piece or about the sheet: either the music does not do what the sheet says,
or the sheet says something the music was never going to do. The fix is in the notes, the arrangement or the sheet -
`gate_feedback.py` names which - never in the row's number without an `rca.py` verdict of `mismatch`.

## 7. Limits

- The strain figures are Chew's cloud per two bars, computed from the score, not from the master. A performance that
  builds by touch alone is invisible to them; the audio half of `scene.macro_contrast` is the check for that.
- `scene.hit_surprise` needs a figure line of at least `min_line_notes` (8) notes; a percussion-only cue reports "not
  measured", not a pass.
- Roughness contrast is a ratio of the section means in dB, not a listening judgement; the rough section still has to be
  the right kind of rough.
- Nothing here measures taste, and none of these rows can make a flat piece good. They make a flat piece fail a profile
  that asked for contrast.
