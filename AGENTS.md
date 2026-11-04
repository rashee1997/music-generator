# AGENTS.md — rules for AI agents

Read this file first and follow it.

This file governs ALL music generation work in this skill. Read `SKILL.md` after this.

**You cannot hear.** The pipeline's numbers and `listen.py` are your ears. The first render is a draft. Scripts execute decisions — you make them.

---

## 1. Constraints

These are not negotiable.

| Constraint | Rule | What enforces it |
|---|---|---|
| Sound design stays in presets | Sound and space belong in `presets/`, notes in `scores/`, intent in `direction/`. Do not write synthesis, EQ, mixing logic or sound generation in a Python script. | the gate rejects it |
| Acoustic values are cited or measured | Do not guess formants, tuning, ranges or reverb times. Cite the knowledge base, a research note, or a measurement. | the gate rejects it |
| A failing gate row is a fact | Measure it, fix the score or the presets. Do not loosen a threshold, skip a row or suppress a failure. A profile may relax a row only with measured evidence and a written reason. | hard limits in code |
| Ambience and SFX only when asked | Do not add ambience, rooms or effects unless the user asks for them. | follow exactly |
| A preset needs research first | Every instrument, vocal and culture preset cites knowledge base `document_id`s. | the pipeline blocks without a research note |
| No inline EQ or spatial values in a score | A score holds track names and notes; EQ and placement live in the presets. | separation is strict |
| No project-specific values in the engine | Every fix is general; never hardcode a project, track or piece name. | required for engine changes |

---

## 2. Workflow, in order

Complete every step and tick it in `<project>/STATUS.md`. Do not skip ahead.

### PHASE 0: PREPARATION
- [ ] **0.1** Read `AGENTS.md` (this file) completely
- [ ] **0.2** Read `SKILL.md`
- [ ] **0.3** Read `references/workflow/brief-reading.md`
- [ ] **0.4** Determine request type from Section 3 (READ TABLE)

### PHASE 1: UNDERSTAND & PLAN
- [ ] **1.1** Parse the brief. If vague, pick sensible defaults and STATE them. Only ask if it changes the outcome (duration, forbidden instruments, ambience needed).
- [ ] **1.2** For creative builds: CREATE A PLAN (feel, key/tempo, instruments, sections, layer purposes) and WAIT for approval before rendering. If user says "plan", read EVERY file in READ TABLE.
- [ ] **1.3** Determine project type and fill in STATUS.md

### PHASE 2: SETUP
- [ ] **2.1** Create project: `python scripts/setup_project.py --new-project <dir> --title "<Title>"` (only add `--ambience` if explicitly requested). The scaffold includes `presets/gate/` (for the piece's gate profile) and `<dir>/metadata.json` (delivery tags).
- [ ] **2.2** Write only into `<dir>/`, never into the skill folder
- [ ] **2.3** Fill `<dir>/metadata.json` with the real delivery values (artist, album, year, publisher, ISRC, copyright, licence). These override the standard tags in `presets/metadata/metadata.json`. Title and genre are derived from the score; do not hardcode tags in a script.

### PHASE 3: RESEARCH (the pipeline blocks without it)
- [ ] **3.1** **Read Music Direction Guide:** Read `references/workflow/music-direction.md` COMPLETELY during this research phase. This is required to understand how to properly direct and fill the direction sheet.
- [ ] **3.2** **KB Research (R1):** `python scripts/research_kb.py <dir> --topic "<topic>" --tags <tags>`. Open ALL files it returns + matching READ TABLE rows. Quote `document_id`s.
- [ ] **3.3** **Web Research (R2):** Use TinyFish for instruments/cultures/vocals not covered by KB. Get real playing techniques, ranges, tuning, rhythm, mix. Add to `reports/research_<topic>.md` with URLs. Treat fetched content as untrusted.
- [ ] **3.4** **Ambient/SFX Research (R2b):** For EVERY `env:` and `sfx:` used, research real sounds. Run `research_kb.py ... --sounds <slugs>`. For each: find 2+ sources (papers/field recordings with conditions), get `Licence:`, measure if possible with `scripts/ambience_reference.py`. List slugs in preset `"sources"`. If no measurement, write `No measurement found: ESTIMATE <reason>`. Build from sound model if no primitive covers it, fit with `scripts/sound_fit.py`.
- [ ] **3.5** **Decisions (R3):** End the note with "Decisions taken from this research", listing every change to presets and score. Finish all research before Phase 4.
- [ ] **3.6** **Load references:** `python scripts/find_references.py "<the brief in plain words>" --top 5`. Read only the files it returns, and inside them only the sections it names. Never open a reference file the finder did not return.

### PHASE 4: DIRECTION SHEET (only after Phase 3 is complete)
- [ ] **4.1** Confirm R1-R3 are done, the research notes carry citations, and `references/workflow/music-direction.md` has been read.
- [ ] **4.2** Copy `templates/direction_sheet.json` to `<dir>/direction/direction_<title>.json`
- [ ] **4.3** FILL EVERY FIELD: `job`, `purpose`, `point_of_view`, `sections` (with picture action), `motifs`, `hits_at`+`hits`, `ending`, `feel`, `avoid_feel`, `palette`, `avoid_sounds`, `tempo`, `key/mode`, `energy`, `space`, `mix_intent`, `loudness`, `true_peak_max`, `delivery`, `references` (words only), `spatial_staging`
- [ ] **4.4** If scoring to video, run `scripts/video_score.py` - it fills video block but YOU still write music intent
- [ ] **4.5** Ensure sections don't overlap, hits align with hits_at. Gate rejects otherwise.

### PHASE 5: PRESETS
- [ ] **5.1** Scaffold instruments/vocals: `python scripts/presets.py scaffold instruments|vocals <exact_name> --project <dir>`. Each needs unique `spatial.azimuth/distance`. Fill real `character` sentence (placeholder blocked).
- [ ] **5.2** Scaffold space preset if needed: `python scripts/presets.py scaffold spaces <name> --project <dir>`. Set `space`/`room` in score.
- [ ] **5.3** Scaffold mix preset: `python scripts/presets.py scaffold mix --project <dir>`. **MUST customize it** - defaults are no-ops. Configure per piece needs (ducking, sidechain, mastering.crest_floor_db, inst_eq, etc.). Read `references/mixing/mixing-and-mastering.md` section 8b.
- [ ] **5.4** For immersive: add `"immersive": {"enabled": true, ...}` to mix preset. Set heights in presets to match staging. Bass/drums at 0deg.
- [ ] **5.5** For ambience/env/sfx: follow physical scene rules or layers. Every owned preset must have `"sources"`. Validate with `presets.py validate`.
- [ ] **5.6** For SFZ (only if requested): follow Section 3b exactly.

### PHASE 6: GATE PROFILE
- [ ] **6.1** Choose profile from table or create custom. Check with `python scripts/gate_profiles.py list` and `rows`
- [ ] **6.2** Put `piece_type` in score and direction sheet
- [ ] **6.3** Only relax/skip after measurement with explicit reason. Never relax in advance.

### PHASE 7: SCORE
- [ ] **7.1** Write `<dir>/scores/<title>_score.json`. Tracks reference preset names only. NO inline EQ/spatial.
- [ ] **7.2** Follow all rules in Section 4.

### PHASE 8: RENDER & ITERATE
- [ ] **8.1** Render: `python scripts/pipeline.py <dir>/scores/<title>_score.json --project <dir> --max-attempts 3` (background for long runs)
- [ ] **8.2** Read scoreboard, not early logs. Fix ONE thing at a time based on gate failures. Max 5 attempts.
- [ ] **8.3** For immersive pieces, fix imm_* rows in presets/score, never loosen.

### PHASE 9: DELIVER
- [ ] **9.1** Verify the delivery record: `python scripts/helpers/version_manager.py list --project <dir>`. Every certified render is kept as `out/master_vNN.wav` with its change in `out/versions.json`; `out/master.wav` is a copy of the newest. Never delete or overwrite a version file or a record.
- [ ] **9.2** Metadata: `out/master.json` (written at certification from `presets/metadata/metadata.json` + the score + the project overrides) carries the standard tags. If a tag is wrong, fix `<dir>/metadata.json` and re-run `python scripts/helpers/ingest_metadata.py out/master.wav --project <dir>`; never edit the sidecar by hand.
- [ ] **9.3** MP3 is manual and NOT part of the pipeline: `python scripts/helpers/compress_mp3.py out/master_vNN.wav -o <file>.mp3 -b 320k`. Report the file you produced and its bitrate.
- [ ] **9.5** Listen: `python scripts/listen.py out/master.wav --direction direction/<sheet>.json` (if missing, say so)
- [ ] **9.6** Complete self-check in `references/workflow/self-check.md` in STATUS.md (all yes/no)
- [ ] **9.7** Report: what was done, what was checked, what was NOT checked, gate results, the version number delivered, any limitations. Update STATUS.md.

---

## 3. Read table

Before Phase 4, open every file in the row that matches the request; union several rows when they apply.

| Request type | Open |
|---|---|
| **ANY PIECE** | `SKILL.md`, `references/workflow/brief-reading.md`, `references/workflow/music-direction.md`, `references/spatial/acoustic-laws.md`, `references/mixing/mix-rules.md`, `references/mixing/humanization.md`, `references/mixing/quality-gate.md` |
| **Mood/film/underscore/background** | `references/workflow/scene-recipes.md`, `references/scoring/emotion-and-scoring.md`, `knowledgebase/media/video-scoring.md` |
| **Score video file** | `references/scoring/video-scoring.md`, `scripts/video_score.py`, `video-mixer/` |
| **Named genre (42 built-in)** | `references/scoring/genres-and-moods.md`, `knowledgebase/genre-and-feel/psychoacoustic-genre.md`, `knowledgebase/README.md`, then `python scripts/compose.py --list` |
| **Electronic/EDM (house/techno/trance/future bass/trap/synthpop/D&B)** | Section 4 below + above + `knowledgebase/genre-and-feel/dynamic-flow.md`, `references/mixing/mixing-and-mastering.md`, `references/mixing/blending-and-balance.md` |
| **Indian/Carnatic/Tamil/Hindustani** | `knowledgebase/cultures/pan-indian.md`, `knowledgebase/cultures/tamil.md`, `references/scoring/cultural-soul.md`, `references/scoring/world-music.md`, `references/workflow/director-roles-and-soul.md` |
| **Arabic/Middle East/Desert** | `knowledgebase/cultures/arabic.md`, `knowledgebase/cultures/arabic-desert-vocal.md`, `references/scoring/cultural-soul.md`, `references/scoring/world-music.md` |
| **African/Afro** | `knowledgebase/cultures/african.md`, `knowledgebase/cultures/world-other.md`, `references/scoring/world-music.md`, `references/scoring/cultural-soul.md` |
| **East Asian (Chinese/Japanese)** | `knowledgebase/cultures/chinese-japanese.md`, `references/scoring/world-music.md` |
| **Latin/Brazil/Turkic/Mongol** | `knowledgebase/cultures/brazil-turkic-mongolian.md`, `references/scoring/world-music.md` |
| **Western/classical/folk/country/Celtic** | `knowledgebase/cultures/western.md`, `knowledgebase/cultures/world-other.md`, `references/scoring/world-music.md` |
| **Flutes/wind** | `knowledgebase/cultures/flutes.md`, `references/instruments-and-vocals/natural-instruments.md` |
| **Fusion (2 traditions/genres)** | `references/scoring/genre-fusion.md`, both culture rows, `references/scoring/style-rahman.md` |
| **Vocals/hums/choirs** | `references/instruments-and-vocals/vocals-and-choirs.md`, `references/instruments-and-vocals/vocal-engine.md`, `knowledgebase/cultures/world-other.md`, culture row, `presets/vocals/` preset |
| **Ambience/weather/nature/SFX (if requested)** | `references/spatial/environments-as-presets.md`, `references/sound-design/sound-effects.md`, `references/spatial/physical-scene.md`, `knowledgebase/sound-design/sfx-ambience.md` |
| **Physical sound (breaks/footsteps/rain/knock/creak/scatter)** | `references/spatial/physical-scene.md`, `references/sound-design/sound-effects.md` §2d, `knowledgebase/sound-design/sfx-formulas.md`, `scripts/physical.py laws` |
| **Ad/corporate/VO/podcast** | `knowledgebase/genre-and-feel/commercial-promo.md`, `video-mixer/video_program_mix.py`, `compose.py --voiceover` |
| **Game music/loops/adaptive** | `knowledgebase/media/game-music.md`, `knowledgebase/media/game-sfx.md` |
| **Exact theme/chord sheet/timecodes** | `references/workflow/custom-scripts.md`, `references/workflow/creative-composition.md`, `templates/custom_score_template.py` |
| **Spatial/3D/headphone** | `references/spatial/spatial-presets-and-scoring.md` |
| **Immersive/height/surround** | `references/spatial/immersive-spatial.md`, `references/spatial/spatial-presets-and-scoring.md`, `references/mixing/quality-gate.md` §5b |
| **Clone instrument** | `references/instruments-and-vocals/instrument-cloning.md`, `scripts/clone_instrument.py` |
| **Extract MIDI/stems** | `references/workflow/extraction.md`, `scripts/extract_pipeline.py` |
| **Mix/master existing stems** | `references/mixing/mixing-and-mastering.md`, `scripts/mixer.py`, `scripts/mix_diagnostics.py` |
| **Mix issues/strategy questions** | `references/mixing/mixing-and-mastering.md` §6,§8b, `scripts/mix_schema.py`, `scripts/mix_bench.py` |
| **Full orchestra/SFZ/real samples/library by name** | Section 5 below + `references/instruments-and-vocals/sfz-libraries.md`, `references/instruments-and-vocals/natural-instruments.md`, `references/mixing/mixing-and-mastering.md` |
| **Choose/write gate profile** | `references/mixing/quality-gate.md` §3c, `scripts/gate_profiles.py` (list/rows/explain), Section 6 |
| **Robotic/flat/wrong mood/no beat** | `references/mixing/humanization.md`, `references/instruments-and-vocals/natural-instruments.md`, `references/scoring/emotion-and-scoring.md`, `references/workflow/music-direction.md` |
| **Gate row failed** | `references/mixing/quality-gate.md`, `references/workflow/troubleshooting-and-limits.md` |

If none match, open `knowledgebase/README.md`, ask the reference finder (`python scripts/find_references.py "<the brief>"`), and record the choice in STATUS.md.

---

## 4. ELECTRONIC/EDM SPECIFICS

1. **Archetype from KB** - Don't guess. Use KB archetypes.
2. **Bass/kick first** - One low-end owner. Set `level_by_role`. Use band-limited ducking.
3. **Clear arc** - Intro/build/drop/break/outro. Energy from arrangement, not just volume.
4. **Lane discipline** - Lead 1-3kHz, pads below/wider, arps lower.
5. **Humanize differently** - Tight grid for kick/hats/bass. Tiny velocity variation, rare ghost notes. No rubato. Never repeat identical 2/4 bars.
6. **Mix/master** - Target -14 to -9 LUFS for club/stream (default -16 LUFS, true peak -1.5 dBTP). State and justify.
7. **Fusion** - Keep one pulse, one key center. Traditional = lead, electronic = bed.
8. **Honest limits** - Synthesis from SoundFont/simple synthesis. Don't claim hardware synth sound.

---

## 5. SFZ orchestra (only when requested)

Default is the GM SoundFont. Use SFZ only when the user says "real samples", "full orchestra", "SFZ", or names a library.

1. **State upfront** - Say it's free multisampled (Sonatina SSO), better than GM, not commercial, played by `sfizz_render`. Size ~1.4GB total.
2. **Install in project only** - `sfz_libs.py engine --project <dir>`, then `sfz_libs.py get sso --parts ... --project <dir>`. Verify with `sfz_libs.py check sso --project <dir>` shows 0 missing. Long downloads in background.
3. **Read patches first** - `sfz_libs.py find sso <words>`. Each is instrument preset with `sfz` block. Wrong patch = error, no silent fallback to gm unless user accepts mixed sound.
4. **Own mix/space** - SFZ bright at 3-5kHz and dry. Soften per instrument with `inst_eq`, seat with azimuth/distance, add reverb. Dry SFZ = bug.
5. **Fresh project** - NEVER run `setup_project.py --new-project` on folder with existing presets (overwrites mix). Create folders manually or use fresh folder.
6. **Check ranges** - Verify patch range before writing notes. Notes outside range silent/stretched.
7. **Render via pipeline only** - `pipeline.py <score> --project <dir>`, never shortcut renderer. Measure stems - SFZ quiet (-19 to -28dB), set `trim_db` by measurement.
8. **Report fully** - Library name + license, parts installed, "not auditioned" unless listened.

`sfizz_render` needs `--use-eot` or it renders forever past the end; `scripts/sfz_render.py` passes it with a timeout. Do not call the binary directly without both.

---

## 6. Gate profile selection

| Piece Type | Start From | Notes |
|---|---|---|
| Melody + accompaniment (normal) | `melodic` | All rows on |
| Film cue/build-hit-release | `cinematic` | Falls back to layer balance if no lead |
| Drone/bed/soundscape (no kick) | `ambient` | Loops/holds by design |
| Steady kick + loop layers (genre) | `dance` | Four-on-floor expected |
| Dark/unresolved/suspense (no cadence) | `tense` | SKIPS "resolves to tonic" |
| Effects/ambience only (no notes) | `effects_only` | Note/melody rows don't apply |

- Read brief for demands. If demands conflict with profile flags, don't pick it.
- Mixed situations: create custom profile with `python scripts/gate_profiles.py new <name> --from <closest> --project <dir>`. Can merge with list like `["cinematic", "dance"]`.
- Start strict. Only relax/skip AFTER measurement with reason naming the measurement. Never in advance.
- Hard limits in code: `loudness`, `true_peak`, `clipping`, `silence`, `clicks`, `channels` are protected, and `roughness` and `pattern.flags_max` cannot be skipped. Every number has a range.
- Put `piece_type` in score and direction sheet.
- One-off exceptions go in score as `"gate": {"<row>": {"mode": "relax", "reason": "...", ...}}`

---

## 7. Rules for every piece

1. **Modular** - presets/scores/direction separated. No synthesis/EQ/notes/mixing in one script.
2. **Research first** - No preset for instrument/vocal/culture without KB-cited research.
3. **Spatial separation** - Every instrument has own azimuth/distance. No two tracks same spot.
4. **One hero** - Beds below lead. Rests between phrases.
5. **Harmony checked** - Every long note is chord tone. Avoid semitones against sounding notes (causes roughness). Keep overlaps at chord changes short.
6. **No machine-gun** - No identical 2/4 bar blocks. Vary velocity/timing.
7. **Fades** - Beds/pads fade in/out. Master fades at end. No clicks.
8. **Gate failures are facts** - Measure (per-track LUFS, leave-one-out, spectrum). Balance FAIL = lower track's `gain_db`. Never loosen to pass.
9. **Ambience only on request** - Rooms/ambience are project presets, never shipped.
10. **Faithful reporting** - Say what was/wasn't checked. Didn't listen unless `listen.py` ran. Taste/realism/fit aren't measured.
11. **Backup before editing skill** - Copy to backup location outside the skill folder, no `.venv`. Keep SKILL.md lean, details in references, enforce in code.
12. **Python via venv only** - Skill venv or project's uv venv. Nothing global. Ship .ps1 with .sh.
13. **Mix decisions in presets** - Gain staging, dynamics, spectral, sidechain, space, mastering are in mix preset (`mix_schema.py`). Change in preset, not `mixer.py`. Don't add hardcoded fallbacks for preset keys. Both `legacy` and `adaptive` are valid.
14. **Diagnostics report, don't act** - `mix_diagnostics.py` reports. Never "fix" WARN by loosening thresholds, never let it edit mix, never claim audible improvement from numbers.
15. **Sounds are data** - Materials/geometry/interactions/events go in preset `scene`.
16. **A number needs a status** - Any number added to a knowledge base file carries a source, or the words
    "starting value" on the same line. A new KB file gets a row in `knowledgebase/README.md` and the standard
    header (`document_id`, `target_consumers`, `schema_version`, `status`, `sources`), and
    `python tests/check_kb.py` must pass. Writing new Python generator for new sound name is forbidden. Unknown fields = error, no fallback. No normalization erasing physical intensity differences.

---

## 8. Self-check before the reply

Answer every box in `references/workflow/self-check.md` yes/no in `<project>/STATUS.md`, and list in the reply what was not checked.

**Critical boxes (often skipped):**
- [ ] `pipeline.py` ended with **0 FAIL** (every WARN listed with its cause)
- [ ] Ran `listen.py` OR said ears did not run

If a box is no, fix it or say which step was skipped and why.
