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
- The sampled bank is good, not concert-grade. Do not claim it is indistinguishable from a real orchestra.
- No sung words. Choir and "oohs" are texture only.
- Cloning needs a clean recording of single notes; neural cloning needs a GPU and is not run here.
- Genre readings are uneven: hardstyle, motown and afrobeat fail the family test, acoustic and folk read weakly, and a
  dark epic does not separate from a heroic epic. See
  `references/scoring/genres-and-moods.md` section 7a before you claim a genre works, and check your render with `listen.py`.
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
