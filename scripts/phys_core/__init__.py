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
"""phys_core - the shared physical layer for ambience (`env:`) and one-hit effects (`sfx:`).

Neither presentation owns the physics: `env_engine` decides how long a bed sounds and how it is spread over a place,
`sfx_engine` decides when a hit is triggered, and both ask this package what the sound physically is. No module here
knows about tracks, presets, stems or the score.

    scene.py      the JSON scene schema, its validator and its renderer
    registry.py   which mechanisms a scene may name today, and which stage brings the rest
    baseline.py   freeze / verify renders, so "nothing changed audibly" is a measurement and not a hope

Stage 0 of the upgrade: the schema and validator are live and a scene renders through `sound_model.render` unchanged.
See STATUS-phys-sound.md for the change log and the stages.
"""
VERSION = '0.1.0'
