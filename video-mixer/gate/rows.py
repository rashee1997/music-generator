# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""rows.py - every picture row, measured.

Each function appends one (level, name, detail) row through `quality_gate._row`,
so a video row and a music row have the same shape and land in the same report.
Nothing here decides whether a limit is right for a piece: that is the gate
profile's job, with a written reason.

A row that cannot fail is not a row. Every one of these has a negative control
in `video_selftest.py`.
"""
import os

import numpy as np

# one row shape for video and music rows
try:
    from quality_gate import _row
except Exception:                                   # the gate may be imported by a tool without the skill on sys.path
    def _row(out, level, name, detail):
        out.append((level, name, detail))


def _num(v, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if np.isfinite(f) else default


def _signals():
    """(numpy, soundfile) or (None, None): a row says it could not measure instead of guessing."""
    try:
        import soundfile as sf
        return np, sf
    except Exception:
        return None, None


# ---------------------------------------------------------------- picture time
def duration_row(probe, program_s, cfg, out):
    tol = float(cfg['duration_tolerance_ms'])
    picture = float(probe['source']['duration_s'])
    delta_ms = (program_s - picture) * 1000.0
    level = 'PASS' if abs(delta_ms) <= tol else 'FAIL'
    _row(out, level, 'video.duration_lock',
         f'picture {picture:.3f}s, program {program_s:.3f}s -> {delta_ms:+.0f} ms (limit +/-{tol:.0f})')


def cut_sync_row(cuts, hits, cfg, out):
    """Offsets are signed as heard: negative = the hit arrives before the cut, positive = after it.

    Only hits derived from a cut are judged: a motion hit accents a movement inside a shot and has no edit to be
    late for, so judging it against the nearest cut would be measuring the wrong thing.
    """
    cs = cfg['cut_sync']
    cut_times = [float(c['t'] if isinstance(c, dict) else c) for c in cuts or []]
    cut_hits = [h for h in hits or [] if h.get('kind', 'cut') == 'cut']
    if not cut_hits:
        _row(out, 'PASS', 'video.cut_sync', f'no cut-derived hit ({len(hits or [])} motion hits only): nothing to sync')
        return []
    if not cut_times:
        _row(out, 'PASS', 'video.cut_sync', 'no cut detected: hits are not tied to picture edits')
        return []
    offsets = []
    for h in cut_hits:
        t = float(h['t_s'] if 't_s' in h else h['t'])
        nearest = min(cut_times, key=lambda c: abs(c - t))
        offsets.append((t, nearest, (t - nearest) * 1000.0))
    worst = max(offsets, key=lambda o: abs(o[2]))
    bad = [o for o in offsets if o[2] < -float(cs['early_ms']) or o[2] > float(cs['late_ms'])]
    level = 'FAIL' if bad else ('WARN' if abs(worst[2]) > float(cs['aim_ms']) else 'PASS')
    detail = (f'{len(cut_hits)} cut hits on {len(cut_times)} cuts: worst {worst[2]:+.0f} ms at {worst[0]:.3f}s '
              f'(early limit -{cs["early_ms"]:.0f}, late limit +{cs["late_ms"]:.0f}, aim +/-{cs["aim_ms"]:.0f})')
    if bad:
        detail += f'; {len(bad)} outside the limit'
    _row(out, level, 'video.cut_sync', detail)
    return offsets


def motion_sync_row(motion_beats, hits, cfg, out):
    """A movement hit against the movement it accents.

    The window is wider than a cut's on purpose: music-to-motion synchrony is
    detected inside about 300-450 ms, narrowing towards 150-200 ms as the tempo
    rises (PMC6711538, Petrini 2009). `window_ms` is the preset's call.
    """
    window = float((cfg.get('motion_sync') or {}).get('window_ms', 150.0))
    beats = [float(b['t'] if isinstance(b, dict) else b) for b in motion_beats or []]
    mhits = [h for h in hits or [] if h.get('kind') == 'motion']
    if not mhits:
        _row(out, 'PASS', 'video.motion_sync', 'no movement hit: nothing to sync')
        return []
    if not beats:
        _row(out, 'WARN', 'video.motion_sync',
             f'{len(mhits)} movement hits but no movement beat was measured: the window could not be applied')
        return []
    offsets = []
    for h in mhits:
        t = float(h['t_s'] if 't_s' in h else h['t'])
        nearest = min(beats, key=lambda b: abs(b - t))
        offsets.append((t, nearest, (t - nearest) * 1000.0))
    worst = max(offsets, key=lambda o: abs(o[2]))
    bad = [o for o in offsets if abs(o[2]) > window]
    level = 'FAIL' if bad else ('WARN' if abs(worst[2]) > window * 0.75 else 'PASS')
    detail = (f'{len(mhits)} movement hits: worst {worst[2]:+.0f} ms at {worst[0]:.3f}s '
              f'(window +/-{window:.0f} ms)')
    if bad:
        detail += f'; {len(bad)} outside the window'
    _row(out, level, 'video.motion_sync', detail)
    return offsets


def hit_class_row(hits, cfg, out):
    """A delayed accent must land after its moment; a dead-on one must not drift.

    The rule: an explosion or a cut needs no processing, so it lands on the frame;
    a line or a look needs the audience to absorb it first, so its accent arrives
    after the audience's reaction time (Robin Hoffmann, Placement of Hit Points).
    """
    classes = (cfg.get('classes') or {})
    if not hits:
        _row(out, 'INFO', 'video.hit_class', 'no hits placed')
        return
    bad, checked = [], 0
    for h in hits:
        cls_name = h.get('class')
        if not cls_name:
            continue
        cls = classes.get(cls_name)
        if not cls:
            bad.append(f'{h.get("t")}: unknown class "{cls_name}"')
            continue
        checked += 1
        offset = 0.0 if h.get('offset_s') is None else float(h['offset_s'])
        lo, hi = (float(v) for v in (cls.get('window_s') or [-0.045, 0.125]))
        after = h.get('event_offset_s')
        after = offset if after is None else float(after)
        if not (lo <= after <= hi):
            bad.append(f'{float(h.get("t", 0.0)):.3f}s: {cls_name} at {after:+.3f}s outside {lo:+.3f}..{hi:+.3f}')
    if not checked and not bad:
        _row(out, 'INFO', 'video.hit_class', 'no hit declared a class: the row did not run')
        return
    level = 'FAIL' if bad else 'PASS'
    detail = f'{checked} classified hits inside their class window'
    if bad:
        detail += '; ' + '; '.join(bad[:4])
    _row(out, level, 'video.hit_class', detail)


def grid_phase_row(cut_phase, cfg, out):
    """The cuts' worst residual against the fitted beat grid, in frames."""
    cf = cfg.get('grid_phase') or {}
    tol_frames = float(cf.get('tolerance_frames', 1.0))
    phase = cut_phase or {}
    worst_ms = _num(phase.get('worst_residual_ms'))
    frames = phase.get('tolerance_frames')
    if frames is None:
        fps = _num(phase.get('fps'))
        frames = (worst_ms / 1000.0) * fps if fps else None
    if frames is None:
        _row(out, 'INFO', 'video.grid_phase', 'no frame rate: the residual cannot be stated in frames')
        return
    level = 'PASS' if float(frames) <= tol_frames else ('WARN' if float(frames) <= tol_frames * 2 else 'FAIL')
    _row(out, level, 'video.grid_phase',
         f'worst cut residual {worst_ms:.1f} ms = {float(frames):.2f} frames (limit {tol_frames:.2f}); '
         f'mean {_num(phase.get("mean_residual_ms")):.1f} ms, confidence {_num(phase.get("confidence")):.2f}')


def hit_density_row(hits, cuts, duration_s, cfg, out):
    """Accents per minute against the budget, and how many adjacent cut pairs both got hit.

    Hitting every cut is Mickey Mousing: it gives the audience no room and stops
    meaning anything. The ratio is the measurable form of that rule.
    """
    d = cfg.get('density') or {}
    budget = float(d.get('budget_per_minute', cfg.get('max_hits_per_minute', 24)))
    max_ratio = float(d.get('max_consecutive_cut_hits', 0.60))
    minutes = max(_num(duration_s, 0.0) / 60.0, 1e-6)
    per_min = len(hits or []) / minutes
    cuts_sorted = sorted(float(c['t'] if isinstance(c, dict) else c) for c in cuts or [])
    hit_times = [float(h['t_s'] if 't_s' in h else h['t']) for h in hits or [] if h.get('kind', 'cut') == 'cut']

    def _hit_near(t):
        return any(abs(t - x) <= 0.05 for x in hit_times)

    pairs = list(zip(cuts_sorted, cuts_sorted[1:]))
    both = [1 for a, b in pairs if _hit_near(a) and _hit_near(b)]
    ratio = (len(both) / len(pairs)) if pairs else 0.0
    over = per_min > budget + 1e-9
    mickey = ratio > max_ratio + 1e-9
    level = 'FAIL' if (over or mickey) else 'PASS'
    detail = (f'{len(hits or [])} hits in {_num(duration_s):.1f}s = {per_min:.1f}/min (budget {budget:.0f}); '
              f'{ratio * 100:.0f} % of adjacent cut pairs both hit (limit {max_ratio * 100:.0f} %)')
    if over:
        detail += '; over the budget'
    if mickey:
        detail += '; Mickey Mousing'
    _row(out, level, 'video.hit_density', detail)


def cue_silence_row(program_wav, windows, cfg, out):
    """Music energy where the spotting asked for silence. Silence is a cue, not a gap."""
    if not windows:
        _row(out, 'PASS', 'video.cue_silence', 'the spotting marked no silent section')
        return
    np_, sf = _signals()
    if np_ is None or sf is None or not program_wav or not os.path.exists(program_wav):
        _row(out, 'WARN', 'video.cue_silence', 'no program to measure: the silent windows were not checked')
        return
    y, sr = sf.read(program_wav, always_2d=True)
    y = y.astype(np.float32)
    limit = float((cfg.get('cue_silence') or {}).get('max_dbfs', -50.0))
    worst, loud = None, []
    for a, b in windows:
        i, j = int(float(a) * sr), min(len(y), int(float(b) * sr))
        if j <= i:
            continue
        seg = y[i:j]
        rms = 20.0 * np.log10(np.sqrt(np.mean(np.square(seg))) + 1e-12)
        if worst is None or rms > worst:
            worst = rms
        if rms > limit:
            loud.append((float(a), float(b), float(rms)))
    if worst is None:
        _row(out, 'INFO', 'video.cue_silence', 'the silent windows fall outside the program')
        return
    level = 'FAIL' if loud else 'PASS'
    detail = f'{len(windows)} silent windows, loudest {worst:.1f} dBFS (limit {limit:.1f})'
    if loud:
        a, b, r = loud[0]
        detail += f'; {len(loud)} over: {a:.2f}-{b:.2f}s at {r:.1f} dBFS'
    _row(out, level, 'video.cue_silence', detail)


# ---------------------------------------------------------------- dialogue
def dialogue_row(mix_report, probe, cfg, out):
    """Kept as the single-number row; `dialogue_band_row` is the spectral one below it."""
    if not probe['source'].get('has_audio'):
        _row(out, 'PASS', 'video.dialogue_snr', 'source has no audio: the cue plays alone, nothing to duck under')
        return
    value = (mix_report or {}).get('music_under_voice_db')
    if value is None:
        level = 'WARN'
        detail = 'no speech detected in the program: ducking was not exercised'
        if (mix_report or {}).get('speech_measured'):
            level, detail = 'FAIL', 'speech was measured in the picture but the program reports no music-under-voice figure'
        _row(out, level, 'video.dialogue_snr', detail)
        return
    need = float(cfg['dialogue_snr_min_db'])
    level = 'PASS' if value >= need else 'FAIL'
    _row(out, level, 'video.dialogue_snr',
         f'music {value:.1f} dB under speech (need {need:.1f}) while the voice is active')


def dialogue_band_row(mix_report, probe, cfg, out):
    """The band that carries consonants, not just the overall loudness difference.

    A bed can sit 20 dB under the voice in the low end and still bury a sentence at
    2 kHz. This row measures the music's own 1-4 kHz energy under speech.

    Sign as in `video.dialogue_snr`: the figure is positive when the music sits under
    the voice, so a larger number is a quieter bed.
    """
    if not probe['source'].get('has_audio'):
        _row(out, 'PASS', 'video.dialogue_band', 'source has no audio: nothing to mask')
        return
    value = (mix_report or {}).get('music_under_voice_band_db')
    need = float((cfg.get('dialogue_band') or {}).get(
        'min_db', cfg.get('dialogue_band_min_db', 12.0)))
    if value is None:
        _row(out, 'WARN', 'video.dialogue_band', 'no band figure from the program mix: not measured')
        return
    level = 'PASS' if value >= need else 'FAIL'
    _row(out, level, 'video.dialogue_band',
         f'music {value:.1f} dB under the voice in the consonant band (need {need:.1f})')


# ---------------------------------------------------------------- picture / density
def shot_scale_row(sections, scenes, cfg, out):
    """Density against the camera distance: a close-up cannot hold a full band.

    `sections[].density` is measured from the score (the share of the score's roles
    that sound in that section). `sections[].shot_scale` comes from the context.
    """
    tol = float(cfg.get('shot_scale_tolerance', 0.15))
    allowed = (cfg.get('shot_scale_max_density') or {})
    checked = 0
    bad = []
    by_id = {s.get('id'): s for s in scenes or []}
    for sec in sections or []:
        scale = sec.get('shot_scale')
        density = sec.get('density')
        if scale is None or density is None:
            continue
        cap = allowed.get(scale)
        if cap is None:
            continue
        checked += 1
        if float(density) > float(cap) + tol:
            bad.append(f'{sec.get("name", "?")} ({scale}) density {float(density):.2f} > {float(cap):.2f}')
    if not checked:
        _row(out, 'INFO', 'video.shot_scale', 'no section carried both a shot scale and a density: the row did not run')
        return
    level = 'FAIL' if bad else 'PASS'
    detail = f'{checked} sections inside their shot-scale cap (+{tol:.2f})'
    if bad:
        detail += '; ' + '; '.join(bad[:3])
    _row(out, level, 'video.shot_scale', detail)


# ---------------------------------------------------------------- delivery
def master_row(program_wav, profile, cfg, out, mask=None, sr=None):
    """Delivered loudness **in the profile's declared gating mode**, and true peak.

    `mask` is a per-sample speech mask. When the profile is dialogue-gated and no
    mask is given, the row FAILS rather than silently grading a dialogue target on
    the full program: that substitution is the defect this row exists to catch.
    """
    import mixer as mx
    np_, sf = _signals()
    if np_ is None:
        _row(out, 'WARN', 'video.master_compliance', 'soundfile/numpy unavailable: not measured')
        return
    y, sr_file = sf.read(program_wav, always_2d=True)
    y = y.astype(np.float32)
    rate = int(sr or sr_file)
    mode = str(profile.get('loudness_mode') or 'full_program')
    full = float(mx.lufs(y, rate))
    gated = None
    if mask is not None:
        gated = mx.dialogue_gated_lufs(y, rate, mask)
    measured = gated if (mode == 'dialogue' and gated is not None) else full
    tol = float(cfg['loudness_tolerance_lu'])
    dl = abs(measured - float(profile['lufs']))
    tp = float(mx.true_peak_db(y, rate))
    peak_ok = tp <= float(profile['true_peak_db']) + 0.1
    if mode == 'dialogue' and gated is None:
        _row(out, 'FAIL', 'video.master_compliance',
             f'profile "{mode}" is dialogue-gated but no speech was measured: the target cannot be verified '
             f'(full program reads {full:.1f} LUFS)')
        return
    level = 'PASS' if (dl <= tol and peak_ok) else 'FAIL'
    _row(out, level, 'video.master_compliance',
         f'{measured:.1f} LUFS ({mode}) vs {profile["lufs"]:.1f} +/-{tol:.1f}, '
         f'true peak {tp:.2f} dBTP vs {profile["true_peak_db"]:.2f}'
         + (f'; full program reads {full:.1f}' if mode == 'dialogue' else ''))


def gating_mode_row(profile, measured_mode, out):
    """The mode the profile declares must be the mode that was measured.

    Before this row, `loudness_mode: dialogue_gated` was a label with no gating
    behind it: the master and the gate both measured the full program. A claim
    about how a delivery is measured is a claim the gate has to be able to fail.
    """
    declared = str(profile.get('loudness_mode') or 'full_program')
    measured = str(measured_mode or 'full_program')
    level = 'PASS' if declared == measured else 'FAIL'
    _row(out, level, 'video.gating_mode',
         f'declared "{declared}", measured "{measured}"' +
         ('' if declared == measured else ': the delivery claims a gating that was not applied'))
