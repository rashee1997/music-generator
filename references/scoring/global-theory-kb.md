---
title: Global theory
summary: Scales, modes and microtonal material across traditions, with the notes and intervals to use.
tags: [scale, mode, raga, maqam, microtonal, interval, key]
load_when:
  - choosing a scale outside major and minor
  - writing in a non-Western mode
---

# Global music theory knowledge base: what the skill uses, what was added, what does not hold


## 1. Where each pillar lives in the skill

| KB pillar | Where it is in the skill | Status |
|---|---|---|
| Pitch and modes (raga, maqam, Japanese, Chinese, African, Western) | `world.py` section 1 (`MODES`, `MICRO`), `theory.py` (`MODES`) | Covered. 55 KB scales map to existing shapes (table 2); 3 shapes added |
| Rhythm cycles (tala, iqa'at, bell, samai) | `world.py` section 5 (`CYCLES`) | Covered, plus 4 added (table 3) |
| Articulation (gamaka, meri, strum spread, phrase arch) | `theory.py` helpers (new), `humanize.py` (strum spread, phrase arch) | Strum and arch covered; gamaka, meri, guzheng sweep added |
| Fusion laws (common tones, one pulse, spectral slots, call and response) | `references/scoring/genre-fusion.md`, `references/workflow/creative-composition.md` section 3, `theory.pentatonic_spine` (new) | Laws 1 to 4 in `genre-fusion.md`; Law 1 spine is code |
| Situational mapping (scene to mode, tempo, groove) | `references/workflow/scene-recipes.md`, `references/scoring/genres-and-moods.md`, `world.GENRES` | Covered by the earlier passes |
| Six golden rules (naturalness) | `humanize.py`, `pattern_audit.py`, `naturalness_check.py` | Partly enforced (section 5) |

## 2. KB scale names and where they live in the skill

Most KB names already exist in the skill under another name, or as a shape with a different name. Compare by the
interval set, not the name: the skill's `MODES` stores semitones, and the same set can have several names.

| KB name | Skill name (same interval set) | Note |
|---|---|---|
| `raga_sankarabharanam` | `raga_shankarabharanam` | spelling |
| `raga_charukesi` | `raga_charukeshi` | spelling |
| `raga_keeravani` | no name; same set as `maqam_nahawand`, `harmonic_minor` | shape exists, no name in the skill |
| `raga_hindolam` | no name; same set as `raga_malkauns` | **conflicts** with `raga_hindol` in the skill (different set); pick one, never both |
| `raga_suddha_dhanyasi` | same set as `chinese_yu`, `andean_minor` | |
| `raga_simhendramadhyamam` | same set as `hungarian_minor` | |
| `african_kora` | same set as `raga_harikambhoji`, `mbira_mixolydian` | |
| `african_pent_major` | `african_pentatonic` | |
| `african_desert_blues` | same set as `chinese_yu`, `andean_minor` | |
| `ethiopian_tizita_maj` | `ethiopian_tizita_maj` | **added** |
| `ethiopian_tizita_min` | same set as `hirajoshi` | |
| `ethiopian_bati` | `ethiopian_bati` | **added** |
| `ethiopian_ambassel` | same set as `miyako_bushi` | |
| `maqam_hijaz`, `_hijaz_kar`, `_bayati`, `_rast`, `_saba`, `_nahawand`, `_kurd`, `_nikriz`, `_ajam` | same names | all present |
| `japanese_hirajoshi`, `_insen`, `_miyakobushi`, `_iwato`, `_yo`, `_ryukyu` | `hirajoshi`, `insen`, `miyako_bushi`, `iwato`, `yo`, `ryukyu` | the skill drops the `japanese_` prefix |
| `chinese_gong`, `_shang`, `_jue`, `_zhi`, `_yu` | same names | present |
| `chinese_yayue`, `_qingyue`, `_yanyue` | same sets as `raga_yaman`/`lydian`, `raga_bilawal`, `raga_khamaj` | 7-tone sets; no separate names |
| `western_ionian`, `_dorian`, `_phrygian`, `_lydian`, `_mixolydian`, `_aeolian` | `ionian`, `dorian`, `phrygian`, `lydian`, `mixolydian`, `aeolian` | the skill drops the `western_` prefix |
| `western_harmonic_min`, `_melodic_min`, `_blues`, `_whole_tone` | `harmonic_minor`, `melodic_minor`, `blues`, `whole_tone` | |
| `western_octatonic` | `western_octatonic` | **added** |

## 3. KB rhythm cycles

| KB item | Skill | Note |
|---|---|---|
| Adi tala 4+2+2 (8 beats) | `adi_8` (added) | accents on 1, 5, 7 |
| Rupaka tala (3 beats, 1 + 2) | `rupaka_3` (added) | the KB's grouping. Carnatic rupaka is 3 beats; check the grouping against a source before relying on it |
| Rupaka 6 beats | none | not standard; the KB's "3 or 6" is unclear |
| Khanda chapu 2+3, misra chapu 3+4 | `kanda_chapu`, `misra_chapu` | present |
| Samai thaqil 10/8, 3+2+2+3 | `samai_thaqil` (added) | in a 5-beat bar, as the KB maps it |
| West African 12/8 bell | `gankogui_12_8` (added) | 7 strokes on the 12 grid |
| Maqsum, baladi, saidi, malfuf | same names | present |
| Dum/tak/ka/riq, taiko, ghatam, mridangam, bendir, daf, talking drum | same names | all present in `soundbank` |

## 4. Helpers added to `theory.py`

| Function | What it does | KB section |
|---|---|---|
| `pentatonic_spine(scale)` | the 5-note subset of a scale that an accompaniment can share with any lead | 7, Law 1 |
| `apply_gamaka(notes, tonic_pc, rng)` | Sa and Pa stay pure; a 1 to 3 semitone step gets a slide from below (`gl` cents) | 1D |
| `apply_meri(notes, breath)` | shakuhachi scoop on notes of 1 beat or more, and a breath gap at the end | 4C |
| `guzheng_sweep(t0, dur, tonic, scale, direction, octaves)` | a run through a scale over two octaves | 5B |

Three of the four are covered by `tests/test_world_integrity.py`: the spine on a hijaz set, Sa and Pa left alone and a glide on the
step in the gamaka, and the sweep's length, order and first pitch. `apply_meri` has no test.

`make_arabic_iqa_bar` and `make_tihai_cadence` are left out: the skill's cycle engine (`cycle_notes`) does the
same job from the cycle table.

## 5. The six golden rules: what the code checks

| Rule | Covered by | Gap |
|---|---|---|
| 1. Breath gaps for wind and bowed parts | `apply_meri` (shakuhachi only) | not enforced for ney, horn or cello. Add the gaps by hand, as in the desert piece |
| 2. Velocity arch per phrase | `humanize.py` phrase arch | covered |
| 3. Strum spread on chords | `humanize.py` `strum_ms` (4 to 22 ms by feel) | covered; the KB's 4 to 8 ms sits between `tight` (4 ms) and `natural` (10 ms) |
| 4. Register separation for shared rhythm | nothing | not enforced; set octaves and pans by hand |
| 5. Transition markers before a section change | nothing | not enforced |
| 6. Contrast before a climax | `dynamics` arc in the score | you set the dip; nothing checks it |

## 7. Limits

- No rendered test of the new helpers beyond `tests/test_world_integrity.py`. No listening test of the new cycles or scales.
- The `practice` labels mean the values are the author's approximations. The skill does not present them as sourced.
- The KB names are kept in table 2 so a user can ask for them, but the skill's own names are the ones in the code.

---
