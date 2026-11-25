"""direction.py - the "does it go where it said" rows: focus, intent, balance, expression.

These compare the render against the declarations in the score, and the only legal change is to the declaration or to
the balance that realises it. A focus row is closed to a preset knob, and saying so is the point: the fix belongs in
the score's intent, not in an EQ.
"""
from __future__ import annotations

from .. import margins
from . import base


def analyse(case, rows, history=()):
    notes = []
    intent = case.score.get('intent') or {}
    focus = case.score.get('focus')
    for r in rows:
        notes.append(f"{r['row']}: judged against the score's declarations (focus={focus!r}, "
                     f"intent keys={sorted(intent)[:4]}), so the lever is the declaration or the balance, not a band")
    return base.Analysis(rows=rows, levers=[], coefficients={}, notes=notes,
                         measured=[r['row'] for r in rows], first_order=False)
