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

"""Objective old-vs-new numbers from tests/artifacts/vocals/{old,new}_*.wav -> tests/artifacts/vocals/REPORT.md.
These measure faults and differences. They do NOT show that either voice sounds human: listen."""
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
from vocal_scenarios import ART, SCENARIOS, _MELODY  # noqa: E402

JOINS = [1.2, 2.4, 3.2]          # connected note boundaries of the melody (seconds)


def db(x):
    return 20 * np.log10(x + 1e-12)


def stats(path, melody=True):
    y, sr = sf.read(path)
    m = y.mean(axis=1)
    win = int(0.04 * sr)
    out = dict(rms=db(np.sqrt(np.mean(m ** 2))), peak=db(np.abs(y).max()), dc=float(abs(y.mean(0)).max()),
               jump=float(np.abs(np.diff(m)).max() / (m.std() + 1e-12)))
    if not melody:
        return dict(out, join_dip_db=float('nan'), note_level_range_db=float('nan'), vel_corr=float('nan'))
    # level dip at note joins: RMS in +-20 ms around each join against the RMS 150-300 ms before it
    dips = []
    for j in JOINS:
        a = m[int((j - 0.02) * sr):int((j - 0.02) * sr) + win]
        b = m[int((j - 0.30) * sr):int((j - 0.15) * sr)]
        dips.append(db(np.sqrt(np.mean(a ** 2)) / (np.sqrt(np.mean(b ** 2)) + 1e-12)))
    out['join_dip_db'] = float(np.mean(dips))
    # note-to-note level range (sustain windows of the 7-note melody)
    lv = [db(np.sqrt(np.mean(m[int((t + 0.4 * d) * sr):int((t + 0.9 * d) * sr)] ** 2))) for t, d, p, v in _MELODY]
    out['note_level_range_db'] = float(max(lv) - min(lv))
    out['vel_corr'] = float(np.corrcoef([v for *_, v in _MELODY], lv)[0, 1])
    return out


def main():
    lines = ['# Vocal A/B: old engine vs new engine', '',
             'Files are loudness-matched copies for listening. Numbers are measured from the files. '
             'They show faults and differences, not realism. Listen before believing any of it.', '',
             '| scenario | engine | RMS dB | peak dB | DC | max step / std | dip at joins dB | note level range dB | corr(level, velocity) |',
             '|---|---|---|---|---|---|---|---|---|']
    for name in SCENARIOS:
        for tag in ('old', 'new'):
            p = os.path.join(ART, f'{tag}_{name}.wav')
            if not os.path.exists(p):
                continue
            s = stats(p, melody=not name.startswith('02'))
            lines.append(f'| {name} | {tag} | {s["rms"]:.1f} | {s["peak"]:.1f} | {s["dc"]:.1e} | {s["jump"]:.2f} | '
                         f'{s["join_dip_db"]:+.1f} | {s["note_level_range_db"]:.1f} | {s["vel_corr"]:+.2f} |')
    lines += ['', 'Joins are at 1.2, 2.4 and 3.2 s (the connected notes of the melody). A large negative dip means the voice '
              'drops out between notes. Velocities of the seven notes are 70, 76, 80, 88, 70, 78, 66.']
    open(os.path.join(ART, 'REPORT.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
