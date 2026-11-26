# Debug autopsy - night_pursuit

20261126T063022  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['stem_gate.json']

## In question (5)
- **stem.clipping** on engine: 62.0 samples against 0.0 -> FAILS by 62.00 tolerance units
  - stem "engine": 62 sample(s) at/above 0.999 FS, 2 flat-top run(s)
- **stem.dropout** on engine: 20.000000000010232 ms against 20.0 -> FAILS by 0.00 tolerance units
  - stem "engine": longest hole 20 ms (limit 20-1000 ms), floor -61.1 dBFS; 1 hole(s)
- **stem.dead** on siren_second: 25.54027901871507 dB against 12.0 -> passes with 2.26 units of room
  - stem "siren_second": own median -95.5 dBFS, worst section shortfall 25.5 dB (limit 12 dB), active sections 1; all sections silent
- **stem.tick** on violins_tremolo: 0.633972086306416 rho against 0.35 -> FAILS by 1.42 tolerance units
  - stem "violins_tremolo": onset autocorrelation 0.63 at a 93 ms grid (limit 0.35; onset frames are 11.6 ms apart, so the reported grid can be a multiple of the tick spacing), 16 strong onset(s) of 452, 10 on the grid, IOI CV 1.883; peak rise 7.43 dB at those onsets over 15 onset(s) (min 3); tempogram peak ratio 1.00, PLP peak ratio 1.00
- **stem.dead** on wipers: 27.563631353224935 dB against 12.0 -> passes with 2.59 units of room
  - stem "wipers": own median -97.6 dBFS, worst section shortfall 27.6 dB (limit 12 dB), active sections 1; all sections silent

## Domains
ran: stems
advisory, never binding: 37 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `note.engine.d` -0.06 beats engine written note length (mean 376 beats)

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  stem.clipping::engine: -62.00    -62.00
  stem.dropout::engine: -0.00 -> -1.46
  stem.tick::violins_tremolo: -1.42    -1.42
  stem.clipping::bass_clarinet: +0.00    +0.00
  stem.clicks::bass_clarinet: +0.00    +0.00
  stem.clipping::bass_drum: +0.00    +0.00

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
stem.clipping, stem.dead, stem.tick - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- 'celli: the tightest gap in the score is 23 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'horns: the tightest gap in the score is 1875 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'piano: the tightest gap in the score is 14 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'piano_low: the tightest gap in the score is 94 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'sub_drop: the tightest gap in the score is 5625 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'trombones: the tightest gap in the score is 47 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'tuba: the tightest gap in the score is 234 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'violins_staccato: the tightest gap in the score is 23 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'violins_tremolo: the tightest gap in the score is 47 ms at beat spacing 0.469 s (128 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to bass_clarinet, basses, celli, city_far, crash, engine, horns, piano, piano_low, rain_awnings, rain_street, siren_first, siren_second, sub_drop, trombones, tuba, tyres, violins_staccato, violins_tremolo, wipers, so every row of those stems was loaded as a constraint before the plan was solved'

## Solver
- no admissible combination clears stem.clipping, stem.dropout, stem.tick; the best set leaves it at safety -62.00. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
