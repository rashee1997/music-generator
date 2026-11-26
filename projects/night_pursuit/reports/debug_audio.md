# Debug autopsy - night_pursuit

20261126T065403  ·  level FAIL  ·  plan solved
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T06:51:45Z

## In question (3)
- **clicks**: 6.0 events against 0.0 -> FAILS by 6.00 tolerance units
  - 6 clustered impulse event(s) (MAD), 6 LPC frame(s); 6264 event(s) rejected as a dense burst, 634 as a steep attack; max cluster span 1.497 ms
  - transient attributed to city_far 38%, siren_first 25%, wipers 20%
- **dropout**: 60.000000000002274 ms against 20.0 -> FAILS by 2.00 tolerance units
  - longest hole 60 ms (limit 20-1000 ms), floor -65.1 dBFS; 3 hole(s)
  - transient attributed to rain_street 83%, engine 8%, rain_awnings 4%
- **tempo.audio**: 11.911896186562558 BPM against 2.56 -> FAILS by 9.35 tolerance units
  - measured 139.9 BPM vs 128.0 (tolerance 2.6) from the onset-envelope autocorrelation (peak 5.6x the median); beat tracker said 139.7; four-quarter drift 1.0 BPM reported, not decisive

## Forensics (signal level)
- **8.143s** single source: wipers 90%; step 0.0301 vs threshold 0.0253 (+1.5 dB over, z 9.5) - decomposition fit 0.02x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **152.766s** mixed: city_far 50%, rain_street/water_film 26%; step 0.0286 vs threshold 0.0253 (+1.1 dB over, z 9.1) - decomposition fit 0.0x, treat as indicative
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note
- **155.604s** mixed: city_far 55%, violins_tremolo 30%; step 0.0279 vs threshold 0.0253 (+0.9 dB over, z 8.8) - decomposition fit -0.0x, treat as indicative
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note
- **160.327s** single source: siren_first 83%; step 0.0259 vs threshold 0.0253 (+0.2 dB over, z 8.2) - decomposition fit 0.0x, treat as indicative
  - under it: siren_first is a continuous bed with no onset, so the step is in its texture, not on a note
- **160.575s** mixed: siren_first 34%, city_far 22%; step 0.0367 vs threshold 0.0253 (+3.2 dB over, z 11.6) - decomposition fit -0.0x, treat as indicative
  - under it: siren_first is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note
- **160.875s** coincident transients: city_far 48%, violins_tremolo 22%; step 0.0350 vs threshold 0.0253 (+2.8 dB over, z 11.1) - decomposition fit 0.0x, treat as indicative
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -6.00    -6.00
  dropout::-: -2.00    -2.00
  clipping::-: +0.00    +0.00
  stem.clipping::wipers: +0.00    +0.00
  stem.clicks::wipers: +0.00    +0.00
  loudness::-: +0.00    +0.00

## Conflicts (no value satisfies both)
- `hf.wipers` (wipers high shelf at 5500 Hz: inst_eq["sfx:np_wipers"]): wipers high shelf at 5500 Hz: inst_eq["sfx:np_wipers"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +54.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +54.00 (safety now -6.00)

## Closed rows
dropout - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 6 event(s) exactly (decomposition R^2 0.973); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.6 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.97); gains bass_clarinet 0.96, bass_drum 1.23, basses 1.76, celli 1.04, city_far 4.09, crash 0.16, cymbals 0.72, engine 2.64, horns 0.81, piano 1.09, piano_low 2.12, rain_street 4.19, snare 0.98, sub_drop 2.64, timpani 0.87, trombones 0.78, tuba 2.29, tyres 1.38, violins_staccato 0.79, violins_tremolo 0.67, wipers 2.18'
- 'event 8.143s [single source] wipers 90%; step 0.0301 vs threshold 0.0253 (+1.5 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 152.766s [mixed] city_far 50%, rain_street/water_film 26%; step 0.0286 vs threshold 0.0253 (+1.1 dB over); nearest onset rain_street pNone vNone +0 ms  (fit unreliable)'
- 'event 155.604s [mixed] city_far 55%, violins_tremolo 30%; step 0.0279 vs threshold 0.0253 (+0.9 dB over); nearest onset city_far pNone vNone +0 ms  (fit unreliable)'
- 'event 160.327s [single source] siren_first 83%; step 0.0259 vs threshold 0.0253 (+0.2 dB over); nearest onset siren_first pNone vNone +0 ms  (fit unreliable)'
- 'event 160.575s [mixed] siren_first 34%, city_far 22%; step 0.0367 vs threshold 0.0253 (+3.2 dB over); nearest onset siren_first pNone vNone +0 ms  (fit unreliable)'
- 'event 160.875s [coincident transients] city_far 48%, violins_tremolo 22%; step 0.0350 vs threshold 0.0253 (+2.8 dB over); nearest onset city_far pNone vNone +0 ms  (fit unreliable)'
- 'dropout has 3 event(s) at 169.920s, 169.975s, 170.045s; the transient is rain_street 83%, engine 8%, rain_awnings 4%'
- 'tempo.audio: no domain module examines this row yet'
- 'risk closure: the levers that move this row belong to wipers, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible move improves the binding rows: every lever is burned, closed or already optimal
