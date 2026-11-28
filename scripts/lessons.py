#!/usr/bin/env python3
"""lessons.py - find, suggest, add and check the lessons learnt (`lessons/*.md`), before a fix and after one.

A lesson is one entry in the YAML front matter of a file under `lessons/` (one file per kind of problem). The finder reads them fresh on every
run: nothing here lists a lesson or a keyword.

    python scripts/lessons.py find "stem.dropout 35 ms hole after a rest"        # analysis first: what happened before, what to measure, what to do
    python scripts/lessons.py find --row stem.dead
    python scripts/lessons.py suggest --log /tmp/render.log                        # every [FAIL] / [BLOCKED] line of a pipeline log, with its lessons
    python scripts/lessons.py suggest --project projects/<name>                    # the failing rows of reports/ci_report.json
    python scripts/lessons.py add --section gate-stem-rows --title "..." --keywords a,b,c --symptom "..." --cause "..." --fix "..."
    python scripts/lessons.py update S03 --set "evidence=trailer 2026-12-01"
    python scripts/lessons.py list
    python scripts/lessons.py check                                                 # format and size; exits 1 on a problem

Do not bloat: an entry is at most 9 fields-lines and 1,400 characters, a file at most 160 lines, and `add` refuses an entry whose keywords overlap an
existing one (it names the entry to update instead).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / 'lessons'
REQUIRED = ('id', 'title', 'keywords', 'symptom', 'fix')
FIELDS = ('id', 'title', 'keywords', 'rows', 'symptom', 'cause', 'check', 'fix', 'avoid', 'evidence')
MAX_FILE_LINES, MAX_ENTRY_CHARS, MAX_ENTRY_FIELDS = 160, 1400, 10
DUPLICATE_OVERLAP = 0.6
STOP = set('a an and are as at be by for from in is it its of on or that the this to with was were not no into than then so if but over under after before '
           'when while one two per use used using make made get got has have had do does done can cannot will would should must may might also only just'.split())
FRONT = re.compile(r'\A---\n(.*?)(?:\n---[ \t]*(?:\n|\Z)(.*))?\Z', re.S)


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r'[a-z0-9][a-z0-9_.+\-]*', str(text).lower()) if t not in STOP and len(t) > 1]


def load_file(path: Path):
    text = path.read_text(encoding='utf-8')
    m = FRONT.match(text)
    if not m:
        return None, text
    return yaml.safe_load(m.group(1)) or {}, (m.group(2) or '')


def load_all() -> list[dict]:
    out = []
    for p in sorted(LESSONS.glob('*.md')):
        if p.name.lower() == 'readme.md':
            continue
        try:
            data, _ = load_file(p)
        except yaml.YAMLError:
            continue                       # `check` reports it
        if not isinstance(data, dict):
            continue
        for item in data.get('lessons') or []:
            if isinstance(item, dict):
                out.append(dict(item, _file=p.name, _section=data.get('section', p.stem)))
    return out


def score(lesson: dict, query: str, qtok: set[str], rows: list[str]) -> float:
    q = query.lower()
    s = 0.0
    for r in lesson.get('rows') or []:
        if str(r).lower() in q or str(r).lower() in [x.lower() for x in rows]:
            s += 6.0
    for kw in lesson.get('keywords') or []:
        k = str(kw).lower()
        if len(k) > 2 and k in q:
            s += 3.0
            continue
        s += 0.7 * sum(1 for t in tokens(k) if t in qtok)
    s += 0.4 * sum(1 for t in tokens(lesson.get('title', '')) if t in qtok)
    for field in ('symptom', 'cause'):
        s += min(1.0, 0.1 * sum(1 for t in tokens(lesson.get(field, '')) if t in qtok))
    return round(s, 2)


def find(query: str, rows: list[str] | None = None, top: int = 5, min_score: float = 2.0) -> list[tuple[float, dict]]:
    rows = rows or []
    qtok = set(tokens(query + ' ' + ' '.join(rows)))
    hits = [(score(l, query, qtok, rows), l) for l in load_all()]
    return sorted([h for h in hits if h[0] >= min_score], key=lambda h: -h[0])[:top]


def show(hit: tuple[float, dict], indent: str = '') -> str:
    sc, l = hit
    lines = [f"{indent}{l['id']}  {l['title']}   [score {sc}]  lessons/{l['_file']}"]
    for label, key in (('symptom', 'symptom'), ('cause', 'cause'), ('measure first', 'check'), ('fix', 'fix'), ('avoid', 'avoid'), ('seen', 'evidence')):
        if l.get(key):
            lines.append(f"{indent}  {label}: {l[key]}")
    return '\n'.join(lines)


GUIDE = ('Before you implement: (1) read the entries above, (2) run the "measure first" step so the cause is a measurement, not a guess, '
         '(3) change one thing, (4) after the fix, update the lesson (`lessons.py update <id>` or `add`).')


def cmd_find(a) -> int:
    query = ' '.join(a.query or [])
    if not query and not a.row:
        print('give some words or --row', file=sys.stderr)
        return 2
    hits = find(query, a.row or [], a.top, a.min_score)
    if a.json:
        print(json.dumps([dict(score=s, **{k: v for k, v in l.items()}) for s, l in hits], indent=1))
        return 0
    if not hits:
        print('no lesson matches. If this is a new mistake, fix it, then `lessons.py add` it (rule 22).')
        return 0
    print('\n\n'.join(show(h) for h in hits))
    print('\n' + GUIDE)
    return 0


def failing_lines_from_log(path: Path) -> list[str]:
    seen, out = set(), []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if re.search(r'\[(FAIL|BLOCKED)\]', line):
            s = re.sub(r'\s+', ' ', line.strip())
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def failing_lines_from_project(project: Path) -> list[str]:
    p = project / 'reports' / 'ci_report.json'
    out = []

    def walk(x):
        if isinstance(x, dict):
            if str(x.get('level', '')).upper() == 'FAIL' and x.get('row'):
                out.append(f"[FAIL] {x['row']} {x.get('detail', '')}")
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    if p.exists():
        walk(json.loads(p.read_text(encoding='utf-8')))
    return out


def cmd_suggest(a) -> int:
    lines = []
    if a.log:
        lines += failing_lines_from_log(Path(a.log))
    if a.project:
        lines += failing_lines_from_project(Path(a.project))
    if not lines:
        print('no [FAIL] or [BLOCKED] lines found')
        return 0
    shown = set()
    for line in lines:
        hits = [h for h in find(line, [], a.top, a.min_score)]
        print(f"\n{line[:200]}")
        if not hits:
            print('  no lesson: after the fix, `lessons.py add` it.')
            continue
        for h in hits:
            tag = ' (shown above)' if h[1]['id'] in shown else ''
            print(show(h, '  ') if not tag else f"  {h[1]['id']}  {h[1]['title']}{tag}")
            shown.add(h[1]['id'])
    print('\n' + GUIDE)
    return 0


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def overlap(a: set, b: set) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def entry_text(lesson: dict) -> str:
    body = yaml.safe_dump([{k: lesson[k] for k in FIELDS if k in lesson and lesson[k] not in (None, '', [])}],
                          sort_keys=False, width=100000, allow_unicode=True, default_flow_style=None)
    return ''.join('  ' + ln + '\n' for ln in body.splitlines())


def cmd_add(a) -> int:
    path = LESSONS / f'{a.section}.md'
    kw = [k.strip() for k in a.keywords.split(',') if k.strip()]
    lesson = dict(id=a.id or '', title=a.title, keywords=kw, rows=[r.strip() for r in (a.rows or '').split(',') if r.strip()],
                  symptom=a.symptom, cause=a.cause, check=a.check, fix=a.fix, avoid=a.avoid, evidence=a.evidence)
    if len(kw) < 2:
        print('give at least two keywords', file=sys.stderr)
        return 2
    new_kw = set(tokens(' '.join(kw))) | {r.lower() for r in lesson['rows']}
    for other in load_all():
        old = set(tokens(' '.join(map(str, other.get('keywords') or [])))) | {str(r).lower() for r in other.get('rows') or []}
        if not a.force and (overlap(new_kw, old) >= DUPLICATE_OVERLAP or other.get('title', '').strip().lower() == a.title.strip().lower()):
            print(f"refused: {other['id']} ({other['title']}, lessons/{other['_file']}) already covers this "
                  f"(keywords overlap {overlap(new_kw, old):.0%}). Update it: python scripts/lessons.py update {other['id']} --set \"evidence=...\"", file=sys.stderr)
            return 1
    if path.exists():
        data, _ = load_file(path)
        ids = [str(l.get('id', '')) for l in (data or {}).get('lessons') or []]
    else:
        if not a.section_title:
            print(f'lessons/{a.section}.md does not exist: give --section-title to create it (one file per kind of problem)', file=sys.stderr)
            return 2
        path.write_text(f"---\nsection: {a.section}\ntitle: {a.section_title}\nlessons: []\n---\n", encoding='utf-8')
        ids = []
    if not lesson['id']:
        used = {str(l['id']) for l in load_all()}
        prefix = re.match(r'[A-Za-z]+', ids[0]).group(0) if ids else next(
            (c for c in (a.section[:1].upper() + a.section[1:2].upper(), *'ABCDEFGHIJKLMNOPQRSTUVWXYZ') if not any(u.startswith(c) for u in used)), 'Z')
        n = 1 + max([int(re.sub(r'\D', '', u) or 0) for u in used if u.startswith(prefix)] + [0])
        lesson['id'] = f'{prefix}{n:02d}'
    if any(lesson['id'] == l['id'] for l in load_all()):
        print(f"refused: the id {lesson['id']} is used", file=sys.stderr)
        return 1
    data, _ = load_file(path)
    data.setdefault('lessons', [])
    data['lessons'] = (data['lessons'] or []) + [{k: lesson[k] for k in FIELDS if lesson.get(k) not in (None, '', [])}]
    path.write_text('---\n' + yaml.safe_dump(data, sort_keys=False, width=100000, allow_unicode=True, default_flow_style=None) + '---\n', encoding='utf-8')
    print(f"added {lesson['id']} to lessons/{path.name}")
    problems = check()
    for p in problems:
        print('  ' + p, file=sys.stderr)
    return 1 if problems else 0


def cmd_update(a) -> int:
    for p in sorted(LESSONS.glob('*.md')):
        if p.name.lower() == 'readme.md':
            continue
        data, body = load_file(p)
        for item in (data or {}).get('lessons') or []:
            if item.get('id') == a.id:
                for kv in a.set or []:
                    k, _, v = kv.partition('=')
                    k = k.strip()
                    if k not in FIELDS:
                        print(f'unknown field {k}; fields: {", ".join(FIELDS)}', file=sys.stderr)
                        return 2
                    item[k] = [x.strip() for x in v.split(',')] if k in ('keywords', 'rows') else v.strip()
                head = yaml.safe_dump(data, sort_keys=False, width=100000, allow_unicode=True, default_flow_style=None)
                p.write_text(f'---\n{head.rstrip()}\n---\n{body}', encoding='utf-8')
                print(f'updated {a.id} in lessons/{p.name}')
                problems = check()
                for q in problems:
                    print('  ' + q, file=sys.stderr)
                return 1 if problems else 0
    print(f'no lesson {a.id}', file=sys.stderr)
    return 1


def check() -> list[str]:
    problems, ids = [], {}
    all_l = []
    for p in sorted(LESSONS.glob('*.md')):
        if p.name.lower() == 'readme.md':
            continue
        n_lines = len(p.read_text(encoding='utf-8').splitlines())
        if n_lines > MAX_FILE_LINES:
            problems.append(f'{p.name}: {n_lines} lines (limit {MAX_FILE_LINES}): merge entries with one cause, or split the section')
        try:
            data, _ = load_file(p)
        except yaml.YAMLError as exc:
            problems.append(f'{p.name}: the front matter is not valid YAML ({exc})')
            continue
        if not isinstance(data, dict) or not data.get('section') or not data.get('title'):
            problems.append(f'{p.name}: front matter needs section, title and lessons')
            continue
        for l in data.get('lessons') or []:
            lid = l.get('id', '?')
            for f in REQUIRED:
                if not l.get(f):
                    problems.append(f'{p.name} {lid}: missing {f}')
            if len(l.get('keywords') or []) < 2:
                problems.append(f'{p.name} {lid}: at least two keywords')
            extra = [k for k in l if k not in FIELDS]
            if extra:
                problems.append(f'{p.name} {lid}: unknown field(s) {extra}')
            if len([k for k in l if k in FIELDS]) > MAX_ENTRY_FIELDS:
                problems.append(f'{p.name} {lid}: too many fields')
            size = len(yaml.safe_dump(l, allow_unicode=True))
            if size > MAX_ENTRY_CHARS:
                problems.append(f'{p.name} {lid}: {size} characters (limit {MAX_ENTRY_CHARS}): shorten it, keep the cause and the fix')
            if lid in ids:
                problems.append(f'{p.name} {lid}: the id is also in {ids[lid]}')
            ids[lid] = p.name
            all_l.append((p.name, l))
    for i, (fa, a) in enumerate(all_l):
        ka = set(tokens(' '.join(map(str, a.get('keywords') or [])))) | {str(r).lower() for r in a.get('rows') or []}
        for fb, b in all_l[i + 1:]:
            kb = set(tokens(' '.join(map(str, b.get('keywords') or [])))) | {str(r).lower() for r in b.get('rows') or []}
            if jaccard(ka, kb) >= 0.7:
                problems.append(f'{a.get("id")} and {b.get("id")} share {jaccard(ka, kb):.0%} of their keywords: merge them')
    return problems


def cmd_check(_a) -> int:
    problems = check()
    n = len(load_all())
    for p in problems:
        print(p)
    print(f'{n} lesson(s), {len(problems)} problem(s)')
    return 1 if problems else 0


def cmd_list(_a) -> int:
    for l in load_all():
        print(f"{l['id']:5s} {l['_file']:22s} {l['title']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('find')
    f.add_argument('query', nargs='*')
    f.add_argument('--row', action='append')
    f.add_argument('--top', type=int, default=5)
    f.add_argument('--min-score', type=float, default=2.0)
    f.add_argument('--json', action='store_true')
    f.set_defaults(fn=cmd_find)
    s = sub.add_parser('suggest')
    s.add_argument('--log')
    s.add_argument('--project')
    s.add_argument('--top', type=int, default=3)
    s.add_argument('--min-score', type=float, default=3.0)
    s.set_defaults(fn=cmd_suggest)
    ad = sub.add_parser('add')
    ad.add_argument('--section', required=True)
    ad.add_argument('--section-title')
    ad.add_argument('--id')
    ad.add_argument('--title', required=True)
    ad.add_argument('--keywords', required=True)
    ad.add_argument('--rows')
    ad.add_argument('--symptom', required=True)
    ad.add_argument('--cause')
    ad.add_argument('--check')
    ad.add_argument('--fix', required=True)
    ad.add_argument('--avoid')
    ad.add_argument('--evidence')
    ad.add_argument('--force', action='store_true')
    ad.set_defaults(fn=cmd_add)
    up = sub.add_parser('update')
    up.add_argument('id')
    up.add_argument('--set', action='append', required=True)
    up.set_defaults(fn=cmd_update)
    sub.add_parser('check').set_defaults(fn=cmd_check)
    sub.add_parser('list').set_defaults(fn=cmd_list)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == '__main__':
    sys.exit(main())
