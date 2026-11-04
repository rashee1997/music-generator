# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""gate_report.py - a picture and a text file for each group of gate rows.

    write_reports(wav, score, out_dir, stem_meta=..., mix_meta=...)

Numbers decide; the PNG lets a human see where. Every figure has a `.txt` with the same numbers and a `.json` with the
arrays, so a reader who cannot see the image loses nothing. matplotlib Agg only; no display.
"""
import json
import os

import numpy as np

from gate_audio import load
import gate_checks as gc


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (np.floating, np.integer)):
        return float(v)
    if isinstance(v, np.ndarray):
        return _jsonable(v.tolist())
    return v


def _write(out_dir, name, fig, text, data):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f'{name}.txt'), 'w', encoding='utf-8') as fh:
        fh.write(text.rstrip() + '\n')
    with open(os.path.join(out_dir, f'{name}.json'), 'w', encoding='utf-8') as fh:
        json.dump(_jsonable(data), fh, indent=2)
    if fig is not None:
        fig.savefig(os.path.join(out_dir, f'{name}.png'), dpi=120, bbox_inches='tight')
        import matplotlib.pyplot as plt
        plt.close(fig)


def _plt():
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        return plt
    except Exception:
        return None


def _flags(metrics):
    out = []
    for m in metrics or []:
        for t in m.get('worst_times_s') or []:
            out.append((float(t), m.get('row', '?'), m.get('stem') or 'master', m.get('level', '')))
    return sorted(out)


def write_reports(wav_path, score, out_dir, stem_meta=None, mix_meta=None):
    """Write waveform, spectrogram, level, stereo, stem-level and section-energy figures + text."""
    if not out_dir:
        return {}
    metrics = list((stem_meta or {}).get('metrics') or []) + list((mix_meta or {}).get('metrics') or [])
    flags = _flags(metrics)
    try:
        sig = load(wav_path)
    except Exception as exc:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, 'report_error.txt'), 'w', encoding='utf-8') as fh:
            fh.write(f'cannot read {wav_path}: {exc}\n')
        return {}
    dur = sig.dur
    secs = gc.section_bounds(score, dur)
    plt = _plt()
    written = {}

    # waveform + section boundaries + flagged times
    text = [f'file: {wav_path}', f'duration_s: {dur:.3f}', f'sample_rate: {sig.sr}', 'sections:']
    text += [f'  {s["name"]}: {s["start_s"]:.2f}-{s["end_s"]:.2f} s, dyn {s["dyn"]:.2f}' for s in secs]
    text.append(f'flagged times: {len(flags)}')
    text += [f'  {t:.3f}s {row} [{level}] {stem}' for t, row, stem, level in flags[:60]]
    fig = None
    if plt is not None:
        fig, ax = plt.subplots(figsize=(12, 3.2))
        t = np.arange(len(sig.mono)) / float(sig.sr)
        step = max(1, len(t) // 6000)
        ax.plot(t[::step], sig.mono[::step], lw=0.4, color='#333')
        for s in secs:
            ax.axvline(s['start_s'], color='#999', lw=0.6, ls='--')
        for t0, row, stem, level in flags:
            ax.axvline(t0, color='#c0392b' if level == 'FAIL' else '#e67e22', lw=1.0, alpha=0.8)
        ax.set_xlim(0, dur)
        ax.set_xlabel('seconds')
        ax.set_ylabel('amplitude')
        ax.set_title('master with section boundaries and flagged times')
    _write(out_dir, 'waveform', fig, '\n'.join(text), dict(duration_s=dur, sections=secs, flags=flags[:200]))
    written['waveform'] = os.path.join(out_dir, 'waveform.png')

    # log spectrogram
    db = 20 * np.log10(sig.stft + 1e-9)
    fig = None
    if plt is not None:
        fig, ax = plt.subplots(figsize=(12, 3.6))
        freqs = np.linspace(0, sig.sr / 2, db.shape[0])
        ax.pcolormesh(np.arange(db.shape[1]) * 512 / sig.sr, freqs, db, shading='auto', cmap='magma',
                      vmin=np.max(db) - 80, vmax=np.max(db))
        ax.set_yscale('symlog', linthresh=200)
        ax.set_ylim(30, sig.sr / 2)
        ax.set_xlabel('seconds')
        ax.set_ylabel('Hz')
        ax.set_title('log spectrogram (dB)')
    text = (f'shape: {db.shape[0]} bins x {db.shape[1]} frames\n'
            f'frame_hop_s: {512 / sig.sr:.4f}\n'
            f'peak_db: {np.max(db):.1f}\n'
            f'band_db: ' + ', '.join(f'{lo}-{hi}Hz {np.mean(db[(freqs >= lo) & (freqs < hi)]):.1f}'
                                     for lo, hi in ((20, 200), (200, 2000), (2000, 6000), (6000, 16000))))
    _write(out_dir, 'spectrogram', fig, text, dict(shape=list(db.shape), peak_db=float(np.max(db))))
    written['spectrogram'] = os.path.join(out_dir, 'spectrogram.png')

    # short-term level
    level_db, times = sig.frame_db(frame_ms=50, hop_ms=25)
    target = float(((score.get('master') or {}).get('lufs', -14.0)))
    fig = None
    if plt is not None:
        fig, ax = plt.subplots(figsize=(12, 2.8))
        ax.plot(times, level_db, lw=0.8, color='#2c3e50')
        ax.axhline(target, color='#c0392b', ls='--', lw=0.8, label=f'target {target:g} LUFS (dBFS frame level shown)')
        ax.set_xlim(0, dur)
        ax.set_xlabel('seconds')
        ax.set_ylabel('dBFS (50 ms RMS)')
        ax.legend(loc='lower right', fontsize=7)
        ax.set_title('short-term level')
    text = (f'frames: {level_db.size}\nmin_db: {np.min(level_db):.1f}\nmax_db: {np.max(level_db):.1f}\n'
            f'median_db: {np.median(level_db):.1f}\np05_db: {np.percentile(level_db, 5):.1f}\n'
            f'p95_db: {np.percentile(level_db, 95):.1f}\ntarget_lufs: {target:g} (not the same unit as dBFS)')
    _write(out_dir, 'level', fig, text, dict(min_db=float(np.min(level_db)), max_db=float(np.max(level_db)),
                                             median_db=float(np.median(level_db)), target_lufs=target))
    written['level'] = os.path.join(out_dir, 'level.png')

    # stereo correlation
    win = max(1, int(0.5 * sig.sr))
    hop = max(1, int(0.25 * sig.sr))
    cs, ct = [], []
    for a in range(0, max(1, len(sig.mono) - win), hop):
        l = sig.stereo[a:a + win, 0]
        r = sig.stereo[a:a + win, min(1, sig.stereo.shape[1] - 1)]
        if l.size < win // 2 or np.std(l) < 1e-9 or np.std(r) < 1e-9:
            continue
        cs.append(float(np.corrcoef(l, r)[0, 1]))
        ct.append((a + win / 2) / sig.sr)
    fig = None
    if plt is not None and cs:
        fig, ax = plt.subplots(figsize=(12, 2.2))
        ax.plot(ct, cs, lw=0.8, color='#16a085')
        ax.axhline(0, color='#999', lw=0.6)
        ax.set_ylim(-1, 1)
        ax.set_xlim(0, dur)
        ax.set_xlabel('seconds')
        ax.set_ylabel('L/R correlation')
        ax.set_title('stereo correlation (0.5 s windows)')
    text = (f'windows: {len(cs)}\nmin: {min(cs) if cs else 0:.3f}\nmedian: {np.median(cs) if cs else 0:.3f}\n'
            f'max: {max(cs) if cs else 0:.3f}\nchannels: {sig.stereo.shape[1]}')
    _write(out_dir, 'stereo', fig, text, dict(times=ct, corr=cs))
    written['stereo'] = os.path.join(out_dir, 'stereo.png')

    # per-stem level against the score dynamics curve
    dead = [m for m in (stem_meta or {}).get('metrics', []) if m.get('row') == 'stem.dead' and m.get('table')]
    if dead:
        fig = None
        if plt is not None:
            fig, ax = plt.subplots(figsize=(max(6, len(dead) * 1.2), 3.2))
            width = 0.8 / max(1, len(dead))
            for i, m in enumerate(dead):
                xs = np.arange(len(m['table'])) + i * width
                ax.bar(xs, [r['measured_db'] for r in m['table']], width=width, label=m.get('stem', '?'))
            ax.set_xticks(np.arange(len(dead[0]['table'])) + 0.4 - width / 2)
            ax.set_xticklabels([r['section'] for r in dead[0]['table']], fontsize=8)
            ax.set_ylabel('dBFS')
            ax.set_title('per-stem level by section (against the score dynamics)')
            ax.legend(fontsize=7)
        lines = ['stem,section,measured_db,expected_db,dyn']
        for m in dead:
            for r in m['table']:
                lines.append(f'{m.get("stem")},{r["section"]},{r["measured_db"]},{r["expected_db"]},{r["dyn"]}')
        _write(out_dir, 'stem_levels', fig, '\n'.join(lines), dict(rows=[dict(stem=m.get('stem'), table=m['table']) for m in dead]))
        written['stem_levels'] = os.path.join(out_dir, 'stem_levels.png')

    # section energy against the sheet
    se = next((m for m in (mix_meta or {}).get('metrics', []) if m.get('row') == 'section.energy' and m.get('table')), None)
    if se:
        fig = None
        if plt is not None:
            fig, ax = plt.subplots(figsize=(8, 3.0))
            xs = np.arange(len(se['table']))
            ax.bar(xs, [r['level_db'] for r in se['table']], color='#34495e', alpha=0.8)
            ax.set_ylabel('section level (dBFS)')
            ax2 = ax.twinx()
            ax2.plot(xs, [r['energy'] for r in se['table']], color='#e67e22', marker='o', lw=1.2)
            ax2.set_ylim(0, 1.05)
            ax2.set_ylabel('promised energy 0..1')
            ax.set_xticks(xs)
            ax.set_xticklabels([r['name'] for r in se['table']], rotation=20, fontsize=8)
            ax.set_title(f'section energy vs measured (rho {se["value"]:.2f})')
        lines = [f'rho: {se["value"]:.3f}', 'section,start_s,end_s,promised,level_db']
        lines += [f'{r["name"]},{r["start_s"]:.2f},{r["end_s"]:.2f},{r["energy"]:.3f},{r["level_db"]:.2f}' for r in se['table']]
        _write(out_dir, 'section_energy', fig, '\n'.join(lines), se)
        written['section_energy'] = os.path.join(out_dir, 'section_energy.png')

    return written
