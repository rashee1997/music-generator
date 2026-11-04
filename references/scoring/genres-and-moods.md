---
title: Genres and moods
summary: The genre table: tempo, groove and layers for each genre, and the mood aliases that map onto it.
tags: [genre, tempo, groove, layers, mood, hip hop, techno, rock]
load_when:
  - the brief names a genre
  - the brief names a mood that is not in the basic list
---

# Genres and moods: which genre, which tempo, which groove

Use this file when the brief names a genre (hip hop, funk, metal) or a mood that is not in the basic list, or when
the user asks what "epic" should sound like. Pick the row, then set the layer and groove it names; the numbers are
starting values, not measurements, and a brief that names its own tempo wins.

---

## 0. Where the deep material lives

Sub-archetypes, axis coordinates and synthesis models are in `knowledgebase/genre-and-feel/` (`psychoacoustic-genre.md`, `dynamic-flow.md`, `commercial-promo.md`). Read the one you need with
`python scripts/find_references.py "<the words of the brief>"` rather than all three. This file stays
the decision table: which genre, which tempo, which groove, which layers.

## 1. Epic: how big, and in which mode

- An epic is power, loudness, bombast and aggression: a percussion battery, a synth bass and a choir are its typical
  elements.
- The braam (a low, stacked brass swell, often pitched down) is a trailer device. Add it on a hit, never as a whole-cue
  style.
- The film cue table: **power and anger** go with minor mode, fast tempo and loud dynamics; **triumph and joy** go with
  major mode, fast tempo and loud dynamics. Mode is the cue that separates "triumphant" from "dark".
- There is no settled epic tempo or mode. Treat both as direction decisions.

- `epic` (heroic, the default): major or mixolydian, 88-112 BPM, taiko percussion, brass and strings. Major because the
  cue table ties loud-fast-major to triumph.
- `dark_epic`: aeolian or phrygian, 76-100 BPM, the same kit. Use it for battle, dread, villains and "dark and huge".
- Use `epic` when the user says heroic, triumphant, victory or reveal. Use `dark_epic` when the user says battle, dark,
  menacing or war.
- The percussion: a mood's own drums enter at intensity 0.35, so a build arc still gets its taiko or half-time pattern in a 45 s cue.

## 2. Mood models

| Model | What it says | How the skill uses it |
|---|---|---|
| Cue studies | Mode is the strongest cue for happy and sad; dynamics for scary and peaceful; cues add up | Order of decisions: mode, tempo, register, dynamics, articulation, timbre |
| Film cue table | Power and anger: minor, fast, loud. Triumph and joy: major, fast, loud. | Mode choice for `epic` vs `dark_epic`, and for `triumphant` vs `angry` |
| GEMS | Nine factors: wonder, transcendence, tenderness, nostalgia, peacefulness, power, joyful activation, tension, sadness | Aliases so each factor maps to a preset (see table below) |
| Basic emotions | Happiness, sadness, anger, fear, tenderness and their factors | Presets `joyful`, `sad`, `angry`, `scary`, `tender` |

GEMS to preset (aliases in `compose.py`):

| GEMS factor | Preset | Note |
|---|---|---|
| wonder | `wonder` | |
| transcendence | `wonder` | nearest preset; no separate transcendent preset |
| tenderness | `tender` | |
| nostalgia | `nostalgic` | |
| peacefulness | `calm` | |
| power | `epic` | heroic major; use `dark_epic` for dark power |
| joyful activation | `energetic` (or `joyful`) | |
| tension | `tense` | |
| sadness | `sad` | |

Basic emotions with no direct preset: **disgust** has no preset. The nearest route is `angry` or `scary` with a dissonant
mode, and this is a gap, not a solved case. **Surprise** has no preset either; a stinger from the `hit_points` list
is the usual tool for it.

## 3. Genres: instrumentation, tempo and groove

The table is a recipe, not a measurement: tempo and groove are starting values that two tempo guides agree on.
When a brief gives a tempo, that tempo wins.

| Genre (`brief.genre`) | Tempo used (BPM) | Groove (`theory.GROOVES`) | Typical layers in the code | Label |
|---|---|---|---|---|
| hiphop | 84-100 | boom_bap | keys, vibraphone lead, sync bass, strings, 808 kit | groove sourced (hip-hop 16-step pattern); rest practice |
| trap | 66-80 (felt as half-time) | trap | pad, glockenspiel bell, sub 808 pedal, music box, 808 | practice |
| dubstep | 138-144 (snare on beat 3 = 70 feel) | halftime | sweep pad, wobble bass, saw lead | practice |
| dnb | 166-176 | breakbeat | pad, arp keys, reese bass, saw lead | practice |
| reggae | 66-84 | one_drop | offbeat skank guitar, organ, harmonica, room kit | practice |
| funk | 96-112 | funk | clavinet, pulsing bass, brass section, trumpet | practice |
| rock | 110-140 | rock | distortion guitar, overdrive lead, pick bass, rock organ, power kit | practice |
| metal | 140-180 | metal | distortion guitar, pick bass, lead, choir pad, power kit | practice |
| rnb | 66-92 | rnb | electric piano, strings, alto sax, sync bass, 808 | practice |
| bossa | 112-132 | bossa | nylon guitar, flute, brush kit (3-2 clave on the rim) | practice |
| samba | 96-116 | samba | nylon guitar, trumpet, standard kit (tom and shaker stand in for surdo and shaker) | practice |
| house | 118-128 | four_floor | stabs, synth bass, saw lead, electronic kit | practice (four_floor was already in the code) |
| techno | 124-134 | four_floor | pad, ostinato stab, synth bass, square lead | practice |

More genres (starting values, not measurements):

| Genre | Tempo used (BPM) | Groove | Typical layers in the code |
|---|---|---|---|
| corporate | 112-126 | pop | piano pulse, clean guitar strum, vibraphone lead, finger bass, strings, standard kit |
| indie | 100-140 | rock | clean guitar, overdrive lead, pulse bass, piano, room kit |
| futurebass | 140-160 | halftime | supersaw chords, warm pad, sub, saw lead, electronic kit |
| halloween | 80-110 | heartbeat | tremolo strings, music box, celesta, contrabass pedal, choir |
| trance | 134-142 | four_floor | pad, 16th pluck, synth bass, saw lead, electronic kit |
| hardstyle | 150-165 | four_floor | saw stabs, pulsing bass, square lead, power kit |
| synthpop | 100-125 | synthpop | polysynth pad, e-piano arp, synth bass, saw lead, electronic kit |
| deep_house | 118-124 | four_floor | warm pad, seventh-chord e-piano, sync bass, vibraphone, room kit |
| darksynth | 100-125 | halftime | sweep pad, saw ostinato, synth bass, synth brass, electronic kit |
| motown | 108-128 | motown | piano pulse, pulse bass, trumpet, strings, standard kit with tambourine |
| reggaeton | 88-100 | dembow | nylon pluck, synth bass, saw lead, 808 kit |
| cumbia | 84-100 | cumbia | accordion, nylon guitar, half-note bass, congas and guiro |
| salsa | 170-200 | salsa | piano comp, acoustic bass, trumpet, trombone, clave, cowbell, congas |
| forro | 108-130 | forro | accordion, acoustic guitar, bass, kick, low tom, triangle |
| afrobeat | 98-112 | afrobeat | clean guitar comp, bass, marimba, brass section, rim and bongo |
| percussion | 92-120 | percussion_drive | orchestral toms and timpani, tremolo strings, brass, trumpet |
| comedy | 110-130 | march | pizzicato, bassoon, tuba, xylophone |
| kids | 100-118 | shaker | nylon strum, xylophone, bass, glockenspiel, brush kit |

`lofi` uses the boom_bap groove with an 808 kit at 68-88 BPM.

**World genres** (India, Arabic, Turkish, Persian, Chinese, Japanese, Korean, Brazil, Latin, Caribbean, African,
Celtic, flamenco) are in `references/scoring/world-music.md`, with the same starting-value status.

The `cinematic` taiko pattern hits on every beat (accents on 1 and 3) so an epic cue has a steady pulse.

**Groove rule.** A genre names its groove. The groove replaces the mood's drum default, unless the brief sets `drums`
explicitly.

**Tempo rule: the mood wins, the genre owns the groove.** The genre's tempo range is kept inside the mood's range
when they overlap. When they do not overlap ("calm house", "motivational corporate"), the mood wins 2:1 (tempo is
the second-strongest emotion cue after mode) and the score's `meta.mood_notes` says so; the genre's instruments,
groove and mix still apply. Only a request with no recognised mood word is genre-driven, and if it carries modifier
words ("slow", "uptempo") those still choose the mood and move the tempo. Without this rule a calm brief that names a fast genre comes out at the genre's upbeat tempo.

**Grid caveat.** The grooves are 4/4 grids of 16 steps. In a 3/4 bar, hits past beat 3 are dropped, so use a 4/4 meter
with genre grooves.

### 3a. Label to genre

Labels from stock and streaming catalogues resolve through `GENRE_ALIASES` in `compose.py`: `--genre "Soft House"`
and `--genre future-bass` both work, and a label outside the table is taken as the nearest row by tempo, groove and
layers.

Every alias is in `GENRE_ALIASES` in `compose.py`.
Mood words from Pixabay playlists (relax, peace, mellow, laid-back, focus, energise, stimulating, spooky, haunting) are
in `EMOTION_ALIASES`; `motivational` maps to `hopeful` and `adventure / quest / journey / expedition` map to the
`adventure` preset. Words that describe how to play it rather than what it feels like (`slow`, `reverb`, `sparse`,
`driving`, ...) are handled by `MOOD_MODS`, `WET_WORDS`, `DRY_WORDS` and `DENSE_WORDS` in the same file, and are
listed in `emotion-and-scoring.md` section 1a.

## 4. The grooves, step by step

Grids use 16 steps per bar (step 0 = beat 1, each step a sixteenth). Numbers below are 0-indexed.

- **boom_bap** (sourced): kick on steps 0, 8, 10; snare on 4, 12; eighth-note hats on every even step. The source's
  1-indexed pattern is kick 1, 9, 11 and snare 5, 13.
- **trap** (practice): kick 0, 10; snare 8; sixteenth hats.
- **halftime** (practice): kick 0, 10; snare 8; eighth hats.
- **breakbeat** (practice): kick 0, 10; snare 4, 12; a ghost snare at 7, 11; eighth hats.
- **one_drop** (practice): kick and rim on 8; offbeat hats 2, 6, 10, 14.
- **rock** (practice): kick 0, 8; snare 4, 12; eighth hats.
- **funk** (practice): kick 0, 6, 10; snare 4, 12; ghost snares 3, 7, 11, 15; eighth hats.
- **metal** (practice): kick on every eighth; snare 4, 12.
- **rnb** (practice): kick 0, 9; snare 4, 12; eighth hats.
- **bossa** (practice): rim on 0, 3, 6, 10, 12 (the 3-2 son clave); kick 0, 8; ride on eighths.
- **samba** (practice): tom_floor on 0, 8 (surdo stand-in); tom_low on 4, 12; shaker on eighths; rim 3, 7, 11, 15.
- **dembow** (practice): kick on 0, 4, 8, 12; snare on 3, 6, 11, 14.
- **cumbia** (practice): kick 0, 8; open conga 4, 12; guiro on every even step.
- **salsa** (practice): claves 0, 3, 6, 10, 12; cowbell on eighths; open conga 6, 12; muted conga 4, 10, 14.
- **afrobeat** (practice): kick 0, 6, 10; rim 4, 12; eighth hats; bongo 2, 5, 9, 13.
- **motown** (practice): kick 0, 8; snare 4, 12 (strong); tambourine on eighths.
- **synthpop** (practice): kick 0, 8; snare and clap 4, 12; eighth hats.
- **forro** (practice): kick 0, 8; low tom 4, 12; triangle on eighths.
- **percussion_drive** (practice): floor tom 0, 8; low tom 4, 12; mid tom 2, 6, 10, 14.

## 5. Adding a genre or a groove

- Genre: add a dict to `GENRES` in `compose.py` with `room`, `swing`, `humanize`, `tone`, `lufs`, `layers`, and
  optionally `groove` and `bpm`. Every instrument name must resolve (`soundbank.resolve`). Use only texture names that
  exist in `theory.TEXTURES`.
- Groove: add an entry to `GROOVES` in `theory.py` with its label (`sourced` or `practice`), the grid and the weights.
  Use `name@tag` keys for a second hit with a different weight.
