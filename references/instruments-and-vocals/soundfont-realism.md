---
title: Making a SoundFont sound natural (velocity, layering, space)
summary: The levers that take a General MIDI SoundFont part from a sample player toward an orchestral sound, and the limits that stay.
tags: [soundfont, sf2, sf3, velocity, orchestra, realism, layering, articulation, cinematic]
load_when:
  - a brief asks for an orchestral, cinematic or acoustic sound played by the SoundFont
  - a SoundFont part sounds flat, the same loud and soft, or like a sample player
---

# Making a SoundFont sound natural

Facts, with their status: `knowledgebase/sound-design/soundfont-velocity-and-realism.md`. A free General MIDI SoundFont
has one sample per key and cannot sound like a commercial multisampled library. These levers close part of the gap; say
what remains in the report.

## 1. Where the realism is lost

| Loss | Why | Lever |
|---|---|---|
| A soft note is the same colour as a hard one | the engine maps velocity to gain only; the SF2 velocity-to-cutoff modulator is not applied | `velocity_timbre` (section 2) |
| The front of a note is soft | one sample, no attack layer | `enhance_sf2_dynamics` (always on), `onset_fade_ms` only to remove a click |
| A held note is a flat loop | no per-note evolution | a written dynamics arc, and for sustained parts `per_note_channels` with an `expression` shape and vibrato from the preset |
| Every note of a line is as if one player | no per-part variation | one track per part (a section is several tracks, each with its own humanise and its own `lean`) |
| It is dry | a sample is recorded close | one shared room for every part with the send per role in the mix preset |

## 2. Velocity as brightness: `velocity_timbre`

An instrument preset (or a track) can declare:

```json
"velocity_timbre": {"points": [[25, 1800], [60, 3200], [100, 6500], [127, 9500]], "bands": 4}
```

The notes are played in `bands` groups by written velocity (equal counts), each group is low-passed at the cutoff
`points` give for its mean velocity (log-frequency interpolation), and the groups are summed. A soft note is warmer, a
hard one open. Rules:

- `points` are `[velocity, low-pass Hz]` pairs in rising velocity order; every number carries a source or "starting
  value" in the preset's `sources` (the knowledge-base file lists starting figures).
- It is for a plain SoundFont track. An SFZ track has real velocity layers and a clone, effect, environment or voice has
  none to emulate: asking for it there is an error.
- Write the velocities: a part whose notes are all at one velocity is one band, and nothing changes. A phrase that swells
  needs written velocities that rise and fall; the engine cannot invent them.
- A note's neighbours in another band are invisible to the humanizer, so a slur across two bands does not overlap. Keep
  a legato line within a narrow velocity range, or give it its own track.
- It cannot add a real second layer: the attack and the harmonic series stay those of the one sample. Say so.

## 2b. A continuous loudness-timbre coupling: `timbre_dynamics`

`velocity_timbre` splits written velocities into bands. A part whose written velocities already move can instead
ask for a continuous coupling: the rendered level of the stem controls a nonlinear residue and a high shelf, so a
swell gets brighter as it rises and a quiet passage keeps its body.

```json
"timbre_dynamics": {"drive": 0.5, "tilt_db": 2.0, "tilt_hz": 2800, "band_hz": [140, 7000],
                    "amount": 0.6, "smooth_s": 0.35}
```

It is level-compensated: colour, not pattern level. The sub is excluded from the nonlinear band so the low end
stays clean. A stem with no dynamic range is returned unchanged. Do not put it on `sfx:`, `env:` or `clone:` tracks.
Facts: `knowledgebase/sound-design/theatrical-realism.md` section 1. It cannot add the missing fortissimo sample;
say so in the report.

## 3. Layering and articulation

- A sustained part gets a short attack under it: `timpani` or `pizzicato` under `strings`, a staccato `horn` under a
  pad, a `harp` or `piano` arpeggio under a held chord. The attack is a separate track with its own preset.
- Use the articulation the music means: `pizzicato` for plucked, `tremolo_strings` for tension that builds,
  `string_ensemble` for a legato body. One sustain patch for a whole part is the sample-player tell.
- Choose the SoundFont by instrument, not by size: MuseScore General (MIT) is a general-MIDI bank, GeneralUser GS is
  the engine's default. A better orchestral source is an SFZ library (`AGENTS.md` section 5).

## 4. Dynamics: velocity versus the controller

Velocity decides how a note begins; the CC11 (expression) curve decides how it evolves. The engine writes the score's
`dynamics` as CC11, so a crescendo exists in the score's `dynamics` and in written velocities, not in the mix. A held
note that must swell needs `per_note_channels` and an `expression` shape (`bow` or `breath`).

## 4b. Write what an orchestra could play

A SoundFont plays any note, so a line no player could play still renders and reads as a mock-up. Run
`python scripts/orch_rows.py <score> --project <dir>` before a render (stage 2 runs it too): it flags a note outside the
instrument's range (`orch.range`), parallel fifths between two lines (`orch.voice_leading`), more simultaneous notes,
a faster repeated-note run or a longer breathless phrase than a player or section has (`orch.playable`), and a gap between
notes marked legato (`orch.legato`). A section is a track named for one (`strings`, `horns`) or an `ensemble` block;
mark a deliberate extreme with `"extended_range": true`. Rows and limits: `quality-gate-rows.md` section 7; facts and their
status: `knowledgebase/genre-and-feel/orchestral-writing.md`.

## 5. Report

Say which SoundFont played, which parts used `velocity_timbre` and with what points, which attacks were layered, and
that nothing was auditioned unless `listen.py` ran.
