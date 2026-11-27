# Debug autopsy - western_ghats_sunrise

20261127T092941  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=17 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T09:28:47Z

## In question (1)
- **clicks**: 4.0 events against 0.0 -> FAILS by 4.00 tolerance units
  - 4 clustered impulse event(s) (MAD), 1 LPC frame(s); 68 event(s) rejected as a dense burst, 103 as a steep attack; max cluster span 1.451 ms
  - transient attributed to ambience 78%, violins_counter 14%, bansuri 9%

## Forensics (signal level)
- **45.562s** mixed: violins_counter 52%, bansuri 33%; step 0.0487 vs threshold 0.0453 (+0.6 dB over, z 8.6) - decomposition fit 0.04x, treat as indicative
  - under it: bansuri pitch 78 vel 0.88, event is +62 ms from that note's onset (written 0.5 beats)
  - under it: violins_counter pitch 62 vel 0.72, event is +62 ms from that note's onset (written 0.5 beats)
- **60.911s** single source: ambience 100%; step 0.0550 vs threshold 0.0453 (+1.7 dB over, z 9.7) - decomposition fit 0.13x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.978s** single source: ambience 100%; step 0.0533 vs threshold 0.0453 (+1.4 dB over, z 9.4) - decomposition fit -0.05x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **61.063s** single source: ambience 100%; step 0.0472 vs threshold 0.0453 (+0.3 dB over, z 8.3) - decomposition fit 0.15x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 16 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.ambience` +6.00 dB ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  clicks::-: -4.00 -> -2.67
  clipping::-: +0.00    +0.00
  stem.clipping::ambience: +0.00    +0.00
  stem.clicks::ambience: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.ambience -9 dB: 4 -> 3 (better)
- hf.ambience -12 dB: 4 -> 3 (better)
- hf.ambience -9 dB, hf.violins_counter -3 dB: 4 -> 3 (better)
- hf.ambience -9 dB, hf.bansuri -3 dB: 4 -> 3 (better)
- hf.ambience -9 dB, hf.violins_counter -6 dB: 4 -> 3 (better)
- hf.ambience -9 dB, hf.bansuri -6 dB: 4 -> 3 (better)
- hf.ambience -9 dB, hf.violins_counter -9 dB: 4 -> 3 (better)
- hf.ambience -9 dB, hf.bansuri -9 dB: 4 -> 3 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.ambience` (ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]): ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +18.00 .. +6.00 dB within bounds -12.00 .. +6.00
  - clicks needs +18.00 (safety now -4.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 4 event(s) exactly (decomposition R^2 0.133); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 34.7 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.13); gains ambience 2.78, bansuri 2.82, celli 0.67, choir 1.27, guitar_clean 1.40, guitar_drive 1.88, kit 1.21, pipes 0.41, pipes_drone 0.56, santoor 0.93, sitar 1.65, tabla 1.39, tanpura 1.44, violas 2.94, violins_counter 1.69, violins_long 1.36'
- 'event 45.562s [mixed] violins_counter 52%, bansuri 33%; step 0.0487 vs threshold 0.0453 (+0.6 dB over); nearest onset bansuri p78 v0.88 +62 ms  (fit unreliable)'
- 'event 60.911s [single source] ambience 100%; step 0.0550 vs threshold 0.0453 (+1.7 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 60.978s [single source] ambience 100%; step 0.0533 vs threshold 0.0453 (+1.4 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 61.063s [single source] ambience 100%; step 0.0472 vs threshold 0.0453 (+0.3 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (4, 5, 11, 11) -> (4, 5, 10, 11) after bansuri -3 dB'
- 'risk closure: the levers that move this row belong to ambience, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -2.67. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
