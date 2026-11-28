# Debug autopsy - indo_afro_sunrise

20261128T064033  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/home/user/music-generator/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=14 processed stems from .cache/mix, master=out/_draft_indo_afro_sunrise.wav, verdict=2026-11-28T06:32:58Z

## In question (1)
- **clicks**: 21.0 events against 0.0 -> FAILS by 21.00 tolerance units
  - 21 clustered impulse event(s) (MAD), 17 LPC frame(s); 782 event(s) rejected as a dense burst, 185 as a steep attack; max cluster span 1.497 ms
  - transient attributed to kit 100%

## Forensics (signal level)
- **13.401s** single source: kit 98%; step 0.0530 vs threshold 0.0518 (+0.2 dB over, z 8.2)
- **13.910s** single source: kit 99%; step 0.0535 vs threshold 0.0518 (+0.3 dB over, z 8.3)
- **17.416s** single source: kit 90%; step 0.0580 vs threshold 0.0518 (+1.0 dB over, z 9.0)
- **18.231s** single source: kit 76%; step 0.0657 vs threshold 0.0518 (+2.1 dB over, z 10.1)
  - under it: kit pitch 36 vel 0.685, event is +231 ms from that note's onset (written 0.45 beats)
- **19.150s** single source: kit 99%; step 0.0548 vs threshold 0.0518 (+0.5 dB over, z 8.5)
  - under it: kit pitch 54 vel 0.583, event is +128 ms from that note's onset (written 0.25 beats)
- **19.824s** single source: kit 93%; step 0.0633 vs threshold 0.0518 (+1.7 dB over, z 9.8)
- **23.465s** single source: kit 94%; step 0.0524 vs threshold 0.0518 (+0.1 dB over, z 8.1)
- **30.597s** single source: kit 84%; step 0.0554 vs threshold 0.0518 (+0.6 dB over, z 8.5)
  - under it: kit pitch 36 vel 0.685, event is +97 ms from that note's onset (written 0.45 beats)

## Domains
ran: master, stems
advisory, never binding: 32 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.kit` +3.00 dB kit high shelf at 5500 Hz: inst_eq["kit"]

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  clicks::-: -21.00 -> -20.33
  clipping::-: +0.00    +0.00
  stem.clipping::kit: +0.00    +0.00
  stem.clicks::kit: +0.00    +0.00
  loudness::-: +0.02    +0.02
  true peak::-: +0.02    +0.02

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.kit -12 dB: 21 -> 0 (clears, 2 dB clear of the threshold)
- hf.kit -12 dB: 21 -> 0 (clears, 2 dB clear of the threshold)
- hf.kit -9 dB: 21 -> 1 (better)
- hf.kit -3 dB: 21 -> 2 (better)
- hf.kit -6 dB: 21 -> 2 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Prediction record: 2 settled, 2 held, 0 did not

## Conflicts (no value satisfies both)
- `hf.kit` (kit high shelf at 5500 Hz: inst_eq["kit"]): kit high shelf at 5500 Hz: inst_eq["kit"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +94.50 .. +3.00 dB within bounds -12.00 .. +3.00
  - clicks needs +94.50 (safety now -21.00)

## Already tried (not proposed again)
- `onset.kit.ms` (kit onset ramp) for clicks
- `onset.kit.all` (kit ramp every onset) for clicks

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 21 vs gate 8; missing at [], extra at [31.247, 31.641, 32.58]): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 1.0 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.95); gains bansuri -0.06, bass 0.64, canopy 5.69, djembe 1.32, guitar 1.93, horns 1.39, kit 1.18, marimba -0.19, shekere 1.30, sitar 0.09, tabla 1.55, tanpura -0.28, vocal_group 2.93, vocal_lead 3.37'
- 'event 13.401s [single source] kit 98%; step 0.0530 vs threshold 0.0518 (+0.2 dB over)'
- 'event 13.910s [single source] kit 99%; step 0.0535 vs threshold 0.0518 (+0.3 dB over)'
- 'event 17.416s [single source] kit 90%; step 0.0580 vs threshold 0.0518 (+1.0 dB over)'
- 'event 18.231s [single source] kit 76%; step 0.0657 vs threshold 0.0518 (+2.1 dB over); nearest onset kit p36 v0.685 +231 ms'
- 'event 19.150s [single source] kit 99%; step 0.0548 vs threshold 0.0518 (+0.5 dB over); nearest onset kit p54 v0.583 +128 ms'
- 'event 19.824s [single source] kit 93%; step 0.0633 vs threshold 0.0518 (+1.7 dB over)'
- 'event 23.465s [single source] kit 94%; step 0.0524 vs threshold 0.0518 (+0.1 dB over)'
- 'event 30.597s [single source] kit 84%; step 0.0554 vs threshold 0.0518 (+0.6 dB over); nearest onset kit p36 v0.685 +97 ms'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (21, 22, 15, 11) -> (0, 0, 0, 2) after kit -12 dB'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'kit: the tightest gap in the score is 122 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to kit, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -20.33. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
- the best candidate comes from a model that failed its sham test, so it is not adopted as a plan
