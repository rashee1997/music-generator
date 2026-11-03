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

"""Stage `drums`: discover the drum pieces from the percussive part, name them, cut each out.

No fixed kit. Every hit's magnitude spectrum is a column of V; a non-negative factorisation V ~ W H finds the pieces
(columns of W = a piece's spectrum, rows of H = how hard each hit played it), so a kick and a hat struck together
are two pieces, not a third sound. The number of pieces grows until the fit is good enough (profile `drums.nmf_error`).
Pieces are named from the music_db (nearest declared piece by spectral centroid), otherwise `perc_n`.
Each piece's stem is spectrum x decaying envelope per hit, shared with overlapping pieces in proportion, on the stereo STFT."""
import os

import numpy as np

from .config import jdump


def onset_times(perc_mono, sr, cfg):
    import librosa
    d = cfg['drums']
    hop = cfg['analysis']['hop']
    env = librosa.onset.onset_strength(y=perc_mono, sr=sr, hop_length=hop)
    fr = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, delta=d['onset_delta'],
                                    wait=max(int(d['min_gap_s'] * sr / hop), 1), backtrack=False)
    return librosa.frames_to_time(fr, sr=sr, hop_length=hop)


def stft_complex(y, cfg):
    import librosa
    s = cfg['separate']
    return np.stack([librosa.stft(c, n_fft=s['n_fft'], hop_length=s['hop']) for c in y])


def hit_matrix(mag, times, sr, cfg):
    """V (bins, hits): mean magnitude over the window that starts at each onset."""
    d, s = cfg['drums'], cfg['separate']
    ft = s['hop'] / sr
    w = max(int(d['hit_window_s'] / ft), 1)
    cols = []
    for t in times:
        a = min(max(int((t - d['pre_s']) / ft), 0), mag.shape[1] - 1)
        cols.append(mag[:, a:a + w].mean(axis=1))
    return np.array(cols).T


def nmf(V, k, iters, seed):
    """Multiplicative-update NMF (Euclidean). Deterministic for a given seed."""
    rng = np.random.default_rng(seed)
    W = rng.random((V.shape[0], k)).astype('float64') + 0.1
    H = rng.random((k, V.shape[1])).astype('float64') + 0.1
    eps = 1e-12
    for _ in range(iters):
        H *= (W.T @ V) / (W.T @ W @ H + eps)
        W *= (V @ H.T) / (W @ H @ H.T + eps)
    scale = W.sum(axis=0) + eps
    return W / scale, H * scale[:, None]


def fit_pieces(V, cfg):
    """Number of pieces from the data: the smallest k that fits to `nmf_error`, or after which one more piece adds
    less than `nmf_elbow` of everything gained so far (noisy hits of one drum then do not split into several pieces)."""
    d = cfg['drums']
    norm = np.linalg.norm(V) + 1e-12
    fits = []
    for k in range(1, min(d['max_pieces'], V.shape[1]) + 1):
        W, H = nmf(V, k, d['nmf_iters'], d['seed'])
        fits.append((W, H, np.linalg.norm(V - W @ H) / norm))
    errs = [f[2] for f in fits]
    for k in range(len(fits)):
        if errs[k] <= d['nmf_error'] or k + 1 == len(fits):
            return fits[k]
        if k >= 1 and (errs[k] - errs[k + 1]) < d['nmf_elbow'] * (errs[0] - errs[k]):
            return fits[k]
    return fits[-1]


def centroid(spec, sr, cfg):
    """Median frequency of a piece's spectrum (half the energy lies below it): steadier than the mean when another piece leaks in."""
    f = np.arange(len(spec)) * sr / cfg['separate']['n_fft']
    c = np.cumsum(spec ** 2)
    return float(f[min(np.searchsorted(c, 0.5 * c[-1]), len(f) - 1)])


def name_pieces(cents, db_pieces, cfg):
    """Component index -> (id, kind, source). Each declared piece is used once, nearest centroid within the tolerance (octaves)."""
    tol = cfg['drums']['name_centroid_octaves']
    pairs = sorted(((abs(np.log2(max(c, 1.0) / p['centroid_hz'])), k, i)
                    for k, c in cents.items() for i, p in enumerate(db_pieces) if p.get('centroid_hz')), key=lambda x: x[0])
    names, used = {}, set()
    for dist, k, i in pairs:
        if k in names or i in used or dist > tol:
            continue
        names[k] = (db_pieces[i]['id'], db_pieces[i].get('kind'), 'music_db')
        used.add(i)
    n = 0
    for k in cents:
        if k not in names:
            n += 1
            names[k] = (f'perc_{n}', None, 'measured')
    return names


def piece_stems(X, sr, W, H, times, members, cfg):
    """Stereo stem per component. Expected magnitude = spectrum x level x decaying envelope, per hit it belongs to."""
    import librosa
    d, s = cfg['drums'], cfg['separate']
    ft = s['hop'] / sr
    n_frames = X.shape[2]
    tau = d['tail_s'] / np.log(1.0 / d['tail_floor'])
    E = {k: np.zeros(X.shape[1:], 'float32') for k in range(W.shape[1])}
    for k in E:
        for i in members[k]:
            a = min(max(int((times[i] - d['pre_s']) / ft), 0), n_frames - 1)
            b = min(a + int(d['tail_s'] * 1.5 / ft) + 1, n_frames)
            env = np.exp(-(np.arange(b - a) * ft) / tau)
            E[k][:, a:b] += (W[:, k, None] * (H[k, i] * env)[None, :]).astype('float32')
    total = sum(E.values())
    length = int((n_frames - 1) * s['hop'])
    out = {}
    for k in E:
        M = np.where(total > 0, E[k] / np.maximum(total, 1e-12), 0.0)
        out[k] = np.stack([librosa.istft(c * M, hop_length=s['hop'], length=length) for c in X]).astype('float32')
    return out


def extract(perc, sr, db_pieces, cfg):
    """{'pieces': {id: {kind, source, hits, centroid_hz, times, levels, stem}}, 'unexplained': (2, n), 'fit_error': float}."""
    d = cfg['drums']
    empty = {'pieces': {}, 'unexplained': perc, 'fit_error': None}
    times = onset_times(perc.mean(axis=0), sr, cfg)
    if len(times) < d['min_hits']:
        return empty
    X = stft_complex(perc, cfg)
    V = hit_matrix(np.abs(X).mean(axis=0), times, sr, cfg)
    W, H, err = fit_pieces(V, cfg)
    members = {k: [i for i in range(len(times)) if H[k, i] >= d['member_frac'] * H[k].max()] for k in range(W.shape[1])}
    keep = [k for k in members if len(members[k]) >= d['min_hits']]
    if not keep:
        return empty
    cents = {k: centroid(W[:, k], sr, cfg) for k in keep}
    names = name_pieces(cents, db_pieces, cfg)
    stems = piece_stems(X, sr, W[:, keep], H[keep], times, {j: members[k] for j, k in enumerate(keep)}, cfg)
    out = {}
    for j, k in enumerate(keep):
        pid, kind, src = names[k]
        mem = members[k]
        stem = np.zeros_like(perc)
        stem[:, :stems[j].shape[1]] = stems[j][:, :perc.shape[1]]
        out[pid] = {'kind': kind, 'source': src, 'hits': len(mem), 'centroid_hz': cents[k],
                    'times': [round(float(times[i]), 4) for i in mem], 'levels': [float(H[k, i]) for i in mem], 'stem': stem}
    return {'pieces': out, 'unexplained': perc - sum(p['stem'] for p in out.values()), 'fit_error': float(err)}


def write_midi(pieces, bpm, path, cfg):
    import pretty_midi
    d = cfg['drums']
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(bpm or 120.0))
    ins = pretty_midi.Instrument(program=0, is_drum=True, name='drums')
    for pid, p in pieces.items():
        pitch = d['midi'].get(p['kind'] or pid, d['midi'].get(pid, d['default_midi']))
        top = max(p['levels']) or 1.0
        for t, lv in zip(p['times'], p['levels']):
            vel = int(np.clip(30 + 97 * (lv / top) ** 0.6, 1, 127))
            ins.notes.append(pretty_midi.Note(velocity=vel, pitch=int(pitch), start=t, end=t + d['midi_note_s']))
    pm.instruments.append(ins)
    pm.write(path)


def run(ctx):
    from . import separate
    cfg, d = ctx['cfg'], ctx['data']
    if 'sep' not in d:
        separate.run(ctx)
    sr = cfg['analysis']['sr']
    res = extract(d['sep']['perc'], sr, ctx['priors']['drum_pieces'], cfg)
    d['drums'] = res
    write_midi(res['pieces'], ctx['priors']['bpm'], os.path.join(ctx['root'], 'out', 'midi', 'drums.mid'), cfg)
    rep = {pid: {k: v for k, v in p.items() if k not in ('stem', 'levels')} for pid, p in res['pieces'].items()}
    jdump({'fit_error': res['fit_error'], 'pieces': rep}, os.path.join(ctx['root'], 'reports', 'drums.json'))
    for pid, p in res['pieces'].items():
        print(f'  {pid:<24} {p["hits"]:>4} hits  centroid {p["centroid_hz"]:>6.0f} Hz  ({p["source"]})')
    print(f'  NMF relative error {res["fit_error"]}')
