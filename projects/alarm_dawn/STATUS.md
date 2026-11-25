# Project Status: Dawn Alarm (one-minute wake-up alarm)

## Flow (SKILL.md)
- [x] 1. Project scaffolded
- [x] 2. Research: reports/research_wake_up_alarm_...md cites KB ids short-form-functional-music, flutes, world-other; six web URLs (search-result text only, not opened); "Decisions taken from this research" lists seven decisions. New KB section 5 and reference section 8 were written from it.
- [x] 3. Direction sheet: direction/direction_dawn_alarm.json (seven sections, motif, hits, mix_intent, spatial_staging, expression block, intent, piece_type)
- [x] 3b. Craft pass (references/workflow/director-craft.md section 1):
  - hook: three repeated D notes then a leap of a fifth to A; the answer leaps to B and falls to D (`lines.hook`)
  - arc: dawn 0.4, stir 0.5, rise 0.65, wake 0.8, lift 0.9, peak 1.0, settle 0.55; each stage adds one lever (notes per second, a new voice, an octave, a layer, level)
  - density map: notes per bar by 4-bar window 16.0 / 35.5 / 46.0 / 49.2 / 52.0 / 53.5 / 10.2
  - lanes: kalimba, bansuri and oud carry the tune in turn; koto flourishes at phrase ends; marimba and bell keep the interlock; pad and bass are the bed
  - contrast: a new carrier or register at each stage; the settle drops 12 LU on purpose
  - ending: steps down to D, Dfinal chord, rings out
- [x] 4. Presets: ten instrument presets (carried over from the ringtone project, each with its measured sources), room `dawn_alarm_room`, mix `dawn_alarm_mix` (profile `alarm`, -12 LUFS); `presets.py validate` clean
- [x] 5. Score: scores/dawn_alarm_arrangement.json is the piece; `python scripts/arrange.py` writes scores/dawn_alarm_score.json. No musical value is in Python.
- [x] 6. `pipeline.py ... --project` ends CERTIFIED PASS with 0 FAIL (stereo)
- [x] 7. Revision: see Decisions; the gate was never loosened
- [x] 8. listen.py ran (measurements only: earshot is not installed)

## Self-check (references/workflow/self-check.md)
- [x] yes: AGENTS.md, SKILL.md and the READ TABLE rows (ANY PIECE, ringtone/alarm, fusion, mix, gate) read
- [x] yes: research cites KB ids and has web sources with URLs
- [x] n/a: no env/sfx track; no SFZ track; no voice; not immersive; not scored to picture
- [x] yes: gate profile `melodic`, declared as `piece_type`; no row relaxed or skipped
- [x] yes: every instrument has an exact-name project preset with a real `character`
- [x] yes: score has `space`, `mix_preset`; no inline EQ or spatial value
- [x] yes: the mix preset's mastering profile `alarm` (-12 LUFS, -1.5 dBTP, 7 kHz low-pass, 110 Hz high-pass) is a starting value, said so in its `note`
- [x] yes: pipeline ended with 0 FAIL; WARNs listed below
- [x] yes: listen.py ran; the ears (earshot) did NOT run
- [x] yes: the reply lists what was not checked

## Measurements on the delivered file (out/master_v03.wav = out/master.wav)
- 61.35 s, 44.1 kHz, 24-bit stereo, -12.3 LUFS, crest 14.8 dB
- arc_report (LUFS mean): dawn -22.6, stir -19.7, rise -13.8, wake -11.6, lift -9.1, peak -10.2, settle -22.1: rising stage by stage, the settle is the release
- expression_report: rank correlation with the declared energy +0.86; interval entropy 3.14 bits, range 24 semitones
- short_form_report: 90% of the energy in 300-5000 Hz, 2.3% below 200 Hz; 10 onsets in the first 3 s; the opening shape returns 7 times; density spread 0.44

## WARNs from the last run (causes)
- cochlear_roughness one frame at 53.0 s (0.115 against 0.070, 2 frames of 19; a FAIL needs 3): the first bar of the settle where the kalimba and the pad's new chord meet; not found by a leave-one-out, left as a WARN
- modulation_flutter on the oud and the kalimba: trills and flams by design
- mix:spectral overlap: oud with darbuka, bass with pad, bell with shaker
- witek_groove_curve: bar syncopation index 0.00 on the grid reading; the pattern is a three-three-two
- intent.avoid: tritone_pedal, bed_through_the_gap, compressed_crest, descending_resolution, rubato_on_the_cell are mix-side gestures that cannot be measured from the score

## Decisions / feedback
- The piece is declared, not coded: scripts/arrange.py (new, tested in tests/test_arrange.py) expands the JSON.
- The gate decided details, each a fact: note_collision (a duplicated fill), stem.dropout (a kalimba and a bass note longer than their samples, drum notes shortened to the sample), stem.edge (bass ring-out 2.2 beats), preflight roughness and unison (a final chord that does not share the kalimba's D5), cochlear_roughness (a kalimba line that did not unison with the pad), clicks (the tag and the zither flower lowered so no note is stretched past its sample range, zither run ceiling 86), spatial.z_separation (the pad moved to -105 degrees).
- The escalation is by density, register and layers, with a few LU of level, not by harshness: no siren, no sharp 2-5 kHz peak, no sub-bass.
- A gapless loop was not delivered: `end.abrupt` has no loop-aware replacement (a gate-policy decision for the owner). The alarm ends on the tonic chord it starts on and rings out; `short_form_report --loop` FLAGs the level jump across the repeat for that reason.

## Not checked
- Nothing was auditioned: feel, instrument, pulse, tempo and key checks of listen.py did not run (earshot is not installed). Whether the tune is catchy, whether the blend is pleasant and whether it wakes a sleeper is not measured. The research finding behind the melodic choice is a small self-reported survey.
- Not tried on a real phone speaker; the 300-5000 Hz share is a proxy.
- The loudness (-12 LUFS) is a starting value, not calibrated against a bedside phone.
- A sample-accurate loop was not delivered or measured.
