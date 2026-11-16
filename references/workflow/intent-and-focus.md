---
title: Intent and focus
summary: Declaring what the piece is and what carries it, the words that resolve, and the two gate rows that read them.
tags: [intent, focus, roles, emotion, scene, register, tension, vocabulary, brief]
load_when:
  - writing a brief or a direction sheet from a client's sentence
  - choosing piece_type or the role of the leading part
  - the focus.declared or intent.vocabulary row fails or warns
---

# Intent and focus: say what the piece is, not only what it plays

A score can be perfectly playable and still be the wrong piece: a tune where the brief asked for a bed, a
groove where the brief asked for grief. Two declarations close that gap, and both are data.

| Declaration | The question it answers | Where it lives |
|---|---|---|
| `piece_type` | which rules should judge this piece? | score and direction sheet; `references/data/presets/gate/` |
| `focus` | what carries it: a line, a bed, a groove, a surface, a gesture? | score (`focus` or `meta.focus`); profiles carry a default |
| `intent` | what it is: mood, register, scene, tension, and what it must avoid? | score `intent`; `references/data/presets/intent/` |

`piece_type` is the gate profile. `focus` is the subject. `intent` is the meaning. They are separate because a
grief cue and a joyful cue can both be `cinematic` and both be carried by a drone.

## 1. Focus: name the subject before writing the arrangement

`roles.py` holds the only role vocabulary in the engine: `melody`, `lead`, `vocal`, `counter`, `chord`, `pad`,
`bass`, `drum`, `arp`, `ostinato`, `drone`, `texture`, `fx`, `environment`. A role is a function, never an
instrument. Synonyms (`harmony`, `vox`, `percussion`, `sfx`, `theme`, `riff`) live in `roles.ALIASES` and nowhere
else; `canonical()` maps them, and an unknown role raises instead of falling through to a default.

A focus is a short list of roles that may carry the piece:

| `focus` | Roles it accepts | The piece is |
|---|---|---|
| `melody` | `melody`, `lead`, `vocal` | a figure the ear follows |
| `drone` | `drone`, `pad` | a held centre, no harmonic motion |
| `groove` | `drum`, `bass`, `ostinato` | the rhythm and the low end |
| `texture` | `texture`, `pad`, `arp` | a surface that moves |
| `gesture` | `fx`, `drum`, `arp` | events in space, not a line |

Rules:

- **The focus is declared, not guessed.** A score without `focus` uses its profile's default (the `focus` block
  in the gate preset). A score that declares one that the profile does not judge gets a WARN naming both, because
  the report would otherwise apply the wrong rule.
- **A type that declares a figure must have one.** `focus.declared` FAILs when a profile expects a line and no
  track carries one, and it names the tracks the piece actually has. The fix is to write the line or to change
  `piece_type` to the type the piece really is; deleting the figure is what the row exists to prevent.
- **An effects piece says so.** `effects_only` declares an empty focus and skips the row; the report prints
  `INFO` with that reason.
- **What a focus changes.** The balance rule (accompaniment against the loudest focus track), the masking rule
  (which stems may mask the subject), the humanizer's phrasing profile, and the mix preset's level and width
  tables. A `groove` piece is not judged for lacking a tune, and its bass is not called an over-loud
  accompaniment.

## 2. The intent block

```json
"intent": {
  "emotions": ["grief"],
  "registers": ["cinematic"],
  "scenes": ["farewell"],
  "tensions": ["unresolved_dominant"],
  "must_hear": ["the cello above the room"],
  "avoid": ["drums", "major_cadence"],
  "words": ["sparse", "cold room"]
}
```

| Key | Holds | What it does |
|---|---|---|
| `emotions` | ids from `emotions.json` | the mood's numbers: mode, tempo band, energy band, forbidden gestures |
| `registers` | `cinematic`, `natural`, `documentary`, `diegetic`, `hybrid` | loudness range, crest and reverb-tail expectations for the delivery |
| `scenes` | ids from `scenes.json` | a job in the picture, its focus and its energy arc |
| `tensions` | ids from `tensions.json` | the harmonic pressure the piece should hold, with its forbidden resolutions |
| `must_hear` | free sentences | a note to the director and the mixer; nothing measures it |
| `avoid` | gesture names or any word that forbids one | measured against the notes by `intent.avoid` |
| `words` | free adjectives | kept on the score for the report; the measuring words are the four above |

Every entry of the first four kinds resolves through `synonyms.json`, so a brief may write "heartbroken",
"funeral", "barely there", "atonal", "documentary" and get the concept the engine owns. A word that resolves to
nothing is an error that lists the closest words that do resolve, and a word that resolves to two concepts of the
same kind is also an error: a small model must not be able to type a mood the engine has no meaning for.

`compose.py` accepts the block in a brief. It fills only what the brief left empty: the emotion, the focus (a
`farewell` is a drone, not a tune) and the intensity from the scene's own arc. Anything the brief states itself
wins, and the resolved block travels onto the score, where the gate reads it.

CLI:

```
python scripts/intent.py check             # the vocabulary against compose.EMOTIONS and the gestures
python scripts/intent.py list              # every concept, its focus and its forbidden gestures
python scripts/intent.py explain grief     # one word: what it means here
python scripts/intent.py resolve "a cold, sparse farewell under a drone"
```

## 3. The two rows

| Row | Reads | PASS | FAIL |
|---|---|---|---|
| `intent.vocabulary` | the declaration | every word resolves to one concept | a word resolves to nothing, or to two concepts of one kind |
| `intent.avoid` | the notes against the forbidden gestures | every measurable forbidden gesture was looked for and is absent | a forbidden gesture is in the score, named with the track and the count |

Gestures with a score-side measurement: `drum_kit`, `four_on_floor`, `bright_staccato`, `major_cadence`,
`thin_texture_throughout`, `min_silence_long`, `sudden_loud`, `steady_pulse`, `wide_range`,
`pedal_drone_throughout`, `cut_synced_hits`. Any other gesture in `avoid` is reported as a **WARN** naming it as
unmeasurable: a declaration is never passed by silence.

A declaration is a promise, not a lever. If `grief` forbids `major_cadence` and the piece ends on its tonic
major triad, the row FAILs and the fix is the last two bars, not the emotion.

## 4. Adding a word or a gesture

1. Add the concept to the matching file in `references/data/presets/intent/`, with `character`, `sources` and its
   forbidden gestures. A scene also needs `focus`, `register` and a three-point `energy_arc`.
2. Add the synonyms that should reach it to `synonyms.json` as `[kind, id]` pairs; a gesture is
   `["gestures", "<name>"]`.
3. Run `python scripts/intent.py check`. It rejects an emotion `compose` cannot play, a scene whose focus is not a
   focus, a forbidden gesture that is not a gesture, and a register missing its bands.

A new gesture needs an entry in `intent.GESTURES` and, if it should be checkable, a measuring function in
`intent.MEASURE`. Without the function it is reported unmeasured, which is the honest state, not a pass.

## 5. What this cannot do

- It cannot hear. A well-declared piece can still be dull; `listen.py` and the director's ear remain the judge.
- `must_hear` and `words` are not measured. They are for the report and the mixer.
- The vocabulary is the engine's meaning, not a musicological one: `grief` is a set of numbers and forbidden
  gestures, and the character sentence is prose, not a test.
