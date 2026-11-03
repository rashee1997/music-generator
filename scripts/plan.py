# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

#!/usr/bin/env python3
"""plan.py - the composition blueprint: sections, and separate energy curves per dimension.

compose.py used to drive every layer from one intensity number, so loudness, density and register rose together.
This module labels each bar with a section (open, develop, build, climax, hush, reveal, release) and gives each
section its own values for loudness (dyn), density (dens: which layers are allowed in), and whether the lead plays
(lead), plus a register shift for the lead (reg, semitones). Hit points set the structure: an impact starts a
climax, a silence is a hush, and the bars after it are a reveal.

    python3 scripts/plan.py score.json           # print the sections and the validation report
    from plan import build_plan, check_plan      # used by compose.py when the brief asks for a plan

Values are targets a director sets, not physics. Edit SECTION_TABLE to change the character of a section.
"""
import json
import sys

import numpy as np

# name: (dyn, density, lead, register shift in semitones, ending-ish)
SECTION_TABLE = {
    'open':    dict(dyn=0.30, dens=0.15, lead=True,  reg=0,  purpose='one voice over a bed: identity before density'),
    'develop': dict(dyn=0.50, dens=0.35, lead=True,  reg=0,  purpose='the motif returns over fuller harmony'),
    'build':   dict(dyn=0.60, dens=0.85, lead=True,  reg=0,  purpose='rhythm and bass arrive before the volume does'),
    'climax':  dict(dyn=1.00, dens=1.00, lead=True,  reg=12, purpose='full ensemble; the lead an octave up'),
    'hush':    dict(dyn=0.05, dens=0.00, lead=False, reg=0,  purpose='silence: everything falls away'),
    'reveal':  dict(dyn=0.85, dens=0.80, lead=True,  reg=0,  purpose='the reveal lands after the hush'),
    'release': dict(dyn=0.25, dens=0.45, lead=True,  reg=0,  purpose='quiet but still full of voices: the resolve sits, it does not thin to nothing'),
}
# fraction of the piece where each template section starts (used when no hit points are given)
TEMPLATE = [(0.00, 'open'), (0.18, 'develop'), (0.42, 'build'), (0.70, 'climax'), (0.84, 'release')]
ENDINGS = {'release': dict(fade_out=2.0, note='a thinning resolve: the tonic under a long ring'),
           'reveal': dict(fade_out=2.0, note='the reveal rings out; the tail is kept, not faded early')}


def _labels(n_bars, bb, bpm, hits):
    """One section name per bar: the template by fraction, overridden by hit points."""
    lab = [None] * n_bars
    for i, (frac, name) in enumerate(TEMPLATE):
        a = int(round(frac * n_bars))
        b = int(round(TEMPLATE[i + 1][0] * n_bars)) if i + 1 < len(TEMPLATE) else n_bars
        for k in range(a, min(b, n_bars)):
            lab[k] = name
    bar_of = lambda t: int(round(t * bpm / 60.0 / bb))
    silences = sorted(bar_of(h['t']) for h in hits if h.get('type') == 'silence')
    for h in hits:
        if h.get('type') != 'impact':
            continue
        b = bar_of(h['t'])
        nxt = [s for s in silences if s > b]
        e = nxt[0] if nxt else min(n_bars, b + max(2, int(round(0.14 * n_bars))))
        for k in range(b, min(e, n_bars)):
            lab[k] = 'climax'
    for h in hits:
        if h.get('type') != 'silence':
            continue
        s = bar_of(h['t'])
        L = max(1, int(round(float(h.get('beats', 1.5)) / bb)))
        for k in range(s, min(s + L, n_bars)):
            lab[k] = 'hush'
        for k in range(s + L, min(s + L + max(2, int(round(0.12 * n_bars))), n_bars)):
            lab[k] = 'reveal'
    # any bar with no label after the overrides keeps the release
    return [x or 'release' for x in lab]


def build_plan(n_bars, bb=4, bpm=100, hits=None):
    hits = list(hits or [])
    labels = _labels(n_bars, bb, bpm, hits)
    sections, s = [], 0
    for k in range(1, n_bars + 1):
        if k == n_bars or labels[k] != labels[s]:
            name = labels[s]
            sections.append(dict(name=name, start_bar=s, end_bar=k, **{x: SECTION_TABLE[name][x]
                                 for x in ('dyn', 'dens', 'lead', 'reg', 'purpose')}))
            s = k
    last = sections[-1]['name']
    ending = dict(kind=last if last in ENDINGS else 'release', **ENDINGS.get(last, ENDINGS['release']))
    return dict(n_bars=n_bars, bb=bb, bpm=bpm, sections=sections, ending=ending, hits=hits)


def per_bar(plan):
    """Per-bar arrays for compose.py: dyn, dens, lead (bool), reg (semitones). Short ramps smooth each boundary,
    except into or out of a hush, which cuts."""
    n = plan['n_bars']
    dyn, dens = np.zeros(n), np.zeros(n)
    lead = np.zeros(n, bool)
    reg = np.zeros(n)
    for sec in plan['sections']:
        for k in range(sec['start_bar'], sec['end_bar']):
            dyn[k], dens[k], lead[k], reg[k] = sec['dyn'], sec['dens'], sec['lead'], sec['reg']
    for i in range(1, len(plan['sections'])):          # one bar of blend at each boundary
        a, b = plan['sections'][i - 1], plan['sections'][i]
        if 'hush' in (a['name'], b['name']):
            continue
        k = b['start_bar']
        dyn[k] = (a['dyn'] + b['dyn']) / 2
        dens[k] = (a['dens'] + b['dens']) / 2
    return dyn, dens, lead, reg


def check_plan(plan, corr_limit=0.97):
    """Returns a list of (level, message). FAIL: the structure cannot work. CHECK: a question for the composer."""
    out = []
    secs = plan['sections']
    names = [s['name'] for s in secs]
    if 'climax' not in names:
        out.append(('FAIL', 'no climax section: add an impact hit or use a longer template'))
    else:
        c = next(s for s in secs if s['name'] == 'climax')
        if c['dyn'] < max(s['dyn'] for s in secs) - 1e-9:
            out.append(('FAIL', 'climax is not the loudest section'))
        before = [s for s in secs if s['start_bar'] < c['start_bar']]
        if before and c['dens'] <= max(s['dens'] for s in before):
            out.append(('CHECK', 'climax is not denser than what comes before it: it may not feel earned'))
    if secs and secs[0]['dens'] >= 0.5:
        out.append(('CHECK', 'the opening is already dense: the listener has nowhere to be led from'))
    if len(set(round(s['dens'], 2) for s in secs)) < 3:
        out.append(('CHECK', 'fewer than three density levels: the arrangement may not develop'))
    if secs and secs[-1]['dyn'] >= max(s['dyn'] for s in secs) - 0.2 and secs[-1]['name'] != 'reveal':
        out.append(('CHECK', 'the final section is nearly as loud as the climax: no release'))
    if plan['n_bars'] >= 8:
        dyn, dens, _, _ = per_bar(plan)
        if dyn.std() > 1e-6 and dens.std() > 1e-6:
            r = float(np.corrcoef(dyn, dens)[0, 1])
            if r > corr_limit:
                out.append(('CHECK', f'loudness and density move in lockstep (r={r:.2f}); vary one independently'))
    if any(s['name'] == 'hush' for s in secs) and not any(s['name'] == 'reveal' for s in secs):
        out.append(('CHECK', 'a hush with nothing after it: add a reveal or the silence may read as a cut'))
    return out or [('PASS', 'plan has an opening, a climax, a release and varied density')]


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: plan.py score.json   (prints the plan stored by compose.py, or a plan from a brief)')
    d = json.load(open(sys.argv[1], encoding='utf-8'))
    plan = d.get('plan') or d
    if 'sections' not in plan:
        sys.exit('no plan in that file: compose.py writes one when the brief sets "plan": true')
    for s in plan['sections']:
        print(f"  bars {s['start_bar']:3d}-{s['end_bar']:<3d} {s['name']:8s} dyn {s['dyn']:.2f} dens {s['dens']:.2f} "
              f"lead {'yes' if s['lead'] else 'no '} reg {s['reg']:+d}  {s['purpose']}")
    print('ending:', plan['ending']['kind'], '-', plan['ending']['note'])
    for lvl, msg in check_plan(plan):
        print(f'  {lvl:5s} {msg}')


if __name__ == '__main__':
    main()
