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

"""ecology_schema.py - the validator of a biome preset's `ecology` block (called by biome.schema.problems)."""
import math

import roles

KEYS = ('density_budget', 'niches', 'rules', 'score')
SUB = {
    'density_budget': ('events_per_s_max', 'fatigue_guard'),
    'niches': ('auto', 'min_separation'),
    'score': ('occupancy', 'protect_roles', 'margin_db', 'pocket_threshold', 'bed_threshold', 'p_force', 'max_tries'),
}
RULE_ON = ('fauna', 'score')
RULE_DO = ('freeze', 'for_s', 'fade_ms', 'ramp_s', 'answer', 'after_ms', 'p')
# path -> (default, low, high, unit, doc)
NUMBERS = {
    'density_budget.events_per_s_max': (None, 0.001, 100.0, 'calls/s', 'calls begun per second over a sliding 10 s, all animals together'),
    'score.margin_db': (3.0, 0.0, 24.0, 'dB', 'how wide the score\'s figure is protected: 3 dB or more is one band either side, 6 dB or more is two'),
    'score.pocket_threshold': (0.35, 0.0, 1.0, '-', 'a foreground call needs the score to occupy its band less than this (starting value)'),
    'score.bed_threshold': (0.8, 0.0, 1.0, '-', 'a bed call is only kept out of passages the score fills beyond this (starting value)'),
    'score.p_force': (0.05, 0.0, 1.0, '-', 'chance a call that found no pocket is made anyway (starting value)'),
    'score.max_tries': (8, 0, 100, '-', 'pockets looked for before a call is given up (starting value)'),
    'rule.fade_ms': (200.0, 1.0, 20000.0, 'ms', 'how fast a call that is sounding falls silent when a rule freezes its animal'),
    'rule.ramp_s': (0.0, 0.0, 600.0, 's', 'how long the animal takes to come back after the freeze'),
    'rule.p': (1.0, 0.0, 1.0, '-', 'chance an answer is given'),
}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _in(path, v, out, where):
    d, lo, hi, unit, _ = NUMBERS[path]
    if not _num(v) or not lo <= v <= hi:
        out.append(f'{where}={v!r}: a number from {lo:g} to {hi:g} {unit}')


def _pair(v):
    return isinstance(v, list) and len(v) == 2 and all(_num(x) and x >= 0 for x in v) and v[0] <= v[1]


def problems(eco, preset=None):
    if not isinstance(eco, dict):
        return ['ecology: an object']
    out = [f'ecology: unknown key "{k}" (known: {", ".join(KEYS)})' for k in eco if k not in KEYS]
    names = {f.get('name') for f in (preset or {}).get('fauna', []) if isinstance(f, dict)}
    for blk, keys in SUB.items():
        v = eco.get(blk)
        if v is None:
            continue
        if not isinstance(v, dict):
            out.append(f'ecology.{blk}: an object')
            continue
        out += [f'ecology.{blk}: unknown key "{k}" (known: {", ".join(keys)})' for k in v if k not in keys]
    db = eco.get('density_budget') or {}
    if 'events_per_s_max' in db:
        _in('density_budget.events_per_s_max', db['events_per_s_max'], out, 'ecology.density_budget.events_per_s_max')
    ni = eco.get('niches') or {}
    if 'auto' in ni and not isinstance(ni['auto'], bool):
        out.append('ecology.niches.auto: true or false')
    if 'min_separation' in ni:
        s = str(ni['min_separation']).replace(' ', '')
        try:
            assert s.startswith('D<=') and 0.0 <= float(s[3:]) <= 1.0
        except (AssertionError, ValueError):
            out.append('ecology.niches.min_separation: "D<=x" with x from 0 to 1 (Schoener\'s overlap)')
    sc = eco.get('score') or {}
    if sc.get('occupancy', 'from_score') != 'from_score':
        out.append('ecology.score.occupancy: only "from_score"')
    for k in ('margin_db', 'pocket_threshold', 'bed_threshold', 'p_force', 'max_tries'):
        if k in sc:
            _in(f'score.{k}', sc[k], out, f'ecology.score.{k}')
    for r in sc.get('protect_roles', []):
        try:
            roles.canonical(r, strict=True)
        except Exception as exc:
            out.append(f'ecology.score.protect_roles: {exc}')
    rules = eco.get('rules', [])
    if not isinstance(rules, list):
        return out + ['ecology.rules: a list of {"on", "do"}']
    for i, r in enumerate(rules):
        w = f'ecology.rules[{i}]'
        if not isinstance(r, dict) or set(r) - {'on', 'do', 'note'} or not isinstance(r.get('on'), dict) or not isinstance(r.get('do'), dict):
            out.append(f'{w}: {{"on": {{...}}, "do": {{...}}}}')
            continue
        on, do = r['on'], r['do']
        out += [f'{w}.on: unknown key "{k}" (known: {", ".join(RULE_ON)})' for k in on if k not in RULE_ON]
        out += [f'{w}.do: unknown key "{k}" (known: {", ".join(RULE_DO)})' for k in do if k not in RULE_DO]
        if len(on) != 1:
            out.append(f'{w}.on: exactly one of {", ".join(RULE_ON)}')
        if 'fauna' in on and preset is not None and on['fauna'] not in names:
            out.append(f'{w}.on.fauna "{on["fauna"]}" is not an animal ({", ".join(sorted(names)) or "none"})')
        if not do.get('freeze') and not do.get('answer'):
            out.append(f'{w}.do: needs "freeze" (a list of animals) or "answer" (an animal)')
        for n in list(do.get('freeze') or []) + ([do['answer']] if do.get('answer') else []):
            if preset is not None and n not in names:
                out.append(f'{w}.do names "{n}", which is not an animal ({", ".join(sorted(names)) or "none"})')
        if 'for_s' in do and not (_pair(do['for_s']) or (_num(do['for_s']) and do['for_s'] >= 0)):
            out.append(f'{w}.do.for_s: seconds, or [low, high]')
        if 'after_ms' in do and not _pair(do['after_ms']):
            out.append(f'{w}.do.after_ms: [low, high] in ms')
        for k, p in (('fade_ms', 'rule.fade_ms'), ('ramp_s', 'rule.ramp_s'), ('p', 'rule.p')):
            if k in do:
                _in(p, do[k], out, f'{w}.do.{k}')
        if on.get('fauna') and on['fauna'] in (do.get('freeze') or []):
            out.append(f'{w}: an animal cannot freeze itself')
    return out
