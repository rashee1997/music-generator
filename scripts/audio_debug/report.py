"""report.py - the autopsy as a person and a machine read it.

Written into the project's own `reports/` folder (`debug_audio.md`, `debug_audio.json`), next to the render record,
because it belongs to that piece's history: which row failed, what was measured about it, what the solver would move
and which pairs of rows cannot both be satisfied. Nothing here is an instruction to the gate; the gate's verdicts are
the input.
"""
from __future__ import annotations

import datetime as _dt
import json
import os

from . import margins

KIND_WORD = {'linear': 'solved', 'partial': 'best admissible set (row not cleared)',
             'greedy': 'best single moves', 'nothing to move': 'nothing to move',
             'no binding row': 'nothing binding', 'no rows': 'no rows'}


class Report:
    def __init__(self, case, analysis, plan, binding, advisory, run_domains, skipped, level, stamp=None,
                 remeasured=()):
        self.case = case
        self.analysis = analysis
        self.plan = plan
        self.binding = binding
        self.advisory = advisory
        self.run_domains = run_domains
        self.skipped = skipped
        self.level = level
        self.stamp = stamp or _dt.datetime.now().strftime('%Y%m%dT%H%M%S')
        self.remeasured = list(remeasured)

    # -- machine form -----------------------------------------------------------------------------
    def as_dict(self):
        return dict(
            stamp=self.stamp, project=os.path.basename(self.case.project), level=self.level,
            sources=self.case.sources,
            binding=[dict(row=r['row'], stem=r.get('stem'), level=r['level'], value=r.get('value'),
                          threshold=r.get('threshold'), unit=r.get('unit'),
                          safety=round(margins.safety(r)[0], 4), detail=r.get('detail', ''))
                     for r in self.binding],
            advisory=[dict(row=r['row'], value=r.get('value'), unit=r.get('unit')) for r in self.advisory],
            domains=dict(run=self.run_domains, skipped=self.skipped),
            model=dict(first_order=self.analysis.first_order, rows=len(self.analysis.rows),
                       levers=[lv.as_dict() for lv in {l.id: l for l in self.analysis.levers}.values()]),
            plan=self.plan.as_dict(), notes=self.analysis.notes)

    # -- human form -------------------------------------------------------------------------------
    def _lines(self):
        out = []
        push = out.append
        push(f"# Debug autopsy - {os.path.basename(self.case.project)}")
        push('')
        push(f"{self.stamp}  ·  level {self.level}  ·  plan {KIND_WORD.get(self.plan.status, self.plan.status)}")
        if self.case.sources:
            push('sources: ' + ', '.join(f'{k}={v}' for k, v in self.case.sources.items()))
        if self.remeasured:
            push('re-measured on the master with the gate\'s own checkers: ' + ', '.join(self.remeasured))
        if getattr(self.case, 'stale', False):
            push('**the audio on disk is newer than the verdict**: the pending render has not been judged, so only the '
                 'verdict\'s rows are used; re-render to measure the current mix')
        push('')
        push(f"## In question ({len(self.binding)})")
        if not self.binding:
            push('nothing failed, so nothing was analysed')
        for r in self.binding:
            s, sense, ss = margins.safety(r)
            push(f"- **{r['row']}**{(' on ' + r['stem']) if r.get('stem') else ''}: {r.get('value')} "
                 f"{r.get('unit') or ''} against {r.get('threshold')} -> {margins.describe(s)}")
            if r.get('detail'):
                push(f"  - {r['detail']}")
            att = (r.get('raw') or {}).get('attribution')
            if att:
                push('  - transient attributed to ' + ', '.join(f"{a['stem']} {100 * a['share']:.0f}%" for a in att))
        push('')
        push('## Domains')
        push(f"ran: {', '.join(self.run_domains) or 'none'}")
        if self.skipped:
            push('not run (nothing in question): ' + ', '.join(f'{d} ({n} rows)' for d, n in self.skipped.items()))
        if self.advisory:
            push(f"advisory, never binding: {len(self.advisory)} row(s) - "
                 + ', '.join(sorted({r['row'] for r in self.advisory})[:8]))
        push('')
        push('## Proposed (first-order prediction)')
        if not self.plan.deltas:
            push('no admissible move improves the binding rows')
        for lid, d in sorted(self.plan.deltas.items(), key=lambda kv: -abs(kv[1])):
            lv = next((l for l in self.analysis.levers if l.id == lid), None)
            unit = lv.unit if lv else ''
            where = f' {lv.text}' if lv else ''
            push(f"- `{lid}` {d:+.2f} {unit}{where}")
        if self.plan.predicted:
            push('')
            worst = sorted(self.plan.predicted.items(), key=lambda kv: kv[1][1])[:6]
            for k, (before, after) in worst:
                arrow = '->' if abs(after - before) > 1e-6 else '  '
                push(f"  {k}: {before:+.2f} {arrow} {after:+.2f}")
        push('')
        push('## Conflicts (no value satisfies both)')
        if not self.plan.conflicts:
            push('none found in the levers this project declares')
        for c in self.plan.conflicts:
            push(f"- `{c['lever']}` ({c['text']}): {c['why']}")
            push(f"  - feasible move interval {c['feasible'][0]:+.2f} .. {c['feasible'][1]:+.2f} {c['unit']} "
                 f"within bounds {c['bounds'][0]:+.2f} .. {c['bounds'][1]:+.2f}")
            push('  - ' + '; '.join(f"{r['row']} needs {r['needs']:+.2f} (safety now {r['safety']:+.2f})"
                                    for r in c['rows']))
        push('')
        if self.plan.closed:
            push('## Closed rows')
            push(', '.join(sorted(set(self.plan.closed))) + ' - no declared lever moves these; they need a score, '
                 'preset or dataset change rather than a knob')
            push('')
        if self.plan.burned:
            push('## Already tried (not proposed again)')
            for b in self.plan.burned:
                push(f"- `{b['lever']}` ({b['text']}) for {', '.join(b['rows'])}")
            push('')
        if self.analysis.notes:
            push('## Measurements behind this')
            for n in self.analysis.notes[:24]:
                push(f'- {n}')
            push('')
        if self.plan.notes:
            push('## Solver')
            for n in self.plan.notes:
                push(f'- {n}')
        return out

    @property
    def text(self):
        return '\n'.join(self._lines()) + '\n'

    def write(self):
        d = os.path.join(self.case.project, 'reports')
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'debug_audio.md'), 'w', encoding='utf-8') as fh:
            fh.write(self.text)
        with open(os.path.join(d, 'debug_audio.json'), 'w', encoding='utf-8') as fh:
            json.dump(self.as_dict(), fh, indent=1)
        return os.path.join(d, 'debug_audio.md')
