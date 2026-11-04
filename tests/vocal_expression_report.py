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

"""A/B measurement of the phrase performance shaping.

Baseline = `phrasing.amount = 0`: the phrase engine exactly as it behaved before this change (one static
arc, no accents, no micro-timing, no articulation glide, time-locked ensemble inhales).
Expressive = the defaults in references/data/vocal-engine-data/defaults.json.

Everything here is measured from the same renders: the contour correlation between the first and last phrase
of a line, the micro-timing distribution, accents, vibrato depth by note length, formant articulation,
the ensemble's inhale spread, and the level/intonation the mix and the gate depend on. It writes
`tests/artifacts/vocals/expr/` (loudness-matched WAVs + REPORT.md) and prints the table.

    .venv/Scripts/python.exe tests/vocal_expression_report.py
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'scripts')]
from vocal_engine import context, data, ensemble, performance as pf  # noqa: E402

SR = 44100
OUT = os.path.join(HERE, 'artifacts', 'vocals', 'expr')
MEL = [dict(t=0.0, dur=1.2, p=62, v=70), dict(t=1.2, dur=1.2, p=65, v=76), dict(t=2.4, dur=0.8, p=64, v=80),
       dict(t=3.2, dur=1.6, p=62, v=88), dict(t=5.2, dur=1.0, p=60, v=70), dict(t=6.2, dur=1.0, p=62, v=78),
       dict(t=7.2, dur=2.4, p=57, v=66)]


def _cfg(amount, expression='', hum=False):
    c = data.defaults()
    c['phrasing']['amount'] = float(amount)
    c['ensemble'].update(voices=1, expression=expression or '', diversity=1.0)
    if hum:
        c['hum'] = True
    return c


def _resample(x, n=128):
    x = np.asarray(x, dtype=float)
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(x)), x)


def _phrases(cfg, events=MEL, hum=False):
    piece = context.analyse(events, cfg)
    out = []
    for li, line in enumerate(pf.split_lines([dict(e, vowel=e.get('vowel', 'm' if hum else 'a')) for e in events])):
        phs = pf.split_phrases(line, cfg, default_hum=hum)
        for i, ph in enumerate(phs):
            r = pf.render_phrase(ph, SR, np.random.default_rng([7, li, i]), cfg, hum=hum,
                                 ctx=context.phrase_context(ph, piece, cfg, i, len(phs)))
            out.append((r, ph))
    return out


def _vib_metrics(cfg):
    """Vibrato onset on a short note and extent on a long one: the engine should not leave a short note plain
    and should not make a long note scream. Two separate numbers, so neither hides the other."""
    r = pf.render_phrase([dict(t=0.0, dur=0.35, p=60, v=80), dict(t=0.5, dur=3.0, p=60, v=80)],
                         SR, np.random.default_rng(5), cfg)
    cs = 1200 * np.log2(np.maximum(r['f0'], 1e-6) / 440.0)
    seg = cs[:int(0.35 * SR)]
    seg = seg - np.median(seg)
    win = max(8, int(0.06 * SR))
    starts = list(range(0, max(1, len(seg) - win), win)) + [max(0, len(seg) - win)]
    dev = np.array([np.ptp(seg[i:i + win]) for i in starts])
    onset = float(np.argmax(dev > 10.0) * win / SR) if np.any(dev > 10.0) else float('nan')
    longseg = cs[int(2.2 * SR):int(3.2 * SR)]
    return onset, float((np.percentile(longseg, 97.5) - np.percentile(longseg, 2.5)) / 2)


def _pitch_error(phrases):
    """Median realised pitch against the score inside each note (vibrato averages out): the honest intonation
    number, independent of where a level window happens to land."""
    errs = []
    for r, notes in phrases:
        for i, e in enumerate(notes):
            a = r['s'][i] + int(0.40 * (r['e'][i] - r['s'][i]))
            b = r['s'][i] + int(0.65 * (r['e'][i] - r['s'][i]))
            if b > a + 64:
                errs.append(float(np.median(1200 * np.log2(np.maximum(r['f0'][a:b], 1e-6) / 440.0)) - 100.0 * (e['p'] - 69)))
    return float(np.mean(np.abs(errs))) if errs else 0.0


def _formant_onset(cfg):
    r = pf.render_phrase([dict(t=0.0, dur=2.5, p=62, v=80)], SR, np.random.default_rng(6), cfg)
    F = np.asarray(r['formants'])
    if F.ndim == 1:
        return 0.0
    return float(np.max(np.abs(F[:, int(0.01 * SR)] - F[:, int(1.5 * SR)])))


def _mix(cfg, events=MEL, hum=False, voices=1):
    cfg['ensemble']['voices'] = voices
    return ensemble.render(events, SR, cfg, seed=4, hum=hum, stems=True)


def _lufs(y):
    """Rough loudness proxy (RMS, K-weighting skipped): used only to confirm the A/B is level matched."""
    return 20 * np.log10(np.sqrt(np.mean(np.asarray(y, dtype=float) ** 2)) + 1e-12)


def _corr(a, b):
    n = min(len(a), len(b))
    a, b = np.asarray(a[:n], float), np.asarray(b[:n], float)
    if a.ndim > 1:
        a, b = a.mean(axis=1), b.mean(axis=1)
    return float(np.corrcoef(a, b)[0, 1])


def measure(amount):
    """Every number for one engine setting. One render per scenario; no number is reused across settings."""
    cfg = _cfg(amount)
    ph = _phrases(cfg)
    arc = [_resample(r['arc_db']) for r, _ in ph]
    tim = np.concatenate([np.asarray(r['timing_ms']) for r, _ in ph])
    acc = [float(np.max(np.abs(r['accents_db']))) for r, _ in ph]
    vib_onset, vib_extent = _vib_metrics(cfg)
    solo, info1 = _mix(cfg, voices=1)
    choir_cfg = _cfg(amount, hum=True)
    choir, info5 = _mix(choir_cfg, hum=True, voices=5)
    mel_cfg = _cfg(amount, expression='melancholic', hum=True)
    exp, info_m = _mix(mel_cfg, hum=True, voices=1)
    return dict(
        arc_corr=float(np.corrcoef(arc[0], arc[-1])[0, 1]) if len(arc) > 1 else 1.0,
        contours=sorted({r['contour'] for r, _ in ph}),
        timing_std_ms=float(np.std(tim)), timing_max_ms=float(np.max(np.abs(tim))),
        accent_db=float(np.mean(acc)), accent_range_db=float(np.max(acc) - np.min(acc)),
        vib_onset_short_s=vib_onset, vib_extent_long_cents=vib_extent,
        pitch_error_cents=_pitch_error(ph), formant_onset_hz=_formant_onset(cfg),
        inhale_spread_ms=info5['report']['phrasing']['inhale_spread_ms'],
        inhale_spread_baseline_ms=info1['report']['phrasing']['inhale_spread_ms'],
        intonation_cents=float(info1['report']['mean_abs_dev_cents']),
        countours_used=len(ph),
        rms_solo_db=_lufs(solo), rms_choir_db=_lufs(choir),
        peak=float(np.max(np.abs(solo))), finite=bool(np.isfinite(solo).all() and np.isfinite(choir).all()),
        phrasing_report=info1['report']['phrasing'],
        audio=dict(solo=solo, choir=choir, expressive=exp))


def _write_wav(path, y):
    import soundfile as sf
    sf.write(path, np.asarray(y, dtype=np.float32), SR, subtype='FLOAT')


def main():
    os.makedirs(OUT, exist_ok=True)
    base, new = measure(0.0), measure(1.0)
    gain = 10 ** ((base['rms_solo_db'] - new['rms_solo_db']) / 20)
    for tag, d in (('baseline', base), ('expressive', new)):
        g = 1.0 if tag == 'baseline' else gain
        for kind in ('solo', 'choir', 'expressive'):
            _write_wav(os.path.join(OUT, f'{tag}_{kind}.wav'), np.asarray(d['audio'][kind]) * g)

    rows = [('contour correlation, first vs last phrase', base['arc_corr'], new['arc_corr'], 'lower = less repetitive'),
            ('distinct contours in the line', len(base['contours']), len(new['contours']), ''),
            ('micro-timing std (ms)', base['timing_std_ms'], new['timing_std_ms'], '0 = perfectly on the grid'),
            ('micro-timing max (ms)', base['timing_max_ms'], new['timing_max_ms'], ''),
            ('accent depth (dB)', base['accent_db'], new['accent_db'], 'peak accent over the phrase'),
            ('vibrato onset on a 0.35 s note (s)', base['vib_onset_short_s'], new['vib_onset_short_s'], 'nan = no vibrato at all'),
            ('vibrato extent on a 3 s note (cents)', base['vib_extent_long_cents'], new['vib_extent_long_cents'], ''),
            ('pitch error vs score (mean cents)', base['pitch_error_cents'], new['pitch_error_cents'], 'median inside each note'),
            ('formant onset movement (Hz)', base['formant_onset_hz'], new['formant_onset_hz'], '0 = frozen filter'),
            ('choir inhale spread (ms)', 0.0 if base['inhale_spread_ms'] is None else base['inhale_spread_ms'],
             new['inhale_spread_ms'], '0 = the whole choir gasps together'),
            ('ensemble intonation (mean cents)', base['intonation_cents'], new['intonation_cents'], 'gate limit 60'),
            ('solo RMS (dBFS)', base['rms_solo_db'], new['rms_solo_db'], 'level match'),
            ('A/B waveform correlation (solo)', 1.0, _corr(base['audio']['solo'], new['audio']['solo']), '1.0 = no change'),
            ('A/B waveform correlation (choir)', 1.0, _corr(base['audio']['choir'], new['audio']['choir']), '')]
    print(f'\n{"metric":42s} {"baseline":>10s} {"expressive":>11s}   note')
    for name, a, b, note in rows:
        print(f'{name:42s} {a:10.3f} {b:11.3f}   {note}')

    checks = [('finite audio', base['finite'] and new['finite']),
              ('no clipping above full scale', max(base['peak'], new['peak']) <= 1.0),
              ('micro-timing inside 60 ms', new['timing_max_ms'] < 60.0),
              ('intonation inside the gate limit', new['intonation_cents'] <= 60.0),
              ('level within 0.5 dB of baseline', abs(new['rms_solo_db'] - base['rms_solo_db']) <= 0.5),
              ('choir breaths are not time-locked', (new['inhale_spread_ms'] or 0) >= 4.0),
              ('the setting actually changes the audio', _corr(base['audio']['solo'], new['audio']['solo']) < 0.995)]
    print('\n' + '\n'.join(f'{"PASS" if ok else "FAIL"}  {name}' for name, ok in checks))

    md = ['# Vocal phrase performance: A/B measurements', '',
          'Baseline = `phrasing.amount = 0` (the previous phrase behaviour). Expressive = shipped defaults.',
          'Both were rendered from the same notes with the same seeds; the expressive mix is level matched.',
          '', '| metric | baseline | expressive | note |', '|---|---|---|---|']
    md += [f'| {n} | {a:.3f} | {b:.3f} | {note} |' for n, a, b, note in rows]
    md += ['', '| check | result |', '|---|---|'] + [f'| {n} | {"PASS" if ok else "FAIL"} |' for n, ok in checks]
    md += ['', 'Not checked: how any of it sounds. These are measurements of timing, level, vibrato extent,',
           'formant movement and breath timing, not of musicality. The WAVs beside this file are for listening.']
    with open(os.path.join(OUT, 'REPORT.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(md) + '\n')
    with open(os.path.join(OUT, 'measurements.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(baseline={k: v for k, v in base.items() if k != 'audio'},
                       expressive={k: v for k, v in new.items() if k != 'audio'}), f, indent=2, default=str)
    print(f'\nwrote {OUT}')
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
