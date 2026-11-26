# Debug autopsy - night_pursuit

20261126T082021  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T08:00:20Z

## In question (2)
- **clicks**: 12.0 events against 0.0 -> FAILS by 12.00 tolerance units
  - 12 clustered impulse event(s) (MAD), 12 LPC frame(s); 2091 event(s) rejected as a dense burst, 1089 as a steep attack; max cluster span 1.497 ms
  - transient attributed to wipers 57%, engine 18%, city_far 8%
- **dropout**: 69.99999999999318 ms against 20.0 -> FAILS by 2.50 tolerance units
  - longest hole 70 ms (limit 20-1000 ms), floor -65.0 dBFS; 1 hole(s)
  - transient attributed to rain_street 64%, city_far 14%, engine 11%

## Forensics (signal level)
- **5.060s** single source: wipers 93%; step 0.0343 vs threshold 0.0200 (+4.7 dB over, z 13.7) - decomposition fit 0.03x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **9.769s** single source: wipers 94%; step 0.0314 vs threshold 0.0200 (+3.9 dB over, z 12.6) - decomposition fit 0.03x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **48.857s** coincident transients: wipers 52%, engine 42%; step 0.0245 vs threshold 0.0200 (+1.8 dB over, z 9.8) - decomposition fit 0.08x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **51.384s** single source: engine 81%; step 0.0272 vs threshold 0.0200 (+2.7 dB over, z 10.9) - decomposition fit 0.05x, treat as indicative
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
- **90.163s** single source: wipers 77%; step 0.0233 vs threshold 0.0200 (+1.3 dB over, z 9.3) - decomposition fit 0.16x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **104.823s** single source: wipers 74%; step 0.0221 vs threshold 0.0200 (+0.9 dB over, z 8.8) - decomposition fit 0.03x, treat as indicative
  - under it: wipers is a continuous bed with no onset, so the step is in its texture, not on a note
- **156.816s** mixed: city_far 54%, rain_street/water_film 26%; step 0.0206 vs threshold 0.0200 (+0.2 dB over, z 8.2) - decomposition fit 0.0x, treat as indicative
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: city_far is a continuous bed with no onset, so the step is in its texture, not on a note
- **156.902s** coincident transients: siren_first 36%, violins_tremolo 26%, rain_street/water_film 22%; step 0.0417 vs threshold 0.0200 (+6.4 dB over, z 16.7) - decomposition fit 0.0x, treat as indicative
  - under it: siren_first is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master
not run (nothing in question): stems (74 rows)
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -12.00    -12.00
  dropout::-: -2.50    -2.50
  clipping::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  true peak::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
clicks, dropout - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 12 vs gate 8; missing at [], extra at [160.877, 164.582, 164.983]): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 0.5 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.98); gains bass_clarinet 1.28, bass_drum 0.98, basses 1.82, celli 1.12, city_far 4.15, crash 0.19, cymbals 0.67, engine 2.66, horns 0.83, piano 1.10, piano_low 1.71, rain_street 4.23, snare 0.91, sub_drop 2.03, timpani 0.76, trombones 0.77, tuba 1.37, tyres 1.39, violins_staccato 0.84, violins_tremolo 0.67, wipers 2.26'
- 'event 5.060s [single source] wipers 93%; step 0.0343 vs threshold 0.0200 (+4.7 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 9.769s [single source] wipers 94%; step 0.0314 vs threshold 0.0200 (+3.9 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 48.857s [coincident transients] wipers 52%, engine 42%; step 0.0245 vs threshold 0.0200 (+1.8 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 51.384s [single source] engine 81%; step 0.0272 vs threshold 0.0200 (+2.7 dB over); nearest onset engine pNone vNone +0 ms  (fit unreliable)'
- 'event 90.163s [single source] wipers 77%; step 0.0233 vs threshold 0.0200 (+1.3 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 104.823s [single source] wipers 74%; step 0.0221 vs threshold 0.0200 (+0.9 dB over); nearest onset wipers pNone vNone +0 ms  (fit unreliable)'
- 'event 156.816s [mixed] city_far 54%, rain_street/water_film 26%; step 0.0206 vs threshold 0.0200 (+0.2 dB over); nearest onset rain_street pNone vNone +0 ms  (fit unreliable)'
- 'event 156.902s [coincident transients] siren_first 36%, violins_tremolo 26%, rain_street/water_film 22%; step 0.0417 vs threshold 0.0200 (+6.4 dB over); nearest onset siren_first pNone vNone +0 ms  (fit unreliable)'
- 'clicks: cutting the band of engine is NOT monotone (replay: -3 dB -> 14 event(s), -6 dB -> 14 event(s), -9 dB -> 14 event(s), -12 dB -> 15 event(s) against 12 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of wipers is NOT monotone (replay: -6 dB -> 12 event(s), -9 dB -> 12 event(s), -3 dB -> 13 event(s), -12 dB -> 14 event(s) against 12 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of rain_street/water_film is NOT monotone (replay: -3 dB -> 12 event(s), -6 dB -> 12 event(s), -9 dB -> 13 event(s), -12 dB -> 13 event(s) against 12 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'dropout has 1 event(s) at 170.310s; the transient is rain_street 64%, city_far 13%, engine 11%'

