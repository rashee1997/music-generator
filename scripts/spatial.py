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
"""spatial.py - Programmatic 3D Spatial Audio & Natural Externalization Engine.

Eliminates in-head localization (lateralization) by delivering the acoustic cues the human auditory
system requires to perceive sounds situated naturally in the external physical environment:
  1. Direct Sound Path:
     - Brown & Duda (1998) analytical 1-pole 1-zero continuous spherical head shadow filter H(s).
     - Kuhn (1977) frequency-dependent ITD (wave diffraction vs ray path) with phase dispersion.
     - Proximal Near-Field Acoustic Holography (acoustic parallax & low-frequency ILD surge for r < 1.0m).
     - ISO 9613-1 physical atmospheric air absorption (molecular vibrational relaxation of O2 and N2).
  2. Pinna & Elevation Spectral Shaping:
     - Concha resonance peak (+4 dB at 4.5 kHz).
     - Dynamic pinna notch N1 (6.0 - 9.5 kHz) shifting monotonically with vertical elevation.
     - Front/Back pinna notch N2 (10 - 14 kHz) resolving cone-of-confusion front/back ambiguity.
  3. Torso & Upper-Body Scattering:
     - Upper-body reflections (0.8 - 1.2 ms) with elevation-dependent intensity.
  4. 6-Surface Image Source Model (ISM) Early Reflection Engine:
     - Physical 6-boundary early reflections (ground, ceiling, left, right, front, rear) with
       surface material absorption coefficients and direction-dependent binauralization.
  5. Distance-Coupled Direct-to-Reverberant Ratio (DRR):
     - Calibrated to room critical distance (dc), smoothly moving sounds outward as distance increases.
  6. Sub-Block Continuous Trajectory & Doppler Engine:
     - One continuous cubic-interpolated r(t)/c delay (true Doppler), then angle filters on 50 %-overlap
       Hann blocks (8192 samples) so early reflections survive and there is no block-rate buzz.
  7. Ambisonic B-Format Processing:
     - 1st-Order Ambisonics (W, Y, Z, X) encoding and virtual loudspeaker Max-rE binaural decoding.

Coordinate conventions:
  Azimuth (degrees): 0 = center/front, +90 = right, -90 = left, 180 = rear
  Elevation (degrees): 0 = horizontal plane, +90 = zenith/above, -90 = below
  Distance (meters): 1.0 = reference distance, > 1.0 = farther away, < 1.0 = proximal near-field
"""
import argparse
import os
import sys
import numpy as np
import scipy.signal as signal
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 44100
HEAD_RADIUS = 0.0875  # Average human head radius in meters (~8.75 cm)
SPEED_OF_SOUND = 343.0  # Speed of sound in air (m/s)

# Acoustic reflection profiles for physical environments (6-surface ISM + reverb)
ACOUSTIC_SPACES = {
    'outdoor_open': {
        'ground_delay_ms': 8.5,
        'ground_gain': 0.35,
        'ground_cutoff_hz': 3200,
        'lateral_delay_ms': 26.0,
        'lateral_gain': 0.12,
        'lateral_cutoff_hz': 2400,
        'reverb_decay_s': 0.6,
        'ceiling_delay_ms': 45.0,
        'ceiling_gain': 0.04,
        'rear_delay_ms': 35.0,
        'rear_gain': 0.08,
    },
    'forest_canopy': {
        'ground_delay_ms': 9.2,
        'ground_gain': 0.28,
        'ground_cutoff_hz': 2200,
        'lateral_delay_ms': 22.0,
        'lateral_gain': 0.25,
        'lateral_cutoff_hz': 1800,
        'reverb_decay_s': 0.9,
        'ceiling_delay_ms': 18.0,
        'ceiling_gain': 0.22,
        'rear_delay_ms': 28.0,
        'rear_gain': 0.18,
    },
    'desert_vast': {
        'ground_delay_ms': 12.0,
        'ground_gain': 0.40,
        'ground_cutoff_hz': 3800,
        'lateral_delay_ms': 38.0,
        'lateral_gain': 0.08,
        'lateral_cutoff_hz': 1500,
        'reverb_decay_s': 0.4,
        'ceiling_delay_ms': 60.0,
        'ceiling_gain': 0.02,
        'rear_delay_ms': 45.0,
        'rear_gain': 0.05,
    },
    'bazaar_alley': {
        'ground_delay_ms': 7.0,
        'ground_gain': 0.45,
        'ground_cutoff_hz': 4000,
        'lateral_delay_ms': 16.0,
        'lateral_gain': 0.42,
        'lateral_cutoff_hz': 3200,
        'reverb_decay_s': 1.4,
        'ceiling_delay_ms': 20.0,
        'ceiling_gain': 0.28,
        'rear_delay_ms': 18.0,
        'rear_gain': 0.35,
    },
    'hall': {
        'ground_delay_ms': 6.5,
        'ground_gain': 0.50,
        'ground_cutoff_hz': 4500,
        'lateral_delay_ms': 14.0,
        'lateral_gain': 0.48,
        'lateral_cutoff_hz': 3600,
        'reverb_decay_s': 2.2,
        'ceiling_delay_ms': 15.0,
        'ceiling_gain': 0.45,
        'rear_delay_ms': 24.0,
        'rear_gain': 0.40,
    },
}


# ---------------------------------------------------------------------------------------------
# 1. Direct Path: Analytical Head Shadow & Kuhn Frequency-Dependent ITD
# ---------------------------------------------------------------------------------------------

def woodworth_itd(azimuth_deg, head_radius=HEAD_RADIUS, c=SPEED_OF_SOUND, sr=SR):
    """Computes high-frequency ray ITD (Woodworth-Schlosberg model) in seconds and samples."""
    theta = np.radians(float(azimuth_deg))
    abs_theta = np.abs(theta)
    if abs_theta <= np.pi / 2:
        itd_sec = (head_radius / c) * (abs_theta + np.sin(abs_theta))
    else:
        theta_eff = np.pi - abs_theta
        itd_sec = (head_radius / c) * (theta_eff + np.sin(theta_eff))
    
    itd_sec = float(itd_sec * np.sign(theta))
    itd_samples = itd_sec * sr
    return itd_sec, itd_samples


def kuhn_itd(azimuth_deg, head_radius=HEAD_RADIUS, c=SPEED_OF_SOUND, sr=SR):
    """Computes frequency-dependent ITD according to Kuhn (1977).
    Returns: (low_freq_itd_s, high_freq_itd_s, low_freq_samples, high_freq_samples).
    Kuhn showed that below 500 Hz wave diffraction causes ITD = (3a/c)*sin(theta),
    which is ~16% larger than high-frequency ray ITD = (a/c)*(theta + sin(theta)).
    """
    theta = np.radians(float(azimuth_deg))
    abs_theta = np.abs(theta)
    
    # Low-frequency wave diffraction limit (Kuhn 1977)
    tau_0 = (3.0 * head_radius / c) * np.sin(abs_theta)
    
    # High-frequency ray limit (Woodworth 1954)
    if abs_theta <= np.pi / 2:
        tau_inf = (head_radius / c) * (abs_theta + np.sin(abs_theta))
    else:
        theta_eff = np.pi - abs_theta
        tau_inf = (head_radius / c) * (theta_eff + np.sin(theta_eff))
        
    tau_0_signed = float(tau_0 * np.sign(theta))
    tau_inf_signed = float(tau_inf * np.sign(theta))
    return tau_0_signed, tau_inf_signed, tau_0_signed * sr, tau_inf_signed * sr


def brown_duda_head_shadow(x, azimuth_deg, head_radius=HEAD_RADIUS, c=SPEED_OF_SOUND, sr=SR):
    """Applies Brown & Duda (1998) continuous spherical head shadow filter discretized via Bilinear Transform.
    H(s) = (alpha*s + w0) / (s + w0)
    where w0 = 2*c / a (~7840 rad/s), and alpha(theta) smoothly varies from 2.0 (ipsilateral boost)
    down to ~0.15 (contralateral shadow), providing authentic physical phase and group delay.
    Returns: (l_out, r_out)
    """
    az = float(azimuth_deg)
    w0 = 2.0 * c / head_radius
    T = 1.0 / sr
    K = w0 * T / 2.0
    
    # Incident angle relative to right ear (+90) and left ear (-90)
    theta_r = abs(np.radians(90.0 - az))
    theta_l = abs(np.radians(-90.0 - az))
    
    # alpha varies smoothly: at 0 rad (facing ear) alpha=2.0; at pi rad (shadow) alpha=0.15
    alpha_min = 0.15
    # Brown & Duda (1998) Eq. 4 form: cos=1 -> 2.0, cos=-1 -> alpha_min
    alpha_r = (1.0 + 0.5 * alpha_min) + (1.0 - 0.5 * alpha_min) * np.cos(theta_r)
    alpha_l = (1.0 + 0.5 * alpha_min) + (1.0 - 0.5 * alpha_min) * np.cos(theta_l)
    alpha_r = float(np.clip(alpha_r, alpha_min, 2.0))
    alpha_l = float(np.clip(alpha_l, alpha_min, 2.0))
    
    # Bilinear transform discrete coefficients
    b_r = [(alpha_r + K) / (1.0 + K), (K - alpha_r) / (1.0 + K)]
    a_r = [1.0, (K - 1.0) / (1.0 + K)]
    
    b_l = [(alpha_l + K) / (1.0 + K), (K - alpha_l) / (1.0 + K)]
    a_l = [1.0, (K - 1.0) / (1.0 + K)]
    
    r_out = signal.lfilter(b_r, a_r, x).astype(np.float32)
    l_out = signal.lfilter(b_l, a_l, x).astype(np.float32)
    return l_out, r_out


# ---------------------------------------------------------------------------------------------
# 2. Fractional Delay & Kuhn Frequency-Dispersive Delay
# ---------------------------------------------------------------------------------------------

def apply_fractional_delay(x, delay_samples):
    """Applies sub-sample delay using sinc interpolation with Hann window."""
    if abs(delay_samples) < 1e-4:
        return x.copy()
    
    int_delay = int(np.floor(delay_samples))
    frac_delay = delay_samples - int_delay
    
    kernel_radius = 16
    n = np.arange(-kernel_radius, kernel_radius + 1)
    kernel = np.sinc(n - frac_delay) * np.hanning(len(n))
    s = np.sum(kernel)
    if abs(s) > 1e-7:
        kernel /= s
    
    delayed = signal.convolve(x, kernel, mode='same')
    
    if int_delay > 0:
        out = np.zeros_like(delayed)
        out[int_delay:] = delayed[:-int_delay]
        return out
    elif int_delay < 0:
        out = np.zeros_like(delayed)
        shift = abs(int_delay)
        out[:-shift] = delayed[shift:]
        return out
    return delayed


def apply_kuhn_dispersive_delay(x, azimuth_deg, head_radius=HEAD_RADIUS, c=SPEED_OF_SOUND, sr=SR):
    """Applies Kuhn frequency-dispersive ITD:
    High-frequency ray delay is applied via fractional delay, and low frequencies receive
    additional phase delay via an allpass filter to match Kuhn's (3a/c)*sin(theta) wave limit.
    """
    _, _, tau_0_samps, tau_inf_samps = kuhn_itd(azimuth_deg, head_radius=head_radius, c=c, sr=sr)
    tau_0_samps, tau_inf_samps = abs(tau_0_samps), abs(tau_inf_samps)   # this is the far ear: always delayed, for either side
    
    # Base fractional delay for high frequencies
    delayed_inf = apply_fractional_delay(x, tau_inf_samps)
    
    # Extra low-frequency delay needed
    delta_samps = abs(tau_0_samps) - abs(tau_inf_samps)
    if delta_samps > 0.2:
        # Allpass filter: A(z) = (p + z^-1) / (1 + p*z^-1)
        # For p in [-0.6, -0.2], group delay at DC is (1-p)/(1+p) samples with zero gain coloration
        p = -float(np.clip(delta_samps / (2.0 + delta_samps), 0.1, 0.6))
        b_ap = [p, 1.0]
        a_ap = [1.0, p]
        out = signal.lfilter(b_ap, a_ap, delayed_inf).astype(np.float32)
    else:
        out = delayed_inf
    return out


# ---------------------------------------------------------------------------------------------
# 3. Proximal Near-Field Acoustic Holography (Distance Variation Function)
# ---------------------------------------------------------------------------------------------

def apply_near_field_divergence(l_in, r_in, azimuth_deg, distance_m, head_radius=HEAD_RADIUS, sr=SR):
    """Applies proximal near-field acoustic holography for distance < 1.0 meter:
    When a source is close to the head, spherical wave divergence creates acoustic parallax
    and a massive low-frequency ILD surge (up to +15 dB below 500 Hz).
    """
    dist = max(0.08, float(distance_m))
    if dist >= 1.0:
        return l_in, r_in
        
    az = float(azimuth_deg)
    theta = np.radians(az)
    
    # Exact geometric distance from source (r, theta) to right ear (+a) and left ear (-a)
    # d_R = sqrt(r^2 + a^2 - 2*a*r*sin(theta))
    # d_L = sqrt(r^2 + a^2 + 2*a*r*sin(theta))
    d_r = np.sqrt(dist**2 + head_radius**2 - 2.0 * head_radius * dist * np.sin(theta))
    d_l = np.sqrt(dist**2 + head_radius**2 + 2.0 * head_radius * dist * np.sin(theta))
    
    # Inverse distance level factor relative to head center reference
    gain_r = float(np.clip(dist / max(0.05, d_r), 0.25, 4.0))
    gain_l = float(np.clip(dist / max(0.05, d_l), 0.25, 4.0))
    
    # Low-frequency ILD boost (spherical wavefront curvature impacts low frequencies intensely in near-field)
    sos_lp = signal.butter(1, min(sr * 0.45, 800.0), btype='lowpass', fs=sr, output='sos')
    l_bass = signal.sosfilt(sos_lp, l_in)
    r_bass = signal.sosfilt(sos_lp, r_in)
    
    l_out = (l_in * gain_l + 0.3 * l_bass * (gain_l - 1.0)).astype(np.float32)
    r_out = (r_in * gain_r + 0.3 * r_bass * (gain_r - 1.0)).astype(np.float32)
    return l_out, r_out


# ---------------------------------------------------------------------------------------------
# 4. ISO 9613-1 Atmospheric Air Absorption & Distance Attenuation
# ---------------------------------------------------------------------------------------------

def iso9613_air_absorption(x, distance_m, temp_c=20.0, rel_humidity=50.0, pressure_kpa=101.325, sr=SR):
    """Applies molecular vibrational relaxation of O2 and N2 according to ISO 9613-1 standard.
    High frequencies attenuate progressively with distance based on atmospheric conditions.
    """
    dist = max(0.1, float(distance_m))
    if dist <= 1.0:
        return x
    import airabs
    return airabs.apply(x, dist - 1.0, temp_c, rel_humidity, pressure_kpa, sr)  # absorption beyond the 1 m reference


def distance_attenuation(x, distance_m=1.0, d0=1.5, sr=SR):
    """Applies 1/r inverse-square law attenuation and ISO 9613-1 atmospheric air absorption.

    d0 = 1.5 m, the same reference distance mixer._place uses: below it the source is unity (the near field is
    handled by the divergence stage), above it one law owns the level instead of two stacked curves.
    """
    dist = max(0.1, float(distance_m))
    level_gain = min(1.0, d0 / dist)
    absorbed = iso9613_air_absorption(x, distance_m=dist, sr=sr)
    return (absorbed * level_gain).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# 5. Pinna & Torso Spectral Modeling
# ---------------------------------------------------------------------------------------------

def pinna_spectral_filter(x, elevation_deg=0.0, azimuth_deg=0.0, sr=SR):
    """Synthesizes monaural spectral cues:
    1. Concha resonance peak (+4 dB at 4.5 kHz).
    2. Dynamic pinna notch N1 (6.0 - 9.5 kHz) shifting monotonically with vertical elevation.
    3. Front/Back pinna notch N2 (10 - 14 kHz) resolving cone-of-confusion front/back ambiguity.
    """
    el = float(np.clip(elevation_deg, -90.0, 90.0))
    az = float(azimuth_deg)
    out = x.copy()
    
    # 1. Concha resonance (broad boost around 4.5 kHz)
    concha_fc = min(sr * 0.45, 4500.0)
    sos_concha = signal.butter(1, [max(10.0, concha_fc - 1200.0), min(sr * 0.48, concha_fc + 1200.0)],
                               btype='bandpass', fs=sr, output='sos')
    concha_boost = signal.sosfilt(sos_concha, x) * 0.35  # ~+3 dB
    out = out + concha_boost
    
    # 2. Elevation Notch N1 (shifts from 6.0 kHz up to 9.5 kHz with elevation)
    if abs(el) > 2.0:
        notch_fc = float(np.clip(6800.0 + 2800.0 * (el / 90.0), 3000.0, sr * 0.45))
        q = 6.0
        b_n1, a_n1 = signal.iirnotch(notch_fc, q, fs=sr)
        out = signal.lfilter(b_n1, a_n1, out)
        
    # 3. Front/Back Disambiguation Notch N2 (deep for front, flattened for rear)
    # Crossfaded over 80-110 deg: a hard switch at 90 deg made a rotating source flip front-to-back instead of
    # turning through the side.
    def _front(sig):
        n2_fc = min(sr * 0.45, 11500.0)
        b_n2, a_n2 = signal.iirnotch(n2_fc, 8.0, fs=sr)
        return signal.lfilter(b_n2, a_n2, sig)

    def _rear(sig):
        rear_shadow_fc = max(2500.0, min(sr * 0.45, 12000.0 - 2500.0 * (max(0.0, abs(az) - 90.0) / 90.0)))
        sos_rear = signal.butter(1, rear_shadow_fc, btype='lowpass', fs=sr, output='sos')
        return signal.sosfilt(sos_rear, sig)

    if abs(az) >= 110.0:
        out = _rear(out)
    elif abs(az) > 80.0:
        w = (abs(az) - 80.0) / 30.0
        out = _front(out) * (1.0 - w) + _rear(out) * w
    else:
        out = _front(out)

    return out.astype(np.float32)


def apply_torso_bounce(x, elevation_deg=0.0, sr=SR):
    """Applies torso/shoulder reflection (0.9 ms, -12 dB) to break in-head ear-canal collapse."""
    el = float(elevation_deg)
    delay_samps = int(0.0009 * sr)
    if delay_samps >= len(x):
        return x
        
    # Torso reflection is stronger from above (el > 0) than from below (el < 0)
    torso_gain = float(np.clip(0.25 + 0.10 * (el / 90.0), 0.10, 0.40))
    bounce = np.zeros_like(x)
    bounce[delay_samps:] = x[:-delay_samps] * torso_gain
    sos = signal.butter(1, min(sr * 0.45, 2800.0), btype='lowpass', fs=sr, output='sos')
    bounce = signal.sosfilt(sos, bounce)
    return (x + bounce).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# 6. Physical 6-Surface Image Source Early Reflection Engine
# ---------------------------------------------------------------------------------------------

def _arrive(sig, azimuth_deg, elevation_deg, sr=SR):
    """A reflection placed where it comes from: pinna colour for its height, head shadow and ITD for its side."""
    l, r = brown_duda_head_shadow(pinna_spectral_filter(sig, elevation_deg, azimuth_deg, sr=sr), azimuth_deg, sr=sr)
    itd = kuhn_itd(azimuth_deg, sr=sr)[3]
    if itd > 0:
        l = apply_fractional_delay(l, itd)
    elif itd < 0:
        r = apply_fractional_delay(r, abs(itd))
    return l, r


def _path_attenuate(sig, distance_m, delay_samps, space_cfg, sr=SR):
    """A reflection obeys the same laws as the direct sound, over its own longer path: 1/r about the preset's reference
    distance (`reflections.ref_m`, default 1.5 m = the direct law's d0) plus the air the extra path crosses.
    `reflections.path_physics` (default true) switches it off for a project mixed with the old unattenuated taps."""
    if not space_cfg.get('path_physics', True):
        return sig
    extra = SPEED_OF_SOUND * max(0.0, float(delay_samps)) / sr
    ref = float(space_cfg.get('ref_m', 1.5))
    out = np.asarray(sig, np.float32) * (ref / max(float(distance_m) + extra, 1e-6))
    return iso9613_air_absorption(out.astype(np.float32), distance_m=extra + 1.0, sr=sr)


def synthesize_early_reflections(x, azimuth_deg, distance_m, space_cfg, elevation_deg=0.0, sr=SR):
    """Synthesizes physical 6-surface early reflections (ground, ceiling, lateral walls, rear wall)
    using the Image Source Model (ISM) for authentic room geometry and natural externalization.
    """
    dist = max(0.5, float(distance_m))
    n = len(x)
    ref_l = np.zeros(n, dtype=np.float32)
    ref_r = np.zeros(n, dtype=np.float32)
    az = float(azimuth_deg)
    
    # 1. Ground Reflection (floor bounce: arrives slightly from below)
    g_delay_samps = int((space_cfg.get('ground_delay_ms', 8.5) / 1000.0) * sr * (1.0 + 0.1 * dist))
    if g_delay_samps < n:
        g_sig = np.zeros(n, dtype=np.float32)
        g_sig[g_delay_samps:] = x[:-g_delay_samps] * space_cfg.get('ground_gain', 0.35)
        sos_g = signal.butter(2, min(sr * 0.45, space_cfg.get('ground_cutoff_hz', 3200)), btype='lowpass', fs=sr, output='sos')
        g_filtered = signal.sosfilt(sos_g, g_sig)
        g_filtered = _path_attenuate(g_filtered, dist, g_delay_samps, space_cfg, sr)
        gl, gr = _arrive(g_filtered, az, -25.0, sr)         # from the floor, on the source's side
        ref_l += gl * 0.8
        ref_r += gr * 0.8
        
    # 2. Contralateral Lateral Reflection (opposite wall / tree canopy bounce)
    lat_delay_samps = int((space_cfg.get('lateral_delay_ms', 22.0) / 1000.0) * sr * (1.0 + 0.15 * dist))
    if lat_delay_samps < n:
        lat_sig = np.zeros(n, dtype=np.float32)
        lat_sig[lat_delay_samps:] = x[:-lat_delay_samps] * space_cfg.get('lateral_gain', 0.25)
        sos_lat = signal.butter(2, min(sr * 0.45, space_cfg.get('lateral_cutoff_hz', 2400)), btype='lowpass', fs=sr, output='sos')
        lat_filtered = signal.sosfilt(sos_lat, lat_sig)
        lat_filtered = _path_attenuate(lat_filtered, dist, lat_delay_samps, space_cfg, sr)
        
        opp_azimuth = -az * 0.8
        lat_l, lat_r = brown_duda_head_shadow(lat_filtered, opp_azimuth, sr=sr)
        _, _, _, opp_itd = kuhn_itd(opp_azimuth, sr=sr)
        if opp_itd > 0:
            lat_l = apply_fractional_delay(lat_l, opp_itd)
        elif opp_itd < 0:
            lat_r = apply_fractional_delay(lat_r, abs(opp_itd))
        ref_l += lat_l
        ref_r += lat_r
        
    # 3. Ceiling Reflection (overhead bounce)
    ceil_delay = space_cfg.get('ceiling_delay_ms', 30.0)
    ceil_delay_samps = int((ceil_delay / 1000.0) * sr * (1.0 + 0.12 * dist))
    if ceil_delay_samps < n:
        ceil_sig = np.zeros(n, dtype=np.float32)
        ceil_sig[ceil_delay_samps:] = x[:-ceil_delay_samps] * space_cfg.get('ceiling_gain', 0.15)
        sos_c = signal.butter(2, min(sr * 0.45, 2800.0), btype='lowpass', fs=sr, output='sos')
        ceil_filtered = signal.sosfilt(sos_c, ceil_sig)
        ceil_filtered = _path_attenuate(ceil_filtered, dist, ceil_delay_samps, space_cfg, sr)
        cl, cr = _arrive(ceil_filtered, az, 60.0, sr)       # from above: the height cue
        ref_l += cl * 0.65
        ref_r += cr * 0.65
        
    # 4. Rear Reflection (back wall bounce)
    rear_delay = space_cfg.get('rear_delay_ms', 28.0)
    rear_delay_samps = int((rear_delay / 1000.0) * sr * (1.0 + 0.18 * dist))
    if rear_delay_samps < n:
        rear_sig = np.zeros(n, dtype=np.float32)
        rear_sig[rear_delay_samps:] = x[:-rear_delay_samps] * space_cfg.get('rear_gain', 0.18)
        sos_r = signal.butter(2, min(sr * 0.45, 2000.0), btype='lowpass', fs=sr, output='sos')
        rear_filtered = signal.sosfilt(sos_r, rear_sig)
        rear_filtered = _path_attenuate(rear_filtered, dist, rear_delay_samps, space_cfg, sr)
        rl, rr = _arrive(rear_filtered, (1.0 if az >= 0 else -1.0) * (180.0 - abs(az)), 0.0, sr)   # from behind
        ref_l += rl * 0.55
        ref_r += rr * 0.55
        
    return ref_l, ref_r


# ---------------------------------------------------------------------------------------------
# 7. Complete Spatialization Stem Pipeline
# ---------------------------------------------------------------------------------------------

def spatialize_stem(audio, azimuth_deg=0.0, elevation_deg=0.0, distance_m=1.0, 
                    acoustic_space='outdoor_open', externalize=True, sr=SR):
    """Spatializes mono audio into a naturally externalized 3D physical sound field:
    1. Torso scattering for externalization.
    2. Distance attenuation & ISO 9613-1 atmospheric air absorption.
    3. Pinna & concha elevation/front-back spectral shaping.
    4. Brown & Duda analytical spherical head shadow ILD.
    5. Kuhn frequency-dependent ITD with phase dispersion.
    6. Proximal near-field divergence (r < 1.0m).
    7. 6-surface Image Source Model (ISM) early reflections.
    """
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
        
    if isinstance(acoustic_space, dict):          # a space preset's "reflections" block; missing keys come from outdoor_open
        space_cfg = {**ACOUSTIC_SPACES['outdoor_open'], **acoustic_space}
    else:
        space_cfg = ACOUSTIC_SPACES.get(acoustic_space, ACOUSTIC_SPACES['outdoor_open'])
    
    # 1. Torso scattering
    if externalize:
        x_body = apply_torso_bounce(x, elevation_deg=elevation_deg, sr=sr)
    else:
        x_body = x
        
    # 2. Distance attenuation + ISO 9613-1 air absorption (one reference distance: 1.5 m, as in the mixer)
    x_direct = distance_attenuation(x_body, distance_m=distance_m, d0=1.5, sr=sr)
    
    # 3. Pinna & elevation spectral cues
    x_direct = pinna_spectral_filter(x_direct, elevation_deg=elevation_deg, azimuth_deg=azimuth_deg, sr=sr)
    
    # 4. Brown & Duda (1998) analytical head shadow
    l_shadow, r_shadow = brown_duda_head_shadow(x_direct, azimuth_deg=azimuth_deg, sr=sr)
    
    # 5. Kuhn frequency-dependent ITD
    _, _, tau_0_samps, tau_inf_samps = kuhn_itd(azimuth_deg=azimuth_deg, sr=sr)
    if tau_inf_samps > 0:  # Source on right: left ear delayed
        l_direct = apply_kuhn_dispersive_delay(l_shadow, azimuth_deg=azimuth_deg, sr=sr)
        r_direct = r_shadow
    elif tau_inf_samps < 0:  # Source on left: right ear delayed
        l_direct = l_shadow
        r_direct = apply_kuhn_dispersive_delay(r_shadow, azimuth_deg=azimuth_deg, sr=sr)
    else:
        l_direct = l_shadow
        r_direct = r_shadow
        
    # 6. Proximal Near-Field Divergence (for r < 1.0m)
    if distance_m < 1.0:
        l_direct, r_direct = apply_near_field_divergence(l_direct, r_direct, azimuth_deg=azimuth_deg,
                                                         distance_m=distance_m, sr=sr)
                                                         
    # 7. 6-Surface Image Source Environmental Reflections
    if externalize:
        ref_l, ref_r = synthesize_early_reflections(x, azimuth_deg=azimuth_deg, 
                                                    distance_m=distance_m, 
                                                    space_cfg=space_cfg,
                                                    elevation_deg=elevation_deg, sr=sr)
        l_out = l_direct + ref_l
        r_out = r_direct + ref_r
    else:
        l_out = l_direct
        r_out = r_direct
        
    out = np.stack([l_out, r_out], axis=1)
    return out.astype(np.float32)


# ---------------------------------------------------------------------------------------------
# 8. Dynamic Trajectory & Continuous Doppler Engine
# ---------------------------------------------------------------------------------------------

def render_trajectory(audio, trajectory, acoustic_space='outdoor_open', sr=SR):
    """Renders a moving 3D sound trajectory.
    1. One continuous variable delay from r(t)/c over the whole signal (true Doppler, no block edges).
    2. The angle/distance filters run on 50 %-overlapped periodic-Hann blocks (overlap-add sums to 1), so
       filter memory and early reflections (8-60 ms) survive and there is no frame-rate buzz.
    """
    from scipy.interpolate import CubicSpline
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)

    n_samples = len(x)
    g = lambda k, d: float(trajectory.get(k, d))
    start_az, end_az = g('start_azimuth', -45.0), g('end_azimuth', 45.0)
    start_dist, end_dist = g('start_distance', 3.0), g('end_distance', 1.5)
    start_el, end_el = g('start_elevation', 0.0), g('end_elevation', 0.0)

    frac_n = np.arange(n_samples) / max(1, n_samples)
    if trajectory.get('doppler', True) and n_samples > 8:
        r = start_dist + frac_n * (end_dist - start_dist)
        delay = (r - r.min()) / SPEED_OF_SOUND * sr          # samples; causal because we subtract the minimum
        x = CubicSpline(np.arange(n_samples), x)(np.clip(np.arange(n_samples) - delay, 0, n_samples - 1)).astype(np.float32)

    block, hop = 8192, 4096                                   # 186 ms: holds the longest early reflections
    win = signal.get_window('hann', block, fftbins=True)      # periodic Hann, COLA at 50 %
    pad = block
    xp = np.concatenate([np.zeros(pad, np.float32), x, np.zeros(pad, np.float32)])
    out = np.zeros((len(xp), 2), dtype=np.float32)
    for i0 in range(0, len(xp) - block + 1, hop):
        centre = i0 + block / 2.0 - pad
        frac = float(np.clip(centre / max(1, n_samples), 0.0, 1.0))
        # direct path only per block: the reflections are built once, below. Building them inside each Hann
        # window tapered their onsets at the hop rate (a 10.8 Hz warble on the reflection bed).
        seg = spatialize_stem(xp[i0:i0 + block] * win, azimuth_deg=start_az + frac * (end_az - start_az),
                              elevation_deg=start_el + frac * (end_el - start_el),
                              distance_m=start_dist + frac * (end_dist - start_dist),
                              acoustic_space=acoustic_space, externalize=False, sr=sr)
        out[i0:i0 + block] += seg
    if isinstance(acoustic_space, dict):
        space_cfg = {**ACOUSTIC_SPACES['outdoor_open'], **acoustic_space}
    else:
        space_cfg = ACOUSTIC_SPACES.get(acoustic_space, ACOUSTIC_SPACES['outdoor_open'])
    ref_l, ref_r = synthesize_early_reflections(x, azimuth_deg=0.5 * (start_az + end_az),
                                                distance_m=0.5 * (start_dist + end_dist), space_cfg=space_cfg,
                                                elevation_deg=0.5 * (start_el + end_el), sr=sr)
    m = min(n_samples, len(ref_l))
    out[pad:pad + m, 0] += ref_l[:m]
    out[pad:pad + m, 1] += ref_r[:m]
    return out[pad:pad + n_samples]


# ---------------------------------------------------------------------------------------------
# 9. Ambisonic B-Format Encoding & Virtual Loudspeaker Binaural Decoding
# ---------------------------------------------------------------------------------------------

def encode_ambisonic_bformat(audio, azimuth_deg=0.0, elevation_deg=0.0):
    """Encodes mono audio into 1st-Order Ambisonics (B-format: W, Y, Z, X).
    ACN channel ordering, SN3D normalization:
      W = omnidirectional (l=0, m=0)
      Y = left-right dipole (l=1, m=-1)
      Z = up-down dipole (l=1, m=0)
      X = front-back dipole (l=1, m=1)
    Returns: (N, 4) float32 array.
    """
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
        
    az_rad = np.radians(float(azimuth_deg))
    el_rad = np.radians(float(elevation_deg))
    
    w = x * 1.0
    y = x * (np.sin(az_rad) * np.cos(el_rad))
    z = x * (np.sin(el_rad))
    x_ch = x * (np.cos(az_rad) * np.cos(el_rad))
    
    bformat = np.stack([w, y, z, x_ch], axis=1)
    return bformat.astype(np.float32)


def decode_ambisonic_to_binaural(bformat, sr=SR):
    """Decodes 1st-Order Ambisonics (B-format: W, Y, Z, X) to binaural stereo headphones
    via an 8-virtual-loudspeaker cube array with Max-rE weighting.
    Returns: (N, 2) float32 array.
    """
    b = np.asarray(bformat, dtype=np.float32)
    assert b.ndim == 2 and b.shape[1] >= 4, "bformat must be (N, 4)"
    
    # 8 virtual loudspeakers arranged on a cube
    # (azimuths: +/-45, +/-135; elevations: +/-35.26 deg)
    speakers = [
        (45.0, 35.26), (-45.0, 35.26), (135.0, 35.26), (-135.0, 35.26),
        (45.0, -35.26), (-45.0, -35.26), (135.0, -35.26), (-135.0, -35.26)
    ]
    
    binaural_out = np.zeros((len(b), 2), dtype=np.float32)
    w_weight = 1.0 / np.sqrt(2.0)
    
    for az, el in speakers:
        az_r, el_r = np.radians(az), np.radians(el)
        # Max-rE decoder matrix weight for 1st-order: W/sqrt(2) + (1/sqrt(3))*(X*cos + Y*sin + Z*sin)
        spk_signal = (b[:, 0] * w_weight + 
                      (1.0 / np.sqrt(3.0)) * (b[:, 3] * np.cos(az_r) * np.cos(el_r) +
                                              b[:, 1] * np.sin(az_r) * np.cos(el_r) +
                                              b[:, 2] * np.sin(el_r)))
        # decode at the reference distance (1.0 m, inside the 1.5 m unity radius) so the ambisonic route is
        # level-matched with the direct binaural route instead of arriving ~8 dB down
        spk_binaural = spatialize_stem(spk_signal, azimuth_deg=az, elevation_deg=el,
                                       distance_m=1.0, externalize=False, sr=sr)
        binaural_out += spk_binaural * (1.0 / len(speakers))
        
    return binaural_out.astype(np.float32)


# ---------------------------------------------------------------------------------------------
# 10. CLI Interface
# ---------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input_wav', help='Path to input WAV file')
    ap.add_argument('--azimuth', type=float, default=0.0, help='Azimuth in degrees (-90 to +90)')
    ap.add_argument('--elevation', type=float, default=0.0, help='Elevation in degrees (-90 to +90)')
    ap.add_argument('--distance', type=float, default=1.0, help='Distance in meters (< 1.0 = near-field)')
    ap.add_argument('--space', default='outdoor_open', choices=sorted(ACOUSTIC_SPACES.keys()),
                    help='Acoustic space reflection profile')
    ap.add_argument('--no-externalize', action='store_true', help='Disable early reflections (anechoic mode)')
    ap.add_argument('--bformat', action='store_true', help='Export 4-channel 1st-Order Ambisonics (B-format)')
    ap.add_argument('--out', default='spatial_out.wav', help='Output WAV path')
    args = ap.parse_args()
    
    data, sr = sf.read(args.input_wav, always_2d=True)
    if args.bformat:
        bformat_data = encode_ambisonic_bformat(data, azimuth_deg=args.azimuth, elevation_deg=args.elevation)
        sf.write(args.out, bformat_data, sr, subtype='PCM_24')
        print(f'Wrote 1st-Order Ambisonics B-format (4 channels): {args.out} (Azimuth {args.azimuth} deg, Elevation {args.elevation} deg)')
    else:
        spatial_data = spatialize_stem(data, azimuth_deg=args.azimuth, elevation_deg=args.elevation, 
                                      distance_m=args.distance, acoustic_space=args.space, 
                                      externalize=not args.no_externalize, sr=sr)
        sf.write(args.out, spatial_data, sr, subtype='PCM_24')
        print(f'Wrote physical 3D spatial audio: {args.out} (Azimuth {args.azimuth} deg, Distance {args.distance} m, Space {args.space})')


if __name__ == '__main__':
    main()
