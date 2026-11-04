#!/usr/bin/env python3
"""Find the reference files a task needs, by keyword match over their own text.

Nothing here lists a file, a topic or a tag: the index is rebuilt from `references/**/*.md` on every run.
A file's YAML front matter is used when present (`title`, `summary`, `tags`, `load_when`); when it is missing,
the first heading is the title and the headings are the tags, so the finder still works on a new file.

Usage
    python scripts/find_references.py "vocal formants choir"
    python scripts/find_references.py --tags imm elevation
    python scripts/find_references.py --list
    python scripts/find_references.py --check          # front matter audit, exits 1 if a file has none

Scoring is BM25 over the body, plus a title hit and a tag hit, and the best-scoring sections are printed so the
reader can jump straight to the lines that matter instead of reading the whole file.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "references"

STOP = set(
    """a an the and or but if then than that this these those of to in on for with without from by as at is are was
    were be been being it its into over under after before when where which who whom what how why not no do does did
    done can could should would must may might will shall you your we our they them their he she his her there here
    only also very more most less least some any all each every both few many much such same other another one two
    three per via use used using make makes made get gets got give gives given keep keeps kept see sees seen say says
    said take takes taken put puts set sets run runs ran go goes went come comes came know knows known new old
    """.split()
)

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
WORD = re.compile(r"[a-z0-9][a-z0-9'+#._-]*")


def stem(word: str) -> str:
    for suffix in ("ies", "ing", "ers", "es", "ed", "er", "ly", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    out = []
    for raw in WORD.findall(text.lower()):
        if raw in STOP or len(raw) < 2:
            continue
        out.append(stem(raw))
    return out


def parse_front_matter(text: str) -> tuple[dict, int]:
    """Return (fields, body_start_line). Understands the small YAML subset a reference file uses."""
    if not text.startswith("---"):
        return {}, 0
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return {}, 0
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, 0

    fields: dict[str, object] = {}
    key = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- ") and key:
            fields.setdefault(key, [])
            if isinstance(fields[key], list):
                fields[key].append(raw.lstrip()[2:].strip().strip("\"'"))
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value.startswith("[") and value.endswith("]"):
            fields[key] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        elif value:
            fields[key] = value.strip("\"'")
        else:
            fields[key] = []
    return fields, end + 1


def load(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    fields, start = parse_front_matter(text)
    body_lines = text.splitlines()[start:]

    sections: list[tuple[str, int, list[str]]] = []
    heading, heading_line, buffer = "(intro)", start + 1, []
    for offset, line in enumerate(body_lines):
        m = HEAD.match(line)
        if m:
            sections.append((heading, heading_line, buffer))
            heading, heading_line, buffer = m.group(2).strip(), start + offset + 1, []
        else:
            buffer.append(MD_LINK.sub(lambda mm: mm.group(1).replace("/", " ").replace("-", " "), line))
    sections.append((heading, heading_line, buffer))

    body_tokens: list[str] = []
    for _, _, lines in sections:
        body_tokens.extend(tokenize("\n".join(lines)))
    if not body_tokens:
        return None

    title = str(fields.get("title") or next((h for h, _, _ in sections if h != "(intro)"), path.stem))
    tags = fields.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(t).lower() for t in tags]
    load_when = fields.get("load_when") or []
    if isinstance(load_when, str):
        load_when = [load_when]

    section_index = []
    for name, line, lines in sections:
        toks = tokenize(name + "\n" + "\n".join(lines))
        if toks:
            section_index.append((name, line, Counter(toks), len(toks)))

    return {
        "path": path.relative_to(ROOT).as_posix(),
        "title": title,
        "summary": str(fields.get("summary", "")),
        "tags": tags,
        "load_when": [str(x) for x in load_when],
        "has_front_matter": bool(fields),
        "lines": len(text.splitlines()),
        "tokens": Counter(body_tokens),
        "length": len(body_tokens),
        "sections": section_index,
        "headings": [h for h, _, _ in sections if h != "(intro)"],
    }


def build() -> list[dict]:
    docs = []
    for path in sorted(REFS.rglob("*.md")):
        if path.name == "README.md" and path.parent == REFS:
            continue
        doc = load(path)
        if doc:
            docs.append(doc)
    return docs


def idf(docs: list[dict]) -> dict[str, float]:
    n = len(docs)
    seen: Counter = Counter()
    for doc in docs:
        for term in doc["tokens"]:
            seen[term] += 1
    return {term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in seen.items()}


def score(docs: list[dict], query: list[str], top: int) -> list[dict]:
    weights = idf(docs)
    avg = sum(d["length"] for d in docs) / max(1, len(docs))
    k1, b = 1.4, 0.75
    ranked = []
    for doc in docs:
        tf = doc["tokens"]
        total = 0.0
        hits: list[str] = []
        for term in query:
            f = tf.get(term, 0)
            if not f:
                continue
            hits.append(term)
            total += weights.get(term, 0.0) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * doc["length"] / avg))
        tag_text = " ".join(doc["tags"])
        title_text = (doc["title"] + " " + doc["summary"]).lower()
        for term in query:
            if term in tag_text:
                total += 2.0
            if term in title_text:
                total += 1.5
        if total <= 0:
            continue

        best_sections = []
        for name, line, counts, length in doc["sections"]:
            local = sum(weights.get(t, 0.0) * counts.get(t, 0) / math.sqrt(max(1, length)) for t in query)
            if local > 0:
                best_sections.append((local, name, line))
        best_sections.sort(reverse=True)
        ranked.append({**doc, "score": round(total, 2), "matched": hits, "sections": best_sections[:3]})

    ranked.sort(key=lambda d: d["score"], reverse=True)
    return ranked[:top]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find the reference files a task needs.")
    ap.add_argument("query", nargs="*", help="words describing what you are about to do")
    ap.add_argument("--top", type=int, default=5, help="how many files to print (default 5)")
    ap.add_argument("--tags", nargs="+", help="only files whose tags contain one of these words")
    ap.add_argument("--list", action="store_true", help="every reference file with its tags")
    ap.add_argument("--check", action="store_true", help="report files with no or incomplete front matter")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    docs = build()
    if not docs:
        print("no reference files found under references/", file=sys.stderr)
        return 2
    if args.tags:
        wanted = [t.lower() for t in args.tags]
        docs = [d for d in docs if any(w in " ".join(d["tags"]) for w in wanted)]
        if not docs:
            print("no file carries that tag; try --list", file=sys.stderr)
            return 1

    if args.check:
        required = ("title", "summary", "tags", "load_when")
        bad = 0
        for doc in docs:
            missing = [key for key in required if not doc.get(key)]
            if not doc["has_front_matter"] or missing:
                bad += 1
                state = "no front matter" if not doc["has_front_matter"] else "missing: " + ", ".join(missing)
                print(f"{doc['path']}: {state}")
        print(f"{len(docs)} files, {bad} need work")
        return 1 if bad else 0

    if args.list or (args.tags and not args.query):
        for doc in docs:
            print(f"{doc['path']}  [{', '.join(doc['tags']) or '-'}]  {doc['summary']}")
        return 0

    if not args.query:
        ap.print_help()
        return 2

    query = tokenize(" ".join(args.query))
    if not query:
        print("query had no usable words", file=sys.stderr)
        return 2
    results = score(docs, query, args.top)
    if not results:
        print("nothing matched; try fewer or plainer words, or --list")
        return 1

    if args.json:
        print(json.dumps(
            [{k: v for k, v in r.items() if k not in ("tokens", "sections")} |
             {"sections": [[round(s, 2), n, ln] for s, n, ln in r["sections"]]}
             for r in results], indent=2))
        return 0

    print(f"query: {' '.join(query)}")
    for r in results:
        print(f"\n{r['score']:>6.2f}  {r['path']}")
        print(f"        {r['title']}")
        if r["summary"]:
            print(f"        {r['summary']}")
        for _, name, line in r["sections"]:
            print(f"        -> line {line}: {name}")
    print("\nRead only these files, and inside them only the sections above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
