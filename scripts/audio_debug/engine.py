"""engine.py - run the domains that are in question, and only those.

The order is deliberate and cheap-first:

    1. classify every row from the gate's own numbers (no audio is touched);
    2. keep the binding rows, drop the advisory ones (chemistry, ears, direction are predictions, not limits);
    3. import and run one module per domain that owns a binding row - domains with nothing failing are never loaded;
    4. solve the merged system once;
    5. write the report into the project's reports folder, and record what was proposed.

A project whose only failure is an impulse runs one domain and reads one stem's high frequencies. Nothing re-renders.
"""
from __future__ import annotations

import os

from . import Case, domains, margins, measure, report, rows as rowmap, solve


def classify(case, level=None):
    """(binding rows, advisory rows, ignored rows) from the gate's own verdicts."""
    binding, advisory, other = [], [], []
    for r in case.rows:
        name = r.get('row') or ''
        if rowmap.is_advisory(name) or r.get('level') == 'INFO':
            advisory.append(r)
        elif r.get('level') in (level or rowmap.BINDING_LEVELS):
            binding.append(r)
        else:
            other.append(r)
    return binding, advisory, other


def autopsy(case, level=None, history=None, write=True, stamp=None):
    """Analyse the rows in question and return the report object (also written under reports/)."""
    binding, advisory, other = classify(case, level)
    used_level = level
    if not binding and not level:
        binding, advisory, other = classify(case, ('WARN',))
        used_level = 'WARN'
    # A discrete row whose verdict lost its numbers gets them back from the gate's own checker before any domain
    # prices it; two seconds on one file, and only for rows that actually failed.
    measured = measure.enrich(case, binding)
    run = [d for d in rowmap.domains_for(binding) if d in domains.MODULES]
    skipped = rowmap.skipped_domains(binding + advisory, run)

    analysis = None
    for name in run:
        got = domains.analyse(name, case, [r for r in binding + other if rowmap.domain_of(r.get('row')) == name],
                              history=history or ())
        analysis = got if analysis is None else analysis.merge(got)
    if analysis is None:
        from .domains import base
        analysis = base.Analysis()

    # Risk closure. A lever is not free just because its own row is the only one failing: changing a stem's ramp or
    # band moves every row that stem has, in domains that had nothing to fail and were therefore skipped. Bring those
    # rows in as constraints before solving, which is what turns a one-knob fix into a check that it breaks nothing.
    touched = {lv.stem for lv in analysis.levers if lv.stem
               and any(abs(c) > 0 and lid == lv.id for (_k, lid), c in analysis.coefficients.items())}
    if touched:
        extra = [r for r in case.rows if r.get('stem') in touched
                 and rowmap.domain_of(r.get('row')) not in run]
        for name in rowmap.domains_for(extra):
            analysis.merge(domains.analyse(name, case,
                                           [r for r in extra if rowmap.domain_of(r.get('row')) == name],
                                           history=history or ()))
            run.append(name)
        touched_note = ', '.join(sorted(touched))
    else:
        touched_note = ''

    plan = solve.plan(analysis, history=history or ()) if analysis.rows else solve.Plan(status='no rows')
    known = {r['row'] for r in analysis.rows}
    for r in binding:
        if r['row'] not in known:                    # a row no module claimed is still reported, never dropped
            analysis.notes.append(f"{r['row']}: no domain module examines this row yet")

    if touched_note:
        analysis.notes.append(f'risk closure: the levers that move this row belong to {touched_note}, so every row of '
                              f'those stems was loaded as a constraint before the plan was solved')
    rep = report.Report(case=case, analysis=analysis, plan=plan, binding=binding, advisory=advisory,
                        run_domains=run, skipped=skipped, level=used_level or 'FAIL', stamp=stamp,
                        remeasured=measured)
    if write:
        rep.write()
    return rep
