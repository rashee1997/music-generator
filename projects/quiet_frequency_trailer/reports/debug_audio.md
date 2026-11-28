# Debug autopsy - quiet_frequency_trailer

20261128T092037  ·  level WARN  ·  plan no rows
sources: score=/home/user/music-generator/projects/quiet_frequency_trailer/scores/quiet_frequency_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=28 processed stems from .cache/mix, master=out/_draft_quiet_frequency_trailer.wav, verdict=2026-11-28T09:03:02Z

## In question (1)
- **section.energy**: 0.5757575757575757 rho against 0.5 -> FAILS by 0.38 tolerance units
  - Spearman rho 0.58 between promised energy and measured section level (FAIL < 0.5, WARN < 0.7)

## Domains
ran: none
not run (nothing in question): stems (106 rows)
advisory, never binding: 106 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- 'section.energy: no domain module examines this row yet'

