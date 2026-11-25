# Debug autopsy - indo_afro_sunrise

20261125T033740  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/workspace/chats/c7f800ed356753289887290c/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-25T03:34:16Z

## In question (1)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 1 LPC frame(s); 1355 event(s) rejected as a dense burst, 258 as a steep attack; max cluster span 1.497 ms
  - transient attributed to kit 86%, bansuri 9%, sitar 3%

## Domains
ran: master
not run (nothing in question): stems (24 rows)
advisory, never binding: 24 row(s) - stem.cut, stem.edge, stem.tick

## Proposed (first-order prediction)
- `onset.kit.ms` +1.00 ms kit onset ramp

  clicks::-: -1.00 -> -0.14
  loudness::-: -0.11    -0.11
  true peak::-: -0.00    -0.00
  clipping::-: +0.00    +0.00
  master.dc::-: +0.10    +0.10

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- clicks has 1 event(s) at 46.646s; the transient is kit 86%, bansuri 9%, sitar 3%

## Solver
- no admissible combination clears clicks; the best set leaves it at safety -0.14. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
