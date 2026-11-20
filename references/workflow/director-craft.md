---
title: Director craft
summary: The decisions a producer makes before and after the notes, the failures that make output sound generated, and how to blend traditions without pastiche.
tags: [director, craft, quality, producer, hook, arrangement, density, blend, fusion, review, funky, generic]
load_when:
  - before the direction sheet of any piece
  - a render passes the gate and still sounds generated, flat or cluttered
  - blending instruments from more than one tradition
---

# Director craft: what separates a produced piece from a generated one

A generator fills time with notes in the right key. A producer decides what the listener should notice at each moment
and what must stay out of the way, then writes only the notes that do that. The gate says a render is not faulty. It does
not say the piece was directed. This file is the pass between the brief and the first note, and the pass after the first
render.

## 1. The craft pass: six answers before any note

Every answer goes into a field the sheet already has. Nothing here adds a field.

| Decide | Write it in | A good answer |
|---|---|---|
| The hook: the one idea a listener leaves with | `motifs[0].shape`, `expression.theme` | a few notes as a shape (rise, step back, leap on a weak beat), with its rhythm cell; not a mood word |
| The arc: where the piece rises, breathes and lands | `sections[]` with `energy` and `role` | a low and a high that differ by a clear step, and one section that is thinner than its neighbours |
| The density map: who plays and who rests, section by section | `sections[].music` | each section names the parts that play; at least one part rests in every section |
| The lanes: who carries, who answers, who keeps pulse, who is the bed | `mix_intent`, `spatial_staging`, `instruments` | one carrier per section; a second part speaks only in the carrier's rests |
| The contrast: what changes at each boundary | `sections[].music`, `expression.producer_moves` | at least one of register, timbre, density, rhythm or harmony changes, and one thing stays |
| The ending | `ending`, `sections[-1]` | a cadence or a deliberate open ending, never a cut in the middle of a phrase |

Then fill `expression.anti_generic`: the generic version of this piece in one sentence, and the one measurable thing that
stops this piece being it. If the score's first idea is that sentence, rewrite the score.

## 2. The failures that read as generated, and the counter for each

| Failure | What the listener hears | Counter | What can measure it |
|---|---|---|---|
| Every part plays all the time | a wall with no focus | the density map: every section drops a part; `focus` and `mix_intent.hero` say who leads | `scripts/helpers/short_form_report.py` density spread, the balance rows |
| Bars copied | a loop machine | change one thing at every return (interval, rhythm, register, harmony, instrument) | the `pattern` row, `melody.variety` |
| No phrase shape | a stream of notes with no breath | phrases of two, four or eight bars; a rest or a long note at each phrase end; a longer note on the cadence | the breath-gap rows |
| Two parts compete for the lead | mud in the midrange | one carrier per section; the others answer in its rests | `balance`, `spatial.z_separation` |
| Different scales in one piece | wrong notes between traditions | one tonic and one scale for every part; ornaments stay inside the scale | the harmony rows, `intent.avoid` |
| Pastiche | an instrument playing another tradition's part | each instrument keeps its own gesture and plays the role it is best at (section 4) | `expression.performer` |
| Reverb as glue | a wash, soft attacks, lost rhythm | the send per role (`space.send_by_role`), a shorter tail on a fast part | the mix rows |
| A pulse nobody chose | a groove that is an accident | one pulse declared; the groove cell written down | the groove rows |
| No contrast | one level from start to end | an arc with a floor and a peak | `scripts/helpers/arc_report.py` |
| The piece stops instead of ending | a cut | an ending plan, a harmony that lands, a tail that dies in the room | the end rows |
| Machine timing | everything on the grid | a humanize preset per role; a tight grid only for the parts that need it | `scripts/helpers/expression_report.py` |
| Bright and loud everywhere | fatigue | a part owns each band; the carrier is carved room in the mix | `mix:spectral overlap`, `lead_carve` |

A counter that moves a number but not the sentence in the second column has not fixed the failure.

## 3. Lanes

Give each part a function before an instrument: **carrier** (the line the ear follows), **answer** (a second voice in
the carrier's rests), **pulse** (what keeps time), **bed** (the harmony that holds), **colour** (a short accent or a
texture). No two parts share a function and a register in the same section. A part that has nothing to add in a section
rests: a rest is a decision, and the section after it lands harder. The spectral and spatial rules that follow from lanes
are in `references/mixing/blending-and-balance.md` and `references/mixing/mix-rules.md`.

## 4. Blending traditions without pastiche

A blend is one piece in which each tradition does what it is best at. It is not a medley and not a shared bar count.

1. **Fix the shared core first.** One tonic, one scale every part can play (pentatonic subsets are common to many
   traditions), one pulse and meter, one tempo. `scripts/fusion.py` plans these from `"fusion": [...]`; read what it
   chose and say it in the sheet.
2. **Give each tradition a job.** A lead voice, a rhythmic engine, an ornament layer, a bed. Not an equal share of bars.
3. **Keep each instrument's own gesture, and write it.** A bent note, a slide, a plucked pattern, a breath: put it in the
   notes (`gl`, `gs`, `c` on the GM path) and in the `performer` field. The SFZ path cannot send a glide or a microtonal
   offset (`AGENTS.md` 3b): a part that needs one goes to a path that can.
4. **Fixed-pitch instruments fix the tuning.** A piano, marimba or kalimba is equal-tempered. A bending instrument may lean
   toward its own tradition's inflection, but a semitone rub against a fixed-pitch part on the same note is roughness, not
   colour: keep the bend on the passing notes and land on the shared scale degree.
5. **Hand over, do not stack.** The line passes from one instrument to the next at phrase ends, with at most a note of
   overlap. The blend is in the hand-over, not in six instruments playing the same melody.
6. **One room.** Every part sits in one space with its own azimuth and distance, so the traditions share a place instead of
   being laid over each other.
7. **Write an original tune.** Do not quote a living repertoire's melody. The shape comes from the sheet.

## 5. The director's two reviews

**Before the render**, in `STATUS.md`, the six answers of section 1 in one line each, and the sentence in
`expression.anti_generic`. If a line cannot be written, the piece is not decided yet.

**After the render and the measurements**, in `STATUS.md`:

- Which rows of the table in section 2 the piece could still show, and the measurement that says it does not.
- The one thing a human player or producer would change first, and whether it was changed.
- What was not checked. A render was not heard unless `listen.py` ran with its ears; taste, melody and the pleasantness of a
  blend are not measured. Say it in those words.

A piece that passes every row and fails the second review goes back to section 1, not to the gate.
