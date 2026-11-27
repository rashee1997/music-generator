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
"""gate_profiles.py - the quality gate adapts to the type of piece, and every adaptation is a preset (kind 'gate').

    python3 scripts/gate_profiles.py list                         # profiles and what each changes against 'melodic'
    python3 scripts/gate_profiles.py explain score.json [--project D]   # chosen profile, why, and every row's final mode
    python3 scripts/gate_profiles.py new horror --from tense --project D  # scaffold a project profile
    python3 scripts/gate_profiles.py check [--project D]          # validate every profile (project_gate calls the same)
    python3 scripts/gate_profiles.py rows                         # every gate row, its parameters and limits

A profile (references/data/presets/gate/<name>.json, or <project>/presets/gate/) says, per gate row, `apply`, `relax`
(new parameter values) or `skip`, and every relax/skip carries a reason. `extends` inherits another profile. `detect`
(keywords, pulse words, drone ratio) lets the gate infer a type when the score does not declare one. `flags` keep the
old feel-check switches (ambient / tense / dance). The score picks with "piece_type": "tense" or a list; a one-off row
change goes in score["gate"] = {row: {"mode": "relax", "reason": "...", param: value}}.

Hard limits (a profile cannot switch the gate off): PROTECTED rows stay `apply` with default numbers, every parameter has a
range, relax/skip need a reason. A relaxed row still prints (with its reason); a skipped row prints SKIP.
"""
import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import presets
import roles as rolelib

MODES = ('apply', 'relax', 'skip')
FLAGS = ('ambient', 'tense', 'dance')
DEFAULT_PROFILE = 'melodic'
TRAITS = {'drone_ratio_min': (0.0, 1.0)}
# a profile's "focus" says what the ear follows in this type of music. The roles are canonical role
# names (scripts/roles.py), so a piece whose line is written `lead` or `vocal` is judged exactly like
# one written `melody` - before this, only the literal string 'melody' was ever checked.
FOCUS_KEYS = ('roles', 'fallback', 'label', 'reason')

# id -> meaning, params {name: (default, lo, hi)}, protected. A bool default means a bool parameter.
ROWS_PATH = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate', 'data', 'rows.json')


def _load_rows(path=ROWS_PATH):
    """Every gate row's numbers, read from references/data/presets/gate/data/rows.json.

    The table used to be a Python literal. It is data now: `meaning`, `why` (the rationale the literal carried), the
    `protected`/`no_skip` marks, each parameter's default, its range or choices, and the `source` that number came from -
    copied from the row's own rationale where it had one, the words "starting value" where no published measurement
    exists. Nothing here is a second copy: this function is the only reader.

    Returns (rows, sources). `rows` keeps the shape the rest of the gate expects (`params` as tuples: (default, low,
    high[, unit]) for a number, (default, *choices) for an enumeration, (default,) for a flag), so no caller changed.
    """
    with open(path, encoding='utf-8') as f:
        doc = json.load(f)
    rows, sources = {}, {}
    for rid, spec in (doc.get('rows') or {}).items():
        entry = {'meaning': spec.get('meaning', '')}
        for k in ('protected', 'no_skip', 'hint'):
            if spec.get(k):
                entry[k] = spec[k]
        params, src = {}, {}
        for name, p in (spec.get('params') or {}).items():
            default = p.get('default')
            if isinstance(default, bool):
                params[name] = (default,)
            elif 'choices' in p:
                vals = [default] + [c for c in (p.get('choices') or []) if c != default]
                params[name] = tuple(vals)
            else:
                t = (default, p.get('low'), p.get('high'))
                if p.get('unit'):
                    t = t + (str(p['unit']),)
                params[name] = t
            src[name] = p.get('source', '')
        if params:
            entry['params'] = params
        rows[rid] = entry
        sources[rid] = src
    return rows, sources


ROWS, SOURCES = _load_rows()


# The report and the profile must name the same row, or nobody can tell which rule was relaxed. The gate prints some rows
# under a descriptive id (cochlear_roughness, spiral_tension_arc); the profile owns them under a stable one (roughness,
# feel.spiral). canonical() maps a reported id to its profile row, so `on`/`mode`/`param` work whichever id the caller has.
ALIASES = {
    'cochlear_roughness': 'roughness',
    'kick_grid': 'kick.grid',
    'harmonic_concordance': 'chroma.concordance',
    'erb_binaural_masking': 'masking.vs_melody',
    'balance': 'balance.vs_lead',
    'melodic_contour_feel': 'feel.contour',
    'harmonic_resolution_feel': 'feel.resolution',
    'groove_pocket_lock': 'feel.groove',
    'kinematic_effort_feel': 'feel.effort',
    'spiral_tension_arc': 'feel.spiral',
    'witek_groove_curve': 'feel.witek',
    'melodic_information_entropy': 'feel.entropy',
    'imm_cues': 'imm.cues',
    'imm_elevation': 'imm.elevation',
    'imm_frontback': 'imm.frontback',
    'imm_height_rules': 'imm.height_rules',
    'imm_band': 'imm.band',
    'imm_externalization': 'imm.externalization',
    'imm_envelopment': 'imm.envelopment',
    'imm_width': 'imm.width',
    'imm_foldown': 'imm.foldown',
    'imm_coloration': 'imm.coloration',
    'imm_route_parity': 'imm.route_parity',
    'imm_iacc_early': 'imm.iacc_early',
    'imm_clarity': 'imm.clarity',
    'imm_low_fold': 'imm.low_fold',
    'imm_kinematics': 'imm.kinematics',
    'natural_aliasing': 'natural.aliasing',
}
REPORT_IDS = {}
for _reported, _row in ALIASES.items():
    REPORT_IDS.setdefault(_row, []).append(_reported)


def canonical(rid):
    """The profile row that owns a reported row id (identity when it already is a profile row)."""
    return ALIASES.get(rid, rid)


def _pspec(row, name):
    row = canonical(row)
    return (ROWS[row].get('params') or {}).get(name)


def defaults(row):
    return {k: v[0] for k, v in (ROWS[row].get('params') or {}).items()}


# ---------- the figures the expression rows judge with ----------
# direction.expression is read from the sheet; expression.arousal_order and melody.variety are measured from the notes
# against the anchors below. Those anchors live in the piece's own gate profile (`"expression": {...}`), not in
# scripts/helpers/expression_report.py, because the anchors describe the piece: a drone cue has no build to rank, a
# through-composed cue has no repeating figure, a twenty-second sting is shorter than a phrase. The values here are the
# ones every profile inherited before the block existed, so a profile that says nothing is judged exactly as it was.
# Neither measured row can FAIL (WARN at most), and no value here switches a row off: EXPRESSION_RANGES bounds every
# number, so a profile states its piece instead of silencing the row (a min_rho of -1 would pass everything).
EXPRESSION_DEFAULTS = {
    'anchors': {'tempo_bpm': (60.0, 180.0), 'notes_per_beat': (0.0, 8.0), 'velocity': (0.2, 1.0),
                'pitch': (36.0, 84.0)},
    'arousal_order': {'min_sections': 3, 'min_rho': 0.5},
    'melody_variety': {'min_notes': 16, 'max_identical_bar_share': 0.6, 'min_interval_entropy_bits': 1.0,
                       'min_range_semitones': 7, 'intervals_for_leap_check': 20},
    'figure_roles': ('melody', 'lead', 'vocal'),
    'skip_roles': ('environment', 'fx', 'texture'),
}

EXPRESSION_RANGES = {
    ('arousal_order', 'min_sections'): (2, 10),
    ('arousal_order', 'min_rho'): (0.1, 1.0),          # 0 means "no rank order required": that is switching the row off
    ('melody_variety', 'min_notes'): (4, 200),
    ('melody_variety', 'max_identical_bar_share'): (0.0, 0.9),   # 1.0 would pass any amount of repetition
    ('melody_variety', 'min_interval_entropy_bits'): (0.2, 6.0),  # 0.0 would pass a single-interval line
    ('melody_variety', 'min_range_semitones'): (1, 48),
    ('melody_variety', 'intervals_for_leap_check'): (4, 200),
}

EXPRESSION_KEYS = ('anchors', 'arousal_order', 'melody_variety', 'figure_roles', 'skip_roles')


def expression_problems(expr, where):
    """Problems in a profile's `expression` block; [] when it is usable (the same contract as profile_problems)."""
    if expr is None:
        return []
    if not isinstance(expr, dict):
        return [f'{where}: "expression" must be an object ({', '.join(EXPRESSION_KEYS)})']
    problems = []
    for k in expr:
        if k not in EXPRESSION_KEYS + ('_source',):
            problems.append(f'{where}: expression has unknown key "{k}" (known: {", ".join(EXPRESSION_KEYS)})')
    for block in ('anchors', 'arousal_order', 'melody_variety'):
        d = expr.get(block)
        if d is None:
            continue
        if not isinstance(d, dict):
            problems.append(f'{where}: expression.{block} must be an object')
            continue
        for k, v in d.items():
            if k == '_source':
                continue
            if k not in EXPRESSION_DEFAULTS[block]:
                problems.append(f'{where}: expression.{block} has unknown key "{k}" '
                                f'(known: {", ".join(EXPRESSION_DEFAULTS[block])})')
            elif block == 'anchors':
                if not (isinstance(v, (list, tuple)) and len(v) == 2):
                    problems.append(f'{where}: expression.anchors.{k} must be [lo, hi]')
                else:
                    try:
                        lo, hi = float(v[0]), float(v[1])
                    except (TypeError, ValueError):
                        problems.append(f'{where}: expression.anchors.{k} must be two numbers')
                    else:
                        if hi <= lo:
                            problems.append(f'{where}: expression.anchors.{k} = {v}: hi must be above lo')
            else:
                lo, hi = EXPRESSION_RANGES[(block, k)]
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    problems.append(f'{where}: expression.{block}.{k} must be a number, not {v!r}')
                elif not lo <= float(v) <= hi:
                    problems.append(f'{where}: expression.{block}.{k} = {v} is outside {lo:g}..{hi:g}')
    for key in ('figure_roles', 'skip_roles'):
        v = expr.get(key)
        if v is None:
            continue
        if not isinstance(v, list) or not v:
            problems.append(f'{where}: expression.{key} must be a non-empty list of roles')
            continue
        for r in v:
            try:
                rolelib.canonical(r)
            except (rolelib.UnknownRole, TypeError):
                problems.append(f'{where}: expression.{key}: "{r}" is not a role. '
                                f'Known: {", ".join(rolelib.CANONICAL_ROLES)}')
    return problems


# ---------- the scene block ----------
# A profile may point at the piece's own timeline (`"scene": {...}`). The roles and the range of every figure live in
# references/data/presets/gate/scene_roles.json, not here: the contract is data, and a role the file does not list is an
# error rather than a silent 'place'. scripts/scene_timeline.py reads the windows; scene_gate.py judges them.
SCENE_KEYS = ('timeline', 'roles', 'dialogue')
SCENE_PATH = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate', 'data', 'scene_roles.json')


def scene_contract():
    """The role/key contract: roles, their allowed keys, required keys, and the range of every figure."""
    with open(SCENE_PATH, encoding='utf-8') as f:
        return json.load(f)


def _scene_num(key, spec, v, where):
    """Range/type problems for one scene figure, [] when it is usable. Ranges come from the contract file."""
    typ = spec.get('type', 'number')
    if typ == 'bool':
        return [] if isinstance(v, bool) else [f'{where}: {key} must be true or false']
    if typ == 'enum':
        return [] if v in spec.get('values', ()) else [f'{where}: {key} must be one of {list(spec.get("values", ()))}, not {v!r}']
    if typ == 'rows':
        bad = []
        if not isinstance(v, list) or not v:
            return [f'{where}: {key} must be a non-empty list of gate row ids']
        for rid in v:
            if canonical(rid) not in ROWS:
                bad.append(f'{where}: {key} names "{rid}", which is not a gate row')
        return bad
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return [f'{where}: {key} must be a number, not {v!r}']
    lo, hi = (spec.get('range') or [None, None])
    if lo is not None and not (lo <= float(v) <= hi):
        return [f'{where}: {key} = {v} is outside {lo:g}..{hi:g}']
    if typ == 'integer' and float(v) != int(v):
        return [f'{where}: {key} must be an integer, not {v!r}']
    return []


def scene_problems(scene, where):
    """Problems in a profile's `scene` block; [] when it is usable or absent.

    The block is how a piece says what its scenes are: which window is a peak, what a build may not do, where the sheet
    says silence. It cannot be half-written - an unknown role, a key a role may not state, a role missing the rule type
    its kind requires, or a figure outside its range is a failure (`scene.preset`), never a default.
    """
    if scene is None:
        return []
    if not isinstance(scene, dict):
        return [f'{where}: "scene" must be an object ({', '.join(SCENE_KEYS)})']
    try:
        doc = scene_contract()
    except (OSError, ValueError) as exc:
        return [f'{where}: scene_roles.json cannot be read ({exc})']
    keys, roles = doc.get('keys') or {}, doc.get('roles') or {}
    problems = []
    for k in scene:
        if k not in SCENE_KEYS + ('_source',):
            problems.append(f'{where}: scene has unknown key "{k}" (known: {", ".join(SCENE_KEYS)})')
    tl = scene.get('timeline')
    if tl is not None:
        if not isinstance(tl, dict):
            problems.append(f'{where}: scene.timeline must be an object')
        else:
            for k in tl:
                if k not in ('sheet', '_source', 'roles_from_sections', 'tolerance_s'):
                    problems.append(f'{where}: scene.timeline has unknown key "{k}" (sheet, roles_from_sections, tolerance_s)')
            if tl.get('sheet') is not None and not isinstance(tl['sheet'], str):
                problems.append(f'{where}: scene.timeline.sheet must be a path relative to the project')
            for k in ('roles_from_sections', 'tolerance_s'):
                if k in tl:
                    problems += _scene_num(k, doc['timeline'][k], tl[k], f'{where}: scene.timeline')
    role_map = scene.get('roles')
    if role_map is not None:
        if not isinstance(role_map, dict):
            problems.append(f'{where}: scene.roles must be an object {role: {...}}')
        else:
            for role, cfg in role_map.items():
                rk = str(role).strip().lower()
                if rk not in roles:
                    problems.append(f'{where}: scene.roles names "{role}", which is not a scene role. '
                                    f'Known: {", ".join(sorted(roles))}')
                    continue
                if not isinstance(cfg, dict):
                    problems.append(f'{where}: scene.roles.{role} must be an object')
                    continue
                rule = roles[rk]
                allowed = rule.get('allowed') or []
                for k in cfg:
                    if k == '_source':
                        continue
                    if k not in allowed:
                        problems.append(f'{where}: scene.roles.{role} may not state "{k}" '
                                        f'(allowed: {", ".join(allowed)})')
                    elif k in keys:
                        problems += _scene_num(f'scene.roles.{role}.{k}', keys[k], cfg[k], where)
                    else:
                        problems.append(f'{where}: scene.roles.{role}.{k} has no contract entry in scene_roles.json')
                for k in rule.get('required') or []:
                    if k not in cfg:
                        problems.append(f'{where}: scene.roles.{role} must state "{k}" (a {rule.get("kind", "scene")} '
                                        f'role without it is a word, not a rule)')
    dlg = scene.get('dialogue')
    if dlg is not None:
        if not isinstance(dlg, dict):
            problems.append(f'{where}: scene.dialogue must be an object')
        else:
            contract_d = doc.get('dialogue') or {}
            for k, v in dlg.items():
                if k in ('_source', 'windows'):
                    continue
                spec = contract_d.get(k)
                if spec is None:
                    problems.append(f'{where}: scene.dialogue has unknown key "{k}" '
                                    f'(known: windows, {", ".join(sorted(contract_d))})')
                else:
                    problems += _scene_num(f'scene.dialogue.{k}', spec, v, where)
            for row in dlg.get('windows') or []:
                try:
                    a, b = float(row[0]), float(row[1])
                except (TypeError, ValueError, IndexError):
                    problems.append(f'{where}: scene.dialogue.windows entries must be [start_s, end_s]')
                    break
                if b <= a:
                    problems.append(f'{where}: scene.dialogue.windows has {row} with end before start')
                    break
    if not role_map:
        problems.append(f'{where}: scene is declared but names no role: it would judge nothing. The whole-piece contrast '
                        f'floors are the scene.macro_contrast row parameters, set in "rows"')
    return problems


def _check_range(row, name, val, problems, where):
    spec = _pspec(row, name)
    if spec is None:
        problems.append(f'{where}: row "{row}" has no parameter "{name}". Parameters: {sorted(ROWS[row].get("params") or {}) or "none"}')
        return
    if isinstance(spec[0], bool):
        if not isinstance(val, bool):
            problems.append(f'{where}: {row}.{name} must be true or false')
        return
    if isinstance(spec[0], str):                     # an enumerated parameter: the tuple lists the allowed values
        if val not in spec:
            problems.append(f'{where}: {row}.{name} must be one of {list(spec)}, not {val!r}')
        return
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        problems.append(f'{where}: {row}.{name} must be a number')
    elif not spec[1] <= val <= spec[2]:
        problems.append(f'{where}: {row}.{name} = {val} is outside {spec[1]}..{spec[2]} (that would switch the check off, not adapt it)')


def row_problems(rows, where):
    """Problems in a {row: {mode, reason, params}} mapping (a preset's "rows" or a score's "gate")."""
    problems = []
    if not isinstance(rows, dict):
        return [f'{where}: "rows" must be an object {{row: {{mode, reason, ...}}}}']
    for rid0, cfg in rows.items():
        rid = canonical(rid0)
        if rid not in ROWS:
            problems.append(f'{where}: unknown row "{rid0}". Rows: {", ".join(sorted(ROWS))}')
            continue
        if not isinstance(cfg, dict):
            problems.append(f'{where}: row "{rid}" must be an object')
            continue
        mode = cfg.get('mode', 'apply')
        if mode not in MODES:
            problems.append(f'{where}: {rid}.mode "{mode}" is not one of {MODES}')
            continue
        extra = [k for k in cfg if k not in ('mode', 'reason', 'fallback') and k not in (ROWS[rid].get('params') or {})]
        for k in extra:
            problems.append(f'{where}: row "{rid}" has no parameter "{k}". Parameters: {sorted(ROWS[rid].get("params") or {}) or "none"}')
        if ROWS[rid].get('protected'):
            if mode != 'apply' or len(cfg) > (1 if 'mode' in cfg else 0):
                problems.append(f'{where}: "{rid}" is a protected row: it cannot be relaxed, skipped or retuned by any type of music')
            continue
        if mode == 'skip' and ROWS[rid].get('no_skip'):
            problems.append(f'{where}: "{rid}" cannot be skipped (it is the rule that makes the others safe); relax its numbers instead')
        if mode in ('relax', 'skip') and not str(cfg.get('reason', '')).strip():
            problems.append(f'{where}: {rid} is {mode} but has no "reason" (say why this type of music needs it)')
        if mode == 'skip' and any(k in (ROWS[rid].get('params') or {}) for k in cfg):
            problems.append(f'{where}: {rid} is skip and also sets parameters; pick one')
        if 'fallback' in cfg and cfg['fallback'] not in ROWS:
            problems.append(f'{where}: {rid}.fallback "{cfg["fallback"]}" is not a row')
        for k, v in cfg.items():
            if k in (ROWS[rid].get('params') or {}):
                _check_range(rid, k, v, problems, where)
    return problems


def profile_problems(name, p, all_profiles):
    where = f'gate/{name}'
    problems = []
    if not str(p.get('character', '')).strip():
        problems.append(f'{where}: missing "character" (one sentence: the type of music and why these rules suit it)')
    ext = p.get('extends')
    if ext is not None:
        seen, cur = [name], ext
        while cur is not None:
            if cur not in all_profiles:
                problems.append(f'{where}: extends "{cur}", which does not exist. Known: {sorted(all_profiles)}')
                break
            if cur in seen:
                problems.append(f'{where}: extends loops: {" -> ".join(seen + [cur])}')
                break
            seen.append(cur)
            cur = all_profiles[cur].get('extends')
    for f in p.get('flags', []):
        if f not in FLAGS:
            problems.append(f'{where}: flag "{f}" is not one of {FLAGS}')
    foc = p.get('focus')
    if foc is not None:
        if not isinstance(foc, dict):
            problems.append(f'{where}: "focus" must be an object (roles, fallback, label, reason)')
        else:
            for k in foc:
                if k not in FOCUS_KEYS:
                    problems.append(f'{where}: focus has unknown key "{k}" (roles, fallback, label, reason)')
            rs = foc.get('roles')
            if rs is not None and not isinstance(rs, list):
                problems.append(f'{where}: focus.roles must be a list of roles')
            elif rs is not None:
                for r in rs:
                    try:
                        rolelib.canonical(r)
                    except rolelib.UnknownRole:
                        problems.append(f'{where}: focus role "{r}" is not a role. Known: {", ".join(rolelib.CANONICAL_ROLES)}')
                if not rs and not str(foc.get('reason', '')).strip():
                    problems.append(f'{where}: focus.roles is empty; name at least one role, or give a reason '
                                    f'(a type of music with no line at all)')
            fb = foc.get('fallback')
            if fb is not None and fb not in ROWS:
                problems.append(f'{where}: focus.fallback "{fb}" is not a row')
    det = p.get('detect') or {}
    for k in det:
        if k not in ('keywords', 'pulse', 'traits'):
            problems.append(f'{where}: detect has unknown key "{k}" (keywords, pulse, traits)')
    for k in ('keywords', 'pulse'):
        if not all(isinstance(w, str) for w in det.get(k, [])):
            problems.append(f'{where}: detect.{k} must be a list of words')
    for k, v in (det.get('traits') or {}).items():
        if k not in TRAITS:
            problems.append(f'{where}: unknown trait "{k}". Traits: {sorted(TRAITS)}')
        elif not (isinstance(v, (int, float)) and TRAITS[k][0] <= v <= TRAITS[k][1]):
            problems.append(f'{where}: trait {k} must be {TRAITS[k][0]}..{TRAITS[k][1]}')
    problems += row_problems(p.get('rows', {}), where)
    problems += expression_problems(p.get('expression'), where)
    problems += scene_problems(p.get('scene'), where)
    return problems


def shipped_names():
    """Names of the profiles shipped with the skill (from the folder, so a project profile can never look shipped)."""
    folder = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate')
    try:
        return {os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith('.json')}
    except OSError:
        return set()


def problems(project_dirs=()):
    """Problems in every gate profile (shipped and project). Empty = good.

    A project may add a profile and `extends` any shipped one, but it may not reuse a shipped profile's NAME: that would
    retune the whole type in every piece of the project at once, which is exactly how a gate gets quietly switched off.
    """
    shipped = shipped_names()
    shipped_dir = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate').replace('\\', '/')
    for d in project_dirs:
        presets.add_project(d)
    allp = presets.load('gate')
    out = []
    for name, p in allp.items():
        src = str(p.get('_source') or '').replace('\\', '/')
        if name in shipped and src and not src.startswith(shipped_dir):
            out.append(f'gate/{name}: a project profile may not redefine the shipped profile "{name}". Give it its own name '
                       f'and "extends": "{name}", so the report says which type this piece was judged as')
    if DEFAULT_PROFILE not in allp:
        out.append(f'gate/{DEFAULT_PROFILE}: the default profile is missing')
    for name, p in allp.items():
        out += profile_problems(name, p, allp)
    return out


def _chain(name, allp):
    """Profile names from the root ancestor down to `name`."""
    chain, cur = [], name
    while cur is not None and cur not in chain:
        chain.append(cur)
        cur = allp[cur].get('extends')
    return chain[::-1]


def _merge_profile(name, allp):
    flags, rows, focus, expr, scene = set(), {}, {}, {}, {}
    for n in _chain(name, allp):
        p = allp[n]
        flags |= set(p.get('flags', []))
        focus = presets._deep_merge(focus, p.get('focus') or {})
        expr = presets._deep_merge(expr, p.get('expression') or {})
        scene = presets._deep_merge(scene, p.get('scene') or {})
        for rid, cfg in (p.get('rows') or {}).items():
            rid = canonical(rid)            # mode()/param() look rows up by canonical id: store them the same way
            rows[rid] = presets._deep_merge(rows.get(rid, {}), cfg)
    return flags, rows, focus, expr, scene


def _drone_ratio(score):
    tr = [t for t in score.get('tracks', []) if t.get('role') not in ('drum', 'environment') and 'notes' in t]
    if not tr:
        return 0.0
    return sum(1 for t in tr if t.get('is_drone') or t.get('allow_ostinato') or t.get('role') in ('drone', 'pad')) / len(tr)


def _score_text(score):
    meta = score.get('meta') or {}
    emotion = str(meta.get('emotion') or score.get('emotion', '')).lower()
    genre = str(meta.get('genre') or score.get('genre', '')).lower()
    feels = [str(f).lower() for f in (score.get('feel') or meta.get('mood_notes') or [])]
    pulse = str(score.get('pulse', '')).lower()
    return emotion + ' ' + genre + ' ' + ' '.join(feels) + ' ' + pulse, pulse


def infer(score, allp):
    """[(name, hits, why)] for every profile whose `detect` matches the score, strongest last."""
    text, pulse = _score_text(score)
    drone = _drone_ratio(score)
    found = []
    for name, p in allp.items():
        det = p.get('detect') or {}
        hits, why = 0, []
        for k in det.get('keywords', []):
            if k in text:
                hits += 1
                why.append(f'"{k}"')
        if pulse and pulse in det.get('pulse', []):
            hits += 1
            why.append(f'pulse={pulse}')
        dm = (det.get('traits') or {}).get('drone_ratio_min')
        if dm is not None and drone > dm:
            hits += 1
            why.append(f'drone_ratio {drone:.2f}')
        if hits:
            found.append((name, hits, ', '.join(why)))
    found.sort(key=lambda f: f[1])
    return found


class Profile:
    def __init__(self, names, how, why, flags, rows, errors, focus=None, expression=None, scene=None):
        self.names, self.how, self.why = names, how, why
        self.flags, self.rows, self.errors = flags, rows, errors
        self.focus = focus or {}
        self.expression = expression or {}
        self.scene = scene or {}

    def expression_cfg(self):
        """The figures this piece's expression rows are judged with, from the profile's `expression` block.

        The block is optional: without it a profile inherits EXPRESSION_DEFAULTS, which is what every profile used
        before the block existed. An unknown key, a number outside its range or a role that does not exist raises, so
        a typo in the piece's own figures is an error and never a silent default.
        """
        problems = expression_problems(self.expression, f'gate/{self.label}')
        if problems:
            raise ValueError('; '.join(problems))
        out = copy.deepcopy(EXPRESSION_DEFAULTS)
        for block in ('anchors', 'arousal_order', 'melody_variety'):
            for k, v in (self.expression.get(block) or {}).items():
                if k == '_source':
                    continue
                out[block][k] = tuple(float(x) for x in v) if block == 'anchors' else v
        for key in ('figure_roles', 'skip_roles'):
            if self.expression.get(key) is not None:
                out[key] = tuple(self.expression[key])
        both = set(out['figure_roles']) & set(out['skip_roles'])
        if both:
            # a role cannot be the figure and be skipped in the same profile: the figure would vanish from every
            # measurement and the row would report "no figure" for a piece that has one
            raise ValueError(f'gate/{self.label}: {sorted(both)} is in both figure_roles and skip_roles')
        out['source'] = (self.expression.get('_source')
                         or f'gate/{self.label} (no expression block: the shipped figures)')  
        return out

    @property
    def label(self):
        return '+'.join(self.names)

    def focus_roles(self):
        """The roles this type of music treats as its reference figure, most specific first.

        Defaults to the figure family, so a profile written before this field existed is judged exactly
        as before: melody, lead and vocal all count, instead of only the literal string 'melody'.
        """
        # `roles: []` is a decision (an effects piece has no line), not a missing key: an empty list must not
        # fall back to the figure family, or the type would demand the very line it just said it has none of.
        raw = self.focus.get('roles')
        out = []
        for r in (list(rolelib.LEAD) if raw is None else raw):
            try:
                c = rolelib.canonical(r)
            except rolelib.UnknownRole:
                continue
            if c not in out:
                out.append(c)
        return tuple(out)

    def focus_label(self):
        if not self.focus_roles():
            return 'no line by definition'
        if self.focus.get('label'):
            return str(self.focus['label'])
        return ' / '.join(self.focus_roles())

    def focus_fallback(self):
        return self.focus.get('fallback')

    def mode(self, rid):
        return self.rows.get(canonical(rid), {}).get('mode', 'apply')

    def on(self, rid):
        """False when the row is skipped by this type of piece."""
        return self.mode(rid) != 'skip'

    def param(self, rid, name):
        rid = canonical(rid)
        return self.rows.get(rid, {}).get(name, defaults(rid)[name])

    def fallback(self, rid):
        return self.rows.get(canonical(rid), {}).get('fallback')

    def notes(self):
        """Report rows: the chosen type, then every relaxed or skipped row with its reason."""
        out = [('INFO', 'piece_type', f'{self.label} ({self.how}{": " + self.why if self.why else ""})'),
               ('INFO', 'focus', f'judged around {self.focus_label()}')]
        dec = self.focus.get('reason')
        if dec and self.focus_roles():
            out.append(('INFO', 'focus', dec))
        for rid in sorted(self.rows):
            cfg = self.rows[rid]
            m = cfg.get('mode', 'apply')
            shown = rid if rid not in REPORT_IDS else f'{rid} (reported as {", ".join(REPORT_IDS[rid])})'
            if m == 'skip':
                out.append(('INFO', 'gate_skip', f'SKIP {shown}: {cfg.get("reason", "")}'))
            elif m == 'relax':
                nums = ', '.join(f'{k}={v}' for k, v in cfg.items() if k not in ('mode', 'reason', 'fallback'))
                out.append(('INFO', 'gate_relax', f'{shown}: {nums or "relaxed"} ({cfg.get("reason", "")})'))
        for e in self.errors:
            out.append(('FAIL', 'piece_type', e))
        return out


GATE_DIR = os.path.join('presets', 'gate')
FIGURE_SUBDIR = 'figures'
DATA_SUBDIR = 'data'


def artifacts_dir(project):
    """Where a project's gate lives: presets/gate/ (the profile and every gate data file, never reports/)."""
    return os.path.abspath(os.path.join(str(project), GATE_DIR))


def figures_dir(project):
    """The only place gate visualisations go: presets/gate/figures/."""
    return os.path.join(artifacts_dir(project), FIGURE_SUBDIR)


def data_dir(project):
    """The gate's data files (level.json, stem_gate.json, waveform.json, section_energy.json, ...): presets/gate/data/."""
    return os.path.join(artifacts_dir(project), DATA_SUBDIR)


def profile_files(project):
    """The project's own gate profiles (file stems), from presets/gate/*.json."""
    d = artifacts_dir(project)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.json'))


def project_profile_problems(score, project):
    """A project must carry its own gate profile. A shipped profile is a starting point, not a project's decision."""
    import presets as _presets
    own = profile_files(project)
    if not own:
        return ['no custom gate profile: a project must own presets/gate/<name>.json '
                '(scaffold: python scripts/gate_profiles.py new <name> --from <closest> --project <dir>)']
    if score is None:
        return []
    decl = score.get('piece_type')
    want = decl if isinstance(decl, list) else ([decl] if decl else [])
    want = [_presets._norm(w) for w in want if w]
    if not want:
        return [f'the score declares no "piece_type": a project is judged by its own gate profile ({own}) and by nothing inferred or default. '
                f'Declare it, and put in that profile only the rows this piece needs relaxed, each with a reason (gate_profiles.py relax)']
    missing = [w for w in want if w not in own]
    if missing:
        return [f'piece_type names {missing}, which is a shipped profile; this project owns {own}. '
                f'Declare a profile of this project (a custom gate is mandatory) or scaffold {missing[0]} into it']
    return []


def resolve(score):
    """The profile for this score: declared piece_type (name or list, merged in order), else inferred, else 'melodic'.
    score["gate"] row overrides are merged last. Never raises: an unknown type becomes a FAIL row (Profile.errors)."""
    allp = presets.load('gate')
    errors = []
    decl = score.get('piece_type')
    names, how, why = [], 'default', ''
    if decl:
        want = [decl] if isinstance(decl, str) else list(decl)
        want = [presets._norm(w) for w in want]
        for w in want:
            if w in allp:
                names.append(w)
            else:
                errors.append(f'piece_type "{w}" is not a gate profile. Known: {sorted(allp)}. Write one: gate_profiles.py new {w} --project <dir>')
        how = 'declared'
    if not names and not decl:
        found = infer(score, allp)
        if found:
            names = [f[0] for f in found]
            how = 'inferred'
            why = '; '.join(f'{n}: {w}' for n, _, w in found)
    if not names:
        names = [DEFAULT_PROFILE] if DEFAULT_PROFILE in allp else []
    flags, rows, focus, expr, scene = set(), {}, {}, {}, {}
    for n in names:
        f, r, foc, ex, sc = _merge_profile(n, allp)
        flags |= f
        focus = presets._deep_merge(focus, foc)
        expr = presets._deep_merge(expr, ex)
        scene = presets._deep_merge(scene, sc)
        for rid, cfg in r.items():
            rows[rid] = presets._deep_merge(rows.get(rid, {}), cfg)
    over = score.get('gate')
    if over:
        errors += row_problems(over, 'score "gate"')
        for rid, cfg in over.items():
            rid = canonical(rid)
            if rid in ROWS and not ROWS[rid].get('protected'):
                rows[rid] = presets._deep_merge(rows.get(rid, {}), cfg)
    return Profile(names, how, why, flags, rows, errors, focus, expr, scene)


# ---------- command line ----------
def _row_line(rid, cfg):
    m = cfg.get('mode', 'apply')
    nums = ', '.join(f'{k}={v}' for k, v in cfg.items() if k not in ('mode', 'reason', 'fallback'))
    return f'    {rid:22s} {m:5s} {nums}  - {cfg.get("reason", "")}'


def cmd_list():
    allp = presets.load('gate')
    for name in sorted(allp):
        p = allp[name]
        flags, rows, focus, _expr, _scene = _merge_profile(name, allp)
        print(f'{name}: {p.get("character", "")}   [{p.get("_source")}]')
        if p.get('extends'):
            print(f'  extends {p["extends"]}; flags {sorted(flags) or "-"}')
        print(f'  focus: {" / ".join(focus.get("roles") or rolelib.LEAD)}  ({focus.get("label", "-")})')
        for rid in sorted(rows):
            print(_row_line(rid, rows[rid]))


def cmd_rows():
    for rid, r in ROWS.items():
        ps = ', '.join(f'{k}={v[0]} ({v[1]}..{v[2]})' if len(v) == 3 and not isinstance(v[0], str) else f'{k}={"|".join(str(x) for x in v)}' for k, v in (r.get('params') or {}).items())
        print(f'{rid:22s} {"PROTECTED " if r.get("protected") else ""}{r["meaning"]}' + (f'  [{ps}]' if ps else ''))


def cmd_explain(score_path):
    score = json.load(open(score_path, encoding='utf-8'))
    p = resolve(score)
    for lv, name, d in p.notes():
        print(f'[{lv}] {name}: {d}')
    print(f'flags: {sorted(p.flags) or "-"}')
    print(f'focus: {" / ".join(p.focus_roles())}  ({p.focus_label()})')
    print('every row (final):')
    for rid in ROWS:
        cfg = dict(defaults(rid) if not ROWS[rid].get('protected') else {}, **p.rows.get(rid, {}))
        cfg.setdefault('mode', 'apply')
        print(_row_line(rid, cfg))


def _failing_measurements(project, rid):
    """Every FAIL/WARN line the last render wrote for `rid` (or its alias), from presets/gate/data/*.json: [(stem|None, value, unit, detail)]."""
    names = {rid} | {a for a, c in ALIASES.items() if c == rid}
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get('row') in names and o.get('level') in ('FAIL', 'WARN'):
                found.append((o.get('stem'), o.get('value'), o.get('unit'), str(o.get('detail', ''))[:160]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    d = data_dir(project)
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith('.json'):
            try:
                walk(json.load(open(os.path.join(d, f), encoding='utf-8')))
            except (OSError, ValueError):
                pass
    return found


def cmd_relax(row, project, sets, reason, profile=None):
    """Write a bounded relaxation into the project's own gate profile, only for a row the last render measured as failing.

    This is the route the profile exists for (AGENTS 6.3): a number inside the row's range, a reason, and the measurement that
    justifies it, recorded in the profile so the report lists it as `gate_relax`. It refuses a protected row, a value outside the
    range, a row that did not fail in the last render, and a reason of fewer than six words. It never skips a row."""
    if not (row and project and sets):
        print('usage: gate_profiles.py relax <row> --project <dir> --set PARAM=VALUE [--set ...] --reason "<why>"')
        return 2
    rid = canonical(row)
    if rid not in ROWS:
        print(f'unknown row "{row}". Rows: {", ".join(sorted(ROWS))}')
        return 2
    if ROWS[rid].get('protected'):
        print(f'"{rid}" is a protected row: no profile can relax it. Fix the audio.')
        return 1
    params = {}
    for item in sets:
        k, _, v = item.partition('=')
        spec = _pspec(rid, k)
        params[k] = (v.lower() == 'true') if spec is not None and isinstance(spec[0], bool) else (float(v) if v.replace('.', '', 1).replace('-', '', 1).isdigit() else v)
    if len(str(reason).split()) < 6:
        print('give a reason in a full sentence: what in this piece makes the default number wrong for it')
        return 1
    measured = _failing_measurements(project, rid)
    if not measured:
        print(f'"{rid}" did not fail in the last render recorded under {data_dir(project)}: relax a row only after a render measured it')
        return 1
    own = profile_files(project)
    name = profile or (own[0] if len(own) == 1 else None)
    if name is None or name not in own:
        print(f'name the profile with --profile; this project owns {own}')
        return 2
    path = os.path.join(artifacts_dir(project), name + '.json')
    doc = json.load(open(path, encoding='utf-8'))
    worst = ', '.join(f'{m[0] or "master"} {m[1]:.3g} {m[2] or ""}'.strip() if isinstance(m[1], (int, float)) else f'{m[0] or "master"}' for m in measured[:4])
    entry = dict(mode='relax', reason=f'{str(reason).strip()} Measured in the last render: {worst}.', **params)
    bad = row_problems({rid: entry}, name)
    if bad:
        print('\n'.join(bad))
        return 1
    doc.setdefault('rows', {})[rid] = entry
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write('\n')
    print(f'{name}: {rid} relaxed to {params} ({worst}); the report will list it as gate_relax')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['list', 'explain', 'new', 'check', 'rows', 'relax'])
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--project', default=None)
    ap.add_argument('--from', dest='from_name', default=None)
    ap.add_argument('--set', dest='sets', action='append', default=[], metavar='PARAM=VALUE', help='relax: a parameter of the row (repeatable)')
    ap.add_argument('--reason', default='', help='relax: why this piece needs it (the measurement is added from the last render)')
    ap.add_argument('--profile', default=None, help='relax: the project profile to edit (default: the only one)')
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    if a.cmd == 'list':
        cmd_list()
    elif a.cmd == 'rows':
        cmd_rows()
    elif a.cmd == 'explain':
        cmd_explain(a.arg)
    elif a.cmd == 'new':
        print('wrote', presets.scaffold('gate', a.arg, a.project or '.', a.from_name))
    elif a.cmd == 'relax':
        sys.exit(cmd_relax(a.arg, a.project, a.sets, a.reason, a.profile))
    elif a.cmd == 'check':
        bad = problems()
        print('\n'.join(bad) if bad else 'all gate profiles are valid')
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
