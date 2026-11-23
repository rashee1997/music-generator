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
lives in another medium (T = 4 Z1 Z2 / (Z1 + Z2)^2), and panned by azimuth; a `field` source is decorrelated into a wide
bed. Elevation, trajectories and the ambisonic bus are the spatial engine's business (biome/spatial.py).

Every source is delayed by the same LATENCY (the group delay of its absorption filter), absorbed here by priming, so the
output is aligned with the sources.
"""
import math

import numpy as np
from scipy import signal

from biome import SCHEMA_ID, fauna as fauna_mod, generators, schema
from biome.context import Context
from phys_core import medium as medium_mod

LATENCY = medium_mod.TAPS // 2
PLACE_KEYS = ('azimuth', 'elevation', 'distance', 'field', 'trajectory', 'binaural')


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


class StreamDecorrelator:
    """Mono to two weakly correlated channels with a cascade of random-radius allpass sections on an ERB scale (the magnitude
    is untouched, so the mono fold stays close in level). Same construction as environment.decorrelate, but stateful."""

    def __init__(self, rng, sr, stages=24, r_hi=0.985):
        import auditory
        centres = auditory.erb_centres(100.0, min(16000.0, 0.45 * sr), stages)
        self.sos, self.zi = [], []
        for _ in (0, 1):
            rows = []
            for fc in centres:
                w = 2 * np.pi * float(fc) * rng.uniform(0.9, 1.1) / sr
                rad = float(rng.uniform(r_hi - 0.085, r_hi))
                c = -2.0 * rad * np.cos(w)
                rows.append([rad * rad, c, 1.0, 1.0, c, rad * rad])
            sos = np.array(rows)
            self.sos.append(sos)
            self.zi.append(np.zeros((len(rows), 2)))

    def process(self, x):
        out = np.empty((len(x), 2))
        for ch in (0, 1):
            out[:, ch], self.zi[ch] = signal.sosfilt(self.sos[ch], x, zi=self.zi[ch])
        return out


def pan_gains(azimuth_deg):
    """Constant-power stereo gains (left, right) for an azimuth in degrees (0 front, +90 right)."""
    p = float(np.clip(math.sin(math.radians(float(azimuth_deg))), -1.0, 1.0))
    ang = (p + 1.0) * (math.pi / 4.0)
    return math.cos(ang), math.sin(ang)


class Source:
    """One generator or animal with its path to the listener."""

    def __init__(self, gen, place, listener, src_medium, sr, rng, gain_db=0.0):
        self.gen, self.place = gen, dict(place)
        self.name = gen.name
        d = max(float(self.place.get('distance', 1.0)), 0.1)
        self.distance = d
        self.field = bool(self.place.get('field', False))
        self.az = float(self.place.get('azimuth', 0.0))
        self.el = float(self.place.get('elevation', 0.0))
        iface = 0.0 if src_medium is listener else src_medium.transmission_db(listener)
        self.interface_db = iface
        self.gain = 10.0 ** ((float(gain_db) + iface) / 20.0) / d
        self.fir = StreamFIR(listener.fir(max(d - 1.0, 0.0), sr))
        self.dec = StreamDecorrelator(rng, sr) if self.field else None
        self.pan = pan_gains(self.az)

    def render(self, n):
        x = self.gen.process(n).astype(np.float64) * self.gain
        y = self.fir.process(x)
        if self.field:
            return self.dec.process(y) * math.sqrt(0.5)             # two channels share the power one point source would have
        return np.stack([y * self.pan[0], y * self.pan[1]], axis=1)


class Biome:
    def __init__(self, preset, sr=44100, seed=42, scheduler=None):
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
            self._add(generators.build(g, self._ctx(g)), g.get('spatial') or {}, g, g.get('medium'))
        for f in preset.get('fauna') or []:
            self._add(fauna_mod.build(f, self._ctx(f), scheduler), f.get('position') or {}, f, f.get('medium'))
        self._primed = False
        self.position = 0

    def _ctx(self, cfg):
        m = self.media[cfg['medium']] if cfg.get('medium') else self.listener
        return self.base.with_medium(m) if m is not self.base.medium else self.base

    def _add(self, gen, place, cfg, medium_name):
        src_m = self.media[medium_name] if medium_name else self.listener
        self.sources.append(Source(gen, place, self.listener, src_m, self.sr, self.base.rng(cfg['name'] + '/place'), cfg.get('gain_db', 0.0)))

    def source(self, name):
        return next(s for s in self.sources if s.name == name)

    def _step(self, n):
        out = np.zeros((n, 2))
        for s in self.sources:
            out += s.render(n)
        return (out / self.full_scale_pa).astype(np.float32)

    def process(self, n):
        """The next n samples, (n, 2) float32, in units of the reference full scale (Pa / full_scale_pa)."""
        if not self._primed:
            self._step(LATENCY)                       # the absorption filters delay by LATENCY samples: let that pass first
            self._primed = True
        self.position += int(n)
        return self._step(int(n))

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

    def report(self):
        """What was built, for the gate rows and the report: one dict per source."""
        return [dict(name=s.name, kind=getattr(s.gen, 'kind', ''), distance_m=s.distance, azimuth=s.az, elevation=s.el,
                     field=s.field, interface_db=s.interface_db, medium=s.gen.med.name) for s in self.sources]


def render_preset(cfg, duration_s=30.0, sr=44100, seed=42):
    """Stereo float32 for a `biome/1` preset: the hand-over environment.render_environment_preset uses."""
    return Biome(cfg, sr=sr, seed=seed).render(duration_s)


def is_biome(cfg):
    return isinstance(cfg, dict) and cfg.get('schema') == SCHEMA_ID
