# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""The humanize engine, split by concern.

`config` holds the values and their schema; `noise`, `form`, `timemap`, `swing` and `ensemble` are the
model; `microtiming`, `dynamics` and `articulation` are the per-track stages; `drums` and `pocket` are
kit behaviour; `track` runs the stages; `report` measures what came out.

`scripts/humanize.py` is the facade: it re-exports every name from these modules so existing callers and
tests keep working. The engine never imports the facade.
"""
from . import (articulation, config, coupling, drums, dynamics, ensemble, form, microtiming, noise, pocket,
               report, swing, timemap, track)

__all__ = ['articulation', 'config', 'coupling', 'drums', 'dynamics', 'ensemble', 'form', 'microtiming',
           'noise', 'pocket', 'report', 'swing', 'timemap', 'track']
