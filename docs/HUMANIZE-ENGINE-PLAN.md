# Humanize engine plan

Status: the engine split, the schema fix, tempo-relative spread, pockets, the swing on-beat delay, the
ensemble asynchrony field, cross-track phase coupling (`score.coupling`) and the humanize report are
implemented and tested. Breath/phrase constraints, iterative coupling and a part-to-part coupling network are
not implemented; they are stated as limits rather than approximated.

The engine is `scripts/humanize_engine/`; `scripts/humanize.py` is the facade that keeps every existing
caller working. Rules and module ownership: `AGENTS.md` section 11. The behaviour reference:
`references/mixing/humanization.md`.

## 1. What changed, and why

| # | Change | Why it was needed | Where |
|---|---|---|---|
| 1 | The monolith became a flat package with one module per concern, and a re-exporting facade | the file mixed values, form, tempo, timing, dynamics, articulation and drums; a fix had no obvious home | `scripts/humanize_engine/` |
| 2 | Both cache keys now cover the package | `stem_cache.code_hash` hashes `<package>/*.py`; an edit to the engine could have served a stale stem or a stale gate row | `render_natural._RENDER_PACKAGES`, `stem_gate._gate_code` |
| 3 | `humanize` dicts are schema-checked, and a nested `preset` now selects the base | 92 example instrument presets wrote `"preset": "tight"` and silently played `natural`; unknown keys were no-ops | `config.resolve` |
| 4 | Tempo-relative short-scale spread (`timing_beat_frac`) | measured microtiming is a fraction of the beat (0.026 in funk, 0.068 in swing), not a fixed ms value | `microtiming.py` |
| 5 | Pockets (`pocket`) as data | a pushed or laid-back feel is timing **and** dynamics, per limb and tempo-dependent | `pocket.py`, `references/data/presets/humanize/*.json` |
| 6 | Swing on-beat delay (`swing_downbeat_ms`) | measured swing delays the on-beat note too | `swing.py` |
| 7 | The ensemble asynchrony field (`score.asynchrony`) | the parts of a real ensemble are 20-50 ms apart, with the bass as the reference; the engine had only a shared drift | `ensemble.py`, `timemap.py`, `track.py` |
| 8 | Cross-track phase correction (`score.coupling`) | the asynchrony field gives the spread but no coordination; the measured model is a first-order correction toward the reference. The pre-pass takes the render's own humanize arguments and its curves are cached, so a cached rebuild estimates nothing twice | `coupling.py`, `render_natural._coupling_prepass` |
| 9 | `scripts/humanize_report.py` | "more human" was unfalsifiable: no tempo-adjusted deviation, spread, swing ratio or expressive-performance ratio | `report.py` |

All the opt-in score/track keys default to the old behaviour, so a score that does not ask renders exactly as
before. The renderer version is `natural-10`: `natural-9` was the schema fix (it can change the example
presets that named a base preset) and `natural-10` is the coupling pre-pass.

## 2. The new keys

| Key | Where | Default | Meaning |
|---|---|---|---|
| `preset` | a `humanize` dict | none | the base groove preset; explicit keys then override it |
| `timing_beat_frac` | preset / score / track `humanize` | 0 | short-scale sigma as a fraction of the beat, floored at `timing_ms` |
| `timing_cap_ms` | same | 40 | its cap; drums cap at 10 ms |
| `swing_downbeat_ms` | same | 0 | delay the notes that land on a beat (clipped +/-20 ms) |
| `pocket` | drum track `humanize` | none | a named pocket from `references/data/presets/humanize/` |
| `asynchrony` | score | absent | `{amount_ms}`: one stable signed offset per named part, capped 35 ms |
| `coupling` | score | absent | `{mode: "phase", gain, anchor, window_beats, cap_ms}`: first-order phase correction between parts; each part's curve is in its cache key, the pre-pass itself is cached by score/seed/presets, and an unknown `anchor` is an error |

## 3. Measurement

`python scripts/humanize_report.py <score.json>` prints, per part, the tempo-adjusted deviation in beats
(`sdt`), the lag-1 timing correlation, the velocity/duration correlation, unique velocity levels, the DNVR
and DNODR expressive-performance ratios and an estimated swing ratio, plus the ensemble spread. It is
advisory: it never edits the piece and it is not a gate row. `tests/test_humanize_engine.py` asserts the
features and the measurement's positive and negative controls; the five parity hashes were frozen before
the split so a refactor that moves one float fails.

## 4. Not implemented, and why

- **Iterative and networked coupling.** The implemented correction is first-order: every part is pulled once
  toward one anchor from the onsets they share, with a bounded, smoothed curve. A second pass, a
  part-to-part network (a section following its principal while the principal follows the bass), and per-player
  ensemble jitter in the estimate are not modelled; the curve is recomputed only when the score or seed
  changes, which is what keeps stems cacheable.
- **Breath and hand-span constraints.** The sources found are orchestration practice, not measurements;
  under the project's own rule no number goes in without a research note. A phrase a player cannot play is
  still a documented limit.
- **Error and fatigue models.** Fidelity to the score, no credible measurement, and both would fight the
  `pattern`/`stem` rows.

## 5. Acceptance used

| Feature | Check |
|---|---|
| split | five frozen event hashes unchanged; facade identity; no reverse import; both cache keys include the package |
| schema | an unknown key raises with the known list; `{"preset": "tight", "timing_ms": 9}` keeps 9 and takes `drum_ms` 2 from `tight` |
| tempo-relative | 60 vs 120 BPM absolute spread ratio above 1.6 with the fraction on, below 1.2 off; default identical |
| pocket | laid-back snare later and louder than the hat, pushed hat earlier than the snare, unknown name raises |
| swing delay | every on-beat event moves by exactly the configured ms |
| asynchrony | bass negative, strings positive, deterministic, absent/zero means no field, a named part receives exactly its offset |
| coupling | off by default; a 12 ms late part loses 60% of its RMS deviation and keeps the rest; correction is capped at 25 ms; the anchor is drums then bass; a part with one shared onset gets no curve; the curve is in the cache key and the report |
| report | a humanized line has non-zero deviation; a grid-perfect line is flat with no lag-1 and no swing; a known 10 ms offset reads 10 ms |
