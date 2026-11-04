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

#!/usr/bin/env python3
"""quality_gate.py - the checks a piece must pass before it is called finished.

    python3 scripts/quality_gate.py score.json rendered.wav   # score checks, render checks, audio checks
    python3 scripts/quality_gate.py score.json                # renders to <score>_gate.wav first
    python3 scripts/quality_gate.py --selftest                # the renderer's pitch-bend range and channel rules

Exit code 1 on any FAIL. The gate measures faults that code can see: copy-paste bars, glides and bends the synth cannot
play, shared channels, clipping, missed loudness, silent gaps, clicks, flat dynamics, breathless winds and bows.
It cannot judge phrasing, taste or cultural correctness: listen (listen.py, earshot) and check the direction sheet.
A PASS means the measurable faults are absent. It does not mean the music is natural.
Research behind these checks: references/quality-gate.md."""
import argparse
import json
import os
import sys

import numpy as np
try:
    from scipy.ndimage import median_filter
except Exception:
    median_filter = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturalness_check as nc
import pattern_audit
import render_natural as rn

# instruments that need breath or bow room between phrases (the KB's "ma" rule)
WIND = {'flute', 'bansuri', 'shakuhachi', 'ney', 'mizmar', 'shehnai', 'dizi', 'recorder', 'horn', 'french_horn', 'trumpet',
        'saxophone', 'alto_sax', 'tenor_sax', 'clarinet', 'oboe', 'bassoon', 'trombone', 'tuba', 'harmonica', 'accordion'}
GAP_BEATS = 0.08          # a breath or bow gap is at least this long
WINDOW_BARS = 4
CLICK_STEP = 0.5          # one-sample jump, full scale: no real note rises this fast; a sample that starts mid-wave does


def find_clicks(mono, quiet=220):
    """Isolated single-sample jumps: a jump of more than CLICK_STEP in one or two samples, with no other jump within
    `quiet` samples (5 ms at 44.1 kHz). A dense cluster of jumps is loud high-frequency content (cymbal, shaker,
    crash), not a click. A second-difference test was tried first and flagged 841 spikes in the desert sample, most of
    them real attacks."""
    idx = np.flatnonzero(np.abs(np.diff(mono)) > CLICK_STEP)
    if not len(idx):
        return idx
    groups = np.split(idx, np.flatnonzero(np.diff(idx) > 2) + 1)
    out = []
    for i, g in enumerate(groups):
        if len(g) > 2:
            continue
        before = groups[i - 1][-1] if i else -10 ** 9
        after = groups[i + 1][0] if i + 1 < len(groups) else 10 ** 12
        if g[0] - before > quiet and after - g[-1] > quiet:
            out.append(g[0])
    return np.array(out, dtype=int)


def _row(out, level, name, detail):
    out.append((level, name, detail))


def mix_preset_row(score, out):
    """Every piece gets its own mix preset ("mix_preset": "<name>", kind 'mix'), written for that piece's musical character.
    FAIL when it is missing, is 'default', does not exist, or differs from the default in nothing but its name."""
    import presets
    if not presets.PROJECT_ROOTS:
        return          # a scratch cue has no project folder to hold a per-piece mix preset; project mode demands one
    name = score.get('mix_preset')
    if not name or name == 'default':
        _row(out, 'FAIL', 'mix_preset', 'score has no custom "mix_preset". Create one: python scripts/presets.py scaffold mix <name>, '
             'set its values for this music (references/blending-and-balance.md section "Mix preset"), then add "mix_preset": "<name>" to the score')
        return
    try:
        mine = presets.get('mix', name)
    except KeyError as e:
        _row(out, 'FAIL', 'mix_preset', str(e))
        return
    base = presets.mix()
    changed = [k for k, v in mine.items() if k not in ('name', '_source', 'description', 'character') and base.get(k) != v]
    if not mine.get('character'):
        _row(out, 'FAIL', 'mix_preset', f'"{name}" has no "character" line: say in one sentence what this music is and why the mix is set this way')
    elif not changed:
        _row(out, 'FAIL', 'mix_preset', f'"{name}" is a copy of the default mix: change at least one value for this music')
    else:
        _row(out, 'PASS', 'mix_preset', f'"{name}" customises {len(changed)} mix value(s): {", ".join(sorted(changed)[:6])}')


def score_checks(score, out):
    """Structure and musical checks on the score itself (no audio)."""
    bb = score.get('ts', [4, 4])[0]
    import gate_profiles
    gp = gate_profiles.resolve(score)
    out.extend(gp.notes())                       # the chosen piece type, and every relaxed or skipped row with its reason
    mix_preset_row(score, out)
    for t in score['tracks']:
        if t.get('role') == 'environment' or t.get('instrument') == 'environment' or t.get('is_environment') or str(t.get('instrument', '')).startswith('env:'):
            continue
        ns = t.get('notes', [])
        if not ns:
            _row(out, 'FAIL', t.get('name', '?'), 'track has no notes')
            continue
        bad = [n for n in ns if (isinstance(n['p'], (int, float)) and not 0 <= n['p'] <= 127)   # drums carry a name, not a pitch
               or n.get('d', 0) <= 0 or not np.isfinite(n['t'])]
        if bad:
            _row(out, 'FAIL', t['name'], f'{len(bad)} note(s) with a pitch outside 0-127, a zero length or a bad time')
        wide = [n for n in ns if abs(n.get('gl', 0)) > rn.BEND_SEMIS * 100 or abs(n.get('c', 0)) > rn.BEND_SEMIS * 100]
        if wide:
            _row(out, 'FAIL', t['name'], f'{len(wide)} glide or microtone wider than {rn.BEND_SEMIS} semitones: the synth cannot bend that far')
        if (t.get('instrument') in rn.BOWED or t.get('instrument') in WIND) and gp.on('bow.breath_gap'):
            gap_beats = gp.param('bow.breath_gap', 'gap_beats')
            if t.get('role') in ('melody', 'counter') and len(ns) >= 12:
                win = WINDOW_BARS * bb
                ns = sorted(ns, key=lambda n: n['t'])
                starts = np.arange(0, max(n['t'] for n in ns) + win, win)
                no_gap = 0
                for w0 in starts:
                    seg = [n for n in ns if w0 <= n['t'] < w0 + win]
                    if len(seg) < 2:
                        continue
                    gaps = [b['t'] - (a['t'] + a['d']) for a, b in zip(seg, seg[1:])]
                    if max(gaps) < gap_beats:
                        no_gap += 1
                if no_gap:
                    _row(out, 'WARN', t['name'], f'{no_gap} phrase window(s) of {WINDOW_BARS} bars with no breath or bow gap: add 0.1-0.2 beat rests at phrase ends')
    for level, name, detail in pattern_audit.acoustic_checks(score):
        _row(out, level, name, detail)
    _, flags = pattern_audit.audit(score)           # audit() returns (info, flags)
    for f in flags:
        _row(out, 'WARN', 'pattern', f)
    max_flags = score.get('pattern_flags_max', score.get('quality', {}).get('pattern_flags_max', gp.param('pattern.flags_max', 'max')))
    if len(flags) >= max_flags:
        _row(out, 'FAIL', 'pattern', f'{len(flags)} repetition or flatness flags: the piece reads as a loop, not a composition')
    if not flags:
        _row(out, 'PASS', 'pattern', 'no copy-paste, grid-bound or flat-dynamics flags in the score')


def render_checks(out):
    """Counters the renderer keeps during the last build_stems call."""
    if rn.STATS['clipped']:
        _row(out, 'FAIL', 'glides', f"{rn.STATS['clipped']} bend value(s) were clipped")
    else:
        _row(out, 'PASS', 'glides', f'no bend clipped (range +-{rn.BEND_SEMIS} semitones)')
    if rn.STATS['collisions']:
        _row(out, 'FAIL', 'channels', f"{rn.STATS['collisions']} note(s) started on a channel that was still sounding: "
                                      'a microtone or glide moved a note already playing. Split the track or shorten notes')
    else:
        _row(out, 'PASS', 'channels', 'every microtone note had its own channel')


def spatial_check(path, score, out):
    """A score that stages sources off-centre or at a height must be heard that way. The default mixer path is amplitude pan
    only (no time difference, no elevation), so a staged score with no binaural / trajectory track renders near-mono."""
    import soundfile as sf
    import presets
    imm = _mix_immersive(score)
    staged, routed = 0, 0
    for tr in score.get('tracks', []):
        if tr.get('role') == 'environment' or str(tr.get('instrument', '')).startswith('env:'):
            continue
        sp = tr.get('spatial') or {}
        inst = str(tr.get('instrument') or '')
        pc = {}
        if inst:
            try:
                pc = presets.exact('instruments', inst) or presets.exact('vocals', inst) or {}
            except Exception:
                pc = {}
        spm = dict(pc.get('spatial') or {})
        spm.update(sp)
        role = tr.get('role') or pc.get('role') or 'chord'
        if abs(float(spm.get('azimuth', 0.0))) >= 10.0 or float(spm.get('elevation', 0.0)) != 0.0:
            staged += 1
            is_binaural = bool(spm.get('binaural')) or bool(spm.get('trajectory'))
            if imm and role != 'environment' and spm.get('binaural') is not False:
                is_binaural = True
            routed += bool(is_binaural)
    if not staged:
        return
    try:
        x, _ = sf.read(path, always_2d=True)
    except Exception:
        return
    if x.shape[1] < 2 or float(np.std(x[:, 0])) < 1e-9 or float(np.std(x[:, 1])) < 1e-9:
        return
    corr = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
    if routed == 0 and corr > 0.95:
        _row(out, 'WARN', 'spatial_staging', f'{staged} track(s) are staged off-centre or at a height, but the master is nearly mono '
             f'(L/R correlation {corr:.2f}) and none uses "binaural": true or "trajectory". Only pan and distance were applied; '
             'set binaural on point sources for time/level/height cues, or widen the beds')
    else:
        _row(out, 'PASS', 'spatial_staging', f'{routed} of {staged} staged track(s) use the binaural route; L/R correlation {corr:.2f}')


def _cues(y, sr=44100):
    """(right minus left level in dB, ms the right ear lags the left)"""
    from scipy import signal
    L, R = y[:, 0], y[:, 1]
    ild = 20 * np.log10((np.sqrt((R ** 2).mean()) + 1e-12) / (np.sqrt((L ** 2).mean()) + 1e-12))
    return float(ild), float((np.argmax(signal.correlate(R, L, 'full')) - (len(L) - 1)) / sr * 1000)


def _band_db(y, lo, hi, sr=44100):
    from scipy import signal
    f, p = signal.welch(y.mean(axis=1) if y.ndim == 2 else y, sr, nperseg=2048)
    return float(10 * np.log10(p[(f > lo) & (f < hi)].mean() + 1e-20))


def _third_octave_db(y, lo=500.0, hi=5000.0, sr=44100):
    """1/3-octave band levels from a Welch PSD, for comparing two renderings of the same signal."""
    from scipy import signal
    m = y.mean(axis=1) if np.ndim(y) == 2 else np.asarray(y)
    f, p = signal.welch(m, sr, nperseg=4096)
    out = []
    for c in np.geomspace(float(lo), float(hi), 12):
        sel = (f >= c * 2 ** (-1 / 6.0)) & (f < c * 2 ** (1 / 6.0))
        if np.any(sel):
            out.append(10 * np.log10(p[sel].mean() + 1e-20))
    return np.array(out)


def immersive_rows(score, path, stems, out):
    """Rows for a piece whose mix preset has "immersive": {"enabled": true}. Probes run through the head-data route the mixer
    forces (spatial_hrtf), so a sign flip or a missing filter shows here; the route and height rules are re-checked on the final score."""
    import gate_profiles
    import mixer
    import project_gate
    import soundfile as sf
    from scipy import signal
    cfg = mixer.immersive_cfg(score)
    if not cfg:
        return
    gp = gate_profiles.resolve(score)
    try:
        from spatial_hrtf import binaural as hb
        ok = hb.available()
    except Exception:
        ok = False
    if not ok:
        if gp.on('imm.cues'):
            _row(out, 'FAIL', 'imm_cues', 'head data missing: run `python -m spatial_hrtf.data` from scripts/; without it immersive falls back to spatial.py')
        return
    sr = 44100
    probe = signal.sosfilt(signal.butter(4, [300, 6000], 'band', fs=sr, output='sos'), np.random.default_rng(1).standard_normal(sr))
    if gp.on('imm.cues'):
        min_ild = float(gp.param('imm.cues', 'min_ild_db'))
        min_itd = float(gp.param('imm.cues', 'min_itd_ms'))
        r_ild, r_itd = _cues(hb.spatialize(probe, 60, 0, 1.0))
        l_ild, l_itd = _cues(hb.spatialize(probe, -60, 0, 1.0))
        if r_ild > min_ild and l_ild < -min_ild and r_itd < -min_itd and l_itd > min_itd:
            _row(out, 'PASS', 'imm_cues', f'probe at +-60 deg: level difference {r_ild:+.1f}/{l_ild:+.1f} dB, time difference {r_itd:+.2f}/{l_itd:+.2f} ms')
        else:
            _row(out, 'FAIL', 'imm_cues', f'probe at +-60 deg: level {r_ild:+.1f}/{l_ild:+.1f} dB (want over {min_ild:g}), time {r_itd:+.2f}/{l_itd:+.2f} ms '
                 f'(want right source first, over {min_itd:g} ms): the head filters are wrong or mirrored')

    def tilt(y):
        return _band_db(y, 6000, 12000) - _band_db(y, 500, 1500)
    base = tilt(hb.spatialize(probe, 0, 0, 1.0))
    if gp.on('imm.elevation'):
        lift = {e: tilt(hb.spatialize(probe, 0, e, 1.0)) - base for e in (45, 60)}
        need = float(gp.param('imm.elevation', 'min_tilt_db'))
        _row(out, 'PASS' if lift[60] > need else 'FAIL', 'imm_elevation',
             f'high-frequency tilt grows {lift[45]:+.1f} dB at +45 deg, {lift[60]:+.1f} dB at +60 deg (want over {need:g} dB at +60)')
    if gp.on('imm.frontback'):
        need = float(gp.param('imm.frontback', 'min_tilt_db'))
        fb = abs(tilt(hb.spatialize(probe, 30, 0, 1.0)) - tilt(hb.spatialize(probe, 150, 0, 1.0)))
        _row(out, 'PASS' if fb > need else 'WARN', 'imm_frontback', f'front (30 deg) vs back (150 deg) tilt differs by {fb:.1f} dB (want over {need:g} dB)')
    if gp.on('imm.coloration'):
        lo_hz = float(gp.param('imm.coloration', 'lo_hz'))
        hi_hz = float(gp.param('imm.coloration', 'hi_hz'))
        lim = float(gp.param('imm.coloration', 'max_dev_db'))
        dev = _third_octave_db(hb.spatialize(probe, 0, 0, 1.0), lo_hz, hi_hz, sr) - _third_octave_db(probe, lo_hz, hi_hz, sr)
        dev = dev - np.nanmean(dev)                       # a level offset is not coloration
        spread = float(np.nanstd(dev))
        worst = float(np.max(np.abs(dev))) if len(dev) else 0.0
        _row(out, 'PASS' if spread <= lim else 'WARN', 'imm_coloration',
             f'front-facing 1/3-octave deviation from the dry signal {spread:.1f} dB rms, worst {worst:.1f} dB '
             f'({lo_hz:g}-{hi_hz:g}, limit {lim:g}); an individual head set usually sits lower than a general one')
    if gp.on('imm.route_parity'):
        max_ild = float(gp.param('imm.route_parity', 'max_ild_db'))
        max_itd = float(gp.param('imm.route_parity', 'max_itd_ms'))
        worst_ild = worst_itd = 0.0
        checked = 0
        import spatial as _ana
        for a in (60.0, -60.0):
            try:
                ana = _ana.spatialize_stem(probe, azimuth_deg=a, elevation_deg=0.0, distance_m=1.0,
                                           acoustic_space='outdoor_open', externalize=False, sr=sr)
            except Exception:
                continue
            mi, mt = _cues(hb.spatialize(probe, a, 0, 1.0))
            ai, at = _cues(ana)
            worst_ild = max(worst_ild, abs(mi - ai))
            worst_itd = max(worst_itd, abs(mt - at))
            checked += 1
        if checked:
            ok = worst_ild <= max_ild and worst_itd <= max_itd
            _row(out, 'PASS' if ok else 'WARN', 'imm_route_parity',
                 f'measured vs analytic route: level difference agrees within {worst_ild:.1f} dB (limit {max_ild:g}), '
                 f'time difference within {worst_itd:.2f} ms (limit {max_itd:g}); beyond that one route is wrong for its angles')

    mx, lifted, bad = float(cfg.get('max_elevation', 60.0)), 0, []
    elevs = project_gate.effective_elevations(score, cfg, os.path.dirname(os.path.dirname(os.path.abspath(path))) if path else '.')
    if gp.on('imm.height_rules'):
        for tname, (role, el, sp, _) in elevs.items():
            if sp.get('binaural') is False:
                bad.append(f'{tname}: binaural false')
            if role in ('bass', 'drum') and el:
                bad.append(f'{tname}: {role} at {el:g} deg')
            if abs(el) > mx:
                bad.append(f'{tname}: {el:g} deg beyond {mx:g}')
            lifted += el >= 3.0
        if lifted < int(cfg.get('min_height_tracks', 1)):
            bad.append(f'only {lifted} lifted track(s), want {cfg.get("min_height_tracks", 1)}')
        _row(out, 'FAIL' if bad else 'PASS', 'imm_height_rules', '; '.join(bad[:4]) if bad else f'{lifted} lifted track(s), all within {mx:g} deg, bass/drums level, none left on plain pan')

    if stems and gp.on('imm.band'):
        min_frac = float(gp.param('imm.band', 'min_hf_frac'))
        dull = []
        for tname, (role, el, sp, _) in elevs.items():
            a = stems.get(tname)
            if a is None or el < 15:
                continue
            m = np.asarray(a).mean(axis=1) if np.ndim(a) == 2 else np.asarray(a)
            if len(m) < 2048 or not np.any(m):
                continue
            f, p = signal.welch(m, sr, nperseg=2048)
            if p[f > 4000].sum() / (p.sum() + 1e-20) < min_frac:
                dull.append(tname)
        _row(out, 'WARN' if dull else 'PASS', 'imm_band',
             (f'{", ".join(dull[:4])} sit high but hold under {min_frac * 100:g}% of their energy above 4 kHz: pinna cues live up there, so they will not sound high'
              if dull else 'every lifted stem has energy above 4 kHz to carry its height'))

    rname = score.get('space') or score.get('room', 'hall')
    refl = (mixer.resolve_space(rname) or {}).get('reflections') or {}
    if gp.on('imm.externalization'):
        need_dirs = int(gp.param('imm.externalization', 'min_directions'))
        lo, hi = float(gp.param('imm.externalization', 'min_db')), float(gp.param('imm.externalization', 'max_db'))
        n_dir = sum(float(refl.get(k + '_gain', 0.0)) > 0 for k in ('ground', 'lateral', 'ceiling', 'rear'))
        if n_dir < need_dirs:
            _row(out, 'FAIL', 'imm_externalization', f'space "{rname}" gives reflections from {n_dir} direction(s); immersive needs ground, ceiling, lateral and rear '
                 f'(at least {need_dirs}) because room cues are what move a sound outside the head')
        else:
            er = hb.reflections(probe, 30, 1.5, refl)
            d = hb.spatialize(probe, 30, 0, 1.5)
            ratio = 10 * np.log10((er ** 2).sum() / ((d ** 2).sum() + 1e-12) + 1e-12)
            _row(out, 'PASS' if lo <= ratio <= hi else 'WARN', 'imm_externalization',
                 f'reflections from {n_dir} directions, {ratio:+.1f} dB re direct (want {lo:g} to {hi:g})')
    space = mixer.resolve_space(rname)
    if gp.on('imm.envelopment'):
        ir = mixer.make_ir(space if space.get('room') else 'hall')
        t0 = int(0.08 * sr)
        lat = ir[t0:]
        iacc = float(np.max(np.abs(signal.correlate(lat[:, 0], lat[:, 1], 'full')[len(lat) - 1 - 44:len(lat) + 44])) / (np.sqrt((lat[:, 0] ** 2).sum() * (lat[:, 1] ** 2).sum()) + 1e-12))
        lim = float((gp.rows.get('imm.envelopment') or {}).get('max_late_iacc')
                    or (cfg.get('gate') or {}).get('max_late_iacc', gp.param('imm.envelopment', 'max_late_iacc')))
        _row(out, 'PASS' if iacc <= lim else 'WARN', 'imm_envelopment',
             f'late-tail interaural correlation {iacc:.2f} (limit {lim:g}); IACC alone does not prove envelopment, and the overhead part of the tail is not measured')

    x, _ = sf.read(path, always_2d=True) if path else (np.zeros((1, 2)), sr)
    if x.shape[1] == 2 and len(x) > sr:
        if gp.on('imm.width'):
            c = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
            lim = float((gp.rows.get('imm.width') or {}).get('max_corr', gp.param('imm.width', 'max_corr')))
            _row(out, 'WARN' if c > lim else 'PASS', 'imm_width',
                 f'L/R correlation {c:.2f} (limit {lim:g})' + (' (nearly mono: beds are not wide)' if c > lim else ''))
        if gp.on('imm.foldown'):
            drop = mixer.lufs(x, sr) - mixer.lufs(np.stack([x.mean(axis=1)] * 2, 1), sr)
            lim = float((gp.rows.get('imm.foldown') or {}).get('max_lu', gp.param('imm.foldown', 'max_lu')))
            _row(out, 'FAIL' if drop > lim else 'PASS', 'imm_foldown', f'mono fold-down is {drop:+.1f} LU vs the stereo master (limit {lim:g}): '
                 + ('phase cancellation will thin it on phone speakers' if drop > lim else 'holds up on a phone speaker'))


def audio_checks(path, score, out):
    """Measurements of the rendered file against the score's own targets."""
    master = score.get('master', {})
    target = master.get('lufs', -14.0)
    lufs_tol = master.get('lufs_tolerance', master.get('tolerance_lu', 2.5))
    tp_target = master.get('true_peak', -1.5)
    r = nc.analyse(path, target_lufs=target)
    spatial_check(path, score, out)
    for level, msg in nc.verdicts(r, target=target):
        _row(out, level, 'audio', msg)
    d = r['lufs'] - target
    if abs(d) > lufs_tol:
        _row(out, 'FAIL', 'loudness', f'{r["lufs"]:.1f} LUFS, target {target}: missed by {d:+.1f} LU. The mix is too dynamic for the '
                                      'target under the limiter. Lower the target or the dynamics range, or accept it and say so')
    if r['true_peak'] > tp_target + 0.3:
        _row(out, 'FAIL', 'true peak', f"{r['true_peak']:.2f} dBTP is above the ceiling {tp_target}")
    x, sr = nc.load(path)
    mono = x.mean(axis=1) if x.ndim == 2 else x
    # silent gap: a run of 1 s or more under -60 dBFS, away from the start and end
    win = int(0.25 * sr)
    n = len(mono) // win
    rms_db = 10 * np.log10(np.mean(mono[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    quiet = rms_db < -60
    run, gaps = 0, []
    for i, q in enumerate(quiet):
        run = run + 1 if q else 0
        if run == 4:                                   # 1 s of quiet
            gaps.append(i * 0.25)
    inner = [g for g in gaps if 2.0 < g < r['dur'] - 2.0]
    if inner:
        _row(out, 'FAIL', 'silence', f'silent gap of 1 s or more at {", ".join(f"{g:.1f}s" for g in inner[:4])}')
    else:
        _row(out, 'PASS', 'silence', 'no silent gap in the middle of the piece')
    clicks = find_clicks(mono)
    if len(clicks):
        when = ', '.join(f'{i / sr:.3f}s' for i in clicks[:5])
        _row(out, 'WARN', 'clicks', f'{len(clicks)} single-sample jump(s) above {CLICK_STEP} of full scale, first at {when}. '
                                    'Check the sample start or add a 2-5 ms fade-in at that note')
    else:
        _row(out, 'PASS', 'clicks', f'no single-sample jump above {CLICK_STEP} of full scale')
    import gate_profiles
    gp = gate_profiles.resolve(score)
    if gp.on('natural.aliasing'):
        # the sampler resamples with linear interpolation; a note transposed up leaves images up there, and a
        # real instrument has little energy above 15 kHz unless it is a cymbal. Measured on the delivered master.
        from scipy import signal as _sig
        f, p = _sig.welch(mono, sr, nperseg=8192)
        band = p[(f > 200.0) & (f < 16000.0)].sum() + 1e-20
        share = 10 * np.log10(p[f >= 15000.0].sum() / band + 1e-20)
        lim = float(gp.param('natural.aliasing', 'max_hf_share_db'))
        _row(out, 'WARN' if share > lim else 'PASS', 'natural_aliasing',
             f'15-22 kHz holds {share:.1f} dB of the 200 Hz-16 kHz band (limit {lim:g}); above that it is sampler '
             f'interpolation images, not instrument (fix: render.oversample in the mix preset)')
    # 2.1 Plomp-Levelt & Sethares Cochlear Sensory Roughness
    rough_rows, _ = nc.cochlear_roughness_check(x, sr=sr, score=score)
    for l, n, d in rough_rows:
        _row(out, l, n, d)


MASK_WIN_S = 4.0            # the congestion check looks at 4-second windows
MASK_MARGIN_DB = 3.0        # a bed within 3 dB of the lead in an ERB critical band is congested


def masking_rows(stems, score, sr=44100, out=None):
    """2.2 Moore-Glasberg ERB Critical-Band & Binaural Unmasking (Moore & Glasberg 1983).
    Evaluates 8 ERB critical bands across 250 - 4000 Hz, with up to +3.5 dB delta BMLD binaural
    unmasking bonus for stereo azimuth/pan separation.
    """
    from scipy.signal import butter, sosfilt
    import mixer
    import gate_profiles
    rows = []
    gp = gate_profiles.resolve(score)
    if not gp.on('masking.vs_melody'):
        return rows                                        # listed once, with its reason, by the profile notes
    margin_db = gp.param('masking.vs_melody', 'margin_db')
    if mixer.STATE.get('processed'):                       # measure the mix as played: after the EQ and the carve
        stems = mixer.STATE['processed']
    roles = {t['name']: t.get('role') for t in score['tracks']}
    leads = [n for n, r in roles.items() if r == 'melody' and n in stems]
    beds = [n for n, r in roles.items() if r in ('pad', 'chord', 'arp', 'counter') and n in stems and n not in leads]
    beds += [n for n in ('chorus',) if n in stems and n not in beds]
    if not leads or not beds:
        return rows

    # 8 ERB center frequencies spanning 250 - 4000 Hz
    center_freqs = [300, 500, 800, 1200, 1750, 2400, 3100, 3900]
    win = int(MASK_WIN_S * sr)

    def pan_profile(x):
        if x.ndim == 2 and x.shape[1] >= 2:
            l_rms = float(np.std(x[:, 0]))
            r_rms = float(np.std(x[:, 1]))
            return (r_rms - l_rms) / (r_rms + l_rms + 1e-9)
        return 0.0

    def effective_pan(name):
        """Where the source actually sits. A binaural/HRTF stem's L/R balance says nothing about its azimuth
        (spatial.py applies the head shadow), so a declared spatial.azimuth is the separation credit; a plain
        stereo stem falls back to its measured pan."""
        tr = next((t for t in score.get('tracks', []) if t.get('name') == name), None) or {}
        for cand in (tr.get('spatial') or {}, {}):
            try:
                if isinstance(cand, dict) and cand.get('azimuth') is not None:
                    return float(np.clip(np.sin(np.radians(float(cand['azimuth']))), -1.0, 1.0))
            except (TypeError, ValueError):
                pass
        try:
            import presets as _p
            inst = str(tr.get('instrument', ''))
            cfg = (_p.find_instrument(inst) or _p.find_vocal(inst) or {}) or {}
            sp = cfg.get('spatial') or {}
            if sp.get('azimuth') is not None:
                return float(np.clip(np.sin(np.radians(float(sp['azimuth']))), -1.0, 1.0))
        except Exception:
            pass
        return pan_profile(stems[name])

    lead_pans = {n: effective_pan(n) for n in leads}
    bed_pans = {n: effective_pan(n) for n in beds}

    congested = []
    for fc in center_freqs:
        erb = 24.7 * (4.37 * fc / 1000.0 + 1.0)
        flo = max(20.0, fc - erb / 2.0)
        fhi = min(sr / 2.0 - 50.0, fc + erb / 2.0)
        sos = butter(2, [flo, fhi], btype='band', fs=sr, output='sos')

        def band_db(x):
            m = x.mean(axis=1) if x.ndim == 2 else x
            y = sosfilt(sos, m)
            return 20 * np.log10(np.sqrt(np.mean(y.reshape(-1)[:len(y) // win * win].reshape(-1, win) ** 2, axis=1)) + 1e-12)

        lead_db = {n: band_db(stems[n]) for n in leads}
        bed_db = {n: band_db(stems[n]) for n in beds}

        for ln, ld in lead_db.items():
            l_pan = lead_pans.get(ln, 0.0)
            for i in range(len(ld)):
                if ld[i] < -42.0:
                    continue
                for bn, bd in bed_db.items():
                    if i < len(bd):
                        b_pan = bed_pans.get(bn, 0.0)
                        pan_diff = abs(l_pan - b_pan)
                        delta_bmld = min(3.5, 3.5 * pan_diff)
                        effective_margin = margin_db - delta_bmld
                        if bd[i] > ld[i] - effective_margin:
                            congested.append((i * MASK_WIN_S, ln, bn, fc, round(bd[i] - (ld[i] - effective_margin), 1)))

    if congested:
        t0, ln, bn, fc, ov = congested[0]
        stems_hit = sorted(set(c[2] for c in congested))
        fcs_hit = sorted(set(c[3] for c in congested))
        lvl = 'FAIL' if len(congested) > 8 else 'WARN'
        rows.append((lvl, 'erb_binaural_masking',
                     f"{len(congested)} ERB critical-band collision window(s) where lead ({ln}) is masked by {', '.join(stems_hit)} "
                     f"around {', '.join(f'{f}Hz' for f in fcs_hit[:3])}, first at {t0:.1f}s. "
                     f"Apply a narrow parametric EQ notch at {fc}Hz or increase stereo azimuth separation (spatial.azimuth)."))
    else:
        rows.append(('PASS', 'erb_binaural_masking', 'Lead vocal/melody has clear auditory separation across all 8 ERB critical bands (250-4000 Hz)'))

    if out is not None:
        out.extend(rows)
    return rows


def _longest_run(mask):
    """Length of the longest stretch of consecutive True values."""
    best = run = 0
    for v in mask:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def ambient_fusion_rows(score, rendered_path, stems=None, out=None, sr=44100):
    """Quality gate check for fused environmental soundscapes (SKILL.md, 'ambient_glue').
    
    Verifies that when nature ambience (water, birds, canopy, rain) is fused with music:
      1. Zero Dropouts: Ambient beds do not drop to zero or cut out abruptly during the musical body.
      2. Zero Rapid Gain Pumping / Chatter: Short-term gain changes between adjacent 0.5s windows remain
         smooth (|delta RMS| <= 3.8 dB), proving proper long release times and sigmoid crossfading.
      3. Shared Acoustic Space: Verifies that both musical instruments and ambient tracks share the reverb bus.
    """
    rows = []
    import gate_profiles
    gp = gate_profiles.resolve(score)               # pump_db belongs to the piece's type, not to this function
    env_tracks = [t['name'] for t in score.get('tracks', [])
                  if t.get('role') == 'environment' or str(t.get('instrument', '')).startswith('env:')]
    if not env_tracks:
        return rows
        
    import mixer
    if mixer.STATE.get('processed'):
        stems = mixer.STATE['processed']
        
    # Check 1: Shared Reverb Space
    room = score.get('space') or score.get('room') or 'none'
    if room != 'none':
        rows.append(('PASS', 'ambient_glue', f'shared acoustic space unified on "{room}" reverb convolution bus'))
    else:
        rows.append(('WARN', 'ambient_glue', 'no shared room reverb bus specified; nature and instruments may sound separated'))
        
    if stems:
        found_envs = [n for n in env_tracks if n in stems]
        # "silence" is relative to the mix: stems are judged before mastering, where the absolute level is just gain staging.
        # The old fixed -58 dBFS sat about 38 dB under a typical pre-master mix; keep that distance, never stricter than -58.
        _m = [v.mean(axis=1) if v.ndim == 2 else v for v in stems.values()]
        _n = min(len(v) for v in _m)
        _mix = np.sum([v[:_n] for v in _m], axis=0)
        _body = _mix[int(8 * sr):-int(8 * sr)] if _n > 16 * sr else _mix
        mix_db = float(20 * np.log10(np.sqrt(np.mean(_body ** 2)) + 1e-12))
        floor_db = min(-58.0, mix_db - 38.0)
        for name in found_envs:
            x = stems[name]
            mono = x.mean(axis=1) if x.ndim == 2 else x
            win = int(0.5 * sr)
            if len(mono) < win * 6:
                continue
            k = len(mono) // win
            blocks = mono[:k * win].reshape(k, win)
            rms = np.sqrt(np.mean(blocks ** 2, axis=1) + 1e-12)
            rms_db = 20 * np.log10(rms)
            
            # Musical body region: avoid the first 8s and last 8s where macro fades occur
            idx_start = int(8.0 / 0.5)
            idx_end = max(idx_start + 1, k - int(8.0 / 0.5))
            tr = next((t for t in score.get('tracks', []) if t.get('name') == name), {})
            if tr.get('notes') and not tr.get('full_length'):      # a bed that enters late is only judged where it plays
                bd = 60.0 / float(score.get('bpm', 90.0))
                s0 = min(float(nt['t']) for nt in tr['notes']) * bd
                s1 = max(float(nt['t']) + float(nt.get('d', 1.0)) for nt in tr['notes']) * bd
                idx_start = max(idx_start, int((s0 + 3.0) / 0.5))   # 2 s fade-in + humanize drift
                idx_end = min(idx_end, int((s1 - 3.0) / 0.5))
            if idx_end > idx_start + 4:
                body_db = rms_db[idx_start:idx_end]
                # Sparse event stems (calls, drips, creaks) are silent between events by nature: a steady-bed test would read every
                # call as a jump. They are recognised by their gaps (a quarter or more of the blocks 40 dB under their loudest block)
                # and by short bursts: no sound lasts over 8 s, so a bed with a long dead stretch is still judged as a bed.
                gap = body_db < max(body_db.max() - 40.0, -110.0)      # the block meter reads exact silence as -120 dB
                if gap.mean() >= 0.25 and _longest_run(~gap) <= 16:
                    loud_blocks = int(np.sum(body_db > floor_db))
                    if loud_blocks < 3:
                        rows.append(('FAIL', 'ambient_bed', f'event stem "{name}" never rises above the silent floor ({floor_db:.0f} dBFS); '
                                     f'its loudest block is {body_db.max():.0f} dBFS. Raise gain_db or event_rate'))
                    else:
                        rows.append(('PASS', 'ambient_bed', f'event stem "{name}": {loud_blocks} audible 0.5 s blocks above {floor_db:.0f} dBFS '
                                     f'between silent gaps (steady-bed dropout and pumping tests do not apply)'))
                    continue
                # A. Dropout check: no block in the active musical section should drop to the silent floor (relative to the mix, see above)
                dropouts = np.where(body_db < floor_db)[0]
                if len(dropouts) > 0:
                    t_drop = (idx_start + dropouts[0]) * 0.5
                    rows.append(('FAIL', 'ambient_bed', f'ambient stem "{name}" drops out to silence at {t_drop:.1f}s'))
                    
                # B. Pumping / Chatter check: derivative between adjacent 0.5s windows. A bed that swells into a
                # climax is not pumping: the score's own dynamics arc raises the limit by half its dB/s slope.
                try:
                    if median_filter is not None and len(body_db) >= 11:
                        baseline = median_filter(body_db, size=11, mode='nearest')
                        measure_db = np.minimum(body_db, baseline + 2.0)
                    else:
                        measure_db = body_db
                except Exception:
                    measure_db = body_db
                diffs = np.abs(np.diff(measure_db))
                max_diff = float(np.max(diffs)) if len(diffs) else 0.0
                slope_db_s = 0.0
                dyn = score.get('dynamics') or []
                if len(dyn) >= 2:
                    try:
                        pts = sorted((float(b), float(v)) for b, v in dyn)
                        bpm = float(score.get('bpm', 90.0))
                        for (b0, v0), (b1, v1) in zip(pts, pts[1:]):
                            if b1 > b0 and v0 > 1e-6 and v1 > 1e-6:
                                slope_db_s = max(slope_db_s, abs(20 * np.log10(v1 / v0)) / (b1 - b0) * bpm / 60.0)
                    except (TypeError, ValueError):
                        slope_db_s = 0.0
                pump_limit = gp.param('ambient_bed', 'pump_db') + 0.5 * slope_db_s
                if max_diff > pump_limit:
                    i_max = int(np.argmax(diffs))
                    t_pump = (idx_start + i_max) * 0.5
                    rows.append(('FAIL', 'ambient_bed', f'rapid gain pumping on "{name}" ({max_diff:.1f} dB jump at {t_pump:.1f}s, '
                                 f'limit {pump_limit:.1f}). Smooth ducker release or use sigmoid crossfade'))
                else:
                    rows.append(('PASS', 'ambient_bed', f'ambient stem "{name}" glides smoothly with zero dropouts or pumping (max 0.5s delta: {max_diff:.1f} dB)'))
    else:
        rows.append(('PASS', 'ambient_fusion', f'{len(env_tracks)} ambient soundscape tracks integrated into score'))
        
    if out is not None:
        out.extend(rows)
    return rows


LEAD_ROLES = ('melody', 'lead', 'vocal')


def balance_allow_db(mix=None):
    """Role allowances from the piece's mix preset (`balance.allow_db`), schema defaults otherwise."""
    import mix_schema
    allow = ((mix or {}).get('balance') or {}).get('allow_db')
    return allow or mix_schema.DEFAULTS['balance']['allow_db']


def _active_db(x, sr, win_s=0.5, span_db=30.0):
    """Mean level of the blocks that are playing (within span_db of the loudest), so rests do not hide a loud stem."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    k = len(mono) // int(win_s * sr)
    if k < 2:
        return None
    b = mono[:k * int(win_s * sr)].reshape(k, -1)
    p = np.mean(b ** 2, axis=1)
    db = 10 * np.log10(p + 1e-12)
    on = db > db.max() - span_db
    return float(10 * np.log10(np.mean(p[on]) + 1e-12))


def balance_rows(score, stems=None, out=None, sr=44100):
    """Any music: no accompaniment stem may sit far above the lead. Role allowances come from the piece's mix
    preset (`balance.allow_db`); WARN/FAIL at the gate row's warn_over_db / fail_over_db. Environment and fx
    stems are judged by ambient_bed, not here. Level is plain RMS, not K-weighted."""
    rows = []
    import mixer
    import gate_profiles
    gp = gate_profiles.resolve(score)
    st = mixer.STATE.get('processed') or stems
    if st:
        roles = {t['name']: t.get('role') for t in score.get('tracks', [])}
        lv = {n: _active_db(v, sr) for n, v in st.items() if n in roles}
        leads = [lv[n] for n in lv if roles[n] in LEAD_ROLES and lv[n] is not None]
        if leads and gp.on('balance.vs_lead'):
            lead = max(leads)
            warn_over, fail_over = gp.param('balance.vs_lead', 'warn_over_db'), gp.param('balance.vs_lead', 'fail_over_db')
            for n, db in lv.items():
                allow = balance_allow_db(mixer._mix()).get(roles[n])
                if allow is None or db is None:
                    continue
                over = db - lead - allow
                if over > fail_over:
                    rows.append(('FAIL', 'balance', f'"{n}" ({roles[n]}) plays {db - lead:+.1f} dB against the lead; allowed {allow:+.0f}. Lower its gain_db by about {over:.0f} dB'))
                elif over > warn_over:
                    rows.append(('WARN', 'balance', f'"{n}" ({roles[n]}) plays {db - lead:+.1f} dB against the lead; allowed {allow:+.0f}'))
            if not rows:
                rows.append(('PASS', 'balance', f'every accompaniment stem sits within its role allowance of the lead'))
        elif gp.fallback('balance.vs_lead') == 'balance.layers' and gp.on('balance.layers'):
            rows += layer_balance_rows(score, lv, roles, gp)
    if out is not None:
        out.extend(rows)
    return rows


def layer_balance_rows(score, lv, roles, gp):
    """No lead to measure against (effects-only, ambient, a cue): each layer against the median layer.
    WARN / FAIL at balance.layers warn_db / fail_db above or below. Environment stems are judged by ambient_bed instead.
    INFO when no layer stands out from the rest. Plain RMS of the blocks that play, like balance.vs_lead."""
    rows = []
    layers = {n: db for n, db in lv.items() if db is not None and roles.get(n) != 'environment'}
    if len(layers) < 2:
        return rows
    med = float(np.median(list(layers.values())))
    warn, fail = gp.param('balance.layers', 'warn_db'), gp.param('balance.layers', 'fail_db')
    for n, db in layers.items():
        d = db - med
        if abs(d) > fail:
            rows.append(('FAIL', 'balance', f'"{n}" plays {d:+.1f} dB from the median layer (limit {fail:.0f}). Set its gain_db about {-d:+.0f} dB'))
        elif abs(d) > warn:
            rows.append(('WARN', 'balance', f'"{n}" plays {d:+.1f} dB from the median layer (limit {warn:.0f})'))
    if not rows:
        top = sorted(layers.values())[-2:]
        spread = top[1] - top[0]
        if spread < 1.0:
            rows.append(('INFO', 'balance', f'{len(layers)} layers sit within {warn:.0f} dB of the median; no layer is clearly in front (top two within {spread:.1f} dB)'))
        else:
            rows.append(('PASS', 'balance', f'{len(layers)} layers sit within {warn:.0f} dB of the median layer (no lead to compare against)'))
    return rows


Z_BAND_HZ = (500.0, 4000.0)      # where strings, brass and a bright synth lead all sit
Z_FRAME_S = 0.25                 # band-envelope resolution for the overlap measure


def _band_frames(x, sr, lo=500.0, hi=4000.0, win_s=Z_FRAME_S):
    """RMS of the lo-hi band in win_s frames, or None when the stem is shorter than two frames."""
    from scipy.signal import butter, sosfilt
    mono = np.asarray(x, dtype=np.float32)
    mono = mono.mean(axis=1) if mono.ndim == 2 else mono
    n = int(win_s * sr)
    if len(mono) < 2 * n:
        return None
    sos = butter(4, [lo, min(hi, sr * 0.45)], btype='band', fs=sr, output='sos')
    y = sosfilt(sos, mono)
    k = len(y) // n
    return np.sqrt((y[:k * n].reshape(k, n) ** 2).mean(axis=1) + 1e-20)


def _mix_immersive(score):
    """The score's mix preset's immersive block when it is on, without switching the mixer's context."""
    import presets
    name = score.get('mix_preset')
    if not name:
        return None
    try:
        imm = (presets.exact('mix', name) or {}).get('immersive') or {}
    except Exception:
        return None
    return imm if imm.get('enabled') else None


def _place_of(score, tr, imm):
    """(azimuth, elevation, spatial, role, height_rendered) as the mixer will apply them for this track."""
    import presets
    inst = str(tr.get('instrument') or '')
    pc = {}
    if inst:
        try:
            pc = presets.exact('instruments', inst) or presets.exact('vocals', inst) or {}
        except Exception:
            pc = {}
    sp = dict(pc.get('spatial') or {})
    tr_sp = tr.get('spatial') or {}
    sp.update(tr_sp)
    role = tr.get('role') or pc.get('role') or 'chord'
    az = float(sp.get('azimuth', 0.0))
    el = float(sp.get('elevation', 0.0))
    if imm and 'elevation' not in tr_sp and float(el) == 0.0:
        el = float((imm.get('height_by_role') or {}).get(role, 0.0))
    elif 'elevation' not in sp and imm:
        el = float((imm.get('height_by_role') or {}).get(role, 0.0))
    if imm and role in ('bass', 'drum'):
        el = 0.0                                  # the mixer keeps bass and drums on the floor
    rendered = bool(sp.get('binaural')) or bool(sp.get('trajectory')) or bool(imm)
    if sp.get('binaural') is False:
        rendered = False
    return az, el, sp, role, rendered


def _has_staging(score, tr):
    """True when a preset or the track itself says where this part sits. A generic test cue has neither, so there
    is no placement to judge; a real project always has one, because its presets are required and each carries a spot."""
    import presets
    inst = str(tr.get('instrument') or '')
    if inst:
        try:
            pc = presets.exact('instruments', inst) or presets.exact('vocals', inst) or {}
        except Exception:
            pc = {}
        if pc.get('spatial'):
            return True
    return bool(tr.get('spatial'))


def _wrap_deg(d):
    d = abs(float(d)) % 360.0
    return 360.0 - d if d > 180.0 else d


def spatial_separation_rows(score, stems=None, out=None, sr=44100):
    """Z-axis separation in the climax. Two parts that hold the same midrange band at the same time and level mask each
    other; HRTF height and azimuth separate them where an EQ cut would only make both dull. Measured on the loudest quarter
    of the piece (the climax), never assumed. A pair passes on min_sep_deg of angular separation or min_elev_deg of height;
    height only counts where the mixer renders it. Environment stems are excluded (their width is spread/kind, not a spot)."""
    rows = []
    import gate_profiles
    gp = gate_profiles.resolve(score)
    if not gp.on('spatial.z_separation'):
        return rows                          # listed once, with its reason, by the profile notes
    import mixer
    st = mixer.STATE.get('processed') or stems
    if not st:
        return rows
    tracks = {t.get('name'): t for t in score.get('tracks', [])}
    cand = [n for n, t in tracks.items() if n in st and t.get('role') != 'environment'
            and not str(t.get('instrument', '')).startswith('env:')]
    frames = {n: _band_frames(st[n], sr) for n in cand}
    frames = {n: f for n, f in frames.items() if f is not None and len(f) >= 4}
    if len(frames) < 2:
        return rows
    k = min(len(f) for f in frames.values())
    frames = {n: f[:k] for n, f in frames.items()}
    total = np.sum(list(frames.values()), axis=0)
    top = max(8, int(round(0.25 * k)))       # the loudest quarter: the climax
    climax = np.zeros(k, dtype=bool)
    climax[np.argsort(total)[-min(top, k):]] = True

    overlap_min = float(gp.param('spatial.z_separation', 'overlap_min'))
    min_sep = float(gp.param('spatial.z_separation', 'min_sep_deg'))
    min_elev = float(gp.param('spatial.z_separation', 'min_elev_deg'))
    imm = _mix_immersive(score)
    where = {n: _place_of(score, tracks[n], imm) for n in frames}
    staged = {n: _has_staging(score, tracks[n]) for n in frames}
    unplaced = 0

    fights, closest = [], None
    names = sorted(frames)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            fa, fb = frames[a][climax], frames[b][climax]
            on = (fa > fa.max() * 0.03) & (fb > fb.max() * 0.03)   # both within 30 dB of their own climax level
            if on.sum() < 4:
                continue
            if not (staged[a] or staged[b]):
                unplaced += 1                      # nothing declares a spot, so there is no separation to measure
                continue
            ov = float(np.mean(np.minimum(fa, fb)[on] / np.maximum(fa, fb)[on]))
            az_a, el_a, sp_a, role_a, h_a = where[a]
            az_b, el_b, sp_b, role_b, h_b = where[b]
            delev = abs(el_a - el_b) if (h_a and h_b) else 0.0
            daz = _wrap_deg(az_a - az_b)
            sep = float(np.hypot(daz, delev))
            if closest is None or ov > closest[2]:
                closest = (a, b, ov, sep, daz, delev)
            if ov >= overlap_min and sep < min_sep and delev < min_elev:
                fights.append((ov, a, b, sep, daz, delev, h_a and h_b, sp_a, sp_b))

    if fights:
        fights.sort(reverse=True)
        ov, a, b, sep, daz, delev, heights, sp_a, sp_b = fights[0]
        names_hit = ', '.join(f'"{x}" and "{y}"' for _, x, y, *_ in fights[:3])
        unbinaural = [n for n in (a, b) if not heights]
        hint = ''
        if unbinaural:
            hint = (f'; {unbinaural[0]}' + (f' and {unbinaural[1]}' if len(unbinaural) > 1 else '') +
                    ' has no binaural route, so a staged height is not rendered: set "binaural": true')
        _row(out, 'FAIL', 'spatial.z_separation',
             f'{names_hit} both hold the 500-4000 Hz band in the climax (envelope overlap {ov:.2f}) and sit {sep:.0f} deg apart '
             f'(azimuth {daz:.0f}, elevation {delev:.0f}); the limit is {min_sep:.0f} deg apart or {min_elev:.0f} deg of height. '
             f'Give one part an elevated arc (for a strings-versus-low-brass collision: strings out at about +-50 deg azimuth, '
             f'+25..35 deg elevation; low brass and timpani anchored at about +-20 deg, -10..0 deg) or move one {min_sep:.0f} deg '
             f'or more in azimuth{hint}')
    elif closest:
        a, b, ov, sep, daz, delev = closest
        _row(out, 'PASS', 'spatial.z_separation',
             f'closest competing pair "{a}"/"{b}": band envelope overlap {ov:.2f} (limit {overlap_min:.2f}), {sep:.0f} deg apart '
             f'(azimuth {daz:.0f}, elevation {delev:.0f}); every pair that shares the midrange in the climax is separated')
    elif unplaced:
        _row(out, 'INFO', 'spatial.z_separation',
             f'{unplaced} competing pair(s) carry no declared staging (a test-mode cue has no presets), so their '
             f'separation is not judged; a project places every part in a preset')
    if out is not None:
        out.extend(rows)
    return rows


def _ath_db(f):
    """Terhardt's absolute threshold of hearing (dB SPL) for f in Hz: the sensitivity dip near 3.3 kHz that ISO 226's
    threshold region encodes. Used as a relative weighting, never as an absolute SPL calibration."""
    k = np.maximum(np.asarray(f, dtype=np.float64), 20.0) / 1000.0
    return 3.64 * k ** -0.8 - 6.5 * np.exp(-0.6 * (k - 3.3) ** 2) + 1e-3 * k ** 4


def equal_loudness_rows(score, stems=None, out=None, sr=44100):
    """Equal-loudness (K-weighted) harshness in the 2.5-5 kHz ear-sensitivity zone. A bright synth lead or a raw sample can
    sit far louder there than its mids once the ear's sensitivity is weighted, which reads as harsh even when the plain
    spectrum looks modest. Per stem: Welch power weighted by the threshold-sensitivity curve, the 2.5-5 kHz band against
    500 Hz-2.5 kHz, corrected to an equal-energy-per-octave reference. The row names the narrow inst_eq cut to paste into the
    piece's mix preset; it never edits the mix itself. This is an approximation of equal loudness, not a certified ISO 226 meter."""
    rows = []
    import gate_profiles
    gp = gate_profiles.resolve(score)
    if not gp.on('spectral.equal_loudness'):
        return rows
    import mixer
    st = mixer.STATE.get('processed') or stems
    if not st:
        return rows
    roles = {t.get('name'): t.get('role') for t in score.get('tracks', [])}
    lo = float(gp.param('spectral.equal_loudness', 'band_lo_hz'))
    hi = float(gp.param('spectral.equal_loudness', 'band_hi_hz'))
    warn_db = float(gp.param('spectral.equal_loudness', 'warn_db'))
    fail_db = float(gp.param('spectral.equal_loudness', 'fail_db'))
    max_trim = float(gp.param('spectral.equal_loudness', 'max_trim_db'))
    from scipy import signal as _sig
    ref_lo = 500.0
    baseline = 10.0 * np.log10(np.log2(hi / lo) / np.log2(lo / ref_lo))    # equal energy per octave reads about 0 dB
    worst = None
    for name in sorted(st):
        if roles.get(name) == 'environment':
            continue
        x = np.asarray(st[name], dtype=np.float32)
        mono = x.mean(axis=1) if x.ndim == 2 else x
        if len(mono) < 4096 or not np.any(mono):
            continue
        f, p = _sig.welch(mono.astype(np.float64), sr, nperseg=4096)
        w = 10.0 ** ((float(_ath_db(1000.0)) - _ath_db(f)) / 10.0)     # sensitivity relative to 1 kHz
        pw = p * w
        band = (f >= lo) & (f <= hi)
        ref = (f >= ref_lo) & (f < lo)
        if not band.any() or not ref.any():
            continue
        excess = 10.0 * np.log10((pw[band].sum() + 1e-20) / (pw[ref].sum() + 1e-20)) - baseline
        if worst is None or excess > worst[1]:
            worst = (name, excess)
        if excess > warn_db:
            trim = min(max_trim, max(1.0, excess - warn_db))
            level = 'FAIL' if excess > fail_db else 'WARN'
            rows.append((level, 'spectral.equal_loudness',
                         f'"{name}" ({roles.get(name) or "?"}) puts {excess:.1f} dB more ear-weighted level in {lo:.0f}-{hi:.0f} Hz '
                         f'than its 500-{lo:.0f} Hz mids (warn {warn_db:.0f}, fail {fail_db:.0f}). Trim about {trim:.1f} dB at '
                         f'{(lo * hi) ** 0.5:.0f} Hz in the mix preset: "inst_eq": {{"{name}": [{{"type": "peak", "f": '
                         f'{(lo * hi) ** 0.5:.0f}, "gain": -{trim:.1f}, "q": 1.0}}]}}'))
    if not rows and worst:
        _row(out, 'PASS', 'spectral.equal_loudness',
             f'highest ear-weighted {lo:.0f}-{hi:.0f} Hz excess is {worst[1]:+.1f} dB on "{worst[0]}" (warn {warn_db:.0f}): '
             f'no stem spikes in the 2.5-5 kHz sensitivity zone')
    if out is not None:
        out.extend(rows)
    return rows


def metadata_rows(score, out, project_dir=None):
    """Delivery traceability: the certified master carries standard metadata (`<master>.json`, written by
    scripts/helpers/ingest_metadata.py) and a version record in `out/versions.json` whose versioned file still
    exists (scripts/helpers/version_manager.py). The gate only reads this; it never writes or repairs it.
    These rows never FAIL: metadata is written after the musical gate passes, so a missing record is a WARN
    about the delivery, not a reason to reject the music."""
    import gate_profiles
    gp = gate_profiles.resolve(score)
    if not project_dir:
        return
    out_dir = os.path.join(project_dir, 'out')
    master = os.path.join(out_dir, 'master.wav')
    # The gate runs before certification writes the record, so the very first render has nothing to trace
    # yet: report that as INFO rather than as a defect.
    first_render = not os.path.isfile(master) and not os.path.isfile(os.path.join(out_dir, 'versions.json'))

    if first_render:
        if gp.on('meta.tags') or gp.on('meta.version'):
            out.append(('INFO', 'meta', 'traceability: no certified master yet, tags and the version record are '
                                      'written at certification'))
        return

    if gp.on('meta.tags'):
        limit = int(gp.param('meta.tags', 'max_missing'))
        sidecar = os.path.splitext(master)[0] + '.json'
        missing = []
        if not os.path.isfile(sidecar):
            missing.append('no sidecar beside the master')
        else:
            try:
                tags = (json.load(open(sidecar, encoding='utf-8')) or {}).get('metadata') or {}
            except Exception:
                tags = {}
            if not tags:
                missing.append('sidecar holds no tags')
            if tags and score.get('title') and not tags.get('title'):
                missing.append('sidecar has no title')
            elif score.get('title') and tags.get('title') != score.get('title'):
                missing.append(f'sidecar title "{tags.get("title")}" is not the score title "{score.get("title")}"')
        lvl = 'PASS' if not missing else ('WARN' if len(missing) <= limit else 'WARN')
        out.append((lvl, 'meta', 'metadata: standard tags present beside the master' if not missing
                    else 'metadata: ' + '; '.join(missing) + ' (run scripts/helpers/ingest_metadata.py)'))

    if gp.on('meta.version'):
        limit = int(gp.param('meta.version', 'max_missing'))
        index = os.path.join(out_dir, 'versions.json')
        problems = []
        entry = None
        if not os.path.isfile(index):
            problems.append('no versions.json')
        else:
            try:
                data = json.load(open(index, encoding='utf-8'))
                versions = data.get('versions') or []
                entry = versions[-1] if versions else None
            except Exception:
                problems.append('versions.json is unreadable')
            if entry is None and not problems:
                problems.append('no version recorded')
            elif entry:
                versioned = os.path.join(out_dir, entry.get('file') or '')
                if not entry.get('file'):
                    problems.append('the latest record names no file')
                elif not os.path.isfile(versioned):
                    problems.append(f'the recorded file {entry.get("file")} is missing')
                if entry.get('title') and score.get('title') and entry['title'] != score.get('title'):
                    problems.append(f'version title "{entry["title"]}" is not the score title "{score["title"]}"')
                if not entry.get('change'):
                    problems.append('the latest version records no change')
        lvl = 'PASS' if not problems else ('WARN' if len(problems) <= limit else 'WARN')
        detail = (f"version v{entry['version']:02d} ({entry.get('file')}): {entry.get('change')}"
                  if entry and not problems else 'version: ' + '; '.join(problems))
        out.append((lvl, 'meta', detail))


def run_gate(score_path, wav_path=None, refresh=True, stems=None, score=None):
    """refresh=False: the caller has just rendered this score in this process, so the renderer's counters are already
    current and the gate does not render the stems a second time (a full render takes minutes).

    score=: use this in-memory score instead of reading score_path. pipeline.py renders in this process, so it passes
    its own score and this function is the only list of gate rows anything uses (there is no second, hand-copied list)."""
    import presets
    s_dir = os.path.dirname(os.path.abspath(score_path)) if score_path else None
    if s_dir:
        presets.add_project(s_dir)
        presets.add_project(os.path.dirname(s_dir))
    if score is None:
        if not score_path:
            raise ValueError('run_gate needs a score_path or a score dict')
        score = json.load(open(score_path, encoding='utf-8'))
    rendered = wav_path
    if rendered is None:
        import mixer
        rendered = os.path.splitext(score_path)[0] + '_gate.wav'
        stems, _ = rn.build_stems(score, verbose=False)
        mixer.mix_and_master(score, stems, rendered)
    elif refresh:
        rn.build_stems(score, verbose=False)          # refresh the renderer counters for this score
    out = []
    score_checks(score, out)
    render_checks(out)
    audio_checks(rendered, score, out)
    immersive_rows(score, rendered, stems, out)
    ambient_fusion_rows(score, rendered, stems, out=out)
    import ambience_reference as ar                     # WARN only: a render far from its measured real recordings
    dirs = [d for d in (s_dir, os.path.dirname(s_dir) if s_dir else None) if d]
    out.extend(ar.gate_rows(score, stems, dirs))
    import sfx_eval                                     # WARN only: a sound that behaves unlike its own physics
    out.extend(sfx_eval.gate_rows(score, stems))
    balance_rows(score, stems, out=out)
    spatial_separation_rows(score, stems, out=out)
    equal_loudness_rows(score, stems, out=out)
    vocal_rows(score, stems, out=out)
    chroma_concordance_rows(score, rendered, stems, out=out)
    kick_grid_rows(score, stems, out=out)
    soul_rows(score, out)
    if stems is not None:
        out.extend(masking_rows(stems, score))
        out.extend(nc.modulation_flutter_check(stems, score))
    project_dir = os.path.dirname(s_dir) if s_dir else None
    metadata_rows(score, out, project_dir=project_dir)
    return out, rendered


def vocal_rows(score, stems=None, out=None, sr=44100, report=None):
    """Vocal tracks, from the vocal engine's own report (render_natural.REPORT[track]['vocal']) and the raw stems.
    Measurable faults only: non-finite or DC-offset stems, clicks at note joins, phrases past breath capacity, a
    'choir' that is one voice copied, pitch far from the written note, level that ignores velocity, a hum that is
    bright. It cannot say whether the voice sounds human or the phrasing is musical: listen."""
    import gate_profiles
    rows = []
    gp = gate_profiles.resolve(score)
    rep = rn.REPORT if report is None else report
    for tr in score.get('tracks', []):
        name = tr.get('name')
        v = (rep.get(name) or {}).get('vocal')
        if not v:
            continue
        tag = f'vocal "{name}"'
        dc_max = gp.param('vocal.integrity', 'dc_max')
        if not v.get('finite', True) or v.get('dc', 0.0) > dc_max:
            rows.append(('FAIL', 'vocal', f'{tag}: stem has NaN/Inf or DC offset {v.get("dc", 0):.4f} (limit {dc_max})'))
        elif v.get('peak_pre_limit', 0.0) > 0.98:
            rows.append(('WARN', 'vocal', f'{tag}: the soft limiter engaged (pre-limit peak {v["peak_pre_limit"]:.2f}); lower dynamics.level_scale or gain_db'))
        else:
            rows.append(('PASS', 'vocal', f'{tag}: finite, DC {v.get("dc", 0):.1e}, peak {v.get("peak", 0):.2f}, no limiter hit'))
        if gp.on('vocal.clicks'):
            st = None if stems is None else stems.get(name)
            if st is None:
                rows.append(('INFO', 'vocal', f'{tag}: stem not available, click check skipped'))
            else:
                mono = st.mean(axis=1) if st.ndim == 2 else st
                n_click = len(find_clicks(mono))
                lim = int(gp.param('vocal.clicks', 'max_clicks'))
                rows.append(('FAIL' if n_click > lim else 'PASS', 'vocal',
                             f'{tag}: {n_click} click(s) in the stem (limit {lim})' + ('; check note joins and attack' if n_click > lim else '')))
        if gp.on('vocal.breath') and v.get('capacity_s'):
            lim = v['capacity_s'] * gp.param('vocal.breath', 'over_capacity_factor')
            if v.get('longest_phrase_s', 0.0) > lim:
                rows.append(('WARN', 'vocal', f'{tag}: a phrase runs {v["longest_phrase_s"]:.1f} s, past one breath ({lim:.1f} s). '
                                              f'Leave a rest of 0.3 s or more, or raise breathing.capacity_s'))
            else:
                rows.append(('PASS', 'vocal', f'{tag}: longest phrase {v.get("longest_phrase_s", 0):.1f} s within one breath ({lim:.1f} s); '
                                              f'{v.get("inhales", 0)} inhale(s) placed, {v.get("no_room_phrases", 0)} phrase(s) without room for one'))
        if gp.on('vocal.ensemble') and v.get('voices', 1) >= 3:
            lim = gp.param('vocal.ensemble', 'max_corr')
            c = v.get('max_corr')
            if c is not None:
                rows.append(('FAIL' if c > lim else 'PASS', 'vocal',
                             f'{tag}: strongest voice-to-voice correlation {c:.2f} (limit {lim})'
                             + ('; the voices are one singer copied: raise ensemble.diversity or lower cohesion' if c > lim else '')))
        if gp.on('vocal.intonation') and v.get('phrases'):
            lim = gp.param('vocal.intonation', 'max_cents')
            if v.get('mean_abs_dev_cents', 0.0) > lim:
                rows.append(('FAIL', 'vocal', f'{tag}: mean pitch error {v["mean_abs_dev_cents"]:.0f} cents (limit {lim:.0f})'))
            elif v.get('max_abs_dev_cents', 0.0) > 2 * lim:
                rows.append(('WARN', 'vocal', f'{tag}: one note is {v["max_abs_dev_cents"]:.0f} cents from the written pitch (limit {2 * lim:.0f})'))
            else:
                rows.append(('PASS', 'vocal', f'{tag}: pitch within {v.get("mean_abs_dev_cents", 0):.0f} cents of the score on average (vibrato excluded)'))
        if gp.on('vocal.dynamics'):
            c = v.get('dyn_corr')
            if c is None:
                rows.append(('INFO', 'vocal', f'{tag}: velocities too uniform to test that level follows velocity'))
            else:
                lim = gp.param('vocal.dynamics', 'min_corr')
                rows.append(('FAIL' if c < lim else 'PASS', 'vocal',
                             f'{tag}: note level vs velocity correlation {c:.2f} (min {lim})'
                             + ('; levels are being normalised or flattened' if c < lim else '')))
        if gp.on('vocal.hum_tone') and v.get('hum_hf_frac') is not None:
            lim = gp.param('vocal.hum_tone', 'max_hf_frac')
            f = v['hum_hf_frac']
            rows.append(('WARN' if f > lim else 'PASS', 'vocal', f'{tag}: hum energy above 1.5 kHz {f:.1e} (limit {lim})'
                         + ('; too bright for a closed-mouth hum: lower humming.brightness' if f > lim else '')))
    if out is not None:
        out.extend(rows)
    return rows


def chroma_concordance_rows(score, rendered_path, stems=None, out=None, sr=44100):
    """Harmonic Concordance Check:
    Verifies that ambient beds / nature tracks do not introduce dissonant semitone collisions
    (minor 2nd intervals) against the song's root tonic or active chord tones."""
    rows = []
    import gate_profiles
    gp = gate_profiles.resolve(score)
    if not stems or not gp.on('chroma.concordance'):
        return rows
    max_diss = gp.param('chroma.concordance', 'max_dissonance')
    env_tracks = [t['name'] for t in score.get('tracks', [])
                  if t.get('role') == 'environment' or str(t.get('instrument', '')).startswith('env:')]
    if not env_tracks:
        return rows

    # Get song root key pitch class
    key_str = score.get('key', 'C')
    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    ENHARMONIC = {'DB': 'C#', 'EB': 'D#', 'FB': 'E', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#', 'CB': 'B'}
    raw_root = key_str.split()[0].replace('m', '').replace('minor', '').replace('major', '').capitalize()
    root_name = ENHARMONIC.get(raw_root.upper(), raw_root)
    root_pc = NOTES.index(root_name) if root_name in NOTES else 0
    dissonant_pcs = [(root_pc + 1) % 12, (root_pc + 11) % 12]
    
    for name in env_tracks:
        if name in stems:
            c = nc.chroma_profile(stems[name], sr)
            diss_energy = float(c[dissonant_pcs].sum())
            if diss_energy > max_diss:
                rows.append(('WARN', 'harmonic_concordance',
                             f'ambient track "{name}" has high dissonant semitone energy ({diss_energy*100:.1f}%) against key {root_name}. Retune or notch'))
            else:
                rows.append(('PASS', 'harmonic_concordance',
                             f'ambient track "{name}" is harmonically concordant with key {root_name} (dissonance {diss_energy*100:.1f}% <= {max_diss*100:.0f}%)'))
    if out is not None:
        out.extend(rows)
    return rows


def kick_grid_rows(score, stems=None, out=None, sr=44100):
    """Kick-Drum Beat-Grid Lock:
    Calculates low-frequency transient arrival times and checks them against the tempo grid."""
    rows = []
    import gate_profiles
    gp = gate_profiles.resolve(score)
    if not stems or not gp.on('kick.grid'):
        return rows
    min_lock = gp.param('kick.grid', 'min_lock')
    drum_stems = [stems[t['name']] for t in score.get('tracks', [])
                  if t.get('role') == 'drum' and t['name'] in stems]
    if not drum_stems:
        return rows
    bpm = score.get('bpm', 120.0)
    spb = 60.0 / bpm
    dm = drum_stems[0].mean(axis=1) if drum_stems[0].ndim == 2 else drum_stems[0]
    from scipy.signal import butter, sosfilt
    sos = butter(4, min(140.0, sr * 0.45), 'low', fs=sr, output='sos')
    kick = sosfilt(sos, dm)
    on = nc.onsets(kick[:, np.newaxis], sr)
    if len(on) >= 4:
        rem = (on % spb)
        dist = np.minimum(rem, spb - rem)
        within40 = float((dist <= 0.040).sum() / len(dist))
        if within40 >= min_lock:
            rows.append(('PASS', 'kick_grid', f'{within40*100:.0f}% of kick transients lock within 40 ms of the {bpm:.0f} BPM beat grid'))
        else:
            rows.append(('INFO', 'kick_grid', f'{within40*100:.0f}% of kick transients within 40 ms of {bpm:.0f} BPM grid (loose / humanized swing)'))
    if out is not None:
        out.extend(rows)
    return rows


def soul_rows(score, out):
    """The soul gate (scripts/soul_check.py): runs when the score names its cultures (a fusion or a soul block)."""
    import soul
    import soul_check
    cultures = (score.get('fusion') or {}).get('cultures') or score.get('soul_cultures')
    if not cultures:
        return
    req = soul.merged(cultures, score.get('soul'))
    out.extend(soul_check.check(score, req))


def report(out, path):
    print(f'quality gate: {path}')
    for level, name, detail in out:
        print(f'  [{level:4s}] {name:12s} {detail}')
    fails = sum(1 for l, _, _ in out if l == 'FAIL')
    warns = sum(1 for l, _, _ in out if l == 'WARN')
    print(f'result: {fails} FAIL, {warns} WARN')
    print('not checked by code: whether the phrasing sounds human, cultural correctness, taste, real-player feel. Listen.')
    return fails


def selftest():
    """The renderer's pitch-bend range and channel rules, measured on audio; then the acoustic score rules in both
    directions (a MIDI-style score trips them, a composed score does not). Fails on the old 200-cent limit."""
    import humanize as hz
    import soundbank as sb
    sf = sb.ensure_soundfont()
    tm = hz.TempoMap(60, total_beats=8)
    # 1. a flute A4 bent up 300 cents must sound at 440 * 2^(300/1200) = 523.25 Hz
    tr = dict(name='bend', instrument='flute', role='melody', per_note_channels=True, vibrato=dict(depth_cents=0),
              expression='flat', notes=[dict(t=0, d=4, p=69, v=0.7, c=300.0)])
    rn.STATS.update(clipped=0, collisions=0)
    x = rn.render_track(tr, tm, sf, None, 'natural', 1, [4, 4], 0.5)
    mono = x.mean(axis=1) if x.ndim == 2 else x
    sr = rn.SR
    seg = mono[int(1.5 * sr):int(3.0 * sr)] * np.hanning(int(1.5 * sr))
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    spec = np.abs(np.fft.rfft(seg))
    band = (f > 400) & (f < 700)
    peak = f[band][np.argmax(spec[band])]
    expect = 440 * 2 ** (300 / 1200)
    assert abs(peak - expect) < 4, f'bent 300 cents: peak {peak:.1f} Hz, expected {expect:.1f} Hz'
    assert rn.STATS['clipped'] == 0, rn.STATS
    print(f'ok: +300 cents rendered at {peak:.1f} Hz (expected {expect:.1f})')
    # 2. twenty notes at once on one track must trip the channel-collision counter; one note must not
    rn.STATS.update(clipped=0, collisions=0)
    rn.render_track(dict(tr, notes=[dict(t=0, d=4, p=60 + i, v=0.6, c=10.0) for i in range(20)]), tm, sf, None, 'natural', 1, [4, 4], 0.5)
    crowded = rn.STATS['collisions']
    assert crowded > 0, 'collision counter did not fire'
    rn.STATS.update(clipped=0, collisions=0)
    rn.render_track(tr, tm, sf, None, 'natural', 1, [4, 4], 0.5)
    assert rn.STATS['collisions'] == 0, rn.STATS
    print(f'ok: 20 simultaneous microtone notes gave {crowded} channel collisions; one note gave 0')
    # 3. the click detector: a clean tone and a fast-attack kick have none; an injected jump is found
    sr = rn.SR
    t = np.arange(sr) / sr
    tone = 0.5 * np.sin(2 * np.pi * 220 * t)
    kick = 0.9 * np.sin(2 * np.pi * 55 * t) * np.exp(-t * 8)
    assert len(find_clicks(tone)) == 0 and len(find_clicks(kick)) == 0, 'false click on clean material'
    jumped = tone.copy()
    jumped[sr // 2] += 0.8
    assert list(find_clicks(jumped)) == [sr // 2 - 1], find_clicks(jumped)
    burst = tone.copy()
    burst[sr // 2:sr // 2 + 40] += 0.7 * np.sign(np.sin(np.arange(40) * 2.5))   # a dense burst: not a click
    assert len(find_clicks(burst)) == 0, 'a cymbal-like burst was counted as a click'
    print('ok: clean tone and a fast-attack kick give no clicks; an isolated jump is found; a dense burst is not')
    # 4. the acoustic rules (references/quality-gate.md, SKILL.md): a score written like a MIDI file trips every
    # FAIL row, and a score from compose.py trips none. Both directions matter: a rule that never fires is dead.
    bad = dict(ts=[4, 4], room='hall', tracks=[
        dict(name='keys', instrument='piano', role='chord',
             notes=[dict(t=b, d=1.0, p=p, v=0.6) for b in range(4) for p in (60, 64, 67)]
                   + [dict(t=0, d=0.8, p=60, v=0.9)]),        # the same pitch twice on one beat
        dict(name='gtr', instrument='acoustic_guitar', role='chord',
             notes=[dict(t=i, d=0.2, p=52 + i % 5, v=0.6, art='staccato') for i in range(10)]),
        dict(name='drums', instrument='drums', role='drum',
             notes=[dict(t=i * 0.5, d=0.5, p=p, v=0.5) for i in range(8) for p in ('snare', 'clap')]),
        dict(name='pad', instrument='strings', role='pad',
             notes=[dict(t=b, d=2.0, p=p, v=0.5) for b in range(4) for p in (45, 48, 52)]),
    ])
    hits = {n for level, n, _ in pattern_audit.acoustic_checks(bad) if level == 'FAIL'}
    want = {'note_collision', 'chord_voicing_and_strum', 'choked_resonance', 'machine_gun_percussion',
            'percussion_flam', 'low_interval_mud'}
    assert want <= hits, f'acoustic rules missed: {sorted(want - hits)}'
    print(f'ok: a MIDI-style score trips {len(want)} acoustic rules')

    # 5. Psychoacoustic & Cognitive Gate tests:
    # 5.1 Cochlear sensory roughness on a harsh low-register cluster
    # inside the measured roughness band (200-4000 Hz) and a real semitone cluster, not a low fifth that only the kernel calls rough
    t_rough = np.arange(int(sr * 3)) / sr
    harsh_cluster = 0.4 * np.sin(2 * np.pi * 262 * t_rough) + 0.4 * np.sin(2 * np.pi * 277 * t_rough) + 0.4 * np.sin(2 * np.pi * 294 * t_rough)
    r_rows, r_metrics = nc.cochlear_roughness_check(harsh_cluster, sr=sr)
    assert any(r[0] == 'FAIL' and r[1] == 'cochlear_roughness' for r in r_rows), f'cochlear roughness check missed harsh cluster: {r_rows}'
    print(f'ok: cochlear roughness check correctly caught harsh cluster (max roughness {r_metrics["max_roughness"]:.3f})')

    # 5.1b Amplitude flutter at 6-25 Hz: a 12 Hz tremolo is flagged, a steady tone and a 3 Hz sway are not
    t_fl = np.arange(int(sr * 4)) / sr
    carrier = np.sin(2 * np.pi * 440 * t_fl)
    fl_score = dict(tracks=[dict(name='s', role='pad')])
    flags = lambda am: [r[0] for r in nc.modulation_flutter_check({'s': 0.3 * carrier * am}, fl_score, sr)]
    assert flags(1 + 0.4 * np.sin(2 * np.pi * 12 * t_fl)) == ['WARN'], 'flutter check missed a 12 Hz tremolo'
    assert flags(np.ones_like(t_fl)) == ['PASS'], 'flutter check flagged a steady tone'
    assert flags(1 + 0.4 * np.sin(2 * np.pi * 3 * t_fl)) == ['PASS'], 'flutter check flagged a 3 Hz sway'
    print('ok: flutter check flags a 12 Hz tremolo and passes a steady tone and a 3 Hz sway')

    # 5.2 Witek-Vuust hyper-syncopated drum pattern trips BSI > 5.5
    hyper_drums = dict(ts=[4, 4], tracks=[dict(name='d', role='drum', notes=[dict(t=b + 0.25, d=0.1, v=0.9) for b in range(16)] + [dict(t=b + 0.75, d=0.1, v=0.9) for b in range(16)])])
    w_rows = pattern_audit.witek_groove_curve(hyper_drums)
    assert any(r[0] == 'FAIL' and r[1] == 'witek_groove_curve' for r in w_rows), f'witek groove check missed metric collapse: {w_rows}'
    print('ok: Witek groove curve caught hyper-syncopated metric collapse (BSI > 5.5)')

    # 5.3 Chaotic score with sawtooth melody, unresolved tension, and chaotic drum autocorrelation
    rng = np.random.default_rng(123)
    chaotic = dict(
        key='C major', ts=[4, 4], room='hall',
        tracks=[
            dict(name='pad', role='chord', instrument='piano', notes=[dict(t=0, d=24, p=p, v=0.5) for p in (60, 64, 67)]),
            dict(name='saw', role='melody', instrument='violin', notes=[dict(t=i*1.0, d=0.9, p=60 if i % 2 == 0 else 67, v=0.7) for i in range(10)]),
            dict(name='tension', role='lead', instrument='flute', notes=[dict(t=i*1.0, d=0.8, p=61 if i % 2 == 0 else 67, v=0.7) for i in range(6)]),
            dict(name='drums', role='drum', instrument='drums', notes=[dict(t=float(t), d=0.1, p='snare', v=0.6) for t in sorted(rng.uniform(0.1, 24.0, 30))])
        ]
    )
    c_rows = pattern_audit.cognitive_feel_checks(chaotic)
    c_fails = {r[1] for r in c_rows if r[0] == 'FAIL'}
    assert 'melodic_contour_feel' in c_fails, f'melodic_contour_feel missed: {c_fails}'
    assert 'harmonic_resolution_feel' in c_fails, f'harmonic_resolution_feel missed: {c_fails}'
    assert 'groove_pocket_lock' in c_fails, f'groove_pocket_lock missed: {c_fails}'
    print('ok: cognitive feel checks caught sawtooth contour, ungrounded tension leap, and chaotic groove pocket')

    # 5.4 Natural composed score passes all acoustic and cognitive rules
    import compose
    good = compose.compose(dict(emotion='motivational', duration_s=45, seed=7))
    left = [r for r in pattern_audit.acoustic_checks(good) if r[0] == 'FAIL']
    assert not left, f'a composed score fails an acoustic/cognitive rule: {left[:1]}'
    print('ok: a composed motivational score passes every acoustic & cognitive rule (0 FAILs)')

    # vocal rows: a clean report passes, and each fault trips its own row (negative controls)
    sc = {'tracks': [{'name': 'v', 'role': 'pad'}]}
    clean = dict(voices=5, phrases=2, longest_phrase_s=3.0, capacity_s=7.0, mean_abs_dev_cents=8.0, max_abs_dev_cents=20.0,
                 dyn_corr=0.9, max_corr=0.2, hum_hf_frac=1e-4, finite=True, dc=1e-6, peak_pre_limit=0.3, peak=0.3)
    ok = vocal_rows(sc, {'v': np.zeros((44100, 2))}, report={'v': {'vocal': clean}})
    assert ok and not [r for r in ok if r[0] in ('FAIL', 'WARN')], ok
    for fault, want in ((dict(finite=False), 'FAIL'), (dict(max_corr=0.97), 'FAIL'), (dict(dyn_corr=0.0), 'FAIL'),
                        (dict(longest_phrase_s=20.0), 'WARN'), (dict(hum_hf_frac=0.5), 'WARN')):
        bad = vocal_rows(sc, {'v': np.zeros((44100, 2))}, report={'v': {'vocal': dict(clean, **fault)}})
        assert any(r[0] == want for r in bad), (fault, bad)
    print('ok: vocal rows pass a clean vocal report and catch NaN, a copied choir, flat dynamics, a breathless phrase, a bright hum')
    print('selftest passed')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('score', nargs='?')
    ap.add_argument('wav', nargs='?')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not a.score:
        ap.error('give a score.json (and optionally its rendered wav), or --selftest')
    out, rendered = run_gate(a.score, a.wav)
    sys.exit(1 if report(out, rendered) else 0)


if __name__ == '__main__':
    main()
