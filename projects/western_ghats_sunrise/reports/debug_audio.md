# Debug autopsy - western_ghats_sunrise

20261127T090213  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=17 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T08:55:36Z

## In question (2)
- **clicks**: 10.0 events against 0.0 -> FAILS by 10.00 tolerance units
  - 10 clustered impulse event(s) (MAD), 2 LPC frame(s); 365 event(s) rejected as a dense burst, 178 as a steep attack; max cluster span 1.497 ms
  - transient attributed to ambience 95%, pipes 5%
- **tempo.audio**: 103.72303480332144 BPM against 2.08 -> FAILS by 101.64 tolerance units
  - measured 207.7 BPM vs 104.0 (tolerance 2.1) from the onset-envelope autocorrelation (peak 3.9x the median); beat tracker said 103.4; four-quarter drift 8.1 BPM reported, not decisive

## Forensics (signal level)
- **32.728s** single source: ambience 96%; step 0.0418 vs threshold 0.0416 (+0.0 dB over, z 8.0) - decomposition fit 0.12x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **35.843s** coincident transients: ambience 53%, pipes 34%; step 0.0429 vs threshold 0.0416 (+0.3 dB over, z 8.2) - decomposition fit 0.06x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **40.063s** mixed: ambience 64%; step 0.0444 vs threshold 0.0416 (+0.6 dB over, z 8.5) - decomposition fit 0.19x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **47.718s** mixed: ambience 40%; step 0.0421 vs threshold 0.0416 (+0.1 dB over, z 8.1) - decomposition fit 0.08x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **58.867s** single source: ambience 93%; step 0.0418 vs threshold 0.0416 (+0.0 dB over, z 8.0) - decomposition fit 0.07x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **59.632s** single source: ambience 99%; step 0.0427 vs threshold 0.0416 (+0.2 dB over, z 8.2) - decomposition fit 0.11x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **59.648s** single source: ambience 99%; step 0.0448 vs threshold 0.0416 (+0.6 dB over, z 8.6) - decomposition fit 0.27x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **59.664s** single source: ambience 100%; step 0.0427 vs threshold 0.0416 (+0.2 dB over, z 8.2) - decomposition fit 0.25x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master
not run (nothing in question): stems (16 rows)
advisory, never binding: 16 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -10.00    -10.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.ambience -9 dB: 10 -> 7 (better)
- hf.ambience -9 dB, hf.pipes -3 dB: 10 -> 7 (better)
- hf.ambience -9 dB, hf.pipes -6 dB: 10 -> 7 (better)
- hf.ambience -9 dB, hf.pipes -9 dB: 10 -> 7 (better)
- hf.ambience -12 dB: 10 -> 8 (better)
- hf.ambience -6 dB: 10 -> 9 (better)
- hf.ambience -6 dB, hf.pipes -3 dB: 10 -> 9 (better)
- hf.ambience -6 dB, hf.pipes -6 dB: 10 -> 9 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 10 vs gate 8; missing at [], extra at [59.935, 60.018]): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 26.6 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.23); gains ambience 2.97, bansuri 2.86, bass 9.92, celli 1.89, choir 1.41, guitar_clean 1.33, guitar_drive 1.71, kit 1.18, pipes 0.43, pipes_drone 0.47, santoor 1.08, sitar 1.48, tabla 1.41, tanpura 1.48, violas 0.77, violins_counter 1.67, violins_long 1.40'
- 'event 32.728s [single source] ambience 96%; step 0.0418 vs threshold 0.0416 (+0.0 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 35.843s [coincident transients] ambience 53%, pipes 34%; step 0.0429 vs threshold 0.0416 (+0.3 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 40.063s [mixed] ambience 64%; step 0.0444 vs threshold 0.0416 (+0.6 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 47.718s [mixed] ambience 40%; step 0.0421 vs threshold 0.0416 (+0.1 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 58.867s [single source] ambience 93%; step 0.0418 vs threshold 0.0416 (+0.0 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.632s [single source] ambience 99%; step 0.0427 vs threshold 0.0416 (+0.2 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.648s [single source] ambience 99%; step 0.0448 vs threshold 0.0416 (+0.6 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.664s [single source] ambience 100%; step 0.0427 vs threshold 0.0416 (+0.2 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'clicks: cutting the band of ambience is NOT monotone (replay: -9 dB -> 7 event(s), -12 dB -> 8 event(s), -6 dB -> 9 event(s), -3 dB -> 10 event(s) against 10 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'tempo.audio: no domain module examines this row yet'

## Solver
- the best candidate comes from a model that failed its sham test, so it is not adopted as a plan
