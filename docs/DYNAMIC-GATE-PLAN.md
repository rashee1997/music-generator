# Dynamic project- and scene-synced gate plan

Status: IMPLEMENTED (revision 2). Phases P0-P4 are in the tree; the Phase 1 audit below is kept as the record of why.
Deviations from revision 1, all deliberate: the whole-piece contrast floors are the `scene.macro_contrast` row's
parameters rather than a `scene.macro` block (one figure, one home); P1 and P2 landed in one commit because they share
`gate_profiles.py` and `quality_gate.py`; the row table itself moved to
`references/data/presets/gate/data/rows.json` with a `source` per parameter (a citation or "starting value"), which
revision 1 did not ask for and the owner did; `GateFeedback` became `scripts/gate_feedback.py` +
`references/data/presets/gate/data/feedback.json`, wired into `rca.py`, the gate report and `debug_audio.py --feedback`.
New reference: `references/mixing/quality-gate-scenes.md`.

Scope rule that governs every item: **JSON only, no YAML, no new file format**. Every new number goes in a file the
code already reads (`<project>/presets/gate/`, `references/data/presets/gate/`, the project's `direction/*.json`), under
a key validated by `gate_profiles.row_problems` / `profile_problems` with a `(default, lo, hi)` range. No project, track
or piece name in engine code. One verdict, one row list: no second report. A row that cannot fail is not a row, and
nothing here loosens a row that is failing today.

---

## 1. Phase 1 audit

### 1.1 How a row is defined and how its result is consumed

| Stage | Code | What a FAIL does |
|---|---|---|
| 2 preflight (score) | `scripts/preflight_lint.py::full_checks` via `pipeline.py::stage2_preflight_lint` | prints; blocks only with `--strict` |
| 4b stem gate (audio, per stem) | `scripts/stem_gate.py` (`stem.clicks`, `stem.dropout`, `stem.cut`, `stem.end`, `stem.edge`, `stem.tick`, `stem.dead`, `stem.dc`, `stem.flatness`, `stem.present`, `stem.duplicate`, `stem.clipping`, `stem.vocal`) | **hard stop**: `pipeline.py` refuses to mix ("mixing is not allowed until they are fixed") |
| 6 CI suite (master + score) | `scripts/quality_gate.py::run_gate` (line 2059), one list | FAILs counted, exit code 1 |
| 7 package | `pipeline.py::stage7_package_release` | writes `reports/ci_report.json`, `status: PASSED/FAILED` |

One list, one verdict — `run_gate` calls, in order: `score_checks`, `render_checks`, `expression_rows`,
`audio_checks`, `spatial_gate.output_rows`, `master_extra_rows`, then (non-draft) `immersive_rows`,
`immersive2_rows`, `fold_rows`, `ambient_fusion_rows`, `ambience_reference.gate_rows`, `sfx_eval.gate_rows`,
`focus_rows`, `intent_rows`, `balance_rows`, `spatial_separation_rows`, `equal_loudness_rows`, `vocal_rows`,
`chroma_concordance_rows`, `kick_grid_rows`, `soul_rows`, `masking_rows`, `critical_band_rows`, `ear_rows.rows`,
`chem_rows.rows`, `env_rows.rows`, `nc.modulation_flutter_check`, then `metadata_rows`, `direction_rows`.

Definitions live in `scripts/gate_profiles.py`:

- `ROWS` (line 57): **167** row ids, each `{meaning, params{name:(default, lo, hi)}, protected, no_skip, hint}`.
  `protected` (12): `loudness`, `true_peak`, `clipping`, `silence`, `clicks`, `stem.clipping`, `channels`,
  `video.duration_lock`, `video.master_compliance`, `video.gating_mode`, `vocal.integrity`, `render.finite`.
  `no_skip` (6): `stem.clicks`, `pattern.flags_max`, `roughness`, `ambient_bed`, `modulation_flutter`,
  `vocal.perturbation`.
- `ALIASES` (28): reported id -> profile row (`cochlear_roughness`->`roughness`, `erb_binaural_masking`->
  `masking.vs_melody`, `melodic_contour_feel`->`feel.contour`, `witek_groove_curve`->`feel.witek`, ...).
- `resolve(score)` -> `Profile` with `mode(rid)`, `on(rid)`, `param(rid, name)`, `focus_roles()`, `notes()`;
  `_merge_profile` walks `extends`, deep-merges `rows`, `focus` and `expression`; a score's `gate` block merges last.
- `profile_problems` / `row_problems`: mode in `apply|relax|skip`, reason required, params range-checked, protected
  rows cannot be touched, `expression` block validated (`EXPRESSION_RANGES`, `EXPRESSION_KEYS`).
- `project_gate.project_profile_problems`: a project must own `presets/gate/<name>.json` and its score must declare it.

**No generator feedback loop exists.** `fails` only change the exit code and the report; `--max-attempts` prints a stop
rule and nothing re-rolls. `scripts/rca.py` and `scripts/debug_audio.py` read the numbers after the fact;
`scripts/preflight_levels.py` predicts the expensive audio rows before a render. That is the whole coupling.

### 1.2 Inventory by tier (167 rows)

There is **no tier field anywhere** (`ROWS` entries carry `protected`/`no_skip` only). What follows is the classification
the plan will encode in JSON. "Can FAIL" is what the code actually emits today.

**Tier 1 - engineering, hearing and spatial invariants (static, always) — 30 rows**

- Protected master/render: `loudness`, `true_peak`, `clipping`, `silence`, `clicks`, `render.finite`, `channels`.
- Stem gate (blocks the mix): `stem.clicks` (no_skip), `stem.dropout`, `stem.cut`, `stem.end`, `stem.edge`,
  `stem.tick`, `stem.dead`, `stem.dc`, `stem.flatness`, `stem.clipping`, `stem.vocal`, `stem.present`,
  `stem.duplicate`.
- Delivery/geometry: `master.dc`, `delivery.loudness_ceiling`, `delivery.conform`, `iamf.container`,
  `channel.virtual`, `vocal.integrity`, and the reported-only `delivery.true_peak` (`spatial_gate.output_rows` lines
  312/533 - a real invariant that has **no `ROWS` entry**, so today no profile can name it; the tier map records it as
  reported).
- Picture locks: `video.duration_lock`, `video.master_compliance`, `video.gating_mode`.

**Tier 1 by physics, but currently advisory (misfiled) — 6 rows.** These are objectively broken regardless of genre and
should be Tier 1 in the tier map even where the code caps them at WARN today: `lfe.polarity` (comment: "advisory except a
flipped sub"; `scripts/spatial_gate.py::lfe_rows`, `front.fold_phantom`), `imm.foldown`, `mix.band_fold`,
`channel.bars` (isolated channel dropout/polarity flip while the others hold), `front.fold_phantom` (fold-down phase
cancellation), `imm.low_fold`. The plan moves the *declaration*, not the thresholds, and only promotes a row to blocking
where the code can already emit FAIL for it (`channel.bars`, `imm.foldown`, `mix.band_fold`).

**Tier 2 - expressive, cognitive and perceptual style rows (dynamic, 79 rows)**

| Family | Ids (representative) | Current limit |
|---|---|---|
| Contour / Meyer | `feel.contour` (reported `melodic_contour_feel`) | step share, gap-fill, zig-zag |
| Huron | `feel.resolution` (`harmonic_resolution_feel`), `low_interval_mud` (`theory.py:150`, Huron 2001) | unresolved tension share |
| Chew | `feel.spiral` (`spiral_tension_arc`, `_spiral_series`) | momentum, outro strain, concordance |
| Witek | `feel.witek` (`witek_groove_curve`, `bar_syncopation`) | BSI window |
| IDyOM-style | `feel.entropy` (`melodic_information_entropy`), `expr.surprise_grounded` | bits corridor, ungrounded share |
| Plomp-Levelt / Sethares | `roughness` (`nc.cochlear_roughness_check`), `ear.mod_roughness` | median roughness |
| ERB / Moore-Glasberg | `masking.vs_melody` (reported `erb_binaural_masking`), `ear.masking`, `masking.excess` | band margin |
| ISO 3382-1 style room probes | `imm.clarity` (C80 500-4000 Hz), `imm.iacc_early`, `imm.envelopment` (late IACC) | single probe |
| Environmental bed stability | `ambient_bed` (no_skip), `env.loop_stationarity`, `env.diffuse_field`, `env.level_physical` | pump/deviation |
| Structure / patterns | `pattern.*` (9), `shape.contrast`, `pattern.track_flags_max` | flags, distinct share, contrast |
| Arc | `section.energy` (`gate_checks.section_energy`), `emotion.arc_arousal`, `emotion.arc_valence` | rho over sections |
| Balance / space | `balance.vs_lead`, `balance.layers`, `spatial.z_separation`, `spectral.equal_loudness` | dB margins |
| Declarations | `focus.declared`, `intent.vocabulary`, `intent.avoid`, `delivery.*` sheet rows, `key.mode`, `tempo.bpm` | pass/fail |
| Immersive expressive | `imm.cues`, `imm.elevation`, `imm.frontback`, `imm.band`, `imm.height_rules`, `imm.externalization`, `imm.width`, `imm.coloration`, `imm.route_parity`, `imm.kinematics` | per-target |
| Vocal | `vocal.breath`, `vocal.ensemble`, `vocal.intonation`, `vocal.dynamics`, `vocal.ring`, `vocal.perturbation`, `vocal.passaggio`, `vocal.vibrato`, ... (16) | per-row |
| Orchestral | `orch.range`, `orch.voice_leading`, `orch.playable`, `orch.legato` | per-row |
| Chem | `chem.reward_build`, `chem.stress_load`, `chem.motor_drive` (BSI), `chem.recovery`, ... | **never a FAIL** (AGENTS.md) |

**Tier 3 - advisory telemetry (58 rows)**

`ear.*` (5), `chem.*` (10), `master.micro_dynamics`, `master.mono_bands`, `masking.excess`, `expr.ic_profile`,
`expr.tension_ic`, `expr.agogic_coupling`, `emotion.*` (2), `lfe.modal_spread`, `lfe.sum_coherence`, `delivery.standard`
(file half), `pattern.*` INFO paths, `env.cpu_budget`, `sfx`/`ambience_reference` rows, `soul_rows`, `music21_*`,
`mix:*` diagnostics, `stem_rows` note. Rows whose code can only emit INFO/WARN belong here by construction, and several
of them are the only rows that would notice flat, dull, safe music - which is the actual root of the soft-melodic drift.

### 1.3 The soft-melodic bottlenecks, exactly

1. **`pattern_audit.py:360` reads an unregistered row.**
   `mc = (getattr(_gp(score), 'rows', {}) or {}).get('melodic_contour') or {}` then defaults `step_frac 0.45`,
   `step_frac_fail 0.25`, `leap_semis 4.8`, `flip_frac 0.85`. `melodic_contour` is not in `ROWS` (the registered id is
   `feel.contour`), so writing those numbers in a profile is rejected as an unknown row and cannot take effect: the
   four thresholds are hard-coded in practice. Further constants in the same function: `unrecovered_frac > 0.50` (Meyer),
   `abs(diffs[i+1]) >= 3.8`, `flips > 0.75 and step_frac < 0.30`, `stepwise <= 3.2` semitones. A profile can only skip
   the whole row.
2. **Huron is exempted by a type flag, never by the scene.** `pattern_audit.py:484`:
   `if unresolved_ratio > 0.40 and not intent['is_tense']`, with `resolved = leap <= 2.2` (scale-aware `<= 4.2`) and
   `tension_count >= 3`. `intent['is_tense']` comes from `get_intent_profile` (line 278) = the profile's `flags`, i.e.
   once per project. A suspense cue can therefore never fail premature resolution, and a climax cannot forbid it.
3. **Groove: one constant, no stillness or asymmetry mode.** `pattern_audit.py:550`: `pocket_corr < 0.30` FAIL, `< 4 bars`
   INFO, 1-bar/2-bar Pearson autocorrelation of the whole piece. `build_metric_tree` already scores 5/4 and 7/8 (and
   compound metres), but the *decision* (tight pocket vs rubato vs deliberate metric rupture) is a single 0.30.
4. **Witek: three constants, two sources of truth, and a contradictory message.** `pattern_audit.py:782-793`: PASS below
   5.5, WARN `< 0.4`, FAIL `> 5.5`, and the PASS text claims "in [0.4, 4.8]". `chem.motor_drive` carries
   `bsi_lo 0.4` / `bsi_hi 4.8` in `gate_profiles.ROWS`, so 4.9-5.5 passes `feel.witek` with a message that says it is
   outside the window, and two modules own the same figures. No `bsi_mode`: an ambient/rubato scene cannot declare
   `BSI < 0.15` as intended, and a rupture cannot declare `BSI > 5.5`.
5. **Chew is all constants.** `pattern_audit.py:694-737`: static `mean_cm < 0.05` (WARN), teleportation `max_cm > 1.45`
   (FAIL), outro `last_strain > p30 and > 0.50` (FAIL), concordance `r < -0.35`, all skipped when `is_tense` /
   `is_cliffhanger`; `is_cliffhanger` is `dynamics[-1] >= 0.85`, a level, not a scene. This is also the only row that
   sees a static pedal centre, and it reports it as WARN.
6. **Entropy corridor is already right, but one-sided in effect.** `pattern_audit.py:831` reads
   `feel.entropy.min_bits/max_bits` (1.15..4.4): "too low" FAILs, "too high" only WARNs. Nothing measures surprise
   *where it must land* - there is no hit-point term anywhere.
7. **Silence is a protected FAIL with no concept of a declared rest.** `quality_gate.py:754-771`: any run of 1 s under
   -60 dBFS away from start/end is a FAIL, even when `direction` declares `hits[].silence_after_s` (AGENTS.md 4.5) or a
   section whose `music` is silence. Conversely `ambient_bed` (`quality_gate.py:1278`) computes
   `pump_limit = pump_db + 0.5 * slope_db_s` with the 0.5 hard-coded, and also judges the file globally.
8. **Masking is windowed but the margin is global and the verdict is a count.** `quality_gate.py:1042-1150` measures 8 ERB
   bands (300-3900 Hz) over `MASK_WIN_S` windows - the time resolution needed for dialogue already exists - but one
   `margin_db` applies to the whole piece, FAIL is `len(congested) > 8` (a count, not a share of windows), and
   `mix_intent.sits_under` / `video.dialogue` windows are not consulted at all.
9. **The arc rows are correlations only.** `gate_checks.section_energy` (FAIL `rho < 0.5`, WARN `< 0.7`) and
   `affect.rows` (`emotion.arc_arousal`, WARN `rho < 0.6`) rank sections against the sheet's `sections[].energy`. A piece
   can track the curve loosely and still under-deliver every peak; nothing checks a floor, a step between two named
   roles, or whether a `peak` is actually above its `build`.
10. **The only conditioning that exists is a whole-piece flag.** `get_intent_profile` returns
    `is_ambient / is_tense / is_dance / is_cliffhanger`, read at `pattern_audit.py:368,400,484,550,696,706,782,834,839`
    and `naturalness_check.py:582`. This is exactly why a project profile today can only be strict or permissive for its
    entire duration, and why scene intent cannot be expressed.
11. **The rows that would notice safe music cannot fail.** `ear.*` (INFO/WARN by contract), `chem.*` (never FAIL),
    `expr.ic_profile` / `expr.tension_ic` (INFO), `emotion.*` (INFO/WARN). Meanwhile the rows that do block measure
    local defects (clicks, collisions, ranges). The gate is therefore strong on "is this broken" and weak on "is this
    what the scene asked for".
12. **Duplicated limits.** `preflight_levels.ARC_MIN_RHO = 0.5` restates `section.energy.fail_rho`; `chem.motor_drive`
    restates the Witek window; `affect.MIN_SECTION_S` / `CLASH_WEIGHT` are module constants (acceptable: advisory), but
    the first two must read the row.

### 1.4 What is already JSON and reusable (no new format needed)

| Path | Holds | Read by |
|---|---|---|
| `<project>/presets/gate/<piece_type>.json` | `character`, `extends`, `why`, `flags`, `detect`, `focus`, `rows{mode,reason,param}`, `expression{anchors,arousal_order,melody_variety,figure_roles,skip_roles}` | `gate_profiles.resolve`, every row |
| `<project>/presets/gate/chem/{model,moods,genres}.json` | project chem presets | `chem_rows`, `chem_model.config` |
| `references/data/presets/gate/*.json` | shipped types (`melodic` = default, `cinematic`, `ambient`, `tense`, `dance`, `groove`, `texture`, `effects_only`, `video_*`) | `presets.load('gate')` |
| `<project>/direction/*.json` | **the scene timeline that already exists**: `sections[]{name,start_s,end_s,energy,role,action,music}`, `hits_at[]`, `hits[]{t,kind,sync,silence_after_s}`, `expression.cues[]`, `harmony_plan[]`, `mix_intent{hero,sits_under,leave_free_hz}`, `video{cut_sync,dialogue,cuts}`, `piece_type`, `focus`, `intent` | `direction_rows`, `affect.rows`, `gate_checks.section_energy(sheet)`, `project_gate`, `listen.py` |
| `<project>/presets/gate/data/*.json` | `level.json`, `stem_gate.json`, `section_energy.json`, ... | gate + `gate_report.py` |
| `references/data/presets/intent/*` | emotion/register/scene/tension vocabulary | `intent.py`, `intent_rows` |

So: the **SceneTimeline is the direction sheet** (Phase 4 already writes it, `templates/direction_sheet.json` shows the
`role` vocabulary `place/establish/build/peak/transition/button`), the **ProjectGateProfile is the project's gate
profile**, and the scene rules are a new JSON block inside that profile. No YAML, no parallel schema.

---

## 2. Phase 2 - separate the tiers (code, no new verdict)

**P2.0 Tier map as data.** New `references/data/presets/gate/tiers.json`:

```json
{
  "_source": "one place that says what a row is. Every id in gate_profiles.ROWS and every id in ALIASES appears exactly once.",
  "tiers": {
    "1": {"name": "invariant", "blocks": "render-and-stem", "ids": ["loudness", "true_peak", "clipping", "silence", "clicks", "render.finite", "channels", "stem.clicks", "stem.dropout", "stem.cut", "stem.end", "stem.edge", "stem.tick", "stem.dead", "stem.dc", "stem.flatness", "stem.clipping", "stem.vocal", "stem.present", "stem.duplicate", "master.dc", "delivery.true_peak", "delivery.loudness_ceiling", "delivery.conform", "iamf.container", "channel.virtual", "channel.bars", "vocal.integrity", "lfe.polarity", "front.fold_phantom", "imm.foldown", "mix.band_fold", "imm.low_fold", "video.duration_lock", "video.master_compliance", "video.gating_mode"]},
    "2": {"name": "expressive", "blocks": "certification", "ids": ["feel.contour", "feel.resolution", "feel.spiral", "feel.witek", "feel.entropy", "..."]},
    "3": {"name": "advisory", "blocks": "nothing", "ids": ["ear.fatigue", "chem.reward_build", "expr.ic_profile", "..."]}
  }
}
```

The key set is exactly `gate_profiles.ROWS` - the same set `scripts/lint_coverage.py::COVERAGE` already covers, one entry
per row, which is the precedent for this file. Ids a module emits without a profile row go in a second block:
`"reported": {"delivery.true_peak": 1, "audio": 1, "vocal": 2, "true peak": 1, "stem_rows": 3,
"music21_*": 3, "mix:*": 3, "outputs": 1, "expression.preset": 2, "scene.preset": 2, "scene.*": 2}` - so
`delivery.true_peak` (a physical invariant) and `expression.preset` (an existing FAIL) are declared instead of being
invisible, and no row of either kind can be emitted without a tier. (`harmonic_concordance` does not belong here: it is an `ALIASES` key for
`chroma.concordance` and already has a profile row.)

`scripts/gate_tiers.py`: `load()`, `tier_of(rid)` (alias-aware), `problems()` — every `ROWS` id present exactly once,
every `ALIASES` target and every `reported` id resolvable, every Tier 3 id emitted only at INFO/WARN by its owner
(a declared `max_level`), every Tier 1 id either `protected` or measured before the mix. `scripts/lint_coverage.py`
gains that check so a new row without a tier fails CI. No row's code moves.

**P2.1 One scoreboard, split.** `pipeline.stage6_ci_quality_suite` prints the three sections in order
(invariant / expressive / advisory) with the same rows; `stage7` writes `verdict.tiers` into `reports/ci_report.json`.
`gate_report.py` renders the same split. The certification rule stays: 0 FAIL overall.

**P2.2 `scripts/safety_gate.py`** — a Tier-1 runner usable **outside** a project, so a delivered file can be proven
safe without a profile or a sheet: `python scripts/safety_gate.py <wav> [--stems <dir>]`. It calls the owners
(`gate_checks.check_*`, `quality_gate.per_channel_clicks`, `channel_qa`, `spatial_gate.lfe_rows`,
`render_targets.true_peak`) and emits the same row ids. It is **not** called a second time inside a pipeline run; stage 4b
and the certification path stay the ones that block.

**P2.3 Constants that are really profile values (verdict-preserving defaults).** Each new parameter is registered in
`ROWS` with `(default = the constant in the code today, lo, hi)`, so no existing piece changes until its profile says so:

| Where | Today | Becomes |
|---|---|---|
| `pattern_audit.melodic_contour_feel` | reads `rows['melodic_contour']` (unregistered); `0.50`, `3.8`, `0.75`, `0.30` | reads `feel.contour`: `step_frac`, `step_frac_fail`, `leap_semis`, `flip_frac`, `gap_fill_max`, `zigzag_max`, `zigzag_step_frac` |
| `pattern_audit.harmonic_resolution_feel` | `0.40`, `2.2`, `4.2`, `3` | `feel.resolution`: `max_unresolved_share`, `resolve_step_semitones`, `resolve_leap_semitones`, `min_tension_notes` |
| `pattern_audit.groove_pocket_lock` | `0.30`, `4` | `feel.groove`: `min_pocket_corr`, `min_bars` |
| `pattern_audit.witek_groove_curve` | `0.4`, `4.8`, `5.5` | `feel.witek`: `bsi_lo`, `bsi_hi`, `bsi_fail_hi`; `chem_rows.motor_drive` reads the same three |
| `pattern_audit.spiral_tension_arc` | `0.05`, `1.45`, `0.50`, `30`, `-0.35` | `feel.spiral`: `static_momentum`, `teleport_momentum`, `outro_strain_max`, `outro_percentile`, `concordance_min_rho` |
| `quality_gate.audio_checks` | silence `1 s / -60 dBFS`, `0.5 * slope_db_s` | `silence` stays protected (Tier 1) but gains **window exemptions** from the sheet (3.3); `ambient_bed.slope_allowance` |
| `quality_gate.masking_rows` | `len(congested) > 8` | `masking.vs_melody.max_window_share` (share of analysed windows, not a count) + per-window margin classes (3.4) |
| `preflight_levels.ARC_MIN_RHO` | `0.5` | `gate_profiles.param('section.energy', 'fail_rho')` |

**P2.4 Intent flags stop being the only switch.** `get_intent_profile` keeps returning its flags (backward compatible)
but every row that used `is_ambient` / `is_tense` / `is_cliffhanger` to *switch itself off* instead asks the profile or
the scene for the value: `is_ambient` -> `feel.witek.bsi_mode`, `is_tense` -> `huron_resolution_gravity`, `is_cliffhanger`
-> the sheet's last section `role`. Until a profile sets them the resolved value is today's flag, so the verdicts stand.

---

## 3. Phase 3 - the dynamic, project- and scene-synced engine

### 3.1 The `scene` block (new JSON inside the project's gate profile)

Optional. **Absent = today's behaviour exactly** (no new rows, identical reports), so every certified piece stays
certified until its own file says otherwise.

```json
{
  "name": "night_pursuit_cinematic",
  "character": "...",
  "extends": "cinematic",
  "scene": {
    "_source": "the scene contract of this cue. Roles are the direction sheet's section roles; the figures below are measured on this project (presets/gate/data/scene.json) and each one is a floor or a corridor, never an off switch.",
    "timeline": {"sheet": "direction/night_pursuit_cinematic.json", "roles_from_sections": true, "tolerance_s": 0.25},
    "roles": {
      "place":   {"arousal_max": 0.4},
      "build":   {"huron_resolution_gravity": "FORBID", "strain_slope_min": 0.0, "roughness_min_frac": 0.35},
      "peak":    {"arousal_min": 0.6, "roughness_min_frac": 0.55, "surprise_min_z": 1.0, "min_hits": 1, "hit_window_ms": 250},
      "release": {"huron_resolution_gravity": "ENFORCE", "strain_drop_min": 0.15, "allow_intentional_silence": true},
      "rupture": {"bsi_mode": "rupture", "bsi_min": 5.5},
      "button":  {"arousal_max": 0.35, "bow_breath_gap_required": true}
    },
    "dialogue": {"windows_from": "mix_intent.sits_under", "margin_db_tight": 5.0, "min_window_share": 0.8},
    "macro": {"min_dynamic_range_lu": 6.0, "min_tension_variance": 0.02, "min_roughness_contrast_db": 3.0}
  },
  "rows": {},
  "expression": {"...": "unchanged"}
}
```

- Role vocabulary: `references/data/presets/gate/scene_roles.json` (`place`, `establish`, `build`, `peak`, `transition`,
  `button`, `release`, `rupture`) — the sheet template's own roles plus the two the task names. A sheet role that is not
  there, an unknown key, a number outside its range, or a role with no floors is a **FAIL `scene.preset`** (the same
  contract as `expression.preset`), never a silent default. `scene_roles.json` also carries the defaults each role must
  state, so "a profile that declares scenes" cannot omit the floors that make a safe piece fail.
- `huron_resolution_gravity`: `"ENFORCE" | "RELAX" | "FORBID"` — per scene role. `FORBID` turns premature tonic
  arrival in a suspense build into a FAIL (`feel.spiral` outro term + `feel.resolution` at the boundary); `ENFORCE`
  requires the resolution; `RELAX` keeps today's WARN.
- `allow_intentional_silence`: exempts the sheet's declared windows (`hits[].silence_after_s`, a section whose `music`
  says silence, a `release` whose `energy` is 0) from the Tier-1 `silence` row and from `ambient_bed`, within
  `tolerance_s`. The row still FAILs an undeclared hole.
- `bsi_mode`: `"pocket" | "stillness" | "rupture"` — `stillness` accepts `BSI < 0.15`, `rupture` requires
  `BSI > bsi_min`, `pocket` is today's inverted U. Asymmetric metres are already scored by
  `pattern_audit.build_metric_tree`, so 5/4 and 7/8 keep their own metric tree; grouping awareness is the tree, not a new
  number.

### 3.2 Windowed and trajectory evaluation — `scripts/scene_gate.py`

No new DSP. Every windowed series already exists:

| Source | Series |
|---|---|
| `pattern_audit._spiral_series` | Chew strain `T_tss`, cloud momentum, per 2 bars |
| `expectation.analyse` + `expectation.by_bar` | IC and H per note and per bar, per melodic line |
| `affect.arc` / `affect.section_features` | per section: LUFS, onset rate, centroid, mode, clash; composite arousal |
| `nc.cochlear_roughness_check` | roughness metrics per frame |
| `quality_gate.masking_rows` | ERB band excess per `MASK_WIN_S` window across 8 bands |
| `gate_checks.frame_db` / `gate_checks.section_energy` | level per window, dB per section |
| `pattern_audit.bar_syncopation` | BSI (one number, already shared with chem) |

New rows (Tier 2, registered in `ROWS`; each FAILs only where the sheet supplies the data it needs, and says
"not measured: no scene block" as INFO otherwise — a row that could not run is never a pass):

| Row | Measures | Fails when |
|---|---|---|
| `scene.preset` | the block validates against `scene_roles.json` | any invalid key/range/missing floor (FAIL) |
| `scene.arc_step` | arousal and Chew strain of each `peak`/`build` section pair | `peak - build < arousal_step_min` / `strain_step_min` |
| `scene.hit_surprise` | IC z, onset-rate delta and level delta inside `±hit_window_ms` of each `hits[]` entry | a `sync: hard` hit has no spike above `surprise_min_z` / `delta_min_db` |
| `scene.release_delta` | Chew strain and Huron resolution across the `peak -> release` boundary | drop `< strain_drop_min`, or the release ends unresolved when gravity is `ENFORCE` |
| `scene.dialogue_mask` | `masking.vs_melody` windows intersected with the dialogue windows | the tightened margin fails in more than `1 - min_window_share` of dialogue windows |
| `scene.silence_honoured` | level inside each declared silence window | the window is not silent (this is the other half of the exemption: a declared rest must actually rest) |
| `scene.macro_contrast` | whole-piece dynamic range (LU), tension variance, roughness contrast | any below its floor — the anti-flatness row, so a "polite" track fails an action profile |
| `scene.bed_stability` | `ambient_bed` with declared rest windows removed | pumping outside the declared windows only |

`scene.hit_surprise` reuses `expectation` (score side) and `affect.section_features` (audio side): the musical hit is
judged on the notes, the audible hit on the master, and the row reports which of the two was flat.

### 3.3 Floors for existing rows (corridors, not new global strictness)

A floor on a whole piece is the mistake this plan is fixing. Floors therefore live **per scene role** in
`scene.roles`, and a row reads one only when a window of that role exists:

- `roughness_min_frac`: share of a section's frames above `roughness.median_min` (`gate_profiles` gains the parameter,
  range `0.0..0.40` of calibrated median, default `0.0` = today).
- `arousal_min` / `arousal_max` per role: uses the measured `affect` arousal, not a new measurement.
- `surprise_min_z`: a hit needs surprise, not an average.
- `chem.motor_drive` gains `bsi_mode` too, so a stillness scene is not warned for an "optimal" pocket it must not have.
- `feel.entropy` keeps its corridor and gains nothing: it is already two-sided.

### 3.4 Generator coupling - `GateFeedback`

`scripts/gate_feedback.py` writes `<project>/presets/gate/data/feedback.json` from the rows the gate just produced:

```json
{"generated_at": "...", "attempt": 2, "rows": [
  {"row": "scene.hit_surprise", "tier": 2, "window_s": [12.1, 12.7], "role": "peak",
   "measured": -0.4, "target": 1.0, "delta": -1.4, "lever": "anticipate the hit by one 8th, or place the leap on the cut"},
  {"row": "scene.macro_contrast", "tier": 2, "measured": 4.1, "target": 6.0, "delta": -1.9,
   "lever": "mastering.section_levels from the plan energy, or thin the build"}
], "blocked": [{"row": "roughness", "tier": 2, "reason": "pressure and this row conflict: see debug_audio.md"}]}
```

Consumed by `rca.py` (adds the window and the role to each finding), `debug_audio.md` (names the scene role a failing
row belongs to) and `gate_report.py` (prints the directional line instead of a bare FAIL). It never edits a score, and
nothing auto-re-rolls: the contract in AGENTS.md 17d stands.

### 3.5 Profiles: `default_balanced` and two examples (the exact files to create)

`DEFAULT_PROFILE = 'melodic'` is referenced across `gate_profiles`, `project_gate` and the tests, so `default_balanced`
is **documented as the existing `melodic`**, not a rename (a rename would silently re-type every project). The two new
shipped profiles are what the task calls `cinematic_suspense` and `expressive_acoustic`:

`references/data/presets/gate/cinematic_suspense.json`
```json
{
  "name": "cinematic_suspense",
  "character": "a suspense cue: tension is carried and withheld, and a premature homecoming is the fault, not the goal",
  "extends": "cinematic",
  "detect": {"keywords": ["suspense", "thriller", "dread", "stalk"]},
  "scene": {
    "timeline": {"roles_from_sections": true, "tolerance_s": 0.25},
    "roles": {
      "build":   {"huron_resolution_gravity": "FORBID", "strain_slope_min": 0.0},
      "peak":    {"arousal_min": 0.6, "surprise_min_z": 1.0, "roughness_min_frac": 0.5, "min_hits": 1},
      "release": {"huron_resolution_gravity": "ENFORCE", "strain_drop_min": 0.15, "allow_intentional_silence": true}
    },
    "macro": {"min_dynamic_range_lu": 6.0, "min_tension_variance": 0.02, "min_roughness_contrast_db": 3.0}
  },
  "rows": {}
}
```

`references/data/presets/gate/expressive_acoustic.json`
```json
{
  "name": "expressive_acoustic",
  "character": "an intimate acoustic piece: a human line and a breath, where a wide leap or a silence is expression",
  "extends": "melodic",
  "detect": {"keywords": ["intimate", "acoustic", "unplugged", "singer-songwriter"]},
  "scene": {
    "timeline": {"roles_from_sections": true, "tolerance_s": 0.25},
    "roles": {
      "place": {"arousal_max": 0.4, "allow_intentional_silence": true},
      "build": {"huron_resolution_gravity": "RELAX"},
      "peak":  {"arousal_min": 0.55, "surprise_min_z": 0.8},
      "button": {"allow_intentional_silence": true}
    },
    "dialogue": {"windows_from": "mix_intent.sits_under", "margin_db_tight": 4.0, "min_window_share": 0.8},
    "macro": {"min_dynamic_range_lu": 5.0, "min_tension_variance": 0.015, "min_roughness_contrast_db": 2.0}
  },
  "rows": {"feel.contour": {"mode": "relax", "gap_fill_max": 0.6, "reason": "a folk line leaps and recovers late; measured on <project> (verdict mismatch)"}}
}
```

A project profile `extends` one of these and adds nothing but its own measured figures — the pattern
`projects/indo_afro_sunrise/presets/gate/indo_afro_sunrise.json` already uses for `expression`.

---

## 4. Phase 4 - verification

| Test | Asserts |
|---|---|
| `tests/test_gate_tiers.py` | every `ROWS` id and every `ALIASES` id in exactly one tier; no Tier-1 id is `relax`/`skip` in any shipped or project profile; no Tier-3 id is declared blocking; `safety_gate.py` returns the same ids as the pipeline for one fixture |
| `tests/test_scene_timeline_gate.py` (the name `test_scene_gate.py` is taken by the physical-scene ambience test) | scene block validation (`scene.preset`), role vocabulary, hit window, dialogue window tightening, declared silence passes `silence` + `scene.silence_honoured`, undeclared hole still FAILs |
| `tests/test_gate_anti_soft.py` | a soft, consonant, low-roughness, stepwise fixture under `cinematic_suspense` **FAILs** (`scene.macro_contrast`, `scene.hit_surprise`, `roughness_min_frac`); a tense, wide-leap, hit-synced fixture **PASSes**; both run through `tests/gate_fixture.py` |
| `tests/test_gate_no_loosening.py` (existing) | extended over every new parameter: the ranges cannot be widened to "off" |
| `tests/test_lint_coverage.py` (existing) | every new row id is emitted by an owner function |
| `scripts/quality_gate.py` self-test (`main`) | a hyper-syncopated fixture still trips `witek_groove_curve`, and a BSI of 5.0 now fails instead of passing with a contradictory message |
| regression | re-gate `projects/indo_afro_sunrise`, `night_pursuit_cinematic`, `western_ghats_sunrise` with no `scene` block and diff `presets/gate/data/*.json`: rows must be identical to today's |

---

## 5. Order, cost, risk

1. **P0** `tiers.json` + `gate_tiers.py` + lint check — no verdict changes. 1 commit.
2. **P1** constant -> parameter moves (P2.3/P2.4), the `melodic_contour` bug, the Witek message and the two sources of
   truth, `preflight_levels` reading `section.energy`, silence exemptions, masking window share. **Defaults equal
   today's constants**, so the three re-gated projects must diff clean; that diff is the acceptance test. 1-2 commits.
3. **P2** `scene_gate.py` + `scene` schema + `scene.preset` validation + the two shipped profiles. Rows are emitted only
   when a profile declares scenes. 1 commit.
4. **P3** `gate_feedback.py` + `rca.py` / `debug_audio.py` / `gate_report.py` wiring. 1 commit.
5. **P4** tests above, then docs: `references/mixing/quality-gate.md` §3c (scene block), a new
   `references/mixing/quality-gate-scenes.md`, `AGENTS.md` §6 (one bullet per new rule), Phase 4.8 in
   `references/workflow/music-direction.md` (section `role` becomes a checked field, not prose).

Risks and answers:

- **A stricter gate on existing pieces.** No: every new number defaults to the constant in the code, and the scene rows
  are absent without a `scene` block. The regression diff in Phase 4 is the proof.
- **Two sources of truth (Witek/chem, section.energy/preflight).** Resolved in P1 by one row owning each number.
- **Cost.** `masking_rows` already runs per window and per band; `scene.*` reuses series the gate computes once. The only
  new work is arithmetic over existing arrays, plus one JSON read of the sheet.
- **What this plan does not do.** No YAML, no second verdict or report, no auto re-roll, no DSP/HOA/ear physics change, no
  project or track name in engine code, no relaxation of a row that fails today. A `scene` block is a promise the piece
  is judged against; it can make a piece FAIL that passes now, never the reverse without a `relax` carrying a measurement
  and an `rca` verdict of `mismatch`.
