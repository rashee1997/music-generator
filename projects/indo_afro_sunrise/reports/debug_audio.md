# Debug autopsy - indo_afro_sunrise

20261125T052355  ·  level FAIL  ·  plan nothing to move
sources: score=/workspace/chats/c7f800ed356753289887290c/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-25T05:20:15Z

## In question (1)
- **clicks**: 3.0 events against 0.0 -> FAILS by 3.00 tolerance units
  - 3 clustered impulse event(s) (MAD), 3 LPC frame(s); 1376 event(s) rejected as a dense burst, 255 as a steep attack; max cluster span 1.497 ms
  - transient attributed to shekere 33%, kit 22%, guitar 22%

## Domains
ran: master
not run (nothing in question): stems (32 rows)
advisory, never binding: 32 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -3.00    -3.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
clicks - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- 'clicks has 3 event(s) at 12.346s, 22.276s, 55.240s; the transient is shekere 33%, kit 22%, guitar 22%'

