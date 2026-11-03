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
"""extract_pipeline.py - orchestrator: song -> MIDI -> stems rebuilt from that MIDI (pure DSP, guided by a listening-model music_db).

Scope: instruments (and humming), drums, space and ambience. Sung, rapped and spoken vocals are not modelled.

    extract_pipeline.py setup --new-project DIR --song FILE [--no-env]   # project folder + own .venv-extraction
    extract_pipeline.py check-db DIR [--profile NAME] [--set k=v ...]    # validate music_db/ and print the priors
    extract_pipeline.py run DIR [--profile NAME] [--set k=v ...] [--stages a,b] [--max-attempts N]
    extract_pipeline.py status DIR

Runs in its own environment (requirements-extraction.txt, no neural models). If started from another Python it
re-launches itself in .venv-extraction. Every number comes from the profile (templates/extraction_profile.json)."""
import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.dirname(HERE)
sys.path.insert(0, HERE)

VENV = os.path.join(SK, '.venv-extraction')
REQ = os.path.join(SK, 'requirements-extraction.txt')
TREE = ['music_db', 'profiles', 'presets', 'prompts', 'out/stems', 'out/midi', 'reports']
# stage name -> (module, function). Modules are imported only when the stage runs.
STAGES = {'listen': ('listen', 'run'), 'voices': ('voices', 'run'), 'separate': ('separate', 'run'),
          'drums': ('drums', 'run'), 'resynth': ('resynth', 'run'), 'effects': ('effects', 'run'), 'spatial': ('spatial', 'run'), 'residual': ('residual', 'run'),
          'gate': ('gate', 'run'), 'enhance': ('enhance', 'run'), 'export': ('export', 'run')}


def venv_python():
    return os.path.join(VENV, 'Scripts' if os.name == 'nt' else 'bin', 'python.exe' if os.name == 'nt' else 'python')


def have_deps():
    try:
        import numpy, scipy, soundfile, librosa, pretty_midi, pyloudnorm, pedalboard  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_env():
    """Re-launch inside .venv-extraction when this interpreter lacks the dependencies."""
    if have_deps():
        return
    py = venv_python()
    if not os.path.isfile(py):
        sys.exit(f'dependencies missing and {VENV} does not exist. Run:  python {os.path.join(HERE, "extract_pipeline.py")} setup --new-project <dir> --song <file>')
    sys.exit(subprocess.call([py, os.path.abspath(__file__)] + sys.argv[1:]))


def make_env():
    if not shutil.which('uv'):
        sys.exit('uv is not installed; install it first (https://docs.astral.sh/uv/). Nothing is installed globally.')
    if not os.path.isfile(venv_python()):
        subprocess.check_call(['uv', 'venv', VENV])
    subprocess.check_call(['uv', 'pip', 'install', '--python', venv_python(), '-r', REQ])


from extraction.config import jdump, jload   # one implementation, shared with the extraction stages


def write_new(path, text):
    """Create a file only if it is absent, so a second `setup` changes nothing."""
    if os.path.exists(path):
        return False
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return True


STATUS_TEXT = """# Extraction status: {title}

Song: `{song}`

Scope: instruments (and humming), drums, space and ambience. Sung / rapped / spoken vocals are listed in `song.json` `ignored_vocals`, not modelled.

## Steps
1. [ ] Paste `prompts/gemini_listener_prompts.md` modules 1-6 into a listening model with the song; save its JSON in `music_db/`.
2. [ ] `extract_pipeline.py check-db .` is clean (no ERROR; read the WARNs).
3. [ ] `extract_pipeline.py run .`  (listen, voices, separate, residual, drums, effects, spatial, **resynth**, gate, export)
4. [ ] Read `reports/extraction_report.json` (the gate rows). Listen to `out/stems/` (voices rebuilt from MIDI, drums, ambient, effects, room, unmodelled) and `out/mix_resynth.wav`.
5. [ ] `out/midi/song.mid` and `drums.mid` are the cleaned MIDI; `presets/` holds samplers, instrument presets and drum one-shots.

## Decisions / feedback
(none yet)
"""


def cmd_setup(a):
    root = os.path.abspath(a.new_project)
    song = os.path.abspath(a.song)
    if not os.path.isfile(song):
        sys.exit(f'song not found: {song}')
    meta_path = os.path.join(root, 'project.json')
    if os.path.isfile(meta_path) and jload(meta_path).get('song') != song:
        sys.exit(f'{root} already belongs to {jload(meta_path).get("song")}; use another folder')
    created = []
    for d in TREE:
        p = os.path.join(root, *d.split('/'))
        if not os.path.isdir(p):
            os.makedirs(p)
            created.append(d + '/')
    st = os.stat(song)
    if write_new(meta_path, json.dumps({'schema': 'extraction.project/1', 'song': song, 'bytes': st.st_size,
                                         'title': os.path.splitext(os.path.basename(song))[0]}, indent=1)):
        created.append('project.json')
    prompts = os.path.join(SK, 'templates', 'gemini_listener_prompts.md')
    if write_new(os.path.join(root, 'prompts', 'gemini_listener_prompts.md'), open(prompts, encoding='utf-8').read()):
        created.append('prompts/gemini_listener_prompts.md')
    if write_new(os.path.join(root, 'profiles', 'project.json'),
                 json.dumps({'_about': 'Your overrides only. Keys come from templates/extraction_profile.json. Pass another file with --profile NAME.'}, indent=1)):
        created.append('profiles/project.json')
    title = os.path.splitext(os.path.basename(song))[0]
    if write_new(os.path.join(root, 'STATUS.md'), STATUS_TEXT.format(title=title, song=song)):
        created.append('STATUS.md')
    if not a.no_env:
        make_env()
    print(f'project: {root}')
    print('created: ' + (', '.join(created) if created else 'nothing (already set up)'))
    print(f'environment: {VENV if os.path.isfile(venv_python()) else "not created (--no-env)"}')
    print(f'scope: instruments, drums, space and ambience (no sung/rapped vocals). next: put the listening model\'s JSON in {os.path.join(root, "music_db")}, then: extract_pipeline.py check-db {root}')


def project_of(path):
    root = os.path.abspath(path)
    if not os.path.isfile(os.path.join(root, 'project.json')):
        sys.exit(f'{root} is not an extraction project (no project.json). Create one with: setup --new-project')
    meta = jload(os.path.join(root, 'project.json'))
    return root, meta


def load_cfg(root, a):
    from extraction import config
    try:
        return config.load(a.profile, a.set, root)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(f'profile error: {e}')


def cmd_check_db(a):
    ensure_env()
    root, _ = project_of(a.dir)
    from extraction import music_db
    cfg = load_cfg(root, a)
    lines, issues = music_db.report(music_db.load(os.path.join(root, 'music_db'), cfg), cfg)
    print('\n'.join(lines))
    sys.exit(1 if any(i[0] == 'ERROR' for i in issues) else 0)


def state_path(root):
    return os.path.join(root, 'reports', 'state.json')


def cmd_status(a):
    root, meta = project_of(a.dir)
    st = jload(state_path(root)) if os.path.isfile(state_path(root)) else {}
    have = sorted(os.listdir(os.path.join(root, 'music_db')))
    print(f'project {meta["title"]}\nsong {meta["song"]}\nmusic_db files: {have or "none yet"}')
    for name in STAGES:
        s = st.get(name)
        print(f'  {name:<9} ' + (f'done in {s["seconds"]:.1f} s ({s["when"]})' if s else '-'))


LOOP_BLOCK = ['voices', 'separate', 'residual', 'drums', 'effects', 'spatial', 'resynth', 'gate']      # what a retry attempt redoes


def run_stage(ctx, name, st, root):
    mod, fn = STAGES[name]
    try:
        stage = getattr(importlib.import_module('extraction.' + mod), fn)
    except ModuleNotFoundError as e:
        if e.name != 'extraction.' + mod:
            raise
        sys.exit(f'stage "{name}" is not built yet (extraction/{mod}.py missing)')
    t0 = time.time()
    print(f'[{name}] ...', flush=True)
    stage(ctx)
    st[name] = {'seconds': time.time() - t0, 'when': time.strftime('%Y-%m-%d %H:%M:%S')}
    jdump(st, state_path(root))
    print(f'[{name}] done in {st[name]["seconds"]:.1f} s', flush=True)


def fresh_data(data):
    """What a retry keeps from the listening stage; everything downstream is recomputed."""
    return {k: data[k] for k in ('tuning', 'spec', 'duration_s') if k in data}


def retry_loop(ctx, st, root):
    """Re-run the extraction block with one lever changed per attempt; keep the attempt with the lowest gate score."""
    from extraction import config
    cfg0 = ctx['cfg']
    levers, limit = cfg0['gate']['levers'], cfg0['gate']['max_attempts']
    attempts = [{'attempt': 1, 'lever': None, 'score': ctx['data']['gate']['score']}]
    best = (ctx['data']['gate']['score'], ctx['data'], cfg0, None)
    for k in range(2, limit + 1):
        if best[0] == 0 or k - 2 >= len(levers):
            break
        lever = levers[k - 2]
        print(f'--- attempt {k}: {lever[0]} = {lever[1]} (best score so far {best[0]})', flush=True)
        ctx2 = {**ctx, 'cfg': config.with_overrides(cfg0, [lever]), 'data': fresh_data(ctx['data'])}
        for name in LOOP_BLOCK:
            run_stage(ctx2, name, st, root)
        sc = ctx2['data']['gate']['score']
        attempts.append({'attempt': k, 'lever': lever, 'score': sc})
        if sc < best[0]:
            best = (sc, ctx2['data'], ctx2['cfg'], lever)
    if best[3] is not None and attempts[-1]['score'] != best[0]:
        print(f'--- re-running the best attempt ({best[3][0]} = {best[3][1]}) to restore its stems', flush=True)
        ctx3 = {**ctx, 'cfg': best[2], 'data': fresh_data(ctx['data'])}
        for name in LOOP_BLOCK:
            run_stage(ctx3, name, st, root)
        best = (best[0], ctx3['data'], best[2], best[3])
    ctx['data'], ctx['cfg'] = best[1], best[2]
    ctx['data']['attempts'] = attempts
    print('attempts: ' + '; '.join(f'#{x["attempt"]} score {x["score"]}' + (f' ({x["lever"][0]}={x["lever"][1]})' if x['lever'] else '') for x in attempts))
    jdump(attempts, os.path.join(root, 'reports', 'attempts.json'))


def cmd_run(a):
    ensure_env()
    root, meta = project_of(a.dir)
    from extraction import music_db
    cfg = load_cfg(root, a)
    if a.max_attempts:
        cfg['gate']['max_attempts'] = a.max_attempts
    db = music_db.load(os.path.join(root, 'music_db'), cfg)
    errors = [i for i in music_db.validate(db, cfg) if i[0] == 'ERROR']
    if errors:
        sys.exit('music_db has errors, run check-db first:\n' + '\n'.join(f'  {w}: {m}' for _, w, m in errors))
    wanted = a.stages.split(',') if a.stages else cfg['stages']
    bad = [s for s in wanted if s not in STAGES]
    if bad:
        sys.exit(f'unknown stage(s): {bad}. Known: {list(STAGES)}')
    ctx = {'root': root, 'song': meta['song'], 'cfg': cfg, 'db': db, 'priors': music_db.priors(db, cfg), 'data': {}}
    st = jload(state_path(root)) if os.path.isfile(state_path(root)) else {}
    for name in wanted:
        run_stage(ctx, name, st, root)
        if name == 'gate' and cfg['gate']['max_attempts'] > 1 and ctx['data']['gate']['score'] > 0:
            retry_loop(ctx, st, root)
    log_status(root, wanted, ctx)


def log_status(root, wanted, ctx):
    gate = ctx['data'].get('gate')
    line = f'- {time.strftime("%Y-%m-%d %H:%M")} ran {",".join(wanted)}' + (f'; gate score {gate["score"]}' if gate else '') + '\n'
    with open(os.path.join(root, 'STATUS.md'), 'a', encoding='utf-8') as f:
        f.write(line)


def cmd_kb(a):
    ensure_env()
    from extraction import config, knowledge, music_db
    if a.action == 'pitch-table':
        print(f'pitch table: {knowledge.build_pitch_table()} pitches -> {knowledge.PITCH_TABLE}')
        return
    root, _ = project_of(a.dir)
    cfg = config.load(project=root)
    db = music_db.load(os.path.join(root, 'music_db'), cfg)
    cur = jload(knowledge.SIGNATURES) if os.path.isfile(knowledge.SIGNATURES) else {'schema': 'music_db.signatures/1', 'instruments': {}}
    new = 0
    for ins in db['instruments']:
        if (cur['instruments'].get(ins['id']) or {}).get('measured'):
            continue
        new += ins['id'] not in cur['instruments']
        cur['instruments'][ins['id']] = music_db.to_signature(ins, cfg)
    jdump(cur, knowledge.SIGNATURES)
    print(f'{knowledge.SIGNATURES}: {len(cur["instruments"])} signatures ({new} new)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('setup')
    s.add_argument('--new-project', required=True)
    s.add_argument('--song', required=True)
    s.add_argument('--no-env', action='store_true', help='skip creating .venv-extraction')
    s.set_defaults(fn=cmd_setup)
    k = sub.add_parser('kb', help='grow the fallback knowledge base')
    k.add_argument('action', choices=['seed', 'pitch-table'])
    k.add_argument('dir', nargs='?')
    k.set_defaults(fn=cmd_kb)
    for name, fn in (('check-db', cmd_check_db), ('run', cmd_run), ('status', cmd_status)):
        p = sub.add_parser(name)
        p.add_argument('dir')
        if name != 'status':
            p.add_argument('--profile')
            p.add_argument('--set', action='append', default=[], metavar='section.key=value')
        if name == 'run':
            p.add_argument('--stages', help='comma list; default = profile stages')
            p.add_argument('--max-attempts', type=int)
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
