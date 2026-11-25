# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""affect.py - a rendered piece's arousal and valence arc, compared with what the direction sheet promised.

Per section of the direction sheet the audio slice is measured with features the gate already has:

  loudness   integrated LUFS of the slice            (naturalness_check.lufs_meter)
  onsets     spectral-flux onsets per second         (naturalness_check.onsets)
  centroid   log spectral centroid of the slice      (Welch spectrum)
  mode       best major-template correlation minus best minor-template correlation over the 12 keys of the section's
             pitch-class profile (naturalness_check.chroma_analysis): -1..+1, absolute
  clash      energy in adjacent pitch classes of that profile: sum_i c_i * c_(i+1), a rough-chord proxy

arousal of a section = mean of the z-scores of loudness, onset rate and centroid across the sections (relative: an arc,
not a level). Valence of a section = mode - clash (absolute). Targets: the sheet's per-section `energy` for arousal, and
the valence of the brief's `intent.emotions` words (references/data/presets/intent/valence_arousal.json) for valence.

Both are starting values and neither is fitted to annotated data. Audio-only valence prediction is much weaker than
arousal prediction (knowledgebase/sound-design/valence-arousal.md), so the valence row can only warn, and neither row
is a statement about taste.
"""
import numpy as np
from scipy.signal import welch

import naturalness_check as nc
import presets

MIN_SECTION_S = 3.0
CLASH_WEIGHT = 1.0          # valence = mode - CLASH_WEIGHT * clash (starting value)


def _profiles():
    p = (presets.load('intent').get('valence_arousal') or {}).get('mode_profiles') or {}
    return np.asarray(p.get('major'), dtype=float), np.asarray(p.get('minor'), dtype=float)


def mode_score(chroma):
    """Major-minor template correlation difference of a 12-value pitch-class profile, -1..+1 (0 for a flat profile)."""
    c = np.asarray(chroma, dtype=float)
    if c.sum() <= 0.0 or np.std(c) < 1e-9:
        return 0.0
    maj, mnr = _profiles()
    best_maj = max(np.corrcoef(c, np.roll(maj, k))[0, 1] for k in range(12))
    best_min = max(np.corrcoef(c, np.roll(mnr, k))[0, 1] for k in range(12))
    return float(np.clip(best_maj - best_min, -1.0, 1.0))


def clash(chroma):
    c = np.asarray(chroma, dtype=float)
    if c.sum() <= 0.0:
        return 0.0
    c = c / c.sum()
    return float(np.sum(c * np.roll(c, -1)))


def section_features(x, sr):
    """The five measurements of one audio slice (stereo or mono)."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    stereo = x if x.ndim == 2 else np.column_stack([x, x])
    dur = len(mono) / float(sr)
    lufs = float(nc.lufs_meter(stereo[:, :2], sr)) if dur >= 0.4 else -70.0
    on = nc.onsets(stereo[:, :2] if stereo.ndim == 2 else mono, sr)
    f, p = welch(mono, sr, nperseg=4096)
    centroid = float(np.sum(f * p) / (np.sum(p) + 1e-30))
    ca = nc.chroma_analysis(stereo[:, :2], sr)
    chroma = ca['chroma'] if ca else np.zeros(12)
    return dict(lufs=lufs if np.isfinite(lufs) else -70.0, onset_rate=len(on) / max(dur, 1e-6),
                centroid=float(np.log2(max(centroid, 20.0))), mode=mode_score(chroma), clash=clash(chroma),
                tonal=bool(ca and ca['tonal_fraction'] > 0.0))


def _z(v):
    v = np.asarray(v, dtype=float)
    s = float(np.std(v))
    return (v - v.mean()) / s if s > 1e-9 else np.zeros_like(v)


def arc(x, sr, sections):
    """Per section: its features and the composite arousal and valence. `sections` is [(name, start_s, end_s)]. Sections
    shorter than MIN_SECTION_S are skipped (a profile of a few seconds says nothing about key or onset rate)."""
    feats, names, spans = [], [], []
    for name, a, b in sections:
        seg = x[int(a * sr):int(b * sr)]
        if len(seg) / float(sr) < MIN_SECTION_S:
            continue
        feats.append(section_features(seg, sr))
        names.append(name)
        spans.append((a, b))
    if not feats:
        return dict(sections=[], arousal=np.zeros(0), valence=np.zeros(0), names=[], spans=[])
    arousal = (_z([f['lufs'] for f in feats]) + _z([f['onset_rate'] for f in feats]) + _z([f['centroid'] for f in feats])) / 3.0
    valence = np.array([f['mode'] - CLASH_WEIGHT * f['clash'] for f in feats])
    return dict(sections=feats, arousal=arousal, valence=valence, names=names, spans=spans)


def target_valence(sheet):
    """Mean valence of the sheet's intent emotion words, or None when it names none that resolve."""
    import intent
    va = (presets.load('intent').get('valence_arousal') or {}).get('emotions') or {}
    words = ((sheet.get('intent') or {}).get('emotions')) or []
    vals = []
    for w in words:
        try:
            for kind, cid in intent.resolve_word(w):
                if kind == 'emotions' and cid in va:
                    vals.append(float(va[cid]['valence']))
        except Exception:
            continue
    return float(np.mean(vals)) if vals else None


def rows(score, sheet, path):
    """emotion.arc_arousal and emotion.arc_valence for a rendered file against its direction sheet (WARN / INFO only)."""
    import gate_profiles
    from scipy.stats import spearmanr
    gp = gate_profiles.resolve(score)
    want_a, want_v = gp.on('emotion.arc_arousal'), gp.on('emotion.arc_valence')
    out = []
    if not (want_a or want_v):
        return out
    secs = [(s.get('name', f'section {i + 1}'), float(s['start_s']), float(s['end_s']), s.get('energy'))
            for i, s in enumerate(sheet.get('sections') or []) if 'start_s' in s and 'end_s' in s]
    if not secs:
        return [('INFO', r, 'not measured: the direction sheet has no sections with start_s and end_s')
                for r in ('emotion.arc_arousal', 'emotion.arc_valence') if gp.on(r)]
    try:
        x, sr = nc.load(path)
    except (OSError, RuntimeError, ValueError) as exc:
        return [('INFO', r, f'not measured: the rendered file could not be read ({exc})')
                for r in ('emotion.arc_arousal', 'emotion.arc_valence') if gp.on(r)]
    a = arc(x, sr, [(n, s, e) for n, s, e, _ in secs])
    if not a['names']:
        return [('INFO', r, f'not measured: no section is {MIN_SECTION_S:g} s or longer') for r in ('emotion.arc_arousal', 'emotion.arc_valence') if gp.on(r)]
    energy = {n: en for n, s, e, en in secs}
    if want_a:
        pairs = [(float(energy[n]), float(v)) for n, v in zip(a['names'], a['arousal']) if energy.get(n) is not None]
        need = float(gp.param('emotion.arc_arousal', 'min_rho'))
        if len(pairs) < 3 or np.std([p[0] for p in pairs]) < 1e-9:
            out.append(('INFO', 'emotion.arc_arousal', f'not measured: {len(pairs)} section(s) with a distinct energy (need 3)'))
        else:
            rho = float(spearmanr([p[0] for p in pairs], [p[1] for p in pairs])[0])
            shown = ', '.join(f'{n} {v:+.1f}' for n, v in zip(a['names'], a['arousal']))
            out.append(('WARN' if rho < need else 'INFO', 'emotion.arc_arousal',
                        f'rank correlation of measured arousal with the sheet\'s section energy {rho:+.2f} over {len(pairs)} sections '
                        f'(want {need:+.2f} or more); measured: {shown}'
                        + ('. A section is not as active as the sheet says: change its density, level or register in the notes, not the sheet' if rho < need else '')))
    if want_v:
        target = target_valence(sheet)
        band = float(gp.param('emotion.arc_valence', 'neutral_band'))
        dur = np.array([b - s for s, b in a['spans']])
        got = float(np.average(a['valence'], weights=dur))
        if target is None:
            out.append(('INFO', 'emotion.arc_valence', f'measured valence {got:+.2f}; the sheet names no emotion word with coordinates'))
        else:
            bad = abs(target) >= band and abs(got) > 0.05 and np.sign(target) != np.sign(got)
            out.append(('WARN' if bad else 'INFO', 'emotion.arc_valence',
                        f'measured valence {got:+.2f} (major-minor template difference less clashing pitch classes) against the '
                        f'intent words\' {target:+.2f}' + ('; the mode or harmony reads the other way: audio-only valence is a weak '
                                                          'measure, listen before changing the notes' if bad else '')))
    return out
