---
title: Commercial-grade cinematic and hybrid scoring
summary: How to direct, write, mix and check a tense, large-scale orchestral or hybrid cue so it has pressure and not only mood.
tags: [cinematic, hybrid, orchestral, trailer, tension, ostinato, braam, loudness, pressure, dread, epic, unknown, suspense, thriller, adventure]
load_when:
  - the brief asks for a cinematic, epic, trailer, thriller or hybrid orchestral cue
  - a render passed the gate and still sounds calm, thin or meditative
  - the brief names a large-scale film composer's style
---

# Commercial-grade cinematic and hybrid scoring

Facts and sources: `knowledgebase/genre-and-feel/cinematic-hybrid-scoring.md`. This file is the procedure. The gate
(`references/mixing/quality-gate.md`) says whether a render is faulty; nothing in it says whether the render has the
pressure the brief asked for. A cue can pass every row and be a pad with a few drum hits. This file is how you tell, and
what to do about it.

## 1. The lesson that made this file

A 97 s rain-forest cue written to feel like an unwelcoming unknown place passed the gate with 0 FAIL and was heard
as meditation. What had happened, in the order it happened:

1. Each gate failure was fixed at the notes (sparser trombone stabs, the tuba kept to a few structural moments, the sub
   boom removed, chopped pulses taken out, velocities compressed so no hit stood out). Every fix was legitimate and each one
   took pressure out. Nobody checked the sum.
2. The master was -16 LUFS with the loudest stretch about -13 to -18 dBFS RMS; whole sections sat 12 LU or more under
   the integrated level; the final section, which should culminate, was the quietest after the opening.
3. `scripts/helpers/arc_report.py` shows all of that in one table. It was run after the complaint, not before.

Rule: after the gate is green, measure the arc against the brief before certifying. Fix a missing pressure in the
writing, never by loosening a gate row.

## 2. Direct the pressure first (Phase 4 of `AGENTS.md`)

In the direction sheet, decide these before any note:

| Field | Decide | Test it can fail |
|---|---|---|
| `energy` | one number per section on the brief's scale, rising to the last section unless the brief says the end collapses | `arc_report.py` section means follow the same order |
| `loudness` | the target of the brief's medium: a film cue, a trailer, a game loop (figures in the knowledge-base file, section 4) | integrated value in `arc_report.py` |
| the carriers | which of pulse, low brass and sub weight, constant percussion, rising or accelerating device carries the piece | each has a track and notes in every section that needs it |
| silence | where the cue drops out on purpose, and how long | no unplanned stretch in the quiet-stretch list |
| the turning points | each hit, with the silence before it | `hits` in the sheet agree with the score |

A brief that says "unknown", "unwelcoming", "hostile" or "dread" asks for pressure and unresolved harmony, not for
space and atmosphere. Atmosphere (rain, river, canopy) sits under the cue and is turned down, not up, when the brief
is about threat.

## 3. Write it

1. **A pulse that keeps going.** One low-string or percussion figure from the first section to the last. Build it from
   chord tones; change a few notes on each repeat; humanize timing and velocity so no two bars are identical. It
   speeds up or thickens as the sections rise. A pulse that stops for a section needs a reason in the sheet.
2. **Low weight at the turning points.** Low brass and the lowest strings together on a hit, with a riser into it and a
   sub drop after it. Write the hit loud and the note before it quiet: the contrast is the hit. One real hit per turning point
   is better than many small ones.
3. **Percussion as a layer, not as accents.** A drum ensemble with a long room tail carries the chase. Vary the pattern;
   `pattern.flags_max` and the tick row will catch a machine loop.
4. **Unresolved harmony.** A pedal point under changing chords, clusters with inner movement, tremolo that grows
   by adding instruments, a glissando that is slow. End on a chord that does not resolve unless the brief ends in relief.
5. **The last section is the peak or the cliff, never the fade of a peak.** If the arc ends quietly, the sheet says so
   and `arc_report.py` shows a drop that was asked for.
6. **Keep the stems' velocities.** Compressing velocities to quiet a gate row removes the contrast that makes a hit a
   hit. Fix the row at the instrument or the placement; keep a quiet note quiet and a loud note loud.

## 4. A gate row and a pressure goal that collide

Large low hits and dense low brass trigger gate rows that exist for good reasons. Solve them in the piece:

| Row | Cause on a heavy cue | Fix in the piece |
|---|---|---|
| `master.dc` (1 s block means) | a loud 80-120 Hz tone that does not complete its cycles in each 1 s block reads as drift | `mastering.highpass_hz` with `mastering.highpass_order` 3 in the mix preset; a stereo file does not need the sub that a layout's low-frequency channel carries |
| `dropout` | a quiet tail that dips under the floor and comes back | end the quiet bed with the music instead of letting it run on; a long tail after the last chord is a hole waiting to be found |
| `cochlear_roughness` | a bass harmonic a semitone from a sustained chord note | move the bass to the chord's root, or move the chord note; do not mute the bass |
| `spatial.z_separation` | two parts in the same midrange at the same place | separate by azimuth or height; a bass cannot be raised, so move the other part |
| `fold.mono` | a head-filtered stereo master adds up 3-5 dB low in 450-1500 Hz | `immersive.stereo_decode: "speakers"` for a loudspeaker master; headphones keep `binaural` |
| the calm ending is as loud as the chase | a melody, lead or vocal part that plays only the quiet sections: gain staging lifts every figure-family part to full level | give the part the role `counter` (`preflight.figure_level` warns before the render) |
| `clicks`, `stem.edge`, `ambient_bed` on random sources | a bout of calls or a noise bed lands differently on each render | give the track a fixed length that ends on a call, and a bed under it that does not stop; re-render, do not relax the row |

## 5. Mix it

- Target the loudness of the medium (knowledge-base file, section 4) in the score's `master` block; the figure is a
  starting value until the delivery spec is known. A trailer is not -16 LUFS.
- The low end needs one owner. High-pass what should not carry the sub. Use `sidechain` and the mix preset's multi-band
  tools; never raise a gate threshold.
- Reverb is one shared room: the same `space` for every instrument, with the send per role in the mix preset.
- A free, dry sample library cannot reach a commercial hybrid sound by writing alone. Say so in the report; offer a
  better SFZ library as a preset, and layer short attacks over sustained patches (the SFZ section of `AGENTS.md`).

## 6. Check it (before Phase 9)

```
python scripts/helpers/arc_report.py out/master.wav --score scores/<title>_score.json
```

Read the table against the sheet:

- the section means rise in the order of the sheet's `energy`;
- the last section is where the sheet put the peak;
- the pressure share (the part of the file within 6 LU of the loudest 3 s) is what the brief needs: a thriller cue that
  is under 50 % has more atmosphere than threat;
- every quiet stretch in the list is a silence the sheet asked for.

The report prints; it does not pass or fail. When it disagrees with the brief, change the writing and render again.
When it agrees, say in the report that the arc was measured and that the sound was not auditioned.
