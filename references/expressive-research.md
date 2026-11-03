# Expressive performance and arrangement: what the research says, and what this skill does with it

Read before changing how a piece is planned, orchestrated or performed. Each finding is tagged:
**[established]** (replicated across studies or standard theory), **[practice]** (common orchestration or film-scoring
practice, a style guide's opinion), **[heuristic]** (our own rule, to be checked by listening).

## Sources read

- Cancino-Chacón, Grachten, Goebl, Widmer (2018), *Computational Models of Expressive Music Performance: A
  Comprehensive and Critical Review*, Frontiers in Digital Humanities, doi:10.3389/fdigh.2018.00025.
- University of Minnesota Open Library, *Techniques of Orchestration*, "Type I orchestration".
- Vienna Symphonic Library, *Orchestration Recipes*, intro guide.
- Berklee Online (Ben Newhouse), *How to Write for an Orchestra* (excerpt).

## Findings and what they changed

1. **Performance is planned in a hierarchy: structure, then planning, then movement.** The review describes expressive
   performance as grouping the music into phrases (GTTM-style), planning a shape, then executing it. [established]
   *Change:* `scripts/plan.py` plans sections first; `compose.py` and the humanizer then act on those sections.

2. **Phrase-level tempo and dynamics follow arch shapes** (Todd 1992; Friberg and Sundberg 1999, cited in the review).
   [established] *Change:* the melody swells to the middle of its phrase, and its last note is held a little longer
   (`humanize.py`, phrase-end breath 8 %). Beds (pad, chord) and drums no longer get the arch.

3. **Timing error is not one thing.** The review's timing models separate a slow tempo component (low-frequency) from
   the note-to-note timing (high-frequency). Our humanizer already splits drift from per-note error. [established]
   *Keep:* drift and per-note error stay separate. Not changed.

4. **A melody leads the accompaniment only when the accompaniment is there.** This was a verified defect: the code
   applied the early lead to every melody note, while its comment said otherwise. [established, from the code]
   *Change:* `render_natural._mark_accompanied` flags each melody note that has another pitched track sounding at its
   onset. The lead moves early only on those notes.

5. **Use an instrument only when it is needed; overuse wastes the palette.** [practice, Berklee]
   *Change:* the plan's density curve decides when each layer enters (`gate` in `compose.py`), so a layer is absent
   in sections where it adds nothing.

6. **Density and loudness are separate dimensions.** Film-score practice reaches a climax by adding voices, and a
   large orchestra can play quietly. [practice, Vienna and Berklee] *Change:* loudness (`dyn`) and density (`dens`) are
   separate columns in the plan. The plan table deliberately sets a build that is denser than it is loud, and a
   release that is sparse but not quiet. `plan.check_plan` reports loudness-density correlation above 0.97.

7. **Register and voicing change the sense of arrival.** Orchestration references describe raising the lead for a
   climax. [practice] *Change:* the climax lifts the lead one octave (`reg` in the plan). It is clamped to the
   instrument's playable range, as before.

8. **Restraint: the climax must follow contrast.** [practice] *Change:* `check_plan` flags a climax that is not the
   loudest and densest section, and a climax that is not denser than what comes before it.

9. **Stereo widening must be reproducible.** Verified defect: `mixer.py` seeded widening with Python's `hash()`,
   which changes per process. *Change:* `zlib.crc32`. Regression test: `tests/test_composition.py`.

## What this research does not license

- Classical orchestral rules (arch dynamics, woodwind answers, brass on the climax) are conventions of European
  art-music and film scoring. Do not apply them unchanged to Indian, African, folk, or electronic styles. The
  world-music and genre references carry those idioms; this file does not override them.
- No finding here says a particular number is correct. Values in `scripts/plan.py` (section loudness and density,
  the 8 % breath, the one-octave lift) are [heuristic]. They are starting points for listening tests, not measured
  optima.
- Expressive-performance models are evaluated against human recordings of trained performers. Our renders use
  SoundFont samples, so per-note timing and dynamics can be realised only as far as the sampler allows. Check the
  output on a listening test; do not assume a model's effect survives the renderer.

## Open questions for listening

- Does the climax feel earned, or only louder? Listen to the hush-to-reveal transition alone.
- Does the 8 % phrase-end breath read as phrasing or as a stumble?
- Is the release (quieter, still full) an ending, or a fade in disguise?

---

## Use

Reference only (the research behind the plan and the humanizer). Nothing to create.
