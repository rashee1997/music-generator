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

"""deep_merge.py - one recursive dict merge for the whole skill.

`over` wins key by key; nested dicts merge, everything else replaces. Preset layering
(skill -> project -> score) and the mix schema both depend on exactly this rule, so it
lives in one place instead of three.
"""
import copy


def merge(base, over):
    """A new dict: `over` laid over `base`, nested dicts merged. An absent section (`None`) is an empty one."""
    if over is None:
        return copy.deepcopy(base)
    if not isinstance(over, dict):
        return copy.deepcopy(over)
    out = copy.deepcopy(base) if isinstance(base, dict) else {}
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out
