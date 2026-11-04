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

"""The skill's fallback knowledge base: data files in knowledgebase/ that name what the extractor measured.

Nothing here is a fixed list in code: rules and signatures are JSON the user can edit, and `grow` writes new
measurements back so the next project starts smarter."""
import os

from .config import SK, jload

KB = os.path.join(SK, 'knowledgebase', 'data')
EFFECTS = os.path.join(KB, 'effect_signatures.json')


def holds(rule, feats):
    """Every min_X / max_X key of the rule is met by the measured feature X (a missing feature fails the rule)."""
    for k, lim in rule.items():
        if k.startswith('min_'):
            if feats.get(k[4:]) is None or feats[k[4:]] < lim:
                return False
        elif k.startswith('max_'):
            if feats.get(k[4:]) is None or feats[k[4:]] > lim:
                return False
    return True


def classify(feats, rules, default='other'):
    """First matching rule's kind, else `default`."""
    for r in rules:
        if holds({k: v for k, v in r.items() if k != 'kind'}, feats):
            return r['kind']
    return default


def effect_rules():
    return jload(EFFECTS)


def ambient_kind(feats):
    return classify(feats, effect_rules()['ambient_kinds'], default='ambient')


SIGNATURES = os.path.join(KB, 'instrument_signatures.json')
PITCH_TABLE = os.path.join(KB, 'pitch_table.json')


def grow(ctx, summary):
    """Write what this project measured into the fallback database. A measured entry with more notes is never replaced by a thinner one."""
    import json

    from .music_db import to_signature
    cur = jload(SIGNATURES) if os.path.isfile(SIGNATURES) else {'schema': 'music_db.signatures/1', 'instruments': {}}
    d, cfg = ctx['data'], ctx['cfg']
    declared = {i['id']: i for i in ctx['db']['instruments']}
    song = os.path.basename(ctx['song'])
    changed = []
    for vid, info in summary.items():
        if vid.startswith('drum:') or not info.get('notes'):
            continue
        base = to_signature(declared[vid], cfg) if vid in declared else {'source': 'measured_only', 'label': vid}
        prev = cur['instruments'].get(vid, {})
        if (prev.get('measured') or {}).get('notes', 0) > info['notes']:
            continue
        notes = d['sep']['notes'][vid]
        midis = [n['midi'] for n in notes]
        base['measured'] = {'notes': info['notes'], 'harmonics_rel': info['template'], 'midi_lo': int(min(midis)), 'midi_hi': int(max(midis)),
                            'tuning_cents': round(float(d['tuning']['cents']), 1), 'song': song, 'spatial': info.get('spatial')}
        cur['instruments'][vid] = {**prev, **base}
        changed.append(vid)
    with open(SIGNATURES, 'w', encoding='utf-8') as f:
        json.dump(cur, f, indent=1, ensure_ascii=False)
    return changed


def build_pitch_table(a4=440.0, harmonics=12):
    """MIDI 0..127: Hz, ERB bandwidth, A-weighting, where each harmonic falls (nearest semitone and cents off equal temperament),
    and which known instruments can play it (from the signatures' ranges)."""
    import json

    import numpy as np
    sig = jload(SIGNATURES).get('instruments', {}) if os.path.isfile(SIGNATURES) else {}

    def a_weight(f):
        f2 = f * f
        ra = (12194.0 ** 2 * f2 ** 2) / ((f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194.0 ** 2))
        return float(20 * np.log10(ra) + 2.0)

    from .music_db import note_to_midi
    table = {}
    for m in range(128):
        f = a4 * 2.0 ** ((m - 69) / 12.0)
        ladder = []
        for h in range(1, harmonics + 1):
            x = m + 12 * np.log2(h)
            ladder.append({'h': h, 'semitone': int(round(x)), 'cents_off': round(float((x - round(x)) * 100), 1)})
        who = []
        for k, v in sig.items():
            r = v.get('range') or {}
            lo, hi = note_to_midi(r.get('lowest_note')), note_to_midi(r.get('highest_note'))
            if lo is not None and hi is not None and lo <= m <= hi:
                who.append(k)
        table[str(m)] = {'hz': round(f, 3), 'erb_hz': round(24.7 * (4.37 * f / 1000 + 1), 2), 'a_weight_db': round(a_weight(f), 1),
                         'harmonics': ladder, 'instruments': who}
    with open(PITCH_TABLE, 'w', encoding='utf-8') as f:
        json.dump({'schema': 'music_db.pitch_table/1', 'a4_hz': a4, 'pitches': table}, f, indent=0)
    return len(table)
