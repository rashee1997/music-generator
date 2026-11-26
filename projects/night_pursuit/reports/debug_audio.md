# Debug autopsy - night_pursuit

20261126T091325  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T08:53:13Z

## In question (1)
- **clicks**: 6.0 events against 0.0 -> FAILS by 6.00 tolerance units
  - 6 clustered impulse event(s) (MAD), 6 LPC frame(s); 722 event(s) rejected as a dense burst, 630 as a steep attack; max cluster span 1.497 ms
  - transient attributed to rain_street/drops 69%, engine 17%, snare 14%

## Forensics (signal level)
- **104.180s** single source: snare 77%; step 0.0207 vs threshold 0.0200 (+0.3 dB over, z 8.7)
- **146.787s** single source: engine 90%; step 0.0207 vs threshold 0.0200 (+0.3 dB over, z 8.7)
  - under it: engine is a continuous bed with no onset, so the step is in its texture, not on a note
- **155.705s** single source: rain_street/drops 94%; step 0.0219 vs threshold 0.0200 (+0.8 dB over, z 9.2)
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
- **156.904s** single source: rain_street/drops 98%; step 0.0281 vs threshold 0.0200 (+3.0 dB over, z 11.8)
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
- **157.832s** single source: rain_street/drops 90%; step 0.0238 vs threshold 0.0200 (+1.5 dB over, z 10.0)
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note
- **164.427s** single source: rain_street/drops 92%; step 0.0261 vs threshold 0.0200 (+2.3 dB over, z 10.9)
  - under it: rain_street is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master, stems
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.engine` +9.00 dB engine high shelf at 5500 Hz: inst_eq["sfx:np_engine"]
- `hf.snare` +3.00 dB snare high shelf at 5500 Hz: inst_eq["pursuit_snare"]

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  clicks::-: -6.00 -> -4.67
  clipping::-: +0.00    +0.00
  stem.clipping::engine: +0.00    +0.00
  stem.clicks::engine: +0.00    +0.00
  stem.clipping::snare: +0.00    +0.00
  stem.clicks::snare: +0.00    +0.00

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- layer.rain_street.drops -6 dB, hf.engine -6 dB: 6 -> 2 (better)
- layer.rain_street.drops -6 dB, hf.engine -6 dB: 6 -> 2 (better)
- layer.rain_street.drops -6 dB, hf.engine -9 dB: 6 -> 2 (better)
- layer.rain_street.drops -6 dB, hf.engine -3 dB: 6 -> 3 (better)
- layer.rain_street.drops -9 dB, hf.engine -3 dB: 6 -> 3 (better)
- layer.rain_street.drops -9 dB, hf.engine -6 dB: 6 -> 3 (better)
- layer.rain_street.drops -9 dB, hf.engine -9 dB: 6 -> 3 (better)
- layer.rain_street.drops -6 dB: 6 -> 4 (better)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.snare` (snare high shelf at 5500 Hz: inst_eq["pursuit_snare"]): snare high shelf at 5500 Hz: inst_eq["pursuit_snare"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +54.00 .. +3.00 dB within bounds -12.00 .. +3.00
  - clicks needs +54.00 (safety now -6.00)
- `hf.engine` (engine high shelf at 5500 Hz: inst_eq["sfx:np_engine"]): engine high shelf at 5500 Hz: inst_eq["sfx:np_engine"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +54.00 .. +9.00 dB within bounds -12.00 .. +9.00
  - clicks needs +54.00 (safety now -6.00)

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 6 event(s) exactly (decomposition R^2 0.962); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.5 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.96); gains bass_clarinet 1.30, bass_drum 0.99, basses 1.82, celli 1.14, city_far 4.17, crash 0.19, cymbals 0.72, engine 2.69, horns 0.84, piano 1.15, piano_low 1.80, rain_street 4.28, snare 0.92, sub_drop 2.50, timpani 0.80, trombones 0.78, tuba 1.39, tyres 1.41, violins_staccato 0.85, violins_tremolo 0.69, wipers 2.28'
- 'event 104.180s [single source] snare 77%; step 0.0207 vs threshold 0.0200 (+0.3 dB over)'
- 'event 146.787s [single source] engine 90%; step 0.0207 vs threshold 0.0200 (+0.3 dB over); nearest onset engine pNone vNone +0 ms'
- 'event 155.705s [single source] rain_street/drops 94%; step 0.0219 vs threshold 0.0200 (+0.8 dB over); nearest onset rain_street pNone vNone +0 ms'
- 'event 156.904s [single source] rain_street/drops 98%; step 0.0281 vs threshold 0.0200 (+3.0 dB over); nearest onset rain_street pNone vNone +0 ms'
- 'event 157.832s [single source] rain_street/drops 90%; step 0.0238 vs threshold 0.0200 (+1.5 dB over); nearest onset rain_street pNone vNone +0 ms'
- 'event 164.427s [single source] rain_street/drops 92%; step 0.0261 vs threshold 0.0200 (+2.3 dB over); nearest onset rain_street pNone vNone +0 ms'
- 'clicks: cutting the band of rain_street/drops is NOT monotone (replay: -6 dB -> 4 event(s), -3 dB -> 5 event(s), -9 dB -> 5 event(s), -12 dB -> 5 event(s) against 6 now): its highs set the floor the threshold is taken against, so the lever is priced at zero and the cut belongs on the part that makes the transient'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (6, 8, 6, 5) -> (2, 3, 0, 0) after rain_street/drops -6 dB, engine -6 dB'
- 'snare: the tightest gap in the score is 117 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'snare: the tightest gap in the score is 117 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to engine, snare, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -4.67. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
