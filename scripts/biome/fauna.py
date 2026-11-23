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

"""fauna.py - a creature that calls, as data: bouts of calls made of elements, each a source kind and a resonator.

    {"name": "tiger", "power_w": 0.01, "bouts_per_min": 0.2,
     "source":    {"kind": "glottal_chaos", "rd": 1.8, "subharmonic": 0.4, "chaos": 0.25},
     "elements":  {"roar": {"f0_hz": [[0, 120], [0.4, 150], [1, 90]], "ms": [1800, 2600]}},
     "resonator": {"kind": "tract", "segments": [[0.11, 4.0], [0.10, 9.0], [0.08, 14.0]]}}

A fauna entry may start from a `calls` preset (`"call": "owl_hoot"`): that preset's elements, sequence, gap and tube become
the defaults, with the additive source, and any key written beside it wins. Output is pressure in pascals at 1 m: the
calling animal radiates `power_w` (acoustic watts, while it calls), so the same animal is quieter in a thin atmosphere and
louder in a thick one by the medium's own impedance.

Calls are scheduled per individual in bouts. The default schedule is the one calls.py always had (mean gap from
`bouts_per_min`, 0.7-1.3 jitter); an ecology scheduler plugs in through `scheduler.next_start(...)` and decides when each
bout may begin. Synthesis and scheduling draw from streams named after the animal, the individual and the bout, so the
samples do not depend on how they were asked for or on any other generator.
"""
import numpy as np

from biome import physics, sources, tract
from biome.generators import Generator
from env_engine import calls

KEYS = ('name', 'call', 'elements', 'sequence', 'gap_ms', 'source', 'resonator', 'individuals', 'individual_spread', 'bouts_per_min',
        'power_w', 'niche', 'salience', 'medium', 'position', 'first_s', 'sources', 'note', 'rate_per_k', 'temp_ref_k')
NICHE_KEYS = ('band_hz', 'active')
POSITION_KEYS = ('azimuth', 'elevation', 'distance', 'trajectory')
LEGACY_RES = ('tract_cm', 'formants_hz', 'formant_q', 'formant_mix')
MAX_BOUT_S = 90.0


def from_call_preset(cfg):
    """The cfg with a named `calls` preset's grammar laid under the keys the entry wrote itself."""
    if not cfg.get('call'):
        return dict(cfg)
    import presets
    pre = {k: v for k, v in presets.get('calls', cfg['call']).items() if k not in calls.PRESET_ONLY}
    out = {k: v for k, v in pre.items() if k not in LEGACY_RES and k != 'rate_per_c'}
    if 'source' not in cfg:
        out['source'] = {'kind': 'additive'}
    if 'resonator' not in cfg:
        q = float(pre.get('formant_q', 6.0))
        if pre.get('tract_cm'):
            out['resonator'] = {'kind': 'tube', 'length_cm': float(pre['tract_cm']), 'q': q, 'mix': float(pre.get('formant_mix', 0.7))}
        elif pre.get('formants_hz'):
            out['resonator'] = {'kind': 'formant_bank', 'formants': [[float(f), float(f) / q, 0.0] for f in pre['formants_hz']],
                                'mix': float(pre.get('formant_mix', 0.7))}
    out.update({k: v for k, v in cfg.items() if k != 'call'})
    out['call'] = cfg['call']
    return out


class Fauna(Generator):
    kind = 'fauna'

    def __init__(self, cfg, ctx, scheduler=None):
        super().__init__(cfg, ctx)
        m = from_call_preset(cfg)
        self.scheduler = scheduler
        src = dict(m.get('source') or {'kind': 'additive'})
        self.src_kind = src.pop('kind')
        self.src_defaults = src
        self.elements = m.get('elements') or {'call': {}}
        self.sequence = m.get('sequence') or list(self.elements)
        self.gap_ms = m.get('gap_ms', (60.0, 140.0))
        self.res = m.get('resonator')
        self.n_ind = max(1, int(m.get('individuals', 1)))
        self.spread = float(m.get('individual_spread', 0.06))
        self.bouts_per_min = float(m.get('bouts_per_min', 4.0))
        if m.get('power_w') is None:
            raise ValueError(f'fauna "{self.name}": needs power_w, the acoustic power it radiates while calling (W); there is no default level')
        self.power_w = float(m['power_w'])
        self.first_s = m.get('first_s')
        self.rate_per_k = float(m.get('rate_per_k', 0.0))
        self.temp_ref = float(m.get('temp_ref_k', self.med.temperature_k))
        self.rate = max(0.1, 1.0 + self.rate_per_k * (self.med.temperature_k - self.temp_ref))
        self.mean_gap = 60.0 / max(0.05, self.bouts_per_min * self.rate)
        bad = self._problems()
        if bad:
            raise ValueError(f'fauna "{self.name}": ' + '; '.join(bad))
        self.sched = [ctx.rng(f'{self.name}/i{i}/schedule') for i in range(self.n_ind)]
        self.scale, self.level = [], []
        for i in range(self.n_ind):
            r = ctx.rng(f'{self.name}/i{i}/self')
            self.scale.append(float(np.exp(r.normal(0.0, self.spread))) if self.n_ind > 1 else 1.0)
            self.level.append(10.0 ** (-r.uniform(0.0, 9.0) / 20.0) if self.n_ind > 1 else 1.0)
        self.bout = [0] * self.n_ind
        self.next = [None] * self.n_ind
        self.active = []                      # (start sample, waveform)
        self.starts = []                      # every bout begun, (individual, start s, duration s): what the ecology rules read

    def _params(self, name):
        return {**self.src_defaults, **(self.elements[name] or {})}

    def _problems(self):
        out = []
        if self.src_kind not in sources.KINDS:
            return [f'source.kind "{self.src_kind}": use one of {", ".join(sources.KINDS)}']
        for n in self.elements:
            out += sources.problems(self.src_kind, self._params(n), f'element "{n}"')
        for item in self.sequence:
            n = item if isinstance(item, str) else (item[0] if item else None)
            if n not in self.elements:
                out.append(f'sequence names "{n}", which is not an element ({", ".join(sorted(self.elements))})')
        out += tract.problems(self.res)
        return out

    # -- one call: elements in order, then the body
    def _call(self, rng, ind):
        sr = self.sr
        scale = self.scale[ind]
        glo, ghi = calls._pair(self.gap_ms)
        parts = []
        for item in self.sequence:
            name, lo, hi = (item, 1, 1) if isinstance(item, str) else (item[0], int(item[1]), int(item[-1]))
            p = dict(self._params(name), _rate=self.rate)
            for _ in range(int(rng.integers(lo, hi + 1))):
                parts.append(sources.element(self.src_kind, p, sr, rng, scale, self.ctx))
                parts.append(np.zeros(int(rng.uniform(glo, ghi) / 1000.0 * sr)))
        y = np.concatenate(parts[:-1]) if parts else np.zeros(0)
        if len(y) and self.res:
            y = tract.apply(y, tract.design(self.res, self.med, sr, scale), sr, float(self.res.get('mix', 0.7)))
        if not len(y):
            return y
        voiced = np.abs(y) > 0.01 * np.abs(y).max()
        rms = float(np.sqrt(np.mean(y[voiced] ** 2)))
        want = physics.pressure_rms_from_power(self.med.z, self.power_w * self.level[ind] ** 2)
        return (y / max(rms, 1e-12) * want)[: int(MAX_BOUT_S * sr)]

    def _next_start(self, ind, start, dur):
        earliest = start + dur + 0.2
        if self.scheduler is not None:
            return self.scheduler.next_start(self.name, ind, earliest, dur, self.sched[ind])
        return start + max(dur + 0.2, self.mean_gap * float(self.sched[ind].uniform(0.7, 1.3)))

    def _first(self, ind):
        if self.scheduler is not None:
            return self.scheduler.next_start(self.name, ind, 0.0, 0.0, self.sched[ind])
        if self.first_s is not None and ind == 0:
            return float(self.first_s)
        return float(self.sched[ind].uniform(0.1, 1.0) * self.mean_gap)

    def _block(self):
        B, sr = self.B, self.sr
        s0 = self.index * B
        end_s = (s0 + B) / sr
        for ind in range(self.n_ind):
            if self.next[ind] is None and self.bout[ind] == 0:
                self.next[ind] = self._first(ind)
            while self.next[ind] is not None and self.next[ind] < end_s:
                t = self.next[ind]
                w = self._call(self.ctx.rng(f'{self.name}/i{ind}/b{self.bout[ind]}'), ind)
                self.active.append((int(round(t * sr)), w))
                self.starts.append((ind, t, len(w) / sr))
                self.bout[ind] += 1
                self.next[ind] = self._next_start(ind, t, len(w) / sr)
        out = np.zeros(B)
        keep = []
        for a, w in self.active:
            lo, hi = max(a, s0), min(a + len(w), s0 + B)
            if hi > lo:
                out[lo - s0:hi - s0] += w[lo - a:hi - a]
            if a + len(w) > s0 + B:
                keep.append((a, w))
        self.active = keep
        return out


def build(cfg, ctx, scheduler=None):
    return Fauna(cfg, ctx, scheduler)
