---
title: References
summary: What this folder is, the front matter every file carries, and how to find the one file a task needs.
tags: [index, references, front matter, finder]
load_when:
  - unsure which reference file applies
  - adding or renaming a reference file
---

# References

Instructions and lookup tables for the AI. No history, no sources, no test results, no marketing words: a line here
either tells you what to do or gives you a value to use.

## Find the file you need

```
python scripts/find_references.py "the words of the brief" --top 5
python scripts/find_references.py --tags vocal
python scripts/find_references.py --list
python scripts/find_references.py --check
```

The finder indexes this folder at run time by keyword; no file list is stored. It prints the best-matching file, its
summary and the line numbers of the sections that matched. Read those sections only.

## The folders

| Folder | Holds |
|---|---|
| `workflow/` | how a piece is made: brief, research, direction, score, render, delivery |
| `scoring/` | what to choose: genres, moods, cultures, fusion, video |
| `mixing/` | mix presets, balance, humanization, the gate |
| `instruments-and-vocals/` | sources, ranges, and how voices are built |
| `spatial/` | space, distance, elevation, physical scenes |
| `sound-design/` | turning a sound name into a model |
| `data/` | the JSON the scripts read: presets, styles, vocal data, sound models |

## Front matter

Every file starts with:

```yaml
---
title: Mixing and mastering
summary: One line naming the decision this file lets you make.
tags: [mix, master, loudness]
load_when:
  - building or auditing a mix preset
---
```

`title`, `summary`, `tags` and `load_when` are required; `scripts/find_references.py --check` fails without them and
CI runs it. The title is not repeated as a heading rule: keep the H1 short and factual.

## Writing style

- An instruction in the imperative, or a table of values. Nothing else.
- One home per rule. A second file points at the first.
- No counts ("all the documents", never a number): a count goes stale.
- Every number is either measured, cited from the knowledge base, or labelled as a starting value.
- `tests/check_references.py` rejects banned provenance phrases, URLs, broken relative links and counts in prose.
