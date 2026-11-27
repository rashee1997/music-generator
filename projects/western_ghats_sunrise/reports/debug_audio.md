# Debug autopsy - western_ghats_sunrise

20261127T093446  ·  level FAIL  ·  plan replay-direction (inside model error)
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=17 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T09:34:23Z

## In question (1)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 0 LPC frame(s); 37 event(s) rejected as a dense burst, 97 as a steep attack; max cluster span 1.451 ms
  - transient attributed to ambience 100%

## Forensics (signal level)
- **60.844s** single source: ambience 99%; step 0.0457 vs threshold 0.0453 (+0.1 dB over, z 8.1) - decomposition fit 0.05x, treat as indicative
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master
not run (nothing in question): stems (16 rows)
advisory, never binding: 16 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.ambience` -12.00 dB ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.ambience` -12.00 dB ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]

  clicks::-: -1.00    -1.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.ambience -12 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
- hf.ambience -3 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
- hf.ambience -6 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
- hf.ambience -9 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
- hf.ambience -12 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 1 event(s) exactly (decomposition R^2 0.132); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 35.1 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.13); gains ambience 2.77, bansuri 2.79, bass 0.20, celli 0.64, choir 1.30, guitar_clean 1.41, guitar_drive 1.87, kit 1.21, pipes 0.41, pipes_drone 0.58, santoor 0.94, sitar 1.76, tabla 1.39, tanpura 1.42, violas 3.01, violins_counter 1.68, violins_long 1.38'
- 'event 60.844s [single source] ambience 99%; step 0.0457 vs threshold 0.0453 (+0.1 dB over); nearest onset ambience pNone vNone +0 ms  (fit unreliable)'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (1, 11, 13, 12) -> (0, 9, 7, 7) after ambience -12 dB'

## Solver
- best candidate clears the modelled row with 0 dB of margin but the model's own error is 35.1 dB: this is a direction, not a proof, and the next render is the test (it will be recorded against this prediction)
