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

"""Guard for references/: instructions and lookup tables only.

Fails when a reference file carries provenance (history, "this pass", a fetch note), a URL, a link to a file that is
not there, or a count in prose (counts go stale; name the thing, not how many). Warns above 250 lines.

Run: python tests/check_references.py            (repo root or anywhere)
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, 'references')

PROVENANCE = re.compile(r'instagram|medium\.com|wikipedia|study\.com|pressbooks|general sources|ohiolink'
                        r'|Ryan Leach|Berklee|ArtofComposing|What was read|Not verified|section 7a', re.I)
BANNED = re.compile(PROVENANCE.pattern +
                    r'|this session|this pass|TinyFish|Moved verbatim|Reference only|How to create / use'
                    r'|What changed|Before \| Now|written from memory|not fetched|could not be fetched'
                    r'|Arsenal|Thermodynamic|Sacred Lead|JUCE|Headless VST3|state-of-the-art|cutting-edge'
                    r'|robust|seamless|powerful'
                    r"|not (yet )?(added|covered|implemented)|have not been|haven't|TODO:|FIXME"
                    r"|basically|obviously|needless to say|as you can see|it's worth noting|please note", re.I)
EMOJI = re.compile('[🌀-🫿☀-➿⬀-⯿️]')
URL = re.compile(r'https?://')
# a count in prose: "42 genres", "9 scales", "16 rows" - a number followed by a plural noun of a thing the skill owns
COUNT = re.compile(r'(?<![\w.])[0-9]+\s+(genres|scales|instruments|presets|documents|files|cultures|rows|moods'
                   r'|effects|spaces|sounds|models|sections|tracks)\b', re.I)
MD_LINK = re.compile(r'\]\(([^)\s]+)\)')
CODE_PATH = re.compile(r'`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|json|py|txt|html))`')
PREFIXES = ('references/', 'knowledgebase/', 'scripts/', 'templates/', 'docs/', 'presets/', 'video-mixer/', 'tests/')


def reference_files():
    for base, _dirs, names in os.walk(REF):
        for n in sorted(names):
            if n.endswith('.md'):
                yield os.path.join(base, n)


def resolves(target, start):
    """A link resolves when it is a real file relative to the doc or to the repository root."""
    if target.startswith(('#', 'mailto:')):
        return True
    target = target.split('#')[0]
    if not target:
        return True
    for base in (os.path.dirname(start), ROOT):
        if os.path.exists(os.path.normpath(os.path.join(base, target))):
            return True
    return False


def main():
    fails, warns = [], []
    for path in reference_files():
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
        text = open(path, encoding='utf-8', errors='replace').read()
        for i, line in enumerate(text.splitlines(), 1):
            hit = BANNED.search(line)
            # a catalogue label and a mood/expression word are vocabulary, not hype: both are allowed
            spans = [(m.start(), m.end()) for m in re.finditer(r'`[^`]*`', line)]
            quoted = hit and any(a <= hit.start() and hit.end() <= b for a, b in spans)
            if hit and not quoted and not (hit.group(0) == 'Powerful' and 'Powerful Percussion' in line):
                fails.append(f'{rel}:{i}: banned text: {hit.group(0).strip()}')
            if EMOJI.search(line):
                fails.append(f'{rel}:{i}: emoji in references')
            if URL.search(line):
                fails.append(f'{rel}:{i}: URL in references')
            if COUNT.search(line):
                fails.append(f'{rel}:{i}: count in prose: {COUNT.search(line).group(0).strip()}')
            for target in MD_LINK.findall(line):
                if URL.match(target) or not resolves(target, path):
                    fails.append(f'{rel}:{i}: link to a missing file: {target}')
            for target in CODE_PATH.findall(line):
                if target.startswith(PREFIXES) and not resolves(target, path):
                    fails.append(f'{rel}:{i}: path that does not exist: {target}')
        n = len(text.splitlines())
        if n > 300:
            fails.append(f'{rel}: {n} lines (limit 300)')
        elif n > 250:
            warns.append(f'{rel}: {n} lines')

    # a style overlay may name what it changes, not where the idea was read
    styles = os.path.join(REF, 'data', 'styles')
    for name in sorted(os.listdir(styles)) if os.path.isdir(styles) else []:
        if not name.endswith('.json'):
            continue
        rel = f'references/data/styles/{name}'
        try:
            data = json.load(open(os.path.join(styles, name), encoding='utf-8'))
        except ValueError as exc:
            fails.append(f'{rel}: invalid JSON: {exc}')
            continue
        for key in ('sources', 'source'):
            for value in data.get(key) or []:
                hit = PROVENANCE.search(str(value))
                if hit:
                    fails.append(f'{rel}: {key} cites {hit.group(0).strip()}')

    for w in warns:
        print(f'warn: {w}')
    for f in fails:
        print(f'FAIL: {f}')
    print(f'{len(fails)} fail(s), {len(warns)} warning(s)')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
