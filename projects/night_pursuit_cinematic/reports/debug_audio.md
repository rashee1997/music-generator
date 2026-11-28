# Debug autopsy - night_pursuit_cinematic

20261127T041521  ·  level WARN  ·  plan no rows
sources: score=/home/user/music-generator/projects/night_pursuit_cinematic/scores/night_pursuit_cinematic_score.json, gate_data=['level.json', 'realism.json', 'rows.json', 'section_energy.json', 'spectrogram.json', 'stem_gate.json', 'stem_levels.json', 'stereo.json', 'waveform.json'], stems=30 processed stems from .cache/mix, master=out/night_pursuit_cinematic.wav, verdict=2026-11-27T03:36:07Z, drift=the presets or score changed after this master was rendered: presets/environments/np_city_far.json, presets/environments/np_drips.json, presets/instruments/pursuit_bass_clarinet.json, presets/instruments/pursuit_bass_drum.json - the autopsy describes the previous mix until you re-render
**inputs changed after this render** (presets/environments/np_city_far.json, presets/environments/np_drips.json, presets/instruments/pursuit_bass_clarinet.json, presets/instruments/pursuit_bass_drum.json, presets/instruments/pursuit_basses.json, presets/instruments/pursuit_basses_pizz.json): the rows and stems below describe the previous mix, so no proposal is settled and a lever read from the presets may already be applied

## In question (0)
nothing failed, so nothing was analysed

## Domains
ran: none
not run (nothing in question): stems (100 rows)
advisory, never binding: 100 row(s) - stem.cut, stem.dc, stem.dropout, stem.edge, stem.tick

## Proposed (first-order prediction)
no admissible move improves the binding rows

## Prediction record: 2 settled, 0 held, 2 did not
- `hf.snare`: replay predicted 0 event(s), the render said no change
- `hf.snare`: replay predicted 0 event(s), the render said no change

## Conflicts (no value satisfies both)
none found in the levers this project declares

