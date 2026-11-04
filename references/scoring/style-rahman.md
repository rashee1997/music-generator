---
title: A.R. Rahman style
summary: The production overlay: which instruments lead each role, and what it leaves alone.
tags: [style, rahman, production, overlay, lead, arrangement]
load_when:
  - the brief names a production style
  - a culture mix needs an arrangement voice
---

# A.R. Rahman style: what the production voice is

A production style is an overlay on a culture mix (`scripts/fusion.py`, `STYLES`). It changes which instruments lead
each role, not the cultures' scales, tempos or soul rules.

## How the style is built into the planner (`STYLES['rahman']`)
- **Pad:** `slow_strings` first, so the lush bed is the string sound.
- **Lift (counter line):** `violin` first, the leitmotif voice above the melody.
- **Chorus:** `choir_formant` first, the choral layer that enters with the build.

Use it with `"style": "rahman"` in a fusion brief. The cultures' soul rules still apply: the soul gate checks them
on the piece, and the mix gate checks the lead's band.

## What is not in the overlay
- Electronic drum programming and reggae or jungle rhythms.
- Sung words. The choir and hum are texture only (see SKILL.md limits).
