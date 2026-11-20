# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""master.py - the finishing stage of a discrete multichannel deliverable.

A multichannel file cannot go through the stereo master chain: its mid/side width, its mono fold and its brickwall
limiter are two-channel operations. What a multichannel master needs is the same things a listener needs - one
loudness for the whole programme, the format's own true-peak ceiling, and clean fades - so this module does exactly
those three, and nothing that would change the image:

  * loudness is measured on the layout's own two-channel fold (downmix.py, BS.775 coefficients), because that is the
    programme a listener hears when the room is not set up for the format;
  * one scalar gain reaches the target, so every channel keeps its relationship to every other channel;
  * the true peak is checked per channel against the target's ceiling, and the programme is trimmed if any channel
    would overshoot. A target preset may switch on a linked limiter (`"limiter": {"enabled": true, ...}`): one gain
    curve for every channel, so loud material can reach its loudness target without the image moving. Without that
    block the programme is only trimmed, as it always was.

The target loudness and the fade come from the same master block the stereo path uses; the ceiling comes from the
target preset.
"""
import numpy as np

from . import downmix


def fold_lufs(audio, layout_name):
    """Integrated loudness of the BS.775 fold of a multichannel programme."""
    import mixer
    return mixer.lufs(downmix.fold(audio, layout_name))


def channel_peaks(audio, sr):
    """True peak per channel, in the layout's order (dBTP)."""
    import dsp
    y = np.asarray(audio, dtype=np.float64)
    return [float(dsp.true_peak_db(y[:, i], sr)) for i in range(y.shape[1])]


def _dc_block(audio, layout_name, sr, hz=24.0):
    """Remove sub-audio content from every main channel; LFE keeps its band.

    The stereo master chain starts with a 24 Hz high-pass (mixer.master_chain). This path had no filter of any kind, so a
    residual offset or very slow drift in the stems reached the deliverable unfiltered, scaled by one gain. Measured on a
    7.1 delivery: a 1 s block mean wandered 0.015 FS in FL (limit 0.001) while every stem passed the same row at
    0.0007 or below. LFE is skipped: its band is 20-120 Hz by definition.
    """
    from scipy.signal import butter, sosfilt
    from . import config
    try:
        names = list(config.channel_names(layout_name))
    except Exception:
        names = []
    out = np.array(audio, dtype=np.float64, copy=True)
    sos = butter(2, hz, btype='highpass', fs=sr, output='sos')
    for i in range(out.shape[1]):
        if i < len(names) and names[i] == 'LFE':
            continue
        out[:, i] = sosfilt(sos, out[:, i])
    return out


def limit(audio, sr, ceiling_db, cfg):
    """A linked true-peak limiter for any channel count: one gain curve for every channel, so the image does not move.

    The gain is computed from the oversampled peak across all channels, held ahead of each peak for `lookahead_ms`
    (a sliding minimum, then a moving average of the same length, so the curve is already down when the peak arrives
    and has no corner), and let go with a `release_ms` time constant. Offline, so nothing is delayed: the window is
    centred on the sample.

    cfg: lookahead_ms, release_ms, oversample. Returns (limited, deepest gain reduction in dB as a positive number).
    """
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    from scipy.signal import resample_poly
    y = np.asarray(audio, dtype=np.float64)
    over = max(1, int(cfg.get('oversample', 4)))
    ceil_lin = 10.0 ** (float(ceiling_db) / 20.0)
    peak = np.zeros(len(y))
    for ch in range(y.shape[1]):                    # one channel at a time: twelve oversampled channels at once is GBs
        up = np.abs(resample_poly(y[:, ch], over, 1)) if over > 1 else np.abs(y[:, ch])
        np.maximum(peak, up[:len(y) * over].reshape(len(y), over).max(axis=1), out=peak)
    need = np.minimum(1.0, ceil_lin / np.maximum(peak, 1e-12))
    if float(need.min()) >= 1.0:
        return np.asarray(audio, dtype=np.float32), 0.0
    # release: the attenuation a = -ln(gain) falls by a factor k per sample unless a new peak asks for more.
    # a_rel[n] = max_j<=n a[j] k^(n-j), computed in the log domain as a running maximum (no loop, no overflow).
    a = -np.log(need)
    k = np.exp(-1.0 / max(1.0, float(cfg['release_ms']) * sr / 1000.0))
    idx = np.arange(len(a), dtype=np.float64)
    with np.errstate(divide='ignore'):
        a_rel = np.exp(np.maximum.accumulate(np.log(a) - idx * np.log(k)) + idx * np.log(k))
    gain = np.exp(-a_rel)
    win = max(3, int(float(cfg['lookahead_ms']) * sr / 1000.0) | 1)
    gain = uniform_filter1d(minimum_filter1d(gain, size=win, mode='nearest'), size=win, mode='nearest')
    out = (y * gain[:, None]).astype(np.float32)
    return out, float(-20.0 * np.log10(max(float(gain.min()), 1e-12)))


def programme_lufs(audio, layout_name, sr, target):
    """The loudness the target preset asks for: BS.1770 with the layout's channel weights (`"loudness":
    {"method": "bs1770_layout"}`), or the loudness of the two-channel fold (the default, and what every 7.1 file was
    levelled with before the method was data)."""
    method = str(((target or {}).get('loudness') or {}).get('method') or 'stereo_fold')
    if method == 'bs1770_layout':
        import loudness
        return loudness.layout_lufs(audio, layout_name, sr), method
    if method != 'stereo_fold':
        raise ValueError(f'loudness method "{method}" is not one of bs1770_layout, stereo_fold')
    return fold_lufs(audio, layout_name), method


REPORT = {}          # the last multichannel master: target, method, loudness reached, limiter depth (for the gate)


def master(audio, score, target, sr=44100):
    """Trim, level, limit and fade a multichannel programme for delivery. Returns float32 (N, channels)."""
    import mixer
    target = dict(target or {})
    layout_name = target.get('layout')
    if not layout_name:
        raise ValueError('a spatial deliverable needs a layout in its target preset')
    ceiling = float(target.get('true_peak_dbtp', -1.5))
    score = score or {}
    try:
        cfg = mixer._master_cfg(dict(score.get('master') or {}), mixer._mix())
        lufs_target = float(cfg.get('lufs', -14.0))
        fade_out = float(cfg.get('fade_out', 0.6))
    except Exception:                     # a bare score with no context: the engine's own delivery target
        lufs_target, fade_out = -14.0, 0.6
    if (target.get('loudness') or {}).get('target_lufs') is not None:      # a format with a loudness of its own
        lufs_target = float(target['loudness']['target_lufs'])
    y = mixer.trim_tail(np.asarray(audio, dtype=np.float32), sr)
    y = _dc_block(y, layout_name, sr).astype(np.float32)
    measured, method = programme_lufs(y, layout_name, sr, target)
    gain_db = lufs_target - measured
    lim = target.get('limiter') or {}
    depth = 0.0
    if lim.get('enabled'):
        # The limiter is in the loop: limiting lowers the loudness a little, so the gain is corrected until the
        # limited programme is at the target. If that would take more reduction than the preset allows, the
        # programme keeps its dynamics and comes out under the target, and the report says by how much.
        max_gr = float(lim['max_reduction_db'])
        out = y
        for _ in range(int(lim.get('max_iterations', 4))):
            out, depth = limit(y * np.float32(10.0 ** (gain_db / 20.0)), sr, ceiling - float(lim.get('margin_db', 0.0)), lim)
            if depth > max_gr:
                gain_db -= depth - max_gr
                continue
            err = lufs_target - programme_lufs(out, layout_name, sr, target)[0]
            if abs(err) < float(lim.get('tolerance_lu', 0.2)):
                break
            gain_db += err
        over = max(channel_peaks(out, sr)) - ceiling
        if over > 0.0:                    # last safety, as on the stereo master
            out = out * np.float32(10.0 ** (-(over + 0.05) / 20.0))
    else:
        for _ in range(6):
            out = y * np.float32(10.0 ** (gain_db / 20.0))
            over = max(channel_peaks(out, sr)) - ceiling
            if over <= 0.0:
                break
            gain_db -= over + 0.05            # one scalar trim keeps the image; loop until every channel is under
    reached = programme_lufs(out, layout_name, sr, target)[0]
    REPORT.clear()
    REPORT.update(layout=layout_name, method=method, target_lufs=lufs_target, reached_lufs=float(reached),
                  limiter=bool(lim.get('enabled')), limiter_depth_db=float(depth), ceiling_dbtp=ceiling)
    return mixer.fades(out, sr, fout=fade_out)
