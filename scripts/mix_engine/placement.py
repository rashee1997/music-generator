"""placement - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

import mix_schema
import numpy as np
import os
import presets
import roles as rolelib
import zlib
from .core import STATE, _level_by_role, _mix, _seating, _space, _space_owned, _space_owned_hook, _widen_by_role, resolve_space
from .dsp_utils import _air_absorb, _direct_gain, _pan_inplace, _proximity, _spatial_cfg, _use_proximity, _width_inplace, pair_half_width, place_of, widen
from .chains import from_table


def _imm():
    """The active mix preset's immersive block when it is switched on, else None."""
    c = _mix().get('immersive') or {}
    return c if c.get('enabled') else None


def _use_head_set(imm):
    """The head set is a preset value: a listener's own set when the piece names one, the bundled one otherwise."""
    from spatial_hrtf import binaural as _hrtf
    want_set = str(((imm or {}).get('hrtf') or {}).get('dataset') or '')
    try:
        _hrtf.set_dataset(_head_set(want_set))
    except Exception as e:
        print(f'  [spatial] head set "{want_set}" could not be used ({e}); using the bundled set')
        _hrtf.set_dataset(None)


def _head_set(name):
    """Resolve a mix preset's `immersive.hrtf.dataset` to a file path (None = the bundled set). A bare name looks in
    every project's presets/hrtf/ for <name>.sofa or <name>.mat; a path is used as given."""
    if not name or name.lower() in ('fabian', 'default', 'bundled'):
        return None
    if os.path.exists(name):
        return name
    for root in presets.PROJECT_ROOTS:
        for ext in ('.sofa', '.mat'):
            p = os.path.join(os.path.dirname(root), 'presets', 'hrtf', name + ext)
            if os.path.exists(p):
                return p
    raise FileNotFoundError(f'no presets/hrtf/{name}.sofa or .mat in any project; '
                            f'put the listener\'s set there or give a path')


def default_spec(tr):
    role = rolelib.canonical(tr.get('role', 'chord')) if tr.get('role') else 'chord'
    inst = str(tr.get('instrument', '')).lower().replace(' ', '_')
    # A role with no level is a leak, not a default: -8 dB is somewhere between a pad and a bass. Unlisted
    # roles are one of the four families now, so the number comes from the family's own entry.
    fam = rolelib.FAMILY_OF.get(role, 'harmony')
    level = _level_by_role().get(role)
    if level is None:
        level = _level_by_role().get({'figure': 'melody', 'harmony': 'chord',
                                      'rhythm': 'bass', 'colour': 'pad'}[fam], -8)
    sends = mix_schema.section(_mix(), 'space')['send_by_role']
    d = dict(role=role, gain_db=level,
             pan=from_table(_seating(), inst, 0.0) if role not in ('bass', 'drum', 'drone', 'percussion', 'ostinato') else 0.0,
             reverb=float(sends['default']), widen=_widen_by_role().get(role, 0.0))
    d['inst'] = inst

    passthrough = ('gain_db', 'pan', 'spatial', 'reverb', 'width', 'eq', 'comp', 'hp', 'lp', 'chain',
                   'saturation', 'mono_below', 'duck_by', 'duck_db', 'widen', 'fade_in_s', 'fade_out_s',
                   'intro_outro_boost_db', 'target_lufs', 'crossfade_start_s', 'crossfade_end_s',
                   'outro_start_s', 'outro_end_s', 'spectral_profile', 'preserve_spectrum', 'ref_lufs',
                   'dynamics', 'sidechain', 'pan_law', 'release_ms', 'attack_ms', 'smooth_s',
                   'duck_full_band', 'duck_band_hz')
    inst_cfg = None
    try:
        if inst.startswith('sfx:'):
            inst_cfg = presets.find_sfx(inst[4:])
        elif inst.startswith('env:'):
            inst_cfg = presets.find_environment(inst[4:])
        else:
            inst_cfg = presets.find_instrument(inst) or presets.find_vocal(inst)
        if inst_cfg and isinstance(inst_cfg, dict):
            # A physical scene already propagated its sound to the listener; applying this stage's
            # distance law again would attenuate it twice.
            prop = (inst_cfg.get('scene') or {}).get('propagation') or {}
            if prop.get('distance_m') is not None:
                d['scene_distance_m'] = float(prop['distance_m'])

            def _layer_d(l):
                for blk in (l.get('propagation'), (l.get('scene') or {}).get('propagation')):
                    if isinstance(blk, dict) and blk.get('distance_m') is not None:
                        return True
                return False
            n_scene = sum(1 for l in inst_cfg.get('scene_layers', []) or [] if _layer_d(l))
            if n_scene or (inst_cfg.get('propagation') or {}).get('distance_m') is not None:
                d['scene_distance_m'] = True
            for k in passthrough:
                if k in inst_cfg and inst_cfg[k] is not None:
                    d[k] = inst_cfg[k]
    except Exception as e:
        print(f'  [WARN] preset lookup for {inst!r} failed, using role defaults: {e}')

    sat = from_table(_mix().get('saturation') or {}, inst)
    if sat is not None:
        d['saturation'] = sat
    # The role's own send, unless the instrument preset set one. The per-role sends that used to be written here
    # (bass 0, drum 0.08, pad 0.30 ...) never applied: every role already carried the default by this line, so a
    # bass was sent to the room like a flute. They are data now (`space.send_by_role`): the schema default lists only
    # `default`, so an older piece mixes as it always has, and a preset that lists a role gets that role's send.
    if 'reverb' not in (inst_cfg if isinstance(inst_cfg, dict) else {}) and role in sends:
        d['reverb'] = float(sends[role])
    d.update({k: tr[k] for k in ('role',) + passthrough if k in tr and tr[k] is not None})
    return d


def guess_role(name):
    n = name.lower()
    for words, role in ((('drum', 'kick', 'snare', 'perc', 'hat', 'kit'), 'drum'), (('bass', 'sub', '808'), 'bass'),
                        (('pad', 'string', 'choir', 'organ', 'atmos', 'drone'), 'pad'),
                        (('lead', 'vocal', 'vox', 'melody', 'solo', 'flute', 'violin', 'sax'), 'melody'),
                        (('fx', 'sfx', 'riser', 'impact', 'noise'), 'fx'), (('arp', 'pluck', 'bell', 'spark'), 'arp')):
        if any(w in n for w in words):
            return role
    return 'chord'


def _place(name, x, spec, mx, sr):
    """Width, widen, pan, distance laws, the binaural route and the DRR send decision."""
    sp = spec.get('spatial')
    mono_render = bool(STATE.get('unplaced'))   # a one-channel deliverable: no pan, no width, no head, only distance
    if not sp:
        if mono_render:
            return x
        w = spec.get('width', 1.0)
        if w != 1.0:
            x = _width_inplace(x, w)
        if spec.get('widen', 0) > 0:
            x = widen(x, spec['widen'], seed=zlib.crc32(name.encode()) % 997, sr=sr)
        return _pan_inplace(x, spec.get('pan', 0.0), spec.get('pan_law', 'legacy'))

    imm = _imm()
    az, el, dist = place_of(spec, imm)

    sp_cfg = _spatial_cfg(mx, _space())
    ref_d = float(sp.get('ref_distance', sp_cfg.get('air_absorption_ref_distance', 1.5)))
    damp = float(sp.get('air_damping', sp_cfg.get('air_absorption_damping', 0.40)))
    min_cut = float(sp.get('min_cutoff_hz', sp_cfg.get('min_air_cutoff_hz', 3200.0)))
    falloff = float(sp.get('falloff_scale', sp_cfg.get('direct_falloff_scale', 0.18)))

    if mono_render:
        return _distance(x, spec, sp, dist, ref_d, damp, min_cut, falloff, sr)
    traj = sp.get('trajectory')
    binaural = bool(sp.get('binaural')) or bool(traj)
    route = sp.get('binaural')
    kind = sp.get('kind')
    if imm and sp.get('binaural') is not False:
        binaural, route = True, 'hrtf'
    elif kind == 'bed' and not traj:
        binaural = False
    elif kind == 'spot' and 'binaural' not in sp and _space().get('binaural', {}).get('spot'):
        binaural = True
    refl = resolve_space(sp['space']).get('reflections') if sp.get('space') else None
    space_arg = refl or sp.get('space') or (_space().get('reflections') if _space_owned_hook(_space()) else None) or 'outdoor_open'
    hrtf_ok = False
    # the ambisonic bus places this track itself (spatial_engine/hoa.py): hand it over unplaced, at its own level
    on_bus = bool(STATE.get('hoa') and imm and sp.get('binaural') is not False)
    if on_bus:                 # no width or widen either: in a 3-D field a stem's width is its pair angle
        x /= np.float32(max(dist, 1.0))
        return np.asarray(x, dtype=np.float32)
    if traj and (traj.get('keyframes') or traj.get('mode')):
        raise ValueError(f'track "{name}": trajectory keyframes and modes need the ambisonic bus; set '
                         f'"immersive": {{"enabled": true, "engine": "hoa_bus"}} in the mix preset')
    elif binaural and route == 'hrtf':
        from spatial_hrtf import binaural as _hrtf
        hrtf_ok = _hrtf.available()
        if not hrtf_ok:
            print('  [spatial] "binaural": "hrtf" asked for but the head data is missing: run '
                  '`python -m spatial_hrtf.data` from scripts/. Using spatial.py.')
    if hrtf_ok:
        _use_head_set(imm)
        # the near field belongs to the space, not to the mix: below one metre the ears hear different distances
        track_space = resolve_space(sp['space']) if sp.get('space') else _space()
        near = (track_space.get('distance') or {}).get('near_field')
        kw = dict(sr=sr, trajectory=traj, temp_c=float(sp.get('temp_c', 20.0)), rh=float(sp.get('rh', 50.0)),
                  near_field=near)
        mono = x.mean(axis=1)
        hw = pair_half_width(x, sp, imm) if imm and not traj else 0.0
        direct = (_hrtf.spatialize_pair(x, az, el, dist, hw, **kw) if hw > 0
                  else _hrtf.spatialize(mono, az, el, dist, **kw))
        if imm and not traj:
            import spatial
            refl_cfg = space_arg if isinstance(space_arg, dict) else (resolve_space(space_arg).get('reflections')
                                                                      or spatial.ACOUSTIC_SPACES.get(space_arg))
            path_physics = bool((refl_cfg or {}).get('path_physics', True))
            x = direct + (_hrtf.reflections(mono, az, dist, refl_cfg, sr=sr, path_physics=path_physics,
                                            temp_c=float(sp.get('temp_c', 20.0)), rh=float(sp.get('rh', 50.0)),
                                            elevation_deg=el)
                          if refl_cfg else 0.0)
            # the late field: several decorrelated tails from spread directions, or none when the preset says so
            tail = _hrtf.late(mono, az, dist, refl_cfg, sr=sr) if refl_cfg else None
            if tail is not None:
                x = x + tail
        else:
            x = direct
    elif binaural:
        import spatial
        if traj:
            x = spatial.render_trajectory(x.mean(axis=1), traj, acoustic_space=space_arg)
        else:
            p_db, p_hz = _use_proximity(sp_cfg, sp)
            x = spatial.spatialize_stem(x.mean(axis=1), azimuth_deg=az, elevation_deg=el, distance_m=dist,
                                        acoustic_space=space_arg, externalize=True,
                                        proximity_db=p_db, proximity_hz=p_hz,
                                        er_distance_exponent=sp_cfg.get('er_distance_exponent'), sr=sr)
    # A. distance air absorption
    own_distance = spec.get('scene_distance_m') is not None
    if not binaural and not own_distance and dist > ref_d and sp.get('air_absorption', True):
        x = _air_absorb(x, sp, dist, ref_d, damp, min_cut, sr)
    # B. 1/r direct level (in place from here on: this stem's buffer is already private to this mix)
    if not binaural and not own_distance and dist > 1.0:
        x *= np.float32(_direct_gain(dist, falloff))
    if not binaural and not own_distance:
        p_db, p_hz = _use_proximity(sp_cfg, sp)
        x = _proximity(x, dist, ref_d, p_db, p_hz, sr)
    # C. apparent source width
    spread = float(np.clip(float(sp.get('spread', 0.0)), 0.0, 1.0))
    w = float(sp.get('width', spec.get('width', 1.0))) * (1.0 + spread)
    if w != 1.0:
        x = _width_inplace(x, w)
    widen_amt = float(sp.get('widen', spec.get('widen', 0.0)))
    if widen_amt > 0:
        x = widen(x, widen_amt, seed=zlib.crc32(name.encode()) % 997, sr=sr)
    # D. pan (no comb delays)
    pan_val = float(sp.get('pan', np.clip(np.sin(np.radians(az)), -1.0, 1.0))) * (1.0 - spread)
    if not binaural:
        x = _pan_inplace(x, pan_val, sp.get('pan_law', spec.get('pan_law', 'legacy')))
    return x


def _distance(x, spec, sp, dist, ref_d, damp, min_cut, falloff, sr):
    """What distance does to a source that is not placed by a head filter: air absorption and the 1/r level. The
    same two laws _place applies to a panned stem, for a deliverable that has no directions to place it in."""
    if spec.get('scene_distance_m') is not None:        # a physical scene already propagated itself
        return x
    if dist > ref_d and sp.get('air_absorption', True):
        x = _air_absorb(x, sp, dist, ref_d, damp, min_cut, sr)
    if dist > 1.0:
        x = x * np.float32(_direct_gain(dist, falloff))
    p_db, p_hz = _use_proximity(_spatial_cfg(_mix(), _space()), sp)
    return _proximity(np.asarray(x, dtype=np.float32), dist, ref_d, p_db, p_hz, sr)
