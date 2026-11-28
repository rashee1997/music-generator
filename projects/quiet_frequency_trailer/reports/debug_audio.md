# Debug autopsy - quiet_frequency_trailer

20261128T084614  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/quiet_frequency_trailer/scores/quiet_frequency_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=28 processed stems from .cache/mix, master=out/_draft_quiet_frequency_trailer.wav, verdict=2026-11-28T08:28:43Z

## In question (1)
- **dropout**: 39.99999999999204 ms against 20.0 -> FAILS by 1.00 tolerance units
  - longest hole 40 ms (limit 20-1000 ms), floor -64.6 dBFS; 1 hole(s)
  - transient attributed to violins_long 67%, sfx_impacts 33%, timpani 0%

## Domains
ran: master
not run (nothing in question): stems (106 rows)
advisory, never binding: 106 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  dropout::-: -1.00    -1.00
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
- 'dropout has 1 event(s) at 120.310s; the transient is violins_long 67%, sfx_impacts 33%, timpani 0%'

