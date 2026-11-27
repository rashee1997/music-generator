"""bus - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

from scipy import signal
import argparse
import compute
import json
import mix_schema
import numpy as np
import os
import resources
import soundfile as sf
import sys
from .core import SR, STATE, _context_for, _mix, _space, _space_owned, _space_owned_hook, release_stems
from .dsp_utils import _validate_export, _workers_that_fit, apply_mid_side, duck_gain, fades, finalize_pcm, fit, lufs, reverb_bus, reverb_send_level, trim_tail, true_peak_db, wrap_loop
from .chains import _cache_get, _cache_put, _chain_key, process_chain
from .placement import _place, default_spec, guess_role
from .theatrical import _hoa_bus, sympathetic_bed, theatrical_send_gain, theatrical_tone
from .mastering import _master_cfg, master_chain
from .carve import apply_lead_carve, carve_for_lead


def process_stem(name, x, spec, sr=SR, ctx=None):
    """One stem through the chain and then placed for this mix's bus."""
    x = process_chain(name, x, spec, sr, ctx)
    if x.size == 0:
        return x
    x = _place(name, x, spec, _mix(), sr)
    if not np.isfinite(x).all():
        raise ValueError(f'stem "{name}" produced non-finite samples (check its eq/comp/spatial values)')
    return np.asarray(x, dtype=np.float32)


def _biome_sources(name, placed, stem, spec, sr):
    """The separate emitters of a biome environment track for a bus that places sources, or None for any other track."""
    from biome import spatial as biome_spatial
    if not biome_spatial.is_registered(name):
        return None
    return biome_spatial.bus_sources(name, placed, stem, spec, sr)


def mix_stems(score, stems, sr=SR, ctx=None, bus=None):
    """Return the pre-master mix (float32).

    `bus` is an object with add(name, signal, spec), add_reverb(signal) and result(); when it is given, every
    finished track signal and the shared reverb return are handed to it instead of being summed to stereo, and its
    result is returned. That is the seam the discrete multichannel renderer uses: every mixing decision stays here,
    and only the summing target changes.
    """
    if not stems:
        raise ValueError('mix_stems needs at least one stem')
    ctx = _context_for(score, ctx)
    mx = _mix()
    space_name = ctx.space_name or score.get('space') or score.get('room', 'hall')
    n = max(len(v) for v in stems.values())
    specs = {}
    for i, tr in enumerate(score.get('tracks', [])):
        specs[tr.get('name', f'track{i}')] = default_spec(tr)
    for name in stems:                                  # stems with no spec: guess the role
        if name not in specs:
            specs[name] = default_spec(dict(role=guess_role(name)))
    for k, v in (score.get('mix', {}).get('tracks', {}) or {}).items():
        if k in specs:
            specs[k].update(v)

    # Shared acoustic space: when environmental layers are present, acoustic instruments send a little
    # more into the shared room so music and nature are not two unrelated recordings. Preset-gated.
    blend = mix_schema.section(mx, 'space').get('auto_env_blend') or {}
    has_env = any(specs[name].get('role') == 'environment' for name in stems)
    if has_env and blend.get('enabled', True):
        floors = {role: (float(v[0]), str(v[1])) for role, v in (blend.get('floors') or {}).items()}
        for name, sp in specs.items():
            rule = floors.get(sp.get('role'))
            if not rule:
                continue
            floor, key = rule
            if float(sp.get('reverb', 0.0)) < floor:
                sp['reverb'] = float(blend.get(key, floor))

    # Sidechain routing. "legacy" auto-ducks a bed under the first drum track (the behaviour this engine
    # shipped with); "explicit" only ducks what a track asks for; "off" ducks nothing.
    sc_mode = str(((mx.get('sidechain') or {}).get('mode')) or 'legacy').lower()
    drum_track = next((name for name, sp in specs.items() if sp.get('role') == 'drum'), None)
    if sc_mode == 'legacy' and drum_track:
        for name, sp in specs.items():
            if sp.get('role') == 'environment' and not sp.get('duck_by'):
                sp['duck_by'] = drum_track
                sp['duck_db'] = float(sp.get('duck_db', mix_schema.section(mx, 'sidechain')['legacy_env_duck_db']))
    if sc_mode == 'off':
        for sp in specs.values():
            sp.pop('duck_by', None)

    carve_for_lead(specs, mx)                           # the mix rule: beds make room for the lead
    dry = np.zeros((n, 2), np.float32)
    send = np.zeros((n, 2), np.float32)
    processed = {}
    own_bus, bus = _hoa_bus(score, bus, sr)
    STATE['hoa'] = own_bus is not None                  # _place leaves these tracks for the bus to place
    STATE['unplaced'] = bool(getattr(bus, 'unplaced', False)) and own_bus is None   # an immersive bus has its own hand-over
    rcfg = mix_schema.section(mx, 'render')
    import compute
    comp = rcfg.get('compute') or {}
    want = (str(comp.get('device') or 'auto').lower(), comp.get('workers'))
    if STATE.get('compute_request') != want:               # resolve once per setting, not once per mix
        compute.configure(*want)
        STATE['compute_request'] = want
    STATE['compute'] = compute.info()
    workers = rcfg.get('mix_workers', 1)
    workers = (os.cpu_count() or 1) if workers == 'auto' else max(1, int(workers))
    workers = _workers_that_fit(workers, n, sr, rcfg)
    cache = STATE.get('cache_dir')
    keys = {}
    if cache:
        try:
            keys = {nm: _chain_key(nm, v, specs[nm], mx, sr, n) for nm, v in stems.items()}
        except Exception as exc:                  # a cache that cannot be keyed is no cache, never a failed render
            print(f'  [mix] processed-stem cache off for this run ({exc})')
            keys = {}

    def _work(item):
        """One stem: its chain (reused when nothing it reads changed), then its place on this mix's bus.

        The chain is cached and placement is not, so a second format reuses the first one's EQ and dynamics and
        only re-places the stems, and a repeat render after one note fix re-runs only the stems that changed.
        """
        nm, v = item
        _context_for(score, ctx)                  # the context is per thread: this one reads the piece's own
        got = _cache_get(cache, keys.get(nm), nm, n) if keys else None
        hit = got is not None
        x = got if hit else process_chain(nm, v, specs[nm], sr, ctx)
        if not hit and x.size:
            _cache_put(cache, keys.get(nm), nm, x, n)   # before placement: the cache holds the dry chain output,
        y = fit(_place(nm, x, specs[nm], mx, sr), n) if x.size else fit(x, n)   # and _place may work in place
        return nm, y, hit

    try:
        if workers > 1 and len(stems) > 1:
            # One stem per thread. The plugins and the filters release the interpreter lock, the context is
            # per-thread (the worker installs the piece's own), and every stem writes only its own entries in
            # STATE, so the result is the same samples as the serial loop, in the same order.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(workers, len(stems))) as pool:
                done = list(pool.map(_work, stems.items()))
        else:
            done = [_work(item) for item in stems.items()]
    finally:
        STATE['hoa'] = False
        STATE['unplaced'] = False
    for nm, y, _hit in done:
        processed[nm] = y
    import resources
    resources.release_memory()                  # the stem chains ran on several threads: their freed 64-bit temporaries are still held by the heap
    STATE['cache'] = dict(dir=cache, hits=sum(1 for _n, _y, h in done if h), stems=len(done))
    apply_lead_carve(processed, specs, mx, sr, intent=score.get('mix_intent'))  # the dynamic half of the lead rule, keyed by the lead itself
    STATE['processed'] = processed              # what the mix actually plays: the gate measures this
    STATE['specs'] = specs

    # the musical body (first to last note that is not an environment layer)
    bpm = float(score.get('bpm', 90.0))
    beat_dur = 60.0 / bpm
    first_note_s, last_note_s = None, None
    for tr in score.get('tracks', []):
        if tr.get('role') == 'environment' or str(tr.get('instrument', '')).startswith('env:'):
            continue
        for note in tr.get('notes', []):
            t0 = float(note['t']) * beat_dur
            t1 = (float(note['t']) + float(note.get('d', 0.0))) * beat_dur
            if first_note_s is None or t0 < first_note_s:
                first_note_s = t0
            if last_note_s is None or t1 > last_note_s:
                last_note_s = t1

    sc = mix_schema.section(mx, 'sidechain')
    band = tuple(float(v) for v in sc['band_hz'])
    residual = float(sc['residual'])
    timing = sc['timing']
    for name, sp in specs.items():
        src = sp.get('duck_by')
        if not src or src not in processed:
            continue
        is_env = (sp.get('role') == 'environment')
        base = timing['environment'] if is_env else timing['default']
        rel_ms = float(sp.get('release_ms', (sc.get('release_ms') or {}).get(sp.get('role'), base['release_ms'])))
        att_ms = float(sp.get('attack_ms', (sc.get('attack_ms') or {}).get(sp.get('role'), base['attack_ms'])))
        smooth_s = float(sp.get('smooth_s', base['smooth_s']))
        d_gain = duck_gain(processed[src], n, sp.get('duck_db', float(sc['default_duck_db'])), float(sc['threshold']),
                           attack_ms=att_ms, release_ms=rel_ms,
                           lookahead_ms=float(sc['lookahead_ms']), smooth_s=smooth_s, sr=sr)
        if is_env and sc.get('env_plateau', True) and first_note_s is not None and last_note_s is not None \
                and last_note_s > first_note_s:
            # Lock a bed to a steady plateau across the musical body: it should not swell during a
            # two-second instrumental pause mid-piece.
            i_body_start = int(first_note_s * sr)
            i_body_end = min(n, int(last_note_s * sr))
            if i_body_end > i_body_start:
                min_floor = 10.0 ** (float(sp.get('duck_db', float(sc['default_duck_db']))) / 20.0)
                plateau_gain = float(np.percentile(d_gain[i_body_start:i_body_end], float(sc['plateau_percentile'])))
                plateau_gain = max(min_floor, min(plateau_gain, 1.0))
                fade_s = min(float(sc['plateau_fade_max_s']), (last_note_s - first_note_s) * float(sc['plateau_fade_frac']))
                n_fade = int(fade_s * sr)
                if n_fade > 0 and 2 * n_fade < (i_body_end - i_body_start):
                    t = np.linspace(0.0, np.pi, n_fade, dtype=np.float32)
                    cf_in = 0.5 * (1.0 + np.cos(t))
                    cf_out = 0.5 * (1.0 - np.cos(t))
                    d_gain[i_body_start:i_body_start + n_fade] = (
                        d_gain[i_body_start:i_body_start + n_fade] * cf_in + plateau_gain * cf_out)
                    d_gain[i_body_start + n_fade:i_body_end - n_fade] = plateau_gain
                    d_gain[i_body_end - n_fade:i_body_end] = (
                        plateau_gain * cf_in + d_gain[i_body_end - n_fade:i_body_end] * cf_out)
                elif n_fade > 0 and (i_body_start + n_fade) < i_body_end:
                    t = np.linspace(0.0, np.pi, n_fade, dtype=np.float32)
                    cf_in = 0.5 * (1.0 + np.cos(t))
                    cf_out = 0.5 * (1.0 - np.cos(t))
                    d_gain[i_body_start:i_body_start + n_fade] = (
                        d_gain[i_body_start:i_body_start + n_fade] * cf_in + plateau_gain * cf_out)
                    d_gain[i_body_start + n_fade:i_body_end] = plateau_gain
        if sp.get('role') in sc['band_roles'] and not sp.get('duck_full_band'):
            # only the band the lead lives in takes the whole duck; the rest follows at `residual` of it.
            # mid*d + (x - mid)*d**residual == x*res + mid*(d - res), written in place: the placed stem becomes
            # the result, so a ducked track costs two full-length curves instead of four temporaries plus an output.
            x_ = processed[name]
            sos_b = signal.butter(2, [band[0], band[1]], btype='band', fs=sr, output='sos')
            mid = signal.sosfiltfilt(sos_b, x_, axis=0).astype(np.float32)
            res = np.power(d_gain, residual)
            x_ *= res[:, None]
            mid *= (d_gain - res)[:, None]
            x_ += mid
            processed[name] = x_
        else:
            processed[name] *= d_gain[:, None]

    bed = sympathetic_bed(score, processed, specs, mx, sr)
    if bed is not None:
        bed = fit(bed, n)
        if bus is not None:
            bed_spec = default_spec(dict(role='pad'))
            if (mx.get('sympathetic_resonance') or {}).get('spatial'):
                bed_spec['spatial'] = dict(mx['sympathetic_resonance']['spatial'])
            bus.add('sympathetic_resonance', bed, bed_spec)
        else:
            dry += bed
    th = mix_schema.section(mx, 'theatrical')
    detail_gain = None
    if th.get('enabled') and bus is None:
        dry_ref = np.zeros((n, 2), np.float32)
        for y in processed.values():
            dry_ref[:min(len(y), n)] += y[:min(len(y), n)]
        detail_gain = theatrical_send_gain(dry_ref, sr, th)
    law = _space().get('distance', {}).get('pre_delay_law') if _space_owned_hook(_space()) else None
    STATE['sends'] = {}
    for name, y in processed.items():
        if bus is not None:
            placed = _biome_sources(name, y, stems.get(name), specs[name], sr)
            if placed:                                      # an environment track written as a biome: its emitters, not its stereo fold
                for ename, ey, espec in placed:
                    bus.add(ename, ey, espec)
            else:
                bus.add(name, y, specs[name])
        else:
            dry += y
        send_level = reverb_send_level(specs[name], mx, _space())
        STATE['sends'][name] = send_level
        ys = y * send_level
        pre = _space().get('predelay_ms_by_role') or {}
        if pre:
            ms = float(pre.get(specs[name].get('role'), pre.get('default', 0.0)) or 0.0)
            if ms > 0:
                k = int(ms * sr / 1000.0)
                if k > 0:
                    ys = np.pad(ys, ((k, 0), (0, 0)))[:len(ys)]   # pre-delay on the send, never the dry path
        if detail_gain is not None:
            ys = ys * detail_gain[:len(ys), None]
        sp_ = specs[name].get('spatial')
        if law and sp_:
            k = int(float(np.clip(law['base_ms'] - law['per_m'] * float(sp_.get('distance', 1.5)), 0.0,
                                  law['max_ms'])) * sr / 1000.0)
            if k > 0:
                ys = np.pad(ys, ((k, 0), (0, 0)))[:len(ys)]
        send += ys
    room = _space() if _space().get('room') else score.get('room', 'hall')
    if space_name != 'none' and send.any():
        ret = reverb_bus(send, room, sr) * float(score.get('mix', {}).get('reverb_return', 1.0))
        if bus is not None:
            bus.add_reverb(ret)
        else:
            total = len(ret)
            if total > len(dry):                 # grow the bus in place: a second full-length buffer is a copy
                dry = np.pad(dry, ((0, total - len(dry)), (0, 0)))
            dry[:total] += ret
            mix = dry
    else:
        mix = dry
    if th.get('enabled') and bus is None:
        out = theatrical_tone(mix, sr, th)
        mix = out
    else:
        out = bus.result() if bus is not None else mix
    # a mix bus can collect a slow drift from summed low beds and reverbs; DC-block it once, below hearing
    if getattr(out, 'ndim', 1) == 2 and len(out):
        sos = signal.butter(2, 30.0, btype='high', fs=sr, output='sos')   # sub-38 Hz only wanders the block mean; nothing musical lives there
        out = signal.sosfilt(sos, out, axis=0).astype(np.float32)
    return out


def mix_and_master(score, stems, out_path, master=True, sr=SR, report=True, ctx=None, diagnose=False):
    if not stems:
        raise ValueError('mix_and_master needs at least one stem')
    ctx = _context_for(score, ctx)
    release_stems()                 # a previous piece's stems must not accumulate in one process
    mix = mix_stems(score, stems, sr, ctx)
    loop = score.get('loop_seconds')
    if loop:
        mix = wrap_loop(mix, loop, sr)
    else:
        mix = trim_tail(mix, sr)
    m = dict(score.get('master', {}))
    m['_sections'] = (score.get('plan') or {}).get('sections')       # master_chain reads it for section_levels and drops it
    out = master_chain(mix, m, sr, ctx) if master else mix
    if not loop:
        out = fades(out, sr, fout=float(_master_cfg(m, _mix()).get('fade_out', 0.6)))
    if not np.isfinite(out).all():
        raise ValueError('the master produced non-finite samples')
    # Optional mid/side processing
    mm_cfg = _mix().get('mastering') or {}
    mid_gain = float(mm_cfg.get('mid_gain', 1.0))
    side_gain = float(mm_cfg.get('side_gain', 1.0))
    if mid_gain != 1.0 or side_gain != 1.0:
        out = apply_mid_side(out, mid_gain=mid_gain, side_gain=side_gain)
    over = int(np.sum(np.abs(out) >= 1.0))         # the no-master path clipped without ever saying so
    if over:
        sys.stderr.write(f'[export] {over} samples above full scale before the write (master skipped); '
                         f'the file is hard-clipped there\n')
    ceiling_db = None
    if master:             # the ceiling the master chain aimed at, less the write guard, so the written file stays under it
        ceiling_db = (float(_master_cfg(m, _mix()).get('true_peak', -1.5))
                      - float(mix_schema.section(_mix(), 'mastering')['true_peak_write_guard_db']))
    out, dtype_subtype = finalize_pcm(out, sr, mm_cfg, ceiling_db=ceiling_db)
    sf.write(out_path, out, sr, subtype=dtype_subtype)
    mm = _mix().get('mastering') or {}
    if master and mm.get('validate_export', True):
        master_tp = (STATE.get('master') or {}).get('true_peak')
        rep = _validate_export(out_path, sr, len(out) / sr,
                               ceiling=float(_master_cfg(m, _mix()).get('true_peak', -1.5)),
                               true_peak=master_tp)
        STATE['export'] = rep
        if rep['problems']:
            for p in rep['problems']:
                sys.stderr.write(f'[export] {p}\n')
    elif not master:
        STATE['export'] = {'path': out_path, 'clipped_samples': over,
                           'peak_db': float(20 * np.log10(np.abs(out).max() + 1e-12)),
                           'problems': [f'{over} samples above full scale'] if over else []}
    if diagnose:
        import mix_diagnostics
        STATE['diagnostics'] = mix_diagnostics.analyse(score, STATE.get('processed') or stems,
                                                      mix=_mix(), master=STATE.get('master'), sr=sr)
    if report:
        meas = STATE.get('master') if out is not None else None
        tp_txt = (f'{float(meas["true_peak"]):.2f}' if meas and meas.get('true_peak') is not None
                  else f'{true_peak_db(out, sr):.2f}')
        line = f'wrote {out_path}  {len(out)/sr:.1f}s  LUFS {lufs(out, sr):.1f}  true-peak {tp_txt} dBTP'
        if meas:
            line += (f'  crest {meas["crest"]:.1f} dB  LRA {meas["lra"]:.1f} LU  '
                     f'mono {meas["mono_fold"]:+.1f} dB')
        print(line)
    return out


def main():
    ap = argparse.ArgumentParser(description='Mix a folder of stem WAVs (any source) and master it.')
    ap.add_argument('stems_dir')
    ap.add_argument('--mix', default=None, help='JSON: {"tracks":[{"name","role","gain_db","pan","reverb",...}],'
                                                '"room":"hall","master":{...}}')
    ap.add_argument('--out', default='mixed.wav')
    ap.add_argument('--diagnose', action='store_true', help='print the mixing diagnostics table')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    import cli_util
    cli_util.require_dir(a.stems_dir, 'stems folder')
    cli_util.require_file(a.mix, 'mix spec')
    files = sorted(f for f in os.listdir(a.stems_dir) if f.lower().endswith('.wav'))
    stems = {os.path.splitext(f)[0]: sf.read(os.path.join(a.stems_dir, f), always_2d=True)[0].astype(np.float32)
             for f in files}
    cfg = json.load(open(a.mix, encoding='utf-8')) if a.mix else {}
    tracks = cfg.get('tracks') or [{'name': k, 'role': 'chord'} for k in stems]
    cfg['tracks'] = tracks
    mix_and_master(cfg, stems, a.out, report=not a.quiet, diagnose=a.diagnose)
    if a.diagnose:
        import mix_diagnostics
        for lvl, name, detail in STATE.get('diagnostics') or []:
            print(f'{lvl:6s} {name:22s} {detail}')
