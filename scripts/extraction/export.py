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

"""Stage `export`: turn the extraction into things music-generator can use, and record what was learned.

* presets/clones/<voice>/   a sampler (instrument.json + samples/) cut from the voice's cleanest notes, loadable by clone_instrument.py
* presets/instruments/<voice>.json   staging (azimuth, distance, width) measured by the spatial stage, plus the clone path
* presets/drums/<piece>/    the cleanest isolated hits of each drum piece
* presets/clones/ambient_bed/   a loopable bed + its measured description
* (MIDI is written by the resynth and drums stages: out/midi/song.mid, out/midi/drums.mid)
* knowledgebase/instrument_signatures.json   measured templates written back, so the next project starts smarter
* reports/extraction_report.json   one consolidated report"""
import json
import os

import numpy as np

from . import knowledge
from .config import jdump


def cleanliness(note, own, others, sr):
    """Energy of the voice in the note's window over everything else's: higher = a cleaner sample."""
    a, b = int(note['start_s'] * sr), int(note['end_s'] * sr)
    mine = float(np.sum(own[:, a:b] ** 2)) + 1e-12
    rest = float(sum(np.sum(o[:, a:b] ** 2) for o in others)) + 1e-12
    return mine / rest


def purity(note, mono, sr, tuning_cents, harmonics=20, tol=0.03):
    """Share of the stem's energy in the note's window that sits on the note's own harmonics (0..1): 1 = nothing else in the stem there."""
    from .music_db import hz
    a, b = int(note['start_s'] * sr), int(note['end_s'] * sr)
    seg = mono[a:b]
    if len(seg) < 2048:
        return 0.0
    mid = max((len(seg) - 8192) // 2, 0)
    seg = seg[mid:mid + 8192]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    f0 = hz(note['midi'], tuning_cents)
    own = np.zeros(len(f), bool)
    for k in range(1, harmonics + 1):
        if k * f0 < 0.45 * sr:
            own |= np.abs(f - k * f0) <= min(tol * k * f0, 0.25 * f0)
    room = f < 0.45 * sr
    return float(spec[own & room].sum() / (spec[room].sum() + 1e-12))


def distance_m(tail_db, cfg):
    c = cfg['export']['distance']
    if tail_db is None:
        return c['default_m']
    f = float(np.clip((tail_db - c['tail_db_near']) / (c['tail_db_far'] - c['tail_db_near']), 0.0, 1.0))
    return round(c['near_m'] + f * (c['far_m'] - c['near_m']), 2)


def build_sampler(vid, stem, notes, others, tuning_cents, sr, out_dir, cfg, min_clean=0.0, quality='clean'):
    """Cut the best notes out of a voice's stem into a clone_instrument sampler. Returns instrument.json dict or None.
    quality 'clean': voice-to-everything-else energy in the note's window. 'purity': share of the stem's own energy that sits on the note's harmonics."""
    import clone_instrument as ci
    import soundfile as sf
    from scipy import signal
    ex = cfg['export']
    mono = stem.mean(axis=0)
    if sr != ci.SR:                                        # the sampler player assumes its own rate
        mono = signal.resample_poly(mono, ci.SR, sr)
        sr_in, sr = sr, ci.SR
    else:
        sr_in = sr
    cands = [n for n in notes if n['end_s'] - n['start_s'] >= ex['min_note_s']]
    if not cands:
        return None
    best = {}
    for n in cands:
        c = cleanliness(n, stem, others, sr_in) if quality == 'clean' else purity(n, mono, sr, tuning_cents)
        if n['midi'] not in best or c > best[n['midi']][0]:
            best[n['midi']] = (c, n)
    picked = [x for x in sorted(best.values(), key=lambda x: -x[0])[:ex['max_samples']] if x[0] >= min_clean]
    if not picked:
        return None
    d = os.path.join(out_dir, vid)
    os.makedirs(os.path.join(d, 'samples'), exist_ok=True)
    peak = float(np.max(np.abs(mono))) + 1e-9
    rms = []
    zones = []
    for i, (c, n) in enumerate(sorted(picked, key=lambda x: x[1]['midi'])):
        a = int(n['start_s'] * sr)
        b = min(int(n['end_s'] * sr), a + int(ex['max_sample_s'] * sr))
        seg = mono[a:b].copy() / peak * 0.9
        fi, fo = int(0.004 * sr), int(0.02 * sr)
        seg[:fi] *= np.linspace(0, 1, fi)
        seg[-fo:] *= np.linspace(1, 0, fo)
        spec = np.abs(np.fft.rfft(seg[:8192] * np.hanning(min(len(seg), 8192))))
        fr = np.fft.rfftfreq(min(len(seg), 8192), 1 / sr)
        r_db = float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9))
        rms.append(r_db)
        fn = f'n{i:02d}_{n["midi"]}.wav'
        sf.write(os.path.join(d, 'samples', fn), seg, sr, subtype='PCM_24')
        zones.append({'file': f'samples/{fn}', 'midi': round(n['midi'] + tuning_cents / 100.0, 3), 'vel': 0.7, 'rms_db': round(r_db, 1),
                      'centroid': round(float((spec * fr).sum() / (spec.sum() + 1e-9))), 'dur': round(len(seg) / sr, 3), 'cleanliness': round(c, 2)})
    lo, hi = min(rms) - 1e-3, max(rms) + 1e-3
    for z in zones:
        z['vel'] = round(float(np.interp(z['rms_db'], [lo, hi], [0.35, 0.95])), 3) if len(zones) > 1 else 0.7
    meta = {'type': 'sampler', 'name': vid, 'sr': sr, 'zones': zones, 'source': 'extract_pipeline'}
    with open(os.path.join(d, 'instrument.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1)
    return meta


def build_hits(pid, shot, piece, sr, out_dir):
    """One-shot sampler for a drum piece: the aligned median of its most isolated hits."""
    import soundfile as sf
    d = os.path.join(out_dir, pid)
    os.makedirs(d, exist_ok=True)
    sf.write(os.path.join(d, 'hit00.wav'), shot.T, sr, subtype='PCM_24')
    meta = {'type': 'one_shot', 'name': pid, 'kind': piece['kind'], 'sr': sr, 'hits': ['hit00.wav'], 'count_in_song': piece['hits']}
    with open(os.path.join(d, 'instrument.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1)
    return meta


def run(ctx):
    cfg, d, root = ctx['cfg'], ctx['data'], ctx['root']
    if 'enhance' not in d and cfg['enhance']['enabled']:
        from . import enhance
        enhance.run(ctx)
    elif 'gate' not in d:
        from . import gate
        gate.run(ctx)
    sr = d['sr']
    cents = d['tuning']['cents']
    rs = d['resynth']
    raw = d['sep']['voices']
    spat = d['spatial']['sources']
    clones = os.path.join(root, 'presets', 'clones')
    inst_dir = os.path.join(root, 'presets', 'instruments')
    os.makedirs(inst_dir, exist_ok=True)
    declared = {v['id']: v for v in ctx['db']['instruments']}
    summary = {}
    for vid, notes in rs['midi'].items():
        others = [a for k, a in raw.items() if k != vid] + [p['stem'] for p in d['drums']['pieces'].values()]
        meta = rs['samplers'].get(vid) or build_sampler(vid, raw[vid], notes, others, cents, sr, clones, cfg)   # samples are the real recording, cut at the cleaned notes
        sp = (spat.get(vid) or {}).get('baseline', {})
        decl = declared.get(vid, {})
        preset = {'name': vid, 'description': decl.get('label') or f'{vid} extracted from {os.path.basename(ctx["song"])}',
                  'role': decl.get('role', 'melody'), 'clone': f'presets/clones/{vid}' if meta else None,
                  'spatial': {'azimuth': round(sp.get('azimuth_deg', 0.0), 1), 'distance': distance_m(sp.get('reverb_tail_db'), cfg),
                              'width': round(sp.get('width_0_1', 0.0), 2)},
                  'extraction': {'samples': len(meta['zones']) if meta else 0, 'notes': len(notes),
                                 'template': [round(float(x), 3) for x in d['voices'][vid]['template']],
                                 'declared': d['voices'][vid]['declared']}}
        with open(os.path.join(inst_dir, f'{vid}.json'), 'w', encoding='utf-8') as f:
            json.dump(preset, f, indent=2)
        summary[vid] = preset['extraction'] | {'spatial': preset['spatial']} | {k: rs['voice_info'][vid][k] for k in ('gain', 'noise_ratio', 'energy_pct', 'mode')}
    for pid, shot in rs['oneshots'].items():
        piece = d['drums']['pieces'][pid]
        build_hits(pid, shot, piece, sr, os.path.join(root, 'presets', 'drums'))
        summary[f'drum:{pid}'] = {'hits': piece['hits'], 'kind': piece['kind'], 'source': piece['source']}
    from . import audio_io
    loop = rs['ambient'][:, :int(cfg['resynth']['bed_loop_s'] * sr)] / rs['scale']
    os.makedirs(os.path.join(clones, 'ambient_bed'), exist_ok=True)
    audio_io.write(os.path.join(clones, 'ambient_bed', 'bed.wav'), loop, sr)
    jdump({'type': 'loop', 'name': 'ambient_bed', 'file': 'bed.wav', **d['effects']['bed_info'], 'clicks_per_s': d['effects']['clicks_per_s']},
          os.path.join(clones, 'ambient_bed', 'instrument.json'))
    grown = knowledge.grow(ctx, summary) if cfg['export']['grow_knowledge'] else None
    test = test_render(ctx) if cfg['export']['test_render'] else None
    rep = {'song': ctx['song'], 'tuning': {k: v for k, v in d['tuning'].items()}, 'gate': d['gate'], 'voices': summary,
           'dropped_voices': rs['dropped'], 'midi_repairs': rs['midi_stats'],
           'drums': {k: {'hits': p['hits'], 'kind': p['kind'], 'source': p['source'], 'centroid_hz': p['centroid_hz']} for k, p in d['drums']['pieces'].items()},
           'effects': [{k: v for k, v in e.items() if k != 'audio'} for e in d['effects']['events']], 'ambient_bed': d['effects']['bed_info'],
           'clicks_per_s': d['effects']['clicks_per_s'], 'spatial_space': d['spatial']['space'], 'residual_rounds': d.get('residual_log'),
           'enhance': d.get('enhance'), 'knowledge_updated': grown, 'preset_test_render': test}
    jdump(rep, os.path.join(root, 'reports', 'extraction_report.json'))
    print(f'  wrote {len(rs["midi"])} voice presets, {len(rs["oneshots"])} drum sets, ambient bed, reports/extraction_report.json')


def test_render(ctx):
    """Load each sampler through clone_instrument (the route render_natural uses) and play a few notes; reports peak and silence."""
    import clone_instrument as ci
    out = {}
    for vid in ctx['data']['resynth']['midi']:
        path = os.path.join(ctx['root'], 'presets', 'clones', vid)
        if not os.path.isfile(os.path.join(path, 'instrument.json')):
            continue
        inst = ci.load_instrument(path)
        with open(os.path.join(path, 'instrument.json'), encoding='utf-8') as f:
            zones = json.load(f)['zones']
        mids = sorted(round(z['midi'] - ctx['data']['tuning']['cents'] / 100.0) for z in zones)
        pick = [mids[0], mids[len(mids) // 2], mids[-1]]
        ev = [{'t': 0.6 * k, 'dur': 0.5, 'p': m, 'v': 90} for k, m in enumerate(pick)]
        y = ci.render_events(inst, ev)
        out[vid] = {'notes': pick, 'peak': round(float(np.max(np.abs(y))), 3)}
    return out
