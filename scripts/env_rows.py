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

"""env_rows.py - gate rows for environment tracks written as `biome/1` presets (see biome/ and references/mixing/quality-gate.md).

Every row names the lever in the preset or the score, never a threshold. The numbers are starting values (gate_profiles.ROWS):
nothing here has been calibrated on real recordings, so the measured rows are INFO or WARN; only the facts about the
declaration (a key that does not exist, a medium that contradicts its own measurement, a number with no source) are FAIL.

    env.declaration          the preset validates; every generator, animal and medium names its sources or says ESTIMATE
    env.medium_consistency   c against the measured value; the biome's air against the bus's; a tube's F1 against c / 4L; no 343 literal
    env.niche_collision      Schoener D of two animals' bands x the share of time both call (from the plan)
    env.score_pocket         the share of foreground calls the score's occupancy leaves a pocket for
    env.foreground_salience  a call against the rest of the biome in its own band (the figure is ear.masking's business)
    env.loop_stationarity    a bed declared `stationary`: level drift, chunk-edge seam, repeat
    env.density_budget       calls begun per second against ecology.density_budget
    env.level_physical       a generator's rendered pressure against its own physics
    env.diffuse_field        a field source's interchannel correlation against its target
    env.ecology_rules        every freeze honoured, every rule fired
    env.cpu_budget           render time per minute of audio, projected from a short render
"""
import ast
import math
import os
import time

import numpy as np
from scipy import signal

import gate_profiles
import presets

SCENE_MODULES = ('env_engine/calls.py', 'phys_core/propagate.py', 'phys_core/resonate.py', 'environment.py', 'airabs.py',
                 'spatial_engine/hoa.py', 'spatial_engine/nfc.py', 'spatial_hrtf/room.py', 'biome/engine.py', 'biome/generators.py',
                 'biome/fauna.py', 'biome/sources.py', 'biome/tract.py', 'biome/ecology.py')
LEVELS = {'INFO': 0, 'WARN': 1, 'FAIL': 2}
SR = 44100
FRAME_S = 0.25


def _row(out, level, name, detail):
    out.append((level, name, detail))


def _worst(levels):
    return max(levels, key=lambda lv: LEVELS[lv]) if levels else 'INFO'


# ------------------------------------------------------------------------------------------------ the tracks
def _is_biome(cfg):
    return isinstance(cfg, dict) and cfg.get('schema') == 'biome/1'


def biome_tracks(score):
    """[{track, name, preset, t0, span}] for every environment track of the score whose preset is a `biome/1`."""
    from biome import ecology
    out = []
    for i, tr in enumerate((score or {}).get('tracks') or []):
        raw = str(tr.get('instrument', ''))
        key = tr.get('environment') or (raw.split(':', 1)[1] if raw.startswith('env:') else None)
        if not key:
            continue
        cfg = presets.find_environment(key)
        if not _is_biome(cfg):
            continue
        t0, span = ecology.track_timing(score, tr)
        out.append(dict(track=tr.get('name', f'track{i}'), name=key, preset=cfg, t0=t0, span=span))
    return out


def literals(path, values=(343, 343.0)):
    root = os.path.dirname(os.path.abspath(__file__))
    tree = ast.parse(open(os.path.join(root, path), encoding='utf-8').read())
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool) and n.value in values]


def _biome(rec, score, seed=7, preset=None):
    from biome import engine
    return engine.Biome(preset or rec['preset'], seed=seed, score=score, t0_s=rec['t0'])


def bouts(biome, span):
    """{animal: [(start, duration)]} that the biome will call within `span` seconds: the plan, or the animal's own schedule."""
    out = {f.name: [] for f in biome.fauna}
    if biome.planner is not None:
        biome.planner.plan_until(float(span) + 1.0)
        for (name, _), v in biome.planner.plan.items():
            out[name] += [b for b in v if b[0] < span]
    else:
        for f in biome.fauna:
            out[f.name] += [(t, d) for _, t, d in f.bouts_until(float(span))]
    return {k: sorted(v) for k, v in out.items()}


def _union(intervals):
    """[(start, duration)] -> disjoint [(start, end)]: an animal with several individuals is calling whenever any of them is."""
    out = []
    for s, d in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], s + d)
        else:
            out.append([s, s + d])
    return out


def _overlap_s(a, b):
    """Seconds in which both animals are calling, counting each moment once."""
    ua, ub, tot = _union(a), _union(b), 0.0
    for s, e in ua:
        for s2, e2 in ub:
            tot += max(0.0, min(e, e2) - max(s, s2))
    return tot


def _calling_s(a):
    return sum(e - s for s, e in _union(a))


# ------------------------------------------------------------------------------------------------ static rows
def declaration_row(gp, rec, out):
    from biome import schema
    label = f'"{rec["track"]}" ({rec["name"]})'
    bad = schema.problems(rec['preset'])
    if bad:
        _row(out, 'FAIL', 'env.declaration', f'{label}: ' + '; '.join(bad[:4]) + (f' (and {len(bad) - 4} more)' if len(bad) > 4 else ''))
        return
    p = rec['preset']
    media = p['media'] if 'media' in p else {'air': p['medium']}
    blocks = [(f'medium {n}', m) for n, m in media.items()] + [(f'generator {g["name"]}', g) for g in p.get('generators') or []] \
        + [(f'animal {f["name"]}', f) for f in p.get('fauna') or []]
    missing = [n for n, b in blocks if not [s for s in (b.get('sources') or []) if str(s).strip()]]
    if missing:
        _row(out, 'FAIL', 'env.declaration', f'{label}: no "sources" line on {", ".join(missing)}: every number names its source or says ESTIMATE')
        return
    est = [n for n, b in blocks if any(str(s).startswith('ESTIMATE') for s in b.get('sources') or [])]
    if est:
        _row(out, 'WARN', 'env.declaration', f'{label}: ESTIMATE remains on {", ".join(est)}; a delivered preset carries measurements from the research note')
    else:
        _row(out, 'INFO', 'env.declaration', f'{label}: valid, every block names its sources')


def consistency_row(gp, rec, score, out):
    from phys_core import medium as M
    from biome import tract
    label = f'"{rec["track"]}"'
    p = rec['preset']
    cfgs = p['media'] if 'media' in p else {'air': p['medium']}
    lv, msg = [], []
    max_c, fail_c = gp.param('env.medium_consistency', 'max_err_c'), gp.param('env.medium_consistency', 'fail_err_c')
    for n, c in cfgs.items():
        m = M.Medium(dict(c, name=c.get('name', n)))
        e = m.consistency()['err_c']
        if e is not None:
            lv.append('FAIL' if e > fail_c else 'WARN' if e > max_c else 'INFO')
            msg.append(f'{n}: c {m.c:.1f} m/s against the measured {m.c_measured:g} ({100 * e:.1f} %)')
    world = p.get('world') or {}
    lm = (world.get('listener') or {}).get('medium') or ('air' if 'air' in cfgs else sorted(cfgs)[0])
    mine, bus = M.Medium(cfgs[lm]), M.from_score(score)
    f = np.array([1000.0, 4000.0, 8000.0])
    a, b = np.asarray(mine.alpha_db_per_m(f)), np.asarray(bus.alpha_db_per_m(f))
    e = float(np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-9)))
    mx, fl = gp.param('env.medium_consistency', 'max_err_alpha'), gp.param('env.medium_consistency', 'fail_err_alpha')
    lv.append('FAIL' if e > fl else 'WARN' if e > mx else 'INFO')
    msg.append(f'absorption of the biome\'s air against the score\'s medium: {100 * e:.1f} % at 1, 4, 8 kHz'
               + ('; declare the same medium on the score (score.medium)' if e > mx else ''))
    for fa in p.get('fauna') or []:
        r = fa.get('resonator') or {}
        if r.get('kind') == 'tube':
            m = M.Medium(cfgs[fa.get('medium') or lm])
            f1 = tract.design(r, m, SR)[0][0]
            want = m.c / (4.0 * r['length_cm'] / 100.0)
            e1 = abs(f1 - want) / want
            lv.append('WARN' if e1 > gp.param('env.medium_consistency', 'max_f1_err') else 'INFO')
            msg.append(f'{fa["name"]}: tube F1 {f1:.0f} Hz against c/4L {want:.0f} Hz ({100 * e1:.1f} %)')
    found = {m_: literals(m_) for m_ in SCENE_MODULES}
    found = {k: v for k, v in found.items() if v}
    if found:
        lv.append('FAIL')
        msg.append('a 343 literal is left in ' + ', '.join(f'{k}:{v[0]}' for k, v in found.items()) + ': read the speed from the medium')
    _row(out, _worst(lv), 'env.medium_consistency', f'{label}: ' + '; '.join(msg))


# ------------------------------------------------------------------------------------------------ plan rows
def niche_row(gp, rec, biome, plan, out):
    from biome import ecology
    label = f'"{rec["track"]}"'
    cfgs = [f.cfg for f in biome.fauna if (f.cfg.get('niche') or {}).get('band_hz')]
    if len(cfgs) < 2:
        _row(out, 'INFO', 'env.niche_collision', f'{label}: fewer than two animals declare a niche band: nothing to compare')
        return
    wd, wc, fd, fc = (gp.param('env.niche_collision', k) for k in ('warn_d', 'warn_co', 'fail_d', 'fail_co'))
    rows, lv = [], []
    for i, a in enumerate(cfgs):
        for b in cfgs[i + 1:]:
            d = ecology.schoener(ecology.band_shares(*a['niche']['band_hz']), ecology.band_shares(*b['niche']['band_hz']))
            pa, pb = plan.get(a['name'], []), plan.get(b['name'], [])
            ta, tb = _calling_s(pa), _calling_s(pb)
            co = _overlap_s(pa, pb) / min(ta, tb) if min(ta, tb) > 0 else 0.0
            lv.append('FAIL' if (d >= fd and co >= fc) else 'WARN' if (d >= wd and co >= wc) else 'INFO')
            rows.append(f'{a["name"]}/{b["name"]}: D {d:.2f}, calling together {100 * co:.0f} % of the shorter one\'s time')
    worst = _worst(lv)
    tail = '' if worst == 'INFO' else '. Move niche.band_hz apart, change their active windows, lower individuals, or set ecology.niches.auto'
    _row(out, worst, 'env.niche_collision', f'{label}: ' + '; '.join(rows) + tail)


def pocket_row(gp, rec, biome, plan, score, out):
    from biome import ecology
    label = f'"{rec["track"]}"'
    fg = [f for f in biome.fauna if f.cfg.get('salience') == 'foreground' and (f.cfg.get('niche') or {}).get('band_hz')]
    if not fg or biome.occupancy is None and not (score or {}).get('tracks'):
        _row(out, 'INFO', 'env.score_pocket', f'{label}: no foreground animal with a niche band, or no score to read: not measured')
        return
    occ = biome.occupancy or ecology.Occupancy.from_score(score)
    thr = float(((rec['preset'].get('ecology') or {}).get('score') or {}).get('pocket_threshold', 0.35))
    inside = total = 0
    for f in fg:
        lo, hi = f.cfg['niche']['band_hz']
        for s, d in plan.get(f.name, []):
            total += 1
            inside += int(occ.level(s + rec['t0'], s + rec['t0'] + d, lo, hi) <= thr)
    if not total:
        _row(out, 'INFO', 'env.score_pocket', f'{label}: the foreground animals make no call in the span: not measured')
        return
    share = inside / total
    mn, fl = gp.param('env.score_pocket', 'min_in_pocket'), gp.param('env.score_pocket', 'fail_in_pocket')
    lvl = 'INFO' if share >= mn else 'FAIL' if share < fl else 'WARN'
    _row(out, lvl, 'env.score_pocket', f'{label}: {inside} of {total} foreground calls ({100 * share:.0f} %) sit where the score occupies their band '
                                       f'under {thr:g} (want {100 * mn:.0f} %)' + ('' if lvl == 'INFO' else '. Raise ecology.score.pocket_threshold or margin_db, lower bouts_per_min, or move the niche band'))


def density_row(gp, rec, biome, plan, out):
    label = f'"{rec["track"]}"'
    budget = ((rec['preset'].get('ecology') or {}).get('density_budget') or {}).get('events_per_s_max')
    starts = sorted(s for v in plan.values() for s, _ in v)
    declared = sum(f.bouts_per_min * f.n_ind * f.rate for f in biome.fauna) / 60.0
    peak = max([sum(1 for x in starts if t - 10.0 < x <= t) / 10.0 for t in starts] or [0.0])
    if not budget:
        _row(out, 'INFO', 'env.density_budget', f'{label}: no ecology.density_budget declared; the animals plan {len(starts)} calls (at most {peak:.2f} a second over 10 s)')
        return
    over = gp.param('env.density_budget', 'max_over')
    lv = []
    msg = f'budget {budget:g} calls/s; declared rate {declared:.2f}/s, planned peak {peak:.2f}/s over 10 s'
    lv.append('FAIL' if peak > budget * (1 + over) else 'INFO')
    if declared > budget * (1 + over):
        lv.append('WARN')
        msg += '; the animals ask for more than the budget allows, so the planner thins them: lower bouts_per_min or individuals'
    _row(out, _worst(lv), 'env.density_budget', f'{label}: {msg}')


def rules_row(gp, rec, biome, plan, out):
    label = f'"{rec["track"]}"'
    rules = (rec['preset'].get('ecology') or {}).get('rules') or []
    if not rules or biome.planner is None:
        _row(out, 'INFO', 'env.ecology_rules', f'{label}: no ecology rules')
        return
    rep = biome.planner.report()
    bad, idle = [], []
    for n, wins in rep['windows'].items():
        for t0, t1, _, _ in wins:
            for s, _ in plan.get(n, []):
                if t0 <= s < t1:
                    bad.append(f'{n} begins a call at {s:.1f} s inside its freeze {t0:.1f}-{t1:.1f} s')
    for i, r in enumerate(rules):
        targets = list(r['do'].get('freeze') or []) + ([r['do']['answer']] if r['do'].get('answer') else [])
        fired = any(rep['windows'].get(n) for n in r['do'].get('freeze') or []) or (r['do'].get('answer') and plan.get(r['do']['answer']))
        if not fired:
            idle.append(f'rule {i} ({r["on"]}) never fired in the span')
    if bad:
        _row(out, 'FAIL', 'env.ecology_rules', f'{label}: ' + '; '.join(bad[:3]))
    elif idle:
        _row(out, 'WARN', 'env.ecology_rules', f'{label}: ' + '; '.join(idle) + '. Check the names against sections and animals; a trigger that never calls never fires')
    else:
        _row(out, 'INFO', 'env.ecology_rules', f'{label}: {len(rules)} rule(s), every freeze honoured and every rule fired')


# ------------------------------------------------------------------------------------------------ measured rows
def _solo(preset, names, keep_fauna=False):
    """The preset reduced to the named generators (and no animals): independent sources render the same alone as in the mix."""
    p = dict(preset)
    p['generators'] = [g for g in preset.get('generators') or [] if g['name'] in names]
    if not keep_fauna:
        p.pop('fauna', None)
        p.pop('ecology', None)
    return p


def level_row(gp, rec, out, window_s=20.0):
    from biome import engine
    label = f'"{rec["track"]}"'
    p = rec['preset']
    rows, lv, skipped = [], [], []
    mx, fl = gp.param('env.level_physical', 'max_db'), gp.param('env.level_physical', 'fail_db')
    for g in p.get('generators') or []:
        b = engine.Biome(_solo(p, {g['name']}), seed=7)
        gen = b.sources[0].gen
        t_mid = 0.5 * window_s
        want = gen.expected_rms_pa(t_mid)
        if want is None or want <= 0 or (g.get('population') and isinstance(g['population'].get('rate_mm_h'), dict)) or isinstance(((g.get('flow') or {}).get('u_m_s')), dict):
            continue
        if g['kind'] == 'turbulence' and float((g.get('flow') or {}).get('intensity', 0.2)) > 0.15:
            skipped.append(f'{g["name"]}: gust-dominated (a few gust cycles in the window): not compared')
            continue
        rate = gen.events_per_s(t_mid)
        if rate is not None and rate * window_s < 100.0:
            skipped.append(f'{g["name"]}: {rate * window_s:.0f} events in the window, too few for the mean to hold: not compared')
            continue
        y = gen.render(window_s).astype(np.float64)
        got = float(np.sqrt(np.mean(y ** 2)))
        db = 20.0 * math.log10(max(got, 1e-30) / want)
        lv.append('FAIL' if abs(db) > fl else 'WARN' if abs(db) > mx else 'INFO')
        rows.append(f'{g["name"]}: {got:.2e} Pa against the physics\' {want:.2e} ({db:+.1f} dB)')
    if not rows:
        _row(out, 'INFO', 'env.level_physical', f'{label}: no generator with a constant rate and a closed-form prediction: not measured'
             + (' (' + '; '.join(skipped) + ')' if skipped else ''))
        return
    _row(out, _worst(lv), 'env.level_physical', f'{label}: ' + '; '.join(rows + skipped) + ('' if _worst(lv) == 'INFO' else '. Remove any normalisation; check k_dipole, efficiency, area_m2'))


def window_deviation(y, sr=SR, n_windows=8):
    """The largest level difference (dB) of any of 12 bands in any of `n_windows` windows from the median window."""
    edges = np.geomspace(100.0, 8000.0, 13)
    sos = [signal.butter(2, [lo, hi], 'band', fs=sr, output='sos') for lo, hi in zip(edges[:-1], edges[1:])]
    levels = np.array([[10 * np.log10(np.mean(signal.sosfilt(s_, w) ** 2) + 1e-30) for s_ in sos] for w in np.array_split(np.asarray(y, dtype=np.float64), n_windows)])
    return float(np.max(np.abs(levels - np.median(levels, axis=0))))


def chunk_seam_db(y, chunk_s, sr=SR):
    """How much more the 50 ms level jumps across the chunk edges than it does elsewhere (dB, never negative)."""
    y = np.asarray(y, dtype=np.float64)
    h, c = int(0.05 * sr), int(chunk_s * sr)

    def jump(i):
        return abs(10 * np.log10(np.mean(y[i:i + h] ** 2) + 1e-30) - 10 * np.log10(np.mean(y[i - h:i] ** 2) + 1e-30))
    edges = [i for i in range(c, len(y) - h, c)]
    rest = [i + int(0.37 * c) for i in range(0, len(y) - c, c) if i + int(0.37 * c) > h]
    if not edges or not rest:
        return 0.0
    return max(0.0, float(np.mean([jump(i) for i in edges])) - float(np.mean([jump(i) for i in rest])))


def repeat_score(y, sr=SR, lags=(5, 60)):
    """The strongest autocorrelation of the 1 s level envelope at lags of 5-60 s (1 would be an exact tiled loop)."""
    y = np.asarray(y, dtype=np.float64)
    env = np.sqrt(np.mean(y[:len(y) // sr * sr].reshape(-1, sr) ** 2, axis=1))
    env = env - env.mean()
    if len(env) <= lags[0] + 2 or env.std() <= 0:
        return 0.0
    ac = np.correlate(env, env, 'full')[len(env) - 1:]
    ac = ac / max(ac[0], 1e-30)
    return float(np.max(ac[lags[0]:min(lags[1], len(ac))]))


def stationarity_row(gp, rec, out, window_s=80.0, chunk_s=0.2):
    from biome import engine
    label = f'"{rec["track"]}"'
    names = {g['name'] for g in rec['preset'].get('generators') or [] if g.get('stationary')}
    if not names:
        _row(out, 'INFO', 'env.loop_stationarity', f'{label}: no generator declared stationary: not measured')
        return
    secs = min(window_s, max(rec['span'], 20.0))
    b = engine.Biome(_solo(rec['preset'], names), seed=7)
    y = np.concatenate(list(b.stream(secs, chunk_s=chunk_s))).astype(np.float64).mean(axis=1)
    dev, seam, rep = window_deviation(y), chunk_seam_db(y, chunk_s), repeat_score(y)
    P = {k: gp.param('env.loop_stationarity', k) for k in ('max_window_dev', 'fail_window_dev', 'max_seam_db', 'fail_seam_db', 'max_repeat', 'fail_repeat')}
    lv = ['FAIL' if dev > P['fail_window_dev'] else 'WARN' if dev > P['max_window_dev'] else 'INFO',
          'FAIL' if seam > P['fail_seam_db'] else 'WARN' if seam > P['max_seam_db'] else 'INFO',
          'FAIL' if rep > P['fail_repeat'] else 'WARN' if rep > P['max_repeat'] else 'INFO']
    _row(out, _worst(lv), 'env.loop_stationarity', f'{label}: {", ".join(sorted(names))} over {secs:.0f} s: band level moves {dev:.1f} dB between windows, '
                                                  f'chunk-edge seam {seam:.2f} dB, envelope repeat {rep:.2f}'
         + ('' if _worst(lv) == 'INFO' else '. Raise the gust corner or intensity, give the control curve more variance, or split a tiled bed into two named generators'))


def mean_abs_correlation(y, sr=SR, bands=8):
    """Mean over `bands` log-spaced bands (250 Hz - 8 kHz) of the absolute interchannel correlation of a stereo signal."""
    y = np.asarray(y, dtype=np.float64)
    edges = np.geomspace(250.0, 8000.0, bands + 1)
    c = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sos = signal.butter(4, [lo, hi], 'band', fs=sr, output='sos')
        l, r = signal.sosfilt(sos, y[:, 0]), signal.sosfilt(sos, y[:, 1])
        c.append(abs(float(np.corrcoef(l, r)[0, 1])))
    return float(np.mean(c))


def diffuse_row(gp, rec, out, window_s=20.0):
    from biome import engine
    label = f'"{rec["track"]}"'
    fields = {g['name']: g for g in rec['preset'].get('generators') or [] if (g.get('spatial') or {}).get('field')}
    if not fields:
        _row(out, 'INFO', 'env.diffuse_field', f'{label}: no field source: not measured')
        return
    target = float(((rec['preset'].get('spatial_coupling') or {}).get('field') or {}).get('correlation_target', gp.param('env.diffuse_field', 'target')))
    wo, fo = gp.param('env.diffuse_field', 'warn_over'), gp.param('env.diffuse_field', 'fail_over')
    rows, lv = [], []
    b = engine.Biome(_solo(rec['preset'], set(fields)), seed=7)
    for s in b.sources:
        y = np.concatenate(list(s_stream(s, int(window_s * SR)))).astype(np.float64)
        c = mean_abs_correlation(y)
        lv.append('FAIL' if c > target + fo else 'WARN' if c > target + wo else 'INFO')
        rows.append(f'{s.name}: mean |correlation| {c:.2f} over 250 Hz-8 kHz (target {target:g})')
    _row(out, _worst(lv), 'env.diffuse_field', f'{label}: ' + '; '.join(rows) + ('' if _worst(lv) == 'INFO' else '. More emitters, a different correlation_target, or a wider decorrelator'))


def s_stream(src, n, chunk=44100 * 5):
    done = 0
    while done < n:
        m = min(chunk, n - done)
        yield src.render(m)
        done += m


def salience_row(gp, rec, biome, plan, out, window_s=90.0):
    from biome import ecology
    label = f'"{rec["track"]}"'
    fg = [f for f in biome.fauna if f.cfg.get('salience') == 'foreground' and (f.cfg.get('niche') or {}).get('band_hz')]
    if not fg:
        _row(out, 'INFO', 'env.foreground_salience', f'{label}: no foreground animal with a niche band: not measured')
        return
    secs = min(window_s, rec['span'])
    biome.planner and biome.planner.plan_until(secs + 1.0)
    fr = int(FRAME_S * SR)
    series = {f.name: ([], []) for f in fg}
    sos = {f.name: signal.butter(2, [float(f.cfg['niche']['band_hz'][0]), min(float(f.cfg['niche']['band_hz'][1]), 0.45 * SR)], 'band', fs=SR, output='sos') for f in fg}
    zi = {n: [np.zeros((sos[n].shape[0], 2)), np.zeros((sos[n].shape[0], 2))] for n in sos}
    left, step = int(secs * SR), 5 * SR
    carry = {n: ([], []) for n in sos}
    while left > 0:
        n = min(step, left)
        parts = biome.step_parts(n)
        mono = {k: v.mean(axis=1) for k, v in parts.items()}
        tot = sum(mono.values())
        for f in fg:
            for j, x in enumerate((mono[f.name], tot - mono[f.name])):
                y, zi[f.name][j] = signal.sosfilt(sos[f.name], x, zi=zi[f.name][j])
                carry[f.name][j].append(y)
        left -= n
    mn, mxs, share_low = (gp.param('env.foreground_salience', k) for k in ('min_db', 'max_db', 'max_share_low'))
    over_lim = gp.param('env.foreground_salience', 'max_over_s')
    occ = biome.occupancy or (ecology.Occupancy.from_score(biome_score(rec)) if biome_score(rec) else None)
    rows, lv = [], []
    for f in fg:
        a, r = (np.concatenate(c) for c in carry[f.name])
        nfr = len(a) // fr
        ea = np.mean(a[:nfr * fr].reshape(nfr, fr) ** 2, axis=1)
        er = np.mean(r[:nfr * fr].reshape(nfr, fr) ** 2, axis=1)
        sal, over_s = [], 0.0
        for s, d in plan.get(f.name, []):
            i0, i1 = int(s / FRAME_S), min(nfr, max(int(s / FRAME_S) + 1, int((s + d) / FRAME_S)))
            if i0 >= nfr or i1 <= i0:
                continue
            S = 10 * np.log10((ea[i0:i1].mean() + 1e-30) / (er[i0:i1].mean() + 1e-30))
            sal.append(S)
            if S > mxs and occ is not None and occ.level(s + rec['t0'], s + rec['t0'] + d, *f.cfg['niche']['band_hz'], protected_only=True) > 0.3:
                over_s += d
        if not sal:
            continue
        low = float(np.mean([x < mn for x in sal]))
        lv.append('FAIL' if over_s > over_lim else 'WARN' if (low > share_low or max(sal) > mxs) else 'INFO')
        rows.append(f'{f.name}: {len(sal)} calls, median {np.median(sal):+.1f} dB over the biome\'s own band ({100 * low:.0f} % under {mn:g} dB, loudest {max(sal):+.1f} dB)')
    if not rows:
        _row(out, 'INFO', 'env.foreground_salience', f'{label}: the foreground animals make no call in the first {secs:.0f} s: not measured')
        return
    _row(out, _worst(lv), 'env.foreground_salience', f'{label}: ' + '; '.join(rows) + ('' if _worst(lv) == 'INFO' else '. Raise power_w or lower the beds in its band; move the call off the lead\'s band'))


_SCORES = {}


def biome_score(rec):
    return _SCORES.get(rec['track'])


def cpu_row(gp, rec, out, timer=time.perf_counter, probe_s=3.0):
    from biome import engine
    label = f'"{rec["track"]}"'
    b = engine.Biome(rec['preset'], seed=7)
    t = timer()
    b.render(probe_s)
    per_min = (timer() - t) / probe_s * 60.0
    mx, fl = gp.param('env.cpu_budget', 'max_s_per_min'), gp.param('env.cpu_budget', 'fail_s_per_min')
    lvl = 'FAIL' if per_min > fl else 'WARN' if per_min > mx else 'INFO'
    _row(out, lvl, 'env.cpu_budget', f'{label}: {per_min:.1f} s of CPU per minute of audio on this machine, projected from a {probe_s:g} s render (limit {mx:g})'
         + ('' if lvl == 'INFO' else '. Fewer oscillators, patches, individuals or emitters'))


# ------------------------------------------------------------------------------------------------ entry point
def rows(score, path=None, stems=None, project_dir=None, window_s=60.0, timer=time.perf_counter):
    """The env.* rows of every biome environment track of the score. Never raises: a row that cannot be measured says so."""
    gp = gate_profiles.resolve(score)
    wanted = [r for r in gate_profiles.ROWS if r.startswith('env.') and gp.on(r)]
    out = []
    recs = biome_tracks(score)
    if not recs or not wanted:
        return out
    for rec in recs:
        _SCORES[rec['track']] = score
        try:
            b = plan = plan_err = None
            if any(r in wanted for r in ('env.niche_collision', 'env.score_pocket', 'env.density_budget', 'env.ecology_rules')):
                try:
                    b = _biome(rec, score)
                    plan = bouts(b, rec['span'])
                except Exception as exc:                                   # an unbuildable preset is env.declaration's FAIL
                    plan_err = exc
            needs_plan = ('env.niche_collision', 'env.score_pocket', 'env.density_budget', 'env.ecology_rules')
            for rid, fn in (('env.declaration', lambda: declaration_row(gp, rec, out)),
                            ('env.medium_consistency', lambda: consistency_row(gp, rec, score, out)),
                            ('env.niche_collision', lambda: niche_row(gp, rec, b, plan, out)),
                            ('env.score_pocket', lambda: pocket_row(gp, rec, b, plan, score, out)),
                            ('env.density_budget', lambda: density_row(gp, rec, b, plan, out)),
                            ('env.ecology_rules', lambda: rules_row(gp, rec, b, plan, out)),
                            ('env.level_physical', lambda: level_row(gp, rec, out, min(window_s, 20.0))),
                            ('env.loop_stationarity', lambda: stationarity_row(gp, rec, out, min(window_s, 80.0))),
                            ('env.diffuse_field', lambda: diffuse_row(gp, rec, out, min(window_s, 20.0))),
                            ('env.foreground_salience', lambda: salience_row(gp, rec, _biome(rec, score), plan or bouts(_biome(rec, score), rec['span']), out, window_s)),
                            ('env.cpu_budget', lambda: cpu_row(gp, rec, out, timer))):
                if rid not in wanted:
                    continue
                if plan_err is not None and rid in needs_plan:
                    _row(out, 'INFO', rid, f'"{rec["track"]}": not measured ({type(plan_err).__name__}: {plan_err})')
                    continue
                try:
                    fn()
                except Exception as exc:                                   # one row's failure must not hide the others
                    _row(out, 'INFO', rid, f'"{rec["track"]}": not measured ({type(exc).__name__}: {exc})')
        finally:
            _SCORES.pop(rec['track'], None)
    return out
