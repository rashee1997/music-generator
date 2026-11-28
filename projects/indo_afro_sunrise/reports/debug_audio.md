# Debug autopsy - indo_afro_sunrise

20261127T105348  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/workspace/chats/0ae6b42243a7a3f4cbccb523/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_indo_afro_sunrise.wav, verdict=2026-11-27T10:30:26Z

## In question (1)
- **clicks**: 15.0 events against 0.0 -> FAILS by 15.00 tolerance units
  - 15 clustered impulse event(s) (MAD), 13 LPC frame(s); 745 event(s) rejected as a dense burst, 141 as a steep attack; max cluster span 1.497 ms
  - transient attributed to kit 96%, guitar 4%

## Forensics (signal level)
- **8.549s** single source: kit 84%; step 0.0780 vs threshold 0.0698 (+1.0 dB over, z 8.9)
- **18.497s** single source: kit 79%; step 0.0730 vs threshold 0.0698 (+0.4 dB over, z 8.4)
  - under it: kit pitch 54 vel 0.519, event is -3 ms from that note's onset (written 0.25 beats)
- **18.625s** single source: kit 98%; step 0.0703 vs threshold 0.0698 (+0.1 dB over, z 8.1)
  - under it: kit pitch 54 vel 0.519, event is +125 ms from that note's onset (written 0.25 beats)
- **19.012s** single source: kit 94%; step 0.0750 vs threshold 0.0698 (+0.6 dB over, z 8.6)
  - under it: kit pitch 54 vel 0.583, event is -10 ms from that note's onset (written 0.25 beats)
- **20.086s** single source: kit 75%, guitar 24%; step 0.0782 vs threshold 0.0698 (+1.0 dB over, z 9.0)
  - under it: kit pitch 36 vel 0.685, event is +86 ms from that note's onset (written 0.45 beats)
- **35.527s** single source: kit 80%; step 0.0755 vs threshold 0.0698 (+0.7 dB over, z 8.6)
  - under it: kit pitch 54 vel 0.68, event is +27 ms from that note's onset (written 0.25 beats)
- **36.583s** single source: kit 77%; step 0.0744 vs threshold 0.0698 (+0.6 dB over, z 8.5)
  - under it: kit pitch 54 vel 0.612, event is +82 ms from that note's onset (written 0.25 beats)
- **36.872s** single source: kit 98%; step 0.0764 vs threshold 0.0698 (+0.8 dB over, z 8.8)
  - under it: kit pitch 54 vel 0.617, event is +122 ms from that note's onset (written 0.25 beats)

## Domains
ran: master, stems
advisory, never binding: 56 row(s) - stem.cut, stem.dropout, stem.edge, stem.flatness, stem.tick

## Proposed (first-order prediction)
- `hf.kit` +3.00 dB kit high shelf at 5500 Hz: inst_eq["kit"]

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  clicks::-: -15.00 -> -13.33
  clipping::-: +0.00    +0.00
  stem.clipping::kit: +0.00    +0.00
  stem.clicks::kit: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.kit -9 dB, hf.shekere -6 dB: 15 -> 0 (clears, 1 dB clear of the threshold)
- hf.kit -12 dB: 15 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -9 dB, hf.guitar -3 dB: 15 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -9 dB, hf.guitar -6 dB: 15 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -9 dB, hf.guitar -9 dB: 15 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -6 dB, hf.guitar -6 dB: 15 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -6 dB, hf.guitar -3 dB: 15 -> 0 (clears, 0 dB clear of the threshold)
- hf.kit -6 dB, hf.guitar -9 dB: 15 -> 0 (clears, 0 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Prediction record: 2 settled, 2 held, 0 did not

## Conflicts (no value satisfies both)
- `hf.kit` (kit high shelf at 5500 Hz: inst_eq["kit"]): kit high shelf at 5500 Hz: inst_eq["kit"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +27.00 .. +3.00 dB within bounds -12.00 .. +3.00
  - clicks needs +27.00 (safety now -15.00)

## Already tried (not proposed again)
- `onset.kit.ms` (kit onset ramp) for clicks
- `onset.kit.all` (kit ramp every onset) for clicks

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 15 vs gate 8; missing at [], extra at [42.388, 44.11, 44.367]): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 1.7 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.94); gains bansuri 3.01, bass 2.06, canopy 6.56, djembe 1.46, guitar 2.12, horns 1.32, kit 1.34, marimba 0.16, shekere 1.46, tabla 1.68, tanpura 2.40'
- 'event 8.549s [single source] kit 84%; step 0.0780 vs threshold 0.0698 (+1.0 dB over)'
- 'event 18.497s [single source] kit 79%; step 0.0730 vs threshold 0.0698 (+0.4 dB over); nearest onset kit p54 v0.519 -3 ms'
- 'event 18.625s [single source] kit 98%; step 0.0703 vs threshold 0.0698 (+0.1 dB over); nearest onset kit p54 v0.519 +125 ms'
- 'event 19.012s [single source] kit 94%; step 0.0750 vs threshold 0.0698 (+0.6 dB over); nearest onset kit p54 v0.583 -10 ms'
- 'event 20.086s [single source] kit 75%, guitar 24%; step 0.0782 vs threshold 0.0698 (+1.0 dB over); nearest onset kit p36 v0.685 +86 ms'
- 'event 35.527s [single source] kit 80%; step 0.0755 vs threshold 0.0698 (+0.7 dB over); nearest onset kit p54 v0.68 +27 ms'
- 'event 36.583s [single source] kit 77%; step 0.0744 vs threshold 0.0698 (+0.6 dB over); nearest onset kit p54 v0.612 +82 ms'
- 'event 36.872s [single source] kit 98%; step 0.0764 vs threshold 0.0698 (+0.8 dB over); nearest onset kit p54 v0.617 +122 ms'
- 'clicks: cutting the band of guitar is NOT monotone (replay: -3 dB -> 12 event(s), -12 dB -> 15 event(s), -6 dB -> 18 event(s), -9 dB -> 18 event(s) against 15 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (15, 20, 18, 17) -> (0, 0, 1, 2) after kit -9 dB, shekere -6 dB'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to kit, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -13.33. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
- the best candidate comes from a model that failed its sham test, so it is not adopted as a plan
