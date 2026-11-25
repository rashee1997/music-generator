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

"""schema.py - the `biome/1` preset, validated.

Same convention as phys_core/materials.SCHEMA: a table of (default, low, high, unit, what it does) per number, unknown
keys are errors, out-of-range values are refused and never clamped. `problems(preset)` returns plain sentences; empty
means the preset can be rendered. Every number that is not from a source carries the words "starting value" in its doc.

A number that may follow a slow curve is written {"control": "<name>"} and the name must exist in the preset's `controls`.
"""
import math

from biome import SCHEMA_ID, context
from phys_core import geometry, materials as mat_mod, medium as medium_mod

TOP_KEYS = ('schema', 'name', 'character', 'world', 'media', 'medium', 'interfaces', 'materials', 'controls', 'generators',
            'fauna', 'ecology', 'spatial_coupling', 'reference', 'sources', 'note', 'kind', '_source')   # kind and _source: what the preset loader writes
WORLD_KEYS = ('g_m_s2', 'day_length_s', 'listener')
SALIENCE = ('bed', 'foreground')
COMMON = ('name', 'kind', 'salience', 'gain_db', 'spatial', 'sources', 'note', 'medium', 'stationary')

# path -> (default, low, high, unit, doc)
NUMBERS = {
    'world.g_m_s2': (9.81, 0.01, 50.0, 'm/s2', 'surface gravity: sets how fast drops fall and how high a dune sings'),
    'obstacles.frontal_area_m2': (None, 1e-6, 1e6, 'm2', 'total frontal area of the obstacles that shed vortices (required)'),
    'obstacles.oscillators': (24, 1, 128, '-', 'tones used to stand for the obstacle sizes'),
    'obstacles.d_m.value': (None, 1e-5, 50.0, 'm', 'obstacle diameter, fixed'),
    'obstacles.d_m.median': (None, 1e-5, 50.0, 'm', 'median obstacle diameter, lognormal'),
    'obstacles.d_m.sigma': (0.5, 0.0, 3.0, '-', 'log-standard deviation of the diameters'),
    'flow.gust_corner_hz': (0.1, 0.005, 5.0, 'Hz', 'corner of the -5/3 gust spectrum'),
    'flow.intensity': (0.2, 0.0, 1.0, '-', 'gust standard deviation over the mean speed'),
    'turbulence.k_dipole': (1e-3, 0.0, 10.0, '-', 'Curle dipole constant (starting value)'),
    'turbulence.tone_jitter': (0.02, 0.0, 0.2, '-', 'random wander of each tone, as a fraction of its frequency (starting value)'),
    'broadband.share': (0.3, 0.0, 1.0, '-', 'share of the radiated power that is broadband rather than tonal (starting value)'),
    'population.d_mm': (None, 0.01, 30.0, 'mm', '[low, high] particle diameter'),
    'population.rho_particle': (998.0, 0.1, 30000.0, 'kg/m3', 'particle density'),
    'population.cd': (1.0, 0.05, 5.0, '-', 'drag coefficient of a falling particle (starting value; real drops deform)'),
    'population.lambda_per_mm': (None, 0.05, 50.0, '1/mm', 'size-distribution slope; default Marshall-Palmer from the rate'),
    'population.efficiency': (1e-8, 0.0, 1.0, '-', 'share of impact energy radiated as sound (starting value)'),
    'surface.area_m2': (None, 1e-4, 1e7, 'm2', 'area the particles land on'),
    'surface.patches': (1, 1, 32, '-', 'differently-pitched patches of one surface'),
    'surface.modes': (6, 1, 24, '-', 'modes per solid patch'),
    'surface.rho_kg_m3': (None, 0.1, 30000.0, 'kg/m3', 'density of a liquid surface (default: the particle density)'),
    'bubbles.radius_ratio': (0.2, 0.01, 1.0, '-', 'bubble radius over drop radius (starting value)'),
    'bubbles.energy_share': (0.5, 0.0, 1.0, '-', 'share of the radiated energy that goes into the bubble (starting value)'),
    'bubbles.t60_s': (0.01, 0.0005, 0.5, 's', 'bubble ring-down time (starting value)'),
    'modes.modes': (8, 1, 48, '-', 'modes of a modal object'),
    'modes.grain_size_m': (None, 1e-6, 0.05, 'm', 'dune grain diameter'),
    'modes.k': (0.4, 0.01, 5.0, '-', 'dune pitch constant (starting value)'),
    'modes.q': (30.0, 1.0, 1000.0, '-', 'quality factor of a grain-vibration mode (starting value)'),
    'excitation.energy_j': (1e-9, 0.0, 1e6, 'J', 'mean radiated energy of one excitation event (starting value)'),
    'excitation.sigma': (0.3, 0.0, 3.0, '-', 'log-standard deviation of the event strength'),
    'excitation.burst_shape': (0.5, 0.05, 50.0, '-', 'gamma shape of the burst rate: small = very bursty'),
    'excitation.q': (30.0, 1.0, 1000.0, '-', 'quality factor of the continuous resonators'),
}
KEYS = {
    'turbulence': COMMON + ('obstacles', 'flow', 'k_dipole', 'strouhal', 'broadband', 'tone_jitter'),
    'particulate_impacts': COMMON + ('population', 'surface', 'bubbles'),
    'modal_field': COMMON + ('modes', 'excitation'),
}
SUB = {
    'obstacles': ('d_m', 'frontal_area_m2', 'oscillators', 'shape'),
    'flow': ('u_m_s', 'gust_corner_hz', 'intensity'),
    'strouhal': ('law',),
    'broadband': ('share', 'band_hz'),
    'population': ('kind', 'rate_mm_h', 'd_mm', 'rho_particle', 'cd', 'lambda_per_mm', 'efficiency'),
    'surface': ('kind', 'material', 'geometry', 'modes', 'area_m2', 'patches', 'rho_kg_m3'),
    'bubbles': ('p_by_size', 'radius_ratio', 'energy_share', 't60_s'),
    'modes': ('material', 'geometry', 'modes', 'list', 'law', 'grain_size_m', 'k', 'q'),
    'excitation': ('kind', 'rate_hz', 'energy_j', 'sigma', 'burst_shape', 'level_pa', 'q'),
}
POP_KINDS = ('rain', 'hail', 'grain', 'dust')
SURFACE_KINDS = ('solid', 'liquid')
EXCITE_KINDS = ('poisson', 'granular', 'stress', 'continuous')
D_DISTS = ('fixed', 'lognormal')


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _check(path, v, out, where):
    spec = NUMBERS[path]
    if not _num(v):
        out.append(f'{where}: needs a number ({spec[3]}), got {v!r}')
    elif not spec[1] <= v <= spec[2]:
        out.append(f'{where}={v}: outside {spec[1]} to {spec[2]} {spec[3]}')


def _ref(v, controls, where, out, lo=None, hi=None):
    """A number, or {"control": name} naming a defined control."""
    if isinstance(v, dict):
        if set(v) != {'control'} or v['control'] not in (controls or {}):
            out.append(f'{where}: {{"control": name}} must name one of {sorted(controls or {}) or "none (the preset has no controls)"}')
    elif not _num(v):
        out.append(f'{where}: needs a number or {{"control": name}}, got {v!r}')
    elif (lo is not None and v < lo) or (hi is not None and v > hi):
        out.append(f'{where}={v}: outside {lo} to {hi}')


def _sub(cfg, key, where, out, required=True):
    blk = cfg.get(key)
    if blk is None:
        if required:
            out.append(f'{where}: needs a "{key}" block')
        return {}
    if not isinstance(blk, dict):
        out.append(f'{where}.{key}: an object')
        return {}
    out += [f'{where}.{key}: unknown key "{k}" (known: {", ".join(SUB[key])})' for k in blk if k not in SUB[key]]
    return blk


SPATIAL_KEYS = ('azimuth', 'elevation', 'elevations', 'distance', 'field', 'emitters', 'trajectory', 'binaural')


def spatial_problems(sp, where):
    if not isinstance(sp, dict):
        return [f'{where}.spatial: an object']
    out = [f'{where}.spatial: unknown key "{k}" (known: {", ".join(SPATIAL_KEYS)})' for k in sp if k not in SPATIAL_KEYS]
    for k, lo, hi in (('azimuth', -360, 360), ('elevation', -90, 90), ('distance', 0.1, 100000), ('emitters', 1, 64)):
        if k in sp and not (_num(sp[k]) and lo <= sp[k] <= hi):
            out.append(f'{where}.spatial.{k}: a number from {lo} to {hi}')
    if 'elevations' in sp and not (isinstance(sp['elevations'], list) and sp['elevations'] and all(_num(x) and -90 <= x <= 90 for x in sp['elevations'])):
        out.append(f'{where}.spatial.elevations: a list of elevations in degrees, -90 to 90')
    if 'field' in sp and not isinstance(sp['field'], bool):
        out.append(f'{where}.spatial.field: true or false')
    if sp.get('trajectory') is not None and not isinstance(sp['trajectory'], dict):
        out.append(f'{where}.spatial.trajectory: an object (keyframes or a mode, read by the spatial engine)')
    if 'emitters' in sp and not sp.get('field'):
        out.append(f'{where}.spatial.emitters: only a field has emitters (a point is one source)')
    return out


def generator_problems(cfg, controls=None, where='generator'):
    if not isinstance(cfg, dict):
        return [f'{where}: an object']
    name = cfg.get('name')
    where = f'{where} "{name}"' if name else where
    out = []
    kind = cfg.get('kind')
    if kind not in KEYS:
        return [f'{where}: unknown kind "{kind}" (known: {", ".join(sorted(KEYS))})']
    if not name or not isinstance(name, str):
        out.append(f'{where}: needs a "name" (it seeds the generator, so it must be stable)')
    out += [f'{where}: unknown key "{k}" for kind {kind} (known: {", ".join(KEYS[kind])})' for k in cfg if k not in KEYS[kind]]
    if cfg.get('salience', 'bed') not in SALIENCE:
        out.append(f'{where}.salience: one of {", ".join(SALIENCE)}')
    if 'spatial' in cfg:
        out += spatial_problems(cfg['spatial'], where)
    if 'stationary' in cfg and not isinstance(cfg['stationary'], bool):
        out.append(f'{where}.stationary: true or false (a bed that must hold its level and never loop; env.loop_stationarity measures it)')
    if 'gain_db' in cfg and not _num(cfg['gain_db']):
        out.append(f'{where}.gain_db: a number (a trim in dB on top of the physical level)')
    if kind == 'turbulence':
        ob = _sub(cfg, 'obstacles', where, out)
        if ob:
            if 'frontal_area_m2' not in ob:
                out.append(f'{where}.obstacles: needs frontal_area_m2')
            else:
                _check('obstacles.frontal_area_m2', ob['frontal_area_m2'], out, f'{where}.obstacles.frontal_area_m2')
            if 'oscillators' in ob:
                _check('obstacles.oscillators', ob['oscillators'], out, f'{where}.obstacles.oscillators')
            if ob.get('shape', 'cylinder') != 'cylinder':
                out.append(f'{where}.obstacles.shape: only "cylinder" is modelled (a plate or an edge needs its own Strouhal law and sources)')
            d = ob.get('d_m')
            if not isinstance(d, dict):
                out.append(f'{where}.obstacles.d_m: {{"dist": "fixed", "value"}} or {{"dist": "lognormal", "median", "sigma"}}')
            else:
                dist = d.get('dist', 'fixed')
                if dist not in D_DISTS:
                    out.append(f'{where}.obstacles.d_m.dist: one of {", ".join(D_DISTS)}')
                need = {'fixed': ('value',), 'lognormal': ('median',)}.get(dist, ())
                for k in need:
                    if k not in d:
                        out.append(f'{where}.obstacles.d_m: dist "{dist}" needs "{k}"')
                    else:
                        _check(f'obstacles.d_m.{k}', d[k], out, f'{where}.obstacles.d_m.{k}')
                if 'sigma' in d:
                    _check('obstacles.d_m.sigma', d['sigma'], out, f'{where}.obstacles.d_m.sigma')
                out += [f'{where}.obstacles.d_m: unknown key "{k}"' for k in d if k not in ('dist', 'value', 'median', 'sigma')]
        fl = _sub(cfg, 'flow', where, out)
        if fl:
            if 'u_m_s' not in fl:
                out.append(f'{where}.flow: needs u_m_s')
            else:
                _ref(fl['u_m_s'], controls, f'{where}.flow.u_m_s', out, 0.0, 400.0)
            for k in ('gust_corner_hz', 'intensity'):
                if k in fl:
                    _check(f'flow.{k}', fl[k], out, f'{where}.flow.{k}')
        for k in ('k_dipole', 'tone_jitter'):
            if k in cfg:
                _check(f'turbulence.{k}', cfg[k], out, f'{where}.{k}')
        st = _sub(cfg, 'strouhal', where, out, required=False)
        if st.get('law', 'auto') not in ('auto', 'roshko', 'williamson'):
            out.append(f'{where}.strouhal.law: one of auto, roshko, williamson')
        bb = _sub(cfg, 'broadband', where, out, required=False)
        if 'share' in bb:
            _check('broadband.share', bb['share'], out, f'{where}.broadband.share')
        if 'band_hz' in bb and not (isinstance(bb['band_hz'], list) and len(bb['band_hz']) == 2 and bb['band_hz'][0] < bb['band_hz'][1]
                                    and all(_num(x) and x > 0 for x in bb['band_hz'])):
            out.append(f'{where}.broadband.band_hz: [low, high] in Hz')
    elif kind == 'particulate_impacts':
        pop = _sub(cfg, 'population', where, out)
        if pop:
            if pop.get('kind') not in POP_KINDS:
                out.append(f'{where}.population.kind: one of {", ".join(POP_KINDS)}')
            if 'rate_mm_h' not in pop:
                out.append(f'{where}.population: needs rate_mm_h (volume of particles landing per hour, as mm of depth)')
            else:
                _ref(pop['rate_mm_h'], controls, f'{where}.population.rate_mm_h', out, 0.0, 2000.0)
            if 'd_mm' in pop:
                d = pop['d_mm']
                if not (isinstance(d, list) and len(d) == 2 and all(_num(x) for x in d) and d[0] < d[1]):
                    out.append(f'{where}.population.d_mm: [low, high] in mm')
                else:
                    for x in d:
                        _check('population.d_mm', x, out, f'{where}.population.d_mm')
            for k in ('rho_particle', 'cd', 'lambda_per_mm', 'efficiency'):
                if k in pop:
                    _check(f'population.{k}', pop[k], out, f'{where}.population.{k}')
        sf = _sub(cfg, 'surface', where, out)
        if sf:
            if sf.get('kind', 'solid') not in SURFACE_KINDS:
                out.append(f'{where}.surface.kind: one of {", ".join(SURFACE_KINDS)}')
            if 'area_m2' not in sf:
                out.append(f'{where}.surface: needs area_m2')
            for k in ('area_m2', 'patches', 'modes', 'rho_kg_m3'):
                if k in sf:
                    _check(f'surface.{k}', sf[k], out, f'{where}.surface.{k}')
            if sf.get('kind', 'solid') == 'solid':
                geo = sf.get('geometry')
                if geo is not None:
                    out += [f'{where}.surface.{p}' for p in geometry.problems(geo, 'geometry')]
            elif 'material' in sf or 'geometry' in sf:
                out.append(f'{where}.surface: a liquid surface has no material or geometry (its density is rho_kg_m3)')
        bb = _sub(cfg, 'bubbles', where, out, required=False)
        if bb:
            if sf.get('kind', 'solid') != 'liquid':
                out.append(f'{where}.bubbles: only a liquid surface entrains bubbles')
            tab = bb.get('p_by_size')
            if tab is not None and not (isinstance(tab, list) and tab and all(isinstance(p, list) and len(p) == 2 and _num(p[0]) and _num(p[1])
                                                                              and 0.0 <= p[1] <= 1.0 and p[0] > 0 for p in tab)
                                        and all(tab[i][0] < tab[i + 1][0] for i in range(len(tab) - 1))):
                out.append(f'{where}.bubbles.p_by_size: [[d_mm, probability 0..1], ...] with rising d_mm')
            for k in ('radius_ratio', 'energy_share', 't60_s'):
                if k in bb:
                    _check(f'bubbles.{k}', bb[k], out, f'{where}.bubbles.{k}')
    else:
        md = _sub(cfg, 'modes', where, out)
        if md:
            how = [k for k in ('list', 'law', 'material') if k in md]
            if len(how) != 1:
                out.append(f'{where}.modes: give exactly one of "list", "law" (grain_vibration) or "material" + "geometry"')
            elif how[0] == 'list':
                lst = md['list']
                if not (isinstance(lst, list) and lst and all(isinstance(p, list) and len(p) == 3 and all(_num(x) for x in p) and p[0] > 0 and p[1] > 0
                                                              for p in lst)):
                    out.append(f'{where}.modes.list: [[f_hz, t60_s, gain_db], ...]')
            elif how[0] == 'law':
                if md['law'] != 'grain_vibration':
                    out.append(f'{where}.modes.law: only "grain_vibration" (other shapes come from material + geometry)')
                elif 'grain_size_m' not in md:
                    out.append(f'{where}.modes: grain_vibration needs grain_size_m')
                else:
                    for k in ('grain_size_m', 'k', 'q'):
                        if k in md:
                            _check(f'modes.{k}', md[k], out, f'{where}.modes.{k}')
            else:
                if 'geometry' not in md:
                    out.append(f'{where}.modes: a material needs a geometry')
                else:
                    out += [f'{where}.modes.{p}' for p in geometry.problems(md['geometry'], 'geometry')]
                if 'modes' in md:
                    _check('modes.modes', md['modes'], out, f'{where}.modes.modes')
        ex = _sub(cfg, 'excitation', where, out)
        if ex:
            k = ex.get('kind')
            if k not in EXCITE_KINDS:
                out.append(f'{where}.excitation.kind: one of {", ".join(EXCITE_KINDS)}')
            elif k == 'continuous':
                if 'level_pa' not in ex:
                    out.append(f'{where}.excitation: continuous needs level_pa (rms pressure at 1 m)')
                else:
                    _ref(ex['level_pa'], controls, f'{where}.excitation.level_pa', out, 0.0, 1e4)
                if 'q' in ex:
                    _check('excitation.q', ex['q'], out, f'{where}.excitation.q')
            else:
                if 'rate_hz' not in ex:
                    out.append(f'{where}.excitation: {k} needs rate_hz')
                else:
                    _ref(ex['rate_hz'], controls, f'{where}.excitation.rate_hz', out, 0.0, 1e4)
                for key in ('energy_j', 'sigma', 'burst_shape'):
                    if key in ex:
                        _check(f'excitation.{key}', ex[key], out, f'{where}.excitation.{key}')
    return out


def problems(preset):
    """Every problem of a `biome/1` preset (a dict). Empty means it can be rendered."""
    if not isinstance(preset, dict):
        return ['a biome preset is an object (see biome/schema.py)']
    out = []
    if preset.get('schema') != SCHEMA_ID:
        out.append(f'schema: "{SCHEMA_ID}" expected, got {preset.get("schema")!r}')
    out += [f'unknown top-level key "{k}" (known: {", ".join(TOP_KEYS)})' for k in preset if k not in TOP_KEYS]
    if preset.get('kind', 'environments') != 'environments':
        out.append(f'kind: a biome is an environments preset, not "{preset["kind"]}"')
    if not preset.get('character') or not str(preset.get('character')).strip():
        out.append('character: one sentence on the place and why these parts')
    if 'medium' in preset and 'media' in preset:
        out.append('give "medium" or "media", not both')
    if 'medium' not in preset and 'media' not in preset:
        out.append('medium: a biome declares its medium (or "media" for several); there is no silent Earth default')
    media = preset.get('media') if 'media' in preset else {'air': preset.get('medium')} if 'medium' in preset else {}
    if not isinstance(media, dict):
        out.append('media: an object of named media')
        media = {}
    for n, m in media.items():
        out += medium_mod.problems(m, f'media.{n}')
    world = preset.get('world') or {}
    if not isinstance(world, dict):
        out.append('world: an object')
    else:
        out += [f'world: unknown key "{k}" (known: {", ".join(WORLD_KEYS)})' for k in world if k not in WORLD_KEYS]
        if 'g_m_s2' in world:
            _check('world.g_m_s2', world['g_m_s2'], out, 'world.g_m_s2')
        lm = (world.get('listener') or {}).get('medium')
        if lm is not None and lm not in media:
            out.append(f'world.listener.medium "{lm}" is not one of the media ({", ".join(sorted(media))})')
    mats = preset.get('materials') or {}
    if not isinstance(mats, dict):
        out.append('materials: an object of named materials')
        mats = {}
    for n, m in mats.items():
        out += mat_mod.problems(m, f'materials.{n}')
    controls = preset.get('controls')
    out += context.control_problems(controls)
    gens = preset.get('generators', [])
    if not isinstance(gens, list):
        out.append('generators: a list')
        gens = []
    if not gens and not preset.get('fauna'):
        out.append('a biome needs generators or fauna (or both): there is nothing to hear')
    names = set()
    for g in gens:
        out += generator_problems(g, controls)
        n = g.get('name') if isinstance(g, dict) else None
        if n in names:
            out.append(f'generator "{n}": the name is used twice (it seeds the generator)')
        names.add(n)
    for blk in ('fauna', 'ecology', 'spatial_coupling'):
        try:
            mod = __import__(f'biome.{blk}_schema', fromlist=['problems'])
        except ImportError:
            continue                                          # that part of the design lands in a later milestone
        if blk in preset:
            out += mod.problems(preset[blk], preset)
    if 'reference' in preset and not isinstance(preset['reference'], dict):
        out.append('reference: an object')
    return out
