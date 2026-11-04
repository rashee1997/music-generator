"""Roughness calibration fixtures: synthetic intervals, measured by both models.

    python tests/fixtures/roughness/make_fixtures.py            # calibrate + write wavs + pairs
    python tests/fixtures/roughness/make_fixtures.py --pairs    # only the 12 listening pairs

Additive synthesis only (no downloaded or copyrighted audio): a harmonic series with 1/k^1.1 partials, the
same timbre for every interval, so the only variables are interval, register, level and masking.

Outputs (git-ignored audio, committed numbers):
    wav/            the 63 calibration tones
    pairs/          the 12 A/B listening pairs
    calibration.json  every measured number, and the threshold the new model is calibrated to

The listening sheet is docs/roughness_listening_sheet.md; it deliberately does not say which member of a
pair the model scores rougher.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import naturalness_check as nc  # noqa: E402

SR = 44100
SECS = 4.0
LEVELS = {'ff': -12.0, 'mf': -24.0, 'pp': -36.0}
ROOTS = {'low': 220.0, 'mid': 523.25, 'high': 1046.5}
INTERVALS = {'unison': 0, 'm2': 1, 'M2': 2, 'm3': 3, 'M3': 4, 'tritone': 6, 'P5': 7}
WAV = os.path.join(HERE, 'wav')
PAIRS = os.path.join(HERE, 'pairs')


def tone(f, level_db, secs=SECS, partials=10):
    """One harmonic tone at level_db peak-normalised, 10 partials like the fixture timbre."""
    t = np.arange(int(SR * secs)) / SR
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.1 for k in range(1, partials + 1))
    x = x / np.max(np.abs(x))
    return x * 10 ** (level_db / 20.0)


def mix(*voices):
    x = sum(voices)
    return np.stack([x, x], 1).astype(np.float32)


def dyad(root, semis, level_db):
    return mix(tone(root, level_db), tone(root * 2 ** (semis / 12.0), level_db))


def measure(x, model):
    _, m = nc.cochlear_roughness_check(x, sr=SR, model=model)
    return m['mean_roughness'], m['max_roughness']


def shape_at(root, df_hz, level_db=-24.0):
    """Roughness of two equal sine-pairs separated by df_hz (all partials, same timbre)."""
    return measure(mix(tone(root, level_db), tone(root + df_hz, level_db)), 'level_aware')[0]


def cb_hz(f):
    """Critical bandwidth (Zwicker): 25 + 75*(1 + 1.4*(f/1000)**2)**0.69."""
    return 25.0 + 75.0 * (1.0 + 1.4 * (f / 1000.0) ** 2) ** 0.69


def calibrate():
    os.makedirs(WAV, exist_ok=True)
    rows = {}
    for reg, root in ROOTS.items():
        for name, semis in INTERVALS.items():
            for lvl, db in LEVELS.items():
                x = mix(tone(root, db)) if semis == 0 else dyad(root, semis, db)
                key = f'{reg}/{name}/{lvl}'
                sf.write(os.path.join(WAV, key.replace('/', '_') + '.wav'), x, SR, subtype='PCM_16')
                leg = measure(x, 'legacy')
                la = measure(x, 'level_aware')
                rows[key] = dict(legacy_mean=leg[0], level_aware_mean=la[0])
    # consonant voicings and semitone dyads at the same levels: the two populations the threshold sits between
    cons, semi = [], []
    for reg, root in ROOTS.items():
        for lvl, db in LEVELS.items():
            triad = mix(tone(root, db), tone(root * 2 ** (4 / 12), db), tone(root * 2 ** (7 / 12), db))
            cons.append(measure(triad, 'level_aware')[0])
            semi.append(measure(dyad(root, 1, db), 'level_aware')[0])
    calib = dict(
        rows=rows,
        consonant=sorted(cons),
        semitone=sorted(semi),
        consonant_p95=float(np.percentile(cons, 95)),
        semitone_p05=float(np.percentile(semi, 5)),
    )
    # The limit sits a margin above the loudest consonant voicing in the set (the two populations overlap at the
    # extreme register/level corner, see the note): 1.16x the 95th percentile of the consonant frames keeps every
    # consonant voicing passing while the in-file loud semitone (about 0.031-0.035) stays above it.
    calib['median'] = round(float(calib['consonant_p95']) * 1.16, 4)
    # published-shape checks
    peak = {}
    for root in (220.0, 1000.0, 2093.0):
        scan = [(df, shape_at(root, df)) for df in np.arange(2.0, cb_hz(root) * 1.5, max(1.0, cb_hz(root) / 40))]
        best = max(scan, key=lambda p: p[1])
        peak[str(int(root))] = dict(cb_hz=round(cb_hz(root), 1), peak_df=round(best[0], 1),
                                    peak_ratio_of_cb=round(best[0] / cb_hz(root), 3),
                                    at_one_cb=round(shape_at(root, cb_hz(root)), 4), peak_value=round(best[1], 4))
    calib['shape'] = peak
    # Level is only meaningful inside one file: the model calibrates against the file's own loudness, so two
    # files played at matched loudness are equal by design. One file: 4 s pp semitone, then 4 s ff semitone.
    q = np.arange(int(SR * 8.0)) / SR
    env = np.where(q < 4.0, 10 ** (LEVELS['pp'] / 20.0), 10 ** (LEVELS['ff'] / 20.0))
    lvl = (tone(262.0, 0.0, secs=8.0) + tone(277.0, 0.0, secs=8.0)) * env / 2.0
    frames = nc.cochlear_roughness_check(np.stack([lvl, lvl], 1).astype(np.float32), sr=SR, model='level_aware')[1]['frames']
    first = [v for v in frames[:3] if v is not None]
    last = [v for v in frames[-3:] if v is not None]
    calib['level_within_file'] = dict(pp_frames=first, ff_frames=last,
                                      ratio=round(float(np.mean(last)) / max(float(np.mean(first)), 1e-9), 3))
    # masking: a semitone against a masker 12 dB louder, a minor 9th above the upper note (same critical band)
    masked = mix(tone(262.0, -24.0), tone(277.0, -24.0), tone(311.0, -12.0))
    calib['masking'] = dict(unmasked=measure(dyad(262.0, 1, -24.0), 'level_aware')[0],
                            masked=measure(masked, 'level_aware')[0],
                            legacy_masked=measure(masked, 'legacy')[0],
                            legacy_unmasked=measure(dyad(262.0, 1, -24.0), 'legacy')[0])
    # unison has nothing to beat
    calib['unison'] = dict(level_aware=measure(mix(tone(440.0, -24.0)), 'level_aware')[0],
                           legacy=measure(mix(tone(440.0, -24.0)), 'legacy')[0])
    with open(os.path.join(HERE, 'calibration.json'), 'w', encoding='utf-8') as fh:
        json.dump(calib, fh, indent=2, sort_keys=True)
    return calib


def level_pair(root, semis):
    """One 8 s file, pp for the first half and ff for the second: the model calibrates against the file's own
    loudness, so a pp file and an ff file played at matched loudness are equal by design. Returns the two halves
    (for the listener) and the mother file (for the model's frame-by-frame ordering)."""
    q = np.arange(int(SR * 8.0)) / SR
    env = np.where(q < 4.0, 10 ** (LEVELS['pp'] / 20.0), 10 ** (LEVELS['ff'] / 20.0))
    mother = (tone(root, 0.0, secs=8.0) + tone(root * 2 ** (semis / 12.0), 0.0, secs=8.0)) * env / 2.0
    return (mix(mother[:int(SR * 4.0)]), mix(mother[int(SR * 4.0):]),
            np.stack([mother, mother], 1).astype(np.float32))


MOTHERS = {'01_semitone_262_pp_vs_ff': (262.0, 1), '02_semitone_523_pp_vs_ff': (523.25, 1),
           '03_semitone_1046_pp_vs_ff': (1046.5, 1), '04_M2_440_pp_vs_ff': (440.0, 2),
           '05_m3_262_pp_vs_ff': (262.0, 3), '06_P5_262_pp_vs_ff': (262.0, 7)}

PAIR_DEFS = [
    ('01_semitone_262_pp_vs_ff', lambda: level_pair(262.0, 1)[:2]),
    ('02_semitone_523_pp_vs_ff', lambda: level_pair(523.25, 1)[:2]),
    ('03_semitone_1046_pp_vs_ff', lambda: level_pair(1046.5, 1)[:2]),
    ('04_M2_440_pp_vs_ff', lambda: level_pair(440.0, 2)[:2]),
    ('05_m3_262_pp_vs_ff', lambda: level_pair(262.0, 3)[:2]),
    ('06_P5_262_pp_vs_ff', lambda: level_pair(262.0, 7)[:2]),
    ('07_semitone_low_vs_high', lambda: (dyad(220.0, 1, LEVELS['mf']), dyad(2093.0, 1, LEVELS['mf']))),
    ('08_semitone_masked_vs_unmasked',
     lambda: (dyad(262.0, 1, LEVELS['mf']),
              mix(tone(262.0, -24.0), tone(277.0, -24.0), tone(311.0, -12.0)))),
    ('09_cluster_vs_triad',
     lambda: (mix(tone(440.0, -24.0), tone(466.16, -24.0), tone(493.88, -24.0)),
              mix(tone(440.0, -24.0), tone(554.37, -24.0), tone(659.26, -24.0)))),
    ('10_semitone_bed_vs_alone',
     lambda: (dyad(262.0, 1, LEVELS['mf']),
              mix(tone(262.0, -24.0), tone(277.0, -24.0), 0.02 * np.random.default_rng(3).standard_normal(int(SR * SECS))))),
    ('11_semitone_octave_masked',
     lambda: (dyad(262.0, 1, LEVELS['mf']),
              mix(tone(262.0, -24.0), tone(277.0, -30.0), tone(262.0, -12.0)))),
    ('12_semitone_vs_tritone',
     lambda: (dyad(262.0, 1, LEVELS['mf']), dyad(262.0, 6, LEVELS['mf']))),
]


def make_pairs():
    os.makedirs(PAIRS, exist_ok=True)
    out = []
    for name, build in PAIR_DEFS:
        a, b = build()
        sf.write(os.path.join(PAIRS, name + '_A.wav'), a, SR, subtype='PCM_16')
        sf.write(os.path.join(PAIRS, name + '_B.wav'), b, SR, subtype='PCM_16')
        mother = None
        if name[3:5].isdigit() and name[6:9] in ('_pp',) or name.startswith(('01_', '02_', '03_', '04_', '05_', '06_')):
            mother_root, mother_semis = MOTHERS.get(name, (None, None))
            mother = level_pair(mother_root, mother_semis)[2] if mother_root else None
        if mother is not None:
            frames = [v for v in nc.cochlear_roughness_check(mother, sr=SR, model='level_aware')[1]['frames'] if v]
            la = [float(np.mean(frames[:3])), float(np.mean(frames[-3:]))]
        else:
            la = [measure(a, 'level_aware')[0], measure(b, 'level_aware')[0]]
        leg = [measure(a, 'legacy')[0], measure(b, 'legacy')[0]]
        out.append(dict(pair=name,
                        level_aware=[round(v, 4) for v in la],
                        expected='A' if la[0] > la[1] * 1.05 else 'B' if la[1] > la[0] * 1.05 else 'same',
                        legacy=[round(v, 4) for v in leg],
                        legacy_expected='A' if leg[0] > leg[1] * 1.05 else 'B' if leg[1] > leg[0] * 1.05 else 'same'))
    with open(os.path.join(HERE, 'pairs.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)
    return out


if __name__ == '__main__':
    if '--pairs' in sys.argv:
        for r in make_pairs():
            print(r['pair'], 'level_aware', r['level_aware'], '->', r['expected'], '| legacy ->', r['legacy_expected'])
    else:
        c = calibrate()
        print('median', c['median'], 'consonant_p95', c['consonant_p95'], 'semitone_p05', c['semitone_p05'])
        print('level', c['level_within_file'])
        print('masking', c['masking'])
        print('unison', c['unison'])
        for root, v in c['shape'].items():
            print('shape', root, v)
        for r in make_pairs():
            print(r['pair'], r['level_aware'], '->', r['expected'], '| legacy', r['legacy'], '->', r['legacy_expected'])
