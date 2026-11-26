# Debug autopsy - night_pursuit

20261126T072726  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T07:24:34Z

## In question (2)
- **clicks**: 6.0 events against 0.0 -> FAILS by 6.00 tolerance units
  - 6 clustered impulse event(s) (MAD), 6 LPC frame(s); 1883 event(s) rejected as a dense burst, 709 as a steep attack; max cluster span 1.497 ms
  - transient attributed to engine 39%, wipers 33%, rain_street/water_film 15%
- **dropout**: 34.99999999996817 ms against 20.0 -> FAILS by 0.75 tolerance units
  - longest hole 35 ms (limit 20-1000 ms), floor -65.1 dBFS; 1 hole(s)
  - transient attributed to rain_street 77%, rain_awnings 9%, city_far 9%

## Forensics (signal level)
- **24.627s** single source: snare 72%, wipers 26%; step 0.0339 vs threshold 0.0324 (+0.4 dB over, z 8.4)
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **24.752s** mixed: wipers 66%, engine 26%; step 0.0407 vs threshold 0.0324 (+2.0 dB over, z 10.1) - decomposition fit 0.02x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **107.454s** single source: wipers 95%; step 0.0406 vs threshold 0.0324 (+2.0 dB over, z 10.0) - decomposition fit 0.17x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **136.402s** single source: engine 98%; step 0.0336 vs threshold 0.0324 (+0.3 dB over, z 8.3)
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
- **147.492s** single source: engine 97%; step 0.0326 vs threshold 0.0324 (+0.1 dB over, z 8.1)
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
- **152.110s** single source: rain_street/water_film 86%; step 0.0434 vs threshold 0.0324 (+2.6 dB over, z 10.7) - decomposition fit 0.0x, treat as indicative
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master
not run (nothing in question): stems (74 rows)
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -6.00    -6.00
  dropout::-: -0.75    -0.75
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.engine -9 dB, hf.snare -3 dB: 6 -> 1 (better)
- hf.engine -9 dB: 6 -> 1 (better)
- hf.engine -3 dB, hf.wipers -6 dB: 6 -> 1 (better)
- hf.engine -6 dB, hf.wipers -3 dB: 6 -> 1 (better)
- hf.engine -6 dB, hf.snare -3 dB: 6 -> 1 (better)
- hf.engine -3 dB, hf.wipers -9 dB: 6 -> 1 (better)
- hf.engine -9 dB, layer.rain_street.water_film -3 dB: 6 -> 1 (better)
- hf.engine -6 dB, hf.snare -6 dB: 6 -> 1 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
dropout - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 6 event(s) exactly (decomposition R^2 0.976); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.6 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.98); gains bass_clarinet 1.39, bass_drum 1.17, basses 1.78, celli 1.03, city_far 4.07, crash 0.17, cymbals 0.68, engine 2.61, horns 0.84, piano 1.06, piano_low 2.09, rain_awnings 0.31, rain_street 4.13, snare 0.88, sub_drop 1.73, timpani 0.65, trombones 0.76, tuba 0.98, tyres 1.36, violins_staccato 0.79, violins_tremolo 0.66, wipers 2.15'
- 'event 24.627s [single source] snare 72%, wipers 26%; step 0.0339 vs threshold 0.0324 (+0.4 dB over); nearest onset wipers pNone vNone +0 ms'
- 'event 24.752s [mixed] wipers 66%, engine 26%; step 0.0407 vs threshold 0.0324 (+2.0 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 107.454s [single source] wipers 95%; step 0.0406 vs threshold 0.0324 (+2.0 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 136.402s [single source] engine 98%; step 0.0336 vs threshold 0.0324 (+0.3 dB over); nearest onset engine pNone vNone +0 ms'
- 'event 147.492s [single source] engine 97%; step 0.0326 vs threshold 0.0324 (+0.1 dB over); nearest onset engine pNone vNone +0 ms'
- 'event 152.110s [single source] rain_street/water_film 86%; step 0.0434 vs threshold 0.0324 (+2.6 dB over); nearest onset rain_street pNone vNone +0 ms  (fit unreliable)'
- 'clicks: cutting the band of engine is NOT monotone (replay: -9 dB -> 1 event(s), -6 dB -> 2 event(s), -3 dB -> 3 event(s), -12 dB -> 3 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of wipers is NOT monotone (replay: -9 dB -> 3 event(s), -12 dB -> 3 event(s), -3 dB -> 4 event(s), -6 dB -> 5 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (6, 4, 7, 6) -> (1, 4, 5, 8) after engine -9 dB, snare -3 dB'
- 'dropout has 1 event(s) at 170.485s; the transient is rain_street 77%, rain_awnings 9%, city_far 9%'

