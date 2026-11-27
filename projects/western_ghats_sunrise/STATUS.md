# Project Status: Western Ghats Sunrise

A 60 s A.R. Rahman style cultural mix: a bansuri in the Mohanam pentatonic over a sectioned choir, strings, tanpura, veena, santoor and tabla, with Scottish Highland pipes joining smoothly, in a Western Ghats sunrise ambience with native birds. Delivered as a stereo master and an 8-channel 7.1 bed from one fifth-order ambisonic bus (hoa_bus, order 5).

## Flow
- [x] 0. AGENTS.md and SKILL.md read, request type chosen (fusion, Indian film, cinematic, ambience, immersive, vocals/choirs)
- [x] 1. Brief parsed, defaults stated: 88 BPM, D, 22 bars = 60 s, 4 sections, stereo + 7.1 as asked ("as usual")
- [x] 2. Project scaffolded with `--ambience` (the user asked for the ambience)
- [x] 3. Research: `reports/research_western_ghats_sunrise_rahman_fusion.md` (KB indian-film-fusion, pan-indian, flutes; web sources for Rahman, Mohanam/Bhupali, the Highland pipe scale, the Western Ghats birds and frogs; every figure marked search-result text or ESTIMATE)
- [x] 4. Direction sheet `direction/direction_western_ghats_sunrise.json` (expression block, harmony_plan, immersive block)
- [x] 5. Presets: 9 instruments + tabla, a layered choir (`ensemble.layers`), 5 native bird calls, the ambience, space, mix, gate profile
- [x] 6. Score `scores/western_ghats_sunrise_score.json`, all written by `scripts/build_project.py`
- [x] 7. Pipeline: stereo CERTIFIED and immersive_7_1 delivered (attempt 20 of the run history, see the failure log)
- [x] 8. Reports run: realism, arc, expression, listen (listen: earshot not installed, so the ear checks did not run)

## Outcome
- Stereo: `out/western_ghats_sunrise.wav` (44.1 kHz, 24-bit, 61.5 s, -16.0 LUFS, -1.9 dBTP)
- 7.1: `out/western_ghats_sunrise_immersive_7_1.wav` (8 channels FL FR FC LFE BL BR SL SR, same file length)
- Length: 61.5 s against the 60 s sheet (a 1.5 s tail past the last bar); the length gate row passed, `listen.py` marks it CHECK.
- Gate relaxations (both measured, both in the files): `tempo.audio octave_ok=1` (tempo read 176.2 BPM, the written 88 doubled by the eighth-note pulses) and the score's `channel.bars jump_db=14` for one bar (bar 17: the flute rests while the Highland pipes answer from behind, front centre dips 12.3 dB).

## Arc (arc_report)
mist -25.2 LUFS, first light -20.7, sunrise -12.3, morning -22.3: the loud section stands 13 dB above the quiet one (realism.dynamic_scale 13.9 dB). The expression report ranks the sections in the declared order (rho +1.00).

## Realism report (advisory, stage 5a not run by the pipeline because of a bug found and fixed here; run by hand after)
PASS: transient, depth, low_mid, distance, repetition, coherence, sub_weight (no stem carries a sub), air, dynamic_scale, impact_attack, foreground, harmonic_motion.
WARN, and not fixed:
- timbre_loudness -1.55 dB: loud passages are darker, not brighter (the GM/MuseScore banks have one sample layer; the plan's bank audit measured 0 velocity layers).
- ensemble: 5 section parts are each one player multiplied by the renderer's `ensemble` setting (players 3-6), not recorded sections.
- openness -10.1 dB: the top octave falls at the loudest passages (the tabla high shelf of -15 dB and the 8.5 kHz low-pass were set to clear `clicks`).
- phrasing 0.0: metronomic at the bar (rubato 0 so the plan's section times equal the tempo map; a gentle tempo breath was not added).
- vibrato: the tanpura (a plucked drone) holds a flat pitch.
- velocity_response: bansuri and violins_counter get louder, not brighter.

## Director's second review (director-craft.md section 5)
- Could still show: a generic arc (it rises and falls once): the measured step between sections and the key raise at 30 s are the counters. A static pedal: bars 1-5 are a declared pedal; the other sections move the bass (harmonic_motion PASS).
- A human producer would first: write real section players (recorded or sampled, not multiplied) for the strings and make the loud passages brighter.
- Not heard: everything. No file was auditioned. The bagpipe sample, the five bird calls (contours are ESTIMATES from qualitative descriptions, none measured), and the choir sections (a synthesised vocal engine) are the least certain.

## Failure log (root cause before any edit)
| Row | Cause class | Evidence | Lever | Result |
|---|---|---|---|---|
| stem.dead ambience | fault | stem median -81.9 dBFS: the physical engine's levels with full_scale_pa 2.0 | `reference.full_scale_pa` 0.1 | cleared |
| ambient_bed pumping/dropout | fault | beds alone spread 33 dB over 30 s (wind gusts at intensity 0.35, stream 24 dB under it) | wind intensity 0.08, stream +20 dB, drip +0 dB | beds within 6 dB, cleared |
| env.score_pocket | fault | the score's occupancy is 0.9-1.0 in every band from 0.7 to 7 kHz | birds moved to free bands (4-8 kHz), two far birds as bed | cleared |
| stem.dropout violins_long/celli | fault | held sampled notes of 6 s end early; same-pitch re-attack gaps | one note per bar overlapping 0.5 beat, no onset ramp | cleared |
| stem.tick violins_long | fault | onset autocorrelation 0.62 (every bar attack aligned) | restrikes staggered 0.4 beat per voice | cleared |
| stem.clipping choir | fault | 275 samples at full scale: the sum of five sections had no limiter | soft limit and `peak_trim` on the layer sum in the engine | cleared |
| cochlear_roughness | fault | choir stem alone 0.070; seconds between sustained voices | open voicings, choir cohesion 0.78, 70 % of the voices, tighter pitch spread, gentler vibrato | cleared |
| clicks | fault | debug_audio: all events attributed to tabla above 6 kHz | -15 dB high shelf at 6 kHz in `inst_eq`; snap removed from plucked parts | cleared |
| tempo.audio | mismatch | 176.2 = 2.002 x 88 | bounded `octave_ok` profile parameter (new, default off) | cleared |
| imm.surround_ratio | fault | -9.9 then -10.1 dB; the ambience lift made it worse | sections moved to the sides and behind (celli 88, violas -68, strings 150, choir -140) | cleared |
| spatial.z_separation | fault | tanpura and violas 20 deg apart | violas -68 | cleared |
| channel.bars (7.1) | mismatch | bar 17 FC jump -12.3 dB, the flute rests under the pipes' call | score-level exception `jump_db` 14 with the per-bar table | cleared |
| realism stage 5a | tool bug | `ts` written as a list crashed harmonic_motion; drum names broke it | fixed in `realism_cinema.py`, two regression tests | fixed |
