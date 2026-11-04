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

## 2. Write the direction sheet the way a cue is actually decided

The sheet is the brief turned into things that can be checked, in the order a cue is decided. It is the template
`templates/direction_sheet.json`, copied to `<dir>/direction/direction_<title>.json` and filled. Nothing in it is
optional decoration: the project gate rejects a sheet whose `sections` overlap, whose `hits` disagree with
`hits_at`, or whose `video` block claims a picture it cannot name.

### 2.1 Decide in this order

A director does not start from the notes. Ryan Leach puts the three principles in strict order: **how it feels
first, how it fits the picture second, thematic unity third** - "if the music is the wrong mood, none of the other
elements matter", and a perfect motif in the wrong mood is worthless. So:

1. **What the job is** (`purpose`, `job`, `audience`). ArtofComposing calls this the first rule of spotting:
   decide what the music is supposed to do, then write it down. A cue that does two jobs badly is worse than one
   that does a single job precisely.
2. **What the music knows** (`point_of_view`). The camera only knows what it has seen; the music may foreshadow.
   ArtofComposing names the trap: the same happy figure that sets up a character's fall is foreshadowing, the same
   figure one scene too late is a spoiler. Write the point of view down, because it is what forbids a choice later.
3. **Where it starts and stops** (`in_point_s`, `out_point_s`, `duration_s`). Start on the desired effect, not on
   a bar line; sometimes the cue has to sneak in behind sound effects rather than announce itself.
4. **The arc** (`sections`). Berklee's film-scoring material: form is what separates film music from concert
   music, and "the drama shifts, so must the music". Mark sections in seconds, with what the picture does and what
   the music does, and let the sync points be the section starts.
5. **The palette, then the motif** (`instruments`, `avoid_sounds`, then `motifs`). Palette before theme: a motif
   in the wrong instrument is a costume change, not an idea.

### 2.2 Spotting: the four markers

If there is a picture, watch it once, end to end, and mark four things. This is the spotting session, and its notes
are the sheet:

| Marker | Goes into | What it is |
|---|---|---|
| start | `sections[0].start_s`, `in_point_s` | where the cue enters, chosen for the effect (sneak in, or land on the cut) |
| end | `out_point_s`, `ending` | where it leaves, and how: `hard_out`, `tail_out` or `combination` |
| hit | `hits_at` + `hits` | a moment the music must land; hard (a cut, an explosion) or soft (a head turn, a line ending) |
| descriptive | `sections[].action`, `notes` | a line of dialogue, a look, a shape in the frame - a reminder, not a sync point |

Berklee's distinction is the one that matters for the gate: a **hard sync point** "needs to occur on a specific
frame" (an explosion, a punch, a cut); a **soft** one "doesn't have to be accurate to a specific frame". The same
split appears in the sheet as `hits[].sync`, and in the picture path as the cut-sync window versus motion hits
that are never judged against cuts.

Endings are not decoration either. A **hard out** ends on an accent and hands the frame to the sound effects; a
**tail out** fades on a long note so the music leaves unnoticed, and is what most cues do; a **combination**
accent then fades, which is what lets an editor extend the scene later. Film underscore almost never uses the
repeat-and-fade of a pop song.

**Err toward more sync points than fewer, then thin them.** Leach: students afraid of "Mickey Mousing" end up
hitting too little and "the music barely feels like it belongs at all"; a hit "doesn't have to be hit forcefully
- simply acknowledging a moment with a chord change on time" is enough. The other half of the same rule: the music
should not simply echo what the audience can already see. Hit the structure, not the emotion the actor is already
playing.

No cut? Then spot what you were given: a script, a list of scenes, a mood brief. One sheet per cue, seconds written
out. For a game, the same sheet describes states instead of timecode (section 5).

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
`hits_at`. Nothing else in the sheet is a gate row, and that is why the blocks below matter: they are what stops
a technically green cue from being the wrong cue.

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
- **Bar-grid and timestamp math:** At a fixed `BPM` in `N/4` time, one bar is `N * (60.0 / BPM)` seconds. Align section boundaries and structural downbeat hits to exact bar lines, and verify that `motifs[].first_at_s`, `hits[].t`, `hits_at`, and `mix_intent.must_hear` all state the exact same timestamp for an event (never say a motif enters at 18 s in `motifs` while logging its first strike at 15 s in `hits`).
- **One canonical track name:** The keys in `spatial_staging` must match the track `name` (or custom preset name) in the score 1-to-1 so stage validation and Z-separation checks never miss a part.
- **No false `avoid_sounds` collisions in `action`:** Do not write a forbidden sound word (from `avoid_sounds`) into positive descriptive fields (`sections[].action` or `music`) where a parser or reader could mistake it for a requested cue element.
- **`leave_free_hz` is for speech only:** Only set a broad midrange pocket (such as `[250, 3800]`) when `video.dialogue.present` is `true` or a voice-over is present. For pure music cues, leave `leave_free_hz` empty (`[]`) so the fundamental midrange of strings, winds, and horns is not hollowed out.

### 2.4 Size and ending follow the picture

Berklee's context rule is the one to keep in the sheet's `sections`: **the further the camera is from the
subject, the bigger the music may be**. A helicopter wide of a mountain can hold a lot of orchestra; a close-up of
a hand cannot. Interiors and exteriors work the same way, and the practical reason is dialogue: in the Jurassic
Park helicopter scene the score drops in size whenever the camera is inside, because that is where the talking
happens. "If your music doesn't get softer for the quieter moments, the dubbing mixer will pull the music stems
down at the dub" - which means the cue loses its climax and nobody hears why.

So write the shot into `sections[].action` and let `energy` follow it, not the other way round.

### 2.5 References in words, never a temp track

A temp track is reference music an editor lays under the cut to test the mood. It causes "temp love": the
attachment that makes an original score feel wrong by comparison, and the reason composers are often asked to
imitate it (Sadoff, 2006, on the music editor and the temp track). Two consequences for the sheet:

- `references` takes **words**: "a slow cello line over a soft pulse, like the opening of a documentary", never a
track name and never a melody that belongs to someone. The writing has to be original for legal reasons and
because a copy is a locked door.
- When the user sends a temp track, read what the brief actually wants from it (the texture, the tempo, the
space) and write that into the sheet. Then judge the draft against the sheet, not against the temp.

**Read the brief's words before the sheet.** Separate the mood ("motivational", "adventure", "melancholy") from the
way of playing it ("slow", "reverb", "sparse", "driving"). The mood sets mode and tempo; the modifiers set energy,
room and density. When a mood and a genre disagree on tempo, the mood wins 2:1. `compose.py` prints what it read in
`meta.mood_notes`, and `describe()` prints the mood, the energy and the room; check that line before you render.
The full mapping is in `emotion-and-scoring.md` section 1a.

### 2.6 Direction to picture: the `video` block

When the cue is written against a cut, the picture decides six of the sheet's values and the rest stay hand
decisions. `scripts/video_score.py` probes the file and fills the same sheet the template describes:

| The picture gives | The sheet field | How |
|---|---|---|
| median cut interval | `tempo_bpm` (one number) | taken as 1, 2, 4 or 8 beats, frame-locked when the preset asks |
| cuts | `hits` with `kind: cut`, `sync: hard` | on the frame; judged against the cut list |
| movements inside a shot | `hits` with `kind: motion`, `sync: soft` | never judged against cuts |
| mean luminance | `mode` | dark reads minor, bright reads major |
| horizontal centre of motion | `spatial_staging` azimuth of lead and pad | so the music follows the action across the frame |
| motion, binned | `sections` | labelled from `direction_map.energy_sections` |

What the block carries (all of it from `references/data/presets/video/default.json`, none of it from code):

| Key | Holds |
|---|---|
| `enabled` | `false` for a music-only piece; `true` only when a picture exists |
| `source`, `in_s`, `out_s`, `fps`, `duration_s` | which file, and the part of it this cue covers |
| `cuts`, `cuts_count`, `cut_source`, `motion_hits` | the candidate cut list, and which detector produced it |
| `cut_sync` | `early_ms`, `late_ms` - the sync window the hits are judged in (ITU-R BT.1359) |
| `dialogue` | `present`, `duck_db`, `snr_min_db` - whether the music has to get out of the way, and by how much |
| `master_profile`, `deliverable` | `streaming`, `broadcast` or `cinema`, and the container/codec the mux writes |

A music-only sheet keeps the block with `enabled: false` and nulls, so the reader can see the question was asked
and answered. A sheet with `enabled: true` must name its `source`, its `fps`, its `master_profile` and its sync
window; the gate checks that.

The four picture rows (`video.duration_lock`, `video.cut_sync`, `video.dialogue_snr`,
`video.master_compliance`) run in addition to every music row, and the music is a normal score, so nothing here
relaxes anything. The full path, the per-stage files and its honest limits are in `video-scoring.md`.

### 2.7 Stage the ensemble in 3D space and spectrum

A headphone or orchestral mix turns muddy when parts that share the midrange (`500–4000 Hz`) sit in the same spot
during the climax. Stage `spatial_staging` (and the matching instrument presets) using physical acoustic rules:

- **Angular separation in the climax (`spatial.z_separation`):** Any two parts that play simultaneously in the
  `500–4000 Hz` band during the loudest quarter of the piece must be separated by **at least `25 deg` in azimuth**
  OR **at least `15 deg` in elevation** (when binaural/immersive rendering is active). Do not cluster basses,
  celli, low woodwinds, and percussion all within `-20..+20 deg` at `0 deg` height.
- **Pinna height cues need > 4 kHz energy (`imm_band`):** Human vertical localization relies on pinna spectral
  notches above `4 kHz` (`6–9.5 kHz`). Never place naturally dark instruments with little energy above `4 kHz`
  (French horns, low brass, warm low pads) at `elevation >= 15 deg`—keep them at `0..12 deg` and separate them by
  azimuth instead. Reserve `elevation >= 15 deg` (`+18..+45 deg`) for sources with natural high-frequency overtones
  or air (violins, violas, upper flutes, harp harmonics, celeste, overhead canopy ambience).
- **Anchor the floor (`imm_height_rules`):** Bass and drum roles must always sit at `elevation: 0.0`.
- **One owner per frequency pocket:** Give sub-bass (`< 120 Hz`) to one primary foundation part (e.g., basses or sub)
  and high-pass higher melodic/sparkle tracks so low-end noise never accumulates across stems.

## 3. Decide in the order listeners weigh cues

Juslin and Laukka's reviews and Eerola, Friberg & Bresin (2013) tested six cues (mode, tempo, pitch register,
dynamics, articulation, timbre) on four composed excerpts with 46 listeners. The findings that matter for you:

- **Mode is the strongest cue** for happy and sad (unique explained variance about 0.5 each). Tempo, register,
  dynamics, articulation and timbre follow, in that order overall.
- **Dynamics** mattered most for scary and peaceful, and barely for happy or sad. Do not rely on loudness alone.
- The cues **add up** (additive); their two-way interactions were not significant. So each cue you set in the
  right direction helps, and one cue pointing the wrong way cannot be fully cancelled by the others.
- Limits the authors stated: four excerpts, harmony and melodic contour not varied systematically, three timbres,
  self-report only.

So decide in this order: **mode, tempo, register, loudness arc, articulation, timbre**, and make them agree. For
a mixed feeling (bittersweet, anxious hope), pick the main feeling's mode and tempo, and borrow one cue from the
other feeling. Do not average.

### Why sound moves people (Juslin's mechanisms)

Juslin's reviews list mechanisms, and each one suggests a different use in a scene:

| Mechanism | What it does | Use it for |
|---|---|---|
| Brain stem reflex | sudden, loud, dissonant or fast sound signals urgency | hits, stings, the reveal |
| Emotional contagion | the listener mirrors an emotion the music expresses; slow, low, soft and voice-like = sad; fast, loud, harsh = agitated | the emotional colour of a whole cue |
| Musical expectancy | a delayed resolution or an unexpected chord builds tension and release; it needs several seconds to work | build-ups, the wait before a reveal |
| Evaluative conditioning | a theme repeated next to a character or event becomes associated with it; slow to form, lasting | leitmotifs |
| Visual imagery | the listener's images fill the gaps; in film the picture does most of this, so the score should reinforce, not repeat it | scene mood |
| Episodic memory | a personal memory; the composer cannot target it | period style only, as a hint |

The fetched review lists six of these. Juslin's full framework also includes rhythmic entrainment (the body moves
with a steady beat) and aesthetic judgment. Those two are from background knowledge, not from the fetched text.
The practical point stands: a steady beat entrains (a trailer, a workout), and a clear expectation is what makes a
delayed resolution land.

### 3.1 Write lines, harmony and rhythm that behave like players, not a grid

When writing or directing a custom score, shape every part so it obeys human performance physiology and cognitive
expectation (the rules enforced by `pattern_audit.py` and `quality_gate.py`):

1. **Melodic arch and Meyer's Gap-Fill Law (`melodic_contour_feel`):**
   - Human vocal and instrumental lines (`melody`, `lead`, `counter`) are predominantly conjunct: keep **at least
     `45%` of intervals stepwise** (`<= 3` semitones).
   - Never write a mechanical sawtooth zig-zag (alternating up and down on every note; keep direction reversals
     well under `75%`). Shape phrases as rising and falling arches of 2–4 notes in one direction before turning.
   - When a melody makes a large leap (`>= 5` semitones), recover by reversing direction with stepwise motion
     (`1–2` semitones) rather than leaping again in the same direction.
2. **Melodic surprise and rhythmic variety (`melodic_information_entropy`, `pattern.melody_notes`):**
   - A melodic or counter-melodic line needs genuine interval variety (**Shannon entropy `H >= 1.15 bits`** across
     at least 4–5 distinct interval sizes)—never toggle back and forth between two pitches or repeat one interval
     cell mechanically.
   - Use **at least 3 different note durations** (e.g., quarter, dotted quarter, eighth, tied half) and start
     some phrases off the beat or with a pickup so `< 85%` of notes land dead on the beat grid.
3. **Phrase respiration and bow/breath gaps (`bow.breath_gap`, `kinematic_effort_feel`):**
   - Winds, brass, bowed strings, and voices need room to breathe or change bow: leave a **`0.15–0.30` beat rest**
     at phrase ends (at least once every 4 bars).
   - Couple effort to pitch: as a phrase climbs to its melodic peak, raise velocity (`+5..+12%`) rather than
     letting high notes drop limp.
4. **Common-tone voice leading and tension resolution (`spiral_tension_arc`, `harmonic_resolution_feel`):**
   - When moving between sections or harmonic regions, preserve **at least one common tone or a shared pedal
     pitch** across 2-bar windows so the tonal center of effect moves smoothly (`momentum <= 1.45`) instead of
     teleporting across unrelated triads.
   - Any dissonant non-chord tension note in a melody (minor 2nd or major 7th against the active harmony) must
     resolve by step (`1–2` semitones) on the very next note.
   - Unless the cue is an intentional cliffhanger, resolve the final 2 bars into the home tonic triad.
5. **Groove pocket and ostinato breathing room (`groove_pocket_lock`, `witek_groove_curve`, `pattern.loop_short`):**
   - Lock rhythmic patterns (`drum`, `bass`, `arp`) into a consistent 1- or 2-bar pocket (`autocorrelation >= 0.30`),
     but include syncopated off-beat pickups (`0.4 <= BSI <= 4.8` per bar) so the rhythm invites human prediction
     rather than marching dead on the grid.
   - Never run a static ostinato or drum loop unchanged for the entire cue: vary the figure every 4–8 bars, and
     thin or drop the percussion at the peak or turn so the climax and final bars feel earned.
6. **Register hygiene and climax weight (`low_interval_mud`, `cochlear_roughness`):**
   - Below `F3 (MIDI 53)`, keep chord intervals wider than a major 3rd (`>= 5` semitones; use open roots, 5ths,
     and 10ths) to prevent low-mid mud.
   - In high-energy or tense climaxes, build power from **low-octave brass/bass weight and rhythmic drive**, not by
     stacking multiple dissonant chromatic lines in the `500–4000 Hz` critical band (which creates shrill Plomp-Levelt
     roughness). Keep fast rising tension figures in a single voice or clean octave pair over an open-fifth pedal.

## 4. Build the picture's moments (hits, risers, silence)

Professional trailer and cinematic impact sound, from the sound-design sources reviewed:

- **Hit (impact):** start with a kick or taiko sample and cut its highs. Stack layers from low to high (a sub,
  then a boom, then metal or orchestral percussion for the top). EQ each layer separately so they do not clash.
  Add distortion, then EQ and compression, then reverb. The transient lands on the frame; the tail carries it.
- **Riser:** climb in pitch or filter over several bars, and get faster and louder. It peaks on the cut.
- **Silence before the hit:** end the riser, leave a short gap, then hit. The gap makes the hit land harder.
- **Braam:** a long, loud, low brass note (around C1 to C2), stacked in octaves (C0, C1, C2), pitched down, given
  distortion and reverb. Put it on cuts that mark a transition.
- **Sub drop:** a low layer under the hit, EQ'd separately. Felt more than heard on a large system.

In a score these are: a `rise` (reverse cymbal + roll) at `t`, a `silence` (everything drops), an `impact`
(timpani + crash + boom) at the exact beat. `compose.py` hit points do this. For custom placement use
`direct.add_line` (for a stab or fanfare) or `direct.add_pulse` (for the grid under it).

## 5. Adaptive music (games, interactive pieces)

Writing for a game is writing for a player who controls the timing. Two techniques, from adaptive-music practice:

- **Vertical layering:** one base loop plays all the time; stems fade in or out when game events happen. All the
  stems run together, so a muted stem keeps looping in sync and can come back at any point.
- **Horizontal re-sequencing:** separate sections (intro, loop, outro) switch into one another, with fades to
  soften sharp cuts.
- Combine them: loopable stacked stems that switch sections and add layers.
- Sync every transition to a bar or a beat, set the tempo and meter once, and make the first beat after a
  transition clean.
- Write loops of roughly one to two minutes that can start at almost any bar, because the player may return at any
  moment.

Direction for this: one key and one tempo for every state, three intensity states built with
`compose.py --intensity 0.3 / 0.6 / 0.95 --loop`, and a sheet for each state. Run `listen.py` on each state, since
the calm state must not read tense and the intense state must not read sad.

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

### 6.1 Score, spatial and psychoacoustic gate levers

When Stage 2 or Stage 6 of `pipeline.py` flags a symbolic, spatial, or psychoacoustic gate row, pull one surgical
lever:

| Gate row | First lever | Second lever |
|---|---|---|
| `melodic_contour_feel` (low stepwise % or sawtooth flips) | replace alternating up/down intervals with a smooth 4–6 note unidirectional arch (`>= 45%` steps of 1–3 semitones) | add passing tones after any leap `>= 5` semitones so leaps recover by step in the opposite direction |
| `melodic_information_entropy` (`H < 1.15` or ungrounded leaps) | vary the interval sequence so at least 4–5 distinct interval sizes appear across the phrase | follow any large surprise leap (`> 4.2 bits`) with 2–3 predictable stepwise notes |
| `pattern` (`only 2 note lengths` or `on_beat > 90%`) | mix at least 3 note durations (e.g., eighth, quarter, dotted quarter, half) | shift 20–30% of phrase starts to off-beat pickups or ties across the bar line |
| `spiral_tension_arc` (teleportation at bar $N$, or outro strain) | add a sustained common-tone pedal (tonic or 5th) across the bar boundary, or insert a diatonic pivot chord | ensure the final 2 bars cadence cleanly onto the home tonic triad |
| `witek_groove_curve` (`BSI < 0.4` or `> 5.5`) | if `< 0.4`, add off-beat 8th/16th pickups before strong beats in drum/bass/arp; if `> 5.5`, anchor beats 1 and 3 | adjust velocity accents on syncopated pickups so they clear `85%` of the track's median velocity |
| `spatial.z_separation` (midrange climax collision) | widen azimuth separation between the colliding pair to `>= 28 deg` in both `spatial_staging` and the presets | give the higher-register part an elevated arc (`+18..+35 deg` elevation) and set `"binaural": true` |
| `imm_band` (lifted stem holds `< 0.3%` energy above 4 kHz) | lower the dark instrument's `elevation` below `15 deg` (`0..12 deg`) and separate it by azimuth instead | if the part is meant to sparkle (e.g., celeste, harp, bells), raise its `gain_db` or high-shelf EQ above `4 kHz` |
| `cochlear_roughness` (sustained critical-band clash) | thin overlapping chromatic voices in `200–4000 Hz` so chord tones sit at least a minor 3rd apart | move one clashing part up or down an octave, or lower the secondary counter-line by `3–4 dB` |
| `erb_binaural_masking` (bed masks lead in ERB band) | increase `spatial.azimuth` separation between the lead and the masking bed | add a narrow subtractive EQ cut (`-3 dB` at the flagged ERB frequency) on the masking bed in the mix preset |
| `ambient_bed` (dropout or rapid gain pumping) | smooth `gain_curve` ramps and sidechain ducker release (`release_ms >= 1600`, `duck_db >= -3.5`) | reduce sudden transient burst gain inside the environment preset so the bed glides smoothly |

Two rules that stop revision from going round in circles:

1. **A second change to the same target that does not move it means the lever is wrong.** Try a different lever
   from the same row, or the row below it.
2. **A FAIL on `feel` is a question, not a verdict.** earshot is a model. Listen to the file yourself if you can,
   or tell the user what the numbers say and ask them to listen.

## 7. What earshot can and cannot hear

earshot (MIT, github.com/Leonxlnx/earshot) listens with two open models: CLAP (text-audio similarity, "does this
sound like X") and AST (AudioSet tags), plus measurements. It is a real second opinion, and it is not a human ear.

**Use it for:**
- the forced choice: a feel word against the opposite words, as a percentage, which is the sharpest test (the
  wanted word has to win more than half of it; `listen.py` reports FAIL when an opposite word wins);
- what the piece sounds like in ranked readings (genre, mood, instruments);
- pulse clarity (is there a steady beat?), tempo, key, onsets (do the hits land?);
- comparing two versions of the same cue, A against B.

**Know its limits:**
- Mood labels are wrong about one time in five on test material (earshot's own figure). A single reading is not a verdict.
- Readings are not exclusive: a piece can read "triumphant" and "sad" at once. The forced choice is the sharper test.
- Tempo estimates can read double or half. With no pulse (clarity under 0.15) there is no tempo to trust.
- Key estimates with r under about 0.6 are weak.
- It cannot judge taste, melody, lyrics, cultural authenticity (a raga or a maqam) or whether a clean synth tone
  is "real". A "code-synthesized" realness reading is information, not a fault, for sample-based music.
- An instrument it does not name is not proven absent. Check the instrument's loudness and register first.

**Setup:** earshot is a separate install (torch, about 1 GB of models, an ffmpeg on the path). `scripts/listen.py`
works without it and says so (measurements only). See `scripts/setup_project.py` (`--ears` for earshot).

## 8. Directing by genre and situation

The concrete recipes (with brief JSON, direct calls and a sheet for each) are in `references/workflow/scene-recipes.md`:
trailer or reveal, sad voice-over, calm explainer, tense thriller, joyful end card, adaptive game loop, jingle,
sleep and meditation, playful, and traditional idioms (with the limits named).

## 9. Delivery

Deliver:
- the master WAV (and the MIDI, which is the score in any DAW);
- the direction sheet, filled in;
- the `listen.py` report in plain words: which targets pass, which still check, what earshot heard;
- one or two named variations if the brief was open (another seed, another mode, another tempo);
- one line on what was not checked (taste, the sound of the actual instruments, how it sits in the final video).

Do not say "it sounds like an orchestra" or "it is natural". Say what the sheet asked for, what the listen report
found, and what is left.

Sources: Juslin & Laukka (2003) and Juslin's mechanism review (Behavioral and Brain Sciences, 2008, "Emotional
responses to music: the need to consider underlying mechanisms"); Eerola, Friberg & Bresin (2013), Frontiers in
Psychology, "Emotional expression in music: contribution, linearity, and additivity of primary musical cues";
Ableton's guide to cinematic impact sounds (braams, hits, risers); Guy Jones on adaptive music (gamedeveloper.com);
IRPR Sound glossary on vertical layering and horizontal re-sequencing (could not be fetched in this session; the
definitions here come from the adaptive-music article); beverlyboy.com on spotting sessions; earshot README and
docs (github.com/Leonxlnx/earshot).

The director's method in section 2 was read from: artofcomposing.com/how-to-spot-a-film (first rule of spotting,
what the music is supposed to do and what it knows, cue start / end / hit / descriptive markers, silence as the
strongest hit, hit points as a focus list); online.berklee.edu/takenote/5-film-scoring-concepts-to-know-for-your-
first-movie-score (form follows picture, kinetics, hard vs soft sync points, hard out / tail out / combination,
size following shot distance and interior/exterior, the dub pulling music down under dialogue);
ryanleach.com/blog/2015/08/05/the-three-fundamental-principles-of-film-scoring (mood first, fit to picture second,
thematic unity third; hit more than feels safe, and do not echo what the screen already says);
behindthescore.org/articles/motivic-development-in-film-composition (motif transformations: repetition, variation,
inversion, retrograde, augmentation, diminution, transposition, canon); soundtrack.academy/temp-tracks and R. H.
Sadoff (2006) on the music editor and the temp track, cited from the JSTOR abstract, for "temp love" and why a
reference is written in words; soundbridge.io/spotting-session-film (the spotting notes cover cue in/out and the
moments the music must coincide with, and they change as the edit changes).