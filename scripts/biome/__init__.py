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

"""biome - any real or fictional acoustic environment from a JSON preset (Immersive 3.3).

    physics.py     the closed-form laws (Strouhal, terminal velocity, Minnaert, dune pitch, dipole power), no state
    context.py     what every generator shares: sample rate, medium, gravity, slow controls, per-name seeding
    generators.py  stateful, chunk-exact generators: turbulence, particulate_impacts, modal_field
    schema.py      the preset's validator (unknown keys and out-of-range values are errors)

The medium (phys_core/medium.py) owns c, rho, absorption and viscosity; a generator reads them from the context, never from
a constant. Nothing here knows a place or an animal by name.
"""
VERSION = '0.1.0'
SCHEMA_ID = 'biome/1'
