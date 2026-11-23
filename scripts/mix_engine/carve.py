"""carve - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

from scipy import signal
import dsp
import mix_engine.masking as masking
import mix_schema
import numpy as np
import roles as rolelib
from .core import DEFAULT_CARVE_DB, DEFAULT_LEAD_BAND_HZ, SR, STATE, _mix
from .dsp_utils import _band_center_q, to_stereo


def carve_for_lead(specs, mx=None):
    """Mix rule: when a melody leads, every bed that shares its band (pads, chords, arps, counter lines,
    chorus, environment) gets a small dip at the lead band, so the lead cuts through. A dip the user set is
    kept. The dip never exceeds spectral.max_auto_cut_db."""
    mx = mx or _mix()
    band = float(mx.get('lead_band_hz', DEFAULT_LEAD_BAND_HZ))
    carve = float(mx.get('carve_db', DEFAULT_CARVE_DB))
    limit = float((mx.get('spectral') or {}).get('max_auto_cut_db', 3.0))
    if not any(rolelib.is_lead(s.get('role')) for s in specs.values()):
        return specs
    for name, sp in specs.items():
        if sp.get('role') in ('pad', 'texture', 'drone', 'chord', 'arp', 'ostinato', 'counter', 'environment'):
            eq = sp.setdefault('eq', [])
            if not any(d.get('type') == 'peak' and abs(d.get('f', 0) - band) < 1 for d in eq):
                depth = carve - 1.5 if sp.get('role') == 'environment' else carve
                depth = max(depth, -abs(limit)) if limit > 0 else depth
                eq.append(dict(type='peak', f=band, gain=depth, q=1.0))
    return specs


def apply_lead_carve(processed, specs, mx=None, sr=SR, intent=None):
    """Carve the beds only while the lead is actually sounding in the band they share.

    carve_for_lead() is a decision taken from the score: one fixed dip, for the whole piece, in one band, whether
    or not the lead is there (which is why it can only be small). This is the same rule driven by the lead's own
    signal: each band of each bed is keyed by the band-passed lead, so a bed keeps its body while the lead rests
    and yields only where the two actually collide. Roles the sidechain already ducks under the same source are
    skipped, so nothing is moved twice.

    With `lead_carve.from_intent` on, the direction sheet's `mix_intent` (carried on the score) decides what is
    carved for: `hero` names the track the beds yield to and `leave_free_hz` is the band they yield in. Until this
    existed those two fields were words for the listening pass only; nothing in the mix read them.

    Mutates and returns `processed` (the same dict STATE['processed'] points at).
    """
    mx = mx or _mix()
    cfg = dict(mx.get('lead_carve') or {})
    if not cfg.get('enabled'):
        return processed
    used = {}
    if cfg.get('from_intent') and isinstance(intent, dict):
        hero = intent.get('hero')
        if isinstance(hero, str) and hero in specs:
            cfg['source'] = used['hero'] = hero
        free = intent.get('leave_free_hz')
        if isinstance(free, (list, tuple)) and len(free) == 2 and float(free[1]) > float(free[0]) > 0.0:
            cfg['bands_hz'] = [[float(free[0]), float(free[1])]]
            used['leave_free_hz'] = cfg['bands_hz'][0]
    STATE['mix_intent_used'] = used
    if cfg.get('source'):
        lead = str(cfg['source'])
    else:
        leads = [n for n, sp in specs.items() if rolelib.is_lead(sp.get('role'))]
        if not leads:
            return processed                              # no lead, nothing to make room for
        lead = max(leads, key=lambda n: float(specs[n].get('gain_db', 0.0)))
    if lead not in processed or lead not in specs:
        return processed
    src = to_stereo(processed[lead])
    roles = tuple(cfg.get('roles') or mix_schema.section(mx, 'sidechain')['band_roles'])
    ratio = max(1.0, float(cfg.get('ratio', 2.0)))
    thr = float(cfg.get('threshold_db', -30.0))
    att = float(cfg.get('attack_ms', 6.0))
    rel = float(cfg.get('release_ms', 120.0))
    bands = [list(p) for p in (cfg.get('bands_hz') or [])]
    if str(cfg.get('mode') or 'bands').lower() == 'masking':
        # opt-in: measure where the beds actually sit over the figure, and carve those bands only. The
        # measurement is a band-level proxy (mix_engine.masking); the cap keeps one bad estimate from
        # turning into a hole.
        import mix_engine.masking as masking
        beds_sig = None
        for nm, sp in specs.items():
            if nm == lead or sp.get('role') not in roles or nm not in processed:
                continue
            if cfg.get('skip_ducked', True) and sp.get('duck_by'):
                continue
            y = to_stereo(processed[nm])
            if beds_sig is None:
                beds_sig = y.copy()
            else:
                m = max(len(beds_sig), len(y))
                beds_sig = (np.pad(beds_sig, ((0, m - len(beds_sig)), (0, 0)))
                            + np.pad(y, ((0, m - len(y)), (0, 0))))
        if beds_sig is not None:
            excess = masking.band_excess_db(src, beds_sig, sr)
            floor = float(cfg.get('mask_floor_db', 0.0))
            picked = [r for r in excess if np.isfinite(r['excess_db']) and r['excess_db'] > floor]
            picked.sort(key=lambda r: r['excess_db'], reverse=True)
            bands = [[float(r['band_hz'][0]), float(r['band_hz'][1])]
                     for r in picked[:max(1, int(cfg.get('max_bands', 3)))]]
    for pair in bands:
        lo, hi = float(pair[0]), float(pair[1])
        f, q = _band_center_q(lo, hi)
        sos = signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos')
        sc = signal.sosfiltfilt(sos, src.mean(axis=1)).astype(np.float32)
        for name, sp in specs.items():
            if name == lead or sp.get('role') not in roles or name not in processed:
                continue
            if cfg.get('skip_ducked', True) and sp.get('duck_by'):
                continue
            # gain_db stays 0: the band is only reduced while the sidechain is over threshold, so a bed
            # keeps its body in the rests and yields only where the lead is actually there.
            processed[name] = dsp.dynamic_eq(
                to_stereo(processed[name]), sr, f=f, q=q, threshold_db=thr, ratio=ratio,
                attack_ms=att, release_ms=rel, sidechain=sc)
    return processed
