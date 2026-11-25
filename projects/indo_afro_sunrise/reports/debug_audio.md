# Debug autopsy - indo_afro_sunrise

20261125T040334  ·  level FAIL  ·  plan nothing to move
sources: score=/workspace/chats/c7f800ed356753289887290c/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=12 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-25T04:00:49Z

## In question (1)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 1 LPC frame(s); 1355 event(s) rejected as a dense burst, 258 as a steep attack; max cluster span 1.497 ms
  - transient attributed to kit 86%, bansuri 9%, sitar 3%

## Domains
ran: master, stems
advisory, never binding: 24 row(s) - stem.cut, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -1.00    -1.00
  clipping::-: +0.00    +0.00
  stem.clipping::kit: +0.00    +0.00
  stem.clicks::kit: +0.00    +0.00
  loudness::-: +0.02    +0.02
  true peak::-: +0.02    +0.02

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
clicks - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Already tried (not proposed again)
- `onset.kit.ms` (kit onset ramp) for clicks, stem.dropout

## Measurements behind this
- 'clicks has 1 event(s) at 46.646s; the transient is kit 86%, bansuri 9%, sitar 3%'
- 'kit: the tightest gap in the score is 16 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'kit: the tightest gap in the score is 16 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'risk closure: the levers that move this row belong to kit, so every row of those stems was loaded as a constraint before the plan was solved'

