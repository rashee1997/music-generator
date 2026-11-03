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

#!/usr/bin/env python3
"""mix_bench.py - how long a mix takes, and what the opt-in strategies actually change.

    python3 scripts/mix_bench.py                       # timing on a synthetic arrangement
    python3 scripts/mix_bench.py --compare             # legacy vs adaptive, measured side by side
    python3 scripts/mix_bench.py --score s.json --stems stems/   # time a real piece

The comparison is a measurement, not a claim: it prints the loudness, crest, mono fold and processing
time of the same stems under two configurations, so a change can be seen rather than believed. It does
not listen; nothing here is an improvement until a person or `listen.py` says it is.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsp                    # noqa: E402
import mix_context            # noqa: E402
import mix_schema             # noqa: E402
import mixer                  # noqa: E402

SR = 44100


def synthetic(seconds=20.0, seed=3):
    """A small arrangement that exercises every branch: lead, pad, bass, drums and an ambience bed."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR

    def env(a, r, ms=5.0):
        return np.exp(-(t % (ms / 1000.0)) * 0.0) * 1.0

    lead = 0.25 * np.sin(2 * np.pi * 440 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t))
    pad = 0.18 * (np.sin(2 * np.pi * 220 * t) + 0.5 * np.sin(2 * np.pi * 330 * t))
    bass = 0.30 * np.sin(2 * np.pi * 55 * t)
    kick = np.zeros(n)
    for k in range(int(seconds * 2)):
        i = int(k * 0.5 * SR)
        L = min(n - i, int(0.12 * SR))
        kick[i:i + L] += 0.6 * np.exp(-np.arange(L) / (0.02 * SR)) * np.sin(2 * np.pi * 60 * np.arange(L) / SR)
    bed = 0.05 * rng.standard_normal(n)
    st = lambda x: np.stack([x, x], 1).astype(np.float32)
    return {'lead': st(lead), 'pad': st(pad), 'bass': st(bass), 'kick': st(kick), 'bed': st(bed)}


def synthetic_score():
    return {'bpm': 120, 'meter': [4, 4], 'room': 'hall', 'mix_preset': 'default',
            'tracks': [{'name': 'lead', 'role': 'melody', 'instrument': 'flute'},
                       {'name': 'pad', 'role': 'pad', 'instrument': 'slow_strings'},
                       {'name': 'bass', 'role': 'bass', 'instrument': 'cello'},
                       {'name': 'kick', 'role': 'drum', 'instrument': 'kick'},
                       {'name': 'bed', 'role': 'environment', 'instrument': 'env:bed'}]}


def time_mix(score, stems, ctx=None, repeat=1):
    t0 = time.perf_counter()
    out = None
    for _ in range(repeat):
        out = mixer.mix_stems(score, stems, SR, ctx)
    ms = (time.perf_counter() - t0) / repeat * 1000.0
    return out, ms


def measure(x):
    return dict(lufs=mixer.lufs(x, SR), crest=dsp.crest_db(x), mono=dsp.mono_fold_db(x),
                corr=dsp.correlation(x), peak=20 * np.log10(np.abs(x).max() + 1e-12))


def compare(seconds=12.0):
    stems = synthetic(seconds)
    score = synthetic_score()
    base = mix_context.mix_for('default')
    adaptive = mix_schema.with_defaults({k: v for k, v in base.items() if k != '_source'})
    adaptive['gain_staging'] = dict(adaptive['gain_staging'], strategy='adaptive', peak_headroom_db=-1.0,
                                    crest_preserve_db=10.0, sparse_active_frac=0.2)
    rows = []
    for label, mix in (('legacy', base), ('adaptive', adaptive)):
        ctx = mix_context.MixContext(mix, mixer.resolve_space('hall'), name=label, space_name='hall',
                                     space_owned=False)
        out, ms = time_mix(score, stems, ctx, repeat=2)
        rows.append((label, ms, measure(out)))
    print(f'{"config":10s} {"ms":>8s} {"LUFS":>7s} {"crest":>6s} {"mono":>6s} {"corr":>6s} {"peak":>7s}')
    for label, ms, m in rows:
        print(f'{label:10s} {ms:8.1f} {m["lufs"]:7.1f} {m["crest"]:6.1f} {m["mono"]:6.1f} '
              f'{m["corr"]:6.2f} {m["peak"]:7.1f}')
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--compare', action='store_true', help='legacy vs adaptive, measured')
    ap.add_argument('--seconds', type=float, default=20.0)
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--score', default=None)
    ap.add_argument('--stems', default=None)
    a = ap.parse_args()
    if a.compare:
        compare(min(a.seconds, 30.0))
        return
    if a.score and a.stems:
        import json
        import soundfile as sf
        score = json.load(open(a.score, encoding='utf-8'))
        stems = {os.path.splitext(f)[0]: sf.read(os.path.join(a.stems, f), always_2d=True)[0].astype(np.float32)
                 for f in sorted(os.listdir(a.stems)) if f.lower().endswith('.wav')}
    else:
        score, stems = synthetic_score(), synthetic(a.seconds)
    out, ms = time_mix(score, stems, repeat=max(1, a.repeat))
    m = measure(out)
    print(f'{len(stems)} stems, {len(out) / SR:.1f}s of audio: {ms:.0f} ms per mix '
          f'({len(out) / SR / (ms / 1000.0):.1f}x real time)')
    print(f'LUFS {m["lufs"]:.1f}  crest {m["crest"]:.1f} dB  mono fold {m["mono"]:+.1f} dB  '
          f'correlation {m["corr"]:+.2f}  peak {m["peak"]:.1f} dBFS')


if __name__ == '__main__':
    main()
