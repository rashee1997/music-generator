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
import sys

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
    """Inter-channel correlation of a stereo signal, -1..1 (1.0 when there is nothing to compare).

    Summed in float64 from the float32 samples instead of casting each channel to a full float64 copy: the same
    Pearson coefficient, without two master-length buffers that existed only to be read once.
    """
    x = to_2d(x)
    if x.shape[1] < 2:
        return 1.0
    a, b = x[:, 0], x[:, 1]
    n = len(a)
    sa = np.einsum('i,i->', a, a, dtype=np.float64)
    sb = np.einsum('i,i->', b, b, dtype=np.float64)
    sab = np.einsum('i,i->', a, b, dtype=np.float64)
    ma = float(np.einsum('i->', a, dtype=np.float64)) / n
    mb = float(np.einsum('i->', b, dtype=np.float64)) / n
    va, vb = sa / n - ma * ma, sb / n - mb * mb
    if va <= 1e-18 or vb <= 1e-18:
        return 1.0
    v = float((sab / n - ma * mb) / np.sqrt(va * vb))
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
    x = to_2d(x)
    if x.shape[1] < 2:
        return 0.0

    def _rms_db(a):
        v = np.asarray(a)
        v = v.reshape(v.shape[0], -1)
        return float(10.0 * np.log10(np.einsum('ij,ij->', v, v, dtype=np.float64) / max(v.size, 1) + 1e-24))

    return _rms_db(x.mean(axis=1)) - _rms_db(x)


def band_power(x, sr, lo, hi, nperseg=4096):
    """Total power in [lo, hi) Hz, from a Welch PSD of the mono sum."""
    x = to_2d(x)
    mono = x.mean(axis=1) if x.shape[1] > 1 else x[:, 0]
    n = min(int(nperseg), max(256, len(mono)))
    f, p = signal.welch(mono.astype(np.float64), fs=sr, nperseg=n)
    m = (f >= lo) & (f < hi)
    return float(np.sum(p[m]))


_BAND_DB_CACHE = {}          # (id(x), shape, lo, hi, sr) -> (the array itself, the answer)
_BAND_DB_MAX = 256           # a run asks for a handful of bands of a handful of stems; this only bounds a leak


def band_db(x, sr, lo, hi):
    """10 log10 of one band's power, memoised per array object.

    Several gate rows ask for the same band of the same stem (masking, balance, kick grid, separation), and each
    call re-ran the whole Welch PSD over a multi-minute stem. The cache holds the array itself, so its identity
    cannot be recycled while the entry is live, and an edit produces a new array and therefore a new measurement.
    """
    key = (id(x), np.shape(x), float(lo), float(hi), int(sr))
    got = _BAND_DB_CACHE.get(key)
    if got is not None and got[0] is x:
        return got[1]
    value = 10.0 * np.log10(band_power(x, sr, lo, hi) + EPS)
    if len(_BAND_DB_CACHE) >= _BAND_DB_MAX:
        _BAND_DB_CACHE.clear()
    _BAND_DB_CACHE[key] = (x, value)
    return value


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
    """Oversampled true peak, dBTP. The whole buffer is resampled, as before: no short-buffer surprises.

    One channel at a time, float32, with the peak taken blockwise. The oversampled buffer is four times the
    signal's length, and the old float64 cast plus a full-length `abs` made this the largest single allocation in
    mastering: measured on a 180 s stereo master it added 676 MB to a 63.5 MB signal. float32 is the precision of
    the delivered file (PCM_24), and the blockwise maximum over the same resampled samples agrees with the
    whole-buffer measurement to 2e-7 dB.
    """
    y = to_2d(x)
    if len(y) == 0:
        return -120.0
    peak = 0.0
    for c in range(y.shape[1]):
        z = signal.resample_poly(np.ascontiguousarray(y[:, c], dtype=np.float32), over, 1)
        for a in range(0, len(z), 1 << 18):
            seg = z[a:a + (1 << 18)]
            peak = max(peak, float(np.abs(seg).max()))
        del z
    return float(20 * np.log10(peak + EPS))


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
    e = np.zeros(n)                             # the follower has always started from rest: block 0 stays 0
    e[1:] = _follow_rows(m[1:, None], rate, attack_ms, release_ms)[:, 0]
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
    wet = y * g * 10.0 ** (float(makeup_db) / 20.0)      # make-up belongs to the compressed path: the dry path stays dry
    out = wet if mix >= 1.0 else y * (1.0 - mix) + wet * mix
    return out.astype(np.float32)


def multiband_compressor(x, sr=44100, bands=None, **kw):
    """Split into bands, compress each, sum. `bands` is a list of dicts:

        {"lo": 20, "hi": 120, "threshold_db": -20, "ratio": 2.5, "attack_ms": 20,
         "release_ms": 150, "knee_db": 6, "gain_db": 0}

    The split is a 2nd-order band-pass per band. The sum is not sample-exact in phase (a Linkwitz-Riley
    network would be); a preset that needs that should keep `dynamics.multiband` off.
    Whatever the declared bands do not cover (input minus the sum of the unprocessed band parts) is added back
    untouched, so a gap between bands passes through instead of being discarded.
    """
    y = to_2d(x).astype(np.float32)
    if not bands:
        return y
    out = np.zeros_like(y)
    covered = np.zeros_like(y)
    for b in bands:
        lo = max(20.0, float(b.get('lo', 20.0)))
        hi = min(sr / 2.0 - 50.0, float(b.get('hi', sr / 2.0 - 50.0)))
        if hi <= lo:
            continue
        sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
        part = signal.sosfilt(sos, y, axis=0).astype(np.float32)
        covered += part
        part = compressor(part, sr, threshold_db=b.get('threshold_db', -20.0), ratio=b.get('ratio', 2.0),
                          attack_ms=b.get('attack_ms', 15.0), release_ms=b.get('release_ms', 150.0),
                          knee_db=b.get('knee_db', 0.0), detector=b.get('detector', 'peak'),
                          stereo_link=True, **{k: v for k, v in kw.items() if k in
                                               ('lookahead_ms', 'rate', 'sidechain')})
        out += part * 10.0 ** (float(b.get('gain_db', 0.0)) / 20.0)
    return (out + (y - covered)).astype(np.float32)


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


def transient_shaper(x, sr=44100, attack=0.0, sustain=0.0, fast_ms=3.0, slow_ms=60.0, ref_db=20.0):
    """attack/sustain in dB. Positive attack sharpens the front of a note, negative softens it;
    sustain is the body after the front. 0/0 returns the input untouched.

    The front is measured as the fast envelope over the slow one, in dB. The gain follows it linearly and reaches
    the full `attack` dB when the front stands `ref_db` over the body (20 dB: a clear attack) and stays there, so
    `attack=3` never moves a note by more than +3 dB. `sustain` is the same on the other side: its full dB when
    the body stands `ref_db` over the front."""
    if attack == 0.0 and sustain == 0.0:
        return to_2d(x).astype(np.float32)
    y = to_2d(x).astype(np.float32)
    fast = envelope(y, sr, fast_ms, fast_ms * 2.0)
    slow = envelope(y, sr, slow_ms, slow_ms * 2.0)
    delta = 20.0 * np.log10((fast + EPS) / (slow + EPS))         # dB; >0 on a transient, <=0 on a sustain
    front = np.clip(delta / float(ref_db), 0.0, 1.0)
    body = np.clip(-delta / float(ref_db), 0.0, 1.0)
    curve = 10.0 ** ((attack * front + sustain * body) / 20.0)
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
    except Exception as exc:                          # a different rule would change which clicks are repaired: say so
        sys.stderr.write(f'[dsp] WARN repair_clicks: gate_checks._is_attack is unavailable ({exc!r}); '
                         f'using the built-in monotone-rise rule instead\n')
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


def soften_onsets(x, sr=44100, times=(), ms=2.0, skip_sounding=True):
    """A short raised-cosine ramp at each onset.

    A sampled drum or shaker often begins on a single-sample step: its PCM starts at full level instead of rising
    out of silence, so the high-pass residual shows a clustered impulse at every hit (measured: a GM shaker read
    an impulse on 250 of its 352 hits). Two to three milliseconds is faster than any audible attack, so the
    transient is unchanged, but the step that reads as a click is gone. An onset that lands inside a still-ringing
    hit is left alone when `skip_sounding` is on: on a sustained instrument that would cut the ringing body, not a
    step. A percussion track passes `skip_sounding=False`, because a drum hit is a fresh sample even over the ring
    of the previous one, and in a dense pattern no hit ever starts from silence.
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
        if skip_sounding and float(np.max(np.abs(y[max(0, i0 - 1):i0]))) > 0.02 * peak:
            continue                                    # already sounding: a flam or a layer, not a fresh onset
        w = ramp
        if not skip_sounding:
            # On a hit that lands over a still-ringing one the ramp starts at the level already there, not at zero:
            # multiplying a ringing tail down to 0 is a step of its own (measured: a kit read 28 click events in the
            # master with a 1.5/0.3 ms ramp from zero, 0 with the guard on). From the tail's own level the seam stays
            # continuous and most of the new attack is still stretched.
            a = min(1.0, float(np.max(np.abs(y[max(0, i0 - 2):i0]))) / peak)
            w = a + (1.0 - a) * ramp
        y[i0:i0 + n] *= w
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


def level_timbre(x, sr=44100, drive=0.5, tilt_db=2.0, tilt_hz=2800.0, band_hz=(140.0, 7000.0),
                 amount=0.6, smooth_s=0.35, quiet_pct=20.0, loud_pct=95.0, oversample=2):
    """A source whose timbre changes with its own loudness, not only its level.

    A brass note played softly is dominated by its first partials; played loudly its high-frequency slope
    flattens (Fletcher et al. 1999 measure about -30 dB/octave at a low level and -10 dB/octave at a high one on
    a trumpet) and the spectral centroid rises. The same direction holds for a bowed string, where spectral
    centroid rises with bow force and from pp to f (Schoonderwaldt 2009; Chudy 2016), and for wind noise, whose
    share of the spectrum falls as the dynamic rises (JASA 2018). A SoundFont maps velocity to gain only, so the
    engine has to put that coupling back.

    The coupling is measured *within the stem*, not from an absolute level: short-term RMS is mapped between the
    piece's own quiet and loud percentiles, so a soft passage and a loud one are compared with each other. The
    nonlinear residue of a soft-clipped copy of the 140 Hz-7 kHz band is added in proportion to that measure, and
    a high shelf follows it. Both are level-compensated, so the part's pattern level does not move: this changes
    colour, not loudness. At `drive=0, tilt_db=0` the function returns its input.

    Values are arguments, never decisions: an instrument preset or a track owns them. `drive` 0.5 and
    `tilt_db` 2.0 dB are starting values, not measurements of any one instrument.
    """
    y = to_2d(x).astype(np.float32)
    if len(y) < int(0.1 * sr):
        return y
    drive, tilt_db, amount = float(drive), float(tilt_db), float(amount)
    if drive <= 0.0 and tilt_db <= 0.0:
        return y
    if drive < 0.0 or tilt_db < 0.0 or amount < 0.0:
        raise ValueError('level_timbre: drive, tilt_db and amount cannot be negative')
    if not (0.0 <= float(quiet_pct) < float(loud_pct) <= 100.0):
        raise ValueError('level_timbre: quiet_pct must be below loud_pct (0..100)')
    if int(oversample) not in (1, 2, 4):
        raise ValueError('level_timbre: oversample must be 1, 2 or 4')
    from scipy.ndimage import uniform_filter1d
    mono = np.abs(y).max(axis=1).astype(np.float64)
    ms = uniform_filter1d(mono ** 2, size=max(1, int(0.05 * sr)), mode='nearest')
    lvl = 10.0 * np.log10(ms + EPS)
    active = lvl > float(lvl.max()) - 55.0
    if int(active.sum()) < 16:
        return y
    quiet = float(np.percentile(lvl[active], float(quiet_pct)))
    loud = float(np.percentile(lvl[active], float(loud_pct)))
    if loud - quiet < 2.0:                     # one dynamic: there is no coupling to follow
        return y
    u = np.clip((lvl - quiet) / (loud - quiet), 0.0, 1.0)
    u = uniform_filter1d(u, size=max(1, int(float(smooth_s) * sr)), mode='nearest').astype(np.float32)

    lo, hi = float(band_hz[0]), min(float(band_hz[1]), sr * 0.45)
    if not (20.0 < lo < hi):
        raise ValueError(f'level_timbre: band_hz {band_hz!r} is not a usable band at {sr} Hz')
    band = signal.sosfilt(signal.butter(4, [lo, hi], btype='band', fs=sr, output='sos'), y, axis=0).astype(np.float32)
    gain = 1.0 + drive * u
    if int(oversample) > 1:
        # the residue is generated at a higher rate and brought back through the anti-image filter, so the
        # harmonics it adds land below Nyquist instead of folding over the top octave
        band_o = signal.resample_poly(band, int(oversample), 1, axis=0).astype(np.float32)
        gain_o = signal.resample_poly(gain, int(oversample), 1).astype(np.float32)
        add = (np.tanh(band_o * gain_o[:, None]) - band_o).astype(np.float32)
        add = signal.resample_poly(add, 1, int(oversample), axis=0).astype(np.float32)
        add = add[:len(y)] if len(add) >= len(y) else np.pad(add, ((0, len(y) - len(add)), (0, 0)))
    else:
        add = (np.tanh(band * gain[:, None]) - band).astype(np.float32)
    out = y + (amount * u[:, None] * add).astype(np.float32)
    if tilt_db > 0.0:
        hf = signal.sosfilt(signal.butter(2, min(float(tilt_hz), sr * 0.45), btype='high', fs=sr, output='sos'),
                            y, axis=0).astype(np.float32)
        out = out + hf * (10.0 ** ((tilt_db * u) / 20.0) - 1.0).astype(np.float32)[:, None]
    rms_in = float(np.sqrt(np.mean(y.astype(np.float64) ** 2) + EPS))
    rms_out = float(np.sqrt(np.mean(out.astype(np.float64) ** 2) + EPS))
    if np.isfinite(rms_out) and rms_out > EPS:
        out *= np.float32(rms_in / rms_out)
    if not np.isfinite(out).all():
        raise ValueError('level_timbre: produced non-finite samples (check drive/tilt_db/band_hz)')
    return out.astype(np.float32)


def register_tone(x, sr=44100, semitones=0.0, pivot_hz=1500.0, db_per_oct=1.5, max_db=6.0):
    """Reduce the formant shift of a sampled note transposed above its comfortable register.

    Resampling a sample upward moves its whole spectral envelope up by the transposition ratio, so the formants
    and the spectral centroid rise with pitch even when the player did not change colour (an effect audible at a
    fifth; Driedger/Mueller 2016). A high shelf that falls with the transposition is a first-order correction, not
    a formant-preserving resynthesis: it removes the excess top that the resampling added and leaves the note's
    level where it was. `semitones` is how far above `pivot_hz`'s register the note sits; `db_per_oct` is the cut
    per octave, capped at `max_db`. Values are starting values and belong to the instrument preset or track.

    0 semitones or 0 dB/octave returns the input, so a part that does not ask for it is unchanged.
    """
    y = to_2d(x).astype(np.float32)
    if float(db_per_oct) < 0.0 or float(max_db) < 0.0:
        raise ValueError('register_tone: db_per_oct and max_db cannot be negative')
    cut = float(db_per_oct) * max(0.0, float(semitones)) / 12.0
    cut = min(cut, float(max_db))
    if cut <= 0.0 or len(y) < 8:
        return y
    hz = min(sr * 0.45, max(20.0, float(pivot_hz)))
    hf = signal.sosfilt(signal.butter(2, hz, btype='high', fs=sr, output='sos'), y, axis=0).astype(np.float32)
    out = y + hf * np.float32(10.0 ** (-cut / 20.0) - 1.0)
    rms_in = float(np.sqrt(np.mean(y.astype(np.float64) ** 2) + EPS))
    rms_out = float(np.sqrt(np.mean(out.astype(np.float64) ** 2) + EPS))
    if np.isfinite(rms_out) and rms_out > EPS:
        out *= np.float32(rms_in / rms_out)
    if not np.isfinite(out).all():
        raise ValueError('register_tone: produced non-finite samples')
    return out.astype(np.float32)


def transient_variety(x, sr=44100, times=(), gain_db=1.0, tilt_db=1.5, width_ms=25.0, seed=0):
    """Give each repeated onset its own attack level and bite, without changing the written rhythm.

    A round-robin library still plays the same handful of attacks, and a doubled pluck or a percussion family can
    read as one sample triggered again (measured attack similarity is the `realism_report` transient row). This adds
    a deterministic per-onset gain of +/-`gain_db` and a short high-band emphasis of +/-`tilt_db`, shaped by a
    raised-cosine window of `width_ms` around each onset. It cannot invent a new sample, and it never moves an onset
    in time. `times` are seconds; onsets closer together than the window are one event.

    Values are starting values; the track or preset owns them. gain_db=tilt_db=0 returns the input.
    """
    y = to_2d(x).astype(np.float32)
    if float(gain_db) < 0.0 or float(tilt_db) < 0.0 or float(width_ms) <= 0.0:
        raise ValueError('transient_variety: gain_db, tilt_db and width_ms must be non-negative')
    if float(gain_db) == 0.0 and float(tilt_db) == 0.0:
        return y
    n = len(y)
    span = max(1, int(float(width_ms) * sr / 1000.0))
    rng = np.random.default_rng(int(seed) + 15485863)
    gain = np.ones(n, np.float32)
    tilt = np.zeros(n, np.float32)
    last = -1
    for t in sorted(float(v) for v in times):
        i = int(round(t * sr))
        if i < 0 or i >= n or i - last < span:
            continue
        last = i
        a = float(rng.uniform(-float(gain_db), float(gain_db)))
        b = float(rng.uniform(-float(tilt_db), float(tilt_db)))
        lo, hi = max(0, i - span // 2), min(n, i + span // 2)
        w = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, hi - lo, dtype=np.float32))
        gain[lo:hi] *= (10.0 ** (a / 20.0) * w + (1.0 - w)).astype(np.float32)
        tilt[lo:hi] += (b * w).astype(np.float32)
    hf = signal.sosfilt(signal.butter(2, min(sr * 0.45, 2000.0), btype='high', fs=sr, output='sos'),
                        y, axis=0).astype(np.float32)
    out = y * gain[:, None] + hf * (10.0 ** (tilt / 20.0) - 1.0).astype(np.float32)[:, None]
    if not np.isfinite(out).all():
        raise ValueError('transient_variety: produced non-finite samples')
    return out.astype(np.float32)


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
