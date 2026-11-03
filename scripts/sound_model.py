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
"""sound_model.py - any sound effect or ambience as data: a stack of voices, each  excitation -> resonator -> time process.

    python3 scripts/sound_model.py render model.json --out x.wav [--seconds 3] [--seed 1]
    python3 scripts/sound_model.py check  model.json          # list every problem, render nothing
    python3 scripts/sound_model.py laws                       # the parts and their parameters

A model is {"seconds": 2.0, "voices": [voice, ...]}. A voice:

    {"name": "knock", "gain_db": 0,
     "excite":    {"kind": "impact", "tau": 0.002},                         # impact | noise | friction | periodic | burst
     "resonator": {"kind": "modal", "law": "bar", "f1": 300, "n": 8, "t60": 0.6},   # modal | bandpass | formant | bubble | none
     "events":    {"kind": "poisson", "rate": 3.0},                         # single | periodic | poisson | gamma | cluster | bounce | sequence | continuous
     "vary":      {"size": {"dist": "lognormal", "sigma": 0.2}, "pitch_exp": 1.0, "amp_exp": 2.0, "level_spread_db": 3},
     "control":   {"gain_db": [{"kind": "ou", "sigma_db": 3, "tau_s": 4}]}}

Formulas and where each comes from: knowledgebase/SFX_MODEL_FORMULAS.md (modal bank and impact pulse after van den Doel, Kry and
Pai 2001; fractal-noise scraping from the same paper; Marshall-Palmer drop sizes; Minnaert bubbles). Every random choice is seeded, so a
model and a seed always give the same samples. Unknown keys and out-of-range values are errors; a work estimate stops a runaway model.
"""
import argparse
import json
import math
import sys

import numpy as np
from scipy.signal import lfilter, sosfilt, butter

SR = 44100
MAX_WORK = 6e8              # estimated multiply-adds for one render (about 10 s of CPU on a laptop); above this the model is refused
MAX_VOICES = 24
MAX_MODES = 96
MAX_RING_S = 8.0

# ------------------------------------------------------------------------------------------------ schema
# kind -> {parameter: (default, low, high)}; a string default means "one of" listed in CHOICES
CHOICES = {
    'law': ('string', 'tube_closed', 'bar', 'membrane', 'power', 'free'),
    'color': ('white', 'pink', 'brown'),
    'size_dist': ('none', 'lognormal', 'exp', 'marshall_palmer'),
    'control_kind': ('curve', 'lfo', 'ou', 'env'),
}
EXCITE = {
    'impact': dict(tau=(0.002, 1e-5, 0.2)),                                             # contact time, s (hard = short)
    'noise': dict(color='white', band=None, attack=0.0, tau=None, hold=0.0),             # tau: decay time constant of a burst
    'friction': dict(beta=-1.5, speed=1.0, speed_curve=None, amp_exp=1.0, slip_hz=0.0, slip_depth=0.0),
    'periodic': dict(f0=(100.0, 5.0, 12000.0), glide=None, jitter=(0.0, 0.0, 0.5), harmonics=(12, 1, 64),
                     attack=0.0, tau=None, hold=0.0, am_hz=(0.0, 0.0, 400.0), am_depth=(1.0, 0.0, 1.0), noise_mix=(0.0, 0.0, 1.0)),
    'burst': dict(tau=(0.01, 1e-4, 4.0), color='white'),
}
RESONATOR = {
    'modal': dict(law='string', f1=(440.0, 10.0, 12000.0), n=(8, 1, MAX_MODES), t60=(0.5, 0.005, MAX_RING_S),
                  damp_exp=(0.5, -2.0, 4.0), gain_exp=(1.0, -2.0, 4.0), exponent=(1.0, 0.5, 4.0), ratios=None,
                  strike_spread=(0.0, 0.0, 2.0)),
    'bandpass': dict(band=(300.0, 3000.0), order=(2, 1, 8)),
    'formant': dict(formants=None),
    'bubble': dict(radius_mm=None, f_hz=None, t60=(0.03, 0.002, 2.0), rise=(0.1, 0.0, 2.0)),
    'none': dict(),
}
EVENTS = {
    'single': dict(at=(0.0, 0.0, 600.0)),
    'periodic': dict(period=(1.0, 0.002, 600.0), jitter=(0.0, 0.0, 1.0), start=(0.0, 0.0, 600.0), end=None),
    'poisson': dict(rate=(1.0, 0.01, 4000.0), start=(0.0, 0.0, 600.0), end=None),
    'gamma': dict(rate=(1.0, 0.01, 4000.0), shape=(2.0, 0.2, 50.0), start=(0.0, 0.0, 600.0), end=None),
    'cluster': dict(rate=(0.5, 0.01, 100.0), per=(5.0, 1.0, 500.0), spread=(0.2, 0.001, 30.0), start=(0.0, 0.0, 600.0), end=None),
    'bounce': dict(at=(0.0, 0.0, 600.0), gap=(0.4, 0.005, 5.0), restitution=(0.7, 0.05, 0.99), n=(12, 1, 60)),
    'sequence': dict(times=None, levels=None),
    'continuous': dict(),
}
VOICE_KEYS = {'name', 'gain_db', 'excite', 'resonator', 'events', 'vary', 'control', 'variants', 'note'}
VARY_KEYS = {'size', 'pitch_exp', 'amp_exp', 'level_spread_db'}
SIZE_KEYS = {'dist': 'none', 'sigma': 0.2, 'rate_mm_h': 5.0, 'min': 0.3, 'max': 3.0}
CONTROL_ITEM = {'curve': {'points'}, 'lfo': {'hz', 'depth_db', 'shape', 'phase'}, 'ou': {'sigma_db', 'tau_s', 'mean_db'},
                'env': {'attack', 'hold', 'decay_tau'}}
CONTROL_KEYS = {'gain_db', 'pitch'}


def get_path(model, path):
    """Value at a dotted path such as "voices.0.resonator.f1"."""
    cur = model
    for part in path.split('.'):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def set_path(model, path, value):
    parts = path.split('.')
    cur = model
    for part in parts[:-1]:
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


def _spec_default(v):
    return v[0] if isinstance(v, tuple) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v) else v


def _check_params(where, given, spec, out):
    for k in given:
        if k not in spec:
            out.append(f'{where}: unknown key "{k}" (known: {", ".join(spec) or "none"})')
    for k, v in given.items():
        d = spec.get(k)
        if isinstance(d, tuple) and len(d) == 3 and all(isinstance(x, (int, float)) for x in d):
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                out.append(f'{where}.{k}: needs a number, got {v!r}')
            elif not d[1] <= v <= d[2]:
                out.append(f'{where}.{k}={v}: outside the allowed range {d[1]} to {d[2]}')
        elif k == 'law' and v not in CHOICES['law']:
            out.append(f'{where}.law "{v}": use one of {", ".join(CHOICES["law"])}')
        elif k == 'color' and v not in CHOICES['color']:
            out.append(f'{where}.color "{v}": use one of {", ".join(CHOICES["color"])}')


def problems(model):
    """Every problem of a model (empty = good). Unknown keys, bad ranges, missing parts, and a work estimate over the limit."""
    out = []
    if not isinstance(model, dict):
        return ['a model is an object {"seconds": ..., "voices": [...]}']
    for k in model:
        if k not in ('seconds', 'voices', 'note', 'free'):
            out.append(f'model: unknown key "{k}" (known: seconds, voices, note, free)')
    voices = model.get('voices')
    if not isinstance(voices, list) or not voices:
        return out + ['model: "voices" must be a non-empty list']
    if len(voices) > MAX_VOICES:
        out.append(f'model: {len(voices)} voices, the limit is {MAX_VOICES}')
    sec = model.get('seconds', 1.0)
    if not isinstance(sec, (int, float)) or not 0.02 <= sec <= 3600:
        out.append(f'model.seconds={sec!r}: use a number from 0.02 to 3600')
    for i, v in enumerate(voices):
        w = f'voice {i}' + (f' "{v.get("name")}"' if isinstance(v, dict) and v.get('name') else '')
        if not isinstance(v, dict):
            out.append(f'{w}: must be an object')
            continue
        out += [f'{w}: unknown key "{k}" (known: {", ".join(sorted(VOICE_KEYS))})' for k in v if k not in VOICE_KEYS]
        ex, rs, ev = v.get('excite'), v.get('resonator', {'kind': 'none'}), v.get('events', {'kind': 'single'})
        for label, part, table in (('excite', ex, EXCITE), ('resonator', rs, RESONATOR), ('events', ev, EVENTS)):
            if not isinstance(part, dict) or part.get('kind') not in table:
                out.append(f'{w}.{label}: needs "kind" one of {", ".join(table)}' + (' (excite is required)' if part is None else ''))
                continue
            _check_params(f'{w}.{label}', {k: x for k, x in part.items() if k != 'kind'}, table[part['kind']], out)
        if isinstance(rs, dict) and rs.get('kind') == 'modal':
            law = rs.get('law', 'string')
            if law == 'free' and not rs.get('ratios'):
                out.append(f'{w}.resonator: law "free" needs "ratios": [1, 2.3, ...]')
            if rs.get('ratios') and (not isinstance(rs['ratios'], list) or not all(isinstance(x, (int, float)) and x > 0 for x in rs['ratios'])):
                out.append(f'{w}.resonator.ratios: a list of positive numbers')
        if isinstance(rs, dict) and rs.get('kind') == 'formant':
            fm = rs.get('formants')
            if not (isinstance(fm, list) and fm and all(isinstance(f, list) and len(f) in (2, 3) and f[0] > 20 and f[1] > 1 for f in fm)):
                out.append(f'{w}.resonator.formants: [[freq_hz, bandwidth_hz, gain(optional)], ...]')
        if isinstance(rs, dict) and rs.get('kind') == 'bubble' and rs.get('radius_mm') is None and rs.get('f_hz') is None:
            out.append(f'{w}.resonator: bubble needs "radius_mm" or "f_hz"')
        if isinstance(ev, dict) and ev.get('kind') == 'sequence' and not (isinstance(ev.get('times'), list) and ev['times']):
            out.append(f'{w}.events: sequence needs "times": [seconds, ...]')
        if isinstance(ex, dict) and ex.get('kind') in ('impact', 'burst') and isinstance(ev, dict) and ev.get('kind') == 'continuous':
            out.append(f'{w}: an {ex["kind"]} excitation is an event; use events.kind other than "continuous"')
        if isinstance(ex, dict) and ex.get('kind') == 'friction' and isinstance(ev, dict) and ev.get('kind') != 'continuous':
            out.append(f'{w}: friction runs for the whole voice; use events.kind "continuous"')
        va = v.get('vary', {})
        if isinstance(va, dict):
            out += [f'{w}.vary: unknown key "{k}" (known: {", ".join(sorted(VARY_KEYS))})' for k in va if k not in VARY_KEYS]
            sz = va.get('size') or {}
            out += [f'{w}.vary.size: unknown key "{k}"' for k in sz if k not in SIZE_KEYS]
            if sz.get('dist', 'none') not in CHOICES['size_dist']:
                out.append(f'{w}.vary.size.dist "{sz.get("dist")}": use one of {", ".join(CHOICES["size_dist"])}')
            for k in ('pitch_exp', 'amp_exp', 'level_spread_db'):
                if k in va and not isinstance(va[k], (int, float)):
                    out.append(f'{w}.vary.{k}: needs a number')
        ctl = v.get('control', {})
        if isinstance(ctl, dict):
            out += [f'{w}.control: unknown key "{k}" (known: {", ".join(sorted(CONTROL_KEYS))})' for k in ctl if k not in CONTROL_KEYS]
            for key in CONTROL_KEYS & set(ctl):
                if key == 'pitch':
                    if not (isinstance(ev, dict) and ev.get('kind') == 'continuous' and isinstance(ex, dict) and ex.get('kind') == 'periodic'):
                        out.append(f'{w}.control.pitch: only for a continuous voice with a periodic excitation (an engine, a siren)')
                    if not (isinstance(ctl['pitch'], list) and all(isinstance(i, dict) and i.get('kind') == 'curve' for i in ctl['pitch'])):
                        out.append(f'{w}.control.pitch: a list of curve items; values are frequency multipliers (1 = unchanged)')
                for j, item in enumerate(ctl[key] if isinstance(ctl[key], list) else [ctl[key]]):
                    kind = item.get('kind') if isinstance(item, dict) else None
                    if kind not in CONTROL_ITEM:
                        out.append(f'{w}.control.{key}[{j}]: "kind" one of {", ".join(CONTROL_ITEM)}')
                    else:
                        out += [f'{w}.control.{key}[{j}]: unknown key "{k}"' for k in item if k != 'kind' and k not in CONTROL_ITEM[kind]]
                        if kind == 'curve' and not (isinstance(item.get('points'), list) and len(item['points']) >= 2):
                            out.append(f'{w}.control.{key}[{j}]: curve needs "points": [[seconds, value], ...] (two or more)')
    for path, rng_ in (model.get('free') or {}).items():
        try:
            val = get_path(model, path)
        except (KeyError, IndexError, TypeError):
            out.append(f'model.free "{path}": no such parameter')
            continue
        if not (isinstance(rng_, list) and len(rng_) == 2 and rng_[0] < rng_[1]):
            out.append(f'model.free "{path}": needs [min, max] with min < max')
        elif not isinstance(val, (int, float)):
            out.append(f'model.free "{path}": value {val!r} is not a number')
        elif not rng_[0] <= val <= rng_[1]:
            out.append(f'model.free "{path}": value {val} is outside its range {rng_}')
    if not out:
        work = work_estimate(model)
        if work > MAX_WORK:
            out.append(f'model: estimated work {work:.2e} is above the limit {MAX_WORK:.0e}; lower rate, n, t60 or seconds, or use fewer voices')
    return out


DEFAULT_VOICES = [dict(name='bed', excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[200.0, 4000.0]),
                       events=dict(kind='continuous'))]      # what a model layer with no voices plays: a plain pink-noise bed


# ------------------------------------------------------------------------------------------------ helpers
def _rng(seed, i, j=0):
    return np.random.default_rng(np.random.SeedSequence([int(seed) & 0xFFFFFFFF, i, j]))


def _d(part, table):
    """Parameters of a part with defaults filled in."""
    base = {k: _spec_default(v) for k, v in table[part['kind']].items()}
    base.update({k: v for k, v in part.items() if k != 'kind'})
    return base


def _expected_events(ev, sec):
    k = ev['kind']
    if k in ('single', 'continuous'):
        return 1
    if k == 'periodic':
        return max(1.0, (sec - ev.get('start', 0.0)) / ev['period'])
    if k in ('poisson', 'gamma'):
        return max(1.0, ev['rate'] * sec)
    if k == 'cluster':
        return max(1.0, ev['rate'] * ev['per'] * sec)
    if k == 'bounce':
        return ev['n']
    return len(ev.get('times') or [1])


def _ring_s(rs):
    if rs['kind'] == 'modal':
        return min(MAX_RING_S, rs['t60'] * 1.2)
    if rs['kind'] == 'bubble':
        return min(1.0, rs['t60'] * 1.2)
    return 0.15


def work_estimate(model):
    """Rough multiply-adds: variants x modes x samples to build, plus events x ring samples to place."""
    sec = float(model.get('seconds', 1.0))
    total = 0.0
    for v in model['voices']:
        ex = _d(v['excite'], EXCITE)
        rs = _d(v.get('resonator', {'kind': 'none'}), RESONATOR) | {'kind': v.get('resonator', {'kind': 'none'})['kind']}
        ev = _d(v.get('events', {'kind': 'single'}), EVENTS) | {'kind': v.get('events', {'kind': 'single'})['kind']}
        modes = rs['n'] if rs['kind'] == 'modal' else 2
        if ev['kind'] == 'continuous':
            total += modes * sec * SR * 4
            continue
        ring = _ring_s(rs) + (ex.get('tau') or 0.05) * 3 + float(ex.get('hold', 0) or 0)
        length = ring * SR
        total += v.get('variants', 16) * modes * length * 4 + _expected_events(ev, sec) * length
    return total


def _colored_noise(rng, n, color):
    x = rng.standard_normal(n)
    if color == 'white' or n < 16:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n)
    f[0] = f[1]
    X *= f ** (-0.5 if color == 'pink' else -1.0)
    y = np.fft.irfft(X, n)
    return y / (np.std(y) + 1e-12)


def _band(x, band, sr, order=2):
    if not band:
        return x
    lo, hi = max(float(band[0]), 20.0), min(float(band[1]), sr / 2 - 100)
    if hi <= lo:
        return x
    return sosfilt(butter(order, [lo, hi], btype='band', fs=sr, output='sos'), x)


def _interp_curve(points, t, default=0.0):
    pts = sorted((float(a), float(b)) for a, b in points)
    return np.interp(t, [p[0] for p in pts], [p[1] for p in pts]) if pts else np.full_like(t, default)


# ------------------------------------------------------------------------------------------------ excitation
def _envelope(n, sr, attack, tau, hold):
    t = np.arange(n) / sr
    e = np.ones(n)
    if attack and attack > 0:
        e *= np.clip(t / attack, 0, 1)
    if tau:
        e *= np.where(t < hold, 1.0, np.exp(-(t - hold) / tau))
    return e


def excitation(ex, dur, sr, rng, pitch=1.0, speed_scale=1.0):
    """The raw excitation signal for `dur` seconds (an impact is a short pulse then zeros)."""
    n = max(1, int(round(dur * sr)))
    k = ex['kind']
    if k == 'impact':
        m = max(2, int(round(ex['tau'] * sr)))
        m = min(m, n)
        t = np.arange(m) / (m)
        pulse = 1 - np.cos(2 * np.pi * t)                 # 1 - cos(2 pi t / tau), 0 <= t <= tau   (FoleyAutomatic, impact force)
        out = np.zeros(n)
        out[:m] = pulse / max(pulse.sum(), 1e-12)
        return out
    if k == 'burst':
        x = _colored_noise(rng, n, ex['color']) * np.exp(-np.arange(n) / sr / ex['tau'])
        return x / (np.abs(x).max() + 1e-12) * 0.2
    if k == 'noise':
        x = _band(_colored_noise(rng, n, ex['color']), ex['band'], sr)
        return x * _envelope(n, sr, ex['attack'], ex['tau'], ex['hold'])
    if k == 'periodic':
        f0 = ex['f0'] * pitch
        if ex['glide']:
            g0, g1 = ex['glide']
            f = g0 * (g1 / g0) ** (np.arange(n) / max(n - 1, 1)) * pitch
        else:
            f = np.full(n, f0)
        if ex['jitter']:
            f = f * (1 + ex['jitter'] * np.convolve(rng.standard_normal(n), np.ones(max(1, sr // 200)) / max(1, sr // 200), 'same'))
        ph = np.cumsum(2 * np.pi * f / sr)
        nh = int(min(ex['harmonics'], max(1, (sr / 2 - 200) / max(f.max(), 1.0))))
        x = sum(np.sin(h * ph) / h for h in range(1, nh + 1))
        x = x / (np.std(x) + 1e-12)
        if ex['noise_mix'] > 0:                                   # a rough, breathy source: harmonic part and noise in this ratio
            x = (1 - ex['noise_mix']) * x + ex['noise_mix'] * rng.standard_normal(n)
        if ex['am_hz'] > 0:                                       # a pulse train: amplitude gated at am_hz (calls of frogs, insects, rattles)
            gate = 0.5 * (1 + np.sin(2 * np.pi * ex['am_hz'] * np.arange(n) / sr - np.pi / 2))
            x = x * ((1 - ex['am_depth']) + ex['am_depth'] * gate ** 2)
        return x * _envelope(n, sr, ex['attack'], ex['tau'], ex['hold'])
    if k == 'friction':
        # surface profile = noise with power spectrum ~ omega^beta; read at the contact speed (the needle model of the paper)
        beta = ex['beta']
        L = max(n * 2, sr)
        X = np.fft.rfft(rng.standard_normal(L))
        f = np.fft.rfftfreq(L)
        f[0] = f[1]
        X *= np.abs(f) ** (beta / 2.0)
        prof = np.fft.irfft(X, L)
        prof /= np.std(prof) + 1e-12
        t = np.arange(n) / sr
        v = _interp_curve(ex['speed_curve'], t) if ex['speed_curve'] else np.full(n, float(ex['speed']))
        v = np.clip(v, 0.0, 8.0) * speed_scale
        pos = np.cumsum(v)
        x = np.interp(pos % L, np.arange(L), prof)
        x *= np.clip(v, 0, None) ** ex['amp_exp']
        if ex['slip_hz'] > 0 and ex['slip_depth'] > 0:
            saw = (t * ex['slip_hz']) % 1.0
            x *= 1 - ex['slip_depth'] * saw
        return x
    raise ValueError(f'unknown excitation {k}')


# ------------------------------------------------------------------------------------------------ resonators
def mode_ratios(rs):
    n = int(rs['n'])
    law = rs['law']
    if rs.get('ratios'):
        r = np.asarray(rs['ratios'], float)
        return r[:n] if len(r) >= n else np.concatenate([r, r[-1] * (1 + np.arange(1, n - len(r) + 1) * 0.5)])
    if law == 'string':
        return np.arange(1, n + 1, dtype=float)
    if law == 'tube_closed':
        return np.arange(1, 2 * n, 2, dtype=float)
    if law == 'bar':                                     # free-free bar: measured first five, then ((2n+1)/3)^2
        first = [1.0, 2.757, 5.404, 8.933, 13.34]
        return np.array(first[:n] + [((2 * k + 1) / 3.0) ** 2 for k in range(len(first), n)], float)
    if law == 'membrane':                                # circular membrane: first six zeros of J_mn over the first, then spaced by .35
        first = [1.0, 1.594, 2.136, 2.296, 2.653, 2.918]
        return np.array(first[:n] + [2.918 + 0.35 * (k - 5) for k in range(len(first), n)], float)
    if law == 'power':
        return np.arange(1, n + 1, dtype=float) ** rs['exponent']
    raise ValueError(f'unknown mode law {law}')


def modal_bank(x, rs, sr, rng, pitch=1.0):
    """Drive a bank of damped resonators with x. An impulse in gives sum a_n exp(-d_n t) sin(2 pi f_n t)  (FoleyAutomatic eq. 1)."""
    ratios = mode_ratios(rs)
    f = rs['f1'] * pitch * ratios
    keep = f < sr / 2 - 200
    f, ratios = f[keep], ratios[keep]
    if len(f) == 0:
        return x * 0.0
    t60 = np.maximum(rs['t60'] * (ratios ** (-rs['damp_exp'])), 0.002)
    d = 6.907755 / t60
    gains = ratios ** (-rs['gain_exp'])
    if rs['strike_spread'] > 0:
        gains = gains * np.exp(rng.standard_normal(len(f)) * rs['strike_spread'])
    gains = gains / (gains.max() + 1e-12)
    y = np.zeros(len(x))
    for fn, dn, an in zip(f, d, gains):
        r = math.exp(-dn / sr)
        th = 2 * math.pi * fn / sr
        y += an * lfilter([0.0, r * math.sin(th)], [1.0, -2 * r * math.cos(th), r * r], x)
    return y


def bubble_event(rs, dur, sr, pitch=1.0):
    """Minnaert bubble: f = 3.26 / r (r in metres), a decaying sine whose pitch rises a little (the bubble shrinks as it rings)."""
    f0 = (rs['f_hz'] if rs.get('f_hz') else 3.26 / (float(rs['radius_mm']) * 1e-3)) * pitch
    f0 = min(f0, sr / 2 - 300)
    n = max(2, int(round(dur * sr)))
    t = np.arange(n) / sr
    d = 6.907755 / rs['t60']
    return np.exp(-d * t) * np.sin(2 * np.pi * f0 * (t + 0.5 * rs['rise'] * d * t * t))


def resonate(x, rs, sr, rng, pitch=1.0):
    k = rs['kind']
    if k == 'none':
        return x
    if k == 'modal':
        return modal_bank(x, rs, sr, rng, pitch)
    if k == 'bandpass':
        lo, hi = rs['band']
        return _band(x, [lo * pitch, hi * pitch], sr, int(rs['order']))
    if k == 'formant':
        y = np.zeros(len(x))
        for fm in rs['formants']:
            fc, bw = float(fm[0]) * pitch, float(fm[1])
            g = float(fm[2]) if len(fm) > 2 else 1.0
            r = math.exp(-math.pi * bw / sr)
            th = 2 * math.pi * min(fc, sr / 2 - 200) / sr
            y += g * lfilter([1 - r], [1.0, -2 * r * math.cos(th), r * r], x)
        return y
    raise ValueError(k)


# ------------------------------------------------------------------------------------------------ time processes
def event_times(ev, sec, rng):
    k = ev['kind']
    end = min(sec, ev.get('end') if ev.get('end') is not None else sec)
    if k == 'single':
        return np.array([ev['at']]), np.ones(1)
    if k == 'sequence':
        t = np.asarray(ev['times'], float)
        lv = np.asarray(ev['levels'], float) if ev.get('levels') else np.ones(len(t))
        if len(lv) != len(t):
            raise ValueError('sequence: "levels" needs one value per time')
        return t, lv
    if k == 'bounce':
        gaps = ev['gap'] * ev['restitution'] ** np.arange(ev['n'])
        times = ev['at'] + np.concatenate([[0.0], np.cumsum(gaps[:-1])])
        return times, ev['restitution'] ** np.arange(ev['n'])
    start = ev.get('start', 0.0)
    if k == 'periodic':
        t = np.arange(start, end, ev['period'])
        t = t + ev['jitter'] * ev['period'] * rng.standard_normal(len(t))
        return t, np.ones(len(t))
    if k in ('poisson', 'gamma'):
        shape = 1.0 if k == 'poisson' else ev['shape']
        mean_gap = 1.0 / ev['rate']
        n_est = int((end - start) * ev['rate'] * 1.5) + 20
        gaps = rng.gamma(shape, mean_gap / shape, n_est)
        t = start + np.cumsum(gaps)
        while t.size and t[-1] < end:
            t = np.concatenate([t, t[-1] + np.cumsum(rng.gamma(shape, mean_gap / shape, n_est))])
        t = t[t < end]
        return t, np.ones(len(t))
    if k == 'cluster':
        centres = start + np.cumsum(rng.exponential(1.0 / ev['rate'], int((end - start) * ev['rate'] * 1.5) + 10))
        centres = centres[centres < end]
        t = np.concatenate([c + ev['spread'] * np.abs(rng.standard_normal(max(1, rng.poisson(ev['per'])))) for c in centres]) if len(centres) else np.zeros(0)
        t = t[t < end]
        return np.sort(t), np.ones(len(t))
    raise ValueError(k)


def sample_sizes(vary, n, rng):
    """Relative sizes (mean about 1) for n events or variants. size ~ drop diameter, bubble radius, object scale."""
    sz = {**SIZE_KEYS, **(vary.get('size') or {})}
    dist = sz['dist']
    if dist == 'none':
        return np.ones(n)
    if dist == 'lognormal':
        s = np.exp(sz['sigma'] * rng.standard_normal(n))
    elif dist == 'exp':
        s = rng.exponential(1.0, n)
    else:                                                # Marshall-Palmer: N(D) ~ exp(-Lambda D), Lambda = 4.1 R^-0.21 per mm
        lam = 4.1 * max(sz['rate_mm_h'], 0.05) ** -0.21
        s = rng.exponential(1.0 / lam, n)
        s = np.clip(s, 0.05, 6.0)
    s = np.clip(s, sz['min'] * s.mean(), sz['max'] * s.mean()) if dist != 'marshall_palmer' else s
    return s / s.mean()


# ------------------------------------------------------------------------------------------------ control
def control_db(items, n, sr, rng):
    """Sum of control items in dB over n samples (curve, lfo, ou, env)."""
    t = np.arange(n) / sr
    db = np.zeros(n)
    for it in (items if isinstance(items, list) else [items]):
        k = it['kind']
        if k == 'curve':
            db += _interp_curve(it['points'], t)
        elif k == 'lfo':
            ph = it['phase'] * 2 * np.pi if 'phase' in it else rng.uniform(0, 2 * np.pi)
            wave = np.sin(2 * np.pi * it.get('hz', 0.2) * t + ph)
            if it.get('shape') == 'square':
                wave = np.sign(wave)
            db += it.get('depth_db', 3.0) * wave
        elif k == 'ou':                                  # Ornstein-Uhlenbeck: bounded random walk
            step = max(1, sr // 100)
            m = n // step + 2
            dt = step / sr
            th = 1.0 / max(it.get('tau_s', 3.0), 1e-3)
            sg = it.get('sigma_db', 3.0)
            x = np.zeros(m)
            z = rng.standard_normal(m)
            a = math.exp(-th * dt)
            s = sg * math.sqrt(1 - a * a)
            for i in range(1, m):
                x[i] = a * x[i - 1] + s * z[i]
            db += it.get('mean_db', 0.0) + np.interp(np.arange(n) / step, np.arange(m), x)
        elif k == 'env':
            e = _envelope(n, sr, it.get('attack', 0.0), it.get('decay_tau'), it.get('hold', 0.0))
            db += 20 * np.log10(np.maximum(e, 1e-5))
    return db


# ------------------------------------------------------------------------------------------------ rendering
def _prep_voice(v):
    ex = _d(v['excite'], EXCITE) | {'kind': v['excite']['kind']}
    rs0 = v.get('resonator', {'kind': 'none'})
    rs = _d(rs0, RESONATOR) | {'kind': rs0['kind']}
    ev0 = v.get('events', {'kind': 'single'})
    ev = _d(ev0, EVENTS) | {'kind': ev0['kind']}
    return ex, rs, ev, v.get('vary', {}) or {}, v.get('control', {}) or {}


def _event_buffer(ex, rs, sr, rng, size, vary):
    pitch = size ** -float(vary.get('pitch_exp', 1.0)) if size != 1 else 1.0
    ring = _ring_s(rs)
    if rs['kind'] == 'bubble':
        y = bubble_event(rs, ring, sr, pitch)
        return y / (np.abs(y).max() + 1e-12)
    dur = ring + (ex.get('tau') if ex['kind'] in ('noise', 'periodic') and ex.get('tau') else 0) * 3 + float(ex.get('hold', 0) or 0)
    if ex['kind'] in ('noise', 'periodic') and not ex.get('tau'):
        dur += 0.1
    if ex['kind'] == 'burst':
        dur += ex['tau'] * 3
    x = excitation(ex, dur, sr, rng, pitch)
    y = resonate(x, rs, sr, rng, pitch)
    return y / (np.abs(y).max() + 1e-12)


def render_voice(v, sec, sr, seed, index):
    ex, rs, ev, vary, ctl = _prep_voice(v)
    rng = _rng(seed, index)
    n = int(round(sec * sr))
    if ev['kind'] == 'continuous':
        pitch = 1.0
        if ctl.get('pitch'):
            pitch = np.ones(n)
            for it in ctl['pitch']:
                pitch = pitch * _interp_curve(it['points'], np.arange(n) / sr, 1.0)
        x = excitation(ex, sec, sr, rng, pitch)
        y = resonate(x, rs, sr, rng, 1.0)
        y = y / (np.sqrt(np.mean(y ** 2)) + 1e-12) * 0.25                # continuous voices start at RMS 0.25
    else:
        times, levels = event_times(ev, sec, rng)
        nv = int(v.get('variants', 16))
        if ev['kind'] in ('single', 'bounce', 'sequence'):
            nv = min(nv, max(1, len(times)))
        sizes = sample_sizes(vary, nv, rng)
        bufs = [_event_buffer(ex, rs, sr, _rng(seed, index, 1 + j), float(s), vary) for j, s in enumerate(sizes)]
        y = np.zeros(n)
        pick = rng.integers(0, nv, len(times))
        spread = float(vary.get('level_spread_db', 0.0))
        amp_exp = float(vary.get('amp_exp', 0.0))
        jit = 10 ** (spread * rng.standard_normal(len(times)) / 20) if spread else np.ones(len(times))
        for t0, lv, p, jj in zip(times, levels, pick, jit):
            i = int(round(t0 * sr))
            if i >= n or i < 0:
                continue
            b = bufs[p]
            a = lv * jj * (float(sizes[p]) ** amp_exp)
            seg = b[: n - i]
            y[i:i + len(seg)] += a * seg
        peak = np.abs(y).max()
        if peak > 0:
            y /= peak                                                   # event voices start at peak 1
    if ctl.get('gain_db'):
        y = y * 10 ** (control_db(ctl['gain_db'], n, sr, _rng(seed, index, 999)) / 20)
    return y * 10 ** (float(v.get('gain_db', 0.0)) / 20)


def render(model, sr=SR, seed=1, seconds=None):
    """Mono float64 array of a model. `seconds` overrides the model's own length."""
    bad = problems(model)
    if bad:
        raise ValueError('sound model: ' + '; '.join(bad))
    sec = float(seconds if seconds is not None else model.get('seconds', 1.0))
    out = np.zeros(int(round(sec * sr)))
    for i, v in enumerate(model['voices']):
        out += render_voice(v, sec, sr, seed, i)
    return out


def describe():
    lines = []
    for title, table in (('excite', EXCITE), ('resonator', RESONATOR), ('events', EVENTS)):
        lines.append(f'{title}:')
        for kind, params in table.items():
            ps = ', '.join(f'{k}={_spec_default(v)!r}' + (f' [{v[1]}..{v[2]}]' if isinstance(v, tuple) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v) else '')
                           for k, v in params.items())
            lines.append(f'  {kind:11s} {ps}')
    lines.append('mode laws: ' + ', '.join(CHOICES['law']))
    lines.append('vary: size{dist,sigma,rate_mm_h,min,max}, pitch_exp, amp_exp, level_spread_db   control: gain_db [curve|lfo|ou|env]')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['render', 'check', 'laws'])
    ap.add_argument('model', nargs='?')
    ap.add_argument('--out', default=None)
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    if a.cmd == 'laws':
        print(describe())
        return
    if not a.model:
        sys.exit('give a model JSON file')
    model = json.load(open(a.model, encoding='utf-8'))
    model = model.get('model', model)
    bad = problems(model)
    if a.cmd == 'check':
        print('\n'.join(bad) if bad else 'ok: no problems')
        sys.exit(1 if bad else 0)
    if bad:
        sys.exit('\n'.join(bad))
    import soundfile as sf
    x = render(model, SR, a.seed, a.seconds)
    x = x / (np.abs(x).max() + 1e-12) * 0.9
    out = a.out or a.model.rsplit('.', 1)[0] + '.wav'
    sf.write(out, x.astype(np.float32), SR)
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
