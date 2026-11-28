# Debug autopsy - quiet_frequency_trailer

20261128T090302  ·  level FAIL  ·  plan replay-proved
sources: score=/home/user/music-generator/projects/quiet_frequency_trailer/scores/quiet_frequency_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=28 processed stems from .cache/mix, master=out/_draft_quiet_frequency_trailer.wav, verdict=2026-11-28T08:46:14Z

## In question (1)
- **clicks**: 1.0 events against 0.0 -> FAILS by 1.00 tolerance units
  - 1 clustered impulse event(s) (MAD), 1 LPC frame(s); 300 event(s) rejected as a dense burst, 36 as a steep attack; max cluster span 1.474 ms
  - transient attributed to cymbals 100%

## Forensics (signal level)
- **87.808s** single source: cymbals 90%; step 0.0231 vs threshold 0.0200 (+1.2 dB over, z 15.1)

## Domains
ran: master
not run (nothing in question): stems (106 rows)
advisory, never binding: 106 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
- `hf.cymbals` -3.00 dB cymbals high shelf at 5500 Hz: inst_eq["qf_cymbals"]

clearing set (smallest total move that puts every judged row at zero or better):
- `hf.cymbals` -3.00 dB cymbals high shelf at 5500 Hz: inst_eq["qf_cymbals"]

  clicks::-: -1.00    -1.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.cymbals -3 dB: 1 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -3 dB: 1 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -6 dB: 1 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -9 dB: 1 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -12 dB: 1 -> 0 (clears, 3 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- "clicks: sham replay (no change) reproduces the gate's 1 event(s) exactly (decomposition R^2 0.931); counterfactuals below are priced on a model that passes its own test"
- "clicks: model resolution 1.4 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.93); gains bass_drum 0.82, basses 1.34, celli 0.63, choir 0.72, cymbals 0.53, horns 0.76, low_swell 0.42, piano_theme 1.28, sfx_alarm 0.47, sfx_device 0.59, sfx_impacts 0.23, sfx_road 1.27, sfx_walkie 1.34, snare 0.68, taiko 0.58, timpani 0.48, trombones 0.77, tuba 1.11, violas 0.82, violins_long 0.69, violins_staccato 0.63'
- 'event 87.808s [single source] cymbals 90%; step 0.0231 vs threshold 0.0200 (+1.2 dB over)'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (1, 1, 1, 1) -> (0, 0, 0, 0) after cymbals -3 dB'

## Solver
- clearing set read from a replay through the gate's own checker, not from the linear model; the next render is the measurement
