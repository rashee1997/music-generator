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

"""env_migrate.py - turn a legacy `layers` environment preset into a skeleton `biome/1` preset, and say what could not be carried.

    python scripts/env_migrate.py amazon_rainforest                 # the report
    python scripts/env_migrate.py amazon_rainforest --out bed.json  # and the skeleton

The layer engine and the biome engine are different physics (a layer is a recipe with a level relative to a normalised bed; a
generator is a mechanism whose pressure comes from the medium), so a migrated preset does NOT sound like the old one. What
this does is the bookkeeping: a layer that has a physical equivalent becomes a generator or an animal with its numbers carried
over where they mean the same thing; everything else is listed with the reason, so the person migrating decides, from the
research note, what the number should be. Every migrated block carries an `ESTIMATE:` source naming the layer it came from,
so `env.declaration` keeps asking until a measurement replaces it. A layer's `gain_db` is not carried: levels are physical now
(set `power_w` for an animal, `area_m2` and the rate for a surface).

    rain_physical     particulate_impacts (rate_mm_h; surface water -> a liquid with bubbles, leaf -> leaf_green, solid -> stone)
    noise_bed, resonant_gust   turbulence (a broadband bed in the layer's band; the wind speed is an ESTIMATE)
    cricket_chorus    an animal with the stridulation source (tooth rate from the syllables, rate_per_k from Dolbear's law)
    stridulation_bed  an animal with the stridulation source (tooth rate = the pulse rate, plate at the middle of the band)
    fm_chirp_cluster, bird_chorus   an animal with the dual_syrinx source (the layer's band becomes its niche)
    animal_call       an animal that starts from the same `calls` preset
    anything else     listed as not migrated, with what to write instead
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import environment
import presets
from biome import schema

AIR = {'model': 'iso9613', 'gas': {'molar_mass_kg_mol': 0.02897, 'gamma': 1.4, 'viscosity_pa_s': 1.81e-5, 'prandtl': 0.71},
       'state': {'temperature_k': 293.15, 'pressure_pa': 101325.0, 'rh_percent': 50.0},
       'sources': ['ISO 9613-1 for the absorption; viscosity and Prandtl number of air at about 20 C (handbook values)']}
REASON = {
    'impulse_cluster': 'drops, steps and clatter by an event rate with no surface: write a particulate_impacts generator (rate_mm_h, area_m2 and a material) from the place\'s research',
    'water_flow': 'a river or surf: write a particulate_impacts generator on a liquid surface with bubbles, or a modal_field, from the place\'s research',
    'formant_babble': 'a crowd: write animals with the glottal_chaos source and a tract, one per voice type',
    'doppler_sweep': 'a pass-by: an animal or source with a trajectory (spatial.trajectory) does this on the ambisonic bus',
    'voice_bouts': 'bouts of one voice: an animal with the glottal_chaos source and a tract',
    'syllable_bouts': 'swept syllables: an animal with the dual_syrinx source',
    'model_layer': 'a sound_model voice stack: keep the layers preset, or write the mechanism as a generator',
}
BLENDING_NOTE = 'blending ({keys}) is not carried: the mixer sets the level (role environment), and a notch or high-pass belongs in the mix preset'


def _spatial(lyr):
    sp = dict(lyr.get('spatial') or {})
    out = {}
    if 'azimuth' in sp:
        out['azimuth'] = float(sp['azimuth'])
    elif lyr.get('pan') is not None:
        out['azimuth'] = round(math.degrees(math.asin(max(-1.0, min(1.0, float(lyr['pan']))))), 1)
    for k in ('elevation', 'distance'):
        if k in sp:
            out[k] = float(sp[k])
    return out


def _est(layer, what):
    return [f'ESTIMATE: migrated from layer "{layer.get("name")}" ({layer.get("primitive") or layer.get("type")}); {what}']


def _generator(lyr, canon):
    name = str(lyr.get('name') or canon)
    sp = _spatial(lyr)
    if canon == 'rain_physical':
        surf = lyr.get('surface', 'water')
        g = dict(name=name, kind='particulate_impacts', salience='bed',
                 population=dict(kind='rain', rate_mm_h=float(lyr.get('rate_mm_h', 5.0)), cd=1.1),
                 surface=dict(kind='liquid', area_m2=20.0) if surf == 'water'
                 else dict(kind='solid', material='leaf_green' if surf == 'leaf' else 'stone', area_m2=20.0, patches=3),
                 spatial=dict(sp or {}, field=True, distance=sp.get('distance', 3.0)) if not sp.get('azimuth') else sp,
                 sources=_est(lyr, 'area_m2 20 and the drag coefficient are placeholders; the rate carries over'))
        if surf == 'water':
            p = float(lyr.get('bubble_prob', 0.35))
            g['bubbles'] = dict(p_by_size=[[0.5, p], [6.0, p]])
        return g, None
    if canon in ('noise_bed', 'resonant_gust'):
        lo = float(lyr.get('low_hz', 120.0)) if canon == 'noise_bed' else max(60.0, float(lyr.get('center_hz', 450.0)) * 0.5)
        hi = float(lyr.get('high_hz', 2600.0)) if canon == 'noise_bed' else float(lyr.get('center_hz', 450.0)) * 2.0
        g = dict(name=name, kind='turbulence', salience='bed', obstacles=dict(d_m=dict(dist='lognormal', median=0.004, sigma=0.5), frontal_area_m2=10.0, oscillators=8),
                 flow=dict(u_m_s=3.0, intensity=0.3, gust_corner_hz=float(lyr.get('mod_rate_hz', 0.1)) if 0.005 <= float(lyr.get('mod_rate_hz', 0.1)) <= 5 else 0.1),
                 broadband=dict(share=0.7, band_hz=[lo, min(hi, 20000.0)]),
                 spatial=dict(sp or {}, field=True, distance=sp.get('distance', 3.0)) if not sp.get('azimuth') else sp,
                 sources=_est(lyr, 'wind speed 3 m/s, obstacle sizes and frontal area are placeholders; the band carries over'))
        return g, None
    return None, 'no generator'


def _animal(lyr, canon, atmosphere):
    name = str(lyr.get('name') or canon)
    sp = _spatial(lyr)
    pos = dict(azimuth=sp.get('azimuth', 0.0), elevation=sp.get('elevation', 0.0), distance=sp.get('distance', 10.0))
    base = dict(name=name, salience='foreground' if canon in ('animal_call', 'fm_chirp_cluster', 'bird_chorus') else 'bed', position=pos)
    if canon == 'animal_call':
        a = dict(base, call=lyr.get('call'), power_w=1e-4, bouts_per_min=float(lyr.get('bouts_per_min', 4.0)), individuals=int(lyr.get('individuals', 1)),
                 sources=_est(lyr, 'power_w is a placeholder; the call preset, rate and number of animals carry over'))
        if not a['call']:
            return None, 'an animal_call layer with no `call` preset'
        return a, None
    if canon in ('fm_chirp_cluster', 'bird_chorus'):
        lo, hi = float(lyr.get('f0_low', lyr.get('f_lo', 1400.0))), float(lyr.get('f0_high', lyr.get('f_hi', 3800.0)))
        mid = (lo * hi) ** 0.5
        ms = [float(lyr.get('dur_low', 0.15)) * 1000.0, float(lyr.get('dur_high', 0.45)) * 1000.0]
        rate = float(lyr.get('event_rate', 0.5)) * (int(lyr.get('species', 1)) if canon == 'bird_chorus' else 1)
        return dict(base, power_w=1e-5, bouts_per_min=rate * 60.0, individuals=int(lyr.get('species', 2)) if canon == 'bird_chorus' else 2,
                    source=dict(kind='dual_syrinx', saturation=1.4, harmonics=3, fm_hz=float(lyr.get('mod_rate_hz', 24.0)), fm_depth=0.03),
                    elements=dict(call={'f_left': [[0, round(mid * 0.9)], [1, round(mid * 1.1)]], 'f_right': [[0, round(mid * 0.88)], [1, round(mid * 1.05)]], 'ms': ms}),
                    niche=dict(band_hz=[lo, hi]), resonator=dict(kind='tube', length_cm=4.5),
                    sources=_est(lyr, 'power_w and the pitch contour are placeholders; the band (as the niche), call lengths and rate carry over')), None
    if canon == 'cricket_chorus':
        t_c = float(atmosphere.get('temp_c', lyr.get('temp_c', 20.0)))
        t_f = t_c * 9.0 / 5.0 + 32.0
        syl, gap, n = float(lyr.get('syl_ms', 17.0)), float(lyr.get('gap_ms', 2.0)), int(lyr.get('syllables', 8))
        chirp = n * (syl + gap)
        return dict(base, power_w=1e-6, bouts_per_min=1.0, individuals=int(lyr.get('voices', 5)), rate_per_k=round(1.8 / max(t_f - 40.0, 1.0), 4),
                    temp_ref_k=round(t_c + 273.15, 2),
                    source=dict(kind='stridulation', tooth_hz=round(1000.0 / (syl + gap), 1), plate_hz=float(lyr.get('carrier_hz', 2300.0)), plate_q=60.0,
                                train=dict(chirp_ms=round(chirp, 1), period_ms=round(chirp * 1.6, 1))),
                    elements=dict(chorus=dict(ms=[3000, 5000])), niche=dict(band_hz=[float(lyr.get('carrier_hz', 2300.0)) * 0.9, float(lyr.get('carrier_hz', 2300.0)) * 1.1]),
                    sources=_est(lyr, "power_w is a placeholder; syllable timing, carrier, voices and Dolbear's rate with temperature carry over")), None
    if canon == 'stridulation_bed':
        lo, hi = float(lyr.get('low_hz', 5200.0)), float(lyr.get('high_hz', 8500.0))
        return dict(base, power_w=1e-6, bouts_per_min=2.0, individuals=6,
                    source=dict(kind='stridulation', tooth_hz=float(lyr.get('pulse_rate_hz', 11.5)), plate_hz=round((lo * hi) ** 0.5), plate_q=8.0),
                    elements=dict(chorus=dict(ms=[4000, 7000])), niche=dict(band_hz=[lo, hi]),
                    sources=_est(lyr, 'power_w is a placeholder; the pulse rate and the band carry over')), None
    return None, 'no animal'


def plan(cfg):
    """{biome, mapped, unmapped, notes}: the skeleton `biome/1` preset and the account of every layer."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get('layers'), list):
        raise ValueError('env_migrate takes a legacy preset with a "layers" list (a scene or an already migrated biome has nothing to migrate)')
    atmosphere = dict(cfg.get('atmosphere') or {})
    medium = json.loads(json.dumps(AIR))
    if atmosphere:
        medium['state']['temperature_k'] = float(atmosphere.get('temp_c', 20.0)) + 273.15
        medium['state']['rh_percent'] = float(atmosphere.get('rh', 50.0))
    generators, fauna, mapped, unmapped, notes = [], [], [], [], []
    for lyr in cfg['layers']:
        canon = environment.resolve_primitive(lyr)
        label = f'{lyr.get("name", canon)} ({canon})'
        if lyr.get('atmosphere'):
            notes.append(f'layer {lyr.get("name")}: its own atmosphere {lyr["atmosphere"]} is not carried; a biome has one medium')
        if canon is None:
            unmapped.append((label, f'unknown primitive "{lyr.get("primitive") or lyr.get("type")}"'))
            continue
        g, why = _generator(lyr, canon)
        if g is not None:
            generators.append(g)
            mapped.append((label, f'generator {g["name"]} ({g["kind"]})'))
            continue
        a, why = _animal(lyr, canon, atmosphere)
        if a is not None:
            fauna.append(a)
            mapped.append((label, f'animal {a["name"]}'))
            continue
        unmapped.append((label, why if why not in ('no generator', 'no animal') else REASON.get(canon, 'no physical equivalent yet')))
    if not generators and not fauna:
        raise ValueError('no layer of this preset has a physical equivalent: ' + '; '.join(f'{n}: {w}' for n, w in unmapped))
    extra = sorted((cfg.get('blending') or {}))
    if extra:
        notes.append(BLENDING_NOTE.format(keys=', '.join(extra)))
    notes.append('levels are physical now: a layer\'s gain_db is not carried; set power_w (animals) and area_m2 or the rate (surfaces)')
    biome = dict(schema='biome/1', name=str(cfg.get('name', 'migrated')),
                 character=f'{cfg.get("character") or cfg.get("description") or "a place"} (migrated skeleton: every ESTIMATE is to be replaced from the research note)',
                 medium=medium, generators=generators, sources=['Migrated by scripts/env_migrate.py; see each block for what carried over and what is a placeholder'])
    if fauna:
        biome['fauna'] = fauna
    bad = schema.problems(biome)
    if bad:
        raise ValueError('the skeleton does not validate (a bug in the migration): ' + '; '.join(bad))
    return dict(biome=biome, mapped=mapped, unmapped=unmapped, notes=notes)


def report(result):
    lines = [f'migrated: {len(result["mapped"])} layer(s)']
    lines += [f'  {a} -> {b}' for a, b in result['mapped']]
    lines += [f'not migrated: {len(result["unmapped"])} layer(s)'] if result['unmapped'] else []
    lines += [f'  {a}: {b}' for a, b in result['unmapped']]
    lines += ['notes:'] + [f'  {n}' for n in result['notes']]
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('preset', help='an environments preset name, or the path of a JSON file')
    ap.add_argument('--project', help='project folder whose presets/ are read as well')
    ap.add_argument('--out', help='write the skeleton biome/1 preset here')
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    cfg = json.load(open(a.preset, encoding='utf-8')) if os.path.isfile(a.preset) else presets.find_environment(a.preset)
    if cfg is None:
        ap.error(f'no environment preset "{a.preset}"')
    res = plan(cfg)
    print(report(res))
    if a.out:
        json.dump(res['biome'], open(a.out, 'w', encoding='utf-8'), indent=2)
        print(f'wrote {a.out}')


if __name__ == '__main__':
    main()
