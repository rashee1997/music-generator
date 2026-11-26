# Debug autopsy - night_pursuit_cinematic

20261126T115034  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/night_pursuit_cinematic/scores/night_pursuit_cinematic_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=30 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T11:50:25Z

## In question (1)
- **dropout**: 104.99999999998977 ms against 20.0 -> FAILS by 4.25 tolerance units
  - longest hole 105 ms (limit 20-1000 ms), floor -65.3 dBFS; 2 hole(s)
  - transient attributed to city_far 51%, basses 23%, bumps 15%

## Domains
ran: master
not run (nothing in question): stems (112 rows)
advisory, never binding: 112 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  dropout::-: -4.25    -4.25
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
- 'dropout has 2 event(s) at 192.210s, 192.255s; the transient is city_far 51%, basses 23%, bumps 15%'

