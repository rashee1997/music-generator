# Debug autopsy - western_ghats_sunrise

20261127T090956  ·  level FAIL  ·  plan solved
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=17 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T09:02:13Z

## In question (1)
- **clicks**: 4.0 events against 0.0 -> FAILS by 4.00 tolerance units
  - 4 clustered impulse event(s) (MAD), 0 LPC frame(s); 189 event(s) rejected as a dense burst, 146 as a steep attack; max cluster span 1.474 ms
  - transient attributed to ambience 100%

## Forensics (signal level)
- **59.632s** single source: ambience 99%; step 0.0448 vs threshold 0.0432 (+0.3 dB over, z 8.3) - decomposition fit 0.09x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **59.665s** single source: ambience 99%; step 0.0443 vs threshold 0.0432 (+0.2 dB over, z 8.2) - decomposition fit 0.46x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.017s** single source: ambience 91%; step 0.0486 vs threshold 0.0432 (+1.0 dB over, z 9.0) - decomposition fit -0.01x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
- **60.034s** single source: ambience 99%; step 0.0453 vs threshold 0.0432 (+0.4 dB over, z 8.4) - decomposition fit 0.13x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 16 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -4.00    -4.00
  clipping::-: +0.00    +0.00
  stem.clipping::ambience: +0.00    +0.00
  stem.clicks::ambience: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.ambience -12 dB: 4 -> 3 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.ambience` (ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]): ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +18.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +18.00 (safety now -4.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 4 event(s) exactly (decomposition R^2 0.218); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 26.8 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.22); gains ambience 2.92, bansuri 2.91, bass 10.35, celli 1.93, choir 1.43, guitar_clean 1.34, guitar_drive 1.75, kit 1.19, pipes 0.43, pipes_drone 0.42, santoor 1.08, sitar 1.54, tabla 1.41, tanpura 1.43, violas 0.70, violins_counter 1.69, violins_long 1.45'
- 'event 59.632s [single source] ambience 99%; step 0.0448 vs threshold 0.0432 (+0.3 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 59.665s [single source] ambience 99%; step 0.0443 vs threshold 0.0432 (+0.2 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 60.017s [single source] ambience 91%; step 0.0486 vs threshold 0.0432 (+1.0 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'event 60.034s [single source] ambience 99%; step 0.0453 vs threshold 0.0432 (+0.4 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'risk closure: the levers that move this row belong to ambience, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible move improves the binding rows: every lever is burned, closed or already optimal
