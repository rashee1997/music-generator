# Project Status: Confluence (one-minute multi-cultural ringtone)

## Flow (SKILL.md)
- [x] 1. Project scaffolded
- [x] 2. Research: five notes in reports/ cite the knowledge base ids (indian-film-fusion, flutes, chinese-japanese, arabic, african, pan-indian, short-form-functional-music) and the main note lists six web sources with URLs and a "Decisions taken from this research" section
- [x] 3. Direction sheet filled: direction/direction_confluence.json (sections, motifs, hits, mix_intent, spatial_staging, expression block, intent, piece_type)
- [x] 3b. Craft pass (references/workflow/director-craft.md section 1), written in the sheet's existing fields:
  - hook: `motifs[0]`, `expression.theme` (rising fourth then two steps, held third, three-three-two cell)
  - arc: seven sections, energies 0.5 / 0.6 / 0.65 / 0.8 / 0.4 / 0.75 / 0.45
  - density map: `sections[].music` (the kalimba rests 5-16 and 23-24, the bansuri rests 1-4 and 9-12, everything but one koto note and the pad rests in bar 24)
  - lanes: kalimba, bansuri and oud carry the tune in turn; koto answers at phrase ends; marimba and bell keep the interlock; pad and bass are the bed
  - contrast: a new carrier, register or colour at every boundary; the Breath drops 14 LU; the return is the first full tutti
  - ending: settles on D6 then Dadd9 and rings out
- [x] 4. Presets: ten instrument presets (each with `character` and `sources`), room `confluence_room`, mix `confluence_mix`; `presets.py validate` clean
- [x] 5. Score: scores/confluence_score.json, written by scripts/compose_ringtone.py (notes and roles only)
- [x] 6. `pipeline.py ... --project` ends CERTIFIED PASS with 0 FAIL (stereo only, `output_targets: ["stereo"]`)
- [x] 7. Revision: many one-lever changes, listed under Decisions; the gate was never loosened
- [x] 8. listen.py ran (measurements only: earshot is not installed)

## Self-check (references/workflow/self-check.md)
- [x] yes: I read AGENTS.md, SKILL.md and the READ TABLE rows (ANY PIECE, fusion, ringtone, mix, gate)
- [x] yes: research cites KB ids and has web sources with URLs
- [x] n/a: no `env:` or `sfx:` track
- [x] n/a: no SFZ track
- [x] yes: gate profile `melodic`, declared as `piece_type`; no row relaxed or skipped
- [x] yes: direction sheet complete (feel, avoid_feel, non-overlapping sections, hits with reasons, spatial_staging, video disabled)
- [x] yes: every instrument has an exact-name project preset with a real `character`
- [x] n/a: no voice
- [x] yes: score has `space`, `mix_preset`; no inline EQ or spatial value (the lean offsets are note timing, not placement)
- [x] yes: mix preset validates. Strategies turned on, each with its measurement in the preset's `note` and `sources`: lead_carve from intent; mastering profile and tone `ringtone` (7 kHz low-pass: 5 click events without it, 0 with it); master high-pass 110 Hz (DC drift 0.00111 against 0.001 at 24 Hz; 10.5% of the energy below 200 Hz before); bass and drum role chains
- [x] n/a: mix was not run with `--diagnose` separately; the pipeline's mix diagnostics WARNs are listed below
- [x] n/a: not immersive
- [x] n/a: not scored to picture
- [x] yes: pipeline ended with 0 FAIL; WARNs listed below with their causes
- [x] yes: balance measured (gate `balance` PASS; stem RMS: bansuri 0.030, darbuka 0.026, pad 0.013, bass 0.012, oud 0.009, kalimba 0.009, koto 0.007, marimba 0.006, shaker 0.004, bell 0.003)
- [x] yes: listen.py ran; the ears (earshot) did NOT run
- [x] n/a: no new ambience or effect
- [x] n/a: no scene ambience
- [x] yes: the reply lists what was not checked

## Measurements on the delivered file
- 61.27 s, 44.1 kHz, 24-bit stereo, -14.2 LUFS, -1.5 dBTP, crest 15.8 dB
- arc_report: Hook -18.7, Hook joined -15.6, Passing -14.9, Lift -12.4, Breath -27.3, Return -12.6, Turnaround -18.1 LUFS (mean); no stretch more than 12 LU under the integrated level
- expression_report: rank correlation with the declared energy +0.54; interval entropy 2.95 bits, range 24 semitones, 18% identical bars
- short_form_report: 89% of the energy in 300-5000 Hz, 2.8% below 200 Hz; 10 onsets in the first 3 s; the opening 5-note shape returns 9 times; density spread 0.19; no flags

## WARNs from the last run (causes)
- cochlear_roughness one frame at 34.5 s (0.100 against 0.070, 2 frames of 14; a FAIL needs 3): a drum hit on the Lift downbeat, as the row says
- modulation_flutter on the oud (22 s) and the kalimba (57 s): the oud's decorative trills are about eight notes a second by design
- spectral.equal_loudness koto 6.3 dB (warn 6, fail 10): a plucked zither is bright
- mix:spectral overlap: oud with darbuka, shaker with bell: they share bands and sit 25 to 75 degrees apart
- intent.avoid: compressed_crest, bed_through_the_gap and rubato_on_the_cell are mix-side gestures that cannot be measured from the score
- staging WARNs are informational (stereo only: elevation is not rendered)

## Decisions / feedback
- One scale for every tradition: D major pentatonic (Mohanam / Bhupali / Gong / African pentatonic), no half-step, so no two notes can rub. Chords use only those five notes.
- The gate decided several details, each a fact: stem.dead on a sparse koto (a koto note added to the Turnaround), spiral_tension_arc (the last two bars now settle on the tonic chords), melodic entropy (varied zither shapes), spatial.z_separation (a 25-degree lattice), cochlear_roughness (open voicings, pad released before the next chord, the bansuri obbligato over the oud removed because its A5 sat a quarter critical band from the high agogo), equal_loudness (the SoundFont rattle measured +14.9 dB in 2.5-5 kHz, so manjira and agogo replace it), clicks (a leave-one-out through the real mix and master found the cymbal sample and the zither sweeps; manjira, slower sweeps, performer timing offsets and a 7 kHz master low-pass reached 0).
- A gapless loop was not delivered. The gate's `end.abrupt` row asks for a release and has no loop-aware replacement; adding one would change when a row applies, which is a gate-policy decision left to the owner. The piece ends with a ring-out on the tonic chords instead.
- The SoundFont stands in for the traditional instruments: kalimba for mbira, flute for bansuri, nylon guitar for oud, koto for guzheng, marimba. The mbira buzz, the bansuri wobble and any oud slide are not modelled.

## Not checked
- Nothing was auditioned: the feel, instrument, pulse, tempo and key checks of listen.py did not run (earshot is not installed). Whether the tune is catchy and the blend pleasant is not measured.
- Not tried on a real phone speaker; the 300-5000 Hz share is a proxy.
- A seam-free loop (sample-accurate repeat) was not delivered or measured as a deliverable.
