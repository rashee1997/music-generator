"""mastering - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

import dsp
import mix_context
import mix_engine.meters as meters
import mix_schema
import numpy as np
import pedalboard as pb
import sys
from .core import SR, STATE, _install, _mix
from .dsp_utils import _run, eq_object, lufs, mono_below, to_stereo, true_peak_db, width_ms


def _master_cfg(m, mx):
    """The master block: the chosen profile, the shipped defaults, then the score's own values."""
    mm = mix_schema.section(mx, 'mastering')
    profiles = mm.get('profiles') or {}
    name = m.get('profile') or mm.get('profile') or 'default'
    base = dict(profiles.get(name) or profiles.get('default') or {})
    out = dict(base)
    out.update({k: v for k, v in (m or {}).items() if k in ('lufs', 'true_peak', 'tone', 'glue', 'width',
                                                            'mono_below', 'fade_out', 'loop')})
    out['_profile'] = name
    out['_profiles'] = profiles
    out['_cfg'] = mm
    return out


def master_measures(x, sr=SR):
    """What the delivery report needs: loudness, LRA, crest, true peak at 4x and 8x, PLR/PSR, mono bands.

    Owned by `mix_engine.meters` (one implementation of each definition); this name stays because every
    caller and the gate import it from the mixer.
    """
    return meters.master_measures(to_stereo(x), sr)


def master_chain(x, m, sr=SR, ctx=None):
    """Glue + tone + limiter + loudness. m: {"lufs":-14,"true_peak":-1.5,"tone":"neutral","glue":true}."""
    if ctx is not None and ctx is not mix_context.current():
        _install(ctx.mix, ctx.space)
    cfg = _master_cfg(m, _mix())
    target = float(cfg.get('lufs', -14.0))
    ceiling = float(cfg.get('true_peak', -1.5))
    tone = cfg.get('tone', 'neutral')
    mm = cfg['_cfg']
    # Pedalboard's high-pass is first order (6 dB/octave); `highpass_order` cascades it, so a sub band the master should
    # not carry can be cut harder without a second filter family. 1 is the filter every older master was made with.
    chain = ([pb.HighpassFilter(float(mm['highpass_hz'])) for _ in range(max(1, int(mm.get('highpass_order') or 1)))]
             if float(mm.get('highpass_hz') or 0.0) > 0.0 else [])
    tones = mm.get('tones') or {}
    if tone not in tones:
        # An unlisted tone has always mastered flat without a word. It still masters flat (an older score keeps
        # its sound), but it says so: a tone name that does nothing is a decision nobody made.
        sys.stderr.write(f'[master] tone "{tone}" is not in mastering.tones ({", ".join(sorted(tones))}): '
                         f'mastered neutral. Add it to the mix preset to give it a curve.\n')
        tone = 'neutral'
    chain += [eq_object(band) for band in tones.get(tone) or []]
    glue = mm.get('glue') or {}
    if cfg.get('glue', True) and glue:
        chain.append(pb.Compressor(threshold_db=float(glue['threshold_db']), ratio=float(glue['ratio']),
                                   attack_ms=float(glue['attack_ms']), release_ms=float(glue['release_ms'])))
    if cfg.get('width'):
        x = width_ms(x, cfg['width'])
    x = _run(pb.Pedalboard(chain), x, sr)
    if cfg.get('mono_below'):
        x = mono_below(x, cfg['mono_below'], sr)
    try:
        lim = pb.Pedalboard([pb.BrickwallLimiter(ceiling_db=ceiling, true_peak=True)])
    except Exception:
        fb = mm.get('fallback_limiter') or {}
        lim = pb.Pedalboard([pb.Limiter(threshold_db=ceiling - float(fb['margin_db']), release_ms=float(fb['release_ms']))])
    crest_floor = float(mm.get('crest_floor_db', 0.0))
    conv = mm.get('converge') or {}
    if int(conv['max_iterations']) < 1:
        raise ValueError('mastering.converge.max_iterations must be at least 1: with none, the limiter never runs')
    in_lufs = lufs(x, sr)
    if in_lufs <= -69.9:               # silence reads -70: a gain of target + 70 dB would only amplify the noise floor
        sys.stderr.write('[master] the programme is silent (-70 LUFS); no gain applied to reach the target.\n')
        gain_db = 0.0
    else:
        gain_db = target - in_lufs
    y = x
    for _ in range(int(conv['max_iterations'])):                                               # converge on loudness with the limiter in the loop
        y = _run(lim, x * 10 ** (gain_db / 20.0), sr)
        err = target - lufs(y, sr)
        if abs(err) < float(conv['tolerance_lu']):
            break
        if crest_floor > 0 and dsp.crest_db(y) < crest_floor:
            sys.stderr.write(f'[master] a {target} LUFS target would take the crest under {crest_floor} dB '
                             f'(at {dsp.crest_db(y):.1f} dB); stopping. Raise the headroom or lower the target.\n')
            break
        gain_db += err * float(conv['step'])   # damped step: >1.0 on a saturating limiter is an over-relaxed fixed point
    reached = lufs(y, sr)
    if abs(target - reached) > float(conv['report_miss_lu']):
        sys.stderr.write(f'[master] reached {reached:.1f} LUFS, not {target}: the music is too dynamic for that target under a '
                         f'{ceiling} dBTP ceiling without squashing it. Kept natural dynamics; lower the target or accept it.\n')
    tp = true_peak_db(y, sr)
    if tp > ceiling:                       # last safety: oversampled true peak
        y = y * 10 ** ((ceiling - tp) / 20.0)
        reached = lufs(y, sr)              # the trim moves the whole track: report what was actually delivered
    y = np.asarray(y, dtype=np.float32)
    STATE['master'] = dict(master_measures(y, sr), target=target, ceiling=ceiling, profile=cfg.get('_profile'),
                           reached=reached,
                           limited_by_ceiling=bool(tp > ceiling))
    return y


def suggest_master_target(x, sr=SR, lufs_target=-14.0, ceiling=-1.5):
    """Can this material reach the target without destroying it? Returns (feasible, why)."""
    min_crest = float(mix_schema.section(_mix(), 'mastering')['min_crest_db'])
    m = master_measures(x, sr)
    crest = m['crest']
    needed = lufs_target - m['lufs']
    ceiling_room = ceiling - m['true_peak']
    if needed <= 0:
        return True, f'already at {m["lufs"]:.1f} LUFS; the target needs no gain'
    if crest - needed < min_crest:
        return False, (f'crest factor is {crest:.1f} dB; reaching {lufs_target} LUFS needs {needed:+.1f} dB, '
                       f'which would leave {crest - needed:.1f} dB of crest, below the {min_crest:g} dB this mix preset treats as music')
    if ceiling_room < needed - 0.5:
        return False, (f'{needed:+.1f} dB of gain against {ceiling_room:.1f} dB to the {ceiling} dBTP ceiling: '
                       f'the limiter would have to hold transients down for the whole piece')
    return True, f'{needed:+.1f} dB of gain, {crest:.1f} dB crest, {ceiling_room:.1f} dB to the ceiling'
