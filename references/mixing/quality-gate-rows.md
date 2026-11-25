---
title: Gate rows for deliverables, immersion and extraction
summary: The rows that judge a delivered format, the immersive probes, the z-axis and mono checks, and the extraction gate.
tags: [gate, deliverables, fold, immersive, extraction, roughness]
load_when:
  - a delivery, fold, immersive or extraction row fails
  - choosing what a delivered format is judged on
---

# Gate rows for deliverables, immersion and extraction

Companion to [`quality-gate.md`](quality-gate.md), which holds the rows that judge the score and the mix.
## 5b. Deliverable-format rows (only for the formats the score asked for)

`spatial_gate.output_rows` reads the score's `output_targets` through `render_targets` and checks the delivered file
against the target it claims to be. A format that was not requested is never checked and can never fail.

| Row | Applies to | What is measured | Where the limit comes from |
|---|---|---|---|
| `delivery.true_peak` | every target | worst channel true peak after 4x oversampling | the target preset's `true_peak_dbtp` (-1.5 dBTP two-channel, -3.0 dBTP multichannel) |
| `delivery.format` | every target | channel count against the requested targets (a target with `"channels": 0`, one channel per object, is matched by file name) | `render_targets.channels()` |
| `stereo.correlation` | 2-channel targets | `corr(L, R)` - below the floor the centre is cancelling | target preset `gate.stereo_correlation_min` |
| `imm.lfe_stopband` | multichannel | energy above the stopband, relative to the programme RMS | layout `lfe.stopband_hz` / `stopband_db` |
| `imm.surround_ratio` | multichannel | surround energy (BL+BR+SL+SR) against the front stage (FL+FR+FC) | layout `gate.surround_ratio_db` |
| `imm.height_arc` | layouts with overhead speakers | height energy against the listener-level beds | layout `gate.height_max_rel_db` |
| `imm.fold_coherence` | multichannel | correlation of the ITU-R BS.775 fold | layout `gate.stereo_correlation_min` |
| `imm.loudness` | layouts whose target sets `loudness.method: bs1770_layout` | ITU-R BS.1770 loudness of the delivered channels with the layout's `loudness_weight_db` per speaker, the low-frequency channel left out; WARN when it misses the target by more than the mix preset's `mastering.converge.report_miss_lu` | the score's master block, or the target's `loudness.target_lufs` |
| `fold.mono` | the `mono` target, beside a loudspeaker stereo master | the stereo master summed to one channel against the rendered mono, per auditory band from 100 to 5000 Hz, after level matching | target preset `gate.fold_band_max_db`, `fold_floor_db` |
| `fold.timbre` | every layout target, beside a loudspeaker stereo master | the layout folded to two channels with its own `downmix` coefficients against the stereo master, per auditory band, after level matching | target preset `gate.fold_band_max_db`, `fold_floor_db` |
| `fold.reference` | `mono` and layout targets | WARN: the first deliverable is not a loudspeaker stereo master, so the fold comparison was not made | none |
| `render.finite` | every target | a NaN or an infinite sample in any channel (protected: no profile can switch it off) | none: one is a fault |
| `channel.virtual` | every delivered file | the file's channels against the positions the target claims: a real layout's speakers, or the 36-point `ambix_qa_36` virtual sphere for order-5 AmbiX; fails a wrong channel count, too few virtual speakers or a non-finite decoded channel | target `gate.virtual_layout` / `gate.min_virtual_channels` for AmbiX; layout speaker count otherwise |
| `channel.bars` | every delivered file | per-bar per-channel RMS, comparing an interior bar with both neighbours: isolated jump, dropout, left/right-front/back-floor/height balance swing, or polarity inversion while the other channels stay still | gate profile `channel.bars` parameters (`jump_db`, `dropout_db`, `balance_db`, `stable_db`, `polarity_corr`, `polarity_neighbor`) |
| `adm.container` | the `adm_bw64` target | the container itself, read from the bytes: `BW64` magic + saturated outer size, `ds64` first with the 64-bit file and data sizes matching the file, `fmt `/`chna`/`axml`/`data` agreement, unique ADM IDs with every reference resolved (or a BS.2094 common definition), each `chna` row mapping one channel to one `audioTrackUID`, block times contiguous from 0 to the file end, positions in range | `scripts/spatial_engine/adm.py` `validate_file` (structure, not a threshold) |
| `adm.channels` | the `adm_bw64` target | tracks, sample rate, frames, bit depth read from the parsed container, and that each track maps to exactly one ADM object | `adm.parse` |
| `adm.loudness` | the `adm_bw64` target | names the loudness policy in the report: BS.1770 loudness of a constant-power stereo fold of the objects, applied as one programme gain at render time. This is this engine's internal levelling reference, not a standard-required loudness (an object file has no loudness until a renderer folds it), so the row reports the method rather than inventing a target | `spatial_engine/adm.py` `AdmBus.report` |

The `fold.*` rows compare long-term spectra. They catch a band that cancels, doubles or goes dull between formats;
they do not see a part that drops out for two bars, which is what `channel.bars` and the per-file rows are for. A
one-bar channel fault is isolated against both neighbours while the other channels stay still, so a deliberate
whole-bar accent is not reported as a channel fault. AmbiX has no speaker positions of its own: `channel.virtual`
decodes order-5 ACN/SN3D to `ambix_qa_36` with the engine's AllRAD/max-rE decoder first, and `channel.bars` then
measures the virtual speakers. An undeclared channel file is still checked per channel, without spatial balance.
The rules and sources are in `references/spatial/virtual-speaker-qa.md`. A
`fold.mono` FAIL is a fact about the stereo master (something in that band is out of phase between its channels, or
panned so hard that the sum loses it): narrow, re-pan or lower the widening of the part that lives there. A
`fold.timbre` FAIL is a fact about the layout render: check the part's `spatial` place and the layout's `downmix`.

**When the delivered file is a loudspeaker layout** (`--only immersive_7_1_2`, or a score whose first target is one),
the gate measures that file and nothing it was not given. Three rows have a basis that is easy to get wrong, and each
says in its detail which one it used:

| Row | Basis on a multichannel delivery |
|---|---|
| `loudness` | the basis the master was levelled on: the delivered channels' BS.1770 LKFS when the target says `loudness.method: bs1770_layout`, otherwise the two-channel fold |
| `true peak` | `delivery.true_peak` certifies every channel against the format's own ceiling; the peak of the two-channel fold is INFO, because a fold is a sum of channels and is not a delivery limit |
| `master.dc` | the programme channels; the low-frequency channel is excluded, it carries the sub below the DC blocker's corner by design |

`clipping`, `clicks`, `silence`, `dropout`, `delivery.channels` and `render.finite` are measured on every delivered
channel, so a defect in one surround or height channel still fails with that channel named. `fold.timbre` needs no
stereo master beside it: with only a loudspeaker format delivered, it compares that format with its own two-channel
fold (`spatial_gate._own_fold`), which is the same question — is there a band this layout cancels in its downmix.

**What a gate run costs.** The delivered file is decoded once and shared by every row (`gate_audio.load` keys the
object on the path, its mtime and its size), the per-stem band helpers are memoised on the array object
(`dsp.band_db`, `_band_frames`) instead of band-passing every stem once per row, and the packaging stage reports
the gate's own `nc.analyse` and roughness numbers rather than measuring the same audio again. On the real profile
those repeated filters were 71 s and 30 s of a 290 s gate, plus a full second analysis at the end. No threshold,
row id or verdict changes with any of it.
A file is matched to its target by its file name before its channel count, because two layouts can share a count.

The `adm_bw64` target is checked by those rows and never by `delivery.format`: its channel count is the piece's, not
the format's, and the container is BW64, which libsndfile/soundfile cannot open (`sf.read` raises `Format not
recognised` for the BW64 magic; it understands RF64, not BW64). `adm.parse` is therefore the reader of record, and a
plain RIFF file that merely carries the right name fails `adm.container`.

For a multichannel delivery the `loudness` row is measured on the layout's BS.775 two-channel fold, not on the mean of
the channels: the fold is what a listener without the room hears, and a channel mean changes with the channel count.

A `FAIL` here names the channel or the ratio that broke, so the fix is a preset send level or a track's position - not
a loosened threshold. The low-frequency row is an upper limit, so the guard in `spatial_engine/bass.py` is a low-pass at
the stopband: a high-pass there would strip the band the channel exists to carry.

## 5c. Immersive rows (only when the mix preset has `immersive.enabled`)

`imm_cues`, `imm_elevation`, `imm_height_rules`, `imm_externalization`, `imm_foldown` FAIL; `imm_frontback`, `imm_band`, `imm_envelopment`, `imm_width` WARN.
Probes run through the measured-head route the mixer forces, with the numbers from `tests/test_hrtf.py`. What each row means, the height rules and the
limits: `references/spatial/immersive-spatial.md`. A failing row is fixed in the score or presets (raise a pad, give the space a ceiling reflection, lower a bass), never by loosening the row. The rows of the ambisonic engine (`imm_kinematics`, `imm_low_fold`, `mix.band_fold`, `imm_iacc_early`, `imm_clarity`) are in `immersive-spatial.md`, section 3.

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

## 5e. Delivery, micro-dynamics and mono bands

Four rows were added for evidence that is measurable but has no validated pass mark. They report; they do not
invent a threshold.

- **`delivery.standard`** - the preset's `mastering.standard` names a document (`ebu_r128`, `atsc_a85`,
  `aes_td1008`, `spotify`). A declared target or ceiling that contradicts that document is a FAIL (a preset bug);
  a delivered file outside the document's own tolerance is a WARN; a platform policy is INFO. Figures, versions
  and URLs: [`delivery-standards.md`](delivery-standards.md).
- **`master.micro_dynamics`** - PLR (EBU Tech 3401), PSR (AES EBU 373), LRA (EBU Tech 3342) and true peak at 4x
  and 8x oversampling. INFO always: no document defines a pass mark, and the measured association with listener
  preference is weak (LDR rho = +0.26, De Man & Reiss 2015).
- **`master.mono_bands`** - the octave band (63 Hz-8 kHz) that loses the most in a mono fold, when it loses more
  than 3 dB, with its L/R correlation. WARN at most: a broadband correlation hides a narrow cancellation.
- **`masking.excess`** - the beds' level against the figure per critical band, and one band up (upward spread).
  INFO only: a band-level proxy, not a calibrated masking model.

## 5f. One list of rows, whoever runs the gate

### Two stages: stems before the mix, master after

The gate runs twice on a generated piece:

1. **`stem_gate.run_stem_gate(score, stems)`** runs in pipeline stage 4b, on each stem alone, before `mixer.mix_and_master`.
   It measures clicks, dropout, hard cut at a section boundary, abrupt end, clipping, DC, spectral flatness, vocal
   integrity, duplicate/present stems and a dead part against the score's dynamics. Any `stem.*` FAIL stops the run:
   nothing is mixed and `out/` is untouched. Each stem is measured in its own thread (`GATE_WORKERS` / `--gate-workers`,
   default 2), and the per-stem and total timings go into the report.
2. **`quality_gate.run_gate`** runs after mixing on the draft WAV and certifies. It adds the same detectors on the master
   under unsuffixed ids (`clicks`, `dropout`, `cut.hard`, `end.abrupt`, `clipping`, `master.dc`), plus measured-against-
   sheet `tempo.audio` and `section.energy`. Only 0 FAIL publishes a version.

`--draft` keeps stage 1 and the tier-1 master rows and skips masking, roughness, immersive, chroma, kick grid, equal
loudness, flutter, ambience-reference and sfx rows; it never publishes. The formulas, windows and calibration status of
every new row are in `references/mixing/gate-maths.md`.

Every row also produces a number record: `out/ci_report.json` has `gate.mode`, `gate.stopped` and `gate.stages.{stem,mix}`,
and each stage's `metrics` lists `row`, `stem`, `level`, `value`, `threshold`, `margin`, `unit`, `worst_times_s`,
`calibrated` and `detail`. `scripts/gate_report.py` writes a PNG beside a `.txt` and `.json` for the waveform with section
boundaries and flags, the log spectrogram, the short-term level, stereo correlation, per-stem level against the dynamics
curve and section energy against the sheet, under `<project>/presets/gate/` (and every PNG in `presets/gate/figures/`).

Every stem row is a gate-profile row too. `stem_gate.run_stem_gate` resolves the same profile as the mix gate
(`gate_profiles.resolve(score)`), so the piece's `piece_type` decides whether `stem.clicks`, `stem.dropout`, `stem.cut`,
`stem.end`, `stem.edge`, `stem.tick`, `stem.dead`, `stem.flatness`, `stem.dc`, `stem.clipping`, `stem.vocal`,
`stem.present` and `stem.duplicate` apply, uses the profile's parameter values for each, and a `skip`/`relax` needs the
profile's written reason. A skipped row is printed (`[INFO] stem.<row>: SKIPPED by profile <label>: <reason>`), never
silently dropped, and an unknown `piece_type` is a FAIL in both stages. The chosen profile label is in
`presets/gate/stem_gate.json` and `ci_report.json`. `quality_gate.py <score> --timings` prints the per-group wall time of
a local mix-gate run.

There is one implementation of the row list: `quality_gate.run_gate`. `quality_gate.py <score> --wav <master>` calls it
after rendering; `pipeline.py` calls the same function from stage 6 with the score it rendered
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

### Roughness: forecast it, diagnose it, never loosen it

`cochlear_roughness` reads the ten strongest partials of each 1 s frame, so it fails on overtones that no written note
shows: a D2's sixth harmonic and a D3's third are both A4, 26 Hz from a Bb4. Use the tools in this order and do not guess
at notes first:

1. **Before the render**: `python scripts/preflight_lint.py <score> <project>` prints `preflight.roughness_partials`
   with the worst frames and the two partials that beat; `python scripts/roughness_forecast.py forecast <score> --project <dir>`
   lists every hot frame. Measure the instruments once so it stops using default overtone profiles:
   `roughness_forecast.py partials <project>/stems/<track>.wav <score> <track>` and paste the list into the instrument preset
   as `"partials": [...]`.
2. **After a failing render**: `roughness_forecast.py diagnose <project>/out/_draft_master.wav --stems <project>/stems --score <score>`
   runs the gate's own row and names, for each frame over the limit, the clashing partial pairs and the stems that hold a peak at
   each frequency. It takes seconds; a full pipeline run takes minutes.
3. **Fix in the piece**: move or re-octave the part that owns the partial, keep a bass note off the pitch whose harmonic lands on
   a melody note, lower the part's level, or low-pass a bass preset (`eq` `lp`) so its upper harmonics are not a second voice.
   Never raise the limit.

How far to trust the forecast: on one piece (Antigravity) its frame ranking correlated with the measured frames at about 0.17
with default overtone profiles and 0.24 with profiles measured from the stems (Spearman, 82 frames), and it ranked the single
worst measured frame first. It is a screen that points at where to look; `diagnose` is the measurement.
