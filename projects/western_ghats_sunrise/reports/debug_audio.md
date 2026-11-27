# Debug autopsy - western_ghats_sunrise

20261127T065009  ·  level FAIL  ·  plan replay-direction (inside model error)
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=11 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T06:42:19Z

## In question (1)
- **clicks**: 2.0 events against 0.0 -> FAILS by 2.00 tolerance units
  - 2 clustered impulse event(s) (MAD), 1 LPC frame(s); 105 event(s) rejected as a dense burst, 60 as a steep attack; max cluster span 1.406 ms
  - transient attributed to tabla 100%

## Forensics (signal level)
- **33.062s** single source: tabla 99%; step 0.0302 vs threshold 0.0200 (+3.6 dB over, z 26.4)
- **33.736s** single source: tabla 98%; step 0.0248 vs threshold 0.0200 (+1.9 dB over, z 21.7)

## Domains
ran: master
not run (nothing in question): stems (8 rows)
advisory, never binding: 8 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.tabla` -3.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.tabla` -3.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]

  clicks::-: -2.00    -2.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.tabla -3 dB: 2 -> 0 (clears, 1 dB clear of the threshold)
- hf.tabla -9 dB: 2 -> 0 (clears, 0 dB clear of the threshold)
- hf.tabla -6 dB: 2 -> 1 (better)
- hf.tabla -12 dB: 2 -> 1 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 2 event(s) exactly (decomposition R^2 0.758); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 6.0 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.76); gains ambience 1.44, bansuri 1.37, celli 1.36, choir 0.44, santoor 0.54, sitar 2.03, tabla 1.32, tanpura 1.28, violas 1.21, violins_counter 0.85, violins_long 0.44'
- 'event 33.062s [single source] tabla 99%; step 0.0302 vs threshold 0.0200 (+3.6 dB over)'
- 'event 33.736s [single source] tabla 98%; step 0.0248 vs threshold 0.0200 (+1.9 dB over)'
- 'clicks: cutting the band of tabla is NOT monotone (replay: -3 dB -> 0 event(s), -9 dB -> 0 event(s), -6 dB -> 1 event(s), -12 dB -> 1 event(s) against 2 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'

## Solver
- best candidate clears the modelled row with 1 dB of margin but the model's own error is 6.0 dB: this is a direction, not a proof, and the next render is the test (it will be recorded against this prediction)
