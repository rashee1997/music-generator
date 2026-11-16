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
import contextlib

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


# ---------------------------------------------------------------------------------------------
# The discrete deliverable: mixer.mix_stems hands every finished track signal to a LayoutBus.
# ---------------------------------------------------------------------------------------------

def _mono_fold(y):
    """One channel from a finished stereo track: the linear mid, 0.5 * (L + R).

    A loudspeaker gets one feed, so a stereo track has to become mono first. The mid is what every downmixer uses and
    it leaves the track's own spectrum alone. (An earlier energy fold, sign(L + R) * sqrt((L^2 + R^2) / 2), held a
    hard-panned track at full level, but it squared off the waveform as soon as L and R differed: measured on one 7.1
    delivery, stems that all sat at -56 dB or below relative 15-22 kHz came out of the fold at -20 dB, and those
    broadband edges are what the click and aliasing rows counted.)
    """
    y = np.asarray(y, dtype=np.float64)
    if y.ndim == 1:
        return y
    if y.shape[1] == 1:
        return y[:, 0]
    return 0.5 * (y[:, 0] + y[:, 1])


PAN_STRIDE = 16


class LayoutBus:
    """The summing target for a discrete deliverable.

    mixer.mix_stems owns every per-track decision (gain staging, EQ, dynamics, ducking, the reverb send); this object
    only places the finished signals on the layout's loudspeakers, sends the low-frequency roles to the low-frequency
    channel, spreads the shared reverb return by the layout's own data, and decorrelates the surround beds.

    The interface is the one `bus` in mix_stems expects: add(name, signal, spec), add_reverb(signal), result().
    """
    places_tracks = True               # with immersive on, the mixer hands tracks over unplaced

    def __init__(self, layout_name, target_name=None, sr=44100):
        problems = config.problems(layout_name)
        if problems:
            raise ValueError('layout "' + layout_name + '" is not usable: ' + '; '.join(problems))
        self.layout_name = layout_name
        self.target_name = target_name
        self.sr = int(sr)
        layout = config.layout(layout_name)
        self.names = config.channel_names(layout_name)
        self.speakers = config.speakers(layout_name)
        self.lfe_speaker = config.lfe_speaker(layout_name)
        self.lfe = config.lfe_cfg(layout_name, target_name)
        self.roles = set(self.lfe.get('roles') or [])
        self.reverb = layout.get('reverb') or {}
        self.decorrelation = layout.get('decorrelation') or {}
        self.parts = {name: [] for name in self.names}
        self.low_sends = []
        self.room = None
        self.imm, self.score = None, None      # set by the mixer when the piece is immersive

    def attach_room(self, room_bus):
        """Give the layout a room: an ambisonic bus (hoa.HoaBus, room_only) that hears every track this bus is
        handed and returns its reflections and late field on the loudspeakers. The direct sound stays VBAP."""
        self.room = room_bus

    def _add(self, channel, signal):
        signal = np.asarray(signal, dtype=np.float64)
        if signal.size:
            self.parts[channel].append(signal)

    def add(self, name, y, spec):
        """Place one finished track: mains by VBAP, low-frequency roles through the low-frequency channel."""
        mono = _mono_fold(y)
        if mono.size == 0:
            return
        spec = dict(spec or {})
        if self.room is not None:
            self.room.add(name, y, spec)
        role = str(spec.get('role') or '')
        cutoff = self.lfe.get('lowpass_hz')
        if role in self.roles and cutoff:
            self.low_sends.append(mono)
            mains = bass.highpass(mono, self.sr, float(cutoff))
        else:
            mains = mono
        extra = spec.get('lfe_send_db')            # an optional complement send for a full-range track
        if extra is not None and cutoff:
            self.low_sends.append(mono * bass.send_gain(float(extra)))
        # The mixer keeps a track's place in `spatial`; a flat azimuth/elevation is still accepted for a caller
        # that hands raw specs. Reading only the flat pair put every track at 0 deg (front centre).
        sp = spec.get('spatial') or {}
        azimuth = float(sp.get('azimuth', spec.get('azimuth', 0.0)))
        elevation = float(sp.get('elevation', spec.get('elevation', 0.0)))
        path = None
        if self.imm and sp:                    # an immersive piece: the role's height, and the track's own path
            import mixer
            from . import trajectory
            azimuth, elevation, dist = mixer.place_of(spec, self.imm)
            traj = sp.get('trajectory')
            path = trajectory.path(traj, azimuth, elevation, dist, len(mains), self.sr, self.score)
            if path is not None and trajectory.is_anchor(traj, role):
                path = trajectory.anchor(path, azimuth, elevation, dist,
                                         float(self.imm.get('anchor_max_span_deg', 6.0)))
        if path is None:
            for speaker, gain in pan.gains(azimuth, elevation, self.speakers).items():
                if gain:
                    self._add(speaker, mains * gain)
            return
        # A moving source: VBAP gains every PAN_STRIDE control points (about 23 ms), linear in between, power kept.
        # shortcut: level follows distance but there is no Doppler shift on loudspeakers; the room bus has it.
        idx = np.unique(np.append(np.arange(0, len(path), PAN_STRIDE), len(path) - 1))
        table = np.zeros((len(idx), len(self.speakers)))
        col = {s['name']: j for j, s in enumerate(self.speakers)}
        for i, k in enumerate(idx):
            for speaker, gain in pan.gains(path[k, 0], path[k, 1], self.speakers).items():
                table[i, col[speaker]] = gain
        at = np.arange(len(mains)) / float(trajectory.HOP)
        g = np.stack([np.interp(at, idx, table[:, j]) for j in range(table.shape[1])], axis=1)
        g /= np.maximum(np.sqrt(np.sum(g * g, axis=1, keepdims=True)), 1e-9)
        level = max(dist, 1.0) / np.maximum(trajectory.at_samples(path, 2, 0, len(mains)), 1.0)
        for speaker, j in col.items():
            if table[:, j].any():
                self._add(speaker, mains * g[:, j] * level)

    def add_reverb(self, ret):
        """Spread the shared reverb return: the layout says how loud it sits in front, around and above."""
        if ret is None or not len(ret) or not self.reverb:
            return
        mono = _mono_fold(ret)
        front_max = float(self.reverb.get('front_azimuth_max'))
        gains = {'front': bass.send_gain(self.reverb.get('front_db')),
                 'surround': bass.send_gain(self.reverb.get('surround_db')),
                 'height': bass.send_gain(self.reverb.get('height_db'))}
        for speaker in self.speakers:
            if float(speaker.get('elevation', 0.0)) > 0.0:
                group = 'height'
            elif abs(float(speaker.get('azimuth', 0.0))) <= front_max:
                group = 'front'
            else:
                group = 'surround'
            self._add(speaker['name'], mono * gains[group])

    def result(self):
        """(N, channels) float64 in the layout's channel order, with the low-frequency send applied."""
        n = max((len(s) for parts in self.parts.values() for s in parts), default=0)
        mix = {name: np.zeros(n, dtype=np.float64) for name in self.names}
        for name, parts in self.parts.items():
            for signal in parts:
                mix[name][:len(signal)] += signal
        if self.room is not None and n:
            room = self.room.result()
            for i, speaker in enumerate(self.speakers):
                m = min(n, len(room))
                mix[speaker['name']][:m] += room[:m, i]
        if self.lfe_speaker is not None and self.low_sends:
            low = bass.lfe_bus(self.low_sends, self.sr, self.lfe)
            mix[self.lfe_speaker['name']][:len(low)] += low
        # The low-frequency channel is never decorrelated: it is not a spatial channel, and phase-scrambling a sub
        # only smears it. (decorrelate.bus treats `names` as the channels to leave alone.)
        skip = [self.lfe_speaker['name']] if self.lfe_speaker else None
        mix = decorrelate.bus(mix, self.decorrelation, self.sr, names=skip)
        return np.stack([mix[name] for name in self.names], axis=1)


def spatial_mix(score, stems, target_name, sr=44100, ctx=None):
    """Mix a piece into one discrete target: the whole mixer, a different summing bus."""
    import mixer
    target = config.target(target_name) or {}
    layout_name = target.get('layout')
    if not layout_name:
        raise ValueError(f'deliverable "{target_name}" has no layout: it is not a spatial format')
    bus = LayoutBus(layout_name, target_name, sr)
    mixer.mix_stems(score, stems, sr, ctx, bus=bus)
    return bus.result()


@contextlib.contextmanager
def _immersive(score, ctx=None):
    """The piece's mix context with the immersive block switched on, current for the length of the block. The
    switch belongs to the deliverable, not to the score's stereo mix preset."""
    import mix_context
    import mix_schema
    import mixer
    ctx = mixer._context_for(score, ctx)
    previous = mix_context.current()
    bctx = mix_context.clone(ctx)
    immersive = dict(mix_schema.DEFAULTS.get('immersive') or {})
    immersive.update(ctx.mix.get('immersive') or {})
    immersive['enabled'] = True
    bctx.mix['immersive'] = immersive
    mix_context.make_current(bctx)
    try:
        yield bctx
    finally:
        mix_context.make_current(previous)


def binaural_mix(score, stems, sr=44100, ctx=None):
    """The headphone deliverable: the same mix with the head-related route switched on for the whole piece.

    The route itself is the mixer's existing immersive placement (measured head data when spatial_hrtf is available,
    spatial.py when it is not).
    """
    import mixer
    with _immersive(score, ctx) as bctx:
        mix = mixer.mix_stems(score, stems, sr, bctx)
        mix = mixer.trim_tail(mix, sr)
        master_cfg = dict(score.get('master') or {})
        out = mixer.master_chain(mix, master_cfg, sr, bctx)
        out = mixer.fades(out, sr, fout=float(master_cfg.get('fade_out', 0.6)))
    return out


def _level(audio, ref, score, target, sr):
    """One gain for a programme that has no loudspeaker layout to measure: `ref`, a two-channel stand-in for it,
    is brought to the loudness target, then the gain is cut until every channel is under the ceiling. A single
    gain, because separate ones would move the sound field."""
    import mixer
    from . import master
    cfg = mixer._master_cfg(dict(score.get('master') or {}), mixer._mix())
    gain_db = float(cfg.get('lufs', -14.0)) - float(mixer.lufs(ref, sr))
    if not np.isfinite(gain_db):
        gain_db = 0.0
    ceiling = float(target.get('true_peak_dbtp', -1.5))
    gain_db = min(gain_db, ceiling - 0.05 - max(master.channel_peaks(audio, sr)))
    return mixer.fades(audio * np.float32(10.0 ** (gain_db / 20.0)), sr, fout=float(cfg.get('fade_out', 0.6)))


def hoa_mix(score, stems, target, sr=44100, ctx=None):
    """The mix as a sound field: AmbiX (ACN order, SN3D), (order + 1)^2 channels. Any ambisonic decoder can then
    put it on any loudspeakers or headphones, and it can still be rotated (head tracking, 360 video)."""
    import mixer
    from . import hoa
    with _immersive(score, ctx) as bctx:
        imm = bctx.mix['immersive']
        bus = hoa.HoaBus(sr, int(target.get('order') or imm.get('order', 5)), 'ambix', imm, bctx.space, score)
        field = mixer.trim_tail(mixer.mix_stems(score, stems, sr, bctx, bus=bus), sr)
        return _level(field, np.repeat(field[:, :1], 2, axis=1), score, target, sr)   # W is the plain pressure


def adm_mix(score, stems, target, sr=44100, ctx=None):
    """(audio, axml, chna rows) of the object-based deliverable: see adm.py."""
    import mixer
    from . import adm
    with _immersive(score, ctx) as bctx:
        bus = adm.AdmBus(sr, bctx.mix['immersive'], score)
        audio = mixer.trim_tail(mixer.mix_stems(score, stems, sr, bctx, bus=bus), sr)
        audio = _level(audio, bus.stereo_fold(audio), score, target, sr)
    return audio, bus


def to_rate(audio, sr, rate, ceiling=None):
    """The programme at another sample rate (polyphase resampling). The new samples fall between the old ones, so
    the true peak is measured again and the whole programme is turned down if it now passes the ceiling."""
    from math import gcd
    from scipy.signal import resample_poly
    from . import master
    rate = int(rate)
    if rate == int(sr):
        return np.asarray(audio, np.float32)
    g = gcd(rate, int(sr))
    out = resample_poly(np.asarray(audio, np.float64), rate // g, int(sr) // g, axis=0).astype(np.float32)
    if ceiling is not None:
        over = max(master.channel_peaks(out, rate)) - float(ceiling)
        if over > 0.0:
            out = out * np.float32(10.0 ** (-(over + 0.05) / 20.0))
    return out


def render_deliverable(score, stems, target_name, path, sr=44100, ctx=None):
    """Build one requested deliverable and write it. The target preset's `renderer` names the route."""
    target = config.target(target_name) or {}
    renderer = target.get('renderer')
    rate = int(target.get('rate_hz') or sr)
    ceiling = target.get('true_peak_dbtp')
    subtype = str(target.get('subtype') or 'PCM_24')
    if renderer == 'spatial':
        from . import master
        audio = master.master(spatial_mix(score, stems, target_name, sr, ctx), score, target, sr)
    elif renderer == 'binaural':
        audio = binaural_mix(score, stems, sr, ctx)
    elif renderer == 'hoa':
        audio = hoa_mix(score, stems, target, sr, ctx)
    elif renderer == 'adm':
        from . import adm
        audio, bus = adm_mix(score, stems, target, sr, ctx)
        audio = to_rate(audio, sr, rate, ceiling)
        return adm.write(path, audio, rate, bus.xml(len(audio), rate), bus.chna())
    elif renderer == 'mix_master':
        import mixer
        mixer.mix_and_master(score, stems, path, sr=sr, ctx=ctx)
        if rate != sr:                         # the certified master, resampled: nothing else about it changes
            import soundfile as sf
            info = sf.info(path)
            write(path, to_rate(sf.read(path, always_2d=True, dtype='float32')[0], sr, rate, ceiling), rate,
                  subtype=info.subtype)
        return path
    else:
        raise ValueError(f'deliverable "{target_name}" names renderer {renderer!r}, which the engine does not have')
    write(path, to_rate(audio, sr, rate, ceiling), rate, subtype=subtype)
    return path
