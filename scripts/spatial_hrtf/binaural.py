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

import compute
from scipy import signal

from . import data, decoder, io, room, sph

SR = 44100
ORDER = 5
SPEED_OF_SOUND = 343.0
_cache = {}
MAGLS_VERSION = 2      # bump when the way a MagLS set is built or stored changes: it is part of the disk-cache tag
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
    src = _dataset['path'] or os.path.join(data.HRIR_DIR, f'HRIRs_default_{SR}.mat')
    try:
        st = os.stat(src)
        key = (src, st.st_mtime_ns, st.st_size)      # a file replaced in place is a different set, in memory too
    except OSError:
        key = (src, None, None)
    if (order, key) not in _cache:
        tag = _magls_tag(src, order)
        path = os.path.join(os.path.dirname(data.HRIR_DIR), f'magls_o{order}_{SR}_{tag}.npy')
        if tag and os.path.exists(path):
            _cache[(order, key)] = np.load(path)
        else:
            _cache[(order, key)] = decoder.magls_bin(_load_hrirs(SR), order)
            if tag:
                np.save(path, _cache[(order, key)].astype(np.float32))
    return _cache[(order, key)]


def _magls_tag(src, order):
    """Disk-cache tag of a MagLS set: SHA-256 of the head file's bytes, of the decoder source that builds the set,
    and MAGLS_VERSION, so replacing the file in place or changing the decoder never reuses stale filters. '' when the
    file cannot be read (nothing is then cached on disk)."""
    h = hashlib.sha256()
    try:
        for path in (src, decoder.__file__):
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h.update(chunk)
            h.update(b'|')
    except OSError:
        return ''
    h.update(f'v{MAGLS_VERSION}|o{order}|sr{SR}'.encode('ascii'))
    return h.hexdigest()[:16]


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


def _sphere_mag(mu, rho, cos_t):
    """|H| of a rigid sphere: pressure at a surface point over the free-field pressure at the centre, for a point
    source at rho head radii and normalised frequencies mu = k a (Duda & Martens 1998, eq. 3):

        H = -(rho / mu) exp(-i mu rho) sum_m (2m + 1) P_m(cos t) h_m(mu rho) / h_m'(mu)

    Returns (len(cos_t), len(mu)). Terms past the point where the series has converged are dropped, because the
    Hankel functions there overflow before their ratio does."""
    from scipy.special import eval_legendre, spherical_jn, spherical_yn
    mu = np.asarray(mu, float)
    m = np.arange(0, int(1.3 * mu.max()) + 42)[:, None]     # past m ~ mu the terms fall like rho^-m
    use = m <= 1.3 * mu[None, :] + 40
    with np.errstate(all='ignore'):
        num = spherical_jn(m, mu[None, :] * rho) - 1j * spherical_yn(m, mu[None, :] * rho)
        den = spherical_jn(m, mu[None, :], derivative=True) - 1j * spherical_yn(m, mu[None, :], derivative=True)
        ratio = np.where(use, num / den, 0.0)
    ratio = np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0)
    leg = eval_legendre(m, np.asarray(cos_t, float)[None, :])            # (M, len(cos_t))
    return np.abs(np.einsum('mc,mf->cf', (2 * m + 1) * leg, ratio)) * rho / mu[None, :]


DVF_BLOCK = 2048
DVF_COS = np.linspace(-1.0, 1.0, 25)


def _dvf_table(a, ref_m, sr):
    """The distance variation function on a grid: near-field over reference-distance sphere response, per ear angle.
    (distances, table[distance, cos, bin]). Kan, Jin & van Schaik 2009: multiply a far-field HRTF by this ratio and
    it becomes the HRTF of the nearer source; the head's own shape cancels in the ratio."""
    key = ('dvf', round(a, 5), round(ref_m, 4), sr)
    if key not in _cache:
        bins = np.maximum(np.fft.rfftfreq(DVF_BLOCK, 1.0 / sr), 30.0)
        f = np.geomspace(30.0, sr / 2.0, 96)                # the ratio is smooth: solve on 96 points, read per bin
        mu = 2.0 * np.pi * f * a / SPEED_OF_SOUND
        dists = np.geomspace(0.2, ref_m, 10)
        far = _sphere_mag(mu, ref_m / a, DVF_COS)
        coarse = np.stack([_sphere_mag(mu, d / a, DVF_COS) / np.maximum(far, 1e-9) for d in dists])
        fine = np.empty(coarse.shape[:2] + (len(bins),))
        for i in range(coarse.shape[0]):
            for j in range(coarse.shape[1]):
                fine[i, j] = np.interp(np.log(bins), np.log(f), coarse[i, j])
        _cache[key] = (dists, fine)
    return _cache[key]


def dvf_gains(azimuth_deg, elevation_deg, distance_m, cfg, sr=SR):
    """(2, bins) magnitude for the left / right ear of one source position: 1.0 everywhere at `max_m` and beyond.
    The ears sit on the interaural axis; `strength` blends the cue in dB."""
    a = float(cfg.get('head_radius_m', 0.0875))
    ref = float(cfg.get('max_m', 1.0))
    dists, table = _dvf_table(a, ref, sr)
    d = float(np.clip(distance_m, dists[0], ref))
    c_r = float(np.cos(np.radians(elevation_deg)) * np.sin(np.radians(azimuth_deg)))
    out = []
    for c in (-c_r, c_r):                                  # left ear, right ear
        i = int(np.clip(np.searchsorted(dists, d) - 1, 0, len(dists) - 2))
        j = int(np.clip(np.searchsorted(DVF_COS, c) - 1, 0, len(DVF_COS) - 2))
        u = (np.log(d) - np.log(dists[i])) / (np.log(dists[i + 1]) - np.log(dists[i]))
        v = (c - DVF_COS[j]) / (DVF_COS[j + 1] - DVF_COS[j])
        db = 20.0 * np.log10(np.maximum(table[i:i + 2, j:j + 2], 1e-9))
        out.append((1 - u) * ((1 - v) * db[0, 0] + v * db[0, 1]) + u * ((1 - v) * db[1, 0] + v * db[1, 1]))
    return 10.0 ** (np.array(out) * float(np.clip(cfg.get('strength', 1.0), 0.0, 1.0)) / 20.0)


def stft_gain(y, gain_at, block=DVF_BLOCK, hop=DVF_BLOCK // 4):
    """A zero-phase filter whose magnitude changes over time: `gain_at(sample)` gives (bins,) or (channels, bins) for
    the frame centred on that sample. Root-Hann analysis and synthesis windows at 75 % overlap, so a filter that
    does not change is a plain zero-phase filter and one that does never switches."""
    y = np.asarray(y, float)
    flat = y.ndim == 1
    y2 = y[:, None] if flat else y
    n = len(y2)
    w = np.sqrt(signal.get_window('hann', block, fftbins=True))
    xp = np.concatenate([np.zeros((block, y2.shape[1])), y2, np.zeros((block, y2.shape[1]))])
    out = np.zeros_like(xp)
    wsum = np.zeros(len(xp))
    for i0 in range(0, len(xp) - block + 1, hop):
        g = np.atleast_2d(gain_at(int(np.clip(i0 + block // 2 - block, 0, max(0, n - 1)))))
        spec = np.fft.rfft(xp[i0:i0 + block] * w[:, None], axis=0) * g.T
        out[i0:i0 + block] += np.fft.irfft(spec, block, axis=0) * w[:, None]
        wsum[i0:i0 + block] += w * w
    out = (out / np.maximum(wsum, 1e-9)[:, None])[block:block + n]
    return out[:, 0] if flat else out


def apply_near_field(y, azimuth_deg, elevation_deg, distance_m, cfg, sr=SR):
    """The near-field level difference (and its low-frequency emphasis) on an already binaural signal."""
    if (cfg or {}).get('model', 'geometric') == 'dvf':
        if not cfg.get('enabled', True):
            return y
        az, el, dist = (np.atleast_1d(np.asarray(v, float)) for v in (azimuth_deg, elevation_deg, distance_m))
        if float(dist.min()) >= float(cfg.get('max_m', 1.0)):
            return y
        pick = lambda v, k: float(v[min(k, len(v) - 1)])
        return stft_gain(y, lambda k: dvf_gains(pick(az, k), pick(el, k), pick(dist, k), cfg, sr))
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
            out[:, e] = compute.conv(x, g @ dec[e])[:n]
        if near_field:
            out = apply_near_field(out, a0, e0, d0, near_field, sr)
        return out.astype(np.float32)

    f = np.linspace(0.0, 1.0, n)
    az_t, el_t, d_t = a0 + f * (a1 - a0), e0 + f * (e1 - e0), d0 + f * (d1 - d0)
    if tj.get('doppler', True) and n > 8:
        x = _doppler(x, d_t, sr)
    out = _stft_place(x, az_t, el_t, order, sr)
    out *= (1.0 / np.maximum(1.0, d_t))[:, None]
    out = _air_moving(out, d_t, temp_c, rh, sr)
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


def _stft_place(x, az_t, el_t, order=ORDER, sr=SR, block=1024, hop=256, chunk=128):
    """Time-varying binaural filter in the STFT domain: each frame takes the direction at that instant, so a crossing
    source gets its cue updated every `hop` samples (~6 ms) instead of at a gain-update rate.

    Each frame is Hann-windowed, filtered by a true linear convolution (both transforms are zero-padded to
    >= block + taps - 1, so the filter's tail does not wrap into the frame's start) and overlap-added; the sum is
    divided by the sum of the analysis windows, which makes a still source exactly x * h. The gains of all frame
    directions are evaluated together, `chunk` frames at a time."""
    dec = magls(order)
    taps = dec.shape[-1]
    nfft = 1 << int(np.ceil(np.log2(block + taps - 1)))
    n = len(x)
    pad = block
    xp = np.concatenate([np.zeros(pad), x, np.zeros(pad)])
    w = signal.get_window('hann', block, fftbins=True)
    out = np.zeros((len(xp) + nfft - block, 2))
    wsum = np.zeros(len(xp))
    starts = np.arange(0, len(xp) - block + 1, hop)
    pos = np.clip((starts + block / 2.0 - pad) / max(1, n - 1), 0.0, 1.0)
    k = (pos * (n - 1)).astype(int)
    az_t, el_t = np.asarray(az_t, float), np.asarray(el_t, float)
    for c0 in range(0, len(starts), chunk):
        sl = slice(c0, c0 + chunk)
        st, kk = starts[sl], k[sl]
        segs = xp[st[:, None] + np.arange(block)[None, :]] * w
        X = np.fft.rfft(segs, nfft, axis=1)
        g = gains(order, az_t[kk], el_t[kk])                                   # (F, (order+1)^2)
        for e in (0, 1):
            H = np.fft.rfft(g @ dec[e], nfft, axis=1)                          # (F, nfft/2+1)
            y = np.fft.irfft(X * H, nfft, axis=1)
            for i0, row in zip(st, y):
                out[i0:i0 + nfft, e] += row
        for i0 in st:
            wsum[i0:i0 + block] += w
    out = out[:len(xp)]
    out /= np.maximum(wsum, 1e-9)[:, None]
    return out[pad:pad + n]


def _air_moving(y, dist_t, temp_c, rh, sr):
    """Air loss for a source whose distance changes: ISO 9613-1 for the path beyond one metre at each instant.
    The filters of a grid of distances (about 1 m apart, spanning the move) are blended by the distance at each
    sample, so the high end dulls as the source recedes and returns as it nears; a still source is one exact filter."""
    import airabs
    extra = np.maximum(np.asarray(dist_t, float) - 1.0, 0.0)
    lo, hi = float(extra.min()), float(extra.max())
    if hi <= 0.0:
        return y
    if hi - lo < 1e-9:
        return airabs.apply(y, hi, temp_c=temp_c, rh=rh, sr=sr).astype(float)
    levels = np.linspace(lo, hi, int(min(64, np.ceil(hi - lo) + 1)) + 1)
    pos = np.interp(extra, levels, np.arange(len(levels)))
    j0 = np.minimum(np.floor(pos).astype(int), len(levels) - 2)
    frac = pos - j0
    out = np.zeros_like(np.asarray(y, float))
    for j, d in enumerate(levels):
        wj = np.where(j0 == j, 1.0 - frac, 0.0) + np.where(j0 == j - 1, frac, 0.0)
        if not wj.any():
            continue
        yj = airabs.apply(y, d, temp_c=temp_c, rh=rh, sr=sr).astype(float) if d > 0 else np.asarray(y, float)
        out += yj * (wj[:, None] if out.ndim == 2 else wj)
    return out


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
    return np.stack([compute.conv(s, g @ dec[0])[:len(x)],
                     compute.conv(s, g @ dec[1])[:len(x)]], axis=1)


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
            extra = max(0.0, float(t['distance_m']) - float(t.get('direct_m', dist)))   # the room's own (clamped) direct path
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
            out[:, e] += compute.conv(s, g @ dec[e])[:n]

    for tap in fixed_plan(az):
        add(*tap)
    return out.astype(np.float32)


def fixed_plan(az):
    """The four fixed reflections of a space preset without a geometry: (key, delay growth per metre, default
    cut-off, direction, level). Floor below, the far wall, the ceiling above, the rear wall."""
    side = -1.0 if az > 0 else 1.0
    rear_az = (1.0 if az >= 0 else -1.0) * (180.0 - abs(az))
    plan = [('ground', 0.10, 3200.0, (az, -25.0), 1.0)]
    if abs(az) < 5.0:
        plan += [('lateral', 0.15, 2400.0, (-90.0, 0.0), 0.707), ('lateral', 0.15, 2400.0, (90.0, 0.0), 0.707)]
    else:
        plan += [('lateral', 0.15, 2400.0, (side * 90.0, 0.0), 1.0)]
    return plan + [('ceiling', 0.12, 2800.0, (az, 60.0), 1.0), ('rear', 0.18, 2000.0, (rear_az, 0.0), 1.0)]


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
    cfg = room.late_cfg(refl)                  # "auto" values come from the room's own geometry
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
        tail = compute.conv(x, ir)[:n]
        g = gains(order, daz, del_)[0]
        for e in (0, 1):
            acc[:, e] += compute.conv(tail, g @ dec[e])[:n]
    acc /= max(1, len(dirs))
    dry = np.sqrt(np.mean(x ** 2) + 1e-12)
    got = np.sqrt(np.mean(acc ** 2) + 1e-12)
    acc *= (dry / got) * 10 ** (float(cfg.get('level_db', -18.0)) / 20.0)
    return acc.astype(np.float32)
