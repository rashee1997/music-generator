# Project Status: Night Pursuit

A rainy-night New York car chase, 174 s, C minor, tempo 128 to 156 BPM with two slow-motion dips, delivered as a stereo master and an
8-channel 7.1 file decoded from a fifth-order ambisonic field. Sound effects and ambience were asked for in the brief.

## Flow (SKILL.md): tick each step, note decisions below
- [x] 1. Project scaffolded (direction/ presets/ scores/ midi/ stems/ reports/ scripts/ out/)
- [x] 2. Research: `reports/research_night_pursuit_rain_street.md` cites the knowledge base (sfx-ambience, sfx-formulas, game-sfx, cinematic-hybrid-scoring)
      and web sources; a "Real-world references" section for each of the nine sounds; decisions listed. Pages were read as search results, not opened.
- [x] 3. Direction sheet filled (`direction/direction_night_pursuit.json`, written by `scripts/make_direction.py` from `scripts/timeline.py`)
- [ ] 4. Presets for every non-built-in instrument (presets/instruments), each ambience (presets/environments) and tuned effect (presets/sfx), each listing its "sources"
- [ ] 5. Score written (scores/night_pursuit_score.json, by `scripts/compose_main.py`)
- [ ] 6. `pipeline.py scores/night_pursuit_score.json --project .` renders out/master.wav, midi/, stems/, reports/ci_report.json
- [ ] 7. Revise one lever at a time until 0 FAIL (max 5 attempts, then report)
- [ ] 8. listen.py on out/master.wav; deliver

## Craft pass (director-craft.md section 1): written before any note

1. **The hook.** The tick: C, Db, C, then a leap up a tritone to Gb and a step down to F, long-short-short-long-long. The leap lands on the weak beat every time
   and never resolves. It is whispered by the bass clarinet (spotted), stated by the horns (the avenue), raised a semitone and doubled after the drift snap, played
   by horns and trombones together on the bridge, and at the cliff only the Gb is left. The second hook is not a tune: it is the engine's pitch, which the listener
   follows through four shifts.
2. **The arc.** Stakeout (0.30) -> spotted (0.45) -> avenue (0.70) -> turn (0.85, with the slow-motion drift) -> underpass (0.90) -> roadblock (1.00, with the crash)
   -> bridge (0.95) -> a cut to the cliff (0.20). The energy rises to the roadblock and stays high through the bridge; the last section is a cliff, not the fade of a
   peak. The tempo climbs 128 -> 156 BPM, falling twice into slow motion (60 and 64 BPM) and snapping back.
3. **The density map.** Stakeout: bass and heartbeat only. Spotted: + celli eighths, clarinet. Avenue: + piano sixteenths, celli, 3+3+2 drums, horns, tuba. Turn: full, then
   a collapse to the heartbeat and a low pedal in the slow motion (the quietest bar of the cue before a hit), then full again. Underpass: pulse and low brass only for
   six bars, then tremolo strings and the rising line. Roadblock: everything, trombone stabs, tritone clusters, snare roll; a second hollow bar before the crash.
   Bridge: everything plus the fast violin runs. Cliff: nothing sustained.
4. **The lanes.** Sirens own 600-1500 Hz and the engine's harmonics 50-470 Hz and a body formant near 180 and 600 Hz; the music stays out of the siren's lane: brass low
   (under 400 Hz) and the strings high (over 2 kHz); the horns carry the figure in the lower middle. One owner of the low end: the basses (the tuba and piano_low double
   them and the sub drop is a single event, never a sustained part). The piano's sixteenths are the only constant in the 1-3 kHz middle.
5. **The contrast.** Three planned silences: the hollow bar before the drop (the slow motion), the held bar before the crash, and the cut. A pulse that goes up a semitone at
   each turning point is the rising device. Quiet is real: the stakeout and the cliff sit 15 LU or more under the roadblock.
6. **The ending.** A hard cut on the first beat of the cliff: every sustained voice ramps to silence over 15 ms (`kind: cut`, `sync: hard`), then rain, a ticking engine
   as it cools, one far siren and a single high harmonic over a Gb. It does not resolve: the last pitch is the tritone.

## Blend rule (shared core)
One tonic (C), one scale (C minor with Db and Gb as the two pressure notes), one pulse (a sixteenth grid at the tempo map). The music carries the figure; the engine, tyres
and sirens carry the place; the sirens are tuned off the key's semitone neighbours so they do not beat against the strings.

## Rules
1. Never monolithic: sound and space in presets/, notes in scores/, intent in direction/.
2. The scaffold's sample presets were replaced by this piece's own.
3. The immersive bus is fifth order (36 channels) and is decoded once to the eight speakers of 7.1; 7.1 has no height speakers, so nothing is lifted.

## Decisions / feedback
- 26 November 2026: three minutes allowed by the user; the cue is 174 s. The user asked for a fifth-order render folded to 8 channels so the physics (reflections, Doppler,
  occlusion) happen in the field before the speaker feed.
- Slow motion is made by the tempo map (a dip to 60 and 64 BPM that snaps back) and by `fx` chains on the stems (a pitch glide down and a filter closing on the engine and
  tyres); rain is thinned, not pitched, because water does not pitch down well.
- Street objects: façades of brick (reflection 0.9, absorption 0.1), glass and wet asphalt are the room's materials; parked trucks and a building corner are occluders on the
  sirens; an underpass and a bridge are room scenes.
