# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""spatial_gate.py - the rows a multichannel deliverable must pass, and only for the formats it asked for.

The gate reads the score's `output_targets` through render_targets and checks the file that was actually produced
against the target's own data (its channel order, its true-peak ceiling) and its layout's own data (the low-frequency
crossover and stopband, the surround-energy window, the height ceiling). A format that was not requested is never
checked and never failed.

This module measures only. It has no thresholds of its own.
"""
import os

import numpy as np

from gate_audio import channel_correlation


def correlation_verdict(corr, floor):
    """(level, note). A correlation that cannot be measured (a silent or constant channel) is a FAIL, never a pass."""
    if not np.isfinite(corr):
        return 'FAIL', ' (a channel is silent or constant, so the correlation is undefined)'
    return ('FAIL' if corr < floor else 'PASS'), ''


def _row(out, level, name, detail):
    out.append((level, name, detail))


def _db(x):
    x = np.asarray(x, dtype=np.float64)
    return float(20.0 * np.log10(np.sqrt(np.mean(np.square(x)) + 1e-20)))


def targets_for(score, channels, path=None):
    """The selected targets this file is: the one whose file name it carries when there is one (5.1.2 and 7.1 both
    have eight channels, so a channel count alone cannot tell them apart), else every selected target with that
    channel count. Empty when the file is not a requested format."""
    import render_targets
    sel = render_targets.resolve(score)['selected']
    same = [t for t in sel if render_targets.channels(t) == int(channels)]
    if path is not None:
        base = os.path.basename(str(path))
        if base.startswith('_draft_'):
            base = base[len('_draft_'):]
        named = [t for t in same if base == render_targets.filename(t)]
        if named:
            return named
    return same


def _erb_bands(lo=100.0, hi=5000.0):
    """Edges of the auditory bands between lo and hi (one ERB each): the bands quality_gate.fold_rows uses."""
    import quality_gate
    return quality_gate._erb_edges()


def band_levels(x, sr, edges):
    """Power in each band of a one-channel signal (Welch), as an array."""
    from scipy.signal import welch
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    f, p = welch(x, fs=float(sr), nperseg=min(len(x), 8192))
    return np.array([p[(f >= a) & (f < b)].sum() for a, b in zip(edges[:-1], edges[1:])])


def fold_timbre(reference, candidate, sr, floor_db=30.0):
    """How far the spectrum of `candidate` departs from `reference`, band by band, once their overall levels are
    matched: (worst deviation in dB, the band's edges in Hz). Bands more than `floor_db` under the loudest band of
    the reference are left out: a band with nothing in it has nothing to lose."""
    edges = _erb_bands()
    a, b = band_levels(reference, sr, edges), band_levels(candidate, sr, edges)
    keep = a > a.max() * 10.0 ** (-float(floor_db) / 10.0) if a.max() > 0 else np.zeros(len(a), bool)
    if not keep.any() or b[keep].sum() <= 0:
        return 0.0, (0.0, 0.0)
    dev = 10.0 * np.log10((b + 1e-30) / (a + 1e-30))
    dev = dev - 10.0 * np.log10(b[keep].sum() / a[keep].sum())        # level-matched over the bands that count
    i = int(np.argmax(np.where(keep, np.abs(dev), -1.0)))
    return float(dev[i]), (float(edges[i]), float(edges[i + 1]))


def fold_rows(score, primary_path, extra_path, target_name, out):
    """Rows that compare a deliverable with the certified two-channel master it was delivered beside.

    fold.mono    the rendered mono against the plain sum of the stereo master, band by band. Where they agree, the
                 stereo master is safe on a system that sums it; where they do not, the row names the band the sum
                 loses or gains, which is what a listener on one speaker would hear of the stereo file.
    fold.timbre  a loudspeaker layout folded to two channels (the layout's own BS.775 coefficients) against the
                 stereo master: no format may be the dull one or the thin one.

    Both are comparisons of long-term spectra after level matching. They do not see a part that is missing for two
    bars; the per-file rows and the listening pass are for that.
    """
    import gate_audio
    import render_targets
    tgt = render_targets.get(target_name) or {}
    gate = tgt.get('gate') or {}
    limit = gate.get('fold_band_max_db')
    if limit is None:
        return
    import gate_audio
    primary_name = (render_targets.resolve(score)['selected'] or [None])[0]
    primary = render_targets.get(primary_name) or {}
    floor = float(gate.get('fold_floor_db', 30.0))
    stereo_master = primary.get('channels') == 2 and primary.get('renderer') == 'mix_master'
    if not stereo_master and not (tgt.get('layout') and render_targets.channels(target_name) > 2):
        _row(out, 'WARN', 'fold.reference',
             f'{target_name}: no loudspeaker stereo master was delivered first ("{primary_name}") and this format '
             f'has no layout to fold, so the fold-down comparison was not made')
        return
    try:
        new = gate_audio.load(extra_path)
    except Exception as exc:
        _row(out, 'FAIL', 'fold.reference', f'{target_name}: cannot read the file to compare it ({exc})')
        return
    if not stereo_master:
        # No stereo master beside it: compare the delivered layout with its own fold instead of not making the
        # row. A run that delivers only `immersive_7_1_2` renders nothing else, and the question the row asks (is
        # there a band the format cancels in its own downmix) is still answerable from the file it delivered.
        _own_fold(tgt, new, target_name, limit, floor, out)
        return
    try:
        ref = gate_audio.load(primary_path)
    except Exception as exc:
        _row(out, 'FAIL', 'fold.reference', f'{target_name}: cannot read the master to compare it ({exc})')
        return
    if ref.sr != new.sr:
        _row(out, 'WARN', 'fold.reference', f'{target_name}: {new.sr} Hz against a {ref.sr} Hz master; not compared')
        return
    stereo_sum = 0.5 * (ref.audio[:, 0] + ref.audio[:, 1])
    if tgt.get('renderer') == 'mono':
        dev, (lo, hi) = fold_timbre(new.audio[:, 0], stereo_sum, ref.sr, floor)
        bad = abs(dev) > float(limit)
        _row(out, 'FAIL' if bad else 'PASS', 'fold.mono',
             (f'{target_name}: summed to one channel, the stereo master is {dev:+.1f} dB against the rendered mono at '
              f'{lo:.0f}-{hi:.0f} Hz (limit {float(limit):g} dB): something there is cancelling or doubling in the '
              f'stereo file. Narrow or re-pan the part that lives in that band' if bad else
              f'{target_name}: the stereo master summed to one channel stays within {float(limit):g} dB of the '
              f'rendered mono in every auditory band from 100 to 5000 Hz (worst {dev:+.1f} dB at {lo:.0f}-{hi:.0f} Hz)'))
        return
    lay = tgt.get('layout')
    if lay and new.channels > 2:
        from spatial_engine import downmix
        fold = downmix.fold(new.audio, lay)
        dev, (lo, hi) = fold_timbre(stereo_sum, 0.5 * (fold[:, 0] + fold[:, 1]), ref.sr, floor)
        bad = abs(dev) > float(limit)
        _row(out, 'FAIL' if bad else 'PASS', 'fold.timbre',
             (f'{target_name}: folded to two channels it is {dev:+.1f} dB against the stereo master at '
              f'{lo:.0f}-{hi:.0f} Hz (limit {float(limit):g} dB): this format does not sound like the same mix there'
              if bad else
              f'{target_name}: folded to two channels it stays within {float(limit):g} dB of the stereo master in '
              f'every auditory band from 100 to 5000 Hz (worst {dev:+.1f} dB at {lo:.0f}-{hi:.0f} Hz)'))


def _own_fold(tgt, new, target_name, limit, floor, out):
    """fold.timbre for a loudspeaker layout delivered on its own: the format against its own two-channel fold.

    The reference is the delivered format's own channel power (every channel but the low-frequency one); the
    candidate is the fold a two-channel listener will hear of it. Bands are level-matched first, so the row asks
    about shape, not level: a band the fold loses is a band this layout cancels in its own downmix.
    """
    from spatial_engine import config, downmix
    lay = (tgt or {}).get('layout')
    if not lay or new.channels <= 2:
        _row(out, 'WARN', 'fold.reference',
             f'{target_name}: not a loudspeaker layout, so it has no fold to compare against')
        return
    names = config.channel_names(lay)
    if len(names) != new.channels:
        _row(out, 'WARN', 'fold.reference',
             f'{target_name}: {new.channels} channel(s) but layout "{lay}" has {len(names)}; not compared')
        return
    lfe = {sp['name'] for sp in config.layout(lay)['speakers'] if sp.get('lfe')}
    edges = _erb_bands()
    total = np.zeros(len(edges) - 1)
    for i, name in enumerate(names):
        if name not in lfe:
            total += band_levels(new.audio[:, i], new.sr, edges)
    fold = downmix.fold(new.audio, lay)
    have = band_levels(0.5 * (fold[:, 0] + fold[:, 1]), new.sr, edges)
    top = float(total.max()) if total.size else 0.0
    keep = total > top * 10.0 ** (-float(floor) / 10.0) if top > 0 else np.zeros(total.shape, bool)
    if not keep.any() or have[keep].sum() <= 0:
        dev, lo, hi = 0.0, 0.0, 0.0
    else:
        dev = 10.0 * np.log10((have + 1e-30) / (total + 1e-30))
        dev = dev - 10.0 * np.log10(have[keep].sum() / total[keep].sum())
        i = int(np.argmax(np.where(keep, np.abs(dev), -1.0)))
        dev, lo, hi = float(dev[i]), float(edges[i]), float(edges[i + 1])
    bad = abs(dev) > float(limit)
    _row(out, 'FAIL' if bad else 'PASS', 'fold.timbre',
         (f'{target_name}: its own two-channel fold is {dev:+.1f} dB against the delivered channels at '
          f'{lo:.0f}-{hi:.0f} Hz (limit {float(limit):g} dB): this layout cancels that band in its downmix'
          if bad else
          f'{target_name}: its own two-channel fold stays within {float(limit):g} dB of the delivered channels in '
          f'every auditory band from 100 to 5000 Hz (worst {dev:+.1f} dB at {lo:.0f}-{hi:.0f} Hz); no stereo master '
          f'was delivered, so the comparison is the layout against its own fold'))


def _selected_target(score, wav_path, default='adm_bw64'):
    """The target this file is: its file name picks it out of the selected list, else the given default."""
    import render_targets
    base = os.path.basename(str(wav_path))
    for name in render_targets.resolve(score)['selected']:
        if base.endswith(render_targets.filename(name)):
            return name
    return default


def delivery_sidecar_rows(wav_path, target_name, out):
    """Rows a target declares against the render's own report: a loudness ceiling and a conform window.

    Only a target that names one gets the row. The values are read from `<file>.<format>_report.json`,
    written by the renderer from measurements on the delivered audio; no sidecar means the row says what
    could not be checked instead of passing.
    """
    import json
    import render_targets
    tgt = render_targets.get(target_name) or {}
    ceiling = (tgt.get('loudness') or {}).get('ceiling_lufs')
    conform = tgt.get('conform_max_ms')
    if ceiling is None and conform is None:
        return
    report = {}
    for suffix in ('.adm_report.json', '.iamf_report.json'):
        path = str(wav_path) + suffix
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as fh:
                    report = json.load(fh)
            except (OSError, ValueError):
                report = {}
            break
    if ceiling is not None:
        got = report.get('integrated_lufs')
        if got is None:
            _row(out, 'WARN', 'delivery.loudness_ceiling',
                 f'{target_name}: the render report is missing, so the {float(ceiling):+.1f} LKFS ceiling '
                 f'could not be checked')
        else:
            bad = float(got) > float(ceiling) + 1e-6
            _row(out, 'FAIL' if bad else 'PASS', 'delivery.loudness_ceiling',
                 f'{target_name}: {float(got):.1f} LKFS on the engine stereo fold (ceiling '
                 f'{float(ceiling):+.1f} LKFS)'
                 + ('; the render is over the ceiling the target declares' if bad else ''))
    if conform is not None:
        got = report.get('conform_ms')
        if got is None:
            _row(out, 'WARN', 'delivery.conform',
                 f'{target_name}: no certified stereo master length was recorded, so the '
                 f'{float(conform):g} ms conform window could not be checked')
        else:
            bad = abs(float(got)) > float(conform) + 1e-6
            _row(out, 'FAIL' if bad else 'PASS', 'delivery.conform',
                 f'{target_name}: {float(got):+.1f} ms against the certified stereo master '
                 f'(window +-{float(conform):g} ms)'
                 + ('; the files do not start and end together' if bad else ''))


def iamf_rows(score, wav_path, out):
    """An IAMF file exists and starts like an ISO-BMFF/IAMF stream. It was encoded outside this project."""
    import render_targets
    name = _selected_target(score, wav_path, 'iamf')
    try:
        with open(str(wav_path), 'rb') as fh:
            head = fh.read(16)
    except OSError as exc:
        _row(out, 'FAIL', 'iamf.container', f'{name}: cannot read the file ({exc})')
        return
    ok = len(head) >= 12 and head[4:8] in (b'ftyp', b'iamf')
    _row(out, 'FAIL' if not ok else 'PASS', 'iamf.container',
         (f'{name}: the file does not start with an ISO-BMFF/IAMF box: it is not the encoded deliverable'
          if not ok else
          f'{name}: ISO-BMFF/IAMF container written by the external encoder; it was not decoded or '
          f'profile-validated here'))
    delivery_sidecar_rows(wav_path, name, out)


def adm_rows(score, wav_path, out):
    """Rows for an ADM BW64 deliverable: the container itself (BW64 magic, ds64, fmt/chna/axml/data
    agreement) and the ADM integrity (IDs unique and resolved, chna mapping, block times, positions),
    then finite samples and the true-peak ceiling. The audio is parsed by the same structural reader the
    writer targets (adm.parse) because libsndfile only understands RIFF/RF64, not the BS.2088 BW64 magic."""
    import render_targets
    from spatial_engine import adm
    from spatial_engine import master
    name = _selected_target(score, wav_path, 'adm_bw64')
    ceiling = render_targets.true_peak(name)
    problems = adm.validate_file(str(wav_path))
    _row(out, 'FAIL' if problems else 'PASS', 'adm.container',
         (f'{name}: BW64 container/metadata problems: {"; ".join(problems)}' if problems
          else f'{name}: strict BW64 (BS.2088) container with valid ADM metadata (BS.2076): '
               f'magic, ds64, fmt, chna, axml and data agree; IDs resolve; blocks tile the file'))
    try:
        parsed = adm.parse(str(wav_path))
    except ValueError as e:
        _row(out, 'FAIL', 'adm.channels', f'{name}: cannot read the file to verify its channels ({e})')
        return
    finite_row(parsed['audio'], out, os.path.basename(str(wav_path)))
    _row(out, 'PASS', 'adm.channels',
         f"{name}: {parsed['channels']} track(s) at {parsed['sr']} Hz, "
         f"{parsed['frames']} frames, {parsed['fmt']['bits']}-bit PCM; "
         + ('each channel is one named loudspeaker of the layout (DirectSpeakers pack)'
            if (render_targets.get(name) or {}).get('renderer') == 'adm_speakers'
            else 'each track maps to one ADM object (no fold-down)'))
    peaks = master.channel_peaks(parsed['audio'], parsed['sr'])
    worst = float(np.max(peaks)) if len(peaks) else float('-inf')
    if ceiling is not None:
        _row(out, 'FAIL' if worst > ceiling else 'PASS', 'delivery.true_peak',
             f'{name}: worst channel true peak {worst:+.1f} dBTP (ceiling {ceiling:+.1f} dBTP; '
             f'per channel {", ".join(f"{p:+.1f}" for p in peaks)})')
    _row(out, 'PASS', 'adm.loudness',
         f'{name} loudness is levelled at render time on a constant-power stereo fold of the objects '
         '(engine-internal reference, BS.1770 loudness of the fold; an object file has no loudness of itself)')
    delivery_sidecar_rows(wav_path, name, out)
    return


def _conflict_text(c):
    """One line for a per-bar finding, in the terms a mixer can act on."""
    if c['kind'] == 'balance':
        return (f"bar {c['bar']} {c['group']} balance {c['delta_db']:+.1f} dB "
                f"({c['ratio_db']:+.1f} dB against {c['neighbour_db']:+.1f} dB in both neighbours)")
    if c['kind'] == 'polarity':
        return (f"bar {c['bar']} {c['channel_name']} polarity inverted "
                f"(corr {c['corr_prev']:+.2f}/{c['corr_next']:+.2f} against the neighbours)")
    return (f"bar {c['bar']} {c['channel_name']} {c['kind']} {c['delta_db']:+.1f} dB "
            f"(neighbours at {c['neighbour_db']:+.1f} dB)")


def channel_rows(score, audio, sr, target, out):
    """Per-channel and per-bar rows for any channel count.

    `channel.virtual` puts the file on the positions it claims (a real loudspeaker layout, or the 36-point
    virtual sphere for order-5 AmbiX) or says that it has no layout and is checked per channel. `channel.bars`
    then looks for an isolated bar where one channel jumps, drops out, flips polarity or swings the balance
    while the other channels stay still. The narrow question is deliberate: a one-bar accent moves every
    channel in the bar and is not a channel fault.
    """
    import channel_qa
    import gate_profiles
    import render_targets
    gate = gate_profiles.resolve(score)
    want_virtual = gate.on('channel.virtual')
    want_bars = gate.on('channel.bars')
    if not (want_virtual or want_bars):
        return
    params = {k: gate.param('channel.bars', k) for k in channel_qa.PARAMS}
    try:
        a = channel_qa.analyse(score, audio, sr, target, params)
    except Exception as exc:
        if want_virtual:
            _row(out, 'FAIL', 'channel.virtual',
                 f'{target}: cannot put the delivered file on the layout it claims ({exc})')
        elif want_bars:
            _row(out, 'FAIL', 'channel.bars',
                 f'{target}: cannot measure the per-bar channels because the layout mapping failed ({exc})')
        return
    if want_virtual:
        finite = bool(np.isfinite(a['signals']).all() and
                      (a.get('raw') is None or np.isfinite(a['raw']).all()))
        if not finite:
            _row(out, 'FAIL', 'channel.virtual',
                 f"{target}: {a['note']}; a decoded or delivered channel holds NaN or an infinite sample")
        else:
            _row(out, 'PASS', 'channel.virtual', f"{target}: {a['note']}; every channel is finite")
    if gate.on('imm.decode_uniformity'):
        import mixer
        from spatial_engine import config, hoa
        from spatial_hrtf import sph
        lay = (render_targets.get(target) or {}).get('layout')
        if lay and len(config.speakers(lay)) > 2:
            order = int(((mixer._mix() or {}).get('immersive') or {}).get('order', 5))
            spk = config.speakers(lay)
            az, el = hoa._sphere_points(400)
            y = sph.sh_matrix(order, np.radians(az), np.radians(90.0 - el), 'real')
            kind = str(((mixer._mix() or {}).get('immersive') or {}).get('decoder') or 'allrad2')
            matrix = (hoa.allrad_matrix(spk, order, points=400) if kind == 'allrad'
                      else hoa.allrad2_matrix(spk, order, points=400))
            power = np.sum((y @ matrix.T) ** 2, axis=1)
            db = 10.0 * np.log10(power / np.mean(power) + 1e-30)
            spread = float(db.max() - db.min())
            declared = (config.threshold(lay, 'decode_uniformity_max_db') or {}).get(kind)
            limit = float(declared) if declared is not None else float(gate.param('imm.decode_uniformity', 'max_spread_db'))
            bad = spread > limit
            _row(out, 'WARN' if bad else 'PASS', 'imm.decode_uniformity',
                 f'{target}: {kind} plane-wave power spread {spread:.2f} dB over the sphere '
                 f'(limit {limit:g} dB)'
                 + ('; a direction will be audibly louder than another' if bad else ''))
    if not want_bars:
        return
    bars = int(a['bars'])
    if bars < 3:
        _row(out, 'INFO', 'channel.bars',
             f'{target}: {bars} bar(s) checked on {a["channels"]} channel(s); fewer than three bars, so no '
             f'bar has two neighbours to compare against')
        return
    conflicts = a['conflicts']
    if not conflicts:
        _row(out, 'PASS', 'channel.bars',
             f'{target}: {bars} bars checked on {a["channels"]} channel(s); no isolated channel jump, '
             f'dropout, balance swing or polarity conflict in any bar')
        return
    shown = '; '.join(_conflict_text(c) for c in conflicts[:6])
    more = f' (+{len(conflicts) - 6} more)' if len(conflicts) > 6 else ''
    _row(out, 'FAIL', 'channel.bars',
         f'{target}: {len(conflicts)} isolated per-bar channel conflict(s): {shown}{more}. '
         f'Check that channel\'s automation, pan and polarity in that bar; a deliberate one-bar effect can be '
         f'relaxed in the score gate with a measured reason, never by editing the row')


def lfe_rows(score, audio, sr, target, out):
    """lfe.* and front.fold_phantom for a layout with two low-frequency channels or a declared three-front stage."""
    import gate_profiles
    import render_targets
    from spatial_engine import config, lfe_qa
    gate = gate_profiles.resolve(score)
    lay = (render_targets.get(target) or {}).get('layout')
    if not lay:
        return
    order = list(config.channel_names(lay))
    lfe = config.lfe_names(lay)
    cfg = config.lfe_cfg(lay, target)
    if len(lfe) == 2 and audio.shape[1] == len(order):
        a, b = (audio[:, order.index(n)] for n in lfe)
        hi = float(cfg.get('lowpass_hz', lfe_qa.BAND_HZ[1]))
        if gate.on('lfe.polarity'):
            rho0, best, lag = lfe_qa.polarity(a, b, sr, hi)
            limit = float(gate.param('lfe.polarity', 'min_rho'))
            bad = rho0 < limit and best > 0.3
            _row(out, 'FAIL' if bad else ('WARN' if rho0 < 0.0 else 'PASS'), 'lfe.polarity',
                 f'{target}: {lfe[0]}/{lfe[1]} zero-lag correlation {rho0:+.2f} (best {best:.2f} at {lag:+.2f} ms; '
                 f'fails below {limit:+.2f})' + ('; one low-frequency channel is inverted: set `lfe.polarity` or fix the '
                                                  'bass preset' if bad else ''))
        if gate.on('lfe.sum_coherence'):
            fd = float(cfg.get('decorrelate_above_hz', 40.0))
            rho = lfe_qa.coherence(a, b, sr, lfe_qa.BAND_HZ[0], fd)
            limit = float(gate.param('lfe.sum_coherence', 'min_rho'))
            bad = rho < limit and float(np.mean(a * a) + np.mean(b * b)) > 1e-10
            _row(out, 'WARN' if bad else 'PASS', 'lfe.sum_coherence',
                 f'{target}: {lfe[0]}/{lfe[1]} correlation {rho:+.2f} over {lfe_qa.BAND_HZ[0]:g}-{fd:g} Hz (want {limit:.2f} '
                 f'or more)' + ('; the subs would cancel in that band: use mode stereo_bass or check lfe_pan' if bad else ''))
        if gate.on('lfe.fold_loss'):
            bands, k = lfe_qa.fold_loss_db(a, b, sr, lfe_qa.BAND_HZ[0], hi)
            worst = max(bands, key=lambda t: abs(t[1])) if bands else (0.0, 0.0)
            limit = float(gate.param('lfe.fold_loss', 'max_db'))
            bad = abs(worst[1]) > limit
            _row(out, 'WARN' if bad else 'PASS', 'lfe.fold_loss',
                 f'{target}: folding {lfe[0]}+{lfe[1]} into one channel (gain {k:.2f}) moves the {worst[0]:.0f} Hz band '
                 f'by {worst[1]:+.1f} dB (limit +-{limit:g} dB)' + ('; reduce the decorrelation' if bad else ''))
        room = (config.layout(lay).get('qa') or {}).get('listening_room')
        if gate.on('lfe.modal_spread'):
            if room:
                m = lfe_qa.modal_spread(room, coherent_below_hz=float(cfg.get('decorrelate_above_hz', 40.0)))
                limit = float(gate.param('lfe.modal_spread', 'min_gain_db'))
                bad = m['improvement_db'] < limit
                _row(out, 'WARN' if bad else 'INFO', 'lfe.modal_spread',
                     f"{target}: virtual {room['size_m'][0]:g}x{room['size_m'][1]:g}x{room['size_m'][2]:g} m room, RT60 "
                     f"{room['rt60_s']:g} s: spatial spread {m['one_sub_db']:.1f} dB with one sub, {m['two_subs_db']:.1f} dB "
                     f"with two ({m['improvement_db']:+.1f} dB). A model of a box, not the listener's room")
            else:
                _row(out, 'INFO', 'lfe.modal_spread', f'{target}: the layout declares no qa.listening_room; room modes not modelled')
    front = (config.layout(lay).get('qa') or {}).get('front')
    if front and gate.on('front.fold_phantom'):
        try:
            m = lfe_qa.phantom_fold_error(lay, int(sr))
        except Exception as exc:
            _row(out, 'WARN', 'front.fold_phantom', f'{target}: not measured ({exc})')
        else:
            li, ld = float(gate.param('front.fold_phantom', 'max_itd_us')), float(gate.param('front.fold_phantom', 'max_ild_db'))
            bad = m['itd_error_us'] > li or m['ild_error_db'] > ld
            _row(out, 'WARN' if bad else 'PASS', 'front.fold_phantom',
                 f"{target}: the centre folded into L/R differs from a real centre by {m['itd_error_us']:.0f} us (limit {li:g}) "
                 f"and {m['ild_error_db']:.1f} dB (limit {ld:g}); colour {m['colour_rms_db']:.1f} dB rms over 1-8 kHz. "
                 f'Measured on noise through the head set, independent of the programme')


def finite_row(audio, out, name='the delivered file'):
    """render.finite: a NaN or an infinity in any channel. Players differ on what they do with one (silence, a full
    scale burst), so no file that holds one is delivered."""
    a = np.asarray(audio)
    bad = [c for c in range(a.shape[1] if a.ndim == 2 else 1)
           if not np.isfinite(a[:, c] if a.ndim == 2 else a).all()]
    _row(out, 'FAIL' if bad else 'PASS', 'render.finite',
         (f'{name}: channel(s) {", ".join(str(c + 1) for c in bad)} hold NaN or infinite samples' if bad
          else f'{name}: every sample of every channel is a finite number'))


def output_rows(score, wav_path, out):
    """Rows for the delivered file: its format, its ceiling, and the checks that format needs."""
    import render_targets
    from spatial_engine import config
    # An ADM deliverable is recognised by having been requested and by the target's file name: its channel
    # count is the piece's, not the format's (channels 0 in the preset), and its container is BW64, which
    # the soundfile-based reader cannot open -- so it gets its own structural branch below.
    selected = render_targets.resolve(score)['selected']
    base = os.path.basename(str(wav_path))
    if any((render_targets.get(n) or {}).get('renderer') in ('adm', 'adm_speakers') and base.endswith(render_targets.filename(n))
           for n in selected):
        adm_rows(score, wav_path, out)
        return
    if any((render_targets.get(n) or {}).get('renderer') == 'iamf' and base.endswith(render_targets.filename(n))
           for n in selected):
        iamf_rows(score, wav_path, out)
        return
    import gate_audio
    try:
        sig = gate_audio.load(wav_path)
    except Exception as exc:
        _row(out, 'FAIL', 'delivery.format', f'cannot read {wav_path} to verify the requested format ({exc})')
        return
    n_ch = sig.channels
    finite_row(sig.audio, out, os.path.basename(str(wav_path)))
    targets = targets_for(score, n_ch, wav_path) or [
        t for t in render_targets.resolve(score)['selected']
        if not render_targets.channels(t) and os.path.basename(str(wav_path)).endswith(render_targets.filename(t))]
    if not targets:
        requested = render_targets.resolve(score)['selected']
        _row(out, 'FAIL', 'delivery.format',
             f'{wav_path} has {n_ch} channel(s), which matches none of the requested target(s) '
             f'{", ".join(requested) or "none"}: the delivered format is not the promised one')
        return
    for target in targets:
        name = target
        tgt = render_targets.get(target) or {}
        ceiling = render_targets.true_peak(target)
        peaks = sig.true_peak_by_channel
        worst = float(np.max(peaks))
        if ceiling is not None:
            _row(out, 'FAIL' if worst > ceiling else 'PASS', 'delivery.true_peak',
                 f'{name}: worst channel true peak {worst:+.1f} dBTP (ceiling {ceiling:+.1f} dBTP; '
                 f'per channel {", ".join(f"{p:+.1f}" for p in peaks)})')
        channel_rows(score, sig.audio, sig.sr, name, out)
        lfe_rows(score, sig.audio, sig.sr, name, out)
        if n_ch == 1:
            continue
        if n_ch == 2:
            corr = channel_correlation(sig.audio[:, 0], sig.audio[:, 1])
            limit = float((tgt.get('gate') or {}).get('stereo_correlation_min', 0.0))
            level, note = correlation_verdict(corr, limit)
            _row(out, level, 'stereo.correlation',
                 f'{name}: inter-channel correlation {corr:+.2f} (floor {limit:+.2f}: below it the centre is cancelling)' + note)
            continue
        lay_name = tgt.get('layout')
        if not lay_name:
            continue
        cfg = config.lfe_cfg(lay_name, target)
        order = list(tgt.get('channel_order') or [])
        if (tgt.get('loudness') or {}).get('method') == 'bs1770_layout' and len(order) == n_ch:
            import loudness
            import mix_schema
            import mixer
            got = loudness.layout_lufs(sig.audio, lay_name, sig.sr)
            mcfg = mixer._master_cfg(dict((score or {}).get('master') or {}), mixer._mix())
            want = float((tgt.get('loudness') or {}).get('target_lufs', mcfg.get('lufs', -14.0)))
            miss = float(mix_schema.section(mixer._mix(), 'mastering')['converge']['report_miss_lu'])
            off = abs(got - want) > miss
            _row(out, 'WARN' if off else 'PASS', 'imm.loudness',
                 f'{name}: {got:.1f} LKFS on the delivered channels against a {want:g} LKFS target (ITU-R BS.1770 with '
                 f'this layout\'s channel weights, low-frequency channel excluded)'
                 + ('; the limiter stopped at its allowed reduction rather than flatten the programme: lower the '
                    'target or accept it' if off and got < want else ''))
        # low-frequency channel: nothing above the stopband may leave it
        idx = cfg.get('channel')
        for one in (idx if isinstance(idx, list) else [idx]):
            if isinstance(one, str):                  # the layout names its channel; the target may give an index
                one = (order.index(one) + 1) if one in order else None
            if one is None or not cfg.get('stopband_hz'):
                continue
            i = int(one) - 1
            if 0 <= i < n_ch:
                from spatial_engine import bass
                leak = bass.stopband_leak_db(sig.audio[:, i], sig.sr, cfg, reference=sig.audio)
                limit = float(cfg.get('stopband_db', -45.0))
                _row(out, 'FAIL' if leak > limit else 'PASS', 'imm.lfe_stopband',
                     f'{name}: low-frequency channel {order[i] if i < len(order) else i + 1} energy above '
                     f'{float(cfg["stopband_hz"]):g} Hz is {leak:+.1f} dB relative to the programme '
                     f'(limit {limit:+.1f} dB)' + ('; check the send and the mains high-pass' if leak > limit else ''))
        gate = config.threshold(lay_name, 'surround_ratio_db')
        surrounds = [n for n in order if n in ('BL', 'BR', 'SL', 'SR')]
        fronts = [n for n in order if n in ('FL', 'FR', 'FC')]
        if gate and surrounds and fronts:
            s = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in surrounds))
            f = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in fronts))
            ratio = float(20.0 * np.log10((s + 1e-20) / (f + 1e-20)))
            lo, hi = float(gate[0]), float(gate[1])
            _row(out, 'PASS' if lo <= ratio <= hi else 'FAIL', 'imm.surround_ratio',
                 f'{name}: surround energy {ratio:+.1f} dB against the front stage (window {lo:+.1f}..{hi:+.1f} dB)')
        hlimit = config.threshold(lay_name, 'height_max_rel_db')
        heights = [sp['name'] for sp in config.layout(lay_name)['speakers'] if float(sp.get('elevation', 0.0)) > 0]
        beds = [sp['name'] for sp in config.layout(lay_name)['speakers']
                if float(sp.get('elevation', 0.0)) <= 0 and not sp.get('lfe')]
        if hlimit is not None and heights and beds:
            h = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in heights))
            b = np.sqrt(sum(np.mean(np.square(sig.audio[:, order.index(n)])) for n in beds))
            rel = float(20.0 * np.log10((h + 1e-20) / (b + 1e-20)))
            _row(out, 'PASS' if rel <= float(hlimit) else 'FAIL', 'imm.height_arc',
                 f'{name}: height channels {rel:+.1f} dB against the listener-level beds (ceiling {float(hlimit):+.1f} dB)')
        # a multichannel file must fold to a coherent stereo image (no destructive phase between the two)
        from spatial_engine import downmix
        fold = downmix.fold(sig.audio, lay_name)
        corr = channel_correlation(fold[:, 0], fold[:, 1]) if len(fold) > 1 else 1.0
        limit = float((tgt.get('gate') or {}).get('stereo_correlation_min', 0.0))
        level, note = correlation_verdict(corr, limit)
        _row(out, level, 'imm.fold_coherence',
             f'{name}: the two-channel fold has correlation {corr:+.2f} (floor {limit:+.2f})' + note)
