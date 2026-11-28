---
section: gate-master-rows
title: Master, scene and format rows
lessons:
- id: M01
  title: clicks (protected) on loud layered or noisy material
  keywords: [clicks, click event, crash, splash, squelch, noise burst, onset fade, high-pass MAD, kit, hats, device]
  rows: [clicks]
  symptom: 1-37 click events, usually 0 single-sample jumps
  cause: a stacked crash (two attacks together), a noise burst that starts at full level, an impulsive periodic carrier, kick-snare-hat landing together, a splash on a drum hit
  check: take the event times from gate_checks.check_clicks on the draft, high-pass each stem at 5 kHz and take the largest sample step at those times; the biggest stem is the owner
  fix: onset_fade_ms 3 and a 25 ms stagger on a double crash; noise excite with attack 6 ms, not burst; band-limited noise with a smooth gain curve for a tone-like swell; de-ess the hat band then soft-clip the kit; move a pickup off a drum hit
  avoid: loosening the row (protected)
  evidence: trailer 87.8 s splash, device 112-119 s (35 of 37), indo kit 18.5/32.8/36.3 s
- id: M02
  title: scene.silence_honoured at -40 to -48 dBFS
  keywords: [scene.silence_honoured, declared silence, rest_dip, tail, release, humanizer jitter, hit silence_after_s]
  rows: [scene.silence_honoured]
  symptom: the master is 2-10 dB over -50 dBFS inside the declared second
  cause: a ring-out lifted by an EQ or an opened reverb return; a rest dip whose 80 ms release opens inside the rest; a note that starts at the rest end and leaks 10-25 ms early
  fix: rest_dip depth -42 dB with release_ms 25; start the next notes a quarter beat after the rest ends; gate every sfx voice with the silence
  evidence: highway v06, trailer 62-63 s
- id: M03
  title: scene.hit_surprise with no note in the window
  keywords: [scene.hit_surprise, hit, figure line, melody, horn, leap, register drop, z score, no note in the window]
  rows: [scene.hit_surprise]
  symptom: a hard hit reads "no note in the window" or a z of 0.8-0.93 against 1.0
  cause: the row reads only the figure (melody/lead/vocal) line; drums, bass and sfx do not count
  fix: 'put one horn note on the hit: a leap of 13+ semitones up on a cut into silence, a drop of 20+ semitones on a dropout'
  evidence: trailer hits at 62 s and 104 s
- id: M04
  title: scene.arc_step strain rise too small between build and peak
  keywords: [scene.arc_step, Chew strain, build, peak, harmony, flyover, Gb, Db, tension]
  rows: [scene.arc_step]
  symptom: strain rises +0.015 against a floor of 0.02
  cause: the build's chords were already far from the key; a chord named in the plan adds strain only through the notes actually written (a b9 nobody plays changes nothing)
  fix: calm the build's harmony (Db for Gb), not raise the peak; write the notes you want counted
  evidence: trailer the_flyover, 2026-11-28
- id: M05
  title: spiral_tension_arc outro fails an unresolved ending
  keywords: [spiral_tension_arc, outro, unresolved, cliffhanger, huron_resolution_gravity, ending, subdominant, teleportation]
  rows: [spiral_tension_arc]
  symptom: final bars strain 1.5-1.9 against a 30th percentile of 0.77, or a momentum jump over 1.45 into the last window
  cause: an ending on the dominant, a b9 or a distant chord is read as not coming home; two sfx trigger notes at MIDI 60 also polluted the audit (fixed, engine-notes E01)
  fix: end on a chord near the key that is still not the tonic (Bb minor over F), with common tones into it; excusing the row by scene role RELAX is the user's decision (rule 20)
  evidence: trailer bars 56-60
- id: M06
  title: section.energy rho low after the effects were made louder
  keywords: [section.energy, Spearman, promised energy, section levels, mastering.section_levels, louder effects]
  rows: [section.energy]
  symptom: rho 0.38 against a floor of 0.5
  cause: engines, radio and device kept the quiet sections loud once the music came down
  fix: 'mastering.section_levels {range_db: 6} so the plan''s energy order is set on the master'
  evidence: trailer v04
- id: M07
  title: master dropout at the very end of the file
  keywords: [dropout, final fade, tail, amplitude modulation, 120.3 s, fade_out, end of file]
  rows: [dropout]
  symptom: a 25-40 ms hole just before the file's last 250 ms
  cause: an amplitude-modulated tail dips under the floor on its way out
  fix: end modulated parts well before the file ends (device off at 119.3 s) and fade the master over 1.5 s
  evidence: trailer, 2026-11-28
- id: M08
  title: channel.bars on the 7.1 format only
  keywords: [channel.bars, immersive_7_1, left right balance, front back, one-bar swing, format, relax refused]
  rows: [channel.bars]
  symptom: two isolated bars differ 4-6 dB from both neighbours in the 7.1 file; the stereo master is clean
  cause: story events (a kick placed left in a quiet bar, a V8 waking behind the camera); shortening the revs changed nothing
  fix: 'a one-off score gate entry {mode: relax, balance_db: 6.5, reason: the measurements}; gate_profiles.py relax refuses format rows ("did not fail in the last render")'
  avoid: relaxing without the rca verdict (mismatch) and the written measurement
  evidence: trailer v03
- id: M09
  title: tempo.audio reads half the declared tempo
  keywords: [tempo.audio, beat tracker, 59.9 BPM, half time, odd cycles, 3+3+2, syncopation]
  rows: [tempo.audio]
  symptom: measured 59.9 BPM against 120
  cause: odd-length rhythm cycles moved bar by bar give the tracker only the half-bar
  fix: a score gate skip with the measured value as the reason (not a protected row)
  evidence: trailer
- id: M10
  title: cochlear_roughness between a swell and the next chord
  keywords: [cochlear_roughness, roughness, low swell, chord change, partials, roughness_forecast, impact]
  rows: [cochlear_roughness]
  symptom: 0.074-0.091 over 0.072 at 12.5-13.5 s, 113 s, 119.5 s
  cause: a swell on the old chord rings under the new one; the sfx impact's falling body crosses chord tones
  check: roughness_forecast.py diagnose <draft> --stems --score; read which partials clash
  fix: end each swell at the bar line; keep long ensembles off the impact's tail
  evidence: trailer bars 6-7
- id: M11
  title: pattern row says the piece reads as a loop
  keywords: [pattern, repetition, flatness, velocity barely moves, different bars, drums, tuba, trombones, cymbals]
  rows: [pattern]
  symptom: '6 flags: flat velocity on brass, 2-6 different bars on drums and cymbals'
  cause: the same pattern every bar; a velocity that does not follow the phrase
  fix: accent by phrase position, fills every 8 bars, a ghost before the third beat, a dropped hit, a china and splash pickups; keep ghosts at the part's tier (S01)
  evidence: trailer, 2026-11-28
- id: M12
  title: ambient_bed pumping that is not the ducker
  keywords: [ambient_bed, pumping, 4.3 dB jump, canopy, bird calls, ducker, sidechain environment]
  rows: [ambient_bed]
  symptom: an identical 4.3 dB jump after changing the ducker's attack and release
  cause: the bed's own loud calls sit 8 dB over its floor
  fix: round the calls with a tape saturator on the bed (match_level no)
  evidence: indo canopy 32-35 s
---
