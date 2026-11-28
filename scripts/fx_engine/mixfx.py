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

"""mixfx.py - the mixing techniques as effects: a saturator with six characters, a split-band de-esser, a gate / expander, a parallel
(New York) compressor, an upward compressor, a band-dependent stereo width, a frequency shifter, a key-locked resonator bank, a ducked
ping-pong delay and a spectral tilt. Same contract as modfx.py: `fn(x, sr, p, rng) -> y`, same length and channels; the engine blends
the result by the range mask and `mix`.

None of them holds a number: every default, range and the sentence saying what it does is in references/data/presets/fx/effects.json.
The sources of the techniques are in knowledgebase/sound-design/mixing-techniques.md.
"""
import math

import numpy as np
from scipy import signal

from . import core

HOP_MS = 1.0          # control rate of the level followers: a gain curve is computed once a millisecond and interpolated


def _two(x):
    return np.asarray(x, dtype=np.float32)


def _ctrl_env(mono_abs, sr, attack_ms, release_ms):
    """A peak follower with its own attack and release, computed at 1 kHz and interpolated back to the sample rate (a Python loop over
    120,000 points for two minutes, not over 5 million samples)."""
    hop = max(1, int(sr * HOP_MS / 1000.0))
    n = len(mono_abs)
    m = (n + hop - 1) // hop
    pad = np.pad(mono_abs, (0, m * hop - n))
    peaks = pad.reshape(m, hop).max(axis=1)
    ca = math.exp(-HOP_MS / max(0.05, float(attack_ms)))
    cr = math.exp(-HOP_MS / max(0.05, float(release_ms)))
    env = np.empty(m)
    e = 0.0
    for i in range(m):
        v = peaks[i]
        c = ca if v > e else cr
        e = v + c * (e - v)
        env[i] = e
    return np.interp(np.arange(n), (np.arange(m) + 0.5) * hop, env)


def _gain_follow(curve_db, sr, fall_ms, rise_ms, reduce='min'):
    """A curve in dB smoothed with one time constant when it falls and another when it rises, at the 1 kHz control rate. A gain-reduction
    curve falls with its attack and recovers with its release (`reduce='min'` keeps the deepest millisecond); a lift curve is the other
    way round, so it is given the same call with the two times swapped by the caller."""
    hop = max(1, int(sr * HOP_MS / 1000.0))
    n = len(curve_db)
    m = (n + hop - 1) // hop
    pad = np.pad(curve_db, (0, m * hop - n), mode='edge')
    blocks = pad.reshape(m, hop)
    ctl = blocks.min(axis=1) if reduce == 'min' else blocks.mean(axis=1)
    cf = math.exp(-HOP_MS / max(0.05, float(fall_ms)))
    cr = math.exp(-HOP_MS / max(0.05, float(rise_ms)))
    out = np.empty(m)
    g = 0.0
    for i in range(m):
        v = ctl[i]
        c = cf if v < g else cr
        g = v + c * (g - v)
        out[i] = g
    return np.interp(np.arange(n), (np.arange(m) + 0.5) * hop, out)


def _detect(x, sr, hp_hz=0.0):
    """The mono level the dynamics effects follow: the louder channel, optionally high-passed so a bass does not trigger them."""
    d = np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)
    if hp_hz and hp_hz > 20.0:
        sos = signal.butter(2, min(hp_hz, sr * 0.45) / (sr / 2), 'high', output='sos')
        ch = x if x.ndim == 2 else x[:, None]
        d = np.max(np.abs(signal.sosfilt(sos, ch, axis=0)), axis=1)
    return d


def _apply_gain_db(x, g_db):
    return (x * (10.0 ** (g_db / 20.0))[:, None]).astype(np.float32)


def _db(v):
    return 20.0 * np.log10(np.maximum(v, 1e-9))


# ---------------------------------------------------------------------------------------------------------------- saturator
def saturator(x, sr, p, rng):
    """Six characters of waveshaping, oversampled four times so the harmonics it makes do not fold back:
    tube (asymmetric, even harmonics), tape (symmetric, odd harmonics, rolled off by `tone_hz`), soft_clip (x / (1 + |x|)), hard_clip
    (a ceiling), fold (a wavefolder: the signal turns back on itself) and diode (one half-wave bent more than the other)."""
    mode, drive = p['mode'], 10.0 ** (float(p['drive_db']) / 20.0)
    bias, ceiling = float(p['bias']), 10.0 ** (float(p['ceiling_db']) / 20.0)
    y = np.asarray(x, dtype=np.float64)
    up = signal.resample_poly(y, 4, 1, axis=0)
    pk = max(float(np.max(np.abs(y))), 1e-6)
    u = up / pk * drive
    if mode == 'tube':
        s = np.tanh(u + bias) - math.tanh(bias)
    elif mode == 'tape':
        s = np.tanh(u)
    elif mode == 'soft_clip':
        s = u / (1.0 + np.abs(u))
    elif mode == 'hard_clip':
        s = np.clip(u, -1.0, 1.0)
    elif mode == 'fold':
        s = np.sin(0.5 * math.pi * np.clip(u, -4.0, 4.0))
    else:                                                   # diode
        s = np.where(u >= 0.0, np.tanh(u), 0.5 * np.tanh(u))
    s = s * pk * min(1.0, ceiling) if mode in ('hard_clip', 'soft_clip') else s * pk
    out = signal.resample_poly(s, 1, 4, axis=0)[:len(y)]
    tone = float(p['tone_hz'])
    if tone < sr * 0.45:
        out = signal.sosfilt(signal.butter(1, tone / (sr / 2), 'low', output='sos'), out, axis=0)
    if p['match_level'] == 'yes':                           # the character changes, the level does not
        rin, rout = float(np.sqrt(np.mean(y ** 2))), float(np.sqrt(np.mean(out ** 2)))
        if rin > 1e-9 and rout > 1e-9:
            out = out * (rin / rout)
    return out.astype(np.float32)


# --------------------------------------------------------------------------------------------------------------- de-esser
def de_esser(x, sr, p, rng):
    """Split-band: only the sibilant band is turned down, and only while it is louder than `threshold_db` (a wide-band compressor would
    dull the whole voice). The band is taken out with a zero-phase band-pass, so what is left is the signal with no phase hole."""
    f, q = float(p['freq_hz']), float(p['q'])
    lo, hi = max(40.0, f / (1.0 + 0.5 / q * 2.0)), min(sr * 0.45, f * (1.0 + 0.5 / q * 2.0))
    sos = signal.butter(2, [lo / (sr / 2), hi / (sr / 2)], 'band', output='sos')
    y = _two(x)
    ch = y if y.ndim == 2 else y[:, None]
    band = signal.sosfiltfilt(sos, ch, axis=0)
    det = _ctrl_env(np.max(np.abs(band), axis=1), sr, 1.0, float(p['release_ms']))
    over = _db(det) - float(p['threshold_db'])
    g_db = -np.clip(over, 0.0, None) * (1.0 - 1.0 / float(p['ratio']))
    g_db = np.maximum(g_db, -float(p['max_cut_db']))
    gain = 10.0 ** (g_db / 20.0)
    out = ch - band * (1.0 - gain)[:, None]
    return out.astype(np.float32) if y.ndim == 2 else out[:, 0].astype(np.float32)


# ------------------------------------------------------------------------------------------------------------- gate / expander
def gate(x, sr, p, rng):
    """A downward expander: below `threshold_db` the level falls by (ratio - 1) dB for every dB under, down to `range_db` of reduction; a
    ratio of 100 is a gate. `hold_ms` keeps it open after the level drops; the detector can be high-passed so a rumble does not hold it."""
    from scipy.ndimage import maximum_filter1d
    y = _two(x)
    det = _ctrl_env(_detect(y, sr, float(p['sidechain_hp_hz'])), sr, 0.5, 8.0)          # a fast detector: the closing time is the gain's, below
    hold = int(sr * float(p['hold_ms']) / 1000.0)
    if hold > 1:
        det = maximum_filter1d(det, size=hold, mode='nearest')            # peak hold: the level stays up for hold_ms after it falls
    under = float(p['threshold_db']) - _db(det)
    g_db = np.maximum(-np.clip(under, 0.0, None) * (float(p['ratio']) - 1.0), -float(p['range_db']))
    g_db = _gain_follow(g_db, sr, float(p['release_ms']), float(p['attack_ms']))     # it closes with `release_ms` and opens with `attack_ms`
    return _apply_gain_db(y, g_db)


# ----------------------------------------------------------------------------------------------- parallel / upward compressors
def parallel_comp(x, sr, p, rng):
    """New York compression: a copy squashed hard and added under the original, so the quiet detail comes up and the transients are left
    alone. The engine's `mix` is the blend; `hp_hz` keeps the low end of the copy out of it."""
    y = _two(x)
    det = _ctrl_env(_detect(y, sr), sr, float(p['attack_ms']), float(p['release_ms']))
    over = _db(det) - float(p['threshold_db'])
    knee = float(p['knee_db'])
    if knee > 0.0:                                          # the quadratic soft knee of a feed-forward compressor
        over = np.where(over <= -knee / 2.0, 0.0, np.where(over < knee / 2.0, (over + knee / 2.0) ** 2 / (2.0 * knee), over))
    g_db = -np.clip(over, 0.0, None) * (1.0 - 1.0 / float(p['ratio'])) + float(p['makeup_db'])
    comp = _apply_gain_db(y, g_db)
    hp = float(p['hp_hz'])
    if hp > 20.0:
        comp = signal.sosfilt(signal.butter(2, hp / (sr / 2), 'high', output='sos'), comp, axis=0).astype(np.float32)
    return (y + comp).astype(np.float32)


def upward_comp(x, sr, p, rng):
    """Upward compression: what is under `threshold_db` is lifted by (1 - 1 / ratio) of the distance, up to `max_gain_db`, and nothing under
    `floor_db` is lifted (a noise floor is not detail). It raises tails and quiet notes without touching the peaks."""
    y = _two(x)
    det = _ctrl_env(_detect(y, sr), sr, float(p['attack_ms']), float(p['release_ms']))
    lvl = _db(det)
    under = float(p['threshold_db']) - lvl
    lift = np.clip(under, 0.0, None) * (1.0 - 1.0 / float(p['ratio']))
    lift = np.minimum(lift, float(p['max_gain_db']))
    lift = np.where(lvl < float(p['floor_db']), 0.0, lift)
    lift = _gain_follow(lift, sr, float(p['attack_ms']), float(p['release_ms']), reduce='mean')   # falls fast under a loud note, returns slowly
    return _apply_gain_db(y, np.clip(lift, 0.0, float(p['max_gain_db'])))


# ------------------------------------------------------------------------------------------------------- stereo and spectrum
def band_width(x, sr, p, rng):
    """A stereo field that depends on frequency: below `mono_below_hz` the signal is summed to the centre (a low end that is the same in
    both ears), above it the side signal is scaled by `width` (1 leaves it, 1.5 widens, 0 is mono). Zero-phase crossover."""
    y = _two(x)
    if y.ndim != 2 or y.shape[1] < 2:
        return y
    f = min(float(p['mono_below_hz']), sr * 0.4)
    sos = signal.butter(2, f / (sr / 2), 'low', output='sos')
    low = signal.sosfiltfilt(sos, y, axis=0)
    high = y - low
    mid_l = 0.5 * (low[:, 0] + low[:, 1])
    mid, side = 0.5 * (high[:, 0] + high[:, 1]), 0.5 * (high[:, 0] - high[:, 1]) * float(p['width'])
    out = np.stack([mid_l + mid + side, mid_l + mid - side], axis=1)
    return out.astype(np.float32)


def tilt_eq(x, sr, p, rng):
    """A spectral tilt about `pivot_hz`: +`tilt_db` is brighter (the highs up by half of it and the lows down by half), -`tilt_db` is darker."""
    y = _two(x)
    sos = signal.butter(1, min(float(p['pivot_hz']), sr * 0.4) / (sr / 2), 'low', output='sos')
    low = signal.sosfiltfilt(sos, y, axis=0)
    high = y - low
    t = float(p['tilt_db']) / 2.0
    return (low * 10.0 ** (-t / 20.0) + high * 10.0 ** (t / 20.0)).astype(np.float32)


def freq_shift(x, sr, p, rng):
    """A frequency shifter (not a pitch shifter): every partial moves by `shift_hz`, so harmonic sounds turn inharmonic and a slight shift
    thickens a pad. With `spread` the two channels are shifted in opposite directions (a wide, slowly beating chorus)."""
    y = _two(x)
    ch = y if y.ndim == 2 else y[:, None]
    t = np.arange(len(ch)) / sr
    out = np.empty_like(ch)
    for c in range(ch.shape[1]):
        sign = 1.0 if (c % 2 == 0 or float(p['spread']) < 0.5) else -1.0
        a = signal.hilbert(ch[:, c])
        out[:, c] = np.real(a * np.exp(2j * math.pi * sign * float(p['shift_hz']) * t))
    return out.astype(np.float32) if y.ndim == 2 else out[:, 0].astype(np.float32)


def resonator_bank(x, sr, p, rng):
    """A bank of narrow resonances tuned to the piece's own notes (`pitches`, MIDI numbers) and their first `partials` harmonics: the air and
    the noise in a stem ring in the key, so a bed hums the chord instead of fighting it. `level_db` is the resonated signal against the stem."""
    y = _two(x)
    ch = y if y.ndim == 2 else y[:, None]
    acc = np.zeros_like(ch)
    q = float(p['q'])
    for midi in p['pitches']:
        f0 = 440.0 * 2.0 ** ((float(midi) - 69.0) / 12.0)
        for k in range(1, int(p['partials']) + 1):
            f = f0 * k
            if f < sr * 0.45:
                b, a = signal.iirpeak(f / (sr / 2), q)
                acc += signal.lfilter(b, a, ch, axis=0).astype(np.float32) / (k ** 0.5)
    rms_in, rms_acc = float(np.sqrt(np.mean(ch ** 2))), float(np.sqrt(np.mean(acc ** 2)))
    if rms_acc > 1e-9 and rms_in > 1e-9:
        acc = acc * (rms_in / rms_acc) * 10.0 ** (float(p['level_db']) / 20.0)
    out = ch + acc
    return out.astype(np.float32) if y.ndim == 2 else out[:, 0].astype(np.float32)


def ping_delay(x, sr, p, rng):
    """An echo that stays out of the way: repeats every `time_ms`, each `feedback` as loud as the last, filtered between `hp_hz` and
    `lp_hz`, optionally ping-ponged between the channels (`spread`), and ducked by the dry signal (`duck_db`) so the echoes come up in the
    gaps. The result is the dry plus the echoes (`wet_db` under the stem)."""
    y = _two(x)
    ch = y if y.ndim == 2 else np.repeat(y[:, None], 2, axis=1)
    n = len(ch)
    d = max(1, int(round(float(p['time_ms']) * sr / 1000.0)))
    fb = float(p['feedback'])
    wet = np.zeros_like(ch)
    k, g = 1, fb ** 0.0
    while k * d < n and k <= 48:
        g = fb ** (k - 1)
        if g < 1e-3:
            break
        tap = ch[: n - k * d]
        if float(p['spread']) >= 0.5 and k % 2 == 1:
            tap = tap[:, ::-1]
        wet[k * d:] += g * tap
        k += 1
    hp, lp = float(p['hp_hz']), float(p['lp_hz'])
    if hp > 20.0:
        wet = signal.sosfilt(signal.butter(2, hp / (sr / 2), 'high', output='sos'), wet, axis=0)
    if lp < sr * 0.45:
        wet = signal.sosfilt(signal.butter(2, lp / (sr / 2), 'low', output='sos'), wet, axis=0)
    duck = float(p['duck_db'])
    if duck > 0.1:
        env = _ctrl_env(np.max(np.abs(ch), axis=1), sr, 8.0, 220.0)
        ref = max(float(np.percentile(env, 90)), 1e-6)
        g_db = -duck * np.clip(env / ref, 0.0, 1.0)
        wet = wet * (10.0 ** (g_db / 20.0))[:, None]
    out = ch + wet * 10.0 ** (float(p['wet_db']) / 20.0)
    return out.astype(np.float32) if y.ndim == 2 else out.mean(axis=1).astype(np.float32)
