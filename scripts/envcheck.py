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

#!/usr/bin/env python3
"""envcheck.py - compare the installed packages with the '==' pins in requirements.txt.

    python scripts/envcheck.py        # prints one line per package that is missing or differs; exit 1 if any
pipeline.py calls mismatches() at start-up and prints them as WARN lines (it never blocks a render).
"""
import importlib.metadata as md
import os
import re
import sys

REQ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'requirements.txt')


def mismatches(req=REQ):
    out = []
    if not os.path.isfile(req):
        return out
    for line in open(req, encoding='utf-8'):
        m = re.match(r'^([A-Za-z0-9_.\-]+)==([^\s#]+)', line.strip())
        if not m:
            continue
        name, want = m.groups()
        try:
            have = md.version(name)
        except md.PackageNotFoundError:
            out.append(f'{name} is not installed (pinned {want})')
            continue
        if have != want:
            out.append(f'{name} {have} installed, tested with {want}')
    return out


if __name__ == '__main__':
    bad = mismatches()
    for b in bad:
        print('WARN', b)
    print('environment:', 'differs from the pins' if bad else 'matches the pins')
    sys.exit(1 if bad else 0)
