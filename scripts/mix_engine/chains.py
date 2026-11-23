"""chains - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

import compute
import dsp
import json
import mix_context
import mix_schema
import numpy as np
import os
import pedalboard as pb
import presets
import roles as rolelib
import stem_cache
from .core import REF_LUFS, SR, STATE, _active_db, _gs, _install, _max_boost_db, _mix
from .dsp_utils import _band, _curve, _dsp_dynamics, _run, active_lufs, dynamics_cfg, eq_object, mono_below, to_stereo

MIX_CACHE_VERSION = 1                   # bump when the chain's output would change without its inputs changing

_CODE_TAG = None                        # the engine's own identity, hashed once per process


def role_chain(role, mx=None):
    """The EQ + compression a role starts with, from the mix preset (schema defaults underneath)."""
    chains = (mx or _mix()).get('role_chains') or mix_schema.ROLE_CHAINS
    return chains.get(role) or chains.get('default') or {}


def spectral_chain(role, spec, mx=None):
    """(chain, source): a named spectral profile if the stem has one, else its role chain.

    "preserve_spectrum": true bypasses the automatic chain entirely — for a physically modelled source
    whose spectrum is the point.
    """
    mx = mx or _mix()
    if spec.get('preserve_spectrum'):
        return {}, 'bypassed'
    prof = spec.get('spectral_profile')
    profs = ((mx.get('spectral') or {}).get('profiles') or {})
    if prof and prof in profs:
        return profs[prof], f'profile:{prof}'
    if prof:
        raise ValueError(f'unknown spectral profile "{prof}" (known: {", ".join(sorted(profs))})')
    return role_chain(role, mx), f'role:{role}'


def _chain_objects(chain):
    out = [eq_object(b) for b in (chain.get('eq') or [])]
    c = chain.get('comp')
    if isinstance(c, dict):
        out.append(pb.Compressor(threshold_db=c.get('thr', -22), ratio=c.get('ratio', 2.5),
                                 attack_ms=c.get('attack', 15), release_ms=c.get('release', 150)))
    return out


def role_board(role, inst='', mx=None):
    """Starting-point EQ + compression per role. A preset's "role_chains" replaces one role."""
    return _chain_objects(role_chain(role, mx)) + inst_eq(inst)


def base_names(inst):
    """The names an instrument answers to, own name first: a preset called lead_flute is built on 'flute'
    (its gm / instrument key), and a world name such as quena stands in for a General MIDI sound."""
    name = str(inst).lower().replace(' ', '_')
    out = [name]
    try:
        cfg = presets.find_instrument(name) or presets.find_vocal(name) or {}
    except Exception:
        cfg = {}
    for key in ('gm', 'instrument'):
        v = cfg.get(key)
        if isinstance(v, str) and v.lower() not in out:
            out.append(v.lower().replace(' ', '_'))
    import world
    for n in list(out):
        w = world.INSTRUMENTS.get(n)
        if isinstance(w, str) and w not in out:
            out.append(w)
    return out


def from_table(table, inst, default=None):
    """First hit of `table` for the instrument's own name, then its base names."""
    for n in base_names(inst):
        if n in table:
            return table[n]
    return default


def inst_eq(inst):
    """The instrument's tone moves, from the mix preset's inst_eq table."""
    return [eq_object(b) for b in from_table(_mix().get('inst_eq') or {}, inst, [])]


def gain_stage(x, l, role, spec, gs=None, sr=SR):
    """The gain, in dB, that brings this stem to its level.

    'legacy' (the default): the playing part to ref_lufs, boost capped by max_boost_db — unchanged.
    'adaptive': a per-role reference, a cut cap, a peak-headroom cap and a crest guard, so a delicate
    layer, a percussion stem and a physical ambience recording keep their own dynamic behaviour instead of
    all being pushed to one number.
    """
    gs = gs or _gs()
    strategy = str(gs.get('strategy', 'legacy')).lower()
    ref = float(gs.get('ref_lufs', REF_LUFS))
    max_boost = float(gs.get('max_boost_db', _max_boost_db()))
    if rolelib.is_lead(role):
        # A lead is the reference everything else is judged against, so it has to reach its level. The boost cap
        # exists to protect near-silent ambience; it is not a statement that a quietly played lead must stay buried
        # (a GM lead under a soft dynamics arc sat 15-25 dB under the beds and every bed then read "too loud").
        max_boost = max(max_boost, 24.0)
    if spec.get('target_lufs') is not None and l > -69:
        gain = float(spec['target_lufs']) - l
    elif l > -69:
        if strategy == 'adaptive':
            ref = float(spec.get('ref_lufs', (gs.get('ref_by_role') or {}).get(role, ref)))
        gain = min(ref - l, max_boost)
    elif role == 'environment':
        rms = float(np.sqrt(np.mean(np.asarray(x, np.float64) ** 2) + 1e-12))
        target = float(spec.get('target_lufs', _mix().get('env_target_lufs', -24.0)))
        scale = float(gs.get('env_fallback_rms_scale', 0.5))
        gain = 20 * np.log10((10 ** (target / 20.0) * scale) / rms) if rms > 1e-6 else 0.0
    else:
        return 0.0
    if strategy != 'adaptive':
        return float(gain)
    gain = max(gain, -abs(float(gs.get('max_cut_db', 24.0))))
    if gain > 0:
        headroom = float(gs.get('peak_headroom_db', -1.0)) - dsp.peak_db(x)
        gain = min(gain, max(0.0, headroom))
        crest_floor = float(gs.get('crest_preserve_db', 0.0))
        if crest_floor > 0:
            crest = dsp.crest_db(x)
            if crest < crest_floor:
                gain *= crest / crest_floor
        sparse = float(gs.get('sparse_active_frac', 0.0))
        if sparse > 0 and dsp.active_fraction(x, sr, float(gs.get('block_s', 0.4)),
                                              float(gs.get('active_db', _active_db()))) < sparse:
            gain *= 0.5
    return float(gain)


def process_chain(name, x, spec, sr=SR, ctx=None):
    """Everything before placement: gain staging, EQ, dynamics, low-end hygiene, level, automation, fades.

    `spec` is never modified: the send is read by reverb_send_level(). This half is the same for every deliverable
    of a piece, which is why it can be cached across a repeat render and across output formats; `_place` is not
    (a loudspeaker bus hands a track over unplaced, the stereo mix pans it for two speakers).
    """
    if ctx is not None and ctx is not mix_context.current():
        _install(ctx.mix, ctx.space)
    mx = _mix()
    spec = dict(spec or {})
    role = spec.get('role', 'chord')
    x = to_stereo(x)
    if len(x) == 0:
        return x.astype(np.float32)
    gs = mx.get('gain_staging') or {}
    # 1 gain staging
    l = active_lufs(x, sr, block=float(gs.get('block_s', 0.4)), active_db=float(gs.get('active_db', _active_db())))
    g = gain_stage(x, l, role, spec, gs, sr)
    x = x * 10 ** (g / 20.0)
    STATE.setdefault('gain', {})[name] = g
    STATE.setdefault('in_lufs', {})[name] = l

    # 2/3 EQ + dynamics
    dyn = dynamics_cfg(spec, mx)
    chain = []
    source = 'none'
    if spec.get('chain') != 'none':
        schain, source = spectral_chain(role, spec, mx)
        chain += _chain_objects(schain)
    for d in spec.get('eq', []) or []:
        if d.get('order') and d.get('type') in ('hp', 'highpass', 'lp', 'lowpass'):
            x = dsp.slope_filter(x, sr, _band(d)['f'], d['type'], d['order'])
        else:
            chain.append(eq_object(d))
    if 'hp' in spec:
        chain.insert(0, pb.HighpassFilter(spec['hp']))
    if 'lp' in spec:
        chain.append(pb.LowpassFilter(spec['lp']))
    comp = dyn.get('comp')
    if comp is False or comp == 0:
        comp = None
    if isinstance(comp, dict) and str(dyn.get('engine', 'pedalboard')) == 'pedalboard':
        cp = mix_schema.comp_params(comp)
        chain.append(pb.Compressor(threshold_db=cp['thr'], ratio=cp['ratio'],
                                   attack_ms=cp['attack'], release_ms=cp['release']))
    if spec.get('saturation', 0):
        chain.insert(0, pb.Distortion(drive_db=spec['saturation']))
    if chain:
        x = _run(pb.Pedalboard(chain), x, sr)
    STATE.setdefault('chain', {})[name] = source
    if spec.get('dynamics') or str(dyn.get('engine', 'pedalboard')) == 'dsp':
        # the Pedalboard chain above already ran the compressor: running it again here would compress twice
        x = _dsp_dynamics(x, dyn, sr, comp_done=isinstance(comp, dict)
                          and str(dyn.get('engine', 'pedalboard')) == 'pedalboard')

    # 4 low-end hygiene
    if role == 'bass' or spec.get('mono_below'):
        x = mono_below(x, spec.get('mono_below', 120), sr)
    # level (in place: the chain above already made this stem's private copy)
    x *= np.float32(10 ** (float(spec.get('gain_db', 0.0)) / 20.0))
    # macro automation for environment
    if role == 'environment':
        tot_s = len(x) / sr
        swell_db = float(spec.get('intro_outro_boost_db', 0.0))      # off unless the track asks
        t_in_start = float(spec.get('crossfade_start_s', 4.0))
        t_in_end = float(spec.get('crossfade_end_s', 12.0))
        t_out_start = max(t_in_end + 5.0, float(spec.get('outro_start_s', tot_s - 8.0)))
        t_out_end = min(tot_s, float(spec.get('outro_end_s', tot_s - 1.0)))
        if swell_db > 0.0 and tot_s > (t_in_end + 8.0):
            t_axis = np.arange(len(x)) / sr
            mult_curve = np.zeros(len(x), dtype=np.float32)
            mult_curve[t_axis <= t_in_start] = 1.0
            idx_in = (t_axis > t_in_start) & (t_axis < t_in_end)
            if np.any(idx_in):
                th_in = np.pi * (t_axis[idx_in] - t_in_start) / (t_in_end - t_in_start)
                mult_curve[idx_in] = 0.5 * (1.0 + np.cos(th_in))
            idx_out = (t_axis > t_out_start) & (t_axis < t_out_end)
            if np.any(idx_out):
                th_out = np.pi * (t_axis[idx_out] - t_out_start) / (t_out_end - t_out_start)
                mult_curve[idx_out] = 0.5 * (1.0 - np.cos(th_out))
            mult_curve[t_axis >= t_out_end] = 1.0
            x = x * (10.0 ** ((swell_db * mult_curve) / 20.0))[:, None]
    # opt-in per-track fades
    curve = str(((mx.get('automation') or {}).get('curve')) or 'linear')
    for key, rising in (('fade_in_s', True), ('fade_out_s', False)):
        fade_n = min(len(x), int(float(spec.get(key, 0.0)) * sr))
        if fade_n > 1:
            ramp = _curve(np.linspace(0.0, 1.0, fade_n), curve).astype(np.float32)
            if rising:
                x[:fade_n] = x[:fade_n] * ramp[:, None]
            else:
                x[-fade_n:] = x[-fade_n:] * ramp[::-1, None]
    if not np.isfinite(x).all():
        raise ValueError(f'stem "{name}" produced non-finite samples (check its eq/comp/spatial values)')
    return np.asarray(x, dtype=np.float32)      # already float32: astype() copied every stem a second time


def _code_tag():
    """Identity of the code behind a processed stem: an engine edit must never be served an old stem."""
    global _CODE_TAG
    if _CODE_TAG is None:
        import stem_cache
        here = os.path.dirname(os.path.abspath(__file__))
        _CODE_TAG = stem_cache.code_hash(here, files=('mixer.py', 'dsp.py', 'mix_schema.py', 'mix_context.py',
                                                      'presets.py', 'spatial.py', 'airabs.py', 'spatial_hrtf/room.py',
                                                      'spatial_hrtf/binaural.py'),
                                         packages=('spatial_engine', 'mix_engine'))
    return _CODE_TAG


def _chain_key(name, x, spec, mx, sr, n):
    """What `process_chain` reads: this stem's bytes, its resolved staging/EQ/dynamics spec, the whole mix preset,
    the sample rate and the engine. Placement is deliberately absent: it belongs to the bus, not to the chain."""
    import compute
    import stem_cache
    return stem_cache.digest(dict(version=MIX_CACHE_VERSION, cache=stem_cache.CACHE_VERSION, stem=name,
                                  audio=stem_cache.audio_hash(x, size=16, stride=1), spec=stem_cache.jsonable(spec),
                                  mix=stem_cache.jsonable(mx), sr=int(sr), frames=int(n),
                                  compute=compute.cache_tag(), code=_code_tag()), size=16)


def _cache_files(cache, key, name):
    d = os.path.join(cache, key)
    return os.path.join(d, f'{name}.npy'), os.path.join(d, f'{name}.json')


def _cache_get(cache, key, name, n):
    """The chain's output for this stem, or None. A missing, stale or malformed entry is a miss, never an error."""
    if not (cache and key):
        return None
    arr, meta = _cache_files(cache, key, name)
    if not (os.path.isfile(arr) and os.path.isfile(meta)):
        return None
    try:
        y = np.load(arr)
        with open(meta, encoding='utf-8') as fh:
            m = json.load(fh)
    except (OSError, ValueError):
        return None
    if m.get('version') != MIX_CACHE_VERSION or y.dtype != np.float32 or y.shape != (int(n), 2):
        return None
    for k in ('gain', 'in_lufs', 'chain'):          # the chain's own report, so a hit reads like a fresh run
        if k in (m.get('state') or {}):
            STATE.setdefault(k, {})[name] = m['state'][k]
    return np.ascontiguousarray(y)


def _cache_put(cache, key, name, x, n):
    """Keep one processed stem. Caching is an optimization: a full disk or a read-only project is not a failure."""
    if not (cache and key):
        return
    arr, meta = _cache_files(cache, key, name)
    try:
        os.makedirs(os.path.dirname(arr), exist_ok=True)
        tmp = arr + f'.tmp{os.getpid()}'
        np.save(tmp, np.ascontiguousarray(x, dtype=np.float32))
        os.replace(tmp if tmp.endswith('.npy') else tmp + '.npy', arr)
        with open(meta, 'w', encoding='utf-8') as fh:
            json.dump(dict(version=MIX_CACHE_VERSION,
                           state={k: STATE.get(k, {}).get(name) for k in ('gain', 'in_lufs', 'chain')}), fh)
    except (OSError, ValueError):
        pass


def use_mix_cache(path):
    """Where processed stems are kept between runs; None disables it. A stem is reused only when every input
    that can change its bytes is identical (see `_chain_key`), so a cache can never hand back another mix's audio."""
    STATE['cache_dir'] = str(path) if path else None
