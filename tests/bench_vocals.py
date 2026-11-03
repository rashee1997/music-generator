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

"""Old vs new vocal engine: seconds of compute per second of audio, for 1, 5 and 16 voices (same 10 s phrase)."""
import os
import sys
import time
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '..', 'scripts')]
import legacy_vocals as old  # noqa: E402
import vocals as new  # noqa: E402

SR = 44100
EV = [dict(t=0.0, dur=1.2, p=62, v=70), dict(t=1.2, dur=1.2, p=65, v=76), dict(t=2.4, dur=0.8, p=64, v=80),
      dict(t=3.2, dur=1.6, p=62, v=88), dict(t=5.2, dur=1.0, p=60, v=70), dict(t=6.2, dur=1.0, p=62, v=78), dict(t=7.2, dur=2.4, p=57, v=66)]
AUDIO_S = 9.6 + 1.5


def best_of(fn, n=2):
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return min(ts)


def main():
    warnings.simplefilter('ignore')
    new.render_choir(EV[:1], sr=SR, voices=1, hum=True)            # warm caches (calibration, imports)
    print(f'{"voices":>6} {"old s":>8} {"new s":>8} {"old xRT":>8} {"new xRT":>8}   (hum phrase, {AUDIO_S:.1f} s of audio, best of 2)')
    for v in (1, 5, 16):
        o = best_of(lambda: old.render_choir(EV, sr=SR, voices=v, hum=True, seed=1), 1 if v > 1 else 2)
        n = best_of(lambda: new.render_choir(EV, sr=SR, voices=v, hum=True, seed=1))
        print(f'{v:>6} {o:>8.2f} {n:>8.2f} {o / AUDIO_S:>8.2f} {n / AUDIO_S:>8.2f}')


if __name__ == '__main__':
    main()
