"""family_dsp.py - treatments a family adds to a rendered stem: bow or breath noise, brass flare, a struck onset's snap.

Each one is data in references/data/presets/families/families.json (or the preset's own block of the same name), and runs only
for a preset or track that declares a family or the block. A stem of a preset that declares neither is returned untouched.

  noise  a band-passed noise (bow: friction 2-6 kHz; breath: air 1-4 kHz) that follows the stem's own envelope, level_db under it
  flare  brass spectral enrichment: above `onset_velocity` of the stem's peak envelope, a saturated high band is blended in, so a
         loud note is a different spectrum and not only a louder one (Campbell; Stevenson and Campbell, starting values)
  snap   the front of every onset sharpened (dsp.transient_shaper): the stick or mallet bite of a struck part
  velocity_brightness  a score-driven per-note brightness law. A SoundFont has one sample layer, so a hard note is only a louder copy of a
         soft one (measured: brightness-to-velocity correlation between -0.16 and 0.17 on cello, violin, flute, horn and piano lines).
         The brightness of an instrument is a number of harmonics, not a fixed frequency, so each note gets a low-pass whose
         cutoff is the h-th harmonic of its own fundamental, with h following its written velocity:
             f0(p) = 440 * 2 ** ((p - 69) / 12)
             h(v)  = h_lo * (h_hi / h_lo) ** (v ** gamma),             v = velocity / 127
             fc    = clip(f0 * h(v) * 2 ** N(0, jitter_oct), fc_min, fc_max)
         and, because a sample that holds no overtones cannot be made brighter by filtering (a GM horn's attack centroid measured
         334 Hz), each note is first driven through a saturator whose drive follows the same velocity, so a hard note gains harmonics:
             y' = tanh(D(v) * y / s) * s / D(v),        D(v) = 1 + drive_k * v ** gamma,    s = the stem's peak
         The jitter is the timbre difference between two takes of one note that a round-robin set holds. The spectral centroid of
         brass, winds and strings rises with playing level (Gilbert and Myers; Campbell); the exact curve is a starting value.
  velocity_attack  a soft note rises slower than a hard one:
             ramp_ms(v) = ms_hard + (ms_soft - ms_hard) * (1 - v / 127) ** power
"""
import numpy as np
from scipy import signal

import dsp
import families

NOISE_BANDS = {'bow': (2000.0, 6000.0), 'breath': (1000.0, 4000.0)}     # starting values


def _env(y, sr, ms=25.0):
    m = np.abs(y).mean(axis=1) if y.ndim == 2 else np.abs(y)
    n = max(1, int(sr * ms / 1000.0))
    return np.convolve(m, np.ones(n) / n, mode='same')


def noise_layer(y, sr, kind, level_db, seed=0):
    if kind not in NOISE_BANDS:
        raise ValueError(f'noise kind "{kind}" is not one of {sorted(NOISE_BANDS)}')
    lo, hi = NOISE_BANDS[kind]
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    sos = signal.butter(2, [lo / (sr / 2), min(hi, sr * 0.45) / (sr / 2)], 'band', output='sos')
    out = np.array(y, dtype=np.float32, copy=True)
    e = _env(y, sr)
    for c in range(out.shape[1]):
        nz = signal.sosfilt(sos, rng.normal(0.0, 1.0, len(out))).astype(np.float32)
        out[:, c] += nz * e.astype(np.float32) * float(10 ** (level_db / 20.0))
    return out


def brass_flare(y, sr, onset_velocity, gain_db_per_unit, corner_hz):
    out = np.array(y, dtype=np.float32, copy=True)
    e = _env(y, sr, 40.0)
    pk = float(e.max())
    if pk <= 1e-9:
        return out
    drive = np.clip((e / pk - float(onset_velocity)) / max(1e-6, 1.0 - float(onset_velocity)), 0.0, 1.0).astype(np.float32)
    sos = signal.butter(2, corner_hz / (sr / 2), 'high', output='sos')
    amt = float(10 ** (gain_db_per_unit / 20.0)) - 1.0
    for c in range(out.shape[1]):
        hf = signal.sosfilt(sos, out[:, c]).astype(np.float32)
        out[:, c] += amt * drive * np.tanh(4.0 * hf) / 4.0
    return out


def _unit_velocity(v):
    """A note's velocity on 0..1 whether the score wrote 0..1 or 1..127."""
    v = float(v)
    return float(np.clip(v / 127.0 if v > 1.0 else v, 0.0, 1.0))


def _note_groups(events, window_s=0.03):
    """[(onset_s, end_s, mean unit velocity)]: notes that start within `window_s` of each other are one chord, one cutoff."""
    ev = sorted(((float(e['t']), float(e['t']) + float(e.get('dur', e.get('d', 0.5))), _unit_velocity(e['v']), float(e.get('p', 69)))
                 for e in events if 'v' in e), key=lambda r: r[0])
    out = []
    for t, end, v, p in ev:
        if out and t - out[-1][0] <= window_s:
            a, b, vs, ps = out[-1]
            out[-1] = (a, max(b, end), vs + [v], ps + [p])
        else:
            out.append((t, end, [v], [p]))
    return [(a, b, float(np.mean(vs)), float(np.min(ps))) for a, b, vs, ps in out]


def cutoff_for(velocity, midi_pitch, h_lo, h_hi, gamma=1.0, fc_min=400.0, fc_max=12000.0):
    """The cutoff (Hz) of one note: the h(v)-th harmonic of its fundamental, kept between fc_min and fc_max (the law is in the module docstring)."""
    v = float(np.clip(velocity, 0.0, 1.0))
    f0 = 440.0 * 2.0 ** ((float(midi_pitch) - 69.0) / 12.0)
    h = float(h_lo) * (float(h_hi) / float(h_lo)) ** (v ** float(gamma))
    return float(np.clip(f0 * h, fc_min, fc_max))


def velocity_brightness(y, sr, events, h_lo, h_hi, gamma=1.0, jitter_oct=0.0, fc_min=400.0, fc_max=12000.0, drive_k=0.0, ramp_ms=15.0,
                    hold_s=0.3, seed=0, bank=9):
    """The stem with each note's brightness following its written velocity (the law is in the module docstring).

    The cutoff curve is piecewise constant per note (a note holds its cutoff until the next one starts, or `hold_s` after its end),
    smoothed over `ramp_ms`, and applied by crossfading a bank of `bank` log-spaced second-order low-passes between `fc_min / 1.4`
    and `fc_max`; above `fc_max` the original passes. Level-compensated over the whole stem, so the pattern level does not move.
    """
    y = np.asarray(y, dtype=np.float32)
    groups = _note_groups(events)
    if len(y) == 0 or not groups or float(fc_max) <= float(fc_min) or float(h_hi) <= float(h_lo):
        return y
    rng = np.random.default_rng((int(seed) ^ 0x5EED) & 0xFFFFFFFF)
    n = len(y)
    top = float(np.log2(fc_max))
    curve = np.full(n, top, dtype=np.float64)
    drive = np.ones(n, dtype=np.float64)
    for k, (t0, t1, v, pmin) in enumerate(groups):
        nxt = groups[k + 1][0] if k + 1 < len(groups) else np.inf
        i0 = int(max(0.0, t0) * sr)
        i1 = int(min(n / sr, min(nxt, t1 + hold_s)) * sr)
        L = np.log2(cutoff_for(v, pmin, h_lo, h_hi, gamma, fc_min, fc_max)) + (rng.normal(0.0, jitter_oct) if jitter_oct > 0 else 0.0)
        if i1 > i0:
            curve[i0:i1] = min(L, top)
            drive[i0:i1] = 1.0 + float(drive_k) * float(np.clip(v, 0.0, 1.0)) ** float(gamma)
    w = max(1, int(sr * ramp_ms / 1000.0))
    smooth = lambda c: np.convolve(np.pad(c, (w, w), mode='edge'), np.ones(2 * w + 1) / (2 * w + 1), mode='valid')[:n]
    curve = smooth(curve)
    if drive_k > 0:
        d = smooth(drive).astype(np.float32)[:, None]
        pk = max(float(np.max(np.abs(y))), 1e-6)
        sat = (np.tanh(d * y / pk) * pk / d).astype(np.float32)
        # a saturator compresses its loudest peaks hardest, which would flatten the very dynamics this law exists to restore
        # (measured: a 14 dB loud-over-soft gap came out as -2.4 dB). The level follows the input: the saturated copy is
        # scaled back, moment by moment, to the short-time level of the dry stem, so only the timbre changes.
        e_in, e_out = _env(y, sr, 40.0), _env(sat, sr, 40.0)
        g = np.clip(e_in / np.maximum(e_out, 1e-7), 0.05, 20.0)
        g = np.convolve(g, np.ones(int(sr * 0.02)) / int(sr * 0.02), mode='same').astype(np.float32)[:, None]
        y = (sat * g).astype(np.float32)
    lo = float(np.log2(float(fc_min) / 1.4))
    levels = np.linspace(lo, top, int(bank))
    outs = []
    for L in levels[:-1]:
        sos = signal.butter(2, min(2.0 ** L, sr * 0.45) / (sr / 2), 'low', output='sos')
        outs.append(signal.sosfilt(sos, y, axis=0).astype(np.float32))
    outs.append(y)
    pos = np.clip((curve - lo) / (top - lo) * (len(levels) - 1), 0.0, len(levels) - 1 - 1e-9)
    idx = pos.astype(int)
    frac = (pos - idx).astype(np.float32)[:, None]
    stack = np.stack(outs)                                   # (bank, n, channels)
    res = stack[idx, np.arange(n)] * (1.0 - frac) + stack[idx + 1, np.arange(n)] * frac
    rin, rout = float(np.sqrt(np.mean(y ** 2))), float(np.sqrt(np.mean(res ** 2)))
    return (res * (rin / rout)).astype(np.float32) if rout > 1e-9 and rin > 1e-9 else res.astype(np.float32)


def velocity_attack(y, sr, events, ms_soft, ms_hard=3.0, power=1.5):
    """Each onset gets a raised-cosine rise whose length grows as the note gets softer (dsp.soften_onsets, per onset)."""
    groups = _note_groups(events)
    if not groups:
        return y
    times = [g[0] for g in groups]
    ms = [float(ms_hard) + (float(ms_soft) - float(ms_hard)) * (1.0 - g[2]) ** float(power) for g in groups]
    return dsp.soften_onsets(y, sr=sr, times=times, ms=ms, skip_sounding=True)


def apply(stem, inst_cfg, tr, sr, seed=0, events=None):
    """The stem after the family's treatments; the same array when nothing is declared."""
    beh = families.effective(inst_cfg, tr)
    if not beh:
        return stem
    y = dsp.to_2d(stem).astype(np.float32)
    if beh.get('snap'):
        y = dsp.transient_shaper(y, sr=sr, attack=float(beh['snap']['attack']), sustain=float(beh['snap']['sustain']))
    if beh.get('flare'):
        f = beh['flare']
        y = brass_flare(y, sr, f['onset_velocity'], f['gain_db_per_unit'], f['corner_hz'])
    # the older opt-in `velocity_timbre` block of a preset or track (note bands and zones, render_natural) is a different
    # implementation of the same idea: where a part declares it, it wins and the family law stays out, so the two never stack
    legacy_bands = bool((tr or {}).get('velocity_timbre') or (inst_cfg or {}).get('velocity_timbre'))
    if events:
        if beh.get('velocity_attack'):
            a = beh['velocity_attack']
            y = velocity_attack(y, sr, events, a['ms_soft'], a.get('ms_hard', 3.0), a.get('power', 1.5))
        if beh.get('velocity_brightness') and not legacy_bands:
            t = beh['velocity_brightness']
            y = velocity_brightness(y, sr, events, t['h_lo'], t['h_hi'], t.get('gamma', 1.0), t.get('jitter_oct', 0.0),
                                t.get('fc_min', 400.0), t.get('fc_max', 12000.0), t.get('drive_k', 0.0), seed=seed)
    if beh.get('noise'):
        y = noise_layer(y, sr, beh['noise']['kind'], beh['noise']['level_db'], seed)
    return y
