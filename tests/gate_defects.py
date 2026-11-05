"""The defect-injection matrix for both gate stages, as a module and a CLI.

One registry, two stages: each injection is applied to one stem (expected row `stem.*`) and, where it makes sense, to the
summed mix (expected row unsuffixed). A case is caught only when its own row FAILs; any other FAIL is collateral and is
reported, because a detector that fires on everything is not a detector.

    .venv/Scripts/python.exe tests/gate_defects.py --matrix
    .venv/Scripts/python.exe tests/gate_defects.py --matrix --out tests/fixtures/gate/defect_matrix.json

The material is `tests/gate_fixture.py`: short synthetic tones built in memory, not a rendered preset. No gate script
holds sound design; the fixture exists only to make the expected row unambiguous.
"""
import argparse
import datetime
import json
import os
import sys
import tempfile

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, HERE)

import gate_fixture as fx  # noqa: E402
import stem_gate  # noqa: E402
import quality_gate  # noqa: E402

STEM_CASES = [
    dict(name='baseline', expected=None, mutate=lambda s: s),
    dict(name='click', expected='stem.clicks', mutate=lambda s: dict(s, pad=fx.add_click(s['pad']))),
    dict(name='dropout', expected='stem.dropout', mutate=lambda s: dict(s, pad=fx.add_dropout(s['pad']))),
    dict(name='cut', expected='stem.cut', mutate=lambda s: dict(s, pad=fx.add_cut(s['pad']))),
    dict(name='truncate', expected='stem.end', mutate=lambda s: dict(s, pad=fx.truncate_end(s['pad']))),
    dict(name='late_start', expected='stem.edge', mutate=lambda s: dict(s, pad=fx.trim_head(s['pad']))),
    dict(name='dc', expected='stem.dc', mutate=lambda s: dict(s, bass=fx.add_dc(s['bass']))),
    dict(name='clip', expected='stem.clipping', mutate=lambda s: dict(s, lead=fx.clip_hard(s['lead']))),
    dict(name='noise', expected='stem.flatness', mutate=lambda s: dict(s, pad=fx.add_noise_burst(s['pad']))),
    dict(name='tick', expected='stem.tick', mutate=lambda s: dict(s, pad=fx.add_tick(s['pad']))),
    dict(name='dead', expected='stem.dead', mutate=lambda s: dict(s, lead=np.zeros_like(s['lead']))),
]

MIX_CASES = [
    dict(name='baseline', expected=None, mutate=lambda m: m),
    dict(name='click', expected='clicks', mutate=lambda m: fx.add_click(m, at=3.0, amp=0.5)),
    dict(name='dropout', expected='dropout', mutate=lambda m: fx.add_dropout(m, at=3.0, ms=80)),
    dict(name='dc', expected='master.dc', mutate=lambda m: fx.add_dc(m, offset=0.01)),
    dict(name='truncate', expected='end.abrupt', mutate=lambda m: fx.truncate_end(m, remove_s=1.0)),
    dict(name='clip', expected='clipping', mutate=lambda m: fx.clip_hard(m, gain=4.0)),
]


def _fails(rows):
    return [n for l, n, _ in rows if l == 'FAIL']


def _levels(rows):
    return {n: l for l, n, _ in rows}


def stem_matrix(workers=1):
    out = []
    for case in STEM_CASES:
        stems = case['mutate'](fx.build_stems())
        rows, meta = stem_gate.run_stem_gate(fx.score(), stems, sr=fx.SR, workers=workers)
        fails = _fails(rows)
        expected = case['expected']
        caught = (not fails) if expected is None else (expected in fails)
        out.append(dict(stage='stem', defect=case['name'], expect=expected or 'none', level='FAIL' if fails else 'PASS',
                        caught=bool(caught), rows_failed=fails,
                        collateral=[f for f in fails if f != expected]))
    return out


def mix_matrix(tmp):
    out = []
    for case in MIX_CASES:
        mix = case['mutate'](fx.build_mix(fx.build_stems()))
        wav = os.path.join(tmp, case['name'] + '.wav')
        sf.write(wav, mix, fx.SR)
        rows, _ = quality_gate.run_gate(None, wav_path=wav, refresh=False, score=fx.score(), mode='draft')
        levels = _levels(rows)
        expected = case['expected']
        fails = _fails(rows)
        caught = levels.get(expected) == 'FAIL' if expected else (not fails)
        out.append(dict(stage='mix', defect=case['name'], expect=expected or 'none',
                        level='FAIL' if fails else 'PASS', caught=bool(caught), rows_failed=fails,
                        collateral=[f for f in fails if f != expected]))
    return out


def run_matrix(workers=1):
    baseline_fails = len([r for r in stem_matrix(workers) if r['defect'] == 'baseline' and r['rows_failed']])
    with tempfile.TemporaryDirectory(prefix='gate_defects_') as tmp:
        rows = stem_matrix(workers) + mix_matrix(tmp)
    missed = [f"{r['stage']}:{r['defect']}" for r in rows if not r['caught']]
    return dict(generated=datetime.datetime.now().isoformat(timespec='seconds'), baseline_fails=baseline_fails,
                rows=rows, missed=missed)


def markdown(matrix):
    lines = ['| stage | defect | expected row | caught | rows that fired |', '|---|---|---|---|---|']
    for r in matrix['rows']:
        lines.append(f"| {r['stage']} | {r['defect']} | {r['expect']} | {'yes' if r['caught'] else 'NO'} | "
                     f"{'; '.join(r['rows_failed']) or '-'} |")
    lines.append('')
    lines.append(f"missed: {', '.join(matrix['missed']) if matrix['missed'] else 'none'}")
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--matrix', action='store_true', help='run every injection and print the table')
    ap.add_argument('--out', default=None, help='write the matrix JSON here')
    ap.add_argument('--workers', type=int, default=1)
    a = ap.parse_args()
    if not a.matrix:
        ap.error('pass --matrix')
    matrix = run_matrix(a.workers)
    print(markdown(matrix))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as fh:
            json.dump(matrix, fh, indent=2)
        print('wrote', a.out)
    sys.exit(1 if (matrix['missed'] or matrix['baseline_fails']) else 0)


if __name__ == '__main__':
    main()
