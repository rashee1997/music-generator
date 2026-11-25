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


def _mapping(mapping=None):
    """The film mapping preset, which owns the shot-scale density caps. A missing preset is an error."""
    if mapping is not None:
        return mapping
    import presets
    return presets.get('film', 'mapping')


def _shot_scale_cfg(gate, mapping=None):
    """Density caps and tolerance for video.shot_scale: the film mapping owns the caps, the delivery gate the
    tolerance. Neither has a code default; a missing one is an error."""
    caps = dict(_mapping(mapping))
    for key in ('shot_scale_tolerance', 'shot_scale_max_density'):
        if (gate or {}).get(key) is not None:
            caps[key] = gate[key]
    for key in ('shot_scale_tolerance', 'shot_scale_max_density'):
        if caps.get(key) is None:
            raise ValueError(f'video.shot_scale needs "{key}" in the film mapping or delivery preset; none was given')
    return caps


def _hits_of(video):
    hits = [dict(h) for h in (video.get('hits') or [])]
    if not hits and video.get('hits_at'):
        hits = [dict(t_s=float(t), kind='cut') for t in video['hits_at']]
    return hits


def probe_rows(score, out=None, mapping=None):
    """Rows that need only the score and its own block: no program, no picture file.

    Used when a score carries a `video` block but no program was built, so a plain music render of a film cue is
    still held to the picture rows it can answer. Limits come from the score's own `video.gate_cfg` / `hits_cfg`
    (copied from the film presets when the score was built); a limit the score does not carry is an error.
    """
    out = [] if out is None else out
    video = score.get('video') or {}
    if not video.get('enabled'):
        return out
    gate = dict(video.get('gate_cfg') or {})
    if 'cut_sync' not in gate and video.get('cut_sync'):
        gate['cut_sync'] = video['cut_sync']
    hits_cfg = dict(video.get('hits_cfg') or {})
    hits = _hits_of(video)
    cuts = video.get('cuts') or []
    R.cut_sync_row(cuts, hits, gate, out, dropped=video.get('dropped_cuts'))
    peaks = video.get('motion_peaks')
    R.motion_sync_row(peaks if peaks else (video.get('motion_beats') or []), hits, gate, out,
                      independent=bool(peaks))
    R.hit_class_row(hits, dict(hits_cfg, classes=hits_cfg.get('classes') or {}), out)
    R.hit_density_row(hits, cuts, float(video.get('duration_s') or 0.0),
                      dict(hits_cfg, density=gate.get('hit_density') or hits_cfg.get('density') or {}), out)
    R.grid_phase_row(video.get('cut_phase') or {}, gate, out)
    R.shot_scale_row(video.get('sections') or score.get('sections') or [],
                     video.get('scenes') or [], _shot_scale_cfg(gate, mapping), out)
    return out


def pass_rows(score, context=None, probe=None, program_wav=None, mix_report=None,
              gating=None, master_profile=None, hits=None, out=None, sr=None, mapping=None,
              applied_mode=None, silence_windows=None):
    """Every picture row. Returns (rows, extras).

    `applied_mode` is the gating mode `video_program_mix.master()` reports it applied. For a dialogue-gated
    profile it must be given: a mode nobody reported is "unreported" and fails `video.gating_mode`, because the
    master can fall back to full-program loudness and nothing else records it. `silence_windows` are the
    spotting's no-music windows (reel time of this cue).

    extras carries what the report needs: the cut offsets, the measured gating mode, and the loudness figures in
    both modes so a reader can see the difference.
    """
    import soundfile as sf
    out = [] if out is None else out
    video = score.get('video') or {}
    hits = [dict(h) for h in (hits if hits is not None else video.get('hits') or [])]
    gating = gating or {}
    extras = dict(cut_sync=[], motion_sync=[], gating_mode=None, lufs=None, true_peak_db=None)

    program, rate = None, int(sr or 44100)
    if program_wav:
        try:
            program, rate = sf.read(program_wav, always_2d=True)
            program = program.astype(np.float32)       # decoded once; every row below reads this array
        except Exception:
            program = None
    audio = (program, rate) if program is not None else None

    if probe and probe.get('source'):
        picture_s = float(probe['source']['duration_s'])
        R.duration_row(probe, len(program) / float(rate) if program is not None
                       else float(video.get('duration_s') or 0.0), gating, out)
        cuts = probe.get('cuts') or []
        peaks = probe.get('motion_peaks')
        independent = bool(peaks)
        motion_beats = peaks if independent else (probe.get('motion_hits') or [])
    else:
        picture_s = float(video.get('duration_s') or 0.0)
        if program is not None:
            R.duration_row({'source': {'duration_s': picture_s}}, len(program) / float(rate), gating, out)
        cuts = video.get('cuts') or []
        peaks = video.get('motion_peaks')
        independent = bool(peaks)
        motion_beats = peaks if independent else (video.get('motion_beats') or [])

    extras['cut_sync'] = R.cut_sync_row(cuts, hits, gating, out, dropped=video.get('dropped_cuts'))
    extras['motion_sync'] = R.motion_sync_row(motion_beats, hits, gating, out, independent=independent)
    R.hit_class_row(hits, gating.get('classes') or (gating.get('hits') or {}), out)
    R.hit_density_row(hits, cuts, float(video.get('duration_s') or picture_s or 0.0),
                      dict(gating, density=gating.get('hit_density') or gating.get('density') or {}), out)
    R.grid_phase_row((context or {}).get('cut_phase') or video.get('cut_phase') or {}, gating, out)

    silence = (silence_windows if silence_windows is not None else
               (context or {}).get('silence_windows') or video.get('silence_windows') or [])
    if program_wav:
        R.cue_silence_row(program_wav, silence, gating, out, audio=audio)

    if probe is not None:
        R.dialogue_row(mix_report or {}, probe, gating, out)
        R.dialogue_band_row(mix_report or {}, probe, gating, out)
    elif mix_report:
        R.dialogue_row(mix_report, {'source': {'has_audio': True}}, gating, out)

    sections = (score.get('sections') or video.get('sections') or [])
    scenes = (context or {}).get('scenes') or video.get('scenes') or []
    R.shot_scale_row(sections, scenes, _shot_scale_cfg(gating, mapping), out)

    profile = master_profile
    if profile is None:
        profile = {'loudness_mode': 'full_program', 'lufs': float((score.get('master') or {}).get('lufs', -14.0)),
                   'true_peak_db': float((score.get('master') or {}).get('true_peak', -1.5))}
    declared = str(profile.get('loudness_mode') or 'full_program')
    mask = _speech_mask_from_mix(mix_report, len(program), rate) if program is not None else None
    if program_wav:
        R.master_row(program_wav, profile, gating, out, mask=mask, sr=rate, audio=audio)
    if applied_mode is not None:
        measured_mode = str(applied_mode)
    elif declared == 'full_program':
        measured_mode = 'full_program'                  # nothing was claimed beyond the whole program
    else:
        measured_mode = 'unreported'                    # a gating claim nobody confirmed is not a pass
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
