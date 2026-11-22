# Theatrical realism plan

Status: phases 1 and 4-6 implemented and tested (opt-in); phase 7 measured on a 24 s reference cue. This is the
working plan for the eight qualities in the brief, what is now in the engine, what remains, and how each one is
accepted or rejected.

Evidence: `knowledgebase/sound-design/theatrical-realism.md`. Rules: `references/mixing/theatrical-realism.md`.
Measurement: `scripts/realism_report.py`.

## 1. The gap, against the engine as it was

| # | Quality | What existed | What was missing | Now |
|---|---|---|---|---|
| 1 | Timbre changes with loudness | `dynamic_tilt` (GM/SFZ stems, a level-following low-pass) and `enhance_sf2_dynamics` | no continuous harmonic/bite coupling on a general stem; `dynamic_tilt` only darkens a soft note | `dsp.level_timbre` + track `timbre_dynamics` (opt-in) |
| 2 | Ensemble imperfection | per-note detune, shared drift, anti-correlated timing; drums already vary | one track = one player; a section never had players | `humanize.ensemble_expand` + track `ensemble` |
| 3 | Register and transient consistency | round-robin drum samples, per-hit velocity jitter | high-register formant stretch unaddressed; no per-onset transient variation on plucks | `register` (split + shelf correction) and `transient_variety` (per-onset gain/bite), opt-in |
| 4 | Tactile close detail vs hall | early reflections, HRTF direct path, static send per stem | send does not change within a note, so attacks sit in the wash | `theatrical.detail` send duck; `proximity_db` and `er_distance_exponent` on the space |
| 5 | Low-mid clarity vs sub | role EQ, low-end hygiene, dynamic EQ per stem | no programme-level dynamic control of 180-450 Hz | `theatrical.low_mid` |
| 6 | Radial distance | ISO 9613-1 air absorption, near-field HRTF, distance-scaled send | proximity warmth and distance-aware ER balance are not in the panned path | `proximity_db` low shelf + `er_distance_exponent`; both preset-owned |
| 7 | Openness at peak density | air band untouched; reverb return low-passed | no density-dependent air retention | `theatrical.air` |
| 8 | Macro phrase breathing | phrase rubato, wander, final ritardando, fermata | no bar-scale elasticity or ensemble breath | `humanize.TempoMap` `elastic` + score `elastic` |

## 2. Phase 0: make it measurable (done)

`scripts/realism_report.py` reports eight dimensions with `PASS` / `WARN` / `N/A`:

1. spectral centroid and 2-8 kHz share at the loudest 10 % against the quietest 30 % of sounding frames;
2. declared players on section-named tracks;
3. 60 ms attack-spectrum similarity between consecutive onsets at a comparable level;
4. direct-to-reverberant ratio from the dry-stem sum against the master residual;
5. 180-450 Hz against 500-2000 Hz and against 20-80 Hz, plus their growth into the peak;
6. spatial distances in the project presets, predicted ISO 9613-1 4 kHz loss, missing air models;
7. 8-16 kHz share at the loudest against the quietest frames;
8. bar-scale tempo deviation from the score's tempo map, excluding the final ritardando.

Thresholds are starting values, not gate rows (`references/mixing/quality-gate.md` 3h). Each row has a positive
and a negative control in `tests/test_realism_report.py`; a measurement that cannot fail is not a measurement.

## 3. Phase 1: the couplings, opt-in (done)

### 1. Loudness-dependent timbre

`dsp.level_timbre`: short-term RMS is mapped between the stem's own quiet and loud percentiles. A nonlinear
residue of the 140 Hz-7 kHz band is added in proportion to that measure, oversampled 2x and brought back through
an anti-image filter; a high shelf follows the same measure. Overall RMS is matched, so the pattern level does
not move. `tests/test_theatrical.py::LevelTimbreTests` asserts the loud half gains more third harmonic than the
quiet half, level is compensated, `drive=0, tilt_db=0` is a no-op, a single-dynamic stem is untouched, and bad
values raise.

Track or instrument preset:

```json
"timbre_dynamics": {"drive": 0.5, "tilt_db": 2.0, "tilt_hz": 2800,
                    "band_hz": [140, 7000], "amount": 0.6, "smooth_s": 0.35}
```

### 2. Section scatter

`humanize.ensemble_expand` gives each player a fixed intonation, timing, velocity and length offset for the
whole piece plus per-note jitter. `render_natural` expands notes before humanisation on both the GM and SFZ paths.
`tests/test_theatrical.py::EnsembleTests` asserts every note reaches every player, the cents and ms spreads are
inside the measured section ranges, the result is deterministic, a solo raises, and no copy is an exact clone.

Track:

```json
"ensemble": {"players": 4, "spread_cents": 5, "spread_ms": 10, "vel_spread": 3}
```

### 3. Macro phrase breathing

`TempoMap` now takes `elastic` (peak long-range deviation, zero-mean over the piece), `elastic_corr_beats` (how
long a deviation lasts), `breaths` (beats) and `breath_s`. The score's `elastic` block is validated for unknown
keys and ranges. It sits on top of rubato, wander and the final ritardando. `ElasticTests` asserts bar-scale
movement exists, the average tempo is unchanged, a breath adds exactly its seconds after its beat, and a score
with no block renders exactly as before.

### 4. The theatrical mix stage

`mixer.theatrical_tone` (low-mid dynamic EQ, programme-level air shelf) and `mixer.theatrical_send_gain` (send
dip through attacks) run only when the mix preset enables `theatrical`, stereo only. Defaults are in
`mix_schema.DEFAULTS['theatrical']`, so a preset that does not name it is byte-for-byte the old mix. `detail` is
computed from the summed dry stems and applied to the shared send before the reverb; the tone stage runs before the
DC block.

## 4. Phases 4-6 (implemented)

### Phase 4: distance (proximity and ER balance)

`spatial.distance` now carries three preset-owned values: `proximity_db` (a low shelf below `proximity_hz`, 200 Hz,
that grows linearly as the source moves inside the 1.5 m reference), `proximity_hz`, and `er_distance_exponent`
(early-reflection level against distance, separately from the diffuse tail; 1.0 is the old 1/r law). The panned
stereo path applies proximity in `mixer._place`/`_distance`; the binaural fallback passes it to
`spatial.spatialize_stem`; the early-reflection exponent is applied in `spatial._path_attenuate`. All three are
no-ops when absent, so an older space renders byte-for-byte as before. Acceptance is covered by
`tests/test_theatrical_phases.py::DistanceTests`: a close source gains low band and not high band, a far source is
unchanged, the ER exponent lowers the far early field only, and the mixer reads the mapping.

### Phase 5: register correction and transient variety

- **Register.** `dsp.register_tone` applies a high shelf that falls by `db_per_oct` for the semitones a note sits
  above `ref_pitch`, capped at `max_db` and RMS-compensated. `render_natural` splits a pitched track at
  `split_pitch`, renders the upper notes as their own branch, corrects that branch, and sums it back, so the low
  register is untouched. It is a first-order correction for the resampling formant shift, not a formant-preserving
  resynthesis. Keys: `split_pitch`, `ref_pitch`, `pivot_hz`, `db_per_oct`, `max_db`.
- **Transients.** `dsp.transient_variety` adds a deterministic per-onset gain of +/-`gain_db` and a short high-band
  emphasis of +/-`tilt_db` around each written onset (`width_ms`). It never moves an onset, cannot invent a new
  sample, and is skipped for environments. Keys: `gain_db`, `tilt_db`, `width_ms`.

Acceptance: `RegisterTests` and `OnsetVarietyTests` assert the high band loses more than the low band, level is
compensated, two runs are identical, repeated attacks differ, and zero/unknown values raise or no-op correctly. In
the calibration cue the violin's four notes above C5 were split and corrected; the transient row stayed under the
0.995 similarity line.

### Phase 6: multichannel theatrical stage

`mixer.theatrical_multichannel` runs the same low-mid lean and air shelf on every full-range channel of a discrete
deliverable, with one linked programme curve, and skips the LFE. `spatial_engine/master.py` calls it before
loudness/limiting when the mix preset enables `theatrical`, so the limiter sees the stage's level. The stereo path
still uses `theatrical_tone`. Acceptance: `MultichannelTheatricalTests` asserts the LFE is byte-identical, the
main channels lean, and the stage is off unless enabled. The layout's own `fold.*`/`imm_*` rows remain the final
judge.

## 5. Phase 7: calibration

The reference is a 24 s, 84 BPM, three-part cue (violins with four players, cellos, horns) rendered three ways:
off, part couplings only, and all stages. It lives in `tests/fixtures/theatrical_calibration/`; the masters are not
committed.

```bash
python scripts/render_natural.py tests/fixtures/theatrical_calibration/scores/all.json \
  --out /tmp/cal_all.wav --stems-dir /tmp/cal_stems_all --seed 7
python scripts/realism_report.py /tmp/cal_all.wav \
  --score tests/fixtures/theatrical_calibration/scores/all.json --stems /tmp/cal_stems_all
python scripts/realism_report.py --compare /tmp/cal_off.wav /tmp/cal_couplings.wav /tmp/cal_all.wav
```

Measured on 22 November 2026, all three at -14.0 LUFS:

| Dimension | off | couplings | all | Reading |
|---|---|---|---|---|
| timbre loudness | PASS 6.14 | PASS 4.72 | PASS 3.09 | loud half brighter in every version; the correction reduced excess top |
| ensemble | WARN 3 | PASS 6 | PASS 6 | declared players appear only with the blocks |
| transient | PASS 0.9911 | PASS 0.9874 | PASS 0.9836 | attacks vary in all three; the block helps |
| depth | PASS -1.07 dB | PASS -0.62 dB | PASS -0.73 dB | direct sound stays in front of the hall |
| low mid | WARN 4.49 | WARN 4.38 | WARN 3.75 | the stage leans it; the cue's low cello writing still thickens the region |
| openness | PASS 13.48 | PASS 11.03 | PASS 8.32 | less air is lost at the peak with the stage on |
| phrasing | WARN 0.83 % | PASS 2.47 % | PASS 2.47 % | `elastic` supplies the bar-scale movement |

Band measurement of the stage alone (all vs couplings): 180-450 Hz frames fall by up to 1.61 dB at the loudest
moments (median 0.21 dB), and the 9-16 kHz band rises by 0.45 dB on average, with loudness unchanged. The low-mid
threshold is relative to the band's own 95th percentile (`range_db`, 10 dB) because an absolute dBFS threshold
did not engage before the master; this was found by the calibration, not assumed.

The cue still WARNs on low-mid because its cello part writes continuously in 180-450 Hz. The correct fix is the
part or the arrangement, not a deeper dip: the stage is doing its job (4.38 -> 3.75) without turning the cellos
into a hole. Thresholds remain starting values and are not gate rows.

## 6. Acceptance and regressions

| Dimension | Pass condition (starting value) | Regression to watch |
|---|---|---|
| 1 timbre | loud ≥0.8 dB brighter centroid, ≥0.5 dB more 2-8 kHz | `cochlear_roughness`, harshness |
| 2 ensemble | section part declares 2-8 players | polyphony collisions, render time |
| 3 transients | attack similarity ≤0.995 | clicks, `stem.*` rows |
| 4 depth | DRR -6..+18 dB | reverb send too low, dry mix |
| 5 low-mid | 180-450 below 500-2000, not growing faster than sub | `master.dc`, `low_interval_mud` |
| 6 distance | far sources declare an air model | double attenuation on scene sources |
| 7 openness | 8-16 kHz share drops ≤1 dB at peak | `true_peak`, limiter crest |
| 8 phrasing | bar-scale CV 1-8 % | pulse instruments, `pattern` rows |

Every fix is in the part, the preset or the placement. No row is loosened, and the realism report never replaces
the gate.

## 7. Limits

- The engine cannot hear. A `PASS` is a structure, not a judgement of the cue.
- `timbre_dynamics` adds a plausible coupling, not the missing fortissimo velocity layer.
- `ensemble` is scatter on copies of one sample, not independent players or a recorded section.
- Register correction is a shelf approximation of the formant shift, not a formant-preserving resynthesis; a
glassy top register still needs a different sample path or a rewrite.
- `transient_variety` varies gain and bite around an existing attack; it cannot create the missing sample.
- The theatrical mix stage now runs on discrete multichannel masters as well as stereo, but AmbiX/ADM keep their own
levelling and are not processed by it.
- All thresholds are starting values; the knowledge base labels every one, and the one reference cue does not
calibrate a house default.
