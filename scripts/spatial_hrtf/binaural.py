"""binaural.py - the layer the mixer calls: a mono stem placed at an angle, rendered for headphones with measured head data.

    from spatial_hrtf import binaural
    st = binaural.spatialize(mono, azimuth_deg=-60, elevation_deg=20, distance_m=3.0)       # (N, 2) float32
    st = binaural.spatialize(mono, 0, 0, 2.0, trajectory={'start_azimuth': -70, 'end_azimuth': 70})

Source -> Ambisonic harmonics (sph.sh_matrix) -> MagLS decoder built from the measured set (decoder.magls_bin) -> two ears.
Order 5 is the setting that gives a true time difference (order 3: 0.11 ms at 60 deg, order 5: 0.5 ms).
Our conventions, as in spatial.py: azimuth 0 = front, +90 = right; elevation +90 = above. spaudiopy counts azimuth
anticlockwise and the angle from straight up, hence the sign flip in gains().

Six things this layer owns, each switched by a preset key (nothing is decided here):

  * the head data (`set_dataset`): the bundled FABIAN set, or a listener's own .mat / .sofa set.
  * the near field (`near_field`): below one metre the ears are different distances from the source, so the level
    difference grows. A 1/r per ear about the same reference, plus a low-frequency emphasis, which is the part of the
    proximal cue that carries distance.
  * a moving source (`spatialize` with `trajectory`): Doppler by resampling, then a time-varying filter built in the
    STFT domain, so the direction changes every 256 samples and the filter never zippers.
  * early reflections (`reflections`): four fixed directions, or a room preset's shoebox geometry (room.py).
  * the late field (`late`): decorrelated tails from several directions. One tail in both ears is the in-head sound.
  * path physics: every tap obeys its own path (1/r about `ref_m` plus the air it crosses), not the direct sound's.
"""
import hashlib
import os

import numpy as np
from scipy import signal

from . import data, decoder, io, room, sph

SR = 44100
ORDER = 5
SPEED_OF_SOUND = 343.0
_cache = {}
_dataset = {'path': None, 'name': 'fabian'}


def available():
    """True when the head data is on disk (python -m spatial_hrtf.data fetches the bundled set)."""
    if _dataset['path']:
        return os.path.exists(_dataset['path'])
    return data.ready(SR)


def set_dataset(path=None, name=None):
    """Choose the measured head set. `path` is a listener's own .mat (hrir_l/hrir_r/azi/zen) or .sofa file, resolved
    against the project or the skill; None goes back to the bundled FABIAN set. Returns the name in use.

    A listener's own set is the single largest step towards externalisation: the cues that make a headphone mix sit
    outside the head are individual, and a general set fits nobody exactly. This function only selects the data; the
    decoder is rebuilt and cached per set.
    """
    _dataset['path'] = os.path.abspath(path) if path else None
    _dataset['name'] = name or (os.path.basename(path) if path else 'fabian')
    return _dataset['name']


def dataset_name():
    return _dataset['name']


def _load_hrirs(sr=SR):
    """The measured set at the render rate. A file at another rate is resampled, not rejected."""
    p = _dataset['path']
    if not p:
        return io.load_hrirs(sr)
    h = io.load_sofa_hrirs(p) if p.lower().endswith('.sofa') else io.load_hrirs(sr, p)
    if int(h.fs) == sr:
        return h
    from scipy.signal import resample_poly
    from math import gcd
    g = gcd(int(h.fs), int(sr))
    up, down = sr // g, int(h.fs) // g
    left = resample_poly(h.left, up, down, axis=1)
    right = resample_poly(h.right, up, down, axis=1)
    return type(h)(left, right, h.azi, h.zen, sr)


def magls(order=ORDER):
    """(2, (order+1)^2, 256) filters from harmonic signals to the left / right ear. Built once per head set (about 4 s),
    then kept on disk."""
    key = _dataset['path'] or 'fabian'
    if (order, key) not in _cache:
        tag = hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]
        path = os.path.join(os.path.dirname(data.HRIR_DIR), f'magls_o{order}_{SR}_{tag}.npy')
        if os.path.exists(path):
            _cache[(order, key)] = np.load(path)
        else:
            _cache[(order, key)] = decoder.magls_bin(_load_hrirs(SR), order)
            np.save(path, _cache[(order, key)].astype(np.float32))
    return _cache[(order, key)]


def gains(order, azimuth_deg, elevation_deg):
    """Harmonic gains of sources at our angles: (Q, (order+1)^2)."""
    return sph.sh_matrix(order, -np.radians(np.atleast_1d(azimuth_deg)), np.radians(90.0 - np.atleast_1d(elevation_deg)), 'real')


# ---------------------------------------------------------------------------------------------
# near field
# ---------------------------------------------------------------------------------------------

def near_field_gains(azimuth_deg, elevation_deg, distance_m, cfg, sr=SR):
    """Per-ear level of a point source below one metre: (N, 2) or (2,) multipliers, 1.0 where the cue is off.

    The source is a point at (r, az, el); the ears are +-head_radius apart, so the near ear is closer and gets more
    level and more low end. `cfg` (space preset `distance.near_field`): enabled, max_m, head_radius_m, strength
    (0..1 how much of the geometric difference to apply), lf_boost (extra low-frequency emphasis), lf_hz.
    """
    az = np.atleast_1d(np.asarray(azimuth_deg, float))
    el = np.atleast_1d(np.asarray(elevation_deg, float))
    dist = np.atleast_1d(np.asarray(distance_m, float))
    n = max(len(az), len(el), len(dist))
    az, el, dist = (np.broadcast_to(v, (n,)) for v in (az, el, dist))
    cfg = cfg or {}
    if not cfg.get('enabled', True):
        return None
    a = float(cfg.get('head_radius_m', 0.0875))
    strength = float(np.clip(cfg.get('strength', 1.0), 0.0, 1.0))
    max_m = float(cfg.get('max_m', 1.0))
    gmin, gmax = float(cfg.get('min_gain', 0.35)), float(cfg.get('max_gain', 3.0))
    th, ph = np.radians(az), np.radians(el)
    x = dist * np.cos(ph) * np.sin(th)          # right
    y = dist * np.cos(ph) * np.cos(th)          # front
    z = dist * np.sin(ph)
    d_r = np.sqrt((x - a) ** 2 + y ** 2 + z ** 2)
    d_l = np.sqrt((x + a) ** 2 + y ** 2 + z ** 2)
    out = np.ones((n, 2))
    near = dist < max_m
    if not np.any(near):
        return out
    g_r = np.clip(dist / np.maximum(d_r, 1e-6), gmin, gmax)
    g_l = np.clip(dist / np.maximum(d_l, 1e-6), gmin, gmax)
    out[near, 0] = 1.0 + (g_l[near] - 1.0) * strength          # left ear
    out[near, 1] = 1.0 + (g_r[near] - 1.0) * strength          # right ear
    return out


def apply_near_field(y, azimuth_deg, elevation_deg, distance_m, cfg, sr=SR):
    """The near-field level difference (and its low-frequency emphasis) on an already binaural signal."""
    g = near_field_gains(azimuth_deg, elevation_deg, distance_m, cfg, sr)
    if g is None:
        return y
    if g.ndim == 1:
        g = g[None, :]
    y = np.asarray(y, float)
    if g.shape[0] == 1:
        y = y * g[0]
    else:
        y = y * g[:len(y)]
    lf = float((cfg or {}).get('lf_boost', 0.0))
    if lf > 0:
        hz = float((cfg or {}).get('lf_hz', 700.0))
        sos = signal.butter(2, min(sr * 0.45, hz), 'low', fs=sr, output='sos')
        low = signal.sosfilt(sos, y, axis=0)
        g2 = g[0] if g.shape[0] == 1 else g[:len(y)]
        y = y + low * (g2 - 1.0) * lf
    return y


# ---------------------------------------------------------------------------------------------
# fixed source
# ---------------------------------------------------------------------------------------------

def _air(x, dist, temp_c, rh, sr):
    if float(np.max(dist)) > 1.0:
        import airabs
        x = airabs.apply(x, float(np.max(dist)) - 1.0, temp_c=temp_c, rh=rh, sr=sr).astype(float)
    return x


def spatialize(audio, azimuth_deg=0.0, elevation_deg=0.0, distance_m=1.5, sr=SR, order=ORDER, trajectory=None,
               temp_c=20.0, rh=50.0, near_field=None):
    """Mono (stereo is folded to mono) -> (N, 2) float32 binaural, with 1/r level and ISO 9613-1 air loss beyond 1 m.
    trajectory: start_/end_ azimuth, elevation, distance move the source over the signal (missing key = fixed value);
    `doppler` (default true) resamples for the radial velocity. `near_field` is the space preset's
    `distance.near_field` block; without it there is no near-field cue below one metre."""
    if sr != SR:
        raise ValueError(f'the measured set is {SR} Hz, got {sr}')
    x = np.asarray(audio, float)
    if x.ndim == 2:
        x = x.mean(axis=1)
    n = len(x)
    tj = trajectory or {}
    a0, a1 = float(tj.get('start_azimuth', azimuth_deg)), float(tj.get('end_azimuth', azimuth_deg))
    e0, e1 = float(tj.get('start_elevation', elevation_deg)), float(tj.get('end_elevation', elevation_deg))
    d0, d1 = (max(0.05, float(tj.get(k, distance_m))) for k in ('start_distance', 'end_distance'))

    if not tj:                                            # fixed source: the harmonics collapse to one filter per ear
        dec = magls(order)
        g = gains(order, a0, e0)[0] / max(d0, 1.0)
        x = _air(x, d0, temp_c, rh, sr)
        out = np.zeros((n, 2))
        for e in (0, 1):
            out[:, e] = signal.fftconvolve(x, g @ dec[e])[:n]
        if near_field:
            out = apply_near_field(out, a0, e0, d0, near_field, sr)
        return out.astype(np.float32)

    f = np.linspace(0.0, 1.0, n)
    az_t, el_t, d_t = a0 + f * (a1 - a0), e0 + f * (e1 - e0), d0 + f * (d1 - d0)
    if tj.get('doppler', True) and n > 8:
        x = _doppler(x, d_t, sr)
    out = _stft_place(x, az_t, el_t, order, sr)
    out *= (1.0 / np.maximum(1.0, d_t))[:, None]
    out = _air(out, float(np.max(d_t)), temp_c, rh, sr)
    if near_field:
        out = apply_near_field(out, az_t, el_t, d_t, near_field, sr)
    return out.astype(np.float32)


def _doppler(x, dist_t, sr, c=SPEED_OF_SOUND):
    """Radial motion as a continuous delay: the path length changes while the sound travels, which is the pitch shift.
    Causal (the delay is measured from its own minimum), so the first sample is never pulled from before the start."""
    from scipy.interpolate import CubicSpline
    n = len(x)
    delay = (dist_t - dist_t.min()) / c * sr
    idx = np.clip(np.arange(n) - delay, 0, n - 1)
    return CubicSpline(np.arange(n), x)(idx).astype(float)


def _stft_place(x, az_t, el_t, order=ORDER, sr=SR, block=1024, hop=256):
    """Time-varying binaural filter in the STFT domain: each frame takes the direction at that instant, so a crossing
    source gets its cue updated every `hop` samples (~6 ms) instead of at a gain-update rate. OLA for the periodic Hann
    window with a 4x overlap is exact for a constant filter, so a still source is unaffected."""
    dec = magls(order)
    n = len(x)
    pad = block
    xp = np.concatenate([np.zeros(pad), x, np.zeros(pad)])
    w = signal.get_window('hann', block, fftbins=True)
    out = np.zeros((len(xp), 2))
    wsum = np.zeros(len(xp))
    pos = np.clip((np.arange(0, len(xp) - block + 1, hop) + block / 2.0 - pad) / max(1, n - 1), 0.0, 1.0)
    k = (pos * (n - 1)).astype(int)
    for i0, kk in zip(range(0, len(xp) - block + 1, hop), k):
        seg = xp[i0:i0 + block] * w
        X = np.fft.rfft(seg)
        g = gains(order, az_t[kk], el_t[kk])[0]
        for e in (0, 1):
            H = np.fft.rfft(g @ dec[e], block)
            out[i0:i0 + block, e] += np.fft.irfft(X * H, block) * w
        wsum[i0:i0 + block] += w * w
    out /= np.maximum(wsum, 1e-9)[:, None]
    return out[pad:pad + n]


def spatialize_pair(audio, azimuth_deg, elevation_deg, distance_m, half_width_deg, **kw):
    """Stereo stem as two sources at azimuth -/+ half_width (a pad keeps its width instead of folding to one point).
    Mono input or half_width 0 falls back to spatialize().

    0.707 is the energy-preserving constant for two sources, so the pair carries the stereo stem's own energy. It sits
    ~1 dB under a centred mono source because the filters at +-40 deg are off-axis; that is the head, not a level law.
    The widths are the mix preset's `immersive.pair`, not a number in this file."""
    x = np.asarray(audio, float)
    if x.ndim == 1 or x.shape[1] == 1 or half_width_deg <= 0:
        return spatialize(x if x.ndim == 1 else x.mean(axis=1), azimuth_deg, elevation_deg, distance_m, **kw)
    a = float(half_width_deg)
    return (0.707 * (spatialize(x[:, 0], azimuth_deg - a, elevation_deg, distance_m, **kw)
                     + spatialize(x[:, 1], azimuth_deg + a, elevation_deg, distance_m, **kw))).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# early reflections
# ---------------------------------------------------------------------------------------------

def _place_tap(x, delay_ms, coeffs, dec, order, direction, sr):
    """One reflection: delayed, its wall's absorption applied, then arriving through the head filters from its own
    direction. A directionless copy gives no height or rear cue and sounds like a short delay."""
    d = int(round(float(delay_ms) / 1000.0 * sr))
    if d < 0 or d >= len(x):
        return None
    s = np.zeros(len(x))
    s[d:] = x[:len(x) - d]
    if coeffs is not None:
        fir = room.absorption_fir(coeffs, sr=sr)
        s = signal.lfilter(fir, 1.0, s)
    g = gains(order, direction[0], direction[1])[0]
    return np.stack([signal.fftconvolve(s, g @ dec[0])[:len(x)],
                     signal.fftconvolve(s, g @ dec[1])[:len(x)]], axis=1)


def reflections(audio, azimuth_deg, distance_m, refl, sr=SR, order=ORDER, path_physics=True, ref_m=1.0,
                temp_c=20.0, rh=50.0, elevation_deg=0.0):
    """Early reflections of a space preset, each arriving from its own direction through the same measured filters.

    Two descriptions, both in the preset:
      * `geometry` (room.render.taps): a shoebox with six surfaces, viewer and materials. Delays are real path
        lengths and every surface filters the tap with its own octave absorption.
      * the older four keys (ground/lateral/ceiling/rear gain and delay), which stay for pieces mixed with them.

    `path_physics` makes each tap obey its own path: 1/r about `ref_m` (the direct route's reference distance) over the
    direct path plus the extra distance the bounce adds, and the air that extra crosses. Without it the taps kept full
    level while the direct sound fell, so the DRR inverted (+4 dB measured at 6 m). The space preset owns the switch.
    """
    x = np.asarray(audio, float)
    if x.ndim == 2:
        x = x.mean(axis=1)
    n, dist, az = len(x), max(0.2, float(distance_m)), float(azimuth_deg)
    dec = magls(order)
    out = np.zeros((n, 2))
    ref = float(ref_m)

    taps = []
    geom = refl.get('geometry') if isinstance(refl, dict) else None
    if geom:
        taps = room.taps(geom, az, elevation_deg, dist, sr=sr)

    if taps:
        for t in taps:
            extra = max(0.0, float(t['distance_m']) - dist)
            level = (ref / (dist + extra)) if path_physics else 1.0
            y = _place_tap(x * level, t['delay_ms'], t['coeffs'], dec, order,
                           (t['azimuth'], t['elevation']), sr)
            if y is None:
                continue
            if path_physics and extra > 0:
                import airabs
                y = airabs.apply(y, extra, temp_c=temp_c, rh=rh, sr=sr)
            out += y
        return out.astype(np.float32)

    side = -1.0 if az > 0 else 1.0
    rear_az = (1.0 if az >= 0 else -1.0) * (180.0 - abs(az))

    def add(key, k, cutoff, direction, level=1.0):
        gain = float(refl.get(key + '_gain', 0.0)) * level
        delay_s = float(refl.get(key + '_delay_ms', 0.0)) / 1000.0
        d = int(delay_s * sr * (1.0 + k * dist))
        if gain <= 0.0 or not 0 < d < n:
            return
        s = np.zeros(n)
        s[d:] = x[:n - d] * gain
        if path_physics:
            extra = SPEED_OF_SOUND * d / sr
            s = (s * (float(ref) / max(float(dist) + extra, 1e-6))).astype(np.float64)
            import airabs
            s = airabs.apply(s, extra, temp_c=temp_c, rh=rh, sr=sr)
        s = signal.sosfilt(signal.butter(2, min(sr * 0.45, float(refl.get(key + '_cutoff_hz', cutoff))), 'low', fs=sr, output='sos'), s)
        g = gains(order, direction[0], direction[1])[0]
        for e in (0, 1):
            out[:, e] += signal.fftconvolve(s, g @ dec[e])[:n]

    add('ground', 0.10, 3200.0, (az, -25.0))
    if abs(az) < 5.0:
        add('lateral', 0.15, 2400.0, (-90.0, 0.0), 0.707)
        add('lateral', 0.15, 2400.0, (90.0, 0.0), 0.707)
    else:
        add('lateral', 0.15, 2400.0, (side * 90.0, 0.0))
    add('ceiling', 0.12, 2800.0, (az, 60.0))
    add('rear', 0.18, 2000.0, (rear_az, 0.0))
    return out.astype(np.float32)


# ---------------------------------------------------------------------------------------------
# late field
# ---------------------------------------------------------------------------------------------

def late(audio, azimuth_deg, distance_m, refl, sr=SR, order=ORDER, ref_m=1.0):
    """The directional late field: `late.count` decorrelated tails, each arriving from its own direction, all sharing
    the preset's RT60 and high-frequency damping. Returns (N, 2) or None when the preset does not ask for it.

    Level is `late.level_db` relative to the dry signal the mixer handed in; the preset says how loud the room is.
    A single tail in both ears is the classic in-head failure: it is perfectly correlated, so it has no width and the
    source stays inside the head. Decorrelated tails from spread directions are what give envelopment.
    """
    cfg = (refl or {}).get('late') if isinstance(refl, dict) else None
    if not cfg or not cfg.get('enabled', False):
        return None
    x = np.asarray(audio, float)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if len(x) < 2048:
        return None
    dec = magls(order)
    n = len(x)
    dirs = room.directions(dict(cfg, bias_azimuth_deg=float(cfg.get('bias_azimuth_deg', azimuth_deg))))
    acc = np.zeros((n, 2))
    for i, (daz, del_) in enumerate(dirs):
        ir = room.late_ir(dict(cfg, seed=int(cfg.get('seed', 7)) + i), sr)
        tail = signal.fftconvolve(x, ir)[:n]
        g = gains(order, daz, del_)[0]
        for e in (0, 1):
            acc[:, e] += signal.fftconvolve(tail, g @ dec[e])[:n]
    acc /= max(1, len(dirs))
    dry = np.sqrt(np.mean(x ** 2) + 1e-12)
    got = np.sqrt(np.mean(acc ** 2) + 1e-12)
    acc *= (dry / got) * 10 ** (float(cfg.get('level_db', -18.0)) / 20.0)
    return acc.astype(np.float32)
