---
title: Troubleshooting and limits
summary: Symptom to cause for the common failures, and the honest limits to tell the user.
tags: [troubleshoot, error, symptom, limit, failure, fix]
load_when:
  - a render or check misbehaves
  - writing the limitations section
---

# Troubleshooting and limits

## Troubleshooting

| Symptom | Fix |
|---|---|
| `listen.py` says earshot is not installed | run `python3 scripts/setup_project.py --ears`; measurements still work meanwhile |
| "No steady beat" when a beat was wanted | `direct.add_pulse` from the start; `humanize="tight"` on the drums |
| "It always comes out upbeat" | the brief had no mood word, so `focused` (90-104) was used. Name the feel ("motivational", "adventure", "melancholy", "slow reverb mix") and check `meta.mood_notes`; add `--space large_hall` for the room |
| It reads sad when epic was wanted | `epic` is major by default; if it still reads sad, check `--mode`, then tempo, then a fanfare or a bigger arc. For dark power use `dark_epic` |
| A named instrument is missing | add a track for it (`direct.add_line`), raise its gain, or use a clone |
| Silent or thin stem | wrong instrument name (`soundbank.py --list`), notes past the end, dynamics at 0, or out of range |
| Muddy, harsh, mono or too quiet | `references/mixing/mixing-and-mastering.md` section 6 |
| Still sounds robotic | humanize is `natural` or looser, vibrato on sustained parts, a clear arc, two layered instruments, a real recording cloned |
| Target loudness not reached | a very dynamic piece may not get there; accept it, do not squash it |
| The project gate says "no environment preset in the score has a bed" but yours is a physical scene | a scene counts as a bed when the preset uses `scene_layers`, or when its timeline uses a continuous mechanism (`flow`, `foliage`, `granular`, `rolling`, `gait`, `repeated_impact`). A single impact/creak/fracture scene is a spot: add a bed scene or a `layers` bed |
| `mix:` rows in `reports/ci_report.json` | the mixing diagnostics, advisory by contract: a diagnostic `FAIL` is reported as `WARN` because the gate's own rows (true peak, clipping, silence) own the blocking verdicts. Fix what they name, do not silence them |
| A gate row that `quality_gate.py` reports never appears in a pipeline run | it cannot any more: stage 6 is a single `run_gate` call. If one is missing, the row was added after that call or the profile skips it — check `gate_profiles.py rows` |
| A scene is refused by `physical.py check` | the message names the field, the mechanism or the material and lists what is valid. An unknown interaction is not a typo to ignore: it is a mechanism that does not exist |
| A scene renders far too quiet or too loud | that is calibration, not a bug: set `calibration.level_db`. Do not reach for `normalize: peak`; use `energy` and trim |
| Sand sounds like gravel (or wood like metal) | the material is doing the work: check `grain_size_m`, `young_modulus_gpa`, `loss_factor` and `flow_resistivity` before changing any spectral gear |
| `physical.py verify` reports CHANGED on a sound you did not intend to touch | stop: one of the physics constants moved. Find it with `--only <name>`; if the change is intended, regenerate the baseline and say so |
| A new sound needs a mechanism that is not in `physical.py laws` | add the mechanism (a function and one registry line), not a sound name; then add a test that holds it to a physical fact |
| `presets.py validate` reports `mix.<section>.<key>: unknown key` | the engine would ignore it: the name is misspelled or belongs under another section. `presets.py show mix default` lists every key with its shipped value |
| `unknown spectral profile` is raised | the name is not one of `rain, water, wind, foliage, insect, voice, strings, flute, bed`. Add a profile to the piece's mix preset under `spectral.profiles`, or drop the key and get the role chain |
| The master prints `reached X LUFS, not Y` | the music is too dynamic for that target under that ceiling. Lower the target, raise the ceiling, or accept it; do not add compression to reach a number |
| `[export]` prints a problem | the file written is the file measured: a true peak over the ceiling, full-scale samples or a wrong length mean the master settings (`true_peak`, `width`, `mono_below`), not the export |
| A diagnostics row is WARN but the mix sounds right | the rows are measurements counted per band, not verdicts. Spectral overlap and intelligibility in particular. Keep the decision and say it was deliberate |
| A mix renders differently from the last run | check `mix_preset` and `space` in the score: one context is resolved per piece now, so two pieces in one process cannot share state. Inside your own script, a stale `use_mix()` or a hand-edited `mixer.STATE` still can |
| A mix that was fine reads harsher or muddier after enabling `dynamics.engine: "dsp"` | that engine adds the knee and detector you asked for, and then the role compressor is applied twice if you also left a track `comp`. Set one or the other |

## Limits (say these in the reply)

- The physical engine models the physics it names and estimates the rest. Contact-time scale, fracture energy fraction,
  canopy loss, plate coefficients, and leaf/grain contact bands are ESTIMATE, marked in code; only a measurement
  (`ambience_reference.py measure`, `--modes`) turns one into a number you can defend.
- Radiation is omnidirectional, leaf flutter and canopy scattering are statistical surrogates, and no acoustic model
  here has been checked against a recording unless a project did that check itself.
- Nothing in the physical engine has been auditioned. `physical.py render` and `baseline --wav` produce files to listen
  to; that listening is the user's or a later session's, not something the tests do.
- The vocal source models (`pulse`, `lf`) are not fitted to a recorded singer, and `rd` values are starting values.
- The sympathetic bed is a resonator bank on the mixed stems: it has no bridge, no string coupling and one tuning for
  the whole piece.
- The room rows (`imm_iacc_early`, `imm_clarity`) measure the modelled room's impulse response, not a real hall, and
  their limits are starting values that no corpus has calibrated.
- The sampled bank is good, not concert-grade. Do not claim it is indistinguishable from a real orchestra.
- No sung words. Choir and "oohs" are texture only.
- Cloning needs a clean recording of single notes; neural cloning needs a GPU and is not run here.
- Genre readings are uneven and none is verified by ear: hardstyle, motown and afrobeat fail the family test, acoustic
  and folk read weakly, and a dark epic does not separate from a heroic epic. Check your render with `listen.py`.
- No taqsim, alap or free improvisation: the output is metered and phrase-structured.
- Chords are equal temperament; microtonal modes use drones and sus2 chords on purpose.
- Cultural fit is a human judgement: offer a version to check with someone from the tradition.
- earshot is a model's opinion. It reads feel, instruments, pulse and tempo roughly; it cannot judge taste, melody,
  or whether a raga or maqam is correct. Its mood labels are wrong about one time in five by its own account.
- Traditional idioms are approximations with GM instruments unless the user supplies a recording.
- Nothing here is a substitute for a person listening. Say what was checked and what was not.
- The mix diagnostics measure band energy, inter-channel correlation and crest factor. They cannot hear: a WARN about
  spectral overlap, mud or intelligibility is a measurement, never a taste, and none of its thresholds is a target.
- `dynamics.engine: "dsp"` (soft knee, RMS detector, filtered sidechain, multiband, dynamic EQ) is NumPy/SciPy and slower
  than Pedalboard per stem; `scripts/mix_bench.py` prints the numbers. Its multiband split is a band-pass sum, not a
  phase-exact Linkwitz-Riley network.
- Nothing in the mixer is auditioned by its tests. A change is measured, and whether it sounds better is a person's or
  `listen.py`'s call.
- The plan's values (section loudness and density, the phrase-end breath, the one-octave lift) are starting points
  from `references/mixing/humanization.md`, not measured optima. A silence hit cuts new notes, but the reverb and
  the previous chord still ring into it, so a hush is quiet, not silent, unless the tail is cut.
- The trailer recipe's reveal fanfare at beat 66 falls inside the 38 s silence (the hush runs 65.9 to 67.4 beats).
  Move it to beat 67.5 or later if the reveal should land after the silence.

## Lessons from a long render session (cinematic cue, all deliverable formats)

| Symptom | Cause | What to do |
|---|---|---|
| A stem or bed is the wrong length, or a render of a whole piece fails after a tiny edit | an environment or SFX track's `t` and `d` are in beats, not seconds; a negative duration is accepted without a word and changes the piece's length | write times through the composer's beat helper; print the track's start and end in seconds after composing |
| Nearly every stem re-renders after one change | the piece's length changed, so each stem's cache key and random seed changed | change a length last; a track-only edit (a fade, a gain) leaves the others cached |
| A random sound source fails a row once and passes on the next render | bouts of calls, bed dips and onsets are drawn per render | fix it at the track (a bounded length, a bed that does not stop); changing the track's length redraws it; never relax the row |
| The process disappears with no error | the kernel killed it for memory (`dmesg` shows the kill) | `MUSICGEN_SFZ_WORKERS=2` for the stem stage; many-channel files are measured one channel at a time (`gate_audio.true_peak_by_channel`) |
| `fold.mono` fails by 4-5 dB around 450-1500 Hz | the two-channel master is head-filtered and the ears disagree there | `immersive.stereo_decode: "speakers"` for a loudspeaker master |
| `master.dc` fails with a loud bass | 1 s block means of a loud 80-120 Hz tone | `mastering.highpass_hz` with `mastering.highpass_order` in the mix preset |
| The gate is green and the cue sounds calm | the gate measures faults, not pressure | `scripts/helpers/arc_report.py`, then `references/scoring/cinematic-commercial-grade.md` |
