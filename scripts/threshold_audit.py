#!/usr/bin/env python3
"""threshold_audit.py - which gate numbers are still Python literals instead of rows.json parameters.

Every number a piece is judged by is meant to be a row parameter in references/data/presets/gate/data/rows.json, so a
profile can state it with a reason and a measurement. This lists the module-level numeric constants (NAME = 1.5, NAME =
(1, 2)) in the gate modules: each one is either a physical or unit constant (a sample rate, an ITU weighting) that stays
in code, or a threshold that has not been migrated yet. `tests/test_gate_literals.py` keeps the count from growing: a new
threshold goes in rows.json, and the test fails when a new literal constant appears without the fixture being
regenerated on purpose.

    python scripts/threshold_audit.py            # the list
    python scripts/threshold_audit.py --update   # rewrite tests/fixtures/gate/literal_constants.json (say why in the commit)
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(os.path.dirname(HERE), 'tests', 'fixtures', 'gate', 'literal_constants.json')
GATE_MODULES = ['quality_gate.py', 'stem_gate.py', 'gate_checks.py', 'pattern_audit.py', 'naturalness_check.py',
                'scene_gate.py', 'spatial_gate.py', 'ear_rows.py', 'chem_rows.py', 'preflight_lint.py']


def _is_number(node):
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_number(node.operand)
    if isinstance(node, (ast.Tuple, ast.List)):
        return bool(node.elts) and all(_is_number(e) for e in node.elts)
    return False


def scan(modules=GATE_MODULES):
    """{module: {NAME: line}} for every module-level UPPER_CASE numeric constant."""
    out = {}
    for m in modules:
        path = os.path.join(HERE, m)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read(), m)
        found = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and _is_number(node.value):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.isupper():
                        found[t.id] = node.lineno
        if found:
            out[m] = found
    return out


def names(scanned=None):
    s = scanned or scan()
    return {m: sorted(v) for m, v in s.items()}


def main():
    s = scan()
    if '--update' in sys.argv:
        os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(names(s), f, indent=1, sort_keys=True)
            f.write('\n')
        print('wrote', FIXTURE)
        return
    total = 0
    for m, v in s.items():
        print(f'{m}: {len(v)}')
        for n, line in sorted(v.items(), key=lambda kv: kv[1]):
            print(f'  {line:5d}  {n}')
        total += len(v)
    print(f'{total} literal constants in {len(s)} gate modules')


if __name__ == '__main__':
    main()
