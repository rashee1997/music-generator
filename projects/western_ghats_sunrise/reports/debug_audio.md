# Debug autopsy - western_ghats_sunrise

20261127T071358  ·  level FAIL  ·  plan replay-proved
sources: score=/home/user/music-generator/projects/western_ghats_sunrise/scores/western_ghats_sunrise_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_western_ghats_sunrise.wav, verdict=2026-11-27T07:09:43Z

## In question (1)
- **clicks**: 2.0 events against 0.0 -> FAILS by 2.00 tolerance units
  - 2 clustered impulse event(s) (MAD), 2 LPC frame(s); 83 event(s) rejected as a dense burst, 48 as a steep attack; max cluster span 1.474 ms
  - transient attributed to tabla 100%

## Forensics (signal level)
- **34.815s** single source: tabla 94%; step 0.0689 vs threshold 0.0476 (+3.2 dB over, z 11.6)
- **40.924s** discontinuity: tabla 92%; step 0.0952 vs threshold 0.0476 (+6.0 dB over, z 16.0)

## Domains
ran: master, stems
advisory, never binding: 8 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.tabla` -12.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.tabla` -12.00 dB tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]

  clicks::-: -2.00    -2.00
  clipping::-: +0.00    +0.00
  stem.clipping::tabla: +0.00    +0.00
  stem.clicks::tabla: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.tabla -12 dB: 2 -> 0 (clears, 2 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.tabla` (tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"]): tabla high shelf at 5500 Hz: inst_eq["ghats_tabla"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +6.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +6.00 (safety now -2.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 2 event(s) exactly (decomposition R^2 0.963); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.6 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.96); gains ambience 5.19, bansuri 2.95, celli 1.24, choir 1.22, pipes 0.51, santoor 0.90, sitar 2.11, tabla 2.54, tanpura 1.37, violas 1.58, violins_counter 1.70, violins_long 1.51'
- 'event 34.815s [single source] tabla 94%; step 0.0689 vs threshold 0.0476 (+3.2 dB over)'
- 'event 40.924s [discontinuity] tabla 92%; step 0.0952 vs threshold 0.0476 (+6.0 dB over)'
- 'clicks at 40.924s is a true discontinuity (raw step 0.43 FS): the cause is a sample start or a cut, not a band level; a shelf cannot move it'
- 'tabla: the tightest gap in the score is 136 ms at beat spacing 0.682 s (88 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'tabla: the tightest gap in the score is 136 ms at beat spacing 0.682 s (88 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to tabla, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible move improves the binding rows: every lever is burned, closed or already optimal
- clearing set read from a replay through the gate's own checker, not from the linear model; the next render is the measurement
