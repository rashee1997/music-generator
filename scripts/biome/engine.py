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

"""engine.py - a biome preset becomes sound, chunk by chunk.

    b = Biome(preset, sr=44100, seed=42)
    for chunk in b.stream(600.0, chunk_s=5.0):      # (n, 2) float32, never more than one chunk in memory
        ...
    audio = b.render(30.0)                           # the same samples, all at once

Every source (a generator or an animal) is stateful and chunk-exact (see generators.py), so the render does not depend on
the chunk size and a ten-minute piece needs the memory of one chunk, not of ten minutes (the layer engine drew
`rng.standard_normal(n)` in float64 for the whole piece: 212 MB for one layer of ten minutes). There is no loop and no
cross-fade, so there is no seam.

Placement here is the stereo hand-over (environment.render_environment_preset returns a stereo bed): a point source is
spread by 1/r, filtered by the listener medium's absorption over its distance, crossed through the interface when it
lives in another medium (T = 4 Z1 Z2 / (Z1 + Z2)^2), and panned by azimuth; a `field` source is several independent emitters spread
across the image. Elevation, trajectories and the ambisonic bus are the spatial engine's business (biome/spatial.py).

Every source is delayed by the same LATENCY (the group delay of its absorption filter), absorbed here by priming, so the
output is aligned with the sources.
"""
import math

import numpy as np
from scipy import signal

from biome import SCHEMA_ID, ecology, fauna as fauna_mod, generators, schema
from biome.context import Context
from phys_core import medium as medium_mod

LATENCY = medium_mod.TAPS // 2
PLACE_KEYS = ('azimuth', 'elevation', 'distance', 'field', 'emitters', 'trajectory', 'binaural')


class StreamFIR:
    """A linear-phase filter applied chunk by chunk with the tail carried (overlap-add)."""

    def __init__(self, ir):
        self.ir = np.asarray(ir, dtype=np.float64)
        self.carry = np.zeros(len(self.ir) - 1)

    def process(self, x):
        n = len(x)
        y = signal.fftconvolve(x, self.ir)
        y[:len(self.carry)] += self.carry
        self.carry = y[n:].copy()
        return y[:n]


def pan_gains(azimuth_deg):
    """Constant-power stereo gains (left, right) for an azimuth in degrees (0 front, +90 right)."""
    p = float(np.clip(math.sin(math.radians(float(azimuth_deg))), -1.0, 1.0))
    ang = (p + 1.0) * (math.pi / 4.0)
    return math.cos(ang), math.sin(ang)


class Source:
    """One generator or animal with its path to the listener. A `field` source is `emitters` independent copies of its generator
    (each seeded by its own name, so they are uncorrelated by construction, like drops landing all around the listener), each
    carrying 1/sqrt(emitters) of the amplitude and placed across the image; a point source is one."""

    def __init__(self, gens, place, listener, src_medium, sr, gain_db=0.0):
        self.gens = list(gens)
        self.gen = self.gens[0]
        self.place = dict(place)
        self.name = self.gen.name.split('/e')[0] if len(self.gens) > 1 else self.gen.name
        d = max(float(self.place.get('distance', 1.0)), 0.1)
        self.distance = d
        self.field = bool(self.place.get('field', False))
        self.az = float(self.place.get('azimuth', 0.0))
        self.el = float(self.place.get('elevation', 0.0))
        iface = 0.0 if src_medium is listener else src_medium.transmission_db(listener)
        self.interface_db = iface
        n = len(self.gens)
        self.base_gain = 10.0 ** ((float(gain_db) + iface) / 20.0) / math.sqrt(n)      # trim, interface, shared power: no spreading
        self.gain = self.base_gain / d
        self.fir = [StreamFIR(listener.fir(max(d - 1.0, 0.0), sr)) for _ in self.gens]
        azs = [self.az] if n == 1 else list(np.linspace(-90.0, 90.0, n))      # a field spreads its emitters across the image
        self.pan = [pan_gains(a) for a in azs]

    def emitter_places(self):
        """The place of each emitter for a loudspeaker or ambisonic bus: a field's emitters are spread evenly round the listener from
        `azimuth` (a ring, 360/N apart), at `elevations` (cycled) or `elevation`; a point source keeps its own place and trajectory."""
        n = len(self.gens)
        base = dict(distance=self.distance)
        if not self.field:
            return [dict(self.place, azimuth=self.az, elevation=self.el, distance=self.distance)]
        els = list(self.place.get('elevations') or [self.el])
        return [dict(base, azimuth=(self.az + 360.0 * i / n + 180.0) % 360.0 - 180.0, elevation=float(els[i % len(els)])) for i in range(n)]

    def emit(self, n):
        """The next n samples of each emitter, one mono float64 array each, as the bus wants them: in units of pressure at 1 m with the
        trim, the interface and the shared power applied and the 1/r spreading done (the bus adds its own air absorption and room)."""
        g = self.base_gain / max(self.distance, 1.0)
        return [gen.process(n).astype(np.float64) * g for gen in self.gens]

    def emitter_names(self):
        return [g.name for g in self.gens]

    def render(self, n):
        out = np.zeros((n, 2))
        for gen, fir, (gl, gr) in zip(self.gens, self.fir, self.pan):
            y = fir.process(gen.process(n).astype(np.float64) * self.gain)
            out[:, 0] += y * gl
            out[:, 1] += y * gr
        return out


class Biome:
    def __init__(self, preset, sr=44100, seed=42, scheduler=None, score=None, direction=None, t0_s=0.0, hoa=False):
        bad = schema.problems(preset)
        if bad:
            raise ValueError(f'biome "{(preset or {}).get("name")}": ' + '; '.join(bad))
        self.preset, self.sr, self.seed = preset, int(sr), int(seed)
        media_cfg = preset['media'] if 'media' in preset else {'air': preset['medium']}
        self.media = {n: medium_mod.Medium(dict(c, name=c.get('name', n))) for n, c in media_cfg.items()}
        world = preset.get('world') or {}
        self.listener_name = (world.get('listener') or {}).get('medium') or ('air' if 'air' in self.media else sorted(self.media)[0])
        self.listener = self.media[self.listener_name]
        ref = preset.get('reference') or {}
        self.full_scale_pa = float(ref.get('full_scale_pa', 2.0))
        base = Context(sr=self.sr, medium=self.listener, g=float(world.get('g_m_s2', 9.81)), controls=preset.get('controls'),
                       seed=self.seed, full_scale_pa=self.full_scale_pa, materials=preset.get('materials'))
        self.base = base
        self.sources = []
        for g in preset.get('generators') or []:
            place = g.get('spatial') or {}
            coupled = int((((preset.get('spatial_coupling') or {}).get('field')) or {}).get('emitters', 12))
            n = int(place.get('emitters', coupled if hoa else 2)) if place.get('field') else 1
            gens = [generators.build(g if n == 1 else dict(g, name=f'{g["name"]}/e{i}'), self._ctx(g)) for i in range(n)]
            self._add(gens, place, g, g.get('medium'))
        for f in preset.get('fauna') or []:
            self._add([fauna_mod.build(f, self._ctx(f), scheduler)], f.get('position') or {}, f, f.get('medium'))
        self.fauna = [s.gen for s in self.sources if isinstance(s.gen, fauna_mod.Fauna)]
        self.planner, self.occupancy = None, None
        eco = preset.get('ecology')
        if eco is not None and self.fauna:
            if scheduler is not None:
                raise ValueError('give either a scheduler or an ecology block, not both: both decide when an animal calls')
            sections, hits = ecology.section_times(score, direction)
            sc = eco.get('score') or {}
            if score and sc.get('occupancy', 'from_score') == 'from_score':
                self.occupancy = ecology.Occupancy.from_score(score, direction, protect_roles=sc.get('protect_roles', ecology.FIGURE),
                                                              margin_db=float(sc.get('margin_db', 3.0)))
            self.planner = ecology.Planner(self.fauna, eco, self.base.controls, self.occupancy, sections, hits, t0_s)
            for f in self.fauna:
                f.scheduler = self.planner
        self._primed = False
        self.position = 0
        self._pulled = 0

    def _ctx(self, cfg):
        m = self.media[cfg['medium']] if cfg.get('medium') else self.listener
        return self.base.with_medium(m) if m is not self.base.medium else self.base

    def _add(self, gens, place, cfg, medium_name):
        src_m = self.media[medium_name] if medium_name else self.listener
        self.sources.append(Source(gens, place, self.listener, src_m, self.sr, cfg.get('gain_db', 0.0)))

    def source(self, name):
        return next(s for s in self.sources if s.name == name)

    def step_parts(self, n):
        """The next n samples of every source, {name: (n, 2) float64 in pascals at the listener}. `process` is their sum."""
        if not self._primed:
            self._advance(LATENCY)                    # the absorption filters delay by LATENCY samples: let that pass first
            self._primed = True
        self.position += int(n)
        return self._advance(int(n))

    def step_emitters(self, n):
        """The next n samples of every emitter for a bus that places sources itself: {emitter name: (n,) float64 pressure at 1 m / full
        scale, spread by 1/r}. There is no absorption filter in this path, so no latency to prime. Do not mix it with `process`."""
        n = int(n)
        self._pulled += n
        if self.planner is not None:
            self.planner.plan_until(self._pulled / self.sr + 0.25)
        out = {}
        for s in self.sources:
            for name, y in zip(s.emitter_names(), s.emit(n)):
                out[name] = y / self.full_scale_pa
        return out

    def emitter_specs(self):
        """{emitter name: place} for step_emitters, in the order the sources were built."""
        out = {}
        for s in self.sources:
            for name, place in zip(s.emitter_names(), s.emitter_places()):
                out[name] = place
        return out

    def render_emitters(self, seconds, chunk_s=5.0):
        """Every emitter for `seconds` as mono float32, {name: (n,)}. Memory is sources x duration: the buses that need it hold
        every stem in memory already."""
        total = int(round(float(seconds) * self.sr))
        step = max(1, int(round(float(chunk_s) * self.sr)))
        parts, done = {}, 0
        while done < total:
            m = min(step, total - done)
            for k, v in self.step_emitters(m).items():
                parts.setdefault(k, []).append(v.astype(np.float32))
            done += m
        return {k: np.concatenate(v) for k, v in parts.items()}

    def _advance(self, n):
        self._pulled += int(n)
        if self.planner is not None:                   # decide every call that can sound in this chunk (and the block after it)
            self.planner.plan_until(self._pulled / self.sr + 0.25)
        return {s.name: s.render(n) for s in self.sources}

    def process(self, n):
        """The next n samples, (n, 2) float32, in units of the reference full scale (Pa / full_scale_pa)."""
        parts = self.step_parts(n)
        out = np.zeros((int(n), 2))
        for y in parts.values():
            out += y
        return (out / self.full_scale_pa).astype(np.float32)

    def stream(self, seconds, chunk_s=5.0):
        total = int(round(float(seconds) * self.sr))
        step = max(1, int(round(float(chunk_s) * self.sr)))
        done = 0
        while done < total:
            n = min(step, total - done)
            yield self.process(n)
            done += n

    def render(self, seconds, chunk_s=5.0):
        parts = list(self.stream(seconds, chunk_s))
        return np.concatenate(parts) if parts else np.zeros((0, 2), np.float32)

    def ecology_report(self):
        """The plan of the calls and the rules that shaped it ({} when the preset has no ecology)."""
        return self.planner.report() if self.planner else {}

    def report(self):
        """What was built, for the gate rows and the report: one dict per source."""
        return [dict(name=s.name, kind=getattr(s.gen, 'kind', ''), distance_m=s.distance, azimuth=s.az, elevation=s.el,
                     field=s.field, emitters=len(s.gens), interface_db=s.interface_db, medium=s.gen.med.name) for s in self.sources]


def render_preset(cfg, duration_s=30.0, sr=44100, seed=42, score=None, direction=None, t0_s=0.0):
    """Stereo float32 for a `biome/1` preset: the hand-over environment.render_environment_preset uses. `score` and `direction`
    let its ecology read the piece (pockets, sections, hits); `t0_s` is where this bed starts in the piece."""
    return Biome(cfg, sr=sr, seed=seed, score=score, direction=direction, t0_s=t0_s).render(duration_s)


def is_biome(cfg):
    return isinstance(cfg, dict) and cfg.get('schema') == SCHEMA_ID
