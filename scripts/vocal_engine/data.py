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

"""Loads the engine's JSON data from references/vocal-engine/. Nothing musical is hard-coded in the scripts."""
import copy
import json
import os
from functools import lru_cache

import deep_merge as _merge

DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'references', 'vocal-engine'))


@lru_cache(maxsize=None)
def _read(name):
    with open(os.path.join(DIR, name), encoding='utf-8') as f:
        return json.load(f)


def defaults():
    """Fresh deep copy of defaults.json (callers may mutate it)."""
    return copy.deepcopy({k: v for k, v in _read('defaults.json').items() if not k.startswith('_') and k != 'sources'})


def styles():
    return copy.deepcopy({k: v for k, v in _read('styles.json').items() if not k.startswith('_')})


def deep_merge(base, over):
    """over wins, key by key; dicts merge, everything else replaces. The rule lives in deep_merge.py."""
    return _merge.merge(base, over)
