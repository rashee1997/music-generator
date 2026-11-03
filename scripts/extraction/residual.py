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

"""Stage `residual`: look for what the first pass missed, add it as new voices, separate again.

After voices are cut, the harmonic part that no voice explains is listened to the same way as the song: notes are found
in it and clustered by timbre into `unknown_n` voices. A round that finds nothing, or leaves little unexplained energy,
ends the loop. The per-round energy share is reported, so a song that still has unexplained tonal energy says so."""
import numpy as np

from . import spectrum, voices as voices_mod


def unexplained_share(harm, parts):
    """Fraction of the harmonic part's energy that no voice stem accounts for."""
    resid = harm - sum(parts) if parts else harm
    return float(np.sum(resid ** 2) / (np.sum(harm ** 2) + 1e-12)), resid


def new_voices(resid, sr, tuning_cents, existing, cfg, ignored=None):
    """Notes found in the residual, clustered into voices named after the ones already present."""
    import librosa
    from . import notes as notes_mod
    r = cfg['residual']
    csr = cfg['spectrum']['cqt_sr']
    mono = librosa.resample(resid.mean(axis=0), orig_sr=sr, target_sr=csr) if sr != csr else resid.mean(axis=0)
    spec = spectrum.semitone_spectrum(mono, csr, tuning_cents, cfg)
    found, _ = notes_mod.find_notes(spec, {'voices': []}, cfg)
    found = [n for n in found if n['strength'] >= r['min_strength_rel'] * max([n2['strength'] for n2 in found] or [1.0])]
    vs, _ = voices_mod.assign(found, spec, {'voices': [], 'ignored': ignored or []}, cfg)
    start = sum(1 for k in existing if k.startswith('unknown_'))
    out = {}
    for j, v in enumerate(vs.values(), 1):
        heard = [n['midi'] for n in v['notes']]
        v = {**v, 'id': f'unknown_{start + j}', 'declared': False, 'range': [min(heard), max(heard)]}   # the whole span it was heard in is tried
        out[v['id']] = v
    return out


def rounds(y, sr, voices, spec, tuning_cents, cfg, separate_fn, first=None, ignored=None):
    """Run separation, then up to `max_rounds` more while new voices turn up. Returns (result, voices, log)."""
    r = cfg['residual']
    res = first or separate_fn(y, sr, voices, spec, tuning_cents, cfg)
    share, resid = unexplained_share(res['harm'], list(res['voices'].values()))
    log = [{'round': 0, 'unexplained_pct': round(100 * share, 1), 'voices': len(voices)}]
    for k in range(1, r['max_rounds'] + 1):
        if share * 100 <= r['stop_pct']:
            break
        add = new_voices(resid, sr, tuning_cents, voices, cfg, ignored)
        if not add:
            break
        voices = {**voices, **add}
        res = separate_fn(y, sr, voices, spec, tuning_cents, cfg)
        total = float(np.sum(res['harm'] ** 2)) + 1e-12
        weak = [i for i in add if 100 * np.sum(res['voices'][i] ** 2) / total < r['min_voice_pct']]
        if weak:                                                       # leakage ghosts: a voice that carries almost nothing is not an instrument
            voices = {i: v for i, v in voices.items() if i not in weak}
            add = {i: v for i, v in add.items() if i not in weak}
            res = separate_fn(y, sr, voices, spec, tuning_cents, cfg)
        new_share, resid = unexplained_share(res['harm'], list(res['voices'].values()))
        log.append({'round': k, 'unexplained_pct': round(100 * new_share, 1), 'voices': len(voices), 'added': list(add)})
        if new_share >= share * r['min_gain']:                        # not getting better: keep the voices, stop looking
            share = new_share
            break
        share = new_share
    return res, voices, log


def run(ctx):
    import os
    from . import audio_io, separate
    from .config import jdump
    cfg, d = ctx['cfg'], ctx['data']
    if 'sep' not in d:
        separate.run(ctx)
    sr = cfg['analysis']['sr']
    res, vs, log = rounds(d['mix'], sr, d['voices'], d['spec'], d['tuning']['cents'], cfg, separate.separate, first=d['sep'], ignored=ctx['priors'].get('ignored'))
    d['sep'], d['voices'], d['residual_log'] = res, vs, log
    if cfg['export']['keep_raw']:
        for i, a in res['voices'].items():
            audio_io.write(os.path.join(ctx['root'], 'out', 'raw', f'{i}.wav'), a, sr)
    jdump({'rounds': log}, os.path.join(ctx['root'], 'reports', 'residual.json'))
    for row in log:
        print(f'  round {row["round"]}: {row["unexplained_pct"]}% of the tonal energy unexplained, {row["voices"]} voices {row.get("added", "")}')
