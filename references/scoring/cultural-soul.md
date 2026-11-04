---
title: Cultural soul
summary: What the soul fields mean, where a culture's profile lives, and how to add one.
tags: [culture, soul, traditional, feel, phrase, rhythm]
load_when:
  - a piece uses a traditional idiom
  - adding or checking a culture's soul profile
---

# Cultural soul

The soul is the thing a listener recognises before they can name it: what the music is for, its rhythm, what the
phrase does and what the rest means. It is data: `scripts/soul.py` (built-in table), `references/data/presets/soul/<culture>.json`
and each project's `presets/soul/` (editable, one file per culture). `scripts/soul_check.py` checks a score against it
before release.

For the acoustic models, tuning, ranges and synthesis behind each tradition, use the file the knowledge base lists
for that culture: `knowledgebase/README.md`.

## How to add a culture
1. Research the soul: what the music is for, its rhythm, what the phrase does, what the rest means.
2. Write `references/data/presets/soul/<culture>.json` with the fields in `scripts/soul.py`, citing the knowledge
   base `id` the values come from.
3. Add its scales, tempo and instruments to `scripts/fusion.py` (CULTURES).
4. Run `soul_check.py` on a piece in that culture before release.

## Fields the gate checks
`feel` (words, shown in the report), `breath_beats` (rest between phrases), `groove` (`offbeat`, `cycle`, or none),
`call_response`, `ornament`, `cadence`, `tempo`, `avoid_instruments`.
