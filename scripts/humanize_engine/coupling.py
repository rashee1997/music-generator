# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Cross-track phase coupling: players correcting toward each other, as an opt-in score block.

A real ensemble is not a set of parts each with its own stable offset; players hear an asynchrony and
correct it. The measured model is a first-order linear phase correction: each onset is pulled toward the
reference by a fraction of the observed asynchrony (J. R. Soc. Interface 2014, optimal correction gain).
Listeners with ensemble experience can hear that coordination structure (PLOS One 2025).

The correction is computed once per piece, before the parallel render, from every part's humanized
events. Each part then carries its own bounded correction curve, so a stem can still be cached: the key
includes that part's curve, and a part whose curve did not change reuses its audio.

    "coupling": {"mode": "phase", "gain": 0.6, "anchor": "auto", "window_beats": 2, "cap_ms": 25}

`mode: "off"` (the default) changes nothing. `gain` is the correction gain (a starting value at 0.6, the
value the first-order model predicts for minimal asynchrony variance); `anchor: "auto"` uses the drums,
then the bass, then the first named part; `window_beats` smooths the curve so a correction does not
jitter note to note; `cap_ms` bounds what one player can be moved by the coupling.
"""
import numpy as np

COUPLING_KEYS = ('mode', 'gain', 'anchor', 'window_beats', 'cap_ms')
MODES = ('off', 'phase')


def resolve_block(score):
    """The validated coupling block of a score; absent -> mode 'off'."""
    blk = (score or {}).get('coupling') or {}
    if not isinstance(blk, dict):
        raise ValueError(f"score.coupling must be an object, got {type(blk).__name__}")
    unknown = sorted(set(blk) - set(COUPLING_KEYS))
    if unknown:
        raise ValueError(f"score.coupling: unknown key(s) {', '.join(unknown)}; known: {', '.join(COUPLING_KEYS)}")
    mode = str(blk.get('mode', 'off') or 'off').lower()
    if mode not in MODES:
        raise ValueError(f"score.coupling.mode: expected one of {', '.join(MODES)}, got {mode!r}")
    gain = float(blk.get('gain', 0.6))
    if not 0.0 <= gain <= 1.5:
        raise ValueError('score.coupling.gain: expected 0..1.5')
    cap_ms = float(blk.get('cap_ms', 25.0))
    if not 0.0 <= cap_ms <= 80.0:
        raise ValueError('score.coupling.cap_ms: expected 0..80')
    window = float(blk.get('window_beats', 2.0))
    if not 0.0 <= window <= 16.0:
        raise ValueError('score.coupling.window_beats: expected 0..16')
    return dict(mode=mode, gain=gain, anchor=str(blk.get('anchor', 'auto') or 'auto'),
                window_beats=window, cap_ms=cap_ms)


def _pick_anchor(parts, roles, wanted):
    """The reference part: an explicit name, or drums -> bass -> the first named part."""
    if wanted and wanted != 'auto':
        return wanted if wanted in parts else sorted(parts)[0]
    for family in (('drums', 'drum'), ('bass', 'bass', 'bassline')):
        for name in sorted(parts):
            if str((roles or {}).get(name, '')).lower() in family:
                return name
    return sorted(parts)[0]


def phase_correction(events_by_part, tm, block=None, roles=None):
    """Correction curves and their measured effect.

    Returns ({part: [(beat, correction_s), ...]}, stats). The anchor gets an empty curve. A part with
    fewer than two shared onsets with the anchor gets none: one observed asynchrony is not a trend.
    """
    block = block or dict(mode='phase', gain=0.6, anchor='auto', window_beats=2.0, cap_ms=25.0)
    parts = {str(n): sorted(e, key=lambda x: (x['beat'], x['p']))
             for n, e in (events_by_part or {}).items() if e}
    if str(block.get('mode', 'off')) != 'phase' or len(parts) < 2:
        return {}, dict(mode=str(block.get('mode', 'off')), parts=len(parts),
                        asynchrony_rms_ms_before=None, asynchrony_rms_ms_after=None, mean_abs_ms=None)
    anchor = _pick_anchor(parts, roles, block.get('anchor', 'auto'))
    # onsets are matched by nearest written beat, not by an exact float: humanization moves each part by a few
    # tens of ms, so two parts playing "the same" beat are never at the same float. 0.08 beats is well under a
    # 32nd note and well over any microtiming the engine applies, so it clusters the same written onset only.
    abeats = np.array(sorted({float(e['beat']) for e in parts[anchor]}), float)
    atimes = np.array([next(float(x['t']) for x in parts[anchor] if float(x['beat']) == float(b)) for b in abeats], float)
    gain = float(block.get('gain', 0.6))
    cap = float(block.get('cap_ms', 25.0)) / 1000.0
    window = float(block.get('window_beats', 2.0))
    curves, stats = {}, {}
    for name, evs in parts.items():
        if name == anchor:
            curves[name] = []
            continue
        beats, devs = [], []
        for e in evs:
            b = float(e['beat'])
            k = int(np.searchsorted(abeats, b))
            j = k if k < len(abeats) and (k == 0 or abs(abeats[k] - b) <= abs(b - abeats[k - 1])) else k - 1
            if 0 <= j < len(abeats) and abs(abeats[j] - b) <= 0.08:
                beats.append(b)
                devs.append(float(e['t']) - float(atimes[j]))
        if len(beats) < 2:
            curves[name] = []
            continue
        beats = np.asarray(beats, float)
        dev = np.asarray(devs, float)
        corr = -gain * dev
        if window > 0.0 and len(corr) >= 3:
            gaps = np.abs(np.diff(beats))
            step = float(np.median(gaps)) if len(gaps) else 1.0
            k = max(1, int(round(window / max(step, 1e-6))))
            if 1 < k < len(corr):
                corr = np.convolve(corr, np.ones(k) / k, mode='same')
        corr = np.clip(corr, -cap, cap)
        curves[name] = [(float(b), float(c)) for b, c in zip(beats, corr)]
        after = dev + corr
        # RMS about the anchor, not the standard deviation: a constant offset with no jitter still IS an
        # asynchrony (the part plays 15 ms late), and it must show as one before the correction and shrink after.
        stats[name] = dict(deviation_ms_rms_before=round(float(np.sqrt(np.mean(dev ** 2))) * 1000.0, 3),
                           deviation_ms_rms_after=round(float(np.sqrt(np.mean(after ** 2))) * 1000.0, 3),
                           mean_abs_correction_ms=round(float(np.mean(np.abs(corr))) * 1000.0, 3),
                           max_abs_correction_ms=round(float(np.max(np.abs(corr))) * 1000.0, 3),
                           shared_onsets=int(len(beats)))
    if not stats:
        return curves, dict(mode='phase', parts=len(parts), asynchrony_rms_ms_before=None,
                            asynchrony_rms_ms_after=None, mean_abs_ms=None)
    before = float(np.sqrt(np.mean([s['deviation_ms_rms_before'] ** 2 for s in stats.values()])))
    after = float(np.sqrt(np.mean([s['deviation_ms_rms_after'] ** 2 for s in stats.values()])))
    out = dict(mode='phase', anchor=anchor, parts=len(parts),
               asynchrony_rms_ms_before=round(before, 3), asynchrony_rms_ms_after=round(after, 3),
               mean_abs_ms=round(float(np.mean([s['mean_abs_correction_ms'] for s in stats.values()])), 3),
               per_part=stats)
    return curves, out


def curve_at(curve, beats):
    """Correction in seconds at a beat (nearest value outside the curve)."""
    if not curve:
        return 0.0
    b = np.asarray([float(x) for x, _ in curve], float)
    v = np.asarray([float(y) for _, y in curve], float)
    return np.interp(np.asarray(beats, float), b, v)
