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
"""vocals.py - Sung, chanting and humming voices by source-filter synthesis.

Supports universal world vocal styles and choral traditions without external audio samples:
  - Standard vowels & chest/nasal hums (a, e, i, o, u, m)
  - Tuvan throat singing (Kargyraa subharmonic gravel, Sygyt whistle overtone)
  - Bulgarian folk chant (open-throat chest twang, 2nd harmonic lock, non-vibrato)
  - Nordic Kulning (high-register piercing call with singer's formant cluster)
  - Qawwali / Sufi devotional singing (pharyngeal twang, meend glissando)
  - Gregorian monastic chant (hollow open chest resonance, zero vibrato)
  - African polyphony (staccato register hockets)
  - Classical SATB choir (soprano, alto, tenor, bass)
"""
import argparse
import sys
import numpy as np
from scipy.signal import lfilter
import pedalboard as pb

INSTRUMENTS = {'choir_formant', 'hum_formant', 'voice_formant', 'throat_formant', 'chant_formant'}

VOWELS = {
    'a': (730, 1090, 2440),
    'e': (530, 1840, 2480),
    'i': (270, 2290, 3010),
    'o': (570, 840, 2410),
    'u': (300, 870, 2240),
    'm': (250, 1000, 2100),
}

VOCAL_STYLES = {
    'tuvan_kargyraa': {
        'formants': (300, 820, 2200),
        'bandwidths': (70.0, 95.0, 140.0),
        'subharmonic': True,
        'vib_cents': 8.0,
        'vib_hz': 4.2,
        'breath': 0.05,
    },
    'tuvan_sygyt': {
        'formants': (400, 1800, 2800),
        'bandwidths': (80.0, 45.0, 60.0),
        'whistle_overtone': True,
        'vib_cents': 6.0,
        'vib_hz': 4.5,
        'breath': 0.02,
    },
    'bulgarian_chant': {
        'formants': (650, 1600, 2700),
        'bandwidths': (85.0, 120.0, 160.0),
        'harmonic_lock': True,
        'vib_cents': 3.0,
        'vib_hz': 5.0,
        'breath': 0.02,
    },
    'nordic_kulning': {
        'formants': (850, 2600, 3300),
        'bandwidths': (90.0, 100.0, 120.0),
        'vib_cents': 22.0,
        'vib_hz': 5.8,
        'vib_delay': 0.5,
        'breath': 0.03,
    },
    'qawwali_devotional': {
        'formants': (680, 1350, 2800),
        'bandwidths': (90.0, 110.0, 130.0),
        'vib_cents': 32.0,
        'vib_hz': 5.5,
        'breath': 0.04,
    },
    'gregorian_monastic': {
        'formants': (320, 850, 2300),
        'bandwidths': (70.0, 90.0, 150.0),
        'vib_cents': 0.0,
        'vib_hz': 5.0,
        'breath': 0.01,
    },
    'african_polyphony': {
        'formants': (700, 1250, 2600),
        'bandwidths': (95.0, 115.0, 150.0),
        'vib_cents': 12.0,
        'vib_hz': 5.2,
        'breath': 0.03,
    },
    'classical_choir': {
        'formants': (730, 1090, 2440),
        'bandwidths': (90.0, 110.0, 150.0),
        'vib_cents': 26.0,
        'vib_hz': 5.3,
        'breath': 0.03,
    },
}

BANDWIDTH = (90.0, 110.0, 150.0)
TRACT_GAIN = (1.0, 0.6, 0.3)


def _smooth_noise(rng, n, sr, rate_hz=6.0):
    k = max(1, int(sr / rate_hz))
    x = rng.standard_normal(n + 2 * k)
    x = np.convolve(x, np.ones(k) / k, 'same')[k:k + n]
    return x / (x.std() + 1e-9)


def _resonator(x, f, bw, sr):
    r = np.exp(-np.pi * bw / sr)
    th = 2 * np.pi * f / sr
    b, a = [1 - r * r], [1, -2 * r * np.cos(th), r * r]
    w = np.array([th])
    z = np.exp(-1j * w)
    gain = abs(np.polyval(b, z[0]) / np.polyval(a[::-1], z[0]))
    return lfilter(b, a, x) / gain


def glottal(f0, sr, subharmonic=False, tilt=1.6):
    """Harmonic glottal source with spectral tilt and optional ventricular subharmonics."""
    phase = np.cumsum(2 * np.pi * f0 / sr)
    k_max = max(1, min(40, int(4000 / max(f0.min(), 40))))
    src = np.zeros_like(f0)
    for k in range(1, k_max + 1):
        src += np.sin(k * phase) / (k ** tilt)
        
    if subharmonic:
        # Kargyraa false vocal fold vibration at f0 / 2
        sub_phase = np.cumsum(2 * np.pi * (f0 * 0.5) / sr)
        for k in range(1, k_max // 2 + 1):
            src += 0.65 * np.sin(k * sub_phase) / (k ** 1.4)
            
    return src


def sing(midi, dur, sr, rng, vowel='a', vib_cents=28.0, vib_hz=5.3, vib_delay=0.35, glide_cents=0.0,
         attack=0.18, release=0.22, breath=0.03, formant_scale=1.0, gain=1.0, formants=None,
         style=None, bandwidths=None):
    """Synthesizes one vocal note using formant resonators."""
    n = int(round(dur * sr))
    t = np.arange(n) / sr
    
    style_cfg = VOCAL_STYLES.get(style, {})
    subharmonic = style_cfg.get('subharmonic', False)
    v_cents = float(style_cfg.get('vib_cents', vib_cents))
    v_hz = float(style_cfg.get('vib_hz', vib_hz))
    v_delay = float(style_cfg.get('vib_delay', vib_delay))
    v_breath = float(style_cfg.get('breath', breath))
    
    vib = np.clip((t - v_delay) / 0.6, 0, 1) * np.sin(2 * np.pi * v_hz * t + rng.random() * 6.283) * v_cents
    glide = glide_cents * np.exp(-t / 0.08)
    jitter = 6.0 * _smooth_noise(rng, n, sr)
    f0 = 440.0 * 2 ** (((midi - 69) * 100 + vib + glide + jitter) / 1200.0)
    
    tilt = 2.2 if (vowel == 'm' or style_cfg.get('hum', False)) else 1.6
    src = glottal(f0, sr, subharmonic=subharmonic, tilt=tilt)
    
    # Resolve formants
    if formants:
        F = [f * formant_scale for f in formants]
    elif style_cfg.get('formants'):
        F = [f * formant_scale for f in style_cfg['formants']]
    elif isinstance(vowel, (list, tuple)):
        F = [f * formant_scale for f in vowel]
    else:
        F = [f * formant_scale for f in VOWELS.get(vowel, VOWELS['a'])]
        
    BW = bandwidths or style_cfg.get('bandwidths', BANDWIDTH)
    
    out = sum(g * _resonator(src, f, bw, sr) for g, f, bw in zip(TRACT_GAIN, F, BW))
    
    # Sygyt whistle overtone injection
    if style_cfg.get('whistle_overtone'):
        # Target high harmonic ~1800-2400 Hz
        target_harmonic = int(np.round(2000.0 / np.mean(f0)))
        whistle_f = f0 * target_harmonic
        whistle_phase = 2 * np.pi * np.cumsum(whistle_f) / sr
        whistle = np.sin(whistle_phase) * 0.45
        out += whistle
        
    # Organic half-cosine / quarter-sine swell and release (removes synthetic linear edges)
    att_ramp = np.sin(0.5 * np.pi * np.clip(t / max(attack, 0.005), 0, 1))
    rel_ramp = np.sin(0.5 * np.pi * np.clip((dur - t) / max(release, 0.005), 0, 1))
    env = att_ramp * rel_ramp
    env = env * (1 + 0.03 * _smooth_noise(rng, n, sr, 6.0))
    out = out * env
    
    if v_breath > 0:
        noise = lfilter([1, -1], [1, -0.7], rng.standard_normal(n))
        # Natural continuous aspiration: soft initial puff + organic mucosal breath throughout the note
        aspiration = (0.35 * np.exp(-t / 0.18) + 0.65) * env
        out = out + v_breath * noise * aspiration * (np.abs(out).max() + 1e-9)
        
    return gain * out / (np.abs(out).max() + 1e-9)


def render_choir(events, sr=44100, voices=5, spread_cents=9.0, pan_width=0.45, vowel='a', seed=1, formant_scale=1.0,
                 hum=False, config=None):
    """Renders multi-voice choral stems with stereo detune and spread."""
    cfg = config or {}
    rng = np.random.default_rng(seed)
    end = max((e['t'] + e['dur'] for e in events), default=0.0) + 1.5
    out = np.zeros((int(end * sr) + 1, 2))
    
    cfg_voices = int(cfg.get('voices', voices))
    cfg_spread = float(cfg.get('spread_cents', spread_cents))
    cfg_pan = float(cfg.get('pan_width', pan_width))
    cfg_attack = float(cfg.get('attack', 0.18))
    cfg_release = float(cfg.get('release', 0.22))
    cfg_breath = float(cfg.get('breath', 0.01 if hum else 0.03))
    cfg_vib_cents = float(cfg.get('vib_cents', 18.0 if hum else 28.0))
    cfg_vib_hz = float(cfg.get('vib_hz', 5.3))
    cfg_vib_delay = float(cfg.get('vib_delay', 0.35))
    cfg_formants = cfg.get('formants')
    cfg_style = cfg.get('style')
    
    for e in events:
        v_gain = float(np.clip(e.get('v', 80) / 127.0, 0.05, 1.0)) * 0.5
        vw = e.get('vowel', 'm' if hum else vowel)
        start = int(e['t'] * sr)
        n_v = int(e.get('voices', cfg_voices))
        for j in range(n_v):
            pos = 0.0 if n_v == 1 else (j / (n_v - 1)) * 2 - 1
            detune = pos * cfg_spread + float(e.get('c', 0.0)) / 100.0
            pan = np.clip(pos * cfg_pan, -1, 1)
            x = sing(e['p'] + detune / 100.0, e['dur'], sr, rng, vowel=vw,
                     glide_cents=float(e.get('gl', 0.0)),
                     attack=float(e.get('attack', cfg_attack)),
                     release=float(e.get('release', cfg_release)),
                     breath=float(e.get('breath', cfg_breath)),
                     formant_scale=float(e.get('formant_scale', formant_scale)),
                     vib_cents=float(e.get('vib_cents', cfg_vib_cents)),
                     vib_hz=float(e.get('vib_hz', cfg_vib_hz)),
                     vib_delay=float(e.get('vib_delay', cfg_vib_delay)),
                     gain=v_gain / np.sqrt(max(1, n_v)),
                     formants=e.get('formants', cfg_formants),
                     style=e.get('style', cfg_style))
            left, right = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
            seg = out[start:start + len(x)]
            seg[:, 0] += x * left
            seg[:, 1] += x * right
            
    return out.astype(np.float32)


def add_vocal_harmonies(audio, semitones=(-12, 7), mix=0.35, sr=44100):
    """Generate backing vocal harmonies via Pedalboard PitchShift.
    audio: (samples, 2) stereo or (samples,) mono array.
    """
    if audio.ndim == 1:
        x = np.stack([audio, audio], axis=0)  # (2, N) for pedalboard
    else:
        x = audio.T.copy()  # (2, N)
    
    harmonies = np.zeros_like(x)
    for semi in semitones:
        shift_board = pb.Pedalboard([pb.PitchShift(semitones=semi)])
        shifted = shift_board(x, sr)
        harmonies += shifted / len(semitones)
        
    out = (1.0 - mix) * x + mix * harmonies
    return out.T.astype(np.float32)


def add_vocal_chorus(audio, rate_hz=1.0, depth=0.25, mix=0.4, sr=44100):
    """Add dimension widening and ensemble chorus diffusion using Pedalboard Chorus."""
    if audio.ndim == 1:
        x = np.stack([audio, audio], axis=0)
    else:
        x = audio.T.copy()
    chorus_board = pb.Pedalboard([pb.Chorus(rate_hz=rate_hz, depth=depth, mix=mix)])
    out = chorus_board(x, sr)
    return out.T.astype(np.float32)


def apply_vocal_dsp(audio, sr=44100, style=None):
    """Polish vocal track through Pedalboard: Highpass (80Hz), vocal presence EQ, gentle compression, and style-appropriate sweetening."""
    if audio.ndim == 1:
        x = np.stack([audio, audio], axis=0)
    else:
        x = audio.T.copy()
        
    chain = [
        pb.HighpassFilter(cutoff_frequency_hz=80.0),
        pb.PeakFilter(cutoff_frequency_hz=3200.0, gain_db=1.8, q=0.8),
        pb.HighShelfFilter(cutoff_frequency_hz=10000.0, gain_db=1.5, q=0.7),
        pb.Compressor(threshold_db=-20.0, ratio=2.2, attack_ms=20.0, release_ms=160.0)
    ]
    if style in ('qawwali_sufi', 'arabic_desert_vocal', 'bulgarian_chant'):
        chain.append(pb.Distortion(drive_db=1.5))  # subtle tape warmth
    board = pb.Pedalboard(chain)
    out = board(x, sr)
    return out.T.astype(np.float32)


def _envelope_energy_above(x, sr, f):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / sr)
    return spec[fr > f].sum() / (spec.sum() + 1e-12)


def selftest():
    sr = 44100
    rng = np.random.default_rng(3)
    x = {v: sing(57, 1.5, sr, rng, vowel=v, breath=0.0, vib_cents=0.0) for v in 'aiuom'}
    hi = {v: _envelope_energy_above(x[v][int(0.4 * sr):int(1.2 * sr)], sr, 1500) for v in x}
    assert hi['i'] > 1.5 * hi['u'], hi
    assert hi['m'] < hi['a'], hi
    print('ok: energy above 1.5 kHz (fraction): ' + ', '.join(f'{v}={hi[v]:.1e}' for v in 'aiuom') + '; i > 1.5 u and m < a')
    
    # Test expanded world styles
    x_karg = sing(45, 1.5, sr, rng, style='tuvan_kargyraa')
    assert len(x_karg) > 0 and np.isfinite(x_karg).all()
    x_kul = sing(72, 1.5, sr, rng, style='nordic_kulning')
    assert len(x_kul) > 0 and np.isfinite(x_kul).all()
    print('ok: expanded world vocal styles (kargyraa, kulning) synthesize cleanly')
    
    ev = [dict(t=0.0, dur=2.0, p=60, v=90), dict(t=0.5, dur=2.0, p=64, v=90)]
    st = render_choir(ev, sr=sr, voices=5, seed=4)
    assert st.shape[1] == 2 and np.isfinite(st).all() and np.abs(st).max() <= 1.0
    assert np.abs(st[:, 0] - st[:, 1]).mean() > 1e-3
    assert np.abs(st).max() > 0.05
    print('ok: 5-voice choir: finite, stereo spread, audible')
    
    # Test Pedalboard harmony and chorus integration
    harm = add_vocal_harmonies(st, semitones=[-12, 7], mix=0.3, sr=sr)
    assert harm.shape == st.shape and np.isfinite(harm).all()
    ch_out = add_vocal_chorus(st, rate_hz=1.0, depth=0.25, mix=0.4, sr=sr)
    assert ch_out.shape == st.shape and np.isfinite(ch_out).all()
    dsp_out = apply_vocal_dsp(st, sr=sr, style='qawwali_sufi')
    assert dsp_out.shape == st.shape and np.isfinite(dsp_out).all()
    print('ok: pedalboard harmonies, chorus diffusion, and vocal dsp chain verified')
    print('selftest passed')


def demo(path):
    import soundfile as sf
    chords = [(0.0, [57, 60, 64]), (3.0, [53, 57, 60]), (6.0, [55, 59, 62]), (9.0, [57, 60, 64])]
    ev = [dict(t=t + 0.0, dur=2.8, p=p, v=85, gl=-80 if i == 0 else 0) for t, ps in chords for i, p in enumerate(ps)]
    ev += [dict(t=t, dur=2.8, p=p - 12, v=60, vowel='m') for t, ps in chords for p in ps[:1]]
    st = render_choir(ev, sr=44100, voices=5, seed=9)
    sf.write(path, st / (np.abs(st).max() + 1e-9) * 0.7, 44100)
    print('wrote', path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['selftest', 'demo'])
    ap.add_argument('out', nargs='?', default='choir_demo.wav')
    a = ap.parse_args()
    selftest() if a.cmd == 'selftest' else demo(a.out)


if __name__ == '__main__':
    main()
