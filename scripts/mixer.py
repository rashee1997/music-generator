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

Configuration: every number comes from a mix preset (references/data/presets/mix/default.json, plus the
project's own) with the schema defaults in mix_schema.py underneath. `mix_context.resolve()` resolves a
piece's configuration once; the module-level names below are views of it, kept because the rest of the
skill and the tests read them. See references/mixing/mixing-and-mastering.md.
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
import roles as rolelib

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
    for key, val in mix_schema.inert_dynamics(mix):
        print(f'  [WARN] mix.dynamics.{key} = {val!r} has no effect with engine "pedalboard" (a four-knob compressor): set '
              f'mix.dynamics.engine to "dsp" to use it, or remove the key', flush=True)
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
    # Quantization step: a signed `bits`-bit word has 2**(bits-1) steps per unit of full scale (16-bit: 1/32768)
    scale = 2.0 ** (bits - 1)
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


def finalize_pcm(out, sr, mm_cfg, ceiling_db=None):
    """The last two steps before the write: the DC servo, then the dither. (out float32, PCM subtype).

    The servo comes FIRST. Dither puts every sample on the target word's grid; any filter after it moves the samples
    off that grid, and the write then re-rounds them with no dither at all, which undoes the point of dithering."""
    # a DC servo: a 4 Hz second-order high-pass, inaudible, removes any slow offset the chain collected
    sos_dc = signal.butter(2, 4.0, btype='high', fs=sr, output='sos')   # kills block-level offsets from the limiter
    out = signal.sosfilt(sos_dc, out, axis=0)
    if ceiling_db is not None:
        # the master chain trimmed the true peak to the ceiling BEFORE this filter, and a high-pass moves the edges of
        # low-frequency content (measured: +0.033 dB on a flute, piano and bass cue, enough to fail delivery.true_peak).
        # The same last-safety trim, applied to what is actually written.
        tp = true_peak_db(out, sr)
        if tp > ceiling_db:
            out = out * 10 ** ((ceiling_db - tp) / 20.0)
    subtype = 'PCM_24'
    dither_cfg = (mm_cfg or {}).get('dither')
    bits = None
    shape = 'tpdf'
    if isinstance(dither_cfg, dict):
        bits = int(dither_cfg.get('bits', 16))
        shape = str(dither_cfg.get('shape', 'tpdf'))
        subtype = {16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}.get(bits, subtype)
    elif dither_cfg is True:
        bits, subtype = 16, 'PCM_16'
    if bits is not None and bits < 32:
        out = apply_dither(out, bits=bits, shape=shape)
        out = np.clip(out, -1.0, 1.0 - 1.0 / (1 << (bits - 1)))      # stay on the grid: +1.0 is not a code
        return out.astype(np.float32), subtype
    return np.clip(out.astype(np.float32), -1.0, 1.0), subtype


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
    v = dsp.meter(sr).integrated_loudness(x.astype(np.float64))     # a meter error propagates: -70 means silence
    return -70.0 if not np.isfinite(v) else float(v)


def dialogue_gated_lufs(x, sr=SR, mask=None, min_seg_s=0.2):
    """Integrated loudness of the speech-active part of a program (ITU-R BS.1770-1 practice).

    A print master's "dialogue-gated" loudness is the loudness measured on the dialogue, not on the whole
    program: a wall-to-wall action sequence must not drag the average up. `mask` is a per-sample 0/1 array
    (analysis.speech.mask_at gives one). Segments shorter than `min_seg_s` are ignored, as a meter ignores a
    blip. Returns None when nothing is marked as speech, so the caller falls back to the full program and
    says so rather than inventing a number.
    """
    y = to_stereo(x)
    if mask is None:
        return None
    m = np.asarray(mask, dtype=np.float32).reshape(-1)
    if len(m) != len(y):
        m = np.interp(np.linspace(0, 1, len(y)), np.linspace(0, 1, len(m)), m) >= 0.5
    else:
        m = m >= 0.5
    if not m.any():
        return None
    idx = np.flatnonzero(m)
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate([[idx[0]], idx[breaks + 1]])
    ends = np.concatenate([idx[breaks], [idx[-1]]])
    min_len = max(1, int(float(min_seg_s) * sr))
    parts = [y[a:b + 1] for a, b in zip(starts, ends) if (b - a + 1) >= min_len]
    if not parts:
        return None
    joined = np.concatenate(parts, axis=0)
    return lufs(joined, sr)


def true_peak_db(x, sr=SR, over=4):
    return dsp.true_peak_db(x, sr, over)


rms_db = dsp.rms_db                 # one RMS-in-dB for the engine (video_program_mix reads it as mixer.rms_db)


def _run(board, x, sr=SR):
    x = to_stereo(x)
    y = board(np.ascontiguousarray(x.T), sr)
    return np.ascontiguousarray(y.T)


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
    if isinstance(room, str) and room not in ROOMS:
        room = resolve_space(room) or room          # a space preset's name: use the room it describes
    if isinstance(room, dict):
        room = (room['room']['rt60'], room['room']['pre_delay_ms'], room['room']['hf_decay'],
                room['room']['early_level'])
    elif isinstance(room, str) and room not in ROOMS:
        raise ValueError(f"unknown room {room!r}: known rooms are {', '.join(sorted(ROOMS))} "
                         f"(or the name of a space preset that has a `room` block)")
    key = (str(room), sr, seed)
    space_cfg = mix_schema.section(_mix(), 'space')         # the IR is built from the piece's space section
    irc = space_cfg['ir']
    key = key + (json.dumps(irc, sort_keys=True),)
    cache_ir = bool(space_cfg['cache_ir'])
    cached = _IR_CACHE.get(key)
    if cached is not None and cache_ir:
        return cached
    rt60, pre, hf, er = ROOMS[room] if isinstance(room, str) else room
    rng = np.random.default_rng(seed)
    n = int((rt60 * float(irc['length_factor']) + pre / 1000.0 + float(irc['length_pad_s'])) * sr)
    t = np.arange(n) / sr
    out = np.zeros((n, 2))
    for ch in range(2):
        acc = np.zeros(n)
        for lo, hi, base, hf_power, level in irc['bands']:      # decay of a band = rt60 x base x hf_decay^power
            mult = float(base) * hf ** float(hf_power)
            w = rng.standard_normal(n)
            sos = signal.butter(2, [lo, min(hi, sr / 2 - 100)], 'band', fs=sr, output='sos')
            w = signal.sosfilt(sos, w)
            env = np.exp(-6.9078 * t / (rt60 * mult))
            acc += w * env * float(level)
        # diffuse onset (no hard click)
        acc *= 1 - np.exp(-t / float(irc['onset_s']))
        out[:, ch] = acc
    if er > 0:
        er_block = space_cfg['er']
        er_level = float(er_block['level'])
        # DRR from an explicit ratio: the taps used to be scaled by sqrt(peak) of the random noise tail, so the
        # early-to-late energy changed with every seed and room size. Now the tap gain sets ER RMS = er_level x tail RMS.
        tail_rms = float(np.sqrt(np.mean(out.astype(np.float64) ** 2)) + 1e-12)
        k = int(er_block['taps'])
        gains = float(er_block['first_gain']) * float(er_block['tap_decay']) ** np.arange(k)
        tap = er_level * tail_rms / max(float(np.sqrt(np.sum(gains ** 2))), 1e-9)
        for ch in range(2):
            times = np.sort(rng.uniform(float(er_block['window_s'][0]), float(er_block['window_s'][1]), k))
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


def reverb_bus(x, room='hall', sr=SR, hp=None, lp=None, seed=3, gated=False, gate_thr=-32.0, gate_release_ms=80.0):
    ret = mix_schema.section(_mix(), 'space')['return']
    hp = float(ret['highpass_hz']) if hp is None else hp
    lp = float(ret['lowpass_hz']) if lp is None else lp
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




def duck_gain(source, n, depth_db=-6, thresh=0.05, attack_ms=8, release_ms=180, sr=SR, lookahead_ms=10, smooth_s=0.0):
    """Gain curve (linear) that dips by depth_db while `source` is above threshold; smooth like a compressor."""
    src = fit(to_stereo(source), n)
    e = envelope(src, sr, attack_ms, release_ms, hold_tail=True)
    thresh = max(float(thresh), 1e-9)                                 # 0 is in range: it must mean "any signal ducks", not 0/0
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
    # One window at a time, summed in float64. Stacking the whole stem and squaring a float64 copy of it held six
    # stem-length buffers per worker at once (measured on a 120 s stem: 267 MB peak for 42 MB of audio), and a mix
    # runs one worker per stem: that was most of why a 21-stem 7.1.2 mix peaked at 13-14 GB.
    starts = list(range(0, len(x) - win + 1, win))
    rms = np.empty(len(starts), dtype=np.float64)
    for k, s in enumerate(starts):
        seg = x[s:s + win]
        rms[k] = np.sqrt(np.einsum('ij,ij->', seg, seg, dtype=np.float64) / seg.size + 1e-20)
    keep = np.flatnonzero(20 * np.log10(rms) > active_db)
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
    if rolelib.is_lead(role):
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


_DISTANCE_KEYS = (('ref_m', 'air_absorption_ref_distance'), ('falloff', 'direct_falloff_scale'),
                  ('air_damping', 'air_absorption_damping'), ('min_cutoff_hz', 'min_air_cutoff_hz'),
                  ('reverb_exponent', 'reverb_distance_scale'), ('proximity_db', 'proximity_db'),
                  ('proximity_hz', 'proximity_hz'),
                  ('er_distance_exponent', 'er_distance_exponent'))      # space preset `distance` key -> mix `spatial` key


def _spatial_cfg(mx, space):
    """The mix preset's `spatial` section with the distance law of a project-owned space laid over it."""
    cfg = dict(mx.get('spatial') or {})
    dc = space.get('distance', {}) if _space_owned(space) else {}
    for k_sp, k_mix in _DISTANCE_KEYS:
        if k_sp in dc:
            cfg[k_mix] = dc[k_sp]
    return cfg


def _air_absorb(x, sp, dist, ref_d, damp, min_cut, sr):
    """Air absorption beyond the reference distance: the measured model when the track names a temperature or
    humidity, else a one-pole low-pass whose cutoff falls with distance."""
    if 'temp_c' in sp or 'rh' in sp:
        import airabs
        return airabs.apply(x, dist - 1.0, temp_c=float(sp.get('temp_c', 20.0)), rh=float(sp.get('rh', 50.0)), sr=sr)
    cutoff = max(min_cut, min(sr * 0.45, 22000.0 / (1.0 + damp * (dist - ref_d))))
    return signal.sosfilt(signal.butter(1, cutoff, btype='lowpass', fs=sr, output='sos'), x, axis=0).astype(np.float32)


def _direct_gain(dist, falloff):
    """The direct level at `dist` metres (1 at one metre or nearer)."""
    return 1.0 / (1.0 + falloff * (dist - 1.0)) if dist > 1.0 else 1.0


def _proximity(x, dist, ref_d, max_db, hz, sr):
    """Low-frequency body for a close panned source (spatial.proximity_gain); no-op at the reference distance."""
    if float(max_db) <= 0.0 or float(dist) >= float(ref_d):
        return x
    import spatial
    return spatial.proximity_gain(x, float(dist), ref_m=float(ref_d), max_db=float(max_db), hz=float(hz), sr=sr)


def _use_proximity(sp_cfg, sp):
    return (float(sp.get('proximity_db', sp_cfg.get('proximity_db', 0.0)) or 0.0),
            float(sp.get('proximity_hz', sp_cfg.get('proximity_hz', 200.0)) or 200.0))


def reverb_send_level(spec, mx=None, space=None):
    """The reverb send for this stem: its `reverb` times the distance factor (DRR), never mutating `spec`."""
    mx = mx or _mix()
    base = float(spec.get('reverb', 0.0) or 0.0)
    sp = spec.get('spatial')
    if not sp:
        return base
    space = _space() if space is None else space
    dist = max(0.5, float(sp.get('distance', 1.5)))
    cfg = _spatial_cfg(mx, space)
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

MIX_CACHE_VERSION = 1                   # bump when the chain's output would change without its inputs changing
_CODE_TAG = None                        # the engine's own identity, hashed once per process


def use_mix_cache(path):
    """Where processed stems are kept between runs; None disables it. A stem is reused only when every input
    that can change its bytes is identical (see `_chain_key`), so a cache can never hand back another mix's audio."""
    STATE['cache_dir'] = str(path) if path else None


def _code_tag():
    """Identity of the code behind a processed stem: an engine edit must never be served an old stem."""
    global _CODE_TAG
    if _CODE_TAG is None:
        import stem_cache
        here = os.path.dirname(os.path.abspath(__file__))
        _CODE_TAG = stem_cache.code_hash(here, files=('mixer.py', 'dsp.py', 'mix_schema.py', 'mix_context.py',
                                                      'presets.py', 'spatial.py', 'airabs.py', 'spatial_hrtf/room.py',
                                                      'spatial_hrtf/binaural.py'),
                                         packages=('spatial_engine',))
    return _CODE_TAG


def _chain_key(name, x, spec, mx, sr, n):
    """What `process_chain` reads: this stem's bytes, its resolved staging/EQ/dynamics spec, the whole mix preset,
    the sample rate and the engine. Placement is deliberately absent: it belongs to the bus, not to the chain."""
    import compute
    import stem_cache
    return stem_cache.digest(dict(version=MIX_CACHE_VERSION, cache=stem_cache.CACHE_VERSION, stem=name,
                                  audio=stem_cache.audio_hash(x, size=16, stride=1), spec=stem_cache.jsonable(spec),
                                  mix=stem_cache.jsonable(mx), sr=int(sr), frames=int(n),
                                  compute=compute.cache_tag(), code=_code_tag()), size=16)


def _cache_files(cache, key, name):
    d = os.path.join(cache, key)
    return os.path.join(d, f'{name}.npy'), os.path.join(d, f'{name}.json')


def _cache_get(cache, key, name, n):
    """The chain's output for this stem, or None. A missing, stale or malformed entry is a miss, never an error."""
    if not (cache and key):
        return None
    arr, meta = _cache_files(cache, key, name)
    if not (os.path.isfile(arr) and os.path.isfile(meta)):
        return None
    try:
        y = np.load(arr)
        with open(meta, encoding='utf-8') as fh:
            m = json.load(fh)
    except (OSError, ValueError):
        return None
    if m.get('version') != MIX_CACHE_VERSION or y.dtype != np.float32 or y.shape != (int(n), 2):
        return None
    for k in ('gain', 'in_lufs', 'chain'):          # the chain's own report, so a hit reads like a fresh run
        if k in (m.get('state') or {}):
            STATE.setdefault(k, {})[name] = m['state'][k]
    return np.ascontiguousarray(y)


def _cache_put(cache, key, name, x, n):
    """Keep one processed stem. Caching is an optimization: a full disk or a read-only project is not a failure."""
    if not (cache and key):
        return
    arr, meta = _cache_files(cache, key, name)
    try:
        os.makedirs(os.path.dirname(arr), exist_ok=True)
        tmp = arr + f'.tmp{os.getpid()}'
        np.save(tmp, np.ascontiguousarray(x, dtype=np.float32))
        os.replace(tmp if tmp.endswith('.npy') else tmp + '.npy', arr)
        with open(meta, 'w', encoding='utf-8') as fh:
            json.dump(dict(version=MIX_CACHE_VERSION,
                           state={k: STATE.get(k, {}).get(name) for k in ('gain', 'in_lufs', 'chain')}), fh)
    except (OSError, ValueError):
        pass


def process_chain(name, x, spec, sr=SR, ctx=None):
    """Everything before placement: gain staging, EQ, dynamics, low-end hygiene, level, automation, fades.

    `spec` is never modified: the send is read by reverb_send_level(). This half is the same for every deliverable
    of a piece, which is why it can be cached across a repeat render and across output formats; `_place` is not
    (a loudspeaker bus hands a track over unplaced, the stereo mix pans it for two speakers).
    """
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
            x = dsp.slope_filter(x, sr, _band(d)['f'], d['type'], d['order'])
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
        cp = mix_schema.comp_params(comp)
        chain.append(pb.Compressor(threshold_db=cp['thr'], ratio=cp['ratio'],
                                   attack_ms=cp['attack'], release_ms=cp['release']))
    if spec.get('saturation', 0):
        chain.insert(0, pb.Distortion(drive_db=spec['saturation']))
    if chain:
        x = _run(pb.Pedalboard(chain), x, sr)
    STATE.setdefault('chain', {})[name] = source
    if spec.get('dynamics') or str(dyn.get('engine', 'pedalboard')) == 'dsp':
        # the Pedalboard chain above already ran the compressor: running it again here would compress twice
        x = _dsp_dynamics(x, dyn, sr, comp_done=isinstance(comp, dict)
                          and str(dyn.get('engine', 'pedalboard')) == 'pedalboard')

    # 4 low-end hygiene
    if role == 'bass' or spec.get('mono_below'):
        x = mono_below(x, spec.get('mono_below', 120), sr)
    # level (in place: the chain above already made this stem's private copy)
    x *= np.float32(10 ** (float(spec.get('gain_db', 0.0)) / 20.0))
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
    if not np.isfinite(x).all():
        raise ValueError(f'stem "{name}" produced non-finite samples (check its eq/comp/spatial values)')
    return np.asarray(x, dtype=np.float32)      # already float32: astype() copied every stem a second time


def process_stem(name, x, spec, sr=SR, ctx=None):
    """One stem through the chain and then placed for this mix's bus."""
    x = process_chain(name, x, spec, sr, ctx)
    if x.size == 0:
        return x
    x = _place(name, x, spec, _mix(), sr)
    if not np.isfinite(x).all():
        raise ValueError(f'stem "{name}" produced non-finite samples (check its eq/comp/spatial values)')
    return np.asarray(x, dtype=np.float32)


def _width_inplace(x, width):
    """width_ms() written into the buffer it is given: the caller already owns that copy."""
    m = (x[:, 0] + x[:, 1]) * 0.5
    s = (x[:, 0] - x[:, 1]) * 0.5 * width
    np.add(m, s, out=x[:, 0])
    np.subtract(m, s, out=x[:, 1])
    return x


def _pan_inplace(x, pan, mode='legacy'):
    """The constant-power balance written into the buffer it is given. 'energy' has its own law, so it stays a copy."""
    if mode == 'energy':
        return dsp.pan_energy(x, pan)
    th = (float(pan) + 1) * np.pi / 4
    x *= np.array([np.cos(th) * np.sqrt(2), np.sin(th) * np.sqrt(2)], dtype=np.float32)
    return x


def _workers_that_fit(requested, n, sr, rcfg):
    """Cap the number of stems processed at once by the memory this process may still take.

    One stem's chain holds several full-length working arrays at the same time: the float32 working copy, the EQ /
    compressor output, the width and pan temporaries and the send. `render.mix_workers: "auto"` used to mean one
    stem per core, which on a 16 GB machine is what took the 7.1.2 mix to 13-14 GB. The fit uses the measured
    working set of one stem per second of audio (`render.mix_worker_mb_per_second`) against the free memory
    `resources.available_gb()` reports, less the headroom the mixer, the gate and the system need.
    """
    if requested <= 1:
        return 1
    import resources
    per_mb = float(rcfg.get('mix_worker_mb_per_second', 2.0))
    per_stem = max(48.0, per_mb * (n / float(sr))) * 1e6
    free = resources.available_gb() * 1e9 - resources.HEADROOM_GB * 1e9
    fit = int(free // per_stem)
    if fit < requested:
        print(f'  [mix] {requested} stem worker(s) requested; {max(1, fit)} fit in the '
              f'{resources.available_gb():.1f} GB free ({per_stem / 1e6:.0f} MB per stem)', flush=True)
    return max(1, min(int(requested), fit))


def _curve(v, kind):
    """An automation curve, 0..1 -> 0..1."""
    if kind == 'cosine':
        return 0.5 - 0.5 * np.cos(np.pi * v)
    if kind == 'exponential':
        return np.asarray(v, float) ** 2
    return np.asarray(v, dtype=np.float32)


def _dsp_dynamics(x, dyn, sr, comp_done=False):
    """The part of the chain Pedalboard cannot do: knee/detector/sidechain-filter/parallel/multiband/
    dynamic EQ/transient shaping. Only reached when a preset asks for it."""
    comp = dyn.get('comp')
    if isinstance(comp, dict) and not comp_done:
        cp = mix_schema.comp_params(comp)
        x = dsp.compressor(x, sr, threshold_db=cp['thr'], ratio=cp['ratio'],
                           attack_ms=cp['attack'], release_ms=cp['release'],
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
        x = dsp.dynamic_eq(x, sr, f=b.get('f', b.get('freq', 1000.0)), q=b.get('q', 1.0),
                           threshold_db=b.get('threshold_db', -24.0), ratio=b.get('ratio', 2.0),
                           attack_ms=b.get('attack_ms', 5.0), release_ms=b.get('release_ms', 80.0),
                           knee_db=b.get('knee_db', 3.0), gain_db=b.get('gain_db', 0.0))
    tr = dyn.get('transient')
    if isinstance(tr, dict):
        x = dsp.transient_shaper(x, sr, float(tr.get('attack_db', 0.0)), float(tr.get('sustain_db', 0.0)))
    return x


def place_of(spec, imm=None):
    """(azimuth, elevation, distance) a track is placed at. With immersive on, a track with no elevation of its own
    takes its role's height, bass and drums stay on the floor, and nothing goes above `max_elevation`."""
    sp = spec.get('spatial') or {}
    az = float(sp.get('azimuth', 0.0))
    el = float(sp.get('elevation', 0.0))
    dist = max(0.5, float(sp.get('distance', 1.5)))
    if imm:
        if 'elevation' not in sp:
            el = float(imm.get('height_by_role', {}).get(spec.get('role', ''), 0.0))
        el = 0.0 if spec.get('role') in ('bass', 'drum') else float(np.clip(el, -90.0, float(imm.get('max_elevation', 60.0))))
    return az, el, dist


def pair_half_width(x, sp, imm):
    """Half the angle between the two sources a stereo stem becomes (0 = one source): the track's own
    `half_width_deg`, else the mix preset's `immersive.pair` width for a bed or for a stem that is really stereo."""
    c = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]) if x.shape[1] == 2 and x.std() > 0 else 1.0
    pair = dict(mix_schema.DEFAULTS['immersive'].get('pair') or {})
    pair.update((imm or {}).get('pair') or {})
    default_hw = float(pair['width_deg_bed'] if sp.get('kind') == 'bed'
                       else (pair['width_deg_stereo'] if np.isfinite(c) and c < 0.9 else 0.0))
    return float(sp.get('half_width_deg', default_hw))


def _place(name, x, spec, mx, sr):
    """Width, widen, pan, distance laws, the binaural route and the DRR send decision."""
    sp = spec.get('spatial')
    mono_render = bool(STATE.get('unplaced'))   # a one-channel deliverable: no pan, no width, no head, only distance
    if not sp:
        if mono_render:
            return x
        w = spec.get('width', 1.0)
        if w != 1.0:
            x = _width_inplace(x, w)
        if spec.get('widen', 0) > 0:
            x = widen(x, spec['widen'], seed=zlib.crc32(name.encode()) % 997, sr=sr)
        return _pan_inplace(x, spec.get('pan', 0.0), spec.get('pan_law', 'legacy'))

    imm = _imm()
    az, el, dist = place_of(spec, imm)

    sp_cfg = _spatial_cfg(mx, _space())
    ref_d = float(sp.get('ref_distance', sp_cfg.get('air_absorption_ref_distance', 1.5)))
    damp = float(sp.get('air_damping', sp_cfg.get('air_absorption_damping', 0.40)))
    min_cut = float(sp.get('min_cutoff_hz', sp_cfg.get('min_air_cutoff_hz', 3200.0)))
    falloff = float(sp.get('falloff_scale', sp_cfg.get('direct_falloff_scale', 0.18)))

    if mono_render:
        return _distance(x, spec, sp, dist, ref_d, damp, min_cut, falloff, sr)
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
    # the ambisonic bus places this track itself (spatial_engine/hoa.py): hand it over unplaced, at its own level
    on_bus = bool(STATE.get('hoa') and imm and sp.get('binaural') is not False)
    if on_bus:                 # no width or widen either: in a 3-D field a stem's width is its pair angle
        x /= np.float32(max(dist, 1.0))
        return np.asarray(x, dtype=np.float32)
    if traj and (traj.get('keyframes') or traj.get('mode')):
        raise ValueError(f'track "{name}": trajectory keyframes and modes need the ambisonic bus; set '
                         f'"immersive": {{"enabled": true, "engine": "hoa_bus"}} in the mix preset')
    elif binaural and route == 'hrtf':
        from spatial_hrtf import binaural as _hrtf
        hrtf_ok = _hrtf.available()
        if not hrtf_ok:
            print('  [spatial] "binaural": "hrtf" asked for but the head data is missing: run '
                  '`python -m spatial_hrtf.data` from scripts/. Using spatial.py.')
    if hrtf_ok:
        _use_head_set(imm)
        # the near field belongs to the space, not to the mix: below one metre the ears hear different distances
        track_space = resolve_space(sp['space']) if sp.get('space') else _space()
        near = (track_space.get('distance') or {}).get('near_field')
        kw = dict(sr=sr, trajectory=traj, temp_c=float(sp.get('temp_c', 20.0)), rh=float(sp.get('rh', 50.0)),
                  near_field=near)
        mono = x.mean(axis=1)
        hw = pair_half_width(x, sp, imm) if imm and not traj else 0.0
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
            p_db, p_hz = _use_proximity(sp_cfg, sp)
            x = spatial.spatialize_stem(x.mean(axis=1), azimuth_deg=az, elevation_deg=el, distance_m=dist,
                                        acoustic_space=space_arg, externalize=True,
                                        proximity_db=p_db, proximity_hz=p_hz,
                                        er_distance_exponent=sp_cfg.get('er_distance_exponent'), sr=sr)
    # A. distance air absorption
    own_distance = spec.get('scene_distance_m') is not None
    if not binaural and not own_distance and dist > ref_d and sp.get('air_absorption', True):
        x = _air_absorb(x, sp, dist, ref_d, damp, min_cut, sr)
    # B. 1/r direct level (in place from here on: this stem's buffer is already private to this mix)
    if not binaural and not own_distance and dist > 1.0:
        x *= np.float32(_direct_gain(dist, falloff))
    if not binaural and not own_distance:
        p_db, p_hz = _use_proximity(sp_cfg, sp)
        x = _proximity(x, dist, ref_d, p_db, p_hz, sr)
    # C. apparent source width
    spread = float(np.clip(float(sp.get('spread', 0.0)), 0.0, 1.0))
    w = float(sp.get('width', spec.get('width', 1.0))) * (1.0 + spread)
    if w != 1.0:
        x = _width_inplace(x, w)
    widen_amt = float(sp.get('widen', spec.get('widen', 0.0)))
    if widen_amt > 0:
        x = widen(x, widen_amt, seed=zlib.crc32(name.encode()) % 997, sr=sr)
    # D. pan (no comb delays)
    pan_val = float(sp.get('pan', np.clip(np.sin(np.radians(az)), -1.0, 1.0))) * (1.0 - spread)
    if not binaural:
        x = _pan_inplace(x, pan_val, sp.get('pan_law', spec.get('pan_law', 'legacy')))
    return x


def _distance(x, spec, sp, dist, ref_d, damp, min_cut, falloff, sr):
    """What distance does to a source that is not placed by a head filter: air absorption and the 1/r level. The
    same two laws _place applies to a panned stem, for a deliverable that has no directions to place it in."""
    if spec.get('scene_distance_m') is not None:        # a physical scene already propagated itself
        return x
    if dist > ref_d and sp.get('air_absorption', True):
        x = _air_absorb(x, sp, dist, ref_d, damp, min_cut, sr)
    if dist > 1.0:
        x = x * np.float32(_direct_gain(dist, falloff))
    p_db, p_hz = _use_proximity(_spatial_cfg(_mix(), _space()), sp)
    return _proximity(np.asarray(x, dtype=np.float32), dist, ref_d, p_db, p_hz, sr)


# orchestral-style seating so layers do not stack in the middle (-1 left .. +1 right)
def default_spec(tr):
    role = rolelib.canonical(tr.get('role', 'chord')) if tr.get('role') else 'chord'
    inst = str(tr.get('instrument', '')).lower().replace(' ', '_')
    # A role with no level is a leak, not a default: -8 dB is somewhere between a pad and a bass. Unlisted
    # roles are one of the four families now, so the number comes from the family's own entry.
    fam = rolelib.FAMILY_OF.get(role, 'harmony')
    level = _level_by_role().get(role)
    if level is None:
        level = _level_by_role().get({'figure': 'melody', 'harmony': 'chord',
                                      'rhythm': 'bass', 'colour': 'pad'}[fam], -8)
    sends = mix_schema.section(_mix(), 'space')['send_by_role']
    d = dict(role=role, gain_db=level,
             pan=from_table(_seating(), inst, 0.0) if role not in ('bass', 'drum', 'drone', 'percussion', 'ostinato') else 0.0,
             reverb=float(sends['default']), widen=_widen_by_role().get(role, 0.0))
    d['inst'] = inst

    passthrough = ('gain_db', 'pan', 'spatial', 'reverb', 'width', 'eq', 'comp', 'hp', 'lp', 'chain',
                   'saturation', 'mono_below', 'duck_by', 'duck_db', 'widen', 'fade_in_s', 'fade_out_s',
                   'intro_outro_boost_db', 'target_lufs', 'crossfade_start_s', 'crossfade_end_s',
                   'outro_start_s', 'outro_end_s', 'spectral_profile', 'preserve_spectrum', 'ref_lufs',
                   'dynamics', 'sidechain', 'pan_law', 'release_ms', 'attack_ms', 'smooth_s',
                   'duck_full_band', 'duck_band_hz')
    inst_cfg = None
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
    # The role's own send, unless the instrument preset set one. The per-role sends that used to be written here
    # (bass 0, drum 0.08, pad 0.30 ...) never applied: every role already carried the default by this line, so a
    # bass was sent to the room like a flute. They are data now (`space.send_by_role`): the schema default lists only
    # `default`, so an older piece mixes as it always has, and a preset that lists a role gets that role's send.
    if 'reverb' not in (inst_cfg if isinstance(inst_cfg, dict) else {}) and role in sends:
        d['reverb'] = float(sends[role])
    d.update({k: tr[k] for k in ('role',) + passthrough if k in tr and tr[k] is not None})
    return d

# ---------------------------------------------------------------------------------------------
# mastering
# ---------------------------------------------------------------------------------------------

def _master_cfg(m, mx):
    """The master block: the chosen profile, the shipped defaults, then the score's own values."""
    mm = mix_schema.section(mx, 'mastering')
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


def master_measures(x, sr=SR):
    """What the delivery report needs: integrated/short-term loudness, LRA, crest, true peak, mono fold."""
    import loudness
    blocks = loudness.Blocks(to_stereo(x), sr)              # one K-weighting pass for every number below
    st = np.array(blocks.gated_series(3.0, 0.5), dtype=float)
    st = loudness.Blocks.lra_gate(st[np.isfinite(st)])      # absolute gate, then the power-mean relative gate
    return {
        'lufs': lufs(x, sr),
        'short_term_max': float(st.max()) if len(st) else float('nan'),
        'short_term_min': float(st.min()) if len(st) else float('nan'),
        'lra': blocks.lra(),                                  # EBU Tech 3342, from the standard's own series
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
    mm = cfg['_cfg']
    # Pedalboard's high-pass is first order (6 dB/octave); `highpass_order` cascades it, so a sub band the master should
    # not carry can be cut harder without a second filter family. 1 is the filter every older master was made with.
    chain = ([pb.HighpassFilter(float(mm['highpass_hz'])) for _ in range(max(1, int(mm.get('highpass_order') or 1)))]
             if float(mm.get('highpass_hz') or 0.0) > 0.0 else [])
    tones = mm.get('tones') or {}
    if tone not in tones:
        # An unlisted tone has always mastered flat without a word. It still masters flat (an older score keeps
        # its sound), but it says so: a tone name that does nothing is a decision nobody made.
        sys.stderr.write(f'[master] tone "{tone}" is not in mastering.tones ({", ".join(sorted(tones))}): '
                         f'mastered neutral. Add it to the mix preset to give it a curve.\n')
        tone = 'neutral'
    chain += [eq_object(band) for band in tones.get(tone) or []]
    glue = mm.get('glue') or {}
    if cfg.get('glue', True) and glue:
        chain.append(pb.Compressor(threshold_db=float(glue['threshold_db']), ratio=float(glue['ratio']),
                                   attack_ms=float(glue['attack_ms']), release_ms=float(glue['release_ms'])))
    if cfg.get('width'):
        x = width_ms(x, cfg['width'])
    x = _run(pb.Pedalboard(chain), x, sr)
    if cfg.get('mono_below'):
        x = mono_below(x, cfg['mono_below'], sr)
    try:
        lim = pb.Pedalboard([pb.BrickwallLimiter(ceiling_db=ceiling, true_peak=True)])
    except Exception:
        fb = mm.get('fallback_limiter') or {}
        lim = pb.Pedalboard([pb.Limiter(threshold_db=ceiling - float(fb['margin_db']), release_ms=float(fb['release_ms']))])
    crest_floor = float(mm.get('crest_floor_db', 0.0))
    conv = mm.get('converge') or {}
    if int(conv['max_iterations']) < 1:
        raise ValueError('mastering.converge.max_iterations must be at least 1: with none, the limiter never runs')
    in_lufs = lufs(x, sr)
    if in_lufs <= -69.9:               # silence reads -70: a gain of target + 70 dB would only amplify the noise floor
        sys.stderr.write('[master] the programme is silent (-70 LUFS); no gain applied to reach the target.\n')
        gain_db = 0.0
    else:
        gain_db = target - in_lufs
    y = x
    for _ in range(int(conv['max_iterations'])):                                               # converge on loudness with the limiter in the loop
        y = _run(lim, x * 10 ** (gain_db / 20.0), sr)
        err = target - lufs(y, sr)
        if abs(err) < float(conv['tolerance_lu']):
            break
        if crest_floor > 0 and dsp.crest_db(y) < crest_floor:
            sys.stderr.write(f'[master] a {target} LUFS target would take the crest under {crest_floor} dB '
                             f'(at {dsp.crest_db(y):.1f} dB); stopping. Raise the headroom or lower the target.\n')
            break
        gain_db += err * float(conv['step'])   # damped step: >1.0 on a saturating limiter is an over-relaxed fixed point
    reached = lufs(y, sr)
    if abs(target - reached) > float(conv['report_miss_lu']):
        sys.stderr.write(f'[master] reached {reached:.1f} LUFS, not {target}: the music is too dynamic for that target under a '
                         f'{ceiling} dBTP ceiling without squashing it. Kept natural dynamics; lower the target or accept it.\n')
    tp = true_peak_db(y, sr)
    if tp > ceiling:                       # last safety: oversampled true peak
        y = y * 10 ** ((ceiling - tp) / 20.0)
        reached = lufs(y, sr)              # the trim moves the whole track: report what was actually delivered
    y = np.asarray(y, dtype=np.float32)
    STATE['master'] = dict(master_measures(y, sr), target=target, ceiling=ceiling, profile=cfg.get('_profile'),
                           reached=reached,
                           limited_by_ceiling=bool(tp > ceiling))
    return y


def suggest_master_target(x, sr=SR, lufs_target=-14.0, ceiling=-1.5):
    """Can this material reach the target without destroying it? Returns (feasible, why)."""
    min_crest = float(mix_schema.section(_mix(), 'mastering')['min_crest_db'])
    m = master_measures(x, sr)
    crest = m['crest']
    needed = lufs_target - m['lufs']
    ceiling_room = ceiling - m['true_peak']
    if needed <= 0:
        return True, f'already at {m["lufs"]:.1f} LUFS; the target needs no gain'
    if crest - needed < min_crest:
        return False, (f'crest factor is {crest:.1f} dB; reaching {lufs_target} LUFS needs {needed:+.1f} dB, '
                       f'which would leave {crest - needed:.1f} dB of crest, below the {min_crest:g} dB this mix preset treats as music')
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
    if not any(rolelib.is_lead(s.get('role')) for s in specs.values()):
        return specs
    for name, sp in specs.items():
        if sp.get('role') in ('pad', 'texture', 'drone', 'chord', 'arp', 'ostinato', 'counter', 'environment'):
            eq = sp.setdefault('eq', [])
            if not any(d.get('type') == 'peak' and abs(d.get('f', 0) - band) < 1 for d in eq):
                depth = carve - 1.5 if sp.get('role') == 'environment' else carve
                depth = max(depth, -abs(limit)) if limit > 0 else depth
                eq.append(dict(type='peak', f=band, gain=depth, q=1.0))
    return specs


def _band_center_q(lo, hi):
    """The centre and Q that make dsp.dynamic_eq span exactly [lo, hi].

    dynamic_eq's band runs f / (1 + 1/2q) .. f * (1 + 1/2q), so the requested edges fix both: the geometric
    centre is sqrt(lo*hi) and the half-width ratio gives q = 1 / (2 * (ratio - 1)).
    """
    lo, hi = float(lo), float(hi)
    if lo <= 0.0 or hi <= lo:
        raise ValueError('lead_carve.bands_hz needs pairs with 0 < lo < hi')
    f = float(np.sqrt(lo * hi))
    ratio = float(np.sqrt(hi / lo))
    return f, 1.0 / (2.0 * (ratio - 1.0))


def apply_lead_carve(processed, specs, mx=None, sr=SR, intent=None):
    """Carve the beds only while the lead is actually sounding in the band they share.

    carve_for_lead() is a decision taken from the score: one fixed dip, for the whole piece, in one band, whether
    or not the lead is there (which is why it can only be small). This is the same rule driven by the lead's own
    signal: each band of each bed is keyed by the band-passed lead, so a bed keeps its body while the lead rests
    and yields only where the two actually collide. Roles the sidechain already ducks under the same source are
    skipped, so nothing is moved twice.

    With `lead_carve.from_intent` on, the direction sheet's `mix_intent` (carried on the score) decides what is
    carved for: `hero` names the track the beds yield to and `leave_free_hz` is the band they yield in. Until this
    existed those two fields were words for the listening pass only; nothing in the mix read them.

    Mutates and returns `processed` (the same dict STATE['processed'] points at).
    """
    mx = mx or _mix()
    cfg = dict(mx.get('lead_carve') or {})
    if not cfg.get('enabled'):
        return processed
    used = {}
    if cfg.get('from_intent') and isinstance(intent, dict):
        hero = intent.get('hero')
        if isinstance(hero, str) and hero in specs:
            cfg['source'] = used['hero'] = hero
        free = intent.get('leave_free_hz')
        if isinstance(free, (list, tuple)) and len(free) == 2 and float(free[1]) > float(free[0]) > 0.0:
            cfg['bands_hz'] = [[float(free[0]), float(free[1])]]
            used['leave_free_hz'] = cfg['bands_hz'][0]
    STATE['mix_intent_used'] = used
    if cfg.get('source'):
        lead = str(cfg['source'])
    else:
        leads = [n for n, sp in specs.items() if rolelib.is_lead(sp.get('role'))]
        if not leads:
            return processed                              # no lead, nothing to make room for
        lead = max(leads, key=lambda n: float(specs[n].get('gain_db', 0.0)))
    if lead not in processed or lead not in specs:
        return processed
    src = to_stereo(processed[lead])
    roles = tuple(cfg.get('roles') or mix_schema.section(mx, 'sidechain')['band_roles'])
    ratio = max(1.0, float(cfg.get('ratio', 2.0)))
    thr = float(cfg.get('threshold_db', -30.0))
    att = float(cfg.get('attack_ms', 6.0))
    rel = float(cfg.get('release_ms', 120.0))
    for pair in (cfg.get('bands_hz') or []):
        lo, hi = float(pair[0]), float(pair[1])
        f, q = _band_center_q(lo, hi)
        sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
        sc = signal.sosfiltfilt(sos, src.mean(axis=1)).astype(np.float32)
        for name, sp in specs.items():
            if name == lead or sp.get('role') not in roles or name not in processed:
                continue
            if cfg.get('skip_ducked', True) and sp.get('duck_by'):
                continue
            # gain_db stays 0: the band is only reduced while the sidechain is over threshold, so a bed
            # keeps its body in the rests and yields only where the lead is actually there.
            processed[name] = dsp.dynamic_eq(
                to_stereo(processed[name]), sr, f=f, q=q, threshold_db=thr, ratio=ratio,
                attack_ms=att, release_ms=rel, sidechain=sc)
    return processed


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


def _use_head_set(imm):
    """The head set is a preset value: a listener's own set when the piece names one, the bundled one otherwise."""
    from spatial_hrtf import binaural as _hrtf
    want_set = str(((imm or {}).get('hrtf') or {}).get('dataset') or '')
    try:
        _hrtf.set_dataset(_head_set(want_set))
    except Exception as e:
        print(f'  [spatial] head set "{want_set}" could not be used ({e}); using the bundled set')
        _hrtf.set_dataset(None)


def _hoa_bus(score, bus, sr):
    """(the bus that places the tracks or None, the bus to sum into). With immersive on, a bus that places tracks
    itself (ambisonic, loudspeaker layout, ADM objects) is handed every track unplaced; a stereo or headphone mix
    on the ambisonic engine gets an ambisonic bus of its own; a loudspeaker bus keeps its own panning for the direct
    sound and is given the room through one."""
    imm = _imm()
    if not imm:
        return None, bus
    on_hoa = str(imm.get('engine', 'per_stem')) == 'hoa_bus'
    if not on_hoa and not getattr(bus, 'places_tracks', False):
        return None, bus
    from spatial_hrtf import binaural as _hrtf
    from spatial_engine import hoa
    kw = dict(sr=sr, order=int(imm.get('order', 5)), imm=imm, space=_space(), score=score)
    if getattr(bus, 'places_tracks', False):
        if hasattr(bus, 'attach_room'):                   # a loudspeaker layout
            bus.imm, bus.score = imm, score
            if on_hoa:
                bus.attach_room(hoa.HoaBus(decode='speakers', speakers=bus.speakers, room_only=True, **kw))
        return bus, bus
    if bus is None:
        if not _hrtf.available():
            print('  [spatial] "engine": "hoa_bus" needs the head data: run `python -m spatial_hrtf.data` from '
                  'scripts/. Using the per-stem engine.')
            return None, None
        if str(imm.get('stereo_decode', 'binaural')) == 'speakers':
            from spatial_engine import config as _cfg
            made = hoa.HoaBus(decode='speakers', speakers=_cfg.speakers(imm.get('stereo_layout', 'stereo_bs775')), **kw)
            return made, made
        _use_head_set(imm)
        made = hoa.HoaBus(decode='binaural', **kw)
        return made, made
    return None, bus


def sympathetic_bed(score, processed, specs, mx, sr=SR):
    """The stereo bed of the mix preset's `sympathetic_resonance` block, or None when it is off or has nothing to
    ring with. One fixed tuning for the piece, so nothing is retuned or crossfaded while it plays."""
    cfg = mx.get('sympathetic_resonance') or {}
    if not cfg.get('enabled'):
        return None
    want = set(cfg.get('sources') or [])
    names = [k for k, sp in specs.items() if k in processed and (
        (k in want or sp.get('role') in want) if want else sp.get('role') not in ('drum', 'percussion', 'environment'))]
    if not names:
        return None
    tuning = cfg.get('tuning', 'score_scale')
    if tuning == 'score_scale':
        import cli_util
        weight = np.zeros(12)
        for tr in score.get('tracks', []):
            if tr.get('name') in names:
                for nt in tr.get('notes', []):
                    try:
                        weight[cli_util.midi_int(nt['p']) % 12] += float(nt.get('d', 1.0))
                    except (ValueError, KeyError, TypeError):
                        continue                  # a drum key or an effect hit has no pitch class
        base = 69.0 + 12.0 * np.log2(float(cfg['low_hz']) / 440.0)
        pcs = [int(i) for i in np.argsort(-weight, kind='stable')[:int(cfg['strings'])] if weight[i] > 0]
        freqs = [440.0 * 2.0 ** ((np.ceil((base - pc) / 12.0) * 12.0 + pc - 69.0) / 12.0) for pc in pcs]
    elif isinstance(tuning, (list, tuple)):
        freqs = [float(f) for f in tuning]
    else:
        raise ValueError(f'sympathetic_resonance.tuning must be "score_scale" or a list of Hz (got {tuning!r})')
    freqs = [f * h for f in freqs for h in range(1, int(cfg['partials']) + 1)]
    src = np.sum([to_stereo(processed[k]) for k in names], axis=0).mean(axis=1)
    y = dsp.resonator_bank(src, sr, freqs, float(cfg['q']))
    ref, got = float(np.sqrt(np.mean(src ** 2))), float(np.sqrt(np.mean(y ** 2)))
    if ref <= 0 or got <= 0:
        return None
    y = (y * (ref / got) * 10.0 ** (float(cfg['level_db']) / 20.0)).astype(np.float32)
    return widen(to_stereo(y), amount=float(cfg['width']), sr=sr)


def theatrical_send_gain(dry, sr=SR, cfg=None):
    """How much of the room send survives each instant: less while the direct sound is attacking.

    A hall heard from the audience is not a wash: the attack of a bow, a felt hammer or a stick reaches the ear
    before the room answers, so the direct sound leads the early reflections and the tail. That is a
    direct-to-reverberant ratio that changes *within* a note. The stem's reverb send is static, so this measures
    the front of each event (fast envelope over slow envelope) and dips the send by at most `duck_db` there.
    It is the detail-vs-depth control, not a de-verb: a sustained body keeps its send.

    `cfg` is the mix preset's `theatrical` section. Returns one gain per sample.
    """
    th = cfg if isinstance(cfg, dict) else {}
    d = dict(mix_schema.DEFAULTS['theatrical']['detail'], **(th.get('detail') or {}))
    if not d.get('enabled', True) or float(d.get('duck_db', 0.0)) <= 0.0:
        return np.ones(len(dry), np.float32)
    fast = dsp.envelope(dry, sr, max(1.0, float(d.get('attack_ms', 4.0))),
                        max(2.0, float(d.get('release_ms', 40.0))))
    slow = dsp.envelope(dry, sr, 60.0, 240.0)
    ref = max(3.0, float(d.get('ref_db', 18.0)))
    front = np.clip(20.0 * np.log10((fast + 1e-12) / (slow + 1e-12)) / ref, 0.0, 1.0)
    return (10.0 ** (-float(d.get('duck_db', 2.5)) * front / 20.0)).astype(np.float32)


def _theatrical_low_mid(y, sr, cfg):
    """The 180-420 Hz dynamic lean, linked across the channels it is given."""
    lm = dict(mix_schema.DEFAULTS['theatrical']['low_mid'], **(cfg.get('low_mid') or {}))
    if not lm.get('enabled', True) or float(lm.get('max_dip_db', 0.0)) <= 0.0:
        return y
    lo = max(40.0, float(lm.get('low_hz', 180.0)))
    hi = min(sr * 0.45, float(lm.get('high_hz', 420.0)))
    if hi <= lo:
        return y
    f = 0.5 * (lo + hi)
    q = f / (hi - lo)
    # A threshold in dBFS is wrong here: this stage runs before the master, so the same programme can sit at any
    # level. The band's own loud level (95th percentile of its sounding frames) minus `range_db` is the threshold,
    # so the lean follows the density of the piece rather than its pre-master gain.
    band = signal.sosfilt(signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos'), y, axis=0)
    lvl = 20.0 * np.log10(dsp.envelope(band, sr, 50.0, 200.0) + 1e-12)
    sounding = lvl[lvl > float(lvl.max()) - 45.0]
    threshold = float(np.percentile(sounding, 95.0)) - float(lm.get('range_db', 6.0)) if sounding.size else -30.0
    # a maximum dip at 6 dB over threshold becomes the ratio that produces it
    ceiling = 1.0 / (1.0 - float(np.clip(float(lm.get('max_dip_db', 2.0)) / 6.0, 0.0, 0.9)))
    ratio = max(1.0, min(float(lm.get('ratio', 2.0)), ceiling))
    return dsp.dynamic_eq(y, sr, f=f, q=q, threshold_db=threshold,
                          ratio=ratio, attack_ms=float(lm.get('attack_ms', 20.0)),
                          release_ms=float(lm.get('release_ms', 180.0)),
                          knee_db=float(lm.get('knee_db', 6.0)), gain_db=0.0)


def _theatrical_air_curve(y, sr, cfg):
    """One gain curve for the air shelf, from the piece's own loud end (None = no lift)."""
    air = dict(mix_schema.DEFAULTS['theatrical']['air'], **(cfg.get('air') or {}))
    if not air.get('enabled', True) or float(air.get('max_lift_db', 0.0)) <= 0.0:
        return None
    env = dsp.envelope(y, sr, 60.0, 240.0)
    edb = 20.0 * np.log10(env + 1e-12)
    sounding = edb[edb > float(edb.max()) - 50.0]
    if sounding.size < 8:
        return None
    ref = float(np.percentile(sounding, 95.0))
    span = max(1.0, float(air.get('window_db', 6.0)))
    lift = float(air['max_lift_db']) * np.clip((edb - (ref - span)) / span, 0.0, 1.0)
    return (10.0 ** (lift / 20.0)).astype(np.float32), float(air.get('hz', 9000.0))


def _apply_theatrical_air(y, curve, sr):
    if curve is None:
        return y
    gain, hz = curve
    hz = min(sr * 0.45, hz)
    hf = signal.sosfilt(signal.butter(2, hz, btype='high', fs=sr, output='sos'), y, axis=0).astype(np.float32)
    return (y + hf * (gain - 1.0)[:, None]).astype(np.float32)


def theatrical_tone(x, sr=SR, cfg=None):
    """The programme-side half of the theatrical stage: lean low-mids and air that survives a dense peak.

    `low_mid` compresses only 180-420 Hz when that band is loud, so many heavy layers cannot thicken the region
    where the ear localises weight and loses the sub. `air` lifts the top octave near the piece's own loud end,
    capped at `max_lift_db` and faded out `window_db` below it: at a quiet moment there is nothing to restore, at
    a dense peak the field does not fold inward and lose its upper air. Both are starting values, not
    measurements of a room.

    `cfg` is the mix preset's `theatrical` section. A multichannel bus is left to its own master.
    """
    c = cfg if isinstance(cfg, dict) else {}
    y = to_stereo(x).astype(np.float32)
    y = _theatrical_low_mid(y, sr, c)
    return _apply_theatrical_air(y, _theatrical_air_curve(y, sr, c), sr).astype(np.float32)


def theatrical_multichannel(x, sr=SR, cfg=None, skip=()):
    """The same stage for a discrete deliverable: every full-range channel, LFE left alone.

    The low-mid compressor is linked across the full-range channels and the air shelf follows one programme
    curve, so a dense peak cannot move the front image; the LFE keeps its band because a 180-420 Hz lean and a
    9 kHz shelf are not bass-management decisions. `skip` is a set of channel indices to leave untouched.
    """
    c = cfg if isinstance(cfg, dict) else {}
    y = dsp.to_2d(x).astype(np.float32)
    skip = {int(i) for i in (skip or ())}
    idx = [i for i in range(y.shape[1]) if i not in skip]
    if not idx:
        return y
    main = y[:, idx]
    main = _theatrical_low_mid(main, sr, c)
    main = _apply_theatrical_air(main, _theatrical_air_curve(main, sr, c), sr)
    y[:, idx] = main
    return y.astype(np.float32)


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


def mix_stems(score, stems, sr=SR, ctx=None, bus=None):
    """Return the pre-master mix (float32).

    `bus` is an object with add(name, signal, spec), add_reverb(signal) and result(); when it is given, every
    finished track signal and the shared reverb return are handed to it instead of being summed to stereo, and its
    result is returned. That is the seam the discrete multichannel renderer uses: every mixing decision stays here,
    and only the summing target changes.
    """
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
    blend = mix_schema.section(mx, 'space').get('auto_env_blend') or {}
    has_env = any(specs[name].get('role') == 'environment' for name in stems)
    if has_env and blend.get('enabled', True):
        floors = {role: (float(v[0]), str(v[1])) for role, v in (blend.get('floors') or {}).items()}
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
                sp['duck_db'] = float(sp.get('duck_db', mix_schema.section(mx, 'sidechain')['legacy_env_duck_db']))
    if sc_mode == 'off':
        for sp in specs.values():
            sp.pop('duck_by', None)

    carve_for_lead(specs, mx)                           # the mix rule: beds make room for the lead
    dry = np.zeros((n, 2), np.float32)
    send = np.zeros((n, 2), np.float32)
    processed = {}
    own_bus, bus = _hoa_bus(score, bus, sr)
    STATE['hoa'] = own_bus is not None                  # _place leaves these tracks for the bus to place
    STATE['unplaced'] = bool(getattr(bus, 'unplaced', False)) and own_bus is None   # an immersive bus has its own hand-over
    rcfg = mix_schema.section(mx, 'render')
    import compute
    comp = rcfg.get('compute') or {}
    want = (str(comp.get('device') or 'auto').lower(), comp.get('workers'))
    if STATE.get('compute_request') != want:               # resolve once per setting, not once per mix
        compute.configure(*want)
        STATE['compute_request'] = want
    STATE['compute'] = compute.info()
    workers = rcfg.get('mix_workers', 1)
    workers = (os.cpu_count() or 1) if workers == 'auto' else max(1, int(workers))
    workers = _workers_that_fit(workers, n, sr, rcfg)
    cache = STATE.get('cache_dir')
    keys = {}
    if cache:
        try:
            keys = {nm: _chain_key(nm, v, specs[nm], mx, sr, n) for nm, v in stems.items()}
        except Exception as exc:                  # a cache that cannot be keyed is no cache, never a failed render
            print(f'  [mix] processed-stem cache off for this run ({exc})')
            keys = {}

    def _work(item):
        """One stem: its chain (reused when nothing it reads changed), then its place on this mix's bus.

        The chain is cached and placement is not, so a second format reuses the first one's EQ and dynamics and
        only re-places the stems, and a repeat render after one note fix re-runs only the stems that changed.
        """
        nm, v = item
        _context_for(score, ctx)                  # the context is per thread: this one reads the piece's own
        got = _cache_get(cache, keys.get(nm), nm, n) if keys else None
        hit = got is not None
        x = got if hit else process_chain(nm, v, specs[nm], sr, ctx)
        if not hit and x.size:
            _cache_put(cache, keys.get(nm), nm, x, n)   # before placement: the cache holds the dry chain output,
        y = fit(_place(nm, x, specs[nm], mx, sr), n) if x.size else fit(x, n)   # and _place may work in place
        return nm, y, hit

    try:
        if workers > 1 and len(stems) > 1:
            # One stem per thread. The plugins and the filters release the interpreter lock, the context is
            # per-thread (the worker installs the piece's own), and every stem writes only its own entries in
            # STATE, so the result is the same samples as the serial loop, in the same order.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(workers, len(stems))) as pool:
                done = list(pool.map(_work, stems.items()))
        else:
            done = [_work(item) for item in stems.items()]
    finally:
        STATE['hoa'] = False
        STATE['unplaced'] = False
    for nm, y, _hit in done:
        processed[nm] = y
    import resources
    resources.release_memory()                  # the stem chains ran on several threads: their freed 64-bit temporaries are still held by the heap
    STATE['cache'] = dict(dir=cache, hits=sum(1 for _n, _y, h in done if h), stems=len(done))
    apply_lead_carve(processed, specs, mx, sr, intent=score.get('mix_intent'))  # the dynamic half of the lead rule, keyed by the lead itself
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

    sc = mix_schema.section(mx, 'sidechain')
    band = tuple(float(v) for v in sc['band_hz'])
    residual = float(sc['residual'])
    timing = sc['timing']
    for name, sp in specs.items():
        src = sp.get('duck_by')
        if not src or src not in processed:
            continue
        is_env = (sp.get('role') == 'environment')
        base = timing['environment'] if is_env else timing['default']
        rel_ms = float(sp.get('release_ms', (sc.get('release_ms') or {}).get(sp.get('role'), base['release_ms'])))
        att_ms = float(sp.get('attack_ms', (sc.get('attack_ms') or {}).get(sp.get('role'), base['attack_ms'])))
        smooth_s = float(sp.get('smooth_s', base['smooth_s']))
        d_gain = duck_gain(processed[src], n, sp.get('duck_db', float(sc['default_duck_db'])), float(sc['threshold']),
                           attack_ms=att_ms, release_ms=rel_ms,
                           lookahead_ms=float(sc['lookahead_ms']), smooth_s=smooth_s, sr=sr)
        if is_env and sc.get('env_plateau', True) and first_note_s is not None and last_note_s is not None \
                and last_note_s > first_note_s:
            # Lock a bed to a steady plateau across the musical body: it should not swell during a
            # two-second instrumental pause mid-piece.
            i_body_start = int(first_note_s * sr)
            i_body_end = min(n, int(last_note_s * sr))
            if i_body_end > i_body_start:
                min_floor = 10.0 ** (float(sp.get('duck_db', float(sc['default_duck_db']))) / 20.0)
                plateau_gain = float(np.percentile(d_gain[i_body_start:i_body_end], float(sc['plateau_percentile'])))
                plateau_gain = max(min_floor, min(plateau_gain, 1.0))
                fade_s = min(float(sc['plateau_fade_max_s']), (last_note_s - first_note_s) * float(sc['plateau_fade_frac']))
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
        if sp.get('role') in sc['band_roles'] and not sp.get('duck_full_band'):
            # only the band the lead lives in takes the whole duck; the rest follows at `residual` of it.
            # mid*d + (x - mid)*d**residual == x*res + mid*(d - res), written in place: the placed stem becomes
            # the result, so a ducked track costs two full-length curves instead of four temporaries plus an output.
            x_ = processed[name]
            sos_b = signal.butter(2, [band[0], band[1]], btype='band', fs=sr, output='sos')
            mid = signal.sosfiltfilt(sos_b, x_, axis=0).astype(np.float32)
            res = np.power(d_gain, residual)
            x_ *= res[:, None]
            mid *= (d_gain - res)[:, None]
            x_ += mid
            processed[name] = x_
        else:
            processed[name] *= d_gain[:, None]

    bed = sympathetic_bed(score, processed, specs, mx, sr)
    if bed is not None:
        bed = fit(bed, n)
        if bus is not None:
            bed_spec = default_spec(dict(role='pad'))
            if (mx.get('sympathetic_resonance') or {}).get('spatial'):
                bed_spec['spatial'] = dict(mx['sympathetic_resonance']['spatial'])
            bus.add('sympathetic_resonance', bed, bed_spec)
        else:
            dry += bed
    th = mix_schema.section(mx, 'theatrical')
    detail_gain = None
    if th.get('enabled') and bus is None:
        dry_ref = np.zeros((n, 2), np.float32)
        for y in processed.values():
            dry_ref[:min(len(y), n)] += y[:min(len(y), n)]
        detail_gain = theatrical_send_gain(dry_ref, sr, th)
    law = _space().get('distance', {}).get('pre_delay_law') if _space_owned(_space()) else None
    STATE['sends'] = {}
    for name, y in processed.items():
        if bus is not None:
            bus.add(name, y, specs[name])
        else:
            dry += y
        send_level = reverb_send_level(specs[name], mx, _space())
        STATE['sends'][name] = send_level
        ys = y * send_level
        if detail_gain is not None:
            ys = ys * detail_gain[:len(ys), None]
        sp_ = specs[name].get('spatial')
        if law and sp_:
            k = int(float(np.clip(law['base_ms'] - law['per_m'] * float(sp_.get('distance', 1.5)), 0.0,
                                  law['max_ms'])) * sr / 1000.0)
            if k > 0:
                ys = np.pad(ys, ((k, 0), (0, 0)))[:len(ys)]
        send += ys
    room = _space() if _space().get('room') else score.get('room', 'hall')
    if space_name != 'none' and send.any():
        ret = reverb_bus(send, room, sr) * float(score.get('mix', {}).get('reverb_return', 1.0))
        if bus is not None:
            bus.add_reverb(ret)
        else:
            total = len(ret)
            if total > len(dry):                 # grow the bus in place: a second full-length buffer is a copy
                dry = np.pad(dry, ((0, total - len(dry)), (0, 0)))
            dry[:total] += ret
            mix = dry
    else:
        mix = dry
    if th.get('enabled') and bus is None:
        out = theatrical_tone(mix, sr, th)
        mix = out
    else:
        out = bus.result() if bus is not None else mix
    # a mix bus can collect a slow drift from summed low beds and reverbs; DC-block it once, below hearing
    if getattr(out, 'ndim', 1) == 2 and len(out):
        sos = signal.butter(2, 30.0, btype='high', fs=sr, output='sos')   # sub-38 Hz only wanders the block mean; nothing musical lives there
        out = signal.sosfilt(sos, out, axis=0).astype(np.float32)
    return out


def trim_tail(x, sr=SR, floor_db=None):
    floor_db = float((_mix().get('space') or {}).get('tail_guard_db', -62.0)) if floor_db is None else floor_db
    env = np.abs(x).max(1)
    idx = np.where(env > 10 ** (floor_db / 20))[0]
    end = (idx[-1] + int(0.15 * sr)) if len(idx) else len(x)
    return x[:min(len(x), end)]


def fades(x, sr=SR, fin=0.02, fout=0.6):
    n_in, n_out = min(int(fin * sr), len(x)), min(int(fout * sr), len(x))
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
    # the folded tail fades OUT across the seam while the body stays at full level: body + tail at the start of the
    # fade, body alone at its end. (Fading the body out as well dropped the programme for 35 ms and then stepped.)
    w = np.linspace(0.0, np.pi / 2.0, xf)[:, None]
    body[k - xf:k] += tail[k - xf:k] * np.cos(w)
    return body


def _validate_export(path, sr, expected_seconds=None, ceiling=0.0, true_peak=None):
    """Check the file that was actually written: format, channels, length, peak and true peak.

    true_peak  a measurement already taken on the same audio, reused instead of a second 4x oversampled pass.
    """
    info = sf.info(path)
    # float32 (the file's own precision; PCM_24 needs no float64 copy) and blockwise: a whole-file `np.abs(data)`
    # temporary doubled the master's memory twice over just to read its peak.
    data, _ = sf.read(path, always_2d=True, dtype='float32')
    full = 1.0 - 1.0 / (1 << 23)                       # 0.999 counts a valid -0.01 dBFS PCM_24 peak as clipping
    peak, clipped = 0.0, 0
    for a in range(0, len(data), 1 << 18):
        seg = data[a:a + (1 << 18)]
        peak = max(peak, float(np.abs(seg).max()))
        clipped += int(np.count_nonzero(np.abs(seg) >= full))
    peak_db = 20 * np.log10(peak + 1e-12)
    rep = {'path': path, 'sr': info.samplerate, 'channels': info.channels, 'frames': info.frames,
           'subtype': info.subtype, 'peak_db': peak_db,
           'true_peak_db': float(true_peak) if true_peak is not None else true_peak_db(data, info.samplerate),
           'clipped_samples': clipped,
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
    over = int(np.sum(np.abs(out) >= 1.0))         # the no-master path clipped without ever saying so
    if over:
        sys.stderr.write(f'[export] {over} samples above full scale before the write (master skipped); '
                         f'the file is hard-clipped there\n')
    ceiling_db = None
    if master:             # the ceiling the master chain aimed at, less the write guard, so the written file stays under it
        ceiling_db = (float(_master_cfg(m, _mix()).get('true_peak', -1.5))
                      - float(mix_schema.section(_mix(), 'mastering')['true_peak_write_guard_db']))
    out, dtype_subtype = finalize_pcm(out, sr, mm_cfg, ceiling_db=ceiling_db)
    sf.write(out_path, out, sr, subtype=dtype_subtype)
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
