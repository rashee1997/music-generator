# Debug autopsy - night_pursuit

20261126T083704  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T08:20:21Z

## In question (1)
- **clicks**: 15.0 events against 0.0 -> FAILS by 15.00 tolerance units
  - 15 clustered impulse event(s) (MAD), 15 LPC frame(s); 2026 event(s) rejected as a dense burst, 1089 as a steep attack; max cluster span 1.497 ms
  - transient attributed to wipers 60%, engine 27%, tyres 10%

## Forensics (signal level)
- **5.060s** single source: wipers 93%; step 0.0343 vs threshold 0.0207 (+4.4 dB over, z 13.3) - decomposition fit 0.03x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **9.769s** single source: wipers 81%; step 0.0314 vs threshold 0.0207 (+3.6 dB over, z 12.2) - decomposition fit 0.03x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **48.857s** coincident transients: wipers 52%, engine 42%; step 0.0245 vs threshold 0.0207 (+1.5 dB over, z 9.5) - decomposition fit 0.08x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **51.384s** single source: engine 81%; step 0.0272 vs threshold 0.0207 (+2.4 dB over, z 10.5) - decomposition fit 0.05x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
- **58.907s** coincident transients: wipers 59%, engine 38%; step 0.0213 vs threshold 0.0207 (+0.2 dB over, z 8.2) - decomposition fit 0.36x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.977s** coincident transients: wipers 51%, engine 27%, tyres 21%; step 0.0318 vs threshold 0.0207 (+3.7 dB over, z 12.3) - decomposition fit 0.14x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: tyres is a continuous bed with no onset, so the step is in its texture, not on a note
- **65.238s** mixed: tyres 48%, rain_street/water_film 25%; step 0.0482 vs threshold 0.0207 (+7.4 dB over, z 18.7) - decomposition fit 0.0x, treat as indicative
  - under it: tyres is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
- **90.163s** single source: wipers 76%; step 0.0232 vs threshold 0.0207 (+1.0 dB over, z 9.0) - decomposition fit 0.16x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.tyres` +9.00 dB tyres high shelf at 5500 Hz: inst_eq["sfx:np_drift_squeal"]

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  clicks::-: -15.00 -> -13.00
  clipping::-: +0.00    +0.00
  stem.clipping::tyres: +0.00    +0.00
  stem.clicks::tyres: +0.00    +0.00
  loudness::-: +0.02    +0.02
  true peak::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.tyres -9 dB: 15 -> 13 (better)
- hf.tyres -12 dB: 15 -> 13 (better)
- hf.tyres -9 dB, layer.rain_street.water_film -3 dB: 15 -> 13 (better)
- hf.tyres -9 dB, layer.rain_street.water_film -6 dB: 15 -> 13 (better)
- hf.tyres -9 dB, layer.rain_street.water_film -9 dB: 15 -> 13 (better)
- hf.wipers -6 dB: 15 -> 14 (better)
- hf.tyres -6 dB: 15 -> 14 (better)
- hf.wipers -9 dB: 15 -> 14 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.tyres` (tyres high shelf at 5500 Hz: inst_eq["sfx:np_drift_squeal"]): tyres high shelf at 5500 Hz: inst_eq["sfx:np_drift_squeal"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +67.50 .. +9.00 dB within bounds -12.00 .. +9.00
  - clicks needs +67.50 (safety now -15.00)

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 15 vs gate 8; missing at [], extra at [102.764, 118.75, 156.902]): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 0.5 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.98); gains bass_clarinet 1.28, bass_drum 0.98, basses 1.82, celli 1.12, city_far 4.14, crash 0.19, cymbals 0.67, engine 2.66, horns 0.83, piano 1.10, piano_low 1.71, rain_street 4.23, snare 0.91, sub_drop 2.01, timpani 0.76, trombones 0.77, tuba 1.37, tyres 1.39, violins_staccato 0.84, violins_tremolo 0.67, wipers 2.26'
- 'event 5.060s [single source] wipers 93%; step 0.0343 vs threshold 0.0207 (+4.4 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 9.769s [single source] wipers 81%; step 0.0314 vs threshold 0.0207 (+3.6 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 48.857s [coincident transients] wipers 52%, engine 42%; step 0.0245 vs threshold 0.0207 (+1.5 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 51.384s [single source] engine 81%; step 0.0272 vs threshold 0.0207 (+2.4 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 58.907s [coincident transients] wipers 59%, engine 38%; step 0.0213 vs threshold 0.0207 (+0.2 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 60.977s [coincident transients] wipers 51%, engine 27%, tyres 21%; step 0.0318 vs threshold 0.0207 (+3.7 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 65.238s [mixed] tyres 48%, rain_street/water_film 25%; step 0.0482 vs threshold 0.0207 (+7.4 dB over); nearest onset tyres pNone vNone +0 ms  (fit unreliable)'
- 'event 90.163s [single source] wipers 76%; step 0.0232 vs threshold 0.0207 (+1.0 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'clicks: cutting the band of engine is NOT monotone (replay: -6 dB -> 16 event(s), -9 dB -> 16 event(s), -3 dB -> 17 event(s), -12 dB -> 17 event(s) against 15 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of wipers is NOT monotone (replay: -6 dB -> 14 event(s), -9 dB -> 14 event(s), -3 dB -> 16 event(s), -12 dB -> 16 event(s) against 15 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'risk closure: the levers that move this row belong to tyres, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -13.00. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
- the best candidate comes from a model that failed its sham test, so it is not adopted as a plan
