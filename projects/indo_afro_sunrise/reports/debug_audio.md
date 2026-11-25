# Debug autopsy - indo_afro_sunrise

20261125T034612  ·  level FAIL  ·  plan best admissible set (row not cleared)
sources: score=/workspace/chats/c7f800ed356753289887290c/projects/indo_afro_sunrise/scores/indo_afro_sunrise_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], master=out/_draft_master.wav, verdict=2026-11-25T03:39:15Z

## In question (2)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 1 LPC frame(s); 1355 event(s) rejected as a dense burst, 258 as a steep attack; max cluster span 1.497 ms
- **stem.dropout** on kit: 25.000000000005684 ms against 20.0 -> FAILS by 0.25 tolerance units
  - stem "kit": longest hole 25 ms (limit 20-1000 ms), floor -98.8 dBFS; 3 hole(s)

## Domains
ran: master, stems
advisory, never binding: 24 row(s) - stem.cut, stem.edge, stem.tick

## Proposed (first-order prediction)
- `onset.kit.ms` -0.30 ms kit onset ramp
- `note.kit.d` -0.03 beats kit written note length (mean 0.3047 beats)

**no admissible value clears the failing row**: the levers this project declares cannot reach it, so the change belongs in the score, the sample or the density

  stem.dropout::kit: -0.25 -> -1.07
  clicks::-: -1.00    -1.00
  clipping::-: +0.00    +0.00
  stem.clipping::bansuri: +0.00    +0.00
  stem.clicks::bansuri: +0.00    +0.00
  stem.clipping::bass: +0.00    +0.00

## Conflicts (no value satisfies both)
- `onset.kit.ms` (kit onset ramp): kit onset ramp cannot satisfy stem.dropout at once: the moves that pass one row fail the other, and the bounds leave no value between
  - feasible move interval -0.30 .. -5.00 ms within bounds -0.30 .. +2.70
  - stem.dropout needs -5.00 (safety now -0.25)

## Closed rows
clicks - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- {'t': 0.0, 'd': 70.0, 'p': 60, 'v': 0.5}
- 'clicks: no processed stems and no written onset at that instant, so the impulse could not be attributed'
- 'kit: the tightest gap in the score is 0 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'bansuri: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'bass: the tightest gap in the score is 500 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'djembe: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'guitar: the tightest gap in the score is 20 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'horns: the tightest gap in the score is 15 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'kit: the tightest gap in the score is 0 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'marimba: the tightest gap in the score is 500 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'shekere: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'sitar: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'tabla: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'tanpura: the tightest gap in the score is 0 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'bansuri: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'bass: the tightest gap in the score is 500 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'djembe: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'guitar: the tightest gap in the score is 20 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'horns: the tightest gap in the score is 15 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'marimba: the tightest gap in the score is 500 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'shekere: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'sitar: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'tabla: the tightest gap in the score is 250 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'
- 'tanpura: the tightest gap in the score is 0 ms at beat spacing 0.536 s (112 bpm sixteenths); the note lengths and the ramp share this number, so they cannot be moved independently'

## Solver
- no admissible combination clears clicks, stem.dropout; the best set leaves it at safety -1.07. The rows that limit it have no lever here - fix those first, or change the piece rather than the knob
