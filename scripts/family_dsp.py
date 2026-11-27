"""family_dsp.py - treatments a family adds to a rendered stem: bow or breath noise, brass flare, a struck onset's snap.

Each one is data in references/data/presets/families/families.json (or the preset's own block of the same name), and runs only
for a preset or track that declares a family or the block. A stem of a preset that declares neither is returned untouched.

  noise  a band-passed noise (bow: friction 2-6 kHz; breath: air 1-4 kHz) that follows the stem's own envelope, level_db under it
  flare  brass spectral enrichment: above `onset_velocity` of the stem's peak envelope, a saturated high band is blended in, so a
         loud note is a different spectrum and not only a louder one (Campbell; Stevenson and Campbell, starting values)
  snap   the front of every onset sharpened (dsp.transient_shaper): the stick or mallet bite of a struck part
"""
import numpy as np
from scipy import signal

import dsp
import families

NOISE_BANDS = {'bow': (2000.0, 6000.0), 'breath': (1000.0, 4000.0)}     # starting values


def _env(y, sr, ms=25.0):
    m = np.abs(y).mean(axis=1) if y.ndim == 2 else np.abs(y)
    n = max(1, int(sr * ms / 1000.0))
    return np.convolve(m, np.ones(n) / n, mode='same')


def noise_layer(y, sr, kind, level_db, seed=0):
    if kind not in NOISE_BANDS:
        raise ValueError(f'noise kind "{kind}" is not one of {sorted(NOISE_BANDS)}')
    lo, hi = NOISE_BANDS[kind]
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    sos = signal.butter(2, [lo / (sr / 2), min(hi, sr * 0.45) / (sr / 2)], 'band', output='sos')
    out = np.array(y, dtype=np.float32, copy=True)
    e = _env(y, sr)
    for c in range(out.shape[1]):
        nz = signal.sosfilt(sos, rng.normal(0.0, 1.0, len(out))).astype(np.float32)
        out[:, c] += nz * e.astype(np.float32) * float(10 ** (level_db / 20.0))
    return out


def brass_flare(y, sr, onset_velocity, gain_db_per_unit, corner_hz):
    out = np.array(y, dtype=np.float32, copy=True)
    e = _env(y, sr, 40.0)
    pk = float(e.max())
    if pk <= 1e-9:
        return out
    drive = np.clip((e / pk - float(onset_velocity)) / max(1e-6, 1.0 - float(onset_velocity)), 0.0, 1.0).astype(np.float32)
    sos = signal.butter(2, corner_hz / (sr / 2), 'high', output='sos')
    amt = float(10 ** (gain_db_per_unit / 20.0)) - 1.0
    for c in range(out.shape[1]):
        hf = signal.sosfilt(sos, out[:, c]).astype(np.float32)
        out[:, c] += amt * drive * np.tanh(4.0 * hf) / 4.0
    return out


def apply(stem, inst_cfg, tr, sr, seed=0):
    """The stem after the family's treatments; the same array when nothing is declared."""
    beh = families.effective(inst_cfg, tr)
    if not beh:
        return stem
    y = dsp.to_2d(stem).astype(np.float32)
    if beh.get('snap'):
        y = dsp.transient_shaper(y, sr=sr, attack=float(beh['snap']['attack']), sustain=float(beh['snap']['sustain']))
    if beh.get('flare'):
        f = beh['flare']
        y = brass_flare(y, sr, f['onset_velocity'], f['gain_db_per_unit'], f['corner_hz'])
    if beh.get('noise'):
        y = noise_layer(y, sr, beh['noise']['kind'], beh['noise']['level_db'], seed)
    return y
