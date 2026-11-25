"""Frozen renders of every shipped environment and every shipped `calls` preset (Immersive 3.3, milestone M0).

    python tests/biome_baseline.py --freeze      # (re)write tests/artifacts/biome-baseline/manifest.json
    python tests/biome_baseline.py --verify      # compare the current engine with it

Each target is rendered at a fixed seed and length. The manifest keeps a SHA-256 of the float32 samples and a few
level/spectrum numbers, so a later change can say "the Earth presets are byte-identical" (same hash) or "within
rounding" (metrics inside the tolerances below, for a platform whose float arithmetic differs). Regenerate only when a
change is meant to alter a sound, and say so in the commit.
"""
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

SR = 44100
ENV_SECONDS, ENV_SEED = 6.0, 11
CALL_SECONDS, CALL_SEED = 8.0, 11
DIR = os.path.join(ROOT, 'tests', 'artifacts', 'biome-baseline')
TOL = dict(rms_db=0.05, centroid_rel=0.01)


def _digest(x):
    return hashlib.sha256(np.ascontiguousarray(np.asarray(x, dtype=np.float32)).tobytes()).hexdigest()


def _metrics(x):
    m = np.asarray(x, dtype=np.float64)
    m = m.mean(axis=1) if m.ndim == 2 else m
    rms = float(np.sqrt(np.mean(m ** 2)))
    spec = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    f = np.fft.rfftfreq(len(m), 1.0 / SR)
    return dict(rms_db=round(20 * np.log10(rms + 1e-12), 3), centroid_hz=round(float((f * spec).sum() / (spec.sum() + 1e-30)), 1),
                shape=list(np.asarray(x).shape))


def targets():
    import presets
    out = [dict(name=f'env:{n}', kind='env', preset=n) for n in sorted(presets.load('environments'))]
    out += [dict(name=f'call:{n}', kind='call', preset=n) for n in sorted(presets.load('calls'))]
    return out


def build(t):
    import environment
    if t['kind'] == 'env':
        return environment.render_environment_preset(t['preset'], duration_s=ENV_SECONDS, sr=SR, seed=ENV_SEED)
    cfg = dict(layers=[dict(name=t['preset'], primitive='animal_call', call=t['preset'], gain_db=-12.0, first_s=0.5)])
    return environment.render_environment_preset(cfg, duration_s=CALL_SECONDS, sr=SR, seed=CALL_SEED)


def freeze(path=None):
    path = path or os.path.join(DIR, 'manifest.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    items = {}
    for t in targets():
        x = build(t)
        items[t['name']] = dict(sha256=_digest(x), **_metrics(x))
    json.dump(dict(sr=SR, items=items), open(path, 'w', encoding='utf-8'), indent=2, sort_keys=True)
    return items


def verify(path=None):
    """[(status, name, detail)]: PASS (same hash), CLOSE (metrics inside tolerance), CHANGED, MISSING, NEW."""
    path = path or os.path.join(DIR, 'manifest.json')
    frozen = json.load(open(path, encoding='utf-8'))['items']
    rows, seen = [], set()
    for t in targets():
        seen.add(t['name'])
        old = frozen.get(t['name'])
        if old is None:
            rows.append(('NEW', t['name'], 'not in the baseline'))
            continue
        x = build(t)
        new = dict(sha256=_digest(x), **_metrics(x))
        if new['sha256'] == old['sha256']:
            rows.append(('PASS', t['name'], ''))
        elif (new['shape'] == old['shape'] and abs(new['rms_db'] - old['rms_db']) <= TOL['rms_db']
              and abs(new['centroid_hz'] - old['centroid_hz']) <= TOL['centroid_rel'] * max(old['centroid_hz'], 1.0)):
            rows.append(('CLOSE', t['name'], 'samples differ, metrics inside tolerance'))
        else:
            rows.append(('CHANGED', t['name'], f'rms {old["rms_db"]} -> {new["rms_db"]}, centroid {old["centroid_hz"]} -> {new["centroid_hz"]}'))
    rows += [('MISSING', n, 'frozen but the preset is gone') for n in sorted(set(frozen) - seen)]
    return rows


if __name__ == '__main__':
    if '--freeze' in sys.argv:
        for k, v in freeze().items():
            print(f'froze {k:32s} {v["sha256"][:12]} rms {v["rms_db"]:8.3f} dB')
    else:
        rows = verify()
        for r in rows:
            print(f'{r[0]:8s} {r[1]:32s} {r[2]}')
        sys.exit(0 if all(r[0] in ('PASS', 'CLOSE') for r in rows) else 1)
