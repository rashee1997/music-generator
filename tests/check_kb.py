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
  - has no front matter, or misses document_id, target_consumers, schema_version, status or sources,
  - claims status: sourced with an empty sources list,
  - links to a file that is not there,
  - names a .py that does not exist,
  - is not listed in knowledgebase/README.md,
  - has no "Not verified" note when its status is not sourced.

Run: python tests/check_kb.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, 'knowledgebase')
REQUIRED = ('document_id', 'target_consumers', 'schema_version', 'status', 'sources')
SKIP_HEADER = ('README.md', 'SCHEMA.md')
MD_LINK = re.compile(r'\]\(([^)\s]+)\)')
CODE_PATH = re.compile(r'`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|json|py|txt))`')
PY_NAME = re.compile(r'`([A-Za-z0-9_.-]+\.py)`')
PREFIXES = ('references/', 'knowledgebase/', 'scripts/', 'templates/', 'docs/', 'presets/', 'video-mixer/', 'tests/')


def files():
    for base, _dirs, names in os.walk(KB):
        for n in sorted(names):
            if n.endswith('.md'):
                yield os.path.join(base, n)


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
            value = m.group(2).strip()
            data[key] = [] if not value else value
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
    fails = []
    for path in files():
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
        text = open(path, encoding='utf-8', errors='replace').read()
        if os.path.basename(path) not in SKIP_HEADER:
            data, end = front_matter(text)
            if not end:
                fails.append(f'{rel}: no front matter')
            else:
                for key in REQUIRED:
                    if key not in data:
                        fails.append(f'{rel}: header missing {key}')
                status = str(data.get('status', '')).lower()
                sources = data.get('sources', [])
                if status == 'sourced' and not sources:
                    fails.append(f'{rel}: status sourced but sources is empty')
                if status != 'sourced' and 'not verified' not in text[:1200].lower():
                    fails.append(f'{rel}: not sourced and no "Not verified" note')
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

    for f in fails:
        print(f'FAIL: {f}')
    print(f'{len(fails)} fail(s)')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
