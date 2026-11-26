# Debug autopsy - night_pursuit_cinematic

20261126T112036  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/night_pursuit_cinematic/scores/night_pursuit_cinematic_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=30 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T11:20:13Z

## In question (3)
- **dropout**: 30.000000000001137 ms against 20.0 -> FAILS by 0.50 tolerance units
  - longest hole 30 ms (limit 20-1000 ms), floor -65.6 dBFS; 1 hole(s)
  - transient attributed to city_far 46%, basses 35%, bumps 11%
- **tempo.audio**: 58.35398486181295 BPM against 2.64 -> FAILS by 55.71 tolerance units
  - measured 73.6 BPM vs 132.0 (tolerance 2.6) from the onset-envelope autocorrelation (peak 4.3x the median); beat tracker said 73.8; four-quarter drift 23.7 BPM reported, not decisive
- **section.energy**: 0.34731161595484505 rho against 0.5 -> passes with 0.76 units of room
  - Spearman rho 0.35 between promised energy and measured section level (FAIL < 0.5, WARN < 0.7)

## Domains
ran: master
not run (nothing in question): stems (112 rows)
advisory, never binding: 112 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  dropout::-: -0.50    -0.50
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
- 'dropout has 1 event(s) at 192.325s; the transient is city_far 46%, basses 35%, bumps 11%'
- 'tempo.audio: no domain module examines this row yet'
- 'section.energy: no domain module examines this row yet'

