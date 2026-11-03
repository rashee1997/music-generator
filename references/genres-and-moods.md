# Genres and moods: what the research says, and what the code does

Use this file when the brief names a genre (hip hop, funk, metal) or a mood that is not in the basic list, or when
the user asks what "epic" should sound like. It separates three kinds of claim:

- **Research**: a finding from a source that was read for this skill (listed at the end).
- **Practice**: common practice in composition and production, not from a measured source. Labelled as such.
- **Tested**: what the renders and earshot readings showed in this session (results in section 6).

---

## 0. Extended Sub-Feel & Dynamic Flow Ontologies (Knowledge Base Index)

For deep psychophysical coordinate mappings, exact frequency allocations, and pure-Python synthesis models, consult the authoritative machine-parsable knowledge bases:

* **Breaking the "Upbeat 4/4 Trap" & 22 Sub-Archetypes:**  
  See [`knowledgebase/PSYCHOACOUSTIC_GENRE.md`](file:///D:/Vasima/.agents/skills/music-generator/knowledgebase/PSYCHOACOUSTIC_GENRE.md).  
  Covers the **5 Orthogonal Psychoacoustic Axes** (Melodic Interval Geometry, Harmonic Motion with Chromatic Mediants, Rhythmic Gravity, Spectral Centroid Trajectory, and Spatial Acoustic Envelopes) across:
  - *Adventurous:* Forest Mystic (Dorian 3/4), Frontier (John Williams mixolydian ostinatos), High-Seas Swashbuckler (6/8 gallop), Ancient Desert Ruin (microtonal augmented-seconds), Cosmic Odyssey (Lydian #4).
  - *Epic:* Colossal Hybrid Trailer (braams & sub-drops), Mythic Choral Tragedy (Gothic minor), Triumphant Ascension (major fanfare), Tribal War March (earth-shaking percussion).
  - *Electronic:* Warehouse Techno (hypnotic minimal), Euphoric Progressive Festival (SuperSaw leads), Cyberpunk Midtempo, Organic Deep Sunset House, Neuro Kinetic D&B.
  - *Pop:* Max Martin Radio-Tight Pocket, 80s Dreamy Synth, ASMR Bedroom Whisper, Sunshine Nu-Disco.
  - *Celtic:* Tavern Reel (fiddle frenzy), Highland Lament (keening pipes), Fae SlipJig (9/8 slip), Battle Charge.

* **The 7 Laws of Natural Flow & 24 Niche Sub-Archetypes:**  
  See [`knowledgebase/DYNAMIC_MUSICAL_FLOW_v2.md`](file:///D:/Vasima/.agents/skills/music-generator/knowledgebase/DYNAMIC_MUSICAL_FLOW_v2.md).  
  Enforces the **7 Laws of Natural Flow** (Anti-Loop $A \rightarrow A' \rightarrow B \rightarrow A''$, Phrase Respiration, Energy Curve $E(t) \in [0, 1]$, Conversational Call-and-Response, Transition Physics, 5-Band Spectral Slots, Dynamic Parameter Interpolation) across:
  - *Lo-Fi & Chill:* Tokyo Study (drunken quintuplet swing), Midnight Vinyl Crackle, Cozy Coffee Bossa, Vaporwave Mall.
  - *Ambient & Atmospheric:* Deep Space Drone, Arctic Cello Shimmer, Biophilic Rainforest, Sacred Temple Bell.
  - *Horror, Suspense & Dark:* Sub-Bass Dread, Microtonal Waterphone / Penderecki Cluster, Victorian Haunting Music Box, Industrial Cyber-Slasher.
  - *Gaming & Boss Battles:* Elden Ring Gothic Choir/Brass, Cyberpunk 2077 Glitch Industrial, 8-Bit/16-Bit Chiptune, JRPG Overworld.

* **Commercial, Corporate, Motivational & Modern Musicals:**  
  See [`knowledgebase/COMMERCIAL_CORPORATE_PROMO.md`](file:///D:/Vasima/.agents/skills/music-generator/knowledgebase/COMMERCIAL_CORPORATE_PROMO.md).  
  Covers the **Dopamine Arc** (0–3s Thumb-Stop hook, 15–30s micro-lifts, logo stings), the **Voice-Over First Contract** (1.8 kHz notch, dynamic ducking), and archetypes across Silicon Valley Uplift, Fintech Minimal Pulse, Stomp-Clap Indie Rock, Fashion House, and Lin-Manuel Miranda syncopated rap-showtunes.

---

## 1. Epic: how big, and in which mode

**Research.**
- Bühler's account of epic film music, read through the "Day of Honour" paper, describes the epic as power, loudness,
  bombast and aggression, with a percussion battery, a synth bass and a choir as typical elements.
- The braam (a low, stacked brass swell, often pitched down) is a trailer-era device; its history is in the Northwestern
  braam page. It is a texture to add on a hit, not a whole-cue style.
- Micallef Grimaud & Eerola (2022), a cue table for film music: **power and anger** go with minor mode, fast tempo and
  loud dynamics; **triumph and joy** go with major mode, fast tempo and loud dynamics. The mode split is the cue that
  separates "triumphant" from "dark".
- No source found gives a settled epic tempo or a settled epic mode. The mode is a direction decision, not a fact.

**Practice (the code's choices).**
- `epic` (heroic, the default): major or mixolydian, 88-112 BPM, taiko percussion, brass and strings. Major because the
  cue table ties loud-fast-major to triumph, and because the earlier minor-leaning preset read as sad in tests.
- `dark_epic`: aeolian or phrygian, 76-100 BPM, the same kit. Use it for battle, dread, villains and "dark and huge".
- Use `epic` when the user says heroic, triumphant, victory or reveal. Use `dark_epic` when the user says battle, dark,
  menacing or war.
- The percussion: a mood's own drums enter at intensity 0.35, so a build arc still gets its taiko or half-time pattern
  in a 45 s cue (before this change the drum layer started too late for a short cue).

## 2. Mood models

| Model | What it says | How the skill uses it |
|---|---|---|
| Eerola, Friberg & Bresin (2013) | Mode is the strongest cue for happy and sad; dynamics for scary and peaceful; cues add up | Order of decisions: mode, tempo, register, dynamics, articulation, timbre |
| Micallef Grimaud & Eerola (2022) cue table | Power and anger: minor, fast, loud. Triumph and joy: major, fast, loud. | Mode choice for `epic` vs `dark_epic`, and for `triumphant` vs `angry` |
| GEMS (Zentner et al. 2008, via the Wikipedia summary) | Nine factors: wonder, transcendence, tenderness, nostalgia, peacefulness, power, joyful activation, tension, sadness | Aliases so each factor maps to a preset (see table below) |
| Basic emotions (factor-analysis study, abstract read via dovepress) | Happiness, sadness, anger, fear, tenderness and their factors | Presets `joyful`, `sad`, `angry`, `scary`, `tender` |

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

GTZAN-style genre features (Tzanetakis & Cook 2002) are three families: timbral texture (spectral shape, MFCCs), rhythmic
content (beat strength, tempo) and pitch content. They are features for telling genres apart, not a recipe for making
them. The table below is a recipe, and its tempo and groove numbers are **practice**, cross-checked against two
tempo guides (musical-u and learningmusic). They are not measured on a corpus.

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

Added from the Pixabay pass (all practice values; none measured on a corpus):

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

`lofi` now uses the boom_bap groove with an 808 kit at 68-88 BPM.

**World genres** (India, Arabic, Turkish, Persian, Chinese, Japanese, Korean and K-pop, Rio and Brazil, Latin, Caribbean, African, Celtic, flamenco and more, 79 in all) are in
`references/world-music.md`. They are practice values and are not in the earshot tables below.

Genres older than this pass: piano, cinematic, ambient, acoustic, lofi, orchestral, folk, jazz, pop, dark, electronic.
The `cinematic` taiko pattern is now a hit on every beat (accents on 1 and 3) so epic cues have a steady pulse.

**Groove rule.** A genre names its groove. The groove replaces the mood's drum default, unless the brief sets `drums`
explicitly.

**Tempo rule: the mood wins, the genre owns the groove.** The genre's tempo range is kept inside the mood's range
when they overlap. When they do not overlap ("calm house", "motivational corporate"), the mood wins 2:1 (tempo is
the second-strongest emotion cue after mode) and the score's `meta.mood_notes` says so; the genre's instruments,
groove and mix still apply. Only a request with no recognised mood word is genre-driven, and if it carries modifier
words ("slow", "uptempo") those still choose the mood and move the tempo. This is the fix for the old behaviour where
every genre request came out at the genre's upbeat tempo.

**Grid caveat.** The grooves are 4/4 grids of 16 steps. In a 3/4 bar, hits past beat 3 are dropped, so use a 4/4 meter
with genre grooves.

### 3a. Pixabay's genre list, and where each label goes

The user asked for the genres Pixabay Music uses. What was and was not checked:

- Pixabay's public API has **no music endpoint**. It covers images and videos only (`/api/` and `/api/videos/`); a request to
  `/api/music/` returns 404. The API key the user supplied therefore could not list music genres, and it is not stored anywhere in this skill.
- The pixabay.com/music pages sit behind a Cloudflare challenge in a shell, so they were not fetched that way (and the challenge was not worked around).
  Genre labels were read through the session's page reader instead: locale pages, playlists, and the genre index pages. That is a **sample**
  of the labels on track listings, not a complete catalogue, and some pages returned the same listing twice.
- Labels seen in listings include: Upbeat, Pop, Funk, Soft House, Techno & Trance, Dubstep, Beats, Trap, Urban Latin, Motown & Old School Rnb,
  Mystery, Build Up Scenes, and others summarised in the table below.

| Pixabay label (as seen) | Genre in this skill (`brief.genre`) | Note |
|---|---|---|
| Upbeat, Commercial, Advertising, Vlog, Tutorials, Background | `pop` or `corporate` | `corporate` is tuned to a 120 BPM reference the user supplied |
| Beats, Alternative Hip Hop | `hiphop` | |
| Lo-fi, Chill Beats | `lofi` | |
| Trap | `trap` | |
| Dubstep | `dubstep` | |
| Future Bass | `futurebass` | |
| Techno & Trance | `techno` or `trance` | gabber and hardstyle labels map to `hardstyle` |
| Soft House, Deep House | `deep_house` | |
| House, Dance | `house` | |
| Synthpop, Synthwave, Retrowave | `synthpop` | |
| Cyberpunk, Dark Synth | `darksynth` | |
| Motown & Old School Rnb | `motown` | |
| R&B | `rnb` | |
| Urban Latin | `reggaeton` (and `cumbia`, `salsa`) | cumbia is a separate genre here |
| Brazilian | `samba` or `forro` | |
| Afrobeat, African | `afrobeat` | |
| Reggae | `reggae` | |
| Funk | `funk` | |
| Rock, Indie Rock, Alternative, Sport | `rock` or `indie` | the sport/rock reference the user supplied was measured |
| Metal, Thrash, Doom | `metal` | |
| Powerful Percussion, Taiko | `percussion` | |
| Comedy, Bloopers, Quirky, Cartoon | `comedy` | |
| Children's, Kids | `kids` | |
| Scary Children's Tunes, Spooky | `halloween` | |
| Modern Classical | `piano` | |
| Classical, Epic Classical, Adventure | `orchestral` or `cinematic`, with `emotion: adventure` | Pixabay's "Adventure" is a mood (84-104, lydian/major, half-time) rather than a war-sized `epic`. Use `epic` only for trailer/triumph material |
| Main Title, Trailer, Build Up Scenes | `cinematic` | |
| Mystery | `dark` | |
| Ambient, Meditation, Yoga, Sleep, Nature | `ambient` | |
| Jazz, Bossa Nova, Folk, Acoustic | the genres of the same names | |

Every alias is in `GENRE_ALIASES` in `compose.py`, so `--genre "Soft House"` and `--genre future-bass` both work.
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

## 6. Tested in this session

- All 13 first-pass genres rendered at 10 s, and all 42 genres render at 24 s in the final pass. Every instrument name resolves. Each genre's tempo range and groove take effect (the
  renders' BPMs fall in the ranges above, and each has drum notes).
- The three cinematic moods (`epic`, `dark_epic`, `passionate`) render at 45 s with a percussion track (70, 54 and 165
  drum notes respectively, plus timpani). Before the threshold fix they had none.
- Earshot forced choice: each render was tested for its own label against three other genre labels. Results are in
  section 7.

## 7. Earshot readings

Each file is tested with `api.match` for its own label against three other labels from a pool of 16. p is the share of
the forced choice the target wins; z is earshot's score. "Pass" here means p of 0.5 or more and z of 2.5 or more, the
same rule `listen.py` uses for feel. These are one render per genre, one seed, 10 s, so treat them as a first reading.

| Render | Target label | p | z | Verdict | Earshot's top readings |
|---|---|---|---|---|---|
| funk | funk | 1.00 | 3.2 | pass | celebratory, jazz, uplifting, funk (3rd) |
| samba | samba | 1.00 | 3.7 | pass | jazz, celebratory, uplifting |
| techno | techno | 1.00 | 3.8 | pass | techno, synthwave, chiptune |
| bossa | bossa nova | 1.00 | 3.4 | pass | jazz, celebratory, ukulele |
| reggae | reggae | 1.00 | 2.2 | CHECK (z under 2.5) | funk, music box, acoustic guitar |
| house | house | 0.91 | 2.3 | pass | techno, synthwave |
| rock | rock | 0.77 | 4.6 | pass | funk (1st), rock with electric guitars (2nd) |
| trap | trap | 0.91 | 2.1 | CHECK (z under 2.5) | corporate pop, glockenspiel, sad |
| rnb | R and B soul | 0.90 | 1.9 | CHECK (z under 2.5) | hip hop beat with heavy bass, funk |
| dubstep | dubstep | 0.74 | 2.3 | CHECK | synthwave, corporate |
| hiphop | hip hop | 0.70 | 1.6 | CHECK | playful, chiptune, hip hop beat (3rd) |
| metal | heavy metal | 0.01 | 3.9 | **FAIL** | rock with electric guitars, funk, jazz |
| dnb | drum and bass | 0.02 | 2.4 | **FAIL** | chiptune, synthwave, techno |
| cinematic, epic (10 s, pre-fix render) | epic orchestral | 0.89 | 2.2 | pass, but top reading is "sad and melancholic" | sad, strings ensemble, string quartet |
| cinematic, epic (45 s) | epic orchestral | 1.00 | 3.2 | pass | string quartet, sad, strings, cinematic |
| cinematic, dark_epic (10 s, pre-fix) | dark epic orchestral | 0.10 | 2.0 | **FAIL** | sad, strings, string quartet |
| cinematic, dark_epic (45 s) | dark epic orchestral | 0.19 | 2.9 | **FAIL** (loses to "epic orchestral") | string quartet, sad, strings |
| cinematic, passionate (10 s, pre-fix) | passionate orchestral | 0.67 | 2.3 | pass | sad, strings, string quartet |
| cinematic, passionate (45 s) | passionate orchestral | 0.76 | 2.6 | pass | sad, strings ensemble |

What this says, plainly:

- **Clear passes**: funk, samba, techno, bossa, rock, house, and the 45 s heroic epic. The cues that have a
  characteristic instrument or groove that earshot can name are easy for it.
- **Metal and DnB fail.** Earshot hears metal as rock and DnB as chiptune or synthwave. The metal render has a distorted
  guitar and pick bass; my guess is that the tempo and the mix make it read as rock, but this is not tested. The DnB render's
  lead and pad are bright synths, which earshot files under synth genres. Both need work (see "Next" below); neither
  should be called done.
- **The dark epic does not separate from the heroic epic.** At 45 s the dark_epic render loses its own forced choice
  to "epic orchestral" (p 0.19). Earshot reads the cinematic strings as sad or as a string quartet, whatever the mode.
  So the minor mode is not yet being heard as dark. Do not claim `dark_epic` works until a listen confirms it.
- **The heroic epic reads sad at 10 s.** The pre-fix 10 s render's top reading is "sad and melancholic". The 45 s render
  wins clearly. It is also longer, and the test did not separate length from percussion, so the cause is not yet known.
  The trailer recipe recorded a related limit.
- Earshot's own warning applies: mood labels are wrong about one time in five, and a forced choice only compares the
  labels given. A pass is a reading, not a verdict.

**Next, in order, if these are worth pursuing:** for metal, a faster grid (160-180) with a steady double kick and more
distortion on the guitar layer; for DnB, replace the bright saw lead with a darker pad and a rougher reese; for dark
epic, lower the register further, add a choir or drone, and test in a forced choice against "epic orchestral" before
the next claim.

## 7a. Earshot readings, all 42 genres (final pass)

One 24 s render per genre, seed 3, one mood each. Two forced-choice tests, both with earshot (CLAP), p = share won, z = earshot's score.
"pass" = p of 0.5 or more and z of 2.5 or more; "weak" = p of 0.5 or more with z under 2.5; "FAIL" = p under 0.5.

- **Neighbour test**: the genre's own label against five labels picked by a fixed rotation. Many of those are close relatives
  (house against deep house, salsa against cumbia, rock against funk), so a FAIL here can mean "read as a close cousin",
  not "wrong".
- **Family test**: the same label against one label from each of five other families (electronic, latin/world, hip hop/R&B,
  rock/pop band, orchestral, solo piano). A FAIL here means the render does not even read as the right family.

| Genre | Neighbour p / z | Verdict | Family p / z | Verdict | Pulse clarity |
|---|---|---|---|---|---|
| acoustic | 0.86 / +1.9 | weak | 0.24 / +1.9 | FAIL | 0.32 |
| afrobeat | 0.03 / +1.7 | FAIL | 0.36 / +1.7 | FAIL | 0.29 |
| ambient | 0.96 / +2.7 | pass | 0.96 / +2.7 | pass | 0.07 |
| bossa | 0.93 / +3.0 | pass | 0.96 / +3.0 | pass | 0.35 |
| cinematic | 0.98 / +3.0 | pass | 0.95 / +3.0 | pass | 0.17 |
| comedy | 0.98 / +4.6 | pass | 0.98 / +4.6 | pass | 0.24 |
| corporate | 0.90 / +2.6 | pass | 0.40 / +2.6 | FAIL | 0.48 |
| cumbia | 0.11 / +3.4 | FAIL | 0.99 / +3.4 | pass | 0.41 |
| dark | 1.00 / +2.8 | pass | 1.00 / +2.8 | pass | 0.11 |
| darksynth | 0.07 / +3.3 | FAIL | 0.95 / +3.3 | pass | 0.43 |
| deep_house | 0.48 / +3.1 | FAIL | 1.00 / +3.1 | pass | 0.73 |
| dnb | 0.14 / +3.0 | FAIL | 0.93 / +3.0 | pass | 0.41 |
| dubstep | 0.07 / +2.4 | FAIL | 0.59 / +2.4 | weak | 0.56 |
| electronic | 0.36 / +2.2 | FAIL | 0.67 / +2.2 | weak | 0.85 |
| folk | 0.93 / +1.8 | weak | 0.39 / +1.8 | FAIL | 0.15 |
| forro | 0.98 / +3.5 | pass | 0.99 / +3.5 | pass | 0.38 |
| funk | 0.36 / +4.1 | FAIL | 0.93 / +4.1 | pass | 0.41 |
| futurebass | 0.28 / +1.7 | FAIL | 0.61 / +1.7 | weak | 0.66 |
| halloween | 0.99 / +2.8 | pass | 0.99 / +2.8 | pass | 0.17 |
| hardstyle | 0.00 / +2.4 | FAIL | 0.20 / +2.4 | FAIL | 0.85 |
| hiphop | 0.98 / +2.1 | weak | 0.99 / +2.1 | weak | 0.48 |
| house | 0.03 / +1.9 | FAIL | 0.60 / +1.9 | weak | 0.81 |
| indie | 0.89 / +2.9 | pass | 0.83 / +2.9 | pass | 0.6 |
| jazz | 0.43 / +3.1 | FAIL | 0.80 / +3.1 | pass | 0.34 |
| kids | 0.95 / +2.8 | pass | 0.70 / +2.8 | pass | 0.26 |
| lofi | 0.03 / +1.5 | FAIL | 0.79 / +1.5 | weak | 0.34 |
| metal | 0.25 / +3.5 | FAIL | 0.63 / +3.5 | pass | 0.86 |
| motown | 0.06 / +1.4 | FAIL | 0.02 / +1.4 | FAIL | 0.64 |
| orchestral | 0.99 / +3.7 | pass | 0.99 / +3.7 | pass | 0.21 |
| percussion | 0.95 / +2.9 | pass | 0.99 / +2.9 | pass | 0.7 |
| piano | 1.00 / +3.1 | pass | 0.99 / +3.1 | pass | 0.1 |
| pop | 0.11 / +2.3 | FAIL | 0.89 / +2.3 | weak | 0.41 |
| reggae | 0.19 / +3.2 | FAIL | 0.97 / +3.2 | pass | 0.3 |
| reggaeton | 0.24 / +2.7 | FAIL | 0.65 / +2.7 | pass | 0.4 |
| rnb | 0.93 / +2.2 | weak | 0.99 / +2.2 | weak | 0.28 |
| rock | 0.35 / +3.5 | FAIL | 0.86 / +3.5 | pass | 0.5 |
| salsa | 0.26 / +4.3 | FAIL | 1.00 / +4.3 | pass | 0.42 |
| samba | 0.93 / +4.0 | pass | 0.99 / +4.0 | pass | 0.71 |
| synthpop | 0.97 / +3.3 | pass | 1.00 / +3.3 | pass | 0.57 |
| techno | 0.97 / +3.5 | pass | 0.98 / +3.5 | pass | 0.67 |
| trance | 0.97 / +3.2 | pass | 0.98 / +3.2 | pass | 0.81 |
| trap | 0.45 / +2.2 | FAIL | 0.99 / +2.2 | weak | 0.63 |

Pulse clarity: 0.30 or more is clear, under 0.15 is weak (earshot's own thresholds). Slow, pulse-less genres (ambient, piano,
dark, halloween, orchestral) are meant to score low.

**What changed after the first pass.** Seven genres were retuned after the first readings (drum and bass, future bass, metal, funk,
reggae, pop, reggaeton) and hardstyle was changed too. Two new textures were added for them: `skank` (reggae offbeat stabs) and
`chop` (funk 16th chops). Family-test p before and after: dnb 0.30 to 0.94, futurebass 0.12 to 0.62, metal 0.15 to 0.63,
funk 0.06 to 0.93, reggae 0.08 to 0.97, pop 0.04 to 0.89, reggaeton 0.16 to 0.65, hardstyle 0.03 to 0.20. That was one tuning
round, not a search for the best settings.

**Still failing, so do not claim these work:**
- **hardstyle** (family p 0.20): earshot hears synthwave or chiptune whatever the lead is.
- **motown** (p near 0): reads as generic cheerful music or ukulele pop.
- **afrobeat** (p 0.36 in the family test): reads as playful or joyful, not as afrobeat.
- **acoustic, folk** (family p 0.24 and 0.39): a strummed guitar bed reads as pop or latin music against the other families.
- **corporate** passes the neighbour test (p 0.89) but not the family test (p 0.40), so its reading depends on the competition.
- **Weak only**: futurebass (z 1.7), house (z 1.9), lofi (z 1.5). lo-fi still does not read as "lo-fi hip hop beat" in the neighbour test.
- `dark_epic` still does not separate from `epic` (section 7).

Reference tracks the user supplied (corporate 120 BPM, pulse about 0.54; rock, pulse about 0.22) were measured, and the corporate
render now has 120 BPM and pulse 0.48. No claim is made that either matches its reference by ear.

## Sources

- Eerola, Friberg & Bresin (2013), "Emotional expression in music: contribution, linearity, and additivity of primary musical cues", Frontiers in Psychology (summary and PDF read).
- Micallef Grimaud & Eerola (2022), film music cue table, Durham University repository (read).
- Bühler, "Day of Honour" paper on epic film music (read through the paper's text; full citation to be checked).
- Northwestern University, braam page (read).
- Zentner, Grandjean & Scherer (2008), GEMS model (via the Wikipedia summary, read).
- Basic-emotion factor-analysis study, dovepress (abstract read).
- Tzanetakis & Cook (2002), "Musical genre classification of audio signals", IEEE TSAP (features as described in the paper's PDF; read).
- musical-u rhythm guide (hip-hop 16-step pattern, read through a search excerpt) and learningmusic tempo guide (cross-check for practice tempos).

---

## Use

Reference only (catalogue of the 42 genres and the mood table). Use it through `python scripts/compose.py --genre <name>` / `--list`; there is no creation step. To add a genre, see its section 'how to add a genre'.
