---
id: expectation-idyom
title: Melodic expectation - information content and entropy from a PPM model
domain: sound-design
status: partly-sourced
sources: [https://joss.theoj.org/papers/3f2e7b31cf9ee2f96ba631ff2617f8c5, https://par.nsf.gov/servlets/purl/10565624]
used_by: [scripts/expectation.py, scripts/pattern_audit.py, docs/PSYCHOACOUSTICS.md]
updated: 2026-11-23
---

> **Not verified** in one place: `read in source` means read at the cited page; `from memory` was not re-read;
> `starting value` is this skill's choice.

# Expectation as information content and entropy

| Quantity | Definition | Status |
|---|---|---|
| Information content of an event | `IC = -log2 P(e | context)` | standard result |
| Entropy at a position | `H = -sum_e P(e | context) log2 P(e | context)` | standard result |
| Predictor | prediction by partial matching with escape method C, variable order up to a bound | from memory (Pearce & Wiggins 2004, Pearce 2005) |
| Viewpoints | pitch interval, scale degree, inter-onset ratio, each a separate model | from memory |
| Combination | models weighted by `1/H^b` (higher entropy, lower weight) | from memory (Pearce 2005) |
| Short-term and long-term model | short-term is trained on the piece so far; long-term on a corpus | from memory |
| IDyOM itself | written in Common Lisp; `py2lispIDyOM` is a wrapper that needs it installed, MIT as stated by its package page | read in source (JOSS paper, listing) |
| Performers vary timing and dynamics with melodic uncertainty and surprise | effect sizes small | from memory (Gingras and colleagues, 2016); citation to confirm |
| Optimal-interest entropy corridor 1.2-3.8 bits | this repo's existing row | `docs/PSYCHOACOUSTICS.md`, starting value |

No corpus is bundled. Each candidate corpus has its own licence (not verified); the short-term model alone needs
no data.
