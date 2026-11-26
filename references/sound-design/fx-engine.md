---
title: Effects chains for a stem (fx_engine)
summary: Cinematic and creative effects on a stem, the Pedalboard-style chain that holds them beside built-in Pedalboard plugins, and how a chain is declared, checked and cached.
tags: [fx, effects, pedalboard, riser, downlifter, tape stop, doppler, freeze, shimmer, reverse reverb, cinematic, chain]
load_when:
  - a brief asks for a riser, a downlifter, a tape stop, a reverse swell, a freeze, a pass-by or any other treatment of a part
  - an instrument preset needs an effects chain
  - an fx row or a chain preset fails
---

# Effects chains for a stem

`scripts/fx_engine/` is the effects library. A chain is sound design, so it lives in an **instrument preset** as `fx`
(`presets/instruments/<name>.json`), never in the score. The mixer runs it on the stem after the EQ and dynamics and before
the low-end hygiene and the level, so the gain staging and the room send see the result.

## Why this is not a Pedalboard plugin

Pedalboard cannot host a plugin written in Python: its `Plugin` is an abstract class in C++, and a Python subclass cannot be
put in a `Pedalboard`. So each effect here is a function, the chain runs them in order, and the same chain can name

- `pedalboard`: any built-in Pedalboard plugin on the allow-list (Chorus, Phaser, Delay, Reverb, Distortion, Bitcrush,
  LadderFilter, PitchShift, the filters, Compressor, Limiter, NoiseGate and the rest), with its constructor arguments;
- `external`: a real VST3 or Audio Unit file on disk, loaded through Pedalboard, its parameters set by name. This is the way
  to add a compiled third-party effect. It needs the file on the machine; nothing else in the chain does.

`fx_engine.Board(chain)` has the Pedalboard call shape (channels, samples in and out) for code that wants to treat a chain as
one object.

## Declaring a chain

In an instrument preset, a list of effects, or the name of a chain preset (shipped in `references/data/presets/fx/` or the
project's own `presets/fx/<name>.json`):

```json
"fx": "riser_sweep"
```

```json
"fx": [
  {"type": "filter_sweep", "kind": "lowpass", "f_start_hz": 200, "f_end_hz": 9000, "start_s": 24.0, "end_s": 32.0},
  {"type": "tape_stop", "start_s": 32.0, "dur_s": 0.8},
  {"type": "pedalboard", "plugin": "Chorus", "params": {"rate_hz": 0.4}, "mix": 0.4}
]
```

A list may also name a chain preset as one of its entries (`["riser_sweep", {...}]`). A chain preset is `{"name", "character", "chain": [...]}`; its `character` says in one sentence what the chain is for. A chain
preset may name effects but not another chain preset. Times are in **stem time** (seconds from the start of the stem).

Every effect takes these keys besides its own:

| Key | Meaning |
|---|---|
| `mix` | dry/wet blend of the effect, 0 to 1 |
| `start_s`, `end_s` | where it acts; no `end_s` means the end of the stem |
| `edge_ms` | raised-cosine crossfade at both ends of the range, so nothing steps in or out |
| `seed` | an effect's own random seed, added to the stem's (a render repeats exactly) |

An unknown effect, an unknown key, a number out of range, a wrong type and an `end_s` before `start_s` are errors that list every
problem of the chain together. Run `python -c "import fx_engine; print(fx_engine.describe())"` from `scripts/` for the table
of effects and ranges, or read `references/data/presets/fx/effects.json`, which is the one place the names, parameters, ranges
and defaults are written.

## The effects

| Effect | What it does | Main parameters |
|---|---|---|
| `tape_stop` | playback slows to a halt, level following, silence after | `dur_s`, `curve`, `level_pow` |
| `pitch_glide` | a pitch dive or riser over the range | `semitones`, `curve` |
| `doppler` | a pass-by: delay is path length over the speed of sound, level is closest over distance | `closest_m`, `speed_m_s`, `pass_s`, `c_m_s` |
| `tape_wobble` | wow and flutter set in cents | `wow_hz`, `wow_cents`, `flutter_hz`, `flutter_cents` |
| `stutter` | beat repeat of the first slice of the range | `slice_ms`, `decay_db` |
| `freeze` | spectral hold of the sound at `start_s` as a phase-randomised wash | `hold_s`, `fft` |
| `grain_cloud` | grains read near their own time, scattered in pitch and place | `grain_ms`, `density_hz`, `pitch_spread_cents`, `pos_spread_s`, `level_db` |
| `filter_sweep` | a filter whose cutoff glides between two frequencies (riser, downlifter) | `kind`, `f_start_hz`, `f_end_hz`, `q`, `curve`, `after` |
| `ring_mod` | multiplication by a sine: metallic and robotic colour | `freq_hz` |
| `tremolo` | level dips; auto-pan with `pan_depth` | `rate_hz`, `depth`, `pan_depth` |
| `gate_pulse` | a rhythmic gate | `rate_hz`, `duty`, `floor_db`, `smooth_ms` |
| `transient` | sharpen or soften the front of a note, lift or tuck its body | `attack_db`, `sustain_db` |
| `reverse_swell` | a reverse reverb: a swell that builds into each note | `decay_s`, `wet_db` |
| `shimmer` | a reverb tail pitched up and fed back | `shift_semitones`, `feedback`, `iterations`, `wet_db` |
| `pedalboard` | a built-in Pedalboard plugin | `plugin`, `params` |
| `external` | a VST3 / Audio Unit file | `path`, `params` |

Physical relations are derived from the parameters and not looked up: the Doppler delay and level come from the straight path
(the speed of sound is the active medium's, `phys_core.medium`, unless `c_m_s` says otherwise), and a wow of `cents` at `f` Hz
needs a delay swing of `cents * ln2 / 1200 / (2 pi f)` seconds.

## Shipped chains

Starting points, each a short chain preset; copy one into the project and set its times to the cue.

| Chain | For |
|---|---|
| `riser_sweep`, `downlifter` | the build into a hit and the release after it |
| `tape_stop_out` | a power-failure cut-out on a held part |
| `reverse_build` | the pre-hit suck of a trailer |
| `shimmer_tail`, `dream_chorus` | an ethereal bloom behind a part |
| `freeze_hold`, `impact_tail` | time stopping on the frame; the tail after a hit |
| `sci_fi_pass` | a craft passing close |
| `lofi_tape`, `lofi_8bit`, `telephone`, `megaphone`, `underwater` | a character for a whole part |
| `trance_gate`, `granular_haze` | a chopped pad; a soft cloud under a theme |

## Where a chain meets a hard cut

A cue that stops dead on a frame is a direction-sheet hit (`quality-gate-rows.md` section 8), and the renderer already ramps
the sustained voices there. A `tape_stop` or `downlifter` is the other way to end a part: a slow-down instead of a stop. Use one
or the other on a part, not both at one moment.

## Rules and checks

- **Checked before the render.** Stage 2 runs `preflight.fx` on every track's chain (an invalid one is a FAIL naming each
  problem), and `presets.py validate` checks the library and every chain preset. A chain in the score is blocked by the project
  gate: move it to the instrument preset.
- **Cached by content.** The mixer writes the chain into the track's spec with every parameter filled in, so a change to a chain
  preset or to a library default changes the key of the processed stem; the package is part of the code identity. A chain
  edit does not redraw the dry stems.
- **Repeatable.** Randomness is seeded from the stem's name, the effect's position and its own `seed`.
- **Levels move.** An effect can change a stem's level. The gain staging ran before the chain, so listen for balance and read
  the balance rows after adding one; never loosen a row to hide a loud chain, lower the effect's `mix` or `wet_db`.
- **Project values.** To change a default for a project, write an `effects.json` in the project's `fx` preset folder holding `{"name": "effects",
  "effects": {"tape_stop": {"params": {"dur_s": {"default": 2.0}}}}}`: it is merged over the shipped library one value at a time.

## Limits

- Every default and range is a starting value (`provenance` in the library file), not a measurement.
- The effects work on a whole stem offline. They are not real-time and not sample-accurate to a host's automation.
- The shimmer and the transient shaper depend on Pedalboard's pitch shifter and the repository's own envelope followers; the
  freeze is a phase-randomised resynthesis, so it has no transient of its own.
- A `doppler` pass is a treatment of the stem. It does not place the sound in the room: the placement and the room still come
  from the part's `spatial` block and the space preset.
- `external` is loaded through Pedalboard and was exercised in tests with a stand-in plugin object; a real VST3 was not run.
- Nothing here has been auditioned unless `listen.py` ran.
