"""dsp_utils - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

from scipy import signal
import dsp
import json
import mix_engine.meters as meters
import mix_schema
import numpy as np
import pedalboard as pb
import resources
import soundfile as sf
from .core import ROOMS, SR, _active_db, _mix, _space, _space_owned, _space_owned_hook, resolve_space

rms_db = dsp.rms_db                 # one RMS-in-dB for the engine (video_program_mix reads it as mixer.rms_db)

_IR_CACHE = {}          # one impulse response per (room description, sample rate, seed)

IR_CACHE_MAX = 8        # a scoring batch may visit many rooms; keep only the ones still in play

EQ_TYPES = {'peak': lambda d: pb.PeakFilter(d['f'], d.get('gain', 0), d.get('q', 1.0)),
            'bell': lambda d: pb.PeakFilter(d['f'], d.get('gain', 0), d.get('q', 1.0)),
            'notch': lambda d: pb.PeakFilter(d['f'], d.get('gain', -18.0), d.get('q', 2.0)),
            'hp': lambda d: pb.HighpassFilter(d['f']), 'highpass': lambda d: pb.HighpassFilter(d['f']),
            'lp': lambda d: pb.LowpassFilter(d['f']), 'lowpass': lambda d: pb.LowpassFilter(d['f']),
            'lowshelf': lambda d: pb.LowShelfFilter(d['f'], d.get('gain', 0), d.get('q', 0.7)),
            'highshelf': lambda d: pb.HighShelfFilter(d['f'], d.get('gain', 0), d.get('q', 0.7))}

_DISTANCE_KEYS = (('ref_m', 'air_absorption_ref_distance'), ('falloff', 'direct_falloff_scale'),
                  ('air_damping', 'air_absorption_damping'), ('min_cutoff_hz', 'min_air_cutoff_hz'),
                  ('reverb_exponent', 'reverb_distance_scale'), ('proximity_db', 'proximity_db'),
                  ('proximity_hz', 'proximity_hz'),
                  ('er_distance_exponent', 'er_distance_exponent'))      # space preset `distance` key -> mix `spatial` key


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
    """True peak, measured by mix_engine.meters (4x is the BS.1770-5 reference; the gate judges 8x too)."""
    return meters.true_peak_db(x, sr, over)


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


def eq_object(b):
    """A preset EQ band as a Pedalboard filter. A band with an explicit `order` is applied by dsp."""
    b = _band(b)
    fn = EQ_TYPES.get(b['type'])
    if fn is None:
        raise ValueError(f'unknown EQ band type "{b["type"]}" (known: {", ".join(sorted(EQ_TYPES))})')
    return fn(b)


def _band(b):
    """One preset EQ band, normalised (f/freq, gain, q)."""
    return {'type': b.get('type', 'peak'), 'f': float(b.get('f', b.get('freq', 1000.0))),
            'gain': float(b.get('gain', 0.0)), 'q': float(b.get('q', 1.0)), 'order': b.get('order')}


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


def _spatial_cfg(mx, space):
    """The mix preset's `spatial` section with the distance law of a project-owned space laid over it."""
    cfg = dict(mx.get('spatial') or {})
    dc = space.get('distance', {}) if _space_owned_hook(space) else {}
    for k_sp, k_mix in _DISTANCE_KEYS:
        if k_sp in dc:
            cfg[k_mix] = dc[k_sp]
    return cfg


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
