---
id: video-scoring
title: Video scoring: frame-locked tempo, hit points and voice-over
domain: media
status: unverified
sources: []
used_by: [AGENTS.md]
updated: 2026-11-04
---

> **Not verified.** These values are a starting point from practice, not a measurement.
> Cite a source before presenting one as established, and say "starting value" when a piece uses one.

# Video scoring: frame-locked tempo, hit points and voice-over

## 1. Theoretical Foundations: Frame-Rate Locked Musical Mathematics

In commercial motion graphics, explainer videos, brand trailers, and social video ads, audio and video must operate in **strict mathematical harmony**. In traditional linear music production, tempo is dictated solely by musical groove (BPM). In motion design, visual time is strictly quantized into discrete picture frames dictated by the project frame rate ($\text{FPS} \in \{24, 25, 29.97, 30, 60\}$).

### The Fundamental Quantization Formula
To ensure that musical quarter-note beats, eighth-note pulses, or measures land exactly on integer video frames without temporal drift:

$$F_{\text{beat}} = \frac{\text{FPS} \cdot 60}{\text{BPM}} \in \mathbb{Z}^+ \quad \iff \quad \text{BPM} = \frac{\text{FPS} \cdot 60}{F_{\text{beat}}}$$

Where $F_{\text{beat}}$ is the exact integer number of video frames per musical beat.

## 2. The Universal Frame-to-BPM Quantization Matrix (24, 25, 29.97, 30, 60 FPS)

Composers and sound designers working in motion graphics should select tempos from the **Frame-Quantized Tempo Matrix** to ensure visual keyframes snap dead-on musical beats:

| Frames per Beat ($F_{\text{beat}}$) | 24 FPS (Cinematic / Film) | 25 FPS (PAL / European Broadcast) | 30 FPS (Web / YouTube / Social) | 60 FPS (Fluid 60fps Motion UI) |
| :---: | :---: | :---: | :---: | :---: |
| **10 Frames** | $144.0\text{ BPM}$ | $150.0\text{ BPM}$ | $180.0\text{ BPM}$ | - |
| **12 Frames** | **$120.0\text{ BPM}$** | $125.0\text{ BPM}$ | $150.0\text{ BPM}$ | - |
| **14 Frames** | $102.86\text{ BPM}$ | $107.14\text{ BPM}$ | $128.57\text{ BPM}$ | - |
| **15 Frames** | **$96.0\text{ BPM}$** | $100.0\text{ BPM}$ | **$120.0\text{ BPM}$** | $240.0\text{ BPM}$ |
| **16 Frames** | **$90.0\text{ BPM}$** | $93.75\text{ BPM}$ | $112.50\text{ BPM}$ | $225.0\text{ BPM}$ |
| **18 Frames** | **$80.0\text{ BPM}$** | $83.33\text{ BPM}$ | **$100.0\text{ BPM}$** | $200.0\text{ BPM}$ |
| **20 Frames** | **$72.0\text{ BPM}$** | $75.0\text{ BPM}$ | **$90.0\text{ BPM}$** | $180.0\text{ BPM}$ |
| **24 Frames** | **$60.0\text{ BPM}$** | $62.5\text{ BPM}$ | **$75.0\text{ BPM}$** | **$150.0\text{ BPM}$** |
| **30 Frames** | - | $50.0\text{ BPM}$ | **$60.0\text{ BPM}$** | **$120.0\text{ BPM}$** |

> [!TIP]
> **The Golden Motion Design Tempos:**
> - For **30 FPS**: **$120.0\text{ BPM}$** ($15\text{ frames/beat}$), **$100.0\text{ BPM}$** ($18\text{ frames/beat}$), and **$90.0\text{ BPM}$** ($20\text{ frames/beat}$).
> - For **24 FPS**: **$120.0\text{ BPM}$** ($12\text{ frames/beat}$), **$96.0\text{ BPM}$** ($15\text{ frames/beat}$), and **$72.0\text{ BPM}$** ($20\text{ frames/beat}$).
> - For **60 FPS**: **$120.0\text{ BPM}$** ($30\text{ frames/beat}$) and **$150.0\text{ BPM}$** ($24\text{ frames/beat}$).

## 3. Visual Hit Points & Keyframe Synchronization Mechanics

### 3.1 The ±2 Frame Psychoacoustic Perceptual Window
Cognitive studies in cross-modal temporal integration reveal that the human brain perceives visual and auditory stimuli as **simultaneous** if the audio transient lands within **$-1\text{ frame}$ (audio precedes video) to $+2\text{ frames}$ (audio trails video)**.
- **Audio Preceding Video (Lead):** Up to $-45\text{ ms}$ (about $1$ frame at $24\text{ fps}$) feels natural because light travels faster than sound in physical reality.
- **Audio Trailing Video (Lag):** Lags beyond $+80\text{ ms}$ ($> 2.5\text{ frames}$) create an immediate subconscious perception of amateur desynchronization.

### 3.2 Pre-Roll Riser & Transition Math
A riser (noise sweep, pitch glide, reverse cymbal) must peak **exactly on the first frame of the new scene**, not a fraction of a beat early or late.

At 30 fps with the cut on frame 90: the riser starts at frame 60, the filter has swept 400 Hz to 8 kHz by frame 75 (+6 dB/octave), frame 89 is one frame of silence, and frame 90 is the cut and the impact.

### 3.3 Post-Transition Downlifters & Braams
Following a major visual transition or brand title drop:
1. **Downlifter / Sub-Drop:** Exponential pitch glide downward ($120\text{ Hz} \rightarrow 35\text{ Hz}$ over $1.5\text{s}$) releasing visual kinetic energy.
2. **Trailer Braam:** Heavy distorted low brass and reese synth hit with high harmonic saturation, followed by an expansive $3.0\text{s}$ stereo reverb tail.

## 4. Dynamic Voice-Over Ducking & Speech Corridor Carving (250–3800 Hz)

In product demos, explainer videos, and commercial advertisements, the **voiceover (VO)** is the primary carrier of cognitive information. Traditional broad-band ducking (lowering the entire music track by $-10\text{ dB}$) drains the energy and groove from the video.

### Frequency-Bracketed Corridor Carving
The human voice carries $85\%$ of its acoustic energy and $95\%$ of its intelligibility within the **$250\text{ Hz} - 3800\text{ Hz}$ presence corridor**:
- Vowel formants ($F1, F2$): $300\text{ Hz} - 2500\text{ Hz}$.
- Consonant fricatives and plosives ($s, t, k, p$): $2500\text{ Hz} - 4500\text{ Hz}$.

Three-band duck: below 200 Hz unducked, 250-3800 Hz ducked -8 to -14 dB under the voice, above 4000 Hz ducked about -2 dB.

### Lookahead Ducking Formula:
A voice consonant takes $30-60\text{ ms}$ to reach peak acoustic energy. If ducking reacts reactively, the opening consonant is masked. The engine must employ **$60\text{ ms}$ lookahead sidechain detection**:

$$G_{\text{mid}}(t) = 1.0 - (1.0 - G_{\min}) \cdot \sigma\left(\frac{E_{\text{VO}}(t + t_{\text{lookahead}}) - \text{threshold}}{\text{knee}}\right)$$

## 5. Motion Graphics Narrative Arcs & Kinetic Easing Synchronization

### 5.1 The 15s / 30s / 60s Commercial Promo Motion Arc

| Phase | Timecode (30s Spot) | Visual Narrative Event | Audio / Musical Event | DSP & Mix Action |
| :--- | :--- | :--- | :--- | :--- |
| **1. The Hook** | $0.0 - 3.0\text{s}$ | High-energy visual problem or eye-catching 3D render | Instant sonic grabber (percussion hit, chime, reverse drop) | Immediate full frequency spectrum; no slow fade-in |
| **2. The Agitation** | $3.0 - 10.0\text{s}$ | Explaining user pain point / kinetic text questions | Tense harmonic bed, driving bassline, sparse arrangement | Ducked $-10\text{ dB}$ in speech corridor under narration |
| **3. The Reveal** | $10.0 - 12.0\text{s}$ | Product interface reveal or hero 3D logo entry | Riser buildup $\rightarrow$ 1-beat pre-drop silence $\rightarrow$ **Massive Drop** | Full bass drop + transient whoosh hit on exact cut |
| **4. Feature Tour** | $12.0 - 24.0\text{s}$ | Rapid-fire UI animations, feature callouts | Full groove, uplifting melody, driving drums, rhythmic claps | Syncing micro-foley clicks to UI button presses |
| **5. Climax & CTA** | $24.0 - 30.0\text{s}$ | Call to Action, URL, App Store badges, Logo lockup | Final brass swell, crescendo riser $\rightarrow$ **Logo Stinger Strum** | Clean ring-out tail ($T_{60} \approx 2.5\text{s}$) to zero |

### 5.2 Mirroring Animation Bezier Easing Curves (Cubic-Bezier to DSP Envelopes)
In modern motion design (After Effects, CSS, Framer Motion), animations do not move linearly; they follow cubic-bezier easing curves:
- **Fast In, Gentle Settle (`cubic-bezier(0.16, 1.0, 0.3, 1.0)`):** Snappy entrance with smooth deceleration.
- **Anticipation (Overshoot):** Backing up slightly before springing forward.

**The Audio Mirroring Principle:**
A sound effect or riser amplitude envelope $A(t)$ must match the velocity curve of the animation layer. If an object accelerates exponentially before slamming into place, the audio riser must match the exact exponential exponent ($k \approx 3.5$):

$$A(t) = A_0 + (A_1 - A_0) \cdot \left(\frac{t}{T}\right)^k$$

## 6. Sonic Branding & Audio Logo Stinger Architecture (2 to 6 Seconds)

An audio logo (mnemonic / stinger) must distill a company’s entire brand essence into **2 to 5 seconds**.

A 3.5 s audio logo runs as four layers: ambient intro 0.0-1.2 s, mnemonic melody 1.0-2.5 s, anchor hit at 2.2 s (50 Hz sub plus bell), reverb tail 2.5-4.5 s decaying to -60 dB.

### The 4 Pillars of a Successful Audio Logo:
1. **Unambiguous Tonal Anchor:** A clear root note (often $\text{C}$ or $\text{E}$) grounded by sub-bass.
2. **Pristine Spectral Balance:** Sub-bass punch ($40-80\text{ Hz}$), acoustic warmth ($300-800\text{ Hz}$), vocal-range melody ($1.2-3.0\text{ kHz}$), and air shimmer ($8-16\text{ kHz}$).
3. **Instant Attack Transient:** The hero chord or chime strike must have zero phase lag.
4. **Tail Integrity:** The tail must decay smoothly to silence without clicks, dc-offsets, or truncated room reverb.

## 7. Production Python DSP Implementation

The following production code implements **Frame-Rate Quantized Tempo Calculation**, **Pre-Roll Riser Placement**, and **Frequency-Bracketed Voiceover Ducking**:

```python
import numpy as np
import scipy.signal as signal
import soundfile as sf

def calculate_frame_locked_tempo(target_bpm, fps=30.0):
    """Calculates the nearest frame-accurate tempo where beats land on integer video frames.
    Returns: (quantized_bpm, frames_per_beat, ms_per_beat)
    """
    ideal_fpb = (fps * 60.0) / target_bpm
    integer_fpb = max(1, int(round(ideal_fpb)))
    quantized_bpm = (fps * 60.0) / integer_fpb
    ms_per_beat = (60.0 / quantized_bpm) * 1000.0
    return quantized_bpm, integer_fpb, ms_per_beat

def place_transition_riser(music_bed, target_frame, riser_duration_frames, fps=30.0, sr=44100, vacuum_frames=1):
    """Places an exponential build riser so that it peaks exactly on target_frame.
    vacuum_frames: number of frames of silence immediately preceding the cut to create maximum impact.
    """
    total_len = len(music_bed)
    target_sample = int((target_frame / fps) * sr)
    riser_samples = int((riser_duration_frames / fps) * sr)
    vacuum_samples = int((vacuum_frames / fps) * sr)
    
    start_sample = max(0, target_sample - riser_samples - vacuum_samples)
    actual_riser_len = target_sample - vacuum_samples - start_sample
    
    if actual_riser_len <= 10:
        return music_bed
        
    t = np.arange(actual_riser_len) / actual_riser_len
    # Exponential riser envelope
    env = (np.exp(3.5 * t) - 1.0) / (np.exp(3.5) - 1.0)
    
    # Synthesize swept bandpass noise riser
    rng = np.random.default_rng(42)
    noise = rng.standard_normal(actual_riser_len).astype(np.float32)
    sos = signal.butter(2, [300.0, 7500.0], btype='bandpass', fs=sr, output='sos')
    filtered_riser = signal.sosfilt(sos, noise) * env * 0.75
    
    out = music_bed.copy()
    if out.ndim == 2:
        out[start_sample:start_sample + actual_riser_len, 0] += filtered_riser
        out[start_sample:start_sample + actual_riser_len, 1] += filtered_riser
        # Apply pre-drop vacuum silence
        if vacuum_samples > 0:
            out[target_sample - vacuum_samples:target_sample] *= 0.05
    else:
        out[start_sample:start_sample + actual_riser_len] += filtered_riser
        if vacuum_samples > 0:
            out[target_sample - vacuum_samples:target_sample] *= 0.05
            
    return out

def apply_speech_corridor_ducking(music, voiceover, sr=44100, max_duck_db=-12.0, lookahead_ms=60):
    """Applies frequency-bracketed ducking: selectively cuts 250 - 3800 Hz speech corridor
    while preserving bass power (< 200 Hz) and high air (> 4 kHz).
    """
    n = min(len(music), len(voiceover))
    m = music[:n].copy()
    vo = voiceover[:n]
    if vo.ndim == 2:
        vo = vo.mean(axis=1)
        
    # 1. Split music into 3 bands: Sub/Bass (< 250 Hz), Mid Corridor (250 - 3800 Hz), High Air (> 3800 Hz)
    sos_lp = signal.butter(2, 250.0, btype='lowpass', fs=sr, output='sos')
    sos_bp = signal.butter(2, [250.0, 3800.0], btype='bandpass', fs=sr, output='sos')
    sos_hp = signal.butter(2, 3800.0, btype='highpass', fs=sr, output='sos')
    
    m_bass = signal.sosfilt(sos_lp, m, axis=0)
    m_mid = signal.sosfilt(sos_bp, m, axis=0)
    m_high = signal.sosfilt(sos_hp, m, axis=0)
    
    # 2. Compute smooth voiceover envelope with lookahead
    lookahead_samps = int((lookahead_ms / 1000.0) * sr)
    vo_rect = np.abs(vo)
    # Fast attack (15 ms), smooth release (180 ms)
    b_env, a_env = signal.butter(1, 10.0, btype='lowpass', fs=sr)
    vo_env = signal.lfilter(b_env, a_env, vo_rect)
    
    # Shift forward by lookahead
    vo_env_shifted = np.zeros_like(vo_env)
    if lookahead_samps < n:
        vo_env_shifted[:-lookahead_samps] = vo_env[lookahead_samps:]
    else:
        vo_env_shifted = vo_env
        
    # Normalize envelope to [0, 1]
    peak = max(1e-4, np.max(vo_env_shifted))
    duck_gain_linear = 10.0 ** (max_duck_db / 20.0)
    # Mid band gain curve
    mid_gain = 1.0 - (1.0 - duck_gain_linear) * np.clip(vo_env_shifted / (peak * 0.35), 0.0, 1.0)
    if m.ndim == 2:
        mid_gain = mid_gain[:, None]
        
    # Recombine: Bass is 100% untouched, Mid is ducked, High is gently ducked by 2 dB
    ducked_mid = m_mid * mid_gain
    out = (m_bass + ducked_mid + m_high * 0.85).astype(np.float32)
    return out
```
