# Debug autopsy - western_ghats_sunrise

20261127T092246  ·  level FAIL  ·  plan solved
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=17 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T09:22:09Z

## In question (1)
- **clicks**: 6.0 events against 0.0 -> FAILS by 6.00 tolerance units
  - 6 clustered impulse event(s) (MAD), 3 LPC frame(s); 163 event(s) rejected as a dense burst, 142 as a steep attack; max cluster span 1.474 ms
  - transient attributed to ambience 80%, violins_counter 9%, bansuri 5%

## Forensics (signal level)
- **46.698s** coincident transients: bansuri 29%, violins_long 25%, violins_counter 25%; step 0.0430 vs threshold 0.0414 (+0.3 dB over, z 8.3) - decomposition fit 0.03x, treat as indicative
- **47.624s** mixed: ambience 32%, violins_counter 25%; step 0.0434 vs threshold 0.0414 (+0.4 dB over, z 8.4) - decomposition fit -0.03x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: violins_counter pitch 64 vel 0.72, event is +124 ms from that note's onset (written 0.5 beats)
- **59.632s** single source: ambience 98%; step 0.0432 vs threshold 0.0414 (+0.4 dB over, z 8.4) - decomposition fit -0.04x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **59.665s** single source: ambience 98%; step 0.0426 vs threshold 0.0414 (+0.3 dB over, z 8.2) - decomposition fit 0.18x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.017s** single source: ambience 100%; step 0.0469 vs threshold 0.0414 (+1.1 dB over, z 9.1) - decomposition fit -0.13x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.034s** single source: ambience 98%; step 0.0437 vs threshold 0.0414 (+0.5 dB over, z 8.5) - decomposition fit 0.06x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 16 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -6.00    -6.00
  clipping::-: +0.00    +0.00
  stem.clipping::bansuri: +0.00    +0.00
  stem.clicks::bansuri: +0.00    +0.00
  stem.clipping::violins_counter: +0.00    +0.00
  stem.clicks::violins_counter: +0.00    +0.00

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.kit -6 dB, hf.ambience -3 dB: 6 -> 4 (better)
- hf.ambience -3 dB, hf.violins_counter -3 dB: 6 -> 5 (better)
- hf.ambience -3 dB, hf.violins_counter -6 dB: 6 -> 5 (better)
- hf.ambience -3 dB, hf.violins_counter -9 dB: 6 -> 5 (better)
- hf.ambience -6 dB, hf.violins_counter -6 dB: 6 -> 5 (better)
- hf.ambience -3 dB, hf.bansuri -9 dB: 6 -> 5 (better)
- hf.ambience -6 dB, hf.violins_counter -9 dB: 6 -> 5 (better)
- hf.ambience -9 dB, hf.violins_counter -9 dB: 6 -> 5 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.bansuri` (bansuri high shelf at 5500 Hz: inst_eq["ghats_bansuri"]): bansuri high shelf at 5500 Hz: inst_eq["ghats_bansuri"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +54.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +54.00 (safety now -6.00)
- `hf.violins_counter` (violins_counter high shelf at 5500 Hz: inst_eq["ghats_violins_counter"]): violins_counter high shelf at 5500 Hz: inst_eq["ghats_violins_counter"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +54.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +54.00 (safety now -6.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 6 event(s) exactly (decomposition R^2 0.133); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 34.0 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.13); gains ambience 2.79, bansuri 2.94, bass 10.66, celli 1.92, choir 1.42, guitar_clean 1.36, guitar_drive 1.75, kit 1.20, pipes 0.46, pipes_drone 0.40, santoor 1.04, sitar 1.41, tabla 1.41, tanpura 1.41, violas 0.75, violins_counter 1.69, violins_long 1.31'
- 'event 46.698s [coincident transients] bansuri 29%, violins_long 25%, violins_counter 25%; step 0.0430 vs threshold 0.0414 (+0.3 dB over)  (fit unreliable)'
- 'event 47.624s [mixed] ambience 32%, violins_counter 25%; step 0.0434 vs threshold 0.0414 (+0.4 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.632s [single source] ambience 98%; step 0.0432 vs threshold 0.0414 (+0.4 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.665s [single source] ambience 98%; step 0.0426 vs threshold 0.0414 (+0.3 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 60.017s [single source] ambience 100%; step 0.0469 vs threshold 0.0414 (+1.1 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 60.034s [single source] ambience 98%; step 0.0437 vs threshold 0.0414 (+0.5 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (6, 7, 8, 11) -> (4, 7, 9, 14) after kit -6 dB, ambience -3 dB'
- 'bansuri: the tightest gap in the score is 58 ms at beat spacing 0.577 s (104 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'violins_counter: the tightest gap in the score is 58 ms at beat spacing 0.577 s (104 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'bansuri: the tightest gap in the score is 58 ms at beat spacing 0.577 s (104 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'violins_counter: the tightest gap in the score is 58 ms at beat spacing 0.577 s (104 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to bansuri, violins_counter, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible move improves the binding rows: every lever is burned, closed or already optimal
