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
"""physical.py - one entry point for the physical sound engine (the orchestrator; the models live in phys_core/).

    python scripts/physical.py laws                          # every mechanism a scene may name
    python scripts/physical.py check  scene.json             # every problem, render nothing
    python scripts/physical.py render scene.json --out x.wav [--seed 1] [--seconds 3] [--stereo]
    python scripts/physical.py template --out scene.json     # a worked scene: a branch loaded, creaking, breaking, falling
    python scripts/physical.py bench  scene.json [--runs 3]  # wall-clock, and how much faster than real time
    python scripts/physical.py baseline [--only a,b] [--wav] # freeze today's renders as fixtures
    python scripts/physical.py verify   [--only a,b]         # re-render and prove nothing moved

`check` exits 1 on a problem, `verify` exits 1 on any changed sound. A scene is data: materials, objects, interactions
and propagation (phys_core/scene.py). There is no name-to-sound table and no fallback - an unknown field or interaction
is an error that names what is valid.
"""
import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import phys_core.baseline as baseline
import phys_core.registry as registry
import phys_core.scene as scene

TEMPLATE = {
    "seconds": 5.0,
    "note": "A branch loaded by wind: creaks, fails along the fibres, the limb falls and hits the ground, leaves and twigs settle.",
    "calibration": {"normalize": "energy", "level_db": -10},
    "materials": {
        "oak": {"family": "fibrous", "density": 700, "young_modulus_gpa": 11, "loss_factor": 0.015,
                "toughness_kpa": 900, "thickness_m": 0.03},
        "dry_leaf": {"family": "membrane", "density": 400, "young_modulus_gpa": 0.02, "loss_factor": 0.09,
                     "flow_resistivity": 12000, "thickness_m": 0.0002},
        "soil": {"family": "absorbent", "density": 1300, "young_modulus_gpa": 0.03, "loss_factor": 0.2,
                 "flow_resistivity": 90000}
    },
    "objects": {
        "limb": {"material": "oak", "geometry": {"shape": "bar", "length_m": 1.1, "thickness_m": 0.03}, "modes": 10},
        "ground": {"material": "soil", "geometry": {"shape": "plate", "width_m": 2.0, "thickness_m": 0.2}, "modes": 6},
        "leaves": {"material": "dry_leaf", "geometry": {"shape": "leaf", "width_m": 0.06, "thickness_m": 0.0002},
                   "modes": 5}
    },
    "timeline": [
        {"at": 0.0, "for": 2.6, "interaction": "creak", "target": "limb", "strain": 0.009, "rate_hz": 3.0},
        {"at": 2.6, "interaction": "fracture", "target": "limb", "mass_kg": 1.6, "velocity_m_s": 2.2,
         "then": [
             {"offset": 0.35, "interaction": "impact", "target": "ground", "mass_kg": 1.6, "velocity_m_s": 3.1},
             {"offset": 0.38, "interaction": "foliage", "target": "leaves", "speed_m_s": 2.5, "for": 1.2,
              "leaf_count": 900}
         ]}
    ],
    "propagation": {"distance_m": 9.0, "atmosphere": {"temp_c": 16, "rh": 75}, "canopy_density": 0.2},
    "spatial": {"azimuth": -18}
}


def _load(path):
    if not os.path.isfile(path):
        sys.exit(f'no such scene file: {path}')
    doc = json.load(open(path, encoding='utf-8'))
    for key in ('scene', 'model'):                 # {"scene": ..}, a references/data/sound-models file, or a bare scene
        if isinstance(doc.get(key), dict):
            return doc[key]
    return doc


def cmd_check(a):
    bad = scene.problems(_load(a.file))
    if bad:
        print('\n'.join(bad))
        return 1
    print(f'ok: {a.file} is a valid scene')
    return 0


def cmd_render(a):
    s = _load(a.file)
    bad = scene.problems(s)
    if bad:
        print('\n'.join(bad))
        return 1
    import numpy as np
    import soundfile as sf
    if a.stereo:
        x, report = scene.render_stereo(s, a.sr, a.seed, a.seconds)
    else:
        x, report = scene.render_scene(s, a.sr, a.seed, a.seconds)
    x = np.asarray(x)
    out = a.out or os.path.splitext(a.file)[0] + '.wav'
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    sf.write(out, x.astype(np.float32), a.sr, subtype='FLOAT')
    peak = float(np.abs(x).max()) if x.size else 0.0
    print(f'wrote {out}  ({len(x) / a.sr:.2f} s, peak {peak:.3f}, seed {a.seed})')
    print('  engine ' + str(report.get('engine')) +
          (f", normalize {report.get('normalize')}, {report.get('rms_db')} dBFS" if 'normalize' in report else ''))
    return 0


def cmd_laws(a):
    print(scene.describe())
    print()
    print(registry.describe())
    bad = registry.problems()
    if bad:
        print('\nregistry problems:')
        print('\n'.join('  ' + b for b in bad))
    return 1 if bad else 0


def cmd_template(a):
    path = a.out or 'scene.json'
    if os.path.exists(path) and not a.force:
        sys.exit(f'{path} exists; pass --force to overwrite')
    json.dump(TEMPLATE, open(path, 'w', encoding='utf-8'), indent=2)
    print(f'wrote {path} - check it with: physical.py check {path}')
    return 0


def cmd_bench(a):
    s = _load(a.file)
    bad = scene.problems(s)
    if bad:
        print('\n'.join(bad))
        return 1
    secs = float(a.seconds or s.get('seconds', 1.0))
    times = []
    for _ in range(max(1, a.runs)):
        t0 = time.perf_counter()
        x, _ = scene.render_scene(s, a.sr, a.seed, secs)
        times.append(time.perf_counter() - t0)
    best = min(times)
    print(f'{a.file}: {secs:.1f} s of audio rendered in {best:.2f} s ({secs / best:.1f}x real time, best of {len(times)}), '
          f'{a.sr} Hz, {len(x)} samples')
    return 0


def cmd_baseline(a):
    manifest = baseline.freeze(a.dir, only=a.only.split(',') if a.only else None, wav=a.wav)
    print(f'{len(manifest["items"])} renders frozen - run `physical.py verify` after a change to compare')
    return 0


def cmd_verify(a):
    rows = baseline.verify(a.dir, only=a.only.split(',') if a.only else None)
    return 0 if all(s in ('PASS', 'NEW') for s, _, _ in rows) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['check', 'render', 'laws', 'template', 'bench', 'baseline', 'verify'])
    ap.add_argument('file', nargs='?', help='scene JSON for check/render/bench')
    ap.add_argument('--out', default=None, help='render/template: output path')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--seconds', type=float, default=None, help='override the scene length')
    ap.add_argument('--sr', type=int, default=44100)
    ap.add_argument('--stereo', action='store_true', help='render: place by spatial.azimuth into 2 channels')
    ap.add_argument('--project', default=None, help='read presets/ of this project before the skill defaults')
    ap.add_argument('--dir', default=baseline.DEFAULT_DIR, help='baseline/verify: where the manifest lives')
    ap.add_argument('--only', default=None, help='baseline/verify: comma-separated name fragments')
    ap.add_argument('--wav', action='store_true', help='baseline: also write WAVs for listening')
    ap.add_argument('--runs', type=int, default=3, help='bench: how many renders to time')
    ap.add_argument('--force', action='store_true', help='template: overwrite an existing file')
    a = ap.parse_args()
    if a.project:
        import presets
        presets.add_project(a.project)
    if a.cmd in ('check', 'render', 'bench') and not a.file:
        ap.error('give a scene JSON file')
    return {'check': cmd_check, 'render': cmd_render, 'laws': cmd_laws, 'template': cmd_template,
            'bench': cmd_bench, 'baseline': cmd_baseline, 'verify': cmd_verify}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
