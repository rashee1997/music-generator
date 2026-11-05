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

"""Vocal config: defaults, migration of the old flat keys and the old nested preset keys, validation, ranges.

A vocal preset / track `vocal` block may use any mix of:
  * legacy flat keys   voices spread_cents pan_width attack release breath vib_cents vib_hz vib_delay formants
                       bandwidths formant_scale style vowel hum        (attack/release in seconds, as before)
  * the old nested preset keys  formant_profile{vowel,F1_hz..}  articulation{attack_ms, decay_ms, vib_cents, ...}
  * the new sections   source tract humming articulation performance vibrato dynamics breathing ensemble dsp
  * shortcuts          expression (name or dict), expression_intensity, styles (extra style profiles)
Later wins: defaults < hum adjustments < function arguments < flat keys < sections. Nothing raises: problems come
back as warnings and bad numbers are clamped into data `ranges`.
"""
import copy

from . import data, expression

SECTIONS = ('source', 'tract', 'technique', 'consonants', 'humming', 'articulation', 'performance', 'vibrato',
            'dynamics', 'breathing', 'phrasing', 'ensemble', 'dsp', 'singer_variation')
IGNORED = {'name', 'description', 'character', 'category', 'phonetic_sound', 'register_range', 'role', 'synthesis',
           'spatial', 'gain_db', 'reverb', 'eq', 'pan', 'sends', 'kind', '_source', '_about', 'humanize', 'gm',
           'instrument', 'seating', 'width_ms', 'widen', 'mix',
           # mixer routing, read by mixer.py from this same file (a vocal is a track like any other):
           # duck_by / duck_db pump it under a kick, and the timing keys set that pump's envelope
           'duck_by', 'duck_db', 'attack_ms', 'release_ms', 'smooth_s', 'mono_below', 'duck_full_band',
           'duck_band_hz', 'chain', 'comp', 'hp', 'lp', 'spectral_profile', 'fade_in_s', 'fade_out_s'}
_OLD_ARTIC = {'vib_cents': ('vibrato', 'depth_cents', 1.0), 'vib_hz': ('vibrato', 'rate_hz', 1.0),
              'tremolo_rate_hz': ('vibrato', 'rate_hz', 1.0), 'tremolo_depth_cents': ('vibrato', 'depth_cents', 1.0)}
_OLD_ARTIC_IGNORED = {'decay_ms', 'sustain_level'}


def _put(cfg, path, value):
    ks = path.split('.')
    d = cfg
    for k in ks[:-1]:
        d = d[k]
    d[ks[-1]] = value


def _get(cfg, path):
    d = cfg
    for k in path.split('.'):
        d = d[k]
    return d


def _flat(cfg, key, v, warn):
    """One legacy flat key -> cfg."""
    if key == 'voices':
        cfg['ensemble']['voices'] = int(v)
    elif key == 'spread_cents':
        cfg['ensemble']['pitch_spread_cents'] = float(v)
    elif key == 'pan_width':
        cfg['ensemble']['pan_width'] = float(v)
    elif key == 'attack':
        cfg['articulation']['attack_ms'] = float(v) * 1000.0
    elif key == 'release':
        cfg['articulation']['release_ms'] = float(v) * 1000.0
    elif key == 'breath':
        cfg['source']['breathiness'] = float(v)
    elif key == 'vib_cents':
        cfg['vibrato']['depth_cents'] = float(v)
    elif key == 'vib_hz':
        cfg['vibrato']['rate_hz'] = float(v)
    elif key == 'vib_delay':
        cfg['vibrato']['delay_s'] = float(v)
    elif key == 'formants':
        cfg['tract']['formants'] = [float(x) for x in v]
    elif key == 'bandwidths':
        cfg['tract']['bandwidths'] = [float(x) for x in v]
    elif key == 'formant_scale':
        cfg['tract']['formant_scale'] = float(cfg['tract']['formant_scale']) * float(v)
    elif key in ('style', 'vowel'):
        cfg[key] = v
    elif key == 'hum':
        cfg['hum'] = bool(v)
    elif key == 'expression':
        pass                                                 # applied in resolve(), under the explicit values
    elif key == 'expression_intensity':
        pass
    elif key == 'styles':
        cfg['styles'] = copy.deepcopy(v)
    elif key == 'seed':
        pass
    elif key == 'peak_trim':                                 # opt-in: cap a hot ensemble sum before the limiter
        cfg['peak_trim'] = float(v)
    elif key not in IGNORED:
        warn.append(f'unknown vocal key "{key}" ignored')


def _nested_old(cfg, config, warn):
    """formant_profile and the old articulation block of the shipped presets."""
    fp = config.get('formant_profile')
    if isinstance(fp, dict):
        F = [fp.get(f'F{i}_hz') for i in (1, 2, 3)]
        if all(isinstance(x, (int, float)) for x in F):
            cfg['tract']['formants'] = [float(x) for x in F]
        v = fp.get('vowel')
        if isinstance(v, str):
            cfg['vowel'] = v if v in cfg['tract']['vowels'] else cfg.get('vowel')
    art = config.get('articulation')
    if isinstance(art, dict):
        for k, v in art.items():
            if k in _OLD_ARTIC:
                sec, key, mul = _OLD_ARTIC[k]
                cfg[sec][key] = float(v) * mul
                if k.startswith('tremolo'):
                    cfg['vibrato']['delay_s'] = 0.05
                    cfg['vibrato']['onset_s'] = 0.1
            elif k in _OLD_ARTIC_IGNORED:
                pass                       # accepted and ignored: a legacy preset keeps loading silently


def resolve(config=None, voices=None, spread_cents=None, pan_width=None, vowel=None, formant_scale=None, hum=False):
    """-> (cfg, warnings). cfg is a complete config for ensemble.render."""
    config = config or {}
    warn = []
    cfg = data.defaults()
    hum = bool(hum or config.get('hum'))
    if hum:                                                  # hum defaults first, so expression and the preset can override them
        cfg['hum'] = True
        cfg['vibrato']['depth_cents'] = cfg['humming']['vibrato_cents']
        cfg['source']['breathiness'] = cfg['humming']['breathiness']
    for key, v in (('voices', voices), ('spread_cents', spread_cents), ('pan_width', pan_width),
                   ('formant_scale', formant_scale)):
        if v is not None:
            _flat(cfg, key, v, warn)
    if vowel is not None:
        cfg['vowel'] = vowel
    ex = config.get('expression') or (config.get('ensemble') or {}).get('expression')
    if ex:                                                   # expression sits under the preset's own explicit values
        w = config.get('expression_intensity', (config.get('ensemble') or {}).get('expression_intensity', 1.0))
        try:
            cfg = expression.apply(cfg, ex, w)
            cfg['ensemble']['expression'] = ex if isinstance(ex, str) else ''
            cfg['ensemble']['expression_intensity'] = float(w)
            cfg['_expression_applied'] = True
        except KeyError as e:
            warn.append(str(e.args[0]))
    _nested_old(cfg, config, warn)
    for key, v in config.items():
        if key in SECTIONS or key in ('formant_profile',):
            continue
        if key == 'articulation' or v is None:        # null in JSON = unset
            continue
        _flat(cfg, key, v, warn)
    for sec in SECTIONS:
        if isinstance(config.get(sec), (dict, list)):
            if sec == 'articulation':
                v = {k: x for k, x in config[sec].items() if k not in _OLD_ARTIC and k not in _OLD_ARTIC_IGNORED}
                cfg[sec] = data.deep_merge(cfg[sec], v)
            elif sec == 'singer_variation':
                cfg[sec] = copy.deepcopy(config[sec])
            else:
                cfg[sec] = data.deep_merge(cfg[sec], config[sec])
    warn += clamp(cfg)
    warn += check(cfg)
    return cfg, warn


def clamp(cfg):
    out = []
    for path, (lo, hi) in cfg['ranges'].items():
        try:
            v = _get(cfg, path)
        except (KeyError, TypeError):
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not (lo <= v <= hi):
            _put(cfg, path, min(max(v, lo), hi))
            out.append(f'{path}={v} is outside [{lo}, {hi}]; clamped to {_get(cfg, path)}')
    cfg['ensemble']['voices'] = int(cfg['ensemble']['voices'])
    return out


def check(cfg):
    """Non-numeric problems: unknown register / style / expression, bad formant lists."""
    out = []
    st = data.deep_merge(data.styles(), cfg.get('styles') or {})
    s = cfg.get('style')
    if s and s not in st:
        out.append(f'unknown style "{s}"; known: {sorted(st)}')
    for sec in ('source', 'humming'):
        r = cfg[sec]['register']
        if r not in cfg['source']['registers']:
            out.append(f'{sec}.register "{r}" is not one of {sorted(cfg["source"]["registers"])}')
    ex = cfg['ensemble'].get('expression')
    if isinstance(ex, str) and ex and ex not in expression.names():
        out.append(f'unknown expression "{ex}"; known: {expression.names()}')
    for k in ('formants', 'bandwidths'):
        v = cfg['tract'].get(k)
        if v is not None and (not isinstance(v, list) or not v or any(x <= 0 for x in v)):
            out.append(f'tract.{k} must be a list of positive numbers')
    for k in ('gains', 'bandwidths'):
        v = cfg['tract'].get(k)
        if isinstance(v, list) and any(len(F) > len(v) for F in cfg['tract']['vowels'].values()):
            out.append(f'tract.{k} is shorter than a vowel: the bank is sliced to {len(v)} formants')
    for name, tgt in (cfg['tract'].get('cover_map') or {}).items():
        if name.startswith('_'):
            continue
        if name not in cfg['tract']['vowels']:
            out.append(f'tract.cover_map."{name}" is not a vowel; known: {sorted(cfg["tract"]["vowels"])}')
        elif tgt not in cfg['tract']['vowels']:
            out.append(f'tract.cover_map."{name}" -> "{tgt}" is not a vowel')
    ring = cfg['tract'].get('ring') or {}
    if ring.get('enabled', True) and (len(ring.get('target_hz') or []) != 3 or len(ring.get('shares') or []) != 3):
        out.append('tract.ring needs three target_hz and three shares (F3, F4, F5)')
    ladder = cfg['source'].get('register_ladder') or []
    for r in ladder:
        if r not in cfg['source']['registers']:
            out.append(f'source.register_ladder "{r}" is not one of {sorted(cfg["source"]["registers"])}')
    inv = (cfg.get('consonants') or {}).get('inventory') or {}
    for c in ((cfg.get('consonants') or {}).get('onsets') or []):
        if c not in inv:
            out.append(f'consonants.onsets "{c}" is not in consonants.inventory; known: {sorted(K for K in inv if not K.startswith("_"))}')
    if cfg.get('vowel') and cfg['vowel'] not in cfg['tract']['vowels'] and not isinstance(cfg['vowel'], (list, tuple)):
        out.append(f'unknown vowel "{cfg["vowel"]}"; known: {sorted(cfg["tract"]["vowels"])}')
    table = (cfg.get('phrasing') or {}).get('contours')
    if not isinstance(table, dict) or not table:
        out.append('phrasing.contours must be a non-empty object of named phrase contours')
    else:
        for name, c in table.items():
            pts = c.get('points') if isinstance(c, dict) else None
            if not isinstance(pts, list) or len(pts) < 2:
                out.append(f'phrasing.contours.{name}.points must be at least two [position, level] pairs')
                continue
            bad = [p for p in pts if not (isinstance(p, (list, tuple)) and len(p) == 2
                                          and all(isinstance(x, (int, float)) for x in p))]
            if bad:
                out.append(f'phrasing.contours.{name}.points: each point is [position 0..1, level {bad[0]!r}]')
            if not isinstance(c.get('weight', 0), (int, float)) or float(c.get('weight', 0)) <= 0:
                out.append(f'phrasing.contours.{name}.weight must be a positive number')
    for sec, keys in (('expression_bias', ('contours', 'depth', 'timing', 'vibrato', 'amount')),
                      ('role_profiles', ('amount', 'depth', 'timing', 'vibrato'))):
        profs = (cfg.get('phrasing') or {}).get(sec)
        if profs is None:
            continue
        if not isinstance(profs, dict):
            out.append(f'phrasing.{sec} must be an object')
            continue
        for pname, prof in profs.items():
            if not isinstance(prof, dict):
                out.append(f'phrasing.{sec}.{pname} must be an object')
                continue
            for k in prof:
                if k not in keys:
                    out.append(f'phrasing.{sec}.{pname}.{k} is not one of {sorted(keys)}')
                elif k == 'contours':
                    for cn in prof[k]:
                        if cn not in table:
                            out.append(f'phrasing.{sec}.{pname}.contours."{cn}" is not a defined contour')
    return out


def validate(config):
    """Problems in a preset's vocal config (for presets.validate / project_gate). [] = good."""
    _, w = resolve(config)
    return w
