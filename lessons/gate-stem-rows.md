---
section: gate-stem-rows
title: Stem-stage rows that blocked a render
lessons:
- id: S01
  title: stem.dead on a part with many ghost notes
  keywords: [stem.dead, ghost note, pickup, median, quiet notes, snare, section shortfall, dropped in a section]
  rows: [stem.dead]
  symptom: a drum part is 12.1-12.9 dB under the energy curve in one section although it plays there
  cause: the row takes the median of each note's first 0.5 s; ghost notes, pickups and drags at vel 0.3-0.55 pull the median down
  check: print the part's per-section table (presets/gate/data/stem_gate.json, row stem.dead, table)
  fix: write ghosts, pickups and drags at the part's main tier (0.75-0.9 of the backbeat), and keep variety in position and pitch, not in loudness
  avoid: relaxing under_db for a part that is only quiet because of how it was written
  evidence: quiet_frequency_trailer snare, 2026-11-28
- id: S02
  title: sound effect read as silent or dead because it starts late or fades in
  keywords: [stem.dead, sfx, trigger note, first 0.5 s, fade in, all sections silent, tyres, road, device]
  rows: [stem.dead]
  symptom: '"own median -90 to -111 dBFS, all sections silent" for an sfx stem that is audible later'
  cause: for a trigger note the gate listens to the first 0.5 s after the onset; the preset began silent or faded in over more than 0.3 s
  fix: start the preset at its first audible sound and give it an attack of 0.15 s or less (begin() at the first event, not before it)
  avoid: padding a preset with a quiet lead-in
  evidence: tyres, road, device presets, 2026-11-28
- id: S03
  title: stem.dropout of 20-40 ms between notes of one part
  keywords: [stem.dropout, hole, 35 ms, bass, humanizer, articulation gate, bar line, legato, note length]
  rows: [stem.dropout]
  symptom: one or two holes of 25-40 ms in a bass or pad stem
  cause: the humanizer plays 90 % of a written length (articulation gate 0.9); a note written to the bar line leaves a hole
  check: scan the stem for 20 ms frames under (median - 45 dB) and read the times against the score's note ends
  fix: write each bar's note to the bar line (4.0 beats), set the preset articulation {gate 1.0, overlap_ms 25}; retrigger every bar
  avoid: 'tying one note across eight seconds (a sampled double bass dies: a 495 ms hole)'
  evidence: qf_basses, indo finger_bass, 2026-11-28
- id: S04
  title: a 1000 ms hole in an sfx stem at the declared silence
  keywords: [stem.dropout, 1000 ms, declared silence, in_silence, engine, rest, limit]
  rows: [stem.dropout]
  symptom: '"longest hole 1000 ms (limit 20-1000 ms)" on an engine stem across the declared second'
  cause: the hole is exactly the silence, which the row counts because it is not longer than the limit
  fix: fall away 150 ms before the silence and return 150 ms after it, so the hole is longer than 1000 ms and is read as a rest
  evidence: make_sfx.in_silence edge 0.15
- id: S05
  title: stem.tick fires on a few isolated notes
  keywords: [stem.tick, onset autocorrelation, low swell, isolated notes, 93 ms grid, flutter, MIDI 24]
  rows: [stem.tick]
  symptom: autocorrelation 0.5-0.64 at a 93 ms grid on a texture part with 6-9 notes and an IOI CV over 1
  cause: notes at bar-grid times match some 93 ms grid within 20 ms, and notes below MIDI 29 make the GM sample flutter at about 10.7 Hz
  fix: fewer, longer notes, none below MIDI 29 (F1)
  avoid: relaxing min_events before the register and the count are fixed
  evidence: qf_low_swell, 2026-11-28
- id: S06
  title: first note after a rest has a 35 ms hole (family saturator)
  keywords: [stem.dropout, velocity_brightness, drive_k, saturator, family, first note after rest, plucked, 35 ms]
  rows: [stem.dropout]
  symptom: 35 ms of digital silence about 70 ms into the first note after a long rest, on a part that declares a family
  cause: not found; it goes away with the family's saturator off (drive_k 0). A synthetic note did not reproduce it
  fix: 'override the preset with velocity_brightness {drive_k: 0.0} (only on a preset that declares a family; an override with no family raises KeyError h_lo)'
  evidence: 'indo finger_bass, 2026-11-28. Open: engine-notes E02'
---
