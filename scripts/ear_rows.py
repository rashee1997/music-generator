# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""ear_rows.py - gate rows read from the virtual ear (scripts/ear_model): fatigue, masking, modulation roughness,
pitch salience and interaural correlation.

All five are advisory (INFO / WARN, never FAIL): the model's numbers are starting values, calibrated only on synthetic
fixtures (tests/test_ear_model.py, tests/fixtures/roughness). Known limits, said in the rows where they matter:

  * the hair cell saturates, so modulation depth falls as level rises: `ear.mod_roughness` under-reads loud material
    and does not reproduce the rise of roughness with level that `cochlear_roughness` (level_aware) models;
  * the neural activity pattern is sampled at 2240 Hz, so pitch salience covers fundamentals up to about 700 Hz;
  * fatigue is read at the file's own level: it is a proxy for sustained drive, not a measured neural quantity.

Remediations name the lever in the score or the presets, never a threshold.
"""
import numpy as np

import gate_profiles
import naturalness_check as nc


def _mono(x):
    x = np.asarray(x, dtype=np.float32)
    return x.mean(axis=1) if x.ndim == 2 else x


def _runs(flags):
    """[(start, length)] of consecutive True values."""
    out, start = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - start))
            start = None
    return out


def _row(out, level, name, detail):
    out.append((level, name, detail))


def summary_for(path):
    """The mono summary of a rendered master, or None when it cannot be read. One call, shared by the ear rows and
    the chem rows (the model takes about 6 s a minute of audio; it must not run twice in one gate pass)."""
    from ear_model import EarModel, Summariser
    try:
        master, sr = nc.load(path)
    except (OSError, RuntimeError, ValueError):
        return None
    return Summariser(EarModel(sr)).run(_mono(master))


def fatigue_row(gp, summary, master, sr, out):
    f_max = float(gp.param('ear.fatigue', 'f_max'))
    min_s = float(gp.param('ear.fatigue', 'min_seconds'))
    rng_lu = float(gp.param('ear.fatigue', 'lufs_range_lu'))
    fat, frame = summary['fatigue'], float(summary['frame_s'])
    st = nc.short_term(master, sr, win=3.0, hop=1.0)
    hits = []
    for start, length in _runs(fat > f_max):
        if length * frame < min_s:
            continue
        seg = st[start:start + length] if len(st) else np.array([])
        stable = len(seg) == 0 or (float(seg.max() - seg.min()) < rng_lu)
        if stable:
            hits.append((start * frame, length * frame, float(fat[start:start + length].mean())))
    peak = float(fat.max()) if len(fat) else 0.0
    if hits:
        t0, dur, val = max(hits, key=lambda h: h[1])
        _row(out, 'WARN', 'ear.fatigue',
             f'neural adaptation stays above {f_max:g} (mean {val:.2f}) for {dur:.0f} s from {t0:.0f} s while the short-term '
             f'loudness moves less than {rng_lu:g} LU: a sustained dense drive a loudness meter does not see. Thin the '
             f'pad (fewer voices), add rests or motion, lower the bed gain_db or high-pass it. Advisory: starting values')
    else:
        _row(out, 'INFO', 'ear.fatigue', f'adaptation index peaks at {peak:.2f} (warn above {f_max:g} for {min_s:g} s at stable loudness)')


def roughness_row(gp, summary, out):
    limit = float(gp.param('ear.mod_roughness', 'max_index'))
    need = int(gp.param('ear.mod_roughness', 'min_frames'))
    r = summary['roughness']
    runs = [(s, n) for s, n in _runs(r > limit) if n >= need]
    peak = float(r.max()) if len(r) else 0.0
    if runs:
        s, n = max(runs, key=lambda t: t[1])
        _row(out, 'WARN', 'ear.mod_roughness',
             f'30-150 Hz envelope modulation index stays above {limit:g} for {n} frames from {s * summary["frame_s"]:.0f} s '
             f'(peak {peak:.2f}). Name the clashing partials with `roughness_forecast.py diagnose`, then move the part. '
             f'Advisory: the hair cell saturates, so loud material is under-read')
    else:
        _row(out, 'INFO', 'ear.mod_roughness', f'modulation roughness index peaks at {peak:.2f} (warn above {limit:g} for {need} frames)')


def masking_row(gp, ear, score, stems, sr, out):
    import quality_gate
    from ear_model import Summariser
    lead, bed, _ = quality_gate.figure_and_bed(score, stems)
    if lead is None:
        _row(out, 'INFO', 'ear.masking', 'not measured: no figure stem against a bed in the focus roles')
        return
    a, b = Summariser(ear).run(_mono(stems[lead])), Summariser(ear).run(_mono(bed))
    n = min(len(a['fatigue']), len(b['fatigue']))
    fig, bd = a['excitation'][:n].astype(np.float64), b['excitation'][:n].astype(np.float64)
    active = fig.sum(axis=1) > 0.05 * (fig.sum(axis=1).max() + 1e-12)
    if not active.any():
        _row(out, 'INFO', 'ear.masking', 'not measured: the figure stem is silent')
        return
    shares = []
    for f, g in zip(fig[active], bd[active]):
        use = f > 0.05 * f.max()
        w = f[use] / f[use].sum()
        shares.append(float((w * f[use] / (f[use] + g[use] + 1e-12)).sum()))
    shares = np.asarray(shares)
    min_share = float(gp.param('ear.masking', 'min_share'))
    min_frames = float(gp.param('ear.masking', 'min_frames'))
    ok = float(np.mean(shares >= min_share))
    _row(out, 'WARN' if ok < min_frames else 'INFO', 'ear.masking',
         f'"{lead}" holds at least {min_share:.0%} of the neural activity in its own channels in {ok:.0%} of its active frames '
         f'(want {min_frames:.0%}); median share {np.median(shares):.2f}'
         + ('. The figure is buried by the beds: lane EQ, `lead_carve`, a lower bed level or a different register' if ok < min_frames else ''))


def pitch_row(gp, ear, summary_master, score, stems, sr, out):
    import quality_gate
    from ear_model import Summariser
    lead, _, _ = quality_gate.figure_and_bed(score, stems) if stems else (None, None, None)
    if lead is None:
        _row(out, 'INFO', 'ear.pitch_salience', 'not measured: no figure stem to follow in the mix')
        return
    alone = Summariser(ear).run(_mono(stems[lead]))
    n = min(len(alone['salience']), len(summary_master['salience']))
    pitched = alone['salience'][:n] >= 0.3
    if not pitched.any():
        _row(out, 'INFO', 'ear.pitch_salience', f'not measured: "{lead}" has no clear pitch below the 700 Hz limit of the model')
        return
    lo = float(gp.param('ear.pitch_salience', 'min_salience'))
    need = float(gp.param('ear.pitch_salience', 'min_frames'))
    sal, f0m = summary_master['salience'][:n][pitched], summary_master['f0_hz'][:n][pitched]
    f0a = alone['f0_hz'][:n][pitched]
    kept = (sal >= lo) & (np.abs(f0m / np.maximum(f0a, 1e-9) - 1.0) < 0.06)
    frac = float(kept.mean())
    _row(out, 'WARN' if frac < need else 'INFO', 'ear.pitch_salience',
         f'"{lead}" keeps its pitch (salience >= {lo:g}, same f0 within 6 %) in {frac:.0%} of its pitched frames (want {need:.0%})'
         + ('. The pitch is lost in the mix: raise the register, remove a co-registered bed, or change the timbre' if frac < need else ''))


def iacc_row(gp, ear_cls, master, sr, score, out):
    if master.ndim != 2 or master.shape[1] != 2:
        return
    import mixer
    from ear_model import BinauralSummariser
    ear_l, ear_r = ear_cls(sr), ear_cls(sr)
    v = BinauralSummariser(ear_l, ear_r).run(master[:, 0], master[:, 1])
    if not len(v):
        return
    lo, hi = float(gp.param('ear.iacc', 'min_iacc')), float(gp.param('ear.iacc', 'max_iacc'))
    mean = float(v.mean())
    strict = bool(mixer.immersive_cfg(score))
    bad = strict and not (lo <= mean <= hi)
    _row(out, 'WARN' if bad else 'INFO', 'ear.iacc',
         f'interaural correlation of the neural patterns, 500-880 Hz: mean {mean:.2f} (window {lo:g}..{hi:g}'
         f'{"" if strict else ", reported only: the piece is not immersive"})'
         + ('. Near 1 is a mono image, near 0 an unrelated pair: set the placement, widen or narrow the stems' if bad else ''))


def rows(score, path, stems=None, summary=None):
    """The ear rows for a rendered master (and its stems, when the caller has them). `summary` is a mono summary the
    caller already computed (`summary_for`), so a chem run in the same pass does not read the master twice."""
    from ear_model import EarModel, Summariser
    gp = gate_profiles.resolve(score)
    wanted = [r for r in ('ear.fatigue', 'ear.mod_roughness', 'ear.masking', 'ear.pitch_salience', 'ear.iacc') if gp.on(r)]
    out = []
    if not wanted:
        return out
    try:
        master, sr = nc.load(path)
    except (OSError, RuntimeError, ValueError) as exc:
        return [('INFO', r, f'not measured: the rendered file could not be read ({exc})') for r in wanted]
    ear = EarModel(sr)
    if summary is None and any(r in wanted for r in ('ear.fatigue', 'ear.mod_roughness', 'ear.pitch_salience')):
        summary = Summariser(ear).run(_mono(master))
    if 'ear.fatigue' in wanted:
        fatigue_row(gp, summary, master, sr, out)
    if 'ear.mod_roughness' in wanted:
        roughness_row(gp, summary, out)
    if stems and 'ear.masking' in wanted:
        masking_row(gp, ear, score, stems, sr, out)
    if stems and 'ear.pitch_salience' in wanted:
        pitch_row(gp, ear, summary, score, stems, sr, out)
    if 'ear.iacc' in wanted:
        iacc_row(gp, EarModel, master, sr, score, out)
    return out
