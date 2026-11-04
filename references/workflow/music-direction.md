---
title: Music direction
summary: The director's loop: brief, direction sheet, draft, listen, judge, change one lever.
tags: [direction, sheet, spotting, hits, sections, revision, judge]
load_when:
  - before rendering any piece
  - a target misses and one lever must change
---

# Music direction: decide what the piece must do, then judge what you made

A generator makes something and hands it over. A director decides what the piece has to do, makes a draft,
listens to it against that decision, changes one thing, and listens again. This file is the director's side of
the skill. The scripts only carry the decisions out.

The rule: **the first render is a draft.** Never deliver it on the strength of the code having run.

## 1. The loop

\`\`\`
brief (what, for whom, where it plays)
  -> spotting (only with a picture: watch once, mark starts, ends, hits, and what to remember)
  -> direction sheet (job, sections, motifs, hits, feel, avoid, tempo, mode, staging, delivery, video)
     templates/direction_sheet.json
  -> draft (scripts/compose.py from a brief, or a custom script from templates/custom_score_template.py)
  -> direct (scripts/direct.py: add a pulse, a fanfare, a bass line, change a tempo or an arc)
  -> render (scripts/render_natural.py score.json, which masters too)
  -> listen (scripts/listen.py cue.wav --direction sheet.json)    measurements + earshot
  -> judge (each target PASS / CHECK / FAIL, with the numbers)
  -> revise ONE lever (section 6), render, listen again
  -> deliver (the file, the sheet, the report, what still misses)
\`\`\`

Stop when every target passes, or when two revisions in a row do not move the failing target. Then say what
is left, and do not hide it.

## 2. Write the direction sheet the way a cue is decided

The sheet is the brief turned into things that can be checked, in the order a cue is decided: `templates/direction_sheet.json`,
copied to `<dir>/direction/direction_<title>.json` and filled. The project gate rejects overlapping `sections`, `hits`
that disagree with `hits_at`, or a `video` block naming a picture it cannot find.

### 2.1 Decide in this order

Feel first, fit to the picture second, thematic unity third: music in the wrong mood is worthless whatever else it
gets right.

1. **The job** (`purpose`, `job`, `audience`): decide what the music must do, then write it down. A cue that does two
   jobs badly is worse than one that does a single job precisely.
2. **What the music knows** (`point_of_view`): the camera knows only what it has seen, the music may foreshadow. The
   same happy figure that sets up a character's fall is foreshadowing, one scene later it is a spoiler.
3. **Start and stop** (`in_point_s`, `out_point_s`, `duration_s`): start on the effect, not on a bar line; a cue may
   sneak in behind sound effects rather than announce itself.
4. **The arc** (`sections`): form separates film music from concert music; when the drama shifts, the music shifts.
   Mark sections in seconds, with what the picture does and what the music does, and let the sync points be the
   section starts.
5. **The palette, then the motif** (`instruments`, `avoid_sounds`, then `motifs`): a motif in the wrong instrument is
   a costume change, not an idea.

### 2.2 Spotting: the four markers

With a picture, watch it once end to end and mark four things. The notes are the sheet:

| Marker | Goes into | What it is |
|---|---|---|
| start | `sections[0].start_s`, `in_point_s` | where the cue enters, chosen for the effect (sneak in, or land on the cut) |
| end | `out_point_s`, `ending` | where it leaves, and how: `hard_out`, `tail_out` or `combination` |
| hit | `hits_at` + `hits` | a moment the music must land; hard (a cut, an explosion) or soft (a head turn, a line ending) |
| descriptive | `sections[].action`, `notes` | a line of dialogue, a look, a shape in the frame - a reminder, not a sync point |

A **hard sync point** must land on a specific frame (an explosion, a punch, a cut); a **soft** one may drift. The same
split is `hits[].sync`, and the cut-sync window versus motion hits in the picture path.

Endings: a **hard out** ends on an accent and hands the frame to the sound effects; a **tail out** fades on a long
note so the music leaves unnoticed, which is what most cues do; a **combination** accents then fades, so an editor
can extend the scene later. Film underscore almost never uses the repeat-and-fade of a pop song.

**Err toward more sync points, then thin them.** A chord change on time is enough to acknowledge a moment; a cue
afraid of "Mickey Mousing" ends up hitting too little and the music barely feels like it belongs. Do not echo what the
audience can already see: hit the structure, not the emotion the actor is playing. No cut? Spot what you have - a
script, a scene list, a mood brief - one sheet per cue, seconds written out; for a game the sheet describes states
instead of timecode (section 5).

### 2.3 The fields

The core targets. `listen.py` reads these directly, so fill them with words and numbers, not intentions.

| Field | What to write | Example |
|---|---|---|
| `brief` | the client's words, verbatim | "make it feel like the valley is breathing" |
| `purpose` | where it plays and what job it does | "45 s trailer opener; quiet start, hit at 24 s, reveal" |
| `medium` | what it is for | `film`, `ad`, `game`, `album`, `social`, `installation` |
| `audience` | who hears it, where, what they already know | "a festival audience, no narration, played loud" |
| `point_of_view` | whose ears we are in, and what that forbids | "the character's: no music she cannot hear" |
| `feel` | 1-3 plain words the listener must hear | `["epic", "triumphant"]` |
| `avoid_feel` | words that must lose, the nearest wrong feel | `["sad", "calm"]` |
| `instruments` | what must be audible | `["taiko", "brass", "strings"]` |
| `avoid_sounds` | what must never appear | `["drums", "choir", "bell"]` |
| `pulse` | `steady`, `loose` or `none` | `steady` for a trailer, `none` for a sad solo piano |
| `tempo_bpm` | the range the score should be in; one number only when a cut fixed it | `[96, 112]` |
| `key`, `mode` | the key, and major or minor (the strongest cue) | `D`, `dorian` |
| `energy` | 0..1 how hard it pushes, relative to the mood's own band (0.5 = midpoint, calm 0.40, epic 0.68) | `0.6` for a confident build, `0.35` for reflective |
| `space` | `dry`, `studio`, `hall`, `large_hall`, `cathedral`, or the project space preset | `large_hall` for landscape or "reverb mix" |
| `loudness_lufs` | integrated loudness for the destination | `-16` (web/video), `-18` to `-16` (film underscore), `-20` to `-18` (bed under a voice) |
| `true_peak_max` | ceiling in dBTP | `-1.0` |
| `hits_at` | seconds where a hit, a cut or a reveal must land | `[24.0, 38.0]` |
| `duration_s` | length the picture needs | `45` |
| `spatial_staging` | each part's azimuth, elevation and distance; the presets must match | `{"flute": {"azimuth": 0, "distance": 1.4}}` |

`listen.py` checks `feel` against `avoid_feel` as a forced choice and looks for an onset within 0.3 s of every
`hits_at`; nothing else is a gate row, which is why the blocks below stop a green cue from being the wrong cue.

**The director's blocks.** Each one answers a question a composer is asked out loud before writing:

| Block | The question it answers |
|---|---|
| `job` | what must the music do, in order of importance? (a list, not a sentence) |
| `story` | the cue in one sentence, first moment to last |
| `sections` | the arc in seconds: `name`, `start_s`, `end_s`, `energy`, `action` (picture), `music` (what enters and does what), `role` (`place`, `establish`, `build`, `peak`, `transition`, `button`) |
| `motifs` | the theme plan: `name`, `first_at_s`, `shape` (its few notes), `returns` (where it comes back and how it changed) |
| `hits` | the same moments as `hits_at`, each with `kind` (`cut`, `motion`, `musical`), `sync` (`hard`, `soft`), `sound`, and `why` - the reason the moment needs an accent |
| `ending` | how it leaves: `hard_out`, `tail_out`, `combination` |
| `mix_intent` | `hero`, `support`, `sits_under` (what must win), `must_hear` (audible by when), `leave_free_hz` |
| `delivery` | `format`, `sample_rate`, `bit_depth`, `stage` (`web`, `broadcast`, `cinema`) |
| `references` | the reference in words, never a track (2.5) |
| `video` | the picture this cue was written against, when there is one (2.6) |

**Sheet internal consistency (check before writing the score):**
- **Bar-grid and timestamp math:** at `BPM` in `N/4` time one bar is `N * (60.0 / BPM)` seconds. Put section boundaries
  and structural hits on bar lines, and give every event one timestamp across `motifs[].first_at_s`, `hits[].t`,
  `hits_at` and `mix_intent.must_hear`.
- **One canonical track name:** `spatial_staging` keys match the score's track names one to one.
- **No false `avoid_sounds` collisions:** do not write a forbidden sound word into `sections[].action` or `music`.
- **`leave_free_hz` is for speech only:** set the pocket (`[250, 3800]`) only when `video.dialogue.present` is `true`
  or a voice-over runs; for pure music leave it empty (`[]`) so the midrange is not hollowed out.

### 2.4 Size and ending follow the picture

**The further the camera is from the subject, the bigger the music may be.** A wide of a mountain can hold a lot of
orchestra; a close-up of a hand cannot. The reason is dialogue: the score drops in size whenever the camera is inside,
because that is where the talking happens, and a cue that does not soften for the quiet moments is pulled down by the
dubbing mixer at the dub, losing its climax with nobody hearing why. Write the shot into `sections[].action` and let
`energy` follow it.

### 2.5 References in words, never a temp track

A temp track is reference music laid under the cut to test the mood. It causes "temp love": the attachment that makes
an original score feel wrong by comparison, and the reason composers are asked to imitate it.

- `references` takes **words**: "a slow cello line over a soft pulse, like the opening of a documentary", never a
  track name and never a melody that belongs to someone. The writing has to be original for legal reasons and because
  a copy is a locked door.
- With a temp track, read what the brief wants from it (texture, tempo, space), write that into the sheet, and judge
  the draft against the sheet.

**Read the brief's words before the sheet.** Separate the mood ("motivational", "adventure", "melancholy") from the way
of playing it ("slow", "reverb", "sparse", "driving"): the mood sets mode and tempo, the modifiers set energy, room and
density. When mood and genre disagree on tempo, the mood wins 2:1; check `meta.mood_notes` (mapping:
`emotion-and-scoring.md` section 1a).

### 2.6 Direction to picture: the `video` block

Against a cut, the picture decides six of the sheet's values and the rest stay hand decisions. `scripts/video_score.py`
probes the file and fills the sheet: the median cut interval sets `tempo_bpm` (1, 2, 4 or 8 beats, frame-locked), cuts
become `hits` with `kind: cut, sync: hard`, movement inside a shot becomes `kind: motion, sync: soft` and is never
judged against cuts, mean luminance picks the mode (dark reads minor, bright reads major), the horizontal centre of
motion sets the lead and pad azimuth, and motion binned into sections labels `sections`.

| Key | Holds |
|---|---|
| `enabled` | `false` for a music-only piece; `true` only when a picture exists |
| `source`, `in_s`, `out_s`, `fps`, `duration_s` | which file, and the part of it this cue covers |
| `cuts`, `cuts_count`, `cut_source`, `motion_hits` | the candidate cut list, and which detector produced it |
| `cut_sync` | `early_ms`, `late_ms` - the sync window the hits are judged in (ITU-R BT.1359) |
| `dialogue` | `present`, `duck_db`, `snr_min_db` - whether the music has to get out of the way, and by how much |
| `master_profile`, `deliverable` | `streaming`, `broadcast` or `cinema`, and the container/codec the mux writes |

A music-only sheet keeps `enabled: false` and nulls; with `enabled: true` it must name `source`, `fps`, `master_profile`
and the sync window. The picture rows (`video.duration_lock`, `video.cut_sync`, `video.dialogue_snr`,
`video.master_compliance`) run beside every music row; the full path and its limits are in `video-scoring.md`.

### 2.7 Stage the ensemble in 3D space and spectrum

Parts that share the midrange (`500-4000 Hz`) during the climax turn muddy when they sit in the same place. Stage
`spatial_staging`, and the matching instrument presets, by the rules in `references/spatial/immersive-spatial.md`
(what may be lifted, what stays on the floor) and the `spatial.z_separation` row in `references/mixing/quality-gate.md`
§5d (25 deg azimuth or 15 deg elevation between competing pairs). Give the sub-bass (`< 120 Hz`) to one foundation
part and high-pass the higher parts so low end does not accumulate.

## 3. Decide in the order listeners weigh cues

Mode is the strongest cue for happy and sad; tempo, register, dynamics, articulation and timbre follow, and the cues
add up, so one pointing the wrong way is not cancelled by the rest. Decide in that order and make them agree. For a
mixed feeling (bittersweet, anxious hope), take the main feeling's mode and tempo and borrow one cue from the other;
do not average.

Rows and thresholds for melodic contour, interval entropy, note lengths, breath gaps, voice leading, groove pocket
and ostinato repetition: see `references/mixing/quality-gate.md` §3e, and write to them instead of fixing failures
later.

## 4. Build the picture's moments (hits, risers, silence)

- **Hit:** a kick or taiko with its highs cut, layers stacked low to high (sub, boom, metal or orchestral percussion),
  each EQ'd separately, then distortion, EQ, compression and reverb; the transient lands on the frame.
- **Riser:** pitch or filter climbing over several bars, faster and louder, peaking on the cut.
- **Silence before the hit:** end the riser, leave a short gap, then hit; the gap makes the hit land harder.
- **Braam:** a long, loud, low brass note (C1-C2) stacked in octaves (C0, C1, C2), pitched down, distorted and
  reverbed, on cuts that mark a transition.
- **Sub drop:** a low layer under the hit, EQ'd separately, felt more than heard on a large system.

In a score these are a `rise` at `t`, a `silence`, and an `impact` on the exact beat; `compose.py` hit points do this.
For custom placement use `direct.add_line` (a stab or fanfare) or `direct.add_pulse` (the grid under it).

## 5. Adaptive music (games, interactive pieces)

A game hands timing to the player.

- **Vertical layering:** one base loop runs always; stems fade in or out on events, and a muted stem keeps looping in
  sync so it can return at any point.
- **Horizontal re-sequencing:** intro, loop and outro sections switch into one another, with fades to soften cuts.
- Combine them: loopable stacked stems that switch sections and add layers. Sync transitions to a bar or beat, set
  tempo and meter once, keep the first beat after a transition clean, and write loops of one to two minutes.

Direction: one key and one tempo for every state, three intensities with
`compose.py --intensity 0.3 / 0.6 / 0.95 --loop`, a sheet per state, and `listen.py` on each.

## 6. Revision levers: what to change when a target misses

Change one lever at a time, render, listen. Each row starts with the most likely cause.

| Target misses | First lever | Second lever | Code |
|---|---|---|---|
| It reads upbeat when the brief was not | check `meta.mood_notes`: if it says "no mood word recognised", name the feel. Then `energy` and `space` | add `slow`/`sparse` words, or lower `energy` one step | `compose --emotion`, `--energy`, `--space` |
| The mood is right but the room is wrong | `space`: `large_hall` for landscape or "reverb mix", `dry` for intimate | lower the reverb return (`mix.reverb_return`) instead of the room | score `room`, `mix` |
| `feel` loses to `avoid_feel` (forced choice under 35 %) | **mode**: major for epic, triumphant, hopeful; minor/dorian for sad, tense | tempo up 10-20 BPM for energy, down for calm | `compose.py --mode major --bpm 104` |
| Forced choice is close (35-50 %) | a bigger **loudness arc** (quiet start, loud peak) | add a **fanfare or a hook** on the reveal | `direct.set_arc`, `direct.add_line` |
| `avoid` word in top 3 readings | take out the layer or the harmony that reads as the wrong feel | slow the tempo or lower the register | `direct.remove_track`, `direct.set_gain` |
| `pulse` clarity under 0.15 but `steady` wanted | add a kick on every beat from the start | make the drums `tight`, keep the tempo map flat | `direct.add_pulse` |
| `pulse` high but `none` wanted | remove drums and bar-locked ostinatos | let the phrases rubato | `direct.remove_track` |
| `tempo` out of range (double/half counts as passing) | set the score tempo | check the score bpm, not a render estimate | `direct.tempo`, `compose --bpm` |
| `instruments` not named (e.g. taiko) | add a track for the instrument, or raise its gain 3-6 dB | move it up a register | `direct.add_line`, `direct.set_gain` |
| `mode` mismatch with a weak key (r under 0.6) | do not trust the key estimate; check the sound, then decide | change the mode only if the feel check also fails | `compose --mode` |
| `hits` missing onsets | put the hit on a beat (`hit_points` snap to half-beats) | add a sub layer under the hit (+3 dB on the impact) | `compose` hit points, `direct.add_line` |
| `loudness` off | `master.lufs` in the score | a very dynamic piece may not reach a target; accept it | score `master` |
| `true_peak` hot or `clipping` | lower the master input 2-3 dB | lower the loudest stem's `gain_db` | score `master`, `gain_db` |
| `length` off | `duration_s` / bar count | a ring-out adds 2-5 s; trim the file or accept and say so | `compose --duration` |

Gate rows, thresholds and levers: see `references/mixing/quality-gate.md`.

Two rules that stop revision from going round in circles:

1. **A second change to the same target that does not move it means the lever is wrong.** Try another lever from the
   same row, or the row below it.
2. **A FAIL on `feel` is a question, not a verdict.** earshot is a model: listen yourself, or tell the user what the
   numbers say and ask them to listen.

## 7. What earshot can and cannot hear

earshot listens with CLAP (text-audio similarity) and AST (AudioSet tags) plus measurements: a second opinion, not a
human ear.

**Use it for:** the forced choice (the wanted word must win more than half; `listen.py` reports FAIL when an opposite
wins), the ranked readings (genre, mood, instruments), pulse clarity, tempo, key, onsets and an A/B comparison.

**Its limits:** mood labels are wrong about one time in five; readings are not exclusive (a piece can read triumphant
and sad at once); tempo can read double or half, and with no pulse (clarity under 0.15) there is none to trust; key
estimates with r under 0.6 are weak; it cannot judge taste, melody, lyrics, cultural fit or whether a synth is real,
and an instrument it does not name is not proven absent.

## 8. Delivery

Deliver the master WAV and the MIDI, the filled direction sheet, the `listen.py` report in plain words (which targets
pass, which still check, what earshot heard), one or two named variations if the brief was open, and one line on what
was not checked (taste, the real instruments, how it sits in the final video). Situation recipes, each with a brief,
the direct calls and a sheet: `references/workflow/scene-recipes.md`.

Do not say "it sounds like an orchestra" or "it is natural". Say what the sheet asked for, what the report found, and
what is left.
