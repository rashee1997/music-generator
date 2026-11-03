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

"""music_db: read, check and use a project's music_db/ folder (JSON written by a listening model).

The model's numbers are estimates by ear. Nothing here fixes them silently: it reports what looks wrong and turns the
rest into search windows (when, where in pitch, how many voices), which signal processing then measures.
Every constant comes from the profile's `music_db` section."""
import glob
import os
import re

import numpy as np

from .config import SK, jload

NOTE_RE = re.compile(r'^([A-Ga-g])([#b]?)(-?\d)$')
PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SIGNATURES = os.path.join(SK, 'knowledgebase', 'instrument_signatures.json')
REGISTRY = os.path.join(SK, 'knowledgebase', 'instruments_registry.json')


def note_to_midi(name):
    """'D#2' -> 39 (C4 = 60). None if the text is not a note name."""
    m = NOTE_RE.match(str(name).strip())
    if not m:
        return None
    letter, acc, octave = m.groups()
    return 12 * (int(octave) + 1) + PC[letter.upper()] + {'#': 1, 'b': -1, '': 0}[acc]


def hz(midi, cents=0.0, a4=440.0):
    """Frequency of a MIDI pitch when the recording sits `cents` above (or below) concert pitch."""
    return a4 * 2.0 ** ((midi - 69) / 12.0 + cents / 1200.0)


def load(folder, cfg):
    """{'song', 'instruments', 'drums', 'effects', 'spatial', 'files', 'schema_errors'}; later files win by id."""
    if not os.path.isdir(folder):
        raise FileNotFoundError(f'music_db folder not found: {folder}')
    m = cfg['music_db']
    db = {'folder': folder, 'song': {}, 'instruments': [], 'drums': {'pieces': []}, 'effects': {'events': [], 'textures': []},
          'spatial': {'space': {}, 'sources': [], 'transitions': []}, 'files': {}, 'schema_errors': []}
    for kind, pat in m['files'].items():
        for path in sorted(glob.glob(os.path.join(folder, pat))):
            d = jload(path)
            name = os.path.basename(path)
            db['files'].setdefault(kind, []).append(name)
            if d.get('schema') != m['schemas'][kind]:
                db['schema_errors'].append(f'{name}: schema "{d.get("schema")}" should be "{m["schemas"][kind]}"')
            if kind == 'song':
                db['song'].update(d)
            elif kind == 'instruments':
                by_id = {i['id']: i for i in db['instruments']}
                for i in d.get('instruments', []):
                    by_id[i['id']] = {**by_id.get(i['id'], {}), **i}
                db['instruments'] = list(by_id.values())
            elif kind == 'drums':
                db['drums'].update({k: v for k, v in d.items() if k != 'pieces'})
                db['drums']['pieces'] += d.get('pieces', [])
            elif kind == 'effects':
                db['effects']['events'] += d.get('events', [])
                db['effects']['textures'] += d.get('textures', [])
            else:
                db['spatial']['space'].update(d.get('space', {}))
                by_id = {s['id']: s for s in db['spatial']['sources']}
                for s in d.get('sources', []):
                    by_id[s['id']] = {**by_id.get(s['id'], {}), **s}
                db['spatial']['sources'] = list(by_id.values())
                db['spatial']['transitions'] += d.get('transitions', [])
    return db


def known_ids():
    ids = set()
    for p in (REGISTRY, SIGNATURES):
        if os.path.isfile(p):
            ids |= set(jload(p).get('instruments', {}))
    return ids


def grid_info(song, cfg):
    """Beat length, bar length and a downbeat anchor (first section whose name is not an intro word, unless anchor_s is a number)."""
    m = cfg['music_db']
    bpm = (song.get('tempo_bpm') or {}).get('value')
    if not bpm:
        return None
    beat = 60.0 / bpm
    secs = song.get('sections') or []
    if m['anchor_s'] != 'auto':
        anchor = float(m['anchor_s'])
    else:
        body = [s for s in secs if not any(w in str(s.get('name', '')).lower() for w in m['intro_names'])]
        anchor = float((body or secs or [{'start_s': 0.0}])[0]['start_s'])
    return {'beat_s': beat, 'bar_s': beat * int(str(song.get('time_signature', '4/4')).split('/')[0]), 'anchor_s': anchor}


def grid_residual(times, grid, subdiv):
    """Distance (s) of each time to the nearest 1/subdiv beat."""
    step = grid['beat_s'] / subdiv
    t = np.asarray(times, float) - grid['anchor_s']
    return np.abs(t - np.round(t / step) * step)


def validate(db, cfg):
    """List of (level, where, message). ERROR = cannot use, WARN = use with care."""
    m = cfg['music_db']
    out = []
    add = lambda lv, where, msg: out.append((lv, where, msg))
    for e in db['schema_errors']:
        add('ERROR', 'schema', e)
    song = db['song']
    dur = song.get('duration_s')
    if not dur:
        add('ERROR', 'song', 'no duration_s')
        dur = 1e9
    slack = m['song_end_slack_s']
    grid = grid_info(song, cfg)
    if grid is None:
        add('WARN', 'song', 'no tempo_bpm.value; no grid checks')
    secs = song.get('sections', [])
    for a, b in zip(secs, secs[1:]):
        if abs(a['end_s'] - b['start_s']) > m['section_gap_tol_s']:
            add('WARN', f'song.sections[{a["name"]}]', f'ends {a["end_s"]} but next starts {b["start_s"]}')
    if grid and len(secs) > 2:
        off = [abs(x - round(x)) for x in [(s['end_s'] - s['start_s']) / grid['bar_s'] for s in secs[1:-1]]]
        if max(off) > m['section_bar_off_warn']:
            add('WARN', 'song.sections', f'section lengths are not whole bars at {song["tempo_bpm"]["value"]} BPM (worst {max(off):.2f} bar off)')
    for a in song.get('ignored_vocals') or []:
        if a.get('start_s') is None or a.get('end_s') is None or a['start_s'] >= a['end_s'] or a['end_s'] > dur + slack:
            add('ERROR', 'song.ignored_vocals', f'window {a.get("start_s")}-{a.get("end_s")} invalid')
    ids = known_ids()
    seen = set()
    for ins in db['instruments']:
        w = f'instruments[{ins.get("id")}]'
        if ins.get('id') in seen:
            add('ERROR', w, 'duplicate id')
        seen.add(ins.get('id'))
        if ins.get('family') == 'voice' and not str(ins.get('id', '')).startswith('humming'):
            add('WARN', w, 'a singing/rapping voice is out of scope (only humming_* voices are modelled): move it to song.ignored_vocals')
        r = ins.get('range') or {}
        lo, hi = note_to_midi(r.get('lowest_note')), note_to_midi(r.get('highest_note'))
        if (r.get('lowest_note') or r.get('highest_note')) and (lo is None or hi is None):
            add('ERROR', w, f'range is not note names: {r}')
        elif lo is not None and lo > hi:
            add('ERROR', w, 'lowest_note is above highest_note')
        h = (ins.get('timbre') or {}).get('harmonics_rel')
        if h is not None and (len(h) != m['harmonics_count'] or max(h) > 1.0 + 1e-9 or min(h) < 0):
            add('WARN', w, f'harmonics_rel should be {m["harmonics_count"]} numbers in 0..1')
        sim = ins.get('similar_to') or []
        for s in ([sim] if isinstance(sim, str) else sim):
            if s not in ids:
                add('WARN', w, f'similar_to "{s}" is not a known id (new instrument?)')
        for a in ins.get('activity', []):
            if a['start_s'] > a['end_s'] or a['end_s'] > dur + slack:
                add('ERROR', w, f'activity {a["start_s"]}-{a["end_s"]} outside the song')
    for p in db['drums'].get('pieces', []):
        w = f'drums[{p.get("id")}]'
        ht = [t for t in p.get('hit_times_s', []) if 0 <= t <= dur + slack]
        if len(ht) != len(p.get('hit_times_s', [])):
            add('ERROR', w, 'hit_times_s outside the song')
        if grid and len(ht) >= m['min_hits_for_grid_check']:
            sub = m['grid_subdivision']
            med = float(np.median(grid_residual(ht, grid, sub))) / (grid['beat_s'] / sub)
            if med > m['hit_offset_warn_steps']:
                add('WARN', w, f'hit_times_s sit {med:.2f} of a step (1/{sub} beat) off the grid (median): treat as search windows, not marks')
    evs = sorted(db['effects'].get('events', []), key=lambda e: e['start_s'])
    for ev in evs:
        if ev['start_s'] >= ev['end_s'] or ev['end_s'] > dur + slack:
            add('ERROR', f'effects[{ev.get("id")}]', f'window {ev["start_s"]}-{ev["end_s"]} invalid')
    if len(evs) > 2 and all(abs(a['end_s'] - b['start_s']) < m['section_gap_tol_s'] for a, b in zip(evs, evs[1:])):
        add('WARN', 'effects', 'events are back-to-back with no gaps: windows are chunks of one continuous region, not true event edges')
    all_ids = seen | {p.get('id') for p in db['drums'].get('pieces', [])} | {e.get('id') for e in evs}
    for s in db['spatial']['sources']:
        if s.get('id') not in all_ids:
            add('WARN', f'spatial[{s.get("id")}]', 'id matches no instrument, drum piece or effect')
        for mv in s.get('moves', []):
            if mv.get('start_s', 0) > mv.get('end_s', 0) or mv.get('end_s', 0) > dur + slack:
                add('ERROR', f'spatial[{s.get("id")}]', f'move {mv.get("start_s")}-{mv.get("end_s")} invalid')
    return out


def priors(db, cfg):
    """What the extractor needs: tuning, grid, voices (when/where), drum pieces, effect windows, spatial claims."""
    song = db['song']
    offs = [i['pitch_behavior']['tuning_offset_cents'] for i in db['instruments']
            if (i.get('pitch_behavior') or {}).get('tuning_offset_cents') is not None]
    voices = []
    for i in db['instruments']:
        r = i.get('range') or {}
        voices.append({'id': i['id'], 'family': i.get('family'), 'role': i.get('role'), 'polyphony': i.get('polyphony', 1),
                       'midi_lo': note_to_midi(r.get('lowest_note')), 'midi_hi': note_to_midi(r.get('highest_note')),
                       'spans': [(a['start_s'], a['end_s']) for a in i.get('activity', [])],
                       'timbre': i.get('timbre'), 'envelope': i.get('envelope'), 'pitch_behavior': i.get('pitch_behavior'), 'pan': (i.get('space') or {}).get('pan_minus1_to_1'),
                       'similar_to': i.get('similar_to') or []})
    return {'tuning_cents': float(np.median(offs)) if offs else float(song.get('tuning_cents') or 0.0),
            'bpm': (song.get('tempo_bpm') or {}).get('value'), 'grid': grid_info(song, cfg), 'key': song.get('key'),
            'duration_s': song.get('duration_s'), 'sections': song.get('sections', []), 'voices': voices,
            'ignored': [(float(a['start_s']), float(a['end_s'])) for a in song.get('ignored_vocals') or []
                        if a.get('start_s') is not None and a.get('end_s') is not None],
            'drum_pieces': db['drums'].get('pieces', []), 'effects': db['effects'].get('events', []),
            'spatial': db['spatial']}


def in_windows(t, windows):
    """True if time t lies inside any (start, end) window; used for the sung/rapped parts we do not model."""
    return any(a <= t <= b for a, b in windows)


def voice_active(voice, t, pad):
    """True if a voice may sound at time t (inside any listed span, padded)."""
    return any(a - pad <= t <= b + pad for a, b in voice['spans']) if voice['spans'] else True


def to_signature(ins, cfg):
    """Strip a listening-model entry to the fields the matcher needs; the estimate stays until it is measured."""
    return {k: ins[k] for k in cfg['music_db']['signature_fields'] if k in ins} | {'source': 'listening_model_estimate', 'measured': None}


def report(db, cfg):
    """(lines, issues) for `check-db`."""
    issues = validate(db, cfg)
    p = priors(db, cfg)
    key = p['key'] and (p['key'].get('tonic'), p['key'].get('mode'))
    lines = [f'files: {db["files"]}', f'song: {p["duration_s"]} s, {p["bpm"]} BPM, key {key}, tuning {p["tuning_cents"]:+.0f} cents']
    if p['grid']:
        lines.append(f'grid: beat {p["grid"]["beat_s"]:.4f} s, bar {p["grid"]["bar_s"]:.3f} s, downbeat anchor {p["grid"]["anchor_s"]} s')
    lines.append(f'{len(p["voices"])} voices, {len(p["drum_pieces"])} drum pieces, {len(p["effects"])} effect events, '
                 f'{len(p["sections"])} sections, {len(p["spatial"]["sources"])} spatial sources')
    for v in p['voices']:
        lines.append(f'  {v["id"]:<26} midi {v["midi_lo"]}-{v["midi_hi"]}  poly {v["polyphony"]}  spans {len(v["spans"])}')
    lines.append(f'{len(issues)} issue(s)')
    lines += [f'  [{lv}] {w}: {m}' for lv, w, m in issues]
    return lines, issues
