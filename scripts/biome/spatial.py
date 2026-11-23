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

"""spatial.py - a biome on a bus that places sources itself (ambisonic, loudspeaker layouts, ADM objects).

The stereo hand-over (biome/engine.py) folds every source to two channels, which is the right thing for a stereo mix and the
wrong thing for a 3-D one: a bed is then one pair of sources and an animal has lost its azimuth and elevation. For an
immersive mix the mixer's bus hand-over asks this module instead. An environment track written as a biome is REGISTERED when
render_natural renders it (what preset, seed, span and piece it came from); when the mixer is about to give the track to a bus
that places sources, `bus_sources` renders the biome again as its separate emitters and animals and hands those over, each at
its own azimuth, elevation, distance and trajectory:

    a `field` generator   `spatial_coupling.field.emitters` independent emitters (12 unless the preset says), a ring round the
                          listener, each from its own named random stream, so they are uncorrelated by construction
    a point generator     one source at its `spatial` place (with its trajectory)
    an animal             one source at its `position` (with its trajectory); an animal in another medium arrives already
                          reduced by the interface loss

The track's level in the mix is kept: the mixer's chain gain on the stereo stem (its rms after the chain over its rms before,
with the track's own distance taken back out) is applied to the emitters, whose total power equals the stereo stem's. The
second render costs as much as the first; the mixer holds every stem in memory already, and so does the bus.
"""
import numpy as np

REGISTRY = {}
FADE_S = 0.02                       # the end ramp render_natural puts on a bed that covers only part of the piece


def clear():
    REGISTRY.clear()


def register(track, preset, seed, sr, t0_s, span_s, score):
    """Remember what rendered the stereo stem of an environment track, so a placing bus can render its emitters instead."""
    REGISTRY[str(track)] = dict(preset=preset, seed=int(seed), sr=int(sr), t0=float(t0_s), span=float(span_s), score=score)


def is_registered(track):
    return str(track) in REGISTRY


def _rms(x):
    x = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


def bus_sources(name, placed, stem, spec, sr=None):
    """[(source name, mono float32 of the track's length, spec)] for the track `name`, or None when it is not a registered biome.

    `placed` is the track after the mixer's chain and placement (what would have been handed to the bus), `stem` the stereo stem
    before it, `spec` the track's mixer spec."""
    rec = REGISTRY.get(str(name))
    if rec is None or stem is None:
        return None
    rs, rp = _rms(stem), _rms(placed)
    if rs <= 0.0 or rp <= 0.0:
        return None
    from biome import engine
    from mix_engine.dsp_utils import place_of
    sr = int(sr or rec['sr'])
    n = len(placed)
    track_distance = max(float(place_of(spec)[2]), 1.0)          # the chain/placement divided the stem by this; the emitters carry their own
    gain = rp / rs * track_distance
    b = engine.Biome(rec['preset'], sr=sr, seed=rec['seed'], score=rec['score'], t0_s=rec['t0'], hoa=True)
    parts = b.render_emitters(rec['span'])
    places = b.emitter_specs()
    room = (((rec['preset'].get('spatial_coupling') or {}).get('room')) or {}).get('space')
    i0 = int(rec['t0'] * sr)
    out = []
    for ename, mono in parts.items():
        full = np.zeros(n, np.float32)
        seg = mono[:max(0, n - i0)] * np.float32(gain)
        k = int(min(FADE_S, len(seg) / sr / 4.0) * sr)
        if k > 1:
            ramp = np.sin(np.linspace(0.0, np.pi / 2.0, k)) ** 2
            seg = seg.copy()
            seg[:k] *= ramp
            seg[-k:] *= ramp[::-1]
        full[i0:i0 + len(seg)] = seg
        pl = places[ename]
        sp = {k_: pl[k_] for k_ in ('azimuth', 'elevation', 'distance', 'trajectory', 'binaural') if pl.get(k_) is not None}
        if room:
            sp['space'] = room
        out.append((f'{name}/{ename}', full, dict(spec, spatial=sp)))
    return out
