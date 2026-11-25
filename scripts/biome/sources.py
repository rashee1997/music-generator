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

"""sources.py - how a creature makes sound: one synthesizer per excitation kind, each a few physical equations.

    additive      the call grammar of env_engine/calls.py (pitch contour, subharmonic, biphonation, pulses, vibrato)
    glottal_chaos mammal vocal folds: an LF-model pulse train (vocal_engine) with jitter and shimmer, a period-doubled
                  subharmonic, and chaos from a logistic map that modulates the period (Wilden et al. 1998; Herzel)
    dual_syrinx   two independent syringeal oscillators with their own contours, saturation, FM and AM, summed or cross-
                  modulated (Mindlin & Laje, "The Physics of Birdsong")
    stridulation  teeth struck at a rate that follows temperature, ringing a resonant plate, gated into chirp trains
                  (Dolbear's law, written as data: rate_per_k)
    click_train   damped-sine clicks at a changing inter-click interval (sonar, buzz)
    swim_bladder  a gas bladder driven by muscle pulses; it rings at the Minnaert pitch of ITS depth and medium

Every function takes (params, sr, rng, scale, ctx) and returns a mono float64 waveform of the element's own duration.
Levels here are relative; fauna.py sets the absolute level from the radiated power. Numbers that are not from a source
are labelled "starting value" in their doc.
"""
import math

import numpy as np
from scipy import signal

from biome import physics
from env_engine import calls

KINDS = ('additive', 'glottal_chaos', 'dual_syrinx', 'stridulation', 'click_train', 'swim_bladder')
COMMON = ('ms', 'attack', 'release', 'level_db')
KEYS = {
    'additive': tuple(sorted(calls.ELEMENT_KEYS)),
    'glottal_chaos': COMMON + ('f0_hz', 'rd', 'jitter', 'shimmer', 'subharmonic', 'chaos', 'breath', 'tilt_hz'),
    'dual_syrinx': COMMON + ('f_left', 'f_right', 'harmonics', 'rolloff', 'saturation', 'fm_hz', 'fm_depth', 'am_hz', 'am_depth',
                             'mix', 'cross_depth'),
    'stridulation': COMMON + ('tooth_hz', 'plate_hz', 'plate_q', 'train', 'jitter', 'rate_per_k', 'temp_ref_k'),
    'click_train': COMMON + ('fc_hz', 'q', 'ici_ms', 'jitter'),
    'swim_bladder': COMMON + ('radius_m', 'depth_m', 'pulse_hz', 'q', 'jitter'),
}
TRAIN_KEYS = ('chirp_ms', 'period_ms')
REQUIRED = {
    'additive': ('f0_hz',), 'glottal_chaos': ('f0_hz',), 'dual_syrinx': ('f_left',), 'stridulation': ('tooth_hz', 'plate_hz'),
    'click_train': ('fc_hz', 'ici_ms'), 'swim_bladder': ('radius_m', 'pulse_hz'),
}
RANGES = {   # key -> (low, high, unit) for plain numbers
    'ms': (5.0, 60000.0, 'ms'), 'attack': (0.0, 1.0, '-'), 'release': (0.0, 1.0, '-'), 'level_db': (-80.0, 40.0, 'dB'),
    'rd': (0.3, 2.7, '-'), 'jitter': (0.0, 0.3, '-'), 'shimmer': (0.0, 0.5, '-'), 'subharmonic': (0.0, 1.0, '-'),
    'chaos': (0.0, 1.0, '-'), 'breath': (0.0, 2.0, '-'), 'tilt_hz': (20.0, 20000.0, 'Hz'),
    'harmonics': (1, 40, '-'), 'rolloff': (0.0, 4.0, '-'), 'saturation': (0.0, 10.0, '-'), 'fm_hz': (0.0, 500.0, 'Hz'),
    'fm_depth': (0.0, 0.5, '-'), 'am_hz': (0.0, 500.0, 'Hz'), 'am_depth': (0.0, 1.0, '-'), 'cross_depth': (0.0, 2.0, '-'),
    'tooth_hz': (1.0, 20000.0, 'Hz'), 'plate_hz': (20.0, 20000.0, 'Hz'), 'plate_q': (1.0, 500.0, '-'),
    'rate_per_k': (-0.2, 0.2, '1/K'), 'temp_ref_k': (1.0, 2000.0, 'K'), 'fc_hz': (20.0, 20000.0, 'Hz'), 'q': (0.5, 500.0, '-'),
    'radius_m': (1e-4, 1.0, 'm'), 'depth_m': (0.0, 11000.0, 'm'), 'pulse_hz': (0.5, 500.0, 'Hz'),
}


def problems(kind, params, where='source'):
    """Problems of one element's parameters for a source kind (the merged source-level and element-level keys)."""
    if kind not in KINDS:
        return [f'{where}.kind "{kind}": use one of {", ".join(KINDS)}']
    out = [f'{where}: unknown key "{k}" for {kind} (known: {", ".join(KEYS[kind])})' for k in params if k not in KEYS[kind] and k != 'kind']
    out += [f'{where}: {kind} needs "{k}"' for k in REQUIRED[kind] if k not in params]
    if kind == 'additive':
        return out + [f'{where}: ' + p for p in calls.problems({'elements': {'e': {k: v for k, v in params.items() if k != 'kind'}}}) if 'never read' in p]
    for k, v in params.items():
        if k in RANGES:
            lo, hi, unit = RANGES[k]
            vals = v if (k == 'ms' and isinstance(v, list) and len(v) == 2) else [v]       # a duration may be a [low, high] pair
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not lo <= x <= hi for x in vals):
                out.append(f'{where}.{k}={v!r}: a number from {lo:g} to {hi:g} {unit}')
    if kind in ('stridulation',) and 'train' in params:
        t = params['train']
        if not isinstance(t, dict) or any(k not in TRAIN_KEYS for k in t) or any(k not in t for k in TRAIN_KEYS):
            out.append(f'{where}.train: {{"chirp_ms", "period_ms"}}')
        elif t['chirp_ms'] > t['period_ms']:
            out.append(f'{where}.train: a chirp cannot be longer than its period')
    if kind == 'click_train' and 'ici_ms' in params:
        i = params['ici_ms']
        ok = isinstance(i, list) and len(i) >= 2 and all(isinstance(p, list) and len(p) == 2 and p[1] > 0 for p in i)
        if not ok:
            out.append(f'{where}.ici_ms: [[position 0..1, interval ms], ...]')
    for k in ('f0_hz', 'f_left', 'f_right'):
        if k in params and kind != 'additive':
            v = params[k]
            ok = (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0) or (
                isinstance(v, list) and len(v) >= 2 and all(isinstance(p, list) and len(p) == 2 and p[1] > 0 for p in v))
            if not ok:
                out.append(f'{where}.{k}: Hz, or [[position 0..1, Hz], ...]')
    return out


def _m(p, sr, rng):
    lo, hi = calls._pair(p.get('ms', 200.0))
    return max(32, int(rng.uniform(lo, hi) / 1000.0 * sr))


def envelope(m, p):
    x = np.arange(m) / m
    att, rel = max(float(p.get('attack', 0.15)), 1e-3), max(float(p.get('release', 0.3)), 1e-3)
    return np.sin(0.5 * np.pi * np.clip(x / att, 0, 1)) ** 2 * np.sin(0.5 * np.pi * np.clip((1.0 - x) / rel, 0, 1)) ** 2


def _level(p):
    return 10.0 ** (float(p.get('level_db', 0.0)) / 20.0)


def _ou(m, sr, rng, corner_hz=30.0):
    """Unit-variance slow noise (one-pole low-passed white noise): jitter and shimmer wander."""
    if m < 4:
        return np.zeros(m)
    a = math.exp(-2.0 * math.pi * corner_hz / sr)
    x = signal.lfilter([1.0], [1.0, -a], rng.standard_normal(m))
    return x / (x.std() + 1e-12)


def additive(p, sr, rng, scale, ctx):
    rate = 1.0
    return calls.element({k: v for k, v in p.items() if k != 'kind'}, sr, rng, scale, rate)


def glottal_chaos(p, sr, rng, scale, ctx):
    from vocal_engine.source import lf_pulse
    m = _m(p, sr, rng)
    f0 = calls._contour(p['f0_hz'], m) * scale
    rd = np.clip(calls._contour(p.get('rd', 1.0), m), 0.3, 2.7)
    f = f0 * (1.0 + float(p.get('jitter', 0.02)) * _ou(m, sr, rng))
    chaos = float(p.get('chaos', 0.0))
    if chaos > 0:                                          # the period itself follows a logistic map, cycle by cycle
        r = 3.5 + 0.5 * chaos
        x, t, mod = 0.4, 0, np.ones(m)
        while t < m:
            n = max(2, int(sr / max(float(f[min(t, m - 1)]), 20.0)))
            mod[t:t + n] = 1.0 + 0.15 * chaos * (2.0 * x - 1.0)
            x = r * x * (1.0 - x)
            t += n
        f = f * mod
    c = np.cumsum(f) / sr
    d, _ = lf_pulse(c - np.floor(c), rd)
    sub = float(p.get('subharmonic', 0.0))
    if sub > 0:                                            # period doubling: a second pulse train at half the rate
        c2 = c / 2.0
        d = d + sub * lf_pulse(c2 - np.floor(c2), rd)[0]
    if float(p.get('shimmer', 0.0)) > 0:
        d = d * np.maximum(1.0 + float(p['shimmer']) * _ou(m, sr, rng), 0.05)
    if float(p.get('breath', 0.0)) > 0:
        d = d + float(p['breath']) * 0.25 * np.std(d) * rng.standard_normal(m)
    if p.get('tilt_hz'):
        d = signal.lfilter([1 - math.exp(-2 * math.pi * float(p['tilt_hz']) / sr)], [1.0, -math.exp(-2 * math.pi * float(p['tilt_hz']) / sr)], d)
    d = d - d.mean()
    return d / (np.abs(d).max() + 1e-12) * envelope(m, p) * _level(p)


def dual_syrinx(p, sr, rng, scale, ctx):
    m = _m(p, sr, rng)
    t = np.arange(m) / sr
    hmax = int(p.get('harmonics', 4))
    roll = float(p.get('rolloff', 1.0))
    drive = 1.0 + float(p.get('saturation', 1.0))
    voices = []
    for key in ('f_left', 'f_right'):
        if key not in p:
            continue
        f = calls._contour(p[key], m) * scale
        if float(p.get('fm_depth', 0.0)) > 0:
            f = f * (1.0 + float(p['fm_depth']) * np.sin(2.0 * math.pi * float(p.get('fm_hz', 20.0)) * t + rng.uniform(0, 2 * math.pi)))
        f = np.minimum(f, 0.45 * sr)
        ph = 2.0 * math.pi * np.cumsum(f) / sr
        top = max(1, min(hmax, int(0.45 * sr / float(f.max()))))
        w = sum(np.sin(h * ph) / h ** roll for h in range(1, top + 1))
        voices.append(np.tanh(drive * w / (np.abs(w).max() + 1e-12)))
    if len(voices) == 2 and p.get('mix', 'sum') == 'cross' or (len(voices) == 2 and float(p.get('cross_depth', 0.0)) > 0):
        y = voices[0] + voices[1] * (1.0 + float(p.get('cross_depth', 0.5)) * voices[0])
    else:
        y = sum(voices)
    if float(p.get('am_depth', 0.0)) > 0:
        y = y * (1.0 + float(p['am_depth']) * np.sin(2.0 * math.pi * float(p.get('am_hz', 30.0)) * t))
    y = y - y.mean()
    return y / (np.abs(y).max() + 1e-12) * envelope(m, p) * _level(p)


def _rate_factor(p, ctx):
    dk = float(ctx.medium.temperature_k) - float(p.get('temp_ref_k', ctx.medium.temperature_k))
    return max(0.1, 1.0 + float(p.get('rate_per_k', 0.0)) * dk)


def _ring(imp, f_hz, q, sr):
    """Impulses into a damped resonator: a ring of quality factor q at f_hz."""
    r = math.exp(-math.pi * f_hz / (q * sr))
    th = 2.0 * math.pi * f_hz / sr
    return signal.lfilter([0.0, r * math.sin(th)], [1.0, -2.0 * r * math.cos(th), r * r], imp)


def stridulation(p, sr, rng, scale, ctx):
    m = _m(p, sr, rng)
    rate = _rate_factor(p, ctx)
    tooth = float(p['tooth_hz']) * rate
    jit = float(p.get('jitter', 0.03))
    n_t = int(m / sr * tooth * 1.3) + 4
    gaps = (sr / tooth) * (1.0 + jit * rng.standard_normal(n_t))
    pos = np.cumsum(np.maximum(gaps, 2.0)).astype(int)
    pos = pos[pos < m]
    imp = np.zeros(m)
    imp[pos] = 1.0 + 0.1 * rng.standard_normal(len(pos))
    y = _ring(imp, min(float(p['plate_hz']) * scale, 0.45 * sr), float(p.get('plate_q', 20.0)), sr)
    tr = p.get('train')
    if tr:
        period, chirp = float(tr['period_ms']) / 1000.0 / rate, float(tr['chirp_ms']) / 1000.0 / rate
        ph = (np.arange(m) / sr) % period
        edge = max(0.002, 0.15 * chirp)
        gate = np.clip(ph / edge, 0, 1) * np.clip((chirp - ph) / edge, 0, 1)
        y = y * gate
    return y / (np.abs(y).max() + 1e-12) * envelope(m, dict(p, attack=p.get('attack', 0.05), release=p.get('release', 0.1))) * _level(p)


def click_train(p, sr, rng, scale, ctx):
    m = _m(p, sr, rng)
    tab = np.asarray(p['ici_ms'], dtype=float)
    imp = np.zeros(m)
    t = 0.0
    jit = float(p.get('jitter', 0.03))
    dur = m / sr
    while t < dur:
        imp[int(t * sr)] = 1.0 + 0.1 * rng.standard_normal()
        ici = float(np.interp(t / dur, tab[:, 0], tab[:, 1])) / 1000.0
        t += max(ici * (1.0 + jit * rng.standard_normal()), 0.5 / sr * 2)
    y = _ring(imp, min(float(p['fc_hz']) * scale, 0.45 * sr), float(p.get('q', 3.0)), sr)
    return y / (np.abs(y).max() + 1e-12) * envelope(m, dict(p, attack=p.get('attack', 0.05), release=p.get('release', 0.1))) * _level(p)


def bladder_hz(p, ctx):
    """Minnaert pitch of a swim bladder at its depth, in the animal's medium."""
    med = ctx.medium
    press = med.pressure_pa + med.rho * ctx.g * float(p.get('depth_m', 0.0))
    return physics.minnaert_hz(float(p['radius_m']), med.gamma, press, med.rho)


def swim_bladder(p, sr, rng, scale, ctx):
    m = _m(p, sr, rng)
    f = bladder_hz(p, ctx) / scale
    if f >= 0.45 * sr:
        raise ValueError(f'swim_bladder: the bladder rings at {f:.0f} Hz, above the Nyquist frequency of {sr} Hz')
    rate = float(p['pulse_hz'])
    n = int(m / sr * rate * 1.3) + 4
    gaps = (sr / rate) * (1.0 + float(p.get('jitter', 0.05)) * rng.standard_normal(n))
    pos = np.cumsum(np.maximum(gaps, 2.0)).astype(int)
    pos = pos[pos < m]
    imp = np.zeros(m)
    imp[pos] = 1.0 + 0.2 * rng.standard_normal(len(pos))
    y = _ring(imp, f, float(p.get('q', 15.0)), sr)
    return y / (np.abs(y).max() + 1e-12) * envelope(m, p) * _level(p)


SYNTH = {'additive': additive, 'glottal_chaos': glottal_chaos, 'dual_syrinx': dual_syrinx, 'stridulation': stridulation,
         'click_train': click_train, 'swim_bladder': swim_bladder}


def element(kind, params, sr, rng, scale, ctx):
    """One element's waveform (peak about 1, its own envelope)."""
    return SYNTH[kind](params, sr, rng, scale, ctx)
