# Debug autopsy - night_pursuit

20261126T094853  ·  level FAIL  ·  plan replay-proved
sources: score=/home/user/music-generator/projects/night_pursuit/scores/night_pursuit_score.json, gate_data=['level.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=24 processed stems from .cache/mix, master=out/_draft_master.wav, verdict=2026-11-26T09:48:00Z

## In question (1)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 1 LPC frame(s); 342 event(s) rejected as a dense burst, 258 as a steep attack; max cluster span 1.497 ms
  - transient attributed to snare 100%

## Forensics (signal level)
- **138.511s** mixed: snare 63%; step 0.0218 vs threshold 0.0202 (+0.7 dB over, z 8.6)

## Domains
ran: master
not run (nothing in question): stems (74 rows)
advisory, never binding: 74 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.snare` -12.00 dB snare high shelf at 5500 Hz: inst_eq["pursuit_snare"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.snare` -12.00 dB snare high shelf at 5500 Hz: inst_eq["pursuit_snare"]

  clicks::-: -1.00    -1.00
  clipping::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10
  true peak::-: +0.35    +0.35

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.snare -12 dB: 1 -> 0 (clears, 2 dB clear of the threshold)
- hf.snare -6 dB: 1 -> 0 (clears, 1 dB clear of the threshold)
- hf.snare -9 dB: 1 -> 0 (clears, 1 dB clear of the threshold)
- hf.snare -3 dB: 1 -> 0 (clears, 0 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 1 event(s) exactly (decomposition R^2 0.946); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 0.7 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.95); gains bass_clarinet 1.31, bass_drum 0.99, basses 1.83, celli 1.14, city_far 4.18, crash 0.19, cymbals 0.71, engine 2.69, horns 0.84, piano 1.16, piano_low 1.80, rain_street 4.28, snare 0.92, sub_drop 2.53, timpani 0.82, trombones 0.78, tuba 1.42, tyres 1.41, violins_staccato 0.85, violins_tremolo 0.69, wipers 2.29'
- 'event 138.511s [mixed] snare 63%; step 0.0218 vs threshold 0.0202 (+0.7 dB over)'

## Solver
- clearing set read from a replay through the gate's own checker, not from the linear model; the next render is the measurement
