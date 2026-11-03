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

"""Shared event lists for the vocal A/B renders (old engine vs new engine)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, 'artifacts', 'vocals')

# (start s, duration s, midi, velocity)
_MELODY = [(0.0, 1.2, 62, 70), (1.2, 1.2, 65, 76), (2.4, 0.8, 64, 80), (3.2, 1.6, 62, 88),
           (5.2, 1.0, 60, 70), (6.2, 1.0, 62, 78), (7.2, 2.4, 57, 66)]


def _ev(rows, **kw):
    return [dict(t=t, dur=d, p=p, v=v, **kw) for t, d, p, v in rows]


SCENARIOS = {
    '02_isolated_hum': dict(events=[dict(t=0.0, dur=3.0, p=62, v=80)], voices=1, hum=True),
    '03_connected_hum_phrase': dict(events=_ev(_MELODY), voices=1, hum=True),
    '04_expressive_hum_phrase': dict(events=_ev(_MELODY), voices=1, hum=True, expression='melancholic'),
    '05_single_singer': dict(events=_ev(_MELODY), voices=1, hum=False),
    '06_five_hum_ensemble': dict(events=_ev(_MELODY), voices=5, hum=True),
    '07_cinematic_layers': dict(
        events=_ev(_MELODY) + _ev([(t, d, p - 12, v - 12) for t, d, p, v in _MELODY], vowel='m')
        + _ev([(t, d, p + 7, v - 20) for t, d, p, v in _MELODY], vowel='o'),
        voices=5, hum=True, expression='cinematic'),
}
