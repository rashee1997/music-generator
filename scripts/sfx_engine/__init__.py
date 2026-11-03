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
"""sfx_engine - one-hit effects: a moment, triggered.

This package owns what makes an effect different from ambience: it is short, it is triggered, it has a mix position,
and it may need to be laid on a timeline under picture or music. It owns none of the physics; that is phys_core, shared
with env_engine.

    oneshot.py   make() and timeline(): a preset to mono samples, and many effects onto a stereo bed

`sfx.py` in scripts/ stays the public entry point (the score, `render_natural.py` and the project gate call it). Its 28
built-in recipes remain as compatibility adapters, so a score written before the physical scene existed still renders.
"""
