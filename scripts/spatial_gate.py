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


def adm_rows(score, wav_path, out):
    """Rows for an ADM BW64 deliverable: the container itself (BW64 magic, ds64, fmt/chna/axml/data
    agreement) and the ADM integrity (IDs unique and resolved, chna mapping, block times, positions),
    then finite samples and the true-peak ceiling. The audio is parsed by the same structural reader the
    writer targets (adm.parse) because libsndfile only understands RIFF/RF64, not the BS.2088 BW64 magic."""
    import render_targets
    from spatial_engine import adm
    from spatial_engine import master
    ceiling = render_targets.true_peak('adm_bw64')
    problems = adm.validate_file(str(wav_path))
    _row(out, 'FAIL' if problems else 'PASS', 'adm.container',
         (f'adm_bw64: BW64 container/metadata problems: {"; ".join(problems)}' if problems
          else f'adm_bw64: strict BW64 (BS.2088) container with valid ADM metadata (BS.2076): '
               f'magic, ds64, fmt, chna, axml and data agree; IDs resolve; blocks tile the file'))
    try:
        parsed = adm.parse(str(wav_path))
    except ValueError as e:
        _row(out, 'FAIL', 'adm.channels', f'adm_bw64: cannot read the file to verify its channels ({e})')
        return
    finite_row(parsed['audio'], out, os.path.basename(str(wav_path)))
    _row(out, 'PASS', 'adm.channels',
         f"adm_bw64: {parsed['channels']} track(s) at {parsed['sr']} Hz, "
         f"{parsed['frames']} frames, {parsed['fmt']['bits']}-bit PCM; "
         f"each track maps to one ADM object (no fold-down)")
    peaks = master.channel_peaks(parsed['audio'], parsed['sr'])
    worst = float(np.max(peaks)) if len(peaks) else float('-inf')
    if ceiling is not None:
        _row(out, 'FAIL' if worst > ceiling else 'PASS', 'delivery.true_peak',
             f'adm_bw64: worst channel true peak {worst:+.1f} dBTP (ceiling {ceiling:+.1f} dBTP; '
             f'per channel {", ".join(f"{p:+.1f}" for p in peaks)})')
    _row(out, 'PASS', 'adm.loudness',
         'adm_bw64 loudness is levelled at render time on a constant-power stereo fold of the objects '
         '(engine-internal reference, BS.1770 loudness of the fold; an object file has no loudness of itself)')
    return


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
    if 'adm_bw64' in render_targets.resolve(score)['selected'] and \
            os.path.basename(str(wav_path)).endswith(render_targets.filename('adm_bw64')):
        adm_rows(score, wav_path, out)
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
        if n_ch == 1:
            continue
        if n_ch == 2:
            corr = float(np.corrcoef(sig.audio[:, 0], sig.audio[:, 1])[0, 1]) if n_ch == 2 else 1.0
            limit = float((tgt.get('gate') or {}).get('stereo_correlation_min', 0.0))
            _row(out, 'FAIL' if corr < limit else 'PASS', 'stereo.correlation',
                 f'{name}: inter-channel correlation {corr:+.2f} (floor {limit:+.2f}: below it the centre is cancelling)')
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
        if isinstance(idx, str):                      # the layout names its channel; the target may give an index
            idx = (order.index(idx) + 1) if idx in order else None
        if idx is not None and cfg.get('stopband_hz'):
            i = int(idx) - 1
            if 0 <= i < n_ch:
                from spatial_engine import bass
                leak = bass.stopband_leak_db(sig.audio[:, i], sig.sr, cfg, reference=sig.audio)
                limit = float(cfg.get('stopband_db', -45.0))
                _row(out, 'FAIL' if leak > limit else 'PASS', 'imm.lfe_stopband',
                     f'{name}: low-frequency channel energy above {float(cfg["stopband_hz"]):g} Hz is {leak:+.1f} dB '
                     f'relative to the programme (limit {limit:+.1f} dB)'
                     + ('; check the send and the mains high-pass' if leak > limit else ''))
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
        corr = float(np.corrcoef(fold[:, 0], fold[:, 1])[0, 1]) if len(fold) > 1 else 1.0
        limit = float((tgt.get('gate') or {}).get('stereo_correlation_min', 0.0))
        _row(out, 'FAIL' if corr < limit else 'PASS', 'imm.fold_coherence',
             f'{name}: the two-channel fold has correlation {corr:+.2f} (floor {limit:+.2f})')
