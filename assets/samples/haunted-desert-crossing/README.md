# The Unwelcome Crossing — a haunted desert game cue

A second Immersive 2.0 sample, and the darker one: an unwelcoming desert where no route survives. 102 s, 76 BPM,
D maqam bayati, 32 bars, built only from Arabian instruments plus piano, violin and flutes, with a haunted desert air
made of natural SFX rather than a cricket loop.

`../haunted-desert-crossing.mp3` is the listenable master (320 kbps, from `out/master.wav`). The multichannel and
object masters stay in the project's `out/`, because this repository ignores `*.wav`:

| File | Channels | Rate | Length |
|---|---|---|---|
| `out/master.wav` | 2 | 44.1 kHz | 102.75 s |
| `out/master_48k.wav` | 2 | 48 kHz | 102.75 s — the game-engine twin |
| `out/master_7_1_2.wav` | 10 — ITU-R BS.2051 System I | 44.1 kHz | 102.61 s |
| `out/master_7_1.wav` | 8 — ITU-R BS.2051 System H | 44.1 kHz | 102.61 s |
| `out/master_adm.wav` | 14 — 11 objects plus a stereo bed | 44.1 kHz | 102.56 s |

`master.json` is the sidecar of the current master and `versions.json` lists both certified versions (v01 and v02; the
second one re-rendered the same decisions with the ADM path fixed).

## What the piece does

- **No path.** The trail figure is D–E♭(+50c)–F–G: the half-flat second always leaning upward and never resolving. The
  piece ends on the fifth. It is judged by the `tense` gate profile, on purpose, because a cue that resolves would be
  telling a different story.
- **Patterns that never repeat.** The oud has four rhythmic cells, chosen per bar, transposed and mirrored bar by bar
  with a small timing jitter; the darbuka states a saidi-family 4/4 cycle with a different fill each bar and drops out
  completely under the dune; the qanun changes its arpeggio shape every bar (up, down, broken).
- **Zimmer's method, Rahman's layering.** A low piano pulse is the clock — 8ths through the crossing, 16ths into the
  jackals, then almost nothing. The violin is a sustained texture of five long swells, not a counter-line. The qanun
  carries the harmony in fast runs while the ney sings over it and the rababa holds the floor.
- **Haunted air, natural SFX.** `haunted_desert_air` is a 78 Hz dune bed with its harmonics, a sand hiss at 0.85–2.5 kHz,
  a gust that starts and stops, and a far jackal answered from the right rear. Two one-hit SFX mark the turns:
  `sand_blast` when the trail erases, `dune_slump` when the slip face gives way.
- **Objects, not just channels.** The same render is delivered as 7.1.2, 7.1, a 48 kHz stereo twin and an ADM BW64 file
  whose 11 object channels carry their positions over time, so a game engine can place the parts instead of replaying
  a fixed mix.

## Gate result

`pipeline.py` certified it: **0 FAIL, 139 PASS, 15 WARN**, −17.2 LUFS and −2.0 dBTP on the stereo master, with
`clicks` clean, `tempo.audio` reading 76 BPM, `ambient_bed` gliding without dropouts and every `adm.*` row passing on
the BW64 container. `section.energy` is the one WARN worth naming: the arc correlates at rho 0.60, below the 0.7 the
row asks for.

## Honest limits

- **Nothing was auditioned.** `listen.py` needs earshot, which is not installed; the numbers are the only evidence.
- **No SFZ.** No Arabian library is in the skill registry and sfizz cannot build on this host, so every part is the
  General MIDI bank through a project preset.
- The 44.1 kHz engine rate is the project's; the 48 kHz twin is a resample of the certified master, not a second mix.
- Scene and object files have no loudness until a renderer folds them; only the stereo masters are normalised.

`direction_sheet.json` and `score.json` are the two project files behind this render: the intent, and the notes.
