# Debug autopsy - night_pursuit

20261126T074328  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T07:24:34Z

## In question (2)
- **clicks**: 6.0 events against 0.0 -> FAILS by 6.00 tolerance units
  - 6 clustered impulse event(s) (MAD), 6 LPC frame(s); 1550 event(s) rejected as a dense burst, 643 as a steep attack; max cluster span 1.497 ms
  - transient attributed to wipers 29%, engine 27%, tyres 23%
- **dropout**: 34.99999999996817 ms against 20.0 -> FAILS by 0.75 tolerance units
  - longest hole 35 ms (limit 20-1000 ms), floor -65.0 dBFS; 1 hole(s)
  - transient attributed to rain_street 76%, rain_awnings 10%, city_far 9%

## Forensics (signal level)
- **46.571s** single source: wipers 77%; step 0.0216 vs threshold 0.0208 (+0.3 dB over, z 8.3) - decomposition fit 0.08x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **47.591s** coincident transients: wipers 50%, engine 26%; step 0.0407 vs threshold 0.0208 (+5.8 dB over, z 15.6) - decomposition fit 0.02x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.796s** coincident transients: tyres 58%, engine 36%; step 0.0370 vs threshold 0.0208 (+5.0 dB over, z 14.2) - decomposition fit 0.29x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: tyres is a continuous bed with no onset, so the step is in its texture, not on a note
- **65.998s** mixed: tyres 60%, city_far 23%; step 0.0303 vs threshold 0.0208 (+3.3 dB over, z 11.7) - decomposition fit 0.0x, treat as indicative
  - under it: tyres is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note
- **149.629s** single source: engine 74%, wipers 22%; step 0.0371 vs threshold 0.0208 (+5.0 dB over, z 14.3) - decomposition fit 0.07x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **152.110s** single source: city_far 83%; step 0.0444 vs threshold 0.0208 (+6.6 dB over, z 17.1) - decomposition fit 0.0x, treat as indicative
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note

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
- hf.tyres -3 dB: 6 -> 5 (better)
- hf.tyres -3 dB, hf.city_far -3 dB: 6 -> 5 (better)
- hf.tyres -3 dB, hf.city_far -6 dB: 6 -> 5 (better)
- hf.tyres -12 dB: 6 -> 5 (better)
- hf.tyres -3 dB, hf.city_far -9 dB: 6 -> 5 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
dropout - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 6 event(s) exactly (decomposition R^2 0.968); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.6 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.97); gains bass_clarinet 1.42, bass_drum 1.20, basses 1.81, celli 1.05, city_far 4.09, crash 0.18, cymbals 0.70, engine 2.65, horns 0.85, piano 1.06, piano_low 2.10, rain_awnings 0.49, rain_street 4.19, snare 0.89, sub_drop 1.95, timpani 0.89, trombones 0.76, tuba 1.39, tyres 1.39, violins_staccato 0.80, violins_tremolo 0.68, wipers 2.16'
- 'event 46.571s [single source] wipers 77%; step 0.0216 vs threshold 0.0208 (+0.3 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 47.591s [coincident transients] wipers 50%, engine 26%; step 0.0407 vs threshold 0.0208 (+5.8 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 60.796s [coincident transients] tyres 58%, engine 36%; step 0.0370 vs threshold 0.0208 (+5.0 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 65.998s [mixed] tyres 60%, city_far 23%; step 0.0303 vs threshold 0.0208 (+3.3 dB over); nearest onset tyres pNone vNone +0 ms  (fit unreliable)'
- 'event 149.629s [single source] engine 74%, wipers 22%; step 0.0371 vs threshold 0.0208 (+5.0 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 152.110s [single source] city_far 83%; step 0.0444 vs threshold 0.0208 (+6.6 dB over); nearest onset city_far pNone vNone +0 ms  (fit unreliable)'
- 'clicks: cutting the band of engine is NOT monotone (replay: -3 dB -> 8 event(s), -6 dB -> 8 event(s), -12 dB -> 8 event(s), -9 dB -> 10 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of tyres is NOT monotone (replay: -3 dB -> 5 event(s), -12 dB -> 5 event(s), -6 dB -> 6 event(s), -9 dB -> 6 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of wipers is NOT monotone (replay: -3 dB -> 7 event(s), -6 dB -> 7 event(s), -9 dB -> 8 event(s), -12 dB -> 8 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'dropout has 1 event(s) at 170.485s; the transient is rain_street 76%, rain_awnings 10%, city_far 9%'

