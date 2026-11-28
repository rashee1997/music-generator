# Debug autopsy - quiet_frequency_trailer

20261128T150452  ·  level FAIL  ·  plan nothing to move
sources: score=/home/user/music-generator/projects/quiet_frequency_trailer/scores/quiet_frequency_score.json, gate_data=['feedback.json', 'level.json', 'rca.json', 'realism.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=30 processed stems from .cache/mix, master=out/quiet_frequency_trailer.wav, verdict=2026-11-28T12:40:40Z, drift=the presets or score changed after this master was rendered: presets/instruments/qf_bass_drum.json, presets/instruments/qf_basses.json, presets/instruments/qf_basses_pizz.json, presets/instruments/qf_celli.json - the autopsy describes the previous mix until you re-render
**inputs changed after this render** (presets/instruments/qf_bass_drum.json, presets/instruments/qf_basses.json, presets/instruments/qf_basses_pizz.json, presets/instruments/qf_celli.json, presets/instruments/qf_choir.json, presets/instruments/qf_cymbals.json): the rows and stems below describe the previous mix, so no proposal is settled and a lever read from the presets may already be applied

## In question (1)
- **clicks**: 2.0 events against 0.0 -> FAILS by 2.00 tolerance units
  - 2 clustered impulse event(s) (MAD), 1 LPC frame(s); 239 event(s) rejected as a dense burst, 17 as a steep attack; max cluster span 1.474 ms
  - transient attributed to cymbals 100%

## Forensics (signal level)
- **36.430s** single source: cymbals 84%; step 0.0106 vs threshold 0.0200 (-5.5 dB over, z 48.6) - decomposition fit -0.0x, treat as indicative
- **87.658s** single source: cymbals 89%; step 0.0328 vs threshold 0.0200 (+4.3 dB over, z 150.6) - decomposition fit -0.0x, treat as indicative

## Domains
ran: master
not run (nothing in question): stems (118 rows)
advisory, never binding: 118 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

  clicks::-: -2.00    -2.00
  clipping::-: +0.00    +0.00
  true peak::-: +0.00    +0.00
  loudness::-: +0.02    +0.02
  end.abrupt::-: +0.02    +0.02
  master.dc::-: +0.10    +0.10

## Replay-verified candidates (each priced by running the gate's own checker on the modelled mix)
- hf.cymbals -3 dB: 2 -> 0 (clears, 2 dB clear of the threshold)
- hf.cymbals -6 dB: 2 -> 0 (clears, 2 dB clear of the threshold)
- hf.cymbals -9 dB: 2 -> 0 (clears, 2 dB clear of the threshold)
- hf.cymbals -12 dB: 2 -> 0 (clears, 2 dB clear of the threshold)
  - a cut is a high shelf at the row's corner added to `inst_eq.<stem>` in the mix preset; the model replaces the stem's band by a scaled copy, so the real shelf is the measurement

## Conflicts (no value satisfies both)
none found in the levers this project declares

## Measurements behind this
- 'clicks: the sham replay does NOT reproduce the gate (model 0 vs gate 2; missing at [36.4289, 87.6585], extra at []): every candidate below is UNVERIFIED and is shown for direction only'
- "clicks: model resolution 69.0 dB (90th percentile error of its steps against the master's); a candidate counts as proved only when it clears with at least that margin"
- 'decomposition: master ~ sum of gain x stem in the click band (R^2 0.00); gains basses -0.16, basses_pizz 3.42, choir 0.21, low_swell -1.22, piano_theme -0.20, sfx_alarm -0.14, sfx_boom -0.30, taiko -0.07, timpani -2.92, trombones 0.43, tuba 2.10, violas -0.07'
- 'event 36.430s [single source] cymbals 84%; step 0.0106 vs threshold 0.0200 (-5.5 dB over)  (fit unreliable)'
- 'event 87.658s [single source] cymbals 89%; step 0.0328 vs threshold 0.0200 (+4.3 dB over)  (fit unreliable)'

## Solver
- the best candidate comes from a model that failed its sham test, so it is not adopted as a plan
