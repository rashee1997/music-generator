---
title: Blending and balance
summary: The mix-preset keys that decide gain staging, ducking and spectral balance, and what each one does.
tags: [mix, balance, ducking, sidechain, eq, gain, preset keys]
load_when:
  - writing or fixing a mix preset
  - one part is inaudible or masks another
---

# Blending and balance (any music)

How a human mixer makes layers sound like one piece. Applies to ambient, pop, film, game, anything. Sources: Salivity "Layering Field Recordings Under Ambient Beds", Sound On Sound "Depth of Field" (Heimer, 2025), SonusGearFlow "Designing Ambiences" (2026). Full notes: a project's `reports/research_mixing_blend.md`.

## Rules, and the score key that does each

| Rule | Key (per track) |
|---|---|
| Beds sit behind: high-pass 100-200 Hz, gentle low-pass 5-8 kHz | `hp`, `lp` |
| Nothing starts or stops with a click or a jump | `fade_in_s`, `fade_out_s` (sine-squared) |
| Environment tracks get an automatic +3 dB swell at the intro and outro. Turn it off when it sounds like a surge | `intro_outro_boost_db: 0` |
| The bed gives way under the lead, slowly | `duck_by`, `duck_db` (-3 to -6), plus the static carve |
| One shared room; depth from send level, not from different reverbs | score `room`, track `reverb`; far sources wetter and darker (`spatial.distance`) |
| Same perspective for everything: a close, dry event over a distant bed sounds like a collage | give every layer a `reverb` and `spatial` that agree |
| Events narrower than the bed, important ones near the centre | `width`, `spatial.azimuth` |
| Bass and pads must not out-shout the lead | the `balance` gate: bass/drum +6 dB, chord/pad/counter/arp +3 dB over the lead is the most allowed (WARN +3, FAIL +6 beyond that) |

## Order of work
1. Set levels by role (bass under the lead, beds under everything) before touching EQ.
2. Add fades to every layer that starts or ends inside the piece.
3. Cut the bed's low end and top end; narrow-cut where the pad and a bed fight.
4. Duck beds under the lead; keep release over 0.5 s so it breathes.
5. Run the gate. `balance` FAIL means the stem is too loud: lower `gain_db` by the amount it prints. Do not loosen the gate.

## Mix preset (required for every piece)

The gate FAILS a score with no custom mix preset. Do not use `default`, and do not copy it. Follow these steps in order:

1. Scaffold: `python scripts/presets.py scaffold mix <name>` (in a project it lands in `<project>/presets/mix/<name>.json`).
2. Fill `character`: one sentence saying what this music is (genre, mood, density) and why the mix suits it.
3. Set only the values that differ from the default. Pick from this table by the music's character. The scaffold also
   writes out the full `role_chains` (one EQ + compression chain per role) and `spectral.profiles` (rain, water, wind,
   foliage, insect, voice, strings, flute, bed): edit the one entry a source needs, or set `"spectral_profile"` on that
   track's preset to choose one by name. Two strings instruments that need different low-mid treatment are two edited
   chains, not one role.

| Character | `level_by_role` (dB) | `lead_band_hz` | `carve_db` | `widen_by_role` |
|---|---|---|---|---|
| Sparse ambient / nature | bass -13, pad -11, chord -10, melody -3 | 1500-2000 | -3 | pad 0.35 |
| Dense pop / rock / dance | bass -6, drum -7, chord -8, melody -3 | 2500-3500 | -4 to -6 | pad 0.2 |
| Orchestral / cinematic | pad -10, chord -9, bass -8, melody -3 | 1800-2500 | -3 | pad 0.4, chord 0.3 |
| Lo-fi / chill | bass -8, chord -9, melody -4 | 1200-2000 | -3 | chord 0.2 |
| Solo or small acoustic | melody -2, chord -8, bass -9 | 2000-3000 | -2 | none |

   Also set `inst_eq`, `seating` or `saturation` when an instrument in this piece needs it.

   The engine's strategies are mix-preset keys too, and every default is the behaviour this engine already had. Change one
   only when this piece needs it, then re-measure:

   | Key | Default | When to change it |
   |---|---|---|
   | `gain_staging.strategy` | `legacy` (playing part to -24 LUFS, boost capped) | `adaptive`: a per-role reference, a cut limit, a peak-headroom cap and a crest guard, so a delicate layer, a percussion stem and a field recording keep their own dynamics |
   | `dynamics.engine` | `pedalboard` (threshold/ratio/attack/release) | `dsp`: adds `knee_db`, a peak/RMS `detector`, a filtered sidechain, `lookahead_ms`, `parallel`, `multiband`, `dynamic_eq` and `transient`, per track or for the whole preset |
   | `spectral.max_auto_cut_db` | `0` (no clamp) | set `3` to bound the automatic lead carve |
   | `space.auto_env_blend` | `on` | `off` when the instruments should stay dry next to an ambience bed |
   | `sidechain.mode` | `legacy` (a bed ducks under the first drum track) | `explicit` (only what a track's `duck_by` asks for) or `off` |
   | `mastering.profile` | `default` (-14 LUFS, -1.5 dBTP) | a named profile in `mastering.profiles` (`streaming`, `podcast`, `broadcast`, `cinema`); the score's own `master` block always wins over it |
   | `automation.curve` | `linear` | `cosine` or `exponential` for the track fades |

   `python scripts/presets.py validate` rejects an unknown mix key or an out-of-range value, and `python scripts/presets.py
   show mix default` prints every key with its shipped value. A single track can also carry `spectral_profile`,
   `preserve_spectrum`, `ref_lufs`, `dynamics` or `pan_law`. Full detail: `references/mixing/mixing-and-mastering.md` section 8b.
4. Add `"mix_preset": "<name>"` to the score.
5. Run the pipeline. A `balance` FAIL prints how many dB to lower a track; change that preset value or the track's `gain_db`.

Gate rows: `mix_preset` (exists, has a `character`, differs from default) and `balance`. The mixing diagnostics
(`mixer.py --diagnose`, `mix_and_master(..., diagnose=True)`) are **not** gate rows: they report and never change the mix,
so a WARN there is a question you answer in the preset or in STATUS.md, not a row to satisfy.

## Not covered yet (say so in the reply)
Frequency-selective ducking is researched but not built. Distance-dependent reverb pre-delay is in the project's space preset (`distance.pre_delay_law`); the chopped-note check is the `modulation_flutter` row (WARN only). The `balance` check uses plain RMS, not K-weighted loudness.
