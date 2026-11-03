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
"""mix_diagnostics.py - what a mix engineer would write down after listening to the measurements.

It reports; it never changes the mix. Every row is (level, name, detail):

  FAIL  a critical technical error (phase, clipping, a stem that is not there)
  WARN  a potential mix problem, with the stems and the frequency regions that cause it
  INFO  an observation about an artistic choice, or an optional improvement

Called by `mixer.mix_and_master(..., diagnose=True)`, `mixer.py --diagnose` and the quality gate (as
non-blocking rows). Numeric evidence only: no row is emitted from a rule of thumb that was not measured
on these stems.
"""
import numpy as np

import dsp
import mix_schema

BANDS = ((20, 120, 'sub'), (120, 400, 'low-mid'), (400, 1200, 'mid'), (1200, 4000, 'presence'),
         (4000, 8000, 'brilliance'), (8000, 16000, 'air'))
# Ranges the rows need that are not one of the six report bands. Measured from the same spectrogram.
EXTRA_BANDS = ((120, 1000, 'low120-1000'), (1000, 4000, 'speech'))
_ALL_BANDS = BANDS + EXTRA_BANDS


def _thr(mix, key):
    """An advisory threshold from the piece's mix preset (`diagnostics`), else the schema default."""
    sec = (mix or {}).get('diagnostics') or {}
    return float(sec.get(key, mix_schema.DEFAULTS['diagnostics'][key]))


def analyse(score, stems, mix=None, master=None, sr=44100):
    """[(level, name, detail)] for this mix. `stems` is what the mix actually plays (post-EQ/pan)."""
    rows = []
    if not stems:
        return [('FAIL', 'stems', 'no stems to analyse')]
    mix = mix or {}
    roles = {t.get('name'): t.get('role', 'chord') for t in (score or {}).get('tracks', [])}
    for name in stems:
        roles.setdefault(name, 'chord')
    n = max(len(v) for v in stems.values())

    # One spectrogram per stem for every band question below (see dsp.band_powers).
    bands = {name: dsp.band_powers(v, sr, _ALL_BANDS) for name, v in stems.items()}
    rows += _missing(score, stems)
    rows += _phase(stems, roles)
    rows += _levels(stems, roles, sr, mix)
    rows += _spectral(stems, roles, sr, mix, bands)
    rows += _masking(stems, roles, sr, mix, bands)
    rows += _transients(stems, roles, sr, mix)
    rows += _low_end(stems, roles, sr, mix, bands)
    rows += _dynamics(stems, roles, mix)
    rows += _space(stems, roles, mix)
    rows += _speech(stems, roles, sr, mix, bands)
    rows += _master(master, mix)
    return rows


# ---------------------------------------------------------------------------------------------

def _missing(score, stems):
    out = []
    silent = [n for n, v in stems.items() if float(np.abs(v).max()) < 1e-6]
    if silent:
        out.append(('FAIL', 'silent stems', f'{", ".join(silent)} carry no signal after processing; '
                                           f'check the preset (eq/comp/gain) before the master'))
    empty = [t.get('name') for t in (score or {}).get('tracks', []) if t.get('name') and not t.get('notes')]
    if empty:
        out.append(('INFO', 'empty tracks', f'{", ".join(map(str, empty))} have no notes; a silent track '
                                             f'still costs a reverb send'))
    return out


def _phase(stems, roles):
    worst = min(stems, key=lambda n: dsp.correlation(stems[n]))
    c = dsp.correlation(stems[worst])
    side = dsp.side_mid_db(stems[worst])
    fold = dsp.mono_fold_db(stems[worst])
    if c < -0.2 and fold < -3.0:
        return [('FAIL', 'phase', f'"{worst}" is {c:+.2f} correlated between channels: it cancels in mono '
                                  f'(fold costs {fold:+.1f} dB). Check the width/pan and any delay in its chain')]
    if c < -0.2 and fold >= -3.0:
        return [('WARN', 'phase', f'"{worst}" shows negative inter-channel correlation ({c:+.2f}) with limited mono fold loss '
                                  f'({fold:+.1f} dB); likely binaural/HRTF ITD dispersion, not a phase flip')]
    if fold < -3.0:
        return [('WARN', 'mono fold', f'"{worst}" loses {fold:.1f} dB in a mono fold-down (side/mid {side:+.1f} dB, '
                                      f'correlation {c:+.2f}); soften the width before delivery')]
    return [('PASS', 'phase', f'every stem stays mono-compatible; worst fold {fold:+.1f} dB on "{worst}" '
                              f'(correlation {c:+.2f})')]


def _levels(stems, roles, sr, mix=None):
    out = []
    lv = {}
    for n, v in stems.items():
        a = dsp.to_2d(v)
        if len(a) < int(0.5 * sr):
            lv[n] = dsp.rms_db(a)
            continue
        env = dsp.envelope(a, sr, 50, 400)
        if len(env):
            thr = max(float(env.max()) * (10.0 ** (-30.0 / 20.0)), 10.0 ** (-70.0 / 20.0))
        else:
            thr = 10 ** (-55 / 20.0)
        sel = a[env > thr] if len(env) == len(a) else a
        lv[n] = dsp.rms_db(sel if len(sel) else a)
    med = float(np.median(list(lv.values())))
    envs = [n for n in lv if roles.get(n) == 'environment']
    spread = max(lv.values()) - min(lv.values())
    if spread > _thr(mix, 'stem_spread_db'):
        loud = max(lv, key=lv.get)
        quiet = min(lv, key=lv.get)
        out.append(('WARN', 'loudness imbalance',
                    f'{spread:.0f} dB between stems: "{loud}" {lv[loud]:.1f} dB against "{quiet}" '
                    f'{lv[quiet]:.1f} dB (median {med:.1f}). That is usually a level, not an EQ, problem'))
    else:
        out.append(('PASS', 'loudness imbalance', f'stems span {spread:.0f} dB around a median of {med:.1f} dB'))
    for n in envs:
        if lv[n] > med + _thr(mix, 'env_over_median_db'):
            out.append(('WARN', 'environment masking',
                        f'"{n}" sits {lv[n] - med:+.1f} dB above the median stem; an ambience above the '
                        f'music masks it instead of supporting it'))
            break
    return out


def _spectral(stems, roles, sr, mix=None, bands=None):
    total = {b[2]: 0.0 for b in BANDS}
    for n, v in stems.items():
        for lo, hi, tag in BANDS:
            db = bands[n][tag] if bands else dsp.band_db(v, sr, lo, hi)
            total[tag] += 10 ** (db / 10.0)
    power = {k: 10 * np.log10(p + 1e-12) for k, p in total.items()}
    lo = power['low-mid']
    mid = power['mid']
    pres = power['presence']
    out = []
    mud = 10 * np.log10(10 ** (power['sub'] / 10) + 10 ** (lo / 10) + 1e-12) - \
          10 * np.log10(10 ** (power['mid'] / 10) + 10 ** (pres / 10) + 1e-12)
    if mud > _thr(mix, 'mud_db'):
        who = _band_leader(stems, sr, 120, 400, bands)
        out.append(('WARN', 'mud', f'energy below 400 Hz is {mud:+.1f} dB over 400 Hz-4 kHz; '
                                   f'"{who}" contributes most. A cut near 250-350 Hz or a higher high-pass is the usual fix'))
    else:
        out.append(('PASS', 'mud', f'low end sits {mud:+.1f} dB against the mids'))
    harsh = pres - mid
    if harsh > _thr(mix, 'harsh_db'):
        who = _band_leader(stems, sr, 1200, 4000, bands)
        out.append(('WARN', 'harshness', f'1.2-4 kHz is {harsh:+.1f} dB over 400-1200 Hz; "{who}" is the '
                                         f'source. Check its presence boost or low-pass'))
    elif pres < mid - _thr(mix, 'dull_db'):
        out.append(('INFO', 'dull top', f'1.2-4 kHz is {harsh:+.1f} dB under the mids: the mix may read as dark '
                                        f'or distant; that can be deliberate'))
    return out


def _band_leader(stems, sr, lo, hi, bands=None):
    tag = next((t for l, h, t in BANDS if l == lo and h == hi), None)
    if bands and tag:
        return max(bands, key=lambda n: bands[n][tag])
    return max(stems, key=lambda n: dsp.band_db(stems[n], sr, lo, hi))


def _masking(stems, roles, sr, mix=None, bands=None):
    """Spectral overlap: two stems within 4 dB in three or more bands is a real collision."""
    out = []
    names = [n for n in stems if len(stems[n])]
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            close = []
            for lo, hi, tag in BANDS:
                if bands:
                    da, db = bands[a][tag], bands[b][tag]
                else:
                    da, db = dsp.band_db(stems[a], sr, lo, hi), dsp.band_db(stems[b], sr, lo, hi)
                if abs(da - db) < _thr(mix, 'overlap_db'):
                    close.append(tag)
            if len(close) >= int(_thr(mix, 'overlap_bands')):
                pairs.append((a, b, close))
    for a, b, close in pairs[:3]:
        out.append(('WARN', 'spectral overlap',
                    f'"{a}" and "{b}" overlap within 4 dB in {", ".join(close)}; separate them with level, '
                    f'pan or a complementary EQ rather than more compression'))
    if not pairs:
        out.append(('PASS', 'spectral overlap', 'no two stems share three bands within 4 dB'))
    return out


def _transients(stems, roles, sr, mix=None):
    lead = next((n for n in stems if roles.get(n) == 'melody'), None)
    if lead is None:
        return []
    bed = [n for n in stems if roles.get(n) in ('pad', 'chord', 'environment', 'arp') and n != lead]
    if not bed:
        return []
    e_lead = dsp.envelope(stems[lead], sr, 2, 60)
    e_bed = dsp.envelope(np.sum([stems[n] for n in bed], axis=0), sr, 2, 60)
    thr = 10 ** (-26 / 20.0)
    attacks = np.flatnonzero((e_lead > thr) & (np.diff(np.concatenate([[0.0], e_lead])) > 0))
    if len(attacks) < 4:
        return []
    win = int(0.02 * sr)
    masked = 0
    for a in attacks:
        lo, hi = max(0, a - win), min(len(e_bed), a + win)
        if hi > lo and e_bed[lo:hi].max() > e_lead[a] * 1.4:
            masked += 1
    frac = masked / len(attacks)
    if frac > 0.5:
        return [('WARN', 'transient masking',
                 f'{frac * 100:.0f}% of the lead\'s {len(attacks)} attacks land under a louder bed: '
                 f'the articulation is being covered, not the melody')]
    return [('PASS', 'transient masking', f'the lead\'s attacks stay clear ({frac * 100:.0f}% covered)')]


def _low_end(stems, roles, sr, mix=None, bands=None):
    def _db(n, lo, hi, tag):
        return bands[n][tag] if bands else dsp.band_db(stems[n], sr, lo, hi)
    if not stems:
        return [('PASS', 'low-end congestion', '0 stem(s) own the region below 120 Hz')]
    max_sub_all = max((_db(n, 20, 120, 'sub') for n in stems), default=-120.0)
    low = []
    for n in stems:
        sub_db = _db(n, 20, 120, 'sub')
        own_max = -120.0
        for lo, hi, tag in _ALL_BANDS:
            own_max = max(own_max, _db(n, lo, hi, tag))
        if sub_db >= (own_max - 6.0) and sub_db >= (max_sub_all - 15.0):
            low.append(n)
    if len(low) > 2:
        return [('WARN', 'low-end congestion',
                 f'{len(low)} stems carry their weight below 120 Hz ({", ".join(low)}): one owner for the sub, '
                 f'the rest high-passed, is clearer and uses less headroom')]
    return [('PASS', 'low-end congestion', f'{len(low)} stem(s) own the region below 120 Hz')]


def _dynamics(stems, roles, mix=None):
    out = []
    for n, v in stems.items():
        c = dsp.crest_db(v)
        if roles.get(n) in ('drum', 'fx') and c < _thr(mix, 'drum_crest_min_db'):
            out.append(('WARN', 'over-compression',
                        f'"{n}" has a crest factor of {c:.1f} dB: a percussive stem should keep 8-15 dB. '
                        f'Lower its compression ratio or raise its threshold'))
        elif roles.get(n) in ('melody', 'pad', 'environment') and c < _thr(mix, 'crest_min_db'):
            out.append(('WARN', 'over-compression',
                        f'"{n}" ({roles.get(n)}) has {c:.1f} dB of crest: the performance is being held still'))
    if not out:
        out.append(('PASS', 'over-compression', 'every stem keeps a musical crest factor'))
    return out


def _space(stems, roles, mix):
    """Reverb send decisions, not reverb measurements: a tail that outweighs the dry signal is a warning."""
    sends = {}
    for n in stems:
        sends[n] = float(((mix.get('space') or {}).get('auto_env_blend') or {}).get(roles.get(n), 0.0) or 0.0)
    wet = sum(1 for n in stems if roles.get(n) not in ('bass', 'drum'))
    if mix.get('space') and (mix['space'].get('auto_env_blend') or {}).get('enabled') and wet > _thr(mix, 'env_wet_db'):
        return [('INFO', 'reverb buildup',
                 f'{wet} stems route to the shared room; if the mix reads as washy, lower the return '
                 f'(mix.reverb_return) before shortening the room')]
    return []


def _speech(stems, roles, sr, mix=None, bands=None):
    """Lead intelligibility: the 1-4 kHz band of the lead against every bed, per second."""
    lead = next((n for n in stems if roles.get(n) in ('melody', 'counter')), None)
    beds = [n for n in stems if roles.get(n) in ('pad', 'chord', 'arp', 'environment')]
    if lead is None or not beds:
        return []

    def _db(n, lo, hi, tag):
        return bands[n][tag] if bands else dsp.band_db(stems[n], sr, lo, hi)
    l = _db(lead, 1000, 4000, 'speech')
    b = 10 * np.log10(sum(10 ** (_db(n, 1000, 4000, 'speech') / 10) for n in beds) + 1e-12)
    if l - b < _thr(mix, 'lead_over_beds_db'):
        return [('WARN', 'intelligibility',
                 f'the lead sits {l - b:+.1f} dB against the beds in 1-4 kHz: words and articulation will be '
                 f'covered. Carve the beds there or lift the lead')]
    return [('PASS', 'intelligibility', f'the lead is {l - b:+.1f} dB over the beds in 1-4 kHz')]


def _master(master, mix):
    out = []
    if not master:
        return out
    tp = master.get('true_peak', -120.0)
    ceiling = master.get('ceiling', -1.0)
    if tp > ceiling + 0.05:
        out.append(('FAIL', 'true peak', f'{tp:.2f} dBTP over the {ceiling} ceiling'))
    if master.get('sample_peak', -120.0) > -0.05:
        out.append(('FAIL', 'clipping', f'sample peak {master["sample_peak"]:.2f} dBFS: the export is at full scale'))
    lra = master.get('lra', 0.0)
    target_lra = (mix.get('mastering') or {}).get('lra_target_lu')
    if target_lra is not None and lra < float(target_lra) - 1.0:
        out.append(('WARN', 'loudness range', f'LRA is {lra:.1f} LU against a {target_lra} LU target: the master '
                                              f'is flatter than this delivery asks for'))
    if master.get('limited_by_ceiling'):
        out.append(('INFO', 'headroom', 'the true-peak safety trimmed the master after limiting: the loudness '
                                        'target could not be met at this ceiling'))
    if out:
        return out
    return [('PASS', 'headroom', f'{tp:.2f} dBTP, LRA {lra:.1f} LU, crest {master.get("crest", 0):.1f} dB')]


def selftest():
    """Positive and negative controls: a clean pair passes; mud, harshness and a phase flip are caught."""
    sr, n = 44100, 44100
    t = np.arange(n) / sr
    tone = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    score = {'tracks': [{'name': 'pad', 'role': 'pad'}, {'name': 'lead', 'role': 'melody'}]}
    clean = {'pad': np.stack([tone, tone], 1), 'lead': np.stack([0.4 * tone, 0.4 * tone], 1)}
    rows = analyse(score, clean)
    assert not [r for r in rows if r[0] == 'FAIL'], rows
    mud = (0.5 * np.sin(2 * np.pi * 60 * t)).astype(np.float32)
    rows = analyse({'tracks': [{'name': 'pad', 'role': 'pad'}]}, {'pad': np.stack([mud, mud], 1)})
    assert any(r[0] == 'WARN' and r[1] == 'mud' for r in rows), rows
    harsh = (0.3 * np.sin(2 * np.pi * 2500 * t)).astype(np.float32)
    rows = analyse({'tracks': [{'name': 'pad', 'role': 'pad'}]}, {'pad': np.stack([harsh, harsh], 1)})
    assert any(r[0] == 'WARN' and r[1] == 'harshness' for r in rows), rows
    rows = analyse({'tracks': [{'name': 'pad', 'role': 'pad'}]}, {'pad': np.stack([tone, -tone], 1)})
    assert any(r[0] == 'FAIL' and r[1] == 'phase' for r in rows), rows
    print('selftest passed: clean passes; mud, harshness and a phase flip each fire their own row')


if __name__ == '__main__':
    selftest()
