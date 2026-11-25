"""chem.py - the inferred-chemistry rows.

These are predictions about a listener (valence, arousal, tension, affiliation) read out of measured audio
descriptors. They are advisory by construction: the gate warns, it does not fail. The module reports which descriptor
the prediction rests on so a change can be aimed at it, and never turns a prediction into a lever problem.
"""
from __future__ import annotations

from .. import margins
from . import base


def analyse(case, rows, history=()):
    notes = []
    for r in rows:
        val = r.get('value')
        notes.append(f"{r['row']} = {val} ({r.get('unit') or 'index'}): advisory prediction from the measured "
                     f"descriptors, cannot fail; read it, do not chase it")
    return base.Analysis(rows=rows, levers=[], coefficients={}, notes=notes,
                         measured=[r['row'] for r in rows], first_order=False)
