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
"""sfx_eval.py - does this effect or ambience *behave* like a physical sound, or only pass a syntax check?

    python scripts/sfx_eval.py out.wav [--kind impact|granular|flow|foliage|fracture|gait|tonal] [--json]

`acceptable()` in sfx.py answers "is this a valid buffer". This answers the questions a listener would ask first, as
measurements:

    tonal_excess        one frequency sticking out of a supposedly noisy event (a whistle inside rain)
    periodicity         the sound repeating on a cycle (an LFO wearing a texture)
    transient_uniformity every event the same size (a loop, not a cascade)
    hf_hiss             the top end is a wall of hiss
    missing_low_end     a heavy contact with no structural weight
    over_normalized     the peak sits exactly at the legacy normalization value and the crest is low
    dc / clipping / clicks

Every row is WARN or PASS, never FAIL: these are symptoms to look at, not a verdict. The verdict is a listener's. The
thresholds live in LIMITS so a project can argue with a number instead of arguing with the code.

It reuses what exists rather than re-deriving it: `quality_gate.find_clicks`, and `ambience_reference.measure_array`
for the band shares when a clip is long enough.
"""
import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

SR = 44100

LIMITS = dict(
    tonal_excess_db=24.0,        # a peak this far above its local spectral floor in a noise event
    periodicity=0.60,            # normalized autocorrelation at a cyclic lag
    transient_cv=0.08,           # coefficient of variation of onset peaks (0 = every hit identical)
    hf_share=0.50,               # share of energy above 7 kHz
    lf_share=0.01,               # share of energy below 300 Hz, for a heavy contact
    dc=1e-3,
    peak=0.999,
    legacy_peak=0.9,             # sfx._norm's default, the fingerprint of peak normalization
    low_crest=6.0,
    period_lags=(0.02, 0.5),     # s: the cyclic spans worth calling "periodic"
)

NOISY = ('granular', 'flow', 'foliage', 'friction', 'rolling')     # a tonal peak in these is a fault
HEAVY = ('impact', 'fracture', 'gait', 'repeated_impact')          # these should carry low end


def _mono(x):
    x = np.asarray(x, dtype=float)
    return x.mean(axis=1) if x.ndim == 2 else x


def metrics(x, sr=SR):
    """Everything measured here, in one dict. Never raises on a valid buffer."""
    m = _mono(x)
    n = len(m)
    out = dict(seconds=round(n / sr, 3), peak=0.0, rms_db=-120.0, crest=0.0, dc=0.0)
    if n < 512:                       # too short to measure anything but level; never raise on a stub
        if n:
            peak = float(np.abs(m).max())
            rms = float(np.sqrt(np.mean(m ** 2)))
            out.update(peak=round(peak, 6), rms_db=round(20 * np.log10(rms + 1e-12), 2),
                       crest=round(peak / (rms + 1e-12), 2), dc=round(float(np.mean(m)), 6))
        return out
    peak = float(np.abs(m).max())
    rms = float(np.sqrt(np.mean(m ** 2)))
    out.update(peak=round(peak, 6), rms_db=round(20 * np.log10(rms + 1e-12), 2),
               crest=round(peak / (rms + 1e-12), 2), dc=round(float(np.mean(m)), 6))

    # spectrum
    win = min(8192, n if n % 2 == 0 else n - 1)
    win = max(256, win - win % 2)
    frames = np.lib.stride_tricks.sliding_window_view(m, win)[:: win // 2] * np.hanning(win)
    P = (np.abs(np.fft.rfft(frames, axis=1)) ** 2).mean(axis=0) + 1e-20
    f = np.fft.rfftfreq(win, 1.0 / sr)
    tot = float(P.sum())
    out['centroid_hz'] = round(float((f * P).sum() / tot), 1)
    out['bands'] = {k: round(float(P[(f >= lo) & (f < hi)].sum() / tot), 4)
                    for k, (lo, hi) in (('lt300', (0, 300)), ('300_3k', (300, 3000)),
                                        ('3k_7k', (3000, 7000)), ('gt7k', (7000, sr / 2 + 1)))}
    # tonal excess: the loudest peak above its local median floor (a noise floor is smooth, a whistle is not)
    from scipy.ndimage import median_filter
    floor = median_filter(P, size=101, mode='nearest') + 1e-20
    ratio = 10 * np.log10(P / floor)
    band = f > 60
    out['tonal_excess_db'] = round(float(ratio[band].max()), 1) if band.any() else 0.0
    out['tonal_hz'] = round(float(f[band][np.argmax(ratio[band])]), 1) if band.any() else 0.0

    # periodicity: is the *level* cycling? A noise texture multiplied by an LFO has almost no autocorrelation in the
    # signal (the noise decorrelates) but a strong one in its envelope, which is exactly what a listener hears as
    # "it repeats".
    k_env = max(8, sr // 400)
    env0 = np.convolve(m ** 2, np.ones(k_env) / k_env, 'same')
    d = env0 - env0.mean()
    spec = np.fft.rfft(d, 2 * n)
    ac = np.fft.irfft(np.abs(spec) ** 2)[:n]
    ac = ac / (ac[0] + 1e-12)
    lo, hi = int(LIMITS['period_lags'][0] * sr), min(int(LIMITS['period_lags'][1] * sr), n - 2)
    if hi > lo + 2:
        lo_search = lo
        # advance past zero-lag main lobe
        for i in range(lo, min(hi - 1, lo + int(0.1 * sr))):
            if ac[i] <= 0.0 or ac[i] <= ac[i + 1]:
                lo_search = i + 1
                break
        try:
            from scipy.signal import find_peaks
            peaks, props = find_peaks(ac[lo_search:hi], prominence=0.10)
            if len(peaks):
                # peaks are relative to lo_search
                best = peaks[np.argmax(props.get('prominences', ac[lo_search + peaks]))]
                lag = lo_search + int(best)
                out['periodicity'] = round(float(ac[lag]), 3)
                out['period_s'] = round(lag / sr, 4)
            else:
                out['periodicity'], out['period_s'] = 0.0, 0.0
        except Exception:
            lag = lo_search + int(np.argmax(ac[lo_search:hi])) if (hi - lo_search) > 0 else lo
            if ac[lag] > LIMITS['periodicity']:
                out['periodicity'] = round(float(ac[lag]), 3)
                out['period_s'] = round(lag / sr, 4)
            else:
                out['periodicity'], out['period_s'] = 0.0, 0.0
    else:
        out['periodicity'], out['period_s'] = 0.0, 0.0

    # onsets: rises in a short-time envelope, and how equal they are
    k = max(16, sr // 700)
    env = np.convolve(m ** 2, np.ones(k) / k, 'same') + 1e-20
    db = 10 * np.log10(env)
    rise = np.diff(db, prepend=db[0])
    peaks = [i for i in range(1, len(rise) - 1)
             if rise[i] > 1.5 and rise[i] >= rise[i - 1] and rise[i] >= rise[i + 1]]
    gaps = np.diff(peaks) / sr if len(peaks) > 1 else np.zeros(0)
    peaks = [p for p, g in zip(peaks, np.r_[gaps, 1.0]) if g > 0.001]
    amps = np.array([env[p] for p in peaks]) if peaks else np.zeros(0)
    out['onsets'] = int(len(peaks))
    out['transient_cv'] = round(float(amps.std() / (amps.mean() + 1e-20)), 3) if amps.size >= 2 else None
    out['event_rate'] = round(float(len(peaks) / (n / sr)), 1)

    from quality_gate import find_clicks
    out['clicks'] = int(len(find_clicks(m)))
    return out


def problems_for(m, kinds=(), interp='spot'):
    """[(status, check, message)] for one measured sound. All WARN/PASS: a symptom, not a verdict."""
    rows = []
    kinds = set(kinds)
    noisy = bool(kinds & set(NOISY))
    heavy = bool(kinds & set(HEAVY))

    if m['dc'] is not None and abs(m['dc']) > LIMITS['dc']:
        rows.append(('WARN', 'sfx_eval', f'DC offset {m["dc"]:+.5f} (limit {LIMITS["dc"]})'))
    if m['peak'] > LIMITS['peak']:
        rows.append(('WARN', 'sfx_eval', f'peak {m["peak"]:.3f} is at or over full scale'))

    if noisy and m.get('tonal_excess_db', 0) > LIMITS['tonal_excess_db']:
        rows.append(('WARN', 'sfx_eval',
                     f'a tonal component at {m.get("tonal_hz", 0):.0f} Hz stands {m["tonal_excess_db"]:.0f} dB above its '
                     f'local spectral floor in a noisy event (limit {LIMITS["tonal_excess_db"]:.0f} dB)'))

    if m.get('periodicity', 0) > LIMITS['periodicity']:
        rows.append(('WARN', 'sfx_eval',
                     f'repeats every {m.get("period_s", 0):.3f} s (autocorrelation {m["periodicity"]:.2f}, limit '
                     f'{LIMITS["periodicity"]})'))

    cv = m.get('transient_cv')
    if m.get('onsets', 0) >= 6 and cv is not None and cv < LIMITS['transient_cv']:
        rows.append(('WARN', 'sfx_eval',
                     f'{m["onsets"]} transients with variation {cv:.3f}: every event is the same size '
                     f'(limit {LIMITS["transient_cv"]})'))

    if m.get('bands', {}).get('gt7k', 0) > LIMITS['hf_share']:
        rows.append(('WARN', 'sfx_eval', f'{m["bands"]["gt7k"]:.0%} of the energy is above 7 kHz: a hiss wall'))

    if heavy and m.get('bands', {}).get('lt300', 1) < LIMITS['lf_share']:
        rows.append(('WARN', 'sfx_eval',
                     f'only {m["bands"]["lt300"]:.1%} of the energy is below 300 Hz for a heavy contact: no structural weight'))

    if abs(m['peak'] - LIMITS['legacy_peak']) < 2e-3 and m['crest'] < LIMITS['low_crest']:
        rows.append(('WARN', 'sfx_eval',
                     f'peak sits at {LIMITS["legacy_peak"]} with crest {m["crest"]:.1f}: looks peak-normalized, which '
                     f'flattens intensity (use calibration.normalize "energy")'))

    if m.get('clicks', 0) and not (kinds & {'granular', 'fracture', 'impact', 'repeated_impact'}):
        rows.append(('WARN', 'sfx_eval', f'{m["clicks"]} isolated click(s) in a sound that should be continuous'))
    return rows


def evaluate(x, kinds=(), sr=SR):
    """(metrics, rows) for one rendered sound."""
    m = metrics(x, sr)
    return m, problems_for(m, kinds)


# ------------------------------------------------------------------------------------------------ gate integration
def _kinds_of(cfg):
    """Which physical interactions a preset names, so the checks can be kind-aware."""
    kinds = set()
    scene = (cfg or {}).get('scene') or {}
    for act in scene.get('timeline') or []:
        if isinstance(act, dict) and act.get('interaction'):
            kinds.add(act['interaction'])
    if (cfg or {}).get('generator') in ('footstep',):
        kinds.add('gait')
    if (cfg or {}).get('generator') in ('glass_break', 'impact', 'boom', 'hit', 'explosion'):
        kinds.add('impact')
    return kinds


def gate_rows(score, stems, project=None, sr=SR):
    """Rows for every `sfx:`/`env:` track that has a stem. WARN and PASS only; never blocks a piece."""
    rows = []
    if not stems:
        return rows
    try:
        import presets
    except Exception:
        return rows
    for tr in score.get('tracks', []):
        raw = str(tr.get('instrument', ''))
        name = tr.get('name')
        kind = 'sfx' if raw.startswith('sfx:') else 'environments' if raw.startswith('env:') else None
        if kind is None or name not in stems or stems[name] is None:
            continue
        stem = stems[name]
        if not isinstance(stem, np.ndarray) or stem.size < 4096:
            continue
        cfg = presets.exact(kind, raw.split(':', 1)[1]) or {}
        kind_set = _kinds_of(cfg)
        m = metrics(stem, sr)
        found = problems_for(m, kind_set)
        if found:
            rows += [(s, 'sfx_eval', f'track "{name}": {msg}') for s, _, msg in found]
        else:
            rows.append(('PASS', 'sfx_eval',
                         f'track "{name}": no tonal excess, no cycle, transients vary, '
                         f'centroid {m.get("centroid_hz", 0):.0f} Hz, crest {m["crest"]:.1f}'))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('audio')
    ap.add_argument('--kind', default='', help='comma list: ' + ', '.join(NOISY + HEAVY + ('tonal',)))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    import soundfile as sf
    x, sr = sf.read(a.audio, always_2d=True, dtype='float64')
    kinds = [k.strip() for k in a.kind.split(',') if k.strip()]
    m, rows = evaluate(x, kinds, sr)
    if a.json:
        print(json.dumps(dict(metrics=m, rows=rows), indent=2))
        return 0
    print(f'{a.audio}  {m["seconds"]} s, peak {m["peak"]}, crest {m["crest"]}, centroid {m.get("centroid_hz", 0):.0f} Hz, '
          f'onsets {m.get("onsets", 0)}, periodicity {m.get("periodicity", 0)}')
    for status, check, msg in rows:
        print(f'{status:5s} {msg}')
    if not rows:
        print('PASS  nothing flagged')
    return 0


if __name__ == '__main__':
    sys.exit(main())
