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

"""Render vocal A/B WAVs. usage: render_vocal_artifacts.py old|new  -> tests/artifacts/vocals/<tag>_*.wav"""
import os
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '..', 'scripts')]
from vocal_scenarios import SCENARIOS, ART  # noqa: E402

SR = 44100


def render(which, sc, seed=11):
    if which == 'old':
        import legacy_vocals as v
        return v.render_choir(sc['events'], sr=SR, voices=sc['voices'], hum=sc['hum'], seed=seed)
    import vocals as v
    cfg = {'expression': sc['expression']} if 'expression' in sc else None
    return v.render_choir(sc['events'], sr=SR, voices=sc['voices'], hum=sc['hum'], seed=seed, config=cfg)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'old'
    os.makedirs(ART, exist_ok=True)
    for name, sc in SCENARIOS.items():
        t0 = time.perf_counter()
        y = render(which, sc)
        dt = time.perf_counter() - t0
        # loudness-matched for listening (whole file, one gain): RMS -20 dBFS, peak held under 0.9
        g = 0.1 / (float(np.sqrt(np.mean(y ** 2))) + 1e-12)
        g = min(g, 0.9 / (float(np.abs(y).max()) + 1e-12))
        pk = float(np.abs(y).max())
        sf.write(os.path.join(ART, f'{which}_{name}.wav'), y * g, SR)
        print(f'{which} {name}: {len(y)/SR:.1f}s audio, {dt:.2f}s render, peak {pk:.2f}')


if __name__ == '__main__':
    main()
