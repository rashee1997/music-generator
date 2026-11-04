# The quality gate: bottlenecks in code-made music, what was fixed, and what a gate cannot prove

`scripts/quality_gate.py` is the check a piece must pass before it is called finished. It measures what code can see.
It does not prove that a piece is "100% natural": no code can, and the objective metrics that exist are weak proxies.

## 1. Research: where code-made music goes wrong

- **Humanising is not random jitter.** Research and production sources (the Soundfly and Reddit threads on humanising
  MIDI) say MIDI sounds lifeless when it is quantised exactly and when velocity is constant. Real players move timing
  and velocity together, by phrase. The skill already does this in `humanize.py` (phrase arch, strum spread, timing
  drift by role).
- **Quantising at 100 % sounds robotic;** 50 % or so sounds human (a production-tips source). The skill uses
  `humanize` presets rather than a fixed grid, so this bottleneck is covered in principle, not measured.
- **Metrics are weak.** The Fréchet Audio Distance (FAD) is the common objective measure for generated music. A 2024
  arXiv study ("Adapting Fréchet Audio Distance for Generative Music Evaluation") finds it depends on sample-size bias,
  the choice of audio embedding, and the reference set. A single piece cannot be scored by FAD at all. So the gate uses
  direct measurements (loudness, peaks, dynamics, gaps, clicks, repetition) and leaves taste to listening.
- **Repetition is the common failure.** The pattern audit (copy-paste bars, one loop for the whole piece, grid-bound
  melody, a march grid) is the most frequent cause of "flat" output. This gate counts it.
- **SoundFont limits.** Soundfont samples loop, have a limited number of velocity layers, and sample starts can
  click. Microtones and glides need a pitch bend per note, and a MIDI channel carries one bend at a time, so a note that
  needs its own bend needs its own channel.

## 2. Bugs the gate work found and fixed (in the renderer)

| Bug | Effect | Fix | Found by |
|---|---|---|---|
| Pitch-bend range assumed ±2 semitones (`bend_value` clipped at 200 cents) | any glide or microtone wider than 200 cents was silently clipped; the KB's talking-drum (+300) and gamaka glides lost their width | `RPN 0` sets the range to ±12 semitones on each microtone channel; `bend_value` scales to it; `STATS['clipped']` counts clips | the self-test: a flute bent 300 cents sounded at 494 Hz under the old range, 524 Hz under the fix (target 523) |
| More notes sounding at once than free MIDI channels (15), with each channel held 0.8 s after a note | a new note's bend moved a note still sounding | `STATS['collisions']` counts it; the gate fails a score that collides | self-test: 20 simultaneous microtone notes give 5 collisions |
| Loudness target not checked against the file | the mixer printed a warning and the file was delivered | the gate reads `master.lufs` from the score and fails a miss of more than 2 LU | the existing samples: −18.2 LUFS against −16, −16.3 against −14 |
| Pattern audit read the score's velocity, not the rendered one | a flat score velocity was reported even though the renderer adds an arch and noise | noted in the audit; the render adds the arch and the noise (`humanize.py`) | reading `humanize.py` |
| Dead branch `if is_drum: pass` in `humanize.py` | none (no behaviour), but it hid intent | removed | reading the code |
| Click test based on second differences | 841 "clicks" in the desert sample, almost all real drum and bass attacks | a click is an isolated one-or-two-sample jump of more than 0.5 full scale, with 5 ms of quiet on each side; a dense burst (cymbal, shaker) is not a click | measured: the 18 large jumps in that sample sit in one 0.3 s cluster, so they are not counted |

## 3. What the gate checks

Score (no audio): non-finite or out-of-range notes; glides and microtones wider than the synth's range; breath or bow
gaps for winds and bowed parts (WARN); copy-paste and flatness (`pattern_audit`, FAIL at three or more flags).

The seven acoustic rows (`pattern_audit.acoustic_checks`, same file as the copy-paste audit): pitch collisions (the
same pitch attacked twice on one beat - a protected fault, FIXed in the score, never relaxed - and a re-attack while
the same pitch still rings, WARN), chord voicing and strum
(flat block chords, an un-strummed guitar), choked resonance (short plucked notes), machine-gun percussion (a flat or
linear run judged against its own mean), phase-locked flams (clap/tambourine on a snare sample), low-interval mud
(close intervals below F3), and dry tracks in a wet score (`spatial_glue`, WARN). Dynamics are judged relative to the
track's mean (5 % sd) and the piece's own dynamics curve (25 % of the mean), so a quiet mood is not failed for being
quiet.

Render (counters from the renderer): clipped bends; shared channels.

Audio (the rendered file): loudness against the score's target (FAIL beyond 2 LU; the naturalness verdicts give WARN
within 2); true peak above the ceiling; a silent gap of one second or more away from the start and end; isolated clicks;
the naturalness verdicts (dynamics range, crest factor, sub energy, mud, harshness).

Ambient fusion (`ambient_fusion_rows`): when environmental soundscapes (water, birds, canopy, rain) are fused into a score:
1. Zero dropouts during the active musical body. The silent floor is relative to the mix: `min(-58, mix level - 38 dB)`.
2. Zero rapid gain pumping or chatter (|delta RMS| between adjacent 0.5s windows <= 3.8 dB) for steady beds.
   Sparse event stems (calls, drips; a quarter of blocks 40 dB under the loudest, no sound over 8 s) are judged as events:
   they FAIL only if fewer than 3 blocks are audible.
3. Shared acoustic space: verifies unified room convolution reverb routing between instruments and nature.

Balance (`balance_rows`, any music): active RMS of each accompaniment stem against the loudest lead (melody/lead/vocal).
Allowed over the lead: bass and drum +6 dB, chord, pad, counter, arp +3 dB. WARN beyond +3 dB over that, FAIL beyond +6 dB.
Environment and fx stems are left to the ambient rows.

Roughness (`naturalness_check`): only tonal peaks (15 dB over the local spectral floor) are scored, so noise beds are not "rough".

## 3a. Audio Analysis & Objective Measurements (from real-sfx)

1. **Critical-Band Vocal & Speech Masking (`masking_rows`)**:
   - For vocal leads or voice-over, tests the critical speech intelligibility corridor (**250 Hz – 3,800 Hz**). Accompaniment or ambient beds rising within 3 dB of the lead trigger a `WARN` with exact timestamps and offending stems.
2. **Harmonic Chroma Concordance (`chroma_concordance_rows`)**:
   - Extracts 12-TET chroma vectors via 8,192-point FFT on ambient soundscapes and background beds.
   - Detects dissonant semitone collisions (minor 2nd intervals against the tonic root or active chord tones). Flags if dissonance energy exceeds 28%.
3. **Mobile Phone Presence Mono Fold-Down (`mono_phone_loss`)**:
   - Tests mono summing in the 1–5 kHz presence band. Flags if mono cancellation exceeds **-3.5 dB**, catching aggressive Haas stereo wideners before testing on phone speakers.
4. **Kick-Drum Beat-Grid Lock (`kick_grid_rows`)**:
   - Isolates low-frequency drum transients (30–140 Hz) and checks onset arrivals against the score's tempo grid. Verifies that at least 70% of kick onsets land within $\pm 40\text{ ms}$ of the grid.

---

Self-test (`--selftest`): pitch-bend range (measured on audio, fails on the old range); channel collisions; click
detector on a clean tone, a fast-attack kick, an injected jump and a dense burst; the acoustic rules in both
directions (a MIDI-style score trips all five FAIL rules, a composed `motivational` score trips none).

## 3b. Rows added for presets and flutter

- `modulation_flutter` (WARN only until calibrated): the 6-25 Hz amplitude flutter of each pad/melody/lead/counter stem, measured on its
  sounding parts. A steady tone scores 0, a 3 Hz sway about 0.01, a 12 Hz tremolo of depth 0.4 scores 0.4. The Amazon flute and pan flute
  stems scored 0.23 and 0.18 before the renderer fixes. Warns above 0.18.
- Project gate (before rendering): environment presets are the project's own, have a `character` and a bed, use known primitives and keys,
  and no script builds ambience; the score's `space` is a project preset with a `character`. It also prints a `staging` line per track
  (azimuth, distance, route). See `environments-as-presets.md`.

## 3d. Vocal rows (`quality_gate.vocal_rows`, only for tracks the vocal engine rendered)

The engine records what it did (`vocals.LAST`, copied by `render_natural` into `REPORT[track]['vocal']`); the gate reads that and the raw
stem. Seven rows, all in `gate_profiles.ROWS`:

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

## 3c. The gate adapts to the type of piece (gate profiles)

Rules tuned on melodies false-flag a tense drone, an ambient bed, a dance loop or an effects-only piece. So which rows run, and their
numbers, come from a **gate profile**: a preset of kind `gate` (`references/data/presets/gate/`, project `presets/gate/` wins; `scripts/gate_profiles.py`).

- Pick the type: `"piece_type": "tense"` in the score (a list merges in order, later wins; `compose.py` carries it from the brief; the
  direction sheet has the key). Not declared: each profile's `detect` (keywords, pulse words, drone ratio) is matched and the gate prints
  `piece_type: tense (inferred: ...)`. Nothing matches: `melodic`, today's gate. Declare it; keyword inference is a guess.
- A profile sets each row to `apply`, `relax` (new numbers) or `skip`, always with a `reason`. `extends` inherits. `flags` (`ambient`,
  `tense`, `dance`) keep the old switches of the feel checks. `fallback: balance.layers` hands a row over when it has nothing to measure
  against (no lead): each layer against the median layer, WARN / FAIL at `warn_db` / `fail_db`.
- Shipped starters: `melodic`, `tense`, `ambient`, `dance`, `cinematic`, `effects_only`. Their numbers are reasoned from the checks' own
  logic, not measured on a corpus of real pieces. Adjust them with evidence in the project.
- Report ids and profile ids are mapped by `gate_profiles.ALIASES` (`cochlear_roughness` → `roughness`, `kick_grid` → `kick.grid`,
  `harmonic_concordance` → `chroma.concordance`, `spiral_tension_arc` → `feel.spiral`, …). A relax/skip line names both, so a
  relaxed row can be found in the report under either name. `Profile.on/mode/param` accept either id.
- Every row the gate prints has a profile row: the score's acoustic rules (`note_collision`, `chord_voicing_and_strum`,
  `choked_resonance`, `machine_gun_percussion`, `percussion_flam`, `low_interval_mud`), `ambient_bed` and `modulation_flutter`
  included. A row with no profile entry could never be adapted, which meant a type of music the gate could not describe.
- A project profile may not reuse a shipped profile's name (that would retune every piece of that type in the project at once,
  the quiet way to switch the gate off). Give it its own name and `extends` the closest shipped one; the report then says
  which type judged the piece.
- Hard limits: `loudness`, `true_peak`, `clipping`, `silence`, `clicks`, `channels` are protected (no profile or score can touch them);
  `roughness`, `ambient_bed`, `modulation_flutter` and `pattern.flags_max` cannot be skipped; every number has a range (a value
  outside it is an error, because that is loosening, not adapting). A bed may be allowed 6 dB of pump by a profile, never 20. Relax means "a small amount of this is normal", not "off": a dynamics curve that does not move at all is
  still flagged in a dance profile.
- The report always lists the chosen type, and every relaxed row (`gate_relax`) and skipped row (`gate_skip`) with its reason.
- Per-score one-off: `"gate": {"pattern.flags_max": {"mode": "relax", "max": 9, "reason": "single-take improvisation"}}`.
- Commands: `gate_profiles.py list | rows | explain score.json | new <name> --from tense --project D | check`. The project gate runs
  `check`, rejects an unknown `piece_type`, and warns when the type was inferred.

## 4. What the gate cannot judge

- Whether the phrasing sounds human, whether the style is right, cultural correctness, taste. Listen (`listen.py`,
  earshot) and check the direction sheet.
- Whether a repeated section is intended. A loop-based piece (desert gallop, a test chord loop) will fail the pattern check
  on purpose. The gate reports it; the composer decides.
- Whether a loudness miss matters. A dynamic piece cannot reach a loud target without squashing its crest factor, so a
  miss of 2 LU or more is reported as FAIL and the composer decides whether to lower the target.

## 5. Limits of the measurements

- The loudness and true-peak measures are the skill's own (`naturalness_check.py`), not a certified EBU R128 meter.
- The click threshold (0.5 of full scale in one sample) is a choice, calibrated on two samples and the synthetic tests.
  A real click smaller than that is missed.
- `cochlear_roughness` is the Plomp-Levelt kernel applied to the ten loudest partials in 200 Hz-4 kHz, reduced to the mean of
  the **three strongest pair contributions** per frame, so it measures a clash and not how many parts are sounding. Only frames
  whose detected partials hold at least 40 % of the band's energy are judged: a frame under 6 such frames is not judged at all
  and says so. Calibrated on six finished masters (a clean master reads 0.027 and passes; the same master with a semitone
  cluster mixed in at -18 dB reads 0.131 and fails) against consonant three-, four- and eight-part voicings (0.041-0.062).
  Median limit 0.070; a spike must also last (3+ frames, or 2 % of the piece), so a single drum hit is a WARN. Below 200 Hz a
  low fifth of two fundamentals scores as "rough" in the kernel but is not harsh, so that register is left to
  `low_interval_mud` and the mix's mud row.
- The silent-gap test looks at 0.25 s windows, so a gap shorter than one second is not reported.

## 5b. Immersive rows (only when the mix preset has `immersive.enabled`)

`imm_cues`, `imm_elevation`, `imm_height_rules`, `imm_externalization`, `imm_foldown` FAIL; `imm_frontback`, `imm_band`, `imm_envelopment`, `imm_width` WARN.
Probes run through the measured-head route the mixer forces, with the numbers from `tests/test_hrtf.py`. What each row means, the height rules and the
limits: `references/spatial/immersive-spatial.md`. A failing row is fixed in the score or presets (raise a pad, give the space a ceiling reflection, lower a bass), never by loosening the row.

## 5d. Z-axis separation and equal-loudness harshness

**`spatial.z_separation`** (`overlap_min`, `min_sep_deg`, `min_elev_deg`). In the loudest quarter of the piece (the climax,
measured, not assumed) it takes every pair of non-environment tracks that both hold the 500-4000 Hz band at a similar level
(band-envelope overlap above `overlap_min`) and asks whether they are placed apart. A pair passes on **either** `min_sep_deg`
of angular separation (azimuth wrapped, so +170 deg and -170 deg are 20 deg apart) **or** `min_elev_deg` of elevation
difference. Elevation only counts where the mixer will render it (`spatial.binaural` on the track/preset, or the mix preset's
`immersive.enabled`); a staged height with no binaural route is reported as such, because the default pan path has no height.
The fix the row names: give one part an elevated arc (the reference for a strings-versus-low-brass collision is strings
out at about +-50 deg azimuth and +25..35 deg elevation, low brass and timpani anchored at about +-20 deg and -10..0 deg),
or move one of them 25 deg or more in azimuth. Do not answer it with a broadband EQ cut: the row exists because height
separation is cheaper than carving the midrange. Beds and environments are excluded; their width comes from `spread`/`kind`.

**`spectral.equal_loudness`** (`warn_db`, `fail_db`, `band_lo_hz`, `band_hi_hz`, `max_trim_db`). Per non-environment stem, the
Welch spectrum is weighted by the ear's threshold sensitivity (Terhardt's absolute-threshold curve, the dip that ISO 226's
threshold region encodes: `3.64 f^-0.8 - 6.5 exp(-0.6 (f/3.3 - 1)^2) + 1e-3 f^4`, kHz), and the `band_lo_hz`-`band_hi_hz`
power is compared with the 500 Hz-`band_lo_hz` power, corrected for how many octaves each side holds (a flat, equal-energy-per-octave
source therefore reads about 0 dB). WARN at `warn_db`, FAIL at `fail_db`; the row names the stem and prints the narrow `inst_eq`
cut to paste into the piece's mix preset, bounded by `max_trim_db` (2-3 dB is the usual fix for a bright `.sf2` lead).
This is a K-weighted/equal-loudness **approximation**, not a certified ISO 226 loudness meter, and it judges a stem's balance,
not the master's; it cannot hear whether the brightness is intended. Listen before cutting.

## 5c. One list of rows, whoever runs the gate

There is one implementation of the row list: `quality_gate.run_gate`. `quality_gate.py <score> --wav <master>` calls it
after rendering; `pipeline.py` calls the same function from stage 6 with the score it just rendered
(`run_gate(None, wav_path=..., stems=..., score=score)`), so a row can never exist in one path and not the other. If a row
is missing from a pipeline run, it is skipped by the piece's gate profile, not by the pipeline.

Two groups sit on top of the gate rows:

- **`mix:` rows** — the mixing diagnostics (`scripts/mix_diagnostics.py`), collected because stage 5 mixes with
  `diagnose=True`. They are advisory by contract, so a diagnostic `FAIL` appears here as `WARN`; the gate's own
  true-peak, clipping and silence rows own the blocking verdicts. Fix what they name rather than ignoring them.
- **`music21_hook`** — the `analyze_music21.py` in a project's own `scripts/` folder, if present.

## 6. The extraction gate borrows this gate

`scripts/extraction/gate.py` (stage `gate` of `extract_pipeline.py`) judges a song rebuilt from MIDI against the original.
It imports `naturalness_check.analyse` / `verdicts` / `cochlear_roughness_check` and `quality_gate.find_clicks` /
`masking_rows`, runs them on the rebuilt mix and on the original, and counts a fault only when the original does not have
it too (a bright, hot or narrow master is not the rebuild's fault). `naturalness_check.analyse(..., audio=(samples, sr))`
measures an array in memory for this. Waveforms are never subtracted: the rebuild has its own phase, so spectra, levels
and statistics are compared. See `references/workflow/extraction.md` for the rows.
