"""domains - one module per measured domain, loaded only when a row it owns is in question.

A domain module answers three questions about the rows it owns:

    analyse(case, rows)   -> Analysis(rows, levers, coefficients, notes)
    levers(case)          -> the changes this domain may legally make (bounded, typed)
    notes                 -> what it could not measure, and why

`analyse` returns coefficients for a first-order model: d(value of row)/d(lever), in the row's own units. They are
linearisations of the same measurements the gate took, not new measurements, and the report says so. The point is
not precision: it is to know, before another render, which change moves which row and which pair of rows cannot be
satisfied at once.
"""
from __future__ import annotations

import importlib

from . import base

MODULES = ('master', 'stems', 'spectral', 'spatial', 'channels', 'hrtf', 'chem', 'ears', 'direction')


def get(name):
    """Import one domain module, or None when there is no such module."""
    if name not in MODULES:
        return None
    return importlib.import_module(f'.{name}', __package__)


def analyse(name, case, rows, history=None):
    mod = get(name)
    if mod is None:
        return base.Analysis(rows=rows, notes=[f'no module for domain "{name}"'])
    return mod.analyse(case, rows, history=history or ())
