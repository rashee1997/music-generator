# Debug autopsy - indo_afro_sunrise

20261128T070022  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/home/user/music-generator/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=14 processed stems from .cache/mix, master=out/_draft_indo_afro_sunrise.wav, verdict=2026-11-28T06:40:34Z

## In question (1)
- **clicks**: 9.0 events against 0.0 -> FAILS by 9.00 tolerance units
  - 9 clustered impulse event(s) (MAD), 7 LPC frame(s); 368 event(s) rejected as a dense burst, 149 as a steep attack; max cluster span 1.497 ms
  - transient attributed to kit 100%

## Forensics (signal level)
- **18.497s** single source: kit 84%; step 0.0661 vs threshold 0.0566 (+1.4 dB over, z 9.3)
  - under it: kit pitch 54 vel 0.519, event is -3 ms from that note's onset (written 0.25 beats)
- **24.369s** single source: kit 99%; step 0.0589 vs threshold 0.0566 (+0.3 dB over, z 8.3)
- **30.706s** single source: kit 100%; step 0.0597 vs threshold 0.0566 (+0.5 dB over, z 8.4)
  - under it: kit pitch 36 vel 0.685, event is +206 ms from that note's onset (written 0.45 beats)
- **47.337s** single source: kit 99%; step 0.0749 vs threshold 0.0566 (+2.4 dB over, z 10.6)
  - under it: kit pitch 54 vel 0.674, event is +87 ms from that note's onset (written 0.25 beats)
- **54.422s** single source: kit 100%; step 0.0595 vs threshold 0.0566 (+0.4 dB over, z 8.4)
  - under it: kit pitch 54 vel 0.649, event is +172 ms from that note's onset (written 0.25 beats)
- **56.145s** single source: kit 100%; step 0.0595 vs threshold 0.0566 (+0.4 dB over, z 8.4)
  - under it: kit pitch 36 vel 0.864, event is +145 ms from that note's onset (written 0.45 beats)
- **60.026s** single source: kit 91%; step 0.0615 vs threshold 0.0566 (+0.7 dB over, z 8.7)
  - under it: kit pitch 36 vel 0.864, event is +26 ms from that note's onset (written 0.45 beats)
- **62.067s** single source: kit 98%; step 0.0597 vs threshold 0.0566 (+0.5 dB over, z 8.4)
  - under it: kit pitch 36 vel 0.864, event is +67 ms from that note's onset (written 0.45 beats)

## Domains
ran: master, stems
advisory, never binding: 32 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.kit` +3.00 dB kit high shelf at 5500 Hz: inst_eq["kit"]

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  clicks::-: -9.00 -> -8.67
  clipping::-: +0.00    +0.00
  stem.clipping::kit: +0.00    +0.00
  stem.clicks::kit: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.kit -9 dB: 9 -> 0 (clears, 3 dB clear of the threshold)
- hf.kit -9 dB: 9 -> 0 (clears, 3 dB clear of the threshold)
- hf.kit -12 dB: 9 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -6 dB: 9 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -3 dB: 9 -> 1 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Prediction record: 2 settled, 2 held, 0 did not

## Conflicts (no value satisfies both)
- `hf.kit` (kit high shelf at 5500 Hz: inst_eq["kit"]): kit high shelf at 5500 Hz: inst_eq["kit"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +81.00 .. +3.00 dB within bounds -12.00 .. +3.00
  - clicks needs +81.00 (safety now -9.00)

## Already tried (not proposed again)
- `onset.kit.ms` (kit onset ramp) for clicks
- `onset.kit.all` (kit ramp every onset) for clicks

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 9 vs gate 8; missing at [], extra at [64.734]): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 1.0 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.95); gains bansuri -0.06, bass 0.63, canopy 5.72, djembe 1.32, guitar 1.94, horns 1.39, kit 1.19, marimba -0.17, shekere 1.31, sitar 0.06, tabla 1.56, tanpura -0.06, vocal_group 2.84, vocal_lead 3.42'
- 'event 18.497s [single source] kit 84%; step 0.0661 vs threshold 0.0566 (+1.4 dB over); nearest onset kit p54 v0.519 -3 ms'
- 'event 24.369s [single source] kit 99%; step 0.0589 vs threshold 0.0566 (+0.3 dB over)'
- 'event 30.706s [single source] kit 100%; step 0.0597 vs threshold 0.0566 (+0.5 dB over); nearest onset kit p36 v0.685 +206 ms'
- 'event 47.337s [single source] kit 99%; step 0.0749 vs threshold 0.0566 (+2.4 dB over); nearest onset kit p54 v0.674 +87 ms'
- 'event 54.422s [single source] kit 100%; step 0.0595 vs threshold 0.0566 (+0.4 dB over); nearest onset kit p54 v0.649 +172 ms'
- 'event 56.145s [single source] kit 100%; step 0.0595 vs threshold 0.0566 (+0.4 dB over); nearest onset kit p36 v0.864 +145 ms'
- 'event 60.026s [single source] kit 91%; step 0.0615 vs threshold 0.0566 (+0.7 dB over); nearest onset kit p36 v0.864 +26 ms'
- 'event 62.067s [single source] kit 98%; step 0.0597 vs threshold 0.0566 (+0.5 dB over); nearest onset kit p36 v0.864 +67 ms'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (9, 9, 9, 10) -> (0, 0, 0, 0) after kit -9 dB'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to kit, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -8.67. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
- the best candidate comes from a model that failed its sham test, so it is not adopted as a plan
