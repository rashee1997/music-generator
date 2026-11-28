# Debug autopsy - highway_pursuit

20261127T221054  ·  level WARN  ·  plan no rows
sources: score=/home/user/music-generator/projects/highway_pursuit/scores/highway_pursuit_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=18 processed stems from .cache/mix, master=out/_draft_highway_pursuit.wav, verdict=2026-11-27T16:56:28Z

## In question (1)
- **section.energy**: 0.6666666666666669 rho against 0.5 -> FAILS by 0.83 tolerance units
  - Spearman rho 0.67 between promised energy and measured section level (FAIL < 0.5, WARN < 0.7)

## Domains
ran: none
not run (nothing in question): stems (40 rows)
advisory, never binding: 40 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- 'section.energy: no domain module examines this row yet'

