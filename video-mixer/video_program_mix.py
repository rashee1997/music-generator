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
"""video_program_mix.py - put the music bed under a voice-over and hits, then master the program.

    python3 video-mixer/video_program_mix.py --voice narration.wav --music out/master.wav --out out/program.wav

Moved here from `scripts/video_mix.py` and made preset-driven: every number now comes from the video preset's
"mix" and "master_profiles" blocks. What it does, in order:

  VOICE    chain to voice_lufs (high-pass, mud trim, presence, sibilance tame, gentle compression)
  MUSIC    fitted to the picture, `bed_db` under the voice where nobody speaks, then ducked a further `duck_db`
           while speech is active; the duck is frequency-selective inside `speech_band_hz`, so the low end and the
           top stay put (the band that fights speech is 250-3800 Hz)
  SWELL    the bed rises `pre_hit_db` into each hit and releases after it
  SFX      placed at their seconds, `sfx_headroom_db` under the voice
  MASTER   glue + limiter to the chosen master profile (streaming / broadcast / cinema)

Prints the music-under-speech figure the video gate will judge (aim >= 15 dB).
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
for p in (HERE, os.path.join(SKILL, 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

import mixer as mx          # noqa: E402
import pedalboard as pb     # noqa: E402

SR = 44100                 # the engine's rate; the program is resampled to master.sample_rate at the end


def load(path, sr=SR):
    x, s = sf.read(path, always_2d=True)
    x = x.astype(np.float32)
    if s != sr:
        x = signal.resample_poly(x, sr, s, axis=0).astype(np.float32)
    return mx.to_stereo(x)


def voice_chain(v, cfg):
    board = pb.Pedalboard([
        pb.HighpassFilter(cfg['voice_hp_hz']), pb.PeakFilter(cfg['voice_mud_hz'], cfg['voice_mud_db'], 1.0),
        pb.PeakFilter(cfg['voice_presence_hz'], cfg['voice_presence_db'], 0.9),
        pb.PeakFilter(cfg['voice_sibilance_hz'], cfg['voice_sibilance_db'], 2.0),
        pb.Compressor(threshold_db=cfg['voice_comp_threshold_db'], ratio=cfg['voice_comp_ratio'],
                      attack_ms=cfg['voice_comp_attack_ms'], release_ms=cfg['voice_comp_release_ms']),
        pb.Gain(cfg['voice_makeup_db'])])
    return mx._run(board, v)


def speech_mask(v, cfg, sr=SR):
    """1 while the voice is active, with a hold so the short pauses between words do not release the duck."""
    e = mx.envelope(v, sr, attack_ms=cfg['speech_envelope_attack_ms'], release_ms=cfg['speech_envelope_release_ms'])
    ref = np.percentile(e[e > 1e-5], 95) if (e > 1e-5).any() else 1.0
    active = (e > ref * 10 ** (cfg['speech_threshold_db'] / 20.0)).astype(float)
    hold = max(1, int(cfg['speech_hold_s'] * sr))
    return np.convolve(active, np.ones(hold) / hold, mode='same') > cfg['speech_hold_frac']


def band(x, lo, hi, sr=SR):
    """The part of x inside [lo, hi]. Used to duck only the band that fights speech."""
    sos = signal.butter(4, [lo, hi], btype='band', fs=sr, output='sos')
    return signal.sosfilt(sos, x, axis=0).astype(np.float32)


def duck_curve(voice, n, mask, cfg, sr=SR):
    """The full-band duck, applied only where speech is present."""
    g = mx.duck_gain(voice, n, depth_db=cfg['duck_db'], thresh=cfg['duck_threshold'],
                     attack_ms=cfg['attack_ms'], release_ms=cfg['release_ms'], sr=sr,
                     lookahead_ms=cfg['lookahead_ms'])
    g = np.where(mask, g, np.maximum(g, 10 ** (cfg['duck_floor_db'] / 20.0)))
    smooth = max(1, int(cfg['duck_smooth_s'] * sr))
    return np.convolve(g, np.ones(smooth) / smooth, mode='same')


def spectral_duck(music, voice, n, mask, cfg, sr=SR):
    """Frequency-selective duck: `speech_band_hz` ducks deeper than the rest, so the low end and the top stay put.

    Everything ducks by `duck_db`; the speech band ducks by `duck_db + duck_depth_db` (the ratio between the two
    is the preset's business, not the code's).
    """
    lo, hi = cfg['speech_band_hz']
    lo = max(float(lo), float(cfg['low_end_protect_below_hz']))
    banded = band(music, lo, hi, sr)
    rest = music - banded
    g = duck_curve(voice, n, mask, cfg, sr)
    extra = abs(float(cfg['duck_depth_db']) / float(cfg['duck_db'])) if cfg['duck_db'] else 0.0
    return (rest * g[:, None] + banded * (g ** (1.0 + extra))[:, None]).astype(np.float32)


def swell_curve(n, hit_times, cfg, sr=SR):
    """Bed gain: rises `pre_hit_db` into each hit, releases after it. 1.0 where there is no hit."""
    g = np.ones(n, np.float32)
    if not cfg.get('enabled') or not hit_times:
        return g
    rise, rel = max(1, int(cfg['rise_s'] * sr)), max(1, int(cfg['release_s'] * sr))
    gain = 10 ** (cfg['pre_hit_db'] / 20.0)
    for t in hit_times:
        i = int(float(t) * sr)
        a, b = max(0, i - rise), min(n, i + rel)
        if b <= a:
            continue
        ramp = np.concatenate([np.linspace(1.0, gain, max(1, i - a)), np.linspace(gain, 1.0, max(1, b - i))])
        g[a:b] = np.maximum(g[a:b], ramp[:b - a])
    return g


def fit_music(music, n, cfg, sr=SR):
    """Loop the bed to the picture length with a short crossfade, then trim. Never resample by stretching."""
    m = music
    if len(m) < n:
        xf = max(1, int(min(cfg['loop_crossfade_max_s'], len(m) / sr / 4.0) * sr))
        out = m.copy()
        while len(out) < n:
            w = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
            out[-xf:] = out[-xf:] * (1 - w[:, None]) + m[:xf] * w[:, None]
            out = np.concatenate([out, m[xf:]])
        m = out
    return m[:n]


def build(voice, music, sfx, cfg, sr=SR, hit_times=None, limit_s=None):
    """The program mix. Returns (mix, voice, music_ducked, mask, report).

    `limit_s` is the picture length: the music tail runs past the end of the voice but never past the picture,
    because a program longer than the picture is a delivery fault, not a musical choice.
    """
    n = len(voice) + int(cfg['tail_s'] * sr)
    if limit_s:
        n = min(n, int(round(float(limit_s) * sr)))
    v = mx.fit(voice, n)
    v = v * 10 ** ((cfg['voice_lufs'] - mx.lufs(v, sr)) / 20.0)          # voice to the reference loudness first
    m = fit_music(music, n, cfg, sr)
    m = mx._run(pb.Pedalboard([pb.PeakFilter(cfg['music_carve_hz'], cfg['music_carve_db'], 0.8),
                               pb.HighpassFilter(cfg['music_hp_hz'])]), m)
    m = m * 10 ** (((cfg['voice_lufs'] + cfg['bed_db']) - mx.lufs(m, sr)) / 20.0)
    mask = speech_mask(v, cfg, sr)
    m = spectral_duck(m, v, n, mask, cfg, sr)
    m = m * swell_curve(n, hit_times if hit_times is not None else [t for _, t in sfx], cfg['swell'], sr)[:, None]
    fo = max(1, int(cfg['fade_out_s'] * sr))
    m[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    fi = max(1, int(cfg['fade_in_s'] * sr))
    m[:fi] *= np.linspace(0, 1, fi)[:, None]
    mix = v + m
    for path, t in sfx:
        s = load(path, sr)
        level = cfg['voice_lufs'] + cfg['sfx_headroom_db']
        s = s * 10 ** ((level - mx.lufs(s, sr)) / 20.0) if len(s) > sr // 2 else s * cfg['sfx_short_gain']
        i = int(t * sr)
        if i >= len(mix):
            continue
        seg = s[:len(mix) - i]
        mix[i:i + len(seg)] += seg
    report = dict(speech_ratio=round(float(mask.mean()), 4))
    sp = mask[:len(m)]
    if sp.sum() > sr:
        report['voice_rms_db'] = round(mx.rms_db(v[sp]), 2)
        report['music_rms_db'] = round(mx.rms_db(m[sp]), 2)
        report['music_under_voice_db'] = round(report['voice_rms_db'] - report['music_rms_db'], 2)
    return mix, v, m, mask, report


def master(mix, cfg, sr=SR):
    """Program master: the loudness and true-peak ceiling of the chosen profile, then the delivery sample rate."""
    y = mx.master_chain(mix, dict(lufs=cfg['lufs'], true_peak=cfg['true_peak_db'], glue=True), sr)
    target = int(cfg.get('sample_rate', sr))
    if target != sr:
        y = signal.resample_poly(y, target, sr, axis=0).astype(np.float32)
    return y, target


def master_profile(cfg, name=None):
    """The master profile named by the preset (or overridden), merged over its own defaults."""
    prof = cfg['master_profiles'][name or cfg['master']['profile']]
    out = dict(prof)
    out['sample_rate'] = cfg['master'].get('sample_rate', 48000)
    return out


def main():
    import presets
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--voice', required=True)
    ap.add_argument('--music', required=True)
    ap.add_argument('--sfx', nargs='*', default=[], help='file.wav@seconds')
    ap.add_argument('--out', default='program.wav')
    ap.add_argument('--preset', default='default')
    ap.add_argument('--project')
    ap.add_argument('--profile', default=None, help='streaming | broadcast | cinema (default: the preset)')
    ap.add_argument('--no-voice-chain', action='store_true')
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    cfg = presets.get('video', a.preset)
    import cli_util
    cli_util.require_file(a.voice, 'voice file')
    cli_util.require_file(a.music, 'music file')
    voice = load(a.voice)
    if not a.no_voice_chain:
        voice = voice_chain(voice, cfg['mix'])
    music = load(a.music)
    sfx = [(p.split('@')[0], float(p.split('@')[1])) for p in a.sfx]
    mix, v, m, mask, rep = build(voice, music, sfx, cfg['mix'])
    prof = master_profile(cfg, a.profile)
    out, sr = master(mix, prof)
    sf.write(a.out, out, sr, subtype='PCM_24')
    print(f"wrote {a.out}  {len(out) / sr:.2f}s @ {sr} Hz  LUFS {mx.lufs(out, sr):.1f}  "
          f"true-peak {mx.true_peak_db(out, sr):.2f} dBTP  (target {prof['lufs']} / {prof['true_peak_db']})")
    if 'music_under_voice_db' in rep:
        ok = rep['music_under_voice_db'] >= cfg['gate']['dialogue_snr_min_db']
        print(f"during speech: voice {rep['voice_rms_db']:.1f} dB RMS, music {rep['music_rms_db']:.1f} dB RMS "
              f"-> {rep['music_under_voice_db']:.1f} dB under the voice ({'OK' if ok else 'TOO LOUD: lower bed_db / raise duck_db'})")


if __name__ == '__main__':
    main()
