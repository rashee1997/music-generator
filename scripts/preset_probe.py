# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""preset_probe.py - play each one-shot effect of a score once, alone, and run the stem checks on that one sound.

A stem is its sounds repeated. A sound that is silent, clips, starts on a step, drifts in DC or stops at full level shows
the same fault in every repeat, and the stem gate finds it only after the whole stem is rendered. A one-shot costs
seconds. The probe renders each distinct `sfx:<name>` preset the score uses at its loudest event velocity and judges:

    probe.silent   FAIL  the peak is under -60 dBFS (the leaf brush that rendered at -100 dBFS)
    probe.clip     FAIL  three or more samples at or above 0.999 FS at the loudest velocity (stem.clipping)
    probe.start    FAIL  the first sample is a step: above 0.01 FS and 5 % of the peak (a click at every hit)
    probe.tail     WARN  the last 20 ms is within 30 dB of the peak: the sound is cut, not finished
    probe.dc       WARN  the mean of the sound, spread over one second, is above 0.001 (stem.dc); set `dc_hp_hz` on the track

`render(name, seconds, sr, seed, **kw)` is injectable for tests. Limits are starting values from the failures that
produced them. Only effects are probed: an SFZ patch needs the sampler, and its range is checked by preflight_lint.
"""
import numpy as np

SR = 44100
SILENT_PEAK = 1e-3
CLIP_LEVEL, CLIP_RUN = 0.999, 3
START_ABS, START_REL = 0.01, 0.05
TAIL_DB = -30.0
DC_MAX = 0.001


def default_render(name, seconds, sr, seed, **kw):
    import sfx
    x, _, _ = sfx.make(name, max(0.1, float(seconds)), sr, seed, **kw)
    return np.asarray(x, dtype=float)


def _mono(x):
    x = np.asarray(x, dtype=float)
    return x.mean(axis=1) if x.ndim == 2 else x


def probe_sound(name, x, velocity=1.0, sr=SR, dc_filtered=False):
    """Rows for one rendered sound. `x` is the sound before the event velocity is applied. `dc_filtered`: every track that plays it
    sets `dc_hp_hz`, so a mean in the raw sound is already handled."""
    m = _mono(x) * float(velocity)
    out = []
    peak = float(np.max(np.abs(m))) if m.size else 0.0
    if peak < SILENT_PEAK:
        return [('FAIL', 'probe.silent', f'effect "{name}" renders at {20 * np.log10(peak + 1e-12):.0f} dBFS peak: it makes no usable sound at velocity {velocity:g}')]
    clipped = int(np.sum(np.abs(m) >= CLIP_LEVEL))
    if clipped >= CLIP_RUN:
        out.append(('FAIL', 'probe.clip', f'effect "{name}" clips ({clipped} samples at or above {CLIP_LEVEL} FS) at velocity {velocity:g}: lower its calibration level or gain_db'))
    if abs(float(m[0])) > START_ABS and abs(float(m[0])) > START_REL * peak:
        out.append(('FAIL', 'probe.start', f'effect "{name}" starts on a step ({m[0]:+.3f} FS against a {peak:.2f} peak): every hit is a click. Start the sound from zero'))
    n = int(0.02 * sr)
    if m.size > 3 * n:
        tail = float(np.sqrt(np.mean(m[-n:] ** 2)))
        if tail > 0 and 20 * np.log10(tail / peak) > TAIL_DB:
            out.append(('WARN', 'probe.tail', f'effect "{name}" ends {20 * np.log10(tail / peak):.0f} dB under its peak (limit {TAIL_DB:.0f}): the sound is cut, not finished; lengthen its `seconds`'))
    one_second = np.zeros(max(sr, m.size))
    one_second[:m.size] = m
    dc = abs(float(np.mean(one_second[:sr])))
    if dc > DC_MAX and not dc_filtered:
        out.append(('WARN', 'probe.dc', f'effect "{name}" carries a mean of {dc:.4f} FS over one second (limit {DC_MAX:g}): repeated, it reads as stem.dc. Set `dc_hp_hz` on the track'))
    if not out:
        out.append(('PASS', 'probe.sound', f'effect "{name}": audible, no clipping, starts at zero, finishes, no DC'))
    return out


def probe_rows(score, lookup=None, render=None, sr=SR):
    """One set of rows per distinct sfx preset the score plays."""
    render = render or default_render
    if lookup is None:
        import presets
        lookup = lambda name: presets.find_sfx(name)       # noqa: E731
    loud, filtered = {}, {}
    for t in score.get('tracks') or []:
        inst = str(t.get('instrument') or '')
        if not inst.startswith('sfx:') or not t.get('notes'):
            continue
        name = inst.split(':', 1)[1]
        v = max(float(n.get('v', 0.8)) for n in t['notes'])
        loud[name] = max(loud.get(name, 0.0), v / 127.0 if v > 1.0 else v)
        filtered[name] = filtered.get(name, True) and float(t.get('dc_hp_hz') or 0.0) >= 20.0
    rows = []
    for name, v in sorted(loud.items()):
        preset = lookup(name) or {}
        seconds = float(preset.get('seconds') or 1.0)
        try:
            x = render(name, seconds, sr, 1)
        except Exception as exc:
            rows.append(('INFO', 'probe.sound', f'effect "{name}" could not be rendered for the probe ({exc})'))
            continue
        rows += probe_sound(name, x, v, sr, dc_filtered=filtered.get(name, False))
    return rows
