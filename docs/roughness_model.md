# Roughness model: decision note

Facts and citations live in `knowledgebase/sound-design/roughness.md`. This note records only what was decided
for the gate, why, the measured calibration, and what is still open. Phase 1 reading is that file; Phase 2 design
is §2; Phase 3 numbers are §3.

## 1. Problems this fixes

| # | Problem in `cochlear_roughness_check` | Fix |
|---|---|---|
| 1 | `a_norm = mag / max_a` per frame: a clash at `pp` scores like the same clash at `ff` | partial level is absolute (dB SPL, calibrated against the file's own loudness), never re-normalised per frame |
| 2 | a masked partial counts at full weight | a partial under a louder partial in the same critical band is attenuated by the masking curve before it is weighted |
| 3 | pair weight `min(a1,a2) * kernel` | Vassilakis `(Amin*Amax)^0.1 * 0.5 * (2*Amin/(Amin+Amax))^3.11 * kernel` |
| 4 | one fixed limit for every passage | the new score has its own constant, calibrated from fixtures (§3); the relative limit and the 3-frame rule are kept and are not scaled by mood |

## 2. Model as implemented

Per 1 s frame, per partial `i` (selection unchanged: prominence, tonal fraction, ten loudest, 200 Hz-4 kHz):

    L_i    = 20*log10(a_i) + (calib_spl_db - LUFS_file)          # dB SPL, file-relative calibration
    z_i    = 26.81*f_i/(1960+f_i) - 0.53                          # Bark
    M_i    = max over j within mask_band_bark of L_j - slope*|z_i - z_j|
             slope = 10.5 dB/Bark when f_i > f_j (masking spreads upwards),
                     27 dB/Bark when f_i < f_j
    atten  = max(0, M_i - L_i)                                    # dB pushed under the mask
    heard  = clip((L_i - ATH(f_i)) / 10, 0, 1)                    # 0 at the absolute threshold, 1 by 10 dB SL
    A_i    = heard * 10**((L_i - 94 - atten)/20)                  # amplitude above 1 Pa, mask-attenuated

    pair   = 0.5 * (Amin*Amax)**0.1 * (2*Amin/(Amin+Amax))**3.11 * Z(f1, f2)

Frame value = mean of the three strongest pairs (unchanged). A partial at or below its threshold has `A = 0`, so
its pairs contribute nothing; that is the "near the threshold, ~0" behaviour, with no invented sigmoid.

Profile parameters (`scripts/gate_profiles.py`, row `roughness`): `model` (legacy | level_aware),
`median`, `calib_spl_db`, `mask_band_bark`, `mask_slope_up_db_bark`, `mask_slope_down_db_bark`. The existing
`scale` and `outro_resolve` are unchanged and applied identically by both models.

Kept unchanged, with the reason: the Sethares kernel (register behaviour), the 200 Hz-4 kHz band (below 200 Hz a
quarter critical band is beating, not roughness; above 4 kHz a semitone is far inside one critical band), ten
partials (a modelling cap, not a published constant), 1 s frames at 0.5 s hop (a 1 s frame holds 15-300 whole
modulation periods), the 3-frame persistence rule, the relative limit, the FAIL/WARN wording.

## 3. Calibration

Fixtures: `tests/fixtures/roughness/make_fixtures.py` - 63 synthetic tones (additive synthesis, ten partials at
1/k^1.1, three registers, three levels, seven intervals) and 12 listening pairs. No downloaded audio. Raw numbers:
`tests/fixtures/roughness/calibration.json` and `pairs.json`.

### 3.1 The limit

| quantity | value |
|---|---|
| loudest consonant voicing in the set (95th percentile of 9 triads) | 0.0207 |
| quietest semitone dyad in the set (5th percentile of 9) | 0.0201 |
| **calibrated median** (`ROUGHNESS_MEDIAN_LEVEL_AWARE`, 1.16x over the consonants) | **0.024** |
| loud semitone inside one file (the case that must fail) | 0.0347 |
| the same semitone, quiet half of that file | 0.0200 |

The two populations overlap at one corner: a quiet semitone in the top register scores 0.0201, under the limit.
Inside a piece that semitone at a normal level scores 0.0347 and fails. This is a risk (§5), not a solved case.

### 3.2 Published shape (asserted by `tests/test_roughness_model.py`)

| check | published expectation | measured |
|---|---|---|
| unison | ~0 | 0.0014 (legacy 0.0011) |
| peak separation at 1000 Hz | about 1/4 critical bandwidth (Plomp & Levelt) | 30.4 Hz = 0.19 CB (CB 162 Hz) |
| peak separation at 220 Hz | quarter CB, i.e. beating territory | 14.9 Hz = 0.14 CB |
| peak separation at 2093 Hz | quarter CB | 73.1 Hz = 0.23 CB |
| fall by one CB at 1000 Hz | far below the peak | 0.0028 vs peak 0.0315 |
| level inside one file | rises with level (~3x per 40 dB, Zwicker & Fastl) | 0.0200 (pp) -> 0.0347 (ff), ratio 1.74 |
| masking | a partial under a louder partial in the band is attenuated | 0.0313 -> 0.0070 (legacy 0.0939 -> 0.0379) |

The level ratio measures 1.74x per 24 dB, between the bare Vassilakis `X^0.1` term (about 2% per 10 dB) and
Zwicker & Fastl's 3x per 40 dB; the masking attenuation and the audibility ramp supply the difference.

### 3.3 Legacy vs new

This checkout holds **one** finished master (`master_v01.wav`); there are no six completed projects to re-run, so
the cross-cue comparison is the fixture set plus that one real cue.

| cue | legacy mean / max | level-aware mean / max | verdict change |
|---|---|---|---|
| `master_v01.wav` | 0.0433 / 0.1221 -> FAIL | 0.0070 / 0.0265 -> WARN | **FAIL -> WARN** (risk 1) |

The 12 listening pairs (scores A / B, ordering):

| pair | new A / B | new | legacy A / B | legacy |
|---|---|---|---|---|
| 01 semitone 262, pp vs ff | 0.0181 / 0.0314 | B | 0.0939 / 0.0939 | same |
| 02 semitone 523, pp vs ff | 0.0161 / 0.0279 | B | 0.0914 / 0.0914 | same |
| 03 semitone 1046, pp vs ff | 0.0116 / 0.0201 | B | 0.0727 / 0.0726 | same |
| 04 M2 440, pp vs ff | 0.0092 / 0.0160 | B | 0.0565 / 0.0565 | same |
| 05 m3 262, pp vs ff | 0.0098 / 0.0171 | B | 0.0520 / 0.0520 | same |
| 06 P5 262, pp vs ff | 0.0024 / 0.0042 | B | 0.0105 / 0.0105 | same |
| 07 semitone low vs high | 0.0334 / 0.0206 | A | 0.0976 / 0.1072 | B |
| 08 semitone masked vs not | 0.0313 / 0.0070 | A | 0.0939 / 0.0379 | A |
| 09 cluster vs triad | 0.0347 / 0.0092 | A | 0.1598 / 0.0327 | A |
| 10 semitone over noise vs alone | 0.0313 / 0.0331 | B | 0.0939 / 0.1001 | B |
| 11 semitone octave-masked | 0.0313 / 0.0024 | A | 0.0939 / 0.0070 | A |
| 12 semitone vs tritone | 0.0313 / 0.0119 | A | 0.0939 / 0.0337 | A |

Changed orderings: pairs 1-6 were "same" under legacy (the level bug) and are "B" (the loud half) under the new
model. Pair 7 flipped from "high is rougher" to "low is rougher": a semitone inside a 316 Hz critical band is
further from the quarter-band peak than one inside a 103 Hz band, so the legacy answer was the wrong one. Pairs
8-12 keep their ordering with much larger margins.

## 4. What was not changed

- Kernel, band, partial cap, framing, persistence rule, relative limit, `scale`, `outro_resolve`, wording.
- No mood / section-role scaling (no source supports one).
- `references/` and `AGENTS.md` were not edited; the lines that are now wrong are listed in §6.
- The default stays `legacy`, so no existing piece changes verdict.

## 5. Risks

1. **A delivered master changed from FAIL to WARN.** `master_v01.wav` had a sustained legacy clash
   (max 0.1221, median 0.0433); the new model sees one spike above the limit (max 0.0265) and reports a WARN.
   Either the legacy FAIL was a transient the persistence rule inflated, or the new model under-scores a real
   clash. Nobody has listened to that moment, so it is unresolved - the strongest reason the default stays
   `legacy`.
2. **Population overlap** at the quiet / top-register corner (§3.1): the limit comes from the consonant
   population, not from a perceptual boundary.
3. **Per-file loudness calibration**: the model cannot compare two separately delivered files at different
   loudness. It is a per-piece gate by design.
4. **Calibrated, not derived**: `calib_spl_db = 70`, the 10 dB audibility ramp and the 1.16x margin are choices,
   labelled as such in the knowledge-base file.
5. **Masking slopes are constants** (10.5 and 27 dB/Bark) from one worked example in Daniel & Weber; the real
   upper slope varies with level.

## 6. Doc lines that are now wrong (not edited, per the task)

- `references/mixing/quality-gate.md:189` - describes `cochlear_roughness` as the Plomp-Levelt kernel with
  per-frame normalisation. That is now only the `legacy` model; the row can also run `level_aware` (level,
  masking, Vassilakis terms). Needs a sentence and a pointer to `knowledgebase/sound-design/roughness.md`.
- `references/mixing/quality-gate.md:157`, `:167` - alias and no-skip lists are still correct, but the row now
  has seven parameters; a reader looking for the knobs will not find `model`, `median`, `calib_spl_db`,
  `mask_*` there.
- `AGENTS.md:178` - still correct (row cannot be skipped).
- `AGENTS.md:190` - "Avoid semitones against sounding notes (causes roughness)" now has a citation in the
  knowledge-base file; a pointer, not a change.

## 7. Reproduce (PowerShell)

```powershell
cd <repo>
.venv\Scripts\python.exe tests\fixtures\roughness\make_fixtures.py        # calibrate + write wav/ and pairs/
.venv\Scripts\python.exe -m pytest tests\test_roughness_model.py -q
.venv\Scripts\python.exe -m pytest tests\test_gate_profiles.py tests\test_gate_ambient.py -q
.venv\Scripts\python.exe scripts\gate_profiles.py rows
.venv\Scripts\python.exe scripts\gate_profiles.py check
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'scripts'); import naturalness_check as nc; [print(m, nc.cochlear_roughness_check('master_v01.wav', model=m)[1]) for m in ('legacy','level_aware')]"
.venv\Scripts\python.exe tests\check_kb.py
```

## 8. Status

`roughness.model` remains `legacy`. The new model becomes the FAIL/WARN source only when
`docs/roughness_listening_sheet.md` comes back with at least 10 of 12 answers matching the model's ordering.
