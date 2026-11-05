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
"""naturalness_check.py - objective QA for a rendered track (Claude cannot listen, so measure).

    python3 naturalness_check.py song.wav                       # report + PNG
    python3 naturalness_check.py song.wav --bpm 68 --target-lufs -14
    python3 naturalness_check.py --compare old.wav new.wav      # side by side

Prints PASS / WARN / FAIL lines with plain-language advice. These are PROXIES for how it sounds
(loudness, balance, dynamics, stereo, timing looseness, spectral sanity) - they catch the common
mistakes (clipping, mud, flat dynamics, mechanical grid timing, harsh top end, mono-incompatible
bass) but they cannot tell you the music is beautiful. Say so in your report to the user.
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf
from scipy import ndimage, signal

PEAK_PROMINENCE_DB = 15.0   # a roughness peak must stand this far above its local spectral floor (random noise peaks reach about 11 dB)
PEAK_FLOOR_BINS = 101       # width of the local floor (median) in bins; the frames are 1 s, so 101 Hz
# Roughness is measured where the ear is actually sensitive to it. Below 200 Hz a fifth of two fundamentals scores as "rough"
# in the Plomp-Levelt kernel (they are ~1.6 quarter-bands apart) although no one hears a low D-A as harsh; that dominated
# every orchestral render. Above 4 kHz the partials are too far apart in Hz for the kernel to fire.
ROUGHNESS_BAND_HZ = (200.0, 4000.0)
ROUGHNESS_AUDIBLE_DB = -40.0    # a partial this far under the frame's loudest cannot make roughness audible
# The per-frame value is the MEAN OF THE THREE STRONGEST PAIR CONTRIBUTIONS, not a sum over all pairs: a sum counts how many
# partials are present, so a 6-part consonant chord scored 2x the fail threshold while a semitone dyad scored less (both
# measured, see tests/test_gate_profiles.py::Roughness). Calibrated on 6 real masters (median 0.029-0.047) and a synthetic
# anchor set (consonant triad/4-part/8-part 0.041-0.062; semitone at 262/500/1000 Hz and a 3-semitone cluster 0.073-0.099).
ROUGHNESS_MEDIAN = 0.070
ROUGHNESS_RELATIVE = 1.6        # a spike must also stand this far above the piece's own median
ROUGHNESS_OUTRO_RATIO = 1.2     # the last 3 s must not be rougher than the piece's median by more than this
# Level-aware model (roughness.model = "level_aware"). Every value below is a profile parameter of the `roughness`
# row (scripts/gate_profiles.py); these are its defaults. Sources and the argument for each:
# knowledgebase/sound-design/roughness.md. The legacy computation is untouched and still reported for comparison.
ROUGHNESS_CALIB_SPL_DB = 70.0            # programme loudness is placed at this SPL (the sources measure at 60-70 dB)
ROUGHNESS_MASK_BAND_BARK = 1.0           # Daniel & Weber mask in 1-Bark filters
ROUGHNESS_MASK_SLOPE_UP_DB_BARK = 10.5   # measured upper masking slope, 64-70 dB components at 450-480 Hz
ROUGHNESS_MASK_SLOPE_DOWN_DB_BARK = 27.0 # Daniel & Weber lower masking slope, -27 dB/Bark
ROUGHNESS_SL_RAMP_DB = 10.0             # a partial reaches full weight 10 dB above its threshold (ramp below that)
ROUGHNESS_MEDIAN_LEVEL_AWARE = 0.024     # calibrated on tests/fixtures/roughness (see docs/roughness_model.md)
# Plomp-Levelt is about beating between resolved partials. A drum hit, a cymbal or a noise bed fills the band with random
# peaks that are not partials; measured on six masters, those frames reached 0.13-0.16 and made every piece fail. A frame is
# judged only when its detected partials hold at least this share of the band's energy.
TONAL_MIN_FRACTION = 0.40
TONAL_MIN_FRAMES = 4            # fewer resolved frames than this and the row is not applied (it says so)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BANDS = [('sub <60', 20, 60), ('bass 60-250', 60, 250), ('low-mid 250-500', 250, 500), ('mid 0.5-2k', 500, 2000),
         ('presence 2-6k', 2000, 6000), ('air >6k', 6000, 16000)]


def load(path):
    x, sr = sf.read(path, always_2d=True)
    x = x.astype(np.float64)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, 1)
    return x[:, :2], sr


def lufs_meter(x, sr):
    import pyloudnorm as pyln
    m = pyln.Meter(sr)
    return m.integrated_loudness(x)


def short_term(x, sr, win=3.0, hop=1.0):
    import pyloudnorm as pyln
    m = pyln.Meter(sr)
    vals = []
    for s in np.arange(0, max(len(x) / sr - win, 0.01), hop):
        seg = x[int(s * sr):int((s + win) * sr)]
        if len(seg) < int(0.5 * sr):
            continue
        v = m.integrated_loudness(seg)
        if np.isfinite(v) and v > -70:
            vals.append(v)
    return np.array(vals)


def band_shares(x, sr):
    mono = x.mean(1)
    f, p = signal.welch(mono, sr, nperseg=8192)
    tot = p.sum() + 1e-18
    return {n: 10 * np.log10(p[(f >= lo) & (f < hi)].sum() / tot + 1e-18) for n, lo, hi in BANDS}, f, p


def chroma_profile(x, sr):
    """Compute 12-TET chroma energy profile (80 - 2000 Hz) via 8192-point FFT."""
    mono = x.mean(1) if x.ndim == 2 else x
    n = 8192
    if len(mono) < n:
        mono = np.pad(mono, (0, n - len(mono)))
    mid_idx = max(0, len(mono) // 2 - n // 2)
    seg = mono[mid_idx:mid_idx + n] * np.hanning(n)
    spec = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    valid = (freqs >= 80.0) & (freqs <= 2000.0)
    spec = spec[valid]
    freqs = freqs[valid]
    midi = 69.0 + 12.0 * np.log2(np.maximum(freqs, 1.0) / 440.0)
    chroma = np.zeros(12, dtype=np.float64)
    for p, val in zip(midi, spec):
        pc = int(round(p)) % 12
        chroma[pc] += val
    tot = chroma.sum() + 1e-12
    return chroma / tot


def onsets(x, sr, hop=256):
    """Spectral-flux onset times in seconds."""
    mono = x.mean(1)
    f, t, S = signal.stft(mono, sr, nperseg=1024, noverlap=1024 - hop)
    mag = np.log1p(np.abs(S) * 50)
    flux = np.maximum(0, np.diff(mag, axis=1)).sum(0)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    peaks, _ = signal.find_peaks(flux, height=1.2, distance=int(0.06 * sr / hop))
    return t[1:][peaks]


def timing_looseness(on, bpm, grid=0.25):
    """Std (ms) of onset deviation from the nearest 16th-note grid. ~0-2 ms = machine; 6-20 ms = human."""
    if len(on) < 8:
        return None
    spb = 60.0 / bpm
    unit = spb * grid
    # let the grid float: best global offset
    best = None
    for off in np.linspace(0, unit, 40, endpoint=False):
        d = ((on - off + unit / 2) % unit) - unit / 2
        s = np.sqrt(np.mean(d ** 2))
        if best is None or s < best[0]:
            best = (s, off)
    d = ((on - best[1] + unit / 2) % unit) - unit / 2
    return float(np.std(d) * 1000), float(np.mean(np.abs(d)) * 1000)


def analyse(path, bpm=None, target_lufs=None, audio=None):
    """`audio` = (samples (n, 2), sr) measures an array in memory (path is then only a label)."""
    x, sr = audio if audio is not None else load(path)
    r = {'path': path, 'sr': sr, 'dur': len(x) / sr}
    r['lufs'] = float(lufs_meter(x, sr))
    y = signal.resample_poly(x, 4, 1, axis=0)
    r['true_peak'] = float(20 * np.log10(np.abs(y).max() + 1e-12))
    r['sample_peak'] = float(20 * np.log10(np.abs(x).max() + 1e-12))
    r['clipped'] = int((np.abs(x) >= 0.999).sum())
    rms = np.sqrt(np.mean(x ** 2))
    r['crest'] = float(20 * np.log10(np.abs(x).max() / (rms + 1e-12)))
    st = short_term(x, sr)
    r['st_std'] = float(st.std()) if len(st) > 2 else 0.0
    r['lra'] = float(np.percentile(st, 95) - np.percentile(st, 10)) if len(st) > 3 else 0.0
    r['bands'], f, p = band_shares(x, sr)
    r['centroid'] = float((f * p).sum() / (p.sum() + 1e-18))
    mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
    r['corr'] = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]) if x.std() > 0 else 1.0
    r['side_db'] = float(10 * np.log10((side ** 2).mean() / ((mid ** 2).mean() + 1e-18) + 1e-18))
    lo = signal.sosfiltfilt(signal.butter(4, 120, 'low', fs=sr, output='sos'), x, axis=0)
    r['low_side_db'] = float(10 * np.log10((((lo[:, 0] - lo[:, 1]) / 2) ** 2).mean() / (((lo[:, 0] + lo[:, 1]) / 2) ** 2).mean().clip(1e-18) + 1e-18))
    r['mono_loss'] = float(20 * np.log10(np.sqrt((mid ** 2).mean()) / (np.sqrt(((x ** 2).sum(1) / 2).mean()) + 1e-12) + 1e-12))
    # Mobile phone presence band (1000 - 5000 Hz) mono cancellation check
    mid_bp = signal.sosfiltfilt(signal.butter(4, [1000, 5000], 'bandpass', fs=sr, output='sos'), mid)
    side_bp = signal.sosfiltfilt(signal.butter(4, [1000, 5000], 'bandpass', fs=sr, output='sos'), side)
    st_bp = np.sqrt(((mid_bp ** 2) + (side_bp ** 2)).mean() + 1e-12)
    r['mono_phone_loss'] = float(20 * np.log10(np.sqrt((mid_bp ** 2).mean()) / (st_bp + 1e-12) + 1e-12))
    r['chroma'] = chroma_profile(x, sr).tolist()
    r['dc'] = float(abs(x.mean()))
    on = onsets(x, sr)
    r['n_onsets'] = int(len(on))
    r['onset_rate'] = float(len(on) / (len(x) / sr))
    if bpm:
        tl = timing_looseness(on, bpm)
        r['timing_std_ms'], r['timing_mad_ms'] = tl if tl else (None, None)
    # spectral movement: how much the timbre changes frame to frame (static synth = very low)
    f2, t2, S = signal.stft(x.mean(1), sr, nperseg=2048, noverlap=1536)
    mag = np.abs(S) + 1e-9
    r['spec_flux'] = float(np.mean(np.abs(np.diff(np.log(mag), axis=1))))
    flat = np.exp(np.mean(np.log(mag), 0)) / mag.mean(0)
    r['flatness'] = float(np.median(flat))
    r['head_silence'] = float(np.argmax(np.abs(x).max(1) > 0.003) / sr)
    tail = np.where(np.abs(x).max(1) > 0.003)[0]
    r['tail_silence'] = float((len(x) - tail[-1]) / sr) if len(tail) else 0.0
    r['_x'], r['_sr'] = x, sr
    return r


def verdicts(r, bpm=None, target=None):
    out = []

    def add(level, msg):
        out.append((level, msg))
    if r['clipped'] > 0:
        add('FAIL', f"{r['clipped']} clipped samples - lower the master level / limiter ceiling")
    if r['true_peak'] > -0.9:
        add('WARN', f"true peak {r['true_peak']:.1f} dBTP is hot; streaming transcodes can clip. Aim for -1.5 or lower")
    else:
        add('PASS', f"true peak {r['true_peak']:.1f} dBTP")
    if target is not None:
        d = r['lufs'] - target
        add('PASS' if abs(d) < 1.0 else 'WARN', f"loudness {r['lufs']:.1f} LUFS vs target {target} ({d:+.1f})")
    else:
        add('PASS' if -24 < r['lufs'] < -9 else 'WARN', f"loudness {r['lufs']:.1f} LUFS")
    if r['st_std'] < 0.8 and r['dur'] > 20:
        add('WARN', f"loudness barely changes over time (short-term std {r['st_std']:.1f} dB) - add a dynamics arc (build, drop, breath)")
    else:
        add('PASS', f"dynamics move (short-term loudness std {r['st_std']:.1f} dB, range {r['lra']:.1f} LU)")
    if r['crest'] < 9:
        add('WARN', f"crest factor {r['crest']:.1f} dB - over-compressed / squashed; ease the bus compressor or limiter")
    b = r['bands']
    if b['low-mid 250-500'] > b['bass 60-250'] + 2.0 and b['low-mid 250-500'] > b['mid 0.5-2k'] + 2.0:
        add('WARN', "mud: 250-500 Hz dominates the bass and mid regions - cut 2-4 dB around 300 Hz on chords/pads")
    if b['air >6k'] > b['mid 0.5-2k'] - 6:
        add('WARN', "bright/harsh top end (>6 kHz close to the mids) - typical of raw synth / aliasing; low-pass or de-harsh 3-8 kHz")
    if b['sub <60'] > b['bass 60-250'] - 3:
        add('WARN', "too much sub energy; high-pass non-bass tracks and check small speakers")
    if r['centroid'] > 3500:
        add('WARN', f"spectral centroid {r['centroid']:.0f} Hz is very bright (thin/buzzy)")
    if r['low_side_db'] > -12:
        add('WARN', f"low end is wide ({r['low_side_db']:.0f} dB side/mid below 120 Hz) - mono the bass (mono_below)")
    if r['mono_loss'] < -3:
        add('WARN', f"mono fold-down loses {abs(r['mono_loss']):.1f} dB - phase/width problem")
    if r.get('mono_phone_loss', 0.0) < -3.5:
        add('WARN', f"mobile phone presence loss: mono fold-down loses {abs(r['mono_phone_loss']):.1f} dB in 1-5 kHz - check stereo wideners / Haas phase cancellation")
    if r['corr'] > 0.98 and r['dur'] > 5:
        add('WARN', "stereo image is essentially mono - pan layers / widen pads / use room reverb")
    if r['dc'] > 0.01:
        add('WARN', f"DC offset {r['dc']:.3f}")
    if r['head_silence'] > 1.0:
        add('WARN', f"{r['head_silence']:.1f}s of silence at the start")
    if bpm and r.get('timing_std_ms') is not None:
        s = r['timing_std_ms']
        if s < 3.0:
            add('WARN', f"onsets sit on the grid within {s:.1f} ms - sounds mechanical; use humanize 'natural' or 'loose'")
        else:
            add('INFO', f"onset-vs-grid spread {s:.0f} ms (rough: audio onset detection is noisy; the exact humanize numbers are printed by render_natural.py)")
    if r['spec_flux'] < 0.08:
        add('WARN', f"timbre is static (spectral flux {r['spec_flux']:.3f}) - sustained synth-like; add expression, vibrato, layered articulations")
    return out


def _bark(f):
    """Critical-band rate in Bark (Traunmuller): 26.81*f/(1960+f) - 0.53."""
    f = np.asarray(f, dtype=float)
    return 26.81 * f / (1960.0 + f) - 0.53


def cochlear_roughness_check(path_or_audio, sr=44100, score=None, model=None):
    """2.1 Cochlear sensory roughness, two models.

    Both models take the ten loudest resolved partials in ROUGHNESS_BAND_HZ per 1.0 s Hann frame and reduce the
    pair contributions to the mean of the three strongest (density-independent: a sum grows with the number of
    parts and failed every 6+ part chord).

      model="legacy"       the Plomp-Levelt/Sethares pair weight min(a_norm) * kernel, amplitudes normalised per
                           frame. Unchanged from the original implementation, to 4 decimals.
      model="level_aware"  absolute partial level (dB SPL, calibrated against the file's own loudness); each partial
                           reduced to its margin above the higher of its simultaneous masking threshold and the
                           absolute threshold; the Vassilakis amplitude terms
                           0.5 * (Amin*Amax)^0.1 * (2*Amin/(Amin+Amax))^3.11 * kernel.
                           A pair at or below threshold has A = 0 and contributes nothing.

    `model` defaults to the profile's `roughness.model` (itself default "legacy"), so nothing changes until a piece
    asks for the new model. With the new model the legacy value is still computed and reported as
    INFO "cochlear_roughness_legacy", so the two can be compared. Doc: knowledgebase/sound-design/roughness.md.
    Returns (rows, dict(mean_roughness=..., max_roughness=...)).
    """
    if isinstance(path_or_audio, str):
        x, sr = load(path_or_audio)
    else:
        x = path_or_audio
        if x.ndim == 1:
            x = np.column_stack([x, x])

    mono = x.mean(axis=1) if x.ndim == 2 else x
    dur = len(mono) / sr
    if dur < 1.0:
        return [('PASS', 'cochlear_roughness', 'Audio duration < 1.0s; roughness check skipped')], dict(mean_roughness=0.0, max_roughness=0.0)

    # the model, its numbers and the two legacy knobs all come from the `roughness` row of the gate profile
    intent = dict(is_ambient=False, is_tense=False, is_dance=False, is_cliffhanger=False)
    scale, outro_resolve = 1.0, True
    model_name = 'legacy'
    calib_spl_db, band_bark = ROUGHNESS_CALIB_SPL_DB, ROUGHNESS_MASK_BAND_BARK
    slope_up, slope_down = ROUGHNESS_MASK_SLOPE_UP_DB_BARK, ROUGHNESS_MASK_SLOPE_DOWN_DB_BARK
    median_la = ROUGHNESS_MEDIAN_LEVEL_AWARE
    if score:
        try:
            import pattern_audit
            import gate_profiles
            intent = pattern_audit.get_intent_profile(score)
            gp = gate_profiles.resolve(score)
            scale, outro_resolve = gp.param('roughness', 'scale'), gp.param('roughness', 'outro_resolve')
            model_name = str(gp.param('roughness', 'model'))
            calib_spl_db = float(gp.param('roughness', 'calib_spl_db'))
            band_bark = float(gp.param('roughness', 'mask_band_bark'))
            slope_up = float(gp.param('roughness', 'mask_slope_up_db_bark'))
            slope_down = float(gp.param('roughness', 'mask_slope_down_db_bark'))
            median_la = float(gp.param('roughness', 'median'))
        except Exception:
            pass
    if model is not None:
        model_name = str(model)
    if model_name not in ('legacy', 'level_aware'):
        raise ValueError(f'roughness model must be "legacy" or "level_aware", not {model_name!r}')

    win = int(sr)
    hop = int(sr // 2)
    if len(mono) < win:
        win = len(mono)
        hop = max(win // 2, 1024)
    n_frames = max(1, (len(mono) - win) // hop + 1)

    # Absolute level: the file's own integrated loudness is placed at calib_spl_db, so a partial keeps the level it
    # really has here (a pp frame is judged as pp) and two masters are compared at one playback level.
    lufs_file = None
    if model_name != 'legacy':
        try:
            sig = x[:, :2] if x.ndim == 2 else np.column_stack([x, x])
            lufs_file = float(lufs_meter(sig, sr))
            if not np.isfinite(lufs_file):
                lufs_file = None
        except Exception:
            lufs_file = None
    calib = (calib_spl_db - lufs_file) if lufs_file is not None else 0.0

    def ath_of(freqs):
        try:
            import quality_gate
            return np.asarray(quality_gate._ath_db(freqs), dtype=float)
        except Exception:                       # naturalness_check used on its own, without the gate package
            k = np.maximum(np.asarray(freqs, dtype=float), 20.0) / 1000.0
            return 3.64 * k ** -0.8 - 6.5 * np.exp(-0.6 * (k - 3.3) ** 2) + 1e-3 * k ** 4

    hann = np.hanning(win)
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    band_mask = (freqs >= ROUGHNESS_BAND_HZ[0]) & (freqs <= ROUGHNESS_BAND_HZ[1])
    b_freqs = freqs[band_mask]

    roughness = []
    roughness_legacy = []
    frame_times = []

    for i in range(n_frames):
        t_sec = (i * hop + win / 2.0) / sr
        seg = mono[i * hop : i * hop + win] * hann
        mag = np.abs(np.fft.rfft(seg))[band_mask]
        frame_times.append(t_sec)

        if len(mag) < 3:
            roughness.append(np.nan)
            roughness_legacy.append(np.nan)
            continue
        peaks = np.where((mag[1:-1] > mag[:-2]) & (mag[1:-1] > mag[2:]))[0] + 1
        max_a = float(np.max(mag)) if len(mag) > 0 else 0.0
        if max_a < 1e-6 or len(peaks) < 2:
            roughness.append(np.nan)
            roughness_legacy.append(np.nan)
            continue

        sig_peaks = peaks[mag[peaks] >= 0.03 * max_a]
        # Plomp-Levelt roughness is about beating between partials. A bin of noise is not a partial, and noise (water, wind, rain)
        # throws up random peaks that would score as clashes; keep only peaks that stand PEAK_PROMINENCE_DB above the local floor.
        floor = ndimage.median_filter(mag, size=PEAK_FLOOR_BINS, mode='nearest')
        sig_peaks = sig_peaks[mag[sig_peaks] >= floor[sig_peaks] * 10 ** (PEAK_PROMINENCE_DB / 20.0)]
        if len(sig_peaks) < 2:
            roughness.append(np.nan)
            roughness_legacy.append(np.nan)
            continue
        # broad-band frame (drum hit, cymbal, noise): its "peaks" are random, not partials that can beat
        tonal = float(np.sum(mag[sig_peaks] ** 2) / (np.sum(mag ** 2) + 1e-30))
        if tonal < TONAL_MIN_FRACTION:
            roughness.append(np.nan)
            roughness_legacy.append(np.nan)
            continue

        top_idx = sig_peaks[np.argsort(mag[sig_peaks])[-10:]]
        top_idx = top_idx[mag[top_idx] >= max_a * 10 ** (ROUGHNESS_AUDIBLE_DB / 20.0)]
        if len(top_idx) < 2:
            roughness.append(np.nan)
            roughness_legacy.append(np.nan)
            continue
        f_p = b_freqs[top_idx]
        a_norm = mag[top_idx] / max_a

        order = np.argsort(f_p)
        f_p, a_norm = f_p[order], a_norm[order]

        contrib = []
        for j in range(len(f_p)):
            for k in range(j + 1, len(f_p)):
                f1, f2 = f_p[j], f_p[k]
                S = 0.24 / (0.0207 * f1 + 18.96)
                df = f2 - f1
                w = np.exp(-3.51 * S * df) - np.exp(-5.75 * S * df)
                if w > 0.0:
                    contrib.append(float(min(a_norm[j], a_norm[k]) * w))
        # three strongest clashes, averaged: independent of how many parts happen to be sounding
        contrib.sort(reverse=True)
        legacy_val = float(np.mean(contrib[:3])) if contrib else 0.0
        roughness_legacy.append(legacy_val)

        if model_name == 'legacy' or lufs_file is None:
            roughness.append(legacy_val)
            continue

        # ---- level-aware: absolute level, masked threshold, Vassilakis amplitude terms
        a_abs = mag[top_idx][order] / (win * 0.5)                 # sine amplitude, full scale = 1
        spl = 20.0 * np.log10(np.maximum(a_abs, 1e-12)) + calib   # dB SPL at the calibration playback level
        z = _bark(f_p)
        ath = ath_of(f_p)
        mask = np.full(len(f_p), -np.inf)
        for j in range(len(f_p)):
            dz = np.abs(z - z[j])
            near = (dz <= band_bark) & (dz > 0.0)
            if not near.any():
                continue
            # masking spreads further upwards than downwards: a different slope on each side of the masker
            slope = np.where(f_p > f_p[j], slope_up, slope_down)
            mask = np.maximum(mask, np.where(near, spl[j] - slope * dz, -np.inf))
        atten = np.maximum(0.0, mask - spl)                       # dB the masker pushes this partial under the mask
        heard = np.clip((spl - ath) / ROUGHNESS_SL_RAMP_DB, 0.0, 1.0)  # 0 at the absolute threshold, 1 by 10 dB SL
        A = heard * 10.0 ** ((spl - 94.0 - atten) / 20.0)         # amplitude (1 Pa = 94 dB SPL), mask-attenuated

        lev = []
        for j in range(len(f_p)):
            for k in range(j + 1, len(f_p)):
                if A[j] <= 0.0 or A[k] <= 0.0:
                    continue
                f1, f2 = f_p[j], f_p[k]
                S = 0.24 / (0.0207 * f1 + 18.96)
                df = f2 - f1
                w = np.exp(-3.51 * S * df) - np.exp(-5.75 * S * df)
                if w <= 0.0:
                    continue
                amin, amax = (A[j], A[k]) if A[j] <= A[k] else (A[k], A[j])
                lev.append(float((amin * amax) ** 0.1 * 0.5 * (2.0 * amin / (amin + amax)) ** 3.11 * w))
        lev.sort(reverse=True)
        roughness.append(float(np.mean(lev[:3])) if lev else 0.0)

    r_all = np.array(roughness, dtype=float)
    r_legacy = np.array(roughness_legacy, dtype=float)
    r_arr = r_all[~np.isnan(r_all)]
    r_leg = r_legacy[~np.isnan(r_legacy)]
    if len(r_arr) < TONAL_MIN_FRAMES:
        # Nothing to judge is stated, never a silent pass: a noise bed or a percussion-only piece has no resolved partials to beat.
        return ([('INFO', 'cochlear_roughness',
                  f'{len(r_arr)} of {len(r_all)} frames hold resolved partials (the rest are broad-band, i.e. drums, noise or silence): '
                  'too few to judge cochlear roughness, so the row is not applied')],
                dict(mean_roughness=round(float(np.mean(r_arr)), 4) if len(r_arr) else 0.0,
                     max_roughness=round(float(np.max(r_arr)), 4) if len(r_arr) else 0.0))
    r_med = float(np.median(r_arr))
    r_mean = float(np.mean(r_arr))
    r_max = float(np.max(r_arr))
    legacy_med = float(np.median(r_leg)) if len(r_leg) else 0.0
    legacy_max = float(np.max(r_leg)) if len(r_leg) else 0.0

    median_base = ROUGHNESS_MEDIAN if model_name == 'legacy' else median_la
    abs_thresh = median_base * scale            # `scale` applied once, here
    rel_thresh = max(abs_thresh, ROUGHNESS_RELATIVE * r_med)

    rows = []
    if model_name != 'legacy':
        rows.append(('INFO', 'cochlear_roughness_legacy',
                     f'legacy model on the same frames: median {legacy_med:.3f}, max {legacy_max:.3f} '
                     '(the level-aware model is the one judged above)'))
    spikes = []
    dyn = score.get('dynamics', []) if score else []
    if r_med > abs_thresh:
        rows.append(('FAIL', 'cochlear_roughness',
                     f"Cochlear sensory roughness chronically high (median {r_med:.3f} > {abs_thresh:.3f}); "
                     "continuous clashing overtones throughout piece. Separate chord voices by at least a minor 3rd or notch clashing frequencies."))
    else:
        for i in range(len(r_all)):
            if np.isnan(r_all[i]):
                continue
            if r_all[i] > rel_thresh:
                t_spike = frame_times[i]
                dyn_val = 0.5
                if dyn and len(dyn) >= 2:
                    dyn_times = [d[0] for d in dyn]
                    dyn_vals = [d[1] for d in dyn]
                    bpm = score.get('bpm', 120)
                    sec_times = [b * 60.0 / bpm for b in dyn_times]
                    dyn_val = float(np.interp(t_spike, sec_times, dyn_vals))
                if dyn_val < 0.75:
                    spikes.append((t_spike, r_all[i], rel_thresh))

        if spikes:
            t_sp, val_sp, thr_sp = max(spikes, key=lambda sp_: sp_[1] / sp_[2])
            # A percussion hit is broadband, so its random peaks read as a one-frame clash on every real master (measured:
            # 0.13-0.16 against a 0.03-0.05 median on all six). Sustained roughness is different: the clashing partials stay
            # put, so several frames clear the limit. FAIL needs that persistence; an isolated frame is reported as a WARN.
            need = max(3, int(round(0.02 * len(r_all))))
            if len(spikes) >= need:
                rows.append(('FAIL', 'cochlear_roughness',
                             f"Cochlear critical-band roughness at {t_sp:.1f}s ({val_sp:.3f} > {thr_sp:.3f}) and in "
                             f"{len(spikes)} frames: two instruments clash within 1/4 critical bandwidth for a sustained stretch. "
                             "Separate them by a minor 3rd, by register or by level."))
            else:
                rows.append(('WARN', 'cochlear_roughness',
                             f"one-frame roughness at {t_sp:.1f}s ({val_sp:.3f} > {thr_sp:.3f}), {len(spikes)} frame(s) of "
                             f"{len(r_arr)} (a FAIL needs {need}): reads as a transient or a drum hit, not a sustained clash"))
        else:
            rows.append(('PASS', 'cochlear_roughness',
                         f"Cochlear sensory roughness within physiological threshold (mean {r_mean:.3f}, max {r_max:.3f} <= {rel_thresh:.3f})"))

    if dur >= 6.0 and outro_resolve and not intent['is_cliffhanger']:
        outro_mask = np.array(frame_times) >= (dur - 3.0)
        outro_vals = r_all[outro_mask]
        outro_vals = outro_vals[~np.isnan(outro_vals)]
        if len(outro_vals) >= 2:
            outro_r = float(np.mean(outro_vals))
            # Relative to the piece, with a floor so a very quiet tail is not judged on rounding noise. There is no absolute
            # ceiling here: "does it resolve" is a comparison with this piece, and a full ensemble cadence is not a defect.
            target_outro = max(r_med * ROUGHNESS_OUTRO_RATIO, abs_thresh * 0.6)
            if outro_r > target_outro:
                rows.append(('FAIL', 'cochlear_roughness',
                             f"Sensory roughness does not resolve at outro (final 3s roughness {outro_r:.3f} > {target_outro:.3f}). "
                             "Cadence into a clean consonant triad."))

    metrics = dict(mean_roughness=round(r_mean, 4), max_roughness=round(r_max, 4),
                   frames=[round(float(v), 4) if not np.isnan(v) else None for v in r_all])
    if model_name != 'legacy':
        metrics['frames_legacy'] = [round(float(v), 4) if not np.isnan(v) else None for v in r_legacy]
        metrics['mean_roughness_legacy'] = round(legacy_med, 4)
        metrics['max_roughness_legacy'] = round(legacy_max, 4)
    return rows, metrics

FLUTTER_ROLES = ('pad', 'melody', 'lead', 'counter')   # counter added: on the Amazon render the flute counter-line was the worst (0.23)
FLUTTER_BAND_HZ = (6.0, 25.0)       # faster than vibrato (4-7 Hz), slower than pitch: the choppy-gate / stepping zone
FLUTTER_WARN = 0.18                 # depth = peak amplitude swing in the band, as a fraction of the mean level
FLUTTER_FAIL = None                 # shortcut: no FAIL until the WARN level is calibrated on real stems; set e.g. 0.28 then


def flutter_depth(x, sr=44100, win_s=1.5, hop_s=0.5, span_db=30.0):
    """Depth of 6-25 Hz amplitude modulation inside the sustained parts of one stem (sounding = within span_db of its loudest
    block, so a quiet raw stem is judged like a loud one).
    Returns (depth, offset_s) of the 75th-percentile window: a persistent flutter counts, one note attack does not.
    A pure sine amplitude modulation of depth m scores m."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    blk = int(0.05 * sr)
    k = len(mono) // blk
    if k < int(win_s / 0.05):
        return 0.0, 0.0
    db = 10 * np.log10(np.mean(mono[:k * blk].reshape(k, blk) ** 2, axis=1) + 1e-12)
    on = db > max(db.max() - span_db, -80.0)
    lp = signal.butter(4, 40.0, 'low', fs=sr, output='sos')
    step = max(1, sr // 200)                       # envelope control rate ~200 Hz
    fs_c = sr / step
    bp = signal.butter(2, FLUTTER_BAND_HZ, 'band', fs=fs_c, output='sos')
    depths, offsets = [], []
    w, h = int(win_s / 0.05), int(hop_s / 0.05)
    for i0 in range(0, k - w + 1, h):
        if not on[i0:i0 + w].all():
            continue                               # a window must be sounding all the way: rests and note gaps are not flutter
        seg = mono[i0 * blk:(i0 + w) * blk]
        env = signal.sosfiltfilt(lp, np.abs(signal.hilbert(seg)))[::step]
        m = float(env.mean())
        if m < 1e-9:
            continue
        mod = signal.sosfiltfilt(bp, env / m)
        mod = mod[int(0.2 * fs_c):-int(0.2 * fs_c)]  # drop the filter's edge ringing
        depths.append(float(np.sqrt(2.0 * np.mean(mod ** 2))))
        offsets.append(i0 * 0.05)
    if not depths:
        return 0.0, 0.0
    j = int(np.argsort(depths)[int(0.75 * (len(depths) - 1))])
    return depths[j], offsets[j]


def modulation_flutter_check(stems, score, sr=44100):
    """Gate rows for rapid amplitude flutter (chopped, stepped or pumping sustained notes) on pad, melody and lead stems.
    WARN above the profile's `modulation_flutter.warn` (FLUTTER_WARN by default); FAIL above FLUTTER_FAIL once that is set."""
    roles = {t.get('name'): t.get('role') for t in (score or {}).get('tracks', [])}
    warn = FLUTTER_WARN
    try:
        import gate_profiles
        warn = float(gate_profiles.resolve(score or {}).param('modulation_flutter', 'warn'))
    except Exception:
        pass
    rows, worst = [], 0.0
    for name, x in (stems or {}).items():
        if roles.get(name) not in FLUTTER_ROLES:
            continue
        depth, at = flutter_depth(np.asarray(x, dtype=np.float64), sr)
        worst = max(worst, depth)
        if depth > warn:
            level = 'FAIL' if (FLUTTER_FAIL is not None and depth > FLUTTER_FAIL) else 'WARN'
            rows.append((level, 'modulation_flutter',
                         f'"{name}" ({roles[name]}) swings {depth:.2f} of its level at 6-25 Hz (around {at:.1f}s into the stem): '
                         'rapid flutter, heard as chopped or stepped notes. Check vibrato depth, expression steps, or chord voices beating on separate channels.'))
    if not rows:
        rows.append(('PASS', 'modulation_flutter', f'no pad, melody or lead stem flutters at 6-25 Hz (worst {worst:.2f} <= {warn})'))
    return rows


def plot(r, png):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x, sr = r['_x'], r['_sr']
    fig, ax = plt.subplots(3, 1, figsize=(11, 8), gridspec_kw={'height_ratios': [3, 1.2, 1.2]})
    f, t, S = signal.stft(x.mean(1), sr, nperseg=4096, noverlap=3072)
    db = 20 * np.log10(np.abs(S) + 1e-6)
    m = (f > 30) & (f < 12000)
    ax[0].pcolormesh(t, f[m], db[m], vmin=db.max() - 85, vmax=db.max(), shading='auto', cmap='magma')
    ax[0].set_yscale('symlog', linthresh=500)
    ax[0].set_ylabel('Hz'); ax[0].set_title(os.path.basename(r['path']) + f"   {r['lufs']:.1f} LUFS  {r['true_peak']:.1f} dBTP")
    st = short_term(x, sr, 1.0, 0.5)
    ax[1].plot(np.arange(len(st)) * 0.5 + 0.5, st); ax[1].set_ylabel('LUFS (1 s)'); ax[1].grid(alpha=.3)
    tt = np.arange(len(x)) / sr
    ax[2].plot(tt[::50], x[::50, 0], lw=.3); ax[2].plot(tt[::50], x[::50, 1], lw=.3); ax[2].set_ylabel('wave'); ax[2].set_xlabel('s')
    plt.tight_layout(); plt.savefig(png, dpi=90); plt.close(fig)


def print_report(r, bpm=None, target=None):
    print(f"\n== {r['path']}  ({r['dur']:.1f}s, {r['sr']} Hz) ==")
    print(f"loudness {r['lufs']:.1f} LUFS | true peak {r['true_peak']:.1f} dBTP | crest {r['crest']:.1f} dB | "
          f"LRA~{r['lra']:.1f} | centroid {r['centroid']:.0f} Hz")
    print('bands (dB rel. total): ' + ', '.join(f"{k.split()[0]} {v:.0f}" for k, v in r['bands'].items()))
    print(f"stereo: corr {r['corr']:.2f}, side/mid {r['side_db']:.1f} dB, low-end side {r['low_side_db']:.0f} dB, mono loss {r['mono_loss']:.1f} dB")
    extra = f" | timing std {r['timing_std_ms']:.1f} ms" if r.get('timing_std_ms') is not None else ''
    print(f"onsets {r['n_onsets']} ({r['onset_rate']:.1f}/s) | spectral flux {r['spec_flux']:.3f} | flatness {r['flatness']:.3f}{extra}")
    for lv, msg in verdicts(r, bpm, target):
        print(f"  [{lv}] {msg}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('wav', nargs='*')
    ap.add_argument('--compare', nargs=2, metavar=('A', 'B'))
    ap.add_argument('--bpm', type=float)
    ap.add_argument('--target-lufs', type=float)
    ap.add_argument('--png', help='spectrogram output path (default: <wav>.png)')
    a = ap.parse_args()
    paths = list(a.compare) if a.compare else a.wav
    if not paths:
        ap.error('give a wav (or --compare A B)')
    for p in paths:
        r = analyse(p, a.bpm, a.target_lufs)
        print_report(r, a.bpm, a.target_lufs)
        plot(r, a.png if (a.png and len(paths) == 1) else os.path.splitext(p)[0] + '_check.png')


if __name__ == '__main__':
    main()
