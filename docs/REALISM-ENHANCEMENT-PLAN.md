# Realism and impact enhancement plan

Status: PROPOSED, nothing implemented. Waiting for approval of the phases (AGENTS.md 1.2).
Trigger: listening critique of `night_pursuit_cinematic` (v10) and `antigravity_theme`.

Status labels: **measured** = taken from the real render in this repo; **starting value** = from search-result text only, not yet verified against a full paper; **opinion** = practitioner blog.

## 1. What the measurements say (night_pursuit_cinematic v10 stereo master)

Share of mean spectral power per band, dB relative to the total (FFT 8192, whole file). **Measured.**

| Band | Master | Reading |
|---|---|---|
| 20-60 Hz | -33.2 | almost no sub: the critique is right |
| 60-100 Hz | -14.8 | thin |
| 100-300 Hz | -4.7 | the bulk of the energy: congested |
| 300 Hz-2 kHz | -2.1 | carries the piece |
| 2-8 kHz | -20.9 | dark |
| 8-16 kHz | -42.8 | no air |

Per stem (same method):

- `bass_drum` and `taiko` stems hold their energy at 20-60 Hz (-1.2 / -1.3 dB), yet the master has -33 dB there. The sub is made in the stems and lost between stem and master (mix high-pass, ducking, fade, or the loudness stage). **First thing to find** (RCA, not a guess).
- `horns`, `trombones`, `violins_long`: 8-16 kHz is -56 to -83 dB. The GM samples carry no top end, so an EQ shelf cannot add air. Only synthesis of the missing band can.
- `snare` has real top end (-22.5 dB at 8-16 kHz), so the master loses it too: the master is rolled off, or the snare is too low in the mix.
- Percussion rise time (10 to 90 %) from a crude 2 ms envelope: timpani 10 ms, snare 6 ms, bass_drum/taiko 120-195 ms. Crude, but the low drums rise slowly: no beater click on top of the body.
- Arc report from the previous run: sections -14.7 to -13.3 LUFS against -27.8 in the escape, LRA 12.9 LU, crest 17.3 dB. The loud sections are all one level: contrast is made at the end only.
- Realism report: velocity_response WARN (celli, horns, piano_theme, trombones, tuba, violins_staccato), vibrato WARN (basses flat), low_mid 2.26 WARN.

## 2. Critique mapped to the engine

| # | Critique | What the engine has | Gap |
|---|---|---|---|
| 1 | stiff sustained brass and strings | `vibrato` lfo/ou with `delay_ms`, `expression` bow/breath, `velocity_timbre` zones, `ensemble` | vibrato starts at a fixed depth, no pure-to-warm bloom, no bow noise or breath noise layer, GM brass has one timbre |
| 2 | no sub, congested 100-300 Hz | `sub_drop`, `boom`/`impact` SFX, `inst_eq` low-mid trims, `mix.band_fold` | no sub-layer concept for struck drums, no check that the master keeps what the stem has, no low-mid budget at piece level |
| 3 | static middle, no harmonic turn, no counter-hook | `compose.py`, `arrange.py`, direction `sections`/`motifs`, `intent` | nothing measures harmonic movement per section; craft pass (4.9) asks for an arc but not for a harmonic plan |
| 4 | no stick/mallet bite, no hard stop | `transient` mix key, `enhance_sf2_dynamics` transient shaper (drum, arp only), hits with `sync: hard`/`kind: cut` | no layered impact (click + body + sub + tail) as a preset type, no "hit then true silence" stinger, brass/low drums not transient-shaped |
| 5 | narrow dynamic scale | `loudness`, `mastering.crest_floor_db`, arc_report | arc_report reports; no gate row or realism dimension says "peak sections must beat quiet ones by N LU"; the master loudness stage evens sections |
| 6 | rigid grid, no brass snarl | humanize engine (`timing_ms`, `push_tempo_power`, `ensemble` asynchrony, `coupling`), `velocity_timbre` | no anticipation / bar-end breathing per role, repeated figures quantised, no fortissimo harmonic flare |
| 7 | buried narrative voices | `level_by_role`, `lead_carve`, `balance_rows`, `focus` | only one declared focus; secondary narrative voices (clock tick, violin runs, choir) have no declared audibility floor |
| 8 | shy top end | `inst_eq`, shimmer fx, `realism.openness` (passes at 7.05 on bright SFX) | openness reads the whole mix, not the instrument bands; no air synthesis for band-limited samples |
| 9 | no melodic development | direction `theme` + `variation_plan`, `expression_report` (interval entropy, repeated bars) | no key-change or sequence tool, no per-section root-count measure |

## 3. Research (web, search-result text only unless noted)

1. Brass spectral flare. Trombone spectral centroid rises from about 4 (pp) to 11-12 (ff); trumpet fundamental +8 dB over a crescendo while the ninth and higher harmonics rise more than 45 dB; cause is nonlinear propagation ("cuivre"); narrow-bore horns flare at lower levels. Status: starting value. Implication: ff brass must be a different spectrum, not a louder one. https://phys.unsw.edu.au/jw/brassacoustics.html, https://www.ioa.org.uk/system/files/proceedings/s_stevenson_dm_campbell_effects_of_non-linear_propagation_on_timbre_of_brass_instruments.pdf, https://arxiv.org/pdf/1511.04247
2. String vibrato. Sampled and modelled libraries delay vibrato about half a second after each new note and crossfade between non-vibrato and vibrato layers; crossfading libraries are the usual answer for "starts pure, warms up". Status: starting value, product pages and forum posts. https://www.soundonsound.com/reviews/audio-modeling-swam-string-sections, https://www.vsl.co.at/instruments/synchronized/appassionata-strings
3. Impact design. Layer a click (transient), a body (kick/taiko), a sub (below about 60 Hz) and a tail, each band-split and processed apart (bass below 200 Hz, mids to 2 kHz, highs above); a short silence before the hit makes it feel larger. Status: opinion (vendor blogs). https://www.ableton.com/en/blog/learn-how-to-make-high-impact-sounds-for-movies-and-trailers/, https://blog.native-instruments.com/5-quick-tips-for-epic-movie-trailer-impacts/, https://violetrecording.com/sound-design-for-trailers/
4. Cut to silence. Near-silence before the final hit and no material after it so the tail decays alone; an abrupt silence after a climax leaves tension. Status: opinion. https://violetrecording.com/sound-design-for-trailers/, https://www.ujam.com/tutorials/secrets-of-trailer-soundtracks/
5. Ensemble timing. Players push or pull the beat; asynchronies between onsets occur in every performance; leader/follower roles; phase-correction model (already in `humanize_engine/coupling.py`). Status: starting value, abstracts only (Danielsen et al. 2019, Phillips and Sergeant chapter). https://www.cambridge.org/core/books/music-and-time/ensemble-timing-in-string-quartets/B90A1A6261DC3027E294BAFFFF97EB80, https://pmc.ncbi.nlm.nih.gov/articles/PMC5706983
6. Chase writing. A key raise (semitone, whole tone, minor third) on an ostinato lands best with a dramatic switch on screen; violas often carry the pulse; octatonic colour for instability. Status: opinion. https://www.robin-hoffmann.com/?p=1916, https://www.highonfilms.com/string-the-action-action-movie-composition-techniques/
7. Not found: a sourced rule for counter-melody in action cues, an air-band recovery method for band-limited SoundFonts, a figure for how long the silence after an impact should last. These stay "measure first".

No number from this list goes into a preset without the words "starting value" (AGENTS.md rule 16).

## 4. Phases

Each phase ends with a measurement that can fail, so it cannot pass by claim.

**P0. Find where the sub and the air go (no engine change).** Run `rca.py`-style stem-to-master band trace for bass_drum, taiko, snare. Output: which stage removes 20-60 Hz and 8-16 kHz. Acceptance: the cause is named with a number. Likely cheap fix lives in the mix preset.

**P1. New realism dimensions (advisory, in `realism_report.py`).** `sub_weight` (20-60 Hz share of the master, and stem-to-master loss), `air` (8-16 kHz share and per-section), `dynamic_scale` (loud vs quiet section LU gap, peak-to-quiet), `impact_attack` (rise time and click-to-body ratio of struck stems), `foreground` (declared narrative voices must sit within N dB of their section's lead), `harmonic_motion` (distinct bass roots and key changes per section). Thresholds are starting values. Tests with positive and negative controls, as for the twelve existing dimensions.

**P2. Sound-side levers (presets and renderer, no project values in the engine).**
- `impact` preset type: click, body, sub, tail layers on one hit, band-split, sub from a sine/pitch-dropped primitive (`sound_model`), not a script.
- Vibrato bloom: `vibrato.bloom` (start depth fraction, ramp time) and `expression` bow/breath noise layer, extending the existing `lfo`/`ou` models in `render_natural.py`.
- Brass flare: per-part `velocity_timbre` brass flare model (centroid rises with velocity, harmonic gain above the cutoff) and a diagnosis of why horns and trombones show no response today.
- Air: optional `air` fx on the master or per stem (harmonic excitation above 6 kHz of the band that exists), declared in the mix preset; measured by `air`.
- Transient shaper applied to roles beyond drum/arp, by preset key.

**P3. Time and form.**
- Humanize: per-role anticipation and bar-end breath keys, opt-in (AGENTS.md rule 5 of section 11: defaults must not change).
- Stinger support: a hit with `kind: cut` plus a declared `silence_after_s`, checked by the existing hit window; the gate already allows a hard cut inside the +-150 ms window.
- Direction sheet: a `harmony_plan` field (root per section, key change, counter-hook) and a craft-pass question for it; `compose.py` helper for sequence/key raise.

**P4. Dynamic scale in the master.** Section loudness targets from the sheet's `energy` (mastering preset), so loud sections can sit above quiet ones. Collides with the protected `loudness` row and the `dropout`/`master.dc` rows: fix in the arrangement and the preset, never by relaxing.

**P5. Re-render both pieces** and report P1 before/after. Re-render cost is about 45 min per 194 s cue with 8-channel delivery; run when no other heavy tool is running.

## 5. Risks

- Adding sub raises `master.dc` and `fold.timbre` risk and the 8-channel render needs about 10 GB; run one heavy job at a time.
- Air synthesis can read as hiss; it is advisory and measured per section, never applied by default.
- Deeper dynamic contrast may fight the protected loudness row; the cue-level target stays -16 LUFS integrated, contrast comes from section shape.
- Thresholds are starting values; nothing here claims to say the result sounds better. `listen.py` and a human ear remain the judge.

## 6. Proposed AGENTS.md changes (applied with the phases they depend on)

1. Phase 4.9 craft pass: add a seventh answer, the harmonic plan (root and key per section, where the turn is, what the counter-hook is).
2. Phase 4.8: per-part `cues` must say whether the part blooms (vibrato), flares (brass) or snaps (struck), and the preset key that does it.
3. New 9.4i: read the new realism rows (`sub_weight`, `air`, `dynamic_scale`, `impact_attack`, `foreground`, `harmonic_motion`) and report each WARN with the stage that caused it (stem or master, from P0).
4. New constraint row: "A band that the samples do not contain is not fixed by EQ: say so, or synthesise it in a preset."
5. Section 4b (cinematic): the climax stinger rule: a hit that ends a section declares what follows it (silence or tail) in the sheet.
6. Read table: add this plan's reference file under cinematic and orchestral rows once P2 ships.

## 7. Decision needed

Which phases first? Recommended: P0 and P1 now (cheap, no audio change, tells us which of the nine points are real engine faults and which are arrangement), then P2 impact and bloom, then P3/P4.
