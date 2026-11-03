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
"""env_engine - ambience: a place that keeps sounding.

This package owns what makes ambience different from an effect: it runs for minutes, it has beds and spots, it is
spread over a place, and its statistics evolve. It owns none of the physics; that is phys_core, shared with sfx_engine.

    render.py   a place as layers or as a physical scene, mono layers -> a stereo bed

`environment.py` in scripts/ stays the public entry point (the score, `render_natural.py` and the project gate call it),
and it delegates here. Nothing in this package knows about a score.
"""
