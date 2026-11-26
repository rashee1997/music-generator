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

A **hard sync point** must land on a specific frame (an explosion, a punch, a cut); a **soft** one may drift. The same split is `hits[].sync`, and the cut-sync window versus motion hits in the picture path.
A `sync: hard` hit also opens a +-150 ms gate window where the level drop is not a defect; as `kind: cut` it stops the sustained voices on a 15 ms ramp (`quality-gate-rows.md` section 8); a hard accent over held strings is `kind: musical`.

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
| `piece_type` | which gate profile judges it; declare it rather than letting keywords guess | `cinematic`, `groove`, `ambient` |
| `focus` | what carries the piece: a line, a bed, a groove, a surface or a gesture | `drone` for a farewell, `groove` for a beat with no tune |
| `intent` | what it is, in words the engine owns: emotions, register, scene, tensions, what to avoid | `{"emotions": ["grief"], "scenes": ["farewell"]}` |

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
| `expression` | how it is played and heard: `sonic_picture`, `performer`, `producer_moves`, `anti_generic`, `cues`, `theme` (2.11) |
| `immersive` | whether the field is doing a job, and how: `why`, `engine`, `anchors`, `movers`, `height`, `room_changes`, `deliverables` (2.10) |
| `delivery` | `format`, `sample_rate`, `bit_depth`, `stage` (`web`, `broadcast`, `cinema`), `output_targets` (the score names the same set) |
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
- **A film composer's or a film's style is a list of devices, not a name.** Write what the sound is made of: "a sustained
  pipe-organ pedal under a rising pulsed arpeggio, low brass swells at the turning points, a simple theme that returns
  larger, a hard cut into silence". Do not write the composer, the film or a melody of theirs into the sheet or the score
  (the sheet is words, the writing is original). A "like X" brief is read into those devices in the craft pass
  (`references/workflow/director-craft.md` section 1) and the research note.
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

### 2.8 Declare what the piece is, then what it plays

A sheet that names only notes and tempo can be played correctly and still be the wrong piece. Three fields prevent
that, and they are checked rather than trusted:

- **`piece_type`** picks the gate profile: which rules apply, and what the subject is expected to be.
- **`focus`** names the subject: `melody` (a figure the ear follows), `drone` (a held centre), `groove` (kick, bass and
the cell), `texture` (a surface), `gesture` (events in space). The profile carries a default; write it when the piece is
not that default. `focus.declared` FAILs if the type expects a line and none is there, and names what the piece has.
- **`intent`** is the meaning, as data: `emotions`, `registers`, `scenes`, `tensions`, `avoid`, `must_hear`, `words`.

Every word resolves through `references/data/presets/intent/synonyms.json` to a concept the engine owns, so "heartbroken"
or "funeral" works and an invented mood name is an error that lists the closest words. A concept carries its forbidden
gestures with it (`grief` forbids a major cadence), which `intent.avoid` measures against the notes. The vocabulary, the
row behaviour and how to add a word: [`intent-and-focus.md`](intent-and-focus.md).

### 2.9 When the palette is sampled (SFZ): direct for naturalness, not for realism

An SFZ library sounds recorded and still sounds played by a machine, because the machine part is what the renderer sends it.
The SFZ path carries **one MIDI channel**: timing, velocity, strum and the articulation gate are humanized exactly as on the
GM path, and one controller curve carries dynamics every 15 ms. It does not send per-note vibrato, a per-note expression
arch, a pitch scoop or a glide (`AGENTS.md` 3b lists the whole split). So direction moves the arc into the places the sheet
already controls:

| The sheet says | What the SFZ path turns it into |
|---|---|
| `instruments` naming a patch family per part | which sample set plays: sustain, staccato, marcato, pizzicato, tremolo, legato or key-switch |
| `sections[].music` naming articulation | every note's `"art"` - the attack of a staccato chord and a sustained line are different recordings, not one sample at two lengths |
| `energy` and the score `dynamics` arc | the one continuous controller curve; without it the part holds one level from first note to last |
| `space` | the room the dry free sets have none of; a dry SFZ stem is a bug, not a close sound |
| `spatial_staging` | azimuth and distance per part, so sampled and procedural stems sit in one room |

Two consequences for the direction sheet itself:

- **Write the articulation plan, not just the notes.** A cue that wants a soaring line and a chattering accompaniment needs
  two patches and an `art` on the notes; asking one sustain patch to do both is the single most audible sample tell.
- **A sustained solo is a declared limit.** Nothing in the SFZ path shapes inside a note, so a long solo flute or violin note
  keeps its looped sample level. If that flatness is exposed in the mix, direct that line to the GM path (it gets per-note
  vibrato and an envelope) or the vocal engine, and write which ran in the sheet's `notes`.

Judging it: `listen.py` still judges mood, pulse and form (it cannot hear sample looping), so add the measurements that can -
`naturalness_check.py` reports `spec_flux` and warns when the timbre is static, and the `modulation_flutter` gate row reports
6-25 Hz choppiness on pad, melody, lead and counter stems. Both are proxies: a WARN on a sampled stem is a question about
articulation and patch choice, not a number to lower.

### 2.10 Directing in space: Immersive 2.0

Whether the field does a job, which parts move and why, the height plan, the room changes and the deliverables
that carry them are decided in [`directing-space.md`](directing-space.md); the numbers they describe live in the
presets, never in this sheet.

### 2.11 How the music is played and heard: the `expression` block

This is the entry point of the whole piece. A sheet that says what the cue must do (`job`, `energy`, `feel`) still leaves
the agent to invent what it sounds like, and an agent left to invent writes the generic version: a pad, an arpeggio and a
drum loop in the right key. A human producer decides how the music is *played* before a note exists. Write these
before the score; they are read by `quality_gate.direction_rows` and by `scripts/helpers/expression_report.py`.

| Field | Decide | The test it can fail |
|---|---|---|
| `sonic_picture` | stand in the room: what the listener hears in the first ten seconds, in the middle and in the last note, in plain physical words (distance, size, materials, who is near) | the score's first ten seconds contain what it says |
| `performer` | who plays each part and what a human does: where the player breathes, leans on a beat, lets a note die, plays slightly behind or ahead; how many players share a section part, and whether the same player is the same player all piece | `humanize`, `mood`, `articulation` and, for a section, `ensemble` are set to say it |
| `producer_moves` | what a producer does that a score does not say: a filter that opens over sixteen bars, a full stop before a hit, a reverb throw on the last note | each move has a preset key or a score event |
| `anti_generic` | the generic version of this cue in one sentence, and the one thing that stops this cue being it | the sentence names a measurable difference (a pulse that changes, a leap on a weak beat) |
| `cues` | per section: `arousal` (low, mid, high), `mode_register`, `tempo_trend`, `dynamics`, `articulation`, `timbre` (what changes in the colour when the section gets loud, not only how much louder it gets) | `expression.arousal_order` compares the written notes with the sections' `energy`; realism report dimension 1 measures the colour |
| `theme` | the melody's identity: `contour`, `interval_character`, `rhythm_cell`, `why_memorable`, `variation_plan` (how it changes each time it returns) | `melody.variety` measures interval entropy, range, leaps and bars that repeat exactly |

The cue table follows the research on what carries emotion in music: mode, tempo, register, dynamics, articulation
and timbre, acting mostly additively (`knowledgebase/genre-and-feel/emotion-cues.md`). Decide all six per section; a
section that leaves one open gets the default of the last section, which is how a tense cue ends up calm.

Rules:

**Theatrical realism is decided here, not fixed in the mix.** Three declarations carry it and all three are read by
the engine: a part whose colour changes with loudness says so with `timbre_dynamics`; a section says how many
players it has with `ensemble`; the score says how the bar breathes with `elastic`. If the sheet's `performer` field
cannot say which of those applies, the piece has not decided how it is played. The facts and the working figures are
in `knowledgebase/sound-design/theatrical-realism.md`; the rules and the blocks are in
[`theatrical-realism.md`](../mixing/theatrical-realism.md). Measure the result with
`python scripts/realism_report.py` after the render, and put its WARNs in the director's second review.

1. **Write the theme as a shape, not a mood.** "Heroic" is not a theme. "A rise of a fifth, a step back, then a fall,
   long-short-short-long, the leap on the weak beat, inverted at the return" is one. A melody an agent writes without a shape
   is the average of every melody it has seen.
2. **Every return of a motif changes one thing** (interval, rhythm, register, harmony, instrument) and keeps another. The
   plan says which, in `theme.variation_plan` and in `motifs[].returns`.
3. **Name the human act.** "Violins sustain" is a patch. "The violins enter late, swell with the bow and drop off before the
   change" is a performance, and it becomes `dynamics` in the score and `articulation` on the notes.
4. **The generic version is named so it can be refused.** If the score's first idea is the sentence in `anti_generic`, rewrite it.
5. **What the metrics cannot say stays said.** `expression_report.py` measures arousal cues and melodic variety from notes.
   It does not measure valence, taste or whether the theme is good; say so in the report.

### 2.12 The craft pass

After the sheet is filled and before any note, answer the six questions in [`director-craft.md`](director-craft.md) section 1:
the hook, the arc, the density map, the lanes, the contrast and the ending. Each answer goes into a field above
(`motifs`, `sections`, `mix_intent`, `expression`), so nothing new is added to the sheet. The same file lists the
failures that make a piece read as generated and the counter for each, the rules for blending traditions, and the review
after the render. A ringtone, alert or loop adds [`short-form-and-ringtones.md`](../scoring/short-form-and-ringtones.md).

Sections 3-8 (cue order, picture moments, adaptive music, revision levers, earshot, delivery): [`music-direction-revision.md`](music-direction-revision.md).
