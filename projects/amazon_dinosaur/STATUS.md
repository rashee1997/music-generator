# Project Status: Amazon Dinosaur

## Flow (SKILL.md): tick each step, note decisions below
- [x] 1. Project scaffolded (direction/ presets/ scores/ midi/ stems/ reports/ scripts/ out/)
- [x] 2. Research: `research_kb.py` note citing the knowledge base + web sources (reports/research_<topic>.md);
      for every ambience or effect the score uses: `--sounds a,b` and fill each "Real-world references" section (2 sources, licence)
- [x] 3. Direction sheet filled (direction/direction_sheet.json)
- [x] 4. Presets for every non-built-in instrument / vocal (presets/instruments, presets/vocals), each ambience (presets/environments)
      and tuned one-hit effect (presets/sfx), each listing its "sources"
- [x] 5. Score written (scores/*.json) referencing presets by exact name
- [x] 6. `pipeline.py scores/<title>_score.json --project .` renders out/master.wav, midi/, stems/, reports/ci_report.json
- [x] 7. Revise one lever at a time until 0 FAIL (max 5 attempts, then report)
- [x] 8. listen.py on out/master.wav; deliver

## Rules
1. Never monolithic: sound and space in presets/, notes in scores/, intent in direction/.
2. Sample presets here (lead_flute, warm_piano, ...) are examples: rename or replace them.
3. The mixer applies azimuth (pan), distance (air filter, level, reverb send), width and one shared room.
4. The mix preset owns the strategies: gain_staging (legacy|adaptive), dynamics.engine (pedalboard|dsp),
   spectral profiles, space, sidechain.mode (legacy|explicit|off) and the mastering profile.
   `python scripts/presets.py show mix default` prints every key with its shipped value.
   `spatial.elevation` and `spatial.space` are stored but not applied.

## Decisions / feedback

## Craft pass (director-craft s1, before any note)
1. **Hook**: horn hymn D-F#-A-D in first 8 beats, alone over piano D pedal - you know the giants before you see them.
2. **Arc**: wonder (0.25) -> herd build (0.55) -> dread pedal (0.70) -> chase (0.90) -> awe finale (1.0) -> cliff silence -> last D chord. Last section is peak, never fade of peak.
3. **Density map**: 2 tracks (horns+piano) -> +strings/choir -> +cello ostinato/timpani -> +tremolo/taiko/braam -> all 14 in chase/finale -> hit + silence.
4. **Lanes**: horns centre theme, celli left ostinato, braam centre-low, timpani left taiko right, choir centre-back, strings left pad, trumpets right fanfare. No two midrange parts share a place.
5. **Contrast**: pp hymn vs ff braam, long notes vs marcato stabs, sound vs 2-beat silence before chase/finale.
6. **Ending**: orchestra hit, silence, horns+strings+choir last D in room tail - triumphant but not resolved with a pop cadence.
**Anti-funk rule**: straight beats only, no syncopation, no kit/guitar/bass-guitar/synth, no tempo map, no arpeggio groove. If a line could be played by a funk band, it does not enter.

## Delivery (2026-11-22)
- Stereo master CERTIFIED PASS (master_v09.wav): -14.1 LUFS, -1.5 dBTP, 118.5s, QA gate fully green.
- Immersive 7.1 (master_7_1.wav, 8ch) CERTIFIED PASS: surround -7.6 dB vs front (window -9..-2), LFE/channel.bars 45 bars clean, loudness -14 LKFS.
- Final root causes fixed in notes/presets (never thresholds): bass roots octave-down below LFE crossover (channel.bars), surround-resident gains up (imm.surround_ratio), tuba continuous pedal arc (LFE spikes), bass/tuba 0.2-beat overlap (LFE smoothing without roughness), timpani/taiko pulse + level trims (tempo.audio, roughness).
- Listen (measurements only, --no-ears): loudness/true-peak/clipping PASS; length CHECK (118.5 vs 117.3 target = reverb tail). Ears/feel checks not run. Nothing has been heard by a human.
- Masters are not in version control: `out/` and `*.wav` are gitignored (rebuilt output), and the 8-channel `master_7_1.wav` is 125 MB, above GitHub's 100 MB per-file limit. The render is reproduced from this project with `pipeline.py scores/main_score.json --project .`; `reports/ci_report.json` is the certification record of the delivered renders.
