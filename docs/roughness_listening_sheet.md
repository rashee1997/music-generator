# Listening sheet: roughness model (owner's answers needed)

The agent cannot hear. This sheet is the last step before `roughness.model = "level_aware"` may become the
default; until you answer it, the gate stays on `legacy` and the new model is only a profile option.

## What to do

1. Generate the files (they are git-ignored audio): `python tests/fixtures/roughness/make_fixtures.py --pairs`
2. Listen on headphones at a comfortable, unchanged volume. Do not change the volume between A and B of a pair.
3. For each pair write `A`, `B` or `same` in the last column: which one sounds **rougher** (buzzing, harsh,
   gritty - not "louder", not "more dissonant").
4. Send the completed sheet back. The switch happens when your answers agree with the model's ordering on at
   least 10 of the 12 pairs.

Files are in `tests/fixtures/roughness/pairs/`, named `<pair>_A.wav` and `<pair>_B.wav`.

## Pairs

| # | Pair | What differs between A and B | Your answer |
|---|---|---|---|
| 1 | `01_semitone_262_pp_vs_ff` | the same semitone (262 Hz + 277 Hz), quiet half vs loud half of one performance | |
| 2 | `02_semitone_523_pp_vs_ff` | the same semitone at 523 Hz, quiet vs loud | |
| 3 | `03_semitone_1046_pp_vs_ff` | the same semitone at 1046 Hz, quiet vs loud | |
| 4 | `04_M2_440_pp_vs_ff` | a major second at 440 Hz, quiet vs loud | |
| 5 | `05_m3_262_pp_vs_ff` | a minor third at 262 Hz, quiet vs loud | |
| 6 | `06_P5_262_pp_vs_ff` | a perfect fifth at 262 Hz, quiet vs loud | |
| 7 | `07_semitone_low_vs_high` | a semitone at 220 Hz vs the same semitone at 2093 Hz, same level | |
| 8 | `08_semitone_masked_vs_unmasked` | a semitone alone vs the same semitone with a much louder note in the same critical band | |
| 9 | `09_cluster_vs_triad` | a three-note semitone cluster vs a consonant triad, same level | |
| 10 | `10_semitone_bed_vs_alone` | a semitone alone vs the same semitone over a quiet noise bed | |
| 11 | `11_semitone_octave_masked` | a semitone vs the same semitone with one note doubled an octave louder | |
| 12 | `12_semitone_vs_tritone` | a semitone vs a tritone, same level | |

## Notes on how these were made

- All tones are additive synthesis: a ten-partial harmonic series (1/k^1.1), identical timbre in every file.
  Nothing was downloaded; no copyrighted recording is involved.
- In pairs 1-6, A is the quiet half and B the loud half of one 8 s file. The model's own numbers here come from
  the frames of that one file: it calibrates level against the file's integrated loudness, so two separate files
  played at matched loudness are equal by design, and only a change of level inside a piece is visible to it.
- Pairs 1-6 therefore also test whether that design choice matches your ear: if you hear no roughness difference
  between quiet and loud at the same playback volume, the model's level term is too strong.

## What happens with your answers

- 10+ agreements: the default flips to `level_aware` in `scripts/gate_profiles.py`, and the model becomes the
  FAIL/WARN source with the legacy number kept as the INFO row.
- Fewer than 10: the model stays experimental and the disagreements are used to re-derive the level term and the
  masking slopes before a second round.
