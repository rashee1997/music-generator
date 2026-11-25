# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Benchmark of the ear model: wall time, Python-tracked peak memory (tracemalloc) and process RSS growth.

    python tests/bench_ear.py [--seconds 60] [--sr 44100] [--channels 48]

Prints one line per case and exits non-zero when a budget is missed (default 4 s per 60 s of mono audio, 200 MB of
tracked memory). The time budget is machine dependent: it is a regression guard, not a promise.
"""
import argparse
import os
import resource
import sys
import time
import tracemalloc

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

from ear_model import BinauralSummariser, EarModel, Summariser, params  # noqa: E402


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


def traced(fn):
    tracemalloc.start()
    out = fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return out, peak / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--sr', type=int, default=44100)
    ap.add_argument('--channels', type=int, default=None)
    ap.add_argument('--time-budget', type=float, default=4.0, help='seconds per 60 s of mono audio')
    ap.add_argument('--mem-budget', type=float, default=200.0, help='MB of tracked memory')
    a = ap.parse_args()
    p = params()
    if a.channels:
        p['channels'] = a.channels
    rng = np.random.default_rng(0)
    t = np.arange(int(a.sr * a.seconds)) / a.sr
    x = (0.05 * rng.standard_normal(len(t)) + 0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    y = (0.05 * rng.standard_normal(len(t))).astype(np.float32)
    scale = 60.0 / a.seconds
    bad = []

    def case(name, fn, per_minute_streams=1):
        base = rss_mb()
        _, dt = timed(fn)
        _, peak = traced(fn)
        per60 = dt * scale / per_minute_streams
        print(f'{name:<34} {dt:6.2f} s for {a.seconds:g} s  ({per60:5.2f} s per 60 s per stream)   tracked peak {peak:6.1f} MB'
              f'   RSS growth {rss_mb() - base:6.1f} MB')
        if per60 > a.time_budget:
            bad.append(f'{name}: {per60:.2f} s per 60 s over {a.time_budget:g}')
        if peak > a.mem_budget:
            bad.append(f'{name}: tracked peak {peak:.0f} MB over {a.mem_budget:g}')

    ear = EarModel(a.sr, p)
    case('stream (NAP only)', lambda: [None for _ in ear.stream(x)])
    case('summaries (fatigue, rough, pitch)', lambda: Summariser(ear).run(x))
    el, er = EarModel(a.sr, p), EarModel(a.sr, p)
    case('binaural IACC (two ears)', lambda: BinauralSummariser(el, er).run(x, y), per_minute_streams=2)
    print(f'channels {ear.n}, NAP rate {ear.nap_rate:g} Hz, chunk {ear.p["chunk_s"]} s, process RSS peak {rss_mb():.0f} MB '
          f'(includes the interpreter, numpy and scipy)')
    if bad:
        print('BUDGET MISSED: ' + '; '.join(bad))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
