# Debug autopsy - highway_pursuit

20261127T151822  ·  level FAIL  ·  plan nothing to move
sources: score=/workspace/chats/0ae6b42243a7a3f4cbccb523/projects/highway_pursuit/scores/highway_pursuit_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=18 processed stems from .cache/mix, master=out/_draft_highway_pursuit.wav, verdict=2026-11-27T14:53:49Z

## In question (1)
- **dropout**: 425.00000000000426 ms against 20.0 -> FAILS by 20.25 tolerance units
  - longest hole 425 ms (limit 20-1000 ms), floor -63.0 dBFS; 5 hole(s)
  - transient attributed to taiko 65%, bass_drum 34%, basses_pizz 1%

## Domains
ran: master
not run (nothing in question): stems (40 rows)
advisory, never binding: 40 row(s) - stem.cut, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  dropout::-: -20.25    -20.25
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
- 'dropout has 5 event(s) at 54.235s, 54.295s, 54.380s, 54.420s; the transient is taiko 65%, bass_drum 34%, basses_pizz 1%'

