# Debug autopsy - quiet_frequency_trailer

20261128T152358  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/quiet_frequency_trailer/scores/quiet_frequency_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'realism.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=30 processed stems from .cache/mix, master=out/_draft_quiet_frequency_trailer.wav, verdict=2026-11-28T15:04:52Z

## In question (1)
- **dropout**: 69.99999999999318 ms against 20.0 -> FAILS by 2.50 tolerance units
  - longest hole 70 ms (limit 20-1000 ms), floor -64.6 dBFS; 1 hole(s)
  - transient attributed to violins_long 63%, sfx_impacts 31%, sfx_boom 5%

## Domains
ran: master
not run (nothing in question): stems (118 rows)
advisory, never binding: 118 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  dropout::-: -2.50    -2.50
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
- 'dropout has 1 event(s) at 120.300s; the transient is violins_long 63%, sfx_impacts 31%, sfx_boom 5%'

