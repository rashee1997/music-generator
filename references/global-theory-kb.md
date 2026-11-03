# Global music theory knowledge base: what the skill uses, what was added, what does not hold

Source: `global_music_theory_algorithmic_synthesis_guide.md` (in the skill folder), a user-supplied knowledge base with
five pillars: pitch, rhythm, articulation, cross-cultural fusion, and situational mapping. This file records how it maps
onto the code. Its scale table, rhythm table and helper code are the author's; the skill re-checks each claim it adds.
Nothing in the KB is cited to a source, so every new value is labelled `practice` in `world.py`.

## 1. Where each pillar lives in the skill

| KB pillar | Where it is in the skill | Status |
|---|---|---|
| Pitch and modes (raga, maqam, Japanese, Chinese, African, Western) | `world.py` section 1 (`MODES`, `MICRO`), `theory.py` (`MODES`) | Covered. 55 KB scales map to existing shapes (table 2); 3 shapes added |
| Rhythm cycles (tala, iqa'at, bell, samai) | `world.py` section 5 (`CYCLES`) | Covered, plus 4 added (table 3) |
| Articulation (gamaka, meri, strum spread, phrase arch) | `theory.py` helpers (new), `humanize.py` (strum spread, phrase arch) | Strum and arch covered; gamaka, meri, guzheng sweep added |
| Fusion laws (common tones, one pulse, spectral slots, call and response) | `references/genre-fusion.md`, `references/creative-composition.md` section 3, `theory.pentatonic_spine` (new) | Laws 1 to 4 in `genre-fusion.md`; Law 1 spine is code |
| Situational mapping (scene to mode, tempo, groove) | `references/scene-recipes.md`, `references/genres-and-moods.md`, `world.GENRES` | Covered by the earlier passes |
| Six golden rules (naturalness) | `humanize.py`, `pattern_audit.py`, `naturalness_check.py` | Partly enforced (section 5) |

## 2. KB scale names and where they live in the skill

Most KB names already exist in the skill under another name, or as a shape with a different name. Compare by the
interval set, not the name: the skill's `MODES` stores semitones, and the same set can have several names.

| KB name | Skill name (same interval set) | Note |
|---|---|---|
| `raga_sankarabharanam` | `raga_shankarabharanam` | spelling |
| `raga_charukesi` | `raga_charukeshi` | spelling |
| `raga_keeravani` | no name; same set as `maqam_nahawand`, `harmonic_minor` | shape exists, name not added |
| `raga_hindolam` | no name; same set as `raga_malkauns` | **conflicts** with `raga_hindol` in the skill (different set). See section 6 |
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
| Rupaka 6 beats | not added | not standard; the KB's "3 or 6" is unclear |
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

All four are checked in `scripts/check_world.py`: the spine on a hijaz set, Sa and Pa left alone and a glide on the
step in the gamaka, and the sweep's length, order and first pitch.

Not added: `make_western_cinematic_chord`, which the KB's situational table names but never defines. The KB's
`make_arabic_iqa_bar` and `make_tihai_cadence` are not added either, because the skill's cycle engine (`cycle_notes`)
already does the same job from the cycle table.

## 5. The six golden rules: what the code checks

| Rule | Covered by | Gap |
|---|---|---|
| 1. Breath gaps for wind and bowed parts | `apply_meri` (shakuhachi only) | not enforced for ney, horn or cello. Add the gaps by hand, as in the desert piece |
| 2. Velocity arch per phrase | `humanize.py` phrase arch | covered |
| 3. Strum spread on chords | `humanize.py` `strum_ms` (4 to 22 ms by feel) | covered; the KB's 4 to 8 ms sits between `tight` (4 ms) and `natural` (10 ms) |
| 4. Register separation for shared rhythm | nothing | not enforced; set octaves and pans by hand |
| 5. Transition markers before a section change | nothing | not enforced |
| 6. Contrast before a climax | `dynamics` arc in the score | you set the dip; nothing checks it |

## 6. Problems found in the KB (not copied into the skill)

1. **Hindolam is not the same as Hindol.** The KB's `raga_hindolam` has the Malkauns set `[0,3,5,8,10]`. The skill's `raga_hindol` is `[0,4,6,9,11]`. Both are kept. Do not treat them as one raga.
2. **Keeravani has no separate set here.** Its set matches the harmonic-minor shape. Fine as a sound, but it is not a distinct raga in this table.
3. **Rupaka** is given as "3 or 6 beats". The skill's `rupak` is the 7-beat Hindustani tala (3+2+2). They are different talas. Both names are kept.
4. **Undefined helper.** `make_western_cinematic_chord` is used in the situational table and never written.
5. **Gamaka first-note rule.** In `apply_indian_gamaka`, the random slide runs only on the first note (the `elif`). That is ported as written and marked as a shortcut in `theory.py`. It may have been meant for every note; check by ear.
6. **Unsourced claims.** The vibe words ("autumnal", "sunrise", "spiritual"), the Carnatic and Hindustani equivalences beyond the ones already sourced, and the claim that a Yo scale has "stacked 4ths" are the author's. They are not verified here.

## 7. Limits

- No rendered test of the new helpers beyond the self-checks in `check_world.py`. No listening test of the new cycles or scales.
- The `practice` labels mean the values are the author's approximations. The skill does not present them as sourced.
- The KB names are kept in table 2 so a user can ask for them, but the skill's own names are the ones in the code.

---

## How to create / use

Reference only: records how an outside theory document maps onto `world.py` / `theory.py`. There is nothing to create here; research for a new piece goes through `research_kb.py`.
