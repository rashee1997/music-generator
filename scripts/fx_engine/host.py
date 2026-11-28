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

"""host.py - the two doors to Pedalboard itself: any built-in plugin on an allow-list, and a real VST3 / Audio Unit on disk.

Pedalboard cannot run a plugin written in Python (its `Plugin` is an abstract C++ class), so an effect of this repository is a
function in this package, and the effects Pedalboard already has are used through here, in the same chain."""
import numpy as np

from . import core


def allowed():
    from . import spec
    return list(spec.library()['effects']['pedalboard']['params']['plugin']['choices'])


def build_pedalboard(plugin, params):
    """The Pedalboard built-in `plugin` constructed with `params`. A name off the allow-list or an argument the plugin rejects
    raises (ValueError / TypeError), so a bad chain is found when it is checked and not in the middle of a render."""
    import pedalboard as pb
    if plugin not in allowed():
        raise ValueError(f'{plugin!r} is not on the allow-list {allowed()}')
    return getattr(pb, plugin)(**(params or {}))


def _run(plugin, x, sr):
    y = np.ascontiguousarray(plugin(np.ascontiguousarray(x.T), sr).T, dtype=np.float32)
    if len(y) >= len(x):
        return y[:len(x)]
    return np.concatenate([y, np.zeros((len(x) - len(y), y.shape[1]), np.float32)])


def pedalboard(x, sr, p, rng):
    """A built-in Pedalboard plugin over the range."""
    return _run(build_pedalboard(p['plugin'], p['params']), core.stereo(x), sr)


def external(x, sr, p, rng):
    """A VST3 or Audio Unit plugin loaded from `path`, its parameters set by name. Needs the plugin file on this machine."""
    import pedalboard as pb
    plugin = pb.load_plugin(str(p['path']))
    known = list(getattr(plugin, 'parameters', {}) or {})
    for key, value in (p['params'] or {}).items():
        if key not in known:
            raise ValueError(f'{p["path"]}: no parameter {key!r}. It has: {known}')
        setattr(plugin, key, value)
    return _run(plugin, core.stereo(x), sr)
