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

"""Singer identity: a deterministic set of config overrides per singer (seed + index), so a choir is made of
different people, not one voice copied. The variation table is data (defaults.json `singer_variation`);
`diversity` scales it (0 = identical singers). `ensemble.singers` entries (explicit overrides) win last."""
import copy

import numpy as np

from . import data


def _get(d, path):
    for k in path.split('.'):
        d = d[k]
    return d


def _set(d, path, v):
    ks = path.split('.')
    for k in ks[:-1]:
        d = d[k]
    d[ks[-1]] = v


def make_singer(cfg, index, seed, diversity=None):
    """Return (singer_cfg, identity) - a deep copy of cfg with this singer's variation applied, and the
    identity dict (the sampled values, for metadata/debug)."""
    div = cfg['ensemble']['diversity'] if diversity is None else diversity
    rng = np.random.default_rng([int(seed) & 0xFFFFFFFF, int(index) + 1, 7919])
    out = copy.deepcopy(cfg)
    ident = {}
    for v in cfg.get('singer_variation', []):
        lo, hi = v['range']
        u = rng.random()                                     # always draw, so adding rows never reorders others
        try:
            cur = _get(out, v['path'])
        except KeyError:
            continue
        if v['mode'] == 'mul':
            new = cur * (1.0 + div * (lo + u * (hi - lo) - 1.0))
        else:
            new = cur + div * (lo + u * (hi - lo))
        _set(out, v['path'], new)
        ident[v['path']] = new
    singers = cfg['ensemble'].get('singers') or []
    if singers:
        out = data.deep_merge(out, singers[index % len(singers)])
        ident['explicit'] = index % len(singers)
    out['ensemble'] = copy.deepcopy(cfg['ensemble'])
    return out, ident
