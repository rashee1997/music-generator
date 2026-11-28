---
section: arrangement
title: Notes and rhythm
lessons:
- id: A01
  title: a chase that is not a loop
  keywords: [ostinato, repeater, loop, odd cycle, 3+3+2, Rahman, rhythm, accents, hand-off, hole, polyrhythm]
  symptom: a 16th ostinato every bar reads as a machine
  cause: the same figure at the same accents
  fix: five odd cycles (3+3+2+3+3+2, 3+2+3+3+3+2, 3+3+3+3+2+2, 2+3+3+2+3+3, 4+3+3+3+3) that never repeat the bar before; violins a sixteenth behind the cellos; violas answer on the open steps; drums take the accents the strings did not; one or two rested sixteenths in most bars
  evidence: trailer build_piece.cycle
- id: A02
  title: anything after a rest starts late
  keywords: [rest, humanizer, jitter, silence, beat 2, entrance, quarter beat, 25 ms]
  symptom: a note meant to start at the rest's end leaks into the silence
  cause: the humanizer moves onsets by up to 25 ms
  fix: start it at least a quarter beat after the rest ends
  evidence: M02
- id: A03
  title: low notes in a General MIDI bank
  keywords: [low register, MIDI 24, F1, sample range, flutter, bass, swell, sub]
  symptom: a flutter or a thin note under about 40 Hz
  cause: the sample is outside its range and loops
  fix: nothing below MIDI 29 on a SoundFont part; the sub is the master's virtual bass and the kick/taiko
  evidence: S05
- id: A04
  title: the ending
  keywords: [ending, unresolved, curious, cliffhanger, no happy ending, subdominant, device]
  symptom: a brief asks for an unresolved end and the gate fails the outro
  cause: see M05
  fix: end near the key but off the tonic (iv over the tonic pedal), a single hit, a ring; do not add notes after the hit
  evidence: trailer bars 56-60
- id: A05
  title: the first act is sound design
  keywords: [trailer, structure, three acts, silence before the hit, opening, sound design, 120 s]
  symptom: a trailer that starts at full energy has nowhere to go
  cause: no contrast
  fix: about 24 s of alarm, radio, pulse and one low note; one declared second of nothing before the second peak; the second peak louder than the first
  evidence: web research note (Violet Recording, Scripps)
---
