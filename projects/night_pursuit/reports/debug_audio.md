# Debug autopsy - night_pursuit

20261126T080253  ·  level FAIL  ·  plan solved
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T08:00:20Z

## In question (2)
- **clicks**: 6.0 events against 0.0 -> FAILS by 6.00 tolerance units
  - 6 clustered impulse event(s) (MAD), 6 LPC frame(s); 1530 event(s) rejected as a dense burst, 640 as a steep attack; max cluster span 1.497 ms
  - transient attributed to engine 42%, tyres 23%, city_far 17%
- **dropout**: 34.99999999996817 ms against 20.0 -> FAILS by 0.75 tolerance units
  - longest hole 35 ms (limit 20-1000 ms), floor -65.0 dBFS; 1 hole(s)
  - transient attributed to rain_street 76%, rain_awnings 10%, city_far 9%

## Forensics (signal level)
- **47.591s** coincident transients: wipers 50%, engine 26%; step 0.0407 vs threshold 0.0210 (+5.8 dB over, z 15.5) - decomposition fit 0.02x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.796s** coincident transients: tyres 58%, engine 36%; step 0.0371 vs threshold 0.0210 (+4.9 dB over, z 14.1) - decomposition fit 0.29x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: tyres is a continuous bed with no onset, so the step is in its texture, not on a note
- **65.998s** mixed: tyres 64%, city_far 25%; step 0.0303 vs threshold 0.0210 (+3.2 dB over, z 11.5) - decomposition fit 0.0x, treat as indicative
  - under it: tyres is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note
- **95.033s** single source: engine 84%; step 0.0270 vs threshold 0.0210 (+2.2 dB over, z 10.3) - decomposition fit 0.2x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
- **149.629s** single source: engine 74%, wipers 22%; step 0.0374 vs threshold 0.0210 (+5.0 dB over, z 14.3) - decomposition fit 0.07x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **152.110s** mixed: city_far 63%, rain_street/water_film 25%; step 0.0444 vs threshold 0.0210 (+6.5 dB over, z 16.9) - decomposition fit 0.0x, treat as indicative
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -6.00    -6.00
  dropout::-: -0.75    -0.75
  clipping::-: +0.00    +0.00
  stem.clipping::tyres: +0.00    +0.00
  stem.clicks::tyres: +0.00    +0.00
  true peak::-: +0.00    +0.00

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.tyres -6 dB: 6 -> 5 (better)
- hf.tyres -9 dB: 6 -> 5 (better)
- hf.tyres -6 dB, hf.city_far -3 dB: 6 -> 5 (better)
- hf.tyres -12 dB: 6 -> 5 (better)
- hf.tyres -6 dB, hf.city_far -6 dB: 6 -> 5 (better)
- hf.tyres -9 dB, hf.city_far -3 dB: 6 -> 5 (better)
- hf.tyres -6 dB, hf.city_far -9 dB: 6 -> 5 (better)
- hf.tyres -9 dB, hf.city_far -6 dB: 6 -> 5 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.tyres` (tyres high shelf at 5500 Hz: inst_eq["sfx:np_drift_squeal"]): tyres high shelf at 5500 Hz: inst_eq["sfx:np_drift_squeal"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +54.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +54.00 (safety now -6.00)

## Closed rows
dropout - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 6 event(s) exactly (decomposition R^2 0.969); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.6 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.97); gains bass_clarinet 1.40, bass_drum 0.97, basses 1.79, celli 1.12, city_far 4.10, crash 0.19, cymbals 0.72, engine 2.65, horns 0.82, piano 1.13, piano_low 1.73, rain_awnings 0.40, rain_street 4.19, snare 0.90, sub_drop 2.18, timpani 0.78, trombones 0.76, tuba 1.42, tyres 1.38, violins_staccato 0.84, violins_tremolo 0.67, wipers 2.25'
- 'event 47.591s [coincident transients] wipers 50%, engine 26%; step 0.0407 vs threshold 0.0210 (+5.8 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 60.796s [coincident transients] tyres 58%, engine 36%; step 0.0371 vs threshold 0.0210 (+4.9 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 65.998s [mixed] tyres 64%, city_far 25%; step 0.0303 vs threshold 0.0210 (+3.2 dB over); nearest onset tyres pNone vNone +0 ms  (fit unreliable)'
- 'event 95.033s [single source] engine 84%; step 0.0270 vs threshold 0.0210 (+2.2 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 149.629s [single source] engine 74%, wipers 22%; step 0.0374 vs threshold 0.0210 (+5.0 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 152.110s [mixed] city_far 63%, rain_street/water_film 25%; step 0.0444 vs threshold 0.0210 (+6.5 dB over); nearest onset rain_street pNone vNone +0 ms  (fit unreliable)'
- 'clicks: cutting the band of engine is NOT monotone (replay: -6 dB -> 6 event(s), -3 dB -> 7 event(s), -9 dB -> 7 event(s), -12 dB -> 7 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of wipers is NOT monotone (replay: -3 dB -> 9 event(s), -6 dB -> 9 event(s), -9 dB -> 10 event(s), -12 dB -> 11 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'dropout has 1 event(s) at 170.485s; the transient is rain_street 76%, rain_awnings 10%, city_far 9%'
- 'risk closure: the levers that move this row belong to tyres, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible move improves the binding rows: every lever is burned, closed or already optimal
