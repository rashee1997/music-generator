# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
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
"""scene_gate.py - the rows that judge a piece against its own scenes.

A profile that declares a `scene` block points at the project's direction sheet (`scripts/scene_timeline.py` reads the
windows). These rows then ask the questions a whole-piece scalar cannot:

    scene.preset          the block validates (FAIL), and which sheet it read
    scene.arc_step        a peak stands measurably above the build that set it up
    scene.hit_surprise    a hard hit point has a surprise on it (IDyOM IC, and a level delta when audio is measured)
    scene.release_delta   the tension comes down into the release
    scene.macro_contrast  the piece has a dynamic range, a tension variance and a roughness contrast
    scene.silence_honoured  a declared rest really is silent
    scene.bed_stability   the beds rest where the sheet says silence
    scene.dialogue_mask   the figure keeps its ERB margin while a voice speaks (emitted by quality_gate.masking_rows,
                          where that measurement already lives)

Every floor is a row parameter (`gate_profiles.ROWS`), so a project sets it in `rows` with a range and a reason - one
figure, one home. With no `scene` block the module emits nothing: a piece that has not declared scenes is judged exactly
as it was. A declared block whose sheet cannot be found makes every row INFO ("not run"), never a pass.

What these rows deliberately do not do: they do not measure taste, they do not re-render, and they cannot make a flat
piece good. They make a flat piece fail a profile that asked for contrast, which is the point.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gate_profiles
import naturalness_check as nc
import pattern_audit
import scene_timeline


def _row(out, level, name, detail):
    out.append((level, name, detail))


def _a(tl, key, default=None):
    """One analysis mechanic from the scene contract (references/data/presets/gate/data/scene_roles.json).

    Nothing here is a door: a profile cannot move these, so they are plain values in the JSON rather than row parameters.
    The codes that read them name the JSON key, never the role string or the hit class, so the vocabulary stays in data.
    """
    return (getattr(tl, 'doc', {}) or {}).get('analysis', {}).get(key, default)


def _kind(tl, role):
    """A section role's kind, from the contract's `roles` block ('setup', 'approach', 'peak', ...)."""
    return ((tl.doc.get('roles') or {}).get(role) or {}).get('kind')


def _spans_of_kind(tl, key):
    """The sheet's sections whose role has the kind the contract names under `analysis.<key>`."""
    want = _a(tl, key)
    return [s for s in tl.spans if want is not None and _kind(tl, s['role']) == want]


def _role_allows(tl, role, key):
    """Whether the role's own contract mentions a key: the sheet, not this module, says which roles carry evidence."""
    spec = (tl.doc.get('roles') or {}).get(role) or {}
    return key in (spec.get('required') or []) + (spec.get('allowed') or [])


def _accent_kinds(tl):
    """The hit kinds that count as an accent, from the film hits preset's own classes (analysis.accent_classes)."""
    try:
        import presets
        doc = presets.load('film').get('hits') or {}
    except Exception:
        return set()
    classes = doc.get('classes') or {}
    out = set()
    for name in (_a(tl, 'accent_classes', []) or []):
        out |= set((classes.get(name) or {}).get('kinds') or [])
    return out


def _audio(path):
    if not path or not os.path.isfile(path):
        return None, None
    try:
        return nc.load(path)
    except (OSError, RuntimeError, ValueError):
        return None, None


def _rms_dbfs(x, a, b, sr):
    mono = x.mean(axis=1) if x.ndim == 2 else x
    seg = mono[int(a * sr):int(b * sr)]
    if not len(seg):
        return None
    return float(20.0 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12))


def _lufs(x, a, b, sr):
    seg = x[int(a * sr):int(b * sr)]
    if len(seg) < int(0.4 * sr):
        return None
    sig = seg[:, :2] if seg.ndim == 2 else np.column_stack([seg, seg])
    try:
        v = float(nc.lufs_meter(sig, sr))
    except Exception:
        return None
    return v if np.isfinite(v) else None


def _strain(score, tl):
    """(strain per two-bar window, window centres in seconds) from Chew's series the archive already computes."""
    s = pattern_audit._spiral_series(score)
    if s is None:
        return None, None
    CEs, _T_cds, CE_key, N, w_len = s
    T = np.array([float(np.linalg.norm(ce - CE_key)) for ce in CEs])
    centres = np.array([tl.beat_to_s((i + 0.5) * w_len) for i in range(N)])
    return T, centres


def _mean_between(values, centres, a, b):
    if values is None or not len(values):
        return None
    m = (centres >= a) & (centres < b)
    return float(values[m].mean()) if m.any() else None


def _melody_surprise(score, tl):
    """[(track, onsets_s, z of information content)] for every figure line long enough to standardise."""
    lines = []
    min_notes = int(_a(tl, 'min_line_notes', 8))
    clip = float(_a(tl, 'z_clip', 3.0))
    for name, line in pattern_audit._melody_lines(score):
        ic = np.asarray(line.get('ic'), dtype=float)
        ok = ~np.isnan(ic)
        if ok.sum() < min_notes:
            continue
        vals = ic[ok]
        sd = float(np.std(vals))
        if sd <= 1e-9:
            continue
        z = np.clip((vals - float(np.mean(vals))) / sd, -clip, clip)
        onsets = [tl.beat_to_s(t) for t in np.asarray(line.get('onsets'))[ok]]
        lines.append((name, np.asarray(onsets), z))
    return lines


def _peak_hits(tl, row_cfg):
    """[(t, window_s, role)]: the accents the sheet places inside a role that asks for a surprise.

    A hit is an accent when the contract's `analysis.accent_sync` says so, or when its kind is one of the film hits
    preset's own accent classes: the two vocabularies are data, and neither is named here.
    """
    out = []
    default_ms = float(row_cfg.get('hit_window_ms') or tl.doc.get('default_hit_window_ms', 250))
    surprise_key = _a(tl, 'surprise_key', 'surprise_min_z')
    accent_sync = _a(tl, 'accent_sync', 'hard')
    accent_kinds = _accent_kinds(tl)
    for h in tl.hits:
        role = tl.role_at(h['t'])
        if role is None or not _role_allows(tl, role, surprise_key):
            continue
        if h.get('sync') != accent_sync and h.get('kind') not in accent_kinds:
            continue
        w_ms = float((tl.role_cfg(role) or {}).get('hit_window_ms', default_ms))
        out.append((h['t'], w_ms / 1000.0, role))
    return out


def rows(score, path=None, stems=None, out=None, gp=None, project_dir=None):
    """The scene rows for a score (and its rendered master, when the caller has one). [] when no scene is declared."""
    gp = gp or gate_profiles.resolve(score)
    scene = getattr(gp, 'scene', None) or {}
    res = out if out is not None else []
    if not scene:
        return res
    problems = gate_profiles.scene_problems(scene, f'gate/{gp.label}')
    if problems:
        _row(res, 'FAIL', 'scene.preset', '; '.join(problems))
        return res
    tl = scene_timeline.load(score, gp, project_dir)
    _row(res, 'INFO', 'scene.preset', scene_timeline.describe(tl))
    if tl is None or not tl.active:
        for rid in ('scene.arc_step', 'scene.hit_surprise', 'scene.release_delta', 'scene.macro_contrast',
                    'scene.silence_honoured', 'scene.bed_stability'):
            _row(res, 'INFO', rid, 'not measured: the scene block names no direction sheet with sections')
        return res

    x, sr = _audio(path)
    strain, centres = _strain(score, tl)
    behalf = res

    # ---- scene.arc_step ----------------------------------------------------
    peaks = _spans_of_kind(tl, 'peak_kind')
    builds = _spans_of_kind(tl, 'build_kind')
    if not peaks or not builds:
        _row(behalf, 'INFO', 'scene.arc_step', 'not measured: the sheet has no build followed by a peak')
    else:
        step_need = float(gp.param('scene.arc_step', 'arousal_step_min'))
        strain_need = float(gp.param('scene.arc_step', 'strain_step_min'))
        steps, bad = [], []
        for pk in peaks:
            before = [b for b in builds if b['end_s'] <= pk['start_s'] + tl.tolerance_s]
            if not before:
                continue
            bd = before[-1]
            st_pk = _mean_between(strain, centres, pk['start_s'], pk['end_s'])
            st_bd = _mean_between(strain, centres, bd['start_s'], bd['end_s'])
            ar_pk = _lufs(x, pk['start_s'], pk['end_s'], sr) if x is not None else None
            ar_bd = _lufs(x, bd['start_s'], bd['end_s'], sr) if x is not None else None
            if st_pk is not None and st_bd is not None:
                steps.append(f"strain {bd['name']}->{pk['name']} {st_pk - st_bd:+.3f}")
                if st_pk - st_bd < strain_need:
                    bad.append(f"Chew strain rises only {st_pk - st_bd:+.3f} ({bd['name']} {st_bd:.3f} -> {pk['name']} {st_pk:.3f}), "
                               f"floor {strain_need:g}")
            if ar_pk is not None and ar_bd is not None:
                # a level step is the crude form of the same question; report it, do not require it
                steps.append(f"level {ar_pk - ar_bd:+.1f} LU")
        detail = ('; '.join(steps) or 'no build/peak pair could be measured') + (f' (want +{strain_need:g} strain)' if strain_need else '')
        if bad:
            _row(behalf, 'FAIL', 'scene.arc_step', '; '.join(bad) + '. ' + detail)
        else:
            _row(behalf, 'PASS', 'scene.arc_step', detail)

    # ---- scene.hit_surprise ------------------------------------------------
    want_z = float(gp.param('scene.hit_surprise', 'surprise_min_z'))
    want_db = float(gp.param('scene.hit_surprise', 'delta_min_db'))
    min_hits = int(gp.param('scene.hit_surprise', 'min_hits'))
    hits = _peak_hits(tl, {'hit_window_ms': gp.param('scene.hit_surprise', 'hit_window_ms')})
    lines = _melody_surprise(score, tl)
    if not hits:
        _row(behalf, 'INFO', 'scene.hit_surprise', 'not measured: no hard hit sits inside a peak or rupture window')
    elif not lines:
        _row(behalf, 'INFO', 'scene.hit_surprise', 'not measured: the piece has no figure line long enough to standardise')
    else:
        found, missing = [], []
        for t_hit, win, role in hits:
            best = None
            for name, onsets, z in lines:
                m = (onsets >= t_hit - win) & (onsets <= t_hit + win)
                if m.any():
                    v = float(z[m].max())
                    if best is None or v > best[1]:
                        best = (name, v)
            delta = None
            if x is not None:
                lookback = float(_a(tl, 'delta_lookback_s', 1.0))
                a0, a1 = t_hit - lookback, t_hit
                b0, b1 = t_hit, t_hit + win
                l0, l1 = _lufs(x, max(0.0, a0), a1, sr), _lufs(x, b0, b1, sr)
                if l0 is not None and l1 is not None:
                    delta = l1 - l0
            ok = (best is not None and best[1] >= want_z) or (delta is not None and delta >= want_db)
            label = (f"'{best[0]}' z {best[1]:+.2f}" if best else 'no note in the window') + \
                    (f", level {delta:+.1f} LU" if delta is not None else '')
            if ok:
                found.append(f"{t_hit:.2f}s {role}: {label}")
            else:
                missing.append(f"{t_hit:.2f}s {role}: {label}")
        if missing:
            _row(behalf, 'FAIL', 'scene.hit_surprise',
                 f'{len(missing)} of {len(hits)} hard hit(s) have no surprise: ' + '; '.join(missing)
                 + f'. A hit needs {want_z:g} sd of information content inside +-{float(gp.param("scene.hit_surprise", "hit_window_ms")):.0f} ms, '
                   f'or a {want_db:g} LU level change. Write the leap, the register change or the impact on the hit')
        elif len(found) < min_hits:
            _row(behalf, 'WARN', 'scene.hit_surprise',
                 f'{len(found)} hard hit(s) with a surprise, the profile asks for {min_hits}: ' + '; '.join(found))
        else:
            _row(behalf, 'PASS', 'scene.hit_surprise', '; '.join(found))

    # ---- scene.release_delta ----------------------------------------------
    releases = _spans_of_kind(tl, 'release_kind')
    if not releases or not peaks:
        _row(behalf, 'INFO', 'scene.release_delta', 'not measured: the sheet has no peak followed by a release')
    else:
        drop_need = float(gp.param('scene.release_delta', 'strain_drop_min'))
        drops, bad = [], []
        for rel in releases:
            before = [p for p in peaks if p['end_s'] <= rel['start_s'] + tl.tolerance_s]
            if not before:
                continue
            pk = before[-1]
            st_pk = _mean_between(strain, centres, pk['start_s'], pk['end_s'])
            st_rl = _mean_between(strain, centres, rel['start_s'], rel['end_s'])
            if st_pk is None or st_rl is None:
                continue
            drops.append(f"strain {pk['name']}->{rel['name']} {st_rl - st_pk:+.3f}")
            if st_pk - st_rl < drop_need:
                bad.append(f"strain falls only {st_pk - st_rl:.3f} from {pk['name']} {st_pk:.3f} to {rel['name']} {st_rl:.3f}, "
                           f"floor {drop_need:g}")
        detail = '; '.join(drops) or 'no peak/release pair could be measured'
        if bad:
            _row(behalf, 'FAIL', 'scene.release_delta',
                 '; '.join(bad) + '. The release is a promise the sheet makes: move the harmony home, thin the texture or slow the pulse')
        else:
            _row(behalf, 'PASS', 'scene.release_delta', detail)

    # ---- scene.macro_contrast ---------------------------------------------
    need_sections = int(gp.param('scene.macro_contrast', 'min_sections'))
    force = bool(gp.param('scene.macro_contrast', 'force'))
    roles = tl.roles()
    if len(tl.spans) < need_sections and not force:
        _row(behalf, 'INFO', 'scene.macro_contrast',
             f'not measured: the sheet has {len(tl.spans)} section(s) and this profile measures contrast from {need_sections} '
             f'(set scene.macro_contrast.min_sections=1 or force=true to measure it anyway)')
    else:
        dr_need = float(gp.param('scene.macro_contrast', 'min_dynamic_range_lu'))
        tv_need = float(gp.param('scene.macro_contrast', 'min_tension_variance'))
        rc_need = float(gp.param('scene.macro_contrast', 'min_roughness_contrast_db'))
        parts, fails = [], []
        if strain is not None and len(strain) >= 2:
            tv = float(np.var(strain))
            parts.append(f'tension variance {tv:.3f} (floor {tv_need:g})')
            if tv < tv_need:
                fails.append(f'tension variance {tv:.3f} < {tv_need:g}: one harmonic state for the whole piece')
        if x is not None:
            lufs = [(s['name'], _lufs(x, s['start_s'], s['end_s'], sr)) for s in tl.spans]
            lufs = [(n, v) for n, v in lufs if v is not None]
            if len(lufs) >= 2:
                dr = max(v for _, v in lufs) - min(v for _, v in lufs)
                parts.append(f'dynamic range {dr:.1f} LU (floor {dr_need:g})')
                if dr < dr_need:
                    fails.append(f'dynamic range {dr:.1f} LU < {dr_need:g}: every section sits at one level')
            rough = []
            for s in tl.spans:
                sl = x[int(s['start_s'] * sr):int(s['end_s'] * sr)]
                if len(sl) < int(float(_a(tl, 'min_slice_s', 1.5)) * sr):
                    continue
                try:
                    _r, meta = nc.cochlear_roughness_check(sl, sr=sr)
                    rough.append(float(meta.get('mean_roughness') or 0.0))
                except Exception:
                    continue
            if len(rough) >= 2:
                # in dB of the roughness ratio, which is what the parameter is named in: 3 dB is 1.4x, not a raw 3.0 that
                # no roughness value in the archive ever reaches (they are 0.01-0.10)
                contrast = float(20.0 * np.log10((max(rough) + 1e-6) / (min(rough) + 1e-6)))
                parts.append(f'roughness contrast {contrast:.1f} dB (floor {rc_need:g})')
                if contrast < rc_need:
                    fails.append(f'roughness contrast {contrast:.1f} dB < {rc_need:g}: the roughest section is barely rougher '
                                 f'than the calmest')
        else:
            parts.append('dynamic range and roughness contrast not measured (no rendered audio)')
        detail = f'{len(tl.spans)} section(s), roles {", ".join(roles)}: ' + '; '.join(parts or ['nothing measurable'])
        if fails:
            _row(behalf, 'FAIL', 'scene.macro_contrast', '; '.join(fails) + '. ' + detail)
        elif x is None:
            _row(behalf, 'INFO', 'scene.macro_contrast', detail)
        else:
            _row(behalf, 'PASS', 'scene.macro_contrast', detail)

    # ---- scene.silence_honoured / scene.bed_stability ----------------------
    min_s = float(gp.param('scene.silence_honoured', 'min_s'))
    max_db = float(gp.param('scene.silence_honoured', 'max_dbfs'))
    windows = [(a, b) for a, b in tl.rests if b - a >= min_s]
    if not windows:
        _row(behalf, 'INFO', 'scene.silence_honoured', 'not measured: the sheet declares no rest window')
        _row(behalf, 'INFO', 'scene.bed_stability', 'not measured: the sheet declares no rest window')
    elif x is None:
        _row(behalf, 'INFO', 'scene.silence_honoured', 'not measured: no rendered audio')
        _row(behalf, 'INFO', 'scene.bed_stability', 'not measured: no rendered audio')
    else:
        # the room decays after the hit that opened the rest: read the level once that tail has had `tail_grace_s`
        grace = float(gp.param('scene.silence_honoured', 'tail_grace_s'))
        loud = [(a, b, _rms_dbfs(x, a + (grace if b - a - grace >= 0.1 else 0.0), b, sr)) for a, b in windows]
        loud = [(a, b, v) for a, b, v in loud if v is not None]
        bad = [(a, b, v) for a, b, v in loud if v > max_db]
        if bad:
            _row(behalf, 'FAIL', 'scene.silence_honoured',
                 'the sheet declares silence and the master is not silent there: '
                 + '; '.join(f'{a:.1f}-{b:.1f}s at {v:.0f} dBFS (limit {max_db:g})' for a, b, v in bad[:4])
                 + '. Stop the sustained voices on the hit; do not glide into the rest')
        else:
            _row(behalf, 'PASS', 'scene.silence_honoured',
                 f'{len(loud)} declared rest(s) are silent (loudest {max(v for _, _, v in loud):.0f} dBFS, limit {max_db:g})')
        env = {}
        for name, sig in (stems or {}).items():
            tr = next((t for t in score.get('tracks', []) if t.get('name') == name), None) or {}
            if tr.get('role') == 'environment' or str(tr.get('instrument', '')).startswith('env:'):
                env[name] = sig
        if not env:
            _row(behalf, 'INFO', 'scene.bed_stability', 'not measured: the piece has no environment stem to measure')
        else:
            bed_max = float(gp.param('scene.bed_stability', 'max_dbfs'))
            sits = []
            for name, sig in env.items():
                floor = float(_a(tl, 'silence_floor_dbfs', -120.0))
                v = max((_rms_dbfs(sig, a, b, sr) or floor) for a, b in windows)
                sits.append((name, v))
            worst = max(sits, key=lambda p: p[1])
            if worst[1] > bed_max:
                _row(behalf, 'FAIL', 'scene.bed_stability',
                     f'the bed "{worst[0]}" keeps sounding through a declared rest ({worst[1]:.0f} dBFS, limit {bed_max:g}): '
                     f'the scene asked for silence and the ambience did not follow')
            else:
                _row(behalf, 'PASS', 'scene.bed_stability',
                     'beds: ' + ', '.join(f'{n} {v:.0f} dBFS' for n, v in sits) + f' inside the declared rests (limit {bed_max:g})')
    return res
