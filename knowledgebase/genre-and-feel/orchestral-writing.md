---
# Not verified: the range and speed figures are starting values; the part-writing findings come from search-result text only
id: orchestral-writing
title: Orchestral writing a sampled or SoundFont orchestra can honour
domain: genre
status: partly-sourced
sources: [https://ar5iv.labs.arxiv.org/html/2006.13329, https://music21.org/music21docs/moduleReference/moduleVoiceLeading.html, https://flypaper.soundfly.com/produce/4-techniques-realistic-orchestral-strings/, https://www.sonarworks.com/blog/learn/how-to-bring-your-string-mock-ups-to-life]
used_by: [scripts/orch_rows.py, references/data/presets/orchestra/ranges.json, references/instruments-and-vocals/soundfont-realism.md]
updated: 2026-11-26
---

> **Not verified.** The pages above were not opened in the session that wrote this file; each line is what a search
> result said about its page. The playing ranges, polyphony and note-rate limits in
> `references/data/presets/orchestra/ranges.json` are `starting value` figures: the page meant to cite them could not
> be fetched, so none is quoted from a source. A part-writing row can say a line is hard to play; it cannot say it
> sounds good.

# Orchestral writing a sampled or SoundFont orchestra can honour

## 1. Playability

| Finding | Basis |
|---|---|
| A line written beyond an instrument's playing range, or for more simultaneous notes than one player or one section has, plays in a sampler and could not be played live; the result reads as a mock-up | per search result (Soundfly, Steinberg forum); the point is general, the numbers are not |
| A section line a real section could not play is the usual tell of a string mock-up; divisi splits a section into groups | per search result (Soundfly, Steinberg forum) |
| A wind or brass player needs breath: a continuous line with no gap reads as a keyboard part | starting value (`max_phrase_s` per instrument in the ranges file); `bow.breath_gap` already checks the gap itself |
| Repeated notes on a wind or brass instrument have a speed limit set by the tongue; a bow has one set by the arm | starting value (`max_rate_hz` per instrument) |
| Overlapped MIDI notes are what a legato patch reads as a slur; a gap between two notes marked legato plays as two separate notes | per search result (Sonarworks, Soundfly) |

## 2. Part writing

| Finding | Basis |
|---|---|
| A grader for Bach-style chorales counts parallel fifths and octaves (including unisons), in similar and in contrary motion, relative to the number of notes | per search result (Fang et al., arXiv 2006.13329) |
| music21 has a voice-leading module with methods that test motion types between two voices | per search result (music21 documentation) |
| An octave doubling that runs for the whole line is orchestration, not an error: parallel octaves between two parts that always double each other are skipped by `orch.voice_leading` | starting value (the 0.6 doubling share in `orch_rows.py`) |

## 3. What the engine does with them

`scripts/orch_rows.py` reads the ranges file and the score only (no audio). It never edits a score. Project-owned
ranges (`<project>/presets/orchestra/ranges.json`) override the shipped table per instrument, and a track can say
`"extended_range": true` or `"section": true` when the writing is deliberate.
