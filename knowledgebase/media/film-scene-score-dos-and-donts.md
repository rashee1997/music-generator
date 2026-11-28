---
id: film-scene-score-dos-and-donts
title: Film scene score: what scene-based background music should and should not be
domain: media
status: partly-sourced
sources: [prosoundweb_balancing_dialog, musictech_music_for_picture, cistudios_mixing_pitfalls, robin_hoffmann_dialogue_underscore, production_expert_music_clip_art, packt_spotting_session, berklee_spotting, artofcomposing_how_to_spot_a_film, wikipedia_spotting, fiveable_functions_of_music_in_film]
used_by: [references/data/media/film_scene_score.json, scripts/media_profile.py, references/data/presets/intent/registers.json, AGENTS.md]
updated: 2026-11-28
---

> **Not verified.** The pages behind the sources were not opened: each figure is what a search result said about its page
> (labelled `per search result` in the profile's provenance), not what the page was read to say. Everything here is practitioner advice (mixing blogs, composer guides, course notes) and the spotting
> workflow as teachers describe it; no standard or measurement was found for how loud a music bed sits under dialogue, and the
> speech band is quoted differently by different authors. Figures in the profile say "starting value" where no source gave one.

# Film scene score: what it should and should not be

A scene-based background score (underscore) serves the scene. The profile is `references/data/media/film_scene_score.json`;
the film pipeline's rows are in `AGENTS.md` section 9 and `references/scoring/video-scoring.md`.

## 1. What an underscore is for

- It supports the mood and action the picture shows and gives continuity across cuts; it is non-diegetic (only the audience hears
  it) unless it comes from a source in the scene (diegetic music, placed in the room).
- A scene that needs nothing beyond the picture and the sound can have no music; leaving it out is a valid cue.

## 2. Loudness

There is no standard for a music bed's loudness on its own: the film program is gated on dialogue
(`references/data/presets/film/delivery.json`: -27 LUFS for cinema and Netflix, -23 for broadcast), and the cue is judged against
the dialogue. The register `film_underscore` carries a starting band of -30..-22 LUFS for the cue alone, which is this skill's
starting value, not a published figure. A cue with picture hits that is meant to lead (a trailer, an action cue) uses `cinematic`.

## 3. Scoring: should and should not

Should:
- **Spot first.** The composer and director watch the film and decide where each cue starts and ends and its mood; the notes list
  start and end timecodes, cuts and the kind of music wanted (Packt, Berklee Online, B&H Explora).
- **Hit what matters.** Hit points are the moments the music must line up with; the strongest land on a downbeat, and the tempo is
  chosen so they land. A drama does not hit everything it sees (Packt, Art of Composing).
- **Give a person, place or idea a short theme** (a leitmotif) that can change with the story.
- **Place source music in the room**: its level, reverb and EQ belong to the space, and the shot decides when it becomes score.
- **Make silence a choice.** Fade or cut into and out of it on purpose.

Should not:
- Mickey-mouse: matching every movement with a note reads as cartoon in live action.
- Score what the picture and the acting already show; a cue that only restates the emotion adds nothing.
- Let the temp track decide: a director can attach to it, so take its function and mood, not its notes.
- Drop a stock cue in place of a scored one: music that does not follow the scene is "clip art" (Production Expert).
- Start or end a cue where nothing changes. There are no fixed rules, but each in and out is a decision.

## 4. Mixing under dialogue

- The speech band is quoted as about 1-3 kHz (MusicTech), 1-5 kHz (a studio blog), and 2.5-5 kHz for intelligibility
  (ProSoundWeb). Be careful where the score is strong there; it becomes too forceful.
- EQ the music as well as ducking it: take 2-4 dB out of 2.5-5 kHz while the voice speaks and lift the voice there by a similar
  amount. Keep the low end tight and the highs crisp with a reduced midrange (ProSoundWeb).
- Too dense a piece does not sit under dialogue. A full string quartet's lower strings sit where voices sit; a high bell with a low
  plucked bass leaves room (c-istudios).
- Cut between a full version where there is no dialogue and an underscore version where there is.
- Audition the music with the real dialogue and effects, and never only in solo; a mix that sounds slightly missing a range alone
  is often right in the film.

## 5. Scene types and the instrument families that suit them

Families are those of `references/data/presets/families/families.json`. The mapping follows the advice above (sparse under speech,
drive for action, a single line for an emotional scene) and is a starting value, not a measured table.

| Scene | Energy | Prefer | Avoid | Duck under dialogue |
|---|---|---|---|---|
| dialogue underscore | 0.2 | plucked, keys, synth, bowed | brass, percussion, voice | 4-8 dB |
| suspense | 0.45 | bowed, synth, percussion, reed | keys, brass | 3-6 dB |
| action | 0.9 | percussion, bowed, brass, synth | | 6-10 dB |
| emotional | 0.4 | bowed, keys, voice, reed | percussion, synth | 3-6 dB |
| montage | 0.6 | plucked, keys, synth, bowed | | 0-3 dB |
| source music | 0.4 | as the source | | 6-12 dB |
| silence | 0.0 | | | |

## 6. What is not known

No published level for an underscore against dialogue, no standard for the speech band, and no measured study of how often a
drama should hit. Say "starting value" where a piece uses one, and judge the cue against the actual dialogue.

## Sources

- ProSoundWeb, balancing dialog in post production: https://www.prosoundweb.com/in-the-studio-balancing-dialog-in-post-production/
- MusicTech, music for picture, the final act: https://musictech.com/guides/essential-guide/music-for-picture-final-act/
- c-istudios, pitfalls when mixing audio for film and TV: https://c-istudios.com/avoid-these-pitfalls-when-mixing-audio-for-film-and-tv-to-achieve-professional-results/
- Robin Hoffmann, mixing dialogue and underscore: https://www.robin-hoffmann.com/?p=4285
- Production Expert, music becoming clip art on TV shows: https://www.production-expert.com/production-expert-1/is-music-becoming-clip-art-on-tv-shows
- Packt, what a spotting session is: https://packtpub.com/en-MT/product/scoring-to-picture-in-logic-pro/9781837636891/chapter/chapter-1-understanding-film-music-industry-standards-2/section/what-is-a-spotting-session-ch02lvl1sec05
- Berklee Online, scoring to picture: https://online.berklee.edu/takenote/?p=18411
- Art of Composing, how to spot a film: https://artofcomposing.com/how-to-spot-a-film
- Wikipedia, spotting (filmmaking): https://en.wikipedia.org/wiki/Spotting_(filmmaking)
- Fiveable, functions of music in film and media: https://fiveable.me/sound-design/unit-12/functions-music-film-media/study-guide/CcXRjtX61KuvRaZo
