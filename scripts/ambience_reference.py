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
"""ambience_reference.py - measure a REAL recording once, then check our synthetic ambience against it.

    python3 scripts/ambience_reference.py measure rain_roof.wav --slug rain_roof --project <dir> [--source URL] [--licence TEXT]
    python3 scripts/ambience_reference.py compare out/stems/rain.wav rain_roof --project <dir>

`measure` writes <project>/reference/<slug>.json. Several recordings of the same sound go in one file (run it again with the same
--slug: the new measurement is added). Only these numbers are kept, never the audio, so the licence of a recording does not
travel with the project. All numbers are taken at the same peak level, so loudness plays no part.

Metrics (mono mix, 4096-sample Hann frames): spectral centroid, 90 % rolloff, energy share in <300 Hz, 300-3 kHz, 3-7 kHz,
>7 kHz, a rough event rate (short-time energy rises of 3 dB or more, per second) and crest factor.
The event rate is rough and not calibrated across different sample rates; the compare step weights it low on purpose.

`compare` and the quality-gate row report the distance to each reference. This is a WARN, never a FAIL: a few
recordings can show that a render is far from real, not that it is wrong.
"""
import argparse
import json
import os
import sys

import numpy as np

PEAK = 0.9
BANDS = {'lt300': (0, 300), '300_3k': (300, 3000), '3k_7k': (3000, 7000), 'gt7k': (7000, None)}
# Tolerance: relative for centroid and rolloff, absolute share for the bands. Set wide until it has been checked
# against several real recordings of one sound (decision H); WARN only.
TOL = dict(centroid_rel=0.35, rolloff_rel=0.35, band_abs=0.20)


def _mono(x):
    x = np.asarray(x, dtype=float)
    return x.mean(axis=1) if x.ndim == 2 else x


TEX_BANDS = 12                                   # log-spaced analysis bands, 80 Hz to 10 kHz (the paper uses 32; this is a reduced set)
TEX_MOD = ((0.5, 2.0), (2.0, 8.0), (8.0, 32.0), (32.0, 128.0))      # modulation bands, Hz
TEX_ENV_SR = 400


def texture_stats(x, sr):
    """Reduced McDermott-Simoncelli texture statistics (Neuron 2011): per band the envelope moments (mean, variance/mean^2, skew,
    kurtosis), the cross-band envelope correlations C1, and the envelope power in four modulation bands. Numbers only."""
    from scipy.signal import butter, hilbert, resample_poly, sosfiltfilt
    m = _mono(x)
    m = m / (np.abs(m).max() + 1e-12) * PEAK
    edges = np.geomspace(80.0, min(10000.0, sr / 2 - 500), TEX_BANDS + 1)
    envs = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        band = sosfiltfilt(butter(3, [lo, hi], btype='band', fs=sr, output='sos'), m)
        e = np.abs(hilbert(band)) ** 0.3                                  # compressive nonlinearity on the envelope
        envs.append(resample_poly(e, TEX_ENV_SR, sr))
    E = np.array(envs)
    mu = E.mean(axis=1)
    sd = E.std(axis=1) + 1e-12
    z = (E - mu[:, None]) / sd[:, None]
    mods = []
    for k in range(TEX_BANDS):
        spec = np.abs(np.fft.rfft(E[k] - mu[k])) ** 2
        f = np.fft.rfftfreq(E.shape[1], 1 / TEX_ENV_SR)
        tot = spec.sum() + 1e-12
        mods.append([float(spec[(f >= lo) & (f < hi)].sum() / tot) for lo, hi in TEX_MOD])
    return dict(bands_hz=[float(v) for v in edges], mean=[float(v) for v in mu], var_over_mean2=[float(v) for v in (sd / mu) ** 2],
                skew=[float(v) for v in (z ** 3).mean(axis=1)], kurtosis=[float(v) for v in (z ** 4).mean(axis=1)],
                c1=np.round(np.corrcoef(E), 4).tolist(), mod_power=mods)


def texture_distance(a, b):
    """Components (0 = identical) between two texture_stats dicts: spectrum, sparsity, cross-band correlation, modulation."""
    la, lb = np.log(np.array(a['mean']) + 1e-9), np.log(np.array(b['mean']) + 1e-9)
    spectrum = float(np.abs((la - la.mean()) - (lb - lb.mean())).mean())
    sparsity = float(np.abs(np.log(np.array(a['kurtosis'])) - np.log(np.array(b['kurtosis']))).mean())
    c1 = float(np.abs(np.array(a['c1']) - np.array(b['c1'])).mean())
    mod = float(np.abs(np.array(a['mod_power']) - np.array(b['mod_power'])).mean())
    return dict(spectrum=spectrum, sparsity=sparsity, c1=c1, modulation=mod, total=(spectrum + sparsity + 2 * c1 + 2 * mod) / 6.0)


def modal_fit(x, sr, n=6, fmin=60.0):
    """Strongest resonances of a struck object: [{f_hz, t60_s, rel_db}], from the spectrum peaks and the decay of each (analysis only)."""
    from scipy.signal import butter, hilbert, sosfiltfilt
    m = _mono(x)
    m = m / (np.abs(m).max() + 1e-12)
    spec = np.abs(np.fft.rfft(m * np.hanning(len(m))))
    f = np.fft.rfftfreq(len(m), 1 / sr)
    s = spec.copy()
    s[f < fmin] = 0
    s[f > sr / 2 - 300] = 0
    top = float(s.max()) + 1e-12
    out = []
    for _ in range(n):
        i = int(np.argmax(s))
        fc = float(f[i])
        if s[i] < top * 0.01:
            break
        s[max(0, i - int(len(m) * 0.003)):i + int(len(m) * 0.003) + 1] = 0
        band = sosfiltfilt(butter(2, [fc * 0.97, min(fc * 1.03, sr / 2 - 100)], btype='band', fs=sr, output='sos'), m)
        db = 20 * np.log10(np.abs(hilbert(band)) + 1e-9)
        k = int(0.005 * sr)
        smooth = np.convolve(db, np.ones(k) / k, 'same')
        a = int(np.argmax(smooth))
        seg = smooth[a:a + int(0.8 * sr)]
        t = np.arange(len(seg)) / sr
        ok = seg > seg.max() - 40
        slope = np.polyfit(t[ok], seg[ok], 1)[0] if ok.sum() > 20 else 0.0
        out.append(dict(f_hz=round(fc, 1), t60_s=round(float(-60.0 / slope), 3) if slope < -1.0 else None,
                        rel_db=round(20 * np.log10(float(spec[i]) / top + 1e-12), 1)))
    return sorted(out, key=lambda r: r['f_hz'])


def measure_array(x, sr, texture=False):
    """The metrics of one recording, at equal peak. Raises on silence or a clip shorter than a frame."""
    m = _mono(x)
    if len(m) < 4096 * 2:
        raise ValueError('need at least about 0.2 s of audio')
    peak = np.abs(m).max()
    if peak < 1e-9:
        raise ValueError('the audio is silent')
    m = m / peak * PEAK
    win, hop = 4096, 1024
    frames = np.lib.stride_tricks.sliding_window_view(m, win)[::hop] * np.hanning(win)
    spec = (np.abs(np.fft.rfft(frames, axis=1)) ** 2).mean(axis=0)
    freqs = np.fft.rfftfreq(win, 1 / sr)
    total = spec.sum() + 1e-12
    cum = np.cumsum(spec) / total
    bands = {k: float(spec[(freqs >= lo) & (freqs < (hi if hi else sr / 2 + 1))].sum() / total) for k, (lo, hi) in BANDS.items()}
    e = np.sum(np.lib.stride_tricks.sliding_window_view(m, 128)[::64] ** 2, axis=1)
    rise = np.diff(10 * np.log10(e + 1e-12))
    res = dict(centroid_hz=float((freqs * spec).sum() / total), rolloff90_hz=float(freqs[np.searchsorted(cum, 0.90)]),
               bands=bands, events_per_s=float(np.sum(rise > 3.0) / (len(m) / sr)),
               crest=float(np.abs(m).max() / (np.sqrt(np.mean(m ** 2)) + 1e-12)), seconds=round(len(m) / sr, 2), sr=int(sr))
    if texture:
        res['texture'] = texture_stats(x, sr)
    return res


def metric_distance(render, ref):
    """One number for the fit loop: 1.0 means every spectral metric sits at its tolerance; texture statistics add to it when both have them."""
    rows = distance(render, ref)
    parts = [abs(r - f) / max(f, 1.0) / TOL['centroid_rel'] for k, r, f, _ in rows[:2]] +             [abs(r - f) / TOL['band_abs'] for k, r, f, _ in rows[2:]]
    d = float(np.mean(parts))
    if render.get('texture') and ref.get('texture'):
        d += texture_distance(render['texture'], ref['texture'])['total']
    return d


def distance(render, ref):
    """List of (metric, render value, reference value, outside_tolerance) between two metric dicts."""
    rows = []
    for key, tol in (('centroid_hz', TOL['centroid_rel']), ('rolloff90_hz', TOL['rolloff_rel'])):
        r, f = render[key], ref[key]
        rows.append((key, r, f, abs(r - f) / max(f, 1.0) > tol))
    for b in BANDS:
        r, f = render['bands'][b], ref['bands'][b]
        rows.append((f'band {b}', r, f, abs(r - f) > TOL['band_abs']))
    return rows


def ref_path(project, slug):
    return os.path.join(project, 'reference', f'{slug}.json')


def load_refs(project, slug):
    """The measurements stored for a slug, or []."""
    p = ref_path(project, slug)
    if not os.path.isfile(p):
        return []
    return json.load(open(p, encoding='utf-8')).get('recordings', [])


def measure_file(path, slug, project, source=None, licence=None, modes=0):
    import soundfile as sf
    x, sr = sf.read(path, always_2d=True)
    rec = dict(measure_array(x, sr, texture=True), file=os.path.basename(path), source=source, licence=licence)
    if modes:
        rec['modes'] = modal_fit(x, sr, modes)
    d = os.path.join(project, 'reference')
    os.makedirs(d, exist_ok=True)
    p = ref_path(project, slug)
    data = json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else dict(slug=slug, recordings=[])
    data['recordings'] = [r for r in data['recordings'] if r.get('file') != rec['file']] + [rec]
    json.dump(data, open(p, 'w', encoding='utf-8'), indent=2)
    return p, rec, len(data['recordings'])


def compare_rows(render_metrics, project, slugs):
    """Quality-gate rows (status, check, message) for one render against the references of its slugs. Never FAIL."""
    rows = []
    for slug in slugs:
        refs = load_refs(project, slug)
        if not refs:
            continue
        # judge against the nearest reference: real recordings of one sound differ, the render only has to be near one of them
        best = min((distance(render_metrics, r) for r in refs), key=lambda d: sum(o for *_, o in d))
        out = [f'{m} {r:.2f} vs {f:.2f}' for m, r, f, o in best if o]
        note = f'{len(refs)} recording(s)' + (', fewer than the two the plan asks for' if len(refs) < 2 else '')
        if out:
            rows.append(('WARN', 'ambience_reference', f'"{slug}" is outside the tolerance of the nearest real recording ({note}): ' + '; '.join(out)))
        else:
            rows.append(('PASS', 'ambience_reference', f'"{slug}" is within tolerance of a real recording ({note})'))
    return rows


def gate_rows(score, stems, project_dirs, sr=44100):
    """Called by quality_gate.run_gate. One row per env:/sfx: track whose preset lists sources with a stored measurement."""
    import presets
    rows = []
    if not stems:
        return rows
    for tr in score.get('tracks', []):
        raw = str(tr.get('instrument', ''))
        kind = 'environments' if raw.startswith('env:') else 'sfx' if raw.startswith('sfx:') else None
        if kind is None or tr.get('name') not in stems:
            continue
        cfg = presets.exact(kind, raw.split(':', 1)[1]) or {}
        slugs = [str(s).lower().strip().replace(' ', '_').replace('-', '_') for s in cfg.get('sources') or []]
        for pdir in project_dirs:
            if any(os.path.isfile(ref_path(pdir, s)) for s in slugs):
                try:
                    m = measure_array(stems[tr['name']], sr)
                except ValueError:
                    break
                rows += compare_rows(m, pdir, slugs)
                break
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['measure', 'compare'])
    ap.add_argument('audio')
    ap.add_argument('slug')
    ap.add_argument('--project', required=True)
    ap.add_argument('--source', default=None, help='measure: the URL the recording came from')
    ap.add_argument('--licence', default=None, help='measure: its licence')
    ap.add_argument('--modes', type=int, default=0, help='measure: also fit this many resonances (frequency, decay) of a struck object')
    a = ap.parse_args()
    if a.cmd == 'measure':
        p, rec, n = measure_file(a.audio, a.slug, a.project, a.source, a.licence, a.modes)
        print(f'wrote {p} ({n} recording(s)): centroid {rec["centroid_hz"]:.0f} Hz, rolloff90 {rec["rolloff90_hz"]:.0f} Hz, '
              f'bands ' + ', '.join(f'{k} {v:.2f}' for k, v in rec['bands'].items()) + f', events/s {rec["events_per_s"]:.1f} (rough)')
        if n < 2:
            print('note: one recording is a weak anchor; measure at least two of this sound')
        return
    import soundfile as sf
    x, sr = sf.read(a.audio, always_2d=True)
    m = measure_array(x, sr)
    refs = load_refs(a.project, a.slug)
    if not refs:
        sys.exit(f'no reference for "{a.slug}" in {a.project}/reference/')
    for i, r in enumerate(refs):
        print(f'-- against {r.get("file")}')
        for name, rv, fv, out in distance(m, r):
            print(f'   {name:14s} render {rv:10.2f}   real {fv:10.2f}   {"OUTSIDE" if out else "ok"}')
    for st, check, msg in compare_rows(m, a.project, [a.slug]):
        print(st, check, msg)


if __name__ == '__main__':
    main()
