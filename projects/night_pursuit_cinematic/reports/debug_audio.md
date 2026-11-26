# Debug autopsy - night_pursuit_cinematic

20261126T121458  ·  level FAIL  ·  plan replay-proved
sources: score=/home/user/music-generator/projects/night_pursuit_cinematic/scores/night_pursuit_cinematic_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=30 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T12:13:59Z

## In question (2)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 1 LPC frame(s); 2170 event(s) rejected as a dense burst, 225 as a steep attack; max cluster span 1.497 ms
  - transient attributed to snare 100%
- **dropout**: 104.99999999998977 ms against 20.0 -> FAILS by 4.25 tolerance units
  - longest hole 105 ms (limit 20-1000 ms), floor -65.3 dBFS; 2 hole(s)
  - transient attributed to city_far 51%, basses 23%, bumps 15%

## Forensics (signal level)
- **162.002s** single source: snare 96%; step 0.0220 vs threshold 0.0200 (+0.8 dB over, z 32.9)

## Domains
ran: master, stems
advisory, never binding: 112 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.snare` -12.00 dB snare high shelf at 5500 Hz: inst_eq["pursuit_snare"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.snare` -9.00 dB snare high shelf at 5500 Hz: inst_eq["pursuit_snare"]

  dropout::-: -4.25    -4.25
  clicks::-: -1.00 -> -2.33
  clipping::-: +0.00    +0.00
  stem.clipping::snare: +0.00    +0.00
  stem.clicks::snare: +0.00    +0.00
  true peak::-: +0.00    +0.00

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.snare -9 dB: 1 -> 0 (clears, 3 dB clear of the threshold)
- hf.snare -12 dB: 1 -> 0 (clears, 3 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
- `hf.snare` (snare high shelf at 5500 Hz: inst_eq["pursuit_snare"]): snare high shelf at 5500 Hz: inst_eq["pursuit_snare"] cannot satisfy clicks at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval +9.00 .. +0.00 dB within bounds -12.00 .. +0.00
  - clicks needs +9.00 (safety now -1.00)

## Closed rows
dropout - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 1 event(s) exactly (decomposition R^2 0.876); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 1.7 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.88); gains bass_clarinet 1.94, bass_drum 1.53, basses 2.69, bumps 0.40, celli 1.76, choir 0.77, city_far 6.19, crash 0.14, cymbals 1.14, ferrari 0.97, horns 1.28, landing 0.67, piano 1.97, piano_low 2.90, snare 1.42, solo_violin 1.57, sub_drop 3.02, sub_pulse 2.49, taiko 1.16, timpani 1.24, trombones 1.26, tuba 2.44, violins_staccato 1.29, violins_tremolo 0.99'
- 'event 162.002s [single source] snare 96%; step 0.0220 vs threshold 0.0200 (+0.8 dB over)'
- 'dropout has 2 event(s) at 192.210s, 192.255s; the transient is city_far 51%, basses 23%, bumps 15%'
- 'snare: the tightest gap in the score is 114 ms at beat spacing 0.455 s (132 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'snare: the tightest gap in the score is 114 ms at beat spacing 0.455 s (132 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to snare, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears clicks, dropout; the best set leaves it at safety -4.25. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
- clearing set read from a replay through the gate's own checker, not from the linear model; the next render is the measurement
