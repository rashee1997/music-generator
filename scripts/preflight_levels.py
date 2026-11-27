# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""preflight_levels.py - what the score says about loudness, tempo and dissonance, before any audio is made.

The audio rows `stem.dead`, `section.energy`, `tempo.audio` and `roughness` each cost a render to find. Their causes are
in the notes: a part whose velocity and dynamics curve are both low in a section, a declared energy order the notes do
not follow, a tempo map no single tempo describes, two instruments holding a second apart. These rows read the score
only. They are estimates with starting-value limits, they warn and never fail, and they do not replace the audio rows.

Rows
    preflight.stem_level  WARN  a part plays a section at under 75 % of its usual velocity while the dynamics curve is also under 75 % of its usual
    preflight.arc         WARN  the number of parts playing, weighted by velocity and the curve, does not follow the declared section energy
    preflight.tempo       WARN  the tempo map spans more than 25 %: the beat tracker will read a subdivision or another tempo
    preflight.roughness   WARN  two different instruments hold notes one or two semitones apart for three beats or more (Plomp and Levelt 1965)
"""
import math

import numpy as np

STACK_RATIO = 0.75           # velocity share and curve share under which a quiet section is quiet twice
ARC_MIN_RHO = 0.5            # the same limit the audio row section.energy fails at
TEMPO_SPAN = 0.25            # (max - min) / mean of the tempo map
CLASH_MIN_BEATS = 3.0
CLASH_MAX_SEMITONES = 2
SKIP_ROLES = ('fx', 'environment', 'drum', 'percussion', 'texture')


def _sections(score):
    ts = score.get('ts') or [4, 4]
    bpb = float(ts[0]) * 4.0 / float(ts[1])
    out = []
    for s in (score.get('plan') or {}).get('sections') or []:
        if 'start_bar' in s and 'end_bar' in s:
            out.append(dict(name=str(s.get('name', '?')), a=(float(s['start_bar']) - 1) * bpb, b=float(s['end_bar']) * bpb,
                            energy=s.get('energy')))
    return out


def _curve(score):
    pts = sorted((float(b), float(v)) for b, v in (score.get('dynamics') or []))
    if len(pts) < 2:
        return lambda beat: 1.0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return lambda beat: float(np.interp(beat, xs, ys))


def _tracks(score, skip=SKIP_ROLES):
    return [t for t in score.get('tracks') or [] if t.get('notes') and str(t.get('role')) not in skip
            and not str(t.get('instrument', '')).startswith(('env:', 'sfx:'))]


def _in(sec, n):
    return sec['a'] <= float(n['t']) < sec['b']


def stem_level_rows(score):
    secs, curve = _sections(score), _curve(score)
    if len(secs) < 2:
        return [('INFO', 'preflight.stem_level', 'fewer than two sections: not checked')]
    bad = []
    for t in _tracks(score):
        per = []
        for s in secs:
            ns = [n for n in t['notes'] if _in(s, n)]
            if ns:
                v = float(np.mean([float(n.get('v', 0.7)) for n in ns]))
                c = float(np.mean([curve(float(n['t'])) for n in ns]))
                per.append((s['name'], v, c))
        if len(per) < 2:
            continue
        vm, cm = float(np.median([p[1] for p in per])), float(np.median([p[2] for p in per]))
        for name, v, c in per:
            if vm > 0 and cm > 0 and v / vm < STACK_RATIO and c / cm < STACK_RATIO:
                bad.append((t['name'], name, v / vm, c / cm))
    if not bad:
        return [('PASS', 'preflight.stem_level', 'no part is quiet twice (velocity and curve) in any section it plays')]
    n, sec, rv, rc = bad[0]
    return [('WARN', 'preflight.stem_level', f'{len(bad)} part/section pair(s) play at under {int(STACK_RATIO * 100)} % of the usual velocity while the dynamics curve '
             f'is also under {int(STACK_RATIO * 100)} % of its usual value, e.g. "{n}" in {sec} (velocity {rv:.2f}, curve {rc:.2f}): the stem gate '
             'reads that as a part that dropped out (stem.dead). Raise the velocity there or lift the curve')]


def arc_rows(score):
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'helpers'))
    import expression_report as er
    secs, curve = _sections(score), _curve(score)
    secs = [s for s in secs if s.get('energy') is not None]
    if len(secs) < 3:
        return [('INFO', 'preflight.arc', 'fewer than three sections with a declared energy: not checked')]
    tracks = _tracks(score, skip=('fx', 'environment'))
    power = []
    for s in secs:
        total = 0.0
        for t in tracks:
            ns = [n for n in t['notes'] if _in(s, n)]
            if not ns:
                continue
            play = sum(float(n.get('d') or 0.0) for n in ns) / max(1e-6, s['b'] - s['a'])
            v = float(np.mean([float(n.get('v', 0.7)) for n in ns]))
            c = float(np.mean([curve(float(n['t'])) for n in ns]))
            total += min(1.0, play) * (v * c) ** 2
        power.append(10.0 * math.log10(total + 1e-9))
    rho = er.spearman([float(s['energy']) for s in secs], power)
    if rho is None:
        return [('INFO', 'preflight.arc', 'the declared energy or the predicted level does not vary: nothing to rank')]
    # the same limit the audio row fails at, read from the row instead of restated here
    try:
        import gate_profiles
        need = float(gate_profiles.resolve(score).param('section.energy', 'fail_rho'))
    except Exception:
        need = ARC_MIN_RHO
    if rho < need:
        order = ', '.join(f'{s["name"]} {p:.0f}' for s, p in zip(secs, power))
        return [('WARN', 'preflight.arc', f'predicted section level (parts playing x velocity x curve) follows the declared energy with rank correlation {rho:+.2f} '
                 f'(< {need:g}); the audio row section.energy fails below that. Predicted dB by section: {order}')]
    return [('PASS', 'preflight.arc', f'predicted section level follows the declared energy (rank correlation {rho:+.2f})')]


def tempo_rows(score):
    pts = [float(v) for _, v in (score.get('tempo_points') or [])]
    if len(pts) < 2:
        return [('PASS', 'preflight.tempo', 'a single tempo: tempo.audio has one value to measure')]
    span = (max(pts) - min(pts)) / (sum(pts) / len(pts))
    skip = ((score.get('gate') or {}).get('tempo.audio') or {}).get('mode') == 'skip'
    if span > TEMPO_SPAN and not skip:
        return [('WARN', 'preflight.tempo', f'the tempo map spans {100 * span:.0f} % ({min(pts):g}-{max(pts):g} BPM): the beat tracker will read a subdivision or another tempo, '
                 'and tempo.audio fails against any one declared value. Render once, measure it, and record a measured skip with its reason in the score `gate`')]
    return [('PASS', 'preflight.tempo', f'the tempo map spans {100 * span:.0f} %' + (' and tempo.audio is skipped with a reason' if skip else ''))]


def roughness_rows(score):
    pads = _tracks(score)
    found = []
    for i, a in enumerate(pads):
        for b in pads[i + 1:]:
            if str(a['name']).split('_')[0] == str(b['name']).split('_')[0]:
                continue
            for na in a['notes']:
                da = float(na.get('d') or 0.0)
                if da < CLASH_MIN_BEATS:
                    continue
                for nb in b['notes']:
                    gap = abs(int(na['p']) - int(nb['p']))
                    if not 1 <= gap <= CLASH_MAX_SEMITONES or float(nb.get('d') or 0.0) < CLASH_MIN_BEATS:
                        continue
                    ov = min(float(na['t']) + da, float(nb['t']) + float(nb['d'])) - max(float(na['t']), float(nb['t']))
                    if ov >= CLASH_MIN_BEATS:
                        found.append((ov, a['name'], b['name'], int(na['p']), int(nb['p']), float(max(na['t'], nb['t']))))
    if not found:
        return [('PASS', 'preflight.roughness', 'no two instruments hold a second against each other for three beats or more')]
    found.sort(reverse=True)
    ov, a, b, pa, pb, t = found[0]
    return [('WARN', 'preflight.roughness', f'{len(found)} sustained second(s) between different instruments, longest "{a}" ({pa}) against "{b}" ({pb}) for {ov:g} beats '
             f'(from beat {t:g}): within a critical band the partials beat (Plomp and Levelt 1965) and the audio row roughness fails once the texture is thin. '
             'Move one part a third or more, or shorten the overlap')]


def checks(score):
    return stem_level_rows(score) + arc_rows(score) + tempo_rows(score) + roughness_rows(score)
