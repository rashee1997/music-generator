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

"""Ensemble: every singer is an independent virtual performer (own identity, timing, pitch trajectory, vibrato,
breath). Source only: it returns a stereo mix, dry per-singer stems, a breath stem and placement metadata, and
leaves HRTF/room processing to the project's spatial engine (spatial.py / spatial_hrtf).

cohesion 0..1: 1 = tightly synchronised (small timing/pitch spread, less identity variation); 0 = loose.
Breaths are timed per singer, not per ensemble: one shared plan decides whether a breath happens, each singer
decides when (jitter), how long and through which "end" (character). A choir that gasps on the same
millisecond is the one thing breath modelling must not do.
"""
import numpy as np

from . import breath, context, expression, performance as pf, singer
from . import data
from .utils import dc_block


def soft_limit(y, knee=0.9):
    """Transparent below `knee`, smooth saturation above, never exceeds 1.0. Not a loudness normaliser."""
    a = np.abs(y)
    over = a > knee
    if over.any():
        y = y.copy()
        y[over] = np.sign(y[over]) * (knee + (1 - knee) * np.tanh((a[over] - knee) / (1 - knee)))
    return y


def report(R, dry, mixed, out, sr):
    """Measurements the quality gate reads (quality_gate.vocal_rows). Plain numbers, no judgement here."""
    dev = np.array(R['dev']) if R['dev'] else np.zeros(1)
    v, r = np.array(R['note_v']), np.array(R['note_rms'])
    dyn = None
    if len(v) >= 4 and v.max() - v.min() >= 12 and r.std() > 0:
        dyn = float(np.corrcoef(v, r)[0, 1])
    corr = None
    live = [d for d in dry if d.std() > 1e-9]                     # a silent singer has no correlation
    if len(live) >= 3:
        k = max(1, int(sr // 4000))
        M = np.corrcoef(np.stack([d[::k] for d in live]))
        corr = float(np.nanmax(np.abs(M[np.triu_indices(len(live), 1)])))
    hf = None
    if R['hum']:
        sp = np.abs(np.fft.rfft(mixed[:, 0] * np.hanning(len(mixed)))) ** 2
        fr = np.fft.rfftfreq(len(mixed), 1 / sr)
        hf = float(sp[fr > 1500].sum() / (sp.sum() + 1e-20))
    tim = np.asarray(R.get('timing_ms') or [0.0], dtype=float)
    spreads = [np.asarray(t, dtype=float) for t in (R.get('inhale_map') or {}).values() if len(t) >= 2]
    tv = R.get('technique') or {}
    tech = {k: float(np.mean(v)) for k, v in tv.items() if v}
    vdb, vcr = tv.get('vib_am_db') or [], tv.get('vib_am_corr') or []
    if vdb and len(vdb) == len(vcr):
        # vibrato coupling is read where it is fully developed and measurable: averaging in phrases whose
        # vibrato has not started would report the measurement window, not the singing.
        score = [d * max(c, 0.0) for d, c in zip(vdb, vcr)]
        j = int(np.argmax(score)) if max(score) > 0 else int(np.argmax(vdb))
        tech['vib_am_db'], tech['vib_am_corr'] = float(vdb[j]), float(vcr[j])
    cons = R.get('consonants') or []
    cons_rep = None
    if cons:
        bad = [c for c in cons if c.get('band') and not (0.5 * float(c['band'][0]) <= c.get('centroid_hz', 0.0)
                                                         <= 2.0 * float(c['band'][1]))]
        vot = [c for c in cons if c.get('vot_ms')]
        cons_rep = dict(n=len(cons), centroid_bad=len(bad), centroid_ok=not bad,
                        codes=sorted({c['code'] for c in cons}),
                        declared_vot_ms=float(np.mean([c['vot_ms'] for c in vot])) if vot else None,
                        measured_vot_ms=float(np.mean([c['dur_ms'] for c in vot])) if vot else None)
    ids = np.asarray(R.get('identity') or [], dtype=float)
    identity_pct = float((ids.max() - ids.min()) / max(float(ids.mean()), 1e-9) * 100.0) if len(ids) > 1 else None
    return dict(voices=len(dry), phrases=R['phrases'], joins=R['joins'], longest_phrase_s=round(R['longest_phrase_s'], 2),
                capacity_s=R['capacity_s'], over_capacity=R['over_capacity'], inhales=R['inhales'],
                no_room_phrases=R['no_room_phrases'], mean_abs_dev_cents=float(np.mean(np.abs(dev))),
                max_abs_dev_cents=float(np.max(np.abs(dev))), dyn_corr=dyn, max_corr=corr, hum_hf_frac=hf,
                finite=bool(np.isfinite(mixed).all()), dc=float(np.abs(mixed.mean(0)).max()),
                peak_pre_limit=float(np.abs(mixed).max()), peak=float(np.abs(out).max()),
                technique=tech, consonants=cons_rep, identity_pct=identity_pct, **tech,
                phrasing=dict(contours=sorted(set(R.get('contours') or [])),
                              timing_std_ms=round(float(np.std(tim)), 3),
                              timing_max_ms=round(float(np.max(np.abs(tim))), 3),
                              accent_db=round(float(np.mean(R.get('accents_db') or [0.0])), 3),
                              inhale_spread_ms=None if not spreads else round(float(np.mean([np.std(s) for s in spreads])) * 1e3, 3),
                              tempo_bpm=R.get('tempo_bpm') or 0.0))


def _pos(j, n):
    return 0.0 if n <= 1 else (j / (n - 1)) * 2 - 1


def render(events, sr=44100, cfg=None, seed=1, hum=False, default_vowel=None, voices=None, stems=False, extra_dirs=()):
    """events: dicts t, dur, p, v (+ optional legacy/per-note keys). cfg: full merged config (data.defaults() form).
    Returns (N,2) float32, or (mix, info) when stems=True."""
    cfg = cfg or data.defaults()
    E = cfg['ensemble']
    if not cfg.get('_expression_applied'):                    # vocals.render_choir applies it already, under the preset
        cfg = expression.apply(cfg, E.get('expression'), E.get('expression_intensity', 1.0), extra_dirs)
    E = cfg['ensemble']
    PH = cfg.get('phrasing') or {}
    B = cfg['breathing']
    n_total = int(voices if voices is not None else E['voices'])
    coh = float(np.clip(E['cohesion'], 0.0, 1.0))
    styles = data.deep_merge(data.styles(), cfg.get('styles') or {})
    hum = bool(hum or cfg.get('hum'))
    vowel0 = default_vowel or cfg.get('vowel') or ('m' if hum else 'a')
    end = max((e['t'] + e['dur'] for e in events), default=0.0) + 1.5 + abs(E['timing_spread_ms']) * 1e-3
    N = int(end * sr) + 1
    out = np.zeros((N, 2))
    dry = [np.zeros(N) for _ in range(n_total)]
    brs = [np.zeros(N) for _ in range(n_total)]
    lines = pf.split_lines([dict(e, vowel=e.get('vowel', vowel0)) for e in events])
    info = dict(sr=sr, voices=[], cohesion=coh, expression=E.get('expression') or None)
    piece = context.analyse(events, cfg)
    R = dict(phrases=0, joins=0, longest_phrase_s=0.0, capacity_s=None, over_capacity=0, inhales=0, no_room_phrases=0,
             dev=[], note_v=[], note_rms=[], hum=hum, contours=[], timing_ms=[], accents_db=[], inhale_map={},
             technique={}, consonants=[], identity=[], tempo_bpm=piece['tempo_bpm'])
    div = E['diversity'] * (1.0 - 0.5 * coh)

    for j in range(n_total):
        scfg, ident = singer.make_singer(cfg, j, seed, diversity=div)
        R['identity'].append(float(ident.get('tract.formant_scale', 1.0)) * float(ident.get('tract.length_scale', 1.0))
                             * float(ident.get('tract.pharynx_scale', 1.0)))
        pos = _pos(j, n_total)
        rs = np.random.default_rng([int(seed) & 0xFFFFFFFF, j, 31337])
        t_bias = rs.normal(0.0, E['timing_spread_ms'] * 1e-3 * (1 - coh) * 0.5)
        detune = pos * E['pitch_spread_cents'] * (1 - coh)
        pan = float(np.clip(pos * E['pan_width'], -1, 1))
        gl, gr = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
        gain = 1.0 / np.sqrt(max(1, n_total))
        ref = scfg['dynamics']['ref_rms'] * scfg['dynamics']['level_scale']
        amt = float(np.clip(float((scfg.get('phrasing') or {}).get('amount', 0.0)), 0.0, 1.0))
        for li, line in enumerate(lines):
            if j >= max(int(e.get('voices', n_total)) for e in line):
                continue
            ev = []
            for e in line:
                d = dict(e)
                d['t'] = max(0.0, e['t'] + t_bias + rs.normal(0.0, E['timing_spread_ms'] * 1e-3 * (1 - coh) * 0.2))
                d['c'] = float(e.get('c', 0.0)) + detune
                ev.append(d)
            ev.sort(key=lambda x: x['t'])
            spans = []
            phrases = pf.split_phrases(ev, scfg, default_hum=hum)
            for pi, ph in enumerate(phrases):
                rng = np.random.default_rng([int(seed) & 0xFFFFFFFF, j, li, pi])
                is_hum = pf._is_hum(ph[0], hum)
                st = styles.get(ph[0].get('style') or scfg.get('style') or '', {})
                pctx = context.phrase_context(ph, piece, scfg, pi, len(phrases))
                pctx['role'] = str((scfg.get('phrasing') or {}).get('role') or piece['role'])
                r = pf.render_phrase(ph, sr, rng, scfg, hum=is_hum, style=st, ctx=pctx,
                                     nasality=scfg['humming']['nasality_vowels'] if not is_hum else 0.0)
                a = int(round(r['t0'] * sr))
                sig = r['signal']
                if a < 0:                                      # a consonant before t=0: keep what fits on the timeline
                    sig = sig[-a:]
                    a = 0
                sig = sig[:max(0, N - a)] * gain
                dry[j][a:a + len(sig)] += sig
                spans.append((r['t0'], r['voiced_end']))
                if j == 0:
                    R['phrases'] += 1
                    R['joins'] += r['n_joins']
                    R['contours'].append(r['contour'])
                    R['timing_ms'] += r['timing_ms']
                    if r['accents_db']:
                        R['accents_db'].append(float(np.max(np.abs(r['accents_db']))))
                    for _k, _v in (r.get('technique') or {}).items():
                        if _v is not None:
                            R['technique'].setdefault(_k, []).append(float(_v))
                    R['consonants'] += r.get('consonants') or []
                R['longest_phrase_s'] = max(R['longest_phrase_s'], r['voiced_end'] - r['t0'])
                cap = scfg['breathing']['capacity_s']
                R['capacity_s'] = cap if R['capacity_s'] is None else min(R['capacity_s'], cap)
                R['over_capacity'] += int(r['voiced_end'] - r['t0'] > cap)
                R['dev'] += r['dev_cents']
                R['note_v'] += r['note_v']
                nr = list(r['note_rms'])
                if nr:
                    mnr = float(np.mean(nr))
                    if mnr > 1e-18:
                        nr = [x / mnr for x in nr]
                R['note_rms'] += nr
            # one continuous airflow for the whole line: floor in the gaps, a gap-proportional rise into each
            # phrase, a release after it. Nothing is dropped into silence as a short event.
            if float(scfg['breathing'].get('inhale_gain', 0.0)) > 0:
                rng_b = np.random.default_rng([int(seed) & 0xFFFFFFFF, j, li, 900])
                air = breath.bed(sr, rng_b, scfg['breathing'], ref, spans, N)
                # every singer breathes on the same phase (a section breathes together); only a few ms of
                # offset and a small amplitude difference remain, so the breath is one texture, not N events
                shift = int(round(rs.normal(0.0, min(B['inhale_timing_jitter_ms'], 12.0) * 1e-3) * amt * sr))
                if shift > 0:
                    air = np.concatenate([np.zeros(shift), air[:-shift]])[:N]
                elif shift < 0:
                    air = np.concatenate([air[-shift:], np.zeros(-shift)])[:N]
                air = air * gain * (1.0 + 0.10 * amt * rs.uniform(-1.0, 1.0))
                if amt > 0:
                    # a phrase with no room to breathe still gets the air that escapes at its attack; the bed's
                    # inhale covers the gaps, so a puff is only added where the gap was too short for one
                    rng_p = np.random.default_rng([int(seed) & 0xFFFFFFFF, j, li, 901])
                    for i, (t0, _t1) in enumerate(spans):
                        gap = t0 - spans[i - 1][1] if i else 0.0
                        if i and gap >= float(B['inhale_min_s']) * 0.6:
                            continue
                        puff = breath.onset_puff(sr, rng_p, scfg['breathing'], ref, level_scale=amt)
                        k = int(round(t0 * sr))
                        air[k:k + len(puff)] += puff[:max(0, N - k)]
                brs[j] += air[:N]
                R['inhales'] += sum(1 for i in range(len(spans) - 1)
                                    if spans[i + 1][0] - spans[i][1] >= float(B['inhale_min_s']) * 0.6)
                R['no_room_phrases'] += sum(1 for i in range(len(spans) - 1)
                                            if spans[i + 1][0] - spans[i][1] < float(B['inhale_min_s']) * 0.6)
                if spans:
                    R['inhale_map'].setdefault((li, len(spans) - 1), []).append(spans[-1][0] + shift / float(sr))
        out[:, 0] += (dry[j] + brs[j]) * gl
        out[:, 1] += (dry[j] + brs[j]) * gr
        dist = max(0.3, E['distance_m'] + rs.normal(0.0, E['distance_spread_m']))
        info['voices'].append(dict(index=j, pan=pan, azimuth_deg=float(pos * E['pan_width'] * 60.0), distance_m=float(dist),
                                   detune_cents=float(detune), timing_bias_ms=float(t_bias * 1e3), group='choir',
                                   identity=ident))
    mixed = np.stack([dc_block(out[:, 0]), dc_block(out[:, 1])], axis=1)
    out = soft_limit(mixed).astype(np.float32)
    info['report'] = report(R, dry, mixed, out, sr)
    if not stems:
        return out
    info['stems'] = [soft_limit(dc_block(d)).astype(np.float32) for d in dry]
    info['breath_stems'] = [b.astype(np.float32) for b in brs]
    return out, info
