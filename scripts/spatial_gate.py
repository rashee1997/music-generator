# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""spatial_gate.py - the rows a multichannel deliverable must pass, and only for the formats it asked for.

The gate reads the score's `output_targets` through render_targets and checks the file that was actually produced
against the target's own data (its channel order, its true-peak ceiling) and its layout's own data (the low-frequency
crossover and stopband, the surround-energy window, the height ceiling). A format that was not requested is never
checked and never failed.

This module measures only. It has no thresholds of its own.
"""
import numpy as np


def _row(out, level, name, detail):
    out.append((level, name, detail))


def _db(x):
    x = np.asarray(x, dtype=np.float64)
    return float(20.0 * np.log10(np.sqrt(np.mean(np.square(x)) + 1e-20)))


def targets_for(score, channels):
    """The selected targets whose channel count is `channels` (empty when the file is not a requested format)."""
    import render_targets
    sel = render_targets.resolve(score)['selected']
    return [t for t in sel if render_targets.channels(t) == int(channels)]


def output_rows(score, wav_path, out):
    """Rows for the delivered file: its format, its ceiling, and the checks that format needs."""
    import gate_audio
    import render_targets
    from spatial_engine import config
    try:
        sig = gate_audio.load(wav_path)
    except Exception as exc:
        _row(out, 'WARN', 'delivery.format', f'cannot read {wav_path} to check the requested format ({exc})')
        return
    n_ch = sig.channels
    targets = targets_for(score, n_ch)
    if not targets:
        requested = render_targets.resolve(score)['selected']
        _row(out, 'WARN', 'delivery.format',
             f'{wav_path} has {n_ch} channel(s), which matches none of the requested target(s) '
             f'{", ".join(requested) or "none"}: the delivered format is not the promised one')
        return
    for target in targets:
        name = target
        tgt = render_targets.get(target) or {}
        ceiling = render_targets.true_peak(target)
        peaks = sig.true_peak_by_channel
        worst = float(np.max(peaks))
        if ceiling is not None:
            _row(out, 'FAIL' if worst > ceiling else 'PASS', 'delivery.true_peak',
                 f'{name}: worst channel true peak {worst:+.1f} dBTP (ceiling {ceiling:+.1f} dBTP; '
                 f'per channel {", ".join(f"{p:+.1f}" for p in peaks)})')
        if n_ch == 2:
            corr = float(np.corrcoef(sig.audio[:, 0], sig.audio[:, 1])[0, 1]) if n_ch == 2 else 1.0
            limit = float((tgt.get('gate') or {}).get('stereo_correlation_min', 0.0))
            _row(out, 'FAIL' if corr < limit else 'PASS', 'stereo.correlation',
                 f'{name}: inter-channel correlation {corr:+.2f} (floor {limit:+.2f}: below it the centre is cancelling)')
            continue
        lay_name = tgt.get('layout')
        if not lay_name:
            continue
        cfg = config.lfe_cfg(lay_name, target)
        order = list(tgt.get('channel_order') or [])
        # low-frequency channel: nothing above the stopband may leave it
        idx = cfg.get('channel')
        if isinstance(idx, str):                      # the layout names its channel; the target may give an index
            idx = (order.index(idx) + 1) if idx in order else None
        if idx is not None and cfg.get('stopband_hz'):
            i = int(idx) - 1
            if 0 <= i < n_ch:
                from spatial_engine import bass
                leak = bass.stopband_leak_db(sig.audio[:, i], sig.sr, cfg, reference=sig.audio)
                limit = float(cfg.get('stopband_db', -45.0))
                _row(out, 'FAIL' if leak > limit else 'PASS', 'imm.lfe_stopband',
                     f'{name}: low-frequency channel energy above {float(cfg["stopband_hz"]):g} Hz is {leak:+.1f} dB '
                     f'relative to the programme (limit {limit:+.1f} dB)'
                     + ('; check the send and the mains high-pass' if leak > limit else ''))
        gate = config.threshold(lay_name, 'surround_ratio_db')
        surrounds = [n for n in order if n in ('BL', 'BR', 'SL', 'SR')]
        fronts = [n for n in order if n in ('FL', 'FR', 'FC')]
        if gate and surrounds and fronts:
            s = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in surrounds))
            f = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in fronts))
            ratio = float(20.0 * np.log10((s + 1e-20) / (f + 1e-20)))
            lo, hi = float(gate[0]), float(gate[1])
            _row(out, 'PASS' if lo <= ratio <= hi else 'FAIL', 'imm.surround_ratio',
                 f'{name}: surround energy {ratio:+.1f} dB against the front stage (window {lo:+.1f}..{hi:+.1f} dB)')
        hlimit = config.threshold(lay_name, 'height_max_rel_db')
        heights = [sp['name'] for sp in config.layout(lay_name)['speakers'] if float(sp.get('elevation', 0.0)) > 0]
        beds = [sp['name'] for sp in config.layout(lay_name)['speakers']
                if float(sp.get('elevation', 0.0)) <= 0 and not sp.get('lfe')]
        if hlimit is not None and heights and beds:
            h = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in heights))
            b = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in beds))
            rel = float(20.0 * np.log10((h + 1e-20) / (b + 1e-20)))
            _row(out, 'PASS' if rel <= float(hlimit) else 'FAIL', 'imm.height_arc',
                 f'{name}: height channels {rel:+.1f} dB against the listener-level beds (ceiling {float(hlimit):+.1f} dB)')
        # a multichannel file must fold to a coherent stereo image (no destructive phase between the two)
        from spatial_engine import downmix
        fold = downmix.fold(sig.audio, lay_name)
        corr = float(np.corrcoef(fold[:, 0], fold[:, 1])[0, 1]) if len(fold) > 1 else 1.0
        limit = float((tgt.get('gate') or {}).get('stereo_correlation_min', 0.0))
        _row(out, 'FAIL' if corr < limit else 'PASS', 'imm.fold_coherence',
             f'{name}: the two-channel fold has correlation {corr:+.2f} (floor {limit:+.2f})')
