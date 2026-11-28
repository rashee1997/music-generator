---
id: game-score-dos-and-donts
title: Game score: what it should and should not be, with loudness, structure and mixing figures
domain: media
status: partly-sourced
sources: [audiogang_iesd_mix_ref_levels, designingsound_console_mobile_loudness, designingsound_sony_loudness_interview, meta_quest_loudness, gamedeveloper_rethinking_the_audio_loop, gamedeveloper_whats_wrong_with_game_music, wayline_audio_loops, audiokinetic_hdr_mixing, audiokinetic_surgical_dialogue_mix, berklee_adaptive_game_music, audiokinetic_interactive_music, gamedeveloper_hybrid_horizontal_vertical, gamasutra_generative_music_framework, unity_audio_mixing]
used_by: [references/data/media/game_score.json, scripts/media_profile.py, references/data/presets/intent/registers.json, AGENTS.md]
updated: 2026-11-28
---

> **Not verified.** The pages behind the sources were not opened: each figure is what a search result said about its page
> (labelled `per search result` in the profile's provenance), not what the page was read to say. Platform loudness figures come from a Sony interview, the Independent G.A.N.G. mix reference and Meta's
> developer pages, read through secondary reports (a 2013 interview, a 2015 PDF, search summaries). Structure and mixing advice is
> practitioner opinion (Game Developer, Audiokinetic, Berklee Online). No published tempo or duck-depth table was found; those
> figures in the profile say "starting value". Check the platform holder's current documentation before shipping.

# Game score: what it should and should not be

A game score is heard for hours, in a different order each time, under effects and dialogue the composer does not control. Each rule
below is why the profile (`references/data/media/game_score.json`) asks for what it asks for.

## 1. What a game score is for

- It tells the player the state of play (calm, tension, danger) without words, and it is heard repeatedly, so what a film cue
  gets away with once becomes tiring at the fiftieth time.
- It is data for the engine: stems on one grid, states, transitions and stingers (Audiokinetic, Berklee Online).

## 2. Loudness by platform (starting figures, secondary sources)

| Platform | Integrated loudness | Range / peak | Source |
|---|---|---|---|
| Console and PC | -24 LUFS, +-2 LU | loudness range at most 20 LU; true peak -1 dBTP; measure over at least 30 minutes of play | Independent G.A.N.G. IESD mix reference levels; Sony guidance via a Designing Sound interview |
| Mobile and handheld | -16 LUFS (G.A.N.G.) or -18 LUFS +-2 LU (Sony) | the two sources disagree | G.A.N.G. IESD; Sony; a WHO-ITU document cites -18 +-2 for portable devices |
| Meta Quest headset | -16 LUFS | | Meta developer documentation |
| PCVR through Link | -18 LUFS | | Meta developer documentation |

The registers `game_console` (-26..-22), `game_mobile` (-20..-16) and `game_vr` (-18..-16) carry these bands
(`references/data/presets/intent/registers.json`); `intent.register_loudness` takes the middle. A game cue is not mastered to
streaming or film loudness, and the whole game's mix, not one loop, is measured.

## 3. Structure: should and should not

Should:
- **Loop long.** A minute is the least a track should run before it loops, two or more is better, or give it variants and small
  random variations (one reviewer's rule of thumb, not a measurement; repetition fatigue and listener fatigue are documented in
  game-music research). Short loops measurably tire players (a rhythm-game postmortem).
- **Finish the seam.** Crossfade the end into the beginning or use a pre-roll and a gentle fade at the join; an abrupt end or a
  wrong export setting is the usual defect (Wayline).
- **Layer on one grid.** Vertical layers are stems with one tempo and bar grid whose levels follow game variables; horizontal
  resequencing moves between segments at beat or bar boundaries; hybrids of the two are common (Audiokinetic, Game Developer).
- **Quantise transitions** and bridge a different key or tempo with a stinger or a fill. A stinger fits the current key and
  harmony and may wait for a beat or phrase end (Berklee Online).
- **Write each state.** If the music must change when the player is discovered, stealth, discovered and combat each need material
  (Gamasutra generative-music framework).
- **Use hysteresis**: enter combat quickly, leave it slowly, and hold a change until the new state has lasted a moment; calm that
  lasts two seconds is a reload (Gamasutra).
- **Match the game type**: puzzle music is minimal and quiet and can phase in as the solution builds; stealth uses sparse, muted
  instruments that leave room for footsteps; exploration sits at medium intensity; combat is the high-energy state.

Should not:
- Loop a short phrase for a whole level, or leave a click or gap at the join.
- Tie hits to a cut or timecode (the player decides when things happen); that belongs to film.
- Play one state's music in another, or flip between states every second.
- Master to a film or streaming level.

## 4. Mixing under effects and dialogue

- **No standard duck depth exists.** A search of the middleware documentation found none. Audiokinetic describes thresholded
  ducking (HDR threshold near 0 dB) and a case study where a 3 dB music duck under dialogue was clearly not enough for a loud
  orchestra, which was fixed by EQ ducking on two bands. A flat 6-12 dB duck is this skill's starting value, tuned against the
  loudest dialogue-time content.
- Unity's audio-mixing tutorial gives example mix levels of music about -30 to -20 dB, effects -10 to -5, dialogue -6 to -3; the
  gaps are used as a starting music-to-dialogue distance.
- Duck in the band that matters as well as in level: the speech and effect band (2.5-5 kHz, ProSoundWeb) 2-4 dB.
- Leave the midrange light in states where the player listens for cues (stealth, puzzle); a sparse arrangement leaves room.
- Put a limiter only on the final bus. A loop stem is summed with others, so it keeps its own headroom.

## 5. States and the instrument families that suit them

Families are those of `references/data/presets/families/families.json`. The mapping is the profile's starting value, built from the
descriptions above (puzzle: minimal keys and plucked; stealth: noir-like muted, sparse; exploration: medium, sustained strings and
plucked; combat: drive from percussion, low strings and brass), and is not a measured table.

| State | Energy | Prefer | Avoid |
|---|---|---|---|
| menu | 0.3 | keys, plucked, bowed, synth | brass, percussion |
| exploration | 0.45 | bowed, plucked, keys, voice, reed | brass, percussion |
| puzzle | 0.25 | keys, plucked, synth | brass, percussion, voice |
| stealth | 0.35 | bowed, reed, plucked, synth | brass, percussion, voice |
| tension | 0.6 | bowed, percussion, synth | keys |
| combat | 0.85 | percussion, bowed, brass, synth | |
| boss | 1.0 | percussion, brass, bowed, voice, synth | |
| victory / defeat | 0.7 / 0.2 | resolved brass and strings / falling strings | |

## 6. What is not known

No sourced BPM range per game type, no standard duck depth, no measured loop-length study. Say "starting value" when a piece uses
one of these, and measure over play, not one loop.

## Sources

- Independent G.A.N.G., IESD Mix Reference Levels v03.02: https://www.audiogang.org/wp-content/uploads/2015/04/IESD-Mix-Ref-Levels-v03.02.pdf
- Designing Sound, different loudness ranges for console and mobile games: https://designingsound.org/2013/02/different-loudness-ranges-for-console-and-mobile-games/
- Designing Sound, Sony's Garry Taylor on loudness standards: https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/
- Meta, audio loudness meter overview (Quest -16 LUFS, PCVR -18 LUFS): https://developers.meta.com/horizon/documentation/unreal/audio-loudness-meter-overview/
- Game Developer, rethinking the audio loop in games: https://gamedeveloper.com/audio/rethinking-the-audio-loop-in-games
- Game Developer, what's wrong with game music: https://www.gamedeveloper.com/game-platforms/opinion-what-s-wrong-with-game-music-
- Wayline, quick fix bad audio loops: https://www.wayline.io/blog/quick-fix-bad-audio-loops
- Audiokinetic, Wwise HDR best practices: https://www.audiokinetic.com/en/blog/wwise-hdr-overview-and-best-practices-for-game-mixing
- Audiokinetic, surgical dialogue mix: https://audiokinetic.com/blog/surgical-dialogue-mix
- Berklee Online, adaptive game music: https://online.berklee.edu/takenote/?p=14985
- Audiokinetic, interactive music to score gameplay: https://www.audiokinetic.com/en/blog/how-to-use-interactive-music-to-score-gameplay/
- Game Developer, hybrid horizontal and vertical structure (GDC 2021): https://www.gamedeveloper.com/game-platforms/hybrid-horizontal-vertical-structure-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-
- Gamasutra, a framework for generative music in video games: https://gamasutra.com/audio/deep-dive-generative-music-in-video-games
- Unity Learn, audio mixing: https://learn.unity.com/tutorial/audio-mixing-1
- ProSoundWeb, balancing dialog in post production: https://www.prosoundweb.com/in-the-studio-balancing-dialog-in-post-production/
