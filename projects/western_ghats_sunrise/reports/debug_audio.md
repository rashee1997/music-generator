# Debug autopsy - western_ghats_sunrise

20261127T091656  ·  level FAIL  ·  plan solved
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=17 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T09:15:36Z

## In question (1)
- **clicks**: 8.0 events against 0.0 -> FAILS by 8.00 tolerance units
  - 8 clustered impulse event(s) (MAD), 5 LPC frame(s); 177 event(s) rejected as a dense burst, 140 as a steep attack; max cluster span 1.474 ms
  - transient attributed to ambience 66%, kit 13%, bansuri 10%

## Forensics (signal level)
- **39.789s** coincident transients: bansuri 39%, ambience 32%; step 0.0440 vs threshold 0.0432 (+0.2 dB over, z 8.2) - decomposition fit 0.08x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **45.285s** single source: kit 89%; step 0.0474 vs threshold 0.0432 (+0.8 dB over, z 8.8) - decomposition fit 0.4x, treat as indicative
- **46.698s** coincident transients: bansuri 27%, violins_long 25%, violins_counter 24%; step 0.0444 vs threshold 0.0432 (+0.2 dB over, z 8.2) - decomposition fit 0.03x, treat as indicative
- **47.624s** mixed: ambience 36%, violins_counter 27%; step 0.0442 vs threshold 0.0432 (+0.2 dB over, z 8.2) - decomposition fit -0.04x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: violins_counter pitch 64 vel 0.72, event is +124 ms from that note's onset (written 0.5 beats)
- **59.632s** single source: ambience 99%; step 0.0448 vs threshold 0.0432 (+0.3 dB over, z 8.3) - decomposition fit 0.09x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **59.665s** single source: ambience 99%; step 0.0443 vs threshold 0.0432 (+0.2 dB over, z 8.2) - decomposition fit 0.46x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.017s** single source: ambience 91%; step 0.0485 vs threshold 0.0432 (+1.0 dB over, z 9.0) - decomposition fit -0.01x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.034s** single source: ambience 99%; step 0.0452 vs threshold 0.0432 (+0.4 dB over, z 8.4) - decomposition fit 0.13x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 16 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -8.00    -8.00
  clipping::-: +0.00    +0.00
  stem.clipping::violins_counter: +0.00    +0.00
  stem.clicks::violins_counter: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.ambience -6 dB, hf.kit -9 dB: 8 -> 4 (better)
- hf.kit -3 dB: 8 -> 5 (better)
- hf.kit -3 dB: 8 -> 5 (better)
- hf.ambience -12 dB: 8 -> 5 (better)
- hf.ambience -9 dB, hf.kit -6 dB: 8 -> 5 (better)
- hf.ambience -6 dB, hf.violins_counter -9 dB: 8 -> 5 (better)
- hf.ambience -9 dB, hf.kit -9 dB: 8 -> 5 (better)
- hf.ambience -6 dB: 8 -> 6 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.violins_counter` (violins_counter high shelf at 5500 Hz: inst_eq["ghats_violins_counter"]): violins_counter high shelf at 5500 Hz: inst_eq["ghats_violins_counter"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +72.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +72.00 (safety now -8.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 8 event(s) exactly (decomposition R^2 0.218); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 27.0 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.22); gains ambience 2.92, bansuri 2.90, bass 10.32, celli 1.92, choir 1.44, guitar_clean 1.35, guitar_drive 1.74, kit 1.19, pipes 0.43, pipes_drone 0.42, santoor 1.08, sitar 1.54, tabla 1.41, tanpura 1.42, violas 0.71, violins_counter 1.69, violins_long 1.33'
- 'event 39.789s [coincident transients] bansuri 39%, ambience 32%; step 0.0440 vs threshold 0.0432 (+0.2 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 45.285s [single source] kit 89%; step 0.0474 vs threshold 0.0432 (+0.8 dB over)  (fit unreliable)'
- 'event 46.698s [coincident transients] bansuri 27%, violins_long 25%, violins_counter 24%; step 0.0444 vs threshold 0.0432 (+0.2 dB over)  (fit unreliable)'
- 'event 47.624s [mixed] ambience 36%, violins_counter 27%; step 0.0442 vs threshold 0.0432 (+0.2 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.632s [single source] ambience 99%; step 0.0448 vs threshold 0.0432 (+0.3 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.665s [single source] ambience 99%; step 0.0443 vs threshold 0.0432 (+0.2 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 60.017s [single source] ambience 91%; step 0.0485 vs threshold 0.0432 (+1.0 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 60.034s [single source] ambience 99%; step 0.0452 vs threshold 0.0432 (+0.4 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'clicks: cutting the band of ambience is NOT monotone (replay: -12 dB -> 5 event(s), -6 dB -> 6 event(s), -3 dB -> 7 event(s), -9 dB -> 7 event(s) against 8 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: cutting the band of kit is NOT monotone (replay: -3 dB -> 5 event(s), -9 dB -> 6 event(s), -6 dB -> 7 event(s), -12 dB -> 7 event(s) against 8 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (8, 6, 7, 12) -> (5, 7, 7, 12) after kit -3 dB'
- 'violins_counter: the tightest gap in the score is 58 ms at beat spacing 0.577 s (104 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'violins_counter: the tightest gap in the score is 58 ms at beat spacing 0.577 s (104 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to violins_counter, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible move improves the binding rows: every lever is burned, closed or already optimal
