# The Unwelcome Crossing — a haunted desert game cue

An unwelcoming desert where no route survives. 102 s, 76 BPM, D maqam bayati, 32 bars. Arabian instruments only
(oud, qanun, ney, rababa) plus piano, violin and flutes, over a haunted desert air built from natural SFX.

`../haunted-desert-crossing.mp3` is the listenable master (320 kbps, from `out/master_v06.wav`).

| File | Channels | Rate | Length |
|---|---|---|---|
| `out/master.wav` (= `master_v06.wav`) | 2 | 44.1 kHz | 102.75 s |
| `out/master_48k.wav` | 2 | 48 kHz | 102.75 s — the game-engine twin |
| `out/_draft_master_7_1_2.wav` | 10 — ITU-R BS.2051 System I | 44.1 kHz | 102.6 s |
| `out/master_7_1.wav` | 8 — ITU-R BS.2051 System H | 44.1 kHz | 102.6 s |
| `out/master_adm.wav` | 14 — objects plus a stereo bed | 44.1 kHz | 102.6 s |

The repo ignores `*.wav`, so the scene and object renders live in the project's `out/`; `master.json` and
`versions.json` are the delivery record.

## Rhythm, before anything else

The first revision had no iqa' — and, after a tempo fix, four hits on the beat, which is a metronome, not a groove.
This one plays the cycles, thinned so the beat stays the beat:

- **Maqsum** (D T – T D – T –) through `no_road`: dums on 1 and 3, one tak alternating sides of the bar.
- **Saidi** (D T – D D – T –) through `jackals`: the two back-to-back dums in the middle are the signature.
- **Wahda** in `no_water`: a single dum, because there is nothing left to say.
- A muted `ka` every third bar, one ornament tak every fourth, and the drum drops out completely under the dune —
  so no two bars are the same, and the cycle still reads as maqsum.
- The darbuka plays drum-hand articulations on the kit: doum low, tak dry and high. It is not a kick/snare pattern.

## Why the flute sounded like a throat

The ney was mapped to **GM 77 — shakuhachi**, which is exactly the hollow, hooty tone a ney is not. It now plays
**GM 73 (flute)** with an end-blown EQ (300 Hz high-pass, −2.5 dB at 1.1 kHz for the tube's boxiness, +1.2 dB at 2.8 kHz,
−3 dB shelf at 6 kHz, 10 kHz low-pass). The second flute is a wooden **recorder (GM 74)**, so the two winds are
different instruments rather than two copies.

## Smoothness

- Melody notes overlap by 8% and carry `art: legato`.
- Every phrase has a velocity arch, not a flat line.
- Presets carry a 5–9 ms onset ramp, and the renderer now honours it on the melodic GM path as well (it only did on
  the drum path before), so sampled attacks start out of silence instead of on a step.
- Reverb sends raised across the winds and violin; the mix bus is DC-blocked at 30 Hz and servo'd at 4 Hz.

## Gate result

Stereo certification, **v06: 0 FAIL, 141 PASS, 11 WARN**, −17.2 LUFS, −1.9 dBTP; 48 kHz twin written from it.
`clicks` clean, `tempo.audio` reads 76.0 BPM, `ambient_bed` glides without dropouts.

**Not clean:** `imm.surround_ratio` on the 7.1.2 and 7.1 renders — surround energy −9.9 dB against the front stage,
where the row wants −9.0 to −2.0 dB. So those two scenes (and the ADM built alongside them) are rendered and
audible but do not pass their own row yet; only the stereo masters are certified. `section.energy` is a WARN at
rho 0.60.

## Honest limits

- **Nothing was auditioned.** `listen.py` needs earshot, which is not installed; every claim above is measured data.
- **No SFZ.** No Arabian library is in the skill registry and sfizz cannot build on this host, so the parts are GM
  patches through project presets — good enough to carry the piece, not a real oud or ney.
- The 48 kHz file is a resample of the certified master, not a second mix.
- The piece ends on the fifth with no cadence, so it is judged by the `tense` profile on purpose.

`direction_sheet.json` and `score.json` are the two project files behind this render.
