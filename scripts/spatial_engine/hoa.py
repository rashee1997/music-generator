# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""hoa.py - one ambisonic bus for the whole piece (mix preset `immersive.engine: "hoa_bus"`).

Every source, every reflection and every late tail is written into one higher-order ambisonic sound field
(real spherical harmonics, ACN order, the vendored spaudiopy normalisation), and that field is decoded once:

  binaural   through the measured-head MagLS filters (spatial_hrtf.binaural.magls)
  speakers   through an all-round decoder (AllRAD, Zotter & Frank 2012) built on the engine's own VBAP
  ambix      the field itself, ACN / SN3D

What that buys over placing each stem with its own filter:
  * a moving source is a gain curve on the harmonics, sample by sample: no filter is ever switched;
  * a moving source keeps its room: every image source is followed along the path, with its own delay
    (so each reflection has its own Doppler shift), level and direction;
  * the late field is rendered once for the piece, not once per stem;
  * the room can change between sections (`scenes` on the space preset).

The interface is the one mixer.mix_stems expects of a bus: add(name, signal, spec), add_reverb(signal), result().
Nothing here decides anything: places come from the presets, the room from the space preset.
"""
import collections
import json
import os
import tempfile
import threading

import numpy as np

import compute
from scipy import signal

from . import trajectory

C = 343.0
ABS_FIR_TAPS = 129                      # room.absorption_fir's own length: a tap's absorption filter is never longer
IN_RAM_BYTES = 768 * 1024 * 1024       # a longer field is kept in a temporary file instead of in memory
BLOCK = 1 << 18
# Rows of the field written at a time. Measured on a 90 s source at order 5 (36 columns): 8192 rows 0.95 s per
# encoder pass, 65536 rows 0.49 s, 131072 rows 0.51 s, 262144 rows 0.93 s. The pass is memory-bound, and a block
# that small spent most of its time on the 36-column temporary; 65536 rows is about 9 MB of temporary.
ROWS = 1 << 16
# How much of one source's tap signals are held at once. Holding them turns one bus pass per tap into one pass per
# group (see encode_many); the cap keeps a long piece with many taps from trading a saved pass for an allocation.
SIGNAL_BUDGET = 256 * 1024 * 1024
SPAN_LEAD_S = 0.25                     # the air filter is zero-phase: it rings this long before a source's first sample
SPAN_PAD_S = 1.0                       # silence after a source's last sample that its reflections and air filter can still fill
SILENCE = 1e-7                         # a sample below this is no signal
STEREO_DEG = 30.0                      # where an unplaced stereo stem's two channels sit in a field with no head


def _hrtf():
    from spatial_hrtf import binaural
    return binaural


def _alloc(n, k):
    """(n, k) float32 zeros; on disk when it would not fit comfortably in memory (5 minutes at order 5 is 1.9 GB)."""
    if n * k * 4 <= IN_RAM_BYTES:
        return np.zeros((n, k), np.float32), None
    fd, path = tempfile.mkstemp(suffix='.hoa')
    os.close(fd)
    return np.memmap(path, dtype=np.float32, mode='w+', shape=(n, k)), path


def read(x, pos):
    """x at fractional sample positions (clipped to the signal): a cubic spline through the neighbouring samples,
    built block by block so a long stem does not need a spline over all of it."""
    from scipy.interpolate import CubicSpline
    n = len(x)
    pos = np.clip(np.asarray(pos, float), 0.0, n - 1.0)
    out = np.empty(len(pos))
    for a in range(0, len(pos), BLOCK):
        p = pos[a:a + BLOCK]
        lo, hi = max(0, int(p.min()) - 16), min(n, int(p.max()) + 18)
        out[a:a + BLOCK] = CubicSpline(np.arange(lo, hi), x[lo:hi])(p) if hi - lo > 3 else x[lo]
    return out


def encode(bus, s, g):
    """Add signal s to the field with harmonic gains g: (K,) for a fixed direction, (m, K) on the control grid."""
    n = min(len(s), len(bus))
    s = np.asarray(s[:n], np.float32)
    g = np.asarray(g, np.float32)
    hop = trajectory.HOP
    # Row blocks, all harmonics at once: the field is stored row by row, and writing it a column at a time walked
    # the whole array once per harmonic (most of a render's time went there).
    for a in range(0, n, ROWS):
        b = min(n, a + ROWS)
        if g.ndim == 1:
            bus[a:b] += s[a:b, None] * g[None, :]
            continue
        at = np.arange(a, b) / hop                            # linear between control points
        i = np.minimum(at.astype(np.int64), len(g) - 2)
        fr = np.clip(at - i, 0.0, 1.0).astype(np.float32)[:, None]
        bus[a:b] += s[a:b, None] * (g[i] * (1.0 - fr) + g[i + 1] * fr)


_ABS_CACHE = collections.OrderedDict()   # (surface coefficients, transform size, rate) -> absorption spectrum
_ABS_CACHE_BYTES = 192 * 1024 * 1024     # the cache's whole size. A spectrum is (size / 2 + 1) complex128 values: 64 MB for a 3 minute
                                         # source, and the size is part of the key, so a count limit let 256 of them (16 GB) pile up
_ABS_LOCK = threading.Lock()


def _group_size(count, n, budget=SIGNAL_BUDGET):
    """How many signals of `n` samples are held at once: at least one, at most `count`."""
    return max(1, min(int(count), int(budget) // max(int(n) * 4, 1)))


def _absorption_response(coeffs, size, sr):
    """The room's absorption FIR as a spectrum at `size` points, kept per (coefficients, size, rate).

    A room's taps share their coefficients: one image-source tap is two side walls, the next is a wall and the
    floor, and every source plays in the same room for the whole piece. Designing the filter and transforming it
    once per distinct surface combination is what makes a tap cost one multiply instead of a filter design.
    """
    key = (tuple(round(float(c), 9) for c in coeffs), int(size), int(sr))
    with _ABS_LOCK:
        got = _ABS_CACHE.get(key)
        if got is not None:
            _ABS_CACHE.move_to_end(key)
            return got
    from spatial_hrtf import room
    got = np.fft.rfft(room.absorption_fir(np.asarray(coeffs, float), sr=sr), int(size))
    if got.nbytes <= _ABS_CACHE_BYTES:
        with _ABS_LOCK:
            _ABS_CACHE[key] = got
            while sum(v.nbytes for v in _ABS_CACHE.values()) > _ABS_CACHE_BYTES and len(_ABS_CACHE) > 1:
                _ABS_CACHE.popitem(last=False)             # the least recently used goes first
    return got


def tap_signals(raw, taps, sr, temp_c, rh, physics=True, budget=SIGNAL_BUDGET):
    """Yield (signals (n, T) float32, the T taps) for the reflection taps of a still source, in groups.

    A tap is a delay, a direction, a distance and a material. Rendered one at a time that is a 129-tap
    `lfilter` for the absorption, a 1025-tap FFT convolution for the air and its own 36-column pass over the
    field: about 365 000 forward transforms and 300 write passes in a 180 s piece, which was 715 s of a 907 s
    mix (`docs/mix_profile_palace.md`).

    The source's spectrum is taken once. Each tap is then one multiply by its own response - the absorption
    filter (the room's own `absorption_fir`, exactly), the air absorption at that tap's path (ISO 9613-1
    applied as the gain it is, rather than through a 1025-tap approximation of it) and spherical spreading
    1/distance - and one inverse transform; the delay is the sample offset the tap's signal is written at.
    A phase ramp in the frequency domain is the same shift and costs a full complex exponential per tap,
    which was most of what was left. `size` is padded by the longest delay and the filter so nothing wraps.

    The taps come back grouped so that `encode_many` can add a group to the field in one pass: the field is
    memory-bound, so a pass per tap cost about ten times a pass per source. `budget` is how many bytes of tap
    signals a group may hold; a group is never empty, whatever the length.

    `physics` off is the room's `path_physics: false`: level and air are left out and only the delay and the
    material colour the tap, exactly as the per-tap loop did.
    """
    import airabs
    from scipy.fft import next_fast_len

    n = len(raw)
    delays = [int(round(max(0.0, float(t.get('delay_ms', 0.0))) / 1000.0 * sr)) for t in taps]
    keep = [(t, d) for t, d in zip(taps, delays) if 0 <= d < n]
    if not keep:
        return
    size = int(next_fast_len(n + max(d for _, d in keep) + ABS_FIR_TAPS, real=True))
    spec = np.fft.rfft(np.asarray(raw, dtype=np.float64), size)
    freqs = np.fft.rfftfreq(size, 1.0 / float(sr))
    group = _group_size(len(keep), n, budget)
    for start in range(0, len(keep), group):
        chunk = keep[start:start + group]
        out = np.zeros((n, len(chunk)), np.float32)
        for j, (tap, d) in enumerate(chunk):
            h = _absorption_response(tap['coeffs'], size, sr).copy()
            dist = float(tap.get('distance_m', 1.0))
            if physics:
                if dist > 1.0:
                    h *= 10.0 ** (-airabs.alpha_db_per_m(freqs, temp_c, rh) * (dist - 1.0) / 20.0)
                h /= max(dist, 1e-9)
            y = np.fft.irfft(spec * h, size)[:n]
            if d:                                  # the tap's delay is where its signal starts, not a phase ramp
                out[d:n, j] = y[:n - d]
            else:
                out[:, j] = y
        yield out, [t for t, _ in chunk]


def encode_many(bus, signals, gains):
    """Add several signals to the field in one pass: `signals` (n, T) float32, `gains` (T, K).

    bus[t, :] += sum_j signals[t, j] * gains[j, :]

    Same arithmetic as calling `encode` once per signal with a fixed direction, written as one product per row
    block so the field is read and written once instead of once per tap. That is the difference between a
    reflection pass per tap and a reflection pass per source: the field is memory-bound (or, past
    IN_RAM_BYTES, a file), so the passes are what cost.
    """
    signals = np.asarray(signals, np.float32)
    gains = np.asarray(gains, np.float32)
    n = min(len(bus), signals.shape[0])
    for a in range(0, n, ROWS):
        b = min(n, a + ROWS)
        bus[a:b] += signals[a:b] @ gains


_ALLRAD = {}


def allrad_matrix(speakers, order, points=1200):
    """The decoder of _allrad, kept per layout: building it pans 1200 virtual loudspeakers, which took longer than
    decoding a short piece."""
    key = (json.dumps(speakers, sort_keys=True, default=str), int(order), int(points))
    if key not in _ALLRAD:
        _ALLRAD[key] = _allrad(speakers, order, points)
    return _ALLRAD[key]


def probe_brir(imm, space, sr=44100, azimuth=0.0, distance=2.0, seconds=2.5, score=None):
    """The room as two ears hear it: an impulse at (azimuth, 0, distance) through the bus, decoded to headphones.
    This is what the ISO 3382-1 rows measure (a room measure is defined on an impulse response, not on music)."""
    bus = HoaBus(sr, int((imm or {}).get('order', 5)), 'binaural', imm, space, score)
    x = np.zeros((int(seconds * sr), 1), np.float32)
    x[0] = 1.0
    bus.add('probe', x, dict(role='melody', spatial=dict(azimuth=float(azimuth), elevation=0.0,
                                                         distance=float(distance))))
    return bus.result()


def _allrad(speakers, order, points=1200):
    """(speakers, K) decoder: the field is sampled by many virtual loudspeakers on a sphere and each one is panned
    onto the real layout with the engine's VBAP (All-Round Ambisonic Decoding). max-rE weights per order keep the
    side lobes down; the matrix is scaled so a plane wave keeps unit power on average."""
    from spatial_hrtf import sph
    from . import pan
    i = np.arange(points) + 0.5
    el = np.degrees(np.arcsin(1.0 - 2.0 * i / points))                 # a Fibonacci sphere: near-uniform, any size
    az = (np.degrees(i * np.pi * (3.0 - np.sqrt(5.0))) + 180.0) % 360.0 - 180.0
    names = [s['name'] for s in speakers]
    g = np.zeros((points, len(names)))
    for j in range(points):
        for name, v in pan.gains(az[j], el[j], speakers).items():
            g[j, names.index(name)] = v
    y = _hrtf().gains(order, az, el) * sph.repeat_per_order(sph.max_rE_weights(order))[None, :]
    d = 4.0 * np.pi / points * g.T @ y
    power = np.mean(np.sum((d @ _hrtf().gains(order, az, el).T) ** 2, axis=0))
    return d / np.sqrt(power)


def ambix(field):
    """The engine's field (orthonormal real harmonics) as AmbiX: ACN order, SN3D, W = the plain pressure."""
    order = int(np.sqrt(field.shape[1]) - 1)
    scale = np.concatenate([[np.sqrt(4.0 * np.pi / (2 * n + 1))] * (2 * n + 1) for n in range(order + 1)])
    return np.asarray(field, np.float32) * scale[None, :].astype(np.float32)


def _merge(base, over):
    out = dict(base or {})
    for k, v in (over or {}).items():
        out[k] = _merge(out.get(k), v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class HoaBus:
    places_tracks = True               # mixer._place leaves every placed track for this bus

    def __init__(self, sr=44100, order=5, decode='binaural', imm=None, space=None, score=None, speakers=None,
                 room_only=False):
        if decode not in ('binaural', 'speakers', 'ambix'):
            raise ValueError(f'HoaBus cannot decode to "{decode}"')
        self.sr, self.order, self.decode = int(sr), int(order), decode
        self.k = (self.order + 1) ** 2
        self.imm, self.space, self.score = imm or {}, space or {}, score or {}
        self.speakers, self.room_only = speakers, room_only
        self.sources, self.reverb = [], None

    # ------------------------------------------------------------------ what the mixer hands in
    def add(self, name, y, spec):
        y = np.asarray(y, np.float32)
        if y.size:
            self.sources.append((name, y if y.ndim == 2 else y[:, None], dict(spec or {})))

    def add_reverb(self, ret):
        if ret is not None and len(ret):
            self.reverb = np.asarray(ret, np.float32)

    # ------------------------------------------------------------------ the room, per section
    def _states(self, n):
        """[(reflections block, input window or None)]: the space's own room, then one per scene. Windows are
        raised-cosine and always sum to one, so two identical rooms crossfade to exactly the same room."""
        import mix_context
        import spatial
        # a piece with no space of its own still gets the open-air reflections, as on the per-stem engine: a source
        # with no reflection at all sits inside the head
        base = (self.space.get('reflections') if mix_context.space_owned(self.space) else None)             or spatial.ACOUSTIC_SPACES['outdoor_open']
        scenes = self.space.get('scenes') or []
        if not scenes:
            return [(base, None)]
        tm = trajectory._tempo(self.score)
        bar_s = float(tm.sec(trajectory._beats_per_bar(self.score)))
        cfgs, starts, fades = [base], [0], [0]
        for sc in sorted(scenes, key=lambda s: trajectory.seconds(s.get('anchor') or {}, self.score, tm)):
            cfgs.append(_merge(cfgs[-1], sc.get('space_overrides')))
            starts.append(int(trajectory.seconds(sc.get('anchor') or {}, self.score, tm) * self.sr))
            fade = float(sc['transition_s']) if 'transition_s' in sc else float(sc.get('transition_bars', 0.0)) * bar_s
            fades.append(max(1, int(fade * self.sr)))
        t = np.arange(n)
        rise = [np.ones(n)] + [np.sin(0.5 * np.pi * np.clip((t - a) / f, 0.0, 1.0)) ** 2
                               for a, f in zip(starts[1:], fades[1:])]
        out = []
        for i, cfg in enumerate(cfgs):
            w = rise[i] * (1.0 - rise[i + 1]) if i + 1 < len(cfgs) else rise[i]
            if np.any(w > 0):
                out.append((cfg, None if np.all(w == 1.0) else w))
        return out

    # ------------------------------------------------------------------ one source
    # ------------------------------------------------------------------ where each source is heard, and on how many cores
    def _span(self, y, spec):
        """(a, b): the samples a source can be heard in. A source that stands still is rendered over this span only: the
        direct sound, every reflection and the late-field send are time-invariant, so the part before its first
        sample and after its last (plus `SPAN_PAD_S` for the longest reflection and the air filter) is silence in,
        silence out. A moving source keeps its whole length, because its path is a function of the time of day."""
        n = len(y)
        if (spec.get('spatial') or {}).get('trajectory'):
            return 0, n
        loud = np.abs(y).max(axis=1) if y.ndim == 2 else np.abs(y)
        nz = np.flatnonzero(loud > SILENCE)
        if not nz.size:
            return 0, 0
        return int(max(0, nz[0] - SPAN_LEAD_S * self.sr)), int(min(n, nz[-1] + 1 + SPAN_PAD_S * self.sr))

    def _run(self, bus, stereo, sends, name, y, spec, states, span):
        """One source into (bus, stereo, sends), over its span."""
        a, b = span
        if b <= a:
            return
        if a == 0 and b >= len(y):
            return self._source(bus, stereo, sends, name, y, spec, states)
        local = {}
        window = [(cfg, None if w is None else w[a:b]) for cfg, w in states]
        self._source(bus[a:b], stereo[a:b], local, name, y[a:b], spec, window)
        for key, (refl, send) in local.items():
            if key not in sends:
                sends[key] = [refl, np.zeros(len(bus))]
            sends[key][1][a:b] += send

    def _workers(self, n):
        """How many sources are rendered at once: the mix preset's `render.mix_workers` ('auto' = one per core), cut so
        the partial fields (one per worker, each (n, K) float32) stay inside four times IN_RAM_BYTES."""
        import mixer
        import mix_schema
        w = mix_schema.section(mixer._mix(), 'render').get('mix_workers', 1)
        w = (os.cpu_count() or 1) if w == 'auto' else max(1, int(w))
        return int(max(1, min(w, (4 * IN_RAM_BYTES) // max(n * self.k * 4, 1))))

    def _place_all(self, bus, stereo, sends, states, n):
        spans = [self._span(y, spec) for _, y, spec in self.sources]
        workers = min(self._workers(n), len(self.sources))
        if workers <= 1:
            for (name, y, spec), span in zip(self.sources, spans):
                self._run(bus, stereo, sends, name, y, spec, states, span)
            return
        import mix_context
        from concurrent.futures import ThreadPoolExecutor
        ctx = mix_context.current()
        order = sorted(range(len(self.sources)), key=lambda i: -(spans[i][1] - spans[i][0]))
        chunks, load = [[] for _ in range(workers)], [0] * workers
        for i in order:                                    # the longest first, each onto the least loaded worker
            j = load.index(min(load))
            chunks[j].append(i)
            load[j] += spans[i][1] - spans[i][0] + 1

        def work(chunk):
            mix_context.make_current(ctx)                  # the context is per thread: this one reads the piece's own
            b = np.zeros((n, self.k), np.float32)
            st = np.zeros((n, 2))
            sd = {}
            for i in chunk:
                name, y, spec = self.sources[i]
                self._run(b, st, sd, name, y, spec, states, spans[i])
            return b, st, sd

        with ThreadPoolExecutor(max_workers=workers) as pool:
            parts = list(pool.map(work, [c for c in chunks if c]))
        for b, st, sd in parts:
            for a in range(0, n, ROWS):
                bus[a:a + ROWS] += b[a:a + ROWS]
            stereo += st
            for key, (refl, send) in sd.items():
                if key not in sends:
                    sends[key] = [refl, np.zeros(len(bus))]
                sends[key][1] += send

    def _source(self, bus, stereo, sends, name, y, spec, states):
        import airabs
        import mixer
        H = _hrtf()
        sr, n = self.sr, len(y)
        sp = spec.get('spatial')
        placed = bool(sp) and sp.get('binaural') is not False
        if not placed:                                   # a track the piece keeps out of the 3-D field
            if self.room_only:
                return
            if self.decode == 'binaural':
                stereo[:n] += y if y.shape[1] == 2 else np.repeat(y, 2, axis=1)
            else:
                for ch, az in ((0, -STEREO_DEG), (y.shape[1] - 1, STEREO_DEG)):
                    encode(bus, y[:, ch] * (0.707 if y.shape[1] == 1 else 1.0), H.gains(self.order, az, 0.0)[0])
            return
        az, el, dist = mixer.place_of(spec, self.imm)
        traj = sp.get('trajectory')
        p = trajectory.path(traj, az, el, dist, n, sr, self.score)
        if p is not None and trajectory.is_anchor(traj, spec.get('role')):
            p = trajectory.anchor(p, az, el, dist, float(self.imm.get('anchor_max_span_deg', 6.0)))
        track_space = mixer.resolve_space(sp['space']) if sp.get('space') else None
        near = ((track_space or self.space).get('distance') or {}).get('near_field')
        temp_c, rh = float(sp.get('temp_c', 20.0)), float(sp.get('rh', 50.0))
        hw = mixer.pair_half_width(y, sp, self.imm) if p is None else 0.0
        parts = ([(y[:, 0], az - hw, 0.707), (y[:, 1], az + hw, 0.707)] if hw > 0 and y.shape[1] == 2
                 else [(y.mean(axis=1), az, 1.0)])
        back = max(dist, 1.0)                            # the mixer already applied 1/r for the track's own distance
        dop = float((traj or {}).get('doppler_strength', 1.0)) if (traj or {}).get('doppler', True) else 0.0
        t = np.arange(n, dtype=float)
        for x, a0, weight in parts:
            x = np.asarray(x, float) * weight
            raw = x * back
            if p is None:
                d_s = None
                direct = airabs.apply(x, dist - 1.0, temp_c, rh, sr=sr) if dist > 1.0 else x
                g = H.gains(self.order, a0, el)[0]
            else:
                d_s = trajectory.at_samples(p, 2, 0, n)
                lead = dop * (d_s - d_s.min()) / C * sr                     # the path the sound still has to travel
                direct = (read(raw, t - lead) if dop else raw) / np.maximum(d_s, 1.0)
                f = np.fft.rfftfreq(H.DVF_BLOCK, 1.0 / sr)
                alpha = airabs.alpha_db_per_m(f, temp_c, rh)
                direct = H.stft_gain(direct, lambda k: 10.0 ** (-alpha * max(d_s[k] - 1.0, 0.0) / 20.0))
                g = H.gains(self.order, p[:, 0], p[:, 1])
            if not self.room_only:
                is_near = bool(near and near.get('enabled', True)
                               and (dist if p is None else float(p[:, 2].min())) < float(near.get('max_m', 1.0)))
                if is_near and self.decode == 'binaural':   # the two ears hear different distances: no field holds that
                    dec = H.magls(self.order)
                    if p is None:
                        ears = np.stack([compute.conv(direct, g @ dec[e])[:n] for e in (0, 1)], axis=1)
                        ears = H.apply_near_field(ears, a0, el, dist, near, sr)
                    else:
                        az_s, el_s = trajectory.at_samples(p, 0, 0, n), trajectory.at_samples(p, 1, 0, n)
                        ears = H._stft_place(direct, az_s, el_s, self.order, sr)
                        ears = H.apply_near_field(ears, az_s, el_s, d_s, near, sr)
                    stereo[:n] += ears
                else:
                    encode(bus, direct, g)
            refl_own = (track_space or {}).get('reflections') if track_space else None
            for refl, w in ([(refl_own, None)] if refl_own else states):
                if not isinstance(refl, dict):
                    continue
                feed = raw if w is None else raw * w[:n]
                self._reflections(bus, feed, refl, a0, el, dist, p, dop, temp_c, rh)
                key = id(refl)
                if key not in sends:
                    sends[key] = [refl, np.zeros(len(bus))]
                sends[key][1][:n] += feed * (0.707 if len(parts) == 2 else 1.0)   # a pair sends its mono mean

    def _reflections(self, bus, raw, refl, az, el, dist, p, dop, temp_c, rh):
        import airabs
        from spatial_hrtf import room
        H = _hrtf()
        sr, n = self.sr, len(raw)
        physics = bool(refl.get('path_physics', True))
        geom = refl.get('geometry')

        def air(s, metres):
            return airabs.apply(s, metres - 1.0, temp_c, rh, sr=sr) if physics and metres > 1.0 else s

        if geom and p is None:
            # Still source in a shoebox: every tap is delay + material + air + distance. One transform of the
            # source serves all of them, and one pass over the field adds all their directions; see tap_signals.
            for signals, group in tap_signals(raw, room.taps(geom, az, el, dist, sr=sr), sr, temp_c, rh,
                                              physics=physics):
                gains = np.stack([H.gains(self.order, t['azimuth'], t['elevation'])[0] for t in group])
                encode_many(bus, signals, gains)
        elif geom:
            direct, images = room.image_tracks(geom, p[:, 0], p[:, 1], p[:, 2], sr=sr)
            t = np.arange(n, dtype=float)
            grid = np.arange(len(direct)) * trajectory.HOP
            lead = dop * (direct - direct.min()) / C
            for im in images:
                delay = np.interp(t, grid, (lead + (im['path_m'] - direct) / C) * sr)
                s = read(raw, t - delay)
                if physics:
                    s = s / np.interp(t, grid, im['path_m'])
                s = signal.lfilter(room.absorption_fir(im['coeffs'], sr=sr), 1.0, s)
                # shortcut: one air filter per image, for its mean path. Exact per-frame air is what the direct
                # sound gets; do the same here if a reflection's brightness is ever heard to lag a long move.
                encode(bus, air(s, float(np.mean(im['path_m']))), H.gains(self.order, im['azimuth'], im['elevation']))
        else:
            a_mean = az if p is None else float(np.mean(p[:, 0]))
            d_mean = dist if p is None else float(np.mean(p[:, 2]))
            for key, grow, cutoff, direction, level in H.fixed_plan(a_mean):
                gain = float(refl.get(key + '_gain', 0.0)) * level
                d = int(float(refl.get(key + '_delay_ms', 0.0)) / 1000.0 * sr * (1.0 + grow * d_mean))
                if gain <= 0.0 or not 0 < d < n:
                    continue
                s = np.zeros(n)
                s[d:] = raw[:n - d] * gain
                extra = C * d / sr
                if physics:
                    s = s / max(d_mean + extra, 1e-6)
                s = signal.sosfilt(signal.butter(2, min(sr * 0.45, float(refl.get(key + '_cutoff_hz', cutoff))),
                                                 'low', fs=sr, output='sos'), s)
                encode(bus, air(s, d_mean + extra), H.gains(self.order, direction[0], direction[1])[0])

    def _late(self, bus, refl, send):
        """The late field of one room, once for everything that plays in it. `level_db` is the tail's power against
        the dry power of a steady broadband source; a source with more low end rings longer, as it does in a room."""
        from spatial_hrtf import room
        cfg = room.late_cfg(refl)
        if not cfg or not cfg.get('enabled', False) or len(send) < 2048:
            return
        dirs = room.directions(dict(cfg, bias_azimuth_deg=float(cfg.get('bias_azimuth_deg', 0.0))))
        level = 10.0 ** (float(cfg.get('level_db', -18.0)) / 20.0) / np.sqrt(len(dirs))
        H = _hrtf()
        # One pass over the field per group of directions, not one per direction: the tail itself is six
        # convolutions, but the field is memory-bound and adding six columns at a time costs what one did.
        group = _group_size(len(dirs), len(send))
        for start in range(0, len(dirs), group):
            part = list(range(start, min(len(dirs), start + group)))
            tails = np.zeros((len(send), len(part)), np.float32)
            gains = np.zeros((len(part), self.k), np.float32)
            for j, i in enumerate(part):
                az, el = dirs[i]
                ir = room.late_ir(dict(cfg, seed=int(cfg.get('seed', 7)) + i), self.sr).astype(float)
                tails[:, j] = compute.oaconv(send, ir)[:len(send)] * (level / np.sqrt(np.sum(ir ** 2)))
                gains[j] = H.gains(self.order, az, el)[0]
            encode_many(bus, tails, gains)

    # ------------------------------------------------------------------ the field and its decoders
    def field(self):
        """((n, K) field, (n, 2) signal that bypasses it, temp-file path or None)."""
        n = max([len(y) for _, y, _ in self.sources] + [0])
        if self.reverb is not None and not self.room_only:
            n = max(n, len(self.reverb))
        bus, path = _alloc(n, self.k)
        stereo = np.zeros((n, 2))
        sends, states = {}, self._states(n)
        self._place_all(bus, stereo, sends, states, n)
        for refl, send in sends.values():
            self._late(bus, refl, send)
        if self.reverb is not None and not self.room_only:
            ret = self.reverb if self.reverb.ndim == 2 else np.repeat(self.reverb[:, None], 2, axis=1)
            if self.decode == 'binaural':
                stereo[:len(ret)] += ret[:, :2]
            else:                                         # the shared reverb return, wide: it has no place of its own
                for ch, az in ((0, -2 * STEREO_DEG), (1, 2 * STEREO_DEG)):
                    encode(bus, ret[:, ch].astype(float), _hrtf().gains(self.order, az, 0.0)[0])
        return bus, stereo, path

    def result(self):
        bus, stereo, path = self.field()
        try:
            if self.decode == 'ambix':
                return ambix(bus)
            if self.decode == 'speakers':
                d = allrad_matrix(self.speakers, self.order).astype(np.float32)
                out = np.zeros((len(bus), len(self.speakers)), np.float32)
                for a in range(0, len(bus), BLOCK):
                    out[a:a + BLOCK] = np.asarray(bus[a:a + BLOCK]) @ d.T
                return out
            dec = _hrtf().magls(self.order)
            out = stereo
            for c in range(self.k):
                col = np.asarray(bus[:, c], float)
                if col.any():                             # a long signal, a short filter: overlap-add is the fast way
                    for e in (0, 1):
                        out[:, e] += compute.oaconv(col, dec[e, c])[:len(col)]
            return out.astype(np.float32)
        finally:
            if path:
                del bus
                try:
                    os.remove(path)
                except OSError:
                    pass
