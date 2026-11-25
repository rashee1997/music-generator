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
from . import history as history_mod


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
    if history is None:
        # The pipeline runs this without arguments; a lever already spent must still be burned, or the automated
        # autopsy proposes the same failed experiment as the manual one did.
        history = history_mod.load(case.project)
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
    skipped = rowmap.skipped_domains(binding + advisory, run)   # after risk closure, so a loaded domain is not "skipped"

    if write:
        # Close the loop before planning: a move this engine proposed earlier and that the project has since applied
        # is judged by what this render says, and a spent one is burned for the plan below.
        settled = history_mod.settle(case.project, case, analysis.levers, binding)
        if settled:
            history = history_mod.load(case.project)
            analysis.notes.append('settled from the previous proposal: ' + ', '.join(
                f"{h['lever']} {h['delta']:+g} -> {h['outcome']}" for h in settled))
    plan = solve.plan(analysis, history=history or ()) if analysis.rows else solve.Plan(status='no rows')
    _adopt_replay(plan, analysis, history or ())
    if write and (plan.clearing or plan.deltas):
        history_mod.propose(case.project, plan, analysis.levers, binding, case)
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


def settle_only(case):
    """On a render with no failure: settle the proposals a previous autopsy made, so a fix that worked is on record."""
    from . import catalog
    return history_mod.settle(case.project, case, catalog.all_levers(case), [])


def _spent(exp, levers, history):
    """True when an experiment continues a move the history says failed: same lever, same direction, from the setting
    that failed. A deeper cut from a setting that improved is a new experiment, not a repeat."""
    by_id = {lv.id: lv for lv in levers}
    for lid, delta in exp['moves'].items():
        lv = by_id.get(lid)
        if lv is None:
            continue
        for h in history or ():
            if h.get('lever') != lid or h.get('outcome') not in ('no change', 'worse', 'same', 'unreachable'):
                continue
            if 'target' in h and abs(float(h['target']) - lv.current) > 0.26:
                continue
            if float(h.get('delta') or 0.0) * float(delta) > 0:
                return True
    return False


def _adopt_replay(plan, analysis, history=()):
    """A move priced by replay through the gate's own checker outranks a straight-line guess.

    The linear programme cannot see a row that is a robust statistic of the whole file, so for those rows it says
    "nothing to move" while a replay has just shown which cut clears it. Candidates are ranked by how many events they
    leave, then by whether their neighbours on the replay grid also clear (a move that clears only at one exact depth is
    inside the model's error and is not trusted), then by the smallest total cut. A candidate that repeats a move the
    history says failed is dropped. The best one becomes the clearing set when the programme has none.
    """
    exps = [e for e in analysis.experiments if e.get('verdict') in ('clears', 'better')
            and not _spent(e, analysis.levers, history)]
    by_moves = {tuple(sorted(e['moves'].items())): e for e in analysis.experiments}

    def robust(e):
        # share of the grid neighbours (one stem one step deeper or shallower) that also clear
        near = 0
        total = 0
        for k, v in e['moves'].items():
            for step in (-3.0, 3.0):
                mv = dict(e['moves'])
                mv[k] = v + step
                if mv[k] > 0:
                    continue
                other = by_moves.get(tuple(sorted(mv.items())))
                if other is not None:
                    total += 1
                    near += 1 if other['verdict'] == 'clears' else 0
        return near / total if total else 0.0

    for e in exps:
        e['robust'] = round(robust(e), 2)
    # the closed-loop plan accounts for the events a cut exposes (its profile counts those within 3 dB), so on a tie it wins
    plan.experiments = sorted(exps, key=lambda e: (e['value'], -(e.get('margin_db') or 0.0),
                                                   0 if e.get('kind') == 'iterative' else 1,
                                                   -e['robust'] if e['value'] == 0 else 0.0,
                                                   sum(abs(v) for v in e['moves'].values())))
    if not plan.experiments:
        return
    covered = {e['row'] for e in plan.experiments}
    plan.closed = [c for c in plan.closed if c not in covered]
    best = plan.experiments[0]
    if best.get('unverified'):
        plan.notes.append('the best candidate comes from a model that failed its sham test, so it is not adopted as a plan')
        return
    proved = (best['verdict'] == 'clears' and (best.get('margin_db') or 0.0) >= float(best.get('resolution_db') or 0.0))
    best['proved'] = proved
    if best['verdict'] == 'clears' and not proved:
        plan.status = 'replay (unproven)'
        plan.clearing = dict(best['moves'])
        plan.deltas = dict(best['moves']) if not plan.deltas else plan.deltas
        plan.notes.append(f"best candidate clears the modelled row with {best.get('margin_db') or 0:.0f} dB of margin but the "
                          f"model's own error is {best.get('resolution_db', 0):.1f} dB: this is a direction, not a proof, and "
                          f"the next render is the test (it will be recorded against this prediction)")
        return
    if best['verdict'] == 'clears' and not plan.clearing:
        plan.clearing = dict(best['moves'])
        plan.deltas = dict(best['moves']) if not plan.deltas else plan.deltas
        plan.status = 'replay'
        plan.notes.append('clearing set read from a replay through the gate\'s own checker, not from the linear model; '
                          'the next render is the measurement')

