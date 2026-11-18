# Agent prompt: make the mix fast, and make the engine and the quality gate follow the channels that were asked for

Copy everything below the line into the other agent.

---

You are working on the `music-generator` skill. Repository `rashee1997/music-generator`, branch `ccr-3a0c8741-kv7qx8`. Pull that branch first and work and push on the same branch. Do not open a pull request unless asked.

## Read first, in this order
1. `AGENTS.md` (the rules are binding, section 1 and 7 especially) and `SKILL.md`.
2. `projects/palace_chase/reports/mix_profile.md`: a real `cProfile` of a 180 s, 31-stem piece rendered on the ambisonic bus. It is the evidence for part B. Do not trust any earlier synthetic-fixture report that ranks loudness metering first: metering is 1 % of the real render.
3. `references/mixing/quality-gate.md` (sections 3c, 5b), `references/spatial/immersive-deliverables.md`, `scripts/render_targets.py`, `scripts/pipeline.py` (`stage5_mix_and_master`, stage 6, the extra-format loop after certification, `--only`/`--targets`), `scripts/quality_gate.py` (the `fold.*` rows, `delivery.*` rows, `master.dc`, clipping, true peak), `scripts/spatial_engine/render.py` and `hoa.py`.

## The problem, as the user stated it
The user asks for one deliverable (for example only `immersive_7_1_2`). Today the engine still renders and certifies a **stereo** mix first, because the quality gate judges stereo and the other layouts are rendered only after stereo certifies, each as its own full mix pass. That doubles the work (a real run is about 40 minutes: stereo mix about 15 min, gate about 5 min, then the 7.1.2 mix about 15 min) and it renders something the user did not ask for. A previous measurement also showed that a 7.1 file as the **sole** target failed three rows (clipping, true peak, `master.dc`) on its two-channel fold. Fix that properly: no threshold is loosened, no row is skipped.

## Part A: the engine and the gate must look at the channels that are rendered

Goal: when `output_targets` (or `--only`) names no stereo, nothing renders stereo, and the gate certifies the delivered layout itself.

1. **One truth for "what was rendered".** Add a small function (in `render_targets.py` or a new `deliverables.py`) that returns, for a run, the ordered list of delivered targets with their channel count, layout and renderer. Stage 5, stage 6 and the packaging stage all read it. No module guesses from the file name.
2. **Certify the delivered file.** The gate's first deliverable is the first requested target, not an assumed stereo. Rows that are defined per channel (clipping, true peak per channel, DC, dropout, silence, clicks, finite samples, `channels`) are measured on every channel of the delivered file. Loudness uses BS.1770 multichannel with the layout's channel weights, not a stereo fold. Rows that are defined on two ears (stereo correlation, roughness, cochlear roughness, spatial separation on the headphone view) use a **cheap internal downmix of the delivered file** (the engine's own `spatial_engine/downmix.py` and the layout JSON in `presets/layouts/`), computed once and shared, not a second full mix.
3. **`fold.*` and `imm.*` rows** compare the delivered layout with its own folds (to two channels, to mono). They must not need a separately rendered stereo master. If the user did ask for stereo as well, keep today's behaviour (compare with that master).
4. **Name what was measured.** Every row that used a derived view says so in its detail text (for example `measured on the 2-channel fold of immersive_7_1_2`), and the report lists the delivered targets and which were certified.
5. **Protected rows stay protected** (`loudness`, `true_peak`, `clipping`, `silence`, `clicks`, `channels`, `roughness`, `pattern.flags_max`, and the `video.*` protected ones). Do not relax, retune or skip any of them. If the old three failures on a sole 7.1 target reappear, find the cause (most likely a measurement taken on the wrong basis: a fold whose gains clip, a per-channel limit applied to a sum) and fix the measurement or the master chain, not the number.
6. **Prove it can fail.** Add tests with a positive and a negative control per changed row: a clean 7.1.2 file passes, a file clipped on one surround channel fails `clipping`, a file with DC on the height channels fails `master.dc`, a 7.1.2 whose fold cancels fails `fold.mono`.
7. `--only`, `output_targets` in a score and `presets/outputs/_default.json` keep working; `--only stereo` is still the cheapest path; with no flag the default stays stereo plus `immersive_7_1`.

## Part B: speed, in the order the profile supports

The profile (1,417 s total): stage 5 mix 907 s (64 %), of which `HoaBus.field` 760 s, `_reflections` 715 s, `encode` 265 s, `_late` 59 s, loudness metering 10 s. Stage 6 gate 290 s, much of it repeated `sosfilt` in `band_db` (71 s) and `_band_frames` (30 s).

Do these, one at a time, with a before/after timing for each (add `scripts/helpers/bench_mix.py` or extend `scripts/mix_bench.py`; keep the numbers in the commit message):
1. **Reflection loop** (`hoa.py::_reflections`): take one rfft of the source span; per tap multiply by the delay phase, the absorption response, the air response and 1/distance, then one irfft. Pad by the longest delay so nothing wraps. Replaces the `lfilter` plus `fftconvolve` per tap.
2. **Encode once per source**: sum the taps of one source and one room state per harmonic in the frequency domain, so `encode` writes the 36-column field once, not once per tap.
3. **Merge the absorption FIR and the air IR** if step 1 is not used for some branch (the moving-source branch).
4. **Skip taps** below the room's own floor, using a threshold that lives in the space preset (never a constant in the engine).
5. **Gate**: share per-stem band-filtered signals between `band_db`, `_band_frames` and the tier-2 rows; decode the delivered file once and share the `Signal` and the `nc.analyse` / `cochlear_roughness_check` results with stage 7 instead of re-running them (`pipeline.py` lines near 453).
6. Only after the above, and only if the profile still shows it, the processed-stem cache and the multi-format-from-one-processed-set work (stereo plus 7.1.2 share per-stem processing; placement stays per bus).

Do not parallelise more before 1 to 3 are measured, and do not touch Pedalboard board construction (measured about 0 ms).

## Acceptance
* Before and after, on `projects/palace_chase` (the score `scores/the_mayan_palace_score.json`, targets changed to `immersive_7_1_2` only): per-stage timings from the pipeline's `[TIME]` report, and the gate rows byte-identical in id and level, values within 0.01 LU and 0.1 dB. Paste both tables in the final message.
* `python3 -m unittest discover tests` green; new tests per Part A item 6 and per speed step (the faster path equals the old path on a fixture within tolerance).
* `python scripts/lint_coverage.py` and the preflight tests still pass; docs updated (`quality-gate.md`, `immersive-deliverables.md`, `AGENTS.md` 8.4a, `SKILL.md`).
* No project-specific value in the engine; every number that is new lives in a preset with a source or the words "starting value".
* Commit each step with the Co-Authored-By trailer used in this repository, push to `ccr-3a0c8741-kv7qx8` after each green step.

## Report honestly
Say what was measured and what was not. Nothing is auditioned unless `listen.py` ran. If a speed-up changed any gate value beyond tolerance, say so and revert it.
