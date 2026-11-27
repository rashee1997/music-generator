# Debug autopsy - western_ghats_sunrise

20261127T073533  ·  level FAIL  ·  plan replay-direction (inside model error)
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T07:34:33Z, drift=the presets or score changed after this master was rendered: presets/environments/western_ghats_sunrise.json, presets/instruments/ghats_bansuri.json, presets/instruments/ghats_celli.json, presets/instruments/ghats_pipes.json - the autopsy describes the previous mix until you re-render
**inputs changed after this render** (presets/environments/western_ghats_sunrise.json, presets/instruments/ghats_bansuri.json, presets/instruments/ghats_celli.json, presets/instruments/ghats_pipes.json, presets/instruments/ghats_santoor.json, presets/instruments/ghats_sitar.json): the rows and stems below describe the previous mix, so no proposal is settled and a lever read from the presets may already be applied

## In question (1)
- **clicks**: 3.0 events against 0.0 -> FAILS by 3.00 tolerance units
  - 3 clustered impulse event(s) (MAD), 2 LPC frame(s); 190 event(s) rejected as a dense burst, 39 as a steep attack; max cluster span 1.451 ms
  - transient attributed to tabla 92%, ambience 8%

## Forensics (signal level)
- **34.117s** single source: tabla 76%, ambience 22%; step 0.0710 vs threshold 0.0477 (+3.5 dB over, z 11.9)
  - under it: ambience is a continuous bed with no onset, so the step is in its texture, not on a note
  - under it: tabla pitch tabla_na vel 0.4, event is +116 ms from that note's onset (written 0.3 beats)
- **45.023s** single source: tabla 81%; step 0.0583 vs threshold 0.0477 (+1.7 dB over, z 9.8)
  - under it: tabla pitch shaker vel 0.42, event is +23 ms from that note's onset (written 0.2 beats)
- **47.067s** single source: tabla 93%; step 0.0591 vs threshold 0.0477 (+1.9 dB over, z 9.9)
  - under it: tabla pitch tabla_tin vel 0.52, event is +67 ms from that note's onset (written 0.3 beats)

## Domains
ran: master
not run (nothing in question): stems (8 rows)
advisory, never binding: 8 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.ambience` -6.00 dB ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.ambience` -6.00 dB ambience high shelf at 5500 Hz: inst_eq["env:western_ghats_sunrise"]

  clicks::-: -3.00    -3.00
  clipping::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10
  true peak::-: +0.24    +0.24

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.ambience -6 dB: 3 -> 0 (clears, 1 dB clear of the threshold)
- hf.ambience -3 dB: 3 -> 1 (better)
- hf.ambience -9 dB: 3 -> 2 (better)
- hf.ambience -12 dB: 3 -> 2 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Prediction record: 6 settled, 0 held, 6 did not
- `hf.tabla`: replay predicted 0 event(s), the render said worse
- `hf.tabla`: replay predicted 0 event(s), the render said worse
- `hf.tabla`: replay predicted 0 event(s), the render said worse
- `hf.tabla`: replay predicted 0 event(s), the render said worse
- `hf.tabla`: replay predicted 0 event(s), the render said worse
- `hf.tabla`: replay predicted 0 event(s), the render said worse

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Already tried (not proposed again)
- `hf.tabla` (tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]) for clicks

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 3 event(s) exactly (decomposition R^2 0.937); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 1.1 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.94); gains ambience 5.27, bansuri 3.02, celli 1.64, choir 1.14, pipes 0.51, santoor 0.92, sitar 2.06, tabla 2.55, tanpura 1.41, violas 1.59, violins_counter 1.72, violins_long 1.46'
- 'event 34.117s [single source] tabla 76%, ambience 22%; step 0.0710 vs threshold 0.0477 (+3.5 dB over); nearest onset ambience pNone vNone +0 ms'
- 'event 45.023s [single source] tabla 81%; step 0.0583 vs threshold 0.0477 (+1.7 dB over); nearest onset tabla pshaker v0.42 +23 ms'
- 'event 47.067s [single source] tabla 93%; step 0.0591 vs threshold 0.0477 (+1.9 dB over); nearest onset tabla ptabla_tin v0.52 +67 ms'
- 'clicks: cutting the band of ambience is NOT monotone (replay: -6 dB -> 0 event(s), -3 dB -> 1 event(s), -9 dB -> 2 event(s), -12 dB -> 2 event(s) against 3 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (3, 5, 2, 3) -> (0, 0, 0, 0) after tabla -9 dB, ambience -3 dB'

## Solver
- best candidate clears the modelled row with 1 dB of margin but the model's own error is 1.1 dB: this is a direction, not a proof, and the next render is the test (it will be recorded against this prediction)
