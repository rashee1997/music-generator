#!/usr/bin/env python3
"""bench_memory.py - where the mixing stage's memory goes, measured as peak RSS.

    python3 scripts/helpers/bench_memory.py lufs --seconds 120
    python3 scripts/helpers/bench_memory.py mix --stems 8 --seconds 20 --workers 2
    python3 scripts/helpers/bench_memory.py validate --seconds 60

Every case runs in its own process (`/proc/self/status` VmHWM is a high-water mark, so a second case in
one process would inherit the first one's peak). This measures the engine's own working set: what the
process holds, not what the audio "should" cost.

Cases
  lufs      mixer.active_lufs on one stereo stem: the gain-staging measurement
  mix       mixer.mix_stems on synthetic stems: the chain, the placement, the room and the master
  validate  a written master through mixer._validate_export

Nothing here decides how anything sounds and no acoustic value lives in this file: the stems are seeded
noise, and the mix preset is the shipped default with only `render.mix_workers` set by the command line.
"""
import argparse
import os
import resource
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

SR = 44100
MB = 1e6


def peak_mb():
    """(peak RSS, current RSS) in MB. VmHWM is the high-water mark for this process."""
    try:
        vals = {}
        with open('/proc/self/status', encoding='utf-8') as fh:
            for line in fh:
                if line.startswith(('VmHWM:', 'VmRSS:')):
                    vals[line.split(':')[0]] = float(line.split()[1]) / 1024.0
        return vals.get('VmHWM', 0.0), vals.get('VmRSS', 0.0)
    except OSError:
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        return r, r


def synth(seconds, channels=2, seed=7, gain=0.05):
    """Seeded noise: broadband, so every filter in the chain has something to do."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    x = (gain * rng.standard_normal((n, channels))).astype(np.float32)
    return x


def score_for(names, seconds=20.0, workers=None):
    """A score-shaped dict with one track per stem: the roles are spread over the families the mix reads."""
    roles = ('melody', 'chord', 'pad', 'bass', 'drum', 'arp', 'counter', 'texture', 'ostinato', 'drone')
    tracks = []
    for i, nm in enumerate(names):
        role = roles[i % len(roles)]
        tracks.append(dict(name=nm, role=role, instrument='flute' if role == 'melody' else 'slow_strings',
                           notes=[dict(t=0.0, d=1.0, p=60 + i)], spatial=dict(azimuth=-60.0 + 15.0 * i,
                                                                              elevation=0.0, distance=2.0)))
    sc = dict(title='bench', bpm=90.0, key='C', ts=[4, 4], tracks=tracks, space='hall',
              mix={'reverb_return': 1.0}, master={'lufs': -16.0, 'true_peak': -1.5})
    if workers is not None:
        sc['_bench_workers'] = int(workers)
    return sc


def case_lufs(seconds):
    import mixer
    x = synth(seconds)
    mixer.use_mix('default')
    print(f'stem: {seconds:g} s stereo float32 = {x.nbytes / MB:.1f} MB on disk-worth of samples')
    t0 = time.perf_counter()
    value = mixer.active_lufs(x, SR)
    dt = time.perf_counter() - t0
    print(f'active_lufs -> {value:.2f} LUFS in {dt:.2f} s')
    return value, dt


def case_mix(stems_n, seconds, workers):
    import mix_context
    import mixer
    import mix_schema
    names = [f's{i:02d}' for i in range(stems_n)]
    stems = {nm: synth(seconds, seed=100 + i) for i, nm in enumerate(names)}
    total = sum(v.nbytes for v in stems.values())
    print(f'{stems_n} stems x {seconds:g} s = {total / MB:.1f} MB of float32 audio')
    sc = score_for(names, seconds)
    mix = mix_schema.with_defaults({'render': {'mix_workers': workers}})
    space = mixer.resolve_space('hall')
    ctx = mix_context.MixContext(mix, space, name='bench')
    t0 = time.perf_counter()
    out = mixer.mix_stems(sc, stems, SR, ctx=ctx)
    dt = time.perf_counter() - t0
    print(f'mix_stems -> {out.shape[0] / SR:.1f} s of audio in {dt:.2f} s '
          f'({out.shape[0] / SR / max(dt, 1e-9):.1f}x realtime)')
    return dt


def case_validate(seconds):
    import soundfile as sf
    import mixer
    mixer.use_mix('default')
    x = synth(seconds, gain=0.2)
    fd, path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        sf.write(path, x, SR, subtype='PCM_24')
        print(f'file: {seconds:g} s stereo PCM_24 = {x.nbytes / MB:.1f} MB of float32 samples')
        t0 = time.perf_counter()
        rep = mixer._validate_export(path, SR, expected_seconds=seconds, ceiling=-1.5)
        dt = time.perf_counter() - t0
        print(f'_validate_export -> peak {rep["peak_db"]:.2f} dBFS, {dt:.2f} s')
        return dt
    finally:
        os.remove(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('case', choices=('lufs', 'mix', 'validate'))
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--stems', type=int, default=8)
    ap.add_argument('--workers', type=int, default=1, help='render.mix_workers for the mix case')
    ap.add_argument('--repeat', type=int, default=1)
    a = ap.parse_args()
    before, _ = peak_mb()
    for _ in range(max(1, a.repeat)):
        if a.case == 'lufs':
            case_lufs(a.seconds)
        elif a.case == 'mix':
            case_mix(a.stems, a.seconds, a.workers)
        else:
            case_validate(a.seconds)
    peak, rss = peak_mb()
    print(f'peak RSS {peak:.0f} MB   (resident now {rss:.0f} MB)')
    print(f'idle baseline before the case: {before:.0f} MB')


if __name__ == '__main__':
    main()
