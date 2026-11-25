# Virtual speaker QA for any channel count

This note records the general channel-QA layer added for 36-channel AmbiX and every other delivered channel count.
The rule and the numbers live in `references/spatial/virtual-speaker-qa.md` and
`knowledgebase/sound-design/virtual-speaker-qa.md`; this page is the implementation map.

## What runs

`scripts/spatial_gate.output_rows` calls `channel_rows` for every delivered target. That function uses
`scripts/channel_qa.py` to put the file on the positions it claims:

- a loudspeaker layout uses its `speakers` block in channel order (LFE has no position);
- order-5 AmbiX (36 ACN/SN3D channels) is decoded with `hoa.allrad_matrix` (AllRAD/max-rE) to the 36-point
  `ambix_qa_36` virtual layout;
- an undeclared file is still checked per channel, without spatial balance.

`channel.virtual` reports the mapping and fails a wrong channel count, too few virtual speakers, or a non-finite
decoded channel. `channel.bars` splits the file at the score's bar lines and reports an isolated bar where one
channel jumps, drops out, flips polarity or swings the left/right, front/back or floor/height balance while the
other channels stay still.

## Files

| File | Role |
|---|---|
| `scripts/channel_qa.py` | mapping, bar boundaries, per-bar levels and conflict detection |
| `references/data/presets/layouts/ambix_qa_36.json` | 36-point Fibonacci QA array, names `V01`-`V36` |
| `references/data/presets/outputs/ambix.json` | `gate.virtual_layout` and `gate.min_virtual_channels` |
| `scripts/spatial_gate.py` | `channel.virtual` and `channel.bars` rows |
| `scripts/gate_profiles.py` | row registration and starting-value parameters |
| `tests/test_channel_qa.py` | clean, jump, dropout, polarity, whole-bar accent, 5.1 and AmbiX controls |

## Limits

The virtual array is not a room or a listening test. The per-bar RMS test cannot hear a timbre-only change, and it
does not decide whether a deliberate one-bar effect is musically right. A 36-point Fibonacci sphere is an
observation grid, not a certified spherical design; AllRAD's 1200-point internal sampling is what makes the
decoder. Thresholds are starting values and are relaxed only with a measured reason.

## Two low-frequency channels and a three-front stage

`scripts/spatial_engine/lfe_qa.py` and `spatial_gate.lfe_rows` add, for a layout with two `lfe` speakers (`lrc_lfe2`):

| Row | Reads | Fails or warns |
|---|---|---|
| `lfe.polarity` | zero-lag correlation of LFE1 and LFE2 (and the best within +-1 ms) | FAIL when opposed (default below -0.3 with real correlation) |
| `lfe.sum_coherence` | correlation over 20 Hz to `decorrelate_above_hz` | WARN under 0.9 |
| `lfe.fold_loss` | level the 3.2 -> 3.1 fold gains or loses per 1/3 octave | WARN beyond 1.5 dB |
| `lfe.modal_spread` | spatial spread of a virtual box room, one sub against two | WARN when two are worse; INFO otherwise |
| `front.fold_phantom` | ITD and ILD of the centre folded into L/R against a real centre, measured head set | WARN beyond 100 microseconds or 2 dB |

`lfe.modal_spread` is a model of the room in the layout's `qa.listening_room` (a starting value), not of the listener's. A
front-only layout declares its own decoder bounds in `gate.decode_uniformity_max_db` (measured 0.34 dB for AllRAD2 and
3.26 dB for AllRAD on `lrc_lfe2`), instead of loosening `imm.decode_uniformity`.
