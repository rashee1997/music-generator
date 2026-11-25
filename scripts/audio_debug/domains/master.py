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

    for r in [x for x in rows if margins.is_event_row(x) and x.get('level') == 'FAIL']:
        key = margins.row_key(r)          # its own key: this loop used to inherit the previous loop's row
        ev = margins.events(r)
        if not ev:
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
                         measured=[r['row'] for r in rows])
