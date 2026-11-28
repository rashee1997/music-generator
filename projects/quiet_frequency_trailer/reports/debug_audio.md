# Debug autopsy - quiet_frequency_trailer

20261128T120623  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/quiet_frequency_trailer/scores/quiet_frequency_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'realism.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=28 processed stems from .cache/mix, master=out/quiet_frequency_trailer.wav, verdict=2026-11-28T11:51:26Z, drift=the presets or score changed after this master was rendered: presets/mix/quiet_frequency_mix.json, presets/sfx/qf_alarm.json, presets/sfx/qf_bike.json, presets/sfx/qf_device.json - the autopsy describes the previous mix until you re-render
**inputs changed after this render** (presets/mix/quiet_frequency_mix.json, presets/sfx/qf_alarm.json, presets/sfx/qf_bike.json, presets/sfx/qf_device.json, presets/sfx/qf_heartbeat.json, presets/sfx/qf_impact.json): the rows and stems below describe the previous mix, so no proposal is settled and a lever read from the presets may already be applied

## In question (2)
- **clicks**: 37.0 events against 0.0 -> FAILS by 37.00 tolerance units
  - 37 clustered impulse event(s) (MAD), 12 LPC frame(s); 911 event(s) rejected as a dense burst, 48 as a steep attack; max cluster span 1.497 ms
  - transient attributed to sfx_road 75%, cymbals 25%
- **section.energy**: 0.38181818181818183 rho against 0.5 -> passes with 0.59 units of room
  - Spearman rho 0.38 between promised energy and measured section level (FAIL < 0.5, WARN < 0.7)

## Forensics (signal level)
- **63.623s** single source: cymbals 100%; step 0.0186 vs threshold 0.0200 (-0.6 dB over, z 12.2)
- **64.306s** single source: cymbals 84%; step 0.0188 vs threshold 0.0200 (-0.5 dB over, z 12.3)
- **112.183s** single source: sfx_road 94%; step 0.0020 vs threshold 0.0200 (-20.2 dB over, z 1.3) - decomposition fit 0.16x, treat as indicative
  - under it: sfx_road is a continuous bed with no onset, so the step is in its texture, not on a note
- **112.216s** single source: sfx_road 93%; step 0.0020 vs threshold 0.0200 (-20.1 dB over, z 1.3) - decomposition fit 0.17x, treat as indicative
  - under it: sfx_road is a continuous bed with no onset, so the step is in its texture, not on a note
- **112.510s** single source: sfx_road 79%; step 0.0024 vs threshold 0.0200 (-18.4 dB over, z 1.6) - decomposition fit 0.03x, treat as indicative
  - under it: sfx_road is a continuous bed with no onset, so the step is in its texture, not on a note
- **112.645s** single source: sfx_road 94%; step 0.0021 vs threshold 0.0200 (-19.4 dB over, z 1.4) - decomposition fit 0.09x, treat as indicative
  - under it: sfx_road is a continuous bed with no onset, so the step is in its texture, not on a note
- **113.146s** single source: sfx_road 94%; step 0.0043 vs threshold 0.0200 (-13.4 dB over, z 2.8) - decomposition fit 0.1x, treat as indicative
  - under it: sfx_road is a continuous bed with no onset, so the step is in its texture, not on a note
- **113.184s** single source: sfx_road 94%; step 0.0018 vs threshold 0.0200 (-20.9 dB over, z 1.2) - decomposition fit 0.13x, treat as indicative
  - under it: sfx_road is a continuous bed with no onset, so the step is in its texture, not on a note

## Domains
ran: master
not run (nothing in question): stems (106 rows)
advisory, never binding: 106 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -37.00    -37.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.cymbals -3 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -3 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -6 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
- hf.sfx_road -3 dB, hf.cymbals -3 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -9 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
- hf.sfx_road -3 dB, hf.cymbals -6 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
- hf.sfx_road -6 dB, hf.cymbals -3 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
- hf.cymbals -12 dB: 37 -> 0 (clears, 3 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 0 vs gate 8; missing at [63.623, 64.3063, 112.1816], extra at []): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 3.1 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.86); gains bass_drum 1.09, basses 1.88, basses_pizz 1.27, celli 0.88, choir 1.16, cymbals 0.53, horns 1.03, low_swell 0.22, piano_theme 1.75, sfx_impacts 0.14, sfx_road 4.01, sfx_walkie 1.25, snare 0.90, taiko 0.78, timpani 0.87, trombones 0.50, tuba 0.20, violas 1.05, violins_long 0.70, violins_staccato 0.84'
- 'event 63.623s [single source] cymbals 100%; step 0.0186 vs threshold 0.0200 (-0.6 dB over)'
- 'event 64.306s [single source] cymbals 84%; step 0.0188 vs threshold 0.0200 (-0.5 dB over)'
- 'event 112.183s [single source] sfx_road 94%; step 0.0020 vs threshold 0.0200 (-20.2 dB over); nearest onset sfx_road pNone vNone +0 ms  (fit unreliable)'
- 'event 112.216s [single source] sfx_road 93%; step 0.0020 vs threshold 0.0200 (-20.1 dB over); nearest onset sfx_road pNone vNone +0 ms  (fit unreliable)'
- 'event 112.510s [single source] sfx_road 79%; step 0.0024 vs threshold 0.0200 (-18.4 dB over); nearest onset sfx_road pNone vNone +0 ms  (fit unreliable)'
- 'event 112.645s [single source] sfx_road 94%; step 0.0021 vs threshold 0.0200 (-19.4 dB over); nearest onset sfx_road pNone vNone +0 ms  (fit unreliable)'
- 'event 113.146s [single source] sfx_road 94%; step 0.0043 vs threshold 0.0200 (-13.4 dB over); nearest onset sfx_road pNone vNone +0 ms  (fit unreliable)'
- 'event 113.184s [single source] sfx_road 94%; step 0.0018 vs threshold 0.0200 (-20.9 dB over); nearest onset sfx_road pNone vNone +0 ms  (fit unreliable)'
- 'clicks: iterative replay, profile (events at 0/1/2/3 dB tighter) (0, 2, 1, 1) -> (0, 0, 0, 0) after cymbals -3 dB'
- 'section.energy: no domain module examines this row yet'

## Solver
- the best candidate comes from a model that failed its sham test, so it is not adopted as a plan
