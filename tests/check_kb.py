# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Guard for knowledgebase/: facts only, each one labelled with where it came from.

Fails when a knowledge-base file
  - has no front matter, or misses id, title, domain, status, sources, used_by or updated,
  - has an id that is not its file name,
  - names a domain outside culture | genre | media | sound-design,
  - claims a status other than unverified with an empty sources list,
  - carries scaffolding: a table of contents, a mermaid block, a "Target Application" line,
  - uses a marketing word in a heading (ontology, magical, sacred, ultimate, vast, blueprint,
    "Master X", "Knowledge Base", "Machine-Parsable"),
  - names a person or game as a label (the BANNED_NAMES list),
  - is over 400 lines (warns over 300); python blocks listed in ALLOWED_PYTHON are not counted,
  - carries a python block that is not in ALLOWED_PYTHON (a capability the skill does not script),
  - links to a file that is not there, or names a .py that does not exist,
  - is not listed in knowledgebase/README.md,
  - has no "Not verified" note when its status is not sourced.

ALLOWED_PYTHON is the list of listings that describe a capability the scripts do not have. Add a block
only together with the decision to keep that capability out of code.

Run: python tests/check_kb.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, 'knowledgebase')
REQUIRED = ('id', 'title', 'domain', 'status', 'sources', 'used_by', 'updated')
DOMAINS = ('culture', 'genre', 'media', 'sound-design')
SKIP_HEADER = ('README.md', 'SCHEMA.md')

# (file, nth python block in that file) - capability not in scripts, kept on purpose
ALLOWED_PYTHON = {
    ('cultures/flutes.md', 1),
    ('cultures/indian-film-fusion.md', 1),
    ('cultures/indian-film-fusion.md', 2),
    ('cultures/indian-film-fusion.md', 3),
    ('cultures/indian-film-fusion.md', 4),
    ('cultures/indian-film-fusion.md', 5),
    ('cultures/indian-film-fusion.md', 6),
    ('cultures/indian-film-fusion.md', 7),
    ('cultures/pan-indian.md', 1),
    ('genre-and-feel/commercial-promo.md', 1),
    ('media/game-music.md', 1),
    ('media/game-sfx.md', 1),
    ('media/video-scoring.md', 1),
    ('sound-design/audio-cloning.md', 1),
    ('sound-design/sfx-ambience.md', 1),
}

BANNED_NAMES = ('Anirudh', 'Rahman', 'Ilaiyaraaja', 'Max Martin', 'Weeknd', 'John Williams',
                'Howard Shore', 'Hans Zimmer', 'Zimmer', 'Lin-Manuel', 'Sephiroth', 'Elden Ring',
                'Cyberpunk 2077')
BANNED_WORDS = re.compile(r'\b(ontology|magical|sacred|ultimate|vast|blueprint|arsenal|revolutionary'
                          r'|cutting-edge)\b|\bMaster\s+[A-Z]|\bKnowledge Base\b|Machine-Parsable'
                          r'|Target Application', re.I)
TOC_HEAD = re.compile(r'^#{1,6}\s+.*(table of contents|machine-parsable)', re.I | re.M)
MERMAID = re.compile(r'^```mermaid', re.M)
HEADING = re.compile(r'^#{1,6}\s+.*$', re.M)
PY_BLOCK = re.compile(r'^```python\n.*?^```$', re.S | re.M)
FENCE = re.compile(r'^```([a-zA-Z]*)', re.M)
MD_LINK = re.compile(r'\]\(([^)\s]+)\)')
CODE_PATH = re.compile(r'`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|json|py|txt))`')
PY_NAME = re.compile(r'`([A-Za-z0-9_.-]+\.py)`')
PREFIXES = ('references/', 'knowledgebase/', 'scripts/', 'templates/', 'docs/', 'presets/', 'video-mixer/', 'tests/')


def files():
    for base, _dirs, names in os.walk(KB):
        for n in sorted(names):
            if n.endswith('.md'):
                yield os.path.join(base, n)


def _value(raw):
    """`[a, b]` -> ['a', 'b']; `x` -> 'x'; empty -> []."""
    raw = raw.strip()
    if raw.startswith('[') and raw.endswith(']'):
        return [v.strip().strip('"\'') for v in raw[1:-1].split(',') if v.strip()]
    return raw.strip('"\'') if raw else []


def front_matter(text):
    if not text.startswith('---'):
        return {}, 0
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end = i
            break
    if end is None:
        return {}, 0
    data, key = {}, None
    for raw in lines[1:end]:
        if raw.lstrip().startswith('- ') and key:
            data.setdefault(key, []).append(raw.split('- ', 1)[1].strip())
            continue
        m = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', raw)
        if m:
            key = m.group(1)
            data[key] = _value(m.group(2))
    return data, end


def resolves(target, start):
    if target.startswith(('#', 'mailto:')):
        return True
    target = target.split('#')[0]
    if not target:
        return True
    for base in (os.path.dirname(start), ROOT):
        if os.path.exists(os.path.normpath(os.path.join(base, target))):
            return True
    return False


def script_exists(name):
    for base, _dirs, names in os.walk(ROOT):
        if os.sep + '.git' in base or os.sep + '.venv' in base:
            continue
        if name in names:
            return True
    return False


def main():
    readme = open(os.path.join(KB, 'README.md'), encoding='utf-8').read()
    fails, warns = [], []
    for path in files():
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
        short = os.path.relpath(path, KB).replace('\\', '/')
        text = open(path, encoding='utf-8', errors='replace').read()
        body = text.split('\n')
        if os.path.basename(path) not in SKIP_HEADER:
            data, end = front_matter(text)
            if not end:
                fails.append(f'{rel}: no front matter')
            else:
                for key in REQUIRED:
                    if key not in data:
                        fails.append(f'{rel}: header missing {key}')
                if str(data.get('id', '')) != os.path.splitext(os.path.basename(path))[0]:
                    fails.append(f'{rel}: id is not the file name')
                if str(data.get('domain', '')) not in DOMAINS:
                    fails.append(f'{rel}: domain "{data.get("domain", "")}" is not one of: {", ".join(DOMAINS)}')
                status = str(data.get('status', '')).lower()
                sources = data.get('sources', [])
                if status != 'unverified' and not sources:
                    fails.append(f'{rel}: status {status} but sources is empty')
                if status != 'sourced' and 'not verified' not in text[:1200].lower():
                    fails.append(f'{rel}: not sourced and no "Not verified" note')

        if TOC_HEAD.search(text):
            fails.append(f'{rel}: has a table of contents')
        if MERMAID.search(text):
            fails.append(f'{rel}: has a mermaid block')
        for m in HEADING.finditer(text) if os.path.basename(path) not in SKIP_HEADER else []:
            if BANNED_WORDS.search(m.group(0)):
                fails.append(f'{rel}: marketing word in heading: {m.group(0).strip()}')
            if 'knowledge base' in m.group(0).lower():
                fails.append(f'{rel}: "Knowledge Base" in a title: {m.group(0).strip()}')
        for name in BANNED_NAMES:
            if name in text:
                fails.append(f'{rel}: names a person or game as a label: {name}')

        # python blocks: only the ones on the allowed list, and their lines do not count for the limit
        code_lines = 0
        n = 0
        for m in PY_BLOCK.finditer(text):
            n += 1
            if (short, n) not in ALLOWED_PYTHON:
                fails.append(f'{rel}: python block {n} is not in ALLOWED_PYTHON (a capability the scripts do not have)')
            code_lines += m.group(0).count('\n') + 1
        allowed_here = sum(1 for f, i in ALLOWED_PYTHON if f == short)
        if n != allowed_here:
            fails.append(f'{rel}: {n} python block(s) but ALLOWED_PYTHON lists {allowed_here}')

        # any other fence left open
        if len(FENCE.findall(text)) % 2:
            fails.append(f'{rel}: an unclosed code fence')

        counted = len(body) - code_lines
        if counted > 400:
            fails.append(f'{rel}: {counted} lines (limit 400)')
        elif counted > 300:
            warns.append(f'{rel}: {counted} lines')

        if os.path.basename(path) not in ('README.md', 'SCHEMA.md') and os.path.basename(path) not in readme:
            fails.append(f'{rel}: not listed in knowledgebase/README.md')
        for i, line in enumerate(text.splitlines(), 1):
            for target in MD_LINK.findall(line):
                if re.match(r'https?://', target):
                    continue
                if not resolves(target, path):
                    fails.append(f'{rel}:{i}: link to a missing file: {target}')
            for target in CODE_PATH.findall(line):
                if target.startswith(PREFIXES) and not resolves(target, path):
                    fails.append(f'{rel}:{i}: path that does not exist: {target}')
            for name in PY_NAME.findall(line):
                if '/' not in name and not script_exists(name):
                    fails.append(f'{rel}:{i}: names a script that does not exist: {name}')

    for w in warns:
        print(f'warn: {w}')
    for f in fails:
        print(f'FAIL: {f}')
    print(f'{len(fails)} fail(s), {len(warns)} warning(s)')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
