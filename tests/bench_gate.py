"""Time the mix gate (and the stem gate) on the committed fixture material.

    .venv/Scripts/python.exe tests/bench_gate.py --runs 5 --out tests/fixtures/gate/timings.json

Cold and warm are reported separately: the first run in a process pays for librosa/numpy import and warm-up, the rest
show the steady cost. A before/after comparison is only printed when both files exist; no speedup is claimed otherwise.
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, HERE)

import gate_fixture as fx  # noqa: E402
import quality_gate  # noqa: E402
import stem_gate  # noqa: E402


def _stats(samples):
    return dict(median_ms=round(statistics.median(samples), 1),
                p95_ms=round(sorted(samples)[max(0, int(0.95 * len(samples)) - 1)], 1),
                min_ms=round(min(samples), 1), runs=len(samples))


def bench_mix(wav, runs=5, mode='full'):
    groups = {}
    first = None
    for i in range(runs):
        timings = {}
        t0 = time.perf_counter()
        quality_gate.run_gate(None, wav_path=wav, refresh=False, score=fx.score(), mode=mode, timings=timings)
        total = (time.perf_counter() - t0) * 1000.0
        if i == 0:
            first = round(total, 1)
        for name, ms in timings.items():
            groups.setdefault(name, []).append(ms)
        groups.setdefault('total', []).append(total)
    return dict(cold_ms=first, **{k: _stats(v) for k, v in groups.items()})


def bench_stems(stems, runs=5, workers=2):
    totals, first = [], None
    for i in range(runs):
        t0 = time.perf_counter()
        stem_gate.run_stem_gate(fx.score(), stems, sr=fx.SR, workers=workers)
        ms = (time.perf_counter() - t0) * 1000.0
        if i == 0:
            first = round(ms, 1)
        totals.append(ms)
    return dict(cold_ms=first, **_stats(totals), workers=workers)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--out', default=None)
    ap.add_argument('--before', default=None)
    a = ap.parse_args()
    stems = fx.build_stems()
    with tempfile.TemporaryDirectory(prefix='bench_gate_') as td:
        wav = os.path.join(td, 'mix.wav')
        sf.write(wav, fx.build_mix(stems), fx.SR)
        result = dict(fixture=dict(seconds=fx.DUR, sr=fx.SR, stems=sorted(stems)),
                      mix_draft=bench_mix(wav, a.runs, 'draft'),
                      mix_full=bench_mix(wav, a.runs, 'full'),
                      stem_gate=bench_stems(stems, a.runs))
    print(json.dumps(result, indent=2))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as fh:
            json.dump(result, fh, indent=2)
        print('wrote', a.out)
    if a.before and os.path.isfile(a.before):
        before = json.load(open(a.before, encoding='utf-8'))
        print('\nbefore -> after (median ms):')
        for section in ('mix_draft', 'mix_full'):
            b = before.get(section, {}).get('total', {}).get('median_ms')
            n = result[section]['total']['median_ms']
            if b and n:
                print(f'  {section}: {b} -> {n} ({100.0 * (n - b) / b:+.1f}%)')


if __name__ == '__main__':
    np.seterr(all='ignore')
    main()
