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

"""Stage `voices`: give every found note to an instrument.

Declared voices (from music_db) are matched by range, active span and harmonic template. A voice's template is first
measured from its unambiguous notes, then used to settle notes two voices could play. Notes nobody declared are
clustered by timbre into `unknown_n` voices instead of being thrown away. Nothing is named from a hardcoded list."""
import os

import numpy as np

from .config import jdump
from .music_db import in_windows
from .spectrum import harmonic_offsets


def note_vector(note, spec, cfg):
    """Harmonic amplitudes of a note (median over the middle of its frames), scaled to max 1."""
    S, hop, lo = spec['S'], spec['hop_s'], spec['midi_lo']
    offs = harmonic_offsets(cfg['voices']['template_harmonics'])
    i0, i1 = int(note['start_s'] / hop), max(int(note['end_s'] / hop), int(note['start_s'] / hop) + 1)
    cut = int((i1 - i0) * cfg['voices']['edge_trim'])
    a, b = i0 + cut, max(i1 - cut, i0 + cut + 1)
    row = note['midi'] - lo
    lin = 1.0 / cfg['spectrum']['compress']                                      # back to linear magnitude: templates are used as amplitudes
    v = np.array([np.median(S[row + o, a:b]) ** lin if 0 <= row + o < S.shape[0] else 0.0 for o in offs])
    return v / v.max() if v.max() > 0 else v


def distance(a, b):
    """Cosine distance between two harmonic vectors."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 1.0 if na == 0 or nb == 0 else float(1.0 - a @ b / (na * nb))


def prior_template(voice, cfg):
    h = (voice.get('timbre') or {}).get('harmonics_rel')
    n = cfg['voices']['template_harmonics']
    if not h:
        return None
    h = np.array(h[:n] + [0.0] * (n - len(h)), float)
    return h / h.max() if h.max() > 0 else None


def cluster_vectors(vecs, threshold):
    """Single-pass leader clustering: a vector joins the nearest cluster centre within `threshold`, else starts a new one."""
    centres, label = [], []
    for v in vecs:
        d = [distance(v, c) for c in centres]
        if d and min(d) <= threshold:
            k = int(np.argmin(d))
        else:
            centres.append(v.copy())
            k = len(centres) - 1
        label.append(k)
        members = [vecs[i] for i, l in enumerate(label) if l == k]
        centres[k] = np.mean(members, axis=0)
    return label, centres


def assign(notes, spec, priors, cfg):
    vc = cfg['voices']
    for n in notes:
        n['vec'] = note_vector(n, spec, cfg)
    declared = {v['id']: v for v in priors['voices']}
    temp = {i: prior_template(v, cfg) for i, v in declared.items()}
    measured = {}
    for i in declared:                                  # pass 1: templates from notes only this voice could play
        own = [n['vec'] for n in notes if n['voices'] == [i]]
        if len(own) >= vc['min_notes_for_template']:
            measured[i] = np.percentile(own, vc['template_percentile'], axis=0)
    use = lambda i: measured.get(i, temp.get(i))
    for n in notes:
        c = n['voices']
        if len(c) == 1:
            n['voice'] = c[0]
        elif len(c) > 1:
            scored = [(distance(n['vec'], use(i)) if use(i) is not None else 0.5, i) for i in c]
            n['voice'] = min(scored)[1]
        else:
            n['voice'] = None
    for i in declared:                                  # pass 2: templates re-measured with the settled notes
        mine = [n['vec'] for n in notes if n['voice'] == i]
        if len(mine) >= vc['min_notes_for_template']:
            measured[i] = np.percentile(mine, vc['template_percentile'], axis=0)
    ignored = priors.get('ignored') or []
    loose = [n for n in notes if n['voice'] is None and not in_windows((n['start_s'] + n['end_s']) / 2, ignored)]   # no new instrument from sung/rapped parts
    unknown = {}
    if loose:
        lab, centres = cluster_vectors([n['vec'] for n in loose], vc['undeclared_distance'])
        for k, c in enumerate(centres):
            mem = [n for n, l in zip(loose, lab) if l == k]
            if len(mem) >= vc['undeclared_min_notes'] or sum(n['end_s'] - n['start_s'] for n in mem) >= vc['undeclared_min_s']:
                uid = f'unknown_{len(unknown) + 1}'
                unknown[uid] = c
                for n in mem:
                    n['voice'] = uid
    voices = {}
    for i, v in declared.items():
        voices[i] = {'id': i, 'declared': True, 'template': use(i), 'template_source': 'measured' if i in measured else ('music_db' if temp.get(i) is not None else 'default'),
                     'spans': v['spans'], 'range': [v['midi_lo'], v['midi_hi']]}
    for uid, c in unknown.items():
        voices[uid] = {'id': uid, 'declared': False, 'template': c, 'template_source': 'measured', 'spans': [], 'range': None}
    for i, v in voices.items():
        v['notes'] = [n for n in notes if n['voice'] == i]
        if v['template'] is None:                       # nothing known: a plain decaying series
            v['template'] = vc['default_decay'] ** np.arange(vc['template_harmonics'])
    return voices, [n for n in notes if n['voice'] is None]


def write_midi(voices, path, tempo, cfg):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(tempo or 120.0))
    for i, v in voices.items():
        ins = pretty_midi.Instrument(program=cfg['voices']['midi_program'], name=i)
        top = max([n['strength'] for n in v['notes']] or [1.0])
        for n in v['notes']:
            vel = int(np.clip(cfg['voices']['velocity_floor'] + (127 - cfg['voices']['velocity_floor']) * (n['strength'] / top) ** 0.6, 1, 127))
            ins.notes.append(pretty_midi.Note(velocity=vel, pitch=int(n['midi']), start=n['start_s'], end=n['end_s']))
        pm.instruments.append(ins)
    pm.write(path)


def run(ctx):
    from . import listen, notes as notes_mod
    cfg, d = ctx['cfg'], ctx['data']
    if 'spec' not in d:
        listen.run(ctx)
    found, roll = notes_mod.find_notes(d['spec'], ctx['priors'], cfg)
    voices, leftover = assign(found, d['spec'], ctx['priors'], cfg)
    d.update({'notes': found, 'roll': roll, 'voices': voices, 'unassigned_notes': leftover})
    root = ctx['root']
    rep = {i: {'declared': v['declared'], 'notes': len(v['notes']), 'template_source': v['template_source'],
               'template': [round(float(x), 3) for x in v['template']]} for i, v in voices.items()}
    jdump({'voices': rep, 'unassigned_notes': len(leftover), 'total_notes': len(found)}, os.path.join(root, 'reports', 'voices.json'))
    for i, r in rep.items():
        print(f'  {i:<26} {r["notes"]:>5} notes  ({r["template_source"]})')
    print(f'  unassigned notes: {len(leftover)} of {len(found)}')
