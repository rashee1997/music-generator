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

"""fx_engine - cinematic and creative effects for a stem, in a Pedalboard-style chain.

    chain = [{"type": "filter_sweep", "kind": "lowpass", "f_start_hz": 200, "f_end_hz": 9000, "start_s": 24, "end_s": 32},
             {"type": "tape_stop", "start_s": 32.0, "dur_s": 0.8},
             {"type": "pedalboard", "plugin": "Chorus", "params": {"rate_hz": 0.4}}]
    y = fx_engine.apply(stem, sr, chain, seed=7)          # (n, 2) in, (n, 2) out

    board = fx_engine.Board(chain)                         # the Pedalboard call shape: (channels, samples) in and out
    y = board(audio, sr)

Pedalboard cannot host a plugin written in Python (its `Plugin` is an abstract C++ class), so each effect here is a function,
and the same chain can name any built-in Pedalboard plugin (`pedalboard`) or a real VST3 / Audio Unit file (`external`).
The library is data (`references/data/presets/fx/effects.json`); a chain lives in an instrument preset as `fx`, either written
out or as the name of a chain preset. `spec.problems(chain)` lists everything wrong with a chain before a render.

An effect has a range (`start_s` .. `end_s`, with raised-cosine edges of `edge_ms`) and a `mix`. A "ranged" effect computes its
result over the stem and is blended in only inside its range; a "timed" one (tape_stop) owns its own timing. Effects are
deterministic: the same chain, stem and seed give the same samples.
"""
import numpy as np

from . import core, host, modfx, spacefx, spec, timefx
from . import spec as spec_mod

# type -> (function, mode, window). mode "ranged": blended in inside the window from `window(p, n, sr)` (default: start_s..end_s);
# "timed": the function's output is the result (it handles its own times). The window of an effect with its own length
# (a freeze holds for hold_s; a sweep may hold after end_s) is given by that effect.
EFFECTS = {
    'tape_stop': (timefx.tape_stop, 'timed', None),
    'pitch_glide': (timefx.pitch_glide, 'ranged', None),
    'doppler': (timefx.doppler, 'ranged', None),
    'tape_wobble': (timefx.tape_wobble, 'ranged', None),
    'stutter': (timefx.stutter, 'ranged', None),
    'freeze': (timefx.freeze, 'ranged', timefx.freeze_window),
    'grain_cloud': (timefx.grain_cloud, 'ranged', None),
    'filter_sweep': (modfx.filter_sweep, 'ranged', modfx.sweep_window),
    'ring_mod': (modfx.ring_mod, 'ranged', None),
    'tremolo': (modfx.tremolo, 'ranged', None),
    'gate_pulse': (modfx.gate_pulse, 'ranged', None),
    'transient': (modfx.transient, 'ranged', None),
    'air': (modfx.air, 'ranged', None),
    'reverse_swell': (spacefx.reverse_swell, 'ranged', None),
    'shimmer': (spacefx.shimmer, 'ranged', None),
    'pedalboard': (host.pedalboard, 'ranged', None),
    'external': (host.external, 'ranged', None),
}

problems = spec.problems


def library_problems():
    """What is wrong with the effect library and its registry (empty = good)."""
    return spec.library_problems(EFFECTS)


resolve = spec.resolve
effect_names = spec.effect_names


def _seed(base, index, own):
    return (int(base) * 1000003 + index * 7919 + (int(own) if own is not None else 0)) % (2 ** 32)


def _value_at(points, frac, curve):
    """The automated value at `frac` of the range: piecewise linear through the keyframes; `exp` interpolates a from/to pair in the log domain."""
    if frac <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if frac <= t1:
            u = (frac - t0) / max(t1 - t0, 1e-9)
            if curve == 'exp' and v0 > 0 and v1 > 0:
                return v0 * (v1 / v0) ** u
            return v0 + (v1 - v0) * u
    return points[-1][1]


def _automated(fn, y, sr, p, rng):
    """An effect whose parameters move over its range: the range is cut into `steps` slices, each slice runs the effect with that
    slice's parameter values (taken at its centre), and the slices are cross-faded where they meet. Generic: it knows no effect."""
    n = len(y)
    i0, i1 = core.span(p, n, sr)
    if i1 <= i0:
        return y
    steps = max(2, int(p.get('steps') or 8))
    auto = p['automate']
    out = y.copy()
    edges = np.linspace(i0, i1, steps + 1).astype(int)
    xf = max(2, int(0.5 * (edges[1] - edges[0])))
    weight = np.zeros(n, dtype=np.float32)
    acc = np.zeros_like(y)
    for k in range(steps):
        a, b = int(edges[k]), int(edges[k + 1])
        if b <= a:
            continue
        frac = ((a + b) / 2.0 - i0) / float(i1 - i0)
        q = dict(p, start_s=a / sr, end_s=b / sr, automate=None, edge_ms=0.0)
        for key, spec_ in auto.items():
            pts = spec_mod.automation_points(spec_)
            curve = spec_.get('curve', 'linear') if isinstance(spec_, dict) else 'linear'
            q[key] = _value_at(pts, frac, curve)
        lo, hi = max(i0, a - xf), min(i1, b + xf)
        seg = fn(y, sr, dict(q, start_s=lo / sr, end_s=hi / sr), rng)
        w = core.range_mask(n, lo, hi, xf)
        acc += w[:, None] * seg
        weight += w
    inside = weight > 1e-6
    out[inside] = acc[inside] / weight[inside, None]
    return out


def apply(x, sr, chain, seed=0):
    """`x` through the chain. Returns (n, 2) float32. An empty or missing chain returns the input as float32 (n, 2). A
    non-finite result raises ValueError naming the effect that made it."""
    y = core.stereo(x)
    if not chain or len(y) == 0:
        return y
    for i, entry in enumerate(spec.resolve(chain)):
        kind, p = entry['type'], entry['params']
        fn, mode, window = EFFECTS[kind]
        rng = np.random.default_rng(_seed(seed, i, p.get('seed')))
        if p.get('automate'):
            out = _automated(fn, y, sr, p, rng)
        else:
            out = fn(y, sr, p, rng)
        if mode == 'ranged':
            n = len(y)
            i0, i1 = window(p, n, sr) if window else core.span(p, n, sr)
            mask = core.range_mask(n, i0, i1, int(round(float(p['edge_ms']) * sr / 1000.0)))
            out = y + mask[:, None] * (out - y)
        out = y + np.float32(p['mix']) * (out - y)
        if not np.isfinite(out).all():
            raise ValueError(f'fx[{i}] {kind}: produced non-finite samples (check its parameters)')
        y = np.ascontiguousarray(out, dtype=np.float32)
    return y


class Board:
    """A Pedalboard-shaped callable over a chain: `board(audio, sr)` takes and returns (channels, samples), so it can stand where
    a `pedalboard.Pedalboard` runs a stem. The chain is checked when the board is built."""

    def __init__(self, chain, seed=0):
        self.chain = spec.resolve(chain)
        self.seed = int(seed)

    def __call__(self, audio, sr, *args, **kwargs):
        a = np.asarray(audio, dtype=np.float32)
        mono = a.ndim == 1
        if mono:
            a = a[None, :]
        out = apply(a.T, sr, [dict(e['params'], type=e['type']) for e in self.chain], seed=self.seed).T
        if a.shape[0] == 1:
            out = out[:1]
        out = np.ascontiguousarray(out)
        return out[0] if mono else out


def recipes(intent=None):
    """The shipped and project recipes: {name: {"character", "intent"}}, optionally only those tagged with `intent`
    (build, release, impact, sustain, space, climax, ...). A recipe is placed with {"chain": name, "start_s": a, "end_s": b}."""
    import presets
    out = {}
    for name, p in presets.load('fx').items():
        if isinstance(p, dict) and p.get('relative') and isinstance(p.get('chain'), list):
            if intent is None or intent in (p.get('intent') or []):
                out[name] = {'character': p.get('character', ''), 'intent': list(p.get('intent') or [])}
    return out


def describe():
    """One line per effect: name, what it does and its parameters with ranges."""
    lib = spec.library()
    lines = []
    for name in sorted(lib['effects']):
        e = lib['effects'][name]
        params = ', '.join(
            f'{k}={m.get("default")!r}' + (f' [{m["min"]}..{m["max"]}{m.get("unit", "") and " " + m["unit"]}]' if 'min' in m else '')
            for k, m in (e.get('params') or {}).items())
        lines.append(f'{name:14s} {e["character"]}\n{"":14s} {params}')
    return '\n'.join(lines)
