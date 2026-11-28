---
title: Quality gate
summary: Every gate row, its threshold, the profile that turns it on, and the lever that fixes a failure.
tags: [gate, threshold, fail, profile, verdict, rows, check]
load_when:
  - a gate row fails
  - choosing or writing a gate profile
---

# The quality gate: bottlenecks in code-made music, what was fixed, and what a gate cannot prove

`scripts/quality_gate.py` is the check a piece must pass before it is called finished. It measures what code can see.
It does not prove that a piece is "100% natural": no code can, and the objective metrics that exist are weak proxies.

## 1. Where code-made music goes wrong

- **Humanising is not random jitter.** Exact quantisation plus constant velocity is what sounds lifeless; real players
  move timing and velocity together, by phrase, which `humanize.py` does.
- **Metrics are weak.** Fréchet Audio Distance depends on sample size, embedding and reference set, and cannot score a
  single piece. The gate measures what is direct (loudness, peaks, gaps, dynamics, repetition) and leaves taste to
  listening.
- **Repetition is the common failure:** copy-paste bars, one loop for the piece, a grid-bound melody. The pattern audit
  counts it.
- **SoundFont limits.** Samples loop, velocity layers are few, starts can click; a microtone or a glide needs its own
  pitch bend, and a MIDI channel carries one bend at a time.

## 2. Bugs the gate work found and fixed (in the renderer)

| Bug | Effect | Fix | Found by |
|---|---|---|---|
| Pitch-bend range assumed ±2 semitones (`bend_value` clipped at 200 cents) | any glide or microtone wider than 200 cents was silently clipped; the KB's talking-drum (+300) and gamaka glides lost their width | `RPN 0` sets the range to ±12 semitones on each microtone channel; `bend_value` scales to it; `STATS['clipped']` counts clips | the self-test: a flute bent 300 cents sounded at 494 Hz under the old range, 524 Hz under the fix (target 523) |
| More notes sounding at once than free MIDI channels (15), with each channel held 0.8 s after a note | a new note's bend moved a note still sounding | `STATS['collisions']` counts it; the gate fails a score that collides | self-test: 20 simultaneous microtone notes give 5 collisions |
| Loudness target not checked against the file | the mixer printed a warning and the file was delivered | the gate reads `master.lufs` from the score and fails a miss of more than 2 LU | the existing samples: −18.2 LUFS against −16, −16.3 against −14 |
| Pattern audit read the score's velocity, not the rendered one | a flat score velocity was reported even though the render adds an arch and noise (`humanize.py`) | the audit reads the score; the render adds the arch | reading `humanize.py` |
| Dead branch `if is_drum: pass` in `humanize.py` | none (no behaviour), but it hid intent | removed | reading the code |
| Click test based on second differences | 841 "clicks" in the desert sample, almost all real drum and bass attacks | a click is an isolated one-or-two-sample jump of more than 0.5 full scale, with 5 ms of quiet on each side; a dense burst (cymbal, shaker) is not a click | measured: the 18 large jumps in that sample sit in one 0.3 s cluster, so they are not counted |

## 3. What the gate checks

Score (no audio): non-finite or out-of-range notes; glides and microtones wider than the synth's range; breath or bow
gaps for winds and bowed parts (WARN); copy-paste and flatness (`pattern_audit`, FAIL at three or more flags).

The seven acoustic rows (`pattern_audit.acoustic_checks`): pitch collisions (the same pitch attacked twice on one beat -
a protected fault, fixed in the score, never relaxed - and a re-attack while it still rings, WARN), chord voicing and
strum, choked resonance, machine-gun percussion (a flat or linear run judged against its own mean), phase-locked flams
(clap/tambourine on a snare sample), low-interval mud (close intervals below F3), dry tracks in a wet score (WARN). Dynamics are judged relative to the
track's mean (5 % sd) and the piece's own dynamics curve (25 % of the mean), so a quiet mood is not failed for being
quiet.

Render (counters from the renderer): clipped bends; shared channels.

Audio (the rendered file): loudness against the score's target (FAIL beyond 2 LU; the naturalness verdicts give WARN
within 2); true peak above the ceiling; a silent gap of one second or more away from the start and end; isolated clicks;
the naturalness verdicts (dynamics range, crest factor, sub energy, mud, harshness).

Ambient fusion (`ambient_fusion_rows`), when environmental soundscapes (water, birds, canopy, rain) are fused into a score:
1. Zero dropouts during the active musical body; the silent floor is relative to the mix (`min(-58, mix level - 38 dB)`).
2. Zero gain pumping or chatter (|delta RMS| between adjacent 0.5 s windows <= 3.8 dB) for steady beds. Sparse event stems
   (calls, drips) FAIL only if fewer than 3 blocks are audible.
3. Shared acoustic space: one room convolution routes instruments and nature together.

Balance (`balance_rows`, any music): active RMS of each accompaniment stem against the loudest track in the piece's focus
(the profile's `focus.roles`, or the score's declared `focus`; `melody`, `lead`, `vocal` by default). Allowed over the
focus: bass and drum +6 dB, chord, pad, counter, arp +3 dB. WARN beyond +3 dB over that, FAIL beyond +6 dB. With no focus
track the row says `INFO: not measured` and names the roles it looked for. Environment and fx stems belong to the ambient rows.

Roughness (`naturalness_check`): only tonal peaks (15 dB over the local spectral floor) are scored, so noise beds are not "rough".

## 3a. Audio Analysis & Objective Measurements (from real-sfx)

1. **Critical-Band Vocal & Speech Masking (`masking_rows`)**:
   - For vocal leads or voice-over, tests the critical speech intelligibility corridor (**250 Hz – 3,800 Hz**). Accompaniment or ambient beds rising within 3 dB of the lead trigger a `WARN` with exact timestamps and offending stems.
2. **Harmonic Chroma Concordance (`chroma_concordance_rows`)**:
   - Pitch classes from `naturalness_check.chroma_analysis`: `librosa.feature.chroma_cqt` (CQT, 36 bins/octave from C2)
     over the **whole** stem at 22.05 kHz, with `librosa.estimate_tuning` correcting the band's tuning, weighted by the
     frames that are sounding (within 40 dB of the loudest) and tonal.
   - Tonality is the peak-prominence rule the roughness model uses (peaks 15 dB over a median-filtered floor holding
     40 % of the frame's energy), not spectral flatness: flatness over the whole band calls *band-limited* noise (rain)
     tonal, because its energy sits in one part of the spectrum.
   - Detects dissonant semitone collisions (minor 2nd intervals against the tonic root or active chord tones). Flags if dissonance energy exceeds 28%.
   - A bed with no tonal content, a silent track, or a machine without librosa is reported `INFO` naming what could not be
     measured, never as concordant. The row used to read one 186 ms FFT frame at the file's midpoint, so a bed that
     stopped before the midpoint produced an all-zero profile and printed "0.0% dissonance" - a pass from no measurement.
3. **Mobile Phone Presence Mono Fold-Down (`mono_phone_loss`)**:
   - Tests mono summing in the 1–5 kHz presence band. Flags if mono cancellation exceeds **-3.5 dB**, catching aggressive Haas stereo wideners before testing on phone speakers.
4. **Kick-Drum Beat-Grid Lock (`kick_grid_rows`)**:
   - Isolates low-frequency drum transients (30–140 Hz) and checks onset arrivals against the score's tempo grid. Verifies that at least 70% of kick onsets land within $\pm 40\text{ ms}$ of the grid.

---

Self-test (`--selftest`): pitch-bend range (measured on audio, fails on the old range); channel collisions; click
detector on a clean tone, a fast-attack kick, an injected jump and a dense burst; the acoustic rules in both
directions (a MIDI-style score trips all five FAIL rules, a composed `motivational` score trips none).

## 3b. Rows added for presets and flutter

- `modulation_flutter` (WARN until calibrated): the 6-25 Hz amplitude flutter of each pad/melody/lead/counter stem on its
  sounding parts. A steady tone scores 0, a 3 Hz sway about 0.01, a 12 Hz tremolo of depth 0.4 scores 0.4. Warns above 0.18.
- Project gate (before rendering): environment presets are the project's own, have a `character` and a bed, use known primitives and keys,
  and no script builds ambience; the score's `space` is a project preset with a `character`. It also prints a `staging` line per track
  (azimuth, distance, route). See `environments-as-presets.md`.

## 3d. Vocal rows (`quality_gate.vocal_rows`, only for tracks the vocal engine rendered)

The engine records what it did (`vocals.LAST`, copied by `render_natural` into `REPORT[track]['vocal']`); the gate reads that
and the raw stem. Seven rows, all in `gate_profiles.ROWS`:

| Row | FAIL / WARN when | Default | Why it exists |
|---|---|---|---|
| `vocal.integrity` (protected) | NaN or Inf, DC offset above `dc_max` (FAIL); soft limiter engaged (WARN) | 0.005 | a stem that cannot be mixed |
| `vocal.clicks` | more than `max_clicks` isolated one-sample jumps in the stem (FAIL) | 0 | a bad join between notes |
| `vocal.breath` | longest phrase past `capacity_s * over_capacity_factor` (WARN) | 1.0 | closes the old "choir breath gaps are not enforced" gap |
| `vocal.ensemble` | 3+ voices with stem correlation above `max_corr` (FAIL) | 0.6 | a "choir" that is one singer copied |
| `vocal.intonation` | mean pitch error above `max_cents` (FAIL), one note above twice that (WARN), vibrato excluded | 60 cents | a voice that does not sing the score |
| `vocal.dynamics` | note level vs velocity correlation below `min_corr` (FAIL) | 0.5 | per-note normalisation or flattened dynamics |
| `vocal.hum_tone` | hum energy above 1.5 kHz over `max_hf_frac` (WARN) | 0.02 | a "hum" that is a bright instrument tone |

Only `vocal.integrity` is protected. The others relax or skip only through a gate profile or the score's `gate` block, with a reason.
`project_gate` also validates vocal presets and a track's `vocal` block (unknown style, register, vowel or expression, out-of-range numbers,
placeholder `character`). Negative controls for every row are in `tests/test_vocal_gate.py`. The rows measure faults. They cannot say whether the
voice sounds human, warm or moving: listen (`listen.py`) and say if it did not run. Detail: `references/instruments-and-vocals/vocal-engine.md`.

## 3e. Rows the score decides (lines, harmony, rhythm)

These read the score, not the render. Fix them in the notes; the threshold is the gate's, not a target to tune.

| Row | Fails when | Lever |
|---|---|---|
| `melodic_contour_feel` | under 45 % of intervals are stepwise (`<= 3` semitones), or direction reverses on nearly every note | rewrite the line as 2-4 note arches in one direction; recover a leap of 5 or more semitones by step in the opposite direction |
| `melodic_information_entropy` | interval entropy under 1.15 bits, or too few distinct interval sizes | use 4-5 interval sizes across the phrase; follow a large surprise leap with 2-3 stepwise notes |
| `pattern.melody_notes` | under 3 note lengths, or 85 % or more of the notes on the beat | mix durations; start some phrases on a pickup |
| `bow.breath_gap` | no rest of 0.15-0.30 beat at phrase ends (at least once every 4 bars) on winds, brass, bowed strings and voices | add the rest at the phrase end |
| `kinematic_effort_feel` | velocity does not rise as the phrase climbs to its peak | raise velocity 5-12 % toward the peak |
| `harmonic_resolution_feel` | a tension note does not resolve by step on the next note, or the last 2 bars do not close on the tonic | resolve by 1-2 semitones; close on the tonic triad unless the cue is a deliberate cliffhanger |
| `spiral_tension_arc` | the tonal centre teleports between sections (momentum over 1.45) | hold a common tone or pedal across the boundary, or insert a pivot chord |
| `groove_pocket_lock` | 1- or 2-bar autocorrelation under 0.30 | keep the figure consistent from bar to bar |
| `witek_groove_curve` | syncopation index (BSI) outside 0.4-5.5 per bar | add off-beat pickups when under; anchor beats 1 and 3 when over |
| `pattern.loop_short` | an ostinato or drum loop runs unchanged for the whole cue | vary it every 4-8 bars; thin or drop the percussion at the peak |
| `erb_binaural_masking` | a bed masks the lead inside one ERB band of 250-4000 Hz | widen the azimuth gap; cut -3 dB at the flagged frequency on the bed |
| `spatial.z_separation` | a midrange pair in the climax is under `min_sep_deg` apart in azimuth and under `min_elev_deg` in elevation (25 and 15 by default) | widen the azimuth to 28 deg, or give the higher part an elevated arc |
| `ambient_bed` | a dropout in the active body, or pumping over 3.8 dB between half-second windows | smooth the gain curve; `release_ms >= 1600`, `duck_db >= -3.5` |
| `focus.declared` | the profile expects a line and no track has 4+ pitched notes in a role it names | write the figure, or declare the `piece_type` and `focus` the piece really has; `effects_only` declares an empty focus |
| `intent.vocabulary` | a declared word resolves to nothing, or to two concepts of one kind | use a word `scripts/intent.py explain` knows, or add the concept and its synonyms |
| `intent.avoid` | a gesture the declaration forbids is in the notes (drum-kit groove, four-on-the-floor, major cadence, sudden jump, and the rest of `intent.MEASURE`) | change the bars, not the declaration; a gesture with no score-side measurement is WARN as unmeasured |

**Focus and intent.** `scripts/roles.py` is the only role list and `scripts/intent.py` the only mood vocabulary; a score
may declare `focus` and an `intent` block, and `compose.py` fills only the fields the brief left empty. A declared focus
that the profile does not judge is a WARN naming both, because the report would apply the wrong rule. A declaration is
never deleted to pass a row. Detail: `references/workflow/intent-and-focus.md`.

## 3f. Rows for how the music is played (`quality_gate._expression_rows`, from `scripts/helpers/expression_report.py`)

No neural model and no audio: the rows read the sheet and the score's notes. Anchors are starting values that no corpus has calibrated, so the measured rows warn and never fail.

| Row | Judges | Result |
|---|---|---|
| `direction.expression` | the sheet's `expression` block (music-direction.md 2.11) | WARN when absent, FAIL when present and incomplete, PASS when complete |
| `expression.arousal_order` | rank correlation (Spearman) between the sections' declared `energy` and an index of tempo, note density, velocity, register and staccato share per section; limit 0.5 | WARN below the limit, INFO under three sections |
| `melody.variety` | the figure track: interval entropy (limit 1.0 bit), range (7 semitones), bars that repeat exactly (60 %), no leap in a long line | WARN on a flag, INFO without a figure track |

The last two rows are measured against the **piece's own figures**, not a module constant: `expression.arousal_order`
and `melody.variety` read the `"expression"` block of the project's gate profile
(`<project>/presets/gate/<piece_type>.json`, merged through `extends`), and inherit these values when the block is
absent. That is where a piece states what it is - a drone cue has no build to rank, a sting is shorter than a phrase,
a through-composed cue has no repeating figure - and the block cannot switch a row off: `min_rho` is bounded away from
0, the identical-bar share away from 1, and a role may not be the figure and be skipped at the same time. An unknown
key, a number outside its range or a role that does not exist is `FAIL expression.preset`. Neither row can FAIL; both
only flag. Judge with the same numbers by hand with
`python scripts/helpers/expression_report.py <score> --direction <sheet> --project <dir>`.

The index follows the cue research (mode, tempo, register, dynamics, articulation, timbre; Gabrielsson and Lindstrom 2010, Eerola, Friberg and Bresin 2013). It measures how hard the written music pushes, not its valence.

## 3g. Pre-render rows (`scripts/preflight_lint.py`, stage 2)

Read from the score and the presets before any audio is made; each was found by a render that failed. FAIL and WARN rows print in stage 2 with the pattern-audit rows. They do not replace the audio rows.

| Row | Level | Judges |
|---|---|---|
| `preflight.range` | FAIL | a note outside the sampled key range of its SFZ patch (silent or stretched); read from the `.sfz` and its includes |
| `preflight.sfx_length` | FAIL | a one-shot event cut before 75 % of its sound plays (event `d`, or the next onset, shorter than the preset's `seconds`): the cut is a click |
| `preflight.section_edge` | WARN | a sparse sound (16 beats or less) that ends in a section with none of its events |
| `preflight.unison` | WARN | two instruments of different families on one pitch above middle C for three beats or more |
| `preflight.figure_level` | WARN | a melody, lead or vocal part that plays mostly the quiet sections: gain staging lifts every figure-family part to full level, so give it the role `counter` |
| `preflight.placement` | WARN | a score-placed sound within 25 degrees in azimuth and 15 in elevation of a part that plays with it |

More rows, from the score alone (`scripts/preflight_levels.py`; estimates, WARN only):

| Row | Judges |
|---|---|
| `preflight.stem_level` | a part quiet twice in a section (velocity and the dynamics curve both under 75 % of usual): the stem gate reads it as `stem.dead` |
| `preflight.arc` | parts playing x velocity x curve per section against the declared section energy (rank correlation under 0.5 is where `section.energy` fails) |
| `preflight.tempo` | a tempo map spanning more than 25 %: `tempo.audio` will fail against one declared value; record a measured skip |
| `preflight.roughness` | two different instruments a second apart for three beats or more (Plomp and Levelt 1965) |
| `preflight.roughness_partials` | the score's hottest frames when every note is given its overtones (`scripts/roughness_forecast.py`); WARN only, a screening model |

One-shot effects, rendered once and judged alone (`scripts/preset_probe.py`): `probe.silent` and `probe.clip` and `probe.start` FAIL; `probe.tail` and `probe.dc` WARN (`probe.dc` is silent when every track that plays the effect sets `dc_hp_hz`).

`focus.declared` and `intent.*` run in stage 2 as well. `scripts/lint_coverage.py` maps every gate row to the rule that catches it before a render, or to the reason only audio can; `tests/test_lint_coverage.py` fails when a gate row is missing from it. `scripts/gate_clock.py` is the one beats-to-seconds conversion for every gate module; `tests/test_gate_clock.py` fails when a gate module reads the flat `bpm` without `# flat-bpm-ok: <why>`.

Limits are starting values from those failures. `python scripts/preflight_lint.py scores/<title>_score.json <project>` runs all of them alone.

## 3c. The gate adapts to the type of piece (gate profiles)

Rules tuned on melodies false-flag a tense drone, an ambient bed, a dance loop or an effects-only piece. So which rows run, and their
numbers, come from a **gate profile**: a preset of kind `gate` (`references/data/presets/gate/`, project `presets/gate/` wins; `scripts/gate_profiles.py`).

- Pick the type: `"piece_type": "tense"` in the score (a list merges in order, later wins; `compose.py` carries it from the brief; the
  direction sheet has the key). Not declared: each profile's `detect` (keywords, pulse words, drone ratio) is matched and the gate prints
  `piece_type: tense (inferred: ...)`. Nothing matches: `melodic`, today's gate. Declare it; keyword inference is a guess.
- **A project uses only its own profile.** Inference and the `melodic` fallback exist for a loose score outside a project. A project
  render is blocked unless the score's `piece_type` names the project's own `presets/gate/<name>.json` (the scaffold writes it into
  the score and the direction sheet): no shipped profile, no inferred one, no default. That profile `extends` the closest shipped
  starter for its numbers and then holds **only the rows this piece needs relaxed, each with a numeric change inside the row's range
  and a written reason that names the measurement** (`gate_profiles.py relax` writes it). An empty `rows` is correct until a render has
  measured a mismatch; a row that is relaxed without a measurement, or only to get past a fault in the notes, is not allowed.
- A profile sets each row to `apply`, `relax` (new numbers) or `skip`, always with a `reason`. `extends` inherits. `flags` (`ambient`,
  `tense`, `dance`) keep the old switches of the feel checks. `fallback: balance.layers` hands a row over when it has nothing to measure
  against (no lead): each layer against the median layer, WARN / FAIL at `warn_db` / `fail_db`.
- Shipped starters: `melodic`, `tense`, `ambient`, `dance`, `cinematic`, `groove`, `texture`, `effects_only`. Their numbers are reasoned
  from the checks' own logic, not a measurement of real pieces. Adjust them with evidence in the project. Each declares a
  `focus` (the roles that may carry it), which the balance and masking rows use as their reference.
- Report ids and profile ids are mapped by `gate_profiles.ALIASES` (`cochlear_roughness` → `roughness`, `kick_grid` → `kick.grid`,
  `harmonic_concordance` → `chroma.concordance`, `spiral_tension_arc` → `feel.spiral`, …). A relax/skip line names both, so a
  relaxed row can be found in the report under either name. `Profile.on/mode/param` accept either id.
- Every row the gate prints has a profile row: the score's acoustic rules (`note_collision`, `chord_voicing_and_strum`,
  `choked_resonance`, `machine_gun_percussion`, `percussion_flam`, `low_interval_mud`, and the orchestral-writing rows
  `orch.range`, `orch.voice_leading`, `orch.playable`, `orch.legato`, `quality-gate-rows.md` section 7), `ambient_bed` and `modulation_flutter`
  included. A row with no profile entry could never be adapted, which meant a type of music the gate could not describe.
- A project profile may not reuse a shipped profile's name (that would retune every piece of that type in the project at once,
  the quiet way to switch the gate off). Give it its own name and `extends` the closest shipped one; the report then says
  which type judged the piece.
- Hard limits: `loudness`, `true_peak`, `clipping`, `silence`, `clicks`, `channels` are protected (no profile or score can touch them);
  `roughness`, `ambient_bed`, `modulation_flutter` and `pattern.flags_max` cannot be skipped; every number has a range (a value
  outside it is an error, because that is loosening, not adapting). A bed may be allowed 6 dB of pump by a profile, never 20. Relax means "a small amount of this is normal", not "off": a dynamics curve that does not move at all is
  still flagged in a dance profile.
- **The repetition rows count parts, and one row asks for contrast.** `pattern.track_flags_max` fails when a single part carries
  two or more of the pattern flags: one part looping for the whole piece is heard as a loop even when every other part varies, and
  the old total could not see it (every shipped piece passed at 5 flags of 6 in the audit that added this row). `pattern.loop_short`
  now judges a part by the share of its bars that differ (`min_distinct_frac`, 15 % by default) instead of requiring a short
  `best_period`, so a one-bar cell under a 96-bar piece is flagged; `pattern.velocity_flat` asks for an sd of 15 % of the part's
  mean velocity, because 5 % sat below every measured performance. `shape.contrast` is the one positive row: it fails when the
  quietest and the loudest plan sections sit within 12 MIDI velocity units of each other AND their densities within 1.6x, which is
  the flat piece that passes every repetition row. A type that loops by design says so in its own profile (`ambient`, `dance`,
  `groove`, `texture`, `tense` and `cinematic` each relax `min_distinct_frac` with a reason), never by switching a row off.
- The report always lists the chosen type, and every relaxed row (`gate_relax`) and skipped row (`gate_skip`) with its reason.
- Per-score one-off: `"gate": {"pattern.flags_max": {"mode": "relax", "max": 9, "reason": "single-take improvisation"}}`.
- **Relaxing is the project profile's job, and it has a command.** After a render has measured a row as failing, and the fix would
  take out what the brief asked for (a release section that is quiet by design, a tail that decays on purpose), write the
  relaxation into the project's own profile:
  `gate_profiles.py relax <row> --project D --set PARAM=VALUE --reason "<why this piece needs it>"`. It refuses a protected row, a
  value outside the row's range (`gate_profiles.py rows` lists the ranges), a row that did not fail in the last render, and a
  one-word reason; it records the measurement in the reason so the report's `gate_relax` line carries it. It is the route for a
  *mismatch between the row's rule and the brief*. It is not the route for a fault: a click, a hole from a note below the
  mastering high-pass, a part that is not there. Those are fixed in the notes or the presets. A number a row does not allow
  (for example a stem that stops 170 ms early, when `stem.edge` allows at most 100 ms) is a fault by definition.
- Commands: `gate_profiles.py list | rows | explain score.json | new <name> --from tense --project D | check`. The project gate runs
  `check`, rejects an unknown `piece_type`, and warns when the type was inferred.

## 3h. Realism measurements are advisory, not rows

`python scripts/realism_report.py out/master.wav --score ... --stems out/stems --project .` measures the twelve (eight of the mix, and four of the parts: vibrato, repeated attacks, velocity response and high-band coherence; `knowledgebase/sound-design/theatrical-realism.md`)
qualities in `knowledgebase/sound-design/theatrical-realism.md`: timbre against loudness, section scatter,
transient variety, direct-to-reverberant depth, low-mid against sub, air absorption at distance, air at density and
bar-scale phrasing. It prints `PASS` / `WARN` / `N/A` per dimension. They are **not** gate rows on purpose: the
thresholds are starting values, several need dry stems the gate may not have, and a WARN is a question for the
director, not a faulty render. Report them beside the gate, never instead of it. The gate rows a theatrical change
actually threatens are `cochlear_roughness` (added harmonics), `masking` and `balance` (a lifted air band), `master.dc`
and `fold.mono` (a low-mid stage), and `loudness` / `true_peak` (the air lift). Fix the part or the preset; never
loosen a row to make the realism report look better.

## 3i. Orchestral writing and intentional cuts

Rows judged from the score alone before any render (`orch.range`, `orch.voice_leading`, `orch.playable`, `orch.legato`) and the
direction sheet's hard cuts (`sync: hard` opens a +-150 ms window in which `stem.cut` and `cut.hard` skip the level drop) are in
[`quality-gate-rows.md`](quality-gate-rows.md) sections 7 and 8.

## 4. What the gate cannot judge

- Whether the phrasing sounds human, whether the style is right, cultural correctness, taste. Listen (`listen.py`,
  earshot) and check the direction sheet.
- Whether a repeated section is intended. A loop-based piece (desert gallop, a test chord loop) will fail the pattern check
  on purpose. The gate reports it; the composer decides.
- Whether a loudness miss matters. A dynamic piece cannot reach a loud target without squashing its crest factor, so a
  miss of 2 LU or more is reported as FAIL and the composer decides whether to lower the target.

## 5. Limits of the measurements

- The loudness and true-peak measures are the skill's own (`naturalness_check.py`), not a certified EBU R128 meter, and
  the click threshold (0.5 of full scale in one sample) is a choice, so a smaller real click is missed.
- `cochlear_roughness` is the Plomp-Levelt kernel on the ten loudest partials in 200 Hz-4 kHz, reduced to the mean of the
  **three strongest pair contributions** per frame, so it measures a clash, not how many parts sound. Only frames whose
  partials hold 40 % of the band's energy are judged (under 6 such frames is not judged, and says so). Calibrated on six
  masters: a clean one reads 0.027 and passes, the same with a semitone cluster at -18 dB reads 0.131 and fails; consonant
  three-, four- and eight-part voicings read 0.041-0.062. Median limit 0.070, and a spike must last (3+ frames, or 2 % of
  the piece), so one drum hit is a WARN. Below 200 Hz a low fifth scores as "rough" in the kernel but is not harsh, so
  that register is left to `low_interval_mud`.
- The silent-gap test looks at 0.25 s windows, so a gap shorter than one second is not reported.

## Deliverable and immersive rows

The rows that judge a delivered format, the immersive probes, the z-axis and mono checks, the extraction gate
and the roughness workflow are in [`quality-gate-rows.md`](quality-gate-rows.md).

### 3i. Cinematic realism rows (advisory, stage 5a)

Six more dimensions in `scripts/realism_cinema.py`, read by `realism_report.analyse`: `sub_weight` (the 20-60 Hz share the stems carry reaches the
master; WARN when the master is thin and has lost more than 6 dB of it), `air` (8-16 kHz share at least -40 dB; band-limited parts named),
`dynamic_scale` (loudest section mean at least 10 dB over the quietest), `impact_attack` (a `drum`-role or `struck_*` part rises in 30 ms
or less, or carries a click above -18 dB), `foreground` (voices in the score's `foreground` list within 12 dB of the loudest part while they
play), `harmonic_motion` (a section over 20 s moves the bass or declares `pedal`). All thresholds are starting values; none can FAIL.
The sheet rows `direction.harmony_plan` and `direction.stinger` are WARN only. Fixes live in presets and notes: `family` blocks, an `air` fx,
`sfx:impact_cinematic`, `mastering.section_levels`, `anticipate_ms`, `bar_breath_ms`.

## 3j. Scenes, thresholds as data, and what to change next

Three files took the last hardcoded judgement out of the engine. None of them adds a verdict: they are read by rows that
already existed or by the scene rows below, and a piece with no scene block is judged exactly as before.

- **Every threshold is data.** `references/data/presets/gate/data/rows.json` holds each row's default, its range or
  choices, its rationale and the `source` that number came from - a citation, or the words "starting value" when no
  published measurement exists. `scripts/gate_profiles.py` builds `ROWS` from it and keeps no second copy;
  `tests/test_gate_thresholds_provenance.py` fails on a number with no provenance and on a default that exists in two
  places. Changing a default is a gate decision and `tests/fixtures/gate/thresholds.json` records it.
- **A scene is the piece's own direction sheet.** A profile may declare `"scene"`, which names the sheet's roles and
  the keys they must state (`references/data/presets/gate/data/scene_roles.json`), and the whole-piece rows that used to
  judge a climax by the piece's median now honour it (`waive_ceiling`, `bsi_mode`, `huron_resolution_gravity`, a declared
  rest). The rows that ask the scene's own questions (`scene.arc_step`, `scene.hit_surprise`, `scene.release_delta`,
  `scene.macro_contrast`, `scene.silence_honoured`, `scene.bed_stability`, `scene.dialogue_mask`) are documented in
  `references/mixing/quality-gate-scenes.md`.
- **A failure says what to change.** `references/data/presets/gate/data/feedback.json` is the one table behind
  `scripts/gate_feedback.py`, `rca.py` ("do next"), `reports/.../feedback.txt` and `debug_audio.py --feedback`: what the
  row asks for, where it is changed, and whether that costs a re-render, a re-performance or a code fix. A tier-1 row
  never falls through to the generic advice.

## 3k. Loud, dense and layered music: what a row may and may not mistake

A row measures a defect. These measurements used to read an arrangement choice as a defect, so a loud, layered or
deliberately silent piece failed for being what it was (the Highway Pursuit cue ended FAILED after 14 attempts, on rows
none of which was a fault in the music). Each is now a row parameter in `rows.json`, set in the project profile with the
measurement as the reason, never in Python:

| Row | Read as a defect before | Parameter | What it does |
|---|---|---|---|
| `roughness` | a median over 0.070 in the default (`legacy`) model, a literal in `naturalness_check.py` | `median_legacy` | the legacy model's median is a profile figure; `median_min` is the `level_aware` model's. The forecast reads the same one. |
| `pattern.velocity_flat` | a spread under 15 % of the part's mean, which asks a part near ff for more than 127 allows | `sd_abs_max` | the demand is capped at 0.09 (11.4 MIDI units: the ASAP 5-95 range of 36.7 divided by 3.29) so only a truly flat loud part is flagged |
| `masking.vs_melody` | more than 8 congested cells, a count that grows with length and number of beds | `max_share` | a FAIL needs the count and this share of the compared cells; either alone is a WARN |
| `stem.tick` | a periodic onset train in a part that is not drums or melody, however the score wrote it | `score_match_share`, `tol_ms` | not a tick when this share of the part's written notes start on that period (or a divisor of it): the pulse is in the score. A defect is not in the score. |
| `stem.dead` | a section more than 12 dB under the sheet's energy ratio, even where the sheet asks for silence | `honour_rests`, `dyn_scale` | a declared rest or a window that waives the row is not judged; `dyn_scale` < 1 states that the bank cannot follow the written ratio (`soundbank_audit.py` reports its velocity layers), with that measurement as the reason |
| `dropout` (master) | a hole of 20-1000 ms anywhere | `honour_rests` | a hole whose middle is inside a rest the sheet declared (`silence_after_s`, `silence_windows`, a section whose words say silence) is the score; `scene.silence_honoured` judges whether the rest is quiet |
| `scene.silence_honoured` | the room tail after the hit that opens the rest, counted as sound | `tail_grace_s` | the level is read after the tail has had this long (0.5 s); the real figure is the space preset's decay |

What is not loosened: clipping (stem and master), true peak, loudness, clicks, DC and the channel rows. A loud brass stem
that clips is turned down at its stem, and the dynamic range the sheet asked for is kept by the other parts rising, not by
flattening velocities (AGENTS 17b).

Shipped genre profiles (`orchestral`, `rock_band`, `hiphop`, `jazz_ensemble`, `world_percussion`, `game_loop`, with
`dance`, `ambient`, `cinematic`, `tense`, `groove`, `texture`) are starting points for structure: where the genre repeats
or layers by design, which rows ask a different question. Their figures are starting values, not measurements of a piece.
`python scripts/setup_project.py --new-project <dir> --title "<Title>" --genre orchestral` makes the project's own profile
`extend` one, so it inherits the rows and states only where the piece departs.

Research behind these figures, and what it did not find: EBU R 128 sets no loudness-range limit and says LRA may be limited
for style or genre, and that it is not recommended for programmes under a minute (EBU Tech 3342, R 128); no published
loudness-range table by genre was found, so no genre profile carries one. Streaming targets (-14 LUFS Spotify and YouTube,
-16 Apple Music, AES TD1008 -16 LUFS music, -1 dBTP) were found only in secondary sources and stay as the delivery profile's
starting values until read from the platforms' own pages. ASAP velocity statistics were not found on the web; the 0.09 cap
is a derivation from the corpus range already cited in `shape.contrast`, not a fitted value.

`python scripts/threshold_audit.py` lists the numbers still compiled into the gate modules; `tests/test_gate_literals.py`
fails when a new one appears. A new threshold goes in `rows.json` with a default, a range and a source.

### 3k.1 Loudness is data and follows the register

The master's loudness used to fall back to -14.0 in `mix_schema.py`, `mastering.py`, `quality_gate.py`, `spatial_gate.py` and
`gate_report.py`: Spotify's normalisation level (`standards.py`), not a mastering default, and not what AGENTS.md says (-16).
It is now `references/data/master_targets.json` (the default and the named profiles, each with its source). Order of
authority: the score's `master.lufs`, a mastering profile the piece's mix preset chose, then the middle of the intersection of
the declared registers' `lufs` bands (`intent.register_loudness`; `cinematic` with `hybrid` is -16.0, `natural` -14.5), then the
shipped default. Registers whose bands do not overlap give no target and the default stands. The band edges are starting values.

### 3k.2 Who decides a loosening

An agent does not loosen, relax, waive or skip a row on its own judgement (AGENTS.md rule 20). The route is: measure (`rca.py`),
try the material fix, and where the verdict is `mismatch` or the fix would cost something very important to the piece, ask the
user with the row, the measured value and limit, the cost of the fix and what the relaxation would hide. On a clear yes, use
`gate_profiles.py relax` (or a scene `waive_ceiling`) with the measurement and the approval in the reason. Protected rows are
never loosened.

### 3k.3 Where a number lives

| Number | Home | Override |
|---|---|---|
| What a row judges a piece by | `references/data/presets/gate/data/rows.json` (default, range, source) | the project profile's `rows`, with a reason (`gate_profiles.py relax`) |
| A window or cut-off a measurement is made with (breath gap, masking window, click step, unison length, roughness spike ratio) | `references/data/presets/gate/data/constants.json` | `<project>/presets/gate/constants.json`, `{"name": value}` |
| The mixer's defaults (gain staging, dynamics, spectral profiles, space, sidechain, master chain, role chains) | `references/data/mix_defaults.json` (every section with its provenance); `mix_schema.py` holds the ranges, enums and validation | the project's own mix preset lists only what the piece changes; `project_gate.mix_preset_problems` requires that preset to be the project's, with a written `character` |
| The master's loudness | score `master.lufs`, the mix preset's profile, the declared registers, then `references/data/master_targets.json` (`default`, `profiles`, per-genre `genres`, `voiceover`) | each step overrides the next |
| A game or film-scene score's states, families and mixing | `references/data/media/game_score.json`, `film_scene_score.json` (read with `scripts/media_profile.py`) | the sheet states the choice |

Algorithm constants (sample rates, filter orders, FFT sizes, epsilons) stay in code and are listed by `scripts/threshold_audit.py`.
