# Gate maths: what each row measures, and whether its number is calibrated

Companion to `quality-gate.md`. Every row below is implemented once in `scripts/gate_checks.py` and returns
`value`, `threshold`, `margin`, `unit`, `times`, `detail`. `scripts/stem_gate.py` runs the `stem.*` rows on each stem
before the mix; `scripts/quality_gate.run_gate` runs the same detectors on the master under the unsuffixed ids.

**Status key**

- **calibrated** - the number comes from a measurement on known material, and the measurement is named.
- **fixture-measured** - separated clean from defective on `tests/gate_fixture.py` only; not yet across six finished
  masters.
- **starting value** - chosen from the physics or the defect definition, not from a separation sweep. It must not be
  described as calibrated.

No existing threshold was loosened for this work. Two behaviour changes are tightenings: the master `clicks` row moved
from WARN to FAIL, and a synthetic gain step in the fixture was smoothed so a legitimate 30 ms section ramp is not itself
a click.

## 1. Shared analysis (`scripts/gate_audio.py`)

| What | Setting | Why |
|---|---|---|
| full-rate copy | native `sr` | clicks, clipping, DC and true peak need every sample |
| decimated copy | 8 kHz, `resample_poly` | envelope, cut, dropout, tick and section levels: 5.5x smaller, 20 ms frames survive it |
| STFT | `n_fft=2048`, `hop=512`, magnitude | flatness and spectrogram figure |
| frame level | 20 ms window, 5 ms hop, RMS in dBFS | all step/level rows |
| onset envelope | `librosa.onset.onset_strength`, `hop=512` | tick row |
| true peak | 4x `resample_poly`, max dBFS | master ceiling |
| LUFS | `pyloudnorm` integrated | master loudness |

The cache is lazy and locked: each array is computed once per file. A row never reloads the WAV or runs a second STFT.

## 2. Stem rows

| Row | Measurement | Threshold | Margin | Status |
|---|---|---|---|---|
| `stem.dc` | per-channel mean and 1 s block mean drift, FS | 0.001 FS | value - 0.001 | starting value (defect definition: inaudible offset) |
| `stem.clipping` | samples at or above 0.999 FS; flat-top runs of 3+ samples | any sample | count | calibrated (definition of a clipped sample) |
| `stem.clicks` | 4th-order 6 kHz zero-phase high-pass, first difference, modified z-score `0.6745*(x-med)/MAD`; candidates > 8 z and > 0.02 FS, clustered within 1.5 ms; a second event of >= 0.5x amplitude within 10 ms rejects the cluster (cymbal/shaker burst); Burg LPC order 16, frame 1024, hop 512 on the kept frames, error > 0.2 | 0 events | count | cluster geometry calibrated: a 0.5 FS click makes 4 candidates inside 0.091 ms, a 0.2 FS click 2 inside 0.068 ms (measured at 44.1 kHz), so the 1.5 ms cluster and 10 ms isolation are the measured values; the z=8 and LPC 0.2 are fixture-measured |
| `stem.dropout` | frames 45 dB under the file median **and** under -60 dBFS, 20-1000 ms long, at least 250 ms from either edge; the hole's middle must fall inside one of the track's own notes (+-30 ms), so a gap between phrases is a rest and not a fault | any hole | longest hole - 20 ms | starting value; the score-aware condition is measured: a hummed vocal stem in a real project run read seven 20-40 ms "holes" that were all rests between phrases, while a hole cut out of a sustained pad still fires |
| `stem.cut` | RMS step between frame `i` and `i+2` (10 ms), > 12 dB, no recovery of 3 dB within the next 100 ms, within +-75 ms of a section boundary, and the post-step level at least 25 dB under the file median; the final 200 ms belongs to `stem.end` | 12 dB | value - 12 | the 12 dB is a starting value; the 25 dB "still audible" condition and the end exclusion are measured: a clean 74 BPM render showed a 15.7 dB step at a section change with the level still 59 dB under the median, and two more steps inside the master fade |
| `stem.end` | RMS of the final 50 ms vs the 300-800 ms body; fails when the tail is above -45 dBFS and the decay is under 12 dB; skipped for a stem that reaches the score duration (the mixer owns the master fade) | -45 dBFS / 12 dB | decay - 12 | starting value |
| `stem.edge` | audible span of the stem (first and last 20 ms frame within 60 dB of its loudest frame, the same trim as `librosa.effects.trim(top_db=60)`) against the score's own first note onset and last note end; percussive stems are excluded because a drum note's written length is a grid cell, not a sound length | 25 ms | silence - 25 ms | fixture-measured: clean stems 0 ms, a pad started 300 ms late reads 300 ms |
| `stem.tick` | onset-strength autocorrelation over 0.1-1 s lags; `rho` at the best lag, strong onsets (>= 0.25x max), and how many land on that period with +-20 ms tolerance; also reports tempogram and PLP peak ratios and IOI CV | rho >= 0.35, >= 6 strong onsets, >= 6 on the grid and >= 30% of strong onsets | components reported | fixture-measured: a 4 Hz train gives rho 0.47, 24 strong, 8 on the grid (30% = 7.2); a clean pad gives rho 0.60 but only 5 on the grid, so the 6-count and 30% conditions, not rho alone, decide. CV is reported, not decisive: extra strong onsets inflate it on a real train |
| `stem.dead` | per-note window level (energy mean of dB, window capped at 0.5 s), median over the notes in each section; expected level follows the section `dyn` against the stem's own median | 12 dB under the curve, or all sections under -70 dBFS | shortfall - 12 | starting value (intra-stem only: stems are normalized before mixing and distance is applied later in `mixer._place`) |
| `stem.flatness` | `librosa.feature.spectral_flatness` per STFT frame, sustained >= 50 ms while the frame is above -50 dBFS | 0.10 | value - 0.10 | fixture-measured: clean pad 0.000, 120 ms noise burst 0.188 |
| `stem.vocal` | DC and click count on a vocal stem | 0.001 FS / 0 clicks | count | starting value |
| `stem.present` | score track with notes but no stem | 0 | count | calibrated (count) |
| `stem.duplicate` | pairwise decimated correlation of two stems | 0.999 | correlation - 0.999 | calibrated (definition: an identical copy) |
| `stem.integrity` | the stem could not be read or contains NaN/Inf | any | count | calibrated (definition) |

`stem.dead` is not a cross-stem comparison: `render_natural.build_stems` only normalizes; air absorption, `1/r` level
and pan are applied later in `mixer._place`. A pre-mix stem therefore has no distance term to subtract.

## 3. Master rows added or changed by this work

| Row | Measurement | Threshold | Status |
|---|---|---|---|
| `clicks` | same detector as `stem.clicks`, on the master; **FAIL** now (was WARN). An event that sits on a short monotone ramp (>= 2 same-sign sample steps within 8 samples) is an instrument attack and is reported as `attacks_ignored`, not counted | 0 events | as `stem.clicks`; the attack guard is measured: a real project master read three "clicks" at 1.078 / 1.443 / 2.899 s that were 2-3 sample monotone note attacks (step 0.068-0.078 FS, peak 0.15-0.37 FS, stems clean), while an injected one-sample click is a single step |
| `dropout` | same as `stem.dropout` | any hole | starting value |
| `cut.hard` | same as `stem.cut`, boundaries from the score plan or the direction sheet | 12 dB | as `stem.cut` |
| `end.abrupt` | same as `stem.end`, no `expected_dur` | -45 dBFS / 12 dB | starting value |
| `clipping` | same as `stem.clipping` | any sample | calibrated |
| `master.dc` | same as `stem.dc` | 0.001 FS | starting value |
| `tempo.audio` | full-track `librosa.beat.beat_track`, compared with `score.bpm`; tolerance `max(2 BPM, 2%)`; only judged when the score actually plays a pulse (a percussive track or 6+ isochronous note starts, IOI CV <= 0.05), otherwise it is INFO. Quarter drift from the same beat list is **reported, not decisive** | 2 BPM or 2% | starting value; the drift limitation is measured: a steady 74 BPM render showed 4.1 BPM of quarter-to-quarter tracker jitter with no tempo change, so making drift decisive produced a false FAIL |
| `section.energy` | Spearman rho between the promised section `dyn`/energy and the measured 20 ms frame level in the middle 80% of each section (4+ sections) | FAIL < 0.5, WARN < 0.7 | starting value; skipped (not judged) when fewer than 4 sections or constant energies |

Existing rows keep their old numbers: loudness target +-2.5 LU, true peak ceiling +0.3 dB, the 1 s silence row, and the
naturalness, balance, masking, spatial, immersive and delivery rows. Nothing in `gate_profiles.py` was relaxed; the new
`stem.*` ids were added with the same parameters the code uses.

## 4. Report contract

`out/ci_report.json` carries `gate.mode` (`full` or `draft`), `gate.stopped` (`stem` when the run stopped before mixing),
and `gate.stages.stem` / `gate.stages.mix`. Each stage has `metrics`: one entry per row with `row`, `stage`, `stem`,
`level`, `value`, `threshold`, `margin`, `unit`, `worst_times_s`, `calibrated` and `detail`. The stem stage also has
`timings` (ms per stem), `total_ms`, `workers`, `fails`, `warns` and `sections`. The mix stage has `images`, the folder
with the figures. `scripts/gate_report.py` writes the PNG + `.txt` + `.json` sets described in `quality-gate.md`.

## 5. Draft mode

`pipeline.py --draft` runs the stem gate, then the tier-1 master rows (audio, loudness, true peak, silence, clicks,
dropout, cut, end, clipping, DC, tempo, section energy) and skips tier-2 groups (masking, roughness, immersive, chroma,
kick grid, equal loudness, flutter, ambience reference, sfx). A draft run never publishes, even at 0 FAIL: the draft WAV
stays at `out/_draft_master.wav` and `out/master.wav` is untouched.

## 6. What these rows cannot detect

- A defect identical in every stem before mixing (shared clock error, common offset applied at mix time).
- A tick or click created only by the limiter or the reverb; the master rows cover part of that, not all.
- Musical intent: a stutter, glitch, clock pulse or sudden drop. The direction sheet must declare it and the piece's gate
  profile relaxes the row with a measured reason.
- Phrasing, groove, cultural correctness and beauty. `listen.py` is still the only check for those.
- A written rest in the score during a dropout: the row measures audio only and does not consult the score's rests, so a
  rest that the score writes is still reported. Relax the row with a measured reason or fix the score.

## 7. The rows follow the piece's gate profile

Both stages resolve `gate_profiles.resolve(score)` from the score's `piece_type` (declared, else inferred, else melodic):

- `apply` runs the row with the profile's parameter values (`gp.param`); `relax` runs it with the values in the profile
  entry; `skip` prints `[INFO] <row>: SKIPPED by profile <label>: <reason>` and does not judge.
- A `skip`/`relax` without a reason is rejected by `gate_profiles` (the profile fails validation), and a protected row
  cannot be switched off; `stem.clicks`, `stem.clipping` and `roughness` also carry `no_skip`.
- A row's parameters live in `gate_profiles.ROWS` with a range; the range is validated for every profile and for a score's
  one-off `"gate"` override.
- An unknown `piece_type` becomes a FAIL row (`piece_type`) in both stages, so a typo cannot silently disable a check.

The default numbers in the code are the defaults in `gate_profiles.ROWS`; the stem gate no longer carries private copies.
`tests/test_stem_gate.ProfileAdoptionTest` proves a skip, a relaxed parameter and an unknown type on the stem stage;
`tests/test_gate_no_loosening.py` pins every default against `tests/fixtures/gate/thresholds.json`.
