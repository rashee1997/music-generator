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

"""Stage `effects`: what is left after voices and drums -> ambient bed, crackle clicks, and effect events.

* Ambient bed: the steady part of the residual. Each frequency's quiet-percentile level over the whole song is the floor;
  the bed is whatever sits at or below that floor in every frame. Measured: level, spectrum, width, drift over time.
* Clicks (vinyl crackle, ticks): samples far above the local level in the high band, lifted out as their own layer.
* Events (scratches, risers, tape stops, CD scans, stutters ...): stretches where the bed-free residual rises well above
  its surroundings. Found from the audio, so effects nobody listed turn up too; the music_db windows only tag them.
  Each event is described by measured features and named by the rules in knowledgebase/effect_signatures.json."""
import os

import numpy as np
from scipy import ndimage, signal

from . import knowledge
from .config import jdump


def stft(y, cfg):
    import librosa
    e = cfg['effects']
    return np.stack([librosa.stft(c, n_fft=e['n_fft'], hop_length=e['hop']) for c in y])


def istft(X, cfg, length):
    import librosa
    return np.stack([librosa.istft(c, hop_length=cfg['effects']['hop'], length=length) for c in X]).astype('float32')


def noise_floor(mag, cfg):
    """Per-bin RMS of the steady noise, from its quiet percentile over time (Rayleigh-corrected), smoothed across frequency."""
    e = cfg['effects']
    q = e['floor_percentile'] / 100.0
    fl = np.percentile(mag, e['floor_percentile'], axis=1) / np.sqrt(-np.log(1.0 - q))      # Rayleigh quantile -> RMS of steady noise
    return ndimage.uniform_filter1d(fl, size=e['floor_smooth_bins'])


def bed_mask(mag, floor, cfg):
    """1 where a bin is at the floor, shrinking where the bin rises above it (that excess is not ambience)."""
    return np.minimum(1.0, cfg['effects']['floor_gain'] * floor[:, None] / (mag + 1e-12)).astype('float32')


def detect_clicks(y_mono, sr, cfg):
    """(bool mask per sample, clicks per second): samples of the high band far above its local RMS."""
    e = cfg['effects']
    b, a = signal.butter(2, e['click_hp_hz'] / (sr / 2), 'high')
    hp = signal.lfilter(b, a, y_mono)
    win = max(int(e['click_window_ms'] * sr / 1000), 3)
    local = np.sqrt(ndimage.uniform_filter1d(hp ** 2, size=win) + 1e-12)
    hit = np.abs(hp) > e['click_k'] * local
    hit &= np.abs(hp) > e['click_min_abs']
    lab, n = ndimage.label(ndimage.binary_dilation(hit, iterations=max(int(e['click_dilate_ms'] * sr / 1000), 1)))
    return lab > 0, n / (len(y_mono) / sr)


def frame_db(mag):
    return 20 * np.log10(np.sqrt((mag ** 2).mean(axis=0)) + 1e-9)


def find_events(mag, sr, cfg):
    """[(start_frame, end_frame)] where the bed-free residual stands out from its running median."""
    e = cfg['effects']
    ft = e['hop'] / sr
    db = frame_db(mag)
    edge = max(int(e['edge_frames']), 0)
    if edge and len(db) > 2 * edge:
        db[:edge], db[-edge:] = db[edge], db[-edge - 1]                  # the first and last frames of an STFT are not representative
    local = ndimage.percentile_filter(db, e['background_percentile'], size=max(int(e['background_s'] / ft), 3) | 1, mode='nearest')
    bg = np.minimum(local, np.percentile(db, 50))                       # a long event must not become its own background
    on = db > bg + e['detect_db']
    on &= db > e['abs_floor_db']
    on = ndimage.binary_closing(on, structure=np.ones(max(int(e['merge_gap_s'] / ft), 1) + 1))
    lab, n = ndimage.label(on)
    out = []
    for k in range(1, n + 1):
        idx = np.where(lab == k)[0]
        if (idx[-1] - idx[0] + 1) * ft >= e['min_event_s']:
            out.append((int(idx[0]), int(idx[-1] + 1)))
    return out


def event_features(mag, a, b, sr, cfg):
    """Measured description of frames a..b of a magnitude spectrogram."""
    e = cfg['effects']
    ft = e['hop'] / sr
    f = np.arange(mag.shape[0]) * sr / e['n_fft']
    M = mag[:, a:b]
    energy = (M ** 2).sum(axis=0) + 1e-12
    cen = (f[:, None] * M ** 2).sum(axis=0) / energy
    live = energy > energy.max() * 10 ** (-e['live_db'] / 10)
    t = np.arange(b - a) * ft
    slope = float(np.polyfit(t[live], np.log2(np.maximum(cen[live], 20.0)), 1)[0]) if live.sum() >= 3 else 0.0
    env = np.sqrt(energy)
    ev = env - env.mean()
    rate, depth = 0.0, 0.0
    if len(ev) >= 8:
        sp = np.abs(np.fft.rfft(ev * np.hanning(len(ev))))
        fr = np.fft.rfftfreq(len(ev), ft)
        band = (fr >= e['mod_min_hz']) & (fr <= min(e['mod_max_hz'], 0.5 / ft))
        if band.any():
            k = np.argmax(sp * band)
            rate = float(fr[k])
            depth = float(min(1.0, env.std() / (env.mean() + 1e-12)))
    flat = float(np.mean(np.exp(np.mean(np.log(M + 1e-9), axis=0)) / (M.mean(axis=0) + 1e-9)))
    return {'dur_s': float((b - a) * ft), 'centroid_hz': float(cen[live].mean()), 'centroid_slope_oct_s': slope,
            'mod_rate_hz': rate, 'mod_depth': depth, 'flatness': flat, 'attack_s': float(np.argmax(env) * ft),
            'level_db': float(20 * np.log10(np.sqrt(energy.max()) + 1e-9))}


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def analyse(resid, sr, db_events, cfg):
    """{'bed': (2, n), 'clicks': (2, n), 'bed_info', 'clicks_per_s', 'events': [...], 'bed_free': ...}."""
    e = cfg['effects']
    n = resid.shape[1]
    clickmask, cps = detect_clicks(resid.mean(axis=0), sr, cfg)
    clicks = (resid * clickmask[None]).astype('float32')
    resid = resid - clicks                                              # ticks are their own layer, not bed or events
    X = stft(resid, cfg)
    mag = np.abs(X).mean(axis=0)
    floor = noise_floor(mag, cfg)
    Mb = bed_mask(mag, floor, cfg)
    bed = istft(X * Mb[None], cfg, n)
    free = X * (1 - Mb)[None]
    ft = e['hop'] / sr
    mag_free = np.abs(free).mean(axis=0)
    events = []
    for a, b in find_events(mag_free, sr, cfg):
        feats = event_features(mag_free, a, b, sr, cfg)
        feats['kind'] = knowledge.classify(feats, knowledge.effect_rules()['rules'])
        pad = int(e['pad_s'] / ft)
        lo, hi = max(a - pad, 0), min(b + pad, X.shape[2])
        seg = istft(free[:, :, lo:hi], cfg, (hi - lo) * e['hop'])
        events.append({'start_s': float(a * ft), 'end_s': float(b * ft), 'features': feats, 'audio': seg, 'audio_start_s': float(lo * ft)})
    for ev in events:                                                   # tag with the listening model's window
        best = max(db_events, key=lambda w: overlap(ev['start_s'], ev['end_s'], w['start_s'], w['end_s']), default=None)
        if best and overlap(ev['start_s'], ev['end_s'], best['start_s'], best['end_s']) > 0.5 * (ev['end_s'] - ev['start_s']):
            ev['db_id'], ev['db_type'] = best['id'], best.get('type')
        else:
            ev['db_id'], ev['db_type'] = None, None
    events.sort(key=lambda ev: -(ev['features']['level_db'] + 10 * np.log10(ev['features']['dur_s'])))   # loud and long first
    events = sorted(events[:e['max_events']], key=lambda ev: ev['start_s'])
    bed_mono = bed.mean(axis=0)
    fb = np.arange(mag.shape[0]) * sr / e['n_fft']
    bmag = np.abs(X * Mb[None]).mean(axis=0).mean(axis=1)
    info = {'level_dbfs': float(20 * np.log10(np.sqrt(np.mean(bed_mono ** 2)) + 1e-9)),
            'centroid_hz': float((fb * bmag).sum() / (bmag.sum() + 1e-12)),
            'flatness': float(np.exp(np.mean(np.log(bmag + 1e-12))) / (bmag.mean() + 1e-12)),
            'width_corr_lr': float(np.corrcoef(bed[0], bed[1])[0, 1]) if bed.std() > 0 else 1.0,
            'level_by_second_db': [round(float(20 * np.log10(np.sqrt(np.mean(bed_mono[i:i + sr] ** 2)) + 1e-9)), 1)
                                   for i in range(0, n, sr)]}
    info['kind'] = knowledge.ambient_kind(info)
    return {'bed': bed, 'clicks': clicks, 'bed_info': info, 'clicks_per_s': float(cps), 'events': events, 'free': free}


def run(ctx):
    from . import drums
    cfg, d = ctx['cfg'], ctx['data']
    if 'drums' not in d:
        drums.run(ctx)
    sr = cfg['analysis']['sr']
    resid = d['sep']['residual'] + d['drums']['unexplained']
    res = analyse(resid, sr, ctx['priors']['effects'], cfg)
    d['effects'] = res
    rep = [{k: v for k, v in ev.items() if k != 'audio'} for ev in res['events']]
    jdump({'ambient_bed': res['bed_info'], 'clicks_per_s': res['clicks_per_s'], 'events': rep}, os.path.join(ctx['root'], 'reports', 'effects.json'))
    print(f'  ambient bed: {res["bed_info"]["kind"]}, {res["bed_info"]["level_dbfs"]:.1f} dBFS; clicks {res["clicks_per_s"]:.1f}/s; {len(rep)} effect events')
