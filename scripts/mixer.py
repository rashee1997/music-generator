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
"""mixer.py - the mixing + mastering engine (gain staging, EQ, dynamics, sidechain, space, stereo, loudness).

Use it three ways:
  * automatically from render_natural.py (mix_and_master)
  * on any set of stems:   python3 mixer.py stems_dir/ --mix mix.json --out final.wav
  * as a library:          import mixer; mixer.mix_and_master(score, stems, "out.wav")

Order of operations (what a mix engineer does, and the order this file follows):
  1. GAIN STAGING   - the playing part of a stem is brought to a reference loudness, then `gain_db`.
  2. EQ             - a spectral profile (rain, wind, voice, strings ...) or the role's starting chain.
  3. DYNAMICS       - a compressor; Pedalboard by default, the full DSP compressor when a preset asks.
  4. LOW END        - mono below ~120 Hz for bass, and for anything that asks.
  5. LEVEL          - the role/track `gain_db`, the fades and the optional speech/documentary swell.
  6. PLACE          - width, widen, pan, distance air loss, 1/r falloff, binaural route, DRR send.
  7. SPACE          - one shared reverb bus (a synthesised impulse response).
  8. SIDECHAIN      - optional ducking, band-limited by default.
  9. MASTER         - glue, tone, limiter, loudness to a target with a true-peak ceiling.

Configuration: every number comes from a mix preset (references/presets/mix/default.json, plus the
project's own) with the schema defaults in mix_schema.py underneath. `mix_context.resolve()` resolves a
piece's configuration once; the module-level names below are views of it, kept because the rest of the
skill and the tests read them. See references/mixing-and-mastering.md.
"""
import argparse
import json
import os
import sys
import zlib

import numpy as np
import soundfile as sf
from scipy import signal

import pedalboard as pb

import dsp
import mix_context
import mix_schema
import presets

SR = 44100
REF_LUFS = -24.0

_FALLBACK_MIX = mix_schema.with_defaults(presets.mix())   # what a bare import reads, with no context

# Schema defaults for the flat keys, used only when neither the piece's preset nor the schema names them.
DEFAULT_ACTIVE_DB = -55.0
DEFAULT_MAX_BOOST_DB = 12.0
DEFAULT_LEAD_BAND_HZ = 2000.0
DEFAULT_CARVE_DB = -4.0

STATE = {}           # the last mix: processed stems, sends, per-track gain, master measures, diagnostics


def _mix():
    """The mix preset of the piece being mixed on this thread (never another thread's)."""
    ctx = mix_context.current()
    return ctx.mix if ctx is not None else _FALLBACK_MIX


def _space():
    """The space preset of the piece being mixed on this thread."""
    ctx = mix_context.current()
    return (ctx.space if ctx is not None else None) or {}


def _gs():
    return _mix().get('gain_staging') or {}


def _active_db():
    return float(_gs().get('active_db', _mix().get('active_db', DEFAULT_ACTIVE_DB)))


def _max_boost_db():
    return float(_gs().get('max_boost_db', _mix().get('max_boost_db', DEFAULT_MAX_BOOST_DB)))


def _seating():
    return _mix().get('seating') or {}


def _widen_by_role():
    return _mix().get('widen_by_role') or {}


def _level_by_role():
    return _mix().get('level_by_role') or {}


def _lead_band_hz():
    return float(_mix().get('lead_band_hz', DEFAULT_LEAD_BAND_HZ))


def _carve_db():
    return float(_mix().get('carve_db', DEFAULT_CARVE_DB))


def _install(mix, space=None, ctx=None):
    """Make `mix` (and `space`) the active configuration for THIS THREAD, and return `mix`.

    The resolved values live in the thread-local MixContext, not in module globals: two pieces
    mixed in two threads each read their own preset, and nothing carries over from the piece mixed
    before. A bare import (no context installed) reads the shipped defaults.
    """
    if ctx is None:
        ctx = mix_context.MixContext(mix, {} if space is None else space,
                                     name=str(mix.get('name') or 'default'))
    mix_context.make_current(ctx)
    return mix


def release_stems():
    """Drop the mixed audio arrays; the measures, specs and rows stay for the report.

    `STATE['processed']` is what the gate measures, so it lives until Stage 6 has run. After that it is
    the largest thing this module holds (two float32 stereo buffers per stem) and nothing reads it again.
    """
    STATE.pop('processed', None)
    STATE.pop('sends', None)


def reset_context():
    """Forget this thread's context: later reads fall back to the shipped defaults."""
    mix_context.make_current(None)


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def to_stereo(x):
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    elif x.shape[1] == 1:
        x = np.repeat(x, 2, 1)
    elif x.shape[1] > 2:
        raise ValueError(f'a stem must be mono or stereo, got {x.shape[1]} channels')
    return x


def apply_dither(x, bits=16, shape='tpdf', rng=None):
    """Apply TPDF (triangular probability density function) dithering.
    
    bits: Target bit depth (16, 24). 24-bit dithering is subtle but safe.
    shape: 'tpdf' (standard) or 'rpdf' (rectangular).
    Returns dithered audio in same range.
    """
    if bits >= 32:
        return x
    if rng is None:
        rng = np.random.default_rng(12345)
    x = np.asarray(x, dtype=np.float64)
    # Quantization step
    scale = 2.0 ** bits
    q = 1.0 / scale
    if shape == 'tpdf':
        # TPDF: difference of two uniform random variables
        r1 = rng.random(x.shape)
        r2 = rng.random(x.shape)
        dither = (r1 - r2) * q
    elif shape == 'rpdf':
        r = rng.random(x.shape) - 0.5
        dither = r * q
    else:
        r1 = rng.random(x.shape)
        r2 = rng.random(x.shape)
        dither = (r1 - r2) * q
    y = x + dither
    # Apply quantization
    y = np.round(y * scale) / scale
    return y.astype(np.float32)


def apply_mid_side(x, mid_gain=1.0, side_gain=1.0):
    """Mid/side processing. mid_gain and side_gain are linear multipliers.
    Useful for stereo width control and center-focused processing.
    """
    if mid_gain == 1.0 and side_gain == 1.0:
        return x
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1 or x.shape[1] < 2:
        return x
    mid = (x[:, 0] + x[:, 1]) * 0.5
    side = (x[:, 0] - x[:, 1]) * 0.5
    mid = mid * mid_gain
    side = side * side_gain
    out = np.stack([mid + side, mid - side], axis=1)
    return out.astype(np.float32)


def lufs(x, sr=SR):
    x = to_stereo(x)
    if len(x) < int(0.5 * sr):
        x = np.pad(x, ((0, int(0.5 * sr) - len(x)), (0, 0)))
    try:
        v = dsp.meter(sr).integrated_loudness(x.astype(np.float64))
    except Exception:
        v = -70.0
    return -70.0 if not np.isfinite(v) else float(v)


def true_peak_db(x, sr=SR, over=4):
    return dsp.true_peak_db(x, sr, over)


def rms_db(x):
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12))


def _run(board, x, sr=SR):
    x = to_stereo(x)
    y = board(np.ascontiguousarray(x.T), sr)
    return np.ascontiguousarray(y.T)


def pan_stereo(x, pan, mode='legacy'):
    """Constant-power balance. pan -1..1 ; 0 leaves the stereo image untouched.

    mode='energy' keeps a stereo source's image (a -3 dB floor on the far channel instead of nulling it);
    'legacy' is the amplitude balance this engine has always used."""
    if mode == 'energy':
        return dsp.pan_energy(x, pan)
    th = (float(pan) + 1) * np.pi / 4
    gl, gr = np.cos(th) * np.sqrt(2), np.sin(th) * np.sqrt(2)
    return x * np.array([gl, gr], dtype=np.float32)


def width_ms(x, width):
    m = (x[:, 0] + x[:, 1]) / 2
    s = (x[:, 0] - x[:, 1]) / 2 * width
    return np.stack([m + s, m - s], 1).astype(np.float32)


def widen(x, amount=0.4, hp=250, seed=1, sr=SR, taps=2048):
    """Add stereo width WITHOUT hurting mono: a random-phase all-pass copy of the mid signal is added to
    L and subtracted from R (so L+R is unchanged). Only above `hp` Hz, so the low end stays centred."""
    if amount <= 0:
        return x
    rng = np.random.default_rng(seed)
    nb = taps // 2 + 1
    ph = rng.uniform(-np.pi, np.pi, nb)
    f = np.arange(nb) * sr / taps
    ph *= np.clip((f - hp) / hp, 0, 1)                      # no phase scrambling below hp
    ir = np.fft.irfft(np.exp(1j * ph), taps) * np.hanning(taps) ** 0.3
    mid = (x[:, 0] + x[:, 1]) / 2
    d = signal.fftconvolve(mid, ir, mode='full')[:len(mid)]
    sos = signal.butter(2, hp, 'high', fs=sr, output='sos')
    d = signal.sosfilt(sos, d) * amount
    return np.stack([x[:, 0] + d, x[:, 1] - d], 1).astype(np.float32)


def mono_below(x, hz=120, sr=SR):
    sos = signal.butter(4, hz, 'low', fs=sr, output='sos')
    low = signal.sosfiltfilt(sos, x, axis=0)
    mono = low.mean(1, keepdims=True)
    return (x - low + mono).astype(np.float32)


def fit(x, n):
    if len(x) >= n:
        return x[:n]
    return np.pad(x, ((0, n - len(x)), (0, 0)))

# ---------------------------------------------------------------------------------------------
# reverb: synthesised impulse responses (no IR files needed)
# ---------------------------------------------------------------------------------------------
ROOMS = {
    #            rt60  predelay(ms) HF-decay-factor  early-reflection level
    'dry':        (0.25, 0, 0.7, 0.0),
    'studio':     (0.55, 6, 0.75, 0.5),
    'room_warm':  (0.85, 8, 0.55, 0.5),
    'chamber':    (1.2, 12, 0.65, 0.5),
    'plate':      (1.8, 4, 0.85, 0.0),
    'hall':       (2.3, 24, 0.55, 0.4),
    'forest_canopy': (2.8, 18, 0.45, 0.35),
    'large_hall': (3.2, 34, 0.5, 0.35),
    'cathedral':  (5.2, 45, 0.45, 0.3),
    'cave':       (6.5, 60, 0.35, 0.2),
}

_IR_CACHE = {}          # one impulse response per (room description, sample rate, seed)
IR_CACHE_MAX = 8        # a scoring batch may visit many rooms; keep only the ones still in play


def resolve_space(name):
    """A space preset by name (the project's, else the shipped one), else a built-in ROOMS entry as a
    minimal preset, else {}."""
    if isinstance(name, dict):
        return name
    cfg = presets.find_space(name) if name else None
    if cfg:
        return cfg
    if name in ROOMS:
        r = ROOMS[name]
        return dict(room=dict(rt60=r[0], pre_delay_ms=r[1], hf_decay=r[2], early_level=r[3]))
    return {}


def _space_owned(cfg):
    """True when the space preset lives in the project (a shipped one is only a fallback)."""
    return mix_context.space_owned(cfg)


def make_ir(room='hall', sr=SR, seed=3):
    """Stereo IR: sparse early reflections + decorrelated noise tail whose highs die faster than lows."""
    if isinstance(room, dict):
        room = (room['room']['rt60'], room['room']['pre_delay_ms'], room['room']['hf_decay'],
                room['room']['early_level'])
    key = (json.dumps(room, sort_keys=True) if isinstance(room, dict) else str(room), sr, seed)
    space_cfg = _mix().get('space') or {}                   # the IR is built from the piece's space preset
    cache_ir = bool(space_cfg.get('cache_ir', mix_schema.DEFAULTS['space']['cache_ir']))
    cached = _IR_CACHE.get(key)
    if cached is not None and cache_ir:
        return cached
    rt60, pre, hf, er = ROOMS.get(room, ROOMS['hall']) if isinstance(room, str) else room
    rng = np.random.default_rng(seed)
    n = int((rt60 * 1.15 + pre / 1000.0 + 0.05) * sr)
    t = np.arange(n) / sr
    out = np.zeros((n, 2))
    bands = [((20, 500), 1.15), ((500, 3000), 1.0), ((3000, 9000), hf), ((9000, 18000), hf * 0.6)]
    for ch in range(2):
        acc = np.zeros(n)
        for (lo, hi), mult in bands:
            w = rng.standard_normal(n)
            sos = signal.butter(2, [lo, min(hi, sr / 2 - 100)], 'band', fs=sr, output='sos')
            w = signal.sosfilt(sos, w)
            env = np.exp(-6.9078 * t / (rt60 * mult))
            acc += w * env * (1.0 if hi < 9000 else 0.8)
        # diffuse onset (no hard click)
        acc *= 1 - np.exp(-t / 0.012)
        out[:, ch] = acc
    if er > 0:
        er_block = space_cfg.get('er') if isinstance(space_cfg.get('er'), dict) else {}
        er_level = float(er_block.get('level', (mix_schema.DEFAULTS['space'].get('er') or {}).get('level', 0.35)))
        # DRR from an explicit ratio: the taps used to be scaled by sqrt(peak) of the random noise tail, so the
        # early-to-late energy changed with every seed and room size. Now the tap gain sets ER RMS = er_level x tail RMS.
        tail_rms = float(np.sqrt(np.mean(out.astype(np.float64) ** 2)) + 1e-12)
        k = 12
        gains = 0.9 * 0.82 ** np.arange(k)
        tap = er_level * tail_rms / max(float(np.sqrt(np.sum(gains ** 2))), 1e-9)
        for ch in range(2):
            times = np.sort(rng.uniform(0.006, 0.085, k))
            for i, tt in enumerate(times):
                idx = int(tt * sr)
                out[idx, ch] += tap * gains[i] * rng.choice([-1, 1])
    pad = int(pre / 1000.0 * sr)
    out = np.vstack([np.zeros((pad, 2)), out])
    out /= np.sqrt((out ** 2).sum(0, keepdims=True).mean()) + 1e-12   # unit energy
    out = out.astype(np.float32)
    if cache_ir:
        if len(_IR_CACHE) >= IR_CACHE_MAX:
            _IR_CACHE.pop(next(iter(_IR_CACHE)))     # insertion order: the room used longest ago goes first
        _IR_CACHE[key] = out
    return out


def reverb_bus(x, room='hall', sr=SR, hp=150, lp=7500, seed=3, gated=False, gate_thr=-32.0, gate_release_ms=80.0):
    ir = make_ir(room, sr, seed)
    conv = pb.Pedalboard([pb.Convolution(ir.T.copy(), mix=1.0, sample_rate=sr)])
    x = np.pad(x, ((0, len(ir)), (0, 0)))               # room for the tail: pedalboard returns exactly len(input)
    wet = _run(conv, x, sr)
    chain = [pb.HighpassFilter(hp), pb.LowpassFilter(lp)]
    if gated:
        chain.append(pb.NoiseGate(threshold_db=gate_thr, release_ms=gate_release_ms))
    return _run(pb.Pedalboard(chain), wet, sr)

# ---------------------------------------------------------------------------------------------
# role chains / spectral profiles
# ---------------------------------------------------------------------------------------------

def _peak(f, g, q=1.0):
    return pb.PeakFilter(cutoff_frequency_hz=f, gain_db=g, q=q)


def _band(b):
    """One preset EQ band, normalised (f/freq, gain, q)."""
    return {'type': b.get('type', 'peak'), 'f': float(b.get('f', b.get('freq', 1000.0))),
            'gain': float(b.get('gain', 0.0)), 'q': float(b.get('q', 1.0)), 'order': b.get('order')}


def eq_object(b):
    """A preset EQ band as a Pedalboard filter. A band with an explicit `order` is applied by dsp."""
    b = _band(b)
    fn = EQ_TYPES.get(b['type'])
    if fn is None:
        raise ValueError(f'unknown EQ band type "{b["type"]}" (known: {", ".join(sorted(EQ_TYPES))})')
    return fn(b)


EQ_TYPES = {'peak': lambda d: pb.PeakFilter(d['f'], d.get('gain', 0), d.get('q', 1.0)),
            'bell': lambda d: pb.PeakFilter(d['f'], d.get('gain', 0), d.get('q', 1.0)),
            'notch': lambda d: pb.PeakFilter(d['f'], d.get('gain', -18.0), d.get('q', 2.0)),
            'hp': lambda d: pb.HighpassFilter(d['f']), 'highpass': lambda d: pb.HighpassFilter(d['f']),
            'lp': lambda d: pb.LowpassFilter(d['f']), 'lowpass': lambda d: pb.LowpassFilter(d['f']),
            'lowshelf': lambda d: pb.LowShelfFilter(d['f'], d.get('gain', 0), d.get('q', 0.7)),
            'highshelf': lambda d: pb.HighShelfFilter(d['f'], d.get('gain', 0), d.get('q', 0.7))}


def role_chain(role, mx=None):
    """The EQ + compression a role starts with, from the mix preset (schema defaults underneath)."""
    chains = (mx or _mix()).get('role_chains') or mix_schema.ROLE_CHAINS
    return chains.get(role) or chains.get('default') or {}


def spectral_chain(role, spec, mx=None):
    """(chain, source): a named spectral profile if the stem has one, else its role chain.

    "preserve_spectrum": true bypasses the automatic chain entirely — for a physically modelled source
    whose spectrum is the point.
    """
    mx = mx or _mix()
    if spec.get('preserve_spectrum'):
        return {}, 'bypassed'
    prof = spec.get('spectral_profile')
    profs = ((mx.get('spectral') or {}).get('profiles') or {})
    if prof and prof in profs:
        return profs[prof], f'profile:{prof}'
    if prof:
        raise ValueError(f'unknown spectral profile "{prof}" (known: {", ".join(sorted(profs))})')
    return role_chain(role, mx), f'role:{role}'


def _chain_objects(chain):
    out = [eq_object(b) for b in (chain.get('eq') or [])]
    c = chain.get('comp')
    if isinstance(c, dict):
        out.append(pb.Compressor(threshold_db=c.get('thr', -22), ratio=c.get('ratio', 2.5),
                                 attack_ms=c.get('attack', 15), release_ms=c.get('release', 150)))
    return out


def role_board(role, inst='', mx=None):
    """Starting-point EQ + compression per role. A preset's "role_chains" replaces one role."""
    return _chain_objects(role_chain(role, mx)) + inst_eq(inst)


def base_names(inst):
    """The names an instrument answers to, own name first: a preset called lead_flute is built on 'flute'
    (its gm / instrument key), and a world name such as quena stands in for a General MIDI sound."""
    name = str(inst).lower().replace(' ', '_')
    out = [name]
    try:
        cfg = presets.find_instrument(name) or presets.find_vocal(name) or {}
    except Exception:
        cfg = {}
    for key in ('gm', 'instrument'):
        v = cfg.get(key)
        if isinstance(v, str) and v.lower() not in out:
            out.append(v.lower().replace(' ', '_'))
    import world
    for n in list(out):
        w = world.INSTRUMENTS.get(n)
        if isinstance(w, str) and w not in out:
            out.append(w)
    return out


def from_table(table, inst, default=None):
    """First hit of `table` for the instrument's own name, then its base names."""
    for n in base_names(inst):
        if n in table:
            return table[n]
    return default


def inst_eq(inst):
    """The instrument's tone moves, from the mix preset's inst_eq table."""
    return [eq_object(b) for b in from_table(_mix().get('inst_eq') or {}, inst, [])]

# ---------------------------------------------------------------------------------------------
# sidechain / ducking (control-rate envelope follower)
# ---------------------------------------------------------------------------------------------

def envelope(x, sr=SR, attack_ms=8, release_ms=150, rate=400, hold_tail=False):
    """Peak envelope of `x` at `sr` samples/s using an attack/release follower at a coarse control rate."""
    return dsp.envelope(x, sr, attack_ms, release_ms, rate, hold_tail)


DUCK_BAND_ROLES = ('pad', 'chord', 'arp', 'counter', 'environment')   # ducked in the lead's band, not full-band
DUCK_BAND_HZ = (250.0, 3800.0)
DUCK_RESIDUAL = 0.3


def duck_gain(source, n, depth_db=-6, thresh=0.05, attack_ms=8, release_ms=180, sr=SR, lookahead_ms=10, smooth_s=0.0):
    """Gain curve (linear) that dips by depth_db while `source` is above threshold; smooth like a compressor."""
    src = fit(to_stereo(source), n)
    e = envelope(src, sr, attack_ms, release_ms, hold_tail=True)
    k = np.clip((e - thresh * 0.3) / (thresh * 1.2), 0, 1)           # 0..1 how much to duck
    gain_curve = 10 ** (depth_db * k / 20.0)
    min_floor = 10 ** (depth_db / 20.0)
    gain_curve = np.clip(gain_curve, min_floor, 1.0)
    if smooth_s > 0:
        cutoff_hz = max(0.5, min(20.0, 1.0 / smooth_s))
        sos_sm = signal.butter(1, cutoff_hz, btype='lowpass', fs=sr, output='sos')
        gain_curve = signal.sosfiltfilt(sos_sm, gain_curve)
        gain_curve = np.clip(gain_curve, min_floor, 1.0)
    if lookahead_ms:                     # shift AFTER smoothing: a zero-phase average used to undo the lookahead
        sh = int(lookahead_ms / 1000 * sr)
        if sh > 0:
            gain_curve = np.concatenate([gain_curve[sh:], np.full(sh, gain_curve[-1] if len(gain_curve) else 1.0)])
    return gain_curve.astype(np.float32)

# ---------------------------------------------------------------------------------------------
# gain staging
# ---------------------------------------------------------------------------------------------

def active_lufs(x, sr=SR, block=0.4, active_db=None):
    """Loudness over only the windows where the stem is actually sounding, so a sparse or delicate part is
    not boosted to fill its silences. A dynamic part keeps its own level."""
    x = to_stereo(x)
    active_db = _active_db() if active_db is None else float(active_db)
    n = int(block * sr)
    win = max(n, int(0.5 * sr))        # a loudness window is 400 ms with a 75 ms overlap; never pad it with silence
    if len(x) < win or n < 1:
        return lufs(x, sr)
    # Non-overlapping windows the length of a loudness measurement, so no window straddles the start of a rest and
    # no measured segment is padded with silence (that padding biased every block down by 1 dB).
    starts = list(range(0, len(x) - win + 1, win))
    blocks = np.stack([x[s:s + win] for s in starts])
    rms = np.sqrt((blocks.astype(np.float64) ** 2).mean(axis=(1, 2)) + 1e-20)
    keep = np.where(20 * np.log10(rms) > active_db)[0]
    if not len(keep):
        # Nothing clears the activity floor: it is a very quietly played stem, not silence. Measure the window
        # where it plays, or gain staging leaves it at -70 dB and never brings it into the mix at all.
        keep = np.array([int(np.argmax(rms))])
    # One measurement per active window, averaged in the power domain. Concatenating them (the old way) put a hard
    # splice through the K-weighting filter at every 0.4 s and under-read every hit shorter than a block.
    vals = [lufs(x[starts[i]:starts[i] + win], sr) for i in keep]
    vals = np.asarray([v for v in vals if np.isfinite(v) and v > -70.0], dtype=float)
    if not len(vals):
        return -70.0
    return float(10.0 * np.log10(np.mean(10.0 ** (vals / 10.0)) + 1e-30))


def gain_stage(x, l, role, spec, gs=None, sr=SR):
    """The gain, in dB, that brings this stem to its level.

    'legacy' (the default): the playing part to ref_lufs, boost capped by max_boost_db — unchanged.
    'adaptive': a per-role reference, a cut cap, a peak-headroom cap and a crest guard, so a delicate
    layer, a percussion stem and a physical ambience recording keep their own dynamic behaviour instead of
    all being pushed to one number.
    """
    gs = gs or _gs()
    strategy = str(gs.get('strategy', 'legacy')).lower()
    ref = float(gs.get('ref_lufs', REF_LUFS))
    max_boost = float(gs.get('max_boost_db', _max_boost_db()))
    if role in ('melody', 'lead'):
        # A lead is the reference everything else is judged against, so it has to reach its level. The boost cap
        # exists to protect near-silent ambience; it is not a statement that a quietly played lead must stay buried
        # (a GM lead under a soft dynamics arc sat 15-25 dB under the beds and every bed then read "too loud").
        max_boost = max(max_boost, 24.0)
    if spec.get('target_lufs') is not None and l > -69:
        gain = float(spec['target_lufs']) - l
    elif l > -69:
        if strategy == 'adaptive':
            ref = float(spec.get('ref_lufs', (gs.get('ref_by_role') or {}).get(role, ref)))
        gain = min(ref - l, max_boost)
    elif role == 'environment':
        rms = float(np.sqrt(np.mean(np.asarray(x, np.float64) ** 2) + 1e-12))
        target = float(spec.get('target_lufs', _mix().get('env_target_lufs', -24.0)))
        scale = float(gs.get('env_fallback_rms_scale', 0.5))
        gain = 20 * np.log10((10 ** (target / 20.0) * scale) / rms) if rms > 1e-6 else 0.0
    else:
        return 0.0
    if strategy != 'adaptive':
        return float(gain)
    gain = max(gain, -abs(float(gs.get('max_cut_db', 24.0))))
    if gain > 0:
        headroom = float(gs.get('peak_headroom_db', -1.0)) - dsp.peak_db(x)
        gain = min(gain, max(0.0, headroom))
        crest_floor = float(gs.get('crest_preserve_db', 0.0))
        if crest_floor > 0:
            crest = dsp.crest_db(x)
            if crest < crest_floor:
                gain *= crest / crest_floor
        sparse = float(gs.get('sparse_active_frac', 0.0))
        if sparse > 0 and dsp.active_fraction(x, sr, float(gs.get('block_s', 0.4)),
                                              float(gs.get('active_db', _active_db()))) < sparse:
            gain *= 0.5
    return float(gain)


def reverb_send_level(spec, mx=None, space=None):
    """The reverb send for this stem: its `reverb` times the distance factor (DRR), never mutating `spec`."""
    mx = mx or _mix()
    base = float(spec.get('reverb', 0.0) or 0.0)
    sp = spec.get('spatial')
    if not sp:
        return base
    space = _space() if space is None else space
    dist = max(0.5, float(sp.get('distance', 1.5)))
    cfg = dict(mx.get('spatial') or {})
    dc = space.get('distance', {}) if _space_owned(space) else {}
    for k_sp, k_mix in (('ref_m', 'air_absorption_ref_distance'), ('falloff', 'direct_falloff_scale'),
                        ('air_damping', 'air_absorption_damping'), ('min_cutoff_hz', 'min_air_cutoff_hz'),
                        ('reverb_exponent', 'reverb_distance_scale')):
        if k_sp in dc:
            cfg[k_mix] = dc[k_sp]
    ref_d = float(sp.get('ref_distance', cfg.get('air_absorption_ref_distance', 1.5)))
    drr = (mx.get('space') or {}).get('drr') or {}
    if drr.get('enabled'):
        scale = 10 ** (float(drr.get('target_db', 0.0)) / 20.0)
        return base * scale * (dist / float(drr.get('ref_m', ref_d))) ** float(drr.get('exponent', 0.65))
    exp = float(sp.get('reverb_scale', cfg.get('reverb_distance_scale', 0.65)))
    return base * float(np.clip((dist / ref_d) ** exp, 0.7, 2.2))


def dynamics_cfg(spec, mx=None):
    """This stem's dynamics: the preset's track values over the mix preset's dynamics section.
    `comp` keeps its old meaning (a dict of thr/ratio/attack/release, or False to switch it off)."""
    mx = mx or _mix()
    d = dict(mx.get('dynamics') or {})
    for k, v in (spec.get('dynamics') or {}).items():
        d[k] = v
    if 'comp' in spec:
        d['comp'] = spec['comp']
    return d

# ---------------------------------------------------------------------------------------------
# main mix
# ---------------------------------------------------------------------------------------------

def process_stem(name, x, spec, sr=SR, ctx=None):
    """One stem through the chain. `spec` is never modified: the send is read by reverb_send_level()."""
    if ctx is not None and ctx is not mix_context.current():
        _install(ctx.mix, ctx.space)
    mx = _mix()
    spec = dict(spec or {})
    role = spec.get('role', 'chord')
    x = to_stereo(x)
    if len(x) == 0:
        return x.astype(np.float32)
    gs = mx.get('gain_staging') or {}
    # 1 gain staging
    l = active_lufs(x, sr, block=float(gs.get('block_s', 0.4)), active_db=float(gs.get('active_db', _active_db())))
    g = gain_stage(x, l, role, spec, gs, sr)
    x = x * 10 ** (g / 20.0)
    STATE.setdefault('gain', {})[name] = g
    STATE.setdefault('in_lufs', {})[name] = l

    # 2/3 EQ + dynamics
    dyn = dynamics_cfg(spec, mx)
    chain = []
    source = 'none'
    if spec.get('chain') != 'none':
        schain, source = spectral_chain(role, spec, mx)
        chain += _chain_objects(schain)
    for d in spec.get('eq', []) or []:
        if d.get('order') and d.get('type') in ('hp', 'highpass', 'lp', 'lowpass'):
            x = dsp.slope_filter(x, sr, d['f'], d['type'], d['order'])
        else:
            chain.append(eq_object(d))
    if 'hp' in spec:
        chain.insert(0, pb.HighpassFilter(spec['hp']))
    if 'lp' in spec:
        chain.append(pb.LowpassFilter(spec['lp']))
    comp = dyn.get('comp')
    if comp is False or comp == 0:
        comp = None
    if isinstance(comp, dict) and str(dyn.get('engine', 'pedalboard')) == 'pedalboard':
        chain.append(pb.Compressor(threshold_db=comp.get('thr', -22), ratio=comp.get('ratio', 2.5),
                                   attack_ms=comp.get('attack', 15), release_ms=comp.get('release', 150)))
    if spec.get('saturation', 0):
        chain.insert(0, pb.Distortion(drive_db=spec['saturation']))
    if chain:
        x = _run(pb.Pedalboard(chain), x, sr)
    STATE.setdefault('chain', {})[name] = source
    if spec.get('dynamics') or str(dyn.get('engine', 'pedalboard')) == 'dsp':
        x = _dsp_dynamics(x, dyn, sr)

    # 4 low-end hygiene
    if role == 'bass' or spec.get('mono_below'):
        x = mono_below(x, spec.get('mono_below', 120), sr)
    # level
    x = x * 10 ** (float(spec.get('gain_db', 0.0)) / 20.0)
    # macro automation for environment
    if role == 'environment':
        tot_s = len(x) / sr
        swell_db = float(spec.get('intro_outro_boost_db', 0.0))      # off unless the track asks
        t_in_start = float(spec.get('crossfade_start_s', 4.0))
        t_in_end = float(spec.get('crossfade_end_s', 12.0))
        t_out_start = max(t_in_end + 5.0, float(spec.get('outro_start_s', tot_s - 8.0)))
        t_out_end = min(tot_s, float(spec.get('outro_end_s', tot_s - 1.0)))
        if swell_db > 0.0 and tot_s > (t_in_end + 8.0):
            t_axis = np.arange(len(x)) / sr
            mult_curve = np.zeros(len(x), dtype=np.float32)
            mult_curve[t_axis <= t_in_start] = 1.0
            idx_in = (t_axis > t_in_start) & (t_axis < t_in_end)
            if np.any(idx_in):
                th_in = np.pi * (t_axis[idx_in] - t_in_start) / (t_in_end - t_in_start)
                mult_curve[idx_in] = 0.5 * (1.0 + np.cos(th_in))
            idx_out = (t_axis > t_out_start) & (t_axis < t_out_end)
            if np.any(idx_out):
                th_out = np.pi * (t_axis[idx_out] - t_out_start) / (t_out_end - t_out_start)
                mult_curve[idx_out] = 0.5 * (1.0 - np.cos(th_out))
            mult_curve[t_axis >= t_out_end] = 1.0
            x = x * (10.0 ** ((swell_db * mult_curve) / 20.0))[:, None]
    # opt-in per-track fades
    curve = str(((mx.get('automation') or {}).get('curve')) or 'linear')
    for key, rising in (('fade_in_s', True), ('fade_out_s', False)):
        fade_n = min(len(x), int(float(spec.get(key, 0.0)) * sr))
        if fade_n > 1:
            ramp = _curve(np.linspace(0.0, 1.0, fade_n), curve).astype(np.float32)
            if rising:
                x[:fade_n] = x[:fade_n] * ramp[:, None]
            else:
                x[-fade_n:] = x[-fade_n:] * ramp[::-1, None]
    # 5/6/7 width + pan + 3D spatial staging
    x = _place(name, x, spec, mx, sr)
    if not np.isfinite(x).all():
        raise ValueError(f'stem "{name}" produced non-finite samples (check its eq/comp/spatial values)')
    return x.astype(np.float32)


def _curve(v, kind):
    """An automation curve, 0..1 -> 0..1."""
    if kind == 'cosine':
        return 0.5 - 0.5 * np.cos(np.pi * v)
    if kind == 'exponential':
        return np.asarray(v, float) ** 2
    return np.asarray(v, dtype=np.float32)


def _dsp_dynamics(x, dyn, sr):
    """The part of the chain Pedalboard cannot do: knee/detector/sidechain-filter/parallel/multiband/
    dynamic EQ/transient shaping. Only reached when a preset asks for it."""
    comp = dyn.get('comp')
    if isinstance(comp, dict):
        x = dsp.compressor(x, sr, threshold_db=comp.get('thr', -22), ratio=comp.get('ratio', 2.5),
                           attack_ms=comp.get('attack', 15), release_ms=comp.get('release', 150),
                           knee_db=float(dyn.get('knee_db', 0.0)), detector=str(dyn.get('detector', 'peak')),
                           stereo_link=bool(dyn.get('stereo_link', True)),
                           lookahead_ms=float(dyn.get('lookahead_ms', 0.0)),
                           makeup_db=float(dyn.get('makeup_db', 0.0)),
                           sidechain_hp_hz=float(dyn.get('sidechain_hp_hz', 0.0)),
                           sidechain_lp_hz=float(dyn.get('sidechain_lp_hz', 0.0)),
                           mix=float(dyn.get('parallel', 1.0)))
    if dyn.get('multiband'):
        x = dsp.multiband_compressor(x, sr, dyn['multiband'])
    for b in (dyn.get('dynamic_eq') or []):
        x = dsp.dynamic_eq(x, sr, f=b.get('f', 1000.0), q=b.get('q', 1.0),
                           threshold_db=b.get('threshold_db', -24.0), ratio=b.get('ratio', 2.0),
                           attack_ms=b.get('attack_ms', 5.0), release_ms=b.get('release_ms', 80.0),
                           knee_db=b.get('knee_db', 3.0), gain_db=b.get('gain_db', 0.0))
    tr = dyn.get('transient')
    if isinstance(tr, dict):
        x = dsp.transient_shaper(x, sr, float(tr.get('attack_db', 0.0)), float(tr.get('sustain_db', 0.0)))
    return x


def _place(name, x, spec, mx, sr):
    """Width, widen, pan, distance laws, the binaural route and the DRR send decision."""
    sp = spec.get('spatial')
    if not sp:
        w = spec.get('width', 1.0)
        if w != 1.0:
            x = width_ms(x, w)
        if spec.get('widen', 0) > 0:
            x = widen(x, spec['widen'], seed=zlib.crc32(name.encode()) % 997, sr=sr)
        return pan_stereo(x, spec.get('pan', 0.0), spec.get('pan_law', 'legacy'))

    az = float(sp.get('azimuth', 0.0))
    el = float(sp.get('elevation', 0.0))
    dist = max(0.5, float(sp.get('distance', 1.5)))
    imm = _imm()
    if imm:
        if 'elevation' not in sp:
            el = float(imm.get('height_by_role', {}).get(spec.get('role', ''), 0.0))
        el = 0.0 if spec.get('role') in ('bass', 'drum') else float(np.clip(el, -90.0, float(imm.get('max_elevation', 60.0))))

    sp_cfg = dict(mx.get('spatial') or {})
    dc = _space().get('distance', {}) if _space_owned(_space()) else {}
    for k_sp, k_mix in (('ref_m', 'air_absorption_ref_distance'), ('falloff', 'direct_falloff_scale'),
                        ('air_damping', 'air_absorption_damping'), ('min_cutoff_hz', 'min_air_cutoff_hz'),
                        ('reverb_exponent', 'reverb_distance_scale')):
        if k_sp in dc:
            sp_cfg[k_mix] = dc[k_sp]
    ref_d = float(sp.get('ref_distance', sp_cfg.get('air_absorption_ref_distance', 1.5)))
    damp = float(sp.get('air_damping', sp_cfg.get('air_absorption_damping', 0.40)))
    min_cut = float(sp.get('min_cutoff_hz', sp_cfg.get('min_air_cutoff_hz', 3200.0)))
    falloff = float(sp.get('falloff_scale', sp_cfg.get('direct_falloff_scale', 0.18)))

    traj = sp.get('trajectory')
    binaural = bool(sp.get('binaural')) or bool(traj)
    route = sp.get('binaural')
    kind = sp.get('kind')
    if imm and sp.get('binaural') is not False:
        binaural, route = True, 'hrtf'
    elif kind == 'bed' and not traj:
        binaural = False
    elif kind == 'spot' and 'binaural' not in sp and _space().get('binaural', {}).get('spot'):
        binaural = True
    refl = resolve_space(sp['space']).get('reflections') if sp.get('space') else None
    space_arg = refl or sp.get('space') or (_space().get('reflections') if _space_owned(_space()) else None) or 'outdoor_open'
    hrtf_ok = False
    if binaural and route == 'hrtf':
        from spatial_hrtf import binaural as _hrtf
        hrtf_ok = _hrtf.available()
        if not hrtf_ok:
            print('  [spatial] "binaural": "hrtf" asked for but the head data is missing: run '
                  '`python -m spatial_hrtf.data` from scripts/. Using spatial.py.')
    if hrtf_ok:
        # the head set is a preset value: a listener's own set when the piece names one, the bundled book otherwise
        want_set = str(((imm or {}).get('hrtf') or {}).get('dataset') or '')
        try:
            _hrtf.set_dataset(_head_set(want_set))
        except Exception as e:
            print(f'  [spatial] head set "{want_set}" could not be used ({e}); using the bundled set')
            _hrtf.set_dataset(None)
        # the near field belongs to the space, not to the mix: below one metre the ears hear different distances
        track_space = resolve_space(sp['space']) if sp.get('space') else _space()
        near = (track_space.get('distance') or {}).get('near_field')
        kw = dict(sr=sr, trajectory=traj, temp_c=float(sp.get('temp_c', 20.0)), rh=float(sp.get('rh', 50.0)),
                  near_field=near)
        mono = x.mean(axis=1)
        c = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]) if x.shape[1] == 2 and x.std() > 0 else 1.0
        pair = dict(mix_schema.DEFAULTS['immersive'].get('pair') or {})
        pair.update((imm or {}).get('pair') or {})
        default_hw = float(pair['width_deg_bed'] if kind == 'bed'
                           else (pair['width_deg_stereo'] if np.isfinite(c) and c < 0.9 else 0.0))
        hw = float(sp.get('half_width_deg', default_hw)) if imm and not traj else 0.0
        direct = (_hrtf.spatialize_pair(x, az, el, dist, hw, **kw) if hw > 0
                  else _hrtf.spatialize(mono, az, el, dist, **kw))
        if imm and not traj:
            import spatial
            refl_cfg = space_arg if isinstance(space_arg, dict) else (resolve_space(space_arg).get('reflections')
                                                                      or spatial.ACOUSTIC_SPACES.get(space_arg))
            path_physics = bool((refl_cfg or {}).get('path_physics', True))
            x = direct + (_hrtf.reflections(mono, az, dist, refl_cfg, sr=sr, path_physics=path_physics,
                                            temp_c=float(sp.get('temp_c', 20.0)), rh=float(sp.get('rh', 50.0)),
                                            elevation_deg=el)
                          if refl_cfg else 0.0)
            # the late field: several decorrelated tails from spread directions, or none when the preset says so
            tail = _hrtf.late(mono, az, dist, refl_cfg, sr=sr) if refl_cfg else None
            if tail is not None:
                x = x + tail
        else:
            x = direct
    elif binaural:
        import spatial
        if traj:
            x = spatial.render_trajectory(x.mean(axis=1), traj, acoustic_space=space_arg)
        else:
            x = spatial.spatialize_stem(x.mean(axis=1), azimuth_deg=az, elevation_deg=el, distance_m=dist,
                                        acoustic_space=space_arg, externalize=True, sr=sr)
    # A. distance air absorption
    own_distance = spec.get('scene_distance_m') is not None
    if not binaural and not own_distance and dist > ref_d and sp.get('air_absorption', True) and ('temp_c' in sp or 'rh' in sp):
        import airabs
        x = airabs.apply(x, dist - 1.0, temp_c=float(sp.get('temp_c', 20.0)), rh=float(sp.get('rh', 50.0)), sr=sr)
    elif not binaural and not own_distance and dist > ref_d and sp.get('air_absorption', True):
        cutoff = max(min_cut, min(sr * 0.45, 22000.0 / (1.0 + damp * (dist - ref_d))))
        sos_air = signal.butter(1, cutoff, btype='lowpass', fs=sr, output='sos')
        x = signal.sosfilt(sos_air, x, axis=0).astype(np.float32)
    # B. 1/r direct level
    if not binaural and not own_distance and dist > 1.0:
        x = x * (1.0 / (1.0 + falloff * (dist - 1.0)))
    # C. apparent source width
    spread = float(np.clip(float(sp.get('spread', 0.0)), 0.0, 1.0))
    w = float(sp.get('width', spec.get('width', 1.0))) * (1.0 + spread)
    if w != 1.0:
        x = width_ms(x, w)
    widen_amt = float(sp.get('widen', spec.get('widen', 0.0)))
    if widen_amt > 0:
        x = widen(x, widen_amt, seed=zlib.crc32(name.encode()) % 997, sr=sr)
    # D. pan (no comb delays)
    pan_val = float(sp.get('pan', np.clip(np.sin(np.radians(az)), -1.0, 1.0))) * (1.0 - spread)
    if not binaural:
        x = pan_stereo(x, pan_val, sp.get('pan_law', spec.get('pan_law', 'legacy')))
    return x


# orchestral-style seating so layers do not stack in the middle (-1 left .. +1 right)
def default_spec(tr):
    role = tr.get('role', 'chord')
    inst = str(tr.get('instrument', '')).lower().replace(' ', '_')
    d = dict(role=role, gain_db=_level_by_role().get(role, -8),
             pan=from_table(_seating(), inst, 0.0) if role not in ('bass', 'drum') else 0.0,
             reverb=0.18, widen=_widen_by_role().get(role, 0.0))
    d['inst'] = inst

    passthrough = ('gain_db', 'pan', 'spatial', 'reverb', 'width', 'eq', 'comp', 'hp', 'lp', 'chain',
                   'saturation', 'mono_below', 'duck_by', 'duck_db', 'widen', 'fade_in_s', 'fade_out_s',
                   'intro_outro_boost_db', 'target_lufs', 'crossfade_start_s', 'crossfade_end_s',
                   'outro_start_s', 'outro_end_s', 'spectral_profile', 'preserve_spectrum', 'ref_lufs',
                   'dynamics', 'sidechain', 'pan_law', 'release_ms', 'attack_ms', 'smooth_s',
                   'duck_full_band', 'duck_band_hz')
    try:
        if inst.startswith('sfx:'):
            inst_cfg = presets.find_sfx(inst[4:])
        elif inst.startswith('env:'):
            inst_cfg = presets.find_environment(inst[4:])
        else:
            inst_cfg = presets.find_instrument(inst) or presets.find_vocal(inst)
        if inst_cfg and isinstance(inst_cfg, dict):
            # A physical scene already propagated its sound to the listener; applying this stage's
            # distance law again would attenuate it twice.
            prop = (inst_cfg.get('scene') or {}).get('propagation') or {}
            if prop.get('distance_m') is not None:
                d['scene_distance_m'] = float(prop['distance_m'])

            def _layer_d(l):
                for blk in (l.get('propagation'), (l.get('scene') or {}).get('propagation')):
                    if isinstance(blk, dict) and blk.get('distance_m') is not None:
                        return True
                return False
            n_scene = sum(1 for l in inst_cfg.get('scene_layers', []) or [] if _layer_d(l))
            if n_scene or (inst_cfg.get('propagation') or {}).get('distance_m') is not None:
                d['scene_distance_m'] = True
            for k in passthrough:
                if k in inst_cfg and inst_cfg[k] is not None:
                    d[k] = inst_cfg[k]
    except Exception as e:
        print(f'  [WARN] preset lookup for {inst!r} failed, using role defaults: {e}')

    sat = from_table(_mix().get('saturation') or {}, inst)
    if sat is not None:
        d['saturation'] = sat
    if role in ('bass',):
        d['reverb'] = d.get('reverb', 0.0)
    if role == 'drum':
        d['reverb'] = d.get('reverb', 0.08)
    if role == 'pad':
        d['reverb'] = d.get('reverb', 0.30)
    if role == 'melody':
        d['reverb'] = d.get('reverb', 0.22)
    if role == 'environment':
        d['reverb'] = d.get('reverb', 0.20)
    d.update({k: tr[k] for k in ('role',) + passthrough if k in tr and tr[k] is not None})
    return d

# ---------------------------------------------------------------------------------------------
# mastering
# ---------------------------------------------------------------------------------------------

def _master_cfg(m, mx):
    """The master block: the chosen profile, the shipped defaults, then the score's own values."""
    mm = mx.get('mastering') or {}
    profiles = mm.get('profiles') or {}
    name = m.get('profile') or mm.get('profile') or 'default'
    base = dict(profiles.get(name) or profiles.get('default') or {})
    out = dict(base)
    out.update({k: v for k, v in (m or {}).items() if k in ('lufs', 'true_peak', 'tone', 'glue', 'width',
                                                            'mono_below', 'fade_out', 'loop')})
    out['_profile'] = name
    out['_profiles'] = profiles
    out['_cfg'] = mm
    return out


def _short_term(x, sr, win_s=3.0, hop_s=0.5):
    n, hop = int(win_s * sr), max(1, int(hop_s * sr))
    if len(x) < n:
        return [lufs(x, sr)]
    return [lufs(x[i:i + n], sr) for i in range(0, len(x) - n + 1, hop)]


def master_measures(x, sr=SR):
    """What the delivery report needs: integrated/short-term loudness, LRA, crest, true peak, mono fold."""
    st = np.array(_short_term(x, sr), dtype=float)
    st = st[np.isfinite(st)]
    if len(st):
        st = st[st > -70.0]                        # EBU R128 absolute gate
        if len(st):
            st = st[st > float(np.mean(st)) - 20.0]   # ... and the relative gate, or a silent intro inflates LRA
    return {
        'lufs': lufs(x, sr),
        'short_term_max': float(st.max()) if len(st) else float('nan'),
        'short_term_min': float(st.min()) if len(st) else float('nan'),
        'lra': float(np.percentile(st, 95) - np.percentile(st, 10)) if len(st) > 4 else 0.0,
        'true_peak': true_peak_db(x, sr),
        'sample_peak': float(20 * np.log10(np.abs(x).max() + 1e-12)),
        'crest': dsp.crest_db(x),
        'mono_fold': dsp.mono_fold_db(x),
        'correlation': dsp.correlation(x),
    }


def master_chain(x, m, sr=SR, ctx=None):
    """Glue + tone + limiter + loudness. m: {"lufs":-14,"true_peak":-1.5,"tone":"neutral","glue":true}."""
    if ctx is not None and ctx is not mix_context.current():
        _install(ctx.mix, ctx.space)
    cfg = _master_cfg(m, _mix())
    target = float(cfg.get('lufs', -14.0))
    ceiling = float(cfg.get('true_peak', -1.5))
    tone = cfg.get('tone', 'neutral')
    chain = [pb.HighpassFilter(24)]
    if tone == 'warm':
        chain += [pb.LowShelfFilter(120, 1.0, 0.7), pb.HighShelfFilter(8000, -1.5, 0.7)]
    elif tone in ('earthy', 'forest'):
        chain += [pb.LowShelfFilter(110, 1.4, 0.7), _peak(320, 1.2, 0.9), pb.HighShelfFilter(8200, -1.8, 0.7)]
    elif tone == 'bright':
        chain += [pb.HighShelfFilter(7000, 1.8, 0.7)]
    if cfg.get('glue', True):
        chain.append(pb.Compressor(threshold_db=-18, ratio=1.6, attack_ms=40, release_ms=250))
    if cfg.get('width'):
        x = width_ms(x, cfg['width'])
    x = _run(pb.Pedalboard(chain), x, sr)
    if cfg.get('mono_below'):
        x = mono_below(x, cfg['mono_below'], sr)
    try:
        lim = pb.Pedalboard([pb.BrickwallLimiter(ceiling_db=ceiling, true_peak=True)])
    except Exception:
        lim = pb.Pedalboard([pb.Limiter(threshold_db=ceiling - 0.6, release_ms=120)])
    crest_floor = float((_mix().get('mastering') or {}).get('crest_floor_db', 0.0))
    gain_db = target - lufs(x, sr)
    y = x
    for _ in range(6):                                               # converge on loudness with the limiter in the loop
        y = _run(lim, x * 10 ** (gain_db / 20.0), sr)
        err = target - lufs(y, sr)
        if abs(err) < 0.3:
            break
        if crest_floor > 0 and dsp.crest_db(y) < crest_floor:
            sys.stderr.write(f'[master] a {target} LUFS target would take the crest under {crest_floor} dB '
                             f'(at {dsp.crest_db(y):.1f} dB); stopping. Raise the headroom or lower the target.\n')
            break
        gain_db += err * 0.75          # damped step: >1.0 on a saturating limiter is an over-relaxed fixed point
    reached = lufs(y, sr)
    if abs(target - reached) > 1.0:
        sys.stderr.write(f'[master] reached {reached:.1f} LUFS, not {target}: the music is too dynamic for that target under a '
                         f'{ceiling} dBTP ceiling without squashing it. Kept natural dynamics; lower the target or accept it.\n')
    tp = true_peak_db(y, sr)
    if tp > ceiling:                       # last safety: oversampled true peak
        y = y * 10 ** ((ceiling - tp) / 20.0)
        reached = lufs(y, sr)              # the trim moves the whole track: report what was actually delivered
    y = y.astype(np.float32)
    STATE['master'] = dict(master_measures(y, sr), target=target, ceiling=ceiling, profile=cfg.get('_profile'),
                           reached=reached,
                           limited_by_ceiling=bool(tp > ceiling))
    return y


def suggest_master_target(x, sr=SR, lufs_target=-14.0, ceiling=-1.5):
    """Can this material reach the target without destroying it? Returns (feasible, why)."""
    m = master_measures(x, sr)
    crest = m['crest']
    needed = lufs_target - m['lufs']
    ceiling_room = ceiling - m['true_peak']
    if needed <= 0:
        return True, f'already at {m["lufs"]:.1f} LUFS; the target needs no gain'
    if crest - needed < 8.0:
        return False, (f'crest factor is {crest:.1f} dB; reaching {lufs_target} LUFS needs {needed:+.1f} dB, '
                       f'which would leave {crest - needed:.1f} dB of crest, below the 8 dB this engine treats as music')
    if ceiling_room < needed - 0.5:
        return False, (f'{needed:+.1f} dB of gain against {ceiling_room:.1f} dB to the {ceiling} dBTP ceiling: '
                       f'the limiter would have to hold transients down for the whole piece')
    return True, f'{needed:+.1f} dB of gain, {crest:.1f} dB crest, {ceiling_room:.1f} dB to the ceiling'


def guess_role(name):
    n = name.lower()
    for words, role in ((('drum', 'kick', 'snare', 'perc', 'hat', 'kit'), 'drum'), (('bass', 'sub', '808'), 'bass'),
                        (('pad', 'string', 'choir', 'organ', 'atmos', 'drone'), 'pad'),
                        (('lead', 'vocal', 'vox', 'melody', 'solo', 'flute', 'violin', 'sax'), 'melody'),
                        (('fx', 'sfx', 'riser', 'impact', 'noise'), 'fx'), (('arp', 'pluck', 'bell', 'spark'), 'arp')):
        if any(w in n for w in words):
            return role
    return 'chord'


def carve_for_lead(specs, mx=None):
    """Mix rule: when a melody leads, every bed that shares its band (pads, chords, arps, counter lines,
    chorus, environment) gets a small dip at the lead band, so the lead cuts through. A dip the user set is
    kept. The dip never exceeds spectral.max_auto_cut_db."""
    mx = mx or _mix()
    band = float(mx.get('lead_band_hz', DEFAULT_LEAD_BAND_HZ))
    carve = float(mx.get('carve_db', DEFAULT_CARVE_DB))
    limit = float((mx.get('spectral') or {}).get('max_auto_cut_db', 3.0))
    if not any(s.get('role') == 'melody' for s in specs.values()):
        return specs
    for name, sp in specs.items():
        if sp.get('role') in ('pad', 'chord', 'arp', 'counter', 'environment') or name in ('chorus',):
            eq = sp.setdefault('eq', [])
            if not any(d.get('type') == 'peak' and abs(d.get('f', 0) - band) < 1 for d in eq):
                depth = carve - 1.5 if sp.get('role') == 'environment' else carve
                depth = max(depth, -abs(limit)) if limit > 0 else depth
                eq.append(dict(type='peak', f=band, gain=depth, q=1.0))
    return specs


def use_mix(name=None, space=None):
    """Make `name` the active mix preset: the default with that preset laid over it, so a preset only lists
    what differs. name=None or 'default' restores the default. Returns the resolved mix dict."""
    mix = mix_context.mix_for(name or 'default')
    cur = mix_context.current()
    sp = (cur.space if space is None and cur is not None else space) or {}
    ctx = mix_context.MixContext(mix, sp, name=name or 'default', space_owned=_space_owned(sp))
    _install(mix, sp, ctx)
    return mix


def _head_set(name):
    """Resolve a mix preset's `immersive.hrtf.dataset` to a file path (None = the bundled set). A bare name looks in
    every project's presets/hrtf/ for <name>.sofa or <name>.mat; a path is used as given."""
    if not name or name.lower() in ('fabian', 'default', 'bundled'):
        return None
    if os.path.exists(name):
        return name
    for root in presets.PROJECT_ROOTS:
        for ext in ('.sofa', '.mat'):
            p = os.path.join(os.path.dirname(root), 'presets', 'hrtf', name + ext)
            if os.path.exists(p):
                return p
    raise FileNotFoundError(f'no presets/hrtf/{name}.sofa or .mat in any project; '
                            f'put the listener\'s set there or give a path')


def _imm():
    """The active mix preset's immersive block when it is switched on, else None."""
    c = _mix().get('immersive') or {}
    return c if c.get('enabled') else None


def immersive_cfg(score):
    """The immersive block that mixing this score would use (None when off). The gates call this."""
    use_mix(score.get('mix_preset'))
    return _imm()


def _context_for(score, ctx=None):
    """Resolve (or accept) this piece's context and make it the active one."""
    if ctx is None or ctx is not mix_context.current():
        ctx = ctx or mix_context.resolve(score, space_resolver=resolve_space)
    _install(ctx.mix, ctx.space, ctx)      # idempotent: the same context, this thread's copy
    return ctx


def mix_stems(score, stems, sr=SR, ctx=None):
    """Return the pre-master stereo mix (float32)."""
    if not stems:
        raise ValueError('mix_stems needs at least one stem')
    ctx = _context_for(score, ctx)
    mx = _mix()
    space_name = ctx.space_name or score.get('space') or score.get('room', 'hall')
    n = max(len(v) for v in stems.values())
    specs = {}
    for i, tr in enumerate(score.get('tracks', [])):
        specs[tr.get('name', f'track{i}')] = default_spec(tr)
    for name in stems:                                  # stems with no spec: guess the role
        if name not in specs:
            specs[name] = default_spec(dict(role=guess_role(name)))
    for k, v in (score.get('mix', {}).get('tracks', {}) or {}).items():
        if k in specs:
            specs[k].update(v)

    # Shared acoustic space: when environmental layers are present, acoustic instruments send a little
    # more into the shared room so music and nature are not two unrelated recordings. Preset-gated.
    blend = (mx.get('space') or {}).get('auto_env_blend') or {}
    has_env = any(specs[name].get('role') == 'environment' for name in stems)
    if has_env and blend.get('enabled', True):
        floors = {'chord': (0.20, 'chord'), 'arp': (0.20, 'chord'), 'melody': (0.22, 'melody'),
                  'drum': (0.12, 'drum'), 'environment': (0.15, 'environment')}
        for name, sp in specs.items():
            rule = floors.get(sp.get('role'))
            if not rule:
                continue
            floor, key = rule
            if float(sp.get('reverb', 0.0)) < floor:
                sp['reverb'] = float(blend.get(key, floor))

    # Sidechain routing. "legacy" auto-ducks a bed under the first drum track (the behaviour this engine
    # shipped with); "explicit" only ducks what a track asks for; "off" ducks nothing.
    sc_mode = str(((mx.get('sidechain') or {}).get('mode')) or 'legacy').lower()
    drum_track = next((name for name, sp in specs.items() if sp.get('role') == 'drum'), None)
    if sc_mode == 'legacy' and drum_track:
        for name, sp in specs.items():
            if sp.get('role') == 'environment' and not sp.get('duck_by'):
                sp['duck_by'] = drum_track
                sp['duck_db'] = float(sp.get('duck_db', -3.0))
    if sc_mode == 'off':
        for sp in specs.values():
            sp.pop('duck_by', None)

    carve_for_lead(specs, mx)                           # the mix rule: beds make room for the lead
    dry = np.zeros((n, 2), np.float32)
    send = np.zeros((n, 2), np.float32)
    processed = {}
    for name, x in stems.items():
        processed[name] = fit(process_stem(name, x, specs[name], sr, ctx), n)
    STATE['processed'] = processed              # what the mix actually plays: the gate measures this
    STATE['specs'] = specs

    # the musical body (first to last note that is not an environment layer)
    bpm = float(score.get('bpm', 90.0))
    beat_dur = 60.0 / bpm
    first_note_s, last_note_s = None, None
    for tr in score.get('tracks', []):
        if tr.get('role') == 'environment' or str(tr.get('instrument', '')).startswith('env:'):
            continue
        for note in tr.get('notes', []):
            t0 = float(note['t']) * beat_dur
            t1 = (float(note['t']) + float(note.get('d', 0.0))) * beat_dur
            if first_note_s is None or t0 < first_note_s:
                first_note_s = t0
            if last_note_s is None or t1 > last_note_s:
                last_note_s = t1

    sc = mx.get('sidechain') or {}
    band = tuple(float(v) for v in (sc.get('band_hz') or DUCK_BAND_HZ))
    residual = float(sc.get('residual', DUCK_RESIDUAL))
    for name, sp in specs.items():
        src = sp.get('duck_by')
        if not src or src not in processed:
            continue
        is_env = (sp.get('role') == 'environment')
        rel_ms = float(sp.get('release_ms', (sc.get('release_ms') or {}).get(sp.get('role'),
                                            1600.0 if is_env else 180.0)))
        att_ms = float(sp.get('attack_ms', (sc.get('attack_ms') or {}).get(sp.get('role'),
                                           25.0 if is_env else 8.0)))
        smooth_s = float(sp.get('smooth_s', 0.35 if is_env else 0.0))
        d_gain = duck_gain(processed[src], n, sp.get('duck_db', -4), float(sc.get('threshold', 0.05)),
                           attack_ms=att_ms, release_ms=rel_ms,
                           lookahead_ms=10, smooth_s=smooth_s, sr=sr)
        if is_env and sc.get('env_plateau', True) and first_note_s is not None and last_note_s is not None \
                and last_note_s > first_note_s:
            # Lock a bed to a steady plateau across the musical body: it should not swell during a
            # two-second instrumental pause mid-piece.
            i_body_start = int(first_note_s * sr)
            i_body_end = min(n, int(last_note_s * sr))
            if i_body_end > i_body_start:
                min_floor = 10.0 ** (float(sp.get('duck_db', -4.0)) / 20.0)
                plateau_gain = float(np.percentile(d_gain[i_body_start:i_body_end], 25))
                plateau_gain = max(min_floor, min(plateau_gain, 1.0))
                fade_s = min(2.0, (last_note_s - first_note_s) * 0.25)
                n_fade = int(fade_s * sr)
                if n_fade > 0 and 2 * n_fade < (i_body_end - i_body_start):
                    t = np.linspace(0.0, np.pi, n_fade, dtype=np.float32)
                    cf_in = 0.5 * (1.0 + np.cos(t))
                    cf_out = 0.5 * (1.0 - np.cos(t))
                    d_gain[i_body_start:i_body_start + n_fade] = (
                        d_gain[i_body_start:i_body_start + n_fade] * cf_in + plateau_gain * cf_out)
                    d_gain[i_body_start + n_fade:i_body_end - n_fade] = plateau_gain
                    d_gain[i_body_end - n_fade:i_body_end] = (
                        plateau_gain * cf_in + d_gain[i_body_end - n_fade:i_body_end] * cf_out)
                elif n_fade > 0 and (i_body_start + n_fade) < i_body_end:
                    t = np.linspace(0.0, np.pi, n_fade, dtype=np.float32)
                    cf_in = 0.5 * (1.0 + np.cos(t))
                    cf_out = 0.5 * (1.0 - np.cos(t))
                    d_gain[i_body_start:i_body_start + n_fade] = (
                        d_gain[i_body_start:i_body_start + n_fade] * cf_in + plateau_gain * cf_out)
                    d_gain[i_body_start + n_fade:i_body_end] = plateau_gain
        if sp.get('role') in DUCK_BAND_ROLES and not sp.get('duck_full_band'):
            # only the band the lead lives in takes the whole duck; the rest follows at DUCK_RESIDUAL of it
            x_ = processed[name]
            sos_b = signal.butter(2, [band[0], band[1]], btype='band', fs=sr, output='sos')
            mid = signal.sosfiltfilt(sos_b, x_, axis=0).astype(np.float32)
            processed[name] = mid * d_gain[:, None] + (x_ - mid) * (d_gain ** residual)[:, None]
        else:
            processed[name] = processed[name] * d_gain[:, None]

    law = _space().get('distance', {}).get('pre_delay_law') if _space_owned(_space()) else None
    STATE['sends'] = {}
    for name, y in processed.items():
        dry += y
        send_level = reverb_send_level(specs[name], mx, _space())
        STATE['sends'][name] = send_level
        ys = y * send_level
        sp_ = specs[name].get('spatial')
        if law and sp_:
            k = int(float(np.clip(law['base_ms'] - law['per_m'] * float(sp_.get('distance', 1.5)), 0.0,
                                  law['max_ms'])) * sr / 1000.0)
            if k > 0:
                ys = np.pad(ys, ((k, 0), (0, 0)))[:len(ys)]
        send += ys
    room = _space() if _space().get('room') else score.get('room', 'hall')
    if space_name != 'none' and send.any():
        ret = reverb_bus(send, room, sr)
        total = len(ret)
        mix = np.zeros((max(n, total), 2), np.float32)
        mix[:n] += dry
        mix[:total] += ret * float(score.get('mix', {}).get('reverb_return', 1.0))
    else:
        mix = dry
    return mix


def trim_tail(x, sr=SR, floor_db=None):
    floor_db = float((_mix().get('space') or {}).get('tail_guard_db', -62.0)) if floor_db is None else floor_db
    env = np.abs(x).max(1)
    idx = np.where(env > 10 ** (floor_db / 20))[0]
    end = (idx[-1] + int(0.15 * sr)) if len(idx) else len(x)
    return x[:min(len(x), end)]


def fades(x, sr=SR, fin=0.02, fout=0.6):
    n_in, n_out = int(fin * sr), int(fout * sr)
    x = x.copy()
    if n_in > 0:
        x[:n_in] *= np.linspace(0, 1, n_in)[:, None]
    if n_out > 0:
        x[-n_out:] *= np.linspace(1, 0, n_out)[:, None] ** 2
    return x


def wrap_loop(x, loop_seconds, sr=SR):
    """Seamless loop: the reverb/release tail that runs past the loop point is folded back onto the start."""
    n = int(round(loop_seconds * sr))
    body = x[:n].copy()
    tail = x[n:]
    k = min(len(tail), n)
    if k <= 0:
        return body
    # equal-power crossfade at the seam: adding the folded tail straight in stepped the level and clicked
    xf = min(k, max(1, int(0.035 * sr)))
    if k > xf:
        body[:k - xf] += tail[:k - xf]
    w = np.linspace(0.0, np.pi / 2.0, xf)[:, None]
    body[k - xf:k] = body[k - xf:k] * np.cos(w) + tail[k - xf:k] * np.sin(w)
    return body


def _validate_export(path, sr, expected_seconds=None, ceiling=0.0, true_peak=None):
    """Check the file that was actually written: format, channels, length, peak and true peak.

    true_peak  a measurement already taken on the same audio, reused instead of a second 4x oversampled pass.
    """
    info = sf.info(path)
    data, _ = sf.read(path, always_2d=True)
    peak = float(np.abs(data).max()) if data.size else 0.0
    peak_db = 20 * np.log10(peak + 1e-12)
    full = 1.0 - 1.0 / (1 << 23)                       # 0.999 counts a valid -0.01 dBFS PCM_24 peak as clipping
    rep = {'path': path, 'sr': info.samplerate, 'channels': info.channels, 'frames': info.frames,
           'subtype': info.subtype, 'peak_db': peak_db,
           'true_peak_db': float(true_peak) if true_peak is not None else true_peak_db(data.astype(np.float32), info.samplerate),
           'clipped_samples': int(np.sum(np.abs(data) >= full)),
           'seconds': info.frames / info.samplerate}
    problems = []
    if info.samplerate != sr:
        problems.append(f'sample rate {info.samplerate} != {sr}')
    if info.channels != 2:
        problems.append(f'{info.channels} channels, expected 2')
    if expected_seconds is not None and abs(rep['seconds'] - expected_seconds) > 0.05:
        problems.append(f'{rep["seconds"]:.2f}s written, {expected_seconds:.2f}s expected')
    if rep['clipped_samples']:
        problems.append(f'{rep["clipped_samples"]} samples at full scale')
    if rep['true_peak_db'] > ceiling + 0.1:
        problems.append(f'true peak {rep["true_peak_db"]:.2f} dBTP over the {ceiling} ceiling')
    rep['problems'] = problems
    return rep


def mix_and_master(score, stems, out_path, master=True, sr=SR, report=True, ctx=None, diagnose=False):
    if not stems:
        raise ValueError('mix_and_master needs at least one stem')
    ctx = _context_for(score, ctx)
    release_stems()                 # a previous piece's stems must not accumulate in one process
    mix = mix_stems(score, stems, sr, ctx)
    loop = score.get('loop_seconds')
    if loop:
        mix = wrap_loop(mix, loop, sr)
    else:
        mix = trim_tail(mix, sr)
    m = dict(score.get('master', {}))
    out = master_chain(mix, m, sr, ctx) if master else mix
    if not loop:
        out = fades(out, sr, fout=float(_master_cfg(m, _mix()).get('fade_out', 0.6)))
    if not np.isfinite(out).all():
        raise ValueError('the master produced non-finite samples')
    # Optional mid/side processing
    mm_cfg = _mix().get('mastering') or {}
    mid_gain = float(mm_cfg.get('mid_gain', 1.0))
    side_gain = float(mm_cfg.get('side_gain', 1.0))
    if mid_gain != 1.0 or side_gain != 1.0:
        out = apply_mid_side(out, mid_gain=mid_gain, side_gain=side_gain)
    full = 1.0 - 1.0 / (1 << 23)
    over = int(np.sum(np.abs(out) >= 1.0))         # the no-master path clipped without ever saying so
    if over:
        sys.stderr.write(f'[export] {over} samples above full scale before the write (master skipped); '
                         f'the file is hard-clipped there\n')
    # Optional dithering
    dtype_subtype = 'PCM_24'
    dither_cfg = mm_cfg.get('dither')
    if dither_cfg:
        if isinstance(dither_cfg, dict):
            dither_bits = int(dither_cfg.get('bits', 16))
            dither_shape = str(dither_cfg.get('shape', 'tpdf'))
            if dither_bits == 16:
                dtype_subtype = 'PCM_16'
            elif dither_bits == 24:
                dtype_subtype = 'PCM_24'
            elif dither_bits == 32:
                dtype_subtype = 'PCM_32'
            out = apply_dither(out, bits=dither_bits, shape=dither_shape)
        elif dither_cfg is True:
            out = apply_dither(out, bits=16, shape='tpdf')
            dtype_subtype = 'PCM_16'
    sf.write(out_path, np.clip(out, -1.0, 1.0), sr, subtype=dtype_subtype)
    mm = _mix().get('mastering') or {}
    if master and mm.get('validate_export', True):
        master_tp = (STATE.get('master') or {}).get('true_peak')
        rep = _validate_export(out_path, sr, len(out) / sr,
                               ceiling=float(_master_cfg(m, _mix()).get('true_peak', -1.5)),
                               true_peak=master_tp)
        STATE['export'] = rep
        if rep['problems']:
            for p in rep['problems']:
                sys.stderr.write(f'[export] {p}\n')
    elif not master:
        STATE['export'] = {'path': out_path, 'clipped_samples': over,
                           'peak_db': float(20 * np.log10(np.abs(out).max() + 1e-12)),
                           'problems': [f'{over} samples above full scale'] if over else []}
    if diagnose:
        import mix_diagnostics
        STATE['diagnostics'] = mix_diagnostics.analyse(score, STATE.get('processed') or stems,
                                                      mix=_mix(), master=STATE.get('master'), sr=sr)
    if report:
        meas = STATE.get('master') if out is not None else None
        tp_txt = (f'{float(meas["true_peak"]):.2f}' if meas and meas.get('true_peak') is not None
                  else f'{true_peak_db(out, sr):.2f}')
        line = f'wrote {out_path}  {len(out)/sr:.1f}s  LUFS {lufs(out, sr):.1f}  true-peak {tp_txt} dBTP'
        if meas:
            line += (f'  crest {meas["crest"]:.1f} dB  LRA {meas["lra"]:.1f} LU  '
                     f'mono {meas["mono_fold"]:+.1f} dB')
        print(line)
    return out


def main():
    ap = argparse.ArgumentParser(description='Mix a folder of stem WAVs (any source) and master it.')
    ap.add_argument('stems_dir')
    ap.add_argument('--mix', default=None, help='JSON: {"tracks":[{"name","role","gain_db","pan","reverb",...}],'
                                                '"room":"hall","master":{...}}')
    ap.add_argument('--out', default='mixed.wav')
    ap.add_argument('--diagnose', action='store_true', help='print the mixing diagnostics table')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    import cli_util
    cli_util.require_dir(a.stems_dir, 'stems folder')
    cli_util.require_file(a.mix, 'mix spec')
    files = sorted(f for f in os.listdir(a.stems_dir) if f.lower().endswith('.wav'))
    stems = {os.path.splitext(f)[0]: sf.read(os.path.join(a.stems_dir, f), always_2d=True)[0].astype(np.float32)
             for f in files}
    cfg = json.load(open(a.mix, encoding='utf-8')) if a.mix else {}
    tracks = cfg.get('tracks') or [{'name': k, 'role': 'chord'} for k in stems]
    cfg['tracks'] = tracks
    mix_and_master(cfg, stems, a.out, report=not a.quiet, diagnose=a.diagnose)
    if a.diagnose:
        import mix_diagnostics
        for lvl, name, detail in STATE.get('diagnostics') or []:
            print(f'{lvl:6s} {name:22s} {detail}')


if __name__ == '__main__':
    main()
