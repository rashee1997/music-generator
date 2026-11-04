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
"""sfx.py - sound effects for film, games and music beds, made deterministically by code and DSP.

    python3 scripts/sfx.py list
    python3 scripts/sfx.py make whoosh --seconds 2.5 --out whoosh.wav [--seed 1]
    python3 scripts/sfx.py selftest

All generators use deterministic synthesis and physical DSP, fully reproducible per seed.
Every generator returns a mono float array at `sr`, peak about 0.9 unless normalize=False.
Research notes: references/sound-design/sound-effects.md.
"""
import argparse
import os
import sys

import numpy as np
from scipy.signal import butter, sosfilt
import pedalboard as pb

SR = 44100
SKILL = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


# ------------------------------------------------------------------ building blocks
def _n(sec, sr):
    return int(round(sec * sr))


def _t(sec, sr):
    return np.arange(_n(sec, sr)) / sr


def _noise(rng, n):
    return rng.standard_normal(n)


def _bp(x, lo, hi, sr, order=2):
    lo, hi = max(lo, 20.0), min(hi, sr / 2 - 100)
    return sosfilt(butter(order, [lo, hi], btype='band', fs=sr, output='sos'), x)


def _lp(x, f, sr, order=2):
    return sosfilt(butter(order, min(f, sr / 2 - 100), btype='low', fs=sr, output='sos'), x)


def _hp(x, f, sr, order=2):
    return sosfilt(butter(order, max(f, 20.0), btype='high', fs=sr, output='sos'), x)


def _sweep_bp(x, f0, f1, sr, bw=0.35):
    """Band-pass whose centre glides from f0 to f1 (block-wise, cheap and smooth enough for effects)."""
    out = np.zeros_like(x)
    block = 256
    for i in range(0, len(x), block):
        f = f0 + (f1 - f0) * (i / max(len(x), 1))
        seg = x[max(0, i - 128):i + block + 128]
        y = _bp(seg, f * (1 - bw), f * (1 + bw), sr)
        out[i:i + block] = y[min(128, i):min(128, i) + len(out[i:i + block])]
    return out


def _chirp(t, f0, f1, dur):
    """Phase of a glide from f0 to f1 over dur (linear in frequency)."""
    k = (f1 - f0) / max(dur, 1e-9)
    return 2 * np.pi * (f0 * t + 0.5 * k * t * t)


def _decay(t, tau):
    return np.exp(-t / tau)


# ------------------------------------------------------------------ Pedalboard DSP processors
def apply_lofi(x, sr=SR, bit_depth=8, gsm=False, mp3=False):
    """Degrade audio with vintage sampler bitcrush, telephone GSM or early MP3 codecs."""
    arr = x[np.newaxis, :] if x.ndim == 1 else x.T
    chain = []
    if bit_depth and bit_depth < 16:
        chain.append(pb.Bitcrush(bit_depth=float(bit_depth)))
    if gsm:
        chain.append(pb.GSMFullRateCompressor())
    if mp3:
        chain.append(pb.MP3Compressor(vbr_quality=2.0))
    if not chain:
        return x
    board = pb.Pedalboard(chain)
    out = board(arr, sr)
    return (out[0] if x.ndim == 1 else out.T).astype(np.float32)


def apply_ladder_filter(x, sr=SR, cutoff_hz=1000.0, resonance=0.6, drive=1.0):
    """Moog 4-pole 24 dB/oct resonant ladder filter for analog sweeps and cinematic sound design."""
    arr = x[np.newaxis, :] if x.ndim == 1 else x.T
    board = pb.Pedalboard([
        pb.LadderFilter(mode=pb.LadderFilter.Mode.LPF24,
                        cutoff_hz=float(cutoff_hz),
                        resonance=float(resonance),
                        drive=float(drive))
    ])
    out = board(arr, sr)
    return (out[0] if x.ndim == 1 else out.T).astype(np.float32)


def apply_delay(x, sr=SR, delay_seconds=0.25, feedback=0.35, mix=0.3):
    """Stereo / mono tempo-synced delay echo with feedback and damping."""
    arr = x[np.newaxis, :] if x.ndim == 1 else x.T
    board = pb.Pedalboard([
        pb.Delay(delay_seconds=float(delay_seconds), feedback=float(feedback), mix=float(mix))
    ])
    out = board(arr, sr)
    return (out[0] if x.ndim == 1 else out.T).astype(np.float32)


def _norm(x, peak=0.9):
    m = np.abs(x).max()
    return x * (peak / m) if m > 1e-12 else x


def _place(x, pos_sec, sr, total):
    out = np.zeros(total)
    i = int(pos_sec * sr)
    seg = x[:max(0, total - i)]
    out[i:i + len(seg)] += seg
    return out


# ------------------------------------------------------------------ generators
# each: gen(seconds, sr, rng, **kw) -> mono float array
def whoosh(sec, sr, rng, **kw):
    t = _t(sec, sr)
    env = np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 2
    return _sweep_bp(_noise(rng, len(t)), 400, 3200, sr) * env


def riser(sec, sr, rng, **kw):
    t = _t(sec, sr)
    f = 90 + (900 - 90) * (t / sec) ** 2
    phase = np.cumsum(2 * np.pi * f / sr)
    saw = sum(np.sin(k * phase) / k for k in range(1, 14))
    bright = _lp(_noise(rng, len(t)), 4000, sr) * (0.1 + 0.9 * (t / sec) ** 2) * 0.6    # brightens as it rises
    return (saw * 0.5 + bright) * (t / sec) ** 1.5


def downlifter(sec, sr, rng, **kw):
    t = _t(sec, sr)
    f = 900 - 800 * (t / sec)
    phase = np.cumsum(2 * np.pi * f / sr)
    tone = sum(np.sin(k * phase) / k for k in range(1, 10))
    return (tone * 0.5 + _lp(_noise(rng, len(t)), 2000, sr) * 0.4) * (1 - t / sec) ** 1.5


def impact(sec, sr, rng, **kw):
    t = _t(sec, sr)
    sub = np.sin(2 * np.pi * (48 - 14 * np.minimum(t, 0.4) / 0.4) * t) * _decay(t, 0.9)
    crack = _lp(_noise(rng, len(t)), 3500, sr) * _decay(t, 0.05)
    return sub + 0.6 * crack


def boom(sec, sr, rng, **kw):
    t = _t(sec, sr)
    body = np.sin(2 * np.pi * (62 - 25 * (1 - np.exp(-t / 0.2))) * t) * _decay(t, sec / 3.5)
    return body + 0.25 * _lp(_noise(rng, len(t)), 180, sr) * _decay(t, sec / 2)


def hit(sec, sr, rng, **kw):
    t = _t(sec, sr)
    click = _hp(_noise(rng, len(t)), 2500, sr) * _decay(t, 0.006)
    body = np.sin(2 * np.pi * 190 * t) * _decay(t, 0.09)
    return click * 0.8 + body


def rain(sec, sr, rng, density=70, **kw):
    t = _t(sec, sr)
    bed = _bp(_noise(rng, len(t)), 1200, 7000, sr) * 0.25
    out = bed.copy()
    for _ in range(int(density * sec)):
        i = int(rng.uniform(0, len(t)))
        d = _n(0.02, sr)
        f = rng.uniform(2500, 5500)
        seg = np.sin(2 * np.pi * f * np.arange(d) / sr) * np.exp(-np.arange(d) / (sr * 0.004))
        out[i:i + d] += seg[:len(out[i:i + d])] * rng.uniform(0.1, 0.4)
    return out


def wind(sec, sr, rng, **kw):
    t = _t(sec, sr)
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * (0.09 * t) + 0.8 * np.sin(2 * np.pi * 0.023 * t))
    return _lp(_noise(rng, len(t)), 420, sr, order=3) * gust * 3.0


def ocean(sec, sr, rng, **kw):
    t = _t(sec, sr)
    waves = np.sin(np.pi * t / 4.5) ** 2 * 0.8 + 0.2
    return _lp(_noise(rng, len(t)), 700, sr, order=3) * waves * 2.5


def fire(sec, sr, rng, **kw):
    t = _t(sec, sr)
    rumble = _lp(_noise(rng, len(t)), 220, sr) * 0.7
    out = rumble.copy()
    for _ in range(int(25 * sec)):
        i = int(rng.uniform(0, len(t)))
        d = _n(0.012, sr)
        crackle = _noise(rng, d) * np.exp(-np.arange(d) / (sr * 0.002)) * rng.uniform(0.2, 0.7)
        out[i:i + d] += crackle[:len(out[i:i + d])]
    return out


def crickets(sec, sr, rng, **kw):
    t = _t(sec, sr)
    pulse = (np.sin(2 * np.pi * 18 * t) > 0.6).astype(float)
    tone = np.sin(2 * np.pi * 4500 * t) * pulse * 0.25
    return tone + _bp(_noise(rng, len(t)), 3000, 6000, sr) * 0.05


def birdsong(sec, sr, rng, **kw):
    out = np.zeros(_n(sec, sr))
    pos = rng.uniform(0, 0.4)
    while pos < sec - 0.15:
        d = rng.uniform(0.07, 0.22)
        f0 = rng.uniform(2200, 3400)
        f1 = f0 * rng.uniform(0.7, 1.4)                  # each call is a short glide up or down
        t = _t(d, sr)
        note = np.sin(_chirp(t, f0, f1, d)) * np.sin(np.pi * t / d) ** 0.5
        out = out + _place(note * 0.5, pos, sr, len(out))
        pos += d + rng.uniform(0.06, 0.5)
    return out


def footstep(sec, sr, rng, surface='wood', **kw):
    t = _t(sec, sr)
    if surface == 'gravel':
        crunch = _bp(_noise(rng, len(t)), 1200, 5000, sr) * _decay(t, 0.025)
        return crunch * (1 + 0.5 * (rng.random(len(t)) > 0.97))
    thump = np.sin(2 * np.pi * 110 * t) * _decay(t, 0.05)
    return thump * 0.8 + _lp(_noise(rng, len(t)), 900, sr) * _decay(t, 0.03) * 0.5


def door_creak(sec, sr, rng, **kw):
    t = _t(sec, sr)
    f = 170 + 45 * np.sin(2 * np.pi * (0.7 * t) + 0.5 * np.sin(2 * np.pi * 2.3 * t))
    tone = np.sin(np.cumsum(2 * np.pi * f / sr)) * 0.4 + 0.3 * np.sin(np.cumsum(2 * np.pi * 2.02 * f / sr)) * 0.3
    env = np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 0.5
    return (tone + _bp(_noise(rng, len(t)), 1100, 2400, sr) * 0.15) * env


def glass_break(sec, sr, rng, **kw):
    t = _t(sec, sr)
    partials = [1.0, 2.32, 4.25, 6.63, 9.38]
    base = rng.uniform(1800, 2600)
    tone = sum(np.sin(2 * np.pi * base * p * t) * _decay(t, 0.25 / (i + 1)) for i, p in enumerate(partials)) / 3
    tinkle = np.zeros_like(t)
    for _ in range(14):
        i = int(rng.uniform(0, 0.25) * sr)
        tinkle[i:] += np.sin(2 * np.pi * rng.uniform(3000, 7000) * t[:len(t) - i]) * _decay(t[:len(t) - i], 0.03) * 0.2
    return tone + tinkle + _hp(_noise(rng, len(t)), 4000, sr) * _decay(t, 0.03)


def explosion(sec, sr, rng, **kw):
    t = _t(sec, sr)
    rumble = np.sin(2 * np.pi * (55 - 20 * (1 - np.exp(-t / 0.3))) * t) * _decay(t, sec / 3)
    debris = _bp(_noise(rng, len(t)), 300, 3000, sr) * _decay(t, sec / 4) * 0.6
    return rumble * 1.1 + debris + _lp(_noise(rng, len(t)), 150, sr) * _decay(t, 0.05)


def gunshot(sec, sr, rng, **kw):
    t = _t(sec, sr)
    crack = _hp(_noise(rng, len(t)), 1500, sr) * _decay(t, 0.012)
    thump = np.sin(2 * np.pi * 75 * t) * _decay(t, 0.09)
    tail = _bp(_noise(rng, len(t)), 500, 2500, sr) * _decay(t, sec / 3) * 0.3
    return crack + thump * 0.9 + tail


def laser(sec, sr, rng, **kw):
    t = _t(sec, sr)
    f = 1800 * (200 / 1800) ** (t / sec) * (1 + 0.04 * np.sin(2 * np.pi * 30 * t))
    return np.sin(np.cumsum(2 * np.pi * f / sr)) * np.exp(-t / (sec * 0.6))


def ui_blip(sec, sr, rng, **kw):
    t = _t(sec, sr)
    f = 880 * (1.5 ** (t / sec))
    return np.sin(np.cumsum(2 * np.pi * f / sr)) * np.sin(np.pi * np.clip(t / sec, 0, 1))


def coin(sec, sr, rng, **kw):
    out = np.zeros(_n(sec, sr))
    for i, f in enumerate([1320, 1760]):
        t = _t(0.22, sr)
        out = out + _place(np.sin(2 * np.pi * f * t) * _decay(t, 0.09), i * 0.07, sr, len(out))
    return out


def heartbeat(sec, sr, rng, **kw):
    out = np.zeros(_n(sec, sr))
    for beat in np.arange(0, sec, 0.9):
        for off, amp in [(0.0, 1.0), (0.28, 0.6)]:
            t = _t(0.18, sr)
            thump = np.sin(2 * np.pi * (55 - 15 * t / 0.18) * t) * _decay(t, 0.05) * amp
            out = out + _place(thump, beat + off, sr, len(out))
    return out


def thunder(sec, sr, rng, **kw):
    t = _t(sec, sr)
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.35 * t + rng.uniform(0, 6))
    rumble = _lp(_noise(rng, len(t)), 140, sr, order=3) * mod * _decay(t, sec / 1.5)
    crack = _hp(_noise(rng, len(t)), 500, sr) * _decay(t, 0.25) * 0.8
    return rumble * 4 + crack * np.exp(-t / 0.5)


def clock_tick(sec, sr, rng, **kw):
    t = _t(sec, sr)
    return np.sin(2 * np.pi * 2500 * t) * _decay(t, 0.008)


def electric_hum(sec, sr, rng, mains=50, **kw):
    t = _t(sec, sr)
    hum = sum(np.sin(2 * np.pi * mains * k * t) / k for k in (1, 2, 3))
    return hum * 0.5 + _lp(_noise(rng, len(t)), 400, sr) * 0.02


def water_drip(sec, sr, rng, **kw):
    out = np.zeros(_n(sec, sr))
    for pos in np.sort(rng.uniform(0, sec, max(1, int(sec * 0.6)))):
        t = _t(0.12, sr)
        f = 1200 * (500 / 1200) ** (t / 0.12)
        out = out + _place(np.sin(np.cumsum(2 * np.pi * f / sr)) * _decay(t, 0.03), pos, sr, len(out))
    return out


def shutter(sec, sr, rng, **kw):
    t = _t(sec, sr)
    click = _hp(_noise(rng, len(t)), 3000, sr) * _decay(t, 0.006)
    blip = np.sin(2 * np.pi * 2000 * t) * _decay(t, 0.02) * 0.5
    return click + blip


def typewriter(sec, sr, rng, **kw):
    out = np.zeros(_n(sec, sr))
    for pos in np.sort(rng.uniform(0, sec, max(1, int(sec * 6)))):
        t = _t(0.03, sr)
        out = out + _place(_bp(_noise(rng, len(t)), 1800, 5000, sr) * _decay(t, 0.004), pos, sr, len(out))
    return out


def sword_swing(sec, sr, rng, **kw):
    t = _t(sec, sr)
    f = 620 * (300 / 620) ** (t / sec)
    body = _sweep_bp(_noise(rng, len(t)), 900, 2600, sr, bw=0.2) * np.sin(np.pi * t / sec) ** 2
    return body + 0.2 * np.sin(np.cumsum(2 * np.pi * f / sr)) * np.sin(np.pi * t / sec)


GENERATORS = {
    'whoosh': whoosh, 'riser': riser, 'downlifter': downlifter, 'impact': impact, 'boom': boom, 'hit': hit,
    'rain': rain, 'wind': wind, 'ocean': ocean, 'fire': fire, 'crickets': crickets, 'birdsong': birdsong,
    'footstep': footstep, 'door_creak': door_creak, 'glass_break': glass_break, 'explosion': explosion,
    'gunshot': gunshot, 'laser': laser, 'ui_blip': ui_blip, 'coin': coin, 'heartbeat': heartbeat,
    'thunder': thunder, 'clock_tick': clock_tick, 'electric_hum': electric_hum, 'water_drip': water_drip,
    'shutter': shutter, 'typewriter': typewriter, 'sword_swing': sword_swing,
}


# ------------------------------------------------------------------ the check an effect output must pass
def acceptable(x, sr, seconds):
    """An effect is valid only if it is finite, the right length, not silent, not a bare tone and not clicky."""
    if not np.isfinite(x).all():
        return False, 'not finite'
    if abs(len(x) / sr - seconds) > 0.1 * seconds + 0.05:
        return False, f'length {len(x) / sr:.2f}s, asked {seconds}s'
    rms = np.sqrt(np.mean(x ** 2))
    if 20 * np.log10(rms + 1e-12) < -50:
        return False, 'silent'
    if np.abs(x).max() > 1.0001:
        return False, 'over full scale'
    crest = np.abs(x).max() / (rms + 1e-12)
    if crest < 2.5:
        return False, f'crest {crest:.1f}: a steady tone, not an event'
    from quality_gate import find_clicks          # isolated jumps only: a dense noise burst is not a click
    clicks = find_clicks(x)
    if len(clicks):
        return False, f'{len(clicks)} isolated click(s)'
    return True, 'ok'


# Ambience (a place that keeps sounding) is an environments preset: rain, water and birds there are physical models with
# rate, surface and distance. These seven names stay only so older scores render; sfx:<name> in a project is an error.
AMBIENCE = ('rain', 'wind', 'ocean', 'fire', 'crickets', 'birdsong', 'electric_hum')
MIX_KEYS = {'role', 'gain_db', 'pan', 'spatial', 'reverb', 'width', 'eq', 'comp', 'hp', 'lp', 'chain', 'saturation', 'mono_below',
            'duck_by', 'duck_db', 'widen', 'fade_in_s', 'fade_out_s', 'target_lufs'}      # where it sits in the mix; the mixer reads them from the preset
PRESET_KEYS = {'name', 'kind', 'character', 'description', 'note', 'generator', 'params', 'spec', 'model', 'scene',
               'seconds', 'sources'} | MIX_KEYS


def _generator_params(gen):
    """Parameter names a generator accepts besides (sec, sr, rng, **kw)."""
    import inspect
    return [k for k in inspect.signature(GENERATORS[gen]).parameters if k not in ('sec', 'sr', 'rng', 'kw')]


def preset_problems(cfg):
    """Problems in a one-hit effect preset (empty = good). An unknown key is an error, never ignored."""
    out = [f'unknown key "{k}" (known: {", ".join(sorted(PRESET_KEYS))})' for k in cfg if k not in PRESET_KEYS and not k.startswith('_')]
    gen, spec = cfg.get('generator'), cfg.get('spec')
    if gen is None and spec is None and cfg.get('model') is None and cfg.get('scene') is None:
        out.append('needs "scene" (the physical scene: materials, objects, interactions; physical.py laws), '
                   '"model" (voices: excitation, resonator, events; sound_model.py laws), "generator" (a built-in '
                   'recipe, sfx.py list) or "spec" (a legacy layer spec)')
    if cfg.get('scene') is not None:
        import phys_core.scene as _scene
        out += [f'scene: {p}' for p in _scene.problems(cfg['scene'])]
    if cfg.get('model') is not None:
        import sound_model
        out += [f'model: {p}' for p in sound_model.problems(cfg['model'])]
    if gen is not None and gen not in GENERATORS:
        out.append(f'unknown generator "{gen}"; known: {", ".join(GENERATORS)}')
    elif gen is not None:
        ok = _generator_params(gen)
        out += [f'params "{k}" is not a parameter of {gen} (it takes: {", ".join(ok) or "none"})' for k in cfg.get('params', {}) if k not in ok]
    if spec is not None:
        for layer in spec.get('layers', []):
            if layer.get('kind') not in ('noise', 'glide', 'tone', 'click'):
                out.append(f'spec layer kind "{layer.get("kind")}": use noise, glide, tone or click')
        if not spec.get('layers'):
            out.append('spec has no layers')
    return out


def make(name, seconds=2.0, sr=SR, seed=1, normalize=True, **kw):
    """Return (mono array, 'code', note). The sound comes from the preset called `name` (project first, then the skill's
    default) or, when there is none, from the built-in recipe of that name. Same seed, same sound."""
    # One implementation, in scripts/sfx_engine/oneshot.py (scene -> model -> spec -> generator). This facade keeps
    # its old contract: the same array, the same note, and 'preset' where the engine says 'model'.
    from sfx_engine import oneshot as _oneshot
    x, source, note = _oneshot.make(name, seconds, sr, seed, normalize=normalize, **kw)
    return x, ('preset' if source == 'model' else source), note


def timeline(items, total_sec, sr=SR, seed=1, **kw):
    """Lay effects on a stereo bed. items: dicts with name, at (s), seconds, gain_db, pan (-1..1), optional kw.
    Returns (N, 2) float32. Generated deterministically via procedural DSP."""
    out = np.zeros((_n(total_sec, sr), 2))
    for i, it in enumerate(items):
        item_kw = dict(it.get('kw', {}))
        x, _, _ = make(it['name'], it.get('seconds', 2.0), sr, seed + i, **item_kw)
        x = x * 10 ** (it.get('gain_db', 0.0) / 20)
        pan = np.clip(it.get('pan', 0.0), -1, 1)
        l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
        start = int(it['at'] * sr)
        seg = x[:max(0, len(out) - start)]
        out[start:start + len(seg), 0] += seg * l
        out[start:start + len(seg), 1] += seg * r
    return out.astype(np.float32)


# ------------------------------------------------------------------ dynamic: any sound from a parameter spec
# The 28 named effects above are a starting set. A spec builds any sound from layers, so a new effect is data:
#   {"seconds": 2.0, "layers": [
#       {"kind": "noise", "band": [800, 4000], "env": {"attack": 0.3, "decay": 0.8}, "gain": 0.6},
#       {"kind": "glide", "f0": 200, "f1": 1200, "env": {"attack": 0.5, "decay": 0.5}, "gain": 0.4, "harmonics": 4},
#       {"kind": "click", "rate": 6, "tau": 0.01, "band": [2000, 6000], "gain": 0.5},
#       {"kind": "tone", "f": 220, "env": {"attack": 0.05, "decay": 0.3}, "gain": 0.3}]}
# env: attack and decay are fractions of the length (attack in 0..1, decay as an exponential time constant in seconds
# when given as "tau"). Every layer is seeded, so a spec gives the same sound each time.
def _env(n, sr, env):
    t = np.arange(n) / sr
    dur = n / sr
    a = float(env.get('attack', 0.0)) * dur
    e = np.ones(n)
    if a > 0:
        e *= np.clip(t / a, 0, 1)
    if 'tau' in env:
        e *= np.exp(-t / float(env['tau']))
    elif 'decay' in env:
        e *= np.exp(-t / max(float(env['decay']) * dur, 1e-3))
    return e


def synth(spec, sr=SR, seed=1):
    """Build a mono sound from a layer spec (see the notes above). Returns a float array peaking near 0.9."""
    rng = np.random.default_rng(seed)
    n = _n(float(spec['seconds']), sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    for layer in spec.get('layers', []):
        kind = layer['kind']
        g = float(layer.get('gain', 1.0))
        env = _env(n, sr, layer.get('env', {}))
        if kind == 'noise':
            x = _bp(_noise(rng, n), *layer.get('band', [200, 8000]), sr) if 'band' in layer else _noise(rng, n)
        elif kind == 'glide':
            f = layer['f0'] * (layer['f1'] / layer['f0']) ** (t / (n / sr))
            ph = np.cumsum(2 * np.pi * f / sr)
            x = sum(np.sin(k * ph) / k for k in range(1, int(layer.get('harmonics', 1)) + 1))
        elif kind == 'tone':
            x = np.sin(2 * np.pi * float(layer['f']) * t)
        elif kind == 'click':
            x = np.zeros(n)
            for pos in np.sort(rng.uniform(0, n / sr, max(1, int(float(layer.get('rate', 4)) * n / sr)))):
                i = int(pos * sr)
                d = min(_n(0.05, sr), n - i)
                seg = _noise(rng, d) * np.exp(-np.arange(d) / (float(layer.get('tau', 0.01)) * sr))
                x[i:i + d] += seg
            if 'band' in layer:
                x = _bp(x, *layer['band'], sr)
        else:
            raise ValueError(f'unknown layer kind {kind}: use noise, glide, tone or click')
        out += g * x * env
    return _norm(out)


def selftest():
    spec = {'seconds': 1.5, 'layers': [{'kind': 'noise', 'band': [800, 4000], 'env': {'attack': 0.3, 'decay': 0.8}},
                                       {'kind': 'glide', 'f0': 200, 'f1': 1200, 'env': {'attack': 0.5, 'decay': 0.5}, 'gain': 0.4}]}
    x = synth(spec, SR, seed=3)
    assert np.isfinite(x).all() and abs(len(x) - _n(1.5, SR)) <= 2 and np.abs(x).max() > 0.5
    assert np.array_equal(x, synth(spec, SR, seed=3)), 'a spec must be deterministic for a seed'
    print('ok: a parameter spec builds a finite, deterministic sound')
    rng = np.random.default_rng(0)
    for name, g in GENERATORS.items():
        x = np.asarray(g(1.2, SR, np.random.default_rng(2)), dtype=float)
        assert np.isfinite(x).all(), f'{name}: not finite'
        assert abs(len(x) - _n(1.2, SR)) <= 2, f'{name}: wrong length {len(x)}'
        assert np.abs(x).max() > 1e-4, f'{name}: silent'
        x2 = np.asarray(g(1.2, SR, np.random.default_rng(2)), dtype=float)
        assert np.array_equal(x, x2), f'{name}: not deterministic for a seed'
    print(f'ok: {len(GENERATORS)} effects: finite, right length, not silent, deterministic per seed')
    ok_tone = acceptable(0.5 * np.sin(2 * np.pi * 440 * np.arange(SR) / SR), SR, 1.0)[0]
    ok_hit = acceptable(_norm(GENERATORS['hit'](1.0, SR, rng)), SR, 1.0)[0]
    assert not ok_tone and ok_hit, 'the audio acceptable check should reject a bare tone and accept a hit'
    print('ok: the audio acceptable check rejects a bare tone and accepts a hit')
    bed = timeline([dict(name='whoosh', at=0.2, seconds=1.5), dict(name='impact', at=1.5, seconds=1.0, pan=-0.3)], 3.0)
    assert bed.shape == (_n(3.0, SR), 2) and np.abs(bed).max() > 0.1 and np.isfinite(bed).all()
    print('ok: timeline places two effects on a stereo bed')

    # Test Pedalboard DSP processors (lofi, ladder, delay)
    test_sig = 0.5 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR).astype(np.float32)
    lofi_out = apply_lofi(test_sig, SR, bit_depth=8)
    assert len(lofi_out) == len(test_sig) and np.isfinite(lofi_out).all()
    ladder_out = apply_ladder_filter(test_sig, SR, cutoff_hz=800.0, resonance=0.5)
    assert len(ladder_out) == len(test_sig) and np.isfinite(ladder_out).all()
    delay_out = apply_delay(bed, SR, delay_seconds=0.2, feedback=0.3, mix=0.3)
    assert delay_out.shape == bed.shape and np.isfinite(delay_out).all()
    print('ok: pedalboard lofi, ladder filter, and delay processors verified')
    import presets
    for name in GENERATORS:                                   # every one-hit effect has a shipped default, and it is the recipe unchanged
        cfg = presets.find_sfx(name)
        if name in AMBIENCE:
            assert cfg is None, f'{name}: ambience must not ship as an sfx preset'
            continue
        assert cfg is not None and not preset_problems(cfg), f'{name}: shipped default missing or invalid'
        a = make(name, 1.0, SR, 5)[0]
        assert np.array_equal(a, _norm(np.asarray(GENERATORS[name](1.0, SR, np.random.default_rng(5)), dtype=float))), f'{name}: default differs from the recipe'
    assert preset_problems(dict(generator='hit', params=dict(nope=1), colour=3)), 'unknown keys must be reported'
    print('ok: shipped one-hit defaults match the recipes; unknown preset keys are reported')
    print('selftest passed')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', nargs='?', choices=['list', 'make', 'selftest', 'spec'])
    ap.add_argument('--selftest', action='store_true', help='run the selftest (same as the "selftest" command)')
    ap.add_argument('name', nargs='?', help='for "spec": a JSON file with the layer spec')
    ap.add_argument('--seconds', type=float, default=2.0)
    ap.add_argument('--out', default=None)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--project', default=None, help='use presets/sfx/ of this project before the skill defaults')
    a = ap.parse_args()
    if a.selftest:
        a.cmd = 'selftest'
    if not a.cmd:
        ap.error('give a command: list, make, selftest, spec')
    if a.project:
        import presets
        presets.add_project(a.project)
    if a.cmd == 'list':
        for k in GENERATORS:
            print(k + ('   (ambience: use an environments preset)' if k in AMBIENCE else ''))
        return
    if a.cmd == 'selftest':
        selftest()
        return
    import soundfile as sf
    if a.cmd == 'spec':
        import json
        x = synth(json.load(open(a.name, encoding='utf-8')), SR, a.seed)
        out = a.out or os.path.splitext(a.name)[0] + '.wav'
        sf.write(out, x.astype(np.float32), SR)
        print(f'wrote {out}  (dynamic, from {a.name})')
        return
    x, used, note = make(a.name, a.seconds, SR, a.seed)
    out = a.out or f'{a.name}.wav'
    sf.write(out, x.astype(np.float32), SR)
    print(f'wrote {out}  backend={used}  {note}')


if __name__ == '__main__':
    main()
