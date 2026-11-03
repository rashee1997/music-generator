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

"""Stage `gate`: measure the rebuilt song against the original, and the MIDI and mix against the main quality gate.

The rebuilt stems share no phase with the original (they are synthesised from notes), so nothing here subtracts waveforms:
every comparison is of spectra, levels and statistics. Checks, with limits from the profile `gate` section:

  magnitude_match    spectral error of the rebuilt mix against the original, overall and per band, outside the sung/rapped parts
  voice_fidelity     each rebuilt voice against the cut-out stem it was measured from (log-mel correlation, level)
  drum_fidelity      the same for the drum pieces; ambient_match for the noise bed
  render_modes, room_fit  how each voice was rebuilt (real-note sampler or additive) and whether the fitted room helped
  midi_*             how much of each voice's MIDI had to be repaired, polyphony, very short notes, share of notes in the song's key
  natural:*          the main quality gate's naturalness verdicts (loudness, crest, mud, brightness, width, mono fold-down, static timbre)
                     on the rebuilt mix, reported as a fault only when the original does not have it too
  roughness / clicks / masking / tonal_balance / loudness_match / stereo_match   the same borrowing: rebuilt mix vs original
  tempo / tuning / drum_dropouts / spatial_claims / onset_coverage / residual_rounds   the audio against the listening model's claims
  stem_levels, declared_voices, file_budget    clipping, silent or missing voices, and too many files
The score drives the retry loop in extract_pipeline.py: the best attempt wins."""
import os
import sys

import numpy as np

from .config import SK, jdump

SCRIPTS = os.path.join(SK, 'scripts')


def row(check, level, value, limit, detail=''):
    return {'check': check, 'level': level, 'value': value, 'limit': limit, 'detail': detail}


def lvl(value, warn, fail, higher_is_worse=True):
    if higher_is_worse:
        return 'FAIL' if value >= fail else 'WARN' if value >= warn else 'PASS'
    return 'FAIL' if value <= fail else 'WARN' if value <= warn else 'PASS'


def main_gate():
    """(naturalness_check, quality_gate): the skill's own gate, imported from scripts/. quality_gate is slow to import."""
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import naturalness_check as nc
    import quality_gate as qg
    return nc, qg


def free_mask(times, ignored, pad=0.1):
    """True for frame times outside every sung/rapped window."""
    m = np.ones(len(times), bool)
    for a, b in ignored:
        m &= ~((times >= a - pad) & (times <= b + pad))
    return m


def stft_mag(y, n_fft=2048, hop=1024):
    import librosa
    return np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop))


def magnitude_match(ctx, rows):
    d, cfg = ctx['data'], ctx['cfg']
    g = cfg['gate']
    sr, scale = d['sr'], d['resynth']['scale']
    M = stft_mag((d['mix'] * scale).mean(axis=0))
    S = stft_mag(d['resynth']['mix'].mean(axis=0))
    t = np.arange(M.shape[1]) * 1024 / sr
    ignored = ctx['priors'].get('ignored') or []
    free = free_mask(t, ignored)
    f = np.arange(M.shape[0]) * sr / 2048

    def err(mask, fm=None):
        a, b = M[:, mask], S[:, mask]
        if fm is not None:
            a, b = a[fm], b[fm]
        return float(100 * np.sum((a - b) ** 2) / (np.sum(a ** 2) + 1e-12))

    all_err = err(np.ones(len(t), bool))
    if free.sum() < 20:
        rows.append(row('magnitude_match', 'PASS', {'all_frames_pct': round(all_err, 1)}, 'sung/rapped parts cover the song', 'no clean region to judge: informational'))
        return
    total = err(free)
    bands = {k: err(free, (f >= lo) & (f < hi)) for k, (lo, hi) in cfg['analysis']['bands'].items()}
    worst = max(bands, key=bands.get)
    rows.append(row('magnitude_match', lvl(total, g['magnitude_warn_pct'], g['magnitude_fail_pct']), round(total, 1),
                    f'<{g["magnitude_warn_pct"]}% warn, <{g["magnitude_fail_pct"]}% fail',
                    f'spectral error outside the sung/rapped parts ({free.mean() * 100:.0f}% of the song); {round(all_err, 1)}% over everything'))
    rows.append(row('magnitude_by_band', lvl(bands[worst], g['magnitude_warn_pct'], g['magnitude_fail_pct']), {k: round(v, 1) for k, v in bands.items()},
                    f'<{g["magnitude_warn_pct"]}%', f'worst band: {worst}'))


def logmel(y, sr, cfg):
    import librosa
    return np.log10(librosa.feature.melspectrogram(y=y, sr=sr, n_fft=2048, hop_length=1024, n_mels=cfg['gate']['mel_bands']) + 1e-10)


def fidelity(raw, syn, sr, cfg):
    """(correlation of log-mel over the frames where either is active, level difference in dB)."""
    a, b = logmel(raw.mean(axis=0), sr, cfg), logmel(syn.mean(axis=0), sr, cfg)
    fl = cfg['gate']['fidelity_floor_db'] / 10.0
    a, b = np.maximum(a, a.max() + fl), np.maximum(b, b.max() + fl)        # empty bands differ in their noise floor only: not part of the match
    ea, eb = (10 ** a).sum(axis=0), (10 ** b).sum(axis=0)
    floor = 10 ** (cfg['gate']['active_floor_db'] / 10.0)
    act = (ea > floor * ea.max()) | (eb > floor * eb.max())
    if act.sum() < 3 or a[:, act].std() < 1e-9 or b[:, act].std() < 1e-9:
        return 0.0, 0.0
    corr = float(np.corrcoef(a[:, act].ravel(), b[:, act].ravel())[0, 1])
    return corr, float(10 * np.log10((np.sum(syn ** 2) + 1e-12) / (np.sum(raw ** 2) + 1e-12)))


def fidelity_rows(ctx, rows):
    d, cfg = ctx['data'], ctx['cfg']
    g, sr = cfg['gate'], d['sr']
    for vid, syn in d['resynth']['voices'].items():
        corr, db = fidelity(d['sep']['voices'][vid], syn / d['resynth']['scale'], sr, cfg)
        level = 'FAIL' if corr < g['fidelity_fail'] else 'WARN' if (corr < g['fidelity_warn'] or abs(db) > g['level_tol_db']) else 'PASS'
        rows.append(row(f'voice_fidelity:{vid}', level, {'mel_corr': round(corr, 2), 'level_db': round(db, 1)},
                        f'corr >={g["fidelity_warn"]}, level within {g["level_tol_db"]} dB', 'rebuilt voice against the cut-out stem it was measured from'))
    pieces = d['drums']['pieces']
    res = {}
    for pid, syn in d['resynth']['drums'].items():
        corr, db = fidelity(pieces[pid]['stem'], syn / d['resynth']['scale'], sr, cfg)
        res[pid] = (round(corr, 2), round(db, 1))
    if res:
        worst = min(v[0] for v in res.values())
        level = 'FAIL' if worst < g['fidelity_fail'] else 'WARN' if worst < g['fidelity_warn'] or any(abs(v[1]) > g['level_tol_db'] for v in res.values()) else 'PASS'
        rows.append(row('drum_fidelity', level, {k: {'mel_corr': v[0], 'level_db': v[1]} for k, v in res.items()}, f'corr >={g["fidelity_warn"]}'))
    from scipy import signal
    raw, syn = d['effects']['bed'].mean(axis=0), d['resynth']['ambient'].mean(axis=0) / d['resynth']['scale']
    f, p = signal.welch(raw, sr, nperseg=4096)
    _, q = signal.welch(syn, sr, nperseg=4096)
    lc = float(np.corrcoef(np.log10(p + 1e-14), np.log10(q + 1e-14))[0, 1])
    db = float(10 * np.log10((np.sum(syn ** 2) + 1e-12) / (np.sum(raw ** 2) + 1e-12)))
    rows.append(row('ambient_match', 'PASS' if lc >= g['ambient_corr'] and abs(db) <= g['level_tol_db'] else 'WARN',
                    {'spectrum_corr': round(lc, 2), 'level_db': round(db, 1)}, f'corr >={g["ambient_corr"]}, level within {g["level_tol_db"]} dB',
                    'the rebuilt noise bed against the measured one (clicks are included in the rebuilt bed, not in the measured one)'))


def midi_rows(ctx, rows):
    from . import midi_clean
    d, cfg = ctx['data'], ctx['cfg']
    g = cfg['gate']
    prior = {v['id']: v for v in ctx['priors']['voices']}
    midi, stats = d['resynth']['midi'], d['resynth']['midi_stats']
    for vid, st in stats.items():
        if vid not in midi:
            continue
        poly = (prior.get(vid) or {}).get('polyphony') or cfg['midi']['default_polyphony']
        bad = midi_clean.overlap_violations(midi[vid], poly)
        if bad:
            rows.append(row(f'midi_polyphony:{vid}', 'FAIL', bad, f'<= {poly} notes at once', 'more notes sound together than the instrument can play'))
        rows.append(row(f'midi_repair:{vid}', lvl(st['repaired_pct'], g['drop_warn_pct'], 101), st['repaired_pct'], f'<{g["drop_warn_pct"]}% of the found notes repaired',
                        f'{st["found"]} found, {st["kept"]} kept; short {st["short"]}, out of range {st["out_of_range"]}, over polyphony {st["dropped_poly"]}, trimmed {st["trimmed"]}'
                        if st['repaired_pct'] >= g['drop_warn_pct'] else ''))
    shorty = {v: s['short_pct'] for v, s in stats.items() if v in midi and s['short_pct'] > g['short_warn_pct']}
    rows.append(row('midi_short_notes', 'WARN' if shorty else 'PASS', shorty or 'none', f'<{g["short_warn_pct"]}% of a voice\'s notes under {cfg["midi"]["short_note_s"]} s',
                    'many very short notes mean the finder is flickering between pitches' if shorty else ''))
    fit = midi_clean.key_fit_pct(midi, ctx['priors'].get('key'), g['modes'])
    if fit is not None:
        rows.append(row('midi_key', lvl(fit, g['key_warn_pct'], g['key_fail_pct'], higher_is_worse=False), round(fit, 1), f'>{g["key_warn_pct"]}% of note time in the song key',
                        'low share = wrong key in the database, wrong tuning, or ghost notes'))


def render_rows(ctx, rows):
    """How each voice was rebuilt (real-note sampler or additive) and what the room did for the spectrum."""
    rs = ctx['data']['resynth']
    modes = {v: f'{i["mode"]} ({i["samples"]} samples)' for v, i in rs['voice_info'].items()}
    additive = [v for v, i in rs['voice_info'].items() if i['mode'] == 'additive' and i['notes'] >= 20]
    rows.append(row('render_modes', 'PASS', modes, 'sampler where there are enough clean real notes',
                    ('additive (synthetic tone) for: ' + ', '.join(additive) + ' - too few clean notes to cut a sampler') if additive else ''))
    ri = rs.get('room_info')
    if ri:
        helped = ri['error_without_room_pct'] - ri['error_pct']
        level = 'WARN' if ri['at_grid_limit'] else 'PASS'
        rows.append(row('room_fit', level, ri, 'the room level is the one that brings the spectrum closest to the original',
                        'the room is at the loudest allowed level: the measured decay time may be too short' if ri['at_grid_limit']
                        else f'spectral error falls by {helped:.1f} points' if helped > 0 else 'no room needed'))


def natural_rows(ctx, rows):
    """The main gate's naturalness verdicts on the rebuilt mix, compared with the same verdicts on the original."""
    d, cfg = ctx['data'], ctx['cfg']
    g, sr, scale = cfg['gate'], d['sr'], d['resynth']['scale']
    nc, qg = main_gate()
    syn_x = d['resynth']['mix'].T.astype('float64')
    org_x = (d['mix'] * scale).T.astype('float64')
    bpm = ctx['priors']['bpm']
    a = nc.analyse('rebuilt', bpm=bpm, audio=(syn_x, sr))
    b = nc.analyse('original', bpm=bpm, audio=(org_x, sr))
    key = lambda m: ' '.join(m.split()[:3])
    theirs = {key(m) for lv, m in nc.verdicts(b, bpm=bpm) if lv in ('WARN', 'FAIL')}
    for lv, m in nc.verdicts(a, bpm=bpm):
        if lv in ('WARN', 'FAIL') and key(m) in theirs:
            rows.append(row('natural:inherited', 'PASS', m, 'the original has it too', 'not counted: it comes from the recording'))
        elif lv in ('WARN', 'FAIL'):
            rows.append(row('natural:' + key(m), lv, m, 'main quality gate'))
    rows.append(row('natural:summary', 'PASS', {'lufs': round(a['lufs'], 1), 'true_peak': round(a['true_peak'], 1), 'crest': round(a['crest'], 1),
                                                 'centroid_hz': round(a['centroid']), 'stereo_corr': round(a['corr'], 2)}, 'rebuilt mix',
                    f'original: {round(b["lufs"], 1)} LUFS, crest {round(b["crest"], 1)}, centroid {round(b["centroid"])} Hz, corr {round(b["corr"], 2)}'))
    dl = a['lufs'] - b['lufs']
    rows.append(row('loudness_match', 'PASS' if abs(dl) <= g['loudness_tol_lu'] else 'WARN', round(dl, 1), f'within {g["loudness_tol_lu"]} LU of the original'))
    dif = {k: round(a['bands'][k] - b['bands'][k], 1) for k in a['bands']}
    worst = max(abs(v) for v in dif.values())
    rows.append(row('tonal_balance', lvl(worst, g['band_tol_warn_db'], g['band_tol_fail_db']), dif, f'each band within {g["band_tol_warn_db"]} dB of the original', 'rebuilt minus original, dB share per band'))
    rows.append(row('stereo_match', 'PASS' if a['side_db'] >= b['side_db'] - 6.0 else 'WARN', {'side_db': round(a['side_db'], 1), 'original': round(b['side_db'], 1)},
                    'side/mid within 6 dB of the original', 'a much narrower rebuilt image means the stems lost their width'))
    ra, ma = nc.cochlear_roughness_check(syn_x, sr=sr)
    rb, mb = nc.cochlear_roughness_check(org_x, sr=sr)
    ratio = ma['mean_roughness'] / (mb['mean_roughness'] + 1e-9)
    rows.append(row('roughness', 'PASS' if ratio <= g['rough_ratio'] else 'WARN', {'rebuilt': ma['mean_roughness'], 'original': mb['mean_roughness']},
                    f'rebuilt <= {g["rough_ratio"]} x original', 'clashing overtones added by the synthesis (cochlear roughness, main gate)'))
    mono_a, mono_b = syn_x.mean(axis=1), org_x.mean(axis=1)
    ca, cb = len(qg.find_clicks(mono_a)), len(qg.find_clicks(mono_b))
    rows.append(row('clicks', 'PASS' if ca <= g['click_ratio'] * cb + g['click_min'] else 'FAIL', {'rebuilt': ca, 'original': cb},
                    f'rebuilt <= {g["click_ratio"]} x original + {g["click_min"]}', 'single-sample jumps (main gate): note starts that are not faded in'))
    stem_clicks = {v: len(qg.find_clicks(x.mean(axis=0))) for v, x in d['resynth']['voices'].items()}
    bad = {v: c for v, c in stem_clicks.items() if c > g['click_min']}
    rows.append(row('stem_clicks', 'FAIL' if bad else 'PASS', bad or 'none', f'<= {g["click_min"]} per voice stem'))
    roles = {v['id']: v.get('role') for v in ctx['priors']['voices']}
    tracks = [{'name': k, 'role': 'melody' if roles.get(k) in g['lead_roles'] else 'pad' if roles.get(k) in g['bed_roles'] else 'other'}
              for k in d['resynth']['voices']]
    stems = {k: v.T for k, v in d['resynth']['voices'].items()}
    for lv, name, detail in qg.masking_rows(stems, {'tracks': tracks}, sr=sr):
        rows.append(row(name, lv, '', 'main gate: ERB critical-band masking', detail))


def levels(ctx, rows):
    d, g = ctx['data'], ctx['cfg']['gate']
    for i, a in d['resynth']['voices'].items():
        peak = float(np.max(np.abs(a)))
        rms_db = float(20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9))
        if peak >= g['clip_peak']:
            rows.append(row(f'stem_levels:{i}', 'FAIL', round(peak, 4), f'<{g["clip_peak"]}', 'clipped'))
        elif rms_db < g['silent_rms_db']:
            rows.append(row(f'stem_levels:{i}', 'WARN', round(rms_db, 1), f'>{g["silent_rms_db"]} dBFS', 'silent'))
    for vid, info in d['resynth']['dropped'].items():
        if info['declared']:
            rows.append(row(f'declared_voice:{vid}', 'WARN', info, 'declared voices should be found', 'not found in the audio (no notes, or almost no energy): check the database or the range'))
    n = len([f for f in os.listdir(os.path.join(ctx['root'], 'out', 'stems')) if f.endswith('.wav')])
    rows.append(row('file_budget', 'PASS' if n <= g['max_files'] else 'WARN', n, f'<= {g["max_files"]} stem files'))


def onset_coverage(ctx, rows):
    import librosa
    d, g, cfg = ctx['data'], ctx['cfg']['gate'], ctx['cfg']
    sr, hop = d['sr'], cfg['analysis']['hop']
    mono = d['mix'].mean(axis=0)
    env = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=hop)
    on = librosa.frames_to_time(librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, delta=g['onset_delta']), sr=sr, hop_length=hop)
    if len(on) == 0:
        return
    known = [t for p in d['drums']['pieces'].values() for t in p['times']]
    known += [n['start_s'] for notes in d['resynth']['midi'].values() for n in notes]
    known += [e['start_s'] for e in d['effects']['events']]
    known += [t for a, b in ctx['priors'].get('ignored') or [] for t in np.arange(a, b, 0.05)]      # onsets inside sung parts are not ours to explain
    known = np.sort(np.array(known)) if known else np.array([1e9])
    tol = cfg['analysis']['onset_match_tol_s']
    miss = [t for t in on if np.min(np.abs(known - t)) > tol]
    pct = 100 * (1 - len(miss) / len(on))
    rows.append(row('onset_coverage', lvl(pct, g['onset_warn_pct'], g['onset_fail_pct'], higher_is_worse=False), round(float(pct), 1),
                    f'>{g["onset_warn_pct"]}%', f'{len(miss)} of {len(on)} mix onsets have no note, hit or effect'))


def database_agreement(ctx, rows):
    import librosa
    d, g = ctx['data'], ctx['cfg']['gate']
    t = d['tuning']
    if t.get('prior') is not None:
        rows.append(row('tuning_vs_database', 'PASS' if t['agree'] else 'WARN', round(t['measured'], 1), f'within {ctx["cfg"]["tuning"]["agree_cents"]} cents of {t["prior"]:+.1f}'))
    bpm = ctx['priors']['bpm']
    if bpm:
        m = float(np.atleast_1d(librosa.beat.beat_track(y=d['mix'].mean(axis=0), sr=d['sr'])[0])[0])
        err = min(abs(m / bpm - r) for r in (1.0, 2.0, 0.5))
        rows.append(row('tempo_vs_database', 'PASS' if err <= g['tempo_tol'] else 'WARN', round(m, 1), f'{bpm} BPM +-{100 * g["tempo_tol"]:.0f}% (or x2, /2)'))
    grid = ctx['priors']['grid']
    hits = {t for p in d['drums']['pieces'].values() for t in p['times']}
    kw = tuple(ctx['cfg']['gate']['dropout_words'])
    gaps = [(f['at_s'], f['at_s'] + (grid['bar_s'] if grid else 2.0)) for f in (ctx['db']['drums'].get('groove') or {}).get('fills', [])
            if any(w in str(f.get('kind', '')).lower() for w in kw)]
    for pc in ctx['priors']['drum_pieces']:
        act = sorted((a['start_s'], a['end_s']) for a in pc.get('active', []))
        gaps += [(e0, s1) for (_, e0), (s1, _) in zip(act, act[1:]) if s1 - e0 >= g['dropout_min_s']]
    seen = {}
    for a, b in gaps:
        n = sum(1 for t in hits if a + 0.1 <= t <= b - 0.1)
        seen[f'{a:.1f}-{b:.1f}'] = n
    if seen:
        wrong = {k: v for k, v in seen.items() if v > g['dropout_max_hits']}
        rows.append(row('drum_dropouts', 'WARN' if wrong else 'PASS', wrong or 'all quiet', f'<={g["dropout_max_hits"]} hits in a claimed dropout',
                        'the database says no drums here, but hits were found (leakage from other stems, or the claimed time is off)' if wrong else ''))
    cmp_rows = d.get('spatial', {}).get('claimed_vs_measured', [])
    if cmp_rows:
        off = [r for r in cmp_rows if not r['agree']]
        rows.append(row('spatial_claims', 'WARN' if off else 'PASS', {r['id']: [r['claimed_deg'], r['measured_deg']] for r in off} or 'all agree',
                        f'within {ctx["cfg"]["spatial"]["disagree_deg"]} degrees'))


def residual_rows(ctx, rows):
    log = ctx['data'].get('residual_log')
    if log:
        last = log[-1]['unexplained_pct']
        g = ctx['cfg']['gate']
        rows.append(row('residual_rounds', lvl(last, g['tonal_warn_pct'], g['tonal_fail_pct']), last, f'<{g["tonal_warn_pct"]}% tonal energy unexplained',
                        f'{len(log) - 1} extra round(s)'))


CHECKS = (magnitude_match, fidelity_rows, midi_rows, render_rows, natural_rows, levels, onset_coverage, database_agreement, residual_rows)


def evaluate(ctx):
    rows = []
    if 'resynth' not in ctx['data']:
        from . import resynth
        resynth.run(ctx)
    for fn in CHECKS:
        try:
            fn(ctx, rows)
        except Exception as e:                                 # a broken check must show up in the report, never vanish
            rows.append(row(fn.__name__, 'WARN', '', '', f'check crashed: {type(e).__name__}: {e}'))
    score = sum({'PASS': 0, 'WARN': 3, 'FAIL': 10}[r['level']] for r in rows)
    return rows, score


def run(ctx):
    d = ctx['data']
    d.setdefault('sr', ctx['cfg']['analysis']['sr'])
    if 'spatial' not in d:
        from . import spatial
        spatial.run(ctx)
    rows, score = evaluate(ctx)
    d['gate'] = {'rows': rows, 'score': score}
    for r in rows:
        print(f'  [{r["level"]}] {r["check"]}: {r["value"]}  ({r["limit"]}) {r["detail"]}')
    print(f'  gate score {score} ({sum(r["level"] == "FAIL" for r in rows)} FAIL, {sum(r["level"] == "WARN" for r in rows)} WARN)')
    jdump({'score': score, 'rows': rows}, os.path.join(ctx['root'], 'reports', 'gate.json'))
