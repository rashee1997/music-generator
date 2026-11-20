---
# Not verified: read as search-result text only (see the note under the header)
id: emotion-cues
title: Musical cues that carry emotion, and what can be measured from notes
domain: genre
status: partly-sourced
sources: [https://www.frontiersin.org/articles/10.3389/fpsyg.2013.00487/text, https://jyx.jyu.fi/bitstream/123456789/48672/1/eerolatetal49.full.pdf, https://pmc.ncbi.nlm.nih.gov/articles/PMC3726864, https://dmwhyatt.github.io/melody-features/, https://music21.org/music21docs/_modules/music21/features/jSymbolic.html, https://archives.ismir.net/ismir2004/paper/000166.pdf]
used_by: [AGENTS.md, references/workflow/music-direction.md, scripts/helpers/expression_report.py]
updated: 2026-11-18
---

> **Not verified.** The pages above were not opened in the session that wrote this file; each line is what a search result
> said about its page. A number is `per search result` (a source states it) or `starting value` (a working figure, not
> calibrated). Cite a primary source before presenting any of them as established.

# Musical cues that carry emotion

## 1. The cues

| Cue | Direction of effect | Basis |
|---|---|---|
| Mode | the strongest single cue in a factorial study; major leans positive, minor leans negative | per search result (Eerola, Friberg, Bresin 2013) |
| Tempo | fast and loud and high leans high arousal (anger, excitement); slow, legato, soft leans low arousal (calm, sadness) | per search result |
| Register, dynamics, articulation, timbre | the next cues in rank, with the order changing by emotion | per search result |
| Interaction between cues | almost none in that study, so cues act mostly additively | per search result |
| Phrasing | named with mode, tempo, dynamics, articulation and timbre as the most potent cues in a review | per search result (Gabrielsson and Lindstrom, as cited) |

## 2. What audio features predict

| Finding | Basis |
|---|---|
| valence and energy arousal can be predicted from a few acoustic features, such as the ratio of high-frequency to low-frequency energy | per search result (Eerola, Ferrer Flores, Alluri 2012) |
| a 39-feature model explained about 43 % of arousal variance and about 16 % of valence variance, and did not generalise between genres for valence | per search result |

Arousal is measurable; valence from features is weak. `scripts/helpers/expression_report.py` therefore reports an arousal
index only and makes no claim about valence.

## 3. Melody: measures from symbols

| Measure | What it says | Basis |
|---|---|---|
| interval entropy | higher when a line uses more interval categories, so less predictable | per search result (melody-features, FANTASTIC and jSymbolic lineage) |
| step share and leap share | stepwise motion is intervals of one or two semitones | per search result (jSymbolic features) |
| contour | direction patterns such as the Huron contour classes | per search result |
| Narmour implication-realization | a small interval implies a similar one, a large interval implies a smaller one in the opposite direction; closure weakens the implication | per search result |

An open implementation of the implication-realization model was not found. The limits in `expression_report.py` (one bit of
interval entropy, a 7-semitone range, 60 % of bars repeating exactly, 0.5 rank correlation) are `starting value`s.

## 4. Where the data does not reach

- Whether a theme is memorable or good: no open measure was found.
- Valence from audio alone: weak in the research above.
- Tension features at the symbolic level: no feature set was found in the toolkits searched.
