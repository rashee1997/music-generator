# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""arc_report.py - how loud a finished master is, and for how long, section by section.

The quality gate says whether a render is faulty. It does not say whether the piece has the pressure its brief asked
for: a cue can pass every row and still be quiet for most of its length. This report puts numbers on that so the
direction sheet's `energy` and `loudness` can be compared with what was rendered. It reports; it never edits a mix
and it never fails (a diagnostic is not a gate row).

    python scripts/helpers/arc_report.py out/master.wav --score scores/<title>_score.json

What it prints
    - integrated loudness, loudness range (LRA) and crest factor of the file
    - per section (from the score's `plan.sections`): mean and highest 3 s loudness, and its distance from the file's
      loudest 3 s
    - the share of the file within `--near` LU of its loudest 3 s ("pressure share")
    - every stretch longer than `--gap-s` seconds that sits more than `--gap-lu` below the integrated loudness

The defaults for `--near`, `--gap-lu` and `--gap-s` are starting values, not measured limits: change them to the
brief. 3 s loudness is EBU Tech 3341 short-term loudness from `scripts/loudness.py`.
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import loudness  # noqa: E402

HOP_S = 0.5          # the short-term series' hop; each value covers the 3 s that start at index * HOP_S


def _sections(score_path, duration):
    if not score_path:
        return [dict(name='whole piece', start_s=0.0, end_s=duration)]
    score = json.load(open(score_path, encoding='utf-8'))
    out = []
    for s in (score.get('plan') or {}).get('sections') or []:
        if 'start_s' in s and 'end_s' in s:
            out.append(dict(name=str(s.get('name', '?')), start_s=float(s['start_s']), end_s=float(s['end_s'])))
    return out or [dict(name='whole piece', start_s=0.0, end_s=duration)]


def _gaps(st, floor_db, min_s):
    """(start_s, end_s) of every run of short-term values below floor_db that lasts at least min_s."""
    runs, i = [], 0
    while i < len(st):
        if st[i] >= floor_db:
            i += 1
            continue
        j = i
        while j + 1 < len(st) and st[j + 1] < floor_db:
            j += 1
        a, b = i * HOP_S, j * HOP_S + 3.0
        if b - a >= min_s:
            runs.append((a, b))
        i = j + 1
    return runs


def report(wav, score_path=None, near_lu=6.0, gap_lu=12.0, gap_s=4.0):
    import soundfile as sf
    x, sr = sf.read(wav)
    x = x if x.ndim > 1 else x[:, None]
    dur = len(x) / float(sr)
    blocks = loudness.Blocks(x, sr)
    st = np.asarray(blocks.short_term(HOP_S), dtype=float)
    integrated = float(blocks.integrated())
    top = float(np.max(st))
    rows = []
    for s in _sections(score_path, dur):
        a, b = int(s['start_s'] / HOP_S), max(int(s['start_s'] / HOP_S) + 1, int(s['end_s'] / HOP_S) - 5)
        seg = st[a:b]
        if seg.size:
            rows.append((s['name'], s['start_s'], s['end_s'], float(np.mean(seg)), float(np.max(seg)), float(np.max(seg)) - top))
    crest = 20.0 * np.log10(float(np.max(np.abs(x))) / (float(np.sqrt(np.mean(x ** 2))) + 1e-12) + 1e-12)
    share = float(np.mean(st >= top - near_lu))
    print(f'{os.path.basename(wav)}: {dur:.1f} s, integrated {integrated:.1f} LUFS, LRA {float(blocks.lra()):.1f} LU, '
          f'crest {crest:.1f} dB, loudest 3 s {top:.1f} LUFS')
    print(f'pressure share: {100 * share:.0f} % of the file is within {near_lu:g} LU of its loudest 3 s')
    print(f'{"section":<18}{"from":>7}{"to":>7}{"mean":>8}{"max":>8}{"vs top":>8}')
    for name, a, b, mean, mx, d in rows:
        print(f'{name:<18}{a:>7.1f}{b:>7.1f}{mean:>8.1f}{mx:>8.1f}{d:>+8.1f}')
    gaps = _gaps(st, integrated - gap_lu, gap_s)
    if gaps:
        print(f'quiet stretches (> {gap_lu:g} LU under the integrated level for {gap_s:g} s or more): ' +
              ', '.join(f'{a:.1f}-{b:.1f} s' for a, b in gaps))
    else:
        print(f'no stretch longer than {gap_s:g} s sits more than {gap_lu:g} LU under the integrated level')
    return dict(integrated=integrated, top=top, share=share, sections=rows, gaps=gaps)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('wav')
    ap.add_argument('--score', default=None, help='the score JSON, for its plan.sections')
    ap.add_argument('--near', type=float, default=6.0, help='LU below the loudest 3 s that count as full pressure')
    ap.add_argument('--gap-lu', type=float, default=12.0, help='LU below the integrated level that count as a gap')
    ap.add_argument('--gap-s', type=float, default=4.0, help='shortest gap to report, in seconds')
    a = ap.parse_args(argv)
    report(a.wav, a.score, a.near, a.gap_lu, a.gap_s)
    return 0


if __name__ == '__main__':
    sys.exit(main())
