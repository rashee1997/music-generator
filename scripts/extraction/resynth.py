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

"""Stage `resynth`: recreate every stem from its MIDI instead of cutting it out of the mix.

Mask-cutting (stage `separate`) can only return what is already in the mix, so a voice hidden under another one comes out
with holes and bleed. Here the notes are the truth and the sound is rebuilt:

* voices     cleaned MIDI (midi_clean.py) -> a sampler of real notes cut from the song where there are enough clean ones, otherwise
             additive synthesis. Additive: each note takes its loudness per frame from the fitted level
             (so dynamics and decays are the song's own), the voice's measured harmonic template, a little pitch drift and the
             declared vibrato. The level is then fitted against the cut-out stem, a measured noise layer (breath, bow, pick)
             is added where the harmonic model leaves a remainder, and the stereo balance follows the stem over time.
* drums      one-shot per piece = mean of its most isolated hits (aligned), re-triggered at every hit with the measured level.
* ambience   noise with the bed's measured spectrum, width and level over time, plus the real crackle clicks.
* effects    the strongest events, as found.
* unmodelled what the mix has that the parts above do not (spectral difference): the room, reverb tails, and the sung/rapped parts that are out of scope.
The mask-cut stems stay in memory only as the yardstick for the gate (out/raw/ if `export.keep_raw`)."""
import os
import warnings

import numpy as np
from scipy import ndimage, signal

from . import midi_clean
from .config import jdump
from .music_db import hz


def smooth_noise(n, sr, cutoff_hz, rng):
    """Unit-variance noise low-passed at cutoff_hz (slow pitch drift)."""
    a = 1.0 - np.exp(-2 * np.pi * cutoff_hz / sr)
    x = signal.lfilter([a], [1, -(1 - a)], rng.standard_normal(n))
    return x / (x.std() + 1e-12)


def note_envelope(vals, first_frame, ft, attack_s, release_s, sr, n):
    """(first sample, per-sample level) of one note from its per-frame fitted level, or None. Gaps inside the note are filled."""
    nz = np.nonzero(vals > 0)[0]
    if len(nz) == 0:
        return None
    vals = np.interp(np.arange(len(vals)), nz, vals[nz])
    tf = (first_frame + np.arange(len(vals))) * ft
    T = np.concatenate([[tf[0] - attack_s], tf, [tf[-1] + release_s]])
    V = np.concatenate([[0.0], vals, [0.0]])
    s0, s1 = max(int(T[0] * sr), 0), min(int(T[-1] * sr) + 1, n)
    if s1 <= s0:
        return None
    return s0, np.interp(np.arange(s0, s1) / sr, T, V)


def synth_note(f0, s0, env, template, t_start, sr, vib, rs, rng):
    """One note: harmonics of f0 weighted by the voice's template, louder = brighter, with drift and vibrato."""
    t = (np.arange(len(env)) + s0) / sr
    dev = rs['drift_cents'] * smooth_noise(len(env), sr, rs['drift_hz'], rng)
    if vib and vib.get('rate_hz') and vib.get('depth_cents'):
        delay = (vib.get('onset_delay_ms') or 1000 * rs['vibrato_delay_s']) / 1000.0
        tv = t - t_start - delay
        dev = dev + np.where(tv > 0, np.clip(tv / 0.3, 0, 1) * vib['depth_cents'] * rs['vibrato_scale'] * np.sin(2 * np.pi * vib['rate_hz'] * tv), 0.0)
    phase = 2 * np.pi * np.cumsum(f0 * 2.0 ** (dev / 1200.0)) / sr
    rel = env / (env.max() + 1e-12)
    ph = rng.uniform(0, 2 * np.pi, len(template))
    sig = np.zeros(len(env))
    for h in range(len(template)):
        if f0 * (h + 1) > sr * 0.45 or template[h] <= 0:
            break
        sig += template[h] * rel ** (rs['level_tilt'] * h) * np.sin((h + 1) * phase + ph[h])
    return sig * env


def render_harmonic(notes, amps_v, ft, template, prior, n, sr, tuning_cents, cfg, seed):
    """Mono additive rendering of a voice's cleaned notes (loudness in the units of the separation's STFT)."""
    rs = cfg['resynth']
    nfft = cfg['separate']['n_fft']
    env_p = prior.get('envelope') or {}
    att = env_p.get('attack_ms')
    attack_s = float(np.clip((np.mean([att['min'], att['max']]) if isinstance(att, dict) and att.get('max') else rs['attack_ms_default']) / 1000, 0.003, 0.08))
    release_s = float(np.clip((env_p.get('release_ms') or rs['release_ms_default']) / 1000, 0.02, 0.5))
    vib = ((prior.get('pitch_behavior') or {}).get('vibrato') or {})
    vib = vib if vib.get('present') else None
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for note in notes:
        arr = amps_v.get(note['midi'])
        if arr is None:
            continue
        a = int(note['start_s'] // ft)
        b = max(int(np.ceil(note['end_s'] / ft)) - 1, a)
        res = note_envelope(arr[a:b + 1].astype('float64'), a, ft, attack_s, release_s, sr, n)
        if res is None:
            continue
        s0, env = res
        sig = synth_note(hz(note['midi'], tuning_cents), s0, env * 4.0 / nfft, template, note['start_s'], sr, vib, rs, rng)
        out[s0:s0 + len(sig)] += sig
    return out


def fit_gain(syn, stem, cfg):
    """Least-squares gain of a synthesised mono voice against the cut-out stem (mean channel magnitude), and the two magnitudes."""
    from .separate import stft
    A = np.abs(stft(syn[None].astype('float32'), cfg)[0])
    B = np.abs(stft(stem, cfg)).mean(axis=0)
    m = A > 0.01 * (A.max() + 1e-12)
    g = float((A[m] * B[m]).sum() / ((A[m] ** 2).sum() + 1e-12)) if m.any() else 1.0
    return float(np.clip(g, 0.1, 10.0)), A, B


def noise_layer(A, B, gain, n, cfg, seed, band):
    """Remainder the harmonic model cannot make (breath, bow, pluck): the stem's magnitude minus the model, random phase."""
    from .separate import istft, stft
    rs = cfg['resynth']
    Nm = np.maximum(B - gain * A, 0.0)
    fr = np.arange(Nm.shape[0]) * band[2] / cfg['separate']['n_fft']
    Nm = Nm * ((fr >= band[0]) & (fr <= band[1]))[:, None]          # only around the notes the voice plays: bleed from far-away instruments is not breath
    live = ndimage.binary_dilation((gain * A).sum(axis=0) > 0.02 * (gain * A).sum(axis=0).max(), iterations=1)
    Nm = ndimage.uniform_filter(Nm * live[None], size=(1, rs['noise_smooth_frames']))
    ratio = float((Nm ** 2).sum() / ((B ** 2).sum() + 1e-12))
    if ratio < rs['noise_min_ratio']:
        return None, ratio
    if ratio > rs['noise_max_ratio']:
        Nm = Nm * np.sqrt(rs['noise_max_ratio'] / ratio)
    rng = np.random.default_rng(seed)
    Z = Nm * np.exp(2j * np.pi * rng.random(Nm.shape))
    x = istft(Z[None], cfg, n)[0].astype('float64')
    got = np.abs(stft(x[None].astype('float32'), cfg)[0])
    return x * float(np.sqrt((Nm ** 2).sum() / ((got ** 2).sum() + 1e-12))), ratio


def pan_gains(stem, sr, win_s, n):
    """Left and right gain per sample that keep the stem's own balance over time (mean of the two = 1)."""
    w = max(int(win_s * sr), 1)
    centres, gl, gr = [], [], []
    for i in range(max(stem.shape[1] // w, 1)):
        seg = stem[:, i * w:(i + 1) * w]
        rl, rr = float(np.sqrt(np.mean(seg[0] ** 2))), float(np.sqrt(np.mean(seg[1] ** 2)))
        if (rl + rr) / 2 < 1e-5:
            continue
        gl.append(2 * rl / (rl + rr))
        gr.append(2 * rr / (rl + rr))
        centres.append((i + 0.5) * w)
    if not centres:
        return np.ones(n), np.ones(n)
    x = np.arange(n)
    return np.interp(x, centres, gl), np.interp(x, centres, gr)


def noise_band(notes, template, sr, tuning_cents, cfg):
    """(low Hz, high Hz, sr): from just under the lowest note to just above the top harmonic of the highest."""
    lo = min(n['midi'] for n in notes)
    hi = max(n['midi'] for n in notes)
    return 0.8 * hz(lo, tuning_cents), min(1.2 * hz(hi, tuning_cents) * len(template), 0.45 * sr), sr


def velocity_map(notes):
    """Note strength -> sampler velocity 0.35..0.95 on a log scale (5th..95th percentile of this voice's notes)."""
    ls = np.log(np.maximum([n['strength'] for n in notes], 1e-9))
    lo, hi = (np.percentile(ls, 5), np.percentile(ls, 95)) if len(ls) > 1 else (0.0, 1.0)
    return lambda st: float(np.interp(np.log(max(st, 1e-9)), [lo, hi + 1e-9], [0.35, 0.95]))


def split_notes(notes, zones, tuning_cents, max_semitones):
    """(notes the sampler can play from a sample within `max_semitones`, the rest)."""
    if not zones:
        return [], list(notes)
    z = np.asarray(zones, float)
    cov = [n for n in notes if np.min(np.abs(z - (n['midi'] + tuning_cents / 100.0))) <= max_semitones]
    ids = {id(n) for n in cov}
    return cov, [n for n in notes if id(n) not in ids]


def render_sampled(inst, notes, tuning_cents, n, sr, release_s):
    """Mono audio of the notes played through a real-note sampler (clone_instrument). The sampler runs at its own rate."""
    import clone_instrument as ci
    vel = velocity_map(notes)
    buf = np.zeros(int(n * ci.SR / sr) + ci.SR)
    for note in notes:
        y = inst.play(note['midi'] + tuning_cents / 100.0, vel(note['strength']), note['end_s'] - note['start_s'], ci.SR, release_s)
        a = int(note['start_s'] * ci.SR)
        buf[a:a + len(y)] += y[:len(buf) - a]
    if sr != ci.SR:
        buf = signal.resample_poly(buf, sr, ci.SR)
    out = np.zeros(n)
    out[:min(n, len(buf))] = buf[:n]
    return out


def follow_dynamics(samp, target, cfg):
    """Scale the sampled audio frame by frame so its level follows the fitted level of the song (`target`), keeping the sample's own tone."""
    from .separate import stft
    rs, hop = cfg['resynth'], cfg['separate']['hop']
    ea = np.sqrt((np.abs(stft(samp[None].astype('float32'), cfg)[0]) ** 2).sum(axis=0))
    et = np.sqrt((np.abs(stft(target[None].astype('float32'), cfg)[0]) ** 2).sum(axis=0))
    g = np.where(ea > 1e-6 * (ea.max() + 1e-12), et / (ea + 1e-12), 1.0)
    g = ndimage.uniform_filter1d(np.clip(g, rs['follow_floor'], rs['follow_ceiling']), 3)
    return samp * np.interp(np.arange(len(samp)), np.arange(len(g)) * hop, g)


def render_voice(vid, notes, voice, prior, amps_v, ft, stem, n, sr, tuning_cents, cfg, seed, sampler=None):
    """Stereo stem of one voice and what was measured on the way.
    With a sampler (real notes cut from the song) the sampler plays every note it has a sample near and the song's own loudness
    is followed; notes it cannot reach, and voices without a sampler, are built additively."""
    rs = cfg['resynth']
    template = np.asarray(voice['template'], float)
    zones = [z['midi'] for z in sampler.zones] if sampler is not None else []
    cov, unc = split_notes(notes, zones, tuning_cents, rs['sampler_max_semitones'])
    mk = lambda ns, sd: render_harmonic(ns, amps_v, ft, template, prior, n, sr, tuning_cents, cfg, sd) if ns else np.zeros(n)
    syn_c, syn_u = mk(cov, seed), mk(unc, seed + 17)
    syn = syn_c + syn_u
    info = {'notes': len(notes), 'gain': 1.0, 'noise_ratio': 0.0, 'mode': 'additive', 'samples': len(zones), 'sampled_notes_pct': 0.0}
    if rs['gain_fit'] and np.abs(syn).max() > 0:
        g, A, B = fit_gain(syn, stem, cfg)
        info['gain'] = round(g, 3)
    else:
        g, A, B = 1.0, None, None
    env_p = prior.get('envelope') or {}
    release_s = float(np.clip((env_p.get('release_ms') or rs['release_ms_default']) / 1000, 0.05, 0.5))
    if cov and (len(cov) >= len(notes) * rs['sampler_min_covered']):
        mono = follow_dynamics(render_sampled(sampler, cov, tuning_cents, n, sr, release_s), syn_c * g, cfg) + syn_u * g
        info['mode'] = 'sampler' if not unc else 'sampler+additive'
        info['sampled_notes_pct'] = round(100.0 * len(cov) / len(notes), 1)
    else:
        mono = syn * g
        if rs['noise'] and A is not None:
            nz, ratio = noise_layer(A * g, B, 1.0, n, cfg, seed + 1, noise_band(notes, template, sr, tuning_cents, cfg))
            info['noise_ratio'] = round(ratio, 3)
            if nz is not None:
                mono = mono + nz
    gl, gr = pan_gains(stem, sr, cfg['spatial']['window_s'], n)
    return np.stack([mono * gl, mono * gr]).astype('float32'), info


def oneshot(piece, all_times, sr, cfg):
    """(2, L) one-shot: mean of the piece's most isolated hits, aligned on their first few ms. None if it has no hits.
    A mean keeps the spectral colour of hits that are not identical (live or noisy sounds); a sampled drum comes out clean either way."""
    rs, dr = cfg['resynth'], cfg['drums']
    times = np.asarray(piece['times'], float)
    if len(times) == 0:
        return None
    pre, L = int(dr['pre_s'] * sr), int(rs['drum_oneshot_s'] * sr)
    iso = np.array([np.min(np.abs(all_times[np.abs(all_times - t) > 1e-4]), initial=1e9) for t in times])
    order = [i for i in np.argsort(-np.minimum(iso, 2.0))][:max(rs['drum_oneshots'], 1)]
    segs, ref = [], None
    for i in order:
        a = int(times[i] * sr) - pre
        b = a + min(L, int(min(iso[i], 1.0) * sr) + pre)
        if a < 0 or b <= a:
            continue
        seg = piece['stem'][:, a:b]
        k = int(rs['drum_align_ms'] * sr / 1000)
        if ref is None:
            ref = seg.mean(axis=0)[:3 * k]
        else:
            c = signal.correlate(seg.mean(axis=0)[:3 * k], ref, mode='full')
            lag = int(np.argmax(c)) - (len(ref) - 1)
            seg = seg[:, lag:] if lag >= 0 else np.pad(seg, ((0, 0), (-lag, 0)))
        full = np.full((2, L), np.nan)
        full[:, :min(seg.shape[1], L)] = seg[:, :L]
        segs.append(full)
    if not segs:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        one = np.nan_to_num(np.nanmean(np.stack(segs), axis=0))
    fo = int(0.02 * sr)
    one[:, -fo:] *= np.linspace(1, 0, fo)[None]
    return one.astype('float32')


def render_drums(pieces, sr, n, cfg):
    """({piece: stereo stem}, notes) rebuilt from one-shots at the measured hit times and levels."""
    rs, dr = cfg['resynth'], cfg['drums']
    all_times = np.sort(np.array([t for p in pieces.values() for t in p['times']] or [0.0]))
    pre, win = int(dr['pre_s'] * sr), max(int(rs['gain_window_s'] * sr), 1)
    out, shots = {}, {}
    for pid, p in pieces.items():
        os_ = oneshot(p, all_times, sr, cfg)
        if os_ is None:
            continue
        shots[pid] = os_
        ref = float(np.sqrt(np.mean(os_[:, :win] ** 2))) + 1e-9
        y = np.zeros((2, n), 'float32')
        for t in p['times']:
            a = int(t * sr) - pre
            if a < 0 or a >= n:
                continue
            tgt = float(np.sqrt(np.mean(p['stem'][:, a:a + win] ** 2)))
            seg = os_[:, :n - a] * float(np.clip(tgt / ref, 0.0, 8.0))
            y[:, a:a + seg.shape[1]] += seg
        out[pid] = y
    return out, shots


def render_ambient(eff, sr, n, cfg):
    """Noise with the bed's measured spectrum, width and level over time, plus the real crackle clicks."""
    rs = cfg['resynth']
    bed = eff['bed']
    nf = 4096
    _, P = signal.welch(bed.mean(axis=0), sr, nperseg=nf)
    mag = ndimage.uniform_filter1d(np.sqrt(P), 5)
    h = np.fft.fftshift(np.fft.irfft(mag, nf)) * np.hanning(nf)
    rng = np.random.default_rng(rs['seed'] + 7)
    c = float(np.clip(eff['bed_info'].get('width_corr_lr', 1.0), 0.0, 1.0))
    w1, w2 = rng.standard_normal(n), rng.standard_normal(n)
    y = np.stack([signal.oaconvolve(w1, h, mode='same'), signal.oaconvolve(c * w1 + np.sqrt(1 - c * c) * w2, h, mode='same')])
    sec = sr
    k = max(n // sec, 1)
    want = np.array([np.sqrt(np.mean(bed.mean(axis=0)[i * sec:(i + 1) * sec] ** 2)) for i in range(k)])
    got = np.array([np.sqrt(np.mean(y.mean(axis=0)[i * sec:(i + 1) * sec] ** 2)) for i in range(k)]) + 1e-12
    gain = np.interp(np.arange(n), (np.arange(k) + 0.5) * sec, want / got)
    return ((y * gain[None]) + eff['clicks']).astype('float32')


def place_events(events, sr, n, cfg):
    out = np.zeros((2, n), 'float32')
    f = max(int(cfg['resynth']['event_fade_ms'] * sr / 1000), 1)
    for ev in events:
        a = int(round(ev['audio_start_s'] * sr))
        seg = ev['audio'][:, :max(n - a, 0)].copy()
        if seg.shape[1] > 2 * f:
            seg[:, :f] *= np.linspace(0, 1, f)[None]
            seg[:, -f:] *= np.linspace(1, 0, f)[None]
        out[:, a:a + seg.shape[1]] += seg
    return out


def mag_error(M, S, free):
    """Spectral error (percent) of S against M over the frames flagged `free`."""
    return float(100 * np.sum((M[:, free] - S[:, free]) ** 2) / (np.sum(M[:, free] ** 2) + 1e-12))


def room_spec(d, ctx):
    """(rt60 s, predelay ms, hf-decay factor, early-reflection level) for mixer.make_ir: measured room decay if plausible, else the database's, else the default."""
    rs = ctx['cfg']['resynth']
    space = (ctx['priors'].get('spatial') or {}).get('space') or {}
    t60 = (d['spatial']['space'] or {}).get('rt60_s') or (space.get('rt60_s') or {}).get('overall') or rs['reverb_default_rt60']
    pre = space.get('predelay_ms') or rs['reverb_predelay_ms']
    return float(np.clip(t60, 0.2, rs['reverb_max_rt60'])), float(pre), rs['reverb_hf'], rs['reverb_early']


def fit_room(dry, mix, sr, spec, ignored, cfg):
    """Return (wet stereo at the fitted level, info). The room is the song's own decay time; its level is the one that brings
    the rebuilt mix's spectrum closest to the original over the frames that are not sung or rapped."""
    import mixer
    from .gate import free_mask, stft_mag
    rs = cfg['resynth']
    wet = mixer.reverb_bus(dry.T.astype('float64'), spec, sr, seed=rs['reverb_seed']).T[:, :dry.shape[1]].astype('float32')
    M = stft_mag(mix.mean(axis=0))
    free = free_mask(np.arange(M.shape[1]) * 1024 / sr, ignored)
    if free.sum() < 20:
        free = np.ones(M.shape[1], bool)
    best, dry_err = None, None
    for g_db in rs['reverb_grid_db']:
        g = 10 ** (g_db / 20.0) if g_db > -90 else 0.0
        err = mag_error(M, stft_mag((dry + g * wet).mean(axis=0)), free)
        if dry_err is None:
            dry_err = err
        if best is None or err < best[0] * 0.99:                          # a louder room must buy a real (1 %) improvement
            best = (err, g_db, g)
    return (best[2] * wet).astype('float32'), {'rt60_s': round(spec[0], 2), 'predelay_ms': spec[1], 'gain_db': best[1], 'error_pct': round(best[0], 2),
                                                 'error_without_room_pct': round(dry_err, 2), 'at_grid_limit': best[1] == rs['reverb_grid_db'][-1]}


def build_samplers(ctx, midi):
    """{voice: (SamplerInstrument, meta)} for voices with enough clean real notes. Samples are cut from the song at the cleaned notes."""
    import clone_instrument as ci
    from . import export
    cfg, d = ctx['cfg'], ctx['data']
    rs = cfg['resynth']
    out = {}
    if rs['render'] == 'additive':
        return out
    raw = d['sep']['voices']
    drum_stems = [p['stem'] for p in d['drums']['pieces'].values()]
    clones = os.path.join(ctx['root'], 'presets', 'clones')
    for vid, notes in midi.items():
        others = [a for k, a in raw.items() if k != vid] + drum_stems
        meta = export.build_sampler(vid, raw[vid], notes, others, d['tuning']['cents'], d['sr'], clones, cfg, min_clean=rs['sampler_min_purity'], quality='purity')
        if meta and len(meta['zones']) >= rs['sampler_min_samples']:
            out[vid] = (ci.SamplerInstrument(os.path.join(clones, vid)), meta)
    return out


def spectral_leftover(mix, synth, cfg):
    """What is in the mix but not in the rebuilt parts: magnitude difference (floored at 0) with the mix's own phase.
    The rebuilt parts do not share the mix's phase, so subtracting waveforms would only add the two together."""
    from .separate import istft, stft
    M, S = stft(mix, cfg), stft(synth, cfg)
    return istft(np.maximum(np.abs(M) - np.abs(S), 0.0) * np.exp(1j * np.angle(M)), cfg, mix.shape[1])


def run(ctx):
    from . import audio_io, spatial, voices as voices_mod
    cfg, d, root = ctx['cfg'], ctx['data'], ctx['root']
    rs = cfg['resynth']
    if 'spatial' not in d:
        spatial.run(ctx)
    sr, n = d['sr'], d['mix'].shape[1]
    sep = d['sep']
    ft = sep['frame_t']
    prior = {v['id']: v for v in ctx['priors']['voices']}
    midi, stats, dropped = {}, {}, {}
    for vid, v in d['voices'].items():
        poly = (prior.get(vid) or {}).get('polyphony')
        midi[vid], stats[vid] = midi_clean.clean_voice(sep['notes'][vid], poly, v.get('range'), cfg)
    energy = {vid: float(np.sum(sep['voices'][vid] ** 2)) for vid in midi}
    total = sum(energy.values()) + 1e-12
    for vid in list(midi):
        declared = d['voices'][vid]['declared']
        pct = 100 * energy[vid] / total
        if len(midi[vid]) < (1 if declared else rs['min_notes']) or pct < rs['min_voice_pct'] * (0.2 if declared else 1.0):
            dropped[vid] = {'notes': len(midi[vid]), 'energy_pct': round(pct, 2), 'declared': declared}
            del midi[vid]
    samplers = build_samplers(ctx, midi)
    voices_out, info = {}, {}
    for k, vid in enumerate(midi):
        voices_out[vid], info[vid] = render_voice(vid, midi[vid], d['voices'][vid], prior.get(vid) or {}, sep['amps'].get(vid, {}), ft,
                                                  sep['voices'][vid], n, sr, d['tuning']['cents'], cfg, rs['seed'] + 101 * k, samplers.get(vid, (None, None))[0])
        info[vid]['energy_pct'] = round(100 * energy[vid] / total, 2)
        print(f'  {vid:<26} {info[vid]["notes"]:>5} notes  {info[vid]["mode"]:<17} gain {info[vid]["gain"]:.2f}  noise {100 * info[vid]["noise_ratio"]:.0f}%  {info[vid]["samples"]} samples')
    drum_out, shots = render_drums(d['drums']['pieces'], sr, n, cfg)
    drums_mix = sum(drum_out.values()) if drum_out else np.zeros((2, n), 'float32')
    ambient = render_ambient(d['effects'], sr, n, cfg)
    effects = place_events(d['effects']['events'], sr, n, cfg)
    room, room_info = np.zeros((2, n), 'float32'), None
    if rs['reverb']:
        dry = sum(voices_out.values()) + drums_mix if voices_out else drums_mix
        room, room_info = fit_room(dry, d['mix'], sr, room_spec(d, ctx), ctx['priors'].get('ignored') or [], cfg)
        print(f'  room: RT60 {room_info["rt60_s"]} s, level {room_info["gain_db"]} dB, spectral error {room_info["error_without_room_pct"]}% -> {room_info["error_pct"]}%')
    parts = [*voices_out.values(), drums_mix, ambient, effects, room]
    mix = sum(parts)
    peak = max(float(np.max(np.abs(x))) for x in [*parts, mix])
    scale = 0.999 / peak if peak > 0.999 else 1.0
    if scale < 1.0:
        voices_out = {k: v * scale for k, v in voices_out.items()}
        drum_out = {k: v * scale for k, v in drum_out.items()}
        drums_mix, ambient, effects, room, mix = drums_mix * scale, ambient * scale, effects * scale, room * scale, mix * scale
    unmodelled = spectral_leftover(d['mix'] * scale, mix, cfg)
    stems = os.path.join(root, 'out', 'stems')
    for vid, a in voices_out.items():
        audio_io.write(os.path.join(stems, f'{vid}.wav'), a, sr)
    for name, a in (('drums', drums_mix), ('ambient', ambient), ('effects', effects), ('room', room), ('unmodelled', unmodelled)):
        audio_io.write(os.path.join(stems, f'{name}.wav'), a, sr)
    audio_io.write(os.path.join(root, 'out', 'mix_resynth.wav'), mix, sr)
    voices_mod.write_midi({vid: {'notes': midi[vid]} for vid in midi}, os.path.join(root, 'out', 'midi', 'song.mid'), ctx['priors']['bpm'], cfg)
    d['resynth'] = {'voices': voices_out, 'drums': drum_out, 'drums_mix': drums_mix, 'ambient': ambient, 'effects': effects, 'room': room, 'room_info': room_info, 'unmodelled': unmodelled,
                    'samplers': {k: v[1] for k, v in samplers.items()},
                    'mix': mix, 'scale': scale, 'midi': midi, 'midi_stats': stats, 'dropped': dropped, 'voice_info': info,
                    'oneshots': shots}
    jdump({'voices': info, 'midi_stats': stats, 'dropped_voices': dropped, 'level_scale': round(scale, 4), 'room': room_info,
           'drum_pieces': {k: {'hits': len(d['drums']['pieces'][k]['times'])} for k in drum_out}},
          os.path.join(root, 'reports', 'resynth.json'))
    if dropped:
        print('  dropped (too little music to be an instrument): ' + ', '.join(f'{k} ({v["notes"]} notes, {v["energy_pct"]}%)' for k, v in dropped.items()))
    print(f'  {len(voices_out)} voice stems, drums, ambient, effects, room, unmodelled, mix_resynth.wav')
