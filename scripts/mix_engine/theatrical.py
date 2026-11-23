"""theatrical - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

from scipy import signal
import dsp
import mix_schema
import numpy as np
from .core import SR, _space, use_mix
from .dsp_utils import to_stereo, widen
from .placement import _imm, _use_head_set


def theatrical_send_gain(dry, sr=SR, cfg=None):
    """How much of the room send survives each instant: less while the direct sound is attacking.

    A hall heard from the audience is not a wash: the attack of a bow, a felt hammer or a stick reaches the ear
    before the room answers, so the direct sound leads the early reflections and the tail. That is a
    direct-to-reverberant ratio that changes *within* a note. The stem's reverb send is static, so this measures
    the front of each event (fast envelope over slow envelope) and dips the send by at most `duck_db` there.
    It is the detail-vs-depth control, not a de-verb: a sustained body keeps its send.

    `cfg` is the mix preset's `theatrical` section. Returns one gain per sample.
    """
    th = cfg if isinstance(cfg, dict) else {}
    d = dict(mix_schema.DEFAULTS['theatrical']['detail'], **(th.get('detail') or {}))
    if not d.get('enabled', True) or float(d.get('duck_db', 0.0)) <= 0.0:
        return np.ones(len(dry), np.float32)
    fast = dsp.envelope(dry, sr, max(1.0, float(d.get('attack_ms', 4.0))),
                        max(2.0, float(d.get('release_ms', 40.0))))
    slow = dsp.envelope(dry, sr, 60.0, 240.0)
    ref = max(3.0, float(d.get('ref_db', 18.0)))
    front = np.clip(20.0 * np.log10((fast + 1e-12) / (slow + 1e-12)) / ref, 0.0, 1.0)
    return (10.0 ** (-float(d.get('duck_db', 2.5)) * front / 20.0)).astype(np.float32)


def _theatrical_low_mid(y, sr, cfg):
    """The 180-420 Hz dynamic lean, linked across the channels it is given."""
    lm = dict(mix_schema.DEFAULTS['theatrical']['low_mid'], **(cfg.get('low_mid') or {}))
    if not lm.get('enabled', True) or float(lm.get('max_dip_db', 0.0)) <= 0.0:
        return y
    lo = max(40.0, float(lm.get('low_hz', 180.0)))
    hi = min(sr * 0.45, float(lm.get('high_hz', 420.0)))
    if hi <= lo:
        return y
    f = 0.5 * (lo + hi)
    q = f / (hi - lo)
    # A threshold in dBFS is wrong here: this stage runs before the master, so the same programme can sit at any
    # level. The band's own loud level (95th percentile of its sounding frames) minus `range_db` is the threshold,
    # so the lean follows the density of the piece rather than its pre-master gain.
    band = signal.sosfilt(signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos'), y, axis=0)
    lvl = 20.0 * np.log10(dsp.envelope(band, sr, 50.0, 200.0) + 1e-12)
    sounding = lvl[lvl > float(lvl.max()) - 45.0]
    threshold = float(np.percentile(sounding, 95.0)) - float(lm.get('range_db', 6.0)) if sounding.size else -30.0
    # a maximum dip at 6 dB over threshold becomes the ratio that produces it
    ceiling = 1.0 / (1.0 - float(np.clip(float(lm.get('max_dip_db', 2.0)) / 6.0, 0.0, 0.9)))
    ratio = max(1.0, min(float(lm.get('ratio', 2.0)), ceiling))
    return dsp.dynamic_eq(y, sr, f=f, q=q, threshold_db=threshold,
                          ratio=ratio, attack_ms=float(lm.get('attack_ms', 20.0)),
                          release_ms=float(lm.get('release_ms', 180.0)),
                          knee_db=float(lm.get('knee_db', 6.0)), gain_db=0.0)


def _theatrical_air_curve(y, sr, cfg):
    """One gain curve for the air shelf, from the piece's own loud end (None = no lift)."""
    air = dict(mix_schema.DEFAULTS['theatrical']['air'], **(cfg.get('air') or {}))
    if not air.get('enabled', True) or float(air.get('max_lift_db', 0.0)) <= 0.0:
        return None
    env = dsp.envelope(y, sr, 60.0, 240.0)
    edb = 20.0 * np.log10(env + 1e-12)
    sounding = edb[edb > float(edb.max()) - 50.0]
    if sounding.size < 8:
        return None
    ref = float(np.percentile(sounding, 95.0))
    span = max(1.0, float(air.get('window_db', 6.0)))
    lift = float(air['max_lift_db']) * np.clip((edb - (ref - span)) / span, 0.0, 1.0)
    return (10.0 ** (lift / 20.0)).astype(np.float32), float(air.get('hz', 9000.0))


def _apply_theatrical_air(y, curve, sr):
    if curve is None:
        return y
    gain, hz = curve
    hz = min(sr * 0.45, hz)
    hf = signal.sosfilt(signal.butter(2, hz, btype='high', fs=sr, output='sos'), y, axis=0).astype(np.float32)
    return (y + hf * (gain - 1.0)[:, None]).astype(np.float32)


def theatrical_tone(x, sr=SR, cfg=None):
    """The programme-side half of the theatrical stage: lean low-mids and air that survives a dense peak.

    `low_mid` compresses only 180-420 Hz when that band is loud, so many heavy layers cannot thicken the region
    where the ear localises weight and loses the sub. `air` lifts the top octave near the piece's own loud end,
    capped at `max_lift_db` and faded out `window_db` below it: at a quiet moment there is nothing to restore, at
    a dense peak the field does not fold inward and lose its upper air. Both are starting values, not
    measurements of a room.

    `cfg` is the mix preset's `theatrical` section. A multichannel bus is left to its own master.
    """
    c = cfg if isinstance(cfg, dict) else {}
    y = to_stereo(x).astype(np.float32)
    y = _theatrical_low_mid(y, sr, c)
    return _apply_theatrical_air(y, _theatrical_air_curve(y, sr, c), sr).astype(np.float32)


def theatrical_multichannel(x, sr=SR, cfg=None, skip=()):
    """The same stage for a discrete deliverable: every full-range channel, LFE left alone.

    The low-mid compressor is linked across the full-range channels and the air shelf follows one programme
    curve, so a dense peak cannot move the front image; the LFE keeps its band because a 180-420 Hz lean and a
    9 kHz shelf are not bass-management decisions. `skip` is a set of channel indices to leave untouched.
    """
    c = cfg if isinstance(cfg, dict) else {}
    y = dsp.to_2d(x).astype(np.float32)
    skip = {int(i) for i in (skip or ())}
    idx = [i for i in range(y.shape[1]) if i not in skip]
    if not idx:
        return y
    main = y[:, idx]
    main = _theatrical_low_mid(main, sr, c)
    main = _apply_theatrical_air(main, _theatrical_air_curve(main, sr, c), sr)
    y[:, idx] = main
    return y.astype(np.float32)


def sympathetic_bed(score, processed, specs, mx, sr=SR):
    """The stereo bed of the mix preset's `sympathetic_resonance` block, or None when it is off or has nothing to
    ring with. One fixed tuning for the piece, so nothing is retuned or crossfaded while it plays."""
    cfg = mx.get('sympathetic_resonance') or {}
    if not cfg.get('enabled'):
        return None
    want = set(cfg.get('sources') or [])
    names = [k for k, sp in specs.items() if k in processed and (
        (k in want or sp.get('role') in want) if want else sp.get('role') not in ('drum', 'percussion', 'environment'))]
    if not names:
        return None
    tuning = cfg.get('tuning', 'score_scale')
    if tuning == 'score_scale':
        import cli_util
        weight = np.zeros(12)
        for tr in score.get('tracks', []):
            if tr.get('name') in names:
                for nt in tr.get('notes', []):
                    try:
                        weight[cli_util.midi_int(nt['p']) % 12] += float(nt.get('d', 1.0))
                    except (ValueError, KeyError, TypeError):
                        continue                  # a drum key or an effect hit has no pitch class
        base = 69.0 + 12.0 * np.log2(float(cfg['low_hz']) / 440.0)
        pcs = [int(i) for i in np.argsort(-weight, kind='stable')[:int(cfg['strings'])] if weight[i] > 0]
        freqs = [440.0 * 2.0 ** ((np.ceil((base - pc) / 12.0) * 12.0 + pc - 69.0) / 12.0) for pc in pcs]
    elif isinstance(tuning, (list, tuple)):
        freqs = [float(f) for f in tuning]
    else:
        raise ValueError(f'sympathetic_resonance.tuning must be "score_scale" or a list of Hz (got {tuning!r})')
    freqs = [f * h for f in freqs for h in range(1, int(cfg['partials']) + 1)]
    src = np.sum([to_stereo(processed[k]) for k in names], axis=0).mean(axis=1)
    y = dsp.resonator_bank(src, sr, freqs, float(cfg['q']))
    ref, got = float(np.sqrt(np.mean(src ** 2))), float(np.sqrt(np.mean(y ** 2)))
    if ref <= 0 or got <= 0:
        return None
    y = (y * (ref / got) * 10.0 ** (float(cfg['level_db']) / 20.0)).astype(np.float32)
    return widen(to_stereo(y), amount=float(cfg['width']), sr=sr)


def _hoa_bus(score, bus, sr):
    """(the bus that places the tracks or None, the bus to sum into). With immersive on, a bus that places tracks
    itself (ambisonic, loudspeaker layout, ADM objects) is handed every track unplaced; a stereo or headphone mix
    on the ambisonic engine gets an ambisonic bus of its own; a loudspeaker bus keeps its own panning for the direct
    sound and is given the room through one."""
    imm = _imm()
    if not imm:
        return None, bus
    on_hoa = str(imm.get('engine', 'per_stem')) == 'hoa_bus'
    if not on_hoa and not getattr(bus, 'places_tracks', False):
        return None, bus
    from spatial_hrtf import binaural as _hrtf
    from spatial_engine import hoa
    kw = dict(sr=sr, order=int(imm.get('order', 5)), imm=imm, space=_space(), score=score)
    if getattr(bus, 'places_tracks', False):
        if hasattr(bus, 'attach_room'):                   # a loudspeaker layout
            bus.imm, bus.score = imm, score
            if on_hoa:
                bus.attach_room(hoa.HoaBus(decode='speakers', speakers=bus.speakers, room_only=True, **kw))
        return bus, bus
    if bus is None:
        if not _hrtf.available():
            print('  [spatial] "engine": "hoa_bus" needs the head data: run `python -m spatial_hrtf.data` from '
                  'scripts/. Using the per-stem engine.')
            return None, None
        if str(imm.get('stereo_decode', 'binaural')) == 'speakers':
            from spatial_engine import config as _cfg
            made = hoa.HoaBus(decode='speakers', speakers=_cfg.speakers(imm.get('stereo_layout', 'stereo_bs775')), **kw)
            return made, made
        _use_head_set(imm)
        made = hoa.HoaBus(decode='binaural', **kw)
        return made, made
    return None, bus


def immersive_cfg(score):
    """The immersive block that mixing this score would use (None when off). The gates call this."""
    use_mix(score.get('mix_preset'))
    return _imm()
