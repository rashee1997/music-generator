# Debug autopsy - indo_afro_sunrise

20261128T070605  ·  level FAIL  ·  plan replay-proved
sources: score=/home/user/music-generator/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=14 processed stems from .cache/mix, master=out/_draft_indo_afro_sunrise.wav, verdict=2026-11-28T07:00:23Z

## In question (1)
- **clicks**: 3.0 events against 0.0 -> FAILS by 3.00 tolerance units
  - 3 clustered impulse event(s) (MAD), 2 LPC frame(s); 180 event(s) rejected as a dense burst, 105 as a steep attack; max cluster span 1.474 ms
  - transient attributed to kit 100%

## Forensics (signal level)
- **18.497s** single source: kit 86%; step 0.0598 vs threshold 0.0585 (+0.2 dB over, z 8.2)
  - under it: kit pitch 54 vel 0.519, event is -3 ms from that note's onset (written 0.25 beats)
- **32.828s** single source: kit 87%; step 0.0633 vs threshold 0.0585 (+0.7 dB over, z 8.6)
  - under it: kit pitch 54 vel 0.617, event is +78 ms from that note's onset (written 0.25 beats)
- **36.322s** single source: kit 89%; step 0.0626 vs threshold 0.0585 (+0.6 dB over, z 8.6)
  - under it: kit pitch 54 vel 0.608, event is +72 ms from that note's onset (written 0.25 beats)

## Domains
ran: master, stems
advisory, never binding: 32 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.kit` +3.00 dB kit high shelf at 5500 Hz: inst_eq["kit"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.kit` -6.00 dB kit high shelf at 5500 Hz: inst_eq["kit"]
- `layer.canopy.insects` -3.00  

  clicks::-: -3.00 -> -2.67
  clipping::-: +0.00    +0.00
  stem.clipping::kit: +0.00    +0.00
  stem.clicks::kit: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.kit -6 dB, layer.canopy.insects -3 dB: 3 -> 0 (clears, 2 dB clear of the threshold)
- hf.kit -6 dB: 3 -> 0 (clears, 2 dB clear of the threshold)
- hf.kit -9 dB: 3 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -12 dB: 3 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -3 dB: 3 -> 1 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Prediction record: 2 settled, 2 held, 0 did not

## Conflicts (no value satisfies both)
- `hf.kit` (kit high shelf at 5500 Hz: inst_eq["kit"]): kit high shelf at 5500 Hz: inst_eq["kit"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +27.00 .. +3.00 dB within bounds -12.00 .. +3.00
  - clicks needs +27.00 (safety now -3.00)

## Already tried (not proposed again)
- `onset.kit.ms` (kit onset ramp) for clicks
- `onset.kit.all` (kit ramp every onset) for clicks

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 3 event(s) exactly (decomposition R^2 0.952); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 1.0 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.95); gains bansuri -0.06, bass 0.67, canopy 3.91, djembe 1.30, guitar 1.89, horns 1.35, kit 1.18, marimba -0.16, shekere 1.27, tabla 1.51, tanpura 0.12, vocal_group 2.69, vocal_lead 3.44'
- 'event 18.497s [single source] kit 86%; step 0.0598 vs threshold 0.0585 (+0.2 dB over); nearest onset kit p54 v0.519 -3 ms'
- 'event 32.828s [single source] kit 87%; step 0.0633 vs threshold 0.0585 (+0.7 dB over); nearest onset kit p54 v0.617 +78 ms'
- 'event 36.322s [single source] kit 89%; step 0.0626 vs threshold 0.0585 (+0.6 dB over); nearest onset kit p54 v0.608 +72 ms'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (3, 5, 8, 6) -> (0, 0, 0, 4) after kit -6 dB, canopy/insects -3 dB'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to kit, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -2.67. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
- clearing set read from a replay through the gate's own checker, not from the linear model; the next render is the measurement
