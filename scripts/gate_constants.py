#!/usr/bin/env python3
"""gate_constants.py - the gate numbers that are measurement windows and cut-offs rather than a row's parameters.

`references/data/presets/gate/data/constants.json` holds each one with a source; `<project>/presets/gate/constants.json`
(`{"name": value}`) overrides by name for one piece. A number a row judges a piece by is a `rows.json` parameter instead
(AGENTS.md rule 18); this file is for what a measurement is made WITH. Unknown names raise: no silent default.
"""
import json
import os

SHIPPED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'references', 'data', 'presets',
                       'gate', 'data', 'constants.json')
_CACHE = {}


def _shipped():
    if 'shipped' not in _CACHE:
        with open(SHIPPED, encoding='utf-8') as f:
            _CACHE['shipped'] = json.load(f)['constants']
    return _CACHE['shipped']


def _project_overrides():
    try:
        import presets
        roots = list(getattr(presets, 'PROJECT_ROOTS', []) or [])
    except Exception:
        roots = []
    out = {}
    for r in roots:
        path = os.path.join(os.path.dirname(os.path.abspath(r)), 'presets', 'gate', 'constants.json')
        key = ('proj', path)
        if key not in _CACHE:
            try:
                with open(path, encoding='utf-8') as f:
                    _CACHE[key] = json.load(f)
            except (OSError, ValueError):
                _CACHE[key] = {}
        out.update(_CACHE[key])
    return out


def get(name):
    """The value of one gate constant: the project's override, else the shipped one. Raises KeyError on an unknown name."""
    table = _shipped()
    if name not in table:
        raise KeyError(f'unknown gate constant {name!r}; known: {", ".join(sorted(table))}')
    over = _project_overrides()
    return over[name] if name in over else table[name]['value']


def names():
    return sorted(_shipped())
