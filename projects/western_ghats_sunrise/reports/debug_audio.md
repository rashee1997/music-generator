# Debug autopsy - western_ghats_sunrise

20261127T070014  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T06:50:09Z

## In question (1)
- **clicks**: 7.0 events against 0.0 -> FAILS by 7.00 tolerance units
  - 7 clustered impulse event(s) (MAD), 7 LPC frame(s); 141 event(s) rejected as a dense burst, 70 as a steep attack; max cluster span 1.361 ms
  - transient attributed to tabla 100%

## Forensics (signal level)
- **16.029s** single source: tabla 100%; step 0.0519 vs threshold 0.0416 (+1.9 dB over, z 10.0) - decomposition fit 1.66x, treat as indicative
- **33.059s** single source: tabla 97%; step 0.0581 vs threshold 0.0416 (+2.9 dB over, z 11.2)
- **42.661s** single source: tabla 99%; step 0.0930 vs threshold 0.0416 (+7.0 dB over, z 17.9)
- **45.386s** single source: tabla 95%; step 0.1003 vs threshold 0.0416 (+7.6 dB over, z 19.3)
- **45.727s** single source: tabla 93%; step 0.0750 vs threshold 0.0416 (+5.1 dB over, z 14.4)
  - under it: tabla pitch tabla_na vel 0.5, event is +227 ms from that note's onset (written 0.3 beats)
- **46.066s** single source: tabla 94%; step 0.0887 vs threshold 0.0416 (+6.6 dB over, z 17.0)
  - under it: tabla pitch shaker vel 0.42, event is +66 ms from that note's onset (written 0.2 beats)
- **48.406s** single source: tabla 97%; step 0.1197 vs threshold 0.0416 (+9.2 dB over, z 23.0)

## Domains
ran: master
not run (nothing in question): stems (8 rows)
advisory, never binding: 8 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -7.00    -7.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.tabla -6 dB: 7 -> 1 (better)
- hf.tabla -3 dB: 7 -> 1 (better)
- hf.tabla -6 dB: 7 -> 1 (better)
- hf.tabla -12 dB: 7 -> 4 (better)
- hf.tabla -9 dB: 7 -> 5 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 7 event(s) exactly (decomposition R^2 0.81); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.9 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.81); gains ambience 1.95, bansuri 2.80, celli 1.56, choir 0.79, pipes 0.50, santoor 0.99, sitar 2.02, tabla 2.36, tanpura 1.40, violas 1.25, violins_counter 1.55, violins_long 1.42'
- 'event 16.029s [single source] tabla 100%; step 0.0519 vs threshold 0.0416 (+1.9 dB over)  (fit unreliable)'
- 'event 33.059s [single source] tabla 97%; step 0.0581 vs threshold 0.0416 (+2.9 dB over)'
- 'event 42.661s [single source] tabla 99%; step 0.0930 vs threshold 0.0416 (+7.0 dB over)'
- 'event 45.386s [single source] tabla 95%; step 0.1003 vs threshold 0.0416 (+7.6 dB over)'
- 'event 45.727s [single source] tabla 93%; step 0.0750 vs threshold 0.0416 (+5.1 dB over); nearest onset tabla ptabla_na v0.5 +227 ms'
- 'event 46.066s [single source] tabla 94%; step 0.0887 vs threshold 0.0416 (+6.6 dB over); nearest onset tabla pshaker v0.42 +66 ms'
- 'event 48.406s [single source] tabla 97%; step 0.1197 vs threshold 0.0416 (+9.2 dB over)'
- 'clicks: cutting the band of tabla is NOT monotone (replay: -3 dB -> 1 event(s), -6 dB -> 1 event(s), -12 dB -> 4 event(s), -9 dB -> 5 event(s) against 7 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (7, 8, 5, 5) -> (1, 0, 1, 1) after tabla -6 dB'

