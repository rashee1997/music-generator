---
section: engine-notes
title: Engine faults found and the workarounds in force
lessons:
- id: E01
  title: sfx trigger notes were read as harmony
  keywords: [spiral_tension_arc, trigger note, MIDI 60, sfx, env, pitch audit, roles.is_sound_effect, harmony, Chew]
  symptom: a tonal-tension row gives the same values whatever chords are written
  cause: every sfx track holds one note at MIDI 60 for the whole effect, which counted as a sustained C
  fix: 'fixed in pattern_audit._spiral_series and gate_profiles._drone_ratio with roles.is_sound_effect; any new pitch audit must skip sfx: and env: tracks'
  evidence: tests/test_sfx_not_harmony.py
- id: E02
  title: family saturator can mute the first note after a rest
  keywords: [family_dsp, velocity_brightness, drive_k, restoration, first note after rest, 35 ms, hole]
  symptom: S06
  cause: not found
  fix: workaround S06; to find it, reproduce on a real stem with real events and compare the saturator's level-restore gain before and after the note
  evidence: open
- id: E03
  title: gate_profiles.py relax refuses a row that only failed in a delivery format
  keywords: [gate_profiles relax, did not fail in the last render, format, immersive_7_1, score gate, one-off exception]
  symptom: '''"channel.bars" did not fail in the last render recorded'''
  cause: the recorded gate data is the stereo stem and master stage
  fix: the score gate block with mode relax, a bounded value and the measurement (the gate message names it)
  evidence: M08
- id: E04
  title: importing a project script runs it
  keywords: [import, make_sfx, side effect, rewrote presets, top-level code, main guard]
  symptom: presets rewritten while a render was reading them
  cause: make_sfx.py writes at import
  fix: read values with a throwaway script that parses the file, or put a main guard in the project script
  evidence: '2026-11-28'
---
