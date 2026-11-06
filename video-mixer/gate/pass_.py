# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""pass_.py - one pass, every picture row, inside the certification.

`pipeline.stage6_ci_quality_suite` calls `pass_rows()` with the program it just
built, in the same row list as the music rows, before `stage7` writes a verdict.
That is the whole point: a cue is certified once, by one list of rows.

    rows, extras = pass_rows(score, context=ctx, probe=probe, program_wav=wav,
                             mix_report=mix_rep, gating=film_delivery['gate'],
                             master_profile=prof, hits=hits)

`gating` is the film delivery preset's `gate` block; `master_profile` is the
profile named by the cue. Missing artifacts produce a WARN that says what could
not be measured, never a silent pass.
"""
import numpy as np

from . import rows as R


def film_presets(project=None):
    """The five film presets, merged with the project layer. Missing ones are an error, not a default."""
    import presets
    if project:
        presets.add_project(project)
    out = {}
    for name in ('analysis', 'mapping', 'hits', 'dialogue', 'delivery'):
        out[name] = presets.get('film', name)
    return out


def _speech_mask_from_mix(mix_report, n, sr):
    """The program mix records its mask's segments; a row needs per-sample 0/1."""
    segs = (mix_report or {}).get('speech_segments')
    if not segs or n <= 0:
        return None
    m = np.zeros(int(n), np.float32)
    for a, b in segs:
        i, j = int(float(a) * sr), min(int(n), int(float(b) * sr))
        if j > i:
            m[i:j] = 1.0
    return m if m.any() else None


def probe_rows(score, out=None):
    """Rows that need only the score and its own sheet: no program, no picture file.

    Used by `pipeline.py` when a score carries a `video` block but the program
    has not been built yet, so even a plain music render of a film cue is held to
    the picture rows it can answer from the score.
    """
    out = [] if out is None else out
    video = score.get('video') or {}
    if not video.get('enabled'):
        return out
    hits = [dict(h) for h in (video.get('hits') or [])]
    if not hits and video.get('hits_at'):
        hits = [dict(t_s=float(t), kind='cut') for t in video['hits_at']]
    R.cut_sync_row(video.get('cuts') or [], hits, {'cut_sync': (video.get('cut_sync') or
                    {'early_ms': 45, 'late_ms': 125, 'aim_ms': 40})}, out)
    R.motion_sync_row(video.get('motion_beats') or [], hits,
                      {'motion_sync': video.get('motion_sync') or {'window_ms': 150.0}}, out)
    R.hit_class_row(hits, video.get('hits_cfg') or {}, out)
    R.hit_density_row(hits, video.get('cuts') or [], float(video.get('duration_s') or 0.0),
                      video.get('hits_cfg') or {}, out)
    R.grid_phase_row(video.get('cut_phase'), video.get('gate_cfg') or {}, out)
    R.shot_scale_row(video.get('sections') or score.get('sections') or [],
                     video.get('scenes') or [], video.get('gate_cfg') or {}, out)
    return out


def _mapping(mapping=None):
    """The film mapping preset, which owns the shot-scale density caps."""
    if mapping is not None:
        return mapping
    try:
        import presets
        return presets.get('film', 'mapping')
    except Exception:
        return {}


def pass_rows(score, context=None, probe=None, program_wav=None, mix_report=None,
              gating=None, master_profile=None, hits=None, out=None, sr=None, mapping=None):
    """Every picture row. Returns (rows, extras).

    extras carries what the report needs: the cut offsets, the measured gating mode,
    and the loudness figures in both modes so a reader can see the difference.
    """
    import soundfile as sf
    out = [] if out is None else out
    video = score.get('video') or {}
    hits = [dict(h) for h in (hits if hits is not None else video.get('hits') or [])]
    gating = gating or {}
    extras = dict(cut_sync=[], motion_sync=[], gating_mode=None, lufs=None, true_peak_db=None)

    program = None
    rate = int(sr or 44100)
    if program_wav:
        try:
            program, rate = sf.read(program_wav, always_2d=True)
            program = program.astype(np.float32)
        except Exception:
            program = None

    if probe and probe.get('source'):
        if program is not None:
            R.duration_row(probe, len(program) / float(rate), gating, out)
        else:
            R.duration_row(probe, float(video.get('duration_s') or 0.0), gating, out)
        cuts = probe.get('cuts') or []
        motion_beats = probe.get('motion_hits') or []
    else:
        if program is not None:
            R.duration_row({'source': {'duration_s': float(video.get('duration_s') or 0.0)}},
                           len(program) / float(rate), gating, out)
        cuts = video.get('cuts') or []
        motion_beats = video.get('motion_beats') or []

    extras['cut_sync'] = R.cut_sync_row(cuts, hits, gating, out)
    extras['motion_sync'] = R.motion_sync_row(motion_beats, hits, gating, out)
    R.hit_class_row(hits, gating.get('classes') or (gating.get('hits') or {}), out)
    R.hit_density_row(hits, cuts, float(video.get('duration_s') or
                                        (probe or {}).get('source', {}).get('duration_s') or 0.0),
                      dict(gating, density=gating.get('hit_density') or gating.get('density') or {}), out)
    R.grid_phase_row((context or {}).get('cut_phase') or video.get('cut_phase') or {}, gating, out)

    silence = (context or {}).get('silence_windows') or video.get('silence_windows') or []
    if program_wav:
        R.cue_silence_row(program_wav, silence, gating, out)

    if probe is not None:
        R.dialogue_row(mix_report or {}, probe, gating, out)
        R.dialogue_band_row(mix_report or {}, probe, gating, out)
    elif mix_report:
        R.dialogue_row(mix_report, {'source': {'has_audio': True}}, gating, out)

    sections = (score.get('sections') or video.get('sections') or [])
    scenes = (context or {}).get('scenes') or video.get('scenes') or []
    caps = dict(_mapping(mapping) or {})
    for key in ('shot_scale_tolerance', 'shot_scale_max_density'):
        if gating.get(key) is not None:
            caps[key] = gating[key]
    caps.setdefault('shot_scale_tolerance', 0.15)
    R.shot_scale_row(sections, scenes, caps, out)

    profile = master_profile
    if profile is None:
        profile = {'loudness_mode': 'full_program', 'lufs': float((score.get('master') or {}).get('lufs', -14.0)),
                   'true_peak_db': float((score.get('master') or {}).get('true_peak', -1.5))}
    declared = str(profile.get('loudness_mode') or 'full_program')
    mask = None
    if program is not None:
        mask = _speech_mask_from_mix(mix_report, len(program), rate)
        if mask is None and mix_report and mix_report.get('speech_mask'):
            mask = np.asarray(mix_report['speech_mask'], np.float32) >= 0.5
    if program_wav:
        R.master_row(program_wav, profile, gating, out, mask=mask, sr=rate)
    measured_mode = 'dialogue' if (declared == 'dialogue' and mask is not None) else 'full_program'
    extras['gating_mode'] = measured_mode
    R.gating_mode_row(profile, measured_mode, out)

    if program is not None:
        try:
            import mixer as mx
            extras['lufs'] = round(float(mx.lufs(program, rate)), 2)
            extras['true_peak_db'] = round(float(mx.true_peak_db(program, rate)), 2)
            gated = mx.dialogue_gated_lufs(program, rate, mask) if mask is not None else None
            extras['dialogue_lufs'] = None if gated is None else round(float(gated), 2)
        except Exception:
            pass
    return out, extras
