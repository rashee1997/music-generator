# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_rows.py - the chem.* gate rows: does the piece's arc contain the events that make a listener want the next
moment, feel the arrival and come down, and does that arc answer the mood and the genre the piece declared?

Ten rows, all INFO or WARN, never FAIL (docs/NEUROCHEMICAL-AFFECT-PLAN.md section 4; the chills model that comes
closest to this reaches AUC 0.56-0.60, and 5-10 % of listeners are music-anhedonic, so a piece cannot be failed for a
predicted feeling):

    chem.model            the presets validated, and what the layer is made of
    chem.reward_build     the anticipation pool earns the arrival instead of the piece just getting louder
    chem.reward_arrival   there is a consummation event, at the declared hit, with a real change in it
    chem.stress_load      tension is carried and then resolved, not accumulated
    chem.affiliation      there is something voice-like to bond with
    chem.motor_drive      the body has a pulse to lock to, inside the Witek window
    chem.recovery         the piece comes down, or declares that it will not
    chem.arc_variety      the piece is more than one chemical state
    chem.mood_connection  the signature answers the mood the sheet declares (chem/moods.json)
    chem.genre_connection the signature answers the genre the score declares (chem/genres.json)

Every detail names the confidence tier and the inputs that were actually measured. Remediation names a lever in the
score or the presets, never a threshold.
"""
import os

import chem_model
import chem_model.config as config
import chem_model.targets as targets
import gate_profiles

ROW_IDS = chem_model.ROW_IDS


def _add(out, level, name, detail):
    out.append((level, name, detail))


def _tiers(cfg):
    return ', '.join(f'{p} {cfg["pools"][p]["tier"]}' for p in config.POOLS)


def _inputs(measured, need):
    have = [k for k in need if measured.get(k)]
    miss = [k for k in need if not measured.get(k)]
    said = f'inputs: {", ".join(have) if have else "none"}'
    if miss:
        said += f'; not measured: {", ".join(miss)}'
    return said


def _lever(rep, dim):
    return rep['model']['levers'].get(dim, '')


def model_row(problems, rep, out):
    if problems:
        _add(out, 'WARN', 'chem.model',
             'the chem presets did not validate: ' + '; '.join(problems[:3])
             + (' ...' if len(problems) > 3 else '')
             + '. The other chem rows report only what they could still measure; fix references/data/presets/chem/ first')
        return
    cfg = rep['model']
    _add(out, 'INFO', 'chem.model',
         f'{len(config.POOLS)} inferred pools at {cfg["step_s"]:g} s steps, tiers {_tiers(cfg)}; every constant is a '
         f'starting value and no chem row can FAIL. A row says the arc contains (or lacks) the elicitors of a reward '
         f'cycle: anticipation, consummation, load, warmth, drive, recovery. It does not say a listener will feel '
         f'anything (docs/NEUROCHEMICAL-AFFECT-PLAN.md)')


def build_row(gp, rep, out):
    b = rep['observables']['build']
    lead_min = float(gp.param('chem.reward_build', 'min_lead_s'))
    rho_min = float(gp.param('chem.reward_build', 'min_rho'))
    peak_min = float(gp.param('chem.reward_build', 'min_peak'))
    where = (f'the declared hit at {b["at_s"]:.1f} s' if b['at_s'] is not None and b['declared']
             else f'the strongest measured change at {b["at_s"]:.1f} s (the sheet declares no hits_at)')
    bad = []
    if not b.get('event', True):
        bad.append(f'there is no measurable change at {where} to build towards (the change measures below the event '
                   f'floor), so the anticipation has nothing to earn')
    elif b['lead_s'] < lead_min:
        bad.append(f'anticipation reaches half its peak only {b["lead_s"]:.1f} s before {where} (want {lead_min:g} s)')
    if b.get('event', True) and b['rho'] < rho_min:
        bad.append(f'it rises through the lead-up at rank correlation {b["rho"]:+.2f} (want {rho_min:+.2f})')
    if b['peak'] < peak_min:
        bad.append(f'it peaks at {b["peak"]:.2f} (want {peak_min:g})')
    said = ('; '.join(bad) + f'. {b["lead_s"]:.1f} s lead, peak {b["peak"]:.2f}. Lever: ' + _lever(rep, 'reward_build')
            if bad else
            f'the build earns {where}: {b["lead_s"]:.1f} s of lead, rank correlation {b["rho"]:+.2f}, peak '
            f'{b["peak"]:.2f}')
    _add(out, 'WARN' if bad else 'INFO', 'chem.reward_build',
         f'{said}. Tier B (inferred from expectation and proximity, not assayed); '
         f'{_inputs(rep["features"]["measured"], ("build", "proximity", "tension", "uncertainty"))}')


def arrival_row(gp, rep, out):
    a = rep['observables']['arrival']
    peak_min = float(gp.param('chem.reward_arrival', 'min_peak'))
    off_max = float(gp.param('chem.reward_arrival', 'max_offset_s'))
    con_min = float(gp.param('chem.reward_arrival', 'min_contrast_db'))
    bad, notes = [], []
    if a['peak'] < peak_min:
        bad.append(f'the consummation pool peaks at {a["peak"]:.2f} at {a["at_s"]:.1f} s (want {peak_min:g})')
    if a['declared'] and a['offset_s'] is not None and a['offset_s'] > off_max:
        bad.append(f'the peak is {a["offset_s"]:.1f} s from the declared hit (want {off_max:g} s or less)')
    if a['contrast_db'] is not None and a['contrast_db'] < con_min:
        bad.append(f'the hit changes the level by {a["contrast_db"]:+.1f} dB (want {con_min:g})')
    if a['contrast_db'] is None:
        notes.append('no level contrast was measured (no rendered audio)')
    if not a['declared']:
        notes.append('the sheet declares no hit, so only the peak was judged')
    tail = ('. Lever: ' + _lever(rep, 'reward_arrival')) if bad else ''
    _add(out, 'WARN' if bad else 'INFO', 'chem.reward_arrival',
         f'{"; ".join(bad) if bad else "a consummation event lands at %.1f s with peak %.2f" % (a["at_s"], a["peak"])}'
         f'{tail}. Tier B (Salimpoor 2011 measured ventral-striatal release at the peak; the model only infers it); '
         f'{_inputs(rep["features"]["measured"], ("arrival", "surprise", "low_end", "vocal", "fatigue"))}'
         + (''.join(f'. {n}' for n in notes)))


def stress_row(gp, rep, out):
    s = rep['observables']['stress']
    load_max = float(gp.param('chem.stress_load', 'max_mean_load'))
    unr_max = float(gp.param('chem.stress_load', 'max_unresolved_s'))
    res_min = float(gp.param('chem.stress_load', 'min_resolve_frac'))
    bad = []
    if s['mean_load'] > load_max:
        bad.append(f'the load averages {s["mean_load"]:.2f} over the piece (want {load_max:g} or less)')
    if s['unresolved_s'] > unr_max:
        bad.append(f'{s["unresolved_s"]:.1f} s of it is carried with no fall inside the settle window (want {unr_max:g} s)')
    if s['resolve_frac'] < res_min:
        bad.append(f'only {s["resolve_frac"]:.0%} of its peaks resolve (want {res_min:.0%})')
    said = ('; '.join(bad) + '. Lever: ' + _lever(rep, 'stress_load')) if bad else (
        f'tension is carried and released: load averages {s["mean_load"]:.2f}, {s["unresolved_s"]:.1f} s unresolved, '
        f'{s["resolve_frac"]:.0%} of peaks resolve')
    level = 'WARN' if bad else 'INFO'
    tail = ''
    if bad and 'tense' in gp.flags:
        level = 'INFO'
        tail = ('. The profile declares a type that carries its tension to the last bar, so an unresolved peak is the '
                'brief here and not a fault; the load integral still stands')
    _add(out, level, 'chem.stress_load',
         f'{said}. Tier C (stress is a proxy: de Witte 2019 found d = 0.35 hormonal across 104 trials, and context '
         f'dominates); {_inputs(rep["features"]["measured"], ("tension", "roughness", "surprise", "consonance"))}{tail}')


def affiliation_row(gp, rep, out):
    a = rep['observables']['affiliation']
    mean_min = float(gp.param('chem.affiliation', 'min_mean'))
    leg_min = float(gp.param('chem.affiliation', 'min_legato'))
    bad = []
    if a['mean'] < mean_min:
        bad.append(f'warmth averages {a["mean"]:.2f} (want {mean_min:g})')
    if a['figure'] and a['legato'] < leg_min:
        bad.append(f'only {a["legato"]:.0%} of the sounding figure is legato or held (want {leg_min:.0%})')
    said = ('; '.join(bad) + '. Lever: ' + _lever(rep, 'affiliation')) if bad else (
        f'warmth averages {a["mean"]:.2f}, the figure is legato/held {a["legato"]:.0%} of its sounding time and a voice '
        f'is present {a["vocal"]:.0%} of the piece')
    no_figure = '; no figure (melody/lead/vocal) to test for legato' if not a['figure'] else ''
    _add(out, 'WARN' if bad else 'INFO', 'chem.affiliation',
         f'{said}. Tier C (peripheral oxytocin assays disagree: Ooishi 2017 raised it, group singing lowered it); '
         f'{_inputs(rep["features"]["measured"], ("legato", "vocal", "consonance", "slow_tempo", "pulse"))}{no_figure}')


def motor_row(gp, rep, out):
    m = rep['observables']['motor']
    lo = float(gp.param('chem.motor_drive', 'bsi_lo'))
    hi = float(gp.param('chem.motor_drive', 'bsi_hi'))
    pulse_min = float(gp.param('chem.motor_drive', 'min_pulse'))
    mean_min = float(gp.param('chem.motor_drive', 'min_mean'))
    bad, notes = [], []
    if m['mean'] < mean_min:
        bad.append(f'the drive pool averages {m["mean"]:.2f} (want {mean_min:g})')
    if m['bsi'] is None:
        notes.append('no drum/bass/arp cell to score a syncopation index from')
    elif not (lo <= float(m['bsi']) <= hi):
        bad.append(f'bar syncopation {m["bsi"]:.2f} is outside the {lo:g}-{hi:g} window (Witek 2014 inverted U)')
    if not rep['features']['measured'].get('pulse'):
        notes.append('pulse clarity was not measured (no rendered audio)')
    elif m['pulse'] < pulse_min:
        bad.append(f'measured pulse clarity {m["pulse"]:.2f} (want {pulse_min:g})')
    said = ('; '.join(bad) + '. Lever: ' + _lever(rep, 'motor_drive')) if bad else (
        f'the body has a pulse: drive averages {m["mean"]:.2f}, pulse clarity {m["pulse"]:.2f}'
        + (f', bar syncopation {m["bsi"]:.2f}' if m['bsi'] is not None else ''))
    _add(out, 'WARN' if bad else 'INFO', 'chem.motor_drive',
         f'{said}. Tier C (effort and entrainment read from a pain-threshold proxy: Tarr 2015, Pearce 2016); '
         f'{_inputs(rep["features"]["measured"], ("pulse", "low_end", "density", "slow_tempo"))}'
         + (''.join(f'. {n}' for n in notes)))


def recovery_row(gp, rep, out):
    r = rep['observables']['recovery']
    drop_min = float(gp.param('chem.recovery', 'min_drop_frac'))
    cort_max = float(gp.param('chem.recovery', 'max_final_cort'))
    bad = []
    if r['drop_frac'] < drop_min:
        bad.append(f'the piece ends {r["drop_frac"]:.0%} below its peak instead of coming down (want {drop_min:.0%})')
    if r['final_cort'] > cort_max:
        bad.append(f'the load ends at {r["final_cort"]:.2f} (want {cort_max:g} or less)')
    said = ('; '.join(bad) + '. Lever: ' + _lever(rep, 'recovery')) if bad else (
        f'the piece comes down: {r["drop_frac"]:.0%} below its peak, load ends at {r["final_cort"]:.2f}, arousal at '
        f'{r["final_ne"]:.2f}')
    level, tail = ('WARN', '') if bad else ('INFO', '')
    if bad and 'tense' in gp.flags:
        level = 'INFO'
        tail = '. The profile declares a type that ends on its peak (a cliff), so no come-down was asked for'
    _add(out, level, 'chem.recovery',
         f'{said}. Tier C (recovery from listening alone is weak: g = 0.15, CI -0.21..0.52, n.s., 2022 meta-analysis); '
         f'{_inputs(rep["features"]["measured"], ("recovery", "consonance", "legato", "tension"))}{tail}')


def variety_row(gp, rep, out):
    v = rep['observables']['variety']
    states_min = int(gp.param('chem.arc_variety', 'min_states'))
    flat_max = float(gp.param('chem.arc_variety', 'max_flat_share'))
    arr_max = float(gp.param('chem.arc_variety', 'max_arrivals_per_min'))
    bad = []
    if v['states'] < states_min:
        bad.append(f'only {v["states"]} of {v["of"]} pools move (want {states_min})')
    if v['flat_share'] > flat_max:
        bad.append(f'{v["flat_share"]:.0%} of the piece is one chemical state (want {flat_max:.0%} or less)')
    if v['arrivals_per_min'] > arr_max:
        bad.append(f'{v["arrivals_per_min"]:.2f} arrivals per minute (want {arr_max:g} or fewer: a repeat spends the '
                   f'pool and reads as flat)')
    said = ('; '.join(bad) + '. Lever: ' + _lever(rep, 'arc_variety')) if bad else (
        f'{v["states"]} of {v["of"]} pools move, {v["flat_share"]:.0%} of the piece is flat, '
        f'{v["arrivals_per_min"]:.2f} arrivals per minute')
    _add(out, 'WARN' if bad else 'INFO', 'chem.arc_variety',
         f'{said}. Reads the traced pools, not the listener; a second identical arrival releases less because the '
         f'availability pool is spent (the anti-cliche term in chem/model.json)')


def mood_row(gp, rep, out):
    m = rep['mood']
    limit = float(gp.param('chem.mood_connection', 'max_distance'))
    if not m.get('known'):
        _add(out, 'INFO', 'chem.mood_connection',
             f'not measured: {m.get("why")}. Declare intent.emotions in the direction sheet (or meta.emotion in the '
             f'score) so the signature can be compared with a mood target')
        return
    dist, diffs = targets.distance(rep['dims'], m['target'], m.get('excess_weight', 0.5))
    worst = sorted(diffs, key=lambda d: -abs(d[3]))[:2]
    bad = []
    if dist is None:
        _add(out, 'INFO', 'chem.mood_connection', 'not measured: the mood target has no dimensions')
        return
    words = '/'.join(m['ids'])
    if dist > limit:
        bad = [f'the measured signature is {dist:.2f} from what {words} asks for (limit {limit:g})']
    asked = ', '.join(f'{d} {w:.2f}' for d, w in m['target'].items())
    got = ', '.join(f'{d} {g:.2f}' for d, g, _w, _x in diffs)
    tail = ''
    if bad:
        lead = worst[0]
        tail = (f'. Furthest: {lead[0]} {lead[1]:.2f} given vs {lead[2]:.2f} asked'
                + (f'; {worst[1][0]} {worst[1][1]:.2f} vs {worst[1][2]:.2f}' if len(worst) > 1 else '')
                + f'. Lever: {_lever(rep, lead[0])}')
    said = bad[0] if bad else f'the signature answers {words} within {dist:.2f}'
    _add(out, 'WARN' if bad else 'INFO', 'chem.mood_connection',
         f'{said}'
         f'{tail}. Asked: {asked}. Measured: {got}. Target built from {m["why"]} (chem/moods.json); tier C '
         f'(inferred, and individual differences dominate)')


def genre_row(gp, rep, out):
    g = rep['genre']
    got = rep['dims']
    if not g.get('constraints'):
        _add(out, 'INFO', 'chem.genre_connection',
             f'genre "{g["genre"] or "undeclared"}" maps to the "{g["family"]}" family, which sets no constraint: the '
             f'signature is reported by the rows above. Declare meta.genre, or add the genre to chem/genres.json')
        return
    breaks = targets.breaches(got, g)
    asked = ', '.join(f'{d} {"min" if "min" in lim else "max"} {list(lim.values())[0]:g}'
                      for d, lim in g['constraints'].items())
    if breaks:
        said = '; '.join(f'{d} {val:.2f} {"below" if kind == "min" else "above"} the {kind} {lim:g}'
                         for d, val, kind, lim in breaks)
        tail = '. Lever: ' + _lever(rep, breaks[0][0])
        level = 'WARN'
    else:
        said = f'genre "{g["genre"]}" ({g["family"]} family) is answered'
        tail = ''
        level = 'INFO'
    _add(out, level, 'chem.genre_connection',
         f'{said}. Asked: {asked} (tolerance {g["tolerance"]:g}); measured: '
         f'{", ".join(f"{d} {got[d]:.2f}" for d in g["constraints"])}{tail}. Family reason: {g["why"]}. '
         f'Tier C (the signature is inferred; chem/genres.json)')


def report_rows(rep, gp, problems=None, wanted=None):
    """The rows for a finished evaluation. `wanted` limits them to the rows this profile applies."""
    problems = problems if problems is not None else []
    out = []
    want = set(wanted or ROW_IDS)
    if 'chem.model' in want:
        model_row(problems, rep, out)
    if problems:
        for rid in [r for r in ROW_IDS if r in want and r != 'chem.model']:
            _add(out, 'INFO', rid, 'not measured: the chem presets did not validate, so the model did not run '
                                   '(see chem.model)')
        return out
    if 'chem.reward_build' in want:
        build_row(gp, rep, out)
    if 'chem.reward_arrival' in want:
        arrival_row(gp, rep, out)
    if 'chem.stress_load' in want:
        stress_row(gp, rep, out)
    if 'chem.affiliation' in want:
        affiliation_row(gp, rep, out)
    if 'chem.motor_drive' in want:
        motor_row(gp, rep, out)
    if 'chem.recovery' in want:
        recovery_row(gp, rep, out)
    if 'chem.arc_variety' in want:
        variety_row(gp, rep, out)
    if 'chem.mood_connection' in want:
        mood_row(gp, rep, out)
    if 'chem.genre_connection' in want:
        genre_row(gp, rep, out)
    return out


def rows(score, path, stems=None, summary=None, project_dir=None):
    """The chem rows for a rendered piece: score, its direction sheet, the master and the ear summary.

    `stems` is accepted so the caller can pass it beside the ear rows; the chem model reads the master, not the stems.
    Nothing here raises: a preset or a read failure is a row that names it.
    """
    gp = gate_profiles.resolve(score)
    want = [r for r in ROW_IDS if gp.on(r)]
    if not want:
        return []
    sheet = {}
    if project_dir:
        try:
            import quality_gate
            sheet = quality_gate._direction_sheet(project_dir) or {}
        except Exception:
            sheet = {}
    problems = config.problems()
    try:
        rep = chem_model.evaluate(score, path if path and os.path.isfile(path) else None, sheet, summary, gp)
    except Exception as exc:
        return [('INFO', r, f'not measured: the chem model did not run ({type(exc).__name__}: {exc})') for r in want]
    return report_rows(rep, gp, problems, want)
