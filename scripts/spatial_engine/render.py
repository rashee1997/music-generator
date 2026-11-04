# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""render.py - mix placed stems into one discrete multichannel bus, and write it.

    audio = render_stems(stems, 'itu_bs2051_system_j', specs={'cello': dict(role='melody', azimuth=-20, elevation=10)})
    write('out/master_7_1_4.wav', audio, sr)

Every number - the speaker ring, the crossover, the low-frequency send, the decorrelation, the stereo law - comes from
the layout and target presets. This module only routes signals.

A track's own stem is placed at its track-preset position (azimuth, elevation); a low-frequency role is sent to the
low-frequency channel and its mains are high-passed, so one low end has one owner. Everything else keeps its main image;
a mix preset may add a complement send, which is why `lfe_sends` is separate from `lfe_roles`.
"""
import numpy as np
import soundfile as sf

from . import bass
from . import config
from . import decorrelate
from . import downmix
from . import pan


def specs_from_score(score):
    """Each track's position, from the score and its instrument presets (the same specs the stereo mix uses)."""
    import mixer
    out = {}
    for tr in score.get('tracks', []):
        spec = mixer.default_spec(tr)
        out[tr.get('name', 'track')] = spec
    for name, over in (score.get('mix', {}).get('tracks') or {}).items():
        if name in out:
            out[name].update(over)
    return out


def _mono(y):
    y = np.asarray(y, dtype=np.float64)
    return y if y.ndim == 1 else y.mean(axis=1)


def render_stems(stems, layout_name, target_name=None, score=None, specs=None, sr=44100):
    """Place every stem on the layout and return (N, channels) float64 in the layout's channel order.

    `specs` (name -> dict with role/azimuth/elevation/gain_db) defaults to the score's own track specs.
    Stems the specs do not mention are placed at the layout's first speaker and are still audible.
    """
    if specs is None:
        specs = specs_from_score(score) if score else {}
    names = config.channel_names(layout_name)
    spk = config.speakers(layout_name)
    lfe_spk = config.lfe_speaker(layout_name)
    cfg = config.lfe_cfg(layout_name, target_name)
    roles = set(cfg.get('roles') or [])
    decorated = (config.layout(layout_name).get('decorrelation') or {})
    n = max((len(_mono(v)) for v in stems.values()), default=0)
    mix = {name: np.zeros(n, dtype=np.float64) for name in names}
    sends = []
    for name, y in stems.items():
        spec = dict(specs.get(name) or {})
        x = _mono(y)
        role = str(spec.get('role') or '')
        gain = float(10.0 ** (float(spec.get('gain_db', 0.0)) / 20.0))
        x = x * gain
        az = float(spec.get('azimuth', 0.0))
        el = float(spec.get('elevation', 0.0))
        if role in roles and cfg.get('lowpass_hz'):
            sends.append(x)
            mains = bass.highpass(x, sr, float(cfg['lowpass_hz']))
        else:
            mains = x
        layer = spec.get('lfe_send_db')
        if layer is not None and cfg.get('lowpass_hz'):      # an optional complement send for a full-range track
            sends.append(x * bass.send_gain(float(layer)))
        for sp_name, g in pan.gains(az, el, spk).items():
            if g:
                mix[sp_name][:len(mains)] += mains * g
    if cfg.get('lowpass_hz') and sends and lfe_spk:
        lfe = bass.lfe_bus(sends, sr, cfg)
        mix[lfe_spk['name']][:len(lfe)] += lfe
    mix = decorrelate.bus(mix, decorated, sr)
    probs = config.problems(layout_name)
    if probs:                                      # data is broken: say so instead of writing a crooked file
        raise ValueError('layout "' + layout_name + '" is not usable: ' + '; '.join(probs))
    return np.stack([mix[name] for name in names], axis=1)


def write(path, audio, sr=44100, subtype='PCM_24'):
    """Write a multichannel WAV in the layout's channel order, with its peak left where the ceiling policy says."""
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    sf.write(path, np.asarray(audio, dtype=np.float32), int(sr), subtype=subtype)
    return path


def fold_to_stereo(audio, layout_name):
    return downmix.fold(audio, layout_name)
