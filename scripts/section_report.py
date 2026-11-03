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
"""section_report.py - measure a render section by section, so two versions can be compared on the same numbers.

    python3 scripts/section_report.py score.json cue.wav            # one render
    python3 scripts/section_report.py a.json a.wav b.json b.wav     # two renders side by side

For each section of the score's plan (or, without a plan, for four equal parts) it reports:
  loudness   RMS in dBFS of the render over the section's seconds
  active     tracks with at least one note sounding in the section (density, read from the notes, not the audio)
  lead       whether the melody track is sounding there
  ring       RMS of the final 3 s, to show whether the ending has a tail
These are measurements, not taste. They show whether loudness and density move apart, whether the climax is the
loudest and densest section, and whether the ending has a tail. They cannot say the music is moving.
"""
import json
import sys

import numpy as np
import soundfile as sf


def bar_seconds(score):
    return score['ts'][0] * 60.0 / score['bpm']


def sections(score, n_bars):
    plan = score.get('plan')
    if plan:
        return [(s['name'], s['start_bar'], s['end_bar']) for s in plan['sections']]
    q = max(1, n_bars // 4)
    return [(f'part{i + 1}', i * q, n_bars if i == 3 else (i + 1) * q) for i in range(4)]


def report(score_path, wav_path):
    score = json.load(open(score_path, encoding='utf-8'))
    x, sr = sf.read(wav_path, always_2d=True)
    mono = x.mean(1)
    bs = bar_seconds(score)
    n_bars = score['meta']['bars']
    rows = []
    for name, a, b in sections(score, n_bars):
        t0, t1 = a * bs, b * bs
        seg = mono[int(t0 * sr):int(t1 * sr)]
        rms = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9) if len(seg) else -120.0
        active, lead = 0, False
        for tr in score['tracks']:
            hit = [n for n in tr['notes'] if a * score['ts'][0] <= n['t'] < b * score['ts'][0]]
            if hit:
                active += 1
                if tr.get('role') == 'melody':
                    lead = True
        rows.append(dict(section=name, bars=f'{a}-{b}', loudness_db=round(float(rms), 1), active=active, lead=lead))
    tail = mono[-int(3 * sr):] if len(mono) > 3 * sr else mono
    ring = 20 * np.log10(np.sqrt(np.mean(tail ** 2)) + 1e-9)
    return rows, round(float(ring), 1), len(mono) / sr


def show(label, rows, ring, dur):
    print(f'{label}  ({dur:.1f} s, final 3 s RMS {ring} dBFS)')
    print(f'  {"section":9s} {"bars":7s} {"loudness":>9s} {"active":>7s} lead')
    for r in rows:
        print(f'  {r["section"]:9s} {r["bars"]:7s} {r["loudness_db"]:8.1f}  {r["active"]:5d}  {"yes" if r["lead"] else "no"}')


def main():
    if len(sys.argv) not in (3, 5):
        sys.exit(__doc__)
    pairs = [(sys.argv[i], sys.argv[i + 1]) for i in range(1, len(sys.argv), 2)]
    import cli_util
    for sp, wp in pairs:
        cli_util.require_file(sp, 'score')
        cli_util.require_file(wp, 'audio file')
    for sp, wp in pairs:
        rows, ring, dur = report(sp, wp)
        show(wp, rows, ring, dur)


if __name__ == '__main__':
    main()
