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
"""environment.py - Universal Parameter-Driven Procedural Soundscape Engine.

Generates any environmental soundscape (rainforests, oceans, deserts, bazaars, temples, savannahs)
using generic DSP acoustic primitives configured via JSON presets:
  1. noise_bed: Continuous band-limited stochastic energy (air, breeze, wind floor, ocean base).
  2. resonant_gust: Swept resonant bandpass noise (howling wind, cavern drafts, sand drift).
  3. fm_chirp_cluster: Frequency-modulated vocal/harmonic chirps (birds, whistles, wildlife calls).
  4. impulse_cluster: Poisson-distributed transient impacts (rain drops, footsteps, water drips, clatter).
  5. stridulation_bed: Amplitude-pulsed high-frequency band noise (insects, cicadas, crickets).
  6. water_flow: Periodic surge rumble coupled with turbulent wash (rivers, rapids, surf, waterfalls).
  7. formant_babble: Formant-filtered noise clusters (crowds, bazaars, pedestrian murmurs).
  8. doppler_sweep: FM pitch/noise sweeps (vehicle passes, sirens, swooping objects).
  9. voice_bouts: bouts of a pitched, formant-filtered voice (roars, calls, hums); every number comes from the preset.
 10. syllable_bouts: bouts of short swept tonal syllables (whistles, squeaks, chirps); every number comes from the preset.
     Every primitive in PRIMITIVES takes any of its parameters straight from the layer's keys (see --primitives).

All parameters, layer configurations, spatial positions, and blending curves are read dynamically
from presets; nothing musical or species-specific is hard-coded in the engine.
"""
import inspect
import json
import os
import sys
import zlib
import numpy as np
import scipy.signal as signal
import soundfile as sf
import pedalboard as pb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airabs
import presets

SR = 44100
NORMALIZED = ('rain_physical', 'cricket_chorus', 'bird_chorus', 'model_layer', 'noise_bed',
              'stridulation_bed')   # layers on these start at RMS 0.1 (-20 dBFS), so gain_db is comparable
BED_REF_RMS = 0.25          # the amplitude a noise/stridulation bed is normalized to before gain_db


# ---------------------------------------------------------------------------------------------
# Core Filters
# ---------------------------------------------------------------------------------------------

def _bandpass(x, low, high, sr=SR):
    sos = signal.butter(2, [max(10.0, low), min(sr * 0.49, high)], btype='bandpass', fs=sr, output='sos')
    return signal.sosfilt(sos, x).astype(np.float32)


def _highpass(x, cutoff, sr=SR):
    sos = signal.butter(2, max(10.0, cutoff), btype='highpass', fs=sr, output='sos')
    return signal.sosfilt(sos, x).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# Generic Procedural DSP Primitives
# ---------------------------------------------------------------------------------------------

_PINK_B = [0.049922035, -0.095993537, 0.050612699, -0.004408786]     # -3 dB/octave
_PINK_A = [1.0, -2.494956002, 2.017265875, -0.522189400]


def _slow_mod(n, sr, rate_hz, turbulence, rng):
    """Slow modulation in [-1, 1]: (1 - turbulence) of a sine plus `turbulence` of an irregular gust series with the same corner
    rate, so wind and water never pulse on a predictable cycle. turbulence=0 is the plain sine.
    The gust series is seeded from the generator's current state WITHOUT drawing from it, so no other layer's random numbers move."""
    s = np.sin(2 * np.pi * rate_hz * np.arange(n) / sr)
    if turbulence <= 0:
        return s
    seed = zlib.crc32(repr(rng.bit_generator.state).encode())
    z = _turbulence(n, sr, np.random.default_rng(seed), rate_hz)
    return np.clip((1.0 - turbulence) * s + turbulence * 0.7071 * z, -1.0, 1.0)


def synth_noise_bed(sec, sr=SR, rng=None, color='pink', low_hz=80.0, high_hz=2400.0,
                    mod_rate_hz=0.06, mod_depth=0.15, mod_turbulence=0.7):
    """Continuous band-limited noise bed with slow breathing modulation (mod_turbulence: share of irregular gusts in it, 0 = sine)."""
    rng = rng or np.random.default_rng(101)
    n = int(sec * sr)
    white = rng.standard_normal(n).astype(np.float32)

    if color == 'brown':
        base = np.cumsum(white).astype(np.float32)
    elif color == 'pink':
        base = signal.lfilter(_PINK_B, _PINK_A, white).astype(np.float32)
    else:
        base = white
    if color in ('brown', 'pink'):
        # RMS, not peak: a Gaussian draw's peak is an extreme-value statistic, so peak-normalizing made the bed's
        # level depend on its duration and on the seed (+-1-2 dB). RMS is the physical calibration.
        rms = float(np.sqrt(np.mean(base.astype(np.float64) ** 2)))
        if rms > 1e-9:
            base = (base * (BED_REF_RMS / rms)).astype(np.float32)

    filtered = _bandpass(base, low_hz, high_hz, sr=sr)
    mod = (1.0 - mod_depth) + mod_depth * _slow_mod(n, sr, mod_rate_hz, mod_turbulence, rng)
    return (filtered * mod).astype(np.float32)


def synth_resonant_gust(sec, sr=SR, rng=None, center_hz=450.0, q=7.0, mod_rate_hz=0.15, mod_depth=0.55,
                        turbulence=False):
    """Swept resonant bandpass noise (desert wind howling, cavern drafts).

    turbulence=True drives both the centre frequency and the loudness from one -5/3 gust series
    (corner = mod_rate_hz) instead of a sine, so gusts are irregular and pitch follows strength.
    """
    rng = rng or np.random.default_rng(202)
    n = int(sec * sr)
    t = np.arange(n) / sr
    white = rng.standard_normal(n).astype(np.float32)

    if turbulence:
        z = _turbulence(n, sr, rng, mod_rate_hz)
        lfo = center_hz * np.clip(1.0 + 0.5 * mod_depth * z, 0.3, 2.0)
    else:
        lfo = center_hz * (1.0 + mod_depth * np.sin(2 * np.pi * mod_rate_hz * t))
    lfo = np.clip(lfo, 50.0, sr * 0.45)
    
    block_size = max(64, int(0.01 * sr))   # 10 ms not 50 ms: a held cutoff at q=7 was audible as a 20 Hz wobble
    n_blocks = int(np.ceil(n / block_size))
    out = np.zeros(n, dtype=np.float32)
    zi = None   # carry filter state across blocks, or every block starts from silence (a 20 Hz level dip)

    for i in range(n_blocks):
        i0 = i * block_size
        i1 = min(n, (i + 1) * block_size)
        if i1 <= i0:
            break
        fc = float(lfo[i0])
        bw = max(20.0, fc / float(q))
        sos = signal.butter(2, [max(10.0, fc - bw / 2), min(sr * 0.48, fc + bw / 2)], btype='bandpass', fs=sr, output='sos')
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        out[i0:i1], zi = signal.sosfilt(sos, white[i0:i1], zi=zi)

    if turbulence:
        out *= np.clip(1.0 + 0.45 * z, 0.15, 2.2)
    return out.astype(np.float32)


def synth_fm_chirp_cluster(sec, sr=SR, rng=None, f0_low=1400.0, f0_high=3800.0,
                           mod_rate_hz=24.0, mod_depth_hz=22.0, event_rate=0.8,
                           dur_low=0.15, dur_high=0.45, harmonics=2,
                           nonlinearity=0.35, biphonation=True,
                           biphonation_detune_cents=18.0, biphonation_ratio=0.32,
                           trachea_q=3.8, aspiration_gain=0.025, contour='natural',
                           echo_ms=38.0, echo_db=-12.0, echo_lp_hz=3200.0):
    """Universal frequency-modulated chirps and melodic calls with biological syrinx physical dynamics.

    Models:
      1. Mindlin-Goller non-linear labial limit-cycle saturation (tanh pressure waveshaping).
      2. Dual syringeal labia biphonation (micro-detuned acoustic beating between bronchus sources).
      3. Dynamic tracheal/beak acoustic cavity formant tracking (warm, resonant biological filter).
      4. Aerodynamic aspiration breath turbulence at syllable onset.
      5. Natural physiological pitch trajectories (exponential inflections and syringeal tremolo that blooms mid-call).
    echo_ms / echo_db / echo_lp_hz: one soft canopy echo behind each call, so a call is never bone-dry (echo_db null = off).
    """
    rng = rng or np.random.default_rng(303)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float32)
    
    t_curr = rng.uniform(0.5, 2.5)
    while t_curr < sec - 1.0:
        dur = float(rng.uniform(dur_low, dur_high))
        n_call = int(dur * sr)
        if n_call < 64:
            t_curr += 0.5
            continue
        t = np.arange(n_call) / sr
        tau = (t / dur).astype(np.float32)
        
        f_base = float(rng.uniform(f0_low, f0_high))
        f_end = f_base * float(rng.uniform(0.75, 1.35))
        
        # Physiological pitch trajectory
        if contour == 'linear':
            pitch_base = np.linspace(f_base, f_end, n_call)
        elif contour == 'inflected':
            peak_f = max(f_base, f_end) * float(rng.uniform(1.1, 1.3))
            pitch_base = f_base + (peak_f - f_base) * np.sin(np.pi * tau) + (f_end - f_base) * (tau ** 2)
        else: # 'natural'
            curve_pow = float(rng.uniform(0.8, 1.4))
            pitch_base = f_base + (f_end - f_base) * (tau ** curve_pow)
            
        # Syringeal motor tremolo / vibrato
        tremolo = mod_depth_hz * np.sin(2 * np.pi * mod_rate_hz * t) * np.sin(np.pi * tau) ** 2   # blooms mid-call, silent at both ends
        pitch_t = np.clip(pitch_base + tremolo, 100.0, sr * 0.45)
        
        # Primary labium phase
        phase1 = 2 * np.pi * np.cumsum(pitch_t) / sr
        carrier1 = np.sin(phase1)
        for h in range(2, max(2, harmonics + 1)):
            carrier1 += (0.35 / h) * np.sin(h * phase1)
            
        # Dual-source biphonation (secondary bronchus oscillator)
        if biphonation and biphonation_ratio > 0.01:
            detune_mult = 2.0 ** (biphonation_detune_cents / 1200.0)
            phase2 = 2 * np.pi * np.cumsum(pitch_t * detune_mult) / sr
            carrier2 = np.sin(phase2)
            labia_signal = carrier1 + biphonation_ratio * carrier2
        else:
            labia_signal = carrier1
            
        # Physiological pressure envelope (smooth onset, rounded peak, natural release)
        env = (np.sin(np.pi * tau) ** 1.6).astype(np.float32)
        
        # Mindlin-Goller non-linear labial limit-cycle saturation
        drive = 1.0 + 1.8 * nonlinearity * env
        sat_signal = np.tanh(drive * labia_signal)
        
        # Aerodynamic aspiration breath turbulence
        if aspiration_gain > 0.005:
            white = rng.standard_normal(n_call).astype(np.float32)
            f_mid = float(np.mean(pitch_t))
            sos_breath = signal.butter(2, [max(100.0, f_mid * 0.7), min(sr * 0.48, f_mid * 1.5)], btype='bandpass', fs=sr, output='sos')
            breath = signal.sosfilt(sos_breath, white)
            breath_env = np.sin(np.pi * np.clip(tau * 1.6, 0, 1)) ** 2
            raw_call = sat_signal * 0.85 + breath * breath_env * (aspiration_gain * 1.2)
        else:
            raw_call = sat_signal
            
        # Dynamic vocal tract / beak formant acoustic cavity resonance
        if trachea_q > 0.5:
            f_res = float(np.mean(pitch_t))
            bw = max(50.0, f_res / max(1.0, trachea_q))
            sos_formant = signal.butter(2, [max(50.0, f_res - bw / 2), min(sr * 0.48, f_res + bw / 2)], btype='bandpass', fs=sr, output='sos')
            call_filtered = signal.sosfilt(sos_formant, raw_call) * 1.6 + raw_call * 0.4
        else:
            call_filtered = raw_call
            
        # Normalize peak of call before applying level envelope
        peak_val = max(1e-5, float(np.max(np.abs(call_filtered))))
        call_normalized = (call_filtered / peak_val) * env * float(rng.uniform(0.65, 0.95))
        if echo_db is not None:
            d = int(echo_ms / 1000.0 * sr)
            sos_echo = signal.butter(2, min(echo_lp_hz, sr * 0.45), btype='lowpass', fs=sr, output='sos')
            with_echo = np.zeros(len(call_normalized) + d, dtype=np.float32)
            with_echo[:len(call_normalized)] = call_normalized
            with_echo[d:] += signal.sosfilt(sos_echo, call_normalized) * 10.0 ** (float(echo_db) / 20.0)
            call_normalized = with_echo

        i0 = int(t_curr * sr)
        i1 = min(n, i0 + len(call_normalized))
        out[i0:i1] += call_normalized[:i1 - i0]
        
        t_curr += float(rng.exponential(1.0 / max(0.1, event_rate))) + 0.6
        
    return out.astype(np.float32)


def synth_impulse_cluster(sec, sr=SR, rng=None, event_rate=8.0, freq_low=1400.0,
                          freq_high=4200.0, decay_ms=18.0, pitch_dip=True):
    """Poisson-distributed transient impacts (rain drops, footsteps, water drips, clatter)."""
    rng = rng or np.random.default_rng(404)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float32)
    
    total_events = int(sec * event_rate)
    decay_samps = max(20, int((decay_ms / 1000.0) * sr))
    dt = np.arange(decay_samps) / sr
    
    for _ in range(total_events):
        pos = int(rng.uniform(0, n - decay_samps - 1))
        fc = float(rng.uniform(freq_low, freq_high))
        d_rate = float(rng.uniform(0.005, max(0.006, decay_ms / 1000.0)))
        if pitch_dip:
            pitch_t = fc * np.exp(-dt * 40.0) + fc * 0.75
            phase = 2 * np.pi * np.cumsum(pitch_t) / sr
            click = np.sin(phase)
        else:
            click = np.sin(2 * np.pi * fc * dt)
        env = np.exp(-dt / d_rate)
        out[pos:pos + decay_samps] += click * env * float(rng.uniform(0.2, 0.9))
        
    return out.astype(np.float32)


def synth_stridulation_bed(sec, sr=SR, rng=None, low_hz=5200.0, high_hz=8500.0,
                           pulse_rate_hz=11.5, pulse_depth=0.5):
    """Amplitude-pulsed high-frequency band noise (cicadas, crickets, insects, sand drift)."""
    rng = rng or np.random.default_rng(505)
    n = int(sec * sr)
    t = np.arange(n) / sr
    white = rng.standard_normal(n).astype(np.float32)
    
    band = _bandpass(white, low_hz, high_hz, sr=sr)
    # A real cicada bed is not a phase-0 sine: each layer starts at a random phase, its pulse rate wanders a few
    # percent, and its swell follows turbulence. Two deterministic sines summed coherently and flanged.
    phase0 = float(rng.uniform(0.0, 2.0 * np.pi))
    jitter = 1.0 + 0.18 * _slow_mod(n, sr, 0.9, 0.7, rng)
    phase = 2.0 * np.pi * np.cumsum(pulse_rate_hz * jitter) / sr + phase0
    pulse = (1.0 - pulse_depth) + pulse_depth * np.sin(phase)
    macro_swell = 0.75 + 0.25 * _slow_mod(n, sr, 0.15, 0.75, rng)
    return (band * pulse * macro_swell).astype(np.float32)


def synth_water_flow(sec, sr=SR, rng=None, swell_period_s=6.0, low_cutoff_hz=480.0, foam_cutoff_hz=3600.0,
                     hf_damp=0.65, bubble_rate=10.0, swell_turbulence=0.7, foam_color='pink'):
    """Surge rumble coupled with turbulent wash and Minnaert bubble resonances.

    Includes high-frequency damping (hf_damp) to eliminate white-noise hiss walls that mask
    hi-hats, shakers, and acoustic pick attacks. swell_turbulence: share of irregular gusts in the swell (0 = sine);
    foam_color 'pink' (-3 dB/oct, like real water wash) or 'white', at the same level either way.
    """
    rng = rng or np.random.default_rng(606)
    n = int(sec * sr)
    white = rng.standard_normal(n).astype(np.float32)

    rumble = _bandpass(white, 50.0, low_cutoff_hz, sr=sr)
    foam = _bandpass(white, low_cutoff_hz, min(foam_cutoff_hz, sr * 0.45), sr=sr)
    if foam_color == 'pink':
        pink = _bandpass(signal.lfilter(_PINK_B, _PINK_A, white).astype(np.float32), low_cutoff_hz, min(foam_cutoff_hz, sr * 0.45), sr=sr)
        foam = (pink * float(np.sqrt(np.mean(foam ** 2)) / max(1e-9, np.sqrt(np.mean(pink ** 2))))).astype(np.float32)
    
    # High-frequency damping shelf to prevent hiss wall
    if hf_damp > 0:
        roll_hz = min(sr * 0.45, max(1200.0, foam_cutoff_hz * (1.0 - hf_damp * 0.4)))
        sos_damp = signal.butter(1, roll_hz, btype='lowpass', fs=sr, output='sos')
        foam = signal.sosfilt(sos_damp, foam).astype(np.float32)
        
    swell = (0.7 + 0.3 * _slow_mod(n, sr, 1.0 / swell_period_s, swell_turbulence, rng)).astype(np.float32)
    base_flow = (rumble * swell * 0.65 + foam * 0.35).astype(np.float32)
    
    # Fluid bubble resonant micro-transients (Minnaert resonant micro-bubbles)
    if bubble_rate > 0:
        b_dur_ms = 22.0
        b_samps = max(20, int((b_dur_ms / 1000.0) * sr))
        n_bubbles = int(sec * bubble_rate) if n > b_samps + 1 else 0     # a < 22 ms spot has no room for a bubble
        bubble_layer = np.zeros(n, dtype=np.float32)
        dt = np.arange(b_samps) / sr
        for _ in range(n_bubbles):
            pos = int(rng.uniform(0, max(0, n - b_samps - 1)))
            f_bub = float(rng.uniform(350.0, 1600.0))
            decay_bub = float(rng.uniform(0.006, 0.018))
            phase_bub = 2 * np.pi * f_bub * dt
            click_bub = np.sin(phase_bub) * np.exp(-dt / decay_bub)
            bubble_layer[pos:pos + b_samps] += click_bub * float(rng.uniform(0.05, 0.22))
        base_flow += bubble_layer * 0.35
        
    return base_flow.astype(np.float32)


def synth_formant_babble(sec, sr=SR, rng=None, formants=None, rate_hz=4.5, voices=4):
    """Formant-filtered noise clusters (crowds, bazaars, pedestrian murmurs)."""
    rng = rng or np.random.default_rng(707)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float32)
    formants = formants or [
        [(700, 1200, 2800), (300, 2200, 3000)],
        [(500, 1800, 2500), (400, 1000, 2400)]
    ]
    for v in range(voices):
        white = rng.standard_normal(n).astype(np.float32)
        f_pair = formants[v % len(formants)]
        f1, f2, f3 = f_pair[0]
        f_track = _bandpass(white, f1 * 0.85, f1 * 1.15, sr=sr) * 0.5 + \
                  _bandpass(white, f2 * 0.85, f2 * 1.15, sr=sr) * 0.35 + \
                  _bandpass(white, f3 * 0.85, f3 * 1.15, sr=sr) * 0.2
        t = np.arange(n) / sr
        mod = 0.5 + 0.5 * np.sin(2 * np.pi * (rate_hz * rng.uniform(0.8, 1.2)) * t + rng.uniform(0, 2 * np.pi))
        out += (f_track * mod).astype(np.float32)
    return out / max(1, voices)


def synth_doppler_sweep(sec, sr=SR, rng=None, f_start=350.0, f_end=170.0, pass_time=None, width_s=1.4):
    """FM pitch and noise sweep for passing objects."""
    rng = rng or np.random.default_rng(808)
    n = int(sec * sr)
    t = np.arange(n) / sr
    p_time = float(pass_time) if pass_time is not None else float(sec * 0.5)
    w_s = max(0.2, float(width_s))
    env = np.exp(-((t - p_time) / (w_s * 0.45)) ** 2)
    k = 8.0 / w_s
    pitch_t = f_end + (f_start - f_end) / (1.0 + np.exp(k * (t - p_time)))
    phase = 2 * np.pi * np.cumsum(pitch_t) / sr
    tone = np.sin(phase).astype(np.float32) * 0.35
    white = rng.standard_normal(n).astype(np.float32)
    hiss = _bandpass(white, 400.0, 3200.0, sr=sr) * 0.65
    return ((tone + hiss) * env).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# Preset-Driven Environmental Soundscape Renderer
# ---------------------------------------------------------------------------------------------

def _turbulence(n, sr, rng, corner_hz):
    """Unit-variance gust series: PSD ~ (1+(f/fc)^2)^(-5/6), the -5/3 turbulence slope above fc (von Karman/Kaimal)."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / sr)
    spec *= (1.0 + (f / max(1e-3, corner_hz)) ** 2) ** (-5.0 / 12.0)
    spec[0] = 0.0
    z = np.fft.irfft(spec, n)
    return (z / max(1e-9, z.std())).astype(np.float32)


def synth_rain(sec, sr=SR, rng=None, rate_mm_h=5.0, surface='water', bubble_prob=0.35, drops_per_s=None):
    """Physical rain: Marshall-Palmer drop sizes, a damped impact ring per drop, plus a Minnaert bubble on water.

    Sizes: N(D)=N0 exp(-L D), L = 4.1 R^-0.21 per mm (R mm/h); fall speed v = 3.778 D^0.67 m/s. Bubble pitch
    f = 3.26 / a (a = radius in m) rising a few percent as it rings. Solid surfaces get the impact only.
    shortcut: audible drops/s (30*sqrt(R)) and the impact-frequency ranges are tuned by ear, not measured;
    tune them against a reference recording when one exists.
    """
    rng = rng or np.random.default_rng(909)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float32)
    lam = 4.1 * max(0.05, float(rate_mm_h)) ** -0.21
    rate = float(drops_per_s) if drops_per_s else float(np.clip(30.0 * np.sqrt(max(0.05, rate_mm_h)), 10.0, 600.0))
    # (impact f range Hz, impact decay 1/s, loudness)
    f_rng, beta, loud = {'water': ((2000.0, 12000.0), 2500.0, 1.0), 'solid': ((3000.0, 10000.0), 1800.0, 1.2),
                         'leaf': ((800.0, 4000.0), 900.0, 0.7)}.get(surface, ((2000.0, 12000.0), 2500.0, 1.0))
    ev_len = int(0.025 * sr)
    t = np.arange(ev_len) / sr
    for pos in rng.integers(0, max(1, n - ev_len - 1), int(sec * rate)):
        d = float(np.clip(0.3 + rng.exponential(1.0 / lam), 0.3, 6.0))
        amp = loud * 3.778 * d ** 0.67 * d ** 2 / 60.0            # momentum-like, ~1 for a 4 mm drop
        f_i = float(rng.uniform(*f_rng))
        ev = amp * np.exp(-beta * t) * np.sin(2 * np.pi * f_i * t)
        if surface == 'water' and rng.random() < bubble_prob:
            f_b = min(sr * 0.45, 3.26 / float(rng.uniform(0.25, 1.0) * 1e-3))
            ev = ev + 1.8 * amp * np.exp(-t / 0.004) * np.sin(2 * np.pi * f_b * t * (1.0 + 3.0 * t))
        out[pos:pos + ev_len] += (ev * float(rng.uniform(0.7, 1.0))).astype(np.float32)
    return (out / max(1e-6, float(np.max(np.abs(out)))) * 0.8).astype(np.float32)


def synth_cricket_chorus(sec, sr=SR, rng=None, voices=5, temp_c=20.0, carrier_hz=2300.0,
                         syllables=8, syl_ms=17.0, gap_ms=2.0):
    """Cricket chorus: each chirp is N amplitude-ramped pure-tone syllables; chirp rate follows temperature.

    Rate = (deg F - 40) / 15 chirps per second (Dolbear's law).
    shortcut: Dolbear holds well only for the snowy tree cricket (about 13-30 C); other species need their own
    rate and carrier, so pass carrier_hz / syllables for them.
    """
    rng = rng or np.random.default_rng(1001)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float32)
    rate0 = max(0.3, (temp_c * 9.0 / 5.0 + 32.0 - 40.0) / 15.0)
    syl_n, gap_n = int(syl_ms / 1000 * sr), int(gap_ms / 1000 * sr)
    t = np.arange(syl_n) / sr
    ramp = np.sin(np.pi * np.arange(syl_n) / syl_n) ** 2
    for _ in range(int(voices)):
        f = carrier_hz * rng.uniform(0.94, 1.06)
        syl = ramp * np.sin(2 * np.pi * f * t)
        chirp = np.concatenate([np.concatenate([syl, np.zeros(gap_n)]) for _ in range(int(syllables))])
        period = sr / (rate0 * rng.uniform(0.93, 1.07))
        pos = rng.uniform(0, period)
        while pos + len(chirp) < n:
            i0 = int(pos)
            out[i0:i0 + len(chirp)] += chirp * float(rng.uniform(0.6, 1.0)) * 0.3
            pos += period * rng.uniform(0.97, 1.03)
    return out


def synth_bird_chorus(sec, sr=SR, rng=None, species=5, f_lo=1500.0, f_hi=7500.0, event_rate=0.5, dawn_s=0.0,
                      mod_rate_hz=24.0, mod_depth_hz=22.0, aspiration_gain=0.025, echo_ms=38.0, echo_db=-12.0, echo_lp_hz=3200.0):
    """Several species, each in its own log-spaced frequency band (acoustic niche partitioning, Krause).

    dawn_s > 0 ramps the whole chorus in over that many seconds, like a dawn chorus building.
    The call keys (mod_*, aspiration_gain, echo_*) go to every species' calls; see synth_fm_chirp_cluster.
    """
    rng = rng or np.random.default_rng(1103)
    n = int(sec * sr)
    edges = np.geomspace(f_lo, f_hi, int(species) + 1)
    out = np.zeros(n, dtype=np.float32)
    for i in range(int(species)):
        sub = np.random.default_rng(int(rng.integers(1 << 31)))
        out += synth_fm_chirp_cluster(sec, sr, sub, f0_low=float(edges[i] * 1.04), f0_high=float(edges[i + 1] / 1.04),
                                      event_rate=event_rate * float(rng.uniform(0.6, 1.4)), mod_rate_hz=mod_rate_hz,
                                      mod_depth_hz=mod_depth_hz, aspiration_gain=aspiration_gain, echo_ms=echo_ms,
                                      echo_db=echo_db, echo_lp_hz=echo_lp_hz)
    if dawn_s > 0:
        x = np.clip(np.arange(n) / sr / dawn_s, 0.0, 1.0)
        out *= (0.15 + 0.85 * x * x * (3 - 2 * x)).astype(np.float32)
    return out / max(1, species) ** 0.5


def _bout_starts(sec, rng, per_min, first_s=None, min_gap_s=2.0):
    """Start times (s) of calls that come about `per_min` times a minute, never closer than min_gap_s."""
    mean_gap = 60.0 / max(0.05, per_min)
    t = float(first_s) if first_s is not None else float(rng.uniform(0.2, 0.6) * mean_gap)
    out = []
    while t < sec - 0.5:
        out.append(t)
        t += max(min_gap_s, mean_gap * float(rng.uniform(0.7, 1.3)))
    return out


def synth_voice_bouts(sec, sr=SR, rng=None, bouts_per_min=1.0, bout_s=(3.0, 6.0), f0_hz=100.0, f0_contour=(1.0, 1.0),
                      jitter=0.02, harmonics=30, rolloff=1.2, formants_hz=(), formant_weights=(), breath=0.0,
                      chop_hz=0.0, chop_depth=0.0, first_s=None):
    """Bouts of a pitched, formant-filtered voice: a harmonic stack on a gliding f0 with jitter, optional breath noise,
    optional formant resonators and optional pulsing. Animal calls, roars, humming crowds: all of it comes from the preset.

    f0_contour = (multiplier at the start, multiplier at the end) of each bout; formants_hz / formant_weights are the
    resonances (empty = unfiltered); chop_hz / chop_depth pulse the loudness. The peak of the whole layer is 0.5, so gain_db
    is relative to that.
    shortcut: one voice per bout; for a chorus raise bouts_per_min or stack two layers with different seeds.
    """
    rng = rng or np.random.default_rng(1301)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float32)
    sos = [signal.butter(2, [fc * 0.8, fc * 1.25], btype='bandpass', fs=sr, output='sos') for fc in formants_hz]
    w = list(formant_weights) + [1.0] * (len(sos) - len(formant_weights))
    for t0 in _bout_starts(sec, rng, bouts_per_min, first_s, min_gap_s=float(bout_s[1]) + 2.0):
        m = min(int(rng.uniform(*bout_s) * sr), n - int(t0 * sr))
        if m < sr // 4:
            continue
        x = np.arange(m) / m
        jit = signal.sosfilt(signal.butter(1, 12.0, fs=sr, output='sos'), rng.standard_normal(m)) * jitter
        f0 = f0_hz * (f0_contour[0] + (f0_contour[1] - f0_contour[0]) * x) * (1.0 + jit)
        phase = 2 * np.pi * np.cumsum(f0) / sr
        top = int(min(harmonics, 0.45 * sr / f0_hz))
        src = sum(np.sin(h * phase) / h ** rolloff for h in range(1, top + 1)) + breath * 0.25 * rng.standard_normal(m)
        voiced = sum(wi * signal.sosfilt(s, src) for wi, s in zip(w, sos)) if sos else src
        pulse = 1.0 - chop_depth + chop_depth * (0.5 + 0.5 * np.sin(2 * np.pi * chop_hz * np.arange(m) / sr)) if chop_hz else 1.0
        seg = voiced * np.sin(np.pi * x) ** 0.8 * pulse
        seg /= max(1e-9, np.abs(seg).max())
        i0 = int(t0 * sr)
        out[i0:i0 + m] += seg.astype(np.float32)
    return out * 0.5 / max(1e-9, float(np.abs(out).max())) if out.any() else out


def synth_syllable_bouts(sec, sr=SR, rng=None, bouts_per_min=6.0, syl_per_bout=(3, 8), f_start_hz=3400.0, f_end_hz=1700.0,
                         spread=0.08, sweep_shape=0.8, syl_ms=(70.0, 170.0), gap_ms=(60.0, 160.0), harmonics=3,
                         vibrato_hz=0.0, vibrato_depth=0.0, saturation=1.6, noise=0.02, first_s=None):
    """Bouts of short swept tonal syllables: whistles, squeaks, chirps, clicks of a tone. Each syllable glides from f_start_hz
    to f_end_hz (up or down) with optional vibrato, a few harmonics and soft saturation; bouts are Poisson in time.

    spread randomises the two end frequencies per syllable (fraction); sweep_shape < 1 front-loads the glide.
    The peak of the whole layer is 0.5, so gain_db is relative to that.
    shortcut: a call shape, not a species model; the preset carries the numbers, tune them by ear.
    """
    rng = rng or np.random.default_rng(1303)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float32)
    for t0 in _bout_starts(sec, rng, bouts_per_min, first_s, min_gap_s=2.5):
        pos = int(t0 * sr)
        for _ in range(int(rng.integers(syl_per_bout[0], syl_per_bout[1] + 1))):
            m = int(rng.uniform(*syl_ms) / 1000 * sr)
            if pos + m >= n:
                break
            x = np.arange(m) / m
            a = f_start_hz * float(rng.uniform(1 - spread, 1 + spread))
            b = f_end_hz * float(rng.uniform(1 - spread, 1 + spread))
            f = a * (b / a) ** (x ** sweep_shape) * (1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_hz * x * m / sr))
            phase = 2 * np.pi * np.cumsum(f) / sr
            tone = sum(np.sin(h * phase) / h ** 1.5 for h in range(1, int(harmonics) + 1) if h * float(f.max()) < 0.45 * sr)
            seg = np.tanh(saturation * tone) * np.sin(np.pi * x) ** 0.6
            out[pos:pos + m] += (0.7 * seg + noise * rng.standard_normal(m) * np.sin(np.pi * x)).astype(np.float32)
            pos += m + int(rng.uniform(*gap_ms) / 1000 * sr)
    return out * 0.5 / max(1e-9, float(np.abs(out).max())) if out.any() else out


# ---------------------------------------------------------------------------------------------
# Primitive registry. ONE table decides what a layer can say: a layer's keys are the primitive's own parameters, and the
# defaults live in the function signatures only. To add a primitive: write the function above, add one line here.
# `python environment.py --primitives` prints every name, its parameters and defaults.
# ---------------------------------------------------------------------------------------------
def synth_model_layer(sec, sr=SR, rng=None, voices=None, free=None):
    """Any sound as data: a stack of voices (excitation -> resonator -> events), see sound_model.py laws. Rain on a roof, a frog
    chorus, a creaking door, boiling water: choose the parts and their numbers in the preset, not a recipe in code.
    `free` lists the parameters sound_fit.py may move to match a real recording; it does not change the render."""
    import sound_model
    rng = rng if rng is not None else np.random.default_rng(0)
    model = dict(seconds=float(sec), voices=voices or sound_model.DEFAULT_VOICES)
    return sound_model.render(model, sr, int(rng.integers(0, 2 ** 31 - 1))).astype(np.float32)


PRIMITIVES = {
    'noise_bed': synth_noise_bed, 'resonant_gust': synth_resonant_gust, 'fm_chirp_cluster': synth_fm_chirp_cluster,
    'impulse_cluster': synth_impulse_cluster, 'stridulation_bed': synth_stridulation_bed, 'water_flow': synth_water_flow,
    'formant_babble': synth_formant_babble, 'doppler_sweep': synth_doppler_sweep, 'rain_physical': synth_rain,
    'cricket_chorus': synth_cricket_chorus, 'bird_chorus': synth_bird_chorus, 'voice_bouts': synth_voice_bouts,
    'syllable_bouts': synth_syllable_bouts, 'model_layer': synth_model_layer,
}
ALIASES = {   # older names that still work
    'canopy_birds': 'fm_chirp_cluster', 'tropical_birds': 'fm_chirp_cluster', 'birds': 'fm_chirp_cluster',
    'birdsong': 'fm_chirp_cluster', 'rain_drops': 'impulse_cluster', 'rain': 'impulse_cluster', 'water_drip': 'impulse_cluster',
    'footsteps': 'impulse_cluster', 'clatter': 'impulse_cluster', 'insects': 'stridulation_bed', 'cicadas': 'stridulation_bed',
    'crickets': 'stridulation_bed', 'water_surf': 'water_flow', 'waves': 'water_flow', 'river': 'water_flow',
    'waterfall': 'water_flow', 'gust': 'resonant_gust', 'howling_wind': 'resonant_gust', 'sand_drift': 'resonant_gust',
    'crowd': 'formant_babble', 'babble': 'formant_babble', 'bazaar': 'formant_babble', 'chatter': 'formant_babble',
    'car_pass': 'doppler_sweep', 'traffic_pass': 'doppler_sweep', 'siren': 'doppler_sweep',
}
# keys the renderer itself reads from a layer (the rest must be the primitive's own parameters)
LAYER_KEYS = {'name', 'primitive', 'type', 'kind', 'gain_db', 'gain_curve', 'spatial', 'decorrelate', 'decorrelate_radius',
              'trajectory', 'pan', 'normalize', 'diffuse', 'atmosphere', 'physical', 'species'}
BLENDING_KEYS = {'high_pass_hz', 'vocal_pocket_notch_hz', 'vocal_pocket_notch_db', 'target_lufs', 'overall_gain_db'}
KINDS = ('bed', 'spot')         # bed: steady, wide, nothing recognisable in it. spot: an event with a place of its own
EVENT_PRIMITIVES = {'fm_chirp_cluster', 'impulse_cluster', 'cricket_chorus', 'bird_chorus', 'voice_bouts', 'syllable_bouts',
                    'doppler_sweep'}
EVENT_RADIUS = 0.86             # allpass radius for decorrelating spots / event primitives: short ring, so syllables stay clean
BED_RADIUS = 0.985


def _params(fn):
    return [p for p in inspect.signature(fn).parameters if p not in ('sec', 'sr', 'rng')]


def resolve_primitive(lyr):
    """Canonical primitive name of a layer, or None when its name is unknown."""
    prim = lyr.get('primitive') or lyr.get('type') or 'noise_bed'
    if prim in ('rain', 'rain_drops') and lyr.get('physical'):
        return 'rain_physical'
    if prim in ('crickets', 'insects') and lyr.get('species') == 'cricket':
        return 'cricket_chorus'
    return prim if prim in PRIMITIVES else ALIASES.get(prim)


def layer_problems(lyr):
    """Plain-language problems of one layer: unknown primitive, keys no primitive reads, bad kind or gain_curve."""
    prim = lyr.get('primitive') or lyr.get('type') or 'noise_bed'
    label = f'layer "{lyr.get("name", prim)}"'
    canon = resolve_primitive(lyr)
    if canon is None:
        return [f'{label}: unknown primitive "{prim}" (it would render as a pink noise bed). Valid: {", ".join(sorted(PRIMITIVES))}; '
                f'older names: {", ".join(sorted(ALIASES))}']
    out = []
    valid = set(_params(PRIMITIVES[canon])) | LAYER_KEYS
    bad = sorted(k for k in lyr if k not in valid)
    if bad:
        out.append(f'{label} ({canon}): key(s) {bad} are never read. Valid keys: {", ".join(sorted(valid))}')
    if canon == 'model_layer':
        import sound_model
        out += [f'{label}: {p}' for p in sound_model.problems(dict(seconds=1.0, voices=lyr.get('voices') or sound_model.DEFAULT_VOICES))]
    if 'kind' in lyr and lyr['kind'] not in KINDS:
        out.append(f'{label}: kind "{lyr["kind"]}" must be one of {KINDS}')
    gc = lyr.get('gain_curve')
    if gc is not None:
        ok = isinstance(gc, list) and len(gc) >= 2 and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in gc) \
            and all(gc[i][0] < gc[i + 1][0] for i in range(len(gc) - 1))
        if not ok:
            out.append(f'{label}: gain_curve must be [[seconds, dB], ...] with rising seconds, at least two points')
    return out


LEGACY_NAMES = ('rain', 'rain_drops', 'water_drip', 'birdsong', 'birds', 'crickets', 'insects')   # old fixed-recipe names


def legacy_alias_warnings(cfg):
    """Layers that use an older fixed-recipe name. They still render (same keys, same sound); the named primitive
    is the one to write, because it exposes rate, surface and species. Never blocks."""
    out = []
    for lyr in cfg.get('layers', []):
        prim = lyr.get('primitive') or lyr.get('type')
        canon = resolve_primitive(lyr)
        if prim in LEGACY_NAMES and canon and canon != prim:
            hint = ' (rain_physical: rate_mm_h, surface water|solid|leaf)' if prim in ('rain', 'rain_drops') else ''
            out.append(f'layer "{lyr.get("name", prim)}": "{prim}" is an older name for {canon}; write primitive "{canon}"{hint}')
    return out


def preset_problems(cfg):
    """Every problem of an environment preset (a dict): its layers and its blending keys.

    A preset may also be a physical scene (`scene`, or `scene_layers`: a list of scenes mixed as one bed). Those go to
    phys_core for validation, and nothing is validated twice.
    """
    if isinstance(cfg.get('scene'), dict):
        import phys_core.scene as _scene
        return [f'scene: {p}' for p in _scene.problems(cfg['scene'])]
    if cfg.get('scene_layers'):
        import phys_core.scene as _scene
        out = []
        for i, layer in enumerate(cfg['scene_layers']):
            out += [f'scene_layers[{i}]: {p}' for p in _scene.problems(layer.get('scene') or {})]
        return out
    out = []
    for lyr in cfg.get('layers', []):
        out += layer_problems(lyr)
    bad = sorted(k for k in cfg.get('blending', {}) if k not in BLENDING_KEYS)
    if bad:
        out.append(f'blending key(s) {bad} are never read. Valid: {", ".join(sorted(BLENDING_KEYS))}')
    return out


def _complain(problems):
    """Project mode (presets.STRICT): a bad layer or key is an error. Otherwise print it and keep the old behaviour."""
    if not problems:
        return
    if presets.STRICT:
        raise ValueError('environment preset: ' + '; '.join(problems))
    for p in problems:
        print(f'[environment] WARNING {p}', file=sys.stderr)


def preset_is_bed(cfg):
    """True when an environment preset describes a place that keeps sounding (the bed the project gate asks for):
    a layer whose kind is 'bed', several physical scenes mixed as one bed (`scene_layers`), or one scene built from
    a continuous mechanism (flow, foliage, granular, rolling, gait, repeated impact). A one-shot scene is a spot.

    One owner for the rule: project_gate, the docs and any caller ask this instead of reading `layers` themselves."""
    if not isinstance(cfg, dict):
        return False
    if cfg.get('scene') or cfg.get('scene_layers'):
        import env_engine.render as _env_render
        return _env_render.is_bed(cfg)
    for lyr in cfg.get('layers', []):
        kind = lyr.get('kind', 'spot' if resolve_primitive(lyr) in EVENT_PRIMITIVES else 'bed')
        if kind == 'bed':
            return True
    return False


def list_primitives():
    """Text table of every primitive: parameters with defaults, aliases, first line of its doc."""
    lines = []
    for name, fn in sorted(PRIMITIVES.items()):
        alias = sorted(a for a, c in ALIASES.items() if c == name)
        sig = inspect.signature(fn).parameters
        params = ', '.join(f'{p}={sig[p].default!r}' for p in _params(fn))
        doc = (inspect.getdoc(fn) or '').splitlines()[0] if inspect.getdoc(fn) else ''
        lines.append(f'{name}' + (f'   (also: {", ".join(alias)})' if alias else '') + f'\n    {doc}\n    params: {params}')
    lines.append('\nlayer keys read by the renderer: ' + ', '.join(sorted(LAYER_KEYS)) + f'\nkind: {" | ".join(KINDS)}'
                 '   gain_curve: [[seconds, dB], ...]   decorrelate_radius: allpass radius (beds 0.985, spots/events 0.86)')
    return '\n'.join(lines)


def decorrelate(mono, sr=SR, seed=0, stages=32, f_lo=100.0, f_hi=16000.0, r_hi=0.985):
    """Mono -> (N, 2) with low inter-channel correlation, using cascaded allpass biquads on an ERB scale.

    Allpass keeps the magnitude spectrum, so the mono fold-down stays close in level (no Haas comb notches).
    Measured on white noise: L/R correlation ~0.35, mono sum ~-1.7 dB. High radii (r_hi) ring, so beds (rain wash, wind)
    keep 0.985 and event layers (calls, syllables, bubbles) use a lower r_hi such as 0.86 (see EVENT_RADIUS).
    """
    erb = lambda f: 21.4 * np.log10(1.0 + 0.00437 * f)
    inv = lambda e: (10.0 ** (e / 21.4) - 1.0) / 0.00437
    centres = inv(np.linspace(erb(f_lo), erb(f_hi), int(stages)))
    chans = []
    for ch in (0, 1):
        r = np.random.default_rng(seed * 2 + ch)
        sos = []
        for fc in centres:
            w = 2 * np.pi * float(fc) * r.uniform(0.9, 1.1) / sr
            rad = float(r.uniform(r_hi - 0.085, r_hi))
            c = -2.0 * rad * np.cos(w)
            sos.append([rad * rad, c, 1.0, 1.0, c, rad * rad])
        chans.append(signal.sosfilt(np.array(sos), mono))
    return np.stack(chans, axis=1).astype(np.float32)


def _pan_stereo(mono, pan_val):
    """Clean constant-power stereo panning (-1.0 left to +1.0 right)."""
    p = np.clip(float(pan_val), -1.0, 1.0)
    angle = (p + 1.0) * (np.pi / 4.0)
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1).astype(np.float32)


def render_environment_preset(name_or_dict, duration_s=30.0, sr=SR, seed=42):
    """Renders any environmental soundscape preset driven entirely by JSON configuration."""
    if isinstance(name_or_dict, dict):
        cfg = name_or_dict
    else:
        cfg = presets.find_environment(name_or_dict)
        if not cfg:
            preset_file = os.path.join(os.path.dirname(__file__), '..', 'references', 'presets', 'environments', f'{name_or_dict}.json')
            if os.path.exists(preset_file):
                with open(preset_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            else:
                known = ', '.join(sorted(presets.load('environments')))
                raise ValueError(f'unknown environment "{name_or_dict}" (it would render as silence). Known: {known}')

    if isinstance(cfg.get('scene'), dict) or cfg.get('scene_layers'):
        import env_engine.render as _env_render       # the physical scene path; the layer path below is unchanged
        return _env_render.render_preset(cfg, duration_s=duration_s, sr=sr, seed=seed)

    rng = np.random.default_rng(seed)
    n = int(duration_s * sr)
    out_stereo = np.zeros((n, 2), dtype=np.float32)
    
    layers = cfg.get('layers', [])
    for lyr in layers:
        prim = lyr.get('primitive') or lyr.get('type', 'noise_bed')
        _complain(layer_problems(lyr))         # project mode stops here; legacy mode prints and carries on
        canon = resolve_primitive(lyr) or 'noise_bed'
        fn = PRIMITIVES[canon]
        gain_db = float(lyr.get('gain_db', -18.0))
        gain_lin = 10.0 ** (gain_db / 20.0)

        kw = {k: lyr[k] for k in _params(fn) if k in lyr and not (k == 'species' and canon != 'bird_chorus')}
        if canon == 'cricket_chorus' and 'temp_c' not in kw:
            kw['temp_c'] = float((lyr.get('atmosphere') or cfg.get('atmosphere') or {}).get('temp_c', 20.0))
        mono = fn(duration_s, sr, rng, **kw)

        # new physical primitives are brought to a common RMS first, so gain_db means the same for each of them.
        # Every bed primitive is on this scale now (a cicada layer and an air layer used to sit on different axes).
        # `normalize: "none"` is the explicit opt-out for a layer whose own level is the point.
        do_norm = (canon in NORMALIZED or bool(lyr.get('physical')) or lyr.get('species') == 'cricket'
                   or bool(lyr.get('turbulence')))
        nrm = lyr.get('normalize')
        if isinstance(nrm, str):
            do_norm = nrm.strip().lower() not in ('none', 'off', 'raw')
        elif isinstance(nrm, bool):
            do_norm = nrm
        if do_norm:
            mono = mono / max(1e-9, float(np.sqrt(np.mean(mono ** 2)))) * 0.1
        mono *= gain_lin
        gc = lyr.get('gain_curve')             # [[seconds, dB], ...]: the layer's level over time, on top of gain_db
        if gc:
            mono *= (10.0 ** (np.interp(np.arange(len(mono)) / sr, [p[0] for p in gc], [p[1] for p in gc]) / 20.0)).astype(mono.dtype)
        
        # Distance air absorption (physics-based high frequency attenuation)
        sp = lyr.get('spatial', {})
        dist = max(0.5, float(sp.get('distance', 2.0)))
        atm = lyr.get('atmosphere') or cfg.get('atmosphere')   # {"temp_c": 20, "rh": 50} -> real ISO 9613-1
        if atm and dist > 1.0:
            mono = airabs.apply(mono, dist - 1.0, temp_c=float(atm.get('temp_c', 20.0)),
                                rh=float(atm.get('rh', 50.0)), sr=sr)
        elif dist > 2.0:
            cutoff = max(3200.0, min(sr * 0.45, 22000.0 / (1.0 + 0.35 * (dist - 2.0))))
            sos_air = signal.butter(1, cutoff, btype='lowpass', fs=sr, output='sos')
            mono = signal.sosfilt(sos_air, mono).astype(np.float32)

        # 3D Spatial Pan & Distribution
        traj = lyr.get('trajectory')
        dec = float(np.clip(float(lyr.get('decorrelate', 0.0)), 0.0, 1.0))
        if dec > 0 and not traj:
            p = np.sin(np.radians(float(sp['azimuth']))) if 'azimuth' in sp else float(lyr.get('pan', 0.0))
            ang = (np.clip(p, -1.0, 1.0) + 1.0) * (np.pi / 4.0)
            spot = lyr.get('kind', 'spot' if canon in EVENT_PRIMITIVES else 'bed') == 'spot'
            r_hi = float(lyr.get('decorrelate_radius', EVENT_RADIUS if spot else BED_RADIUS))
            wide = decorrelate(mono, sr, seed=int(rng.integers(1 << 20)), r_hi=r_hi) * np.array([np.cos(ang), np.sin(ang)], np.float32)
            stereo_layer = dec * wide + (1.0 - dec) * _pan_stereo(mono, p)
        elif traj:
            az0 = float(traj.get('start_azimuth', -60.0))
            az1 = float(traj.get('end_azimuth', 60.0))
            pan_curve = np.linspace(np.sin(np.radians(az0)), np.sin(np.radians(az1)), n)
            angle = (pan_curve + 1.0) * (np.pi / 4.0)
            stereo_layer = np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1)
        elif lyr.get('diffuse', False) or prim in ('rain_drops', 'rain'):
            # Ambient diffuse scatter across stereo field
            pan_r = rng.uniform(-0.85, 0.85, n)
            angle = (pan_r + 1.0) * (np.pi / 4.0)
            stereo_layer = np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1)
        elif sp:
            az = float(sp.get('azimuth', 0.0))
            stereo_layer = _pan_stereo(mono, np.sin(np.radians(az)))
        else:
            pan_val = float(lyr.get('pan', 0.0))
            stereo_layer = _pan_stereo(mono, pan_val)
            
        if len(stereo_layer) != n:             # a primitive's own rounding can land 1 sample off duration_s*sr
            if len(stereo_layer) < n:
                stereo_layer = np.pad(stereo_layer, ((0, n - len(stereo_layer)), (0, 0)))
            else:
                stereo_layer = stereo_layer[:n]
        out_stereo += stereo_layer
        
    # Spectral unmasking according to preset's blending configuration
    blend = cfg.get('blending', {})
    hp_hz = float(blend.get('high_pass_hz', 0.0))
    if hp_hz > 20:
        out_stereo[:, 0] = _highpass(out_stereo[:, 0], hp_hz, sr)
        out_stereo[:, 1] = _highpass(out_stereo[:, 1], hp_hz, sr)
        
    notch_hz = float(blend.get('vocal_pocket_notch_hz', 0.0))
    if notch_hz > 100:
        notch_db = float(blend.get('vocal_pocket_notch_db', -3.5))
        b, a = signal.iirnotch(min(sr * 0.45, notch_hz), 3.0, fs=sr)
        g_notch = 10.0 ** (notch_db / 20.0)
        out_stereo[:, 0] = (1.0 - g_notch) * signal.lfilter(b, a, out_stereo[:, 0]) + g_notch * out_stereo[:, 0]
        out_stereo[:, 1] = (1.0 - g_notch) * signal.lfilter(b, a, out_stereo[:, 1]) + g_notch * out_stereo[:, 1]

    # Target loudness or gain scaling from preset
    target_lufs = blend.get('target_lufs')
    if target_lufs is not None:
        target_rms = 10.0 ** (float(target_lufs) / 20.0) * 0.5
        current_rms = np.sqrt(np.mean(out_stereo ** 2) + 1e-12)
        if current_rms > 1e-6:
            out_stereo *= (target_rms / current_rms)
    else:
        overall_db = float(blend.get('overall_gain_db', 0.0))
        out_stereo *= (10.0 ** (overall_db / 20.0))
        
    return out_stereo.astype(np.float32)


def apply_environmental_acoustics(stereo_audio, sr=SR, distance_m=10.0, ir_path=None):
    """Apply physical distance dampening and room/outdoor convolution acoustics via Pedalboard."""
    x = stereo_audio.T.copy() if stereo_audio.ndim == 2 else np.stack([stereo_audio, stereo_audio], axis=0)
    chain = []
    
    # Distance high-frequency air dampening (ISO 9613-1 acoustic absorption)
    if distance_m > 5.0:
        roll_off_hz = max(1200.0, 10000.0 - (distance_m * 120.0))
        chain.append(pb.LowpassFilter(cutoff_frequency_hz=roll_off_hz))
        chain.append(pb.HighShelfFilter(cutoff_frequency_hz=6000.0, gain_db=-min(12.0, distance_m * 0.15), q=0.7))
        
    # Impulse response convolution if provided
    if ir_path and os.path.exists(ir_path):
        ir_data, ir_sr = sf.read(ir_path)
        ir_arr = ir_data.T.copy() if ir_data.ndim == 2 else np.stack([ir_data, ir_data], axis=0)
        chain.append(pb.Convolution(ir_arr, mix=0.35, sample_rate=ir_sr))
        
    if not chain:
        return stereo_audio
        
    board = pb.Pedalboard(chain)
    out = board(x, sr)
    return out.T.astype(np.float32)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('preset', nargs='?', help='Name of environment preset or path to JSON file')
    ap.add_argument('--primitives', action='store_true', help='List every primitive, its parameters and defaults, then exit')
    ap.add_argument('--seconds', type=float, default=10.0, help='Duration in seconds')
    ap.add_argument('--out', default='environment_out.wav', help='Output WAV path')
    args = ap.parse_args()
    if args.primitives:
        print(list_primitives())
        return
    if not args.preset:
        ap.error('give a preset name, or --primitives')
    audio = render_environment_preset(args.preset, duration_s=args.seconds)
    sf.write(args.out, audio, SR, subtype='PCM_16')
    print(f'Wrote environmental soundscape: {args.out} ({len(audio)/SR:.1f} s, shape {audio.shape})')


if __name__ == '__main__':
    main()
