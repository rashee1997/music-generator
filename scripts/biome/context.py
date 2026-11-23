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

"""context.py - what every generator of one biome shares.

    seed_of(seed, name)   a generator's own random stream, from its NAME, so adding or reordering another generator
                          never changes its samples (the layer engine shared one generator and could not promise that)
    Controls              named slow curves ({"curve": [[s, v], ...]} or {"ou": {"mean", "sigma", "tau_s"}}) that rates,
                          flows and gains cite as {"control": name}; evaluated at any time, in any order
    Context               sample rate, the medium, gravity, the controls and the seed
"""
import zlib

import numpy as np

from biome import physics

CONTROL_RATE_HZ = 10.0              # an OU control is built at this rate and interpolated
CONTROL_KEYS = ('curve', 'ou', 'unit')
OU_KEYS = ('mean', 'sigma', 'tau_s')


def seed_of(seed, name):
    """A 32-bit seed from (piece seed, generator name): stable across runs, platforms and the other generators."""
    return int(np.random.SeedSequence([int(seed) & 0xFFFFFFFF, zlib.crc32(str(name).encode('utf-8'))]).generate_state(1)[0])


def rng_of(seed, name):
    return np.random.default_rng(seed_of(seed, name))


def control_problems(controls, where='controls'):
    out = []
    if controls is None:
        return out
    if not isinstance(controls, dict):
        return [f'{where}: an object of named controls']
    for name, c in controls.items():
        if not isinstance(c, dict):
            out.append(f'{where}.{name}: an object with "curve" or "ou"')
            continue
        out += [f'{where}.{name}: unknown key "{k}" (known: {", ".join(CONTROL_KEYS)})' for k in c if k not in CONTROL_KEYS]
        if ('curve' in c) == ('ou' in c):
            out.append(f'{where}.{name}: give exactly one of "curve" or "ou"')
        if 'curve' in c:
            cv = c['curve']
            ok = (isinstance(cv, list) and len(cv) >= 2 and all(isinstance(p, (list, tuple)) and len(p) == 2
                                                                and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in p) for p in cv)
                  and all(cv[i][0] < cv[i + 1][0] for i in range(len(cv) - 1)))
            if not ok:
                out.append(f'{where}.{name}.curve: [[seconds, value], ...] with rising seconds, at least two points')
        if 'ou' in c:
            ou = c['ou']
            if not isinstance(ou, dict) or any(k not in OU_KEYS for k in ou) or not all(isinstance(ou.get(k), (int, float)) for k in ('sigma', 'tau_s')):
                out.append(f'{where}.{name}.ou: {{"sigma", "tau_s", optional "mean"}} numbers')
            elif ou['tau_s'] <= 0 or ou['sigma'] < 0:
                out.append(f'{where}.{name}.ou: tau_s > 0 and sigma >= 0')
    return out


class Controls:
    """Named slow curves. `value(ref, t)` takes a number or {"control": name} and a time (s) or array of times."""

    def __init__(self, cfg=None, seed=0):
        bad = control_problems(cfg)
        if bad:
            raise ValueError('; '.join(bad))
        self.cfg = dict(cfg or {})
        self.seed = int(seed)
        self._ou = {}

    def names(self):
        return sorted(self.cfg)

    def has(self, name):
        return name in self.cfg

    def _ou_values(self, name, upto_s):
        c = self.cfg[name]['ou']
        need = int(upto_s * CONTROL_RATE_HZ) + 3
        have = self._ou.get(name)
        if have is not None and len(have) >= need:
            return have
        # the series is rebuilt from its start every time it must grow, so it is the same series whatever order and
        # in whatever pieces it was asked for
        n = max(need, 2 * len(have) if have is not None else need)
        rng = rng_of(self.seed, 'control:' + name)
        a = float(np.exp(-1.0 / (CONTROL_RATE_HZ * float(c['tau_s']))))
        w = rng.standard_normal(n)
        x = np.empty(n)
        x[0] = w[0]
        for i in range(1, n):
            x[i] = a * x[i - 1] + np.sqrt(1.0 - a * a) * w[i]
        out = float(c.get('mean', 0.0)) + float(c['sigma']) * x
        self._ou[name] = out
        return out

    def curve(self, name, t):
        c = self.cfg[name]
        t = np.asarray(t, dtype=float)
        if 'curve' in c:
            pts = np.asarray(c['curve'], dtype=float)
            return np.interp(t, pts[:, 0], pts[:, 1])
        vals = self._ou_values(name, float(np.max(t)) if t.size else 0.0)
        return np.interp(t, np.arange(len(vals)) / CONTROL_RATE_HZ, vals)

    def value(self, ref, t):
        """A plain number stays a number (broadcast to t); {"control": name} is the curve at t."""
        if isinstance(ref, dict):
            name = ref.get('control')
            if name not in self.cfg:
                raise ValueError(f'control "{name}" is not defined (known: {", ".join(self.names()) or "none"})')
            return self.curve(name, t)
        return np.full(np.shape(t), float(ref)) if np.ndim(t) else float(ref)


class Context:
    def __init__(self, sr=44100, medium=None, g=physics.G_EARTH, controls=None, seed=0, full_scale_pa=2.0, materials=None):
        from phys_core import medium as _medium
        self.sr = int(sr)
        self.medium = medium if medium is not None else _medium.active()
        self.g = float(g)
        self.seed = int(seed)
        self.controls = controls if isinstance(controls, Controls) else Controls(controls, seed)
        self.full_scale_pa = float(full_scale_pa)
        self.materials = dict(materials or {})           # the preset's own materials, over phys_core.materials.PRESETS
        self.block = self.sr // 10                       # 0.1 s: the unit every generator draws its randomness in

    def rng(self, name):
        return rng_of(self.seed, name)
