# Debug autopsy - indo_afro_sunrise

20261125T071051  ·  level FAIL  ·  plan replay-direction (inside model error)
sources: score=/home/user/music-generator/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-25T06:54:59Z, drift=the presets or score changed after this master was rendered: presets/mix/indo_afro_sunrise_mix.json - the autopsy describes the previous mix until you re-render
**inputs changed after this render** (presets/mix/indo_afro_sunrise_mix.json): the rows and stems below describe the previous mix, so no proposal is settled and a lever read from the presets may already be applied

## In question (1)
- **clicks**: 2.0 events against 0.0 -> FAILS by 2.00 tolerance units
  - 2 clustered impulse event(s) (MAD), 2 LPC frame(s); 1327 event(s) rejected as a dense burst, 252 as a steep attack; max cluster span 1.497 ms
  - transient attributed to tabla 50%, shekere 34%, canopy/insects 16%

## Forensics (signal level)
- **15.549s** coincident transients: shekere 59%, canopy/insects 28%; step 0.0344 vs threshold 0.0335 (+0.2 dB over, z 8.2)
  - under it: canopy is a continuous bed with no onset, so the step is in its texture, not on a note
    - impulsive layer in its preset: `drips` (impulse_cluster, -19.0 dB, 10.0 events/s) - a candidate for the transient, not a measurement
    - impulsive layer in its preset: `birds` (fm_chirp_cluster, -16.0 dB, 0.5 events/s) - a candidate for the transient, not a measurement
  - under it: shekere pitch 82 vel 0.3, event is +49 ms from that note's onset (written 0.5 beats)
- **34.712s** single source: tabla 88%; step 0.0350 vs threshold 0.0335 (+0.4 dB over, z 8.4)

## Domains
ran: master, stems
advisory, never binding: 32 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.shekere` -6.00 dB shekere high shelf at 5500 Hz: inst_eq["shekere"]
- `hf.tabla` -3.00 dB tabla high shelf at 5500 Hz: inst_eq["tabla"]
- `hf.djembe` -3.00 
- `hf.kit` -3.00 

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.shekere` -6.00 dB shekere high shelf at 5500 Hz: inst_eq["shekere"]
- `hf.tabla` -3.00 dB tabla high shelf at 5500 Hz: inst_eq["tabla"]
- `hf.djembe` -3.00  
- `hf.kit` -3.00  

  clicks::-: -2.00    -2.00
  clipping::-: +0.00    +0.00
  stem.clipping::canopy: +0.00    +0.00
  stem.clicks::canopy: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.tabla -3 dB, hf.djembe -3 dB, hf.shekere -6 dB, hf.kit -3 dB: 2 -> 0 (clears, 0 dB clear of the threshold)
- hf.shekere -3 dB, layer.canopy.insects -3 dB: 2 -> 0 (clears, 0 dB clear of the threshold)
- hf.tabla -3 dB: 2 -> 1 (better)
- hf.shekere -3 dB: 2 -> 1 (better)
- hf.tabla -6 dB: 2 -> 1 (better)
- hf.shekere -6 dB: 2 -> 1 (better)
- hf.tabla -3 dB, hf.shekere -3 dB: 2 -> 1 (better)
- hf.tabla -9 dB: 2 -> 1 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `layer.canopy.insects` (insects layer gain_db in presets/environments/amazon_rainforest.json): insects layer gain_db in presets/environments/amazon_rainforest.json cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +18.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +18.00 (safety now -2.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 2 event(s) exactly (decomposition R^2 0.879); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 1.7 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.88); gains bansuri 2.95, bass 1.58, canopy 6.29, djembe 1.42, guitar 2.12, horns 1.32, kit 1.30, marimba 0.22, shekere 1.46, sitar 0.11, tabla 1.65, tanpura 1.32'
- 'event 15.549s [coincident transients] shekere 59%, canopy/insects 28%; step 0.0344 vs threshold 0.0335 (+0.2 dB over); nearest onset canopy pNone vNone +0 ms'
- 'event 34.712s [single source] tabla 88%; step 0.0350 vs threshold 0.0335 (+0.4 dB over)'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (2, 4, 8, 9) -> (0, 1, 1, 1) after tabla -3 dB, djembe -3 dB, shekere -6 dB, kit -3 dB'
- 'risk closure: the levers that move this row belong to canopy, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible move improves the binding rows: every lever is burned, closed or already optimal
- best candidate clears the modelled row with 0 dB of margin but the model's own error is 1.7 dB: this is a direction, not a proof, and the next render is the test (it will be recorded against this prediction)
