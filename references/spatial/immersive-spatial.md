# Immersive headphone spatial audio (height, front/back, room, width)

"Immersive" here means one thing: the stereo headphone master gets real height, placement, room and width through the systems the skill already has
(`mixer.py`, `spatial_hrtf` measured-head route, the `spaces` and `mix` presets). There is no separate engine and no multichannel (7.1.4) output.
Switch it on per piece in the **project's mix preset**; it is off by default, so older projects mix exactly as before.

## 1. Switch and rules (mix preset, kind `mix`)

```json
"immersive": {
  "enabled": true,
  "height_by_role": {"melody": 6, "pad": 15, "environment": 40, "chord": 0, "bass": 0, "drum": 0},
  "max_elevation": 60,
  "min_height_tracks": 1,
  "pair": {"width_deg_bed": 40, "width_deg_stereo": 12},
  "hrtf": {"dataset": ""},
  "gate": {"max_late_iacc": 0.4}
}
```
`hrtf.dataset` is `""` for the bundled FABIAN set, or a listener's own set: put `<name>.sofa` or `<name>.mat` in
`<project>/presets/hrtf/` and write it here. A listener's own set is the largest single step towards an externalised
image, because the cues that do it are individual.
`presets.py scaffold mix <name> --project <dir>` writes this block with `enabled: false`.

**Height rules** (all in presets, never in code by track name):
1. Elevation comes from the track's `spatial`, else its instrument/vocal preset `spatial`, else `height_by_role[role]`.
2. Bass and drums stay at 0 deg (the mixer forces it): height is carried by high-frequency pinna cues, which low sounds do not have.
3. Nothing above `max_elevation` (default 60): near-vertical positions are the least reliable with a dummy head.
4. At least `min_height_tracks` tracks are lifted, otherwise the piece is flat in name only.
5. Elevation in the instrument preset must agree with the direction sheet's `spatial_staging` (within 10 deg) when the sheet gives one.
6. A lifted stem needs energy above 4 kHz to sound high (WARN `imm_band` when it has almost none).
7. The piece's `space` preset needs ground, ceiling, lateral and rear reflections (the gate needs at least 3).

## 2. What the mixer does when `enabled` is true

| Before | Now |
|---|---|
| `elevation` and `space` ignored unless the track opted in with `binaural` | every track with a `spatial` block uses the measured-head route (`binaural: "hrtf"`); `binaural: false` is the only opt-out |
| stereo stems folded to mono | stereo stems become two sources at azimuth -/+ half-width (the mix preset's `immersive.pair` sets `width_deg_bed` and `width_deg_stereo`; `spatial.half_width_deg` overrides per track) |
| `kind: "bed"` never binaural | beds are binaural pairs |
| head-data route had no room | early reflections from the space preset, each from its own direction: floor below (-25 deg), ceiling above (+60 deg), far wall (+-90 deg), rear wall |
| `spatial.py` reflections identical in both ears | `spatial.py` now places floor, ceiling and rear reflections with head shadow, ITD and pinna colour (also the fallback when the head data is missing) |
| reflection taps kept full level while the direct sound fell (DRR inverted: +4 dB measured at 6 m) | each tap obeys its own path, 1/r about `reflections.ref_m` plus the air the longer path crosses; the space preset's `reflections.path_physics` (default true) switches it off for an older project |

Distance, air loss and the shared reverb are unchanged.

## 2b. The four physical layers (all space-preset keys)

| Key (space preset) | What it does |
|---|---|
| `distance.near_field` | below `max_m` (1 m) the ears are different distances from a point source, so the near ear gains level and low end. `strength` 0-1 blends the geometric difference, `lf_boost`/`lf_hz` set the bass emphasis. Before this, 0.2 / 0.5 / 1.0 m rendered byte-identical. |
| `reflections.geometry` | a shoebox room instead of four fixed taps: `width_m`/`depth_m`/`height_m`, a `listener`, six surface `materials` from the `materials` preset library, `max_order`, `max_taps`, `min_level_db`. Delays become real path lengths and each surface filters its tap with its own octave absorption (`scripts/spatial_hrtf/room.py`). |
| `reflections.late` | the directional late field: `count` decorrelated tails from spread directions, sharing `rt60_s`, `hf_decay`, `rise_s`. `level_db` is relative to the dry signal. One tail in both ears is the in-head sound; this is what `imm_envelopment` measures. |
| mix `immersive.hrtf.dataset` | the head data in use: bundled or the listener's own set (section 1). |

A moving source now updates its filter in the STFT domain every 256 samples (`spatial_hrtf/binaural.py::_stft_place`) instead of
interpolating harmonic gains 20 times a second, and `doppler` (default true) resamples the path length, so a crossing source
gets its time-varying cue and its pitch shift together. `references/data/presets/spaces/concert_hall_3d.json` is the worked
example: copy it into a project and change the box.

## 3. Stage 0 (project gate) and Stage 6 rows

Stage 0 blocks when immersive is on and: the mix preset lacks `height_by_role`/`max_elevation` or a real `character`; the head data is not downloaded
(`python -m spatial_hrtf.data`); a bass/drum is lifted; an elevation exceeds `max_elevation` or disagrees with the direction sheet; fewer than `min_height_tracks` are lifted.

| Row | Meaning | Level |
|---|---|---|
| `imm_cues` | probe at +-60 deg: level difference above 8 dB, right source reaches the right ear first by over 0.3 ms (numbers from `tests/test_hrtf.py`) | FAIL |
| `imm_elevation` | the 6-12 kHz tilt grows by over 3 dB at +60 deg | FAIL |
| `imm_frontback` | 30 deg vs 150 deg tilt differ by over 2 dB | WARN |
| `imm_height_rules` | rules 1-4 hold on the final score | FAIL |
| `imm_band` | lifted stems hold at least 0.3% of their energy above 4 kHz | WARN |
| `imm_externalization` | reflections from at least 3 directions; their level is -30 to -3 dB re direct | FAIL / WARN |
| `imm_envelopment` | late-tail interaural correlation under `gate.max_late_iacc` | WARN |
| `imm_width` | master L/R correlation under 0.95 | WARN |
| `imm_foldown` | mono fold-down no more than 3 LU below the stereo master | FAIL |
| `imm_coloration` | front-facing 1/3-octave deviation from the dry signal, 500-5000 Hz, under 3.5 dB rms | WARN |
| `imm_route_parity` | the measured-head and analytic routes agree within 3 dB and 0.2 ms at +-60 deg | WARN |

All nine rows are gate-profile rows (`imm.*` in `gate_profiles.py`, reported under their `imm_*` ids), so a type of piece can skip or relax one with a measured reason, and every threshold the function compares against is read from that profile — none is a constant in `quality_gate.py`.

Thresholds other than the `test_hrtf.py` numbers are provisional: calibrate on a real piece, then freeze them; never loosen one to get green.
Loudness, true peak, clicks and silence are the existing rows.

## 4. Research behind it (sources read with TinyFish)

- Reverberation and spectral detail in the direct sound are the two essential cues for externalising headphone sources, even with non-individual data (Li, Schlieper, Peissig 2019, Applied Sciences 9(3):460). Hence directional reflections.
- Envelopment needs surrounding sound events arriving densely from spread directions, and sound from above is its own attribute (arXiv 2301.10210). Hence beds as pairs and a ceiling reflection; a multi-direction late tail is not built yet.
- IACC alone does not predict envelopment, so `imm_envelopment` is a WARN. Spectral manipulation helps elevation with non-individual HRTFs (Rajendran & Gamper 2019; only the abstract was seen).
- Methods already vendored: MagLS binaural decoding (Hold et al. 2023) in `spatial_hrtf`, FABIAN head data.

## 5. Limits (state them in the reply)

- Height with the FABIAN dummy head is weak and differs by listener; front/back can flip.
- The late field is a statistical tail (`room.late_ir`), not a geometric ray-traced one: it has the room's RT60, damping and direction spread, not its actual wall pattern beyond `max_order`.
- Surface diffusion is not modelled (a specular image cannot scatter); `geometry` keeps the strongest `max_taps` images and stops at `min_level_db`. Below the Schroeder frequency of a small room the modal behaviour is not modelled either.
- A listener's own set must be a `.mat` with `hrir_l`/`hrir_r`/`azi`/`zen` or a SOFA file; a set at another rate is resampled, but nothing checks it was measured at the same distance convention as FABIAN.
- Everything is measured by probes and proxies. Nothing replaces listening on headphones (`listen.py`, then a person).
- No speaker (7.1.4/Atmos) delivery.
