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

"""timefx.py - effects that move the time axis of a stem: tape stop, pitch glide, Doppler pass, wow and flutter, stutter,
spectral freeze and a grain cloud.

Each is `fn(x, sr, p, rng) -> y`: x and y are (n, 2) float32 of the same length, p the resolved parameters of the effect
(spec.py), rng a seeded numpy Generator. Outside its range an effect returns the input unchanged; the range, its raised-cosine
edges and the dry/wet mix are applied by the caller (`fx_engine.apply`).
"""
import math

import numpy as np

from . import core


def tape_stop(x, sr, p, rng):
    """Playback speed (1 - t)^curve over dur_s from start_s, level following the speed, silence after."""
    n = len(x)
    i0, _ = core.span(p, n, sr)
    y = x.copy()
    if i0 >= n - 1:
        return y
    m = max(2, int(round(float(p['dur_s']) * sr)))
    u = np.arange(m, dtype=np.float64) / m
    speed = (1.0 - u) ** float(p['curve'])
    pos = i0 + np.concatenate([[0.0], np.cumsum(speed)[:-1]])
    seg = core.read_at(x, pos) * (speed ** float(p['level_pow']))[:, None].astype(np.float32)
    k = min(m, n - i0)
    y[i0:i0 + k] = seg[:k]
    y[i0 + k:] = 0.0
    return y


def pitch_glide(x, sr, p, rng):
    """Playback speed glides by `semitones` between start_s and end_s: a dive (negative) or a riser (positive)."""
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    y = x.copy()
    if i1 - i0 < 2:
        return y
    u = np.linspace(0.0, 1.0, i1 - i0)
    speed = 2.0 ** (float(p['semitones']) * u ** float(p['curve']) / 12.0)
    pos = i0 + np.concatenate([[0.0], np.cumsum(speed)[:-1]])
    y[i0:i1] = core.read_at(x, pos)
    return y


def doppler(x, sr, p, rng):
    """A source passing the listener on a straight path. The delay is the path length over the speed of sound (read back from
    the closest approach, so the pass keeps its place in time), the level is closest / distance, and the pitch change is the
    rate of that delay: nothing here is a lookup of a "doppler" curve."""
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    y = x.copy()
    if i1 - i0 < 2:
        return y
    if p.get('c_m_s') is None:
        from phys_core import medium
        c = float(medium.speed_of_sound())
    else:
        c = float(p['c_m_s'])
    closest, v = float(p['closest_m']), float(p['speed_m_s'])
    t_pass = (i0 + i1) / 2.0 / sr if p.get('pass_s') is None else float(p['pass_s'])
    i = np.arange(i0, i1, dtype=np.float64)
    dist = np.sqrt(closest ** 2 + (v * (i / sr - t_pass)) ** 2)
    pos = i - (dist - closest) / c * sr
    y[i0:i1] = core.read_at(x, pos) * (closest / dist)[:, None].astype(np.float32)
    return y


def tape_wobble(x, sr, p, rng):
    """Wow and flutter. A delay of amplitude A and frequency f changes pitch by at most 2 pi f A, so a drift of `cents` at `f`
    needs A = (cents ln2 / 1200) / (2 pi f) seconds."""
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    y = x.copy()
    if i1 - i0 < 2:
        return y
    i = np.arange(i0, i1, dtype=np.float64)
    t = i / sr
    swing = np.zeros(len(i))
    for hz, cents in ((p['wow_hz'], p['wow_cents']), (p['flutter_hz'], p['flutter_cents'])):
        if cents > 0:
            amp = (float(cents) * math.log(2.0) / 1200.0) / (2.0 * math.pi * float(hz))
            swing += amp * np.sin(2.0 * math.pi * float(hz) * t + rng.uniform(0.0, 2.0 * math.pi))
    y[i0:i1] = core.read_at(x, i + swing * sr)
    return y


def stutter(x, sr, p, rng):
    """The first `slice_ms` of the range repeated to its end, each repeat `decay_db` quieter."""
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    y = x.copy()
    ln = max(2, int(round(float(p['slice_ms']) * sr / 1000.0)))
    if i1 - i0 < ln:
        return y
    piece = x[i0:i0 + ln].copy()
    e = max(2, min(ln // 4, int(0.002 * sr)))
    ramp = np.linspace(0.0, 1.0, e, dtype=np.float32)[:, None]
    piece[:e] *= ramp
    piece[-e:] *= ramp[::-1]
    gain = 10.0 ** (float(p['decay_db']) / 20.0)
    k = 0
    pos = i0
    while pos < i1:
        seg = piece[:min(ln, i1 - pos)] * np.float32(gain ** k)
        y[pos:pos + len(seg)] = seg
        pos += ln
        k += 1
    return y


def freeze_window(p, n, sr):
    i0, _ = core.span(p, n, sr)
    return i0, min(n, i0 + int(round(float(p['hold_s']) * sr)))


def freeze(x, sr, p, rng):
    """Spectral freeze: the magnitude spectrum around start_s, resynthesised with fresh random phases every frame."""
    n = len(x)
    i0, i1 = freeze_window(p, n, sr)
    y = x.copy()
    size = int(p['fft'])
    if i1 - i0 < size or i0 >= n:
        return y
    hop = size // 4
    win = np.hanning(size + 1)[:-1].astype(np.float64)            # periodic Hann: four overlapping frames sum to 2
    out = np.zeros((i1 - i0 + size, 2), dtype=np.float64)
    ref = x[max(0, i0 - size):min(n, i0 + size)]
    for c in range(2):
        mags = []
        for off in (-hop, 0, hop):
            a = min(max(0, i0 + off), max(0, n - size))
            frame = np.zeros(size)
            seg = x[a:a + size, c]
            frame[:len(seg)] = seg
            mags.append(np.abs(np.fft.rfft(frame * win)))
        mag = np.mean(mags, axis=0)
        n_frames = (i1 - i0) // hop + 4
        for start in range(0, n_frames, 256):
            m = min(256, n_frames - start)
            spec = mag[None, :] * np.exp(1j * rng.uniform(0.0, 2.0 * np.pi, (m, len(mag))))
            frames = np.fft.irfft(spec, size, axis=1) * win
            for f in range(m):
                a = (start + f) * hop
                out[a:a + size, c] += frames[f][:max(0, min(size, len(out) - a))]
    held = (out[:i1 - i0] / 2.0).astype(np.float32)
    y[i0:i1] = core.match_rms(held, core.rms(ref))
    return y


def grain_cloud(x, sr, p, rng):
    """Grains of the stem, each read near its own time, scattered in pitch and place, then levelled against the stem."""
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    y = x.copy()
    dur = (i1 - i0) / sr
    ln = max(8, int(round(float(p['grain_ms']) * sr / 1000.0)))
    count = int(float(p['density_hz']) * dur)
    if count < 1 or i1 - i0 < ln:
        return y
    win = np.hanning(ln)[:, None].astype(np.float32)
    cloud = np.zeros((i1 - i0 + ln, 2), dtype=np.float32)
    spread_n = float(p['pos_spread_s']) * sr
    cents = float(p['pitch_spread_cents'])
    for _ in range(count):
        at = int(rng.integers(0, max(1, i1 - i0 - ln + 1)))
        src = float(np.clip(i0 + at + rng.uniform(-spread_n, spread_n), 0, max(0, n - 1)))
        rate = 2.0 ** (rng.uniform(-cents, cents) / 1200.0)
        g = core.read_at(x, src + np.arange(ln) * rate) * win
        theta = (rng.uniform(-float(p['pan_spread']), float(p['pan_spread'])) + 1.0) * np.pi / 4.0
        cloud[at:at + ln, 0] += g[:, 0] * np.float32(math.cos(theta))
        cloud[at:at + ln, 1] += g[:, 1] * np.float32(math.sin(theta))
    cloud = cloud[:i1 - i0]
    target = core.rms(x[i0:i1]) * core.db(p['level_db'])
    y[i0:i1] = core.match_rms(cloud, target)
    return y
