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
"""clone_instrument.py - turn a recording of ANY instrument into a playable instrument.

Two practical cloning methods that run on a CPU in seconds (no neural net, no GPU):

  sampler   (best realism)  Cut the recording into notes (pitch tracked with YIN), keep them as
            multisamples with velocity layers. Playing a note picks the nearest sample, re-pitches it
            (max ~ +-4 semitones sounds natural), darkens soft notes, and extends long notes with
            phase-aligned crossfaded grains. Needs a recording that contains several different notes:
            a scale, a few sustained notes, or a melodic phrase. More notes recorded = better.

  harmonic  (works from ONE note) Analysis/resynthesis in the spirit of DDSP: measures the spectral
            envelope of the harmonics, inharmonicity (stiff strings, bells), noise colour, attack and
            decay, vibrato - then re-synthesises any pitch with those measured traits (additive
            harmonics + coloured noise). Good for the timbre "character"; less lifelike than sampler.

    python3 clone_instrument.py analyze recording.wav --name my_sitar --mode sampler --out clones/
    python3 clone_instrument.py analyze one_note.wav   --name my_bell  --mode harmonic --out clones/
    python3 clone_instrument.py play clones/my_sitar --notes 60 62 64 67 --out demo.wav
    python3 clone_instrument.py sfz clones/my_sitar       # export .sfz for sforzando / DAWs

Use it in a score:   {"name":"lead","instrument":"clone:clones/my_sitar","role":"melody","notes":[...]}

Honest limits: monophonic source recordings work best (one note at a time); chords/mixes cannot be
split into notes by this tool. Do not clone someone else's copyrighted sample pack or a specific
person's voice without permission. A neural cloner (DDSP, few-shot timbre models) can reproduce more
detail but needs a GPU and training - see references/instrument-cloning.md.
"""
import argparse
import json
import os
import sys
from fractions import Fraction

import numpy as np
import soundfile as sf
from scipy import signal

SR = 44100


# ------------------------------------------------------------------------------------------------
# pitch tracking (YIN, de Cheveigne & Kawahara 2002) & acoustic analysis (from tonal.py / beats.py)
# ------------------------------------------------------------------------------------------------

def extract_spectral_onsets(x, sr, hop=256):
    """Spectral-flux transient onset times in seconds (from beats.py / naturalness_check.py)."""
    mono = x.mean(1) if x.ndim > 1 else x
    f, t, S = signal.stft(mono, sr, nperseg=1024, noverlap=1024 - hop)
    mag = np.log1p(np.abs(S) * 50)
    flux = np.maximum(0, np.diff(mag, axis=1)).sum(0)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    peaks, _ = signal.find_peaks(flux, height=1.2, distance=int(0.08 * sr / hop))
    return t[1:][peaks]


def extract_harmonic_partials(x, sr, f0, n_fft=8192):
    """8192-point FFT harmonic partial extraction (from tonal.py).
    Extracts peak partials rising >= 12 dB over the local median floor.
    """
    mono = x.mean(1) if x.ndim > 1 else x
    if len(mono) < n_fft:
        mono = np.pad(mono, (0, n_fft - len(mono)))
    mid_idx = max(0, len(mono) // 2 - n_fft // 2)
    seg = mono[mid_idx:mid_idx + n_fft] * np.hanning(n_fft)
    spec = np.abs(np.fft.rfft(seg))
    fr = np.fft.rfftfreq(n_fft, 1.0 / sr)
    med = np.median(spec) + 1e-12
    
    # 12 dB over median threshold
    peaks, _ = signal.find_peaks(spec, height=med * 3.98)
    partials = []
    for p in peaks:
        freq = float(fr[p])
        if 50.0 <= freq <= min(16000.0, sr * 0.48):
            partials.append({
                'f': round(freq, 2),
                'db': round(float(20 * np.log10(spec[p] / (np.max(spec) + 1e-12) + 1e-9)), 1),
                'harmonic_ratio': round(freq / max(1.0, f0), 3)
            })
    return partials[:16]


def yin(x, sr, fmin=55.0, fmax=2200.0, frame=2048, hop=512, thr=0.15):
    """Return (f0_hz, confidence 0..1, rms_db) per hop. f0=0 when unvoiced."""
    tmax = int(sr / fmin)
    tmin = max(2, int(sr / fmax))
    n = (len(x) - frame - tmax) // hop
    f0 = np.zeros(max(n, 0))
    conf = np.zeros(max(n, 0))
    rmsdb = np.zeros(max(n, 0))
    w = frame
    for i in range(max(n, 0)):
        seg = x[i * hop: i * hop + w + tmax]
        a = seg[:w]
        rmsdb[i] = 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9)
        if rmsdb[i] < -60:
            continue
        # difference function via FFT autocorrelation
        nfft = 1 << int(np.ceil(np.log2(len(seg) + w)))
        fa, fs = np.fft.rfft(a, nfft), np.fft.rfft(seg, nfft)
        r = np.fft.irfft(fs * np.conj(fa), nfft)[:tmax]
        cs = np.concatenate([[0], np.cumsum(seg ** 2)])
        e0 = cs[w]
        et = cs[w:w + tmax] - cs[:tmax]
        d = e0 + et - 2 * r
        d[0] = 0
        cm = np.ones_like(d)
        cm[1:] = d[1:] * np.arange(1, tmax) / (np.cumsum(d[1:]) + 1e-12)
        t = None
        for tau in range(tmin, tmax - 1):
            if cm[tau] < thr:
                while tau + 1 < tmax - 1 and cm[tau + 1] < cm[tau]:
                    tau += 1
                t = tau
                break
        if t is None:
            continue
        # parabolic interpolation
        a_, b_, c_ = cm[t - 1], cm[t], cm[t + 1]
        den = a_ - 2 * b_ + c_
        tau_f = t + (0.5 * (a_ - c_) / den if abs(den) > 1e-12 else 0.0)
        f0[i] = sr / tau_f
        conf[i] = float(np.clip(1 - cm[t], 0, 1))
    return f0, conf, rmsdb


def hz2midi(f):
    return 69 + 12 * np.log2(np.maximum(f, 1e-6) / 440.0)


def midi2hz(m):
    return 440.0 * 2 ** ((np.asarray(m, dtype=float) - 69) / 12.0)


# ------------------------------------------------------------------------------------------------
# note segmentation
# ------------------------------------------------------------------------------------------------

def segment_notes(x, sr, hop=512, min_len=0.15):
    f0, conf, rdb = yin(x, sr, hop=hop)
    midi = np.where(f0 > 0, hz2midi(f0), 0)
    voiced = (conf > 0.75) & (rdb > rdb.max() - 45) & (f0 > 0)
    segs, cur = [], None
    for i in range(len(f0)):
        if not voiced[i]:
            if cur and i - cur['end'] > 2:
                segs.append(cur)
                cur = None
            continue
        onset = i >= 3 and rdb[i] - rdb[i - 3] > 5.0 and rdb[i] > rdb[i - 1]
        if cur is None:
            cur = dict(start=i, end=i, m=[midi[i]])
        else:
            med = np.median(cur['m'][-8:])
            if abs(midi[i] - med) > 0.7 or (onset and i - cur['start'] > 6):
                segs.append(cur)
                cur = dict(start=i, end=i, m=[midi[i]])
            else:
                cur['end'] = i
                cur['m'].append(midi[i])
    if cur:
        segs.append(cur)
    out = []
    # Extract spectral-flux onset times for sub-millisecond attack alignment
    onsets_s = extract_spectral_onsets(x, sr)
    for k, s in enumerate(segs):
        if (s['end'] - s['start']) * hop / sr < min_len:
            continue
        nxt = segs[k + 1]['start'] if k + 1 < len(segs) else len(x) // hop
        t_est = s['start'] * hop / sr
        near_onsets = onsets_s[np.abs(onsets_s - t_est) < 0.06]
        if len(near_onsets) > 0:
            a = max(0, int((near_onsets[0] - 0.005) * sr))
        else:
            a = max(0, s['start'] * hop - hop)
        b = min(len(x), int(min(nxt * hop, s['end'] * hop + 0.30 * sr)))
        out.append(dict(a=a, b=b, midi=float(np.median(s['m'])), rms_db=float(np.max(rdb[s['start']:s['end'] + 1])),
                        voiced_len=(s['end'] - s['start']) * hop / sr))
    return out


# ------------------------------------------------------------------------------------------------
# sampler instrument
# ------------------------------------------------------------------------------------------------

def _to_mono(x):
    return x.mean(1) if x.ndim > 1 else x


def build_sampler(path, name, out_dir, min_len=0.15, max_notes=60):
    x, sr = sf.read(path, always_2d=True)
    xm = _to_mono(x)
    if sr != SR:
        xm = signal.resample_poly(xm, SR, sr)
        x = signal.resample_poly(x, SR, sr, axis=0)
        sr = SR
    xm = xm / (np.abs(xm).max() + 1e-9) * 0.9
    notes = segment_notes(xm, sr, min_len=min_len)
    if not notes:
        raise RuntimeError('no pitched notes found - record single notes / a scale / a monophonic phrase, '
                           'close to the microphone, little reverb')
    d = os.path.join(out_dir, name)
    os.makedirs(os.path.join(d, 'samples'), exist_ok=True)
    notes = sorted(notes, key=lambda n: -n['voiced_len'])[:max_notes]
    rms_all = np.array([n['rms_db'] for n in notes])
    zones = []
    for i, n in enumerate(sorted(notes, key=lambda n: n['midi'])):
        seg = xm[n['a']:n['b']].copy()
        fade = int(0.004 * sr)
        seg[:fade] *= np.linspace(0, 1, fade)
        seg[-int(0.02 * sr):] *= np.linspace(1, 0, int(0.02 * sr))
        spec = np.abs(np.fft.rfft(seg[:min(len(seg), 8192)] * np.hanning(min(len(seg), 8192))))
        fr = np.fft.rfftfreq(min(len(seg), 8192), 1 / sr)
        cen = float((spec * fr).sum() / (spec.sum() + 1e-9))
        vel = float(np.interp(n['rms_db'], [rms_all.min() - 1e-3, rms_all.max() + 1e-3], [0.35, 0.95])) if len(notes) > 1 else 0.7
        fn = f'n{i:02d}_{n["midi"]:.2f}.wav'
        sf.write(os.path.join(d, 'samples', fn), seg, sr, subtype='PCM_24')
        zones.append(dict(file=f'samples/{fn}', midi=round(n['midi'], 3), vel=round(vel, 3), rms_db=round(n['rms_db'], 1),
                          centroid=round(cen), dur=round(len(seg) / sr, 3)))
    meta = dict(type='sampler', name=name, sr=sr, zones=zones, source=os.path.basename(path))
    json.dump(meta, open(os.path.join(d, 'instrument.json'), 'w', encoding='utf-8'), indent=1)
    return d, meta


def _ratio(semis):
    fr = Fraction(2 ** (semis / 12.0)).limit_denominator(2000)
    return fr.numerator, fr.denominator


def _xcorr_align(tail, grain, maxlag):
    n = min(len(tail), len(grain) - maxlag)
    if n <= 16:
        return 0
    best, bl = -1e9, 0
    for lag in range(0, maxlag, max(1, maxlag // 200)):
        c = float(np.dot(tail[-n:], grain[lag:lag + n]))
        if c > best:
            best, bl = c, lag
    return bl


def extend_note(x, target, sr, f0):
    """Make a note longer than its recording by crossfading phase-aligned grains from the stable tail."""
    if len(x) >= target:
        return x[:target]
    g0, g1 = int(len(x) * 0.45), int(len(x) * 0.92)
    grain = x[g0:g1]
    if len(grain) < int(0.12 * sr):
        return np.pad(x, (0, target - len(x)))
    xf = min(int(0.10 * sr), len(grain) // 3)
    period = int(sr / max(f0, 40))
    out = x[:g1].copy()
    win = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
    guard = 0
    while len(out) < target and guard < 400:
        lag = _xcorr_align(out[-xf:], grain, min(period * 4, max(1, len(grain) - xf - 1)))
        g = grain[lag:]
        if len(g) <= xf:
            break
        out[-xf:] = out[-xf:] * (1 - win) + g[:xf] * win
        out = np.concatenate([out, g[xf:]])
        guard += 1
    return out[:target] if len(out) >= target else np.pad(out, (0, target - len(out)))


class SamplerInstrument:
    def __init__(self, d):
        self.dir = d
        self.meta = json.load(open(os.path.join(d, 'instrument.json'), encoding='utf-8'))
        self.sr = self.meta['sr']
        self.zones = self.meta['zones']
        self.cache = {}
        self.rr = {}

    def _load(self, z):
        if z['file'] not in self.cache:
            self.cache[z['file']] = sf.read(os.path.join(self.dir, z['file']))[0]
        return self.cache[z['file']]

    def pick(self, midi, vel):
        costs = [abs(z['midi'] - midi) + 4.0 * abs(z['vel'] - vel) for z in self.zones]
        order = np.argsort(costs)
        # round-robin among near-equal candidates so repeated notes are not identical samples
        cand = [i for i in order[:3] if costs[i] <= costs[order[0]] + 0.6]
        k = self.rr.get(int(midi), 0)
        self.rr[int(midi)] = k + 1
        return self.zones[cand[k % len(cand)]]

    def play(self, midi, vel=0.7, dur=1.0, sr=SR, release=0.12):
        z = self.pick(midi, vel)
        x = self._load(z)
        semis = midi - z['midi']
        if abs(semis) > 0.02:
            up, down = _ratio(semis)
            x = signal.resample_poly(x, down, up)          # raising pitch shortens the sample
        if vel < 0.8:                                       # soft notes are darker
            fc = float(np.clip(18000 * (max(vel, 0.05) / 0.8) ** 2.2, 1500, 18000))
            if fc < 17000:
                x = signal.sosfilt(signal.butter(2, fc, 'low', fs=self.sr, output='sos'), x)
        want = int((dur + release) * sr)
        f0 = float(midi2hz(midi))
        x = extend_note(x, want, sr, f0) if len(x) < want else x[:want]
        nrel = int(release * sr)
        x = x.copy()
        x[-nrel:] *= np.linspace(1, 0, nrel) ** 2
        g = (max(vel, 0.05) / max(z['vel'], 0.05)) ** 1.1
        return (x * g).astype(np.float32)


# ------------------------------------------------------------------------------------------------
# harmonic ("DDSP-lite") instrument from a single note
# ------------------------------------------------------------------------------------------------

def build_harmonic(path, name, out_dir):
    x, sr = sf.read(path, always_2d=True)
    xm = _to_mono(x)
    if sr != SR:
        xm = signal.resample_poly(xm, SR, sr)
        sr = SR
    xm = xm / (np.abs(xm).max() + 1e-9) * 0.9
    f0t, conf, rdb = yin(xm, sr, hop=512)
    ok = (conf > 0.8) & (f0t > 0)
    if ok.sum() < 6:
        raise RuntimeError('could not find a stable pitch - provide a clean single sustained note')
    f0 = float(np.median(f0t[ok]))
    idx = np.where(ok)[0]
    a, b = idx[0], idx[-1]
    # amplitude envelope (10 ms rms)
    h = int(0.01 * sr)
    env = np.sqrt(np.convolve(xm ** 2, np.ones(h) / h, mode='same'))[::h]
    pk = int(np.argmax(env))
    pkv = env[pk]
    att = np.argmax(env >= 0.9 * pkv) * 0.01
    after = env[pk:]
    tdb = 20 * np.log10(after / (pkv + 1e-9) + 1e-6)
    tt = np.arange(len(after)) * 0.01
    sel = (tdb > -30)
    decay_db_s = float(-np.polyfit(tt[sel], tdb[sel], 1)[0]) if sel.sum() > 5 else 0.0
    sustained = decay_db_s < 8.0
    # spectrum of the stable part (loudest 0.3 s after the attack)
    s0 = int(min(len(xm) - 8192, max(0, (pk * 0.01 + 0.05) * sr)))
    seg = xm[s0:s0 + 8192] * np.hanning(8192)
    spec = np.abs(np.fft.rfft(seg))
    fr = np.fft.rfftfreq(8192, 1 / sr)
    K = int(min(60, 0.45 * sr / f0))
    pk_f, pk_a = [], []
    for k in range(1, K + 1):
        lo, hi = k * f0 * 0.965, k * f0 * 1.035
        m = (fr >= lo) & (fr <= hi)
        if not m.any():
            break
        j = np.argmax(spec * m)
        pk_f.append(fr[j])
        pk_a.append(spec[j])
    pk_f, pk_a = np.array(pk_f), np.array(pk_a)
    ratio2 = (pk_f / (np.arange(1, len(pk_f) + 1) * f0)) ** 2 - 1
    kk = np.arange(1, len(pk_f) + 1)[:12]
    B = float(np.clip(np.sum(ratio2[:12] * kk ** 2) / np.sum(kk ** 4), 0, 0.01)) if len(kk) > 3 else 0.0
    # spectral envelope on a log-frequency grid
    grid = np.geomspace(50, 14000, 56)
    dbk = 20 * np.log10(pk_a / (pk_a.max() + 1e-12) + 1e-6)
    env_db = np.interp(np.log(grid), np.log(pk_f), dbk, left=dbk[0], right=dbk[-1])
    env_db = env_db - 12 * np.log2(np.maximum(grid / pk_f[-1], 1.0))      # fall off 12 dB/oct above the last partial
    # noise floor: energy between harmonics
    mask = np.ones_like(fr, bool)
    for f in pk_f:
        mask &= np.abs(fr - f) > 0.35 * f0
    noise_lin = np.sqrt(np.convolve(spec ** 2 * mask, np.ones(41) / 41, mode='same'))
    noise_db = 20 * np.log10(np.interp(grid, fr, noise_lin) / (pk_a.max() + 1e-12) + 1e-6)
    # vibrato from the f0 track
    f0c = 1200 * np.log2(f0t[a:b + 1] / f0)
    vr, vd = 0.0, 0.0
    if len(f0c) > 30:
        fc = f0c - np.polyval(np.polyfit(np.arange(len(f0c)), f0c, 2), np.arange(len(f0c)))
        F = np.abs(np.fft.rfft(fc * np.hanning(len(fc))))
        fq = np.fft.rfftfreq(len(fc), 512 / sr)
        m = (fq > 3.5) & (fq < 8.5)
        if m.any() and F[m].max() > 3 * np.median(F[1:]):
            vr = float(fq[m][np.argmax(F[m])])
            vd = float(np.std(fc) * 1.414)
    # Extract top 16 harmonic partials via 8192-point FFT (tonal.py method)
    partials = extract_harmonic_partials(xm, sr, f0)
    meta = dict(type='harmonic', name=name, sr=sr, f0=round(f0, 2), midi=round(float(hz2midi(f0)), 2), B=B,
                partials=partials,
                grid=[round(float(g), 1) for g in grid], env_db=[round(float(v), 1) for v in env_db],
                noise_db=[round(float(v), 1) for v in noise_db], attack=round(float(max(att, 0.004)), 3),
                decay_db_s=round(decay_db_s, 1), sustained=bool(sustained), vib_rate=round(vr, 2),
                vib_cents=round(vd, 1), source=os.path.basename(path))
    d = os.path.join(out_dir, name)
    os.makedirs(d, exist_ok=True)
    json.dump(meta, open(os.path.join(d, 'instrument.json'), 'w', encoding='utf-8'), indent=1)
    return d, meta


class HarmonicInstrument:
    def __init__(self, d):
        self.meta = json.load(open(os.path.join(d, 'instrument.json'), encoding='utf-8'))
        self.rng = np.random.default_rng(1)

    def play(self, midi, vel=0.7, dur=1.0, sr=SR, release=0.15):
        m = self.meta
        f0 = float(midi2hz(midi))
        n = int((dur + release) * sr)
        t = np.arange(n) / sr
        K = int(min(70, 0.46 * sr / f0))
        k = np.arange(1, K + 1)
        fk = k * f0 * np.sqrt(1 + m['B'] * k ** 2)
        fk = fk[fk < 0.46 * sr]
        grid = np.array(m['grid'])
        env = np.array(m['env_db'])
        amp = 10 ** (np.interp(np.log(fk), np.log(grid), env) / 20.0)
        amp *= 10 ** (((vel - 0.65) * 10.0 * np.log2(np.maximum(fk / 500.0, 1.0))) / 20.0)   # louder = brighter
        vr, vd = m['vib_rate'], m['vib_cents']
        if vr > 0:
            vib = 1 + (vd / 1200.0) * np.log(2) * np.sin(2 * np.pi * vr * t) * np.clip((t - 0.2) / 0.3, 0, 1)
        else:
            vib = np.ones(n)
        out = np.zeros(n)
        ph0 = self.rng.uniform(0, 6.283, len(fk))
        phase_base = (2.0 * np.pi / sr) * np.cumsum(vib)
        for i, f in enumerate(fk):
            out += amp[i] * np.sin(f * phase_base + ph0[i])
        # envelope
        a = max(m['attack'], 0.004)
        e = np.minimum(1.0, (t / a)) ** 1.3
        if not m['sustained']:
            e *= 10 ** (-(m['decay_db_s'] * t) / 20.0)
        nrel = int(release * sr)
        e[-nrel:] *= np.linspace(1, 0, nrel) ** 2
        out = out / (np.abs(out).max() + 1e-9) * e
        # coloured noise
        nz = self.rng.standard_normal(n)
        N = np.fft.rfft(nz)
        fr = np.fft.rfftfreq(n, 1 / sr)
        nd = np.interp(np.log(np.maximum(fr, 50)), np.log(grid), np.array(m['noise_db']))
        nz = np.fft.irfft(N * 10 ** (nd / 20.0), n)
        nz = nz / (np.abs(nz).max() + 1e-9)
        nz_env = e * (0.5 + 1.5 * np.exp(-t / 0.04))
        sig = out + nz * nz_env * 0.5 * 10 ** (np.mean(m['noise_db']) / 20.0) * 3.0
        return (sig / (np.abs(sig).max() + 1e-9) * (0.25 + 0.65 * vel)).astype(np.float32)


# ------------------------------------------------------------------------------------------------
# api
# ------------------------------------------------------------------------------------------------

def load_instrument(d):
    meta = json.load(open(os.path.join(d, 'instrument.json'), encoding='utf-8'))
    return SamplerInstrument(d) if meta['type'] == 'sampler' else HarmonicInstrument(d)


def render_events(inst, events, sr=SR, tail=3.0):
    """events: humanize.py output (seconds). Returns a stereo float32 stem."""
    end = max((e['t'] + e['dur'] for e in events), default=0) + tail
    buf = np.zeros(int(end * sr) + 1, np.float32)
    for e in events:
        frac_midi = float(e['p']) + float(e.get('c', 0.0)) / 100.0
        y = inst.play(frac_midi, e['v'] / 127.0, e['dur'], sr)
        i = int(e['t'] * sr)
        buf[i:i + len(y)] += y[:len(buf) - i]
    max_amp = float(np.abs(buf).max()) if len(buf) > 0 else 0.0
    if max_amp > 0.98:
        buf *= 0.95 / max_amp
    return np.stack([buf, buf], 1)


def export_sfz(d):
    meta = json.load(open(os.path.join(d, 'instrument.json'), encoding='utf-8'))
    if meta['type'] != 'sampler':
        raise SystemExit('sfz export needs a sampler instrument')
    zs = sorted(meta['zones'], key=lambda z: z['midi'])
    lines = [f'// {meta["name"]} - cloned with clone_instrument.py', '<group> ampeg_release=0.15']
    for i, z in enumerate(zs):
        lo = 0 if i == 0 else int(round((zs[i - 1]['midi'] + z['midi']) / 2)) + 1
        hi = 127 if i == len(zs) - 1 else int(round((z['midi'] + zs[i + 1]['midi']) / 2))
        root = int(round(z['midi']))
        cents = int(round((z['midi'] - root) * -100))
        lines.append(f'<region> sample={z["file"]} lokey={lo} hikey={hi} pitch_keycenter={root} tune={cents}')
    p = os.path.join(d, meta['name'] + '.sfz')
    open(p, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('analyze')
    a.add_argument('wav'); a.add_argument('--name', required=True); a.add_argument('--out', default='clones')
    a.add_argument('--mode', choices=['sampler', 'harmonic'], default='sampler')
    p = sub.add_parser('play')
    p.add_argument('dir'); p.add_argument('--notes', type=int, nargs='+', default=[60, 64, 67, 72])
    p.add_argument('--vel', type=float, default=0.7); p.add_argument('--dur', type=float, default=1.2)
    p.add_argument('--out', default='clone_demo.wav')
    s = sub.add_parser('sfz'); s.add_argument('dir')
    args = ap.parse_args()
    if args.cmd == 'analyze':
        d, meta = (build_sampler if args.mode == 'sampler' else build_harmonic)(args.wav, args.name, args.out)
        if meta['type'] == 'sampler':
            ms = [z['midi'] for z in meta['zones']]
            print(f'sampler: {len(ms)} notes, range {min(ms):.1f}-{max(ms):.1f} MIDI -> {d}')
            gaps = np.diff(sorted(ms))
            if len(ms) and (max(ms) - min(ms) > 0 and gaps.max() > 8):
                print('  note: gaps wider than ~8 semitones will be stretched - record a note in between for better realism')
        else:
            print(f'harmonic: f0 {meta["f0"]} Hz, inharmonicity B={meta["B"]:.5f}, attack {meta["attack"]}s, '
                  f'decay {meta["decay_db_s"]} dB/s, vibrato {meta["vib_rate"]} Hz/{meta["vib_cents"]} cents -> {d}')
    elif args.cmd == 'play':
        inst = load_instrument(args.dir)
        out = []
        for m in args.notes:
            y = inst.play(m, args.vel, args.dur)
            out.append(np.concatenate([y, np.zeros(int(0.15 * SR), np.float32)]))
        sf.write(args.out, np.concatenate(out), SR)
        print('wrote', args.out)
    elif args.cmd == 'sfz':
        print('wrote', export_sfz(args.dir))


if __name__ == '__main__':
    main()
