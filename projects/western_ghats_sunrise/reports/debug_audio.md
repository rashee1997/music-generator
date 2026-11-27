# Debug autopsy - western_ghats_sunrise

20261127T073024  ·  level FAIL  ·  plan replay-direction (inside model error)
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T07:29:06Z, drift=the presets or score changed after this master was rendered: presets/environments/western_ghats_sunrise.json, presets/instruments/ghats_bansuri.json, presets/instruments/ghats_celli.json, presets/instruments/ghats_pipes.json - the autopsy describes the previous mix until you re-render
**inputs changed after this render** (presets/environments/western_ghats_sunrise.json, presets/instruments/ghats_bansuri.json, presets/instruments/ghats_celli.json, presets/instruments/ghats_pipes.json, presets/instruments/ghats_santoor.json, presets/instruments/ghats_sitar.json): the rows and stems below describe the previous mix, so no proposal is settled and a lever read from the presets may already be applied

## In question (1)
- **clicks**: 6.0 events against 0.0 -> FAILS by 6.00 tolerance units
  - 6 clustered impulse event(s) (MAD), 0 LPC frame(s); 88 event(s) rejected as a dense burst, 38 as a steep attack; max cluster span 1.383 ms
  - transient attributed to tabla 100%

## Forensics (signal level)
- **30.707s** single source: tabla 99%; step 0.1024 vs threshold 0.0647 (+4.0 dB over, z 12.7)
- **32.056s** single source: tabla 96%; step 0.1139 vs threshold 0.0647 (+4.9 dB over, z 14.1)
  - under it: tabla pitch tabla_ge vel 0.5, event is +56 ms from that note's onset (written 0.4 beats)
- **34.471s** single source: tabla 96%; step 0.1024 vs threshold 0.0647 (+4.0 dB over, z 12.7)
- **45.699s** single source: tabla 97%; step 0.1032 vs threshold 0.0647 (+4.1 dB over, z 12.8)
  - under it: tabla pitch tabla_na vel 0.5, event is +199 ms from that note's onset (written 0.3 beats)
- **48.430s** single source: tabla 96%; step 0.0983 vs threshold 0.0647 (+3.6 dB over, z 12.2)
- **48.767s** single source: tabla 95%; step 0.0975 vs threshold 0.0647 (+3.6 dB over, z 12.1)

## Domains
ran: master
not run (nothing in question): stems (8 rows)
advisory, never binding: 8 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.tabla` -9.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]
- `hf.bansuri` -6.00 

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.tabla` -9.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]
- `hf.bansuri` -6.00  

  clicks::-: -6.00    -6.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.bansuri -6 dB, hf.tabla -9 dB: 6 -> 0 (clears, 1 dB clear of the threshold)
- hf.tabla -9 dB: 6 -> 0 (clears, 0 dB clear of the threshold)
- hf.tabla -6 dB: 6 -> 2 (better)
- hf.tabla -12 dB: 6 -> 2 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 6 event(s) exactly (decomposition R^2 0.52); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 1.5 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.52); gains ambience 2.57, bansuri 3.07, celli 0.33, choir 0.98, pipes 0.45, santoor 1.11, sitar 2.19, tabla 2.60, tanpura 1.37, violas 1.52, violins_counter 1.72, violins_long 1.50'
- 'event 30.707s [single source] tabla 99%; step 0.1024 vs threshold 0.0647 (+4.0 dB over)'
- 'event 32.056s [single source] tabla 96%; step 0.1139 vs threshold 0.0647 (+4.9 dB over); nearest onset tabla ptabla_ge v0.5 +56 ms'
- 'event 34.471s [single source] tabla 96%; step 0.1024 vs threshold 0.0647 (+4.0 dB over)'
- 'event 45.699s [single source] tabla 97%; step 0.1032 vs threshold 0.0647 (+4.1 dB over); nearest onset tabla ptabla_na v0.5 +199 ms'
- 'event 48.430s [single source] tabla 96%; step 0.0983 vs threshold 0.0647 (+3.6 dB over)'
- 'event 48.767s [single source] tabla 95%; step 0.0975 vs threshold 0.0647 (+3.6 dB over)'
- 'clicks: cutting the band of tabla is NOT monotone (replay: -9 dB -> 0 event(s), -6 dB -> 2 event(s), -12 dB -> 2 event(s), -3 dB -> 6 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (6, 3, 5, 7) -> (0, 0, 3, 6) after bansuri -6 dB, tabla -9 dB'

## Solver
- best candidate clears the modelled row with 1 dB of margin but the model's own error is 1.5 dB: this is a direction, not a proof, and the next render is the test (it will be recorded against this prediction)
