# Debug autopsy - quiet_frequency_trailer

20261128T064910  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/quiet_frequency_trailer/scores/quiet_frequency_score.json, gate_data=['level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=28 processed stems from .cache/mix, master=out/_draft_quiet_frequency_trailer.wav, verdict=2026-11-28T06:07:22Z
re-measured on the master with the gate's own checkers: clicks

## In question (2)
- **clicks**: 0.0 events against 0.0 -> passes on the edge (0.00)
  - 0 clustered impulse event(s) (MAD), 0 LPC frame(s); 182 event(s) rejected as a dense burst, 28 as a steep attack; max cluster span 1.497 ms [re-measured: 0 clustered impulse event(s) (MAD), 0 LPC frame(s); 182 event(s) rejected as a dense burst, 28 as a steep attack; max cl]
- **tempo.audio**: 60.05964998605655 BPM against 2.4 -> FAILS by 57.66 tolerance units
  - measured 59.9 BPM vs 120.0 (tolerance 2.4) from the onset-envelope autocorrelation (peak 7.3x the median); beat tracker said 60.1; four-quarter drift 1.0 BPM reported, not decisive

## Domains
ran: master
not run (nothing in question): stems (106 rows)
advisory, never binding: 106 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: +0.00    +0.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Closed rows
clicks - no declared lever moves these; they need a score, preset or dataset change rather than a knob

## Measurements behind this
- 'tempo.audio: no domain module examines this row yet'

