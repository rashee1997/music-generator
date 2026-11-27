# Debug autopsy - western_ghats_sunrise

20261127T070943  ·  level FAIL  ·  plan replay-direction (inside model error)
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T07:00:14Z

## In question (1)
- **clicks**: 8.0 events against 0.0 -> FAILS by 8.00 tolerance units
  - 8 clustered impulse event(s) (MAD), 3 LPC frame(s); 90 event(s) rejected as a dense burst, 41 as a steep attack; max cluster span 1.429 ms
  - transient attributed to tabla 100%

## Forensics (signal level)
- **30.707s** single source: tabla 99%; step 0.1036 vs threshold 0.0645 (+4.1 dB over, z 12.9)
- **34.471s** single source: tabla 96%; step 0.0996 vs threshold 0.0645 (+3.8 dB over, z 12.4)
- **42.298s** single source: tabla 92%; step 0.1170 vs threshold 0.0645 (+5.2 dB over, z 14.5)
- **43.993s** discontinuity: tabla 96%; step 0.1100 vs threshold 0.0645 (+4.6 dB over, z 13.7)
  - under it: tabla pitch tabla_ge vel 0.62, event is -7 ms from that note's onset (written 0.4 beats)
- **45.699s** single source: tabla 97%; step 0.1045 vs threshold 0.0645 (+4.2 dB over, z 13.0)
  - under it: tabla pitch tabla_na vel 0.5, event is +199 ms from that note's onset (written 0.3 beats)
- **48.430s** single source: tabla 96%; step 0.0948 vs threshold 0.0645 (+3.4 dB over, z 11.8)
- **48.450s** single source: tabla 94%; step 0.0825 vs threshold 0.0645 (+2.1 dB over, z 10.2)
- **48.767s** single source: tabla 94%; step 0.0979 vs threshold 0.0645 (+3.6 dB over, z 12.1)

## Domains
ran: master
not run (nothing in question): stems (8 rows)
advisory, never binding: 8 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.tabla` -9.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.tabla` -9.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]

  clicks::-: -8.00    -8.00
  clipping::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  true peak::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.tabla -9 dB: 8 -> 0 (clears, 0 dB clear of the threshold)
- hf.tabla -3 dB, hf.ambience -3 dB: 8 -> 1 (better)
- hf.tabla -3 dB: 8 -> 2 (better)
- hf.tabla -12 dB: 8 -> 3 (better)
- hf.tabla -6 dB: 8 -> 6 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 8 event(s) exactly (decomposition R^2 0.519); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 1.6 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.52); gains ambience 2.56, bansuri 3.07, celli 1.04, choir 0.91, pipes 0.51, santoor 1.06, sitar 2.18, tabla 2.59, tanpura 1.52, violas 1.53, violins_counter 1.72, violins_long 1.55'
- 'event 30.707s [single source] tabla 99%; step 0.1036 vs threshold 0.0645 (+4.1 dB over)'
- 'event 34.471s [single source] tabla 96%; step 0.0996 vs threshold 0.0645 (+3.8 dB over)'
- 'event 42.298s [single source] tabla 92%; step 0.1170 vs threshold 0.0645 (+5.2 dB over)'
- 'event 43.993s [discontinuity] tabla 96%; step 0.1100 vs threshold 0.0645 (+4.6 dB over); nearest onset tabla ptabla_ge v0.62 -7 ms'
- 'event 45.699s [single source] tabla 97%; step 0.1045 vs threshold 0.0645 (+4.2 dB over); nearest onset tabla ptabla_na v0.5 +199 ms'
- 'event 48.430s [single source] tabla 96%; step 0.0948 vs threshold 0.0645 (+3.4 dB over)'
- 'event 48.450s [single source] tabla 94%; step 0.0825 vs threshold 0.0645 (+2.1 dB over)'
- 'event 48.767s [single source] tabla 94%; step 0.0979 vs threshold 0.0645 (+3.6 dB over)'
- 'clicks at 43.993s is a true discontinuity (raw step 0.15 FS): the cause is a sample start or a cut, not a band level; a shelf cannot move it'
- 'clicks: cutting the band of tabla is NOT monotone (replay: -9 dB -> 0 event(s), -3 dB -> 2 event(s), -12 dB -> 3 event(s), -6 dB -> 6 event(s) against 8 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (8, 7, 7, 7) -> (1, 4, 8, 8) after tabla -3 dB, ambience -3 dB'

## Solver
- best candidate clears the modelled row with 0 dB of margin but the model's own error is 1.6 dB: this is a direction, not a proof, and the next render is the test (it will be recorded against this prediction)
