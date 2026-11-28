---
id: mixing-techniques
title: Mixing techniques, conventional and unconventional, and where each lives in the engine
domain: sound-design
status: unverified
sources: [musicradar_10_essential_eq_dynamics, musicradar_parallel_compression, musicradar_weird_production_tricks, musicradar_creative_dynamics, izotope_4_unlikely_mixing_techniques, sonarworks_midside_compression, fiveable_dynamic_mix_techniques, sound_on_sound_scoring_stage_depth, cinemontage_scoring_mix]
used_by: [scripts/fx_engine/mixfx.py, references/data/presets/fx/effects.json, scripts/mix_schema.py, scripts/mix_engine/placement.py, scripts/mix_engine/mastering.py, references/mixing/mixing-and-mastering.md]
updated: 2026-11-28
---

> **Not verified.** The pages behind the sources were not opened: each statement is what a search result said about its page. Every number
> in `effects.json` for these effects is a starting value, not a measurement, and nothing here says how a mix sounds.

# Mixing techniques and the engine

## 1. What the search results said

| Technique | What a result said (summary) | Source id |
|---|---|---|
| Parallel (New York) compression | Blend a heavily compressed copy with the clean signal: it works from the bottom up and avoids the crushing of top-down compression; used on beats, bass, vocals and the master bus; better on its own bus than with a plugin's wet/dry knob | musicradar_parallel_compression, musicradar_10_essential_eq_dynamics |
| Upward compression, mid-side compression | Named as advanced dynamic control; mid and side can take different amounts of compression (a heavy kick in the centre without touching wide overheads) | fiveable_dynamic_mix_techniques, sonarworks_midside_compression |
| Mono lows, bright sides | Keep the low end mono below about 200 Hz and brighten the sides with mid-side EQ | musicradar_10_essential_eq_dynamics |
| De-essing | Sibilance sits around 4-7 kHz; boost the top with EQ and let a de-esser control the harshness it creates | fiveable_dynamic_mix_techniques |
| Ducking | A sidechain compressor can duck one element under another, e.g. bass on each kick; filtering the trigger changes the pump | musicradar_creative_dynamics, musicradar_weird_production_tricks |
| Distortion on a return | Put distortion after a reverb or delay on an aux and duck it with the dry signal, so some clean sound remains in the smashed tail | musicradar_weird_production_tricks |
| Parallel distortion on notes | Blend parallel distortion over certain bass notes so they poke above the cleaner ones | musicradar_weird_production_tricks |
| Reverb on a bus | Reverb on a submix, often before compression, is an overlooked technique | izotope_4_unlikely_mixing_techniques |
| Gates and expanders | Gates combined with pitch shifting or modulation make evolving textures; frequency-dependent gating is an advanced option | fiveable_dynamic_mix_techniques |
| Scoring-stage depth | Pre-delay keeps reverb from smearing the source; roll off the top of the reverb early; early reflections alone make a short, intimate space; film mixers use more room than a concert mix so the music sits behind dialogue | sound_on_sound_scoring_stage_depth, cinemontage_scoring_mix |

**Not found:** tape saturation, delay throws and level riding were not covered by these results; frequency shifting, resonator banks, mid-side
saturation and spectral gating were not covered in depth. The engine's versions of them below are this project's own, from general practice.

## 2. Where each one is in the engine (all of it JSON)

Every technique is an effect of `scripts/fx_engine/` (`mixfx.py`), declared in `references/data/presets/fx/effects.json` with a default, a range, a
unit and a sentence, so a preset states a number and the engine checks it. A chain goes in an instrument preset (`fx`), in the mix preset's `fx`
table (`"*"`, `"@<role>"` or an instrument name), in the mix preset's `mastering.fx` (the summed master), or as a shipped chain preset
(`mix_*`). Any of them can take `automate` (a parameter that moves) when its library entry says `automatable`.

| Effect | Does | Main parameters |
|---|---|---|
| `saturator` | six characters (tube, tape, soft_clip, hard_clip, fold, diode), 4x oversampled, level-matched | `mode`, `drive_db`, `bias`, `ceiling_db`, `tone_hz` |
| `de_esser` | split-band: only the sibilant band is reduced | `freq_hz`, `q`, `threshold_db`, `ratio`, `max_cut_db` |
| `gate` | a downward expander with a hold | `threshold_db`, `ratio`, `range_db`, `hold_ms`, `sidechain_hp_hz` |
| `parallel_comp` | a squashed copy added under the original; `mix` is the blend | `threshold_db`, `ratio`, `makeup_db`, `hp_hz` |
| `upward_comp` | lifts what is under the threshold, up to a limit, not under a floor | `threshold_db`, `ratio`, `max_gain_db`, `floor_db` |
| `band_width` | mono below a corner, the side signal scaled above it | `mono_below_hz`, `width` |
| `tilt_eq` | a spectral tilt about a pivot | `tilt_db`, `pivot_hz` |
| `freq_shift` | every partial moves by the same number of Hz (not a pitch shift) | `shift_hz`, `spread` |
| `resonator_bank` | narrow resonances on the piece's own notes | `pitches`, `q`, `level_db`, `partials` |
| `ping_delay` | filtered ping-pong echoes, ducked by the dry signal | `time_ms`, `feedback`, `duck_db`, `wet_db` |

Shipped chains: `mix_vocal_air`, `mix_new_york_drums`, `mix_tape_glue`, `mix_mono_low_wide_top`, `mix_ducked_echo`, `mix_key_air`, `mix_tight_gate`,
`mix_lift_tails`, `mix_inharmonic_pad`, `mix_fold_grit`, `mix_pulse_dark`.

## 3. Rules the engine keeps

- A technique can change a stem's level; the gain staging ran before the chain. After adding one, read the balance and loudness rows; never loosen
  a row to hide it, lower the effect's `mix`.
- The saturator is level-matched by default (`match_level`): a saturation is a colour, not a gain.
- A compressor, de-esser or gate follows a 1 kHz control curve, so a change of one stem is repeatable and cached by its content.
- Nothing here has been listened to. The tests (`tests/test_mixfx.py`) measure each effect on a signal built to show it (harmonic orders, band
  reduction, the room between notes, a lifted tail, a side signal, a shifted partial, an echo time); they do not say it sounds good.
