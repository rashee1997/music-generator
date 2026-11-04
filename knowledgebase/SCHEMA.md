# Knowledge base schema and rules

The one place that says how a document in `knowledgebase/` or `references/` is written, filed and
cited. Every file follows it.

## 1. One home per topic

If two files cover the same topic, one of them is the home and the other becomes a short pointer
naming it, or is deleted. The home is the file that the read table in `AGENTS.md` sends an agent to.

## 2. Split by purpose, not by history

| Folder | Holds | Test |
|---|---|---|
| `knowledgebase/` | Facts about music and sound: scales, rhythms, instrument physics, genre feel, formulas. | Would it still be true if this skill did not exist? |
| `references/` | How this skill works: workflow steps, rules, script usage, presets, gates. | Does it name a script, a preset key or a gate row? |
| `docs/` | Project documentation and reports: audits, the listen page, psychoacoustics maths. | Is it a dated snapshot or a page for a reader? |

A file that mixes both is split. Facts move to `knowledgebase/`, the rule that uses them stays in
`references/`.

## 3. Three loading tiers

The read table in `AGENTS.md` says what an agent must open for a given request. Keep the load small:

- **Always:** `SKILL.md` and `AGENTS.md`.
- **Per task:** the one or two knowledge-base files that match, or the reference file that matches.
  `scripts/research_kb.py` pulls only the matching sections into a project's research note.
- **Data only:** the JSON files in `knowledgebase/data/` and `references/data/`. Scripts read these;
  an agent should not read them as prose.

## 4. The one header format

Every markdown file in `knowledgebase/` and `references/` starts with this frontmatter and nothing
else:

```yaml
---
id: tamil                       # matches the file name, without a version suffix
title: Tamil folk, gaana and Carnatic
domain: culture                 # culture | genre | media | sound-design | data | workflow | mixing
                                # | instruments | spatial | scoring | sources
status: partly-sourced          # sourced | partly-sourced | unverified
sources: [research_sources_urls] # list; may be empty only when status is unverified
used_by: [scripts/research_kb.py, scripts/world.py]
updated: 2026-11-03
---
```

Rules for the fields:

- `id` matches the file name (`tamil.md` → `id: tamil`). No version numbers in either.
- `status: sourced` means every number in the file traces to a source listed in `sources`.
  `partly-sourced` means some do. `unverified` means none do, and the body says so.
- `sources` may only be empty when `status: unverified`.
- `used_by` lists the scripts or reference files that read this one. It is how a reader tells a live
  file from a dead one.
- Drop `schema_version`, `target_consumers`, `ai_parsable`, `encoding`, `document_type` and
  `system_id`; they carry no information a reader needs.

## 5. Every number needs a status

A number without a provenance label is worse than no number, because it reads like a measurement.
Label each one in the row or sentence that carries it:

- **read in source** — the figure was read in the cited paper or book;
- **standard result** — a textbook result, cited as such;
- **starting value, untested** — chosen to start from, not measured or cited.

`knowledgebase/sound-design/sfx-formulas.md` is the
model: each row says what was read and what was not.

This is the record of what was read and what was **not**, so an
"unverified" status is a statement about the work, not a mark of shame.

## 6. No count in prose

"All 18 documents", "44 reference files" and similar counts go stale the first time a file is added.
Describe the set instead: "the documents in this folder", "the culture files".

## 7. Citing a document

`scripts/research_kb.py` cites a document by its `id`. Any
change to an `id` breaks a citation in an existing project's research note, so change the file name
and the `id` together, and only when the rename is worth it.

## Status and sources

Every file carries `status` and `sources` in its front matter.

- `status: unverified` means the numbers are starting points from practice. The file opens with a
  **Not verified** note, and a piece that uses one of its numbers calls it a starting value.
- `status: sourced` means every number is cited in `sources`; an empty list under `sourced` fails
  `tests/check_kb.py`.
- A number added later gets a source or the words "starting value" on the same line.
- A new file also gets a row in `README.md` with its status.
