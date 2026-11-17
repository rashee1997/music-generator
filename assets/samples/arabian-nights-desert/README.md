# Arabian Nights: The Desert Crossing — an Immersive 2.0 sample

One certified render of the direction-sheet instructions in `references/workflow/directing-space.md`: a 67 s piece in
D maqam hijaz, 88 BPM, with a maqsum darbuka cycle, oud, qanun, ney, bowed rababa, a chant, a high voice and the open
desert air around them, mixed on the ambisonic bus and delivered as a two-channel master plus two scene formats.

`../arabian-nights-desert.mp3` is the listenable master (320 kbps, from `out/master.wav`). The multichannel masters stay
in the project's `out/`, because this repository ignores `*.wav` and a scene file is too heavy to commit:

| File | Channels | Rate | Length |
|---|---|---|---|
| `out/master.wav` | 2 | 44.1 kHz | 67.11 s |
| `out/master_7_1_2.wav` | 10 — ITU-R BS.2051 System I | 44.1 kHz | 67.08 s |
| `out/master_7_1.wav` | 8 — ITU-R BS.2051 System H | 44.1 kHz | 67.08 s |

`master.json` is the sidecar of the current master, `master_v01.json` the record of the version taken when the render
first cleared the `clicks` row, and `versions.json` lists both.

## What the piece does in space

- **One pass-by.** The ney starts far left and low, crosses over the listener's head at the mirage and settles front-right;
  its keyframes are anchored to the score's section names (`crossing`, `mirage`, `first_light`), not to seconds.
- **A voice behind.** The high voice is a mover behind the listener during the mirage.
- **Air around the listener.** `presets/environments/desert_night_air.json` puts an open desert night under everything: a
  wide low wind bed anchored at the listener (+20 deg, 6 m), an intermittent dune gust from the left, and a faint sand
  drift on the right. Drawn from a CC0 desert wind recording, the earth.fm Sahara and Gobi dune recordings, and a JASA
  wind-noise letter; its levels are starting values, written as an ESTIMATE.
- **A room that arrives.** At `first_light` the open desert (earth floor, open walls and sky) becomes a 9 x 14 x 6 m
  concrete cistern over water, with ceiling and side reflections and a much longer tail.
- Seven parts are lifted, one (the arrow) is a `drone` at +20 deg, and the bass and drum stay on the floor.

## Gate result

`pipeline.py` certified it at **v02**: **0 FAIL, 132 PASS, 14 WARN**, -18.7 LUFS and -2.5 dBTP on the two-channel master,
with `ambient_bed` passing (the bed glides, no dropouts or pumping). All `imm_*` rows pass except `imm_band` (WARN): the
drone sits high but has almost nothing above 4 kHz, so it reads as width rather than height. Two rows failed on the way
there and were fixed at their cause, not relaxed: the air bed first rendered 71 dB down, and the front-heavy bed tipped
`imm.surround_ratio` by 0.0 dB until the rear voices came up 3 dB and the front drone went down 2 dB.

## Honest limits

- **Nothing was auditioned.** `listen.py` needs earshot, which was not installed; the numbers are the only evidence.
- **No SFZ.** The registry holds no Arabian library and `sfizz_render` cannot run on the build host, so every part is the
  General MIDI bank through a project preset.
- **7.1.2 is ten channels.** An eight-channel file is 7.1, which is the second scene target here.
- A scene format has no loudness until something folds it, so neither multichannel file is loudness-normalised.

`direction_sheet.json` and `score.json` are the two project files that describe this render: the intent, and the notes.
