---
title: The debug engine (audio_debug)
summary: What the autopsy of a failing gate row is made of, which declared lever moves it, and when no value of one lever can clear two rows.
tags: [debug, autopsy, gate, forensics, solver, clicks, conflict]
load_when:
  - a gate row fails and the fix of one row has broken another
  - changing scripts/audio_debug or debug_audio.py
---

# The debug engine (audio_debug)

`scripts/debug_audio.py` and the pipeline's `[AUTOPSY]` line answer a different question from the gate. The gate says
*which row failed*; the autopsy says *what that row is made of, which declared lever moves it, and whether the rows it
must not break can be satisfied by the same value*. It renders nothing and changes nothing.

Written to `<project>/reports/debug_audio.md` and `.json`. Attempts are appended to `reports/debug_history.jsonl`.

## Why it exists

Fixing one row and breaking another is not bad luck, it is an under-determined problem solved one variable at a time.
Two rows can be functions of the same physical quantity with opposite slopes (a note long enough to avoid a dropout
hole is long enough to overlap the next hit; an EQ cut that removes an impulse also removes the air the equal-loudness
row wanted). Tuning one row at a time walks that trade-off blindly. The engine writes the trade-off down.

The form of the problem follows the mixing literature: a model of the measured metrics in terms of the control
parameters, then an optimiser over those parameters.

- Barchiesi & Reiss, *Automatic Target Mixing using Least-Squares Optimization of Gains and Equalization Settings*,
  DAFx-09 — parameters recovered by least squares against measured metrics.
- *The Mathematics of Mixing*, JAES 62/1 (2014) — mixing posed as a numerical optimisation over an auditory model, and
  the warning that perceptual nonlinearity needs care in the optimiser.
- Terrell & Reiss, *Automatic Monitor Mixing* — an objective plus **side constraints** (SPL limits), which is the same
  shape as a gate's pass marks.
- Luo, Yamkovoy & Garcia, *Constraint Optimized Multichannel Mixer-Limiter Design*, ICASSP 2025 — a mixer designed as a
  constrained programme over gains subject to sample-level limits.

The engine's difference is the constraint set: a gate's pass marks, several of them discrete (an impulse count, a hole
length), so the model is piecewise — continuous rows get a band-energy sensitivity, discrete rows get event
attribution.

## The method

1. **Normalise every row.** `safety = (threshold − value) / tolerance` for an "at most" row and the reverse for an
   "at least" row. Sign is the verdict; magnitude is comparable across dB, ms and event counts. A row the profile did
   not judge is `+inf` and never enters the system.
2. **Only the domains in question.** An advisory row (chemistry, virtual ears, direction) can never bind, so it is
   never analysed. A domain module is imported only when a row it owns has failed.
3. **Price each lever.** A lever is a value the presets or score actually declare — an `inst_eq` band, an instrument
   trim, an onset ramp, a note length, a placement, a reverb send, a ceiling, oversampling. Its coefficient on a row is
   the row's own physics: for a band row, the share of the row's band energy the EQ band covers; for an impulse row,
   the share of the transient its stem owns; for a placement row, one degree per degree.
4. **One programme, not one knob.** Maximise the worst safety over all judged rows subject to each lever's bounds
   (`scipy.optimize.linprog`, HiGHS). If a solution exists it improves every row it touches and pushes none past its
   limit, so the next render cannot trade one failure for another. Moves are snapped to the format's granularity and
   re-evaluated after snapping.
5. **When it is infeasible, say why.** For every lever the engine computes the interval of moves that satisfies each
   of its rows on its own; an empty intersection is reported as a **conflict**, naming the rows, the move each needs
   and the interval with no solution. That is the arithmetic behind a whack-a-mole cycle, and the report says to fix
   the score, the sample or the density instead of the knob.
6. **Never propose a spent lever.** `reports/debug_history.jsonl` records what was tried and what the gate said. A
   lever that did not clear a row is burned for that row and zeroed in the system.

## Domains

| Domain | Rows | Levers |
|---|---|---|
| master | loudness, true peak, clipping, dc, silence, clicks, crest, `dropout`, `cut.hard`, `end.abrupt` | oversampling, ceiling, loudness target, trim |
| stems | `stem.*` (dead, dropout, cut, edge, clipping, dc, flatness); a failing `stem.cut` is read against the direction sheet's hard cuts (`cut_windows.py`) and says whether the drop is outside every window and how far from the nearest | that stem's trim, bands, note length, onset ramp |
| spectral | `spectral.*`, `masking.*`, ERB masking, roughness | EQ bands that overlap the row's band (a trim cannot move a ratio) |
| spatial | `spatial.*`, `imm.*` (clarity, low_fold, kinematics, route parity), `mix.*` | azimuth, elevation, distance, reverb send |
| channels | per-channel `delivery.true_peak`, `fold.*`, `layout.*`, `objects.*`, `adm.*` | master trim/ceiling, send |
| hrtf | `hrtf.*`, `binaural.*`, `imm_cues` | elevation and distance only; the filter itself is a dataset |
| chem | `chem.*` | none: advisory, cannot fail |
| ears | `ear.*` | none: advisory |
| direction | `focus`, `intent.*`, `balance.*`, `expression.*`, `orch.*` | none: the lever is the declaration or the notes |

A row with no lever is reported as **closed**, not as a failure to fix.

## Reading the report

- **In question** — the binding rows with their numbers, plus the attribution of a transient or a hole to a stem.
- **Proposed** — the moves and the predicted safety before/after. First-order, so the next render is the measurement.
- **Conflicts** — no value of that lever clears both rows; change the piece, not the knob.
- **Closed / Already tried** — no lever exists, or one was already spent.
- **Measurements behind this** — the band shares, tightest gap, attribution shares the model rests on.

## Limits

- The coefficients are linearisations of measured quantities, not new renders. They are good for direction and for
  naming a conflict, not for promising a number; the gate re-measures.
- A stem's PSD is taken from the processed stem cache at the render's sample rate assumption (44.1 kHz unless the
  score says otherwise).
- If the audio on disk is newer than the verdict, the report says so and re-measures nothing: a draft no gate judged is
  not this row's evidence.
- It is not a mixer. It proposes preset and score values; a human or the agent applies them.

## Commands

```bash
python scripts/debug_audio.py <project>                       # only the failing domains
python scripts/debug_audio.py <project> --level WARN          # when nothing fails
python scripts/debug_audio.py <project> --json                # machine form
python scripts/debug_audio.py <project> --record clicks=onset.kit.all=1 --outcome worse
```


## Signal-level forensics (added after the indo-afro benchmark)

The first engine priced a click row by a straight line and attributed it by loudness. Measured on a real render that was
wrong in four ways, each of which made a fix come back. Each is now a module behaviour and a test
(`tests/test_audio_debug_forensics.py`).

| Failure seen | Cause | What the engine does now |
|---|---|---|
| Blamed `guitar`, `kit`, `shekere` by loudness; the step was the `canopy` bed | a stem's unscaled amplitude says nothing about the master (the mixer lifts a bed ~16 dB) | `forensics.Mixdown`: regress the master on the processed stems **in the row's own band** (the gate's `HP_HZ`/`CLICK_ORDER`), attribute each event by the stem's *mixed* contribution to the step; R^2 and per-event fit are printed |
| Cutting a bed's highs raised the event count (3 to 5 to 11) | the row is a MAD z-score: the threshold is a function of the HF floor (the same design as MAD-based click detectors, see Sources), so the row is **not monotone** in any stem | levers are priced by **replay through the gate's own `check_clicks`**; a monotone slope is used only when the replay is monotone, otherwise the lever is priced at zero and the report says why |
| `inst_eq["canopy"]` did nothing for three renders | the mixer reads `inst_eq[<instrument>]` (`env:amazon_rainforest`), not the track name | `catalog.inst_key` mirrors the mixer's lookup; after an applied move `history.settle` compares the stem's fingerprint taken at proposal time and records `unreachable` |
| A "fixed" row failed again by one event | replay scaled the whole band by the nominal gain; a 5.5 kHz shelf cuts less near its corner | the move is applied with the same Pedalboard `HighShelfFilter` the mixer uses (`forensics.shelf_hp`); an environment layer is a gain on its own layer, rebuilt with the track's own seed (`forensics.layer_signals`) |
| Moves that exposed the next owner | one cut at a time | `forensics.plan_clicks` closes the loop in simulation: owners of events within 3 dB of the line, one 3 dB cut, re-explain, repeat; the profile (events at 0/1/2/3 dB tighter) is the objective |

### False proof, and how it is bounded
- **Sham replay** (`forensics.validate`): replay with no change must give back the gate's own events at the gate's own times;
  if not, every candidate is labelled UNVERIFIED and is never adopted.
- **Model resolution** (`forensics.resolution_db`): the 90th-percentile error of the model's steps against the master's
  (1.7 dB on the benchmark). A candidate is *proved* only if it clears with at least that margin; otherwise the status is
  `replay-direction (inside model error)` and the next render is the test.
- **Backtest**: undoing a cut whose effect was measured predicted 0 events where the render had 1 (an event 0.4 dB over the
  line), which is the reason for the resolution rule. Do not read a 0-dB-margin candidate as a result.
- **Prediction record**: every proposal stores its predicted value; `history.settle` records `cleared`, `better`,
  `no change`, `worse` or `unreachable` against the next render (also on a render with no failure), and the report prints
  held/missed. Settling is refused while `Case.drift` shows presets or the score newer than the master.
- A move that would *raise* a floor to hide an event is not offered: it is the loosening the workflow forbids.

### z-separation
`quality_gate.z_pairs` is the gate's pair table (the row now reads it, so the engine and the gate cannot disagree);
`zplace.solve` finds the smallest azimuth/elevation change that clears **every** pair (not only the failing one), keeps
anchors (bass, drums) fixed, keeps a unique spot per part, and says when no placement can (the overlap itself must fall).

### Sources
The click-detection methods this engine and the gate rest on (noise-power and MAD thresholds, high-pass residual, autoregressive prediction error, sham intervention) are listed with their status in `knowledgebase/sound-design/click-detection.md`.
