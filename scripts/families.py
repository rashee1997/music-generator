"""families.py - the instrument family of a track, and what that family does.

A preset says `"family": "bowed"`; the behaviour (bloom, noise layer, flare, snap, the programs an audit plays) is the
data in references/data/presets/families/families.json. The engine never branches on an instrument's name for these
behaviours. A preset with no `family` falls back to the legacy name lists in that same file, so nothing renders
differently until a preset declares one.
"""
import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'data', 'presets', 'families', 'families.json')
_CACHE = {}


def table():
    if 'doc' not in _CACHE:
        with open(DATA, encoding='utf-8') as fh:
            _CACHE['doc'] = json.load(fh)
    return _CACHE['doc']


def names():
    return list(table()['families'])


def _norm(name):
    return str(name or '').lower().strip().replace(' ', '_').replace('-', '_')


def family_of(inst_cfg=None, tr=None):
    """The declared family (track, then preset), else the legacy name list, else None. An unknown family is an error."""
    declared = (tr or {}).get('family') or (inst_cfg or {}).get('family')
    if declared:
        if declared not in table()['families']:
            raise ValueError(f'unknown family "{declared}"; known: {", ".join(names())}')
        return declared
    legacy = table()['legacy_names']
    for nm in ((inst_cfg or {}).get('instrument'), (tr or {}).get('instrument'), (inst_cfg or {}).get('name')):
        n = _norm(nm)
        for fam, members in legacy.items():
            if fam != 'note' and n and n in members:
                return fam
    return None


def behaviour(family):
    """The family's entry ({bloom, noise, flare, snap, velocity_brightness, velocity_attack, audit_programs}) or {} for no family."""
    return dict(table()['families'].get(family) or {})


def declared(inst_cfg=None, tr=None):
    """The family a preset or track DECLARES (never the legacy name guess), or None. Behaviour that changes a render only follows a declaration."""
    return ((tr or {}).get('family') or (inst_cfg or {}).get('family')) and family_of(inst_cfg, tr)


def effective(inst_cfg=None, tr=None):
    """The family's behaviour dict with the preset's and the track's own `bloom`, `noise`, `flare`, `snap`, `velocity_brightness`, `velocity_attack` blocks merged over it
    (a block set to null switches it off). {} when no family is declared and no block is given."""
    out = {}
    fam = declared(inst_cfg, tr)
    if fam:
        out = behaviour(fam)
        out.pop('audit_programs', None)
    for src in (inst_cfg or {}, tr or {}):
        for k in ('bloom', 'noise', 'flare', 'snap', 'velocity_brightness', 'velocity_attack'):
            if k in src:
                v = src[k]
                out[k] = None if v is None else dict(out.get(k) or {}, **v)
    return {k: v for k, v in out.items() if v}
