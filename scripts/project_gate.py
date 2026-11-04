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
"""project_gate.py - Stage 0 of the pipeline: is this a real project, before anything renders?

Checks (every problem is listed at once, nothing is guessed):
  1. scaffold folders exist (direction/ presets/ scores/ reports/)
  2. a research note reports/research_*.md cites a knowledge-base id and lists web sources (a URL)
  3. a direction sheet direction/*.json has the required fields
  4. every preset JSON in the project parses
  5. every non-built-in instrument / vocal track names a preset that exists exactly (no substring guessing)
  6. ambience and room come only from presets of this project: environments (character, a bed, known primitives and keys,
     no ambience built in scripts) and the score's space (presets/spaces/)

    python3 scripts/project_gate.py <project> [score.json]      # exit 1 when anything is missing
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import environment as envmod
import presets
import soundbank as sb
import vocals
import world

SKILL = Path(HERE).parent
SCAFFOLD = ('direction', 'presets', 'scores', 'reports')   # out/, midi/, stems/ are created by the run
# each group is satisfied by any one of its keys (older sheets use other names)
DIRECTION_NEEDS = [('title', 'purpose', 'concept'), ('duration_s', 'duration_seconds'), ('tempo_bpm', 'bpm'),
                   ('key', 'mode'), ('feel',), ('avoid_feel',), ('spatial_staging', 'staging'),
                   ('loudness_lufs',), ('true_peak_max',)]
WEB_MARK = re.compile(r'^#+\s*web research', re.I | re.M)
HIT_KINDS = ('cut', 'motion', 'musical')
HIT_SYNC = ('hard', 'soft')
ENDINGS = ('hard_out', 'tail_out', 'combination')


_norm = presets._norm          # one implementation, in presets.py


def kb_document_ids():
    """`id` values from the frontmatter of every markdown file under knowledgebase/."""
    ids = set()
    for p in (SKILL / 'knowledgebase').rglob('*.md'):
        text = p.read_text(encoding='utf-8', errors='replace')
        head = text.split('---', 2)[1] if text.startswith('---') else ''
        ids.update(re.findall(r'^id:\s*["\']?([A-Za-z0-9_\-.]+)', head, re.M))
    return ids


KB_CITE = re.compile(r'\bid:\s*`?([A-Za-z0-9_.\-]+)`?')
KB_PATH = re.compile(r'knowledgebase/[A-Za-z0-9_./-]+\.md')


def cites_kb(text, ids):
    """True when a note names a knowledge-base id (research_kb.py writes `- id: x`) or links its file."""
    cited = set(KB_CITE.findall(text))
    cited.update(os.path.splitext(os.path.basename(t))[0] for t in KB_PATH.findall(text))
    return bool(cited & ids)


def is_builtin(tr):
    """True when the track needs no preset: a native GM / drum-kit name, env:, clone:, or a built-in formant voice.
    World names that merely stand in for a GM sound (oud -> nylon_guitar) are custom: they need a preset."""
    raw = tr.get('instrument', 'piano')
    if isinstance(raw, int):
        return True
    raw = str(raw)
    if raw.startswith(('env:', 'clone:', 'sfx:')) or tr.get('role') == 'environment':
        return True
    k = _norm(raw)
    if world.INSTRUMENTS.get(k, k) != k:       # oud, kora, ney ...: a named stand-in for a GM sound, so it needs its own preset
        return False
    return k in sb.GM or k in sb.DRUM_KITS or k in sb.DRUM_ALIASES or k in vocals.INSTRUMENTS


def research_problems(project):
    notes = sorted((project / 'reports').glob('research_*.md')) if (project / 'reports').is_dir() else []
    if not notes:
        return ['no reports/research_<topic>.md (run: research_kb.py <project> --topic ... --tags ...)']
    ids = kb_document_ids()
    best = None                                   # the note closest to done, for a useful message
    for n in notes:
        t = n.read_text(encoding='utf-8', errors='replace')
        cites = cites_kb(t, ids)
        m = WEB_MARK.search(t)
        web = bool(m and re.search(r'https?://', t[m.end():]))
        if cites and web:
            return []
        if best is None or (cites, web) > best[1]:
            best = (n, (cites, web))
    n, (kb, web) = best
    lack = [x for x, ok in (('a knowledge-base id citation (run research_kb.py)', kb),
                            ('at least one URL under "Web research"', web)) if not ok]
    return [f'{n.name} lacks ' + ' and '.join(lack)]


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def sheet_shape_problems(sheet):
    """Checks on the director's blocks, run only for the blocks a sheet actually carries.

    The sheet is a promise: sections in seconds that do not overlap, hits with a reason, a picture block that names
    its file. A sheet that contradicts itself is worse than a short one, because every later stage trusts it.
    """
    bad = []
    dur = sheet.get('duration_s', sheet.get('duration_seconds'))
    dur = float(dur) if _num(dur) else None
    hits_at = sheet.get('hits_at') or []
    if not isinstance(hits_at, list) or any(not _num(t) for t in hits_at):
        bad.append('hits_at as a list of seconds')

    secs = sheet.get('sections')
    if secs is not None:
        if not isinstance(secs, list):
            bad.append('sections as a list of {name, start_s, end_s, energy, role}')
        else:
            prev = None
            for i, s in enumerate(secs):
                name = (s or {}).get('name', f'sections[{i}]')
                if not isinstance(s, dict) or not _num(s.get('start_s')) or not _num(s.get('end_s')):
                    bad.append(f'{name}: needs start_s and end_s in seconds')
                    break
                if s['end_s'] <= s['start_s']:
                    bad.append(f'{name}: ends at {s["end_s"]} s, before it starts')
                    break
                if prev is not None and s['start_s'] < prev - 0.05:
                    bad.append(f'{name}: starts at {s["start_s"]} s, inside the section above it')
                    break
                if dur and s['end_s'] > dur + 0.5:
                    bad.append(f'{name}: ends at {s["end_s"]} s, past duration_s {dur:g}')
                    break
                prev = s['end_s']

    motifs = sheet.get('motifs')
    if motifs is not None and (not isinstance(motifs, list) or any(not isinstance(m, dict) or not m.get('name')
                                                                 for m in motifs)):
        bad.append('motifs as a list of {name, first_at_s, shape, returns}')

    ending = sheet.get('ending')
    if ending is not None and ending not in ENDINGS:
        bad.append(f'ending "{ending}" is not one of: {", ".join(ENDINGS)}')

    hits = sheet.get('hits')
    if hits is not None:
        if not isinstance(hits, list):
            bad.append('hits as a list of {t, kind, sync, sound, why}')
        else:
            for i, h in enumerate(hits):
                if not isinstance(h, dict) or not _num(h.get('t')):
                    bad.append(f'hits[{i}] needs t in seconds')
                    break
                if h.get('kind') not in HIT_KINDS:
                    bad.append(f'hits[{i}] kind "{h.get("kind")}" is not one of: {", ".join(HIT_KINDS)}')
                    break
                if h.get('sync') is not None and h['sync'] not in HIT_SYNC:
                    bad.append(f'hits[{i}] sync "{h["sync"]}" is hard or soft')
                    break
                if dur and h['t'] > dur + 0.05:
                    bad.append(f'hits[{i}] at {h["t"]} s is past duration_s {dur:g}')
                    break
            else:
                detailed = sorted(round(float(h['t']), 3) for h in hits)
                listed = sorted(round(float(t), 3) for t in hits_at if _num(t))
                if detailed != listed:
                    bad.append(f'hits and hits_at list different moments ({len(detailed)} vs {len(listed)}); '
                               f'hits_at is the summary listen.py checks')

    video = sheet.get('video')
    if video is not None:
        if not isinstance(video, dict):
            bad.append('video as an object (leave enabled false for a music-only piece)')
        elif video.get('enabled'):
            for k in ('source', 'master_profile'):
                if not video.get(k):
                    bad.append(f'video.{k} is empty while video.enabled is true')
            if not _num(video.get('fps')) or float(video.get('fps') or 0) <= 0:
                bad.append('video.fps is the picture rate (a number above 0)')
            if not isinstance(video.get('cuts'), list):
                bad.append('video.cuts is the cut list the hits came from')
            sync = video.get('cut_sync') or {}
            if not (_num(sync.get('early_ms')) and _num(sync.get('late_ms'))):
                bad.append('video.cut_sync needs early_ms and late_ms')

    delivery = sheet.get('delivery')
    if delivery is not None:
        if not isinstance(delivery, dict):
            bad.append('delivery as an object {format, sample_rate, bit_depth, stage}')
        elif not all(_num(delivery.get(k)) and delivery[k] > 0 for k in ('sample_rate', 'bit_depth') if k in delivery):
            bad.append('delivery.sample_rate and bit_depth are numbers above 0')
    return bad


def direction_problems(project):
    sheets = sorted((project / 'direction').glob('*.json')) if (project / 'direction').is_dir() else []
    if not sheets:
        return ['no direction/*.json (copy templates/direction_sheet.json and fill it)']
    last = []
    for s in sheets:
        try:
            d = json.loads(s.read_text(encoding='utf-8'))
        except Exception as e:
            last = [f'{s.name}: not valid JSON ({e})']
            continue
        if 'TODO' in s.read_text(encoding='utf-8'):
            last = [f'{s.name}: still has TODO placeholders; fill them in']
            continue
        miss = [' | '.join(g) for g in DIRECTION_NEEDS if not any(d.get(k) not in (None, '', [], {}) for k in g)]
        if 'hits_at' not in d:
            miss.append('hits_at (use [] if there are none)')
        stg = d.get('spatial_staging') or d.get('staging')
        if stg is not None and not isinstance(stg, dict):
            miss.append('spatial_staging as an object {name: {azimuth, distance}}')
        shape = [] if miss else sheet_shape_problems(d)
        if not miss and not shape:
            return []
        parts = ([f'missing {", ".join(miss)}'] if miss else []) + shape
        last = [f'{s.name}: ' + '; '.join(parts)]
    return last


def preset_file_problems(project):
    out = []
    for p in sorted((project / 'presets').rglob('*.json')) if (project / 'presets').is_dir() else []:
        try:
            json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            out.append(f'presets/{p.parent.name}/{p.name}: not valid JSON ({e})')
    return out


def closest_builtin(name):
    try:
        bank, prog, drum = sb.resolve(name)
    except KeyError:
        return None
    k = _norm(name)
    return next((g for g in sb.GM if g in k or k in g), None)


def track_problems(score, project):
    presets.add_project(str(project))
    out = []
    import sfx
    for i, tr in enumerate(score.get('tracks', [])):
        raw = str(tr.get('instrument', ''))
        if raw.startswith('sfx:'):
            eff = _norm(raw[4:])
            cfg = presets.find_sfx(eff)
            label = f'track "{tr.get("name", i)}"'
            if eff in sfx.AMBIENCE and not (cfg and cfg.get('generator') not in sfx.AMBIENCE):
                out.append(f'{label}: "{eff}" is ambience, not a one-hit effect; make it an environments preset and use env:<name> '
                           f'(presets.py scaffold environments <name> --project <dir>)')
            elif cfg is None and eff not in sfx.GENERATORS:
                out.append(f'{label}: unknown effect "{raw[4:]}"; known: {", ".join(sorted(sfx.GENERATORS))}, '
                           f'or write presets/sfx/{eff}.json (presets.py scaffold sfx {eff} --project <dir>)')
            elif cfg is not None:
                out += [f'sfx/{eff}.json: {p}' for p in sfx.preset_problems(cfg)]
                if _owned(cfg) and _placeholder(cfg.get('character')):
                    out.append(f'sfx/{eff}.json: "character" is empty or still the placeholder; write one sentence on the sound')
        if raw.startswith('env:') and presets.find_environment(raw[4:]) is None:
            out.append(f'track "{tr.get("name", i)}": environment "{raw[4:]}" has no preset (it would render as silence); '
                       f'create: presets.py scaffold environments {_norm(raw[4:])} --project <dir>')
        if isinstance(tr.get('vocal'), dict):         # a track's own vocal block: same checks as a vocal preset
            from vocal_engine import config as vcfg
            out += [f'track "{tr.get("name", i)}" vocal: {w}' for w in vcfg.validate(tr['vocal'])]
        vp = presets.exact('vocals', tr.get('instrument', '')) if isinstance(tr.get('instrument'), str) else None
        if vp is not None:
            from vocal_engine import config as vcfg
            out += [f'vocals/{_norm(tr["instrument"])}.json: {w}' for w in vcfg.validate(vp)]
            if _owned(vp) and _placeholder(vp.get('character')):
                out.append(f'vocals/{_norm(tr["instrument"])}.json: "character" is empty or still the placeholder; write one sentence on who sings and how')
        if is_builtin(tr):
            continue
        inst = tr.get('instrument', '')
        if presets.exact('instruments', inst) is None and presets.exact('vocals', inst) is None:
            near = closest_builtin(inst)
            hint = f'; or use the built-in "{near}"' if near else ''
            out.append(f'track "{tr.get("name", i)}": instrument "{inst}" is not built in and has no exact preset '
                       f'presets/instruments/{_norm(inst)}.json or presets/vocals/{_norm(inst)}.json '
                       f'(create: presets.py scaffold instruments|vocals {_norm(inst)} --project <dir>{hint})')
    return out


def _placeholder(text):
    t = str(text or '').strip()
    return not t or t.startswith('ONE SENTENCE') or 'TODO' in t


def _owned(cfg):
    """True when the preset file lives in a project, not in the skill's shipped (fallback) presets."""
    src = cfg.get('_source') if cfg else None
    return bool(src) and not os.path.abspath(src).startswith(presets.SKILL_PRESETS)


def ambience_problems(score, project):
    """Ambience is made from presets of THIS project, written during research. Nothing is taken from the skill as it ships."""
    presets.add_project(str(project))
    out, env_tracks, has_bed = [], 0, False
    for i, tr in enumerate(score.get('tracks', [])):
        raw = tr.get('instrument', '')
        label = f'track "{tr.get("name", i)}"'
        if isinstance(raw, dict) or 'layers' in tr:
            out.append(f'{label}: the environment is written inline in the score; make it a preset in presets/environments/ and use env:<name>')
            continue
        if not str(raw).startswith('env:'):
            continue
        name = str(raw)[4:]
        cfg = presets.exact('environments', name)
        if cfg is None:
            continue                                   # track_problems already reports a missing preset
        if not _owned(cfg):
            out.append(f'{label}: environment "{name}" is a shipped example of the skill; copy it into the project and tune it: '
                       f'presets.py scaffold environments {_norm(name)} --from {_norm(name)} --project <dir>')
            continue
        if _placeholder(cfg.get('character')):
            out.append(f'environments/{_norm(name)}.json: "character" is empty or still the placeholder; write one sentence on the place and why these layers')
        env_tracks += 1
        # a bed is a layer with kind 'bed', several scenes mixed as one bed, or a scene that keeps sounding;
        # the rule lives in environment.preset_is_bed so a physical scene is judged by what it is
        has_bed = has_bed or envmod.preset_is_bed(cfg)
        for prob in envmod.preset_problems(cfg):
            out.append(f'environments/{_norm(name)}.json: {prob}')
    if env_tracks and not has_bed:
        out.append('no environment preset in the score has a bed (a steady, wide layer with nothing recognisable in it: a layer '
                   'with kind "bed", "scene_layers", or a scene with a continuous mechanism such as flow, foliage, granular, '
                   'rolling, gait or repeated_impact); a place needs one')
    scripts = Path(project) / 'scripts'
    for py in sorted(scripts.glob('*.py')) if scripts.is_dir() else []:
        text = py.read_text(encoding='utf-8', errors='replace')
        if re.search(r'^\s*(import environment|from environment import|.*synth_(noise_bed|resonant_gust|fm_chirp|impulse|stridulation|water|formant|doppler|rain|cricket|bird|voice_bouts|syllable))', text, re.M):
            out.append(f'scripts/{py.name}: builds ambience in code; put it in a preset in presets/environments/ and use env:<name> in the score')
    return out


SOURCE_HEAD = re.compile(r'^#+\s*real-world references:\s*(.+?)\s*$', re.I | re.M)


def reference_sections(project):
    """{slug: (urls, estimate_reason, has_licence_line)} from the 'Real-world references: <slug>' sections of reports/research_*.md."""
    found = {}
    reports = Path(project) / 'reports'
    for n in sorted(reports.glob('research_*.md')) if reports.is_dir() else []:
        text = n.read_text(encoding='utf-8', errors='replace')
        heads = list(SOURCE_HEAD.finditer(text))
        for j, m in enumerate(heads):
            body = text[m.end(): heads[j + 1].start() if j + 1 < len(heads) else len(text)]
            body = re.split(r'^#{1,2}\s', body, maxsplit=1, flags=re.M)[0]
            est = re.search(r'no measurement found:\s*estimate\s*[:\-]?\s*(\S.*)', body, re.I)
            lic = bool(re.search(r'^\W*licen[cs]e:\s*(?!.*todo)\S', body, re.I | re.M))
            found[_norm(m.group(1))] = (sorted(set(re.findall(r'https?://[^\s)>\]]+', body))), est.group(1).strip() if est else None, lic)
    return found


def reference_problems(score, project):
    """Every sound this project made itself (env: and sfx: presets in presets/) must say what real sound it rests on:
    "sources": [slug, ...] in the preset, and a '## Real-world references: <slug>' section with two URLs (and a Licence line),
    or 'No measurement found: ESTIMATE <reason>'. Shipped defaults are neutral and need none. Project mode only."""
    presets.add_project(str(project))
    refs, out, seen = reference_sections(project), [], set()
    for i, tr in enumerate(score.get('tracks', [])):
        raw = str(tr.get('instrument', ''))
        kind = 'environments' if raw.startswith('env:') else 'sfx' if raw.startswith('sfx:') else None
        if kind is None:
            continue
        name = _norm(raw.split(':', 1)[1])
        cfg = presets.exact(kind, name)
        if cfg is None or not _owned(cfg) or (kind, name) in seen:
            continue
        seen.add((kind, name))
        where = f'{kind}/{name}.json'
        slugs = [_norm(x) for x in cfg.get('sources') or []]
        if not slugs:
            out.append(f'{where}: no "sources". Research the real sound, add a "## Real-world references: <slug>" section to '
                       f'reports/research_<topic>.md (research_kb.py --sounds), and list the slug in "sources"')
        for slug in slugs:
            urls, est, lic = refs.get(slug, (None, None, False))
            if urls is None:
                out.append(f'{where}: source "{slug}" has no "## Real-world references: {slug}" section in reports/research_*.md')
            elif len(urls) < 2 and not est:
                out.append(f'{where}: source "{slug}" has {len(urls)} URL(s); give at least two, or write '
                           f'"No measurement found: ESTIMATE <reason>"')
            elif not lic:
                out.append(f'{where}: source "{slug}" has no "Licence:" line (say whether the recording may be kept, or that it was only analysed)')
    return out


def space_problems(score, project):
    """The piece's room must be a space preset of this project (kind "spaces"), written from the research."""
    presets.add_project(str(project))
    name = score.get('space') or score.get('room')
    if not name:
        return ['score has no "space": name a preset in presets/spaces/ (scaffold: presets.py scaffold spaces <name> --project <dir>)']
    if name == 'none':
        return []
    cfg = presets.exact('spaces', name)
    if cfg is None:
        return [f'score space "{name}" has no preset; create it: presets.py scaffold spaces {_norm(name)} --project <dir>']
    if not _owned(cfg):
        return [f'score space "{name}" is a shipped fallback of the skill; copy it into the project and tune it: '
                f'presets.py scaffold spaces {_norm(name)} --from {_norm(name)} --project <dir>']
    if _placeholder(cfg.get('character')):
        return [f'spaces/{_norm(name)}.json: "character" is empty or still the placeholder; write one sentence on the place']
    return []


def _mix_immersive(score):
    name = score.get('mix_preset')
    if not name:
        return None
    try:
        imm = (presets.exact('mix', name) or {}).get('immersive') or {}
    except Exception:
        return None
    return imm if imm.get('enabled') else None


def staging_report(score, project):
    """One line per track: where it sits and by which route the mixer will spatialise it (information, never blocks)."""
    presets.add_project(str(project))
    space = presets.exact('spaces', score.get('space') or score.get('room') or '') or {}
    imm = _mix_immersive(score)
    out = []
    for i, tr in enumerate(score.get('tracks', [])):
        inst = tr.get('instrument', '')
        if isinstance(inst, int):
            cfg = {}
        elif str(inst).startswith('sfx:'):
            cfg = presets.exact('sfx', str(inst)[4:]) or {}
        elif str(inst).startswith('env:'):
            cfg = presets.exact('environments', str(inst)[4:]) or {}
        else:
            cfg = presets.exact('instruments', inst) or presets.exact('vocals', inst) or {}
        sp = dict(cfg.get('spatial') or {}, **(tr.get('spatial') or {}))
        if not sp:
            out.append(f'staging {tr.get("name", i)}: no spatial block (plain pan)')
            continue
        role = tr.get('role') or cfg.get('role') or 'chord'
        kind = sp.get('kind', 'bed' if tr.get('role') == 'environment' or role == 'environment' else None)
        route = 'binaural' if sp.get('binaural') or sp.get('trajectory') else 'stereo'
        if imm and role != 'environment' and sp.get('binaural') is not False:
            route = 'binaural'
        if kind == 'bed':
            route = 'stereo (bed)'
        elif kind == 'spot' and 'binaural' not in sp and (space.get('binaural') or {}).get('spot') and not (imm and role != 'environment'):
            route = 'binaural (spot)'
        out.append(f'staging {tr.get("name", i)}: azimuth {sp.get("azimuth", 0)}, distance {sp.get("distance", 1.5)} m, {route}')
    return out


def staging_of(project):
    for s in sorted((project / 'direction').glob('*.json')) if (project / 'direction').is_dir() else []:
        try:
            d = json.loads(s.read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d.get('spatial_staging') or d.get('staging'), dict):
            return d.get('spatial_staging') or d.get('staging')
    return {}


def stage_problems(score, project):
    """Every custom preset in use needs its own spot on the stage (azimuth + distance); a shared spot is flat."""
    presets.add_project(str(project))
    out, spots, staging = [], {}, staging_of(Path(project))
    for i, tr in enumerate(score.get('tracks', [])):
        if is_builtin(tr):
            continue
        inst = tr.get('instrument', '')
        cfg = presets.exact('instruments', inst) or presets.exact('vocals', inst)
        if cfg is None:
            continue                                  # already reported by track_problems
        sp = cfg.get('spatial') or {}
        if 'azimuth' not in sp or 'distance' not in sp:
            out.append(f'preset "{_norm(inst)}" has no spatial.azimuth and spatial.distance '
                       '(place it from the direction sheet\'s staging; template: presets.py scaffold)')
            continue
        spots.setdefault((float(sp['azimuth']), float(sp['distance'])), []).append(_norm(inst))
        want = {_norm(k): v for k, v in staging.items() if isinstance(v, dict)}.get(_norm(inst))
        try:
            if want and (abs(float(want['azimuth']) - float(sp['azimuth'])) > 10 or abs(float(want['distance']) - float(sp['distance'])) > 0.75):
                out.append(f'preset "{_norm(inst)}" sits at azimuth {sp["azimuth"]}, distance {sp["distance"]} but the direction '
                           f'sheet stages it at azimuth {want["azimuth"]}, distance {want["distance"]}; make them agree')
        except (KeyError, TypeError, ValueError):
            pass                                       # unfilled placeholders are caught by the TODO check
    for (az, d), names in spots.items():
        if len(set(names)) > 1:
            out.append(f'flat stage: {", ".join(sorted(set(names)))} all sit at azimuth {az}, distance {d}; '
                       'give each its own azimuth/distance')
    return out


def effective_elevations(score, cfg, project):
    """{track name: (role, elevation, spatial, instrument)} as the score asks for it: track spatial, else instrument
    preset, else height_by_role. The mixer floors bass and drums at 0 deg; the value here stays the requested one so
    the gate can tell the writer it will be ignored."""
    presets.add_project(str(project))
    out = {}
    imm = cfg if (cfg or {}).get('enabled') else None
    for i, tr in enumerate(score.get('tracks', [])):
        inst = tr.get('instrument', '')
        pc = presets.exact('instruments', inst) or presets.exact('vocals', inst) or {}
        tr_sp = tr.get('spatial') or {}
        sp = dict(pc.get('spatial') or {})
        sp.update(tr_sp)
        role = tr.get('role') or pc.get('role') or 'chord'
        if imm and 'elevation' not in tr_sp and float(sp.get('elevation', 0.0)) == 0.0:
            el = float((imm.get('height_by_role') or {}).get(role, 0.0))
        elif 'elevation' in sp:
            el = sp['elevation']
        else:
            el = (cfg.get('height_by_role') or {}).get(role, 0.0) if cfg else 0.0
        out[tr.get('name', f'track{i}')] = (role, float(el), sp, inst)
    return out


def immersive_problems(score, project):
    """When the piece's mix preset switches "immersive" on: the block must be real, the head data present, heights legal
    (within max_elevation, none on bass or drums), agreeing with the direction sheet, and at least min_height_tracks lifted."""
    presets.add_project(str(project))
    name = score.get('mix_preset')
    mp = presets.exact('mix', name) if name else None
    cfg = (mp or {}).get('immersive')
    if not cfg or not cfg.get('enabled'):
        return []
    out = []
    if not isinstance(cfg.get('height_by_role'), dict) or 'max_elevation' not in cfg:
        out.append(f'mix preset "{name}": immersive needs height_by_role {{role: degrees}} and max_elevation (scaffold: presets.py scaffold mix)')
    if _placeholder(mp.get('character', '')):
        out.append(f'mix preset "{name}": "character" is empty or still the placeholder; immersive pieces need the mix described')
    try:
        from spatial_hrtf import binaural
        if not binaural.available():
            out.append('immersive needs the measured head data: run `python -m spatial_hrtf.data` from scripts/ (setup_project.py does it)')
    except Exception as e:
        out.append(f'immersive: spatial_hrtf could not be loaded ({e})')
    staging = {_norm(k): v for k, v in staging_of(Path(project)).items() if isinstance(v, dict)}
    mx, lifted = float(cfg.get('max_elevation', 60.0)), 0
    for tname, (role, el, sp, inst) in effective_elevations(score, cfg, project).items():
        if role in ('bass', 'drum') and el != 0:
            out.append(f'track "{tname}": a {role} at elevation {el:g} cannot be placed by ear (no pinna cue at low frequency); set it to 0')
            el = 0.0                                                    # the mixer floors it, so it is not a lifted track
        if abs(el) > mx:
            out.append(f'track "{tname}": elevation {el:g} is beyond max_elevation {mx:g}')
        want = staging.get(_norm(tname)) or staging.get(_norm(inst))
        if want and 'elevation' in want and 'elevation' in sp and abs(float(want['elevation']) - el) > 10:
            out.append(f'track "{tname}": elevation {el:g} but the direction sheet stages it at {want["elevation"]}; make them agree')
        lifted += el >= 3.0
    if lifted < int(cfg.get('min_height_tracks', 1)):
        out.append(f'immersive is on but only {lifted} track(s) are lifted (min_height_tracks {cfg.get("min_height_tracks", 1)}): '
                   'raise pads/environments in height_by_role or the staging, or turn immersive off')
    return out


def warnings(project, score=None):
    """Settings that are stored but not applied, or applied twice. Returns lines, never blocks."""
    out = (double_distance_warnings(score, project) + staging_report(score, project)) if score else []
    presets.add_project(str(project))
    if score is not None:
        import sfz_libs
        out += sfz_libs.sfz_warnings(score, project)
        refs = {t for t, _, _ in sfz_libs.score_refs(score)}
        for t in score.get('tracks', []):          # the libraries' authors: "reverb is essential"
            if t.get('name') in refs and float(t.get('reverb', (presets.find_instrument(str(t.get('instrument', ''))) or {}).get('reverb', 0.0))) <= 0.0:
                out.append(f'track "{t.get("name")}" plays an SFZ library with no reverb: the libraries are dry and recorded in different rooms; set reverb on the instrument preset')
    if score is not None and not score.get('piece_type'):
        import gate_profiles
        gp = gate_profiles.resolve(score)
        out.append(f'no "piece_type" in the score: the gate inferred "{gp.label}" ({gp.how}{": " + gp.why if gp.why else ""}). '
                   f'Declare it ("piece_type": "..."; gate_profiles.py list) so the gate does not depend on keywords')
    for name, cfg in presets.load('environments').items():
        if _owned(cfg):
            out += [f'environments/{name}.json: {w}' for w in envmod.legacy_alias_warnings(cfg)]
    imm = _mix_immersive(score) if score is not None else None
    names = []
    for p in sorted((project / 'presets').rglob('*.json')) if (project / 'presets').is_dir() else []:
        try:
            sp = json.loads(p.read_text(encoding='utf-8')).get('spatial') or {}
        except Exception:
            continue
        if ('elevation' in sp or 'space' in sp) and not sp.get('binaural'):
            if imm:
                continue
            names.append(p.stem)
    if not names:
        return out
    return out + [f'{len(names)} preset(s) set spatial.elevation/space ({", ".join(names[:3])}{", ..." if len(names) > 3 else ""}); '
            'the mixer stores but does not apply them unless spatial.binaural is true (azimuth, distance, width, reverb are applied)']


def double_distance_warnings(score, project):
    """An env track whose preset layers already set a distance, plus a track-level distance, is filtered twice."""
    presets.add_project(str(project))
    out = []
    for tr in score.get('tracks', []):
        inst = str(tr.get('instrument', ''))
        if not inst.startswith('env:') and tr.get('role') != 'environment':
            continue
        cfg = presets.find_environment(inst.split(':', 1)[-1]) or {}
        track_d = float((tr.get('spatial') or {}).get('distance', 0) or 0)
        # A physical scene propagated itself (propagate.py). The mixer skips its own distance law for that stem, so the
        # track distance only pans; saying so beats silently ignoring it.
        scene_d = ((cfg.get('scene') or {}).get('propagation') or {}).get('distance_m')
        if scene_d is None:
            ds = [float((l.get('propagation') or {}).get('distance_m')) for l in cfg.get('scene_layers') or []
                  if (l.get('propagation') or {}).get('distance_m') is not None]
            scene_d = max(ds) if ds else None
        if scene_d is not None and track_d > 1.5:
            out.append(f'track "{tr.get("name", inst)}": the scene already propagated this sound from {float(scene_d):g} m '
                       '(1/r, air loss, ground reflection); the track\'s spatial.distance now only sets pan and width — '
                       'set the distance in the scene propagation, not twice')
            continue
        layered = any(float((l.get('spatial') or {}).get('distance', 0)) > 2.0 for l in cfg.get('layers', []))
        if layered and track_d > 1.5:
            out.append(f'track "{tr.get("name", inst)}": distance is set in the environment preset layers and again on the '
                       'track, so the highs are filtered twice; keep one (layer distances for a scene, track distance for one bed)')
    return out


def gate_problems(score, project):
    """Gate profiles (project presets/gate/) must be valid, the score's piece_type must name one, and its "gate" overrides must pass."""
    import gate_profiles
    import sfz_libs
    out = gate_profiles.problems([str(project)]) + sfz_libs.problems([str(project)])
    if score is not None:
        out += gate_profiles.resolve(score).errors + sfz_libs.sfz_problems(score, project)
    return out


def problems(score, project):
    project = Path(project).resolve()
    out = [f'missing folder {d}/ (run: setup_project.py --new-project <dir>)' for d in SCAFFOLD if not (project / d).is_dir()]
    out += research_problems(project) + direction_problems(project) + preset_file_problems(project)
    if score is not None:
        out += track_problems(score, project) + stage_problems(score, project) + ambience_problems(score, project) + reference_problems(score, project) + space_problems(score, project) + immersive_problems(score, project)
        out += gate_problems(score, project)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    project = Path(sys.argv[1])
    if not project.is_dir() or (len(sys.argv) > 2 and not Path(sys.argv[2]).is_file()):
        sys.exit(f'project folder or score file not found: {sys.argv[1:3]}')
    score = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8')) if len(sys.argv) > 2 else None
    probs = problems(score, project)
    for w in warnings(project, score):
        print('WARN ', w)
    for p in probs:
        print('FAIL ', p)
    print('project gate:', 'BLOCKED' if probs else 'ok')
    sys.exit(1 if probs else 0)


if __name__ == '__main__':
    main()
