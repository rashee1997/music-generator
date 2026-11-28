# Realism and impact enhancement plan

Status: PROPOSED (revision 2), nothing implemented. Waiting for approval of the phases (AGENTS.md 1.2).
Trigger: listening critique of `night_pursuit_cinematic` (v10) and `antigravity_theme`.
Revision 2 scope: the fixes must work for **any instrument and any cinematic piece**, not for these two cues; a better default sound bank is part of the plan.

**Generality rule for every item below.** Nothing is keyed on a part name (`horns`, `taiko`). Behaviour is chosen by an instrument **family** (`bowed`, `blown_reed`, `blown_brass`, `struck_membrane`, `struck_pitched`, `plucked`, `voice`, `keys`, `synth`) declared in the instrument preset, with the preset carrying the numbers. The engine today decides by hard-coded name sets (`BOWED`, `SUSTAINED`, `PLUCKED` in `render_natural.py`); P2 moves those into a preset `family` key with a `references/data/presets/families/<family>.json` default (bloom time, flare curve, attack shape, noise layer), so a new instrument (duduk, erhu, sitar, taiko, a clone) gets the right behaviour by declaring a family and nothing else.

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

### 1b. What the installed banks contain (measured, SF2 parsed directly)

Script: a pure-Python RIFF parser that counts the distinct `velRange` generator values (gen 44) behind each General MIDI program in bank 0. A SoundFont can also get brightness from velocity through modulators, so zero zones means "no sample switching", not "no response"; the renderer measurement in 1c below covers the other half.

| Bank | Bank-0 programs with velocity zones | Orchestral programs (violin, viola, cello, bass, pizz, strings, trumpet, trombone, tuba, horns, brass, clarinet, flute, choir, voices, organ, piano) |
|---|---|---|
| MuseScore General | 1 of 128 (9 zones) | **all 0** (a single sample set per instrument) |
| GeneralUser GS | 3 of 128 (4, 4, 20 zones) | **all 0**; only timpani has 20 zones |
| TimGM6mb | 0 of 128 | **all 0** |

Meaning: all three shipped banks are one-layer banks. That is why loud and quiet differ only in volume (critique 5, 6) and why the zone/cutoff emulation added in `render_natural._render_velocity_layers` can only darken a bright sample, never add the missing bright layer. The brass and string stems having no energy above 8 kHz (1) is the same cause: no ff sample was ever recorded in those banks.

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

### 2b. What is missing for cinematic pieces in general (any cue, any instrument)

Checked against the engine and the banks, not against one project:

| Missing | Why it matters for any cinematic cue | Where it is fixed |
|---|---|---|
| Velocity layers in every shipped bank (1b) | loud = quiet but louder; no ff brass or string edge | P-B |
| Articulation patches (spiccato, marcato, sforzando, tremolo, legato, col legno, brass fall) | GM has one sustain, one pizz, one tremolo; the SFZ path has keyswitches but only if a library is installed | P-B (bank map per articulation), existing SFZ path |
| Instrument-family behaviour in presets | bloom, flare, snap are name-keyed in code, so a new instrument gets none | P2 `family` |
| Layered impact and stinger as a preset type | trailers and chases live on hits; today a hit is one sample plus fx | P2 `impact`, P3 stinger |
| Sub synthesis and a stem-to-master band trace | sub can exist in a stem and vanish in the master (measured) | P0, P1 `sub_weight` |
| Air synthesis for band-limited samples | EQ cannot add a band the samples lack | P2 `air` |
| Hybrid layers (risers, braams, pulses) with the orchestra | present as SFX/fx presets, but no rule ties them to a section's declared energy | P3 direction `harmony_plan` and hit classes |
| Section-level dynamic targets | loudness is one integrated number; contrast comes only from arrangement | P4 |
| Harmonic plan and development tools | key raise, sequence, pedal-to-moving-bass, counter-hook not in the direction sheet or `compose.py` | P3 |
| Narrative-voice audibility | one `focus`; secondary hooks (tick, runs, choir) have no floor | P1 `foreground`, direction field `voices_that_must_be_heard` |
| Realism checks that need no project knowledge | dimensions exist, but they judge velocity/vibrato; none judges sub, air, dynamic scale, impact attack | P1 |

## 3. Research (web, search-result text only unless noted)

1. Brass spectral flare. Trombone spectral centroid rises from about 4 (pp) to 11-12 (ff); trumpet fundamental +8 dB over a crescendo while the ninth and higher harmonics rise more than 45 dB; cause is nonlinear propagation ("cuivre"); narrow-bore horns flare at lower levels. Status: starting value. Implication: ff brass must be a different spectrum, not a louder one. https://phys.unsw.edu.au/jw/brassacoustics.html, https://www.ioa.org.uk/system/files/proceedings/s_stevenson_dm_campbell_effects_of_non-linear_propagation_on_timbre_of_brass_instruments.pdf, https://arxiv.org/pdf/1511.04247
2. String vibrato. Sampled and modelled libraries delay vibrato about half a second after each new note and crossfade between non-vibrato and vibrato layers; crossfading libraries are the usual answer for "starts pure, warms up". Status: starting value, product pages and forum posts. https://www.soundonsound.com/reviews/audio-modeling-swam-string-sections, https://www.vsl.co.at/instruments/synchronized/appassionata-strings
3. Impact design. Layer a click (transient), a body (kick/taiko), a sub (below about 60 Hz) and a tail, each band-split and processed apart (bass below 200 Hz, mids to 2 kHz, highs above); a short silence before the hit makes it feel larger. Status: opinion (vendor blogs). https://www.ableton.com/en/blog/learn-how-to-make-high-impact-sounds-for-movies-and-trailers/, https://blog.native-instruments.com/5-quick-tips-for-epic-movie-trailer-impacts/, https://violetrecording.com/sound-design-for-trailers/
4. Cut to silence. Near-silence before the final hit and no material after it so the tail decays alone; an abrupt silence after a climax leaves tension. Status: opinion. https://violetrecording.com/sound-design-for-trailers/, https://www.ujam.com/tutorials/secrets-of-trailer-soundtracks/
5. Ensemble timing. Players push or pull the beat; asynchronies between onsets occur in every performance; leader/follower roles; phase-correction model (already in `humanize_engine/coupling.py`). Status: starting value, abstracts only (Danielsen et al. 2019, Phillips and Sergeant chapter). https://www.cambridge.org/core/books/music-and-time/ensemble-timing-in-string-quartets/B90A1A6261DC3027E294BAFFFF97EB80, https://pmc.ncbi.nlm.nih.gov/articles/PMC5706983
6. Chase writing. A key raise (semitone, whole tone, minor third) on an ostinato lands best with a dramatic switch on screen; violas often carry the pulse; octatonic colour for instability. Status: opinion. https://www.robin-hoffmann.com/?p=1916, https://www.highonfilms.com/string-the-action-action-movie-composition-techniques/
7. Not found: a sourced rule for counter-melody in action cues, an air-band recovery method for band-limited SoundFonts, a figure for how long the silence after an impact should last. These stay "measure first".

No number from this list goes into a preset without the words "starting value" (AGENTS.md rule 16).

## 3b. Free and CC0 bank survey (revision 2)

Constraint found: from this container `github.com`, `api.github.com`, `musical-artifacts.com` and `freepats.zenvoid.org` answer 403/blocked, so **no candidate below was downloaded, loaded or heard**. Everything is "from the web result"; the audit in P-B is what turns it into a fact, on a machine that can fetch.

| Candidate | Format | Licence (web result) | Velocity/dynamics (web result) | Verdict |
|---|---|---|---|---|
| VSCO 2 Community Edition (Versilian) | WAV + SFZ | CC0 1.0 | layer counts not found in results | strongest open orchestral source; needs SFZ path or conversion. https://versilian-studios.com/vsco-community/, https://www.github.com/sgossner/VSCO-2-CE |
| VCSL (Versilian Community Sample Library) | WAV + SFZ | CC0 | draws on VSCO 2 CE; counts not found | broad CC0 source (percussion, ethnic, keys). https://github.com/sgossner/VCSL |
| Sonatina Symphonic Orchestra | SFZ (SF2 build exists) | CC Sampling Plus 1.0, not CC0 | not found; AGENTS.md section 5 already uses it | keep as the SFZ fallback; licence needs attribution and a no-advertising reading. https://github.com/peastman/sso |
| University of Iowa MIS | AIFF mono | "free, no restrictions" per announcement, not a formal licence | three dynamics (pp, mf, ff per file names), anechoic, dry | best real ff/pp source for winds, brass, strings; licence wording must be re-read before shipping a derived bank. https://theremin.music.uiowa.edu/MIS.html |
| CC0 Orchestra compilation (musical-artifacts 5457) | SF2, about 9 MB | CC0 / public domain | small, based on Mini Cheapy Orchestra; no layer data | usable as a CC0 fallback, not a quality upgrade. https://musical-artifacts.com/artifacts/5457 |
| NeoSoundFonts neo-orchestra-hq | SF2 | CC0-1.0 | not found | candidate; lineage of the original is questionable, audit before trusting. https://github.com/NeoSoundFonts/neo-orchestra-hq-realistic-sf2 |
| Freepats | SF2 + SFZ | per instrument, CC0 preferred | per instrument | pick instruments one by one (winds, percussion, ethnic). https://freepats.zenvoid.org/ |
| Aegean Symphonic Orchestra, St. James Orchestra, soundfonts4u set | SF2 | mixed, several CC BY-NC / unclear | some multi-layer | **not eligible** unless a licence file is read: unlicensed = all rights reserved (MuseScore forum guidance). https://sites.google.com/view/hed-sounds/aegean-symphonic-orchestra, https://www.zanderjaz.com/downloads/soundfonts/st-james-orchestra/ |
| MuseScore General | SF2 | MIT | measured: zero zones (1b) | stays as the general GM fallback |

Conversion route for SFZ/WAV sources into one SF2 (so the existing TinySoundFont path plays real velocity layers): ConvertWithMoss (free; reads SFZ and writes SF2, detects velocity layers from file-name patterns, one report of both layers written with the same velocity value, so verify) or Polyphone's `-1` SFZ-to-SF2 command (a forum thread says there is no real batch mode). Status: web result, unverified. A third route needs no conversion: play the SFZ library through the existing `sfizz_render` path (AGENTS.md section 3b/5), which already supports `xfin/xfout`, `fil_veltrack` and `ampeg_vel2attack`.

## 4. Phases

Each phase ends with a measurement that can fail, so it cannot pass by claim.

**P-B. A default bank with real dynamics (new, first because every other fix sits on top of it).**
1. `scripts/soundbank_audit.py <bank>`: for every program, count `velRange` zones, measure the spectral-centroid slope between a soft and a loud render of the same note (the Timbre-2018 style measure already in `realism_report`), the energy above 8 kHz, the loop quality (sustain click rate) and the pitch coverage. Writes `assets/soundfonts/audit/<bank>.json`. No program number is hard-coded; the audit walks the file.
2. `presets/banks/default.json`: an ordered list **per instrument family** (not per instrument): the first bank whose audited programs for that family meet the thresholds is the default; otherwise the next. A score or preset can still name a bank. Thresholds are starting values until measured on a candidate that passes.
3. `scripts/soundfont_fetch.py` gains candidates from section 3b with licence, URL, checksum and `verified: false` until a licence file is read; it refuses an entry with no licence. Fetch runs where the network allows; here it is blocked and said so.
4. `scripts/soundbank_build.py` (offline, optional): assemble one project-independent `cinematic_default.sf2` from CC0/permissive sources (VSCO 2 CE, VCSL, Iowa MIS, Freepats) by the conversion route above, with a velocity-layer map **per family** (for example three layers for sustained instruments, four to six for struck and plucked), a `LICENSES.md` entry per source, and a rejection of any source without a read licence. The bank is an asset on the user's machine, never committed (it is large and not covered by the repository licence).
5. Default switch: `generaluser_gs` stops being the first choice when an audited bank beats it on the family measures; GeneralUser and MuseScore remain the fallbacks; `TimGM6mb` stays CI-only. A render report prints which bank each family used and the audit numbers, so "it is GM" can never be hidden.
6. Acceptance: on the same score, the new default must beat GeneralUser on the audit (velocity zones greater than 1 for every orchestral family, centroid slope above the one-layer bank's, 8-16 kHz energy above it) and on `realism.velocity_response`. A bank that does not beat them is not made the default.

**P0. Find where the sub and the air go (no engine change).** Run `rca.py`-style stem-to-master band trace for bass_drum, taiko, snare. Output: which stage removes 20-60 Hz and 8-16 kHz. Acceptance: the cause is named with a number. Likely cheap fix lives in the mix preset.

**P1. New realism dimensions (advisory, in `realism_report.py`).** `sub_weight` (20-60 Hz share of the master, and stem-to-master loss), `air` (8-16 kHz share and per-section), `dynamic_scale` (loud vs quiet section LU gap, peak-to-quiet), `impact_attack` (rise time and click-to-body ratio of struck stems), `foreground` (declared narrative voices must sit within N dB of their section's lead), `harmonic_motion` (distinct bass roots and key changes per section). Thresholds are starting values. Tests with positive and negative controls, as for the twelve existing dimensions.

**P2. Sound-side levers (presets and renderer, no project values in the engine).**
- `impact` preset type: click, body, sub, tail layers on one hit, band-split, sub from a sine/pitch-dropped primitive (`sound_model`), not a script.
- Vibrato bloom: `vibrato.bloom` (start depth fraction, ramp time) and `expression` bow/breath noise layer, extending the existing `lfo`/`ou` models in `render_natural.py`.
- Instrument families: a `family` key in the instrument preset and `references/data/presets/families/*.json` (bloom, flare, attack shape, noise layer, default vibrato) replace the name sets in `render_natural.py`; a preset that names no family keeps today's behaviour (default must not change).
- Brass flare (family `blown_brass`): `velocity_timbre` flare model (centroid rises with velocity, harmonic gain above the cutoff) and a diagnosis of why horns and trombones show no response today.
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

0. Phase 5.1 (presets): every instrument preset declares a `family`; the bank for it comes from `presets/banks/default.json` unless the preset names one; the report prints the bank and its audit numbers. A single-layer bank may not be the default for an orchestral family once an audited multi-layer bank is installed. Never name a project part in engine code.
1. Phase 4.9 craft pass: add a seventh answer, the harmonic plan (root and key per section, where the turn is, what the counter-hook is).
2. Phase 4.8: per-part `cues` must say whether the part blooms (vibrato), flares (brass) or snaps (struck), and the preset key that does it.
3. New 9.4i: read the new realism rows (`sub_weight`, `air`, `dynamic_scale`, `impact_attack`, `foreground`, `harmonic_motion`) and report each WARN with the stage that caused it (stem or master, from P0).
4. New constraint row: "A band that the samples do not contain is not fixed by EQ: say so, or synthesise it in a preset."
5. Section 4b (cinematic): the climax stinger rule: a hit that ends a section declares what follows it (silence or tail) in the sheet.
6. Read table: add this plan's reference file under cinematic and orchestral rows once P2 ships.

## 7. Decision needed

Which phases first? Recommended order: **P-B (audit tool and bank list first, then the default switch once a candidate passes), P0, P1** now, then P2, P3, P4. Needed from you: (a) allow `github.com` repository downloads for the CC0 sources (they return 403 from this container; `update_environment` can request the hosts) or fetch the files yourself into `assets/soundfonts/`; (b) confirm the Iowa MIS wording is acceptable as a source (its page says "no restrictions", not a named licence); (c) confirm CC Sampling Plus (Sonatina) is acceptable as a non-default fallback. Previous recommendation, still valid for the measurement phases: P0 and P1 now (cheap, no audio change, tells us which of the nine points are real engine faults and which are arrangement), then P2 impact and bloom, then P3/P4.
