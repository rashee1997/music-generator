# Self-check before you reply

Answer every box with yes/no in `<project>/STATUS.md`, then list in your reply what was **not** checked.
If any box is "no", do not deliver: fix it, or state plainly which step was skipped and why.

- [ ] I read `AGENTS.md` and `SKILL.md`, and every file in my READ TABLE rows.
- [ ] `reports/research_*.md` cites KB `document_id`s AND has web sources with URLs (or says why the web was not needed).
- [ ] Every ambience (`env:`) and tuned effect (`sfx:`) in the score has a "Real-world references: <slug>" section (two sources, licence, measured or ESTIMATE with a reason) and lists the slug in its preset's `sources`. No ambience runs through `sfx:`.
- [ ] If any track plays an SFZ library: it is installed in the project (`sfz_libs.py list`), the credit line is in the project credits, the space has reverb, the render finished inside its timeout (AGENTS.md section 3b.1), and I said the sound is a free sample set and was not auditioned.
- [ ] I chose the gate profile from the brief (Step D2), wrote a project profile if the piece changes character, declared it as `piece_type`, and every relax/skip row has a reason that names a measurement.
- [ ] The direction sheet is complete: `feel` and `avoid_feel`, `sections` that do not overlap, `hits` that agree with `hits_at` (each with a reason), `spatial_staging`, `piece_type`, and a `video` block that is either `enabled: false` or names its picture; the score declares `piece_type` (`gate_profiles.py list`). A flagged row in a tense/ambient/dance/effects piece is explained or fixed, never loosened by hand: change it only through a gate profile with a reason.
- [ ] Every non-built-in instrument or vocal has an exact-name project preset with a real `character`.
- [ ] If the score has a voice: the vocal preset passes `presets.py validate`, phrases leave breathing room, the seven `vocal.*` rows are in the report with no loosened row unexplained, and I said the voice was not auditioned (or `listen.py` ran).
- [ ] The score has `space`, `room`, `mix_preset`; there is no inline EQ or spatial value.
- [ ] The piece's mix preset passes `presets.py validate` (no unknown mix key, no out-of-range value), and every strategy I turned on (`adaptive`, `dsp`, a spectral profile, `sidechain.mode`, a mastering profile) is named in STATUS.md with the measurement that justified it.
- [ ] If the mix was diagnosed (`mixer.py --diagnose`, `mix_and_master(..., diagnose=True)`), every WARN is listed with its cause, no WARN was "fixed" by changing a threshold, and I said the diagnostics measure but cannot hear.
- [ ] If the piece is immersive: its mix preset has the `immersive` block, the space has reflections from 3+ directions, the `imm_*` rows ran, and I said height with a dummy head is weak and not listened to.
- [ ] If the piece was scored to a video file: the four `video.*` rows are in `reports/ci_report.json`, the mux report says `video_identical: true`, `cut_source` is quoted when it is a fallback, and I said the program was not auditioned.
- [ ] `pipeline.py` ended with 0 FAIL; any WARN is listed with its cause.
- [ ] I measured balance (per-track levels), not only the gate.
- [ ] I ran `listen.py`, or I said the ears did not run.
- [ ] A new or changed ambience/effect is a `scene` (or a `model`) in its preset, not a new Python generator; its materials, interactions and calibration are in the preset and `physical.py check` reports no problem. A byte change to an existing sound is intended and explained, or `physical.py verify` still says identical.
- [ ] If the score has a `scene` or `scene_layers` ambience: `physical.py check` passes on every scene, the place has a bed (`scene_layers`, or a continuous mechanism — a one-shot scene alone does not satisfy the gate), and the ambience renders above the mix floor in the `ambient_bed` row.
- [ ] My reply uses the template and lists what was NOT checked.
