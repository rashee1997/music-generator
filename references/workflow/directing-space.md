---
title: Directing in space
summary: How an immersive piece is decided: whether the field does a job, which parts are anchors and which move, the height plan, where the room changes, and the deliverables that carry them.
tags: [immersive, direction, staging, trajectory, spatial, height, ambience]
load_when:
  - the piece is immersive, or asks for height, motion or a room that changes
  - an imm_* gate row fails and one lever has to move
---

# Directing in space: Immersive 2.0

Immersive 2.0 is a directing choice before it is a delivery format. A field that moves because the camera moves says
something a stereo mix cannot; a field that moves for no reason is a ride.

Decide four things in this order, and write them in the direction sheet's `immersive` block: whether space is doing a
job, where everything sits, what moves and why, and how the room changes. The numbers that execute those decisions
live in the presets - the sheet carries intent, never azimuth arrays, keyframes or RT60.

## 1. Decide whether space is the job

Write `immersive.why` as one sentence about the listener or the picture: "the camera drifts along the ridge", "the herd
passes behind you". If the sentence cannot be written, leave `enabled` false. A piece delivered in stereo has not
failed.

The mix preset's `immersive.enabled` and `immersive.engine` execute it; the sheet records what was intended. The
ambisonic bus (`engine: "hoa_bus"`) is the one that carries motion, moveable sources and a room that changes; the older
per-stem engine takes no keyframes.

## 2. Stage, then decide what may move

`spatial_staging` gives every part its place (azimuth, elevation, distance, space). In the immersive frame the second
question is which parts are **anchors** and which are **movers**:

- Bass and drums are anchors whatever the preset says: the mixer forces them to the floor and the trajectory engine
  holds them within `anchor_max_span_deg` of their place.
- Anything else is an anchor unless the piece would wobble with it moving. A mover needs a reason a listener could
  name: a character, a vehicle, a camera, a herd.
- Write the reason in `movers[].why` and the path in words in `movers[].path`. A part with no sentence there should
  not move.

## 3. Height belongs to what has high-frequency content

A lifted stem needs energy above 4 kHz to sound high - height is a pinna cue - so lift the flute, strings, air and
bells, not the bass (`imm_band` warns when a lifted stem has almost none above that line).

- Height in the sheet's `immersive.height` and elevation in the instrument preset must agree within 10 deg; stage 0
  compares them and blocks a disagreement.
- Nothing goes above `max_elevation` (60 by default): near-vertical positions are the least reliable with a dummy head.
- A lifted part is one that reads as *above* in the mix, so keep its low end out and its air in.

## 4. Write motion by section, not by second

A trajectory key is placed by `t_s`, `bar`, or a **section name**. The section names in the direction sheet are the
vocabulary a trajectory addresses, so they must match the score's `plan.sections` - the engine raises when a section
named in a key does not exist.

- Keep the keys spread over the section: `imm_kinematics` fails when a path turns faster than the role allows
  (10 deg/s for an anchor, 120 deg/s for a mover by default). An anchor holds within `anchor_max_span_deg` (6) of its
  place.
- Distance changes are what carry the Doppler cue, so write the approach or the pass in the path. A mover that only
  slides left to right is a pan, not a move.
- `mode: "sway"` is for a small continuous drift around a place, not for travel: rate in cycles per bar or Hz, with a
  span per axis.
- A stereo bed becomes a pair of sources at its own sides; `widen` and `width` do not apply on the bus, because there
  the pair angle is the width.

## 5. Change the room when the place changes

`room_changes[].at_section` names the moment (the reveal, the cut to exterior). The execution is a `scenes` entry on
the space preset that fades over `transition_bars` or `transition_s`, so the old room rings out while the new one
builds - two identical rooms crossfade to exactly the same room.

- One or two changes in a cue. A room that changes on every bar is a stutter.
- Write the size and materials (`geometry`) and let `rt60_s: "auto"` derive the decay when the room must be a size
  rather than a number. `auto` is a diffuse-field estimate: wrong for a corridor, a room with one very dead surface, or
  anything coupled to another space.
- Moving a source through a room also moves its reflections: the ceiling tap is what makes height read.

## 6. Deliver what the scene needs, in the right order

`deliverables` names the formats the cue must exist in, and the score's `output_targets` must name the same set,
**two-channel first**: `stereo` (or `binaural`), so the ordinary gate rows judge a real master, then `ambix` (the field
itself, re-renderable later) or `adm_bw64` (objects and their positions) when the piece has to travel.

- Ceilings follow the format: -1.5 dBTP for two channels, -3.0 dBTP for the scene formats.
- Name every system the cue will really be played on. `mono` for a phone speaker, a radio or a public-address system:
  it is rendered from the mix, not summed from the stereo file. `immersive_5_1` and its height variants for a living
  room, the 7.1 family for a theatre. A format nobody will play is a format nobody checked by ear.
- The `fold.mono` and `fold.timbre` rows compare each extra format with the stereo master, so the stereo master is
  listed first. With `binaural` first those rows only warn.
- A scene has no loudness until something folds it, so `loudness_lufs` on the sheet is the two-channel master's number.
- `ambix` holds the whole field in memory while it is written; a long piece at fifth order needs a lot of RAM.

## 7. What the director decides, where it runs, what judges it

| The intent | Sheet | Execution (presets / score) | Gate row |
|---|---|---|---|
| a sound passes overhead | mover with a height change | `trajectory` elevation keys; a ceiling reflection in the space | `imm_elevation`, `imm_externalization` |
| a subject approaches | mover with distance keys | `trajectory` distance; `doppler` left on | `imm_kinematics` |
| a wide ambient bed | staging `kind: bed`, pair width | `immersive.pair.width_deg_bed` | `mix.band_fold`, `imm_low_fold` |
| a grounded low end | bass and drums as anchors, no height | role forced to 0 deg by the mixer | `imm_low_fold`, `imm_height_rules` |
| the room opens at the reveal | `room_changes[].at_section` | space preset `scenes` | `imm_clarity`, `imm_envelopment` |
| a stable image in stereo too | two-channel target listed first | `output_targets` | `imm_folddown`, `mix.band_fold` |

A failing immersive row is a fact about the presets or the score: spread the keyframes, narrow the stem the row names,
lower the space's `late.level_db`, bring a side wall in. Never loosen the row. The rows and their fixes are in
`references/mixing/quality-gate.md` section 5b; the engine and its physics are in
`references/spatial/immersive-spatial.md` section 2c.

## 8. Honesty rules for this block

- Nothing in the immersive path is auditioned by `listen.py`: it judges a stereo master. Say so on delivery, and
  listen on headphones if a person can.
- The limits of the format are stated, not smoothed over: a dummy-head height cue is weak and varies by listener, the
  late field is a statistical tail rather than a ray-traced room, and an ADM file is an open standard, not a certified
  Atmos master.
- A sheet that says `enabled: true` while the mix preset says false, or while the score names no scene target, is a
  sheet that describes a piece nobody will hear. Keep the three equal.
