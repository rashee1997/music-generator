# Debug autopsy - indo_afro_sunrise

20261125T053934  ·  level FAIL  ·  plan nothing to move
sources: score=/workspace/chats/c7f800ed356753289887290c/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-25T05:31:15Z

## In question (1)
- **clicks**: 23.0 events against 0.0 -> FAILS by 23.00 tolerance units
  - 23 clustered impulse event(s) (MAD), 23 LPC frame(s); 1398 event(s) rejected as a dense burst, 250 as a steep attack; max cluster span 1.497 ms
  - transient attributed to kit 61%, djembe 12%, shekere 11%

## Domains
ran: master, stems
advisory, never binding: 32 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -23.00    -23.00
  clipping::-: +0.00    +0.00
  stem.clipping::kit: +0.00    +0.00
  stem.clicks::kit: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
clicks - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Already tried (not proposed again)
- `onset.kit.ms` (kit onset ramp) for clicks
- `onset.kit.all` (kit ramp every onset) for clicks

## Measurements behind this
- 'clicks has 8 event(s) at 11.778s, 12.346s, 13.908s, 14.454s; the transient is kit 61%, djembe 12%, shekere 11%'
- 'kit: the tightest gap in the score is 16 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'kit: the tightest gap in the score is 16 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to kit, so every row of those stems was loaded as a constraint before the plan was solved'

