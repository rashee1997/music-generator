"""ears.py - the virtual-listener rows.

A virtual ear measures what a listener would hear at a position: loudness at the ear, roughness, sharpness. The
measurement is advisory, so these rows never bind and never become a lever problem; the module keeps them in the
report because they explain *why* a binding row matters.
"""
from __future__ import annotations

from .. import margins
from . import base


def analyse(case, rows, history=()):
    notes = []
    for r in rows:
        notes.append(f"{r['row']} = {r.get('value')} ({r.get('unit') or 'index'}): measured at a listener position, "
                     f"advisory; it never fails the gate")
    return base.Analysis(rows=rows, levers=[], coefficients={}, notes=notes,
                         measured=[r['row'] for r in rows], first_order=False)
