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
"""mix_schema.py - the default value and the checking rule of every mix setting.

Three jobs:

  1. `DEFAULTS` names every knob the mixer knows, with the value the engine used before this file existed.
     A preset writes only what it changes; `with_defaults()` lays the defaults underneath.
  2. `validate(mix)` reports a key the engine would ignore, an out-of-range number or a wrong type, with
     the path of the problem. A render never guesses: an unknown key is reported, and the value is kept in
     the dict (so a newer preset is not silently rewritten) but never used.
  3. `role_chains` and `spectral.profiles` live here as starting points rather than inline in `mix_engine/`, so a
     project can replace them from JSON without touching code.

Nothing musical is decided here: these are the values the engine shipped with, restated so they can be
changed.
"""
import copy

import deep_merge
import json
import os


MASTER_TARGETS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'references', 'data',
                                   'master_targets.json')


def master_targets():
    """The mastering profiles and the one default, from references/data/master_targets.json.

    Returns {'default': {...}, 'profiles': {name: {...}}} with each entry's keys `lufs`, `true_peak`, `tone`, `glue`
    (the `source` note stays in the file). The numbers used to be compiled here and in three other modules.
    """
    with open(MASTER_TARGETS_PATH, encoding='utf-8') as f:
        doc = json.load(f)
    keep = ('lufs', 'true_peak', 'tone', 'glue')
    clean = lambda e: {k: v for k, v in e.items() if k in keep}
    return {'default': clean(doc['default']), 'profiles': {n: clean(e) for n, e in (doc.get('profiles') or {}).items()},
            'voiceover': {k: v for k, v in (doc.get('voiceover') or {}).items() if k != 'source'}}


def genre_lufs(genre):
    """The loudness a compose.py genre recipe asks for: references/data/master_targets.json `genres`, else the shipped default."""
    with open(MASTER_TARGETS_PATH, encoding='utf-8') as f:
        doc = json.load(f)
    g = (doc.get('genres') or {}).get(str(genre))
    return float(g) if g is not None else float(doc['default']['lufs'])


def _master_profiles():
    t = master_targets()
    return dict({'default': t['default']}, **t['profiles'])

EPS = 1e-9

# ---------------------------------------------------------------------------------------------
# The shipped defaults are DATA: references/data/mix_defaults.json (every number with its provenance). This file keeps the
# schema: the ranges, the enums and the validation. The loudness profiles of `mastering` come from master_targets.json.
# ---------------------------------------------------------------------------------------------

MIX_DEFAULTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'references', 'data', 'mix_defaults.json')


def _load_defaults():
    with open(MIX_DEFAULTS_PATH, encoding='utf-8') as f:
        doc = json.load(f)
    out = {k: v for k, v in doc.items() if not k.startswith('_')}
    out['mastering']['profiles'] = _master_profiles()
    return out


DEFAULTS = _load_defaults()
ROLE_CHAINS = DEFAULTS['role_chains']                       # kept under their old names: presets.py and setup_project.py copy them
SPECTRAL_PROFILES = DEFAULTS['spectral']['profiles']


# legacy mix-preset keys the engine reads directly (they are not in DEFAULTS because they are flat)
LEGACY_KEYS = {'lead_band_hz', 'carve_db', 'max_boost_db', 'active_db', 'lead_db_margin', 'inst_eq',
               'seating', 'level_by_role', 'widen_by_role', 'saturation', 'spatial', 'env_target_lufs',
               'immersive', 'name', 'character', 'note', '_source', 'role_chains', 'spectral_profiles'}

# (section, key) -> (kind, low, high) for every number with a meaningful range
RANGES = {
    ('gain_staging', 'ref_lufs'): ('db', -70.0, -1.0),
    ('gain_staging', 'max_boost_db'): ('num', 0.0, 30.0),
    ('gain_staging', 'max_cut_db'): ('num', 0.0, 60.0),
    ('gain_staging', 'block_s'): ('num', 0.05, 5.0),
    ('gain_staging', 'active_db'): ('db', -80.0, -20.0),
    ('gain_staging', 'peak_headroom_db'): ('db', -12.0, 0.0),
    ('gain_staging', 'crest_preserve_db'): ('num', 0.0, 40.0),
    ('gain_staging', 'sparse_active_frac'): ('num', 0.0, 1.0),
    ('dynamics', 'knee_db'): ('num', 0.0, 40.0),
    ('dynamics', 'lookahead_ms'): ('num', 0.0, 50.0),
    ('dynamics', 'parallel'): ('num', 0.0, 1.0),
    ('spectral', 'max_auto_cut_db'): ('num', 0.0, 24.0),
    ('render', 'oversample'): ('num', 1, 8),
    ('render', 'mix_worker_mb_per_second'): ('num', 0.1, 64.0),
    ('sidechain', 'residual'): ('num', 0.0, 1.0),
    ('sidechain', 'threshold'): ('num', 0.0, 1.0),
    # mixer.py applies the plateau fade only when 2 * fade < body; fade = body * frac, so frac must stay under 0.5
    # (0.5 itself yields no fade); 0.25 is the shipped starting value.
    ('sidechain', 'plateau_fade_frac'): ('num', 0.0, 0.5),
    ('lead_carve', 'ratio'): ('num', 1.0, 20.0),
    ('lead_carve', 'threshold_db'): ('db', -60.0, 0.0),
    ('lead_carve', 'attack_ms'): ('num', 0.0, 100.0),
    ('lead_carve', 'release_ms'): ('num', 5.0, 2000.0),
    ('lead_carve', 'mask_floor_db'): ('db', -24.0, 24.0),
    ('lead_carve', 'max_bands'): ('num', 1, 8),
    ('mastering', 'crest_floor_db'): ('num', 0.0, 30.0),
    ('mastering', 'true_peak_write_guard_db'): ('num', 0.0, 0.5),
    ('mastering', 'highpass_order'): ('num', 1.0, 6.0),
    ('immersive', 'max_elevation'): ('num', 0.0, 90.0),
    ('immersive', 'min_height_tracks'): ('num', 0.0, 24.0),
    ('immersive', 'order'): ('num', 1.0, 7.0),
    ('sympathetic_resonance', 'low_hz'): ('num', 27.5, 2000.0),
    ('sympathetic_resonance', 'strings'): ('num', 1.0, 24.0),
    ('sympathetic_resonance', 'partials'): ('num', 1.0, 8.0),
    ('sympathetic_resonance', 'q'): ('num', 5.0, 2000.0),
    ('sympathetic_resonance', 'level_db'): ('db', -60.0, -6.0),
    ('sympathetic_resonance', 'width'): ('num', 0.0, 1.0),
    ('immersive', 'anchor_max_span_deg'): ('num', 0.0, 45.0),
}

ENUMS = {
    ('gain_staging', 'strategy'): ('legacy', 'adaptive'),
    ('immersive', 'engine'): ('per_stem', 'hoa_bus'),
    ('immersive', 'stereo_decode'): ('binaural', 'speakers'),
    ('immersive', 'decoder'): ('allrad', 'allrad2'),
    ('dynamics', 'engine'): ('pedalboard', 'dsp'),
    ('dynamics', 'detector'): ('peak', 'rms'),
    ('sidechain', 'mode'): ('legacy', 'explicit', 'off'),
    ('lead_carve', 'mode'): ('bands', 'masking'),
    ('mastering', 'standard'): ('ebu_r128', 'atsc_a85', 'aes_td1008', 'spotify'),
    ('automation', 'curve'): ('linear', 'cosine', 'exponential'),
}
COMPUTE_DEVICES = ('auto', 'cpu', 'cuda', 'mps')

OPEN_SECTIONS = {'role_chains', 'spectral_profiles'}     # keyed by a name the project chooses
EQ_TYPES_OK = ('peak', 'bell', 'notch', 'hp', 'lp', 'lowshelf', 'highshelf')
BAND_KEYS_OK = {'type', 'f', 'freq', 'gain', 'q', 'bandwidth', 'load', 'order'}
# dynamics.dynamic_eq entries (read by mixer._dsp_dynamics -> dsp.dynamic_eq); `freq` is the alias _band() accepts
DYNAMIC_EQ_KEYS_OK = {'f', 'freq', 'q', 'threshold_db', 'ratio', 'attack_ms', 'release_ms', 'knee_db', 'gain_db'}
# dynamics.comp: the keys the engine reads and the values used for any the preset leaves out (starting values:
# a gentle 2.5:1 glue compressor, 15 ms / 150 ms, the figures the engine always used before they moved here).
COMP_KEYS_OK = ('thr', 'ratio', 'attack', 'release')
COMP_DEFAULTS = {'thr': -22, 'ratio': 2.5, 'attack': 15, 'release': 150}


def comp_params(comp):
    """One stem's compressor settings: `comp` (a dict) over COMP_DEFAULTS."""
    return _merge(COMP_DEFAULTS, comp)


def with_defaults(mix):
    """The preset laid over the schema defaults, without mutating either."""
    return deep_merge.merge(DEFAULTS, mix)


def _merge(base, over):
    """Delegates to the one merge in deep_merge.py."""
    return deep_merge.merge(base, over)


def section(mix, name):
    """One section of an already-resolved mix dict, with the defaults for that section."""
    got = (mix or {}).get(name) or {}
    return _merge(DEFAULTS.get(name, {}), got)


def validate(mix):
    """Problems with a mix preset: unknown keys, bad types, out-of-range numbers, malformed EQ bands.
    Returns a list of strings (empty = good). Never raises."""
    problems = []
    if not isinstance(mix, dict):
        return ['mix preset is not an object']
    for key in mix:
        if key not in DEFAULTS and key not in LEGACY_KEYS:
            problems.append(f'mix: unknown key "{key}" (the engine would ignore it); '
                            f'known sections: {", ".join(sorted(DEFAULTS))}')
    for sec, defaults in DEFAULTS.items():
        got = mix.get(sec)
        if not isinstance(got, dict) or sec in OPEN_SECTIONS:
            continue                       # role_chains is keyed by role name, which is open ended
        for key in got:
            if key not in defaults:
                problems.append(f'mix.{sec}.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(defaults))}')
    th = mix.get('theatrical')
    if isinstance(th, dict):
        for key in th:
            if key not in DEFAULTS['theatrical']:
                problems.append(f'mix.theatrical.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(DEFAULTS["theatrical"]))}')
        for part in ('low_mid', 'air', 'detail'):
            got_part = th.get(part)
            if isinstance(got_part, dict):
                for key in got_part:
                    if key not in DEFAULTS['theatrical'][part]:
                        problems.append(f'mix.theatrical.{part}.{key}: unknown key (the engine would ignore it); '
                                        f'known: {", ".join(sorted(DEFAULTS["theatrical"][part]))}')
    imm = mix.get('immersive')
    if isinstance(imm, dict) and isinstance(imm.get('hrtf'), dict):
        for key in imm['hrtf']:
            if key not in DEFAULTS['immersive']['hrtf']:
                problems.append(f'mix.immersive.hrtf.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(DEFAULTS["immersive"]["hrtf"]))}')
        ft = imm['hrtf'].get('f_trans_hz')
        if ft is not None and (not isinstance(ft, (int, float)) or isinstance(ft, bool)
                               or not 200.0 <= float(ft) <= 12000.0):
            problems.append(f'mix.immersive.hrtf.f_trans_hz: {ft} is outside 200..12000 Hz')
    if isinstance(imm, dict) and isinstance(imm.get('nfc'), dict):
        for key in imm['nfc']:
            if key not in DEFAULTS['immersive']['nfc']:
                problems.append(f'mix.immersive.nfc.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(DEFAULTS["immersive"]["nfc"]))}')
        for key, (lo, hi) in (('max_m', (0.2, 2.0)), ('ref_m', (0.2, 3.0)), ('max_gain_db', (0.0, 40.0))):
            v = imm['nfc'].get(key)
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool)
                                  or not lo <= float(v) <= hi):
                problems.append(f'mix.immersive.nfc.{key}: {v} is outside {lo}..{hi}')
    for (sec, key), (kind, lo, hi) in RANGES.items():
        val = (mix.get(sec) or {}).get(key) if isinstance(mix.get(sec), dict) else None
        if val is None:
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            problems.append(f'mix.{sec}.{key}: expected a number, got {type(val).__name__}')
        elif not (lo - EPS <= float(val) <= hi + EPS):
            problems.append(f'mix.{sec}.{key}: {val} is outside {lo}..{hi}')
    for (sec, key), allowed in ENUMS.items():
        val = (mix.get(sec) or {}).get(key) if isinstance(mix.get(sec), dict) else None
        if val is not None and val not in allowed:
            problems.append(f'mix.{sec}.{key}: "{val}" is not one of {", ".join(allowed)}')
    dyn = mix.get('dynamics') if isinstance(mix.get('dynamics'), dict) else {}
    cp = dyn.get('comp')
    if cp not in (None, False, 0):
        if not isinstance(cp, dict):
            problems.append('mix.dynamics.comp: expected an object {thr, ratio, attack, release} or false')
        else:
            for k, v in cp.items():
                if k not in COMP_KEYS_OK:
                    problems.append(f'mix.dynamics.comp.{k}: unknown key; known: {", ".join(COMP_KEYS_OK)}')
                elif not isinstance(v, (int, float)) or isinstance(v, bool):
                    problems.append(f'mix.dynamics.comp.{k}: expected a number, got {type(v).__name__}')
    deq = dyn.get('dynamic_eq')
    if deq is not None:
        if not isinstance(deq, list):
            problems.append('mix.dynamics.dynamic_eq: expected a list of bands')
        for i, b in enumerate(deq if isinstance(deq, list) else []):
            path = f'mix.dynamics.dynamic_eq[{i}]'
            if not isinstance(b, dict):
                problems.append(f'{path}: expected an object')
                continue
            problems += [f'{path}: unknown key "{k}" (known: {", ".join(sorted(DYNAMIC_EQ_KEYS_OK))})'
                         for k in b if k not in DYNAMIC_EQ_KEYS_OK]
            f = b.get('f', b.get('freq'))
            if f is None:
                problems.append(f'{path}: missing "f"')
            elif not isinstance(f, (int, float)) or not (10.0 <= float(f) <= 24000.0):
                problems.append(f'{path}.f: {f} is outside 10..24000 Hz')
    comp = (mix.get('render') or {}).get('compute') if isinstance(mix.get('render'), dict) else None
    if comp is not None:
        if not isinstance(comp, dict):
            problems.append('mix.render.compute: expected an object {device, workers}')
        else:
            for key in comp:
                if key not in ('device', 'workers'):
                    problems.append(f'mix.render.compute.{key}: unknown key; known: device, workers')
            if comp.get('device') is not None and comp['device'] not in COMPUTE_DEVICES:
                problems.append(f'mix.render.compute.device: "{comp["device"]}" is not one of {", ".join(COMPUTE_DEVICES)}')
    for name, bands in (((mix.get('mastering') or {}).get('tones') or {}).items()
                        if isinstance(mix.get('mastering'), dict) else ()):
        if not isinstance(bands, list):
            problems.append(f'mix.mastering.tones.{name}: expected a list of EQ bands')
            continue
        problems += _chain_problems(f'mix.mastering.tones.{name}', {'eq': bands})
    for sec in ('role_chains', 'spectral_profiles'):
        for name, chain in ((mix.get(sec) or {}) if isinstance(mix.get(sec), dict) else {}).items():
            problems += _chain_problems(f'mix.{sec}.{name}', chain)
    for prof, p in ((mix.get('mastering') or {}).get('profiles') or {}).items():
        if not isinstance(p, dict):
            problems.append(f'mix.mastering.profiles.{prof}: expected an object')
            continue
        if 'lufs' in p and not (-40.0 <= float(p['lufs']) <= 0.0):
            problems.append(f'mix.mastering.profiles.{prof}.lufs: {p["lufs"]} is outside -40..0')
        if 'true_peak' in p and not (-12.0 <= float(p['true_peak']) <= 0.0):
            problems.append(f'mix.mastering.profiles.{prof}.true_peak: {p["true_peak"]} is outside -12..0')
    return problems


def inert_dynamics(mix):
    """Dynamics keys a preset sets that the chosen engine never reads.

    With `engine: pedalboard` (the default) the compressor is the four-knob one (thr, ratio, attack, release); knee, detector,
    lookahead, makeup, parallel, sidechain filters, multiband, dynamic EQ and the transient shaper only run on
    `engine: dsp` (or on a stem that carries its own `dynamics`). A value that differs from the default under the
    pedalboard engine therefore changes nothing and says nothing: report it so the preset writer picks the engine.
    Returns [(key, value)], empty when the engine is dsp or every such key is at its default."""
    dyn = (mix or {}).get('dynamics')
    if not isinstance(dyn, dict) or str(dyn.get('engine', DEFAULTS['dynamics']['engine'])) != 'pedalboard':
        return []
    base = DEFAULTS['dynamics']
    return [(k, dyn[k]) for k in INERT_UNDER_PEDALBOARD if k in dyn and dyn[k] != base.get(k)]


INERT_UNDER_PEDALBOARD = ('knee_db', 'detector', 'stereo_link', 'lookahead_ms', 'makeup_db', 'parallel', 'multiband', 'dynamic_eq',
                          'transient', 'sidechain_hp_hz', 'sidechain_lp_hz')


def redundant_chains(mix):
    """Names of `role_chains` / `spectral.profiles` entries a preset repeats exactly as the schema ships them. A copy is not
    wrong, but it stops following the schema defaults: a later tuning there never reaches this preset. List only what differs."""
    out = []
    shipped = {'role_chains': ROLE_CHAINS, 'spectral.profiles': (DEFAULTS.get('spectral') or {}).get('profiles') or {}}
    got = {'role_chains': (mix or {}).get('role_chains') or {},
           'spectral.profiles': ((mix or {}).get('spectral') or {}).get('profiles') or {}}
    for sec, items in got.items():
        if isinstance(items, dict):
            out += [f'{sec}.{k}' for k, v in items.items() if shipped[sec].get(k) == v]
    return out


def _chain_problems(path, chain):
    out = []
    if not isinstance(chain, dict):
        return [f'{path}: expected an object with "eq" and/or "comp"']
    for key in chain:
        if key not in ('eq', 'comp', 'dynamics', 'gain_db'):
            out.append(f'{path}: unknown key "{key}" (known: eq, comp, dynamics, gain_db)')
    for i, band in enumerate(chain.get('eq') or []):
        out += _band_problems(f'{path}.eq[{i}]', band)
    return out


def _band_problems(path, band):
    if not isinstance(band, dict):
        return [f'{path}: expected an object']
    out = [f'{path}: unknown key "{k}" (known: {", ".join(sorted(BAND_KEYS_OK))})'
           for k in band if k not in BAND_KEYS_OK]
    if 'type' not in band:
        out.append(f'{path}: missing "type"')
    elif band['type'] not in EQ_TYPES_OK:
        out.append(f'{path}.type: "{band["type"]}" is not one of {", ".join(EQ_TYPES_OK)}')
    f = band.get('f', band.get('freq'))
    if f is None:
        out.append(f'{path}: missing "f"')
    elif not isinstance(f, (int, float)) or not (10.0 <= float(f) <= 24000.0):
        out.append(f'{path}.f: {f} is outside 10..24000 Hz')
    return out


