# Taking a song apart: notes first, then stems rebuilt from the notes

Pure signal processing, no neural models, CPU only. **Scope: instruments (and humming), drums, space and ambience.**
Sung, rapped and spoken vocals are not modelled; the listening model marks where they are (`song.json` `ignored_vocals`)
and the pipeline keeps away from them.

The idea: a mask can only return what is already in the mix, so a voice hidden under another one comes out with holes and
bleed. Instead the notes are found and repaired as MIDI, and each stem is **played back** from that MIDI.

```
song -> notes per voice -> clean MIDI -> instrument model -> stem -> + drums, ambience, effects, room -> mix -> gate vs the original
```

## Steps

1. **Project** (also builds the pipeline's own environment, `.venv-extraction`, nothing global):
   `python scripts/extract_pipeline.py setup --new-project <dir> --song <file>`
2. **Listen**: paste modules 1-6 of `<dir>/prompts/gemini_listener_prompts.md` into the listening model with the song.
   Save its JSON in `<dir>/music_db/` (`song*.json`, `instruments*.json`, `drums*.json`, `effects*.json`, `spatial*.json`).
3. **Check**: `python scripts/extract_pipeline.py check-db <dir>` (ERROR blocks the run; WARN says what to treat as a search window).
4. **Run**: `python scripts/extract_pipeline.py run <dir> [--profile NAME] [--set section.key=value] [--stages a,b] [--max-attempts N]`
5. **Read** `<dir>/reports/extraction_report.json` (the gate rows), then listen to `out/stems/` and `out/mix_resynth.wav`.

Other commands: `status <dir>`; `kb seed <dir>` (add the database's instruments to the fallback signatures); `kb pitch-table`.

## What each stage does (all numbers are in `templates/extraction_profile.json`)

| stage | does |
|---|---|
| listen | loads the song, measures the tuning offset (cents) and compares it with the database, builds a pitch-resolved spectrum (one row per semitone of the tuned scale, drums removed) |
| voices | iterative multi-pitch note finding, then gives each note to an instrument by range, active span and harmonic template; notes nobody declared are clustered by timbre into `unknown_n` voices (not inside `ignored_vocals`, and only with enough notes) |
| separate | per frame, non-negative least squares over (voice, pitch) atoms, then each voice's share of every STFT bin. These mask-cut stems are a **measuring tool**: the levels for the rebuild and the yardstick for the gate |
| residual | listens to the tonal energy no voice explains, adds new voices, separates again |
| drums | hits from the percussive part; a non-negative factorisation of the hit spectra finds the pieces; named from the database by spectral median, else `perc_n`; `out/midi/drums.mid` |
| effects | ambient bed (steady noise floor), crackle clicks, and the strongest effect events (merged, at most `effects.max_events`), named by `knowledgebase/data/effect_signatures.json` |
| spatial | azimuth, width, delay trick, moves, RT60 from cut-offs, low-end side energy, mono-sum loss; compared with the database's claims |
| **resynth** | **1. MIDI clean-up** per voice (polyphony cap, declared range, overlap trimming, flicker removed; repairs counted). **2. Voices**: a sampler of the voice's own cleanest real notes (picked by harmonic purity) plays the cleaned MIDI and its level follows the song's fitted level; notes the sampler cannot reach, and voices with too few clean notes, are built additively (measured harmonic template, drift, vibrato, breath/bow noise layer). Stereo balance follows the stem over time. **3. Drums**: one-shot per piece (mean of its most isolated hits) retriggered at every hit with the measured level. **4. Ambience**: noise with the bed's spectrum, width and level, plus the real crackle. **5. Effects**: the strongest events as found. **6. Room**: a reverb with the song's measured decay, at the level that brings the rebuilt spectrum closest to the original. Voices with too little music are dropped and reported. `unmodelled.wav` = what the original has that the rebuild does not (sung parts, the rest) |
| gate | see below; PASS / WARN / FAIL per check; up to `gate.max_attempts` attempts, one lever changed per attempt (`gate.levers`), best attempt kept |
| export | sampler presets (`presets/clones/<voice>`, loadable by `clone_instrument.py` and the `clone:` route), instrument presets with measured `spatial`, drum one-shots, a 12 s ambient loop, knowledge write-back, one `extraction_report.json` |
| enhance | optional (`enhance.enabled`, off by default): high-pass and span gate on the mask-cut stems. The rebuilt stems need none |

## What lands in the project

`out/stems/` one file per kept voice + `drums`, `ambient`, `effects`, `room`, `unmodelled` · `out/mix_resynth.wav` ·
`out/midi/song.mid` (cleaned) and `drums.mid` · `presets/` · `reports/` (`extraction_report.json` is the one to read;
the rest are per stage) · `STATUS.md`. The mask-cut stems are written to `out/raw/` only with `--set export.keep_raw=true`.

## The gate

The rebuilt stems share no phase with the original, so nothing subtracts waveforms: every check compares spectra, levels
and statistics.

* `magnitude_match` / `magnitude_by_band` spectral error of the rebuilt mix, outside the `ignored_vocals` windows.
* `voice_fidelity:<id>`, `drum_fidelity`, `ambient_match` each rebuilt part against the cut-out stem it was measured from.
* `midi_repair:<id>`, `midi_polyphony:<id>`, `midi_short_notes`, `midi_key` how much of the MIDI had to be repaired, notes sounding together beyond the instrument's polyphony, flicker, share of note time in the song's key.
* `render_modes`, `room_fit` which voices are sampled and which are synthetic; what the room did for the spectrum.
* **From the main quality gate** (`naturalness_check.py`, `quality_gate.py`), on the rebuilt mix and on the original: `natural:*` (loudness, crest, mud, brightness, width, mono fold-down, static timbre), `roughness`, `clicks`, `stem_clicks`, ERB `masking`, `tonal_balance`, `loudness_match`, `stereo_match`. A fault the original has too is marked `natural:inherited` and not counted: it comes from the recording.
* `tempo_vs_database`, `tuning_vs_database`, `drum_dropouts`, `spatial_claims`, `onset_coverage`, `residual_rounds`, `stem_levels`, `declared_voice`, `file_budget`.

## Using the result

* A voice preset's `clone` path plays through `clone:<project>/presets/clones/<voice>` in a score track.
* The preset's `spatial` block (azimuth degrees, distance metres, width) is measured, not copied from the database.
* The cleaned MIDI is a starting point for a new arrangement: play it through any instrument of the skill.

## Limits (say them out loud)

* Pure DSP is weaker than a neural separator. Notes hidden under louder instruments are missed, and the sampler's real notes still carry some bleed. The gate measures how much; it does not hear.
* Additive voices sound like a tidy synthetic copy of the instrument, not the recording. Samplers sound closer, but only where enough clean notes exist (`render_modes` says which).
* Sung, rapped and spoken parts are not rebuilt; they end up in `unmodelled.wav`.
* Unpitched sound (consonants, breath) is not tracked as notes; the noise layer and the effects stem carry part of it.
* The database's times are search windows. Per-hit times from a listening model are not on the grid; measured hits replace them.
* Tuning must be right before notes are named: the measured offset is used unless `tuning.policy` is `prior`.
* Gate limits are set from synthetic songs. Treat the first real-song numbers as a calibration, and listen.
