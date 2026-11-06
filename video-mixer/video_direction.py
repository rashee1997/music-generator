# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
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
"""video_direction.py - turn probe numbers into a direction sheet, a hit list and a score.

    python3 video-mixer/video_direction.py reports/video_probe.json --preset default --out direction/video_shot.json

Every mapping is a key in the video preset (`direction_map`, `hits`, `mix`, `master`). No tempo, key, mode,
pan or hit rule is written here in code.

  cuts        -> tempo (frame-locked when the preset asks for it) and hit points
  energy      -> intensity (arrangement density follows the picture's own energy)
  luminance   -> major / minor
  centre      -> azimuth of the lead, so the music follows the action across the frame
  warmth      -> timbre handed to the mix preset
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
for p in (HERE, os.path.join(SKILL, 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)


def tempo_from_cuts(cut_times, cfg, fps):
    """A tempo the cuts sit on. Each cut interval is taken as 1, 2, 4 or 8 beats; the closest to `prefer_bpm`
    (or the middle of the allowed range) wins. Frame lock snaps the tempo so one beat is a whole number of frames."""
    tc = cfg['tempo_from_cuts']
    lo, hi, q = float(tc['min_bpm']), float(tc['max_bpm']), float(tc['quantise_bpm'])
    prefer = float(tc.get('prefer_bpm') or (lo + hi) / 2.0)
    intervals = [b - a for a, b in zip(cut_times, cut_times[1:]) if b - a > 1e-3]
    if not intervals:
        bpm = round(prefer / q) * q
        return dict(bpm=bpm, method='no cut: preset preference', frame_lock=None)
    median = float(np.median(intervals))
    best = None
    for beats in (1, 2, 4, 8):
        bpm = 60.0 * beats / median
        frames = None
        if tc.get('prefer_frame_lock') and fps > 0:
            frames = max(1, int(round(fps * 60.0 / bpm)))
            bpm = fps * 60.0 / frames
        bpm = round(bpm / q) * q
        if lo <= bpm <= hi:
            score = abs(bpm - prefer)
            if best is None or score < best[0]:
                best = (score, bpm, beats, frames)
    if best is None:                                  # no interval fits the range: clamp, and say so
        bpm = min(hi, max(lo, round(prefer / q) * q))
        return dict(bpm=bpm, method=f'no interval in {lo:g}-{hi:g} bpm: clamped to preference', frame_lock=None)
    _, bpm, beats, frames = best
    how = f'median cut interval {median:.3f}s = {beats} beat(s)'
    if frames:
        how += f', frame-locked at {frames} frame(s)/beat'
    return dict(bpm=float(bpm), method=how, frame_lock=frames)


def mode_from_luma(luma, cfg):
    for rule in cfg['luminance_to_mode']:
        if luma < float(rule['below']):
            return rule['mode']
    return cfg['luminance_to_mode'][-1]['mode']


def azimuth_from_centre(centre, cfg):
    cm = cfg['centre_of_motion_to_pan']
    lo, hi = float(cm['range'][0]), float(cm['range'][1])
    x = 0.0 if hi <= lo else (float(centre) - lo) / (hi - lo) * 2.0 - 1.0
    return float(np.clip(x, -1.0, 1.0) * float(cm['max_azimuth_deg']))


def staging_from_centre(centre, cfg):
    """One position per role: azimuth follows the action, elevation and distance come from the preset."""
    az = azimuth_from_centre(centre, cfg['direction_map'])
    space = cfg['staging']['space']['name']
    out = {}
    for role, pos in cfg['staging'].items():
        if role == 'space':
            continue
        out[role] = dict(azimuth=round(az if role in ('lead', 'pad') else 0.0, 2),
                         elevation=float(pos['elevation']), distance=float(pos['distance']), space=space)
    return out


def hits_from_probe(rep, cfg, bpm, duration_s):
    """Cut hits first, then motion hits, thinned to the preset's gap and per-minute budget.

    A cut is a hard sync point (the picture jumps and the ear already flinches there), a movement inside a shot is a
    soft one (a few frames either way are inaudible). Only the hard ones are judged against the cut list.
    """
    h = cfg['hits']
    classes = h.get('classes') or {}
    min_gap = float(h['min_gap_beats']) * 60.0 / float(bpm)
    budget = int(np.ceil(max(duration_s, 0.1) / 60.0 * int(h['max_hits_per_minute'])))
    want = [(c['t'], h['cut_sound'], float(h['cut_velocity']), 'cut') for c in rep['cuts']]
    want += [(m['t'], h['motion_sound'], float(h['motion_velocity']), 'motion') for m in rep['motion_hits']]
    kept = []
    for t, sound, vel, kind in sorted(want):
        if t <= 0:
            continue
        if kept and t - kept[-1]['t_s'] < min_gap:
            continue
        kept.append(dict(t_s=round(float(t), 4), sound=sound, velocity=vel, kind=kind,
                         sync='hard' if kind == 'cut' else 'soft',
                         # a cut or a movement is dead on; a reaction accent is chosen by the spotting, never guessed
                         **({'class': 'dead_on'} if classes else {})))
        if len(kept) >= budget:
            break
    return kept


def sections_from_energy(rep, cfg, duration_s):
    """The picture's own arc, in sections a director would mark: how hard the frame is moving, moment to moment.

    Only what was measured goes in (a label from `direction_map.energy_sections`, its times and its energy). What the
    music does inside a section is a hand decision, not something the probe can know.
    """
    ec = cfg['direction_map'].get('energy_sections') or {}
    bins = [float(v) for v in (rep.get('energy') or [])]
    if not ec.get('enabled', True) or not bins or duration_s <= 0:
        return []
    names = ec['names']
    step = float(duration_s) / len(bins)
    out = []
    for i, e in enumerate(bins):
        label = next((r['name'] for r in names if e < float(r['below'])), names[-1]['name'])
        out.append(dict(name=label, start_s=round(i * step, 3), end_s=round((i + 1) * step, 3),
                        energy=round(e, 3), role=label,
                        action=f'measured picture energy {e:.2f} in this slice'))
    return out


def direction_sheet(rep, cfg, brief_text='', title=None, context=None, film=None):
    """The direction sheet: the same fields as `templates/direction_sheet.json`, filled from the picture.

    With `context`, the sheet stops being a summary of one file and becomes a read of the
    reel: one section per scene, each with what the music may do in it (`density`, `shot_scale`,
    `allowed_roles`), so the measured arc reaches the score instead of one mean energy.
    """
    dm = cfg['direction_map']
    src = rep['source']
    duration = float(src['duration_s'])
    tempo = tempo_from_cuts([c['t'] for c in rep['cuts']], dm, float(src['fps']))
    mode = mode_from_luma(float(rep['luma_mean']), dm)
    master = cfg['master_profiles'][cfg['master']['profile']]
    feels = [w for w in brief_text.split() if w] or ['cinematic', 'restrained']
    hits = hits_from_probe(rep, cfg, tempo['bpm'], duration)
    mix_cfg, gate_cfg = cfg['mix'], cfg['gate']
    has_audio = bool(src['has_audio'])
    why = {'cut': 'a picture cut: the frame jumps and the ear flinches there anyway',
           'motion': 'a movement inside a shot, not an edit: soft sync, accent and get out'}
    sheet = dict(
        title=title or os.path.splitext(os.path.basename(rep['path']))[0],
        version=1,
        medium='film',
        brief=brief_text or 'no brief given: the picture and its energy decided this cue',
        audience='the picture\'s own audience, hearing this cue under the film',
        purpose=f'score the picture {os.path.basename(rep["path"])} ({duration:.1f}s, {src["fps"]:.3f} fps)',
        point_of_view='the camera: the music follows what the frame is doing, not a character\'s inner state',
        job=list(dm.get('job') or []),
        story=(f'{len(rep["cuts"])} cuts, {len(rep["motion_hits"])} movements, energy '
               f'{min(rep["energy"] or [0]):.2f}-{max(rep["energy"] or [0]):.2f}; no dialogue'
               if not has_audio else
               f'{len(rep["cuts"])} cuts, {len(rep["motion_hits"])} movements, dialogue present, energy '
               f'{min(rep["energy"] or [0]):.2f}-{max(rep["energy"] or [0]):.2f}'),
        duration_s=round(duration, 3),
        in_point_s=0.0,
        out_point_s=round(duration, 3),
        ending=dm.get('default_ending', 'tail_out'),
        tempo_bpm=tempo['bpm'],
        tempo_method=tempo['method'],
        key=dm['default_key'],
        mode=mode,
        feel=feels[:6],
        avoid_feel=['busy', 'harsh', 'robotic', 'cartoon', 'new-age cliche'],
        sections=sections_from_energy(rep, cfg, duration),
        instruments=[],
        spatial_staging=staging_from_centre(float(rep['centre_mean']), cfg),
        mix_intent=dict(hero='lead', support=['pad', 'bass'], sits_under=['dialogue'] if has_audio else [],
                        must_hear=['the lead above the bed', 'the low end with the bass and the hits'] +
                                  (['250-3800 Hz kept clear while the voice speaks'] if has_audio else []),
                        leave_free_hz=list(mix_cfg['speech_band_hz'])),
        loudness_lufs=float(master['lufs']),
        true_peak_max=float(master['true_peak_db']),
        delivery=dict(format=cfg['mux']['container'], sample_rate=int(cfg['master']['sample_rate']),
                      bit_depth=int(cfg['master']['bit_depth']), stage=cfg['master']['profile']),
        references=[brief_text] if brief_text else [],
        hits_at=[h['t_s'] for h in hits],
        hits=[dict(t=h['t_s'], kind=h['kind'], sync=h['sync'], sound=h['sound'],
                   why=why[h['kind']]) for h in hits],
        piece_type='video_dialogue' if has_audio else 'video_basic',
        video=dict(enabled=True, preset=cfg.get('name', 'default'), source=rep['path'], in_s=0.0,
                   out_s=round(duration, 3), duration_s=round(duration, 3), fps=float(src['fps']),
                   cuts=[c['t'] for c in rep['cuts']], cuts_count=len(rep['cuts']), cut_source=rep['cut_source'],
                   motion_hits=len(rep['motion_hits']), energy=rep['energy'],
                   luma=rep['luma_mean'], warmth=rep['warmth_mean'], centre=rep['centre_mean'],
                   azimuth=round(azimuth_from_centre(float(rep['centre_mean']), dm), 2),
                   has_audio=has_audio,
                   cut_sync=dict(gate_cfg['cut_sync']),
                   dialogue=dict(present=has_audio, duck_db=float(mix_cfg['duck_db']),
                                 snr_min_db=float(gate_cfg['dialogue_snr_min_db'])),
                   master_profile=cfg['master']['profile'],
                   deliverable=dict(container=cfg['mux']['container'],
                                    audio_codec=cfg['mux']['audio_codec'].get(cfg['mux']['container']),
                                    bitrate=cfg['mux']['audio_bitrate'], video_copy=cfg['mux']['video_copy']),
                   notes='filled from the picture by video-mixer/video_direction.py; the music still follows '
                         'every rule in the rest of this sheet')
    )
    if context:
        mapping = (film or {}).get('mapping') or {}
        sheet['sections'] = sections_from_context(context, mapping, fallback=sheet['sections'])
        sheet['reel'] = context.get('reel')
        sheet['video']['scenes'] = context.get('scenes') or []
        sheet['video']['motion_beats'] = context.get('motion_beats') or []
        sheet['video']['cut_phase'] = context.get('cut_phase') or {}
        sheet['video']['silence_windows'] = [(float(s['start_s']), float(s['end_s']))
                                            for s in context.get('scenes') or [] if s.get('music_gap')]
        sheet['story'] = (f"{len(context.get('shots') or [])} shots in {len(context.get('scenes') or [])} scenes; "
                          f"{context.get('reel', {}).get('motion_profile', 'unknown')} movement; "
                          f"{'speech present' if has_audio else 'no speech'}")
        sheet['energy'] = round(float(np.mean([float(s.get('energy') or 0.0)
                                              for s in context.get('scenes') or []] or [0.0])), 4)
    return sheet


def _tone(cfg, rep):
    """Timbre from the picture's warmth: the preset maps warm/cold to a master tone."""
    wt = cfg['direction_map']['warmth_to_timbre']
    return wt['warm'] if float(rep.get('warmth_mean', 0.0)) > 0 else wt['cold']


def class_shift(hit, hits_cfg):
    """(class, seconds after its picture moment) for one hit.

    A dead-on hit sits on the frame. A reaction hit sits after the audience's own
    reaction time, because a line or a look has to be absorbed before it can be
    answered (Robin Hoffmann, Placement of Hit Points).
    """
    classes = (hits_cfg or {}).get('classes') or {}
    cls = str(hit.get('class') or 'dead_on')
    return cls, float((classes.get(cls) or {}).get('after_s', 0.0))


def sections_from_context(context, mapping_cfg, fallback=None):
    """A section per scene, with what the music may do in it.

    `density` is the section's *allowance*: the shot-scale cap scaled by the scene's
    own energy. What actually ends up sounding is measured later by
    `apply_section_arrangement`, which is what `video.shot_scale` judges.
    """
    scenes = (context or {}).get('scenes') or []
    if not scenes:
        return list(fallback or [])
    caps = mapping_cfg.get('shot_scale_max_density') or {}
    roles = mapping_cfg.get('scene_role') or {}
    out = []
    for s in scenes:
        scale = s.get('shot_scale') or 'medium'
        energy = float(s.get('energy') or 0.0)
        density = section_density(scale, energy, mapping_cfg)
        allowed = allowed_roles(density, mapping_cfg)
        action = (f"{s.get('shots', 1)} shot(s), {scale} shot, motion {float(s.get('motion') or 0):.2f}, "
                  f"speech {float(s.get('speech_activity') or 0) * 100:.0f} %")
        music = (f"{', '.join(allowed) or 'lead'} at density {density:.2f} "
                 f"({scale} cap {float(caps.get(scale, 1.0)):.2f}, energy {energy:.2f})")
        out.append(dict(name=f"scene {s.get('id', len(out) + 1)}", start_s=float(s['start_s']),
                        end_s=float(s['end_s']), energy=energy, shot_scale=scale,
                        role=roles.get(scale, s.get('role') or 'build'), action=action, music=music,
                        density=round(density, 3), allowed_roles=allowed))
    return out


def section_density(scale, energy, mapping_cfg):
    """How much of the ensemble a section may carry: the shot-scale cap, half of it floor at silence."""
    cap = float((mapping_cfg.get('shot_scale_max_density') or {}).get(scale, 1.0))
    return round(max(0.0, min(1.0, cap * (0.5 + 0.5 * float(energy)))), 3)


def allowed_roles(density, mapping_cfg):
    """The roles a section of this density may sound, from the preset's own table."""
    table = mapping_cfg.get('layers_by_density') or []
    for row in table:
        if float(density) < float(row.get('below', 1.01)):
            return list(row.get('roles') or [])
    return list((table[-1] or {}).get('roles') or []) if table else []


def _section_at(sections, t_s):
    for s in sections:
        if float(s['start_s']) <= t_s < float(s['end_s']):
            return s
    return None


def apply_section_arrangement(score, sheet, mapping_cfg):
    """Let the measured arc reach the score instead of a single mean energy.

    Each note is kept only where its role is allowed at that section's density, so a
    close-up holds a lead and a wide holds the band. The section's realised
    `density` is then measured from what survived, which is what `video.shot_scale`
    judges: an allowance the arrangement ignored is a fact, not an intention.
    """
    sections = sheet.get('sections') or []
    if not sections or not score.get('tracks'):
        return score
    bpm = float(score.get('bpm') or 120.0)
    for s in sections:
        s.setdefault('density', section_density(s.get('shot_scale') or 'medium',
                                                float(s.get('energy') or 0.0), mapping_cfg))
        s['allowed_roles'] = s.get('allowed_roles') or allowed_roles(float(s['density']), mapping_cfg)
    all_roles = sorted({str(t.get('role')) for t in score['tracks'] if t.get('notes')})
    for track in score['tracks']:
        if not track.get('notes') or track.get('role') in ('sfx', 'environment', 'drum'):
            continue
        role = str(track.get('role'))
        keep = []
        for n in track['notes']:
            t_s = float(n.get('t', 0.0)) * 60.0 / bpm
            sec = _section_at(sections, t_s)
            if sec is None or role in (sec.get('allowed_roles') or [role]):
                keep.append(n)
        track['notes'] = keep
    score['tracks'] = [t for t in score['tracks'] if t.get('notes') or t.get('role') in ('sfx', 'environment')]
    for s in sections:
        present = {str(t.get('role')) for t in score['tracks'] for n in t.get('notes') or []
                   if float(s['start_s']) <= float(n.get('t', 0.0)) * 60.0 / bpm < float(s['end_s'])}
        s['density'] = round(len(present) / len(all_roles), 3) if all_roles else 0.0
        s['roles_present'] = sorted(present)
    score['sections'] = sections
    return score


def score_from_sheet(sheet, cfg, rep, context=None, mapping=None):
    """Build the score through compose (so every musical decision stays in the engine), then place the hits.

    Hits are written at fractional beats: beat = t_s * bpm / 60. compose.add_hit_points rounds to half beats,
    which would throw a cut hit up to a beat away, so it is bypassed on purpose. A reaction-class hit is written
    `after_s` past its picture moment, and the offset travels with it so the gate can check the class was honoured.
    """
    import compose
    has_audio = bool(rep['source']['has_audio'])
    space = cfg['staging']['space']['name']
    bed_lufs = float(cfg['mix']['music_bed_lufs']) if has_audio else float(sheet['loudness_lufs'])
    brief = dict(title=sheet['title'], duration_s=sheet['duration_s'], bpm=sheet['tempo_bpm'],
                 key=sheet['key'], mode=sheet['mode'], emotion=' '.join(sheet['feel']),
                 energy=float(np.mean(rep['energy'])) if rep['energy'] else 0.5,
                 piece_type=sheet['piece_type'], voiceover=has_audio, lufs=bed_lufs,
                 seed=int(sheet.get('seed', 7)), hit_points=[], space=space)
    score = compose.compose(brief)
    score['title'] = sheet['title']
    score['bpm'] = float(sheet['tempo_bpm'])
    score['key'] = f"{sheet['key']} {sheet['mode']}"
    score['space'] = space
    score['room'] = space
    score['master'] = dict(lufs=bed_lufs, true_peak=float(sheet['true_peak_max']), tone=_tone(cfg, rep))
    score['mix_preset'] = cfg['mix_preset']['name']
    score['piece_type'] = sheet['piece_type']
    score['video'] = sheet['video']
    beat = 60.0 / float(sheet['tempo_bpm'])
    dur_beats = float(cfg['hits']['duration_s']) / beat
    hit_pos = cfg['staging']['drum']
    hits_cfg = cfg['hits']
    placed = []
    for i, h in enumerate(hits_from_probe(rep, cfg, sheet['tempo_bpm'], sheet['duration_s'])):
        cls, shift = class_shift(h, hits_cfg)
        score['tracks'].append(dict(name=f'hit_{i + 1:02d}', instrument=h['sound'], role='sfx',
                                    spatial=dict(azimuth=0.0, elevation=float(hit_pos['elevation']),
                                                 distance=float(hit_pos['distance']), space=space),
                                    gain_db=float(cfg['mix']['sfx_headroom_db']),
                                    notes=[dict(t=round((h['t_s'] + shift) / beat, 4), d=round(dur_beats, 4),
                                                v=float(h['velocity']))]))
        placed.append(dict(t=h['t_s'] + shift, kind=h['kind'], sync=h['sync'], sound=h['sound'],
                           event_t=h['t_s'], offset_s=shift, **({'class': cls} if hits_cfg.get('classes') else {})))
    if placed:
        sheet['hits'] = [dict(p, why=next((x['why'] for x in sheet['hits'] if abs(x['t'] - p['event_t']) < 1e-6),
                                    'placed from the picture')) for p in placed]
        sheet['hits_at'] = [round(p['t'], 4) for p in placed]
        sheet['video']['hits'] = placed
        sheet['video']['hits_at'] = sheet['hits_at']
    if mapping is not None:
        apply_section_arrangement(score, sheet, mapping)
    elif sheet.get('sections'):
        score['sections'] = sheet['sections']
    if context:
        score['video'].update(context=dict(reel=context.get('reel'), scenes=context.get('scenes'),
                                           cut_phase=context.get('cut_phase'),
                                           motion_beats=context.get('motion_beats')))
        score['video']['scenes'] = context.get('scenes') or []
        score['video']['motion_beats'] = context.get('motion_beats') or []
        score['video']['cut_phase'] = context.get('cut_phase') or {}
        score['video']['silence_windows'] = [(float(s['start_s']), float(s['end_s']))
                                            for s in context.get('scenes') or [] if s.get('music_gap')]
    score['video']['hits_cfg'] = dict(hits_cfg)
    score['video']['gate_cfg'] = dict((cfg.get('gate') or {}))
    score['video']['sections'] = [{k: s.get(k) for k in ('name', 'start_s', 'end_s', 'energy', 'shot_scale',
                                                         'density', 'roles_present')}
                                  for s in score.get('sections') or []]
    return score


def write_direction(sheet, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(sheet, fh, indent=2)
    return path


def main():
    import argparse
    import presets
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('probe')
    ap.add_argument('--preset', default='default')
    ap.add_argument('--project')
    ap.add_argument('--brief', default='')
    ap.add_argument('--out', default=None)
    ap.add_argument('--score', default=None)
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    cfg = presets.get('video', a.preset)
    with open(a.probe, encoding='utf-8') as fh:
        rep = json.load(fh)
    sheet = direction_sheet(rep, cfg, a.brief)
    if a.out:
        write_direction(sheet, a.out)
        print(f'  wrote {a.out}')
    print(json.dumps({k: sheet[k] for k in ('title', 'duration_s', 'tempo_bpm', 'tempo_method', 'key', 'mode', 'hits_at')}, indent=2))
    if a.score:
        score = score_from_sheet(sheet, cfg, rep)
        with open(a.score, 'w', encoding='utf-8') as fh:
            json.dump(score, fh, indent=2)
        print(f'  wrote {a.score} ({len(score["tracks"])} tracks)')


if __name__ == '__main__':
    main()
