# Debug autopsy - highway_pursuit

20261127T165628  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/highway_pursuit/scores/highway_pursuit_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=18 processed stems from .cache/mix, master=out/_draft_highway_pursuit.wav, verdict=2026-11-27T16:51:23Z

## In question (1)
- **dropout**: 165.00000000000625 ms against 20.0 -> FAILS by 7.25 tolerance units
  - longest hole 165 ms (limit 20-1000 ms), floor -63.2 dBFS; 2 hole(s)
  - transient attributed to taiko 85%, bass_drum 15%, timpani 0%

## Domains
ran: master
not run (nothing in question): stems (40 rows)
advisory, never binding: 40 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  dropout::-: -7.25    -7.25
  clicks::-: +0.00    +0.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
dropout - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- 'dropout has 2 event(s) at 54.390s, 54.440s; the transient is taiko 85%, bass_drum 15%, timpani 0%'

