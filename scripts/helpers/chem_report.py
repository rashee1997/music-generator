# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_report.py - the inferred-neurochemical arc of a finished master, beside the mood and genre it was written for.

The gate decides whether a render is faulty and the chem.* rows warn about the arc; this report prints the whole
trace so a direction can be revised from numbers instead of from memory. It reports; it never edits a score, a preset
or a mix, and it cannot fail a piece.

    python scripts/helpers/chem_report.py out/master.wav --score scores/<title>_score.json --project <dir>

What it prints
    - every pool: where it starts, where and when it peaks, where it ends, and its confidence tier
    - the arrival table against the sheet's hits: measured level contrast, the model's consummation peak, its offset
    - the 0..1 signature the mood and genre rows compare, and what the piece's own mood and genre ask for
    - every chem.* row as the gate would print it

The pool values are inferred states (proxy), not measurements; the constants are starting values in
references/data/presets/gate/chem/model.json and no corpus has calibrated them (docs/NEUROCHEMICAL-AFFECT-PLAN.md).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chem_model  # noqa: E402
import chem_model.config as config  # noqa: E402
import chem_model.targets as targets  # noqa: E402
import chem_rows  # noqa: E402
import gate_profiles  # noqa: E402


def _sheet(args):
    if args.direction:
        with open(args.direction, encoding='utf-8') as fh:
            return json.load(fh)
    if args.project:
        folder = os.path.join(args.project, 'direction')
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.endswith('.json'):
                    with open(os.path.join(folder, name), encoding='utf-8') as fh:
                        return json.load(fh)
    return {}


def report(wav, score_path, sheet=None, summary=None):
    score = json.load(open(score_path, encoding='utf-8'))
    gp = gate_profiles.resolve(score)
    rep = chem_model.evaluate(score, wav if wav and os.path.isfile(wav) else None, sheet or {}, summary, gp)
    print(f'{os.path.basename(score_path)}  {rep["observables"]["build"].get("at_s")} s arrival, '
          f'{rep["features"]["duration_s"]:.0f} s, {rep["features"]["bpm"]:g} BPM, step {rep["step_s"]:g} s')
    print('\npools (inferred state, proxy - not a measurement)')
    for pool in config.POOLS:
        v = rep['pools']['P'][pool]
        i = int(v.argmax()) if len(v) else 0
        print(f'  {pool:7s} tier {rep["model"]["pools"][pool]["tier"]}  start {v[0]:.2f}  peak {v[i]:.2f} at '
              f'{rep["times"][i]:5.1f} s  end {v[-1]:.2f}  availability {rep["pools"]["A"][pool][-1]:.2f}')
    obs = rep['observables']
    print('\narrivals')
    if not obs['arrivals']:
        print('  none declared and none measurable')
    for a in obs['arrivals']:
        c = 'n/a' if a['contrast_db'] is None else f'{a["contrast_db"]:+.1f} dB'
        print(f'  {a["at_s"]:6.1f} s  strength {a["strength"]:.2f}  level contrast {c}  '
              f'{"declared" if a["declared"] else "measured peak"}  {a["entering"]} part(s) entering')
    print(f'  consummation peak {obs["arrival"]["peak"]:.2f} at {obs["arrival"]["at_s"]:.1f} s'
          + (f', {obs["arrival"]["offset_s"]:.1f} s from the declared hit' if obs['arrival']['offset_s'] is not None else ''))
    print('\nsignature (0..1: each dimension against its row bar)')
    for d in config.DIMENSIONS:
        print(f'  {d:15s} {rep["dims"][d]:.2f}')
    m, g = rep['mood'], rep['genre']
    if m.get('known'):
        dist, diffs = targets.distance(rep['dims'], m['target'], m.get('excess_weight', 0.5))
        print(f'\nmood {"".join(m["ids"])}: target distance {dist:.2f} '
              f'(valence {m["valence"]:+.2f}, arousal {m["arousal"]:+.2f})')
        for d, got, want, delta in sorted(diffs, key=lambda x: -abs(x[3])):
            print(f'  {d:15s} measured {got:.2f}  asked {want:.2f}  {delta:+.2f}')
    else:
        print(f'\nmood: {m.get("why")}')
    print(f'genre "{g["genre"] or "undeclared"}" -> family {g["family"]}')
    for d, lim in g['constraints'].items():
        print(f'  {d:15s} measured {rep["dims"][d]:.2f}  {" ".join(f"{k} {v:g}" for k, v in lim.items())}')
    print('\nrows')
    for level, rid, detail in chem_rows.report_rows(rep, gp, config.problems()):
        print(f'  [{level}] {rid}: {detail}')
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('wav', nargs='?', default=None)
    ap.add_argument('--score', required=True)
    ap.add_argument('--direction', default=None, help='the direction sheet (default: <project>/direction/*.json)')
    ap.add_argument('--project', default=None)
    a = ap.parse_args(argv)
    if a.project:
        import presets
        presets.add_project(a.project)
    report(a.wav, a.score, _sheet(a))
    return 0


if __name__ == '__main__':
    sys.exit(main())
