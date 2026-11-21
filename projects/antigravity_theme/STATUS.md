# Project Status: Antigravity (60 s orchestral theme for deep-space exploration, stereo and 7.1)

## Flow (SKILL.md)
- [x] 1. Project scaffolded
- [x] 2. Research: reports/research_deep_space_...md cites KB ids cinematic-hybrid-scoring, psychoacoustic-genre and indian-film-fusion (matched by the finder, not used), plus the new KB note soundfont-velocity-and-realism; web sources are listed with URLs (search-result text only) and "Decisions taken from this research"
- [x] 3. Direction sheet: direction/direction_antigravity.json (sections, motif, hits, mix_intent, spatial_staging, expression, intent, piece_type cinematic, immersive block)
- [x] 3b. Craft pass:
  - hook: eight chord tones, one every two beats: up a fifth, down to the third, up a sixth, a fall of a fourth (`lines.theme`)
  - arc: Weightless 0.25, Ascent 0.5, Orbit 0.8, Singularity 1.0, Horizon 0.3
  - density map: notes per section grow from a pedal, a tick and a piano to the full ensemble (see the arrangement events)
  - lanes: piano states the theme; horn carries it; strings join; organ, choir, low brass and timpani are the weight; arpeggio and cello pulse are the engine
  - contrast: a new carrier or layer at each section boundary; the room opens at Orbit and collapses at the cut
  - ending: a hard cut (timpani on the downbeat of the last bar), then a held organ pedal and one piano D7
- [x] 4. Presets: 13 instrument presets with `velocity_timbre` on every bowed, blown and struck part; room `antigravity_room` (a stone hall with two scenes), mix `antigravity_mix` (ambisonic bus, order 4)
- [x] 5. Score: scores/antigravity_arrangement.json is the piece; `python scripts/arrange.py` writes scores/antigravity_score.json
- [x] 6. `pipeline.py ... --project` ends CERTIFIED PASS with 0 FAIL: stereo master and the 8-channel 7.1 file (`output_targets: ["stereo", "immersive_7_1"]`)
- [x] 7. Revision: many one-lever changes, listed under Decisions; no gate row was loosened
- [x] 8. listen.py ran (measurements only: earshot is not installed)

## Self-check (references/workflow/self-check.md)
- [x] yes: AGENTS.md, SKILL.md and the READ TABLE rows (cinematic, ANY PIECE, soundfont realism, immersive) read
- [x] yes: gate profile `cinematic`, declared as `piece_type`; no row relaxed or skipped
- [x] yes: every instrument has an exact-name project preset with a real `character`; no inline EQ or spatial in the score
- [x] yes: mix preset validates; mastering profile `cue` (-14 LUFS, -1.5 dBTP stereo; -3.0 dBTP on the 7.1 file), 80 Hz third-order master high-pass (measured against master.dc)
- [x] yes: immersive: sheet, mix preset and score agree (`enabled`, hoa_bus, deliverables stereo then immersive_7_1)
- [x] n/a: no ambience or effect, no SFZ track, no voice, not scored to picture
- [x] yes: pipeline ended with 0 FAIL; WARNs listed below
- [x] yes: listen.py ran; the ears (earshot) did NOT run
- [x] yes: the reply lists what was not checked

## Measurements on the delivered files
- stereo master.wav: 66.49 s (60 s of music plus a 6.5 s reverb ring-out), 44.1 kHz, 24-bit, -14.3 LUFS, crest 17.2 dB, LRA 20.7 LU
- 7.1 master_7_1.wav: 8 channels, 44.1 kHz, 24-bit; imm.loudness -14.0 LKFS, imm.surround_ratio -2.4 dB (window -9.0 to -2.0), imm.fold_coherence +0.36, imm.lfe_stopband -83.6 dB, worst channel true peak about -4 dBTP (ceiling -3.0)
- arc_report (LUFS means): Weightless -30.7, Ascent -25.7, Orbit -15.8, Singularity -10.3, Horizon -17.2; pressure share 31 %; the first 22 s sit more than 12 LU under the integrated level by design (the sheet starts the cue near silence)
- expression_report: rank correlation with the declared energy +0.90; interval entropy 3.06 bits

## WARNs from the last run (causes)
- cochlear_roughness one frame at 60.5 s (0.090 against 0.070; a FAIL needs 3): the reverb ring-out after the cut
- imm_band: the harp, string bed and choir sit high but hold under 0.3 % of their energy above 4 kHz (a General MIDI sample's top end), so their height will read weakly
- imm_externalization: reflections from 4 directions at -30.7 dB (want -30 to -3)
- spiral_tension_arc and groove_pocket_lock are informational here; witek_groove_curve: a slow cue on a strict grid has no syncopation
- preflight.roughness_partials: the forecast still lists hot frames around 52 s; the measured row passes (a screening model, see knowledgebase/sound-design/roughness.md)
- intent.avoid: tritone_pedal, bed_through_the_gap, compressed_crest, descending_resolution, rubato_on_the_cell are mix-side gestures that cannot be measured from the score

## Decisions / feedback
- The cue is original: it takes the devices of a space-exploration score (an organ floor, a clock tick, a growing pulse, a hard cut), not any composer's notes.
- A SoundFont has one sample per key and no velocity layers, so `velocity_timbre` (new, scripts/render_natural.py) darkens soft notes per note; the points are starting values.
- The gate decided details, each a fact: roughness came from overtones, not notes (the organ pedal's sixth harmonic at 440 Hz against the horn's Bb4; every low D carries an A4 third harmonic) and was fixed by a D-only pedal point with a 160 Hz low-pass, the theme's Bb replaced by D6, the string bed and arpeggio moved to voicings that avoid the theme's octaves, Dm held through the peak; stem.tick read bar-by-bar chord entries as a pulse on a 93 ms grid (300 ms bow-attack ramps); master.dc from the 73 Hz pedal (80 Hz third-order master high-pass); spiral_tension_arc from the minor third in the final bars (open D and A fifths); imm.surround_ratio (beds 1.0-1.5 dB lower, the front-stage theme parts 1.0-2.0 dB higher, the timpani to the side, a quieter late field).
- `scripts/roughness_forecast.py` (new) forecasts roughness from the score, diagnoses a master and measures a track's partials; see references/mixing/quality-gate.md.

## Not checked
- Nothing was auditioned: feel, instrument, pulse, tempo and key checks of listen.py did not run (earshot is not installed). Whether it sounds like a space film score, whether the theme is memorable, and how the 7.1 field and the height read are not measured. A 7.1 layout has no height channels, and nothing in the immersive path is auditioned.
- The SoundFont is General MIDI: it cannot sound like a commercial orchestral library.
- The delivered file is 66.5 s, not 60.0 s: the tail rings past the cut. A duration tolerance (and a trim) is the follow-up you asked for.
