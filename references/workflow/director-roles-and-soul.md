# Director roles, cultural soul and planned fusions

Moved verbatim from SKILL.md to keep the entry file short.

## Music director: the roles the skill plays

A piece has a director. The skill works through these roles in order, and the release gates are the last two.

| Role | Decides | Tool |
|---|---|---|
| **Director** | the purpose, feel, avoid, length, the picture's hit points; says which culture's soul the piece must carry | the direction sheet |
| **Ethnomusicologist** | the soul of each culture: what the music is for, its rhythm, what the phrase and the rest mean | `knowledgebase/*.md`, `scripts/soul.py`, `references/soul/*.json`, `references/scoring/cultural-soul.md` |
| **Arranger** | the scale, tempo, meter and instruments for a mix, and which instruments must not appear | `scripts/fusion.py` (`"fusion": [...]` in a brief) |
| **Performer** | how the parts breathe, swing and ornament, so they do not sound quantised | `scripts/humanize.py`, `scripts/render_natural.py` |
| **Sound designer** | the effects: named ones, or new ones built from a parameter spec | `scripts/sfx.py` (`spec` command, `synth()`) |
| **Spatial designer** | natural 3D externalization, early reflection spaces, distance DRR, soundscape trajectories | `scripts/spatial.py`, `scripts/environment.py` |
| **Mixer** | balance, space, loudness, the instrument-specific EQ | `scripts/mixer.py` |
| **Theorist & Analyst** | deep computational musicology: key/mode confidence, chordification, melodic contour, voice leading, polyrhythmic cross-meter | `music21`, dynamic custom analysis script (`references/workflow/music21-analysis.md`) |
| **Release gate** | loops, copy-paste, clipping, loudness, and the soul | `scripts/quality_gate.py` (includes the soul rows) and `scripts/soul_check.py` |

**Soul is required, not optional.** When a brief names cultures (a fusion, or a `soul_cultures` list), the soul rules
apply: breath between phrases where the culture needs silence, an off-beat groove where the culture needs one,
call and response where it answers a leader, ornament where it is ornamented, a cadence that comes home, no
instrument that reads as another culture. `soul_check.py` FAILs when a required element is missing, so a piece
does not ship flat. Any culture works: add `references/soul/<culture>.json` with its profile; research it first and cite the sources in
`references/scoring/cultural-soul.md`.

**Mixes are planned, not guessed.** `"fusion": ["carnatic", "tamil", "arabic"]` makes the arranger choose one scale
all the cultures share (or the one most share, with a warning), one tempo in the overlap of the cultures' ranges,
the compound or simple meter, the instruments by role, the rhythm patterns from each culture, and a chorus or hum
layer when a culture sings. A foreign scale or instrument that a culture avoids is left out, unless the mix itself
owns it: an Arabic mix keeps its oud and ney.
