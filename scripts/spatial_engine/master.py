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
    would overshoot. No limiter is used here: a broadband limiter across twelve channels is not a drop-in for the
    stereo one, and inventing one silently would change the mix.

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


def master(audio, score, target, sr=44100):
    """Trim, gain and fade a multichannel programme for delivery. Returns float32 (N, channels)."""
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
    y = mixer.trim_tail(np.asarray(audio, dtype=np.float32), sr)
    y = _dc_block(y, layout_name, sr).astype(np.float32)
    gain_db = lufs_target - fold_lufs(y, layout_name)
    for _ in range(6):
        out = y * np.float32(10.0 ** (gain_db / 20.0))
        over = max(channel_peaks(out, sr)) - ceiling
        if over <= 0.0:
            break
        gain_db -= over + 0.05            # one scalar trim keeps the image; loop until every channel is under
    return mixer.fades(out, sr, fout=fade_out)
