#!/usr/bin/env python3
"""bench_mix.py - how long the 3-D mix takes, and where the time goes.

    python3 scripts/helpers/bench_mix.py                       # 10 s of noise, 4 sources, the skill's own room
    python3 scripts/helpers/bench_mix.py --seconds 30 --sources 21 --profile
    python3 scripts/helpers/bench_mix.py --space cathedral --order 3

This measures `HoaBus.field()`, the mix a piece on `immersive.engine: "hoa_bus"` runs: every source encoded
into one ambisonic bus, its reflections, and the late field. `docs/mix_profile_palace.md` found this to be
64 % of a real 180 s render, with `_reflections` at 715 s of the 907 s; a change to it is measured here before
and after, per part, not believed.

`--profile` prints the cumulative profile in the same shape as that document, so a claim can be checked the
same way. Nothing here decides how anything sounds and no acoustic value lives in this file: the room comes
from a space preset.

The sources are seeded noise at distinct places, which is what an image-source tap sees: a room's taps are
delay, direction and level, none of which care what the source is made of. A real stem with a lot of silence
renders faster, because only the span it sounds in is rendered.
"""
import argparse
import cProfile
import os
import pstats
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import presets                                                # noqa: E402
from spatial_engine import hoa                                # noqa: E402

SR = 44100


def _owner(name):
    """Where the function the bench times lives: the bus method, or the module-level encoder."""
    return hoa if name == 'encode' else hoa.HoaBus


def _timed(obj, name, store):
    """Wrap a function or method so the bench can report its own time and call count."""
    fn = getattr(obj, name)

    def wrapper(*a, **k):
        t = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            store[name][0] += time.perf_counter() - t
            store[name][1] += 1
    setattr(obj, name, wrapper)
    return wrapper


def space_with_room(name=None):
    """A space preset that carries a shoebox geometry (a room whose reflections are image sources)."""
    spaces = presets.load('spaces')
    if name:
        sp = spaces.get(name)
        if not sp:
            raise SystemExit(f'unknown space "{name}": known {", ".join(sorted(spaces))}')
        if not (sp.get('reflections') or {}).get('geometry'):
            raise SystemExit(f'space "{name}" has no reflections.geometry: there are no image-source taps to time')
        return name, dict(sp, _source='bench')
    for key, sp in sorted(spaces.items()):
        if (sp.get('reflections') or {}).get('geometry'):
            # a space only counts as the piece's own room when it carries a source (mix_context.space_owned);
            # without it the bus quietly falls back to the open-air reflections and the room is never timed
            return key, dict(sp, _source='bench')
    raise SystemExit('no space preset in references/data/presets/spaces/ carries reflections.geometry')


def sources(count, seconds, seed=7):
    """`count` noise stems spread round the listener, one place each, a different length apart from the rest."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = []
    for i in range(count):
        az = -180.0 + (i + 0.5) * 360.0 / count
        out.append((f's{i}', (0.1 * rng.standard_normal((n, 1))).astype(np.float32),
                    dict(role='melody', spatial=dict(azimuth=az, elevation=0.0, distance=2.0 + 0.5 * (i % 4)))))
    return out


def run(seconds=10.0, count=4, order=5, space=None, repeat=1):
    name, sp = space_with_room(space)
    tracks = sources(count, seconds)
    n = len(tracks[0][1])
    bus = hoa.HoaBus(SR, order, 'ambix', dict(order=order), sp)
    from spatial_hrtf import room
    taps = len(room.taps((sp.get('reflections') or {}).get('geometry'), 0.0, 0.0, 2.0))
    best = None
    for _ in range(max(1, repeat)):
        b = hoa.HoaBus(SR, order, 'ambix', dict(order=order), sp)
        for nm, y, spec in tracks:
            b.add(nm, y, spec)
        store = {'_reflections': [0.0, 0], 'encode': [0.0, 0], '_late': [0.0, 0]}
        keep = [(_owner(k), k, getattr(_owner(k), k)) for k in store]
        try:
            for owner, k in [(o, k) for o, k, _ in keep]:
                _timed(owner, k, store)
            t0 = time.perf_counter()
            field, _stereo, _path = b.field()
            total = time.perf_counter() - t0
        finally:
            for owner, k, fn in keep:
                setattr(owner, k, fn)
        best = (total, store, field)
    total, store, field = best
    print(f'space {name}: {taps} image-source tap(s) per source, order {order} ({field.shape[1]} channels)')
    print(f'{count} source(s) x {seconds:g} s = {n / SR:g} s of audio')
    print(f'  field          {total:8.2f} s   {n / SR / total:5.2f}x realtime')
    for key, label in (('_reflections', 'reflections'), ('encode', '  of which encode'), ('_late', 'late field')):
        secs, calls = store[key]
        print(f'  {label:18s} {secs:8.2f} s   {100.0 * secs / max(total, 1e-9):5.1f} %   {calls} call(s)')
    print(f'  rest of field      {total - store["_reflections"][0] - store["_late"][0]:7.2f} s')
    print('  (encode is called from inside reflections: its time is already counted there)')
    return total, store


def profile(seconds, count, order, space):
    pr = cProfile.Profile()
    pr.enable()
    run(seconds, count, order, space)
    pr.disable()
    print()
    pstats.Stats(pr).sort_stats('cumulative').print_stats(14)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seconds', type=float, default=10.0, help='length of each synthetic source')
    ap.add_argument('--sources', type=int, default=4)
    ap.add_argument('--order', type=int, default=5)
    ap.add_argument('--space', default=None, help='space preset to use as the room (default: the first with a geometry)')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--profile', action='store_true', help='also print a cumulative cProfile')
    a = ap.parse_args()
    if a.profile:
        profile(a.seconds, a.sources, a.order, a.space)
    else:
        run(a.seconds, a.sources, a.order, a.space, a.repeat)


if __name__ == '__main__':
    main()
