# Lessons learnt

One file per kind of problem, one entry per mistake. Each entry is a few lines: the symptom, the cause, the fix, what to avoid and what to
measure first. They are read before research and before any fix, and updated after one (`AGENTS.md`, rule 22).

| File | Holds |
|---|---|
| `gate-stem-rows.md` | stem-stage rows that blocked a render: dead, dropout, tick, edge |
| `gate-master-rows.md` | master and scene rows: clicks, silence, hit surprise, arc, roughness, channel bars, tempo, pattern |
| `sfx-realism.md` | sound-model effects that sounded fake or too loud: engines, tyres, radio, beds, repeats |
| `mixing.md` | levels, the mix preset and its `fx` table, loudness, section levels |
| `arrangement.md` | notes and rhythm: repetition, held notes, registers, rests, endings |
| `engine-notes.md` | faults found in the engine and the workarounds in force |
| `process.md` | how a session goes wrong: renders, files, scaffolds, reporting, asking |

Find before you fix: `python scripts/lessons.py find "stem.dropout 35 ms hole after a rest"`. Read a whole log's failures:
`python scripts/lessons.py suggest --log /tmp/render.log`. Add or update: `python scripts/lessons.py add ...` (it refuses a near-duplicate and
tells you which entry to update instead). Check size and format: `python scripts/lessons.py check`.

**Do not bloat.** One mistake, one entry, at most 9 lines; a file stays under 160 lines; an entry that is the same cause as another is merged
into it, not added beside it. A fact that is not a mistake (a how-to, a number, a procedure) belongs in `references/` or `knowledgebase/`, not here.
