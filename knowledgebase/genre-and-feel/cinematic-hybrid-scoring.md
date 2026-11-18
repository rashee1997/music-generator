---
# Not verified: the sources were read as search-result text only (see the note under the header)
id: cinematic-hybrid-scoring
title: Hybrid orchestral film and trailer scoring - tension, pressure, loudness and sample realism
domain: genre
status: partly-sourced
sources: [https://en.wikipedia.org/wiki/BRAAAM, https://www.hollywoodreporter.com/news/braaams-beginners-how-a-horn-793220, https://sites.northwestern.edu/hundredthmile/the-origins-of-braaam, https://www.sfcv.org/article/inside-the-making-of-dunkirks-landmark-soundtrack, https://gulfnews.com/entertainment/dunkirk-soundtrack-how-it-all-came-together-1.2066116, https://trailertrash.pages.dev/anatomy-of-a-trailer/, https://violetrecording.com/sound-design-for-trailers/, https://theconversation.com/what-makes-a-film-score-frightening-expert-explains-the-techniques-that-build-tension-and-make-us-jump-216121, https://www.thestrad.com/debate/strings-in-film-leading-screen-composers-discuss-their-use-of-the-broad-string-palette-/7623.article, https://www.sageaudio.com/blog/mastering/mastering-music-for-film-and-video, https://chat.skool.com/audio-artist-academy/new-live-call-key-takeaways-feb-10, https://www.pro-tools-expert.com/production-expert-1/6-tips-for-producing-superb-sampled-strings, https://projectsam.com/getting-started-library-basics/, https://www.sweetwater.com/insync/realistic-orchestral-sequences-part-2/]
used_by: [AGENTS.md, references/scoring/cinematic-commercial-grade.md, scripts/helpers/arc_report.py]
updated: 2026-11-18
---

> **Not verified.** The pages behind the sources above could not be opened in the session that wrote this file
> (the network allowlist blocked them), so each source line is what a search result said about its page, not what the
> page was read to say. A number is labelled `per search result` (a source states it), `starting value` (a working
> figure to be measured on the piece) or `measured here` (measured on a piece rendered by this skill). Cite a primary
> source before presenting any of them as established.

# Hybrid orchestral film and trailer scoring

What separates a cue that feels like a threatening unknown place from one that feels like meditation. This file holds
facts. The rules an agent follows with them are in `references/scoring/cinematic-commercial-grade.md`.

## 1. Pressure, not mood

A calm cue and a dangerous one can share a key, a tempo and an orchestra. They differ in how much of the timeline is
under load. Four things carry the load; a cue that has none of them reads as ambient however dark its chords are.

| Carrier | What it is | Basis |
|---|---|---|
| A pulse that does not stop | a short repeated figure in low strings or percussion, made of notes of the sounding chord, with a few notes changed on each repeat so the shape stays and the pitches move | per search result: an analysis of repeated figures found them mostly chord tones, tweaked on each repeat |
| Low brass and sub weight | very low, very loud brass tones as the "large" sound of the cue | per search result: the low brass blast became a trailer staple after 2010, with precedents in 2007 and 2009 trailers |
| Percussion that is constant | drums as a continuous layer, with accents from trombones and low string staccatos played with the drums | per search result: trombones add accents, often as staccatos beside percussion and low strings |
| A rising or accelerating device | a pitch that seems to climb for ever, or a pulse that speeds up | per search result: a stack of octave-spaced tones moved up in pitch gives the impression of endless ascent; a ticking pulse gives a metric spine |

A cue where the loudest stretch is a few seconds long, and where whole sections drop to a whisper, has pressure only
in those seconds. `measured here`: a 97 s cue written to be tense had its loudest 60 s sit at -13 to -18 dBFS RMS with
dips to -31 dBFS RMS, and was heard by its brief's author as meditative.

## 2. Tension devices by instrument

| Device | Effect | Basis |
|---|---|---|
| Pedal point (a held bass note under changing chords) | even very dissonant chords stay coherent over it; good for builds | per search result |
| Tremolo (rapid repeated or alternating notes) | tension from escalation: more instruments, louder or more regular repeats, pitches rising step by step | per search result |
| Cluster (adjacent pitches together) | a dark cloud; it needs inner movement or it reads as a mass of clashing partials | per search result |
| Bowing near the bridge | an icy, unstable colour with more high overtones | per search result |
| Slow glissando | feels more menacing than a fast one because the pitch change is drawn out | per search result |
| Dissonance that does not resolve | ambiguity is what the listener reads as threat | per search result |

Roughness is the measurable side of dissonance: a cue can be tense and still pass `cochlear_roughness` if the
clashing pair is not sustained. See `knowledgebase/sound-design/roughness.md`.

## 3. Shape of a trailer-style cue

| Part | What happens | Basis |
|---|---|---|
| Open, lull, build, cut to black, final hit | the usual order; the lull is deliberate, because a cue that is exciting throughout is not exciting | per search result |
| Silence before the last hit | a sudden drop to near silence just before the final impact makes the impact larger by contrast | per search result |
| A small kit | a tension drone, a riser, a whoosh, a big hit and a sub drop are enough for the build-and-release shape | per search result |
| A hit followed by silence | the listener supplies what was not shown | per search result |

## 4. Loudness and dynamics

The sources disagree and none is a standard. Treat the figures as the range to measure against.

| Figure | Where | Basis |
|---|---|---|
| -14 LUFS for music mastered for film, the video editor expected to lower it | film and video mastering guide | per search result |
| -14 to -10 LUFS integrated for stems mastered for TV and film | same guide | per search result |
| about -8 to -10 LUFS for trailer music, with peaks allowed higher in the finale; -10 to -14 LUFS for game music | a coaching-call summary, secondary | per search result, weakest source |
| trailer and library music should not carry a large dynamic range; film and TV music may keep a wide one | mastering engineers | per search result |
| -16 LUFS integrated, 13 LU loudness range, 17.9 dB crest | one cue rendered by this skill and judged too calm | measured here |

A chart that listed trailer mixes at -20 to -24 LUFS and theatrical mixes at -27 to -31 LUFS was found and not used:
it was unsourced and the theatrical figure looks wrong. Delivery specs of the platform or trailer house override all
of the above.

Low-end control is where orchestral and hybrid mixes usually fail: a multi-band compressor that narrows the lower
bands is the tool one engineer named (per search result). In this skill that is a mix-preset decision.

## 5. Making a sample library sound like a performance

| Practice | Why | Basis |
|---|---|---|
| Velocity drives short notes; a continuous controller drives long notes | velocity is fixed at the note start, a controller changes loudness while the note sounds | per search result |
| Layer a short attack patch over a sustained one | the attack of a staccato or marcato gives a long note a defined start | per search result |
| Two or three velocity layers on sustained lines | removes the obvious step between loudness zones | per search result |
| Crossfade velocity layers and use round robins | avoids a switch between notes at velocity 49 and 50, and a repeated identical sample | per search result |
| One shared reverb for every library | dry or differently recorded libraries must sit in one space | per search result |
| Play each doubled line separately, never copy-paste it | an exact copy causes phasing | per search result |

`measured here`: the free sample library used by this skill (mid-2000s, dry, no layered ensemble patches) lacks
the close-mic and big-hall character of commercial hybrid scores. That caps how close a cue can get, however it is
written; the arrangement and mix choices above are what remains.

## 6. Where the data does not reach

- Exact timings: how many seconds a lull, a drop or a logo tail should last were not found. Start from the brief's
  duration and measure with `scripts/helpers/arc_report.py`.
- Stage position of sample-library sections in a mix: no source found; the skill's `spatial` presets decide.
