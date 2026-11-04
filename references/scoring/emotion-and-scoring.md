---
title: Emotion and scoring
summary: Which cue carries which feeling, the mood vocabulary the code understands, and the modifiers that change them.
tags: [mood, emotion, feel, major, minor, tempo, energy, modifier]
load_when:
  - a brief names a feeling
  - the forced choice reads the wrong mood
---

# Emotion and situational scoring

How to make music that makes people FEEL a specific thing, and how to fit it to a scene, a cut, a voice-over
or a game state. Read this before choosing key / tempo / instruments, then let `scripts/compose.py` (or your own
script) apply it.

## 1. How listeners hear emotion

Listener studies found that a handful of cues carry most of the emotion, that
they add up roughly linearly, and that **mode is the strongest, then tempo, then register, dynamics,
articulation, timbre**. So set these in this order, and make them all point the same way.

| Emotion | Mode / harmony | Tempo (BPM) | Register | Loudness | Articulation | Timbre | Rhythm / texture |
|---|---|---|---|---|---|---|---|
| Calm / peaceful | major, lydian, pentatonic; consonant, few chord changes | 55-75 | mid | soft, steady | legato | warm, dark, soft attacks | sparse, long notes, slow harmonic rhythm |
| Tender / love | major (maj7, add9, iii), lydian | 58-78 | mid-high melody over warm low pad | soft to medium | legato, rubato | strings, piano, nylon guitar, flute | gentle arpeggios, 4-note voicings |
| Sad | minor / dorian; i-VI-III-VII, i-iv-i-V | 52-70 | low-mid, falling lines | soft, wide quiet dynamics | legato, long notes | dark: cello, piano, soft pad | few notes, long rests, falling contours, slowing at the end |
| Grief | minor, bare fifths, unresolved cadence | 48-60 | low | very soft | very legato | solo cello / piano / choir | extremely sparse, long fermatas |
| Nostalgic | major with borrowed iv (I-iii-IV-iv), mixolydian | 66-86 | mid | soft-medium | mixed, slightly loose | piano, nylon guitar, music box, vibraphone, tape-warm | simple repeating motif, gentle swing |
| Hopeful / uplifting | major, vi-IV-I-V, lydian lift | 76-98 | rising | builds soft to full | legato to light staccato | piano, strings, acoustic guitar | steady pulse, builds in layers |
| Motivational (`motivational` alias -> `hopeful`) | major, I-V-vi-IV, IV-I-V-I | 76-98 | rising, melody in its singing octave | builds from soft to confident, but never a shout | legato with a light accent on phrase starts | piano, strings, guitar, soft kit | steady, layer-by-layer build; 0.68 energy, not 0.5 |
| Adventure / exploration (`adventure`) | major, lydian, dorian; open fifths; I-V-vi-IV, I-II-I-V | 84-104 | wide but not extreme: melody in octave 4-5, bass under it | medium, swells and opens; no war-drum attack | legato, light marcato on the theme | strings, horns, flute, harp, frame drum or half-time kit | one step at a time, half-time pulse; a journey, not a battle |
| Joyful / happy | major, I-V-vi-IV; bright | 108-130 | mid-high | medium-loud | staccato / bouncy | bright: pop kit, guitar, glock, pizzicato | syncopation, lively drums |
| Playful / quirky | major / mixolydian, chromatic passing notes | 100-124 | high | medium | short staccato, pizzicato | pizzicato, woodwinds, marimba | off-beat accents, stops and starts |
| Triumphant / epic (heroic) | major or mixolydian, big cadences; I-V-vi-IV, I-bVII-IV-I; pedal bass | 88-112 | wide: deep bass + high melody | loud, crescendo | broad, accented | brass, full strings, taiko, choir | big layered build, long final chord |
| Dark epic / battle | aeolian or phrygian, big cadences; i-VI-III-VII, i-II-i-VII | 76-100 | wide, low | loud, crescendo | broad, accented | brass, low strings, taiko, timpani | slow huge build; power and anger go with minor |
| Determined / heroic drive | minor / dorian; ostinato | 92-112 | low-mid | medium-loud | marcato | low strings, snare march, piano | driving 8ths/16ths, steady pulse |
| Tense / suspense | minor, phrygian bII, tritone, clusters, unresolved dominant | 70-100 (or pulse-less) | low + sparse high | quiet with sudden loud | tremolo, staccato | tremolo strings, low piano, sub, glassy plinks | ostinato, rising pitch, silences, irregular hits |
| Scary / dread | phrygian/locrian, dissonant, unpredictable | 48-68 | very low drones + very high | quiet <-> sudden loud | tremolo, sul pont. | contrabass, low drones, music box, choir | very sparse, long rests, slow swells, heartbeat |
| Angry / aggressive | phrygian, power chords, dissonance | 120-150 | low-mid | loud | hard, short | distorted guitar, heavy drums | fast, dense, accented |
| Mysterious / curious | lydian #4, whole-tone, dorian, maj7#11 | 58-82 | high sparkles over low drone | soft | detached | celesta, harp, glass, pad | sparse, sustained pedal, unusual intervals |
| Wonder / awe | lydian, major with raised 4th, slow chord changes | 66-90 | wide, ascending | builds | legato | strings, harp, choir, bells | slow swell, arpeggio shimmer |
| Dreamy | lydian / maj7, floating, no strong cadence | 58-76 | mid-high | soft | legato | pad, glock, Rhodes, reverb | slow, washed with reverb |
| Focused / neutral (explainer, study) | simple major/pentatonic, diatonic | 84-104 | mid, avoid 2-4 kHz clutter | soft, EVEN | steady | lo-fi piano, soft guitar, mallets | steady, no big dynamics, no lyrics |
| Energetic / hype | major / mixolydian | 118-140 | mid-high | loud | punchy | pop kit, bass, bright synths/guitars | four-on-the-floor, syncopation |
| Majestic / noble | major / lydian, slow with big chords | 60-78 | wide | medium-loud | broad | horns, strings, timpani, organ | slow broad melody, full harmony |

`compose.py --list` shows the exact emotion names and aliases it understands. The `epic` preset is major or mixolydian (heroic). `dark_epic` is the minor version, for battle and dread. An earlier minor-leaning epic read as sad in tests, which is why the default changed (see `scene-recipes.md` section 1). Genres (hip hop, trap, dubstep, funk, metal and others) and the mood research are in `genres-and-moods.md`.

**What the evidence supports.** Mode is the strongest cue for happy and sad,
dynamics the strongest for scary and peaceful, and the cues additive, on four excerpts with synthetic timbres. Treat the table as
the starting point for a direction sheet, and check the result with `listen.py`, not with the table.

**Combine cues on purpose.** One cue pointing the wrong way muddies the feeling (a "sad" piece at 120 BPM in
major with bright staccato reads as wistful-happy). For *mixed* emotions (bittersweet, anxious hope) pick
the main emotion's mode + tempo and borrow ONE cue from the second (e.g. major key + slow tempo + soft
dynamics + a minor iv chord = nostalgic). Do not average everything.

## 1a. Energy, space and the words around the mood

The mood is not the whole brief. Most real requests are a feeling plus a way of playing it: "slow reverb mix",
"motivational but not cheesy", "adventure in a big room". `compose.py` splits the phrase before it chooses:

| What the user says | What the code does | Why |
|---|---|---|
| a mood word (`motivational`, `adventure`, `melancholy`, ...) | sets `meta.emotion` through `EMOTIONS`/`EMOTION_ALIASES` | mode is the strongest cue, tempo second |
| `slow`, `slower`, `ballad`, `chill`, `lazy` | tempo x0.85-0.90, energy -0.12 to -0.15 | "slow" is a tempo and dynamic decision, not a mood |
| `fast`, `uptempo`, `driving`, `punchy`, `frantic` | tempo x1.05-1.20, energy +0.10 to +0.18 | same, in the other direction |
| `reverb`, `wet`, `spacious`, `distant`, `cavernous` | `room: large_hall`, `mix.reverb_return: 1.5` | the room is part of the request |
| `dry`, `close`, `intimate`, `tight` | `room: dry`, return 0.6 | keep it small |
| `sparse`, `minimal`, `bare` / `dense`, `full`, `lush` | fewer / more layers enter (gate x0.85 / +0.08) | density, not loudness |
| explicit `energy` 0..1, `space`, `tempo_scale`, `intensity`, `bpm` | `energy` and `space` replace what a word would set; `tempo_scale` multiplies; `intensity` and `bpm` are absolute | a number is unambiguous |

Two defaults changed because they caused "everything comes out upbeat":

- **Energy starts at the mood's own midpoint, not 0.5.** Calm starts around 0.40 and epic around 0.68, so a calm
  brief is quiet without anyone setting `intensity`.
- **An unknown brief no longer falls back to `calm`.** If no mood word is recognised and there are modifiers, the
  modifiers choose (`slow + reverb` -> `dreamy`, `fast` -> `energetic`); with nothing, `focused` (neutral,
  mid-tempo) is used and `meta.mood_notes` says so. `describe()` prints the mood, the energy, the room and every
  note, so you can see the reading before the render.

**When mood and genre disagree on tempo**, the mood wins. If the ranges overlap, the overlap is used. If they do not
("calm house", "motivational corporate"), the code takes two parts mood to one part genre and writes the reason in
`meta.mood_notes`; the genre still owns its groove, instruments and mix. A fusion (`"fusion": [...]`) plans its tempo
as a hint with a +-7 BPM window, and it never invents a mood. See `genres-and-moods.md` section 3 and
`genre-fusion.md` section 1.

## 2. Shape over time: the emotional arc

A static loop is ambience; music that moves feels like a story. Pick an arc and write it into the
`dynamics` curve (global loudness 0..1 by beat) and into which layers play when.

| Arc | Shape | Use for |
|---|---|---|
| steady | flat, small waves | explainers, study, background |
| build | quiet -> peak at ~75% -> short release | hope, triumph, reveals, product launch |
| rise_fall | low -> peak mid-late -> low | emotional stories, tributes |
| wave | two or three swells | nostalgia, reflective, cafe |
| tension_release | long rise -> sudden drop/cut | thrillers, cliffhangers, stingers |
| fall | starts fuller, thins out | endings, loss, memory fading |
| sparse | tiny movement, lots of air | meditation, sleep, grief |

Layer entry rule used by compose.py: each instrument has a `min` intensity. At low intensity you hear 1-2
layers (pad, piano). As intensity rises: add bass, add melody doubles, then drums, then high strings/brass.
Adding a layer is stronger than raising volume. Taking layers away is how you create intimacy.

Climax placement: put the peak at roughly 60-75% of the piece (golden section). After the peak, a short
release gives the "payoff". The ending usually slows down (final ritardando) and the last chord rings out.

## 3. Film / game "tension toolkit" (use any 2-3 together)

1. **Ostinato** - a short repeated figure (16ths on a low note) that never resolves.
2. **Pedal tone** - a held low note while chords above it change. Pressure without moving.
3. **Rising pitch / filter** - chromatic climb in the bass or strings; reverse cymbal riser.
4. **Thickening orchestration** - add voices every 2-4 bars.
5. **Register extremes** - very low drone plus very high thin line, nothing in the middle.
6. **Thin texture / silence** - drop everything for a beat before the hit; silence is the loudest sound.
7. **Hits on the beat** - impact (taiko/timpani + cymbal + low boom) on the cut or reveal.
8. **Dissonance** - minor 2nd, tritone, cluster; resolve it late, or never.
9. **Tonal shift** - sudden modulation or mode switch when the situation changes.
10. **Unpredictability** - irregular rests/accents (scary = unpredictable, not just loud).

Release tools: resolve the dominant to the tonic, drop to a major chord, slow the tempo, add a warm pad,
bring in a lone melodic voice.

## 4. Situational recipes

| Situation | Recipe |
|---|---|
| Video underscore (voice-over) | `voiceover: true`: soft, mid-register, steady, simple harmony, no vocals, no busy hi-hats, nothing big that fights the voice. Cut 2-4 kHz on the music (done for you). Mix with `video-mixer/video_program_mix.py` (music ends up 15-20 dB under speech). |
| Intro / outro sting | 4-12 s; strong tonic ending with ring-out (no loop). `duration_s: 6`, add `hit_points`. |
| Reveal / logo hit | `rise` (2-4 s reverse cymbal + roll) into `impact` on the exact second; silence just before for contrast. |
| Scene cut to a new mood | two cues sharing a key centre, crossfaded at the cut (`scene-recipes.md` section 6); or `shift`/`drop` hit points inside one piece. |
| Game state loop | `loop: true` (no ritardando, tail folded to start, exact bar length). Make low / medium / high-intensity versions with the same key + tempo so they can crossfade. |
| Sleep / meditation | `calm`/`dreamy`, 55-65 BPM, no drums, no big dynamics, long pads, `ambient`. |
| Product / tech explainer | `focused` / `hopeful`, 90-110 BPM, lo-fi piano + soft kit, even dynamics. |
| Motivational film / launch | `motivational` (= `hopeful`, 76-98): major, layer-by-layer build, a melody that rises, energy 0.6-0.7. Not `epic` (that is war-sized, 88-112, brass and taiko) and not a shout. |
| Adventure / travel / quest | `adventure` (84-104): major/lydian, open fifths, half-time pulse, strings + horn + flute, a theme that steps upward. Add `space: large_hall` for the landscape; do not add taiko. |
| Slow, reflective, reverb-washed | `slow reverb mix` style brief: `dreamy` at 58-76, tempo x0.86, `room: large_hall`, reverb return 1.5, sparse layers. Long notes and long tails; if it still sounds busy, add `"sparse": true` words or `--energy 0.35`. |
| Kids / playful | `playful`, major, pizzicato + marimba + woodblock, short staccato notes. |
| Documentary / reflective | `melancholy` or `nostalgic`, solo piano + cello, wide rubato. |
| Sports / hype montage | `energetic`, 128-140 BPM, four-on-the-floor, build-drop-build. |
| Religious / devotional / folk traditions | Use the tradition's own scale and the closest instrument, and name any approximation. See `scene-recipes.md` section 10. Respect the tradition; do not mix random scales. |

Tempo-to-picture: choose BPM so 1 bar or 1 beat lines up with cuts (`compose.py` fits the bar count to the
requested duration). For a hit at second T, `hit_points` snaps it to the nearest half-beat.

Key choice: sharp keys (D, A, E) sound brighter; flat keys (Bb, Eb, Ab) sound warmer. Choose a key that
puts the melody in the singing range of the lead instrument (flute C5-C6, violin G3-E6, cello C2-A4).

## 5. Telling the story with motifs (leitmotif)

- Write a 4-8 note theme for the character / idea. Keep rhythm + contour recognisable.
- Reuse it: major version for joy, minor/slow for loss, fast + low for danger, solo instrument for intimacy,
  full orchestra for triumph. (See `templates/custom_score_template.py`.)
- Develop a motif by **repeating** it, **sequencing** it (up/down a scale step), **inverting** it,
  **augmenting** it (longer notes), or **fragmenting** it. People feel "composed", not generated.
- Phrase like speech: ask (rises to the 5th/2nd = half cadence), answer (falls to the tonic = full cadence).
  compose.py does this in 4-bar phrases with the form AABA.

## 6. Quick decision list for an unknown brief

1. What should the listener FEEL at the start, in the middle, at the end? (arc)
2. Where is the picture/voice? (voiceover?) Where are the cuts / reveals? (hit points)
3. How long, and does it loop? (duration, loop)
4. Pick emotion + genre + key/mode + tempo from the table; write the brief.
5. Render, run `scripts/listen.py` against a direction sheet, revise one lever, re-render (`music-direction.md` section 6). Offer 2 variations (different seed / genre) when the brief is open.


---
