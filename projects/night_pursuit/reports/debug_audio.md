# Debug autopsy - night_pursuit

20261126T085634  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T08:53:13Z

## In question (1)
- **clicks**: 5.0 events against 0.0 -> FAILS by 5.00 tolerance units
  - 5 clustered impulse event(s) (MAD), 5 LPC frame(s); 305 event(s) rejected as a dense burst, 362 as a steep attack; max cluster span 1.497 ms
  - transient attributed to snare 62%, rain_street/drops 38%

## Forensics (signal level)
- **6.324s** single source: rain_street/drops 83%; step 0.0343 vs threshold 0.0281 (+1.7 dB over, z 9.8)
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
- **28.219s** single source: snare 98%; step 0.0302 vs threshold 0.0281 (+0.6 dB over, z 8.6)
- **37.040s** single source: snare 85%; step 0.0338 vs threshold 0.0281 (+1.6 dB over, z 9.6)
- **67.252s** single source: rain_street/drops 82%; step 0.0319 vs threshold 0.0281 (+1.1 dB over, z 9.1)
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
- **84.002s** single source: snare 87%; step 0.0316 vs threshold 0.0281 (+1.0 dB over, z 9.0)

## Domains
ran: master
not run (nothing in question): stems (74 rows)
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -5.00    -5.00
  clipping::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10
  true peak::-: +0.34    +0.34

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- layer.rain_street.water_film -6 dB, hf.wipers -3 dB, hf.snare -3 dB: 5 -> 1 (better)
- hf.snare -3 dB: 5 -> 2 (better)
- hf.snare -6 dB: 5 -> 2 (better)
- hf.snare -9 dB: 5 -> 2 (better)
- hf.snare -12 dB: 5 -> 2 (better)
- hf.snare -3 dB, layer.rain_street.drops -9 dB: 5 -> 2 (better)
- hf.snare -6 dB, layer.rain_street.drops -9 dB: 5 -> 2 (better)
- hf.snare -9 dB, layer.rain_street.drops -9 dB: 5 -> 2 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 5 event(s) exactly (decomposition R^2 0.965); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.5 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.96); gains bass_clarinet 1.28, bass_drum 0.97, basses 1.82, celli 1.12, city_far 4.15, crash 0.19, cymbals 0.71, engine 2.66, horns 0.84, piano 1.13, piano_low 1.76, rain_street 4.23, snare 0.91, sub_drop 2.23, timpani 0.79, trombones 0.77, tuba 1.37, tyres 1.39, violins_staccato 0.84, violins_tremolo 0.68, wipers 2.26'
- 'event 6.324s [single source] rain_street/drops 83%; step 0.0343 vs threshold 0.0281 (+1.7 dB over); nearest onset rain_street pNone vNone +0 ms'
- 'event 28.219s [single source] snare 98%; step 0.0302 vs threshold 0.0281 (+0.6 dB over)'
- 'event 37.040s [single source] snare 85%; step 0.0338 vs threshold 0.0281 (+1.6 dB over)'
- 'event 67.252s [single source] rain_street/drops 82%; step 0.0319 vs threshold 0.0281 (+1.1 dB over); nearest onset rain_street pNone vNone +0 ms'
- 'event 84.002s [single source] snare 87%; step 0.0316 vs threshold 0.0281 (+1.0 dB over)'
- 'clicks: cutting the band of rain_street/drops is NOT monotone (replay: -9 dB -> 3 event(s), -12 dB -> 3 event(s), -3 dB -> 5 event(s), -6 dB -> 7 event(s) against 5 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (5, 5, 5, 6) -> (1, 1, 2, 2) after rain_street/water_film -6 dB, wipers -3 dB, snare -3 dB'

