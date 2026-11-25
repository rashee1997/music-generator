"""master.py - the full-mix rows: level, peak, impulses, silence, DC, ending.

The levers here are the ones a mastering stage owns: oversampling before the limiter, the true-peak ceiling and the
master trim. The rows are measured on the master, so a stem's share of an impulse is attributed with the stems'
high-frequency transient energy rather than assumed from the mix.
"""
from __future__ import annotations

from .. import catalog, margins
from . import base


def levers(case):
    """The mastering levers this project declares: oversampling, ceiling, loudness target, trim."""
    out = []
    mx = case.mix or {}
    rend = mx.get('render') or {}
    cur = float(rend.get('oversample') or 1)
    out.append(base.Lever('render.oversample', 'master', 'oversample', cur, 1, 8, 1, 'x',
                          'master oversampling before the limiter', burns=('clicks',)))
    mast = mx.get('mastering') or mx.get('master') or {}
    for key, kind, lo, hi, step, unit, text in (
            ('ceiling_dbtp', 'ceiling', -3.0, -0.1, 0.1, 'dBTP', 'true-peak ceiling'),
            ('target_lufs', 'lufs', -20.0, -8.0, 0.5, 'LUFS', 'integrated loudness target'),
            ('gain_db', 'gain', -6.0, 6.0, 0.1, 'dB', 'master trim')):
        if key in mast:
            out.append(base.Lever(f'master.{key}', 'master', kind, mast[key], lo, hi, step, unit, text,
                                  burns=('true peak', 'loudness', 'crest')))
    return out


def analyse(case, rows, history=()):
    lv_list = levers(case)
    coef, notes = {}, []
    for r in rows:
        key = margins.row_key(r)
        for lv in lv_list:
            if r['row'] in ('clicks', 'audio.clicks') and lv.kind == 'oversample':
                # Oversampling removes *alias* images, not a sample that starts on a step: measured on this gate, an
                # impulse that survived 4x is not an alias, so the marginal effect of more oversampling is not
                # first-order and is priced at zero instead of promising a click per doubling.
                coef[(key, lv.id)] = 0.0
            elif r['row'] in ('true peak', 'delivery.true_peak', 'clipping', 'clipped_samples', 'loudness',
                              'crest', 'crest_factor_db') and lv.kind in ('ceiling', 'gain', 'lufs'):
                coef[(key, lv.id)] = 1.0        # 1 dB of trim or ceiling moves a dB-scaled row by 1

    forensics, experiments = [], []
    for r in [x for x in rows if margins.is_event_row(x) and x.get('level') == 'FAIL']:
        key = margins.row_key(r)          # its own key: this loop used to inherit the previous loop's row
        ev = margins.events(r)
        if not ev:
            continue
        if r['row'] in ('clicks', 'audio.clicks') and _forensic_clicks(case, r, key, lv_list, coef, notes,
                                                                        forensics, experiments):
            continue
        scored = []
        for stem in case.stem_names():
            amp = max((base.energy_at(case, stem, t) for t, _m in ev), default=0.0)
            if amp > 0:
                scored.append((amp, stem))
        if not scored:
            # No stem cache (a run that stopped before mixing, or a cleaned cache): the score still says who plays at
            # that instant, so attribute by written onset instead of giving up on the row.
            for tr in case.score.get('tracks', []):
                # The nearest written onset, not an exact match: humanisation shifts a note tens of milliseconds and
                # the impulse sits on the attack, not on the beat.
                notes = tr.get('notes') or []
                if not notes:
                    continue
                near = min(notes, key=lambda n: abs(float(n.get('t', -9)) - ev[0][0]))
                gap = abs(float(near.get('t', -9)) - ev[0][0])
                if gap <= 0.06:            # an attack, not "a note somewhere nearby": 150 ms matched every bed too
                    scored.append((float(near.get('v', 0.5)) / (1.0 + 400.0 * gap), tr.get('name')))
            if scored:
                total = sum(a for a, _s in scored)
                top = [(s, a / total) for a, s in sorted(scored, reverse=True)[:3]]
                r['raw']['attribution'] = [{'stem': s, 'share': round(v, 3), 'method': 'score onset'}
                                           for s, v in top]
                notes.append(f"{r['row']}: no processed stems, so the owner is read from the score's written onsets at "
                             f"{ev[0][0]:.3f}s: " + ', '.join(f'{s} {100 * v:.0f}%' for s, v in top))
                n = float(r.get('value') or len(ev) or 0.0)
                for stem, share in top[:1]:
                    for lv in catalog.stem_levers(case, [dict(stem=stem)], domain='master'):
                        if lv.id not in [x.id for x in lv_list]:
                            lv_list.append(lv)
                        if lv.kind == 'onset':
                            coef[(key, lv.id)] = -share * n
                        elif lv.kind == 'eq':
                            band = catalog.band_share_for(case, lv, r)
                            if band:
                                coef[(key, lv.id)] = -share * n * band
                continue
            notes.append(f"{r['row']}: no processed stems and no written onset at that instant, so the impulse could "
                         f"not be attributed")
            continue
        scored.sort(reverse=True)
        total = sum(a for a, _s in scored)
        top = [(s, a / total) for a, s in scored[:3]]
        r['raw']['attribution'] = [{'stem': s, 'share': round(v, 3)} for s, v in top]
        notes.append(f"{r['row']} has {len(ev)} event(s) at "
                     + ', '.join(f'{t:.3f}s' for t, _m in ev[:4])
                     + '; the transient is ' + ', '.join(f'{s} {100 * v:.0f}%' for s, v in top))
        # Attribution is only worth having if it reaches a lever. The stem that owns the impulses contributes its own
        # onset and band levers here, one event per event it owns, so an impulse is never "closed" while the part that
        # makes it has a ramp or a band to move.
        n = float(r.get('value') or len(ev) or 0.0)
        for stem, share in top[:1]:
            for lv in catalog.stem_levers(case, [dict(stem=stem)], domain='master'):
                if lv.id not in [x.id for x in lv_list]:
                    lv_list.append(lv)
                if lv.kind == 'onset':
                    coef[(key, lv.id)] = -share * n            # a ramp on this stem removes the events it owns
                elif lv.kind == 'eq':
                    band = catalog.band_share_for(case, lv, r)
                    if band:
                        coef[(key, lv.id)] = -share * n * band
    return base.Analysis(rows=rows, levers=lv_list, coefficients=coef, notes=notes,
                         measured=[r['row'] for r in rows], forensics=forensics, experiments=experiments)


def _forensic_clicks(case, r, key, lv_list, coef, notes, forensics, experiments):
    """Attribute a click row by decomposing the master, price levers by replay. False when it cannot be done.

    The loudness-at-the-instant attribution this replaced named the loudest stem, which is not the stem that made the
    step; and its straight-line coefficient promised a fix for a row that is not a line. Here the owner is the stem
    whose mixed contribution to the step is large, and a lever's effect is what the gate's own checker says after the
    stem's band is scaled. Any failure falls back to the old path rather than losing the row.
    """
    if not case.master or not case.stem_names() or getattr(case, 'stale', False):
        return False
    try:
        from .. import forensics as fx
        mx = fx.mixdown(case)
        times = fx.events(case, r)
        recs = fx.explain_events(case, times, mx) if times else []
    except Exception as exc:                       # the autopsy never turns a diagnostic into a crash
        notes.append(f"{r['row']}: signal forensics unavailable ({type(exc).__name__}: {exc}); loudness attribution used")
        return False
    if not recs:
        return False
    # Owners: the stems that own a share of any event, strongest total first.
    weight = {}
    for e in recs:
        for o in e['owners']:
            weight[o['stem']] = weight.get(o['stem'], 0.0) + o['share']
    owners = [s for s, _w in sorted(weight.items(), key=lambda kv: -kv[1])]
    total = sum(weight.values()) or 1.0
    r['raw']['attribution'] = [{'stem': s, 'share': round(weight[s] / total, 3), 'method': 'master decomposition'}
                               for s in owners[:3]]
    r['raw']['forensics'] = recs
    forensics.extend(recs)
    base_value = int(r.get('value') or len(recs))
    check = fx.validate(case, r, mx)
    r['raw']['validation'] = check
    if check['ok']:
        notes.append(f"{r['row']}: sham replay (no change) reproduces the gate's {check['gate']} event(s) exactly "
                     f"(decomposition R^2 {check['r2']}); counterfactuals below are priced on a model that passes its own test")
    else:
        notes.append(f"{r['row']}: the sham replay does NOT reproduce the gate (model {check['sham']} vs gate {check['gate']}; "
                     f"missing at {check['missing'][:3]}, extra at {check['extra'][:3]}): every candidate below is "
                     f"UNVERIFIED and is shown for direction only")
    unverified = not check['ok']
    res_db = check.get('resolution_db', 3.0)
    notes.append(f"{r['row']}: model resolution {res_db:.1f} dB (90th percentile error of its steps against the master's); "
                 f"a candidate counts as proved only when it clears with at least that margin")
    results = fx.search(case, owners, base_value, mx)
    r['raw']['replay'] = results
    notes.extend(fx.as_notes(recs, results, mx))
    for e in recs:
        if e['kind'] == 'discontinuity':
            notes.append(f"{r['row']} at {e['t']:.3f}s is a true discontinuity (raw step {e['raw_step_fs']:.2f} FS): "
                         f"the cause is a sample start or a cut, not a band level; a shelf cannot move it")
    stem_owners = {o.split('/', 1)[0] for o in owners}
    levers = [lv for lv in catalog.hf_levers(case, 'master', only_stems=stem_owners - {o.split('/', 1)[0]
                                                                                    for o in owners if '/' in o})
              + catalog.layer_levers(case, 'master', only=set(owners))
              if lv.id not in {x.id for x in lv_list}]
    lv_list.extend(levers)
    for lv in levers:
        skey = lv.id[len('layer.'):].replace('.', '/', 1) if lv.kind == 'layer_gain' else lv.stem
        slope = fx.monotone_slope(results, skey)
        # events per dB of gain: the response measured by replay, or zero when it is not a line (a floor effect)
        coef[(key, lv.id)] = 0.0 if slope is None else float(slope)
        if slope is None and any(list(x['moves']) == [skey] for x in results):
            notes.append(f"{r['row']}: cutting the band of {skey} is NOT monotone (replay: "
                         + ', '.join(f"{db:+.0f} dB -> {x['value']} event(s)" for x in results
                                     for db in x['moves'].values() if list(x['moves']) == [skey])
                         + f" against {base_value} now): its highs set the floor the threshold is taken against, so the "
                         f"lever is priced at zero and the cut belongs on the part that makes the transient")
    try:        # the closed loop: cut, re-explain, repeat, so a cut that exposes the next owner is planned for
        deep = fx.plan_clicks(case, mx)
    except Exception as exc:
        deep = None
        notes.append(f"{r['row']}: iterative replay unavailable ({type(exc).__name__}: {exc})")
    if deep and deep['moves'] and deep['profile'] < deep['start']:
        prof = deep['profile']
        margin = float(sum(1 for c in prof if c == 0) - 1) if prof[0] == 0 else None
        # the margin is the deepest tightening that still reads clean (0 dB, 1, 2 or 3 dB tighter than the gate)
        mg = None if prof[0] != 0 else float(max([i for i, c in enumerate(prof) if c == 0 and all(z == 0 for z in prof[:i + 1])] or [0]))
        notes.append(f"{r['row']}: iterative replay, profile (events at 0/1/2/3 dB tighter) {deep['start']} -> {prof} after "
                     + ', '.join(f"{k} {v:+.0f} dB" for k, v in deep['moves'].items()))
        experiments.append(dict(row=r['row'], key=key, kind='iterative', value=int(prof[0]), baseline=base_value, near3=int(sum(prof)),
                                margin_db=mg, unverified=unverified, resolution_db=res_db, times=[], verdict='clears' if prof[0] == 0 else 'better',
                                moves={(f"layer.{s_.replace('/', '.', 1)}" if '/' in s_ else f'hf.{s_}'): v
                                       for s_, v in deep['moves'].items()}))

    for x in results:
        if x['verdict'] in ('clears', 'better'):
            experiments.append(dict(row=r['row'], key=key, kind='hf_shelf', value=x['value'], baseline=base_value,
                                    margin_db=x.get('margin_db'), unverified=unverified, resolution_db=res_db,
                                    moves={(f"layer.{s.replace('/', '.', 1)}" if '/' in s else f'hf.{s}'): db
                                           for s, db in x['moves'].items()}, times=x['times'],
                                    verdict=x['verdict']))
    return True
