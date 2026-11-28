# Debug autopsy - western_ghats_sunrise

20261127T094018  ·  level FAIL  ·  plan replay-direction (inside model error)
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=17 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T09:39:23Z

## In question (1)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 0 LPC frame(s); 53 event(s) rejected as a dense burst, 91 as a steep attack; max cluster span 1.134 ms
  - transient attributed to ambience 100%

## Forensics (signal level)
- **60.844s** single source: ambience 99%; step 0.0458 vs threshold 0.0452 (+0.1 dB over, z 8.1) - decomposition fit 0.06x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 16 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.ambience` +6.00 dB ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.ambience` -12.00 dB ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]

  clicks::-: -1.00 -> -0.33
  clipping::-: +0.00    +0.00
  stem.clipping::ambience: +0.00    +0.00
  stem.clicks::ambience: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.ambience -12 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
- hf.ambience -6 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
- hf.ambience -9 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
- hf.ambience -12 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.ambience` (ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]): ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +9.00 .. +6.00 dB within bounds -12.00 .. +6.00
  - clicks needs +9.00 (safety now -1.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 1 event(s) exactly (decomposition R^2 0.132); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 34.9 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.13); gains ambience 2.77, bansuri 2.80, bass 0.43, celli 0.77, choir 1.28, guitar_clean 1.39, guitar_drive 1.85, kit 1.22, pipes 0.43, pipes_drone 0.60, santoor 0.93, sitar 1.77, tabla 1.38, tanpura 1.44, violas 2.67, violins_counter 1.67, violins_long 1.37'
- 'event 60.844s [single source] ambience 99%; step 0.0458 vs threshold 0.0452 (+0.1 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (1, 7, 13, 12) -> (0, 5, 4, 10) after ambience -12 dB'
- 'risk closure: the levers that move this row belong to ambience, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -0.33. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
- best candidate clears the modelled row with 0 dB of margin but the model's own error is 34.9 dB: this is a direction, not a proof, and the next render is the test (it will be recorded against this prediction)
