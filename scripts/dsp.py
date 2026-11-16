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
"""dsp.py - NumPy/SciPy kernels the mixer needs and Pedalboard does not provide.

Pedalboard 0.9.26 gives a compressor with threshold/ratio/attack/release and nothing else: no knee, no
peak-vs-RMS detector, no sidechain input, no sidechain filtering, no lookahead, no stereo-link control,
no band splitter and no dynamic EQ. Those are engineered here, on top of the same envelope follower the
mixer already used, so a preset can ask for them without leaving the engine.

Every kernel takes and returns float32 arrays shaped (samples, channels), the layout the rest of the skill
uses. Nothing here reads a preset or a file: values arrive as arguments, decisions stay in the mixer.
"""
import numpy as np
from scipy import signal

EPS = 1e-12
CONTROL_RATE = 400.0          # Hz: the envelope is followed on a coarse grid, then interpolated (as before)


# ---------------------------------------------------------------------------------------------
# array + level helpers
# ---------------------------------------------------------------------------------------------

def to_2d(x):
    """(samples, channels) float32. A 1-D array becomes one channel; nothing is duplicated."""
    x = np.asarray(x, dtype=np.float32)
    return x[:, None] if x.ndim == 1 else x


def rms(x):
    return float(np.sqrt(np.mean(np.square(np.asarray(x, dtype=np.float64))) + EPS))


def rms_db(x):
    return 20.0 * np.log10(rms(x) + EPS)


def peak_db(x):
    return 20.0 * np.log10(float(np.abs(np.asarray(x)).max()) + EPS)


def crest_db(x):
    """Peak over RMS, dB. A sine is 3 dB, a snare hit 15-20 dB, a crushed bus 4-6 dB."""
    return peak_db(x) - rms_db(x)


def correlation(x):
    """Inter-channel correlation of a stereo signal, -1..1 (1.0 when there is nothing to compare)."""
    x = to_2d(x)
    if x.shape[1] < 2:
        return 1.0
    l, r = x[:, 0].astype(np.float64), x[:, 1].astype(np.float64)
    if l.std() < 1e-9 or r.std() < 1e-9:
        return 1.0
    v = float(np.corrcoef(l, r)[0, 1])
    return v if np.isfinite(v) else 1.0


def side_mid_db(x):
    """Side energy relative to mid energy in dB. -inf = pure mono, 0 dB = as much side as mid."""
    x = to_2d(x).astype(np.float64)
    if x.shape[1] < 2:
        return -120.0
    m = (x[:, 0] + x[:, 1]) / 2.0
    s = (x[:, 0] - x[:, 1]) / 2.0
    return float(20 * np.log10((np.sqrt(np.mean(s ** 2)) + EPS) / (np.sqrt(np.mean(m ** 2)) + EPS)))


def mono_fold_db(x):
    """How much loudness a mono fold-down costs, dB (0 = mono-compatible, negative = cancels)."""
    x = to_2d(x).astype(np.float64)
    if x.shape[1] < 2:
        return 0.0
    stereo = rms_db(x)
    mono = rms_db(x.mean(axis=1))
    return float(mono - stereo)


def band_power(x, sr, lo, hi, nperseg=4096):
    """Total power in [lo, hi) Hz, from a Welch PSD of the mono sum."""
    x = to_2d(x)
    mono = x.mean(axis=1) if x.shape[1] > 1 else x[:, 0]
    n = min(int(nperseg), max(256, len(mono)))
    f, p = signal.welch(mono.astype(np.float64), fs=sr, nperseg=n)
    m = (f >= lo) & (f < hi)
    return float(np.sum(p[m]))


def band_db(x, sr, lo, hi):
    return 10.0 * np.log10(band_power(x, sr, lo, hi) + EPS)


def band_powers(x, sr, bands, nperseg=4096):
    """{tag: power_db} for several (lo, hi, tag) bands from ONE Welch PSD of the mono sum.

    band_db() re-runs the whole spectrogram on every call. Measuring 24 stems in 6 bands, plus every
    stem pair in the masking check, came to ~1,800 full PSDs over the same audio (2.2 s each on a 3-minute
    stem): that, not the mixing, was the multi-minute stall after the draft master. A caller that wants
    several bands of one signal asks once. Same nperseg and same summation as band_db, so the numbers are
    identical to calling band_db per band.
    """
    x = to_2d(x)
    mono = x.mean(axis=1) if x.shape[1] > 1 else x[:, 0]
    n = min(int(nperseg), max(256, len(mono)))
    f, p = signal.welch(mono.astype(np.float64), fs=sr, nperseg=n)
    out = {}
    for lo, hi, tag in bands:
        m = (f >= lo) & (f < hi)
        out[tag] = 10.0 * np.log10(float(np.sum(p[m])) + EPS)
    return out


_METERS = {}


def meter(sr=44100):
    """One K-weighted loudness meter per sample rate.

    Building a `pyloudnorm.Meter` re-derives the K-weighting filters, so constructing one per
    loudness call made every gain-staging block and every mastering pass pay for it again.
    """
    key = int(sr)
    if key not in _METERS:
        import pyloudnorm as pyln
        _METERS[key] = pyln.Meter(key)
    return _METERS[key]


def active_fraction(x, sr, block_s=0.4, active_db=-55.0):
    """Share of the stem's 0.4 s windows that are actually sounding."""
    x = to_2d(x)
    n = int(block_s * sr)
    if n < 1 or len(x) < n:
        return 1.0
    k = len(x) // n
    blocks = x[:k * n].astype(np.float64).reshape(k, n, -1)
    rms_b = np.sqrt((blocks ** 2).mean(axis=(1, 2)) + EPS)
    return float(np.mean(20 * np.log10(rms_b) > active_db))


def true_peak_db(x, sr=44100, over=4):
    """Oversampled true peak, dBTP. The whole buffer is resampled, as before: no short-buffer surprises."""
    y = to_2d(x)
    if len(y) == 0:
        return -120.0
    z = signal.resample_poly(y.astype(np.float64), over, 1, axis=0)
    return float(20 * np.log10(np.abs(z).max() + EPS))


# ---------------------------------------------------------------------------------------------
# envelope + compressor
# ---------------------------------------------------------------------------------------------

def envelope(x, sr=44100, attack_ms=8.0, release_ms=150.0, rate=CONTROL_RATE, hold_tail=False):
    """Peak envelope (max across channels), followed at `rate` Hz and interpolated to sample rate.

    hold_tail=True keeps the last real control value instead of letting the padded final block fall to
    zero: with lookahead applied on top, a zeroed tail released the duck instantly at the end of a file.
    """
    mono = np.abs(to_2d(x)).max(1)
    blk = max(1, int(sr // rate))
    n = len(mono) // blk + 1
    m = np.pad(mono, (0, n * blk - len(mono))).reshape(n, blk).max(1)
    a = np.exp(-1.0 / (attack_ms / 1000.0 * rate))
    r = np.exp(-1.0 / (release_ms / 1000.0 * rate))
    e = np.zeros(n)
    for i in range(1, n):
        c = a if m[i] > e[i - 1] else r
        e[i] = c * e[i - 1] + (1 - c) * m[i]
    if hold_tail and n > 1:
        e[-1] = e[-2]
    return np.interp(np.arange(len(mono)), np.arange(n) * blk + blk / 2, e)


def _follow_rows(c, rate, attack_ms, release_ms):
    """Attack/release follower over a (blocks, channels) control array."""
    a = np.exp(-1.0 / max(1e-6, attack_ms / 1000.0 * rate))
    r = np.exp(-1.0 / max(1e-6, release_ms / 1000.0 * rate))
    out = np.zeros_like(c, dtype=np.float64)
    prev = np.zeros(c.shape[1], dtype=np.float64)
    for i in range(c.shape[0]):
        cur = c[i]
        coef = np.where(cur > prev, a, r)
        prev = coef * prev + (1.0 - coef) * cur
        out[i] = prev
    return out


def static_gain_reduction_db(level_db, threshold_db, ratio, knee_db=0.0):
    """How much a signal at `level_db` is turned down. Quadratic soft knee, exact at both knee edges."""
    over = np.asarray(level_db, dtype=np.float64) - float(threshold_db)
    slope = 1.0 - 1.0 / max(float(ratio), 1.0)
    if knee_db <= 0:
        return np.maximum(over, 0.0) * slope
    half = float(knee_db) / 2.0
    return np.where(over <= -half, 0.0,
                    np.where(over >= half, over * slope, slope * (over + half) ** 2 / (2.0 * knee_db)))


def compressor(x, sr=44100, threshold_db=-18.0, ratio=2.0, attack_ms=10.0, release_ms=100.0,
               knee_db=0.0, detector='peak', stereo_link=True, lookahead_ms=0.0, makeup_db=0.0,
               sidechain=None, sidechain_hp_hz=0.0, sidechain_lp_hz=0.0, mix=1.0, rate=CONTROL_RATE):
    """Feed-forward compressor with optional soft knee, RMS detector, filtered sidechain and lookahead.

    `sidechain` is an array (a kick, a voice) used as the detector input while `x` is what gets turned
    down. `mix` < 1 is parallel compression. Lookahead moves the gain curve earlier by that many ms, so
    the attack lands on the transient instead of after it.
    """
    y = to_2d(x).astype(np.float32)
    if len(y) == 0:
        return y
    sc = y if sidechain is None else to_2d(sidechain).astype(np.float32)
    if len(sc) < len(y):
        sc = np.pad(sc, ((0, len(y) - len(sc)), (0, 0)))
    sc = sc[:len(y)]
    if sidechain_hp_hz or sidechain_lp_hz:
        lo = max(20.0, float(sidechain_hp_hz)) if sidechain_hp_hz else 20.0
        hi = min(sr / 2.0 - 100.0, float(sidechain_lp_hz)) if sidechain_lp_hz else sr / 2.0 - 100.0
        if hi > lo:
            sc = signal.sosfilt(signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos'),
                                sc, axis=0).astype(np.float32)
    blk = max(1, int(sr // rate))
    n = len(sc) // blk + 1
    blocks = np.pad(sc, ((0, n * blk - len(sc)), (0, 0))).reshape(n, blk, sc.shape[1])
    if detector == 'rms':
        c = np.sqrt(np.mean(blocks.astype(np.float64) ** 2, axis=1))
    else:
        c = np.abs(blocks).max(axis=1)
    if stereo_link and c.shape[1] > 1:
        c = c.max(axis=1, keepdims=True)
    e = _follow_rows(c, rate, attack_ms, release_ms)
    gr = static_gain_reduction_db(20.0 * np.log10(e + EPS), threshold_db, ratio, knee_db)
    gain = 10.0 ** (-gr / 20.0)
    centres = np.arange(n) * blk + blk / 2.0
    t = np.arange(len(y))
    if lookahead_ms > 0:
        t = t + int(lookahead_ms / 1000.0 * sr)
    if gain.shape[1] == 1:
        g = np.interp(t, centres, gain[:, 0]).astype(np.float32)[:, None]
    else:
        g = np.stack([np.interp(t, centres, gain[:, ch]) for ch in range(gain.shape[1])], 1).astype(np.float32)
    wet = y * g
    out = wet if mix >= 1.0 else y * (1.0 - mix) + wet * mix
    return (out * 10.0 ** (float(makeup_db) / 20.0)).astype(np.float32)


def multiband_compressor(x, sr=44100, bands=None, **kw):
    """Split into bands, compress each, sum. `bands` is a list of dicts:

        {"lo": 20, "hi": 120, "threshold_db": -20, "ratio": 2.5, "attack_ms": 20,
         "release_ms": 150, "knee_db": 6, "gain_db": 0}

    The split is a 2nd-order band-pass per band. The sum is not sample-exact in phase (a Linkwitz-Riley
    network would be); a preset that needs that should keep `dynamics.multiband` off.
    """
    y = to_2d(x).astype(np.float32)
    if not bands:
        return y
    out = np.zeros_like(y)
    for b in bands:
        lo = max(20.0, float(b.get('lo', 20.0)))
        hi = min(sr / 2.0 - 50.0, float(b.get('hi', sr / 2.0 - 50.0)))
        if hi <= lo:
            continue
        sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
        part = signal.sosfilt(sos, y, axis=0).astype(np.float32)
        part = compressor(part, sr, threshold_db=b.get('threshold_db', -20.0), ratio=b.get('ratio', 2.0),
                          attack_ms=b.get('attack_ms', 15.0), release_ms=b.get('release_ms', 150.0),
                          knee_db=b.get('knee_db', 0.0), detector=b.get('detector', 'peak'),
                          stereo_link=True, **{k: v for k, v in kw.items() if k in
                                               ('lookahead_ms', 'rate', 'sidechain')})
        out += part * 10.0 ** (float(b.get('gain_db', 0.0)) / 20.0)
    return out


def dynamic_eq(x, sr=44100, f=1000.0, q=1.0, threshold_db=-24.0, ratio=2.0, attack_ms=5.0,
               release_ms=80.0, knee_db=3.0, gain_db=0.0, sidechain=None):
    """Compress one band only. The band is taken out, compressed, and put back, so a loud 3 kHz
    only ducks 3 kHz. A static `gain_db` moves the band as well."""
    y = to_2d(x).astype(np.float32)
    lo = max(20.0, f / (1.0 + 1.0 / (2.0 * max(q, 0.1))))
    hi = min(sr / 2.0 - 50.0, f * (1.0 + 1.0 / (2.0 * max(q, 0.1))))
    if hi <= lo:
        return y
    sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
    band = signal.sosfilt(sos, y, axis=0).astype(np.float32)
    rest = y - band
    band = compressor(band, sr, threshold_db=threshold_db, ratio=ratio, attack_ms=attack_ms,
                      release_ms=release_ms, knee_db=knee_db, sidechain=sidechain, stereo_link=True)
    return (rest + band * 10.0 ** (float(gain_db) / 20.0)).astype(np.float32)


def transient_shaper(x, sr=44100, attack=0.0, sustain=0.0, fast_ms=3.0, slow_ms=60.0):
    """attack/sustain in dB. Positive attack sharpens the front of a note, negative softens it;
    sustain is the body after the front. 0/0 returns the input untouched."""
    if attack == 0.0 and sustain == 0.0:
        return to_2d(x).astype(np.float32)
    y = to_2d(x).astype(np.float32)
    fast = envelope(y, sr, fast_ms, fast_ms * 2.0)
    slow = envelope(y, sr, slow_ms, slow_ms * 2.0)
    delta = np.log10((fast + EPS) / (slow + EPS))                # >0 on a transient, <=0 on a sustain
    body = np.clip(-delta, 0.0, 1.0)
    curve = 10.0 ** ((attack * np.clip(delta, 0.0, 2.0) + sustain * body) / 20.0)
    return (y * curve[:, None]).astype(np.float32)


def fade_out_at(x, sr=44100, times=(), ms=4.0):
    """A short raised-cosine release ending at each note-off, so a damped hit ends instead of being cut.

    A drum note-off lands 120 ms into a sample that is still ringing, and a hard cut on a non-zero sample is a
    click (measured: an isolated impulse at the off of roughly one hit in four on a GM djembe). Four milliseconds
    is faster than any audible damping, so the hit is unchanged but the step is gone.
    """
    y = to_2d(x).astype(np.float32)
    n = int(round(float(ms) * sr / 1000.0))
    if n < 2 or len(y) == 0 or not len(times):
        return y
    ramp = (0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, n))).astype(np.float32)[:, None]
    for t in times:
        i1 = int(round(float(t) * sr))
        i0 = max(0, i1 - n)
        if i1 <= 0 or i0 >= len(y):
            continue
        seg = y[i0:i1]
        y[i0:i1] = (seg * ramp[n - seg.shape[0]:]).astype(np.float32)
    return y


def declick(x, sr=44100, mad_z=8.0, floor_frac=0.02, cluster_ms=1.5, repair_ms=0.8):
    """Repair isolated single-sample discontinuities left in a sampled patch.

    A bank's edited sample can carry a step that no playing produced: measured on one SoundFont djembe, an isolated
    impulse 2-43 ms into the hit, on about a hit in four, and on a shaker on nearly a third of them. The step is a
    defect, not a transient, so it is removed rather than mixed away: a short linear bridge over the step. Only an
    isolated jump is bridged -- a dense noise burst (a shaker's attack) and a steep monotone attack are left alone,
    which is the same distinction the stem gate draws.
    """
    y = to_2d(x).astype(np.float32)
    if len(y) < 64:
        return y
    peak = float(np.max(np.abs(y))) or 1.0
    from scipy.signal import butter, sosfiltfilt
    sos = butter(4, min(6000.0, sr * 0.45), 'high', fs=sr, output='sos')
    h = sosfiltfilt(sos, y.astype(np.float64), axis=0).mean(axis=1)
    r = np.diff(h)
    med = float(np.median(r))
    mad = float(np.median(np.abs(r - med))) * 1.4826 + 1e-12
    cand = np.flatnonzero((np.abs(r - med) > mad_z * mad) & (np.abs(r) > floor_frac * peak))
    if cand.size == 0:
        return y
    groups, cur = [], [int(cand[0])]
    for c in cand[1:]:
        if (int(c) - cur[-1]) / sr * 1000.0 <= cluster_ms:
            cur.append(int(c))
        else:
            groups.append(cur)
            cur = [int(c)]
    groups.append(cur)
    n_rep = max(2, int(round(repair_ms * sr / 1000.0)))
    fixed = 0
    for g in groups:
        if (g[-1] - g[0]) / sr * 1000.0 > cluster_ms:
            continue                                   # a dense burst: noise, not a step
        k = int(g[int(np.argmax(np.abs(r[g])))])
        a, b = k - n_rep, k + n_rep
        if a < 1 or b >= len(y) - 1:
            continue
        # the jump must be isolated: the local slope either side has to be far smaller than the step itself
        local = float(np.median(np.abs(r[a:b]))) + 1e-12
        if abs(float(r[k])) < 4.0 * local:
            continue
        left, right = y[a - 1], y[b]
        w = np.linspace(0.0, 1.0, b - a + 1, dtype=np.float32)[:, None]
        y[a:b + 1] = (left[None, :] * (1.0 - w) + right[None, :] * w).astype(np.float32)
        fixed += 1
    return y if fixed == 0 else y.astype(np.float32)


def repair_clicks(x, sr=44100, mad_z=8.0, floor_frac=0.02, cluster_ms=1.5, isolate_ms=10.0,   # floor_frac is FS
                  second_ratio=0.5, smooth_ms=0.35, half_ms=0.8, _passes=0):
    """Remove the isolated sample steps an edited bank sample carries.

    Measured on this project's GeneralUser bank: a djembe, a bell and a shaker all carry single-sample jumps inside
    the hit (2-43 ms in, on a quarter to a third of the hits) that no playing produced. A step is not a transient, so
    it is repaired rather than mixed away: the samples around it are smoothed and blended back with a raised-cosine
    window, which removes the jump and leaves the surrounding waveform untouched.

    Only an isolated jump is repaired. A dense cluster is a noise burst (a shaker's attack), and a monotone rise out
    of silence is an attack -- both are the instrument, not a defect, and both are left alone.
    """
    y = to_2d(x).astype(np.float32)
    if len(y) < 64:
        return y
    from scipy.ndimage import uniform_filter1d
    from scipy.signal import butter, sosfiltfilt
    mono = y.astype(np.float64).mean(axis=1)
    sos = butter(4, min(6000.0, sr * 0.45), 'high', fs=sr, output='sos')
    h = sosfiltfilt(sos, mono)
    r = np.diff(h)
    med = float(np.median(r))
    mad = float(np.median(np.abs(r - med))) * 1.4826 + 1e-12
    # The gate's own candidate rule, reproduced exactly: one-sided z (a click is a positive step) and an absolute
    # full-scale floor. Any wider net (two-sided, level-relative) merges the isolated jumps into "dense bursts" and
    # then skips exactly the events that need repairing - measured: 0 repaired of 30 on a bell stem.
    cand = np.flatnonzero(((r - med) / mad > mad_z) & (np.abs(r) > floor_frac))
    if cand.size == 0:
        return y
    groups, cur = [], [int(cand[0])]
    for c in cand[1:]:
        if (int(c) - cur[-1]) / sr * 1000.0 <= cluster_ms:
            cur.append(int(c))
        else:
            groups.append(cur)
            cur = [int(c)]
    groups.append(cur)
    ev = []
    for g in groups:
        if (g[-1] - g[0]) / sr * 1000.0 > cluster_ms:
            continue                                   # a dense burst: noise, not a step
        k = int(g[int(np.argmax(np.abs(r[g])))])
        ev.append((k, float(abs(r[k]))))
    iso = isolate_ms * sr / 1000.0
    look = max(4, int(0.002 * sr))
    try:
        from gate_checks import _is_attack             # the gate's own test: repair must agree with measurement
    except Exception:
        _is_attack = None
    kept = []
    for i, (k, amp) in enumerate(ev):
        if any(j != i and abs(k2 - k) <= iso and a2 >= second_ratio * amp for j, (k2, a2) in enumerate(ev)):
            continue                                   # paired with a rival: a layered hit, not a step
        if _is_attack is not None:
            if _is_attack(mono, k):
                continue                               # an attack, not a defect
        else:
            back, fwd = mono[max(0, k - look):k], mono[k + 1:k + 1 + look]
            if back.size > 4 and fwd.size > 4 and (np.all(np.diff(back) >= -1e-6) or np.all(np.diff(fwd) >= -1e-6)):
                continue
        kept.append(k)
    half, win = max(2, int(round(half_ms * sr / 1000.0))), max(3, int(round(smooth_ms * sr / 1000.0)))
    merge = []
    for k in kept:
        if merge and k - merge[-1] < half:
            continue                                   # overlapping windows: one repair covers both
        merge.append(k)
    for k in merge:
        a, b = max(1, k - half), min(len(y) - 1, k + half)
        if b - a < win + 2:
            continue
        seg = y[a:b].copy()
        sm = np.stack([uniform_filter1d(seg[:, c].astype(np.float64), size=win) for c in range(y.shape[1])], axis=1)
        ramp = (np.sin(np.linspace(0.0, np.pi, b - a)) ** 2).astype(np.float32)[:, None]
        y[a:b] = (seg * (1.0 - ramp) + sm.astype(np.float32) * ramp).astype(np.float32)
    if merge and _passes < 2:
        # a step that was only partly smoothed still measures as a click (6 of ~50 on a djembe stem): re-detect what is
        # left instead of assuming one pass reached every event
        return repair_clicks(y, sr, mad_z, floor_frac, cluster_ms, isolate_ms, second_ratio, smooth_ms, half_ms,
                             _passes + 1)
    return y


def trim_digital_lead(x, sr=44100, max_ms=150.0):
    """Roll a stem left by the digital silence a sampled patch starts with.

    A sampled instrument can carry tens of milliseconds of digital zero before its attack (measured: 110 ms on one
    bank's kalimba, 70 ms on a bowed bass), so every note of that patch sounds that late. The delay is identical
    for every note, so removing it from the stem start aligns the whole part with the score instead of moving a
    single note. Only digital silence is trimmed, never an audible swell: 2 ms up to `max_ms`, nothing else.
    """
    y = to_2d(x).astype(np.float32)
    if len(y) == 0:
        return y
    peak = float(np.max(np.abs(y))) or 1.0
    # 72 dB below the stem's loudest moment is inaudible in every listening condition, so what precedes the first
    # sample above it is the patch's pre-attack room tone, not an attack: a bowed bass carried 40 ms of it, which
    # put its first written note 40 ms late against the score.
    loud = np.flatnonzero(np.max(np.abs(y), axis=1) > max(peak * 10 ** (-72.0 / 20.0), 1e-5))
    if loud.size == 0:
        return y
    lead = int(loud[0])
    if lead < int(0.002 * sr) or lead > int(float(max_ms) * sr / 1000.0):
        return y
    return np.concatenate([y[lead:], np.zeros((lead, y.shape[1]), np.float32)]).astype(np.float32)


def soften_onsets(x, sr=44100, times=(), ms=2.0):
    """A short raised-cosine ramp at each onset that starts from silence.

    A sampled drum or shaker often begins on a single-sample step: its PCM starts at full level instead of rising
    out of silence, so the high-pass residual shows a clustered impulse at every hit (measured: a GM shaker read
    an impulse on 250 of its 352 hits). Two to three milliseconds is faster than any audible attack, so the
    transient is unchanged, but the step that reads as a click is gone. An onset that lands inside a still-ringing
    hit is left alone: ramping there would cut the ringing body, not a step.
    """
    y = to_2d(x).astype(np.float32)
    n = int(round(float(ms) * sr / 1000.0))
    if n < 2 or len(y) == 0 or not len(times):
        return y
    ramp = (0.5 - 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, n))).astype(np.float32)[:, None]
    peak = float(np.max(np.abs(y))) or 1.0
    for t in times:
        i0 = int(round(float(t) * sr))
        if not (0 < i0 < len(y) - n):
            continue
        if float(np.max(np.abs(y[max(0, i0 - 1):i0]))) > 0.02 * peak:
            continue                                    # already sounding: a flam or a layer, not a fresh onset
        y[i0:i0 + n] *= ramp
    return y


def dynamic_tilt(x, sr=44100, velocity=None, low_hz=1500.0, span_hz=2600.0, floor=0.55, curve=1.2, norm_env=None):
    """Brightness that follows level: a quiet moment is a warm low-passed copy, a loud one the full band.

    The corner is low_hz + span_hz * (mean velocity / 127); `floor` is how much of the full band a silent moment
    keeps and `curve` bends the blend. Level-compensated over the stem, so pattern level does not move. This is the
    tilt enhance_sf2_dynamics always applied to SoundFont stems, as its own function so that a preset can give it
    to any stem (`dynamic_tilt` on a track or an instrument preset).
    """
    y = to_2d(x).astype(np.float32)
    if len(y) == 0:
        return y
    if norm_env is None:
        env = envelope(y, sr=sr, attack_ms=5.0, release_ms=80.0)[:, None]
        norm_env = env / max(float(env.max()), 1e-6)
    v = 0.55 if velocity is None else float(np.clip(float(velocity) / 127.0, 0.0, 1.0))
    tilt_hz = float(low_hz) + float(span_hz) * v
    sos_warm = signal.butter(2, min(tilt_hz, sr * 0.45), btype='lowpass', fs=sr, output='sos')
    warm = signal.sosfilt(sos_warm, y, axis=0).astype(np.float32)
    w = float(floor) + (1.0 - float(floor)) * np.clip(norm_env, 0.0, 1.0) ** float(curve)
    before = float(np.sqrt(np.mean(y ** 2)) + 1e-12)
    y = (warm * (1.0 - w) + y * w).astype(np.float32)
    return (y * (before / float(np.sqrt(np.mean(y ** 2)) + 1e-12))).astype(np.float32)


def resonator_bank(x, sr, freqs, q):
    """A mono signal through parallel two-pole resonators (unity gain at each centre), summed: strings that are
    never played but ring when the music excites them. A resonator at f with quality q rings for q / (pi f) s."""
    x = np.asarray(x, dtype=np.float64)
    out = np.zeros(len(x))
    for f in freqs:
        if 20.0 < float(f) < 0.45 * sr:
            b, a = signal.iirpeak(float(f), float(q), fs=sr)
            out += signal.lfilter(b, a, x)
    return out


def enhance_sf2_dynamics(x, sr=44100, role='chord', velocity=None):
    """Restores transient snap and velocity-driven harmonic excitement to SF2 stems.

    A SoundFont has one sample layer per instrument, and TinySoundFont maps velocity to plain gain: a quiet
    note is the same timbre, only quieter (measured on GeneralUser-GS: velocity 127 -> 60 is -6.5 dB with the
    spectral centroid unchanged at x1.000). No DSP can re-synthesise the missing bright velocity layer, so this
    puts back the two things a flat layer loses: the front of the note, and a harmonic lift that follows level.
    velocity: the stem's mean MIDI velocity (0-127). A quiet part is rendered darker, as a real instrument's
    soft dynamic is: the tilt corner follows it. Intra-stem dynamics are handled by the envelope term below.

    Both stages are level-compensated, so this changes punch, not pattern level.
    """
    y = to_2d(x).astype(np.float32)
    if len(y) == 0:
        return y
    if role in ('drum', 'arp'):
        y = transient_shaper(y, sr=sr, attack=3.0, sustain=-0.8, fast_ms=2.5, slow_ms=45.0)
    if role in ('chord', 'melody', 'counter', 'drum', 'bass'):
        env = envelope(y, sr=sr, attack_ms=5.0, release_ms=80.0)[:, None]
        peak = max(float(env.max()), 1e-6)
        norm_env = env / peak
        # --- dynamic tilt: a quiet passage is warm and mellow, a loud one opens to the full band ---
        # TinySoundFont has no velocity filter, so brightness was flat across the whole stem. One warm low-passed
        # copy, blended in by how loud the moment is, restores the direction (still not a per-note brightness law:
        # that needs a second sample layer). Level-compensated globally, so pattern level is unchanged.
        if role in ('chord', 'melody', 'counter', 'bass'):
            y = dynamic_tilt(y, sr=sr, velocity=velocity, norm_env=norm_env)   # soft (v=30) ~2.1 kHz, hard ~4.1 kHz
        drive = (1.0 + 0.55 * np.clip((norm_env - 0.55) / 0.45, 0.0, 1.0) ** 2).astype(np.float32)
        # tanh(y*drive)/tanh(drive) carries a +2.4 dB small-signal gain; dividing the drive back out keeps the
        # harmonics and drops the free level, so gain staging never inherits a hidden boost from this stage.
        y = (np.tanh(y * drive) / drive).astype(np.float32)
    return y


def _apply_bands(x, sr, bands):
    """Filter chain from [(type, f, gain_db, q)] using SciPy (slope/order is ours to choose)."""
    y = np.asarray(x, dtype=np.float32)
    for kind, f, gain, q in bands:
        f = float(np.clip(float(f), 20.0, sr / 2.0 - 50.0))
        if kind in ('hp', 'highpass'):
            y = signal.sosfilt(signal.butter(2, f, 'high', fs=sr, output='sos'), y, axis=0).astype(np.float32)
        elif kind in ('lp', 'lowpass'):
            y = signal.sosfilt(signal.butter(2, f, 'low', fs=sr, output='sos'), y, axis=0).astype(np.float32)
        else:
            y = _peak(y, sr, f, float(gain), float(q))
    return y


def _peak(x, sr, f, gain_db, q):
    """RBJ peaking EQ, applied with a short biquad cascade (no Pedalboard needed)."""
    from scipy.signal import lfilter
    A = 10.0 ** (float(gain_db) / 40.0)
    w0 = 2.0 * np.pi * min(max(float(f), 10.0), sr / 2.0 - 50.0) / sr
    alpha = np.sin(w0) / (2.0 * max(float(q), 0.05))
    b = np.array([1 + alpha * A, -2 * np.cos(w0), 1 - alpha * A])
    a = np.array([1 + alpha / A, -2 * np.cos(w0), 1 - alpha / A])
    return lfilter(b / a[0], a / a[0], x, axis=0).astype(np.float32)


def slope_filter(x, sr=44100, f=80.0, kind='hp', order=4):
    """A high/low-pass whose steepness is chosen, not fixed (Butterworth, `order` poles)."""
    y = np.asarray(x, dtype=np.float32)
    if f <= 0 or f >= sr / 2.0:
        return y
    sos = signal.butter(int(max(1, order)), float(f), 'high' if kind in ('hp', 'highpass') else 'low',
                        fs=sr, output='sos')
    return signal.sosfilt(sos, y, axis=0).astype(np.float32)


def pan_energy(x, pan, floor=0.0):
    """A pan law that keeps a stereo source's image, level-neutral at the centre.

    mono in    constant power, 0 dB at pan 0 (cos/sin x sqrt2).
    stereo in  a balance, not a crossfade: the near channel stays at unity, the far channel follows
               cos(|pan| * pi/2) down to `floor`. So pan 0.0 is exactly 0.00 dB ([1, 1], the image untouched),
               pan +-1.0 is the near channel alone, and the old law's +3.01 dB centre boost and its
               hard floor at pan ~0.5 (which never reached the sides) are both gone.
    """
    y = to_2d(x)
    pan = float(np.clip(pan, -1.0, 1.0))
    if y.shape[1] < 2:
        th = (pan + 1.0) * np.pi / 4.0
        return y * np.array([np.cos(th) * np.sqrt(2), np.sin(th) * np.sqrt(2)], dtype=np.float32)
    far = max(float(np.clip(floor, 0.0, 1.0)), float(np.cos(abs(pan) * np.pi / 2.0)))
    gl, gr = (1.0, far) if pan >= 0 else (far, 1.0)
    return (y * np.array([gl, gr], dtype=np.float32)).astype(np.float32)
