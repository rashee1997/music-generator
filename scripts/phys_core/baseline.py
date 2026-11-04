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
"""baseline.py - freeze the current sound of the skill, then prove later that it changed or did not.

    python scripts/physical.py baseline            # write tests/artifacts/phys-core-baseline/manifest.json
    python scripts/physical.py verify              # re-render and compare: PASS / CHANGED / MISSING / NEW

Why this exists: every stage of the physical-sound upgrade changes synthesis, and the temptation is to eyeball a
render and call it fine. A hash says whether *any* sample moved, and the metrics say how much, which is the only
honest answer to "did Stage 2 change the falling rain that already worked?".

What is frozen: every shipped one-hit effect preset (`sfx:<name>`), every shipped environments preset (`env:<name>`)
and every worked model in references/data/sound-models/ (`model:<stem>`). Each is rendered at a fixed seed and length, so
run to run is byte-identical unless the code changed.

The manifest keeps a SHA-256 of the samples and a few level and spectrum numbers. WAVs are optional (--wav) and are
not needed for verification; they are for listening.
"""
import glob
import hashlib
import json
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
_SKILL = os.path.dirname(_SCRIPTS)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import phys_core.scene as scene_mod
import presets

SR = 44100
DEFAULT_DIR = os.path.join(_SKILL, 'tests', 'artifacts', 'phys-core-baseline')
SFX_SEED, ENV_SEED, MODEL_SEED = 7, 11, 3
SFX_SECONDS, ENV_SECONDS = 2.0, 6.0          # short enough to run often, long enough for the spectrum to mean something


def _digest(x):
    return hashlib.sha256(np.ascontiguousarray(np.asarray(x, dtype=np.float32)).tobytes()).hexdigest()


def _metrics(x, sr=SR):
    """Level and spectrum, measured the same way for every item. Never raises: a very short render keeps level only."""
    m = np.asarray(x, dtype=float)
    if m.ndim == 2:
        m = m.mean(axis=1)
    peak = float(np.abs(m).max()) if len(m) else 0.0
    rms = float(np.sqrt(np.mean(m ** 2))) if len(m) else 0.0
    out = dict(peak=round(peak, 6), rms_db=round(20 * math.log10(rms + 1e-12), 3), n=(int(m.shape[0]) if m.ndim else 0))
    try:
        import ambience_reference as ar
        meas = ar.measure_array(m, sr)
        out['centroid_hz'] = round(meas['centroid_hz'], 1)
        out['bands'] = {k: round(v, 4) for k, v in meas['bands'].items()}
    except Exception:                                     # too short to measure: level is still comparable
        pass
    return out


# ------------------------------------------------------------------------------------------------ targets
def _sfx_targets():
    out = []
    for name in sorted(presets.load('sfx')):
        cfg = presets.find_sfx(name) or {}
        secs = min(float(cfg.get('seconds', SFX_SECONDS) or SFX_SECONDS), SFX_SECONDS)
        out.append(dict(name=f'sfx:{name}', kind='sfx', seconds=secs, seed=SFX_SEED, preset=name))
    return out


def _env_targets():
    return [dict(name=f'env:{n}', kind='env', seconds=ENV_SECONDS, seed=ENV_SEED, preset=n)
            for n in sorted(presets.load('environments'))]


def _model_targets():
    out = []
    for path in sorted(glob.glob(os.path.join(_SKILL, 'references', 'data', 'sound-models', '*.json'))):
        stem = os.path.splitext(os.path.basename(path))[0]
        out.append(dict(name=f'model:{stem}', kind='model', seed=MODEL_SEED, path=path))
    return out


def targets():
    """Every frozen render: one-hit effects, environments, and the worked models."""
    return _sfx_targets() + _env_targets() + _model_targets()


def _select(all_targets, only):
    if not only:
        return all_targets
    picks = [str(o).strip().lower() for o in only if str(o).strip()]
    return [t for t in all_targets if any(p in t['name'].lower() for p in picks)]


# ------------------------------------------------------------------------------------------------ build
def build(target):
    """(audio, sr) for one target. Raises with the target name attached, so a broken preset is not a mystery."""
    try:
        if target['kind'] == 'sfx':
            import sfx
            x, _, _ = sfx.make(target['preset'], target['seconds'], SR, target['seed'])
            return np.asarray(x, dtype=np.float32), SR
        if target['kind'] == 'env':
            import environment
            return environment.render_environment_preset(target['preset'], duration_s=target['seconds'],
                                                        sr=SR, seed=target['seed']), SR
        doc = json.load(open(target['path'], encoding='utf-8'))
        model = doc.get('model', doc)
        return scene_mod.render_scene(model, SR, target['seed'])[0], SR
    except Exception as exc:
        raise RuntimeError(f'{target["name"]}: {exc}') from exc


# ------------------------------------------------------------------------------------------------ freeze / verify
def freeze(out_dir=DEFAULT_DIR, only=None, wav=False, quiet=False):
    """Render every selected target and write manifest.json (+ out_dir/wav/*.wav with wav=True). Returns the manifest."""
    os.makedirs(out_dir, exist_ok=True)
    sel = _select(targets(), only)
    if not sel:
        raise ValueError('no target matched --only; nothing to freeze')
    wav_dir = os.path.join(out_dir, 'wav')
    if wav:
        os.makedirs(wav_dir, exist_ok=True)
    items = {}
    for t in sel:
        x, sr = build(t)
        items[t['name']] = dict(kind=t['kind'], seed=t['seed'], seconds=t.get('seconds'), sha256=_digest(x), **_metrics(x, sr))
        if wav:
            import soundfile as sf
            sf.write(os.path.join(wav_dir, t['name'].replace(':', '_') + '.wav'), x, sr, subtype='FLOAT')
        if not quiet:
            print(f'  froze {t["name"]:34s} {items[t["name"]]["sha256"][:12]}  rms {items[t["name"]]["rms_db"]:7.2f} dB')
    manifest = dict(note='Frozen renders of the skill before the physical-sound upgrade. Regenerate only when a change '
                         'is meant to alter a sound, and say so in STATUS-phys-sound.md.',
                    sr=SR, items=items)
    path = os.path.join(out_dir, 'manifest.json')
    json.dump(manifest, open(path, 'w', encoding='utf-8'), indent=2, sort_keys=True)
    if not quiet:
        print(f'wrote {path} ({len(items)} renders)')
    return manifest


def verify(out_dir=DEFAULT_DIR, only=None, quiet=False):
    """Re-render the frozen targets and compare. Returns [(status, name, detail)] with status PASS/CHANGED/MISSING/NEW."""
    path = os.path.join(out_dir, 'manifest.json')
    if not os.path.isfile(path):
        raise FileNotFoundError(f'no baseline at {path}; run: python scripts/physical.py baseline')
    frozen = json.load(open(path, encoding='utf-8'))['items']
    by_name = {t['name']: t for t in targets()}
    # the scope is the union of both sides, so `--only` narrows the comparison instead of reporting every
    # unfiltered frozen item as missing
    scope = set(frozen) | set(by_name)
    if only:
        picks = [str(o).strip().lower() for o in only if str(o).strip()]
        scope = {n for n in scope if any(p in n.lower() for p in picks)}
    current = {}
    for name in sorted(scope):
        t = by_name.get(name)
        if t is None:
            continue
        try:
            x, sr = build(t)
        except RuntimeError as exc:
            current[name] = dict(error=str(exc))
            continue
        current[name] = dict(sha256=_digest(x), **_metrics(x, sr))
    rows = []
    for name in sorted(scope):
        if name not in current and name in frozen:
            rows.append(('MISSING', name, 'frozen but the preset or model is gone'))
        elif name not in frozen:
            rows.append(('NEW', name, 'not in the baseline (regenerate it to cover this)'))
        elif 'error' in current[name]:
            rows.append(('CHANGED', name, current[name]['error']))
        elif current[name]['sha256'] != frozen[name]['sha256']:
            rows.append(('CHANGED', name, _detail(frozen[name], current[name])))
        else:
            rows.append(('PASS', name, ''))
    if not quiet:
        for status, name, detail in rows:
            print(f'{status:8s} {name:34s} {detail}')
        bad = sum(1 for s, _, _ in rows if s != 'PASS')
        print(f'\n{len(rows) - bad}/{len(rows)} identical' + ('' if not bad else f', {bad} differ'))
    return rows


def _detail(old, new):
    bits = []
    for key, unit in (('rms_db', 'dB'), ('centroid_hz', 'Hz'), ('peak', '')):
        if key in old and key in new:
            d = float(new[key]) - float(old[key])
            if abs(d) > (0.01 if key == 'rms_db' else 1.0):
                bits.append(f'{key} {old[key]} -> {new[key]} ({d:+.2f} {unit})'.replace('  ', ' '))
    return '; '.join(bits) or 'samples differ, metrics within rounding'
