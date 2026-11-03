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

"""Stage `separate`: harmonic masks per voice on the stereo STFT, levels solved per frame.

1. Soft harmonic/percussive masks split the mix; voices are cut from the harmonic part, drums later come from the rest.
2. Every (voice, pitch) is an atom: narrow bands at f0*h, h = 1..H, weighted by the voice's harmonic template. Per frame a
   non-negative least-squares fit decides which atoms sound and how loud, so two voices sharing a bin split it by the
   rest of their harmonics. Notes hiding under another voice's harmonic are still tried (their fundamental shows in
   the pitch spectrum).
3. Each voice's share of every bin is its fitted magnitude over the total; the same mask goes to the left and right
   channel, so every stem keeps its stereo image, and the stems never add up to more than the mix.
Everything not claimed stays in `residual` (= mix - voices - percussive), which later stages keep working on."""
import numpy as np
from scipy import ndimage

from .music_db import hz


def stft(y, cfg):
    import librosa
    s = cfg['separate']
    return np.stack([librosa.stft(c, n_fft=s['n_fft'], hop_length=s['hop'], window='hann') for c in y])


def istft(X, cfg, length):
    import librosa
    s = cfg['separate']
    return np.stack([librosa.istft(c, hop_length=s['hop'], window='hann', length=length) for c in X]).astype('float32')


def hp_masks(X, cfg):
    """Soft masks (harmonic, percussive) from the mono magnitude by median filtering in time and frequency."""
    from scipy.ndimage import median_filter
    s = cfg['separate']
    mag = np.abs(X).mean(axis=0)
    H = median_filter(mag, size=(1, s['hp_time_kernel']))
    P = median_filter(mag, size=(s['hp_freq_kernel'], 1))
    m = s['hp_margin']
    hard_h = ((H / (P + 1e-10)) >= m).astype('float32')   # margin > 1 keeps only clearly tonal bins in the harmonic part
    hard_p = ((P / (H + 1e-10)) >= m).astype('float32')
    rest = 1.0 - hard_h - hard_p                          # neither clearly tonal nor clearly percussive: split by energy
    share_h = H ** 2 / (H ** 2 + P ** 2 + 1e-12)
    return (hard_h + rest * share_h).astype('float32'), (hard_p + rest * (1 - share_h)).astype('float32')


def atom_geometry(midi, template, tuning_cents, sr, cfg, n_bins):
    """Bins and weights of one pitch played with a voice's template: triangular peaks at f0*h, h = 1..H."""
    s = cfg['separate']
    binhz = sr / s['n_fft']
    f0 = hz(midi, tuning_cents)
    idx, w = [], []
    for h in range(len(template)):
        f = f0 * (h + 1)
        if f > sr * s['max_freq_frac'] or template[h] <= 0:
            break
        c = f / binhz
        half = max(s['min_halfwidth_bins'], f * s['halfwidth_frac'] / binhz)
        bins = np.arange(max(int(np.floor(c - half)), 0), min(int(np.ceil(c + half)) + 1, n_bins))
        idx.append(bins)
        w.append(template[h] * np.maximum(0.0, 1.0 - np.abs(bins - c) / (half + 1e-9)))
    if not idx:
        return None
    return np.concatenate(idx), np.concatenate(w).astype('float64')


def candidate_pitches(voice, cfg):
    """Pitches a voice may play: its declared range (padded) plus every pitch it was heard on. Undeclared voices: heard pitches only."""
    pad = cfg['notes']['range_pad_semitones']
    heard = {n['midi'] for n in voice['notes']}
    if voice.get('range') and voice['range'][0] is not None:
        return sorted(heard | set(range(voice['range'][0] - pad, voice['range'][1] + pad + 1)))
    return sorted(heard)


def solve_dictionary(voices, spec, mag, tuning_cents, sr, cfg):
    """Per frame, non-negative least squares over (voice, pitch) atoms. Returns ({voice: {midi: amplitude per frame}}, geometry)."""
    from scipy.optimize import nnls
    s = cfg['separate']
    n_bins, n_frames = mag.shape
    frame_t = s['hop'] / sr
    S, lo, shop = spec['S'], spec['midi_lo'], spec['hop_s']
    geo, seeds = {}, {}
    for vid, v in voices.items():
        for m in candidate_pitches(v, cfg):
            g = atom_geometry(m, v['template'], tuning_cents, sr, cfg, n_bins)
            if g is not None and 0 <= m - lo < S.shape[0]:
                geo[(vid, m)] = g
        for n in v['notes']:
            seeds.setdefault((vid, n['midi']), []).append((int(n['start_s'] / frame_t), int(n['end_s'] / frame_t) + 1))
    span_pad = cfg['music_db']['span_pad_s']
    spans = {vid: v.get('spans') for vid, v in voices.items()}
    keys = list(geo)
    rows = np.array([k[1] - lo for k in keys])
    amps = {vid: {} for vid in voices}
    for j in range(n_frames):
        t = j * frame_t
        col = S[:, min(int(t / shop), S.shape[1] - 1)]
        gate = s['candidate_gate'] * col.max()
        on = col[rows] >= gate
        act = [k for q, k in enumerate(keys)
               if (on[q] or any(a <= j < b for a, b in seeds.get(k, ())))
               and (not spans[k[0]] or any(a - span_pad <= t <= b + span_pad for a, b in spans[k[0]]))]
        if not act:
            continue
        if len(act) > s['max_atoms_per_frame']:
            act = sorted(act, key=lambda k: -col[k[1] - lo])[:s['max_atoms_per_frame']]
        bins = np.unique(np.concatenate([geo[k][0] for k in act]))
        A = np.zeros((len(bins), len(act)))
        for c, k in enumerate(act):
            np.add.at(A[:, c], np.searchsorted(bins, geo[k][0]), geo[k][1])
        x, _ = nnls(A, mag[bins, j].astype('float64'))
        top = x.max()
        if top <= 0:
            continue
        for c, k in enumerate(act):
            if x[c] >= s['prune_frac'] * top:
                amps[k[0]].setdefault(k[1], np.zeros(n_frames, 'float32'))[j] = x[c]
    return amps, geo


def field(vid, amps, geo, shape):
    """Dense expected magnitude (bins, frames) of one voice."""
    E = np.zeros(shape, 'float32')
    for m, a in amps[vid].items():
        idx, w = geo[(vid, m)]
        np.add.at(E, idx, (w[:, None] * a[None, :]).astype('float32'))
    return E


def notes_from_amps(vid, amps, frame_t, cfg):
    """Refined notes: runs of frames where a pitch has level, joined across short gaps."""
    s = cfg['separate']
    gap = max(int(round(s['note_gap_s'] / frame_t)), 0)
    out = []
    for m, a in amps[vid].items():
        on = ndimage.binary_closing(a > 0, structure=np.ones(gap + 1)) if gap else a > 0
        lab, cnt = ndimage.label(on)
        for k in range(1, cnt + 1):
            idx = np.where(lab == k)[0]
            if len(idx) * frame_t >= s['note_min_s']:
                seg = a[idx[0]:idx[-1] + 1]
                out.append({'midi': int(m), 'start_s': float(idx[0] * frame_t), 'end_s': float((idx[-1] + 1) * frame_t),
                            'strength': float(seg.max()), 'mean': float(seg[seg > 0].mean())})
    from .notes import suppress_leakage
    return suppress_leakage(sorted(out, key=lambda n: (n['start_s'], n['midi'])), cfg)


def separate(y, sr, voices, spec, tuning_cents, cfg):
    """{'voices': {id: (2, n)}, 'perc', 'harm', 'residual', 'notes': {voice: refined notes}}."""
    s = cfg['separate']
    n = y.shape[1]
    X = stft(y, cfg)
    Mh, Mp = hp_masks(X, cfg)
    Xh = X * Mh
    shape = Xh.shape[1:]
    amps, geo = solve_dictionary(voices, spec, np.abs(Xh).mean(axis=0), tuning_cents, sr, cfg)
    p = s['share_power']
    total = np.zeros(shape, 'float32')
    for i in voices:
        total += field(i, amps, geo, shape) ** p
    out = {}
    for i in voices:
        M = np.where(total > 0, field(i, amps, geo, shape) ** p / np.maximum(total, 1e-12), 0.0)
        if s['smooth_frames'] > 1:
            M = ndimage.uniform_filter(M, size=(1, s['smooth_frames']))
        out[i] = istft(Xh * M[None], cfg, n)
    perc = istft(X * Mp[None], cfg, n)
    harm = istft(Xh, cfg, n)
    residual = y - sum(out.values()) - perc if out else y - perc
    frame_t = s['hop'] / sr
    return {'voices': out, 'perc': perc, 'harm': harm, 'residual': residual.astype('float32'), 'amps': amps, 'frame_t': frame_t,
            'notes': {i: notes_from_amps(i, amps, frame_t, cfg) for i in voices}}


def run(ctx):
    import os
    from . import audio_io, voices as voices_mod
    cfg, d = ctx['cfg'], ctx['data']
    if 'voices' not in d:
        voices_mod.run(ctx)
    sr = cfg['analysis']['sr']
    y = audio_io.load(ctx['song'], sr)
    res = separate(y, sr, d['voices'], d['spec'], d['tuning']['cents'], cfg)
    d['mix'], d['sep'], d['sr'] = y, res, sr
    if cfg['export']['keep_raw']:                      # the mask-cut stems are only a measuring tool; the stems to use come from `resynth`
        for i, a in res['voices'].items():
            audio_io.write(os.path.join(ctx['root'], 'out', 'raw', f'{i}.wav'), a, sr)
        audio_io.write(os.path.join(ctx['root'], 'out', 'raw', 'percussive.wav'), res['perc'], sr)
        audio_io.write(os.path.join(ctx['root'], 'out', 'raw', 'residual.wav'), res['residual'], sr)
